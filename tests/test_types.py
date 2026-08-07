"""Tests for shared types: Event.is_all_day, conflicts(), next_up(), flag_vips()."""

from datetime import datetime
from zoneinfo import ZoneInfo

from executive_assistant.types import (
    EmailSummary,
    Event,
    conflicts,
    flag_vips,
    next_up,
)

TZ = ZoneInfo("America/Los_Angeles")


def ev(summary, sh, sm, eh, em, day=18, all_day=False, tz=TZ):
    return Event(
        summary=summary,
        start=datetime(2026, 7, day, sh, sm, tzinfo=tz),
        end=datetime(2026, 7, day, eh, em, tzinfo=tz),
        all_day=all_day,
    )


class TestIsAllDay:
    def test_default_is_false(self):
        assert ev("Standup", 10, 0, 10, 30).is_all_day is False

    def test_all_day_field_is_mirrored(self):
        assert ev("Conference", 0, 0, 0, 0, all_day=True).is_all_day is True


class TestConflicts:
    def test_overlapping_pair_detected(self):
        a = ev("A", 10, 0, 11, 0)
        b = ev("B", 10, 30, 11, 30)
        assert conflicts([a, b]) == [(a, b)]

    def test_touching_endpoints_do_not_conflict(self):
        a = ev("A", 10, 0, 11, 0)
        b = ev("B", 11, 0, 12, 0)
        assert conflicts([a, b]) == []

    def test_disjoint_events_do_not_conflict(self):
        a = ev("A", 9, 0, 10, 0)
        b = ev("B", 14, 0, 15, 0)
        assert conflicts([a, b]) == []

    def test_all_day_events_never_conflict(self):
        timed = ev("A", 10, 0, 11, 0)
        marker = ev("Holiday", 0, 0, 0, 0, all_day=True)
        assert conflicts([timed, marker]) == []

    def test_different_days_do_not_conflict(self):
        a = ev("A", 10, 0, 11, 0, day=18)
        b = ev("B", 10, 0, 11, 0, day=19)
        assert conflicts([a, b]) == []

    def test_multiple_pairs_all_reported(self):
        a = ev("A", 10, 0, 12, 0)
        b = ev("B", 10, 30, 11, 30)
        c = ev("C", 11, 0, 13, 0)
        pairs = conflicts([a, b, c])
        assert len(pairs) == 3  # A∩B, A∩C, B∩C

    def test_naive_and_aware_aligned(self):
        aware = ev("A", 10, 0, 11, 0)
        naive = Event("B", datetime(2026, 7, 18, 10, 30), datetime(2026, 7, 18, 11, 30))
        assert conflicts([aware, naive]) == [(aware, naive)]


class TestNextUp:
    def test_picks_earliest_future_event(self):
        a = ev("Early", 14, 0, 14, 30)
        b = ev("Late", 16, 0, 16, 30)
        now = datetime(2026, 7, 18, 12, 0, tzinfo=TZ)
        event, minutes = next_up([b, a], now)  # unordered input is fine
        assert event.summary == "Early" and minutes == 120

    def test_past_events_ignored(self):
        a = ev("Past", 9, 0, 10, 0)
        now = datetime(2026, 7, 18, 12, 0, tzinfo=TZ)
        assert next_up([a], now) is None

    def test_all_day_events_ignored(self):
        marker = ev("Holiday", 0, 0, 0, 0, all_day=True)
        now = datetime(2026, 7, 18, 12, 0, tzinfo=TZ)
        assert next_up([marker], now) is None

    def test_tomorrows_events_ignored(self):
        a = ev("Tomorrow", 9, 0, 10, 0, day=19)
        now = datetime(2026, 7, 18, 12, 0, tzinfo=TZ)
        assert next_up([a], now) is None


class TestFlagVips:
    def test_flags_matching_sender_case_insensitive(self):
        msgs = [
            EmailSummary("1", "", "The Boss <BOSS@x.com>", "s", "", ""),
            EmailSummary("2", "", "random@y.com", "s", "", ""),
        ]
        result = flag_vips(msgs, ["boss@X.com"])
        assert result is msgs  # same list object back
        assert msgs[0].vip is True
        assert not hasattr(msgs[1], "vip")

    def test_works_on_plain_dicts(self):
        msgs = [{"sender": "Boss <boss@x.com>"}, {"sender": "a@b.com"}]
        flag_vips(msgs, ["boss"])
        assert msgs[0]["vip"] is True
        assert "vip" not in msgs[1]
