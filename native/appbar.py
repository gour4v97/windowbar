"""Windows AppBar reservation and taskbar state restoration."""

import ctypes
import logging
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"
_log = logging.getLogger("windowsbar.winapi")
ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS = 0, 1, 2, 3
ABM_GETSTATE, ABM_SETSTATE = 4, 10
ABE_TOP, ABE_BOTTOM = 1, 3
ABS_AUTOHIDE = 1


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
                ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]


def _appbar(msg, abd):
    fn = ctypes.windll.shell32.SHAppBarMessage
    fn.restype = ctypes.c_size_t
    return fn(msg, ctypes.byref(abd))


def _abd(hwnd=0):
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(APPBARDATA)
    abd.hWnd = hwnd or None
    return abd


class AppBar:
    """Reserves a strip of the screen so maximized windows stop at the dock."""

    def __init__(self):
        self.hwnd = 0
        self.registered = False

    def reserve(self, top_edge, monitor_rect, thickness):
        if not IS_WIN or not self.hwnd:
            return None
        try:
            abd = _abd(self.hwnd)
            if not self.registered:
                abd.uCallbackMessage = 0x0401
                _appbar(ABM_NEW, abd)
                self.registered = True
            abd.uEdge = ABE_TOP if top_edge else ABE_BOTTOM
            l, t, r, b = monitor_rect
            abd.rc.left, abd.rc.top, abd.rc.right, abd.rc.bottom = l, t, r, b
            _appbar(ABM_QUERYPOS, abd)
            if top_edge:
                abd.rc.bottom = abd.rc.top + thickness
            else:
                abd.rc.top = abd.rc.bottom - thickness
            _appbar(ABM_SETPOS, abd)
            return (abd.rc.left, abd.rc.top, abd.rc.right, abd.rc.bottom)
        except Exception:
            return None

    def remove(self):
        if IS_WIN and self.registered:
            try:
                _appbar(ABM_REMOVE, _abd(self.hwnd))
            except Exception:
                pass
        self.registered = False


def set_taskbar_autohide(enable, hwnd, cfg):
    """Save the user's state before enabling auto-hide so startup can restore it."""
    if not IS_WIN:
        return
    try:
        original = cfg.get("_taskbar_original")
        if enable:
            if original is None:
                original = _appbar(ABM_GETSTATE, _abd(hwnd))
                cfg["_taskbar_original"] = original
            abd = _abd(hwnd)
            abd.lParam = original | ABS_AUTOHIDE
            _appbar(ABM_SETSTATE, abd)
        else:
            restore_taskbar(cfg, hwnd)
    except Exception:
        _log.exception("Could not update taskbar auto-hide state")


def _restore_taskbar_state(cfg, apply_state):
    """Apply and consume a saved taskbar state; injectable for recovery tests."""
    if "_taskbar_original" not in cfg:
        return False
    original = cfg["_taskbar_original"]
    try:
        apply_state(original)
    except Exception:
        _log.exception("Could not restore the saved taskbar state")
        return False
    cfg.pop("_taskbar_original", None)
    return True


def restore_taskbar(cfg, hwnd=0):
    if "_taskbar_original" not in cfg:
        return
    if not IS_WIN:
        cfg.pop("_taskbar_original", None)
        return

    def apply_state(original):
        abd = _abd(hwnd)
        abd.lParam = original
        _appbar(ABM_SETSTATE, abd)

    _restore_taskbar_state(cfg, apply_state)
