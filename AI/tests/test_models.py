import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localization.models import FingerprintKNN, RegressorKNN

SEAT_MAP = {
    "R01-L01": {"x": 0.0, "y": 0.0, "row": 1, "section": "Left"},
    "R01-C01": {"x": 5.0, "y": 0.0, "row": 1, "section": "Center"},
    "R02-L01": {"x": 0.0, "y": 3.0, "row": 2, "section": "Left"},
}


def test_fingerprint_knn_predicts_known_seat():
    model = FingerprintKNN(SEAT_MAP)
    X = [[-50, -70, -80], [-50, -70, -80], [-70, -50, -80], [-80, -70, -50]]
    seats = ["R01-L01", "R01-L01", "R01-C01", "R02-L01"]
    model.fit(X, seats)

    pred = model.predict_seat([[-50, -70, -80]])
    assert pred == ["R01-L01"]


def test_fingerprint_knn_handles_equal_rssi_input():
    """Failure case: an ambiguous all-equal RSSI vector must still return a valid seat,
    not crash."""
    model = FingerprintKNN(SEAT_MAP)
    X = [[-50, -70, -80], [-70, -50, -80], [-80, -70, -50]]
    seats = ["R01-L01", "R01-C01", "R02-L01"]
    model.fit(X, seats)

    pred = model.predict_seat([[-70, -70, -70]])
    assert pred[0] in SEAT_MAP


def test_regressor_knn_predicts_xy_and_seat():
    model = RegressorKNN(SEAT_MAP, n_neighbors=1)
    X = np.array([[-50, -70, -80], [-70, -50, -80], [-80, -70, -50]])
    y = np.array([[0.0, 0.0], [5.0, 0.0], [0.0, 3.0]])
    model.fit(X, y)

    xy = model.predict_xy([[-50, -70, -80]])
    assert xy.shape == (1, 2)

    seats = model.predict_seat([[-50, -70, -80]])
    assert seats[0] in SEAT_MAP
