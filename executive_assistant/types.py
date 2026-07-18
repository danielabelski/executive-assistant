"""Shared data types used by every provider module.

WHY THIS MODULE EXISTS
----------------------
Once we support multiple email/calendar providers (Gmail, IMAP, Google
Calendar, CalDAV, local .ics), they all need to speak the SAME data shapes
so briefing.py doesn't care which provider produced the data. These two
dataclasses are that common language.

Providers convert their native payloads into these types at the boundary;
everything downstream (briefings, approval, rendering) is provider-blind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass
class Event:
    """One calendar event, provider-agnostic.

    `start`/`end` may be timezone-aware (Google, CalDAV with Z times) or
    naive (local .ics files) — render() handles both.
    """

    summary: str
    start: datetime
    end: datetime
    location: str = ""
    all_day: bool = False

    def render(self, tz: ZoneInfo) -> str:
        """'10:00–10:30  Team standup (Clinic)' or 'All day  Conference'."""
        if self.all_day:
            return f"All day      {self.summary}"
        start = self.start.astimezone(tz) if self.start.tzinfo else self.start
        end = self.end.astimezone(tz) if self.end.tzinfo else self.end
        loc = f" ({self.location})" if self.location else ""
        return f"{start:%H:%M}–{end:%H:%M}  {self.summary}{loc}"


@dataclass
class EmailSummary:
    """The lightweight email view used in briefings.

    `id` is provider-specific (Gmail message id, IMAP UID) but always a
    string; `thread_id` may be empty on providers that don't thread.
    """

    id: str
    thread_id: str
    sender: str
    subject: str
    date: str
    snippet: str
    is_important_sender: bool = False
