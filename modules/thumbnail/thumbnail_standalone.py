import json, os, sys, requests, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Fix pour imports relatifs quand exécuté directement
try:
    from .api_keys import PEXELS_KEY
except ImportError:
    parent_dir = Path(__file__).parent
    sys.path.insert(0, str(parent_dir))
    from api_keys import PEXELS_KEY

def log(msg):
    print(f"[THUMB] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

STYLES = {
    "1":  {"nom": "Or divin",         "gradient": [(20,10,0),(80,40,0)],      "titre": (255,215,0),   "sous": (255,220,150), "accent": (255,180,0)},
    "2":  {"nom": "Ciel nocturne",    "gradient": [(5,5,40),(20,20,80)],      "titre": (255,255,255), "sous": (150,200,255), "accent": (100,150,255)},
    "3":  {"nom": "Feu sacre",        "gradient": [(40,0,0),(100,30,0)],      "titre": (255,120,0),   "sous": (255,200,100), "accent": (255,80,0)},
    "4":  {"nom": "Paix eternelle",   "gradient": [(0,30,20),(0,60,40)],      "titre": (100,255,150), "sous": (200,255,220), "accent": (50,200,100)},
    "5":  {"nom": "Lumiere pure",     "gradient": [(20,20,50),(60,40,100)],   "titre": (220,180,255), "sous": (255,255,255), "accent": (180,130,255)},
    "6":  {"nom": "Coucher de soleil","gradient": [(80,20,0),(150,60,0)],     "titre": (255,200,50),  "sous": (255,230,150), "accent": (255,150,0)},
    "7":  {"nom": "Ocean profond",    "gradient": [(0,10,40),(0,30,80)],      "titre": (0,200,255),   "sous": (150,230,255), "accent": (0,150,200)},
    "8":  {"nom": "Foret sacree",     "gradient": [(0,20,10),(10,50,20)],     "titre": (150,255,100), "sous": (200,255,180), "accent": (80,200,50)},
    "9":  {"nom": "Gloire royale",    "gradient": [(30,0,50),(70,0,100)],     "titre": (255,215,0),   "sous": (220,180,255), "accent": (200,100,255)},
    "10": {"nom": "Aube nouvelle",    "gradient": [(50,20,20),(100,50,30)],   "titre": (255,240,200), "sous": (255,220,150), "accent": (255,180,80)},
    "11": {"nom": "Aleatoire",        "gradient": None, "titre": None, "sous": None, "accent": None},
}

def charger_police(taille, gras=True):
    fonts = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if gras else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if gras else "C:\\Windows\\Fonts\\calibri.ttf",
    ]
    for f in fonts:
        try: return ImageFont.truetype(f, taille)
        except: continue
    return ImageFont.load_default()

def telecharger_image_fond(mot_cle):
    try:
        headers = {"Authorization": PEXELS_KEY}
        url = f"https://api.pexels.com/v1/search?query={mot_cle}&per_page=5&orientation=landscape"
        r = requests.get(url, headers=headers, timeout=15)
        photos = r.json().get("photos", [])
        if photos:
            img_url = random.choice(photos)["src"]["large2x"]
            img_r = requests.get(img_url, timeout=30)
            from io import BytesIO
            return Image.open(BytesIO(img_r.content)).convert("RGBA")
    except Exception as e:
        log(f"Erreur image : {e}")
    return None

def ollama(prompt):
    try:
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7}
        })
        return r.json()["response"].strip()
    except:
        return ""

