#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Générateur Thumbnail Standalone - Interface GUI
Utilisable depuis app_gui.py
"""

import customtkinter as ctk
import json
import os
import sys
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Paths
OUTPUT_DIR = str(paths.TEMP_DIR / "thumbnails")
CONFIG_PATH = str(paths.config_path())
ASSETS_PATH = str(paths.ASSETS_DIR)

# Import modules
paths.ajouter_modules_au_path()
from api_keys import PEXELS_KEY

# Styles
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
}


class ThumbnailGeneratorGUI(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Générateur Thumbnail")
        self.geometry("600x700")
        self.resizable(False, False)

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            self,
            text="Générateur Thumbnail",
            font=("Segoe UI", 18, "bold")
        ).grid(row=0, column=0, padx=20, pady=20, sticky="w")

        # Sujet
        ctk.CTkLabel(self, text="Sujet de la vidéo", font=("Segoe UI", 11)).grid(
            row=1, column=0, padx=20, pady=(10, 5), sticky="w"
        )
        self.sujet_entry = ctk.CTkEntry(self, placeholder_text="Ex: La puissance de la prière")
        self.sujet_entry.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        # Type
        ctk.CTkLabel(self, text="Type de contenu", font=("Segoe UI", 11)).grid(
            row=3, column=0, padx=20, pady=(10, 5), sticky="w"
        )
        self.type_var = ctk.StringVar(value="1")

        type_frame = ctk.CTkFrame(self)
        type_frame.grid(row=4, column=0, padx=20, pady=5, sticky="w")
        types = [
            ("Prière chrétienne (FR)", "1"),
            ("Storytelling (FR)", "2"),
            ("Storytelling (EN)", "3"),
            ("Général (FR)", "4"),
        ]
        for i, (text, value) in enumerate(types):
            ctk.CTkRadioButton(type_frame, text=text, variable=self.type_var, value=value).grid(
                row=0, column=i, padx=5, pady=5
            )

        # Style
        ctk.CTkLabel(self, text="Style", font=("Segoe UI", 11)).grid(
            row=5, column=0, padx=20, pady=(10, 5), sticky="w"
        )
        self.style_var = ctk.StringVar(value="1")
        self.style_combo = ctk.CTkOptionMenu(
            self,
            variable=self.style_var,
            values=[f"{k}: {v['nom']}" for k, v in STYLES.items()]
        )
        self.style_combo.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        # Image
        ctk.CTkLabel(self, text="Image de fond", font=("Segoe UI", 11)).grid(
            row=7, column=0, padx=20, pady=(10, 5), sticky="w"
        )
        self.img_var = ctk.StringVar(value="1")
        img_frame = ctk.CTkFrame(self)
        img_frame.grid(row=8, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkRadioButton(img_frame, text="Télécharger automatiquement", variable=self.img_var, value="1").grid(row=0, column=0, padx=5)
        ctk.CTkRadioButton(img_frame, text="Fichier local", variable=self.img_var, value="2").grid(row=0, column=1, padx=5)

        self.image_path_entry = ctk.CTkEntry(self, placeholder_text="Chemin vers l'image...")
        self.image_path_entry.grid(row=9, column=0, padx=20, pady=5, sticky="ew")

        # Number of variants
        ctk.CTkLabel(self, text="Nombre de variantes", font=("Segoe UI", 11)).grid(
            row=10, column=0, padx=20, pady=(10, 5), sticky="w"
        )
        self.nb_variants = ctk.CTkEntry(self, width=100)
        self.nb_variants.insert(0, "1")
        self.nb_variants.grid(row=11, column=0, padx=20, pady=5, sticky="w")

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.grid(row=12, column=0, padx=20, pady=15, sticky="ew")
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.grid(row=13, column=0, padx=20, pady=5, sticky="w")
        self.progress_label.grid_remove()

        # Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=14, column=0, padx=20, pady=20, sticky="e")

        ctk.CTkButton(btn_frame, text="Annuler", command=self.destroy).grid(row=0, column=0, padx=5)
        ctk.CTkButton(
            btn_frame,
            text="Générer",
            command=self.generate,
            fg_color="#3b82f6"
        ).grid(row=0, column=1, padx=5)

    def log(self, msg):
        print(f"[THUMB] {msg}")
        self.progress_label.configure(text=msg)
        self.update_idletasks()

    def generate(self):
        sujet = self.sujet_entry.get().strip()
        if not sujet:
            self.log("Erreur: Veuillez entrer un sujet")
            return

        self.progress_bar.grid()
        self.progress_label.grid()

        type_map = {"1": ("priere", "fr"), "2": ("storytelling", "fr"), "3": ("storytelling", "en"), "4": ("general", "fr")}
        type_contenu, langue = type_map.get(self.type_var.get(), ("priere", "fr"))

        style_key = self.style_var.get()
        if style_key.startswith("11"):
            style_key = str(random.randint(1, 10))

        nb = int(self.nb_variants.get()) if self.nb_variants.get().isdigit() else 1

        image_path = None
        if self.img_var.get() == "2":
            image_path = self.image_path_entry.get().strip()

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        self.log(f"Génération de {nb} thumbnail(s)...")

        for i in range(nb):
            self.progress_bar.set((i + 1) / nb)
            self.log(f"Thumbnail {i+1}/{nb}...")

            # Génération
            self._generate_single_thumbnail(sujet, langue, type_contenu, style_key, image_path, OUTPUT_DIR, i + 1, nb)

        self.log(f"{nb} thumbnail(s) généré(s) dans : {OUTPUT_DIR}")

        # Ouvrir dossier
        import subprocess
        subprocess.Popen(["explorer.exe", OUTPUT_DIR])

        self.destroy()

    def _generate_single_thumbnail(self, sujet, langue, type_contenu, style_key, image_path, output_dir, current, total):
        W, H = 1280, 720
        MARGE = 70

        style = STYLES.get(style_key, STYLES["1"])
        self.log(f"  Style: {style['nom']}")

        # Image fond
        if image_path and os.path.exists(image_path):
            img = Image.open(image_path).convert("RGBA")
            img = img.resize((W, H), getattr(Image, 'LANCZOS', Image.BILINEAR))
        else:
            self.log("  Téléchargement image...")
            img_dl = self._download_image_fond(sujet)
            if img_dl:
                img = img_dl.resize((W, H), getattr(Image, 'LANCZOS', Image.BILINEAR))
            else:
                img = Image.new("RGBA", (W, H), style["gradient"][0] + (255,))

        img = ImageEnhance.Brightness(img).enhance(0.5)
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = self._appliquer_gradient(img, style["gradient"][0], style["gradient"][1])
        img = self._ajouter_vignette(img)

        draw = ImageDraw.Draw(img)

        # Génération contenu IA
        self.log("  Génération titre...")
        langue_nom = "francais" if langue == "fr" else "anglais"
        titre = self._ollama(f"""Sujet: "{sujet}", langue: {langue_nom}.
