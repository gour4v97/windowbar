# Windows Bar

**Windows Bar** (`gour4v97/windowbar`) is a customizable Python/PySide6 smart dock and desktop shell for Windows 10/11 (MIT).

## Architecture
- `windowsbar.py` — entrypoint
- `core/` — config, migrations, widget registry, i18n, plugin loader (`PLUGIN_API = 2`)
- `native/` — Win32 helpers (`appbar`, `glass`, `taskbar`, `windows`, `hooks`, `vdesktop`, `audio`)
- `ui/` — dock, top toolbar, desktop widgets, Alt+Tab switcher, workspaces, flyouts, settings
- `wm/` — opt-in BSP / columns / master-stack tiling window manager and floating rules
- `widgets/` — 28 auto-discovered widget modules
- `tests/` — offscreen Qt + pure-Python test suite (`pytest -q`)
