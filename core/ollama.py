# -*- coding: utf-8 -*-
"""
core/ollama.py — Helpers centralisés pour Ollama.

Centralise l'accès à Ollama (base URL, liste des modèles, santé) afin que
les modules du brain, le diagnostic et le service de gestion (core/services)
raisonnent tous sur la même cible. Aucun module ne doit coder en dur
"http://localhost:11434" — il utilise ici.

Le port peut être surchargé via la variable d'environnement OLLAMA_PORT
(rarement nécessaire ; défaut 11434).
"""

import os
import time
import requests

# --- Base URL -----------------------------------------------------------------
_OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1")
OLLAMA_BASE = f"http://{OLLAMA_HOST}:{_OLLAMA_PORT}"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"
OLLAMA_GENERATE = f"{OLLAMA_BASE}/api/generate"

# --- Modèles attendus (défauts embeddings/LLM du projet)
MODELE_PRIORITE = ["qwen2.5:7b", "mistral:latest", "qwen2.5-coder:3b", "qwen2.5:latest"]


def test_connexion(timeout=5):
    """True si /api/tags répond 200 (Ollama actif)."""
    try:
        r = requests.get(OLLAMA_TAGS, timeout=timeout)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


def modeles_disponibles(timeout=5):
    """Liste des noms de modèles (vidés) installés chez Ollama."""
    try:
        r = requests.get(OLLAMA_TAGS, timeout=timeout)
        if r.status_code != 200:
            return []
        return [m["name"] for m in r.json().get("models", [])]
    except requests.exceptions.RequestException:
        return []


def modele_present(nom, timeout=5):
    """True si au moins un modèle installé matche le nom demandé."""
    disponibles = modeles_disponibles(timeout)
    return any(d == nom or d.startswith(nom.split(":")[0] + ":") for d in disponibles)


def etat_ollama():
    """État structuré : actif + modèles trouvés."""
    actif = test_connexion()
    modeles = modeles_disponibles() if actif else []
    return {
        "actif": actif,
        "modeles": modeles,
        "modele_utilisable": choisir_meilleur_modele() if actif else None,
    }


def choisir_meilleur_modele(timeout=5):
    """Renvoie le premier modèle de MODELE_PRIORITE installé, sinon None."""
    disponibles = set(modeles_disponibles(timeout))
    for nom in MODELE_PRIORITE:
        if any(m == nom or m.startswith(nom.split(":")[0] + ":") for m in disponibles):
            return nom
    return None


def appeler_ollama(prompt, modele=None, temperature=0.8, nommax_tokens=4096, timeout=300):
    """
    Appel génératif Ollama (compatible avec l'usage du brain).
    Renvoie (reponse, modele) ou lève RequestException si injoignable.
    """
    if modele is None:
        modele = choisir_meilleur_modele()
    if modele is None:
        raise RuntimeError("Aucun modèle Ollama disponible")

    payload = {
        "model": modele,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": nommax_tokens,
        },
    }
    r = requests.post(OLLAMA_GENERATE, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", ""), modele


def attendre_serveur(timeout=15, intervalle=0.5):
    """Attend qu'Ollama réponde (utile juste après le lancement du service)."""
    fin = time.time() + timeout
    while time.time() < fin:
        if test_connexion():
            return True
        time.sleep(intervalle)
    return False