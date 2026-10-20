@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title WF-Optimizer - Gemma 4 E4B Standalone Portable

echo =====================================================================
echo           Warframe Build and Synergy Optimizer [WF-Optimizer]
echo                 Standalone Portable - Gemma 4 E4B
echo =====================================================================
echo.

REM 1. Embedded Python Detection
if exist "python_embed\python.exe" (
    set "PY_CMD=python_embed\python.exe"
    echo [1/3] Embedded Python detected. Zero Setup Mode.
) else (
    set "PY_CMD=python"
    echo [1/3] System Python detected.
)

REM 2. Embedded Model Verification
echo.
if exist "models\gemma-2-2b-it-Q4_K_M.gguf" (
    echo [2/3] Embedded Gemma 2 2B model detected. No download or install required!
) else (
    echo [2/3] Checking Ollama fallback service...
    curl -s http://localhost:11434 >nul 2>&1
    if errorlevel 1 (
        echo [Notice] Starting Ollama background service...
        start /b ollama serve >nul 2>&1
        timeout /t 3 /nobreak >nul 2>&1
    )
)

REM 3. Launch Optimizer Server & Open Web UI
echo.
echo [3/3] Starting optimizer engine and web interface...
echo Opening Web UI at: http://localhost:5000
echo.
echo Server is running. To close, press Ctrl+C or close this window.
echo =====================================================================
echo.

%PY_CMD% scripts\app_server.py

if errorlevel 1 (
    echo.
    echo [ERROR] Server terminated with an error code: !errorlevel!
)

echo.
echo [WF-Optimizer] Execution finished. Press any key to exit...
pause >nul
