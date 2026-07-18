"""IMAP+SMTP email provider — the "any email account" option.

WHY THIS PROVIDER EXISTS
------------------------
Gmail is one account type. This module covers everything else — Fastmail,
Outlook/Hotmail, Yahoo, ProtonMail (via Bridge), self-hosted Dovecot —
using only the Python standard library (imaplib/smtplib/email). If your
provider supports an app password, it works here.

MAPPING THE GMAIL-STYLE INTERFACE ONTO IMAP
--------------------------------------------
    list unread        → UID SEARCH UNSEEN + header/snippet FETCH
    read full body     → UID FETCH BODY.PEEK[] (never sets \\Seen)
    create draft       → APPEND to the Drafts mailbox with the \\Draft flag
                         (this is how every IMAP client makes drafts — and
                         like Gmail drafts, it can never send anything)
    send               → SMTP_SSL + login + send_message (through ApprovalGate)
    reply              → In-Reply-To / References headers for threading

Message ids are IMAP UIDs (stable within a folder). thread_id is left empty
— IMAP has no native thread concept; threading is done via headers at send time.

The network surface is one injectable `_connector` callable, so tests drive
the entire client with fake socket objects and zero network.
"""

from __future__ import annotations

import imaplib
import smtplib
from email import message_from_bytes
from email.header import decode_header, make_header
from email.mime.text import MIMEText
from email.utils import parseaddr

from executive_assistant.types import EmailSummary

TIMEOUT = 20  # seconds — a hung mail server must never hang a briefing


class ImapError(Exception):
    """Raised on connect/login/fetch failures; briefing shows a fallback."""


# --- pure parsing helpers (module level so tests hit them directly) --------------


