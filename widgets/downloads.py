"""Small polling, system, and utility widget cards."""
from datetime import datetime
import math
import os
import subprocess
import time
from pathlib import Path
import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QInputDialog, QPushButton
import extras
import winapi
from core.formatting import fmt_hms, fmt_speed
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

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'downloads'
WIDGET_ORDER = 5

def make_card(dock):
    return DownloadsCard(dock.poll("downloads"))
