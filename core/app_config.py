"""Windows Bar user paths, defaults, and configuration helpers."""
import os
import sys
from datetime import datetime
from pathlib import Path
from core import config as config_store
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Windows Bar"
CONFIG = APP_DIR / "config.json"
SCREEN_TIME_FILE = APP_DIR / "screentime.json"
THEMES_DIR = APP_DIR / "themes"
CUSTOM_QSS = APP_DIR / "custom.qss"
DEFAULTS = {
    "position": "bottom",
    "reserve_space": True,
    "hide_taskbar": False,
    "glass": True,
    "pause_before_meeting": False,
    "full_width": False,
    "auto_hide": False,
    "auto_hide_delay": 5,
    "quiet_hours": "",
    "weather_city": "",
    "calendar_url": "",
    "github_user": "",
    "notes": "",
    "widgets": {
        "apps": True, "clock": True, "weather": True, "system": True,
        "battery": True, "media": True, "calendar": True, "quick": True,
        "pomodoro": True, "todos": True,
        "stopwatch": False, "downloads": False, "notes": False,
        "screentime": False, "github": False, "revenue": False,
        "recycle": False, "windows": False, "shots": False,
        "storage": False, "world": False, "progress": False,
        "timer": False, "script": False, "network": False,
        "volume": False, "toggles": False,
    },
    "todos": [],
    "apps": {"Notepad": "notepad.exe", "Calc": "calc.exe",
             "Explorer": "explorer.exe"},
    "pomodoro_minutes": 25,
    "timer_minutes": 5,
    "clock_style": "digital",
    "world_zones": ["America/New_York", "Europe/London", "Asia/Kolkata"],
    "script_command": "",
    "script_interval": 60,
    "script_click_command": "",
    "notes_list": [],
    "notes_current": 0,
    "keep_awake": False,
    "theme": "midnight",
    "dynamic_accent": True,
    "launcher": True,
    "launcher_hotkey": "alt+space",
}

WIDGET_LABELS = {
    "apps": "App launcher", "clock": "Clock", "weather": "Weather",
    "system": "CPU / RAM", "battery": "Battery", "media": "Now playing",
    "calendar": "Next event", "quick": "Quick actions", "pomodoro": "Focus timer",
    "todos": "Todos", "stopwatch": "Stopwatch", "downloads": "Downloads",
    "notes": "Notes", "screentime": "Screen time", "github": "GitHub",
    "revenue": "Stripe revenue", "recycle": "Recycle Bin",
    "windows": "Open windows", "shots": "Screenshots",
    "storage": "Storage", "world": "World clocks",
    "progress": "Day / year progress", "timer": "Timer",
    "script": "Script output", "network": "Network", "volume": "Volume",
    "toggles": "Quick toggles",
}


def load_config():
    return config_store.load(CONFIG, DEFAULTS)


def save_config(cfg):
    config_store.save(CONFIG, cfg)


def in_quiet_hours(spec, now=None):
    """spec is "23:00-07:00" (may wrap midnight). Empty/invalid -> False."""
    try:
        start_s, end_s = spec.split("-", 1)
        sh, sm = (int(x) for x in start_s.strip().split(":"))
        eh, em = (int(x) for x in end_s.strip().split(":"))
    except Exception:
        return False
    now = now or datetime.now()
    cur = now.hour * 60 + now.minute
    start, end = sh * 60 + sm, eh * 60 + em
    return start <= cur < end if start < end else cur >= start or cur < end


def autostart_command():
    exe = Path(sys.executable)
    pw = exe.with_name("pythonw.exe")
    if pw.exists():
        exe = pw
    return f'"{exe}" "{Path(sys.argv[0]).resolve()}"' 

# ----------------------------------------------------------------- cards ----
PRESETS = {
    "Essentials": ["apps", "clock", "weather", "system", "battery",
                   "media", "calendar", "quick"],
    "Focus": ["clock", "calendar", "pomodoro", "timer", "todos", "notes",
              "progress"],
    "Creator": ["apps", "clock", "weather", "media", "github", "revenue",
                "downloads", "shots", "screentime", "quick"],
    "Everything": list(DEFAULTS["widgets"]),
}

MARGIN = 8


# ------------------------------------------------------------------ dock ----
