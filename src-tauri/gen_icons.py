# -*- coding: utf-8 -*-
"""Génère les icônes de l'app (fenêtre + tray + installer) avec PIL.
Dessin : carré arrondi dégradé bleu-violet, croix blanche centrale."""
import os
from PIL import Image, ImageDraw, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(BASE, "icons")
os.makedirs(ICONS, exist_ok=True)

S = 512
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- dégradé bleu → violet (diagonale) ---
top = (36, 82, 214)
bot = (120, 60, 190)
for y in range(S):
    t = y / S
    r = int(top[0] + (bot[0] - top[0]) * t)
    g = int(top[1] + (bot[1] - top[1]) * t)
    b = int(top[2] + (bot[2] - top[2]) * t)
    d.line([(0, y), (S, y)], fill=(r, g, b, 255))

# --- masque arrondi ---
mask = Image.new("L", (S, S), 0)
dm = ImageDraw.Draw(mask)
radius = int(S * 0.18)
dm.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(3))
img.putalpha(mask)

# --- croix blanche ---
cw, ch = S * 0.42, S * 0.42
cx, cy = (S - cw) / 2, (S - ch) / 2
cross = Image.new("RGBA", (S, S), (0, 0, 0, 0))
dc = ImageDraw.Draw(cross)
bar = int(S * 0.09)
# barre verticale
dc.rounded_rectangle([S / 2 - bar / 2, cy, S / 2 + bar / 2, cy + ch], radius=bar, fill=(255, 255, 255, 255))
# barre horizontale (décalée vers le haut, style chrétien)
h_off = cy + ch * 0.13
dc.rounded_rectangle([cx, h_off, cx + cw, h_off + bar], radius=bar, fill=(255, 255, 255, 255))
img = Image.alpha_composite(img, cross)

# --- master 256 ---
img.resize((256, 256), Image.LANCZOS).save(os.path.join(ICONS, "icon.png"))

# --- .ico multi-tailles ---
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.resize((256, 256), Image.LANCZOS).save(
    os.path.join(ICONS, "icon.ico"), format="ICO", sizes=sizes
)
# icônes Tauri requises (fichiers nommés)
img.resize((32, 32), Image.LANCZOS).save(os.path.join(ICONS, "32x32.png"))
img.resize((128, 128), Image.LANCZOS).save(os.path.join(ICONS, "128x128.png"))
img.resize((256, 256), Image.LANCZOS).save(os.path.join(ICONS, "128x128@2x.png"))
img.resize((512, 512), Image.LANCZOS).save(os.path.join(ICONS, "icon.png"))

print("Icônes générées dans", ICONS)
for f in sorted(os.listdir(ICONS)):
    print(" -", f, os.path.getsize(os.path.join(ICONS, f)), "octets")
