# -*- coding: utf-8 -*-
"""
composia.py - Intégration de ComposIA dans StudioIA
Génération automatique de musique de fond à partir d'un prompt.

Usage dans StudioIA :
    from modules.audio.composia import generer_musique_fond

    result = generer_musique_fond(
        projet_path="<dossier_projets>/mon_projet",
        prompt="Fais-moi une musique paisible pour une prière du soir",
        nom="musique_fond",
        duree_cible=180  # secondes
    )
"""

import sys
import os
import json
import subprocess
import shutil
import io
from pathlib import Path
from datetime import datetime

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# ============================================================
# Configuration
# ============================================================

# Chemin vers ComposIA (résolu depuis la racine de l'application)
COMPOSIA_PATH = paths.COMPOSIA_DIR

# Vérification des chemins
if not COMPOSIA_PATH.exists():
    raise FileNotFoundError(f"ComposIA non trouvé à : {COMPOSIA_PATH}")

OLLAMA_URL = "http://localhost:11434/api/chat"
SOUNDFONT_DEFAULT = COMPOSIA_PATH / "soundfonts" / "FluidR3_GM.sf2"
SOUNDFONT_ALTERNATIVE = COMPOSIA_PATH / "soundfonts" / "Arachno_SoundFont_Version_1.0.sf2"

# ============================================================
# Utilitaires
# ============================================================

def log(msg, level="INFO"):
    """Logger avec préfixe - sortie en UTF-8"""
    prefix = f"[COMPOSIA] {level}"
    # Gestion de l'encodage pour Windows
    try:
        print(f"{prefix}: {msg}")
    except UnicodeEncodeError:
        # Fallback pour Windows console
        msg_clean = msg.encode('utf-8', errors='replace').decode('utf-8')
        print(f"{prefix}: {msg_clean}")

