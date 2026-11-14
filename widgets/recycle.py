"""Recycle Bin card."""
from PySide6.QtCore import Qt
from widgets.base import Card
from widgets.system import QuickCard

class RecycleCard(Card):
    INTERVAL = 30

    def __init__(self, poll):
        super().__init__("Recycle Bin")
        self.poll = poll
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to empty the Recycle Bin")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            QuickCard.empty_bin(self)

    def tick(self):
        n = self.poll.value
        return self.set_texts(
            body="—" if n is None else f"{n} item{'s' if n != 1 else ''}")


WIDGET_ID = 'recycle'
WIDGET_ORDER = 17

def make_card(dock):
    return RecycleCard(dock.poll("recycle"))
