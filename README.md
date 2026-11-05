# Winyard

A smart dock for Windows 10/11, written in Python (PySide6). It sits at the top
or bottom of the screen as a row of live cards — clock, calendar, media, system,
money, focus tools — and reserves screen space so maximised windows stop at the
dock instead of sliding under it.

No account, no telemetry, no server. Everything runs locally; each widget talks
only to its own service, and only if you turn it on.

## Install

**Easy way (Windows):** download the release zip, unzip it, and double-click
`setup.bat`. It installs per-user into `%LOCALAPPDATA%\\Winyard` (own venv,
Start Menu shortcut, no admin needed). Remove with `setup.bat --uninstall`.

**From source:**

```
pip install -r requirements.txt
python winyard.py
```

Right-click the dock for the menu: choose widgets, position, and options.
Settings live in `%APPDATA%\Winyard\config.json`.

## Widgets (20)

| Widget | How it works |
|---|---|
| App launcher | edit `apps` in config.json |
| Open windows | buttons for your open windows; click one to bring it to front |
| Clock, CPU/RAM/network, Battery | built in |
| Weather | Open-Meteo, no API key; asks for your city |
| Now playing | Windows media session; click = play/pause (needs `winsdk`) |
| Next event | paste your calendar's secret iCal link (Google, Outlook, iCloud) |
| Quick actions | Lock, Dark/Light theme, Empty Recycle Bin (with confirmation), Open any file/folder path |
| Recycle Bin | item count; click to empty |
| Downloads | files added in the last 24h and the newest file; click to open the folder |
| Screenshots | same idea for `Pictures\Screenshots` |
| Screen time | seconds per focused app today; idle time not counted; data kept 14 days |
| GitHub | public repos and followers; set your username from the menu |
| Stripe revenue | available balance; set your key in the `WINYARD_STRIPE_KEY` environment variable |
| Notes | click to edit |
| Focus / Stopwatch / Todos | click to use; double-click resets; right-click a todo completes it |

## Options

- **Top or bottom** — from the menu, or just drag the dock to a screen edge and it snaps there
- **Reserve screen space** so maximised windows stop at the dock
- **Full width** or a centred pill
- **Auto-hide the Windows taskbar** while the dock runs — the taskbar's original state is restored on quit, and on the next start after a crash
- **Glass effect** — acrylic / DWM backdrop on Windows 11, acrylic accent on older builds
- **Pause music before meetings** — pauses playback one minute before your next calendar event
- **Quiet hours** (e.g. `23:00-07:00`) — the focus timer finishes silently
- **Start with Windows** — adds/removes a Run key for the current user
- **Auto-hide dock** — slides off screen after a few seconds away from it (delay settable, default 5s), and immediately when a fullscreen app (game, video, presentation) takes the screen; the reserved space is released while it is hidden, and it slides back when you touch the screen edge where it sits

## Files

- `winyard.py` — the dock, cards and menu (UI)
- `services.py` — background sources: weather, calendar (iCal + recurrence), media session
- `extras.py` — screen time, GitHub, Stripe, folder stats, background poller
- `winapi.py` — Windows-only native helpers (AppBar reservation, glass, taskbar state, open windows, autostart); safe no-ops elsewhere
- `tests/` — parser/recurrence/folder tests that run anywhere: `pytest -q`


## License

MIT — see [LICENSE](LICENSE).
