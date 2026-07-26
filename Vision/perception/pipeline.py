"""End-to-end vision pipeline: detect people in a frame, project to hall coordinates,
map to seats, and emit person_detected events.
"""

from perception.events import make_person_detected
from perception.homography import pixel_to_world
from perception.seat_mapping import nearest_seat


def foot_point(bbox):
    """Bottom-center of a bounding box — where a person meets the floor."""
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, y2


def process_frame(frame, detector, homography, seats):
    """Detect people in `frame` and return a list of person_detected events."""
    events = []
    for det in detector.detect(frame):
        u, v = foot_point(det["bbox"])
        x, y = pixel_to_world(homography, u, v)
        seat = nearest_seat(x, y, seats)
        events.append(make_person_detected(x, y, seat, det["confidence"]))
    return events
