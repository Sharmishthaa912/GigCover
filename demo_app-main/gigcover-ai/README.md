# GigCover AI - Parametric Insurance for Delivery Workers

## 6-Week Hackathon Project Overview

**Persona Focus:** Food Delivery Workers (Zomato/Swiggy) - Protecting livelihoods from uncontrollable disruptions (weather, app crashes, curfews) causing immediate loss of daily wages.

**Coverage Scope:** LOSS OF INCOME ONLY - Weekly safety net for lost hours/wages. Strictly excludes vehicle repairs, health insurance, or accident medical bills.

**Weekly Pricing Model:** Gig workers operate week-to-week. Financial/premium model structured on weekly basis with dynamic AI-powered risk assessment.

---

## Phase 1 Deliverables: Ideation & Foundation

### The Idea Document

#### Core Strategy

GigCover AI addresses the critical vulnerability of delivery workers to external disruptions that cause immediate income loss. Our parametric insurance platform provides instant, automated payouts when predefined triggers (weather thresholds, app downtime, curfew restrictions) are breached, ensuring workers receive their lost wages within minutes rather than waiting weeks for traditional claims processing.

**Problem Statement:**
- Delivery workers earn ₹300-500/hour but lose 4-8 hours daily during disruptions
- Traditional insurance takes 30+ days for claims, leaving workers without income
- Current solutions don't address the immediacy of gig economy income needs

**Solution:**
- Weekly parametric insurance premiums (₹50-150/week based on risk)
- Real-time monitoring of 5 automated triggers
- Instant UPI payouts when thresholds breached
- Zero-touch claims process requiring no manual intervention

#### Weekly Premium Model

**Base Calculation:**
```
Weekly Premium = (Daily Income × Risk Multiplier × Coverage Hours) ÷ 7
```

**Risk Multipliers:**
- Low Risk Zone: 0.8x (historical safe areas)
- Medium Risk: 1.0x (normal urban areas)
- High Risk: 1.3x (flood-prone, high-traffic zones)

**AI Integration:**
- Dynamic pricing adjusts weekly based on hyper-local risk factors
- ML model analyzes weather patterns, traffic data, and historical disruptions
- Premium reduction of ₹2-5/week for workers in consistently safe zones

#### Parametric Triggers

1. **Rainfall Trigger:** >100mm rainfall in 3 hours
2. **AQI Trigger:** Air quality index >200 (health hazard)
3. **Heatwave Trigger:** Temperature >40°C with humidity >70%
4. **App Crash Trigger:** Platform API downtime >30 minutes
5. **Curfew/Restriction Trigger:** Government-imposed movement restrictions

#### Platform Choice: Web Application

**Justification:**
- Delivery workers access platforms via mobile browsers for orders
- Web app provides instant accessibility without app store delays
- PWA capabilities enable offline functionality and push notifications
- Easier deployment and updates compared to native mobile apps
- Better integration with existing delivery platform workflows

#### AI/ML Integration Plan

**Premium Calculation:**
- RandomForestRegressor model trained on historical weather, traffic, and disruption data
- Features: rainfall_level, aqi_level, traffic_congestion, zone_type, historical_disruptions
- Real-time premium adjustments based on current risk factors

**Fraud Detection:**
- Multi-signal fraud scoring (GPS teleport, activity patterns, timing analysis)
- Isolation Forest for anomaly detection
- Ring detection for coordinated fraud attempts
- Progressive verification tiers (auto-approve, manual review, block)

**Predictive Analytics:**
- Time series forecasting for next week's disruption likelihood
- Worker behavior pattern analysis for risk assessment
- Loss ratio optimization through dynamic pricing

#### Tech Stack & Development Plan

**Frontend:** React 19 + Vite, Tailwind CSS, Framer Motion
**Backend:** Python Flask, SQLite, JWT Authentication
**AI/ML:** scikit-learn, NumPy, joblib
**External APIs:** OpenWeatherMap, Reverse Geocoding
**Deployment:** Render (backend), Netlify/Vercel (frontend)
**Mobile:** Flutter for companion app

**Development Phases:**
- Week 1-2: Core registration, onboarding, risk assessment
- Week 3-4: Parametric triggers, automated claims, payout integration
- Week 5-6: Advanced fraud detection, admin dashboard, predictive analytics

---

## Phase 2 Deliverables: Automation & Protection

