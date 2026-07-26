"""Map a hall (x, y) position to the nearest seat in the shared seat map.

Canonical seat coordinates come from `Shared/seat_map.json` (single source of truth),
same as AI/localization/data.py::load_seat_map.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))          # Vision/perception
_REPO = os.path.dirname(os.path.dirname(_HERE))             # repo root

SEAT_MAP = os.path.join(_REPO, "Shared", "seat_map.json")


def load_seats(path=SEAT_MAP):
    """Return the list of seat dicts from the canonical seat map."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["seats"]


def nearest_seat(x, y, seats):
    """Return the seat_id closest to (x, y) by 2D distance, or None if seats is empty."""
    best_id, best_dist = None, float("inf")
    for seat in seats:
        dist = (seat["x"] - x) ** 2 + (seat["y"] - y) ** 2
        if dist < best_dist:
            best_id, best_dist = seat["seat_id"], dist
    return best_id
