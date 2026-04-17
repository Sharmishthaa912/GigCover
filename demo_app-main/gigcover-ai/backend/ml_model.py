import os
from dataclasses import dataclass
from typing import List, Dict, Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler


MODEL_PATH = os.path.join(os.path.dirname(__file__), "risk_model.joblib")
FRAUD_MODEL_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.joblib")
FRAUD_SCALER_PATH = os.path.join(os.path.dirname(__file__), "fraud_scaler.joblib")


@dataclass
class RiskFeatures:
    rainfall_level: float
    aqi_level: float
    traffic_congestion: float
    zone_type: str
    historical_disruptions: float


@dataclass
class FraudFeatures:
    avg_speed_kmh: float
    activity_ratio: float
    ping_frequency_per_hour: float
    location_variance: float
    time_since_trigger_seconds: Optional[float] = None
    claim_amount: Optional[float] = None
    previous_claims_count: Optional[int] = None


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


def _build_fraud_dataset():
    """Build synthetic fraud detection dataset."""
    np.random.seed(42)

    # Normal behavior patterns
    normal_data = np.random.normal([15, 0.8, 10, 0.1], [5, 0.1, 3, 0.05], (700, 4))

    # Fraudulent behavior patterns
    fraud_data = np.random.normal([80, 0.2, 50, 0.8], [20, 0.2, 15, 0.3], (300, 4))

    X = np.vstack([normal_data, fraud_data])
    y = np.hstack([np.zeros(700), np.ones(300)])  # 0 = normal, 1 = fraud

    return X, y


def train_and_save_model():
    """Train and save the risk prediction model."""
    X, y = _build_dataset()
    model = RandomForestRegressor(n_estimators=240, random_state=42)
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)
    return model


def train_and_save_fraud_model():
    """Train and save the fraud detection model."""
    X, y = _build_fraud_dataset()

    # Train classifier
    classifier = RandomForestClassifier(n_estimators=100, random_state=42)
    classifier.fit(X, y)

    # Train anomaly detector
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    anomaly_detector = IsolationForest(contamination=0.3, random_state=42)
    anomaly_detector.fit(X_scaled)

    # Save models
    joblib.dump(classifier, FRAUD_MODEL_PATH)
    joblib.dump(scaler, FRAUD_SCALER_PATH)

    return classifier, scaler, anomaly_detector


def load_model():
    if not os.path.exists(MODEL_PATH):
        return train_and_save_model()
    return joblib.load(MODEL_PATH)


def load_fraud_model():
    """Load fraud detection models."""
    if not os.path.exists(FRAUD_MODEL_PATH):
        classifier, scaler, _ = train_and_save_fraud_model()
        return classifier, scaler

    classifier = joblib.load(FRAUD_MODEL_PATH)
    scaler = joblib.load(FRAUD_SCALER_PATH)
    return classifier, scaler


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


def predict_fraud_probability(features: FraudFeatures) -> Dict:
    """
    Predict fraud probability using ML models.
    Returns dict with fraud_score, confidence, and flags.
    """
    classifier, scaler = load_fraud_model()

    # Extract basic features
    feature_vector = np.array([[
        features.avg_speed_kmh,
        features.activity_ratio,
        features.ping_frequency_per_hour,
        features.location_variance
    ]])

    # Scale features
    scaled_features = scaler.transform(feature_vector)

    # Get fraud probability
    fraud_prob = float(classifier.predict_proba(scaled_features)[0][1])

    # Additional rule-based checks
    flags = []
    confidence = 0.5

    if features.avg_speed_kmh > 100:
        flags.append('impossible_speed')
        fraud_prob += 0.2
        confidence += 0.2

    if features.activity_ratio < 0.3:
        flags.append('low_activity')
        fraud_prob += 0.15
        confidence += 0.1

    if features.time_since_trigger_seconds and features.time_since_trigger_seconds < 60:
        flags.append('burst_timing')
        fraud_prob += 0.1
        confidence += 0.15

    if features.previous_claims_count and features.previous_claims_count > 10:
        flags.append('high_claim_frequency')
        fraud_prob += 0.1

    # Cap probabilities
    fraud_prob = min(1.0, max(0.0, fraud_prob))
    confidence = min(1.0, max(0.0, confidence))

    risk_level = 'high' if fraud_prob > 0.7 else 'medium' if fraud_prob > 0.4 else 'low'

    return {
        'fraud_score': round(fraud_prob, 3),
        'confidence': round(confidence, 3),
        'risk_level': risk_level,
        'flags': flags,
        'model_used': 'RandomForestClassifier'
    }


def detect_anomalies(activity_logs: List[Dict]) -> Dict:
    """
    Detect anomalous patterns in activity logs using unsupervised learning.
    """
    if len(activity_logs) < 5:
        return {'anomaly_score': 0.0, 'is_anomalous': False, 'details': 'Insufficient data'}

    # Extract features from logs
    features = []
    for log in activity_logs[-20:]:  # Last 20 logs
        features.append([
            log.get('speed_kmh', 0),
            1 if log.get('platform_active', 0) else 0,
            log.get('latitude', 0),
            log.get('longitude', 0)
        ])

    X = np.array(features)

    # Use Isolation Forest for anomaly detection
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
    anomaly_scores = anomaly_detector.fit_predict(X_scaled)

    # Calculate anomaly ratio
    anomalous_count = sum(1 for score in anomaly_scores if score == -1)
    anomaly_ratio = anomalous_count / len(anomaly_scores)

    return {
        'anomaly_score': round(anomaly_ratio, 3),
        'is_anomalous': anomaly_ratio > 0.3,
        'anomalous_logs': anomalous_count,
        'total_logs': len(activity_logs),
        'details': f'{anomalous_count}/{len(activity_logs)} logs flagged as anomalous'
    }
