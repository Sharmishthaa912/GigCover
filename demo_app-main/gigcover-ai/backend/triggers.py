"""
triggers.py  –  5 Automated Trigger Detectors for GigCover AI
=============================================================
Trigger 1 : Heavy Rain      – OpenWeather rain probability / rainfall
Trigger 2 : High AQI        – OpenWeather Air Pollution API (mock fallback)
Trigger 3 : Heatwave        – OpenWeather temperature
Trigger 4 : Flood / Storm   – OpenWeather weather alerts + wind + visibility
Trigger 5 : Low Demand      – Mock platform demand index (income disruption)

Each detector returns:
  {
    'trigger_type': str,
    'fired': bool,
    'observed_value': float,
    'threshold_value': float,
    'severity': 'low'|'medium'|'high',
    'income_disruption_pct': float,   # estimated % income loss
    'description': str,
    'source': 'live'|'mock',
  }
"""

import json
import math
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError

# ---------------------------------------------------------------------------
# City coordinate fallback table (used when GPS not available)
# ---------------------------------------------------------------------------
CITY_COORDS = {
    'delhi':     (28.6139, 77.2090),
    'mumbai':    (19.0760, 72.8777),
    'bengaluru': (12.9716, 77.5946),
    'bangalore': (12.9716, 77.5946),
    'hyderabad': (17.3850, 78.4867),
    'chennai':   (13.0827, 80.2707),
    'kolkata':   (22.5726, 88.3639),
    'pune':      (18.5204, 73.8567),
    'ahmedabad': (23.0225, 72.5714),
    'jaipur':    (26.9124, 75.7873),
    'lucknow':   (26.8467, 80.9462),
    'surat':     (21.1702, 72.8311),
}

# ---------------------------------------------------------------------------
# Mock data tables (used when API key missing or API fails)
# ---------------------------------------------------------------------------
MOCK_WEATHER = {
    'delhi':     {'temperature': 38.0, 'rain_probability': 15, 'wind_speed': 4.2, 'visibility': 5000, 'humidity': 45},
    'mumbai':    {'temperature': 31.0, 'rain_probability': 72, 'wind_speed': 6.8, 'visibility': 3500, 'humidity': 88},
    'bengaluru': {'temperature': 27.0, 'rain_probability': 45, 'wind_speed': 3.1, 'visibility': 8000, 'humidity': 70},
    'bangalore': {'temperature': 27.0, 'rain_probability': 45, 'wind_speed': 3.1, 'visibility': 8000, 'humidity': 70},
    'hyderabad': {'temperature': 35.0, 'rain_probability': 30, 'wind_speed': 3.5, 'visibility': 7000, 'humidity': 55},
    'chennai':   {'temperature': 33.0, 'rain_probability': 55, 'wind_speed': 5.0, 'visibility': 6000, 'humidity': 80},
    'kolkata':   {'temperature': 32.0, 'rain_probability': 65, 'wind_speed': 4.5, 'visibility': 4500, 'humidity': 85},
    'pune':      {'temperature': 29.0, 'rain_probability': 40, 'wind_speed': 3.8, 'visibility': 7500, 'humidity': 65},
}

MOCK_AQI = {
    'delhi':     312,
    'kolkata':   245,
    'mumbai':    178,
    'hyderabad': 165,
    'chennai':   142,
    'bengaluru': 118,
    'bangalore': 118,
    'pune':      130,
}

MOCK_DEMAND_INDEX = {
    # 0.0 = no orders, 1.0 = normal demand
    'delhi':     0.55,
    'mumbai':    0.62,
    'bengaluru': 0.78,
    'bangalore': 0.78,
    'hyderabad': 0.70,
    'chennai':   0.68,
    'kolkata':   0.60,
    'pune':      0.72,
}


def _http_get(url: str, timeout: int = 12) -> dict:
    req = Request(url, headers={'User-Agent': 'GigCoverAI/2.0'})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Coordinate resolver
# ---------------------------------------------------------------------------
def resolve_coords(lat: float, lon: float, city: str = '') -> tuple:
    """Return (lat, lon) – use city table if GPS not available."""
    if abs(lat) > 0.001 and abs(lon) > 0.001:
        return float(lat), float(lon)
    city_key = str(city or '').strip().lower()
    if city_key in CITY_COORDS:
        return CITY_COORDS[city_key]
    return 0.0, 0.0


