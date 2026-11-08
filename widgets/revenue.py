"""Revenue polling widget."""
from .poll import PollCard

WIDGET_ID = "revenue"
WIDGET_ORDER = 20

def make_card(dock):
    return PollCard("Revenue", dock.poll("revenue"))
