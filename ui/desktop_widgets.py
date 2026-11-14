
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

import theme
from core.app_config import display_config_id, save_config
from widgets.clock import ClockCard
from widgets.cpu_ram import SystemCard


class DesktopWidgetsWindow(QWidget):
    """A draggable, non-activating panel kept behind ordinary app windows."""

    def __init__(self, dock):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint
                         | Qt.WindowStaysOnBottomHint
                         | Qt.WindowDoesNotAcceptFocus)
        self.dock = dock
        self.cfg = dock.cfg
        self.setObjectName("desktopWidgets")
        self.setWindowTitle("Windows Bar Desktop Widgets")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(340)
        self.setStyleSheet(dock.styleSheet())
        self._drag_offset = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)
        self.handle = QLabel("WINDOWS BAR · DRAG TO MOVE")
        self.handle.setObjectName("cardbody")
        self.handle.setAlignment(Qt.AlignCenter)
        root.addWidget(self.handle)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.clock = ClockCard()
        self.system = SystemCard()
        for widget_id, card in (("clock", self.clock), ("system", self.system)):
            card.setAttribute(Qt.WA_TransparentForMouseEvents)
            card.setStyleSheet(theme.build_widget_qss(theme.widget_tokens(
                dock.tokens, self.cfg.get("widget_styles", {}).get(widget_id, {}))))
            row.addWidget(card)
        root.addLayout(row)
        self._refresh = QTimer(self)
        self._refresh.timeout.connect(self._tick)
        self._refresh.start(1000)
        self._tick()
        self._place_initially()
        self.setStyleSheet(dock.styleSheet())

    def _tick(self):
        self.clock.tick()
        self.system.tick()

    def _geometry_key(self):
        screen = self.dock.target_screen
        return display_config_id(screen)

    def _place_initially(self):
        self.adjustSize()
        geometry = self.cfg.get("desktop_widgets_geometry", {})
        saved = geometry.get(self._geometry_key())
        screen = self.dock.target_screen
        area = screen.availableGeometry() if screen else self.frameGeometry()
        if isinstance(saved, list) and len(saved) == 2:
            x = min(max(int(saved[0]), area.left()),
                    max(area.left(), area.right() - self.width()))
            y = min(max(int(saved[1]), area.top()),
                    max(area.top(), area.bottom() - self.height()))
            self.move(x, y)
            return
        self.move(area.right() - self.width() - 24, area.top() + 72)

    def apply_theme(self):
        self.setStyleSheet(self.dock.styleSheet())
        for widget_id, card in (("clock", self.clock), ("system", self.system)):
            tokens = theme.widget_tokens(
                self.dock.tokens,
                self.cfg.get("widget_styles", {}).get(widget_id, {}))
            card.setStyleSheet(theme.build_widget_qss(tokens))

    def show_behind_windows(self):
        self.show()
        self.lower()
        # Reapply bottom z-order after Qt creates the native window handle.
        from native.windows import pin_behind_windows
        pin_behind_windows(int(self.winId()))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._save_position()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _save_position(self):
        positions = self.cfg.setdefault("desktop_widgets_geometry", {})
        positions[self._geometry_key()] = [self.x(), self.y()]
        save_config(self.cfg)

    def closeEvent(self, event):
        self._refresh.stop()
        self._save_position()
        super().closeEvent(event)
