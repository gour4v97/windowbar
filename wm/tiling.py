"""Opt-in, reversible BSP window tiling for Windows."""
import ctypes
import sys

from PySide6.QtCore import QObject, QTimer

import winapi
from wm.layouts import (LAYOUT_LABELS, bsp_layout, columns_layout,
                        default_ratio, master_stack_layout, next_layout,
                        normalize_layout, resize_sign)
from wm.rules import FloatingRules, split_names
from wm.hotkeys import parse_hotkey_spec


class TilingManager(QObject):
    def __init__(self, tracker, gap=12, padding=16, workspace_layouts=None,
                 floating_apps=(), floating_rules=None, layout="bsp",
                 on_change=None,
                 parent=None):
        super().__init__(parent)
        self.tracker = tracker
        self.gap, self.padding = int(gap), int(padding)
        self.layout = normalize_layout(layout)
        self.workspace_layouts = (workspace_layouts
                                  if isinstance(workspace_layouts, dict) else {})
        self.floating_apps = set()
        self._rules = FloatingRules()
        self.floating_rules = {}
        self.invalid_title_patterns = []
        self._rule_config = {}
        self.set_floating_apps(floating_apps, notify=False)
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
            ratio = self._saved_ratio(ratios, area_key)
            layout_fn = {"bsp": bsp_layout, "columns": columns_layout,
                         "stack": master_stack_layout}[self.layout]
            for hwnd, rect in zip(order, layout_fn(
                    area, len(order), self.gap, self.padding, ratio=ratio)):
                winapi.move_window_visible_rect(hwnd, rect)
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
        sign = resize_sign(self.layout, order.index(current), len(order))
        if not sign:
            return
        ratio = self._saved_ratio(ratios, area_key)
        if ratio is None:               # even columns: start from equal share
            ratio = 1.0 / len(order)
        ratio += float(delta) * sign
        ratios[self._ratio_key(area_key)] = min(0.8, max(0.2, ratio))
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
        return self._rules.matches(
            winapi.window_process_name(hwnd),
            lambda: winapi.window_class_name(hwnd),
            lambda: winapi.window_title(hwnd))

    def set_floating_apps(self, names, notify=True):
        self.floating_apps = split_names(names)
        self._rebuild_rules()
        if notify:
            self._changed()
            self.schedule_layout()

    def set_floating_rules(self, rules, notify=True):
        self._rule_config = rules if isinstance(rules, dict) else {}
        self._rebuild_rules()
        if notify:
            self._changed()
            self.schedule_layout()

    def _rebuild_rules(self):
        self._rules = FloatingRules(self._rule_config, self.floating_apps)
        self.floating_rules = {
            "executables": set(self._rules.executables),
            "classes": set(self._rules.classes),
            "title_regex": list(self._rules.title_patterns),
        }
        self.invalid_title_patterns = list(self._rules.invalid_title_patterns)

    # -- layout selection and per-layout ratios ---------------------------
    def _ratio_key(self, area_key):
        """BSP keeps its original key; other layouts get their own so a
        ratio set for one layout never leaks into another."""
        return area_key if self.layout == "bsp" else f"{area_key}|{self.layout}"

    def _saved_ratio(self, ratios, area_key):
        """Saved ratio for the current layout, or its default (maybe None)."""
        value = ratios.get(self._ratio_key(area_key))
        if value is None:
            return default_ratio(self.layout)
        try:
            return min(0.8, max(0.2, float(value)))
        except (TypeError, ValueError):
            return default_ratio(self.layout)

    def set_layout(self, name):
        self.layout = normalize_layout(name)
        self.schedule_layout()
        return self.layout

    def cycle_layout(self):
        """Switch to the next layout; returns its display label."""
        return LAYOUT_LABELS[self.set_layout(next_layout(self.layout))]

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
    """Global controls that require a registered safe-release shortcut."""
    HOTKEYS = {0xB19: (0x1B, "release", 0x0003),
               0xB1A: (0x4A, "focus", 0x0003),
               0xB1B: (0x4B, "swap", 0x0003),
               0xB1C: (0x46, "floating", 0x0003),
               0xB1D: (0x48, "resize_smaller", 0x0003),
               0xB1E: (0x4C, "resize_larger", 0x0003),
               0xB1F: (0x25, "move_previous", 0x0007),
               0xB20: (0x27, "move_next", 0x0007),
               0xB21: (0x54, "layout", 0x0003)}
    WM_HOTKEY = 0x0312

    RELEASE_ID = 0xB19
    RELEASE_FALLBACKS = ("ctrl+alt+f12", "ctrl+shift+f12")

    def __init__(self, callbacks, release_hotkey="ctrl+alt+esc"):
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
        self.release_binding = None
        self.release_fallback_used = False
        self.release_attempts = []
        self._actions = dict(callbacks)
        type(self)._actions = self._actions
        if winapi.IS_WIN:
            candidates = []
            preferred_spec = None
            for spec in (release_hotkey, *self.RELEASE_FALLBACKS):
                try:
                    binding = parse_hotkey_spec(spec)
                except ValueError as exc:
                    self.registration_errors["release"] = str(exc)
                    continue
                if preferred_spec is None:
                    preferred_spec = binding["spec"]
                if binding["spec"] not in [item["spec"] for item in candidates]:
                    candidates.append(binding)
            for binding in candidates:
                try:
                    ok = ctypes.windll.user32.RegisterHotKey(
                        None, self.RELEASE_ID, binding["modifiers"] | 0x4000,
                        binding["vk"])
                except Exception:
                    ok = False
                error = 0 if ok else int(ctypes.windll.kernel32.GetLastError())
                self.release_attempts.append((binding["spec"], error))
                if ok:
                    self.release_binding = binding["spec"]
                    self.release_fallback_used = (
                        binding["spec"] != preferred_spec)
                    self.registered_ids.add(self.RELEASE_ID)
                    break
            if self.registered_ids:
                self.registration_errors.pop("release", None)
            else:
                self.registration_errors["release"] = (
                    self.release_attempts[-1][1] if self.release_attempts
                    else "No valid release shortcut")
            if self.registered_ids:
                for hotkey_id, (vk, action_name, modifiers) in self.HOTKEYS.items():
                    if hotkey_id == self.RELEASE_ID:
                        continue
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
                    else:
                        self.registration_errors[action_name] = int(
                            ctypes.windll.kernel32.GetLastError())
        self.registered = self.RELEASE_ID in self.registered_ids
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

