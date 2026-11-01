"""
make_zip.py — Package the entire paasr/ directory into paasr.zip.

Run from the project root (one level above paasr/) OR from inside paasr/:
    python make_zip.py

The zip is created next to this script as 'paasr.zip'.
Files excluded:
  - .venv/       (too large)
  - __pycache__/ (regenerated automatically)
  - *.pyc
  - data/survey.db  (runtime file)
  - logs/*.log      (runtime files)
  - .env            (contains user secrets; .env.example IS included)
"""

from __future__ import annotations

import zipfile
from pathlib import Path

# Determine project root (directory that contains this file).
HERE: Path = Path(__file__).parent.resolve()
OUT_ZIP: Path = HERE / "paasr.zip"

# Patterns to exclude (relative to HERE).
EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".db"}
EXCLUDE_FILES = {".env"}        # exact name, not .env.example

collected: list[Path] = []


def should_exclude(path: Path) -> bool:
    """Return True if this path should be omitted from the zip."""
    parts = path.relative_to(HERE).parts

    # Skip any path containing an excluded directory name.
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True

    # Skip by exact filename.
    if path.name in EXCLUDE_FILES:
        return True

    # Skip by suffix.
    if path.suffix in EXCLUDE_SUFFIXES:
        return True

    return False


def collect_files() -> list[Path]:
    """Walk the project tree and collect files to include."""
    files: list[Path] = []
    for item in sorted(HERE.rglob("*")):
        if item.is_file() and not should_exclude(item):
            files.append(item)
    return files


def build_zip() -> None:
    """Create paasr.zip from the collected file list."""
    files = collect_files()

    print(f"Building {OUT_ZIP.name} ...")
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arc_name = f.relative_to(HERE.parent)   # Include paasr/ prefix in zip.
            zf.write(f, arcname=arc_name)
            print(f"  + {arc_name}")

    size_mb = OUT_ZIP.stat().st_size / (1024 * 1024)
    print(f"\nDone: {OUT_ZIP}  ({size_mb:.2f} MB, {len(files)} files)")


if __name__ == "__main__":
    build_zip()
