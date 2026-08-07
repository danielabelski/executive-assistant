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

AUDIT TRAIL
-----------
Every ruling is appended as one JSON line to AUDIT_LOG_PATH (default
<project>/data/approval_log.jsonl): {ts, action, level, verdict, reason}.
The log is also the data source for the daily auto-send rate limit. A
logging failure NEVER blocks an action — the gate works with or without
its diary.

The module-level ``_`` is a passthrough hook wrapping user-facing reason
strings (swap it for a gettext/i18n function to translate the gate).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from executive_assistant.config import (
    PROJECT_ROOT,
    AssistantConfig,
    EmailPermission,
)

#: Where rulings are journaled. Override (e.g. in tests) to redirect.
AUDIT_LOG_PATH = PROJECT_ROOT / "data" / "approval_log.jsonl"

#: Passthrough hook around user-facing reason strings — replace with a
#: real translation function to localize the gate's explanations.
_ = lambda s: s  # noqa: E731


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


def _append_audit(action: str, level: str, ruling: Ruling) -> None:
    """Journal one ruling. Logging failure must never break the gate."""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "level": level,
            "verdict": ruling.decision.value,
            "reason": ruling.reason,
        }
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # the gate never fails because its diary is unreachable


def _todays_auto_sends(log_path: Path) -> int:
    """Count today's ALLOWED auto-send rulings already in the audit log."""
    today = datetime.now().date().isoformat()
    count = 0
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (entry.get("ts", "")[:10] == today
                    and entry.get("action") == "send_email"
                    and entry.get("level") == EmailPermission.AUTO_SEND_ROUTINE
                    and entry.get("verdict") == Decision.ALLOWED.value):
                count += 1
    except OSError:
        pass  # no log yet → no sends yet
    return count


class ApprovalGate:
    """Evaluates proposed actions against the user's configured policy."""

    def __init__(self, config: AssistantConfig):
        self.cfg = config

    def _record(self, action: str, level: str, ruling: Ruling) -> Ruling:
        _append_audit(action, level, ruling)
        return ruling

    # --- pure evaluations (no audit writes; explain() uses these) -----------

    def _evaluate_send(self, to_address: str) -> Ruling:
        level = self.cfg.email_permission
        to_address = (to_address or "").strip().lower()

        if level == EmailPermission.DRAFT_ONLY:
            return Ruling(
                Decision.FORBIDDEN,
                _("Permission is draft_only — I can prepare a Gmail draft, "
                  "but sending is disabled. Review the draft in Gmail."),
            )

        if level == EmailPermission.APPROVE_SEND:
            return Ruling(
                Decision.NEEDS_APPROVAL,
                _("Permission is approve_send — I need your explicit yes "
                  "before this goes out."),
            )

        # auto_send_routine: only pre-cleared senders bypass approval
        routine = {a.lower() for a in self.cfg.routine_senders}
        if to_address in routine:
            # Rate limit: too many auto-sends today → back to asking.
            limit = getattr(self.cfg, "daily_auto_send_limit", 20)
            if _todays_auto_sends(AUDIT_LOG_PATH) >= limit:
                return Ruling(
                    Decision.NEEDS_APPROVAL,
                    _(f"Daily auto-send limit ({limit}) reached — this one "
                      "needs your approval."),
                )
            return Ruling(
                Decision.ALLOWED,
                _(f"{to_address} is on your routine_senders list — sending "
                  "automatically per your auto_send_routine setting."),
            )
        return Ruling(
            Decision.NEEDS_APPROVAL,
            _(f"{to_address} is not on routine_senders — approval required."),
        )

    def _evaluate_draft(self) -> Ruling:
        if not self.cfg.email_enabled:
            return Ruling(Decision.FORBIDDEN, _("No email provider is enabled."))
        return Ruling(Decision.ALLOWED, _("Drafts never send; always allowed."))

    def _evaluate_calendar_write(self) -> Ruling:
        if not self.cfg.calendar_enabled:
            return Ruling(Decision.FORBIDDEN,
                          _("Calendar integration is disabled."))
        return Ruling(
            Decision.NEEDS_APPROVAL,
            _("Calendar changes always require your confirmation."),
        )

    # --- public, auditing entry points ---------------------------------------

    def check_send(self, to_address: str) -> Ruling:
        """May the assistant SEND an email to `to_address` right now?

        The three permission levels, as promised during onboarding:

        * draft_only        → FORBIDDEN. Always. Create a draft instead.
        * approve_send      → NEEDS_APPROVAL for everyone.
        * auto_send_routine → ALLOWED only for addresses in routine_senders;
                              everyone else still NEEDS_APPROVAL — and once
                              the daily auto-send limit is hit, so do they.
        """
        ruling = self._evaluate_send(to_address)
        return self._record("send_email", self.cfg.email_permission, ruling)

    def check_draft(self) -> Ruling:
        """Creating a draft is always allowed when an email provider is
        enabled — drafts send nothing, on ANY provider (Gmail drafts API,
        IMAP APPEND-to-Drafts; both are inert until a human hits send)."""
        ruling = self._evaluate_draft()
        return self._record("draft_email", self.cfg.email_permission, ruling)

    def check_calendar_write(self) -> Ruling:
        """Creating/deleting calendar events always asks — a wrong event is
        worse than a wrong draft because other people may see it."""
        ruling = self._evaluate_calendar_write()
        return self._record("calendar_write", self.cfg.calendar_provider, ruling)


