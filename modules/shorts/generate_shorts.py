import json, os, sys, requests, subprocess, random, shutil, re, time
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Import voix_config - support pour module et mode direct
try:
    from ..tts.voix_config import VOIX_MAP_SHORTS
except (ImportError, ValueError):
    # En mode direct (python generate_shorts.py)
    parent = Path(__file__).parent.parent
    sys.path.insert(0, str(parent))
    from tts.voix_config import VOIX_MAP_SHORTS

# Import ComposIA pour la musique de fond
try:
    from ..audio.composia import generer_musique_fond, preparer_audio_pour_video
except (ImportError, ValueError):
    # En mode direct
    composia_path = paths.MODULES_DIR / "audio"
    sys.path.insert(0, str(composia_path))
    from composia import generer_musique_fond, preparer_audio_pour_video

FFMPEG = str(paths.FFMPEG)
MUSIC_DIR = str(paths.MUSIC_DIR)

# Encodage robuste de la sortie du processus : le pack TTS et les logs peuvent
# contenir '✓' (U+2713) / '⚠' (U+26A0) qui lèvent UnicodeEncodeError en cp1252
# selon la console du backend (mode installé ou console cmd). On force UTF-8
# (errors=replace) pour que la génération ne crashe jamais à l'impression.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    print(f"[SHORTS] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ollama(prompt, modele="mistral"):
    try:
        try:
            from llm import appeler_llm
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from llm import appeler_llm
        return appeler_llm(prompt, modele=modele, temperature=0.8).strip()
    except Exception as e:
        log(f"Ollama erreur : {e}")
        return ""

def nettoyer_intro_ia(texte):
    """
    Supprime les intros typiques IA qui trainent encore dans le texte genere.
    Coupe tout jusqu'a la premiere phrase 'humaine'.
    """
    if not texte:
        return texte

    # Patterns d'intro IA a supprimer (debut du texte)
    patterns_intro_ia = [
        r'^(?:Dans\s+(?:notre|ce|votre)\s+short[^,]*,\s*)',
        r'^(?:Dans\s+cette\s+video[^,]*,\s*)',
        r'^(?:Aujourd\'hui[^,]*,\s*(?:nous allons|je vais|on va)[^,]*,\s*)',
        r'^(?:Nous\s+(?:allons|avons)\s+(?:partager|voir|decouvrir)[^,]*,\s*)',
        r'^(?:Je\s+vais\s+(?:vous\s+)?(?:parler|montrer|presenter)[^,]*,\s*)',
        r'^(?:On\s+va\s+(?:voir|discuter|parler)[^,]*,\s*)',
        r'^(?:Here\s+(?:is|\'s)\s+what\s+we\s+will[^,]*,\s*)',
        r'^(?:In\s+(?:this|our)\s+short[^,]*,\s*)',
        r'^(?:Today\s+we(?:\'ll|\s+will)[^,]*,\s*)',
    ]

    texte_clean = texte.strip()

    # Appliquer chaque pattern
    for pattern in patterns_intro_ia:
        match = re.match(pattern, texte_clean, re.IGNORECASE)
        if match:
            texte_clean = texte_clean[match.end():].strip()
            log(f"  Intro IA supprimee: '{match.group()[:50]}...'")
            break  # Un seul pattern a la fois

    # Aussi, couper si le texte commence par "Dans notre short intitule..."
    # pattern plus specifique
    if re.match(r'^(?:Dans\s+(?:notre|ce)\s+short\s+intitule\s+["""])[^"""]*["""]', texte_clean, re.IGNORECASE):
        # Trouver la fin de cette phrase (point ou virgule)
        fin_phrase = re.search(r'[.,]', texte_clean)
        if fin_phrase:
            texte_clean = texte_clean[fin_phrase.end()+1:].strip()
            log(f"  Intro IA 'Dans notre short intitule...' supprimee")

    return texte_clean

