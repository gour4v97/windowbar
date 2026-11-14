# Windows Bar

A smart dock for Windows 10/11, written in Python (PySide6). It sits at the top
or bottom of the screen as a row of live cards — clock, calendar, media, system,
money, focus tools — and reserves screen space so maximised windows stop at the
dock instead of sliding under it.

No account, no telemetry, no server. Everything runs locally.

## Install

```
pip install -r requirements.txt
pip install --only-binary=:all: -r requirements-media.txt   # optional: Now playing widget
python windowsbar.py
```

Open **Settings** from the dock menu to manage widgets, layout, themes, and hotkeys with a live preview. Right-click the dock for quick actions.
Settings live in `%APPDATA%\Windows Bar\config.json`.


Windows Bar starts a bar on each connected display, each with its own Settings window and saved widget/layout profile.

## Widgets (28 configurable widgets)


| Widget | How it works |
|---|---|
| App launcher | pinned apps, edit `apps` in config.json. Running apps get a dot: click focuses (or minimises) instead of relaunching; right-click for Open new / Focus / Minimize / Close. `Alt+1`…`Alt+9` open or switch to them by default; change the modifier in the dock menu |
| Open windows | buttons for your open windows; click one to bring it to front |
| Weather | Open-Meteo, no API key; detail popup shows the current city and conditions, with refresh and city controls |
| Now playing | Windows media session; click opens details and play/pause (needs `winsdk`) |
| Next event | paste your calendar's secret iCal link (Google, Outlook, iCloud) |
| Quick actions | Lock, Dark/Light theme, Empty Recycle Bin (with confirmation), Open any file/folder path, Power menu (Sleep, Sign out, Restart, Shut down) |
| Recycle Bin | item count; click to empty |
| Downloads | files added in the last 24h and the newest file; click to open the folder |
| Screenshots | files added in the last 24h in `Pictures\Screenshots` |
| Screen time | seconds per focused app today; idle time not counted; data kept 14 days |
| GitHub | public repos and followers; set your username from the menu |
| Stripe revenue | available balance; set your key in the `WINDOWSBAR_STRIPE_KEY` environment variable |
| Notes | several notes; click opens the notes panel (pick, edit, add, delete) |
| Focus / Stopwatch / Todos | click to use; double-click resets. Todos open a full panel: check to complete, completed ones sink below, delete per row |
| Timer | plain countdown; click start/pause, double-click sets the minutes |
| World clocks | up to three IANA time zones (menu sets them) |
| Day / week / year progress | rotating progress bars |
| Storage | disk used % and free space for the system drive |
| Temperature | first available hardware sensor; optional and may report unavailable without a sensor provider |
| Network | Wi-Fi name, local IP, live up/down speeds |
| Volume | click opens volume and supported internal-display brightness sliders; right-click mutes, scroll adjusts volume |
| Quick toggles | Wi-Fi, Bluetooth and airplane mode (needs `winsdk`, same as Now playing), keep-awake, mute. Do Not Disturb and Night Light are not included because Windows does not expose a stable supported API. |
| Script | first two lines of your own shell command's output, refreshed on a timer; optional click command. Menu: "Set script command…" (`script_command`, `script_interval`, `script_click_command` in config) |
| Calendar popup | click the Next event card for a month view with event days marked |

## Options

- **Arrange widgets** — Settings → Widgets → Arrange widget order
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

## Launcher, themes and accent

- **Launcher** — press `Alt+Space` anywhere. Fuzzy-search your apps, Start Menu programs and open windows; `↑ ↓` to pick, `Enter` to run, `Esc` to close. Type `> command` to run a shell command, `= 2*(3+4)` (or just `2*(3+4)`) to calculate (Enter copies the result), or a path to open it. Change the key with `launcher_hotkey` in config.json (e.g. `ctrl+shift+k`); turn it off from the menu.
- **Themes** — menu > Theme: midnight (default), daylight, aurora, rose, mono. Add your own as JSON in `%APPDATA%\Windows Bar\themes\` (menu > Theme > Open themes folder creates an example). A theme only lists the keys it changes: `panel`, `glass`, `border`, `card`, `text`, `muted`, `button`, `accent` (`"#rrggbb"` or `[r,g,b,a]`, alpha 0-255), `radius`, `panel_radius`, `font`.
- **Theme gallery** — starter `nord`, `forest`, and `ember` JSON themes live in [`themes/gallery/`](themes/gallery/); copy a JSON file into `%APPDATA%\Windows Bar\themes\` to use it.
- **Widget contributions** — see [docs/widget-sdk.md](docs/widget-sdk.md).
- **Custom CSS** — drop a `custom.qss` into `%APPDATA%\Windows Bar\` and it is applied on top of the theme (Qt style sheets, a CSS subset).
- **Dynamic accent** — the accent colour is derived from your wallpaper and follows it when it changes (hover, focused window, launcher selection). Turn it off in the menu to use the theme's own accent.

## Workspaces (Phase 4)

Open **Workspaces…** from the dock menu or the split toolbar. The viewer lists Windows virtual desktops, switches between them, creates/removes desktops, renames them, assigns an emoji or symbol, moves the last active app window, and sets a per-desktop wallpaper on supported Windows 11 builds. Virtual desktop support uses the [MIT-licensed `pyvda` package](https://github.com/mirober/pyvda); if its Windows interface is unavailable, previous/next/create actions fall back to Windows keyboard shortcuts and window movement/removal report the limitation.

To try the custom window switcher, enable **Settings → Hotkeys → Use Windows Bar window switcher for Alt+Tab**. Alt+Tab and Alt+Shift+Tab cycle, arrow keys move through the list, Enter or releasing Alt switches, and Esc cancels. The hook runs on a dedicated thread and is disabled by default.

Enable **Settings → Layout → Show draggable desktop widgets** to show a small clock and CPU/RAM/network panel on the primary display. Drag the panel to reposition it; its location is saved per display. It is placed at the bottom of the window z-order so ordinary app windows cover it.

Phase 5 includes opt-in BSP, Columns, and Master / stack tiling in **Settings → Window manager**. While enabled, **Ctrl+Alt+J** focuses the next tiled window, **Ctrl+Alt+K** swaps its BSP slot, **Ctrl+Alt+H/L** adjusts the focused split (the first column in Columns, the master in Master / stack), **Ctrl+Alt+T** cycles the layout, **Ctrl+Alt+F** toggles floating, and **Ctrl+Alt+Shift+Left/Right** moves the focused window between virtual desktops when the Windows COM API is available. **Ctrl+Alt+Esc** releases windows and restores their saved positions.

## Backup and move your settings

Settings are stored in `%APPDATA%\Windows Bar\config.json`. Close Windows Bar, then use:

```
python windowsbar.py --export-config my-settings.json
python windowsbar.py --import-config my-settings.json
```

Export leaves private values (your calendar link) blank unless you add `--include-private`. Import validates the file first and keeps your previous settings as `config.before-import.bak`. When an update changes the settings format, the old file is kept once as `config.pre-v<N>.bak` before it is rewritten.

## Performance

- Native window-reservation calls are made only when the dock's size/edge actually changes, not on every digit change.
- Widgets with changing numbers keep a stable width.
- Slow Windows calls (window list, Recycle Bin count) run in background threads, never on the UI thread.
- Background work only runs for widgets that are switched on (weather, calendar, media, GitHub, Stripe, folder scans stop when their widget is off).
- The dock background is cached instead of repainted from scratch; cards stop updating while the dock is slid away (timers stay accurate).
- Large calendars are parsed incrementally and old one-off events are dropped early.

## License

MIT — see [LICENSE](LICENSE).

