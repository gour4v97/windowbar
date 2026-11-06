"""Keyboard-first launcher (Rofi/Seelen-style): Alt+Space, type, Enter.

Searches your configured apps, Start Menu programs and open windows with fuzzy
matching. Extras: `> command` runs a shell command, `= 2*(3+4)` calculates
(Enter copies the result), and a typed path opens it.
"""
import ctypes
import os
import subprocess
import threading
import time
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (QApplication, QLineEdit, QListWidget,
                               QListWidgetItem, QVBoxLayout, QWidget)

import search
import theme
import winapi

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000


class HotkeyFilter(QAbstractNativeEventFilter):
    """Global hotkey through RegisterHotKey; works while any app has focus."""
    ID = 0xB17

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.registered = False

    def register(self, spec):
        self.unregister()
        parsed = search.parse_hotkey(spec)
        if not parsed or not winapi.IS_WIN:
            return False
        mods, vk = parsed
        try:
            self.registered = bool(ctypes.windll.user32.RegisterHotKey(
                None, self.ID, mods | MOD_NOREPEAT, vk))
        except Exception:
            self.registered = False
        return self.registered

    def unregister(self):
        if self.registered and winapi.IS_WIN:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.ID)
            except Exception:
                pass
        self.registered = False

    def nativeEventFilter(self, event_type, message):
        if self.registered and event_type in (b"windows_generic_MSG",
                                              "windows_generic_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self.ID:
                    QTimer.singleShot(0, self.callback)
                    return True, 0
            except Exception:
                pass
        return False, 0


class Launcher(QWidget):
    MAX_ROWS = 8

    def __init__(self, cfg, get_tokens):
        super().__init__()
        self.cfg, self.get_tokens = cfg, get_tokens
        self._start_menu = []
        self._scanned_at = 0.0
        self._scanning = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search apps and windows…   > command   = math")
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setUniformItemSizes(True)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lay.addWidget(self.edit)
        lay.addWidget(self.list)
        self.setFixedWidth(560)
        self.edit.textChanged.connect(self.refresh)
        self.edit.installEventFilter(self)
        self.list.itemClicked.connect(lambda _i: self.run_current())
        self._rescan()

    # -- data ----------------------------------------------------------------
    def _rescan(self):
        if self._scanning:
            return
        self._scanning = True

        def work():
            try:
                self._start_menu = search.scan_start_menu()
            finally:
                self._scanned_at = time.monotonic()
                self._scanning = False
        threading.Thread(target=work, daemon=True).start()

    def _entries(self):
        entries = [(n, c, "cmd") for n, c in self.cfg.get("apps", {}).items()]
        names = {e[0].lower() for e in entries}
        entries += [e for e in self._start_menu if e[0].lower() not in names]
        entries += [(t, h, "window") for h, t in winapi.list_open_windows(limit=30)]
        return entries

    # -- show / hide -----------------------------------------------------------
    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.open()

    def open(self):
        if time.monotonic() - self._scanned_at > 600:
            self._rescan()
        self.setStyleSheet(theme.build_launcher_qss(self.get_tokens()))
        self._all = self._entries()
        self.edit.blockSignals(True)
        self.edit.clear()
        self.edit.blockSignals(False)
        self.refresh()
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.x() + (screen.width() - self.width()) // 2,
                  screen.y() + int(screen.height() * 0.22))
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()

    def event(self, e):
        if e.type() == QEvent.WindowDeactivate and self.isVisible():
            QTimer.singleShot(80, self._hide_if_inactive)
        return super().event(e)

    def _hide_if_inactive(self):
        if self.isVisible() and not self.isActiveWindow():
            self.hide()

    # -- results ---------------------------------------------------------------
    def refresh(self):
        text = self.edit.text()
        rows = []
        if text.startswith(">"):
            cmd = text[1:].strip()
            if cmd:
                rows.append((f"Run: {cmd}", cmd, "shell"))
        else:
            expr = text[1:] if text.startswith("=") else text
            if text.startswith("=") or any(c in text for c in "+*/^%"):
                res = search.safe_calc(expr.replace("^", "**"))
                if res is not None:
                    rows.append((f"= {res}   (Enter copies)", res, "copy"))
            path = os.path.expandvars(text.strip().strip('"'))
            if len(path) > 2 and os.path.exists(path):
                rows.append((f"Open {path}", path, "path"))
            rows += search.rank(text, getattr(self, "_all", []), self.MAX_ROWS)
        self.list.clear()
        for name, target, kind in rows[: self.MAX_ROWS]:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (target, kind))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.list.setFixedHeight(max(1, self.list.count()) * 38 + 4)
        self.adjustSize()

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == QEvent.KeyPress:
            key = e.key()
            if key == Qt.Key_Escape:
                self.hide()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.run_current()
                return True
            if key in (Qt.Key_Down, Qt.Key_Up):
                n = self.list.count()
                if n:
                    step = 1 if key == Qt.Key_Down else -1
                    self.list.setCurrentRow((self.list.currentRow() + step) % n)
                return True
        return super().eventFilter(obj, e)

    def run_current(self):
        item = self.list.currentItem()
        if item is None:
            return
        target, kind = item.data(Qt.UserRole)
        self.hide()
        try:
            if kind in ("cmd", "shell"):
                subprocess.Popen(target, shell=True)
            elif kind in ("app", "path"):
                os.startfile(target)
            elif kind == "window":
                winapi.focus_window(target)
            elif kind == "copy":
                QApplication.clipboard().setText(target)
        except Exception:
            pass

    def paintEvent(self, _):
        t = self.get_tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1),
                            t["panel_radius"], t["panel_radius"])
        p.fillPath(path, QColor(*theme.to_rgba(t["panel"])[:3], 245))
        p.setPen(QColor(*theme.to_rgba(t["border"])))
        p.drawPath(path)
