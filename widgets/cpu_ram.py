"""CPU / RAM / network card."""
import time
import psutil
from PySide6.QtCore import Qt
from widgets.base import Card
from core.formatting import fmt_speed

class SystemCard(Card):
    STICKY = True

    def __init__(self):
        super().__init__("CPU / RAM")
        self._last = psutil.net_io_counters()
        self._last_t = time.time()
        self.download_bps = self.upload_bps = 0.0
        self.open_popup = None
        self.setCursor(Qt.PointingHandCursor)
        psutil.cpu_percent(None)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.open_popup:
            self.open_popup()

    def detail_lines(self):
        memory = psutil.virtual_memory()
        return [
            f"CPU usage: {psutil.cpu_percent(None):.0f}%",
            f"Memory: {memory.percent:.0f}% ({memory.used / (1024 ** 3):.1f} / "
            f"{memory.total / (1024 ** 3):.1f} GB)",
            f"Network: ↓{fmt_speed(self.download_bps)}  "
            f"↑{fmt_speed(self.upload_bps)}",
        ]

    def tick(self):
        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        now = psutil.net_io_counters()
        t = time.time()
        dt = max(t - self._last_t, 0.001)
        down = (now.bytes_recv - self._last.bytes_recv) / dt
        self.download_bps = down
        self.upload_bps = (now.bytes_sent - self._last.bytes_sent) / dt
        self._last, self._last_t = now, t
        return self.set_texts(
            body=f"{cpu:.0f}%  {ram:.0f}%  ↓{fmt_speed(down)}")


WIDGET_ID = 'system'
WIDGET_ORDER = 8

def make_card(dock):
    card = SystemCard()
    card.open_popup = lambda: dock.show_widget_details(
        card, "System", card.detail_lines())
    return card
