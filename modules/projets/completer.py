# -*- coding: utf-8 -*-
"""
completer.py — Analyser & terminer les projets incomplets.

Ce module repond au besoin : « analyser les projets, terminer ceux qui ont des
scripts ou d'autres details incomplets, et supprimer ceux qui ne peuvent pas
etre finis ».

Deux actions :
  1. ANALYSER  — pour chaque projet, determiner le type (video longue / Shorts),
     les etapes manquantes et le verdict (a completer / a supprimer / deja terminé).
  2. TERMINER  — executer les etapes manquantes (script, audio, images, montage,
     vignette...) en reutilisant les MEMES modules que le pipeline, PUIS supprimer
     (si demande) les projets toujours incomplets et deja anciens.

La SUPPRESSION proprement dite reste dans modules/projets/cleanup.py
(reutilise ici, non modifie). Aucun fichier du pipeline n'est modifie.

Usage CLI :
    python -m modules.projets.completer --apercu                     # analyse seule
    python -m modules.projets.completer --completer                  # termine les recuperables
    python -m modules.projets.completer --completer --supprimer-echecs
"""

import json
import os
import re
import sys
import shutil
import argparse
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Encodage robuste de la sortie (les logs des etapes peuvent contenir des
# caracteres non-cp1252 : evite les UnicodeEncodeError selon la console).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Etapes auto-completables d'une video longue, dans l'ordre du pipeline.
# Exclues volontairement : upload (OAuth) et intro (voix humaine).
ORDRE_ETAPES_LONGUE = ["script", "chapitres", "audio", "musique_fond",
                       "images", "video", "thumbnail"]


def log(msg):
    print(f"[COMPLETER] {msg}")


def _lire_config():
    """Config via core/paths (utilisateur prime en mode installe)."""
    try:
        return paths.lire_config()
    except Exception:
        try:
            cfg = paths.config_path()
            if cfg.exists():
                return json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}


def _lire_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# ANALYSE
# ---------------------------------------------------------------------------

def _etapes_manquantes_longue(data):
    """Etapes manquantes (non 'termine') d'une video longue, dans l'ordre.

    Gere l'ancien schema (projets du 31/07) : les cles plan/recherche/redaction
    en 'en_attente' sont ignorees si script/chapitres sont deja 'termine' (le
    script existe donc deja, pas de regeneration IA inutile).
    """
    etapes = data.get("etapes", {}) or {}
    legacy_script_fait = (etapes.get("script") == "termine"
                          and etapes.get("chapitres") == "termine")
    manquantes = []
    for e in ORDRE_ETAPES_LONGUE:
        if etapes.get(e) == "termine":
            continue
        if e in ("script", "chapitres") and legacy_script_fait:
            continue
        manquantes.append(e)
    return manquantes


