"""Shared Qt card base and small display helpers."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.i18n import tr


def clip(text, n):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


class Card(QFrame):
    """A titled card refreshed by the dock's timer.

    Keyboard path: a card whose class handles a left-click is focusable
    (Tab) and Enter/Space runs ``activate()`` — the keyboard equivalent of
    that click. Shift+Enter runs ``activate_alternate()`` where the card
    defines one (reset / set-minutes). Display-only cards stay unfocusable.
    """

    INTERVAL = 1
    ALWAYS = False
    STICKY = False

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        clickable = type(self).mousePressEvent is not QWidget.mousePressEvent
        self.setFocusPolicy(Qt.StrongFocus if clickable else Qt.NoFocus)
        self._wmax = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(0)
        self.title = QLabel(tr(title).upper())
        self.title.setObjectName("cardtitle")
        self.body = QLabel("")
        self.body.setObjectName("cardbody")
        lay.addWidget(self.title)
        lay.addWidget(self.body)

    def activate(self):
        """Keyboard equivalent of a left-click. Subclasses with their own
        click action override this; the default covers the common wiring."""
        for attr in ("open_popup", "open_panel", "on_click"):
            action = getattr(self, attr, None)
            if callable(action):
                action()
                return

    def activate_alternate(self):
        """Shift+Enter action (reset / set-minutes). No-op by default."""

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if event.modifiers() & Qt.ShiftModifier:
                self.activate_alternate()
            else:
                self.activate()
            event.accept()
            return
        super().keyPressEvent(event)

    def set_texts(self, title=None, body=None):
        changed = False
        if title is not None and title != self.title.text():
            self.title.setText(title)
            changed = True
        if body is not None and body != self.body.text():
            self.body.setText(body)
            changed = True
        if changed and self.STICKY:
            width = max(self.body.sizeHint().width(), self.title.sizeHint().width())
            if width > self._wmax:
                self._wmax = width
                self.setMinimumWidth(width + 24)
        return changed

    def tick(self):
        return False
