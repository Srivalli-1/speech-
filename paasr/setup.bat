@echo off
REM setup.bat -- PAASR one-time setup for Windows
REM Run this from the paasr\ directory (double-click or right-click > Open in Terminal).
REM Uses CMD, not PowerShell, to avoid execution-policy issues.

setlocal EnableDelayedExpansion

echo.
echo ============================================================
echo  PAASR Setup Script
echo  Phonology-Aware Adaptive Speech Representation Framework
echo ============================================================
echo.

REM ── 1. Check Python version ───────────────────────────────────────────────
echo [1/5] Checking Python version ...
python --version 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Python not found on PATH.
    echo Please install Python 3.11 (64-bit) from:
    echo   https://www.python.org/downloads/release/python-3119/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Require Python 3.11 or newer.
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Python version detected: %PYVER%

REM Extract major and minor version parts
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)

if "%PYMAJ%" NEQ "3" (
    echo.
    echo [ERROR] Python 3.11 is required. Found Python %PYVER%.
    echo Download Python 3.11 from https://www.python.org/downloads/
    echo Use Python 3.11 or newer.
    pause
    exit /b 1
)

if %PYMIN% LSS 11 (
    echo.
    echo [ERROR] Python 3.11+ is required. Found Python %PYVER%.
    echo Download Python 3.11 from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python %PYVER% found.
echo.

REM ── 2. Create virtual environment ────────────────────────────────────────
echo [2/5] Creating virtual environment (.venv) ...
if exist .venv (
    echo [INFO] .venv already exists. Skipping creation.
) else (
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
)
echo.

REM ── 3. Upgrade pip ────────────────────────────────────────────────────────
echo [3/5] Upgrading pip ...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] pip upgrade failed. Continuing anyway.
)
echo [OK] pip upgraded.
echo.

REM ── 4. Install requirements ───────────────────────────────────────────────
echo [4/5] Installing requirements ...
echo This may take a few minutes.
.venv\Scripts\pip.exe install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Requirements installation failed.
    echo Check requirements.txt and your internet connection.
    echo Try running:  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo [OK] All requirements installed.
echo.

REM ── 5. Run check_setup.py ─────────────────────────────────────────────────
echo [5/5] Running setup verification ...
.venv\Scripts\python.exe check_setup.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARN] Some checks failed. Review the output above.
    echo You may still be able to run the app, but some features may not work.
) else (
    echo [OK] All checks passed.
)
echo.

REM ── Done ──────────────────────────────────────────────────────────────────
echo ============================================================
echo  Setup complete!
echo.
echo  NEXT STEPS:
echo    1. Double-click  run.bat  to start the app.
echo    2. Open http://127.0.0.1:7860 in your browser.
echo.
echo  INTERNET NOTE:
echo    Google Speech Recognition and Google Translate require internet access.
echo    Speech and transcript text are sent to Google for processing.
echo    No API key is required; English speech synthesis is local.
echo ============================================================
echo.
pause
