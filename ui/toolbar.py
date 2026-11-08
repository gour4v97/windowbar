"""Top toolbar window used by the optional split shell layout."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

import winapi
from core.app_config import MARGIN


class Toolbar(QWidget):
    """Hosts the enabled information cards above the pinned-app dock."""

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.appbar = winapi.AppBar()
        self.appbar.hwnd = int(self.winId())
        self._res_key = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(dock.styleSheet())
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(14, 8, 14, 8)
        self.row.setSpacing(10)

    def replace_cards(self, cards):
        while self.row.count():
            self.row.takeAt(0)
        for card in cards:
            self.row.addWidget(card)
        self.adjustSize()
        self.place()

    def place(self):
        screen = self.screen() or self.dock.screen()
        if screen is None:
            return
        dpr = screen.devicePixelRatio()
        full = screen.geometry()
        h = self.sizeHint().height()
        y = None
        if self.dock.cfg.get("reserve_space") and winapi.IS_WIN:
            rect = (int(full.x() * dpr), int(full.y() * dpr),
                    int((full.x() + full.width()) * dpr),
                    int((full.y() + full.height()) * dpr))
            key = (True, rect, int((h + 2 * MARGIN) * dpr))
            if key != self._res_key or not self.appbar.registered:
                reserved = self.appbar.reserve(*key)
                self._res_key = key
            else:
                reserved = None
            if reserved:
                y = reserved[1] / dpr + MARGIN
        else:
            self.appbar.remove()
            self._res_key = None
        if y is None:
            avail = screen.availableGeometry()
            y = avail.y() + MARGIN
        self.resize(self.sizeHint())
        self.move(int(full.x() + (full.width() - self.width()) // 2), int(y))

    def showEvent(self, event):
        super().showEvent(event)
        self.appbar.hwnd = int(self.winId())
        self.place()

    def shutdown(self):
        self.appbar.remove()
        self.close()

