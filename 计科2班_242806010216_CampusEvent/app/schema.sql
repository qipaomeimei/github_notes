PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    -- v2 新增：邮件通知接收地址，可为空（为空时跳过邮件渠道）
    email      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS accounts (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student', 'admin')),
    student_id    TEXT REFERENCES students(student_id)
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    start_at    TEXT NOT NULL,
    location    TEXT NOT NULL,
    capacity    INTEGER NOT NULL CHECK (capacity > 0),
    policy_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    is_deleted  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registrations (
    registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id     INTEGER NOT NULL REFERENCES activities(activity_id),
    student_id      TEXT NOT NULL REFERENCES students(student_id),
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- 同一学生对同一活动最多存在一条“待审核/已通过/候补中”的有效报名，
-- 已拒绝、已取消记录保留为历史。
CREATE UNIQUE INDEX IF NOT EXISTS ux_registration_active
    ON registrations(activity_id, student_id)
    WHERE status IN ('pending', 'approved', 'waitlisted');

CREATE INDEX IF NOT EXISTS ix_registration_activity ON registrations(activity_id, status);
CREATE INDEX IF NOT EXISTS ix_registration_student ON registrations(student_id, created_at);

CREATE TABLE IF NOT EXISTS messages (
    message_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL REFERENCES students(student_id),
    activity_id INTEGER REFERENCES activities(activity_id),
    content     TEXT NOT NULL,
    is_read     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_message_student ON messages(student_id, is_read, created_at);

-- 通知失败留痕：通知异常不影响已提交的报名事务
CREATE TABLE IF NOT EXISTS notification_failures (
    failure_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL,
    handler     TEXT NOT NULL,
    error       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- 事件幂等表：同一个事件 ID 只分发一次，避免重复通知
CREATE TABLE IF NOT EXISTS dispatched_events (
    event_id     TEXT PRIMARY KEY,
    dispatched_at TEXT NOT NULL
);

-- v2 新增：模拟邮件发件箱。
-- 课程环境不依赖真实 SMTP，写入 outbox 即视为“邮件已排队”；
-- 生产接入邮件服务时只需替换 EmailNotificationHandler 的发送实现。
CREATE TABLE IF NOT EXISTS email_outbox (
    outbox_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL REFERENCES students(student_id),
    to_email    TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    event_id    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_email_outbox_student ON email_outbox(student_id, created_at);
