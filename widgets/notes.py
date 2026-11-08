"""Notes card widget."""

from PySide6.QtCore import Qt

from .base import Card, clip


class NotesCard(Card):
    id = "notes"
    name = "Notes"
    default_config = {"enabled": False}
    INTERVAL = 5

    def __init__(self, cfg):
        super().__init__("Notes")
        self.cfg = cfg
        self.open_panel = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: open notes")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.open_panel:
            self.open_panel()

    def tick(self):
        notes = self.cfg["notes_list"]
        current = notes[self.cfg["notes_current"]] if notes else ""
        first = (current.strip().splitlines() or [""])[0]
        count = len(notes)
        return self.set_texts(
            f"NOTES · {count}" if count > 1 else "NOTES",
            clip(first, 26) if first else "Click to write")

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'notes'
WIDGET_ORDER = 21

def make_card(dock):
    return dock._notes_card()
