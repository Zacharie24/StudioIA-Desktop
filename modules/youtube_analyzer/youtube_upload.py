# -*- coding: utf-8 -*-
"""
youtube_upload.py — Upload YouTube automatise (OAuth 2.0)

Utilise OAuth 2.0 pour uploader des videos sur YouTube via l'API v3.

Configuration:
  1. Va sur https://console.cloud.google.com/
  2. Active YouTube Data API v3
  3. Cree un OAuth 2.0 Client ID (Desktop application)
  4. Telecharge le JSON et copie-le dans data/youtube_oauth/client_secret.json
  5. Lance auth_flow() pour generer le token
  6. Utilise upload_video() pour uploader

Le token est sauvegarde localement dans data/youtube_oauth/token.json
et est automatiquement rafraichi si necessaire.
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Isolement des chemins (Phase 9) : DATA_DIR = %USERPROFILE%\StudioIA en mode
# installe (via STUDIOIA_DATA_DIR), racine du projet en mode source. Repli sur
# l'ancien chemin si core.paths indisponible (compatibilite).
try:
    from core.paths import DATA_DIR
    CONFIG_PATH = DATA_DIR / "config.json"
    OAUTH_DIR = DATA_DIR / "data" / "youtube_oauth"
except Exception:
    CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"
    OAUTH_DIR = Path(__file__).parent.parent.parent / "data" / "youtube_oauth"
CLIENT_SECRET_PATH = OAUTH_DIR / "client_secret.json"
TOKEN_PATH = OAUTH_DIR / "token.json"


def log(msg):
    print(f"[YOUTUBE-UPLOAD] {msg}")


def _lire_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def client_secret_exists():
    """Verifie si le fichier client_secret.json est present"""
    return CLIENT_SECRET_PATH.exists()


def token_exists():
    """Verifie si le token OAuth est deja present"""
    if not TOKEN_PATH.exists():
        return False
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = json.load(f)
        # Verifier si le token est encore valide
        if token.get("expires_at", 0) > time.time():
            return True
        # Verifier si un refresh token est disponible
        if token.get("refresh_token"):
            return True
        return False
    except:
        return False


def auth_flow():
    """
    Lance le flux OAuth 2.0 pour obtenir un token YouTube.
    Necessite que l'utilisateur autorise dans le navigateur.

    Returns:
        bool: True si l'authentification a reussi
    """
    OAUTH_DIR.mkdir(parents=True, exist_ok=True)

    if not client_secret_exists():
        log("Fichier client_secret.json introuvable")
        log(f"Place le fichier dans: {CLIENT_SECRET_PATH}")
        log("""
