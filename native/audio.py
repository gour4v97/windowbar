"""Default Windows output volume controls through Core Audio COM."""

import ctypes
import sys

IS_WIN = sys.platform == 'win32'


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

