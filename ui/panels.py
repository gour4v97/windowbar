"""Dock-aware detail panels for calendar, todos, and notes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCalendarWidget, QHBoxLayout, QListWidget,
                               QListWidgetItem, QLineEdit, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QLabel)
from ui.popup import DetailPopup
from widgets.base import clip
class Popup(DetailPopup):
    def __init__(self, dock):
        self.dock = dock
        super().__init__(dock, edge=dock.cfg.get("position", "bottom"))

    def show_near(self, widget):
        return super().show_near(
            widget, edge=self.dock.cfg.get("position", "bottom"))


class WidgetDetailPopup(Popup):

    def __init__(self, dock, title, details, actions=()):
        super().__init__(dock)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("cardtitle")
        layout.addWidget(heading)
        for detail in details:
            label = QLabel(str(detail))
            label.setWordWrap(True)
            label.setObjectName("cardbody")
            layout.addWidget(label)
        for label, callback in actions:
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, fn=callback: fn())
            layout.addWidget(button)
        self.setMinimumWidth(220)
        self.setMaximumWidth(340)


class CalendarPopup(Popup):
    def __init__(self, dock, calendar, ask_link):
        super().__init__(dock)
        self.calendar = calendar
        lay = QVBoxLayout(self)
        self.cal = QCalendarWidget()
        self.cal.setGridVisible(True)
        lay.addWidget(self.cal)
        self.list = QListWidget()
        self.list.setMaximumHeight(110)
        lay.addWidget(self.list)
        link = QPushButton("Set calendar link…")
        link.clicked.connect(lambda: (self.close(), ask_link()))
        lay.addWidget(link)
        self.cal.currentPageChanged.connect(lambda *_: self._mark())
        self.cal.selectionChanged.connect(self._fill)
        self._mark()
        self._fill()

    def _mark(self):
        from PySide6.QtCore import QDate
        from PySide6.QtGui import QTextCharFormat
        fmt = QTextCharFormat()
        fmt.setFontWeight(700)
        year, month = self.cal.yearShown(), self.cal.monthShown()
        for day in self.calendar.events_in_month(year, month):
            self.cal.setDateTextFormat(QDate(year, month, day), fmt)
        self._fill()

    def _fill(self):
        self.list.clear()
        d = self.cal.selectedDate()
        events = self.calendar.events_in_month(d.year(), d.month()).get(
            d.day(), [])
        if not events:
            self.list.addItem("No events")
        for when, title in events:
            self.list.addItem(f"{when.strftime('%H:%M')}  {title}")


class TodosPanel(Popup):

    def __init__(self, dock, cfg, save):
        super().__init__(dock)
        self.cfg, self.save = cfg, save
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.itemChanged.connect(self._toggled)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("New todo… (Enter adds)")
        self.edit.returnPressed.connect(self._add)
        row.addWidget(self.edit)
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete)
        row.addWidget(del_btn)
        lay.addLayout(row)
        self.setFixedWidth(300)
        self._fill()

    def _fill(self):
        self.list.blockSignals(True)
        self.list.clear()
        todos = self.cfg["todos"]
        ordered = [t for t in todos if not t["done"]] \
            + [t for t in todos if t["done"]]
        for t in ordered:
            item = QListWidgetItem(t["t"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if t["done"] else Qt.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)

    def _sync_from_list(self):
        todos = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            todos.append({"t": item.text(),
                          "done": item.checkState() == Qt.Checked})
        self.cfg["todos"] = todos
        self.save()

    def _toggled(self, _item):
        self._sync_from_list()
        self._fill()

    def _add(self):
        text = self.edit.text().strip()
        if text:
            self.cfg["todos"].append({"t": text, "done": False})
            self.save()
            self.edit.clear()
            self._fill()

    def _delete(self):
        item = self.list.currentItem()
        if item:
            done = item.checkState() == Qt.Checked
            for i, t in enumerate(self.cfg["todos"]):
                if t["t"] == item.text() and t["done"] == done:
                    del self.cfg["todos"][i]
                    break
            self.save()
            self._fill()


class NotesPanel(Popup):

    def __init__(self, dock, cfg, save):
        super().__init__(dock)
        self.cfg, self.save = cfg, save
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setMaximumHeight(90)
        self.list.currentRowChanged.connect(self._select)
        lay.addWidget(self.list)
        self.edit = QPlainTextEdit()
        self.edit.textChanged.connect(self._edited)
        lay.addWidget(self.edit)
        row = QHBoxLayout()
        new_btn = QPushButton("New note")
        new_btn.clicked.connect(self._new)
        row.addWidget(new_btn)
        del_btn = QPushButton("Delete note")
        del_btn.clicked.connect(self._delete)
        row.addWidget(del_btn)
        lay.addLayout(row)
        self.setFixedWidth(320)
        self._fill()
        self.list.setCurrentRow(self.cfg["notes_current"])

    def _fill(self):
        self.list.blockSignals(True)
        self.list.clear()
        for note in self.cfg["notes_list"]:
            first = (note.strip().splitlines() or ["(empty)"])[0]
            self.list.addItem(clip(first, 34))
        self.list.blockSignals(False)

    def _select(self, row):
        if row < 0:
            return
        self.cfg["notes_current"] = row
        self.edit.blockSignals(True)
        self.edit.setPlainText(self.cfg["notes_list"][row])
        self.edit.blockSignals(False)
        self.save()

    def _edited(self):
        row = self.cfg["notes_current"]
        text = self.edit.toPlainText()
        self.cfg["notes_list"][row] = text
        self.cfg["notes"] = text
        self.save()
        item = self.list.item(row)
        if item:
            first = (text.strip().splitlines() or ["(empty)"])[0]
            if item.text() != clip(first, 34):
                item.setText(clip(first, 34))

    def _new(self):
        self.cfg["notes_list"].append("")
        self.cfg["notes_current"] = len(self.cfg["notes_list"]) - 1
        self.save()
        self._fill()
        self.list.setCurrentRow(self.cfg["notes_current"])
        self.edit.setFocus()

    def _delete(self):
        if len(self.cfg["notes_list"]) <= 1:
            self.cfg["notes_list"] = [""]
        else:
            del self.cfg["notes_list"][self.cfg["notes_current"]]
        self.cfg["notes_current"] = 0
        self.save()
        self._fill()
        self.list.setCurrentRow(0)

