"""System, battery, media, calendar, and quick action cards."""
from datetime import datetime
import os
import time
import psutil
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QMessageBox,
                               QPushButton, QMenu)
import winapi
from widgets.base import Card, clip
from core.formatting import fmt_speed, fmt_delta


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
        self.open_popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: month view")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.open_popup:
                self.open_popup()
            else:
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
        power = QPushButton("Power")
        power.setCursor(Qt.PointingHandCursor)
        power.clicked.connect(self.power_menu)
        lay.addWidget(power)
        self.tick()

    def toggle_theme(self):
        try:
            winapi.set_dark_mode(not winapi.is_dark_mode())
        except Exception:
            pass
        self.tick()

    def power_menu(self):
        m = QMenu(self)
        for label, action in [("Lock", "lock"), ("Sleep", "sleep"),
                              ("Sign out", "signout")]:
            a = QAction(label, self)
            a.triggered.connect(
                lambda _=False, act=action: winapi.power_action(act))
            m.addAction(a)
        m.addSeparator()
        for label, action in [("Restart…", "restart"),
                              ("Shut down…", "shutdown")]:
            a = QAction(label, self)
            a.triggered.connect(
                lambda _=False, act=action, lab=label: self._confirm_power(
                    lab, act))
            m.addAction(a)
        m.exec(self.mapToGlobal(QPoint(0, 0)))

    def _confirm_power(self, label, action):
        verb = "Restart" if action == "restart" else "Shut down"
        if QMessageBox.question(self, verb, f"{verb} the PC now?"
                                ) == QMessageBox.Yes:
            winapi.power_action(action)

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

