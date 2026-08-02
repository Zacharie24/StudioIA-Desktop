# -*- coding: utf-8 -*-
"""
youtube_stats.py — Analyseur de statistiques YouTube

Récupère les stats des chaînes et vidéos via l'API YouTube Data v3.
Fonctionne avec une simple API key (pas d'OAuth pour les lectures).

Configuration:
    Ajouter "youtube_api_key": "VOTRE_CLE" dans config.json
    La clé s'obtient gratuitement sur https://console.cloud.google.com/
"""

import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime, timedelta

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"


def log(msg):
    print(f"[YOUTUBE-STATS] {msg}")


def _lire_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def _api_key():
    """Retourne la clé API YouTube ou None"""
    config = _lire_config()
    return config.get("youtube_api_key") or os.environ.get("YOUTUBE_API_KEY")


def tester_connexion():
    """Vérifie si la clé API est valide"""
    cle = _api_key()
    if not cle:
        return False, "Aucune clé API configurée"
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet",
            "q": "test",
            "maxResults": 1,
            "key": cle
        }, timeout=10)
        if r.status_code == 200:
            return True, "Connexion OK"
        elif r.status_code == 403:
            return False, "Quota dépassé ou clé invalide"
        else:
            return False, f"Erreur {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return False, str(e)


def chercher_chaine(nom_chaine):
    """Cherche une chaîne YouTube par son nom"""
    cle = _api_key()
    if not cle:
        return None

    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet",
            "q": nom_chaine,
            "type": "channel",
            "maxResults": 1,
            "key": cle
        }, timeout=10)

        if r.status_code != 200:
            return None

        data = r.json()
        items = data.get("items", [])
        if not items:
            return None

        channel_id = items[0]["snippet"]["channelId"]
        return channel_id
    except Exception as e:
        log(f"Erreur recherche chaîne: {e}")
        return None


def stats_chaine(channel_id):
    """Récupère les statistiques d'une chaîne"""
    cle = _api_key()
    if not cle:
        return None

    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/channels", params={
            "part": "statistics,snippet",
            "id": channel_id,
            "key": cle
        }, timeout=10)

        if r.status_code != 200:
            return None

        data = r.json()
        items = data.get("items", [])
        if not items:
            return None

        item = items[0]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})

        return {
            "id": channel_id,
            "titre": snippet.get("title", ""),
            "description": snippet.get("description", "")[:200],
            "abonnes": int(stats.get("subscriberCount", 0)),
            "videos_total": int(stats.get("videoCount", 0)),
            "vues_total": int(stats.get("viewCount", 0)),
            "date_analyse": datetime.now().isoformat()
        }
    except Exception as e:
        log(f"Erreur stats chaîne: {e}")
        return None


def dernieres_videos(channel_id, max_results=10):
    """Récupère les dernières vidéos d'une chaîne"""
    cle = _api_key()
    if not cle:
        return []

    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet",
            "channelId": channel_id,
            "order": "date",
            "maxResults": max_results,
            "type": "video",
            "key": cle
        }, timeout=10)

        if r.status_code != 200:
            return []

        data = r.json()
        video_ids = [item["id"]["videoId"] for item in data.get("items", []) if item.get("id", {}).get("videoId")]

        if not video_ids:
            return []

        # Récupérer les stats détaillées
        r2 = requests.get("https://www.googleapis.com/youtube/v3/videos", params={
            "part": "statistics,snippet",
            "id": ",".join(video_ids),
            "key": cle
        }, timeout=10)

        if r2.status_code != 200:
            return []

        videos = []
        for item in r2.json().get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            vues = int(stats.get("viewCount", 0))
            likes = int(stats.get("likeCount", 0))
            commentaires = int(stats.get("commentCount", 0))

            videos.append({
                "id": item["id"],
                "titre": snippet.get("title", ""),
                "date_publication": snippet.get("publishedAt", ""),
                "vues": vues,
                "likes": likes,
                "commentaires": commentaires,
                "engagement": round((likes + commentaires) / max(vues, 1) * 100, 2),
                "duree_secondes": None,  # Nécessite contentDetails
            })

        # Trier par vues décroissantes
        videos.sort(key=lambda v: v["vues"], reverse=True)
        return videos
    except Exception as e:
        log(f"Erreur dernières vidéos: {e}")
        return []


def analyser_performances(channel_id, max_videos=20):
    """
    Analyse complète des performances d'une chaîne.

    Returns:
        dict: métriques, tendances, recommandations
    """
    chaine = stats_chaine(channel_id)
    if not chaine:
        return None

    videos = dernieres_videos(channel_id, max_videos)
    if not videos:
        return {
            "chaine": chaine,
            "videos": [],
            "moyennes": {},
            "meilleure": None,
            "pire": None,
            "tendance": "donnees_insuffisantes"
        }

    # Calculer les moyennes
    moyenne_vues = sum(v["vues"] for v in videos) / len(videos)
    moyenne_engagement = sum(v["engagement"] for v in videos) / len(videos)
    meilleure = max(videos, key=lambda v: v["vues"])
    pire = min(videos, key=lambda v: v["vues"])

    # Détection de tendance (comparer les 5 plus récentes vs les 5 avant)
    videos_chrono = sorted(videos, key=lambda v: v.get("date_publication", ""), reverse=True)
    recentes = videos_chrono[:5]
    anciennes = videos_chrono[5:10] if len(videos_chrono) > 5 else videos_chrono[:3]

    if recentes and anciennes:
        moyenne_recentes = sum(v["vues"] for v in recentes) / len(recentes)
        moyenne_anciennes = sum(v["vues"] for v in anciennes) / len(anciennes)
        if moyenne_recentes > moyenne_anciennes * 1.1:
            tendance = "hausse"
        elif moyenne_recentes < moyenne_anciennes * 0.9:
            tendance = "baisse"
        else:
            tendance = "stable"
    else:
        tendance = "donnees_insuffisantes"

    return {
        "chaine": chaine,
        "videos": videos[:10],
        "moyennes": {
            "vues": round(moyenne_vues, 0),
            "engagement_pct": round(moyenne_engagement, 2),
            "likes_par_video": round(sum(v["likes"] for v in videos) / len(videos), 0),
            "commentaires_par_video": round(sum(v["commentaires"] for v in videos) / len(videos), 0),
        },
        "meilleure": meilleure,
        "pire": pire,
        "tendance": tendance,
        "date_analyse": datetime.now().isoformat()
    }


if __name__ == "__main__":
    # Test
    ok, msg = tester_connexion()
    print(f"Connexion API: {msg}")
    if ok:
        print("Recherche de la chaîne...")
        cid = chercher_chaine("StudioIA")
        if cid:
            print(f"Channel ID: {cid}")
            perf = analyser_performances(cid)
            if perf:
                print(f"Chaîne: {perf['chaine']['titre']}")
                print(f"Abonnés: {perf['chaine']['abonnes']}")
                print(f"Vues totales: {perf['chaine']['vues_total']}")
                print(f"Tendance: {perf['tendance']}")
                print(f"Meilleure vidéo: {perf['meilleure']['titre']} ({perf['meilleure']['vues']} vues)")
