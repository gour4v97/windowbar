"""Compact anchored audio and display control flyouts."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QSlider

import winapi
import theme
from native import brightness
from ui.popup import DetailPopup


class ControlFlyout(DetailPopup):
    def __init__(self, dock):
        super().__init__(dock, edge="bottom")
        self.setObjectName("controlflyout")
        tokens = dock.tokens
        self.setStyleSheet(
            dock.styleSheet()
            + f"QWidget#controlflyout {{ background: {theme.qss(tokens['panel'])}; "
            + f"border: 1px solid {theme.qss(tokens['border'])}; "
            + f"border-radius: {tokens['panel_radius']}px; }}")
        self.setMinimumWidth(260)
        form = QFormLayout(self)
        form.setContentsMargins(14, 12, 14, 12)
        self._brightness_timer = QTimer(self)
        self._brightness_timer.setSingleShot(True)
        self._brightness_timer.timeout.connect(self._apply_brightness)
        self._pending_brightness = None

        volume = winapi.get_volume()
        self.volume_label = QLabel("Unavailable")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setEnabled(volume is not None)
        if volume:
            self.volume_slider.setValue(round(volume[0] * 100))
            self.volume_label.setText(f"{round(volume[0] * 100)}%")
        self.volume_slider.valueChanged.connect(self._set_volume)
        form.addRow("Volume", self.volume_slider)
        form.addRow("", self.volume_label)
        self.mute_button = QPushButton(
            "Unmute" if volume and volume[1] else "Mute")
        self.mute_button.setEnabled(volume is not None)
        self.mute_button.clicked.connect(self._toggle_mute)
        form.addRow("", self.mute_button)

        level = brightness.get_brightness()
        if level is not None:
            self.brightness_label = QLabel(f"{level}%")
            self.brightness_slider = QSlider(Qt.Horizontal)
            self.brightness_slider.setRange(0, 100)
            self.brightness_slider.setValue(level)
            self.brightness_slider.valueChanged.connect(
                self._queue_brightness)
            form.addRow("Brightness", self.brightness_slider)
            form.addRow("", self.brightness_label)

    def _set_volume(self, value):
        winapi.set_volume(value / 100)
        self.volume_label.setText(f"{value}%")

    def _toggle_mute(self):
        volume = winapi.get_volume()
        if volume:
            winapi.set_mute(not volume[1])
            self.mute_button.setText("Unmute" if not volume[1] else "Mute")

    def _queue_brightness(self, value):
        self._pending_brightness = value
        self.brightness_label.setText(f"{value}%")
        self._brightness_timer.start(180)

    def _apply_brightness(self):
        if self._pending_brightness is not None:
            brightness.set_brightness(self._pending_brightness)
            self._pending_brightness = None

    def show_near(self, anchor, edge=None):
        self.adjustSize()
        return super().show_near(anchor, edge)

