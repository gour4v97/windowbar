# Widget contribution API

This is the source-level widget contract used by Windows Bar's built-in widget
registry. It is suitable for a widget contribution or a fork. Windows Bar does
not currently load third-party widget packages at runtime.

## Minimal module

Create a module under `widgets/` that exports a unique `WIDGET_ID` and a
`make_card(context)` factory. The factory receives the running `Dock` as its
context and returns a Qt card. The `widgets/` package is discovered at startup.

```python
from widgets.base import Card

WIDGET_ID = "sample_status"
WIDGET_ORDER = 90


class SampleStatusCard(Card):
    INTERVAL = 10

    def __init__(self, context):
        super().__init__("Sample status")
        self.context = context

    def tick(self):
        self.set_texts(body="Ready")


def make_card(context):
    return SampleStatusCard(context)
```

`WIDGET_ORDER` is optional and controls registry discovery order. Cards may
implement `start()` and `stop()` for work that should run only while enabled.
The dock calls `tick()` during its refresh cycle. Keep I/O off the UI thread;
use the existing worker/poller patterns for asynchronous work.

## Register it in the product

Add the widget's default key to `core/app_config.py` under `DEFAULTS["widgets"]`
and its label to `WIDGET_LABELS`. Add an appropriate module factory in
`widgets/`, then use the widget registry to keep creation and lifecycle
management centralized. Avoid network calls and file scans on the UI thread.

For a copyable scaffold, see [`widget-template/`](widget-template/).

## Compatibility and security

The current context is the internal Dock object; its methods are not yet a
stable external plugin API. Widgets are Python code and run with the same
permissions as Windows Bar. There is no sandbox, package installer, or
third-party runtime discovery. Do not treat this source-level contract as a
promise of binary or runtime plugin compatibility.
