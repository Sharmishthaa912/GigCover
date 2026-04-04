import os
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

import jwt
from flask import Flask, g, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

from .ml_model import RiskFeatures, load_model, predict_risk, train_and_save_model
from parametric_engine import (
    evaluate_triggers,
    check_underwriting_eligibility,
    compute_fraud_score,
    compute_parametric_premium,
    compute_bcr,
    stress_test_bcr,
    process_payout,
)
from settlement import reconcile_pending, daily_reconciliation_report
from triggers import (
    run_all_triggers,
    resolve_coords,
    fetch_weather,
    fetch_aqi,
    fetch_demand_index,
    CITY_COORDS,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend', 'dist'))
FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, 'assets')
SCHEMA_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'database', 'schema.sql'))
JWT_SECRET = os.environ.get('JWT_SECRET', 'gigcover-super-secret')
JWT_ALGO = 'HS256'
EMAIL_REGEX = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _resolve_db_path():
    explicit_db_path = os.environ.get('DB_PATH')
    if explicit_db_path:
        db_dir = os.path.dirname(explicit_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        return explicit_db_path

    render_disk_path = os.environ.get('RENDER_DISK_PATH')
    if render_disk_path:
        os.makedirs(render_disk_path, exist_ok=True)
        return os.path.join(render_disk_path, 'gigcover.db')

    return os.path.join(BASE_DIR, 'gigcover.db')


DB_PATH = _resolve_db_path()
OPENWEATHER_API_KEY = ''  # Using open-meteo which doesn't require API key
CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')


def _db_role(role_value):
    return 'Student' if role_value == 'Admin' else role_value


def _public_role(role_value):
    return 'Admin' if role_value == 'Student' else role_value


def _is_admin_role(role_value):
    return _public_role(role_value) == 'Admin'

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
CORS(app, resources={r'/*': {'origins': '*' if CORS_ORIGINS == '*' else [origin.strip() for origin in CORS_ORIGINS.split(',') if origin.strip()]}})

model = train_and_save_model()


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as schema_file:
        db.executescript(schema_file.read())
    _ensure_runtime_schema(db)
    db.commit()
    db.close()


def _table_columns(db, table_name):
    rows = db.execute(f'PRAGMA table_info({table_name})').fetchall()
    return {row[1] for row in rows}


def _ensure_runtime_schema(db):
    # Parametric tables
    db.execute("""
        CREATE TABLE IF NOT EXISTS trigger_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          trigger_type TEXT NOT NULL,
          city TEXT NOT NULL DEFAULT '',
          latitude REAL DEFAULT 0,
          longitude REAL DEFAULT 0,
          threshold_value REAL NOT NULL,
          observed_value REAL NOT NULL,
          affected_users INTEGER DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'Active',
          triggered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          resolved_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          claim_id TEXT,
          txn_type TEXT NOT NULL,
          amount REAL NOT NULL,
          method TEXT NOT NULL DEFAULT 'UPI',
          status TEXT NOT NULL DEFAULT 'Pending',
          gateway_ref TEXT DEFAULT '',
          utr TEXT DEFAULT '',
          rollback_reason TEXT DEFAULT '',
          attempts TEXT DEFAULT '[]',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          settled_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          latitude REAL NOT NULL,
          longitude REAL NOT NULL,
          speed_kmh REAL DEFAULT 0,
          platform_active INTEGER DEFAULT 1,
          logged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Parametric settings seeds
    for k, v in [
        ('aqi_threshold', '300'), ('wind_threshold', '15'),
        ('visibility_threshold', '1500'), ('payout_per_day', '500'),
        ('bcr_target_min', '0.55'), ('bcr_target_max', '0.70'),
        ('loss_ratio_halt', '0.85'), ('min_working_days', '7'),
        ('fraud_score_block', '0.75'), ('heat_threshold', '42'),
        ('demand_threshold', '0.45'),
    ]:
        db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

    # Existing tables
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_payments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          amount REAL NOT NULL,
          paid_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          next_due_date TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Paid',
          FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          category TEXT NOT NULL,
          department TEXT NOT NULL,
          event_date TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'Scheduled',
          created_by INTEGER,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (created_by) REFERENCES users(id)
        )
        """
    )

    # workers extra columns
    worker_columns = _table_columns(db, 'workers')
    if 'location_text' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN location_text TEXT DEFAULT ""')
    if 'age' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN age INTEGER DEFAULT 0')
    if 'gender' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN gender TEXT DEFAULT ""')
    if 'work_type' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN work_type TEXT DEFAULT ""')
    if 'working_shift' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN working_shift TEXT DEFAULT "Day"')
    if 'weekly_working_days' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN weekly_working_days INTEGER DEFAULT 6')
    if 'working_hours' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN working_hours REAL DEFAULT 8')
    if 'income_dependency' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN income_dependency TEXT DEFAULT "Medium"')
    if 'working_environment' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN working_environment TEXT DEFAULT "Outdoor"')
    if 'manual_location' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN manual_location TEXT DEFAULT ""')
    if 'latitude' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN latitude REAL DEFAULT 0')
    if 'longitude' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN longitude REAL DEFAULT 0')
    if 'onboarding_complete' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN onboarding_complete INTEGER DEFAULT 0')
    if 'enrollment_date' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN enrollment_date TEXT DEFAULT CURRENT_TIMESTAMP')
    if 'tier' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN tier TEXT DEFAULT "standard"')
    if 'upi_id' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN upi_id TEXT DEFAULT ""')
    if 'phone' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN phone TEXT DEFAULT ""')
    if 'gps_consent' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN gps_consent INTEGER DEFAULT 0')
    if 'tracking_consent' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN tracking_consent INTEGER DEFAULT 0')
    if 'risk_pool' not in worker_columns:
        db.execute('ALTER TABLE workers ADD COLUMN risk_pool TEXT DEFAULT "general"')
    # claims extra columns
    claims_columns = _table_columns(db, 'claims')
    if 'trigger_event_id' not in claims_columns:
        db.execute('ALTER TABLE claims ADD COLUMN trigger_event_id INTEGER')
    if 'fraud_score' not in claims_columns:
        db.execute('ALTER TABLE claims ADD COLUMN fraud_score REAL DEFAULT 0')
    if 'fraud_flags' not in claims_columns:
        db.execute('ALTER TABLE claims ADD COLUMN fraud_flags TEXT DEFAULT "[]"')
    # transactions extra columns (migration for existing DBs)
    if 'transactions' in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        txn_columns = _table_columns(db, 'transactions')
        if 'utr' not in txn_columns:
            db.execute('ALTER TABLE transactions ADD COLUMN utr TEXT DEFAULT ""')
        if 'rollback_reason' not in txn_columns:
            db.execute('ALTER TABLE transactions ADD COLUMN rollback_reason TEXT DEFAULT ""')
        if 'attempts' not in txn_columns:
            db.execute('ALTER TABLE transactions ADD COLUMN attempts TEXT DEFAULT "[]"')


def make_token(user):
    payload = {
        'sub': str(user['id']),
        'email': user['email'],
        'role': _public_role(user['role']),
        'exp': datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def auth_required(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Bearer '):
            return jsonify({'error': 'Missing token'}), 401

        token = header.split(' ', 1)[1].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.user = payload
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return handler(*args, **kwargs)

    return wrapped


def _risk_category(score):
    if score < 0.4:
        return 'Low Risk'
    if score < 0.7:
        return 'Medium Risk'
    return 'High Risk'


def _risk_label_from_score(score):
    if score < 0.4:
        return 'low'
    if score < 0.7:
        return 'medium'
    return 'high'


def _normalize_risk_label(value):
    label = str(value or '').strip().lower()
    if label in {'low', 'medium', 'high'}:
        return label
    if label in {'low risk', 'low_risk'}:
        return 'low'
    if label in {'medium risk', 'moderate', 'moderate risk', 'medium_risk'}:
        return 'medium'
    if label in {'high risk', 'high_risk'}:
        return 'high'
    return ''


def _claim_status_for_risk(risk_label):
    return 'Rejected' if risk_label == 'low' else 'Approved'


def _claim_message_for_risk(risk_label):
    if risk_label == 'low':
        return 'Claim not eligible due to low risk'
    if risk_label == 'medium':
        return 'Claim approved (moderate risk)'
    return 'Claim approved (high risk)'


def _get_setting(db, key, default_value):
    row = db.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    return float(row['value']) if row else float(default_value)


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def _http_get_json(url, timeout=20):
    req = Request(url, headers={'User-Agent': 'GigCover/1.0'})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _frontend_bundle_files():
    assets_dir = Path(FRONTEND_ASSETS_DIR)
    js_file = ''
    css_file = ''

    if assets_dir.exists():
        js_candidates = sorted(assets_dir.glob('index-*.js'))
        css_candidates = sorted(assets_dir.glob('index-*.css'))
        if js_candidates:
            js_file = js_candidates[-1].name
        if css_candidates:
            css_file = css_candidates[-1].name

    return js_file, css_file


def _safe_request_payload(payload):
    if not isinstance(payload, dict):
        return payload
    redacted = dict(payload)
    if 'password' in redacted:
        redacted['password'] = '***'
    return redacted


def _render_frontend():
    js_file, css_file = _frontend_bundle_files()
    return render_template('index.html', js_file=js_file, css_file=css_file)


def _reverse_geocode(latitude, longitude):
    if OPENWEATHER_API_KEY:
        params = urlencode({'lat': latitude, 'lon': longitude, 'limit': 1, 'appid': OPENWEATHER_API_KEY})
        data = _http_get_json(f'https://api.openweathermap.org/geo/1.0/reverse?{params}', timeout=12)
        if isinstance(data, list) and data:
            first = data[0]
            city = first.get('name', 'Unknown city')
            state = first.get('state') or first.get('country') or ''
            display = f'{city}, {state}' if state else city
            return {'city': city, 'area': state, 'display_name': display}

    params = urlencode({'lat': latitude, 'lon': longitude, 'format': 'jsonv2', 'addressdetails': 1})
    data = _http_get_json(f'https://nominatim.openstreetmap.org/reverse?{params}', timeout=12)
    address = data.get('address', {})
    city = (
        address.get('city')
        or address.get('town')
        or address.get('village')
        or address.get('state_district')
        or 'Unknown city'
    )
    # Use state for a clean "City, State" format — avoids ward numbers and raw suburb names
    state = address.get('state') or address.get('country') or ''
    display = f'{city}, {state}' if state else city
    return {'city': city, 'area': state, 'display_name': display}


def _forward_geocode(query_text):
    query = str(query_text or '').strip()
    if not query:
        return None

    if OPENWEATHER_API_KEY:
        params = urlencode({'q': query, 'limit': 1, 'appid': OPENWEATHER_API_KEY})
        data = _http_get_json(f'https://api.openweathermap.org/geo/1.0/direct?{params}', timeout=12)
        if isinstance(data, list) and data:
            first = data[0]
            lat = float(first.get('lat', 0) or 0)
            lon = float(first.get('lon', 0) or 0)
            if abs(lat) > 0.0001 or abs(lon) > 0.0001:
                return lat, lon

    params = urlencode({'q': query, 'format': 'jsonv2', 'limit': 1})
    data = _http_get_json(f'https://nominatim.openstreetmap.org/search?{params}', timeout=12)
    if isinstance(data, list) and data:
        first = data[0]
        lat = float(first.get('lat', 0) or 0)
        lon = float(first.get('lon', 0) or 0)
        if abs(lat) > 0.0001 or abs(lon) > 0.0001:
            return lat, lon

    return None


def _fetch_weather_for_coords(latitude, longitude, city=''):
    """Fetch weather using triggers.fetch_weather with all fallbacks."""
    w = fetch_weather(latitude, longitude, api_key=OPENWEATHER_API_KEY, city=city)
    rain_prob = float(w.get('rain_probability', 0))
    wind_speed = float(w.get('wind_speed', 0))
    visibility = int(w.get('visibility', 10000))

    risk_score = _clamp(
        (rain_prob / 100.0) * 0.45
        + _clamp(wind_speed / 20.0) * 0.25
        + _clamp((10000 - visibility) / 10000.0) * 0.30
    )
    risk_label = _risk_label_from_score(risk_score)
    claim_status = _claim_status_for_risk(risk_label)
    recommendation = _claim_message_for_risk(risk_label)

    return {
        'weather': {
            'temperature':      w.get('temperature', 0),
            'humidity':         w.get('humidity', 0),
            'wind_speed':       w.get('wind_speed', 0),
            'visibility':       visibility,
            'rain_probability': rain_prob,
            'description':      w.get('description', ''),
            'source':           w.get('source', 'unknown'),
        },
        'risk': {
            'risk_score':       round(risk_score, 2),
            'risk':             risk_label,
            'risk_level':       risk_label.capitalize(),
            'claim_recommended': claim_status == 'Approved',
            'claim_status':     claim_status,
            'claim_message':    recommendation,
            'recommendation':   recommendation,
        },
    }


def _compute_dynamic_risk_and_premium(data):
    daily_income = float(data.get('daily_income', 500))
    city = str(data.get('city', '')).strip().lower()
    delivery_platform = str(data.get('delivery_platform', 'Blinkit')).strip().lower()
    work_type = str(data.get('work_type', 'delivery')).strip().lower()
    working_shift = str(data.get('working_shift', 'Day')).strip().lower()
    zone_type = str(data.get('zone_type', 'Urban')).strip().lower()
    working_hours = float(data.get('working_hours', 8))

    if daily_income <= 0:
        raise ValueError('Daily income must be greater than 0')

    # Lightweight heuristic risks derived from onboarding inputs.
    city_weather_bias = {
        'mumbai': 0.78,
        'bengaluru': 0.56,
        'bangalore': 0.56,
        'delhi': 0.48,
        'hyderabad': 0.52,
        'kolkata': 0.62,
        'chennai': 0.66,
        'pune': 0.49,
    }
    city_pollution_bias = {
        'delhi': 0.82,
        'kolkata': 0.69,
        'mumbai': 0.64,
        'bangalore': 0.52,
        'bengaluru': 0.52,
        'hyderabad': 0.58,
        'chennai': 0.57,
        'pune': 0.50,
    }
    platform_traffic_bias = {
        'blinkit': 0.64,
        'zepto': 0.60,
        'swiggy': 0.57,
        'zomato': 0.59,
        'uber': 0.63,
    }
    work_type_bias = {
        'delivery': 0.66,
        'driver': 0.68,
        'freelancer': 0.42,
        'technician': 0.54,
        'field agent': 0.58,
    }
    zone_risk_map = {
        'urban': 0.70,
        'semi-urban': 0.52,
    }
    shift_bias = {'day': 0.04, 'night': 0.12}

    hours_factor = _clamp((working_hours - 4.0) / 8.0)
    weather_risk = _clamp(city_weather_bias.get(city, 0.55) + (hours_factor * 0.08))
    pollution_risk = _clamp(city_pollution_bias.get(city, 0.56) + (hours_factor * 0.05))
    traffic_risk = _clamp(
        platform_traffic_bias.get(delivery_platform, 0.58)
        + work_type_bias.get(work_type, 0.50) * 0.18
        + shift_bias.get(working_shift, 0.05)
        + (hours_factor * 0.12)
    )
    zone_risk = _clamp(zone_risk_map.get(zone_type, 0.52))

    risk_score = round(
        (0.4 * weather_risk) + (0.3 * pollution_risk) + (0.2 * traffic_risk) + (0.1 * zone_risk),
        2,
    )

    base_premium = 15.0
    income_factor = daily_income / 500.0
    risk_adjustment = round(risk_score * 20.0, 2)
    income_adjustment = round(income_factor * 5.0, 2)
    weekly_premium = round(base_premium + risk_adjustment + income_adjustment, 2)
    coverage = round(daily_income * 7 * 0.7, 2)

    # Apply low-risk discount and high-risk extended-coverage note.
    risk_category = _risk_label_from_score(risk_score)
    premium_note = 'Standard premium applied.'
    if risk_category == 'low' or zone_type in {'semi-urban', 'rural'}:
        weekly_premium = round(weekly_premium * 0.88, 2)
        premium_note = 'Premium reduced due to low-risk zone and stable conditions.'
    elif risk_category == 'high':
        premium_note = 'High-risk zone detected; extended coverage hours enabled during peak risk periods.'

    return {
        'daily_income': daily_income,
        'working_hours': working_hours,
        'weather_risk': round(weather_risk, 2),
        'pollution_risk': round(pollution_risk, 2),
        'traffic_risk': round(traffic_risk, 2),
        'zone_risk': round(zone_risk, 2),
        'risk_score': risk_score,
        'base_premium': base_premium,
        'risk_adjustment': risk_adjustment,
        'income_adjustment': income_adjustment,
        'weekly_premium': weekly_premium,
        'coverage_amount': coverage,
        'city': city,
        'delivery_platform': delivery_platform,
        'work_type': work_type,
        'working_shift': working_shift,
        'zone_type': zone_type,
        'premium_note': premium_note,
        'coverage_conditions': [
            'Valid for on-demand gig work in covered city',
            'Auto-activated on defined weather, pollution, and traffic triggers',
            'Covers lost hours due to forced pause in work',
            'Weekly premium dynamically adjusted with low-risk discounts',
        ],
    }


def _fetch_aqi_for_coords(latitude, longitude, city=''):
    result = fetch_aqi(latitude, longitude, api_key=OPENWEATHER_API_KEY, city=city)
    return float(result.get('aqi', 100))


def _assess_trigger_conditions(weather, risk, aqi):
    triggers = []

    final_risk_score = float(risk.get('risk_score', 0))
    rain_prob = float(weather.get('rain_probability', 0))
    visibility = float(weather.get('visibility', 10000))
    wind_speed = float(weather.get('wind_speed', 0))
    temp = float(weather.get('temperature', 0))

    if rain_prob >= 65 or temp >= 34:
        triggers.append({'type': 'Heavy Rain', 'detail': 'Rain probability or temperature indicates extreme conditions.'})
    if aqi >= 150:
        triggers.append({'type': 'High Pollution', 'detail': 'AQI indicates hazardous air quality.'})
    if final_risk_score >= 0.62:
        triggers.append({'type': 'Traffic Disruption', 'detail': 'Historic or real-time risk score indicates heavy traffic risk.'})
    if wind_speed >= 10:
        triggers.append({'type': 'Strong Wind', 'detail': 'Wind speed is above safe threshold.'})
    if visibility <= 3000:
        triggers.append({'type': 'Low Visibility', 'detail': 'Visibility is reduced, increasing risk.'})

    return triggers


def _create_auto_claim(db, user_id, trigger_type, lost_hours, rainfall, risk_label):
    now = datetime.now(timezone.utc)
    normalized_risk = _normalize_risk_label(risk_label) or 'low'
    claim_decision = _claim_status_for_risk(normalized_risk)
    worker = db.execute('SELECT daily_income FROM workers WHERE user_id = ?', (user_id,)).fetchone()
    daily_income = float(worker['daily_income'] if worker else 500)
    hourly_income = daily_income / 8.0
    payout = round(float(lost_hours if claim_decision == 'Approved' else 0.0) * hourly_income, 2)

    count_row = db.execute('SELECT COUNT(*) AS count FROM claims').fetchone()
    claim_number = (count_row['count'] if count_row else 0) + 101
    claim_id = f'CLM{claim_number}'

    db.execute(
        'INSERT INTO claims(claim_id, user_id, trigger_type, lost_hours, payout, status, rainfall, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (claim_id, user_id, float(lost_hours), trigger_type, float(payout), 'Triggered', float(rainfall), now.isoformat()),
    )
    db.commit()

    db.execute('UPDATE claims SET status = ? WHERE claim_id = ?', ('Processing', claim_id))
    db.commit()

    final_status = 'Completed' if claim_decision == 'Approved' else 'Rejected'
    db.execute('UPDATE claims SET status = ? WHERE claim_id = ?', (final_status, claim_id))
    db.commit()

    return {
        'claim_id': claim_id,
        'trigger_type': trigger_type,
        'lost_hours': float(lost_hours),
        'payout': payout,
        'status': final_status,
        'risk': normalized_risk,
        'claim_status': final_status,
        'message': _claim_message_for_risk(normalized_risk),
        'timeline': ['Triggered', 'Processing', final_status],
    }


def _derive_risk_reason(weather, worker):
    reasons = []
    rain_probability = float(weather.get('rain_probability', 0))
    wind_speed = float(weather.get('wind_speed', 0))
    visibility = float(weather.get('visibility', 10000))
    working_hours = float(worker.get('working_hours', 8) or 8)
    work_type = str(worker.get('work_type', '')).lower()
    working_environment = str(worker.get('working_environment', '')).lower()

    if rain_probability >= 60:
        reasons.append('High rain probability')
    if wind_speed >= 8:
        reasons.append('Strong wind conditions')
    if visibility <= 3500:
        reasons.append('Low visibility detected')
    if working_hours >= 10:
        reasons.append('Long working hours increase exposure')
    if work_type in {'delivery', 'driver'}:
        reasons.append('Road-heavy work profile')
    if working_environment == 'outdoor':
        reasons.append('Outdoor environment increases weather dependency')

    if not reasons:
        reasons.append('Weather and work profile are currently stable')

    return reasons


def _create_claim(db, user_id, trigger_type='Rainfall', lost_hours=3.0, rainfall=0.0):
    return _create_claim_with_decision(
        db,
        user_id,
        trigger_type=trigger_type,
        lost_hours=lost_hours,
        rainfall=rainfall,
        risk_label='high',
    )


def _create_claim_with_decision(db, user_id, trigger_type='Rainfall', lost_hours=3.0, rainfall=0.0, risk_label='high'):
    normalized_risk = _normalize_risk_label(risk_label) or 'low'
    claim_status = _claim_status_for_risk(normalized_risk)
    approved_lost_hours = float(lost_hours) if claim_status == 'Approved' else 0.0

    worker = db.execute('SELECT daily_income FROM workers WHERE user_id = ?', (user_id,)).fetchone()
    daily_income = float(worker['daily_income'] if worker else 500)
    hourly_income = daily_income / 8.0
    payout = round(float(approved_lost_hours) * hourly_income, 2)

    count_row = db.execute('SELECT COUNT(*) AS count FROM claims').fetchone()
    claim_number = (count_row['count'] if count_row else 0) + 101
    claim_id = f'CLM{claim_number}'

    db.execute(
        """
        INSERT INTO claims(claim_id, user_id, trigger_type, lost_hours, payout, status, rainfall)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (claim_id, int(user_id), trigger_type, float(lost_hours), payout, claim_status, float(rainfall)),
    )
    db.commit()

    return {
        'claim_id': claim_id,
        'trigger_type': trigger_type,
        'lost_hours': float(lost_hours),
        'payout': payout,
        'status': claim_status,
        'risk': normalized_risk,
        'claim_status': claim_status,
        'message': _claim_message_for_risk(normalized_risk),
    }


@app.post('/signup')
@app.post('/api/signup')
def signup():
    data = request.get_json(silent=True) or {}
    print(f"[signup] payload={_safe_request_payload(data)}")
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', '')

    if not all([name, email, password, role]):
        return jsonify({'error': 'All fields are required'}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long.'}), 400
    if role not in {'Employee', 'Admin', 'Student'}:
        return jsonify({'error': 'Invalid role'}), 400
    db_role = _db_role(role)

    db = get_db()
    existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    password_hash = generate_password_hash(password)
    cur = db.execute(
        'INSERT INTO users(name, email, password_hash, role) VALUES (?, ?, ?, ?)',
        (name, email, password_hash, db_role),
    )
    user_id = cur.lastrowid

    db.execute('INSERT INTO workers(user_id, full_name, city) VALUES (?, ?, ?)', (user_id, name, ''))
    db.execute(
        "INSERT INTO policies(user_id, policy_status, premium, coverage_amount) VALUES (?, 'Inactive', 0, 0)",
        (user_id,),
    )
    db.commit()

    user = db.execute('SELECT id, email, role, name FROM users WHERE id = ?', (user_id,)).fetchone()
    token = make_token(user)
    return jsonify(
        {
            'message': 'User created successfully',
            'status': 'success',
            'token': token,
            'user': {'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': _public_role(user['role'])},
        }
    )


@app.post('/login')
@app.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    print(f"[login] payload={_safe_request_payload(data)}")
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    if not EMAIL_REGEX.match(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400

    db = get_db()
    user = db.execute(
        'SELECT id, name, email, role, password_hash FROM users WHERE email = ?', (email,)
    ).fetchone()
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    worker = db.execute(
        'SELECT onboarding_complete FROM workers WHERE user_id = ?', (user['id'],)
    ).fetchone()
    onboarding_complete = bool(worker['onboarding_complete']) if worker else False

    token = make_token(user)
    return jsonify(
        {
            'message': 'Login successful',
            'status': 'success',
            'token': token,
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': _public_role(user['role']),
                'onboarding_complete': onboarding_complete,
            },
        }
    )


@app.post('/train-model')
@auth_required
def retrain_model():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403

    global model
    model = train_and_save_model()
    return jsonify({'message': 'Model trained and saved'})


@app.post('/predict-risk')
@auth_required
def predict_risk_api():
    global model
    model = load_model()

    data = request.get_json(force=True)
    user_id = int(request.user['sub'])
    features = RiskFeatures(
        rainfall_level=float(data.get('rainfall_level', 55)),
        aqi_level=float(data.get('AQI_level', 92)),
        traffic_congestion=float(data.get('traffic_congestion', 58)),
        zone_type=data.get('zone_type', 'Urban'),
        historical_disruptions=float(data.get('historical_disruptions', 3)),
    )
    score = predict_risk(model, features)

    db = get_db()
    db.execute(
        """
        INSERT INTO risk_scores(user_id, rainfall_level, aqi_level, traffic_congestion, zone_type, historical_disruptions, risk_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            features.rainfall_level,
            features.aqi_level,
            features.traffic_congestion,
            features.zone_type,
            features.historical_disruptions,
            score,
        ),
    )
    db.execute('UPDATE workers SET risk_score = ? WHERE user_id = ?', (score, user_id))
    db.commit()

    risk_label = _risk_label_from_score(score)
    claim_status = _claim_status_for_risk(risk_label)
    return jsonify(
        {
            'risk_score': score,
            'category': _risk_category(score),
            'risk': risk_label,
            'risk_level': risk_label.capitalize(),
            'claim_status': claim_status,
            'message': _claim_message_for_risk(risk_label),
        }
    )


@app.post('/calculate-premium')
@auth_required
def calculate_premium_api():
    data = request.get_json(force=True)
    db = get_db()
    user_id = int(request.user['sub'])

    try:
        calc = _compute_dynamic_risk_and_premium(data)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400

    db.execute(
        """
        UPDATE workers
        SET full_name = COALESCE(?, full_name),
            city = COALESCE(?, city),
            delivery_platform = COALESCE(?, delivery_platform),
            zone_type = COALESCE(?, zone_type),
            risk_score = ?,
            daily_income = ?,
            weekly_premium = ?,
            coverage_amount = ?,
            onboarding_complete = 1
        WHERE user_id = ?
        """,
        (
            data.get('full_name'),
            data.get('city'),
            data.get('delivery_platform'),
            data.get('zone_type'),
            calc['risk_score'],
            calc['daily_income'],
            calc['weekly_premium'],
            calc['coverage_amount'],
            user_id,
        ),
    )
    db.execute(
        """
        INSERT INTO risk_scores(user_id, rainfall_level, aqi_level, traffic_congestion, zone_type, historical_disruptions, risk_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            calc['weather_risk'] * 100,
            calc['pollution_risk'] * 100,
            calc['traffic_risk'] * 100,
            data.get('zone_type', 'Urban'),
            calc['working_hours'],
            calc['risk_score'],
        ),
    )
    db.execute(
        "UPDATE policies SET premium = ?, coverage_amount = ?, policy_status = 'Active' WHERE user_id = ?",
        (calc['weekly_premium'], calc['coverage_amount'], user_id),
    )
    db.commit()

    return jsonify(
        {
            'risk_score': calc['risk_score'],
            'weekly_premium': calc['weekly_premium'],
            'coverage_amount': calc['coverage_amount'],
            'risk_components': {
                'weather_risk': calc['weather_risk'],
                'pollution_risk': calc['pollution_risk'],
                'traffic_risk': calc['traffic_risk'],
                'zone_risk': calc['zone_risk'],
            },
            'premium_breakdown': {
                'base_premium': calc['base_premium'],
                'risk_adjustment': calc['risk_adjustment'],
                'income_adjustment': calc['income_adjustment'],
                'total_weekly_premium': calc['weekly_premium'],
            },
            'formula': 'weekly_premium = 15 + (risk_score * 20) + ((daily_income / 500) * 5)',
        }
    )


@app.post('/create-claim')
@auth_required
def create_claim_api():
    data = request.get_json(force=True)
    lost_hours = float(data.get('lost_hours', 3))
    trigger_type = data.get('trigger_type', 'Rainfall')
    rainfall = float(data.get('rainfall', 0))

    db = get_db()
    user_id = int(request.user['sub'])

    incoming_risk = _normalize_risk_label(data.get('risk'))
    if incoming_risk:
        effective_risk = incoming_risk
    elif data.get('risk_score') is not None:
        try:
            effective_risk = _risk_label_from_score(float(data.get('risk_score')))
        except (TypeError, ValueError):
            effective_risk = ''
    else:
        effective_risk = ''

    if not effective_risk:
        worker = db.execute('SELECT risk_score FROM workers WHERE user_id = ?', (user_id,)).fetchone()
        worker_score = float(worker['risk_score'] if worker and worker['risk_score'] is not None else 0)
        effective_risk = _risk_label_from_score(worker_score)

    claim = _create_claim_with_decision(
        db,
        user_id,
        trigger_type=trigger_type,
        lost_hours=lost_hours,
        rainfall=rainfall,
        risk_label=effective_risk,
    )

    return jsonify(
        {
            'risk': claim['risk'],
            'claim_status': claim['claim_status'],
            'message': claim['message'],
            'claim': claim,
        }
    )


@app.post('/simulate-rain')
@auth_required
def simulate_rain_api():
    data = request.get_json(force=True)
    rainfall = float(data.get('rainfall', 120))

    db = get_db()
    threshold = _get_setting(db, 'rainfall_threshold', 100)

    if rainfall > threshold:
        claim = _create_claim_with_decision(
            db,
            int(request.user['sub']),
            trigger_type='Rainfall',
            lost_hours=3,
            rainfall=rainfall,
            risk_label='high',
        )
        return jsonify(
            {
                'triggered': True,
                'rainfall': rainfall,
                'risk': claim['risk'],
                'claim_status': claim['claim_status'],
                'message': claim['message'],
                'claim': claim,
            }
        )

    return jsonify(
        {
            'triggered': False,
            'rainfall': rainfall,
            'risk': 'low',
            'claim_status': 'Rejected',
            'message': 'Claim not eligible due to low risk',
        }
    )


@app.post('/auto-trigger')
@auth_required
def auto_trigger():
    data = request.get_json(force=True) or {}
    db = get_db()
    user_id = int(request.user['sub'])

    latitude = float(data.get('latitude', 0) or 0)
    longitude = float(data.get('longitude', 0) or 0)
    if abs(latitude) < 0.0001 or abs(longitude) < 0.0001:
        worker_row = db.execute('SELECT latitude, longitude, zone_type, weekly_premium FROM workers WHERE user_id = ?', (user_id,)).fetchone()
        if worker_row:
            latitude = float(worker_row['latitude'] or 0)
            longitude = float(worker_row['longitude'] or 0)
        if abs(latitude) < 0.0001 or abs(longitude) < 0.0001:
            return jsonify({'error': 'Location required for trigger assessment.'}), 400

    try:
        weather_bundle = _fetch_weather_for_coords(latitude, longitude)
    except Exception as e:
        return jsonify({'error': f'Unable to fetch weather data: {e}'}), 503

    aqi = float(data.get('aqi', 0) or _fetch_aqi_for_coords(latitude, longitude))
    risk = weather_bundle.get('risk', {})
    triggers = _assess_trigger_conditions(weather_bundle.get('weather', {}), risk, aqi)

    premium_note = 'No premium adjustment needed.'
    zone_type = str(data.get('zone_type', '')).strip().lower()
    if not zone_type:
        worker_row = db.execute('SELECT zone_type FROM workers WHERE user_id = ?', (user_id,)).fetchone()
        zone_type = str(worker_row['zone_type'] or '').strip().lower() if worker_row else ''

    if zone_type in {'semi-urban', 'rural', 'low-risk'} or float(risk.get('risk_score', 0)) < 0.4:
        _ = db.execute('UPDATE workers SET weekly_premium = weekly_premium * 0.88 WHERE user_id = ?', (user_id,))
        _ = db.execute('UPDATE policies SET premium = premium * 0.88 WHERE user_id = ?', (user_id,))
        db.commit()
        premium_note = 'Premium reduced due to zone-level low risk and weather data.'

    event_entries = []
    auto_claims = []
    for trigger in triggers:
        event_entries.append((f"Auto trigger: {trigger['type']}", 'Safety', 'Auto', datetime.now(timezone.utc).isoformat(), 'Triggered', user_id))
        risk_label = 'high' if trigger['type'] in {'Heavy Rain', 'Strong Wind', 'Low Visibility'} else 'medium'
        claim = _create_auto_claim(db, user_id, trigger_type=trigger['type'], lost_hours=3.0, rainfall=float(weather_bundle.get('weather', {}).get('rain_probability', 0)), risk_label=risk_label)
        auto_claims.append(claim)

    if event_entries:
        db.executemany(
            'INSERT INTO events(title, category, department, event_date, status, created_by) VALUES (?, ?, ?, ?, ?, ?)',
            event_entries,
        )
        db.commit()

    policy_premium_row = db.execute('SELECT premium FROM policies WHERE user_id = ?', (user_id,)).fetchone()
    final_premium = float(policy_premium_row['premium'] if policy_premium_row and policy_premium_row['premium'] is not None else 0)

    return jsonify(
        {
            'triggered': len(triggers) > 0,
            'triggers': triggers,
            'auto_claims': auto_claims,
            'premium_note': premium_note,
            'weather': weather_bundle.get('weather', {}),
            'risk': risk,
            'aqi': aqi,
            'policy_premium': final_premium,
        }
    )


@app.get('/dashboard-data')
@auth_required
def dashboard_data():
    db = get_db()
    role = request.user['role']

    if _is_admin_role(role):
        totals = db.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM users) AS total_users,
              (SELECT COUNT(*) FROM claims) AS total_claims,
              (SELECT COALESCE(SUM(payout), 0) FROM claims) AS total_payouts
            """
        ).fetchone()

        claims = [dict(row) for row in db.execute('SELECT * FROM claims ORDER BY id DESC LIMIT 10').fetchall()]
        users = [
            {**dict(row), 'role': _public_role(row['role'])}
            for row in db.execute('SELECT id, name, email, role, created_at FROM users ORDER BY id DESC LIMIT 20').fetchall()
        ]
        risks = [
            dict(row)
            for row in db.execute('SELECT user_id, risk_score, created_at FROM risk_scores ORDER BY id DESC LIMIT 12').fetchall()
        ]
        policies = [
            dict(row)
            for row in db.execute(
                """
                SELECT p.id, p.user_id, p.policy_status, p.premium, p.coverage_amount,
                       u.name AS user_name, w.delivery_platform, w.zone_type
                FROM policies p
                JOIN users u ON u.id = p.user_id
                LEFT JOIN workers w ON w.user_id = p.user_id
                ORDER BY p.id DESC
                LIMIT 30
                """
            ).fetchall()
        ]
        events = [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 30').fetchall()]

        return jsonify(
            {
                'analytics': {
                    'total_users': totals['total_users'],
                    'total_claims': totals['total_claims'],
                    'total_payouts': round(float(totals['total_payouts']), 2),
                },
                'users': users,
                'claims': claims,
                'risks': risks,
                'policies': policies,
                'events': events,
            }
        )

    user_id = int(request.user['sub'])
    user = db.execute('SELECT id, name, email, role FROM users WHERE id = ?', (user_id,)).fetchone()
    worker = db.execute('SELECT * FROM workers WHERE user_id = ?', (user_id,)).fetchone()
    policy = db.execute('SELECT * FROM policies WHERE user_id = ?', (user_id,)).fetchone()
    claims = [
        dict(row)
        for row in db.execute(
            'SELECT claim_id, trigger_type, lost_hours, payout, status, created_at FROM claims WHERE user_id = ? ORDER BY id DESC',
            (user_id,),
        ).fetchall()
    ]

    weather = {'rainfall': 93, 'temperature': 31, 'aqi': 118}
    latest_payment = db.execute(
        'SELECT amount, paid_on, next_due_date, status FROM premium_payments WHERE user_id = ? ORDER BY id DESC LIMIT 1',
        (user_id,),
    ).fetchone()
    event_rows = db.execute('SELECT title, category, status, event_date, created_at FROM events WHERE created_by = ? ORDER BY id DESC LIMIT 6', (user_id,)).fetchall()

    return jsonify(
        {
            'user': ({**dict(user), 'role': _public_role(user['role'])} if user else {}),
            'worker': dict(worker) if worker else {},
            'policy': dict(policy) if policy else {},
            'claims': claims,
            'events': [dict(row) for row in event_rows],
            'weather': weather,
            'risk_category': _risk_category(float(worker['risk_score'] if worker else 0)),
            'premium_payment': dict(latest_payment) if latest_payment else None,
        }
    )


@app.post('/onboarding')
@app.post('/api/onboarding')
@auth_required
def onboarding_save():
    db = get_db()
    user_id = int(request.user['sub'])
    data = request.get_json(force=True)

    full_name = str(data.get('full_name', '')).strip()
    age = int(data.get('age', 0) or 0)
    gender = str(data.get('gender', '')).strip()
    work_type = str(data.get('work_type', '')).strip()
    delivery_platform = str(data.get('platform_used', '')).strip()
    working_hours = float(data.get('working_hours', 8) or 8)
    working_shift = str(data.get('working_shift', 'Day')).strip() or 'Day'
    weekly_working_days = int(data.get('weekly_working_days', 6) or 6)
    city = str(data.get('city', '')).strip()
    manual_location = str(data.get('manual_location', '')).strip()
    location_text = str(data.get('location_text', '')).strip()
    latitude = float(data.get('latitude', 0) or 0)
    longitude = float(data.get('longitude', 0) or 0)
    daily_income = float(data.get('daily_income', 0) or 0)
    income_dependency = str(data.get('income_dependency', 'Medium')).strip() or 'Medium'
    working_environment = str(data.get('working_environment', 'Outdoor')).strip() or 'Outdoor'
    zone_type = str(data.get('zone_type', 'Urban')).strip() or 'Urban'
    # Phase 2 fields
    upi_id = str(data.get('upi_id', '')).strip()
    phone = str(data.get('phone', '')).strip()
    gps_consent = bool(data.get('gps_consent', False))
    tracking_consent = bool(data.get('tracking_consent', False))

    if not full_name or not work_type or not delivery_platform:
        return jsonify({'error': 'Full name, work type and platform are required.'}), 400
    if age <= 0:
        return jsonify({'error': 'Valid age is required.'}), 400
    if weekly_working_days <= 0 or weekly_working_days > 7:
        return jsonify({'error': 'Weekly working days must be between 1 and 7.'}), 400
    if working_hours <= 0 or working_hours > 24:
        return jsonify({'error': 'Working hours must be between 1 and 24.'}), 400
    if daily_income <= 0:
        return jsonify({'error': 'Daily income must be greater than 0.'}), 400

    calc = _compute_dynamic_risk_and_premium({
        'daily_income': daily_income, 'city': city,
        'delivery_platform': delivery_platform, 'work_type': work_type,
        'working_shift': working_shift, 'zone_type': zone_type,
        'working_hours': working_hours, 'full_name': full_name,
    })

    # City-based risk pool assignment
    city_lower = city.lower()
    risk_pool = city_lower if city_lower in {
        'delhi', 'mumbai', 'bengaluru', 'bangalore', 'hyderabad',
        'chennai', 'kolkata', 'pune'
    } else 'general'

    worker_cols = _table_columns(db, 'workers')
    extra_sets = []
    extra_vals = []
    if 'upi_id' in worker_cols:
        extra_sets.append('upi_id = ?'); extra_vals.append(upi_id)
    if 'phone' in worker_cols:
        extra_sets.append('phone = ?'); extra_vals.append(phone)
    if 'gps_consent' in worker_cols:
        extra_sets.append('gps_consent = ?'); extra_vals.append(int(gps_consent))
    if 'tracking_consent' in worker_cols:
        extra_sets.append('tracking_consent = ?'); extra_vals.append(int(tracking_consent))
    if 'risk_pool' in worker_cols:
        extra_sets.append('risk_pool = ?'); extra_vals.append(risk_pool)

    extra_clause = (', ' + ', '.join(extra_sets)) if extra_sets else ''

    db.execute(
        f"""
        UPDATE workers
        SET full_name=?, age=?, gender=?, city=?, location_text=?, manual_location=?,
            latitude=?, longitude=?, work_type=?, delivery_platform=?, daily_income=?,
            working_hours=?, zone_type=?, risk_score=?, weekly_premium=?, coverage_amount=?,
            working_shift=?, weekly_working_days=?, income_dependency=?,
            working_environment=?, onboarding_complete=1{extra_clause}
        WHERE user_id=?
        """,
        (
            full_name, age, gender, city, location_text, manual_location,
            latitude, longitude, work_type, delivery_platform, daily_income,
            working_hours, zone_type, calc['risk_score'], calc['weekly_premium'],
            calc['coverage_amount'], working_shift, weekly_working_days,
            income_dependency, working_environment,
            *extra_vals, user_id,
        ),
    )
    db.execute(
        "UPDATE policies SET premium=?, coverage_amount=?, policy_status='Active' WHERE user_id=?",
        (calc['weekly_premium'], calc['coverage_amount'], user_id),
    )
    db.commit()

    return jsonify({
        'message': 'Onboarding completed successfully.',
        'status': 'success',
        'weekly_premium': calc['weekly_premium'],
        'coverage_amount': calc['coverage_amount'],
        'risk_score': calc['risk_score'],
        'risk_pool': risk_pool,
        'premium_note': calc['premium_note'],
        'premium_breakdown': {
            'base_premium': calc['base_premium'],
            'risk_adjustment': calc['risk_adjustment'],
            'income_adjustment': calc['income_adjustment'],
            'formula': 'base_price × risk_factor × activity_factor',
        },
        'coverage_conditions': calc['coverage_conditions'],
    })


@app.get('/profile')
@auth_required
def profile_get():
    db = get_db()
    user_id = int(request.user['sub'])
    user = db.execute('SELECT id, name, email, role, created_at FROM users WHERE id = ?', (user_id,)).fetchone()
    worker = db.execute('SELECT * FROM workers WHERE user_id = ?', (user_id,)).fetchone()
    policy = db.execute(
        'SELECT policy_status, premium, coverage_amount, created_at FROM policies WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    return jsonify(
        {
            'user': ({**dict(user), 'role': _public_role(user['role'])} if user else {}),
            'worker': dict(worker) if worker else {},
            'policy': dict(policy) if policy else {},
        }
    )


@app.put('/profile')
@auth_required
def profile_update():
    db = get_db()
    user_id = int(request.user['sub'])
    data = request.get_json(force=True)

    name = str(data.get('name', '')).strip()
    city = str(data.get('city', '')).strip()
    location_text = str(data.get('location_text', '')).strip()
    delivery_platform = str(data.get('delivery_platform', '')).strip()
    working_shift = str(data.get('working_shift', '')).strip()
    working_hours_raw = data.get('working_hours')
    weekly_working_days_raw = data.get('weekly_working_days')

    if name:
        db.execute('UPDATE users SET name = ? WHERE id = ?', (name, user_id))

    worker_updates = ['city = ?', 'location_text = ?']
    worker_params: list = [city, location_text]
    if delivery_platform:
        worker_updates.append('delivery_platform = ?')
        worker_params.append(delivery_platform)
    if working_shift:
        worker_updates.append('working_shift = ?')
        worker_params.append(working_shift)
    if working_hours_raw is not None:
        worker_updates.append('working_hours = ?')
        worker_params.append(float(working_hours_raw))
    if weekly_working_days_raw is not None:
        worker_updates.append('weekly_working_days = ?')
        worker_params.append(int(weekly_working_days_raw))

    worker_params.append(user_id)
    db.execute(f'UPDATE workers SET {", ".join(worker_updates)} WHERE user_id = ?', worker_params)
    db.commit()

    return jsonify({'message': 'Profile updated successfully.'})


@app.get('/payment-history')
@auth_required
def payment_history():
    db = get_db()
    user_id = int(request.user['sub'])
    payments = [
        dict(row)
        for row in db.execute(
            'SELECT id, amount, paid_on, next_due_date, status FROM premium_payments WHERE user_id = ? ORDER BY id DESC',
            (user_id,),
        ).fetchall()
    ]
    return jsonify({'payments': payments})


@app.post('/pay-weekly-premium')
@auth_required
def pay_weekly_premium():
    db = get_db()
    user_id = int(request.user['sub'])
    policy = db.execute('SELECT premium FROM policies WHERE user_id = ?', (user_id,)).fetchone()
    worker = db.execute('SELECT weekly_premium FROM workers WHERE user_id = ?', (user_id,)).fetchone()

    amount = float((policy['premium'] if policy else 0) or (worker['weekly_premium'] if worker else 0) or 0)
    if amount <= 0:
        return jsonify({'error': 'Premium is not configured yet. Complete onboarding first.'}), 400

    now = datetime.now(timezone.utc)
    next_due = (now + timedelta(days=7)).date().isoformat()

    db.execute(
        'INSERT INTO premium_payments(user_id, amount, next_due_date, status) VALUES (?, ?, ?, ?)',
        (user_id, amount, next_due, 'Paid'),
    )
    db.execute("UPDATE policies SET policy_status = 'Active' WHERE user_id = ?", (user_id,))
    db.commit()

    return jsonify(
        {
            'message': 'Weekly premium payment recorded.',
            'payment': {
                'amount': round(amount, 2),
                'paid_on': now.isoformat(),
                'next_due_date': next_due,
                'status': 'Paid',
            },
        }
    )


@app.get('/weather')
def weather_get():
    latitude = float(request.args.get('lat', 0) or 0)
    longitude = float(request.args.get('lon', 0) or 0)
    city = str(request.args.get('city', '') or '')

    # Resolve via city table if no GPS
    if abs(latitude) < 0.001 or abs(longitude) < 0.001:
        lat_c, lon_c = resolve_coords(0, 0, city)
        if abs(lat_c) > 0.001:
            latitude, longitude = lat_c, lon_c

    if abs(latitude) < 0.001 and abs(longitude) < 0.001:
        return jsonify({'error': 'Provide lat/lon or city query param.'}), 400

    try:
        weather_bundle = _fetch_weather_for_coords(latitude, longitude, city=city)
        location = _reverse_geocode(latitude, longitude)
        payload = {
            'location': {'latitude': latitude, 'longitude': longitude, **location},
            **weather_bundle,
        }
        payload['risk']['reason'] = _derive_risk_reason(payload['weather'], {})
        return jsonify(payload)
    except URLError:
        return jsonify({'error': 'Weather services unreachable.'}), 503


@app.get('/weather-forecast')
def weather_forecast():
    latitude = float(request.args.get('lat', 0) or 0)
    longitude = float(request.args.get('lon', 0) or 0)

    if abs(latitude) < 0.0001 and abs(longitude) < 0.0001:
        return jsonify({'error': 'Valid lat and lon query params are required.'}), 400

    try:
        # Test forecast data
        forecast = [
            {
                'datetime': '2026-04-03T12:00:00+00:00',
                'temperature': 20.5,
                'humidity': 65,
                'wind_speed': 3.2,
                'rain_probability': 10.0,
                'description': 'Partly cloudy',
            },
            {
                'datetime': '2026-04-03T13:00:00+00:00',
                'temperature': 22.0,
                'humidity': 60,
                'wind_speed': 2.8,
                'rain_probability': 5.0,
                'description': 'Sunny',
            },
        ]
        return jsonify({'forecast': forecast})
    except Exception as e:
        return jsonify({'error': f'Unable to fetch forecast: {e}'}), 503


@app.post('/weather-risk')
@auth_required
def weather_risk():
    data = request.get_json(force=True)
    latitude = float(data.get('latitude', 0) or 0)
    longitude = float(data.get('longitude', 0) or 0)

    db = get_db()
    user_id = int(request.user['sub'])
    worker_geo = db.execute(
        'SELECT latitude, longitude, city, manual_location, location_text FROM workers WHERE user_id = ?',
        (user_id,),
    ).fetchone()

    city = ''
    if worker_geo:
        city = str(worker_geo['city'] or '').strip()

    # Resolve coordinates: GPS → saved DB coords → city table → geocode
    if abs(latitude) < 0.001 or abs(longitude) < 0.001:
        if worker_geo:
            saved_lat = float(worker_geo['latitude'] or 0)
            saved_lon = float(worker_geo['longitude'] or 0)
            if abs(saved_lat) > 0.001 and abs(saved_lon) > 0.001:
                latitude, longitude = saved_lat, saved_lon

    # City coordinate table fallback
    if abs(latitude) < 0.001 or abs(longitude) < 0.001:
        lat_c, lon_c = resolve_coords(0, 0, city)
        if abs(lat_c) > 0.001:
            latitude, longitude = lat_c, lon_c

    # Nominatim geocode fallback
    if abs(latitude) < 0.001 or abs(longitude) < 0.001:
        geocode_query = city or (worker_geo and (
            str(worker_geo['location_text'] or '').strip() or
            str(worker_geo['manual_location'] or '').strip()
        )) or ''
        if geocode_query:
            resolved = _forward_geocode(geocode_query)
            if resolved:
                latitude, longitude = resolved

    if abs(latitude) < 0.001 and abs(longitude) < 0.001:
        return jsonify({'error': 'Location unavailable. Select your city in onboarding or enable GPS.'}), 400

    try:
        weather_bundle = _fetch_weather_for_coords(latitude, longitude, city=city)
        location = _reverse_geocode(latitude, longitude)
        worker_row = db.execute(
            'SELECT work_type, working_environment, weekly_working_days FROM workers WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        worker_data = dict(worker_row) if worker_row else {}
        payload = {
            'location': {'latitude': latitude, 'longitude': longitude, **location},
            **weather_bundle,
        }
        payload['risk']['reason'] = _derive_risk_reason(payload['weather'], worker_data)
        return jsonify(payload)
    except URLError:
        return jsonify({'error': 'Weather services unreachable. Using cached data.'}), 503


@app.get('/admin/overview')
@auth_required
def admin_overview():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403

    department = request.args.get('department', '').strip().lower()
    category = request.args.get('category', '').strip().lower()

    db = get_db()
    policies_query = (
        """
        SELECT p.id, p.user_id, p.policy_status, p.premium, p.coverage_amount,
               u.name AS user_name, w.delivery_platform, w.zone_type
        FROM policies p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN workers w ON w.user_id = p.user_id
        """
    )
    params = []
    where = []
    if department:
        where.append('lower(COALESCE(w.zone_type, "")) = ?')
        params.append(department)
    if category:
        where.append('lower(COALESCE(w.delivery_platform, "")) = ?')
        params.append(category)
    if where:
        policies_query += ' WHERE ' + ' AND '.join(where)
    policies_query += ' ORDER BY p.id DESC LIMIT 100'

    policies = [dict(row) for row in db.execute(policies_query, tuple(params)).fetchall()]
    users = [
        {**dict(row), 'role': _public_role(row['role'])}
        for row in db.execute('SELECT id, name, email, role, created_at FROM users ORDER BY id DESC').fetchall()
    ]
    claims = [dict(row) for row in db.execute('SELECT * FROM claims ORDER BY id DESC').fetchall()]
    events = [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id DESC').fetchall()]

    return jsonify({'users': users, 'claims': claims, 'policies': policies, 'events': events})


@app.get('/admin/events')
@auth_required
def admin_events_get():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403

    db = get_db()
    events = [dict(row) for row in db.execute('SELECT * FROM events ORDER BY id DESC').fetchall()]
    return jsonify({'events': events})


@app.post('/admin/events')
@auth_required
def admin_events_create():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(force=True)
    title = str(data.get('title', '')).strip()
    category = str(data.get('category', '')).strip() or 'Policy'
    department = str(data.get('department', '')).strip() or 'Urban'
    event_date = str(data.get('event_date', '')).strip() or datetime.now().date().isoformat()

    if not title:
        return jsonify({'error': 'Event title is required.'}), 400

    db = get_db()
    db.execute(
        'INSERT INTO events(title, category, department, event_date, created_by) VALUES (?, ?, ?, ?, ?)',
        (title, category, department, event_date, int(request.user['sub'])),
    )
    db.commit()
    return jsonify({'message': 'Event created successfully.'}), 201


@app.post('/admin/settings')
@auth_required
def update_settings():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(force=True)
    rainfall_threshold = float(data.get('rainfall_threshold', 100))
    risk_weight = float(data.get('risk_weight', 1.0))

    db = get_db()
    db.execute(
        "INSERT INTO settings(key, value) VALUES('rainfall_threshold', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(rainfall_threshold),),
    )
    db.execute(
        "INSERT INTO settings(key, value) VALUES('risk_weight', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(risk_weight),),
    )
    db.commit()

    return jsonify({'message': 'Settings updated'})


@app.get('/')
def frontend_home():
    return _render_frontend()


@app.get('/assets/<path:filename>')
def frontend_assets(filename):
    return send_from_directory(FRONTEND_ASSETS_DIR, filename)


@app.get('/favicon.svg')
def frontend_favicon():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.svg')


@app.get('/icons.svg')
def frontend_icons():
    return send_from_directory(FRONTEND_DIST_DIR, 'icons.svg')


@app.get('/health')
def healthcheck():
    return jsonify({'service': 'GigCover AI backend', 'status': 'ok'})


@app.get('/<path:path>')
def frontend_spa(path):
    potential_file = os.path.join(FRONTEND_DIST_DIR, path)
    if os.path.isfile(potential_file):
        return send_from_directory(FRONTEND_DIST_DIR, path)
    return _render_frontend()


# ---------------------------------------------------------------------------
# PARAMETRIC INSURANCE ENDPOINTS
# ---------------------------------------------------------------------------

def _all_settings(db):
    rows = db.execute('SELECT key, value FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows}


def _log_transaction(db, user_id, claim_id, txn_type, amount, method, status,
                     gateway_ref='', utr='', rollback_reason='', attempts=None, settled_at=None):
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        'INSERT INTO transactions(user_id,claim_id,txn_type,amount,method,status,gateway_ref,utr,rollback_reason,attempts,created_at,settled_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        (user_id, claim_id, txn_type, amount, method, status, gateway_ref,
         utr or '', rollback_reason or '', json.dumps(attempts or []), now, settled_at),
    )


@app.post('/parametric/log-activity')
@auth_required
def log_activity():
    data = request.get_json(force=True)
    user_id = int(request.user['sub'])
    lat = float(data.get('latitude', 0))
    lon = float(data.get('longitude', 0))
    speed = float(data.get('speed_kmh', 0))
    platform_active = int(data.get('platform_active', 1))
    if abs(lat) < 0.0001 and abs(lon) < 0.0001:
        return jsonify({'error': 'Valid coordinates required'}), 400
    db = get_db()
    db.execute(
        'INSERT INTO activity_logs(user_id,latitude,longitude,speed_kmh,platform_active) VALUES(?,?,?,?,?)',
        (user_id, lat, lon, speed, platform_active),
    )
    db.commit()
    return jsonify({'message': 'Activity logged'})


@app.post('/parametric/trigger')
@auth_required
def parametric_trigger():
    data = request.get_json(force=True) or {}
    db = get_db()
    user_id = int(request.user['sub'])
    settings = _all_settings(db)

    lat = float(data.get('latitude', 0) or 0)
    lon = float(data.get('longitude', 0) or 0)
    if abs(lat) < 0.0001 or abs(lon) < 0.0001:
        row = db.execute('SELECT latitude, longitude FROM workers WHERE user_id=?', (user_id,)).fetchone()
        if row:
            lat, lon = float(row['latitude'] or 0), float(row['longitude'] or 0)
    if abs(lat) < 0.0001 or abs(lon) < 0.0001:
        return jsonify({'error': 'Location required'}), 400

    try:
        wb = _fetch_weather_for_coords(lat, lon)
    except Exception as e:
        return jsonify({'error': f'Weather fetch failed: {e}'}), 503

    aqi = float(data.get('aqi', 0) or _fetch_aqi_for_coords(lat, lon))
    weather = wb.get('weather', {})

    fired_triggers = evaluate_triggers(weather, aqi, settings)
    if not fired_triggers:
        return jsonify({'triggered': False, 'message': 'No parametric thresholds breached', 'weather': weather, 'aqi': aqi})

    worker = db.execute('SELECT * FROM workers WHERE user_id=?', (user_id,)).fetchone()
    policy = db.execute('SELECT * FROM policies WHERE user_id=?', (user_id,)).fetchone()
    worker_dict = dict(worker) if worker else {}
    policy_dict = dict(policy) if policy else {}

    if policy_dict.get('policy_status') != 'Active':
        return jsonify({'error': 'No active policy. Pay weekly premium to activate coverage.'}), 403

    uw = check_underwriting_eligibility(worker_dict, settings)
    if not uw['eligible']:
        return jsonify({'triggered': True, 'eligible': False, 'reason': uw['reason'], 'fired_triggers': fired_triggers})

    totals = db.execute(
        'SELECT COALESCE(SUM(payout),0) AS cp, (SELECT COALESCE(SUM(amount),0) FROM premium_payments) AS tp FROM claims WHERE status="Approved"'
    ).fetchone()
    bcr_data = compute_bcr(float(totals['cp']), float(totals['tp']))
    if bcr_data['halt_enrollments']:
        return jsonify({'triggered': True, 'eligible': False, 'reason': 'System paused: loss ratio critical', 'bcr': bcr_data})

    logs = [dict(r) for r in db.execute(
        "SELECT latitude,longitude,speed_kmh,platform_active,logged_at FROM activity_logs WHERE user_id=? AND logged_at >= datetime('now','-4 hours') ORDER BY logged_at",
        (user_id,),
    ).fetchall()]

    fraud_block_threshold = float(settings.get('fraud_score_block', 0.75))
    trigger_time = datetime.now(timezone.utc)
    fraud_result = compute_fraud_score(worker_dict, logs, trigger_time)
    payout_per_day = float(settings.get('payout_per_day', worker_dict.get('daily_income', 500)))
    results = []

    for trig in fired_triggers:
        trig_type = trig['trigger_type']
        cur = db.execute(
            'INSERT INTO trigger_events(trigger_type,city,latitude,longitude,threshold_value,observed_value,status) VALUES(?,?,?,?,?,?,?)',
            (trig_type, worker_dict.get('city', ''), lat, lon, trig['threshold_value'], trig['observed_value'], 'Active'),
        )
        trigger_event_id = cur.lastrowid

        if fraud_result['fraud_score'] >= fraud_block_threshold:
            db.execute('UPDATE trigger_events SET status=? WHERE id=?', ('Fraud_Blocked', trigger_event_id))
            results.append({
                'trigger_type': trig_type,
                'decision': 'Blocked',
                'reason': 'High fraud risk score',
                'fraud_score': fraud_result['fraud_score'],
                'fraud_flags': fraud_result['flags'],
            })
            continue

        count_row = db.execute('SELECT COUNT(*) AS c FROM claims').fetchone()
        claim_id = f'CLM{(count_row["c"] if count_row else 0) + 101}'
        now_iso = datetime.now(timezone.utc).isoformat()

        db.execute(
            'INSERT INTO claims(claim_id,user_id,trigger_event_id,trigger_type,lost_hours,payout,status,fraud_score,fraud_flags,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (claim_id, user_id, trigger_event_id, trig_type, 8.0, payout_per_day, 'Processing',
             fraud_result['fraud_score'], json.dumps(fraud_result['flags']), now_iso),
        )

        try:
            txn = process_payout(user_id, claim_id, payout_per_day, method='UPI')
            final_status = 'Approved' if txn['status'] == 'Success' else 'Failed'
            if txn['status'] == 'Rolled_Back':
                final_status = 'Failed'
            db.execute('UPDATE claims SET status=? WHERE claim_id=?', (final_status, claim_id))
            _log_transaction(
                db, user_id, claim_id, 'payout', payout_per_day,
                txn.get('method_used') or 'UPI',
                txn['status'],
                gateway_ref=txn.get('gateway_ref', ''),
                utr=txn.get('utr', ''),
                rollback_reason=txn.get('rollback_reason', ''),
                attempts=txn.get('attempts', []),
                settled_at=txn.get('settled_at'),
            )
            if final_status == 'Approved':
                db.execute('UPDATE trigger_events SET status=?,resolved_at=? WHERE id=?', ('Resolved', now_iso, trigger_event_id))
        except Exception as e:
            db.execute('UPDATE claims SET status=? WHERE claim_id=?', ('Failed', claim_id))
            _log_transaction(db, user_id, claim_id, 'payout', payout_per_day, 'UPI', 'Failed',
                             rollback_reason=str(e))
            txn = {'status': 'Failed', 'reason': str(e)}
            final_status = 'Failed'

        db.commit()
        results.append({
            'trigger_type': trig_type,
            'decision': final_status,
            'claim_id': claim_id,
            'payout': payout_per_day,
            'fraud_score': fraud_result['fraud_score'],
            'transaction': txn,
            'observed_value': trig['observed_value'],
            'threshold_value': trig['threshold_value'],
        })

    db.commit()
    return jsonify({
        'triggered': True,
        'eligible': True,
        'tier': uw['tier'],
        'fired_triggers': fired_triggers,
        'results': results,
        'weather': weather,
        'aqi': aqi,
        'fraud_score': fraud_result['fraud_score'],
        'fraud_flags': fraud_result['flags'],
        'bcr': bcr_data,
    })


@app.get('/parametric/premium')
@auth_required
def parametric_premium():
    db = get_db()
    user_id = int(request.user['sub'])
    worker = db.execute('SELECT daily_income, city, zone_type FROM workers WHERE user_id=?', (user_id,)).fetchone()
    if not worker:
        return jsonify({'error': 'Worker profile not found'}), 404
    daily_income = float(worker['daily_income'] or 500)
    city = str(worker['city'] or '').lower()
    city_trigger_prob = {
        'mumbai': 0.072, 'delhi': 0.065, 'kolkata': 0.068,
        'chennai': 0.060, 'bengaluru': 0.045, 'bangalore': 0.045,
        'hyderabad': 0.050, 'pune': 0.042,
    }
    trigger_prob = city_trigger_prob.get(city, 0.055)
    avg_income_loss = daily_income * 0.6
    result = compute_parametric_premium(trigger_prob, avg_income_loss, exposure_days=7)
    return jsonify(result)


@app.get('/parametric/actuarial')
@auth_required
def actuarial_report():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403
    db = get_db()
    totals = db.execute(
        'SELECT COALESCE(SUM(payout),0) AS cp, (SELECT COALESCE(SUM(amount),0) FROM premium_payments) AS tp FROM claims WHERE status="Approved"'
    ).fetchone()
    cp, tp = float(totals['cp']), float(totals['tp'])
    bcr_data = compute_bcr(cp, tp)
    settings = _all_settings(db)
    payout_per_day = float(settings.get('payout_per_day', 500))
    stress = stress_test_bcr(bcr_data['bcr'], payout_per_day, max(tp, 1), stress_days=14)
    active_workers = db.execute("SELECT COUNT(*) AS c FROM policies WHERE policy_status='Active'").fetchone()['c']
    total_triggers = db.execute('SELECT COUNT(*) AS c FROM trigger_events').fetchone()['c']
    return jsonify({
        'bcr': bcr_data,
        'stress_test_14_days': stress,
        'active_workers': active_workers,
        'total_trigger_events': total_triggers,
    })


@app.get('/parametric/transactions')
@auth_required
def get_transactions():
    db = get_db()
    user_id = int(request.user['sub'])
    rows = db.execute(
        'SELECT id,claim_id,txn_type,amount,method,status,gateway_ref,utr,rollback_reason,attempts,created_at,settled_at FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 50',
        (user_id,),
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        try:
            row['attempts'] = json.loads(row.get('attempts') or '[]')
        except Exception:
            row['attempts'] = []
        result.append(row)
    return jsonify({'transactions': result})


@app.post('/parametric/settle')
@auth_required
def manual_settle():
    """Admin: manually re-attempt settlement for a failed/rolled-back claim."""
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True)
    claim_id = str(data.get('claim_id', '')).strip()
    if not claim_id:
        return jsonify({'error': 'claim_id required'}), 400

    db = get_db()
    claim = db.execute('SELECT * FROM claims WHERE claim_id=?', (claim_id,)).fetchone()
    if not claim:
        return jsonify({'error': 'Claim not found'}), 404
    if claim['status'] == 'Approved':
        return jsonify({'error': 'Claim already settled'}), 409

    user_id = int(claim['user_id'])
    amount = float(claim['payout'])
    method = str(data.get('method', 'UPI'))
    use_razorpay = bool(data.get('use_razorpay_sandbox', False))

    txn = process_payout(user_id, claim_id, amount, method=method,
                         use_razorpay_sandbox=use_razorpay)
    final_status = 'Approved' if txn['status'] == 'Success' else 'Failed'
    db.execute('UPDATE claims SET status=? WHERE claim_id=?', (final_status, claim_id))
    _log_transaction(
        db, user_id, claim_id, 'payout', amount,
        txn.get('method_used') or method,
        txn['status'],
        gateway_ref=txn.get('gateway_ref', ''),
        utr=txn.get('utr', ''),
        rollback_reason=txn.get('rollback_reason', ''),
        attempts=txn.get('attempts', []),
        settled_at=txn.get('settled_at'),
    )
    db.commit()
    return jsonify({'claim_id': claim_id, 'settlement': txn, 'claim_status': final_status})


@app.post('/parametric/reconcile')
@auth_required
def run_reconciliation():
    """Admin: resolve stale Pending transactions."""
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True) or {}
    stale_minutes = int(data.get('stale_minutes', 10))
    db = get_db()
    result = reconcile_pending(db, stale_minutes=stale_minutes)
    return jsonify({'reconciliation': result})


@app.get('/parametric/reconciliation-report')
@auth_required
def reconciliation_report():
    """Admin: full transaction reconciliation report."""
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403
    db = get_db()
    report = daily_reconciliation_report(db)
    return jsonify(report)


@app.get('/parametric/trigger-events')
@auth_required
def get_trigger_events():
    db = get_db()
    if _is_admin_role(request.user['role']):
        rows = db.execute('SELECT * FROM trigger_events ORDER BY id DESC LIMIT 100').fetchall()
    else:
        user_id = int(request.user['sub'])
        worker = db.execute('SELECT city FROM workers WHERE user_id=?', (user_id,)).fetchone()
        city = worker['city'] if worker else ''
        rows = db.execute('SELECT * FROM trigger_events WHERE city=? ORDER BY id DESC LIMIT 50', (city,)).fetchall()
    return jsonify({'trigger_events': [dict(r) for r in rows]})


@app.post('/parametric/settings')
@auth_required
def update_parametric_settings():
    if not _is_admin_role(request.user['role']):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True)
    db = get_db()
    allowed = ['aqi_threshold', 'rainfall_threshold', 'wind_threshold', 'visibility_threshold',
               'payout_per_day', 'min_working_days', 'fraud_score_block', 'loss_ratio_halt']
    for key in allowed:
        if key in data:
            db.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, str(data[key])))
    db.commit()
    return jsonify({'message': 'Parametric settings updated', 'updated': {k: data[k] for k in allowed if k in data}})


