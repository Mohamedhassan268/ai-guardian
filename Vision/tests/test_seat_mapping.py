import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.seat_mapping import load_seats, nearest_seat

SEATS = [
    {"seat_id": "R01-L01", "x": 0.0, "y": 0.0},
    {"seat_id": "R01-C01", "x": 5.0, "y": 0.0},
    {"seat_id": "R02-L01", "x": 0.0, "y": 3.0},
]


def test_nearest_seat_picks_closest():
    assert nearest_seat(0.1, 0.1, SEATS) == "R01-L01"
    assert nearest_seat(4.9, 0.2, SEATS) == "R01-C01"
    assert nearest_seat(0.2, 2.8, SEATS) == "R02-L01"


def test_nearest_seat_returns_none_for_empty_seats():
    """Failure case: no seats to match against must not crash."""
    assert nearest_seat(0.0, 0.0, []) is None


def test_load_seats_matches_real_seat_map():
    """Lightweight integration check against the real committed seat map."""
    seats = load_seats()
    assert len(seats) == 99

    r01_l01 = next(s for s in seats if s["seat_id"] == "R01-L01")
    assert r01_l01["x"] == 0.53
    assert r01_l01["y"] == 2.8
