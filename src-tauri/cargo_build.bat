@echo off
title StudioIA - compilation du shell Tauri
cd /d "%~dp0"

if not exist "%USERPROFILE%\.cargo\bin\cargo.exe" (
    echo cargo introuvable. Installez Rust : winget install Rustlang.Rustup
    exit /b 1
)

set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"

echo Compilation du shell StudioIA (1ere fois: plusieurs minutes)...
call cargo build %*
echo.
echo Termine. Binaire : src-tauri\target\debug\studioia-shell.exe
