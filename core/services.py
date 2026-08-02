# -*- coding: utf-8 -*-
"""
core/services.py — Gestion des services externes de StudioIA (Ollama, FFmpeg).

Objectif (Phase 4) : rendre l'installation des dépendances invisible pour
l'utilisateur final et isoler les gros artefacts dans les données utilisateur.

Scope couvert ici :
  * Ollama : détection de l'exécutable, démarrage du serveur en arrière-plan
    (invisible, aucune console), chemin des modèles (OLLAMA_MODELS) pointé vers
    les données utilisateur (%USERPROFILE%\StudioIA\.ollama\models), libération
    de la RAM entre deux générations (OLLAMA_KEEP_ALIVE court), vérification et
    import des modèles (bundle ou pull).
  * FFmpeg : fonctions de vérification basées sur core/paths (déjà relativisé).

Les appels Ollama (brain, TTS, diagnostic) passent par core/ollama.py, qui
pointe vers le même host/port. Ce module est le seul à connaître l'exécutable,
les variables d'environnement et le dossier .ollama.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# CREATE_NO_WINDOW : ne jamais ouvrir de console pour les sous-processus.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Valeur par défaut : OLLAMA_KEEP_ALIVE court pour libérer la RAM entre les
# générations (objectif petits PC). Surchargé si déjà défini par l'utilisateur.
DEFAULT_KEEP_ALIVE = "1m"

# Modèles attendus (vérification / premier lancement).
MODELES_REQUIS = ["qwen2.5:7b", "mistral:latest"]


# ---------------------------------------------------------------------------
# Chemin des données Ollama (modèles) — isolé dans les données utilisateur
# ---------------------------------------------------------------------------
def ollama_models_dir():
    """Dossier des modèles Ollama. S'appuie sur core/paths (DATA_DIR).

    En mode installé : %USERPROFILE%\StudioIA\.ollama\models
    En mode source  : <racine_app>\.ollama\models (comportement inchangé).
    """
    from core import paths
    return paths.OLLAMA_DIR / "models"


def should_force_ollama_models():
    """Vrai si nous devons imposer notre OLLAMA_MODELS (mode installé).

    En mode source (développement) on se cale sur l'OLLAMA_MODELS existant de
    l'utilisateur s'il est défini ; sinon on propose le dossier isolé."""
    if os.environ.get("STUDIOIA_DATA_DIR", "").strip():
        return True
    return not os.environ.get("OLLAMA_MODELS", "").strip()


# ---------------------------------------------------------------------------
# Détection / installation
# ---------------------------------------------------------------------------
def detecter_executable():
    """Chemin de ollama(.exe) s'il est trouvé, sinon None.

    Ordre : variable OLLAMA_BIN → PATH → emplacements Windows usuels.
    """
    exe = os.environ.get("OLLAMA_BIN", "").strip()
    if exe:
        p = Path(exe)
        if p.exists():
            return str(p)

    # Les deux variantes de nom selon la plateforme.
    noms = ["ollama.exe"] if sys.platform == "win32" else ["ollama"]

    # 1) Dans le PATH.
    for nom in noms:
        p = shutil.which(nom)
        if p:
            return p

    # 2) Emplacements usuels (installateur NSIS : %LocalAppData%\Programs\Ollama).
    if sys.platform == "win32":
        candidats = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Ollama" / "ollama.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Ollama" / "ollama.exe",
            Path.home() / "AppData" / "Local" / "Ollama" / "ollama.exe",
        ]
        for c in candidats:
            if c.exists():
                return str(c)

    return None


def ollama_installe():
    """True si l'exécutable Ollama est présent."""
    return detecter_executable() is not None


def installer_ollama(setup_exe, silent=True):
    """Tente une installation silencieuse d'Ollama depuis l'installeur embarqué.

    Args:
        setup_exe: chemin de l'installeur Ollama (nsis, ex. OllamaSetup.exe).
        silent   : True → /S (silencieux), False → laisser l'installateur clicer.

    Returns:
        (ok: bool, message: str)
    """
    setup = Path(setup_exe)
    if not setup.exists():
        return False, f"Installeur Ollama introuvable : {setup}"
    try:
        cmd = [str(setup)]
        if silent:
            cmd.append("/S")
        subprocess.run(cmd, check=False, creationflags=CREATE_NO_WINDOW)
        # Après installation, l'exécutable devrait être détectable.
        if detecter_executable():
            return True, "Ollama installé"
        return False, "Installation terminée mais Ollama non détecté (redémarrage ?)"
    except Exception as e:
        return False, f"Échec installation Ollama : {e}"


# ---------------------------------------------------------------------------
# Démarrage du serveur
# ---------------------------------------------------------------------------
def serveur_actif():
    """Vrai si le serveur Ollama répond (cf. core/ollama)."""
    from core import ollama
    return ollama.test_connexion()


