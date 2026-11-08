"""Tests for the parts of Windows Bar that do not need Windows or a display:
the iCal parser and recurrence expansion, weather codes, and folder stats.
Run:  pip install pytest && pytest -q
"""
import ast
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extras
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


# ------------------------------------------------------- newer widgets ----
def test_period_progress_bounds():
    from datetime import datetime
    p = extras.period_progress(datetime(2026, 6, 15, 12, 0))
    assert set(p) == {"day", "week", "year"}
    assert all(0.0 <= v <= 1.0 for v in p.values())
    assert abs(p["day"] - 0.5) < 0.01
    assert abs(extras.period_progress(
        datetime(2026, 1, 1, 0, 0))["year"]) < 0.01


def test_disk_summary_shape(tmp_path):
    pct, free, total = extras.disk_summary(str(tmp_path))
    assert 0 <= pct <= 100 and 0 <= free <= total


def test_run_script_echo_and_errors():
    import pytest
    assert extras.run_script("echo hello") == "hello"
    with pytest.raises(ValueError):
        extras.run_script("")
    with pytest.raises(ValueError):
        extras.run_script("exit 3")


def test_network_info_shape():
    name, ip = extras.network_info()
    assert isinstance(name, str) and isinstance(ip, str)


def test_normalize_todos_migrates_strings():
    out = extras.normalize_todos(["a", {"t": "b", "done": True}, {"x": 1}])
    assert out == [{"t": "a", "done": False}, {"t": "b", "done": True}]


def test_normalize_notes_migrates_legacy_text():
    notes, cur = extras.normalize_notes("old note", None)
    assert notes == ["old note"] and cur == 0
    notes, cur = extras.normalize_notes("", ["x", "y"], 9)
    assert notes == ["x", "y"] and cur == 1
    notes, cur = extras.normalize_notes("", [], 0)
    assert notes == [""]


def test_exe_of():
    # same logic as widgets.apps._exe_of, kept Qt-free for the test env
    src = Path(__file__).resolve().parents[1] / "widgets" / "apps.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_exe_of")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "_exe_of", "exec"),
         ns)
    exe_of = ns["_exe_of"]
    assert exe_of("notepad.exe") == "notepad.exe"
    assert exe_of(r'"C:\Apps\Visual Studio Code\Code.exe" .') == "code.exe"
    assert exe_of("") == ""


def test_config_v1_migrates_legacy_settings_and_keeps_defaults(tmp_path):
    import json
    from core.config import CURRENT_SCHEMA_VERSION, load

    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "position": "top",
        "widgets": {"weather": False},
    }), encoding="utf-8")
    defaults = {"position": "bottom", "theme": "midnight",
                "widgets": {"weather": True, "clock": True}}

    cfg = load(path, defaults)

    assert cfg["schema_version"] == CURRENT_SCHEMA_VERSION == 1
    assert cfg["position"] == "top"
    assert cfg["theme"] == "midnight"
    assert cfg["widgets"] == {"weather": False, "clock": True}
    assert "schema_version" not in json.loads(path.read_text(encoding="utf-8"))


def test_config_save_is_versioned_and_round_trips(tmp_path):
    import json
    from core.config import load, save

    path = tmp_path / "nested" / "config.json"
    save(path, {"position": "top", "widgets": {"clock": False}})
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["schema_version"] == 1
    assert not path.with_suffix(".json.tmp").exists()
    assert load(path, {"position": "bottom", "widgets": {"clock": True}}) == {
        "position": "top", "widgets": {"clock": False}, "schema_version": 1}


def test_widget_registry_starts_and_stops_enabled_widgets():
    from core.registry import WidgetDefinition, WidgetRegistry

    events = []

    class FakeWidget:
        id = "clock"
        name = "Clock"
        default_config = {"enabled": True}

        def start(self):
            events.append("start")

        def stop(self):
            events.append("stop")

        def card(self):
            return "clock-card"

        def popup(self):
            return None

        def on_click(self):
            pass

    registry = WidgetRegistry()
    registry.register(WidgetDefinition("clock", "Clock", True, FakeWidget))
    assert registry.start_enabled({"widgets": {}})["clock"].card() == "clock-card"
    registry.start_enabled({"widgets": {"clock": True}})
    assert events == ["start"]
    assert registry.start_enabled({"widgets": {"clock": False}}) == {}
    assert events == ["start", "stop"]


def test_first_widgets_are_in_separate_modules():
    from widgets.clock import ClockCard
    from widgets.notes import NotesCard
    from widgets.weather import WeatherCard

    assert (ClockCard.id, NotesCard.id, WeatherCard.id) == (
        "clock", "notes", "weather")


def test_screen_time_worker_starts_and_stops_with_widget(tmp_path):
    import threading
    from extras import ScreenTime

    sampled = threading.Event()

    def sampler():
        sampled.set()
        return "test-app.exe"

    tracker = ScreenTime(tmp_path / "screen-time.json", sampler=sampler,
                         idle=lambda: 0, start=False)
    assert tracker._thread is None
    tracker.start()
    assert sampled.wait(2)
    tracker.stop()
    assert tracker._thread is None
    assert tracker.today()[0] >= 1


def test_weather_and_calendar_workers_only_run_while_active():
    import time
    from services import CalendarService, WeatherService

    weather = WeatherService({"weather_city": ""}, lambda: None)
    calendar = CalendarService({"calendar_url": ""})
    assert weather._thread is None and calendar._thread is None

    weather.start()
    calendar.start()
    weather_thread, calendar_thread = weather._thread, calendar._thread
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and calendar.status != "Set link":
        time.sleep(0.01)
    assert weather.text == "Click to set city"
    assert calendar.status == "Set link"

    weather.stop()
    calendar.stop()
    weather_thread.join(timeout=1)
    calendar_thread.join(timeout=1)
    assert not weather_thread.is_alive()
    assert not calendar_thread.is_alive()


