"""Clock card widget."""

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
