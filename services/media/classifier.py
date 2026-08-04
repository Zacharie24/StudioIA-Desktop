# -*- coding: utf-8 -*-
"""
classifier.py — Classifieur de thèmes visuels pour vidéos

Fonctionnalités :
- Mappe un sujet de vidéo (ex: "prière du soir") vers des thèmes visuels
- Utilise l'IA locale (Ollama) ou une table de correspondance
- Supporte différents types de contenu (prière, histoire, méditation, etc.)
- Extensible : on peut ajouter des associations manuelles

Utilisation :
    from services.media.classifier import suggerer_themes_pour_sujet

    themes = suggerer_themes_pour_sujet("Prière pour dormir paisiblement")
    # → {"principaux": ["sunset", "ocean", "night"], "secondaires": [...], "ambiances": [...]}
"""

import json
import os
import sys
from pathlib import Path

# === TABLE DE CORRESPONDANCE MANUELLE ===
# Association sujet → thèmes visuels
# Utilisée comme base, enrichie par l'IA

CORRESPONDANCES_THEMATIQUES = {
    # Prières et spiritualité
    "prière": ["paisible", "méditation", "spirituel", "recueillement"],
    "priere": ["paisible", "méditation", "spirituel", "recueillement"],
    "prier": ["paisible", "recueillement", "spirituel"],
    "dieu": ["lumière", "ciel", "nuages", "spirituel", "création"],
    "seigneur": ["lumière", "ciel", "nuages", "spirituel"],
    "jésus": ["lumière", "croix", "aube", "spirituel"],
    "christ": ["lumière", "église", "vitrail", "spirituel"],
    "esprit": ["lumière", "vent", "nature", "spirituel"],
    "foi": ["lumière", "chemin", "horizon", "spirituel"],

    # Émotions et états
    "paix": ["calme", "océan", "nature", "crépuscule"],
    "amour": ["cœur", "coucher soleil", "rose", "chaleureux"],
    "espoir": ["aube", "soleil levant", "arc-en-ciel", "lumière"],
    "joie": ["soleil", "fleurs", "champ", "couleurs"],
    "grâce": ["lumière douce", "aube", "nature paisible"],
    "reconnaissance": ["soleil couchant", "nature", "calme"],

    # Moments de la journée
    "matin": ["aube", "soleil levant", "rosée", "réveil"],
    "matinal": ["aube", "soleil levant", "calme matin"],
    "soir": ["crépuscule", "coucher soleil", "ciel orangé"],
    "nuit": ["étoiles", "lune", "ciel nocturne", "calme"],
    "dormir": ["nuit", "étoiles", "lune", "calme", "sommeil"],
    "sommeil": ["nuit", "lune", "étoiles", "calme profond"],

    # Nature
    "nature": ["forêt", "rivière", "montagne", "verdure"],
    "forêt": ["arbres", "feuillage", "bois", "nature vert"],
    "mer": ["océan", "vagues", "plage", "horizon bleu"],
    "océan": ["vagues", "mer", "horizon", "eau bleue"],
    "montagne": ["sommets", "neige", "altitude", "panorama"],
    "rivière": ["eau qui coule", "ruisseau", "nature calme"],
    "pluie": ["gouttes", "pluie fine", "nature mouillée"],

    # Protection et force
    "protection": ["bouclier", "forteresse", "lumière protectrice"],
    "force": ["montagne", "rocher", "arbre solide"],
    "courage": ["montagne", "aube", "horizon large"],
    "guérison": ["eau", "lumière douce", "nature apaisante"],
    "délivrance": ["libération", "lumière", "horizon ouvert"],

    # Famille et relations
    "famille": ["foyer", "chaleureux", "ensemble", "protection"],
    "enfant": ["jeu", "insouciance", "tendresse", "joie"],
    "parent": ["protection", "tendresse", "foyer"],

    # Histoires et récits
    "histoire": ["livre ancien", "parchemin", "bibliothèque"],
    "biblique": ["désert", "terre sainte", "olivier", "ancien"],
    "témoignage": ["visage", "lumière chaleureuse", "authentique"],

    # Thèmes génériques pour tout contenu
    "motivation": ["aube", "sommet", "horizon", "départ"],
    "méditation": ["calme absolu", "lac", "aube", "nature profonde"],
    "enseignement": ["livre", "savoir", "étude", "lumière"],
    "témoignage": ["visage expressif", "lumière naturelle", "authentique"],
    "création": ["nature sauvage", "aube", "fleurs", "diversité"],
    "voyage": ["route", "horizon", "découverte", "paysage"],
    "sagesse": ["livre ancien", "arbre", "montagne", "temps qui passe"],
}

# Thèmes génériques utilisés comme fallback
THEMES_GENERIQUES = {
    "paisible": ["calm_water", "gentle_nature", "soft_clouds"],
    "doux": ["soft_light", "gentle_waves", "warm_colors"],
    "solemel": ["cathedral", "organ", "stained_glass", "candle"],
    "contemplatif": ["sunset", "silhouette", "vast_landscape", "solitude"],
}

