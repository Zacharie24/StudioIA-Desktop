# -*- coding: utf-8 -*-
"""
StudioIA-Next — Web Dashboard (FastAPI)

Interface web locale pour :
- Tableau de bord avec diagnostic système
- Analyse YouTube
- Statistiques des projets
- Corrections et apprentissage

Lancement: uvicorn web.main:app --reload --host 127.0.0.1 --port 8080
"""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from datetime import datetime

# Ajouter la racine au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import paths
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="StudioIA-Next Dashboard")

# Templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Assistant de premier lancement (routes séparées, aucune route existante touchée)
try:
    from web.setup_routes import setup_router
    app.include_router(setup_router)
except Exception as _e_setup:
    print(f"[web.main] Assistant /setup non monté : {_e_setup}")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Page d'accueil — tableau de bord"""
    # Charger le dernier diagnostic
    try:
        from modules.diagnostic import charger_dernier_diagnostic
        diagnostic = charger_dernier_diagnostic()
    except:
        diagnostic = None

    # ---- État des services EN TEMPS RÉEL ----
    # Le template lit diagnostic.etapes.{ollama,pexels,youtube,config}. Ce
    # fichier peut être absent (aucun diagnostic jamais lancé) ou obsolète :
    # on reconstruit donc ces 4 entrées à la volée.
    # - Ollama : test local rapide via core/ollama (127.0.0.1, évite la
    #   résolution IPv6 lente de "localhost").
    # - Pexels / YouTube : testeurs du module diagnostic (échec immédiat si
    #   aucune clé configurée ; sinon appel réseau réel).
    # - config : lecture directe de config.json.
    try:
        from modules import diagnostic as diag
        from core import services
        cfg = paths.lire_config()
        svc = services.etat_services()["ollama"]
        etapes_live = {
            "ollama": {"ok": svc["actif"], "modeles": svc["modeles"]},
            "pexels": diag._tester_pexels(cfg.get("pexels_api_key", "")),
            "youtube": diag._tester_youtube(),
            "config": {
                "profil_actif": cfg.get("profil_actif", "prayer"),
                "mode_visuel": cfg.get("mode_visuel", "intelligent"),
                "mode": cfg.get("mode", "local"),
                "low_resource": cfg.get("low_resource", True),
                "providers": cfg.get("providers", {"plan": "local", "chapitre": "local"}),
            },
        }
        if diagnostic is None:
            # Aucun diagnostic sauvegardé : structure minimale pour que les
            # cartes du haut ne cassent pas (score 0, projets 0).
            # Les clés ci-dessous correspondent à celles lues par dashboard.html
            # (diagnostic.etapes.profil.nom, .projets.total, .suggestions…).
            diagnostic = {
                "score_pct": 0, "score": 0, "score_max": 0,
                "etapes": {
                    "projets": {"total": 0, "termines": 0, "en_cours": 0},
                    "profil": {"ok": True, "nom": cfg.get("profil_actif", "prayer"), "regles": 0},
                },
                "suggestions": [],
            }
        diagnostic.setdefault("etapes", {})
        diagnostic["etapes"].update(etapes_live)
    except Exception as _e:
        print(f"[web.main] État des services temps réel indisponible : {_e}")

    # Stats rapides
    projects_path = paths.PROJECTS_DIR
    projets = []
    if projects_path.exists():
        for p in projects_path.iterdir():
            pjson = p / "project.json"
            if pjson.exists():
                try:
                    with open(pjson, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    etapes = data.get("etapes", {})
                    projets.append({
                        "nom": p.name,
                        "sujet": data.get("sujet", "?")[:50],
                        "type": data.get("type_contenu", "?"),
                        "termine": etapes.get("video") == "termine",
                        "etapes_terminees": sum(1 for v in etapes.values() if v == "termine"),
                        "etapes_total": len(etapes)
                    })
                except:
                    pass

    # Nombre de corrections
    try:
        from modules.learning.correction_memory import statistiques
        stats_corrections = statistiques()
    except:
        stats_corrections = {"total_corrections": 0, "en_attente": 0}

    return templates.TemplateResponse(request, "dashboard.html", {
        "diagnostic": diagnostic,
        "projets": projets[-10:],
        "stats_corrections": stats_corrections,
        "now": datetime.now().isoformat()
    })


@app.get("/youtube", response_class=HTMLResponse)
async def youtube_analytics(request: Request):
    """Page d'analyse YouTube"""
    return templates.TemplateResponse(request, "youtube.html", {
        "now": datetime.now().isoformat()
    })


@app.get("/youtube/analyze")
async def api_youtube_analyze(channel: str = ""):
    """API: analyse une chaîne YouTube"""
    if not channel:
        return {"erreur": "Paramètre 'channel' requis"}

    try:
        from modules.youtube_analyzer.youtube_stats import chercher_chaine, analyser_performances

        channel_id = chercher_chaine(channel)
        if not channel_id:
            return {"erreur": f"Chaîne '{channel}' introuvable"}

        resultat = analyser_performances(channel_id)
        if not resultat:
            return {"erreur": "Impossible d'analyser les performances"}

        return resultat
    except Exception as e:
        return {"erreur": str(e)}


# ---------------------------------------------------------------
# Audit de chaine
# ---------------------------------------------------------------

@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    """Page d'audit de chaine et comparaison"""
    return templates.TemplateResponse(request, "audit.html", {
        "now": datetime.now().isoformat()
    })


@app.get("/api/audit/ma-chaine")
async def api_audit_ma_chaine(concurrents: str = ""):
    """
    Audit complet de sa propre chaine (via OAuth) + comparaison optionnelle.

    Args:
        concurrents: noms de chaines separees par des virgules
    """
    try:
        from modules.youtube_analyzer.channel_audit import audit_ma_chaine_avec_concurrents
        noms = [n.strip() for n in concurrents.split(",") if n.strip()] if concurrents else []
        # L'audit fait des appels API synchrones -> thread pour ne pas bloquer le dashboard
        return await asyncio.to_thread(audit_ma_chaine_avec_concurrents, noms)
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/api/audit/chaine")
async def api_audit_chaine(channel: str = ""):
    """Audit d'une chaine precise (nom, handle ou ID)"""
    if not channel:
        return {"erreur": "Paramètre 'channel' requis"}

    try:
        from modules.youtube_analyzer.channel_audit import (
            _chercher_id_chaine, auditer_chaine
        )
        cid = channel if channel.startswith(("UC", "UC")) else _chercher_id_chaine(channel)
        if not cid:
            return {"erreur": f"Chaîne '{channel}' introuvable"}
        audit = await asyncio.to_thread(auditer_chaine, cid)
        if not audit:
            return {"erreur": "Impossible d'auditer cette chaîne"}
        return {"ok": True, "audit": audit}
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/api/audit/historique")
async def api_audit_historique():
    """Historique des audits sauvegardes"""
    try:
        from modules.youtube_analyzer.channel_audit import lister_audits
        return {"audits": lister_audits()}
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/api/audit/apprentissage")
async def api_audit_apprentissage():
    """Lecons croisees tirees de tous les audits sauvegardes"""
    try:
        from modules.youtube_analyzer.channel_audit import apprentissage_croise
        return apprentissage_croise()
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/api/comments/analyser")
async def api_comments_analyser(channel: str = ""):
    """Analyse les commentaires de la chaine cible (besoins, prieres des spectateurs)."""
    try:
        from modules.youtube_analyzer.comment_analyzer import analyser_comments_chaine, lire_derniere_analyse
        if channel:
            # Analyser une chaine precise donnee par ID
            return await asyncio.to_thread(analyser_comments_chaine, channel)
        resultat = await asyncio.to_thread(analyser_comments_chaine, None)
        return resultat
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/api/comments/dernieres")
async def api_comments_dernieres():
    """Derniere analyse de commentaires (sans relancer la collecte)."""
    try:
        from modules.youtube_analyzer.comment_analyzer import lire_derniere_analyse
        analyse = lire_derniere_analyse()
        return analyse or {"ok": False, "erreur": "Aucune analyse encore (lance /api/comments/analyser)"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/api/comments/citer")
async def api_comments_citer(n: int = 5):
    """Noms des commentateurs actifs a citer dans une video."""
    try:
        from modules.youtube_analyzer.comment_analyzer import commentateurs_a_citer
        return {"noms": commentateurs_a_citer(n)}
    except Exception as e:
        return {"noms": [], "erreur": str(e)}


# ---------------------------------------------------------------
# Surveillance de la chaine cible (stats + predictions toujours visibles)
# ---------------------------------------------------------------

@app.get("/api/surveillance")
async def api_surveillance():
    """Rapport complet de surveillance : stats + evolution + predictions + plan + avis IA"""
    try:
        from modules.youtube_analyzer.channel_audit import surveiller_chaine
        return await asyncio.to_thread(surveiller_chaine)
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/api/surveillance/statut")
async def api_surveillance_statut():
    """Etat leger (1 appel API) : chaine cible + stats actuelles + dernier controle"""
    try:
        from modules.youtube_analyzer.channel_audit import statut_surveillance
        return statut_surveillance()
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.post("/api/surveillance/cible")
async def api_surveillance_cible(request: Request):
    """Definit la chaine cible a surveiller (nom, handle ou ID)"""
    try:
        from modules.youtube_analyzer.channel_audit import definir_chaine_cible
        data = await request.json()
        nom = data.get("nom") or data.get("channel_id") or ""
        return await asyncio.to_thread(definir_chaine_cible, nom)
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


# ---------------------------------------------------------------
# Touche humaine (voix reelle pour les intros)
# ---------------------------------------------------------------

@app.get("/human-touch", response_class=HTMLResponse)
async def human_touch_page(request: Request):
    """Page touche humaine — enregistrement voix + indicateur DB"""
    return templates.TemplateResponse(request, "human_touch.html", {
        "now": datetime.now().isoformat()
    })


@app.get("/api/human-touch/statut")
async def api_human_touch_statut():
    """Statut de la touche humaine (active + enregistrements)"""
    try:
        from modules.human_touch.intro_voice import statut
        return statut()
    except Exception as e:
        return {"erreur": str(e)}


@app.post("/api/human-touch/activer")
async def api_human_touch_activer(request: Request):
    """Active/desactive la touche humaine"""
    try:
        from modules.human_touch.intro_voice import activer
        data = await request.json()
        return activer(data.get("actif", False))
    except Exception as e:
        return {"erreur": str(e)}


@app.post("/api/human-touch/mode")
async def api_human_touch_mode(request: Request):
    """
    Regle le mode de la touche humaine :
      "ia"   = l'IA ecrit un texte d'intro que l'utilisateur lit.
      "libre"= pas de texte IA, l'utilisateur fait son intro lui-meme
               (improvise au micro) et la video commence directement.
    """
    try:
        from modules.human_touch.intro_voice import set_mode
        data = await request.json()
        return set_mode(data.get("mode", "ia"))
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.post("/api/human-touch/generer-intro")
async def api_human_touch_generer(request: Request):
    """Genere un texte d'intro a lire a voix haute"""
    try:
        from modules.human_touch.intro_voice import generer_intro
        data = await request.json()
        sujet = data.get("sujet", "")
        if not sujet:
            return {"ok": False, "erreur": "Sujet requis"}
        return generer_intro(
            sujet=sujet,
            profil_id=data.get("profil_id", "prayer"),
            duree_secondes=data.get("duree_secondes", None),
            projet_nom=data.get("projet", "") or None
        )
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.post("/api/human-touch/upload-intro")
async def api_human_touch_upload(fichier: UploadFile = File(...),
                                 projet: str = Form(""),
                                 texte: str = Form("")):
    """Enregistre l'audio de l'intro uploade depuis le navigateur"""
    try:
        import tempfile
        from modules.human_touch.intro_voice import sauvegarder_enregistrement

        nom_original = fichier.filename or "intro.webm"
        ext = Path(nom_original).suffix or ".webm"
        contenu = await fichier.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contenu)
            tmp_path = tmp.name

        resultat = sauvegarder_enregistrement(tmp_path, ext.lstrip("."), projet, texte)
        try:
            os.remove(tmp_path)
        except:
            pass
        return resultat
    except Exception as e:
        return {"ok": False, "message": str(e)}


@app.post("/api/human-touch/sauver-texte")
async def api_human_touch_sauver_texte(request: Request):
    """
    Sauvegarde le texte d'intro colle/modifie par l'utilisateur pour un projet.
    C'est ce texte qui sera lu puis enregistre (et garde pour reference).
    """
    try:
        from modules.human_touch.intro_voice import sauvegarder_texte_intro
        data = await request.json()
        projet = (data.get("projet") or "").strip()
        texte = (data.get("texte") or "").strip()
        if not projet:
            return {"ok": False, "erreur": "Nom de projet requis pour sauvegarder le texte"}
        if not texte:
            return {"ok": False, "erreur": "Le texte est vide"}
        ok = sauvegarder_texte_intro(projet, texte)
        return {"ok": ok, "message": "Texte d'intro sauvegarde (il sera lu et enregistre)" if ok else "Echec sauvegarde"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/diagnostic/run")
async def api_run_diagnostic():
    """API: exécute un diagnostic"""
    try:
        from modules.diagnostic import executer_diagnostic
        resultat = executer_diagnostic(silent=True)
        return resultat
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/diagnostic/latest")
async def api_latest_diagnostic():
    """API: dernier diagnostic"""
    try:
        from modules.diagnostic import charger_dernier_diagnostic
        diag = charger_dernier_diagnostic()
        return diag or {"erreur": "Aucun diagnostic trouvé"}
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/api/projets")
async def api_projets():
    """API: liste des projets"""
    projects_path = paths.PROJECTS_DIR
    projets = []
    if projects_path.exists():
        for p in sorted(projects_path.iterdir(), reverse=True)[:20]:
            pjson = p / "project.json"
            if pjson.exists():
                try:
                    with open(pjson, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    etapes = data.get("etapes", {})
                    projets.append({
                        "nom": p.name,
                        "sujet": data.get("sujet", "?"),
                        "type": data.get("type_contenu", "?"),
                        "termine": etapes.get("video") == "termine",
                        "progression": f"{sum(1 for v in etapes.values() if v == 'termine')}/{len(etapes)}"
                    })
                except:
                    pass
    return {"projets": projets}


@app.get("/api/corrections")
async def api_corrections():
    """API: stats des corrections"""
    try:
        from modules.learning.correction_memory import statistiques, lister_corrections
        stats = statistiques()
        dernieres = lister_corrections(limite=10)
        return {"stats": stats, "dernieres": dernieres}
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/apprentissage", response_class=HTMLResponse)
async def apprentissage_page(request: Request):
    """Page d'apprentissage"""
    try:
        from modules.learning.learning_engine import generer_rapport_apprentissage
        rapport = generer_rapport_apprentissage()
    except:
        rapport = "Module d'apprentissage non disponible"

    return templates.TemplateResponse(request, "apprentissage.html", {
        "rapport": rapport,
        "now": datetime.now().isoformat()
    })


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Page de configuration"""
    config_path = Path(__file__).parent.parent / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except:
        config = {}
    return templates.TemplateResponse(request, "config.html", {
        "config": config,
        "now": datetime.now().isoformat()
    })


@app.post("/api/config")
async def api_save_config(request: Request):
    """API: sauvegarde la configuration"""
    config_path = Path(__file__).parent.parent / "config.json"
    try:
        data = await request.json()

        # Charger la config existante pour ne pas perdre les cles non envoyees
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            existing = {}

        existing.update(data)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        return {"ok": True, "message": "Configuration mise a jour"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/automation", response_class=HTMLResponse)
async def automation_page(request: Request):
    """Page d'automatisation"""
    return templates.TemplateResponse(request, "automation.html", {
        "now": datetime.now().isoformat()
    })


@app.get("/api/automation/run")
async def api_automation_run(force_generer: bool = False, force_regenerate: bool = False,
                             directives: str = ""):
    """
    API: lance le pipeline automatique dans un thread en arriere-plan.
    Retourne immediatement; la progression se lit via /api/automation/progress.

    directives: consignes facultatives de l'utilisateur (citer, interdire,
                commentateurs...) respectees par le generateur de texte.
    """
    try:
        from modules.automation.progress import get as progress_get
        if progress_get().get("en_cours"):
            return {"succes": False, "erreur": "Un pipeline est deja en cours. Attends la fin ou relance."}

        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        profil_id = config.get("profil_actif", "prayer")

        from modules.automation.pipeline import executer_pipeline
        from modules.automation.progress import init as progress_init

        progress_init()  # etat propre avant lancement

        def _tache():
            try:
                executer_pipeline(profil_id=profil_id, force_generer=force_generer,
                                  directives=directives.strip() or None)
            except Exception as e:
                import traceback
                traceback.print_exc()
                from modules.automation.progress import fin as progress_fin
                progress_fin(erreur=str(e))

        threading.Thread(target=_tache, daemon=True).start()
        return {"succes": True, "demarre": True, "message": "Pipeline lance en arriere-plan — voir la barre de progression."}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


@app.get("/api/automation/progress")
async def api_automation_progress():
    """API: etat de progression du pipeline en cours (polling par l'interface)"""
    try:
        from modules.automation.progress import get as progress_get
        return progress_get()
    except Exception as e:
        return {"en_cours": False, "erreur": str(e)}


def _chemin_projet(projet: str):
    """Resout un nom de projet vers son dossier, securise sous projects/."""
    projects_root = paths.PROJECTS_DIR.resolve()
    projet_dir = (projects_root / projet).resolve()
    if not str(projet_dir).startswith(str(projects_root)):
        return None
    return projet_dir


@app.get("/api/projets/nettoyer")
async def api_projets_nettoyer(seuil: int = 7):
    """Apercu (dry-run) : liste les projets incomplets candidats a la suppression."""
    try:
        from modules.projets.cleanup import nettoyer_projets_incomplets
    except Exception as e:
        return {"succes": False, "erreur": f"module cleanup indisponible : {e}"}
    return nettoyer_projets_incomplets(paths.PROJECTS_DIR, seuil_jours=seuil, supprimer=False)


@app.post("/api/projets/nettoyer")
async def api_projets_nettoyer_post(request: Request, seuil: int = 7):
    """Supprime reellement les projets incomplets — requiert une confirmation
    explicite dans le corps JSON : {"confirmer": true}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not body.get("confirmer"):
        return {"succes": False,
                "erreur": "Confirmation requise : envoyez un POST avec {\"confirmer\": true}"}
    try:
        from modules.projets.cleanup import nettoyer_projets_incomplets
    except Exception as e:
        return {"succes": False, "erreur": f"module cleanup indisponible : {e}"}
    return nettoyer_projets_incomplets(paths.PROJECTS_DIR, seuil_jours=seuil, supprimer=True)


@app.get("/api/projets/analyser")
async def api_projets_analyser(seuil: int = 7):
    """Analyse (dry-run, rapide) : liste tous les projets avec type, etapes
    manquantes et verdict (a completer / a supprimer / deja termine)."""
    try:
        from modules.projets.completer import analyser_tous_projets
    except Exception as e:
        return {"succes": False, "erreur": f"module completer indisponible : {e}"}
    return analyser_tous_projets(seuil_jours=seuil)


@app.post("/api/projets/completer")
async def api_projets_completer(request: Request):
    """
    Complete les projets recuperables (script/audio/images/video/vignette
    manquants), puis supprime (option) ceux qui restent incomplets ET anciens.

    Corps JSON : {"confirmer": true, "seuil": 7, "supprimer_echecs": false}
    Lance dans un thread en arriere-plan; progression via /api/automation/progress.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not body.get("confirmer"):
        return {"succes": False,
                "erreur": "Confirmation requise : envoyez un POST avec {\"confirmer\": true}"}
    seuil = int(body.get("seuil", 7) or 7)
    supprimer_echecs = bool(body.get("supprimer_echecs", False))

    try:
        from modules.automation.progress import get as progress_get
        if progress_get().get("en_cours"):
            return {"succes": False,
                    "erreur": "Une generation est deja en cours. Attends la fin ou relance."}

        from modules.projets.completer import completer_tous_projets
        from modules.automation.progress import init as progress_init

        progress_init()  # etat propre avant lancement

        def _tache():
            try:
                completer_tous_projets(seuil_jours=seuil,
                                       supprimer_echecs=supprimer_echecs)
            except Exception as e:
                import traceback
                traceback.print_exc()
                from modules.automation.progress import fin as progress_fin
                progress_fin(erreur=str(e))

        threading.Thread(target=_tache, daemon=True).start()
        return {"succes": True, "demarre": True,
                "message": "Completion lancee en arriere-plan — voir la barre de progression."}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


@app.post("/api/projets/completer/un")
async def api_projets_completer_un(request: Request):
    """Complete UN SEUL projet (choisi par l'utilisateur) en arriere-plan.

    Corps JSON : {"nom": "dossier_projet", "confirmer": true}
    Progression via /api/automation/progress (un seul traitement a la fois).
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    nom = (body.get("nom") or "").strip()
    if not body.get("confirmer"):
        return {"succes": False,
                "erreur": "Confirmation requise : envoyez un POST avec {\"confirmer\": true}"}
    if not nom:
        return {"succes": False, "erreur": "Parametre 'nom' requis"}

    try:
        from modules.automation.progress import get as progress_get
        if progress_get().get("en_cours"):
            return {"succes": False,
                    "erreur": "Une generation est deja en cours. Attends la fin ou relance."}

        from core import paths
        dossier = (paths.PROJECTS_DIR / nom).resolve()
        if not str(dossier).startswith(str(paths.PROJECTS_DIR.resolve())) or not dossier.is_dir():
            return {"succes": False, "erreur": f"projet introuvable : {nom}"}

        from modules.projets.completer import completer_projet, _lire_config
        from modules.automation.progress import init as progress_init
        from modules.automation.progress import terminer_etape as progress_terminer
        from modules.automation.progress import fin as progress_fin

        config = _lire_config()
        progress_init()  # etat propre avant lancement

        def _tache():
            try:
                res = completer_projet(dossier, config)
                etat = "OK" if res.get("fait") else "ECHEC"
                progress_terminer("completer", "termine", f"Projet {nom} : {etat}")
                progress_fin(resultat=res)
            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_fin(erreur=str(e))

        threading.Thread(target=_tache, daemon=True).start()
        return {"succes": True, "demarre": True, "projet": nom,
                "message": f"Completion de « {nom} » lancee en arriere-plan."}
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


@app.post("/api/projets/supprimer")
async def api_projets_supprimer(request: Request):
    """Supprime UN SEUL projet, choisi explicitement (garde-fous cleanup.py).

    Corps JSON : {"nom": "dossier_projet", "confirmer": true}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    nom = (body.get("nom") or "").strip()
    if not body.get("confirmer"):
        return {"succes": False,
                "erreur": "Confirmation requise : envoyez un POST avec {\"confirmer\": true}"}
    if not nom:
        return {"succes": False, "erreur": "Parametre 'nom' requis"}
    try:
        from modules.projets.completer import supprimer_projet
        return supprimer_projet(nom)
    except Exception as e:
        return {"succes": False, "erreur": str(e)}


@app.get("/api/automation/video")
async def api_automation_video(projet: str = ""):
    """Sert la video generee d'un projet (lecture / telechargement)."""
    if not projet:
        return {"succes": False, "erreur": "Parametre projet manquant"}
    from fastapi.responses import FileResponse
    projet_dir = _chemin_projet(projet)
    if not projet_dir:
        return {"succes": False, "erreur": "Projet invalide"}

    chemin = None
    pj = projet_dir / "project.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            ff = data.get("fichier_final") or ""
            if ff:
                p = (projet_dir / ff).resolve()
                if str(p).startswith(str(projet_dir)) and p.exists():
                    chemin = p
        except Exception:
            pass
    if not chemin:
        vids = sorted((projet_dir / "export" / "video").glob("*.mp4")) if (projet_dir / "export" / "video").exists() else []
        if vids:
            chemin = vids[-1]
    if not chemin or not chemin.exists():
        return {"succes": False, "erreur": "Aucune video generee pour ce projet"}
    return FileResponse(str(chemin), media_type="video/mp4", filename=chemin.name)


@app.get("/api/automation/thumbnail")
async def api_automation_thumbnail(projet: str = ""):
    """Sert la vignette generee d'un projet."""
    if not projet:
        return {"succes": False, "erreur": "Parametre projet manquant"}
    from fastapi.responses import FileResponse
    projet_dir = _chemin_projet(projet)
    if not projet_dir:
        return {"succes": False, "erreur": "Projet invalide"}
    thumbs = sorted((projet_dir / "thumbnail").glob("*.png")) if (projet_dir / "thumbnail").exists() else []
    if not thumbs:
        return {"succes": False, "erreur": "Aucune vignette pour ce projet"}
    return FileResponse(str(thumbs[-1]), media_type="image/png", filename=thumbs[-1].name)


@app.get("/api/system/stats")
async def api_system_stats():
    """API: utilisation CPU / RAM / Disque / GPU en temps reel pour la barre du haut"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        try:
            disk = psutil.disk_usage("C:")
            disk_pct = round(disk.percent, 1)
        except Exception:
            disk_pct = None
        return {
            "cpu": round(cpu, 1),
            "ram_pct": round(mem.percent, 1),
            "ram_utilisee_gb": round(mem.used / 1024**3, 1),
            "ram_total_gb": round(mem.total / 1024**3, 1),
            "disque_pct": disk_pct,
            "gpu": None,          # pas de GPU detecte (pas de nvidia-smi)
            "gpu_nom": None,
            "cores": psutil.cpu_count(logical=True)
        }
    except Exception as e:
        return {"erreur": str(e)}


@app.get("/api/youtube/auth-status")
async def api_youtube_auth_status():
    """API: statut de l'authentification YouTube OAuth"""
    try:
        from modules.youtube_analyzer.youtube_upload import statut_auth, client_secret_exists
        status = statut_auth()
        status["client_secret_present"] = client_secret_exists()
        return status
    except Exception as e:
        return {"configured": False, "erreur": str(e)}


# ---------------------------------------------------------------
# Edition video / shorts / vignettes / voix (portage du GUI PowerShell)
# ---------------------------------------------------------------

@app.get("/edition", response_class=HTMLResponse)
async def edition_page(request: Request):
    """Page d'edition : shorts, vignettes, clonage de voix"""
    return templates.TemplateResponse(request, "edition.html", {
        "now": datetime.now().isoformat()
    })


@app.post("/api/edition/shorts")
async def api_edition_shorts(request: Request):
    """Lance la generation de Shorts dans un thread de fond (progression via /api/automation/progress)."""
    try:
        from modules.automation.progress import get as progress_get
        if progress_get().get("en_cours"):
            return {"ok": False, "erreur": "Une generation est deja en cours. Attends la fin."}

        data = await request.json()
        sujet = (data.get("sujet") or "").strip()
        if not sujet:
            return {"ok": False, "erreur": "Sujet requis"}

        type_map = {"1": "priere", "2": "storytelling", "3": "storytelling", "4": "general"}
        type_choix = str(data.get("type_contenu", "1"))
        type_contenu = type_map.get(type_choix, "priere")
        langue = "en" if type_choix == "3" else data.get("langue", "fr")
        duree_sec = int(data.get("duree_sec", 60) or 60)
        nb_shorts = max(1, min(10, int(data.get("nb_shorts", 5) or 5)))
        voix_choix = str(data.get("voix_choix", "3"))

        from modules.automation.progress import init as progress_init
        from modules.edition.web_edition import generer_shorts_via_web
        progress_init()

        def _tache():
            try:
                generer_shorts_via_web(
                    sujet=sujet, type_contenu=type_contenu, langue=langue,
                    duree_sec=duree_sec, nb_shorts=nb_shorts, voix_choix=voix_choix
                )
            except Exception as e:
                from modules.automation.progress import fin as progress_fin
                progress_fin(erreur=str(e))

        threading.Thread(target=_tache, daemon=True).start()
        return {"ok": True, "demarre": True,
                "message": f"Generation de {nb_shorts} Shorts lancee — voir la barre de progression."}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/api/edition/shorts/list")
async def api_edition_shorts_list():
    """Liste les projets shorts existants avec leurs videos."""
    try:
        from modules.edition.web_edition import lister_projets_shorts
        return {"projets": lister_projets_shorts()}
    except Exception as e:
        return {"projets": [], "erreur": str(e)}


@app.post("/api/edition/video-longue")
async def api_edition_video_longue(request: Request):
    """
    Lance la generation d'une VIDEO LONGUE dans un thread de fond.

    Body:
        sujet (str, requis), type_contenu (1..4), langue (fr/en),
        duree_minutes (int), voix_choix (str), directives (str ou dict),
        titre (str, optionnel)
    Progression via /api/automation/progress.
    """
    try:
        from modules.automation.progress import get as progress_get
        if progress_get().get("en_cours"):
            return {"ok": False, "erreur": "Une generation est deja en cours. Attends la fin."}

        data = await request.json()
        sujet = (data.get("sujet") or "").strip()
        if not sujet:
            return {"ok": False, "erreur": "Sujet requis"}
        if len(sujet) < 3:
            return {"ok": False, "erreur": "Sujet trop court (3 caracteres min)"}

        type_choix = str(data.get("type_contenu", "1"))
        langue = "en" if type_choix == "3" else data.get("langue", "fr")
        duree_minutes = max(1, min(180, int(data.get("duree_minutes", 30) or 30)))
        voix_choix = str(data.get("voix_choix", "3"))
        directives = data.get("directives") or None
        titre = (data.get("titre") or "").strip() or None
        description = (data.get("description") or "").strip()
        tags = data.get("tags") or []

        from modules.automation.progress import init as progress_init
        from modules.edition.web_edition import generer_video_longue_via_web
        progress_init()

        def _tache():
            try:
                generer_video_longue_via_web(
                    sujet=sujet, type_contenu=type_choix, langue=langue,
                    duree_minutes=duree_minutes, voix_choix=voix_choix,
                    directives=directives, titre=titre, description=description,
                    tags=tags
                )
            except Exception as e:
                import traceback
                traceback.print_exc()
                from modules.automation.progress import fin as progress_fin
                progress_fin(erreur=str(e))

        threading.Thread(target=_tache, daemon=True).start()
        return {"ok": True, "demarre": True,
                "message": f"Generation video longue (~{duree_minutes} min) lancee — voir la barre de progression."}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.get("/api/edition/video-longue/list")
async def api_edition_video_longue_list():
    """Liste les projets de videos longues generes."""
    try:
        from modules.edition.web_edition import lister_projets_longues
        return {"projets": lister_projets_longues()}
    except Exception as e:
        return {"projets": [], "erreur": str(e)}


@app.post("/api/edition/thumbnail")
async def api_edition_thumbnail(request: Request):
    """Genere une vignette standalone a partir d'un titre."""
    try:
        from modules.edition.web_edition import generer_thumbnail_via_web
        data = await request.json()
        titre = (data.get("titre") or "").strip()
        if not titre:
            return {"ok": False, "erreur": "Titre requis"}
        resultat = await asyncio.to_thread(generer_thumbnail_via_web, titre)
        if resultat.get("ok"):
            # Copier dans web/static pour un acces direct via /static
            from shutil import copy2
            static_dir = Path(__file__).parent / "static" / "thumbnails"
            static_dir.mkdir(parents=True, exist_ok=True)
            nom = Path(resultat["chemin"]).name
            dest = static_dir / nom
            try:
                copy2(resultat["chemin"], dest)
                resultat["url"] = "/static/thumbnails/" + nom
            except Exception as e:
                resultat["url"] = None
        return resultat
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


@app.post("/api/edition/voix-clonee")
async def api_edition_voix_clonee(fichier: UploadFile = File(...),
                                  nom: str = Form(""),
                                  description: str = Form("")):
    """Clone une voix depuis un fichier audio uploade."""
    try:
        import tempfile
        from modules.edition.web_edition import cloner_voix_via_web
        nom = nom.strip()
        if not nom:
            return {"ok": False, "message": "Nom de voix requis"}

        nom_original = fichier.filename or "voix.webm"
        ext = Path(nom_original).suffix or ".wav"
        contenu = await fichier.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contenu)
            tmp_path = tmp.name

        try:
            resultat = await asyncio.to_thread(cloner_voix_via_web, nom, tmp_path, description)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return resultat
    except Exception as e:
        return {"ok": False, "message": str(e)}


@app.get("/api/edition/voix-clonees")
async def api_edition_voix_clonees():
    """Liste les voix clonees."""
    try:
        from modules.edition.web_edition import lister_voix_clonees_via_web
        return {"voix": lister_voix_clonees_via_web()}
    except Exception as e:
        return {"voix": [], "erreur": str(e)}


@app.get("/api/edition/voix")
async def api_edition_voix():
    """Liste toutes les voix TTS disponibles (XTTS, Edge, Piper, clones)."""
    try:
        from modules.tts.voix_config import VOIX_DISPONIBLES, CLONED_VOICES, VOIX_MAP_SHORTS
        voix = []
        for k, v in VOIX_DISPONIBLES.items():
            voix.append({"id": k, "label": v.get("label", k), "moteur": v.get("moteur", "")})
        for cv in CLONED_VOICES:
            voix.append({"id": cv.get("key", ""), "label": cv.get("name", cv.get("key", "")),
                         "moteur": "xtts", "clone": True})
        return {"voix": voix, "voix_shorts": list(VOIX_MAP_SHORTS.keys()),
                "defaut": _lire_config_tts_voix()}
    except Exception as e:
        return {"voix": [], "erreur": str(e)}


def _lire_config_tts_voix():
    """Voix TTS par defaut depuis config.json."""
    try:
        cfg = json.loads((Path(__file__).parent.parent / "config.json").read_text(encoding="utf-8"))
        return str(cfg.get("tts_voix", "3"))
    except Exception:
        return "3"


if __name__ == "__main__":
    print("=== StudioIA-Next Web Dashboard ===")
    print("http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)
