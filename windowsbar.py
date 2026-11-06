"""
Windows Bar - a smart dock for Windows 10/11.

Run:   pip install -r requirements.txt
       python windowsbar.py

Right-click the dock for the menu. Settings live in %APPDATA%\\Windows Bar\\config.json
Stripe revenue reads the key from the WINDOWSBAR_STRIPE_KEY environment variable.
"""
import json
import math
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import QPropertyAnimation, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QFont,
                           QImageReader, QPainter, QPainterPath, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

import extras
import theme
import winapi
from launcher import HotkeyFilter, Launcher
from services import CalendarService, MediaService, WeatherService

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Windows Bar"
CONFIG = APP_DIR / "config.json"
SCREEN_TIME_FILE = APP_DIR / "screentime.json"
THEMES_DIR = APP_DIR / "themes"
CUSTOM_QSS = APP_DIR / "custom.qss"
_save_lock = threading.Lock()

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
    },
    "todos": [],
    "apps": {"Notepad": "notepad.exe", "Calc": "calc.exe",
             "Explorer": "explorer.exe"},
    "pomodoro_minutes": 25,
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
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        cfg.update({k: v for k, v in data.items() if k != "widgets"})
        cfg["widgets"].update(data.get("widgets", {}))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    with _save_lock:  # widgets save from background threads too
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            tmp = CONFIG.with_suffix(".tmp")
            tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            os.replace(tmp, CONFIG)
        except Exception:
            pass


