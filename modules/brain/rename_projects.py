import json, os, sys, requests, re, shutil
from pathlib import Path

def log(msg):
    print(f"[NOM] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generer_nom(sujet, langue="fr"):
    try:
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": "mistral",
            "prompt": f"""Sujet : "{sujet}"
Genere un nom de dossier court en {'francais' if langue == 'fr' else 'anglais'}.
Maximum 4 mots, sans accents, sans espaces, utilise underscores, minuscules.
Exemple : priere_protection_divine
UNIQUEMENT le nom, rien d autre.""",
            "stream": False,
            "options": {"temperature": 0.3}
        })
        nom = r.json()["response"].strip().lower()
        nom = re.sub(r'[^a-z0-9_]', '_', nom)
        nom = re.sub(r'_+', '_', nom).strip('_')
        return nom[:35]
    except:
        return re.sub(r'[^a-z0-9_]', '_', sujet.lower())[:35]

def renommer_tous_projets(projects_path):
    projets = list(Path(projects_path).iterdir())
    for p in projets:
        if not p.is_dir():
            continue
        pjson = p / "project.json"
        if not pjson.exists():
            continue
        data = lire_json(str(pjson))
        sujet = data.get("sujet", "")
        id_actuel = data.get("id", p.name)

        # Sauter si deja renomme (pas le format video_XXXXXXXX)
        if not re.match(r'^video_\d{8}_\d{6}$', p.name) and not re.match(r'^video_\d+$', p.name):
            log(f"Deja renomme : {p.name}")
            continue

        if not sujet:
            log(f"Pas de sujet : {p.name}")
            continue

        langue = data.get("langue", "fr")
        nom_court = generer_nom(sujet, langue)
        log(f"Renommage : {p.name} → {nom_court}")

        nouveau_path = p.parent / nom_court

        # Eviter doublons
        compteur = 1
        while nouveau_path.exists() and nouveau_path != p:
            nouveau_path = p.parent / f"{nom_court}_{compteur}"
            compteur += 1

        if nouveau_path != p:
            p.rename(nouveau_path)
            # Mettre a jour project.json
            pjson_new = nouveau_path / "project.json"
            data["id"] = nom_court
            data["nom_lisible"] = nom_court.replace("_", " ").title()
            ecrire_json(str(pjson_new), data)
            log(f"OK : {nouveau_path.name}")
        else:
            log(f"Deja bon : {p.name}")

def main():
    projects_path = "C:\\StudioIA\\projects"
    if len(sys.argv) > 1:
        projects_path = sys.argv[1]
    log(f"Renommage de tous les projets dans : {projects_path}")
    renommer_tous_projets(projects_path)
    log("Renommage termine !")

if __name__ == "__main__":
    main()