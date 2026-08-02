@echo off
title Studio IA
cd /d "C:\StudioIA-Desktop"
echo.
echo ========================================
echo   Lancement de StudioIA
echo ========================================
echo.
echo Choisissez votre interface:
echo [1] Interface Moderne (GUI avec CustomTkinter)
echo [2] Interface PowerShell (ancienne)
echo.
set /p choix="  Votre choix [1]: " || set choix=1

if "%choix%"=="1" (
    echo Lancement de l'interface moderne...
    python app_gui.py
) else (
    echo Lancement de l'interface PowerShell...
    powershell -ExecutionPolicy Bypass -File main.ps1
)

pause