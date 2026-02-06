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
    QBrush,
    QLinearGradient,
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
    QHBoxLayout,
    QSlider,
    QStyleOptionSlider,
    QStyle,
)
import numpy as np


class RangeSlider(QWidget):
    """
    A dual-handle range slider for min/max value selection.
    Mimics the Cellpose saturation slider style.
    """

    rangeChanged = Signal(float, float)  # Emits (min_val, max_val) as floats 0-1

    def __init__(
        self,
        color: Tuple[int, int, int] = (100, 100, 255),
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.color = color
        self._min_val = 0.0  # 0-1 range
        self._max_val = 1.0  # 0-1 range
        self._dragging = None  # 'min', 'max', or None
        self._handle_width = 8
        self._track_height = 6
        self.setMinimumHeight(20)
        self.setMinimumWidth(100)
        self.setCursor(Qt.PointingHandCursor)

    @property
    def min_val(self) -> float:
        return self._min_val

    @property
    def max_val(self) -> float:
        return self._max_val

    def set_range(self, min_val: float, max_val: float) -> None:
        """Set the range values (0-1 scale)."""
        self._min_val = max(0.0, min(1.0, min_val))
        self._max_val = max(0.0, min(1.0, max_val))
        if self._min_val > self._max_val:
            self._min_val, self._max_val = self._max_val, self._min_val
        self.update()

    def _val_to_x(self, val: float) -> int:
        """Convert value (0-1) to x coordinate."""
        usable_width = self.width() - 2 * self._handle_width
        return int(self._handle_width + val * usable_width)

    def _x_to_val(self, x: int) -> float:
        """Convert x coordinate to value (0-1)."""
        usable_width = self.width() - 2 * self._handle_width
        val = (x - self._handle_width) / usable_width
        return max(0.0, min(1.0, val))

    def set_color(self, color: Tuple[int, int, int]) -> None:
        """Update the slider color."""
        self.color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        h = self.height()
        track_y = (h - self._track_height) // 2

        # Draw background track (dark)
        painter.setBrush(QBrush(QColor(40, 40, 40)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(
            self._handle_width,
            track_y,
            self.width() - 2 * self._handle_width,
            self._track_height,
            self._track_height // 2,
            self._track_height // 2,
        )

        # Draw active range (colored)
        min_x = self._val_to_x(self._min_val)
        max_x = self._val_to_x(self._max_val)

        # Create gradient for the active range
        gradient = QLinearGradient(min_x, 0, max_x, 0)
        base_color = QColor(self.color[0], self.color[1], self.color[2])
        gradient.setColorAt(0, base_color.darker(120))
        gradient.setColorAt(1, base_color)

        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(
            min_x,
            track_y,
            max_x - min_x,
            self._track_height,
            self._track_height // 2,
            self._track_height // 2,
        )

        # Draw handles
        handle_h = h - 4
        handle_y = 2

        # Min handle
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRoundedRect(
            min_x - self._handle_width // 2,
            handle_y,
            self._handle_width,
            handle_h,
            2,
            2,
        )

        # Max handle
        painter.drawRoundedRect(
            max_x - self._handle_width // 2,
            handle_y,
            self._handle_width,
            handle_h,
            2,
            2,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            x = event.pos().x()
            min_x = self._val_to_x(self._min_val)
            max_x = self._val_to_x(self._max_val)

            # Check which handle is closer
            dist_min = abs(x - min_x)
            dist_max = abs(x - max_x)

            if dist_min <= dist_max and dist_min < self._handle_width * 2:
                self._dragging = "min"
            elif dist_max < self._handle_width * 2:
                self._dragging = "max"
            else:
                # Click in middle - move nearest handle
                if dist_min < dist_max:
                    self._dragging = "min"
                else:
                    self._dragging = "max"
                self._update_value(x)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._update_value(event.pos().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = None

    def _update_value(self, x: int) -> None:
        val = self._x_to_val(x)

        if self._dragging == "min":
            self._min_val = min(val, self._max_val - 0.01)
        elif self._dragging == "max":
            self._max_val = max(val, self._min_val + 0.01)

        self.update()
        self.rangeChanged.emit(self._min_val, self._max_val)


class AnimatedButton(QPushButton):
    def __init__(
        self,
        text: str,
        size: Tuple[int, int] = (30, 200),
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
    pen_w: float
    dot_size: float

    def __init__(
        self,
        points: Optional[List[QPointF]],
        color: Any = Qt.green,
        pen_w: float = 2,
        dot_size: float = 5,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self.points = deepcopy(points) if points else []
        self.color = color
        self.pen_w = pen_w
        self.dot_size = dot_size
        self.setZValue(1)

    def boundingRect(self) -> QRectF:
        if not self.points:
            return QRectF()
        xs = [p.x() for p in self.points]
        ys = [p.y() for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        margin = max(6, self.dot_size + 2)
        return QRectF(
            min_x - margin,
            min_y - margin,
            (max_x - min_x) + 2 * margin,
            (max_y - min_y) + 2 * margin,
        )

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
            painter.drawEllipse(pt, self.dot_size, self.dot_size)


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


class LoadLabelsDialog(QDialog):
    """Dialog for loading cell labels from CSV or SpatialData table."""

    def __init__(self, spatial_data_loader=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load Cell Labels")
        self.setMinimumWidth(400)

        self.spatial_data_loader = spatial_data_loader
        self.selected_source = None  # 'csv' or 'spatialdata'
        self.csv_path = None
        self.table_name = None
        self.column_name = None

        from PySide6.QtWidgets import (
            QRadioButton,
            QButtonGroup,
            QHBoxLayout,
            QFileDialog,
            QComboBox,
            QGroupBox,
        )

        layout = QVBoxLayout(self)

        # Source selection
        source_group = QGroupBox("Select Label Source")
        source_layout = QVBoxLayout(source_group)

        self.button_group = QButtonGroup()
        self.csv_radio = QRadioButton("Load from CSV file")
        self.spatialdata_radio = QRadioButton("Load from SpatialData table")
        self.delete_radio = QRadioButton("Delete labels")

        self.button_group.addButton(self.csv_radio)
        self.button_group.addButton(self.spatialdata_radio)
        self.button_group.addButton(self.delete_radio)

        source_layout.addWidget(self.csv_radio)
        source_layout.addWidget(self.spatialdata_radio)
        source_layout.addWidget(self.delete_radio)

        # CSV file selection
        csv_group = QGroupBox("CSV File")
        csv_layout = QHBoxLayout(csv_group)
        self.csv_path_label = QLabel("No file selected")
        self.csv_browse_btn = QPushButton("Browse...")
        self.csv_browse_btn.clicked.connect(self.browse_csv)
        csv_layout.addWidget(self.csv_path_label)
        csv_layout.addWidget(self.csv_browse_btn)

        # SpatialData table selection
        sd_group = QGroupBox("SpatialData Table")
        sd_layout = QVBoxLayout(sd_group)

        table_layout = QHBoxLayout()
        table_layout.addWidget(QLabel("Table:"))
        self.table_combo = QComboBox()
        self.table_combo.currentTextChanged.connect(self.on_table_changed)
        table_layout.addWidget(self.table_combo)

        column_layout = QHBoxLayout()
        column_layout.addWidget(QLabel("Column:"))
        self.column_combo = QComboBox()
        column_layout.addWidget(self.column_combo)

        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("ID Column:"))
        self.id_combo = QComboBox()
        id_layout.addWidget(self.id_combo)

        sd_layout.addLayout(table_layout)
        sd_layout.addLayout(id_layout)
        sd_layout.addLayout(column_layout)

        # Populate SpatialData options if available
        if self.spatial_data_loader:
            tables = self.spatial_data_loader.get_available_tables()
            self.table_combo.addItems(tables)
            if tables:
                self.on_table_changed(tables[0])
        else:
            self.spatialdata_radio.setEnabled(False)
            sd_group.setEnabled(False)

        # OK/Cancel buttons
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)

        # Add to main layout
        layout.addWidget(source_group)
        layout.addWidget(csv_group)
        layout.addWidget(sd_group)
        layout.addLayout(button_layout)

        # Connect radio buttons to enable/disable groups
        self.csv_radio.toggled.connect(lambda checked: csv_group.setEnabled(checked))
        self.spatialdata_radio.toggled.connect(
            lambda checked: sd_group.setEnabled(checked)
        )

        # Set default
        self.csv_radio.setChecked(True)
        sd_group.setEnabled(False)

    def browse_csv(self):
        """Open file dialog to select CSV file."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.csv_path = file_path
            self.csv_path_label.setText(file_path.split("/")[-1])

    def on_table_changed(self, table_name):
        """Update column combo when table selection changes."""
        if not self.spatial_data_loader or not table_name:
            return

        # Get categorical columns for this table (label candidates)
        columns = self.spatial_data_loader.get_categorical_columns(table_name)
        self.column_combo.clear()
        self.column_combo.addItems(columns)

        # Populate ID column candidates by scanning all obs columns for common id names
        self.id_combo.clear()
        try:
            table = self.spatial_data_loader.sdata.tables[table_name]
            obs_cols = list(table.obs.columns)
        except Exception:
            obs_cols = []

        # Candidate id columns: those containing 'cell_id' or 'id'
        id_candidates = [
            c
            for c in obs_cols
            if "cell_id" in c.lower() or c.lower() == "id" or c.lower().endswith("_id")
        ]
        # Ensure 'index' is an option (uses row index)
        id_options = id_candidates.copy()
        if "index" not in id_options:
            id_options.insert(0, "index")

        # If no candidates found, fall back to using 'index'
        if not id_candidates:
            id_options = ["index"] + obs_cols[:]

        self.id_combo.addItems(id_options)

        # Prefer a column that contains 'cell_id' as default if present
        default_choice = None
        for c in obs_cols:
            if "cell_id" in c.lower():
                default_choice = c
                break
        if default_choice:
            idx = self.id_combo.findText(default_choice)
            if idx >= 0:
                self.id_combo.setCurrentIndex(idx)

    def accept(self):
        """Validate and accept the dialog."""
        if self.csv_radio.isChecked():
            if not self.csv_path:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self, "No File Selected", "Please select a CSV file."
                )
                return
            self.selected_source = "csv"
        elif self.spatialdata_radio.isChecked():
            self.table_name = self.table_combo.currentText()
            self.column_name = self.column_combo.currentText()
            # ID column selection (may be 'index' meaning use row index)
            try:
                self.id_column = self.id_combo.currentText()
            except Exception:
                self.id_column = None
            if not self.table_name or not self.column_name:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self, "Incomplete Selection", "Please select both table and column."
                )
                return
            self.selected_source = "spatialdata"
        elif self.delete_radio.isChecked():
            self.selected_source = "delete"

        super().accept()