def lire_json(path):
    """Lire un fichier JSON avec encodage utf-8-sig"""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    """Ecrire un fichier JSON avec encodage utf-8"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_ollama():
    """Verifier si Ollama est accessible"""
    try:
        import requests
        resp = requests.get("http://localhost:11434", timeout=3)
        return resp.status_code == 200
    except:
        return False

def check_fluidsynth():
    """Verifier si FluidSynth est installe"""
    return shutil.which("fluidsynth") is not None

def check_ffmpeg():
    """Verifier si FFmpeg est installe"""
    return shutil.which("ffmpeg") is not None

def trouver_soundfont():
    """Trouver une soundfont valide"""
    if SOUNDFONT_DEFAULT.exists():
        return str(SOUNDFONT_DEFAULT)
    if SOUNDFONT_ALTERNATIVE.exists():
        return str(SOUNDFONT_ALTERNATIVE)

    # Chercher toutes les .sf2 dans soundfonts/
    sf_dir = COMPOSIA_PATH / "soundfonts"
    if sf_dir.exists():
        sf_files = list(sf_dir.glob("*.sf2"))
        if sf_files:
            return str(sf_files[0])

    return None

# ============================================================
# Génération musicale
# ============================================================

def generer_json_composition(prompt, model="mistral", duree_minutes=None):
    """
    Generer la composition musicale via Ollama + ComposIA

    Args:
        prompt: Description de la musique souhaitée
        model: Modele Ollama a utiliser
        duree_minutes: Duree cible en minutes

    Returns:
        dict: Configuration de la composition (JSON)
    """
    sys.path.insert(0, str(COMPOSIA_PATH))

    try:
        import generate

        # Construire la demande complete avec duree si specifiee
        demande = prompt
        if duree_minutes:
            demande += f" (duree: {duree_minutes} minutes)"

        log(f"Interrogation de l'IA ({model})...")
        composition = generate.ask_musicien(demande, model=model)

        # Ajouter les metadonnees StudioIA
        composition["_composia_version"] = "1.0"
        composition["_genere_le"] = datetime.now().isoformat()
        composition["_prompt_initial"] = prompt

        log(f"Composition generee : {composition.get('tonalite')} {composition.get('mode')}, tempo {composition.get('tempo')} BPM")

        return composition

    except ImportError as e:
        log(f"Erreur d'import: {e}", "ERROR")
        raise RuntimeError("Impossible d'importer les modules ComposIA. Verifiez les dependances.") from e
    except Exception as e:
        log(f"Erreur lors de la generation: {e}", "ERROR")
        raise


def generer_sortie_sans_interaction(data, args, output_dir):
    """
    Generer les fichiers sans interaction utilisateur
    (version modifiee de generate.py generer_sortie)
    """
    sys.path.insert(0, str(COMPOSIA_PATH))

    from generate import compose_json_to_strudel
    from midi_export import build_midi, build_midi_par_instrument
    import mixage
    import random

    # Set seed for reproducibility
    seed = data.get("_seed", random.randint(0, 999999))
    random.seed(seed)
    data["_seed"] = seed

    instruments_actifs = [i for i in data["instruments"] if i.get("actif", True)]

    log(f"Tonalite: {data.get('tonalite')} {data.get('mode')}")
    log(f"Tempo: {data.get('tempo')} BPM")
    log(f"Style: {data.get('style')}")
    log(f"Instruments: {len(instruments_actifs)} actifs")

    # Generer le code Strudel
    code_strudel = compose_json_to_strudel(data)
    strudel_path = output_dir / "composition.strudel"
    strudel_path.write_text(code_strudel, encoding="utf-8")
    log(f"Strudel genere: {strudel_path.name}")

    # Export MIDI combine
    midi_path = output_dir / "composition.mid"
    _, cycles = build_midi(data, str(midi_path))
    log(f"MIDI combine: {midi_path.name} ({cycles} cycles)")

    # Export pistes MIDI separees
    pistes_dir = output_dir / "pistes"
    pistes = build_midi_par_instrument(data, str(pistes_dir))
    log(f"Pistes MIDI: {len(pistes)} pistes")

    # Rendu audio
    soundfont = args.soundfont or trouver_soundfont()

    if not soundfont:
        log("Aucune soundfont trouvée. Generation des fichiers MIDI uniquement.", "WARNING")
        return {
            "succes": True,
            "midi": str(midi_path),
            "strudel": str(strudel_path),
            "pistes": pistes,
            "audio": None,
            "warning": "Pas de soundfont disponible pour le rendu audio"
        }

    if not check_fluidsynth():
        log("FluidSynth non trouve. Generation des fichiers MIDI uniquement.", "WARNING")
        return {
            "succes": True,
            "midi": str(midi_path),
            "strudel": str(strudel_path),
            "pistes": pistes,
            "audio": None,
            "warning": "FluidSynth non installe pour le rendu audio"
        }

    # Nom du fichier audio de sortie (utilise args.nom pour nommage correct)
    nom_audio = getattr(args, 'nom', 'composition')

    # Gestion du moteur de rendu (FluidSynth ou Windows)
    if args.moteur == "windows":
        log("Rendu audio via le moteur MIDI de Windows...")
        try:
            import enregistrer_via_windows
            resultat = enregistrer_via_windows.exporter(
                str(midi_path), str(output_dir), args.peripherique, nom=nom_audio
            )
            if not resultat.get("succes"):
                log("Echec du rendu Windows", "WARNING")
                return {
                    "succes": True,
                    "midi": str(midi_path),
                    "strudel": str(strudel_path),
                    "pistes": pistes,
                    "audio": None,
                    "warning": "Echec du rendu Windows"
                }
            log(f"Audio genere (Windows): {resultat['wav']}")
            log(f"MP3 genere (Windows): {resultat['mp3']}")
            return {
                "succes": True,
                "midi": str(midi_path),
                "strudel": str(strudel_path),
                "pistes": pistes,
                "wav": resultat["wav"],
                "mp3": resultat["mp3"],
                "seed": seed,
                "moteur": "windows"
            }
        except Exception as e:
            log(f"Erreur moteur Windows: {e}", "WARNING")
            return {
                "succes": True,
                "midi": str(midi_path),
                "strudel": str(strudel_path),
                "pistes": pistes,
                "audio": None,
                "warning": str(e)
            }
    else:
        # Mode FluidSynth (défaut)
        log("Rendu audio (FluidSynth + FFmpeg)...")
        try:
            resultat = mixage.mixer_depuis_pistes_midi(
                pistes, str(output_dir), soundfont, nom=nom_audio
            )
            if resultat.get("succes"):
                log(f"Audio genere: {resultat['wav']}")
                log(f"MP3 genere: {resultat['mp3']}")
                return {
                    "succes": True,
                    "midi": str(midi_path),
                    "strudel": str(strudel_path),
                    "pistes": pistes,
                    "wav": resultat["wav"],
                    "mp3": resultat["mp3"],
                    "seed": seed
                }
            else:
                log("Echec du rendu audio", "WARNING")
                return {
                    "succes": True,
                    "midi": str(midi_path),
                    "strudel": str(strudel_path),
                    "pistes": pistes,
                    "audio": None,
                    "warning": "Echec du rendu audio"
                }
        except Exception as e:
            log(f"Erreur audio: {e}", "WARNING")
            return {
                "succes": True,
                "midi": str(midi_path),
                "strudel": str(strudel_path),
                "pistes": pistes,
                "audio": None,
                "warning": str(e)
            }


class Args:
    """Objet args simulé pour generate_sans_interaction"""
    def __init__(self):
        self.demande = None
        self.model = "mistral"
        self.nom = "musique_fond"
        self.duree = None
        self.no_audio = False
        self.soundfont = None
        self.reverb = "moyen"
        self.sans_apercu = True
        self.seed = None
        self.depuis_json = None
        self.moteur = "fluidsynth"
        self.peripherique = "Mixage stereo"


def generer_fichiers_composition(composition, projet_path, nom="composition", soundfont_path=None, moteur="fluidsynth", peripherique="Mixage stereo"):
    """
    Generer tous les fichiers MIDI et audio a partir d'une composition

    Args:
        composition: Dict de la composition generee par ask_musicien
        projet_path: Chemin du projet StudioIA
        nom: Nom de base pour les fichiers de sortie
        soundfont_path: Chemin optionnel vers une soundfont personnalisée
        moteur: "fluidsynth" (défaut) ou "windows" pour utiliser le moteur MIDI de Windows
        peripherique: Nom du périphérique de capture audio (uniquement pour moteur="windows")

    Returns:
        dict: Resultat avec chemins des fichiers generes
    """
    sys.path.insert(0, str(COMPOSIA_PATH))
    os.chdir(str(COMPOSIA_PATH))

    try:
        import generate
        fixer_progression = generate.fixer_progression
        dossier_pour_nom = generate.dossier_pour_nom
    except ImportError:
        from generate import fixer_progression, dossier_pour_nom

    # Fixer la progression une fois pour toutes
    composition = fixer_progression(composition)

    # Determiner le dossier de sortie
    dossier = dossier_pour_nom(nom)

    # Exporter le JSON de composition dans le projet
    projet_path = Path(projet_path)
    projet_path.mkdir(parents=True, exist_ok=True)
    json_compo_path = projet_path / f"{nom}_composition.json"
    json_compo_path.write_text(
        json.dumps(composition, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Creer le dossier de sortie s'il n'existe pas
    output_dir = dossier if dossier.exists() else (projet_path / "temp_composia" / nom)
    output_dir.mkdir(parents=True, exist_ok=True)

    log(f"Dossier de sortie: {output_dir}")

    # Creer args
    args = Args()
    args.soundfont = soundfont_path
    args.moteur = moteur
    args.peripherique = peripherique

    # Generer sans interaction
    return generer_sortie_sans_interaction(composition, args, output_dir)


def generer_musique_fond(projet_path, prompt, nom="musique_fond", model="mistral", duree_cible=None, soundfont_path=None, moteur="fluidsynth", peripherique="Mixage stereo"):
    """
    Fonction principale : generer une musique de fond complete a partir d'un prompt.

    Pipeline complet :
    1. Prompt -> Ollama -> JSON composition
    2. JSON -> MIDI (multi-pistes)
    3. MIDI -> Audio (WAV/MP3 avec reverberation)

    Args:
        projet_path: Chemin du projet StudioIA
        prompt: Description de la musique
        nom: Nom de base pour les fichiers de sortie
        model: Modele Ollama a utiliser
        duree_cible: Duree cible en secondes (optionnel)
        soundfont_path: Chemin personnalisé vers une soundfont
        moteur: "fluidsynth" (défaut) ou "windows" pour utiliser le moteur MIDI de Windows
        peripherique: Nom du périphérique de capture audio (uniquement pour moteur="windows")

    Returns:
        dict: Resultat contenant :
            - succes: bool
            - midi: chemin du fichier MIDI
            - mp3: chemin du fichier MP3
            - wav: chemin du fichier WAV
            - composition: JSON de la composition
            - prompt_initial: prompt original
            - metadata: metadonnees de generation
    """
    log(f"Debut de la generation musicale pour: {nom}")
    log(f"Prompt: {prompt}")
    log(f"Moteur: {moteur}")

    # Verification prealables
    if not check_ollama():
        log("Ollama n'est pas accessible. Verifiez qu'ollama serve tourne.", "ERROR")
        return {
            "succes": False,
            "error": "Ollama non accessible",
            "hint": "Lancez: ollama serve"
        }

    if not check_ffmpeg():
        log("FFmpeg n'est pas installe.", "ERROR")
        return {
            "succes": False,
            "error": "FFmpeg introuvable"
        }

    # Convertir duree_cible en minutes pour ComposIA
    duree_minutes = duree_cible / 60.0 if duree_cible else None

    # Etape 1: Generer la composition JSON via Ollama
    try:
        composition = generer_json_composition(
            prompt=prompt,
            model=model,
            duree_minutes=duree_minutes
        )
    except Exception as e:
        log(f"Echoec de la generation de la composition: {e}", "ERROR")
        return {"succes": False, "error": str(e)}

    # Sauvegarder la composition dans le projet
    projet_path = Path(projet_path)
    projet_path.mkdir(parents=True, exist_ok=True)

    composition_path = projet_path / f"{nom}_composition.json"
    composition_path.write_text(
        json.dumps(composition, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log(f"Composition sauvegardee: {composition_path}")

    # Etape 2: Generer les fichiers MIDI et audio
    try:
        result = generer_fichiers_composition(
            composition=composition,
            projet_path=str(projet_path),
            nom=nom,
            soundfont_path=soundfont_path,
            moteur=moteur,
            peripherique=peripherique
        )

        # Ajouter les metadonnees StudioIA
        result["prompt_initial"] = prompt
        result["projet_path"] = str(projet_path)
        result["nom"] = nom

        if result.get("succes"):
            log("Generation terminee avec succes!")
            if result.get("mp3"):
                log(f"MP3: {result['mp3']}")
            if result.get("midi"):
                log(f"MIDI: {result['midi']}")
        else:
            log("Generation echouee", "ERROR")

        return result

    except Exception as e:
        log(f"Erreur lors de la generation des fichiers: {e}", "ERROR")
        return {"succes": False, "error": str(e)}


def mettre_a_jour_project_json(projet_path, musique_path, nom_fichier="musique_fond.mp3"):
    """
    Mettre a jour le project.json avec le chemin de la musique generee.

    Args:
        projet_path: Chemin du projet
        musique_path: Chemin complet vers le fichier audio genere
        nom_fichier: Nom du fichier (par defaut musique_fond.mp3)
    """
    projet_path = Path(projet_path)
    project_json = projet_path / "project.json"

    if not project_json.exists():
        log("project.json non trouve, creation d'un fichier de base", "WARNING")
        project_json.write_text(json.dumps({
            "id": projet_path.name,
            "sujet": "",
            "statut": "en_cours",
            "etapes": {},
            "chapitres": [],
            "music_fond": f"audio/{nom_fichier}"
        }, indent=2), encoding="utf-8")
        return

    data = lire_json(project_json)
    data["music_fond"] = f"audio/{nom_fichier}"

    # Mettre a jour le statut si besoin
    if "etapes" not in data:
        data["etapes"] = {}
    data["etapes"]["musique_fond"] = "termine"

    ecrire_json(project_json, data)
    log(f"project.json mis a jour avec: music_fond = audio/{nom_fichier}")


def preparer_audio_pour_video(projet_path, musique_path, duree_cible=None):
    """
    Preparer une musique de fond pour une video StudioIA.

    Copie la musique dans le dossier audio/ du projet et met a jour project.json.
    Copie egalement tous les fichiers de la composition dans sons_de_fond/.

    Args:
        projet_path: Chemin du projet
        musique_path: Chemin du fichier MP3 genere
        duree_cible: Duree cible pour tronquer/ajuster (optionnel)
    """
    projet_path = Path(projet_path)
    audio_dir = projet_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Copier la musique en la renommant en musique_fond.mp3
    musique_path = Path(musique_path)
    dest_path = audio_dir / "musique_fond.mp3"

    log(f"Copie de {musique_path.name} vers audio/musique_fond.mp3")
    shutil.copy(musique_path, dest_path)

    # Mettre a jour project.json
    mettre_a_jour_project_json(str(projet_path), str(dest_path))

    # Copier tous les fichiers de la composition dans sons_de_fond/
    copier_fichiers_composition(projet_path, musique_path)

    log(f"Musique prete pour la video: audio/{musique_path.name}")


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
        log(f"Copie des fichiers de composition depuis {source_compo}")

        # Copier tous les fichiers du dossier de composition
        for fichier in source_compo.iterdir():
            dest = sons_dir / fichier.name
            if fichier.is_file():
                shutil.copy(fichier, dest)
                log(f"  Copie: {fichier.name}")

        # Egalement copier dans sons_de_fond/composition.json pour reference
        json_ref = projet_path / f"{nom_composition}_composition.json"
        if json_ref.exists():
            shutil.copy(json_ref, sons_dir / "composition.json")
            log(f"  Copie: composition.json")

        log(f"Fichiers de composition copies dans: sons_de_fond/")
    else:
        log(f"Dossier de composition non trouve: {source_compo}", "WARNING")


# ============================================================
# Usage interactif (lignes de commande)
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Generer une musique de fond pour StudioIA a partir d'un prompt."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Fais-moi une musique de fond paisible pour une priere",
        help="Prompt decrivant la musique souhaitée"
    )
    parser.add_argument(
        "--projet", "-p",
        default=None,
        help="Chemin du projet StudioIA (optionnel)"
    )
    parser.add_argument(
        "--nom", "-n",
        default="musique_fond",
        help="Nom de base pour les fichiers de sortie"
    )
    parser.add_argument(
        "--model", "-m",
        default="mistral",
        help="Modele Ollama a utiliser"
    )
    parser.add_argument(
        "--duree", "-d",
        type=float,
        default=None,
        help="Duree cible en minutes (ex: 2.5)"
    )
    parser.add_argument(
        "--soundfont", "-s",
        default=None,
        help="Chemin vers une soundfont personnalisée"
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Generer uniquement le fichier MIDI sans rendu audio"
    )

    args = parser.parse_args()

    # Determiner le chemin du projet
    if args.projet:
        projet_path = args.projet
    else:
        # Chercher un projet recent dans projects/
        projects_dir = paths.PROJECTS_DIR
        if projects_dir.exists():
            projects = list(projects_dir.iterdir())
            if projects:
                projet_path = str(projects[-1])
                log(f"Aucun projet specifie, utilisation de: {projet_path}")
            else:
                log(f"Aucun projet trouve dans {paths.PROJECTS_DIR}", "ERROR")
                return 1
        else:
            log("Dossier projects non trouve", "ERROR")
            return 1

    # Lancer la generation
    result = generer_musique_fond(
        projet_path=projet_path,
        prompt=args.prompt,
        nom=args.nom,
        model=args.model,
        duree_cible=int(args.duree * 60) if args.duree else None,
        soundfont_path=args.soundfont
    )

    if result.get("succes"):
        # Copier dans audio/ si MP3 disponible
        if result.get("mp3"):
            preparer_audio_pour_video(projet_path, result["mp3"])

        return 0
    else:
        log(f"Echec: {result.get('error', 'Erreur inconnue')}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
