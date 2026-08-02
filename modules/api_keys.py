# -*- coding: utf-8 -*-
"""
api_keys.py — Clés API des services d'images (Pexels, Unsplash).

Les clés vivent dans api_keys.json. En mode installé, la version migrée ou
saisie par l'utilisateur est lue depuis DATA_DIR (isolée du dossier d'app,
conservée pendant les MAJ) ; sinon on retombe sur celle embarquée.
"""

import json
from pathlib import Path

try:
    from core import paths
except ImportError:
    import sys as _sys
    _rac = Path(__file__).resolve().parent.parent
    _sys.path.insert(0, str(_rac))
    from core import paths


def get_api_keys():
    """Charge les clés API depuis api_keys.json.

    Priorité : DATA_DIR/api_keys.json (installé, migré) puis api_keys.json
    embarqué (racine app). Retourne {} si aucun fichier lisible.
    """
    for base in (paths.chemin_data("api_keys.json"), paths.chemin_app("api_keys.json")):
        p = Path(base)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return {}


_KEYS = get_api_keys()

PEXELS_KEY = _KEYS.get("pexels_key", "")
UNSPLASH_KEY = _KEYS.get("unsplash_key", "")
