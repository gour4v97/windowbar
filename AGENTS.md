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
Phase 1 has versioned config storage in `core/config.py`, a registry and lifecycle adapter in `core/registry.py`, and standalone modules for Clock, Weather, and Notes under `widgets/`. The current 28 cards are registered through the compatibility adapter. Config migration and registry lifecycle tests are present. Next: tighten hidden/disabled widget shutdown behavior and move data-source ownership into widget lifecycle hooks; then port the remaining cards module by module.
