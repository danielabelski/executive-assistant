"""Tests for the IMAP+SMTP email provider — sockets fully faked."""

import pytest

from executive_assistant.imap_client import (
    ImapEmailClient,
    ImapError,
    _literals,
    decode_rfc2047,
    extract_text_body,
    parse_header_block,
)

HEADERS_RAW = (b"From: Client Person <client@y.com>\r\n"
               b"Subject: =?UTF-8?B?U2NoZWR1bGUgY2hhbmdl?=\r\n"  # "Schedule change"
               b"Date: Fri, 17 Jul 2026 18:00:00 -0700\r\n\r\n")

BODY_RAW = (b"From: Client Person <client@y.com>\r\nSubject: Hi\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            b"Hello Walker, can we move our meeting to 3pm?\r\n")


class FakeIMAP:
    """Mimics the imaplib surface the client uses."""

    def __init__(self, uids=(b"101", b"102"), fetch_map=None, login_error=None):
        self._uids = uids
        self._fetch_map = fetch_map or {}
        self._login_error = login_error
        self.appended = []
        self.logged_out = False

    def login(self, user, password):
        if self._login_error:
            import imaplib
            raise imaplib.IMAP4.error(self._login_error)

    def select(self, mailbox, readonly=False):
        return ("OK", [b"2"])

    def uid(self, command, *args):
        if command == "SEARCH":
            return ("OK", [b" ".join(u if isinstance(u, bytes) else u.encode()
                                     for u in self._uids)])
        if command == "FETCH":
            uid = args[0]
            uid = uid.decode() if isinstance(uid, bytes) else uid
            return ("OK", self._fetch_map.get(uid, []))
        return ("NO", [])

    def append(self, mailbox, flags, date_time, message):
        self.appended.append((mailbox, flags, message))
        return ("OK", [])

    def logout(self):
        self.logged_out = True


def client_for(fake):
    return ImapEmailClient("imap.example.com", "me@example.com", "pw",
                           smtp_host="smtp.example.com", _connector=lambda: fake)


def fetch_payload(*literals):
    """Shape imaplib FETCH returns: tuples of (envelope, literal) + closer."""
    return [(f"1 (UID 101 BODY[] {{{len(lit)}}}".encode(), lit) for lit in literals] + [b")"]


class TestUnread:
    def test_summaries_parsed(self):
        fake = FakeIMAP(fetch_map={"101": fetch_payload(HEADERS_RAW, b"Can we move it?"),
                                   "102": fetch_payload(HEADERS_RAW, b"")})
        unread = client_for(fake).unread_for_briefing(max_results=5)
        assert len(unread) == 2
        assert unread[0].id == "102"              # newest first
        assert unread[0].subject == "Schedule change"  # RFC 2047 decoded
        assert unread[1].snippet.startswith("Can we move")

    def test_important_sender_flagged(self):
        fake = FakeIMAP(uids=(b"101",), fetch_map={"101": fetch_payload(HEADERS_RAW, b"")})
        client = client_for(fake)
        client._important = {"client@y.com"}
        assert client.unread_for_briefing()[0].is_important_sender

    def test_login_failure_raises_imap_error(self):
        fake = FakeIMAP(login_error="bad credentials")
        with pytest.raises(ImapError, match="login failed"):
            client_for(fake).unread_for_briefing()

    def test_logout_always_called(self):
        fake = FakeIMAP(uids=(b"101",), fetch_map={"101": fetch_payload(HEADERS_RAW, b"")})
        client_for(fake).unread_for_briefing()
        assert fake.logged_out


class TestBody:
    def test_get_body_prefers_text_plain(self):
        fake = FakeIMAP(fetch_map={"101": fetch_payload(BODY_RAW)})
        fake._uids = (b"101",)
        body = client_for(fake).get_body("101")
        assert "move our meeting to 3pm" in body


class TestDrafts:
    def test_create_draft_appends_with_draft_flag(self):
        fake = FakeIMAP()
        result = client_for(fake).create_draft("a@b.com", "Hello", "Body")
        mailbox, flags, message = fake.appended[0]
        assert mailbox == "Drafts" and flags == "\\Draft"
        assert b"Hello" in message
        assert result["status"] == "draft_created"

    def test_drafts_folder_with_spaces_is_quoted(self):
        fake = FakeIMAP()
        client = client_for(fake)
        client.drafts_folder = "[Gmail] Drafts"
        client.create_draft("a@b.com", "s", "b")
        assert fake.appended[0][0] == '"[Gmail] Drafts"'


class TestHelpers:
    def test_decode_rfc2047(self):
        assert decode_rfc2047("=?UTF-8?B?U2NoZWR1bGUgY2hhbmdl?=") == "Schedule change"
        assert decode_rfc2047("plain") == "plain"
        assert decode_rfc2047("") == ""

    def test_parse_header_block(self):
        headers = parse_header_block(HEADERS_RAW)
        assert headers["From"].startswith("Client Person")
        assert headers["Subject"] == "Schedule change"

    def test_extract_text_body(self):
        assert "3pm" in extract_text_body(BODY_RAW)

    def test_literals_extraction(self):
        first, second = _literals(fetch_payload(b"one", b"two"))
        assert (first, second) == (b"one", b"two")


# --- #39-45: unread_count / search / vip_flag / draft_exists -----------------------

DRAFT_HEADERS = (b"From: me@example.com\r\n"
                 b"Subject: Re: Follow up with supplier\r\n"
                 b"Date: Fri, 17 Jul 2026 18:00:00 -0700\r\n\r\n")


class TestUnreadCount:
    def test_counts_unseen_uids(self):
        fake = FakeIMAP(uids=(b"101", b"102", b"103"))
        assert client_for(fake).unread_count() == 3

    def test_empty_inbox_is_zero(self):
        fake = FakeIMAP(uids=())
        assert client_for(fake).unread_count() == 0

    def test_logout_always_called(self):
        fake = FakeIMAP(uids=(b"101",))
        client_for(fake).unread_count()
        assert fake.logged_out


class TestSearch:
    def test_returns_summaries_newest_first(self):
        fake = FakeIMAP(fetch_map={"101": fetch_payload(HEADERS_RAW, b"a"),
                                   "102": fetch_payload(HEADERS_RAW, b"b")})
        results = client_for(fake).search("meeting", limit=5)
        assert [r.id for r in results] == ["102", "101"]
        assert results[0].subject == "Schedule change"  # same shape as unread

    def test_limit_truncates(self):
        fake = FakeIMAP(uids=(b"101", b"102", b"103"),
                        fetch_map={u: fetch_payload(HEADERS_RAW, b"")
                                   for u in ("101", "102", "103")})
        results = client_for(fake).search("meeting", limit=2)
        assert [r.id for r in results] == ["103", "102"]


class TestVipFlag:
    def test_flags_vip_senders_case_insensitive(self):
        fake = FakeIMAP(uids=(b"101",), fetch_map={"101": fetch_payload(HEADERS_RAW, b"")})
        client = client_for(fake)
        messages = client.unread_for_briefing()
        result = client.vip_flag(messages, ["CLIENT@Y.com"])
        assert result is messages
        assert messages[0].vip is True

    def test_non_vip_untouched(self):
        fake = FakeIMAP(uids=(b"101",), fetch_map={"101": fetch_payload(HEADERS_RAW, b"")})
        client = client_for(fake)
        messages = client.vip_flag(client.unread_for_briefing(), ["boss@z.com"])
        assert not hasattr(messages[0], "vip")


class TestDraftExists:
    def test_subject_substring_case_insensitive(self):
        fake = FakeIMAP(uids=(b"201",), fetch_map={"201": fetch_payload(DRAFT_HEADERS)})
        client = client_for(fake)
        assert client.draft_exists("follow up") is True
        assert client.draft_exists("SUPPLIER") is True
        assert client.draft_exists("different topic") is False

    def test_empty_drafts_folder(self):
        fake = FakeIMAP(uids=())
        assert client_for(fake).draft_exists("anything") is False
