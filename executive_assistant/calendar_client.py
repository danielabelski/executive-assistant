"""Google Calendar client — "what's on today?" and (gated) event creation.

Read access powers the morning briefing. Writes (create/delete) exist for
future assistant features but are ALWAYS routed through ApprovalGate first —
a wrong calendar event can invite other people, so it never happens silently.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from executive_assistant.google_auth import CALENDAR_SCOPES, load_credentials
from executive_assistant.types import Event, next_up


class CalendarClient:
    def __init__(self, service, timezone: str = "America/Los_Angeles"):
        self._svc = service  # injected for testability
        self.tz = ZoneInfo(timezone)

    @classmethod
    def from_config(cls, config) -> "CalendarClient":
        creds = load_credentials(config.token_path, CALENDAR_SCOPES)
        return cls(build("calendar", "v3", credentials=creds, cache_discovery=False),
                   timezone=config.timezone)

    def events_today(self) -> list[Event]:
        """All events between local midnight and midnight tonight."""
        now = datetime.now(self.tz)
        start = datetime.combine(now.date(), time.min, tzinfo=self.tz)
        end = start + timedelta(days=1)
        return self.events_between(start, end)

    def next_event(self, now: datetime | None = None) -> tuple[Event, int] | None:
        """Next timed event today → (event, minutes_until); None if none left."""
        return next_up(self.events_today(), now or datetime.now(self.tz))

    def events_between(self, start: datetime, end: datetime) -> list[Event]:
        resp = (
            self._svc.events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return [self._to_event(item) for item in resp.get("items", [])]

    def _to_event(self, item: dict) -> Event:
        # Google gives either 'dateTime' (timed) or 'date' (all-day).
        if "dateTime" in item.get("start", {}):
            return Event(
                summary=item.get("summary", "(untitled)"),
                start=datetime.fromisoformat(item["start"]["dateTime"]),
                end=datetime.fromisoformat(item["end"]["dateTime"]),
                location=item.get("location", ""),
            )
        return Event(
            summary=item.get("summary", "(untitled)"),
            start=datetime.fromisoformat(item["start"]["date"]).replace(tzinfo=self.tz),
            end=datetime.fromisoformat(item["end"]["date"]).replace(tzinfo=self.tz),
            location=item.get("location", ""),
            all_day=True,
        )

    def create_event(self, summary: str, start: datetime, end: datetime,
                     location: str = "", description: str = "") -> dict:
        """WRITE operation — call only after ApprovalGate.check_calendar_write()
        has been satisfied by the user."""
        body = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": str(self.tz)},
            "end": {"dateTime": end.isoformat(), "timeZone": str(self.tz)},
        }
        created = self._svc.events().insert(calendarId="primary", body=body).execute()
        return {"status": "created", "id": created["id"], "link": created.get("htmlLink", "")}
