"""GitHub status polling widget."""
from .poll import PollCard

WIDGET_ID = "github"
WIDGET_ORDER = 19

def make_card(dock):
    return PollCard("GitHub", dock.poll("github"), dock.ask_github)
