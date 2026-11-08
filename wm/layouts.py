"""Pure window layout geometry helpers."""


def bsp_layout(rect, count, gap=12, padding=16, ratio=0.5):
    """Return balanced BSP rectangles inside ``(x, y, width, height)``."""
    x, y, width, height = (int(value) for value in rect)
    count = max(0, int(count))
    if not count or width <= 0 or height <= 0:
        return []
    gap, padding = max(0, int(gap)), max(0, int(padding))
    ratio = min(0.8, max(0.2, float(ratio)))
    x, y = x + padding, y + padding
    width, height = max(1, width - 2 * padding), max(1, height - 2 * padding)

    def split(box, items, vertical=True, root=False):
        bx, by, bw, bh = box
        if items == 1:
            return [(bx, by, max(1, bw), max(1, bh))]
        left_count = (items + 1) // 2
        right_count = items - left_count
        if vertical:
            first = max(1, int((bw - gap) * (ratio if root else 0.5)))
            second = max(1, bw - gap - first)
            return (split((bx, by, first, bh), left_count, not vertical)
                    + split((bx + first + gap, by, second, bh),
                            right_count, not vertical))
        first = max(1, int((bh - gap) * (ratio if root else 0.5)))
        second = max(1, bh - gap - first)
        return (split((bx, by, bw, first), left_count, not vertical)
                + split((bx, by + first + gap, bw, second),
                        right_count, not vertical))

    return split((x, y, width, height), count, root=True)
