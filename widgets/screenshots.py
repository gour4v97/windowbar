"""Screenshot folder widget."""
from pathlib import Path
from .downloads import DownloadsCard

WIDGET_ID = "shots"
WIDGET_ORDER = 6

def make_card(dock):
    return DownloadsCard(dock.poll("shots"), "Screenshots",
                         Path.home() / "Pictures" / "Screenshots")
