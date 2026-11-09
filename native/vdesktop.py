"""Feature-detected Windows virtual desktop adapter.

`pyvda` owns the Windows COM and build-specific details. Every public action is
guarded so a Windows update or unavailable package leaves the shell usable.
"""

import logging
import sys

from native import windows

_log = logging.getLogger("windowsbar.vdesktop")
IS_WIN = sys.platform == "win32"
_API_CHECKED = False
_API_MODULE = None


def _api():
    global _API_CHECKED, _API_MODULE
    if not IS_WIN:
        return None
    if _API_CHECKED:
        return _API_MODULE
    _API_CHECKED = True
    try:
        import pyvda
        _API_MODULE = pyvda
    except Exception:
        _log.debug("pyvda is unavailable", exc_info=True)
    return _API_MODULE


def available():
    return _api() is not None


def desktops():
    api = _api()
    if api is None:
        return []
    try:
        return api.get_virtual_desktops()
    except Exception:
        _log.warning("Could not enumerate virtual desktops", exc_info=True)
        return []


def current():
    api = _api()
    if api is None:
        return None
    try:
        return api.VirtualDesktop.current()
    except Exception:
        _log.warning("Could not read current virtual desktop", exc_info=True)
        return None


def switch(desktop):
    try:
        desktop.go()
        return True
    except Exception:
        _log.warning("Virtual desktop switch failed", exc_info=True)
        return False


def switch_relative(direction):
    api = _api()
    try:
        desktop = api.VirtualDesktop.current()
        desktops_now = api.get_virtual_desktops()
        current_id = desktop.id
        index = next(i for i, item in enumerate(desktops_now)
                     if item.id == current_id)
        target = (index + (1 if direction > 0 else -1)) % len(desktops_now)
        desktops_now[target].go()
        return True
    except Exception:
        # Windows' documented keyboard path remains usable if COM changes.
        action = "next" if direction > 0 else "previous"
        windows.virtual_desktop_action(action)
        return False


def create():
    api = _api()
    if api is not None:
        try:
            return api.VirtualDesktop.create()
        except Exception:
            _log.warning("Virtual desktop creation failed", exc_info=True)
    windows.virtual_desktop_action("new")
    return None


def remove(desktop):
    try:
        fallback = current()
        if fallback is not None and fallback.id == desktop.id:
            candidates = [item for item in desktops() if item.id != desktop.id]
            fallback = candidates[0] if candidates else None
        desktop.remove(fallback)
        return True
    except Exception:
        _log.warning("Virtual desktop removal failed", exc_info=True)
        return False


def rename(desktop, name):
    try:
        desktop.rename(name)
        return True
    except Exception:
        _log.info("Windows desktop rename is unavailable", exc_info=True)
        return False


def move_window(hwnd, desktop):
    api = _api()
    if api is None or not hwnd:
        return False
    try:
        api.AppView(hwnd=int(hwnd)).move(desktop)
        return True
    except Exception:
        _log.warning("Could not move window to virtual desktop", exc_info=True)
        return False


def set_wallpaper(desktop, path):
    try:
        desktop.set_wallpaper(path)
        return True
    except Exception:
        _log.info("Per-desktop wallpaper is unavailable", exc_info=True)
        return False

