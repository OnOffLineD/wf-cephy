@echo off
rem UTF-8 code page so the Korean prompt below renders (this file is saved as UTF-8).
chcp 65001 >nul
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
echo.
rem Default Y: a bare Enter keeps this value, as set /p leaves the variable untouched on empty input.
set "USE_LLM=Y"
set /p USE_LLM="로컬 LLM(Cephalon Ordis AI 대화 엔진)을 사용하시겠습니까? (Y/N) [기본값: Y]: "
set "LLM_FLAG=--enable-llm"
if /i "%USE_LLM%"=="N" goto skip_llm_download
rem The runner skips whatever is already present (llama-server.exe, model over 1GB).
%PY_EXE% scripts\embedded_llm_runner.py --download-bin --download-model
if errorlevel 1 (
    echo [ERROR] llama.cpp or model download failed. Check your internet connection and try again.
    pause
    exit /b 1
)
goto llm_ready
:skip_llm_download
set "LLM_FLAG=--disable-llm"
echo [INFO] Local LLM disabled. Mod diagnosis and damage formulas still work.
:llm_ready

echo.
echo [2/2] Launching Desktop Pet Companion (Background Windowless Mode)...
echo - Floating Pet will appear at the bottom-right of your screen.
echo - Global Hotkeys: [Alt+Q] Screen Capture Diagnosis, [Alt+W] Toggle Cephy Chat
echo =====================================================================

start "" %PYW_EXE% main_companion.py %LLM_FLAG%
timeout /t 2 >nul
exit /b 0
