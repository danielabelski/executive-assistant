"""Tests for the composer — template assembly + compact thinking jobs."""

from datetime import date

import pytest

from executive_assistant.composer import (
    THINKING_PROMPT_BUDGET,
    BriefingComposer,
    ThinkingJob,
)
from executive_assistant.config import AssistantConfig
from executive_assistant.phrasebank import PhraseBank, build_db


@pytest.fixture(scope="module")
def pb(tmp_path_factory):
    return PhraseBank(build_db(tmp_path_factory.mktemp("pb") / "phrasebank.db"))


def composer(pb, **kw) -> BriefingComposer:
    return BriefingComposer(AssistantConfig(user_name="Walker", **kw),
                            phrasebank=pb, day=date(2026, 7, 18))


class FakeTask:
    def __init__(self, title, due=None, priority="normal"):
        self.title, self.due, self.priority = title, due, priority


class FakeSummary:
    def __init__(self, sender, subject):
        self.sender, self.subject = sender, subject


class TestTemplateSide:
    def test_greeting_fills_name(self, pb):
        text = composer(pb).greeting()
        assert "Walker" in text and "{" not in text

    def test_same_day_same_voice(self, pb):
        assert composer(pb).greeting() == composer(pb).greeting()

    def test_different_days_can_vary(self, pb):
        greetings = {
            BriefingComposer(AssistantConfig(user_name="W"), phrasebank=pb,
                             day=date(2026, 7, d)).greeting()
            for d in range(1, 29)
        }
        assert len(greetings) > 1   # voice rotates across days

    def test_fallback_line_renders(self, pb):
        line = composer(pb).fallback_line("Gmail", "auth missing")
        assert "Gmail" in line and "auth missing" in line


class TestThinkingJobs:
    def test_prioritize_prompt_is_compact(self, pb):
        tasks = [FakeTask(f"Task {i}") for i in range(40)]  # more than the cap
        job = composer(pb).job_prioritize_tasks(tasks)
        assert job.kind == "prioritize_tasks"
        assert job.within_budget, f"{len(job.prompt)} chars exceeds {THINKING_PROMPT_BUDGET}"
        assert "ONLY the task numbers" in job.prompt     # forces terse model output
        assert "10." in job.prompt and "11." not in job.prompt  # hard cap applied

    def test_triage_prompt_is_compact(self, pb):
        summaries = [FakeSummary(f"s{i}@x.com", f"Subject {i}") for i in range(20)]
        job = composer(pb).job_triage_email(summaries)
        assert job.within_budget
        assert "ONLY the number" in job.prompt
        assert "8." in job.prompt and "9." not in job.prompt   # capped at 8

    def test_draft_reply_scaffolds_from_phrasebank(self, pb):
        job = composer(pb).job_draft_reply("Client <c@x.com>", "Schedule change",
                                           "Can we move our meeting to 3pm?", tone="warm")
        assert job.within_budget
        assert job.context["opener"]          # phrasebank provided the scaffolding
        assert job.context["signoff"]
        assert "Body only" in job.prompt      # model writes only the core

    def test_assemble_reply_stitches_parts(self, pb):
        job = composer(pb).job_draft_reply("c@x.com", "Hi", "hello there", tone="neutral")
        full = composer(pb).assemble_reply(job, "Yes, 3pm works perfectly.")
        assert job.context["opener"] in full
        assert "Yes, 3pm works perfectly." in full
        assert job.context["signoff"] in full
        assert full.rstrip().endswith("Walker")
