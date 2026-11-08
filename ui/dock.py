"""Main dock window and its interaction orchestration."""
import json
import logging
import math
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import psutil
from PySide6.QtCore import QPoint, QPropertyAnimation, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QFont,
                           QImageReader, QPainter, QPainterPath, QPixmap)
from PySide6.QtWidgets import (QApplication, QCalendarWidget, QFrame,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
    QColorDialog)
import extras
import theme
import winapi
import widgets
from core.app_config import (APP_DIR, SCREEN_TIME_FILE, THEMES_DIR, CUSTOM_QSS,
    DEFAULTS, WIDGET_LABELS, load_config, save_config, in_quiet_hours,
    autostart_command, PRESETS, MARGIN)
from core.registry import WidgetRegistry
from launcher import HotkeyFilter, Launcher
from ui.hotkeys import AppHotkeyFilter
from ui.panels import (CalendarPopup, TodosPanel, NotesPanel,
                       WidgetDetailPopup)
from services import CalendarService, MediaService, RadioService, WeatherService
from widgets.calendar_card import CalendarCard
from widgets.clock import ClockCard, AnalogClockCard
from widgets.apps import AppsCard, _exe_of
from widgets.notes import NotesCard
from widgets.todos import TodoCard

_log = logging.getLogger("windowsbar")
class Dock(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.cfg["todos"] = extras.normalize_todos(self.cfg.get("todos"))
        notes, cur = extras.normalize_notes(
            self.cfg.get("notes", ""), self.cfg.get("notes_list"),
            self.cfg.get("notes_current", 0))
        self.cfg["notes_list"], self.cfg["notes_current"] = notes, cur
        if self.cfg.get("keep_awake"):
            winapi.set_keep_awake(True)
        winapi.restore_taskbar(self.cfg)   # undo auto-hide left by a crash
        save_config(self.cfg)

        self.weather = WeatherService(self.cfg, lambda: save_config(self.cfg))
        self.calendar = CalendarService(self.cfg)
        self.media = MediaService()
        self.radios = RadioService()
        self.screen_time = extras.ScreenTime(SCREEN_TIME_FILE, start=False)
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
            "storage": (lambda: extras.disk_summary(), 60),
            "network": (lambda: extras.network_info(), 30),
            "script": (lambda: extras.run_script(self.cfg["script_command"]),
                       None),   # interval filled in poll()
            "apps": (winapi.open_window_processes, 2),
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
        self._widget_registry = WidgetRegistry()
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
        self.app_hotkeys = AppHotkeyFilter(self._app_hotkey)
        QApplication.instance().installNativeEventFilter(self.app_hotkeys)
        self.app_hotkeys.register_all(
            self.cfg.get("app_hotkey_modifier", "alt"))

    def ask_app_hotkey_modifier(self):
        choices = ["Alt", "Ctrl+Alt", "Win"]
        current = self.cfg.get("app_hotkey_modifier", "alt").lower()
        selected = next((item for item in choices
                         if item.lower() == current), "Alt")
        value, ok = QInputDialog.getItem(
            self, "Pinned-app hotkeys", "Modifier for 1–9:", choices,
            choices.index(selected), False)
        if ok:
            self.cfg["app_hotkey_modifier"] = value.lower()
            self.app_hotkeys.register_all(value.lower())
            save_config(self.cfg)

    def _app_hotkey(self, index):
        names = list(self.cfg["apps"])
        if index < len(names):
            name = names[index]
            state = self.polls.get("apps")
            hwnd = (state.value or {}).get(_exe_of(self.cfg["apps"][name]))                 if state else None
            if hwnd:
                winapi.focus_window(hwnd)
            else:
                AppsCard.launch(self.cfg["apps"][name])

    # -- build ---------------------------------------------------------------
    def rebuild(self):
        self._widget_registry.stop_all()
        for c in self.cards:
            self.row.removeWidget(c)
            c.deleteLater()
        self.cards = []
        registry = WidgetRegistry()
        registry.register_package(
            widgets, self, DEFAULTS["widgets"], WIDGET_LABELS)
        active = registry.start_enabled(self.cfg)
        self._widget_registry = registry
        self.cards = [widget.card() for widget in active.values()]
        for widget_id, widget in active.items():
            widget.card().setProperty("widgetId", widget_id)
        self._apply_widget_styles()
        for c in self.cards:
            self.row.addWidget(c)
            c.tick()
        self._sync_services()
        self.tick()
        self.place()

    def show_widget_details(self, anchor, title, details, actions=()):
        popup = WidgetDetailPopup(self, title, details, actions)
        return popup.show_near(anchor)

    def _clock_card(self):
        if self.cfg.get("clock_style") == "analog":
            return AnalogClockCard(lambda: self.cfg.get("_accent"))
        return ClockCard()

    def _calendar_card(self):
        card = CalendarCard(self.calendar, self.ask_calendar)
        card.open_popup = lambda: CalendarPopup(
            self, self.calendar, self.ask_calendar).show_near(card)
        return card

    def _todo_card(self):
        card = TodoCard(self.cfg, save_config)
        card.open_panel = lambda: TodosPanel(
            self, self.cfg, lambda: save_config(self.cfg)).show_near(card)
        return card

    def _notes_card(self):
        card = NotesCard(self.cfg)
        card.open_panel = lambda: NotesPanel(
            self, self.cfg, lambda: save_config(self.cfg)).show_near(card)
        return card

    def poll(self, key):
        if key not in self.polls:
            fetch, every = self._poll_makers[key]
            if every is None:
                every = max(5, int(self.cfg.get("script_interval", 60)))
            self.polls[key] = extras.Poll(fetch, every)
        return self.polls[key]

    def _sync_services(self):
        """Background work only runs for widgets that are switched on."""
        w = self.cfg["widgets"]
        meeting = bool(self.cfg["pause_before_meeting"])
        if w.get("screentime"):
            self.screen_time.start()
        else:
            self.screen_time.stop()
        self.weather.active = bool(w.get("weather"))
        self.calendar.active = bool(w.get("calendar")) or meeting
        self.media.active = bool(w.get("media")) or meeting
        self.radios.active = bool(w.get("toggles"))
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
        self._apply_widget_styles()
        self._bg = None
        self.update()

    def _apply_widget_styles(self):
        registry = getattr(self, "_widget_registry", None)
        if registry is None:
            return
        styles = self.cfg.get("widget_styles", {})
        for widget_id, widget in registry.active.items():
            tokens = theme.widget_tokens(
                self.tokens, styles.get(widget_id, {}))
            widget.card().setStyleSheet(theme.build_widget_qss(tokens))

    def edit_widget_style(self):
        labels = list(WIDGET_LABELS.values())
        keys = list(WIDGET_LABELS)
        label, ok = QInputDialog.getItem(
            self, "Widget style", "Widget:", labels, 0, False)
        if not ok:
            return
        widget_id = keys[labels.index(label)]
        options = ["Accent", "Card background", "Text", "Button", "Radius"]
        prop, ok = QInputDialog.getItem(
            self, "Widget style", "Style token:", options, 0, False)
        if not ok:
            return
        token = {"Accent": "accent", "Card background": "card",
                 "Text": "text", "Button": "button", "Radius": "radius"}[prop]
        override = self.cfg.setdefault("widget_styles", {}).setdefault(
            widget_id, {})
        if token == "radius":
            value, ok = QInputDialog.getInt(
                self, "Widget radius", "Radius:",
                int(override.get("radius", self.tokens["radius"])), 0, 48)
        else:
            current = QColor(*theme.to_rgba(
                override.get(token, self.tokens[token])))
            color = QColorDialog.getColor(current, self, f"{label}: {prop}",
                                          QColorDialog.ShowAlphaChannel)
            ok = color.isValid()
            value = list(color.getRgb()) if ok else None
        if not ok:
            return
        override[token] = value
        save_config(self.cfg)
        self.apply_theme()

    def clear_widget_style(self):
        labels = list(WIDGET_LABELS.values())
        keys = list(WIDGET_LABELS)
        label, ok = QInputDialog.getItem(
            self, "Reset widget style", "Widget:", labels, 0, False)
        if ok:
            self.cfg.setdefault("widget_styles", {}).pop(
                keys[labels.index(label)], None)
            save_config(self.cfg)
            self.apply_theme()

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
    def open_settings(self):
        if not getattr(self, "_settings_window", None):
            from ui.settings import SettingsWindow
            self._settings_window = SettingsWindow(self)
        self._settings_window.refresh()
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

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
        settings = QAction("Settings…", self)
        settings.triggered.connect(self.open_settings)
        m.addAction(settings)
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
        modifier = self.cfg.get("app_hotkey_modifier", "alt").title()
        app_keys = QAction(f"Pinned-app hotkeys ({modifier}+1…9)…", self)
        app_keys.triggered.connect(self.ask_app_hotkey_modifier)
        m.addAction(app_keys)
        auto = QAction("Start with Windows", self, checkable=True)
        auto.setChecked(winapi.autostart_enabled())
        auto.toggled.connect(
            lambda on: winapi.set_autostart(on, "Windows Bar", autostart_command()))
        m.addAction(auto)
        style_menu = m.addMenu("Widget styles")
        edit_style = QAction("Set widget style override…", style_menu)
        edit_style.triggered.connect(self.edit_widget_style)
        style_menu.addAction(edit_style)
        reset_style = QAction("Reset widget style…", style_menu)
        reset_style.triggered.connect(self.clear_widget_style)
        style_menu.addAction(reset_style)
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
        presets = m.addMenu("Presets")
        for label, keys in PRESETS.items():
            a = QAction(label, presets)
            a.triggered.connect(
                lambda _=False, ks=keys: self.apply_preset(ks))
            presets.addAction(a)
        style = QAction("Clock style: analogue", self, checkable=True)
        style.setChecked(self.cfg.get("clock_style") == "analog")
        style.toggled.connect(
            lambda on: self.set_clock_style("analog" if on else "digital"))
        m.addAction(style)
        script = QAction("Set script command…", self)
        script.triggered.connect(self.ask_script)
        m.addAction(script)
        zones = QAction("Set world clock zones…", self)
        zones.triggered.connect(self.ask_zones)
        m.addAction(zones)
        m.addSeparator()
        q = QAction("Quit", self)
        q.triggered.connect(QApplication.quit)
        m.addAction(q)
        m.exec(e.globalPos())

    def apply_preset(self, keys):
        for key in self.cfg["widgets"]:
            self.cfg["widgets"][key] = key in keys
        save_config(self.cfg)
        self.rebuild()

    def set_clock_style(self, style):
        self.cfg["clock_style"] = style
        save_config(self.cfg)
        self.rebuild()

    def ask_script(self):
        def refresh():
            poll = self.polls.get("script")
            if poll:
                poll.refresh()
            self.rebuild()
        self.ask_text("script_command", "Script widget",
                      "Shell command whose output the Script widget shows:",
                      refresh)

    def ask_zones(self):
        text, ok = QInputDialog.getText(
            self, "World clocks",
            "IANA zones, comma-separated (e.g. Europe/London, Asia/Tokyo):",
            text=", ".join(self.cfg["world_zones"]))
        if ok:
            self.cfg["world_zones"] = [z.strip() for z in text.split(",")
                                       if z.strip()][:3] or DEFAULTS[
                                           "world_zones"]
            save_config(self.cfg)
            self.rebuild()

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
        _log.info("Windows Bar shutting down")
        settings = getattr(self, "_settings_window", None)
        if settings is not None:
            settings.close()
        self._widget_registry.stop_all()
        for poll in self.polls.values():
            poll.stop()
        self.weather.stop()
        self.calendar.stop()
        self.media.stop()
        self.radios.stop()
        self.hotkey.unregister()
        self.app_hotkeys.unregister()
        winapi.set_keep_awake(False)
        self.screen_time.stop()
        self.appbar.remove()
        winapi.set_taskbar_autohide(False, self.appbar.hwnd, self.cfg)
        save_config(self.cfg)

