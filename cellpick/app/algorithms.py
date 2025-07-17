from typing import List, Tuple

import numpy as np
from shapely.geometry import Point, Polygon


def gonzalez_k_center(points: np.ndarray, k: int) -> List[int]:
    """
    Select k centers from a set of points using the Gonzalez k-center algorithm.

    Parameters
    ----------
    points : np.ndarray
        Array of points with shape (n_points, n_features).
    k : int
        Number of centers to select.

    Returns
    -------
    List[int]
        Indices of the selected centers.
    """
    if k == 0:
        return []
    centers = [0]
    dists = np.linalg.norm(points - points[0], axis=1)

    for _ in range(1, k):
        idx = np.argmax(dists)
        centers.append(idx)
        dists = np.minimum(dists, np.linalg.norm(points - points[idx], axis=1))

    return centers


def round_robin_gonzalez(points: List[np.ndarray], k: int):
    """
    Select k centers from a set of points using a heuristic for the fair k-center problem
    based on the Gonzalez k-center algorithm.

    Parameters
    ----------
    points : List[np.ndarray]
        A list of arrays of points with shape (n_points, n_features), one per class.
    k : int
        Number of centers to select per class.

    Returns
    -------
    List[List[int]]
        A list of lists of indices of the selected centers.
    """
    if k == 0:
        return [[]]

    num_classes = len(points)

    centers = [[] for c in range(num_classes)]
    dists = [np.full(points[c].shape[0], np.inf) for c in range(num_classes)]

    for _ in range(0, k):
        for c in range(num_classes):
            if len(centers[c]) > points[c].shape[0]:
                continue
            idx = np.argmax(dists[c])
            centers[c].append(idx)
            dists = [
                np.minimum(
                    dists[c2], np.linalg.norm(points[c2] - points[c][idx], axis=1)
                )
                for c2 in range(num_classes)
            ]

    return centers


def polygon_gonzalez(polys: List[List[Tuple[float, float]]], k: int) -> List[int]:
    """
    Select k centers from a set of polygons using the Gonzalez k-center algorithm.

    Parameters
    ----------
    points : np.ndarray
        Array of points with shape (n_points, n_features).
    k : int
        Number of centers to select.

    Returns
    -------
    List[int]
        Indices of the selected centers.
    """
    if k == 0:
        return []
    centers = [0]
    dists = np.array([approx_shape_distance(poly, polys[0]) for poly in polys])

    for _ in range(1, k):
        idx = np.argmax(dists)
        centers.append(idx)
        dists2 = np.array([approx_shape_distance(poly, polys[idx]) for poly in polys])
        dists = np.minimum(dists, dists2)

    return centers


def polygon_round_robin_gonzalez(polys: List[List[List[Tuple[float, float]]]], k: int):
    """
    Select k centers from a set of polygons using a heuristic for the fair k-center problem
    based on the Gonzalez k-center algorithm.

    Parameters
    ----------
    points : List[List[List[Tuple[float, float]]]]
        A list of lists of polygons
    k : int
        Number of centers to select per class.

    Returns
    -------
    List[List[int]]
        A list of lists of indices of the selected centers.
    """
    if k == 0:
        return [[]]

    num_classes = len(polys)

    centers = [[] for c in range(num_classes)]
    dists = [np.full(len(polys[c]), np.inf) for c in range(num_classes)]

    for _ in range(0, k):
        for c in range(num_classes):
            if len(centers[c]) > len(polys[c]):
                continue
            idx = np.argmax(dists[c])
            centers[c].append(idx)
            dists = [
                np.minimum(
                    dists[c2],
                    np.array(
                        [
                            approx_shape_distance(poly, polys[c][idx])
                            for poly in polys[c2]
                        ]
                    ),
                )
                for c2 in range(num_classes)
            ]

    return centers


def dist_to_polygon(
    point: Tuple[float, float], polygon: List[Tuple[float, float]]
) -> float:
    """
    Compute the minimum distance from a point to a polygon.

    Parameters
    ----------
    point : Tuple[float, float]
        The (x, y) coordinates of the point.
    polygon : List[Tuple[float, float]]
        List of (x, y) coordinates representing the polygon vertices.

    Returns
    -------
    float
        The minimum distance from the point to the polygon.
    """
    point = Point(point)
    polygon = Polygon(polygon)
    return point.distance(polygon)


def approx_shape_distance(
    polygon1: List[Tuple[float, float]], polygon2: List[Tuple[float, float]]
) -> float:
    """
    Compute the distance between two polygons.

    Parameters
    ----------
    polygon1 : List[Tuple[float, float]]
        List of (x, y) coordinates representing the polygon vertices.
    polygon2 : List[Tuple[float, float]]
        List of (x, y) coordinates representing the polygon vertices.

    Returns
    -------
    float
        The approximate distance between the polygons.
    """
    A = np.array(polygon1)
    B = np.array(polygon2)

    a = A[np.linalg.norm(A - B.mean(axis=0), axis=1).argmin()]
    b = B[np.linalg.norm(B - a, axis=1).argmin()]
    return float(np.linalg.norm(a - b))