# ---------------------------------------------------------------------------
# Weather data fetcher (OpenWeather + open-meteo fallback + mock)
# ---------------------------------------------------------------------------
def fetch_weather(lat: float, lon: float, api_key: str = '', city: str = '') -> dict:
    """Fetch current weather. Falls back to open-meteo, then mock data."""
    # 1. OpenWeather (live)
    if api_key:
        try:
            params = urlencode({'lat': lat, 'lon': lon, 'appid': api_key, 'units': 'metric'})
            d = _http_get(f'https://api.openweathermap.org/data/2.5/weather?{params}')
            rain_1h = float((d.get('rain') or {}).get('1h', 0) or 0)
            rain_prob = min(100.0, rain_1h * 25)
            return {
                'temperature':    round(float(d['main']['temp']), 1),
                'humidity':       int(d['main']['humidity']),
                'wind_speed':     round(float(d['wind']['speed']), 2),
                'visibility':     int(d.get('visibility', 10000)),
                'rain_probability': rain_prob,
                'description':    d['weather'][0]['description'] if d.get('weather') else '',
                'source': 'openweather_live',
            }
        except Exception:
            pass

    # 2. Open-Meteo (free, no key)
    try:
        params = urlencode({
            'latitude': lat, 'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m,visibility,precipitation',
            'daily': 'precipitation_probability_max',
            'timezone': 'auto', 'forecast_days': 1,
        })
        d = _http_get(f'https://api.open-meteo.com/v1/forecast?{params}', timeout=10)
        cur = d.get('current', {})
        pop = (d.get('daily', {}).get('precipitation_probability_max') or [0])[0]
        return {
            'temperature':    round(float(cur.get('temperature_2m', 30)), 1),
            'humidity':       int(cur.get('relative_humidity_2m', 60)),
            'wind_speed':     round(float(cur.get('wind_speed_10m', 0)) / 3.6, 2),
            'visibility':     int(cur.get('visibility', 10000)),
            'rain_probability': float(pop),
            'description':    '',
            'source': 'open_meteo_live',
        }
    except Exception:
        pass

    # 3. Mock fallback
    city_key = str(city or '').strip().lower()
    mock = MOCK_WEATHER.get(city_key, {
        'temperature': 32.0, 'rain_probability': 30,
        'wind_speed': 4.0, 'visibility': 7000, 'humidity': 60,
    })
    return {**mock, 'description': 'mock data', 'source': 'mock'}


def fetch_aqi(lat: float, lon: float, api_key: str = '', city: str = '') -> dict:
    """Fetch AQI. OpenWeather AQI API → mock fallback."""
    if api_key:
        try:
            params = urlencode({'lat': lat, 'lon': lon, 'appid': api_key})
            d = _http_get(f'https://api.openweathermap.org/data/2.5/air_pollution?{params}')
            if d.get('list'):
                ow_index = int(d['list'][0]['main']['aqi'])
                # OpenWeather AQI 1-5 → approximate PM2.5-based AQI
                aqi_map = {1: 35, 2: 75, 3: 125, 4: 200, 5: 320}
                aqi_val = aqi_map.get(ow_index, 100)
                pm25 = float(d['list'][0]['components'].get('pm2_5', 0))
                return {'aqi': aqi_val, 'pm25': round(pm25, 1), 'source': 'openweather_live'}
        except Exception:
            pass

    # Mock fallback
    city_key = str(city or '').strip().lower()
    aqi_val = MOCK_AQI.get(city_key, int((abs(lat + lon) * 7) % 200 + 60))
    return {'aqi': aqi_val, 'pm25': round(aqi_val * 0.4, 1), 'source': 'mock'}


