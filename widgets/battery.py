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

class BatteryCard(Card):
    INTERVAL = 5
    STICKY = True

    def __init__(self):
        super().__init__("Battery")

    def tick(self):
        b = psutil.sensors_battery()
        if b is None:
            return self.set_texts(body="No battery")
        return self.set_texts(
            body=f"{b.percent:.0f}% {'⚡' if b.power_plugged else ''}")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'battery'
WIDGET_ORDER = 11

def make_card(dock):
    return BatteryCard()
