# Phase 0 source audit

Audit scope: GitHub `gour4v97/windowbar` default branch snapshot fetched 2026-11-08. The supplied handoff ZIP is an older project snapshot and does not match this source in identity or feature count.

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

Line counts use newline-delimited source; generated/install artifacts excluded.

## Untested / Windows-only areas

- `tests/test_core.py` covers iCal parsing/recurrence, weather-code labels, downloads summaries, duration formatting, theme resolution/QSS/accent, fuzzy search/hotkey parsing/calculator, progress and disk/network summaries, shell helper validation, todo/note normalization, and executable parsing.
- No UI integration tests are present for the 2,108-line `windowsbar.py`; no direct tests cover launcher UI or registered native hotkeys. Config migration/save and registry lifecycle tests have since been added.
- `winapi.py` contains Win32 AppBar reservation, DWM backdrop/glass, taskbar auto-hide state, shell/recycle-bin, registry/theme, audio COM, power, window enumeration/focus, wallpaper, and Run-key helpers. These require Windows and several lack isolated tests.
- `launcher.py` registers global hotkeys through `ctypes.windll.user32`; application launch uses Windows `os.startfile`.
- `services.py` optionally loads Windows media-session and radio APIs through `winsdk`/`winrt`; `requirements-media.txt` marks `winsdk` as Windows/Python-version conditional.
- `extras.py` mostly provides portable helpers but imports `winapi` and has OS-dependent network/script behavior.
- `windowsbar.py` and UI widgets use PySide6; the actual dock behavior is Windows-specific even though helper tests aim to run cross-platform.

## Roadmap reconciliation

The initial source had 27 widget IDs and the calendar popup was a detail panel; Phase 2 added an optional Temperature widget, bringing the registry to 28 configured widget IDs. and already documents a launcher, theme JSON/QSS, custom CSS, wallpaper-derived accent, pinned-app running indicators/hotkeys, world clocks, timer, disk/storage, volume, quick toggles, and background polling. Several Phase 2/3 roadmap bullets were already partially or fully present. Phase 1 has now delivered the architecture split, widget registry/contract, versioned config migration, and popup framework. Independent per-monitor bars and a separate settings window remain future work.

The source, config path, installer, README, and Stripe environment variable now consistently use the product name **Windows Bar**. The roadmap naming decision is to keep the repository `windowbar` and the product name Windows Bar.

## Phase 0 status

- Source audit: complete for file layout and test/native boundary; behavior review still needed.
- CI workflow and checkpoint script: prepared locally.
- Roadmap/handoff reconciliation: prepared locally; naming and target baseline need owner decision.
- GitHub issues and `v0.1.0` tag remain outstanding. This source snapshot was fetched as an archive without Git history; Phase 1 changes are being pushed through a GitHub feature branch.


