"""Now-playing media card."""
from PySide6.QtCore import Qt
from widgets.base import Card, clip

class MediaCard(Card):
    INTERVAL = 2

    def __init__(self, media):
        super().__init__("Now playing")
        self.media = media
        self.open_popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: details and playback controls")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.open_popup:
                self.open_popup()
            else:
                self.media.toggle()

    def tick(self):
        m = self.media
        if not m.available:
            return self.set_texts("NOW PLAYING", "Media support not installed")
        if not m.has_session:
            return self.set_texts("NOW PLAYING", "Nothing playing")
        text = m.title + (f" — {m.artist}" if m.artist else "")
        return self.set_texts("NOW PLAYING " + ("▶" if m.playing else "❚❚"),
                              clip(text, 28))


WIDGET_ID = 'media'
WIDGET_ORDER = 12

def make_card(dock):
    card = MediaCard(dock.media)
    def show_details():
        media = dock.media
        if not media.available:
            details = ["Media controls are unavailable (install the optional media support)."]
        elif not media.has_session:
            details = ["Nothing is currently playing."]
        else:
            details = [media.title or "Unknown title",
                       media.artist or "Unknown artist",
                       "Playing" if media.playing else "Paused"]
        dock.show_widget_details(
            card, "Now playing", details,
            [("Play / pause", media.toggle)] if media.available else [])
    card.open_popup = show_details
    return card
