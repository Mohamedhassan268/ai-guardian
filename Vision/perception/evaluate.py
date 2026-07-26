"""Geometry evaluation for the synthetic vision dataset.

This measures ONLY the geometry: given each person's exact ground-truth pixel bounding
box (from Blender's projection math, not object detection), does
homography + nearest_seat recover the seat the person was actually placed in?

Detection is deliberately not exercised here — the placeholder people are bare
primitives a real-photo-trained YOLO would not detect, so running it now would just add
noise (see status.md's Vision AI blocker). `_GroundTruthDetector` is the seam where a
real detector goes later: swap it for perception.detection.PersonDetector wired to the
rendered PNGs, and this same code produces an end-to-end (detection + geometry) number.
"""

import numpy as np

from perception import homography
from perception import pipeline
from perception.data import load_calibration_points


class _GroundTruthDetector:
    """Feeds recorded ground-truth bboxes through the real pipeline in place of a
    detector — so evaluate reuses process_frame unchanged instead of reimplementing the
    pixel->world->seat chain. Only in-frame people are 'detected'."""

    def __init__(self, people):
        self._detections = [
            {"bbox": p["bbox_px"], "confidence": 1.0} for p in people if p["in_frame"]
        ]

    def detect(self, frame):
        return self._detections


def fit_calibration_homography(ground_truth):
    """Fit the pixel->hall homography once from the exported floor calibration points."""
    pixel_points, world_points = load_calibration_points(ground_truth)
    return homography.compute_homography(pixel_points, world_points)


def coverage_metrics(ground_truth):
    """How many of the canonical seats are actually inside the camera frame — a real
    limitation of the fixed camera, reported (not asserted)."""
    visibility = ground_truth["seat_visibility"]
    in_frame = sum(1 for v in visibility.values() if v["in_frame"])
    total = len(visibility)
    return {
        "in_frame_seats": in_frame,
        "total_seats": total,
        "frame_coverage_rate": in_frame / total if total else 0.0,
    }


def evaluate_scene(scene, homography_matrix, seats):
    """Run the real pipeline on one scene's ground-truth people. Returns a list of
    per-person result dicts (true vs predicted seat, position error) for the in-frame
    people, in the same order process_frame emits them."""
    people_in_frame = [p for p in scene["people"] if p["in_frame"]]
    detector = _GroundTruthDetector(scene["people"])
    events = pipeline.process_frame(None, detector, homography_matrix, seats)

    # The zip below pairs people to events positionally. That holds only because
    # process_frame emits exactly one event per detection, in order — if it ever starts
    # dropping detections, silently misaligned pairs would produce plausible but wrong
    # accuracy numbers, so fail loudly instead.
    if len(events) != len(people_in_frame):
        raise ValueError(
            f"{scene['scene_id']}: {len(events)} events for {len(people_in_frame)} "
            "in-frame people — cannot pair results positionally"
        )

    results = []
    for person, event in zip(people_in_frame, events):
        pred_x = event["position"]["x"]
        pred_y = event["position"]["y"]
        error = ((pred_x - person["true_x"]) ** 2 + (pred_y - person["true_y"]) ** 2) ** 0.5
        results.append({
            "scene_id": scene["scene_id"],
            "scene_type": scene["type"],
            "true_seat": person["seat_id"],
            "predicted_seat": event["position"]["seat"],
            "correct": event["position"]["seat"] == person["seat_id"],
            "position_error_m": error,
        })
    return results


def evaluate_all_scenes(ground_truth, homography_matrix, seats):
    """Aggregate geometry metrics across all scenes, with a single/multi breakdown.

    position_error_m is non-zero by design even though the pixel input is exact: the
    homography is an approximate planar fit from a handful of calibration points, and the
    placeholders' feet sit at bench height (z=0.45) while the calibration plane is the
    true floor (z=0) — a real, expected parallax, not a bug.
    """
    per_person = []
    for scene in ground_truth["scenes"]:
        per_person.extend(evaluate_scene(scene, homography_matrix, seats))

    return {
        "overall": _summarize(per_person),
        "single": _summarize([r for r in per_person if r["scene_type"] == "single"]),
        "multi": _summarize([r for r in per_person if r["scene_type"] == "multi"]),
        "per_person": per_person,
    }


def _summarize(results):
    """Correct-seat rate and position-error stats over a list of per-person results."""
    n = len(results)
    if n == 0:
        return {
            "n": 0,
            "correct_seat_rate": 0.0,
            "median_position_error_m": 0.0,
            "mean_position_error_m": 0.0,
            "max_position_error_m": 0.0,
        }
    errors = np.array([r["position_error_m"] for r in results])
    correct = sum(1 for r in results if r["correct"])
    return {
        "n": n,
        "correct_seat_rate": correct / n,
        "median_position_error_m": float(np.median(errors)),
        "mean_position_error_m": float(np.mean(errors)),
        "max_position_error_m": float(np.max(errors)),
    }