def test_detail_popup_position_respects_edge_and_screen_bounds():
    from PySide6.QtCore import QPoint, QRect, QSize
    from ui.popup import popup_position

    screen = QRect(0, 0, 800, 800)
    anchor = QRect(500, 500, 100, 30)
    size = QSize(200, 100)
    assert popup_position(anchor, size, screen, "top") == QPoint(449, 536)
    assert popup_position(anchor, size, screen, "bottom") == QPoint(449, 394)

    near_edge = QRect(760, 20, 50, 20)
    assert popup_position(near_edge, size, screen, "bottom") == QPoint(600, 0)


def test_logging_creates_rotating_log_in_app_logs(tmp_path):
    import logging
    import sys
    import threading
    from core.logging_setup import configure_logging

    logger = logging.getLogger("windowsbar")
    old_sys_hook, old_thread_hook = sys.excepthook, threading.excepthook
    log_path = configure_logging(tmp_path)
    try:
        logger.warning("test log entry")
        for handler in logger.handlers:
            handler.flush()
        assert log_path == tmp_path / "logs" / "windowsbar.log"
        assert "test log entry" in log_path.read_text(encoding="utf-8")
    finally:
        for handler in list(logger.handlers):
            if getattr(handler, "_windowsbar_file_handler", False):
                logger.removeHandler(handler)
                handler.close()
        sys.excepthook = old_sys_hook
        threading.excepthook = old_thread_hook


def test_taskbar_auto_hide_state_restores_after_restart(tmp_path, monkeypatch):
    import json
    from native import appbar
    import winapi

    calls = []

    def fake_appbar(message, data):
        if message == winapi.ABM_GETSTATE:
            return 0
        calls.append((message, data.lParam))
        return 1

    monkeypatch.setattr(appbar, "IS_WIN", True)
    monkeypatch.setattr(appbar, "_appbar", fake_appbar)
    config = {"hide_taskbar": True}
    winapi.set_taskbar_autohide(True, 123, config)
    assert config["_taskbar_original"] == 0

    saved = tmp_path / "config.json"
    saved.write_text(json.dumps(config), encoding="utf-8")
    recovered_config = json.loads(saved.read_text(encoding="utf-8"))
    calls.clear()  # the next process only performs restore
    winapi.restore_taskbar(recovered_config, 123)

    assert calls == [(winapi.ABM_SETSTATE, 0)]
    assert "_taskbar_original" not in recovered_config


def test_widget_modules_discover_every_configured_widget():
    import widgets
    from core.app_config import DEFAULTS, WIDGET_LABELS
    from core.registry import WidgetRegistry

    registry = WidgetRegistry()
    registry.register_package(widgets, object(), DEFAULTS["widgets"],
                              WIDGET_LABELS)

    assert set(registry.definitions) == set(DEFAULTS["widgets"])
    assert len(registry.definitions) == 28
    assert [d.name for d in registry.definitions.values()] == [
        WIDGET_LABELS[key] for key in (
            "apps", "clock", "world", "progress", "weather", "downloads",
            "shots", "windows", "system", "network", "storage", "battery",
            "media", "volume", "toggles", "calendar", "quick", "recycle",
            "screentime", "github", "revenue", "notes", "pomodoro", "timer",
            "stopwatch", "script", "todos", "temperature")]


def test_app_hotkey_modifier_flags_are_configurable():
    from ui.hotkeys import AppHotkeyFilter

    assert AppHotkeyFilter.modifier_flags("alt") == 0x0001
    assert AppHotkeyFilter.modifier_flags("ctrl+alt") == 0x0003
    assert AppHotkeyFilter.modifier_flags("win") == 0x0008
    assert AppHotkeyFilter.modifier_flags("unknown") == 0x0001


def test_temperature_reader_handles_supported_and_missing_sensors(monkeypatch):
    from types import SimpleNamespace
    import psutil
    from widgets.temperature import temperature_readings

    monkeypatch.setattr(psutil, "sensors_temperatures", lambda **_: {
        "CPU": [SimpleNamespace(current=57.5)]}, raising=False)
    assert temperature_readings() == [("CPU", 57.5)]

    def unavailable(**_kwargs):
        raise NotImplementedError
    monkeypatch.setattr(psutil, "sensors_temperatures", unavailable, raising=False)
    assert temperature_readings() == []


def test_widget_theme_overrides_are_validated_and_scoped():
    import theme

    base = theme.resolve("midnight")
    tokens = theme.widget_tokens(base, {
        "accent": "#ff0000",
        "card": [10, 20, 30, 180],
        "radius": 90,
        "text": "invalid",
        "panel": "#000000",
    })
    assert tokens["accent"] == "#ff0000"
    assert tokens["card"] == [10, 20, 30, 180]
    assert tokens["radius"] == 48
    assert tokens["text"] == base["text"]
    assert tokens["panel"] == base["panel"]
    assert "rgba(255,0,0,150)" in theme.build_widget_qss(tokens)


def test_builtin_theme_aliases_and_spacing_blur_tokens():
    import theme

    assert theme.resolve("default") == theme.resolve("midnight")
    assert theme.resolve("light") == theme.resolve("daylight")
    assert theme.resolve("dark") == theme.resolve("midnight")
    glass = theme.resolve("glass")
    assert glass["blur"] > 0 and glass["spacing"] == 12
    assert "padding: 12px" in theme.build_qss(glass)
    assert {"default", "glass", "light", "dark"}.issubset(
        theme.list_themes())
