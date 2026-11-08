"""Live settings window for Windows Bar."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget, QMessageBox,
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
        display_name = (dock.target_screen.name()
                        if dock.target_screen is not None
                        else "Primary display")
        self.setWindowTitle(f"Windows Bar Settings — {display_name}")
        self.setMinimumSize(620, 480)
        self.tabs = QTabWidget(self)
        root = QVBoxLayout(self)
        root.addWidget(self.tabs)
        self._build_widgets_tab()
        self._build_layout_tab()
        self._build_appearance_tab()
        self._build_hotkeys_tab()
        self._build_window_manager_tab()
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
        order_button = QPushButton("Arrange widget order…")
        order_button.clicked.connect(self._arrange_widgets)
        layout.addWidget(order_button)
        self.tabs.addTab(page, "Widgets")

    def _arrange_widgets(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Arrange widgets")
        dialog.setMinimumSize(360, 420)
        layout = QVBoxLayout(dialog)
        listing = QListWidget(dialog)
        stored = self.dock.cfg.get("widget_order", [])
        fallback = list(WIDGET_LABELS)
        order = sorted(fallback, key=lambda key: stored.index(key)
                       if key in stored else len(stored) + fallback.index(key))
        for key in order:
            item = QListWidgetItem(WIDGET_LABELS[key])
            item.setData(Qt.UserRole, key)
            listing.addItem(item)
        layout.addWidget(listing)
        move_row = QHBoxLayout()
        up = QPushButton("Move up")
        down = QPushButton("Move down")
        move_row.addWidget(up)
        move_row.addWidget(down)
        layout.addLayout(move_row)

        def move_item(delta):
            source = listing.currentRow()
            target = source + delta
            if 0 <= source < listing.count() and 0 <= target < listing.count():
                item = listing.takeItem(source)
                listing.insertItem(target, item)
                listing.setCurrentRow(target)

        up.clicked.connect(lambda: move_item(-1))
        down.clicked.connect(lambda: move_item(1))
        buttons = QHBoxLayout()
        save = QPushButton("Save order")
        cancel = QPushButton("Cancel")
        save.clicked.connect(dialog.accept)
        cancel.clicked.connect(dialog.reject)
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)
        if dialog.exec():
            self.dock.cfg["widget_order"] = [
                listing.item(i).data(Qt.UserRole)
                for i in range(listing.count())]
            save_config(self.dock.cfg)
            self.dock.rebuild()

    def _build_layout_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        form.addRow(QLabel(
            "Widget and layout choices are saved independently per display."))
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
            ("desktop_widgets", "Show draggable desktop widgets"),
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
        self.custom_alt_tab = QCheckBox("Use Windows Bar window switcher for Alt+Tab")
        self.custom_alt_tab.toggled.connect(self._set_custom_alt_tab)
        form.addRow(self.custom_alt_tab)
        form.addRow(QLabel(
            "Use Alt+Tab / Alt+Shift+Tab to browse. Arrow keys also navigate; "
            "release Alt or press Enter to switch, Esc to cancel."))
        if not self.dock.is_primary_display:
            page.setEnabled(False)
            form.addRow(QLabel("Global hotkeys are configured on the primary display."))
        self.tabs.addTab(page, "Hotkeys")

    def _build_window_manager_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.window_tracking = QCheckBox("Track open application windows")
        self.window_tracking.toggled.connect(self._set_window_tracking)
        form.addRow(self.window_tracking)
        self.tiling_enabled = QCheckBox("Automatically tile windows (BSP)")
        self.tiling_enabled.toggled.connect(self._set_tiling_enabled)
        form.addRow(self.tiling_enabled)
        self.tiling_gap = QSpinBox()
        self.tiling_gap.setRange(0, 80)
        self.tiling_gap.setSuffix(" px")
        self.tiling_gap.valueChanged.connect(self._set_tiling_spacing)
        form.addRow("Gap between windows", self.tiling_gap)
        self.tiling_padding = QSpinBox()
        self.tiling_padding.setRange(0, 120)
        self.tiling_padding.setSuffix(" px")
        self.tiling_padding.valueChanged.connect(self._set_tiling_spacing)
        form.addRow("Screen edge padding", self.tiling_padding)
        form.addRow(QLabel(
            "BSP tiling moves visible taskbar windows on the primary monitor. "
            "Ctrl+Alt+Esc releases them and restores their saved positions."))
        if not self.dock.is_primary_display:
            page.setEnabled(False)
            form.addRow(QLabel(
                "Window tracking is configured on the primary display."))
        self.tabs.addTab(page, "Window manager")

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

    def _set_custom_alt_tab(self, enabled):
        self.dock.set_custom_alt_tab(enabled)

    def _set_window_tracking(self, enabled):
        self.dock.set_window_tracking(enabled)

    def _set_tiling_enabled(self, enabled):
        if not self.dock.set_tiling_enabled(enabled):
            self.tiling_enabled.blockSignals(True)
            self.tiling_enabled.setChecked(False)
            self.tiling_enabled.blockSignals(False)

    def _set_tiling_spacing(self, _value):
        self.dock.set_tiling_spacing(self.tiling_gap.value(),
                                     self.tiling_padding.value())

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
        self.custom_alt_tab.blockSignals(True)
        self.custom_alt_tab.setChecked(bool(cfg.get("custom_alt_tab", False)))
        self.custom_alt_tab.setEnabled(self.dock.is_primary_display)
        self.custom_alt_tab.blockSignals(False)
        self.window_tracking.blockSignals(True)
        self.window_tracking.setChecked(bool(cfg.get("window_tracking", False)))
        self.window_tracking.setEnabled(self.dock.is_primary_display)
        self.window_tracking.blockSignals(False)
        self.tiling_enabled.blockSignals(True)
        self.tiling_enabled.setChecked(bool(cfg.get("tiling_enabled", False)))
        self.tiling_enabled.setEnabled(self.dock.is_primary_display)
        self.tiling_enabled.blockSignals(False)
        self.tiling_gap.blockSignals(True)
        self.tiling_gap.setValue(int(cfg.get("tiling_gap", 12)))
        self.tiling_gap.setEnabled(self.dock.is_primary_display)
        self.tiling_gap.blockSignals(False)
        self.tiling_padding.blockSignals(True)
        self.tiling_padding.setValue(int(cfg.get("tiling_padding", 16)))
        self.tiling_padding.setEnabled(self.dock.is_primary_display)
        self.tiling_padding.blockSignals(False)
        modifier = cfg.get("app_hotkey_modifier", "alt").title()
        if self.app_modifier.findText(modifier) < 0:
            modifier = "Alt"
        self.app_modifier.blockSignals(True)
        self.app_modifier.setCurrentText(modifier)
        self.app_modifier.blockSignals(False)
        self._refresh_preview()
