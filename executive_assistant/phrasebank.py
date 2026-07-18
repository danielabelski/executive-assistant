"""Phrasebank — a local SQLite store of ~1,000 ready-made phrases.

THE TOKEN-ECONOMICS POINT
--------------------------
Every string in this DB is one the assistant would otherwise ask an LLM to
generate — greetings, status lines, draft openers/closers, fallbacks. At
~10-30 tokens each, several per briefing, twice a day, every day: the
savings are real, and on a small local model the latency win is bigger
still. The DB is queried in microseconds and rendered with slots; the LLM
is only invoked for genuine judgment (composer.py decides when).

USAGE
    from executive_assistant.phrasebank import PhraseBank

    pb = PhraseBank()                              # auto-builds DB on first use
    pb.phrase("greeting_morning", name=", Walker") # random variant, slots filled
    pb.phrase("fallback", tone="brief", source="Gmail", reason="auth missing")

DETERMINISM OPTION
    Pass rng=random.Random(seed) — briefing.py seeds by the day's ordinal,
    so one day = one consistent voice, and tests stay reproducible.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

from executive_assistant.config import PROJECT_ROOT
from executive_assistant.phrasebank_data import CATEGORIES, ENTRIES

DEFAULT_DB = PROJECT_ROOT / "data" / "phrasebank.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS phrases (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    text     TEXT NOT NULL,
    tone     TEXT NOT NULL DEFAULT 'neutral'
);
CREATE INDEX IF NOT EXISTS idx_category ON phrases(category);
CREATE INDEX IF NOT EXISTS idx_cat_tone ON phrases(category, tone);
"""


class PhraseBankError(Exception):
    pass


def build_db(path: Path | None = None) -> Path:
    """(Re)build the SQLite DB from phrasebank_data. Idempotent."""
    path = path or DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.execute("DELETE FROM phrases")
        conn.executemany(
            "INSERT INTO phrases (category, text, tone) VALUES (?, ?, ?)", ENTRIES
        )
        conn.commit()
    finally:
        conn.close()
    return path


class PhraseBank:
    """Query + render interface over the phrase DB."""

    def __init__(self, db_path: Path | None = None, autobuild: bool = True):
        self.db_path = db_path or DEFAULT_DB
        if not self.db_path.exists():
            if not autobuild:
                raise PhraseBankError(f"No phrasebank DB at {self.db_path}")
            build_db(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # --- queries -------------------------------------------------------------
    def count(self, category: str | None = None) -> int:
        with self._connect() as conn:
            if category:
                (n,) = conn.execute(
                    "SELECT COUNT(*) FROM phrases WHERE category=?", (category,)
                ).fetchone()
            else:
                (n,) = conn.execute("SELECT COUNT(*) FROM phrases").fetchone()
        return n

    def categories(self) -> list[str]:
        return list(CATEGORIES)

    def all(self, category: str, tone: str | None = None) -> list[str]:
        sql = "SELECT text FROM phrases WHERE category=?"
        params: list = [category]
        if tone:
            sql += " AND tone=?"
            params.append(tone)
        with self._connect() as conn:
            return [row[0] for row in conn.execute(sql, params).fetchall()]

    # --- rendering -------------------------------------------------------------
    def phrase(self, category: str, tone: str | None = None,
               rng: random.Random | None = None, **slots) -> str:
        """One random variant from a category, with {slots} filled.

        Falls back to the unfiltered category if the requested tone is empty,
        and renders leniently — a missing slot never crashes a briefing, it
        just renders empty ('Good morning!' from 'Good morning{name}!').
        """
        choices = self.all(category, tone)
        if not choices and tone:
            choices = self.all(category)          # tone fallback
        if not choices:
            raise PhraseBankError(f"Unknown or empty category: {category!r}")
        pick = (rng or random).choice(choices)
        return _render(pick, slots)


def _render(template: str, slots: dict) -> str:
    """Fill {slots}; unknown slots render as empty strings, never raise."""
    out = template
    for key in _slot_names(template):
        out = out.replace("{" + key + "}", str(slots.get(key, "")))
    return out


def _slot_names(template: str) -> list[str]:
    names, i = [], 0
    while True:
        start = template.find("{", i)
        if start == -1:
            return names
        end = template.find("}", start)
        if end == -1:
            return names
        names.append(template[start + 1:end])
        i = end
