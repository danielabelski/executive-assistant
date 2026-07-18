"""Tests for the thinker — LLM policy enforcement, Ollama HTTP, fallbacks."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

from executive_assistant.composer import ThinkingJob
from executive_assistant.config import AssistantConfig
from executive_assistant.thinker import (
    DRAFT_FALLBACK_BODY,
    OllamaError,
    Thinker,
    deterministic_fallback,
    ollama_generate,
    ollama_model_pulled,
    ollama_models,
    parse_ranking,
)

HOST = "http://localhost:11434"


def cfg(**kw) -> AssistantConfig:
    return AssistantConfig(user_name="Walker", **kw)


def prioritize_job():
    return ThinkingJob(kind="prioritize_tasks", prompt="…", context={
        "top_n": 2,
        "tasks": [
            ("Someday maybe", None, "low"),
            ("Due next week", (date.today() + timedelta(days=7)).isoformat(), "normal"),
            ("OVERDUE thing", (date.today() - timedelta(days=1)).isoformat(), "high"),
        ],
    })


def triage_job():
    return ThinkingJob(kind="triage_email", prompt="…", context={
        "senders": ["news@letter.com", "Important Client <vip@client.com>", "x@y.com"],
    })


class TestOllamaHttp:
    def test_models_lists_names(self):
        resp = MagicMock()
        resp.json.return_value = {"models": [{"name": "qwen2.5:3b"}, {"name": "gemma2:2b"}]}
        with patch("executive_assistant.thinker.requests.get", return_value=resp):
            assert ollama_models(HOST) == ["qwen2.5:3b", "gemma2:2b"]

    def test_models_unreachable_raises(self):
        with patch("executive_assistant.thinker.requests.get",
                   side_effect=requests.ConnectionError("refused")):
            with pytest.raises(OllamaError, match="unreachable"):
                ollama_models(HOST)

    def test_model_pulled_accepts_latest_suffix(self):
        with patch("executive_assistant.thinker.ollama_models",
                   return_value=["qwen2.5:latest", "gemma2:2b"]):
            assert ollama_model_pulled("qwen2.5", HOST) is True        # bare → :latest
            assert ollama_model_pulled("qwen2.5:latest", HOST) is True  # exact
            assert ollama_model_pulled("gemma2:2b", HOST) is True
            assert ollama_model_pulled("llama3.2:3b", HOST) is False

    def test_generate_returns_text(self):
        resp = MagicMock()
        resp.json.return_value = {"response": "  3, 1, 2  "}
        with patch("executive_assistant.thinker.requests.post", return_value=resp) as post:
            assert ollama_generate("p", "qwen2.5:3b", HOST) == "3, 1, 2"
            payload = post.call_args.kwargs["json"]
            assert payload["options"]["temperature"] == 0.2   # decisions, not prose

    def test_generate_empty_raises(self):
        resp = MagicMock()
        resp.json.return_value = {"response": "   "}
        with patch("executive_assistant.thinker.requests.post", return_value=resp):
            with pytest.raises(OllamaError, match="empty"):
                ollama_generate("p", "m", HOST)


class TestPolicy:
    def test_cloud_mode_returns_none_for_hermes(self):
        # cloud mode: the project never executes jobs; Hermes/active model does
        assert Thinker(cfg(llm_local_only=False)).run(prioritize_job()) is None

    def test_local_mode_uses_ollama(self):
        with patch("executive_assistant.thinker.ollama_generate", return_value="3, 2") as gen:
            outcome = Thinker(cfg(llm_local_only=True)).run(prioritize_job())
        assert outcome is not None
        assert outcome.text == "3, 2"
        assert outcome.engine == "ollama:qwen2.5:3b"
        gen.assert_called_once()

    def test_local_mode_falls_back_when_ollama_down(self):
        with patch("executive_assistant.thinker.ollama_generate",
                   side_effect=OllamaError("down")):
            outcome = Thinker(cfg(llm_local_only=True)).run(prioritize_job())
        assert outcome.engine == "fallback(ollama-down)"
        assert outcome.text                          # still a usable answer
        # …and NO cloud call exists anywhere in this code path by construction

    def test_local_mode_falls_back_when_model_hallucinates(self):
        """Regression from the live Jetson run: qwen2.5:3b answered '4,5,6'
        for a five-task list. Garbage must never reach the user."""
        with patch("executive_assistant.thinker.ollama_generate", return_value="4,5,6"):
            outcome = Thinker(cfg(llm_local_only=True)).run(prioritize_job())
        assert outcome.engine == "fallback(ollama-invalid)"
        assert outcome.text == "3, 2"                # deterministic answer instead

    def test_local_only_is_default_off(self):
        assert cfg().llm_local_only is False


class TestFallbacks:
    def test_prioritize_overdue_wins(self):
        # task 3 is overdue+high, task 2 due soon, task 1 someday → "3, 2"
        assert deterministic_fallback(prioritize_job(), cfg()) == "3, 2"

    def test_triage_important_sender_wins(self):
        c = cfg(important_senders=["vip@client.com"])
        assert deterministic_fallback(triage_job(), c) == "2"

    def test_triage_no_important_senders_is_zero(self):
        assert deterministic_fallback(triage_job(), cfg()) == "0"

    def test_draft_fallback_is_a_polite_body(self):
        job = ThinkingJob(kind="draft_reply", prompt="…", context={})
        assert deterministic_fallback(job, cfg()) == DRAFT_FALLBACK_BODY

    def test_unknown_kind_is_empty(self):
        assert deterministic_fallback(ThinkingJob("mystery", "…", {}), cfg()) == ""


class TestParseRanking:
    def test_extracts_numbers_in_order(self):
        assert parse_ranking("The top tasks are 2, 5 and 1.", 10) == [2, 5, 1]

    def test_dedupes_and_drops_out_of_range(self):
        assert parse_ranking("2, 2, 99, 3", 5) == [2, 3]

    def test_empty_on_garbage(self):
        assert parse_ranking("no numbers here", 5) == []
