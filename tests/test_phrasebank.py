"""Tests for the phrasebank — DB build, counts, querying, slot rendering."""

import random

import pytest

from executive_assistant.phrasebank import (
    PhraseBank,
    PhraseBankError,
    _render,
    build_db,
)
from executive_assistant.phrasebank_data import CATEGORIES


@pytest.fixture(scope="module")
def pb(tmp_path_factory):
    db = build_db(tmp_path_factory.mktemp("pb") / "phrasebank.db")
    return PhraseBank(db)


class TestBuild:
    def test_count_meets_thousand_entry_goal(self, pb):
        assert pb.count() >= 1000

    def test_every_category_non_empty(self, pb):
        for category in pb.categories():
            assert pb.count(category) > 0, f"empty category: {category}"

    def test_build_is_idempotent(self, tmp_path):
        db = build_db(tmp_path / "x.db")
        build_db(db)  # rebuild over the top
        assert PhraseBank(db).count() >= 1000

    def test_autobuild_on_missing_db(self, tmp_path):
        bank = PhraseBank(tmp_path / "fresh.db")
        assert bank.count() > 0

    def test_no_autobuild_raises(self, tmp_path):
        with pytest.raises(PhraseBankError):
            PhraseBank(tmp_path / "nope.db", autobuild=False)


class TestQuery:
    def test_tone_filter(self, pb):
        brief = pb.all("greeting_morning", tone="brief")
        assert brief and all(isinstance(t, str) for t in brief)

    def test_unknown_category_raises(self, pb):
        with pytest.raises(PhraseBankError, match="not_a_category"):
            pb.phrase("not_a_category")

    def test_tone_fallback_to_category(self, pb):
        # 'playful' exists for greetings; a nonsense tone must fall back, not raise
        text = pb.phrase("greeting_morning", tone="nonsense-tone")
        assert isinstance(text, str) and text

    def test_categories_match_data_module(self, pb):
        assert pb.categories() == CATEGORIES


class TestRendering:
    def test_slots_filled(self, pb):
        text = pb.phrase("greeting_morning", rng=random.Random(1), name=", Walker")
        assert "{name}" not in text
        assert "Walker" in text or "{name}" not in "".join(pb.all("greeting_morning"))

    def test_missing_slot_renders_empty_never_raises(self, pb):
        # {name} with no slot provided → 'Good morning!' style, no KeyError
        text = pb.phrase("greeting_morning", rng=random.Random(1))
        assert "{" not in text and "}" not in text

    def test_render_unit(self):
        assert _render("Hi {name}, you have {count} tasks", {"name": "W", "count": 3}) == \
            "Hi W, you have 3 tasks"
        assert _render("{a}{b}{c}", {"b": "X"}) == "X"

    def test_seeded_rng_is_deterministic(self, pb):
        a = pb.phrase("greeting_morning", rng=random.Random(42), name="")
        b = pb.phrase("greeting_morning", rng=random.Random(42), name="")
        assert a == b


class TestUsageStats:
    """Every render leaves a crumb — hot phrases earn variants, cold ones
    get pruned. Stats are best-effort: a broken stats path must never
    break a briefing."""

    def test_render_records_usage(self, pb):
        before = sum(n for _, _, n in pb.stats(limit=1000))
        pb.phrase("greeting_morning", rng=random.Random(7), name=", W")
        after = sum(n for _, _, n in pb.stats(limit=1000))
        assert after == before + 1

    def test_stats_shape(self, pb):
        pb.phrase("greeting_evening", rng=random.Random(1), name="")
        rows = pb.stats(limit=5)
        assert rows, "expected at least one usage row after a render"
        category, text, n = rows[0]
        assert isinstance(category, str) and isinstance(text, str)
        assert n >= 1

    def test_stats_survive_reopen(self, pb):
        pb.phrase("greeting_morning", rng=random.Random(3), name="")
        reopened = PhraseBank(pb.db_path)
        assert sum(n for _, _, n in reopened.stats(limit=1000)) >= 1


class TestCategoryCounts:
    def test_counts_cover_all_categories(self, pb):
        counts = dict(pb.category_counts())
        assert set(counts) == set(pb.categories())
        assert all(n > 0 for n in counts.values())

    def test_total_matches_count(self, pb):
        assert sum(n for _, n in pb.category_counts()) == pb.count()


class TestSlotValidation:
    def test_shipped_data_has_no_unknown_slots(self, pb):
        # Doctor runs this; a typo'd {slot} would render '' silently forever.
        assert pb.validate_slots() == []
