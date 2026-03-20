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

from ml_model import RiskFeatures, load_model, predict_risk, train_and_save_model

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
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
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


def _fetch_weather_for_coords(latitude, longitude):
    if OPENWEATHER_API_KEY:
        params = urlencode({'lat': latitude, 'lon': longitude, 'appid': OPENWEATHER_API_KEY, 'units': 'metric'})
        data = _http_get_json(f'https://api.openweathermap.org/data/2.5/weather?{params}')
        weather = {
            'temperature': round(float((data.get('main', {}) or {}).get('temp', 0)), 1),
            'humidity': int((data.get('main', {}) or {}).get('humidity', 0)),
            'wind_speed': round(float((data.get('wind', {}) or {}).get('speed', 0)), 2),
            'visibility': int(data.get('visibility', 10000)),
            'rain_probability': float(((data.get('rain', {}) or {}).get('1h', 0) or 0) * 30),
        }

        risk_score = _clamp(
            (weather['rain_probability'] / 100.0) * 0.45
            + _clamp(weather['wind_speed'] / 20.0) * 0.25
            + _clamp((10000 - weather['visibility']) / 10000.0) * 0.30
        )

        risk_label = _risk_label_from_score(risk_score)
        risk_level = risk_label.capitalize()
        claim_status = _claim_status_for_risk(risk_label)
        claim_recommended = claim_status == 'Approved'
        recommendation = _claim_message_for_risk(risk_label)

        return {
            'weather': weather,
            'risk': {
                'risk_score': round(risk_score, 2),
                'risk': risk_label,
                'risk_level': risk_level,
                'claim_recommended': claim_recommended,
                'claim_status': claim_status,
                'claim_message': recommendation,
                'recommendation': recommendation,
            },
        }

    params = urlencode(
        {
            'latitude': latitude,
            'longitude': longitude,
            'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m,visibility',
            'daily': 'precipitation_probability_max',
            'timezone': 'auto',
            'forecast_days': 1,
        }
    )
    data = _http_get_json(f'https://api.open-meteo.com/v1/forecast?{params}')
    current = data.get('current', {})
    daily = data.get('daily', {})
    pop = (daily.get('precipitation_probability_max') or [0])[0]

    weather = {
        'temperature': round(float(current.get('temperature_2m', 0)), 1),
        'humidity': int(current.get('relative_humidity_2m', 0)),
        'wind_speed': round(float(current.get('wind_speed_10m', 0)) / 3.6, 2),
        'visibility': int(current.get('visibility', 10000)),
        'rain_probability': float(pop),
    }

    # Visibility is in meters and wind is in m/s here.
    risk_score = _clamp(
        (weather['rain_probability'] / 100.0) * 0.45
        + _clamp(weather['wind_speed'] / 20.0) * 0.25
        + _clamp((10000 - weather['visibility']) / 10000.0) * 0.30
    )

    risk_label = _risk_label_from_score(risk_score)
    risk_level = risk_label.capitalize()
    claim_status = _claim_status_for_risk(risk_label)
    claim_recommended = claim_status == 'Approved'
    recommendation = _claim_message_for_risk(risk_label)

    return {
        'weather': weather,
        'risk': {
            'risk_score': round(risk_score, 2),
            'risk': risk_label,
            'risk_level': risk_level,
            'claim_recommended': claim_recommended,
            'claim_status': claim_status,
            'claim_message': recommendation,
            'recommendation': recommendation,
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

    return jsonify(
        {
            'user': ({**dict(user), 'role': _public_role(user['role'])} if user else {}),
            'worker': dict(worker) if worker else {},
            'policy': dict(policy) if policy else {},
            'claims': claims,
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
    print(f"[onboarding] user_id={user_id} payload={_safe_request_payload(data)}")

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

    calc = _compute_dynamic_risk_and_premium(
        {
            'daily_income': daily_income,
            'city': city,
            'delivery_platform': delivery_platform,
            'work_type': work_type,
            'working_shift': working_shift,
            'zone_type': zone_type,
            'working_hours': working_hours,
            'full_name': full_name,
        }
    )

    db.execute(
        """
        UPDATE workers
        SET full_name = ?, age = ?, gender = ?, city = ?, location_text = ?, manual_location = ?, latitude = ?, longitude = ?,
            work_type = ?, delivery_platform = ?, daily_income = ?, working_hours = ?, zone_type = ?, risk_score = ?, weekly_premium = ?, coverage_amount = ?,
            working_shift = ?, weekly_working_days = ?, income_dependency = ?, working_environment = ?, onboarding_complete = 1
        WHERE user_id = ?
        """,
        (
            full_name,
            age,
            gender,
            city,
            location_text,
            manual_location,
            latitude,
            longitude,
            work_type,
            delivery_platform,
            daily_income,
            working_hours,
            zone_type,
            calc['risk_score'],
            calc['weekly_premium'],
            calc['coverage_amount'],
            working_shift,
            weekly_working_days,
            income_dependency,
            working_environment,
            user_id,
        ),
    )
    db.execute(
        "UPDATE policies SET premium = ?, coverage_amount = ?, policy_status = 'Active' WHERE user_id = ?",
        (calc['weekly_premium'], calc['coverage_amount'], user_id),
    )
    db.commit()

    return jsonify(
        {
            'message': 'Onboarding completed successfully.',
            'status': 'success',
            'weekly_premium': calc['weekly_premium'],
            'coverage_amount': calc['coverage_amount'],
            'risk_score': calc['risk_score'],
        }
    )


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

    if abs(latitude) < 0.0001 and abs(longitude) < 0.0001:
        return jsonify({'error': 'Valid lat and lon query params are required.'}), 400

    try:
        weather_bundle = _fetch_weather_for_coords(latitude, longitude)
        location = _reverse_geocode(latitude, longitude)

        payload = {
            'location': {
                'latitude': latitude,
                'longitude': longitude,
                **location,
            },
            **weather_bundle,
        }
        payload['risk']['reason'] = _derive_risk_reason(payload['weather'], {})
        return jsonify(payload)
    except URLError:
        return jsonify({'error': 'Weather/location services are currently unreachable.'}), 503


@app.post('/weather-risk')
@auth_required
def weather_risk():
    data = request.get_json(force=True)
    latitude = float(data.get('latitude', 0) or 0)
    longitude = float(data.get('longitude', 0) or 0)

    db = get_db()
    user_id = int(request.user['sub'])

    # Fallback path for webviews/browsers where geolocation may be blocked.
    if abs(latitude) < 0.0001 and abs(longitude) < 0.0001:
        worker_geo = db.execute(
            'SELECT latitude, longitude, city, manual_location, location_text FROM workers WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        if worker_geo:
            saved_lat = float(worker_geo['latitude'] or 0)
            saved_lon = float(worker_geo['longitude'] or 0)
            if abs(saved_lat) > 0.0001 or abs(saved_lon) > 0.0001:
                latitude, longitude = saved_lat, saved_lon
            else:
                geocode_query = (
                    str(worker_geo['city'] or '').strip()
                    or str(worker_geo['location_text'] or '').strip()
                    or str(worker_geo['manual_location'] or '').strip()
                )
                resolved = _forward_geocode(geocode_query)
                if resolved:
                    latitude, longitude = resolved

    if abs(latitude) < 0.0001 and abs(longitude) < 0.0001:
        return jsonify({'error': 'Enable location or complete onboarding location to fetch weather.'}), 400

    try:
        weather_bundle = _fetch_weather_for_coords(latitude, longitude)
        location = _reverse_geocode(latitude, longitude)
        worker_row = db.execute(
            'SELECT work_type, working_environment, weekly_working_days FROM workers WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        worker_data = dict(worker_row) if worker_row else {}
        payload = {
            'location': {
                'latitude': latitude,
                'longitude': longitude,
                **location,
            },
            **weather_bundle,
        }
        payload['risk']['reason'] = _derive_risk_reason(payload['weather'], worker_data)
        return jsonify(
            payload
        )
    except URLError:
        return jsonify({'error': 'Weather/location services are currently unreachable.'}), 503


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


init_db()
model = load_model()

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', '5000')),
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
    )
