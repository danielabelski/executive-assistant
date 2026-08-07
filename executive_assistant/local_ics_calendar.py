"""Local .ics calendar provider — a calendar that is just a FILE.

WHY THIS PROVIDER EXISTS
------------------------
Same philosophy as tasks.md: some users don't want another cloud account.
A calendar.ics in the project directory is a real calendar — readable by
this assistant, editable by hand, importable into almost any calendar app,
and version-controllable if you like. Zero accounts, zero OAuth, works
offline. It's also the provider used in examples and demos.

Events are parsed/serialized with ics_util (RFC 5545 subset). Writes append
a VEVENT to the file; existing content is never rewritten.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from executive_assistant.ics_util import (
    parse_vevents,
    serialize_event,
    vevent_to_event_dict,
)
from executive_assistant.types import Event, next_up


class LocalIcsCalendar:
    """Read/write a local iCalendar file. Interface matches CalendarClient."""

    def __init__(self, path: Path | str, timezone: str = "America/Los_Angeles"):
        self.path = Path(path)
        self.tz = ZoneInfo(timezone)

    # --- reads ---------------------------------------------------------------
    def _all_events(self) -> list[Event]:
        if not self.path.exists():
            return []
        return [Event(**vevent_to_event_dict(v)) for v in parse_vevents(self.path.read_text())]

    def events_today(self) -> list[Event]:
        now = datetime.now(self.tz)
        start = datetime.combine(now.date(), time.min).replace(tzinfo=self.tz)
        return self.events_between(start, start + timedelta(days=1))

    def next_event(self, now: datetime | None = None) -> tuple[Event, int] | None:
        """Next timed event today → (event, minutes_until); None if none left."""
        return next_up(self.events_today(), now or datetime.now(self.tz))

    def events_between(self, start: datetime, end: datetime) -> list[Event]:
        """Events overlapping [start, end). Naive file times are compared as
        naive; aware times as aware — we normalize to the query's awareness."""
        results = []
        for ev in self._all_events():
            ev_start, ev_end = ev.start, ev.end
            q_start, q_end = start, end
            if ev_start.tzinfo is None and q_start.tzinfo is not None:
                q_start, q_end = q_start.replace(tzinfo=None), q_end.replace(tzinfo=None)
            elif ev_start.tzinfo is not None and q_start.tzinfo is None:
                q_start, q_end = q_start.replace(tzinfo=ev_start.tzinfo), q_end.replace(tzinfo=ev_start.tzinfo)
            if ev_start < q_end and ev_end > q_start:
                results.append(ev)
        return sorted(results, key=lambda e: e.start)

    # --- writes ----------------------------------------------------------------
    def create_event(self, summary: str, start: datetime, end: datetime,
                     location: str = "", description: str = "") -> dict:
        """Append one VEVENT. (As always, ApprovalGate checked first upstream.)
        `description` is accepted for interface parity; not stored (scope)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
                "PRODID:-//executive-assistant//EN\r\nEND:VCALENDAR\r\n"
            )
        new_cal = serialize_event(summary, start, end, location=location)
        # Splice the new VEVENT in before END:VCALENDAR.
        vevent_body = new_cal[new_cal.index("BEGIN:VEVENT"): new_cal.index("END:VEVENT") + len("END:VEVENT")]
        text = self.path.read_text()
        text = text.replace("END:VCALENDAR", vevent_body + "\r\nEND:VCALENDAR")
        self.path.write_text(text)
        return {"status": "created", "id": f"local:{summary}", "link": str(self.path)}
