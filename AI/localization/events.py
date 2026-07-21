"""Emit localization results as the shared Guardian AI event schema (see CLAUDE.md).

This is the contract Phase 5 fusion consumes, so the localization module produces it
directly rather than leaving translation to a downstream caller.
"""

import uuid
from datetime import datetime, timezone


def make_position_estimate(x, y, seat, error_m, confidence, source_module="localization"):
    """Build one position_estimate event matching the CLAUDE.md shared JSON schema."""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        + "Z",
        "source_module": source_module,
        "event_type": "position_estimate",
        "position": {"x": float(x), "y": float(y), "seat": seat, "error_m": float(error_m)},
        "signal": None,
        "confidence": float(confidence),
        "evidence_ref": None,
    }
