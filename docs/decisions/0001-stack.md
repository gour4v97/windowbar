# Stack decision: keep Python and PySide6

**Status:** Provisional go for Phase 4, 2026-11-08

## Decision

Continue with Python and PySide6. Keep Win32-specific behavior behind the existing `native/` helpers. Do not start a Rust/PyO3 core or a Tauri rewrite for Phase 4.

## Reasons

- The current widget registry, settings, popup, and display-profile boundaries support the shell work without a native rewrite.
- The latency-sensitive work so far is limited to short Win32 calls and Qt event handling. There is no custom global keyboard hook or window tiling loop yet.
- Rewriting now would add deployment and maintenance cost before the planned Phase 4 features demonstrate a real bottleneck.

## Performance evidence and follow-up

This environment did not have an available Python runtime, and Windows Bar was not running here. Idle CPU/RAM and interactive input latency therefore were **not measured** for this decision. Before implementing the Phase 4 Alt+Tab hook or tiling loop, capture an idle baseline on a supported Windows machine and measure keyboard-to-UI response under load. Reopen this decision if those measurements show missed input, sustained UI stalls, or excessive idle resource use.

The decision is a scope choice based on the current architecture, not a claim that performance has been benchmarked.

