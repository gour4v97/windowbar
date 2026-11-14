"""Opt-in runtime widget plugins for Windows Bar (pure Python, no Qt).

A plugin is a Python file (``plugins/<name>.py``) or a package folder
(``plugins/<name>/__init__.py``) inside ``%APPDATA%\\Windows Bar\\plugins``.
It exports the same contract as a built-in widget module::

    WIDGET_ID = "my_widget"         # required, ^[a-z][a-z0-9_]{1,31}$
    def make_card(context): ...     # required, returns a Card

and may add ``WIDGET_LABEL`` (display name), ``WIDGET_DEFAULT`` (enabled on
first run, default False), ``WIDGET_ORDER`` and ``PLUGIN_API`` (default 1).

Plugins are ordinary Python code and run with the user's permissions, so
loading is off unless ``plugins_enabled`` is true in the config. A plugin that
fails to import, is invalid, or reuses an id is skipped and reported; it can
never stop the dock from starting.
"""
import importlib.util
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

API_VERSION = 1
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_log = logging.getLogger("windowsbar.plugins")

_loaded = []          # modules of successfully loaded plugins
_errors = []          # PluginError records from the last load


@dataclass(frozen=True)
class PluginError:
    name: str
    reason: str


def _candidates(plugins_dir):
    folder = Path(plugins_dir)
    if not folder.is_dir():
        return []
    items = []
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith((".", "_")):
            continue
        if entry.is_file() and entry.suffix == ".py":
            items.append((entry.stem, entry))
        elif entry.is_dir() and (entry / "__init__.py").is_file():
            items.append((entry.name, entry / "__init__.py"))
    return items


def _import(name, path):
    module_name = f"windowbar_plugin_{re.sub(r'[^0-9A-Za-z_]', '_', name)}"
    kwargs = {}
    if path.name == "__init__.py":
        kwargs["submodule_search_locations"] = [str(path.parent)]
    spec = importlib.util.spec_from_file_location(module_name, path, **kwargs)
    if spec is None or spec.loader is None:
        raise ImportError("cannot create an import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:                  # undo, then let the caller decide
        sys.modules.pop(module_name, None)
        raise
    return module


def validate(module, reserved_ids=()):
    """Return ``None`` if ``module`` is a valid plugin, else the reason."""
    widget_id = getattr(module, "WIDGET_ID", None)
    if not isinstance(widget_id, str) or not ID_PATTERN.match(widget_id):
        return "WIDGET_ID must match ^[a-z][a-z0-9_]{1,31}$"
    if widget_id in reserved_ids:
        return f"WIDGET_ID {widget_id!r} is already used"
    if not callable(getattr(module, "make_card", None)):
        return "make_card(context) is missing"
    api = getattr(module, "PLUGIN_API", API_VERSION)
    if api != API_VERSION:
        return f"PLUGIN_API {api!r} is not supported (need {API_VERSION})"
    return None


def load_plugins(plugins_dir, reserved_ids=()):
    """Import every plugin in ``plugins_dir``; return ``(modules, errors)``.

    ``reserved_ids`` are ids that may not be reused (built-in widgets).
    Results are also kept for ``loaded_modules()`` / ``load_errors()``.
    """
    unload_plugins()
    taken = set(reserved_ids)
    for name, path in _candidates(plugins_dir):
        try:
            module = _import(name, path)
        except (Exception, SystemExit) as exc:   # must not kill the app
            _errors.append(PluginError(name, f"import failed: {exc!r}"))
            _log.warning("plugin %s failed to import: %r", name, exc)
            continue
        reason = validate(module, taken)
        if reason:
            _errors.append(PluginError(name, reason))
            _log.warning("plugin %s rejected: %s", name, reason)
            sys.modules.pop(module.__name__, None)
            continue
        taken.add(module.WIDGET_ID)
        _loaded.append(module)
        _log.info("plugin %s loaded as widget %s", name, module.WIDGET_ID)
    return list(_loaded), list(_errors)


def apply_plugins(modules, widget_defaults, labels):
    """Add plugin ids/labels to the config defaults and label maps in place."""
    for module in modules:
        widget_id = module.WIDGET_ID
        widget_defaults.setdefault(widget_id, bool(
            getattr(module, "WIDGET_DEFAULT", False)))
        label = getattr(module, "WIDGET_LABEL", None)
        labels.setdefault(widget_id, str(label) if label
                          else widget_id.replace("_", " ").title())


def loaded_modules():
    return list(_loaded)


def load_errors():
    return list(_errors)


def unload_plugins():
    for module in _loaded:
        sys.modules.pop(module.__name__, None)
    _loaded.clear()
    _errors.clear()


class PluginContext:
    """The small, documented object plugins receive instead of the raw Dock.

    Stable members: ``get_config(key, default)``, ``tokens`` (current theme
    tokens), ``app_dir`` and ``logger``. Anything else is forwarded to the
    underlying Dock for backwards compatibility, but it is internal, may change
    without notice, and logs a one-time warning naming the attribute.
    """

    def __init__(self, dock, app_dir=None, logger=None):
        self._dock = dock
        self._warned = set()
        self.app_dir = app_dir
        self.logger = logger or logging.getLogger("windowsbar.plugin")

    def get_config(self, key, default=None):
        """Read a setting (a copy for lists/dicts, so plugins cannot mutate it)."""
        import copy
        cfg = getattr(self._dock, "cfg", None) or {}
        return copy.deepcopy(cfg.get(key, default))

    @property
    def tokens(self):
        import copy
        return copy.deepcopy(getattr(self._dock, "tokens", {}))

    def __getattr__(self, name):
        if name.startswith("__") or name in ("_dock", "_warned"):
            raise AttributeError(name)
        if name not in self._warned:
            self._warned.add(name)
            _log.warning("a plugin used internal Dock attribute %r; it may "
                         "break in a future version", name)
        return getattr(self._dock, name)
