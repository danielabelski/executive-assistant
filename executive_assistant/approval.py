"""The approval gate — every sensitive action passes through here.

WHY THIS MODULE EXISTS
----------------------
The whole point of the onboarding chooser is that the USER decides how
much autonomy the assistant gets. That decision is useless unless every
code path that could act on the user's behalf checks it first. So:

    * briefing.py never sends email directly
    * gmail_client.py can *technically* send, but higher layers call
      ApprovalGate.check_send() BEFORE invoking it
    * tests prove each permission level behaves as documented

Think of it as a tiny policy engine: config in, decision out.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from executive_assistant.config import AssistantConfig, EmailPermission


class Decision(Enum):
    """What the gate decided about a proposed action."""

    ALLOWED = "allowed"                  # go ahead, no human in the loop
    NEEDS_APPROVAL = "needs_approval"    # must ask the user first
    FORBIDDEN = "forbidden"              # policy says never; do not ask, do not do


@dataclass
class Ruling:
    """A decision plus a human-readable explanation (shown in chat/logs)."""

    decision: Decision
    reason: str

    @property
    def ok(self) -> bool:
        return self.decision is Decision.ALLOWED


class ApprovalGate:
    """Evaluates proposed actions against the user's configured policy."""

    def __init__(self, config: AssistantConfig):
        self.cfg = config

    def check_send(self, to_address: str) -> Ruling:
        """May the assistant SEND an email to `to_address` right now?

        The three permission levels, as promised during onboarding:

        * draft_only        → FORBIDDEN. Always. Create a draft instead.
        * approve_send      → NEEDS_APPROVAL for everyone.
        * auto_send_routine → ALLOWED only for addresses in routine_senders;
                              everyone else still NEEDS_APPROVAL.
        """
        level = self.cfg.email_permission
        to_address = (to_address or "").strip().lower()

        if level == EmailPermission.DRAFT_ONLY:
            return Ruling(
                Decision.FORBIDDEN,
                "Permission is draft_only — I can prepare a Gmail draft, "
                "but sending is disabled. Review the draft in Gmail.",
            )

        if level == EmailPermission.APPROVE_SEND:
            return Ruling(
                Decision.NEEDS_APPROVAL,
                "Permission is approve_send — I need your explicit yes "
                "before this goes out.",
            )

        # auto_send_routine: only pre-cleared senders bypass approval
        routine = {a.lower() for a in self.cfg.routine_senders}
        if to_address in routine:
            return Ruling(
                Decision.ALLOWED,
                f"{to_address} is on your routine_senders list — sending "
                "automatically per your auto_send_routine setting.",
            )
        return Ruling(
            Decision.NEEDS_APPROVAL,
            f"{to_address} is not on routine_senders — approval required.",
        )

    def check_draft(self) -> Ruling:
        """Creating a draft is always allowed when an email provider is
        enabled — drafts send nothing, on ANY provider (Gmail drafts API,
        IMAP APPEND-to-Drafts; both are inert until a human hits send)."""
        if not self.cfg.email_enabled:
            return Ruling(Decision.FORBIDDEN, "No email provider is enabled.")
        return Ruling(Decision.ALLOWED, "Drafts never send; always allowed.")

    def check_calendar_write(self) -> Ruling:
        """Creating/deleting calendar events always asks — a wrong event is
        worse than a wrong draft because other people may see it."""
        if not self.cfg.calendar_enabled:
            return Ruling(Decision.FORBIDDEN, "Calendar integration is disabled.")
        return Ruling(
            Decision.NEEDS_APPROVAL,
            "Calendar changes always require your confirmation.",
        )
