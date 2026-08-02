# -*- coding: utf-8 -*-
"""
core/capabilities.py — Profil auto "petit PC" pour StudioIA Desktop.

Objectif (Phase 7) : détecter les capacités réelles de la machine (mémoire
RAM, CPU, GPU) et en déduire un profil d'utilisation qui préserve la fluidité
sur les machines modestes (CPU seul, peu de RAM) sans sacrifier la qualité sur
les machines puissantes.

Imports matériels (psutil, GPUtil) chargés PAresseusement pour ne pas ralentir
le démarrage. Ce module ne modifie rien lui-même : il renvoie des
recommandations que l'appelant applique (config, assistant, runtime).

Profils :
  'puissant' — RAM >= 16 Go ET >= 6 cœurs  → 1080p, XTTS, low_resource=false
  'moyen'    — 8 Go <= RAM < 16 Go          → 720p,  Edge, low_resource=true
  'petit'    — RAM < 8 Go ou <= 4 cœurs     → 720p,  Edge, low_resource=true
"""

# ---------------------------------------------------------------------------
# Seuils (ajustables ; calibrés pour un petit PC dans l'esprit du projet).
# ---------------------------------------------------------------------------
_RAM_PUISSANT_GO = 16.0     # mémoire totale (Go) pour le profil "puissant"
_RAM_PETIT_GO = 8.0         # mémoire totale (Go) sous laquelle on passe "petit"
_MIN_CORES_PUISSANT = 8     # cœurs logiques requis pour "puissant"
_MIN_CORES_PETIT = 4        # cœurs logiques sous lesquels on force "petit"


# ---------------------------------------------------------------------------
# Détection matérielle (paresseuse et tolérante aux pannes)
# ---------------------------------------------------------------------------
def memoire_ram_go():
    """Mémoire RAM totale en Go (ou None si non mesurable)."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        return None


def nombre_coeurs():
    """Nombre de cœurs logiques (ou None si non mesurable)."""
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except Exception:
        return None


def detecter_gpu():
    """Nom du premier GPU dédié via GPUtil, sinon None (léger, tolérant)."""
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            return gpus[0].name
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------
def detecter_profil():
    """Profil matériel ('puissant' | 'moyen' | 'petit').

    Repli sûr : si la détection échoue, on part du principe que la machine est
    modeste ('petit') — le choix le plus sûr pour la fluidité.
    """
    ram = memoire_ram_go()
    cores = nombre_coeurs()

    if ram is None or cores is None:
        return "petit"  # pas de mesure : hypothèse prudente

    if ram >= _RAM_PUISSANT_GO and cores >= _MIN_CORES_PUISSANT:
        return "puissant"
    if ram < _RAM_PETIT_GO or cores < _MIN_CORES_PETIT:
        return "petit"
    return "moyen"


# ---------------------------------------------------------------------------
# Réglages recommandés par profil
# ---------------------------------------------------------------------------
RESOLUTIONS = {
    "puissant": "1920x1080",
    "moyen": "1280x720",
    "petit": "1280x720",
}

# Voix TTS : "3" = Edge Henri (léger, cloud) ; "1"/"2" = XTTS (lourd, venv).
VOIX_TTS = {
    "puissant": "2",   # XTTS Vwa Soft — qualité maximale
    "moyen": "3",      # Edge Henri — bon compromis (pas de charge locale)
    "petit": "3",      # Edge Henri — zéro charge locale
}


def recommandations(profil=None):
    """Réglages recommandés pour le profil matériel détecté.

    Args:
        profil: force un profil ('puissant'|'moyen'|'petit'), sinon autodétecté.

    Returns:
        dict avec 'profil', 'video_resolution', 'tts_voix', 'low_resource',
        'mode_visuel' + le diagnostic matériel brute (ram_go, coeurs, gpu).
    """
    profil = profil or detecter_profil()
    return {
        "profil": profil,
        "video_resolution": RESOLUTIONS.get(profil, "1280x720"),
        "tts_voix": VOIX_TTS.get(profil, "3"),
        "low_resource": profil != "puissant",
        "mode_visuel": "images" if profil == "petit" else "intelligent",
        "ram_go": memoire_ram_go(),
        "coeurs": nombre_coeurs(),
        "gpu": detecter_gpu(),
    }


# ---------------------------------------------------------------------------
# API web (état) — lecture seule pour le dashboard / l'assistant
# ---------------------------------------------------------------------------
def etat():
    """Résumé sérialisable pour le dashboard / assistant (/setup)."""
    rec = recommandations()
    return {
        "profil": rec["profil"],
        "video_resolution": rec["video_resolution"],
        "tts_voix": rec["tts_voix"],
        "low_resource": rec["low_resource"],
        "mode_visuel": rec["mode_visuel"],
        "ram_go": rec["ram_go"],
        "coeurs": rec["coeurs"],
        "gpu": rec["gpu"],
        "contexte": ("machine détectée comme : "
                     + _decrire(rec["profil"])),
    }


def _decrire(profil):
    return {
        "puissant": "moderne",
        "moyen": "confortable",
        "petit": "modeste (réglages allégés)",
    }.get(profil, "modeste")