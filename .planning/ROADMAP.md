# GSD Roadmap

- **Phases 1–6:** Complete (modular core, Dockyard-style widgets, theming engine, split toolbar/dock, launcher, flyouts, virtual desktops, Alt+Tab, desktop widgets, BSP/columns/stack tiling, plugins, i18n, packaging). See root `ROADMAP.md` for historical details.
- **Phase 7: Floating Shell & WM Polish** *(in progress)*
  - Floating pill toolbar with glass/acrylic backdrop and refined `harbor` default theme
  - Theme-matched `paintEvent` on `DesktopWidgetsWindow` and `SwitcherDialog` (Alt+Tab)
  - Built-in default floating exclusions in `wm/rules.py` so shell overlays and system dialogs are never tiled
  - Regression tests for all new behavior + ruff & pytest verification
