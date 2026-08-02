# StudioIA - Guide de Dveloppement

## Architecture du Projet

StudioIA est un systme de gnration automatique de contenu YouTube (vidos longues et Shorts) avec une approche "tous-en-un" pour les crateurs de contenu chrtien protestant.

### Structure du Projet

```
C:\StudioIA\
├── modules\
│   ├── brain\           # Gestion de l'IA (génération script, modèles)
│   ├── images\          # Téléchargement et gestion des images
│   ├── shorts\          # Génération de contenu Shorts
│   ├── tts\             # Synthèse vocale (text-to-speech)
│   ├── thumbnail\       # Génération de miniatures
│   ├── video\           # Montage vidéo (Shotcut)
│   └── utils\           # Utilitaires partagés
├── assets\              # Ressources statiques (polices, musiques, backgrounds)
├── projects\            # Projets de vidéos générés
├── config.json          # Configuration globale
├── style_redaction.json # Règles de style et de rédaction
├── api_keys.json        # Clés API (Pexels, Unsplash) - gitignored
├── A_CORRIGER.txt       # Liste des corrections à effectuer
└── DEVELOPPEMENT.md     # Ce fichier
```

### Modules Principaux

| Module | Fonction |
|--------|----------|
| `modules/brain/` | Génération de scripts via Ollama (Qwen, Mistral) |
| `modules/images/library_manager.py` | Téléchargement d'images (Pexels, Unsplash, Openverse) |
| `modules/tts/run_tts.py` | Génération audio (XTTS, Edge, Piper) |
| `modules/video/build_video.py` | Montage vidéo avec Shotcut |
| `modules/shorts/generate_shorts.py` | Génération de Shorts YouTube |

### Flux de Travail

1. **Script** (`modules/brain/generate_script.py`) : Génère le plan et les chapitres
2. **Images** (`modules/images/library_manager.py`) : Télécharge les visuels
3. **Audio** (`modules/tts/run_tts.py`) : Crée la voix off
4. **Thumbnail** (`modules/thumbnail/thumbnail_builder.py`) : Génère la miniature
5. **Vidéo** (`modules/video/build_video.py`) : Monte la vidéo finale

## Comment Ajouter une Nouvelle Fonctionnalité

1. **Identifier le module concerné**
   - Script/contenu → `modules/brain/`
   - Images → `modules/images/`
   - Audio → `modules/tts/`
   - Vidéo → `modules/video/`
   - Shorts → `modules/shorts/`

2. **Créer une nouvelle fonction** dans le module approprié

3. **Respecter les conventions** :
   - Fonctions avec docstrings
   - Gestion d'erreurs avec try/except
   - Logs via `log(msg)` ou `print()`

4. **Mettre à jour `config.json`** si besoin de nouvelles options

5. **Tester avec un projet existant**

## Guide de Contribution

### Style de Code

- Python 3.10+
- Pathlib pour les chemins
- UTF-8 pour tous les fichiers
- Anglais pour les variables techniques, français pour les messages utilisateur

### Conventions

```python
def ma_fonction(parametre, optionnel=True):
    """Docstring avec description, paramètres et retour."""
    log("Message de log")
    try:
        # code
        return resultat
    except Exception as e:
        log(f"Erreur : {e}")
        return None
```

### Ajouter une nouvelle voix TTS

Modifier `modules/tts/voix_config.py` :

```python
"15": {"label": "Nouvelle Voix", "moteur": "xtts", "voix": "xtts_nouvelle_voix"},
```

## Corrections Déjà Terminées (v2026-07-22)

### 1. Clés API Exposées ✅
- Création de `api_keys.json` (gitignored)
- Création de `modules/api_keys.py`
- Mise à jour de `assets_manager.py` et `library_manager.py`

### 2. Fichier de Style Uni ✅
- Suppression de `style_guide.json`
- Mise à jour de `library_manager.py` vers `style_redaction.json`

### 3. Chemin TTS Externalisé ✅
- Ajout de `tts_external_path` dans `config.json`
- Mise à jour de `run_tts.py` pour utiliser la config

### 4. Thumbnail Builder Robuste ✅
- Gestion d'erreur pour liste `bgs` vide

### 5. Suppression Kdenlive ✅
- Fichiers supprimés : `gen_kdenlive.py`, `open_kdenlive.py`, `ouvrir_projet_kdenlive.py`
- Shotcut est maintenant le seul moteur de montage

### 6. Ollama Return Value ✅
- `appeler_ollama` retourne maintenant `(response, modele)`
- Mise à jour de `generate_script.py`

### 7. clean_intro.py ✅
- Vérification de l'existence du dossier `chapters/`

### 8. Mapping Voix Unifié ✅
- Création de `modules/tts/voix_config.py` partagé
- Synchronisation `run_tts.py` ↔ `generate_shorts.py`

## Configuration

### config.json (extrait)

```json
{
  "tts_external_path": "C:\\tts-pentest",
  "projects_path": "C:\\StudioIA\\projects",
  "assets_path": "C:\\StudioIA\\assets",
  "video_resolution": "1920x1080",
  "target_duration_minutes": 60,
  "language": "fr"
}
```

## Dépannage

### Erreur "Aucun modèle disponible"
→ Lancer Ollama et télécharger un modèle : `ollama pull mistral`

### Erreur d'authentification Pexels/Unsplash
→ Vérifier `api_keys.json` et `.gitignore`

### Audio non généré
→ Vérifier le chemin `tts_external_path` dans `config.json`

---

*Dernière mise à jour : 2026-07-22*
