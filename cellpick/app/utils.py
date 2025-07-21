from typing import Any, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import PIL
import untangle
from lxml import etree
from PIL import Image
from scipy import interpolate
from tqdm import tqdm as tqdm

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
        """
        Parse the number of shapes from the XML content.
        """
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
            Index of the shape to return.

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
        """
        Read calibration points from the XML content.
        """
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
        """
        Load the image from the file path and store its shape.
        """
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

    def export_xml(self, path: str, indices: List[int]) -> None:
        """
        Select shapes with ID Shape_index in indices and export them to an XML file.

        Parameters
        ----------
        path : str
            Path to the output XML file.
        indices : List[int]
            List of shape indices to export.
        """
        # Create root element
        root = etree.Element("ImageData")
        # Add header comment
        root.append(etree.Comment("Cells selected using CellPick"))
        # Copy GlobalCoordinates from input if present, else set to 1
        global_coords = self.dvpxml.content.find(".//GlobalCoordinates")
        if global_coords is not None:
            gc_elem = etree.SubElement(root, "GlobalCoordinates")
            gc_elem.text = global_coords.text
        else:
            gc_elem = etree.SubElement(root, "GlobalCoordinates")
            gc_elem.text = "1"
        # Add calibration points
        for i in range(3):
            x_val = (
                self.dvpxml.x_calibration[i]
                if i < len(self.dvpxml.x_calibration)
                else 0
            )
            y_val = (
                self.dvpxml.y_calibration[i]
                if i < len(self.dvpxml.y_calibration)
                else 0
            )
            x_elem = etree.SubElement(root, f"X_CalibrationPoint_{i+1}")
            x_elem.text = str(x_val)
            y_elem = etree.SubElement(root, f"Y_CalibrationPoint_{i+1}")
            y_elem.text = str(y_val)
        # Add ShapeCount
        shape_count_elem = etree.SubElement(root, "ShapeCount")
        shape_count_elem.text = str(len(indices))
        # Add each selected shape, renumbered
        for new_idx, orig_idx in enumerate(indices, 1):
            x, y = self.dvpxml.return_shape(orig_idx + 1)
            shape_elem = etree.SubElement(root, f"Shape_{new_idx}")
            point_count_elem = etree.SubElement(shape_elem, "PointCount")
            point_count_elem.text = str(len(x))
            for j in range(len(x)):
                x_elem = etree.SubElement(shape_elem, f"X_{j+1}")
                x_elem.text = str(int(x[j]))
                y_elem = etree.SubElement(shape_elem, f"Y_{j+1}")
                y_elem.text = str(int(y[j]))
        # Write XML
        tree = etree.ElementTree(root)
        tree.write(path, pretty_print=True, xml_declaration=True, encoding="utf-8")

    def export_landmarks_xml(
        self, path: str, landmarks: List[List[Any]], scale: float
    ) -> None:
        """
        Export landmarks (list of list of QPointF) to an XML file.
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

    def export_ar_xml(self, path: str, ars: List[List[Any]], scale: float) -> None:
        """
        Export ARs (list of list of QPointF) to an XML file.
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
