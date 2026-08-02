import json, os, sys, requests, re
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

def log(msg):
    print(f"[NOM] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generer_nom_court(sujet, langue="fr"):
    try:
        sys.path.insert(0, str(paths.MODULES_DIR / "brain"))
        from model_selector import choisir_meilleur_modele
        modele = choisir_meilleur_modele()
    except:
        modele = "mistral"

    if langue == "fr":
        prompt = f"""Pour une video YouTube sur : "{sujet}"
Genere un nom de dossier court en francais.
Maximum 4 mots, sans accents, sans espaces (utilise des underscores).
Exemple : priere_protection_divine
UNIQUEMENT le nom, rien d autre."""
    else:
        prompt = f"""For a YouTube video about: "{sujet}"
Generate a short folder name in English.
Maximum 4 words, no spaces (use underscores).
Example: divine_protection_prayer
ONLY the name, nothing else."""

    try:
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": modele,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        })
        nom = r.json()["response"].strip().lower()
        nom = re.sub(r'[^a-z0-9_]', '_', nom)
        nom = re.sub(r'_+', '_', nom).strip('_')
        return nom[:40]
    except:
        return re.sub(r'[^a-z0-9_]', '_', sujet.lower())[:40]

def renommer_projet(project_path):
    pjson = os.path.join(project_path, "project.json")
    if not os.path.exists(pjson):
        return project_path

    data = lire_json(pjson)
    sujet = data.get("sujet", "")
    langue = data.get("langue", "fr")
    id_actuel = data.get("id", "")

    if not sujet:
        return project_path

    # Generer nom court
    nom_court = generer_nom_court(sujet, langue)
    log(f"Nom genere : {nom_court}")

    # Nouveau chemin
    parent = str(Path(project_path).parent)
    nouveau_path = os.path.join(parent, nom_court)

    # Eviter les doublons
    if os.path.exists(nouveau_path) and nouveau_path != project_path:
        nouveau_path = nouveau_path + "_2"

    # Renommer le dossier
    if nouveau_path != project_path:
        os.rename(project_path, nouveau_path)
        log(f"Dossier renomme : {id_actuel} → {nom_court}")

        # Mettre a jour project.json
        pjson_nouveau = os.path.join(nouveau_path, "project.json")
        data["id"] = nom_court
        data["nom_lisible"] = nom_court.replace("_", " ").title()
        ecrire_json(pjson_nouveau, data)

        return nouveau_path
    return project_path

def main():
    project_path = sys.argv[1]
    nouveau_path = renommer_projet(project_path)
    log(f"Projet : {nouveau_path}")

if __name__ == "__main__":
    main()