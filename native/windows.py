"""Windows-only native helpers. Every function is a safe no-op elsewhere."""
import ctypes
import logging
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"
_log = logging.getLogger("windowsbar.winapi")
PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
from native.appbar import (ABM_GETSTATE, ABM_NEW, ABM_QUERYPOS, ABM_REMOVE,
                           ABM_SETSTATE, ABM_SETPOS, ABE_BOTTOM, ABE_TOP,
                           ABS_AUTOHIDE, AppBar, restore_taskbar,
                           set_taskbar_autohide)
from native.glass import disable_glass, enable_glass


# ------------------------------------------------------------------ glass --
from native.system import (foreground_process, foreground_is_fullscreen, idle_seconds,
                           recycle_count, empty_recycle_bin, is_dark_mode,
                           set_dark_mode, lock_screen)
from native.audio import get_volume, set_volume, set_mute

# ---------------------------------------------------- power / keep awake ----
def set_keep_awake(on):
    """Stop the display/system sleeping while `on` (cleared with off).
    Applies to the calling thread; call from the UI thread."""
    if not IS_WIN:
        return
    try:
        ES_CONTINUOUS = 0x80000000
        flags = ES_CONTINUOUS | (0x1 | 0x2 if on else 0)  # SYSTEM|DISPLAY
        ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_ulong(flags))
    except Exception:
        pass


def power_action(action):
    """lock | sleep | signout | restart | shutdown (restart/shutdown are
    immediate -- the caller confirms first)."""
    if not IS_WIN:
        return
    import subprocess
    try:
        if action == "lock":
            lock_screen()
        elif action == "sleep":
            ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        elif action == "signout":
            subprocess.run(["shutdown", "/l"], check=False)
        elif action == "restart":
            subprocess.run(["shutdown", "/r", "/t", "0"], check=False)
        elif action == "shutdown":
            subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
    except Exception:
        pass


def open_notification_center():
    """Open the native Windows notification surface using its built-in key."""
    if not IS_WIN:
        return
    try:
        user32 = ctypes.windll.user32
        vk_win, vk_n, vk_a = 0x5B, 0x4E, 0x41
        key = vk_n if sys.getwindowsversion().build >= 22000 else vk_a
        keybd_event = user32.keybd_event
        keybd_event(vk_win, 0, 0, 0)
        keybd_event(key, 0, 0, 0)
        keybd_event(key, 0, 0x0002, 0)
        keybd_event(vk_win, 0, 0x0002, 0)
    except Exception:
        _log.exception("Could not open Windows notification center")


def virtual_desktop_action(action):
    """Use supported shell hotkeys for virtual desktop navigation."""
    if not IS_WIN:
        return
    shortcuts = {
        "previous": (0x5B, 0x11, 0x25),
        "next": (0x5B, 0x11, 0x27),
        "new": (0x5B, 0x11, 0x44),
        "overview": (0x5B, 0x09),
    }
    keys = shortcuts.get(action)
    if not keys:
        return
    user32 = ctypes.windll.user32
    try:
        for key in keys:
            user32.keybd_event(key, 0, 0, 0)
        for key in reversed(keys):
            user32.keybd_event(key, 0, 0x0002, 0)
    except Exception:
        _log.exception("Could not invoke virtual desktop shortcut: %s", action)


def close_window(hwnd):
    if IS_WIN and hwnd:
        try:
            ctypes.windll.user32.PostMessageW(
                wintypes.HWND(hwnd), 0x0010, 0, 0)  # WM_CLOSE
        except Exception:
            pass


def minimize_window(hwnd):
    if IS_WIN and hwnd:
        try:
            ctypes.windll.user32.ShowWindow(wintypes.HWND(hwnd), 6)  # SW_MINIMIZE
        except Exception:
            pass


def open_window_processes():
    """{exe_name_lower: hwnd} for taskbar windows -- which pinned apps are
    currently running, and where to focus them."""
    if not IS_WIN:
        return {}
    try:
        import psutil
    except Exception:
        return {}
    user32 = ctypes.windll.user32
    out = {}
    wins = list_open_windows(64)
    for hwnd, _title in wins:
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(wintypes.HWND(hwnd),
                                            ctypes.byref(pid))
            name = psutil.Process(pid.value).name().lower()
            out.setdefault(name, hwnd)
        except Exception:
            continue
    return out


# ------------------------------------------------------- windows / startup --
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def list_open_windows(limit=8, exclude=()):
    """[(hwnd, title)] for windows that would appear on the taskbar: visible,
    titled, not cloaked (UWP ghosts, other virtual desktops), not tool windows
    and not owned popups. Meant to run in a background thread."""
    if not IS_WIN:
        return []
    user32 = ctypes.windll.user32
    dwm = ctypes.windll.dwmapi
    out = []
    skip = {int(x) for x in exclude}

    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _):
        h = int(hwnd or 0)
        if h in skip or not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if not n:
            return True
        ex = user32.GetWindowLongW(hwnd, -20)           # GWL_EXSTYLE
        if ex & 0x80 and not ex & 0x40000:              # TOOLWINDOW, not APPWINDOW
            return True
        if user32.GetWindow(hwnd, 4):                   # GW_OWNER
            return True
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value.strip()
        if title and title != "Program Manager":
            out.append((h, title))
        return len(out) < limit

    try:
        user32.EnumWindows(CB(_cb), 0)
    except Exception:
        pass
    return out[:limit]


def window_rect(hwnd):
    if not IS_WIN or not hwnd:
        return None
    rect = wintypes.RECT()
    try:
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(int(hwnd)),
                                                   ctypes.byref(rect)):
            return None
        return (rect.left, rect.top, rect.right - rect.left,
                rect.bottom - rect.top)
    except Exception:
        return None


