"""Composer — assembles assistant output from the phrasebank (zero LLM tokens)
and isolates the small set of jobs that genuinely need a thinking model.

THE DEAL
--------
    templates  → everything formulaic (greetings, headers, status lines,
                 draft scaffolding). Rendered locally from phrasebank.db.
                 Cost: microseconds, zero tokens, works offline.

    thinking   → the FEW things requiring judgment (ranking priorities,
                 choosing which email deserves a reply, drafting a sensitive
                 message). For each, we build the SMALLEST prompt that
                 carries the decision — a compact task list, not a whole
                 conversation — and hand it to the configured strong model
                 (config.llm.thinking_model). Hermes executes the job; this
                 module only defines and sizes it.

RULE OF THUMB: a ThinkingJob prompt should be under ~400 characters. If it
needs more, the data — not the prompt — is probably wrong.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from executive_assistant.config import AssistantConfig
from executive_assistant.phrasebank import PhraseBank

#: The model prompt-budget we aim for on thinking jobs (chars, ≈ tokens×4).
#: Compare: a full briefing context runs 2,000+ chars. These jobs stay ~10× leaner.
THINKING_PROMPT_BUDGET = 600


@dataclass
class ThinkingJob:
    """One compact unit of LLM work, ready for the thinking model."""

    kind: str            # e.g. "prioritize_tasks", "triage_email", "draft_reply"
    prompt: str          # the COMPACT prompt — only what the decision needs
    context: dict = field(default_factory=dict)  # structured data for the caller

    @property
    def within_budget(self) -> bool:
        return len(self.prompt) <= THINKING_PROMPT_BUDGET


class BriefingComposer:
    """Template-first assembly for morning briefings and wrap-ups."""

    def __init__(self, config: AssistantConfig, phrasebank: PhraseBank | None = None,
                 day: date | None = None):
        self.cfg = config
        self.pb = phrasebank or PhraseBank()
        # One seed per day: the briefing voice is consistent within a day and
        # varies day to day — and tests can pin a date for reproducibility.
        self.day = day or date.today()
        self.rng = random.Random(self.day.toordinal())

    # --- template-side (zero tokens) ------------------------------------------
    def greeting(self) -> str:
        return self.pb.phrase("greeting_morning", rng=self.rng,
                              name=f", {self.cfg.user_name}" if self.cfg.user_name else "")

    def intro(self) -> str:
        return self.pb.phrase("briefing_intro", rng=self.rng)

    def fallback_line(self, source: str, reason: str) -> str:
        return self.pb.phrase("fallback", rng=self.rng, source=source, reason=reason)

    def draft_offer(self) -> str:
        return self.pb.phrase("draft_offer", rng=self.rng)

    def encouragement(self) -> str:
        return self.pb.phrase("encouragement", rng=self.rng)

    def priority_frame(self) -> str:
        return self.pb.phrase("priority_frame", rng=self.rng)

    # --- thinking-side (compact jobs for the strong model) -----------------------
    def job_prioritize_tasks(self, tasks: list, top_n: int = 3) -> ThinkingJob:
        """Rank open tasks. Prompt carries ONLY titles+due+priority — never
        the whole briefing context. Hard-capped at 10 rows to stay lean."""
        lines = []
        for i, t in enumerate(tasks[:10], 1):
            due = f", due {t.due}" if t.due else ""
            lines.append(f"{i}. {t.title} ({t.priority}{due})")
        prompt = (
            "Order these tasks by urgency: overdue first, then due date, "
            "then high priority. Reply with ONLY the task numbers in order, "
            "comma-separated.\n" + "\n".join(lines)
        )
        # structured context powers the deterministic fallback (see thinker.py)
        return ThinkingJob(kind="prioritize_tasks", prompt=prompt,
                           context={"top_n": top_n, "count": len(tasks),
                                    "tasks": [(t.title, t.due, t.priority)
                                              for t in tasks[:10]]})

    def job_triage_email(self, summaries: list) -> ThinkingJob:
        """Which unread email most deserves a reply? Sender+subject only."""
        lines = [f"{i}. {s.sender} — {s.subject}" for i, s in enumerate(summaries[:8], 1)]
        prompt = (
            "Which of these emails most needs a reply today? "
            "Reply with ONLY the number, or 0 for none.\n" + "\n".join(lines)
        )
        return ThinkingJob(kind="triage_email", prompt=prompt,
                           context={"count": len(summaries),
                                    "senders": [s.sender for s in summaries[:8]]})

    def job_draft_reply(self, sender: str, subject: str, body_excerpt: str,
                        tone: str = "neutral") -> ThinkingJob:
        """Draft ONE reply. The scaffold (opener/signoff) comes from the
        phrasebank; the model writes only the message core."""
        opener = self.pb.phrase("draft_opener", tone=tone, rng=self.rng, subject=subject)
        signoff = self.pb.phrase("signoff", tone=tone, rng=self.rng)
        prompt = (
            f"Write the body (2-4 sentences, {tone} tone) of a reply to "
            f"{sender} about '{subject}'. They wrote: {body_excerpt[:160]!r}. "
            "Body only, no greeting or signoff."
        )
        return ThinkingJob(kind="draft_reply", prompt=prompt,
                           context={"opener": opener, "signoff": signoff,
                                    "sender": sender, "subject": subject})

    # --- assembly ----------------------------------------------------------------
    def assemble_reply(self, job: ThinkingJob, model_body: str) -> str:
        """Stitch phrasebank scaffolding around the model's core text."""
        return (
            f"{job.context['opener']}\n\n"
            f"{model_body.strip()}\n\n"
            f"{job.context['signoff']}\n{self.cfg.user_name}"
        )
