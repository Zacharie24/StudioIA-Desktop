# -*- coding: utf-8 -*-
"""
intro_voice.py — Touche humaine : voix reelle pour les introductions

Permet d'ajouter la voix de l'utilisateur (enregistree au micro) en debut
de chaque video, pour apporter une valeur humaine reelle et ne pas etre
penalise par YouTube (contenu sans valeur ajoutee / IA pure).

Flux :
  1. L'utilisateur active l'option "touche humaine"
  2. Le systeme genere un TEXTE D'INTRO (modifiable dans l'interface)
  3. L'utilisateur enregistre sa voix au micro (avec indicateur de niveau DB)
  4. L'enregistrement est sauvegarde dans data/human_touch/
  5. Le pipeline ajoute automatiquement l'intro en debut de video
"""

import json
import subprocess
import sys
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"
HUMAN_TOUCH_DIR = Path(__file__).parent.parent.parent / "data" / "human_touch"
DEFAUT_ACTIF = False
DEFAUT_DUREE = 30  # secondes
DEFAUT_MODE = "ia"  # "ia" = l'IA ecrit un texte a lire ; "libre" = l'utilisateur improvise
MODES_AUTORISES = ("ia", "libre")


def log(msg):
    print(f"[HUMAN-TOUCH] {msg}")


def _lire_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def _ecrire_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_parametres():
    """Retourne la config de la touche humaine."""
    config = _lire_config()
    ht = config.get("human_touch", {})
    return {
        "actif": ht.get("actif", DEFAUT_ACTIF),
        "duree_intro_secondes": ht.get("duree_intro_secondes", DEFAUT_DUREE),
        "mode": ht.get("mode", DEFAUT_MODE),
        "dossier": str(HUMAN_TOUCH_DIR),
        "nb_enregistrements": len(lister_enregistrements()),
        "config_globale": config
    }


def activer(actif):
    """Active/desactive la touche humaine dans la config."""
    config = _lire_config()
    ht = config.get("human_touch", {})
    ht["actif"] = bool(actif)
    ht["modifie_le"] = datetime.now().isoformat()
    config["human_touch"] = ht
    _ecrire_config(config)
    return {"ok": True, "actif": bool(actif)}


def set_duree(duree_secondes):
    """Regle la duree cible de l'intro."""
    config = _lire_config()
    ht = config.get("human_touch", {})
    ht["duree_intro_secondes"] = max(10, int(duree_secondes))
    config["human_touch"] = ht
    _ecrire_config(config)
    return {"ok": True, "duree_intro_secondes": ht["duree_intro_secondes"]}


def set_mode(mode):
    """
    Regle le mode de la touche humaine.

    mode="ia"   : l'IA ecrit un texte d'intro que l'utilisateur lit a voix haute.
    mode="libre": PAS de texte genere — l'utilisateur improvise librement au micro,
                  et la video commence directement (l'IA ne cree aucune intro).
    """
    if mode not in MODES_AUTORISES:
        return {"ok": False, "erreur": f"Mode invalide: {mode}. Autorises: {MODES_AUTORISES}"}
    config = _lire_config()
    ht = config.get("human_touch", {})
    ht["mode"] = mode
    ht["modifie_le"] = datetime.now().isoformat()
    config["human_touch"] = ht
    _ecrire_config(config)
    return {"ok": True, "mode": mode}


# ---------------------------------------------------------------
# Generation du texte d'intro (via Ollama + regles du profil)
# ---------------------------------------------------------------

def _charger_regles_profil(profil_id):
    """Charge les regles de redaction du profil actif (pour le ton de l'intro)."""
    try:
        from core.profiles.profile_manager import get_manager
        profil = get_manager().charger(profil_id)
        if profil and isinstance(profil, dict):
            regles = profil.get("regles_redaction") or profil.get("regles") or []
            return "\n".join(f"- {r}" if isinstance(r, str) else str(r) for r in regles[:15])
    except Exception:
        try:
            from core.profiles.profile_manager import get_manager
            profil = get_manager().charger_profil_actif()
            if profil and isinstance(profil, dict):
                regles = profil.get("regles_redaction") or profil.get("regles") or []
                return "\n".join(f"- {r}" if isinstance(r, str) else str(r) for r in regles[:15])
        except Exception as e:
            log(f"Regles profil indisponibles: {e}")
    return ""


