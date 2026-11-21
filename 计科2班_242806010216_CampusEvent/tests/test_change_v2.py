"""change-v2 变更验收：候补报名 + 邮件通知 + 数据库平滑升级。

对应文档 docs/07_变更影响分析.md 与 docs/08_回归测试表.md 中的 C11—C17。
"""
from __future__ import annotations

import sqlite3

import pytest

from app.db import _apply_migrations, get_db
from app.domain.events import EVENT_APPROVED, new_event
from app.domain.models import RegistrationStatus
from app.errors import BusinessError
from app.handlers import EmailNotificationHandler, SiteMessageHandler
from app.notifications import build_event_bus
from app.repositories import (
    EmailOutboxRepository,
    MessageRepository,
    NotificationFailureRepository,
    RegistrationRepository,
)
from app.services import ActivityService, RegistrationService

from tests.helpers import create_activity


def test_c11_full_waitlist_activity_puts_student_into_queue(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="waitlist", capacity=1)
        service = RegistrationService(conn)

        first = service.register(activity.activity_id, "S001")
        second = service.register(activity.activity_id, "S002")

        assert first.status is RegistrationStatus.APPROVED
        assert second.status is RegistrationStatus.WAITLISTED
        stats = ActivityService(conn).stats(activity.activity_id)
        assert stats.approved == 1
        assert stats.waitlisted == 1
        assert stats.remaining == 0

        messages = MessageRepository(conn).list_for_student("S002")
        assert "候补" in messages[0]["content"]


def test_c12_cancel_approved_promotes_earliest_waitlisted(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="waitlist", capacity=1)
        service = RegistrationService(conn)

        approved = service.register(activity.activity_id, "S001")
        first_wait = service.register(activity.activity_id, "S002")
        second_wait = service.register(activity.activity_id, "S003")
        assert first_wait.status is RegistrationStatus.WAITLISTED
        assert second_wait.status is RegistrationStatus.WAITLISTED

        service.cancel(approved.registration_id, "S001")

        promoted = RegistrationRepository(conn).get(first_wait.registration_id)
        still_waiting = RegistrationRepository(conn).get(second_wait.registration_id)
        assert promoted.status is RegistrationStatus.APPROVED
        assert still_waiting.status is RegistrationStatus.WAITLISTED

        stats = ActivityService(conn).stats(activity.activity_id)
        assert stats.approved == 1
        assert stats.waitlisted == 1
        assert stats.remaining == 0

        promoted_messages = MessageRepository(conn).list_for_student("S002")
        assert "自动递补" in promoted_messages[0]["content"]


def test_c13_waitlisted_registration_can_be_cancelled(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="waitlist", capacity=1)
        service = RegistrationService(conn)

        service.register(activity.activity_id, "S001")
        waiting = service.register(activity.activity_id, "S002")

        cancelled = service.cancel(waiting.registration_id, "S002")
        assert cancelled.status is RegistrationStatus.CANCELLED
        assert ActivityService(conn).stats(activity.activity_id).waitlisted == 0

        # 取消候补后可重新报名，不会触发唯一索引冲突
        again = service.register(activity.activity_id, "S002")
        assert again.status is RegistrationStatus.WAITLISTED


def test_c14_no_promotion_after_activity_started(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="waitlist", capacity=1)
        service = RegistrationService(conn)

        approved = service.register(activity.activity_id, "S001")
        waiting = service.register(activity.activity_id, "S002")

        # 模拟活动已经开始
        conn.execute(
            "UPDATE activities SET start_at = ? WHERE activity_id = ?",
            ("2020-01-01T09:00:00", activity.activity_id),
        )
        conn.commit()

        service.cancel(approved.registration_id, "S001")
        still_waiting = RegistrationRepository(conn).get(waiting.registration_id)
        assert still_waiting.status is RegistrationStatus.WAITLISTED


