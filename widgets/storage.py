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

class StorageCard(Card):
    INTERVAL = 10

    def __init__(self, poll):
        super().__init__("Storage")
        self.poll = poll

    def tick(self):
        if self.poll.value is None:
            return self.set_texts(body=self.poll.error or "Loading…")
        pct, free, total = self.poll.value
        self.setToolTip(f"{extras.fmt_bytes(total - free)} of "
                        f"{extras.fmt_bytes(total)} used")
        return self.set_texts(f"DISK · {pct:.0f}% USED",
                              f"{extras.fmt_bytes(free)} free")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'storage'
WIDGET_ORDER = 10

def make_card(dock):
    return StorageCard(dock.poll("storage"))
