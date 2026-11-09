# Stack decision: keep Python and PySide6

**Status:** Retain Python for Phase 4; reassess before Phase 5, 2026-11-08

## Decision

Continue with Python and PySide6. Keep Win32-specific behavior behind the existing `native/` helpers. Do not start a Rust/PyO3 core or a Tauri rewrite for Phase 4. The available measurements do not show a Python/Qt event-dispatch bottleneck that justifies a rewrite. The hook installed during an isolated app launch, but real keyboard response and full-dock idle use remain unmeasured.

## Reasons

- The current widget registry, settings, popup, and display-profile boundaries support the shell work without a native rewrite.
- The low-level keyboard hook is isolated on a dedicated message-loop thread and posts actions to Qt. It is opt-in. Phase 5 tiling has not started.
- Rewriting now would add deployment and maintenance cost before the planned Phase 4 features demonstrate a real bottleneck.

## Performance evidence and follow-up

Measured 2026-11-08 with the bundled Python 3.13.17 and PySide6 6.12.0 runtime. The probe used an offscreen Qt event loop with an empty widget, a 10 ms timer for 30 seconds, and 1,000 synthetic in-process Qt key events. It intentionally did not install a Win32 hook, run the full Windows Bar dock, or exercise virtual desktops/tiling.

| Measurement | Result |
| --- | ---: |
| Idle event-loop process CPU | 1.20% of one core |
| Process RSS | 42.7 MiB at start; 43.0 MiB at end |
| 10 ms timer lateness | 0.23 ms median; 0.78 ms p95 |
| Synthetic Qt key dispatch | 0.0058 ms median; 0.0177 ms p95; 0.1811 ms max |

These are a runtime/event-loop baseline, not a Windows Bar application or physical-input latency result. The isolated app launched with the custom hook enabled, but this session could not capture the switcher response or measure physical key latency. The Windows virtual-desktop COM service returns access denied here, so desktop switching and wallpaper changes could not be exercised. Keep the Python implementation for now; do not begin a Rust/PyO3 or Tauri port based on these measurements alone. Before Phase 5 tiling, measure the real dock on a supported interactive Windows session, including idle CPU/RAM, physical key-to-visible-response latency, missed/repeated inputs, and load behavior. Reopen this decision if the real measurements show sustained UI stalls, missed input, or unacceptable idle resource use.
