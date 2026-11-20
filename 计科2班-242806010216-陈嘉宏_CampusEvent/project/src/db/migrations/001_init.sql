-- baseline-v1 初始数据库结构
CREATE TABLE IF NOT EXISTS students (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  role          TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  category    TEXT NOT NULL,
  start_at    TEXT NOT NULL,
  location    TEXT NOT NULL,
  capacity    INTEGER NOT NULL CHECK (capacity > 0),
  policy_type TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  activity_id INTEGER NOT NULL REFERENCES activities(id),
  student_id  TEXT NOT NULL REFERENCES students(id),
  status      TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_registration_activity ON registrations(activity_id);
CREATE INDEX IF NOT EXISTS idx_registration_student ON registrations(student_id);

CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id  TEXT NOT NULL REFERENCES students(id),
  activity_id INTEGER,
  content     TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  is_read     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_message_student ON messages(student_id);

-- 通知留痕：同一事件在同一渠道最多成功投递一次，用于避免重复通知
CREATE TABLE IF NOT EXISTS notification_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id   TEXT NOT NULL,
  channel    TEXT NOT NULL,
  status     TEXT NOT NULL,
  detail     TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (event_id, channel)
);
