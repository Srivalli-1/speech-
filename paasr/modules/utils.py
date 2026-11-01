"""
modules/utils.py — Shared utilities: logging setup, audio validation, helpers.

All path operations use pathlib so they work correctly on Windows.
"""

from __future__ import annotations

import logging
import logging.handlers
import wave
from pathlib import Path
from typing import Tuple

import config


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    """
    Configure the root application logger.

    Writes to both the console (INFO+) and a rotating file (DEBUG+).
    Returns the named 'paasr' logger.
    """
    logger = logging.getLogger("paasr")
    if logger.handlers:
        # Already initialised (e.g. called twice).
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler — INFO and above.
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    ch.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    # Rotating file handler — DEBUG and above.
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


logger: logging.Logger = setup_logging()


# ── Audio validation ──────────────────────────────────────────────────────────

class AudioValidationError(ValueError):
    """Raised when an audio file fails validation."""


def get_wav_duration(path: Path) -> float:
    """
    Return the duration in seconds of a WAV file.

    Raises:
        AudioValidationError: if the file cannot be read as WAV.
    """
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate == 0:
                raise AudioValidationError("WAV file has zero sample rate.")
            return frames / float(rate)
    except wave.Error as exc:
        raise AudioValidationError(f"Cannot read WAV file: {exc}") from exc


def validate_audio_file(file_path: str | None) -> Tuple[Path, float]:
    """
    Validate an audio file supplied by the user.

    Args:
        file_path: Absolute path string from Gradio's Audio component, or None.

    Returns:
        (resolved Path, duration in seconds)

    Raises:
        AudioValidationError: with a user-friendly message on any failure.
    """
    if file_path is None or str(file_path).strip() == "":
        raise AudioValidationError(
            "No audio received.  Please record or upload a Telugu audio clip."
        )

    path = Path(file_path)
    if not path.exists():
        raise AudioValidationError(
            "Audio file not found.  It may have been cleaned up.  "
            "Please record or upload again."
        )

    if path.stat().st_size == 0:
        raise AudioValidationError(
            "Audio file is empty.  Please try recording again."
        )

    # Determine duration.
    suffix = path.suffix.lower()
    duration: float = 0.0

    if suffix == ".wav":
        try:
            duration = get_wav_duration(path)
        except AudioValidationError:
            # Non-fatal — faster-whisper can still try to decode it.
            logger.warning("Could not determine WAV duration; skipping length check.")
            return path, 0.0
    else:
        # For non-WAV files (webm, mp3, ogg, …) we skip the duration check
        # because reading them requires an external library.  faster-whisper
        # will handle decoding and will surface its own errors.
        logger.debug("Non-WAV audio (%s); skipping duration pre-check.", suffix)
        return path, 0.0

    if duration < config.AUDIO_MIN_DURATION_S:
        raise AudioValidationError(
            f"Audio clip is too short ({duration:.2f} s).  "
            f"Please record at least {config.AUDIO_MIN_DURATION_S} seconds of speech."
        )

    if duration > config.AUDIO_MAX_DURATION_S:
        raise AudioValidationError(
            f"Audio clip is too long ({duration:.0f} s).  "
            f"Maximum allowed length is {config.AUDIO_MAX_DURATION_S:.0f} seconds (2 minutes)."
        )

    return path, duration


# ── Misc helpers ──────────────────────────────────────────────────────────────

def safe_str(text: str) -> str:
    """
    Replace non-ASCII characters for safe Windows CMD console output.

    Keeps the text readable while avoiding UnicodeEncodeError on cp1252 terminals.
    """
    return text.encode("ascii", errors="replace").decode("ascii")


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentence-like chunks for translation.

    Uses a simple rule: split on common Latin and Indic sentence punctuation
    and newlines.
    Preserves non-empty stripped chunks.

    Args:
        text: Input text, possibly multi-sentence.

    Returns:
        List of sentence strings.
    """
    import re
    # Split on sentence-ending punctuation; keep delimiters via lookahead.
    parts = re.split(r"(?<=[.!?|\u0964\u0965\uff01\uff1f])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]