def analyser_projet(dossier, seuil_jours=7):
    """Analyse un dossier projet : type, etapes manquantes, verdict."""
    from modules.projets import cleanup

    dossier = Path(dossier)
    nom = dossier.name
    pjson = dossier / "project.json"
    planjson = dossier / "plan.json"

    # Stats communes (statut, taille, dernier modif) via cleanup (non modifie).
    base = cleanup.analyser_projet(dossier, seuil_jours)
    rapport = {
        "chemin": str(dossier),
        "nom": nom,
        "type": "?",
        "statut": base.get("statut", ""),
        "taille_mo": base.get("taille_mo", 0.0),
        "dernier_modif": base.get("dernier_modif", ""),
        "etapes": {},
        "etapes_manquantes": [],
        "nb_ok": 0,
        "nb_total": 0,
        "completable": False,
        "raison": "pas_un_projet",
    }

    if planjson.exists():
        # ---- SHORTS ----
        # NB : le champ plan.json["statut"] est marque "termine" meme en echec
        # (bug preexistant de web_edition.generer_shorts_via_web) -> on decide
        # uniquement sur le NOMBRE DE VIDEOS produites, pas sur le champ statut.
        plan = _lire_json(planjson)
        titres = plan.get("titres", []) or []
        export = dossier / "export" / "shorts"
        videos = sorted(export.glob("short_*.mp4")) if export.exists() else []
        nb_videos = len(videos)
        rapport["type"] = "shorts"
        rapport["etapes"] = {"shorts_ok": nb_videos, "total": len(titres)}
        rapport["nb_ok"] = nb_videos
        rapport["nb_total"] = len(titres)
        manquantes = [f"short_{i:02d}" for i in range(1, len(titres) + 1)
                      if not list(export.glob(f"short_{i:02d}_*.mp4"))] if export.exists() \
                      else [f"short_{i:02d}" for i in range(1, len(titres) + 1)]
        rapport["etapes_manquantes"] = manquantes

        if titres and nb_videos >= len(titres):
            rapport["completable"] = False
            rapport["raison"] = "statut_termine"  # tous les shorts sont produits
        elif titres:
            rapport["completable"] = True
            rapport["raison"] = "a_completer"
        else:
            rapport["completable"] = False
            rapport["raison"] = "incomplet_irrecuperable"  # plan sans titres
        return rapport

    if pjson.exists():
        # ---- VIDEO LONGUE ----
        data = _lire_json(pjson)
        etapes = data.get("etapes", {}) or {}
        manquantes = _etapes_manquantes_longue(data)
        rapport["type"] = "longue"
        rapport["etapes"] = etapes
        rapport["etapes_manquantes"] = manquantes

        statut = rapport["statut"]
        if statut in cleanup.STATUTS_TERMINES:
            rapport["raison"] = "statut_termine"
        elif etapes.get("video") == "termine" or cleanup._a_video_finale(dossier):
            # Deja produit : on ne re-rend PAS la video (couteux + risque).
            rapport["raison"] = "video_presente"
        elif not manquantes:
            rapport["raison"] = "statut_termine"
        else:
            rapport["completable"] = True
            rapport["raison"] = "a_completer"
        return rapport

    # Ni plan.json ni project.json -> pas un projet (cleanup l'ignore aussi).
    return rapport


def analyser_tous_projets(seuil_jours=7):
    """Rapport complet (dry-run) sur tous les projets du dossier projets."""
    projects_dir = paths.PROJECTS_DIR
    if not projects_dir.exists() or not projects_dir.is_dir():
        return {"succes": False, "erreur": f"dossier projets introuvable : {projects_dir}",
                "projets": []}

    rapports = []
    for d in sorted(projects_dir.iterdir()):
        if not d.is_dir():
            continue
        if not str(d.resolve()).startswith(str(projects_dir.resolve())):
            continue
        rapports.append(analyser_projet(d, seuil_jours))

    a_completer = [r for r in rapports if r.get("completable")]
    a_supprimer = [r for r in rapports if r.get("raison") == "incomplet_irrecuperable"]
    termines = [r for r in rapports if not r.get("completable")
                and r.get("raison") in ("statut_termine", "video_presente")]

    return {
        "succes": True,
        "mode": "apercu",
        "seuil_jours": seuil_jours,
        "projets": rapports,
        "total": len(rapports),
        "a_completer": [r["nom"] for r in a_completer],
        "a_supprimer": [r["nom"] for r in a_supprimer],
        "termines": [r["nom"] for r in termines],
        "espace_recuperable_mo": round(sum(r.get("taille_mo", 0) for r in rapports
                                          if r.get("raison") == "incomplet_irrecuperable"), 1),
    }


# ---------------------------------------------------------------------------
# COMPLETION
# ---------------------------------------------------------------------------

def _sauver_argv(fonction_main, args):
    """Appelle fonction_main() avec sys.argv pointe sur args (motif du pipeline)."""
    import sys as _sys
    old_argv = _sys.argv
    _sys.argv = ["completer.py"] + list(args)
    try:
        fonction_main()
    finally:
        _sys.argv = old_argv


