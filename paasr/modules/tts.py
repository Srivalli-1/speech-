"""Local English speech synthesis using eSpeak on Linux and pyttsx3 elsewhere."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
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


def _validate_wav(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("The speech engine did not create an audio file.")

    try:
        with wave.open(str(path), "rb") as audio_file:
            if audio_file.getnframes() == 0:
                raise wave.Error("generated audio contains no frames")
    except (OSError, EOFError, wave.Error) as exc:
        raise RuntimeError(f"The speech engine created an invalid WAV file: {exc}") from exc


def _synthesise_espeak(text: str) -> Path:
    """Use the eSpeak CLI on Linux to avoid pyttsx3's fragile ctypes driver."""
    executable = shutil.which("espeak-ng") or shutil.which("espeak")
    if executable is None:
        raise RuntimeError(
            "Neither espeak-ng nor espeak is installed. Install the eSpeak "
            "system package in the Render build."
        )

    out_path = _make_temp_path(".wav")
    command = [
        executable,
        "-v",
        "en-us",
        "-s",
        str(config.TTS_PYTTSX3_RATE),
        "-w",
        str(out_path),
        "--stdin",
    ]
    try:
        result = subprocess.run(
            command,
            input=text,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        out_path.unlink(missing_ok=True)
        raise RuntimeError(f"Could not run eSpeak: {exc}") from exc

    if result.returncode != 0:
        out_path.unlink(missing_ok=True)
        detail = result.stderr.strip() or result.stdout.strip() or "no error output"
        raise RuntimeError(
            f"eSpeak exited with status {result.returncode}: {detail}"
        )

    try:
        _validate_wav(out_path)
    except RuntimeError:
        out_path.unlink(missing_ok=True)
        raise
    return out_path


def _synthesise_pyttsx3(text: str) -> Path:
    """Synthesize speech on Windows using the installed platform voice."""
    import pyttsx3

    out_path = _make_temp_path(".wav")
    engine = None
    try:
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

    try:
        _validate_wav(out_path)
    except RuntimeError:
        out_path.unlink(missing_ok=True)
        raise
    return out_path


def synthesise_speech(english_text: str) -> Tuple[str, str]:
    """Synthesize the supplied English text into a verified local WAV file."""
    global _last_tts_file

    if not english_text or not english_text.strip():
        raise ValueError("TTS input is empty.")

    _cleanup_last_temp()
    started = time.time()
    system = platform.system()
    try:
        audio_path = (
            _synthesise_espeak(english_text)
            if system == "Linux"
            else _synthesise_pyttsx3(english_text)
        )
    except Exception as exc:
        logger.exception(
            "English TTS failed on %s for %d characters.",
            system,
            len(english_text),
        )
        raise RuntimeError(
            f"English audio generation failed on {system}: {exc}"
        ) from exc

    _last_tts_file = audio_path
    info = (
        f"TTS: {'eSpeak' if system == 'Linux' else 'pyttsx3'} "
        f"({system} speech engine) | Audio: {audio_path.stat().st_size} bytes | "
        f"Synthesis time: {time.time() - started:.1f}s"
    )
    logger.info(info)
    return str(audio_path), info
