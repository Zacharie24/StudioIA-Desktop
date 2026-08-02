# -*- coding: utf-8 -*-
"""
rotation_manager.py — Gestionnaire de rotation des vidéos

Fonctionnalités :
- Suivi de l'utilisation de chaque vidéo (date, nombre d'utilisations)
- Période de "refroidissement" avant réutilisation
- Sélection intelligente : privilégie les vidéos fraîches et variées
- Nettoyage automatique du registre (vidéos supprimées)
"""

import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

# Fichier de registre (SQLite à terme, JSON pour l'instant)
REGISTRE_PATH = Path(__file__).parent.parent.parent / "data" / "media_registry.json"

# Période de refroidissement par défaut (en jours)
COOLDOWN_DAYS = 7

# Nombre maximum d'utilisations avant pause prolongée
MAX_USAGE_BEFORE_LONG_COOLDOWN = 3
LONG_COOLDOWN_DAYS = 30


def log(msg):
    print(f"[ROTATION] {msg}")


def _charger_registre():
    """Charge le registre d'utilisation des vidéos"""
    if REGISTRE_PATH.exists():
        try:
            with open(REGISTRE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"videos": {}, "dernier_nettoyage": None}


def _sauvegarder_registre(registre):
    """Sauvegarde le registre"""
    REGISTRE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRE_PATH, "w", encoding="utf-8") as f:
        json.dump(registre, f, ensure_ascii=False, indent=2)


def enregistrer_utilisation(fichier_video, theme=None, projet_id=None):
    """
    Enregistre l'utilisation d'une vidéo

    Args:
        fichier_video: chemin absolu ou relatif de la vidéo
        theme: thème associé (optionnel)
        projet_id: ID du projet qui a utilisé la vidéo
    """
    registre = _charger_registre()
    videos = registre["videos"]
    fichier = str(fichier_video)

    if fichier not in videos:
        videos[fichier] = {
            "premiere_utilisation": datetime.now().isoformat(),
            "derniere_utilisation": datetime.now().isoformat(),
            "nombre_utilisations": 0,
            "themes": [],
            "projets": []
        }

    entry = videos[fichier]
    entry["derniere_utilisation"] = datetime.now().isoformat()
    entry["nombre_utilisations"] += 1

    if theme and theme not in entry["themes"]:
        entry["themes"].append(theme)

    if projet_id and projet_id not in entry["projets"]:
        entry["projets"].append(projet_id)

    _sauvegarder_registre(registre)


def est_disponible(fichier_video, cooldown_days=COOLDOWN_DAYS):
    """
    Vérifie si une vidéo est disponible (hors période de refroidissement)

    Args:
        fichier_video: chemin de la vidéo
        cooldown_days: nombre de jours de pause

    Returns:
        bool: True si la vidéo peut être utilisée
    """
    registre = _charger_registre()
    fichier = str(fichier_video)

    # Si la vidéo n'a jamais été utilisée → disponible
    if fichier not in registre["videos"]:
        return True

    entry = registre["videos"][fichier]

    # Vérifier si le fichier existe toujours
    if not os.path.exists(fichier):
        # Nettoyer l'entrée obsolète
        del registre["videos"][fichier]
        _sauvegarder_registre(registre)
        return False

    # Calculer le temps depuis la dernière utilisation
    derniere_utilisation = datetime.fromisoformat(entry["derniere_utilisation"])
    jours_depuis = (datetime.now() - derniere_utilisation).days

    # Si utilisée trop souvent → pause longue
    if entry["nombre_utilisations"] >= MAX_USAGE_BEFORE_LONG_COOLDOWN:
        return jours_depuis >= LONG_COOLDOWN_DAYS

    # Pause normale
    return jours_depuis >= cooldown_days


def filtrer_disponibles(liste_fichiers, cooldown_days=COOLDOWN_DAYS):
    """
    Filtre une liste de fichiers pour ne garder que les disponibles

    Args:
        liste_fichiers: liste de chemins de vidéos
        cooldown_days: période de refroidissement

    Returns:
        list: fichiers disponibles
    """
    return [f for f in liste_fichiers if est_disponible(f, cooldown_days)]


