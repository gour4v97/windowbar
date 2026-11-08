"""Open-window, pinned-app, and Recycle Bin cards."""
import subprocess
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton
import winapi
from widgets.base import Card, clip
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

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'recycle'
WIDGET_ORDER = 17

def make_card(dock):
    return RecycleCard(dock.poll("recycle"))
