
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget
import theme


def paint_shell_panel(widget, tokens, glass_active=False):
    """Paint a rounded translucent shell surface from theme tokens."""
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(widget.rect()).adjusted(1, 1, -1, -1)
    path = QPainterPath()
    path.addRoundedRect(rect, tokens["panel_radius"], tokens["panel_radius"])
    fill = tokens["glass"] if glass_active else tokens["panel"]
    painter.fillPath(path, QColor(*theme.to_rgba(fill)))
    painter.setPen(QColor(*theme.to_rgba(tokens["border"])))
    painter.drawPath(path)


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
        self.setObjectName("detailPopup")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint
                            | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if parent is not None:
            tokens = getattr(parent, "tokens", theme.resolve("midnight"))
            self.setStyleSheet(
                parent.styleSheet()
                + f"""
QWidget#detailPopup {{ background: {theme.qss(tokens['panel'], 255)};
    border: 1px solid {theme.qss(tokens['border'])};
    border-radius: {tokens['panel_radius']}px; }}
""")

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

