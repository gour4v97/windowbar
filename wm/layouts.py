"""Pure window layout geometry helpers."""


def bsp_layout(rect, count, gap=12, padding=16, ratio=0.5):
    """Return balanced BSP rectangles inside ``(x, y, width, height)``."""
    count = max(0, int(count))
    if not count:
        return []
    x, y, width, height, gap = _usable_area(rect, gap, padding, count)
    if width <= 0 or height <= 0:
        return []
    ratio = min(0.8, max(0.2, float(ratio)))

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


def _usable_area(rect, gap, padding, count):
    x, y, width, height = (int(value) for value in rect)
    count = max(0, int(count))
    if width <= 0 or height <= 0:
        return x, y, 0, 0, 0
    gap, padding = max(0, int(gap)), max(0, int(padding))
    padding = min(padding, (width - 1) // 2, (height - 1) // 2)
    usable_width = width - 2 * padding
    usable_height = height - 2 * padding
    if count > 1:
        # Reserve enough pixels for every tile even in a narrow work area.
        # This is conservative across all layouts and prevents repeated gaps
        # from pushing the last column or stack past the screen edge.
        gap = min(gap, max(0, (min(usable_width, usable_height) - count)
                           // (count - 1)))
    return (x + padding, y + padding, usable_width, usable_height, gap)


def columns_layout(rect, count, gap=12, padding=16, ratio=None):
    """Equal-height columns. ``ratio=None`` makes every column the same
    width; a number sets the leftmost column's share (0.2-0.8)."""
    count = max(0, int(count))
    if not count:
        return []
    x, y, width, height, gap = _usable_area(rect, gap, padding, count)
    if width <= 0 or height <= 0:
        return []
    available = max(count, width - gap * (count - 1))
    if count == 1:
        return [(x, y, available, height)]
    if ratio is None:
        ratio = 1.0 / count
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
    x, y, width, height, gap = _usable_area(rect, gap, padding, count)
    if width <= 0 or height <= 0:
        return []
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


DEFAULT_LAYOUT = "bsp"
LAYOUT_ORDER = ("bsp", "columns", "stack")
LAYOUT_LABELS = {"bsp": "BSP", "columns": "Columns", "stack": "Master / stack"}


def normalize_layout(name):
    """Return a known layout name, falling back to the default."""
    name = str(name or "").strip().lower()
    return name if name in LAYOUT_ORDER else DEFAULT_LAYOUT


def next_layout(name):
    """Return the layout after ``name`` in the cycle order."""
    current = normalize_layout(name)
    return LAYOUT_ORDER[(LAYOUT_ORDER.index(current) + 1) % len(LAYOUT_ORDER)]


def resize_sign(name, index, count):
    """Which way a positive resize delta moves the focused window's share.

    ``+1`` means the window grows, ``-1`` that it shrinks, ``0`` that the
    resize does nothing (fewer than two windows). In BSP the first half of
    the windows sit on the root split's first side; in Columns the ratio is
    the first column's share; in Master / stack it is the master's share.
    """
    if count < 2:
        return 0
    if normalize_layout(name) == "bsp":
        return 1 if index < (count + 1) // 2 else -1
    return 1 if index == 0 else -1


def default_ratio(name):
    """Starting ratio for a layout (``None`` = even columns)."""
    return {"bsp": 0.5, "columns": None, "stack": 0.6}[normalize_layout(name)]

