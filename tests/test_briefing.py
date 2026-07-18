"""Tests for briefing aggregation — fake collectors, real rendering logic."""

from datetime import date

from executive_assistant.briefing import EveningWrapUp, MorningBriefing, _run
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
