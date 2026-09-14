@echo off
setlocal
title ScreenText Helper Launcher
chcp 65001 >nul

:: Allow --force flag to force reinstall
set "FORCE="
if /i "%1"=="--force" set FORCE=1
if /i "%1"=="-f" set FORCE=1

echo ===================================================
echo             ScreenText Helper Launcher
echo ===================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python and add it to PATH.
    pause
    exit /b
)

if defined FORCE (
    echo [INFO] Force reinstall mode.
    if exist ".installed_marker" del ".installed_marker"
)

if not exist ".installed_marker" (
    echo [1/2] Installing dependencies...
    echo This may take a few minutes...
    python -m pip install --upgrade pip >nul 2>&1
    python -m pip install -r requirements.txt
    
    if %errorlevel% equ 0 (
        echo. > ".installed_marker"
        echo [SUCCESS] Libraries installed.
    ) else (
        echo [WARNING] Some libraries could not be installed. Check your internet connection.
        echo The program will start, but OCR/translation features may be limited.
    )
) else (
    if defined FORCE (
        echo [1/2] Reinstalling dependencies...
        python -m pip install -r requirements.txt
        if %errorlevel% equ 0 (
            echo [SUCCESS] Libraries reinstalled.
        ) else (
            echo [WARNING] Some libraries could not be reinstalled.
        )
    ) else (
        echo [1/2] Dependencies are already checked.
    )
)

echo.
echo [2/2] Launching ScreenText Helper...
echo ---------------------------------------------------
python run.py

if %errorlevel% neq 0 (
    echo.
    echo [CRASH] Application crashed. Check the log file.
    pause
)

endlocal
