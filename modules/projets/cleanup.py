# -*- coding: utf-8 -*-
"""
cleanup.py — Nettoyage des projets incomplets (conserver l'espace disque).

Un projet est considere INCOMPLET (donc candidat a la suppression) si TOUTES
les conditions suivantes sont reunies :
  1. c'est un vrai projet (project.json OU plan.json present) ;
  2. son statut n'est PAS termine/publie ;
  3. aucune video finale (.mp4) n'a ete produite dans export/ ;
  4. il n'a pas ete modifie depuis `seuil_jours` jours.

Le mode par defaut est DRY-RUN : on liste sans rien supprimer. La suppression
reelle exige `supprimer=True` et ne touche JAMAIS :
  - des dossiers hors de projects_dir (garde-fou de chemin) ;
  - des projets avec statut termine/publie ;
  - des projets ayant deja une video finale ;
  - des dossiers sans project.json/plan.json (ce ne sont pas des projets).

Usage CLI :
    python -m modules.projets.cleanup --seuil 7                 # apercu
    python -m modules.projets.cleanup --seuil 7 --supprimer     # suppression reelle
"""

import json
import os
import shutil
import time
import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths

STATUTS_TERMINES = {
    "termine", "publie", "terminé", "publié", "publiees", "publies",
    "done", "completed", "finished",
}


def _lire_statut(dossier: Path) -> str:
    """Statut lu dans project.json, en minuscules, ou ''."""
    try:
        p = dossier / "project.json"
        if not p.exists():
            return ""
        return str(json.loads(p.read_text(encoding="utf-8")).get("statut", "") or "").strip().lower()
    except Exception:
        return ""


def _est_marqueur_projet(dossier: Path) -> bool:
    """Vrai projet = project.json (video longues) ou plan.json (shorts)."""
    return (dossier / "project.json").exists() or (dossier / "plan.json").exists()


def _a_video_finale(dossier: Path) -> bool:
    """Une .mp4 a-t-elle ete produite sous export/ (video longues ou shorts) ?"""
    export = dossier / "export"
    if not export.exists():
        return False
    for p in export.rglob("*.mp4"):
        return True
    return False


def _dernier_modif(dossier: Path) -> float:
    """Timestamp du fichier/dossier le plus recent dans tout l'arbre."""
    maxi = 0.0
    try:
        maxi = max(maxi, os.path.getmtime(dossier))
    except Exception:
        pass
    for racine, sous_dossiers, fichiers in os.walk(dossier):
        for nom in fichiers:
            try:
                maxi = max(maxi, os.path.getmtime(os.path.join(racine, nom)))
            except Exception:
                pass
        for s in sous_dossiers:
            try:
                maxi = max(maxi, os.path.getmtime(os.path.join(racine, s)))
            except Exception:
                pass
    return maxi


def _taille_mo(dossier: Path) -> float:
    """Taille totale du dossier, en Mo."""
    total = 0
    for racine, _, fichiers in os.walk(dossier):
        for nom in fichiers:
            try:
                total += os.path.getsize(os.path.join(racine, nom))
            except Exception:
                pass
    return total / (1024 * 1024)


def analyser_projet(dossier: Path, seuil_jours: int) -> dict:
    """Analyse un dossier : est-ce un projet incomplet ? Rapporte tout."""
    if not _est_marqueur_projet(dossier):
        return {"chemin": str(dossier), "nom": dossier.name, "statut": "",
                "taille_mo": 0, "dernier_modif": "", "incomplet": False,
                "raison": "pas_un_projet"}

    statut = _lire_statut(dossier)
    dernier = _dernier_modif(dossier)
    rapport = {
        "chemin": str(dossier),
        "nom": dossier.name,
        "statut": statut,
        "taille_mo": round(_taille_mo(dossier), 1),
        "dernier_modif": datetime.fromtimestamp(dernier).strftime("%Y-%m-%d %H:%M") if dernier else "",
        "incomplet": False,
        "raison": "",
    }

    if statut in STATUTS_TERMINES:
        rapport["raison"] = "statut_termine"
        return rapport
    if _a_video_finale(dossier):
        rapport["raison"] = "video_presente"
        return rapport
    if (time.time() - dernier) < seuil_jours * 86400:
        rapport["raison"] = "modifie_recemment"
        return rapport

    rapport["incomplet"] = True
    rapport["raison"] = "incomplet_sans_video"
    return rapport


