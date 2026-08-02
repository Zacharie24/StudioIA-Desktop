@echo off
REM ============================================
REM StudioIA-Next — Lanceur automatique
REM ============================================
TITLE StudioIA-Next
cd /d "C:\StudioIA-Desktop"

:MENU
cls
echo ============================================
echo   StudioIA-Next — Menu Principal
echo ============================================
echo.
echo  1) Lancer le Dashboard Web (recommande)
echo  2) Lancer l'interface graphique (GUI)
echo  3) Executer le pipeline automatique
echo  4) Diagnostic systeme
echo  5) Configuration rapide
echo  6) Quitter
echo.
set /p choix="Choix (1-6): "

if "%choix%"=="1" goto WEB
if "%choix%"=="2" goto GUI
if "%choix%"=="3" goto AUTO
if "%choix%"=="4" goto DIAG
if "%choix%"=="5" goto CONFIG
if "%choix%"=="6" goto QUIT
goto MENU

:WEB
cls
echo ============================================
echo   StudioIA-Next — Dashboard Web
echo ============================================
echo.
echo  Diagnostic en cours...
python -c "from modules.diagnostic import executer_diagnostic; executer_diagnostic()"
echo.
echo  Demarrage du serveur web...
echo.
echo  Ouvre http://127.0.0.1:8080 dans ton navigateur
echo  (Ctrl+C pour arreter)
echo.
python -m uvicorn web.main:app --host 127.0.0.1 --port 8080
echo.
echo  Appuie sur une touche pour revenir au menu...
pause >nul
goto MENU

:GUI
cls
echo ============================================
echo   StudioIA-Next — Interface Graphique
echo ============================================
echo.
python app_gui.py
echo.
echo  Appuie sur une touche pour revenir au menu...
pause >nul
goto MENU

:AUTO
cls
echo ============================================
echo   Pipeline Automatique
echo ============================================
echo.
echo  Mode:
echo  1) Preview (analyser seulement)
echo  2) Production complete
echo.
set /p mode="Choix (1-2): "

if "%mode%"=="1" (
    python -c "from modules.automation.pipeline import executer_pipeline; import json; r=executer_pipeline(force_generer=False); print(json.dumps(r, ensure_ascii=False, indent=2))"
) else if "%mode%"=="2" (
    echo.
    echo  ATTENTION: La production complete va generer du contenu.
    set /p confirm="Confirmer (o/N): "
    if /i "!confirm!"=="o" (
        python -c "from modules.automation.pipeline import executer_pipeline; import json; r=executer_pipeline(force_generer=True); print(json.dumps(r, ensure_ascii=False, indent=2))"
    ) else (
        echo Annule.
    )
) else (
    echo Choix invalide.
)
echo.
echo  Appuie sur une touche pour revenir au menu...
pause >nul
goto MENU

:DIAG
cls
echo ============================================
echo   Diagnostic Systeme
echo ============================================
echo.
python -c "from modules.diagnostic import executer_diagnostic; executer_diagnostic()"
echo.
echo  Appuie sur une touche pour revenir au menu...
pause >nul
goto MENU

:CONFIG
cls
echo ============================================
echo   Configuration Rapide
echo ============================================
echo.
echo  Quelques configurations depuis le terminal.
echo  Pour une config complete, utilise le Dashboard Web.
echo.
echo  1) Voir la configuration actuelle
echo  2) Definir la cle YouTube API
echo  3) Definir la cle Pexels API
echo  4) Changer le profil actif
echo  5) Retour
echo.
set /p ccfg="Choix (1-5): "

if "%ccfg%"=="1" (
    python -c "import json; print(json.dumps(json.load(open('config.json','r')), ensure_ascii=False, indent=2))"
    pause
) else if "%ccfg%"=="2" (
    set /p ytkey="Cle YouTube API: "
    python -c "import json; c=json.load(open('config.json','r')); c['youtube_api_key']='%ytkey%'; json.dump(c, open('config.json','w'), ensure_ascii=False, indent=2); print('OK')"
    pause
) else if "%ccfg%"=="3" (
    set /p pxkey="Cle Pexels API: "
    python -c "import json; c=json.load(open('config.json','r')); c['pexels_api_key']='%pxkey%'; json.dump(c, open('config.json','w'), ensure_ascii=False, indent=2); print('OK')"
    pause
) else if "%ccfg%"=="4" (
    python -c "
import json
c=json.load(open('config.json','r'))
from core.profiles.profile_manager import get_manager
m=get_manager()
print('Profil actuel:', c.get('profil_actif','?'))
p=m.lister_profils()
for i,pr in enumerate(p):
    print(f'  {i+1}) {pr.get(\"manifest\",{}).get(\"name\",pr[\"id\"])} ({pr[\"id\"]})')
"
    set /p psel="Numero du profil: "
    python -c "
import json; c=json.load(open('config.json','r'))
from core.profiles.profile_manager import get_manager
ps=get_manager().lister_profils()
i=int('%psel%')-1
if i>=0 and i<len(ps):
    c['profil_actif']=ps[i]['id']
    json.dump(c, open('config.json','w'), ensure_ascii=False, indent=2)
    print('Profil change vers:', ps[i]['id'])
else:
    print('Choix invalide')
"
    pause
)
goto CONFIG

:QUIT
cls
echo   Au revoir !
timeout /t 2 >nul
exit /b 0
