#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
StudioIA - Interface Graphique Moderne
Interface moderne avec CustomTkinter pour ordinateurs faibles

AMÉLIORATIONS POUR MATERIEL FAIBLE:
- Mode "Low Resource" par défaut (CRF 28, sans zoompan)
- Limite les threads IA à 2
- Réduit la résolution par défaut
- Nettoyage mémoire automatique après chaque étape
"""

import customtkinter as ctk
import json
import os
import sys
import subprocess
import threading
import gc
from pathlib import Path
from datetime import datetime

# Import for thumbnail standalone
from modules.thumbnail.thumbnail_standalone_gui import ThumbnailGeneratorGUI

# Fix for messagebox (CustomTkinter doesn't have it built-in)
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# Configuration CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Paths
CONFIG_PATH = "C:\\StudioIA-Next\\config.json"
PROJECTS_PATH = "C:\\StudioIA-Next\\projects"
ASSETS_PATH = "C:\\StudioIA\\assets"
LOGS_PATH = "C:\\StudioIA\\logs"

# Import modules
sys.path.insert(0, "C:\\StudioIA\\modules")

class StudioIAApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("StudioIA - Automatisation YouTube")
        self.geometry("1100x800")
        self.minsize(900, 600)

        # Configuration
        self.config = self.load_config()
        self.low_resource_mode = self.config.get("low_resource", True)

        # Variables
        self.project_path = None
        self.log_text = []
        self.current_project = None

        # Setup UI
        self.setup_ui()

    def load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {
                "ia_model": "qwen2",
                "tts_engine": "xtts",
                "video_resolution": "1920x1080",
                "language": "fr",
                "projects_path": PROJECTS_PATH,
                "mode": "local",
                "low_resource": True
            }

    def save_config(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        self.header = ctk.CTkFrame(self, height=70, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.header,
            text="StudioIA",
            font=("Segoe UI", 24, "bold"),
            text_color="#3b82f6"
        ).grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # Mode indicator
        mode_color = "#ef4444" if self.low_resource_mode else "#10b981"
        mode_text = "LOW RESOURCE" if self.low_resource_mode else "NORMAL"
        ctk.CTkLabel(
            self.header,
            text=f"Mode: {mode_text}",
            font=("Segoe UI", 11, "bold"),
            text_color=mode_color
        ).grid(row=0, column=1, padx=20, pady=15, sticky="e")

        # Toggle low resource button
        ctk.CTkButton(
            self.header,
            text="Basculer mode faible",
            command=self.toggle_low_resource,
            height=30,
            font=("Segoe UI", 10),
            fg_color="#374151"
        ).grid(row=0, column=2, padx=20, pady=10)

        # Status bar
        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew")

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="Prêt",
            font=("Segoe UI", 10),
            text_color="#9ca3af"
        )
        self.status_label.grid(row=0, column=0, padx=10, sticky="w")

        self.mem_label = ctk.CTkLabel(
            self.status_bar,
            text="Mémoire: -- MB",
            font=("Segoe UI", 10),
            text_color="#6b7280"
        )
        self.mem_label.grid(row=0, column=1, padx=20, sticky="w")

        # Content area
        self.content = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

        self.show_main_menu()
        self.update_mem_info()

    def toggle_low_resource(self):
        self.low_resource_mode = not self.low_resource_mode
        self.config["low_resource"] = self.low_resource_mode
        self.save_config()

        mode_color = "#ef4444" if self.low_resource_mode else "#10b981"
        mode_text = "LOW RESOURCE" if self.low_resource_mode else "NORMAL"
        self.header.winfo_children()[2].configure(
            text=f"Mode: {mode_text}",
            text_color=mode_color
        )
        self.log(f"Mode basculé: {'FAIBLE' if self.low_resource_mode else 'NORMAL'}")

    def update_mem_info(self):
        try:
            import psutil
            mem = psutil.virtual_memory()
            available = mem.available / (1024 * 1024)
            total = mem.total / (1024 * 1024)
            self.mem_label.configure(
                text=f"Mémoire: {available:.0f}/{total:.0f} MB"
            )
            # Auto nettoyage si mémoire faible
            if available < 500:  # Moins de 500MB disponibles
                self.log("Mémoire faible - Nettoyage automatique...")
                gc.collect()
        except:
            pass
        self.after(5000, self.update_mem_info)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        self.status_label.configure(text=message)
        self.update_idletasks()

    def show_main_menu(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        # Stats card
        stats_frame = ctk.CTkFrame(self.content, corner_radius=10, fg_color="#1f2937")
        stats_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        projets = list(Path(PROJECTS_PATH).glob("*")) if Path(PROJECTS_PATH).exists() else []
        projets_termines = sum(1 for p in projets if list((Path(p) / "export").rglob("*_final.mp4")) or list((Path(p) / "export" / "shorts").glob("*.mp4")))
        projets_encours = len(projets) - projets_termines

        stats_text = f"Total projets: {len(projets)} | Terminés: {projets_termines} | En cours: {projets_encours}"
        ctk.CTkLabel(
            stats_frame,
            text=stats_text,
            font=("Segoe UI", 12)
        ).pack(pady=15)

        # Buttons grid
        btn_frame = ctk.CTkFrame(self.content, corner_radius=10)
        btn_frame.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        buttons = [
            ("Nouveau projet vidéo", "#3b82f6", self.create_new_project),
            ("Continuer un projet", "#3b82f6", self.continue_project),
            ("Paramètres système", "#10b981", self.show_settings),
            ("Gestionnaire assets", "#8b5cf6", self.show_assets_manager),
            ("Shorts Generator", "#f59e0b", self.show_shorts_generator),
            ("Thumbnail standalone", "#ec4899", self.show_thumbnail_standalone),
            ("Cloner voix", "#9d174d", self.show_voice_cloner),
            ("Monitor projet", "#6366f1", self.show_project_monitor),
            ("Corrections & Apprentissage", "#f97316", self.show_corrections),
        ]

        for i, (text, color, callback) in enumerate(buttons):
            btn = ctk.CTkButton(
                btn_frame,
                text=text,
                command=callback,
                height=70,
                font=("Segoe UI", 12, "bold"),
                corner_radius=8,
                fg_color=color,
                hover_color=color.replace("5", "6") if color.endswith("5") else color
            )
            btn.grid(row=i//2, column=i%2, padx=10, pady=10, sticky="nsew")

        # Quit button
        ctk.CTkButton(
            self.content,
            text="Quitter StudioIA",
            command=self.quit,
            fg_color="#ef4444",
            hover_color="#dc2626",
            height=45,
            font=("Segoe UI", 12, "bold")
        ).grid(row=2, column=0, padx=20, pady=20, sticky="e")

    # ============================================================
    # CREATE NEW PROJECT
    # ============================================================

    def create_new_project(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        # Sujet
        ctk.CTkLabel(frame, text="Sujet de la vidéo", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, padx=15, pady=(20, 5), sticky="w"
        )
        sujet_entry = ctk.CTkEntry(frame, placeholder_text="Ex: La puissance de la prière quotidienne", width=500)
        sujet_entry.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        # Type
        ctk.CTkLabel(frame, text="Type de contenu", font=("Segoe UI", 14, "bold")).grid(
            row=2, column=0, padx=15, pady=(20, 5), sticky="w"
        )
        type_var = ctk.StringVar(value="1")

        type_frame = ctk.CTkFrame(frame)
        type_frame.grid(row=3, column=0, padx=15, pady=5, sticky="w")

        types = [
            ("Prière chrétienne (FR)", "1"),
            ("Storytelling (FR)", "2"),
            ("Storytelling (EN)", "3"),
            ("Autre contenu (FR)", "4"),
            ("Autre contenu (EN)", "5"),
        ]

        for i, (text, value) in enumerate(types):
            ctk.CTkRadioButton(type_frame, text=text, variable=type_var, value=value).grid(
                row=0, column=i, padx=5, pady=5
            )

        # Profile info
        profil_info = ""
        try:
            from core.profiles.profile_manager import ProfileManager
            pm = ProfileManager()
            p = pm.charger_profil_actif()
            if p:
                m = p.get("manifest", {})
                profil_info = f"Profil actif: {m.get('name', '?')} — {m.get('description', '')[:60]}"
        except:
            profil_info = "Profil actif: prayer"
        ctk.CTkLabel(frame, text=profil_info, font=("Segoe UI", 10), text_color="#9ca3af").grid(
            row=4, column=0, padx=15, pady=(0, 10), sticky="w"
        )

        # Duration
        ctk.CTkLabel(frame, text="Durée cible (minutes)", font=("Segoe UI", 14, "bold")).grid(
            row=5, column=0, padx=15, pady=(20, 5), sticky="w"
        )
        duree_var = ctk.StringVar(value="30")
        ctk.CTkOptionMenu(frame, variable=duree_var, values=["10", "15", "20", "30", "45", "60", "75", "90"]).grid(
            row=5, column=0, padx=15, pady=5, sticky="w"
        )

        # Quality - DEFAULT TO LOW RESOURCE
        ctk.CTkLabel(frame, text="Qualité vidéo (matériel faible: choisir RAPIDE)", font=("Segoe UI", 14, "bold")).grid(
            row=7, column=0, padx=15, pady=(20, 5), sticky="w"
        )
        quality_var = ctk.StringVar(value="1")  # Default: Rapide

        qual_frame = ctk.CTkFrame(frame)
        qual_frame.grid(row=8, column=0, padx=15, pady=5, sticky="w")

        qualities = [
            ("RAPIDE - CRF 28, sans zoompan (~300MB)", "1"),
            ("NORMAL - CRF 23, zoompan léger (~1GB)", "2"),
            ("QUALITÉ - CRF 18, zoompan complet (~3GB)", "3"),
        ]

        for i, (text, value) in enumerate(qualities):
            ctk.CTkRadioButton(qual_frame, text=text, variable=quality_var, value=value).grid(
                row=0, column=i, padx=5, pady=5
            )

        # Voice
        ctk.CTkLabel(frame, text="Voix TTS", font=("Segoe UI", 14, "bold")).grid(
            row=9, column=0, padx=15, pady=(20, 5), sticky="w"
        )
        voice_var = ctk.StringVar(value="2")
        voice_opts = [f"{k}: {v['label']}" for k, v in [
            ("1", {"label": "XTTS - Vwa Gra"}),
            ("2", {"label": "XTTS - Vwa Soft"}),
            ("3", {"label": "Edge - Henri"}),
            ("4", {"label": "Edge - Denise"}),
        ]]
        ctk.CTkOptionMenu(frame, variable=voice_var, values=voice_opts).grid(
            row=10, column=0, padx=15, pady=5, sticky="ew"
        )

        # Buttons
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.grid(row=11, column=0, padx=15, pady=20, sticky="e")

        ctk.CTkButton(btn_frame, text="Annuler", command=self.show_main_menu).grid(row=0, column=0, padx=5)
        ctk.CTkButton(
            btn_frame,
            text="Créer le projet",
            command=lambda: self._create_project(
                sujet_entry.get(), type_var.get(), duree_var.get(), quality_var.get(), voice_var.get()
            ),
            fg_color="#3b82f6"
        ).grid(row=0, column=1, padx=5)

    def _create_project(self, sujet, type_choix, duree, quality, voice):
        if not sujet.strip():
            self.log("Erreur: Veuillez entrer un sujet")
            return

        self.log(f"Création du projet: {sujet}")

        # Générer un nom court à partir du sujet pour le dossier et l'id
        sys.path.insert(0, "C:\\StudioIA-Next\\modules\\brain")
        from name_project import generer_nom_court
        project_id = generer_nom_court(sujet, "fr")
        project_path = Path(PROJECTS_PATH) / project_id
        project_path.mkdir(parents=True, exist_ok=True)

        dossiers = ["chapters", "audio", "images/backgrounds", "images/overlays", "thumbnail", "export"]
        for d in dossiers:
            (project_path / d).mkdir(parents=True, exist_ok=True)

        type_map = {"1": ("priere", "fr"), "2": ("storytelling", "fr"), "3": ("storytelling", "en"), "4": ("general", "fr"), "5": ("general", "en")}
        type_contenu, langue = type_map.get(type_choix, ("priere", "fr"))

        project = {
            "id": project_id,
            "sujet": sujet,
            "langue": langue,
            "type_contenu": type_contenu,
            "statut": "en_cours",
            "etapes": {"script": "en_attente", "chapitres": "en_attente", "audio": "en_attente", "musique_fond": "en_attente", "images": "en_attente", "video": "en_attente", "thumbnail": "en_attente"},
            "meta": {"duree_cible": int(duree)},
            "chapitres": [],
            "config_locale": {"voix": voice}
        }

        with open(project_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(project, f, indent=2, ensure_ascii=False)

        self.log(f"Projet créé: {project_id}")
        self.log("Lancement du pipeline...")
        self._run_pipeline(project_path, quality)

    def _run_pipeline(self, project_path, quality="1"):
        """Run the complete pipeline with step status checking."""
        self.log(f"Pipeline: {project_path.name}")

        # Charger l'état du projet
        pjson = os.path.join(project_path, "project.json")
        try:
            with open(pjson, "r", encoding="utf-8") as f:
                project = json.load(f)
        except:
            project = {"etapes": {}}

        etapes = project.get("etapes", {})

        # Set low resource config if selected
        crf = "28" if quality == "1" else "23" if quality == "2" else "18"
        preset = "veryfast" if quality == "1" else "fast" if quality == "2" else "slow"
        use_zoompan = "0" if quality == "1" else "1"

        self.log(f"Configuration: CRF {crf}, {preset}, Zoompan: {use_zoompan}")

        # Step 1: Script
        if etapes.get("script") != "termine":
            self.log("Étape 1/5: Génération du script...")
            self._run_step("C:\\StudioIA\\modules\\brain\\generate_script.py", project_path)
            if not self._check_step_ok(pjson, "script"):
                self.log("ÉCHEC à l'étape Script - abandon du pipeline")
                return
        else:
            self.log("Étape 1/5: Script déjà terminé, on saute.")

        # Step 2: Audio
        if etapes.get("audio") != "termine":
            self.log("Étape 2/5: Génération audio TTS...")
            self._run_step("C:\\StudioIA\\modules\\tts\\run_tts.py", project_path)
            if not self._check_step_ok(pjson, "audio"):
                self.log("ÉCHEC à l'étape Audio - abandon du pipeline")
                return
        else:
            self.log("Étape 2/5: Audio déjà terminé, on saute.")

        # Step 3: Audio (ComposIA musique de fond)
        if etapes.get("musique_fond") != "termine":
            self.log("Étape 3/5: Génération musique de fond (ComposIA)...")
            self._run_step("C:\\StudioIA\\modules\\audio\\composia_config.py", project_path)
        else:
            self.log("Étape 3/5: Musique déjà générée, on saute.")

        # Step 4: Images
        if etapes.get("images") != "termine":
            self.log("Étape 4/5: Téléchargement images...")
            self._run_step("C:\\StudioIA\\modules\\images\\library_manager.py", project_path)
            if not self._check_step_ok(pjson, "images"):
                self.log("ÉCHEC à l'étape Images - abandon du pipeline")
                return
        else:
            self.log("Étape 4/5: Images déjà téléchargées, on saute.")

        # Step 5: Video
        if etapes.get("video") != "termine":
            self.log("Étape 5/5: Montage vidéo...")
            self._run_step("C:\\StudioIA\\modules\\video\\build_video.py", project_path)
            if not self._check_step_ok(pjson, "video"):
                self.log("ÉCHEC à l'étape Vidéo")
                return
        else:
            self.log("Étape 5/5: Vidéo déjà montée, on saute.")

        # Thumbnail
        if etapes.get("thumbnail") != "termine":
            self.log("Étape: Génération thumbnail...")
            self._run_step("C:\\StudioIA\\modules\\thumbnail\\thumbnail_builder.py", project_path)
        else:
            self.log("Étape: Thumbnail déjà généré, on saute.")

        self.log("Pipeline terminé !")
        self.show_main_menu()

    def _check_step_ok(self, pjson, step_name):
        """Vérifie si une étape est marquée terminée dans project.json"""
        try:
            with open(pjson, "r", encoding="utf-8") as f:
                proj = json.load(f)
            return proj.get("etapes", {}).get(step_name) == "termine"
        except:
            return False

    def _run_step(self, script, project_path):
        """Run a pipeline step with error output"""
        try:
            result = subprocess.run([
                sys.executable, script, str(project_path)
            ], capture_output=True, text=True, timeout=7200)
            if result.returncode == 0:
                self.log(f"{os.path.basename(script)}: OK")
            else:
                # Afficher les dernières lignes d'erreur
                stderr_tail = result.stderr.strip()[-500:] if result.stderr.strip() else ""
                self.log(f"{os.path.basename(script)}: ERREUR (code {result.returncode})")
                if stderr_tail:
                    self.log(f"  Dernières erreurs: {stderr_tail}")
                return False
            return True
        except subprocess.TimeoutExpired:
            self.log(f"{os.path.basename(script)}: TIMEOUT (>2h)")
            return False
        except Exception as e:
            self.log(f"Erreur: {e}")
            return False

    # ============================================================
    # CONTINUE PROJECT
    # ============================================================

    def continue_project(self):
        projets = list(Path(PROJECTS_PATH).glob("*")) if Path(PROJECTS_PATH).exists() else []
        if not projets:
            ctk.CTkLabel(self.content, text="Aucun projet trouvé", text_color="red").pack(pady=20)
            return

        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(frame, text="Choisir un projet à continuer", font=("Segoe UI", 16, "bold")).pack(pady=20)

        project_list = ctk.CTkScrollableFrame(frame, height=300)
        project_list.pack(fill="both", expand=True, padx=10, pady=10)

        for p in projets:
            pjson = p / "project.json"
            if pjson.exists():
                try:
                    with open(pjson) as f:
                        data = json.load(f)
                    ctk.CTkButton(
                        project_list,
                        text=f"{data.get('sujet', 'Sans titre')} - {data.get('statut', 'inconnu')}",
                        command=lambda path=p: self._resume_project(path),
                        height=50
                    ).pack(fill="x", padx=5, pady=5)
                except:
                    pass

        ctk.CTkButton(frame, text="Retour", command=self.show_main_menu).pack(pady=10)

    def _resume_project(self, project_path):
        self.log(f"Continuation: {project_path.name}")
        # Lire la qualité depuis video_config.json si elle existe
        vidcfg_path = os.path.join(project_path, "video_config.json")
        quality = "1"
        if os.path.exists(vidcfg_path):
            try:
                with open(vidcfg_path) as f:
                    vcfg = json.load(f)
                quality = vcfg.get("qualite", "1")
            except:
                pass
        self._run_pipeline(project_path, quality)

    # ============================================================
    # SETTINGS
    # ============================================================

    def show_settings(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Paramètres du système", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, columnspan=2, pady=20)

        # IA Model
        ctk.CTkLabel(frame, text="Modèle IA", font=("Segoe UI", 12)).grid(row=1, column=0, padx=20, pady=5, sticky="w")
        model_var = ctk.StringVar(value=self.config.get("ia_model", "qwen2"))
        ctk.CTkOptionMenu(frame, variable=model_var, values=["qwen2", "mistral", "llama3", "gemma2"]).grid(row=1, column=1, padx=20, pady=5, sticky="w")

        # Video Resolution
        ctk.CTkLabel(frame, text="Résolution vidéo", font=("Segoe UI", 12)).grid(row=2, column=0, padx=20, pady=5, sticky="w")
        res_var = ctk.StringVar(value=self.config.get("video_resolution", "1920x1080"))
        ctk.CTkOptionMenu(frame, variable=res_var, values=["1920x1080", "1280x720", "3840x2160"]).grid(row=2, column=1, padx=20, pady=5, sticky="w")

        # VOICE VOLUME
        ctk.CTkLabel(frame, text="Volume voix TTS", font=("Segoe UI", 12)).grid(row=3, column=0, padx=20, pady=5, sticky="w")
        voice_vol_var = ctk.StringVar(value=str(self.config.get("voice_volume", 1.0)))
        voice_vol_value = self.config.get("voice_volume", 1.0)
        if not isinstance(voice_vol_value, (int, float)):
            voice_vol_value = 1.0
        voice_vol_var = ctk.DoubleVar(value=voice_vol_value)
        ctk.CTkSlider(frame, from_=0.0, to=2.0, number_of_steps=20, variable=voice_vol_var).grid(row=3, column=1, padx=20, pady=5, sticky="ew")
        voice_vol_label = ctk.CTkLabel(frame, text=f"{voice_vol_value:.1f}x")
        voice_vol_label.grid(row=3, column=2, padx=5, sticky="w")

        def update_voice_vol_label(val):
            voice_vol_label.configure(text=f"{float(val):.1f}x")
        voice_vol_var.trace("w", lambda *args: update_voice_vol_label(voice_vol_var.get()))

        # MUSIC VOLUME
        ctk.CTkLabel(frame, text="Volume musique fond", font=("Segoe UI", 12)).grid(row=4, column=0, padx=20, pady=5, sticky="w")
        music_vol_var = ctk.StringVar(value=str(self.config.get("music_volume", 0.15)))
        music_vol_value = self.config.get("music_volume", 0.15)
        if not isinstance(music_vol_value, (int, float)):
            music_vol_value = 0.15
        music_vol_var = ctk.DoubleVar(value=music_vol_value)
        ctk.CTkSlider(frame, from_=0.0, to=1.0, number_of_steps=20, variable=music_vol_var).grid(row=4, column=1, padx=20, pady=5, sticky="ew")
        music_vol_label = ctk.CTkLabel(frame, text=f"{music_vol_value:.1f}x")
        music_vol_label.grid(row=4, column=2, padx=5, sticky="w")

        def update_music_vol_label(val):
            music_vol_label.configure(text=f"{float(val):.1f}x")
        music_vol_var.trace("w", lambda *args: update_music_vol_label(music_vol_var.get()))

        # SEPARATOR
        sep1 = ctk.CTkFrame(frame, height=2, fg_color="#374151")
        sep1.grid(row=5, column=0, columnspan=3, sticky="ew", padx=20, pady=15)

        # AUDIO EFFECTS TITLE
        ctk.CTkLabel(frame, text="Effets Audio", font=("Segoe UI", 12, "bold")).grid(row=6, column=0, columnspan=2, pady=(10, 5))

        # REVERB EFFECT
        ctk.CTkLabel(frame, text="Réverbe", font=("Segoe UI", 11)).grid(row=7, column=0, padx=20, pady=5, sticky="w")
        reverb_var = ctk.StringVar(value=str(self.config.get("reverb_level", 0.3)))
        ctk.CTkOptionMenu(frame, variable=reverb_var, values=["0.0", "0.2", "0.4", "0.6", "0.8", "1.0"]).grid(row=7, column=1, padx=20, pady=5, sticky="w")

        # DELAY EFFECT
        ctk.CTkLabel(frame, text="Delay", font=("Segoe UI", 11)).grid(row=8, column=0, padx=20, pady=5, sticky="w")
        delay_var = ctk.StringVar(value=str(self.config.get("delay_level", 0.2)))
        ctk.CTkOptionMenu(frame, variable=delay_var, values=["0.0", "0.2", "0.4", "0.6", "0.8", "1.0"]).grid(row=8, column=1, padx=20, pady=5, sticky="w")

        # EQ (Simple preset selection)
        ctk.CTkLabel(frame, text="Egaliseur (EQ)", font=("Segoe UI", 11)).grid(row=9, column=0, padx=20, pady=5, sticky="w")
        eq_var = ctk.StringVar(value=self.config.get("eq_preset", "normal"))
        eq_options = ["Normal", "Chaleur", "Clarté", "Basses renforcées", "Voix prioritaire"]
        ctk.CTkOptionMenu(frame, variable=eq_var, values=eq_options).grid(row=9, column=1, padx=20, pady=5, sticky="w")

        # ============================================
        # NETTOYAGE AUDIO (Denoiser + Gate + Whisper)
        # ============================================
        sep_nettoyage = ctk.CTkFrame(frame, height=2, fg_color="#374151")
        sep_nettoyage.grid(row=10, column=0, columnspan=3, sticky="ew", padx=20, pady=15)

        ctk.CTkLabel(frame, text="Nettoyage Audio", font=("Segoe UI", 12, "bold")).grid(row=11, column=0, columnspan=2, pady=(10, 5))

        # GATE TOGGLE
        gate_var = ctk.BooleanVar(value=self.config.get("gate_enabled", True))
        ctk.CTkLabel(frame, text="Gate (coupe silences)", font=("Segoe UI", 11)).grid(row=12, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkSwitch(frame, text="", variable=gate_var, onvalue=True, offvalue=False, command=lambda: None).grid(row=12, column=1, padx=20, pady=5, sticky="w")

        # GATE SENSITIVITY
        ctk.CTkLabel(frame, text="Sensibilité gate", font=("Segoe UI", 11)).grid(row=13, column=0, padx=20, pady=5, sticky="w")
        gate_sens_value = self.config.get("gate_sensitivity", 0.5)
        if not isinstance(gate_sens_value, (int, float)):
            gate_sens_value = 0.5
        gate_sens_var = ctk.DoubleVar(value=gate_sens_value)
        ctk.CTkSlider(frame, from_=0.1, to=1.0, number_of_steps=9, variable=gate_sens_var).grid(row=13, column=1, padx=20, pady=5, sticky="ew")
        gate_sens_label = ctk.CTkLabel(frame, text=f"{gate_sens_value:.1f}")
        gate_sens_label.grid(row=13, column=2, padx=5, sticky="w")

        def update_gate_sens_label(val):
            gate_sens_label.configure(text=f"{float(val):.1f}")
        gate_sens_var.trace("w", lambda *args: update_gate_sens_label(gate_sens_var.get()))

        # WHISPER VERIFICATION TOGGLE
        whisper_var = ctk.BooleanVar(value=self.config.get("verification_enabled", True))
        ctk.CTkLabel(frame, text="Vérif. Whisper (paroles)", font=("Segoe UI", 11)).grid(row=14, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkSwitch(frame, text="", variable=whisper_var, onvalue=True, offvalue=False).grid(row=14, column=1, padx=20, pady=5, sticky="w")

        # WHISPER AUTO REGEN TOGGLE
        regen_var = ctk.BooleanVar(value=self.config.get("verification_auto_regenerate", True))
        ctk.CTkLabel(frame, text="Régénération auto", font=("Segoe UI", 11)).grid(row=15, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkSwitch(frame, text="", variable=regen_var, onvalue=True, offvalue=False).grid(row=15, column=1, padx=20, pady=5, sticky="w")

        # SEPARATOR
        sep2 = ctk.CTkFrame(frame, height=2, fg_color="#374151")
        sep2.grid(row=17, column=0, columnspan=3, sticky="ew", padx=20, pady=15)

        # SUBTITLES SETTINGS TITLE
        ctk.CTkLabel(frame, text="Sous-titres", font=("Segoe UI", 12, "bold")).grid(row=18, column=0, columnspan=2, pady=(10, 5))

        # SUBTITLES STYLE
        ctk.CTkLabel(frame, text="Style de sous-titres", font=("Segoe UI", 11)).grid(row=19, column=0, padx=20, pady=5, sticky="w")
        sub_style_var = ctk.StringVar(value=self.config.get("subtitle_style", "1"))
        sub_style_options = ["Or classique", "Blanc pur", "Cyan lumineux", "Rose spirituel", "Vert emeraude", "Jaune doré"]
        ctk.CTkOptionMenu(frame, variable=sub_style_var, values=sub_style_options).grid(row=19, column=1, padx=20, pady=5, sticky="w")

        # SUBTITLES SIZE SLIDER
        ctk.CTkLabel(frame, text="Taille des sous-titres", font=("Segoe UI", 11)).grid(row=20, column=0, padx=20, pady=5, sticky="w")
        sub_size_value = self.config.get("subtitle_size", 14)
        if not isinstance(sub_size_value, (int, float)):
            sub_size_value = 14
        sub_size_var = ctk.IntVar(value=sub_size_value)
        sub_size_slider = ctk.CTkSlider(frame, from_=8, to=32, number_of_steps=24, variable=sub_size_var)
        sub_size_slider.grid(row=20, column=1, padx=20, pady=5, sticky="ew")
        sub_size_label = ctk.CTkLabel(frame, text=f"{sub_size_var.get()} pt")
        sub_size_label.grid(row=13, column=2, padx=5, sticky="w")

        def update_sub_size_label(val):
            sub_size_label.configure(text=f"{int(float(val))} pt")
        sub_size_var.trace("w", lambda *args: update_sub_size_label(sub_size_var.get()))

        # SUBTITLES POSITION (vertical margin)
        ctk.CTkLabel(frame, text="Position verticale", font=("Segoe UI", 11)).grid(row=14, column=0, padx=20, pady=5, sticky="w")
        sub_margin_value = self.config.get("subtitle_margin", 40)
        if not isinstance(sub_margin_value, (int, float)):
            sub_margin_value = 40
        sub_margin_var = ctk.IntVar(value=sub_margin_value)
        sub_margin_slider = ctk.CTkSlider(frame, from_=10, to=100, number_of_steps=18, variable=sub_margin_var)
        sub_margin_slider.grid(row=21, column=1, padx=20, pady=5, sticky="ew")
        sub_margin_label = ctk.CTkLabel(frame, text=f"{sub_margin_var.get()} px")
        sub_margin_label.grid(row=21, column=2, padx=5, sticky="w")

        def update_sub_margin_label(val):
            sub_margin_label.configure(text=f"{int(float(val))} px")
        sub_margin_var.trace("w", lambda *args: update_sub_margin_label(sub_margin_var.get()))

        # SEPARATOR — MODE VISUEL
        sep_visuel = ctk.CTkFrame(frame, height=2, fg_color="#374151")
        sep_visuel.grid(row=23, column=0, columnspan=3, sticky="ew", padx=20, pady=15)

        ctk.CTkLabel(frame, text="Mode Visuel", font=("Segoe UI", 12, "bold")).grid(row=24, column=0, columnspan=2, pady=(10, 5))

        mode_visuel_var = ctk.StringVar(value=self.config.get("mode_visuel", "intelligent"))
        modes_visuels = [
            ("images", "🖼  Images uniquement (actuel)"),
            ("videos", "🎬  Vidéos libres de droits"),
            ("mix",    "🔄  Mix images + vidéos"),
            ("intelligent", "🤖  Mode intelligent (IA décide)"),
        ]

        ctk.CTkLabel(frame, text="Type de contenu visuel", font=("Segoe UI", 11)).grid(row=25, column=0, padx=20, pady=5, sticky="w")
        mode_frame = ctk.CTkFrame(frame, fg_color="transparent")
        mode_frame.grid(row=25, column=1, columnspan=2, padx=10, pady=5, sticky="w")

        for val, label in modes_visuels:
            ctk.CTkRadioButton(
                mode_frame, text=label, variable=mode_visuel_var, value=val,
                font=("Segoe UI", 10)
            ).pack(anchor="w", pady=2)

        # SEPARATOR — PROFIL
        sep_profil = ctk.CTkFrame(frame, height=2, fg_color="#374151")
        sep_profil.grid(row=26, column=0, columnspan=3, sticky="ew", padx=20, pady=15)

        ctk.CTkLabel(frame, text="Profil de contenu", font=("Segoe UI", 12, "bold")).grid(row=27, column=0, columnspan=2, pady=(10, 5))

        # Charger la liste des profils disponibles
        profils_disponibles = []
        profil_actif_id = self.config.get("profil_actif", "prayer")
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from core.profiles.profile_manager import ProfileManager
            pm = ProfileManager()
            for p in pm.lister_profils():
                pid = p.get("id", "?")
                pname = p.get("name", pid)
                profils_disponibles.append(f"{pid}: {pname}")
        except Exception as e:
            profils_disponibles = ["prayer: Prières chrétiennes", "default: Profil générique"]
            log(f"Erreur chargement profils: {e}")

        profil_var = ctk.StringVar(value=f"{profil_actif_id}: {self._get_profil_name(profil_actif_id)}")
        ctk.CTkLabel(frame, text="Profil actif", font=("Segoe UI", 11)).grid(row=28, column=0, padx=20, pady=5, sticky="w")
        profil_menu = ctk.CTkOptionMenu(frame, variable=profil_var, values=profils_disponibles)
        profil_menu.grid(row=28, column=1, padx=20, pady=5, sticky="w")

        # Save button
        save_row = 29
        ctk.CTkButton(
            frame,
            text="Sauvegarder",
            command=lambda: self._save_settings(
                model_var.get(), res_var.get(),
                float(voice_vol_var.get()), float(music_vol_var.get()),
                float(reverb_var.get()), float(delay_var.get()), eq_var.get(),
                sub_style_var.get(), float(sub_size_var.get()), float(sub_margin_var.get()),
                gate_var.get(), float(gate_sens_var.get()),
                whisper_var.get(), regen_var.get(),
                mode_visuel_var.get(),
                profil_var.get()
            )
        ).grid(row=save_row, column=0, columnspan=2, pady=20)

        ctk.CTkButton(frame, text="Retour", command=self.show_main_menu).grid(row=save_row + 1, column=0, columnspan=2)

    def _get_profil_name(self, profil_id):
        """Retourne le nom d'un profil depuis son ID"""
        try:
            from core.profiles.profile_manager import ProfileManager
            pm = ProfileManager()
            p = pm.obtenir_profil(profil_id)
            if p:
                return p.get("name", profil_id)
        except:
            pass
        return profil_id

    def _save_settings(self, model, resolution, voice_volume, music_volume, reverb, delay, eq_preset,
                       subtitle_style="1", subtitle_size=14, subtitle_margin=40,
                       gate_enabled=True, gate_sensitivity=0.5,
                       whisper_enabled=True, regen_enabled=True,
                       mode_visuel="intelligent", profil_str="prayer: Prières chrétiennes"):
        self.config["ia_model"] = model
        self.config["video_resolution"] = resolution
        self.config["voice_volume"] = voice_volume
        self.config["music_volume"] = music_volume
        self.config["reverb_level"] = reverb
        self.config["delay_level"] = delay
        self.config["eq_preset"] = eq_preset
        self.config["subtitle_style"] = subtitle_style
        self.config["subtitle_size"] = subtitle_size
        self.config["subtitle_margin"] = subtitle_margin
        # Nettoyage audio
        self.config["gate_enabled"] = bool(gate_enabled)
        self.config["gate_sensitivity"] = float(gate_sensitivity)
        self.config["verification_enabled"] = bool(whisper_enabled)
        self.config["verification_auto_regenerate"] = bool(regen_enabled)
        # Mode visuel
        self.config["mode_visuel"] = mode_visuel
        # Profil actif
        if profil_str and ":" in profil_str:
            profil_id = profil_str.split(":")[0].strip()
            self.config["profil_actif"] = profil_id
        self.save_config()
        self.log(f"Paramètres sauvegardés (mode visuel: {mode_visuel}, profil: {self.config.get('profil_actif', 'prayer')})")

    # ============================================================
    # ASSETS MANAGER
    # ============================================================

    def show_assets_manager(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.content,
            text="Gestionnaire d'Assets\nLancement en cours...",
            font=("Segoe UI", 16)
        ).pack(pady=50)
        self.update_idletasks()

        self.log("Lancement du gestionnaire d'assets...")
        subprocess.Popen([sys.executable, "C:\\StudioIA\\modules\\assets_manager.py"])
        ctk.CTkButton(
            self.content,
            text="Retour au menu",
            command=self.show_main_menu
        ).pack(pady=20)

    # ============================================================
    # SHORTS GENERATOR
    # ============================================================

    def show_shorts_generator(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.content,
            text="Générateur Shorts\nLancement en cours...",
            font=("Segoe UI", 16)
        ).pack(pady=50)
        self.update_idletasks()

        self.log("Lancement du générateur Shorts...")
        subprocess.Popen([sys.executable, "C:\\StudioIA\\modules\\shorts\\generate_shorts.py"])
        ctk.CTkButton(
            self.content,
            text="Retour au menu",
            command=self.show_main_menu
        ).pack(pady=20)

    # ============================================================
    # THUMBNAIL STANDALONE
    # ============================================================

    def show_thumbnail_standalone(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.content,
            text="Générateur Thumbnails\nInterface en cours de chargement...",
            font=("Segoe UI", 16)
        ).pack(pady=50)
        self.update_idletasks()

        # Create thumbnail generator window
        self.log("Ouverture du générateur de thumbnails...")
        ThumbnailGeneratorGUI(self)

    # ============================================================
    # RENAME PROJECTS
    # ============================================================

    def rename_projects(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        ctk.CTkLabel(
            self.content,
            text="Renommage des Projets\nEn cours...",
            font=("Segoe UI", 16)
        ).pack(pady=50)
        self.update_idletasks()

        self.log("Renommage des projets...")
        subprocess.Popen([sys.executable, "C:\\StudioIA\\modules\\brain\\rename_projects.py"])
        ctk.CTkButton(
            self.content,
            text="Retour au menu",
            command=self.show_main_menu
        ).pack(pady=20)

    # ============================================================
    # DIAGNOSTIC
    # ============================================================

    def run_diagnostic(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(frame, text="Diagnostic Système", font=("Segoe UI", 16, "bold")).pack(pady=20)

        results = ctk.CTkFrame(frame)
        results.pack(fill="both", expand=True, padx=20, pady=10)

        # System info
        ctk.CTkLabel(results, text="Système:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=5)

        import platform
        ctk.CTkLabel(results, text=f"OS: {platform.system()} {platform.release()}").pack(anchor="w")

        try:
            import psutil
            cpu = psutil.cpu_count()
            ram = psutil.virtual_memory().total / (1024**3)
            ctk.CTkLabel(results, text=f"Cœurs CPU: {cpu}").pack(anchor="w")
            ctk.CTkLabel(results, text=f"RAM: {ram:.1f} GB").pack(anchor="w")
        except:
            ctk.CTkLabel(results, text="psutil non disponible").pack(anchor="w")

        # Ollama check
        ctk.CTkLabel(results, text="\nOllama:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=5)
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                modeles = r.json().get("models", [])
                ctk.CTkLabel(results, text=f"Ollama: CONNECTÉ | {len(modeles)} modèles disponibles").pack(anchor="w", text_color="#10b981")
            else:
                ctk.CTkLabel(results, text="Ollama: NON DISPONIBLE").pack(anchor="w", text_color="#ef4444")
        except:
            ctk.CTkLabel(results, text="Ollama: NON DISPONIBLE").pack(anchor="w", text_color="#ef4444")

        # Low resource warning
        if self.low_resource_mode:
            ctk.CTkLabel(
                results,
                text="\n⚠ MODE FAIBLE ACTIF - Performances réduites",
                font=("Segoe UI", 10, "bold"),
                text_color="#f59e0b"
            ).pack(anchor="w", pady=10)

        ctk.CTkButton(frame, text="Retour", command=self.show_main_menu).pack(pady=10)

    # ============================================================
    # VOICE CLONER
    # ============================================================

    def show_voice_cloner(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Clonage de Voix", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=20
        )

        # Nom de la voix
        ctk.CTkLabel(frame, text="Nom de la voix", font=("Segoe UI", 12)).grid(
            row=1, column=0, padx=20, pady=5, sticky="w"
        )
        nom_voix_entry = ctk.CTkEntry(frame, placeholder_text="Ex: Voix Clone Henri")
        nom_voix_entry.grid(row=1, column=1, padx=20, pady=5, sticky="ew")

        # Description
        ctk.CTkLabel(frame, text="Description (optionnel)", font=("Segoe UI", 12)).grid(
            row=2, column=0, padx=20, pady=5, sticky="w"
        )
        desc_entry = ctk.CTkEntry(frame, placeholder_text="Genre, âge, style...")
        desc_entry.grid(row=2, column=1, padx=20, pady=5, sticky="ew")

        # Fichier audio
        ctk.CTkLabel(frame, text="Fichier audio (5-30s recommandé)", font=("Segoe UI", 12)).grid(
            row=3, column=0, padx=20, pady=5, sticky="w"
        )
        audio_path_var = ctk.StringVar()
        audio_path_entry = ctk.CTkEntry(frame, textvariable=audio_path_var)
        audio_path_entry.grid(row=3, column=1, padx=20, pady=5, sticky="ew")

        def choisir_fichier():
            import tkinter.filedialog
            fichier = tkinter.filedialog.askopenfilename(
                title="Sélectionner un fichier audio",
                filetypes=[("Fichiers audio", "*.wav *.mp3 *.flac *.m4a")]
            )
            if fichier:
                audio_path_var.set(fichier)

        ctk.CTkButton(
            frame, text="Parcourir", command=choisir_fichier, width=80
        ).grid(row=3, column=2, padx=5, pady=5)

        # Bouton cloner
        def cloner():
            from modules.tts.voice_cloner import cloner_voix, lister_voix_clonees
            nom = nom_voix_entry.get().strip()
            audio_path = audio_path_var.get().strip()

            if not nom:
                self.log("Erreur: Veuillez entrer un nom de voix")
                return
            if not audio_path or not os.path.exists(audio_path):
                self.log("Erreur: Fichier audio introuvable")
                return

            self.log(f"Clonage de la voix: {nom}...")
            voix = cloner_voix(nom, audio_path, desc_entry.get().strip())

            if voix:
                self.log(f"Voix clonée avec succès: {voix['name']}")
                self.log(f"  Key: {voix['key']}")
                self.log(f"  Fichier: {voix['sample_path']}")
            else:
                self.log("Échec du clonage de voix")

        ctk.CTkButton(
            frame, text="Cloner la voix", command=cloner, fg_color="#9d174d"
        ).grid(row=4, column=0, columnspan=2, pady=20)

        # Liste des voix clonées
        ctk.CTkLabel(frame, text="Voix clonées disponibles", font=("Segoe UI", 12, "bold")).grid(
            row=5, column=0, columnspan=2, pady=(20, 10)
        )

        self.voix_list_frame = ctk.CTkScrollableFrame(frame, height=150)
        self.voix_list_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=20, pady=5)

        def refresh_voix_list():
            from modules.tts.voice_cloner import lister_voix_clonees
            for widget in self.voix_list_frame.winfo_children():
                widget.destroy()

            voix = lister_voix_clonees()
            if not voix:
                ctk.CTkLabel(self.voix_list_frame, text="Aucune voix clonée").pack(pady=10)
                return

            for v in voix:
                voix_frame = ctk.CTkFrame(self.voix_list_frame)
                voix_frame.pack(fill="x", padx=5, pady=5)

                ctk.CTkLabel(voix_frame, text=f"• {v.get('name', 'Sans nom')}", font=("Segoe UI", 11)).pack(side="left", padx=5)
                ctk.CTkLabel(voix_frame, text=f"({v.get('langue', '??')})", text_color="#6b7280").pack(side="left", padx=5)

                # Afficher la durée
                duree = v.get('duree_secondes', 0)
                if duree > 0:
                    ctk.CTkLabel(voix_frame, text=f" - {duree:.1f}s", text_color="#6b7280").pack(side="left", padx=5)

        refresh_voix_list()
        ctk.CTkButton(frame, text="Actualiser", command=refresh_voix_list, height=30).grid(
            row=7, column=0, columnspan=2, pady=10
        )

        ctk.CTkButton(frame, text="Retour", command=self.show_main_menu).grid(row=8, column=0, columnspan=2, pady=10)

    # ============================================================
    # CORRECTIONS & APPRENTISSAGE
    # ============================================================

    def _lister_projets_avec_script(self):
        """Liste les projets qui ont un script généré (corrigeable)"""
        projets = []
        if not Path(PROJECTS_PATH).exists():
            return projets
        for p in Path(PROJECTS_PATH).iterdir():
            pjson = p / "project.json"
            if pjson.exists():
                try:
                    with open(pjson, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("etapes", {}).get("script") == "termine":
                        projets.append((p.name, data.get("sujet", p.name)))
                except:
                    pass
        return projets

    def show_corrections(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Corrections & Apprentissage", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=20
        )

        # Stats des apprentissages
        try:
            from modules.learning.correction_memory import statistiques
            stats = statistiques()
            stats_frame = ctk.CTkFrame(frame, fg_color="#1f2937", corner_radius=8)
            stats_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
            stats_text = (f"Corrections: {stats['total_corrections']} | "
                         f"Analysées: {stats['analysees']} | "
                         f"Validées: {stats['validees']} | "
                         f"En attente: {stats['en_attente']}")
            ctk.CTkLabel(stats_frame, text=stats_text, font=("Segoe UI", 11)).pack(pady=10)
        except Exception as e:
            self.log(f"Erreur stats: {e}")

        # Sélection de projet à corriger
        ctk.CTkLabel(frame, text="Projet à corriger", font=("Segoe UI", 12, "bold")).grid(
            row=2, column=0, padx=20, pady=(20, 5), sticky="w"
        )

        projets = self._lister_projets_avec_script()
        projet_var = ctk.StringVar()
        projets_opts = [f"{p[0]} — {p[1][:50]}" for p in projets] if projets else ["Aucun projet disponible"]

        ctk.CTkOptionMenu(frame, variable=projet_var, values=projets_opts).grid(
            row=3, column=0, padx=20, pady=5, sticky="ew"
        )

        if projets:
            def open_chapter_editor():
                selection = projet_var.get()
                if selection and " — " in selection:
                    projet_id = selection.split(" — ")[0].strip()
                    self._show_chapter_editor(projet_id)

            ctk.CTkButton(frame, text="Ouvrir l'éditeur de chapitres",
                          command=open_chapter_editor, fg_color="#f97316").grid(
                row=4, column=0, padx=20, pady=10
            )

        # Section d'analyse des corrections en attente
        sep = ctk.CTkFrame(frame, height=2, fg_color="#374151")
        sep.grid(row=5, column=0, sticky="ew", padx=20, pady=20)

        ctk.CTkLabel(frame, text="Apprentissage automatique", font=("Segoe UI", 12, "bold")).grid(
            row=6, column=0, padx=20, pady=5, sticky="w"
        )

        ctk.CTkLabel(frame, text=("Analyse les corrections en attente via l'IA locale\n"
                                  "et propose des règles à ajouter au profil actif."),
                     font=("Segoe UI", 10), text_color="#9ca3af", justify="left").grid(
            row=7, column=0, padx=20, pady=5, sticky="w"
        )

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=8, column=0, padx=20, pady=10, sticky="w")

        def analyser_corrections():
            self.log("Analyse des corrections en cours...")
            try:
                from modules.learning.learning_engine import analyser_toutes_corrections, generer_rapport_apprentissage
                props = analyser_toutes_corrections(limite=10)
                if props:
                    self.log(f"{len(props)} proposition(s) générée(s)")
                    self._show_propositions(props)
                else:
                    rapport = generer_rapport_apprentissage()
                    self.log(f"Analyse terminée. {rapport.split(chr(10))[1]}")
                    self.log("Aucune nouvelle proposition générée (LLM peut-être indisponible)")
            except Exception as e:
                self.log(f"Erreur analyse: {e}")

        ctk.CTkButton(btn_frame, text="Analyser les nouvelles corrections",
                      command=analyser_corrections, fg_color="#10b981").pack(side="left", padx=5)

        def voir_rapport():
            try:
                from modules.learning.learning_engine import generer_rapport_apprentissage
                rapport = generer_rapport_apprentissage()
                self._show_text_dialog("Rapport d'apprentissage", rapport)
            except Exception as e:
                self.log(f"Erreur rapport: {e}")

        ctk.CTkButton(btn_frame, text="Voir le rapport", command=voir_rapport,
                      fg_color="#6366f1").pack(side="left", padx=5)

        ctk.CTkButton(frame, text="Retour", command=self.show_main_menu).grid(
            row=9, column=0, padx=20, pady=20, sticky="w"
        )

    def _show_chapter_editor(self, projet_id):
        """Affiche l'éditeur de chapitres pour un projet"""
        for widget in self.content.winfo_children():
            widget.destroy()

        project_path = Path(PROJECTS_PATH) / projet_id
        pjson = project_path / "project.json"
        with open(pjson, "r", encoding="utf-8") as f:
            project = json.load(f)

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)

        # Header
        ctk.CTkLabel(frame, text=f"Correction: {projet_id}",
                     font=("Segoe UI", 16, "bold")).grid(row=0, column=0, padx=20, pady=10, sticky="w")
        ctk.CTkLabel(frame, text=project.get("sujet", ""),
                     font=("Segoe UI", 11), text_color="#9ca3af").grid(row=1, column=0, padx=20, pady=5, sticky="w")

        # Zone de chapitres scrollable
        ch_frame = ctk.CTkScrollableFrame(frame, corner_radius=8)
        ch_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        ch_frame.grid_columnconfigure(0, weight=1)

        # Charger les chapitres
        chapitres = project.get("chapitres", [])
        if not chapitres:
            ctk.CTkLabel(ch_frame, text="Aucun chapitre trouvé", text_color="#ef4444").pack(pady=20)
        else:
            # Dictionnaire pour stocker les textes modifiés
            text_widgets = {}

            for ch in chapitres:
                ch_id = ch["id"]
                ch_file = project_path / ch["script_file"]
                titre = ch.get("titre", ch_id)

                # Lire le texte actuel
                texte = ""
                if ch_file.exists():
                    with open(ch_file, "r", encoding="utf-8") as f:
                        texte = f.read()
                elif ch.get("texte"):
                    texte = ch["texte"]

                # Cadre pour ce chapitre
                ch_card = ctk.CTkFrame(ch_frame, corner_radius=8, fg_color="#1f2937")
                ch_card.pack(fill="x", padx=5, pady=5)
                ch_card.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(ch_card, text=f"{ch_id}: {titre}",
                             font=("Segoe UI", 11, "bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

                text_widget = ctk.CTkTextbox(ch_card, height=120, wrap="word")
                text_widget.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
                text_widget.insert("1.0", texte)
                text_widgets[ch_id] = {
                    "widget": text_widget,
                    "original": texte,
                    "titre": titre,
                    "fichier": str(ch_file)
                }

                # Barre d'outils du chapitre
                tool_frame = ctk.CTkFrame(ch_card, fg_color="transparent")
                tool_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")

                def save_chapter(cid=ch_id):
                    data = text_widgets[cid]
                    new_text = data["widget"].get("1.0", "end-1c").strip()
                    original = data["original"].strip()

                    if new_text != original:
                        # Sauvegarder le fichier
                        with open(data["fichier"], "w", encoding="utf-8") as f:
                            f.write(new_text)
                        # Enregistrer la correction dans la mémoire
                        try:
                            from modules.learning.correction_memory import enregistrer_correction
                            enregistrer_correction(
                                profil_id=self.config.get("profil_actif", "prayer"),
                                projet_id=projet_id,
                                chapitre_id=cid,
                                texte_original=original,
                                texte_corrige=new_text,
                                titre_chapitre=data["titre"],
                                sujet_projet=project.get("sujet", "")
                            )
                            self.log(f"Chapitre {cid} corrigé et enregistré")
                        except Exception as e:
                            self.log(f"Erreur enregistrement correction: {e}")
                    else:
                        self.log(f"Chapitre {cid}: aucune modification")

                ctk.CTkButton(tool_frame, text="💾 Sauvegarder", command=save_chapter,
                              fg_color="#10b981", height=28, font=("Segoe UI", 10)).pack(side="left", padx=2)

        # Boutons de navigation
        nav_frame = ctk.CTkFrame(frame, fg_color="transparent")
        nav_frame.grid(row=3, column=0, padx=20, pady=10, sticky="w")

        ctk.CTkButton(nav_frame, text="← Retour aux corrections",
                      command=lambda: self.show_corrections(),
                      fg_color="#374151").pack(side="left", padx=5)

    def _show_propositions(self, propositions):
        """Affiche les propositions d'apprentissage pour validation"""
        win = ctk.CTkToplevel(self)
        win.title("Propositions d'apprentissage")
        win.geometry("600x500")
        win.transient(self)

        frame = ctk.CTkFrame(win, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Propositions de règles à ajouter au profil",
                     font=("Segoe UI", 14, "bold")).grid(row=0, column=0, pady=10)

        scroll = ctk.CTkScrollableFrame(frame, corner_radius=8)
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)

        for i, prop in enumerate(propositions):
            if prop.get("type_proposition") == "aucune":
                continue

            card = ctk.CTkFrame(scroll, corner_radius=8, fg_color="#1f2937")
            card.pack(fill="x", padx=5, pady=5)
            card.grid_columnconfigure(0, weight=1)

            type_label = {
                "ajouter_mot_eviter": "🚫 Mot à éviter",
                "ajouter_remplacement": "🔄 Remplacement",
                "nouvelle_regle_generale": "📝 Nouvelle règle générale",
                "nouvelle_regle_grammaire": "📖 Nouvelle règle grammaire",
            }.get(prop.get("type_proposition", ""), "❓ Proposition")

            ctk.CTkLabel(card, text=f"{type_label} (confiance: {prop.get('confiance', 0):.0%})",
                         font=("Segoe UI", 11, "bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

            valeur = prop.get("valeur", "")
            ctk.CTkLabel(card, text=f"Valeur: {valeur}",
                         font=("Segoe UI", 10), wraplength=450, justify="left").grid(
                row=1, column=0, padx=10, pady=2, sticky="w")

            justification = prop.get("justification", "")
            ctk.CTkLabel(card, text=f"Justification: {justification}",
                         font=("Segoe UI", 9), text_color="#9ca3af", wraplength=450, justify="left").grid(
                row=2, column=0, padx=10, pady=(2, 10), sticky="w")

            btn_sub = ctk.CTkFrame(card, fg_color="transparent")
            btn_sub.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="w")

            def do_accept(p=prop):
                try:
                    from modules.learning.learning_engine import appliquer_proposition
                    profil_id = self.config.get("profil_actif", "prayer")
                    if appliquer_proposition(p, profil_id):
                        self.log(f"Règle acceptée et intégrée au profil '{profil_id}'")
                except Exception as e:
                    self.log(f"Erreur application: {e}")

            ctk.CTkButton(btn_sub, text="✓ Accepter", command=do_accept,
                          fg_color="#10b981", height=28, font=("Segoe UI", 10)).pack(side="left", padx=2)

            ctk.CTkButton(btn_sub, text="✗ Refuser", command=lambda: card.destroy(),
                          fg_color="#ef4444", height=28, font=("Segoe UI", 10)).pack(side="left", padx=2)

        ctk.CTkButton(frame, text="Fermer", command=win.destroy,
                      fg_color="#374151").grid(row=2, column=0, pady=10)

    def _show_text_dialog(self, title, text):
        """Affiche un texte long dans une fenêtre modale"""
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("600x400")
        win.transient(self)

        frame = ctk.CTkFrame(win, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        textbox = ctk.CTkTextbox(frame, wrap="word", font=("Consolas", 10))
        textbox.grid(row=0, column=0, sticky="nsew")
        textbox.insert("1.0", text)
        textbox.configure(state="disabled")

        ctk.CTkButton(frame, text="Fermer", command=win.destroy,
                      fg_color="#374151").grid(row=1, column=0, pady=10)

    # ============================================================
    # PROJECT MONITOR
    # ============================================================

    def show_project_monitor(self):
        for widget in self.content.winfo_children():
            widget.destroy()

        frame = ctk.CTkFrame(self.content, corner_radius=10)
        frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Monitor de Projet", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=2, pady=20
        )

        # Sélection projet
        ctk.CTkLabel(frame, text="Sélectionner un projet", font=("Segoe UI", 12)).grid(
            row=1, column=0, padx=20, pady=5, sticky="w"
        )

        projets = list(Path(PROJECTS_PATH).glob("*")) if Path(PROJECTS_PATH).exists() else []
        projets_opts = [p.name for p in projets if (p / "project.json").exists()]

        if projets_opts:
            projet_var = ctk.StringVar(value=projets_opts[0] if projets_opts else "")
            ctk.CTkOptionMenu(frame, variable=projet_var, values=projets_opts).grid(
                row=1, column=1, padx=20, pady=5, sticky="ew"
            )

            def lancer_monitor():
                projet_path = os.path.join(PROJECTS_PATH, projet_var.get())
                from modules.monitoring.project_monitor import ProjectMonitor, create_monitor_gui
                monitor = ProjectMonitor(projet_path)
                create_monitor_gui(monitor)
                monitor.start()
                self.log(f"Monitor lancé pour: {projet_var.get()}")

            ctk.CTkButton(frame, text="Lancer le monitor", command=lancer_monitor).grid(
                row=2, column=0, columnspan=2, pady=20
            )
        else:
            ctk.CTkLabel(frame, text="Aucun projet disponible", text_color="#ef4444").grid(
                row=2, column=0, columnspan=2, pady=20
            )

        ctk.CTkButton(frame, text="Retour", command=self.show_main_menu).grid(
            row=3, column=0, columnspan=2, pady=10
        )


def main():
    app = StudioIAApp()
    app.mainloop()


if __name__ == "__main__":
    main()
