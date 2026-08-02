#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module de surveillance des ressources en temps réel pour StudioIA
Affiche la consommation CPU, RAM et GPU pendant la génération de projets.
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
from pathlib import Path

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import GPUtil
    GPUTIL_AVAILABLE = True
except ImportError:
    GPUTIL_AVAILABLE = False


class ProjectMonitor:
    """Moniteur de ressources pour les projets StudioIA."""

    def __init__(self, project_path):
        self.project_path = project_path
        self.project_id = Path(project_path).name
        self.monitoring = False
        self.data = []
        self.thread = None
        self.start_time = None
        self.log_file = Path(project_path) / "monitoring.json"

    def get_cpu_usage(self):
        """Retourne l'utilisation CPU en %."""
        if not PSUTIL_AVAILABLE:
            return 0
        return psutil.cpu_percent(interval=0.1)

    def get_memory_usage(self):
        """Retourne l'utilisation mémoire (RAM) en MB."""
        if not PSUTIL_AVAILABLE:
            return 0
        mem = psutil.virtual_memory()
        return {
            "used_mb": int(mem.used / (1024 * 1024)),
            "available_mb": int(mem.available / (1024 * 1024)),
            "total_mb": int(mem.total / (1024 * 1024)),
            "percent": mem.percent
        }

    def get_gpu_usage(self):
        """Retourne l'utilisation GPU et VRAM."""
        if not GPUTIL_AVAILABLE:
            return None

        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Prendre la première GPU
                return {
                    "id": gpu.id,
                    "name": gpu.name,
                    "load_percent": gpu.load * 100,
                    "memory_used_mb": int(gpu.memoryUsed),
                    "memory_total_mb": int(gpu.memoryTotal),
                    "temperature": gpu.temperature
                }
        except:
            pass
        return None

    def get_process_info(self):
        """Retourne les informations sur le processus Python actuel."""
        if not PSUTIL_AVAILABLE:
            return None

        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            return {
                "pid": process.pid,
                "name": process.name(),
                "memory_mb": int(mem_info.rss / (1024 * 1024)),
                "cpu_percent": process.cpu_percent(),
                "threads": process.num_threads()
            }
        except:
            return None

    def collect_sample(self):
        """Collecte un échantillon de métriques."""
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": self.get_cpu_usage(),
            "memory": self.get_memory_usage(),
            "gpu": self.get_gpu_usage(),
            "process": self.get_process_info()
        }

    def _monitor_loop(self, interval=1.0):
        """Boucle de surveillance en arrière-plan."""
        while self.monitoring:
            sample = self.collect_sample()
            self.data.append(sample)

            # Mettre à jour le fichier de log
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump({
                    "project_id": self.project_id,
                    "start_time": self.start_time,
                    "current_time": datetime.now().isoformat(),
                    "samples": self.data[-100:],  # Garder les 100 derniers échantillons
                    "summary": self.get_summary()
                }, f, indent=2, ensure_ascii=False)

            time.sleep(interval)

    def start(self, interval=1.0):
        """Démarrer la surveillance."""
        if self.monitoring:
            return
        self.monitoring = True
        self.start_time = datetime.now().isoformat()
        self.data = []
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.thread.start()
        print(f"[MONITOR] Surveillance démarrée pour {self.project_id}")

    def stop(self):
        """Arrêter la surveillance."""
        if not self.monitoring:
            return
        self.monitoring = False
        if self.thread:
            self.thread.join(timeout=2)
        print(f"[MONITOR] Surveillance arrêtée pour {self.project_id}")
        print(f"  Échantillons collectés : {len(self.data)}")
        print(f"  Résumé : {self.get_summary()}")

    def get_summary(self):
        """Retourne un résumé des métriques."""
        if not self.data:
            return {}

        cpu_values = [d["cpu_percent"] for d in self.data]
        mem_values = [d["memory"]["used_mb"] for d in self.data]

        # Calculer la durée correctement (désormais stockée comme datetime, pas str)
        duration = 0
        if self.start_time:
            try:
                start_dt = datetime.fromisoformat(self.start_time) if isinstance(self.start_time, str) else self.start_time
                duration = (datetime.now() - start_dt).total_seconds()
            except:
                duration = 0

        return {
            "duration_seconds": duration,
            "samples_count": len(self.data),
            "cpu_avg": round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else 0,
            "cpu_max": round(max(cpu_values), 1) if cpu_values else 0,
            "memory_avg_mb": round(sum(mem_values) / len(mem_values), 0) if mem_values else 0,
            "memory_max_mb": round(max(mem_values), 0) if mem_values else 0,
            "gpu_available": self.get_gpu_usage() is not None
        }

    def get_latest_metrics(self):
        """Retourne les dernières métriques."""
        if self.data:
            return self.data[-1]
        return self.collect_sample()


