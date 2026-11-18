"""Generate clean UI screenshots for documentation and README."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from ui.dock import Dock
from ui.settings import SettingsWindow


def generate():
    app = QApplication.instance() or QApplication(sys.argv)
    font_path = "C:/Windows/Fonts/segoeui.ttf"
    if Path(font_path).exists():
        font_id = QFontDatabase.addApplicationFont(font_path)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))

    out_dir = ROOT / "docs" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    dock = Dock(None)
    dock.show()

    # Capture Midnight theme
    dock.cfg["theme"] = "midnight"
    dock.apply_theme()
    dock.adjustSize()
    pix_midnight = dock.grab()
    pix_midnight.save(str(out_dir / "dock_midnight.png"))
    print("Saved dock_midnight.png")

    # Capture Nord theme
    dock.cfg["theme"] = "nord"
    dock.apply_theme()
    dock.adjustSize()
    pix_nord = dock.grab()
    pix_nord.save(str(out_dir / "dock_nord.png"))
    print("Saved dock_nord.png")

    # Capture Settings Window (Widgets tab)
    settings = SettingsWindow(dock)
    settings.show()
    settings.adjustSize()
    pix_settings = settings.grab()
    pix_settings.save(str(out_dir / "settings_preview.png"))
    print("Saved settings_preview.png")

    # Capture Settings Window (Appearance tab)
    settings.tabs.setCurrentIndex(2)
    settings.adjustSize()
    pix_appearance = settings.grab()
    pix_appearance.save(str(out_dir / "settings_appearance.png"))
    print("Saved settings_appearance.png")

    dock.shutdown()
    print("All screenshots generated successfully.")


if __name__ == "__main__":
    generate()
