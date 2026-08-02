# Installateur StudioIA Desktop

Ce dossier contient le pipeline de construction des installateurs Windows de
StudioIA, basé sur **Inno Setup 6**.

## Livrables

| Fichier | Contenu | Taille approx. |
|---|---|---|
| `StudioIA-Setup.exe` | Application complète : code + runtime Python + FFmpeg + assets + ComposIA (sauf démos). **Sans** les modèles IA. | ~900 Mo–1 Go |
| `StudioIA-Models.exe` | Payload modèles Ollama (qwen2.5:7b + mistral, ~9 Go), installé dans `%USERPROFILE%\StudioIA\.ollama\models`. Produit seulement si `bundle-models\` est présent. | ~9 Go |

> Pourquoi deux fichiers ? La limite de **GitHub Releases est de 2 Go par fichier**.
> L'application sans les modèles tient sous la limite ; le payload modèles doit
> vivre dans un livrable séparé.

## Principes de l'installation

- **Dossier d'installation** : `%LOCALAPPDATA%\Programs\StudioIA` (pas Program
  Files → **aucun accès administrateur** requis).
- **Données utilisateur isolées** : `%USERPROFILE%\StudioIA\` (projects, config,
  logs, `.ollama\models`, xtts). L'app résout ce chemin via la variable
  `STUDIOIA_DATA_DIR`, **posée par le shell Tauri au lancement** (aucune var
  d'environnement globale requise, pas d'effet de bord système).
- **Désinstallation** : supprime le dossier d'app + raccourcis, **jamais** les
  données utilisateur. Réinstaller/ mettre à jour ne perd rien.

## Prérequis pour compiler

1. **Shell Tauri buildé** : `src-tauri\target\release\studioia-shell.exe`
   (`scripts\build.ps1 -Shell` ou `cargo build --release` dans `src-tauri/`).
2. **Runtime Python portable** : `runtime\python\python.exe` (`scripts/build.ps1`).
3. **Inno Setup 6** : `winget install --id JRSoftware.InnoSetup` — fournit
   `ISCC.exe`.

## Compiler

```powershell
# Tout (Setup + Models si bundle-models/ présent)
.\installer\build_installer.ps1

# Uniquement l'application
.\installer\build_installer.ps1 -Setup

# Uniquement le payload modèles (exige bundle-models/)
.\installer\build_installer.ps1 -Models

# Sans rebuild le shell Tauri (s'il est déjà buildé)
.\installer\build_installer.ps1 -SkipShellBuild
```

Les exécutables sont écrits dans `installer\Output\`.

## Compilation directe (sans script)

```powershell
# Application
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" `
   /dMODELS_ONLY=0 /dAppVersion=1.0.0 /dSrcDir=C:\StudioIA-Desktop\installer\ `
   C:\StudioIA-Desktop\installer\studioia.iss

# Modèles (exige bundle-models/)
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" `
   /dMODELS_ONLY=1 /dAppVersion=1.0.0 /dSrcDir=C:\StudioIA-Desktop\installer\ `
   C:\StudioIA-Desktop\installer\studioia.iss
```

## Notes de payload

- **`ComposIA\compositions\*.wav` / `*.mp3`** : démos pré-rendues, **non
  nécessaires** au pipeline (seuls `.json`, `.mid`, `.strudel`, `pistes\` sont
  lus par `modules/audio/composia.py`). Exclus du livrable pour rester sous la
  limite GitHub. Régénérées à la volée par fluidsynth.
- **`bundle-models\`** : miroir d'un dossier `OLLAMA_MODELS` (manifests +
  blobs). Le livrable modèles l'installe directement dans les données
  utilisateur, là où `core/services.py` attend le dépôt (`%USERPROFILE%\StudioIA\.ollama\models`).

## Test recommandé

Sur une **machine vierge (VM)** : installer `StudioIA-Setup.exe` → premier
lancement → le shell démarre le backend, l'assistant `/setup` détecte Ollama,
importe les modèles (depuis `Models.exe` ou par `ollama pull`), score 100 %.
Voir `RAPPORT_GLOBAL.md` pour la matrice de non-régression.