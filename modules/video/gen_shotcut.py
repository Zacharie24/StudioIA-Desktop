import json, os, sys, subprocess, re, random, math
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

FFMPEG    = str(paths.FFMPEG)
SHOTCUT   = "C:\\Program Files\\Shotcut\\shotcut.exe"
MUSIC_DIR = str(paths.MUSIC_DIR)

def get_projet_musique(project_path):
    """Chercher la musique ComposIA dans le dossier audio du projet"""
    audio_dir = Path(project_path) / "audio"
    if audio_dir.exists():
        fichiers = list(audio_dir.glob("musique_fond*.mp3")) + list(audio_dir.glob("musique_fond*.wav"))
        if fichiers:
            return str(fichiers[0])
    return None

def lire_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def get_duree_tc(path):
    result = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            t = line.strip().split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            sec = float(h)*3600 + float(m)*60 + float(s)
            hh = int(sec//3600); mm = int((sec%3600)//60); ss = sec%60
            return f"{hh:02d}:{mm:02d}:{ss:06.3f}", sec
    return "00:01:00.000", 60

def lire_srt(path):
    for enc in ["utf-8","utf-8-sig","latin-1"]:
        try:
            with open(path,"r",encoding=enc) as f: return f.read()
        except: continue
    return ""

def decaler_srt(srt, offset):
    def tc_ms(tc):
        h,m,s = tc.replace(",",".").split(":")
        return int((float(h)*3600+float(m)*60+float(s))*1000)
    def ms_tc(ms):
        h=ms//3600000; ms%=3600000; m=ms//60000; ms%=60000
        s=ms//1000; ms%=1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    off = int(offset*1000)
    return re.sub(r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})',
        lambda m: f"{ms_tc(tc_ms(m.group(1))+off)} --> {ms_tc(tc_ms(m.group(2))+off)}", srt)

def fusionner_srt(items):
    out = ""; n = 1
    for item in items:
        if item.get("srt"):
            for bloc in item["srt"].strip().split("\n\n"):
                lignes = bloc.strip().split("\n")
                if len(lignes) >= 3:
                    out += f"{n}\n" + "\n".join(lignes[1:]) + "\n\n"; n += 1
    return out

def choisir_musique():
    d = Path(MUSIC_DIR)
    if not d.exists(): return None
    f = list(d.glob("*.mp3")) + list(d.glob("*.wav")) + list(d.glob("*.m4a")) + list(d.glob("*.ogg"))
    if not f: return None
    choix = random.choice(f)
    print(f"[SHOTCUT] Musique selectionnee : {choix.name}")
    return str(choix).replace("\\","/")

def get_meta_audio(path):
    result = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    meta = {
        "nb_streams": "1",
        "stream_type": "audio",
        "sample_fmt": "s16",
        "sample_rate": "44100",
        "channels": "2",
        "layout": "stereo",
        "codec_name": "pcm_s16le",
        "bit_rate": "1411200"
    }
    # Detecter MP3
    if path.endswith(".mp3"):
        meta["codec_name"] = "mp3"
        meta["sample_fmt"] = "fltp"
        meta["bit_rate"] = "128000"
    return meta

def choisir_options():
    print("\n  ================================")
    print("  OPTIONS DE GENERATION")
    print("  ================================")

    print("\n  [1] QUALITE VIDEO :")
    print("    [1] Rapide  (CRF 28, sans zoompan) — 30min, ~300MB")
    print("    [2] Normal  (CRF 23, zoompan leger) — 2h, ~1GB")
    print("    [3] Qualite (CRF 18, zoompan complet) — 5h+, ~3GB")
    q = input("  Choix qualite [1] : ").strip() or "1"

    print("\n  [2] EFFET ZOOMPAN (mouvement image) :")
    print("    [1] Oui — Ken Burns")
    print("    [2] Non — image statique (plus rapide)")
    z = input("  Choix zoompan [2] : ").strip() or "2"

    print("\n  [3] FORMAT AUDIO FINAL :")
    print("    [1] MP3 128k — leger et rapide")
    print("    [2] AAC 192k — bonne qualite")
    print("    [3] WAV      — non compresse")
    a = input("  Choix audio [1] : ").strip() or "1"

    qualite = {"1": {"crf":"28","preset":"veryfast"}, "2": {"crf":"23","preset":"fast"}, "3": {"crf":"18","preset":"slow"}}.get(q, {"crf":"28","preset":"veryfast"})
    zoompan = z == "1"
    audio_fmt = {"1":"mp3","2":"aac","3":"wav"}.get(a,"mp3")

    return qualite, zoompan, audio_fmt

