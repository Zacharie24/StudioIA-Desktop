import json, os, sys, subprocess, shutil, random
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# Import audio cleanup module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audio"))
from audio_cleanup import get_combined_audio_filter, nettoyer_audio_complet, verifier_audio_avec_whisper

# Import media library (StudioIA-Next)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services"))
from media.media_library import preparer_medias, MediaLibrary

FFMPEG = str(paths.FFMPEG)

def log(msg):
    print(f"[VIDEO] {msg}")

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def ecrire_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

STYLES_SOUS_TITRES = {
    "1": {"nom": "Or classique",   "couleur": "&H00FFD700&", "contour": "&H00000000&", "taille": 14},
    "2": {"nom": "Blanc pur",      "couleur": "&H00FFFFFF&", "contour": "&H00000000&", "taille": 14},
    "3": {"nom": "Cyan lumineux",  "couleur": "&H00FFFF00&", "contour": "&H00800000&", "taille": 14},
    "4": {"nom": "Rose spirituel", "couleur": "&H00FF69B4&", "contour": "&H00000000&", "taille": 14},
    "5": {"nom": "Vert emeraude",  "couleur": "&H0050C878&", "contour": "&H00000000&", "taille": 14},
    "6": {"nom": "Jaune dore",     "couleur": "&H0000FFFF&", "contour": "&H00000000&", "taille": 14},
    "7": {"nom": "Aleatoire",      "couleur": None,           "contour": None,           "taille": 14},
}

EFFETS_PARTICULES = {
    "1": "pluie_or",
    "2": "etincelles",
    "3": "lueurs",
    "4": "neige",
    "5": "aleatoire",
    "6": "aucun",
}

EFFETS_KENBURNS = [
    "zoom_in_centre","zoom_out_centre","pan_gauche_droite",
    "pan_droite_gauche","zoom_in_gauche","zoom_in_droite","pan_haut_bas",
]

def get_kenburns_vf(effet, w, h, duree):
    fps = 25
    frames = int(duree * fps)
    if effet == "zoom_in_centre":
        zp = f"z='min(1+on/{frames}*0.3,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "zoom_out_centre":
        zp = f"z='if(lte(on,1),1.3,max(1.0,1.3-on/{frames}*0.3))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "pan_gauche_droite":
        zp = f"z=1.2:x='on/{frames}*(iw-(iw/zoom))':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "pan_droite_gauche":
        zp = f"z=1.2:x='(iw-(iw/zoom))-on/{frames}*(iw-(iw/zoom))':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "zoom_in_gauche":
        zp = f"z='min(1+on/{frames}*0.3,1.3)':x='0':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    elif effet == "zoom_in_droite":
        zp = f"z='min(1+on/{frames}*0.3,1.3)':x='iw-(iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}"
    else:
        zp = f"z=1.2:x='iw/2-(iw/zoom/2)':y='on/{frames}*(ih-(ih/zoom))':d={frames}:s={w}x{h}:fps={fps}"
    return f"scale=8000:-1,zoompan={zp}"

def get_particules_vf(effet):
    if effet == "pluie_or":
        return "noise=alls=25:allf=t+u,colorchannelmixer=rr=1.3:gg=1.15:bb=0.6:aa=1"
    elif effet == "etincelles":
        return "noise=alls=30:allf=t+u,colorchannelmixer=rr=1.4:gg=1.3:bb=1.0:aa=1"
    elif effet == "lueurs":
        return "gblur=sigma=4,colorchannelmixer=rr=1.15:gg=1.08:bb=0.85:aa=1,noise=alls=12:allf=t"
    elif effet == "neige":
        return "noise=alls=28:allf=t+u,colorchannelmixer=rr=1.0:gg=1.0:bb=1.3:aa=1"
    return None