def test_c15_email_outbox_receives_notification(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)

        RegistrationService(conn).register(activity.activity_id, "S001")

        outbox = EmailOutboxRepository(conn).list_for_student("S001")
        assert len(outbox) == 1
        assert outbox[0]["to_email"] == "zhangsan@example.edu.cn"
        assert outbox[0]["subject"] == "报名结果：已通过"
        assert outbox[0]["status"] == "queued"
        # 站内消息渠道同时收到通知，两个渠道互不替代
        assert len(MessageRepository(conn).list_for_student("S001")) == 1


def test_c16_empty_email_skips_mail_but_keeps_site_message(app):
    with app.app_context():
        conn = get_db()
        conn.execute(
            "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?)",
            ("S004", "赵六", ""),
        )
        conn.commit()

        activity = create_activity(conn, capacity=2)
        RegistrationService(conn).register(activity.activity_id, "S004")

        assert len(MessageRepository(conn).list_for_student("S004")) == 1
        assert EmailOutboxRepository(conn).list_for_student("S004") == []


def test_c17_email_channel_failure_is_isolated(app, monkeypatch):
    def broken_handler(self, event):
        raise RuntimeError("邮件服务不可用")

    monkeypatch.setattr(EmailNotificationHandler, "handle", broken_handler)

    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        registration = RegistrationService(conn).register(activity.activity_id, "S001")

        # 邮件渠道失败不影响报名与站内消息
        assert registration.status is RegistrationStatus.APPROVED
        assert len(MessageRepository(conn).list_for_student("S001")) == 1
        assert NotificationFailureRepository(conn).count() == 1


def test_c18_duplicate_event_notifies_each_channel_once(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        bus = build_event_bus(conn)
        event = new_event(
            EVENT_APPROVED,
            "S001",
            activity.activity_id,
            activity.title,
            "报名成功",
        )

        assert bus.publish(event) is True
        assert bus.publish(event) is False
        assert len(MessageRepository(conn).list_for_student("S001")) == 1
        assert len(EmailOutboxRepository(conn).list_for_student("S001")) == 1


def test_c19_legacy_database_is_migrated_to_v2(tmp_path):
    """baseline-v1 数据库可直接升级，不需要清库重建。"""
    legacy = sqlite3.connect(str(tmp_path / "legacy.db"))
    legacy.row_factory = sqlite3.Row
    legacy.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE students (
            student_id TEXT PRIMARY KEY,
            name       TEXT NOT NULL
        );
        CREATE TABLE activities (
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
        CREATE TABLE registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id     INTEGER NOT NULL REFERENCES activities(activity_id),
            student_id      TEXT NOT NULL REFERENCES students(student_id),
            status          TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );
        CREATE UNIQUE INDEX ux_registration_active
            ON registrations(activity_id, student_id)
            WHERE status IN ('pending', 'approved');
        INSERT INTO students (student_id, name) VALUES ('S001', '张三');
        INSERT INTO activities
            (title, category, start_at, location, capacity, policy_type,
             description, is_deleted, created_at, updated_at)
        VALUES ('历史活动', '文体活动', '2099-01-01T09:00:00', '体育馆', 1,
                'waitlist', '', 0, '2026-01-01T09:00:00', '2026-01-01T09:00:00');
        """
    )
    legacy.commit()

    _apply_migrations(legacy)
    legacy.commit()

    columns = {row["name"] for row in legacy.execute("PRAGMA table_info(students)")}
    assert "email" in columns
    index_sql = legacy.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'ux_registration_active'"
    ).fetchone()["sql"]
    assert "waitlisted" in index_sql

    # 迁移后可以正常写入候补状态
    legacy.execute(
        "INSERT INTO registrations (activity_id, student_id, status, created_at, updated_at) "
        "VALUES (1, 'S001', 'waitlisted', '2026-01-01T10:00:00', '2026-01-01T10:00:00')"
    )
    legacy.commit()
    row = legacy.execute(
        "SELECT status FROM registrations WHERE student_id = 'S001'"
    ).fetchone()
    assert row["status"] == "waitlisted"
    legacy.close()
