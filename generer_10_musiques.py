#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script pour générer 10 musiques de fond différentes avec ComposIA
et les fusionner dans un fichier musique_fond_final.mp3
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Chemin vers ComposIA (résolu depuis la racine de l'application)
COMPOSIA_PATH = paths.COMPOSIA_DIR
COMPOSIA_MUSICS_DIR = COMPOSIA_PATH / "compositions"
PROJECT_PATH = paths.PROJECTS_DIR / "calme_angoisse_problemes"
AUDIO_DIR = PROJECT_PATH / "audio"
SONS_DIR = PROJECT_PATH / "sons_de_fond"

def generer_musique(nom, prompt, duree_minutes=120):
    """Générer une musique avec ComposIA"""
    cmd = [
        sys.executable,
        str(COMPOSIA_PATH / "generate.py"),
        f'"{prompt}"',
        "--nom", nom,
        "--duree", str(duree_minutes),
        "--sans-apercu"
    ]
    print(f"\n  Generation: {nom}")
    print(f"  Prompt: {prompt}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def fusionner_musiques():
    """Fusionner toutes les musiques dans un seul fichier"""
    # Chercher toutes les musiques générées
    musiques = sorted(AUDIO_DIR.glob("musique_*.mp3"))
    if len(musiques) < 2:
        print(f"  Pas assez de musiques à fusionner: {len(musiques)}")
        return None

    print(f"\n  Fusion de {len(musiques)} musiques...")

    # Calculer le volume pour chaque musique
    volume_par_musique = round(1.0 / len(musiques), 3)
    volume_db = int(20 * 3.322 * volume_par_musique)  # log10(x) = log2(x) / log2(10) ≈ log2(x) / 3.322

    cmd = [str(paths.FFMPEG), "-y"]
    for m in musiques:
        cmd.extend(["-i", str(m)])

    # Créer le filtre de mixage
    filter_parts = []
    for i in range(len(musiques)):
        filter_parts.append(f"[{i}:a]volume={volume_par_musique:.2f}[m{i}]")

    mix_input = "".join(filter_parts)
    mix_parts = "".join(f"[m{i}]" for i in range(len(musiques)))
    filter_cmd = f"{mix_input}{mix_parts}amix=inputs={len(musiques)}:duration=longest[aout]"

    cmd.extend(["-filter_complex", filter_cmd, "-map", "[aout]"])
    cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
    output_path = AUDIO_DIR / "musique_fond_final.mp3"
    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        # Copier vers musique_fond.mp3
        dest = AUDIO_DIR / "musique_fond.mp3"
        shutil.copy(output_path, dest)
        print(f"    Fichier final: musique_fond_final.mp3 ({output_path.stat().st_size / 1024:.0f} KB)")
        return str(output_path)
    else:
        print(f"    Erreur: {result.stderr[-200:]}")
        return None

def main():
    print("=" * 60)
    print("GENERATION DE 10 MUSIQUES DE FOND")
    print("=" * 60)

    sujet = "calmer les peurs et chasser l'angoisse dans les problemes"
    type_contenu = "priere"

    # 10 prompts variés pour varier les musiques
    prompts = [
        "Fais-moi une musique douce et apaisante pour une prière du soir, piano acoustique et cordes douces, tempo 60 BPM",
        "Crée une musique instrumentale calme avec pad chaud et cordes, pour méditation et prière, tempo 65 BPM",
        "Mélodie relaxante avec piano léger et flute, pour calme et paix intérieure, tempo 58 BPM",
        "Musique paisible avec orgue doux et cordes, pour prière solennelle, tempo 68 BPM",
        "Composition douce avec epiano et pad atmosphérique, pour prière intime, tempo 62 BPM",
        "Musique relaxante avec piano seul et cordes très douces, pour méditation profonde, tempo 55 BPM",
        "Instrumentale calme avec piano et cloches, pour prière du matin, tempo 64 BPM",
        "Musique douce avec cordes chaudes et basse douce, pour prière de gratitude, tempo 66 BPM",
        "Composition apaisante avec piano et pad léger, pour prière de protection, tempo 63 BPM",
        "Mélodie relaxante avec piano, cordes et flute douce, pour sommeil paisible, tempo 59 BPM"
    ]

    # Générer les 10 musiques
    for i, prompt in enumerate(prompts, 1):
        nom = f"musique_{i:02d}"
        result = generer_musique(nom, prompt, duree_minutes=2)

        if result.returncode == 0:
            # Copier la musique dans audio/
            source_musique = COMPOSIA_MUSICS_DIR / nom / "composition.mp3"
            dest_musique = AUDIO_DIR / f"{nom}.mp3"

            if source_musique.exists():
                shutil.copy(source_musique, dest_musique)
                print(f"    {nom} OK")

                # Copier dans sons_de_fond
                if not SONS_DIR.exists():
                    SONS_DIR.mkdir(parents=True)

                for fichier in (COMPOSIA_MUSICS_DIR / nom).glob("*"):
                    if fichier.is_file():
                        shutil.copy(fichier, SONS_DIR / fichier.name)
                print(f"    Copié dans sons_de_fond/")
            else:
                print(f"    {nom} ECHEC - fichier non trouvé")
        else:
            print(f"    {nom} ECHEC - {result.stderr[-100:]}")

    # Fusionner les musiques
    print("\n" + "=" * 60)
    fusionner_musiques()
    print("=" * 60)

if __name__ == "__main__":
    main()
