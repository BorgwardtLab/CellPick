from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Optional
import random

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPolygonF
from PySide6.QtWidgets import QMessageBox

from .algorithms import (
    dist_to_polygon,
    gonzalez_k_center,
    polygon_gonzalez,
    polygon_round_robin_gonzalez,
    round_robin_gonzalez,
    polygon_mindist
)

CHANNEL_COLORS = [
    np.array([255, 255, 255]),
    np.array([100, 255, 100]),
    np.array([100, 100, 255]),
]


@dataclass
class ImageChannel:
    """
    Data class representing an image channel.

    Attributes
    ----------
    image_data : np.ndarray
        The image data for the channel.
    name : str
        The name of the channel.
    visible : bool
        Whether the channel is visible.
    color_idx : int
        Index for the display color.
    custom_color : Optional[np.ndarray]
        Custom RGB color array. If provided, overrides color_idx.
    """

    image_data: np.ndarray
    name: str
    visible: bool = True
    color_idx: int = 0
    custom_color: Optional[np.ndarray] = None


class Polygon:
    """
    Class representing a polygon with points, label, score, and color.

    Attributes
    ----------
    points : List[QPointF]
        The vertices of the polygon.
    label : str
        The label for the polygon.
    score : Optional[float]
        The score associated with the polygon.
    color : QColor
        The color of the polygon.
    original_id : Optional[int]
        The original segmentation mask ID (if loaded from labels).
    """

    points: List[QPointF]
    label: str
    score: Optional[float]
    color: QColor
    original_id: Optional[int]

    def __init__(
        self, points: List[QPointF], label: str = "", original_id: Optional[int] = None
    ) -> None:
        """
        Initialize a Polygon instance.

        Parameters
        ----------
        points : List[QPointF]
            The vertices of the polygon.
        label : str, optional
            The label for the polygon (default is '').
        original_id : Optional[int], optional
            The original segmentation mask ID (default is None).
        """
        self.points = points
        self.label = label
        self.score: Optional[float] = None
        self.color = QColor(255, 0, 255)
        self.original_id = original_id

    def set_color(self) -> None:
        """
        Set the color of the polygon based on its score.
        """
        if not self.score:
            self.color = QColor(255, 0, 255)
            return
        green = int(255 * self.score)
        red = 255 - green
        self.color = QColor(red, green, 0)

    def centroid(self) -> QPointF:
        """
        Compute the centroid of the polygon.

        Returns
        -------
        QPointF
            The centroid point.
        """
        if not self.points:
            return QPointF(0, 0)
        sum_x = sum(p.x() for p in self.points)
        sum_y = sum(p.y() for p in self.points)
        count = len(self.points)
        return QPointF(sum_x / count, sum_y / count)


class AppState(Enum):
    """
    Enum representing the application state.
    """

    HOME = auto()
    ADV_HOME = auto()
    MAIN = auto()
    SELECTING_LND = auto()
    DELETING_LND = auto()
    SELECTING_AR = auto()
    DELETING_AR = auto()
    ADDING_SHP = auto()
    DELETING_SHP = auto()
    SELECTING_CLB = auto()


class DataLoadMode(Enum):
    """
    Enum representing the data loading mode.
    Once set, this determines which workflow is available.
    """

    NONE = auto()  # No data loaded yet
    IMAGE = auto()  # Traditional image + XML workflow
    SPATIALDATA = auto()  # SpatialData workflow


