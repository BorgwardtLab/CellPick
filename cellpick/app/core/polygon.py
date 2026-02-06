"""
Polygon data structures and geometry utilities.

This module provides the Polygon class for representing cell boundaries
and utility functions for coordinate transformations.
"""

from typing import List, Optional

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPolygonF


def rescale_points_vectorized(
    points: List[QPointF], scale_factor: float
) -> List[QPointF]:
    """
    Rescale a list of QPointF using vectorized numpy operations.

    Parameters
    ----------
    points : List[QPointF]
        The list of points to rescale.
    scale_factor : float
        The factor to divide coordinates by.

    Returns
    -------
    List[QPointF]
        The rescaled points.
    """
    if not points or scale_factor == 1:
        return points

    # Extract coordinates into numpy arrays (vectorized extraction)
    n = len(points)
    coords = np.empty((n, 2), dtype=np.float64)
    for i, p in enumerate(points):
        coords[i, 0] = p.x()
        coords[i, 1] = p.y()

    # Vectorized division (single operation on entire array)
    coords *= 1.0 / scale_factor

    # Convert back to QPointF list
    return [QPointF(coords[i, 0], coords[i, 1]) for i in range(n)]


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
        self._cached_qpolygon: Optional[QPolygonF] = None

    def get_qpolygon(self) -> QPolygonF:
        """
        Get cached QPolygonF, creating it if necessary.

        Returns
        -------
        QPolygonF
            The cached polygon for efficient rendering.
        """
        if self._cached_qpolygon is None:
            self._cached_qpolygon = QPolygonF(self.points)
        return self._cached_qpolygon

    def invalidate_cache(self) -> None:
        """Invalidate the cached QPolygonF (call when points change)."""
        self._cached_qpolygon = None

    def set_color(self) -> None:
        """
        Set the color of the polygon based on its score.

        If no score is set, uses magenta. Otherwise, uses a
        gradient from red (low score) to green (high score).
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
