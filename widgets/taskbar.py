"""Open-window, pinned-app, and Recycle Bin cards."""
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton
import winapi
from widgets.base import Card, clip
from widgets.system import QuickCard
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


class AppsCard(QFrame):
    """Pinned apps: a dot marks the running ones; clicking
    a running app focuses it (or minimises it when already focused),
    clicking a stopped one launches it. Right-click an app for more."""

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
            b = QPushButton(name)
            b.setCursor(Qt.PointingHandCursor)
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
        a = QAction("Open new window", self)
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
            b.setText(name + " ●" if on else name)
            prop = "true" if on else "false"
            if b.property("active") != prop:
                b.setProperty("active", prop)
                b.style().unpolish(b)
                b.style().polish(b)
        return True


# ---------------------------------------------------------- more cards ----
