"""
tests/test_parametric_engine.py
Run with: pytest tests/test_parametric_engine.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timezone, timedelta
from parametric_engine import (
    evaluate_triggers,
    check_underwriting_eligibility,
    compute_fraud_score,
    compute_parametric_premium,
    compute_bcr,
    stress_test_bcr,
    process_payout,
)


# ---------------------------------------------------------------------------
# Trigger Detection
# ---------------------------------------------------------------------------

def test_no_triggers_below_thresholds():
    weather = {'rain_probability': 30, 'wind_speed': 5, 'visibility': 8000, 'temperature': 28}
    result = evaluate_triggers(weather, aqi=100, settings={})
    assert result == []


def test_heavy_rain_trigger():
    weather = {'rain_probability': 70, 'wind_speed': 5, 'visibility': 8000, 'temperature': 28}
    result = evaluate_triggers(weather, aqi=100, settings={'rainfall_threshold': '65'})
    types = [r['trigger_type'] for r in result]
    assert 'Heavy Rain' in types


def test_high_aqi_trigger():
    weather = {'rain_probability': 10, 'wind_speed': 3, 'visibility': 9000, 'temperature': 25}
    result = evaluate_triggers(weather, aqi=320, settings={'aqi_threshold': '300'})
    types = [r['trigger_type'] for r in result]
    assert 'High AQI' in types


def test_low_visibility_trigger():
    weather = {'rain_probability': 10, 'wind_speed': 3, 'visibility': 800, 'temperature': 25}
    result = evaluate_triggers(weather, aqi=80, settings={'visibility_threshold': '1500'})
    types = [r['trigger_type'] for r in result]
    assert 'Low Visibility' in types


def test_multiple_triggers_fire():
    weather = {'rain_probability': 80, 'wind_speed': 20, 'visibility': 500, 'temperature': 25}
    result = evaluate_triggers(weather, aqi=350, settings={})
    assert len(result) >= 3


# ---------------------------------------------------------------------------
# Underwriting Eligibility
# ---------------------------------------------------------------------------

def test_eligible_worker():
    worker = {
        'onboarding_complete': 1,
        'enrollment_date': (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        'weekly_working_days': 6,
    }
    result = check_underwriting_eligibility(worker, settings={'min_working_days': '7'})
    assert result['eligible'] is True
    assert result['tier'] == 'standard'


def test_ineligible_onboarding_incomplete():
    worker = {'onboarding_complete': 0, 'enrollment_date': datetime.now(timezone.utc).isoformat()}
    result = check_underwriting_eligibility(worker, settings={})
    assert result['eligible'] is False
    assert 'Onboarding' in result['reason']


def test_ineligible_too_new():
    worker = {
        'onboarding_complete': 1,
        'enrollment_date': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        'weekly_working_days': 6,
    }
    result = check_underwriting_eligibility(worker, settings={'min_working_days': '7'})
    assert result['eligible'] is False
    assert 'days' in result['reason']


def test_basic_tier_low_activity():
    worker = {
        'onboarding_complete': 1,
        'enrollment_date': (datetime.now(timezone.utc) - timedelta(days=15)).isoformat(),
        'weekly_working_days': 3,
    }
    result = check_underwriting_eligibility(worker, settings={'min_working_days': '7'})
    assert result['eligible'] is True
    assert result['tier'] == 'basic'


# ---------------------------------------------------------------------------
# Fraud Detection
# ---------------------------------------------------------------------------

def test_clean_worker_no_flags():
    now = datetime.now(timezone.utc)
    logs = [
        {'latitude': 28.61, 'longitude': 77.20, 'speed_kmh': 20, 'platform_active': 1,
         'logged_at': (now - timedelta(minutes=90)).isoformat()},
        {'latitude': 28.62, 'longitude': 77.21, 'speed_kmh': 22, 'platform_active': 1,
         'logged_at': (now - timedelta(minutes=30)).isoformat()},
    ]
    result = compute_fraud_score({}, logs, now)
    assert result['fraud_score'] < 0.75
    assert not any('gps_teleport' in f for f in result['flags'])


def test_gps_teleport_detected():
    now = datetime.now(timezone.utc)
    logs = [
        {'latitude': 28.61, 'longitude': 77.20, 'speed_kmh': 0, 'platform_active': 1,
         'logged_at': (now - timedelta(seconds=30)).isoformat()},
        # Jump from Delhi to Mumbai in 20 seconds
        {'latitude': 19.07, 'longitude': 72.87, 'speed_kmh': 0, 'platform_active': 1,
         'logged_at': (now - timedelta(seconds=10)).isoformat()},
    ]
    result = compute_fraud_score({}, logs, now)
    assert any('gps_teleport' in f for f in result['flags'])
    assert result['fraud_score'] >= 0.40


def test_no_activity_logs_flagged():
    result = compute_fraud_score({}, [], datetime.now(timezone.utc))
    assert 'no_activity_logs' in result['flags']
    assert result['fraud_score'] >= 0.35


def test_inactive_during_trigger_window():
    now = datetime.now(timezone.utc)
    logs = [
        {'latitude': 28.61, 'longitude': 77.20, 'speed_kmh': 0, 'platform_active': 0,
         'logged_at': (now - timedelta(minutes=60)).isoformat()},
    ]
    result = compute_fraud_score({}, logs, now)
    assert 'platform_offline_during_trigger' in result['flags']


# ---------------------------------------------------------------------------
# Parametric Premium
# ---------------------------------------------------------------------------

def test_premium_clamped_to_minimum():
    result = compute_parametric_premium(0.001, 100, 7)
    assert result['weekly_premium'] == 20.0


def test_premium_clamped_to_maximum():
    result = compute_parametric_premium(0.10, 400, 7)
    assert result['weekly_premium'] == 50.0


def test_premium_formula_mid_range():
    # 0.055 * 300 * 7 = 115.5 -> clamped to 50
    result = compute_parametric_premium(0.055, 300, 7)
    assert result['raw_premium'] == round(0.055 * 300 * 7, 2)
    assert 20.0 <= result['weekly_premium'] <= 50.0


def test_premium_contains_formula_string():
    result = compute_parametric_premium(0.05, 200, 7)
    assert 'formula' in result


# ---------------------------------------------------------------------------
# Actuarial BCR
# ---------------------------------------------------------------------------

def test_bcr_healthy():
    result = compute_bcr(total_claims_paid=600, total_premium_collected=1000)
    assert result['bcr'] == 0.6
    assert result['status'] == 'healthy'
    assert result['halt_enrollments'] is False


def test_bcr_critical_halts_enrollments():
    result = compute_bcr(total_claims_paid=900, total_premium_collected=1000)
    assert result['bcr'] == 0.9
    assert result['status'] == 'critical'
    assert result['halt_enrollments'] is True


def test_bcr_elevated():
    result = compute_bcr(total_claims_paid=780, total_premium_collected=1000)
    assert result['status'] == 'elevated'
    assert result['halt_enrollments'] is False


def test_bcr_no_premium_returns_insufficient():
    result = compute_bcr(0, 0)
    assert result['status'] == 'insufficient_data'


def test_stress_test_increases_bcr():
    base = compute_bcr(600, 1000)
    stress = stress_test_bcr(base['bcr'], daily_payout=500, total_premium=1000, stress_days=14)
    assert stress['stressed_bcr'] > base['bcr']
    assert stress['additional_claims'] == 7000.0
    assert stress['halt_enrollments'] is True


# ---------------------------------------------------------------------------
# Payout Processing
# ---------------------------------------------------------------------------

def test_sandbox_payout_success():
    import random
    random.seed(42)  # seed for deterministic result (no random failure)
    result = process_payout(user_id=1, claim_id='CLM101', amount=500.0, method='UPI')
    assert result['status'] == 'Success'
    assert result['gateway_ref'].startswith('GC-')
    assert result['amount'] == 500.0
    assert result['method_used'] in ('UPI', 'IMPS')
    assert result['settled_at'] is not None


def test_payout_zero_amount_raises():
    raised = False
    try:
        process_payout(1, 'CLM102', 0)
    except ValueError:
        raised = True
    assert raised


def test_payout_exceeds_sandbox_limit():
    result = process_payout(1, 'CLM103', 110000.0)
    assert result['status'] == 'Rolled_Back'
    assert result['rollback_reason'] is not None


def test_payout_imps_method():
    import random
    random.seed(0)  # seed so IMPS doesn't randomly fail
    result = process_payout(1, 'CLM104', 300.0, method='IMPS')
    assert result['status'] == 'Success'
    assert result['method_used'] == 'IMPS'


def test_payout_has_timestamps():
    import random
    random.seed(1)
    result = process_payout(1, 'CLM105', 250.0)
    assert 'settled_at' in result
    assert 'gateway_ref' in result
