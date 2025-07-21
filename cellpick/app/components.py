from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Optional

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPolygonF

from .algorithms import (
    dist_to_polygon,
    gonzalez_k_center,
    polygon_gonzalez,
    polygon_round_robin_gonzalez,
    round_robin_gonzalez,
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
    """

    points: List[QPointF]
    label: str
    score: Optional[float]
    color: QColor

    def __init__(self, points: List[QPointF], label: str = "") -> None:
        """
        Initialize a Polygon instance.

        Parameters
        ----------
        points : List[QPointF]
            The vertices of the polygon.
        label : str, optional
            The label for the polygon (default is '').
        """
        self.points = points
        self.label = label
        self.score: Optional[float] = None
        self.color = QColor(255, 0, 255)

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
    """

    state: AppState
    image_viewer: Any
    main_window: Any
    shapes: List[Polygon]
    active_shape_ids: List[int]
    selected_shape_ids: List[int]
    landmarks: List[List[QPointF]]
    current_lnd_points: List[QPointF]
    active_regions: List[List[QPointF]]
    current_ar_points: List[QPointF]

    def __init__(self) -> None:
        """
        Initialize the AppStateManager.
        """
        self.state = AppState.HOME
        self.image_viewer = None
        self.main_window = None
        self.shapes: List[Polygon] = []
        self.active_shape_ids: List[int] = []
        self.selected_shape_ids: List[int] = []
        self.landmarks: List[List[QPointF]] = []
        self.current_lnd_points: List[QPointF] = []
        self.active_regions: List[List[QPointF]] = []
        self.current_ar_points: List[QPointF] = []

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

    def select_shapes(self, k: int) -> None:
        """
        Select k shapes from the active shapes using the Gonzalez k-center algorithm.

        Parameters
        ----------
        k : int
            Number of shapes to select.
        """
        if len(self.active_shape_ids) <= k:
            self.selected_shape_ids = self.active_shape_ids
        elif self.main_window.page2.clustering_type.currentIndex() == 0:
            polys = []
            for i, idx1 in enumerate(self.active_shape_ids):
                polys.append([(p.x(), p.y()) for p in self.shapes[idx1].points])
            selected_ids = polygon_gonzalez(polys, k)
            self.selected_shape_ids = [self.active_shape_ids[i] for i in selected_ids]
        else:
            point_ids = [[] for _ in self.active_regions]
            polys = [[] for _ in self.active_regions]
            for i in self.active_shape_ids:
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
            if selected_idss is None:
                QMessageBox.warning(
                    self.main_window, "Error", f"Could not select {k} shapes per AR"
                )
                return
            self.selected_shape_ids = []
            for i, selected_ids in enumerate(selected_idss):
                self.selected_shape_ids += [point_ids[i][idx] for idx in selected_ids]

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

    def reset_scores(self) -> None:
        """
        Reset the scores for all shapes.
        """
        for shape in self.shapes:
            shape.score = None
            shape.set_color()
        self.image_viewer.update_polygon_display()
