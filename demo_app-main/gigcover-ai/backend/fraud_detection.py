"""
fraud_detection.py
Advanced fraud detection for GigCover AI Phase 3.
Features:
  - Multi-signal fraud scoring (GPS, activity, timing)
  - Anomaly detection using ML models
  - Ring detection for coordinated fraud
  - Progressive verification tiers
"""

import math
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Fraud detection model (trained on synthetic data)
_fraud_model = None
_scaler = None

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in km."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def _parse_dt(dt_str: str) -> Optional[datetime]:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
    except:
        return None

def initialize_fraud_model():
    """Initialize fraud detection ML model with synthetic training data."""
    global _fraud_model, _scaler

    # Synthetic training data: normal vs fraudulent patterns
    np.random.seed(42)
    n_samples = 1000

    # Normal patterns
    normal_data = np.random.normal([0, 0, 0, 0], [0.5, 0.5, 0.2, 0.2], (800, 4))
    # Fraudulent patterns: high speeds, no activity, burst timing
    fraud_data = np.random.normal([2, -1, 1, 1], [0.8, 0.3, 0.5, 0.5], (200, 4))

    training_data = np.vstack([normal_data, fraud_data])

    _scaler = StandardScaler()
    scaled_data = _scaler.fit_transform(training_data)

    _fraud_model = IsolationForest(contamination=0.2, random_state=42)
    _fraud_model.fit(scaled_data)

def compute_fraud_score(worker: Dict, activity_logs: List[Dict], trigger_time: datetime) -> Dict:
    """
    Multi-signal fraud scoring (0.0 = clean, 1.0 = high risk).
    Signals:
      1. GPS teleport: impossible speed between consecutive pings
      2. No recent activity: worker was offline during trigger window
      3. Burst timing: claim filed within 60 s of trigger (script-like)
      4. ML anomaly score: trained model on activity patterns
    Returns {'fraud_score': float, 'flags': list[str], 'confidence': float}
    """
    flags = []
    score = 0.0
    confidence = 0.5  # Base confidence

    if not activity_logs:
        flags.append('no_activity_logs')
        score += 0.35
        confidence += 0.2
    else:
        # Check for GPS teleport (speed > 200 km/h between pings)
        sorted_logs = sorted(activity_logs, key=lambda x: x.get('logged_at', ''))
        teleport_detected = False
        for i in range(1, len(sorted_logs)):
            prev, curr = sorted_logs[i - 1], sorted_logs[i]
            try:
                dt_seconds = max(1, (
                    datetime.fromisoformat(str(curr['logged_at']).replace('Z', '+00:00')) -
                    datetime.fromisoformat(str(prev['logged_at']).replace('Z', '+00:00'))
                ).total_seconds())
                dist_km = _haversine(
                    prev['latitude'], prev['longitude'],
                    curr['latitude'], curr['longitude']
                )
                speed = (dist_km / dt_seconds) * 3600
                if speed > 200:
                    flags.append(f'gps_teleport_{round(speed)}kmh')
                    score += 0.40
                    teleport_detected = True
                    confidence += 0.3
                    break
            except Exception:
                pass

        # Check worker was active within 2 hours of trigger
        window_start = trigger_time - timedelta(hours=2)
        recent = [
            l for l in activity_logs
            if _parse_dt(l.get('logged_at', '')) and
               window_start <= _parse_dt(l['logged_at']) <= trigger_time
        ]
        if not recent:
            flags.append('inactive_during_trigger_window')
            score += 0.30
            confidence += 0.2
        else:
            offline_count = sum(1 for l in recent if not l.get('platform_active', 1))
            if offline_count > len(recent) * 0.8:
                flags.append('mostly_offline_during_trigger')
                score += 0.25
                confidence += 0.1

        # Burst timing check (claim within 60 seconds of trigger)
        if activity_logs:
            last_log_time = max(_parse_dt(l.get('logged_at', '')) for l in activity_logs if _parse_dt(l.get('logged_at', '')))
            if last_log_time and (trigger_time - last_log_time).total_seconds() < 60:
                flags.append('burst_timing_suspicious')
                score += 0.20
                confidence += 0.15

        # ML-based anomaly detection
        if _fraud_model and _scaler:
            try:
                # Extract features: avg_speed, activity_ratio, ping_frequency, location_variance
                speeds = []
                for i in range(1, len(sorted_logs)):
                    prev, curr = sorted_logs[i-1], sorted_logs[i]
                    dt_sec = max(1, (
                        _parse_dt(curr['logged_at']) - _parse_dt(prev['logged_at'])
                    ).total_seconds())
                    dist = _haversine(prev['latitude'], prev['longitude'], curr['latitude'], curr['longitude'])
                    speeds.append((dist / dt_sec) * 3600)

                avg_speed = np.mean(speeds) if speeds else 0
                activity_ratio = np.mean([l.get('platform_active', 1) for l in activity_logs[-10:]])  # Last 10 logs
                ping_freq = len(activity_logs) / max(1, (trigger_time - _parse_dt(activity_logs[0]['logged_at'])).total_seconds() / 3600)  # pings per hour

                # Location variance (spread of coordinates)
                lats = [l['latitude'] for l in activity_logs]
                lons = [l['longitude'] for l in activity_logs]
                lat_var = np.var(lats) if lats else 0
                lon_var = np.var(lons) if lons else 0
                location_variance = lat_var + lon_var

                features = np.array([[avg_speed, activity_ratio, ping_freq, location_variance]])
                scaled_features = _scaler.transform(features)
                anomaly_score = _fraud_model.decision_function(scaled_features)[0]

                # Convert anomaly score to fraud probability (lower anomaly_score = more anomalous)
                ml_fraud_prob = 1 / (1 + np.exp(anomaly_score * 2))  # Sigmoid transformation
                score += ml_fraud_prob * 0.3  # Weight ML score at 30%
                confidence += 0.2

                if ml_fraud_prob > 0.7:
                    flags.append('ml_anomaly_detected')
            except Exception as e:
                flags.append(f'ml_scoring_error: {str(e)}')

    # Cap score and adjust confidence
    score = min(1.0, max(0.0, score))
    confidence = min(1.0, max(0.0, confidence))

    return {
        'fraud_score': round(score, 3),
        'flags': flags,
        'confidence': round(confidence, 3),
        'risk_level': 'high' if score > 0.7 else 'medium' if score > 0.4 else 'low'
    }

