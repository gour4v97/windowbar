# Windows Bar

A smart dock for Windows 10/11, written in Python (PySide6). It sits at the top
or bottom of the screen as a row of live cards — clock, calendar, media, system,
money, focus tools — and reserves screen space so maximised windows stop at the
dock instead of sliding under it.

No account, no telemetry, no server. Everything runs locally; each widget talks
only to its own service, and only if you turn it on.

## Install

```
pip install -r requirements.txt
pip install --only-binary=:all: -r requirements-media.txt   # optional: Now playing widget
python windowsbar.py
```

Open **Settings** from the dock menu to manage widgets, layout, themes, and hotkeys with a live preview. Right-click the dock for quick actions.
Settings live in `%APPDATA%\Windows Bar\config.json`.

In Settings → Layout, choose **Separate top toolbar and app dock** to put enabled information widgets in a top toolbar and pinned apps in a bottom dock. The default **Combined bar** keeps the current single-row layout.

## Widgets (28 configurable widgets)

The calendar popup is a detail panel on the Next event widget, not a separate widget. Pinned-app shortcuts default to `Alt+1` through `Alt+9`; change the modifier from the dock menu. Temperature is optional; for Windows hardware sensors, run LibreHardwareMonitor and install `wmi` with `pip install -r requirements-temperature.txt`.

| Widget | How it works |
|---|---|
| App launcher | pinned apps, edit `apps` in config.json. Running apps get a dot: click focuses (or minimises) instead of relaunching; right-click for Open new / Focus / Minimize / Close. `Alt+1`…`Alt+9` open or switch to them by default; change the modifier in the dock menu |
| Open windows | buttons for your open windows; click one to bring it to front |
| Clock, CPU/RAM/network, Battery | built in |
| Weather | Open-Meteo, no API key; detail popup shows the current city and conditions, with refresh and city controls |
| Now playing | Windows media session; click opens details and play/pause (needs `winsdk`) |
| Next event | paste your calendar's secret iCal link (Google, Outlook, iCloud) |
| Quick actions | Lock, Dark/Light theme, Empty Recycle Bin (with confirmation), Open any file/folder path, Power menu (Sleep, Sign out, Restart, Shut down) |
| Recycle Bin | item count; click to empty |
| Downloads | files added in the last 24h and the newest file; click to open the folder |
| Screenshots | same idea for `Pictures\Screenshots` |
| Screen time | seconds per focused app today; idle time not counted; data kept 14 days |
| GitHub | public repos and followers; set your username from the menu |
| Stripe revenue | available balance; set your key in the `WINDOWSBAR_STRIPE_KEY` environment variable |
| Notes | several notes; click opens the notes panel (pick, edit, add, delete) |
| Focus / Stopwatch / Todos | click to use; double-click resets. Todos open a full panel: check to complete, completed ones sink below, delete per row |
| Timer | plain countdown; click start/pause, double-click sets the minutes |
| World clocks | up to three IANA time zones (menu sets them) |
| Day / week / year progress | rotating progress bars for the period |
| Storage | disk used % and free space for the system drive |
| Temperature | first available hardware sensor; optional and may report unavailable without a sensor provider |
| Network | Wi-Fi name, local IP, live up/down speeds |
| Volume | output volume; click mutes, scroll adjusts |
| Quick toggles | Wi-Fi, Bluetooth and airplane mode (needs `winsdk`, same as Now playing), keep-awake, mute. Do Not Disturb and Night Light are not included because Windows does not expose a stable supported API. |
| Script | first two lines of your own shell command's output, refreshed on a timer; optional click command. Menu: "Set script command…" (`script_command`, `script_interval`, `script_click_command` in config) |
| Calendar popup | click the Next event card for a month view with event days marked |

## Options

