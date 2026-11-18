# Project handoff

## Current product
The repository is `gour4v97/windowbar`; the product is **Windows Bar**. It is a Python/PySide6 Windows 10/11 dock.

## Development
- Install: `pip install -r requirements.txt`
- Run: `python windowsbar.py`
- Tests: `pytest -q` (`tests/test_core.py`, cross-platform intent)
- User config: `%APPDATA%\Windows Bar\config.json`
- Logs: `%APPDATA%\Windows Bar\logs\windowsbar.log`
- Stripe secret: `WINDOWSBAR_STRIPE_KEY`; never commit credentials or personal config.

## Guardrails
- Reimplement capabilities; do not copy Seelen UI code/assets (AGPL-3.0) or Dockyard code (unlicensed).
- Keep Win32 access in the native helper layer (`native/`); no blocking/network work on the UI thread.
- Any taskbar hiding or reserving screen space must be restorable after a crash.
- New features need a platform-independent test where practical.

## Session handoff
Phase 6 begun: runtime plugin loader (opt-in, API v1 unstable, no sandbox), CLI config export/import, Settings > General (language, plugins), PyInstaller/Inno/winget packaging (unbuilt, unsigned), tag-triggered release workflow. All UI strings routed through `tr()`; Hindi locale reviewed (Hinglish mix, commit `bc80ae3`) and supported. `PLUGIN_API = 2` frozen (`get_config`/`tokens`/`app_dir`/`logger` guaranteed; Dock forwarding deprecated); per-plugin allow-list via `plugins_allowed` in config.json (`null` = allow all), checked before import. Offscreen Qt tests cover the Settings window (14 tests, incl. the Arrange widgets dialog); Linux CI job is blocking and green (run 254). Keyboard paths (C3): clickable cards focusable with Enter/Space to activate, Shift+Enter for reset/set-minutes, Ctrl+Alt+D focuses the dock, Alt+Up/Down moves Arrange rows. Still unverified on Windows: Settings tab click-through, plugin end-to-end, installer builds, Ctrl+Alt+D registration. Live reload (C4): language/plugin changes apply without a restart.
