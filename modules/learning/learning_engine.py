# -*- coding: utf-8 -*-
"""
learning_engine.py — Moteur d'apprentissage par analyse des corrections

Analyse les corrections utilisateur via le LLM local et propose
des mises à jour de règles pour le profil actif.

Cycle:
    1. Charger une correction non-analysée
    2. Envoyer (original → corrigé) au LLM avec le contexte du profil
    3. LLM propose une règle: "ajouter X à mots_a_eviter" ou "nouvelle regle: ..."
    4. Stocker la proposition
    5. Après validation humaine, intégrer la règle dans le profil
"""

import json
import os
import sys
import requests
from pathlib import Path

# Import des modules du projet
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.profiles.profile_manager import get_manager as get_profile_manager
from modules.learning.correction_memory import (
    lister_corrections, charger_correction, marquer_apprentissage_propose,
    marquer_apprentissage_valide, statistiques
)


def log(msg):
    print(f"[APPRENTISSAGE] {msg}")


def _appeler_llm(prompt, modele="mistral", temperature=0.3):
    """Appelle Ollama pour analyser"""
    try:
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": modele,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "repeat_penalty": 1.1}
        }, timeout=30)
        return r.json()["response"].strip()
    except requests.exceptions.Timeout:
        log("LLM timeout (30s)")
        return None
    except Exception as e:
        log(f"Erreur LLM: {e}")
        return None


def analyser_correction(chemin_correction):
    """
    Analyse une correction utilisateur et propose une règle.

    Args:
        chemin_correction: chemin vers le fichier de correction

    Returns:
        dict: proposition d'apprentissage ou None si échec
    """
    data = charger_correction(chemin_correction)
    if not data:
        log("Impossible de charger la correction")
        return None

    # Déjà analysée ?
    if data.get("apprentissage", {}).get("analysee"):
        log("Cette correction a déjà été analysée")
        return data["apprentissage"]["proposition"]

    profil_id = data["metadata"]["profil_id"]
    original = data["avant"]
    corrige = data["apres"]
    differences = data.get("differences", [])

    # Charger le profil pour connaître les règles actuelles
    pm = get_profile_manager()
    profil = pm.charger(profil_id)
    if not profil:
        log(f"Profil '{profil_id}' introuvable")
        return None

    rules = profil.get("rules", {})
    regles_actuelles = json.dumps({
        "regles_generales": rules.get("regles_generales", []),
        "mots_a_eviter": rules.get("mots_a_eviter", [])[:15],
        "mots_de_remplacement": rules.get("mots_de_remplacement", {}),
        "regles_grammaire": rules.get("regles_grammaire", []),
    }, ensure_ascii=False, indent=2)

    # Résumé des différences
    diff_text = ""
    for d in differences[:5]:
        if d["type"] == "modification":
            diff_text += f"  MODIFIÉ: \"{d['original']}\" → \"{d['corrige']}\"\n"
        elif d["type"] == "suppression":
            diff_text += f"  SUPPRIMÉ: \"{d['original']}\"\n"
        elif d["type"] == "ajout":
            diff_text += f"  AJOUTÉ: \"{d['corrige']}\"\n"

    prompt = f"""Tu es un expert en analyse de contenu et amélioration de règles éditoriales.

CONTEXTE :
Un utilisateur a corrigé un texte généré par IA dans un projet de type "{profil_id}".

RÈGLES ACTUELLES DU PROFIL :
{regles_actuelles}

TEXTE ORIGINAL (généré par IA) :
{original}

TEXTE CORRIGÉ (par l'utilisateur) :
{corrige}

DIFFÉRENCES DÉTECTÉES :
{diff_text}

TA MISSION :
Analyse la correction et détermine QUELLE RÈGLE pourrait être ajoutée ou modifiée
pour que l'IA produise directement le bon texte à l'avenir.

Parmi ces types de propositions possibles :
1. "ajouter_mot_eviter" — un mot ou une expression à éviter
2. "ajouter_remplacement" — remplacer un mot complexe par un plus simple
3. "nouvelle_regle_generale" — une règle de style à ajouter
4. "nouvelle_regle_grammaire" — une règle de grammaire
5. "aucune" — la correction est un choix stylistique, pas une règle

Réponds UNIQUEMENT avec ce JSON valide (pas d'autre texte) :
{{
    "type_proposition": "ajouter_mot_eviter|ajouter_remplacement|nouvelle_regle_generale|nouvelle_regle_grammaire|aucune",
    "valeur": "la règle ou le mot à ajouter",
    "remplacement": "si type=ajouter_remplacement, le mot simple équivalent",
    "justification": "Pourquoi cette règle aiderait (1 phrase)",
    "confiance": 0.8
}}"""

    reponse = _appeler_llm(prompt)
    if not reponse:
        log("Pas de réponse du LLM")
        return None

    # Extraire le JSON
    try:
        debut = reponse.find("{")
        fin = reponse.rfind("}") + 1
        proposition = json.loads(reponse[debut:fin])
    except (json.JSONDecodeError, ValueError) as e:
        log(f"Erreur parsing réponse LLM: {e}")
        log(f"Réponse brute: {reponse[:200]}...")
        return None

    # Sauvegarder la proposition
    marquer_apprentissage_propose(chemin_correction, proposition)

    log(f"Proposition: {proposition.get('type_proposition')} "
        f"— {proposition.get('valeur', '')[:60]}")
    return proposition


