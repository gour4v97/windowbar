"""World-clock card."""
from datetime import datetime
from widgets.base import Card

class WorldClockCard(Card):
    INTERVAL = 5
    STICKY = True

    def __init__(self, zones):
        super().__init__("World")
        self.zones = zones

    def tick(self):
        from zoneinfo import ZoneInfo
        parts = []
        for z in self.zones[:3]:
            try:
                t = datetime.now(ZoneInfo(z))
            except Exception:
                continue
            label = z.split("/")[-1].replace("_", " ")[:5].upper()
            parts.append(f"{label} {t.strftime('%H:%M')}")
        return self.set_texts(
            body=" · ".join(parts) if parts else "Bad time zone")


WIDGET_ID = 'world'
WIDGET_ORDER = 2

def make_card(dock):
    return WorldClockCard(dock.cfg["world_zones"])
