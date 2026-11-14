"""Small widget registry and lifecycle bridge for Windows Bar."""

from dataclasses import dataclass
import importlib
import pkgutil
from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class Widget(Protocol):
    id: str
    name: str
    default_config: dict

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def card(self): ...
    def popup(self): ...
    def on_click(self) -> None: ...


@dataclass(frozen=True)
class WidgetDefinition:
    id: str
    name: str
    default_config: object
    factory: Callable[[], Widget]


class WidgetRegistry:
    """Register widget factories and control enabled widget lifecycles."""

    def __init__(self):
        self._definitions = {}
        self._active = {}

    @property
    def definitions(self):
        return dict(self._definitions)

    @property
    def active(self):
        return dict(self._active)

    def register(self, definition):
        if not isinstance(definition, WidgetDefinition):
            raise TypeError("definition must be a WidgetDefinition")
        if not definition.id or definition.id in self._definitions:
            raise ValueError(f"duplicate or empty widget id: {definition.id!r}")
        self._definitions[definition.id] = definition

    def register_package(self, package, context, widget_defaults, labels):
        """Discover widget modules that export WIDGET_ID and make_card()."""
        modules = [importlib.import_module(f"{package.__name__}.{item.name}")
                   for item in pkgutil.iter_modules(package.__path__)]
        return self.register_modules(modules, context, widget_defaults, labels)

    def register_modules(self, modules, context, widget_defaults, labels):
        """Register already-imported modules (built-in or plugin widgets)."""
        discovered = []
        for module in modules:
            widget_id = getattr(module, "WIDGET_ID", None)
            make_card = getattr(module, "make_card", None)
            if not widget_id or not callable(make_card):
                continue
            order = getattr(module, "WIDGET_ORDER", 10_000)
            discovered.append((order, widget_id, module, make_card))

        for _, widget_id, _module, make_card in sorted(
                discovered, key=lambda item: item[:2]):
            if widget_id in self._definitions:
                continue                  # first registration wins
            name = labels.get(widget_id, widget_id.title())
            default = bool(widget_defaults.get(widget_id, False))
            self.register(WidgetDefinition(
                id=widget_id,
                name=name,
                default_config=default,
                factory=lambda mid=widget_id, label=name, enabled=default,
                              maker=make_card: CardWidgetAdapter(
                    mid, label, enabled, lambda: maker(context)),
            ))
        return self.definitions

    def start_enabled(self, config):
        """Start enabled widgets and stop disabled ones; return active widgets."""
        enabled = config.get("widgets", {})
        for widget_id in list(self._active):
            definition = self._definitions[widget_id]
            if not enabled.get(widget_id, definition.default_config):
                self._stop_one(widget_id)
        for widget_id, definition in self._definitions.items():
            if widget_id in self._active:
                continue
            if enabled.get(widget_id, definition.default_config):
                widget = definition.factory()
                widget.start()
                self._active[widget_id] = widget
        return dict(self._active)

    def stop_all(self):
        for widget_id in list(self._active):
            self._stop_one(widget_id)

    def _stop_one(self, widget_id):
        widget = self._active.pop(widget_id)
        widget.stop()


class CardWidgetAdapter:
    """Expose an existing card through the new internal widget contract."""

    def __init__(self, widget_id, name, default_config, card_factory):
        self.id = widget_id
        self.name = name
        self.default_config = {"enabled": bool(default_config)}
        self._card = card_factory()

    def start(self):
        start = getattr(self._card, "start", None)
        if callable(start):
            start()

    def stop(self):
        stop = getattr(self._card, "stop", None)
        if callable(stop):
            stop()

    def card(self):
        return self._card

    def popup(self):
        popup = getattr(self._card, "popup", None)
        return popup() if callable(popup) else None

    def on_click(self):
        callback = getattr(self._card, "on_click", None)
        if callable(callback):
            callback()

