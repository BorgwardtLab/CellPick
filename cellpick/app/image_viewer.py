import sys
from copy import deepcopy
from typing import Any, Callable, List, Optional

import numpy as np
import pandas as pd
import skimage
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from shapely.geometry import MultiPoint

from .components import CHANNEL_COLORS, AppState, ImageChannel, Polygon
from .ui_components import PolygonPreviewItem

ALPHA_BASE1 = 200
ALPHA_BASE2 = 100
ALPHA_ENABLED1 = 240
ALPHA_ENABLED2 = 160
ALPHA_DISABLED1 = 100
ALPHA_DISABLED2 = 50


class ZoomableGraphicsView(QGraphicsView):
    scene: QGraphicsScene
    pixmap_item: Optional[QGraphicsPixmapItem]
    zoom_factor: float
    max_zoom: float

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.pixmap_item: Optional[QGraphicsPixmapItem] = None
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.zoom_factor: float = 1.0
        self.max_zoom: float = 100.0
        self.setStyleSheet("background-color: white; border: none")

    def fit_in_view(self) -> None:
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self.zoom_factor = 1.0

    def set_image(self, qimage: QImage) -> None:
        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)
        pixmap = QPixmap.fromImage(qimage)
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fit_in_view()

    def wheelEvent(self, event) -> None:
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            if self.zoom_factor * zoom_in_factor <= self.max_zoom:
                self.zoom_factor *= zoom_in_factor
                self.scale(zoom_in_factor, zoom_in_factor)
        else:
            if self.zoom_factor * zoom_out_factor >= 1.0:
                self.zoom_factor *= zoom_out_factor
                self.scale(zoom_out_factor, zoom_out_factor)


