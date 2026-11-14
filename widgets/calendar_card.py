"""Next-event calendar card."""
from datetime import datetime
from PySide6.QtCore import Qt
from widgets.base import Card, clip
from core.formatting import fmt_delta

class CalendarCard(Card):
    INTERVAL = 5

    def __init__(self, calendar, ask_link):
        super().__init__("Next event")
        self.calendar, self.ask_link = calendar, ask_link
        self.open_popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click: month view")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.open_popup:
                self.open_popup()
            else:
                self.ask_link()

    def tick(self):
        cal = self.calendar
        if cal.status:
            return self.set_texts("NEXT EVENT", cal.status)
        nxt = cal.next_event()
        if not nxt:
            return self.set_texts("NEXT EVENT", "Nothing soon")
        dt, title = nxt
        delta = fmt_delta((dt - datetime.now()).total_seconds())
        return self.set_texts("NEXT · " + delta.upper(), clip(title, 26))


WIDGET_ID = 'calendar'
WIDGET_ORDER = 15

def make_card(dock):
    return dock._calendar_card()
