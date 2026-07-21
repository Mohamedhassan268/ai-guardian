"""Localization models: map a 4-value RSSI reading to a seat position.

Two lightweight k-NN approaches, compared in evaluate.py — no deep learning needed
for a 4-feature problem.
"""

import json

import numpy as np
from sklearn.neighbors import KNeighborsRegressor


def _nearest_seat(x, y, seat_map):
    """Snap an (x, y) estimate to the nearest seat in seat_map."""
    best_id, best_dist = None, float("inf")
    for seat_id, s in seat_map.items():
        dist = (s["x"] - x) ** 2 + (s["y"] - y) ** 2
        if dist < best_dist:
            best_id, best_dist = seat_id, dist
    return best_id


class FingerprintKNN:
    """Nearest-neighbor match against mean per-seat RSSI fingerprints."""

    def __init__(self, seat_map):
        self.seat_map = seat_map
        self._seat_ids = []
        self._fingerprints = None

    @classmethod
    def from_fingerprint_file(cls, path, seat_map):
        """Load precomputed per-seat mean RSSI vectors instead of recomputing them.

        Fingerprint entries store means as flat fields rssi_node1..rssi_node4, in the
        same node order as rf_nodes (RF_NODE_01..04 == FrontLeft/FrontRight/BackLeft/
        BackRight), which matches data.NODE_ORDER / data.FEATURE_COLS.
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        model = cls(seat_map)
        seat_ids, vectors = [], []
        for fp in data["fingerprints"]:
            seat_ids.append(fp["seat_id"])
            vectors.append(
                [fp["rssi_node1"], fp["rssi_node2"], fp["rssi_node3"], fp["rssi_node4"]]
            )
        model._seat_ids = seat_ids
        model._fingerprints = np.array(vectors)
        return model

    def fit(self, X, seat_ids):
        """Fit from training data by averaging RSSI per seat (fallback path)."""
        by_seat = {}
        for row, seat_id in zip(X, seat_ids):
            by_seat.setdefault(seat_id, []).append(row)
        self._seat_ids = list(by_seat.keys())
        self._fingerprints = np.array([np.mean(v, axis=0) for v in by_seat.values()])
        return self

    def predict_seat(self, X):
        X = np.asarray(X)
        dists = np.linalg.norm(self._fingerprints[None, :, :] - X[:, None, :], axis=2)
        idx = dists.argmin(axis=1)
        return [self._seat_ids[i] for i in idx]

    def predict_xy(self, X):
        seats = self.predict_seat(X)
        return np.array([[self.seat_map[s]["x"], self.seat_map[s]["y"]] for s in seats])


class RegressorKNN:
    """k-NN regression on raw RSSI -> continuous (x, y), snapped to nearest seat."""

    def __init__(self, seat_map, n_neighbors=5):
        self.seat_map = seat_map
        self.model = KNeighborsRegressor(n_neighbors=n_neighbors)

    def fit(self, X, y_xy):
        self.model.fit(X, y_xy)
        return self

    def predict_xy(self, X):
        return self.model.predict(X)

    def predict_seat(self, X):
        xy = self.predict_xy(X)
        return [_nearest_seat(x, y, self.seat_map) for x, y in xy]
