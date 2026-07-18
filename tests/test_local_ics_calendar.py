"""Tests for the local .ics calendar provider."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from executive_assistant.local_ics_calendar import LocalIcsCalendar

TZ = "America/Los_Angeles"


class TestReads:
    def test_missing_file_means_no_events(self, tmp_path):
        cal = LocalIcsCalendar(tmp_path / "nope.ics", TZ)
        assert cal.events_today() == []

    def test_events_between_filters_window(self, tmp_path):
        p = tmp_path / "cal.ics"
        p.write_text(
            "BEGIN:VCALENDAR\r\n"
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260718T170000Z\r\n"
            "DTEND:20260718T173000Z\r\nSUMMARY:In window\r\nEND:VEVENT\r\n"
            "BEGIN:VEVENT\r\nUID:2\r\nDTSTART:20260725T170000Z\r\n"
            "DTEND:20260725T173000Z\r\nSUMMARY:Outside window\r\nEND:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        cal = LocalIcsCalendar(p, TZ)
        tz = ZoneInfo(TZ)
        events = cal.events_between(datetime(2026, 7, 18, 0, 0, tzinfo=tz),
                                    datetime(2026, 7, 19, 0, 0, tzinfo=tz))
        assert [e.summary for e in events] == ["In window"]

    def test_render_uses_local_timezone(self, tmp_path):
        p = tmp_path / "cal.ics"
        p.write_text(
            "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:1\r\n"
            "DTSTART:20260718T170000Z\r\nDTEND:20260718T173000Z\r\n"
            "SUMMARY:Standup\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        cal = LocalIcsCalendar(p, TZ)
        tz = ZoneInfo(TZ)
        events = cal.events_between(datetime(2026, 7, 18, 0, 0, tzinfo=tz),
                                    datetime(2026, 7, 19, 0, 0, tzinfo=tz))
        # 17:00 UTC = 10:00 PDT
        assert events[0].render(cal.tz).startswith("10:00–10:30  Standup")


class TestWrites:
    def test_create_event_appends_and_reads_back(self, tmp_path):
        p = tmp_path / "cal.ics"
        cal = LocalIcsCalendar(p, TZ)
        tz = ZoneInfo(TZ)
        start = datetime.now(tz).replace(microsecond=0) + timedelta(hours=1)
        result = cal.create_event("Review labs", start, start + timedelta(minutes=30),
                                  location="Office")
        assert result["status"] == "created"
        # Readable on next load — the file is the database.
        cal2 = LocalIcsCalendar(p, TZ)
        summaries = [e.summary for e in cal2.events_today()]
        assert "Review labs" in summaries

    def test_create_initializes_missing_file(self, tmp_path):
        p = tmp_path / "new" / "cal.ics"
        LocalIcsCalendar(p, TZ).create_event(
            "First", datetime(2026, 7, 20, 9, 0), datetime(2026, 7, 20, 9, 30))
        assert "BEGIN:VCALENDAR" in p.read_text()
