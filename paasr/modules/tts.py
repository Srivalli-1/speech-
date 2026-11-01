"""Local text-to-speech for English output using the platform speech engine."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Tuple

import config
from modules.utils import logger

_last_tts_file: Path | None = None


def _cleanup_last_temp() -> None:
    """Delete the previous TTS temp file if it still exists."""
    global _last_tts_file
    if _last_tts_file is not None and _last_tts_file.exists():
        try:
            _last_tts_file.unlink()
            logger.debug("Cleaned up temp TTS file: %s", _last_tts_file)
        except OSError:
            logger.exception("Could not delete temp TTS file %s.", _last_tts_file)
    _last_tts_file = None


def _make_temp_path(suffix: str) -> Path:
    """Create a temporary file path (file not yet created)."""
    fd, tmp_str = tempfile.mkstemp(suffix=suffix, prefix="paasr_tts_")
    os.close(fd)
    return Path(tmp_str)


def _synthesise_pyttsx3(text: str) -> Path:
    """Synthesize speech locally with the platform's installed engine."""
    import pyttsx3

    out_path = _make_temp_path(".wav")
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", config.TTS_PYTTSX3_RATE)
        engine.setProperty("volume", config.TTS_PYTTSX3_VOLUME)
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
        try:
            engine.stop()
        except Exception:
            logger.exception("Could not stop the pyttsx3 engine after synthesis.")
        logger.info("Local pyttsx3 synthesis complete: %s", out_path.name)
        return out_path
    except Exception as exc:
        if out_path.exists():
            out_path.unlink(missing_ok=True)
        raise RuntimeError(f"Local pyttsx3 synthesis failed: {exc}") from exc


def synthesise_speech(english_text: str) -> Tuple[str, str]:
    """Synthesize English speech without contacting an external service."""
    global _last_tts_file

    if not english_text or not english_text.strip():
        raise ValueError("TTS input is empty.")

    _cleanup_last_temp()
    started = time.time()
    try:
        audio_path = _synthesise_pyttsx3(english_text)
    except Exception as exc:
        logger.exception("Local pyttsx3 synthesis failed.")
        raise RuntimeError(
            "Local speech synthesis failed. Ensure pyttsx3 and a supported "
            "speech engine are available (Windows SAPI5 or Linux eSpeak). "
            f"Detail: {exc}"
        ) from exc

    _last_tts_file = audio_path
    info = (
        f"TTS: pyttsx3 (local platform voice) | "
        f"Synthesis time: {time.time() - started:.1f}s"
    )
    logger.info(info)
    return str(audio_path), info