def format_metrics_html(monitor):
    """Génère un HTML pour afficher les métriques."""
    latest = monitor.get_latest_metrics()

    html = f"""
    <div class="monitor-bar">
        <div class="metric">
            <span class="label">CPU</span>
            <div class="progress-bar">
                <div class="progress" style="width: {latest['cpu_percent']:.0f}%"></div>
            </div>
            <span class="value">{latest['cpu_percent']:.0f}%</span>
        </div>
        <div class="metric">
            <span class="label">RAM</span>
            <div class="progress-bar">
                <div class="progress" style="width: {latest['memory']['percent']:.0f}%"></div>
            </div>
            <span class="value">{latest['memory']['used_mb']}/{latest['memory']['total_mb']} MB</span>
        </div>
    """

    if latest.get('gpu'):
        gpu = latest['gpu']
        html += f"""
        <div class="metric">
            <span class="label">GPU</span>
            <div class="progress-bar">
                <div class="progress" style="width: {gpu['load_percent']:.0f}%"></div>
            </div>
            <span class="value">{gpu['memory_used_mb']}/{gpu['memory_total_mb']} MB</span>
        </div>
        """

    html += "</div>"
    return html


def create_monitor_gui(monitor):
    """
    Crée une fenêtre GUI simple avec CustomTkinter pour afficher les métriques.
    """
    try:
        import customtkinter as ctk
    except ImportError:
        return None

    window = ctk.CTkToplevel()
    window.title("Monitoring - " + monitor.project_id)
    window.geometry("400x200")
    window.attributes("-topmost", True)

    # Frame principale
    frame = ctk.CTkFrame(window)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Labels
    labels = {}

    labels["cpu"] = ctk.CTkLabel(frame, text="CPU: -- %", font=("Segoe UI", 12, "bold"))
    labels["cpu"].pack(anchor="w", padx=10, pady=5)

    labels["ram"] = ctk.CTkLabel(frame, text="RAM: -- / -- MB", font=("Segoe UI", 12, "bold"))
    labels["ram"].pack(anchor="w", padx=10, pady=5)

    labels["gpu"] = ctk.CTkLabel(frame, text="GPU: -- %", font=("Segoe UI", 12, "bold"))
    labels["gpu"].pack(anchor="w", padx=10, pady=5)

    labels["process"] = ctk.CTkLabel(frame, text="Process: --", font=("Segoe UI", 10))
    labels["process"].pack(anchor="w", padx=10, pady=5)

    labels["duration"] = ctk.CTkLabel(frame, text="Durée: 0s", font=("Segoe UI", 10, "italic"))
    labels["duration"].pack(anchor="e", padx=10, pady=5)

    def update_metrics():
        if not monitor.monitoring:
            return

        latest = monitor.get_latest_metrics()

        labels["cpu"].configure(text=f"CPU: {latest['cpu_percent']:.1f}%")
        labels["ram"].configure(
            text=f"RAM: {latest['memory']['used_mb']} / {latest['memory']['total_mb']} MB"
        )

        gpu_text = "GPU: Non disponible"
        if latest.get('gpu'):
            gpu = latest['gpu']
            gpu_text = f"GPU: {gpu['load_percent']:.1f}% ({gpu['memory_used_mb']}/{gpu['memory_total_mb']} MB)"
        labels["gpu"].configure(text=gpu_text)

        if latest.get('process'):
            labels["process"].configure(
                text=f"Process: PID {latest['process']['pid']} - {latest['process']['name']} - {latest['process']['memory_mb']} MB"
            )

        if monitor.start_time:
            try:
                start_dt = datetime.fromisoformat(monitor.start_time) if isinstance(monitor.start_time, str) else monitor.start_time
                elapsed = (datetime.now() - start_dt).total_seconds()
            except:
                elapsed = 0
            labels["duration"].configure(text=f"Durée: {elapsed:.1f}s")

        window.after(500, update_metrics)

    update_metrics()
    return window