def generer_plan_shorts(sujet, nb_shorts, type_contenu, langue):
    langue_nom = "francais" if langue == "fr" else "anglais"
    prompt = f"""Tu es un createur de contenu YouTube Shorts.
Sujet central : "{sujet}"
Type : {type_contenu}
Langue : {langue_nom}
Genere exactement {nb_shorts} titres de Shorts DIFFERENTS et UNIQUES sur ce sujet.
Chaque Short doit avoir un angle different et captivant.
Reponds UNIQUEMENT en JSON valide :
{{"shorts": ["Titre 1", "Titre 2", "Titre 3"]}}"""
    
    try:
        try:
            from llm import appeler_llm
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from llm import appeler_llm
        texte = appeler_llm(prompt, modele="mistral", temperature=0.9)
        debut = texte.find("{")
        fin   = texte.rfind("}") + 1
        return json.loads(texte[debut:fin])["shorts"]
    except:
        return [f"{sujet} - Short {i+1}" for i in range(nb_shorts)]

def generer_script_short(titre, sujet, type_contenu, langue, duree_secondes=60):
    mots_cible = int(duree_secondes * 2.2)  # ~130 mots/min

    if type_contenu == "priere":
        style = "une courte priere chretienne protestante, personnelle et sincere"
    elif type_contenu == "storytelling":
        style = "une histoire courte captivante avec debut, tension et resolution"
    else:
        style = "un contenu court et engageant"

    # CONSIGNE LINGUISTIQUE STRICTE POUR FORCER LE FRANCAIS
    if langue == "fr":
        consigne_langue = """CRITICAL LANGUAGE RULE - LECTURE OBLIGATOIRE:
- TU DOIS ECRIRE EXCLUSIVEMENT EN FRANCAIS
- JAMAIS de mots ou phrases en anglais
- Si tu utilises un mot anglais par erreur, CORRIGE-LE IMMEDIATEMENT
- Tout le texte doit etre en francais, point final."""
    else:
        consigne_langue = """CRITICAL LANGUAGE RULE - MANDATORY READING:
- YOU MUST WRITE EXCLUSIVELY IN ENGLISH
- NO French words or phrases whatsoever
- Correct any French errors immediately
- All text must be in English, period."""

    # CONSIGNES ANTI-IA POUR SHORTS — FORCER LE STYLE HUMAIN
    if langue == "fr":
        regles_humain = """REGLES CRITIQUES — TEXTE HUMAIN, PAS D'IA:

1. JAMAIS de phrase de presentation du genre:
   - "Dans ce short, nous allons..."
   - "Dans notre short intitule ..., nous partagerons..."
   - "Aujourd'hui, je vais vous presenter..."
   - "Dans cette video, on va parler de..."
   - "Voici ce que nous allons decouvrir..."

2. COMMENCE DIRECTEMENT PAR LE COEUR DU SUJET:
   - Une question percutante qui interpelle
   - Une verite biblique forte (pour les prieres)
   - Une situation concrete que le spectateur vit
   - Un constat brutal et honeste

3. EXEMPLES D'INTROS HUMAINES (pas IA):
   - "Tu te reveilles a 3h du matin, le coeur qui bat trop vite..."
   - "Seigneur, je viens devant toi pour tous ceux qui..."
   - "La peur ne dort jamais la nuit. Elle revient toujours."
   - "Combien de fois as-tu essaye de prier mais les mots ne venaient pas ?"

4. INTERDIT: les mots "nous partagerons", "nous allons", "dans ce short", "dans cette video", "je vais vous montrer", "on va decouvrir"

5. Style: comme si tu parlais a un ami proche, pas comme une presentation corporate."""
    else:
        regles_humain = """CRITICAL RULES — HUMAN TEXT, NOT AI:

1. NEVER use presentation sentences like:
   - "In this short, we will share..."
   - "Today, I'm going to present..."
   - "In this video, we'll talk about..."
   - "Here's what we'll discover..."

2. START DIRECTLY WITH THE HEART OF THE TOPIC:
   - A powerful question that hits
   - A biblical truth (for prayers)
   - A concrete situation the viewer lives
   - A blunt honest observation

3. HUMAN INTRO EXAMPLES (not AI):
   - "You wake up at 3am, heart racing, mind spinning..."
   - "Lord, I come before you for everyone who..."
   - "Fear never sleeps at night. It always comes back."
   - "How many times have you tried to pray but the words wouldn't come?"

4. FORBIDDEN: "we will share", "we're going to", "in this short", "in this video", "I'm going to show you", "we'll discover"

5. Style: like talking to a close friend, not a corporate presentation."""

    prompt = f"""{consigne_langue}

{regles_humain}

Tu es un createur YouTube Shorts.
Titre du Short : "{titre}"
Sujet central : "{sujet}"
Style : {style}
Langue : {"francais" if langue == "fr" else "anglais"}
Ecris exactement {mots_cible} mots.
Style oral, dynamique, comme si tu parlais a un ami.
Pas de titres, pas de markdown, texte continu uniquement.
COMMENCE DIRECTEMENT PAR LE SUJET — JAMAIS par une phrase d'introduction ou de presentation."""

    return ollama(prompt)

