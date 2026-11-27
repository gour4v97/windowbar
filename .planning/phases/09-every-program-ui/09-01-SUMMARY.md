# Phase 9 Summary: Every-Program UI

## Completed
- **Win32 helpers (`native/windows.py`):** Added `toggle_maximize_window(hwnd)` and `window_process_path(hwnd)`.
- **Dynamic running programs (`widgets/apps.py`):** `AppsCard` now renders pinned apps plus any other running taskbar programs (excluding `windows bar.exe` / `windowsbar.exe`) with cached native `.exe` icons, active indicators, left-click focus/minimize, and right-click Focus / Minimize / Close / Pin to dock.
- **Active window controls (`ui/toolbar.py`):** Added `active_icon` and minimize/maximize/close `toolbarButton` controls bound to the current external foreground window.
- **Tests & locales:** Added `test_apps_card_shows_unpinned_running_programs` in `tests/test_core.py` and updated `locales/en.json` via `scripts/extract_strings.py --write`.
