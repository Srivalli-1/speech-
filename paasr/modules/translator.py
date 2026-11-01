"""Google Translate text translation with safe request limits."""

from __future__ import annotations

import time
from typing import Callable

import requests

import config
from modules.utils import logger

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split long input into bounded pieces without dropping source text."""
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > max_chars:
        split_at = remaining.rfind(" ", 0, max_chars + 1)
        newline_at = remaining.rfind("\n", 0, max_chars + 1)
        split_at = max(split_at, newline_at)
        if split_at <= 0:
            split_at = max_chars
        chunk = remaining[:split_at].strip()
        if not chunk:
            raise ValueError("Could not split the text for Google Translate.")
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _translate_chunk(text: str, source_code: str, target_code: str) -> str:
    try:
        response = requests.get(
            GOOGLE_TRANSLATE_URL,
            params={
                "client": "gtx",
                "sl": source_code,
                "tl": target_code,
                "dt": "t",
                "q": text,
            },
            timeout=config.GOOGLE_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.exception("Google Translate request failed.")
        raise RuntimeError(
            "Could not reach Google Translate. Check your internet connection "
            f"and try again. Detail: {exc}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        logger.exception("Google Translate returned invalid JSON.")
        raise RuntimeError(
            "Google Translate returned an unreadable response. Try again later."
        ) from exc

    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        raise RuntimeError("Google Translate returned an unexpected response.")

    translated = "".join(
        part[0]
        for part in payload[0]
        if isinstance(part, list) and part and isinstance(part[0], str)
    ).strip()
    if not translated:
        raise RuntimeError("Google Translate returned an empty translation.")
    return translated


def translate_text(
    text: str,
    source_language: str,
    target_language: str,
    progress: Callable | None = None,
) -> tuple[str, str]:
    """Translate complete text using Google's public Translate endpoint."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Translation input is empty.")

    try:
        source_code = config.TRANSLATION_LANGUAGES[source_language]
    except (KeyError, TypeError) as exc:
        supported = ", ".join(config.TRANSLATION_LANGUAGES)
        raise ValueError(
            f"Unsupported source language: {source_language!r}. "
            f"Supported languages: {supported}."
        ) from exc
    try:
        target_code = config.TRANSLATION_LANGUAGES[target_language]
    except (KeyError, TypeError) as exc:
        supported = ", ".join(config.TRANSLATION_LANGUAGES)
        raise ValueError(
            f"Unsupported target language: {target_language!r}. "
            f"Supported languages: {supported}."
        ) from exc
    if source_code == target_code:
        raise ValueError("Source and target languages must be different.")

    chunks = _split_text(text, config.GOOGLE_TRANSLATE_MAX_CHARS)
    started = time.monotonic()
    translated_chunks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        if progress is not None:
            progress(
                0.1 + 0.8 * (index - 1) / len(chunks),
                desc=f"Translating text with Google ({index}/{len(chunks)}) ...",
            )
        try:
            translated_chunks.append(
                _translate_chunk(chunk, source_code, target_code)
            )
        except (ValueError, RuntimeError):
            raise
        except Exception as exc:
            logger.exception(
                "Google Translate failed on segment %d of %d.",
                index,
                len(chunks),
            )
            raise RuntimeError(
                f"Google Translate failed on segment {index} of {len(chunks)}. "
                f"Detail: {exc}"
            ) from exc

    result = " ".join(translated_chunks).strip()
    if not result:
        raise RuntimeError("Google Translate returned an empty translation.")

    info = (
        f"Translation: Google Translate | {source_language} -> {target_language} | "
        f"Segments: {len(chunks)} | "
        f"Translation time: {time.monotonic() - started:.1f}s"
    )
    logger.info(
        "Completed Google Translate: %s -> %s, input_chars=%d, segments=%d.",
        source_language,
        target_language,
        len(text),
        len(chunks),
    )
    if progress is not None:
        progress(1.0, desc="Translation complete.")
    return result, info
