"""
Utilitaires d'optimisation pour ordinateurs faibles
StudioIA - Optimisation mémoire et CPU
"""

import gc
import sys

def nettoyer_memoire():
    """
    Force le nettoyage de la mémoire et libère les objets non utilisés
    À appeler après chaque étape importante
    """
    gc.collect()
    # Force le garbage collector Python
    for _ in range(3):
        collected = gc.collect()
        if collected == 0:
            break
    return True

def reduire_resolution_image(img, max_dimension=1024):
    """
    Réduit la taille d'une image si elle dépasse max_dimension
    Utile pour économiser la mémoire sur des images 4K
    """
    from PIL import Image

    w, h = img.size
    if max(w, h) <= max_dimension:
        return img

    ratio = max_dimension / max(w, h)
    new_w = int(w * ratio)
    new_h = int(h * ratio)

    # Utiliser LANCZOS pour Pillow >=9, BILINEAR pour compatibilité
    resize_method = getattr(Image, 'LANCZOS', Image.BILINEAR)
    return img.resize((new_w, new_h), resize_method)

def limiter_threads_ia(max_threads=2):
    """
    Réduit le nombre de threads utilisés par les modèles IA
    à exécuter AVANT l'import des bibliothèques IA
    """
    try:
        import os
        # Limitation pour numpy
        os.environ.setdefault("OMP_NUM_THREADS", str(max_threads))
        os.environ.setdefault("OPENBLAS_NUM_THREADS", str(max_threads))
        os.environ.setdefault("MKL_NUM_THREADS", str(max_threads))
        os.environ.setdefault("VECLIB_MAXIMUM_THREADS", str(max_threads))
        os.environ.setdefault("NUMEXPR_NUM_THREADS", str(max_threads))
    except Exception:
        pass

def chunker(liste, taille_chunk):
    """
    Divise une liste en chunks de taille définie
    Permet de traiter les éléments par lots
    """
    for i in range(0, len(liste), taille_chunk):
        yield liste[i:i + taille_chunk]

def est_memoire_basse(seuil_percent=85):
    """
    Vérifie si la mémoire disponible est en dessous du seuil
    Retourne True si la mémoire est faible
    """
    try:
        import psutil
        memoire = psutil.virtual_memory()
        return memoire.available < (memoire.total * seuil_percent / 100)
    except Exception:
        return False

def get_taille_memoire_disponible():
    """
    Retourne la mémoire disponible en MB
    """
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 * 1024)
    except Exception:
        return 0

def optimiser_chargement_fichiers(liste_fichiers, taille_chunk=10):
    """
    Génère un itérateur qui charge les fichiers par lots
    """
    for chunk in chunker(liste_fichiers, taille_chunk):
        yield chunk
