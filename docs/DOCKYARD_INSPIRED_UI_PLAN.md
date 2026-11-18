# Harbor UI and Windows Integration Roadmap

**Status:** In progress  
**Repository:** gour4v97/windowbar  
**Working branch:** feature/dockyard-inspired-windows-ui  
**Base branch:** main  
**Product:** Windows Bar for Windows 10/11, using the existing Python and PySide6 stack.

## Goal

Make Windows Bar feel like a cohesive, configurable Windows dock: a floating glass or solid surface, compact information tiles, recognizable pinned apps, useful popups, and reliable Windows shell behavior. Dockyard is a source of product and interaction ideas only. Do not copy its code, name, icons, screenshots, or stylesheets.

## Current state

The feature branch has a complete repository snapshot. The latest verified code commit passed both Windows and Linux CI in workflow run 274. The local app could not be launched in this workspace, so the final DPI and desktop-shell checks still require a real Windows session.

### Completed on this branch

- Added the selectable Harbor theme with compact spacing and cool glass colors; saved theme choices remain unchanged.
- Pinned apps use Windows shell icons when their configured command resolves. Unresolved commands retain text labels; app names remain available to accessibility tools and tooltips.
- Icon apps show a running state, while text fallback apps retain their running dot.
- Detail popups use an opaque, theme-matched surface and keep their edge-aware placement behavior.
- Data tiles have subtle hover tint and a visible keyboard-focus border, including when per-widget styling is active.
- New/default widget order groups system and information tiles before pinned apps, utility widgets after them, and the clock at the far right. A saved custom widget order still wins.
- Fixed the Windows CI hotkey-ID test so it checks distinct IDs without trying to register a real system-wide hotkey.
- Added an original SVG concept at docs/mockups/harbor-dock.svg.

## Remaining roadmap

Complete these steps in order. Each step stays on the feature branch and should be reviewable as a focused change.

### 1. Review the design on real Windows

- [ ] Run the branch build on Windows 10 and Windows 11.
- [ ] Capture the combined dock, split toolbar, Settings preview, app group, and representative popups.
- [ ] Review 100%, 125%, 150%, and 200% display scaling.
- [ ] Check top and bottom placement, floating pill and full-width modes, and a mixed-DPI multi-monitor setup.
- [ ] Compare the running app with docs/mockups/harbor-dock.svg and record specific visual defects before changing more styling.

**Done when:** screenshots and a short defect list cover both Windows versions, all target scales, and the combined/split layouts.

### 2. Finish the shared dock layout

- [x] Establish a useful default order for data tiles, pinned apps, utilities, and clock.
- [ ] Tune spacing, bar margins, tile height, corner radii, and app-icon hit targets using the Windows captures.
- [ ] Check that the floating layout stays centered and usable when widgets are enabled or disabled.
- [ ] Check full-width mode, top placement, auto-hide, and split toolbar geometry after the layout changes.
- [ ] Keep the Settings widget arranger and live preview consistent with the actual dock order.

**Done when:** layout remains balanced with the Essentials, Focus, Creator, and Everything presets, and user-saved orders are preserved.

### 3. Finish tile and pinned-app behavior

- [x] Add native app icons, readable fallback labels, running state, hover, and keyboard focus treatment.
- [ ] Verify icons for executable paths, quoted commands, Start Menu shortcuts, and unresolved commands.
- [ ] Confirm app launch, focus/minimize, right-click actions, and Alt+number shortcuts still work.
- [ ] Check tile width with long labels, changing values, narrow displays, and all built-in themes.
- [ ] Ensure disabled, unavailable, and empty widgets have clear states and do no unnecessary polling.

**Done when:** icons and information tiles remain readable and operable with mouse and keyboard across themes and scales.

### 4. Unify popups and Settings

- [x] Apply a shared opaque themed surface to detail popups.
- [ ] Check popup placement near screen edges and on top- and bottom-docked layouts.
- [ ] Normalize popup headings, spacing, close/dismiss behavior, shadows, and action buttons.
- [ ] Check clock, system, weather, media, calendar, notes, and todos popups for visual consistency.
- [ ] Verify keyboard focus, Escape dismissal, contrast, and high-contrast/readability behavior.
- [ ] Confirm Settings theme/layout preview matches the live dock.

**Done when:** each popup is anchored correctly, looks like part of Windows Bar, and remains usable with keyboard alone.

### 5. Validate Windows integration and recovery

- [ ] Check AppBar reservation and maximized-window work areas with taskbar visible and hidden.
- [ ] Exercise auto-hide, fullscreen applications, Explorer restart, sleep/resume, monitor add/remove, and mixed scaling.
- [ ] Confirm taskbar state and window geometry restore after normal quit, crash, and next launch.
- [ ] Check virtual desktop, Alt+Tab, hotkey, and tiling features on supported Windows builds; keep graceful fallback messages for unsupported APIs.
- [ ] Keep Win32 calls behind native helpers and all slow work away from the UI thread.

**Done when:** the dock does not strand the user, cover work areas unexpectedly, or leave the taskbar altered after failure.

### 6. Measure performance and accessibility

- [ ] Measure cold start, idle CPU/RAM, live update cost, and key-to-visible-response latency on a real Windows machine.
- [ ] Confirm hidden or disabled widgets stop polling and background workers stop when no longer needed.
- [ ] Check keyboard navigation order, focus visibility, accessible names, contrast, and reduced-motion choices.
- [ ] Record measurements and test machine details in the project docs.

**Done when:** measurements show no persistent UI stalls or excessive idle work, and known limitations are documented.

### 7. Prepare a reviewable release

- [ ] Update README screenshots and add a short, privacy-safe demo.
- [ ] Build and verify the Windows package, install/upgrade/uninstall paths, autostart, and recovery behavior.
- [ ] Run the full Windows and Linux CI jobs on the final feature commit.
- [ ] Open a pull request from feature/dockyard-inspired-windows-ui to main with screenshots, checks, and remaining limitations.
- [ ] Merge only after review; do not commit project changes directly to main.

**Done when:** CI is green, the Windows package has been exercised on a clean profile, and the pull request explains the verified behavior and remaining limitations.

## Guardrails

- Keep all project changes on feature branches and publish them to GitHub. This effort uses feature/dockyard-inspired-windows-ui; main remains the stable target.
- Preserve existing saved widget orders, themes, and configuration values.
- Reimplement ideas independently; do not copy Dockyard code or assets.
- Keep network, filesystem, and slow system work off the UI thread; disabled widgets should not poll.
- Keep taskbar, work-area, hook, and window changes recoverable after crashes.
- Never commit credentials, personal settings, runtime logs, or screenshots containing private data.
- Use small commits and update this checklist as steps are completed.

## Primary references

- UI concept: docs/mockups/harbor-dock.svg
- Existing project roadmap: ROADMAP.md
- Windows shell audit: AUDIT.md
- Stack decision and performance baseline: docs/decisions/0001-stack.md
- Project instructions: AGENTS.md