def nettoyer_projets_incomplets(projects_dir=None, seuil_jours: int = 7, supprimer: bool = False) -> dict:
    """
    Liste (dry-run) ou supprime les projets incomplets d'un dossier projets.

    projects_dir : chemin du dossier contenant les projets (defaut : paths.PROJECTS_DIR).
    seuil_jours  : age minimum (jours) sans modification pour etre candidat.
    supprimer    : False = apercu seul ; True = suppression reelle.
    """
    projects_dir = Path(projects_dir) if projects_dir else paths.PROJECTS_DIR
    projects_dir = projects_dir.resolve()
    if not projects_dir.exists() or not projects_dir.is_dir():
        return {"succes": False, "erreur": f"dossier projets introuvable : {projects_dir}"}

    rapports = []
    for dossier in sorted(projects_dir.iterdir()):
        if not dossier.is_dir():
            continue
        # Garde-fou : on ne travaille JAMAIS hors de projects_dir.
        if not str(dossier.resolve()).startswith(str(projects_dir)):
            continue
        rapports.append(analyser_projet(dossier, seuil_jours))

    incomplets = [r for r in rapports if r["incomplet"]]

    supprimes = []
    if supprimer:
        for r in incomplets:
            try:
                shutil.rmtree(r["chemin"])
                supprimes.append(r["nom"])
            except Exception as e:
                r["erreur_suppression"] = str(e)

    return {
        "succes": True,
        "mode": "suppression" if supprimer else "apercu",
        "seuil_jours": seuil_jours,
        "projets_analyses": len(rapports),
        "incomplets": incomplets,
        "total_incomplets": len(incomplets),
        "espace_recuperable_mo": round(sum(r["taille_mo"] for r in incomplets), 1),
        "supprimes": supprimes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Nettoyage des projets incomplets de StudioIA (conservation d'espace disque).")
    parser.add_argument("--projets", default=None,
                        help="Dossier des projets (defaut : paths.PROJECTS_DIR)")
    parser.add_argument("--seuil", type=int, default=7,
                        help="Age minimum sans modification, en jours (defaut: 7)")
    parser.add_argument("--supprimer", action="store_true",
                        help="Supprime reellement les projets incomplets (sinon apercu seul)")
    args = parser.parse_args()

    projects_dir = args.projets or str(paths.PROJECTS_DIR)
    resultat = nettoyer_projets_incomplets(projects_dir, seuil_jours=args.seuil, supprimer=args.supprimer)

    if not resultat["succes"]:
        print(f"[ERREUR] {resultat['erreur']}")
        sys.exit(1)

    print(f"\n=== Nettoyage des projets incomplets ({resultat['mode']}) ===")
    print(f"Dossier projets  : {projects_dir}")
    print(f"Projets analyses : {resultat['projets_analyses']}")
    print(f"Incomplets trouves : {resultat['total_incomplets']}")
    print(f"Espace recuperable : {resultat['espace_recuperable_mo']} Mo\n")

    for r in resultat["incomplets"]:
        print(f"  [X] {r['nom']:<55} {r['taille_mo']:>8} Mo   {r['dernier_modif']}")

    if not resultat["incomplets"]:
        print("  (aucun projet incomplet - rien a nettoyer)")
        return

    if resultat["supprimes"]:
        print(f"\nSupprimes : {', '.join(resultat['supprimes'])}")
    elif not args.supprimer:
        print(f"\nApercu seul : rien n'a ete supprime.")
        print(f"Pour supprimer vraiment : python -m modules.projets.cleanup --seuil {args.seuil} --supprimer")


if __name__ == "__main__":
    main()