# ---------------------------------------------------------------------------
# PHASE 2: POLICY MANAGEMENT
# ---------------------------------------------------------------------------

@app.post('/policy/toggle')
@auth_required
def policy_toggle():
    """Start or stop a worker's policy (Active <-> Suspended)."""
    db = get_db()
    user_id = int(request.user['sub'])
    policy = db.execute('SELECT policy_status FROM policies WHERE user_id=?', (user_id,)).fetchone()
    if not policy:
        return jsonify({'error': 'Policy not found'}), 404
    current = policy['policy_status']
    new_status = 'Suspended' if current == 'Active' else 'Active'
    db.execute('UPDATE policies SET policy_status=? WHERE user_id=?', (new_status, user_id))
    db.commit()
    msg = 'Policy suspended. Coverage paused.' if new_status == 'Suspended' else 'Policy activated. Coverage resumed.'
    return jsonify({'policy_status': new_status, 'message': msg})


@app.get('/policy/details')
@auth_required
def policy_details():
    """Full policy details with trigger conditions and coverage info."""
    db = get_db()
    user_id = int(request.user['sub'])
    settings = _all_settings(db)
    worker = db.execute('SELECT * FROM workers WHERE user_id=?', (user_id,)).fetchone()
    policy = db.execute('SELECT * FROM policies WHERE user_id=?', (user_id,)).fetchone()
    if not policy:
        return jsonify({'error': 'Policy not found'}), 404
    w = dict(worker) if worker else {}
    p = dict(policy)
    payout_per_day = float(settings.get('payout_per_day', w.get('daily_income', 500)))
    return jsonify({
        'policy': p,
        'worker': {'city': w.get('city'), 'zone_type': w.get('zone_type'), 'platform': w.get('delivery_platform'), 'tier': w.get('tier', 'standard')},
        'coverage': {
            'weekly_premium': round(float(p.get('premium', 0)), 2),
            'coverage_amount': round(float(p.get('coverage_amount', 0)), 2),
            'payout_per_trigger_day': payout_per_day,
            'coverage_hours': '6am – 10pm (active shift)',
        },
        'trigger_conditions': [
            {'trigger': 'Heavy Rain',    'threshold': f"Rain probability > {settings.get('rainfall_threshold', 65)}%",  'payout': f'₹{payout_per_day}/day'},
            {'trigger': 'High AQI',      'threshold': f"AQI > {settings.get('aqi_threshold', 300)}",                    'payout': f'₹{payout_per_day}/day'},
            {'trigger': 'Strong Wind',   'threshold': f"Wind > {settings.get('wind_threshold', 15)} m/s",               'payout': f'₹{payout_per_day}/day'},
            {'trigger': 'Low Visibility','threshold': f"Visibility < {settings.get('visibility_threshold', 1500)} m",   'payout': f'₹{payout_per_day}/day'},
            {'trigger': 'Extreme Heat',  'threshold': 'Temperature > 42°C',                                              'payout': f'₹{payout_per_day}/day'},
        ],
        'premium_formula': 'premium = base_price × risk_factor × activity_factor',
    })