Titre YouTube court, max 4 mots en {langue_nom.upper()}, pas de guillemets.""").upper()[:45]

        self.log("  Génération verset...")
        if type_contenu == "priere":
            verset = self._ollama(f"""Verset biblique court sur "{sujet}" en {langue_nom}, max 10 mots.""")[:80]
        else:
            verset = self._ollama(f"""Phrase inspirante sur "{sujet}" en {langue_nom}, max 8 mots.""")[:80]

        cta_options = {
            "fr": ["Regardez maintenant", "Ecoutez et priez", "Abonnez-vous"],
            "en": ["Watch Now", "Subscribe", "Don't Miss This"]
        }
        cta = random.choice(cta_options.get(langue, cta_options["fr"]))

        # Polices
        font_titre = self._charger_police(85)
        font_verset = self._charger_police(26, gras=False)
        font_cta = self._charger_police(28)
        font_petit = self._charger_police(18, gras=False)

        # Layout
        mots = titre.split()
        ligne1 = " ".join(mots[:len(mots)//2]) if len(mots) > 3 else titre
        ligne2 = " ".join(mots[len(mots)//2:]) if len(mots) > 3 else ""

        y = 130
        self._dessiner_texte_centre(draw, y, ligne1, font_titre, style["titre"], W, MARGE)
        y += 105
        if ligne2:
            self._dessiner_texte_centre(draw, y, ligne2, font_titre, style["titre"], W, MARGE)
            y += 105

        draw.line([(MARGE*2, y), (W-MARGE*2, y)], fill=style["accent"]+(180,), width=2)
        y += 15

        if verset:
            self._dessiner_texte_centre(draw, y, verset, font_verset, style["sous"], W, MARGE)
            y += 45

        draw.line([(MARGE*2, y), (W-MARGE*2, y)], fill=style["accent"]+(80,), width=1)
        y += 15

        if cta:
            bbox = draw.textbbox((0, 0), cta, font=font_cta)
            tw = bbox[2] - bbox[0]
            x = (W - tw) // 2
            pad = 12
            draw.rounded_rectangle([x-pad, y-pad//2, x+tw+pad, y+40], radius=8, fill=style["accent"]+(200,))
            draw.text((x+1, y+1), cta, font=font_cta, fill=(0, 0, 0, 150))
            draw.text((x, y), cta, font=font_cta, fill=(255, 255, 255, 255))

        # Watermark
        nom = "Priere Connexion" if (langue == "fr" and type_contenu == "priere") else "Unspoken"
        draw.text((W-160, H-30), nom, font=font_petit, fill=(255, 255, 255, 120))

        # Sauvegarder
        nom_fichier = f"thumb_{sujet[:20].replace(' ', '_')}_{style['nom'].replace(' ', '_')}.png"
        output_path = os.path.join(output_dir, nom_fichier)
        img.convert("RGB").save(output_path, "PNG", quality=95)

        self.log(f"  Thumbnail sauvegardé: {nom_fichier}")

    def _ollama(self, prompt):
        try:
            import requests
            r = requests.post("http://localhost:11434/api/generate", json={
                "model": "qwen2.5:7b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7}
            }, timeout=30)
            return r.json()["response"].strip()
        except Exception as e:
            self.log(f"  Ollama erreur: {e}")
            return "Titre par defaut"

    def _download_image_fond(self, sujet):
        try:
            import requests
            import random
            headers = {"Authorization": PEXELS_KEY}
            url = f"https://api.pexels.com/v1/search?query={sujet}&per_page=3&orientation=landscape"
            r = requests.get(url, headers=headers, timeout=15)
            photos = r.json().get("photos", [])
            if photos:
                img_url = random.choice(photos)["src"]["large2x"]
                img_r = requests.get(img_url, timeout=30)
                from io import BytesIO
                return Image.open(BytesIO(img_r.content)).convert("RGBA")
        except Exception as e:
            self.log(f"  Download erreur: {e}")
        return None

    def _charger_police(self, taille, gras=True):
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

    def _dessiner_texte_centre(self, draw, y, texte, font, couleur, W, marge=70):
        bbox = draw.textbbox((0, 0), texte, font=font)
        tw = bbox[2] - bbox[0]
        x = max(marge, (W - tw) // 2)
        draw.text((x+2, y+2), texte, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), texte, font=font, fill=couleur + (255,))

    def _appliquer_gradient(self, img, c_haut, c_bas):
        w, h = img.size
        g = Image.new("RGBA", (w, h))
        for y in range(h):
            ratio = y / h
            r = int(c_haut[0] + (c_bas[0] - c_haut[0]) * ratio)
            gg = int(c_haut[1] + (c_bas[1] - c_haut[1]) * ratio)
            b = int(c_haut[2] + (c_bas[2] - c_haut[2]) * ratio)
            a = int(200 * ratio)
            for x in range(w):
                g.putpixel((x, y), (r, gg, b, a))
        return Image.alpha_composite(img.convert("RGBA"), g)

    def _ajouter_vignette(self, img):
        w, h = img.size
        v = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(v)
        steps = min(w, h) // 4
        for i in range(steps):
            a = int(150 * (1 - i / steps))
            draw.rectangle([i, i, w-i, h-i], outline=(0, 0, 0, a))
        return Image.alpha_composite(img.convert("RGBA"), v)


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()  # Cacher la fenêtre principale

    app = ThumbnailGeneratorGUI(root)
    app.mainloop()


if __name__ == "__main__":
    main()
