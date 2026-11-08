"""Focus, stopwatch, todo, and screen time cards."""
import math
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog
import extras
from core.formatting import fmt_hms
from widgets.base import Card, clip

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

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'pomodoro'
WIDGET_ORDER = 22

def make_card(dock):
    return PomodoroCard(dock.cfg["pomodoro_minutes"], quiet=lambda: in_quiet_hours(dock.cfg["quiet_hours"]))
