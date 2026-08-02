import os, requests, shutil, sys
from pathlib import Path

# Fix pour imports relatifs quand exécuté directement
try:
    from .api_keys import PEXELS_KEY, UNSPLASH_KEY
except ImportError:
    parent_dir = Path(__file__).parent
    sys.path.insert(0, str(parent_dir))
    from api_keys import PEXELS_KEY, UNSPLASH_KEY

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

def log(msg):
    print(f"[ASSETS] {msg}")

FONTS_DIR  = str(paths.FONTS_DIR)
MUSIC_DIR  = str(paths.MUSIC_DIR)
BG_DIR     = str(paths.BACKGROUNDS_DIR)

# Polices gratuites Google Fonts (via GitHub - google/fonts)
# Format: nom -> liste de dossiers dans ofl/ pour cette police
POLICES = {
    "Cinzel":           ["ofl/cinzel", "Cinzel"],
    "Cormorant":        ["ofl/cormorantgaramond", "CormorantGaramant"],
    "Playfair":         ["ofl/playfairdisplay", "PlayfairDisplay"],
    "Montserrat":       ["ofl/montserrat", "Montserrat"],
    "Lora":             ["ofl/lora", "Lora"],
    "Oswald":           ["ofl/oswald", "Oswald"],
    "Raleway":          ["ofl/raleway", "Raleway"],
}

# Musiques de fond gratuites (Free Music Archive / ccMixter)
MUSIQUES = {
    "ambient_prayer_1": "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/no_curator/Kai_Engel/Satin/Kai_Engel_-_01_-_Satin.mp3",
    "ambient_calm_2":   "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/ccCommunity/Kai_Engel/Chapter_Two_-_White/Kai_Engel_-_01_-_Hope.mp3",
}

# Mots-cles images supplementaires
IMAGES_SUPP = {
    "divine_light":     "divine light rays heaven",
    "peaceful_nature":  "peaceful nature morning",
    "open_bible":       "open bible light",
    "church_worship":   "church worship praise",
    "sunset_prayer":    "sunset prayer silhouette",
}

# API keys imported from api_keys.py (lines 5-10)

def telecharger_polices():
    os.makedirs(FONTS_DIR, exist_ok=True)
    log("Telechargement polices Google Fonts...")
    for nom, paths in POLICES.items():
        font_dir = paths[0]  # Ex: "ofl/cinzel"
        font_name = paths[1]  # Ex: "Cinzel"
        dest_dir = os.path.join(FONTS_DIR, nom)
        if os.path.exists(dest_dir):
            log(f"  {nom} deja installe")
            continue
        try:
            log(f"  Telechargement {nom}...")
            # Obtenir la liste des fichiers via GitHub API
            api_url = f"https://api.github.com/repos/google/fonts/contents/{font_dir}"
            r = requests.get(api_url, timeout=30)
            data = r.json()

            # Télécharger les fichiers .ttf
            ttf_files = [f for f in data if f.get('name', '').endswith('.ttf')]
            if not ttf_files:
                log(f"  ECHEC {nom}: Aucun fichier .ttf trouvé")
                continue

            os.makedirs(dest_dir, exist_ok=True)
            downloaded = 0
            for file_info in ttf_files:
                download_url = file_info.get('download_url', '')
                if download_url:
                    try:
                        file_r = requests.get(download_url, timeout=30)
                        file_path = os.path.join(dest_dir, file_info['name'])
                        with open(file_path, "wb") as f:
                            f.write(file_r.content)
                        downloaded += 1
                    except:
                        pass

            if downloaded > 0:
                log(f"  OK : {nom} ({downloaded} fichiers)")
            else:
                log(f"  ECHEC {nom}: Aucun fichier téléchargé")
        except Exception as e:
            log(f"  ECHEC {nom} : {e}")

def telecharger_musiques():
    os.makedirs(MUSIC_DIR, exist_ok=True)
    log("Telechargement musiques de fond...")
    for nom, url in MUSIQUES.items():
        dest = os.path.join(MUSIC_DIR, f"{nom}.mp3")
        if os.path.exists(dest):
            log(f"  {nom} deja present")
            continue
        try:
            log(f"  Telechargement {nom}...")
            r = requests.get(url, timeout=60, stream=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            taille = os.path.getsize(dest) / 1024
            log(f"  OK : {nom} ({taille:.0f} KB)")
        except Exception as e:
            log(f"  ECHEC {nom} : {e}")

def telecharger_images_supp():
    os.makedirs(BG_DIR, exist_ok=True)
    log("Telechargement images supplementaires...")
    for nom, mot_cle in IMAGES_SUPP.items():
        dest = os.path.join(BG_DIR, f"global_{nom}.jpg")
        if os.path.exists(dest):
            log(f"  {nom} deja present")
            continue
        try:
            # Essai Pexels
            headers = {"Authorization": PEXELS_KEY}
            url = f"https://api.pexels.com/v1/search?query={mot_cle}&per_page=1&orientation=landscape"
            r = requests.get(url, headers=headers, timeout=15)
            data = r.json()
            if data.get("photos"):
                img_url = data["photos"][0]["src"]["large2x"]
                img_r = requests.get(img_url, timeout=30)
                with open(dest, "wb") as f:
                    f.write(img_r.content)
                log(f"  OK : {nom}")
            else:
                log(f"  ECHEC : {nom}")
        except Exception as e:
            log(f"  ECHEC {nom} : {e}")

def menu():
    print("\n  ================================")
    print("  GESTIONNAIRE D ASSETS")
    print("  ================================")
    print("  [1] Telecharger polices Google Fonts")
    print("  [2] Telecharger musiques de fond")
    print("  [3] Telecharger images supplementaires")
    print("  [4] Tout telecharger")
    print("  [5] Voir ce qui est installe")
    print("  [0] Quitter")

    choix = input("\n  Votre choix : ").strip()

    if choix == "1":
        telecharger_polices()
    elif choix == "2":
        telecharger_musiques()
    elif choix == "3":
        telecharger_images_supp()
    elif choix == "4":
        telecharger_polices()
        telecharger_musiques()
        telecharger_images_supp()
    elif choix == "5":
        print(f"\n  Polices   : {len(os.listdir(FONTS_DIR))} dossiers")
        print(f"  Musiques  : {len([f for f in os.listdir(MUSIC_DIR) if f.endswith('.mp3')])} fichiers")
        print(f"  Images    : {len([f for f in os.listdir(BG_DIR) if f.endswith('.jpg')])} fichiers")

if __name__ == "__main__":
    menu()