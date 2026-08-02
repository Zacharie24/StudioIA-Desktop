# -*- coding: utf-8 -*-
"""
downloader.py — Téléchargement de vidéos libres de droits

Sources :
- Pexels Video API (clé API existante)
- Pixabay Video API (fallback gratuit)

Fonctionnalités :
- Téléchargement par mot-clé avec cache
- Sélection aléatoire parmi les résultats
- Fallback automatique entre sources
- Limitation de bande passante (fichier max 50 Mo)
"""

import json
import os
import sys
import requests
import random
import time
from pathlib import Path

# Chemins
MODULES_DIR = Path(__file__).parent.parent.parent / "modules"
sys.path.insert(0, str(MODULES_DIR))

try:
    from api_keys import PEXELS_KEY
except ImportError:
    PEXELS_KEY = ""

# Clé Pixabay (optionnelle) — laisser vide pour désactiver Pixabay
PIXABAY_KEY = os.environ.get("PIXABAY_KEY", "")

# Dossier de destination des vidéos
VIDEOS_DIR = Path(__file__).parent.parent.parent / "assets" / "videos"

# Taille maximale par vidéo (50 Mo)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Timeout
TIMEOUT = 30

# Nombre max de vidéos par thème
MAX_VIDEOS_PER_THEME = 20


def log(msg):
    print(f"[MEDIA_DOWNLOADER] {msg}")


def s_assurer_dossier(theme):
    """Crée le dossier pour un thème si nécessaire"""
    dossier = VIDEOS_DIR / theme
    dossier.mkdir(parents=True, exist_ok=True)
    return dossier


def compter_videos_presentes(theme):
    """Retourne le nombre de vidéos déjà téléchargées pour un thème"""
    dossier = VIDEOS_DIR / theme
    if not dossier.exists():
        return 0
    return len(list(dossier.glob("*.mp4")))


def telecharger_fichier(url, dest_path):
    """
    Télécharge un fichier avec vérification de taille
    Retourne True si réussi, False sinon
    """
    try:
        r = requests.get(url, stream=True, timeout=TIMEOUT)
        r.raise_for_status()

        # Vérifier la taille avant de télécharger
        content_length = int(r.headers.get("content-length", 0))
        if content_length > MAX_FILE_SIZE:
            log(f"Fichier trop volumineux ({content_length//1024//1024} Mo) : {url}")
            return False

        # Télécharger
        taille_telechargee = 0
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    taille_telechargee += len(chunk)
                    if taille_telechargee > MAX_FILE_SIZE:
                        log(f"Téléchargement dépassé la limite, annulé")
                        os.remove(dest_path)
                        return False

        return True
    except requests.exceptions.RequestException as e:
        log(f"Erreur téléchargement : {e}")
        return False
    except Exception as e:
        log(f"Erreur inattendue : {e}")
        return False


def telecharger_pexels(mot_cle, dest_path, orientation="landscape"):
    """
    Télécharge une vidéo depuis Pexels Video API
    Documentation : https://www.pexels.com/api/documentation/#videos-search
    """
    if not PEXELS_KEY:
        log("Clé Pexels manquante")
        return False

    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={mot_cle}&per_page=15&orientation={orientation}"

    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()

        videos = data.get("videos", [])
        if not videos:
            log(f"Aucune vidéo trouvée pour : {mot_cle}")
            return False

        # Sélectionner une vidéo aléatoire
        video = random.choice(videos)

        # Chercher le meilleur fichier (qualité moyenne pour équilibre taille/qualité)
        fichiers = video.get("video_files", [])
        fichier_choisi = None

        # Priorité : qualité moyenne (hd) ou la première dispo
        for f in fichiers:
            qualité = f.get("quality", "")
            if qualité in ("hd", "sd") and f.get("width", 0) <= 1920:
                fichier_choisi = f
                break

        if not fichier_choisi and fichiers:
            fichier_choisi = fichiers[0]

        if not fichier_choisi or not fichier_choisi.get("link"):
            log(f"Aucun fichier vidéo trouvé pour : {mot_cle}")
            return False

        video_url = fichier_choisi["link"]
        log(f"Téléchargement Pexels : {mot_cle} ({fichier_choisi.get('quality', '?')})")

        return telecharger_fichier(video_url, dest_path)

    except requests.exceptions.RequestException as e:
        log(f"Pexels erreur ({mot_cle}): {e}")
        return False
    except json.JSONDecodeError:
        log(f"Pexels réponse invalide ({mot_cle})")
        return False
    except Exception as e:
        log(f"Pexels erreur inattendue ({mot_cle}): {e}")
        return False


