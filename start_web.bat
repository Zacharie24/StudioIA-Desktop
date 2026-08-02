@echo off
REM StudioIA — Lancement rapide du Dashboard Web
cd /d "C:\StudioIA-Desktop"
TITLE StudioIA Dashboard
echo.
echo === StudioIA Web Dashboard ===
echo.
REM Preferer le runtime Python embarque, sinon python du PATH
if exist "C:\StudioIA-Desktop\runtime\python\python.exe" (
    set "PY=C:\StudioIA-Desktop\runtime\python\python.exe"
) else (
    set "PY=python"
)
echo.
echo Nettoyage des anciens serveurs...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'uvicorn' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }"
timeout /t 1 /nobreak >nul
echo.
echo Demarrage du serveur sur http://127.0.0.1:8080
echo.
"%PY%" -m uvicorn web.main:app --host 127.0.0.1 --port 8080
pause
