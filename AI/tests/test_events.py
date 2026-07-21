import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.events import make_position_estimate


def test_event_has_all_required_schema_keys():
    event = make_position_estimate(x=3.2, y=5.1, seat="R04-S7", error_m=1.2, confidence=0.94)

    for key in [
        "event_id",
        "timestamp_utc",
        "source_module",
        "event_type",
        "position",
        "signal",
        "confidence",
        "evidence_ref",
    ]:
        assert key in event

    assert event["source_module"] == "localization"
    assert event["event_type"] == "position_estimate"
    assert event["position"] == {"x": 3.2, "y": 5.1, "seat": "R04-S7", "error_m": 1.2}
    assert event["confidence"] == 0.94


def test_event_timestamp_is_utc_iso_with_milliseconds():
    event = make_position_estimate(x=0, y=0, seat="R01-L01", error_m=0, confidence=1.0)
    ts = event["timestamp_utc"]
    assert ts.endswith("Z")
    assert "." in ts  # millisecond precision present
