"""
Core module containing fundamental data structures and state management.

This module provides:
- AppState, DataLoadMode, AppStateManager: Application state management
- Polygon, rescale_points_vectorized: Polygon geometry utilities
- ImageChannel, CHANNEL_COLORS: Image channel data structures
"""

from .state import AppState, DataLoadMode, AppStateManager
from .polygon import Polygon, rescale_points_vectorized
from .channel import ImageChannel, CHANNEL_COLORS

# Set canonical module paths to avoid Sphinx cross-reference ambiguity
AppState.__module__ = "cellpick.app.core.state"
DataLoadMode.__module__ = "cellpick.app.core.state"
AppStateManager.__module__ = "cellpick.app.core.state"
Polygon.__module__ = "cellpick.app.core.polygon"
ImageChannel.__module__ = "cellpick.app.core.channel"

__all__ = [
    "AppState",
    "DataLoadMode",
    "AppStateManager",
    "Polygon",
    "rescale_points_vectorized",
    "ImageChannel",
    "CHANNEL_COLORS",
]
