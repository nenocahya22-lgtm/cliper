-- VideoClipse Supabase Schema
-- Jalankan di SQL Editor Supabase (https://app.supabase.com)

-- 1. Queue
CREATE TABLE IF NOT EXISTS queue (
  id BIGSERIAL PRIMARY KEY,
  url TEXT NOT NULL,
  platforms JSONB DEFAULT '["youtube"]',
  schedule_at TEXT DEFAULT '',
  title_template TEXT DEFAULT '',
  clip_duration INT DEFAULT 45,
  min_dur INT DEFAULT 30,
  max_dur INT DEFAULT 45,
  status TEXT DEFAULT 'pending',
  output_path TEXT DEFAULT '',
  error TEXT DEFAULT '',
  user_id TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Schedules
CREATE TABLE IF NOT EXISTS schedules (
  id BIGSERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  times JSONB DEFAULT '[]',
  user_id TEXT DEFAULT '',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Stats
CREATE TABLE IF NOT EXISTS stats (
  id BIGSERIAL PRIMARY KEY,
  date TEXT UNIQUE NOT NULL,
  uploaded INT DEFAULT 0,
  links JSONB DEFAULT '[]',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Clips
CREATE TABLE IF NOT EXISTS clips (
  id BIGSERIAL PRIMARY KEY,
  name TEXT DEFAULT '',
  path TEXT DEFAULT '',
  title TEXT DEFAULT '',
  description TEXT DEFAULT '',
  source_url TEXT DEFAULT '',
  duration FLOAT DEFAULT 0,
  file_size BIGINT DEFAULT 0,
  platforms JSONB DEFAULT '[]',
  upload_status JSONB DEFAULT '{}',
  user_id TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Users (sync from Google Auth)
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT,
  name TEXT,
  avatar TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_user ON queue(user_id);
CREATE INDEX IF NOT EXISTS idx_clips_user ON clips(user_id);
CREATE INDEX IF NOT EXISTS idx_stats_date ON stats(date);

-- Row Level Security (optional, set sesuai kebutuhan)
ALTER TABLE queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
