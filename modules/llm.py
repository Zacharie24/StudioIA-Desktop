"""
Module central LLM — Unifie les appels Ollama (local) et OmniRoute (cloud).

Tous les modules StudioIA passent par ce module pour leurs appels IA.
- Ollama (défaut) : API native localhost:11434 (inchangé)
- OmniRoute : API compatible OpenAI localhost:20128 (cloud, auto-switch providers)

Config (config.json) :
  "fournisseur_llm": "ollama" | "omniroute"
  "fournisseur_llm_modele": "auto/fast" | "mistral" | ...
"""

import json
import logging
import os
import sys
from pathlib import Path

import requests

logger = logging.getLogger("studioia.llm")

# ── URLs ──────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
OMNIROUTE_URL = "http://localhost:20128/v1"


# ── Configuration ─────────────────────────────────────────────────────────────

def _lire_config() -> dict:
    """Lit config.json en priorisant STUDIOIA_DATA_DIR, puis racine Next, puis racine."""
    # 1. Via core.paths (Desktop installé ou dev avec STUDIOIA_DATA_DIR)
    try:
        if "core" in sys.modules:
            from core.paths import lire_config
            return lire_config()
        # Import direct si core.paths pas encore chargé
        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root))
        from core.paths import lire_config
        return lire_config()
    except Exception:
        pass
    # 2. Fallback : racine du projet (Next ou Desktop)
    for candidate in [
        os.environ.get("STUDIOIA_DATA_DIR", ""),
        str(Path(__file__).resolve().parent.parent),
    ]:
        try:
            p = Path(candidate) / "config.json"
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue
    return {}


def _config_llm() -> tuple:
    """Retourne (fournisseur, modele) lus dans config.json."""
    cfg = _lire_config()
    fournisseur = cfg.get("fournisseur_llm", "ollama").strip().lower()
    modele = cfg.get("fournisseur_llm_modele", "").strip()
    if not modele:
        modele = "auto/fast" if fournisseur == "omniroute" else "mistral"
    return fournisseur, modele


# ── Appel prompt → texte (anciennement /api/generate) ────────────────────────

def appeler_llm(prompt: str, modele: str = None, temperature: float = 0.8,
                max_tokens: int = 512, timeout: int = 600,
                options: dict = None) -> str:
    """
    Appel LLM unifié (prompt → texte brut).

    - Ollama : POST /api/generate (natif), options = repeat_penalty, repeat_last_n...
    - OmniRoute : POST /v1/chat/completions (OpenAI), même résultat.

    Retourne le texte généré. En cas d'échec OmniRoute → repli automatique Ollama.

    Timeout par défaut 600 s : les modèles locaux (Ollama) sur petit PC peuvent
    mettre plusieurs minutes pour générer un long script. L'ancien code n'avait
    aucun timeout — 600 s est généreux tout en évitant les blocages infinis.
    """
    fournisseur, modele_defaut = _config_llm()
    if modele is None:
        modele = modele_defaut

    if fournisseur == "omniroute":
        return _appeler_omniroute_generate(prompt, modele, temperature,
                                           max_tokens, timeout)
    return _appeler_ollama_generate(prompt, modele, temperature, options, timeout)


def _appeler_ollama_generate(prompt: str, modele: str, temperature: float,
                              options: dict, timeout: int) -> str:
    """Appel natif Ollama /api/generate."""
    opts = {"temperature": temperature}
    if options:
        opts.update(options)
    else:
        opts["repeat_penalty"] = 1.3
        opts["repeat_last_n"] = 128
    payload = {"model": modele, "prompt": prompt, "stream": False, "options": opts}
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data.get("response", "")


def _appeler_omniroute_generate(prompt: str, modele: str, temperature: float,
                                 max_tokens: int, timeout: int) -> str:
    """OmniRoute : traduction OpenAI /v1/chat/completions → texte."""
    payload = {
        "model": modele,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        r = requests.post(f"{OMNIROUTE_URL}/chat/completions", json=payload,
                          timeout=timeout)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        logger.warning("OmniRoute (generate) indisponible (%s), repli sur Ollama", e)
        return _appeler_ollama_generate(prompt, modele, temperature, None, timeout)


# ── Appel chat messages → texte (anciennement /api/chat) ─────────────────────

def appeler_chat_llm(messages: list, modele: str = None, temperature: float = 0.8,
                     max_tokens: int = 2048, timeout: int = 600,
                     format_json: bool = False) -> str:
    """
    Appel LLM unifié en mode chat (liste de messages → texte).

    - Ollama : POST /api/chat (natif), format:"json" si format_json.
    - OmniRoute : POST /v1/chat/completions (OpenAI), response_format si format_json.

    Retourne le texte de la réponse. Repli automatique Ollama si OmniRoute échoue.

    Timeout par défaut 600 s (même raison que appeler_llm : générations locales
    lentes sur petit PC).
    """
    fournisseur, modele_defaut = _config_llm()
    if modele is None:
        modele = modele_defaut

    if fournisseur == "omniroute":
        return _appeler_omniroute_chat(messages, modele, temperature,
                                       max_tokens, timeout, format_json)
    return _appeler_ollama_chat(messages, modele, temperature,
                                max_tokens, timeout, format_json)


def _appeler_ollama_chat(messages: list, modele: str, temperature: float,
                          max_tokens: int, timeout: int, format_json: bool) -> str:
    """Appel natif Ollama /api/chat."""
    payload = {
        "model": modele,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if max_tokens:
        payload["options"]["num_predict"] = max_tokens
    if format_json:
        payload["format"] = "json"
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["message"]["content"].strip()


def _appeler_omniroute_chat(messages: list, modele: str, temperature: float,
                             max_tokens: int, timeout: int, format_json: bool) -> str:
    """OmniRoute : traduction OpenAI /v1/chat/completions."""
    payload = {
        "model": modele,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if format_json:
        payload["response_format"] = {"type": "json_object"}
    try:
        r = requests.post(f"{OMNIROUTE_URL}/chat/completions", json=payload,
                          timeout=timeout)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        logger.warning("OmniRoute (chat) indisponible (%s), repli sur Ollama", e)
        return _appeler_ollama_chat(messages, modele, temperature,
                                    max_tokens, timeout, format_json)
