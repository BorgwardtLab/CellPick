"""
Image channel data structures for multi-channel fluorescence microscopy.

This module provides the ImageChannel dataclass for managing individual
image channels with visibility, color, and saturation control.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


# Default channel colors optimized for fluorescence microscopy on black background
# Inspired by DAPI, FITC, TRITC, Cy5 conventions + high contrast colors
CHANNEL_COLORS = [
    np.array([70, 130, 255]),  # Blue (DAPI/nuclei style)
    np.array([0, 255, 100]),  # Green (FITC style)
    np.array([255, 70, 70]),  # Red (TRITC style)
    np.array([255, 0, 255]),  # Magenta (Cy5 style)
    np.array([0, 255, 255]),  # Cyan
    np.array([255, 255, 0]),  # Yellow
]


@dataclass
class ImageChannel:
    """
    Data class representing an image channel.

    Attributes
    ----------
    image_data : np.ndarray
        The image data for the channel.
    name : str
        The name of the channel.
    visible : bool
        Whether the channel is visible.
    color_idx : int
        Index for the display color.
    custom_color : Optional[np.ndarray]
        Custom RGB color array. If provided, overrides color_idx.
    saturation_min : float
        Minimum saturation level (0-1 scale, maps to percentile of image).
    saturation_max : float
        Maximum saturation level (0-1 scale, maps to percentile of image).
    _raw_min : Optional[float]
        Cached minimum value of raw image data.
    _raw_max : Optional[float]
        Cached maximum value of raw image data.
    _processed_rgb : Optional[np.ndarray]
        Cached RGB contribution after saturation adjustment, ready to sum.
    _cache_sat_min : float
        Saturation min value used when cache was computed.
    _cache_sat_max : float
        Saturation max value used when cache was computed.
    """

    image_data: np.ndarray
    name: str
    visible: bool = True
    color_idx: int = 0
    custom_color: Optional[np.ndarray] = None
    saturation_min: float = field(default=0.0, repr=False)
    saturation_max: float = field(default=1.0, repr=False)
    _raw_min: Optional[float] = field(default=None, repr=False)
    _raw_max: Optional[float] = field(default=None, repr=False)
    _processed_rgb: Optional[np.ndarray] = field(default=None, repr=False)
    _cache_sat_min: float = field(default=-1.0, repr=False)
    _cache_sat_max: float = field(default=-1.0, repr=False)

    def get_raw_range(self) -> Tuple[float, float]:
        """
        Get the minimum and maximum values of raw image data.

        Computes and caches the range on first call.

        Returns
        -------
        Tuple[float, float]
            The (min, max) values of the raw image data.
        """
        if self._raw_min is None or self._raw_max is None:
            self._raw_min = float(np.min(self.image_data))
            self._raw_max = float(np.max(self.image_data))
        return self._raw_min, self._raw_max

    def compute_auto_saturation(
        self, percentile_low: float = 1.0, percentile_high: float = 99.0
    ) -> Tuple[float, float]:
        """
        Compute automatic saturation values based on percentiles.

        Parameters
        ----------
        percentile_low : float, optional
            Lower percentile for minimum saturation (default is 1.0).
        percentile_high : float, optional
            Upper percentile for maximum saturation (default is 99.0).

        Returns
        -------
        Tuple[float, float]
            The (sat_min, sat_max) values in 0-1 scale.
        """
        raw_min, raw_max = self.get_raw_range()
        raw_range = raw_max - raw_min

        if raw_range < 1e-6:
            return 0.0, 1.0

        # Compute percentiles on the raw data
        p_low = np.percentile(self.image_data, percentile_low)
        p_high = np.percentile(self.image_data, percentile_high)

        # Convert to 0-1 scale relative to data range
        sat_min = (p_low - raw_min) / raw_range
        sat_max = (p_high - raw_min) / raw_range

        return float(np.clip(sat_min, 0, 1)), float(np.clip(sat_max, 0, 1))

    def get_processed_rgb(self) -> np.ndarray:
        """
        Get the RGB contribution for this channel.

        Uses cached result if saturation settings haven't changed.

        Returns
        -------
        np.ndarray
            The RGB contribution array with shape (H, W, 3).
        """
        # Check if cache is valid
        if (
            self._processed_rgb is not None
            and abs(self._cache_sat_min - self.saturation_min) < 1e-9
            and abs(self._cache_sat_max - self.saturation_max) < 1e-9
        ):
            return self._processed_rgb

        # Recompute
        raw_min, raw_max = self.get_raw_range()
        raw_range = raw_max - raw_min

        if raw_range < 1e-6:
            # Constant image
            channel_data = np.zeros_like(self.image_data, dtype=np.float32)
        else:
            # Normalize to 0-1 based on raw range
            channel_data = (self.image_data.astype(np.float32) - raw_min) / raw_range

            # Apply saturation windowing: remap sat_min-sat_max to 0-1
            sat_range = self.saturation_max - self.saturation_min
            if sat_range < 1e-6:
                sat_range = 1e-6
            channel_data = (channel_data - self.saturation_min) / sat_range
            channel_data = np.clip(channel_data, 0, 1)

        # Apply color
        if self.custom_color is not None:
            color = self.custom_color
        else:
            color = CHANNEL_COLORS[self.color_idx % len(CHANNEL_COLORS)]

        # Pre-multiply with color to get RGB contribution (scale to 0-255)
        self._processed_rgb = channel_data[..., None] * color[None, None, :]
        self._cache_sat_min = self.saturation_min
        self._cache_sat_max = self.saturation_max

        return self._processed_rgb

    def invalidate_cache(self) -> None:
        """
        Invalidate all caches.

        Call this when image_data or color changes.
        """
        self._raw_min = None
        self._raw_max = None
        self._processed_rgb = None
        self._cache_sat_min = -1.0
        self._cache_sat_max = -1.0
