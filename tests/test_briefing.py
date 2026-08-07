"""Tests for briefing aggregation — fake collectors, real rendering logic."""

from datetime import date, datetime

from executive_assistant.briefing import (
    EveningWrapUp,
    MorningBriefing,
    Section,
    _run,
    headline,
    is_weekend,
    render_sections,
)
from executive_assistant.composer import FALLBACK_MARKER
from executive_assistant.config import AssistantConfig


def cfg(**kw) -> AssistantConfig:
    return AssistantConfig(user_name="Walker", **kw)


class TestSectionResilience:
    def test_failing_collector_becomes_warning_section(self):
        def boom():
            raise RuntimeError("auth missing")

        section = _run(boom, "📧 Unread email")
        assert section.error and "auth missing" in section.error
        assert "⚠" in section.render()

    def test_empty_section_says_nothing_to_report(self):
        section = _run(lambda: [], "✅ Tasks")
        assert "(nothing to report)" in section.render()


class TestMorningBriefing:
    def test_renders_all_sections_with_fakes(self):
        briefing = MorningBriefing(cfg(), collectors={
            "📅 Today's schedule": lambda: ["10:00–10:30  Standup"],
            "✅ Tasks": lambda: ["OVERDUE: Renew license"],
        })
        text = briefing.render_text()
        assert "Walker" in text.split("\n\n")[0]   # greeting line addresses the user
        assert "Standup" in text
        assert "OVERDUE: Renew license" in text

    def test_one_failure_does_not_kill_the_briefing(self):
        def boom():
            raise ConnectionError("NWS down")

        briefing = MorningBriefing(cfg(), collectors={
            "📅 Today's schedule": lambda: ["09:00–10:00  Clinic"],
            "🌦 Weather": boom,
        })
        text = briefing.render_text()
        assert "Clinic" in text          # the good section still renders
        assert "unavailable" in text      # the bad one degrades gracefully

    def test_draft_only_footer_offers_drafts_not_sending(self):
        text = MorningBriefing(cfg(email_provider="gmail", email_permission="draft_only"),
                               collectors={}).render_text()
        assert "prepare drafts" in text and "approval" not in text


class FakeTask:
    def __init__(self, title, done=False, completed_on=None, priority="normal", due=None):
        self.title, self.done, self.completed_on = title, done, completed_on
        self.priority, self.due = priority, due


class FakeTaskFile:
    def __init__(self, tasks):
        self._tasks = tasks

    def completed_today(self, today):
        return [t for t in self._tasks if t.done and t.completed_on == today]

    def open_tasks(self):
        return [t for t in self._tasks if not t.done]

    def prioritized(self):
        return [t for t in self._tasks if not t.done]


class TestEveningWrapUp:
    def test_full_render(self):
        today = date.today()
        tf = FakeTaskFile([
            FakeTask("Chart notes", done=True, completed_on=today),
            FakeTask("Call lab"),
            FakeTask("Order supplies"),
        ])
        text = EveningWrapUp(cfg(), task_file=tf).render_text()
        assert "Chart notes" in text
        assert "Still open:** 2" in text
        assert "Suggested focus for tomorrow" in text
        assert "1. Call lab" in text

    def test_nothing_done_and_nothing_open(self):
        text = EveningWrapUp(cfg(), task_file=FakeTaskFile([])).render_text()
        assert "nothing marked complete" in text
        assert "Still open:** 0" in text


# --- improvements #9-16: weekend mode, ordering, quiet hours, headline, -------.
# --- line budget, streak, tomorrow preview, fallback note ---------------------
# New config knobs are set via setattr so old AssistantConfig objects (which
# lack these fields entirely) are also exercised by the default-path tests.

SATURDAY = date(2026, 8, 8)
MONDAY = date(2026, 8, 10)


class TestWeekendMode:
    def test_is_weekend(self):
        assert is_weekend(SATURDAY) is True
        assert is_weekend(date(2026, 8, 9)) is True   # Sunday
        assert is_weekend(MONDAY) is False

    def test_weekend_uses_lighter_section_set(self):
        c = cfg()
        c.briefing_weekend_sections = ["✅ Tasks"]
        briefing = MorningBriefing(c, collectors={
            "📅 Today's schedule": lambda: ["10:00–10:30  Standup"],
            "✅ Tasks": lambda: ["Buy milk"],
        })
        text = briefing.render_text(today=SATURDAY)
        assert "Buy milk" in text
        assert "Standup" not in text        # dropped on weekends
        assert "Today's schedule" not in text

    def test_weekday_ignores_weekend_section_list(self):
        c = cfg()
        c.briefing_weekend_sections = ["✅ Tasks"]
        briefing = MorningBriefing(c, collectors={
            "📅 Today's schedule": lambda: ["10:00–10:30  Standup"],
            "✅ Tasks": lambda: ["Buy milk"],
        })
        text = briefing.render_text(today=MONDAY)
        assert "Standup" in text            # full set on weekdays

    def test_weekend_mode_off_by_default(self):
        briefing = MorningBriefing(cfg(), collectors={
            "📅 Today's schedule": lambda: ["10:00–10:30  Brunch"],
        })
        assert "Brunch" in briefing.render_text(today=SATURDAY)


