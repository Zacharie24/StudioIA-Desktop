# -*- coding: utf-8 -*-
"""
web/setup_routes.py — Assistant de premier lancement (/setup).

Routes séparées du gros main.py pour ne rien y casser. Montées par
`app.include_router(setup_router)` dans web/main.py.

Fournit :
  GET  /setup                       — page d'assistant (template setup.html)
  GET  /api/setup/etat              — état de préparation (services + config)
  POST /api/setup/demarrer-ollama   — démarre / vérifie Ollama en fond
  POST /api/setup/verifier-modeles  — liste les modèles manquants
  POST /api/setup/config            — enregistre clés API + réglages de départ

Le score de préparation réutilise le diagnostic existant. Aucune fonctionnalité
existante n'est modifiée.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

sys.path.insert(0, str(Path(__file__).parent.parent))

setup_router = APIRouter()

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def _lire_config():
    from core import paths
    try:
        with open(paths.config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _sauver_config(donnees):
    from core import paths
    try:
        existing = _lire_config()
        existing.update(donnees)
        with open(paths.config_path(), "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


@setup_router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Assistant de premier lancement."""
    from core import services, paths
    cfg = _lire_config()

    # État initial (léger) pour peaufiner la page.
    etat = {
        "ollama_installe": services.ollama_installe(),
        "ollama_actif": services.serveur_actif(),
        "ffmpeg_ok": services.ffmpeg_ok(),
        "config_path": str(paths.config_path()),
    }
    return _templates.TemplateResponse(request, "setup.html", {
        "etat": etat,
        "config": cfg,
        "now": datetime.now().isoformat(),
    })


@setup_router.get("/api/setup/etat")
async def api_setup_etat():
    """État de préparation complet (7 items, score compris)."""
    from core import services

    manquants, presents = services.modeles_manquants()

    # Items de préparation.
    items = []
    items.append({"cle": "ollama", "label": "Ollama",
                  "ok": services.serveur_actif(),
                  "detail": "serveur actif" if services.serveur_actif() else "hors ligne"})
    items.append({"cle": "modeles", "label": "Modèles IA (qwen2.5:7b + mistral)",
                  "ok": len(manquants) == 0,
                  "detail": ", ".join(manquants) if manquants else f"{len(presents)} modèle(s)"})
    items.append({"cle": "ffmpeg", "label": "FFmpeg",
                  "ok": services.ffmpeg_ok(), "detail": "présent"})
    cfg = _lire_config()
    items.append({"cle": "pexels", "label": "Clé API Pexels",
                  "ok": bool(cfg.get("pexels_api_key")),
                  "detail": "configurée" if cfg.get("pexels_api_key") else "manquante"})
    items.append({"cle": "youtube", "label": "Clé API YouTube",
                  "ok": bool(cfg.get("youtube_api_key")),
                  "detail": "configurée" if cfg.get("youtube_api_key") else "manquante"})
    items.append({"cle": "profil", "label": "Contexte (profil utilisateur)",
                  "ok": True, "detail": cfg.get("profil_actif", "prayer")})
    items.append({"cle": "donnees", "label": "Données utilisateur",
                  "ok": True, "detail": "prêtes"})

    ok = sum(1 for it in items if it["ok"])
    score = round(ok / len(items) * 100) if items else 0

    return {
        "score": score,
        "items": items,
        "ollama_models_dir": str(services.ollama_models_dir()),
        "services": services.etat_services(),
    }


@setup_router.post("/api/setup/demarrer-ollama")
async def api_setup_demarrer_ollama():
    """Démarre / vérifie Ollama (asynchrone pour ne pas bloquer la page)."""
    import threading
    resultat = {"ok": False, "message": "en cours"}

    def _tache():
        from core import services
        ok, msg = services.demarrer_serveur()
        resultat["ok"] = ok
        resultat["message"] = msg

    threading.Thread(target=_tache, daemon=True).start()
    return resultat


@setup_router.post("/api/setup/verifier-modeles")
async def api_setup_verifier_modeles(body: dict | None = None):
    """Liste les modèles manquants par rapport aux requis."""
    from core import services
    requis = (body or {}).get("modeles") or services.MODELES_REQUIS
    manquants, presents = services.modeles_manquants(requis)
    return {"manquants": manquants, "presents": presents, "requis": requis}


@setup_router.post("/api/setup/import-modeles")
async def api_setup_import_modeles():
    """Importe les modèles depuis le bundle local (payload installateur), si présent."""
    from core import paths
    bundle_dir = paths.RACINE_APP / "bundle-models"
    if not bundle_dir.exists():
        return {"ok": False, "message": "Bundle de modèles absent (mode source).", "importe": []}

    from core import services
    importe = []
    errors = []
    for nom in services.MODELES_REQUIS:
        try:
            if services.importer_modele_depuis_bundle(nom, str(bundle_dir)):
                importe.append(nom)
        except Exception as e:
            errors.append(f"{nom}: {e}")
    return {"ok": len(errors) == 0, "importe": importe, "erreurs": errors}


@setup_router.post("/api/setup/config")
async def api_setup_enregistrer(request: Request):
    """Enregistre clés API + réglages (surcharge par-dessus la config)."""
    try:
        data = await request.json()
        if _sauver_config(data):
            return {"ok": True, "message": "Configuration enregistrée"}
        return {"ok": False, "erreur": "Échec de l'enregistrement"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}