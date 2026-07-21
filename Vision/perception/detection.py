"""Person detection, backed by YOLOv8 (ultralytics) but decoupled from it.

The real ultralytics model is only ever loaded inside _UltralyticsBackend, and only on
first use — not at import time. PersonDetector talks to a small custom `.predict()`
contract instead of ultralytics' native Results API, so tests can inject a trivial stub
backend without ultralytics/torch being installed at all.
"""

PERSON_CLASS_ID = 0  # COCO class index for "person"


class _UltralyticsBackend:
    """Real detection backend — loads YOLOv8 lazily so importing this module never
    requires ultralytics/torch to be installed."""

    def __init__(self, weights="yolov8n.pt"):
        from ultralytics import YOLO

        self.model = YOLO(weights)

    def predict(self, frame):
        """Return raw detections as (x1, y1, x2, y2, confidence, class_id) tuples."""
        results = self.model(frame, verbose=False)[0]
        return [
            (*[float(v) for v in box.xyxy[0]], float(box.conf[0]), int(box.cls[0]))
            for box in results.boxes
        ]


class PersonDetector:
    def __init__(self, backend=None, confidence_threshold=0.5):
        self.backend = backend if backend is not None else _UltralyticsBackend()
        self.confidence_threshold = confidence_threshold

    def detect(self, frame):
        """Return person-class detections above the confidence threshold, as
        [{"bbox": (x1, y1, x2, y2), "confidence": c}, ...]."""
        detections = []
        for x1, y1, x2, y2, confidence, class_id in self.backend.predict(frame):
            if class_id != PERSON_CLASS_ID or confidence < self.confidence_threshold:
                continue
            detections.append({"bbox": (x1, y1, x2, y2), "confidence": confidence})
        return detections
