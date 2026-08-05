@echo off
REM ============================================
REM StudioIA — Analyser & terminer les projets
REM ============================================
TITLE StudioIA - Completion Projets
cd /d "C:\StudioIA-Desktop"

REM Preferer le runtime Python embarque, sinon python du PATH
if exist "C:\StudioIA-Desktop\runtime\python\python.exe" (
    set "PY=C:\StudioIA-Desktop\runtime\python\python.exe"
) else (
    set "PY=python"
)

REM Le runtime embarque est en mode isole (-I) : il ignore le CWD et PYTHONPATH.
REM On insere donc explicitement la racine du projet dans sys.path avant d'importer.
set "BOOT=import sys; sys.path.insert(0, r'C:\StudioIA-Desktop'); "

echo ============================================
echo   Analyser & terminer les projets incomplets
echo ============================================
echo.
echo  Ce script analyse les projets, termine ceux qui sont
echo  recuperables (script, audio, images, montage, vignette)
echo  et supprime ceux qui ne peuvent pas etre finis.
echo.
echo  ATTENTION: Utilise Ollama/TTS, les generations peuvent
echo  prendre 10+ minutes par projet.
echo.

echo  --- Etape 1 : analyse (apercu, rien ne modifie) ---
"%PY%" -c "%BOOT%from modules.projets.completer import main; main()" --apercu
if errorlevel 1 (
    echo.
    echo  Erreur lors de l'analyse.
    pause
    exit /b 1
)

echo.
set /p confirm="Lancer la completion + suppression des echecs (o/N): "
if /i not "%confirm%"=="o" (
    echo Annule.
    pause
    exit /b
)

echo.
echo  --- Etape 2 : completion des recuperables + suppression des irrecuperables ---
"%PY%" -c "%BOOT%from modules.projets.completer import main; main()" --completer --supprimer-echecs

echo.
echo  Termine. Consulte le dashboard web pour les details.
echo.
pause
