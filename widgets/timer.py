"""Countdown timer card."""
import math
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog
from core.formatting import fmt_hms
from widgets.base import Card
from core.app_config import save_config, in_quiet_hours

class TimerCard(Card):
    """Countdown timer."""

    ALWAYS = True
    STICKY = True

    def __init__(self, cfg, quiet=None, save=None):
        super().__init__("Timer")
        self.cfg = cfg
        self.save = save or (lambda _cfg: None)
        self.quiet = quiet or (lambda: False)
        self.remaining = cfg["timer_minutes"] * 60.0
        self.running = False
        self._t = time.monotonic()
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: start/pause   Double-click: set minutes")

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
        val, ok = QInputDialog.getInt(self, "Timer", "Minutes:",
                                      int(self.cfg["timer_minutes"]), 1, 480)
        if ok:
            self.cfg["timer_minutes"] = val
            self.save(self.cfg)
            self.running = False
            self.remaining = val * 60.0

    def tick(self):
        self._advance()
        if self.running and self.remaining <= 0:
            self.running = False
            self.remaining = self.cfg["timer_minutes"] * 60.0
            if not self.quiet():
                QApplication.beep()
        return self.set_texts(
            "TIMER" + (" ▶" if self.running else " ❚❚"),
            fmt_hms(math.ceil(self.remaining)))


WIDGET_ID = 'timer'
WIDGET_ORDER = 23

def make_card(dock):
    return TimerCard(dock.cfg, quiet=lambda: in_quiet_hours(dock.cfg["quiet_hours"]), save=lambda cfg: save_config(cfg))
