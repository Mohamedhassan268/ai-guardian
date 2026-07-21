import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.detection import PersonDetector


class _StubBackend:
    """Stubs only .predict() — PersonDetector never touches ultralytics/torch
    directly, so this is enough to test its filtering logic without either installed."""

    def __init__(self, detections):
        self._detections = detections

    def predict(self, frame):
        return self._detections


def test_detect_filters_to_person_class_above_threshold():
    raw = [
        (0, 0, 10, 10, 0.9, 0),  # person, high confidence -> kept
        (0, 0, 10, 10, 0.9, 2),  # car, high confidence -> dropped (wrong class)
        (0, 0, 10, 10, 0.3, 0),  # person, low confidence -> dropped (below threshold)
    ]
    detector = PersonDetector(backend=_StubBackend(raw), confidence_threshold=0.5)

    detections = detector.detect(frame=None)

    assert detections == [{"bbox": (0, 0, 10, 10), "confidence": 0.9}]


def test_detect_returns_empty_list_for_no_detections():
    """Failure case: nothing detected in a frame must not crash."""
    detector = PersonDetector(backend=_StubBackend([]))
    assert detector.detect(frame=None) == []


def test_detect_keeps_every_surviving_detection_not_just_the_first():
    raw = [
        (0, 0, 10, 10, 0.9, 0),
        (20, 20, 30, 30, 0.8, 0),
        (40, 40, 50, 50, 0.7, 0),
    ]
    detector = PersonDetector(backend=_StubBackend(raw), confidence_threshold=0.5)

    detections = detector.detect(frame=None)

    assert detections == [
        {"bbox": (0, 0, 10, 10), "confidence": 0.9},
        {"bbox": (20, 20, 30, 30), "confidence": 0.8},
        {"bbox": (40, 40, 50, 50), "confidence": 0.7},
    ]


def test_detect_keeps_detection_exactly_at_threshold():
    raw = [(0, 0, 10, 10, 0.5, 0)]
    detector = PersonDetector(backend=_StubBackend(raw), confidence_threshold=0.5)

    assert detector.detect(frame=None) == [{"bbox": (0, 0, 10, 10), "confidence": 0.5}]
