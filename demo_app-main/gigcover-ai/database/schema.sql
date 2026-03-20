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

CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id TEXT UNIQUE NOT NULL,
  user_id INTEGER NOT NULL,
  trigger_type TEXT NOT NULL,
  lost_hours REAL NOT NULL,
  payout REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'Approved',
  rainfall REAL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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

INSERT OR IGNORE INTO settings(key, value) VALUES ('rainfall_threshold', '100');
INSERT OR IGNORE INTO settings(key, value) VALUES ('risk_weight', '1.0');
