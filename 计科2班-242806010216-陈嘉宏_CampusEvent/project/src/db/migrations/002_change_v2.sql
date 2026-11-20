-- 变更单 CR-01 数据库迁移
-- 1) 活动软删除：新增 status 字段，历史数据默认“进行中”
ALTER TABLE activities ADD COLUMN status TEXT NOT NULL DEFAULT 'active';

-- 2) 候补队列：记录候补顺序（仅候补中的报名有值）
ALTER TABLE registrations ADD COLUMN waitlist_seq INTEGER;

CREATE INDEX IF NOT EXISTS idx_registration_waitlist
  ON registrations(activity_id, status, waitlist_seq);

-- 3) 邮件通知渠道（模拟发件箱）：与站内消息双通道
CREATE TABLE IF NOT EXISTS email_outbox (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id TEXT NOT NULL REFERENCES students(id),
  event_id   TEXT NOT NULL,
  subject    TEXT NOT NULL,
  body       TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (event_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_email_student ON email_outbox(student_id);
