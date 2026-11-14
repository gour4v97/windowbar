"""Script-output card."""
import subprocess
from PySide6.QtCore import Qt
from widgets.base import Card, clip

class ScriptCard(Card):

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


WIDGET_ID = 'script'
WIDGET_ORDER = 25

def make_card(dock):
    return ScriptCard(dock.poll("script"), dock.cfg)