class AppStateManager:
    """
    Class to manage the application state, shapes, landmarks, and active regions.

    Attributes
    ----------
    state : AppState
        The current application state.
    image_viewer : Any
        Reference to the image viewer.
    main_window : Any
        Reference to the main window.
    shapes : List[Polygon]
        List of all polygons.
    active_shape_ids : List[int]
        Indices of active shapes.
    selected_shape_ids : List[int]
        Indices of selected shapes.
    landmarks : List[List[QPointF]]
        List of landmark point lists.
    current_lnd_points : List[QPointF]
        Points for the current landmark selection.
    active_regions : List[List[QPointF]]
        List of active region point lists.
    current_ar_points : List[QPointF]
        Points for the current active region selection.
    cell_labels : Optional[Dict[int, Any]]
        Dictionary mapping cell indices to their labels.
    label_colors : Optional[Dict[Any, Tuple[int, int, int]]]
        Dictionary mapping label values to RGB colors.
    """

    state: AppState
    data_load_mode: DataLoadMode
    image_viewer: Any
    main_window: Any
    shapes: List[Polygon]
    active_shape_ids: List[int]
    selected_shape_ids: List[int]
    landmarks: List[List[QPointF]]
    current_lnd_points: List[QPointF]
    active_regions: List[List[QPointF]]
    current_ar_points: List[QPointF]
    cell_labels: Optional[dict[int, Any]]
    label_colors: Optional[dict[Any, tuple[int, int, int]]]

    def __init__(self) -> None:
        """
        Initialize the AppStateManager.
        """
        self.state = AppState.HOME
        self.data_load_mode = DataLoadMode.NONE
        self.image_viewer = None
        self.main_window = None
        self.shapes: List[Polygon] = []
        self.active_shape_ids: List[int] = []
        self.selected_shape_ids: List[int] = []
        self.landmarks: List[List[QPointF]] = []
        self.current_lnd_points: List[QPointF] = []
        self.active_regions: List[List[QPointF]] = []
        self.current_ar_points: List[QPointF] = []
        self.calibration_points: List[QPointF] = []
        self.cell_labels: Optional[dict[int, Any]] = None
        self.label_colors: Optional[dict[Any, tuple[int, int, int]]] = None

    def to_home(self) -> None:
        """
        Set the application state to HOME and reset home buttons.
        """
        self.state = AppState.HOME
        self.main_window.reset_home_buttons()

    def enable_advanced_home(self) -> None:
        """
        Set the application state to ADV_HOME and enable advanced home buttons.
        """
        self.state = AppState.ADV_HOME
        self.main_window.enable_adv_home_buttons()

    def reset_shapes(self) -> None:
        """
        Reset the shapes and related selection lists.
        """
        self.shapes = []
        self.active_shape_ids = []
        self.selected_shape_ids = []

    def can_add_lnd(self) -> bool:
        """
        Check if a new landmark can be added.

        Returns
        -------
        bool
            True if less than 2 landmarks exist, False otherwise.
        """
        return len(self.landmarks) < 2

    def start_landmark_selection(self) -> None:
        """
        Start the landmark selection process.
        """
        self.state = AppState.SELECTING_LND
        self.current_lnd_points = []

    def add_lnd_point(self, point: QPointF) -> None:
        """
        Add a point to the current landmark selection.

        Parameters
        ----------
        point : QPointF
            The point to add.
        """
        assert self.state == AppState.SELECTING_LND
        self.current_lnd_points.append(point)
        if len(self.current_lnd_points) > 2:
            self.main_window.enable_confirm_landmark()
        self.image_viewer.update_lnd_preview(self.current_lnd_points)

    def delete_last_lnd_point(self) -> None:
        """
        Delete the last point from the current landmark selection.
        """
        assert self.state == AppState.SELECTING_LND
        if len(self.current_lnd_points) > 0:
            self.current_lnd_points.pop()
        if len(self.current_lnd_points) <= 2:
            self.main_window.disable_confirm_landmark()
        self.image_viewer.update_lnd_preview(self.current_lnd_points)

    def confirm_landmark(self) -> None:
        """
        Confirm the current landmark selection and add it to the list of landmarks.
        """
        assert self.state == AppState.SELECTING_LND
        assert len(self.current_lnd_points) > 2
        self.landmarks.append(list(self.current_lnd_points))
        self.current_lnd_points = []
        self.image_viewer.update_lnd_preview(self.current_lnd_points)
        self.image_viewer.add_persistent_lnd(self.landmarks[-1])
        if len(self.landmarks) == 2:
            self.set_scores()
        self.state = AppState.MAIN

    def cancel_landmark(self) -> None:
        """
        Cancel the current landmark selection.
        """
        assert self.state == AppState.SELECTING_LND
        self.current_lnd_points = []
        if self.image_viewer.lnd_preview_item:
            self.image_viewer.graphics_view.scene.removeItem(
                self.image_viewer.lnd_preview_item
            )
        self.image_viewer.lnd_preview_item = None
        self.image_viewer.update()
        self.state = AppState.MAIN

    def start_landmark_deletion(self) -> None:
        """
        Start the landmark deletion process.
        """
        self.state = AppState.DELETING_LND

    def end_landmark_deletion(self) -> None:
        """
        End the landmark deletion process.
        """
        self.state = AppState.MAIN

    def try_deleting_landmark(self, scene_pos: QPointF) -> None:
        """
        Try to delete a landmark at the given scene position.

        Parameters
        ----------
        scene_pos : QPointF
            The position to check for landmark deletion.
        """
        for idx, lnd in enumerate(self.landmarks):
            poly = QPolygonF(lnd)
            if poly.containsPoint(scene_pos, Qt.OddEvenFill):
                self.landmarks.pop(idx)
                self.image_viewer.delete_persistent_lnd(idx)
                self.reset_scores()
                return

    def can_add_ar(self) -> bool:
        """
        Check if a new active region can be added.

        Returns
        -------
        bool
            True if can add active regions, False otherwise.
        """
        # return len(self.active_regions) < 1 # If we allow only one region
        return True

    def can_load_lnd(self):
        """
        Check if landmarks can be loaded from a file.

        Returns
        -------
        bool
            True if can load landmarks, False otherwise.
        """
        # Enable only if there are no landmarks
        return len(self.landmarks) == 0

    def can_load_ar(self):
        """
        Check if active regions can be loaded from a file.

        Returns
        -------
        bool
            True if can load active regions, False otherwise.
        """
        # Enable only if there are no ARs
        return len(self.active_regions) == 0

    def start_ar_selection(self) -> None:
        """
        Start the active region selection process.
        """
        self.state = AppState.SELECTING_AR
        self.current_ar_points = []

    def add_ar_point(self, point: QPointF) -> None:
        """
        Add a point to the current active region selection.

        Parameters
        ----------
        point : QPointF
            The point to add.
        """
        assert self.state == AppState.SELECTING_AR
        self.current_ar_points.append(point)
        if len(self.current_ar_points) > 2:
            self.main_window.enable_confirm_ar()
        self.image_viewer.update_ar_preview(self.current_ar_points)

    def delete_last_ar_point(self) -> None:
        """
        Delete the last point from the current active region selection.
        """
        assert self.state == AppState.SELECTING_AR
        if len(self.current_ar_points) > 0:
            self.current_ar_points.pop()
        if len(self.current_ar_points) <= 2:
            self.main_window.enable_confirm_ar(False)
        self.image_viewer.update_ar_preview(self.current_ar_points)

    def confirm_ar(self) -> None:
        """
        Confirm the current active region selection and add it to the list of active regions.
        """
        assert self.state == AppState.SELECTING_AR
        assert len(self.current_ar_points) > 2
        self.active_regions.append(list(self.current_ar_points))
        self.current_ar_points = []
        self.image_viewer.update_ar_preview(self.current_ar_points)
        self.image_viewer.add_persistent_ar(self.active_regions[-1])
        self.filter_by_ar()
        self.state = AppState.MAIN

    def cancel_ar(self) -> None:
        """
        Cancel the current active region selection.
        """
        assert self.state == AppState.SELECTING_AR
        self.current_ar_points = []
        if self.image_viewer.ar_preview_item:
            self.image_viewer.graphics_view.scene.removeItem(
                self.image_viewer.ar_preview_item
            )
        self.image_viewer.ar_preview_item = None
        self.image_viewer.update()
        self.state = AppState.MAIN

    def start_ar_deletion(self) -> None:
        """
        Start the active region deletion process.
        """
        self.state = AppState.DELETING_AR

    def end_ar_deletion(self) -> None:
        """
        End the active region deletion process.
        """
        self.state = AppState.MAIN

    def try_deleting_ar(self, scene_pos: QPointF) -> None:
        """
        Try to delete an active region at the given scene position.

        Parameters
        ----------
        scene_pos : QPointF
            The position to check for active region deletion.
        """
        for idx, ar in enumerate(self.active_regions):
            poly = QPolygonF(ar)
            if poly.containsPoint(scene_pos, Qt.OddEvenFill):
                self.active_regions.pop(idx)
                self.image_viewer.delete_persistent_ar(idx)
                self.filter_by_ar()
                return

    def filter_by_ar(self) -> None:
        """
        Filter shapes by active regions and update the display.
        """
        self.active_shape_ids = []
        for i in range(len(self.shapes)):
            c = self.shapes[i].centroid()
            is_contained = False
            for ar in self.active_regions:
                poly = QPolygonF(ar)
                if poly.containsPoint(c, Qt.OddEvenFill):
                    is_contained = True
                    break
            if is_contained:
                self.active_shape_ids.append(i)
        self.selected_shape_ids = self.active_shape_ids
        self.image_viewer.update_polygon_display()

    def update_active_shapes(self) -> None:
        """
        Update active shapes based on current active regions.
        Alias for filter_by_ar() for clearer semantics.
        """
        self.filter_by_ar()

    def select_shapes(self, k: int) -> None:
        """
        Select k shapes from the active shapes using the Gonzalez k-center algorithm.

        Parameters
        ----------
        k : int
            Number of shapes to select.
        """
        # Check if we're using label-based selection
        clustering_index = self.main_window.page2.clustering_type.currentIndex()

        # Filter active shapes by selected labels if using label-based selection
        if clustering_index == 3:
            # Get selected labels from checkboxes
            selected_labels = self.main_window.page2.get_selected_labels()
            if selected_labels is None:
                QMessageBox.warning(
                    self.main_window,
                    "Error",
                    "No labels are loaded. Please load labels first.",
                )
                return

            # Filter active shapes to only include those with selected labels
            filtered_active_ids = []
            for idx in self.active_shape_ids:
                if idx in self.cell_labels:
                    label = self.cell_labels[idx]
                    if label in selected_labels:
                        filtered_active_ids.append(idx)

            if not filtered_active_ids:
                QMessageBox.warning(
                    self.main_window,
                    "Error",
                    "No shapes with selected labels in active regions.",
                )
                return

            # Use filtered list for selection
            active_ids_for_selection = filtered_active_ids
        else:
            active_ids_for_selection = self.active_shape_ids

        if len(active_ids_for_selection) <= k:
            self.selected_shape_ids = active_ids_for_selection
            QMessageBox.warning(
                self.main_window, "Warning", f"Could not select {k} shapes, selected {len(self.active_shape_ids)}"
            )
        elif clustering_index == 0:
            # Select k over union of regions
            polys = []
            for i, idx1 in enumerate(active_ids_for_selection):
                polys.append([(p.x(), p.y()) for p in self.shapes[idx1].points])
            selected_ids = polygon_gonzalez(polys, k)
            self.selected_shape_ids = [
                active_ids_for_selection[i] for i in selected_ids
            ]
        elif clustering_index == 1: 
            # Select randomly
            selected_ids = sorted(random.sample(range(len(active_ids_for_selection)), k))
            self.selected_shape_ids = [active_ids_for_selection[i] for i in selected_ids]
        elif clustering_index == 2:
            # Select k per active region
            point_ids = [[] for _ in self.active_regions]
            polys = [[] for _ in self.active_regions]
            for i in active_ids_for_selection:
                p = self.shapes[i].centroid()
                is_contained = -1
                for j, ar in enumerate(self.active_regions):
                    poly = QPolygonF(ar)
                    if poly.containsPoint(p, Qt.OddEvenFill):
                        is_contained = j
                        break
                assert is_contained >= 0
                point_ids[is_contained].append(i)
                polys[is_contained].append(
                    [(p.x(), p.y()) for p in self.shapes[i].points]
                )
            selected_idss = polygon_round_robin_gonzalez(polys, k)
            if any([len(ids)<k for ids in selected_idss]):
                QMessageBox.warning(
                    self.main_window, "Warning", f"Could not select {k} shapes per AR"
                )
            self.selected_shape_ids = []
            for i, selected_ids in enumerate(selected_idss):
                self.selected_shape_ids += [point_ids[i][idx] for idx in selected_ids]
        elif clustering_index == 3:
            # Select k per label
            point_ids = [[] for _ in selected_labels]
            polys = [[] for _ in selected_labels]
            for i in active_ids_for_selection:
                label = self.cell_labels[i]
                label_idx = selected_labels.index(label)
                point_ids[label_idx].append(i)
                polys[label_idx].append([(p.x(), p.y()) for p in self.shapes[i].points])
            selected_idss = polygon_round_robin_gonzalez(polys, k)
            if any([len(ids)<k for ids in selected_idss]):
                QMessageBox.warning(
                    self.main_window, "Warning", f"Could not select {k} shapes per label"
                )
            self.selected_shape_ids = []
            for i, selected_ids in enumerate(selected_idss):
                self.selected_shape_ids += [point_ids[i][idx] for idx in selected_ids]

        polys = []
        for i, idx1 in enumerate(self.selected_shape_ids):
            polys.append([(p.x(), p.y()) for p in self.shapes[idx1].points])
        if polygon_mindist(polys) < 2.0:
            QMessageBox.warning(
                self.main_window, "Warning", f"Some selected shapes are contiguous"
            )

        self.image_viewer.update_polygon_display()

    def try_adding_shp(self, scene_pos: QPointF) -> None:
        """
        Try to add a shape at the given scene position to the selection.

        Parameters
        ----------
        scene_pos : QPointF
            The position to check for shape addition.
        """
        for idx in self.active_shape_ids:
            poly = QPolygonF(self.shapes[idx].points)
            if poly.containsPoint(scene_pos, Qt.OddEvenFill):
                self.selected_shape_ids.append(idx)
                self.image_viewer.update_polygon_display()
                return

    def try_deleting_shp(self, scene_pos: QPointF) -> None:
        """
        Try to delete a shape at the given scene position from the selection.

        Parameters
        ----------
        scene_pos : QPointF
            The position to check for shape deletion.
        """
        for i, idx in enumerate(self.selected_shape_ids):
            poly = QPolygonF(self.shapes[idx].points)
            if poly.containsPoint(scene_pos, Qt.OddEvenFill):
                self.selected_shape_ids.pop(i)
                self.image_viewer.update_polygon_display()
                return

    def set_scores(self) -> None:
        """
        Set the score for each shape based on the distance to the two landmarks.
        """
        assert len(self.landmarks) == 2
        landmark1 = [(p.x(), p.y()) for p in self.landmarks[0]]
        landmark2 = [(p.x(), p.y()) for p in self.landmarks[1]]
        for shape in self.shapes:
            c = shape.centroid()
            d1 = dist_to_polygon((c.x(), c.y()), landmark1)
            d2 = dist_to_polygon((c.x(), c.y()), landmark2)
            shape.score = d1 / (d1 + d2 + 1e-9)
            shape.set_color()
        self.image_viewer.update_polygon_display()

    def load_cell_labels(self, labels_dict: dict[int, Any]) -> None:
        """
        Load cell labels and generate color mapping using Tab20 or Tab10 palette.

        Parameters
        ----------
        labels_dict : dict[int, Any]
            Dictionary mapping cell original IDs (from segmentation mask or table instance column) to their labels.
        """
        # If shapes have original_id attributes, build a reverse mapping: original_id -> shape_index
        # This allows labels_dict (keyed by original mask IDs) to correctly map to shape list indices.
        original_id_to_index = {}
        has_original_ids = False
        for idx, shape in enumerate(self.shapes):
            if hasattr(shape, "original_id") and shape.original_id is not None:
                original_id_to_index[shape.original_id] = idx
                has_original_ids = True

        if has_original_ids:
            # Remap labels_dict from original_id keys to shape_index keys
            remapped_labels = {}
            for original_id, label in labels_dict.items():
                shape_idx = original_id_to_index.get(original_id)
                if shape_idx is not None:
                    remapped_labels[shape_idx] = label
            self.cell_labels = remapped_labels
        else:
            # No original_ids, use labels_dict as-is (assumes keys are already shape indices)
            self.cell_labels = labels_dict

        self.generate_label_colors()

        if self.image_viewer:
            self.image_viewer.update_polygon_display()

    def generate_label_colors(self) -> None:
        """
        Generate distinct colors for each unique label using matplotlib Tab20 or Tab10 palette.
        Uses Tab10 if fewer than 10 labels, otherwise Tab20.
        """
        if not self.cell_labels:
            self.label_colors = None
            return

        # Get unique labels
        unique_labels = sorted(set(self.cell_labels.values()))
        n_labels = len(unique_labels)

        # Use matplotlib's Tab10 or Tab20 colormap for categorical colors
        import matplotlib.pyplot as plt

        if n_labels <= 10:
            cmap = plt.cm.get_cmap("tab10")
        else:
            cmap = plt.cm.get_cmap("tab20")

        # Generate colors for each unique label
        self.label_colors = {}
        for idx, label in enumerate(unique_labels):
            # Cycle through colors
            color_idx = idx % (10 if n_labels <= 10 else 20)
            rgba = cmap(color_idx)
            # Convert to RGB (0-255)
            rgb = (int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255))
            self.label_colors[label] = rgb

    def clear_cell_labels(self) -> None:
        """
        Clear loaded cell labels.
        """
        self.cell_labels = None
        self.label_colors = None
        if self.image_viewer:
            self.image_viewer.update_polygon_display()

    def reset_scores(self) -> None:
        """
        Reset the scores for all shapes.
        """
        for shape in self.shapes:
            shape.score = None
            shape.set_color()
        self.image_viewer.update_polygon_display()

    def start_calibration_selection(self) -> None:
        self.calibration_points = []
        self.image_viewer.remove_calibration_items()
        self.state = AppState.SELECTING_CLB

    def end_calibration_selection(self) -> None:
        self.state = AppState.ADV_HOME
        self.image_viewer.remove_calibration_items()

    def add_calibration_point(self, scene_pos: QPointF) -> None:
        self.calibration_points.append(scene_pos)
        self.image_viewer.add_calibration_item(
            scene_pos, len(self.calibration_points) - 1
        )
        if len(self.calibration_points) == 3:
            self.state = AppState.ADV_HOME
            self.main_window.page1.manual_calibration_btn.setText("Manual")
            self.main_window.enable_adv_home_buttons()
            