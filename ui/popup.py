
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def popup_position(anchor, popup_size, screen, edge="bottom", gap=6):
    x = anchor.center().x() - popup_size.width() // 2
    if edge == "top":
        y = anchor.bottom() + 1 + gap
    else:
        y = anchor.top() - popup_size.height() - gap

    max_x = max(screen.left(), screen.right() - popup_size.width() + 1)
    max_y = max(screen.top(), screen.bottom() - popup_size.height() + 1)
    return QPoint(
        min(max(x, screen.left()), max_x),
        min(max(y, screen.top()), max_y),
    )


class DetailPopup(QWidget):

    def __init__(self, parent=None, edge="bottom"):
        super().__init__(parent)
        self.edge = edge
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())

    def show_near(self, anchor, edge=None):
        self.adjustSize()
        global_anchor = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(global_anchor, anchor.size())
        center = anchor.mapToGlobal(QPoint(anchor.width() // 2,
                                           anchor.height() // 2))
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is not None:
            pos = popup_position(anchor_rect, self.size(),
                                 screen.availableGeometry(),
                                 edge or self.edge)
            self.move(pos)
        self.show()
        self.raise_()
        return self