### Registration Process
- Email/phone verification with OTP
- Profile creation with delivery platform selection
- Location permission and GPS tracking consent
- Risk pool assignment based on city and platform

### Insurance Policy Management
- Weekly premium calculation and payment
- Coverage hours customization (6-12 hours/day)
- Automatic renewal with risk-based adjustments
- Policy status dashboard with active coverage tracking

### Dynamic Premium Calculation
- Real-time risk assessment using weather and location data
- ML-powered premium adjustments
- Historical performance-based discounts
- Transparent pricing with breakdown display

### Claims Management
- Zero-touch automated claims processing
- Real-time trigger monitoring
- Instant payout notifications
- Claims history with detailed analytics

---

## Phase 3 Deliverables: Scale & Optimise

### Advanced Fraud Detection
- GPS spoofing detection using speed/acceleration analysis
- Activity pattern monitoring during trigger windows
- Ring detection for coordinated fraud attempts
- ML-based anomaly scoring with 95% detection rate

### Instant Payout System (Simulated)
- Multi-channel settlement (UPI, IMPS, Razorpay sandbox)
- Fraud-aware payouts with automatic blocking
- Real-time status tracking and reconciliation
- Rollback capabilities for disputed transactions

### Intelligent Dashboard

**Worker Dashboard:**
- Earnings protected with weekly coverage status
- Real-time risk monitoring and trigger alerts
- Payout history with UTR references
- Platform activity integration

**Admin Dashboard:**
- Loss ratios and financial performance metrics
- Predictive analytics for next week's disruption claims
- Fraud detection monitoring and alert system
- System configuration and trigger management

---

## Business Viability

### Weekly Pricing Model Benefits
- **Affordability:** ₹50-150/week vs traditional insurance costs
- **Flexibility:** Week-to-week coverage matches gig worker income cycles
- **Scalability:** Parametric triggers eliminate manual claims processing
- **Profitability:** 15-20% profit margins with 85% loss ratio target

### Market Opportunity
- 3 million+ delivery workers in India
- ₹50,000 Cr gig economy market
- 20-30% income disruption frequency
- High willingness to pay for income protection

### Competitive Advantages
- First parametric insurance for gig workers
- AI-powered dynamic pricing
- Instant automated payouts
- Platform-integrated fraud prevention

---

## Technical Architecture

### System Components
1. **Frontend Web App:** React-based PWA for worker interaction
2. **Mobile Companion:** Flutter app for real-time monitoring
3. **Backend API:** Flask REST API with JWT authentication
4. **ML Engine:** scikit-learn models for risk and fraud detection
5. **Database:** SQLite with Render Disk persistence
6. **External Services:** Weather APIs, payment gateways

### Security Measures
- End-to-end encryption for sensitive data
- GPS data anonymization and aggregation
- Multi-factor fraud detection
- Secure payment processing with PCI compliance

### Scalability Considerations
- Horizontal scaling with load balancers
- Database optimization for high-frequency GPS data
- Caching layer for weather API responses
- Microservices architecture for independent scaling

---

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 18+
- Flutter SDK (for mobile app)

### Backend Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
```bash
# Backend
JWT_SECRET=your-secret-key
OPENWEATHER_API_KEY=your-api-key
DB_PATH=gigcover.db

# Frontend
VITE_API_URL=http://localhost:5000
```

---

## Demo Script for 5-Minute Video

### Opening (30 seconds)
- Show platform landing page with value proposition
- Highlight "Perfect for Your Worker" theme
- Demonstrate modern glassmorphism UI

### Registration & Onboarding (1 minute)
- Worker registration with platform selection (Zomato/Swiggy)
- Profile setup with location permissions
- Risk assessment and premium calculation
- Weekly policy activation

### Trigger Simulation (2 minutes)
- Simulate rainstorm trigger (>100mm rainfall)
- Show real-time weather monitoring
- Demonstrate automated claim firing
- Display fraud detection analysis
- Show instant UPI payout processing

### Dashboard Features (1 minute)
- Worker dashboard with earnings protection
- Admin dashboard with predictive analytics
- Fraud detection monitoring
- System performance metrics

### Closing (30 seconds)
- Business viability highlights
- Scalability demonstration
- Call to action for judging panel

---

## Contact & Repository

**GitHub Repository:** [Link to be provided]
**Demo Video:** [YouTube/Vimeo link to be provided]
**Team:** GigCover AI Development Team

For questions or technical details, please refer to the codebase documentation.

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