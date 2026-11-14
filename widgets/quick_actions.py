"""Quick-actions card."""
import os
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QMessageBox,
                               QPushButton, QMenu)
import winapi

class QuickCard(QFrame):
    """Lock, dark/light theme, and empty Recycle Bin."""

    INTERVAL = 10

    def __init__(self, parent_widget):
        super().__init__()
        self.setObjectName("card")
        self.parent_widget = parent_widget
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self.theme_btn = QPushButton()
        for text, fn in [("Lock", winapi.lock_screen),
                         ("Theme", self.toggle_theme),
                         ("Empty bin", self.empty_bin),
                         ("Open…", self.open_path)]:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            if text == "Theme":
                self.theme_btn = b
            b.clicked.connect(fn)
            lay.addWidget(b)
        power = QPushButton(tr("Power"))
        power.setCursor(Qt.PointingHandCursor)
        power.clicked.connect(self.power_menu)
        lay.addWidget(power)
        self.tick()

    def toggle_theme(self):
        try:
            winapi.set_dark_mode(not winapi.is_dark_mode())
        except Exception:
            pass
        self.tick()

    def power_menu(self):
        m = QMenu(self)
        for label, action in [("Lock", "lock"), ("Sleep", "sleep"),
                              ("Sign out", "signout")]:
            a = QAction(label, self)
            a.triggered.connect(
                lambda _=False, act=action: winapi.power_action(act))
            m.addAction(a)
        m.addSeparator()
        for label, action in [("Restart…", "restart"),
                              ("Shut down…", "shutdown")]:
            a = QAction(label, self)
            a.triggered.connect(
                lambda _=False, act=action, lab=label: self._confirm_power(
                    lab, act))
            m.addAction(a)
        m.exec(self.mapToGlobal(QPoint(0, 0)))

    def _confirm_power(self, label, action):
        verb = "Restart" if action == "restart" else "Shut down"
        if QMessageBox.question(self, verb, f"{verb} the PC now?"
                                ) == QMessageBox.Yes:
            winapi.power_action(action)

    def open_path(self):
        text, ok = QInputDialog.getText(
            self, "Open", "Folder or file path (e.g. D:\\work, %USERPROFILE%):")
        if ok and text.strip():
            try:
                os.startfile(os.path.expandvars(text.strip().strip('"')))
            except Exception:
                pass

    def empty_bin(self):
        if QMessageBox.question(self, "Empty Recycle Bin",
                                "Permanently delete everything in the Recycle Bin?"
                                ) == QMessageBox.Yes:
            winapi.empty_recycle_bin()

    def tick(self):
        try:
            dark = winapi.is_dark_mode()
            text = "Light" if dark else "Dark"
            if text != self.theme_btn.text():
                self.theme_btn.setText(text)
                return True
        except Exception:
            pass
        return False

from core.i18n import tr

WIDGET_ID = 'quick'
WIDGET_ORDER = 16

def make_card(dock):
    return QuickCard(dock)
