# Phase 7 Summary: Floating Shell & WM Polish

## Completed
- **Floating shell & theme defaults:** `core/app_config.py` defaults to `shell_layout: "split"` and `theme: "harbor"`; `theme.py` refines `harbor` tokens and adds `QLabel#activeWindow` / `QPushButton#toolbarButton` QSS; `ui/toolbar.py` and `ui/dock.py` paint a rounded translucent pill surface and sync Win32 glass state; `widgets/apps.py` enlarges dock icons to `25x25` in `44x44` buttons.
- **Shared panel painter & Phase 4 overlays:** Added `paint_shell_panel` in `ui/popup.py` and wired it into `Toolbar`, `DesktopWidgetsWindow`, and `SwitcherDialog` (with `WA_TranslucentBackground` and parent stylesheet inheritance).
- **Phase 5 tiling rules:** Added `DEFAULT_FLOATING_EXECUTABLES` in `wm/rules.py` so shell overlays and core system utilities stay floating.

## Verification
- `pytest -q`: **140 passed** (including 3 new tests for floating shell defaults, default floating rules, and `SwitcherDialog` translucent backdrop).
- `ruff check .`: **All checks passed!**