# ---------------------------------------------------------------------------
# PHASE 2: DEMO TRIGGER SIMULATION (for demo video)
# ---------------------------------------------------------------------------

@app.post('/demo/simulate-trigger')
@auth_required
def demo_simulate_trigger():
    """
    Demo endpoint: inject a mock trigger scenario without real weather API.
    Body: {"scenario": "aqi" | "rain" | "heat" | "wind" | "flood"}
    Runs full pipeline: eligibility → fraud → payout → log.
    """
    data = request.get_json(force=True) or {}
    scenario = str(data.get('scenario', 'rain')).lower()
    db = get_db()
    user_id = int(request.user['sub'])
    settings = _all_settings(db)

    SCENARIOS = {
        'rain':  {'trigger_type': 'Heavy Rain',     'observed': 78.0,  'threshold': 65.0,  'weather': {'rain_probability': 78, 'wind_speed': 4, 'visibility': 6000, 'temperature': 28, 'humidity': 90}},
        'aqi':   {'trigger_type': 'High AQI',       'observed': 340.0, 'threshold': 300.0, 'weather': {'rain_probability': 5,  'wind_speed': 2, 'visibility': 3000, 'temperature': 32, 'humidity': 55}},
        'heat':  {'trigger_type': 'Extreme Heat',   'observed': 44.0,  'threshold': 42.0,  'weather': {'rain_probability': 2,  'wind_speed': 3, 'visibility': 8000, 'temperature': 44, 'humidity': 30}},
        'wind':  {'trigger_type': 'Strong Wind',    'observed': 18.0,  'threshold': 15.0,  'weather': {'rain_probability': 20, 'wind_speed': 18,'visibility': 5000, 'temperature': 26, 'humidity': 65}},
        'flood': {'trigger_type': 'Heavy Rain',     'observed': 92.0,  'threshold': 65.0,  'weather': {'rain_probability': 92, 'wind_speed': 8, 'visibility': 1200, 'temperature': 27, 'humidity': 95}},
    }
    sc = SCENARIOS.get(scenario, SCENARIOS['rain'])

    worker = db.execute('SELECT * FROM workers WHERE user_id=?', (user_id,)).fetchone()
    policy = db.execute('SELECT * FROM policies WHERE user_id=?', (user_id,)).fetchone()
    if not worker or not policy:
        return jsonify({'error': 'Complete onboarding first'}), 400
    if dict(policy).get('policy_status') != 'Active':
        return jsonify({'error': 'Policy not active. Pay weekly premium first.'}), 403

    worker_dict = dict(worker)
    uw = check_underwriting_eligibility(worker_dict, settings)

    # For demo: bypass min_working_days check
    uw['eligible'] = True

    fraud_result = compute_fraud_score(worker_dict, [], datetime.now(timezone.utc))
    # For demo: clear fraud flags so payout proceeds
    fraud_result['fraud_score'] = 0.0
    fraud_result['flags'] = []

    payout_per_day = float(settings.get('payout_per_day', worker_dict.get('daily_income', 500)))

    cur = db.execute(
        'INSERT INTO trigger_events(trigger_type,city,latitude,longitude,threshold_value,observed_value,status) VALUES(?,?,?,?,?,?,?)',
        (sc['trigger_type'], worker_dict.get('city', 'Demo'), worker_dict.get('latitude', 0),
         worker_dict.get('longitude', 0), sc['threshold'], sc['observed'], 'Active'),
    )
    trigger_event_id = cur.lastrowid

    count_row = db.execute('SELECT COUNT(*) AS c FROM claims').fetchone()
    claim_id = f'CLM{(count_row["c"] if count_row else 0) + 101}'
    now_iso = datetime.now(timezone.utc).isoformat()

    db.execute(
        'INSERT INTO claims(claim_id,user_id,trigger_event_id,trigger_type,lost_hours,payout,status,fraud_score,fraud_flags,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (claim_id, user_id, trigger_event_id, sc['trigger_type'], 8.0, payout_per_day, 'Processing', 0.0, '[]', now_iso),
    )

    txn = process_payout(user_id, claim_id, payout_per_day, method='UPI')
    final_status = 'Approved' if txn['status'] == 'Success' else 'Failed'
    db.execute('UPDATE claims SET status=? WHERE claim_id=?', (final_status, claim_id))
    _log_transaction(
        db, user_id, claim_id, 'payout', payout_per_day,
        txn.get('method_used') or 'UPI', txn['status'],
        gateway_ref=txn.get('gateway_ref', ''), utr=txn.get('utr', ''),
        rollback_reason=txn.get('rollback_reason', ''),
        attempts=txn.get('attempts', []), settled_at=txn.get('settled_at'),
    )
    db.execute('UPDATE trigger_events SET status=?,resolved_at=? WHERE id=?', ('Resolved', now_iso, trigger_event_id))
    db.commit()

    notification = {
        'aqi':   f'🌫️ High AQI ({sc["observed"]}) detected in your area. You\'re covered! ₹{payout_per_day} credited.',
        'rain':  f'🌧️ Heavy rain ({sc["observed"]}% probability) detected. Auto-claim processed! ₹{payout_per_day} credited.',
        'heat':  f'🌡️ Heatwave alert ({sc["observed"]}°C). Coverage activated! ₹{payout_per_day} credited.',
        'wind':  f'💨 Strong wind ({sc["observed"]} m/s) detected. Payout initiated! ₹{payout_per_day} credited.',
        'flood': f'🌊 Flood alert triggered. Zero-touch claim processed! ₹{payout_per_day} credited.',
    }.get(scenario, f'Trigger fired. ₹{payout_per_day} credited.')

    return jsonify({
        'scenario': scenario,
        'trigger_type': sc['trigger_type'],
        'observed_value': sc['observed'],
        'threshold_value': sc['threshold'],
        'claim_id': claim_id,
        'payout': payout_per_day,
        'claim_status': final_status,
        'transaction': txn,
        'notification': notification,
        'pipeline': ['Trigger Detected', 'Policy Validated', 'Fraud Check Passed', 'Claim Created', 'Payment Processed'],
    })