# Mots-clés en anglais pour la recherche API (mapping final)
THEMES_TO_ENGLISH_KEYWORDS = {
    "aube": "sunrise dawn",
    "soleil": "sun sunrise golden hour",
    "coucher soleil": "sunset golden hour dusk",
    "crépuscule": "twilight dusk sunset colors",
    "calme": "calm peaceful serene quiet",
    "océan": "ocean waves sea water",
    "mer": "sea ocean waves coastline",
    "vagues": "waves ocean water sea",
    "nature": "nature landscape natural scenery",
    "forêt": "forest woods trees nature",
    "montagne": "mountain peaks landscape nature",
    "rivière": "river stream water nature",
    "ciel": "sky clouds heaven blue",
    "nuages": "clouds sky heaven white",
    "étoiles": "stars night sky starry",
    "lune": "moon night sky moonlight",
    "lumière": "light sunlight divine light glow",
    "spirituel": "spiritual sacred holy prayer",
    "paix": "peace tranquility harmony calm",
    "recueillement": "meditation contemplation quiet prayer",
    "méditation": "meditation zen mindfulness calm",
    "champ": "field meadow grass nature landscape",
    "fleurs": "flowers meadow field nature",
    "crépuscule": "dusk twilight sunset",
    "nuit": "night dark evening moonlight",
    "eau": "water stream river lake",
    "lac": "lake water reflection calm",
    "cascade": "waterfall stream water nature",
    "arbre": "tree forest nature foliage",
    "neige": "snow winter landscape white",
    "désert": "desert sand dunes landscape",
    "horizon": "horizon landscape wide open view",
    "ciel étoilé": "starry sky galaxy night",
    "arc-en-ciel": "rainbow sky color hope",
    "chemin": "path road journey way trail",
    "livre": "book ancient old knowledge",
    "église": "church cathedral religious architecture",
    "vitrail": "stained glass church colorful light",
    "croix": "cross christian faith symbol",
    "bougie": "candle light flame warm glow",
}


def _extraire_mots_cles_francais(sujet):
    """
    Extrait les mots-clés français d'un sujet de vidéo
    Ex: "Prière du soir pour dormir paisiblement"
      → ["prière", "soir", "dormir", "paisiblement"]
    """
    # Nettoyer et normaliser
    sujet = sujet.lower().strip()
    mots = sujet.replace("é", "e").replace("è", "e").replace("ê", "e")
    mots = mots.replace("à", "a").replace("â", "a").replace("ù", "u")
    mots = mots.replace("ï", "i").replace("î", "i").replace("ô", "o")
    mots = mots.replace("ç", "c").replace("'", " ").replace("-", " ")

    # Mots vides à ignorer
    stop_words = {
        "le", "la", "les", "de", "du", "des", "un", "une", "pour",
        "sur", "dans", "avec", "par", "et", "ou", "est", "sont",
        "ce", "cet", "cette", "ces", "mon", "ton", "son", "notre",
        "votre", "leur", "je", "tu", "il", "elle", "nous", "vous",
        "ils", "elles", "qui", "que", "quoi", "dont", "où",
        "au", "aux", "en", "se", "sa", "ne", "pas", "plus"
    }

    mots_cles = []
    for mot in mots.split():
        mot = mot.strip()
        if mot and mot not in stop_words and len(mot) > 2:
            mots_cles.append(mot)

    return mots_cles


def _mapper_vers_themes(mots_cles):
    """
    Mappe des mots-clés français vers des thèmes visuels
    Retourne une liste triée par pertinence
    """
    scores = {}

    for mot_cle in mots_cles:
        # Chercher dans les correspondances manuelles
        if mot_cle in CORRESPONDANCES_THEMATIQUES:
            for theme in CORRESPONDANCES_THEMATIQUES[mot_cle]:
                scores[theme] = scores.get(theme, 0) + 2

        # Chercher les racines (ex: "paisiblement" → "paisible")
        for cle, valeur in CORRESPONDANCES_THEMATIQUES.items():
            if cle in mot_cle and len(cle) > 3:
                for theme in valeur:
                    scores[theme] = scores.get(theme, 0) + 1

    # Trier par score décroissant
    themes_tries = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [t[0] for t in themes_tries]


def _themes_vers_mots_cles_anglais(themes_francais):
    """
    Convertit les thèmes français en mots-clés anglais pour l'API Pexels
    """
    mots_cles = []

    for theme in themes_francais:
        if theme in THEMES_TO_ENGLISH_KEYWORDS:
            mots_cles.append(THEMES_TO_ENGLISH_KEYWORDS[theme])
        else:
            # Fallback : garder le mot français simple
            mots_cles.append(theme)

    return mots_cles


def _generer_via_ia(sujet, langue="fr"):
    """
    Utilise l'IA locale (Ollama) pour enrichir la suggestion de thèmes
    Fallback silencieux si l'IA n'est pas disponible
    """
    prompt = f"""Sujet de vidéo : "{sujet}"
Langue : {langue}

Génère 5 thèmes visuels en français pour illustrer cette vidéo.
Thèmes simples (1-2 mots) : nature, paysage, émotion, atmosphère.
Format : UNIQUEMENT JSON valide : {{"themes": ["theme1","theme2","theme3","theme4","theme5"]}}"""

    try:
        import sys
        try:
            from llm import appeler_llm
        except ImportError:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from llm import appeler_llm
        texte = appeler_llm(prompt, modele="mistral", timeout=15)
        debut = texte.find("{")
        fin = texte.rfind("}") + 1
        if debut >= 0 and fin > debut:
            data = json.loads(texte[debut:fin])
            return data.get("themes", [])
    except Exception:
        pass

    return []


