"""Tests for the pure window-manager logic (layouts, rules, geometry).

These need neither Windows nor Qt and run on any OS.
"""
from wm.geometry import compensate, frame_insets
from wm.layouts import (LAYOUT_ORDER, bsp_layout, columns_layout,
                        default_ratio, master_stack_layout, next_layout,
                        normalize_layout, resize_sign)
from wm.rules import FloatingRules, split_names
from wm.hotkeys import parse_hotkey_spec

LAYOUTS = {"bsp": bsp_layout, "columns": columns_layout,
           "stack": master_stack_layout}
AREAS = [(0, 0, 1920, 1040), (0, 0, 1366, 728), (-1920, 0, 1920, 1080),
         (100, 50, 801, 601)]


def _inside(rect, box):
    x, y, w, h = rect
    bx, by, bw, bh = box
    return x >= bx and y >= by and x + w <= bx + bw and y + h <= by + bh


def _overlap(a, b):
    return (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
            and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])


def test_safe_release_hotkey_parser_normalizes_valid_chords():
    assert parse_hotkey_spec("ALT + Control + Escape") == {
        "spec": "ctrl+alt+esc", "modifiers": 3, "vk": 0x1B}
    assert parse_hotkey_spec("ctrl+shift+f12")["vk"] == 0x7B


def test_safe_release_hotkey_parser_rejects_unsafe_or_conflicting_chords():
    for spec in ("alt+space", "ctrl+alt+delete", "ctrl+shift+esc",
                 "ctrl+alt+j", "ctrl+alt+shift+left", "win+ctrl+q",
                 "ctrl+ctrl+x", "ctrl+alt+f25"):
        try:
            parse_hotkey_spec(spec)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unsafe shortcut: {spec}")


def test_every_layout_returns_one_rect_per_window_inside_the_area():
    for name, layout in LAYOUTS.items():
        for area in AREAS:
            for count in range(1, 11):
                for gap, padding in ((0, 0), (12, 16), (20, 8)):
                    rects = layout(area, count, gap, padding)
                    assert len(rects) == count, (name, area, count)
                    box = (area[0] + padding, area[1] + padding,
                           area[2] - 2 * padding, area[3] - 2 * padding)
                    for rect in rects:
                        assert rect[2] >= 1 and rect[3] >= 1
                        assert _inside(rect, box), (name, area, count, rect)


def test_dense_layouts_reduce_gaps_to_keep_tiles_inside_small_areas():
    area = (50, -20, 300, 200)
    box = (area[0] + 16, area[1] + 16,
           area[2] - 32, area[3] - 32)
    for name, layout in LAYOUTS.items():
        for count in (11, 32, 100):
            rects = layout(area, count, gap=40, padding=16)
            assert len(rects) == count, (name, count)
            assert all(_inside(rect, box) for rect in rects), (name, count)
            for i, first in enumerate(rects):
                for second in rects[i + 1:]:
                    assert not _overlap(first, second), (name, count)


def test_no_layout_overlaps_windows():
    for name, layout in LAYOUTS.items():
        for count in range(2, 10):
            rects = layout((0, 0, 1920, 1040), count, 12, 16)
            for i, first in enumerate(rects):
                for second in rects[i + 1:]:
                    assert not _overlap(first, second), (name, count)


def test_empty_and_degenerate_inputs_return_no_rectangles():
    for layout in LAYOUTS.values():
        assert layout((0, 0, 1000, 600), 0) == []
    assert bsp_layout((0, 0, 0, 600), 3) == []
    assert bsp_layout((0, 0, 1000, -5), 3) == []


def test_columns_are_equal_by_default():
    cols = columns_layout((0, 0, 1000, 500), 3, gap=0, padding=0)
    widths = [c[2] for c in cols]
    assert max(widths) - min(widths) <= 1
    assert cols[0][0] == 0 and cols[-1][0] + cols[-1][2] == 1000
    assert all(c[1] == 0 and c[3] == 500 for c in cols)
    # The manager's starting ratio for Columns must keep them equal.
    assert default_ratio("columns") is None
    even = columns_layout((0, 0, 1000, 500), 3, 0, 0, ratio=default_ratio("columns"))
    assert even == cols


def test_columns_ratio_sets_the_first_column_share():
    cols = columns_layout((0, 0, 1000, 500), 3, gap=0, padding=0, ratio=0.5)
    assert cols[0][2] == 500
    assert cols[1][2] == cols[2][2] == 250


def test_gaps_are_respected():
    cols = columns_layout((0, 0, 1000, 500), 3, gap=10, padding=0)
    assert cols[1][0] - (cols[0][0] + cols[0][2]) == 10
    assert cols[2][0] - (cols[1][0] + cols[1][2]) == 10


