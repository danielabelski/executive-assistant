"""Tests for the composer — template assembly + compact thinking jobs."""

from datetime import date

import pytest

from executive_assistant.composer import (
    DEFAULT_JOB_TIMEOUT_S,
    FALLBACK_MARKER,
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


# --- improvements #9-16: result cache, fallback marker, timeout plumbing -------


class TestFallbackMarker:
    def test_marker_constant(self):
        assert FALLBACK_MARKER == "[fallback]"


class TestJobResultCache:
    def test_cache_miss_then_hit(self, pb):
        c = composer(pb)
        job = c.job_prioritize_tasks([FakeTask("A"), FakeTask("B")])
        assert c.cache_get(job) is None               # miss before anything stored
        c.cache_put(job, "2,1")
        assert c.cache_get(job) == "2,1"              # hit for identical job

    def test_different_prompt_is_a_miss(self, pb):
        c = composer(pb)
        c.cache_put(c.job_prioritize_tasks([FakeTask("A")]), "1")
        assert c.cache_get(c.job_prioritize_tasks([FakeTask("B")])) is None

    def test_cache_is_per_day(self, pb):
        c1 = composer(pb)  # pinned to 2026-07-18 by the fixture helper
        job = c1.job_prioritize_tasks([FakeTask("A")])
        c1.cache_put(job, "1")
        c2 = BriefingComposer(AssistantConfig(user_name="Walker"),
                              phrasebank=pb, day=date(2026, 7, 19))
        assert c2.cache_get(c2.job_prioritize_tasks([FakeTask("A")])) is None

    def test_cache_key_stable_and_content_addressed(self, pb):
        c = composer(pb)
        job = c.job_prioritize_tasks([FakeTask("A")])
        assert c.cache_key(job) == c.cache_key(job)
        assert str(date(2026, 7, 18).toordinal()) in c.cache_key(job)


class TestTimeoutPlumbing:
    def test_default_timeout_is_30s(self, pb):
        c = composer(pb)
        assert c.job_prioritize_tasks([FakeTask("A")]).timeout_s == 30.0
        assert c.job_triage_email([FakeSummary("a@x.com", "Hi")]).timeout_s == 30.0
        assert c.job_draft_reply("a@x.com", "Hi", "hello").timeout_s == 30.0

    def test_custom_timeout_reaches_every_job_type(self, pb):
        c = BriefingComposer(AssistantConfig(user_name="Walker"),
                             phrasebank=pb, day=date(2026, 7, 18), timeout=5)
        assert c.job_prioritize_tasks([FakeTask("A")]).timeout_s == 5
        assert c.job_triage_email([FakeSummary("a@x.com", "Hi")]).timeout_s == 5
        assert c.job_draft_reply("a@x.com", "Hi", "hello").timeout_s == 5

    def test_thinking_job_timeout_defaults_without_composer(self):
        job = ThinkingJob(kind="k", prompt="p")
        assert job.timeout_s == DEFAULT_JOB_TIMEOUT_S