def fix_srt(srt_path, output_path, max_chars=42):
    import re
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            contenu = f.read()
        blocs = contenu.strip().split("\n\n")
        nouveau = []
        compteur = 1
        for bloc in blocs:
            lignes = bloc.strip().split("\n")
            if len(lignes) < 3:
                continue
            timing = lignes[1]
            texte = " ".join(lignes[2:]).strip()
            texte = re.sub(r'\s+', ' ', texte)
            if len(texte) <= max_chars:
                nouveau.append(f"{compteur}\n{timing}\n{texte}")
                compteur += 1
            else:
                match = re.match(r'(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)', timing)
                if not match:
                    nouveau.append(f"{compteur}\n{timing}\n{texte[:max_chars]}")
                    compteur += 1
                    continue
                def tc_ms(tc):
                    h,m,s = tc.replace(',','.').split(':')
                    return int(float(h)*3600000+float(m)*60000+float(s)*1000)
                def ms_tc(ms):
                    h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000
                    s=ms//1000; ms%=1000
                    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                d_ms = tc_ms(match.group(1))
                f_ms = tc_ms(match.group(2))
                mots = texte.split()
                groupes = []
                buf = ""
                for mot in mots:
                    test = (buf+" "+mot).strip()
                    if len(test) <= max_chars:
                        buf = test
                    else:
                        if buf: groupes.append(buf)
                        buf = mot
                if buf: groupes.append(buf)
                dpg = (f_ms - d_ms) // max(len(groupes),1)
                for j, g in enumerate(groupes):
                    td = d_ms + j*dpg
                    tf = td + dpg - 50
                    nouveau.append(f"{compteur}\n{ms_tc(td)} --> {ms_tc(tf)}\n{g}")
                    compteur += 1
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(nouveau))
        return True
    except Exception as e:
        log(f"Erreur SRT fix: {e}")
        return False

def get_denoiser_af(config):
    """Retourne le filtre audio FFmpeg pour le denoiser (léger)"""
    if not config.get("denoiser_enabled", False):
        return None
    strength = config.get("denoiser_strength", "light")
    # NOUVEAUX seuils conservateurs — ne pas casser la voix
    nf_map = {"light": "-42", "medium": "-38", "strong": "-35"}
    nf = nf_map.get(strength, "-42")
    # highpass=60 garde les basses naturelles de la voix
    return f"highpass=f=60,afftdn=nf={nf}:nt=w"

def get_duree_audio(wav_path):
    result = subprocess.run([FFMPEG, "-i", wav_path], capture_output=True, text=True)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            t = line.strip().split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return float(h)*3600 + float(m)*60 + float(s)
    return 60

def get_filtre_video_simple(w, h):
    """Filtre simple sans zoompan - beaucoup plus rapide"""
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"

