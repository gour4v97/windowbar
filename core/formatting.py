"""Small display formatting helpers shared by widgets."""

def fmt_hms(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_speed(bps):
    for unit in ("B/s", "KB/s", "MB/s"):
        if bps < 1024:
            return f"{bps:.0f} {unit}"
        bps /= 1024
    return f"{bps:.1f} GB/s"


def fmt_delta(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return "now"
    m = seconds // 60
    if m < 60:
        return f"in {m}m"
    h, m = divmod(m, 60)
    return f"in {h}h {m:02d}m" if h < 24 else f"in {h // 24}d"
