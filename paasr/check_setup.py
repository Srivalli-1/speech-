"""
check_setup.py — Verify that all PAASR dependencies are installed and importable.

Run this after setup.bat to confirm a working installation before launching app.py.
Exit code 0 = all checks passed.  Exit code 1 = one or more checks failed.
"""

from __future__ import annotations

import sys

# Enforce Python version early.
if sys.version_info < (3, 11):
    print(
        f"[FAIL] Python 3.11+ is required.  "
        f"You are running {sys.version}.  "
        f"Download Python 3.11 from https://www.python.org/downloads/"
    )
    sys.exit(1)

import importlib
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).parent.resolve()
PASS_COUNT = 0
FAIL_COUNT = 0


def check(label: str, fn: Callable[[], None]) -> None:
    """Run fn(); print PASS or FAIL with label."""
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f"  [PASS] {label}")
        PASS_COUNT += 1
    except Exception as exc:
        print(f"  [FAIL] {label}")
        print(f"         {type(exc).__name__}: {exc}")
        FAIL_COUNT += 1


# ── Section helpers ────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


# ─────────────────────────────────────────────────────────────────────────────
section("1. Python version")
# ─────────────────────────────────────────────────────────────────────────────

def _check_python():
    major, minor = sys.version_info[:2]
    if major != 3 or minor < 11:
        raise RuntimeError(f"Need Python 3.11, got {major}.{minor}")

check("Python >= 3.11", _check_python)

# ─────────────────────────────────────────────────────────────────────────────
section("2. Core package imports")
# ─────────────────────────────────────────────────────────────────────────────

PACKAGES = [
    ("gradio",          "gradio"),
    ("speech_recognition", "speech_recognition"),
    ("av",              "av"),
    ("requests",        "requests"),
    ("pyttsx3",         "pyttsx3"),
    ("numpy",           "numpy"),
    ("dotenv",          "dotenv"),
]

for pkg_label, import_name in PACKAGES:
    def _import_check(name=import_name):
        importlib.import_module(name)
    check(f"import {pkg_label}", _import_check)

# ─────────────────────────────────────────────────────────────────────────────
section("3. PAASR modules")
# ─────────────────────────────────────────────────────────────────────────────

PAASR_MODULES = [
    "config",
    "modules.utils",
    "modules.asr",
    "modules.translator",
    "modules.tts",
    "modules.survey_db",
]

for mod in PAASR_MODULES:
    def _mod_check(m=mod):
        importlib.import_module(m)
    check(f"import {mod}", _mod_check)

# ─────────────────────────────────────────────────────────────────────────────
section("4. File system")
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_FILES = [
    "app.py",
    "config.py",
    "requirements.txt",
    "assets/style.css",
    "modules/__init__.py",
    "modules/asr.py",
    "modules/translator.py",
    "modules/tts.py",
    "modules/survey_db.py",
    "modules/utils.py",
]

for rel in REQUIRED_FILES:
    def _file_check(r=rel):
        p = ROOT / r
        if not p.exists():
            raise FileNotFoundError(f"Missing: {p}")
    check(f"exists: {rel}", _file_check)

# ─────────────────────────────────────────────────────────────────────────────
section("5. Google language configuration")
# ─────────────────────────────────────────────────────────────────────────────

def _check_google_languages():
    import config
    if config.TRANSLATION_LANGUAGES.get("Telugu") != "te":
        raise RuntimeError("Google Translate Telugu source must be 'te'.")
    if config.TRANSLATION_LANGUAGES.get("English") != "en":
        raise RuntimeError("Google Translate English target must be 'en'.")
    if config.SPEECH_TO_TRANSLATION_LANGUAGE.get("te") != "Telugu":
        raise RuntimeError("Telugu speech must translate from Telugu.")

check("Google Telugu/English language codes", _check_google_languages)

# ─────────────────────────────────────────────────────────────────────────────
section("6. SQLite DB creation")
# ─────────────────────────────────────────────────────────────────────────────

def _check_db():
    import sqlite3
    import tempfile
    fd_path = Path(tempfile.mktemp(suffix=".db"))
    try:
        conn = sqlite3.connect(str(fd_path))
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        row = conn.execute("SELECT x FROM t").fetchone()
        conn.close()
        if row[0] != 42:
            raise AssertionError("Read-back mismatch.")
    finally:
        if fd_path.exists():
            fd_path.unlink()

check("SQLite create / insert / read", _check_db)

# ─────────────────────────────────────────────────────────────────────────────
section("7. Log and data directories")
# ─────────────────────────────────────────────────────────────────────────────

def _check_dirs():
    import config
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    test_file = config.LOG_DIR / "_write_test.tmp"
    test_file.write_text("ok")
    test_file.unlink()

check("logs/ and data/ writable", _check_dirs)

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
section("Summary")
print(f"  Passed: {PASS_COUNT}")
print(f"  Failed: {FAIL_COUNT}")
print()

if FAIL_COUNT > 0:
    print("  [!] Some checks failed.  Fix the issues above and re-run.")
    print("      If packages are missing, run:  pip install -r requirements.txt")
    sys.exit(1)
else:
    print("  All checks passed.  Run:  python app.py")
    sys.exit(0)
