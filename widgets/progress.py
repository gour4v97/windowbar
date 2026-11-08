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

class ProgressCard(Card):
    """How far through the day / week / year -- rotates every tick."""

    INTERVAL = 5
    STICKY = True
    ORDER = ("day", "week", "year")

    def __init__(self):
        super().__init__("Day")
        self._i = 0

    def tick(self):
        p = extras.period_progress()
        key = self.ORDER[self._i % len(self.ORDER)]
        self._i += 1
        v = p[key]
        filled = int(round(v * 10))
        bar = "█" * filled + "░" * (10 - filled)
        return self.set_texts(key.upper(), f"{bar} {v * 100:.0f}%")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'progress'
WIDGET_ORDER = 3

def make_card(dock):
    return ProgressCard()
