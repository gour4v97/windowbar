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
Phase 1 is complete: all 28 configurable widgets now live in individual modules with module-level factories and are auto-discovered through the registry. The README count is reconciled: the calendar popup is a detail panel, not a separate widget. `windowsbar.py` delegates to `ui/dock.py`; config defaults live in `core/app_config.py`; native helpers live in `native/`; and the installer copies all package directories. Existing lifecycle, popup, logging, and taskbar crash-recovery work remains covered. Phase 2 added configurable pinned-app hotkeys, optional temperature sensor support, and detail popups for clock, system, media, and weather; DND and Night Light are documented as unsupported. Phase 3 is in progress: per-widget color/radius overrides can be edited from the dock menu and apply as scoped QSS. The separate settings window, multi-monitor bars, Toolbar/Dock split, and brightness flyout remain.
