"""Phase 1 tests for XML export and parsing utilities."""

from pathlib import Path

import numpy as np
from lxml import etree
from PySide6.QtCore import QPointF

from cellpick.app.io.export import export_ar_xml, export_landmarks_xml, export_xml
from cellpick.app.io.xml_io import DVPXML, MockDVPXML


class _Shape:
    def __init__(self, points):
        self.points = points


def test_export_xml_writes_expected_shape_count(tmp_path: Path) -> None:
    shapes = [_Shape([QPointF(0.0, 0.0), QPointF(10.0, 0.0), QPointF(0.0, 10.0)])]
    dvpxml = MockDVPXML(shapes)

    output = tmp_path / "selected.xml"
    export_xml(str(output), [0], dvpxml, scale=2.0)

    tree = etree.parse(str(output))
    root = tree.getroot()

    assert root.findtext("ShapeCount") == "1"
    assert root.findtext("Shape_1/PointCount") == "3"
    assert root.findtext("Shape_1/X_1") == "0"
    assert root.findtext("Shape_1/Y_2") == "0"


def test_export_landmarks_and_ar_xml_counts(tmp_path: Path) -> None:
    landmarks_out = tmp_path / "landmarks.xml"
    ars_out = tmp_path / "ars.xml"

    landmarks = [[QPointF(0.0, 0.0), QPointF(2.0, 2.0), QPointF(4.0, 4.0)]]
    ars = [[QPointF(1.0, 1.0), QPointF(3.0, 3.0), QPointF(5.0, 5.0)]]

    export_landmarks_xml(str(landmarks_out), landmarks, scale=1.0)
    export_ar_xml(str(ars_out), ars, scale=1.0)

    landmarks_tree = etree.parse(str(landmarks_out))
    ars_tree = etree.parse(str(ars_out))

    assert landmarks_tree.getroot().findtext("LandmarkCount") == "1"
    assert ars_tree.getroot().findtext("ARCount") == "1"


def test_dvpxml_parses_minimal_input(tmp_path: Path) -> None:
    xml_text = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<ImageData>
  <GlobalCoordinates>1</GlobalCoordinates>
  <X_CalibrationPoint_1>10</X_CalibrationPoint_1>
  <Y_CalibrationPoint_1>20</Y_CalibrationPoint_1>
  <X_CalibrationPoint_2>30</X_CalibrationPoint_2>
  <Y_CalibrationPoint_2>40</Y_CalibrationPoint_2>
  <X_CalibrationPoint_3>50</X_CalibrationPoint_3>
  <Y_CalibrationPoint_3>60</Y_CalibrationPoint_3>
  <ShapeCount>1</ShapeCount>
  <Shape_1>
    <PointCount>3</PointCount>
    <X_1>1</X_1><Y_1>2</Y_1>
    <X_2>3</X_2><Y_2>4</Y_2>
    <X_3>5</X_3><Y_3>6</Y_3>
  </Shape_1>
</ImageData>
"""
    xml_path = tmp_path / "input.xml"
    xml_path.write_text(xml_text, encoding="utf-8")

    dvp = DVPXML(str(xml_path))
    assert dvp.n_shapes == 1
    assert dvp.x_calibration == [10, 30, 50]
    assert dvp.y_calibration == [20, 40, 60]

    x, y = dvp.return_shape(1)
    np.testing.assert_array_equal(x, np.array([1.0, 3.0, 5.0]))
    np.testing.assert_array_equal(y, np.array([2.0, 4.0, 6.0]))
