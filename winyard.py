"""
Winyard - a smart dock for Windows 10/11.

Run:   pip install -r requirements.txt
       python winyard.py

Right-click the dock for the menu. Settings live in %APPDATA%\\Winyard\\config.json
Stripe revenue reads the key from the WINYARD_STRIPE_KEY environment variable.
"""
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil
from PySide6.QtCore import QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import (QAction, QColor, QCursor, QFont, QPainter,
                     QPainterPath)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

import extras
import winapi
from services import CalendarService, MediaService, WeatherService

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Winyard"
CONFIG = APP_DIR / "config.json"
SCREEN_TIME_FILE = APP_DIR / "screentime.json"
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

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
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
        return changed

    def tick(self):
        return False


class ClockCard(Card):
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
            return self.set_texts("NOW PLAYING", "pip install winsdk")
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
    def __init__(self, minutes, quiet=None):
        super().__init__("Focus")
        self.quiet = quiet or (lambda: False)
        self.minutes = minutes
        self.remaining = minutes * 60
        self.running = False
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: start/pause   Double-click: reset")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.running = not self.running

    def mouseDoubleClickEvent(self, e):
        self.running = False
        self.remaining = self.minutes * 60

    def tick(self):
        if self.running:
            self.remaining -= 1
            if self.remaining <= 0:
                self.running = False
                self.remaining = self.minutes * 60
                if not self.quiet():
                    QApplication.beep()
        return self.set_texts(
            "FOCUS" + (" ▶" if self.running else " ❚❚"),
            fmt_hms(self.remaining))


class StopwatchCard(Card):
    def __init__(self):
        super().__init__("Stopwatch")
        self.elapsed = 0
        self.running = False
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: start/pause   Double-click: reset")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.running = not self.running

    def mouseDoubleClickEvent(self, e):
        self.running = False
        self.elapsed = 0

    def tick(self):
        if self.running:
            self.elapsed += 1
        return self.set_texts(body=fmt_hms(self.elapsed))


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
    """Buttons for the currently open windows; click one to focus it."""

    INTERVAL = 4

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 6, 8, 6)
        self.lay.setSpacing(6)
        self._titles = None

    def tick(self):
        wins = winapi.list_open_windows(limit=6)
        titles = [t for _, t in wins]
        if titles == self._titles:
            return False
        self._titles = titles
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
            b.clicked.connect(lambda _=False, h=hwnd: winapi.focus_window(h))
            self.lay.addWidget(b)
        return True


class RecycleCard(Card):
    INTERVAL = 30

    def __init__(self):
        super().__init__("Recycle Bin")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to empty the Recycle Bin")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            QuickCard.empty_bin(self)

    def tick(self):
        n = winapi.recycle_count()
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


STYLE = """
QFrame#card { background: rgba(255,255,255,0.07); border-radius: 12px; }
QLabel#cardtitle { color: rgba(255,255,255,0.55); font-size: 9px;
                   font-weight: 600; letter-spacing: 1px; }
QLabel#cardbody { color: white; font-size: 15px; font-weight: 600; }
QPushButton { background: rgba(255,255,255,0.10); color: white; border: none;
              border-radius: 8px; padding: 6px 10px; font-size: 12px; }
QPushButton:hover { background: rgba(255,255,255,0.20); }
"""
MARGIN = 8