def construire_segment(img_path, audio_path, srt_path, output_path,
                       kenburns, particules, style_st, resolution,
                       logo_path="", langue="fr", nom_chaine="", crf="23", preset="fast",
                       config=None):
    if config is None:
        config = {}
    w, h = resolution.split("x")
    duree = get_duree_audio(audio_path)

    kb_vf   = get_kenburns_vf(kenburns, w, h, duree)
    part_vf = get_particules_vf(particules)

    if part_vf and particules != "aucun":
        vf = f"{kb_vf},{part_vf},format=yuv420p"
    else:
        vf = f"{kb_vf},format=yuv420p"

    # Sous-titres corriges
    if srt_path and os.path.exists(srt_path):
        srt_fixed = srt_path.replace(".srt", "_fixed.srt")
        fix_srt(srt_path, srt_fixed)
        srt_use = srt_fixed if os.path.exists(srt_fixed) else srt_path
        srt_escaped = srt_use.replace("\\", "/").replace("C:", "C\\:")
        couleur = style_st["couleur"]
        contour = style_st["contour"]
        taille  = style_st["taille"]
        # Utiliser la taille depuis config (sinon valeur du style)
        taille_final = config.get("subtitle_size", taille)
        margev_final = config.get("subtitle_margin", 40)
        vf += f",subtitles='{srt_escaped}':force_style='FontName=Arial,FontSize={taille_final},PrimaryColour={couleur},OutlineColour={contour},Outline=2,Shadow=1,Alignment=2,MarginV={margev_final},BorderStyle=1'"

    # Watermark texte si pas de logo
    if not logo_path and nom_chaine:
        vf += f",drawtext=text='{nom_chaine}':fontsize=20:fontcolor=white@0.7:x=w-tw-20:y=h-th-20:shadowx=1:shadowy=1"

    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", img_path,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-r", "25", "-t", str(duree),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
    ]

    # Ajouter le denoiser + gate audio si configuré (combiné)
    combined_af = get_combined_audio_filter(config)
    if combined_af:
        cmd.extend(["-af", combined_af])

    cmd.append(output_path)

    # Ajouter logo PNG si present
    if logo_path and os.path.exists(logo_path):
        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-i", img_path,
            "-i", audio_path,
            "-i", logo_path,
            "-filter_complex",
            f"[0:v]{vf}[bg];[bg][2:v]overlay=W-w-20:H-h-20:format=auto,format=yuv420p[out]",
            "-map", "[out]", "-map", "1:a",
            "-c:v", "libx264", "-preset", preset, "-crf", crf,
            "-r", "25", "-t", str(duree),
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
        ]
        # Ajouter le denoiser + gate audio si configuré
        if combined_af:
            cmd.extend(["-af", combined_af])
        cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Erreur FFmpeg : {result.stderr[-300:]}")
    return result.returncode == 0

def construire_segment_video(video_path, audio_path, srt_path, output_path,
                              resolution, style_st, config=None,
                              logo_path="", langue="fr", nom_chaine="",
                              crf="23", preset="fast"):
    """
    Construit un segment vidéo avec une vidéo de fond au lieu d'une image fixe.
    La vidéo est bouclée si nécessaire et redimensionnée pour s'adapter.

    Args:
        video_path: chemin vers la vidéo de fond
        audio_path: chemin vers l'audio (voix off)
        srt_path: chemin vers les sous-titres
        output_path: chemin de sortie
        resolution: "1920x1080" par exemple
        style_st: style des sous-titres
        config: configuration globale
        logo_path: chemin du logo PNG
        langue: langue du projet
        nom_chaine: nom de la chaîne pour watermark
        crf: qualité vidéo
        preset: preset de compression
    """
    if config is None:
        config = {}
    w, h = resolution.split("x")
    duree = get_duree_audio(audio_path)

    # Filtre de redimensionnement pour la vidéo
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"

    # Sous-titres
    if srt_path and os.path.exists(srt_path):
        srt_fixed = srt_path.replace(".srt", "_fixed.srt")
        fix_srt(srt_path, srt_fixed)
        srt_use = srt_fixed if os.path.exists(srt_fixed) else srt_path
        srt_escaped = srt_use.replace("\\", "/").replace("C:", "C\\:")
        couleur = style_st["couleur"]
        contour = style_st["contour"]
        taille  = style_st["taille"]
        taille_final = config.get("subtitle_size", taille)
        margev_final = config.get("subtitle_margin", 40)
        vf += f",subtitles='{srt_escaped}':force_style='FontName=Arial,FontSize={taille_final},PrimaryColour={couleur},OutlineColour={contour},Outline=2,Shadow=1,Alignment=2,MarginV={margev_final},BorderStyle=1'"

    # Watermark texte si pas de logo
    if not logo_path and nom_chaine:
        vf += f",drawtext=text='{nom_chaine}':fontsize=20:fontcolor=white@0.7:x=w-tw-20:y=h-th-20:shadowx=1:shadowy=1"

    # Construction de la commande FFmpeg
    # La vidéo est stream_loop -1 pour boucler si elle est plus courte que l'audio
    cmd = [
        FFMPEG, "-y",
        "-stream_loop", "-1", "-i", video_path,
        "-i", audio_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", preset, "-crf", crf,
        "-r", "25", "-t", str(duree),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
    ]

    # Ajouter le denoiser + gate audio si configuré
    combined_af = get_combined_audio_filter(config)
    if combined_af:
        cmd.extend(["-af", combined_af])

    cmd.append(output_path)

    # Ajouter logo PNG si présent (plus complexe avec overlay)
    if logo_path and os.path.exists(logo_path):
        cmd = [
            FFMPEG, "-y",
            "-stream_loop", "-1", "-i", video_path,
            "-i", audio_path,
            "-i", logo_path,
            "-filter_complex",
            f"[0:v]{vf}[bg];[bg][2:v]overlay=W-w-20:H-h-20:format=auto,format=yuv420p[out]",
            "-map", "[out]", "-map", "1:a",
            "-c:v", "libx264", "-preset", preset, "-crf", crf,
            "-r", "25", "-t", str(duree),
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
        ]
        if combined_af:
            cmd.extend(["-af", combined_af])
        cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"Erreur FFmpeg vidéo : {result.stderr[-300:]}")
    return result.returncode == 0


