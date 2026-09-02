@echo off
REM Modrinth Collection Downloader - native Windows launcher
REM ============================================================
REM Thin .bat wrapper around modrinth_dl.ps1. No Python involved:
REM PowerShell already ships with every Windows 10/11 install, so this
REM works out of the box, double-click or from the command line.
REM
REM Usage examples:
REM   modrinth_dl.bat
REM   modrinth_dl.bat -Collection N6yU1DBr -McVersion 1.21.1 -Loader fabric -Dest .\out -Zip -Yes
REM   modrinth_dl.bat -Collection N6yU1DBr -ListItems
REM   modrinth_dl.bat -Help

setlocal
set "SCRIPT_DIR=%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
    echo [ERROR] PowerShell was not found on PATH. It ships with Windows by
    echo         default - if you removed or renamed it, reinstall/repair it
    echo         from Windows Features before using this tool.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%modrinth_dl.ps1" %*
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% NEQ 0 (
    echo.
    echo The script exited with an error ^(code %EXIT_CODE%^).
    pause
)

exit /b %EXIT_CODE%
