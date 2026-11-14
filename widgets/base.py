"""Shared Qt card base and small display helpers."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from core.i18n import tr


def clip(text, n):
    text = str(text)
    return text if len(text) <= n else text[: n - 1] + "…"


class Card(QFrame):
    """A titled card refreshed by the dock's timer."""

    INTERVAL = 1
    ALWAYS = False
    STICKY = False

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
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
