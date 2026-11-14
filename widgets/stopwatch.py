"""Stopwatch card."""
import time
from PySide6.QtCore import Qt
from core.formatting import fmt_hms
from widgets.base import Card

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


WIDGET_ID = 'stopwatch'
WIDGET_ORDER = 24

def make_card(dock):
    return StopwatchCard()