def suggerer_themes_pour_sujet(sujet, langue="fr", utiliser_ia=True):
    """
    Point d'entrée principal : suggère des thèmes visuels pour un sujet

    Args:
        sujet: le sujet de la vidéo (ex: "Prière du soir pour la paix")
        langue: "fr" ou "en"
        utiliser_ia: utiliser l'IA pour enrichir (défaut: True)

    Returns:
        dict: {
            "principaux": [...],   # thèmes principaux (anglais pour API)
            "francais": [...],     # thèmes en français
            "mots_cles": [...],    # mots-clés extraits du sujet
        }
    """
    # Étape 1 : extraire les mots-clés du sujet
    mots_cles = _extraire_mots_cles_francais(sujet)

    # Étape 2 : mapper vers des thèmes français
    themes_fr = _mapper_vers_themes(mots_cles)

    # Étape 3 : enrichir avec l'IA si demandé
    if utiliser_ia:
        themes_ia = _generer_via_ia(sujet, langue)
        for t in themes_ia:
            t_norm = t.lower().strip()
            if t_norm not in themes_fr:
                themes_fr.append(t_norm)

    # Étape 4 : convertir en mots-clés anglais pour l'API
    mots_cles_en = _themes_vers_mots_cles_anglais(themes_fr)

    # Étape 5 : garder les plus pertinents (max 10)
    mots_cles_en = mots_cles_en[:10]

    return {
        "principaux": mots_cles_en,
        "francais": themes_fr[:10],
        "mots_cles": mots_cles,
        "sujet": sujet
    }


def determiner_ambiance_sujet(sujet):
    """
    Détermine l'ambiance visuelle d'un sujet
    Utile pour le mode "intelligent"

    Retourne un dict avec:
    - rythme: "lent", "modere", "dynamique"
    - luminosite: "sombre", "douce", "lumineuse"
    - palette: description des couleurs
    - transition: "fondu", "cut", "doux"
    """
    sujet_lower = sujet.lower()

    # Détection du rythme
    mots_lents = ["dormir", "paix", "calme", "repos", "nuit", "méditation",
                  "recueillement", "sommeil", "silence", "profond"]
    mots_dynamiques = ["action", "force", "combat", "victoire", "courage",
                       "puissant", "délivrance", "autorité"]

    rythme = "modere"
    score_lent = sum(1 for m in mots_lents if m in sujet_lower)
    score_dynamique = sum(1 for m in mots_dynamiques if m in sujet_lower)

    if score_lent > score_dynamique:
        rythme = "lent"
    elif score_dynamique > score_lent:
        rythme = "dynamique"

    # Détection luminosité
    mots_sombres = ["nuit", "ténèbres", "obscurité", "peur", "angoisse",
                    "larme", "triste", "solitude"]
    mots_lumineux = ["joie", "lumière", "soleil", "espoir", "aube",
                     "matin", "bénédiction", "gloire"]

    luminosite = "douce"
    if sum(1 for m in mots_sombres if m in sujet_lower) > 0:
        luminosite = "sombre"
    if sum(1 for m in mots_lumineux if m in sujet_lower) > 0:
        luminosite = "lumineuse"

    # Palette de couleurs suggérée
    palettes = {
        "sombre": "bleu profond, violet, gris argenté",
        "douce": "bleu pastel, or doux, blanc chaud, vert sauge",
        "lumineuse": "or, blanc, jaune chaud, bleu ciel, vert tendre"
    }

    # Type de transition
    transitions = {
        "lent": "fondu enchaîné",
        "modere": "fondu doux",
        "dynamique": "cut rapide"
    }

    return {
        "rythme": rythme,
        "luminosite": luminosite,
        "palette": palettes.get(luminosite, "couleurs naturelles"),
        "transition": transitions.get(rythme, "fondu doux")
    }


if __name__ == "__main__":
    # Test
    sujets_test = [
        "Prière du soir pour dormir paisiblement",
        "Protection divine pour ma famille",
        "Histoire de la création du monde",
        "Méditation sur la paix intérieure",
        "Action de grâce pour les bénédictions reçues"
    ]

    for sujet in sujets_test:
        resultat = suggerer_themes_pour_sujet(sujet, utiliser_ia=False)
        ambiance = determiner_ambiance_sujet(sujet)
        print(f"\n📹 Sujet : {sujet}")
        print(f"   Mots-clés : {resultat['mots_cles']}")
        print(f"   Thèmes FR : {resultat['francais']}")
        print(f"   Recherche API : {resultat['principaux'][:5]}")
        print(f"   Ambiance : {ambiance['rythme']} / {ambiance['luminosite']}")