def test_master_stack_uses_ratio_and_stacks_the_rest():
    master, *stack = master_stack_layout((0, 0, 1000, 600), 4, 0, 0, ratio=0.6)
    assert master == (0, 0, 600, 600)
    assert all(r[0] == 600 and r[2] == 400 for r in stack)
    assert stack[0][1] == 0 and stack[-1][1] + stack[-1][3] == 600
    assert master_stack_layout((0, 0, 1000, 600), 1, 0, 0) == [(0, 0, 1000, 600)]


def test_bsp_root_ratio_changes_first_split():
    even = bsp_layout((0, 0, 1000, 600), 2, gap=0, padding=0, ratio=0.5)
    wide = bsp_layout((0, 0, 1000, 600), 2, gap=0, padding=0, ratio=0.7)
    assert even[0][2] == 500 and wide[0][2] == 700 and wide[1][2] == 300


def test_layout_names_normalize_and_cycle():
    assert normalize_layout("COLUMNS ") == "columns"
    assert normalize_layout("rows") == "bsp"
    assert normalize_layout(None) == "bsp"
    seen, name = [], "bsp"
    for _ in LAYOUT_ORDER:
        seen.append(name)
        name = next_layout(name)
    assert seen == list(LAYOUT_ORDER) and name == "bsp"


def test_resize_sign_matches_what_each_ratio_controls():
    assert resize_sign("bsp", 0, 1) == 0
    assert resize_sign("bsp", 0, 4) == 1 and resize_sign("bsp", 3, 4) == -1
    # Columns ratio = first column's share; stack ratio = master's share.
    assert resize_sign("columns", 0, 3) == 1
    assert resize_sign("columns", 2, 3) == -1
    assert resize_sign("stack", 0, 3) == 1
    assert resize_sign("stack", 1, 3) == -1


def test_split_names_accepts_text_and_lists():
    assert split_names("A.exe, b.exe;\nC.EXE") == {"a.exe", "b.exe", "c.exe"}
    assert split_names([" Spotify.exe ", ""]) == {"spotify.exe"}
    assert split_names(None) == set()


def test_floating_rules_match_exe_class_and_title():
    rules = FloatingRules(
        {"executables": ["calc.exe"], "classes": ["TaskManagerWindow"],
         "title_regex": [r"^Picture[- ]in[- ]picture$", "(broken"]},
        floating_apps=["Spotify.exe"])
    assert rules.matches("Calc.EXE") and rules.matches("spotify.exe")
    assert rules.matches("x.exe", window_class="taskmanagerwindow")
    assert rules.matches("x.exe", "Other", "Picture-in-Picture")
    assert not rules.matches("x.exe", "Other", "Notepad")
    assert rules.invalid_title_patterns == ["(broken"]


def test_floating_rules_only_look_up_class_and_title_when_needed():
    calls = []
    rules = FloatingRules({"executables": ["a.exe"], "classes": ["k"],
                           "title_regex": ["t"]})

    def klass():
        calls.append("class")
        return "k"

    def title():
        calls.append("title")
        return "t"

    assert rules.matches("a.exe", klass, title) and calls == []
    assert rules.matches("b.exe", klass, title) and calls == ["class"]
    assert FloatingRules().matches("a.exe", klass, title) is False


def test_floating_rules_tolerate_bad_config_shapes():
    assert FloatingRules("not a dict").matches("a.exe") is False
    rules = FloatingRules({"executables": "a.exe, b.exe", "classes": 5,
                           "title_regex": "one|two"})
    assert rules.matches("b.exe") and rules.matches("x.exe", title="Two")


def test_frame_insets_and_compensation_make_the_visible_frame_match():
    outer, visible = (95, 100, 810, 608), (102, 100, 796, 601)
    insets = frame_insets(outer, visible)
    assert insets == (7, 0, 7, 7)
    target = (0, 0, 800, 600)
    x, y, w, h = compensate(target, insets)
    assert (x, y, w, h) == (-7, 0, 814, 607)
    assert (x + insets[0], y + insets[1],
            w - insets[0] - insets[2], h - insets[1] - insets[3]) == target


def test_frame_insets_rejects_implausible_values():
    assert frame_insets((0, 0, 800, 600), (200, 200, 100, 100)) == (0, 0, 0, 0)
    assert frame_insets((10, 10, 100, 100), (5, 10, 100, 100)) == (0, 0, 0, 0)
    assert compensate((10, 20, 300, 200), (0, 0, 0, 0)) == (10, 20, 300, 200)