def appliquer_proposition(proposition, profil_id="prayer"):
    """
    Applique une proposition validée au profil.

    Args:
        proposition: dict de la proposition
        profil_id: ID du profil à modifier

    Returns:
        bool: True si la règle a été intégrée
    """
    pm = get_profile_manager()
    type_prop = proposition.get("type_proposition")

    if type_prop == "aucune":
        log("Proposition 'aucune' — rien à appliquer")
        return True

    # Charger les règles actuelles
    profil = pm.charger(profil_id)
    if not profil:
        log(f"Profil '{profil_id}' introuvable")
        return False

    rules = profil.get("rules", {})
    modifications = {}

    valeur = proposition.get("valeur", "").strip()
    if not valeur:
        log("Proposition vide, ignorée")
        return False

    if type_prop == "ajouter_mot_eviter":
        mots_eviter = rules.get("mots_a_eviter", [])
        if valeur not in mots_eviter:
            mots_eviter.append(valeur)
            modifications["mots_a_eviter"] = mots_eviter
            log(f"Ajouté à mots_a_eviter: '{valeur}'")

    elif type_prop == "ajouter_remplacement":
        remplacement = proposition.get("remplacement", "").strip()
        if remplacement:
            mots_remplacement = rules.get("mots_de_remplacement", {})
            if valeur not in mots_remplacement:
                mots_remplacement[valeur] = remplacement
                modifications["mots_de_remplacement"] = mots_remplacement
                log(f"Ajouté remplacement: '{valeur}' → '{remplacement}'")

    elif type_prop == "nouvelle_regle_generale":
        regles = rules.get("regles_generales", [])
        if valeur not in regles:
            regles.append(valeur)
            modifications["regles_generales"] = regles
            log(f"Ajouté règle générale: '{valeur}'")

    elif type_prop == "nouvelle_regle_grammaire":
        regles = rules.get("regles_grammaire", [])
        if valeur not in regles:
            regles.append(valeur)
            modifications["regles_grammaire"] = regles
            log(f"Ajouté règle grammaire: '{valeur}'")

    if modifications:
        pm.mettre_a_jour_regles(profil_id, modifications)
        log(f"Règles appliquées au profil '{profil_id}'")
        return True
    else:
        log("Aucune modification nécessaire")
        return True


def analyser_toutes_corrections(profil_id=None, limite=20):
    """
    Analyse toutes les corrections en attente.

    Args:
        profil_id: filtrer par profil
        limite: nombre max de corrections à analyser

    Returns:
        list[dict]: propositions générées
    """
    corrections = lister_corrections(profil_id, limite)
    non_analysees = [c for c in corrections if not c.get("apprentissage", {}).get("analysee")]

    log(f"{len(non_analysees)}/{len(corrections)} corrections non analysées")

    propositions = []
    for corr in non_analysees[:limite]:
        chemin = corr.get("_fichier")
        if not chemin:
            continue
        prop = analyser_correction(chemin)
        if prop:
            propositions.append(prop)

    return propositions


def generer_rapport_apprentissage(profil_id=None):
    """Génère un rapport texte sur l'état des apprentissages"""
    stats = statistiques(profil_id)
    corrections = lister_corrections(profil_id, 10)

    rapport = []
    rapport.append("=== RAPPORT D'APPRENTISSAGE ===")
    rapport.append(f"Total corrections: {stats['total_corrections']}")
    rapport.append(f"Analysées: {stats['analysees']}")
    rapport.append(f"Validées: {stats['validees']}")
    rapport.append(f"En attente: {stats['en_attente']}")
    rapport.append(f"Différences totales: {stats['total_differences']}")
    rapport.append("")

    if corrections:
        rapport.append("Dernières corrections:")
        for c in corrections[:5]:
            meta = c.get("metadata", {})
            prop = c.get("apprentissage", {}).get("proposition", {})
            status = "VALIDEE" if c.get("apprentissage", {}).get("validee") else \
                     "ANALYSEE" if c.get("apprentissage", {}).get("analysee") else "EN_ATTENTE"
            rapport.append(f"  [{status}] {meta.get('projet_id','?')}/{meta.get('chapitre_id','?')}")
            if prop:
                rapport.append(f"         → {prop.get('type_proposition','?')}: {prop.get('valeur','')[:50]}")

    return "\n".join(rapport)


if __name__ == "__main__":
    # Test
    from correction_memory import enregistrer_correction

    # Simuler une correction
    path = enregistrer_correction(
        profil_id="prayer",
        projet_id="test_apprentissage",
        chapitre_id="ch01",
        texte_original="Seigneur je te remercie pour cette journée. Protège ma famille.",
        texte_corrige="Seigneur, je te remercie pour cette journée de grace. Protege ma famille bien-aimee.",
        titre_chapitre="Action de grace",
        sujet_projet="Priere du soir"
    )
    print(f"Correction: {path}")

    # Analyser
    prop = analyser_correction(path)
    if prop:
        print(f"\nProposition: {json.dumps(prop, ensure_ascii=False, indent=2)}")
    else:
        print("Pas de proposition (LLM non disponible)")

    print(f"\n{generer_rapport_apprentissage('prayer')}")
