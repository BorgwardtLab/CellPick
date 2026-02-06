import sys
from copy import deepcopy
from typing import Any, Callable, List, Optional, Tuple

import numpy as np
import pandas as pd
import skimage
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF, QBrush
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
        self.setStyleSheet("background-color: black; border: none")

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

    def update_image(self, qimage: QImage) -> None:
        """Update the displayed image without changing zoom/pan."""
        if self.pixmap_item:
            pixmap = QPixmap.fromImage(qimage)
            self.pixmap_item.setPixmap(pixmap)
        else:
            # Fallback to set_image if no pixmap exists yet
            self.set_image(qimage)

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
    # Hybrid rendering: rasterized overlay for non-selected shapes
    _shape_overlay_item: Optional[QGraphicsPixmapItem]
    _shapes_visible: bool

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
        # Hybrid rendering state
        self._shape_overlay_item: Optional[QGraphicsPixmapItem] = None
        self._shapes_visible: bool = True
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

    def _update_composite_image(self, preserve_view: bool = False) -> None:
        """Update just the composite image without touching shape overlays.

        Args:
            preserve_view: If True, keep current zoom/pan. If False, reset to fit.
        """
        if not self.channels or self.height is None or self.width is None:
            return

        composite = np.zeros((self.height, self.width, 3), dtype=np.float32)
        for channel in self.channels:
            if channel.visible:
                # Use cached processed RGB data (fast path when saturation unchanged)
                composite += channel.get_processed_rgb()
        composite = np.clip(composite, 0, 255).astype(np.uint8)
        self.composite_image = composite
        h, w, _ = composite.shape
        bytes_per_line = 3 * w
        qimage = QImage(composite.data, w, h, bytes_per_line, QImage.Format_RGB888)
        if preserve_view:
            self.graphics_view.update_image(qimage)
        else:
            self.graphics_view.set_image(qimage)

    def update_display(self) -> None:
        """Full display update: recompute composite image AND update shape overlays."""
        self._update_composite_image()
        self.update_polygon_display()

    def update_image_only(self) -> None:
        """Fast update: only recompute composite image, preserve shape overlays and view."""
        self._update_composite_image(preserve_view=True)
        # Shape overlay and selected items are already in the scene with correct z-order

    def set_shapes_visible(self, visible: bool) -> None:
        """Show or hide all shape overlays."""
        self._shapes_visible = visible
        # Update overlay visibility
        if self._shape_overlay_item:
            self._shape_overlay_item.setVisible(visible)
        # Update selected shape items visibility
        for item in self.shape_items:
            item.setVisible(visible)

    def _get_shape_color(
        self,
        idx: int,
        polygon: Polygon,
        shape_outline_color: QColor,
        use_label_colors: bool,
        has_selected_shapes: bool,
    ) -> Tuple[QColor, QColor, int]:
        """
        Compute outline color, fill color, and pen width for a shape.

        Returns (outline_color, fill_color, base_pen_width)
        """
        # Priority: 1) Label colors (if enabled), 2) Score colors, 3) User-selected color
        if use_label_colors and idx in self.state.cell_labels:
            label = self.state.cell_labels[idx]
            if label in self.state.label_colors:
                rgb = self.state.label_colors[label]
                color = QColor(rgb[0], rgb[1], rgb[2])
                fill_color = QColor(rgb[0], rgb[1], rgb[2], 128)
            else:
                color = QColor(shape_outline_color)
                fill_color = QColor(
                    shape_outline_color.red(),
                    shape_outline_color.green(),
                    shape_outline_color.blue(),
                    128,
                )
        elif polygon.score is not None:
            color = QColor(polygon.color)
            fill_color = QColor(
                polygon.color.red(),
                polygon.color.green(),
                polygon.color.blue(),
                128,
            )
        else:
            color = QColor(shape_outline_color)
            fill_color = QColor(
                shape_outline_color.red(),
                shape_outline_color.green(),
                shape_outline_color.blue(),
                128,
            )

        is_selected = idx in self.state.selected_shape_ids

        if is_selected:
            color.setAlpha(ALPHA_ENABLED1)
            color.setRed(min(255, color.red() + 50))
            color.setGreen(min(255, color.green() + 50))
            color.setBlue(min(255, color.blue() + 50))
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
                fill_color.setAlpha(ALPHA_BASE2)
                fill_color.setRed(min(255, fill_color.red() + 50))
                fill_color.setGreen(min(255, fill_color.green() + 50))
                fill_color.setBlue(min(255, fill_color.blue() + 50))
                base_pen_width = 2

        return color, fill_color, base_pen_width

    def _rasterize_shapes(
        self,
        shape_outline_color: QColor,
        pen_scale: float,
        use_label_colors: bool,
        has_selected_shapes: bool,
    ) -> Optional[QPixmap]:
        """
        Rasterize all non-selected shapes into a single RGBA image.

        Renders at 2x resolution for crisp display when zoomed in.
        Returns a QPixmap with transparent background, or None if no shapes.
        """
        if not self.state.shapes or self.height is None or self.width is None:
            return None

        # Render at 2x resolution for better quality when zoomed
        scale = 2
        render_width = self.width * scale
        render_height = self.height * scale

        # Create transparent RGBA image at higher resolution
        overlay = QImage(render_width, render_height, QImage.Format_ARGB32)
        overlay.fill(Qt.transparent)

        painter = QPainter(overlay)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        # Scale the painter to draw at 2x
        painter.scale(scale, scale)

        selected_set = set(self.state.selected_shape_ids)

        for idx, polygon in enumerate(self.state.shapes):
            # Skip selected shapes - they'll be rendered as vector items
            if idx in selected_set:
                continue

            color, fill_color, base_pen_width = self._get_shape_color(
                idx, polygon, shape_outline_color, use_label_colors, has_selected_shapes
            )
            pen_width = max(0.5, base_pen_width * pen_scale)

            # Draw the polygon
            qpoly = polygon.get_qpolygon()
            painter.setPen(QPen(color, pen_width))
            painter.setBrush(QBrush(fill_color))
            painter.drawPolygon(qpoly)

        painter.end()

        # Scale back down to original size for proper positioning
        pixmap = QPixmap.fromImage(overlay)
        return pixmap.scaled(
            self.width, self.height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )

    def update_polygon_display(self) -> None:
        """
        Update shape display using hybrid rasterization.

        Non-selected shapes are rendered to a single rasterized overlay image.
        Selected shapes are rendered as vector QGraphicsPolygonItem for crisp display.
        """
        # Remove old vector items
        for item in self.shape_items:
            self.graphics_view.scene.removeItem(item)
        self.shape_items = []

        # Remove old overlay
        if self._shape_overlay_item:
            self.graphics_view.scene.removeItem(self._shape_overlay_item)
            self._shape_overlay_item = None

        # Early exit if no shapes or no image
        if not self.state.shapes or self.height is None:
            return

        # Get configuration from main window
        main_window = self.parent()
        while main_window and not hasattr(main_window, "shape_outline_color"):
            main_window = main_window.parent()

        if main_window and hasattr(main_window, "shape_outline_color"):
            shape_outline_color = main_window.shape_outline_color
        else:
            shape_outline_color = QColor(0, 255, 0)

        # Get scale factor for pen width
        scale_factor = 1
        if main_window and hasattr(main_window, "_spatialdata_scale_factor"):
            scale_factor = main_window._spatialdata_scale_factor
        pen_scale = max(0.25, min(1.0, 1.0 / (scale_factor**0.3)))

        has_selected_shapes = len(self.state.selected_shape_ids) > 0

        # Check label settings
        labels_available = (
            self.state.cell_labels is not None and self.state.label_colors is not None
        )
        prefer_gradient = False
        if main_window and hasattr(main_window, "_prefer_gradient_over_labels"):
            prefer_gradient = main_window._prefer_gradient_over_labels
        use_label_colors = labels_available and not prefer_gradient

        # 1) Rasterize all non-selected shapes into overlay
        overlay_pixmap = self._rasterize_shapes(
            shape_outline_color, pen_scale, use_label_colors, has_selected_shapes
        )

        if overlay_pixmap:
            self._shape_overlay_item = QGraphicsPixmapItem(overlay_pixmap)
            self._shape_overlay_item.setZValue(2)  # Below selected shapes
            self._shape_overlay_item.setVisible(self._shapes_visible)
            self.graphics_view.scene.addItem(self._shape_overlay_item)

        # 2) Render selected shapes as vector items (crisp at any zoom)
        for idx in self.state.selected_shape_ids:
            if idx >= len(self.state.shapes):
                continue
            polygon = self.state.shapes[idx]

            color, fill_color, base_pen_width = self._get_shape_color(
                idx, polygon, shape_outline_color, use_label_colors, has_selected_shapes
            )
            pen_width = max(0.5, base_pen_width * pen_scale)

            poly_item = QGraphicsPolygonItem(polygon.get_qpolygon())
            poly_item.setPen(QPen(color, pen_width))
            poly_item.setBrush(fill_color)
            poly_item.setZValue(3)  # Above overlay
            poly_item.setVisible(self._shapes_visible)
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
