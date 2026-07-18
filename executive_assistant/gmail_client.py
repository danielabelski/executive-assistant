"""Gmail client — read unread mail, create drafts, send (through the gate).

IMPORTANT SEPARATION OF CONCERNS
---------------------------------
This client is *capable* of sending, but it never decides WHETHER sending
is allowed — that is approval.py's job. Higher layers do:

    ruling = ApprovalGate(config).check_send(to)
    if ruling.ok:           gmail.send(...)
    elif NEEDS_APPROVAL:    ask the user in chat, then maybe gmail.send(...)
    else:                   gmail.create_draft(...)

Everything returns plain dicts so results serialize cleanly into briefings.
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from executive_assistant.google_auth import load_credentials
from executive_assistant.types import EmailSummary


class GmailClient:
    """Thin wrapper over the Gmail API. Construct with from_config()."""

    def __init__(self, service, important_senders: list[str] | None = None):
        # `service` is injected (not built here) so tests pass a mock.
        self._svc = service
        self._important = {a.lower() for a in (important_senders or [])}

    @classmethod
    def from_config(cls, config) -> "GmailClient":
        from executive_assistant.google_auth import GMAIL_SCOPES  # local: keep import surface small

        creds = load_credentials(config.token_path, GMAIL_SCOPES)
        return cls(build("gmail", "v1", credentials=creds, cache_discovery=False),
                   important_senders=config.important_senders)

    # --- reading -------------------------------------------------------------
    def search(self, query: str, max_results: int = 10) -> list[EmailSummary]:
        """Gmail search syntax, e.g. 'is:unread newer_than:1d'."""
        resp = (
            self._svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        out = []
        for stub in resp.get("messages", []):
            msg = (
                self._svc.users()
                .messages()
                .get(userId="me", id=stub["id"], format="metadata",
                     metadataHeaders=["From", "Subject", "Date"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            sender = headers.get("From", "")
            out.append(
                EmailSummary(
                    id=msg["id"],
                    thread_id=msg.get("threadId", ""),
                    sender=sender,
                    subject=headers.get("Subject", "(no subject)"),
                    date=headers.get("Date", ""),
                    snippet=msg.get("snippet", ""),
                    is_important_sender=self._is_important(sender),
                )
            )
        return out

    def unread_for_briefing(self, max_results: int = 5) -> list[EmailSummary]:
        """Overnight inbox signal: unread, skipping the noisy categories."""
        return self.search(
            "in:inbox is:unread -category:promotions -category:social -category:forums",
            max_results=max_results,
        )

    def get_body(self, message_id: str, max_chars: int = 4000) -> str:
        """Full plain-text body of one message (prefers text/plain parts)."""
        msg = (
            self._svc.users().messages().get(userId="me", id=message_id, format="full").execute()
        )
        return self._extract_text(msg.get("payload", {}))[:max_chars]

    def _extract_text(self, payload: dict) -> str:
        """Walk MIME parts; prefer text/plain, fall back to snippet-ish text."""
        mime = payload.get("mimeType", "")
        if mime == "text/plain" and payload.get("body", {}).get("data"):
            return _b64decode(payload["body"]["data"])
        for part in payload.get("parts", []):
            text = self._extract_text(part)
            if text:
                return text
        if payload.get("body", {}).get("data"):
            return _b64decode(payload["body"]["data"])
        return ""

    def _is_important(self, sender: str) -> bool:
        """Match on the address part of 'Name <addr@x.com>' or bare addr."""
        s = sender.lower()
        return any(addr in s for addr in self._important)

    # --- writing ---------------------------------------------------------------
    def create_draft(self, to: str, subject: str, body: str,
                     thread_id: str | None = None) -> dict:
        """Create a Gmail draft. This NEVER sends — safe under every policy."""
        raw = _encode_message(to, subject, body)
        draft_body: dict = {"message": {"raw": raw}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id
        draft = self._svc.users().drafts().create(userId="me", body=draft_body).execute()
        return {"status": "draft_created", "draft_id": draft["id"], "to": to, "subject": subject}

    def send(self, to: str, subject: str, body: str,
             thread_id: str | None = None) -> dict:
        """Actually send. Call ONLY after ApprovalGate allows it."""
        raw = _encode_message(to, subject, body)
        msg: dict = {"raw": raw}
        if thread_id:
            msg["threadId"] = thread_id
        sent = self._svc.users().messages().send(userId="me", body=msg).execute()
        return {"status": "sent", "id": sent["id"], "to": to}

    def reply(self, message_id: str, body: str) -> dict:
        """Reply within the original thread (Subject + threading handled)."""
        original = (
            self._svc.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata",
                 metadataHeaders=["From", "Subject", "Message-ID"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        return self.send(to=headers.get("From", ""), subject=subject, body=body,
                         thread_id=original.get("threadId"))


def _b64decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")


def _encode_message(to: str, subject: str, body: str) -> str:
    mime = MIMEText(body, "plain", "utf-8")
    mime["to"] = to
    mime["subject"] = subject
    return base64.urlsafe_b64encode(mime.as_bytes()).decode()
