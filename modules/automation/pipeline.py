# -*- coding: utf-8 -*-
"""
pipeline.py — Pipeline d'automatisation

Analyse -> Decide -> Produit -> Upload
Orchestre la creation de contenu de bout en bout.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(_rac))
    from core import paths

from modules.automation.content_planner import (
    suggerer_contenu,
    analyser_tendances_youtube,
    analyser_performances_profil
)
from modules.automation.progress import (
    init as progress_init,
    etape as progress_etape,
    terminer_etape as progress_terminer,
    attendre_humaine as progress_attente,
    reprendre as progress_reprendre,
    fin as progress_fin,
    get as progress_get,
)


def log(msg):
    print(f"[PIPELINE] {msg}")


def _lire_config():
    # Resolution via core/paths : en mode installe, la config UTILISATEUR
    # (%USERPROFILE%\StudioIA\config.json) prime sur la config embarque.
    try:
        from core import paths
        return paths.lire_config()
    except Exception:
        try:
            config_path = Path(__file__).parent.parent.parent / "config.json"
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


class PipelineAutomation:
    """
    Pipeline complet de creation de contenu automatisee.

    Utilisation:
        pipeline = PipelineAutomation(profil_id="prayer")
        resultat = pipeline.executer()
    """

    def __init__(self, profil_id="prayer", mode_silencieux=False, directives=None):
        self.profil_id = profil_id
        self.mode_silencieux = mode_silencieux
        self.directives = directives
        self.config = _lire_config()
        self.resultat = {
            "timestamp": datetime.now().isoformat(),
            "profil": profil_id,
            "phases": {},
            "succes": False,
            "erreur": None,
            "suggestion": None,
            "projet_creer": None
        }

    def phase_analyse(self):
        """Phase 1: Analyser l'etat du systeme et les opportunites"""
        log("Phase 1: Analyse...")
        progress_etape("analyse", "Analyse du systeme (diagnostic, tendances, performances)...", 5)

        # Diagnostic systeme
        try:
            from modules.diagnostic import executer_diagnostic
            diagnostic = executer_diagnostic(silent=True)
            self.resultat["phases"]["diagnostic"] = {
                "score": diagnostic.get("score_pct", 0),
                "services": {k: v.get("ok", False) if isinstance(v, dict) else False
                            for k, v in diagnostic.get("etapes", {}).items()
                            if isinstance(v, dict) and "ok" in v}
            }
        except Exception as e:
            self.resultat["phases"]["diagnostic"] = {"erreur": str(e)}

        # Performances du profil
        try:
            perf = analyser_performances_profil(self.profil_id)
            self.resultat["phases"]["performances"] = perf
        except Exception as e:
            self.resultat["phases"]["performances"] = {"erreur": str(e)}

        # Tendances YouTube
        try:
            tendances = analyser_tendances_youtube()
            if tendances:
                self.resultat["phases"]["tendances"] = {
                    "ok": True,
                    "videos_populaires": [
                        {"titre": v.get("titre", "?"), "vues": v.get("vues", 0)}
                        for v in (tendances.get("videos", [])[:5])
                    ]
                }
            else:
                self.resultat["phases"]["tendances"] = {
                    "ok": False,
                    "raison": "YouTube API non configure"
                }
        except Exception as e:
            self.resultat["phases"]["tendances"] = {"ok": False, "erreur": str(e)}

        progress_terminer("analyse", "termine", "Analyse terminee")
        log(f"  Analyse terminee. Score: {self.resultat['phases'].get('diagnostic', {}).get('score', '?')}%")
        return self

    def phase_decision(self):
        """Phase 2: Decider quoi produire"""
        log("Phase 2: Decision...")
        progress_etape("decision", "Decision du contenu a produire...", 15)

        tendances = self.resultat.get("phases", {}).get("tendances", {})
        suggestion = suggerer_contenu(
            profil_id=self.profil_id,
            tendances=tendances if tendances.get("ok") else None
        )

        self.resultat["suggestion"] = suggestion
        self.resultat["phases"]["decision"] = {
            "sujet": suggestion.get("titre", ""),
            "type": suggestion.get("type", "generic"),
            "raison": suggestion.get("raison", "")
        }

        progress_terminer("decision", "termine", "Contenu decide")
        log(f"  Contenu suggere: {suggestion.get('titre', '?')[:60]}")
        return self

    def phase_production(self, force_generer=False):
        """
        Phase 3: Produire le contenu

        Args:
            force_generer: Si True, lance la generation meme sans confirmation
        """
        log("Phase 3: Production...")

        if not force_generer:
            log("  Mode preview — aucune generation lancee")
            self.resultat["phases"]["production"] = {
                "statut": "preview",
                "message": "Mode preview. Passe force_generer=True pour lancer la production."
            }
            return self

        suggestion = self.resultat.get("suggestion", {})
        if not suggestion:
            self.resultat["phases"]["production"] = {
                "statut": "erreur",
                "message": "Aucune suggestion disponible. Lance d'abord la phase decision."
            }
            return self

        # Directives de l'utilisateur (citer, interdire, commentateurs) injectees
        # dans la suggestion -> portees par _creer_projet dans project.json
        if self.directives:
            suggestion["directives"] = self.directives

        # Creer le projet
        progress_etape("production", "Creation du projet...", 20)
        projet_nom = self._creer_projet(suggestion)
        self.resultat["projet_creer"] = projet_nom

        if not projet_nom:
            self.resultat["phases"]["production"] = {
                "statut": "erreur",
                "message": "Impossible de creer le projet"
            }
            return self

        # Touche humaine : generer le texte d'intro a lire (option activee dans config)
        #
        # Deux modes :
        #   "ia"   (defaut) : l'IA ecrit un texte d'intro que l'utilisateur lit au micro.
        #   "libre"         : PAS de texte genere — l'utilisateur improvise librement.
        #                    La video commence directement par la priere (aucune intro
        #                    IA), seule une voix enregistree librement est fusionnee.
        try:
            from modules.human_touch.intro_voice import generer_intro, sauvegarder_texte_intro
            ht = self.config.get("human_touch", {})
            mode_intro = ht.get("mode", "ia")
            if ht.get("actif", False):
                sujet = suggestion.get("description", suggestion.get("titre", ""))

                if mode_intro == "libre":
                    # MODE LIBRE : aucun texte d'intro genere par l'IA.
                    # On attend simplement que l'utilisateur enregistre sa voix librement
                    # (ou pas : la video peut commencer directement par la priere).
                    self.resultat["intro"] = {
                        "statut": "libre",
                        "projet": projet_nom,
                        "texte": "",
                        "message": "Mode libre : aucune intro IA. Enregistre librement ta voix dans la page "
                                   "/human-touch, sinon la video commence directement par la priere."
                    }
                    log(f"  Intro en mode LIBRE pour {projet_nom} — pas de texte genere, attente enregistrement libre")
                    progress_attente(
                        "Mode libre : enregistre librement ta voix (ou laisse passer), la video commence directement.",
                        28
                    )
                    self._attendre_enregistrement_intro(
                        projet_nom,
                        timeout=int(ht.get("attente_max_minutes", 60)) * 60
                    )
                    progress_reprendre("Fin d'attente — poursuite automatique du pipeline.", 32)
                    self.resultat["intro"]["statut"] = "libre_enregistre"
                    self.resultat["intro"]["message"] = ("Intro libre enregistree et integree (sinon la video "
                                                         "commence directement par la priere).")
                    log(f"  Attente intro libre terminee pour {projet_nom} — poursuite automatique")
                else:
                    intro = generer_intro(
                        sujet=sujet,
                        profil_id=self.profil_id,
                        duree_secondes=ht.get("duree_intro_secondes", 30),
                        projet_nom=projet_nom
                    )
                    if intro.get("ok"):
                        texte = intro.get("texte", "")
                        # Copie dans le projet (reference) + pour l'UI (pre-remplissage)
                        try:
                            projet_dir = paths.PROJECTS_DIR / projet_nom
                            (projet_dir / "intro_texte.txt").write_text(texte, encoding="utf-8")
                        except Exception as e:
                            log(f"  Intro: ecriture texte projet impossible: {e}")
                        sauvegarder_texte_intro(projet_nom, texte)
                        self.resultat["intro"] = {
                            "statut": "en_attente_enregistrement",
                            "projet": projet_nom,
                            "texte": texte,
                            "message": "Enregistre ta voix dans la page /human-touch pour l'ajouter en debut de video."
                        }
                        log(f"  Intro generee pour {projet_nom} — en attente de ton enregistrement (page /human-touch)")

                        # PAUSE TOUCHE HUMAINE : le pipeline s'arrete ici et attend
                        # que l'utilisateur enregistre sa voix (ou colle son propre texte).
                        # Des que l'enregistrement est detecte, il reprend automatiquement.
                        progress_attente(
                            "Enregistre ta voix dans la page /human-touch, puis c'est automatique.",
                            28
                        )
                        self._attendre_enregistrement_intro(
                            projet_nom,
                            timeout=int(ht.get("attente_max_minutes", 60)) * 60
                        )
                        progress_reprendre("Intro enregistree — poursuite automatique du pipeline.", 32)
                        self.resultat["intro"]["statut"] = "enregistre"
                        self.resultat["intro"]["message"] = "Intro enregistree et integree automatiquement."
                        log(f"  Intro enregistree pour {projet_nom} — poursuite automatique")
                    else:
                        self.resultat["intro"] = {"statut": "erreur", "erreur": intro.get("message", "?")}
        except Exception as e:
            log(f"  Erreur generation intro: {e}")

        # Generer le script
        try:
            log(f"  Generation du script pour {projet_nom}...")
            progress_etape("script", "Generation du script (plan + chapitres)...", 30)

            # Utiliser generate_script.main() qui lit le project.json
            projet_path = str(paths.PROJECTS_DIR / projet_nom)

            from modules.brain.generate_script import main as generate_main
            # Sauvegarder et restaurer sys.argv
            import sys as _sys
            old_argv = _sys.argv
            _sys.argv = ["generate_script.py", projet_path]
            try:
                generate_main()
            finally:
                _sys.argv = old_argv

            # Filtrer avec filter_text.main()
            from modules.brain.filter_text import main as filter_main
            _sys.argv = ["filter_text.py", projet_path]
            try:
                filter_main()
            finally:
                _sys.argv = old_argv

            log(f"  Script genere pour: {projet_nom}")
        except Exception as e:
            log(f"  Erreur generation script: {e}")
            import traceback
            traceback.print_exc()

        self.resultat["phases"]["production"] = {
            "statut": "termine",
            "projet": projet_nom
        }
        progress_terminer("production", "termine", f"Production terminee — projet {projet_nom}")

        return self

    def phase_video(self, projet_nom):
        """
        Phase 3.5 : Genere le contenu video du projet
        (audio TTS -> musique de fond -> images -> montage video -> vignette).

        Meme sequence que le GUI PowerShell (app_gui._run_pipeline),
        appelee de facon NON interactive. Chaque sous-etape est
        tolerante aux erreurs (log + continue) pour que le pipeline
        aille au bout.
        """
        import shutil
        import sys as _sys

        log(f"Phase Video: {projet_nom}")
        projet_path = paths.PROJECTS_DIR / projet_nom
        pjson = projet_path / "project.json"

        try:
            data = json.loads(pjson.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"  Impossible de lire project.json: {e}")
            data = {}

        # --- 1. Audio TTS ---
        progress_etape("audio", "Generation audio TTS (chapitres)...", 40)
        try:
            from modules.tts.run_tts import main as tts_main
            voix = str(self.config.get("tts_voix", "3"))
            old_argv = _sys.argv
            _sys.argv = ["run_tts.py", str(projet_path), voix]
            try:
                tts_main()
            finally:
                _sys.argv = old_argv
            audio_ok = (projet_path / "audio").exists() and len(list((projet_path / "audio").glob("*.wav"))) > 0
            log(f"  Audio: {'OK' if audio_ok else 'aucun wav genere'}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            log(f"  Erreur generation audio: {e}")
            audio_ok = False

        if not audio_ok:
            self.resultat["phases"]["video"] = {
                "statut": "erreur",
                "message": f"Audio TTS echoue — video non generee ({projet_nom})"
            }
            log("  Audio TTS echoue — abandon de la phase video")
            return self

        # --- 2. Musique de fond (fallback deteministe) ---
        progress_etape("musique_fond", "Musique de fond...", 55)
        musique_copier = None
        try:
            music_dir = paths.MUSIC_DIR
            if music_dir.exists():
                candidats = sorted(list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav")))
                if candidats:
                    musique_copier = candidats[0]
        except Exception as e:
            log(f"  Musique: recherche impossible: {e}")
        if musique_copier:
            try:
                audio_dir = projet_path / "audio"
                audio_dir.mkdir(exist_ok=True)
                dest = audio_dir / "musique_fond.mp3"
                shutil.copy(str(musique_copier), str(dest))
                log(f"  Musique copiee: {Path(musique_copier).name} -> {dest.name}")
            except Exception as e:
                log(f"  Musique: copie impossible: {e}")
        progress_terminer("musique_fond", "termine", "Musique de fond prete")

        # --- 3. Images (library_manager, puis fallback local) ---
        progress_etape("images", "Telechargement images...", 60)
        try:
            from modules.images.library_manager import main as img_main
            old_argv = _sys.argv
            _sys.argv = ["library_manager.py", str(projet_path)]
            try:
                img_main()
            finally:
                _sys.argv = old_argv
        except Exception as e:
            log(f"  Images: library_manager erreur: {e}")

        # Verifier que des fonds existent ; sinon fallback assets/backgrounds
        images_ok = False
        try:
            data = json.loads(pjson.read_text(encoding="utf-8"))
            images_ok = bool(data.get("images_data", {}).get("backgrounds"))
        except Exception:
            pass

        if not images_ok:
            log("  Images: fallback vers assets/backgrounds")
            try:
                bg_src = Path(__file__).parent.parent.parent / "assets" / "backgrounds"
                bg_dest = projet_path / "images" / "backgrounds"
                bg_dest.mkdir(parents=True, exist_ok=True)
                fonds = sorted(list(bg_src.glob("*.jpg")) + list(bg_src.glob("*.png")))[:5]
                bgs = []
                for i, f in enumerate(fonds, 1):
                    nom = f"bg_fallback_{i:02d}.jpg"
                    shutil.copy(str(f), str(bg_dest / nom))
                    bgs.append({"fichier": f"images/backgrounds/{nom}", "mot_cle": "fallback", "nom": nom})
                if bgs:
                    data["images_data"] = {"backgrounds": bgs, "overlays": []}
                    pjson.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    images_ok = True
                    log(f"  Images fallback: {len(bgs)} fonds copies")
            except Exception as e:
                log(f"  Images fallback erreur: {e}")
        else:
            log(f"  Images: {len(data.get('images_data', {}).get('backgrounds', []))} fonds OK")

        if not images_ok:
            log("  Aucune image — on continue (build_video ignorera les segments sans fond)")

        # --- 4. Montage video ---
        progress_etape("video", "Montage video (lent ~7 min)...", 75)
        try:
            from modules.video.build_video import main as bv_main
            old_argv = _sys.argv
            # argv: style=7 (aleatoire), particules=5 (aleatoire), kenburns=8 (aleatoire), logo=""
            _sys.argv = ["build_video.py", str(projet_path), "7", "5", "8", ""]
            try:
                bv_main()
            finally:
                _sys.argv = old_argv
        except Exception as e:
            import traceback
            traceback.print_exc()
            log(f"  Erreur montage video: {e}")

        # --- 5. Vignette ---
        progress_etape("thumbnail", "Generation vignette...", 90)
        try:
            from modules.thumbnail.thumbnail_builder import main as th_main
            old_argv = _sys.argv
            _sys.argv = ["thumbnail_builder.py", str(projet_path), "6"]
            try:
                th_main()
            finally:
                _sys.argv = old_argv
        except Exception as e:
            log(f"  Erreur vignette: {e}")

        # --- Resultat ---
        try:
            data = json.loads(pjson.read_text(encoding="utf-8"))
            fichier_final = data.get("fichier_final", "")
            video_path = projet_path / fichier_final if fichier_final else None
            if not video_path or not video_path.exists():
                # fallback: chercher export/video/*.mp4
                candidats = sorted((projet_path / "export" / "video").glob("*.mp4")) if (projet_path / "export" / "video").exists() else []
                if candidats:
                    video_path = candidats[-1]
            self.resultat["fichier_video"] = str(video_path) if (video_path and video_path.exists()) else None
            # Vignette (thumbnail)
            vignettes = sorted((projet_path / "thumbnail").glob("*.png")) if (projet_path / "thumbnail").exists() else []
            self.resultat["fichier_thumbnail"] = str(vignettes[-1]) if vignettes else None
            self.resultat["phases"]["video"] = {
                "statut": "termine" if self.resultat.get("fichier_video") else "echec",
                "fichier": self.resultat.get("fichier_video")
            }
            if self.resultat.get("fichier_video"):
                log(f"  VIDEO OK: {self.resultat['fichier_video']}")
            else:
                log("  VIDEO ABSENTE — verifie build_video")
        except Exception as e:
            log(f"  Erreur lecture resultat video: {e}")

        progress_terminer("video", "termine" if self.resultat.get("fichier_video") else "echec",
                          "Video generee" if self.resultat.get("fichier_video") else "Echec video")

        return self

    def _attendre_enregistrement_intro(self, projet_nom, timeout=3600, intervalle=4):
        """
        Boucle d'attente : le pipeline reste bloque tant que l'utilisateur
        n'a pas enregistre sa voix pour ce projet. Quand l'audio est detecte,
        on retourne et le pipeline continue tout seul.

        Args:
            projet_nom: nom du projet
            timeout: duree maximale d'attente en secondes (defaut 60 min)
            intervalle: periode de poll en secondes

        Returns:
            dict: {"ok": bool, "audio": str} — audio = chemin du fichier enregistre
        """
        import time as _time
        debut = _time.time()

        # Si l'intro est deja enregistree (trop rapide), ne pas attendre
        try:
            from modules.human_touch.intro_voice import get_intro_projet
            intro = get_intro_projet(projet_nom)
            if intro.get("ok"):
                return {"ok": True, "audio": intro.get("audio", "")}
        except Exception:
            pass

        while _time.time() - debut < timeout:
            _time.sleep(intervalle)
            try:
                from modules.human_touch.intro_voice import get_intro_projet
                intro = get_intro_projet(projet_nom)
                if intro.get("ok"):
                    return {"ok": True, "audio": intro.get("audio", "")}
            except Exception as e:
                log(f"  Attente intro: erreur poll: {e}")

        log("  Attente intro: delai maximum depasse — on continue sans intro")
        return {"ok": False, "audio": ""}

    def _verifier_intro_enregistree(self, projet_nom):
        """
        Verifie si l'utilisateur a enregistre sa voix pour ce projet.
        Met a jour l'etape "intro" dans project.json.

        Returns:
            dict: {"ok": bool, "audio": str}
        """
        if not projet_nom:
            return {"ok": False, "audio": ""}
        projet_path = paths.PROJECTS_DIR / projet_nom
        pjson = projet_path / "project.json"
        try:
            from modules.human_touch.intro_voice import get_intro_projet
            intro = get_intro_projet(projet_nom)
            if intro.get("ok"):
                with open(pjson, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("etapes", {}).get("intro") == "en_attente":
                    data["etapes"]["intro"] = "termine"
                    with open(pjson, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    log(f"  Intro enregistree pour {projet_nom} — etape 'intro' terminee")
                return {"ok": True, "audio": intro.get("audio", "")}
        except Exception as e:
            log(f"  Erreur verification intro: {e}")
        return {"ok": False, "audio": ""}

    def phase_upload(self):
        """Phase 4: Uploader vers YouTube (si OAuth configure et video produite)"""
        log("Phase 4: Upload...")
        progress_etape("upload", "Upload vers YouTube...", 95)

        # Touche humaine : verifier si l'intro a ete enregistree (met a jour l'etape)
        projet_nom = self.resultat.get("projet_creer")
        self._verifier_intro_enregistree(projet_nom)

        # L'upload necessite OAuth 2.0 (token), pas seulement la cle API
        try:
            from modules.youtube_analyzer.youtube_upload import token_exists, statut_auth, upload_video
            oauth_ok = token_exists()
            if not oauth_ok:
                st = statut_auth()
                self.resultat["phases"]["upload"] = {
                    "statut": "non_disponible",
                    "message": f"OAuth non configure. {st.get('message', 'Lance auth_flow()')}"
                }
                log("  OAuth non configure — upload ignore (lance auth_flow() une fois)")
                return self
        except Exception as e:
            self.resultat["phases"]["upload"] = {
                "statut": "erreur",
                "message": f"Erreur verification OAuth: {e}"
            }
            log(f"  Erreur verification OAuth: {e}")
            return self

        # Chercher un fichier video dans le projet genere
        # Ordre de recherche (fiabilite decroissante) :
        #   1. data["fichier_final"] ecrit par build_video (le plus fiable)
        #   2. export/**/*.mp4 (la ou build_video ecrit reellement)
        #   3. *.mp4 / *.mkv en racine projet (fallback)
        projet_nom = self.resultat.get("projet_creer")
        chemin_video = None
        if projet_nom:
            projet_path = paths.PROJECTS_DIR / projet_nom
            try:
                data = json.loads((projet_path / "project.json").read_text(encoding="utf-8"))
            except Exception:
                data = {}
            fichier_final = data.get("fichier_final") or ""
            if fichier_final:
                p = projet_path / fichier_final
                if p.exists():
                    chemin_video = str(p)

            if not chemin_video:
                for ext in ("*.mp4", "*.mkv", "*.mov", "*.webm"):
                    candidats = sorted(projet_path.glob("export/**/" + ext))
                    if candidats:
                        chemin_video = str(candidats[-1])
                        break
            if not chemin_video:
                for ext in ("*.mp4", "*.mkv", "*.mov", "*.webm"):
                    candidats = list(projet_path.glob(ext))
                    if candidats:
                        chemin_video = str(candidats[0])
                        break

        if not chemin_video:
            self.resultat["phases"]["upload"] = {
                "statut": "pas_de_video",
                "message": "OAuth OK mais aucune video produite. Genere d'abord la video (etape video)."
            }
            log("  OAuth OK mais aucune video a uploader")
            return self

        # Uploader
        try:
            suggestion = self.resultat.get("suggestion", {})
            titre = suggestion.get("titre", projet_nom)
            description = suggestion.get("description", "Genere par StudioIA-Next")
            tags = suggestion.get("mots_cles", [])
            resultat = upload_video(
                chemin_video=chemin_video,
                titre=titre,
                description=description,
                tags=tags,
                privacy_status="private"
            )
            self.resultat["phases"]["upload"] = {
                "statut": "termine" if resultat.get("ok") else "erreur",
                "video_id": resultat.get("video_id"),
                "message": resultat.get("message", "Upload termine")
            }
            log(f"  Upload: {resultat.get('video_id', resultat.get('message', '?'))}")
        except Exception as e:
            self.resultat["phases"]["upload"] = {
                "statut": "erreur",
                "message": f"Erreur upload: {e}"
            }
            log(f"  Erreur upload: {e}")

        return self

    def _creer_projet(self, suggestion):
        """Cree un projet dans projects/ a partir d'une suggestion"""
        import re

        projects_path = paths.PROJECTS_DIR

        # Generer un nom de dossier
        titre = suggestion.get("titre", "contenu_automatique")
        nom_dossier = titre.lower()
        nom_dossier = re.sub(r'[^a-z0-9]+', '_', nom_dossier)[:40]
        nom_dossier = nom_dossier.strip('_')

        if not nom_dossier:
            nom_dossier = f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        projet_path = projects_path / nom_dossier
        if projet_path.exists():
            nom_dossier = f"{nom_dossier}_{datetime.now().strftime('%H%M%S')}"
            projet_path = projects_path / nom_dossier

        projet_path.mkdir(parents=True, exist_ok=True)
        # Sous-dossiers attendus par generate_script / build_video
        (projet_path / "chapters").mkdir(exist_ok=True)
        (projet_path / "audio").mkdir(exist_ok=True)
        (projet_path / "images").mkdir(exist_ok=True)
        (projet_path / "export").mkdir(exist_ok=True)

        # Creer project.json
        duree = suggestion.get("duree_recommandee_minutes") or self._estimer_duree()
        etapes = {
            "script": "en_attente",
            "chapitres": "en_attente",
            "audio": "en_attente",
            "musique_fond": "en_attente",
            "images": "en_attente",
            "video": "en_attente",
            "thumbnail": "en_attente",
            "upload": "en_attente"
        }

        # Touche humaine activee -> ajouter une etape "intro" :
        # le pipeline genere d'abord le texte, attend l'enregistrement de la voix,
        # puis la video sera construite avec l'intro fusionnee en debut.
        human_touch = self.config.get("human_touch", {})
        if human_touch.get("actif", False):
            etapes = {
                "intro": "en_attente",
                **etapes
            }

        project_data = {
            "id": nom_dossier,
            "sujet": suggestion.get("description", suggestion.get("titre", "")),
            "type_contenu": suggestion.get("type", "generic"),
            "langue": "fr",
            "duree_cible_minutes": duree,
            "directives": suggestion.get("directives"),
            "meta": {
                "profil": self.profil_id,
                "genere_le": datetime.now().isoformat(),
                "automatique": True,
                "duree_cible": duree,
                "mots_cles": suggestion.get("mots_cles", []),
                "touche_humaine": bool(human_touch.get("actif", False))
            },
            "etapes": etapes
        }

        with open(projet_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

        return nom_dossier

    def _estimer_duree(self):
        """Estime la duree du contenu basee sur les performances passees"""
        try:
            perf = self.resultat.get("phases", {}).get("performances", {})
            duree_moy = perf.get("duree_moyenne", 0)
            if duree_moy > 0:
                return int(duree_moy)
        except:
            pass
        return 10  # 10 minutes par defaut

    def executer(self, force_generer=False):
        """
        Execute le pipeline complet.

        Args:
            force_generer: Si True, lance la generation du contenu
                          (pas seulement l'analyse et la decision)

        Returns:
            dict: Resultat complet du pipeline
        """
        log("=== PIPELINE AUTOMATIQUE ===")
        log(f"Profil: {self.profil_id}")
        progress_init()

        try:
            self.phase_analyse()
            self.phase_decision()
            self.phase_production(force_generer=force_generer)
            if force_generer and self.resultat.get("projet_creer"):
                self.phase_video(self.resultat["projet_creer"])
            self.phase_upload()
            progress_etape("fini", "Pipeline termine avec succes", 100)

            self.resultat["succes"] = True
            log("=== PIPELINE TERMINE ===")
        except Exception as e:
            self.resultat["succes"] = False
            self.resultat["erreur"] = str(e)
            log(f"ERREUR: {e}")

        progress_fin(erreur=self.resultat.get("erreur"), resultat=self.resultat)
        return self.resultat


def executer_pipeline(profil_id="prayer", force_generer=False, directives=None):
    """
    Fonction de convenience pour lancer le pipeline.

    Args:
        profil_id: Profil a utiliser
        force_generer: Lancer la production ou seulement analyser/decider
        directives: Consignes libres de l'utilisateur (citer, interdire,
                    commentateurs...) portees dans project.json puis respectees
                    par le generateur de texte.

    Returns:
        dict: Resultat du pipeline
    """
    pipeline = PipelineAutomation(profil_id=profil_id, directives=directives)
    return pipeline.executer(force_generer=force_generer)


if __name__ == "__main__":
    import json
    resultat = executer_pipeline(force_generer=False)
    print(json.dumps(resultat, ensure_ascii=False, indent=2))
