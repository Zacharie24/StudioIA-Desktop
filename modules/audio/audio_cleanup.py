# -*- coding: utf-8 -*-
"""
audio_cleanup.py — Nettoyage audio intelligent

Fonctionnalités :
- Gate adaptatif : analyse les niveaux dB et applique un gate intelligent
- Détection d'artefacts : repère les pics/bruits anormaux via numpy/scipy
- Pipeline complet de nettoyage

Dépendances : numpy, scipy, ffmpeg
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

FFMPEG = "C:\\StudioIA\\tools\\ffmpeg\\ffmpeg.exe"


def log(msg):
    print(f"[AUDIO_CLEANUP] {msg}")


def lire_config():
    """Lire la config globale"""
    cfg_path = "C:\\StudioIA\\config.json"
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


# ============================================================
# Analyse des niveaux dB
# ============================================================

def analyser_niveaux_db(audio_path: str) -> dict:
    """
    Analyser les niveaux audio avec FFmpeg volumedetect

    Args:
        audio_path: Chemin du fichier audio (wav, mp3, etc.)

    Returns:
        dict: stats avec mean_volume, max_volume, min_volume, histogram
    """
    cmd = [
        FFMPEG, "-i", audio_path,
        "-af", "volumedetect",
        "-f", "null", "NUL"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    stats = {
        "mean_volume": -30.0,
        "max_volume": 0.0,
        "min_volume": -60.0,
        "histogram": {}
    }

    for line in result.stderr.split("\n"):
        line = line.strip()
        if "mean_volume" in line:
            try:
                stats["mean_volume"] = float(line.split(":")[1].strip().replace(" dB", ""))
            except:
                pass
        elif "max_volume" in line:
            try:
                stats["max_volume"] = float(line.split(":")[1].strip().replace(" dB", ""))
            except:
                pass
        elif "min_volume" in line:
            try:
                stats["min_volume"] = float(line.split(":")[1].strip().replace(" dB", ""))
            except:
                pass
        elif "histogram" in line:
            try:
                parts = line.split(":", 1)[1].strip()
                db_val = float(parts.split("dB")[0].strip())
                count = int(parts.split(":")[-1].strip())
                stats["histogram"][db_val] = count
            except:
                pass

    return stats


def calculer_seuil_gate(stats: dict, sensitivity: float = 0.5) -> float:
    """
    Calculer le seuil du gate adaptativement selon les stats dB

    Args:
        stats: Résultat de analyser_niveaux_db()
        sensitivity: 0.0 (peu agressif) à 1.0 (très agressif)

    Returns:
        float: Seuil du gate en dB (ex: -18.5)
    """
    mean_vol = stats.get("mean_volume", -30.0)

    # Le seuil est calculé par rapport au volume moyen
    # Plus la sensibilité est haute, plus on coupe proche du niveau moyen
    if sensitivity >= 0.8:
        offset = 3  # Très agressif : coupe à 3 dB sous la moyenne
    elif sensitivity >= 0.5:
        offset = 6  # Modéré : coupe à 6 dB sous la moyenne
    elif sensitivity >= 0.3:
        offset = 10  # Léger : coupe à 10 dB sous la moyenne
    else:
        offset = 15  # Très léger : coupe à 15 dB sous la moyenne

    seuil = mean_vol + offset
    # Ne pas dépasser -10 dB pour éviter de couper la parole
    seuil = max(seuil, -10.0)

    log(f"Volume moyen: {mean_vol:.1f} dB → Seuil gate: {seuil:.1f} dB (sensibilité: {sensitivity})")
    return seuil


def get_gate_filter(config: dict = None) -> str:
    """
    Générer la chaîne de filtre gate FFmpeg

    Gate LÉGER : coupe uniquement le bruit de fond très bas (sous -40dB).
    Ne touche PAS à la parole.

    Args:
        config: Configuration avec gate_enabled, gate_sensitivity, etc.

    Returns:
        str: Chaîne de filtre ou chaîne vide si désactivé
    """
    if config is None:
        config = lire_config()

    if not config.get("gate_enabled", True):
        return ""

    sensitivity = config.get("gate_sensitivity", 0.5)
    attack = config.get("gate_attack", 0.01)
    release = config.get("gate_release", 0.5)

    # SEUIL EXTREMEMENT LEGER : couper uniquement le silence/bruit de fond
    # La parole est typiquement entre -30dB et -50dB
    # On met le gate à -40dB pour ne JAMAIS couper la parole
    # sensitivity 0.0 = -45dB (ultra léger), 1.0 = -35dB (encore léger)
    seuil_gate = -45 + (sensitivity * 10)  # -45 à -35 selon sensibilité

    gate = f"agate=threshold={seuil_gate:.0f}dB:attack={attack}:release={release}:makeup=1.0"

    # PAS de silenceremove — il coupe la parole trop agressivement
    # On garde juste le gate léger pour les vrais silences
    log(f"Gate filtre (léger): {gate}")
    return gate


# ============================================================
# Détection et correction d'artefacts (numpy + scipy)
# ============================================================

def detecter_artefacts(audio_path: str, zscore_threshold: float = 3.0) -> list:
    """
    Détecter les artefacts audio (clics, pops, bruits anormaux)

    Utilise numpy + scipy pour analyser le signal par fenêtres
    et repérer les pics RMS anormaux.

    Args:
        audio_path: Chemin du fichier WAV
        zscore_threshold: Seuil z-score pour considérer un artefact (defaut: 3.0)

    Returns:
        list: Liste de dicts {start, end, rms, zscore} par artefact
    """
    try:
        import numpy as np
        from scipy.io import wavfile
        from scipy import signal
    except ImportError as e:
        log(f"numpy/scipy non disponible: {e}")
        return []

    if not os.path.exists(audio_path):
        log(f"Fichier non trouvé: {audio_path}")
        return []

    # Essayer de lire le WAV (si MP3, convertir d'abord)
    try:
        sr, data = wavfile.read(audio_path)
    except Exception:
        # Convertir en WAV temporairement
        log(f"Conversion en WAV pour analyse...")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        cmd = [FFMPEG, "-y", "-i", audio_path, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", tmp_wav]
        subprocess.run(cmd, capture_output=True, text=True)
        try:
            sr, data = wavfile.read(tmp_wav)
        except Exception as e:
            log(f"Erreur lecture audio: {e}")
            os.unlink(tmp_wav)
            return []
        os.unlink(tmp_wav)

    # Si stéréo, convertir en mono
    if len(data.shape) > 1:
        data = np.mean(data, axis=1).astype(np.int16)

    # Normaliser en float entre -1 et 1
    if data.dtype == np.int16:
        data_float = data / 32768.0
    elif data.dtype == np.int32:
        data_float = data / 2147483648.0
    else:
        data_float = data.astype(np.float64) / np.max(np.abs(data))

    # Fenêtrage : fenêtres de 0.3s avec overlap 0.15s
    window_size = int(0.3 * sr)
    hop_size = int(0.15 * sr)

    if len(data_float) < window_size:
        log(f"Audio trop court pour l'analyse")
        return []

    # Calculer RMS par fenêtre
    n_windows = (len(data_float) - window_size) // hop_size + 1
    rms_values = []
    timestamps = []

    for i in range(n_windows):
        start = i * hop_size
        end = start + window_size
        if end > len(data_float):
            break
        segment = data_float[start:end]
        rms = np.sqrt(np.mean(segment ** 2))
        rms_values.append(rms)
        timestamps.append(start / sr)

    rms_values = np.array(rms_values)

    # Éviter la division par zéro
    if np.std(rms_values) < 1e-10:
        log(f"Signal trop uniforme, pas d'artefacts détectés")
        return []

    # Calculer z-scores
    mean_rms = np.mean(rms_values)
    std_rms = np.std(rms_values)
    zscores = (rms_values - mean_rms) / std_rms

    # Détecter les artefacts
    artefacts = []
    in_artefact = False
    artefact_start = 0

    for i, z in enumerate(zscores):
        if abs(z) > zscore_threshold:
            if not in_artefact:
                artefact_start = timestamps[i]
                in_artefact = True
        else:
            if in_artefact:
                artefacts.append({
                    "start": artefact_start,
                    "end": timestamps[i],
                    "rms": float(rms_values[i]),
                    "zscore": float(z)
                })
                in_artefact = False

    # Fermer le dernier artefact si encore ouvert
    if in_artefact and timestamps:
        artefacts.append({
            "start": artefact_start,
            "end": timestamps[-1],
            "rms": float(rms_values[-1]),
            "zscore": float(zscores[-1])
        })

    # Filtrer : ne garder que les artefacts très courts (< 1s) = clics/pops
    # ou les artefacts qui sont des pics POSITIFS (bruit fort) et pas juste du silence
    artefacts = [a for a in artefacts
                 if (a["end"] - a["start"] < 1.0 and a["zscore"] > 0)
                 or (a["zscore"] > 3.0 and a["end"] - a["start"] < 2.0)]

    log(f"   {len(artefacts)} artefacts détectés (seuil z-score: {zscore_threshold})")
    return artefacts


def corriger_artefacts(input_path: str, output_path: str, artefacts: list, padding: float = 0.05) -> bool:
    """
    Corriger les artefacts en les remplaçant par des fades progressifs

    Utilise FFmpeg pour appliquer des 'volume' fades sur les zones d'artefacts.

    Args:
        input_path: Chemin du fichier audio source
        output_path: Chemin du fichier de sortie
        artefacts: Liste des artefacts de detecter_artefacts()
        padding: Secondes de padding avant/après l'artefact

    Returns:
        bool: True si succès
    """
    if not artefacts:
        log("Aucun artefact à corriger")
        return False

    # Construire un filtre volume pour chaque artefact
    # On crée des curves de volume : volume=0 aux artefacts, 1 ailleurs
    duration_cmd = [FFMPEG, "-i", input_path, "-f", "null", "NUL"]
    result = subprocess.run(duration_cmd, capture_output=True, text=True)

    # Extraire la durée totale
    duree = 0
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            try:
                t = line.strip().split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                duree = float(h) * 3600 + float(m) * 60 + float(s)
            except:
                pass

    if duree <= 0:
        log("Impossible de déterminer la durée, copie simple")
        import shutil
        shutil.copy(input_path, output_path)
        return True

    # Construire les segments de volume
    # Format: volume=0 entre start et end, volume=1 ailleurs
    volume_points = []
    volume_points.append((0, 1))  # Début

    for a in artefacts:
        s = max(0, a["start"] - padding)
        e = min(duree, a["end"] + padding)

        # Fade out
        volume_points.append((s, 1))
        volume_points.append((s + 0.01, 0))
        # Zone silencieuse
        volume_points.append((e - 0.01, 0))
        volume_points.append((e, 1))

    volume_points.append((duree, 1))  # Fin

    # Convertir en expression volume
    # On utilise une approche plus simple : segmented volume=0 sur chaque artefact
    filter_parts = []
    prev_end = 0

    # Trier les artefacts par start
    artefacts_sorted = sorted(artefacts, key=lambda a: a["start"])

    # Créer un filtre avec volume=0 sur chaque artefact (avec padding)
    for i, a in enumerate(artefacts_sorted):
        s = max(0, a["start"] - padding)
        e = min(duree, a["end"] + padding)

        if i == 0 and s > 0:
            filter_parts.append(f"volume=enable='between(t,0,{s})':volume=1")

        filter_parts.append(f"volume=enable='between(t,{s},{e})':volume=0")

        if i < len(artefacts_sorted) - 1:
            next_s = artefacts_sorted[i + 1]["start"] - padding
            if e < next_s:
                filter_parts.append(f"volume=enable='between(t,{e},{next_s})':volume=1")
        else:
            if e < duree:
                filter_parts.append(f"volume=enable='between(t,{e},{duree})':volume=1")

    if not filter_parts:
        log("Aucun filtre à appliquer")
        return False

    # Appliquer le volume filter
    volume_filter = ",".join(filter_parts)

    cmd = [
        FFMPEG, "-y", "-i", input_path,
        "-af", volume_filter,
        "-acodec", "pcm_s16le",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"Erreur correction artefacts: {result.stderr[-200:]}")
        return False

    log(f"   {len(artefacts)} artefacts corrigés dans {os.path.basename(output_path)}")
    return True


# ============================================================
# Pipeline complet
# ============================================================

def nettoyer_audio_complet(input_path: str, output_path: str, config: dict = None) -> dict:
    """
    Pipeline complet de nettoyage audio :
    1. Gate adaptatif (FFmpeg)
    2. Détection artefacts (numpy)
    3. Correction artefacts (FFmpeg)

    Args:
        input_path: Chemin du fichier audio source
        output_path: Chemin du fichier de sortie
        config: Configuration globale (ou None pour lire depuis config.json)

    Returns:
        dict: Résultat du nettoyage
    """
    if config is None:
        config = lire_config()

    result = {
        "succes": True,
        "gate_applique": False,
        "artefacts_detectes": 0,
        "artefacts_corriges": False,
        "fichier": output_path
    }

    fichier_courant = input_path

    # Étape 1 : Gate
    if config.get("gate_enabled", True):
        log("=== Étape 1/3 : Gate adaptatif ===")
        gate_filter = get_gate_filter(config)
        if gate_filter:
            temp_gate = output_path.replace(".wav", "_gate_temp.wav") if output_path != input_path else output_path + ".gate.wav"
            cmd = [
                FFMPEG, "-y", "-i", fichier_courant,
                "-af", gate_filter,
                "-acodec", "pcm_s16le",
                temp_gate
            ]
            subprocess.run(cmd, capture_output=True, text=True)
            if os.path.exists(temp_gate):
                fichier_courant = temp_gate
                result["gate_applique"] = True
                log(f"   Gate appliqué → {os.path.basename(temp_gate)}")

    # Étape 2 : Détection + correction artefacts
    if config.get("gate_enabled", True):  # Même toggle pour les artefacts
        log("=== Étape 2/3 : Détection artefacts ===")
        artefacts = detecter_artefacts(fichier_courant, zscore_threshold=3.0)
        result["artefacts_detectes"] = len(artefacts)

        if len(artefacts) >= 3:
            log(f"   {len(artefacts)} artefacts détectés, correction en cours...")
            # Toujours convertir en WAV pour la correction
            temp_corrige = output_path.replace(".wav", "_artefacts_corrige.wav") if output_path != input_path else output_path + ".fix.wav"
            ok = corriger_artefacts(fichier_courant, temp_corrige, artefacts)
            if ok and os.path.exists(temp_corrige):
                fichier_courant = temp_corrige
                result["artefacts_corriges"] = True
                log(f"   Artefacts corrigés → {os.path.basename(temp_corrige)}")
        elif len(artefacts) > 0:
            log(f"   {len(artefacts)} artefacts mineurs ignorés (< 3)")
        else:
            log(f"   Aucun artefact détecté")

    # Étape 3 : Copie finale si nécessaire
    if fichier_courant != output_path:
        import shutil
        shutil.copy(fichier_courant, output_path)
        log(f"   Fichier final: {os.path.basename(output_path)}")

        # Nettoyer fichiers temporaires
        for f in [fichier_courant]:
            if f != input_path and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

    result["succes"] = os.path.exists(output_path)
    return result


def get_combined_audio_filter(config: dict = None) -> str:
    """
    Générer la chaîne de filtre audio combinée (denoiser + gate)
    pour utilisation directe dans les commandes FFmpeg.

    CORRECTION : denoiser ultra-léger, gate très léger, PAS de silenceremove.
    L'objectif est de garder la voix claire et audible, pas de tout couper.

    Args:
        config: Configuration

    Returns:
        str: Chaîne de filtre ou chaîne vide
    """
    if config is None:
        config = lire_config()

    filters = []

    # 1. Denoiser ULTRA-LÉGER : juste le bruit de fond très bas
    # highpass à 60Hz (pas 80 — on garde les basses de la voix)
    # afftdn avec nf=-40 (pas -25 — on ne coupe que le bruit très faible)
    if config.get("denoiser_enabled", True):
        strength = config.get("denoiser_strength", "light")
        # NOUVEAUX seuils beaucoup plus conservateurs
        nf_map = {"light": "-42", "medium": "-38", "strong": "-35"}
        nf = nf_map.get(strength, "-42")
        # highpass=60 garde les basses naturelles de la voix
        filters.append(f"highpass=f=60,afftdn=nf={nf}:nt=w")

    # 2. Gate TRÈS LÉGER : coupe uniquement le vrai silence/bruit de fond
    # Seuil à -40dB — la parole est rarement en dessous
    if config.get("gate_enabled", True):
        sensitivity = config.get("gate_sensitivity", 0.3)  # 0.3 au lieu de 0.5
        attack = config.get("gate_attack", 0.05)  # 0.05 au lieu de 0.01 (plus doux)
        release = config.get("gate_release", 0.8)  # 0.8 au lieu de 0.5 (plus lent = moins agressif)
        # Seuil : -40dB (très bas, ne coupe que le silence)
        seuil_base = -40
        filters.append(f"agate=threshold={seuil_base}dB:attack={attack}:release={release}:makeup=1.0")

    # PAS de silenceremove — il coupe la parole trop agressivement
    # C'était la cause principale de la réduction de 60min à 18min

    return ",".join(filters) if filters else ""


# ============================================================
# Vérification Whisper (import depuis whisper_check.py)
# ============================================================

def verifier_audio_avec_whisper(project_path: str, config: dict = None) -> dict:
    """
    Lancer la vérification Whisper sur un projet après nettoyage audio

    Args:
        project_path: Chemin du projet
        config: Configuration

    Returns:
        dict: Résultat de la vérification
    """
    if config is None:
        config = lire_config()

    if not config.get("verification_enabled", True):
        log("Vérification Whisper désactivée")
        return {"succes": True, "verifie": False, "note": "Désactivé"}

    log("=== Vérification Whisper ===")

    try:
        sys.path.insert(0, "C:\\StudioIA\\modules")
        from tts.whisper_check import verifier_audio_projet

        seuil = config.get("verification_similarity_threshold", 0.3)
        auto_regen = config.get("verification_auto_regenerate", True)

        problemes = verifier_audio_projet(
            project_path,
            seuil_similarite=seuil,
            regenerer=auto_regen
        )

        nb_problemes = len(problemes)
        if nb_problemes > 0:
            log(f"⚠  {nb_problemes} problème(s) détecté(s)")
        else:
            log(f"✅ Vérification OK")

        return {
            "succes": True,
            "problemes": nb_problemes,
            "details": problemes
        }

    except Exception as e:
        log(f"Erreur vérification Whisper: {e}")
        return {"succes": False, "erreur": str(e)}


# ============================================================
# Main
# ============================================================

def main():
    """Point d'entrée en ligne de commande"""
    import argparse

    parser = argparse.ArgumentParser(description="Nettoyage audio intelligent")
    parser.add_argument("input", help="Fichier audio d'entrée")
    parser.add_argument("-o", "--output", default=None, help="Fichier de sortie (défaut: input + _clean)")
    parser.add_argument("--gate-only", action="store_true", help="Appliquer uniquement le gate")
    parser.add_argument("--artefacts-only", action="store_true", help="Détecter/corriger uniquement les artefacts")
    parser.add_argument("--analyse", action="store_true", help="Analyser uniquement les niveaux dB")
    parser.add_argument("--whisper", metavar="PROJECT_PATH", help="Lancer vérification Whisper sur un projet")

    args = parser.parse_args()

    if args.whisper:
        result = verifier_audio_avec_whisper(args.whisper)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("succes") else 1

    if args.analyse:
        stats = analyser_niveaux_db(args.input)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    if args.artefacts_only:
        artefacts = detecter_artefacts(args.input)
        print(f"{len(artefacts)} artefacts détectés")
        if artefacts and args.output:
            corriger_artefacts(args.input, args.output, artefacts)
            print(f"Corrigé → {args.output}")
        return 0

    if args.gate_only:
        gate_filter = get_gate_filter()
        output = args.output or args.input.replace(".wav", "_gate.wav")
        cmd = [FFMPEG, "-y", "-i", args.input, "-af", gate_filter, "-acodec", "pcm_s16le", output]
        subprocess.run(cmd, capture_output=True)
        print(f"Gate appliqué → {output}")
        return 0

    # Pipeline complet
    output = args.output or args.input.replace(".wav", "_clean.wav")
    result = nettoyer_audio_complet(args.input, output)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("succes") else 1


if __name__ == "__main__":
    sys.exit(main())