def check(action: str, config: AssistantConfig) -> Ruling:
    """Functional front door: `check("send_email:a@b.com", cfg)` → Ruling.

    Known actions: send_email[:address], draft_email, calendar_write.
    Anything unrecognized is treated as NEEDS_APPROVAL — unknown actions
    ask rather than silently pass.
    """
    gate = ApprovalGate(config)
    name, _sep, arg = (action or "").partition(":")
    name = name.strip().lower()
    if name == "send_email":
        return gate.check_send(arg.strip())
    if name == "draft_email":
        return gate.check_draft()
    if name == "calendar_write":
        return gate.check_calendar_write()
    ruling = Ruling(
        Decision.NEEDS_APPROVAL,
        _(f"Unknown action {action!r} — asking first, to be safe."),
    )
    return gate._record(name or "unknown", config.email_permission, ruling)


def explain(action: str, config: AssistantConfig) -> str:
    """Human-readable WHY for a proposed action — without writing the log.

    e.g. draft_only mode → "draft_only mode: sending is always forbidden".
    """
    gate = ApprovalGate(config)
    name, _sep, arg = (action or "").partition(":")
    name = name.strip().lower()

    if name == "send_email":
        level = config.email_permission
        if level == EmailPermission.DRAFT_ONLY:
            return _("draft_only mode: sending is always forbidden — "
                     "a draft is created instead.")
        if level == EmailPermission.APPROVE_SEND:
            return _("approve_send mode: every send asks for your explicit "
                     "yes first.")
        addr = arg.strip().lower()
        routine = {a.lower() for a in config.routine_senders}
        if addr in routine:
            limit = getattr(config, "daily_auto_send_limit", 20)
            return _(f"auto_send_routine mode: {addr} is pre-cleared, so it "
                     f"sends automatically (up to {limit}/day, then it asks).")
        return _(f"auto_send_routine mode: {addr or 'this address'} is not "
                 "on routine_senders, so it asks first.")
    if name == "draft_email":
        if not config.email_enabled:
            return _("No email provider is enabled — drafts are impossible.")
        return _("Drafts are always allowed: they send nothing until you do.")
    if name == "calendar_write":
        if not config.calendar_enabled:
            return _("Calendar integration is disabled — writes are forbidden.")
        return _("Calendar writes always ask: other people can see events.")
    return _(f"Unknown action {action!r} — it would ask first, to be safe.")
