import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from perception.events import make_person_detected


def test_event_has_all_required_schema_keys():
    event = make_person_detected(x=3.2, y=5.1, seat="R04-C03", confidence=0.87)

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

    assert event["source_module"] == "vision"
    assert event["event_type"] == "person_detected"
    assert event["position"] == {"x": 3.2, "y": 5.1, "seat": "R04-C03", "error_m": None}
    assert event["confidence"] == 0.87
    assert event["signal"] is None
    assert event["evidence_ref"] is None


def test_event_timestamp_is_utc_iso_with_milliseconds():
    event = make_person_detected(x=0, y=0, seat="R01-L01", confidence=1.0)
    ts = event["timestamp_utc"]
    assert ts.endswith("Z")
    assert "." in ts  # millisecond precision present
