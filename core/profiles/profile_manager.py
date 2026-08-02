# -*- coding: utf-8 -*-
"""
profile_manager.py — Gestionnaire de profils de contenu

Fonctionnalités :
- Lister, charger, créer, modifier des profils
- Chaque profil contient ses règles éditoriales, son vocabulaire, sa structure
- Les profils sont stockés dans core/profiles/profiles/
- Le profil "prière" est le premier profil pré-installé

Utilisation :
    from core.profiles.profile_manager import ProfileManager

    pm = ProfileManager()
    profil = pm.charger("prayer")
    regles = profil.get("regles_generales", [])
"""

import json
import os
import shutil
from pathlib import Path

# Chemin où sont stockés les profils
PROFILES_DIR = Path(__file__).parent / "profiles"

# Fichier de configuration du profil actif
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "active_profile.json"


def log(msg):
    print(f"[PROFILES] {msg}")


class ProfileManager:
    """
    Gestionnaire central des profils de contenu.

    Usage:
        pm = ProfileManager()
        pm.lister_profils()
        profil = pm.charger("prayer")
        pm.definir_profil_actif("prayer")
    """

    def __init__(self, config_dir=None):
        self._profiles_cache = None

    # ============================================================
    # LISTE DES PROFILS
    # ============================================================

    def lister_profils(self):
        """
        Liste tous les profils disponibles

        Returns:
            list[dict]: liste des manifestes des profils
        """
        if self._profiles_cache is not None:
            return self._profiles_cache

        profils = []

        if not PROFILES_DIR.exists():
            log(f"Dossier des profils introuvable: {PROFILES_DIR}")
            return profils

        for dossier in PROFILES_DIR.iterdir():
            if not dossier.is_dir():
                continue

            manifest_path = dossier / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    manifest["_dossier"] = str(dossier)
                    profils.append(manifest)
            except (json.JSONDecodeError, OSError) as e:
                log(f"Erreur chargement manifeste {dossier.name}: {e}")

        # Trier par nom
        profils.sort(key=lambda p: p.get("name", ""))
        self._profiles_cache = profils
        return profils

    def obtenir_profil(self, profil_id):
        """
        Trouve un profil par son ID

        Args:
            profil_id: l'identifiant du profil ("prayer", "default", ...)

        Returns:
            dict or None: le manifeste du profil ou None si introuvable
        """
        profils = self.lister_profils()
        for p in profils:
            if p.get("id") == profil_id:
                return p
        return None

    # ============================================================
    # CHARGEMENT D'UN PROFIL
    # ============================================================

    def charger(self, profil_id):
        """
        Charge les règles complètes d'un profil

        Args:
            profil_id: identifiant du profil

        Returns:
            dict: {
                "manifest": {...},
                "rules": {...},
                "toutes_regles": [...]   # règles fusionnées pour prompts
            }
            ou None si le profil n'existe pas
        """
        profil = self.obtenir_profil(profil_id)
        if not profil:
            log(f"Profil '{profil_id}' introuvable")
            return None

        dossier = Path(profil["_dossier"])
        rules_path = dossier / "rules.json"

        rules = {}
        if rules_path.exists():
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log(f"Erreur chargement règles {profil_id}: {e}")

        # Fusionner toutes les règles textuelles pour les prompts
        toutes_regles = self._fusionner_regles(rules, profil)

        return {
            "manifest": profil,
            "rules": rules,
            "toutes_regles": toutes_regles,
            "id": profil_id,
            "dossier": str(dossier)
        }

    def _fusionner_regles(self, rules, manifest):
        """
        Fusionne toutes les règles en une liste unique de consignes
        Utilisé pour construire les prompts IA
        """
        fusion = []

        # Règles listées dans manifest.regles_incluses
        inclusions = manifest.get("regles_incluses", [])
        for cle in inclusions:
            valeurs = rules.get(cle, [])
            if isinstance(valeurs, list):
                fusion.extend(valeurs)
            elif isinstance(valeurs, dict):
                for k, v in valeurs.items():
                    fusion.append(f"{k}: {v}")

        # Structure du script
        structure = rules.get("structure_script", {})
        if structure:
            fusion.append("--- Structure du script ---")
            for section, desc in structure.items():
                fusion.append(f"- {section}: {desc}")

        return fusion

    # ============================================================
    # PROFIL ACTIF
    # ============================================================

    def get_profil_actif(self):
        """
        Récupère l'ID du profil actif depuis la configuration

        Returns:
            str: ID du profil actif ("prayer" par défaut)
        """
        # D'abord essayer depuis le fichier de config dédié
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg.get("profil_actif", "prayer")
            except (json.JSONDecodeError, OSError):
                pass

        # Fallback: config.json du projet
        try:
            config_main = Path(__file__).parent.parent.parent / "config.json"
            if config_main.exists():
                with open(config_main, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    return cfg.get("profil_actif", "prayer")
        except (json.JSONDecodeError, OSError):
            pass

        return "prayer"

    def definir_profil_actif(self, profil_id):
        """
        Définit le profil actif

        Args:
            profil_id: identifiant du profil

        Returns:
            bool: True si réussi
        """
        # Vérifier que le profil existe
        profil = self.obtenir_profil(profil_id)
        if not profil:
            log(f"Impossible de définir '{profil_id}' comme actif : profil introuvable")
            return False

        # Sauvegarder dans le fichier de config
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"profil_actif": profil_id}, f, ensure_ascii=False, indent=2)

        log(f"Profil actif : {profil_id} ({profil.get('name', profil_id)})")
        return True

    def charger_profil_actif(self):
        """
        Raccourci : charge le profil actif directement

        Returns:
            dict: le profil complet (manifest + rules) ou None
        """
        profil_id = self.get_profil_actif()
        return self.charger(profil_id)

    # ============================================================
    # CRÉATION ET GESTION
    # ============================================================

    def creer_profil(self, profil_id, nom, description, base="default"):
        """
        Crée un nouveau profil à partir d'un modèle existant

        Args:
            profil_id: identifiant unique (ex: "histoire")
            nom: nom affiché (ex: "Histoires et récits")
            description: description courte
            base: profil à copier comme base ("default" par défaut)

        Returns:
            bool: True si le profil a été créé
        """
        # Vérifier que l'ID n'existe pas déjà
        if self.obtenir_profil(profil_id):
            log(f"Un profil avec l'ID '{profil_id}' existe déjà")
            return False

        # Vérifier que le modèle existe
        profil_base = self.obtenir_profil(base)
        if not profil_base:
            log(f"Profil de base '{base}' introuvable")
            return False

        dossier_base = Path(profil_base["_dossier"])
        dossier_new = PROFILES_DIR / profil_id

        if dossier_new.exists():
            log(f"Le dossier '{profil_id}' existe déjà")
            return False

        # Copier le profil de base
        shutil.copytree(dossier_base, dossier_new)

        # Modifier le manifest
        manifest_path = dossier_new / "manifest.json"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            manifest = {}

        manifest["id"] = profil_id
        manifest["name"] = nom
        manifest["description"] = description
        manifest["version"] = "1.0.0"
        manifest["type"] = "contenu"
        manifest["date_creation"] = "2026-07-30"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # Invalider le cache
        self._profiles_cache = None

        log(f"Profil '{profil_id}' créé depuis '{base}'")
        return True

    def mettre_a_jour_regles(self, profil_id, nouvelles_regles):
        """
        Met à jour les règles d'un profil

        Args:
            profil_id: identifiant du profil
            nouvelles_regles: dict partiel des règles à mettre à jour

        Returns:
            bool: True si réussi
        """
        profil = self.obtenir_profil(profil_id)
        if not profil:
            return False

        dossier = Path(profil["_dossier"])
        rules_path = dossier / "rules.json"

        # Charger les règles existantes
        rules = {}
        if rules_path.exists():
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
            except (json.JSONDecodeError, OSError):
                rules = {}

        # Fusionner
        rules.update(nouvelles_regles)

        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)

        log(f"Règles mises à jour pour '{profil_id}'")
        return True

    def supprimer_profil(self, profil_id):
        """
        Supprime un profil (sauf 'default' et 'prayer')

        Args:
            profil_id: identifiant du profil

        Returns:
            bool: True si supprimé
        """
        if profil_id in ("default", "prayer"):
            log(f"Impossible de supprimer le profil '{profil_id}' : protégé")
            return False

        profil = self.obtenir_profil(profil_id)
        if not profil:
            return False

        dossier = Path(profil["_dossier"])
        shutil.rmtree(dossier, ignore_errors=True)
        self._profiles_cache = None

        log(f"Profil '{profil_id}' supprimé")
        return True


# ============================================================
# FONCTIONS DE RACCOURCI
# ============================================================

_manager_instance = None


def get_manager():
    """Retourne l'instance unique du ProfileManager"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ProfileManager()
    return _manager_instance


def lister():
    return get_manager().lister_profils()


def charger(profil_id):
    return get_manager().charger(profil_id)


def profil_actif():
    return get_manager().charger_profil_actif()


def definir_actif(profil_id):
    return get_manager().definir_profil_actif(profil_id)


if __name__ == "__main__":
    # Test
    pm = ProfileManager()

    print("=== Profils disponibles ===")
    for p in pm.lister_profils():
        print(f"  [{p['id']}] {p['name']} — {p.get('description', '')[:60]}")

    print(f"\nProfil actif : {pm.get_profil_actif()}")

    profil = pm.charger_profil_actif()
    if profil:
        print(f"\nRègles chargées : {len(profil['toutes_regles'])} consignes")
        for r in profil['toutes_regles'][:5]:
            print(f"  • {r[:80]}")
        print(f"  ... et {len(profil['toutes_regles'])-5} autres")
