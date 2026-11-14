"""Day / week / year progress card."""
import extras
from widgets.base import Card

class ProgressCard(Card):

    INTERVAL = 5
    STICKY = True
    ORDER = ("day", "week", "year")

    def __init__(self):
        super().__init__("Day")
        self._i = 0

    def tick(self):
        p = extras.period_progress()
        key = self.ORDER[self._i % len(self.ORDER)]
        self._i += 1
        v = p[key]
        filled = int(round(v * 10))
        bar = "█" * filled + "░" * (10 - filled)
        return self.set_texts(key.upper(), f"{bar} {v * 100:.0f}%")


WIDGET_ID = 'progress'
WIDGET_ORDER = 3

def make_card(dock):
    return ProgressCard()
