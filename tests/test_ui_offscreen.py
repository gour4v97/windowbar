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


# --- Settings window -------------------------------------------------------
# The Dock itself needs Windows, so these tests drive SettingsWindow with a
# QWidget stand-in that carries a real config and recording dock methods.
# save_config / save_global_setting are stubbed so no real config is touched.

def _fake_dock(monkeypatch, primary=True, screen=None, tiling_ok=True):
    import copy
    import theme
    from types import SimpleNamespace
    from core.app_config import DEFAULTS

    dock = QtWidgets.QWidget()
    dock.cfg = copy.deepcopy(DEFAULTS)
    dock.tokens = theme.resolve(dock.cfg.get("theme", "midnight"))
    dock.target_screen = screen
    dock.is_primary_display = primary
    dock.calls = []
    dock.app_hotkeys = SimpleNamespace(
        register_all=lambda key: dock.calls.append(("register_all", key)))
    dock._tiling_hotkey_unavailable = []
    dock._tiling_release_status = ""
    dock._tiling_manager = None
    dock._tiling_invalid_title_patterns = []
    dock._tiling_hotkey_errors = {}
    dock._tiling_runtime_error = ""

    def set_widget(widget_id, enabled):
        dock.cfg["widgets"][widget_id] = bool(enabled)
        dock.calls.append(("set_widget", widget_id, bool(enabled)))

    def set_option(option, enabled):
        dock.cfg[option] = bool(enabled)
        dock.calls.append(("set_option", option, bool(enabled)))

    def set_shell_layout(value):
        dock.cfg["shell_layout"] = value
        dock.calls.append(("set_shell_layout", value))

    def set_theme(value):
        dock.cfg["theme"] = value
        dock.tokens = theme.resolve(value)
        dock.calls.append(("set_theme", value))

    dock.set_widget = set_widget
    dock.set_option = set_option
    dock.set_shell_layout = set_shell_layout
    dock.set_theme = set_theme
    dock.place = lambda: dock.calls.append(("place",))
    dock.sync_hotkey = lambda: dock.calls.append(("sync_hotkey",))
    dock.set_custom_alt_tab = lambda v: dock.calls.append(
        ("set_custom_alt_tab", bool(v)))
    dock.set_window_tracking = lambda v: dock.calls.append(
        ("set_window_tracking", bool(v)))
    dock.set_tiling_enabled = lambda v: dock.calls.append(
        ("set_tiling_enabled", bool(v))) or tiling_ok
    dock.set_tiling_release_hotkey = lambda text: dock.calls.append(
        ("set_tiling_release_hotkey", text)) or True
    dock.set_tiling_spacing = lambda gap, pad: dock.calls.append(
        ("set_tiling_spacing", gap, pad))
    dock.set_tiling_layout = lambda v: dock.calls.append(
        ("set_tiling_layout", v))
    dock.set_tiling_floating_rules = lambda a, c, t: dock.calls.append(
        ("set_tiling_floating_rules", a, c, t))
    dock.edit_widget_style = lambda: dock.calls.append(("edit_widget_style",))
    dock.clear_widget_style = lambda: dock.calls.append(
        ("clear_widget_style",))
    dock.rebuild = lambda: dock.calls.append(("rebuild",))
    return dock


def _settings(monkeypatch, qapp, **dock_kwargs):
    import ui.settings as settings_module
    saved = []

    def fake_save_config(cfg):
        saved.append(("save_config",))

    def fake_save_global(key, value):
        saved.append(("save_global", key, value))

    monkeypatch.setattr(settings_module, "save_config", fake_save_config)
    monkeypatch.setattr(settings_module, "save_global_setting",
                        fake_save_global)
    dock = _fake_dock(monkeypatch, **dock_kwargs)
    window = settings_module.SettingsWindow(dock)
    return window, dock, saved


def _tab_index(window, title):
    for i in range(window.tabs.count()):
        if window.tabs.tabText(i) == title:
            return i
    raise AssertionError(f"no tab {title!r}")


def _button(window, text):
    for button in window.findChildren(QtWidgets.QPushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"no button {text!r}")


def test_settings_window_builds_all_tabs(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    assert window.windowTitle() == "Windows Bar Settings — Primary display"
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        "Widgets", "Layout", "Appearance", "Hotkeys", "Window manager",
        "General"]
    from core.app_config import WIDGET_LABELS
    assert set(window.widget_checks) == set(WIDGET_LABELS)
    assert window.widget_checks["clock"].isChecked() is True
    languages = [window.language_choice.itemText(i)
                 for i in range(window.language_choice.count())]
    assert languages[0] == "System default"
    assert "English" in languages and "हिन्दी" in languages
    assert window.plugins_enabled.isChecked() is False
    assert window.plugin_status.text() == ""
    assert dock.calls == [] and saved == []  # construction is side-effect free


