"""Phase 1 tests for core algorithmic helpers."""

import numpy as np

from cellpick.app.algorithms import (
    approx_shape_distance,
    dist_to_polygon,
    gonzalez_k_center,
    polygon_gonzalez,
    polygon_mindist,
    polygon_round_robin_gonzalez,
)


def test_gonzalez_k_center_zero() -> None:
    points = np.array([[0.0], [1.0], [2.0]])
    assert gonzalez_k_center(points, 0) == []


def test_gonzalez_k_center_basic() -> None:
    points = np.array([[0.0], [10.0], [20.0]])
    assert gonzalez_k_center(points, 2) == [0, 2]


def test_polygon_gonzalez_zero() -> None:
    polys = [[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]]
    assert polygon_gonzalez(polys, 0) == []


def test_polygon_round_robin_shape() -> None:
    polys = [
        [[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]],
        [[(10.0, 0.0), (11.0, 0.0), (10.0, 1.0)]],
    ]
    centers = polygon_round_robin_gonzalez(polys, 1)
    assert len(centers) == 2
    assert centers[0] == [0]
    assert centers[1] == [0]


def test_polygon_mindist_identical_is_zero() -> None:
    poly = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    assert polygon_mindist([poly, poly]) == 0.0


def test_dist_to_polygon_inside_is_zero() -> None:
    polygon = [(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)]
    assert dist_to_polygon((0.2, 0.2), polygon) == 0.0


def test_approx_shape_distance_positive_for_separated_shapes() -> None:
    p1 = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    p2 = [(10.0, 10.0), (11.0, 10.0), (10.0, 11.0)]
    assert approx_shape_distance(p1, p2) > 0.0
