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
        self.open_popup = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click for weather details")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.open_popup:
                self.open_popup()
            else:
                self.ask_city()

    def tick(self):
        return self.set_texts(self.weather.label, self.weather.text)


WIDGET_ID = 'weather'
WIDGET_ORDER = 4

def make_card(dock):
    card = WeatherCard(dock.weather, dock.ask_city)
    def show_details():
        geo = dock.cfg.get("weather_geo") or {}
        city = geo.get("name") or dock.cfg.get("weather_city") or "No city set"
        details = [f"Location: {city}", f"Current: {dock.weather.text}"]
        dock.show_widget_details(
            card, "Weather", details,
            [("Refresh", dock.weather.refresh), ("Change city", dock.ask_city)])
    card.open_popup = show_details
    return card
