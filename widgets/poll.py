from PySide6.QtCore import Qt
from widgets.base import Card, clip

class PollCard(Card):

    INTERVAL = 5

    def __init__(self, title, poll, on_click=None, hint=""):
        super().__init__(title)
        self.poll, self.on_click, self.hint = poll, on_click, hint
        if on_click:
            self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.on_click:
            self.on_click()

    def tick(self):
        if self.poll.value is not None:
            text = clip(str(self.poll.value), 30)
        elif self.poll.error:
            text = clip(self.poll.error, 30)
        else:
            text = "Loading…"
        return self.set_texts(body=text)
