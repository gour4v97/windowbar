# Project handoff

## Current product
The repository is `gour4v97/windowbar`; the product is **Windows Bar**. It is a Python/PySide6 Windows 10/11 dock. The README documents 28 configurable widgets plus a calendar popup and a launcher, themes, wallpaper accent, media, and quick toggles.

## Development
- Install: `pip install -r requirements.txt`
- Run: `python windowsbar.py`
- Tests: `pytest -q` (`tests/test_core.py`, cross-platform intent)
- User config: `%APPDATA%\Windows Bar\config.json`
- Logs: `%APPDATA%\Windows Bar\logs\windowsbar.log` (rotates at 1 MiB, four backups)
- Stripe secret: `WINDOWSBAR_STRIPE_KEY`; never commit credentials or personal config.

## Guardrails
- Reimplement capabilities; do not copy Seelen UI code/assets (AGPL-3.0) or Dockyard code (unlicensed).
- Keep Win32 access in the native helper layer (`winapi.py`); no blocking/network work on the UI thread.
- Any taskbar hiding or reserving screen space must be restorable after a crash.
- New features need a platform-independent test where practical.

## Session handoff
Phase 1 is complete: all 28 configurable widgets now live in individual modules with module-level factories and are auto-discovered through the registry. The README count is reconciled: the calendar popup is a detail panel, not a separate widget. `windowsbar.py` delegates to `ui/dock.py`; config defaults live in `core/app_config.py`; native helpers live in `native/`; and the installer copies all package directories. Existing lifecycle, popup, logging, and taskbar crash-recovery work remains covered. Phase 2 added configurable pinned-app hotkeys, optional temperature sensor support, and detail popups for clock, system, media, and weather; DND and Night Light are documented as unsupported. Phase 3 is complete: built-in themes and scoped per-widget color/radius overrides are available, Settings is a separate live window, multi-monitor docks and profiles are supported, and split Toolbar/Dock layout and brightness flyout are implemented. Phase 4 feature implementation is present: virtual desktop actions and viewer, per-desktop wallpaper action, an opt-in dedicated-thread Alt+Tab switcher, and a draggable theme-aware desktop clock/system panel. Interactive verification remains pending: this session's `pyvda` COM activation returns access denied, and UI automation could not target the isolated Qt dock/panel for live layer and key-navigation checks. Phase 5 now includes an opt-in BSP tiler backed by the native window-event tracker, per-monitor BSP/Columns/Master-stack layouts, configurable spacing, keyboard focus/swap/resize, floating executable/class/title-regex rules, adjacent virtual desktop movement, per-desktop order/ratio persistence, and a Ctrl+Alt+Esc release key. Native HWND tiling/restoration and BSP persistence smoke checks pass. The current session denies pyvda COM access and `RegisterHotKey` returns Win32 error 5, so the app refuses to enable tiling because it cannot guarantee emergency release; live workspace movement is unverified.
