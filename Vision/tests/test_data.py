import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.data import iter_people, load_calibration_points, load_ground_truth

GROUND_TRUTH = {
    "camera_calibration": {
        "correspondences": [
            {"pixel": [0, 0], "world": [0.5, 3.0]},
            {"pixel": [1920, 0], "world": [11.7, 3.0]},
            {"pixel": [0, 1080], "world": [0.5, 14.5]},
            {"pixel": [1920, 1080], "world": [11.7, 14.5]},
        ]
    },
    "seat_visibility": {
        "R01-L01": {"in_frame": False},
        "R06-C03": {"in_frame": True},
    },
    "scenes": [
        {
            "scene_id": "single_R06-C03",
            "type": "single",
            "people": [
                {"seat_id": "R06-C03", "true_x": 6.12, "true_y": 8.8, "true_z": 0.45,
                 "bbox_px": [900, 400, 960, 560], "in_frame": True}
            ],
        },
        {
            "scene_id": "multi_01",
            "type": "multi",
            "people": [
                {"seat_id": "R06-C03", "true_x": 6.12, "true_y": 8.8, "true_z": 0.45,
                 "bbox_px": [900, 400, 960, 560], "in_frame": True},
                {"seat_id": "R01-L01", "true_x": 0.53, "true_y": 2.8, "true_z": 0.45,
                 "bbox_px": None, "in_frame": False},
            ],
        },
    ],
}


def test_load_ground_truth_reads_file(tmp_path):
    path = tmp_path / "ground_truth.json"
    path.write_text(json.dumps(GROUND_TRUTH), encoding="utf-8")

    loaded = load_ground_truth(str(path))

    assert loaded["scenes"][0]["scene_id"] == "single_R06-C03"


def test_load_ground_truth_missing_file_names_the_generator(tmp_path):
    """Failure case: the dataset doesn't exist until the Blender script has been run,
    so the error must say so rather than surfacing a bare OSError."""
    missing = tmp_path / "nope.json"

    with pytest.raises(FileNotFoundError, match="render_vision_dataset.py"):
        load_ground_truth(str(missing))


def test_calibration_points_stay_in_matching_order():
    pixel_points, world_points = load_calibration_points(GROUND_TRUTH)

    assert len(pixel_points) == len(world_points) == 4
    assert pixel_points[0] == [0, 0]
    assert world_points[0] == [0.5, 3.0]
    assert pixel_points[3] == [1920, 1080]
    assert world_points[3] == [11.7, 14.5]


def test_iter_people_flattens_single_and_multi_scenes():
    pairs = list(iter_people(GROUND_TRUTH))

    assert len(pairs) == 3  # 1 from the single scene + 2 from the multi scene
    scene_ids = [scene["scene_id"] for scene, _ in pairs]
    assert scene_ids == ["single_R06-C03", "multi_01", "multi_01"]
