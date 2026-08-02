# StudioIA-Next — Rapport Global

**Date :** 30 Juillet 2026
**Projet :** Système autonome de création de contenu vidéo
**Version :** 2.0 (Next Generation)

---

## Table des matières

1. [Qu'est-ce que StudioIA-Next ?](#1-quest-ce-que-studiIa-next)
2. [Architecture générale](#2-architecture-générale)
3. [Modules et fonctionnalités](#3-modules-et-fonctionnalités)
4. [Guide d'utilisation](#4-guide-dutilisation)
5. [Dashboard Web](#5-dashboard-web)
6. [Projets](#6-projets)
7. [Dépannage](#7-dépannage)
8. [Prochaines étapes](#8-prochaines-étapes)

---

## 1. Qu'est-ce que StudioIA-Next ?

StudioIA-Next est un système autonome de création de contenu vidéo. Il permet de :

- **Générer automatiquement** des scripts vidéo via une IA locale (Ollama)
- **Apprendre des corrections** de l'utilisateur pour améliorer les générations futures
- **Analyser YouTube** pour comprendre ce qui fonctionne (via API Data v3)
- **Planifier et produire** du contenu de façon autonome
- **Uploader** les vidéos terminées sur YouTube (via OAuth 2.0)

### Principe fondamental

```
Correction manuelle > Analyse LLM > Validation > Integration au profil
```

L'utilisateur reste maître : ses corrections sont toujours prioritaires sur l'apprentissage automatique.

---

## 2. Architecture générale

```
C:\StudioIA-Next\
│
├── core/profiles/          ← Système de profils (règles d'écriture)
├── modules/
│   ├── automation/         ← Pipeline tout-automatique
│   ├── brain/              ← Génération de scripts (coeur IA)
│   ├── learning/           ← Apprentissage par corrections
│   └── youtube_analyzer/   ← Analyse et upload YouTube
├── web/                    ← Interface web (FastAPI)
├── projects/               ← Projets de contenu (27 existants)
└── data/                   ← Données (diagnostics, corrections, tokens)
```

### Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend web | FastAPI + Uvicorn |
| Templates | Jinja2 |
| IA locale | Ollama (qwen2.5-coder, mistral) |
| Stats YouTube | YouTube Data API v3 |
| Upload YouTube | OAuth 2.0 (google-api-python-client) |
| Interface bureau | CustomTkinter (app_gui.py) |
| Stockage | JSON (fichiers) |

---

## 3. Modules et fonctionnalités

### 3.1 Core — Profils (`core/profiles/profile_manager.py`)

Gère les profils de contenu. Chaque profil contient des règles d'écriture spécifiques.

**Profils disponibles :**
| Profil | Règles | Description |
|--------|--------|-------------|
| `prayer` | 55 | Prières chrétiennes (format, ton, structure, mots) |
| `default` | 14 | Profil générique |

**Fonctions principales :**
- `get_manager()` → Récupère le gestionnaire de profils
- `charger_profil_actif()` → Charge le profil configuré dans config.json
- `lister_profils()` → Liste tous les profils disponibles
- `mettre_a_jour_regles()` → Met à jour les règles d'un profil (utilisé par l'apprentissage)

### 3.2 Brain — Génération (`modules/brain/`)

Le cerveau du système. Génère des scripts vidéo via Ollama.

**`generate_script.py` :**
- `generer_plan(sujet, nb_chapitres, type_contenu, langue)` → Planifie les chapitres
- `generer_chapitre(sujet, numero, total, titre, mots_cible, type_contenu, langue)` → Génère un chapitre
- `main(projet_path)` → Point d'entrée qui lit le project.json et génère tout le contenu
- `charger_regles_redaction()` → Charge les règles depuis le profil actif
- `get_prompt_plan()` / `get_prompt_chapitre()` → Templates de prompts avec règles du profil

**`filter_text.py` :**
- `main(projet_path)` → Filtre et nettoie le texte généré
- Supprime les répétitions, bégaiements, remplace les mots complexes
- Utilise les règles du profil actif (mots à éviter, remplacements)

### 3.3 Apprentissage (`modules/learning/`)

Système de mémoire des corrections avec analyse LLM.

**`correction_memory.py` :**
- `enregistrer_correction(profil_id, projet_id, chapitre_id, texte_original, texte_corrige)` → Sauvegarde une correction
- `lister_corrections(profil_id, limite)` → Liste les corrections récentes
- `marquer_apprentissage_propose(chemin, proposition)` → Marque une correction comme analysée
- `marquer_apprentissage_valide(chemin)` → Marque une règle comme validée
- `statistiques(profil_id)` → Stats complètes (total, analysées, validées, en attente)

**`learning_engine.py` :**
- `analyser_correction(chemin_correction)` → Envoie la correction à Ollama pour proposer des règles
- `appliquer_proposition(proposition, profil_id)` → Applique une règle validée au profil
- `analyser_toutes_corrections(profil_id, limite)` → Analyse les corrections en attente
- `generer_rapport_apprentissage(profil_id)` → Génère un rapport d'apprentissage

### 3.4 YouTube Analyzer (`modules/youtube_analyzer/`)

**`youtube_stats.py` (lecture seule, clé API) :**
- `tester_connexion()` → Teste la validité de la clé API
- `chercher_chaine(nom_chaine)` → Trouve une chaîne YouTube
- `stats_chaine(channel_id)` → Abonnés, vues, vidéos
- `dernieres_videos(channel_id, max_results)` → Dernières vidéos avec stats
- `analyser_performances(channel_id, max_videos)` → Analyse complète + tendances

**`youtube_upload.py` (upload, OAuth 2.0) :**
- `auth_flow()` → Lance le flux OAuth (ouvre le navigateur)
- `upload_video(chemin_video, titre, description, ...)` → Uploade une vidéo
- `statut_auth()` → Vérifie le statut de l'authentification
- `lister_videos_chaine(channel_id)` → Liste les vidéos de la chaîne
- `_refresh_token()` → Rafraîchit automatiquement le token OAuth

### 3.5 Diagnostic (`modules/diagnostic.py`)

Analyse l'état du système au lancement.

- `executer_diagnostic(silent=False)` → Teste tout : config, profil, Ollama, Pexels, YouTube, projets, apprentissage
- `charger_dernier_diagnostic()` → Récupère le dernier diagnostic sauvegardé

**Score actuel : 100%** (90/90)
- Ollama : OK
- Profil prières : OK (55 règles)
- Pexels : OK (clé API configurée)
- YouTube API : OK (clé API configurée)
- YouTube OAuth : validé (token actif, upload automatique opérationnel)
- Projets : 29 total, 11 terminés

### 3.6 Automation — Pipeline (`modules/automation/`)

Le pipeline tout-automatique. 4 phases :

```
Phase 1: ANALYSE
  ├── Diagnostic système
  ├── Performances du profil
  └── Tendances YouTube (si configuré)

Phase 2: DÉCISION
  └── Suggestion du prochain contenu via IA

Phase 3: PRODUCTION
  ├── Création du projet
  ├── Génération du script (Ollama)
  └── Filtrage du texte

Phase 4: UPLOAD
  └── Upload vers YouTube (si OAuth configuré)
```

**Classes et fonctions :**
- `PipelineAutomation(profil_id)` → Instance du pipeline
- `executer_pipeline(profil_id, force_generer)` → Fonction de convenience
- `suggerer_contenu(profil_id, tendances)` → Suggère le prochain contenu
- `analyser_performances_profil(profil_id)` → Stats du profil

---

## 4. Guide d'utilisation

### 4.1 Lancement rapide

**Option A : Dashboard Web (recommandé)**
```
C:\StudioIA-Next\start_web.bat
→ Ouvre http://127.0.0.1:8080
```

**Option B : Menu principal**
```
C:\StudioIA-Next\launch.bat
→ Menu avec 6 options
```

**Option C : Directement**
```bash
cd C:\StudioIA-Next
python -m uvicorn web.main:app --host 127.0.0.1 --port 8080
```

### 4.2 Pages du Dashboard

| Page | URL | Fonction |
|------|-----|----------|
| Dashboard | `/` | Vue d'ensemble, score, services, suggestions |
| Automation | `/automation` | Lancer le pipeline automatique |
| Audit de chaîne | `/audit` | Audit de sa chaîne + comparaison concurrents + idées à tester |
| Touche humaine | `/human-touch` | Voix réelle en intro : texte à lire + DB meter + enregistrement mic |
| YouTube | `/youtube` | Analyser des chaînes YouTube |
| Apprentissage | `/apprentissage` | Suivi des corrections et règles apprises |
| Configuration | `/config` | API keys, profil, audio, sous-titres |

### 4.3 API REST

| Route | Méthode | Description |
|-------|---------|-------------|
| `/diagnostic/run` | GET | Exécute un diagnostic |
| `/diagnostic/latest` | GET | Dernier diagnostic |
| `/api/projets` | GET | Liste des projets |
| `/api/corrections` | GET | Statistiques des corrections |
| `/api/config` | POST | Sauvegarde la configuration |
| `/api/automation/run` | GET | Lance le pipeline |
| `/api/youtube/auth-status` | GET | Statut OAuth YouTube |
| `/youtube/analyze` | GET | Analyse une chaîne YouTube |
| `/api/audit/ma-chaine` | GET | Audit de sa chaîne (+`?concurrents=a,b`) |
| `/api/audit/chaine` | GET | Audit d'une chaîne précise (`?channel=`) |
| `/api/audit/historique` | GET | Historique des audits sauvegardés |
| `/api/audit/apprentissage` | GET | Leçons croisées des audits |
| `/api/human-touch/statut` | GET | Statut touche humaine |
| `/api/human-touch/activer` | POST | Active/désactive (`{"actif": true}`) |
| `/api/human-touch/generer-intro` | POST | Génère le texte d'intro (`sujet`, `projet` optionnel) |
| `/api/human-touch/upload-intro` | POST | Upload multipart de l'enregistrement vocal |

### 4.4 Configuration des API externes

**YouTube API (pour les stats et l'analyse) :**
1. Va sur https://console.cloud.google.com/
2. Crée un projet → active YouTube Data API v3
3. Crée une clé API → copie la clé
4. Ajoute-la dans le Dashboard `/config` (champ "Clé API YouTube")

**YouTube OAuth (pour l'upload automatique) :**
1. Dans Google Cloud Console → onglet "Credentials"
2. Crée un "OAuth 2.0 Client ID" (type: Desktop app)
3. Télécharge le JSON → place-le dans `data/youtube_oauth/client_secret.json`
4. Lance dans un terminal :
```bash
cd C:\StudioIA-Next
python -c "from modules.youtube_analyzer.youtube_upload import auth_flow; auth_flow()"
```

**Pexels (pour les images d'illustration) :**
1. Va sur https://www.pexels.com/api/
2. Crée un compte → obtiens une clé API (gratuite)
3. Ajoute-la dans le Dashboard `/config`

### 4.5 Pipeline automatique

Depuis le Dashboard `/automation` :
1. Clique **"Preview (analyser seulement)"** pour voir ce qui serait produit
2. Clique **"Production complète"** pour lancer la génération réelle
3. Active l'option "Forcer regénération" pour écraser les scripts existants

Depuis la ligne de commande :
```bash
# Preview
python -c "from modules.automation.pipeline import executer_pipeline; executer_pipeline(force_generer=False)"

# Production
python -c "from modules.automation.pipeline import executer_pipeline; executer_pipeline(force_generer=True)"
```

### 4.6 Corrections et apprentissage

1. Génère un script via le pipeline ou l'interface GUI
2. Corrige le texte manuellement dans l'éditeur de chapitres
3. La correction est sauvegardée dans `data/corrections/`
4. L'IA analyse la correction et propose des règles
5. Valide ou rejette les propositions dans l'interface d'apprentissage
6. Les règles validées sont intégrées au profil actif

---

## 5. Dashboard Web

### 5.1 Pages détaillées

**Dashboard (`/`)**
- Score système (100% actuellement)
- Nombre de projets (29 total, 11 terminés, 18 en cours)
- Stats des corrections
- État des services (Ollama, Pexels, YouTube)
- Suggestions d'amélioration
- Tableau des projets récents

**Automation (`/automation`)**
- État du système (score, API, tendances)
- Boutons Preview / Production complète
- Affichage en temps réel des phases du pipeline
- Résultat complet avec suggestion de contenu

**YouTube (`/youtube`)**
- Recherche de chaîne YouTube
- Statistiques détaillées (abonnés, vues, engagement)
- Top vidéos avec analyse
- Statut de l'API et de l'authentification OAuth
- Guide de configuration

**Apprentissage (`/apprentissage`)**
- Statistiques des corrections (total, analysées, validées, en attente)
- Rapport d'apprentissage complet

**Configuration (`/config`)**
- API keys (YouTube, Pexels)
- Sélection du profil actif (prières par défaut)
- Mode visuel et Low Resource
- Paramètres audio (volume, reverb)
- Sous-titres (style, taille)
- Sauvegarde automatique avec diagnostic

### 5.2 Intégration avec l'interface graphique

L'application GUI (`app_gui.py`) CustomTkinter offre :
- Sélection de profil
- Éditeur de chapitres avec sauvegarde des corrections
- Visualisation des propositions d'apprentissage
- Fenêtres modales pour les textes longs

---

## 6. Projets

### 6.1 État actuel

**Total : 27 projets**
- Terminés : **11** (40.7%)
- En cours : **16** (59.3%)

### 6.2 Projets les plus avancés

| Projet | Type | Avancement | Étapes restantes |
|--------|------|------------|-------------------|
| protection_prieure | Prière | 5/7 (71%) | video, export |
| benediction_matinale_protection | Prière | 5/8 (62%) | video, thumbnail, export |
| video_20260716_210417 | Prière | 4/7 (57%) | video, thumbnail, export |
| dormir_en_presence_de_dieu | Prière | 2/7 (28%) | audio, video, thumbnail, export, images |
| protection_enfants_prospere_famille | Prière | 2/7 (28%) | script (en cours), video, export, chapitres, audio |
| sleep_protection_powerful_hour | Prière | 2/7 (28%) | video, thumbnail, export, images, audio |

### 6.3 Compléter les projets

Pour générer les scripts manquants :
```bash
cd C:\StudioIA-Next
completer_projets.bat
```

Pour terminer un projet individuellement :
```bash
python -c "
from modules.brain.generate_script import main
import sys
sys.argv = ['gen.py', 'projects/NOM_DU_PROJET']
main()
"
```

**Note :** La génération via Ollama prend ~1-2 minutes par chapitre. Pour un projet de 5 chapitres, compter 5-10 minutes.

---

## 7. Dépannage

### Problèmes courants

| Problème | Cause | Solution |
|----------|-------|----------|
| Ollama ne répond pas | Service non lancé | Lance `ollama serve` dans un terminal |
| Génération lente | Modèle local | Réduire `target_duration_minutes` dans config.json |
| YouTube stats non disponibles | Clé API manquante | Configurer via `/config` |
| Upload impossible | OAuth non configuré | Placer `client_secret.json` dans `data/youtube_oauth/` |
| Caractères spéciaux (�) | Console Windows cp1252 | Utiliser le dashboard web (UTF-8) |
| Erreur 500 sur le dashboard | Cache Jinja2 | Redémarrer le serveur web |

### Commandes de diagnostic

```bash
# Diagnostic complet
python -c "from modules.diagnostic import executer_diagnostic; executer_diagnostic()"

# Test Ollama
python -c "import requests; r=requests.get('http://localhost:11434/api/tags'); print(r.json())"

# Test modules
python -c "from modules.automation.pipeline import executer_pipeline; executer_pipeline(force_generer=False)"
```

### Redémarrage

```bash
# Arrêter le serveur web
Ctrl+C dans le terminal

# Relancer
python -m uvicorn web.main:app --host 127.0.0.1 --port 8080
```

---

## 8. Prochaines étapes

### Priorité haute

1. ✅ **API keys configurées** (YouTube + Pexels) — fait le 30/07/2026, score 100%
2. ✅ **OAuth YouTube validé** — auth_flow() réussi le 30/07/2026, token sauvegardé, test réel OK (2 vidéos listées sur la chaîne)
3. ✅ **Audit de chaîne** — page `/audit` : audit complet de sa chaîne (1790 abonnés, 59 vidéos), comparaison concurrents (Desiring God 15.2x), mots-clés gagnants (dormir/seigneur/repos/psaume), durée optimale 35.4 min, idées à tester, apprentissage croisé
4. ✅ **Touche humaine (voix réelle)** — page `/human-touch` : texte d'intro généré + casier modifiable, sélection carte son, **DB meter temps réel** (idéal -18 à -6 dB), enregistrement mic, sauvegarde. Intégrée au pipeline : étape `intro` en attente d'enregistrement, fusion ffmpeg automatique en début de vidéo (`fusionner_intro` testé OK). Option opt-in (`human_touch.actif`, défaut false)
5. **Lancer la génération des projets en cours** avec `completer_projets.bat`
6. **Uploader les vidéos** — dès qu'un .mp4 existe dans un projet, le pipeline l'uploade automatiquement (mode privé par défaut)

### Priorité moyenne

7. **Automatiser le démarrage** du dashboard au boot Windows
8. **Ajouter plus de profils** (storytelling, éducation, etc.)
9. **Régler la durée par défaut** dans `config.json` (`target_duration_minutes`) pour des vidéos plus courtes (5-10 min)

### Priorité basse

10. **Migration vers SQLite** (remplacement du stockage JSON)
11. **Mode "agent permanent"** qui surveille et produit en continu
12. **Interface multilingue**

---

## Résumé technique

```
Modules Python : 14
Pages Web : 7
Routes API : 19
Projets : 29 (11 terminés, 18 en cours)
Profils : 2 (prayer: 55 règles, default: 14)
Score système : 100%
IA locale : Ollama (qwen2.5-coder, mistral)
Services externes : YouTube API v3 (OK), Pexels (OK), OAuth 2.0 (client_secret en place)
```

---

*Rapport généré le 30 Juillet 2026 — StudioIA-Next*
