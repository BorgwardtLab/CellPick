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
        layout = QVBoxLayout(self)
        self.graphics_view = ZoomableGraphicsView()
        layout.addWidget(self.graphics_view)
        self.setMouseTracking(True)

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

        has_selected_shapes = len(self.state.selected_shape_ids) > 0

        for idx, polygon in enumerate(self.state.shapes):
            # Use gradient color if shape has a score, otherwise use user-selected color
            if polygon.score is not None:
                color = QColor(polygon.color)
            else:
                color = QColor(shape_outline_color)
            is_selected = idx in self.state.selected_shape_ids

            if is_selected:
                color.setAlpha(200)
                color.setRed(min(255, color.red() + 50))
                color.setGreen(min(255, color.green() + 50))
                color.setBlue(min(255, color.blue() + 50))
                pen_width = 4
            else:
                if has_selected_shapes:
                    color.setAlpha(140)
                    color.setRed(max(0, int(color.red() * 0.7)))
                    color.setGreen(max(0, int(color.green() * 0.7)))
                    color.setBlue(max(0, int(color.blue() * 0.7)))
                    pen_width = 1
                else:
                    color.setAlpha(200)
                    color.setRed(min(255, color.red() + 50))
                    color.setGreen(min(255, color.green() + 50))
                    color.setBlue(min(255, color.blue() + 50))
                    pen_width = 2

            poly_item = QGraphicsPolygonItem(QPolygonF(polygon.points))
            poly_item.setPen(QPen(color, pen_width))
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

    def update_lnd_preview(self, points: List[QPointF]) -> None:
        if self.lnd_preview_item:
            self.graphics_view.scene.removeItem(self.lnd_preview_item)

        self.lnd_preview_item = PolygonPreviewItem(points, color=Qt.white, pen_w=2)
        self.graphics_view.scene.addItem(self.lnd_preview_item)

        self.update()

    def add_persistent_lnd(self, points: List[QPointF]) -> None:
        # Add persistent polygon to scene
        poly_item = QGraphicsPolygonItem(QPolygonF(points))
        if len(self.landmark_items) == 0:
            poly_item.setPen(QPen(Qt.red, 2))
            poly_item.setBrush(QColor(255, 20, 20, 60))
        else:
            poly_item.setPen(QPen(Qt.green, 2))
            poly_item.setBrush(QColor(20, 255, 20, 60))
        poly_item.setZValue(2)
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
            poly_item.setPen(QPen(Qt.red, 2))
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

        self.ar_preview_item = PolygonPreviewItem(points, color=Qt.yellow, pen_w=2)
        self.graphics_view.scene.addItem(self.ar_preview_item)

        self.update()

    def add_persistent_ar(self, points: List[QPointF]) -> None:
        # Add persistent polygon to scene
        poly_item = QGraphicsPolygonItem(QPolygonF(points))
        poly_item.setPen(QPen(Qt.yellow, 3))
        poly_item.setBrush(QColor(255, 255, 0, 20))
        poly_item.setZValue(1)
        self.graphics_view.scene.addItem(poly_item)
        self.ar_items.append(poly_item)
        self.update()

    def delete_persistent_ar(self, idx: int) -> None:
        item = self.ar_items.pop(idx)
        self.graphics_view.scene.removeItem(item)
        self.update()
