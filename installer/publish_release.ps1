# ============================================================================
# publish_release.ps1 — Publie une release StudioIA sur GitHub Releases
# ============================================================================
# Construit le shell (si besoin), le Setup.exe Inno, le signe, genère le
# manifest updater (latest.json) puis crée la release GitHub.
#
# Usage :
#   .\installer\publish_release.ps1 -Version 1.1.0 -Notes "Corrections audio"
#   .\installer\publish_release.ps1 -Version 1.1.0 -SkipBuild   # réutilise le Setup.exe déjà construit
#
# Prérequis : gh CLI authentifié, clés updater dans installer\keys\.
# Les secrets (installer\keys\) sont gitignorés et ne partent pas au repo.
# ============================================================================

param(
    [Parameter(Mandatory = $true)]
    [string]$Version,          # ex "1.1.0"
    [string]$Notes = "",       # notes de version
    [switch]$SkipBuild = $false  # réutilise le Setup.exe déjà présent (pas de recompil)
)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$root = Split-Path -Parent $scriptDir
# Cargo n'est pas dans le PATH PowerShell par défaut (rustup → %USERPROFILE%\.cargo\bin).
$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
$keysDir = "$root\installer\keys"
$releaseDir = "$root\installer\Output"
$setup = Join-Path $releaseDir "StudioIA-Setup.exe"
$repo = "Zacharie24/StudioIA-Desktop"
$tag = "v$Version"

Write-Host "=== Publication StudioIA $Version ($tag) ===" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1) Mettre à jour la version partout (tauri.conf.json + Cargo.toml)
# ---------------------------------------------------------------------------
function Set-VersionInFiles {
    param([string]$v)
    $conf = "$root\src-tauri\tauri.conf.json"
    (Get-Content $conf -Raw) -replace '("version"\s*:\s*")[^"]*(")', "`${1}$v`$2" |
        Set-Content $conf -Encoding UTF8 -NoNewline
    $cargo = "$root\src-tauri\Cargo.toml"
    (Get-Content $cargo -Raw) -replace '(?m)^(version\s*=\s*")[^"]*(")', "`${1}$v`$2" |
        Set-Content $cargo -Encoding UTF8 -NoNewline
    Write-Host "Version écrite : $v" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 2) Appliquer la version, puis construire (optionnel) le shell + le Setup.exe
# ---------------------------------------------------------------------------
Set-VersionInFiles $Version

if (-not $SkipBuild) {
    Write-Host "`n--- Build du shell (cargo build --release) ---"
    Push-Location "$root\src-tauri"
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "Échec cargo build --release" }
    Pop-Location

    Write-Host "`n--- Build du Setup.exe (Inno) ---"
    & "$scriptDir\build_installer.ps1" -Setup -SkipShellBuild -Version $Version
}

if (-not (Test-Path $setup)) { throw "Setup.exe introuvable : $setup" }

# ---------------------------------------------------------------------------
# 3) Signer le Setup.exe (tauri signer) pour l'updater
# ---------------------------------------------------------------------------
$keyPath = Join-Path $keysDir "updater.key"
$pass = (Get-Content (Join-Path $keysDir "updater.pass") -Raw).Trim()
if (-not (Test-Path $keyPath)) { throw "Clé privée updater introuvable : $keyPath" }

Write-Host "`n--- Signature du Setup.exe (tauri signer) ---"
Push-Location "$root\src-tauri"
npx tauri signer sign "$setup" -k $keyPath -p $pass
if ($LASTEXITCODE -ne 0) { throw "Échec tauri signer sign" }
Pop-Location

$setupSig = "$setup.sig"
if (-not (Test-Path $setupSig)) { throw "Signature non générée : $setupSig" }
$signature = (Get-Content $setupSig -Raw).Trim()
Write-Host ("Signature OK (" + $signature.Length + " chars)")

# ---------------------------------------------------------------------------
# 4) Générer le manifest updater (latest.json)
# ---------------------------------------------------------------------------
$pubDate = [DateTime]::UtcNow.ToString("o")
$assetUrl = "https://github.com/$repo/releases/download/$tag/StudioIA-Setup.exe"
$manifest = [ordered]@{
    version = $Version
    notes   = $Notes
    pub_date = $pubDate
    platforms = [ordered]@{
        "windows-x86_64" = [ordered]@{
            signature = $signature
            url       = $assetUrl
        }
    }
}
$latestJson = Join-Path $releaseDir "latest.json"
$manifest | ConvertTo-Json -Depth 10 | Set-Content $latestJson -Encoding UTF8
Write-Host "`nManifest écrit : $latestJson"

# ---------------------------------------------------------------------------
# 5) Créer la release GitHub
# ---------------------------------------------------------------------------
Write-Host "`n--- Création de la release $tag ---"
$assets = @($setup, "$setup.sig", $latestJson)
$notesText = "StudioIA $Version`n`n$Notes"
$ghArgs = @($tag) + $assets + @(
    "--repo", $repo,
    "--title", "StudioIA $Version",
    "--notes", $notesText
)
& gh release create @ghArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "gh release create a échoué (exit $LASTEXITCODE). Si une release $tag existe déjà, relance avec -SkipBuild pour ---clobber." -ForegroundColor Yellow
    throw "Échec gh release create"
}

Write-Host "`n=== Release $tag publiée : https://github.com/$repo/releases/tag/$tag ===" -ForegroundColor Green
Write-Host "L'updater pointe sur /releases/latest/download/latest.json → une app plus ancienne se mettra à jour vers $version."