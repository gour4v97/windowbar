"""Workspace viewer for Windows virtual desktops."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

import winapi
from core.app_config import save_config
from native import vdesktop


class WorkspaceViewer(QDialog):

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.shell = dock.shared_shell or dock
        self.cfg = self.shell.cfg
        self.target_hwnd = dock.last_external_hwnd
        self.setWindowFlag(Qt.Window, True)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setStyleSheet(dock.styleSheet())
        self.setWindowTitle("Workspaces")
        self.resize(760, 600)
        root = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.cards_host)
        root.addWidget(scroll)
        actions = QHBoxLayout()
        self.create_button = QPushButton("New workspace")
        self.create_button.clicked.connect(self._create)
        task_view = QPushButton("Windows Task View")
        task_view.clicked.connect(
            lambda: winapi.virtual_desktop_action("overview"))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        actions.addWidget(self.create_button)
        actions.addStretch(1)
        actions.addWidget(task_view)
        actions.addWidget(close)
        root.addLayout(actions)
        screen = dock.target_screen
        if screen is not None:
            area = screen.availableGeometry()
            self.resize(min(760, max(480, area.width() - 32)),
                        min(600, max(360, area.height() - 48)))
            self.move(area.x() + (area.width() - self.width()) // 2,
                      area.y() + (area.height() - self.height()) // 2)
        self.reload()

    def _metadata(self, desktop):
        key = str(desktop.id)
        return self.cfg.setdefault("workspace_metadata", {}).setdefault(
            key, {"icon": "▦"})

    @staticmethod
    def _desktop_name(desktop, metadata):
        custom = metadata.get("name", "").strip()
        if custom:
            return custom
        try:
            return desktop.name.strip() or f"Desktop {desktop.number}"
        except Exception:
            try:
                return f"Desktop {desktop.number}"
            except Exception:
                return "Desktop"

    def _clear_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def reload(self):
        self._clear_cards()
        desktops = vdesktop.desktops()
        current = vdesktop.current()
        if not desktops:
            self.status.setText(
                "Windows virtual desktop control is unavailable in this "
                "session. Check the pyvda installation and run Windows Bar "
                "in an interactive Windows session; keyboard shortcuts and "
                "Task View remain available.")
            self.create_button.setEnabled(True)
            return
        self.create_button.setEnabled(True)
        current_id = str(current.id) if current is not None else ""
        self.status.setText(
            f"{len(desktops)} desktops · select one to switch, rename it, "
            "or move the previously active window.")
        metadata_store = self.cfg.setdefault("workspace_metadata", {})
        valid_ids = {str(item.id) for item in desktops}
        for key in list(metadata_store):
            if key not in valid_ids:
                metadata_store.pop(key, None)
        save_config(self.cfg)
        for desktop in desktops:
            meta = self._metadata(desktop)
            card = QFrame()
            card.setObjectName("card")
            layout = QVBoxLayout(card)
            head = QHBoxLayout()
            name = self._desktop_name(desktop, meta)
            icon = QLabel(meta.get("icon", "▦"))
            icon.setStyleSheet("font-size: 22px;")
            title = QLabel(name)
            title.setObjectName("cardtitle")
            head.addWidget(icon)
            head.addWidget(title, 1)
            if str(desktop.id) == current_id:
                head.addWidget(QLabel("Current"))
            switch = QPushButton("Switch")
            switch.clicked.connect(
                lambda _=False, item=desktop: self._switch(item))
            head.addWidget(switch)
            layout.addLayout(head)
            windows = self._window_titles(desktop)
            summary = QLabel(", ".join(windows) if windows else "No open windows")
            summary.setObjectName("cardbody")
            layout.addWidget(summary)

            buttons = QHBoxLayout()
            rename = QPushButton("Rename")
            rename.clicked.connect(
                lambda _=False, item=desktop: self._rename(item))
            edit_icon = QPushButton("Set icon")
            edit_icon.clicked.connect(
                lambda _=False, item=desktop: self._set_icon(item))
            move = QPushButton("Move window here")
            move.setToolTip("Move the last active app window to this workspace")
            move.setEnabled(bool(self.target_hwnd)
                            and str(desktop.id) != current_id)
            move.clicked.connect(
                lambda _=False, item=desktop: self._move_window(item))
            wallpaper = QPushButton("Wallpaper…")
            wallpaper.clicked.connect(
                lambda _=False, item=desktop: self._set_wallpaper(item))
            remove = QPushButton("Remove")
            remove.setEnabled(len(desktops) > 1)
            remove.clicked.connect(
                lambda _=False, item=desktop: self._remove(item))
            for button in (rename, edit_icon, move, wallpaper, remove):
                buttons.addWidget(button)
            layout.addLayout(buttons)
            self.cards_layout.addWidget(card)

    @staticmethod
    def _window_titles(desktop):
        try:
            views = desktop.apps_by_z_order()
            titles = [winapi.window_title(view.hwnd) for view in views]
            return [title for title in titles if title][:4]
        except Exception:
            return []

    def _switch(self, desktop):
        if vdesktop.switch(desktop):
            self.close()
        else:
            QMessageBox.warning(
                self, "Workspace switch failed",
                "Windows could not switch to that desktop. Try the toolbar's "
                "previous/next shortcuts or Windows Task View.")

    def _create(self):
        desktop = vdesktop.create()
        if desktop is not None:
            self.reload()
        else:
            QTimer.singleShot(500, self.reload)

    def _rename(self, desktop):
        meta = self._metadata(desktop)
        current = self._desktop_name(desktop, meta)
        name, ok = QInputDialog.getText(self, "Rename workspace", "Name:",
                                        text=current)
        if ok and name.strip():
            meta["name"] = name.strip()[:64]
            vdesktop.rename(desktop, meta["name"])
            save_config(self.cfg)
            self.reload()

    def _set_icon(self, desktop):
        meta = self._metadata(desktop)
        icon, ok = QInputDialog.getText(
            self, "Workspace icon", "Enter one emoji or short symbol:",
            text=meta.get("icon", "▦"))
        if ok and icon.strip():
            meta["icon"] = icon.strip()[:4]
            save_config(self.cfg)
            self.reload()

    def _move_window(self, desktop):
        if not self.target_hwnd:
            return
        if vdesktop.move_window(self.target_hwnd, desktop):
            self.status.setText("Window moved to the selected workspace.")
            self.reload()
        else:
            QMessageBox.warning(
                self, "Could not move window",
                "Windows did not allow this window to move. Some system and "
                "tool windows cannot be assigned to a virtual desktop.")

    def _set_wallpaper(self, desktop):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose workspace wallpaper", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        if vdesktop.set_wallpaper(desktop, path):
            meta = self._metadata(desktop)
            meta["wallpaper"] = path
            save_config(self.cfg)
            self.status.setText("Wallpaper applied to this workspace.")
        else:
            QMessageBox.information(
                self, "Wallpaper unavailable",
                "Per-workspace wallpaper needs a supported Windows build. "
                "This build did not accept the request.")

    def _remove(self, desktop):
        meta = self._metadata(desktop)
        name = self._desktop_name(desktop, meta)
        answer = QMessageBox.question(
            self, "Remove workspace?",
            f"Remove {name}? Windows will move its windows to another desktop.")
        if answer != QMessageBox.Yes:
            return
        if vdesktop.remove(desktop):
            save_config(self.cfg)
            self.reload()
        else:
            QMessageBox.warning(
                self, "Could not remove workspace",
                "Windows could not remove this desktop. Open Task View and "
                "try again.")

