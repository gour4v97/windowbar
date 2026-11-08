"""
Windows Bar - a smart dock for Windows 10/11.

Run:   pip install -r requirements.txt
       python windowsbar.py

Right-click the dock for the menu. Settings live in %APPDATA%\\Windows Bar\\config.json
Stripe revenue reads the key from the WINDOWSBAR_STRIPE_KEY environment variable.
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
    dock = Dock()
    app.aboutToQuit.connect(dock.shutdown)
    dock.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