def fusionner_videos(segments, output_path, temp_dir):
    liste_path = os.path.join(temp_dir, "liste.txt")
    with open(liste_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"file '{seg.replace(chr(92), '/')}'\n")
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0",
           "-i", liste_path, "-c", "copy", output_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def ajouter_musique(video_path, music_path, output_path, music_volume=0.15, voice_volume=1.0, reverb=0.0, delay=0.0, eq_preset="normal"):
    """
    Ajoute de la musique de fond à une vidéo avec mixage contrôlé.
    CORRECTION : PAS de reverb/delay sur la voix — on garde la voix naturelle.
    """
    voice_vol_str = f"{voice_volume:.1f}"
    music_vol_str = f"{music_volume:.2f}"

    # EQ léger sur la musique (pas sur la voix)
    music_eq = ""
    if eq_preset == "chaleur":
        music_eq = ",equalizer=f=100:width_type=h:width=200:g=2"
    elif eq_preset == "clarte":
        music_eq = ",equalizer=f=10000:width_type=h:width=2000:g=-2"
    elif eq_preset == "basses":
        music_eq = ",equalizer=f=60:width_type=h:width=100:g=4"
    elif eq_preset == "voix":
        music_eq = ",equalizer=f=1000:width_type=h:width=500:g=3"

    # Mixage SIMPLE : voix (volume ajusté) + musique (volume bas) — PAS d'effets
    cmd = [
        FFMPEG, "-y", "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex",
        f"[0:a]volume={voice_vol_str}[voice];[1:a]volume={music_vol_str}{music_eq}[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def choisir_image(images_data, index):
    bgs = images_data.get("backgrounds", [])
    if not bgs: return None
    return bgs[index % len(bgs)]["fichier"]

def choisir_musique(music_path, project_path=None):
    """Choisir une musique : d'abord ComposIA dans audio/, puis music_path"""
    # 1. Chercher musique ComposIA dans le dossier audio du projet
    if project_path:
        audio_dir = Path(project_path) / "audio"
        if audio_dir.exists():
            fichiers = list(audio_dir.glob("musique_fond*.mp3")) + list(audio_dir.glob("musique_fond*.wav"))
            if fichiers:
                return str(fichiers[0])

    # 2. Fallback vers le chemin de config
    music_dir = Path(music_path)
    if not music_dir.exists(): return None
    fichiers = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    return str(fichiers[0]) if fichiers else None

def choisir_style(defaut="7"):
    import sys
    sys.path.insert(0, str(paths.MODULES_DIR / "utils"))
    from timeout_input import choisir_avec_timeout
    print("\n[VIDEO] Style sous-titres :")
    for k, v in STYLES_SOUS_TITRES.items():
        print(f"  [{k}] {v['nom']}")
    choix = choisir_avec_timeout(STYLES_SOUS_TITRES, defaut, 10, "Style sous-titres")
    if choix == "7":
        return random.choice([v for k,v in STYLES_SOUS_TITRES.items() if k != "7"])
    return STYLES_SOUS_TITRES.get(choix, STYLES_SOUS_TITRES["1"])

def choisir_particules(defaut="5"):
    from timeout_input import choisir_avec_timeout
    print("\n[VIDEO] Effet particules :")
    for k, v in EFFETS_PARTICULES.items():
        print(f"  [{k}] {v}")
    choix = choisir_avec_timeout(EFFETS_PARTICULES, defaut, 10, "Effet particules")
    if choix == "5":
        return random.choice([v for k,v in EFFETS_PARTICULES.items() if k not in ["5","6"]])
    return EFFETS_PARTICULES.get(choix, "aucun")

def choisir_kenburns(defaut="8"):
    from timeout_input import choisir_avec_timeout
    print("\n[VIDEO] Mouvement image :")
    for i, e in enumerate(EFFETS_KENBURNS, 1):
        print(f"  [{i}] {e}")
    print("  [8] Aleatoire par chapitre")
    opts = {str(i+1): e for i, e in enumerate(EFFETS_KENBURNS)}
    opts["8"] = "aleatoire"
    choix = choisir_avec_timeout(opts, defaut, 10, "Mouvement image")
    if choix == "8": return "aleatoire"
    try: return EFFETS_KENBURNS[int(choix)-1]
    except: return "aleatoire"

def lire_video_config(project_path):
    cfg_path = os.path.join(project_path, "video_config.json")
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

def _decider_mode_segment(mode_visuel, index_segment, total_segments,
                           index_video_deja_utilise, videos_data,
                           images_data, medias_info=None):
    """
    Décide si un segment doit utiliser une image ou une vidéo selon le mode.

    Args:
        mode_visuel: "images", "videos", "mix", "intelligent"
        index_segment: index du segment dans la séquence
        total_segments: nombre total de segments
        index_video_deja_utilise: combien de vidéos déjà utilisées
        videos_data: liste des vidéos disponibles
        images_data: dict des images disponibles
        medias_info: infos d'ambiance (mode intelligent)

    Returns:
        bool: True si on utilise une vidéo, False pour une image
    """
    # Vérifier qu'on a encore des vidéos disponibles
    if index_video_deja_utilise >= len(videos_data):
        return False

    # Vérifier qu'on a des images disponibles (fallback)
    bgs = images_data.get("backgrounds", [])
    if not bgs:
        return True  # Pas d'images → forcer vidéo

    if mode_visuel == "images":
        return False
    elif mode_visuel == "videos":
        return True
    elif mode_visuel == "mix":
        # Alternance : vidéo aux segments pairs
        return index_segment % 2 == 0
    elif mode_visuel == "intelligent":
        if not medias_info:
            return index_segment % 2 == 0

        # Mode intelligent : utiliser l'ambiance pour décider
        ambiance = medias_info.get("ambiance", {})
        rythme = ambiance.get("rythme", "modere")

        # Distribution selon le rythme
        if rythme == "lent":
            # Plus de vidéos, moins de transitions
            return index_segment % 3 != 1  # 2 vidéos sur 3
        elif rythme == "dynamique":
            # Plus d'images, coupes plus rapides
            return index_segment % 3 == 0  # 1 vidéo sur 3
        else:
            # Modéré : équilibré
            return index_segment % 2 == 0

    return False


def ajouter_intro_humaine(project_path, video_finale):
    """
    Touche humaine : fusionne l'enregistrement vocal de l'utilisateur
    en DEBUT de la video finale (si l'option est activee ET qu'une intro
    a ete enregistree pour ce projet).

    Returns:
        str or None: chemin de la video avec intro (remplace video_finale)
    """
    try:
        # Config de StudioIA-Next (ou vit l'option touche humaine)
        root_next = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(root_next))
        from modules.human_touch.intro_voice import get_intro_projet, fusionner_intro, get_parametres

        params = get_parametres()
        if not params.get("actif"):
            log("Touche humaine inactive — pas d'intro.")
            return None

        projet_nom = Path(project_path).name
        intro = get_intro_projet(projet_nom)
        if not intro.get("ok"):
            log(f"Touche humaine active mais AUCUNE intro enregistree pour '{projet_nom}'.")
            log("  Enregistre ta voix dans la page /human-touch puis relance la video.")
            return None

        intro_audio = intro.get("audio")
        # Nom de sortie distinct (ffmpeg refuse d'ecrire sur le fichier d'entree)
        video_avec_intro = video_finale.replace("_final.mp4", "_avec_intro.mp4")
        if video_avec_intro == video_finale:
            video_avec_intro = video_finale.rsplit(".", 1)[0] + "_avec_intro.mp4"
        res = fusionner_intro(video_finale, intro_audio, video_avec_intro)
        if res.get("ok"):
            os.replace(video_avec_intro, video_finale)  # la video avec intro devient la finale
            log(f"INTRO VOCALE ajoutee au debut de la video ({res.get('message')})")
            return video_finale
        log(f"Echec fusion intro: {res.get('message')}")
    except Exception as e:
        log(f"Erreur touche humaine: {e}")
    return None


