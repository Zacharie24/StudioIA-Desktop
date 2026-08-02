# -*- coding: utf-8 -*-
"""
core/paths.py — Résolution centrale des chemins de StudioIA Desktop.

Toutes les constantes absolues de l'ancienne version
(C:\\StudioIA\\..., C:\\StudioIA-Next\\..., C:\\tts-pentest) sont remplacées
par des chemins résolus ici. Aucun module ne doit contenir de chemin absolu.

Deux racines :
  RACINE_APP  — dossier de l'application (modules/, web/, assets/, tools/...).
                C'est le parent de core/, donc fonctionne en mode source
                comme en mode installé (%LOCALAPPDATA%\\Programs\\StudioIA).
  DATA_DIR    — données utilisateur (%USERPROFILE%\\StudioIA) : projets,
                config utilisateur, logs, modèles Ollama, pack XTTS.
                Surchargé par la variable d'environnement STUDIOIA_DATA_DIR
                (l'installateur / le shell Tauri la définissent).

En mode source (développement), DATA_DIR n'existe pas encore : la config et
les projets restent dans RACINE_APP, exactement comme avant — aucun
changement de comportement.
"""

import os
import sys
from pathlib import Path

# --- Racine de l'application -------------------------------------------------
# core/paths.py  ->  RACINE_APP = C:\StudioIA-Desktop (ou dossier installé)
RACINE_APP = Path(__file__).resolve().parent.parent

# --- Données utilisateur ------------------------------------------------------
# Mode installé : STUDIOIA_DATA_DIR est défini par le shell Tauri / l'installateur
# → les données utilisateur vivent hors du dossier d'app (%USERPROFILE%\StudioIA).
# Mode source (développement) : aucune variable → tout reste dans RACINE_APP,
# exactement comme avant (aucun changement de comportement).
_env_data = os.environ.get("STUDIOIA_DATA_DIR", "").strip()
if _env_data:
    DATA_DIR = Path(_env_data)
else:
    DATA_DIR = RACINE_APP


# --- Helpers de base -----------------------------------------------------------
def chemin_app(*parts):
    """Chemin sous la racine de l'application (modules, web, assets...)."""
    return RACINE_APP.joinpath(*parts)


def chemin_data(*parts):
    """Chemin sous les données utilisateur (projets, config, logs...)."""
    return DATA_DIR.joinpath(*parts)


def str_chemin(p):
    """Convertit un Path en chaîne Windows native (pratique pour subprocess)."""
    return str(Path(p))


# --- Chemins "app" fréquents ----------------------------------------------------
MODULES_DIR      = chemin_app("modules")
WEB_DIR          = chemin_app("web")
ASSETS_DIR       = chemin_app("assets")
MUSIC_DIR        = ASSETS_DIR / "music"
BACKGROUNDS_DIR  = ASSETS_DIR / "backgrounds"
FONTS_DIR        = ASSETS_DIR / "fonts"
COMPOSIA_DIR     = chemin_app("ComposIA")
SOUNDFONTS_DIR   = COMPOSIA_DIR / "soundfonts"
COMPOSITIONS_DIR = COMPOSIA_DIR / "compositions"
TOOLS_DIR        = chemin_app("tools")
FFMPEG_DIR       = TOOLS_DIR / "ffmpeg"
FFMPEG           = FFMPEG_DIR / "ffmpeg.exe"
FFPROBE          = FFMPEG_DIR / "ffprobe.exe"
FFPLAY           = FFMPEG_DIR / "ffplay.exe"
TEMP_DIR         = chemin_app("temp")

# --- Chemins "données utilisateur" ----------------------------------------------
PROJECTS_DIR     = chemin_data("projects")
LOGS_DIR         = chemin_data("logs")
OLLAMA_DIR       = chemin_data(".ollama")
XTTS_DIR         = chemin_data("xtts")


# --- Configuration ----------------------------------------------------------------
def config_path():
    """Chemin du config.json effectif pour LECTURE directe.

    Ordre :
      1. utilisateur (DATA_DIR/config.json) — mode installé,
      2. config.local.json (dev, gitignoré)  — mode source avec clés locales,
      3. config embarquée (RACINE_APP/config.json).
    """
    if DATA_DIR != RACINE_APP:
        p = chemin_data("config.json")
        if p.exists():
            return p
    local = chemin_app("config.local.json")
    if local.exists():
        return local
    return chemin_app("config.json")


