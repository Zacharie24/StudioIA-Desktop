#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module de clonage de voix pour StudioIA
Permet de cloner une voix à partir d'un fichier audio et de l'utiliser pour la génération TTS.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

try:
    import torch
    import torchaudio
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

FFMPEG = "C:\\StudioIA\\tools\\ffmpeg\\ffmpeg.exe"
CLONED_VOICES_DIR = "C:\\tts-pentest\\cloned_voices"

def log(msg):
    print(f"[VOICE_CLONE] {msg}")

def preparer_audio_clonage(audio_path, output_path):
    """
    Prépare un fichier audio pour le clonage de voix :
    - Convertit en mono 16kHz
    - Normalise le volume
    - Coupe les silences excessifs
    """
    if not PYDUB_AVAILABLE:
        log("pydub non disponible, utilisation directe du fichier")
        shutil.copy(audio_path, output_path)
        return True

    try:
        # Charger l'audio
        audio = AudioSegment.from_file(audio_path)

        # Convertir en mono
        audio = audio.set_channels(1)

        # Échantillonage à 16kHz
        audio = audio.set_frame_rate(16000)

        # Normaliser le volume (-16dBFS est l'idéal pour TTS)
        target_dbfs = -16
        change_in_db = target_dbfs - audio.dBFS
        audio = audio.apply_gain(change_in_db)

        # Couper les silences excessifs en début/fin (plus de 2 secondes)
        non_silent_ranges = AudioSegment.silence.detect_nonsilent(
            audio, min_silence_len=1000, silence_thresh=-40
        )

        if non_silent_ranges:
            debut = max(0, non_silent_ranges[0][0] - 500)
            fin = min(len(audio), non_silent_ranges[-1][1] + 500)
            audio = audio[debut:fin]

        # Sauvegarder
        audio.export(output_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
        log(f"Audio préparé : {output_path}")
        return True

    except Exception as e:
        log(f"Erreur lors de la préparation : {e}")
        return False


def detecter_langue_audio(audio_path):
    """
    Détecte la langue d'un fichier audio via Whisper.
    """
    if not WHISPER_AVAILABLE:
        return "fr"

    try:
        model = whisper.load_model("small")
        result = model.transcribe(str(audio_path), language="fr")
        return result.get("language", "fr")
    except Exception as e:
        log(f"Détection langue impossible : {e}")
        return "fr"


def cloner_voix(nom_voix, audio_path, description=""):
    """
    Clone une voix à partir d'un fichier audio.

    Arguments :
        nom_voix : Nom de la voix clonée
        audio_path : Chemin du fichier audio (5-30 secondes recommandé)
        description : Description de la voix (genre, âge, style)

    Retourne :
        dict avec les informations de la voix clonée ou None en cas d'échec
    """
    if not TORCH_AVAILABLE:
        log("PyTorch non disponible - clonage impossible")
        return None

    log(f"Démarrage du clonage de voix : {nom_voix}")

    # Créer le dossier s'il n'existe pas
    os.makedirs(CLONED_VOICES_DIR, exist_ok=True)

    # Préparer le fichier
    audio_name = Path(audio_path).stem
    output_path = os.path.join(CLONED_VOICES_DIR, f"{audio_name}_cloned.wav")

    if not preparer_audio_clonage(audio_path, output_path):
        log("Échec de la préparation de l'audio")
        return None

    # Créer le fichier de metadata
    voix_meta = {
        "key": f"xtts_clone_{audio_name.lower().replace(' ', '_')}",
        "name": nom_voix,
        "description": description,
        "sample_path": output_path,
        "gender": "Unknown",
        "langue": detecter_langue_audio(output_path),
        "date_clonage": datetime.now().isoformat(),
        "duree_secondes": 0
    }

    # Calculer la durée
    try:
        audio = AudioSegment.from_file(output_path)
        voix_meta["duree_secondes"] = len(audio) / 1000
    except:
        pass

    # Sauvegarder la metadata
    meta_path = os.path.join(CLONED_VOICES_DIR, f"{audio_name}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(voix_meta, f, indent=2, ensure_ascii=False)

    log(f"Voix clonée créée : {nom_voix}")
    log(f"  Fichier : {output_path}")
    log(f"  Metadata : {meta_path}")

    return voix_meta


def lister_voix_clonees():
    """
    List toutes les voix clonées disponibles.
    """
    voix = []

    if not os.path.exists(CLONED_VOICES_DIR):
        return voix

    for fichier in os.listdir(CLONED_VOICES_DIR):
        if fichier.endswith("_meta.json"):
            try:
                with open(os.path.join(CLONED_VOICES_DIR, fichier), "r", encoding="utf-8") as f:
                    voix.append(json.load(f))
            except:
                continue

    return voix


def supprimer_voix_clonee(key):
    """
    Supprime une voix clonée et ses fichiers associés.
    """
    voix = lister_voix_clonees()
    for v in voix:
        if v.get("key") == key:
            try:
                os.remove(v.get("sample_path"))
                meta_path = v.get("sample_path").replace("_cloned.wav", "_meta.json")
                if os.path.exists(meta_path):
                    os.remove(meta_path)
                log(f"Voix supprimée : {v.get('name')}")
                return True
            except Exception as e:
                log(f"Erreur suppression : {e}")
                return False
    return False


def mettre_a_jour_config_xtts():
    """
    Met à jour le fichier voix_config.py avec les voix clonées.
    """
    voix_clonees = lister_voix_clonees()

    config_path = "C:\\StudioIA\\modules\\tts\\voix_config.py"

    with open(config_path, "r", encoding="utf-8") as f:
        contenu = f.read()

    # Construire la liste des voix clonées
    voix_clonées_list = []
    for v in voix_clonees:
        voix_clonées_list.append({
            "key": v["key"],
            "sample_path": v["sample_path"],
            "name": v["name"],
            "gender": v.get("gender", "Unknown")
        })

    # Mettre à jour le fichier
    nouveau_contenu = contenu.split("# === VOIX CLONÉES ===")[0]
    if len(contenu.split("# === VOIX CLONÉES ===")) > 1:
        nouveau_contenu += "# === VOIX CLONÉES ===\n"

    if voix_clonées_list:
        nouveau_contenu += 'CLONED_VOICES = [\n'
        for v in voix_clonées_list:
            nouveau_contenu += f'    {{"key": "{v["key"]}", "sample_path": r"{v["sample_path"]}", "name": "{v["name"]}", "gender": "{v["gender"]}"}},\n'
        nouveau_contenu += ']\n\n'
    else:
        nouveau_contenu += 'CLONED_VOICES = []\n\n'

    nouveau_contenu += contenu.split("# === FIN VOIX CLONÉES ===")[0]
    if len(contenu.split("# === FIN VOIX CLONÉES ===")) > 1:
        nouveau_contenu += "# === FIN VOIX CLONÉES ===\n"

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(nouveau_contenu)

    log("Configuration XTTS mise à jour")
