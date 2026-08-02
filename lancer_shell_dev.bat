@echo off
title StudioIA (shell Tauri dev)
cd /d "C:\StudioIA-Desktop"

echo ========================================
echo   StudioIA - Shell natif (mode dev)
echo ========================================
echo.

set "APP=src-tauri\target\debug\studioia-shell.exe"
if not exist "%APP%" (
    echo Binaire non compile. Lancement de cargo build...
    call src-tauri\cargo_build.bat 2>nul
    if not exist "%APP%" (
        echo Compilation impossible. Verifiez Rust et la toolchain MSVC.
        pause
        exit /b 1
    )
)

echo Lancement du shell (le backend demarre automatiquement)...
"%APP%"

echo.
echo Shell ferme - backend arrete.
pause
