> **Current baseline (2026-11-08):** Product name is Windows Bar; repository remains `gour4v97/windowbar`. The existing source documents 28 configurable widgets plus a calendar detail popup and already includes a launcher, theme engine, wallpaper accent, and several Phase 2 features. The matrix is being reconciled against the source; see `AUDIT.md`.
# Windows Bar Roadmap

Goal: grow Windows Bar from a single smart dock into a full, customizable Windows desktop shell with the same *feature set* as [Seelen UI](https://github.com/eythaann/seelen-ui), plus the smart-dock extras from [Dockyard](https://github.com/aryansoni57/dockyard). Everything stays local: no account, no telemetry.

Legend: ✅ done · 🟡 partial · ⬜ not started · Effort: S (a session) · M (a few sessions) · L (weeks) · XL (a month+)

---

## 0. Ground rules (read first)

**Licensing.** Seelen UI is AGPL-3.0. Windows Bar is MIT. Re-implementing *features and behaviour* is fine. Copying Seelen source, CSS, icons, logo or the name is not, and would force Windows Bar to become AGPL. Dockyard has no license file, so treat it as all-rights-reserved: take ideas, not code. Windows Bar gets its **own visual identity**; we match capabilities, not pixels.

**Stack decision.** Stay on Python + PySide6 through Phase 3. At the end of Phase 3, make a written go/no-go call on whether Phase 4+ (Alt+Tab, tiling) needs a native core (Rust via PyO3) or a Tauri rewrite. See Risks.

**GitHub rule.** Nothing exists until it is pushed. See section 7.

---

## 1. Where Windows Bar is today

From the README and the source audit in `AUDIT.md`:

- Bar on each connected display with per-display widget/layout settings; combined or split Toolbar/Dock layout, snaps to edges, optional full-width or pill
- AppBar space reservation, glass/acrylic, taskbar auto-hide with crash-safe restore
- Auto-hide dock with fullscreen detection, start with Windows
- 28 configurable widgets, including pinned apps, open windows, clock, system, weather, media, calendar, quick actions, notes, focus tools, storage, network, volume, and quick toggles; the calendar popup is a detail panel
- Files: `windowsbar.py` (UI), `launcher.py`, `search.py`, `theme.py`, `services.py`, `extras.py`, `winapi.py`, `tests/`
- MIT; see `LICENSE`

---

## 2. Feature matrix: Seelen UI → Windows Bar

| Seelen feature | Windows Bar now | Target phase | Effort |
|---|---|---|---|
| Custom toolbar (replaces taskbar) | ✅ optional split toolbar + pinned-app dock, active-window title, virtual-desktop shortcuts; notification-area tray remains Windows-owned | — | — |
| Dock with launch / focus / badges | ✅ pinned apps show running dots and focus or launch on click | — | — |
| Desktop widgets on wallpaper layer | ⬜ | P4 | L |
| Custom flyouts (volume, brightness, system) | ✅ volume and WMI internal-panel brightness; system detail popups | — | — |
| Start menu / keyboard launcher (fuzzy search) | ✅ Alt+Space launcher searches apps, files, commands, and calculator | — | — |
| Tiling window manager (BSP, columns, stacks) | ⬜ | P5 | XL |
| Per-app rules, floating mode, gaps | ⬜ | P5 | L |
| Custom Alt+Tab | ⬜ | P4 | L |
| Virtual desktops + workspace viewer | ⬜ | P4 | L |
| Wallpaper per workspace, named workspaces | ⬜ | P4 | M |
| Theming engine (CSS/JSON-style) | ✅ built-in JSON themes, custom themes and QSS | — | — |
| Dynamic accent from wallpaper | ✅ | — | — |
| Per-widget theming | ✅ color/radius overrides through Settings | — | — |
| Community themes / sharing | ⬜ | P6 | M |
| Media controls | ✅ | — | — |
| Multi-monitor, per-display config | ✅ one bar and settings profile per connected display | — | — |
| Settings app with live preview | ✅ separate live Settings window | — | — |
| Keyboard-first (everything reachable) | 🟡 pinned-app Alt+1..9 (modifier configurable); remaining controls still need keyboard paths | P2 → P3 | M |
| i18n (Seelen: 70+ languages) | ⬜ | P6 | M |
| Widget SDK | ⬜ | P1 (internal), P6 (public) | M |
| Portable, plain-file config | 🟡 `%APPDATA%\Windows Bar\config.json`; schema v1 migration started | P1 (export/import remains) | S |
| Signed installer / winget | ⬜ | P6 | M |

---

## 3. Dockyard ideas to adopt

Already in Windows Bar: clock, stopwatch, focus timer, CPU/RAM/network, battery, weather, now playing, todos.

| Dockyard idea | Notes for Windows | Phase |
|---|---|---|
| Pinned apps with *running dots* | Match pinned entries to open windows by exe path | P2 |
| Hotkeys to open/switch pinned apps 1–9 | `Win+1..9` belongs to Explorer; default to `Alt+1..9` (configurable) via `RegisterHotKey` | P2 |
| World clocks | `zoneinfo`, pure Python | P2 |
| Pomodoro + countdown timer | Extend the existing focus widget | P2 |
| Temperature sensor | Often unavailable on Windows without a helper (LibreHardwareMonitor); make it optional | P2 |
| Disk usage widget | `psutil` | P2 |
| Click-to-open **detail popup** per widget | Core UI pattern; build once in P1 | P1/P2 |
| Quick toggles: mute, Wi-Fi, Bluetooth | mute via native Core Audio; radios via WinRT. Do Not Disturb and Night Light are undocumented on Windows and remain unsupported | P2 |
| "Each module is one dumb view; data sources live once" | Adopt as the widget architecture | P1 |
| Hidden modules stop their timers/sensors | Copy this behaviour exactly; big battery/CPU win | P1 |
| Glass desktop theme | Ship as a built-in theme | P3 |

---

## 4. Target architecture

```
windows_bar/
  app.py                 entry point (future split from windowsbar.py)
  core/
    config.py            schema, versioning, migrations, export/import
    registry.py          widget discovery + lifecycle
    events.py            small pub/sub (window events, theme changes)
    theme.py             tokens (JSON) -> QSS, dynamic accent
  native/                (split of today's winapi.py)
    appbar.py  glass.py  taskbar.py  windows.py  hooks.py  vdesktop.py  audio.py
  widgets/               one file per widget
  ui/                    bar.py  card.py  popup.py  settings/
  launcher/              fuzzy search window
  wm/                    tiling engine (Phase 5)
  themes/                default.json, glass.json, light.json
tests/
```

**Widget contract** (this is the internal SDK; publish it in Phase 6):

```python
class Widget:
    id = "weather"                # unique
    name = "Weather"
    default_config = {...}
    poll_seconds = 600            # None = event-driven
    def start(self): ...          # begin timers/threads
    def stop(self): ...           # called when hidden or disabled
    def card(self) -> QWidget: ...
    def popup(self) -> QWidget | None: ...   # detail view on click
    def on_click(self): ...
```

Rules: widgets never touch Win32 directly (go through `native/`); all native hooks run on one dedicated thread and post events to Qt; no widget does network work on the UI thread.

---

## 5. Phases

### Phase 0: Safety net *(S, do this first)*
- [x] Add `ROADMAP.md`, `AGENTS.md`, `scripts/checkpoint.ps1`, `.github/workflows/ci.yml` to the repo
- [ ] Commit and push (see section 7)
- [x] Naming decision: keep repository `windowbar`, product name Windows Bar; README already uses Windows Bar
- [x] Audit current code: line counts per file, what is untested, what is Windows-only (`AUDIT.md`)
- [ ] Create GitHub Issues from the checklists below (one per bullet or per group)
- [ ] Tag `v0.1.0` for the current state

**Done when:** a fresh clone + `pip install -r requirements.txt` + `pytest -q` works, and CI is green.

### Phase 1: Modular core *(M)*
- [x] Split `windowsbar.py` / `winapi.py` into the structure in section 4, with no behaviour change; `windowsbar.py` is the entrypoint, Dock/config are in `ui/` and `core/`, and native helpers are in `native/`
- [x] Give each configured widget its own module and factory; registry package discovery registers widgets from the modules and config defaults.
- [x] Widget registry + widget contract; all 28 configured widgets are auto-discovered and registered through the compatibility adapter
- [x] Versioned config with migration from the current `config.json` (schema v1, legacy migration, and focused tests; export/import is a later enhancement)
- [x] Widgets stop their work when hidden or disabled (poll workers stop, Screen Time sampler is opt-in, and weather/calendar/media/radio workers stop when inactive)
- [x] Detail-popup component (`ui/popup.py`, shared by calendar, notes, and todos panels)
- [x] Rotating logging to `%APPDATA%\Windows Bar\logs` and a crash-recovery test for saved taskbar auto-hide state

**Done when:** all 28 configured widgets run through the registry; adding a widget = one module + one config key.

### Phase 2: Dockyard parity + keyboard basics *(M–L)*
- [x] Pinned apps with running dots and focus/launch behaviour
- [x] Global hotkeys `Alt+1..9` by default; configurable modifier (Alt, Ctrl+Alt, or Win)
- [x] World clocks, pomodoro/timer, disk widget, optional temperature (psutil or optional LibreHardwareMonitor WMI)
- [x] Quick toggles: mute, Wi-Fi, Bluetooth; DND / Night Light documented as unsupported
- [x] Detail popups for clock, system, media, weather

**Done when:** every Dockyard feature in section 3 is either shipped or documented as unsupported on Windows.

### Phase 3: Shell basics, Seelen tier 1 *(L)*
- [x] **Theming engine:** JSON theme files, color/radius/font/spacing/blur tokens, QSS, and default/glass/light/dark built-ins
- [x] Dynamic accent colour from the current wallpaper (dominant-colour extraction, live update)
- [x] Per-widget style overrides for accent, card background, text, button color, and radius
- [x] Split **Toolbar** (top: active-window title, virtual-desktop shortcuts, enabled information widgets) and **Dock** (bottom: pinned apps + running); Windows notification-area tray remains OS-owned
- [x] Multi-monitor: a bar per display with independent widget/layout profile
- [x] Separate Settings window for widgets, layout, themes, hotkeys, and live preview
- [x] **Launcher:** global hotkey, fuzzy search over apps, files, commands, calculator
- [x] Volume and brightness flyouts (brightness via optional WMI on supported internal panels; external DDC displays are not supported)
- [x] Optional notification-centre integration: open the native Windows notification surface; Windows owns the notification feed and rendering

**Done when:** a non-programmer can restyle and rearrange widgets and layouts from Settings without editing JSON. **Met.** Native notification feeds and the system tray remain rendered by Windows.

> **Decision gate (end of Phase 3):** the written decision is to stay on Python/PySide6 and measure idle CPU/RAM and input latency before Phase 4's hook/tiling work. No runtime measurements were available in the authoring environment; reopen the decision if Windows measurements show stalls or excessive idle resource use. See `docs/decisions/0001-stack.md`.

### Phase 4: Workspaces, Alt+Tab, desktop widgets, Seelen tier 2 *(L)*
- [ ] Virtual desktop control (switch, move window, create/remove), using a maintained wrapper rather than raw undocumented COM, with a fallback if Windows updates break it
- [ ] Workspace viewer overlay, named workspaces with icons
- [ ] Wallpaper per workspace
- [ ] Custom Alt+Tab: low-level keyboard hook on its own thread, window previews (DWM thumbnails or captured frames), keyboard + mouse navigation
- [ ] Desktop-widgets layer pinned beneath normal windows (wallpaper layer), draggable, theme-aware

### Phase 5: Tiling window manager *(XL)*
- [ ] Window tracking via `SetWinEventHook`; ignore tool windows, dialogs, UWP edge cases
- [ ] Layout engines: BSP first, then columns/stacks
- [ ] Gaps/padding, keyboard focus/swap/resize/move-to-workspace
- [ ] Floating mode toggle, per-app rules (match by exe / class / title regex)
- [ ] Per-monitor and per-workspace layouts, persistence across restarts
- [ ] Safe mode: hotkey to release all windows if the WM misbehaves

### Phase 6: Ecosystem and release *(M–L)*
- [ ] Public widget SDK docs + example widget repo template
- [ ] Theme sharing format and a `themes/` gallery in the repo
- [ ] i18n with a translation workflow
- [ ] Installer (Inno Setup / MSIX), code signing if feasible, GitHub Releases, winget manifest
- [ ] Screenshots, GIFs, a proper README, contribution guide

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| Python latency for Alt+Tab / tiling | Dedicated hook thread; decision gate after Phase 3; native core if needed |
| Undocumented Windows APIs (virtual desktops, DND, Night Light) | Use maintained wrappers, feature-flag them, degrade gracefully |
| Windows updates break shell tricks | Pin tested Windows builds in docs; keep a tested "safe restore" path for taskbar/AppBar state |
| Scope: Seelen has 2,700+ commits and many contributors | Ship phase by phase; Phase 3 is already a very usable product |
| Accidental AGPL contamination | Never paste Seelen code or assets; implement from behaviour |
| Locked-out desktop if the shell crashes | Crash-safe restore on next start + a documented recovery hotkey/command |

---

## 7. GitHub workflow (so progress is never lost)

1. **Work on branches:** `phase-1-core`, `phase-2-dockyard`, … merge to `main` when the phase's "Done when" is met.
2. **Checkpoint often:** run `scripts/checkpoint.ps1 "what you did"` at the end of every work session, and after any milestone. It commits and pushes.
3. **Small commits:** `feat(widgets): add world clock`, `fix(appbar): restore taskbar on crash`, `refactor(core): split winapi`.
4. **One Issue per roadmap bullet** (or group); close them from commits with `closes #N`.
5. **Tag milestones:** `v0.1.0` (today) → `v0.2.0` (P1) → `v0.3.0` (P2) → `v0.4.0` (P3, first "shell" release) → …
6. **Keep `AGENTS.md` current:** its "Current state" section is the handoff note. Any AI assistant (or you in a month) starts there.
7. **Never commit secrets:** the Stripe key stays in `WINDOWSBAR_STRIPE_KEY`; check `.gitignore` before each push.








