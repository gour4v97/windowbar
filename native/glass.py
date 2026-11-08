"""DWM backdrop and acrylic window effects."""

import ctypes
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"


class _MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int),
                ("t", ctypes.c_int), ("b", ctypes.c_int)]


class _ACCENT(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WCA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t)]


def _set_accent(hwnd, state):
    accent = _ACCENT(state, 2, 0x99161616, 0)
    data = _WCA(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p),
                ctypes.sizeof(accent))
    ctypes.windll.user32.SetWindowCompositionAttribute(
        wintypes.HWND(hwnd), ctypes.byref(data))


def enable_glass(hwnd):
    """Apply a DWM acrylic backdrop on Windows; return whether it succeeded."""
    if not IS_WIN:
        return False
    try:
        dwm = ctypes.windll.dwmapi
        if sys.getwindowsversion().build >= 22621:
            def attr(attribute, value):
                val = ctypes.c_int(value)
                return dwm.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), attribute, ctypes.byref(val), 4)
            attr(20, 1)
            attr(33, 2)
            margins = _MARGINS(-1, -1, -1, -1)
            dwm.DwmExtendFrameIntoClientArea(
                wintypes.HWND(hwnd), ctypes.byref(margins))
            return attr(38, 3) >= 0
        _set_accent(hwnd, 4)
        return True
    except Exception:
        return False


def disable_glass(hwnd):
    if not IS_WIN:
        return
    try:
        dwm = ctypes.windll.dwmapi
        if sys.getwindowsversion().build >= 22621:
            value = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 38,
                                      ctypes.byref(value), 4)
        else:
            _set_accent(hwnd, 0)
    except Exception:
        pass
