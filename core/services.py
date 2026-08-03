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

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# CREATE_NO_WINDOW : ne jamais ouvrir de console pour les sous-processus.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Valeur par défaut : OLLAMA_KEEP_ALIVE court pour libérer la RAM entre les
# générations (objectif petits PC). Surchargé si déjà défini par l'utilisateur.
DEFAULT_KEEP_ALIVE = "1m"

# Modèles attendus (vérification / premier lancement).
MODELES_REQUIS = ["qwen2.5:7b", "mistral:latest"]

# Installeur Ollama officiel (NSIS). Téléchargé à la demande si Ollama absent.
OLLAMA_SETUP_URL = "https://ollama.com/download/OllamaSetup.exe"

# ---------------------------------------------------------------------------
# Tâche de préparation (1er lancement) — état global lu par /api/setup/…
# Un seul processus à la fois (préparation complète OU installation d'un modèle
# supplémentaire). Imite le pattern de core/importer.ETAT.
# ---------------------------------------------------------------------------
TACHE = {
    "actif": False,
    "termine": False,
    "etape": "",          # ollama | modeles | modele_extra | xtts
    "message": "",
    "progres": 0.0,       # 0..100 pour la préparation complète
    "rapport": "",
    "erreur": None,
}


def _humain(octets):
    """Formate une taille en Go/Mo/Ko lisible."""
    for unite, div in (("Go", 1 << 30), ("Mo", 1 << 20), ("Ko", 1 << 10)):
        if octets >= div:
            return f"{octets/div:.1f} {unite}"
    return f"{octets} o"


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
# Téléchargement + préparation automatisée (1er lancement)
# ---------------------------------------------------------------------------
def _telecharger(url, dest, tache=None, debut_pct=0, fin_pct=100):
    """Télécharge url vers dest (flux), en mettant à jour tache['progres'].

    Écrit d'abord un fichier .part puis le renomme : jamais de fichier
    tronqué si le téléchargement est interrompu.
    """
    import requests
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0) or 0)
        ok = 0
        with open(tmp, "wb") as f:
            for bloc in r.iter_content(chunk_size=256 * 1024):
                if not bloc:
                    continue
                f.write(bloc)
                ok += len(bloc)
                if tache is not None:
                    if total:
                        tache["progres"] = round(debut_pct + (fin_pct - debut_pct) * ok / total, 1)
                    tache["message"] = f"Téléchargement… {_humain(ok)} / {_humain(total)}"
    tmp.replace(dest)
    if tache is not None:
        tache["progres"] = round(fin_pct, 1)
    return dest


