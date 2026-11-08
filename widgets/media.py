"""System, battery, media, calendar, and quick action cards."""
from datetime import datetime
import os
import time
import psutil
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QMessageBox,
                               QPushButton, QMenu)
import winapi
from widgets.base import Card, clip
from core.formatting import fmt_speed, fmt_delta

class MediaCard(Card):
    INTERVAL = 2

    def __init__(self, media):
        super().__init__("Now playing")
        self.media = media
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: play / pause")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.media.toggle()

    def tick(self):
        m = self.media
        if not m.available:
            return self.set_texts("NOW PLAYING", "Media support not installed")
        if not m.has_session:
            return self.set_texts("NOW PLAYING", "Nothing playing")
        text = m.title + (f" — {m.artist}" if m.artist else "")
        return self.set_texts("NOW PLAYING " + ("▶" if m.playing else "❚❚"),
                              clip(text, 28))

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'media'
WIDGET_ORDER = 12

def make_card(dock):
    return MediaCard(dock.media)