def _run_tts_script(texte, output_wav, moteur, voix, nom_fichier="short_audio"):
    """Execute une generation TTS via le venv du pack XTTS (résolu par core/paths).
    PYTHONIOENCODING=utf-8 : le pack imprime '✓' (U+2713) en console, ce qui
    lève UnicodeEncodeError en cp1252 sur Windows → on force l'encodage UTF-8
    du sous-processus pour que la génération aboutisse.
    Retourne True si le .wav a bien été produit."""
    tts_root = paths.tts_path()
    if not tts_root:
        log("Pack TTS (XTTS) absent pour ce short — abandon TTS local")
        return False
    venv_python = os.path.join(tts_root, "venv", "Scripts", "python.exe")

    script = f"""
import sys
sys.path.insert(0, r"{tts_root}")
from tts_total import initialiser_projet, generer_long_texte
import shutil, os

initialiser_projet("short_gen")
resultat = generer_long_texte(
    texte={repr(texte)},
    moteur="{moteur}",
    voice_key="{voix}",
    nom_fichier="{nom_fichier}"
)
if resultat and os.path.exists(resultat):
    shutil.copy(resultat, r"{output_wav}")
    print("OK:" + resultat)
else:
    print("ECHEC")
"""
    script_path = output_wav.replace(".wav", "_gen.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        subprocess.run([venv_python, script_path], cwd=tts_root,
                       capture_output=False, env=env)
    except Exception:
        pass
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)

    return os.path.exists(output_wav)


def generer_audio_short(texte, output_wav, langue, voix_choix="3"):
    """Genere l'audio d'un short avec la voix choisie.
    Si la voix demandee (ex. XTTS) echoue, fallback automatique Edge Henri."""
    cfg = VOIX_MAP_SHORTS.get(voix_choix, VOIX_MAP_SHORTS["3"])

    if _run_tts_script(texte, output_wav, cfg["moteur"], cfg["voix"]):
        return True

    # Fallback : voix Edge fiable si le moteur choisi (XTTS/Piper) a echoue
    if cfg["moteur"] != "edge":
        print(f"[SHORTS] Echec moteur '{cfg['moteur']}' — fallback Edge Henri")
        return _run_tts_script(texte, output_wav, "edge", "fr_FR_henri")

    return False