def _pull_modele_progressif(nom, tache, debut_pct, fin_pct):
    """`ollama pull nom` en lisant sa sortie JSON (progression réelle).

    Ollama émet des lignes JSON sur stdout quand il n'est pas sur un TTY :
      {"status":"downloading","completed":N,"total":M,...}
      {"status":"success",...}
    On mappe la progression sur [debut_pct, fin_pct] de la tâche globale.
    """
    exe = detecter_executable()
    if not exe:
        return False
    try:
        proc = subprocess.Popen(
            [exe, "pull", nom],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
        for ligne in proc.stdout:
            ligne = ligne.strip()
            if not ligne:
                continue
            try:
                j = json.loads(ligne)
            except Exception:
                continue  # ligne non-JSON (rare), on ignore
            status = j.get("status", "")
            if status == "downloading":
                comp = j.get("completed", 0)
                tot = j.get("total", 0)
                tache["message"] = f"{nom} : téléchargement {_humain(comp)} / {_humain(tot)}"
                if tot:
                    tache["progres"] = round(
                        debut_pct + (fin_pct - debut_pct) * min(comp / tot, 1.0), 1)
            elif status == "success":
                tache["message"] = f"{nom} installé."
        proc.wait()
        from core import ollama
        return ollama.modele_present(nom)
    except Exception:
        return False


def preparer(modeles=None):
    """Lance la préparation complète du 1er lancement, en arrière-plan :
    Ollama (installé si absent) + démarrage + modèles requis (bundle sinon
    pull avec progression). Ne touche jamais à ce qui est déjà présent.

    Stratégie « les deux combinés » : si le payload modèles est présent
    (bundle-models/), on l'importe localement (0 réseau) ; sinon on
    télécharge depuis le registre Ollama.
    """
    import threading
    if TACHE["actif"]:
        return {"ok": False, "message": "Une préparation est déjà en cours."}
    threading.Thread(target=_executer_preparation, args=(modeles,), daemon=True).start()
    return {"ok": True, "message": "Préparation lancée en arrière-plan."}


def _executer_preparation(modeles):
    from core import paths, ollama
    modeles = modeles or MODELES_REQUIS
    TACHE.update({"actif": True, "termine": False, "erreur": None, "rapport": "",
                  "etape": "ollama", "message": "Vérification d'Ollama…", "progres": 0})
    t0 = time.time()
    try:
        # 1) Ollama — installé silencieusement si absent (téléchargement officiel).
        if not ollama_installe():
            TACHE["message"] = "Ollama absent — téléchargement de l'installeur (~700 Mo)…"
            setup = _telecharger(OLLAMA_SETUP_URL,
                                 paths.chemin_data("temp", "OllamaSetup.exe"),
                                 TACHE, 0, 25)
            TACHE["message"] = "Installation d'Ollama…"
            ok, msg = installer_ollama(setup)
            if not ok:
                raise RuntimeError(msg)
        TACHE["progres"] = 35
        ok, msg = demarrer_serveur()
        if not ok:
            raise RuntimeError(msg)
        TACHE["progres"] = 40

        # 2) Modèles requis — bundle si présent, sinon pull (progression).
        TACHE["etape"] = "modeles"
        manquants, _ = modeles_manquants(modeles)
        bundle = paths.RACINE_APP / "bundle-models"
        if manquants:
            part = 60.0 / len(manquants)
            for i, nom in enumerate(manquants):
                base = 40 + i * part
                TACHE["message"] = f"Préparation du modèle {nom}…"
                if bundle.exists() and importer_modele_depuis_bundle(nom, str(bundle)):
                    TACHE["message"] = f"{nom} importé du bundle (sans réseau)."
                    TACHE["progres"] = round(base + part, 1)
                    continue
                if not _pull_modele_progressif(nom, TACHE, base, base + part):
                    raise RuntimeError(f"Impossible d'installer le modèle {nom}")
                TACHE["progres"] = round(base + part, 1)
        else:
            TACHE["message"] = "Modèles déjà présents."

        TACHE["progres"] = 100
        TACHE["rapport"] = (
            f"Préparation terminée en {int(time.time() - t0)} s : "
            f"Ollama actif, {len(ollama.modeles_disponibles())} modèle(s) installé(s)."
        )
        TACHE["message"] = "Préparation terminée."
    except Exception as e:
        TACHE["erreur"] = str(e)
        TACHE["message"] = f"Préparation interrompue : {e}"
    finally:
        TACHE["actif"] = False
        TACHE["termine"] = True
    return dict(TACHE)


def installer_modele(nom):
    """Installe un modèle supplémentaire (plus puissant, à la demande) en fond."""
    import threading
    nom = (nom or "").strip()
    if not nom:
        return {"ok": False, "message": "Nom de modèle manquant"}
    if TACHE["actif"]:
        return {"ok": False, "message": "Une préparation est déjà en cours."}
    threading.Thread(target=_executer_installation_modele, args=(nom,), daemon=True).start()
    return {"ok": True, "message": f"Installation de {nom} lancée en arrière-plan."}


def _executer_installation_modele(nom):
    from core import ollama
    TACHE.update({"actif": True, "termine": False, "erreur": None, "rapport": "",
                  "etape": "modele_extra", "message": f"Installation de {nom}…", "progres": 0})
    try:
        if ollama.modele_present(nom):
            TACHE["message"] = f"{nom} déjà présent."
            TACHE["progres"] = 100
        else:
            ok, msg = demarrer_serveur()
            if not ok:
                raise RuntimeError(msg)
            if not _pull_modele_progressif(nom, TACHE, 0, 100):
                raise RuntimeError(f"Échec de l'installation de {nom}")
            TACHE["progres"] = 100
            TACHE["message"] = f"{nom} installé."
        TACHE["rapport"] = f"{nom} prêt."
    except Exception as e:
        TACHE["erreur"] = str(e)
        TACHE["message"] = f"Installation interrompue : {e}"
    finally:
        TACHE["actif"] = False
        TACHE["termine"] = True
    return dict(TACHE)


# ---------------------------------------------------------------------------
# XTTS (voix optionnelle) — détection + import d'un pack local
# ---------------------------------------------------------------------------
def xtts_ok():
    """True si le pack XTTS est utilisable (venv présent)."""
    from core import paths
    return paths.tts_venv_python() is not None


def importer_pack_xtts(source):
    """Copie un pack XTTS local (ex. StudioIA-XTTS, C:\\tts-pentest) vers
    DATA_DIR\\xtts, que l'app détecte alors automatiquement. Copie seule."""
    from core import paths
    src = Path(source)
    if not (src / "venv" / "Scripts" / "python.exe").exists():
        return False, "Pack invalide : pas de venv\\Scripts\\python.exe à la source"
    if src.resolve() == paths.XTTS_DIR.resolve():
        return False, "Ce dossier est déjà la destination"
    try:
        dst = paths.XTTS_DIR
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
        if xtts_ok():
            return True, f"Pack XTTS importé dans {dst}"
        return False, "Pack copié mais non détecté par l'app (venv\\Scripts\\python.exe absent ?)"
    except Exception as e:
        return False, f"Échec de l'import XTTS : {e}"


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