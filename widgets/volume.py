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

class VolumeCard(Card):
    INTERVAL = 2
    STICKY = True

    def __init__(self):
        super().__init__("Volume")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: mute / unmute   Scroll: volume")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            v = winapi.get_volume()
            if v:
                winapi.set_mute(not v[1])
            self.tick()

    def wheelEvent(self, e):
        v = winapi.get_volume()
        if v:
            step = 0.05 if e.angleDelta().y() > 0 else -0.05
            winapi.set_volume(v[0] + step)
        self.tick()

    def tick(self):
        v = winapi.get_volume()
        if v is None:
            return self.set_texts(body="No device")
        level, muted = v
        return self.set_texts(body="Muted" if muted else f"{level * 100:.0f}%")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'volume'
WIDGET_ORDER = 13

def make_card(dock):
    return VolumeCard()