# ------------------------------------------------------------------ dock ----
class Dock(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        winapi.restore_taskbar(self.cfg)   # undo auto-hide left by a crash
        save_config(self.cfg)

        self.weather = None
        self.calendar = None
        self.media = None
        self.screen_time = None
        self.polls = {}
        self._ensure_services()
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
        self._animating = False
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(180)
        self._anim.finished.connect(self._anim_done)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)
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
        self._hover_timer.start(250)

    def _ensure_services(self):
        """Start only workers needed by enabled widgets and automations."""
        widgets = self.cfg["widgets"]
        if widgets.get("weather") and self.weather is None:
            self.weather = WeatherService(
                self.cfg, lambda: save_config(self.cfg))
        needs_calendar = widgets.get("calendar") or self.cfg["pause_before_meeting"]
        if needs_calendar and self.calendar is None:
            self.calendar = CalendarService(self.cfg)
        needs_media = widgets.get("media") or self.cfg["pause_before_meeting"]
        if needs_media and self.media is None:
            self.media = MediaService()
        if widgets.get("screentime") and self.screen_time is None:
            self.screen_time = extras.ScreenTime(SCREEN_TIME_FILE)
        poll_specs = {
            "github": (
                lambda: extras.github_summary(self.cfg["github_user"]), 1800),
            "revenue": (
                lambda: extras.stripe_revenue(
                    os.environ.get("WINYARD_STRIPE_KEY", "")), 1800),
            "downloads": (lambda: extras.downloads_summary(), 30),
            "shots": (
                lambda: extras.downloads_summary(
                    Path.home() / "Pictures" / "Screenshots"), 30),
        }
        for key, (fetch, interval) in poll_specs.items():
            if widgets.get(key) and key not in self.polls:
                self.polls[key] = extras.Poll(fetch, interval)

    # -- build ---------------------------------------------------------------
    def rebuild(self):
        self._ensure_services()
        for c in self.cards:
            self.row.removeWidget(c)
            c.deleteLater()
        self.cards = []
        w = self.cfg["widgets"]
        makers = [
            ("apps", lambda: AppsCard(self.cfg["apps"])),
            ("clock", ClockCard),
            ("weather", lambda: WeatherCard(self.weather, self.ask_city)),
            ("downloads", lambda: DownloadsCard(self.polls["downloads"])),
            ("shots", lambda: DownloadsCard(
                self.polls["shots"], "Screenshots",
                Path.home() / "Pictures" / "Screenshots")),
            ("windows", WindowsCard),
            ("system", SystemCard),
            ("battery", BatteryCard),
            ("media", lambda: MediaCard(self.media)),
            ("calendar", lambda: CalendarCard(self.calendar, self.ask_calendar)),
            ("quick", lambda: QuickCard(self)),
            ("recycle", RecycleCard),
            ("screentime", lambda: ScreenTimeCard(self.screen_time)),
            ("github", lambda: PollCard("GitHub", self.polls["github"],
                                        self.ask_github)),
            ("revenue", lambda: PollCard("Revenue", self.polls["revenue"])),
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
        self.tick()
        self.place()

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
            rc = self.appbar.reserve(top, rect, int((h + 2 * MARGIN) * dpr))
            if rc:
                y = rc[1] / dpr + MARGIN if top else rc[3] / dpr - h - MARGIN
        else:
            self.appbar.remove()
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
            if self._tick_n % getattr(c, "INTERVAL", 1) == 0:
                changed = bool(c.tick()) or changed
        if changed and not self._hidden:
            old_size = (self.width(), self.height())
            self.adjustSize()
            size = (self.width(), self.height())
            if size != old_size and size != self._last_size:
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
        fullscreen = winapi.foreground_is_fullscreen(
            self.appbar.hwnd or int(self.winId()))
        if idle_long or fullscreen:
            self._slide(True)

    def _slide(self, hide):
        if hide == self._hidden or self._shown_pos is None:
            return
        self._hidden = hide
        if hide:
            self.appbar.remove()   # give the space back while hidden
        self._anim.stop()
        self._animating = True
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self._hidden_pos() if hide
                               else self._shown_pos)
        self._anim.start()

    def _anim_done(self):
        self._animating = False
        if not self._hidden:
            self.place()           # re-reserve space, settle exact position
        self._last_hover = time.monotonic()

    def enterEvent(self, e):
        self._last_hover = time.monotonic()
        super().enterEvent(e)

    # -- automations ---------------------------------------------------------
    def automations(self):
        if not self.cfg["pause_before_meeting"]:
            return
        if self.calendar is None or self.media is None:
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
        if self.weather is None:
            return
        self.ask_text("weather_city", "Weather", "City:", self.weather.refresh)

    def ask_calendar(self):
        if self.calendar is None:
            return
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
        if "github" not in self.polls:
            return
        self.ask_text("github_user", "GitHub", "GitHub username:",
                      self.polls["github"].refresh)

    # -- painting / dragging -------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.glass_active:
            p.fillRect(self.rect(), QColor(20, 20, 24, 60))
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 20, 20)
        p.fillPath(path, QColor(18, 18, 22, 225))
        p.setPen(QColor(255, 255, 255, 40))
        p.drawPath(path)

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
        ]:
            a = QAction(label, self, checkable=True)
            a.setChecked(self.cfg[key])
            a.toggled.connect(lambda on, k=key: self.set_option(k, on))
            m.addAction(a)
        auto = QAction("Start with Windows", self, checkable=True)
        auto.setChecked(winapi.autostart_enabled())
        auto.toggled.connect(
            lambda on: winapi.set_autostart(on, "Winyard", autostart_command()))
        m.addAction(auto)
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
        if key == "pause_before_meeting" and on:
            self._ensure_services()
        if key == "auto_hide":
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
            self.update()
        save_config(self.cfg)
        self.place()

    def shutdown(self):
        if self.screen_time is not None:
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
