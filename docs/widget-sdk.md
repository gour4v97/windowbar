# Widget contribution API

This is the widget contract used by Windows Bar's registry. It works two ways:
as a built-in widget in a source checkout (below), or as a **runtime plugin**
dropped into your plugins folder (see "Runtime plugins").

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
and its label to `WIDGET_LABELS`.

For a copyable scaffold, see [`widget-template/`](widget-template/).

## Runtime plugins

A plugin is a single `.py` file, or a folder with an `__init__.py`, placed in
`%APPDATA%\\Windows Bar\\plugins`. It exports the same names as a built-in
widget module, plus optional metadata:

| Name | Required | Meaning |
|---|---|---|
| `WIDGET_ID` | yes | Unique id, `^[a-z][a-z0-9_]{1,31}$`; may not reuse a built-in id |
| `make_card(context)` | yes | Returns the card (see above) |
| `WIDGET_LABEL` | no | Name shown in Settings (default: the id, title-cased) |
| `WIDGET_DEFAULT` | no | Enabled on first run (default `False`) |
| `WIDGET_ORDER` | no | Discovery order |
| `PLUGIN_API` | no | Must be `1` if present |

`make_card(context)` receives a `PluginContext` (see "Compatibility and security").

Turn on **Settings > General > Load widget plugins** (or set
`"plugins_enabled": true` in `config.json`) and restart. Then enable the widget
in Settings > Widgets. A copyable example is in
[`plugins-example/hello_plugin.py`](../plugins-example/hello_plugin.py).

A plugin that fails to import, is invalid, or reuses an id is skipped and
listed in Settings > General and in the log; it cannot stop the dock starting.
Loading is off by default.

## Compatibility and security

Built-in widgets receive the internal Dock object as context. Runtime plugins instead receive a `PluginContext` (below); its surface is the stable plugin API, currently version 1. Widgets are Python code and run with the same
permissions as Windows Bar. There is no sandbox and no package installer: **a plugin can do anything you
can do**, so only enable plugins you have read or trust. `PLUGIN_API = 1` is
the first version. Plugins receive a `PluginContext` with a small stable surface:
`get_config(key, default)` (a copy), `tokens` (theme colours), `app_dir` and
`logger`. Other attributes are forwarded to the internal Dock for compatibility,
but log a one-time warning and may break in a future version.
