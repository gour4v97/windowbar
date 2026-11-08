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
        self._orders = {}
        self._floating = set()
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
            if hwnd in self._floating or winapi.window_is_minimized(hwnd):
                continue
            rect = winapi.window_rect(hwnd)
            if rect and rect[2] > 0 and rect[3] > 0:
                area = winapi.window_work_area(hwnd)
                if not area:
                    continue
                self._original.setdefault(hwnd, winapi.window_state(hwnd))
                candidates.setdefault(area, []).append(hwnd)
        for area, hwnds in candidates.items():
            order = self._orders.setdefault(area, [])
            order[:] = [hwnd for hwnd in order if hwnd in hwnds]
            order.extend(hwnd for hwnd in hwnds if hwnd not in order)
            for hwnd, rect in zip(order, bsp_layout(
                    area, len(order), self.gap, self.padding)):
                winapi.move_window_rect(hwnd, rect)

    def focus_next(self):
        windows = self._ordered_windows()
        if not windows:
            return
        current = int(self.tracker.foreground_hwnd or 0)
        try:
            index = windows.index(current)
        except ValueError:
            index = -1
        winapi.focus_window(windows[(index + 1) % len(windows)])

    def swap_focused(self):
        current = int(self.tracker.foreground_hwnd or 0)
        area = winapi.window_work_area(current)
        order = self._orders.get(area, [])
        if current not in order or len(order) < 2:
            return
        index = order.index(current)
        other = (index + 1) % len(order)
        order[index], order[other] = order[other], order[index]
        self.schedule_layout()

    def toggle_floating(self):
        current = int(self.tracker.foreground_hwnd or 0)
        if not current:
            return
        if current in self._floating:
            self._floating.remove(current)
            self.schedule_layout()
            return
        self._original.setdefault(current, winapi.window_state(current))
        self._floating.add(current)
        state = self._original.get(current)
        if state:
            winapi.restore_window_state(current, state)
        self.schedule_layout()

    def _ordered_windows(self):
        return [hwnd for order in self._orders.values() for hwnd in order]

    def release_all(self):
        self._layout_timer.stop()
        for hwnd, state in list(self._original.items()):
            if state:
                winapi.restore_window_state(hwnd, state)
        self._original.clear()
        self._orders.clear()
        self._floating.clear()


class EmergencyReleaseHotkey:
    """Global WM controls with Ctrl+Alt+Esc as the required safe release."""
    HOTKEYS = {0xB19: (0x1B, "release"), 0xB1A: (0x4A, "focus"),
               0xB1B: (0x4B, "swap"), 0xB1C: (0x46, "floating")}
    WM_HOTKEY = 0x0312

    def __init__(self, callbacks):
        from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
        from ctypes import wintypes

        class Filter(QAbstractNativeEventFilter):
            def nativeEventFilter(inner_self, event_type, message):
                if event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
                    return False, 0
                try:
                    msg = wintypes.MSG.from_address(int(message))
                    action = EmergencyReleaseHotkey._actions.get(msg.wParam)
                    if msg.message == EmergencyReleaseHotkey.WM_HOTKEY and action:
                        QTimer.singleShot(0, action)
                        return True, 0
                except Exception:
                    pass
                return False, 0

        self.filter = Filter()
        self.registered_ids = set()
        self.registered = False
        self._actions = dict(callbacks)
        type(self)._actions = self._actions
        if winapi.IS_WIN:
            for hotkey_id, (vk, action_name) in self.HOTKEYS.items():
                callback = callbacks.get(action_name)
                if not callback:
                    continue
                try:
                    ok = ctypes.windll.user32.RegisterHotKey(
                        None, hotkey_id, 0x0002 | 0x0001 | 0x4000, vk)
                except Exception:
                    ok = False
                if ok:
                    self.registered_ids.add(hotkey_id)
                elif hotkey_id == 0xB19:
                    break
        self.registered = 0xB19 in self.registered_ids

    def close(self):
        for hotkey_id in self.registered_ids:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
            except Exception:
                pass
        self.registered_ids.clear()
        self.registered = False
