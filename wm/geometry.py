"""Pure rectangle helpers for window placement (no Windows or Qt imports)."""


def frame_insets(outer, visible):
    """Invisible-border sizes ``(left, top, right, bottom)`` of a window.

    ``outer`` is the rectangle from ``GetWindowRect`` and ``visible`` the one
    from ``DWMWA_EXTENDED_FRAME_BOUNDS``, both as ``(x, y, width, height)``.
    Windows 10/11 add transparent resize borders to the outer rectangle, so
    the two differ by a few pixels on most sides.
    """
    ox, oy, ow, oh = (int(v) for v in outer)
    vx, vy, vw, vh = (int(v) for v in visible)
    left, top = vx - ox, vy - oy
    right, bottom = (ox + ow) - (vx + vw), (oy + oh) - (vy + vh)
    insets = (left, top, right, bottom)
    # Reject nonsense (e.g. a stale or unrelated rectangle) rather than
    # moving a window to a wildly wrong place.
    if any(value < 0 or value > 64 for value in insets):
        return (0, 0, 0, 0)
    return insets


def compensate(target, insets):
    """Return the ``SetWindowPos`` rectangle that makes the *visible* frame
    land on ``target`` given the window's invisible ``insets``."""
    x, y, width, height = (int(v) for v in target)
    left, top, right, bottom = insets
    return (x - left, y - top,
            max(1, width + left + right), max(1, height + top + bottom))