def generer_srt_for_short(audio_path, texte, output_srt):
    """Génère un fichier SRT simple avec le texte synchronisé à l'audio"""
    duree = get_duree(audio_path)

    # Calculer le temps par mot (en supposant ~130 mots/min)
    mots = texte.split()
    nb_mots = len(mots)
    temps_par_mot = duree / nb_mots if nb_mots > 0 else 1

    srt_lines = []
    srt_counter = 1
    srt_lines.append(str(srt_counter))
    srt_counter += 1

    debut = 0.0
    fin = temps_par_mot
    srt_lines.append(f"{int(debut//3600):02d}:{int((debut%3600)//60):02d}:{int(debut%60):02d},{int((debut%1)*1000):03d} --> {int(fin//3600):02d}:{int((fin%3600)//60):02d}:{int(fin%60):02d},{int((fin%1)*1000):03d}")

    # Premier mot en début d'audio
    mot = mots[0] if mots else "..."
    srt_lines.append(mot)
    srt_lines.append("")

    # Créer des blocs de mots par intervalles
    intervalle = int(len(mots) * 0.1)  # 10% des mots par bloc
    if intervalle < 1:
        intervalle = 1

    for i in range(1, len(mots), intervalle):
        fin_bloc = min(i + intervalle, len(mots))
        bloc = " ".join(mots[i:fin_bloc])

        debut_bloc = i * temps_par_mot
        fin_bloc_time = fin_bloc * temps_par_mot

        srt_lines.append(str(srt_counter))
        srt_counter += 1
        srt_lines.append(f"{int(debut_bloc//3600):02d}:{int((debut_bloc%3600)//60):02d}:{int(debut_bloc%60):02d},{int((debut_bloc%1)*1000):03d} --> {int(fin_bloc_time//3600):02d}:{int((fin_bloc_time%3600)//60):02d}:{int(fin_bloc_time%60):02d},{int((fin_bloc_time%1)*1000):03d}")
        srt_lines.append(bloc)
        srt_lines.append("")

    with open(output_srt, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines).strip() + "\n")

    return os.path.exists(output_srt)

def get_duree(path):
    if not os.path.exists(path):
        log(f"  Fichier introuvable pour get_duree: {path}")
        return 60
    result = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            t = line.strip().split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            duree = float(h)*3600 + float(m)*60 + float(s)
            return duree
    log(f"  Impossible de lire la duree de {os.path.basename(path)}, fallback 60s")
    return 60

# Effets pour les Shorts (Ken Burns en vertical)
EFFETS_KENBURNS_SHORTS = [
    "zoom_in_centre", "zoom_out_centre",
    "pan_haut_bas", "pan_bas_haut",
]

def get_kenburns_vf_shorts(effet, w, h, duree):
    fps = 25
    frames = int(duree * fps)
    if effet == "zoom_in_centre":
        zp = f"z='min(1+on/{frames}*0.3,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "zoom_out_centre":
        zp = f"z='if(lte(on,1),1.3,max(1.0,1.3-on/{frames}*0.3))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "pan_haut_bas":
        zp = f"z=1.2:y='on/{frames}*(ih-(ih/zoom))':x='iw/2-(iw/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "pan_bas_haut":
        zp = f"z=1.2:y='(ih-(ih/zoom))-on/{frames}*(ih-(ih/zoom))':x='iw/2-(iw/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    else:
        zp = f"z=1.2:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    return f"scale=8000:-1,zoompan={zp}"

def choisir_musique(music_path):
    music_dir = Path(music_path)
    if not music_dir.exists(): return None
    fichiers = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    return str(fichiers[0]) if fichiers else None

def generer_musique_fond_projet(shorts_path, sujet, type_contenu, config):
    """
    Générer automatiquement une musique de fond pour le projet Shorts.

    Priority order:
    1. ComposIA (génération IA) - si disponible
    2. Fallback vers musique existante dans assets/music
    """
    log("  Generation musique de fond...")

    # Déterminer le prompt selon le type de contenu
    if type_contenu == "priere":
        prompt = f"Fais-moi une musique de fond pieuse et apaisante pour une priere, avec piano et cordes. Sujet: {sujet}"
        duree = 120
    elif type_contenu == "storytelling":
        prompt = f"Fais-moi une musique cinematique et narrative pour une histoire/narration, sans batterie. Sujet: {sujet}"
        duree = 180
    else:
        prompt = f"Fais-moi une musique de fond agréable et harmonieuse pour une vidéo. Sujet: {sujet}"
        duree = 120

    # Étape 1: Tenter ComposIA si Ollama est accessible
    try:
        import requests
        ollama_ok = requests.get("http://localhost:11434", timeout=3).status_code == 200
    except:
        ollama_ok = False

    if ollama_ok:
        try:
            result = generer_musique_fond(
                projet_path=str(shorts_path),
                prompt=prompt,
                nom="musique_fond",
                duree_cible=duree
            )

            if result.get("succes") and result.get("mp3"):
                preparer_audio_pour_video(str(shorts_path), result["mp3"])
                log(f"  Musique generee par ComposIA: {os.path.basename(result['mp3'])}")
                return result["mp3"]
        except Exception as e:
            log(f"  ComposIA échoué: {e}")

    # Étape 2: Fallback vers musique existante
    log("  Fallback vers musique existante...")
    music_file = choisir_musique(str(paths.MUSIC_DIR))
    if music_file:
        # Copier la musique dans le dossier audio du projet
        import shutil
        audio_dir = Path(shorts_path) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        dest_path = audio_dir / os.path.basename(music_file)
        shutil.copy(music_file, dest_path)
        log(f"  Musique copiée: {os.path.basename(music_file)}")
        return str(dest_path)

    log("  Aucune musique disponible")
    return None


