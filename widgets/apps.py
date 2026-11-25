"""Pinned-app card."""
import shutil
import subprocess
from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFileIconProvider, QFrame, QHBoxLayout,
                               QMenu, QPushButton)
import winapi

def _exe_of(cmd):
    """'C:\\…\\Code.exe --flag' / 'notepad.exe' -> 'code.exe' / 'notepad.exe'."""
    text = (cmd or "").strip()
    if not text:
        return ""
    if text.startswith('"'):
        first = text[1:].split('"')[0]
    else:
        first = text.split()[0]
    return first.replace("/", "\\").rsplit("\\", 1)[-1].lower()

def _icon_for_command(cmd):
    """Return the shell icon for a configured executable when it resolves."""
    text = (cmd or "").strip()
    if not text:
        return None
    if text.startswith('"'):
        executable = text[1:].split('"', 1)[0]
    else:
        executable = text.split()[0]
    path = (executable if QFileInfo(executable).isAbsolute()
            else shutil.which(executable))
    if not path or not QFileInfo(path).exists():
        return None
    icon = QFileIconProvider().icon(QFileInfo(path))
    return icon if not icon.isNull() else None

class AppsCard(QFrame):
    """Pinned apps, with a dot on the running ones."""

    INTERVAL = 2

    def __init__(self, apps, poll):
        super().__init__()
        self.setObjectName("card")
        self.poll = poll
        self.apps = apps
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self.btns = {}
        for name, cmd in apps.items():
            b = QPushButton()
            icon = _icon_for_command(cmd)
            if icon is not None:
                b.setIcon(icon)
                b.setIconSize(QSize(25, 25))
                b.setFixedSize(44, 44)
                b.setObjectName("appIcon")
            else:
                b.setText(name)
                b.setMinimumHeight(44)
            b.setProperty("usesNativeIcon", icon is not None)
            b.setCursor(Qt.PointingHandCursor)
            b.setAccessibleName(name)
            b.setToolTip(name + "  (Win/Alt+number opens or switches)")
            b.clicked.connect(lambda _=False, n=name: self.activate(n))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(
                lambda pos, n=name, btn=b: self._menu(n, btn, pos))
            lay.addWidget(b)
            self.btns[name] = b
        self._running = None

    @staticmethod
    def launch(cmd):
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception:
            pass

    def _hwnd(self, name):
        state = self.poll.value or {}
        return state.get(_exe_of(self.apps[name]))

    def activate(self, name):
        hwnd = self._hwnd(name)
        if hwnd:
            if winapi.foreground_hwnd() == hwnd:
                winapi.minimize_window(hwnd)
            else:
                winapi.focus_window(hwnd)
        else:
            self.launch(self.apps[name])

    def _menu(self, name, btn, pos):
        hwnd = self._hwnd(name)
        m = QMenu(self)
        a = QAction(tr("Open new window"), self)
        a.triggered.connect(lambda: self.launch(self.apps[name]))
        m.addAction(a)
        if hwnd:
            for label, fn in [("Focus", lambda: winapi.focus_window(hwnd)),
                              ("Minimize",
                               lambda: winapi.minimize_window(hwnd)),
                              ("Close window",
                               lambda: winapi.close_window(hwnd))]:
                a = QAction(label, self)
                a.triggered.connect(fn)
                m.addAction(a)
        m.exec(btn.mapToGlobal(pos))

    def tick(self):
        state = self.poll.value
        if state is None:
            return False
        running = {name: (_exe_of(cmd) in state)
                   for name, cmd in self.apps.items()}
        if running == self._running:
            return False
        self._running = running
        for name, on in running.items():
            b = self.btns[name]
            if not b.property("usesNativeIcon"):
                b.setText(name + " ●" if on else name)
            prop = "true" if on else "false"
            if b.property("active") != prop:
                b.setProperty("active", prop)
                b.style().unpolish(b)
                b.style().polish(b)
        return True

from core.i18n import tr

WIDGET_ID = 'apps'
WIDGET_ORDER = 0

def make_card(dock):
    return AppsCard(dock.cfg["apps"], dock.poll("apps"))