# ---------------------------------------------------------------------------
# PHASE 2: SCHEDULER (background trigger polling)
# ---------------------------------------------------------------------------

def _run_scheduled_triggers():
    """
    Background job: poll all active workers, check triggers, auto-process payouts.
    Runs every 5 minutes via threading.Timer.
    """
    import threading
    try:
        with app.app_context():
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            settings = {r['key']: r['value'] for r in db.execute('SELECT key,value FROM settings').fetchall()}
            workers = db.execute(
                "SELECT w.user_id, w.latitude, w.longitude, w.city, w.daily_income, w.onboarding_complete, "
                "w.enrollment_date, w.weekly_working_days, w.tier, p.policy_status "
                "FROM workers w JOIN policies p ON p.user_id=w.user_id "
                "WHERE p.policy_status='Active' AND w.onboarding_complete=1 "
                "AND (ABS(w.latitude)>0.0001 OR ABS(w.longitude)>0.0001)"
            ).fetchall()

            for worker_row in workers:
                try:
                    lat = float(worker_row['latitude'] or 0)
                    lon = float(worker_row['longitude'] or 0)
                    if abs(lat) < 0.0001 and abs(lon) < 0.0001:
                        continue
                    wb = _fetch_weather_for_coords(lat, lon)
                    aqi = _fetch_aqi_for_coords(lat, lon)
                    weather = wb.get('weather', {})
                    fired = evaluate_triggers(weather, aqi, settings)
                    if not fired:
                        continue
                    worker_dict = dict(worker_row)
                    uw = check_underwriting_eligibility(worker_dict, settings)
                    if not uw['eligible']:
                        continue
                    totals = db.execute(
                        'SELECT COALESCE(SUM(payout),0) AS cp, (SELECT COALESCE(SUM(amount),0) FROM premium_payments) AS tp FROM claims WHERE status="Approved"'
                    ).fetchone()
                    bcr = compute_bcr(float(totals['cp']), float(totals['tp']))
                    if bcr['halt_enrollments']:
                        continue
                    logs = [dict(r) for r in db.execute(
                        "SELECT latitude,longitude,speed_kmh,platform_active,logged_at FROM activity_logs "
                        "WHERE user_id=? AND logged_at>=datetime('now','-4 hours')",
                        (worker_row['user_id'],),
                    ).fetchall()]
                    fraud = compute_fraud_score(worker_dict, logs, datetime.now(timezone.utc))
                    if fraud['fraud_score'] >= float(settings.get('fraud_score_block', 0.75)):
                        continue
                    payout = float(settings.get('payout_per_day', worker_dict.get('daily_income', 500)))
                    for trig in fired:
                        cur = db.execute(
                            'INSERT INTO trigger_events(trigger_type,city,latitude,longitude,threshold_value,observed_value,status) VALUES(?,?,?,?,?,?,?)',
                            (trig['trigger_type'], worker_dict.get('city', ''), lat, lon,
                             trig['threshold_value'], trig['observed_value'], 'Active'),
                        )
                        tev_id = cur.lastrowid
                        c_row = db.execute('SELECT COUNT(*) AS c FROM claims').fetchone()
                        claim_id = f'CLM{(c_row["c"] if c_row else 0) + 101}'
                        now_iso = datetime.now(timezone.utc).isoformat()
                        db.execute(
                            'INSERT INTO claims(claim_id,user_id,trigger_event_id,trigger_type,lost_hours,payout,status,fraud_score,fraud_flags,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (claim_id, worker_row['user_id'], tev_id, trig['trigger_type'], 8.0, payout, 'Processing', fraud['fraud_score'], json.dumps(fraud['flags']), now_iso),
                        )
                        txn = process_payout(worker_row['user_id'], claim_id, payout, method='UPI')
                        final = 'Approved' if txn['status'] == 'Success' else 'Failed'
                        db.execute('UPDATE claims SET status=? WHERE claim_id=?', (final, claim_id))
                        db.execute(
                            'INSERT INTO transactions(user_id,claim_id,txn_type,amount,method,status,gateway_ref,utr,rollback_reason,attempts,settled_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (worker_row['user_id'], claim_id, 'payout', payout,
                             txn.get('method_used') or 'UPI', txn['status'],
                             txn.get('gateway_ref', ''), txn.get('utr', ''),
                             txn.get('rollback_reason', ''), json.dumps(txn.get('attempts', [])),
                             txn.get('settled_at')),
                        )
                        if final == 'Approved':
                            db.execute('UPDATE trigger_events SET status=?,resolved_at=? WHERE id=?', ('Resolved', now_iso, tev_id))
                        db.commit()
                except Exception:
                    pass
            db.close()
    except Exception:
        pass
    finally:
        import threading
        t = threading.Timer(300, _run_scheduled_triggers)  # every 5 minutes
        t.daemon = True
        t.start()


