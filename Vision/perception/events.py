"""Emit vision detections as the shared Guardian AI event schema (see CLAUDE.md).

This is the contract Phase 5 fusion consumes, so the vision module produces it
directly rather than leaving translation to a downstream caller.
"""

import uuid
from datetime import datetime, timezone


def make_person_detected(x, y, seat, confidence, source_module="vision"):
    """Build one person_detected event matching the CLAUDE.md shared JSON schema."""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        + "Z",
        "source_module": source_module,
        "event_type": "person_detected",
        # error_m has no meaning here — unlike localization, there's no ground truth
        # to compute an error against at inference time.
        "position": {"x": float(x), "y": float(y), "seat": seat, "error_m": None},
        "signal": None,
        "confidence": float(confidence),
        "evidence_ref": None,
    }