def sauvegarder_texte_intro(projet_nom, texte):
    """
    Sauvegarde le texte d'intro attendu pour un projet (genere par le pipeline).
    L'UI le retrouve ensuite pour pre-remplir le casier modifiable.

    Returns:
        bool: True si sauvegarde reussie
    """
    try:
        if not projet_nom or not texte:
            return False
        dossier = _dossier_enregistrement(projet_nom)
        (dossier / "texte_attendu.txt").write_text(texte, encoding="utf-8")
        return True
    except Exception as e:
        log(f"Erreur sauvegarde texte attendu: {e}")
        return False


def get_texte_attendu(projet_nom=""):
    """Recupere le texte d'intro deja genere par le pipeline pour un projet."""
    if not projet_nom:
        return ""
    dossier = HUMAN_TOUCH_DIR / "projets" / projet_nom
    f = dossier / "texte_attendu.txt"
    if f.exists():
        try:
            return f.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def generer_intro(sujet, profil_id="prayer", duree_secondes=None, projet_nom=None):
    """
    Genere un texte d'intro court a lire a voix haute.

    Si un texte a deja ete genere par le pipeline pour ce projet
    (texte_attendu.txt), il est renvoye tel quel (pre-remplissage du casier).

    Returns:
        dict: {"ok": bool, "texte": str, "modele": str, "erreur": str}
    """
    # Texte deja genere par le pipeline pour ce projet -> pas de re-generation
    texte_attendu = get_texte_attendu(projet_nom)
    if texte_attendu:
        return {
            "ok": True,
            "texte": texte_attendu,
            "modele": "pipeline",
            "duree_secondes": duree_secondes or get_parametres()["duree_intro_secondes"],
            "origine": "pipeline"
        }

    if duree_secondes is None:
        duree_secondes = get_parametres()["duree_intro_secondes"]

    nb_mots = max(25, min(80, int(duree_secondes * 2.2)))

    regles = _charger_regles_profil(profil_id)
    prompt = f"""
Tu es un assistant qui ecrit des INTRODUCTIONS ORALES courtes pour des videos YouTube.
C'est la voix reelle du createur qui va lire ce texte. Il doit etre naturel, chaleureux,
authentique et parler directement au spectateur ("vous", "tu" selon le ton).

Le sujet de la video : "{sujet}"

Regles d'ecriture du profil (a respecter) :
{regles or "Ton doux et spirituel."}

Contraintes :
- Environ {nb_mots} mots ({duree_secondes} secondes de lecture a voix haute).
- Niveau : oral, facile a lire, phrases courtes.
- Accroche forte dans la premiere phrase.
- Se termine en annoncant le contenu de la video.
- PAS de titre de video, PAS de hashtags, PAS de note "intro".

Ecris uniquement le texte de l'intro, sans commentaire.
"""

    try:
        from modules.brain.generate_script import appeler_ollama
        texte, modele = appeler_ollama(prompt, modele="qwen2.5:7b", temperature=0.8)
        texte = texte.strip().strip('"')
        return {"ok": True, "texte": texte, "modele": modele, "duree_secondes": duree_secondes}
    except Exception as e:
        # Fallback : intro basique
        texte = (
            f"Bonjour et bienvenue sur la chaîne. Aujourd'hui, nous allons "
            f"{sujet[:80].lower()}. Prenez un moment de calme, et laissez-vous porter. "
            f"Commençons."
        )
        return {"ok": True, "texte": texte, "modele": "fallback", "duree_secondes": duree_secondes, "erreur_fallback": str(e)}


# ---------------------------------------------------------------
# Enregistrements
# ---------------------------------------------------------------

def _dossier_enregistrement(projet_nom=""):
    if projet_nom:
        d = HUMAN_TOUCH_DIR / "projets" / projet_nom
    else:
        d = HUMAN_TOUCH_DIR / "generiques"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sauvegarder_enregistrement(fichier_temporaire, ext="webm", projet_nom="", texte_intro=""):
    """
    Sauvegarde un enregistrement vocal uploade depuis le navigateur.

    Args:
        fichier_temporaire: chemin du fichier temporaire (UploadFile)
        ext: extension (webm, ogg, wav, mp3...)
        projet_nom: si vide, enregistrement generique (reutilisable)
        texte_intro: le texte lu (pour reference)

    Returns:
        dict: {"ok": bool, "chemin": str, "message": str}
    """
    try:
        dossier = _dossier_enregistrement(projet_nom)
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        nom = f"intro_{horodatage}.{ext}"
        chemin = dossier / nom
        with open(fichier_temporaire, "rb") as src, open(chemin, "wb") as dst:
            dst.write(src.read())

        # Sauvegarder aussi le texte lu pour reference
        if texte_intro:
            (dossier / f"intro_{horodatage}_texte.txt").write_text(texte_intro, encoding="utf-8")

        # Mettre a jour le "intro courant" (utilise par le pipeline)
        _mettre_a_jour_intro_courant(dossier, nom, texte_intro, projet_nom)

        return {
            "ok": True,
            "chemin": str(chemin),
            "message": f"Enregistrement sauvegarde ({nom})"
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}