def lire_config():
    """Lit la configuration effective, en FUSIONNANT les sources :

        config embarquée (défauts) < config.local.json (dev) < config utilisateur

    Les clés réelles (API, etc.) vivent hors de la config embarquée committée
    (config.local.json en source / DATA_DIR en installé) : ce merge les
    réintroduit au moment de la lecture, sans jamais polluer config.json.
    En mode source, DATA_DIR == RACINE_APP : la config embarquée sert de base
    et config.local.json la surcharge (pas de 3e source dupliquée).
    """
    import json

    def _lire(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception:
            return {}

    merged = {}
    merged.update(_lire(chemin_app("config.json")))        # défauts embarqués
    merged.update(_lire(chemin_app("config.local.json")))  # dev (gitignoré)
    if DATA_DIR != RACINE_APP:
        merged.update(_lire(chemin_data("config.json")))   # utilisateur (installé)
    return merged


def ecrire_config(donnees):
    """Sauvegarde la configuration UTILISATEUR (jamais la config embarquée).

    Mode installé : %USERPROFILE%\\StudioIA\\config.json (isolé du dossier app,
    conservé pendant les mises à jour / désinstallation).
    Mode source   : config.local.json (gitignoré) — pour ne jamais écrire des
    valeurs locales ou clés réelles dans la config embarquée committée.
    """
    import json
    if DATA_DIR != RACINE_APP:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = chemin_data("config.json")
    else:
        path = chemin_app("config.local.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
    return str(path)


def lire_json(path):
    """Lecture JSON tolérante à la BOM. Retourne {} si échec."""
    import json
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return {}


def ecrire_json(path, data):
    """Écriture JSON propre (UTF-8, indenté)."""
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- sys.path --------------------------------------------------------------------
def ajouter_modules_au_path():
    """Ajoute modules/ au sys.path (exécution directe des scripts).
    Retourne le chemin inséré."""
    m = str(MODULES_DIR)
    if m not in sys.path:
        sys.path.insert(0, m)
    return m


# --- Runtime Python embarqué ---------------------------------------------------------
def python_exe():
    """Chemin de l'interpréteur Python à utiliser pour les sous-processus.

    Retourne le Python embarqué (runtime/python.exe) s'il existe, sinon
    l'interpréteur courant (sys.executable). L'appelant décide de lancer ou
    d'accepter un interpréteur système (GUI legacy, outils de dev).
    """
    rt = RACINE_APP / "runtime" / "python" / "python.exe"
    return str(rt) if rt.exists() else sys.executable


def pythonw_exe():
    """Version sans console (pythonw.exe) du runtime, pour processus en fond."""
    rt = RACINE_APP / "runtime" / "python" / "pythonw.exe"
    return str(rt) if rt.exists() else sys.executable


def lancer_script(script: str, args=None, cwd=None):
    """Commande subprocess pour lancer un script Python avec le runtime.

    Retourne la liste à passer à subprocess.run/Popen :
        subprocess.Popen(paths.lancer_script("modules/x.py", ["a"]))
    Preferer sys.executable pour les tâches internes (même interpréteur) ;
    utiliser celui-ci pour forcer explicitement le runtime.
    """
    cmd = [python_exe(), script_path(script)]
    if args:
        cmd.extend(args)
    return cmd


def script_path(script):
    """Résout un chemin de script relatif à la racine de l'application."""
    p = Path(script)
    return str(p if p.is_absolute() else RACINE_APP / p)


def _import_depuis_racine():
    """Import robuste du module paths depuis un script exécuté en direct.

    Parcourt les parents jusqu'à trouver le dossier contenant core/paths.py,
    l'ajoute à sys.path puis importe. À utiliser ainsi :

        try:
            from core import paths
        except ImportError:
            paths = __import__("core.paths", fromlist=["paths"]).paths
            # fallback manuel ci-dessous si besoin
    """
    rac = Path(__file__).resolve().parent
    while not (rac / "core" / "paths.py").exists():
        rac = rac.parent
        if rac.parent == rac:
            raise ImportError("core/paths.py introuvable")
    if str(rac) not in sys.path:
        sys.path.insert(0, str(rac))
    return rac


# --- TTS (XTTS optionnel / Edge par défaut) -----------------------------------------
def tts_path():
    """Chemin du moteur TTS externe (pack XTTS), ou None si absent.

    Ordre de résolution :
      1. config.json -> tts_external_path (clé historique)
      2. DATA_DIR/xtts (pack installé par l'application)
      3. ancien C:\\tts-pentest encore présent (compat développement)

    Si None -> l'app utilise Edge par défaut (fallback déjà codé).
    """
    cfg = lire_config()
    p = cfg.get("tts_external_path")
    if p:
        return str(p)

    d = chemin_data("xtts")
    if (d / "venv" / "Scripts" / "python.exe").exists():
        return str(d)

    legacy = Path(r"C:\tts-pentest")
    if (legacy / "venv" / "Scripts" / "python.exe").exists():
        return str(legacy)
    return None


def tts_venv_python():
    """Interpréteur Python du venv TTS (pack XTTS) ou None."""
    t = tts_path()
    if not t:
        return None
    vp = Path(t) / "venv" / "Scripts" / "python.exe"
    return str(vp) if vp.exists() else None
