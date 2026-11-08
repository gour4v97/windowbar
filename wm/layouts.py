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


def _usable_area(rect, gap, padding):
    x, y, width, height = (int(value) for value in rect)
    gap, padding = max(0, int(gap)), max(0, int(padding))
    return (x + padding, y + padding,
            max(1, width - 2 * padding), max(1, height - 2 * padding), gap)


def columns_layout(rect, count, gap=12, padding=16, ratio=0.5):
    """Equal-height columns; ratio adjusts the leftmost column's share."""
    count = max(0, int(count))
    if not count:
        return []
    x, y, width, height, gap = _usable_area(rect, gap, padding)
    available = max(count, width - gap * (count - 1))
    if count == 1:
        return [(x, y, available, height)]
    ratio = min(.8, max(.2, float(ratio)))
    first = min(available - (count - 1), max(1, int(available * ratio)))
    remainder = available - first
    widths = [first]
    for index in range(count - 1):
        widths.append(remainder // (count - 1)
                      + (1 if index < remainder % (count - 1) else 0))
    boxes, cursor = [], x
    for tile_width in widths:
        boxes.append((cursor, y, tile_width, height))
        cursor += tile_width + gap
    return boxes


def master_stack_layout(rect, count, gap=12, padding=16, ratio=0.6):
    """Place one master window beside a vertical stack of the others."""
    count = max(0, int(count))
    if not count:
        return []
    x, y, width, height, gap = _usable_area(rect, gap, padding)
    if count == 1:
        return [(x, y, width, height)]
    available = max(2, width - gap)
    master_width = min(available - 1,
                       max(1, int(available * min(.8, max(.2, ratio)))))
    stack_width = available - master_width
    stack_count = count - 1
    available_height = max(stack_count, height - gap * (stack_count - 1))
    base, extra = divmod(available_height, stack_count)
    boxes = [(x, y, master_width, height)]
    cursor = y
    for index in range(stack_count):
        tile_height = base + (1 if index < extra else 0)
        boxes.append((x + master_width + gap, cursor, stack_width, tile_height))
        cursor += tile_height + gap
    return boxes
