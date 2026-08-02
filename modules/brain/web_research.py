# -*- coding: utf-8 -*-
"""
web_research.py — Recherche web avec fallback local si pas d'internet

Fonctionnalités :
- Recherche Google/Wikipedia si internet disponible
- Passe automatiquement en mode local si pas de connexion
- Stocke les résultats pour enrichir les prompts IA
"""

import sys
import socket
import json
import requests
from pathlib import Path
from datetime import datetime


# ============================================================
# Vérification de la connexion
# ============================================================

def est_connecte_internet(host="8.8.8.8", port=53, timeout=3):
    """
    Vérifie si une connexion internet est disponible
    Teste si on peut joindre Google DNS (ou tout autre serveur)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


# ============================================================
# Recherche web ( quand internet est disponible)
# ============================================================

def chercher_wikipedia(query, langue="fr"):
    """
    Recherche sur Wikipedia et retourne un résumé
    API publique, pas besoin de clé
    Nécessite un User-Agent (Wikipedia bloque les requêtes sans)
    """
    try:
        url = f"https://{langue}.wikipedia.org/w/api.php"
        headers = {
            "User-Agent": "StudioIA/1.0 (https://studioia.fr)"
        }
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json",
            "srprop": "snippet"
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("query", {}).get("search", [])[:2]:
            # Nettoyer le snippet (balises HTML)
            snippet = item["snippet"]
            import re
            snippet = re.sub(r'<[^>]+>', '', snippet)
            results.append({
                "title": item["title"],
                "snippet": snippet,
                "wiki_url": f"https://{langue}.wikipedia.org/wiki/{item['title'].replace(' ', '_')}"
            })
        return results
    except Exception as e:
        return []


def chercher_google(query, api_key=None, cx=None):
    """
    Recherche Google (optionnel avec clé API)
    Si pas de clé, retourne une liste vide (mode dégradé)
    """
    # Si pas de clé configurée, on passe en mode dégradé
    if not api_key or not cx:
        return []

    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cx,
            "q": query,
            "num": 3
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("items", [])[:2]:
            results.append({
                "title": item["title"],
                "link": item["link"],
                "snippet": item.get("snippet", "")
            })
        return results
    except Exception as e:
        return []


def rechercher_sur_web(query):
    """
    Fonction principale : recherche sur le web avec fallback automatique
    Retourne les résultats sous forme de texte formaté
    """
    connexion = est_connecte_internet()

    if not connexion:
        return None  # Pas d'internet, l'IA locale gère

    results = {}

    # Recherche Wikipedia (toujours disponible)
    wiki_results = chercher_wikipedia(query)
    if wiki_results:
        results["wikipedia"] = wiki_results

    # Recherche Google (si clé configurée)
    # TODO: Charger la clé depuis config.json ou un fichier dédié
    # results_google = chercher_google(query, api_key="...", cx="...")
    # if results_google:
    #     results["google"] = results_google

    # Formater le résultat
    if results:
        texte = []
        if "wikipedia" in results:
            texte.append("=== Wikipedia ===")
            for r in results["wikipedia"]:
                texte.append(f"Titre: {r['title']}")
                texte.append(f"Snippet: {r['snippet']}")
                texte.append("")

        return "\n".join(texte)

    return None


# ============================================================
# Utilitaires pour l'intégration
# ============================================================

def enrichir_prompt_avec_recherche(prompt, query_recherche=None):
    """
    Enrichit un prompt avec des résultats de recherche
    Si pas d'internet, retourne le prompt original
    """
    if query_recherche is None:
        query_recherche = prompt  # On recherche sur le sujet du prompt

    contexte = rechercher_sur_web(query_recherche)

    if contexte is None:
        # Pas d'internet - l'IA locale gère
        return prompt, False  # (prompt, internet_disponible)

    if contexte:
        prompt_enrichi = f"""[INFORMATION RÉCENTE TROUVÉE SUR LE WEB]

{contexte}

[TA TÂCHE]
{prompt}

[INSTRUCTIONS]
Utilise les informations ci-dessus pour enrichir ta réponse.
Forme ton raisonnement à partir de ces faits.
Ne copie pas textuellement, intègre l'information naturellement."""

        return prompt_enrichi, True
    else:
        return prompt, True


def get_infonot_found() -> bool:
    """
    Vérifie si internet est disponible
    Retourne True si internet fonctionne, False sinon
    """
    return est_connecte_internet()


def tester_recherche(query="prière chrétienne"):
    """
    Test la recherche web et affiche les résultats
    """
    print(f"[TEST] Recherche sur: {query}")
    print(f"[TEST] Internet: {'CONNECTÉ' if est_connecte_internet() else 'HORS LIGNE'}")

    if not est_connecte_internet():
        print("[TEST] Pas d'internet → mode local activé")
        return None

    wiki = chercher_wikipedia(query)
    print(f"[TEST] Wikipedia: {len(wiki)} résultats")

    for r in wiki:
        print(f"  - {r['title']}")

    return wiki


# ============================================================
# Usage en ligne de commande
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Recherche web avec fallback local"
    )
    parser.add_argument("query", help="Query de recherche")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")

    args = parser.parse_args()

    connexion = est_connecte_internet()

    if not connexion:
        if args.json:
            print(json.dumps({"internet": False, "resultats": None}))
        else:
            print("[Internet] NON CONNECTÉ → L'IA locale gérera")
        return 1

    print("[Internet] CONNECTÉ")

    results = chercher_wikipedia(args.query)

    if args.json:
        print(json.dumps({"internet": True, "resultats": results}, ensure_ascii=False, indent=2))
    else:
        if results:
            print("\nRésultats Wikipedia:")
            for r in results:
                print(f"\n- {r['title']}")
                print(f"  {r['snippet']}")
        else:
            print("Aucun résultat trouvé.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