def test_settings_widget_toggle_updates_config(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    window.widget_checks["clock"].setChecked(False)
    assert ("set_widget", "clock", False) in dock.calls
    assert dock.cfg["widgets"]["clock"] is False
    window.widget_checks["weather"].setChecked(False)
    window.widget_checks["weather"].setChecked(True)
    assert dock.cfg["widgets"]["weather"] is True


def test_settings_language_change_saves_globally(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    window.language_choice.setCurrentIndex(
        window.language_choice.findData("hi"))
    assert dock.cfg["language"] == "hi"
    assert ("save_global", "language", "hi") in saved


def test_settings_plugins_toggle_and_status(qapp, monkeypatch, tmp_path):
    from core import plugins
    window, dock, saved = _settings(monkeypatch, qapp)
    window.plugins_enabled.setChecked(True)
    assert dock.cfg["plugins_enabled"] is True
    assert ("save_global", "plugins_enabled", True) in saved
    assert window.plugin_status.text() == "Plugins load when the app restarts."
    (tmp_path / "hello.py").write_text(
        'WIDGET_ID = "hello_plugin"\nWIDGET_LABEL = "Hello"\n'
        'def make_card(c): pass\n', encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    try:
        modules, errors = plugins.load_plugins(tmp_path)
        assert len(modules) == 1 and len(errors) == 1
        window._refresh_plugin_status()
        status = window.plugin_status.text()
        assert "Loaded plugins: hello_plugin" in status
        assert "broken" in status and "import failed" in status
    finally:
        plugins.unload_plugins()


def test_settings_refresh_reflects_config(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    dock.cfg["theme"] = "daylight"
    dock.cfg["position"] = "top"
    dock.cfg["widgets"]["clock"] = False
    dock.cfg["shell_layout"] = "split"
    window.refresh()
    assert window.theme_choice.currentText() == "daylight"
    assert window.position.currentText() == "top"
    assert window.position.isEnabled() is False  # split layout hides position
    assert window.widget_checks["clock"].isChecked() is False


def test_settings_position_and_theme_call_dock(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    window.position.setCurrentText("top")
    assert dock.cfg["position"] == "top"
    assert ("save_config",) in saved and ("place",) in dock.calls
    window.theme_choice.setCurrentText("daylight")
    assert ("set_theme", "daylight") in dock.calls


def test_settings_launcher_hotkey_valid_and_invalid(qapp, monkeypatch):
    import ui.settings as settings_module
    warned = []
    monkeypatch.setattr(settings_module.QMessageBox, "warning",
                        staticmethod(lambda *a: warned.append(a)))
    window, dock, saved = _settings(monkeypatch, qapp)
    window.launcher_key.setText("ctrl+shift+k")
    window.launcher_key.editingFinished.emit()
    assert dock.cfg["launcher_hotkey"] == "ctrl+shift+k"
    assert ("save_config",) in saved and ("sync_hotkey",) in dock.calls
    window.launcher_key.setText("bogus")
    window.launcher_key.editingFinished.emit()
    assert warned, "invalid hotkey must warn"
    assert window.launcher_key.text() == "ctrl+shift+k"  # restored
    assert dock.cfg["launcher_hotkey"] == "ctrl+shift+k"


def test_settings_tiling_controls_call_dock(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    window.tiling_gap.setValue(20)
    assert ("set_tiling_spacing", 20, 16) in dock.calls
    window.tiling_layout.setCurrentIndex(
        window.tiling_layout.findData("columns"))
    assert ("set_tiling_layout", "columns") in dock.calls
    window.floating_apps.setText("spotify.exe\ncode.exe")
    window.floating_classes.setText("Chrome_WidgetWin_1")
    window.floating_titles.setPlainText("Picture.*")
    _button(window, "Save floating rules").click()
    assert ("set_tiling_floating_rules", "spotify.exe\ncode.exe",
            "Chrome_WidgetWin_1", "Picture.*") in dock.calls
    window.tiling_enabled.setChecked(True)
    assert ("set_tiling_enabled", True) in dock.calls
    assert window.tiling_enabled.isChecked() is True


def test_settings_tiling_enable_reverts_when_dock_refuses(qapp, monkeypatch):
    window, dock, saved = _settings(
        monkeypatch, qapp, tiling_ok=False)
    window.tiling_enabled.setChecked(True)
    assert ("set_tiling_enabled", True) in dock.calls
    assert window.tiling_enabled.isChecked() is False


def test_settings_secondary_display_disables_hotkey_tabs(qapp, monkeypatch):
    from types import SimpleNamespace
    screen = SimpleNamespace(name=lambda: "Display 2")
    window, dock, saved = _settings(
        monkeypatch, qapp, primary=False, screen=screen)
    assert window.windowTitle() == "Windows Bar Settings — Display 2"
    assert window.tabs.widget(_tab_index(window, "Hotkeys")).isEnabled() is False
    assert window.tabs.widget(
        _tab_index(window, "Window manager")).isEnabled() is False
    assert window.custom_alt_tab.isEnabled() is False
    assert window.window_tracking.isEnabled() is False


def test_settings_export_import_use_config_store(qapp, monkeypatch, tmp_path):
    import ui.settings as settings_module
    from core import config as config_store
    exported, imported, informed = [], [], []
    monkeypatch.setattr(config_store, "export_config",
                        lambda *a: exported.append(a) or [])
    monkeypatch.setattr(config_store, "import_config",
                        lambda *a: imported.append(a) or {})
    monkeypatch.setattr(settings_module.QMessageBox, "information",
                        staticmethod(lambda *a: informed.append(a)))
    monkeypatch.setattr(settings_module.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a: (str(tmp_path / "out.json"), "")))
    monkeypatch.setattr(settings_module.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a: (str(tmp_path / "in.json"), "")))
    window, dock, saved = _settings(monkeypatch, qapp)
    _button(window, "Export settings…").click()
    assert len(exported) == 1 and str(tmp_path / "out.json") in exported[0]
    _button(window, "Import settings…").click()
    assert len(imported) == 1 and str(tmp_path / "in.json") in imported[0]
    assert informed and "Settings imported" in informed[0][2]


def _arrange_dialog(monkeypatch, window, accept=True, move_down=False):
    """Run _arrange_widgets with exec() stubbed: the stub drives the dialog
    instead of showing it, so the test never blocks on a modal popup."""
    import ui.settings as settings_module

    def fake_exec(self):
        listing = self.findChild(QtWidgets.QListWidget)
        if move_down:
            listing.setCurrentRow(0)
            for button in self.findChildren(QtWidgets.QPushButton):
                if button.text() == "Move down":
                    button.click()
        return 1 if accept else 0

    monkeypatch.setattr(settings_module.QDialog, "exec", fake_exec)
    _button(window, "Arrange widget order…").click()


def test_settings_arrange_widgets_save_order(qapp, monkeypatch):
    from core.app_config import WIDGET_LABELS
    window, dock, saved = _settings(monkeypatch, qapp)
    _arrange_dialog(monkeypatch, window, accept=True, move_down=True)
    order = dock.cfg["widget_order"]
    assert len(order) == len(WIDGET_LABELS)
    assert order[0] == list(WIDGET_LABELS)[1]
    assert order[1] == list(WIDGET_LABELS)[0]
    assert ("save_config",) in saved
    assert ("rebuild",) in dock.calls


def test_settings_arrange_widgets_cancel_keeps_order(qapp, monkeypatch):
    window, dock, saved = _settings(monkeypatch, qapp)
    _arrange_dialog(monkeypatch, window, accept=False, move_down=True)
    assert dock.cfg["widget_order"] == []
    assert saved == [] and ("rebuild",) not in dock.calls


def test_settings_arrange_widgets_respects_stored_order(qapp, monkeypatch):
    import ui.settings as settings_module
    from PySide6.QtCore import Qt
    from core.app_config import WIDGET_LABELS
    window, dock, saved = _settings(monkeypatch, qapp)
    dock.cfg["widget_order"] = ["weather", "clock"]
    seen = []

    def fake_exec(self):
        listing = self.findChild(QtWidgets.QListWidget)
        seen.extend(listing.item(i).data(Qt.UserRole)
                    for i in range(listing.count()))
        return 0

    monkeypatch.setattr(settings_module.QDialog, "exec", fake_exec)
    _button(window, "Arrange widget order…").click()
    expected = ["weather", "clock"] + [
        key for key in WIDGET_LABELS if key not in ("weather", "clock")]
    assert seen == expected
