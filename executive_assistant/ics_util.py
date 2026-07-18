"""Minimal iCalendar (RFC 5545) VEVENT parsing and serialization — stdlib only.

SCOPE (deliberately narrow)
---------------------------
Exactly what briefings and basic event creation need:
    SUMMARY, DTSTART, DTEND, LOCATION, UID, and all-day vs timed events.
Handled:
    * line unfolding (continuation lines start with space/tab, RFC 5545 §3.1)
    * DATE values (20260718)              → all-day events
    * DATE-TIME UTC (20260718T170000Z)    → timezone-aware datetimes
    * DATE-TIME local (20260718T100000)   → naive datetimes (documented:
      TZID parameters are ignored; local .ics files are assumed local time)
NOT handled (out of scope): RRULE recurrence, VALARM, ATTENDEE, escaping
beyond comma/semicolon/newline in SUMMARY+LOCATION.

Both the local-.ics provider and the CalDAV provider build on this module,
so the parsing logic is tested in exactly one place.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

# --- parsing ---------------------------------------------------------------------


def unfold_lines(text: str) -> list[str]:
    """RFC 5545 §3.1: a line beginning with space/tab continues the previous."""
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def parse_vevents(ics_text: str) -> list[dict[str, str]]:
    """Extract every VEVENT as a flat {PROPERTY: value} dict.

    Property parameters (e.g. DTSTART;TZID=...) are stripped — see scope note.
    """
    events: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in unfold_lines(ics_text):
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
        elif upper == "END:VEVENT" and current is not None:
            events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            prop = key.split(";", 1)[0].upper()  # drop ;TZID=... etc.
            current[prop] = _unescape(value.strip())
    return events


def parse_dt(value: str) -> tuple[datetime, bool]:
    """Parse a DTSTART/DTEND value → (datetime, is_all_day).

    DATE            20260718            → midnight, all_day=True
    DATE-TIME UTC   20260718T170000Z    → tz-aware UTC
    DATE-TIME local 20260718T100000     → naive
    """
    value = value.strip()
    if "T" not in value:  # DATE — all-day marker
        d = datetime.strptime(value, "%Y%m%d")
        return d, True
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc), False
    return datetime.strptime(value, "%Y%m%dT%H%M%S"), False


def vevent_to_event_dict(vevent: dict[str, str]) -> dict:
    """Normalize a raw VEVENT dict into the kwargs for types.Event.

    Kept separate from the Event dataclass so ics_util has no import cycle.
    Missing DTEND gets DTSTART (zero-duration / reminder-style events).
    """
    start, all_day = parse_dt(vevent.get("DTSTART", "19700101"))
    end, _ = parse_dt(vevent["DTEND"]) if "DTEND" in vevent else (start, all_day)
    return {
        "summary": vevent.get("SUMMARY", "(untitled)"),
        "start": start,
        "end": end,
        "location": vevent.get("LOCATION", ""),
        "all_day": all_day,
    }


# --- serialization -----------------------------------------------------------------


def format_dt(dt: datetime, all_day: bool = False) -> str:
    """Inverse of parse_dt. Aware datetimes are emitted in UTC with Z."""
    if all_day:
        return f"{dt:%Y%m%d}"
    if dt.tzinfo:
        return f"{dt.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}"
    return f"{dt:%Y%m%dT%H%M%S}"


def serialize_event(summary: str, start: datetime, end: datetime,
                    location: str = "", all_day: bool = False,
                    uid: str | None = None) -> str:
    """A complete VCALENDAR string containing one VEVENT (lines CRLF-folded)."""
    uid = uid or f"{uuid.uuid4()}@executive-assistant"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//executive-assistant//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
        f"DTSTART:{format_dt(start, all_day)}",
        f"DTEND:{format_dt(end, all_day)}",
        f"SUMMARY:{_escape(summary)}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def _fold(line: str, limit: int = 75) -> str:
    """RFC 5545 folding: continuation lines start with a single space."""
    if len(line) <= limit:
        return line
    parts = [line[:limit]]
    rest = line[limit:]
    while rest:
        parts.append(" " + rest[: limit - 1])
        rest = rest[limit - 1:]
    return "\r\n".join(parts)


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def _unescape(text: str) -> str:
    return (text.replace("\\n", "\n").replace("\\,", ",")
                .replace("\\;", ";").replace("\\\\", "\\"))