def _marquer_etape(pjson, etape):
    """Marque une etape 'termine' dans project.json (idempotent)."""
    try:
        data = json.loads(pjson.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data.setdefault("etapes", {})[etape] = "termine"
    pjson.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _completer_longue(dossier, config):
    """Complete les etapes manquantes d'une video longue (meme sequence que
    pipeline.phase_video + generate_script). Tolerant : log + continue."""
    from modules.projets import cleanup

    dossier = Path(dossier)
    pjson = dossier / "project.json"
    data = _lire_json(pjson)
    manquantes = _etapes_manquantes_longue(data)
    if not manquantes:
        return {"ok": True, "fait": False, "deja_termine": True,
                "etapes_terminees": [], "erreurs": []}

    voix = str(config.get("tts_voix", "3"))
    terminees = []
    erreurs = []

    # 1. Script + chapitres
    if "script" in manquantes or "chapitres" in manquantes:
        try:
            log(f"  [{dossier.name}] Generation du script (Ollama, ~1-2 min)...")
            from modules.brain.generate_script import main as gen_main
            _sauver_argv(gen_main, [str(dossier)])
            from modules.brain.filter_text import main as filt_main
            _sauver_argv(filt_main, [str(dossier)])
            if (dossier / "script.txt").exists() or list((dossier / "chapters").glob("*.txt")):
                _marquer_etape(pjson, "script")
                _marquer_etape(pjson, "chapitres")
                terminees += ["script", "chapitres"]
            else:
                erreurs.append("script: aucun script.txt/chapitre genere")
        except Exception as e:
            erreurs.append(f"script: {e}")

    # 2. Audio TTS
    if "audio" in manquantes:
        try:
            log(f"  [{dossier.name}] Audio TTS...")
            from modules.tts.run_tts import main as tts_main
            _sauver_argv(tts_main, [str(dossier), voix])
            if list((dossier / "audio").glob("*.wav")):
                _marquer_etape(pjson, "audio")
                terminees.append("audio")
            else:
                erreurs.append("audio: aucun wav genere")
        except Exception as e:
            erreurs.append(f"audio: {e}")

    # 3. Musique de fond (fallback deterministe du pipeline : copie MUSIC_DIR)
    if "musique_fond" in manquantes:
        try:
            music_dir = paths.MUSIC_DIR
            candidat = None
            if music_dir.exists():
                candidats = sorted(list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav")))
                if candidats:
                    candidat = candidats[0]
            if candidat:
                audio_dir = dossier / "audio"
                audio_dir.mkdir(exist_ok=True)
                shutil.copy(str(candidat), str(audio_dir / "musique_fond.mp3"))
                _marquer_etape(pjson, "musique_fond")
                terminees.append("musique_fond")
            else:
                erreurs.append("musique_fond: aucun mp3/wav dans MUSIC_DIR")
        except Exception as e:
            erreurs.append(f"musique_fond: {e}")

    # 4. Images (library_manager puis fallback assets/backgrounds)
    if "images" in manquantes:
        try:
            log(f"  [{dossier.name}] Images...")
            from modules.images.library_manager import main as img_main
            _sauver_argv(img_main, [str(dossier)])
            data = _lire_json(pjson)
            if data.get("images_data", {}).get("backgrounds"):
                _marquer_etape(pjson, "images")
                terminees.append("images")
            else:
                # fallback : fonds par defaut depuis assets/backgrounds
                bg_src = Path(paths.ASSETS_DIR) / "backgrounds"
                bg_dest = dossier / "images" / "backgrounds"
                bg_dest.mkdir(parents=True, exist_ok=True)
                fonds = sorted(list(bg_src.glob("*.jpg")) + list(bg_src.glob("*.png")))[:5]
                bgs = []
                for i, f in enumerate(fonds, 1):
                    nom = f"bg_fallback_{i:02d}.jpg"
                    shutil.copy(str(f), str(bg_dest / nom))
                    bgs.append({"fichier": f"images/backgrounds/{nom}",
                                "mot_cle": "fallback", "nom": nom})
                if bgs:
                    data["images_data"] = {"backgrounds": bgs, "overlays": []}
                    pjson.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
                    _marquer_etape(pjson, "images")
                    terminees.append("images")
                else:
                    erreurs.append("images: aucun fond disponible")
        except Exception as e:
            erreurs.append(f"images: {e}")

    # 5. Montage video (lent ~7 min)
    if "video" in manquantes:
        try:
            log(f"  [{dossier.name}] Montage video (lent)...")
            from modules.video.build_video import main as bv_main
            _sauver_argv(bv_main, [str(dossier), "7", "5", "8", ""])
            data = _lire_json(pjson)
            fichier_final = data.get("fichier_final", "")
            video_ok = bool(fichier_final and (dossier / fichier_final).exists())
            if not video_ok:
                candidats = sorted((dossier / "export" / "video").glob("*.mp4")) \
                    if (dossier / "export" / "video").exists() else []
                video_ok = bool(candidats)
            if video_ok:
                _marquer_etape(pjson, "video")
                terminees.append("video")
            else:
                erreurs.append("video: aucune video finale produite")
        except Exception as e:
            erreurs.append(f"video: {e}")

    # 6. Vignette
    if "thumbnail" in manquantes:
        try:
            log(f"  [{dossier.name}] Vignette...")
            from modules.thumbnail.thumbnail_builder import main as th_main
            _sauver_argv(th_main, [str(dossier), "6"])
            if list((dossier / "thumbnail").glob("*.png")):
                _marquer_etape(pjson, "thumbnail")
                terminees.append("thumbnail")
            else:
                erreurs.append("thumbnail: aucun png genere")
        except Exception as e:
            erreurs.append(f"thumbnail: {e}")

    ok = not erreurs
    return {"ok": ok, "fait": ok, "deja_termine": False,
            "etapes_terminees": terminees, "erreurs": erreurs}


def _completer_shorts(dossier, config):
    """Complete les Shorts manquants d'un projet shorts, EN PLACE (meme boucle
    que generer_shorts_via_web) : musique -> par short script/audio/srt/image/
    video/vignette. Les shorts deja produits (mp4) sont sautes."""
    dossier = Path(dossier)
    planjson = dossier / "plan.json"
    plan = _lire_json(planjson)
    titres = plan.get("titres", []) or []
    if not titres:
        return {"ok": False, "fait": False, "deja_termine": False,
                "etapes_terminees": [], "erreurs": ["plan sans titres — irrecuperable"]}

    sujet = plan.get("sujet", "")
    langue = plan.get("langue", "fr")
    type_contenu = plan.get("type_contenu", "priere")
    duree_sec = int(plan.get("duree_sec", 60) or 60)
    voix = str(plan.get("voix_choix") or config.get("tts_voix", "3"))

    from modules.shorts.generate_shorts import (
        generer_script_short, nettoyer_intro_ia, generer_audio_short,
        generer_srt_for_short, choisir_image, creer_video_short,
        generer_thumbnail_short, generer_musique_fond_projet,
    )

    (dossier / "scripts").mkdir(exist_ok=True)
    (dossier / "audio").mkdir(exist_ok=True)
    (dossier / "export" / "shorts").mkdir(parents=True, exist_ok=True)
    (dossier / "thumbnails").mkdir(exist_ok=True)
    export = dossier / "export" / "shorts"

    # Musique de fond si absente
    if not (dossier / "audio" / "musique_fond.mp3").exists():
        try:
            log(f"  [{dossier.name}] Musique de fond...")
            generer_musique_fond_projet(dossier, sujet, type_contenu, config)
        except Exception as e:
            log(f"  [{dossier.name}] musique_fond: {e}")

    terminees = []
    erreurs = []
    for i, titre in enumerate(titres, 1):
        if list(export.glob(f"short_{i:02d}_*.mp4")):
            terminees.append(f"short_{i:02d}")
            continue
        nom_safe = re.sub(r'[^a-z0-9_]', '_', str(titre).lower())[:30]
        script_path = dossier / "scripts" / f"short_{i:02d}.txt"
        audio_path = dossier / "audio" / f"short_{i:02d}.wav"
        video_path = export / f"short_{i:02d}_{nom_safe}.mp4"
        thumb_path = dossier / "thumbnails" / f"short_{i:02d}.png"
        try:
            log(f"  [{dossier.name}] Short {i}/{len(titres)} : {str(titre)[:40]}")
            script = generer_script_short(titre, sujet, type_contenu, langue, duree_sec)
            script = nettoyer_intro_ia(script)
            script_path.write_text(script, encoding="utf-8")

            ok_audio = generer_audio_short(script, str(audio_path), langue, voix)
            if not ok_audio or not audio_path.exists():
                erreurs.append(f"short_{i:02d}: audio echec")
                continue
            try:
                generer_srt_for_short(str(audio_path), script,
                                      str(audio_path).replace(".wav", ".srt"))
            except Exception:
                pass

            image = choisir_image(str(paths.ASSETS_DIR), sujet, langue)
            if not image:
                erreurs.append(f"short_{i:02d}: aucune image")
                continue

            ok_video = creer_video_short(str(audio_path), image, str(video_path), titre,
                                         config, shorts_path=str(dossier), langue=langue,
                                         duree_sec=duree_sec)
            if not ok_video or not video_path.exists():
                erreurs.append(f"short_{i:02d}: video echec")
                continue
            try:
                generer_thumbnail_short(titre, str(thumb_path))
            except Exception:
                pass
            terminees.append(f"short_{i:02d}")
        except Exception as e:
            erreurs.append(f"short_{i:02d}: {e}")

    tout_termine = len(terminees) == len(titres)
    plan["statut"] = "termine" if tout_termine else "en_cours"
    planjson.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": tout_termine, "fait": tout_termine, "deja_termine": False,
            "etapes_terminees": terminees, "erreurs": erreurs}


def completer_projet(dossier, config):
    """Complete UN projet incomplet. Retourne un rapport."""
    rapport = analyser_projet(dossier)
    nom = rapport.get("nom", Path(dossier).name)
    if not rapport.get("completable"):
        return {"nom": nom, "fait": False, "deja_termine": True,
                "raison": rapport.get("raison", ""), "etapes_terminees": [], "erreurs": []}
    if rapport["type"] == "shorts":
        res = _completer_shorts(dossier, config)
    elif rapport["type"] == "longue":
        res = _completer_longue(dossier, config)
    else:
        res = {"ok": False, "etapes_terminees": [], "erreurs": ["pas_un_projet"]}
    res["nom"] = nom
    res["fait"] = bool(res.get("ok"))
    res["raison"] = "a_completer"
    return res


def completer_tous_projets(seuil_jours=7, supprimer_echecs=False):
    """Complete tous les projets recuperables, puis (option) supprime ceux qui
    restent incomplets ET etaient deja anciens ET sans video avant le traitement.

    La suppression n'est pas nouvelle : c'est la logique de cleanup.py
    (incomplet_sans_video), appliquee aux projets qui ont echoue la completion.
    """
    from modules.automation.progress import init as progress_init
    from modules.automation.progress import etape as progress_etape
    from modules.automation.progress import terminer_etape as progress_terminer
    from modules.automation.progress import fin as progress_fin
    from modules.projets import cleanup

    projects_dir = paths.PROJECTS_DIR
    if not projects_dir.exists() or not projects_dir.is_dir():
        return {"succes": False, "erreur": f"dossier projets introuvable : {projects_dir}"}

    config = _lire_config()
    rapport = analyser_tous_projets(seuil_jours)
    a_completer = [r for r in rapport["projets"] if r.get("completable")]

    # Avant traitement : quels projets etaient deja "incomplet_sans_video" (anciens) ?
    # Capte AVANT la completion car celle-ci rafraichit les dates de modification.
    anciens_sans_video = set()
    for d in projects_dir.iterdir():
        if not d.is_dir():
            continue
        if cleanup.analyser_projet(d, seuil_jours).get("raison") == "incomplet_sans_video":
            anciens_sans_video.add(d.name)

    progress_init()
    resultats = []
    total = max(len(a_completer), 1)
    for idx, p in enumerate(a_completer, 1):
        progress_etape("completer", f"Completion de {p['nom'][:45]}...",
                       int(5 + 90 * idx / total))
        try:
            res = completer_projet(Path(p["chemin"]), config)
        except Exception as e:
            res = {"nom": p["nom"], "fait": False, "raison": "exception",
                   "etapes_terminees": [], "erreurs": [str(e)]}
        resultats.append(res)
        etat = "OK" if res.get("fait") else "ECHEC"
        log(f"  [{idx}/{len(a_completer)}] {res['nom']}: {etat}")

    completes = [r.get("nom") for r in resultats if r.get("fait")]
    echecs = [r for r in resultats if not r.get("fait")]

    supprimes = []
    if supprimer_echecs:
        for r in echecs:
            nom = r.get("nom")
            if nom not in anciens_sans_video:
                continue  # pas deja ancien sans video -> on ne supprime pas
            dossier = projects_dir / nom
            if not dossier.exists():
                continue
            if not str(dossier.resolve()).startswith(str(projects_dir.resolve())):
                continue
            try:
                shutil.rmtree(str(dossier))
                supprimes.append(nom)
                log(f"  [SUPPRIME] {nom} (irrecuperable, echec de completion)")
            except Exception as e:
                log(f"  [ERREUR SUPPRESSION] {nom}: {e}")

    progress_terminer("completer", "termine", "Completion des projets terminee")
    progress_fin(resultat={"completes": completes, "echecs": [r.get("nom") for r in echecs],
                           "supprimes": supprimes})

    return {
        "succes": True,
        "mode": "completion" + ("+nettoyage" if supprimer_echecs else ""),
        "seuil_jours": seuil_jours,
        "total_a_completer": len(a_completer),
        "completes": completes,
        "echecs": [r.get("nom") for r in echecs],
        "supprimes": supprimes,
        "details": resultats,
    }


def supprimer_projet(nom):
    """Supprime UN SEUL projet, choisi explicitement par l'utilisateur.

    Memes garde-fous que cleanup.py (non modifie) : jamais hors de
    projects_dir, jamais un non-projet, jamais un projet termine/publie,
    jamais un projet avec video finale.
    """
    from modules.projets import cleanup

    projects_dir = paths.PROJECTS_DIR
    projects_root = projects_dir.resolve()
    dossier = (projects_dir / nom).resolve()
    if not str(dossier).startswith(str(projects_root)):
        return {"succes": False, "erreur": "projet invalide (hors du dossier projets)"}
    if not dossier.exists() or not dossier.is_dir():
        return {"succes": False, "erreur": f"projet introuvable : {nom}"}
    if not (dossier / "project.json").exists() and not (dossier / "plan.json").exists():
        return {"succes": False,
                "erreur": f"'{nom}' n'est pas un projet StudioIA (pas de project.json/plan.json)"}

    base = cleanup.analyser_projet(dossier, 0)  # seuil 0 : l'age ne bloque pas un choix explicite
    if base.get("raison") in ("statut_termine", "video_presente", "pas_un_projet"):
        return {"succes": False,
                "erreur": f"'{nom}' est {base.get('raison')} : suppression refusee (securite)"}

    try:
        shutil.rmtree(str(dossier))
    except Exception as e:
        return {"succes": False, "erreur": f"suppression impossible : {e}"}
    return {"succes": True, "supprime": nom}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _afficher_rapport(rapport):
    print("\n=== Analyse des projets incomplets (apercu) ===")
    print(f"Dossier projets  : {paths.PROJECTS_DIR}")
    print(f"Projets analyses : {rapport['total']}")
    print(f"A completer      : {len(rapport['a_completer'])}")
    print(f"Deja termines    : {len(rapport['termines'])}")
    print(f"IRRECUPERABLES   : {len(rapport['a_supprimer'])} "
          f"({rapport['espace_recuperable_mo']} Mo)\n")
    for r in rapport["projets"]:
        manq = ", ".join(r.get("etapes_manquantes", [])[:8]) or "-"
        print(f"  [{r['type']:<6}] {r['nom'][:42]:<44} {r['taille_mo']:>7} Mo  "
              f"verdict={r['raison']}")
        if manq != "-":
            print(f"        manque : {manq}")
    if not rapport["projets"]:
        print("  (aucun projet)")

    print(f"\nPour completer   : python -m modules.projets.completer --completer")
    print(f"Pour completer + supprimer les echecs : "
          f"python -m modules.projets.completer --completer --supprimer-echecs")


def main():
    parser = argparse.ArgumentParser(
        description="Analyser & terminer les projets incomplets de StudioIA.")
    parser.add_argument("--apercu", action="store_true",
                        help="Analyse seule, rien ne modifie (defaut)")
    parser.add_argument("--completer", action="store_true",
                        help="Complete les projets recuperables")
    parser.add_argument("--supprimer-echecs", action="store_true",
                        help="Supprime (apres completion) les projets toujours "
                             "incomplets ET anciens (logique cleanup.py)")
    parser.add_argument("--seuil", type=int, default=7,
                        help="Age minimum sans modification, en jours (defaut: 7)")
    args = parser.parse_args()

    if args.completer:
        res = completer_tous_projets(seuil_jours=args.seuil,
                                     supprimer_echecs=args.supprimer_echecs)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _afficher_rapport(analyser_tous_projets(seuil_jours=args.seuil))


if __name__ == "__main__":
    main()
