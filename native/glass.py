"""DWM backdrop and acrylic window effects."""

import ctypes
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"

# Windows DWM attributes and corner/backdrop constants (Windows 11 22H2+)
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38

DWMWCP_ROUND = 2
DWMSBT_AUTO = 1
DWMSBT_NONE = 2
DWMSBT_MAINWINDOW = 3       # Mica
DWMSBT_TRANSIENTWINDOW = 4   # Acrylic
DWMSBT_TABBED = 5            # Tabbed (Mica Alt)


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


def enable_glass(hwnd, acrylic=True):
    """Apply a DWM acrylic (or Mica) backdrop on Windows; return whether it succeeded."""
    if not IS_WIN:
        return False
    try:
        dwm = ctypes.windll.dwmapi
        if sys.getwindowsversion().build >= 22621:
            def attr(attribute, value):
                val = ctypes.c_int(value)
                return dwm.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd), attribute, ctypes.byref(val), 4)
            attr(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
            attr(DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
            margins = _MARGINS(-1, -1, -1, -1)
            dwm.DwmExtendFrameIntoClientArea(
                wintypes.HWND(hwnd), ctypes.byref(margins))
            backdrop = DWMSBT_TRANSIENTWINDOW if acrylic else DWMSBT_MAINWINDOW
            res = attr(DWMWA_SYSTEMBACKDROP_TYPE, backdrop)
            if res < 0 and acrylic:
                # Fallback to Mica if Acrylic is unavailable on this driver/composition
                res = attr(DWMWA_SYSTEMBACKDROP_TYPE, DWMSBT_MAINWINDOW)
            return res >= 0
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
            value = ctypes.c_int(DWMSBT_AUTO)
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_SYSTEMBACKDROP_TYPE,
                                      ctypes.byref(value), 4)
        else:
            _set_accent(hwnd, 0)
    except Exception:
        pass
