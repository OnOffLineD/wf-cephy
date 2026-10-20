@echo off
cd /d "%~dp0"
title WF-Companion: Desktop Cephalon Ordis (Embedded Standalone)

echo =====================================================================
echo             WF-Companion: Desktop Cephalon Ordis Pet
echo        Embedded Standalone Engine - Gemma 2 2B (Zero-Setup)
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
    pause
    exit /b 1
)
echo [OK] Standalone GUI runtime verified (%PY_EXE%).

echo.
echo [2/2] Launching Desktop Pet Companion (Background Windowless Mode)...
echo - Floating Pet will appear at the bottom-right of your screen.
echo - Global Hotkeys: [Alt+Q] Screen Capture Diagnosis, [Alt+W] Toggle Ordis Chat
echo =====================================================================

start "" %PYW_EXE% main_companion.py
timeout /t 2 >nul
exit /b 0
