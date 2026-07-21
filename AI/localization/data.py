"""Load and reshape the simulated RSSI dataset for localization.

The raw CSV (`AI/training_data/rssi_dataset.csv`) is in long format: one row per
(seat, node, sample) with a single `rssi_dbm` reading. Localization needs one row
per observation with all four node readings side by side, so we pivot long -> wide.

Canonical seat coordinates come from `Shared/seat_map.json` (single source of truth),
not from the CSV's duplicated `true_x`/`true_y` columns.
"""

import json
import os

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))          # AI/localization
_REPO = os.path.dirname(os.path.dirname(_HERE))             # repo root

DATA_CSV = os.path.join(_REPO, "AI", "training_data", "rssi_dataset.csv")
SEAT_MAP = os.path.join(_REPO, "Shared", "seat_map.json")
FINGERPRINT_JSON = os.path.join(_REPO, "AI", "training_data", "rssi_fingerprint.json")

# Fixed node order. Real hardware must map to these same feature slots later, so the
# order is frozen here regardless of how the CSV happens to be sorted.
NODE_ORDER = [
    "RF_NODE_01_FrontLeft",
    "RF_NODE_02_FrontRight",
    "RF_NODE_03_BackLeft",
    "RF_NODE_04_BackRight",
]
FEATURE_COLS = ["N1", "N2", "N3", "N4"]


def load_seat_map(path=SEAT_MAP):
    """Return {seat_id: {x, y, row, section}} from the canonical seat map."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        s["seat_id"]: {
            "x": s["x"],
            "y": s["y"],
            "row": s["row"],
            "section": s["section"],
        }
        for s in data["seats"]
    }


def load_rf_nodes(path=FINGERPRINT_JSON):
    """Return the RF node list [{node_id, x, y, z}, ...] from the fingerprint file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["rf_nodes"]


def load_wide(csv_path=DATA_CSV, seat_map=None, window_size=1):
    """Pivot the long RSSI CSV into wide form.

    Returns a DataFrame with columns:
        seat_id, sample_idx, N1..N4, true_x, true_y, row, section
    One row per (seat, sample index) — 99 seats x 100 samples = 9,900 rows when
    window_size=1.

    window_size > 1 averages that many consecutive raw samples into one observation
    (sample_idx becomes the window index). A single instantaneous RSSI reading has
    per-sample noise (sim: std 3 dB) comparable to the RSSI difference between
    neighboring seats (~1-2 dB), so real localization needs to observe over a short
    window rather than classify off one reading — this mirrors that.
    """
    if seat_map is None:
        seat_map = load_seat_map()

    df = pd.read_csv(csv_path)
    # sample_id looks like "R01-L01_N1_S001"; the trailing _S### is the sample index.
    df["sample_idx"] = df["sample_id"].str.extract(r"_S(\d+)$", expand=False).astype(int)
    df["sample_idx"] = df["sample_idx"] // window_size

    wide = df.pivot_table(
        index=["seat_id", "sample_idx"], columns="node_id", values="rssi_dbm"
    )
    missing = [n for n in NODE_ORDER if n not in wide.columns]
    if missing:
        raise ValueError(f"Dataset is missing RF node columns: {missing}")

    wide = wide[NODE_ORDER]
    wide.columns = FEATURE_COLS
    wide = wide.reset_index()

    wide["true_x"] = wide["seat_id"].map(lambda s: seat_map[s]["x"])
    wide["true_y"] = wide["seat_id"].map(lambda s: seat_map[s]["y"])
    wide["row"] = wide["seat_id"].map(lambda s: seat_map[s]["row"])
    wide["section"] = wide["seat_id"].map(lambda s: seat_map[s]["section"])
    return wide
