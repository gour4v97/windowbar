"""Windows-only native helpers. Every function is a safe no-op elsewhere."""
import ctypes
import logging
import sys
from ctypes import wintypes

IS_WIN = sys.platform == "win32"
_log = logging.getLogger(__name__)
ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS = 0, 1, 2, 3
ABM_GETSTATE, ABM_SETSTATE = 4, 10
ABE_TOP, ABE_BOTTOM = 1, 3
ABS_AUTOHIDE = 1
PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


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
    """Auto-hide the Windows taskbar. The user's original state is stored in
    cfg['_taskbar_original'] so restore_taskbar() can put it back after a crash."""
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


# ------------------------------------------------------------------ glass --
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
    """Acrylic blur-behind. Windows 11 22H2+ uses the DWM backdrop API;
    older builds use the acrylic accent. Returns True when applied."""
    if not IS_WIN:
        return False
    try:
        dwm = ctypes.windll.dwmapi
        if sys.getwindowsversion().build >= 22621:
            def attr(a, v):
                val = ctypes.c_int(v)
                return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), a,
                                                 ctypes.byref(val), 4)
            attr(20, 1)     # dark title/chrome
            attr(33, 2)     # rounded corners
            m = _MARGINS(-1, -1, -1, -1)
            dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(m))
            return attr(38, 3) >= 0          # 3 = acrylic backdrop
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
            val = ctypes.c_int(1)              # 1 = no backdrop
            dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 38,
                                      ctypes.byref(val), 4)
        else:
            _set_accent(hwnd, 0)
    except Exception:
        pass


# ------------------------------------------------------ system queries ----
_fg_cache = {"hwnd": 0, "name": None}


def foreground_process():
    """Executable name of the focused window, e.g. 'Code.exe'.
    Cached by window handle: this runs every second for screen time, and
    building a psutil.Process each time was a steady source of CPU use."""
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
    """True when the focused window covers its whole monitor (games, video,
    presentation apps) and is not the desktop, the shell or the dock itself."""
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
        mon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
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
        # no confirmation, no progress UI, no sound
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1 | 2 | 4)


def is_dark_mode():
    if not IS_WIN:
        return True
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE) as k:
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0


def set_dark_mode(dark):
    if not IS_WIN:
        return
    import winreg
    v = 0 if dark else 1
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "AppsUseLightTheme", 0, winreg.REG_DWORD, v)
        winreg.SetValueEx(k, "SystemUsesLightTheme", 0, winreg.REG_DWORD, v)
    # tell open apps the theme changed
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF, 0x001A, 0, ctypes.c_wchar_p("ImmersiveColorSet"), 2, 1000, None)


def lock_screen():
    if IS_WIN:
        ctypes.windll.user32.LockWorkStation()


# ------------------------------------------------------------- volume -------
def _guid(text):
    import uuid
    return ctypes.create_string_buffer(uuid.UUID(text).bytes_le, 16)


class _Com:
    """Minimal COM helper: build an interface pointer, call vtable slots."""
    @staticmethod
    def create(clsid, iid):
        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)
        ptr = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(_guid(clsid), None, 1,  # CLSCTX_INPROC
                                    _guid(iid), ctypes.byref(ptr))
        if hr != 0 or not ptr:
            raise OSError(f"CoCreateInstance failed: {hr:#x}")
        return ptr


_VOLUME = {"ptr": None}


def _endpoint_volume():
    """IAudioEndpointVolume for the default render device (cached)."""
    if _VOLUME["ptr"]:
        return _VOLUME["ptr"]
    if not IS_WIN:
        return None
    enum = _Com.create("{BCDE0395-E52F-467C-8E3D-C4579291692E}",
                       "{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    device = ctypes.c_void_p()
    vtbl = ctypes.cast(enum, ctypes.POINTER(ctypes.c_void_p))[0]
    get_default = ctypes.cast(
        ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[4],
        ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int,
                           ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)))
    if get_default(enum, 0, 0, ctypes.byref(device)) != 0 or not device:
        raise OSError("no default audio device")
    vol = ctypes.c_void_p()
    dtbl = ctypes.cast(device, ctypes.POINTER(ctypes.c_void_p))[0]
    activate = ctypes.cast(
        ctypes.cast(dtbl, ctypes.POINTER(ctypes.c_void_p))[3],
        ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_ulong, ctypes.c_void_p,
                           ctypes.POINTER(ctypes.c_void_p)))
    iid = _guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")
    if activate(device, iid, 1, None, ctypes.byref(vol)) != 0 or not vol:
        raise OSError("Activate(IAudioEndpointVolume) failed")
    _VOLUME["ptr"] = vol
    return vol


def get_volume():
    """(level 0..1, muted) for the default output device, or None."""
    if not IS_WIN:
        return None
    try:
        vol = _endpoint_volume()
        level = ctypes.c_float()
        vtbl = ctypes.cast(vol, ctypes.POINTER(ctypes.c_void_p))[0]
        get_scalar = ctypes.cast(
            ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[6],
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                               ctypes.POINTER(ctypes.c_float)))
        if get_scalar(vol, ctypes.byref(level)) != 0:
            return None
        muted = ctypes.c_int()
        get_mute = ctypes.cast(
            ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[12],
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                               ctypes.POINTER(ctypes.c_int)))
        get_mute(vol, ctypes.byref(muted))
        return level.value, bool(muted.value)
    except Exception:
        _VOLUME["ptr"] = None
        return None


def set_volume(fraction):
    if not IS_WIN:
        return
    try:
        vol = _endpoint_volume()
        vtbl = ctypes.cast(vol, ctypes.POINTER(ctypes.c_void_p))[0]
        set_scalar = ctypes.cast(
            ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[4],
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_float,
                               ctypes.c_void_p))
        set_scalar(vol, ctypes.c_float(max(0.0, min(1.0, fraction))), None)
    except Exception:
        _VOLUME["ptr"] = None


def set_mute(muted):
    if not IS_WIN:
        return
    try:
        vol = _endpoint_volume()
        vtbl = ctypes.cast(vol, ctypes.POINTER(ctypes.c_void_p))[0]
        setm = ctypes.cast(
            ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[11],
            ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int,
                               ctypes.c_void_p))
        setm(vol, ctypes.c_int(1 if muted else 0), None)
    except Exception:
        _VOLUME["ptr"] = None


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