def dessiner_texte_centre(draw, y, texte, font, couleur, W, marge=70):
    bbox = draw.textbbox((0,0), texte, font=font)
    tw = bbox[2]-bbox[0]
    x = max(marge, (W-tw)//2)
    draw.text((x+2,y+2), texte, font=font, fill=(0,0,0,180))
    draw.text((x,y), texte, font=font, fill=couleur+(255,))

def appliquer_gradient(img, c_haut, c_bas):
    w, h = img.size
    g = Image.new("RGBA", (w,h))
    for y in range(h):
        ratio = y/h
        r = int(c_haut[0]+(c_bas[0]-c_haut[0])*ratio)
        gg = int(c_haut[1]+(c_bas[1]-c_haut[1])*ratio)
        b = int(c_haut[2]+(c_bas[2]-c_haut[2])*ratio)
        a = int(200*ratio)
        for x in range(w): g.putpixel((x,y),(r,gg,b,a))
    return Image.alpha_composite(img.convert("RGBA"), g)

def ajouter_vignette(img):
    w, h = img.size
    v = Image.new("RGBA", (w,h), (0,0,0,0))
    draw = ImageDraw.Draw(v)
    steps = min(w,h)//4
    for i in range(steps):
        a = int(150*(1-i/steps))
        draw.rectangle([i,i,w-i,h-i], outline=(0,0,0,a))
    return Image.alpha_composite(img.convert("RGBA"), v)

def generer_thumbnail_standalone(sujet, langue, type_contenu, style_key, image_fond_path=None, output_dir=None):
    W, H = 1280, 720
    MARGE = 70

    if output_dir is None:
        output_dir = "C:\\StudioIA\\temp\\thumbnails"
    os.makedirs(output_dir, exist_ok=True)

    # Style
    if style_key == "11":
        style = random.choice([v for k,v in STYLES.items() if k != "11"])
    else:
        style = STYLES.get(style_key, STYLES["1"])
    log(f"Style : {style['nom']}")

    # Image de fond
    if image_fond_path and os.path.exists(image_fond_path):
        img = Image.open(image_fond_path).convert("RGBA")
        img = img.resize((W,H), Image.LANCZOS)
    else:
        log("Telechargement image de fond...")
        mots_cle = "prayer divine light" if type_contenu == "priere" else "story dramatic"
        img_dl = telecharger_image_fond(mots_cle)
        if img_dl:
            img = img_dl.resize((W,H), Image.LANCZOS)
        else:
            img = Image.new("RGBA", (W,H), style["gradient"][0]+(255,))

    img = ImageEnhance.Brightness(img).enhance(0.5)
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = appliquer_gradient(img, style["gradient"][0], style["gradient"][1])
    img = ajouter_vignette(img)

    draw = ImageDraw.Draw(img)

    # Generer contenu IA
    log("Generation titre...")
    langue_nom = "francais" if langue == "fr" else "anglais"
    titre = ollama(f"""Sujet : "{sujet}", langue : {langue_nom}.
Titre YouTube court et percutant, max 4 mots en {langue_nom.upper()}.
UNIQUEMENT le titre sans guillemets.""").upper()[:45]

    log("Generation verset...")
    if type_contenu == "priere":
        verset = ollama(f"""Verset biblique court inspire par "{sujet}" en {langue_nom}, max 10 mots.
UNIQUEMENT le verset.""")[:80]
    else:
        verset = ollama(f"""Phrase inspirante courte sur "{sujet}" en {langue_nom}, max 8 mots.
UNIQUEMENT la phrase.""")[:80]

    cta_options_fr = ["Regardez maintenant", "Ecoutez et priez", "Abonnez-vous", "Ne manquez pas ca"]
    cta_options_en = ["Watch Now", "Subscribe", "Don t Miss This", "Listen Now"]
    cta = random.choice(cta_options_fr if langue == "fr" else cta_options_en)

    log(f"Titre  : {titre}")
    log(f"Verset : {verset}")
    log(f"CTA    : {cta}")

    # Polices
    font_titre = charger_police(85)
    font_verset = charger_police(26, gras=False)
    font_cta = charger_police(28)
    font_petit = charger_police(18, gras=False)

    # Layout
    mots = titre.split()
    if len(mots) > 3:
        mid = len(mots)//2
        ligne1 = " ".join(mots[:mid])
        ligne2 = " ".join(mots[mid:])
    else:
        ligne1 = titre
        ligne2 = ""

    y = 130
    dessiner_texte_centre(draw, y, ligne1, font_titre, style["titre"], W, MARGE)
    y += 105
    if ligne2:
        dessiner_texte_centre(draw, y, ligne2, font_titre, style["titre"], W, MARGE)
        y += 105

    draw.line([(MARGE*2,y),(W-MARGE*2,y)], fill=style["accent"]+(180,), width=2)
    y += 15

    if verset:
        dessiner_texte_centre(draw, y, verset, font_verset, style["sous"], W, MARGE)
        y += 45

    draw.line([(MARGE*2,y),(W-MARGE*2,y)], fill=style["accent"]+(80,), width=1)
    y += 15

    if cta:
        bbox = draw.textbbox((0,0), cta, font=font_cta)
        tw = bbox[2]-bbox[0]
        x = (W-tw)//2
        pad = 12
        draw.rounded_rectangle([x-pad,y-pad//2,x+tw+pad,y+40], radius=8, fill=style["accent"]+(200,))
        draw.text((x+1,y+1), cta, font=font_cta, fill=(0,0,0,150))
        draw.text((x,y), cta, font=font_cta, fill=(255,255,255,255))

    # Watermark
    nom = "Priere Connexion" if (langue=="fr" and type_contenu=="priere") else "Unspoken"
    draw.text((W-160, H-30), nom, font=font_petit, fill=(255,255,255,120))

    # Sauvegarder
    nom_fichier = f"thumb_{sujet[:20].replace(' ','_')}_{style['nom'].replace(' ','_')}.png"
    output_path = os.path.join(output_dir, nom_fichier)
    img.convert("RGB").save(output_path, "PNG", quality=95)

    # Sauvegarder JSON
    json_path = output_path.replace(".png", ".json")
    ecrire_json(json_path, {
        "sujet": sujet,
        "titre": titre,
        "verset": verset,
        "cta": cta,
        "style": style["nom"],
        "langue": langue,
        "type_contenu": type_contenu
    })

    log(f"Thumbnail sauvegardee : {output_path}")
    return output_path

def menu_standalone():
    print("\n  ================================")
    print("  GENERATEUR THUMBNAIL STANDALONE")
    print("  ================================")

    sujet = input("\n  Sujet de la video : ").strip()
    if not sujet:
        return

    print("\n  Type de contenu :")
    print("  [1] Priere chretienne (FR)")
    print("  [2] Storytelling (FR)")
    print("  [3] Storytelling (EN)")
    print("  [4] General (FR)")
    type_choix = input("  Choix [1] : ").strip() or "1"

    langue = "fr"
    type_contenu = "priere"
    if type_choix == "2": langue, type_contenu = "fr", "storytelling"
    elif type_choix == "3": langue, type_contenu = "en", "storytelling"
    elif type_choix == "4": langue, type_contenu = "fr", "general"

    print("\n  Style :")
    for k, v in STYLES.items():
        print(f"  [{k}] {v['nom']}")
    style_key = input("  Choix [11=Aleatoire] : ").strip() or "11"

    print("\n  Image de fond :")
    print("  [1] Telecharger automatiquement (Pexels)")
    print("  [2] Utiliser un fichier local")
    img_choix = input("  Choix [1] : ").strip() or "1"

    image_fond_path = None
    if img_choix == "2":
        image_fond_path = input("  Chemin image : ").strip()

    print("\n  Nombre de variantes a generer :")
    nb = input("  Nombre [1] : ").strip() or "1"
    nb = int(nb) if nb.isdigit() else 1

    output_dir = "C:\\StudioIA\\temp\\thumbnails"
    chemins = []

    for i in range(nb):
        log(f"Generation variante {i+1}/{nb}...")
        s_key = style_key if style_key != "11" else str(random.randint(1,10))
        path = generer_thumbnail_standalone(
            sujet, langue, type_contenu, s_key, image_fond_path, output_dir)
        chemins.append(path)

    print(f"\n  {nb} thumbnail(s) generee(s) dans : {output_dir}")
    ouvrir = input("  Ouvrir le dossier ? (o/n) : ").strip()
    if ouvrir == "o":
        import subprocess
        subprocess.Popen(["explorer.exe", output_dir])

if __name__ == "__main__":
    menu_standalone()