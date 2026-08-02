# -*- coding: utf-8 -*-
"""
content_planner.py — Planificateur de contenu automatique

Analyse les tendances YouTube et les performances passees
pour suggerer le meilleur contenu a produire.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.profiles.profile_manager import get_manager as get_profile_manager
try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(_rac))
    from core import paths


def _lire_config():
    config_path = Path(__file__).parent.parent.parent / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def _appeler_llm(prompt, modele="mistral", temperature=0.4, timeout=30):
    """Interroge Ollama local"""
    import requests
    try:
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": modele,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
            "max_tokens": 512
        }, timeout=timeout)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return None
    except:
        return None


def analyser_tendances_youtube(channel_id=None):
    """
    Analyse les tendances YouTube si l'API est configuree.
    Retourne les sujets qui performent le mieux.
    """
    config = _lire_config()
    if not config.get("youtube_api_key"):
        return None

    try:
        from modules.youtube_analyzer.youtube_stats import analyser_performances, chercher_chaine
        # Utiliser la chaine passee ou chercher la chaine du profil
        cid = channel_id
        if not cid:
            # Chercher une chaine par defaut (celle du profil actif)
            profil_id = config.get("profil_actif", "prayer")
            pm = get_profile_manager()
            profil = pm.charger(profil_id)
            channel_name = None
            if profil:
                channel_name = profil.get("manifest", {}).get("youtube_channel")
            if channel_name:
                cid = chercher_chaine(channel_name)

        if not cid:
            return None

        resultat = analyser_performances(cid)
        return resultat
    except:
        return None


def suggerer_contenu(profil_id="prayer", tendances=None):
    """
    Utilise l'IA pour suggerer le prochain contenu a produire.
    Prend en compte les tendances YouTube, les regles du profil,
    et les contenus deja produits.
    """
    config = _lire_config()

    # Charger le profil
    pm = get_profile_manager()
    profil = pm.charger(profil_id)
    if not profil:
        return {"erreur": "Profil introuvable"}

    manifest = profil.get("manifest", {})
    nom_profil = manifest.get("name", profil_id)
    type_contenu = manifest.get("type_contenu", "generic")
    langue = manifest.get("langue", "fr")

    # Charger les projets existants
    projects_path = paths.PROJECTS_DIR
    sujets_existants = []
    if projects_path.exists():
        for p in sorted(projects_path.iterdir(), reverse=True)[:20]:
            pjson = p / "project.json"
            if pjson.exists():
                try:
                    with open(pjson, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    sujets_existants.append(data.get("sujet", p.name)[:60])
                except:
                    pass

    # --- Apprentissage depuis l'audit de la chaine (ce qui MARCHE) ---
    lecons_audit = _charger_lecons_audit()
    lecons_str = ""
    if lecons_audit:
        lecons_str = "\nCE QUI MARCHE (apprentissage de l'audit de ta chaine):\n" + lecons_audit

    # --- Besoins des spectateurs (commentaires) ---
    besoins_str = _charger_besoins_commentaires()

    # Preparer le prompt pour l'IA
    tendances_str = ""
    if tendances:
        videos = tendances.get("videos", [])
        if videos:
            tendances_str = "\nVideos qui performent bien:\n"
            for v in videos[:5]:
                tendances_str += f"- {v.get('titre', '?')} ({v.get('vues', 0)} vues, {v.get('engagement', 0)}% engagement)\n"

    prompt = f"""Tu es un planificateur de contenu pour un profil YouTube.

Profil: {nom_profil}
Type de contenu: {type_contenu}
Langue: {langue}
{tendances_str}
{lecons_str}
{besoins_str}

Contenu deja produit (a eviter de repeter):
{chr(10).join(f'- {s}' for s in sujets_existants[:10]) if sujets_existants else 'Aucun contenu existant'}

