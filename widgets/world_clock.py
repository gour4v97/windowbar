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

class WorldClockCard(Card):
    INTERVAL = 5
    STICKY = True

    def __init__(self, zones):
        super().__init__("World")
        self.zones = zones

    def tick(self):
        from zoneinfo import ZoneInfo
        parts = []
        for z in self.zones[:3]:
            try:
                t = datetime.now(ZoneInfo(z))
            except Exception:
                continue
            label = z.split("/")[-1].replace("_", " ")[:5].upper()
            parts.append(f"{label} {t.strftime('%H:%M')}")
        return self.set_texts(
            body=" · ".join(parts) if parts else "Bad time zone")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'world'
WIDGET_ORDER = 2

def make_card(dock):
    return WorldClockCard(dock.cfg["world_zones"])
