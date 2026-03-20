# GigCover AI Deployment Guide

## 1. Production Architecture

1. Flutter app (Android/iOS) calls public HTTPS backend URL
2. Flask backend is deployed on Render Web Service
3. Persistent data is stored on Render Disk (SQLite) or PostgreSQL (recommended at scale)
4. OpenWeatherMap API key is injected as environment variable

## 2. Backend Deployment (Render)

### Prerequisites

1. Push repository to GitHub
2. Ensure these files exist:
   - `backend/requirements.txt`
   - `backend/Procfile`
   - `render.yaml`

### Create Service

1. Open Render Dashboard
2. Create `New` -> `Blueprint` and select repo (recommended)
3. Render reads `render.yaml` automatically

Alternative manual setup:
1. Create `Web Service`
2. Root Directory: `backend`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`

### Environment Variables

Set in Render:

1. `JWT_SECRET` = long random secret
2. `OPENWEATHER_API_KEY` = your key
3. `CORS_ORIGINS` = `*` (or specific domains)
4. `DB_PATH` = `/var/data/gigcover.db`

### Persistent Storage

1. Add Render Disk
2. Mount path: `/var/data`
3. Size: 1GB+

### Health Check

After deploy, open:

`https://your-app.onrender.com/`

Expected JSON:

```json
{
  "service": "GigCover AI backend",
  "status": "ok"
}
```

## 3. Flutter Mobile Integration

### Use Live Backend URL

Run app against production backend:

```bash
flutter run --dart-define=API_BASE_URL=https://your-app.onrender.com
```

Build production APK:

```bash
flutter build apk --dart-define=API_BASE_URL=https://your-app.onrender.com
```

## 4. Web Frontend Integration

Set environment file in frontend:

`.env`

```env
VITE_API_BASE_URL=https://your-app.onrender.com
```

Then build/deploy frontend.

## 5. Security Checklist

1. Keep secrets only in environment variables
2. Use HTTPS endpoint in mobile/web
3. Validate request payloads at API layer
4. Rotate `JWT_SECRET` periodically
5. Restrict `CORS_ORIGINS` in production to known clients

## 6. Optional Upgrades

1. Migrate SQLite to PostgreSQL for multi-instance scale
2. Add API rate-limiting
3. Add centralized logging (Render logs + Sentry)
4. Add CI/CD on push using GitHub Actions
