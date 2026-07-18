"""CalDAV calendar provider — Nextcloud, Fastmail, iCloud, Radicale, Baikal…

WHY STDLIB + requests (not the `caldav` package)
-------------------------------------------------
The feature set here is deliberately small: list events in a window, create
an event. That maps onto exactly two WebDAV operations (REPORT + PUT), so we
speak CalDAV directly with `requests` and `xml.etree` — no lxml/vobject
dependency chain to build on ARM64. VEVENT payloads are parsed by our own
tested ics_util.

CONFIG NOTE
-----------
`url` must be the CALENDAR COLLECTION URL (the …/personal/ folder that
contains the .ics resources), e.g.
    Nextcloud: https://cloud.example.com/remote.php/dav/calendars/you/personal/
    Fastmail:  https://caldav.fastmail.com/dav/calendars/user/you@fastmail.com/<id>/
    iCloud:    https://caldav.icloud.com/  (collection discovery varies)
Basic-auth username + app password (in secrets.yaml) — every major server
supports it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from defusedxml import ElementTree as ET  # safe against XXE/billion-laughs:
                                          # this XML arrives from a remote server

from executive_assistant.ics_util import parse_vevents, serialize_event, vevent_to_event_dict
from executive_assistant.types import Event

TIMEOUT = 20

# Namespaces we speak. ElementTree supports {*} wildcards when matching.
NS_D = "DAV:"
NS_C = "urn:ietf:params:xml:ns:caldav"


class CalDavError(Exception):
    """Raised on connection/auth/parse failures; briefing shows a fallback."""


class CalDavCalendar:
    """Interface-compatible with CalendarClient, backed by a CalDAV server."""

    def __init__(self, url: str, username: str, password: str,
                 timezone: str = "America/Los_Angeles", _session=None):
        self.url = url.rstrip("/") + "/"
        self.tz = ZoneInfo(timezone)
        self._session = _session or requests.Session()
        self._session.auth = (username, password)
        self._session.headers.update({"Content-Type": "application/xml; charset=utf-8"})

    # --- WebDAV plumbing ---------------------------------------------------------
    def _report(self, body_xml: str) -> str:
        try:
            resp = self._session.request(
                "REPORT", self.url, data=body_xml.encode(),
                headers={"Depth": "1"}, timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            raise CalDavError(f"CalDAV REPORT failed: {exc}") from exc

    @staticmethod
    def _calendar_query(start: datetime, end: datetime) -> str:
        """RFC 4791 calendar-query with a VEVENT time-range filter (UTC)."""
        def utc(dt: datetime) -> str:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return f"{dt.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"

        return (
            f'<c:calendar-query xmlns:d="{NS_D}" xmlns:c="{NS_C}">'
            "<d:prop><d:getetag/><c:calendar-data/></d:prop>"
            '<c:filter><c:comp-filter name="VCALENDAR">'
            '<c:comp-filter name="VEVENT">'
            f'<c:time-range start="{utc(start)}" end="{utc(end)}"/>'
            "</c:comp-filter></c:comp-filter></c:filter></c:calendar-query>"
        )

    # --- public interface ------------------------------------------------------------
    def events_today(self) -> list[Event]:
        now = datetime.now(self.tz)
        start = datetime.combine(now.date(), time.min).replace(tzinfo=self.tz)
        return self.events_between(start, start + timedelta(days=1))

    def events_between(self, start: datetime, end: datetime) -> list[Event]:
        xml_text = self._report(self._calendar_query(start, end))
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise CalDavError(f"Could not parse multistatus response: {exc}") from exc
        events = []
        for cal_data in root.iter(f"{{{NS_C}}}calendar-data"):
            if cal_data.text:
                for vevent in parse_vevents(cal_data.text):
                    events.append(Event(**vevent_to_event_dict(vevent)))
        return sorted(events, key=lambda e: e.start)

    def create_event(self, summary: str, start: datetime, end: datetime,
                     location: str = "", description: str = "") -> dict:
        """PUT a new .ics resource. ApprovalGate checked this upstream."""
        uid = f"{uuid.uuid4()}@executive-assistant"
        ics = serialize_event(summary, start, end, location=location, uid=uid)
        try:
            resp = self._session.put(
                f"{self.url}{uid}.ics", data=ics.encode(),
                headers={"Content-Type": "text/calendar; charset=utf-8"}, timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CalDavError(f"CalDAV PUT failed: {exc}") from exc
        return {"status": "created", "id": uid, "link": f"{self.url}{uid}.ics"}
