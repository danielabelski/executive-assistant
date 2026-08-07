"""Paths — one place that owns where runtime files live.

WHY THIS MODULE EXISTS
----------------------
Six different modules want to write into data/ (phrasebank.db, audit log,
assistant.log, ...). If each one mkdir's its own way, a fresh clone fails
with six different "No such file or directory" errors. Here, every path
helper guarantees its parent directory exists (best-effort) so a missing
data/ dir becomes invisible, not fatal.

Best-effort means: on a read-only filesystem the helpers still RETURN the
path (so error messages name it) and set `last_warning` instead of raising.
"""

from __future__ import annotations

from pathlib import Path

from executive_assistant.config import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"

#: Set when a mkdir fails — doctor surfaces it, nothing crashes.
last_warning: str | None = None


def _ensure(path: Path) -> Path:
    global last_warning
    try:
        path.mkdir(parents=True, exist_ok=True)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.touch()
    except OSError as exc:
        last_warning = f"cannot create {path}: {exc}"
    return path


def data_dir() -> Path:
    """The runtime data directory, created (with .gitkeep) if absent."""
    return _ensure(DATA_DIR)


def log_path() -> Path:
    """data/assistant.log — the rotating application log."""
    return data_dir() / "assistant.log"


def audit_log_path() -> Path:
    """data/approval_log.jsonl — every approval-gate ruling."""
    return data_dir() / "approval_log.jsonl"
