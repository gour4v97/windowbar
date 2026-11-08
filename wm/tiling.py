"""Opt-in, reversible BSP window tiling for Windows."""
import ctypes
import sys

from PySide6.QtCore import QObject, QTimer

import winapi
from wm.layouts import bsp_layout


class TilingManager(QObject):
    def __init__(self, tracker, gap=12, padding=16, parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.gap, self.padding = int(gap), int(padding)
        self._original = {}
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(180)
        self._layout_timer.timeout.connect(self.apply_layout)
        self.tracker.windows_changed.connect(self.schedule_layout)
        self.schedule_layout()

    def schedule_layout(self, *_):
        self._layout_timer.start()

    def apply_layout(self):
        if sys.platform != "win32":
            return
        candidates = {}
        for hwnd, _title in self.tracker.windows:
            hwnd = int(hwnd)
            if not winapi.IS_WIN:
                continue
            if winapi.window_is_minimized(hwnd):
                continue
            rect = winapi.window_rect(hwnd)
            if rect and rect[2] > 0 and rect[3] > 0:
                area = winapi.window_work_area(hwnd)
                if not area:
                    continue
                candidates.setdefault(area, []).append(hwnd)
                self._original.setdefault(hwnd, winapi.window_state(hwnd))
        for area, hwnds in candidates.items():
            for hwnd, rect in zip(hwnds, bsp_layout(
                    area, len(hwnds), self.gap, self.padding)):
                winapi.move_window_rect(hwnd, rect)

    def release_all(self):
        self._layout_timer.stop()
        for hwnd, state in list(self._original.items()):
            if state:
                winapi.restore_window_state(hwnd, state)
        self._original.clear()


class EmergencyReleaseHotkey:
    """Ctrl+Alt+Esc global hotkey used to restore managed window positions."""
    ID = 0xB19
    WM_HOTKEY = 0x0312

    def __init__(self, callback):
        from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
        from ctypes import wintypes

        class Filter(QAbstractNativeEventFilter):
            def nativeEventFilter(inner_self, event_type, message):
                if event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
                    return False, 0
                try:
                    msg = wintypes.MSG.from_address(int(message))
                    if msg.message == EmergencyReleaseHotkey.WM_HOTKEY and msg.wParam == EmergencyReleaseHotkey.ID:
                        QTimer.singleShot(0, callback)
                        return True, 0
                except Exception:
                    pass
                return False, 0

        self.filter = Filter()
        try:
            self.registered = bool(
                winapi.IS_WIN and ctypes.windll.user32.RegisterHotKey(
                    None, self.ID, 0x0002 | 0x0001 | 0x4000, 0x1B))
        except Exception:
            self.registered = False

    def close(self):
        if self.registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.ID)
            except Exception:
                pass
            self.registered = False
