"""Qt-facing snapshot tracker fed by the native out-of-context WinEvent hook."""

from PySide6.QtCore import QObject, QTimer, Signal

import winapi
from native.window_events import WinEventHook


class WindowTracker(QObject):
    """Publish stable top-level window snapshots and foreground changes."""

    windows_changed = Signal(object)
    foreground_changed = Signal(int)
    _native_event = Signal(object)

    def __init__(self, parent=None, exclude_hwnds=()):
        super().__init__(parent)
        self._exclude_hwnds = tuple(int(hwnd) for hwnd in exclude_hwnds if hwnd)
        self._windows = []
        self._foreground = 0
        self._hook = WinEventHook(self._native_event.emit)
        self._native_event.connect(self._handle_event)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self.refresh)

    @property
    def windows(self):
        return list(self._windows)

    @property
    def foreground_hwnd(self):
        return self._foreground

    @property
    def error(self):
        return self._hook.error

    def start(self):
        if not self._hook.start():
            return False
        self.refresh()
        return True

    def stop(self):
        self._refresh_timer.stop()
        self._hook.stop()

    def refresh(self):
        current = winapi.list_open_windows(256, exclude=self._exclude_hwnds)
        if current != self._windows:
            self._windows = current
            self.windows_changed.emit(list(current))
        foreground = winapi.foreground_hwnd()
        if foreground != self._foreground:
            self._foreground = foreground
            self.foreground_changed.emit(foreground)

    def _handle_event(self, event):
        if not event:
            return
        if event[0] == "foreground":
            hwnd = event[1]
            if hwnd != self._foreground:
                self._foreground = hwnd
                self.foreground_changed.emit(hwnd)
        else:
            # Window create/destroy/show/hide/move bursts collapse into one
            # z-order snapshot on the Qt thread.
            self._refresh_timer.start()
