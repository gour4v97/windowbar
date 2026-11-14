"""Storage card."""
import extras
from widgets.base import Card

class StorageCard(Card):
    INTERVAL = 10

    def __init__(self, poll):
        super().__init__("Storage")
        self.poll = poll

    def tick(self):
        if self.poll.value is None:
            return self.set_texts(body=self.poll.error or "Loading…")
        pct, free, total = self.poll.value
        self.setToolTip(f"{extras.fmt_bytes(total - free)} of "
                        f"{extras.fmt_bytes(total)} used")
        return self.set_texts(f"DISK · {pct:.0f}% USED",
                              f"{extras.fmt_bytes(free)} free")


WIDGET_ID = 'storage'
WIDGET_ORDER = 10

def make_card(dock):
    return StorageCard(dock.poll("storage"))
