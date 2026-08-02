@echo off
REM ============================================
REM StudioIA — Compléter les projets en cours
REM ============================================
TITLE StudioIA - Completion Projets
cd /d "C:\StudioIA-Desktop"

REM Preferer le runtime Python embarque, sinon python du PATH
if exist "C:\StudioIA-Desktop\runtime\python\python.exe" (
    set "PY=C:\StudioIA-Desktop\runtime\python\python.exe"
) else (
    set "PY=python"
)

echo ============================================
echo   Completion automatique des projets
echo ============================================
echo.
echo  Ce script va generer les scripts manquants
echo  pour tous les projets en cours.
echo.
echo  ATTENTION: Utilise Ollama, donc les generations
echo  peuvent prendre 1-2 minutes par projet.
echo.
set /p confirm="Continuer (o/N): "
if /i not "!confirm!"=="o" (
    echo Annule.
    pause
    exit /b
)

echo.
echo  Analyse des projets en cours...
"%PY%" -c "
import json
from pathlib import Path

projects_path = Path('projects')
pending = []

for p in sorted(projects_path.iterdir()):
    pjson = p / 'project.json'
    if not pjson.exists():
        continue
    try:
        with open(pjson, 'r', encoding='utf-8') as f:
            data = json.load(f)
        etapes = data.get('etapes', {})
        if etapes.get('video') == 'termine':
            continue  # deja termine

        # Verifier si le script est en attente
        script_status = data.get('etapes', {}).get('script', '')
        redaction_status = data.get('etapes', {}).get('redaction', '')

        if script_status == 'en_attente' or 'en_cours':
            pending.append(p.name)
            print(f'  [{p.name}] script: {script_status}, redaction: {redaction_status}')
    except:
        pass

print(f'\nProjets en attente de script: {len(pending)}')
print(f'Total en cours: ...')
"
echo.
echo  Pour lancer la generation:
echo    "%PY%" -c \"from modules.brain.generate_script import main; import sys; sys.argv=['gen.py','projects/NOM_PROJET']; main()\"
echo.
echo  Conseil: Lance le dashboard web pour suivre la progression.
echo.
pause
