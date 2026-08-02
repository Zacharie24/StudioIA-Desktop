# -*- coding: utf-8 -*-
"""
spelling_corrector.py — Correcteur orthographique pour les texts IA

Corrige les erreurs courantes faites par les modèles IA (Ollama, HuggingFace)
ainsi que les confusions fréquentes en français.
"""

# Dictionnaire des corrections orthographiques
# Format: "mot_erre": "mot_correct"
CORRECTIONS = {
    # Confusions communes
    "immotel": "immotelle",
    "immotelles": "immotelles",
    "puissant": "puissant",  # Le mot est correct, mais l'IA le confond parfois
    "puisant": "puissant",
    "puissances": "puissances",

    # Autres erreurs fréquentes
    "leur": "leur",
    "leurs": "leurs",
    "a": "a",
    "à": "à",
    "son": "son",
    "sont": "sont",
    "cest": "c'est",
    "cesta": "c'est à",
    "ellea": "elle a",
    "ilya": "il y a",
    "nest": "n'est",
    "ne pas": "ne pas",
    "pas": "pas",
    "sur": "sur",
    "son": "son",
    "sont": "sont",

    # Noms propres et termes spécifiques
    "jesus": "Jésus",
    "jésus": "Jésus",
    "jesuche": "Jésus-Christ",
    "jesus christ": "Jésus-Christ",
    "dieu": "Dieu",
    "dieu": "Dieu",
    "demon": "démon",
    "demons": "démon",
    "paradis": "paradis",
    "enfer": "enfer",
    "apocalypse": "apocalypse",

    # Formes verbales
    "aimez": "aimez",
    "aimer": "aimer",
    "prier": "prier",
    "priez": "priez",
    "bienvenue": "bienvenue",
    "bienvenu": "bienvenu",
}

# Patterns de remplacement (pour les expressions)
CORRECTIONS_PATTERNS = [
    # Espaces manquants avant apostrophes
    (r"(\w)'(\w)", r"\1'\2"),  # Ex: c est -> c'est
    # Espaces manquants après apostrophes
    (r"'(\w)", r"' \1"),  # Ex: 'il -> ' il (à corriger ensuite)
    # Espaces doubles
    (r"  +", " "),
]


def corriger_texte(texte):
    """
    Appliquer les corrections orthographiques à un texte

    Args:
        texte: Le texte à corriger

    Returns:
        Le texte corrigé
    """
    if not texte:
        return ""

    # Appliquer les corrections mot à mot
    for mot_erre, mot_correct in CORRECTIONS.items():
        # Remplacer en respectant la casse
        if mot_erre.lower() in texte.lower():
            # Remplacer tout en conservant la casse d'origine
            import re

            def replace_case(match):
                original = match.group(0)
                if original.isupper():
                    return mot_correct.upper()
                elif original[0].isupper():
                    return mot_correct.capitalize()
                return mot_correct

            pattern = r'\b' + re.escape(mot_erre) + r'\b'
            texte = re.sub(pattern, replace_case, texte, flags=re.IGNORECASE)

    return texte


def corriger_chapitre(texte_chapitre):
    """
    Correction complète d'un chapitre avec vérification
    """
    if not texte_chapitre:
        return texte_chapitre

    texte_corrigé = corriger_texte(texte_chapitre)

    return texte_corrigé


def verifier_chapitre(texte_chapitre):
    """
    Vérifier un chapitre pour détecter les erreurs courantes

    Args:
        texte_chapitre: Le texte à vérifier

    Returns:
        dict avec: {erreurs: [list], correct: bool, texte_corrigé: str}
    """
    if not texte_chapitre:
        return {"erreurs": [], "correct": True, "texte_corrigé": ""}

    erreurs = []
    texte_temp = texte_chapitre

    for mot_erre, mot_correct in CORRECTIONS.items():
        if mot_erre.lower() in texte_temp.lower():
            # Trouver la position
            import re
            pattern = r'\b' + re.escape(mot_erre) + r'\b'
            matches = list(re.finditer(pattern, texte_temp, flags=re.IGNORECASE))
            for m in matches:
                position = m.start()
                contexte = texte_temp[max(0, position-20):min(len(texte_temp), position+20)]
                erreurs.append({
                    "mot": mot_erre,
                    "correct": mot_correct,
                    "position": position,
                    "contexte": contexte
                })

    texte_corrigé = corriger_texte(texte_chapitre)

    return {
        "erreurs": erreurs,
        "correct": len(erreurs) == 0,
        "texte_corrigé": texte_corrigé
    }


def afficher_resultats_verification(texte, resultats):
    """
    Afficher les résultats de la vérification orthographique
    """
    if resultats["correct"]:
        print("[VOIX] Aucune erreur détectée")
        return True

    print(f"[VOIX] {len(resultats['erreurs'])} erreur(s) détectée(s):")
    for err in resultats["erreurs"][:5]:  # Limiter à 5 erreurs
        print(f"  - '{err['mot']}' devrait être '{err['correct']}'")
        print(f"    Contexte: ...{err['contexte']}...")

    return False


if __name__ == "__main__":
    # Test
    test_text = "Jésus est le dieu puissant qui nous protège. L'immotel est notre refuge."
    print("Texte original:", test_text)

    resultats = verifier_chapitre(test_text)
    print("\nVérification:")
    if not resultats["correct"]:
        for err in resultats["erreurs"]:
            print(f"  Erreur: '{err['mot']}' -> '{err['correct']}'")

    print("\nTexte corrigé:", resultats["texte_corrigé"])
