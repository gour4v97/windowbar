"""Battery card."""
import psutil
from widgets.base import Card

class BatteryCard(Card):
    INTERVAL = 5
    STICKY = True

    def __init__(self):
        super().__init__("Battery")

    def tick(self):
        b = psutil.sensors_battery()
        if b is None:
            return self.set_texts(body="No battery")
        return self.set_texts(
            body=f"{b.percent:.0f}% {'⚡' if b.power_plugged else ''}")


WIDGET_ID = 'battery'
WIDGET_ORDER = 11

def make_card(dock):
    return BatteryCard()
