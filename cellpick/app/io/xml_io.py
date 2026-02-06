"""
XML and metadata parsing for CellPick.

This module provides classes for reading DVP XML files containing
shape coordinates and calibration data, as well as metadata files.
"""

from typing import Any, List, Tuple

import numpy as np
import pandas as pd
import PIL
from lxml import etree
from PIL import Image
from scipy import interpolate

PIL.Image.MAX_IMAGE_PIXELS = 1063733067


class DVPXML:
    """
    Class for parsing and handling DVP XML files containing shape and calibration data.

    Attributes
    ----------
    path : str
        Path to the XML file.
    content : Any
        Parsed XML content.
    n_shapes : int
        Number of shapes in the XML.
    x_calibration : List[int]
        X calibration points.
    y_calibration : List[int]
        Y calibration points.
    """

    path: str
    content: Any
    n_shapes: int
    x_calibration: List[int]
    y_calibration: List[int]

    def __init__(self, path: str) -> None:
        """
        Initialize DVPXML by parsing the XML file and reading shapes/calibration points.

        Parameters
        ----------
        path : str
            Path to the XML file.
        """
        self.path = path
        self.content = etree.parse(path)
        self.parse_shapes()
        self.read_calibration_points()

    def parse_shapes(self) -> None:
        """Parse the number of shapes from the XML content."""
        shape_count_element = self.content.find(".//ShapeCount")
        self.n_shapes = (
            int(shape_count_element.text) if shape_count_element is not None else 0
        )

    def return_shape(self, index: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Return the x and y coordinates of the shape at the given index.

        Parameters
        ----------
        index : int
            Index of the shape to return (1-based).

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            The x and y coordinates of the shape.
        """
        if index > self.n_shapes:
            raise ValueError(f"Maximum shape is {self.n_shapes}")

        shape_path = f".//Shape_{index}"
        shape_element = self.content.find(shape_path)

        if shape_element is not None:
            n_points = int(shape_element.find(".//PointCount").text)
            pts = np.zeros((n_points, 2))

            for i in range(n_points):
                x_path = f".//X_{i+1}"
                y_path = f".//Y_{i+1}"

                x_element = shape_element.find(x_path)
                y_element = shape_element.find(y_path)

                if x_element is not None and y_element is not None:
                    pts[i, 0] = float(x_element.text)
                    pts[i, 1] = float(y_element.text)

            return pts[:, 0], pts[:, 1]
        else:
            return np.array([]), np.array([])

    def read_calibration_points(self) -> None:
        """Read calibration points from the XML content."""
        self.x_calibration = []
        self.y_calibration = []

        for i in range(3):
            x_path = f".//X_CalibrationPoint_{i+1}"
            y_path = f".//Y_CalibrationPoint_{i+1}"

            x_element = self.content.find(x_path)
            y_element = self.content.find(y_path)

            if x_element is not None and y_element is not None:
                self.x_calibration.append(int(x_element.text))
                self.y_calibration.append(int(y_element.text))


class MockDVPXML:
    """
    Mock DVPXML class for spatial data that doesn't have original XML.

    Provides the same interface as DVPXML for export functions.

    Attributes
    ----------
    shapes : list
        List of Polygon objects from the application state.
    n_shapes : int
        Number of shapes.
    x_calibration : List[int]
        X calibration points (default identity mapping).
    y_calibration : List[int]
        Y calibration points (default identity mapping).
    content : etree.Element
        Minimal XML content tree for compatibility.
    """

    def __init__(self, shapes) -> None:
        """
        Initialize MockDVPXML with shapes from the application state.

        Parameters
        ----------
        shapes : list
            List of Polygon objects from the application state.
        """
        self.shapes = shapes
        self.n_shapes = len(shapes)
        # Default calibration points (identity mapping)
        self.x_calibration = [0, 1000, 2000]
        self.y_calibration = [0, 1000, 2000]
        # Create a minimal XML content tree for compatibility
        self.content = etree.Element("ImageData")
        gc_elem = etree.SubElement(self.content, "GlobalCoordinates")
        gc_elem.text = "1"

    def return_shape(self, index: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Return shape coordinates for the given index (1-based).

        Parameters
        ----------
        index : int
            Shape index (1-based).

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            (x_coords, y_coords) as numpy arrays.
        """
        if index < 1 or index > len(self.shapes):
            raise ValueError(f"Shape index {index} out of range")

        shape = self.shapes[index - 1]
        x_coords = np.array([pt.x() for pt in shape.points])
        y_coords = np.array([pt.y() for pt in shape.points])
        return x_coords, y_coords


class DVPMETA:
    """
    Class for handling DVP metadata files.

    Attributes
    ----------
    path : str
        Path to the metadata file.
    metadata : pd.DataFrame
        DataFrame containing the metadata.
    """

    path: str
    metadata: pd.DataFrame

    def __init__(self, path: str) -> None:
        """
        Initialize DVPMETA by reading the metadata file.

        Parameters
        ----------
        path : str
            Path to the metadata file.
        """
        self.path = path
        self.metadata = pd.read_csv(path, sep="\t")

    def slice_subset(self, selected_slide: Any) -> pd.DataFrame:
        """
        Return a subset of the metadata for the selected slide.

        Parameters
        ----------
        selected_slide : Any
            The slide identifier to filter by.

        Returns
        -------
        pd.DataFrame
            Subset of the metadata for the selected slide.
        """
        metadata = self.metadata.copy()
        sub = metadata[metadata["Slide"] == selected_slide]
        return sub


class ImXML:
    """
    Class for handling image, XML, and metadata integration and operations.

    Attributes
    ----------
    dvpmeta : DVPMETA
        Metadata handler.
    dvpxml : DVPXML
        XML handler.
    im_path : str
        Path to the image file.
    im : np.ndarray
        Image data.
    im_shape : Tuple[int, ...]
        Shape of the image.
    slide : Any
        Current slide identifier.
    calib_x : Any
        X calibration values.
    calib_y : Any
        Y calibration values.
    fxx : Any
        Interpolator for x calibration.
    fyy : Any
        Interpolator for y calibration.
    """

    dvpmeta: DVPMETA
    dvpxml: DVPXML
    im_path: str
    im: np.ndarray
    im_shape: Tuple[int, ...]
    slide: Any
    calib_x: Any
    calib_y: Any
    fxx: Any
    fyy: Any

    def __init__(self, METADATA_PATH: str, XML_PATH: str, IM_PATH: str) -> None:
        """
        Initialize ImXML by loading metadata and XML only (no image loading here).

        Parameters
        ----------
        METADATA_PATH : str
            Path to the metadata file.
        XML_PATH : str
            Path to the XML file.
        IM_PATH : str
            Path to the image file.
        """
        self.dvpmeta = DVPMETA(METADATA_PATH)
        self.dvpxml = DVPXML(XML_PATH)
        self.im_path = IM_PATH

    def load_image(self) -> None:
        """Load the image from the file path and store its shape."""
        self.im = np.array(Image.open(self.im_path))
        self.im_shape = self.im.shape

    def bounding_rect(self, x: np.ndarray, y: np.ndarray) -> List[int]:
        """
        Calculate the bounding rectangle for the given x and y coordinates.

        Parameters
        ----------
        x : np.ndarray
            X-coordinates.
        y : np.ndarray
            Y-coordinates.

        Returns
        -------
        List[int]
            The bounding rectangle as [xmin, xmax, ymin, ymax].
        """
        return [
            int(np.floor(min(x))),
            int(np.ceil(max(x))),
            int(np.floor(min(y))),
            int(np.ceil(max(y))),
        ]

    def calibration(self, slide: Any) -> None:
        """
        Calibrate the image using the selected slide's metadata.

        Parameters
        ----------
        slide : Any
            The slide identifier to calibrate for.
        """
        self.slide = slide
        sub = self.dvpmeta.slice_subset(slide)
        resolution = sub["resolution"].iloc[0]
        xx = sub["X"] * 1 / resolution + self.im_shape[1] / 2
        yy = sub["Y"] * 1 / resolution + self.im_shape[0] / 2
        self.calib_x = xx
        self.calib_y = yy
        self.fxx = interpolate.interp1d(
            self.dvpxml.y_calibration, xx, fill_value="extrapolate"
        )
        self.fyy = interpolate.interp1d(
            self.dvpxml.x_calibration, yy, fill_value="extrapolate"
        )
