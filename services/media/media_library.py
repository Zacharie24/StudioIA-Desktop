# -*- coding: utf-8 -*-
"""
media_library.py — Bibliothèque Média Intelligente

Point d'entrée central pour la gestion des médias vidéo.

Fonctionnalités :
- Coordonne le téléchargement, le classement et la rotation
- Fournit une API simple pour le pipeline vidéo
- Gère les 4 modes visuels (images, vidéos, mix, intelligent)
- Assure la disponibilité des médias pour un projet

Utilisation dans le pipeline :
    from services.media.media_library import MediaLibrary

    lib = MediaLibrary()
    medias = lib.preparer_medias_pour_projet(
        sujet="Prière du soir",
        duree_secondes=1800,
        mode_visuel="intelligent"
    )
    # → {"backgrounds": [...], "videos": [...], "ambiance": {...}}
"""

import json
import os
import sys
import random
from pathlib import Path

from services.media.downloader import (
    approvisionner_theme, nettoyer_cache, VIDEOS_DIR, compter_videos_presentes
)
from services.media.classifier import (
    suggerer_themes_pour_sujet, determiner_ambiance_sujet
)
from services.media.rotation_manager import (
    choisir_video, filtrer_disponibles, enregistrer_utilisation,
    lister_par_theme, nettoyer_registre
)

# Dossier des images de fond existant
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"

# Nombre de vidéos minimum par thème
MIN_VIDEOS_PAR_THEME = 5


def log(msg):
    print(f"[MEDIA_LIBRARY] {msg}")


class MediaLibrary:
    """
    Bibliothèque média intelligente.

    Usage:
        lib = MediaLibrary()
        medias = lib.preparer_medias_pour_projet("Mon sujet", 600, "mix")
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.videos_dir = VIDEOS_DIR

    # ============================================================
    # API PUBLIQUE
    # ============================================================

    def preparer_medias_pour_projet(self, sujet, duree_secondes, mode_visuel="intelligent",
                                     langue="fr", projet_id=None):
        """
        Prépare les médias (images + vidéos) pour un projet vidéo

        Args:
            sujet: sujet de la vidéo
            duree_secondes: durée estimée en secondes
            mode_visuel: "images", "videos", "mix", "intelligent"
            langue: langue du projet
            projet_id: ID du projet (optionnel, pour le tracking)

        Returns:
            dict: {
                "mode": le mode utilisé,
                "images": liste des chemins d'images,
                "videos": liste des chemins de vidéos,
                "ambiance": paramètres d'ambiance visuelle,
                "ratio_images_videos": float (0=none, 1=tout vidéo)
            }
        """
        log(f"Préparation médias pour : {sujet}")
        log(f"Mode visuel : {mode_visuel}")

        # Déterminer l'ambiance du sujet
        ambiance = determiner_ambiance_sujet(sujet)
        log(f"Ambiance : {ambiance['rythme']} / {ambiance['luminosite']}")

        # Déterminer le ratio images/vidéos selon le mode
        ratio_videos = self._calculer_ratio_videos(mode_visuel, sujet, ambiance)

        # Suggérer des thèmes visuels
        suggestions = suggerer_themes_pour_sujet(sujet, langue, utiliser_ia=True)
        themes = suggestions["principaux"]
        log(f"Thèmes suggérés : {themes[:5]}")

        # S'assurer que les vidéos nécessaires sont disponibles
        videos_disponibles = self._approvisionner_si_besoin(themes)

        # Sélectionner les vidéos pour ce projet
        videos_choisies = self._selectionner_videos(
            themes, videos_disponibles, duree_secondes, ratio_videos,
            projet_id, ambiance
        )

        # Résultat
        resultat = {
            "mode": mode_visuel,
            "images": [],  # Rempli par le pipeline existant
            "videos": videos_choisies,
            "ambiance": ambiance,
            "ratio_images_videos": ratio_videos,
            "themes_visuels": themes[:5],
            "themes_francais": suggestions["francais"][:5]
        }

        log(f"Préparation terminée : {len(videos_choisies)} vidéos sélectionnées")
        return resultat

    def obtenir_stats(self):
        """Retourne les statistiques de la bibliothèque"""
        from services.media.rotation_manager import obtenir_statistiques
        stats = obtenir_statistiques()

        # Compter les vidéos par thème
        if self.videos_dir.exists():
            themes = [d for d in self.videos_dir.iterdir() if d.is_dir()]
            stats["themes"] = {
                d.name: len(list(d.glob("*.mp4")))
                for d in themes
            }
            stats["total_videos"] = sum(stats["themes"].values())

        return stats

    def nettoyer(self, limite_mo=500):
        """
        Nettoie la bibliothèque (cache + registre)
        """
        nettoyer_cache(limite_mo=limite_mo)
        nettoyer_registre()
        log("Nettoyage terminé")

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    def _calculer_ratio_videos(self, mode_visuel, sujet, ambiance):
        """
        Calcule le ratio images/vidéos selon le mode et l'ambiance

        Returns:
            float: 0.0 = 100% images, 1.0 = 100% vidéos
        """
        if mode_visuel == "images":
            return 0.0
        elif mode_visuel == "videos":
            return 1.0
        elif mode_visuel == "mix":
            return 0.5
        elif mode_visuel == "intelligent":
            # Le ratio dépend de l'ambiance
            ratios = {
                "lent": 0.7,       # Plus de vidéos pour les ambiances calmes
                "modere": 0.5,
                "dynamique": 0.3,  # Plus d'images pour les dynamiques
            }
            return ratios.get(ambiance["rythme"], 0.5)
        else:
            return 0.5

    def _approvisionner_si_besoin(self, themes, min_videos=MIN_VIDEOS_PAR_THEME):
        """
        Vérifie et approvisionne les thèmes nécessaires

        Args:
            themes: liste de mots-clés pour la recherche
            min_videos: nombre minimum de vidéos par thème

        Returns:
            dict: {theme: [liste des fichiers vidéo disponibles]}
        """
        disponibles = {}

        for mot_cle in themes[:5]:  # Limiter à 5 thèmes
            theme_dossier = mot_cle.split()[0].replace(" ", "_").lower()
            if not theme_dossier:
                continue

            # Vérifier le nombre de vidéos déjà présentes
            compte = compter_videos_presentes(theme_dossier)

            if compte < min_videos:
                log(f"Approvisionnement thème '{theme_dossier}' : {compte}/{min_videos}")
                approvisionner_theme(
                    theme_dossier,
                    [mot_cle],
                    nombre_min=min_videos
                )

            # Lister les vidéos disponibles
            videos = lister_par_theme(theme_dossier, self.videos_dir)
            disponibles[theme_dossier] = [str(v) for v in videos]
            log(f"Thème '{theme_dossier}' : {len(videos)} vidéos disponibles")

        return disponibles

    def _selectionner_videos(self, themes, videos_disponibles, duree_secondes,
                              ratio_videos, projet_id, ambiance):
        """
        Sélectionne les vidéos à utiliser pour un projet

        Args:
            themes: thèmes visuels suggérés
            videos_disponibles: dict {theme: [fichiers]}
            duree_secondes: durée de la vidéo
            ratio_videos: ratio vidéo souhaité
            projet_id: ID du projet
            ambiance: paramètres d'ambiance

        Returns:
            list: [{chemin, theme, duree_estimee, ...}]
        """
        if ratio_videos == 0.0:
            return []

        # Calculer le nombre de segments vidéo nécessaires
        # (estimation : un segment vidéo dure ~15 secondes en boucle)
        duree_segment = 15
        nombre_videos_max = max(1, int(duree_secondes / duree_segment * ratio_videos))

        # Rassembler toutes les vidéos disponibles
        toutes_videos = []
        for theme, fichiers in videos_disponibles.items():
            for f in fichiers:
                toutes_videos.append((f, theme))

        if not toutes_videos:
            log("Aucune vidéo disponible")
            return []

        # Filtrer les vidéos disponibles (hors refroidissement)
        disponibles = filtrer_disponibles([f for f, _ in toutes_videos])

        if not disponibles:
            log("Toutes les vidéos sont en refroidissement")
            # Prendre les moins utilisées
            disponibles = [f for f, _ in toutes_videos]

        # Adapter le nombre de vidéos à ce qu'on a
        nombre_videos = min(nombre_videos_max, len(disponibles))
        if nombre_videos == 0:
            nombre_videos = 1

        # Sélectionner les vidéos
        videos_selectionnees = []
        for i in range(nombre_videos):
            # Choisir une vidéo (stratégie : préférer les récentes)
            video = choisir_video(disponibles, preferer_recentes=True)
            if video is None:
                break

            # Enregistrer l'utilisation
            enregistrer_utilisation(
                video,
                theme=",".join(themes[:3]),
                projet_id=projet_id
            )

            videos_selectionnees.append({
                "chemin": video,
                "nom": Path(video).name,
                "theme": Path(video).parent.name,
                "duree_estimee": duree_segment,
                "index": i
            })

            # Retirer de la liste pour éviter les doublons
            if video in disponibles:
                disponibles.remove(video)

        log(f"{len(videos_selectionnees)} vidéos sélectionnées sur {nombre_videos_max} demandées")
        return videos_selectionnees


# ============================================================
# FONCTIONS DE RACCOURCI (usage simple)
# ============================================================

_lib_instance = None


def get_library(config=None):
    """Retourne l'instance unique de MediaLibrary (singleton)"""
    global _lib_instance
    if _lib_instance is None:
        _lib_instance = MediaLibrary(config)
    return _lib_instance