def decode_rfc2047(value: str) -> str:
    """'=?UTF-8?B?...?='-style encoded headers → plain unicode."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value  # tolerate malformed encodings — show raw rather than die


def parse_header_block(raw: bytes) -> dict[str, str]:
    """Raw header bytes → {From, Subject, Date, Message-ID} (decoded)."""
    msg = message_from_bytes(raw)
    return {
        "From": decode_rfc2047(msg.get("From", "")),
        "Subject": decode_rfc2047(msg.get("Subject", "(no subject)")),
        "Date": msg.get("Date", ""),
        "Message-ID": msg.get("Message-ID", ""),
    }


def extract_text_body(raw_message: bytes, max_chars: int = 4000) -> str:
    """Full message bytes → best-effort plain-text body (prefers text/plain)."""
    msg = message_from_bytes(raw_message)
    fallback = ""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            text = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            continue
        if ctype == "text/plain":
            return text[:max_chars]
        fallback = fallback or text[:max_chars]
    return fallback


class ImapEmailClient:
    """Interface-compatible with GmailClient, backed by IMAP+SMTP."""

    def __init__(self, host: str, username: str, password: str,
                 port: int = 993, smtp_host: str = "", smtp_port: int = 465,
                 drafts_folder: str = "Drafts",
                 important_senders: list[str] | None = None,
                 _connector=None):
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.smtp_host = smtp_host or host.replace("imap.", "smtp.")
        self.smtp_port = smtp_port
        self.drafts_folder = drafts_folder
        self._important = {a.lower() for a in (important_senders or [])}
        # Injectable connection factory (tests); production uses IMAP4_SSL.
        self._connector = _connector or (
            lambda: imaplib.IMAP4_SSL(self.host, self.port, timeout=TIMEOUT))

    # --- connection -----------------------------------------------------------
    def _connect(self):
        try:
            conn = self._connector()
            conn.login(self.username, self.password)
            return conn
        except imaplib.IMAP4.error as exc:
            raise ImapError(f"IMAP login failed for {self.username}: {exc}") from exc
        except OSError as exc:
            raise ImapError(f"Cannot reach {self.host}:{self.port} — {exc}") from exc

    # --- reading ----------------------------------------------------------------
    def unread_for_briefing(self, max_results: int = 5) -> list[EmailSummary]:
        conn = self._connect()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.uid("SEARCH", None, "UNSEEN")
            if typ != "OK":
                raise ImapError(f"SEARCH failed: {typ}")
            uids = data[0].split()[-max_results:]  # newest last → take the tail
            summaries = []
            for uid in reversed(uids):  # newest first in the briefing
                summaries.append(self._fetch_summary(conn, uid.decode()))
            return summaries
        finally:
            _quiet(conn.logout)

    def _fetch_summary(self, conn, uid: str) -> EmailSummary:
        """Headers + a small body peek — never marks the message read."""
        typ, data = conn.uid(
            "FETCH", uid,
            "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] BODY.PEEK[TEXT]<0.200>)",
        )
        if typ != "OK":
            raise ImapError(f"FETCH failed for UID {uid}")
        header_bytes, peek_bytes = _literals(data)
        headers = parse_header_block(header_bytes)
        snippet = " ".join(
            peek_bytes.decode("utf-8", errors="replace").split())[:160]
        sender = headers["From"]
        return EmailSummary(
            id=uid, thread_id="", sender=sender,
            subject=headers["Subject"], date=headers["Date"], snippet=snippet,
            is_important_sender=self._is_important(sender),
        )

    def get_body(self, message_id: str, max_chars: int = 4000) -> str:
        conn = self._connect()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.uid("FETCH", message_id, "(BODY.PEEK[])")
            if typ != "OK":
                raise ImapError(f"FETCH failed for UID {message_id}")
            literals = _literals(data)
            return extract_text_body(literals[0], max_chars) if literals else ""
        finally:
            _quiet(conn.logout)

    def _is_important(self, sender: str) -> bool:
        _, addr = parseaddr(sender)
        addr = addr.lower()
        return any(imp in addr or imp in sender.lower() for imp in self._important)

    # --- writing (drafts via IMAP; sending via SMTP) --------------------------------
    @staticmethod
    def _mime(to: str, subject: str, body: str,
              in_reply_to: str = "", references: str = "") -> MIMEText:
        mime = MIMEText(body, "plain", "utf-8")
        mime["to"] = to
        mime["subject"] = subject
        mime["from"] = ""  # server fills in for the authenticated user
        if in_reply_to:
            mime["In-Reply-To"] = in_reply_to
            mime["References"] = references or in_reply_to
        return mime

    def create_draft(self, to: str, subject: str, body: str,
                     thread_id: str | None = None) -> dict:
        """APPEND to the Drafts mailbox with \\Draft — visible in every mail
        client, and (by construction) incapable of sending."""
        mime = self._mime(to, subject, body)
        conn = self._connect()
        try:
            mailbox = f'"{self.drafts_folder}"' if " " in self.drafts_folder else self.drafts_folder
            typ, _ = conn.append(mailbox, "\\Draft", None, mime.as_bytes())
            if typ != "OK":
                raise ImapError(f"APPEND to {self.drafts_folder} failed: {typ}")
            return {"status": "draft_created", "draft_id": f"imap:{self.drafts_folder}",
                    "to": to, "subject": subject}
        finally:
            _quiet(conn.logout)

    def send(self, to: str, subject: str, body: str,
             thread_id: str | None = None,
             in_reply_to: str = "", references: str = "") -> dict:
        """SMTP send — call ONLY after ApprovalGate allows it."""
        mime = self._mime(to, subject, body, in_reply_to, references)
        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=TIMEOUT) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(mime, from_addr=self.username, to_addrs=[to])
        except (smtplib.SMTPException, OSError) as exc:
            raise ImapError(f"SMTP send failed: {exc}") from exc
        return {"status": "sent", "id": "smtp", "to": to}

    def reply(self, message_id: str, body: str) -> dict:
        """Reply with proper threading headers (Message-ID chain)."""
        conn = self._connect()
        try:
            conn.select("INBOX", readonly=True)
            typ, data = conn.uid(
                "FETCH", message_id,
                "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT MESSAGE-ID)])")
            if typ != "OK":
                raise ImapError(f"FETCH failed for UID {message_id}")
            header_bytes, _ = _literals(data)
            headers = parse_header_block(header_bytes)
        finally:
            _quiet(conn.logout)
        subject = headers["Subject"]
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        _, to_addr = parseaddr(headers["From"])
        return self.send(to=to_addr or headers["From"], subject=subject, body=body,
                         in_reply_to=headers["Message-ID"])


# --- small utilities -----------------------------------------------------------------


def _literals(fetch_data: list) -> tuple[bytes, bytes]:
    """Pull byte literals out of an imaplib FETCH response.

    imaplib returns a mixed list of tuples (envelope, literal) and bare bytes;
    the literals are what carry header/body content. First literal = headers,
    second (if any) = the body peek.
    """
    literals = [part[1] for part in fetch_data
                if isinstance(part, tuple) and isinstance(part[1], bytes)]
    first = literals[0] if literals else b""
    second = literals[1] if len(literals) > 1 else b""
    return first, second


def _quiet(fn) -> None:
    try:
        fn()
    except Exception:
        pass
