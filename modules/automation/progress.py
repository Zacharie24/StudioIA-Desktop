# -*- coding: utf-8 -*-
"""
progress.py — Suivi de progression du pipeline automatique

Le pipeline (ou generate_script) ecrit son avancement ici a chaque etape.
L'interface web lit cet etat via /api/automation/progress (polling).

Un seul pipeline peut tourner a la fois (verrou + flag en_cours).
"""

import threading
import time

_lock = threading.Lock()
_etat = {
    "en_cours": False,
    "demarre_le": None,
    "etape": "",
    "message": "",
    "pct": 0,
    "detail": "",
    "etapes": [],
    "erreur": None,
    "resultat": None,
    "attente_humaine": False,
}


def init():
    """Reinitialise l'etat pour un nouveau lancement."""
    with _lock:
        _etat["en_cours"] = True
        _etat["demarre_le"] = time.time()
        _etat["etape"] = "demarrage"
        _etat["message"] = "Demarrage du pipeline..."
        _etat["pct"] = 0
        _etat["detail"] = ""
        _etat["etapes"] = []
        _etat["erreur"] = None
        _etat["resultat"] = None
        _etat["attente_humaine"] = False


def etape(nom, message, pct, detail=""):
    """Positionne l'etape en cours et ajoute un marqueur si inconnu."""
    with _lock:
        _etat["etape"] = nom
        _etat["message"] = message
        _etat["pct"] = max(0, min(100, pct))
        _etat["detail"] = detail
        if not any(e["nom"] == nom and e["statut"] == "en_cours" for e in _etat["etapes"]):
            _etat["etapes"].append({
                "nom": nom, "message": message, "pct": _etat["pct"], "statut": "en_cours"
            })


def terminer_etape(nom, statut="termine", message=""):
    """Marque une etape comme terminee (ou en erreur)."""
    with _lock:
        for e in _etat["etapes"]:
            if e["nom"] == nom:
                e["statut"] = statut
                if message:
                    e["message"] = message


def attendre_humaine(message, pct):
    """Pipeline en attente de l'enregistrement de la voix (touche humaine)."""
    with _lock:
        _etat["attente_humaine"] = True
        _etat["etape"] = "intro"
        _etat["message"] = message
        _etat["pct"] = pct
        _etat["detail"] = "Enregistre ta voix dans la page /human-touch"


def reprendre(message="", pct=None):
    """L'enregistrement a ete detecte : on quitte l'attente."""
    with _lock:
        _etat["attente_humaine"] = False
        if message:
            _etat["message"] = message
        if pct is not None:
            _etat["pct"] = pct


def fin(erreur=None, resultat=None):
    """Pipeline termine (succes ou erreur)."""
    with _lock:
        _etat["en_cours"] = False
        _etat["erreur"] = erreur
        _etat["resultat"] = resultat
        if erreur:
            _etat["pct"] = min(_etat["pct"], 99)
            _etat["message"] = f"Erreur: {erreur}"


def get():
    """Copie de l'etat courant (thread-safe)."""
    with _lock:
        return dict(_etat)
