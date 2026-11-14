"""
Windows Bar - a smart dock for Windows 10/11.
"""
import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from core.app_config import APP_DIR
from core.logging_setup import configure_logging
from ui.dock import Dock

_log = logging.getLogger("windowsbar")


def main():
    log_path = configure_logging(APP_DIR)
    _log.info("Windows Bar starting (log file: %s)", log_path)
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    all_screens = app.screens() or [None]
    primary_screen = app.primaryScreen() or all_screens[0]
    screens = ([primary_screen]
               + [screen for screen in all_screens
                  if screen != primary_screen])
    docks = []
    primary = Dock(screens[0])
    docks.append(primary)

    def track_screen(dock):
        screen = dock.target_screen
        if screen is not None:
            screen.geometryChanged.connect(
                lambda _geometry, bar=dock: bar.place())
            screen.availableGeometryChanged.connect(
                lambda _geometry, bar=dock: bar.place())

    track_screen(primary)
    for screen in screens[1:]:
        dock = Dock(screen, shared_shell=primary)
        docks.append(dock)
        track_screen(dock)

    def add_display(screen):
        if any(dock.target_screen == screen for dock in docks):
            return
        dock = Dock(screen, shared_shell=primary)
        docks.append(dock)
        track_screen(dock)
        app.aboutToQuit.connect(dock.shutdown)
        dock.show()

    def remove_display(screen):
        for dock in list(docks):
            if dock.target_screen == screen and dock is not primary:
                docks.remove(dock)
                try:
                    app.aboutToQuit.disconnect(dock.shutdown)
                except (TypeError, RuntimeError):
                    pass
                dock.shutdown()
                dock.close()
                dock.deleteLater()

    app.screenAdded.connect(add_display)
    app.screenRemoved.connect(remove_display)
    for dock in docks:
        app.aboutToQuit.connect(dock.shutdown)
        dock.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

