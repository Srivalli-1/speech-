@echo off
REM run.bat -- Start the PAASR web app
REM Run this from the paasr\ directory after running setup.bat.

setlocal

REM ── Check venv exists ─────────────────────────────────────────────────────
if not exist .venv\Scripts\python.exe (
    echo [ERROR] Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM ── Set UTF-8 output so Python does not crash on Unicode paths ────────────
set PYTHONUTF8=1

REM ── Activate venv (updates PATH for this session) ────────────────────────
call .venv\Scripts\activate.bat

echo.
echo ============================================================
echo  PAASR -- Telugu-to-English Voice Translator
echo ============================================================
echo  Starting application ...
echo  Open http://127.0.0.1:7860 in your browser.
echo.
echo  Google Speech Recognition and Google Translate require internet access.
echo  Speech audio and transcript text will be sent to Google.
echo.
echo  Press Ctrl+C to stop the server.
echo ============================================================
echo.

python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] The app exited with an error.
    echo Check logs\app.log for details.
    pause
)