def fetch_demand_index(city: str, platform: str = '') -> dict:
    """
    Mock platform demand index.
    In production: call Swiggy/Zomato partner API for order volume.
    Returns demand_index 0.0–1.0 (1.0 = normal, <0.5 = severe disruption).
    """
    city_key = str(city or '').strip().lower()
    base = MOCK_DEMAND_INDEX.get(city_key, 0.65)

    # Simulate time-of-day demand variation
    hour = datetime.now(timezone.utc).hour
    if 12 <= hour <= 14 or 19 <= hour <= 21:
        base = min(1.0, base + 0.15)   # lunch/dinner peak
    elif 2 <= hour <= 6:
        base = max(0.1, base - 0.30)   # dead hours

    return {
        'demand_index': round(base, 2),
        'platform': platform or 'general',
        'city': city_key,
        'source': 'mock',
        'note': 'Replace with Swiggy/Zomato partner API in production',
    }


# ---------------------------------------------------------------------------
# TRIGGER 1 – Heavy Rain
# ---------------------------------------------------------------------------
def trigger_heavy_rain(weather: dict, threshold: float = 65.0) -> dict:
    rain = float(weather.get('rain_probability', 0))
    fired = rain > threshold
    severity = 'high' if rain > 85 else 'medium' if rain > threshold else 'low'
    disruption = _clamp((rain - threshold) / 35.0) * 0.80 if fired else 0.0
    return {
        'trigger_type': 'Heavy Rain',
        'fired': fired,
        'observed_value': round(rain, 1),
        'threshold_value': threshold,
        'severity': severity,
        'income_disruption_pct': round(disruption * 100, 1),
        'description': f'Rain probability {rain:.0f}% exceeds {threshold:.0f}% threshold. Delivery severely impacted.' if fired
                       else f'Rain probability {rain:.0f}% – below trigger threshold.',
        'source': weather.get('source', 'unknown'),
        'unit': '%',
    }


# ---------------------------------------------------------------------------
# TRIGGER 2 – High AQI / Air Pollution
# ---------------------------------------------------------------------------
def trigger_high_aqi(aqi_data: dict, threshold: float = 300.0) -> dict:
    aqi = float(aqi_data.get('aqi', 0))
    fired = aqi > threshold
    severity = 'high' if aqi > 400 else 'medium' if aqi > threshold else 'low'
    disruption = _clamp((aqi - threshold) / 200.0) * 0.60 if fired else 0.0
    return {
        'trigger_type': 'High AQI',
        'fired': fired,
        'observed_value': round(aqi, 0),
        'threshold_value': threshold,
        'severity': severity,
        'income_disruption_pct': round(disruption * 100, 1),
        'description': f'AQI {aqi:.0f} is hazardous (>{threshold:.0f}). Outdoor work health risk.' if fired
                       else f'AQI {aqi:.0f} – within safe limits.',
        'source': aqi_data.get('source', 'unknown'),
        'unit': 'AQI',
        'pm25': aqi_data.get('pm25', 0),
    }


# ---------------------------------------------------------------------------
# TRIGGER 3 – Heatwave
# ---------------------------------------------------------------------------
def trigger_heatwave(weather: dict, threshold: float = 42.0) -> dict:
    temp = float(weather.get('temperature', 0))
    fired = temp > threshold
    severity = 'high' if temp > 46 else 'medium' if temp > threshold else 'low'
    disruption = _clamp((temp - threshold) / 8.0) * 0.70 if fired else 0.0
    return {
        'trigger_type': 'Heatwave',
        'fired': fired,
        'observed_value': round(temp, 1),
        'threshold_value': threshold,
        'severity': severity,
        'income_disruption_pct': round(disruption * 100, 1),
        'description': f'Temperature {temp:.1f}°C exceeds {threshold:.0f}°C. Dangerous outdoor conditions.' if fired
                       else f'Temperature {temp:.1f}°C – within safe range.',
        'source': weather.get('source', 'unknown'),
        'unit': '°C',
    }


