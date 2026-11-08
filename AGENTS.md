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
Phase 0 docs and the source audit are prepared. Phase 1 config persistence now lives in `core/config.py` (schema v1), and `core/registry.py` introduces a widget lifecycle contract currently bridged to the existing card classes. All 28 current card factories register through the registry. Config migration, persistence, and registry lifecycle tests are added. Next: port Clock, Weather, and Notes into independent widget modules, then move their polling/service ownership into widget start/stop hooks.
