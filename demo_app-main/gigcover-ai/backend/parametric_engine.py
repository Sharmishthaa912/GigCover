"""
parametric_engine.py
Parametric Insurance core logic:
  - Trigger detection against thresholds
  - Underwriting eligibility check
  - Fraud scoring (GPS + activity coherence)
  - Actuarial BCR computation
  - Payout processing with rollback support
"""
import json
import math
import uuid
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Trigger Detection
# ---------------------------------------------------------------------------

TRIGGER_THRESHOLDS = {
    'Heavy Rain':         ('rain_probability', 65.0),
    'High AQI':           ('aqi',              300.0),
    'Strong Wind':        ('wind_speed',        15.0),
    'Low Visibility':     ('visibility',       1500.0),   # metres, BELOW threshold
    'Extreme Heat':       ('temperature',       42.0),
}


def evaluate_triggers(weather: dict, aqi: float, settings: dict) -> list[dict]:
    """
    Compare live sensor values against parametric thresholds.
    Returns list of fired trigger dicts.
    """
    rain_threshold  = float(settings.get('rainfall_threshold', 65))
    aqi_threshold   = float(settings.get('aqi_threshold', 300))
    wind_threshold  = float(settings.get('wind_threshold', 15))
    vis_threshold   = float(settings.get('visibility_threshold', 1500))

    checks = [
        ('Heavy Rain',     weather.get('rain_probability', 0),  rain_threshold,  'above'),
        ('High AQI',       aqi,                                  aqi_threshold,   'above'),
        ('Strong Wind',    weather.get('wind_speed', 0),         wind_threshold,  'above'),
        ('Low Visibility', weather.get('visibility', 10000),     vis_threshold,   'below'),
        ('Extreme Heat',   weather.get('temperature', 0),        42.0,            'above'),
    ]

    fired = []
    for name, observed, threshold, direction in checks:
        triggered = (observed > threshold) if direction == 'above' else (observed < threshold)
        if triggered:
            fired.append({
                'trigger_type':    name,
                'observed_value':  round(float(observed), 2),
                'threshold_value': threshold,
                'direction':       direction,
            })
    return fired


# ---------------------------------------------------------------------------
# Underwriting Eligibility
# ---------------------------------------------------------------------------

def check_underwriting_eligibility(worker: dict, settings: dict) -> dict:
    """
    Returns {'eligible': bool, 'reason': str, 'tier': str}
    Rules:
      - Policy must be Active
      - Worker must have completed onboarding
      - Minimum working days since enrollment
      - Low-activity workers → lower tier
    """
    min_days = int(settings.get('min_working_days', 7))

    if not worker.get('onboarding_complete'):
        return {'eligible': False, 'reason': 'Onboarding not complete', 'tier': 'none'}

    enrollment_raw = worker.get('enrollment_date') or worker.get('created_at', '')
    try:
        enrollment_dt = datetime.fromisoformat(str(enrollment_raw).replace('Z', '+00:00'))
        days_enrolled = (datetime.now(timezone.utc) - enrollment_dt).days
    except Exception:
        days_enrolled = min_days  # assume eligible if date parse fails

    if days_enrolled < min_days:
        return {
            'eligible': False,
            'reason': f'Minimum {min_days} working days required (enrolled {days_enrolled} days ago)',
            'tier': 'none',
        }

    weekly_days = int(worker.get('weekly_working_days', 6) or 6)
    tier = 'standard' if weekly_days >= 5 else 'basic'

    return {'eligible': True, 'reason': 'Eligible for parametric payout', 'tier': tier}


# ---------------------------------------------------------------------------
# Fraud Detection
# ---------------------------------------------------------------------------

