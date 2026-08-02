import json, os, sys, requests, subprocess
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

PENPOT_URL = "http://localhost:9001"
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

def log(msg):
    print(f"[PENPOT] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def get_credentials():
    creds_path = str(paths.chemin_app("tools", "penpot", "credentials.json"))
    if os.path.exists(creds_path):
        c = lire_json(creds_path)
        return c.get("email",""), c.get("password","")
    email = input("  Email Penpot : ").strip()
    pwd   = input("  Mot de passe : ").strip()
    with open(creds_path, "w") as f:
        json.dump({"email": email, "password": pwd}, f)
    return email, pwd

def login(email, pwd):
    r = requests.post(f"{PENPOT_URL}/api/rpc/command/login-with-password",
        json={"email": email, "password": pwd}, headers=HEADERS)
    if r.status_code == 200:
        log("Connexion OK")
        return r.cookies
    log(f"Erreur login : {r.status_code}")
    return None

def get_team(cookies):
    r = requests.get(f"{PENPOT_URL}/api/rpc/command/get-teams",
        cookies=cookies, headers=HEADERS)
    if r.status_code == 200:
        teams = r.json()
        if isinstance(teams, list) and teams:
            return teams[0]["id"]
    return None

def create_project(cookies, team_id, nom):
    r = requests.post(f"{PENPOT_URL}/api/rpc/command/create-project",
        json={"team-id": team_id, "name": nom},
        cookies=cookies, headers=HEADERS)
    if r.status_code == 200:
        return r.json()["id"]
    log(f"Erreur projet : {r.status_code}")
    return None

def create_file(cookies, project_id, nom, projet_thumb):
    W, H = 1280, 720
    titre  = projet_thumb.get("titre", "TITRE")
    verset = projet_thumb.get("verset", "")
    cta    = projet_thumb.get("cta", "")

    file_data = {
        "project-id": project_id,
        "name": nom,
        "is-shared": False,
        "data": {
            "version": 23,
            "pages-index": {
                "page1": {
                    "id": "page1",
                    "name": "Thumbnail",
                    "objects": {
                        "root": {
                            "id": "root",
                            "type": "frame",
                            "name": f"Thumbnail {W}x{H}",
                            "x": 0, "y": 0,
                            "width": W, "height": H,
                            "fills": [{"fill-color": "#0a0510", "fill-opacity": 1}],
                            "shapes": ["titre_obj","verset_obj","cta_obj"]
                        },
                        "titre_obj": {
                            "id": "titre_obj",
                            "type": "text",
                            "name": "Titre",
                            "x": 70, "y": 180,
                            "width": W-140, "height": 200,
                            "content": {
                                "type": "root",
                                "children": [{"type": "paragraph",
                                    "align": "center",
                                    "children": [{"text": titre,
                                        "fontSize": "80",
                                        "fontWeight": "700",
                                        "fills": [{"fill-color": "#FFD700",
                                                   "fill-opacity": 1}]}]
                                }]
                            }
                        },
                        "verset_obj": {
                            "id": "verset_obj",
                            "type": "text",
                            "name": "Verset",
                            "x": 70, "y": 400,
                            "width": W-140, "height": 80,
                            "content": {
                                "type": "root",
                                "children": [{"type": "paragraph",
                                    "align": "center",
                                    "children": [{"text": verset,
                                        "fontSize": "26",
                                        "fontWeight": "400",
                                        "fills": [{"fill-color": "#FFFFFF",
                                                   "fill-opacity": 0.9}]}]
                                }]
                            }
                        },
                        "cta_obj": {
                            "id": "cta_obj",
                            "type": "text",
                            "name": "Call to Action",
                            "x": 70, "y": 520,
                            "width": W-140, "height": 60,
                            "content": {
                                "type": "root",
                                "children": [{"type": "paragraph",
                                    "align": "center",
                                    "children": [{"text": cta,
                                        "fontSize": "28",
                                        "fontWeight": "700",
                                        "fills": [{"fill-color": "#FFD700",
                                                   "fill-opacity": 1}]}]
                                }]
                            }
                        }
                    },
                    "options": {}
                }
            },
            "pages": ["page1"]
        }
    }

    r = requests.post(f"{PENPOT_URL}/api/rpc/command/create-file",
        json=file_data, cookies=cookies, headers=HEADERS)
    if r.status_code == 200:
        return r.json()["id"]
    log(f"Erreur fichier : {r.status_code} {r.text[:300]}")
    return None

def ouvrir_penpot(project_id, file_id):
    url = f"{PENPOT_URL}/view/{project_id}/{file_id}"
    log(f"Ouverture : {url}")
    subprocess.Popen(["cmd", "/c", "start", url], shell=True)

def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else str(paths.PROJECTS_DIR / "test_rapide")

    thumb_json = os.path.join(project_path, "thumbnail", "thumbnail.json")
    pjson      = os.path.join(project_path, "project.json")

    if not os.path.exists(thumb_json):
        log("Aucune thumbnail trouvee.")
        sys.exit(1)

    projet_thumb = lire_json(thumb_json)
    data         = lire_json(pjson)
    sujet        = data.get("sujet", "Projet")

    log(f"Sujet : {sujet}")

    email, pwd = get_credentials()
    cookies    = login(email, pwd)
    if not cookies:
        sys.exit(1)

    team_id = get_team(cookies)
    if not team_id:
        log("Equipe introuvable.")
        sys.exit(1)
    log(f"Equipe : {team_id}")

    log("Creation projet...")
    project_id = create_project(cookies, team_id, f"StudioIA - {sujet}")
    if not project_id:
        sys.exit(1)
    log(f"Projet cree : {project_id}")

    log("Creation fichier thumbnail...")
    file_id = create_file(cookies, project_id, f"Thumbnail - {sujet}", projet_thumb)
    if not file_id:
        sys.exit(1)
    log(f"Fichier cree : {file_id}")

    ouvrir_penpot(project_id, file_id)
    log("Penpot ouvert ! Tu peux modifier ta thumbnail librement.")

if __name__ == "__main__":
    main()