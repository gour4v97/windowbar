"""Windows system state, input, recycle-bin, and theme helpers."""

import ctypes
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"
PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_fg_cache = {"hwnd": 0, "name": None}


def foreground_process():
    """Executable name of the focused window, cached by window handle."""
    if not IS_WIN:
        return None
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None
        if hwnd == _fg_cache["hwnd"]:
            return _fg_cache["name"]
        import psutil
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = psutil.Process(pid.value).name()
        _fg_cache.update(hwnd=hwnd, name=name)
        return name
    except Exception:
        return None


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def foreground_is_fullscreen(exclude_hwnd=0):
    """True when the focused app covers its monitor, excluding shell/dock."""
    if not IS_WIN:
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd or int(hwnd) == int(exclude_hwnd or 0):
            return False
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd",
                         "Shell_SecondaryTrayWnd"):
            return False
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        mon = user32.MonitorFromWindow(hwnd, 2)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return False
        m = info.rcMonitor
        return (rect.left <= m.left and rect.top <= m.top
                and rect.right >= m.right and rect.bottom >= m.bottom)
    except Exception:
        return False


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def idle_seconds():
    if not IS_WIN:
        return 0.0
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        ticks = ctypes.windll.kernel32.GetTickCount()
        return ((ticks - info.dwTime) & 0xFFFFFFFF) / 1000
    except Exception:
        return 0.0


class _RBINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong),
                ("i64NumItems", ctypes.c_longlong)]


def recycle_count():
    if not IS_WIN:
        return None
    try:
        info = _RBINFO()
        info.cbSize = ctypes.sizeof(info)
        ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        return info.i64NumItems
    except Exception:
        return None


def empty_recycle_bin():
    if IS_WIN:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1 | 2 | 4)


def is_dark_mode():
    if not IS_WIN:
        return True
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE) as key:
        return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0


def set_dark_mode(dark):
    if not IS_WIN:
        return
    import winreg
    value = 0 if dark else 1
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE, 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, ctypes.c_wchar_p("ImmersiveColorSet"), 2, 1000, None)


def lock_screen():
    if IS_WIN:
        ctypes.windll.user32.LockWorkStation()