def generer_mlt(project_path, auto=False):
    data        = lire_json(os.path.join(project_path, "project.json"))
    chapitres   = data.get("chapitres", [])
    images_data = data.get("images_data", {})
    bgs         = images_data.get("backgrounds", [])
    export_dir  = os.path.join(project_path, "export")
    os.makedirs(export_dir, exist_ok=True)

    projet_id = data.get("id", "projet")
    sujet     = data.get("sujet", "Projet")
    langue    = data.get("langue", "fr")
    lang_code = "fre" if langue == "fr" else "eng"

    # Utiliser export/video pour les vidéos longues
    export_dir = os.path.join(project_path, "export", "video")
    os.makedirs(export_dir, exist_ok=True)
    mlt_path  = os.path.join(export_dir, f"{projet_id}_shotcut.mlt")

    if auto:
        qualite  = {"crf":"23","preset":"fast"}
        zoompan  = False
        audio_fmt = "mp3"
    else:
        qualite, zoompan, audio_fmt = choisir_options()

    print(f"\nQualite : CRF {qualite['crf']} / {qualite['preset']}")
    print(f"Zoompan : {'Oui' if zoompan else 'Non'}")
    print(f"Audio   : {audio_fmt}")

    items = []; curseur = 0.0

    for i, ch in enumerate(chapitres):
        ch_id = ch["id"]
        # Chercher WAV ou MP3
        audio_path = ""
        for ext in [".wav", ".mp3"]:
            p = os.path.join(project_path, "audio", f"{ch_id}{ext}")
            if os.path.exists(p):
                audio_path = p; break
        if not audio_path:
            log(f"  {ch_id} audio manquant")
            continue

        srt_path = os.path.join(project_path, "audio", f"{ch_id}.srt")
        img_rel  = ch.get("image_file","")
        if not img_rel and bgs:
            img_rel = bgs[i % len(bgs)]["fichier"]
        img_path = os.path.join(project_path, img_rel) if img_rel else ""
        if not os.path.exists(img_path): img_path = ""

        tc, duree = get_duree_tc(audio_path)
        srt = decaler_srt(lire_srt(srt_path), curseur) if os.path.exists(srt_path) else ""
        meta = get_meta_audio(audio_path)

        items.append({
            "ch_id":   ch_id,
            "audio":   audio_path.replace("\\","/"),
            "audio_ext": os.path.splitext(audio_path)[1],
            "image":   img_path.replace("\\","/") if img_path else "",
            "img_nom": os.path.basename(img_path) if img_path else "",
            "srt":     srt,
            "tc":      tc,
            "duree":   duree,
            "meta":    meta,
        })
        curseur += duree

    hh=int(curseur//3600); mm=int((curseur%3600)//60); ss=curseur%60
    tc_total   = f"{hh:02d}:{mm:02d}:{ss:06.3f}"
    srt_global = fusionner_srt(items)

    # Chercher d'abord la musique ComposIA du projet, sinon assets/music
    musique = get_projet_musique(project_path)
    if not musique:
        musique = choisir_musique()

    x = []
    x.append('<?xml version="1.0" standalone="no"?>')
    x.append(f'<mlt LC_NUMERIC="C" version="7.40.0" title="StudioIA - {sujet}" producer="main_bin">')
    x.append('  <profile description="HD 1080p 25 fps" width="1920" height="1080"')
    x.append('    progressive="1" sample_aspect_num="1" sample_aspect_den="1"')
    x.append('    display_aspect_num="16" display_aspect_den="9"')
    x.append('    frame_rate_num="25" frame_rate_den="1" colorspace="709"/>')
    x.append('  <playlist id="main_bin">')
    x.append('    <property name="xml_retain">1</property>')
    x.append('  </playlist>')

    # Black
    x.append(f'  <producer id="black" in="00:00:00.000" out="{tc_total}">')
    x.append(f'    <property name="length">{tc_total}</property>')
    x.append(f'    <property name="eof">pause</property>')
    x.append(f'    <property name="resource">0</property>')
    x.append(f'    <property name="mlt_service">color</property>')
    x.append(f'    <property name="mlt_image_format">rgba</property>')
    x.append(f'    <property name="set.test_audio">0</property>')
    x.append(f'  </producer>')
    x.append('  <playlist id="background">')
    x.append(f'    <entry producer="black" in="00:00:00.000" out="{tc_total}"/>')
    x.append('  </playlist>')

    # Audio chains (WAV et MP3 supportes)
    for item in items:
        meta = item["meta"]
        x.append(f'  <chain id="chain_{item["ch_id"]}" out="{item["tc"]}">')
        x.append(f'    <property name="length">{item["tc"]}</property>')
        x.append(f'    <property name="eof">pause</property>')
        x.append(f'    <property name="resource">{item["audio"]}</property>')
        x.append(f'    <property name="mlt_service">avformat-novalidate</property>')
        x.append(f'    <property name="meta.media.nb_streams">1</property>')
        x.append(f'    <property name="meta.media.0.stream.type">audio</property>')
        x.append(f'    <property name="meta.media.0.codec.sample_rate">{meta["sample_rate"]}</property>')
        x.append(f'    <property name="meta.media.0.codec.channels">{meta["channels"]}</property>')
        x.append(f'    <property name="meta.media.0.codec.name">{meta["codec_name"]}</property>')
        x.append(f'    <property name="seekable">1</property>')
        x.append(f'    <property name="audio_index">0</property>')
        x.append(f'    <property name="video_index">-1</property>')
        x.append(f'    <property name="astream">0</property>')
        x.append(f'    <property name="shotcut:skipConvert">1</property>')
        x.append(f'    <property name="shotcut:caption">{item["ch_id"]}{item["audio_ext"]}</property>')
        x.append(f'  </chain>')

    # Image producers
    for item in items:
        if item["image"]:
            x.append(f'  <producer id="img_{item["ch_id"]}" in="00:00:00.000" out="03:59:59.960">')
            x.append(f'    <property name="length">04:00:00.000</property>')
            x.append(f'    <property name="eof">pause</property>')
            x.append(f'    <property name="resource">{item["image"]}</property>')
            x.append(f'    <property name="ttl">1</property>')
            x.append(f'    <property name="aspect_ratio">1</property>')
            x.append(f'    <property name="seekable">1</property>')
            x.append(f'    <property name="mlt_service">qimage</property>')
            x.append(f'    <property name="shotcut:caption">{item["img_nom"]}</property>')
            x.append(f'  </producer>')

    # Musique
    if musique:
        tc_m, _ = get_duree_tc(musique)
        meta_m   = get_meta_audio(musique)
        x.append(f'  <chain id="chain_music" out="{tc_total}">')
        x.append(f'    <property name="length">{tc_total}</property>')
        x.append(f'    <property name="eof">loop</property>')
        x.append(f'    <property name="resource">{musique}</property>')
        x.append(f'    <property name="mlt_service">avformat-novalidate</property>')
        x.append(f'    <property name="meta.media.0.codec.name">{meta_m["codec_name"]}</property>')
        x.append(f'    <property name="seekable">1</property>')
        x.append(f'    <property name="audio_index">0</property>')
        x.append(f'    <property name="video_index">-1</property>')
        x.append(f'    <property name="astream">0</property>')
        x.append(f'    <property name="shotcut:caption">{os.path.basename(musique)}</property>')
        # Volume bas
        x.append(f'    <filter id="filt_music_vol">')
        x.append(f'      <property name="mlt_service">volume</property>')
        x.append(f'      <property name="level">-20</property>')
        x.append(f'    </filter>')
        x.append(f'  </chain>')

    # Playlist V1 images
    x.append('  <playlist id="playlist_video">')
    x.append('    <property name="shotcut:video">1</property>')
    x.append('    <property name="shotcut:name">V1 - Images</property>')
    for item in items:
        if item["image"]:
            x.append(f'    <entry producer="img_{item["ch_id"]}" in="00:00:00.000" out="{item["tc"]}"/>')
        else:
            x.append(f'    <blank length="{item["tc"]}"/>')
    x.append('  </playlist>')

    # Playlist A1 voix (meme format que Shotcut genere lui-meme)
    x.append('  <playlist id="playlist_audio">')
    x.append('    <property name="shotcut:video">1</property>')
    x.append('    <property name="shotcut:name">A1 - Voix</property>')
    for item in items:
        x.append(f'    <entry producer="chain_{item["ch_id"]}" in="00:00:00.000" out="{item["tc"]}"/>')
    x.append('  </playlist>')

    # Playlist A2 musique
    if musique:
        x.append('  <playlist id="playlist_music">')
        x.append('    <property name="shotcut:video">1</property>')
        x.append('    <property name="shotcut:name">A2 - Musique fond</property>')
        x.append(f'    <entry producer="chain_music" in="00:00:00.000" out="{tc_total}"/>')
        x.append('  </playlist>')

    # Tractor
    x.append(f'  <tractor id="tractor0" title="StudioIA - {sujet}" in="00:00:00.000" out="{tc_total}">')
    x.append('    <property name="shotcut">1</property>')
    x.append('    <property name="shotcut:projectAudioChannels">2</property>')
    x.append('    <property name="shotcut:projectFolder">0</property>')
    x.append('    <property name="shotcut:processingMode">Native8Cpu</property>')
    x.append('    <track producer="background"/>')
    x.append('    <track producer="playlist_video"/>')
    x.append('    <track producer="playlist_audio"/>')
    if musique:
        x.append('    <track producer="playlist_music"/>')
    x.append('    <transition id="transition0">')
    x.append('      <property name="a_track">0</property>')
    x.append(f'      <property name="b_track">{2 if musique else 1}</property>')
    x.append('      <property name="mlt_service">mix</property>')
    x.append('      <property name="always_active">1</property>')
    x.append('      <property name="sum">1</property>')
    x.append('    </transition>')
    x.append('    <transition id="transition1">')
    x.append('      <property name="a_track">0</property>')
    x.append('      <property name="b_track">1</property>')
    x.append('      <property name="mlt_service">qtblend</property>')
    x.append('      <property name="compositing">0</property>')
    x.append('      <property name="disable">1</property>')
    x.append('    </transition>')

    # SRT
    if srt_global.strip():
        srt_esc = srt_global.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        x.append('    <filter id="filter_srt">')
        x.append(f'      <property name="feed">Sous-titres</property>')
        x.append(f'      <property name="lang">{lang_code}</property>')
        x.append(f'      <property name="mlt_service">subtitle_feed</property>')
        x.append(f'      <property name="shotcut:hidden">1</property>')
        x.append(f'      <property name="text">{srt_esc}</property>')
        x.append('    </filter>')

    x.append('  </tractor>')
    x.append('</mlt>')

    with open(mlt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(x))

    print(f"\nProjet Shotcut : {mlt_path}")
    print(f"Chapitres      : {len(items)}")
    print(f"Duree totale   : {tc_total}")
    print(f"SRT integre    : {'Oui' if srt_global.strip() else 'Non'}")
    print(f"Musique        : {'Oui - '+os.path.basename(musique) if musique else 'Non'}")

    if os.path.exists(SHOTCUT):
        subprocess.Popen([SHOTCUT, mlt_path])
        print("Shotcut ouvert !")

    return mlt_path


def generer_mlt_for_short(project_path, short_idx, titre, audio_path, image_path, video_path, config):
    """
    Genere un projet Shotcut pour un Short specifique.
    """
    music_path = None
    musique_dir = paths.MUSIC_DIR
    if musique_dir.exists():
        fichiers = list(musique_dir.glob("*.mp3")) + list(musique_dir.glob("*.wav"))
        if fichiers:
            music_path = str(fichiers[0])

    # Recuperer le volume musique de la config
    music_volume = config.get("music_volume", 0.15)

    # Dossier export
    export_dir = Path(project_path) / "export" / "shorts"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Nom du fichier shotcut
    short_id = f"short_{short_idx:02d}"
    mlt_path = str(export_dir / f"{short_id}_shotcut.mlt")

    # Duree du short
    tc, duree = get_duree_tc(video_path)

    x = []
    x.append('<?xml version="1.0" standalone="no"?>')
    x.append(f'<mlt LC_NUMERIC="C" version="7.40.0" title="Short - {titre[:40]}" producer="main_bin">')
    x.append('  <profile description="HD 1080p 25 fps" width="1080" height="1920"')
    x.append('    progressive="1" sample_aspect_num="1" sample_aspect_den="1"')
    x.append('    display_aspect_num="9" display_aspect_den="16"')
    x.append('    frame_rate_num="25" frame_rate_den="1" colorspace="709"/>')

    # Black background
    x.append(f'  <producer id="black" in="00:00:00.000" out="{tc}">')
    x.append(f'    <property name="length">{tc}</property>')
    x.append(f'    <property name="eof">pause</property>')
    x.append(f'    <property name="resource">0</property>')
    x.append(f'    <property name="mlt_service">color</property>')
    x.append(f'    <property name="mlt_image_format">rgba</property>')
    x.append(f'    <property name="set.test_audio">0</property>')
    x.append(f'  </producer>')
    x.append('  <playlist id="background">')
    x.append(f'    <entry producer="black" in="00:00:00.000" out="{tc}"/>')
    x.append('  </playlist>')

    # Audio (voix)
    meta_audio = get_meta_audio(audio_path)
    x.append(f'  <chain id="chain_voix" out="{tc}">')
    x.append(f'    <property name="length">{tc}</property>')
    x.append(f'    <property name="eof">pause</property>')
    # Prepare path for XML (replace backslashes with forward slashes)
    audio_path_xml = audio_path.replace("\\", "/")
    x.append(f'    <property name="resource">{audio_path_xml}</property>')
    x.append(f'    <property name="mlt_service">avformat-novalidate</property>')
    x.append(f'    <property name="meta.media.0.codec.name">{meta_audio["codec_name"]}</property>')
    x.append(f'    <property name="meta.media.0.codec.sample_rate">{meta_audio["sample_rate"]}</property>')
    x.append(f'    <property name="meta.media.0.codec.channels">{meta_audio["channels"]}</property>')
    x.append(f'    <property name="seekable">1</property>')
    x.append(f'    <property name="audio_index">0</property>')
    x.append(f'    <property name="video_index">-1</property>')
    x.append(f'    <property name="astream">0</property>')
    x.append(f'    <property name="shotcut:caption">Voix</property>')
    x.append(f'  </chain>')

    # Image
    x.append(f'  <producer id="img_video" in="00:00:00.000" out="{tc}">')
    x.append(f'    <property name="length">{tc}</property>')
    x.append(f'    <property name="eof">pause</property>')
    # Prepare path for XML
    image_path_xml = image_path.replace("\\", "/")
    x.append(f'    <property name="resource">{image_path_xml}</property>')
    x.append(f'    <property name="ttl">1</property>')
    x.append(f'    <property name="aspect_ratio">1</property>')
    x.append(f'    <property name="seekable">1</property>')
    x.append(f'    <property name="mlt_service">qimage</property>')
    x.append(f'    <property name="shotcut:caption">Image</property>')
    x.append(f'  </producer>')

    # Video (clip exporte)
    meta_video = get_meta_audio(video_path)
    x.append(f'  <chain id="chain_video" out="{tc}">')
    x.append(f'    <property name="length">{tc}</property>')
    x.append(f'    <property name="eof">pause</property>')
    # Prepare path for XML
    video_path_xml = video_path.replace("\\", "/")
    x.append(f'    <property name="resource">{video_path_xml}</property>')
    x.append(f'    <property name="mlt_service">avformat-novalidate</property>')
    x.append(f'    <property name="meta.media.0.codec.name">{meta_video["codec_name"]}</property>')
    x.append(f'    <property name="meta.media.0.codec.sample_rate">{meta_video["sample_rate"]}</property>')
    x.append(f'    <property name="meta.media.0.codec.channels">{meta_video["channels"]}</property>')
    x.append(f'    <property name="seekable">1</property>')
    x.append(f'    <property name="audio_index">0</property>')
    x.append(f'    <property name="video_index">-1</property>')
    x.append(f'    <property name="astream">0</property>')
    x.append(f'    <property name="shotcut:caption">Video finale</property>')
    x.append(f'  </chain>')

    # Musique
    if music_path:
        tc_m, _ = get_duree_tc(music_path)
        meta_m = get_meta_audio(music_path)

        # Convertir le volume (0.15 = -16dB approx)
        volume_db = int(20 * math.log10(music_volume) * 10) / 10 if music_volume > 0 else -100

        # Prepare path for XML
        music_path_xml = music_path.replace("\\", "/")

        x.append(f'  <chain id="chain_music" out="{tc}">')
        x.append(f'    <property name="length">{tc}</property>')
        x.append(f'    <property name="eof">loop</property>')
        x.append(f'    <property name="resource">{music_path_xml}</property>')
        x.append(f'    <property name="mlt_service">avformat-novalidate</property>')
        x.append(f'    <property name="meta.media.0.codec.name">{meta_m["codec_name"]}</property>')
        x.append(f'    <property name="seekable">1</property>')
        x.append(f'    <property name="audio_index">0</property>')
        x.append(f'    <property name="video_index">-1</property>')
        x.append(f'    <property name="astream">0</property>')
        x.append(f'    <property name="shotcut:caption">{music_path.split("/")[-1]}</property>')
        x.append(f'    <filter id="filt_music_vol">')
        x.append(f'      <property name="mlt_service">volume</property>')
        x.append(f'      <property name="level">{volume_db}</property>')
        x.append(f'    </filter>')
        x.append(f'  </chain>')

    # Playlist video
    x.append('  <playlist id="playlist_video">')
    x.append('    <property name="shotcut:video">1</property>')
    x.append('    <property name="shotcut:name">V1 - Video</property>')
    x.append(f'    <entry producer="img_video" in="00:00:00.000" out="{tc}"/>')
    x.append('  </playlist>')

    # Playlist audio
    x.append('  <playlist id="playlist_audio">')
    x.append('    <property name="shotcut:video">1</property>')
    x.append('    <property name="shotcut:name">A1 - Voix + Musique</property>')
    x.append(f'    <entry producer="chain_voix" in="00:00:00.000" out="{tc}"/>')
    if music_path:
        x.append(f'    <entry producer="chain_music" in="00:00:00.000" out="{tc}"/>')
    x.append('  </playlist>')

    # Tractor
    x.append(f'  <tractor id="tractor0" title="Short - {titre[:40]}" in="00:00:00.000" out="{tc}">')
    x.append('    <property name="shotcut">1</property>')
    x.append('    <property name="shotcut:projectAudioChannels">2</property>')
    x.append('    <property name="shotcut:projectFolder">0</property>')
    x.append('    <property name="shotcut:processingMode">Native8Cpu</property>')
    x.append('    <track producer="background"/>')
    x.append('    <track producer="playlist_video"/>')
    x.append('    <track producer="playlist_audio"/>')
    x.append('    <transition id="transition0">')
    x.append('      <property name="a_track">0</property>')
    x.append('      <property name="b_track">1</property>')
    x.append('      <property name="mlt_service">mix</property>')
    x.append('      <property name="always_active">1</property>')
    x.append('      <property name="sum">1</property>')
    x.append('    </transition>')
    x.append('  </tractor>')
    x.append('</mlt>')

    # Ecrire le fichier
    with open(mlt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(x))

    print(f"[SHOTCUT] Projet Short genere : {mlt_path}")

    if os.path.exists(SHOTCUT):
        subprocess.Popen([SHOTCUT, mlt_path])
        print(f"[SHOTCUT] Shotcut ouvert !")


def detect_project_type(project_path):
    """Detecte si c'est un projet video ou shorts"""
    pjson = os.path.join(project_path, "project.json")
    planjson = os.path.join(project_path, "plan.json")
    if os.path.exists(pjson):
        return "video"
    elif os.path.exists(planjson):
        return "shorts"
    return None

if __name__ == "__main__":
    project_path = sys.argv[1] if len(sys.argv) > 1 else str(paths.PROJECTS_DIR / "video_20260614_074242")
    auto = len(sys.argv) > 2 and sys.argv[2] == "--auto"

    project_type = detect_project_type(project_path)
    if project_type == "shorts":
        # Projets Shorts ont deja genere les Shotcuts
        print(f"[SHOTCUT] Projet Shorts detecte - deja genere")
    else:
        generer_mlt(project_path, auto=auto)