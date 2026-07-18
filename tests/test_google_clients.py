"""Tests for Gmail + Calendar clients — Google services are mocked.

No OAuth, no network: we inject fake `service` objects that mimic the
googleapiclient request-builder chain (.users().messages().list().execute()).
"""

import base64

from executive_assistant.calendar_client import CalendarClient
from executive_assistant.gmail_client import GmailClient, _b64decode, _encode_message


# --- fake googleapiclient service machinery -------------------------------------


class FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class FakeMessages:
    def __init__(self, list_payload, get_payloads):
        self._list = list_payload
        self._gets = get_payloads  # id → payload

    def list(self, userId, q, maxResults):
        self.last_query = q
        return FakeRequest(self._list)

    def get(self, userId, id, format, metadataHeaders=None):
        return FakeRequest(self._gets[id])


class FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


def gmail_service(list_payload, get_payloads):
    # NOTE: build the FakeMessages ONCE — every users() call must return the
    # same instance so recorded state (last_query) is visible to the test.
    messages = FakeMessages(list_payload, get_payloads)

    class FakeService:
        def users(self):
            return FakeUsers(messages)

    return FakeService()


METADATA_MSG = {
    "id": "abc123",
    "threadId": "t1",
    "snippet": "Can we move our meeting?",
    "payload": {"headers": [
        {"name": "From", "value": "Client Person <client@y.com>"},
        {"name": "Subject", "value": "Schedule change"},
        {"name": "Date", "value": "Fri, 17 Jul 2026 18:00:00 -0700"},
    ]},
}


class TestGmailSearch:
    def test_summaries_parsed_and_importance_flagged(self):
        svc = gmail_service({"messages": [{"id": "abc123"}]}, {"abc123": METADATA_MSG})
        client = GmailClient(svc, important_senders=["client@y.com"])
        results = client.search("is:unread")
        assert len(results) == 1
        r = results[0]
        assert r.sender.startswith("Client Person")
        assert r.subject == "Schedule change"
        assert r.is_important_sender is True

    def test_briefing_query_excludes_noisy_categories(self):
        svc = gmail_service({"messages": []}, {})
        client = GmailClient(svc)
        client.unread_for_briefing()
        q = svc.users()._messages.last_query
        assert "is:unread" in q and "-category:promotions" in q


class TestEncoding:
    def test_encode_decode_roundtrip(self):
        raw = _encode_message("a@b.com", "Hello", "Body text")
        decoded = base64.urlsafe_b64decode(raw.encode()).decode()
        # Headers appear verbatim; the utf-8 body is base64'd by MIMEText, so
        # we assert on the headers + that the payload is non-trivial.
        assert "a@b.com" in decoded and "Hello" in decoded
        assert len(decoded) > 40

    def test_b64decode_helper(self):
        assert _b64decode(base64.urlsafe_b64encode(b"hi").decode()) == "hi"


# --- calendar ---------------------------------------------------------------------


class FakeEvents:
    def __init__(self, items):
        self._items = items

    def list(self, calendarId, timeMin, timeMax, singleEvents, orderBy):
        return FakeRequest({"items": self._items})


def calendar_service(items):
    class FakeService:
        def events(self):
            return FakeEvents(items)

    return FakeService()


class TestCalendarParsing:
    def test_timed_and_all_day_events(self):
        svc = calendar_service([
            {"summary": "Standup",
             "start": {"dateTime": "2026-07-18T10:00:00-07:00"},
             "end": {"dateTime": "2026-07-18T10:30:00-07:00"},
             "location": "Clinic"},
            {"summary": "Conference",
             "start": {"date": "2026-07-18"},
             "end": {"date": "2026-07-19"}},
        ])
        client = CalendarClient(svc, timezone="America/Los_Angeles")
        now = __import__("datetime").datetime
        from datetime import datetime as dt
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Los_Angeles")
        events = client.events_between(dt(2026, 7, 18, 0, 0, tzinfo=tz),
                                       dt(2026, 7, 19, 0, 0, tzinfo=tz))
        timed, allday = events
        assert timed.render(client.tz).startswith("10:00–10:30  Standup (Clinic)")
        assert allday.all_day and "All day" in allday.render(client.tz)
