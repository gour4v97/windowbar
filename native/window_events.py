"""Dedicated-thread out-of-context WinEvent hook for top-level windows."""

import ctypes
import logging
import sys
import threading
from ctypes import wintypes

_log = logging.getLogger("windowsbar.window_events")
IS_WIN = sys.platform == "win32"
EVENT_SYSTEM_FOREGROUND = 0x0003
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_DESTROY = 0x8001
EVENT_OBJECT_SHOW = 0x8002
EVENT_OBJECT_HIDE = 0x8003
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
OBJID_WINDOW = 0
CHILDID_SELF = 0
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
WM_QUIT = 0x0012
_OBJECT_EVENTS = {
    EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY, EVENT_OBJECT_SHOW,
    EVENT_OBJECT_HIDE, EVENT_OBJECT_LOCATIONCHANGE,
}

_WINFUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_WINEVENTPROC = _WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
    wintypes.LONG, wintypes.DWORD, wintypes.DWORD)


class WinEventHook:
    """Listen for foreground and top-level window lifecycle events.

    ``on_event`` must only enqueue/emit the event. Windows calls it on this
    object's dedicated message-loop thread.
    """

    def __init__(self, on_event):
        self.on_event = on_event
        self._thread = None
        self._thread_id = 0
        self._hooks = []
        self._ready = threading.Event()
        self.error = ""
        self._callback = _WINEVENTPROC(self._on_win_event)

    def start(self, timeout=2.0):
        if not IS_WIN:
            self.error = "Window tracking requires Windows."
            return False
        if self._thread and self._thread.is_alive():
            return bool(self._hooks)
        self.error = ""
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._message_loop, name="WindowsBarWinEventHook",
            daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            self.error = "The Windows event hook did not start in time."
            self.stop()
            return False
        return bool(self._hooks)

    def stop(self, timeout=2.0):
        thread = self._thread
        if not IS_WIN or thread is None:
            return
        if thread.is_alive() and self._thread_id:
            try:
                post = ctypes.windll.user32.PostThreadMessageW
                post.argtypes = (wintypes.DWORD, wintypes.UINT,
                                 ctypes.c_size_t, ctypes.c_ssize_t)
                post.restype = wintypes.BOOL
                post(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                _log.exception("Could not stop the WinEvent message loop")
            thread.join(timeout)
        if thread.is_alive():
            _log.error("WinEvent hook thread did not stop")

    def _message_loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            get_thread_id = kernel32.GetCurrentThreadId
            get_thread_id.restype = wintypes.DWORD
            self._thread_id = int(get_thread_id())

            peek = user32.PeekMessageW
            peek.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                             wintypes.UINT, wintypes.UINT, wintypes.UINT)
            peek.restype = wintypes.BOOL
            peek(ctypes.byref(wintypes.MSG()), None, 0, 0, 0)

            set_hook = user32.SetWinEventHook
            set_hook.argtypes = (
                wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                _WINEVENTPROC, wintypes.DWORD, wintypes.DWORD,
                wintypes.DWORD)
            set_hook.restype = wintypes.HANDLE
            flags = WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
            foreground = set_hook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, None,
                self._callback, 0, 0, flags)
            if foreground:
                self._hooks.append(foreground)
            objects = set_hook(
                EVENT_OBJECT_CREATE, EVENT_OBJECT_LOCATIONCHANGE, None,
                self._callback, 0, 0, flags)
            if objects:
                self._hooks.append(objects)
            if len(self._hooks) != 2:
                self.error = "Windows refused to install the window event hook."
                self._ready.set()
                return

            get_message = user32.GetMessageW
            get_message.argtypes = (ctypes.POINTER(wintypes.MSG),
                                    wintypes.HWND, wintypes.UINT,
                                    wintypes.UINT)
            get_message.restype = ctypes.c_int
            translate = user32.TranslateMessage
            dispatch = user32.DispatchMessageW
            message = wintypes.MSG()
            self._ready.set()
            while True:
                result = get_message(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                translate(ctypes.byref(message))
                dispatch(ctypes.byref(message))
        except Exception as exc:
            self.error = str(exc)
            _log.exception("WinEvent hook thread failed")
            self._ready.set()
        finally:
            unhook = user32.UnhookWinEvent
            unhook.argtypes = (wintypes.HANDLE,)
            unhook.restype = wintypes.BOOL
            for hook in self._hooks:
                try:
                    unhook(hook)
                except Exception:
                    _log.exception("Could not remove a WinEvent hook")
            self._hooks.clear()
            self._thread_id = 0

    def _on_win_event(self, _hook, event, hwnd, object_id, child_id,
                      event_thread, event_time):
        if event == EVENT_SYSTEM_FOREGROUND:
            handle = int(hwnd or 0)
            if handle:
                self._emit(("foreground", handle))
            return
        if event not in _OBJECT_EVENTS or object_id != OBJID_WINDOW \
                or child_id != CHILDID_SELF:
            return
        handle = int(hwnd or 0)
        if handle:
            self._emit(("window", event, handle, int(event_thread),
                        int(event_time)))

    def _emit(self, event):
        try:
            self.on_event(event)
        except Exception:
            _log.exception("Could not queue a Windows window event")
