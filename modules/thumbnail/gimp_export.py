import json, os, sys, subprocess, shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

GIMP_PATHS = [
    "C:\\Program Files\\GIMP 3\\bin\\gimp-3.exe",
    "C:\\Program Files\\GIMP 2\\bin\\gimp-2.10.exe",
    "C:\\Program Files (x86)\\GIMP 2\\bin\\gimp-2.10.exe",
]

def log(msg):
    print(f"[GIMP-AUTO] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def trouver_gimp():
    for p in GIMP_PATHS:
        if os.path.exists(p):
            return p
    return None

def charger_police(taille, gras=True):
    fonts = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if gras else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if gras else "C:\\Windows\\Fonts\\calibri.ttf",
    ]
    for f in fonts:
        try:
            return ImageFont.truetype(f, taille)
        except:
            continue
    return ImageFont.load_default()

def creer_calques_png(project_path, projet_thumb):
    W, H   = 1280, 720
    titre  = projet_thumb.get("titre", "TITRE")
    verset = projet_thumb.get("verset", "")
    cta    = projet_thumb.get("cta", "")
    thumb_dir   = Path(project_path) / "thumbnail"
    calques_dir = thumb_dir / "calques"
    calques_dir.mkdir(exist_ok=True)

    # Fond
    shutil.copy(str(thumb_dir / "thumbnail.png"),
                str(calques_dir / "01_fond.png"))

    def calque(nom, fn):
        img = Image.new("RGBA", (W,H), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        fn(img, draw)
        img.save(str(calques_dir / nom))

    def draw_titre(img, draw):
        font = charger_police(80)
        mots = titre.split()
        lignes = [" ".join(mots[:len(mots)//2]), " ".join(mots[len(mots)//2:])] if len(mots) > 3 else [titre]
        y = 160
        for ligne in lignes:
            bbox = draw.textbbox((0,0), ligne, font=font)
            x = (W-(bbox[2]-bbox[0]))//2
            draw.text((x+2,y+2), ligne, font=font, fill=(0,0,0,180))
            draw.text((x,y), ligne, font=font, fill=(255,215,0,255))
            y += 100

    def draw_verset(img, draw):
        if not verset: return
        font = charger_police(26, gras=False)
        bbox = draw.textbbox((0,0), verset[:80], font=font)
        x = (W-(bbox[2]-bbox[0]))//2
        draw.text((x,380), verset[:80], font=font, fill=(255,255,255,255))

    def draw_cta(img, draw):
        if not cta: return
        font = charger_police(28)
        bbox = draw.textbbox((0,0), cta, font=font)
        tw = bbox[2]-bbox[0]
        x = (W-tw)//2
        draw.rounded_rectangle([x-12,488,x+tw+12,538], radius=8, fill=(255,180,0,200))
        draw.text((x,490), cta, font=font, fill=(255,255,255,255))

    def draw_ligne(img, draw):
        draw.line([(70,372),(W-70,372)], fill=(255,215,0,200), width=2)

    calque("02_titre.png",  draw_titre)
    calque("03_ligne.png",  draw_ligne)
    calque("04_verset.png", draw_verset)
    calque("05_cta.png",    draw_cta)

    log(f"5 calques PNG crees dans : {calques_dir}")
    return calques_dir

def ouvrir_gimp_avec_calques(project_path, calques_dir):
    gimp = trouver_gimp()
    if not gimp:
        log("GIMP non trouve sur cet ordinateur.")
        log("Installe GIMP depuis : https://www.gimp.org/downloads/")
        return False

    calques = sorted(Path(calques_dir).glob("*.png"))
    log(f"Ouverture GIMP avec {len(calques)} calques...")
    subprocess.Popen([gimp, "--no-splash"] + [str(c) for c in calques])
    log("GIMP ouvert !")
    log("Dans GIMP : Fichier → Ouvrir en calques → selectionne tous les PNG")
    return True

def main():
    project_path = sys.argv[1] if len(sys.argv) > 1 else str(paths.PROJECTS_DIR / "test_rapide")

    thumb_json = os.path.join(project_path, "thumbnail", "thumbnail.json")
    if not os.path.exists(thumb_json):
        log("Aucune thumbnail trouvee — lance d abord thumbnail_builder.py")
        sys.exit(1)

    projet_thumb = lire_json(thumb_json)
    log("Creation des calques PNG...")
    calques_dir = creer_calques_png(project_path, projet_thumb)
    ouvrir_gimp_avec_calques(project_path, calques_dir)

if __name__ == "__main__":
    main()