def preparer_medias(sujet, duree_secondes, mode_visuel="intelligent", langue="fr",
                    projet_id=None):
    """
    Fonction de raccourci pour préparer les médias

    Usage simple :
        from services.media.media_library import preparer_medias
        medias = preparer_medias("Prière du soir", 1800, "mix")
    """
    lib = get_library()
    return lib.preparer_medias_pour_projet(
        sujet, duree_secondes, mode_visuel, langue, projet_id
    )


if __name__ == "__main__":
    # Test
    lib = MediaLibrary()

    print("=== Test Media Library ===\n")

    # Test stats
    stats = lib.obtenir_stats()
    print(f"Statistiques : {json.dumps(stats, indent=2)}")

    # Test préparation
    sujets = [
        "Prière du soir pour dormir paisiblement",
        "Protection divine pour ma famille"
    ]

    for sujet in sujets[:1]:  # Un seul pour le test
        print(f"\n--- Test : {sujet} ---")
        medias = lib.preparer_medias_pour_projet(
            sujet=sujet,
            duree_secondes=600,
            mode_visuel="intelligent",
            projet_id="test_media_lib"
        )
        print(f"Mode : {medias['mode']}")
        print(f"Ratio vidéo : {medias['ratio_images_videos']}")
        print(f"Ambiance : {medias['ambiance']['rythme']} / {medias['ambiance']['luminosite']}")
        print(f"Vidéos : {len(medias['videos'])}")
        for v in medias['videos'][:3]:
            print(f"  - {v['nom']} (thème: {v['theme']})")

    # Nettoyage
    lib.nettoyer()
    print("\nTest terminé")
