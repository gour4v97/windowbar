"""Live settings window for Windows Bar."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QPlainTextEdit, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
    QMessageBox, QFileDialog,
)

import theme
import search
from core import config as config_store
from core import plugins
from core.app_config import (CONFIG, DEFAULTS, PLUGINS_DIR, THEMES_DIR,
                             WIDGET_LABELS, save_config, save_global_setting)
from core.i18n import available_locales, tr


class SettingsWindow(QDialog):

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
        self._build_general_tab()
        close = QPushButton(tr("Close"))
        close.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self.refresh()

    def _build_widgets_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(tr("Choose which widgets appear on the bar.")))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        self.widget_checks = {}
        for i, (key, label) in enumerate(WIDGET_LABELS.items()):
            check = QCheckBox(tr(label))
            check.toggled.connect(
                lambda enabled, widget_id=key:
                self.dock.set_widget(widget_id, enabled))
            grid.addWidget(check, i // 2, i % 2)
            self.widget_checks[key] = check
        scroll.setWidget(content)
        layout.addWidget(scroll)
        order_button = QPushButton(tr("Arrange widget order…"))
        order_button.clicked.connect(self._arrange_widgets)
        layout.addWidget(order_button)
        self.tabs.addTab(page, tr("Widgets"))

    def _arrange_widgets(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Arrange widgets"))
        dialog.setMinimumSize(360, 420)
        layout = QVBoxLayout(dialog)
        listing = QListWidget(dialog)
        stored = self.dock.cfg.get("widget_order", [])
        fallback = list(WIDGET_LABELS)
        order = sorted(fallback, key=lambda key: stored.index(key)
                       if key in stored else len(stored) + fallback.index(key))
        for key in order:
            item = QListWidgetItem(tr(WIDGET_LABELS[key]))
            item.setData(Qt.UserRole, key)
            listing.addItem(item)
        layout.addWidget(listing)
        move_row = QHBoxLayout()
        up = QPushButton(tr("Move up"))
        down = QPushButton(tr("Move down"))
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
        save = QPushButton(tr("Save order"))
        cancel = QPushButton(tr("Cancel"))
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
            tr("Widget and layout choices are saved independently per display.")))
        self.position = QComboBox()
        self.position.addItems(["bottom", "top"])
        self.position.currentTextChanged.connect(self._set_position)
        form.addRow(tr("Bar position"), self.position)
        self.shell_layout = QComboBox()
        self.shell_layout.addItem(tr("Combined bar"), "combined")
        self.shell_layout.addItem(tr("Separate top toolbar and app dock"), "split")
        self.shell_layout.currentIndexChanged.connect(self._set_shell_layout)
        form.addRow(tr("Shell layout"), self.shell_layout)
        self.option_checks = {}
        for key, label in (
            ("full_width", tr("Full width")),
            ("reserve_space", tr("Reserve screen space")),
            ("auto_hide", tr("Auto-hide dock")),
            ("glass", tr("Glass effect")),
            ("dynamic_accent", tr("Dynamic wallpaper accent")),
            ("desktop_widgets", tr("Show draggable desktop widgets")),
        ):
            check = QCheckBox(label)
            check.toggled.connect(
                lambda enabled, option=key:
                self.dock.set_option(option, enabled))
            form.addRow(check)
            self.option_checks[key] = check
        self.tabs.addTab(page, tr("Layout"))

    def _build_appearance_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.theme_choice = QComboBox()
        self.theme_choice.addItems(theme.list_themes(THEMES_DIR))
        self.theme_choice.currentTextChanged.connect(self._set_theme)
        form.addRow(tr("Theme"), self.theme_choice)
        layout.addLayout(form)
        layout.addWidget(QLabel(tr("Preview")))
        self.preview = QFrame()
        self.preview.setObjectName("card")
        preview_layout = QVBoxLayout(self.preview)
        title = QLabel(tr("WINDOWS BAR"))
        title.setObjectName("cardtitle")
        body = QLabel(tr("A live theme preview"))
        body.setObjectName("cardbody")
        preview_layout.addWidget(title)
        preview_layout.addWidget(body)
        layout.addWidget(self.preview)
        styles = QHBoxLayout()
        edit = QPushButton(tr("Edit widget style…"))
        edit.clicked.connect(self._edit_widget_style)
        reset = QPushButton(tr("Reset widget style…"))
        reset.clicked.connect(self._reset_widget_style)
        styles.addWidget(edit)
        styles.addWidget(reset)
        layout.addLayout(styles)
        layout.addStretch(1)
        self.tabs.addTab(page, tr("Appearance"))

    def _build_general_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.language_choice = QComboBox()
        self.language_choice.addItem(tr("System default"), "system")
        for tag in available_locales():
            self.language_choice.addItem(tag, tag)
        current = self.dock.cfg.get("language", "system")
        index = self.language_choice.findData(current)
        self.language_choice.setCurrentIndex(max(index, 0))
        self.language_choice.currentIndexChanged.connect(self._set_language)
        form.addRow(tr("Language"), self.language_choice)
        self.plugins_enabled = QCheckBox(
            tr("Load widget plugins from the plugins folder"))
        self.plugins_enabled.setChecked(
            bool(self.dock.cfg.get("plugins_enabled")))
        self.plugins_enabled.toggled.connect(self._set_plugins_enabled)
        form.addRow(tr("Plugins"), self.plugins_enabled)
        layout.addLayout(form)
        note = QLabel(tr(
            "Language and plugin changes apply after restarting Windows Bar. "
            "Plugins are Python code and run with your permissions; only "
            "enable ones you trust."))
        note.setWordWrap(True)
        layout.addWidget(note)
        self.plugin_status = QLabel("")
        self.plugin_status.setWordWrap(True)
        layout.addWidget(self.plugin_status)
        open_plugins = QPushButton(tr("Open plugins folder"))
        open_plugins.clicked.connect(self._open_plugins_folder)
        layout.addWidget(open_plugins)
        backup = QHBoxLayout()
        export = QPushButton(tr("Export settings…"))
        export.clicked.connect(self._export_settings)
        import_ = QPushButton(tr("Import settings…"))
        import_.clicked.connect(self._import_settings)
        backup.addWidget(export)
        backup.addWidget(import_)
        layout.addLayout(backup)
        layout.addStretch(1)
        self.tabs.addTab(page, tr("General"))
        self._refresh_plugin_status()

    def _set_language(self, index):
        value = self.language_choice.itemData(index)
        if value and value != self.dock.cfg.get("language", "system"):
            self.dock.cfg["language"] = value
            save_global_setting("language", value)

    def _set_plugins_enabled(self, enabled):
        self.dock.cfg["plugins_enabled"] = bool(enabled)
        save_global_setting("plugins_enabled", bool(enabled))
        self._refresh_plugin_status()

    def _refresh_plugin_status(self):
        loaded = [module.WIDGET_ID for module in plugins.loaded_modules()]
        errors = plugins.load_errors()
        lines = []
        if loaded:
            lines.append(tr("Loaded plugins: {names}", names=", ".join(loaded)))
        for error in errors:
            lines.append(f"{error.name}: {error.reason}")
        if not lines and self.dock.cfg.get("plugins_enabled"):
            lines.append(tr("Plugins load when the app restarts."))
        self.plugin_status.setText("\n".join(lines))

    def _open_plugins_folder(self):
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.startfile(str(PLUGINS_DIR))
        except (AttributeError, OSError) as exc:
            QMessageBox.warning(self, tr("Plugins"), str(exc))

    def _export_settings(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Export settings"), "windows-bar-settings.json",
            "JSON (*.json)")
        if not path:
            return
        try:
            redacted = config_store.export_config(CONFIG, DEFAULTS, path)
        except OSError as exc:
            QMessageBox.warning(self, tr("Export settings"), str(exc))
            return
        if redacted:
            QMessageBox.information(
                self, tr("Export settings"),
                tr("Private values were left out: {keys}",
                   keys=", ".join(redacted)))

    def _import_settings(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Import settings"), "", "JSON (*.json)")
        if not path:
            return
        try:
            config_store.import_config(path, CONFIG, DEFAULTS)
        except config_store.ConfigImportError as exc:
            QMessageBox.warning(self, tr("Import settings"), str(exc))
            return
        QMessageBox.information(
            self, tr("Import settings"),
            tr("Settings imported. Restart Windows Bar to apply them."))

    def _build_hotkeys_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.launcher_key = QLineEdit()
        self.launcher_key.setPlaceholderText(tr("alt+space"))
        self.launcher_key.editingFinished.connect(self._set_launcher_hotkey)
        form.addRow(tr("Launcher hotkey"), self.launcher_key)
        self.app_modifier = QComboBox()
        self.app_modifier.addItems(["Alt", "Ctrl+Alt", "Win"])
        self.app_modifier.currentTextChanged.connect(self._set_app_modifier)
        form.addRow(tr("Pinned apps 1–9"), self.app_modifier)
        form.addRow(QLabel(tr("Pinned shortcuts open or focus the first nine apps.")))
        self.custom_alt_tab = QCheckBox(tr("Use Windows Bar window switcher for Alt+Tab"))
        self.custom_alt_tab.toggled.connect(self._set_custom_alt_tab)
        form.addRow(self.custom_alt_tab)
        form.addRow(QLabel(
            tr("Use Alt+Tab / Alt+Shift+Tab to browse. Arrow keys also navigate; "
            "release Alt or press Enter to switch, Esc to cancel.")))
        if not self.dock.is_primary_display:
            page.setEnabled(False)
            form.addRow(QLabel(tr("Global hotkeys are configured on the primary display.")))
        self.tabs.addTab(page, tr("Hotkeys"))

    def _build_window_manager_tab(self):
        page = QWidget()
        form = QFormLayout(page)
        self.window_tracking = QCheckBox(tr("Track open application windows"))
        self.window_tracking.toggled.connect(self._set_window_tracking)
        form.addRow(self.window_tracking)
        self.tiling_enabled = QCheckBox(tr("Automatically tile windows"))
        self.tiling_enabled.toggled.connect(self._set_tiling_enabled)
        form.addRow(self.tiling_enabled)
        self.tiling_release_key = QLineEdit()
        self.tiling_release_key.setPlaceholderText(tr("ctrl+alt+esc"))
        self.save_tiling_release_key = QPushButton(tr("Save safe-release shortcut"))
        self.save_tiling_release_key.clicked.connect(self._save_tiling_release_key)
        form.addRow(tr("Safe-release shortcut"), self.tiling_release_key)
        form.addRow(self.save_tiling_release_key)
        self.tiling_layout = QComboBox()
        self.tiling_layout.addItem(tr("BSP"), "bsp")
        self.tiling_layout.addItem(tr("Columns"), "columns")
        self.tiling_layout.addItem(tr("Master / stack"), "stack")
        self.tiling_layout.currentIndexChanged.connect(
            lambda index: self.dock.set_tiling_layout(
                self.tiling_layout.itemData(index)))
        form.addRow(tr("Layout engine"), self.tiling_layout)
        self.tiling_gap = QSpinBox()
        self.tiling_gap.setRange(0, 80)
        self.tiling_gap.setSuffix(" px")
        self.tiling_gap.valueChanged.connect(self._set_tiling_spacing)
        form.addRow(tr("Gap between windows"), self.tiling_gap)
        self.tiling_padding = QSpinBox()
        self.tiling_padding.setRange(0, 120)
        self.tiling_padding.setSuffix(" px")
        self.tiling_padding.valueChanged.connect(self._set_tiling_spacing)
        form.addRow(tr("Screen edge padding"), self.tiling_padding)
        self.floating_apps = QLineEdit()
        self.floating_apps.setPlaceholderText(tr("One executable per line, e.g. spotify.exe"))
        form.addRow(tr("Float executable names"), self.floating_apps)
        self.floating_classes = QLineEdit()
        self.floating_classes.setPlaceholderText(tr("One window class per line"))
        form.addRow(tr("Float window classes"), self.floating_classes)
        self.floating_titles = QPlainTextEdit()
        self.floating_titles.setPlaceholderText(
            tr("One case-insensitive title regular expression per line"))
        self.floating_titles.setMaximumHeight(72)
        form.addRow(tr("Float title patterns"), self.floating_titles)
        self.save_floating_rules = QPushButton(tr("Save floating rules"))
        self.save_floating_rules.clicked.connect(self._save_floating_rules)
        form.addRow(self.save_floating_rules)
        self.tiling_status = QLabel()
        form.addRow(self.tiling_status)
        form.addRow(QLabel(
            tr("BSP tiling moves visible taskbar windows on each monitor. "
            "Ctrl+Alt+J focuses the next tiled window, Ctrl+Alt+K swaps its "
            "slot, Ctrl+Alt+H/L resizes the focused split, Ctrl+Alt+T cycles the layout, Ctrl+Alt+F "
            "toggles floating, and Ctrl+Alt+Shift+Left/Right moves the "
            "focused window to the previous/next virtual desktop. Ctrl+Alt+Esc "
            "releases windows. Per-workspace order and split sizes are saved.")))
        if not self.dock.is_primary_display:
            page.setEnabled(False)
            form.addRow(QLabel(
                tr("Window tracking is configured on the primary display.")))
        self.tabs.addTab(page, tr("Window manager"))

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

    def _save_tiling_release_key(self):
        if self.dock.set_tiling_release_hotkey(self.tiling_release_key.text()):
            self.refresh()

    def _set_tiling_spacing(self, _value):
        self.dock.set_tiling_spacing(self.tiling_gap.value(),
                                     self.tiling_padding.value())

    def _set_tiling_layout(self, value):
        self.dock.set_tiling_layout(value)

    def _save_floating_rules(self):
        self.dock.set_tiling_floating_rules(
            self.floating_apps.text(), self.floating_classes.text(),
            self.floating_titles.toPlainText())
        self.refresh()

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
        self.tiling_release_key.blockSignals(True)
        self.tiling_release_key.setText(cfg.get(
            "tiling_release_hotkey", "ctrl+alt+esc"))
        self.tiling_release_key.setEnabled(
            self.dock.is_primary_display and not cfg.get("tiling_enabled"))
        self.save_tiling_release_key.setEnabled(
            self.dock.is_primary_display and not cfg.get("tiling_enabled"))
        self.tiling_release_key.blockSignals(False)
        self.tiling_layout.blockSignals(True)
        layout_index = self.tiling_layout.findData(
            cfg.get("tiling_layout", "bsp"))
        self.tiling_layout.setCurrentIndex(max(0, layout_index))
        self.tiling_layout.setEnabled(self.dock.is_primary_display)
        self.tiling_layout.blockSignals(False)
        self.tiling_gap.blockSignals(True)
        self.tiling_gap.setValue(int(cfg.get("tiling_gap", 12)))
        self.tiling_gap.setEnabled(self.dock.is_primary_display)
        self.tiling_gap.blockSignals(False)
        self.tiling_padding.blockSignals(True)
        self.tiling_padding.setValue(int(cfg.get("tiling_padding", 16)))
        self.tiling_padding.setEnabled(self.dock.is_primary_display)
        self.tiling_padding.blockSignals(False)
        rules = cfg.get("tiling_floating_rules", {})
        self.floating_apps.setText("\n".join(
            rules.get("executables") or cfg.get("tiling_floating_apps", [])))
        self.floating_classes.setText("\n".join(rules.get("classes", [])))
        self.floating_titles.setPlainText(
            "\n".join(rules.get("title_regex", [])))
        unavailable = getattr(self.dock, "_tiling_hotkey_unavailable", [])
        messages = []
        release_status = getattr(self.dock, "_tiling_release_status", "")
        if release_status:
            messages.append(release_status)
        elif not cfg.get("tiling_enabled"):
            messages.append("Safe-release fallbacks: Ctrl+Alt+F12, Ctrl+Shift+F12.")
        if unavailable and cfg.get("tiling_enabled"):
            messages.append("Shortcut conflict/unavailable: "
                            + ", ".join(unavailable))
            errors = getattr(self.dock, "_tiling_hotkey_errors", {})
            if errors:
                messages[-1] += " (Win32 error(s): " + ", ".join(
                    f"{name}={code}" for name, code in errors.items()) + ")"
        manager = getattr(self.dock, "_tiling_manager", None)
        invalid_patterns = (manager.invalid_title_patterns if manager is not None
                            else getattr(self.dock,
                                         "_tiling_invalid_title_patterns", []))
        if invalid_patterns:
            messages.append("Invalid title regex ignored: "
                            + ", ".join(invalid_patterns))
        if cfg.get("tiling_enabled"):
            try:
                from native import vdesktop
                if not vdesktop.available():
                    messages.append(
                        "Virtual desktop COM is unavailable in this session; "
                        "window moves and separate per-desktop layouts may not work.")
            except Exception:
                messages.append("Virtual desktop controls are unavailable.")
        runtime_error = getattr(self.dock, "_tiling_runtime_error", "")
        if runtime_error:
            messages.append(runtime_error)
        self.tiling_status.setText("\n".join(messages) or
                                   ("Tiling is off." if not cfg.get(
                                       "tiling_enabled") else ""))
        modifier = cfg.get("app_hotkey_modifier", "alt").title()
        if self.app_modifier.findText(modifier) < 0:
            modifier = "Alt"
        self.app_modifier.blockSignals(True)
        self.app_modifier.setCurrentText(modifier)
        self.app_modifier.blockSignals(False)
        self._refresh_preview()

