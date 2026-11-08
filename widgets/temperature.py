"""Optional temperature widget for psutil or LibreHardwareMonitor sensors."""
import psutil
from widgets.base import Card

WIDGET_ID = "temperature"
WIDGET_ORDER = 28


def temperature_readings():
    """Return (sensor, Celsius) pairs; absent hardware support is normal."""
    try:
        groups = psutil.sensors_temperatures(fahrenheit=False) or {}
    except Exception:
        groups = {}
    readings = [(name, sensor.current) for name, sensors in groups.items()
                for sensor in sensors if sensor.current is not None]
    if readings:
        return readings
    try:
        import wmi
        client = wmi.WMI(namespace=r"root\LibreHardwareMonitor")
        return [(sensor.Name, float(sensor.Value))
                for sensor in client.Sensor(SensorType="Temperature")]
    except Exception:
        return []


class TemperatureCard(Card):
    INTERVAL = 15
    STICKY = True

    def __init__(self):
        super().__init__("Temperature")

    def tick(self):
        readings = temperature_readings()
        if not readings:
            return self.set_texts(body="No sensor available")
        name, value = readings[0]
        return self.set_texts(body=f"{name[:10]} {value:.0f}°C")


def make_card(dock):
    return TemperatureCard()
