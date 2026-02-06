"""
Backward compatibility module for components.

This module re-exports all classes from the new core module structure
to maintain backward compatibility with existing imports.

The actual implementations are now in:
- cellpick.app.core.state: AppState, DataLoadMode, AppStateManager
- cellpick.app.core.polygon: Polygon, rescale_points_vectorized
- cellpick.app.core.channel: ImageChannel, CHANNEL_COLORS
"""

# Re-export from new module structure for backward compatibility
from .core.channel import CHANNEL_COLORS, ImageChannel
from .core.polygon import Polygon, rescale_points_vectorized
from .core.state import AppState, DataLoadMode, AppStateManager

__all__ = [
    "CHANNEL_COLORS",
    "ImageChannel",
    "Polygon",
    "rescale_points_vectorized",
    "AppState",
    "DataLoadMode",
    "AppStateManager",
]
