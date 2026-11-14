"""TilingManager logic with a fake window layer.

Needs PySide6 (for QObject/QTimer) but not Windows: the Win32 helpers are
replaced by an in-memory fake, so layout choice, floating rules and resize
behaviour can be checked anywhere.
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

EXE = {1: "code.exe", 2: "chrome.exe", 3: "calc.exe", 4: "term.exe"}
CLASS = {1: "A", 2: "B", 3: "CalcWnd", 4: "D"}
TITLE = {1: "x", 2: "Picture in picture", 3: "c", 4: "d"}
AREA = (0, 0, 1920, 1040)
AREA_KEY = "0,0,1920,1040"


class _Signal:
    def connect(self, _callback):
        pass


class _Tracker:
    windows = [(1, "a"), (2, "b"), (3, "c"), (4, "d")]
    foreground_hwnd = 1
    windows_changed = _Signal()
    foreground_changed = _Signal()


def _manager(monkeypatch, **kwargs):
    import wm.tiling as tiling
    # QApplication, not QCoreApplication: the offscreen Qt tests need a real
    # QApplication in this process, and Qt allows only one app object.
    if QtWidgets.QApplication.instance() is None:
        QtWidgets.QApplication([])
    moves = {}
    fake = types.SimpleNamespace(
        IS_WIN=True, is_window=lambda h: True,
        window_is_minimized=lambda h: False,
        window_rect=lambda h: (0, 0, 500, 400),
        window_work_area=lambda h: AREA,
        window_state=lambda h: ((0, 0, 500, 400), False, False),
        window_process_name=lambda h: EXE[h],
        window_class_name=lambda h: CLASS[h],
        window_title=lambda h: TITLE[h],
        move_window_visible_rect=lambda h, r: moves.__setitem__(h, r) or True,
        move_window_rect=lambda h, r: True,
        restore_window_state=lambda h, s: True,
        focus_window=lambda h: None)
    monkeypatch.setattr(tiling, "winapi", fake)
    monkeypatch.setattr(tiling, "sys", types.SimpleNamespace(platform="win32"))
    saved = []
    options = dict(gap=0, padding=0, workspace_layouts={},
                   on_change=lambda: saved.append(1))
    options.update(kwargs)
    return tiling.TilingManager(_Tracker(), **options), moves, saved


def test_floating_apps_and_title_rules_exclude_windows(monkeypatch):
    manager, moves, _ = _manager(
        monkeypatch, floating_apps=["calc.exe"],
        floating_rules={"title_regex": ["picture"]})
    manager.apply_layout()
    assert set(moves) == {1, 4}
    assert moves[1] == (0, 0, 960, 1040) and moves[4] == (960, 0, 960, 1040)


def test_cycle_layout_changes_geometry(monkeypatch):
    manager, moves, _ = _manager(monkeypatch, floating_apps=["calc.exe", "chrome.exe"])
    assert manager.cycle_layout() == "Columns" and manager.layout == "columns"
    manager.apply_layout()
    assert moves[1][2] == 960 and moves[4][0] == 960
    assert manager.cycle_layout() == "Master / stack"
    assert manager.cycle_layout() == "BSP"


def test_columns_start_equal_not_lopsided(monkeypatch):
    manager, moves, _ = _manager(monkeypatch, layout="columns",
                                 floating_apps=["calc.exe"])
    manager.apply_layout()                      # 3 tiled windows: 1, 2, 4
    widths = [moves[h][2] for h in (1, 2, 4)]
    assert max(widths) - min(widths) <= 1


def test_stack_resize_grows_master_when_master_is_focused(monkeypatch):
    manager, moves, _ = _manager(monkeypatch, layout="stack",
                                 floating_apps=["calc.exe", "chrome.exe"])
    manager.apply_layout()
    manager.resize_focused(0.1)
    ratios = manager.workspace_layouts["default"]["ratios"]
    assert abs(ratios[AREA_KEY + "|stack"] - 0.7) < 1e-9
    manager.apply_layout()
    assert moves[1][2] == 1344


def test_resize_on_a_stack_window_shrinks_the_master(monkeypatch):
    manager, _, _ = _manager(monkeypatch, layout="stack",
                             floating_apps=["calc.exe"])
    _Tracker.foreground_hwnd = 4
    try:
        manager.apply_layout()
        manager.resize_focused(0.1)
    finally:
        _Tracker.foreground_hwnd = 1
    ratios = manager.workspace_layouts["default"]["ratios"]
    assert abs(ratios[AREA_KEY + "|stack"] - 0.5) < 1e-9


def test_ratios_do_not_leak_between_layouts(monkeypatch):
    manager, _, _ = _manager(monkeypatch, floating_apps=["calc.exe", "chrome.exe"])
    manager.apply_layout()
    manager.resize_focused(0.1)                 # BSP ratio, original key
    ratios = manager.workspace_layouts["default"]["ratios"]
    assert AREA_KEY in ratios and AREA_KEY + "|columns" not in ratios
    manager.set_layout("columns")
    manager.apply_layout()
    assert AREA_KEY + "|columns" not in ratios   # columns still on its default


def test_rules_can_be_replaced_and_invalid_patterns_are_reported(monkeypatch):
    manager, moves, _ = _manager(monkeypatch, floating_apps=["calc.exe"])
    manager.set_floating_rules({"title_regex": ["(bad"], "classes": ["D"]})
    assert manager.invalid_title_patterns == ["(bad"]
    manager.apply_layout()
    assert set(moves) == {1, 2}