def telecharger_pixabay(mot_cle, dest_path, orientation="horizontal"):
    """
    Télécharge une vidéo depuis Pixabay Video API (fallback gratuit)
    Documentation : https://pixabay.com/api/videos/
    """
    key = PIXABAY_KEY
    if not key:
        log("Pixabay non configuré (clé manquante), passage à Pexels uniquement")
        return False
    url = f"https://pixabay.com/api/videos/?key={key}&q={mot_cle}&per_page=10&orientation={orientation}"

    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()

        hits = data.get("hits", [])
        if not hits:
            log(f"Aucune vidéo Pixabay pour : {mot_cle}")
            return False

        # Sélection aléatoire
        hit = random.choice(hits)

        # Chercher une vidéo de taille moyenne (large ou medium)
        videos = hit.get("videos", {})
        fichier_choisi = None

        for qualité in ("large", "medium", "small"):
            if qualité in videos and videos[qualité].get("url"):
                fichier_choisi = videos[qualité]
                break

        if not fichier_choisi or not fichier_choisi.get("url"):
            log(f"Aucune vidéo trouvée dans la réponse Pixabay")
            return False

        video_url = fichier_choisi["url"]
        largeur = fichier_choisi.get("width", 0)
        log(f"Téléchargement Pixabay : {mot_cle} ({largeur}px)")

        return telecharger_fichier(video_url, dest_path)

    except requests.exceptions.RequestException as e:
        # Silencieux pour les erreurs Pixabay (fallback normal)
        if "400" in str(e):
            log(f"Pixabay mot-clé invalide: {mot_cle}")
        else:
            log(f"Pixabay erreur ({mot_cle}): {e}")
        return False
    except Exception as e:
        log(f"Pixabay erreur inattendue ({mot_cle}): {e}")
        return False


def telecharger_video(mot_cle, dest_path, source="aleatoire", orientation="landscape"):
    """
    Télécharge une vidéo depuis n'importe quelle source disponible
    Avec fallback : Pexels → Pixabay → échec
    """
    sources = ["pexels", "pixabay"] if source == "aleatoire" else [source]
    random.shuffle(sources)

    for src in sources:
        if src == "pexels":
            if telecharger_pexels(mot_cle, dest_path, orientation):
                return True
        elif src == "pixabay":
            if telecharger_pixabay(mot_cle, dest_path, orientation):
                return True

    return False


def approvisionner_theme(theme, mots_cles, nombre_min=5):
    """
    Télécharge des vidéos pour un thème jusqu'à atteindre nombre_min
    Utilise plusieurs mots-clés pour enrichir le thème

    Args:
        theme: nom du dossier (ex: "nature", "ocean")
        mots_cles: liste de mots-clés en anglais pour la recherche
        nombre_min: nombre minimum de vidéos souhaité

    Returns:
        int: nombre de vidéos téléchargées
    """
    dossier = s_assurer_dossier(theme)
    deja_present = compter_videos_presentes(theme)

    if deja_present >= nombre_min:
        log(f"Thème '{theme}' déjà suffisant ({deja_present} vidéos)")
        return 0

    besoin = min(nombre_min - deja_present, MAX_VIDEOS_PER_THEME - deja_present)
    if besoin <= 0:
        return 0

    log(f"Approvisionnement thème '{theme}' : besoin de {besoin} vidéos")
    telechargees = 0
    tentatives = 0
    max_tentatives = besoin * 3  # Pour éviter les boucles infinies

    while telechargees < besoin and tentatives < max_tentatives:
        mot_cle = random.choice(mots_cles)
        # Ajouter un suffixe aléatoire pour varier les résultats
        suffixes = ["", "nature", "calm", "beautiful", "scenic", "peaceful"]
        mot_recherche = mot_cle
        if random.random() > 0.5:
            mot_recherche = f"{mot_cle} {random.choice(suffixes)}"

        nom_fichier = f"{theme}_{telechargees}_{int(time.time())}.mp4"
        dest = dossier / nom_fichier

        if dest.exists():
            tentatives += 1
            continue

        ok = telecharger_video(mot_recherche, str(dest))
        if ok:
            telechargees += 1
            log(f"  [{telechargees}/{besoin}] {mot_recherche}")
        else:
            log(f"  Échec : {mot_recherche}")

        tentatives += 1
        # Pause pour éviter de saturer l'API
        time.sleep(0.5)

    log(f"Thème '{theme}' : {telechargees} nouvelles vidéos (total: {deja_present + telechargees})")
    return telechargees


def nettoyer_cache(theme=None, limite_mo=500):
    """
    Nettoie les vidéos les moins utilisées si le dossier dépasse la limite

    Args:
        theme: thème spécifique ou None pour tout
        limite_mo: limite en mégaoctets
    """
    if theme:
        dossiers = [VIDEOS_DIR / theme]
    else:
        dossiers = [d for d in VIDEOS_DIR.iterdir() if d.is_dir()]

    total_octets = 0
    fichiers_par_theme = []

    for dossier in dossiers:
        if not dossier.exists():
            continue
        videos = list(dossier.glob("*.mp4"))
        for v in videos:
            taille = v.stat().st_size
            total_octets += taille
            fichiers_par_theme.append((v, taille, v.stat().st_mtime))

    limite_octets = limite_mo * 1024 * 1024
    if total_octets <= limite_octets:
        log(f"Cache sous la limite ({total_octets//1024//1024}/{limite_mo} Mo)")
        return

    # Trier par date (plus ancien en premier)
    fichiers_par_theme.sort(key=lambda x: x[2])

    a_supprimer = total_octets - limite_octets
    supprime = 0
    for fichier, taille, _ in fichiers_par_theme:
        if supprime >= a_supprimer:
            break
        try:
            os.remove(str(fichier))
            supprime += taille
            log(f"Nettoyage : {fichier.name}")
        except OSError:
            continue

    log(f"Nettoyage terminé : {supprime//1024//1024} Mo libérés")


if __name__ == "__main__":
    # Test rapide
    theme_test = "nature"
    approvisionner_theme(theme_test, ["forest", "river", "sunset", "trees"], 2)
    nettoyer_cache()
