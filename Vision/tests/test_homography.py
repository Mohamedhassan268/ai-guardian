import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.homography import compute_homography, pixel_to_world

# A known scale+translate mapping (a special case of a projective homography) so the
# expected world coordinates can be computed directly, without depending on the fit.
_SCALE_U, _OFFSET_X = 0.01, 1.0
_SCALE_V, _OFFSET_Y = 0.02, 2.0


def _world_of(u, v):
    return (_SCALE_U * u + _OFFSET_X, _SCALE_V * v + _OFFSET_Y)


def test_homography_recovers_known_mapping_from_four_points():
    pixel_corners = [(0, 0), (1920, 0), (0, 1080), (1920, 1080)]
    world_corners = [_world_of(u, v) for u, v in pixel_corners]

    H = compute_homography(pixel_corners, world_corners)

    x, y = pixel_to_world(H, 960, 540)
    expected_x, expected_y = _world_of(960, 540)
    assert x == pytest.approx(expected_x, abs=1e-6)
    assert y == pytest.approx(expected_y, abs=1e-6)


def test_homography_recovers_known_mapping_from_overdetermined_points():
    """Six exact correspondences (more than the minimum 4) should still fit exactly."""
    pixel_points = [(0, 0), (1920, 0), (0, 1080), (1920, 1080), (500, 300), (1400, 800)]
    world_points = [_world_of(u, v) for u, v in pixel_points]

    H = compute_homography(pixel_points, world_points)

    x, y = pixel_to_world(H, 500, 300)
    expected_x, expected_y = _world_of(500, 300)
    assert x == pytest.approx(expected_x, abs=1e-6)
    assert y == pytest.approx(expected_y, abs=1e-6)


def test_compute_homography_requires_at_least_four_points():
    """Failure case: fewer than 4 correspondences can't determine a homography."""
    pixel_points = [(0, 0), (1920, 0), (0, 1080)]
    world_points = [_world_of(u, v) for u, v in pixel_points]

    with pytest.raises(ValueError):
        compute_homography(pixel_points, world_points)


def test_compute_homography_requires_matching_lengths():
    """Failure case: mismatched pixel/world point counts can't be paired."""
    pixel_points = [(0, 0), (1920, 0), (0, 1080), (1920, 1080)]
    world_points = [_world_of(u, v) for u, v in pixel_points[:3]]  # one fewer

    with pytest.raises(ValueError):
        compute_homography(pixel_points, world_points)


def test_pixel_to_world_raises_on_degenerate_homography():
    """Failure case: a degenerate homography maps a point to infinity (w=0)."""
    degenerate_h = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]])

    with pytest.raises(ValueError):
        pixel_to_world(degenerate_h, 5, 5)
