"""Tests for the parts of Windows Bar that do not need Windows or a display:
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


# ---- theme engine / launcher helpers -------------------------------------
def test_parse_ics_drop_before_discards_old_one_offs():
    events = parse_ics(ICS, drop_before=datetime(2026, 11, 5))
    assert [e["summary"] for e in events] == ["Design review", "Standup"]
    events = parse_ics(ICS, drop_before=datetime(2026, 11, 20))
    assert [e["summary"] for e in events] == ["Standup"]   # recurring is kept


def test_parse_ics_unfolds_long_lines():
    folded = ("BEGIN:VEVENT\nDTSTART:20261110T100000\n"
              "SUMMARY:Very long\n  title\nEND:VEVENT\n")
    assert parse_ics(folded)[0]["summary"] == "Very long title"


def test_theme_resolve_and_fallback(tmp_path):
    import theme
    assert theme.resolve("rose")["accent"] == "#ff7aa8"
    (tmp_path / "mine.json").write_text('{"accent": "#112233", "radius": "x"}')
    t = theme.resolve("mine", tmp_path)
    assert t["accent"] == "#112233" and t["radius"] == 12   # bad value -> default
    assert theme.resolve("does-not-exist", tmp_path) == theme.resolve("midnight")
    assert "mine" in theme.list_themes(tmp_path)


def test_theme_accent_override_and_qss():
    import theme
    t = theme.resolve("midnight", accent="#ff0000")
    assert t["accent"] == "#ff0000"
    assert "rgba(255,0,0,70)" in theme.build_qss(t)
    assert theme.resolve("midnight", accent="nonsense")["accent"] == "#7aa2ff"


def test_dominant_accent():
    import theme
    reddish = [(220, 30, 30)] * 10 + [(128, 128, 128)] * 50
    acc = theme.to_rgba(theme.dominant_accent(reddish))
    assert acc[0] > acc[1] and acc[0] > acc[2]
    assert theme.dominant_accent([(100, 100, 100)] * 20) is None


def test_fuzzy_rank():
    import search
    entries = [("Google Chrome", "a", "app"), ("Calculator", "b", "app"),
               ("Notepad", "c", "app")]
    assert search.rank("chr", entries)[0][0] == "Google Chrome"
    assert search.rank("calc", entries)[0][0] == "Calculator"
    assert search.rank("zzz", entries) == []
    assert search.fuzzy_score("npd", "Notepad") is not None


def test_hotkey_and_calc():
    import search
    assert search.parse_hotkey("alt+space") == (1, 0x20)
    assert search.parse_hotkey("ctrl+shift+k") == (6, ord("K"))
    assert search.parse_hotkey("space") is None
    assert search.safe_calc("2*(3+4)**2") == "98"
    assert search.safe_calc("5") is None
    assert search.safe_calc("__import__('os')") is None
    assert search.safe_calc("9**9**9") is None
