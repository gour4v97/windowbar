"""Tests for the parts of Winyard that do not need Windows or a display:
the iCal parser and recurrence expansion, weather codes, and folder stats.
Run:  pip install pytest && pytest -q
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extras import downloads_summary, fmt_dur
from services import occurrences, parse_ics, wmo_text

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20261110T100000
SUMMARY:Design review
END:VEVENT
BEGIN:VEVENT
DTSTART:20261102T090000
RRULE:FREQ=WEEKLY;BYDAY=MO
SUMMARY:Standup
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261105
SUMMARY:Holiday
END:VEVENT
END:VCALENDAR
"""


def test_parse_ics_keeps_timed_events_only():
    events = parse_ics(ICS)
    summaries = [e["summary"] for e in events]
    assert summaries == ["Design review", "Standup"]  # all-day dropped


def test_weekly_recurrence_expands():
    events = parse_ics(ICS)
    standup = next(e for e in events if e["summary"] == "Standup")
    now = datetime(2026, 11, 2, 0, 0)
    got = occurrences(standup, now, now + timedelta(days=14))
    assert got == [datetime(2026, 11, 2, 9, 0), datetime(2026, 11, 9, 9, 0)]


def test_wmo_text():
    assert wmo_text(0) == "Clear"
    assert wmo_text(61) == "Rain"
    assert wmo_text(95) == "Thunderstorm"


def test_downloads_summary(tmp_path):
    import os
    import time
    old = tmp_path / "old.txt"
    old.write_text("x")
    os.utime(old, (time.time() - 90000, time.time() - 90000))
    (tmp_path / "new.txt").write_text("x")
    recent, newest = downloads_summary(tmp_path)
    assert recent == 1
    assert newest == "new.txt"


def test_downloads_summary_missing_folder(tmp_path):
    assert downloads_summary(tmp_path / "nope") == (0, None)


def test_fmt_dur():
    assert fmt_dur(0) == "0m"
    assert fmt_dur(3660) == "1h 01m"
