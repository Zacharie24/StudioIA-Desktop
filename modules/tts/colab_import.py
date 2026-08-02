import json, os, sys, zipfile, shutil, time
from pathlib import Path

def log(msg):
    print(f"[COLAB-IMPORT] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def trouver_zip_recent(downloads_dir, nom_pattern="audio_complet"):
    downloads = Path(downloads_dir)
    if not downloads.exists():
        return None

    candidats = list(downloads.glob(f"*{nom_pattern}*.zip"))
    if not candidats:
        return None

    # Le plus recent
    plus_recent = max(candidats, key=lambda p: p.stat().st_mtime)

    # Verifier qu'il a ete telecharge il y a moins de 30 minutes
    age_minutes = (time.time() - plus_recent.stat().st_mtime) / 60
    if age_minutes > 30:
        log(f"ZIP trouve mais trop ancien ({age_minutes:.0f} min) : {plus_recent.name}")
        return None

    return plus_recent

def importer_audio(project_path, zip_path):
    audio_dir = Path(project_path) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    log(f"Extraction de : {zip_path.name}")

    temp_extract = Path(project_path) / "temp_colab" / "extracted"
    temp_extract.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(zip_path), 'r') as z:
        z.extractall(str(temp_extract))

    fichiers_copies = 0
    for wav_file in temp_extract.glob("*.wav"):
        dest = audio_dir / wav_file.name
        shutil.copy(str(wav_file), str(dest))
        log(f"Copie : {wav_file.name}")
        fichiers_copies += 1

    # Nettoyage
    shutil.rmtree(str(temp_extract), ignore_errors=True)

    return fichiers_copies

def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not project_path:
        log("Chemin projet manquant.")
        sys.exit(1)

    downloads_dir = str(Path.home() / "Downloads")

    log("Recherche du ZIP audio recent dans Downloads...")
    zip_path = trouver_zip_recent(downloads_dir)

    if not zip_path:
        log("Aucun ZIP audio_complet.zip trouve recemment.")
        log(f"Verifie qu'il est bien dans : {downloads_dir}")
        manuel = input("Chemin manuel du ZIP (ou Entree pour annuler) : ").strip()
        if not manuel or not os.path.exists(manuel):
            log("Annule.")
            sys.exit(1)
        zip_path = Path(manuel)

    log(f"ZIP trouve : {zip_path}")

    nb_fichiers = importer_audio(project_path, zip_path)
    log(f"{nb_fichiers} fichiers audio importes !")

    # Mettre a jour project.json
    pjson = os.path.join(project_path, "project.json")
    data = lire_json(pjson)

    chapitres = data.get("chapitres", [])
    audio_dir = Path(project_path) / "audio"
    for ch in chapitres:
        wav_path = audio_dir / f"{ch['id']}.wav"
        if wav_path.exists():
            ch["statut_tts"] = "termine"

    data["etapes"]["audio"] = "termine"
    ecrire_json(pjson, data)

    log("Statut projet mis a jour : audio termine.")
    log("Tu peux maintenant lancer le module video !")

    # Proposer de supprimer le ZIP de Downloads pour faire le menage
    nettoyer = input("\nSupprimer le ZIP de Downloads ? (o/n) : ").strip()
    if nettoyer == "o":
        try:
            os.remove(str(zip_path))
            log("ZIP supprime de Downloads.")
        except Exception as e:
            log(f"Impossible de supprimer : {e}")

if __name__ == "__main__":
    main()