"""
I/O module for CellPick file operations.

This module provides:
- DVPXML, MockDVPXML, DVPMETA, ImXML: XML and metadata parsing
- export_xml, export_landmarks_xml, export_ar_xml: Export functions
- SpatialData loading and export utilities
"""

from .xml_io import DVPXML, MockDVPXML, DVPMETA, ImXML
from .export import export_xml, export_landmarks_xml, export_ar_xml

# Set canonical module paths to avoid Sphinx cross-reference ambiguity
DVPXML.__module__ = "cellpick.app.io.xml_io"
MockDVPXML.__module__ = "cellpick.app.io.xml_io"
DVPMETA.__module__ = "cellpick.app.io.xml_io"
ImXML.__module__ = "cellpick.app.io.xml_io"

__all__ = [
    "DVPXML",
    "MockDVPXML",
    "DVPMETA",
    "ImXML",
    "export_xml",
    "export_landmarks_xml",
    "export_ar_xml",
]