def main():
    project_path = sys.argv[1]
    pjson = os.path.join(project_path, "project.json")
    config    = lire_json(paths.config_path())
    data      = lire_json(pjson)
    vid_cfg   = lire_video_config(project_path)
    crf, preset, use_zoompan = get_parametres_qualite(
        vid_cfg.get("qualite","1"),
        vid_cfg.get("zoompan","0")
    )
    audio_fmt = {"1":"mp3","2":"aac","3":"wav"}.get(vid_cfg.get("audio_fmt","1"),"mp3")
    log(f"Qualite : CRF {crf} / {preset}")
    log(f"Zoompan : {use_zoompan}")
    log(f"Audio   : {audio_fmt}")

    langue       = data.get("langue", "fr")
    type_contenu = data.get("type_contenu", "priere")
    chapitres    = data.get("chapitres", [])
    images_data  = data.get("images_data", {})
    resolution   = config.get("video_resolution", "1920x1080")
    logo_path    = data.get("logo_path", "")

    # Nom chaine selon langue et type
    if langue == "en":
        nom_chaine = "Unspoken"
    elif type_contenu == "priere":
        nom_chaine = "Priere Connexion Divine"
    else:
        nom_chaine = "Unspoken"

    temp_dir   = os.path.join(project_path, "temp_video")
    export_dir = os.path.join(project_path, "export", "video")
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(export_dir, exist_ok=True)

        # Parametres depuis ligne de commande ou interactif
    if len(sys.argv) > 3:
        st_map = {"1": STYLES_SOUS_TITRES["1"],"2": STYLES_SOUS_TITRES["2"],"3": STYLES_SOUS_TITRES["3"],"4": STYLES_SOUS_TITRES["4"],"5": STYLES_SOUS_TITRES["5"],"6": STYLES_SOUS_TITRES["6"],"7": random.choice([v for k,v in STYLES_SOUS_TITRES.items() if k != "7"])}
        part_map = {"1":"pluie_or","2":"etincelles","3":"lueurs","4":"neige","5":random.choice(["pluie_or","etincelles","lueurs","neige"]),"6":"aucun"}
        kb_map = {"1":"zoom_in_centre","2":"zoom_out_centre","3":"pan_gauche_droite","4":"pan_droite_gauche","5":"zoom_in_gauche","6":"zoom_in_droite","7":"pan_haut_bas","8":"aleatoire"}
        style_st   = st_map.get(sys.argv[2], random.choice([v for k,v in STYLES_SOUS_TITRES.items() if k != "7"]))
        particules = part_map.get(sys.argv[3], "aleatoire")
        kenburns   = kb_map.get(sys.argv[4] if len(sys.argv) > 4 else "8", "aleatoire")
        logo_path  = sys.argv[5] if len(sys.argv) > 5 else ""
    else:
        # Valeurs par defaut si pas de parametres ligne de commande
        style_st   = choisir_style("7")
        particules = choisir_particules("5")
        kenburns   = choisir_kenburns("8")

    log(f"Sous-titres : {style_st['nom']}")
    log(f"Particules  : {particules}")
    log(f"Mouvement   : {kenburns}")
    log(f"Chaine      : {nom_chaine}")
    log(f"Logo        : {logo_path if logo_path else 'aucun'}")

    # ================================================================
    # MODE VISUEL : Préparer les médias vidéo si nécessaire
    # ================================================================
    mode_visuel = config.get("mode_visuel", "images")
    medias_info = None
    videos_data = []

    # Si le mode inclut des vidéos, préparer la bibliothèque média
    if mode_visuel in ("videos", "mix", "intelligent"):
        try:
            duree_totale = sum(get_duree_audio(
                os.path.join(project_path, "audio", f"{ch['id']}.wav")
            ) for ch in chapitres if os.path.exists(
                os.path.join(project_path, "audio", f"{ch['id']}.wav")
            ))
            if duree_totale == 0:
                duree_totale = 3600  # fallback 1h

            lib = MediaLibrary(config)
            medias_info = lib.preparer_medias_pour_projet(
                sujet=data.get("sujet", "Vidéo"),
                duree_secondes=duree_totale,
                mode_visuel=mode_visuel,
                langue=langue,
                projet_id=data.get("id", "projet")
            )
            videos_data = medias_info.get("videos", [])
            log(f"{len(videos_data)} vidéos disponibles pour ce projet")
        except Exception as e:
            log(f"Erreur préparation médias vidéo: {e}")
            log("Fallback: mode images uniquement")
            mode_visuel = "images"
    else:
        mode_visuel = "images"

    data["etapes"]["video"] = "en_cours"
    ecrire_json(pjson, data)

    segments_ok = []
    index_video = 0  # compteur pour alterner les vidéos

    for i, ch in enumerate(chapitres):
        ch_id      = ch["id"]
        audio_path = os.path.join(project_path, "audio", f"{ch_id}.wav")
        srt_path   = os.path.join(project_path, "audio", f"{ch_id}.srt")
        seg_output = os.path.join(temp_dir, f"seg_{ch_id}.mp4")

        if os.path.exists(seg_output):
            log(f"{ch_id} deja existe.")
            segments_ok.append(seg_output)
            continue

        if not os.path.exists(audio_path):
            log(f"{ch_id} audio manquant.")
            continue

        # Décider si ce segment utilise une image ou une vidéo
        utiliser_video = _decider_mode_segment(
            mode_visuel, i, len(chapitres), index_video, videos_data,
            images_data, medias_info
        )

        if utiliser_video and index_video < len(videos_data):
            # SEGMENT VIDÉO
            video_item = videos_data[index_video]
            video_path = video_item["chemin"]

            if not os.path.exists(video_path):
                log(f"{ch_id} vidéo manquante, fallback image")
                utiliser_video = False
            else:
                index_video += 1
                log(f"Segment {i+1}/{len(chapitres)} : {ch_id} [VIDEO]")

                ok = construire_segment_video(
                    video_path, audio_path, srt_path, seg_output,
                    resolution, style_st, config,
                    logo_path, langue, nom_chaine,
                    crf=crf, preset=preset
                )

        if not utiliser_video:
            # SEGMENT IMAGE (comportement existant)
            img_rel = choisir_image(images_data, i - index_video)
            if not img_rel: continue

            img_path = os.path.join(project_path, img_rel)
            if not os.path.exists(img_path): continue

            # Zoompan desactive si qualite rapide
            if not use_zoompan:
                kb = "aucun"
            else:
                kb = random.choice(EFFETS_KENBURNS) if kenburns == "aleatoire" else kenburns
            log(f"Segment {i+1}/{len(chapitres)} : {ch_id} [{kb}]")

            ok = construire_segment(
                img_path, audio_path, srt_path, seg_output,
                kb, particules, style_st, resolution,
                logo_path, langue, nom_chaine,
                crf=crf, preset=preset, config=config
            )
        if ok:
            segments_ok.append(seg_output)
            log(f"{ch_id} OK")
        else:
            log(f"{ch_id} ECHEC")

    if not segments_ok:
        log("Aucun segment. Arret.")
        sys.exit(1)

    # Kdenlive remplace par Shotcut

    log(f"Fusion {len(segments_ok)} segments...")
    video_brute  = os.path.join(temp_dir, "video_brute.mp4")
    # Utiliser le nom lisible (sujet) pour le nom de la vidéo finale
    nom_lisible = data.get("nom_lisible", data.get("sujet", "video")).replace(" ", "_").replace("/", "_")
    video_finale = os.path.join(export_dir, f"{nom_lisible}_final.mp4")
    fusionner_videos(segments_ok, video_brute, temp_dir)

    music_file = choisir_musique(str(paths.MUSIC_DIR), project_path)
    if music_file:
        log(f"Musique : {os.path.basename(music_file)}")
        # Récupérer les paramètres audio depuis config
        voice_vol = config.get("voice_volume", 1.0)
        music_vol = config.get("music_volume", 0.15)
        reverb = config.get("reverb_level", 0.3)
        delay = config.get("delay_level", 0.2)
        eq_preset = config.get("eq_preset", "normal")
        log(f"Paramètres audio: voix={voice_vol:.1f}x, musique={music_vol:.2f}, reverb={reverb}, delay={delay}, eq={eq_preset}")
        ok_m = ajouter_musique(video_brute, music_file, video_finale,
                               music_vol, voice_vol, reverb, delay, eq_preset)
        if not ok_m:
            shutil.copy(video_brute, video_finale)
    else:
        log("Pas de musique.")
        shutil.copy(video_brute, video_finale)

    shutil.rmtree(temp_dir, ignore_errors=True)

    # Touche humaine : ajouter la voix reelle de l'utilisateur en debut de video
    ajouter_intro_humaine(project_path, video_finale)

    data["etapes"]["video"] = "termine"
    data["fichier_final"]   = f"export/{nom_lisible}_final.mp4"
    ecrire_json(pjson, data)

    taille = os.path.getsize(video_finale) / (1024*1024)
    log(f"Video finale : {video_finale}")
    log(f"Taille       : {taille:.1f} Mo")
    log("VIDEO TERMINEE !")

    # Verification Whisper post-traitement
    if config.get("verification_enabled", True):
        log("\n=== VERIFICATION AUDIO WHISPER ===")
        try:
            result_whisper = verifier_audio_avec_whisper(project_path, config)
            if result_whisper.get("problemes", 0) > 0:
                log(f"⚠  {result_whisper['problemes']} segments problématiques")
            else:
                log("✅ Vérification audio OK")
        except Exception as e:
            log(f"Erreur vérification: {e}")
    else:
        log("Vérification Whisper désactivée")

    # Generer projet Shotcut automatiquement
    log("Generation projet Shotcut...")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gen_shotcut",
            str(paths.MODULES_DIR / "video" / "gen_shotcut.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.generer_mlt(project_path, auto=True)
        log("Projet Shotcut cree !")
    except Exception as e:
        log(f"Shotcut erreur : {e}")

if __name__ == "__main__":
    main()