def fmt_hms(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_speed(bps):
    for unit in ("B/s", "KB/s", "MB/s"):
        if bps < 1024:
            return f"{bps:.0f} {unit}"
        bps /= 1024
    return f"{bps:.1f} GB/s"


def fmt_delta(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "now"
    m = seconds // 60
    if m < 60:
        return f"in {m}m"
    h, m = divmod(m, 60)
    return f"in {h}h {m:02d}m" if h < 24 else f"in {h // 24}d"


def clip(text, n):
    return text if len(text) <= n else text[: n - 1] + "…"


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
    return f'"{exe}" "{Path(__file__).resolve()}"' 


# ----------------------------------------------------------------- cards ----
class Card(QFrame):
    """A titled card. INTERVAL is how many seconds between refreshes --
    slow sources (Recycle Bin, open windows) must not run every second.
    tick() returns True only when the displayed text actually changed,
    so the dock can skip relayout/repaint work on quiet seconds."""

    INTERVAL = 1
    ALWAYS = False   # True: keeps ticking while the dock is slid away
    STICKY = False   # True: never shrinks, so changing digits can't make the dock jitter

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        self._wmax = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(0)
        self.title = QLabel(title.upper())
        self.title.setObjectName("cardtitle")
        self.body = QLabel("")
        self.body.setObjectName("cardbody")
        lay.addWidget(self.title)
        lay.addWidget(self.body)

    def set_texts(self, title=None, body=None):
        changed = False
        if title is not None and title != self.title.text():
            self.title.setText(title)
            changed = True
        if body is not None and body != self.body.text():
            self.body.setText(body)
            changed = True
        if changed and self.STICKY:
            w = max(self.body.sizeHint().width(), self.title.sizeHint().width())
            if w > self._wmax:
                self._wmax = w
                self.setMinimumWidth(w + 24)
        return changed

    def tick(self):
        return False


class ClockCard(Card):
    STICKY = True

    def __init__(self):
        super().__init__("Time")

    def tick(self):
        return self.set_texts(time.strftime("%a %d %b").upper(),
                              time.strftime("%I:%M %p").lstrip("0"))


class WeatherCard(Card):
    INTERVAL = 5

    def __init__(self, weather, ask_city):
        super().__init__("Weather")
        self.weather, self.ask_city = weather, ask_city
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to change city")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.ask_city()

    def tick(self):
        return self.set_texts(self.weather.label, self.weather.text)


class SystemCard(Card):
    STICKY = True

    def __init__(self):
        super().__init__("CPU / RAM")
        self._last = psutil.net_io_counters()
        self._last_t = time.time()
        psutil.cpu_percent(None)

    def tick(self):
        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        now = psutil.net_io_counters()
        t = time.time()
        dt = max(t - self._last_t, 0.001)
        down = (now.bytes_recv - self._last.bytes_recv) / dt
        self._last, self._last_t = now, t
        return self.set_texts(
            body=f"{cpu:.0f}%  {ram:.0f}%  ↓{fmt_speed(down)}")


class BatteryCard(Card):
    INTERVAL = 5
    STICKY = True

    def __init__(self):
        super().__init__("Battery")

    def tick(self):
        b = psutil.sensors_battery()
        if b is None:
            return self.set_texts(body="No battery")
        return self.set_texts(
            body=f"{b.percent:.0f}% {'⚡' if b.power_plugged else ''}")


class MediaCard(Card):
    INTERVAL = 2

    def __init__(self, media):
        super().__init__("Now playing")
        self.media = media
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: play / pause")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.media.toggle()

    def tick(self):
        m = self.media
        if not m.available:
            return self.set_texts("NOW PLAYING", "Media support not installed")
        if not m.has_session:
            return self.set_texts("NOW PLAYING", "Nothing playing")
        text = m.title + (f" — {m.artist}" if m.artist else "")
        return self.set_texts("NOW PLAYING " + ("▶" if m.playing else "❚❚"),
                              clip(text, 28))


class CalendarCard(Card):
    INTERVAL = 5

    def __init__(self, calendar, ask_link):
        super().__init__("Next event")
        self.calendar, self.ask_link = calendar, ask_link
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to set your calendar's secret iCal link")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.ask_link()

    def tick(self):
        cal = self.calendar
        if cal.status:
            return self.set_texts("NEXT EVENT", cal.status)
        nxt = cal.next_event()
        if not nxt:
            return self.set_texts("NEXT EVENT", "Nothing soon")
        dt, title = nxt
        delta = fmt_delta((dt - datetime.now()).total_seconds())
        return self.set_texts("NEXT · " + delta.upper(), clip(title, 26))


class QuickCard(QFrame):
    """Lock, dark/light theme, and empty Recycle Bin."""

    INTERVAL = 10

    def __init__(self, parent_widget):
        super().__init__()
        self.setObjectName("card")
        self.parent_widget = parent_widget
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self.theme_btn = QPushButton()
        for text, fn in [("Lock", winapi.lock_screen),
                         ("Theme", self.toggle_theme),
                         ("Empty bin", self.empty_bin),
                         ("Open…", self.open_path)]:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            if text == "Theme":
                self.theme_btn = b
            b.clicked.connect(fn)
            lay.addWidget(b)
        self.tick()

    def toggle_theme(self):
        try:
            winapi.set_dark_mode(not winapi.is_dark_mode())
        except Exception:
            pass
        self.tick()

    def open_path(self):
        text, ok = QInputDialog.getText(
            self, "Open", "Folder or file path (e.g. D:\\work, %USERPROFILE%):")
        if ok and text.strip():
            try:
                os.startfile(os.path.expandvars(text.strip().strip('"')))
            except Exception:
                pass

    def empty_bin(self):
        if QMessageBox.question(self, "Empty Recycle Bin",
                                "Permanently delete everything in the Recycle Bin?"
                                ) == QMessageBox.Yes:
            winapi.empty_recycle_bin()

    def tick(self):
        try:
            dark = winapi.is_dark_mode()
            text = "Light" if dark else "Dark"
            if text != self.theme_btn.text():
                self.theme_btn.setText(text)
                return True
        except Exception:
            pass
        return False


class PomodoroCard(Card):
    ALWAYS = True
    STICKY = True

    def __init__(self, minutes, quiet=None):
        super().__init__("Focus")
        self.quiet = quiet or (lambda: False)
        self.minutes = minutes
        self.remaining = minutes * 60.0
        self.running = False
        self._t = time.monotonic()
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: start/pause   Double-click: reset")

    def _advance(self):
        now = time.monotonic()
        if self.running:
            self.remaining -= now - self._t
        self._t = now

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._advance()
            self.running = not self.running

    def mouseDoubleClickEvent(self, e):
        self.running = False
        self.remaining = self.minutes * 60.0

    def tick(self):
        self._advance()
        if self.running and self.remaining <= 0:
            self.running = False
            self.remaining = self.minutes * 60.0
            if not self.quiet():
                QApplication.beep()
        return self.set_texts(
            "FOCUS" + (" ▶" if self.running else " ❚❚"),
            fmt_hms(math.ceil(self.remaining)))


class StopwatchCard(Card):
    ALWAYS = True
    STICKY = True

    def __init__(self):
        super().__init__("Stopwatch")
        self.elapsed = 0.0
        self.running = False
        self._t = time.monotonic()
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: start/pause   Double-click: reset")

    def _advance(self):
        now = time.monotonic()
        if self.running:
            self.elapsed += now - self._t
        self._t = now

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._advance()
            self.running = not self.running

    def mouseDoubleClickEvent(self, e):
        self.running = False
        self.elapsed = 0.0

    def tick(self):
        self._advance()
        return self.set_texts(body=fmt_hms(int(self.elapsed)))


class TodoCard(Card):
    INTERVAL = 2

    def __init__(self, cfg):
        super().__init__("Todos")
        self.cfg = cfg
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: add todo   Right-click: complete first todo")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            text, ok = QInputDialog.getText(self, "New todo", "Todo:")
            if ok and text.strip():
                self.cfg["todos"].append(text.strip())
                save_config(self.cfg)
        elif e.button() == Qt.RightButton and self.cfg["todos"]:
            self.cfg["todos"].pop(0)
            save_config(self.cfg)

    def contextMenuEvent(self, e):
        e.accept()

    def tick(self):
        todos = self.cfg["todos"]
        return self.set_texts(f"TODOS ({len(todos)})",
                              clip(todos[0], 24) if todos else "All clear")


class NotesCard(Card):
    INTERVAL = 5

    def __init__(self, cfg):
        super().__init__("Notes")
        self.cfg = cfg
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to edit notes")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            text, ok = QInputDialog.getMultiLineText(
                self, "Notes", "Notes:", self.cfg["notes"])
            if ok:
                self.cfg["notes"] = text
                save_config(self.cfg)

    def tick(self):
        first = (self.cfg["notes"].strip().splitlines() or [""])[0]
        return self.set_texts(
            body=clip(first, 26) if first else "Click to write")


class ScreenTimeCard(Card):
    INTERVAL = 5

    def __init__(self, tracker):
        super().__init__("Screen time")
        self.tracker = tracker

    def tick(self):
        total, top = self.tracker.today()
        tip = "\n".join(f"{n}: {extras.fmt_dur(s)}" for n, s in top)
        if tip and tip != self.toolTip():
            self.setToolTip(tip)
        return self.set_texts(body=extras.fmt_dur(total) + " today")


class PollCard(Card):
    """Shows the value of a background Poll, or its error."""

    INTERVAL = 5

    def __init__(self, title, poll, on_click=None, hint=""):
        super().__init__(title)
        self.poll, self.on_click, self.hint = poll, on_click, hint
        if on_click:
            self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.on_click:
            self.on_click()

    def tick(self):
        if self.poll.value is not None:
            text = clip(str(self.poll.value), 30)
        elif self.poll.error:
            text = clip(self.poll.error, 30)
        else:
            text = "Loading…"
        return self.set_texts(body=text)


class DownloadsCard(Card):
    INTERVAL = 5

    def __init__(self, poll, name="Downloads", folder=None):
        super().__init__(name)
        self.poll = poll
        self.name = name
        self.folder = folder or (Path.home() / "Downloads")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Click to open {name}")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            os.startfile(str(self.folder))

    def tick(self):
        if self.poll.value is None:
            return self.set_texts(body=self.poll.error or "Loading…")
        recent, newest = self.poll.value
        return self.set_texts(f"{self.name.upper()} · {recent} TODAY",
                              clip(newest or "Empty", 26))


class WindowsCard(QFrame):
    """Buttons for the open windows (taskbar-style); click one to focus it.
    The window list is gathered by a background poll; the focused window is
    highlighted with the theme accent."""

    INTERVAL = 2

    def __init__(self, poll):
        super().__init__()
        self.setObjectName("card")
        self.poll = poll
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 6, 8, 6)
        self.lay.setSpacing(6)
        self._state = None

    def tick(self):
        wins = self.poll.value
        if wins is None:
            return False
        fg = winapi.foreground_hwnd()
        state = (tuple(wins), fg)
        if state == self._state:
            return False
        old_titles = [t for _, t in (self._state[0] if self._state else ())]
        self._state = state
        if old_titles == [t for _, t in wins] and self.lay.count() == len(wins):
            for i, (hwnd, _) in enumerate(wins):     # only the highlight moved
                b = self.lay.itemAt(i).widget()
                b.setProperty("active", "true" if hwnd == fg else "false")
                b.style().unpolish(b)
                b.style().polish(b)
            return False
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not wins:
            lab = QLabel("No open windows")
            lab.setObjectName("cardbody")
            self.lay.addWidget(lab)
            return True
        for hwnd, title in wins:
            b = QPushButton(clip(title, 16))
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(title)
            b.setProperty("active", "true" if hwnd == fg else "false")
            b.clicked.connect(lambda _=False, h=hwnd: winapi.focus_window(h))
            self.lay.addWidget(b)
        return True


