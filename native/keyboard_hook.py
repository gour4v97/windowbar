"""Dedicated-thread WH_KEYBOARD_LL hook for the custom Alt+Tab switcher."""

import ctypes
import logging
import sys
import threading
from ctypes import wintypes

_log = logging.getLogger("windowsbar.keyboard_hook")
IS_WIN = sys.platform == "win32"
WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_QUIT = 0x0012
VK_TAB, VK_RETURN, VK_ESCAPE = 0x09, 0x0D, 0x1B
VK_SHIFT, VK_LSHIFT, VK_RSHIFT = 0x10, 0xA0, 0xA1
VK_CONTROL, VK_LCONTROL, VK_RCONTROL = 0x11, 0xA2, 0xA3
VK_MENU, VK_LMENU, VK_RMENU = 0x12, 0xA4, 0xA5
VK_LEFT, VK_RIGHT, VK_HOME, VK_END = 0x25, 0x27, 0x24, 0x23


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


_HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)


class LowLevelKeyboardHook:
    """Install/uninstall a fast keyboard hook on a thread with a message loop.

    ``on_action`` must be a nonblocking queue operation. It is called from the
    hook thread; the UI handles the queued action on its own Qt thread.
    """

    def __init__(self, on_action):
        self.on_action = on_action
        self._thread = None
        self._thread_id = 0
        self._hook = None
        self._ready = threading.Event()
        self._active = False
        self._alt_down = False
        self._shift_down = False
        self._ctrl_down = False
        self.error = ""
        self._callback = _HOOKPROC(self._hook_proc)

    def start(self, timeout=2.0):
        if not IS_WIN:
            self.error = "The custom switcher requires Windows."
            return False
        if self._thread and self._thread.is_alive():
            return self._hook is not None
        self._ready.clear()
        self.error = ""
        self._thread = threading.Thread(
            target=self._message_loop, name="WindowsBarKeyboardHook",
            daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            self.error = "The keyboard hook did not start in time."
            self.stop()
            return False
        return self._hook is not None

    def stop(self, timeout=2.0):
        thread = self._thread
        if not IS_WIN or thread is None:
            return
        if thread.is_alive() and self._thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                _log.exception("Could not stop the keyboard-hook message loop")
            thread.join(timeout)
        if thread.is_alive():
            _log.error("Keyboard-hook thread did not stop")
        self._active = False

    def _message_loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            get_thread_id = kernel32.GetCurrentThreadId
            get_thread_id.restype = wintypes.DWORD
            self._thread_id = int(get_thread_id())

            get_module = kernel32.GetModuleHandleW
            get_module.argtypes = (wintypes.LPCWSTR,)
            get_module.restype = ctypes.c_void_p
            module = get_module(None)

            set_hook = user32.SetWindowsHookExW
            set_hook.argtypes = (ctypes.c_int, _HOOKPROC,
                                 ctypes.c_void_p, wintypes.DWORD)
            set_hook.restype = ctypes.c_void_p
            self._hook = set_hook(WH_KEYBOARD_LL, self._callback, module, 0)
            if not self._hook:
                self.error = "Windows refused to install the keyboard hook."
                self._ready.set()
                return

            get_message = user32.GetMessageW
            get_message.argtypes = (ctypes.POINTER(wintypes.MSG),
                                    wintypes.HWND, wintypes.UINT,
                                    wintypes.UINT)
            get_message.restype = ctypes.c_int
            peek_message = user32.PeekMessageW
            peek_message.argtypes = (ctypes.POINTER(wintypes.MSG),
                                     wintypes.HWND, wintypes.UINT,
                                     wintypes.UINT, wintypes.UINT)
            # Create this thread's message queue before start() can be followed
            # immediately by stop() and a PostThreadMessage(WM_QUIT).
            peek_message(ctypes.byref(wintypes.MSG()), None, 0, 0, 0)
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
            _log.exception("Keyboard-hook thread failed")
            self._ready.set()
        finally:
            if self._hook:
                try:
                    user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    _log.exception("Could not remove the keyboard hook")
            self._hook = None
            self._thread_id = 0

    def _emit(self, action, direction=0):
        try:
            self.on_action((action, direction))
        except Exception:
            # The hook callback must never raise or delay Windows input.
            _log.exception("Could not queue Alt+Tab action")

    def _hook_proc(self, code, wparam, lparam):
        user32 = ctypes.windll.user32
        if code != HC_ACTION:
            return user32.CallNextHookEx(self._hook, code, wparam, lparam)
        try:
            key = ctypes.cast(
                lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode
            down = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            up = wparam in (WM_KEYUP, WM_SYSKEYUP)

            if key in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT):
                self._shift_down = down
            elif key in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
                self._ctrl_down = down
            elif key in (VK_MENU, VK_LMENU, VK_RMENU):
                self._alt_down = down
                if up and self._active:
                    self._active = False
                    self._emit("commit")
                    return 1
            elif down and key == VK_TAB and self._alt_down \
                    and not self._ctrl_down:
                if not self._active:
                    self._active = True
                    self._emit("start", -1 if self._shift_down else 1)
                else:
                    self._emit("step", -1 if self._shift_down else 1)
                return 1
            elif self._active:
                if up and key == VK_TAB:
                    return 1
                if down and key == VK_ESCAPE:
                    self._active = False
                    self._emit("cancel")
                    return 1
                if down and key == VK_RETURN:
                    self._active = False
                    self._emit("commit")
                    return 1
                if down and key in (VK_LEFT, VK_RIGHT):
                    self._emit("step", -1 if key == VK_LEFT else 1)
                    return 1
                if down and key == VK_HOME:
                    self._emit("first")
                    return 1
                if down and key == VK_END:
                    self._emit("last")
                    return 1
        except Exception:
            _log.exception("Keyboard-hook callback failed")
        return user32.CallNextHookEx(self._hook, code, wparam, lparam)
