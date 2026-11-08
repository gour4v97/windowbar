
from datetime import datetime
import math
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame

import time

from .base import Card


class ClockCard(Card):
    id = "clock"
    name = "Clock"
    default_config = {"enabled": True}
    STICKY = True

    def __init__(self):
        super().__init__("Time")

    def tick(self):
        return self.set_texts(time.strftime("%a %d %b").upper(),
                              time.strftime("%I:%M %p").lstrip("0"))


class AnalogClockCard(QFrame):
    """Clock style: analogue face (the digital card is the other style)."""

    INTERVAL = 1

    def __init__(self, get_accent):
        super().__init__()
        self.setObjectName("card")
        self.get_accent = get_accent
        self.setFixedSize(62, 58)

    def tick(self):
        self.update()
        return False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        accent = QColor(self.get_accent() or "#ffffff")
        cx, cy, r = self.width() / 2, self.height() / 2, 24
        p.setPen(QColor(255, 255, 255, 90))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        now = datetime.now()
        for i in range(12):
            a = math.radians(i * 30 - 90)
            p.drawLine(QPoint(int(cx + 20 * math.cos(a)),
                              int(cy + 20 * math.sin(a))),
                       QPoint(int(cx + 23 * math.cos(a)),
                              int(cy + 23 * math.sin(a))))

        def hand(angle_deg, length, color, width):
            a = math.radians(angle_deg - 90)
            pen = p.pen()
            pen.setColor(color)
            pen.setWidth(width)
            p.setPen(pen)
            p.drawLine(QPoint(int(cx), int(cy)),
                       QPoint(int(cx + length * math.cos(a)),
                              int(cy + length * math.sin(a))))

        hand(now.hour % 12 * 30 + now.minute / 2, 13,
             QColor(255, 255, 255), 3)
        hand(now.minute * 6, 19, QColor(255, 255, 255), 2)
        hand(now.second * 6, 21, accent, 1)


# ------------------------------------------------------------- popups --------

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'clock'
WIDGET_ORDER = 1

def make_card(dock):
    return dock._clock_card()
