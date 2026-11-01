"""Local smoke checks for the PAASR Google-backed translation app."""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

failures = 0


def check(label: str, action) -> None:
    global failures
    try:
        detail = action()
        print(f"[PASS] {label}" + (f": {detail}" if detail else ""))
    except Exception as exc:
        failures += 1
        print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")


def check_imports() -> str:
    for name in (
        "config",
        "modules.utils",
        "modules.asr",
        "modules.translator",
        "modules.tts",
        "modules.survey_db",
    ):
        importlib.import_module(name)
    return "application modules imported"


def check_database() -> str:
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "smoke.db"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("CREATE TABLE sample (value TEXT)")
            connection.execute("INSERT INTO sample VALUES ('ok')")
            value = connection.execute("SELECT value FROM sample").fetchone()[0]
        finally:
            connection.close()
        if value != "ok":
            raise AssertionError("SQLite read-back mismatch")
    return "SQLite read/write succeeded"


def check_tts() -> str:
    from modules.tts import synthesise_speech

    path, info = synthesise_speech("PAASR local speech smoke test.")
    output = Path(path)
    try:
        if not output.is_file() or output.stat().st_size == 0:
            raise AssertionError("TTS output file is missing or empty")
        return info
    finally:
        output.unlink(missing_ok=True)


check("Imports", check_imports)
check("SQLite", check_database)
check("Local English TTS", check_tts)

if os.environ.get("PAASR_RUN_GOOGLE_INTEGRATION") == "1":
    from modules.translator import translate_text

    check(
        "Google Telugu-to-English service",
        lambda: translate_text(
            "నాకు కడుపు నొప్పిగా ఉంది", "Telugu", "English"
        )[0],
    )
    sample_audio = os.environ.get("PAASR_TEST_AUDIO")
    if sample_audio:
        from modules.asr import transcribe_audio

        check(
            "Google te-IN speech recognition",
            lambda: transcribe_audio(sample_audio)[0],
        )
    else:
        print("[SKIP] Real speech recognition: set PAASR_TEST_AUDIO to an audio file.")
else:
    print(
        "[SKIP] Google integration checks: set "
        "PAASR_RUN_GOOGLE_INTEGRATION=1 to contact Google."
    )

if failures:
    raise SystemExit(1)
print("Smoke checks completed.")