class RecycleCard(Card):
    INTERVAL = 30

    def __init__(self, poll):
        super().__init__("Recycle Bin")
        self.poll = poll
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to empty the Recycle Bin")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            QuickCard.empty_bin(self)

    def tick(self):
        n = self.poll.value
        return self.set_texts(
            body="—" if n is None else f"{n} item{'s' if n != 1 else ''}")


class AppsCard(QFrame):
    def __init__(self, apps):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        for name, cmd in apps.items():
            b = QPushButton(name)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=cmd: self.launch(c))
            lay.addWidget(b)

    INTERVAL = 3600

    @staticmethod
    def launch(cmd):
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception:
            pass

    def tick(self):
        return False


MARGIN = 8


# ------------------------------------------------------------------ dock ----
class Dock(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        winapi.restore_taskbar(self.cfg)   # undo auto-hide left by a crash
        save_config(self.cfg)

        self.weather = WeatherService(self.cfg, lambda: save_config(self.cfg))
        self.calendar = CalendarService(self.cfg)
        self.media = MediaService()
        self.screen_time = extras.ScreenTime(SCREEN_TIME_FILE)
        self.polls = {}            # created on demand, stopped when the widget is off
        self._poll_makers = {
            "github": (lambda: extras.github_summary(self.cfg["github_user"]), 1800),
            "revenue": (lambda: extras.stripe_revenue(
                os.environ.get("WINDOWSBAR_STRIPE_KEY", "")), 1800),
            "downloads": (lambda: extras.downloads_summary(), 30),
            "shots": (lambda: extras.downloads_summary(
                Path.home() / "Pictures" / "Screenshots"), 30),
            "windows": (lambda: winapi.list_open_windows(
                6, exclude=[self.appbar.hwnd]), 2),
            "recycle": (winapi.recycle_count, 30),
        }
        self.appbar = winapi.AppBar()
        self.glass_active = False
        self._drag = None
        self._last_size = None
        self._fired = None
        self._tick_n = 0
        self._hidden = False
        self._shown_pos = None
        self._last_hover = time.monotonic()
        self._menu_open = False
        self._res_key = self._res_rc = None   # last AppBar reservation (skip no-ops)
        self._fs = (0.0, False)               # throttled fullscreen check
        self._bg = None                       # cached background pixmap
        self._wall_key = None
        self._accent_pending = None
        self.accent = self.cfg.get("_accent")
        self.tokens = theme.resolve(self.cfg["theme"], THEMES_DIR, None)
        self._animating = False
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(180)
        self._anim.finished.connect(self._anim_done)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.apply_theme()
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(14, 10, 14, 10)
        self.row.setSpacing(10)
        self.cards = []
        self.rebuild()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)

        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._autohide_check)
        self._sync_autohide_timer()

        self.launcher = Launcher(self.cfg, lambda: self.tokens)
        self.hotkey = HotkeyFilter(self.launcher.toggle)
        QApplication.instance().installNativeEventFilter(self.hotkey)
        self.sync_hotkey()

    # -- build ---------------------------------------------------------------
    def rebuild(self):
        for c in self.cards:
            self.row.removeWidget(c)
            c.deleteLater()
        self.cards = []
        w = self.cfg["widgets"]
        makers = [
            ("apps", lambda: AppsCard(self.cfg["apps"])),
            ("clock", ClockCard),
            ("weather", lambda: WeatherCard(self.weather, self.ask_city)),
            ("downloads", lambda: DownloadsCard(self.poll("downloads"))),
            ("shots", lambda: DownloadsCard(
                self.poll("shots"), "Screenshots",
                Path.home() / "Pictures" / "Screenshots")),
            ("windows", lambda: WindowsCard(self.poll("windows"))),
            ("system", SystemCard),
            ("battery", BatteryCard),
            ("media", lambda: MediaCard(self.media)),
            ("calendar", lambda: CalendarCard(self.calendar, self.ask_calendar)),
            ("quick", lambda: QuickCard(self)),
            ("recycle", lambda: RecycleCard(self.poll("recycle"))),
            ("screentime", lambda: ScreenTimeCard(self.screen_time)),
            ("github", lambda: PollCard("GitHub", self.poll("github"),
                                        self.ask_github)),
            ("revenue", lambda: PollCard("Revenue", self.poll("revenue"))),
            ("notes", lambda: NotesCard(self.cfg)),
            ("pomodoro", lambda: PomodoroCard(
                self.cfg["pomodoro_minutes"],
                quiet=lambda: in_quiet_hours(self.cfg["quiet_hours"]))),
            ("stopwatch", StopwatchCard),
            ("todos", lambda: TodoCard(self.cfg)),
        ]
        for key, make in makers:
            if w.get(key):
                self.cards.append(make())
        for c in self.cards:
            self.row.addWidget(c)
            c.tick()
        self._sync_services()
        self.tick()
        self.place()

    def poll(self, key):
        if key not in self.polls:
            fetch, every = self._poll_makers[key]
            self.polls[key] = extras.Poll(fetch, every)
        return self.polls[key]

    def _sync_services(self):
        """Background work only runs for widgets that are switched on."""
        w = self.cfg["widgets"]
        meeting = bool(self.cfg["pause_before_meeting"])
        self.weather.active = bool(w.get("weather"))
        self.calendar.active = bool(w.get("calendar")) or meeting
        self.media.active = bool(w.get("media")) or meeting
        for key in list(self.polls):
            if not w.get(key):
                self.polls.pop(key).stop()

    # -- theme / accent ------------------------------------------------------
    def apply_theme(self):
        self.tokens = theme.resolve(
            self.cfg["theme"], THEMES_DIR,
            self.accent if self.cfg["dynamic_accent"] else None)
        css = theme.build_qss(self.tokens)
        try:
            css += "\n" + CUSTOM_QSS.read_text(encoding="utf-8")
        except OSError:
            pass
        font = self.tokens["font"]
        if QApplication.font().family() != font:
            QApplication.setFont(QFont(font, 10))
        self.setStyleSheet(css)
        self._bg = None
        self.update()

    def set_theme(self, name):
        self.cfg["theme"] = name
        save_config(self.cfg)
        self.apply_theme()

    def _check_wallpaper(self):
        path = winapi.wallpaper_path()
        if not path:
            return
        try:
            key = (path, os.path.getmtime(path))
        except OSError:
            return
        if key != self._wall_key:
            self._wall_key = key
            threading.Thread(target=self._compute_accent, args=(path,),
                             daemon=True).start()

    def _compute_accent(self, path):
        """Runs in a thread: decode a tiny version of the wallpaper."""
        try:
            reader = QImageReader(path)
            reader.setScaledSize(QSize(48, 27))
            img = reader.read()
            if img.isNull():
                return
            px = []
            for y in range(img.height()):
                for x in range(img.width()):
                    c = img.pixelColor(x, y)
                    px.append((c.red(), c.green(), c.blue()))
            acc = theme.dominant_accent(px)
            if acc:
                self._accent_pending = acc
        except Exception:
            pass

    def sync_hotkey(self):
        if self.cfg.get("launcher"):
            self.hotkey.register(self.cfg.get("launcher_hotkey", "alt+space"))
        else:
            self.hotkey.unregister()

    def _sync_autohide_timer(self):
        if self.cfg.get("auto_hide"):
            if not self._hover_timer.isActive():
                self._hover_timer.start(250)
        else:
            self._hover_timer.stop()

    def _fullscreen(self):
        now = time.monotonic()
        if now - self._fs[0] >= 1.0:
            self._fs = (now, winapi.foreground_is_fullscreen(
                self.appbar.hwnd or int(self.winId())))
        return self._fs[1]

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self.apply_native)

    def apply_native(self):
        hwnd = int(self.winId())
        self.appbar.hwnd = hwnd
        self.glass_active = bool(self.cfg["glass"]) and winapi.enable_glass(hwnd)
        winapi.set_taskbar_autohide(self.cfg["hide_taskbar"], hwnd, self.cfg)
        save_config(self.cfg)
        self.place()
        self._bg = None
        self.update()
        if not self.cfg["weather_city"] and self.cfg["widgets"]["weather"]:
            QTimer.singleShot(400, self.ask_city)

    def place(self):
        screen = QApplication.primaryScreen()
        dpr = screen.devicePixelRatio()
        full = screen.geometry()
        w, h = self.width(), self.height()
        top = self.cfg["position"] == "top"
        y = None
        if self.cfg["reserve_space"] and winapi.IS_WIN and self.appbar.hwnd:
            rect = (int(full.x() * dpr), int(full.y() * dpr),
                    int((full.x() + full.width()) * dpr),
                    int((full.y() + full.height()) * dpr))
            key = (top, rect, int((h + 2 * MARGIN) * dpr))
            if key != self._res_key or not self.appbar.registered:
                self._res_rc = self.appbar.reserve(*key)
                self._res_key = key
            rc = self._res_rc
            if rc:
                y = rc[1] / dpr + MARGIN if top else rc[3] / dpr - h - MARGIN
        else:
            self.appbar.remove()
            self._res_key = None
        if y is None:
            avail = screen.availableGeometry()
            y = (avail.y() + MARGIN if top
                 else avail.y() + avail.height() - h - MARGIN)
        if self.cfg.get("full_width"):
            self.setFixedWidth(int(full.width() - 2 * MARGIN))
            self.move(int(full.x() + MARGIN), int(y))
        else:
            self.move(int(full.x() + (full.width() - w) // 2), int(y))
        self._shown_pos = self.pos()
        if self._hidden:
            self.move(self._hidden_pos())

    def tick(self):
        self._tick_n += 1
        changed = False
        for c in self.cards:
            if self._hidden and not getattr(c, "ALWAYS", False):
                continue                      # slid away: only timers keep running
            if self._tick_n % getattr(c, "INTERVAL", 1) == 0:
                changed = bool(c.tick()) or changed
        if self._accent_pending:
            acc, self._accent_pending = self._accent_pending, None
            if acc != self.accent:
                self.accent = acc
                self.cfg["_accent"] = acc
                save_config(self.cfg)
                if self.cfg["dynamic_accent"]:
                    self.apply_theme()
        if self.cfg["dynamic_accent"] and self._tick_n % 30 == 1:
            self._check_wallpaper()
        if changed and not self._hidden:
            self.adjustSize()
            size = (self.width(), self.height())
            if size != self._last_size:
                self._last_size = size
                self.place()
        self.automations()

    # -- auto-hide -----------------------------------------------------------
    SLIVER = 4  # px left visible at the edge while hidden

    def _hidden_pos(self):
        pos = self._shown_pos or self.pos()
        screen = QApplication.primaryScreen().geometry()
        if self.cfg["position"] == "top":
            return pos.__class__(pos.x(), screen.y() - self.height()
                                 + self.SLIVER)
        return pos.__class__(pos.x(), screen.y() + screen.height()
                             - self.SLIVER)

    def _cursor_near(self):
        """True when the mouse is over the dock, or over the sliver / screen
        edge where the hidden dock sits."""
        cur = QCursor.pos()
        rect = self.geometry()
        rect.adjust(-2, -2, 2, 2)
        if rect.contains(cur):
            return True
        if self._hidden and self._shown_pos is not None:
            screen = QApplication.primaryScreen().geometry()
            in_x = (self._shown_pos.x() - 40 <= cur.x()
                    <= self._shown_pos.x() + self.width() + 40)
            if not in_x:
                return False
            if self.cfg["position"] == "top":
                return cur.y() <= screen.y() + 2
            return cur.y() >= screen.y() + screen.height() - 3
        return False

    def _autohide_check(self):
        if not self.cfg.get("auto_hide"):
            if self._hidden:
                self._slide(False)
            return
        if self._drag is not None or self._menu_open \
                or QApplication.activeModalWidget() is not None:
            self._last_hover = time.monotonic()
            return
        if self._animating:
            return
        if self._cursor_near():
            self._last_hover = time.monotonic()
            if self._hidden:
                self._slide(False)
            return
        if self._hidden:
            return
        delay = max(2, int(self.cfg.get("auto_hide_delay", 5)))
        idle_long = time.monotonic() - self._last_hover >= delay
        if idle_long or self._fullscreen():
            self._slide(True)

    def _slide(self, hide):
        if hide == self._hidden or self._shown_pos is None:
            return
        self._hidden = hide
        if hide:
            self.appbar.remove()   # give the space back while hidden
            self._res_key = None
        self._anim.stop()
        self._animating = True
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self._hidden_pos() if hide
                               else self._shown_pos)
        self._anim.start()

    def _anim_done(self):
        self._animating = False
        if not self._hidden:
            for c in self.cards:   # catch up on what changed while hidden
                c.tick()
            self.place()           # re-reserve space, settle exact position
        self._last_hover = time.monotonic()

    def enterEvent(self, e):
        self._last_hover = time.monotonic()
        super().enterEvent(e)

    # -- automations ---------------------------------------------------------
    def automations(self):
        if not self.cfg["pause_before_meeting"]:
            return
        nxt = self.calendar.next_event()
        if not nxt:
            return
        dt, title = nxt
        secs = (dt - datetime.now()).total_seconds()
        if 0 <= secs <= 60 and self._fired != (dt, title):
            self._fired = (dt, title)
            if self.media.playing:
                self.media.pause()

    # -- dialogs -------------------------------------------------------------
    def ask_text(self, key, title, label, refresh=None):
        text, ok = QInputDialog.getText(self, title, label, text=self.cfg[key])
        if ok:
            self.cfg[key] = text.strip()
            save_config(self.cfg)
            if refresh:
                refresh()

    def ask_city(self):
        self.ask_text("weather_city", "Weather", "City:", self.weather.refresh)

    def ask_calendar(self):
        self.ask_text("calendar_url", "Calendar",
                      "Secret iCal link (Google: Settings > calendar > "
                      "'Secret address in iCal format'):",
                      self.calendar.refresh)

    def ask_autohide_delay(self):
        val, ok = QInputDialog.getInt(
            self, "Auto-hide", "Hide after this many seconds away:",
            int(self.cfg.get("auto_hide_delay", 5)), 2, 120)
        if ok:
            self.cfg["auto_hide_delay"] = val
            save_config(self.cfg)

    def ask_quiet_hours(self):
        self.ask_text("quiet_hours", "Quiet hours",
                      "Quiet hours for sounds, e.g. 23:00-07:00 "
                      "(blank = off):")

    def ask_github(self):
        self.ask_text("github_user", "GitHub", "GitHub username:",
                      lambda: self.poll("github").refresh())

    # -- painting / dragging -------------------------------------------------
    def resizeEvent(self, e):
        self._bg = None
        super().resizeEvent(e)

    def _render_bg(self):
        dpr = self.devicePixelRatioF()
        pm = QPixmap(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.tokens
        if self.glass_active:
            p.fillRect(self.rect(), QColor(*theme.to_rgba(t["glass"])))
        else:
            path = QPainterPath()
            r = t["panel_radius"]
            path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), r, r)
            p.fillPath(path, QColor(*theme.to_rgba(t["panel"])))
            p.setPen(QColor(*theme.to_rgba(t["border"])))
            p.drawPath(path)
        p.end()
        self._bg = pm

    def paintEvent(self, _):
        if self._bg is None:
            self._render_bg()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        was_drag = self._drag is not None
        self._drag = None
        if not was_drag:
            return
        geo = QApplication.primaryScreen().geometry()
        y = e.globalPosition().toPoint().y()
        edge = None
        if y <= geo.y() + 48:
            edge = "top"
        elif y >= geo.y() + geo.height() - 48:
            edge = "bottom"
        if edge and edge != self.cfg["position"]:
            self.cfg["position"] = edge
            save_config(self.cfg)
        self.place()

    # -- menu ----------------------------------------------------------------
    def contextMenuEvent(self, e):
        self._menu_open = True
        try:
            self._build_menu(e)
        finally:
            self._menu_open = False

    def _build_menu(self, e):
        m = QMenu(self)
        pos = QAction("Move to top" if self.cfg["position"] == "bottom"
                      else "Move to bottom", self)
        pos.triggered.connect(self.toggle_position)
        m.addAction(pos)
        m.addSeparator()
        for key, label in WIDGET_LABELS.items():
            a = QAction(label, self, checkable=True)
            a.setChecked(self.cfg["widgets"].get(key, False))
            a.toggled.connect(lambda on, k=key: self.set_widget(k, on))
            m.addAction(a)
        m.addSeparator()
        for key, label in [
            ("reserve_space", "Reserve screen space"),
            ("hide_taskbar", "Auto-hide Windows taskbar"),
            ("glass", "Glass effect"),
            ("pause_before_meeting", "Pause music before meetings"),
            ("full_width", "Full width"),
            ("auto_hide", "Auto-hide dock (fullscreen friendly)"),
            ("dynamic_accent", "Dynamic accent (from wallpaper)"),
            ("launcher", f"Launcher hotkey ({self.cfg['launcher_hotkey']})"),
        ]:
            a = QAction(label, self, checkable=True)
            a.setChecked(self.cfg[key])
            a.toggled.connect(lambda on, k=key: self.set_option(k, on))
            m.addAction(a)
        auto = QAction("Start with Windows", self, checkable=True)
        auto.setChecked(winapi.autostart_enabled())
        auto.toggled.connect(
            lambda on: winapi.set_autostart(on, "Windows Bar", autostart_command()))
        m.addAction(auto)
        tm = m.addMenu("Theme")
        grp = QActionGroup(tm)
        for name in theme.list_themes(THEMES_DIR):
            a = QAction(name.capitalize(), tm, checkable=True)
            a.setChecked(name == self.cfg["theme"])
            grp.addAction(a)
            tm.addAction(a)
            a.triggered.connect(lambda _=False, n=name: self.set_theme(n))
        tm.addSeparator()
        folder = QAction("Open themes folder…", tm)
        folder.triggered.connect(self.open_themes_folder)
        tm.addAction(folder)
        launch = QAction("Open launcher", self)
        launch.triggered.connect(self.launcher.open)
        m.addAction(launch)
        quiet = QAction("Set quiet hours…", self)
        quiet.triggered.connect(self.ask_quiet_hours)
        m.addAction(quiet)
        delay = QAction("Set auto-hide delay…", self)
        delay.triggered.connect(self.ask_autohide_delay)
        m.addAction(delay)
        m.addSeparator()
        for label, fn in [("Set weather city…", self.ask_city),
                          ("Set calendar link…", self.ask_calendar),
                          ("Set GitHub user…", self.ask_github)]:
            a = QAction(label, self)
            a.triggered.connect(fn)
            m.addAction(a)
        m.addSeparator()
        q = QAction("Quit", self)
        q.triggered.connect(QApplication.quit)
        m.addAction(q)
        m.exec(e.globalPos())

    def toggle_position(self):
        if self._hidden:
            self._hidden = False
            self._anim.stop()
            self._animating = False
        self.cfg["position"] = "top" if self.cfg["position"] == "bottom" else "bottom"
        save_config(self.cfg)
        self.place()

    def set_widget(self, key, on):
        self.cfg["widgets"][key] = on
        save_config(self.cfg)
        self.rebuild()

    def set_option(self, key, on):
        self.cfg[key] = on
        if key == "auto_hide":
            self._sync_autohide_timer()
            self._last_hover = time.monotonic()
            if not on and self._hidden:
                self._slide(False)
        elif key == "hide_taskbar":
            winapi.set_taskbar_autohide(on, self.appbar.hwnd, self.cfg)
        elif key == "full_width" and not on:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
        elif key == "glass":
            if on:
                self.glass_active = winapi.enable_glass(self.appbar.hwnd)
            else:
                winapi.disable_glass(self.appbar.hwnd)
                self.glass_active = False
            self._bg = None
            self.update()
        elif key == "dynamic_accent":
            self._wall_key = None
            self.apply_theme()
        elif key == "launcher":
            self.sync_hotkey()
        elif key == "pause_before_meeting":
            self._sync_services()
        save_config(self.cfg)
        self.place()

    def open_themes_folder(self):
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
        example = THEMES_DIR / "example.json"
        if not example.exists():
            example.write_text(json.dumps(
                {"accent": "#ff9f43", "panel": [24, 18, 12, 230],
                 "card": [255, 200, 120, 22], "radius": 14}, indent=2),
                encoding="utf-8")
        os.startfile(str(THEMES_DIR))

    def shutdown(self):
        self.hotkey.unregister()
        self.screen_time.flush()
        self.appbar.remove()
        winapi.set_taskbar_autohide(False, self.appbar.hwnd, self.cfg)
        save_config(self.cfg)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    dock = Dock()
    app.aboutToQuit.connect(dock.shutdown)
    dock.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
