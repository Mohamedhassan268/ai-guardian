"""Map camera pixel coordinates to hall (x, y) coordinates via a homography.

CLAUDE.md commits Vision to OpenCV, so this uses cv2.findHomography (point-
correspondence based) rather than a hand-rolled DLT implementation. Real calibration —
getting actual pixel<->world correspondences from a mounted camera — needs a real or
rendered frame and isn't available yet; this module just provides the math.
"""

import cv2
import numpy as np


def compute_homography(pixel_points, world_points, method=0):
    """Fit a 3x3 homography mapping pixel (u, v) to hall (x, y) from >=4 point
    correspondences.

    `method` is passed through to cv2.findHomography (0 = plain least-squares,
    appropriate for exact/noise-free points; pass cv2.RANSAC once real, possibly
    noisy calibration points exist — no interface change needed then).
    """
    pixel_points = np.asarray(pixel_points, dtype=np.float64)
    world_points = np.asarray(world_points, dtype=np.float64)
    if len(pixel_points) != len(world_points):
        raise ValueError(
            f"pixel_points and world_points must be the same length "
            f"({len(pixel_points)} != {len(world_points)})"
        )
    if len(pixel_points) < 4:
        raise ValueError("Need at least 4 point correspondences to compute a homography")

    H, _ = cv2.findHomography(pixel_points, world_points, method=method)
    if H is None:
        raise ValueError("cv2.findHomography failed to compute a homography for these points")
    return H


def pixel_to_world(H, u, v):
    """Apply a homography to one pixel point, returning (x, y) in hall coordinates."""
    point = H @ np.array([u, v, 1.0])
    if abs(point[2]) < 1e-9:
        raise ValueError(f"Degenerate homography: point ({u}, {v}) maps to infinity")
    return float(point[0] / point[2]), float(point[1] / point[2])
