"""Tests for the CalDAV provider — HTTP fully mocked, zero network."""

import pytest
import requests

from executive_assistant.caldav_client import CalDavCalendar, CalDavError

MULTISTATUS = """<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/dav/cal/1.ics</d:href>
    <d:propstat><d:prop>
      <c:calendar-data>BEGIN:VCALENDAR
BEGIN:VEVENT
UID:1@x
DTSTART:20260718T170000Z
DTEND:20260718T173000Z
SUMMARY:CalDAV standup
LOCATION:Clinic
END:VEVENT
END:VCALENDAR</c:calendar-data>
    </d:prop></d:propstat>
  </d:response>
</d:multistatus>"""


class FakeResponse:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    """Records requests; serves canned responses by method."""

    def __init__(self, report_text=MULTISTATUS, report_status=200):
        self.report_text, self.report_status = report_text, report_status
        self.calls = []
        self.auth = None
        self.headers = {}

    def request(self, method, url, data=None, headers=None, timeout=None):
        self.calls.append((method, url, data))
        return FakeResponse(self.report_text, self.report_status)

    def put(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("PUT", url, data))
        return FakeResponse("", 201)


def make_client(session):
    return CalDavCalendar("https://cloud.example.com/dav/calendars/me/personal/",
                          "me", "secret", _session=session)


class TestRead:
    def test_events_parsed_from_multistatus(self):
        session = FakeSession()
        events = make_client(session).events_today()
        assert len(events) == 1
        assert events[0].summary == "CalDAV standup"
        assert events[0].location == "Clinic"

    def test_report_sends_time_range_query(self):
        session = FakeSession()
        make_client(session).events_today()
        method, url, body = session.calls[0]
        assert method == "REPORT"
        assert url.endswith("/dav/calendars/me/personal/")
        assert b"time-range" in body

    def test_auth_set_on_session(self):
        session = FakeSession()
        make_client(session)
        assert session.auth == ("me", "secret")

    def test_http_error_raises_caldav_error(self):
        session = FakeSession(report_status=401)
        with pytest.raises(CalDavError, match="REPORT failed"):
            make_client(session).events_today()

    def test_malformed_xml_raises_caldav_error(self):
        session = FakeSession(report_text="<not xml")
        with pytest.raises(CalDavError, match="parse"):
            make_client(session).events_today()


class TestWrite:
    def test_create_event_puts_ics_resource(self):
        session = FakeSession()
        from datetime import datetime

        result = make_client(session).create_event(
            "New event", datetime(2026, 7, 20, 9, 0), datetime(2026, 7, 20, 9, 30))
        method, url, body = session.calls[0]
        assert method == "PUT" and url.endswith(".ics")
        assert b"SUMMARY:New event" in body
        assert result["status"] == "created"
