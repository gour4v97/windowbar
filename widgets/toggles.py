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

class TogglesCard(QFrame):
    """Quick toggles: Wi-Fi, Bluetooth, airplane mode, keep awake, mute.
    Radio buttons only appear when the WinRT radios API is available."""

    INTERVAL = 4

    def __init__(self, radios, cfg, save):
        super().__init__()
        self.setObjectName("card")
        self.radios, self.cfg, self.save = radios, cfg, save
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self.btns = {}
        for key, label in [("wifi", "Wi-Fi"), ("bluetooth", "BT"),
                           ("airplane", "Plane"), ("awake", "Awake"),
                           ("mute", "Mute")]:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.toggle(k))
            lay.addWidget(b)
            self.btns[key] = b
        self.tick()

    def toggle(self, key):
        if key in ("wifi", "bluetooth"):
            cur = self.radios.states.get(key)
            if cur is not None:
                self.radios.set(key, not cur)
        elif key == "airplane":
            states = self.radios.states
            if states:
                # airplane on = every radio off, and back
                self.radios.set("airplane", not any(states.values()))
        elif key == "awake":
            on = not self.cfg.get("keep_awake", False)
            self.cfg["keep_awake"] = on
            self.save()
            winapi.set_keep_awake(on)
        elif key == "mute":
            v = winapi.get_volume()
            if v:
                winapi.set_mute(not v[1])
        QTimer.singleShot(600, self.tick)

    def _set_btn(self, key, text, active):
        b = self.btns[key]
        changed = False
        if b.text() != text:
            b.setText(text)
            changed = True
        prop = "true" if active else "false"
        if b.property("active") != prop:
            b.setProperty("active", prop)
            b.style().unpolish(b)
            b.style().polish(b)
            changed = True
        return changed

    def tick(self):
        changed = False
        states = self.radios.states if self.radios else {}
        for key, label in [("wifi", "Wi-Fi"), ("bluetooth", "BT")]:
            on = states.get(key)
            self.btns[key].setVisible(on is not None)
            if on is not None:
                changed = self._set_btn(
                    key, f"{label} {'On' if on else 'Off'}", on) or changed
        all_off = bool(states) and not any(states.values())
        self.btns["airplane"].setVisible(bool(states))
        if states:
            changed = self._set_btn(
                "airplane", "Plane On" if all_off else "Plane", all_off) \
                or changed
        awake = bool(self.cfg.get("keep_awake"))
        changed = self._set_btn(
            "awake", "Awake On" if awake else "Awake", awake) or changed
        v = winapi.get_volume()
        muted = bool(v and v[1])
        changed = self._set_btn(
            "mute", "Muted" if muted else "Mute", muted) or changed
        return changed

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'toggles'
WIDGET_ORDER = 14

def make_card(dock):
    return TogglesCard(dock.radios, dock.cfg, lambda: save_config(dock.cfg))
