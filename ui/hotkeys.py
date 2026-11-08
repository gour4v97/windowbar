"""Native event filter for pinned application hotkeys."""
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
import winapi
class AppHotkeyFilter(QAbstractNativeEventFilter):
    """Win+1..Win+9 for the pinned apps (Alt+digit fallback: Windows itself
    owns Win+number for the taskbar and usually refuses the registration,
    so the Alt variant is registered as a fallback)."""

    BASE = 0xC00
    WM_HOTKEY = 0x0312

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.count = 0

    def register_all(self):
        self.unregister()
        if not winapi.IS_WIN:
            return 0
        import ctypes
        user32 = ctypes.windll.user32
        MOD_WIN, MOD_ALT, MOD_NOREPEAT = 0x8, 0x1, 0x4000
        for i in range(9):
            vk = 0x31 + i
            ok = user32.RegisterHotKey(None, self.BASE + i,
                                       MOD_WIN | MOD_NOREPEAT, vk)
            if not ok:
                ok = user32.RegisterHotKey(None, self.BASE + i,
                                           MOD_ALT | MOD_NOREPEAT, vk)
            if ok:
                self.count += 1
        return self.count

    def unregister(self):
        if winapi.IS_WIN and self.count:
            import ctypes
            for i in range(9):
                try:
                    ctypes.windll.user32.UnregisterHotKey(None, self.BASE + i)
                except Exception:
                    pass
        self.count = 0

    def nativeEventFilter(self, event_type, message):
        if self.count and event_type in (b"windows_generic_MSG",
                                         "windows_generic_MSG"):
            try:
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == self.WM_HOTKEY \
                        and self.BASE <= msg.wParam < self.BASE + 9:
                    idx = int(msg.wParam) - self.BASE
                    QTimer.singleShot(0, lambda i=idx: self.callback(i))
                    return True, 0
            except Exception:
                pass
        return False, 0