- **Top or bottom** — from the menu, or just drag the dock to a screen edge and it snaps there
- **Reserve screen space** so maximised windows stop at the dock
- **Full width** or a centred pill
- **Auto-hide the Windows taskbar** while the dock runs — the taskbar's original state is restored on quit, and on the next start after a crash
- **Glass effect** — acrylic / DWM backdrop on Windows 11, acrylic accent on older builds
- **Themes** — built-in default, glass, light, and dark themes; JSON theme files can override colors, radius, font, spacing, and blur
- **Widget styles** — use the Widget styles menu to set each widget’s accent, card background, text, button color, and corner radius
- **Pause music before meetings** — pauses playback one minute before your next calendar event
- **Quiet hours** (e.g. `23:00-07:00`) — the focus timer finishes silently
- **Start with Windows** — adds/removes a Run key for the current user
- **Auto-hide dock** — slides off screen after a few seconds away from it (delay settable, default 5s), and immediately when a fullscreen app (game, video, presentation) takes the screen; the reserved space is released while it is hidden, and it slides back when you touch the screen edge where it sits
- **Clock style** — digital, or an analogue face (menu toggle)
- **Presets** — one-click widget sets: Essentials, Focus, Creator, Everything

## Launcher, themes and accent (Seelen-style)

- **Launcher** — press `Alt+Space` anywhere. Fuzzy-search your apps, Start Menu programs and open windows; `↑ ↓` to pick, `Enter` to run, `Esc` to close. Type `> command` to run a shell command, `= 2*(3+4)` (or just `2*(3+4)`) to calculate (Enter copies the result), or a path to open it. Change the key with `launcher_hotkey` in config.json (e.g. `ctrl+shift+k`); turn it off from the menu.
- **Themes** — menu > Theme: midnight (default), daylight, aurora, rose, mono. Add your own as JSON in `%APPDATA%\Windows Bar\themes\` (menu > Theme > Open themes folder creates an example). A theme only lists the keys it changes: `panel`, `glass`, `border`, `card`, `text`, `muted`, `button`, `accent` (`"#rrggbb"` or `[r,g,b,a]`, alpha 0-255), `radius`, `panel_radius`, `font`.
- **Custom CSS** — drop a `custom.qss` into `%APPDATA%\Windows Bar\` and it is applied on top of the theme (Qt style sheets, a CSS subset).
- **Dynamic accent** — the accent colour is derived from your wallpaper and follows it when it changes (hover, focused window, launcher selection). Turn it off in the menu to use the theme's own accent.
- The open-windows widget now behaves like a taskbar (no hidden/cloaked windows) and highlights the focused window.

## Performance

- Native window-reservation calls are made only when the dock's size/edge actually changes, not on every digit change (this was the main source of lag: it made other windows re-layout).
- Widgets with changing numbers keep a stable width, so the dock no longer jitters.
- Slow Windows calls (window list, Recycle Bin count) run in background threads, never on the UI thread.
- Background work only runs for widgets that are switched on (weather, calendar, media, GitHub, Stripe, folder scans stop when their widget is off).
- The dock background is cached instead of repainted from scratch; the auto-hide watcher only runs when auto-hide is on; cards stop updating while the dock is slid away (timers stay accurate).
- Large calendars are parsed incrementally and old one-off events are dropped early.

## Files

- `windowsbar.py` — application entry point
- `ui/dock.py` — dock behavior and quick menu
- `ui/settings.py` — separate live Settings window
- `launcher.py` — the Alt+Space launcher and global hotkey
- `theme.py` — themes, QSS builder, wallpaper accent (pure Python)
- `search.py` — fuzzy search, Start Menu scan, hotkey parsing, safe calculator (pure Python)
- `services.py` — background sources: weather, calendar (iCal + recurrence), media session, Wi-Fi/Bluetooth radios
- `extras.py` — screen time, GitHub, Stripe, folder stats, disk/progress/script/network helpers, background poller
- `winapi.py` — Windows-only native helpers (AppBar reservation, glass, taskbar state, open windows, volume, power, autostart); safe no-ops elsewhere
- `tests/` — parser/recurrence/folder tests that run anywhere: `pytest -q`


## License

MIT — see [LICENSE](LICENSE).

