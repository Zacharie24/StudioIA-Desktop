# -*- coding: utf-8 -*-
"""
ia_online.py — Génération IA en ligne via Hugging Face (gratuit)

Fonctionnalités :
- Utilise Hugging Face Inference API pour des modèles de qualité
- Fallback automatique vers local si pas d'internet
- Configurable via config.json (ia_provider: "local" ou "huggingface")
"""

import sys
import json
import requests
from pathlib import Path

try:
    from core import paths
except ImportError:
    _rac = Path(__file__).resolve().parent
    while not (_rac / "core" / "paths.py").exists() and _rac.parent != _rac:
        _rac = _rac.parent
    sys.path.insert(0, str(_rac))
    from core import paths


# ============================================================
# Configuration
# ============================================================

HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/{model}"
HUGGINGFACE_MODELS = {
    "mistral": "mistralai/Mistral-7B-Instruct-v0.3",
    "llama": "meta-llama/Llama-3.2-3B-Instruct",
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
    "gemma": "google/gemma-2-9b-it",
}


def get_huggingface_key():
    """Récupère la clé Hugging Face depuis config ou environnement"""
    # D'abord essayer depuis config.json
    try:
        config_path = paths.config_path()
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
                if config.get("huggingface_api_key"):
                    return config["huggingface_api_key"]
    except:
        pass

    # Ensuite essayer depuis un fichier dédié
    try:
        keys_path = paths.chemin_app("modules", "api_keys.py")
        if keys_path.exists():
            paths.ajouter_modules_au_path()
            import api_keys
            if hasattr(api_keys, "HUGGINGFACE_KEY"):
                return api_keys.HUGGINGFACE_KEY
    except:
        pass

    return None


def estimator_tokens(text):
    """Estime le nombre de tokens (1 token ≈ 4 caractères en français)"""
    return len(text) // 4


def generer_avec_huggingface(prompt, model="mistral", max_tokens=2048, temperature=0.7):
    """
    Génère du texte avec Hugging Face Inference API
    """
    api_key = get_huggingface_key()
    if not api_key:
        return None, "Pas de clé Hugging Face configurée"

    # Vérifier la longueur du prompt
    tokens = estimator_tokens(prompt)
    if tokens > max_tokens:
        return None, f"Prompt trop long: {tokens} tokens"

    huggingface_model = HUGGINGFACE_MODELS.get(model, HUGGINGFACE_MODELS["mistral"])
    url = f"https://api-inference.huggingface.co/models/{huggingface_model}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "return_full_text": False,
            "do_sample": True
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()

        # HuggingFace retourne souvent une liste
        if isinstance(result, list):
            result = result[0]

        texte = result.get("generated_text", "")
        return texte, None

    except requests.exceptions.Timeout:
        return None, "Timeout Hugging Face"
    except requests.exceptions.ConnectionError:
        return None, "Erreur de connexion Hugging Face"
    except Exception as e:
        return None, str(e)


def generer_prompt_online(prompt, model="mistral", provider="huggingface"):
    """
    Génère du texte avec le fournisseur spécifié
    Fallback vers local si pas d'internet ou erreur
    """
    connexion = est_connecte_internet()

    if not connexion:
        return None, False, "Pas d'internet"

    if provider == "huggingface":
        texte, erreur = generer_avec_huggingface(prompt, model=model)

        if texte:
            return texte, True, None
        else:
            return None, False, erreur

    return None, False, f"Provider inconnu: {provider}"


def est_connecte_internet(host="8.8.8.8", port=53, timeout=3):
    """
    Vérifie si une connexion internet est disponible
    """
    try:
        import socket
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


# ============================================================
# Usage en ligne de commande
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Génération IA en ligne via Hugging Face"
    )
    parser.add_argument("prompt", help="Prompt à générer")
    parser.add_argument("--model", default="mistral", choices=["mistral", "llama", "qwen", "gemma"],
                       help="Modèle à utiliser")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")

    args = parser.parse_args()

    print(f"[IA Online] Prompt: {args.prompt[:50]}...")
    print(f"[IA Online] Modèle: {args.model}")
    print(f"[IA Online] Provider: Hugging Face")
    print(f"[IA Online] Internet: {'CONNECTÉ' if est_connecte_internet() else 'HORS LIGNE'}")

    texte, internet, erreur = generer_prompt_online(args.prompt, model=args.model)

    if not internet:
        if args.json:
            print(json.dumps({"succes": False, "erreur": erreur}))
        else:
            print(f"[IA Online] ERROR: {erreur}")
        return 1

    if texte:
        if args.json:
            print(json.dumps({"succes": True, "texte": texte}))
        else:
            print(f"\n[IA Online] RÉSULTAT:")
            print(texte)
        return 0
    else:
        if args.json:
            print(json.dumps({"succes": False, "erreur": erreur}))
        else:
            print(f"[IA Online] ERROR: {erreur}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
