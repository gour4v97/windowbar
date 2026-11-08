"""Native event filter for pinned application hotkeys."""
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
import winapi
class AppHotkeyFilter(QAbstractNativeEventFilter):
    """Global number hotkeys for pinned apps, with a configurable modifier."""

    BASE = 0xC00
    WM_HOTKEY = 0x0312
    MODIFIERS = {"alt": 0x0001, "ctrl+alt": 0x0001 | 0x0002,
                 "win": 0x0008}
    MOD_NOREPEAT = 0x4000

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.count = 0
        self.modifier = "alt"

    @classmethod
    def modifier_flags(cls, modifier):
        return cls.MODIFIERS.get(str(modifier).lower(), cls.MODIFIERS["alt"])

    def register_all(self, modifier="alt"):
        self.unregister()
        modifier = str(modifier).lower()
        self.modifier = modifier if modifier in self.MODIFIERS else "alt"
        if not winapi.IS_WIN:
            return 0
        import ctypes
        user32 = ctypes.windll.user32
        flags = self.modifier_flags(self.modifier) | self.MOD_NOREPEAT
        for i in range(9):
            if user32.RegisterHotKey(None, self.BASE + i, flags, 0x31 + i):
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
