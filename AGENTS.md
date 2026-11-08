# Project handoff

## Current product
The repository is `gour4v97/windowbar`; the product is **Windows Bar**. It is a Python/PySide6 Windows 10/11 dock. The README documents 28 widgets plus a launcher, themes, wallpaper accent, media, and quick toggles.

## Development
- Install: `pip install -r requirements.txt`
- Run: `python windowsbar.py`
- Tests: `pytest -q` (`tests/test_core.py`, cross-platform intent)
- User config: `%APPDATA%\Windows Bar\config.json`
- Stripe secret: `WINDOWSBAR_STRIPE_KEY`; never commit credentials or personal config.

## Guardrails
- Reimplement capabilities; do not copy Seelen UI code/assets (AGPL-3.0) or Dockyard code (unlicensed).
- Keep Win32 access in the native helper layer (`winapi.py`); no blocking/network work on the UI thread.
- Any taskbar hiding or AppBar reservation must have a recovery path.
- New features need a platform-independent test where practical.

## Session handoff
Phase 1 has schema-v1 config storage, a widget registry/lifecycle adapter, standalone Clock/Weather/Notes modules, stoppable background workers, and the reusable monitor-aware popup in `ui/popup.py`. Tests cover config migration, registry and worker lifecycle, and popup placement. Remaining Phase 1 work: split the rest of `windowsbar.py`/`winapi.py`, then add file logging and a crash-safe taskbar restore test. The next checklist item is logging plus the restore test.
