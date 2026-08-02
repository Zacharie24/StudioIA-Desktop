# -*- coding: utf-8 -*-
"""
core/importer.py — Migration des données réelles vers StudioIA Desktop.

Copie depuis une ancienne installation (ex. C:\\StudioIA-Next) vers les
données utilisateur (%USERPROFILE%\\StudioIA) :

  config.json    → config utilisateur (clés API, réglages, human_touch,
                   chaine_cible), chemins absolus PURGÉS (résolus par paths.py)
  api_keys.json  → DATA_DIR/api_keys.json (pexels_key, unsplash_key)
  data\          → DATA_DIR\data (audits, diagnostics, corrections, oauth…)
  logs\          → DATA_DIR\logs
  projects\      → DATA_DIR\projects  (VOLUMINEUX — à cocher)

Principes :
  * Jamais de suppression à la source (copie seule).
  * Jamais d'écrasement d'un fichier déjà présent à la cible (résumable,
    respecte ce que l'utilisateur a pu resaisir dans la nouvelle app).
  * Les soundfonts ComposIA ne sont PAS copiés : l'app les embarque dans son
    dossier (modules/audio/composia.py les lit depuis COMPOSIA_DIR).
  * Progression accessible en continu (état global) et depuis la CLI.

Usage CLI :
  python core/importer.py <source> <cible> [--projets]
  # source = dossier racine de l'ancienne install (ex C:\\StudioIA-Next)
  # cible  = %USERPROFILE%\\StudioIA (DATA_DIR de l'app installée)
"""

import json
import shutil
import sys
import time
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_rac))
    from core import paths

# --- État global de l'import (lu par GET /api/setup/importer/etat) ----------
ETAT = {
    "actif": False,          # un import est en cours
    "termine": False,        # l'import (réussi ou non) est fini
    "etape": "",             # section en cours : config | api_keys | data | logs | projets
    "source": "",            # dossier source choisi
    "cible": "",             # dossier de destination (DATA_DIR)
    "copies": 0,             # fichiers copiés
    "ignores": 0,            # fichiers déjà présents à la cible (non réécrits)
    "erreurs": 0,            # fichiers en échec
    "fichiers_total": 0,     # fichiers à copier (toutes sections)
    "fichiers_faits": 0,     # fichiers copiés
    "octets_total": 0,       # octets à copier (toutes sections)
    "octets_faits": 0,       # octets copiés
    "message": "",           # message humain courant
    "rapport": "",           # résumé final
    "erreur": None,          # erreur fatale éventuelle
}

# Clés de config migrées, à PURGER (chemins absolus résolus par paths.py).
CLES_PURGEES = ("projects_path", "assets_path", "music_path")

# Sections (dossier source → dossier cible).
SECTIONS = ("config", "api_keys", "data", "logs", "projets")


# --- Helpers ----------------------------------------------------------------
def _taille_dossier(chem: Path) -> int:
    """Taille totale (octets) d'un dossier, fichier ou dossier vide."""
    if chem.is_file():
        return chem.stat().st_size
    if chem.is_dir():
        try:
            return sum(p.stat().st_size for p in chem.rglob("*") if p.is_file())
        except Exception:
            return 0
    return 0


def _nb_fichiers(chem: Path) -> int:
    if chem.is_file():
        return 1
    if chem.is_dir():
        try:
            return sum(1 for p in chem.rglob("*") if p.is_file())
        except Exception:
            return 0
    return 0


def _humain(octets: int) -> str:
    """Formate une taille en Go/Mo/Ko lisible."""
    for unite, div in (("Go", 1 << 30), ("Mo", 1 << 20), ("Ko", 1 << 10)):
        if octets >= div:
            return f"{octets/div:.1f} {unite}"
    return f"{octets} o"


# --- Analyse (avant confirmation) --------------------------------------------
def analyser(source):
    """État de la source et tailles par section, sans copier quoi que ce soit."""
    src = Path(source)
    if not src.exists():
        return {"source": str(src), "existe": False, "erreur": "Source introuvable"}
    sections = {}
    for sec in SECTIONS:
        chemin = {
            "config": src / "config.json",
            "api_keys": src / "api_keys.json",
            "data": src / "data",
            "logs": src / "logs",
            "projets": src / "projects",
        }[sec]
        if chemin.exists():
            sections[sec] = {
                "octets": _taille_dossier(chemin),
                "fichiers": _nb_fichiers(chemin),
            }
    return {
        "source": str(src),
        "existe": True,
        "cible": str(paths.DATA_DIR),
        "cible_existe": paths.DATA_DIR.exists(),
        "sections": sections,
        "total_octets": sum(s["octets"] for s in sections.values()),
    }


# --- Copie récursive sans écrasement -----------------------------------------
def _copier_section(src_dir: Path, dst_dir: Path, etape: str):
    """Copie src_dir → dst_dir (fichiers déjà présents ignorés), en progression."""
    ETAT["etape"] = etape
    ETAT["message"] = f"Copie de {etape}…"
    ETAT["octets_total"] += _taille_dossier(src_dir)
    ETAT["fichiers_total"] += _nb_fichiers(src_dir)

    def _un(s: Path, d: Path):
        if s.is_dir():
            d.mkdir(parents=True, exist_ok=True)
            for e in s.iterdir():
                _un(e, d / e.name)
        else:
            if d.exists():
                ETAT["ignores"] += 1
                return
            d.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(s, d)
            except Exception as e:
                ETAT["erreurs"] += 1
                ETAT["message"] = f"Erreur sur {s.name} : {e}"
                return
            sz = s.stat().st_size
            ETAT["copies"] += 1
            ETAT["fichiers_faits"] += 1
            ETAT["octets_faits"] += sz

    dst_dir.mkdir(parents=True, exist_ok=True)
    for e in src_dir.iterdir():
        _un(e, dst_dir / e.name)


