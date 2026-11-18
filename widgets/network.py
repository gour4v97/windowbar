"""Network card."""
import time
import psutil
from core.formatting import fmt_speed
from widgets.base import Card

class NetworkCard(Card):
    INTERVAL = 1
    STICKY = True

    def __init__(self, info_poll):
        super().__init__("Network")
        self.info = info_poll
        self._last = psutil.net_io_counters()
        self._last_t = time.time()

    def tick(self):
        now = psutil.net_io_counters()
        t = time.time()
        dt = max(t - self._last_t, 0.001)
        down = (now.bytes_recv - self._last.bytes_recv) / dt
        up = (now.bytes_sent - self._last.bytes_sent) / dt
        self._last, self._last_t = now, t
        name, ip = self.info.value or ("", "")
        title = (name or "NETWORK").upper()
        if ip:
            title += " · " + ip
        return self.set_texts(
            title, f"↓{fmt_speed(down)} ↑{fmt_speed(up)}")


WIDGET_ID = 'network'
WIDGET_ORDER = 9

def make_card(dock):
    return NetworkCard(dock.poll("network"))