class ImageViewer(QWidget):
    state: Any
    channels: List[ImageChannel]
    composite_image: Optional[np.ndarray]
    brightness: float
    height: Optional[int]
    width: Optional[int]
    shape_items: List[QGraphicsPolygonItem]
    landmark_items: List[QGraphicsPolygonItem]
    lnd_preview_item: Optional[QGraphicsItem]
    ar_items: List[QGraphicsPolygonItem]
    ar_preview_item: Optional[QGraphicsItem]
    calibration_items: List[QGraphicsPolygonItem]
    graphics_view: ZoomableGraphicsView

    def __init__(self, state: Any) -> None:
        super().__init__()
        self.state = state
        self.state.image_viewer = self
        self.channels: List[ImageChannel] = []
        self.composite_image: Optional[np.ndarray] = None
        self.gamma: float = 1.0
        self.contrast: float = 1.0
        self.height: Optional[int] = None
        self.width: Optional[int] = None
        self.shape_items: List[QGraphicsPolygonItem] = []
        self.landmark_items: List[QGraphicsPolygonItem] = []
        self.lnd_preview_item: Optional[QGraphicsItem] = None
        self.ar_items: List[QGraphicsPolygonItem] = []
        self.ar_preview_item: Optional[QGraphicsItem] = None
        self.calibration_items = []
        layout = QVBoxLayout(self)
        self.graphics_view = ZoomableGraphicsView()
        layout.addWidget(self.graphics_view)
        self.setMouseTracking(True)

    def get_pen_scale(self) -> float:
        """Get the pen width scale factor based on spatialdata resolution level."""
        main_window = self.parent()
        while main_window and not hasattr(main_window, "_spatialdata_scale_factor"):
            main_window = main_window.parent()

        if main_window and hasattr(main_window, "_spatialdata_scale_factor"):
            scale_factor = main_window._spatialdata_scale_factor
            # Using a gentler exponent (0.3) to keep outlines visible at high downsampling
            return max(0.25, min(1.0, 1.0 / (scale_factor**0.3)))
        return 1.0

    def add_channel(
        self,
        image_data: np.ndarray,
        name: str = "",
        custom_color: Optional[np.ndarray] = None,
    ) -> int:
        if len(image_data.shape) not in (2, 3):
            return 1
        if len(image_data.shape) == 3:
            image_data = image_data[0] if image_data.shape[0] == 1 else image_data
        color_idx = len(self.channels) % len(CHANNEL_COLORS)
        if not self.channels:
            self.height, self.width = image_data.shape[0], image_data.shape[1]
        elif self.height != image_data.shape[0] or self.width != image_data.shape[1]:
            return 2
        self.channels.append(
            ImageChannel(image_data, name, True, color_idx, custom_color)
        )
        self.update_display()
        return 0

    def update_display(self) -> None:
        composite = np.zeros((self.height, self.width, 3), dtype=np.float32)
        for channel in self.channels:
            if channel.visible:
                channel_data = channel.image_data.astype(np.float32)
                channel_data /= np.max(channel_data) if np.max(channel_data) > 0 else 1
                if abs(self.gamma - 1.0) > 1e-9:
                    channel_data = skimage.exposure.adjust_gamma(
                        channel_data, 1.0 / self.gamma
                    )
                # Apply contrast adjustment: out = (in - 0.5) * contrast + 0.5
                channel_data = np.clip((channel_data - 0.5) * self.contrast + 0.5, 0, 1)
                # Use custom color if available, otherwise use default color
                if channel.custom_color is not None:
                    color = channel.custom_color
                else:
                    color = CHANNEL_COLORS[channel.color_idx % len(CHANNEL_COLORS)]
                composite += channel_data[..., None] * color[None, None, :]
        composite = np.clip(composite, 0, 255).astype(np.uint8)
        self.composite_image = composite  # Store for shape color contrast
        h, w, _ = composite.shape
        bytes_per_line = 3 * w
        qimage = QImage(composite.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.graphics_view.set_image(qimage)
        self.update_polygon_display()

    def update_polygon_display(self) -> None:
        for item in self.shape_items:
            self.graphics_view.scene.removeItem(item)
        self.shape_items = []

        # Use the selected shape outline color from the MainWindow
        main_window = self.parent()
        while main_window and not hasattr(main_window, "shape_outline_color"):
            main_window = main_window.parent()
        if main_window and hasattr(main_window, "shape_outline_color"):
            shape_outline_color = main_window.shape_outline_color
        else:
            shape_outline_color = QColor(0, 255, 0)

        # Get scale factor for pen width adjustment
        # At high downsampling levels, shapes are smaller so pen should be thinner
        scale_factor = 1
        if main_window and hasattr(main_window, "_spatialdata_scale_factor"):
            scale_factor = main_window._spatialdata_scale_factor

        # Calculate pen width scale (inverse of scale factor, with min/max bounds)
        # Using a gentler exponent (0.3) to keep outlines visible at high downsampling
        pen_scale = max(0.25, min(1.0, 1.0 / (scale_factor**0.3)))

        has_selected_shapes = len(self.state.selected_shape_ids) > 0

        # Check if labels are loaded
        labels_available = (
            self.state.cell_labels is not None and self.state.label_colors is not None
        )

        # Check if user prefers gradient over labels
        prefer_gradient = False
        if main_window and hasattr(main_window, "_prefer_gradient_over_labels"):
            prefer_gradient = main_window._prefer_gradient_over_labels

        # Use labels only if available AND not preferring gradient
        use_label_colors = labels_available and not prefer_gradient

        for idx, polygon in enumerate(self.state.shapes):
            # Priority: 1) Label colors (if enabled), 2) Score colors, 3) User-selected color
            if use_label_colors and idx in self.state.cell_labels:
                # Color by label using Tab10/Tab20 palette
                label = self.state.cell_labels[idx]
                if label in self.state.label_colors:
                    rgb = self.state.label_colors[label]
                    color = QColor(rgb[0], rgb[1], rgb[2])
                    fill_color = QColor(rgb[0], rgb[1], rgb[2], 128)  # Alpha 0.5
                else:
                    # Fallback if label not in color map
                    color = QColor(shape_outline_color)
                    fill_color = QColor(
                        shape_outline_color.red(),
                        shape_outline_color.green(),
                        shape_outline_color.blue(),
                        128,
                    )
            elif polygon.score is not None:
                # Use gradient color if shape has a score
                color = QColor(polygon.color)
                fill_color = QColor(
                    polygon.color.red(),
                    polygon.color.green(),
                    polygon.color.blue(),
                    128,
                )  # Alpha 0.5
            else:
                # Use user-selected color
                color = QColor(shape_outline_color)
                fill_color = QColor(
                    shape_outline_color.red(),
                    shape_outline_color.green(),
                    shape_outline_color.blue(),
                    128,
                )  # Alpha 0.5

            is_selected = idx in self.state.selected_shape_ids

            if is_selected:
                color.setAlpha(ALPHA_ENABLED1)
                color.setRed(min(255, color.red() + 50))
                color.setGreen(min(255, color.green() + 50))
                color.setBlue(min(255, color.blue() + 50))
                # Update fill color for selected
                fill_color.setAlpha(ALPHA_ENABLED2)
                fill_color.setRed(min(255, fill_color.red() + 50))
                fill_color.setGreen(min(255, fill_color.green() + 50))
                fill_color.setBlue(min(255, fill_color.blue() + 50))
                base_pen_width = 4
            else:
                if has_selected_shapes:
                    color.setAlpha(ALPHA_DISABLED1)
                    color.setRed(max(0, int(color.red() * 0.7)))
                    color.setGreen(max(0, int(color.green() * 0.7)))
                    color.setBlue(max(0, int(color.blue() * 0.7)))
                    # Update fill color for dimmed
                    fill_color.setAlpha(ALPHA_DISABLED2)
                    fill_color.setRed(max(0, int(fill_color.red() * 0.7)))
                    fill_color.setGreen(max(0, int(fill_color.green() * 0.7)))
                    fill_color.setBlue(max(0, int(fill_color.blue() * 0.7)))
                    base_pen_width = 1
                else:
                    color.setAlpha(ALPHA_BASE1)
                    color.setRed(min(255, color.red() + 50))
                    color.setGreen(min(255, color.green() + 50))
                    color.setBlue(min(255, color.blue() + 50))
                    # Update fill color for selected
                    fill_color.setAlpha(ALPHA_BASE2)
                    fill_color.setRed(min(255, fill_color.red() + 50))
                    fill_color.setGreen(min(255, fill_color.green() + 50))
                    fill_color.setBlue(min(255, fill_color.blue() + 50))

                    base_pen_width = 2

            # Scale pen width based on resolution level
            pen_width = max(0.5, base_pen_width * pen_scale)

            # Use cached QPolygonF for efficient rendering
            poly_item = QGraphicsPolygonItem(polygon.get_qpolygon())
            poly_item.setPen(QPen(color, pen_width))
            poly_item.setBrush(fill_color)
            poly_item.setZValue(3)
            self.graphics_view.scene.addItem(poly_item)
            self.shape_items.append(poly_item)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.RightButton:
            view_pos = self.graphics_view.mapFrom(self, event.pos())
            scene_pos = self.graphics_view.mapToScene(view_pos)

            if self.state.state == AppState.SELECTING_LND:
                self.state.add_lnd_point(scene_pos)
            if self.state.state == AppState.DELETING_LND:
                self.state.try_deleting_landmark(scene_pos)
            if self.state.state == AppState.SELECTING_AR:
                self.state.add_ar_point(scene_pos)
            if self.state.state == AppState.DELETING_AR:
                self.state.try_deleting_ar(scene_pos)
            if self.state.state == AppState.ADDING_SHP:
                self.state.try_adding_shp(scene_pos)
            if self.state.state == AppState.DELETING_SHP:
                self.state.try_deleting_shp(scene_pos)
            if self.state.state == AppState.SELECTING_CLB:
                self.state.add_calibration_point(scene_pos)

    def update_lnd_preview(self, points: List[QPointF]) -> None:
        if self.lnd_preview_item:
            self.graphics_view.scene.removeItem(self.lnd_preview_item)

        pen_scale = self.get_pen_scale()
        scaled_pen_w = max(0.5, 2 * pen_scale)
        scaled_dot_size = max(1.5, 5 * pen_scale)
        self.lnd_preview_item = PolygonPreviewItem(
            points, color=Qt.white, pen_w=scaled_pen_w, dot_size=scaled_dot_size
        )
        self.graphics_view.scene.addItem(self.lnd_preview_item)

        self.update()

    def add_persistent_lnd(self, points: List[QPointF]) -> None:
        # Add persistent polygon to scene
        pen_scale = self.get_pen_scale()
        scaled_pen_w = max(0.5, 2 * pen_scale)
        poly_item = QGraphicsPolygonItem(QPolygonF(points))
        if len(self.landmark_items) == 0:
            poly_item.setPen(QPen(Qt.red, scaled_pen_w))
            poly_item.setBrush(QColor(255, 20, 20, 60))
        else:
            poly_item.setPen(QPen(Qt.green, scaled_pen_w))
            poly_item.setBrush(QColor(20, 255, 20, 60))
        poly_item.setZValue(
            4
        )  # Higher than shapes (z=3) so landmarks are visible on top
        self.graphics_view.scene.addItem(poly_item)
        self.landmark_items.append(poly_item)
        self.update()

    def delete_persistent_lnd(self, idx: int) -> None:
        poly_item = self.landmark_items.pop(idx)
        self.graphics_view.scene.removeItem(poly_item)

        if idx == 0 and len(self.landmark_items) > 0:  # we re-index the lankmarks
            # delete also the other landmark
            poly_item = self.landmark_items.pop(0)
            self.graphics_view.scene.removeItem(poly_item)
            pen_scale = self.get_pen_scale()
            scaled_pen_w = max(0.5, 2 * pen_scale)
            poly_item.setPen(QPen(Qt.red, scaled_pen_w))
            poly_item.setBrush(QColor(255, 20, 20, 60))
            poly_item.setZValue(2)
            # and add it back, but in red
            self.graphics_view.scene.addItem(poly_item)
            self.landmark_items.append(poly_item)

        self.update()

    # Active regions
    def update_ar_preview(self, points: List[QPointF]) -> None:
        if self.ar_preview_item:
            self.graphics_view.scene.removeItem(self.ar_preview_item)

        pen_scale = self.get_pen_scale()
        scaled_pen_w = max(0.5, 2 * pen_scale)
        scaled_dot_size = max(1.5, 5 * pen_scale)
        self.ar_preview_item = PolygonPreviewItem(
            points, color=Qt.yellow, pen_w=scaled_pen_w, dot_size=scaled_dot_size
        )
        self.graphics_view.scene.addItem(self.ar_preview_item)

        self.update()

    def add_persistent_ar(self, points: List[QPointF]) -> None:
        # Add persistent polygon to scene
        pen_scale = self.get_pen_scale()
        scaled_pen_w = max(0.75, 3 * pen_scale)
        poly_item = QGraphicsPolygonItem(QPolygonF(points))
        poly_item.setPen(QPen(Qt.yellow, scaled_pen_w))
        poly_item.setBrush(QColor(255, 255, 0, 20))
        poly_item.setZValue(1)
        self.graphics_view.scene.addItem(poly_item)
        self.ar_items.append(poly_item)
        self.update()

    def delete_persistent_ar(self, idx: int) -> None:
        item = self.ar_items.pop(idx)
        self.graphics_view.scene.removeItem(item)
        self.update()

    # Calibration
    def add_calibration_item(self, point: QPointF, idx: int):
        x, y = point.x(), point.y()
        poly = [
            QPointF(x - 2, y - 100),
            QPointF(x + 2, y - 100),
            QPointF(x + 2, y - 2),
            QPointF(x + 100, y - 2),
            QPointF(x + 100, y + 2),
            QPointF(x + 2, y + 2),
            QPointF(x + 2, y + 100),
            QPointF(x - 2, y + 100),
            QPointF(x - 2, y + 2),
            QPointF(x - 100, y + 2),
            QPointF(x - 100, y - 2),
            QPointF(x - 2, y - 2),
        ]
        poly_item = QGraphicsPolygonItem(QPolygonF(poly))
        poly_item.setPen(QPen(Qt.white, 2))
        if idx == 0:
            poly_item.setBrush(QColor(255, 0, 0, 255))
        if idx == 1:
            poly_item.setBrush(QColor(0, 255, 0, 255))
        if idx == 2:
            poly_item.setBrush(QColor(0, 0, 255, 255))
        poly_item.setZValue(1)
        self.graphics_view.scene.addItem(poly_item)
        self.calibration_items.append(poly_item)
        self.update()

    def remove_calibration_items(self):
        for item in self.calibration_items:
            self.graphics_view.scene.removeItem(item)
        self.calibration_items = []
        self.update()
