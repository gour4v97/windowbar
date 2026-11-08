"""Live settings window for Windows Bar."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget, QMessageBox,
)

import theme
import search
from core.app_config import THEMES_DIR, WIDGET_LABELS, save_config


class SettingsWindow(QDialog):
    """Separate settings window; changes are applied to the running dock."""

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("Windows Bar Settings")
        self.setMinimumSize(620, 480)
        self.tabs = QTabWidget(self)
        root = QVBoxLayout(self)
        root.addWidget(self.tabs)
        self._build_widgets_tab()
        self._build_layout_tab()
        self._build_appearance_tab()
        self._build_hotkeys_tab()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self.refresh()

    def _build_widgets_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Choose which widgets appear on the bar."))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        self.widget_checks = {}
        for i, (key, label) in enumerate(WIDGET_LABELS.items()):
            check = QCheckBox(label)
            check.toggled.connect(
                lambda enabled, widget_id=key:
                self.dock.set_widget(widget_id, enabled))
            grid.addWidget(check, i // 2, i % 2)
            self.widget_checks[key] = check
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.tabs.addTab(page, "Widgets")

    def _build_layout_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.position = QComboBox()
        self.position.addItems(["bottom", "top"])
        self.position.currentTextChanged.connect(self._set_position)
        form.addRow("Bar position", self.position)
        self.shell_layout = QComboBox()
        self.shell_layout.addItem("Combined bar", "combined")
        self.shell_layout.addItem("Separate top toolbar and app dock", "split")
        self.shell_layout.currentIndexChanged.connect(self._set_shell_layout)
        form.addRow("Shell layout", self.shell_layout)
        self.option_checks = {}
        for key, label in (
            ("full_width", "Full width"),
            ("reserve_space", "Reserve screen space"),
            ("auto_hide", "Auto-hide dock"),
            ("glass", "Glass effect"),
            ("dynamic_accent", "Dynamic wallpaper accent"),
        ):
            check = QCheckBox(label)
            check.toggled.connect(
                lambda enabled, option=key:
                self.dock.set_option(option, enabled))
            form.addRow(check)
            self.option_checks[key] = check
        self.tabs.addTab(page, "Layout")

    def _build_appearance_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.theme_choice = QComboBox()
        self.theme_choice.addItems(theme.list_themes(THEMES_DIR))
        self.theme_choice.currentTextChanged.connect(self._set_theme)
        form.addRow("Theme", self.theme_choice)
        layout.addLayout(form)
        layout.addWidget(QLabel("Preview"))
        self.preview = QFrame()
        self.preview.setObjectName("card")
        preview_layout = QVBoxLayout(self.preview)
        title = QLabel("WINDOWS BAR")
        title.setObjectName("cardtitle")
        body = QLabel("A live theme preview")
        body.setObjectName("cardbody")
        preview_layout.addWidget(title)
        preview_layout.addWidget(body)
        layout.addWidget(self.preview)
        styles = QHBoxLayout()
        edit = QPushButton("Edit widget style…")
        edit.clicked.connect(self._edit_widget_style)
        reset = QPushButton("Reset widget style…")
        reset.clicked.connect(self._reset_widget_style)
        styles.addWidget(edit)
        styles.addWidget(reset)
        layout.addLayout(styles)
        layout.addStretch(1)
        self.tabs.addTab(page, "Appearance")

    def _build_hotkeys_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.launcher_key = QLineEdit()
        self.launcher_key.setPlaceholderText("alt+space")
        self.launcher_key.editingFinished.connect(self._set_launcher_hotkey)
        form.addRow("Launcher hotkey", self.launcher_key)
        self.app_modifier = QComboBox()
        self.app_modifier.addItems(["Alt", "Ctrl+Alt", "Win"])
        self.app_modifier.currentTextChanged.connect(self._set_app_modifier)
        form.addRow("Pinned apps 1–9", self.app_modifier)
        form.addRow(QLabel("Pinned shortcuts open or focus the first nine apps."))
        self.tabs.addTab(page, "Hotkeys")

    def _edit_widget_style(self):
        self.dock.edit_widget_style()
        self._refresh_preview()

    def _reset_widget_style(self):
        self.dock.clear_widget_style()
        self._refresh_preview()

    def _set_position(self, value):
        if value and value != self.dock.cfg.get("position"):
            self.dock.cfg["position"] = value
            save_config(self.dock.cfg)
            self.dock.place()

    def _set_shell_layout(self, index):
        value = self.shell_layout.itemData(index)
        if value:
            self.dock.set_shell_layout(value)
            self.refresh()

    def _set_theme(self, value):
        if value and value != self.dock.cfg.get("theme"):
            self.dock.set_theme(value)
        self._refresh_preview()

    def _set_launcher_hotkey(self):
        value = self.launcher_key.text().strip()
        if value and value != self.dock.cfg.get("launcher_hotkey"):
            if search.parse_hotkey(value) is None:
                QMessageBox.warning(
                    self, "Invalid hotkey",
                    "Use a modifier and key, for example alt+space or ctrl+shift+k.")
                self.launcher_key.setText(
                    self.dock.cfg.get("launcher_hotkey", "alt+space"))
                return
            self.dock.cfg["launcher_hotkey"] = value
            save_config(self.dock.cfg)
            self.dock.sync_hotkey()

    def _set_app_modifier(self, value):
        key = value.lower()
        if key != self.dock.cfg.get("app_hotkey_modifier", "alt"):
            self.dock.cfg["app_hotkey_modifier"] = key
            self.dock.app_hotkeys.register_all(key)
            save_config(self.dock.cfg)

    def _refresh_preview(self):
        self.setStyleSheet(theme.build_qss(self.dock.tokens))
        overrides = self.dock.cfg.get("widget_styles", {}).get("clock", {})
        tokens = theme.widget_tokens(self.dock.tokens, overrides)
        self.preview.setStyleSheet(theme.build_widget_qss(tokens))

    def refresh(self):
        cfg = self.dock.cfg
        for key, check in self.widget_checks.items():
            check.blockSignals(True)
            check.setChecked(bool(cfg["widgets"].get(key, False)))
            check.blockSignals(False)
        self.position.blockSignals(True)
        self.position.setCurrentText(cfg.get("position", "bottom"))
        self.position.blockSignals(False)
        self.shell_layout.blockSignals(True)
        layout_index = self.shell_layout.findData(
            cfg.get("shell_layout", "combined"))
        self.shell_layout.setCurrentIndex(max(0, layout_index))
        self.shell_layout.blockSignals(False)
        self.position.setEnabled(cfg.get("shell_layout") != "split")
        for key, check in self.option_checks.items():
            check.blockSignals(True)
            check.setChecked(bool(cfg.get(key, False)))
            check.blockSignals(False)
        self.theme_choice.blockSignals(True)
        if self.theme_choice.findText(cfg.get("theme", "midnight")) < 0:
            self.theme_choice.addItem(cfg.get("theme", "midnight"))
        self.theme_choice.setCurrentText(cfg.get("theme", "midnight"))
        self.theme_choice.blockSignals(False)
        self.launcher_key.setText(cfg.get("launcher_hotkey", "alt+space"))
        modifier = cfg.get("app_hotkey_modifier", "alt").title()
        if self.app_modifier.findText(modifier) < 0:
            modifier = "Alt"
        self.app_modifier.blockSignals(True)
        self.app_modifier.setCurrentText(modifier)
        self.app_modifier.blockSignals(False)
        self._refresh_preview()