def ajouter_musique(video_path, music_path, output_path, music_volume=0.15):
    cmd = [
        FFMPEG, "-y", "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex",
        f"[1:a]volume={music_volume}[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def lire_video_config(project_path=None):
    # Pour les shorts, on utilise la config globale
    cfg_path = str(paths.chemin_app("config_video.json"))
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {"qualite": "1", "audio_fmt": "1", "zoompan": "0"}

def get_parametres_qualite(qualite_choix, zoompan_choix):
    qualites = {
        "1": {"crf": "28", "preset": "veryfast"},
        "2": {"crf": "23", "preset": "fast"},
        "3": {"crf": "18", "preset": "slow"}
    }
    zoompan_map = {"0": False, "1": True, "2": True}
    q = qualites.get(qualite_choix, qualites["1"])
    z = zoompan_map.get(zoompan_choix, False)
    return q["crf"], q["preset"], z

def get_combined_audio_filter(config):
    """Retourne le filtre audio FFmpeg combiné (denoiser + gate)"""
    # Importer depuis audio_cleanup pour la version complète
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audio"))
        from audio_cleanup import get_combined_audio_filter as _cleanup_filter
        return _cleanup_filter(config)
    except ImportError:
        # Fallback : denoiser only
        filters = []
        if config.get("denoiser_enabled", True):
            strength = config.get("denoiser_strength", "medium")
            nf_map = {"light": "-35", "medium": "-25", "strong": "-18"}
            nf = nf_map.get(strength, "-25")
            filters.append(f"highpass=f=80,afftdn=nf={nf}:nt=w")
        if config.get("gate_enabled", True):
            sensitivity = config.get("gate_sensitivity", 0.5)
            attack = config.get("gate_attack", 0.01)
            release = config.get("gate_release", 0.5)
            seuil_base = -15 - (sensitivity * 5)
            filters.append(f"agate=threshold={seuil_base:.0f}dB:attack={attack}:release={release}:makeup=1.0")
            filters.append("silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=1:stop_threshold=-45dB:start_silence=0.5:stop_silence=1.0")
        return ",".join(filters) if filters else None

def creer_video_short(audio_path, image_path, output_path, titre, config, shorts_path=None, use_zoompan=False, langue="fr", duree_sec=60):
    duree = get_duree(audio_path)
    log(f"  Duree audio detectee: {duree:.1f}s (cible: {duree_sec}s)")

    # Validation : si l'audio est bien plus court que la cible, avertir
    if duree > 0 and duree < duree_sec * 0.3:
        log(f"  ⚠ ATTENTION: l'audio ne fait que {duree:.0f}s au lieu de {duree_sec}s cibles")
        log(f"  Le TTS semble avoir genere un fichier trop court")
    elif duree < 1:
        log(f"  ⚠ Audio extremement court ({duree:.2f}s) - fichier peut-etre corrompu")

    # Format vertical 9:16 pour Shorts
    W, H = 1080, 1920

    qualite_cfg = lire_video_config()
    crf, preset, use_zoompan = get_parametres_qualite(
        qualite_cfg.get("qualite", "1"),
        qualite_cfg.get("zoompan", "0")
    )

    # Texte titre adapte
    titre_court = titre[:40] + "..." if len(titre) > 40 else titre

    # Effet Ken Burns optionnel
    if use_zoompan:
        kb_effet = random.choice(EFFETS_KENBURNS_SHORTS)
        kb_vf = get_kenburns_vf_shorts(kb_effet, W, H, duree)
        vf = f"{kb_vf},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    else:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=yuv420p"

    # Recherche du fichier SRT associe
    srt_path = audio_path.replace(".wav", ".srt")
    srt_used = None
    if os.path.exists(srt_path):
        srt_used = srt_path
    else:
        # Chercher dans le dossier audio
        audio_dir = os.path.dirname(audio_path)
        srt_files = list(Path(audio_dir).glob("short_*.srt"))
        if srt_files:
            srt_used = str(srt_files[0])

    # Ajouter les sous-titres SRT si disponibles
    if srt_used:
        srt_escaped = srt_used.replace("\\", "/").replace("C:", "C\\:")
        # Style sous-titres pour Shorts (colori, centré, bordure)
        vf += f",subtitles='{srt_escaped}':force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,Outline=2,Shadow=1,Alignment=2,MarginV=80,BorderStyle=1'"
        log(f"  SRT ajoute: {os.path.basename(srt_used)}")

    # Rechercher la musique de fond générée par ComposIA
    music_file = None
    if shorts_path:
        audio_dir = Path(shorts_path) / "audio"
        musique_composia = audio_dir / "musique_fond.mp3"
        if musique_composia.exists():
            music_file = str(musique_composia)
            log(f"  Musique de fond: {musique_composia.name}")
        else:
            # Fallback vers musique_path dans config
            music_file = choisir_musique(str(paths.MUSIC_DIR))

    # Constructeur de commande FFmpeg
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-r", "25", "-t", str(duree),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
    ]

    # PAS de denoiser/gate pour les shorts : trop agressif, coupe l'audio
    # Les shorts sont courts, le TTS produit déjà un audio propre
    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Ajouter musique de fond apres la video de base
    if music_file and result.returncode == 0:
        video_intermediaire = output_path.replace(".mp4", "_temp.mp4")
        shutil.copy(output_path, video_intermediaire)
        ok_m = ajouter_musique(video_intermediaire, music_file, output_path, config.get("music_volume", 0.15))
        if ok_m:
            os.remove(video_intermediaire)
        else:
            # Si echec musique, garder la video sans musique
            log(f"  Note: musique non ajoutee (video conservee)")

    return result.returncode == 0

