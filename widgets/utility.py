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
class PollCard(Card):
    """Shows the value of a background Poll, or its error."""

    INTERVAL = 5

    def __init__(self, title, poll, on_click=None, hint=""):
        super().__init__(title)
        self.poll, self.on_click, self.hint = poll, on_click, hint
        if on_click:
            self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.on_click:
            self.on_click()

    def tick(self):
        if self.poll.value is not None:
            text = clip(str(self.poll.value), 30)
        elif self.poll.error:
            text = clip(self.poll.error, 30)
        else:
            text = "Loading…"
        return self.set_texts(body=text)


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


class TimerCard(Card):
    """Plain countdown timer (the Focus timer's simpler sibling)."""

    ALWAYS = True
    STICKY = True

    def __init__(self, cfg, quiet=None, save=None):
        super().__init__("Timer")
        self.cfg = cfg
        self.save = save or (lambda _cfg: None)
        self.quiet = quiet or (lambda: False)
        self.remaining = cfg["timer_minutes"] * 60.0
        self.running = False
        self._t = time.monotonic()
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: start/pause   Double-click: set minutes")

    def _advance(self):
        now = time.monotonic()
        if self.running:
            self.remaining -= now - self._t
        self._t = now

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._advance()
            self.running = not self.running

    def mouseDoubleClickEvent(self, e):
        val, ok = QInputDialog.getInt(self, "Timer", "Minutes:",
                                      int(self.cfg["timer_minutes"]), 1, 480)
        if ok:
            self.cfg["timer_minutes"] = val
            self.save(self.cfg)
            self.running = False
            self.remaining = val * 60.0

    def tick(self):
        self._advance()
        if self.running and self.remaining <= 0:
            self.running = False
            self.remaining = self.cfg["timer_minutes"] * 60.0
            if not self.quiet():
                QApplication.beep()
        return self.set_texts(
            "TIMER" + (" ▶" if self.running else " ❚❚"),
            fmt_hms(math.ceil(self.remaining)))


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


class NetworkCard(Card):
    INTERVAL = 1
    STICKY = True

    def __init__(self, info_poll):
        super().__init__("Network")
        self.info = info_poll
        self._last = psutil.net_io_counters()
        self._last_t = time.time()

    def tick(self):
        now = psutil.net_io_counters()
        t = time.time()
        dt = max(t - self._last_t, 0.001)
        down = (now.bytes_recv - self._last.bytes_recv) / dt
        up = (now.bytes_sent - self._last.bytes_sent) / dt
        self._last, self._last_t = now, t
        name, ip = self.info.value or ("", "")
        title = (name or "NETWORK").upper()
        if ip:
            title += " · " + ip
        return self.set_texts(
            title, f"↓{fmt_speed(down)} ↑{fmt_speed(up)}")


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

