"""
CellPick application package.

This package provides the main application components for CellPick,
a tool for selecting cells in spatial omics data.

Modules
-------
core : Core data structures and state management
    - AppState, DataLoadMode, AppStateManager
    - Polygon, rescale_points_vectorized
    - ImageChannel, CHANNEL_COLORS

io : File I/O operations
    - DVPXML, MockDVPXML, DVPMETA, ImXML
    - export_xml, export_landmarks_xml, export_ar_xml

algorithms : Selection algorithms
    - gonzalez_k_center, polygon_gonzalez, etc.

ui_main : Main UI components
    - MainWindow, SelectionPage, ActionPage

ui_components : Reusable UI widgets
    - RangeSlider, AnimatedButton, ProgressDialog, etc.

image_viewer : Image display components
    - ImageViewer, ZoomableGraphicsView
"""

from .ui_main import MainWindow

# Re-export core components for convenient access
from .core import (
    AppState,
    DataLoadMode,
    AppStateManager,
    Polygon,
    rescale_points_vectorized,
    ImageChannel,
    CHANNEL_COLORS,
)

# Re-export I/O components
from .io import (
    DVPXML,
    MockDVPXML,
    DVPMETA,
    ImXML,
    export_xml,
    export_landmarks_xml,
    export_ar_xml,
)

__all__ = [
    # Main UI
    "MainWindow",
    # Core
    "AppState",
    "DataLoadMode",
    "AppStateManager",
    "Polygon",
    "rescale_points_vectorized",
    "ImageChannel",
    "CHANNEL_COLORS",
    # I/O
    "DVPXML",
    "MockDVPXML",
    "DVPMETA",
    "ImXML",
    "export_xml",
    "export_landmarks_xml",
    "export_ar_xml",
]