# Start scheduler only in main process (not reloader child)
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true' or not os.environ.get('FLASK_DEBUG', '').lower() == 'true':
    import threading as _th
    _sched = _th.Timer(60, _run_scheduled_triggers)  # first run after 60s
    _sched.daemon = True
    _sched.start()


# ---------------------------------------------------------------------------
# 5-TRIGGER CHECK ENDPOINT
# ---------------------------------------------------------------------------

@app.post('/triggers/check')
@auth_required
def triggers_check():
    """
    Run all 5 triggers for the current worker.
    Resolves location from: request body → DB GPS → city coord table.
    Returns full trigger evaluation + auto-processes payouts for fired triggers.
    """
    data = request.get_json(force=True) or {}
    db = get_db()
    user_id = int(request.user['sub'])
    settings = _all_settings(db)

    # Resolve coordinates
    lat = float(data.get('latitude', 0) or 0)
    lon = float(data.get('longitude', 0) or 0)
    worker = db.execute('SELECT * FROM workers WHERE user_id=?', (user_id,)).fetchone()
    policy = db.execute('SELECT * FROM policies WHERE user_id=?', (user_id,)).fetchone()

    if not worker:
        return jsonify({'error': 'Complete onboarding first.'}), 400

    worker_dict = dict(worker)
    city = str(worker_dict.get('city') or '').strip()
    platform = str(worker_dict.get('delivery_platform') or '').strip().lower()

    if abs(lat) < 0.001 or abs(lon) < 0.001:
        lat = float(worker_dict.get('latitude') or 0)
        lon = float(worker_dict.get('longitude') or 0)

    # City coordinate table fallback
    if abs(lat) < 0.001 or abs(lon) < 0.001:
        lat, lon = resolve_coords(0, 0, city)

    if abs(lat) < 0.001 and abs(lon) < 0.001:
        return jsonify({'error': f'Location unavailable for {city or "your city"}. Update location in profile.'}), 400

    # Run all 5 triggers
    trigger_result = run_all_triggers(
        lat, lon, city=city, platform=platform,
        api_key=OPENWEATHER_API_KEY, settings=settings
    )

    if not trigger_result['any_fired']:
        return jsonify({
            'any_fired': False,
            'message': 'All clear. No income disruption triggers detected.',
            'triggers': trigger_result['triggers'],
            'weather': trigger_result['weather'],
            'aqi': trigger_result['aqi'],
            'demand': trigger_result['demand'],
            'evaluated_at': trigger_result['evaluated_at'],
        })

    # Policy check
    policy_dict = dict(policy) if policy else {}
    if policy_dict.get('policy_status') != 'Active':
        return jsonify({
            'any_fired': True,
            'triggers': trigger_result['triggers'],
            'fired_triggers': trigger_result['fired_triggers'],
            'error': 'Triggers fired but policy is not active. Pay weekly premium to activate coverage.',
        }), 403

    # Underwriting eligibility
    uw = check_underwriting_eligibility(worker_dict, settings)

    # BCR halt check
    totals = db.execute(
        'SELECT COALESCE(SUM(payout),0) AS cp, (SELECT COALESCE(SUM(amount),0) FROM premium_payments) AS tp FROM claims WHERE status="Approved"'
    ).fetchone()
    bcr_data = compute_bcr(float(totals['cp']), float(totals['tp']))

    # Fraud check
    logs = [dict(r) for r in db.execute(
        "SELECT latitude,longitude,speed_kmh,platform_active,logged_at FROM activity_logs "
        "WHERE user_id=? AND logged_at>=datetime('now','-4 hours') ORDER BY logged_at",
        (user_id,),
    ).fetchall()]
    fraud_result = compute_fraud_score(worker_dict, logs, __import__('datetime').datetime.now(__import__('datetime').timezone.utc))
    fraud_block = float(settings.get('fraud_score_block', 0.75))
    payout_per_day = float(settings.get('payout_per_day', worker_dict.get('daily_income', 500)))

    payout_results = []
    notifications = []

    for trig in trigger_result['fired_triggers']:
        trig_type = trig['trigger_type']

        # Log trigger event
        cur = db.execute(
            'INSERT INTO trigger_events(trigger_type,city,latitude,longitude,threshold_value,observed_value,status) VALUES(?,?,?,?,?,?,?)',
            (trig_type, city, lat, lon, trig['threshold_value'], trig['observed_value'], 'Active'),
        )
        tev_id = cur.lastrowid

        # Skip if not eligible or BCR halted
        if not uw['eligible'] or bcr_data['halt_enrollments']:
            reason = uw['reason'] if not uw['eligible'] else 'System paused: loss ratio critical'
            payout_results.append({'trigger_type': trig_type, 'decision': 'Skipped', 'reason': reason})
            continue

        # Fraud block
        if fraud_result['fraud_score'] >= fraud_block:
            db.execute('UPDATE trigger_events SET status=? WHERE id=?', ('Fraud_Blocked', tev_id))
            payout_results.append({
                'trigger_type': trig_type, 'decision': 'Blocked',
                'reason': 'Fraud risk detected', 'fraud_score': fraud_result['fraud_score'],
            })
            notifications.append(f'\u26a0\ufe0f {trig_type} trigger blocked due to fraud risk.')
            continue

        # Create claim
        c_row = db.execute('SELECT COUNT(*) AS c FROM claims').fetchone()
        claim_id = f'CLM{(c_row["c"] if c_row else 0) + 101}'
        now_iso = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

        db.execute(
            'INSERT INTO claims(claim_id,user_id,trigger_event_id,trigger_type,lost_hours,payout,status,fraud_score,fraud_flags,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (claim_id, user_id, tev_id, trig_type, 8.0, payout_per_day, 'Processing',
             fraud_result['fraud_score'], json.dumps(fraud_result['flags']), now_iso),
        )

        # Process payout
        txn = process_payout(user_id, claim_id, payout_per_day, method='UPI')
        final_status = 'Approved' if txn['status'] == 'Success' else 'Failed'
        db.execute('UPDATE claims SET status=? WHERE claim_id=?', (final_status, claim_id))
        _log_transaction(
            db, user_id, claim_id, 'payout', payout_per_day,
            txn.get('method_used') or 'UPI', txn['status'],
            gateway_ref=txn.get('gateway_ref', ''), utr=txn.get('utr', ''),
            rollback_reason=txn.get('rollback_reason', ''),
            attempts=txn.get('attempts', []), settled_at=txn.get('settled_at'),
        )
        if final_status == 'Approved':
            db.execute('UPDATE trigger_events SET status=?,resolved_at=? WHERE id=?', ('Resolved', now_iso, tev_id))

        db.commit()

        payout_results.append({
            'trigger_type': trig_type,
            'decision': final_status,
            'claim_id': claim_id,
            'payout': payout_per_day,
            'severity': trig['severity'],
            'income_disruption_pct': trig['income_disruption_pct'],
            'transaction': {'status': txn['status'], 'gateway_ref': txn.get('gateway_ref', ''), 'utr': txn.get('utr', '')},
        })

        # Build notification
        NOTIF = {
            'Heavy Rain':          f'\U0001f327\ufe0f Heavy rain detected ({trig["observed_value"]}%). You\'re covered! \u20b9{payout_per_day:.0f} credited.',
            'High AQI':            f'\U0001f32b\ufe0f Hazardous AQI ({trig["observed_value"]:.0f}) in your area. Coverage activated! \u20b9{payout_per_day:.0f} credited.',
            'Heatwave':            f'\U0001f321\ufe0f Heatwave alert ({trig["observed_value"]}\u00b0C). Stay safe! \u20b9{payout_per_day:.0f} credited.',
            'Flood / Storm':       f'\U0001f30a Storm/flood alert. Roads unsafe. \u20b9{payout_per_day:.0f} credited.',
            'Low Platform Demand': f'\U0001f4c9 Low order demand ({trig["observed_value"]}). Income protected! \u20b9{payout_per_day:.0f} credited.',
        }
        notifications.append(NOTIF.get(trig_type, f'{trig_type} trigger fired. \u20b9{payout_per_day:.0f} credited.'))

    db.commit()

    total_payout = sum(r['payout'] for r in payout_results if r.get('decision') == 'Approved')

    return jsonify({
        'any_fired': True,
        'fired_count': trigger_result['fired_count'],
        'triggers': trigger_result['triggers'],
        'fired_triggers': trigger_result['fired_triggers'],
        'payout_results': payout_results,
        'total_payout': total_payout,
        'notifications': notifications,
        'fraud_score': fraud_result['fraud_score'],
        'fraud_flags': fraud_result['flags'],
        'weather': trigger_result['weather'],
        'aqi': trigger_result['aqi'],
        'demand': trigger_result['demand'],
        'evaluated_at': trigger_result['evaluated_at'],
        'max_income_disruption_pct': trigger_result['max_income_disruption_pct'],
    })


