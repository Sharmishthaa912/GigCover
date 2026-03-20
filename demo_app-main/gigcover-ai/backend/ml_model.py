import os
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor


MODEL_PATH = os.path.join(os.path.dirname(__file__), "risk_model.joblib")


@dataclass
class RiskFeatures:
    rainfall_level: float
    aqi_level: float
    traffic_congestion: float
    zone_type: str
    historical_disruptions: float


def _zone_to_num(zone_type: str) -> int:
    return 1 if str(zone_type).lower() == "urban" else 0


def _build_dataset():
    # Synthetic but realistic disruption dataset for hackathon prototype.
    rows = np.array(
        [
            [25, 70, 45, 1, 2],
            [40, 80, 52, 1, 3],
            [60, 95, 62, 1, 4],
            [90, 110, 73, 1, 6],
            [110, 130, 80, 1, 7],
            [20, 65, 35, 0, 1],
            [35, 75, 43, 0, 2],
            [55, 85, 55, 0, 3],
            [75, 96, 64, 0, 4],
            [95, 108, 70, 0, 5],
            [120, 145, 88, 1, 8],
            [130, 152, 92, 1, 9],
            [70, 100, 59, 1, 5],
            [50, 92, 49, 0, 3],
            [100, 120, 75, 0, 6],
            [85, 105, 68, 1, 6],
            [65, 98, 60, 0, 4],
            [115, 138, 83, 1, 8],
        ],
        dtype=float,
    )
    y = np.array(
        [
            0.22,
            0.29,
            0.39,
            0.55,
            0.67,
            0.16,
            0.22,
            0.31,
            0.42,
            0.53,
            0.75,
            0.81,
            0.49,
            0.34,
            0.62,
            0.57,
            0.44,
            0.78,
        ]
    )
    return rows, y


def train_and_save_model():
    X, y = _build_dataset()
    model = RandomForestRegressor(n_estimators=240, random_state=42)
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)
    return model


def load_model():
    if not os.path.exists(MODEL_PATH):
        return train_and_save_model()
    return joblib.load(MODEL_PATH)


def predict_risk(model, features: RiskFeatures) -> float:
    sample = np.array(
        [
            [
                float(features.rainfall_level),
                float(features.aqi_level),
                float(features.traffic_congestion),
                _zone_to_num(features.zone_type),
                float(features.historical_disruptions),
            ]
        ]
    )
    score = float(model.predict(sample)[0])
    return round(max(0.0, min(1.0, score)), 2)
