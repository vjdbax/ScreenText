@echo off
setlocal
title ScreenText Helper Compiler

echo ===================================================
echo             ScreenText Helper Compiler
echo ===================================================

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in system PATH.
    pause
    exit /b
)

:: ---- Step 1: Pre-download EasyOCR models ----
echo.
echo [1/3] Pre-downloading EasyOCR models...
echo This ensures models are bundled and no download needed on target PC.
python download_models.py
if %errorlevel% neq 0 (
    echo [WARNING] Model download failed. OCR may not work on target PC.
    echo Continuing with compilation...
)

:: ---- Step 2: Install PyInstaller if needed ----
echo.
echo [2/3] Checking PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller
) else (
    echo PyInstaller is already installed.
)

:: ---- Step 3: Compile ----
echo.
echo [3/3] Compiling... Please wait, this takes 3-5 minutes.
echo Do not close this window!
echo ---------------------------------------------------

if exist "easyocr_models" (
    pyinstaller --noconsole --onedir --paths=src ^
        --name="ScreenTextHelper" ^
        --icon="assets/icon.ico" ^
        --add-data "assets;assets" ^
        --add-data "easyocr_models;easyocr_models" ^
        --collect-all easyocr ^
        run.py
) else (
    pyinstaller --noconsole --onedir --paths=src ^
        --name="ScreenTextHelper" ^
        --icon="assets/icon.ico" ^
        --add-data "assets;assets" ^
        --collect-all easyocr ^
        run.py
)

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [SUCCESS] Compilation completed!
    echo App folder: dist\ScreenTextHelper\
    echo Run: dist\ScreenTextHelper\ScreenTextHelper.exe
    echo ===================================================
) else (
    echo.
    echo [ERROR] Compilation failed.
)

pause
endlocal
