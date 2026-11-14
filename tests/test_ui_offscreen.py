"""Qt smoke tests that run without a display (QT_QPA_PLATFORM=offscreen).

They are skipped when PySide6 is not installed. They cover the pieces that need
Qt but no Windows APIs; the Dock itself still needs an interactive Windows run.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_card_title_is_translated_and_uppercased(qapp, tmp_path):
    import json
    from core import i18n
    from widgets.base import Card

    (tmp_path / "xx.json").write_text(
        json.dumps({"Weather": "Mausam"}), encoding="utf-8")
    try:
        i18n.set_locale("xx", directory=tmp_path)
        assert Card("Weather").title.text() == "MAUSAM"
        i18n.set_locale("en", directory=tmp_path)
        assert Card("Weather").title.text() == "WEATHER"
    finally:
        i18n.set_locale("en")


def test_card_set_texts_reports_changes(qapp):
    from widgets.base import Card

    card = Card("Clock")
    assert card.set_texts(body="12:00") is True
    assert card.set_texts(body="12:00") is False


def test_plugin_card_works_through_the_registry(qapp, tmp_path):
    from core import plugins
    from core.registry import WidgetRegistry

    (tmp_path / "demo.py").write_text('''
from widgets.base import Card
WIDGET_ID = "demo_plugin"
def make_card(context):
    card = Card("Demo")
    card.set_texts(body=str(context.get_config("theme", "none")))
    return card
''', encoding="utf-8")
    try:
        modules, errors = plugins.load_plugins(tmp_path)
        assert errors == []
        dock = type("D", (), {"cfg": {"theme": "nord"}, "tokens": {}})()
        registry = WidgetRegistry()
        registry.register_modules(
            modules, plugins.PluginContext(dock), {"demo_plugin": True}, {})
        active = registry.start_enabled({"widgets": {"demo_plugin": True}})
        assert active["demo_plugin"].card().body.text() == "nord"
        registry.stop_all()
    finally:
        plugins.unload_plugins()
