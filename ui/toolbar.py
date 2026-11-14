"""Top toolbar window used by the optional split shell layout."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

import winapi
from core.app_config import MARGIN
from native import vdesktop
from core.i18n import tr


class Toolbar(QWidget):

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.appbar = winapi.AppBar()
        self.appbar.hwnd = int(self.winId())
        self._res_key = self._res_rc = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(dock.styleSheet())
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(14, 8, 14, 8)
        self.row.setSpacing(10)
        self._cards = []
        self.active_window = QLabel()
        self.active_window.setMinimumWidth(100)
        self.active_window.setMaximumWidth(360)
        self.active_window.setToolTip(tr("Active window"))
        self.row.addWidget(self.active_window)
        self._add_desktop_button("‹", "Previous desktop", "previous")
        self._add_desktop_button("›", "Next desktop", "next")
        self._add_desktop_button("+", "Create desktop", "new")
        self._add_desktop_button("▦", "Open Windows Bar workspace viewer",
                                 "viewer")
        self._window_timer = QTimer(self)
        self._window_timer.timeout.connect(self._refresh_active_window)
        self._window_timer.start(1000)
        self._refresh_active_window()

    def _add_desktop_button(self, label, tip, action):
        button = QPushButton(label)
        button.setToolTip(tip)
        button.setFixedWidth(28)
        button.clicked.connect(lambda _checked=False, name=action:
                               self._workspace_action(name))
        self.row.addWidget(button)

    def _workspace_action(self, action):
        if action in ("previous", "next"):
            vdesktop.switch_relative(-1 if action == "previous" else 1)
        elif action == "new":
            vdesktop.create()
        elif action == "viewer":
            self.dock.open_workspaces()

    def _refresh_active_window(self):
        title = winapi.window_title()
        self.active_window.setText(title or "Desktop")
        self.active_window.setToolTip(title or "Active window")

    def replace_cards(self, cards):
        for card in self._cards:
            self.row.removeWidget(card)
        self._cards = list(cards)
        for card in cards:
            self.row.addWidget(card)
        self.adjustSize()
        self.place()

    def place(self):
        screen = (self.dock.target_screen or self.screen()
                  or self.dock.screen())
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
                self._res_rc = self.appbar.reserve(*key)
                self._res_key = key
            reserved = self._res_rc
            if reserved:
                y = reserved[1] / dpr + MARGIN
        else:
            self.appbar.remove()
            self._res_key = self._res_rc = None
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

