# -*- coding: utf-8 -*-
"""
composia_config.py — Configuration de la musique de fond pour ComposIA

Fonctionnalités :
- Configurer la musique avant le lancement du pipeline
- Mode IA automatique ou configuration manuelle
- Prévisualisation des choix
"""

import json
import os
import sys
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

# ============================================================
# Fichier de configuration par projet
# ============================================================

def get_composia_config_path(project_path: str) -> str:
    """Retourne le chemin du fichier de config ComposIA pour un projet"""
    return os.path.join(project_path, "composia_config.json")


def charger_config(project_path: str) -> dict:
    """Charger la configuration ComposIA d'un projet"""
    config_path = get_composia_config_path(project_path)
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def sauvegarder_config(project_path: str, config: dict):
    """Sauvegarder la configuration ComposIA"""
    config_path = get_composia_config_path(project_path)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ============================================================
# Styles de musique prédéfinis
# ============================================================

STYLES_MUSIQUE = {
    "1": {
        "label": "Prière / Méditation (douce)",
        "description": "Musique paisible, très douce, piano et cordes chaudes",
        "prompt": "Fais-moi une musique de fond très douce et apaisante pour une prière, piano acoustique et cordes douces, sans batterie, tempo 60 BPM",
        "duree": 120,
        "instruments": ["piano", "cordes", "pad"],
        "style": "priere"
    },
    "2": {
        "label": "Prière / Méditation (organ)",
        "description": "Musique solennelle avec orgue et cordes",
        "prompt": "Fais-moi une musique de fond pieuse et solennelle avec orgue église, cordes douces et pad chaud, tempo 68 BPM",
        "duree": 120,
        "instruments": ["orgue", "cordes", "pad"],
        "style": "priere"
    },
    "3": {
        "label": "Louange / Joie",
        "description": "Musique joyeuse, entraînante, pour louange",
        "prompt": "Fais-moi une musique de fond joyeuse et uplifting pour une prière de louange, epiano, choeur léger, rythme doux, tempo 95 BPM",
        "duree": 90,
        "instruments": ["epiano", "choeur", "batterie_douce"],
        "style": "louange"
    },
    "4": {
        "label": "Gospel",
        "description": "Musique gospel avec chœur et rythme marqué",
        "prompt": "Fais-moi une musique de fond gospel avec choeur, epiano et batterie douce, tempo 80 BPM",
        "duree": 120,
        "instruments": ["epiano", "choeur", "batterie"],
        "style": "gospel"
    },
    "5": {
        "label": "Mélancolique / Réfléchi",
        "description": "Musique mélancolique, introspective, piano seul ou avec flute",
        "prompt": "Fais-moi une musique de fond mélancolique et introspective en mineur, piano acoustique seul ou avec flute douce, tempo lent 55 BPM",
        "duree": 150,
        "instruments": ["piano", "flute"],
        "style": "melancolique"
    },
    "6": {
        "label": "Storytelling (cinématique)",
        "description": "Musique cinematique, légère, pour narration",
        "prompt": "Fais-moi une musique de fond cinematique et légère pour une histoire/narration, cordes douces, pad atmosphérique, sans batterie, tempo modéré",
        "duree": 180,
        "instruments": ["cordes", "pad", "cloche"],
        "style": "meditation"
    },
    "7": {
        "label": "Config personnalisée",
        "description": " Configure tes propres paramètres",
        "prompt": None,
        "duree": None,
        "instruments": None,
        "style": None
    }
}


# ============================================================
# Configuration automatique selon le type de contenu
# ============================================================