def window_is_minimized(hwnd):
    try:
        return bool(IS_WIN and ctypes.windll.user32.IsIconic(
            wintypes.HWND(int(hwnd))))
    except Exception:
        return False


def is_window(hwnd):
    try:
        return bool(IS_WIN and hwnd and ctypes.windll.user32.IsWindow(
            wintypes.HWND(int(hwnd))))
    except Exception:
        return False


def window_process_name(hwnd):
    """Lowercase executable basename for per-app window rules."""
    if not IS_WIN or not hwnd:
        return ""
    try:
        import psutil
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(
            wintypes.HWND(int(hwnd)), ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower()
    except Exception:
        return ""


def window_class_name(hwnd):
    if not IS_WIN or not hwnd:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        length = ctypes.windll.user32.GetClassNameW(
            wintypes.HWND(int(hwnd)), buf, len(buf))
        return buf.value[:length].lower()
    except Exception:
        return ""


def window_state(hwnd):
    """Capture a window's rectangle and show state for safe restoration."""
    if not IS_WIN:
        return None
    rect = window_rect(hwnd)
    if not rect:
        return None
    user32 = ctypes.windll.user32
    return (rect, bool(user32.IsZoomed(wintypes.HWND(int(hwnd)))),
            bool(user32.IsIconic(wintypes.HWND(int(hwnd)))))


def primary_work_area():
    if not IS_WIN:
        return None
    rect = wintypes.RECT()
    try:
        if ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return (rect.left, rect.top, rect.right - rect.left,
                    rect.bottom - rect.top)
    except Exception:
        pass
    return None


def window_work_area(hwnd):
    """Return the nearest monitor's work area for a window."""
    if not IS_WIN or not hwnd:
        return None
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    try:
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE,
                                           ctypes.POINTER(MONITORINFO))
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        monitor = user32.MonitorFromWindow(wintypes.HWND(int(hwnd)), 2)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not monitor or not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        rect = info.rcWork
        return (rect.left, rect.top, rect.right - rect.left,
                rect.bottom - rect.top)
    except Exception:
        _log.exception("Could not read work area for window %s", hwnd)
        return None


def move_window_rect(hwnd, rect):
    if not IS_WIN or not hwnd:
        return False
    x, y, width, height = (int(value) for value in rect)
    user32 = ctypes.windll.user32
    try:
        handle = wintypes.HWND(int(hwnd))
        if user32.IsIconic(handle) or user32.IsZoomed(handle):
            user32.ShowWindow(handle, 9)  # SW_RESTORE
        return bool(user32.SetWindowPos(handle, None, x, y, width, height,
                                        0x0004 | 0x0010))  # NOZORDER|NOACTIVATE
    except Exception:
        _log.exception("Could not tile window %s", hwnd)
        return False


def restore_window_state(hwnd, state):
    if not IS_WIN or not state or not is_window(hwnd):
        return False
    rect, was_maximized, was_minimized = state
    move_window_rect(hwnd, rect)
    try:
        if was_maximized:
            ctypes.windll.user32.ShowWindow(wintypes.HWND(int(hwnd)), 3)
        elif was_minimized:
            ctypes.windll.user32.ShowWindow(wintypes.HWND(int(hwnd)), 6)
        return True
    except Exception:
        _log.exception("Could not restore window %s", hwnd)
        return False


def foreground_hwnd():
    if not IS_WIN:
        return 0
    try:
        get_foreground = ctypes.windll.user32.GetForegroundWindow
        get_foreground.restype = wintypes.HWND
        return int(get_foreground() or 0)
    except Exception:
        return 0


def window_title(hwnd=0):
    """Return the title of a window handle, or an empty string."""
    if not IS_WIN:
        return ""
    try:
        user32 = ctypes.windll.user32
        if not hwnd:
            get_foreground = user32.GetForegroundWindow
            get_foreground.restype = wintypes.HWND
            hwnd = get_foreground()
        handle_value = (hwnd.value if hasattr(hwnd, "value")
                        else int(hwnd or 0))
        handle = wintypes.HWND(handle_value)
        user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        length = user32.GetWindowTextLengthW(handle)
        if not length:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW.argtypes = (
            wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowTextW(handle, buf, length + 1)
        return buf.value.strip()
    except Exception:
        return ""


def wallpaper_path():
    """Current desktop wallpaper file ('' when unknown, e.g. slideshow)."""
    if not IS_WIN:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        ctypes.windll.user32.SystemParametersInfoW(0x0073, 520, buf, 0)  # GETDESKWALLPAPER
        if buf.value:
            return buf.value
        import os
        cached = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows",
                              "Themes", "TranscodedWallpaper")
        return cached if os.path.exists(cached) else ""
    except Exception:
        return ""


def focus_window(hwnd):
    if not IS_WIN:
        return
    try:
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def pin_behind_windows(hwnd):
    """Place a desktop widget HWND at the bottom without activating it."""
    if not IS_WIN:
        return False
    try:
        user32 = ctypes.windll.user32
        set_pos = user32.SetWindowPos
        set_pos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            wintypes.UINT)
        set_pos.restype = wintypes.BOOL
        HWND_BOTTOM = wintypes.HWND(1)
        SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = (
            0x0001, 0x0002, 0x0010, 0x0040)
        return bool(set_pos(wintypes.HWND(int(hwnd)), HWND_BOTTOM, 0, 0, 0, 0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
                            | SWP_SHOWWINDOW))
    except Exception:
        _log.exception("Could not place desktop widgets behind windows")
        return False


def autostart_enabled(name="Windows Bar"):
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, name)
        return True
    except OSError:
        return False


def set_autostart(enable, name, command):
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(k, name)
            except OSError:
                pass
