# Configuration partagée des voix TTS pour le projet StudioIA
# Ce fichier est partagé par run_tts.py et generate_shorts.py

VOIX_DISPONIBLES = {
    "1":  {"label": "XTTS - Vwa Gra (FR clone)",      "moteur": "xtts",  "voix": "xtts_clone_vwa_gra"},
    "2":  {"label": "XTTS - Vwa Soft (FR clone)",     "moteur": "xtts",  "voix": "xtts_clone_vwa_soft"},
    "3":  {"label": "Edge - Henri (FR homme)",         "moteur": "edge",  "voix": "fr_FR_henri"},
    "4":  {"label": "Edge - Remi (FR homme)",          "moteur": "edge",  "voix": "fr_FR_remi"},
    "5":  {"label": "Edge - Michael (FR homme)",       "moteur": "edge",  "voix": "fr_FR_michael"},
    "6":  {"label": "Edge - Denise (FR femme)",        "moteur": "edge",  "voix": "fr_FR_denise"},
    "7":  {"label": "Edge - Charline (FR femme BE)",   "moteur": "edge",  "voix": "fr_BE_charline"},
    "8":  {"label": "Edge - Steffan (EN homme US)",    "moteur": "edge",  "voix": "en_US_steffan"},
    "9":  {"label": "Edge - Ryan (EN homme GB)",       "moteur": "edge",  "voix": "en_GB_ryan"},
    "10": {"label": "Edge - Jenny (EN femme US)",      "moteur": "edge",  "voix": "en_US_jenny"},
    "11": {"label": "Piper - Gilles (FR homme)",       "moteur": "piper", "voix": "fr_FR_gilles"},
    "12": {"label": "Piper - Tom (FR homme)",          "moteur": "piper", "voix": "fr_FR_tom"},
    "13": {"label": "Piper - Siwis (FR femme)",        "moteur": "piper", "voix": "fr_FR_siwis"},
    "14": {"label": "Piper - Lessac (EN homme)",       "moteur": "piper", "voix": "en_US_lessac"},
}

# Mapping pour generate_shorts.py (sous-ensemble)
VOIX_MAP_SHORTS = {
    "1": {"moteur": "xtts", "voix": "xtts_clone_vwa_gra"},
    "2": {"moteur": "xtts", "voix": "xtts_clone_vwa_soft"},
    "3": {"moteur": "edge", "voix": "fr_FR_henri"},
    "4": {"moteur": "edge", "voix": "fr_FR_denise"},
    "8": {"moteur": "edge", "voix": "en_US_steffan"},
    "9": {"moteur": "edge", "voix": "en_GB_ryan"},
}

# === VOIX CLONÉES ===
CLONED_VOICES = []
# === FIN VOIX CLONÉES ===

def get_voix_label(voix_id):
    """Retourne le label d'une voix a partir de son ID"""
    return VOIX_DISPONIBLES.get(voix_id, {}).get("label", "Voix inconnue")

def get_voix_config(voix_id, moteur_par_defaut="edge"):
    """Retourne la configuration complete d'une voix"""
    # Vérifier d'abord les voix clonées
    for v in CLONED_VOICES:
        if v.get("key") == voix_id:
            return {"moteur": "xtts", "voix": voix_id}

    if voix_id in VOIX_DISPONIBLES:
        return VOIX_DISPONIBLES[voix_id]
    return {"moteur": moteur_par_defaut, "voix": "fr_FR_henri"}
