"""Google Speech Recognition for Telugu audio."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import config
from modules.utils import AudioValidationError, logger, validate_audio_file

GOOGLE_SPEECH_LANGUAGE = "te-IN"
GOOGLE_AUDIO_SAMPLE_RATE = 16_000


def _update_progress(progress: Callable | None, value: float, description: str) -> None:
    if progress is not None:
        progress(value, desc=description)


def _decode_audio(path: Path, progress: Callable | None = None):
    """Decode supported container formats to mono, 16 kHz, signed 16-bit PCM."""
    try:
        import av
    except ImportError as exc:
        logger.exception("PyAV is required to decode uploaded audio.")
        raise RuntimeError(
            "Audio decoding support is missing. Run "
            ".venv\\Scripts\\python.exe -m pip install -r requirements.txt."
        ) from exc

    try:
        with av.open(str(path)) as container:
            audio_stream = next(
                (stream for stream in container.streams if stream.type == "audio"),
                None,
            )
            if audio_stream is None:
                raise AudioValidationError(
                    "The uploaded file does not contain an audio stream."
                )

            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=GOOGLE_AUDIO_SAMPLE_RATE,
            )
            pcm_frames: list[bytes] = []
            duration_seconds = 0.0
            for frame in container.decode(audio=audio_stream.index):
                if frame.sample_rate:
                    duration_seconds += frame.samples / frame.sample_rate
                for converted in resampler.resample(frame):
                    pcm_frames.append(converted.to_ndarray().tobytes())
                if duration_seconds > config.AUDIO_MAX_DURATION_S:
                    raise AudioValidationError(
                        f"Audio is longer than the {config.AUDIO_MAX_DURATION_S:.0f}-second limit."
                    )

            for converted in resampler.resample(None):
                pcm_frames.append(converted.to_ndarray().tobytes())

    except AudioValidationError:
        raise
    except Exception as exc:
        logger.exception("Could not decode audio file %s.", path.name)
        raise AudioValidationError(
            "Could not read this audio file. Try a WAV, MP3, OGG, WebM, or M4A "
            f"recording. Detail: {exc}"
        ) from exc

    if duration_seconds + 0.001 < config.AUDIO_MIN_DURATION_S:
        raise AudioValidationError(
            "Audio is empty or too short to recognize. Please record at least "
            f"{config.AUDIO_MIN_DURATION_S:.1f} seconds of Telugu speech."
        )
    if not pcm_frames or not any(pcm_frames):
        raise AudioValidationError(
            "No audio samples were found. Please record or upload the clip again."
        )

    pcm_data = b"".join(pcm_frames)
    logger.info(
        "Decoded audio: duration=%.2fs, sample_rate=%dHz, channels=1, "
        "sample_width=2 bytes.",
        duration_seconds,
        GOOGLE_AUDIO_SAMPLE_RATE,
    )
    _update_progress(progress, 0.35, "Audio decoded; contacting Google Speech Recognition ...")

    try:
        import speech_recognition as sr
    except ImportError as exc:
        logger.exception("SpeechRecognition dependency is missing.")
        raise RuntimeError(
            "Google speech recognition support is missing. Run "
            ".venv\\Scripts\\python.exe -m pip install -r requirements.txt."
        ) from exc

    return sr.AudioData(pcm_data, GOOGLE_AUDIO_SAMPLE_RATE, 2), sr


def transcribe_audio(
    file_path: str | None,
    progress: Callable | None = None,
) -> tuple[str, str, str]:
    """Transcribe audio into Telugu script using Google's te-IN recognizer."""
    path, _ = validate_audio_file(file_path)
    logger.info("Starting Google Telugu speech recognition for %s.", path.name)
    _update_progress(progress, 0.1, "Preparing Telugu audio ...")

    audio_data, sr = _decode_audio(path, progress)
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = config.GOOGLE_REQUEST_TIMEOUT_SECONDS
    _update_progress(progress, 0.55, "Recognizing Telugu speech with Google ...")
    started = time.monotonic()
    try:
        transcript = recognizer.recognize_google(
            audio_data,
            language=GOOGLE_SPEECH_LANGUAGE,
        )
    except sr.UnknownValueError as exc:
        logger.info("Google Speech Recognition could not understand audio.")
        raise RuntimeError(
            "Google Speech Recognition could not understand this recording. "
            "Try a clearer Telugu recording with less background noise."
        ) from exc
    except sr.RequestError as exc:
        logger.exception("Google Speech Recognition request failed.")
        raise RuntimeError(
            "Could not reach Google Speech Recognition. Check your internet "
            f"connection and try again. Detail: {exc}"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected Google Speech Recognition failure.")
        raise RuntimeError(
            "Google Speech Recognition failed unexpectedly. "
            f"Detail: {exc}"
        ) from exc

    transcript = transcript.strip() if isinstance(transcript, str) else ""
    if not transcript:
        raise RuntimeError(
            "Google Speech Recognition returned an empty transcript. "
            "Try recording the Telugu speech again."
        )

    elapsed = time.monotonic() - started
    info = (
        f"ASR: Google Speech Recognition | language={GOOGLE_SPEECH_LANGUAGE} | "
        f"recognition time: {elapsed:.1f}s"
    )
    logger.info("%s | transcript_chars=%d", info, len(transcript))
    _update_progress(progress, 1.0, "Telugu transcription complete.")
    return transcript, info, "te"
