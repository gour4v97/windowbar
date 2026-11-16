# Dockyard-Inspired Windows UI Plan

**Status:** In progress  
**Repository:** `gour4v97/windowbar`  
**Working branch:** `feature/dockyard-inspired-windows-ui`  
**Target:** A cohesive, polished Windows dock experience inspired by Dockyard's interaction and visual ideas, implemented with Windows Bar's existing Python/PySide6 stack and Windows-native behavior.

## Product direction

Make the dock feel like one adaptable surface: a floating glass or solid bar, compact tiles sized to their content, pinned app icons with clear running state, and predictable detail popups. Keep the interface configurable and accessible, and preserve Windows Bar's existing capabilities where they already work.

Use Dockyard as a reference for behavior and visual principles only. Do not copy its code, name, icons, screenshots, stylesheets, or other assets. Windows Bar remains an independent MIT project.

## Current foundation

The repository already has configurable widgets, theme tokens and QSS, per-widget styling, a launcher, shared popup infrastructure, app pinning, running indicators, hotkeys, per-display profiles, auto-hide, glass effects, and disabled-widget polling controls. This effort should refine and connect those pieces before adding more widgets.

## Progress on the feature branch

- [x] Added the selectable Harbor theme with compact spacing, cool glass surfaces, and distinct app-icon states; existing saved theme choices remain unchanged.
- [x] Pinned apps use Windows shell icons when the configured executable resolves, retain a readable text fallback, and keep names available to accessibility tools.
- [x] Detail popups use an opaque theme-matched surface with the existing edge-aware placement behavior.
- [x] Fixed the Windows CI hotkey-ID test so it checks distinct IDs without attempting to register a real system-wide hotkey.
- [x] Created an original SVG concept at `docs/mockups/harbor-dock.svg` to make the target layout reviewable before implementation.
- [ ] Capture and review the dock, app icons, and popups in a real Windows session at common DPI scales; tune the layout from those screenshots.

## Work plan

### Milestone 1 — UI inventory and target spec

- Capture the current dock, Settings, and representative widget popups on Windows 10/11 at common DPI scales.
- Map current widgets to their card and popup implementations; identify duplicated styling and interaction patterns.
- Specify a small set of layout choices: floating pill or full-width bar, top or bottom placement, content-sized tile widths, app grouping, spacing, and popup anchoring.
- Define design tokens for bar/tile surfaces, borders, corner radii, shadow, typography, icon sizes, focus, hover, and running-app state. Reuse the theme engine instead of introducing a second styling system.
- Record Windows-specific constraints and graceful fallbacks, including unsupported radios, fullscreen apps, mixed-DPI monitors, and taskbar coexistence.

**Exit criteria:** approved mockups for the dock, one data tile, one app icon state, one popup, and Settings preview; documented token mapping to existing theme keys.

### Milestone 2 — Shared dock and tile presentation

- Implement the chosen layout using the existing dock and widget registry.
- Use consistent outer bar and inner tile geometry, spacing, hover/focus/pressed feedback, and disabled/empty states.
- Keep pinned app icons visually distinct from information tiles; show running and active states without relying on color alone.
- Ensure text and numbers do not shift the layout as live values change.
- Keep themes, per-widget overrides, and saved configuration backward-compatible.

**Exit criteria:** representative widgets and apps use the shared presentation; existing layouts and custom themes still load; screenshots show consistent rendering at 100%, 150%, and 200% scale.

### Milestone 3 — Popup and Settings consistency

- Apply one popup pattern for size, placement, header, close behavior, shadow, keyboard focus, and dismissal.
- Anchor popups to their triggering tile and flip them when near a screen edge or when the dock is at the top.
- Make the live Settings preview reflect layout and theme changes without requiring a restart.
- Preserve keyboard operation and readable contrast in light, dark, glass, and high-contrast modes.

**Exit criteria:** clock, media, system, and one list-style popup follow the same interaction rules; keyboard-only use remains possible.

### Milestone 4 — Windows integration and resilience

- Review AppBar reservation, taskbar hiding/restoration, auto-hide, fullscreen detection, and multi-monitor geometry together.
- Exercise mixed DPI, monitor add/remove, sleep/resume, explorer restart, and application crash/restart.
- Keep Win32 calls behind `native/`; do not perform blocking work on the UI thread.
- Keep unsupported or undocumented Windows functions optional and report limitations in the UI.

**Exit criteria:** the dock does not cover maximized work areas unexpectedly, and taskbar state can be restored after a crash.

### Milestone 5 — Performance and release polish

- Measure startup time, idle CPU/RAM, update cost with common widgets enabled, and interaction latency on a real Windows session.
- Confirm hidden/disabled widgets stop polling and slow service calls stay off the UI thread.
- Check localization, accessibility, screenshots, installation, upgrade, and uninstall flows.
- Update the README with the final design, Windows requirements, and an animated demo.

**Exit criteria:** measurements and known limitations are recorded; CI is green; Windows packaging and recovery paths are verified before release.

## First implementation slice

Start with Milestone 1 and a small UI prototype using existing components. Do not rewrite the app architecture or add widgets in this slice. Compare the current dock against the target spec, then change one representative tile and its popup behind the existing theme/config system. Use that slice to validate spacing, transparency, DPI scaling, popup placement, and keyboard focus before applying the pattern broadly.

## Performance and usability guardrails

- Keep networking, filesystem scans, and slow Windows queries off the UI thread.
- Do not poll widgets that are disabled or hidden.
- Prefer native app icons and Windows conventions for launching, focus, and window state.
- Preserve keyboard access, focus visibility, contrast, and reduced-motion/animation choices.
- Keep taskbar and work-area changes reversible, including after abnormal shutdown.
- Measure the running application on Windows; do not treat offscreen Qt timings as full-app performance results.

## GitHub-only workflow

- Do all project work on GitHub feature branches. Never commit project changes directly to `main`.
- This effort uses `feature/dockyard-inspired-windows-ui`, created from `main`.
- Commit each focused change to this branch and push it to GitHub.
- Open a pull request from this branch into `main` when the milestone is reviewable; merge only through that pull request.
- Keep the branch current with `main` without force-pushing shared history.
- Use small commits, for example `docs(ui): define dockyard-inspired design plan` and `feat(ui): unify dock tile surfaces`.
- Do not commit credentials, personal configuration, generated captures containing private data, or copied third-party assets.
