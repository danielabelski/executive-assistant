"""Tests for ics_util — the RFC 5545 subset both file and CalDAV providers use."""

from datetime import datetime, timezone

from executive_assistant.ics_util import (
    format_dt,
    parse_dt,
    parse_vevents,
    serialize_event,
    unfold_lines,
    vevent_to_event_dict,
)

SAMPLE_ICS = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:one@example\r
DTSTART:20260718T170000Z\r
DTEND:20260718T173000Z\r
SUMMARY:Team standup\r
LOCATION:Clinic\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:two@example\r
DTSTART:20260719\r
SUMMARY:Conference day with a very long summary line that must be folded acr\r
 oss two physical lines per the RFC\r
END:VEVENT\r
END:VCALENDAR\r
"""


class TestUnfold:
    def test_continuation_lines_joined(self):
        assert unfold_lines("SUMMARY:long\r\n line") == ["SUMMARY:longline"]

    def test_lf_and_crlf_both_handled(self):
        assert unfold_lines("A:1\nB:2\r\nC:3") == ["A:1", "B:2", "C:3"]


class TestParseVevents:
    def test_two_events_extracted(self):
        events = parse_vevents(SAMPLE_ICS)
        assert len(events) == 2
        assert events[0]["SUMMARY"] == "Team standup"
        assert events[0]["LOCATION"] == "Clinic"

    def test_folded_summary_recovered(self):
        events = parse_vevents(SAMPLE_ICS)
        assert "folded across two physical lines" in events[1]["SUMMARY"]

    def test_parameters_stripped(self):
        events = parse_vevents("BEGIN:VEVENT\nDTSTART;TZID=America/LA:20260718T100000\nEND:VEVENT")
        assert events[0]["DTSTART"] == "20260718T100000"


class TestParseDt:
    def test_utc_datetime(self):
        dt, all_day = parse_dt("20260718T170000Z")
        assert dt.tzinfo == timezone.utc and not all_day

    def test_local_datetime_naive(self):
        dt, all_day = parse_dt("20260718T100000")
        assert dt.tzinfo is None and not all_day

    def test_date_marks_all_day(self):
        dt, all_day = parse_dt("20260718")
        assert all_day and (dt.month, dt.day) == (7, 18)

    def test_format_dt_inverts(self):
        aware = datetime(2026, 7, 18, 17, 0, tzinfo=timezone.utc)
        assert format_dt(aware) == "20260718T170000Z"
        assert format_dt(datetime(2026, 7, 18, 10, 0)) == "20260718T100000"


class TestSerializeRoundTrip:
    def test_serialized_event_parses_back(self):
        ics = serialize_event("Checkup, annual", datetime(2026, 7, 20, 9, 0),
                              datetime(2026, 7, 20, 9, 30), location="Room 2; north")
        events = parse_vevents(ics)
        assert len(events) == 1
        kwargs = vevent_to_event_dict(events[0])
        assert kwargs["summary"] == "Checkup, annual"      # comma survived escaping
        assert kwargs["location"] == "Room 2; north"        # semicolon survived
        assert kwargs["start"] == datetime(2026, 7, 20, 9, 0)

    def test_all_day_serialization(self):
        ics = serialize_event("Holiday", datetime(2026, 12, 25), datetime(2026, 12, 26),
                              all_day=True)
        kwargs = vevent_to_event_dict(parse_vevents(ics)[0])
        assert kwargs["all_day"] is True
