"""Opt-in, reversible BSP window tiling for Windows."""
import ctypes
import re
import sys

from PySide6.QtCore import QObject, QTimer

import winapi
from wm.layouts import bsp_layout, columns_layout, master_stack_layout


class TilingManager(QObject):
    def __init__(self, tracker, gap=12, padding=16, workspace_layouts=None,
                 floating_apps=(), floating_rules=None, layout="bsp",
                 on_change=None,
                 parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.gap, self.padding = int(gap), int(padding)
        self.layout = layout if layout in ("bsp", "columns", "stack") else "bsp"
        self.workspace_layouts = (workspace_layouts
                                  if isinstance(workspace_layouts, dict) else {})
        if isinstance(floating_apps, str):
            floating_apps = re.split(r"[,;\r\n]+", floating_apps)
        self.floating_apps = {str(name).strip().lower() for name in floating_apps
                              if str(name).strip()}
        self.set_floating_rules(floating_rules or {}, notify=False)
        self.on_change = on_change
        self._original = {}
        self._orders = {}
        self._floating_overrides = {}
        self._cached_workspace_id = "default"
        self._workspace_checked_at = 0.0
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(180)
        self._layout_timer.timeout.connect(self.apply_layout)
        self.tracker.windows_changed.connect(self.schedule_layout)
        self.tracker.foreground_changed.connect(self._foreground_changed)
        self.schedule_layout()

    def schedule_layout(self, *_):
        self._layout_timer.start()

    def _foreground_changed(self, *_):
        # A virtual desktop switch can keep a shared/pinned window foregrounded
        # while the visible window list itself stays unchanged.
        self._workspace_checked_at = 0.0
        self.schedule_layout()

    def apply_layout(self):
        if sys.platform != "win32":
            return
        workspace = self._workspace_id()
        candidates = {}
        for hwnd, _title in self.tracker.windows:
            hwnd = int(hwnd)
            if not winapi.IS_WIN or not winapi.is_window(hwnd):
                continue
            if self._is_floating(hwnd) or winapi.window_is_minimized(hwnd):
                continue
            rect = winapi.window_rect(hwnd)
            if rect and rect[2] > 0 and rect[3] > 0:
                area = winapi.window_work_area(hwnd)
                if not area:
                    continue
                self._original.setdefault(hwnd, winapi.window_state(hwnd))
                candidates.setdefault(area, []).append(hwnd)
        self._floating_overrides = {
            hwnd: value for hwnd, value in self._floating_overrides.items()
            if winapi.is_window(hwnd)}
        self._original = {hwnd: state for hwnd, state in self._original.items()
                          if winapi.is_window(hwnd)}
        for key in list(self._orders):
            if key[0] == workspace and key[1] not in candidates:
                self._orders.pop(key, None)
        for area, hwnds in candidates.items():
            key = (workspace, area)
            state = self.workspace_layouts.get(workspace)
            if not isinstance(state, dict):
                state = self.workspace_layouts[workspace] = {}
            area_key = self._area_key(area)
            orders = state.get("order")
            if not isinstance(orders, dict):
                orders = state["order"] = {}
            saved_order = orders.get(area_key, [])
            if not isinstance(saved_order, list):
                saved_order = []
            order = self._orders.setdefault(key, [])
            order[:] = [hwnd for hwnd in order if hwnd in hwnds]
            if not order and saved_order:
                remaining = list(hwnds)
                for app_name in saved_order:
                    match = next((hwnd for hwnd in remaining
                                  if winapi.window_process_name(hwnd) == app_name), None)
                    if match is not None:
                        order.append(match)
                        remaining.remove(match)
                order.extend(remaining)
            order.extend(hwnd for hwnd in hwnds if hwnd not in order)
            ratios = state.get("ratios")
            if not isinstance(ratios, dict):
                ratios = state["ratios"] = {}
            try:
                ratio = float(ratios.get(area_key, 0.5))
            except (TypeError, ValueError):
                ratio = 0.5
            layout_fn = {"bsp": bsp_layout, "columns": columns_layout,
                         "stack": master_stack_layout}[self.layout]
            for hwnd, rect in zip(order, layout_fn(
                    area, len(order), self.gap, self.padding, ratio=ratio)):
                winapi.move_window_rect(hwnd, rect)
            names = [winapi.window_process_name(hwnd) for hwnd in order]
            names = [name for name in names if name]
            if names and orders.get(area_key) != names:
                orders[area_key] = names
                self._changed()

    def focus_next(self):
        workspace = self._workspace_id()
        windows = self._ordered_windows(workspace)
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
        order = self._orders.get((self._workspace_id(), area), [])
        if current not in order or len(order) < 2:
            return
        index = order.index(current)
        other = (index + 1) % len(order)
        order[index], order[other] = order[other], order[index]
        self._save_order(area, order)
        self.schedule_layout()

    def resize_focused(self, delta):
        current = int(self.tracker.foreground_hwnd or 0)
        area = winapi.window_work_area(current)
        workspace = self._workspace_id()
        order = self._orders.get((workspace, area), [])
        if current not in order or len(order) < 2:
            return
        state = self.workspace_layouts.get(workspace)
        if not isinstance(state, dict):
            state = self.workspace_layouts[workspace] = {}
        area_key = self._area_key(area)
        ratios = state.get("ratios")
        if not isinstance(ratios, dict):
            ratios = state["ratios"] = {}
        try:
            ratio = float(ratios.get(area_key, 0.5))
        except (TypeError, ValueError):
            ratio = 0.5
        left_count = (len(order) + 1) // 2
        ratio += float(delta) if order.index(current) < left_count else -float(delta)
        ratios[area_key] = min(0.8, max(0.2, ratio))
        self._changed()
        self.schedule_layout()

    def toggle_floating(self):
        current = int(self.tracker.foreground_hwnd or 0)
        if not current or current not in {int(hwnd) for hwnd, _ in self.tracker.windows}:
            return
        self._original.setdefault(current, winapi.window_state(current))
        self._floating_overrides[current] = not self._is_floating(current)
        self._changed()
        state = self._original.get(current)
        if self._is_floating(current) and state:
            winapi.restore_window_state(current, state)
        self.schedule_layout()

    def move_focused_workspace(self, direction):
        current = int(self.tracker.foreground_hwnd or 0)
        if (not current or current not in
                {int(hwnd) for hwnd, _ in self.tracker.windows}):
            return False
        try:
            from native import vdesktop
            desktops = vdesktop.desktops()
            active = vdesktop.current()
            if not desktops or active is None:
                return False
            index = next(i for i, desktop in enumerate(desktops)
                         if str(desktop.id) == str(active.id))
            if len(desktops) < 2:
                return False
            target = desktops[(index + (1 if direction > 0 else -1))
                              % len(desktops)]
            return bool(vdesktop.move_window(current, target))
        except Exception:
            return False

    def _ordered_windows(self, workspace):
        return [hwnd for (key, _area), order in self._orders.items()
                if key == workspace for hwnd in order if winapi.is_window(hwnd)]

    def _is_floating(self, hwnd):
        if hwnd in self._floating_overrides:
            return self._floating_overrides[hwnd]
        exe = winapi.window_process_name(hwnd)
        if exe in self.floating_apps or exe in self.floating_rules["executables"]:
            return True
        klass = winapi.window_class_name(hwnd)
        if klass in self.floating_rules["classes"]:
            return True
        patterns = self.floating_rules["title_regex"]
        if patterns:
            title = winapi.window_title(hwnd)
            return any(pattern.search(title) for pattern in patterns)
        return False

    def set_floating_apps(self, names):
        self.floating_apps = {str(name).strip().lower() for name in names
                              if str(name).strip()}
        self._changed()
        self.schedule_layout()

    def set_floating_rules(self, rules, notify=True):
        rules = rules if isinstance(rules, dict) else {}
        def values(key):
            raw = rules.get(key, [])
            if isinstance(raw, str):
                return re.split(r"[,;\r\n]+", raw) if key != "title_regex" else [raw]
            return raw if isinstance(raw, (list, tuple, set)) else []
        patterns, invalid = [], []
        for value in values("title_regex"):
            try:
                patterns.append(re.compile(str(value), re.IGNORECASE))
            except re.error:
                invalid.append(str(value))
        self.floating_rules = {
            "executables": {str(value).strip().lower()
                            for value in values("executables")
                            if str(value).strip()},
            "classes": {str(value).strip().lower()
                        for value in values("classes")
                        if str(value).strip()},
            "title_regex": patterns,
        }
        self.invalid_title_patterns = invalid
        if notify:
            self._changed()
            self.schedule_layout()

    def _workspace_id(self):
        import time
        if time.monotonic() - self._workspace_checked_at < 1.0:
            return self._cached_workspace_id
        self._workspace_checked_at = time.monotonic()
        self._cached_workspace_id = "default"
        try:
            from native import vdesktop
            current = vdesktop.current()
            if current is not None:
                self._cached_workspace_id = str(current.id)
        except Exception:
            pass
        return self._cached_workspace_id

    @staticmethod
    def _area_key(area):
        return ",".join(str(int(value)) for value in area)

    def _save_order(self, area, order):
        workspace = self._workspace_id()
        state = self.workspace_layouts.get(workspace)
        if not isinstance(state, dict):
            state = self.workspace_layouts[workspace] = {}
        names = [winapi.window_process_name(hwnd) for hwnd in order]
        orders = state.get("order")
        if not isinstance(orders, dict):
            orders = state["order"] = {}
        orders[self._area_key(area)] = [
            name for name in names if name]
        self._changed()

    def _changed(self):
        if self.on_change:
            self.on_change()

    def release_all(self):
        self._layout_timer.stop()
        for hwnd, state in list(self._original.items()):
            if state:
                winapi.restore_window_state(hwnd, state)
        self._original.clear()
        self._orders.clear()
        self._floating_overrides.clear()


class EmergencyReleaseHotkey:
    """Global WM controls with Ctrl+Alt+Esc as the required safe release."""
    HOTKEYS = {0xB19: (0x1B, "release", 0x0003),
               0xB1A: (0x4A, "focus", 0x0003),
               0xB1B: (0x4B, "swap", 0x0003),
               0xB1C: (0x46, "floating", 0x0003),
               0xB1D: (0x48, "resize_smaller", 0x0003),
               0xB1E: (0x4C, "resize_larger", 0x0003),
               0xB1F: (0x25, "move_previous", 0x0007),
               0xB20: (0x27, "move_next", 0x0007)}
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
        self.registration_errors = {}
        self._actions = dict(callbacks)
        type(self)._actions = self._actions
        if winapi.IS_WIN:
            for hotkey_id, (vk, action_name, modifiers) in self.HOTKEYS.items():
                callback = callbacks.get(action_name)
                if not callback:
                    continue
                try:
                    ok = ctypes.windll.user32.RegisterHotKey(
                        None, hotkey_id, modifiers | 0x4000, vk)
                except Exception:
                    ok = False
                if ok:
                    self.registered_ids.add(hotkey_id)
                elif hotkey_id == 0xB19:
                    self.registration_errors[action_name] = int(
                        ctypes.windll.kernel32.GetLastError())
                    break
                else:
                    self.registration_errors[action_name] = int(
                        ctypes.windll.kernel32.GetLastError())
        self.registered = 0xB19 in self.registered_ids
        self.unavailable = [action for hotkey_id, (_vk, action, _mods)
                            in self.HOTKEYS.items()
                            if callbacks.get(action) and
                            hotkey_id not in self.registered_ids]

    def close(self):
        for hotkey_id in self.registered_ids:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
            except Exception:
                pass
        self.registered_ids.clear()
        self.registered = False