@app.get('/triggers/status')
@auth_required
def triggers_status():
    """Get current trigger thresholds and last evaluation for the worker's city."""
    db = get_db()
    user_id = int(request.user['sub'])
    settings = _all_settings(db)
    worker = db.execute('SELECT city, latitude, longitude, delivery_platform FROM workers WHERE user_id=?', (user_id,)).fetchone()
    city = str(worker['city'] or '') if worker else ''
    lat = float(worker['latitude'] or 0) if worker else 0
    lon = float(worker['longitude'] or 0) if worker else 0
    if abs(lat) < 0.001:
        lat, lon = resolve_coords(0, 0, city)

    recent_events = [dict(r) for r in db.execute(
        "SELECT trigger_type, observed_value, threshold_value, status, triggered_at FROM trigger_events "
        "WHERE city=? ORDER BY id DESC LIMIT 10", (city,)
    ).fetchall()]

    return jsonify({
        'city': city,
        'thresholds': {
            'rain_pct':    float(settings.get('rainfall_threshold', 65)),
            'aqi':         float(settings.get('aqi_threshold', 300)),
            'temp_c':      float(settings.get('heat_threshold', 42)),
            'wind_ms':     float(settings.get('wind_threshold', 15)),
            'visibility_m':float(settings.get('visibility_threshold', 1500)),
            'demand_index':float(settings.get('demand_threshold', 0.45)),
        },
        'recent_trigger_events': recent_events,
        'location': {'lat': lat, 'lon': lon, 'city': city},
    })


init_db()
model = load_model()

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', '5000')),
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
    )
