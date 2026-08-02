# ============================================================================
# build_installer.ps1 — Construit les installateurs StudioIA (Inno Setup 6)
# ============================================================================
# Produit deux livrables dans .\installer\Output :
#
#   StudioIA-Setup.exe   — l'application complète (code + runtime + ffmpeg +
#                          assets + ComposIA). PAS les modèles IA.
#   StudioIA-Models.exe  — payload modèles Ollama (qwen2.5:7b + mistral),
#                          installé dans %USERPROFILE%\StudioIA\.ollama\models
#                          (créé seulement si .\bundle-models\ est présent).
#
# Prérequis :
#   * Rust buildé : .\src-tauri\target\release\studioia-shell.exe
#   * runtime      : .\runtime\python\python.exe
#   * Inno Setup 6 : ISCC.exe (détecté ou via -Iscc <chemin>)
#
# Usage :
#   .\installer\build_installer.ps1            # tout (Setup + Models si bundle)
#   .\installer\build_installer.ps1 -Setup     # uniquement l'app
#   .\installer\build_installer.ps1 -Models    # uniquement le payload modèles
#   .\installer\build_installer.ps1 -SkipShellBuild   # si le shell est déjà buildé
# ============================================================================

param(
    [switch]$Setup = $false,          # Force le livrable app
    [switch]$Models = $false,         # Force le livrable modèles
    [switch]$SkipShellBuild = $false, # Ne pas rebuild le shell Tauri
    [string]$Iscc = "",               # Chemin explicite vers ISCC.exe
    [string]$Version = ""             # Version (ex "1.1.0") ; sinon lue depuis tauri.conf.json
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$root = Split-Path -Parent $scriptDir   # C:\StudioIA-Desktop
Set-Location $root
# Cargo n'est pas dans le PATH PowerShell par défaut (rustup → %USERPROFILE%\.cargo\bin).
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path

# ---------------------------------------------------------------------------
# Détection d'ISCC.exe (Inno Setup 6)
# ---------------------------------------------------------------------------
function Find-Iscc {
    if ($Iscc -and (Test-Path $Iscc)) { return $Iscc }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "ISCC.exe introuvable. Installe Inno Setup 6 (winget install JRSoftware.InnoSetup) ou passe -Iscc <chemin>."
}

# ---------------------------------------------------------------------------
# Déterminer quels livrables construire
# ---------------------------------------------------------------------------
if (-not $Setup -and -not $Models) {
    # Par défaut : Setup toujours, Models seulement si le bundle existe.
    $Setup = $true
    $Models = (Test-Path "$root\bundle-models")
    if ($Models) { Write-Host "Bundle modèles détecté : le livrable Models sera construit." -ForegroundColor Cyan }
}

# ---------------------------------------------------------------------------
# Vérifier les prérequis communs
# ---------------------------------------------------------------------------
$shell = "$root\src-tauri\target\release\studioia-shell.exe"
$python = "$root\runtime\python\python.exe"

if ($Setup) {
    if (-not (Test-Path $python)) { throw "Runtime introuvable : $python. Construis d'abord le runtime (scripts\build.ps1)." }

    if (-not (Test-Path $shell)) {
        if ($SkipShellBuild) {
            throw "Shell introuvable : $shell (et -SkipShellBuild). Construis-le d'abord."
        }
        Write-Host "Shell Tauri introuvable → build release en cours (cargo build --release)…" -ForegroundColor Yellow
        Push-Location "$root\src-tauri"
        cargo build --release | Out-Host
        Pop-Location
        if (-not (Test-Path $shell)) { throw "Le build du shell a échoué." }
    }
}

# ---------------------------------------------------------------------------
# Compiler chaque livrable
# ---------------------------------------------------------------------------
$iscc = Find-Iscc
Write-Host "ISCC : $iscc" -ForegroundColor Cyan

function Invoke-Inno {
    param([switch]$WithModels)
    $flags = "/dMODELS_ONLY=$(if ($WithModels) {1} else {0})", "/dAppVersion=$Version", "/dSrcDir=$scriptDir\"
    $args = @($flags) + @("$scriptDir\studioia.iss")
    & $iscc $args
    if ($LASTEXITCODE -ne 0) { throw "Échec de la compilation Inno (exit $LASTEXITCODE)." }
}

# ---------------------------------------------------------------------------
# Résoudre la version (param -Version sinon lue dans src-tauri/tauri.conf.json)
# ---------------------------------------------------------------------------
if (-not $Version) {
    $conf = Get-Content "$root\src-tauri\tauri.conf.json" -Raw | ConvertFrom-Json
    $Version = $conf.version
    Write-Host "Version lue dans tauri.conf.json : $Version" -ForegroundColor Cyan
}

if ($Setup) {
    Write-Host "`n=== Livrable : StudioIA-Setup.exe (v$Version) ===" -ForegroundColor Green
    Invoke-Inno
}
if ($Models) {
    Write-Host "`n=== Livrable : StudioIA-Models.exe ===" -ForegroundColor Green
    Invoke-Inno -WithModels
}

# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------
Write-Host "`n=== Récapitulatif ===" -ForegroundColor Green
Get-ChildItem "$root\installer\Output" -Filter *.exe -ErrorAction SilentlyContinue |
    ForEach-Object {
        $go = [math]::Round($_.Length / 1GB, 2)
        $mb = [math]::Round($_.Length / 1MB, 1)
        $limite = if ($go -gt 2.0) { "  ⚠ DÉPASSE 2 Go (limite GitHub)" } else { "" }
        Write-Host ("  {0}  {1} Mo ({2} Go){3}" -f $_.Name, $mb, $go, $limite)
    }
Write-Host ""
Write-Host "Terminé." -ForegroundColor Green
