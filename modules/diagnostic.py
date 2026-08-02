# -*- coding: utf-8 -*-
"""
diagnostic.py — Diagnostic automatique au lancement

Analyse l'état du système au démarrage :
- Vérifie la configuration
- Teste les connexions (Ollama, API YouTube, Pexels)
- Analyse les performances YouTube si configuré
- Calcule les statistiques des projets récents
- Suggère des actions
"""

import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.profiles.profile_manager import get_manager as get_profile_manager

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Diagnostics utilisateur : %USERPROFILE%\StudioIA\data\diagnostics (isolé du
# dossier d'app, préservé pendant les MAJ). Résolu par paths.py.
DATA_DIR = paths.chemin_data("data", "diagnostics")


def log(msg):
    print(f"[DIAG] {msg}")


def _lire_config():
    # Config EFFECTIVE (utilisateur en installé, embarquée + locale en source).
    return paths.lire_config()


def _sauvegarder_diagnostic(resultat):
    """Sauvegarde le résultat du diagnostic"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    # Garder aussi un "dernier" pour accès rapide
    derniere_path = DATA_DIR / "dernier_diagnostic.json"
    with open(derniere_path, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    return str(path)


def _tester_ollama():
    """Teste la connexion à Ollama"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            modeles = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "modeles": modeles}
        return {"ok": False, "erreur": f"HTTP {r.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "erreur": "Ollama ne répond pas"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _tester_pexels(api_key):
    """Teste la connexion à Pexels"""
    if not api_key:
        return {"ok": False, "erreur": "Pas de clé API"}

    try:
        r = requests.get("https://api.pexels.com/v1/search", params={
            "query": "nature",
            "per_page": 1
        }, headers={"Authorization": api_key}, timeout=10)
        return {"ok": r.status_code == 200, "erreur": None if r.status_code == 200 else f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _tester_youtube():
    """Teste la connexion à l'API YouTube"""
    try:
        from modules.youtube_analyzer.youtube_stats import tester_connexion
        ok, msg = tester_connexion()
        return {"ok": ok, "erreur": None if ok else msg}
    except Exception as e:
        return {"ok": False, "erreur": f"Module non disponible: {e}"}


def _analyser_projets_recents(jours=7):
    """Analyse les projets créés récemment"""
    projects_path = paths.PROJECTS_DIR
    if not projects_path.exists():
        return {"total": 0, "termines": 0}

    depuis = datetime.now() - timedelta(days=jours)
    projets = []

    for p in projects_path.iterdir():
        pjson = p / "project.json"
        if not pjson.exists():
            continue

        try:
            with open(pjson, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            continue

        # Vérifier la date
        meta = data.get("meta", {})
        duree = meta.get("duree_cible", 0)
        etapes = data.get("etapes", {})
        termine = etapes.get("video") == "termine"
        type_c = data.get("type_contenu", "?")
        sujet = data.get("sujet", "?")[:40]

        projets.append({
            "nom": p.name,
            "sujet": sujet,
            "type": type_c,
            "termine": termine,
            "duree": duree
        })

    termines = sum(1 for p in projets if p["termine"])
    return {
        "total": len(projets),
        "termines": termines,
        "en_cours": len(projets) - termines,
        "projets": projets[:10]
    }


def executer_diagnostic(silent=False):
    """
    Exécute le diagnostic complet du système.

    Returns:
        dict: résultat complet du diagnostic
    """
    config = _lire_config()
    profil_id = config.get("profil_actif", "prayer")

    if not silent:
        log("=== DIAGNOSTIC SYSTEME ===")

    etapes = {}

    # 1. Configuration
    etapes["config"] = {
        "profil_actif": profil_id,
        "mode_visuel": config.get("mode_visuel", "intelligent"),
        "mode": config.get("mode", "local"),
        "low_resource": config.get("low_resource", True),
        "providers": config.get("providers", {"plan": "local", "chapitre": "local"})
    }

    # 2. Profil
    try:
        pm = get_profile_manager()
        p = pm.charger_profil_actif()
        if p:
            etapes["profil"] = {
                "ok": True,
                "nom": p.get("manifest", {}).get("name", "?"),
                "regles": len(p.get("toutes_regles", []))
            }
        else:
            etapes["profil"] = {"ok": False, "erreur": "Profil introuvable"}
    except Exception as e:
        etapes["profil"] = {"ok": False, "erreur": str(e)}

    # 3. Ollama
    etapes["ollama"] = _tester_ollama()

    # 4. Pexels
    etapes["pexels"] = _tester_pexels(config.get("pexels_api_key", ""))

    # 5. YouTube API
    etapes["youtube"] = _tester_youtube()

    # 6. Projets récents
    etapes["projets"] = _analyser_projets_recents(7)

    # 7. Corrections en attente
    try:
        from modules.learning.correction_memory import statistiques
        stats = statistiques(profil_id)
        etapes["apprentissage"] = {
            "corrections": stats["total_corrections"],
            "en_attente_analyse": stats["en_attente"],
            "propositions_validees": stats["validees"]
        }
    except Exception as e:
        etapes["apprentissage"] = {"erreur": str(e)}

    # Score global
    score = 0
    max_score = 0

    if etapes.get("ollama", {}).get("ok"):
        score += 25
    max_score += 25

    if etapes.get("pexels", {}).get("ok"):
        score += 15
    max_score += 15

    if etapes.get("profil", {}).get("ok"):
        score += 20
    max_score += 20

    if etapes.get("config"):
        score += 10
    max_score += 10

    if etapes.get("youtube", {}).get("ok"):
        score += 10
    max_score += 10

    if etapes.get("apprentissage", {}).get("corrections", 0) > 0:
        score += 10
    max_score += 10

    # Suggestions
    suggestions = []
    if not etapes.get("ollama", {}).get("ok"):
        suggestions.append("Ollama ne répond pas — lance Ollama pour générer du contenu")
    if not etapes.get("pexels", {}).get("ok"):
        suggestions.append("Ajoute ta clé Pexels API dans config.json pour les images/vidéos")
    if not etapes.get("youtube", {}).get("ok"):
        suggestions.append("Configure youtube_api_key dans config.json pour l'analyse de chaîne")
    if etapes.get("apprentissage", {}).get("en_attente_analyse", 0) > 3:
        suggestions.append(f"{etapes['apprentissage']['en_attente_analyse']} corrections en attente — lance l'analyse")
    if etapes.get("projets", {}).get("en_cours", 0) > 2:
        suggestions.append(f"{etapes['projets']['en_cours']} projets en cours — termine-les")

    resultat = {
        "timestamp": datetime.now().isoformat(),
        "score": score,
        "score_max": max_score,
        "score_pct": round(score / max_score * 100) if max_score > 0 else 0,
        "etapes": etapes,
        "suggestions": suggestions
    }

    chemin = _sauvegarder_diagnostic(resultat)

    if not silent:
        log(f"Score: {resultat['score_pct']}% ({score}/{max_score})")
        log(f"Ollama: {'OK' if etapes.get('ollama',{}).get('ok') else 'HORS LIGNE'}")
        log(f"Pexels: {'OK' if etapes.get('pexels',{}).get('ok') else 'NON CONFIGURE'}")
        log(f"YouTube: {'OK' if etapes.get('youtube',{}).get('ok') else 'NON CONFIGURE'}")
        log(f"Profil: {etapes.get('profil',{}).get('nom','?')}")
        log(f"Projets récents: {etapes.get('projets',{}).get('total',0)} ({etapes.get('projets',{}).get('termines',0)} terminés)")
        if suggestions:
            log("Suggestions:")
            for s in suggestions:
                log(f"  >> {s}")
        log(f"Diagnostic sauvegardé: {chemin}")

    return resultat


def charger_dernier_diagnostic():
    """Charge le dernier diagnostic sauvegardé"""
    path = DATA_DIR / "dernier_diagnostic.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None


if __name__ == "__main__":
    executer_diagnostic()
