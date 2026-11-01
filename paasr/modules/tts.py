"""Local text-to-speech for English output using the platform speech engine."""

from __future__ import annotations

import os
import platform
import shutil
import tempfile
import time
import wave
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
    engine = None
    try:
        if platform.system() == "Linux":
            if shutil.which("espeak") is None:
                raise RuntimeError(
                    "The Linux eSpeak executable is missing. Install "
                    "espeak, espeak-data, and libespeak1 in the Render build."
                )
            engine = pyttsx3.init(driverName="espeak")
        else:
            engine = pyttsx3.init()
        engine.setProperty("rate", config.TTS_PYTTSX3_RATE)
        engine.setProperty("volume", config.TTS_PYTTSX3_VOLUME)
        engine.save_to_file(text, str(out_path))
        engine.runAndWait()
    except Exception as exc:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(f"pyttsx3 synthesis failed: {exc}") from exc
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                logger.exception("Could not stop the pyttsx3 engine.")

    if not out_path.is_file() or out_path.stat().st_size == 0:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(
            "pyttsx3 completed without creating an audio file. "
            "Check that the Linux eSpeak engine and voice data are installed."
        )

    try:
        with wave.open(str(out_path), "rb") as audio_file:
            if audio_file.getnframes() == 0:
                raise wave.Error("generated audio contains no frames")
    except (OSError, EOFError, wave.Error) as exc:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(f"pyttsx3 created an invalid WAV file: {exc}") from exc

    return out_path


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
        logger.exception(
            "English TTS failed on %s for %d characters.",
            platform.system(),
            len(english_text),
        )
        raise RuntimeError(
            "English audio generation failed. On Render, verify the build "
            "installed espeak, espeak-data, and libespeak1. "
            f"Detail: {exc}"
        ) from exc

    _last_tts_file = audio_path
    info = (
        f"TTS: pyttsx3 ({platform.system()} speech engine) | "
        f"Audio: {audio_path.stat().st_size} bytes | "
        f"Synthesis time: {time.time() - started:.1f}s"
    )
    logger.info(info)
    return str(audio_path), info
