"""Small widget registry and lifecycle bridge for Windows Bar."""

from dataclasses import dataclass
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

