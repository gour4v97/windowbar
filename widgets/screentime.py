"""Focus, stopwatch, todo, and screen time cards."""
import math
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog
import extras
from core.formatting import fmt_hms
from widgets.base import Card, clip

class ScreenTimeCard(Card):
    INTERVAL = 5

    def __init__(self, tracker):
        super().__init__("Screen time")
        self.tracker = tracker

    def tick(self):
        total, top = self.tracker.today()
        tip = "\n".join(f"{n}: {extras.fmt_dur(s)}" for n, s in top)
        if tip and tip != self.toolTip():
            self.setToolTip(tip)
        return self.set_texts(body=extras.fmt_dur(total) + " today")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'screentime'
WIDGET_ORDER = 18

def make_card(dock):
    return ScreenTimeCard(dock.screen_time)
