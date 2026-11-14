"""Downloads card."""
import os
from pathlib import Path
from PySide6.QtCore import Qt
from widgets.base import Card, clip

class DownloadsCard(Card):
    INTERVAL = 5

    def __init__(self, poll, name="Downloads", folder=None):
        super().__init__(name)
        self.poll = poll
        self.name = name
        self.folder = folder or (Path.home() / "Downloads")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Click to open {name}")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            os.startfile(str(self.folder))

    def tick(self):
        if self.poll.value is None:
            return self.set_texts(body=self.poll.error or "Loading…")
        recent, newest = self.poll.value
        return self.set_texts(f"{self.name.upper()} · {recent} TODAY",
                              clip(newest or "Empty", 26))


WIDGET_ID = 'downloads'
WIDGET_ORDER = 5

def make_card(dock):
    return DownloadsCard(dock.poll("downloads"))