1. Va sur https://console.cloud.google.com/
2. Cree un projet -> Active YouTube Data API v3
3. Dans Credentials -> Cree un OAuth 2.0 Client ID (type: Desktop app)
4. Telecharge le JSON et sauvegarde-le comme """)
        print(f"     {CLIENT_SECRET_PATH}")
        return False

    # Tenter d'utiliser google_auth_oauthlib si disponible
    try:
        _auth_flow_oauthlib()
        return True
    except ImportError:
        log("google_auth_oauthlib non installe, tentative avec le flux manuel...")
        pass

    # Fallback: flux manuel via l'API REST
    try:
        _auth_flow_manual()
        return True
    except Exception as e:
        log(f"Erreur authentification: {e}")
        return False


def _auth_flow_oauthlib():
    """Flux OAuth via google_auth_oauthlib (recommande)"""
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube"]

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    credentials = flow.run_local_server(port=0)

    token = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expiry.timestamp() if credentials.expiry else 0,
        "scopes": list(credentials.scopes)
    }

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)

    log("Authentification OAuth reussie !")
    return True


def _auth_flow_manual():
    """
    Flux OAuth manuel sans google_auth_oauthlib.
    Affiche l'URL d'autorisation pour que l'utilisateur la visite.
    """
    import requests

    with open(CLIENT_SECRET_PATH, "r", encoding="utf-8") as f:
        secret = json.load(f)

    client_id = secret.get("installed", {}).get("client_id", "")
    redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        "redirect_uri=urn:ietf:wg:oauth:2.0:oob&"
        "response_type=code&"
        "scope=https://www.googleapis.com/auth/youtube.upload"
    )

    print()
    print("=" * 60)
    print("AUTORISATION YOUTUBE REQUISE")
    print("=" * 60)
    print(f"1. Ouvre ce lien dans un navigateur:")
    print(f"   {auth_url}")
    print()
    code = input("2. Colle le code d'autorisation ici: ").strip()

    # Echange le code contre un token
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "client_secret": secret.get("installed", {}).get("client_secret", ""),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }, timeout=30)

    if r.status_code != 200:
        log(f"Erreur echange token: {r.text}")
        return False

    data = r.json()
    token = {
        "token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": time.time() + data.get("expires_in", 3600),
        "scopes": ["https://www.googleapis.com/auth/youtube.upload"]
    }

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)

    log("Token OAuth sauvegarde !")
    return True


def _refresh_token():
    """Rafraichit le token OAuth si necessaire"""
    if not TOKEN_PATH.exists():
        return False

    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = json.load(f)
    except:
        return False

    if token.get("expires_at", 0) > time.time():
        return True  # Encore valide

    if not token.get("refresh_token"):
        log("Pas de refresh token, necessite re-authentification")
        return False

    try:
        with open(CLIENT_SECRET_PATH, "r", encoding="utf-8") as f:
            secret = json.load(f)
    except:
        log("client_secret.json introuvable pour rafraichir le token")
        return False

    import requests
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": secret.get("installed", {}).get("client_id", ""),
        "client_secret": secret.get("installed", {}).get("client_secret", ""),
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token"
    }, timeout=30)

    if r.status_code != 200:
        log(f"Erreur refresh token: {r.text}")
        return False

    data = r.json()
    token["token"] = data["access_token"]
    token["expires_at"] = time.time() + data.get("expires_in", 3600)

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(token, f, ensure_ascii=False, indent=2)

    log("Token rafraichi")
    return True


def _get_access_token():
    """Retourne le access token actuel (valide)"""
    if not _refresh_token():
        return None

    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = json.load(f)
        return token.get("token")
    except:
        return None


def upload_video(chemin_video, titre, description="", categorie="22",
                 privacy_status="private", tags=None):
    """
    Uploade une video sur YouTube.

    Args:
        chemin_video: Chemin vers le fichier video
        titre: Titre de la video
        description: Description (peut contenir des sauts de ligne)
        categorie: ID categorie YouTube (22=People & Blogs, 28=Science, etc.)
        privacy_status: public / private / unlisted
        tags: Liste de mots-cles

    Returns:
        dict: Resultat avec video_id ou erreur
    """
    if not os.path.exists(chemin_video):
        return {"ok": False, "erreur": f"Fichier introuvable: {chemin_video}"}

    access_token = _get_access_token()
    if not access_token:
        return {"ok": False, "erreur": "Authentification OAuth requise. Lance auth_flow() d'abord."}

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError

        credentials = _build_credentials(access_token)
        youtube = build("youtube", "v3", credentials=credentials)

        body = {
            "snippet": {
                "title": titre[:100],
                "description": description[:5000],
                "categoryId": categorie,
                "tags": tags[:20] if tags else []
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        log(f"Upload: {titre[:50]}...")
        media = MediaFileUpload(chemin_video, chunksize=1024*1024,
                                resumable=True)

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = request.execute()
        video_id = response.get("id")

        log(f"Upload reussi ! Video ID: {video_id}")
        return {
            "ok": True,
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "titre": titre
        }

    except ImportError:
        # Fallback: upload via requete HTTP directe
        return _upload_video_http(chemin_video, titre, description,
                                  categorie, privacy_status, tags, access_token)
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def _build_credentials(access_token):
    """Cree un objet credentials a partir du token"""
    from google.oauth2.credentials import Credentials
    return Credentials(token=access_token)


def _upload_video_http(chemin_video, titre, description, categorie,
                       privacy_status, tags, access_token):
    """
    Upload via HTTP direct (sans googleapiclient).
    Necessite le module requests et un fichier video < 50MB.
    """
    import requests

    log("Upload via HTTP direct...")

    # 1: Creer la ressource video
    body = {
        "snippet": {
            "title": titre[:100],
            "description": description[:5000],
            "categoryId": categorie,
            "tags": tags[:20] if tags else []
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    # Upload en 2 etapes: d'abord creer la ressource, puis uploader le media
    # Note: cette methode simplifiee fonctionne pour les petits fichiers
    upload_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    r = requests.post(upload_url, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        return {"ok": False, "erreur": f"Erreur creation ressource: {r.status_code} {r.text}"}

    upload_endpoint = r.headers.get("Location", "")
    if not upload_endpoint:
        return {"ok": False, "erreur": "Pas d'endpoint d'upload dans la reponse"}

    # Uploader le fichier video
    file_size = os.path.getsize(chemin_video)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "video/*",
        "Content-Length": str(file_size)
    }

    with open(chemin_video, "rb") as f:
        r = requests.put(upload_endpoint, headers=headers, data=f, timeout=600)

    if r.status_code in (200, 201):
        data = r.json()
        video_id = data.get("id")
        return {
            "ok": True,
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "titre": titre
        }
    else:
        return {"ok": False, "erreur": f"Erreur upload: {r.status_code} {r.text}"}


def lister_videos_chaine(channel_id=None, max_results=10):
    """Liste les dernieres videos de la chaine authentifiee"""
    access_token = _get_access_token()
    if not access_token:
        return {"ok": False, "erreur": "Authentification requise"}

    try:
        from googleapiclient.discovery import build
        credentials = _build_credentials(access_token)
        youtube = build("youtube", "v3", credentials=credentials)

        if channel_id:
            request = youtube.search().list(
                part="snippet",
                channelId=channel_id,
                order="date",
                maxResults=max_results
            )
        else:
            request = youtube.channels().list(
                part="contentDetails",
                mine=True
            )
            response = request.execute()
            if not response.get("items"):
                return {"ok": False, "erreur": "Aucune chaine trouvee"}
            uploads = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            request = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads,
                maxResults=max_results
            )

        response = request.execute()
        videos = []
        for item in response.get("items", []):
            video_id = item.get("snippet", {}).get("resourceId", {}).get("videoId") or item.get("id", {}).get("videoId")
            videos.append({
                "id": video_id,
                "titre": item.get("snippet", {}).get("title", "?"),
                "publiee_le": item.get("snippet", {}).get("publishedAt", "")
            })

        return {"ok": True, "videos": videos}

    except ImportError:
        return {"ok": False, "erreur": "googleapiclient non installe"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)}


def statut_auth():
    """Retourne le statut de l'authentification OAuth"""
    if not client_secret_exists():
        return {
            "configured": False,
            "etape": "client_secret_manquant",
            "message": "client_secret.json manquant"
        }

    if not token_exists():
        return {
            "configured": False,
            "etape": "token_manquant",
            "message": "Token OAuth manquant — lance auth_flow()"
        }

    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = json.load(f)
        valide = token.get("expires_at", 0) > time.time()
        refresh = bool(token.get("refresh_token"))
        return {
            "configured": True,
            "token_valide": valide,
            "refresh_token_present": refresh,
            "message": "Authentification OK" if valide else "Token expire, refresh disponible" if refresh else "Token expire, necessite re-authentification"
        }
    except:
        return {"configured": False, "etape": "token_invalide", "message": "Token corrompu"}


if __name__ == "__main__":
    import json
    print(json.dumps(statut_auth(), ensure_ascii=False, indent=2))
    if not client_secret_exists():
        print(f"\nPlace client_secret.json dans:\n  {CLIENT_SECRET_PATH}")
