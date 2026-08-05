import json, os, sys, random, requests
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

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

def ollama(prompt):
    try:
        try:
            from llm import appeler_llm
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from llm import appeler_llm
        return appeler_llm(prompt, modele="mistral").strip()
    except:
        return ""

def generer_contenu_thumb(sujet, langue, type_contenu):
    langue_nom = "francais" if langue == "fr" else "anglais"

    # Titre
    titre = ollama(f"""Sujet video YouTube : "{sujet}"
Langue : {langue_nom}
Genere un titre court et percutant pour miniature YouTube.
Maximum 4 mots en {langue_nom.upper()}.
Pas de guillemets ni ponctuation. UNIQUEMENT le titre.""").upper()[:45]

    # Verset ou pensee
    if type_contenu == "priere":
        verset = ollama(f"""Pour une video de priere sur "{sujet}" en {langue_nom},
donne un court verset biblique inspire (max 10 mots en {langue_nom}).
Format : "Verset - Livre Chapitre:verset"
UNIQUEMENT le verset, rien d autre.""")[:80]
    else:
        verset = ollama(f"""Pour une video sur "{sujet}" en {langue_nom},
donne une courte phrase inspirante (max 8 mots en {langue_nom}).
UNIQUEMENT la phrase, rien d autre.""")[:80]

    # Call to action
    if langue == "fr":
        cta = random.choice([
            "Regardez maintenant",
            "Ecoutez et priez",
            "Abonnez-vous",
            "Ne manquez pas ca",
        ])
    else:
        cta = random.choice([
            "Watch Now",
            "Subscribe",
            "Don't Miss This",
            "Listen & Pray",
        ])

    return titre, verset, cta

def charger_police(taille, gras=True):
    fonts = [
        "C:\\Windows\\Fonts\\arialbd.ttf" if gras else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if gras else "C:\\Windows\\Fonts\\calibri.ttf",
        "C:\\Windows\\Fonts\\verdanab.ttf" if gras else "C:\\Windows\\Fonts\\verdana.ttf",
    ]
    for f in fonts:
        try:
            return ImageFont.truetype(f, taille)
        except:
            continue
    return ImageFont.load_default()

def texte_largeur(draw, texte, font):
    bbox = draw.textbbox((0,0), texte, font=font)
    return bbox[2] - bbox[0]

def adapter_taille_police(draw, texte, taille_max, largeur_max, gras=True):
    taille = taille_max
    while taille > 20:
        font = charger_police(taille, gras)
        if texte_largeur(draw, texte, font) <= largeur_max:
            return font
        taille -= 5
    return charger_police(20, gras)

def dessiner_texte_ombre(draw, x, y, texte, font, couleur):
    for dx, dy in [(-2,2),(2,2),(0,3),(0,-1)]:
        draw.text((x+dx, y+dy), texte, font=font, fill=(0,0,0,180))
    draw.text((x, y), texte, font=font, fill=couleur+(255,))

