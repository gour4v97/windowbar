"""Focus, stopwatch, todo, and screen time cards."""
import math
import time
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog
import extras
from core.formatting import fmt_hms
from widgets.base import Card, clip

class TodoCard(Card):
    INTERVAL = 2

    def __init__(self, cfg, save):
        super().__init__("Todos")
        self.cfg = cfg
        self.save = save
        self.open_panel = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: open the list   Right-click: complete first")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.open_panel:
                self.open_panel()
            else:
                text, ok = QInputDialog.getText(self, "New todo", "Todo:")
                if ok and text.strip():
                    self.cfg["todos"].append({"t": text.strip(),
                                               "done": False})
                    self.save(self.cfg)
        elif e.button() == Qt.RightButton:
            for t in self.cfg["todos"]:
                if not t["done"]:
                    t["done"] = True
                    self.save(self.cfg)
                    break

    def contextMenuEvent(self, e):
        e.accept()

    def tick(self):
        todos = self.cfg["todos"]
        open_ = [t["t"] for t in todos if not t["done"]]
        return self.set_texts(
            f"TODOS ({len(open_)})",
            clip(open_[0], 24) if open_ else
            ("All done" if todos else "All clear"))

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'todos'
WIDGET_ORDER = 26

def make_card(dock):
    return dock._todo_card()
