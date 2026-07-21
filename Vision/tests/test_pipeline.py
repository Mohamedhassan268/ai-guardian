import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.homography import compute_homography
from perception.pipeline import process_frame

SEATS = [
    {"seat_id": "R01-L01", "x": 5.0, "y": 20.0},
    {"seat_id": "R01-C01", "x": 50.0, "y": 20.0},
    {"seat_id": "R02-L01", "x": 5.0, "y": 60.0},
]


class _StubDetector:
    def __init__(self, detections):
        self._detections = detections

    def detect(self, frame):
        return self._detections


def _identity_homography():
    """A homography where pixel coordinates equal world coordinates, so the seat
    mapping can be checked without depending on a real calibration."""
    corners = [(0, 0), (100, 0), (0, 100), (100, 100)]
    return compute_homography(corners, corners)


def test_process_frame_produces_correctly_seated_events():
    detector = _StubDetector([{"bbox": (0, 0, 10, 20), "confidence": 0.9}])
    homography = _identity_homography()

    events = process_frame(frame=None, detector=detector, homography=homography, seats=SEATS)

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "person_detected"
    assert event["position"]["seat"] == "R01-L01"
    assert event["position"]["x"] == pytest.approx(5.0, abs=1e-6)
    assert event["position"]["y"] == pytest.approx(20.0, abs=1e-6)
    assert event["confidence"] == 0.9


def test_process_frame_returns_empty_list_for_no_detections():
    """Failure case: no detections in the frame must not crash."""
    detector = _StubDetector([])
    homography = _identity_homography()

    events = process_frame(frame=None, detector=detector, homography=homography, seats=SEATS)

    assert events == []


def test_process_frame_emits_one_event_per_detection():
    """Multiple detections must all survive, not just the first/last."""
    detector = _StubDetector(
        [
            {"bbox": (0, 0, 10, 20), "confidence": 0.9},  # foot point (5, 20) -> R01-L01
            {"bbox": (45, 10, 55, 20), "confidence": 0.6},  # foot point (50, 20) -> R01-C01
        ]
    )
    homography = _identity_homography()

    events = process_frame(frame=None, detector=detector, homography=homography, seats=SEATS)

    assert len(events) == 2
    assert [e["position"]["seat"] for e in events] == ["R01-L01", "R01-C01"]
    assert [e["confidence"] for e in events] == [0.9, 0.6]
