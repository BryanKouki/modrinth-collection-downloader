@echo off
setlocal

echo ============================================
echo  Modrinth Collection Downloader - Build EXE
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH. Install Python 3.10+ and check "Add to PATH".
    pause
    exit /b 1
)

echo.
echo [1/3] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo [2/3] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ModrinthCollectionDownloader.spec del /q ModrinthCollectionDownloader.spec

set ICON_ARG=
if exist icon.ico set ICON_ARG=--icon=icon.ico

echo.
echo [3/3] Building the executable with PyInstaller...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ModrinthCollectionDownloader" ^
    --collect-all customtkinter ^
    %ICON_ARG% ^
    main.py

echo.
if exist dist\ModrinthCollectionDownloader.exe (
    echo Build finished! The executable is at: dist\ModrinthCollectionDownloader.exe
) else (
    echo [ERROR] The build failed. Check the messages above.
)

pause
