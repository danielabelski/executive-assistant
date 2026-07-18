"""Tests for the approval gate — proving each permission level behaves as promised."""

from executive_assistant.approval import ApprovalGate, Decision
from executive_assistant.config import (
    AssistantConfig,
    CalendarProvider,
    EmailProvider,
    EmailPermission,
)


def gate_for(level, **kw) -> ApprovalGate:
    return ApprovalGate(AssistantConfig(
        email_provider=EmailProvider.GMAIL,
        calendar_provider=CalendarProvider.GOOGLE,
        email_permission=level, **kw))


class TestDraftOnly:
    def test_send_is_forbidden_not_just_approval(self):
        ruling = gate_for(EmailPermission.DRAFT_ONLY).check_send("anyone@x.com")
        assert ruling.decision is Decision.FORBIDDEN
        assert "draft" in ruling.reason.lower()

    def test_drafts_still_allowed(self):
        assert gate_for(EmailPermission.DRAFT_ONLY).check_draft().ok


class TestApproveSend:
    def test_every_send_needs_approval(self):
        ruling = gate_for(EmailPermission.APPROVE_SEND).check_send("anyone@x.com")
        assert ruling.decision is Decision.NEEDS_APPROVAL

    def test_even_routine_listed_senders_ask(self):
        ruling = gate_for(EmailPermission.APPROVE_SEND,
                          routine_senders=["news@x.com"]).check_send("news@x.com")
        assert ruling.decision is Decision.NEEDS_APPROVAL


class TestAutoSendRoutine:
    def test_routine_sender_allowed(self):
        ruling = gate_for(EmailPermission.AUTO_SEND_ROUTINE,
                          routine_senders=["News@X.com"]).check_send("news@x.com")
        assert ruling.decision is Decision.ALLOWED  # case-insensitive match

    def test_stranger_still_asks(self):
        ruling = gate_for(EmailPermission.AUTO_SEND_ROUTINE,
                          routine_senders=["news@x.com"]).check_send("client@y.com")
        assert ruling.decision is Decision.NEEDS_APPROVAL

    def test_empty_routine_list_means_everything_asks(self):
        ruling = gate_for(EmailPermission.AUTO_SEND_ROUTINE).check_send("news@x.com")
        assert ruling.decision is Decision.NEEDS_APPROVAL


class TestProviderAgnosticism:
    def test_draft_allowed_for_imap_provider(self):
        gate = ApprovalGate(AssistantConfig(email_provider=EmailProvider.IMAP))
        assert gate.check_draft().ok

    def test_draft_forbidden_when_no_email_provider(self):
        gate = ApprovalGate(AssistantConfig(email_provider=EmailProvider.NONE))
        assert gate.check_draft().decision is Decision.FORBIDDEN

    def test_calendar_write_always_asks_any_provider(self):
        for provider in (CalendarProvider.GOOGLE, CalendarProvider.CALDAV,
                         CalendarProvider.LOCAL_ICS):
            gate = ApprovalGate(AssistantConfig(calendar_provider=provider))
            assert gate.check_calendar_write().decision is Decision.NEEDS_APPROVAL
