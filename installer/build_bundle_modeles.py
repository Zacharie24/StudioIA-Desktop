# -*- coding: utf-8 -*-
"""
installer/build_bundle_modeles.py — Construit le payload modèles (StudioIA-Models.exe).

Copie les manifests + blobs des modèles REQUIS (qwen2.5:7b + mistral) depuis
le dossier OLLAMA_MODELS local vers bundle-models/, au format exact attendu
par l'installateur (studioia.iss, section MODELS_ONLY) et par l'app
(core/services.importer_modele_depuis_bundle).

  bundle-models/
    manifests/registry.ollama.ai/library/<famille>/<tag>   (fichiers JSON)
    blobs/sha256-...                                        (poids + config + templates)

Usage :
  python installer/build_bundle_modeles.py
  python installer/build_bundle_modeles.py --source "C:\\Users\\X\\.ollama\\models" --cible bundle-models --modeles "qwen2.5:7b,mistral:latest"

Principes :
  * Copie seule — ne modifie JAMAIS la source.
  * Les blobs sont identifiés par leur sha256 (contenu-adressé) : on saute ceux
    déjà présents à la cible (sans risque).
  * Vérification finale : chaque blob référencé par chaque manifest doit exister
    à la cible ; on peut ensuite valider avec `ollama list` en pointant OLLAMA_MODELS
    sur le bundle.
"""

import json
import shutil
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CIBLE_DEFAUT = RACINE / "bundle-models"
SOURCE_DEFAUT = Path.home() / ".ollama" / "models"
MODELES_REQUIS = ["qwen2.5:7b", "mistral:latest"]


def _humain(octets: int) -> str:
    for unite, div in (("Go", 1 << 30), ("Mo", 1 << 20), ("Ko", 1 << 10)):
        if octets >= div:
            return f"{octets/div:.1f} {unite}"
    return f"{octets} o"


def _tous_digests(manifest: dict) -> list:
    """Tous les digests référencés par un manifest (config + layers)."""
    digests = []
    cfg = manifest.get("config") or {}
    if cfg.get("digest"):
        digests.append(cfg["digest"])
    for lyr in manifest.get("layers") or []:
        if lyr.get("digest"):
            digests.append(lyr["digest"])
    return digests


def construire_bundle(source, cible, modeles):
    src = Path(source)
    cible = Path(cible)
    if not (src / "manifests").exists():
        raise SystemExit(f"Source invalide (pas de manifests/) : {src}")

    cible.mkdir(parents=True, exist_ok=True)
    blobs_dir = cible / "blobs"
    blobs_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    total_octets = 0
    total_blobs = 0
    rapports = []

    for spec in modeles:
        famille, _, tag = spec.partition(":")
        tag = tag or "latest"
        manifest_rel = Path("manifests") / "registry.ollama.ai" / "library" / famille / tag
        manifest_src = src / manifest_rel
        if not manifest_src.exists():
            rapports.append(f"  ✗ manifest introuvable : {spec} ({manifest_src})")
            continue
        try:
            data = json.loads(manifest_src.read_text(encoding="utf-8"))
        except Exception as e:
            rapports.append(f"  ✗ manifest illisible {spec} : {e}")
            continue

        # 1) copie du manifest (petit, on l'écrit toujours)
        manifest_dst = cible / manifest_rel
        manifest_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_src, manifest_dst)
        nb = 0
        oct = 0
        # 2) copie des blobs référencés (saut si déjà présent — contenu-adressé)
        #    Le manifest utilise sha256:<hex>, le fichier est nommé sha256-<hex>.
        for digest in _tous_digests(data):
            nom = digest.replace(":", "-")
            b_src = src / "blobs" / nom
            b_dst = blobs_dir / nom
            if not b_src.exists():
                rapports.append(f"  ✗ blob manquant à la source : {digest}")
                continue
            if b_dst.exists():
                continue
            shutil.copy2(b_src, b_dst)
            nb += 1
            oct += b_src.stat().st_size
            total_blobs += 1
            total_octets += b_src.stat().st_size
        rapports.append(f"  ✓ {spec} : {nb} blob(s) copiés, {_humain(oct)}")

    duree = time.time() - t0
    print(f"Source : {src}")
    print(f"Cible  : {cible}")
    print(f"{len(modeles)} modèle(s), {total_blobs} blob(s) copiés, "
          f"{_humain(total_octets)} en {int(duree)} s\n")
    print("\n".join(rapports))

    # --- Vérification finale : tous les blobs référencés présents à la cible
    manquants = []
    for spec in modeles:
        famille, _, tag = spec.partition(":")
        tag = tag or "latest"
        mp = cible / "manifests" / "registry.ollama.ai" / "library" / famille / tag
        if not mp.exists():
            manquants.append(f"{spec} (manifest absent)")
            continue
        try:
            data = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as e:
            manquants.append(f"{spec} (manifest illisible : {e})")
            continue
        for digest in _tous_digests(data):
            if not (blobs_dir / digest.replace(":", "-")).exists():
                manquants.append(f"{spec} (blob {digest[:16]}… manquant)")
    if manquants:
        print("\n⚠ VERIFICATION : éléments manquants :")
        print("\n".join("  " + m for m in manquants))
        return 1
    taille = sum(p.stat().st_size for p in blobs_dir.rglob("*") if p.is_file())
    print(f"\n✓ Bundle complet : {_humain(taille)} de blobs, tous les manifests OK.")
    print("  Valider ensuite : OLLAMA_MODELS=<bundle> ollama list")
    return 0


def _cli():
    import argparse
    # stdout Windows = cp1252 par défaut : passe en UTF-8 (les ✓/✗ cassent sinon).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Construit le payload modèles StudioIA")
    ap.add_argument("--source", default=str(SOURCE_DEFAUT),
                    help="dossier OLLAMA_MODELS source")
    ap.add_argument("--cible", default=str(CIBLE_DEFAUT),
                    help="dossier bundle-models de destination")
    ap.add_argument("--modeles", default=",".join(MODELES_REQUIS),
                    help="modèles à inclure (séparés par des virgules)")
    args = ap.parse_args()
    modeles = [m.strip() for m in args.modeles.split(",") if m.strip()]
    return construire_bundle(args.source, args.cible, modeles)


if __name__ == "__main__":
    sys.exit(_cli())
