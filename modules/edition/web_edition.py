# -*- coding: utf-8 -*-
"""
web_edition.py — Edition video / shorts depuis l'interface web

Porte vers le web les fonctions d'edition du GUI PowerShell :
- Generateur de Shorts (non interactif, pilote par les parametres du formulaire)
- Vignettes (thumbnails) standalone
- Clonage de voix (re-expose voice_cloner)
- Liste des projets shorts

Chaque generation ecrit sa progression dans modules/automation/progress.py,
affichee dans la barre de progression de la page /edition et /automation.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(_rac))
    from core import paths


def _lire_config():
    # Config EFFECTIVE (utilisateur en installé, embarquée + locale en source) :
    # les chemins projets/musique/assets sont résolus par paths.py, plus jamais
    # depuis des chemins absolus stockés dans la config.
    return paths.lire_config()


def log(msg):
    print(f"[WEB-EDITION] {msg}")


def _slug(txt, longueur=25):
    return re.sub(r"[^a-z0-9_]", "_", txt.lower())[:longueur].strip("_") or "sans_nom"


# ---------------------------------------------------------------
# SHORTS
# ---------------------------------------------------------------

def generer_shorts_via_web(sujet, type_contenu="priere", langue="fr",
                           duree_sec=60, nb_shorts=5, voix_choix="3"):
    """
    Genere des Shorts de bout en bout (plan -> script -> audio -> video -> vignette)
    de facon non interactive, avec progression.

    Returns:
        dict: {"ok": bool, "projet": str, "chemin": str, "nb_ok": int, "nb_total": int,
               "videos": [str], "erreur": str}
    """
    from modules.automation.progress import init as progress_init
    from modules.automation.progress import etape as progress_etape
    from modules.automation.progress import terminer_etape as progress_terminer
    from modules.automation.progress import fin as progress_fin

    from modules.shorts.generate_shorts import (
        generer_plan_shorts, generer_script_short, nettoyer_intro_ia,
        generer_audio_short, generer_srt_for_short, generer_thumbnail_short,
        creer_video_short, choisir_image, generer_musique_fond_projet,
    )

    config = _lire_config()
    progress_init()

    resultat = {
        "ok": False, "projet": "", "chemin": "", "nb_ok": 0, "nb_total": nb_shorts,
        "videos": [], "erreur": None
    }

    try:
        # Dossier projet Shorts (résolu via core/paths)
        projects_path = paths.PROJECTS_DIR
        projects_path.mkdir(parents=True, exist_ok=True)
        shorts_id = f"shorts_{_slug(sujet)}_{int(time.time())}"
        shorts_path = projects_path / shorts_id
        (shorts_path / "scripts").mkdir(parents=True, exist_ok=True)
        (shorts_path / "audio").mkdir(exist_ok=True)
        (shorts_path / "export" / "shorts").mkdir(parents=True, exist_ok=True)
        (shorts_path / "thumbnails").mkdir(exist_ok=True)
        resultat["projet"] = shorts_id
        resultat["chemin"] = str(shorts_path)

        # 1. Plan (titres)
        progress_etape("shorts", "Generation des titres (plan)...", 5, f"Sujet: {sujet[:50]}")
        titres = generer_plan_shorts(sujet, nb_shorts, type_contenu, langue)
        if not titres:
            raise RuntimeError("Aucun titre genere par l'IA (Ollama indisponible ?)")
        plan = {
            "id": shorts_id, "sujet": sujet, "langue": langue,
            "type_contenu": type_contenu, "duree_sec": duree_sec,
            "nb_shorts": nb_shorts, "titres": titres, "statut": "en_cours"
        }
        (shorts_path / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        progress_terminer("shorts", "termine", f"{len(titres)} titres generes")

        # 2. Musique de fond (ComposIA ou fallback)
        progress_etape("shorts", "Generation musique de fond...", 8)
        musique = generer_musique_fond_projet(shorts_path, sujet, type_contenu, config)
        if musique:
            log(f"  Musique de fond prete: {Path(musique).name}")
        progress_terminer("shorts", "termine", "Musique de fond prete")

        # 3. Boucle sur chaque short
        succes = 0
        for i, titre in enumerate(titres, 1):
            pct = 10 + int(85 * i / len(titres))
            progress_etape("shorts", f"Short {i}/{len(titres)} : {titre[:45]}", pct,
                           "script -> audio -> video -> vignette")

            nom_safe = _slug(titre, 30)
            script_path = shorts_path / "scripts" / f"short_{i:02d}.txt"
            audio_path = shorts_path / "audio" / f"short_{i:02d}.wav"
            video_path = shorts_path / "export" / "shorts" / f"short_{i:02d}_{nom_safe}.mp4"
            thumb_path = shorts_path / "thumbnails" / f"short_{i:02d}.png"

            # Script
            script = generer_script_short(titre, sujet, type_contenu, langue, duree_sec)
            script = nettoyer_intro_ia(script)
            script_path.write_text(script, encoding="utf-8")
            log(f"  Short {i}: script {len(script.split())} mots")

            # Audio (TTS via le venv du pack XTTS résolu par core/paths)
            try:
                ok_audio = generer_audio_short(script, str(audio_path), langue, voix_choix)
            except Exception as e:
                log(f"  Short {i}: echec audio: {e}")
                ok_audio = False
            if not ok_audio or not audio_path.exists():
                log(f"  Short {i}: ECHEC audio — on saute")
                continue

            # SRT sous-titres
            try:
                generer_srt_for_short(str(audio_path), script, str(audio_path).replace(".wav", ".srt"))
            except Exception as e:
                log(f"  Short {i}: srt ignore: {e}")

            # Image de fond
            image = choisir_image(str(paths.ASSETS_DIR), sujet, langue)
            if not image:
                log(f"  Short {i}: aucune image disponible — on saute")
                continue

            # Video
            try:
                ok_video = creer_video_short(
                    str(audio_path), image, str(video_path), titre, config,
                    shorts_path=str(shorts_path), langue=langue, duree_sec=duree_sec
                )
            except Exception as e:
                log(f"  Short {i}: echec video: {e}")
                ok_video = False
            if not ok_video or not video_path.exists():
                log(f"  Short {i}: ECHEC video")
                continue

            # Vignette
            try:
                generer_thumbnail_short(titre, str(thumb_path))
            except Exception as e:
                log(f"  Short {i}: vignette ignoree: {e}")

            resultat["videos"].append(str(video_path))
            succes += 1
            log(f"  Short {i} OK : {video_path.name}")

        plan["statut"] = "termine"
        (shorts_path / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

        resultat["nb_ok"] = succes
        resultat["ok"] = succes > 0
        if succes == 0:
            resultat["erreur"] = "Aucun short genere (verifie Ollama, le venv TTS et assets/images)"
        progress_fin(erreur=resultat.get("erreur"), resultat=resultat)
        return resultat

    except Exception as e:
        resultat["erreur"] = str(e)
        progress_fin(erreur=str(e), resultat=resultat)
        return resultat


def generer_video_longue_via_web(sujet, type_contenu="priere", langue="fr",
                                 duree_minutes=30, voix_choix="3",
                                 directives=None, titre=None, description=None,
                                 tags=None):
    """
    Genere une VIDEO LONGUE de bout en bout (plan -> script -> audio -> images
    -> video -> vignette) de facon non interactive, avec progression.

    Cree un projet dans projects/, ecrit project.json (sujet, duree, directives,
    voix), puis enchaine : generate_script -> filter_text -> phase_video (pipeline).

    Returns:
        dict: {"ok": bool, "projet": str, "chemin": str, "fichier_video": str,
               "fichier_thumbnail": str, "erreur": str}
    """
    from modules.automation.progress import init as progress_init
    from modules.automation.progress import etape as progress_etape
    from modules.automation.progress import terminer_etape as progress_terminer
    from modules.automation.progress import fin as progress_fin

    config = _lire_config()
    progress_init()

    resultat = {
        "ok": False, "projet": "", "chemin": "", "fichier_video": "",
        "fichier_thumbnail": "", "erreur": None
    }

    try:
        duree = max(1, int(duree_minutes or 30))
        # Dossier projet
        projects_path = paths.PROJECTS_DIR
        projects_path.mkdir(parents=True, exist_ok=True)
        prefix = titre or sujet
        projet_id = f"long_{_slug(prefix, 40)}_{int(time.time())}"
        projet_path = projects_path / projet_id
        projet_path.mkdir(parents=True, exist_ok=True)
        (projet_path / "chapters").mkdir(exist_ok=True)
        (projet_path / "audio").mkdir(exist_ok=True)
        (projet_path / "images").mkdir(exist_ok=True)
        (projet_path / "export").mkdir(exist_ok=True)
        resultat["projet"] = projet_id
        resultat["chemin"] = str(projet_path)

        type_map = {
            "1": "priere", "2": "storytelling", "3": "storytelling", "4": "general",
            "priere": "priere", "storytelling": "storytelling", "general": "general"
        }
        type_contenu = type_map.get(str(type_contenu), "priere")

        # project.json avec directives + duree + voix
        project_data = {
            "id": projet_id,
            "sujet": sujet,
            "type_contenu": type_contenu,
            "langue": langue,
            "duree_cible_minutes": duree,
            "directives": directives or None,
            "meta": {
                "profil": "prayer",
                "genere_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "automatique": False,
                "duree_cible": duree,
                "mots_cles": tags or [],
                "touche_humaine": bool((config.get("human_touch") or {}).get("actif", False))
            },
            "etapes": {
                "script": "en_attente", "chapitres": "en_attente",
                "audio": "en_attente", "musique_fond": "en_attente",
                "images": "en_attente", "video": "en_attente",
                "thumbnail": "en_attente", "upload": "en_attente"
            }
        }
        (projet_path / "project.json").write_text(
            json.dumps(project_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 1. Script (generate_script.main lit project.json)
        progress_etape("script", "Generation du script (plan + chapitres)...", 8)
        from modules.brain.generate_script import main as generate_main
        _sys_argv = sys.argv
        sys.argv = ["generate_script.py", str(projet_path)]
        try:
            generate_main()
        finally:
            sys.argv = _sys_argv
        progress_terminer("script", "termine", "Script genere")

        # 2. Filtre (interdits directives + nettoyage)
        progress_etape("chapitres", "Filtrage du texte...", 18)
        from modules.brain.filter_text import main as filter_main
        sys.argv = ["filter_text.py", str(projet_path)]
        try:
            filter_main()
        finally:
            sys.argv = _sys_argv
        progress_terminer("chapitres", "termine", "Texte filtre")

        # 3. Phase video (audio + musique + images + montage + vignette)
        #    On force la voix choisie dans la config pour cette generation.
        from modules.automation.pipeline import PipelineAutomation
        pipeline = PipelineAutomation()
        pipeline.config["tts_voix"] = str(voix_choix)
        pipeline.resultat["projet_creer"] = projet_id
        pipeline.phase_video(projet_id)

        resultat["fichier_video"] = pipeline.resultat.get("fichier_video", "")
        resultat["fichier_thumbnail"] = pipeline.resultat.get("fichier_thumbnail", "")
        resultat["ok"] = bool(resultat["fichier_video"])
        if not resultat["ok"]:
            resultat["erreur"] = "Video non produite (voir phase_video)."

        progress_fin(erreur=resultat.get("erreur"), resultat=resultat)
        return resultat

    except Exception as e:
        resultat["erreur"] = str(e)
        progress_fin(erreur=str(e), resultat=resultat)
        return resultat


def lister_projets_longues():
    """Liste les projets de videos longues generes depuis /edition."""
    config = _lire_config()
    projects_path = paths.PROJECTS_DIR
    if not projects_path.exists():
        return []

    projets = []
    for p in sorted(projects_path.glob("long_*"), reverse=True):
        if not p.is_dir():
            continue
        pj = p / "project.json"
        data = {}
        if pj.exists():
            try:
                data = json.loads(pj.read_text(encoding="utf-8"))
            except Exception:
                pass
        videos = sorted((p / "export" / "video").glob("*.mp4")) if (p / "export" / "video").exists() else []
        thumbs = sorted((p / "thumbnail").glob("*.png")) if (p / "thumbnail").exists() else []
        etapes = data.get("etapes", {})
        projets.append({
            "nom": p.name,
            "sujet": data.get("sujet", ""),
            "langue": data.get("langue", "fr"),
            "type": data.get("type_contenu", ""),
            "duree_minutes": data.get("duree_cible_minutes", ""),
            "statut": etapes.get("video", "?"),
            "video": str(videos[-1]) if videos else "",
            "thumbnail": str(thumbs[-1]) if thumbs else ""
        })
    return projets


def lister_projets_shorts():
    """Liste les projets shorts existants + videos generees."""
    config = _lire_config()
    projects_path = paths.PROJECTS_DIR
    if not projects_path.exists():
        return []

    projets = []
    for p in sorted(projects_path.glob("shorts_*"), reverse=True):
        if not p.is_dir():
            continue
        plan = {}
        pj = p / "plan.json"
        if pj.exists():
            try:
                plan = json.loads(pj.read_text(encoding="utf-8"))
            except Exception:
                pass
        videos = [str(v) for v in sorted((p / "export" / "shorts").glob("*.mp4"))] if (p / "export" / "shorts").exists() else []
        projets.append({
            "nom": p.name,
            "sujet": plan.get("sujet", ""),
            "langue": plan.get("langue", "fr"),
            "type": plan.get("type_contenu", ""),
            "nb_shorts": plan.get("nb_shorts", 0),
            "nb_videos": len(videos),
            "statut": plan.get("statut", "?"),
            "videos": videos[:10]
        })
    return projets


# ---------------------------------------------------------------
# VIGNETTES (thumbnails) standalone
# ---------------------------------------------------------------

def generer_thumbnail_via_web(titre, output_path=None, projet_nom=""):
    """
    Genere une vignette standalone a partir d'un titre (PIL, sans Ollama).

    Returns:
        dict: {"ok": bool, "chemin": str, "message": str}
    """
    try:
        from modules.shorts.generate_shorts import generer_thumbnail_short
        if not output_path:
            config = _lire_config()
            projects_path = paths.PROJECTS_DIR
            d = projects_path / "thumbnails_web"
            d.mkdir(parents=True, exist_ok=True)
            output_path = str(d / f"thumb_{_slug(titre, 30)}.png")
        generer_thumbnail_short(titre, output_path)
        if Path(output_path).exists():
            return {"ok": True, "chemin": output_path, "message": "Vignette generee"}
        return {"ok": False, "message": "Echec generation vignette"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ---------------------------------------------------------------
# CLONAGE DE VOIX
# ---------------------------------------------------------------

def cloner_voix_via_web(nom, chemin_audio, description=""):
    """Clone une voix depuis un fichier audio (PyTorch requis)."""
    try:
        from modules.tts.voice_cloner import cloner_voix
        voix = cloner_voix(nom, chemin_audio, description)
        if voix:
            return {"ok": True, "voix": voix, "message": f"Voix '{nom}' clonee"}
        return {"ok": False, "message": "Clonage impossible (PyTorch indisponible ?). Verifie les logs."}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def lister_voix_clonees_via_web():
    try:
        from modules.tts.voice_cloner import lister_voix_clonees
        return lister_voix_clonees()
    except Exception as e:
        return []
