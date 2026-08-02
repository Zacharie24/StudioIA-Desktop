# -*- coding: utf-8 -*-
"""
correction_memory.py — Mémoire des corrections utilisateur

Stocke chaque correction avec le contexte (avant/après),
permet de rejouer l'analyse d'apprentissage et de
suivre l'évolution des règles par profil.

Structure de stockage :
    corrections/
        <profil_id>/
            <timestamp>__<projet_id>__<chapitre_id>.json
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

# Racine de stockage des corrections
MEMORY_DIR = Path(__file__).parent.parent.parent / "data" / "corrections"


def log(msg):
    print(f"[CORRECTION] {msg}")


def _assurer_dossier(profil_id):
    """Crée le dossier de corrections pour un profil si nécessaire"""
    dossier = MEMORY_DIR / profil_id
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def enregistrer_correction(profil_id, projet_id, chapitre_id,
                           texte_original, texte_corrige,
                           titre_chapitre="", sujet_projet=""):
    """
    Enregistre une correction utilisateur dans la mémoire.

    Args:
        profil_id: ID du profil actif au moment de la correction
        projet_id: ID du projet
        chapitre_id: "ch01", "ch02", etc.
        texte_original: le texte généré par l'IA avant correction
        texte_corrige: le texte après correction manuelle
        titre_chapitre: titre du chapitre (optionnel)
        sujet_projet: sujet du projet (optionnel)

    Returns:
        str: chemin du fichier de correction créé
    """
    dossier = _assurer_dossier(profil_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nom_fichier = f"{timestamp}__{projet_id}__{chapitre_id}.json"
    chemin = dossier / nom_fichier

    # Détecter les différences
    differences = _detecter_differences(texte_original, texte_corrige)

    correction = {
        "metadata": {
            "timestamp": timestamp,
            "profil_id": profil_id,
            "projet_id": projet_id,
            "chapitre_id": chapitre_id,
            "titre_chapitre": titre_chapitre,
            "sujet_projet": sujet_projet,
            "type": "correction_manuelle"
        },
        "avant": texte_original,
        "apres": texte_corrige,
        "differences": differences,
        "apprentissage": {
            "analysee": False,
            "proposition": None,
            "validee": False,
            "date_validation": None
        }
    }

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(correction, f, ensure_ascii=False, indent=2)

    log(f"Correction enregistrée: {nom_fichier} ({len(differences)} différences)")
    return str(chemin)


def _detecter_differences(original, corrige):
    """
    Détecte les différences textuelles entre original et corrigé.
    Retourne une liste de dictionnaires décrivant chaque changement.
    """
    differences = []

    if original == corrige:
        return differences

    # Découper en phrases
    phrases_original = re.findall(r'[^.!?]+[.!?]*', original)
    phrases_corrige = re.findall(r'[^.!?]+[.!?]*', corrige)

    # Comparer phrase par phrase
    i, j = 0, 0
    while i < len(phrases_original) or j < len(phrases_corrige):
        if i < len(phrases_original) and j < len(phrases_corrige):
            po = phrases_original[i].strip()
            pc = phrases_corrige[j].strip()

            if po != pc:
                # Vérifier si c'est une modification ou un ajout/suppression
                if po and pc and len(po) > 0 and len(pc) > 0:
                    # Comparer les mots
                    mots_o = set(po.lower().split())
                    mots_c = set(pc.lower().split())
                    similarite = len(mots_o & mots_c) / max(len(mots_o | mots_c), 1)

                    if similarite > 0.3:
                        # C'est une modification
                        differences.append({
                            "type": "modification",
                            "original": po,
                            "corrige": pc
                        })
                        i += 1
                        j += 1
                    else:
                        # Phrase différente — pourrait être remplacement
                        differences.append({
                            "type": "remplacement",
                            "original": po,
                            "corrige": pc
                        })
                        i += 1
                        j += 1
                else:
                    i += 1
                    j += 1
            else:
                i += 1
                j += 1
        elif i < len(phrases_original):
            # Phrase supprimée
            po = phrases_original[i].strip()
            if po:
                differences.append({"type": "suppression", "original": po, "corrige": ""})
            i += 1
        elif j < len(phrases_corrige):
            # Phrase ajoutée
            pc = phrases_corrige[j].strip()
            if pc:
                differences.append({"type": "ajout", "original": "", "corrige": pc})
            j += 1

    return differences


def lister_corrections(profil_id=None, limite=50):
    """
    Liste les corrections enregistrées, triées par date (récentes d'abord).

    Args:
        profil_id: filtrer par profil (None = tous)
        limite: nombre maximum de corrections

    Returns:
        list[dict]: corrections récentes
    """
    toutes = []

    dossiers = [MEMORY_DIR / profil_id] if profil_id else (MEMORY_DIR.iterdir() if MEMORY_DIR.exists() else [])
    for dossier in ([MEMORY_DIR / profil_id] if profil_id else
                    ([d for d in MEMORY_DIR.iterdir() if d.is_dir()] if MEMORY_DIR.exists() else [])):
        if not dossier.exists():
            continue
        for f in sorted(dossier.glob("*.json"), reverse=True)[:limite]:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    data["_fichier"] = str(f)
                    toutes.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    # Trier par timestamp décroissant
    toutes.sort(key=lambda x: x.get("metadata", {}).get("timestamp", ""), reverse=True)
    return toutes[:limite]


def charger_correction(chemin):
    """Charge une correction depuis son fichier"""
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log(f"Erreur chargement correction {chemin}: {e}")
        return None


def marquer_apprentissage_propose(chemin, proposition):
    """Marque une correction comme analysée avec une proposition de règle"""
    data = charger_correction(chemin)
    if not data:
        return False

    data["apprentissage"]["analysee"] = True
    data["apprentissage"]["proposition"] = proposition
    data["apprentissage"]["validee"] = False

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def marquer_apprentissage_valide(chemin):
    """Marque une proposition comme validée par l'utilisateur"""
    data = charger_correction(chemin)
    if not data:
        return False

    data["apprentissage"]["validee"] = True
    data["apprentissage"]["date_validation"] = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def statistiques(profil_id=None):
    """Retourne des stats sur les corrections"""
    corrections = lister_corrections(profil_id, limite=10000)
    total = len(corrections)
    analysees = sum(1 for c in corrections if c.get("apprentissage", {}).get("analysee"))
    validees = sum(1 for c in corrections if c.get("apprentissage", {}).get("validee"))
    total_diff = sum(len(c.get("differences", [])) for c in corrections)

    return {
        "total_corrections": total,
        "analysees": analysees,
        "validees": validees,
        "en_attente": total - analysees,
        "total_differences": total_diff
    }


if __name__ == "__main__":
    # Test
    original = "Seigneur je te remercie pour cette journee. Protege ma famille et mes amis."
    corrige = "Seigneur, je te remercie pour cette journee de grace. Protege ma famille, mes amis et tous ceux qui souffrent."

    path = enregistrer_correction(
        profil_id="prayer",
        projet_id="test_project",
        chapitre_id="ch01",
        texte_original=original,
        texte_corrige=corrige,
        titre_chapitre="Action de grace",
        sujet_projet="Priere du soir"
    )
    print(f"Correction sauvegardee: {path}")

    stats = statistiques("prayer")
    print(f"Stats: {stats}")
