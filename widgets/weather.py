"""Weather card widget."""

from PySide6.QtCore import Qt

from .base import Card


class WeatherCard(Card):
    id = "weather"
    name = "Weather"
    default_config = {"enabled": True}
    INTERVAL = 5

    def __init__(self, weather, ask_city):
        super().__init__("Weather")
        self.weather, self.ask_city = weather, ask_city
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to change city")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.ask_city()

    def tick(self):
        return self.set_texts(self.weather.label, self.weather.text)

from core.app_config import save_config, in_quiet_hours

WIDGET_ID = 'weather'
WIDGET_ORDER = 4

def make_card(dock):
    return WeatherCard(dock.weather, dock.ask_city)