def detect_fraud_ring(accounts: List[Dict], claims: List[Dict]) -> Dict:
    """
    Detect coordinated fraud rings based on shared signals.
    Returns ring analysis with suspicious clusters.
    """
    rings = []
    suspicious_accounts = []

    # Simple ring detection: accounts with similar claim patterns
    claim_groups = {}
    for claim in claims:
        key = f"{claim.get('trigger_type', '')}_{claim.get('latitude', 0):.2f}_{claim.get('longitude', 0):.2f}"
        if key not in claim_groups:
            claim_groups[key] = []
        claim_groups[key].append(claim)

    for location_key, group_claims in claim_groups.items():
        if len(group_claims) >= 3:  # At least 3 claims at same location
            account_ids = set(c.get('user_id') for c in group_claims)
            if len(account_ids) >= 2:  # Multiple accounts
                # Check timing clustering (claims within 5 minutes)
                timestamps = sorted([_parse_dt(c.get('created_at', '')) for c in group_claims if _parse_dt(c.get('created_at', ''))])
                if timestamps:
                    time_spread = (timestamps[-1] - timestamps[0]).total_seconds()
                    if time_spread < 300:  # 5 minutes
                        rings.append({
                            'ring_id': f"ring_{len(rings)+1}",
                            'accounts': list(account_ids),
                            'location_key': location_key,
                            'claim_count': len(group_claims),
                            'time_spread_seconds': time_spread,
                            'suspicious_level': 'high'
                        })
                        suspicious_accounts.extend(account_ids)

    return {
        'rings_detected': len(rings),
        'rings': rings,
        'suspicious_accounts': list(set(suspicious_accounts)),
        'analysis_timestamp': datetime.now(timezone.utc).isoformat()
    }

def progressive_verification(fraud_score: float, flags: List[str]) -> Dict:
    """
    Determine verification tier based on fraud risk.
    Returns verification requirements and actions.
    """
    if fraud_score > 0.8 or 'gps_teleport' in str(flags):
        return {
            'tier': 'block',
            'action': 'deny_claim',
            'reason': 'High fraud risk detected',
            'verification_required': ['manual_review', 'device_verification']
        }
    elif fraud_score > 0.6 or len(flags) >= 3:
        return {
            'tier': 'escalate',
            'action': 'manual_review',
            'reason': 'Medium fraud risk - requires human verification',
            'verification_required': ['location_verification', 'activity_review']
        }
    elif fraud_score > 0.3 or len(flags) >= 1:
        return {
            'tier': 'monitor',
            'action': 'approve_with_monitoring',
            'reason': 'Low fraud risk - approve but monitor',
            'verification_required': ['automated_checks']
        }
    else:
        return {
            'tier': 'approve',
            'action': 'auto_approve',
            'reason': 'Clean claim - auto approve',
            'verification_required': []
        }