def _migrer_config(src: Path, cible: Path):
    """Fusionne la config source dans la config cible (source prioritaire),
    en PURGEANT les chemins absolus. Ne crée jamais un écrasement destructeur."""
    src_cfg = paths.lire_json(src / "config.json")
    if not src_cfg:
        ETAT["message"] = "Aucune config.json à la source"
        return 0
    for k in CLES_PURGEES:
        src_cfg.pop(k, None)

    cible_cfg = paths.lire_json(cible / "config.json")
    avant = len(cible_cfg)
    cible_cfg.update(src_cfg)  # la source apporte ses clés réelles ; la cible garde les siennes
    cible.mkdir(parents=True, exist_ok=True)
    paths.ecrire_json(cible / "config.json", cible_cfg)
    ETAT["copies"] += 1
    ETAT["message"] = "Config migrée (clés API + réglages)"
    return len(src_cfg)


# --- Import principal ---------------------------------------------------------
def importer(source, cible=None, sections=("config", "api_keys", "data", "logs"),
             en_fond=True):
    """Lance la migration. Retourne immédiatement si en_fond=True (thread),
    sinon exécute en synchronie (CLI)."""
    if en_fond:
        import threading
        threading.Thread(target=_executer, args=(source, cible, sections),
                         daemon=True).start()
        return {"ok": True, "message": "Import lancé en arrière-plan"}
    return _executer(source, cible, sections)


def _executer(source, cible, sections):
    ETAT.update({
        "actif": True, "termine": False, "erreur": None, "rapport": "",
        "etape": "", "copies": 0, "ignores": 0, "erreurs": 0,
        "fichiers_total": 0, "fichiers_faits": 0,
        "octets_total": 0, "octets_faits": 0, "message": "Démarrage…",
    })
    ETAT["source"] = str(source)
    ETAT["cible"] = str(cible if cible else paths.DATA_DIR)
    t0 = time.time()
    try:
        src = Path(source)
        if not src.exists():
            raise ValueError(f"Source introuvable : {src}")
        dst = Path(ETAT["cible"])
        if src.resolve() == dst.resolve():
            raise ValueError("La source et la cible sont identiques.")

        # 1) config
        if "config" in sections:
            _migrer_config(src, dst)

        # 2) api_keys.json (ne PAS écraser une clé déjà saisie à la cible)
        if "api_keys" in sections:
            ETAT["etape"] = "api_keys"
            src_ak = src / "api_keys.json"
            if src_ak.exists():
                dst_ak = dst / "api_keys.json"
                if dst_ak.exists():
                    ETAT["ignores"] += 1
                    ETAT["message"] = "api_keys.json déjà présent (non réécrit)"
                else:
                    dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_ak, dst_ak)
                    ETAT["copies"] += 1
                    ETAT["message"] = "api_keys.json copié"
            else:
                ETAT["message"] = "Pas d'api_keys.json à la source"

        # 3) data / logs / projets
        for sec, dossier in (("data", "data"), ("logs", "logs"), ("projets", "projects")):
            if sec in sections:
                src_dir = src / dossier
                if src_dir.exists():
                    _copier_section(src_dir, dst / dossier, sec)
                else:
                    ETAT["message"] = f"Pas de dossier {dossier} à la source"

        duree = time.time() - t0
        ETAT["rapport"] = (
            f"{ETAT['copies']} fichier(s) copié(s), {ETAT['ignores']} déjà présent(s), "
            f"{ETAT['erreurs']} erreur(s), en {int(duree)} s. "
            f"({_humain(ETAT['octets_faits'])} copiés)"
        )
        ETAT["message"] = "Import terminé."
        ETAT["erreur"] = None
    except Exception as e:
        ETAT["erreur"] = str(e)
        ETAT["message"] = f"Import interrompu : {e}"
    finally:
        ETAT["actif"] = False
        ETAT["termine"] = True
    return ETAT


# --- CLI ----------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    source = sys.argv[1]
    cible = sys.argv[2]
    avec_projets = "--projets" in sys.argv
    sections = ("config", "api_keys", "data", "logs") + (("projets",) if avec_projets else ())

    a = analyser(source)
    print(f"Source  : {a.get('source')}  (existe : {a.get('existe')})")
    if a.get("existe"):
        for sec, inf in (a.get("sections") or {}).items():
            print(f"  {sec:<8} {_humain(inf['octets']):>10}  {inf['fichiers']:>7} fichiers")
    print(f"Cible   : {a.get('cible')}")
    print("Sections retenues :", ", ".join(sections))
    print("Lancement…")

    res = importer(source, cible, sections, en_fond=False)
    print("\n" + res.get("rapport", ""))
    if res.get("erreur"):
        print("ERREUR :", res["erreur"])
        sys.exit(1)
