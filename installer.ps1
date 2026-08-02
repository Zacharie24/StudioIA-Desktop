# ============================================================
# STUDIO IA — INSTALLATEUR AUTOMATIQUE
# A lancer sur un nouvel ordinateur pour tout installer
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   STUDIO IA - INSTALLATION AUTOMATIQUE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Verifier($nom, $commande) {
    try {
        $null = Invoke-Expression $commande 2>&1
        Write-Host "  [OK] $nom deja installe" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "  [MANQUANT] $nom" -ForegroundColor Yellow
        return $false
    }
}

# 1. Verifier Python
Write-Host "[1/6] Verification Python..." -ForegroundColor Yellow
$python_ok = Verifier "Python" "python --version"
if (-not $python_ok) {
    Write-Host "  Telecharge Python sur : https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "  IMPORTANT : coche 'Add Python to PATH' pendant l'installation" -ForegroundColor Red
    Start-Process "https://www.python.org/downloads/"
    Read-Host "  Appuie sur Entree une fois Python installe"
}

# 2. Verifier/Installer Ollama
Write-Host ""
Write-Host "[2/6] Verification Ollama..." -ForegroundColor Yellow
$ollama_ok = Verifier "Ollama" "ollama --version"
if (-not $ollama_ok) {
    Write-Host "  Ouverture de la page de telechargement Ollama..." -ForegroundColor Yellow
    Start-Process "https://ollama.com/download/windows"
    Read-Host "  Appuie sur Entree une fois Ollama installe"
}

# 3. Telecharger modele Ollama
Write-Host ""
Write-Host "[3/6] Telechargement modele Mistral..." -ForegroundColor Yellow
ollama pull mistral

# 4. Verifier FFmpeg
Write-Host ""
Write-Host "[4/6] Verification FFmpeg..." -ForegroundColor Yellow
$ffmpeg_path = "C:\\StudioIA-Next\tools\ffmpeg\ffmpeg.exe"
if (Test-Path $ffmpeg_path) {
    Write-Host "  [OK] FFmpeg deja present" -ForegroundColor Green
} else {
    Write-Host "  [MANQUANT] FFmpeg" -ForegroundColor Yellow
    Write-Host "  1. Telecharge : https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -ForegroundColor Yellow
    Write-Host "  2. Extrais le ZIP" -ForegroundColor Yellow
    Write-Host "  3. Copie ffmpeg.exe, ffprobe.exe, ffplay.exe dans : C:\\StudioIA-Next\tools\ffmpeg\" -ForegroundColor Yellow
    Start-Process "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    Read-Host "  Appuie sur Entree une fois FFmpeg copie"
}

# 5. Installer dependances Python
Write-Host ""
Write-Host "[5/6] Installation librairies Python..." -ForegroundColor Yellow
pip install --break-system-packages requests pillow pydub numpy 2>$null
pip install requests pillow pydub numpy

Write-Host "  [OK] Librairies Python installees" -ForegroundColor Green

# 6. Verifier structure dossiers
Write-Host ""
Write-Host "[6/6] Verification structure StudioIA..." -ForegroundColor Yellow
$dossiers = @(
    "C:\\StudioIA-Next\modules\brain\prompt_templates",
    "C:\\StudioIA-Next\modules\tts",
    "C:\\StudioIA-Next\modules\video",
    "C:\\StudioIA-Next\modules\images",
    "C:\\StudioIA-Next\modules\thumbnail\templates",
    "C:\\StudioIA-Next\assets\backgrounds",
    "C:\\StudioIA-Next\assets\overlays",
    "C:\\StudioIA-Next\assets\music",
    "C:\\StudioIA-Next\assets\fonts",
    "C:\\StudioIA-Next\assets\logos",
    "C:\\StudioIA-Next\projects",
    "C:\\StudioIA-Next\temp",
    "C:\\StudioIA-Next\logs",
    "C:\\StudioIA-Next\tools\ffmpeg"
)
foreach ($d in $dossiers) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
Write-Host "  [OK] Structure de dossiers creee" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   INSTALLATION TERMINEE !" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Pour optionnel (GIMP, Docker/Penpot) :" -ForegroundColor Yellow
Write-Host "  - GIMP : https://www.gimp.org/downloads/" -ForegroundColor White
Write-Host "  - Docker : https://www.docker.com/products/docker-desktop/" -ForegroundColor White
Write-Host ""
Write-Host "  Lance maintenant : lancer_studio.bat" -ForegroundColor Cyan
Write-Host ""
Read-Host "Appuie sur Entree pour fermer"