def generer_prompt_automatique(sujet: str, type_contenu: str, langue: str) -> str:
    """
    Générer automatiquement un prompt de composition selon le type de contenu
    """
    # Analyser le sujet pour adapter la musique
    sujet_lower = sujet.lower()

    # Détection de thèmes
    if any(mot in sujet_lower for mot in ["prière", "saint", "dieu", "jésus", "marie"]):
        type_theme = "religieux"
    elif any(mot in sujet_lower for mot in ["histoire", "récit", "conte", "documentaire"]):
        type_theme = "histoire"
    elif any(mot in sujet_lower for mot in ["calme", "paix", "sommeil", "relax"]):
        type_theme = "calme"
    elif any(mot in sujet_lower for mot in ["joie", "louange", "bénédiction", "gratitude"]):
        type_theme = "joie"
    else:
        type_theme = "general"

    # Configuration par type
    config = {
        "religieux": {
            "prompt": "Fais-moi une musique de fond pieuse et solennelle pour une prière, avec organ ou piano",
            "style": "priere",
            "duree": 120,
            "batterie": False
        },
        "histoire": {
            "prompt": "Fais-moi une musique de fond cinematique et narrative pour une histoire, tempo modéré",
            "style": "meditation",
            "duree": 150,
            "batterie": False
        },
        "calme": {
            "prompt": "Fais-moi une musique de fond très calme et apaisante pour un sommeil paisible",
            "style": "meditation",
            "duree": 180,
            "batterie": False
        },
        "joie": {
            "prompt": "Fais-moi une musique de fond joyeuse et uplifting pour une prière de louange",
            "style": "louange",
            "duree": 90,
            "batterie": True
        },
        "general": {
            "prompt": "Fais-moi une musique de fond agréable et harmonieuse pour une vidéo",
            "style": "priere",
            "duree": 120,
            "batterie": False
        }
    }

    cfg = config.get(type_theme, config["general"])
    return cfg


# ============================================================
# Interface de configuration
# ============================================================

