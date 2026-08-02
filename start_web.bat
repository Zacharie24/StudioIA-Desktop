@echo off
REM StudioIA-Next — Lancement rapide du Dashboard Web
cd /d "C:\StudioIA-Desktop"
TITLE StudioIA-Next Dashboard
echo.
echo === StudioIA-Next Web Dashboard ===
echo.
REM Tuer les anciens serveurs uvicorn (evite les 500 sur du vieux code)
echo Nettoyage des anciens serveurs...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'uvicorn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }"
timeout /t 1 /nobreak >nul
echo.
echo Diagnostic en cours...
python -c "from modules.diagnostic import executer_diagnostic; executer_diagnostic()"
echo.
echo Demarrage du serveur sur http://127.0.0.1:8080
echo.
python -m uvicorn web.main:app --host 127.0.0.1 --port 8080
pause
