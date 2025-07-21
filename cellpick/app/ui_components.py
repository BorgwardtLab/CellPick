from copy import deepcopy
from typing import Any, List, Optional, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsWidget,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AnimatedButton(QPushButton):
    def __init__(
        self,
        text: str,
        size: Tuple[int, int] = (32, 200),
        color1: str = "50,50,50",
        color2: str = "0,0,0",
    ) -> None:
        super().__init__(text)
        self.style = """
            QPushButton:!pressed {{
                text-align: center;
                font-family: "Roboto";
                height: {h1};
                border-radius: {r1};
                background-color: rgb({color1});
                color: white;
                border: none;
            }}
            QPushButton:pressed {{
                text-align: center;
                font-family: "Roboto";
                height: {h1};
                border-radius: {r1};
                background-color: rgb({color2});
                color: white;
                border: none;
                border: 2px solid rgba(255,255,255,0)
            }}
            QPushButton:disabled {{
                background-color: rgba({color1},80);
                color: rgba(255,255,255,150);
            }}
            """

        # Try setting the height and width
        h = size[0]
        self.setStyleSheet(
            self.style.format(h1=h, r1=h // 2, color1=color1, color2=color2)
        )
        self.setMinimumWidth(size[1])


class PolygonPreviewItem(QGraphicsItem):
    points: List[QPointF]
    color: Any
    pen_w: int

    def __init__(
        self,
        points: Optional[List[QPointF]],
        color: Any = Qt.green,
        pen_w: int = 2,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self.points = deepcopy(points) if points else []
        self.color = color
        self.pen_w = pen_w
        self.setZValue(1)

    def boundingRect(self) -> QRectF:
        if not self.points:
            return QRectF()
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return QRectF(min_x - 6, min_y - 6, (max_x - min_x) + 12, (max_y - min_y) + 12)

    def paint(self, painter: QPainter, option: Any, widget: Optional[QWidget]) -> None:
        if not self.points:
            return
        pen = QPen(self.color, self.pen_w)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing)
        if len(self.points) > 2:
            painter.drawPolygon(QPolygonF(self.points))
        elif len(self.points) > 1:
            painter.drawPolyline(QPolygonF(self.points))
        painter.setBrush(self.color)
        for pt in self.points:
            painter.drawEllipse(pt, 5, 5)


class ProgressDialog(QDialog):
    def __init__(self, title="Loading...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.label = QLabel("Loading shapes...", self)
        self.progress = QProgressBar(self)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        layout.addWidget(self.label)
        layout.addWidget(self.progress)
        self.setLayout(layout)

    def update_progress(self, value, text=None):
        self.progress.setValue(value)
        if text is not None:
            self.label.setText(text)


class ClickableLabel(QLabel):
    """A clickable label widget for channel names."""

    clicked = Signal()

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("color: #404040; text-decoration: underline;")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ClickableColorLabel(QLabel):
    """A clickable color label widget for channel colors."""

    clicked = Signal()

    def __init__(self, color, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.color = color
        self.update_style()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(20, 20)

    def update_style(self) -> None:
        """Update the style sheet with the current color, rounded corners, and thick black border."""
        self.setStyleSheet(
            f"background-color: rgb({self.color[0]}, {self.color[1]}, {self.color[2]}); "
            f"border: 2px solid black; "
            f"border-radius: 4px;"
        )

    def set_color(self, color) -> None:
        """Set the color and update the display."""
        self.color = color
        self.update_style()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
