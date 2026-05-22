"""Phase 1 tests for image channel processing helpers."""

import numpy as np

from cellpick.app.core.channel import ImageChannel


def test_get_raw_range_and_cache() -> None:
    image = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    channel = ImageChannel(image_data=image, name="ch")

    raw_min, raw_max = channel.get_raw_range()
    assert raw_min == 1.0
    assert raw_max == 4.0

    raw_min2, raw_max2 = channel.get_raw_range()
    assert raw_min2 == raw_min
    assert raw_max2 == raw_max


def test_auto_saturation_constant_image_defaults() -> None:
    image = np.ones((3, 3), dtype=np.float32)
    channel = ImageChannel(image_data=image, name="ch")

    sat_min, sat_max = channel.compute_auto_saturation()
    assert sat_min == 0.0
    assert sat_max == 1.0


def test_processed_rgb_shape_and_cache_reuse() -> None:
    image = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)
    channel = ImageChannel(image_data=image, name="ch")

    rgb1 = channel.get_processed_rgb()
    assert rgb1.shape == (2, 2, 3)
    assert np.all(rgb1 >= 0.0)

    rgb2 = channel.get_processed_rgb()
    assert rgb1 is rgb2


def test_invalidate_cache_resets_and_recomputes() -> None:
    image = np.array([[0.0, 1.0], [2.0, 3.0]], dtype=np.float32)
    channel = ImageChannel(image_data=image, name="ch")

    rgb1 = channel.get_processed_rgb()
    channel.invalidate_cache()
    rgb2 = channel.get_processed_rgb()

    assert rgb1 is not rgb2
