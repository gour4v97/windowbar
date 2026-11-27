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

def _icon_for_path(path):
    """Return the shell icon for an existing executable path."""
    if not path or not QFileInfo(path).exists():
        return None
    icon = QFileIconProvider().icon(QFileInfo(path))
    return icon if not icon.isNull() else None


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
    return _icon_for_path(path)


_SELF_EXES = frozenset({"windows bar.exe", "windowsbar.exe"})


class AppsCard(QFrame):
    """Pinned apps plus active running programs, with running indicators."""

    INTERVAL = 2

    def __init__(self, apps, poll, on_pin=None):
        super().__init__()
        self.setObjectName("card")
        self.poll = poll
        self.apps = apps
        self._on_pin = on_pin
        self._pinned_exes = {_exe_of(cmd) for cmd in apps.values() if _exe_of(cmd)}
        self._icon_cache = {}
        self._dynamic_btns = {}
        self._dynamic_paths = {}
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(8, 6, 8, 6)
        self.lay.setSpacing(6)
        self.btns = {}
        for name, cmd in apps.items():
            b = self._build_button(
                name,
                _icon_for_command(cmd),
                name + "  (Win/Alt+number opens or switches)",
                lambda _=False, n=name: self.activate(n),
                lambda pos, btn, n=name: self._menu(n, btn, pos),
            )
            self.lay.addWidget(b)
            self.btns[name] = b
        self._running = None
        self._dynamic_state = None

    @staticmethod
    def _build_button(label, icon, tip, on_click, on_menu):
        b = QPushButton()
        if icon is not None:
            b.setIcon(icon)
            b.setIconSize(QSize(25, 25))
            b.setFixedSize(44, 44)
            b.setObjectName("appIcon")
        else:
            b.setText(label)
            b.setMinimumHeight(44)
        b.setProperty("usesNativeIcon", icon is not None)
        b.setCursor(Qt.PointingHandCursor)
        b.setAccessibleName(label)
        b.setToolTip(tip)
        b.clicked.connect(on_click)
        b.setContextMenuPolicy(Qt.CustomContextMenu)
        b.customContextMenuRequested.connect(lambda pos, btn=b: on_menu(pos, btn))
        return b

    @staticmethod
    def launch(cmd):
        try:
            subprocess.Popen(cmd, shell=True)
        except Exception:
            pass

    def _hwnd(self, name):
        state = self.poll.value or {}
        return state.get(_exe_of(self.apps[name]))

    @staticmethod
    def _focus_or_minimize(hwnd):
        if winapi.foreground_hwnd() == hwnd:
            winapi.minimize_window(hwnd)
        else:
            winapi.focus_window(hwnd)

    def activate(self, name):
        hwnd = self._hwnd(name)
        if hwnd:
            self._focus_or_minimize(hwnd)
        else:
            self.launch(self.apps[name])

    def _window_menu(self, hwnd, btn, pos, extra_actions=()):
        m = QMenu(self)
        for action in extra_actions:
            m.addAction(action)
        if hwnd:
            for label, fn in [("Focus", lambda: winapi.focus_window(hwnd)),
                              ("Minimize",
                               lambda: winapi.minimize_window(hwnd)),
                              ("Close window",
                               lambda: winapi.close_window(hwnd))]:
                a = QAction(tr(label), self)
                a.triggered.connect(fn)
                m.addAction(a)
        m.exec(btn.mapToGlobal(pos))

    def _menu(self, name, btn, pos):
        hwnd = self._hwnd(name)
        pin_new = QAction(tr("Open new window"), self)
        pin_new.triggered.connect(lambda: self.launch(self.apps[name]))
        self._window_menu(hwnd, btn, pos, extra_actions=(pin_new,))

    def _dynamic_menu(self, exe, btn, pos):
        state = self.poll.value or {}
        hwnd = state.get(exe)
        extras = []
        path = self._dynamic_paths.get(exe)
        if self._on_pin is not None and path:
            label = exe[:-4].capitalize() if exe.endswith(".exe") else exe
            pin = QAction(tr("Pin to dock"), self)
            pin.triggered.connect(lambda: self._on_pin(label, path))
            extras.append(pin)
        self._window_menu(hwnd, btn, pos, extra_actions=extras)

    def _sync_dynamic(self, state):
        active_exes = tuple(
            exe for exe in state
            if exe not in self._pinned_exes and exe not in _SELF_EXES
        )
        if active_exes == self._dynamic_state:
            return False
        self._dynamic_state = active_exes
        active_set = set(active_exes)
        for exe in list(self._dynamic_btns):
            if exe not in active_set:
                btn = self._dynamic_btns.pop(exe)
                self.lay.removeWidget(btn)
                btn.deleteLater()
        for exe in active_exes:
            if exe in self._dynamic_btns:
                continue
            hwnd = state[exe]
            if exe not in self._icon_cache:
                path = winapi.window_process_path(hwnd)
                self._dynamic_paths[exe] = path
                self._icon_cache[exe] = _icon_for_path(path)
            label = exe[:-4] if exe.endswith(".exe") else exe
            btn = self._build_button(
                label,
                self._icon_cache[exe],
                label,
                lambda _=False, e=exe: self._focus_or_minimize(
                    (self.poll.value or {}).get(e)),
                lambda pos, b, e=exe: self._dynamic_menu(e, b, pos),
            )
            btn.setProperty("active", "true")
            self.lay.addWidget(btn)
            self._dynamic_btns[exe] = btn
        return True

    def tick(self):
        state = self.poll.value
        if state is None:
            return False
        changed = False
        running = {name: (_exe_of(cmd) in state)
                   for name, cmd in self.apps.items()}
        if running != self._running:
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
            changed = True
        if self._sync_dynamic(state):
            changed = True
        return changed

from core.i18n import tr

WIDGET_ID = 'apps'
WIDGET_ORDER = 0

def make_card(dock):
    def _pin(label, path):
        if label not in dock.cfg["apps"]:
            dock.cfg["apps"][label] = path
            dock.reload_widgets()
    return AppsCard(dock.cfg["apps"], dock.poll("apps"), on_pin=_pin)
