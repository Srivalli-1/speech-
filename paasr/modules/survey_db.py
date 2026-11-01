"""
modules/survey_db.py — SQLite-backed survey storage.

Uses only stdlib sqlite3 with parameterised queries (no raw string
interpolation) to prevent SQL injection.  The DB file is created on first use.
"""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import config
from modules.utils import logger

# ── Schema ────────────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS survey_responses (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT,
    preferred_language TEXT NOT NULL,
    translation_rating INTEGER NOT NULL CHECK(translation_rating BETWEEN 1 AND 5),
    asr_rating         INTEGER NOT NULL CHECK(asr_rating BETWEEN 1 AND 5),
    feedback           TEXT,
    submitted_at       TEXT NOT NULL
);
"""


# ── Connection helper ─────────────────────────────────────────────────────────

def _get_connection() -> sqlite3.Connection:
    """
    Open (or create) the SQLite database and return a connection.

    The database file is created at config.DB_PATH if it does not exist.
    WAL mode is enabled for better concurrent-read performance.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn


# ── Initialisation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create the survey table if it does not already exist.

    Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS).
    """
    with _get_connection() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
    logger.info("Survey DB initialised at: %s", config.DB_PATH)


# ── Write ─────────────────────────────────────────────────────────────────────

def insert_response(
    name: Optional[str],
    preferred_language: str,
    translation_rating: int,
    asr_rating: int,
    feedback: Optional[str],
) -> int:
    """
    Insert a survey response into the database.

    Args:
        name:               Respondent name (optional).
        preferred_language: Respondent's preferred language.
        translation_rating: 1–5 rating for translation quality.
        asr_rating:         1–5 rating for ASR quality.
        feedback:           Free-text feedback (optional).

    Returns:
        The row ID of the newly inserted record.

    Raises:
        ValueError: if ratings are out of range.
        sqlite3.Error: for unexpected DB errors.
    """
    if not 1 <= translation_rating <= 5:
        raise ValueError(f"translation_rating must be 1–5, got {translation_rating}.")
    if not 1 <= asr_rating <= 5:
        raise ValueError(f"asr_rating must be 1–5, got {asr_rating}.")

    submitted_at = datetime.now(tz=timezone.utc).isoformat()
    clean_name = name.strip() if name and name.strip() else None
    clean_feedback = feedback.strip() if feedback and feedback.strip() else None

    sql = """
    INSERT INTO survey_responses
        (name, preferred_language, translation_rating, asr_rating, feedback, submitted_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            sql,
            (clean_name, preferred_language, translation_rating, asr_rating,
             clean_feedback, submitted_at),
        )
        conn.commit()
        row_id: int = cursor.lastrowid  # type: ignore[assignment]

    logger.info("Survey response inserted: id=%d", row_id)
    return row_id


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_responses() -> list[dict[str, Any]]:
    """
    Return all survey responses as a list of dicts, newest first.

    Returns:
        List of row dicts with keys:
        id, name, preferred_language, translation_rating, asr_rating,
        feedback, submitted_at.
    """
    sql = "SELECT * FROM survey_responses ORDER BY submitted_at DESC;"
    with _get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


# ── CSV export ────────────────────────────────────────────────────────────────

def export_responses_csv() -> str:
    """
    Serialize all survey responses to a CSV string.

    Returns:
        CSV text (UTF-8, with header row).  Empty string if no responses.
    """
    rows = fetch_all_responses()
    if not rows:
        return ""

    output = io.StringIO()
    fieldnames = [
        "id", "name", "preferred_language", "translation_rating",
        "asr_rating", "feedback", "submitted_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_responses_to_file() -> Optional[str]:
    """
    Write survey responses CSV to a temp file and return its path.

    Returns:
        Absolute path to the CSV file, or None if there are no responses.
    """
    import tempfile
    csv_text = export_responses_csv()
    if not csv_text:
        return None

    fd, tmp_path = tempfile.mkstemp(suffix=".csv", prefix="paasr_survey_")
    import os
    os.close(fd)
    Path(tmp_path).write_text(csv_text, encoding="utf-8")
    logger.info("Survey CSV exported to: %s", tmp_path)
    return tmp_path
