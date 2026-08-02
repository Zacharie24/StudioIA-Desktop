import json, os, sys, zipfile, shutil
from pathlib import Path

def log(msg):
    print(f"[COLAB-EXPORT] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def creer_zip_chapitres(project_path):
    ch_dir = Path(project_path) / "chapters"
    if not ch_dir.exists():
        log("Aucun dossier chapters trouve.")
        return None

    zip_path = Path(project_path) / "temp_colab" / "chapitres.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(zip_path), 'w') as z:
        for f in ch_dir.glob("*.txt"):
            z.write(str(f), f.name)

    log(f"ZIP cree : {zip_path}")
    return str(zip_path)

def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not project_path:
        log("Chemin projet manquant.")
        sys.exit(1)

    pjson = os.path.join(project_path, "project.json")
    data = lire_json(pjson)

    log(f"Projet : {data['sujet']}")
    log("Preparation export vers Colab...")

    zip_path = creer_zip_chapitres(project_path)
    if not zip_path:
        sys.exit(1)

    # Ouvrir le dossier contenant le ZIP pour faciliter l'upload
    import subprocess
    subprocess.Popen(["explorer.exe", "/select,", zip_path.replace("/", "\\")])

    print("")
    print("=" * 50)
    print("  PRET POUR COLAB")
    print("=" * 50)
    print(f"  Fichier ZIP : {zip_path}")
    print("")
    print("  ETAPES SUIVANTES :")
    print("  1. Ouvre ton notebook Google Colab")
    print("  2. Execute : pipeline_complet()")
    print("  3. Quand demande, uploade ce fichier ZIP")
    print("  4. Attends la generation")
    print("  5. Le ZIP audio sera telecharge automatiquement")
    print("  6. Reviens ici et lance le module d import")
    print("=" * 50)

    data["etapes"]["audio"] = "en_attente_colab"
    ecrire_json(pjson, data)

if __name__ == "__main__":
    main()