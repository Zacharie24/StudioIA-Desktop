import json, os, re, sys, shutil, subprocess
from pathlib import Path
from datetime import datetime

# Support relative imports when called as module or direct
try:
    from .voix_config import VOIX_DISPONIBLES
except (ImportError, ValueError):
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tts.voix_config import VOIX_DISPONIBLES

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

def log(msg):
    print(f"[TTS] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

VOIX_DISPONIBLES = {
    "1":  {"label": "XTTS - Vwa Gra (FR clone)",      "moteur": "xtts",  "voix": "xtts_clone_vwa_gra"},
    "2":  {"label": "XTTS - Vwa Soft (FR clone)",     "moteur": "xtts",  "voix": "xtts_clone_vwa_soft"},
    "3":  {"label": "Edge - Henri (FR homme)",         "moteur": "edge",  "voix": "fr_FR_henri"},
    "4":  {"label": "Edge - Remi (FR homme)",          "moteur": "edge",  "voix": "fr_FR_remi"},
    "5":  {"label": "Edge - Michael (FR homme)",       "moteur": "edge",  "voix": "fr_FR_michael"},
    "6":  {"label": "Edge - Denise (FR femme)",        "moteur": "edge",  "voix": "fr_FR_denise"},
    "7":  {"label": "Edge - Charline (FR femme BE)",   "moteur": "edge",  "voix": "fr_BE_charline"},
    "8":  {"label": "Edge - Steffan (EN homme US)",    "moteur": "edge",  "voix": "en_US_steffan"},
    "9":  {"label": "Edge - Ryan (EN homme GB)",       "moteur": "edge",  "voix": "en_GB_ryan"},
    "10": {"label": "Edge - Jenny (EN femme US)",      "moteur": "edge",  "voix": "en_US_jenny"},
    "11": {"label": "Piper - Gilles (FR homme)",       "moteur": "piper", "voix": "fr_FR_gilles"},
    "12": {"label": "Piper - Tom (FR homme)",          "moteur": "piper", "voix": "fr_FR_tom"},
    "13": {"label": "Piper - Siwis (FR femme)",        "moteur": "piper", "voix": "fr_FR_siwis"},
    "14": {"label": "Piper - Lessac (EN homme)",       "moteur": "piper", "voix": "en_US_lessac"},
}

def choisir_voix(voix_defaut="2"):
    import sys
    sys.path.insert(0, str(paths.MODULES_DIR / "utils"))
    from timeout_input import choisir_avec_timeout

    print("\n[TTS] Voix disponibles :")
    for k, v in VOIX_DISPONIBLES.items():
        print(f"  [{k:>2}] {v['label']}")

    choix = choisir_avec_timeout(
        options_dict=VOIX_DISPONIBLES,
        defaut=voix_defaut,
        timeout=10,
        message="Choisir voix"
    )
    return VOIX_DISPONIBLES.get(choix, VOIX_DISPONIBLES[voix_defaut])

def get_tts_path():
    """Chemin du moteur TTS externe (résolu via core/paths.py).
    Retourne un chemin même si le pack est absent (le fallback Edge est alors utilisé)."""
    t = paths.tts_path()
    return t if t else str(paths.XTTS_DIR)

def generer_chapitre_tts(ch_file, output_wav, moteur, voix, nom_projet, tts_path=None):
    if tts_path is None:
        tts_path = get_tts_path()

    with open(ch_file, "r", encoding="utf-8") as f:
        texte = f.read()

    script_appel = f"""
import sys
sys.path.insert(0, r"{tts_path}")
from tts_total import initialiser_projet, generer_long_texte

initialiser_projet("{nom_projet}")
resultat = generer_long_texte(
    texte={repr(texte)},
    moteur="{moteur}",
    voice_key="{voix}",
    nom_fichier="{Path(output_wav).stem}"
)
print("RESULT:" + str(resultat))
"""
    script_tmp = paths.TEMP_DIR / "appel_tts.py"
    script_tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(script_tmp, "w", encoding="utf-8") as f:
        f.write(script_appel)

    venv_python = f"{tts_path}\\venv\\Scripts\\python.exe"
    try:
        result = subprocess.run(
            [venv_python, str(script_tmp)],
            capture_output=True,
            cwd=tts_path
        )
    except Exception as e:
        log(f"  Erreur subprocess TTS: {e}")
        return None

    # Le moteur TTS tronque le nom de projet a 30 car. -> le dossier
    # reel n'est PAS toujours zacharie_<nom complet>. Le chemin exact est
    # renvoye sur la ligne "RESULT:<chemin>" par le script appele.
    chemin_reel = None
    try:
        stdout = (result.stdout or b"").decode("utf-8", errors="replace")
        for ligne in stdout.splitlines():
            if ligne.startswith("RESULT:"):
                chemin_reel = ligne[len("RESULT:"):].strip()
                break
    except Exception:
        pass

    if chemin_reel and Path(chemin_reel).exists():
        return chemin_reel

    # Fallback : chercher le dossier tronque zacharie_<prefixe>* le plus recent
    try:
        base = Path(tts_path)
        nom_safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', nom_projet)[:30].lower()
        prefix = "zacharie_" + nom_safe
        for d in sorted(base.glob("zacharie_*"), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.name.startswith(prefix):
                out = d / "output"
                if out.exists():
                    wavs = sorted(out.glob("*.wav"))
                    if wavs:
                        return str(wavs[-1])
    except Exception:
        pass

    return None

def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    data = lire_json(pjson)

    log(f"Projet : {data['id']}")
    log(f"Sujet  : {data['sujet']}")

    # Choisir la voix
    voix_choix = sys.argv[2] if len(sys.argv) > 2 else None
    voix_choisie = VOIX_DISPONIBLES.get(voix_choix) if voix_choix else choisir_voix()
    moteur = voix_choisie["moteur"]
    voix   = voix_choisie["voix"]
    log(f"Moteur : {moteur} | Voix : {voix}")

    chapitres = data.get("chapitres", [])
    if not chapitres:
        log("Aucun chapitre trouve dans project.json")
        sys.exit(1)

    data["etapes"]["audio"] = "en_cours"
    ecrire_json(pjson, data)

    succes_total = 0

    for ch in chapitres:
        ch_id = ch["id"]

        # Reprendre si deja genere
        audio_dest = os.path.join(project_path, "audio", f"{ch_id}.wav")
        if os.path.exists(audio_dest):
            log(f"{ch_id} deja genere, on saute.")
            ch["statut_tts"] = "termine"
            succes_total += 1
            continue

        ch_file = os.path.join(project_path, ch["script_file"])
        log(f"Generation {ch_id} : {ch.get('titre', '')}")

        chemin_wav = generer_chapitre_tts(
            ch_file=ch_file,
            output_wav=audio_dest,
            moteur=moteur,
            voix=voix,
            nom_projet=data["id"]
        )

        # Fallback automatique : si la voix demandee (ex. XTTS, lent/lourd)
        # echoue, on retente avec une voix Edge fiable (Henri FR).
        if not chemin_wav and moteur != "edge":
            log(f"  {ch_id} echec moteur '{moteur}' — fallback Edge Henri")
            chemin_wav = generer_chapitre_tts(
                ch_file=ch_file,
                output_wav=audio_dest,
                moteur="edge",
                voix="fr_FR_henri",
                nom_projet=data["id"]
            )
            if chemin_wav:
                log(f"  {ch_id} genere avec fallback Edge (voix differente de la config)")

        # Le chemin reel du WAV est renvoye (le moteur tronque le nom de
        # projet a 30 car., on ne peut pas redeviner le dossier).
        if chemin_wav:
            shutil.copy(chemin_wav, audio_dest)
            log(f"{ch_id} WAV copie vers audio/")

            srt_source = str(Path(chemin_wav)).replace(".wav", ".srt")
            if os.path.exists(srt_source):
                srt_dest = os.path.join(project_path, "audio", f"{ch_id}.srt")
                shutil.copy(srt_source, srt_dest)
                log(f"{ch_id} SRT copie vers audio/")

            ch["statut_tts"] = "termine"
            succes_total += 1
        else:
            log(f"{ch_id} ECHEC generation")
            ch["statut_tts"] = "echec"

        # Sauvegarder progression apres chaque chapitre
        ecrire_json(pjson, data)

    data["etapes"]["audio"] = "termine" if succes_total == len(chapitres) else "partiel"
    ecrire_json(pjson, data)

    log(f"Audio termine : {succes_total}/{len(chapitres)} chapitres")

if __name__ == "__main__":
    main()