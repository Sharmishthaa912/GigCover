# GigCover AI

GigCover AI is a full-stack gig worker insurance platform built for real-time risk assessment, premium pricing, and claim workflows for delivery workers.

It includes a React web frontend, Flutter mobile app, Flask backend APIs, JWT authentication, weather and location-aware risk analysis, and admin analytics.

## Architecture

1. Frontend Web: Vite + React
2. Mobile App: Flutter (Dart)
3. Backend API: Flask + Gunicorn
4. Database: SQLite (local) with Render Disk persistence in production
5. ML Layer: scikit-learn RandomForestRegressor risk model
6. External Data: OpenWeatherMap and reverse geocoding services

## Technology Stack

1. Flutter, Dart
2. Python, Flask
3. scikit-learn, NumPy, joblib
4. REST APIs, JWT auth
5. OpenWeather API
6. Render deployment
7. React + Vite
8. SQLite

## Risk Model

1. Active model: RandomForestRegressor
2. Training code: backend/ml_model.py in train_and_save_model()
3. Saved artifact: backend/risk_model.joblib
4. Model inputs:
  - rainfall_level
  - aqi_level
  - traffic_congestion
  - zone_type
  - historical_disruptions

## Core Features

1. Signup and login with Employee/Admin roles
2. Worker onboarding with profile and location capture
3. Weekly premium calculation from risk + income
4. Weather-risk detection via coordinates and geocoding
5. Claim eligibility and payout logic
6. Weekly premium payment tracking
7. Admin dashboard for users, policies, claims, events, and system trends

## Adversarial Defense & Anti-Spoofing Strategy

This section addresses the Market Crash scenario: coordinated fraud using fake GPS, synchronized claims, and payout abuse.

### Goal

Detect fraudulent location-based claims quickly while protecting genuine stranded workers from false rejection.

### Threat Model

1. Fake GPS injection (mock location apps, emulator routes)
2. GPS teleporting (impossible jumps in short time)
3. Collusive rings (many users filing similar claims from clustered synthetic traces)
4. Device farming (many accounts from few devices or network fingerprints)
5. Timing attacks (claims filed immediately after scripted location updates)

### Defense Strategy (Logic-Only)

1. Multi-signal trust scoring instead of single GPS pass/fail
2. Progressive verification based on risk tier
3. Ring-level anomaly detection in addition to user-level checks
4. Human review fallback for ambiguous cases
5. Strong audit trail for every approval and rejection

### Anti-Spoofing Signals Used

1. Location trajectory consistency:
  - Speed and acceleration plausibility
  - Route continuity and drift patterns
  - Teleport detection between pings
2. Sensor coherence:
  - GPS movement vs device motion behavior
  - Foreground activity consistency during claim window
3. Device and session integrity:
  - Reused device identifiers across multiple accounts
  - Suspicious account creation and claim velocity
4. Network and geo context:
  - Repeated claim clusters from shared network fingerprints
  - Distance mismatch between claimed disruption zone and recent path
5. Temporal behavior:
  - Script-like timing (identical intervals, synchronized submissions)
  - Burst claims around payout windows

### Fraud Ring Detection

1. Build graph edges between accounts using shared signals:
  - Device overlap
  - IP/network overlap
  - Reused route signatures
  - Same disruption-time claim bursts
2. Identify dense suspicious communities with high internal similarity and low historical legitimacy
3. Escalate whole cluster to higher scrutiny, not just individual nodes

### Decision Engine

1. Low risk score:
  - Auto-approve if policy and weather/disruption context align
2. Medium risk score:
  - Delay payout briefly and request lightweight re-verification
3. High risk score:
  - Block instant payout
  - Trigger manual review and ring investigation

### False-Positive Protection (Do Not Punish Honest Workers)

1. No permanent penalty from a single suspicious event
2. Appeal flow with secondary evidence acceptance
3. Grace threshold for noisy GPS environments
4. Favor partial hold over hard denial when confidence is uncertain
5. Explainable reason tags for each decision

### Operational Response During Market Crash

1. Activate emergency risk mode (higher sensitivity for coordinated attacks)
2. Shorten fraud monitoring intervals
3. Increase manual audit sampling for high-payout claims
4. Freeze only suspicious clusters, not entire geography
5. Publish transparent status updates to maintain worker trust

### Metrics to Track

1. Fraud capture rate
2. False positive rate
3. Mean time to detect ring behavior
4. Mean time to release valid payouts
5. Loss prevented vs delayed genuine payouts

### Why This Works

1. Attackers can spoof one signal, but not many coherent signals over time
2. Ring analytics catches coordinated abuse that per-user checks miss
3. Tiered decisions preserve platform liquidity while protecting genuine workers

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Runs on http://127.0.0.1:5000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:5173

### Flutter

```bash
cd gigcover_mobile
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:5000
```

For Android device over USB, run:

```bash
adb reverse tcp:5000 tcp:5000
```

## Render Deployment Guide

### 1. Push Code

Push the gigcover-ai project to your GitHub repository.

### 2. Create Render Web Service

1. Open Render dashboard
2. Create New -> Web Service
3. Connect your GitHub repository
4. Use render.yaml or configure manually:
  - Build command: pip install -r requirements.txt
  - Start command: gunicorn app:app --bind 0.0.0.0:$PORT
5. If manual setup is used, set Root Directory = backend

### 3. Environment Variables on Render

1. JWT_SECRET
2. OPENWEATHER_API_KEY
3. CORS_ORIGINS=*
4. DB_PATH=/var/data/gigcover.db

### 4. Add Persistent Disk

Attach Render Disk and mount at /var/data.

### 5. Health Check

Open:

https://your-app.onrender.com/

Expected response:

```json
{
  "service": "GigCover AI backend",
  "status": "ok"
}
```

## Production Configuration

### Flutter

```bash
flutter build apk --dart-define=API_BASE_URL=https://your-app.onrender.com
```

or

```bash
flutter run --dart-define=API_BASE_URL=https://your-app.onrender.com
```

### Web

Set VITE_API_BASE_URL=https://your-app.onrender.com and build frontend.

## Key APIs

1. POST /signup
2. POST /login
3. POST /onboarding
4. POST /weather-risk
5. POST /pay-weekly-premium
6. POST /create-claim
7. GET /dashboard-data
8. GET /profile
9. PUT /profile
10. GET /payment-history
11. GET /admin/overview
12. POST /admin/events

## Security and Runtime Notes

1. Use a strong JWT_SECRET value
2. Keep all secrets in environment variables
3. Use HTTPS backend URLs in production mobile/web apps
4. SQLite is acceptable for small deployments; PostgreSQL is recommended at scale