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


def foreground_hwnd():
    if not IS_WIN:
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


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
