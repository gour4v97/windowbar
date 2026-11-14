"""Keyboard-driven window switcher with an isolated native hook thread."""

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QVBoxLayout,
)

import winapi
from native.keyboard_hook import LowLevelKeyboardHook


class SwitcherDialog(QDialog):
    """Small switcher overlay; window enumeration and capture stay on UI side."""

    def __init__(self, parent, windows, current_hwnd):
        super().__init__(parent)
        self.setWindowTitle("Windows Bar — Switch windows")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.resize(620, 390)
        self._windows = list(windows)
        self._frames = {}

        root = QVBoxLayout(self)
        title = QLabel("Switch windows")
        title.setObjectName("cardtitle")
        root.addWidget(title)
        body = QHBoxLayout()
        self.listing = QListWidget()
        self.listing.setMinimumWidth(240)
        self.preview = QLabel("Choose a window")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(320, 180)
        self.preview.setObjectName("card")
        body.addWidget(self.listing, 1)
        body.addWidget(self.preview, 2)
        root.addLayout(body, 1)
        hint = QLabel("Alt+Tab / Alt+Shift+Tab · arrows · Enter to switch · Esc to cancel")
        hint.setObjectName("cardbody")
        root.addWidget(hint)

        for hwnd, caption in self._windows:
            item = QListWidgetItem(caption)
            item.setData(Qt.UserRole, hwnd)
            self.listing.addItem(item)
        self.listing.itemDoubleClicked.connect(lambda _item: self.accept())
        self.listing.currentRowChanged.connect(self._preview_row)
        row = next((i for i, (hwnd, _title) in enumerate(self._windows)
                    if hwnd == current_hwnd), 0)
        if self.listing.count():
            self.listing.setCurrentRow(row)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            self.move(area.x() + (area.width() - self.width()) // 2,
                      area.y() + (area.height() - self.height()) // 2)

    def _preview_row(self, row):
        if not 0 <= row < len(self._windows):
            return
        hwnd = self._windows[row][0]
        self.preview.setText("Loading preview…")
        # Capture after the overlay is visible so the first paint is responsive.
        QTimer.singleShot(35, lambda: self._capture(hwnd))

    def _capture(self, hwnd):
        if not self.isVisible() or self.listing.currentItem() is None:
            return
        if self.listing.currentItem().data(Qt.UserRole) != hwnd:
            return
        pixmap = self._frames.get(hwnd)
        if pixmap is None:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                self.preview.setText("Preview unavailable")
                return
            pixmap = screen.grabWindow(int(hwnd))
            if pixmap.isNull():
                self.preview.setText("Preview unavailable")
                return
            self._frames[hwnd] = pixmap
        self.preview.setText("")
        self.preview.setPixmap(pixmap.scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def step(self, direction):
        count = self.listing.count()
        if count:
            self.listing.setCurrentRow((self.listing.currentRow() + direction) % count)

    def select_edge(self, last=False):
        if self.listing.count():
            self.listing.setCurrentRow(self.listing.count() - 1 if last else 0)

    @property
    def selected_hwnd(self):
        item = self.listing.currentItem()
        return int(item.data(Qt.UserRole)) if item else 0


class AltTabController(QObject):
    """Own the hook and marshal its actions onto the Qt event thread."""

    _action_received = Signal(object)

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.dialog = None
        self.original_hwnd = 0
        self.hook = LowLevelKeyboardHook(self._action_received.emit)
        self._action_received.connect(self._handle_action)

    def start(self):
        return self.hook.start()

    def stop(self):
        self.hook.stop()
        self._cancel()

    def _handle_action(self, action):
        name, direction = action
        if name == "start":
            self._open(direction)
        elif name == "step" and self.dialog is not None:
            self.dialog.step(direction)
        elif name == "first" and self.dialog is not None:
            self.dialog.select_edge()
        elif name == "last" and self.dialog is not None:
            self.dialog.select_edge(last=True)
        elif name == "commit":
            self._commit()
        elif name == "cancel":
            self._cancel()

    def _open(self, direction):
        self._cancel()
        self.original_hwnd = winapi.foreground_hwnd()
        skip = [self.dock.appbar.hwnd, int(self.dock.winId())]
        windows = winapi.list_open_windows(64, exclude=skip)
        windows = [(hwnd, title) for hwnd, title in windows
                   if hwnd != self.original_hwnd or len(windows) > 1]
        if not windows:
            return
        self.dialog = SwitcherDialog(self.dock, windows, self.original_hwnd)
        self.dialog.step(direction)
        self.dialog.finished.connect(self._dialog_finished)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _dialog_finished(self, _result):
        dialog, self.dialog = self.dialog, None
        if dialog is not None:
            hwnd = (dialog.selected_hwnd if _result == QDialog.Accepted
                    else self.original_hwnd)
            dialog.deleteLater()
            if hwnd:
                winapi.focus_window(hwnd)
            self.original_hwnd = 0

    def _commit(self):
        if self.dialog is not None:
            self.dialog.done(QDialog.Accepted)
        else:
            self.original_hwnd = 0

    def _cancel(self):
        if self.dialog is not None:
            self.dialog.reject()
        elif self.original_hwnd:
            hwnd, self.original_hwnd = self.original_hwnd, 0
            winapi.focus_window(hwnd)
