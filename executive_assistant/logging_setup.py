"""Logging setup — one rotating file, quiet console.

WHY: when a 7 AM cron briefing silently misbehaves, the only evidence is
what got written down. A RotatingFileHandler at data/assistant.log (1 MB
x 3) keeps weeks of history without growing unbounded; stderr stays at
WARNING so interactive use isn't noisy.

get_logger is IDEMPOTENT: calling it twice (imports, tests, doctor + CLI
in one process) never stacks duplicate handlers — that's the classic
double-logging bug.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from executive_assistant.paths import log_path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_MAX_BYTES = 1_000_000
_BACKUPS = 3
_ROOT_NAME = "executive_assistant"
_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.INFO)
    try:
        fh = RotatingFileHandler(log_path(), maxBytes=_MAX_BYTES,
                                 backupCount=_BACKUPS, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(fh)
    except OSError:
        pass                      # read-only fs: stderr still works
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(sh)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """A module logger under the executive_assistant namespace."""
    _configure_root()
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
