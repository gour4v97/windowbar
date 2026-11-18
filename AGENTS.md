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
Phase 6 progress: runtime plugin loader (`PLUGIN_API = 2` frozen, per-plugin allow-list, live reload), CLI config export/import, Settings > General (language, plugins), PyInstaller standalone build verified (`dist/Windows Bar/Windows Bar.exe`), Inno Setup and winget templates written. All UI strings routed through `tr()`; Hindi locale reviewed and supported (228/228 keys). Full test suite: 136 tests passing (100% green). Example plugin `hello_plugin.py` installed and verified in `%APPDATA%\Windows Bar\plugins`. Remaining for release: live manual click-through on Windows (Alt+Tab hook, tiling hotkeys, Settings tabs), recording demo GIF/screenshots, re-authenticating GitHub CLI (`gh auth login`) to push and tag `v0.1.0`/`v0.2.0`, and filling winget manifest hashes.
