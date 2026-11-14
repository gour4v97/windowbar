"""Volume card."""
from PySide6.QtCore import Qt
import winapi
from widgets.base import Card

class VolumeCard(Card):
    INTERVAL = 2
    STICKY = True

    def __init__(self, dock=None):
        super().__init__("Volume")
        self.dock = dock
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: volume and brightness controls   Scroll: volume")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.dock is not None:
                from ui.flyouts import ControlFlyout
                ControlFlyout(self.dock).show_near(self)
        elif e.button() == Qt.RightButton:
            v = winapi.get_volume()
            if v:
                winapi.set_mute(not v[1])
            self.tick()

    def wheelEvent(self, e):
        v = winapi.get_volume()
        if v:
            step = 0.05 if e.angleDelta().y() > 0 else -0.05
            winapi.set_volume(v[0] + step)
        self.tick()

    def tick(self):
        v = winapi.get_volume()
        if v is None:
            return self.set_texts(body="No device")
        level, muted = v
        return self.set_texts(body="Muted" if muted else f"{level * 100:.0f}%")


WIDGET_ID = 'volume'
WIDGET_ORDER = 13

def make_card(dock):
    return VolumeCard(dock)

