import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.evaluate import (
    coverage_metrics,
    evaluate_all_scenes,
    evaluate_scene,
    fit_calibration_homography,
)

# Identity pixel->world mapping, so a person's foot point in pixels IS their hall (x, y).
# Keeps the geometry trivially predictable and isolates what's under test: the
# scene -> pipeline -> seat comparison logic, not the homography fit itself.
_IDENTITY_CORNERS = [[0, 0], [100, 0], [0, 100], [100, 100]]

SEATS = [
    {"seat_id": "R01-L01", "x": 10.0, "y": 20.0},
    {"seat_id": "R01-C01", "x": 60.0, "y": 20.0},
    {"seat_id": "R02-L01", "x": 10.0, "y": 80.0},
]


def _ground_truth(scenes, visibility=None):
    return {
        "camera_calibration": {
            "correspondences": [
                {"pixel": p, "world": w}
                for p, w in zip(_IDENTITY_CORNERS, _IDENTITY_CORNERS)
            ]
        },
        "seat_visibility": (
            {s["seat_id"]: {"in_frame": True} for s in SEATS}
            if visibility is None
            else visibility  # an explicitly-passed {} must be honored, not defaulted
        ),
        "scenes": scenes,
    }


def _person(seat_id, true_x, true_y, bbox, in_frame=True):
    return {
        "seat_id": seat_id, "true_x": true_x, "true_y": true_y, "true_z": 0.45,
        "bbox_px": bbox, "in_frame": in_frame,
    }


def _scene(scene_id, people, scene_type="single"):
    return {"scene_id": scene_id, "type": scene_type, "people": people}


def test_correct_seat_rate_is_one_when_geometry_lands_on_the_true_seat():
    # bbox foot point = bottom-center = (10, 20) -> exactly seat R01-L01 under identity.
    scene = _scene("single_R01-L01", [_person("R01-L01", 10.0, 20.0, [5, 0, 15, 20])])
    ground_truth = _ground_truth([scene])
    H = fit_calibration_homography(ground_truth)

    results = evaluate_all_scenes(ground_truth, H, SEATS)

    assert results["overall"]["n"] == 1
    assert results["overall"]["correct_seat_rate"] == 1.0
    assert results["overall"]["median_position_error_m"] == pytest.approx(0.0, abs=1e-6)


def test_wrong_seat_is_flagged_incorrect():
    """A person labelled as one seat whose pixels land on a different seat must count
    as incorrect, not silently pass."""
    # Foot point (60, 20) is seat R01-C01, but the person is labelled R01-L01.
    scene = _scene("single_mislabelled", [_person("R01-L01", 10.0, 20.0, [55, 0, 65, 20])])
    ground_truth = _ground_truth([scene])
    H = fit_calibration_homography(ground_truth)

    results = evaluate_all_scenes(ground_truth, H, SEATS)

    assert results["overall"]["correct_seat_rate"] == 0.0
    assert results["per_person"][0]["predicted_seat"] == "R01-C01"
    assert results["per_person"][0]["correct"] is False


def test_out_of_frame_people_are_excluded_from_the_denominator():
    scene = _scene(
        "multi_01",
        [
            _person("R01-L01", 10.0, 20.0, [5, 0, 15, 20]),
            _person("R02-L01", 10.0, 80.0, None, in_frame=False),
        ],
        scene_type="multi",
    )
    ground_truth = _ground_truth([scene])
    H = fit_calibration_homography(ground_truth)

    results = evaluate_all_scenes(ground_truth, H, SEATS)

    assert results["overall"]["n"] == 1  # the out-of-frame person is not scored
    assert results["overall"]["correct_seat_rate"] == 1.0


def test_position_error_matches_a_known_offset():
    """Foot point (13, 24) vs true (10, 20) is a 3-4-5 triangle, so the position error
    must be exactly 5.0."""
    scene = _scene("single_offset", [_person("R01-L01", 10.0, 20.0, [10, 0, 16, 24])])
    ground_truth = _ground_truth([scene])
    H = fit_calibration_homography(ground_truth)

    results = evaluate_all_scenes(ground_truth, H, SEATS)

    assert results["overall"]["median_position_error_m"] == pytest.approx(5.0, abs=1e-6)


def test_single_and_multi_are_broken_out_separately():
    scenes = [
        _scene("single_a", [_person("R01-L01", 10.0, 20.0, [5, 0, 15, 20])]),
        _scene(
            "multi_a",
            [_person("R01-C01", 60.0, 20.0, [55, 0, 65, 20])],
            scene_type="multi",
        ),
    ]
    ground_truth = _ground_truth(scenes)
    H = fit_calibration_homography(ground_truth)

    results = evaluate_all_scenes(ground_truth, H, SEATS)

    assert results["single"]["n"] == 1
    assert results["multi"]["n"] == 1
    assert results["overall"]["n"] == 2


def test_coverage_metrics_counts_in_frame_seats():
    ground_truth = _ground_truth(
        [],
        visibility={
            "R01-L01": {"in_frame": False},
            "R01-C01": {"in_frame": True},
            "R02-L01": {"in_frame": True},
        },
    )

    coverage = coverage_metrics(ground_truth)

    assert coverage["in_frame_seats"] == 2
    assert coverage["total_seats"] == 3
    assert coverage["frame_coverage_rate"] == pytest.approx(2 / 3)


def test_empty_dataset_summarizes_to_zeros_without_crashing():
    """Failure case: a dataset with no scored people must not divide by zero."""
    ground_truth = _ground_truth([], visibility={})
    H = fit_calibration_homography(ground_truth)

    results = evaluate_all_scenes(ground_truth, H, SEATS)
    coverage = coverage_metrics(ground_truth)

    assert results["overall"]["n"] == 0
    assert results["overall"]["correct_seat_rate"] == 0.0
    assert coverage["frame_coverage_rate"] == 0.0


def test_evaluate_scene_returns_one_result_per_in_frame_person():
    scene = _scene(
        "multi_b",
        [
            _person("R01-L01", 10.0, 20.0, [5, 0, 15, 20]),
            _person("R01-C01", 60.0, 20.0, [55, 0, 65, 20]),
        ],
        scene_type="multi",
    )
    ground_truth = _ground_truth([scene])
    H = fit_calibration_homography(ground_truth)

    results = evaluate_scene(scene, H, SEATS)

    assert len(results) == 2
    assert [r["true_seat"] for r in results] == ["R01-L01", "R01-C01"]
    assert all(r["correct"] for r in results)
