CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('Employee', 'Admin', 'Student')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  full_name TEXT,
  age INTEGER DEFAULT 0,
  gender TEXT DEFAULT '',
  city TEXT,
  location_text TEXT DEFAULT '',
  manual_location TEXT DEFAULT '',
  latitude REAL DEFAULT 0,
  longitude REAL DEFAULT 0,
  work_type TEXT DEFAULT '',
  delivery_platform TEXT,
  daily_income REAL DEFAULT 0,
  working_hours REAL DEFAULT 8,
  zone_type TEXT DEFAULT 'Urban',
  working_shift TEXT DEFAULT 'Day',
  weekly_working_days INTEGER DEFAULT 6,
  income_dependency TEXT DEFAULT 'Medium',
  working_environment TEXT DEFAULT 'Outdoor',
  risk_score REAL DEFAULT 0,
  weekly_premium REAL DEFAULT 0,
  coverage_amount REAL DEFAULT 0,
  onboarding_complete INTEGER DEFAULT 0,
  enrollment_date TEXT DEFAULT CURRENT_TIMESTAMP,
  tier TEXT DEFAULT 'standard',
  upi_id TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  gps_consent INTEGER DEFAULT 0,
  tracking_consent INTEGER DEFAULT 0,
  risk_pool TEXT DEFAULT 'general',
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  policy_status TEXT DEFAULT 'Inactive',
  premium REAL DEFAULT 0,
  coverage_amount REAL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Parametric trigger events (one row per detected trigger event)
CREATE TABLE IF NOT EXISTS trigger_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trigger_type TEXT NOT NULL,          -- 'Heavy Rain' | 'High AQI' | 'Strong Wind' | 'Low Visibility' | 'Traffic Disruption'
  city TEXT NOT NULL DEFAULT '',
  latitude REAL DEFAULT 0,
  longitude REAL DEFAULT 0,
  threshold_value REAL NOT NULL,       -- e.g. AQI threshold = 300
  observed_value REAL NOT NULL,        -- actual measured value
  affected_users INTEGER DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'Active',  -- 'Active' | 'Resolved'
  triggered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL,
  trigger_event_id INTEGER,            -- FK to trigger_events
  trigger_type TEXT NOT NULL,
  lost_hours REAL NOT NULL,
  payout REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'Approved',
  rainfall REAL DEFAULT 0,
  fraud_score REAL DEFAULT 0,          -- 0.0 = clean, 1.0 = high fraud risk
  fraud_flags TEXT DEFAULT '[]',       -- JSON array of flag strings
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (trigger_event_id) REFERENCES trigger_events(id)
);

-- All financial transactions (payouts + premium payments)
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  claim_id TEXT,                       -- NULL for premium payments
  txn_type TEXT NOT NULL,              -- 'payout' | 'premium'
  amount REAL NOT NULL,
  method TEXT NOT NULL DEFAULT 'UPI',  -- 'UPI' | 'IMPS' | 'Sandbox'
  status TEXT NOT NULL DEFAULT 'Pending',  -- 'Pending' | 'Success' | 'Failed' | 'Rolled_Back'
  gateway_ref TEXT DEFAULT '',         -- Razorpay/sandbox reference
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  settled_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- GPS + activity logs for fraud detection
CREATE TABLE IF NOT EXISTS activity_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  speed_kmh REAL DEFAULT 0,
  platform_active INTEGER DEFAULT 1,   -- 1 = worker was online on platform
  logged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS risk_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  rainfall_level REAL NOT NULL,
  aqi_level REAL NOT NULL,
  traffic_congestion REAL NOT NULL,
  zone_type TEXT NOT NULL,
  historical_disruptions REAL NOT NULL,
  risk_score REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS premium_payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  paid_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  next_due_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Paid',
  FOREIGN KEY (user_id) REFERENCES users(id)
);

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
);

-- Seed default settings
INSERT OR IGNORE INTO settings(key, value) VALUES ('rainfall_threshold', '100');
INSERT OR IGNORE INTO settings(key, value) VALUES ('risk_weight', '1.0');
INSERT OR IGNORE INTO settings(key, value) VALUES ('aqi_threshold', '300');
INSERT OR IGNORE INTO settings(key, value) VALUES ('wind_threshold', '15');
INSERT OR IGNORE INTO settings(key, value) VALUES ('visibility_threshold', '1500');
INSERT OR IGNORE INTO settings(key, value) VALUES ('payout_per_day', '500');
INSERT OR IGNORE INTO settings(key, value) VALUES ('bcr_target_min', '0.55');
INSERT OR IGNORE INTO settings(key, value) VALUES ('bcr_target_max', '0.70');
INSERT OR IGNORE INTO settings(key, value) VALUES ('loss_ratio_halt', '0.85');
INSERT OR IGNORE INTO settings(key, value) VALUES ('min_working_days', '7');
INSERT OR IGNORE INTO settings(key, value) VALUES ('fraud_score_block', '0.75');