class TestSectionOrdering:
    def test_render_sections_reorders_by_name(self):
        sections = [Section("B", ["b"]), Section("A", ["a"]), Section("C", ["c"])]
        ordered = render_sections(sections, ["A", "B"])
        assert [s.title for s in ordered] == ["A", "B", "C"]  # unnamed keep order

    def test_render_sections_none_keeps_original(self):
        sections = [Section("B", ["b"]), Section("A", ["a"])]
        assert [s.title for s in render_sections(sections)] == ["B", "A"]

    def test_briefing_reads_section_order_from_config(self):
        c = cfg()
        c.briefing_section_order = ["✅ Tasks", "📅 Today's schedule"]
        briefing = MorningBriefing(c, collectors={
            "📅 Today's schedule": lambda: ["10:00  Standup"],
            "✅ Tasks": lambda: ["Buy milk"],
        })
        text = briefing.render_text(today=MONDAY)
        assert text.index("✅ Tasks") < text.index("📅 Today's schedule")


class TestQuietHours:
    def test_note_prepended_during_quiet_hours(self):
        c = cfg()
        c.quiet_hours = ("22:00", "07:00")
        text = MorningBriefing(c, collectors={}).render_text(
            today=MONDAY, now=datetime(2026, 8, 10, 23, 30))
        assert text.startswith("🌙 quiet hours")

    def test_overnight_window_wraps_past_midnight(self):
        c = cfg()
        c.quiet_hours = ("22:00", "07:00")
        text = MorningBriefing(c, collectors={}).render_text(
            today=MONDAY, now=datetime(2026, 8, 10, 6, 15))
        assert "🌙 quiet hours" in text

    def test_no_note_outside_quiet_hours(self):
        c = cfg()
        c.quiet_hours = ("22:00", "07:00")
        text = MorningBriefing(c, collectors={}).render_text(
            today=MONDAY, now=datetime(2026, 8, 10, 12, 0))
        assert "quiet hours" not in text

    def test_malformed_quiet_hours_never_kills_briefing(self):
        c = cfg()
        c.quiet_hours = ("not-a-time", None)
        text = MorningBriefing(c, collectors={}).render_text(
            today=MONDAY, now=datetime(2026, 8, 10, 23, 30))
        assert "quiet hours" not in text and "Walker" in text


class TestHeadline:
    def test_headline_summarizes_tasks_busiest_and_weather(self):
        sections = [
            Section("✅ Tasks", ["a", "b", "c"]),
            Section("📅 Today's schedule",
                    ["10:00–10:30  Standup", "10:30–11:00  Review", "14:00  Dentist"]),
            Section("🌦 Weather", ["☀️ Sunny, 24°C"]),
        ]
        assert headline(MONDAY, sections) == "3 tasks · busiest 10:00 · ☀️"

    def test_headline_empty_when_nothing_to_say(self):
        assert headline(MONDAY, [Section("✅ Tasks", [])]) == ""

    def test_headline_in_briefing_after_header(self):
        briefing = MorningBriefing(cfg(), collectors={
            "✅ Tasks": lambda: ["a", "b", "c"],
            "📅 Today's schedule": lambda: ["10:00  Standup", "10:30  Review"],
        })
        text = briefing.render_text(today=MONDAY)
        blocks = text.split("\n\n")
        assert "Walker" in blocks[0]                  # header still first
        assert blocks[1] == "3 tasks · busiest 10:00"  # headline right below


class TestLineBudget:
    def test_section_render_truncates_with_overflow_count(self):
        s = Section("✅ Tasks", ["t1", "t2", "t3", "t4", "t5"])
        text = s.render(max_lines=2)
        assert "t1" in text and "t2" in text and "t3" not in text
        assert "… and 3 more" in text

    def test_briefing_reads_max_lines_from_config(self):
        c = cfg()
        c.briefing_max_lines = 1
        briefing = MorningBriefing(c, collectors={
            "✅ Tasks": lambda: ["t1", "t2", "t3"],
        })
        text = briefing.render_text(today=MONDAY)
        assert "t1" in text and "t2" not in text and "… and 2 more" in text

    def test_default_budget_is_ten(self):
        briefing = MorningBriefing(cfg(), collectors={
            "✅ Tasks": lambda: [f"t{i}" for i in range(12)],
        })
        text = briefing.render_text(today=MONDAY)
        assert "… and 2 more" in text   # 10 shown + overflow line


class TestWrapUpExtras:
    def test_streak_rendered(self):
        today = date.today()
        tf = FakeTaskFile([FakeTask("Chart notes", done=True, completed_on=today)])
        text = EveningWrapUp(cfg(), task_file=tf).wrap_up(streak=4)
        assert "🔥 Streak: 4 consecutive days" in text

    def test_no_streak_line_when_zero(self):
        text = EveningWrapUp(cfg(), task_file=FakeTaskFile([])).wrap_up(streak=0)
        assert "Streak" not in text

    def test_tomorrow_preview_lines(self):
        text = EveningWrapUp(cfg(), task_file=FakeTaskFile([])).wrap_up(
            tomorrow=["09:00 Clinic", "13:00 Call lab"])
        assert "**Tomorrow**" in text
        assert "• 09:00 Clinic" in text and "• 13:00 Call lab" in text

    def test_fallback_quality_note(self):
        text = EveningWrapUp(cfg(), task_file=FakeTaskFile([])).wrap_up(used_fallback=True)
        assert FALLBACK_MARKER in text
        assert "thinking model" in text

    def test_plain_wrap_up_matches_render_text(self):
        today = date.today()
        tf = FakeTaskFile([FakeTask("Chart notes", done=True, completed_on=today)])
        w = EveningWrapUp(cfg(), task_file=tf)
        assert w.wrap_up() == w.render_text()
