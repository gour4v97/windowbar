# Project handoff

## Current product
The repository is `gour4v97/windowbar`; the product is **Windows Bar**. It is a Python/PySide6 Windows 10/11 dock. The README documents 28 widgets plus a launcher, themes, wallpaper accent, media, and quick toggles.

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
Phase 1 now includes schema-v1 config storage, a widget registry/lifecycle adapter, standalone Clock/Weather/Notes modules, stoppable background workers, the reusable detail popup, rotating file logs, and a tested taskbar auto-hide crash-recovery path. Tests pass locally. The `winapi.py` implementation has been split into `native/appbar.py`, `native/glass.py`, `native/system.py`, and `native/audio.py`, with `native/windows.py` and the root `winapi.py` preserving compatibility. All widget card groups now live in `widgets/` modules, popup panels live in `ui/panels.py`, the app hotkey filter lives in `ui/hotkeys.py`, and the compatibility card adapter lives in `core/registry.py`. Remaining Phase 1 work is to move Dock orchestration and application startup/configuration glue out of `windowsbar.py` without changing behavior.
