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

class ScriptCard(Card):
    """First line of your own command's output, big; second line small."""

    INTERVAL = 5

    def __init__(self, poll, cfg):
        super().__init__("Script")
        self.poll, self.cfg = poll, cfg
        if cfg.get("script_click_command"):
            self.setCursor(Qt.PointingHandCursor)
            self.setToolTip("Click to run the click command")

    def mousePressEvent(self, e):
        cmd = self.cfg.get("script_click_command", "")
        if e.button() == Qt.LeftButton and cmd:
            try:
                subprocess.Popen(cmd, shell=True)
            except Exception:
                pass

    def tick(self):
        if self.poll.value is None:
            return self.set_texts(
                "SCRIPT", self.poll.error or "Loading…")
        text = str(self.poll.value)
        lines = text.splitlines() or [""]
        if text != self.toolTip():
            self.setToolTip(text)
        return self.set_texts(
            clip(lines[1].upper(), 30) if len(lines) > 1 else "SCRIPT",
            clip(lines[0], 30))

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'script'
WIDGET_ORDER = 25

def make_card(dock):
    return ScriptCard(dock.poll("script"), dock.cfg)
