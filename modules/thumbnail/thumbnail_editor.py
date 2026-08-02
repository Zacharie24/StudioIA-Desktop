import json, os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import random

def log(msg):
    print(f"[THUMB-EDIT] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

STYLES = {
    "1": {"nom": "Or divin",       "gradient": [(20,10,0),(80,40,0)],    "titre": (255,215,0),   "sous": (255,220,150), "accent": (255,180,0)},
    "2": {"nom": "Ciel nocturne",  "gradient": [(5,5,40),(20,20,80)],    "titre": (255,255,255), "sous": (150,200,255), "accent": (100,150,255)},
    "3": {"nom": "Feu sacre",      "gradient": [(40,0,0),(100,30,0)],    "titre": (255,120,0),   "sous": (255,200,100), "accent": (255,80,0)},
    "4": {"nom": "Paix eternelle", "gradient": [(0,30,20),(0,60,40)],    "titre": (100,255,150), "sous": (200,255,220), "accent": (50,200,100)},
    "5": {"nom": "Lumiere pure",   "gradient": [(20,20,50),(60,40,100)], "titre": (220,180,255), "sous": (255,255,255), "accent": (180,130,255)},
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

def texte_largeur(draw, texte, font):
    bbox = draw.textbbox((0,0), texte, font=font)
    return bbox[2] - bbox[0]

def adapter_police(draw, texte, taille_max, largeur_max, gras=True):
    taille = taille_max
    while taille > 20:
        font = charger_police(taille, gras)
        if texte_largeur(draw, texte, font) <= largeur_max:
            return font
        taille -= 5
    return charger_police(20, gras)

def dessiner_texte_ombre(draw, x, y, texte, font, couleur):
    for dx, dy in [(-2,2),(2,2),(0,3)]:
        draw.text((x+dx, y+dy), texte, font=font, fill=(0,0,0,180))
    draw.text((x, y), texte, font=font, fill=couleur+(255,))

def dessiner_centre(draw, y, texte, font, couleur, W, marge=70):
    tw = texte_largeur(draw, texte, font)
    x  = max(marge, (W-tw)//2)
    dessiner_texte_ombre(draw, x, y, texte, font, couleur)

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

def regenerer_image(project_path, projet, style):
    W, H  = 1280, 720
    MARGE = 70

    # Fond
    bg_fichier = projet.get("image_fond", "")
    if bg_fichier:
        bg_path = os.path.join(project_path, bg_fichier)
        try:
            img = Image.open(bg_path).convert("RGBA")
            img = img.resize((W,H), Image.LANCZOS)
            img = ImageEnhance.Brightness(img).enhance(0.5)
            img = ImageEnhance.Contrast(img).enhance(1.3)
        except:
            img = Image.new("RGBA", (W,H), style["gradient"][0]+(255,))
    else:
        img = Image.new("RGBA", (W,H), style["gradient"][0]+(255,))

    img  = appliquer_gradient(img, style["gradient"][0], style["gradient"][1])
    img  = ajouter_vignette(img)
    draw = ImageDraw.Draw(img)

    titre  = projet.get("titre", "")
    verset = projet.get("verset", "")
    cta    = projet.get("cta", "")

    mots = titre.split()
    if len(mots) > 3:
        mid    = len(mots)//2
        ligne1 = " ".join(mots[:mid])
        ligne2 = " ".join(mots[mid:])
    else:
        ligne1 = titre
        ligne2 = ""

    font_titre  = adapter_police(draw, ligne1, 90, W-MARGE*2)
    font_verset = charger_police(26, gras=False)
    font_cta    = charger_police(28, gras=True)
    font_petit  = charger_police(20, gras=False)

    y = 100
    dessiner_centre(draw, y, ligne1, font_titre, style["titre"], W, MARGE)
    y += 110
    if ligne2:
        dessiner_centre(draw, y, ligne2, font_titre, style["titre"], W, MARGE)
        y += 110

    draw.line([(MARGE*2,y),(W-MARGE*2,y)], fill=style["accent"]+(180,), width=2)
    draw.line([(MARGE*2,y+4),(W-MARGE*2,y+4)], fill=style["accent"]+(60,), width=1)
    y += 20

    if verset:
        dessiner_centre(draw, y, verset, font_verset, style["sous"], W, MARGE)
        y += 45

    draw.line([(MARGE*2,y),(W-MARGE*2,y)], fill=style["accent"]+(80,), width=1)
    y += 15

    if cta:
        tw  = texte_largeur(draw, cta, font_cta)
        x_c = (W-tw)//2
        pad = 12
        draw.rounded_rectangle([x_c-pad,y-pad//2,x_c+tw+pad,y+35+pad//2],
                                radius=8, fill=style["accent"]+(180,))
        dessiner_texte_ombre(draw, x_c, y, cta, font_cta, (255,255,255))

    # Watermark
    langue       = projet.get("langue","fr")
    type_contenu = projet.get("type_contenu","priere")
    nom = "Priere Connexion Divine" if (langue=="fr" and type_contenu=="priere") else "Unspoken"
    draw.text((W-200, H-35), nom, font=font_petit, fill=(255,255,255,130))

    return img

def menu_editeur(project_path):
    thumb_json = os.path.join(project_path, "thumbnail", "thumbnail.json")
    thumb_png  = os.path.join(project_path, "thumbnail", "thumbnail.png")

    if not os.path.exists(thumb_json):
        log("Aucun projet thumbnail trouve. Lancez d abord thumbnail_builder.py")
        return

    projet = lire_json(thumb_json)
    style_nom = projet.get("style", "Or divin")
    style_key = next((k for k,v in STYLES.items() if v["nom"]==style_nom), "1")
    style = STYLES[style_key]

    while True:
        print("\n  ================================")
        print("  EDITEUR THUMBNAIL")
        print("  ================================")
        print(f"  Titre   : {projet.get('titre','')}")
        print(f"  Verset  : {projet.get('verset','')}")
        print(f"  CTA     : {projet.get('cta','')}")
        print(f"  Style   : {style['nom']}")
        print(f"  Fond    : {projet.get('image_fond','')}")
        print("  --------------------------------")
        print("  [1] Modifier titre")
        print("  [2] Modifier verset / pensee")
        print("  [3] Modifier call to action")
        print("  [4] Changer style")
        print("  [5] Changer image de fond")
        print("  [6] Exporter PNG")
        print("  [7] Exporter et ouvrir")
        print("  [0] Quitter")

        choix = input("\n  Choix : ").strip()

        if choix == "1":
            nouveau = input(f"  Nouveau titre [{projet['titre']}] : ").strip()
            if nouveau: projet["titre"] = nouveau.upper()

        elif choix == "2":
            nouveau = input(f"  Nouveau verset [{projet.get('verset','')}] : ").strip()
            if nouveau: projet["verset"] = nouveau

        elif choix == "3":
            nouveau = input(f"  Nouveau CTA [{projet.get('cta','')}] : ").strip()
            if nouveau: projet["cta"] = nouveau

        elif choix == "4":
            print("\n  Styles :")
            for k, v in STYLES.items():
                print(f"    [{k}] {v['nom']}")
            sc = input("  Choix : ").strip()
            if sc in STYLES:
                style = STYLES[sc]
                projet["style"] = style["nom"]

        elif choix == "5":
            # Lister images disponibles
            bg_dir = os.path.join(project_path, "images", "backgrounds")
            if os.path.exists(bg_dir):
                imgs = [f for f in os.listdir(bg_dir) if f.endswith(".jpg")]
                for i, img_name in enumerate(imgs, 1):
                    print(f"    [{i}] {img_name}")
                ic = input("  Choix image : ").strip()
                try:
                    projet["image_fond"] = f"images/backgrounds/{imgs[int(ic)-1]}"
                except:
                    log("Choix invalide")

        elif choix in ["6","7"]:
            log("Generation en cours...")
            img = regenerer_image(project_path, projet, style)
            img.convert("RGB").save(thumb_png, "PNG", quality=95)
            ecrire_json(thumb_json, projet)
            log(f"Sauvegarde : {thumb_png}")
            if choix == "7":
                import subprocess
                subprocess.Popen(["start", thumb_png], shell=True)

        elif choix == "0":
            break

if __name__ == "__main__":
    project_path = sys.argv[1] if len(sys.argv) > 1 else "C:\\StudioIA\\projects\\test_rapide"
    menu_editeur(project_path)