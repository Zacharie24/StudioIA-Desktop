; ============================================================================
; studioia.iss — Installateur StudioIA Desktop
; ============================================================================
; Compilé avec Inno Setup 6. Deux livrables (limite GitHub 2 Go / fichier) :
;
;   StudioIA-Setup.exe   — l'application complète (code + runtime + ffmpeg +
;                          assets + ComposIA) — PAS les modèles IA (~9 Go).
;                          Compilé avec : /dMODELS_ONLY=0
;   StudioIA-Models.exe  — payload modèles Ollama (qwen2.5:7b + mistral).
;                          Compilé avec : /dMODELS_ONLY=1
;
; Les données utilisateur (%USERPROFILE%\StudioIA) vivent HORS du dossier
; d'installation : l'app les résout via STUDIOIA_DATA_DIR (posée par le shell
; Tauri au lancement). La désinstallation ne touche donc JAMAIS aux données.
;
; Prérequis de compilation :
;   * app buildée   : src-tauri\target\release\studioia-shell.exe
;   * runtime       : runtime\python\  (venv portable)
;   * bundle modèles: bundle-models\   (seulement pour le livrable modèles)
; ============================================================================

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef MODELS_ONLY
  #define MODELS_ONLY "0"
#endif

; Répertoire racine de la source (le dossier du .iss)
#ifndef SrcDir
  #define SrcDir SourcePath
#endif

; Nom des sorties selon le livrable
#if MODELS_ONLY == "1"
  #define MyAppName "StudioIA — Modèles IA"
  #define MyAppId   "{{7D3C1B45-9A71-4A1E-9D6F-4C0E6A9B8F12}"
  #define OutFile   "StudioIA-Models"
#else
  #define MyAppName "StudioIA"
  #define MyAppId   "{{A1B2C3D4-5E6F-4A7B-8C9D-0E1F2A3B4C5D}"
  #define OutFile   "StudioIA-Setup"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=StudioIA
AppPublisherURL=https://studioia.example
DefaultDirName={localappdata}\Programs\StudioIA
DefaultGroupName=StudioIA
DisableProgramGroupPage=yes
OutputDir=..\installer\Output
OutputBaseFilename={#OutFile}
SetupIconFile={#SrcDir}..\src-tauri\icons\icon.ico
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\StudioIA.exe
; Pas d'accès administrateur nécessaire (installation par utilisateur).
PrivilegesRequired=lowest
; Aucune page de sélection de dossier : répertoire imposé.
DisableDirPage=yes
DisableReadyPage=no
; Version Windows minimale : 10 (build 17763).
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
#if MODELS_ONLY == "1"
Name: "importauto"; Description: "Importer les modèles immédiatement"; Flags: unchecked
#else
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; Flags: unchecked
Name: "demarrerapp"; Description: "Lancer StudioIA après l'installation"
#endif

; ============================================================================
; [Files] — Application complète (MODELS_ONLY="0")
; ============================================================================
[Files]
#if MODELS_ONLY == "0"

; --- Shell Tauri (exe principal à la racine, l'installateur le nomme StudioIA.exe)
Source: "{#SrcDir}..\src-tauri\target\release\studioia-shell.exe"; DestDir: "{app}"; DestName: "StudioIA.exe"; Flags: ignoreversion

; --- Code Python
Source: "{#SrcDir}..\core\*"; DestDir: "{app}\core"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}..\modules\*"; DestDir: "{app}\modules"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}..\web\*"; DestDir: "{app}\web"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}..\services\*"; DestDir: "{app}\services"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; --- Config embarquée (valeurs par défaut) + dépendances
Source: "{#SrcDir}..\config.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}..\config_video.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}..\style_redaction.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

; --- Runtime Python portable
Source: "{#SrcDir}..\runtime\python\*"; DestDir: "{app}\runtime\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; --- FFmpeg embarqué
Source: "{#SrcDir}..\tools\ffmpeg\*"; DestDir: "{app}\tools\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs

; --- ComposIA (fluidsynth + soundfonts + gabarits de composition).
;     Les .wav/.mp3 de démo dans compositions\ sont des PRÉ-RENDUES (non
;     nécessaires au pipeline : seuls .json/.mid/.strudel/pistes sont lus).
;     On les exclut pour rester sous la limite GitHub (2 Go/fichier).
Source: "{#SrcDir}..\ComposIA\*"; DestDir: "{app}\ComposIA"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.wav,*.mp3"

; --- Icône (réutilisée par le raccourci Bureau / le désinstalleur)
Source: "{#SrcDir}..\src-tauri\icons\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

#endif

; ============================================================================
; [Files] — Payload modèles (MODELS_ONLY=1)
; ============================================================================
#if MODELS_ONLY == "1"
; Le payload est un miroir d'un dossier OLLAMA_MODELS (manifests + blobs).
; Il est installé dans les DONNÉES UTILISATEUR : %USERPROFILE%\StudioIA\.ollama\models
; (exactement le chemin que core/services.py attend, via STUDIOIA_DATA_DIR).
Source: "{#SrcDir}..\bundle-models\*"; DestDir: "{userprofile}\StudioIA\.ollama\models"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif

; ============================================================================
; [Icons]
; ============================================================================
[Icons]
#if MODELS_ONLY == "0"
Name: "{autoprograms}\StudioIA.lnk"; Filename: "{app}\StudioIA.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"
Name: "{userdesktop}\StudioIA.lnk"; Filename: "{app}\StudioIA.exe"; WorkingDir: "{app}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
#endif

; ============================================================================
; [Run]
; ============================================================================
[Run]
#if MODELS_ONLY == "0"
; Premier lancement : l'app démarre le backend + assistant de configuration.
Filename: "{app}\StudioIA.exe"; Description: "Lancer StudioIA"; Flags: nowait postinstall skipifsilent; Tasks: demarrerapp
#endif

; ============================================================================
; [Registry] — Aucune clé nécessaire : l'état est dans les données utilisateur.
; ============================================================================

; ============================================================================
; [Code] — Vérification après installation
; ============================================================================
[Code]
procedure InitializeWizard;
begin
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
end;