def configurer_musique_interactive(project_path: str) -> dict:
    """
    Configurer la musique de fond de façon interactive (avant le pipeline)
    Retourne la configuration complète
    """
    import sys
    sys.path.insert(0, str(paths.MODULES_DIR / "utils"))
    from timeout_input import choisir_avec_timeout

    print("\n" + "="*60)
    print("  CONFIGURATION MUSIQUE DE FOND (ComposIA)")
    print("="*60)

    # Lire le projet
    pjson = os.path.join(project_path, "project.json")
    with open(pjson, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    sujet = data.get("sujet", "")
    type_contenu = data.get("type_contenu", "priere")
    langue = data.get("langue", "fr")

    print(f"\nProjet : {sujet}")
    print(f"Type : {type_contenu} ({langue})")

    # Choix du mode
    print("\n" + "-"*40)
    print("MODE DE GENERATION")
    print("-"*40)
    print("[1] IA automatique - Je donne le sujet et ComposIA compose")
    print("[2] Configuration manuelle - Je spécifie mes instructions")

    choix_mode = choisir_avec_timeout(
        {"1": "IA automatique", "2": "Configuration manuelle"},
        "1",
        10,
        "Choisir mode"
    )

    # Configuration
    config = {
        "actif": True,
        "mode": "auto" if choix_mode == "1" else "manuel",
        "projet_path": project_path
    }

    if choix_mode == "1":
        # Mode automatique
        print("\n" + "-"*40)
        print("CONFIGURATION AUTOMATIQUE")
        print("-"*40)

        # Générer prompt automatique
        cfg_auto = generer_prompt_automatique(sujet, type_contenu, langue)

        print(f"\nPrompt généré : {cfg_auto['prompt']}")
        print(f"Style : {cfg_auto['style']}")
        print(f"Durée : {cfg_auto['duree']}s")

        # Demander confirmation ou modification
        print("\n[1] Valider ce prompt")
        print("[2] Modifier le prompt")

        choix = choisir_avec_timeout({"1": "Valider", "2": "Modifier"}, "1", 10, "Confirmation")
        if choix == "2":
            user_prompt = input("\nTa description de la musique : ").strip()
            cfg_auto["prompt"] = user_prompt

        config["prompt"] = cfg_auto["prompt"]
        config["duree_cible"] = cfg_auto["duree"]
        config["style"] = cfg_auto.get("style", "priere")
        config["avec_batterie"] = cfg_auto.get("batterie", False)

    else:
        # Mode manuel
        print("\n" + "-"*40)
        print("CONFIGURATION MANUELLE")
        print("-"*40)

        print("\nDécris la musique que tu veux (en français) :")
        print("Exemple : 'piano seul, très calme, pour prière du soir'")
        prompt = input("> ").strip()
        if not prompt:
            prompt = "Fais-moi une musique de fond paisible"

        print("\nDurée cible en secondes (ex: 120 pour 2 min) :")
        duree_input = input("> ").strip()
        duree_cible = int(duree_input) if duree_input.isdigit() else 120

        print("\nAvec batterie/rythme ? (o/n)")
        with_batterie = input("> ").strip().lower()
        avec_batterie = with_batterie in ("o", "oui", "y", "yes")

        config["prompt"] = prompt
        config["duree_cible"] = duree_cible
        config["avec_batterie"] = avec_batterie

    # Sauvegarder
    sauvegarder_config(project_path, config)

    print("\n" + "="*60)
    print("  CONFIGURATION SAUVEGARDEE")
    print("="*60)
    print(f"Mode : {'IA automatique' if choix_mode == '1' else 'Manuel'}")
    print(f"Prompt : {config['prompt']}")
    print(f"Durée : {config['duree_cible']}s")
    print(f"Batterie : {'Oui' if config['avec_batterie'] else 'Non'}")

    return config


def configurer_musique(project_path: str) -> dict:
    """
    Fonction principale : configurer la musique (sans interaction si déjà configuré)
    Si pas de config existante, créer une configuration automatique
    """
    config = charger_config(project_path)

    if not config:
        # Pas de config existante -> créer une configuration automatique
        print("\n[ComposIA] Configuration automatique...")
        pjson = os.path.join(project_path, "project.json")
        with open(pjson, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        cfg_auto = generer_prompt_automatique(
            data.get("sujet", ""),
            data.get("type_contenu", "priere"),
            data.get("langue", "fr")
        )

        config = {
            "actif": True,
            "mode": "auto",
            "prompt": cfg_auto["prompt"],
            "duree_cible": cfg_auto["duree"],
            "avec_batterie": cfg_auto.get("batterie", False),
            "style": cfg_auto.get("style", "priere"),
            "projet_path": project_path
        }
        sauvegarder_config(project_path, config)

    return config


def generer_musique_depuit_config(project_path: str, moteur: str = "fluidsynth") -> dict:
    """
    Générer la musique à partir de la configuration sauvegardée
    Retourne le résultat de la génération

    Args:
        project_path: Chemin du projet
        moteur: "fluidsynth" (défaut) ou "windows" pour utiliser le moteur MIDI de Windows
    """
    sys.path.insert(0, str(paths.MODULES_DIR / "audio"))
    from composia import generer_musique_fond, preparer_audio_pour_video

    config = charger_config(project_path)

    if not config or not config.get("actif", False):
        return {"succes": True, "note": "Musique désactivée"}

    print(f"\n[ComposIA] Génération de la musique de fond...")

    # Passer le moteur à composia.py pour utiliser le moteur MIDI de Windows
    result = generer_musique_fond(
        projet_path=project_path,
        prompt=config["prompt"],
        nom="musique_fond",
        duree_cible=config["duree_cible"],
        moteur=moteur
    )

    if result.get("succes") and result.get("mp3"):
        preparer_audio_pour_video(project_path, result["mp3"])

    return result


def generer_multiple_musiques(project_path: str, nb_musiques: int = 10) -> dict:
    """
    Générer plusieurs musiques de fond pour un projet (rotation automatique).
    Chaque musique est stockée dans sons_de_fond/ du projet et fusionnée dans un fichier final.

    Args:
        project_path: Chemin du projet
        nb_musiques: Nombre de musiques à générer (défaut: 10)

    Returns:
        dict: Résultat avec liste des musiques générées
    """
    import random
    import math

    sys.path.insert(0, str(paths.MODULES_DIR / "audio"))
    from composia import generer_musique_fond, preparer_audio_pour_video

    # Charger la config existante ou créer une par défaut
    config = charger_config(project_path)
    if not config:
        config = configurer_musique(project_path)

    # Lire le projet pour adapter les prompts
    pjson = os.path.join(project_path, "project.json")
    with open(pjson, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    sujet = data.get("sujet", "")
    type_contenu = data.get("type_contenu", "priere")
    duree_cible = config.get("duree_cible", 120)

    # Générer plusieurs prompts différents pour varier
    prompts_varies = [
        f"Fais-moi une musique douce et apaisante pour une prière : {sujet[:80]}",
        f"Crée une musique instrumentale calme et harmonieuse pour : {sujet[:80]}",
        f"Mélodie relaxante avec piano et cordes pour : {sujet[:80]}",
        f"Musique paisible pour méditation et prière : {sujet[:80]}",
        f"Composition douce avec pad et cordes pour : {sujet[:80]}",
        f"Musique douce et spiriteuelle pour une prière : {sujet[:80]}",
        f"Instrumentale calme pour fond de prière : {sujet[:80]}",
        f"Mélodie douce avec cordes chaudes pour : {sujet[:80]}",
        f"Musique relaxante et harmonieuse pour : {sujet[:80]}",
        f"Composition apaisante avec piano pour prière : {sujet[:80]}",
    ]

    # Limiter le nombre de musiques
    nb_musiques = min(nb_musiques, len(prompts_varies))

    print(f"\n[ComposIA] Génération de {nb_musiques} musiques de fond...")

    sons_dir = Path(project_path) / "sons_de_fond"
    sons_dir.mkdir(parents=True, exist_ok=True)

    musiques_generees = []
    seeds = [random.randint(0, 999999) for _ in range(nb_musiques)]

    # Dossier temporaire pour les musiques individuelles
    temp_dir = Path(project_path) / "temp_musiques"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for i, prompt in enumerate(prompts_varies[:nb_musiques], 1):
        nom_musique = f"musique_{i:02d}"
        print(f"\n  [{i}/{nb_musiques}] Génération de {nom_musique}...")

        result = generer_musique_fond(
            projet_path=project_path,
            prompt=prompt,
            nom=nom_musique,
            duree_cible=duree_cible
        )

        if result.get("succes") and result.get("mp3"):
            mp3_path = Path(result["mp3"])
            dest_path = Path(project_path) / "audio" / f"{nom_musique}.mp3"
            shutil.copy(mp3_path, dest_path)

            # Copier tous les fichiers dans sons_de_fond
            copier_fichiers_composition(project_path, dest_path)

            # Mettre à jour config
            config[f"musique_{i:02d}"] = {
                "nom": nom_musique,
                "prompt": prompt,
                "chemin": f"audio/{nom_musique}.mp3",
                "seed": seeds[i-1]
            }

            musiques_generees.append({
                "nom": nom_musique,
                "chemin": f"audio/{nom_musique}.mp3",
                "seed": seeds[i-1]
            })

            print(f"    {nom_musique} OK")

    # Fusionner toutes les musiques dans un fichier final
    print(f"\n[ComposIA] Fusion des musiques dans musique_fond_final.mp3...")

    # Utiliser FFmpeg pour mixer toutes les musiques
    all_audio_paths = [str(Path(project_path) / "audio" / f"musique_{i:02d}.mp3")
                      for i in range(1, nb_musiques + 1)
                      if (Path(project_path) / "audio" / f"musique_{i:02d}.mp3").exists()]

    if len(all_audio_paths) >= 2:
        # Calculer le volume pour chaque musique (inversément proportionnel au nombre)
        volume_per_music = round(1.0 / nb_musiques, 3)
        volume_db = int(20 * math.log10(volume_per_music)) if volume_per_music > 0 else -100

        # Créer la commande FFmpeg
        cmd = [str(paths.FFMPEG), "-y"]
        for audio_path in all_audio_paths:
            cmd.extend(["-i", audio_path])

        # Créer le filtre de mixage avec volume ajusté
        filter_parts = []
        for i in range(len(all_audio_paths)):
            filter_parts.append(f"[{i}:a]volume={volume_per_music:.2f}[m{i}]")

        mix_input = "".join(filter_parts)
        mix_parts = "".join(f"[m{i}]" for i in range(len(all_audio_paths)))
        filter_cmd = f"{mix_input}{mix_parts}amix=inputs={len(all_audio_paths)}:duration=longest:dropout_transition=0[aout]"

        cmd.extend(["-filter_complex", filter_cmd, "-map", "[aout]"])
        cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
        cmd.append(str(Path(project_path) / "audio" / "musique_fond_final.mp3"))

        result_fusion = subprocess.run(cmd, capture_output=True, text=True)

        if result_fusion.returncode == 0:
            print(f"    Musique fusionnée: musique_fond_final.mp3")
            # Copier la musique finale dans audio/
            final_path = Path(project_path) / "audio" / "musique_fond_final.mp3"
            dest_path = Path(project_path) / "audio" / "musique_fond.mp3"
            shutil.copy(final_path, dest_path)
            print(f"    Copié vers: musique_fond.mp3")

            # Copier dans sons_de_fond
            shutil.copy(final_path, sons_dir / "musique_fond_final.mp3")
        else:
            print(f"    Erreur fusion: {result_fusion.stderr[-200:]}")
    elif len(all_audio_paths) == 1:
        # Si seulement une musique, la copier directement
        shutil.copy(all_audio_paths[0], str(Path(project_path) / "audio" / "musique_fond.mp3"))
        print(f"    Une seule musique générée, copiée directement")
    else:
        print(f"    Aucune musique générée")

    # Sauvegarder config avec toutes les musiques
    config["musiques"] = {k: v for k, v in config.items() if k.startswith("musique_")}
    config["nb_musiques"] = len(musiques_generees)
    sauvegarder_config(project_path, config)

    print(f"\n[ComposIA] {nb_musiques} musiques générées et stockées dans sons_de_fond/")

    return {"succes": True, "musiques": musiques_generees}


def copier_fichiers_composition(projet_path, musique_path):
    """
    Copier tous les fichiers de la composition ComposIA dans le dossier sons_de_fond/ du projet.

    Args:
        projet_path: Chemin du projet
        musique_path: Chemin du fichier MP3 genere (pour determiner le dossier source)
    """
    projet_path = Path(projet_path)
    sons_dir = projet_path / "sons_de_fond"
    sons_dir.mkdir(parents=True, exist_ok=True)

    # Le dossier source est le parent du fichier musique (ex: musique_fond/)
    source_dir = musique_path.parent
    nom_composition = source_dir.name

    # Chercher le dossier de composition dans ComposIA/compositions/
    composia_compositions = paths.COMPOSITIONS_DIR
    source_compo = composia_compositions / nom_composition

    if source_compo.exists():
        print(f"  Copie des fichiers de composition depuis {source_compo}")

        # Copier tous les fichiers du dossier de composition
        for fichier in source_compo.iterdir():
            dest = sons_dir / fichier.name
            if fichier.is_file():
                shutil.copy(fichier, dest)
                print(f"    Copie: {fichier.name}")

        # Egalement copier dans sons_de_fond/composition.json pour reference
        json_ref = projet_path / f"{nom_composition}_composition.json"
        if json_ref.exists():
            shutil.copy(json_ref, sons_dir / "composition.json")
            print(f"    Copie: composition.json")

        print(f"  Fichiers de composition copies dans: sons_de_fond/")
    else:
        print(f"  Attention: Dossier de composition non trouve: {source_compo}")


# ============================================================
# Usage en ligne de commande
# ============================================================

def main():
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="Configuration de la musique de fond ComposIA pour StudioIA"
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=None,
        help="Chemin du projet StudioIA"
    )
    parser.add_argument(
        "--configurer",
        action="store_true",
        help="Forcer la configuration interactive"
    )
    parser.add_argument(
        "--generer",
        action="store_true",
        help="Générer la musique à partir de la config existante"
    )
    parser.add_argument(
        "--moteur",
        default="fluidsynth",
        choices=["fluidsynth", "windows"],
        help="Moteur de rendu audio: fluidsynth (défaut) ou windows"
    )
    parser.add_argument(
        "--desactiver",
        action="store_true",
        help="Désactiver la musique de fond"
    )

    args = parser.parse_args()

    if not args.project_path:
        parser.print_help()
        return 1

    project_path = args.project_path

    if args.desactiver:
        config = charger_config(project_path)
        config["actif"] = False
        sauvegarder_config(project_path, config)
        print(f"\n[ComposIA] Musique désactivée pour le projet {project_path}")
        return 0

    if args.generer:
        return generer_musique_depuit_config(project_path, moteur=args.moteur)

    # Si pas d'option spécifique, vérifier si config existe déjà
    config_existant = charger_config(project_path)

    if config_existant and not args.configurer:
        # Config existante -> générer directement
        print(f"\n[ComposIA] Configuration existante trouvée, génération...")
        return generer_musique_depuit_config(project_path, moteur=args.moteur)
    else:
        # Pas de config ou --configurer -> configuration interactive
        configurer_musique_interactive(project_path)
        # Puis générer
        return generer_musique_depuit_config(project_path, moteur=args.moteur)


if __name__ == "__main__":
    sys.exit(main())