def choisir_video(liste_fichiers, cooldown_days=COOLDOWN_DAYS, preferer_recentes=False):
    """
    Choisit intelligemment une vidéo parmi une liste

    Stratégie :
    1. Priorité aux vidéos jamais utilisées
    2. Puis aux vidéos hors refroidissement
    3. Si preferer_recentes=True, privilégie les vidéos récemment téléchargées
    4. Sinon, sélection aléatoire parmi les disponibles

    Args:
        liste_fichiers: liste de chemins de vidéos
        cooldown_days: période de refroidissement
        preferer_recentes: privilégier les vidéos récentes

    Returns:
        str: chemin de la vidéo choisie, ou None si aucune disponible
    """
    if not liste_fichiers:
        return None

    # Séparer les jamais utilisées et les disponibles
    jamais_utilisees = []
    disponibles = []

    for f in liste_fichiers:
        if not os.path.exists(f):
            continue
        if est_disponible(f, cooldown_days):
            registre = _charger_registre()
            if str(f) not in registre["videos"]:
                jamais_utilisees.append(f)
            else:
                disponibles.append(f)

    # Stratégie : jamais utilisées d'abord
    if jamais_utilisees:
        if preferer_recentes:
            # Prendre la plus récente (par date de modification)
            jamais_utilisees.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            return jamais_utilisees[0]
        return random.choice(jamais_utilisees)

    # Puis les disponibles
    if disponibles:
        return random.choice(disponibles)

    # Aucune disponible → forcer la moins utilisée
    if liste_fichiers:
        registre = _charger_registre()
        archive = [(f, registre["videos"].get(str(f), {}).get("nombre_utilisations", 0))
                   for f in liste_fichiers if os.path.exists(f)]
        if archive:
            archive.sort(key=lambda x: x[1])
            log(f"Aucune disponible, forcing : {Path(archive[0][0]).name}")
            return archive[0][0]

    return None


def lister_par_theme(theme, dossier_videos=None):
    """
    Liste toutes les vidéos disponibles pour un thème

    Args:
        theme: nom du thème (dossier)
        dossier_videos: chemin du dossier racine des vidéos

    Returns:
        list: chemins des fichiers vidéo
    """
    if dossier_videos is None:
        dossier_videos = Path(__file__).parent.parent.parent / "assets" / "videos"

    dossier_theme = Path(dossier_videos) / theme
    if not dossier_theme.exists():
        return []

    return sorted(dossier_theme.glob("*.mp4"))


def obtenir_statistiques():
    """
    Retourne des statistiques sur la bibliothèque vidéo

    Returns:
        dict: statistiques
    """
    registre = _charger_registre()
    videos = registre["videos"]

    total = len(videos)
    utilisees_recemment = sum(
        1 for v in videos.values()
        if (datetime.now() - datetime.fromisoformat(v["derniere_utilisation"])).days <= COOLDOWN_DAYS
    )
    jamais_utilisees = sum(1 for v in videos.values() if v["nombre_utilisations"] == 0)
    tres_utilisees = sum(1 for v in videos.values() if v["nombre_utilisations"] >= MAX_USAGE_BEFORE_LONG_COOLDOWN)

    return {
        "total_enregistrees": total,
        "utilisees_recemment": utilisees_recemment,
        "jamais_utilisees": jamais_utilisees,
        "en_pause_longue": tres_utilisees
    }


def nettoyer_registre():
    """
    Nettoie le registre des entrées orphelines (fichiers supprimés)
    """
    registre = _charger_registre()
    videos = registre["videos"]
    a_supprimer = []

    for fichier in videos:
        if not os.path.exists(fichier):
            a_supprimer.append(fichier)

    for fichier in a_supprimer:
        del videos[fichier]
        log(f"Entrée orpheline supprimée : {fichier}")

    registre["dernier_nettoyage"] = datetime.now().isoformat()
    _sauvegarder_registre(registre)

    if a_supprimer:
        log(f"Nettoyage : {len(a_supprimer)} entrées supprimées")

    return len(a_supprimer)


if __name__ == "__main__":
    # Test
    from pathlib import Path
    import tempfile

    # Créer un fichier test
    test_dir = Path(tempfile.gettempdir()) / "studioia_test_rotation"
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / "test_video.mp4"
    test_file.write_text("fake video content")

    print("=== Test Rotation Manager ===")

    # Test disponibilité (jamais utilisée → True)
    dispo = est_disponible(str(test_file))
    print(f"Jamais utilisée : disponible = {dispo}")

    # Test enregistrement
    enregistrer_utilisation(str(test_file), theme="nature", projet_id="test_projet")
    print(f"Après 1ère utilisation")

    # Test indisponibilité juste après
    dispo = est_disponible(str(test_file), cooldown_days=30)  # cooldown long
    print(f"Juste utilisée (cooldown 30j) : disponible = {dispo}")

    # Nettoyage
    os.remove(str(test_file))
    nettoyer_registre()
    print("Test terminé")
