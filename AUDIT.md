# Phase 0 source audit

Audit scope: GitHub `gour4v97/windowbar` default branch snapshot fetched 2026-11-08.

## Baseline

| File | Lines |
|---|---:|
| `windowsbar.py` | 2,130 |
| `winapi.py` | 589 |
| `services.py` | 414 |
| `setup_windowsbar.py` | 293 |
| `extras.py` | 253 |
| `launcher.py` | 224 |
| `theme.py` | 159 |
| `search.py` | 128 |
| `tests/test_core.py` | 192 |
| `README.md` | 96 |


## Untested / Windows-only areas

- `tests/test_core.py` covers parsers, theme/QSS, search/calculator, and helper summaries (see the test file for the full list).
- No UI integration tests are present for the dock UI; no direct tests cover launcher UI or registered native hotkeys. Config migration/save and registry lifecycle tests have since been added.
- `winapi.py` contains the Win32 helpers (AppBar, glass, taskbar, audio COM, power, windows, wallpaper, Run key). These require Windows and several lack isolated tests.
- `launcher.py` registers global hotkeys through `ctypes.windll.user32`; application launch uses Windows `os.startfile`.
- `services.py` optionally loads Windows media-session and radio APIs through `winsdk`/`winrt`; `requirements-media.txt` marks `winsdk` as Windows/Python-version conditional.
- `extras.py` mostly provides portable helpers but imports `winapi` and has OS-dependent network/script behavior.
- `windowsbar.py` and UI widgets use PySide6; the actual dock behavior is Windows-specific even though helper tests aim to run cross-platform.

## Roadmap reconciliation

The initial source had 27 widget IDs; Phase 2 added an optional Temperature widget, bringing the registry to 28. Phase 1 delivered the architecture split, widget registry/contract, versioned config migration, and popup framework.