def choisir_image(assets_path, sujet, langue):
    bg_dir = Path(assets_path) / "backgrounds"
    images = list(bg_dir.glob("*.jpg")) + list(bg_dir.glob("*.png"))
    if images:
        return str(random.choice(images))
    return None

def generer_thumbnail_short(titre, output_path, style_couleur=(255,215,0)):
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 1080, 1920
        img  = Image.new("RGB", (W,H), (10,5,20))
        draw = ImageDraw.Draw(img)

        try:
            font_grand  = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 90)
            font_petit  = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 45)
        except:
            font_grand = font_petit = ImageFont.load_default()

        # Gradient
        for y in range(H):
            ratio = y/H
            r = int(10 + 40*ratio)
            g = int(5 + 20*ratio)
            b = int(20 + 60*ratio)
            draw.line([(0,y),(W,y)], fill=(r,g,b))

        # Titre
        mots = titre.split()
        lignes = []
        buf = ""
        for mot in mots:
            test = (buf+" "+mot).strip()
            bbox = draw.textbbox((0,0), test, font=font_grand)
            if bbox[2]-bbox[0] > W-100:
                if buf: lignes.append(buf)
                buf = mot
            else:
                buf = test
        if buf: lignes.append(buf)

        y_start = H//2 - len(lignes)*100//2
        for ligne in lignes:
            bbox = draw.textbbox((0,0), ligne, font=font_grand)
            tw = bbox[2]-bbox[0]
            x  = (W-tw)//2
            draw.text((x+3,y_start+3), ligne, font=font_grand, fill=(0,0,0,200))
            draw.text((x,y_start), ligne, font=font_grand, fill=style_couleur)
            y_start += 110

        # Hashtag
        draw.text((W//2-100, H-120), "#Shorts", font=font_petit, fill=(200,200,200))

        img.save(output_path, "PNG", quality=95)
        return True
    except Exception as e:
        log(f"Thumbnail erreur : {e}")
        return False

def main():
    config = lire_json(str(paths.config_path()))

    # Detecter si on reprend un projet existant (chemin passe en argument)
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    if project_path and os.path.isdir(project_path):
        planjson = os.path.join(project_path, "plan.json")
        if os.path.exists(planjson):
            # Reprendre un projet existant
            plan = lire_json(planjson)
            sujet = plan.get("sujet", "")
            langue = plan.get("langue", "fr")
            type_contenu = plan.get("type_contenu", "priere")
            duree_sec = plan.get("duree_sec", 60)
            nb_shorts = plan.get("nb_shorts", 5)
            voix_choix = None  # A definir selon config

            print("\n  ================================")
            print("  REPRENDRE PROJET SHORTS")
            print("  ================================")
            print(f"  Sujet    : {sujet}")
            print(f"  Langue   : {langue}")
            print(f"  Type     : {type_contenu}")
            print(f"  Duree    : {duree_sec}s")
            print(f"  Nb Shorts: {nb_shorts}")
            print("  ================================")

            # Utiliser le dossier existant
            shorts_path = Path(project_path)
            # Recuperer les titres du plan
            titres = plan.get("titres", [])
            if not titres:
                log("Aucun titre trouve dans le plan. Arret.")
                sys.exit(1)
            nb_shorts = len(titres)
            log(f"Reprise du projet : {shorts_path}")
            log(f"Reprise avec {nb_shorts} Shorts")
        else:
            # Nouveau projet avec sujet en argument
            sujet = sys.argv[1] if len(sys.argv) > 1 else ""
            if not sujet:
                sujet = input("\n  Sujet central des Shorts : ").strip()
                if not sujet: return
    else:
        # Mode interactif normal
        print("\n  ================================")
        print("  GENERATEUR YOUTUBE SHORTS")
        print("  ================================")

        sujet = input("\n  Sujet central des Shorts : ").strip()
        if not sujet: return

        print("\n  Type de contenu :")
        print("  [1] Priere chretienne (FR)")
        print("  [2] Storytelling (FR)")
        print("  [3] Storytelling (EN)")
        print("  [4] General (FR)")
        type_choix = input("  Choix [1] : ").strip() or "1"

        langue = "fr"
        type_contenu = "priere"
        if type_choix == "2": langue, type_contenu = "fr", "storytelling"
        elif type_choix == "3": langue, type_contenu = "en", "storytelling"
        elif type_choix == "4": langue, type_contenu = "fr", "general"

        print("\n  Duree de chaque Short :")
        print("  [1] 30 secondes")
        print("  [2] 60 secondes (1 minute)")
        print("  [3] 90 secondes")
        duree_choix = input("  Choix [2] : ").strip() or "2"
        duree_sec = {"1": 30, "2": 60, "3": 90}.get(duree_choix, 60)

        nb = input("\n  Nombre de Shorts a generer [5] : ").strip() or "5"
        nb_shorts = int(nb) if nb.isdigit() else 5

        print("\n  Voix TTS :")
        print("  [3] Edge Henri (FR)  [4] Edge Denise (FR)")
        print("  [8] Edge Steffan (EN) [9] Edge Ryan (EN)")
        voix_choix = input("  Choix [3] : ").strip() or "3"

        # Dossier projet Shorts
        import re, time
        nom_safe = re.sub(r'[^a-z0-9_]', '_', sujet.lower())[:25]
        shorts_id   = f"shorts_{nom_safe}_{int(time.time())}"
        shorts_path = Path(config["projects_path"]) / shorts_id
        shorts_path.mkdir(parents=True, exist_ok=True)
        (shorts_path / "scripts").mkdir(exist_ok=True)
        (shorts_path / "audio").mkdir(exist_ok=True)
        (shorts_path / "export" / "shorts").mkdir(parents=True, exist_ok=True)
        (shorts_path / "thumbnails").mkdir(exist_ok=True)
        # Generer plan pour nouveau projet
        log(f"Projet Shorts : {shorts_id}")
        log(f"Nombre : {nb_shorts} Shorts de {duree_sec}s")
        log("Generation des titres...")
        titres = generer_plan_shorts(sujet, nb_shorts, type_contenu, langue)
        log(f"{len(titres)} titres generes")
        # Sauvegarder plan
        plan = {
            "id": shorts_id, "sujet": sujet,
            "langue": langue, "type_contenu": type_contenu,
            "duree_sec": duree_sec, "nb_shorts": nb_shorts,
            "titres": titres, "statut": "en_cours"
        }
        ecrire_json(str(shorts_path / "plan.json"), plan)

        # Générer automatiquement la musique de fond avec ComposIA
        log("\n  Generation musique de fond...")
        musique_path = generer_musique_fond_projet(shorts_path, sujet, type_contenu, config)
        if musique_path:
            log(f"  Musique de fond prête: {os.path.basename(musique_path)}")
        else:
            log(f"  Note: musique de fond non disponible")

    succes = 0
    for i, titre in enumerate(titres, 1):
        log(f"\nShort {i}/{nb_shorts} : {titre}")

        # Chemins
        nom_safe_titre = re.sub(r'[^a-z0-9_]', '_', titre.lower())[:30]
        script_path_f  = str(shorts_path / "scripts" / f"short_{i:02d}.txt")
        audio_path     = str(shorts_path / "audio"   / f"short_{i:02d}.wav")
        video_path     = str(shorts_path / "export" / "shorts" / f"short_{i:02d}_{nom_safe_titre}.mp4")
        thumb_path     = str(shorts_path / "thumbnails" / f"short_{i:02d}.png")

        # 1. Script
        log("  Generation script...")
        script = generer_script_short(titre, sujet, type_contenu, langue, duree_sec)
        # Nettoyage des intros IA residuelles
        script = nettoyer_intro_ia(script)
        with open(script_path_f, "w", encoding="utf-8") as f:
            f.write(script)
        log(f"  Script : {len(script.split())} mots")

        # 2. Audio
        log("  Generation audio...")
        ok_audio = generer_audio_short(script, audio_path, langue, voix_choix)
        if not ok_audio:
            log(f"  ECHEC audio — on saute")
            continue

        # 2b. Generation SRT
        srt_path = audio_path.replace(".wav", ".srt")
        generer_srt_for_short(audio_path, script, srt_path)
        log(f"  SRT genere")

        # 3. Image
        image = choisir_image(config["assets_path"], sujet, langue)
        if not image:
            log("  Aucune image disponible")
            continue

        # 4. Video (avec musique, parametres de qualite et sous-titres)
        log("  Creation video Short...")
        ok_video = creer_video_short(audio_path, image, video_path, titre, config, shorts_path=str(shorts_path), langue=langue, duree_sec=duree_sec)
        if not ok_video:
            log("  ECHEC video")
            continue

        # 5. Thumbnail
        generer_thumbnail_short(titre, thumb_path)

        log(f"  Short {i} OK : {os.path.basename(video_path)}")
        succes += 1

        # Générer projet Shotcut pour chaque short
        log("  Generation projet Shotcut...")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "gen_shotcut",
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video", "gen_shotcut.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # Créer un projet Shotcut pour ce short
            short_export_dir = str(shorts_path / "export")
            mod.generer_mlt_for_short(str(shorts_path), i, titre, audio_path, image, video_path, config)
        except Exception as e:
            log(f"  Shotcut non genere: {e}")

    # Rapport final
    print(f"\n  ================================")
    print(f"  SHORTS TERMINES !")
    print(f"  {succes}/{nb_shorts} Shorts generes")
    print(f"  Dossier : {shorts_path / 'export' / 'shorts'}")
    print(f"  ================================")

    # Ouvrir dossier
    ouvrir = input("\n  Ouvrir le dossier export ? (o/n) : ").strip()
    if ouvrir == "o":
        subprocess.Popen(["explorer.exe", str(shorts_path / "export")])

if __name__ == "__main__":
    main()