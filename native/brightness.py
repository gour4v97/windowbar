"""Optional internal-panel brightness control through Windows WMI."""

import sys


def _methods():
    if sys.platform != "win32":
        return []
    try:
        import wmi
        return wmi.WMI(namespace="wmi").WmiMonitorBrightnessMethods()
    except Exception:
        return []


def get_brightness():
    """Return the first internal display's brightness percentage, if exposed."""
    if sys.platform != "win32":
        return None
    try:
        import wmi
        levels = wmi.WMI(namespace="wmi").WmiMonitorBrightness()
        return int(levels[0].CurrentBrightness) if levels else None
    except Exception:
        return None


def set_brightness(percent):
    """Set internal display brightness; external DDC monitors are unsupported."""
    value = max(0, min(100, int(percent)))
    try:
        methods = _methods()
        for method in methods:
            method.WmiSetBrightness(Timeout=0, Brightness=value)
        return bool(methods)
    except Exception:
        return False

