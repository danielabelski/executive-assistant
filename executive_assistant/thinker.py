"""Thinker — executes composer 'thinking jobs' under the user's LLM policy.

THE POLICY
----------
    llm.local_only: false → jobs return to the caller (Hermes / active cloud
                            model executes them). Quality first, per-token fees.
    llm.local_only: true  → jobs run on LOCAL OLLAMA ONLY. No paid/cloud API
                            is ever called. If Ollama is unreachable or the
                            model isn't pulled, DETERMINISTIC fallbacks keep
                            the assistant fully functional at zero cost.

The zero-fee guarantee is structural, not aspirational: in local_only mode
this module is the ONLY code path that executes a thinking job, and it
never touches a non-localhost endpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import requests

from executive_assistant.composer import ThinkingJob
from executive_assistant.config import AssistantConfig

#: Short outputs only — jobs demand terse replies ("ONLY the numbers").
GENERATE_TIMEOUT = 90          # seconds; a 3B model on Jetson needs headroom
TAGS_TIMEOUT = 5
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}

#: Generic body used when a draft is needed but no model is available.
DRAFT_FALLBACK_BODY = (
    "Thank you for your message — I've received it and will follow up "
    "with a full reply shortly."
)


class OllamaError(Exception):
    pass


# --- Ollama HTTP (stdlib-level, no ollama package dependency) -----------------

def ollama_models(host: str) -> list[str]:
    """Names of locally pulled models, or OllamaError if unreachable."""
    try:
        resp = requests.get(f"{host.rstrip('/')}/api/tags", timeout=TAGS_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(f"Ollama unreachable at {host}: {exc}") from exc
    return [m.get("name", "") for m in resp.json().get("models", [])]


def ollama_model_pulled(model: str, host: str) -> bool:
    """True if `model` (with or without :latest) is available locally."""
    names = ollama_models(host)
    return model in names or f"{model}:latest" in names


def ollama_generate(prompt: str, model: str, host: str) -> str:
    """One completion from a local model. Low temperature: jobs want
    decisions, not prose."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 150},
    }
    try:
        resp = requests.post(f"{host.rstrip('/')}/api/generate",
                             json=payload, timeout=GENERATE_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OllamaError(f"Ollama generate failed: {exc}") from exc
    text = resp.json().get("response", "").strip()
    if not text:
        raise OllamaError("Ollama returned an empty response")
    return text


# --- Result type -----------------------------------------------------------------

@dataclass
class ThinkingOutcome:
    text: str
    engine: str          # "ollama:<model>" | "fallback" | "hermes"


# --- The policy-enforcing executor ---------------------------------------------------

class Thinker:
    """Executes ThinkingJobs according to cfg.llm policy."""

    def __init__(self, cfg: AssistantConfig):
        self.cfg = cfg
        self.host = cfg.ollama_host
        self.model = cfg.ollama_model

    @property
    def local_only(self) -> bool:
        return self.cfg.llm_local_only

    def status(self) -> dict:
        """Used by `doctor`: is the local path healthy?"""
        try:
            pulled = ollama_model_pulled(self.model, self.host)
            return {"reachable": True, "model_pulled": pulled, "model": self.model}
        except OllamaError:
            return {"reachable": False, "model_pulled": False, "model": self.model}

    def run(self, job: ThinkingJob) -> ThinkingOutcome | None:
        """Execute a job per policy.

        Returns None in cloud mode — the caller (Hermes / active model) is
        expected to execute the job itself. In local_only mode, ALWAYS
        returns an outcome: a validated Ollama answer if healthy, else the
        deterministic fallback (marked by engine name). Zero fees either way.
        """
        if not self.local_only:
            return None
        try:
            raw = ollama_generate(job.prompt, self.model, self.host)
        except OllamaError:
            return ThinkingOutcome(text=deterministic_fallback(job, self.cfg),
                                   engine="fallback(ollama-down)")
        normalized = validate_and_normalize(job, raw)
        if normalized is not None:
            return ThinkingOutcome(text=normalized, engine=f"ollama:{self.model}")
        # Model answered garbage (small models do) — heuristics win this round.
        return ThinkingOutcome(text=deterministic_fallback(job, self.cfg),
                               engine="fallback(ollama-invalid)")


def validate_and_normalize(job: ThinkingJob, text: str) -> str | None:
    """Check a model's raw answer is usable; return the canonical form or None.

    Small local models sometimes hallucinate ('4,5,6' for five tasks). Each
    job kind has a checkable contract — if the answer breaks it, the caller
    should fall back rather than ship nonsense to the user.
    """
    if job.kind == "prioritize_tasks":
        ranking = parse_ranking(text, len(job.context.get("tasks", [])))
        return ", ".join(str(n) for n in ranking) if ranking else None
    if job.kind == "triage_email":
        match = re.search(r"\d+", text)
        if match and 0 <= int(match.group()) <= job.context.get("count", 0):
            return str(int(match.group()))
        return None
    if job.kind == "draft_reply":
        return text if len(text.split()) >= 3 else None
    return text or None


# --- Deterministic fallbacks (zero tokens, always available) -------------------------

def deterministic_fallback(job: ThinkingJob, cfg: AssistantConfig) -> str:
    """Answer a thinking job with pure heuristics. Not clever — dependable."""
    if job.kind == "prioritize_tasks":
        return _fallback_prioritize(job)
    if job.kind == "triage_email":
        return _fallback_triage(job, cfg)
    if job.kind == "draft_reply":
        return DRAFT_FALLBACK_BODY
    return ""


def _fallback_prioritize(job: ThinkingJob) -> str:
    """Urgency = soonest due date, then priority rank. Overdue wins."""
    tasks = job.context.get("tasks", [])       # list of (title, due|None, priority)
    top_n = job.context.get("top_n", 3)

    def key(item):
        idx, (_title, due, priority) = item
        due_key = date.max.isoformat() if not due else due
        return (due_key, PRIORITY_RANK.get(str(priority).lower(), 1), idx)

    ranked = sorted(enumerate(tasks, 1), key=key)
    return ", ".join(str(i) for i, _ in ranked[:top_n])


def _fallback_triage(job: ThinkingJob, cfg: AssistantConfig) -> str:
    """First email from an important sender; else 'none'."""
    senders = job.context.get("senders", [])
    important = [s.lower() for s in cfg.important_senders]
    for i, sender in enumerate(senders, 1):
        if any(imp in sender.lower() for imp in important):
            return str(i)
    return "0"


def parse_ranking(text: str, maximum: int) -> list[int]:
    """Pull a ranking out of model output, tolerating chatter.

    'The top tasks are 2, 5 and 1.' → [2, 5, 1]. Out-of-range dropped.
    """
    seen: list[int] = []
    for token in re.findall(r"\d+", text):
        n = int(token)
        if 1 <= n <= maximum and n not in seen:
            seen.append(n)
    return seen
