"""Screen-time card."""
import extras
from widgets.base import Card

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


WIDGET_ID = 'screentime'
WIDGET_ORDER = 18

def make_card(dock):
    return ScreenTimeCard(dock.screen_time)