def dessiner_texte_centre(draw, y, texte, font, couleur, W, marge=60):
    tw = texte_largeur(draw, texte, font)
    x = max(marge, (W - tw) // 2)
    dessiner_texte_ombre(draw, x, y, texte, font, couleur)
    return tw

def appliquer_gradient(img, couleur_haut, couleur_bas):
    w, h = img.size
    gradient = Image.new("RGBA", (w,h))
    for y in range(h):
        ratio = y / h
        r = int(couleur_haut[0]+(couleur_bas[0]-couleur_haut[0])*ratio)
        g = int(couleur_haut[1]+(couleur_bas[1]-couleur_haut[1])*ratio)
        b = int(couleur_haut[2]+(couleur_bas[2]-couleur_haut[2])*ratio)
        a = int(200 * ratio)
        for x in range(w):
            gradient.putpixel((x,y),(r,g,b,a))
    return Image.alpha_composite(img.convert("RGBA"), gradient)

def ajouter_vignette(img, intensite=150):
    w, h = img.size
    vignette = Image.new("RGBA", (w,h), (0,0,0,0))
    draw = ImageDraw.Draw(vignette)
    steps = min(w,h)//4
    for i in range(steps):
        a = int(intensite * (1 - i/steps))
        draw.rectangle([i,i,w-i,h-i], outline=(0,0,0,a))
    return Image.alpha_composite(img.convert("RGBA"), vignette)

def creer_thumbnail(project_path, data, style_key="6"):
    W, H   = 1280, 720
    MARGE  = 70   # marge securite YouTube
    sujet        = data["sujet"]
    langue       = data.get("langue", "fr")
    type_contenu = data.get("type_contenu", "priere")
    images_data  = data.get("images_data", {})
    bgs          = images_data.get("backgrounds", [])
    logo_path    = data.get("logo_path", "")

    thumb_dir = Path(project_path) / "thumbnail"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    # Style
    if style_key == "6":
        style = random.choice([v for k,v in STYLES.items() if k != "6"])
    else:
        style = STYLES.get(style_key, STYLES["1"])
    log(f"Style : {style['nom']}")

    # Image fond
    if bgs:
        try:
            bg_path = os.path.join(project_path, random.choice(bgs)["fichier"])
            img = Image.open(bg_path).convert("RGBA")
            # LANCZOS pour Pillow >=9, BILINEAR pour compatibilité
            resize_method = getattr(Image, 'LANCZOS', Image.BILINEAR)
            img = img.resize((W,H), resize_method)
            img = ImageEnhance.Brightness(img).enhance(0.5)
            img = ImageEnhance.Contrast(img).enhance(1.3)
        except Exception as e:
            log(f"Erreur image fond: {e}, utilisation couleur par defaut")
            img = Image.new("RGBA", (W,H), style["gradient"][0]+(255,))
    else:
        log("Aucune image disponible, utilisation couleur par defaut")
        img = Image.new("RGBA", (W,H), style["gradient"][0]+(255,))

    img = appliquer_gradient(img, style["gradient"][0], style["gradient"][1])
    img = ajouter_vignette(img)

    draw = ImageDraw.Draw(img)
    LARGEUR_MAX = W - MARGE * 2

    # Generer contenu
    log("Generation contenu IA...")
    titre, verset, cta = generer_contenu_thumb(sujet, langue, type_contenu)
    log(f"Titre  : {titre}")
    log(f"Verset : {verset}")
    log(f"CTA    : {cta}")

    # Decouper titre en lignes
    mots = titre.split()
    if len(mots) > 3:
        mid    = len(mots) // 2
        ligne1 = " ".join(mots[:mid])
        ligne2 = " ".join(mots[mid:])
    else:
        ligne1 = titre
        ligne2 = ""

    # Police titre adaptee automatiquement
    font_titre = adapter_taille_police(draw, ligne1, 90, LARGEUR_MAX)
    font_verset = charger_police(26, gras=False)
    font_cta    = charger_police(28, gras=True)
    font_petit  = charger_police(20, gras=False)

    # Layout vertical
    y = 100
    dessiner_texte_centre(draw, y, ligne1, font_titre, style["titre"], W, MARGE)
    y += 110

    if ligne2:
        dessiner_texte_centre(draw, y, ligne2, font_titre, style["titre"], W, MARGE)
        y += 110

    # Ligne decorative
    draw.line([(MARGE*2, y),(W-MARGE*2, y)], fill=style["accent"]+(180,), width=2)
    draw.line([(MARGE*2, y+4),(W-MARGE*2, y+4)], fill=style["accent"]+(60,), width=1)
    y += 20

    # Verset
    if verset:
        dessiner_texte_centre(draw, y, verset, font_verset, style["sous"], W, MARGE)
        y += 45

    # Ligne decorative bas
    draw.line([(MARGE*2, y),(W-MARGE*2, y)], fill=style["accent"]+(80,), width=1)
    y += 15

    # CTA
    tw_cta = texte_largeur(draw, cta, font_cta)
    x_cta = (W - tw_cta) // 2
    # Fond CTA
    pad = 12
    draw.rounded_rectangle(
        [x_cta-pad, y-pad//2, x_cta+tw_cta+pad, y+35+pad//2],
        radius=8, fill=style["accent"]+(180,))
    dessiner_texte_ombre(draw, x_cta, y, cta, font_cta, (255,255,255))

    # Logo ou nom chaine (en bas a droite, dans la marge)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_h = 50
            ratio  = logo_h / logo.size[1]
            logo_w = int(logo.size[0] * ratio)
            logo   = logo.resize((logo_w, logo_h), Image.LANCZOS)
            img.paste(logo, (W-logo_w-MARGE, H-logo_h-15), logo)
        except Exception as e:
            log(f"Logo erreur : {e}")
    else:
        nom = "Priere Connexion Divine" if (langue=="fr" and type_contenu=="priere") else "Unspoken"
        draw.text((W-220, H-35), nom, font=font_petit, fill=(255,255,255,130))

    # Sauvegarder
    output_png = thumb_dir / "thumbnail.png"
    img.convert("RGB").save(str(output_png), "PNG", quality=95)

    # Créer un projet modifiable (format Penpot JSON)
    projet_penpot = {
        "type": "projet_modifiable",
        "nom": f"Thumbnail - {data['sujet'][:30]}",
        "dimensions": {"largeur": W, "hauteur": H},
        "style": style["nom"],
        "elements": [
            {
                "type": "texte",
                "nom": "Titre Principal",
                "contenu": titre,
                "position": {"x": W//2, "y": 100},
                "police": "Arial Bold",
                "taille": 90,
                "couleur": list(style["titre"]) + [1.0],
                "alignement": "centre",
                "marge": MARGE
            },
            {
                "type": "texte",
                "nom": "Ligne 2 (optionnelle)",
                "contenu": ligne2 if ligne2 else "",
                "position": {"x": W//2, "y": 210},
                "police": "Arial Bold",
                "taille": 90,
                "couleur": list(style["titre"]) + [1.0],
                "alignement": "centre",
                "marge": MARGE
            },
            {
                "type": "texte",
                "nom": "Verset/Bandeau",
                "contenu": verset,
                "position": {"x": W//2, "y": y - 45 if ligne2 else y - 25},
                "police": "Arial",
                "taille": 26,
                "couleur": list(style["sous"]) + [1.0],
                "alignement": "centre",
                "marge": MARGE
            },
            {
                "type": "texte",
                "nom": "Call to Action",
                "contenu": cta,
                "position": {"x": W//2, "y": y + 35},
                "police": "Arial Bold",
                "taille": 28,
                "couleur": [1.0, 1.0, 1.0, 1.0],
                "alignement": "centre",
                "fond": list(style["accent"]) + [0.7],
                "coins_roundes": 8
            },
            {
                "type": "texte",
                "nom": "Nom chaine",
                "contenu": nom,
                "position": {"x": W - 220, "y": H - 35},
                "police": "Arial",
                "taille": 20,
                "couleur": [1.0, 1.0, 1.0, 0.5],
                "alignement": "droite"
            }
        ],
        "config": {
            "langue": langue,
            "type_contenu": type_contenu,
            "date_generation": datetime.now().isoformat(),
            "sujet": sujet
        }
    }

    # Sauvegarder le projet modifiable
    projet_path = thumb_dir / "thumbnail_project.json"
    with open(projet_path, "w", encoding="utf-8") as f:
        json.dump(projet_penpot, f, indent=2, ensure_ascii=False)

    # Sauvegarder aussi le fichier JSON initial pour compatibilité
    ecrire_json(str(thumb_dir / "thumbnail_meta.json"), {
        "style": style["nom"], "titre": titre,
        "verset": verset, "cta": cta,
        "langue": langue, "type_contenu": type_contenu,
        "resolution": f"{W}x{H}"
    })

    log(f"Thumbnail sauvegardee : {output_png}")
    log(f"Projet modifiable : {projet_path.name} (pour Penpot/Photoshop)")
    return str(output_png)

def choisir_style():
    import sys
    sys.path.insert(0, str(paths.MODULES_DIR / "utils"))
    from timeout_input import choisir_avec_timeout
    print("\n[THUMB] Style thumbnail :")
    for k, v in STYLES.items():
        print(f"  [{k}] {v['nom']}")
    return choisir_avec_timeout(STYLES, "6", 10, "Style thumbnail")

def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    data = lire_json(pjson)
    style_key = sys.argv[2] if len(sys.argv) > 2 else choisir_style()
    creer_thumbnail(project_path, data, style_key)
    data["etapes"]["thumbnail"] = "termine"
    ecrire_json(pjson, data)
    log("THUMBNAIL TERMINEE !")

if __name__ == "__main__":
    main()