def demarrer_serveur(modeles_dir=None, keep_alive=DEFAULT_KEEP_ALIVE):
    """Lance `ollama serve` en arrière-plan (invisible) et attend qu'il réponde.

    Args:
        modeles_dir: dossier à utiliser comme OLLAMA_MODELS (None = défaut isolé).
        keep_alive  : OLLAMA_KEEP_ALIVE (None = ne pas l'imposer).

    Returns:
        (ok: bool, message: str)
    """
    from core import ollama
    if ollama.test_connexion():
        return True, "Ollama déjà actif"

    exe = detecter_executable()
    if not exe:
        return False, "Ollama n'est pas installé"

    env = dict(os.environ)
    # Pointer les modèles vers les données utilisateur (isolé de l'app).
    if should_force_ollama_models() or not env.get("OLLAMA_MODELS"):
        env["OLLAMA_MODELS"] = str(modeles_dir or ollama_models_dir())
    if keep_alive:
        env["OLLAMA_KEEP_ALIVE"] = keep_alive

    try:
        # CREATE_NO_WINDOW : aucune console.
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:
        return False, f"Impossible de lancer ollama serve : {e}"

    if ollama.attendre_serveur(timeout=25):
        return True, "Ollama démarré (modèles : " + env["OLLAMA_MODELS"] + ")"
    return False, "Ollama ne répond pas après lancement"


# ---------------------------------------------------------------------------
# Modèles : vérification, pull, import depuis le bundle
# ---------------------------------------------------------------------------
def modeles_manquants(requis=None):
    """Liste des modèles requis absents (via /api/tags).

    Returns:
        (manquants: list[str], presents: list[str])
    """
    from core import ollama
    requis = requis or MODELES_REQUIS
    presents = ollama.modeles_disponibles()
    manquants = []
    for nom in requis:
        if not any(p == nom or p.startswith(nom.split(":")[0] + ":") for p in presents):
            manquants.append(nom)
    return manquants, presents


def pull_modele(nom):
    """Télécharge un modèle manquant via `ollama pull` (génération du registre).

    Note : préférer l'import depuis le bundle quand il est disponible (plus
    rapide, aucun réseau). Ce repli sert si le bundle est absent ou obsolète.
    """
    exe = detecter_executable()
    if not exe:
        return False, "Ollama n'est pas installé"
    try:
        subprocess.run([exe, "pull", nom], check=False, creationflags=CREATE_NO_WINDOW)
        from core import ollama
        if ollama.modele_present(nom):
            return True, f"Modèle {nom} disponible"
        return False, f"Pull de {nom} terminé mais modèle non listé"
    except Exception as e:
        return False, f"Échec pull {nom} : {e}"


def importer_modele_depuis_bundle(nom, bundle_models_dir):
    """Importe un modèle depuis le bundle local (payload de l'installateur).

    L'installateur place les blobs+manifests (qwen2.5:7b, mistral) dans
    bundle-models/<model>. On les copie dans OLLAMA_MODELS (Ollama de préférence
    ARRÊTÉ pour éviter un conflit avec son registre interne).

    Returns: True si le modèle est ensuite visible via ollama list.
    """
    bundle = Path(bundle_models_dir) / nom
    target = ollama_models_dir()
    if not bundle.exists():
        return False
    try:
        target.mkdir(parents=True, exist_ok=True)
        for child in bundle.iterdir():
            dest = target / child.name
            if child.is_dir():
                shutil.copytree(str(child), str(dest), dirs_exist_ok=True)
            else:
                shutil.copy2(str(child), str(dest))
    except Exception as e:
        return False
    from core import ollama
    return ollama.modele_present(nom)


# ---------------------------------------------------------------------------
# FFmpeg
# ---------------------------------------------------------------------------
def ffmpeg_ok():
    """Vrai si les binaires FFmpeg embarqués existent."""
    from core import paths
    return paths.FFMPEG.exists() and paths.FFPROBE.exists()


# ---------------------------------------------------------------------------
# État global
# ---------------------------------------------------------------------------
def etat_services():
    """Résumé de l'état des services (pour le dashboard / /api).
    Renvoie une structure sérialisable."""
    from core import ollama
    actif = ollama.test_connexion()
    manquants, presents = modeles_manquants()
    return {
        "ollama": {
            "installe": ollama_installe(),
            "actif": actif,
            "exe": detecter_executable(),
            "modeles": presents,
            "modeles_manquants": manquants,
            "modeles_dir": str(ollama_models_dir()),
        },
        "ffmpeg": ffmpeg_ok(),
        "environnement": {
            "OLLAMA_MODELS": os.environ.get("OLLAMA_MODELS", ""),
            "OLLAMA_KEEP_ALIVE": os.environ.get("OLLAMA_KEEP_ALIVE", ""),
        },
    }