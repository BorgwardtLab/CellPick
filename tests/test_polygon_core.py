"""Phase 1 tests for polygon/core helpers."""

from PySide6.QtCore import QPointF

from cellpick.app.core.polygon import Polygon, rescale_points_vectorized


def test_rescale_points_vectorized_scales_coordinates() -> None:
    points = [QPointF(2.0, 4.0), QPointF(6.0, 8.0)]
    scaled = rescale_points_vectorized(points, 2.0)

    assert len(scaled) == 2
    assert scaled[0].x() == 1.0
    assert scaled[0].y() == 2.0
    assert scaled[1].x() == 3.0
    assert scaled[1].y() == 4.0


def test_rescale_points_vectorized_identity_returns_original_list() -> None:
    points = [QPointF(1.0, 2.0)]
    same = rescale_points_vectorized(points, 1.0)
    assert same is points


def test_polygon_centroid_empty_is_origin() -> None:
    poly = Polygon(points=[])
    centroid = poly.centroid()
    assert centroid.x() == 0.0
    assert centroid.y() == 0.0


def test_polygon_centroid_non_empty() -> None:
    poly = Polygon(points=[QPointF(0.0, 0.0), QPointF(2.0, 2.0)])
    centroid = poly.centroid()
    assert centroid.x() == 1.0
    assert centroid.y() == 1.0


def test_polygon_set_color_handles_non_finite_score() -> None:
    poly = Polygon(points=[QPointF(0.0, 0.0), QPointF(1.0, 0.0), QPointF(0.0, 1.0)])
    poly.score = float("nan")
    poly.set_color()
    assert (poly.color.red(), poly.color.green(), poly.color.blue()) == (255, 0, 255)
