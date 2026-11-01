"""
config.py — PAASR global configuration.

All tunables live here.  Values can be overridden by a .env file in the
project root (loaded by python-dotenv in app.py before anything else).
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Project root (one level up from this file) ────────────────────────────────
ROOT_DIR: Path = Path(__file__).parent.resolve()

# ── Data / log directories ────────────────────────────────────────────────────
DATA_DIR: Path = ROOT_DIR / "data"
LOG_DIR: Path = ROOT_DIR / "logs"
ASSETS_DIR: Path = ROOT_DIR / "assets"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE: Path = LOG_DIR / "app.log"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── SQLite survey database ────────────────────────────────────────────────────
DB_PATH: Path = DATA_DIR / "survey.db"

# ── Google Speech Recognition and Translate ───────────────────────────────────
GOOGLE_REQUEST_TIMEOUT_SECONDS: int = int(
    os.getenv("GOOGLE_REQUEST_TIMEOUT_SECONDS", "30")
)
GOOGLE_TRANSLATE_MAX_CHARS: int = 4500
SPEECH_TO_TRANSLATION_LANGUAGE: dict[str, str] = {"te": "Telugu"}

# Audio clip limits
AUDIO_MIN_DURATION_S: float = 0.5    # Shorter clips are likely silence.
AUDIO_MAX_DURATION_S: float = 120.0  # 2 minutes max per clip.

TRANSLATION_LANGUAGES: dict[str, str] = {
    "English": "en",
    "Hindi": "hi",
    "Telugu": "te",
}

# ── TTS ───────────────────────────────────────────────────────────────────────
TTS_PYTTSX3_RATE: int = 150          # Words per minute for offline fallback.
TTS_PYTTSX3_VOLUME: float = 0.9

# ── Gradio server ─────────────────────────────────────────────────────────────
GRADIO_SERVER_NAME: str = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
GRADIO_SERVER_PORT: int = int(
    os.getenv("PORT", os.getenv("GRADIO_SERVER_PORT", "10000"))
)
GRADIO_IN_BROWSER: bool = os.getenv("GRADIO_IN_BROWSER", "true").lower() == "true"
GRADIO_SHARE: bool = os.getenv("GRADIO_SHARE", "false").lower() == "true"

# ── App metadata ──────────────────────────────────────────────────────────────
APP_TITLE: str = "PAASR — Multilingual Voice & Text Translator"
APP_VERSION: str = "1.0.0"
