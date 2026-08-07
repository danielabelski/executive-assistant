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
CREATE TABLE IF NOT EXISTS phrase_usage (
    phrase_id   INTEGER NOT NULL,
    rendered_on TEXT NOT NULL    -- ISO date; one row per render
);
CREATE INDEX IF NOT EXISTS idx_usage_phrase ON phrase_usage(phrase_id);
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
        else:
            # Older DBs predate phrase_usage — migrate in place, never rebuild
            # (a rebuild would lose the user's accumulated stats).
            with self._connect() as conn:
                conn.executescript(
                    "CREATE TABLE IF NOT EXISTS phrase_usage ("
                    " phrase_id INTEGER NOT NULL,"
                    " rendered_on TEXT NOT NULL);"
                    "CREATE INDEX IF NOT EXISTS idx_usage_phrase"
                    " ON phrase_usage(phrase_id);"
                )

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

    def category_counts(self) -> list[tuple[str, int]]:
        """(category, row count) pairs — powers `phrasebank --stats`."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT category, COUNT(*) FROM phrases"
                " GROUP BY category ORDER BY category"
            ).fetchall()

    def stats(self, limit: int = 20) -> list[tuple[str, str, int]]:
        """Most-rendered phrases: (category, text, times_used).

        The point: phrases that never render are candidates for pruning, and
        hot ones tell you which categories deserve more variants.
        """
        with self._connect() as conn:
            return conn.execute(
                "SELECT p.category, p.text, COUNT(u.phrase_id) AS n"
                " FROM phrase_usage u JOIN phrases p ON p.id = u.phrase_id"
                " GROUP BY u.phrase_id ORDER BY n DESC LIMIT ?",
                (limit,),
            ).fetchall()

    def validate_slots(self) -> list[str]:
        """Templates whose {slots} can't be filled from the shared slot set.

        Returns offending templates (empty list = healthy). A phrase that
        references a slot no caller ever passes would render a silent '' —
        this makes that loud at doctor/seed time instead.
        """
        from executive_assistant.phrasebank_data import KNOWN_SLOTS

        bad = []
        with self._connect() as conn:
            rows = conn.execute("SELECT text FROM phrases").fetchall()
        for (text,) in rows:
            unknown = set(_slot_names(text)) - set(KNOWN_SLOTS)
            if unknown:
                bad.append(f"{text!r} references unknown slot(s): {sorted(unknown)}")
        return bad

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
        self._record_usage(category, pick)
        return _render(pick, slots)

    def _record_usage(self, category: str, text: str) -> None:
        """One row per render. Stats are nice-to-have — a hiccup here must
        never break a briefing, so failures are swallowed by design."""
        try:
            from datetime import date

            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM phrases WHERE category=? AND text=?",
                    (category, text),
                ).fetchone()
                if row:
                    conn.execute(
                        "INSERT INTO phrase_usage (phrase_id, rendered_on)"
                        " VALUES (?, ?)",
                        (row[0], date.today().isoformat()),
                    )
        except Exception:
            pass


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
        # '{date:%A}' — the format spec belongs to the caller, not the slot name
        names.append(template[start + 1:end].split(":", 1)[0])
        i = end
