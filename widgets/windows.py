"""Open-windows card."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
import winapi
from widgets.base import clip

class WindowsCard(QFrame):
    """Buttons for the open windows (taskbar-style); click one to focus it."""

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
            for i, (hwnd, _) in enumerate(wins):
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
            lab = QLabel(tr("No open windows"))
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

from core.i18n import tr

WIDGET_ID = 'windows'
WIDGET_ORDER = 7

def make_card(dock):
    return WindowsCard(dock.poll("windows"))
