"""Top toolbar window used by the optional split shell layout."""
from PySide6.QtCore import QFileInfo, QSize, Qt, QTimer
from PySide6.QtWidgets import QFileIconProvider, QHBoxLayout, QLabel, QPushButton, QWidget

import winapi
from core.app_config import MARGIN
from native import vdesktop
from core.i18n import tr
from ui.popup import paint_shell_panel


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
        self.row.setContentsMargins(16, 8, 16, 8)
        self.row.setSpacing(8)
        self._cards = []
        self._active_hwnd = 0
        self._icon_cache = {}
        self.active_icon = QLabel()
        self.active_icon.setFixedSize(18, 18)
        self.active_icon.setScaledContents(True)
        self.row.addWidget(self.active_icon)
        self.active_window = QLabel()
        self.active_window.setObjectName("activeWindow")
        self.active_window.setMinimumWidth(120)
        self.active_window.setMaximumWidth(300)
        self.active_window.setToolTip(tr("Active window"))
        self.row.addWidget(self.active_window)
        self._win_btns = [
            self._add_window_button("—", tr("Minimize"), "minimize"),
            self._add_window_button("□", tr("Maximize"), "maximize"),
            self._add_window_button("✕", tr("Close window"), "close"),
        ]
        self._add_desktop_button("‹", "Previous desktop", "previous")
        self._add_desktop_button("›", "Next desktop", "next")
        self._add_desktop_button("+", "Create desktop", "new")
        self._add_desktop_button("▦", tr("Open Windows Bar workspace viewer"),
                                 "viewer")
        self._window_timer = QTimer(self)
        self._window_timer.timeout.connect(self._refresh_active_window)
        self._window_timer.start(1000)
        self._refresh_active_window()

    def _add_window_button(self, label, tip, action):
        button = QPushButton(label)
        button.setObjectName("toolbarButton")
        button.setToolTip(tip)
        button.setFixedSize(28, 28)
        button.clicked.connect(lambda _checked=False, name=action:
                               self._window_action(name))
        self.row.addWidget(button)
        return button

    def _window_action(self, action):
        hwnd = self._active_hwnd
        if not hwnd:
            return
        if action == "minimize":
            winapi.minimize_window(hwnd)
        elif action == "maximize":
            winapi.toggle_maximize_window(hwnd)
        elif action == "close":
            winapi.close_window(hwnd)

    def _add_desktop_button(self, label, tip, action):
        button = QPushButton(label)
        button.setObjectName("toolbarButton")
        button.setToolTip(tip)
        button.setFixedSize(34, 34)
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
        hwnd = winapi.foreground_hwnd()
        own = {int(self.winId()), int(self.dock.winId())}
        if hwnd and hwnd not in own:
            self._active_hwnd = hwnd
        elif hwnd and hwnd in own:
            hwnd = self._active_hwnd
        else:
            self._active_hwnd = 0
        title = winapi.window_title(self._active_hwnd) if self._active_hwnd else ""
        self.active_window.setText(title or "Desktop")
        self.active_window.setToolTip(title or "Active window")
        path = winapi.window_process_path(self._active_hwnd) if self._active_hwnd else ""
        if path:
            if path not in self._icon_cache:
                icon = QFileIconProvider().icon(QFileInfo(path))
                self._icon_cache[path] = icon.pixmap(QSize(18, 18)) if not icon.isNull() else None
            pix = self._icon_cache[path]
            if pix is not None:
                self.active_icon.setPixmap(pix)
                self.active_icon.show()
            else:
                self.active_icon.clear()
                self.active_icon.hide()
        else:
            self.active_icon.clear()
            self.active_icon.hide()
        enabled = bool(self._active_hwnd)
        for btn in self._win_btns:
            btn.setEnabled(enabled)

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

    def paintEvent(self, event):
        paint_shell_panel(self, self.dock.tokens, self.dock.glass_active)
        super().paintEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.appbar.hwnd = int(self.winId())
        if self.dock.cfg.get("glass") and self.dock.tokens.get("blur", 0):
            winapi.enable_glass(self.appbar.hwnd)
        self.place()

    def shutdown(self):
        self.appbar.remove()
        winapi.disable_glass(self.appbar.hwnd)
        self.close()

