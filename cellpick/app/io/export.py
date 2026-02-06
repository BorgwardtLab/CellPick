"""
Export functions for CellPick.

This module provides functions for exporting selected shapes,
landmarks, and active regions to XML and CSV formats.
"""

from typing import Any, List

from lxml import etree


def export_xml(path: str, indices: List[int], dvpxml, scale: float = 1.0) -> None:
    """
    Select shapes with ID Shape_index in indices and export them to an XML file.

    Parameters
    ----------
    path : str
        Path to the output XML file.
    indices : List[int]
        List of shape indices to export.
    dvpxml : DVPXML or MockDVPXML
        The DVPXML object containing shape data.
    scale : float, optional
        Scale factor for coordinates. Coordinates are divided by this value.
        Use this to rescale from display coordinates to full resolution.
        Default is 1.0 (no scaling).
    """
    # Create root element
    root = etree.Element("ImageData")
    # Add header comment
    root.append(etree.Comment("Cells selected using CellPick"))
    # Copy GlobalCoordinates from input if present, else set to 1
    global_coords = dvpxml.content.find(".//GlobalCoordinates")
    if global_coords is not None:
        gc_elem = etree.SubElement(root, "GlobalCoordinates")
        gc_elem.text = global_coords.text
    else:
        gc_elem = etree.SubElement(root, "GlobalCoordinates")
        gc_elem.text = "1"
    # Add calibration points
    for i in range(3):
        x_val = dvpxml.x_calibration[i] if i < len(dvpxml.x_calibration) else 0
        y_val = dvpxml.y_calibration[i] if i < len(dvpxml.y_calibration) else 0
        x_elem = etree.SubElement(root, f"X_CalibrationPoint_{i+1}")
        x_elem.text = str(x_val)
        y_elem = etree.SubElement(root, f"Y_CalibrationPoint_{i+1}")
        y_elem.text = str(y_val)
    # Add ShapeCount
    shape_count_elem = etree.SubElement(root, "ShapeCount")
    shape_count_elem.text = str(len(indices))
    # Add each selected shape, renumbered
    for new_idx, orig_idx in enumerate(indices, 1):
        x, y = dvpxml.return_shape(orig_idx + 1)
        shape_elem = etree.SubElement(root, f"Shape_{new_idx}")
        point_count_elem = etree.SubElement(shape_elem, "PointCount")
        point_count_elem.text = str(len(x))
        for j in range(len(x)):
            x_elem = etree.SubElement(shape_elem, f"X_{j+1}")
            x_elem.text = str(int(x[j] / scale))
            y_elem = etree.SubElement(shape_elem, f"Y_{j+1}")
            y_elem.text = str(int(y[j] / scale))
    # Write XML
    tree = etree.ElementTree(root)
    tree.write(path, pretty_print=True, xml_declaration=True, encoding="utf-8")


def export_landmarks_xml(path: str, landmarks: List[List[Any]], scale: float) -> None:
    """
    Export landmarks (list of list of QPointF) to an XML file.

    Parameters
    ----------
    path : str
        Path to the output XML file.
    landmarks : List[List[Any]]
        List of landmarks, where each landmark is a list of QPointF.
    scale : float
        Scale factor for coordinates. Coordinates are divided by this value.
    """
    root = etree.Element("LandmarksData")
    root.append(etree.Comment("Landmarks exported using CellPick"))
    count_elem = etree.SubElement(root, "LandmarkCount")
    count_elem.text = str(len(landmarks))
    for idx, lnd in enumerate(landmarks, 1):
        lnd_elem = etree.SubElement(root, f"Landmark_{idx}")
        point_count_elem = etree.SubElement(lnd_elem, "PointCount")
        point_count_elem.text = str(len(lnd))
        for j, pt in enumerate(lnd):
            x_elem = etree.SubElement(lnd_elem, f"X_{j+1}")
            x_elem.text = str(int(pt.x() / scale))
            y_elem = etree.SubElement(lnd_elem, f"Y_{j+1}")
            y_elem.text = str(int(pt.y() / scale))
    tree = etree.ElementTree(root)
    tree.write(path, pretty_print=True, xml_declaration=True, encoding="utf-8")


def export_ar_xml(path: str, ars: List[List[Any]], scale: float) -> None:
    """
    Export active regions (ARs) (list of list of QPointF) to an XML file.

    Parameters
    ----------
    path : str
        Path to the output XML file.
    ars : List[List[Any]]
        List of active regions, where each AR is a list of QPointF.
    scale : float
        Scale factor for coordinates. Coordinates are divided by this value.
    """
    root = etree.Element("ARData")
    root.append(etree.Comment("Active Regions exported using CellPick"))
    count_elem = etree.SubElement(root, "ARCount")
    count_elem.text = str(len(ars))
    for idx, ar in enumerate(ars, 1):
        ar_elem = etree.SubElement(root, f"AR_{idx}")
        point_count_elem = etree.SubElement(ar_elem, "PointCount")
        point_count_elem.text = str(len(ar))
        for j, pt in enumerate(ar):
            x_elem = etree.SubElement(ar_elem, f"X_{j+1}")
            x_elem.text = str(int(pt.x() / scale))
            y_elem = etree.SubElement(ar_elem, f"Y_{j+1}")
            y_elem.text = str(int(pt.y() / scale))
    tree = etree.ElementTree(root)
    tree.write(path, pretty_print=True, xml_declaration=True, encoding="utf-8")
