@echo off
cd /d "%~dp0"
title WF-Cephy: Desktop Companion (Embedded Standalone)

echo =====================================================================
echo             WF-Cephy: Desktop Companion Pet
echo        Embedded Standalone Engine - Gemma 4 E2B
echo =====================================================================
echo.

echo [1/2] Detecting standalone Python GUI runtime...
set "PY_EXE="
set "PYW_EXE="

if exist "python_embed\python.exe" (
    python_embed\python.exe -c "import PyQt6" >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=python_embed\python.exe"
        set "PYW_EXE=python_embed\pythonw.exe"
    ) else (
        python_embed\python.exe -c "import PySide6" >nul 2>&1
        if not errorlevel 1 (
            set "PY_EXE=python_embed\python.exe"
            set "PYW_EXE=python_embed\pythonw.exe"
        )
    )
)

if "%PY_EXE%"=="" (
    python -c "import PyQt6" >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=python"
        set "PYW_EXE=pythonw"
    ) else (
        python -c "import PySide6" >nul 2>&1
        if not errorlevel 1 (
            set "PY_EXE=python"
            set "PYW_EXE=pythonw"
        )
    )
)

if "%PY_EXE%"=="" (
    echo [ERROR] Neither PyQt6 nor PySide6 was found in portable or system Python.
    echo.
    echo [GUIDE] Please install the required dependencies by running:
    echo     pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo [OK] Standalone GUI runtime verified (%PY_EXE%).
rem Model missing or under 1GB: download here first. Zero-padded string compare, as cmd ints overflow at 2GB.
for %%A in ("models\google_gemma-4-E2B-it-Q4_K_M.gguf") do set "MODEL_PAD=0000000000000%%~zA"
if "%MODEL_PAD:~-13%" LSS "0001000000000" (
    %PY_EXE% scripts\embedded_llm_runner.py --download
    if errorlevel 1 (
        echo [ERROR] Model download failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

echo.
echo [2/2] Launching Desktop Pet Companion (Background Windowless Mode)...
echo - Floating Pet will appear at the bottom-right of your screen.
echo - Global Hotkeys: [Alt+Q] Screen Capture Diagnosis, [Alt+W] Toggle Cephy Chat
echo =====================================================================

start "" %PYW_EXE% main_companion.py
timeout /t 2 >nul
exit /b 0