def _mettre_a_jour_intro_courant(dossier, nom_fichier, texte_intro, projet_nom):
    """Enregistre le pointeur vers l'intro a utiliser pour ce projet."""
    if not projet_nom:
        return
    try:
        data = {
            "projet": projet_nom,
            "fichier": nom_fichier,
            "texte": texte_intro,
            "modifie_le": datetime.now().isoformat()
        }
        (dossier / "courant.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def lister_enregistrements(projet_nom=""):
    """Liste les enregistrements (generiques ou d'un projet)."""
    if projet_nom:
        d = HUMAN_TOUCH_DIR / "projets" / projet_nom
    else:
        d = HUMAN_TOUCH_DIR / "generiques"

    if not d.exists():
        return []

    ext_audio = {".webm", ".ogg", ".wav", ".mp3", ".m4a", ".opus"}
    resultats = []
    for f in sorted(d.glob("intro_*"), reverse=True):
        if f.suffix.lower() not in ext_audio:
            continue
        taille_kb = round(f.stat().st_size / 1024, 1)
        resultats.append({
            "fichier": f.name,
            "chemin": str(f),
            "taille_kb": taille_kb,
            "modifie_le": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        })
    return resultats


def get_intro_projet(projet_nom):
    """
    Recupere l'intro enregistree pour un projet (texte + audio).

    Returns:
        dict: {"ok": bool, "texte": str, "audio": str (chemin), "message": str}
    """
    dossier = HUMAN_TOUCH_DIR / "projets" / projet_nom
    courant = dossier / "courant.json"
    if courant.exists():
        try:
            data = json.loads(courant.read_text(encoding="utf-8"))
            audio_path = dossier / data.get("fichier", "")
            if audio_path.exists():
                return {
                    "ok": True,
                    "texte": data.get("texte", ""),
                    "audio": str(audio_path),
                    "fichier": data.get("fichier", "")
                }
        except Exception:
            pass

    # Fallback : dernier audio du dossier
    enr = lister_enregistrements(projet_nom)
    if enr:
        return {
            "ok": True,
            "texte": "",
            "audio": enr[0]["chemin"],
            "fichier": enr[0]["fichier"]
        }
    return {"ok": False, "texte": "", "audio": "", "message": "Aucune intro enregistree pour ce projet"}


# ---------------------------------------------------------------
# Fusion dans la video (ffmpeg)
# ---------------------------------------------------------------

def _trouver_ffmpeg():
    """Trouve l'executable ffmpeg (chemin connu ou PATH)."""
    candidats = [
        str(paths.FFMPEG),
    ]
    for c in candidats:
        if Path(c).exists():
            return c
    try:
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"
    except:
        return "ffmpeg"


def _duree_audio(ffmpeg, chemin):
    """Duree d'un fichier audio via ffmpeg (secondes)."""
    try:
        r = subprocess.run([ffmpeg, "-i", chemin], capture_output=True, text=True)
        for line in r.stderr.split("\n"):
            if "Duration" in line:
                t = line.strip().split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception:
        pass
    return 0


def _choisir_musique_fond():
    """Premier mp3/wav de la bibliotheque musique (resolue par paths.py)."""
    mp = paths.MUSIC_DIR
    if mp.exists():
        fichiers = sorted(list(mp.glob("*.mp3")) + list(mp.glob("*.wav")))
        if fichiers:
            return str(fichiers[0])
    return None


def fusionner_intro(video_path, intro_path, output_path):
    """
    Ajoute l'intro (voix reelle) en DEBUT de la video.

    La voix d'intro est traitee exactement comme les autres voix du projet :
    - volume de config (voice_volume)
    - normalisation loudnorm (meme niveau master que le pipeline video)
    - musique de fond (music_volume) mixee en dessous
    La derniere frame de la video est figee pendant la duree de l'intro.

    Returns:
        dict: {"ok": bool, "message": str}
    """
    if not Path(video_path).exists():
        return {"ok": False, "message": f"Video introuvable: {video_path}"}
    if not Path(intro_path).exists():
        return {"ok": False, "message": f"Intro introuvable: {intro_path}"}

    ffmpeg = _trouver_ffmpeg()
    intro_duree = _duree_audio(ffmpeg, intro_path)
    if intro_duree <= 0:
        return {"ok": False, "message": "Duree de l'intro illisible"}

    config = _lire_config()
    voice_vol = float(config.get("voice_volume", 1.0))
    music_vol = float(config.get("music_volume", 0.15))
    musique = _choisir_musique_fond()
    if musique:
        log(f"  Intro: musique de fond utilisee: {Path(musique).name} (vol {music_vol})")

    # Voix d'intro -> volume config + loudnorm (meme cible master que le reste)
    voix_filtre = f"[0:a]volume={voice_vol:.1f},loudnorm=I=-14:TP=-1.5:LRA=11[av]"

    if musique:
        # Intro avec musique de fond : voix traitee + musique (vol bas) -> amix
        cmd = [
            ffmpeg, "-y",
            "-i", intro_path,
            "-i", video_path,
            "-stream_loop", "-1", "-i", musique,
            "-filter_complex",
            f"[1:v]tpad=stop_mode=clone:stop_duration={intro_duree:.3f}[vout];"
            f"{voix_filtre};"
            f"[2:a]volume={music_vol:.2f}[am];"
            f"[av][am]amix=inputs=2:duration=first:dropout_transition=2,"
            f"atrim=0:{intro_duree:.3f},aresample=44100:async=1[a0];"
            f"[1:a]aresample=44100:async=1[a1];"
            f"[a0][a1]concat=n=2:v=0:a=1[aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]
    else:
        # Sans musique : voix traitee puis concat avec la video
        cmd = [
            ffmpeg, "-y",
            "-i", intro_path,
            "-i", video_path,
            "-filter_complex",
            f"[1:v]tpad=stop_mode=clone:stop_duration={intro_duree:.3f}[vout];"
            f"{voix_filtre},atrim=0:{intro_duree:.3f},aresample=44100:async=1[a0];"
            f"[1:a]aresample=44100:async=1[a1];"
            f"[a0][a1]concat=n=2:v=0:a=1[aout]",
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return {"ok": False, "message": f"Erreur ffmpeg: {result.stderr[-300:]}"}
        return {"ok": True, "message": f"Intro ajoutee et traitee (master + musique) ({intro_duree:.1f}s)"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def statut():
    """Statut complet de la touche humaine."""
    params = get_parametres()
    enr_generiques = lister_enregistrements()
    intros_projets = []
    textes_en_attente = []  # textes generes par le pipeline, audio pas encore enregistre
    d_projets = HUMAN_TOUCH_DIR / "projets"
    if d_projets.exists():
        for p in sorted(d_projets.iterdir()):
            if p.is_dir():
                c = p / "courant.json"
                info = {"projet": p.name, "audio": None}
                if c.exists():
                    try:
                        d = json.loads(c.read_text(encoding="utf-8"))
                        info["audio"] = d.get("fichier")
                        info["texte"] = d.get("texte", "")
                    except:
                        pass
                intros_projets.append(info)

                # Texte genere par le pipeline mais pas encore enregistre ?
                if not info["audio"]:
                    f_texte = p / "texte_attendu.txt"
                    if f_texte.exists():
                        try:
                            textes_en_attente.append({
                                "projet": p.name,
                                "texte": f_texte.read_text(encoding="utf-8").strip()
                            })
                        except Exception:
                            pass

    return {
        "actif": params["actif"],
        "duree_intro_secondes": params["duree_intro_secondes"],
        "mode": params.get("mode", "ia"),
        "dossier": params["dossier"],
        "enregistrements_generiques": enr_generiques,
        "intros_projets": intros_projets,
        "textes_en_attente": textes_en_attente,
        "nb_total": len(enr_generiques) + len(intros_projets)
    }


if __name__ == "__main__":
    st = statut()
    print(json.dumps(st, ensure_ascii=False, indent=2))
