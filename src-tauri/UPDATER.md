# Mise à jour automatique — StudioIA Desktop

Le shell Tauri vérifie automatiquement les mises à jour via **GitHub Releases**
(`tauri-plugin-updater` + `tauri-plugin-dialog`).

## Comportement (source actuelle)

Au lancement, ~10 s après le démarrage du dashboard, l'app vérifie la version :

- **Pas de nouvelle version** → rien (silencieux, même hors ligne).
- **Nouvelle version dispo** → boîte de dialogue native :
  - **Oui** → télécharge l'installateur **signé** (`StudioIA-Setup.exe`, octets
    vérifiés par la pubkey), le lance en silencieux, puis quitte l'app pour
    laisser l'installateur remplacer les fichiers.
  - **Non** (« Plus tard ») → la version est mémorisée dans
    `%USERPROFILE%\StudioIA\updater_seen.txt` ; on ne re-demandera pas pour
    cette même version au prochain lancement.

Ne touche jamais aux données utilisateur (`%USERPROFILE%\StudioIA`, isolé) ni
aux modèles Ollama.

## Publier une nouvelle version (sur le PC de dev)

Prérequis : Rust + `cargo-tauri`, la **clé privée de signature** disponible
(gitignorée — `installer/keys/` ou variables d'env
`TAURI_SIGNING_PRIVATE_KEY` / `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`).

1. **Bump de version** (doivent correspondre) :
   - `src-tauri/Cargo.toml` → `[package] version`
   - `src-tauri/tauri.conf.json` → `version`
2. **Build avec artefacts updater** (déjà activé : `createUpdaterArtifacts: true`) :
   ```
   cd src-tauri
   npm run tauri build   # ou : cargo tauri build
   ```
   Produit dans `target/release/bundle/` : l'installeur + `latest.json`
   (+ fichiers de signature `.sig`).
3. **Créer la GitHub Release** sur `Zacharie24/studioia-desktop`, tag
   `vX.Y.Z` (semver), et **uploader les artefacts** : `latest.json`,
   l'installeur (`*.exe`/`*.msi`) et les `.sig`.
   → L'endpoint configuré dans `tauri.conf.json` :
   `https://github.com/Zacharie24/studioia-desktop/releases/latest/download/latest.json`
   pointe automatiquement vers la Release la plus récente.
4. La pubkey dans `tauri.conf.json → plugins.updater.pubkey` **ne change pas**
   tant qu'on signe avec la même clé privée.

## Notes

- **Première fois** : si l'app installée est antérieure à cette version « qui
  demande », elle installera la nouvelle version silencieusement une fois ;
  ensuite, chaque mise à jour sera proposée par le dialogue.
- La vérification se fait sur le PC où l'app **s'exécute** (ici) ; la publication
  se fait sur le PC de **développement** (l'autre PC).