Suggere UN sujet de contenu a produire maintenant, qui s'appuie SUR CE QUI MARCHE
deja (duree, mots, themes gagnants) et qui repond aux besoins des spectateurs.
Reponds UNIQUEMENT au format JSON (sans markdown):
{{
  "titre": "titre du contenu",
  "description": "description courte",
  "type": "{type_contenu}",
  "raison": "pourquoi ce sujet maintenant",
  "mots_cles": ["mot1", "mot2", "mot3"],
  "duree_recommandee_minutes": <nombre entier>
}}"""

    # Duree recommandee par l'audit (fallback si l'IA ne repond pas)
    import re as _re
    duree_audit = None
    if lecons_audit:
        m = _re.search(r"~(\d+(?:[.,]\d+)?) minutes", lecons_audit)
        if m:
            duree_audit = int(float(m.group(1).replace(",", ".")))

    reponse = _appeler_llm(prompt)
    if not reponse:
        # Fallback: suggestion par defaut (en tenant compte de ce qui marche)
        lecon_mot = ""
        if lecons_audit:
            m = _re.search(r"Mots qui marchent[^\n]*: ([^\n]+)", lecons_audit)
            if m:
                lecon_mot = m.group(1).strip().split(", ")[0]
        return {
            "titre": f"Contenu {nom_profil} du {datetime.now().strftime('%d/%m/%Y')}",
            "description": f"Contenu automatique genere pour le profil {nom_profil}",
            "type": type_contenu,
            "raison": "Suggestion automatique (IA indisponible)",
            "mots_cles": [nom_profil.lower(), lecon_mot] if lecon_mot else [nom_profil.lower()],
            "duree_recommandee_minutes": duree_audit
        }

    # Extraire le JSON
    import re
    match = re.search(r'\{.*\}', reponse, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass

    return {
        "titre": f"Contenu {nom_profil}",
        "description": f"Genere pour {nom_profil}",
        "type": type_contenu,
        "raison": "Suggestion par defaut",
        "mots_cles": []
    }


def _charger_lecons_audit():
    """
    Charge les lecons de l'audit le plus recent de la chaine cible :
    duree optimale, mots gagnants, meilleure video, plan de rythme.

    Returns:
        str: texte des lecons ("" si aucun audit)
    """
    audits_dir = Path(__file__).parent.parent.parent / "data" / "audits"
    if not audits_dir.exists():
        return ""

    # Fichier audit le plus recent
    fichiers = sorted(audits_dir.glob("audit_*.json"))
    if not fichiers:
        return ""

    try:
        with open(fichiers[-1], "r", encoding="utf-8") as f:
            audit = json.load(f)
    except Exception:
        return ""

    lignes = []
    patterns = audit.get("patterns", {})
    motifs = patterns.get("motifs_gagnants", [])[:5]
    if motifs:
        lignes.append("- Mots qui marchent dans tes titres : " +
                      ", ".join(m.get("mot", "") for m in motifs))
    duree = patterns.get("duree_optimale") or patterns.get("duree_top")
    if duree:
        lignes.append(f"- Duree qui marche le mieux : ~{duree} minutes")
    meilleure = audit.get("meilleure")
    if meilleure and meilleure.get("titre"):
        lignes.append(f"- Ta meilleure video : '{meilleure['titre'][:60]}' "
                      f"({meilleure.get('vues', 0)} vues) — inspire-toi de ce theme")
    # Plan de rythme
    plan = audit.get("plan_rythme")
    if plan and plan.get("a_reproduire"):
        for v in plan["a_reproduire"][:2]:
            if v.get("titre"):
                lignes.append(f"- Video a reproduire : '{v['titre'][:55]}'")
    # Recommandations
    for r in audit.get("recommandations", [])[:2]:
        if r.get("titre"):
            lignes.append(f"- Conseil : {r['titre']}")

    return "\n".join(lignes)


def _charger_besoins_commentaires():
    """
    Charge les besoins des spectateurs depuis l'analyse des commentaires
    (modules/youtube_analyzer/comment_analyzer.py -> data/audits/comments_analysis.json).
    """
    analysis_file = Path(__file__).parent.parent.parent / "data" / "audits" / "comments_analysis.json"
    if not analysis_file.exists():
        return ""
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""

    analyse = data.get("analyse", {})
    lignes = ["\nBESOINS DES SPECTATEURS (depuis les commentaires de tes videos):"]
    besoins = analyse.get("besoins", [])[:5]
    if besoins:
        lignes.append("- " + ", ".join(f"{b['theme']} ({b['nb']})" for b in besoins))
    else:
        lignes.append("- (peu de besoins detectes)")

    prieres = analyse.get("prieres", [])[:2]
    for p in prieres:
        if p.get("texte"):
            lignes.append(f"- Prieres ecrites par '{p.get('auteur','?')}': {p['texte'][:140]}")

    synthese = data.get("synthese", {})
    if synthese and synthese.get("texte"):
        lignes.append(f"- Synthese IA: {synthese['texte'][:220]}")

    return "\n".join(lignes)


def analyser_performances_profil(profil_id="prayer"):
    """
    Analyse les performances des contenus produits pour un profil.
    Croise les stats YouTube (si configure) avec les projets.
    """
    config = _lire_config()
    results = {
        "total_projets": 0,
        "termines": 0,
        "en_cours": 0,
        "duree_moyenne": 0,
        "youtube_disponible": False,
        "suggestions": []
    }

    # Stats des projets
    projects_path = paths.PROJECTS_DIR
    durees = []
    if projects_path.exists():
        for p in projects_path.iterdir():
            pjson = p / "project.json"
            if pjson.exists():
                try:
                    with open(pjson, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results["total_projets"] += 1
                    etapes = data.get("etapes", {})
                    if etapes.get("video") == "termine":
                        results["termines"] += 1
                    else:
                        results["en_cours"] += 1
                    duree = data.get("meta", {}).get("duree_cible", 0)
                    if duree:
                        durees.append(duree)
                except:
                    pass

    if durees:
        results["duree_moyenne"] = sum(durees) / len(durees)

    # Verifier YouTube
    if config.get("youtube_api_key"):
        results["youtube_disponible"] = True

    # Generer des suggestions
    if results["en_cours"] > results["termines"]:
        results["suggestions"].append(
            f"{results['en_cours']} projets en cours — termine les d'abord"
        )
    else:
        results["suggestions"].append(
            "Tu peux lancer la production automatique d'un nouveau contenu"
        )

    return results