# ---------------------------------------------------------------------------
# TRIGGER 4 – Flood / Storm Alert (wind + visibility composite)
# ---------------------------------------------------------------------------
def trigger_flood_storm(weather: dict, wind_threshold: float = 15.0, vis_threshold: float = 1500.0) -> dict:
    wind = float(weather.get('wind_speed', 0))
    vis  = float(weather.get('visibility', 10000))
    rain = float(weather.get('rain_probability', 0))

    wind_fired = wind > wind_threshold
    vis_fired  = vis < vis_threshold
    flood_risk = rain > 80 and wind > 8

    fired = wind_fired or vis_fired or flood_risk
    severity = 'high' if (wind > 20 or vis < 500 or flood_risk) else 'medium' if fired else 'low'

    reasons = []
    if wind_fired:  reasons.append(f'wind {wind:.1f} m/s')
    if vis_fired:   reasons.append(f'visibility {vis:.0f} m')
    if flood_risk:  reasons.append('flood-risk rain+wind combo')

    disruption = 0.0
    if fired:
        disruption = _clamp(
            (max(0, wind - wind_threshold) / 15.0) * 0.4 +
            (max(0, vis_threshold - vis) / vis_threshold) * 0.4 +
            (0.2 if flood_risk else 0)
        ) * 0.85

    return {
        'trigger_type': 'Flood / Storm',
        'fired': fired,
        'observed_value': round(wind, 1),
        'threshold_value': wind_threshold,
        'visibility': vis,
        'severity': severity,
        'income_disruption_pct': round(disruption * 100, 1),
        'description': f'Storm alert: {", ".join(reasons)}. Roads unsafe for delivery.' if fired
                       else 'No storm or flood conditions detected.',
        'source': weather.get('source', 'unknown'),
        'unit': 'm/s wind',
    }


# ---------------------------------------------------------------------------
# TRIGGER 5 – Low Platform Demand (income disruption)
# ---------------------------------------------------------------------------
def trigger_low_demand(demand_data: dict, threshold: float = 0.45) -> dict:
    idx = float(demand_data.get('demand_index', 1.0))
    fired = idx < threshold
    severity = 'high' if idx < 0.25 else 'medium' if fired else 'low'
    disruption = _clamp((threshold - idx) / threshold) * 0.65 if fired else 0.0
    return {
        'trigger_type': 'Low Platform Demand',
        'fired': fired,
        'observed_value': round(idx, 2),
        'threshold_value': threshold,
        'severity': severity,
        'income_disruption_pct': round(disruption * 100, 1),
        'description': f'Platform demand index {idx:.2f} below {threshold:.2f}. Significant order drop detected.' if fired
                       else f'Platform demand index {idx:.2f} – normal order volume.',
        'source': demand_data.get('source', 'mock'),
        'unit': 'index (0–1)',
        'platform': demand_data.get('platform', ''),
    }


# ---------------------------------------------------------------------------
# Master trigger runner
# ---------------------------------------------------------------------------
def run_all_triggers(lat: float, lon: float, city: str = '', platform: str = '',
                     api_key: str = '', settings: dict = None) -> dict:
    """
    Run all 5 triggers. Returns full result dict with fired list and summary.
    """
    s = settings or {}
    rain_threshold  = float(s.get('rainfall_threshold', 65))
    aqi_threshold   = float(s.get('aqi_threshold', 300))
    heat_threshold  = float(s.get('heat_threshold', 42))
    wind_threshold  = float(s.get('wind_threshold', 15))
    vis_threshold   = float(s.get('visibility_threshold', 1500))
    demand_threshold = float(s.get('demand_threshold', 0.45))

    weather = fetch_weather(lat, lon, api_key=api_key, city=city)
    aqi_data = fetch_aqi(lat, lon, api_key=api_key, city=city)
    demand_data = fetch_demand_index(city, platform)

    results = [
        trigger_heavy_rain(weather, rain_threshold),
        trigger_high_aqi(aqi_data, aqi_threshold),
        trigger_heatwave(weather, heat_threshold),
        trigger_flood_storm(weather, wind_threshold, vis_threshold),
        trigger_low_demand(demand_data, demand_threshold),
    ]

    fired = [r for r in results if r['fired']]
    max_disruption = max((r['income_disruption_pct'] for r in fired), default=0.0)

    return {
        'triggers': results,
        'fired_triggers': fired,
        'any_fired': len(fired) > 0,
        'fired_count': len(fired),
        'max_income_disruption_pct': max_disruption,
        'weather': weather,
        'aqi': aqi_data,
        'demand': demand_data,
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
        'location': {'lat': lat, 'lon': lon, 'city': city},
    }
