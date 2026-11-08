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

class SystemCard(Card):
    STICKY = True

    def __init__(self):
        super().__init__("CPU / RAM")
        self._last = psutil.net_io_counters()
        self._last_t = time.time()
        psutil.cpu_percent(None)

    def tick(self):
        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        now = psutil.net_io_counters()
        t = time.time()
        dt = max(t - self._last_t, 0.001)
        down = (now.bytes_recv - self._last.bytes_recv) / dt
        self._last, self._last_t = now, t
        return self.set_texts(
            body=f"{cpu:.0f}%  {ram:.0f}%  ↓{fmt_speed(down)}")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'system'
WIDGET_ORDER = 8

def make_card(dock):
    return SystemCard()