def compute_fraud_score(worker: dict, activity_logs: list[dict], trigger_time: datetime) -> dict:
    """
    Multi-signal fraud scoring (0.0 = clean, 1.0 = high risk).
    Signals:
      1. GPS teleport: impossible speed between consecutive pings
      2. No recent activity: worker was offline during trigger window
      3. Burst timing: claim filed within 60 s of trigger (script-like)
    Returns {'fraud_score': float, 'flags': list[str]}
    """
    flags = []
    score = 0.0

    if not activity_logs:
        flags.append('no_activity_logs')
        score += 0.35
    else:
        # Check for GPS teleport (speed > 200 km/h between pings)
        sorted_logs = sorted(activity_logs, key=lambda x: x.get('logged_at', ''))
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
        else:
            offline_count = sum(1 for l in recent if not l.get('platform_active', 1))
            if offline_count == len(recent):
                flags.append('platform_offline_during_trigger')
                score += 0.20

    # Burst timing: claim filed < 60 s after trigger (scripted behaviour)
    now = datetime.now(timezone.utc)
    if (now - trigger_time).total_seconds() < 60:
        flags.append('burst_timing')
        score += 0.15

    score = min(round(score, 2), 1.0)
    return {'fraud_score': score, 'flags': flags}


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_dt(value: str):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Parametric Premium Pricing
# ---------------------------------------------------------------------------

def compute_parametric_premium(trigger_probability: float, avg_income_loss: float,
                                exposure_days: int = 7) -> dict:
    """
    Formula: premium = trigger_probability × avg_income_loss × exposure_days
    Clamped to ₹20–₹50/week.
    """
    raw = trigger_probability * avg_income_loss * exposure_days
    weekly_premium = round(max(20.0, min(50.0, raw)), 2)
    return {
        'trigger_probability': round(trigger_probability, 4),
        'avg_income_loss': round(avg_income_loss, 2),
        'exposure_days': exposure_days,
        'raw_premium': round(raw, 2),
        'weekly_premium': weekly_premium,
        'formula': 'premium = trigger_probability × avg_income_loss × exposure_days  [clamped ₹20–₹50]',
    }


# ---------------------------------------------------------------------------
# Actuarial BCR
# ---------------------------------------------------------------------------

def compute_bcr(total_claims_paid: float, total_premium_collected: float) -> dict:
    """
    BCR (Burning Cost Ratio) = total_claims / total_premium
    Target: 0.55 – 0.70
    Halt new enrollments if loss_ratio > 0.85
    """
    if total_premium_collected <= 0:
        return {'bcr': 0.0, 'status': 'insufficient_data', 'halt_enrollments': False}

    bcr = round(total_claims_paid / total_premium_collected, 4)
    if bcr < 0.55:
        status = 'under_priced_risk'
    elif bcr <= 0.70:
        status = 'healthy'
    elif bcr <= 0.85:
        status = 'elevated'
    else:
        status = 'critical'

    return {
        'bcr': bcr,
        'total_claims_paid': round(total_claims_paid, 2),
        'total_premium_collected': round(total_premium_collected, 2),
        'status': status,
        'halt_enrollments': bcr > 0.85,
        'target_range': '0.55 – 0.70',
    }


def stress_test_bcr(base_bcr: float, daily_payout: float, total_premium: float,
                    stress_days: int = 14) -> dict:
    """Simulate N-day continuous trigger (e.g. 14-day rain) impact on BCR."""
    additional_claims = daily_payout * stress_days
    stressed_bcr = round((base_bcr * total_premium + additional_claims) / max(total_premium, 1), 4)
    return {
        'stress_days': stress_days,
        'additional_claims': round(additional_claims, 2),
        'stressed_bcr': stressed_bcr,
        'halt_enrollments': stressed_bcr > 0.85,
    }


# ---------------------------------------------------------------------------
# Payout Processing — delegates to settlement.py
# ---------------------------------------------------------------------------

def process_payout(user_id: int, claim_id: str, amount: float,
                   method: str = 'UPI', worker_upi: str = '',
                   use_razorpay_sandbox: bool = False) -> dict:
    """
    Delegates to settlement.settle_payout().
    Returns a settlement_result dict with status, gateway_ref, utr, attempts.
    Raises ValueError for invalid amount.
    """
    from settlement import settle_payout
    return settle_payout(
        user_id=user_id,
        claim_id=claim_id,
        amount=amount,
        worker_upi=worker_upi,
        preferred_method=method,
        use_razorpay_sandbox=use_razorpay_sandbox,
    )
