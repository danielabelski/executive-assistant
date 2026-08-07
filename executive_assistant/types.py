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

    @property
    def is_all_day(self) -> bool:
        """Canonical all-day flag (aliases the `all_day` field)."""
        return self.all_day

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


# --- shared email helpers --------------------------------------------------------


def flag_vips(messages: list, vip_senders: list[str]) -> list:
    """Set 'vip': True on messages whose sender contains any VIP entry.

    Case-insensitive substring match, so 'boss@x.com' matches
    'The Boss <boss@x.com>'. Works on EmailSummary objects (sets the
    attribute) and plain dicts (sets the key); returns the SAME list.
    """
    needles = [v.lower() for v in vip_senders]
    for msg in messages:
        sender = msg.sender if hasattr(msg, "sender") else msg.get("sender", "")
        if any(n in sender.lower() for n in needles):
            if isinstance(msg, dict):
                msg["vip"] = True
            else:
                msg.vip = True
    return messages


# --- shared calendar helpers -------------------------------------------------------


def _align(a: datetime, b: datetime) -> tuple[datetime, datetime]:
    """Make two datetimes comparable when one is naive and the other aware.

    The naive one is assumed to be in the aware one's timezone (mirrors the
    normalization events_between() does in the local .ics provider).
    """
    if a.tzinfo is None and b.tzinfo is not None:
        return a.replace(tzinfo=b.tzinfo), b
    if a.tzinfo is not None and b.tzinfo is None:
        return a, b.replace(tzinfo=a.tzinfo)
    return a, b


def conflicts(events: list[Event]) -> list[tuple[Event, Event]]:
    """All pairs of events that overlap in time.

    Rules: same calendar day only, a.start < b.end and b.start < a.end
    (touching endpoints do NOT conflict), and all-day events never conflict
    (they're markers, not time blocks).
    """
    timed = [e for e in events if not e.is_all_day]
    pairs: list[tuple[Event, Event]] = []
    for i, a in enumerate(timed):
        for b in timed[i + 1:]:
            if a.start.date() != b.start.date():
                continue
            a_start, b_start = _align(a.start, b.start)
            a_end, b_end = _align(a.end, b.end)
            if a_start < b_end and b_start < a_end:
                pairs.append((a, b))
    return pairs


def next_up(events: list[Event], now: datetime) -> tuple[Event, int] | None:
    """The next TIMED event starting later today, and minutes until it starts.

    Shared by every calendar provider's next_event(). All-day events are
    skipped (they have no meaningful start time); returns None when nothing
    is left today.
    """
    best: tuple[Event, int] | None = None
    best_start: datetime | None = None
    for ev in events:
        if ev.is_all_day:
            continue
        start, now_aligned = _align(ev.start, now)
        if start <= now_aligned or start.date() != now_aligned.date():
            continue
        if best_start is None or start < best_start:
            minutes = int((start - now_aligned).total_seconds() // 60)
            best, best_start = (ev, minutes), start
    return best
