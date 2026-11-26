"""CR-01 年级限定策略 + CR-02 邮件通知 — 变更回归用例。

对应教师专用材料：
- CR-01：仅面向大二、大三学生的活动，其他年级收到明确提示
- CR-02：MockEmailSender 模拟邮件，故障不回滚报名，同一事件不重复发送
"""
from __future__ import annotations

import pytest

from app.db import get_db
from app.domain.models import RegistrationStatus
from app.errors import BusinessError
from app.mock_email import MockEmailSender
from app.notifications import build_event_bus
from app.repositories import (
    EmailOutboxRepository,
    MessageRepository,
    NotificationFailureRepository,
    StudentRepository,
)
from app.services import RegistrationService
from tests.helpers import create_activity


# ---------------------------------------------------------------------------
# CR-01 年级限定策略
# ---------------------------------------------------------------------------


def test_grade_restricted_accepts_sophomore(app):
    """大二学生可以报名年级限定直接活动。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="grade-restricted-direct", capacity=5)
        reg = RegistrationService(conn).register(activity.activity_id, "S001")  # 大二
        assert reg.status is RegistrationStatus.APPROVED


def test_grade_restricted_accepts_junior(app):
    """大三学生可以报名年级限定直接活动。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="grade-restricted-direct", capacity=5)
        reg = RegistrationService(conn).register(activity.activity_id, "S002")  # 大三
        assert reg.status is RegistrationStatus.APPROVED


def test_grade_restricted_rejects_freshman_with_clear_message(app):
    """大一学生报名时收到明确提示。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="grade-restricted-direct", capacity=5)
        with pytest.raises(BusinessError, match="仅面向大二、大三"):
            RegistrationService(conn).register(activity.activity_id, "S003")  # 大一


def test_grade_restricted_rejects_senior_with_clear_message(app):
    """大四学生报名时收到明确提示。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="grade-restricted-direct", capacity=5)
        with pytest.raises(BusinessError, match="仅面向大二、大三"):
            RegistrationService(conn).register(activity.activity_id, "S004")  # 大四


def test_grade_restricted_also_respects_capacity(app):
    """年级通过后仍受名额限制约束。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="grade-restricted-direct", capacity=1)
        service = RegistrationService(conn)
        service.register(activity.activity_id, "S001")  # 大二 -> 通过
        with pytest.raises(BusinessError, match="名额已满"):
            service.register(activity.activity_id, "S002")  # 大三但满了


def test_grade_restricted_ignored_for_other_policies(app):
    """原有 direct / approval 策略不受年级字段影响，保持既有行为。"""
    with app.app_context():
        conn = get_db()
        freshman_activity = create_activity(conn, policy_type="direct", capacity=5)
        service = RegistrationService(conn)
        reg = service.register(freshman_activity.activity_id, "S003")  # 大一
        assert reg.status is RegistrationStatus.APPROVED

        approval_activity = create_activity(
            conn, policy_type="approval", capacity=5
        )
        reg2 = service.register(approval_activity.activity_id, "S004")  # 大四
        assert reg2.status is RegistrationStatus.PENDING


# ---------------------------------------------------------------------------
# CR-02 MockEmailSender + EmailNotificationHandler
# ---------------------------------------------------------------------------


def test_email_sent_on_registration_approved(app):
    """报名通过后，站内消息 + 邮件 outbox 同时记录。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="direct", capacity=5)
        RegistrationService(conn).register(activity.activity_id, "S001")

        messages = MessageRepository(conn).list_for_student("S001")
        emails = EmailOutboxRepository(conn).list_for_student("S001")
        assert len(messages) == 1
        assert len(emails) == 1
        assert emails[0]["status"] == "sent"
        assert "g2@campus.edu.cn" in emails[0]["to_email"]
        assert "报名通过" in emails[0]["subject"]


def test_email_sent_on_pending_submission(app):
    """提交审核类报名，邮件主题对应 pending 事件。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=5)
        RegistrationService(conn).register(activity.activity_id, "S002")

        emails = EmailOutboxRepository(conn).list_for_student("S002")
        assert len(emails) == 1
        assert emails[0]["status"] == "sent"
        assert "已提交" in emails[0]["subject"]


def test_email_sent_on_admin_approval_and_rejection(app):
    """管理员批准 / 拒绝都触发对应邮件。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=5)
        service = RegistrationService(conn)
        p1 = service.register(activity.activity_id, "S001")
        p2 = service.register(activity.activity_id, "S002")

        service.approve(p1.registration_id)
        service.reject(p2.registration_id)

        emails_s1 = EmailOutboxRepository(conn).list_for_student("S001")
        emails_s2 = EmailOutboxRepository(conn).list_for_student("S002")
        assert any("通过" in e["subject"] for e in emails_s1)
        assert any("未通过" in e["subject"] for e in emails_s2)


def test_email_failure_does_not_rollback_registration(app):
    """邮件发送异常：报名仍成功，失败记录到 outbox + notification_failures。"""
    broken_sender = MockEmailSender(injected_exception=RuntimeError("SMTP 不通"))

    with app.app_context():
        conn = get_db()
        # 用 broken sender 构造事件总线
        service = RegistrationService(conn)
        service.bus = build_event_bus(conn)
        # 替换 email handler 的 sender
        for h in service.bus.handlers:
            if h.name == "email":
                h.sender = broken_sender

        activity = create_activity(conn, policy_type="direct", capacity=5)
        reg = service.register(activity.activity_id, "S001")

        # 报名仍然成功
        assert reg.status is RegistrationStatus.APPROVED
        # 站内消息成功（另一个 handler 不受影响）
        assert len(MessageRepository(conn).list_for_student("S001")) == 1
        # 邮件失败记录到 outbox
        failed = [
            e for e in EmailOutboxRepository(conn).list_for_student("S001")
            if e["status"] == "failed"
        ]
        assert len(failed) == 1
        assert "SMTP" in failed[0]["error"]
        # notification_failures 也记录了 handler 异常
        assert NotificationFailureRepository(conn).count() == 1


def test_email_and_site_both_subject_to_event_idempotency(app):
    """同一 event_id 重复 publish：站内消息 + 邮件都只记录一次。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="direct", capacity=5)
        bus = build_event_bus(conn)
        from app.domain.events import new_event

        event = new_event(
            "registration.approved", "S001",
            activity.activity_id, activity.title, "报名成功",
        )
        bus.publish(event)
        bus.publish(event)  # 重复

        assert len(MessageRepository(conn).list_for_student("S001")) == 1
        assert len(EmailOutboxRepository(conn).list_for_student("S001")) == 1


def test_cancel_registration_sends_both_notifications(app):
    """取消报名后，站内消息 + 取消主题邮件都发出。"""
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="direct", capacity=5)
        service = RegistrationService(conn)
        reg = service.register(activity.activity_id, "S001")
        service.cancel(reg.registration_id, "S001")

        emails = EmailOutboxRepository(conn).list_for_student("S001")
        cancel_email = [e for e in emails if "取消" in e["subject"]]
        assert len(cancel_email) == 1

        messages = MessageRepository(conn).list_for_student("S001")
        assert any("取消" in m["content"] for m in messages)


def test_student_grade_column_exists_and_seeded(app):
    """验证 students 表已具备 grade 列，conftest 注入的年级值可读取。"""
    with app.app_context():
        conn = get_db()
        assert StudentRepository(conn).get_grade("S001") == 2
        assert StudentRepository(conn).get_grade("S002") == 3
        assert StudentRepository(conn).get_grade("S003") == 1
        assert StudentRepository(conn).get_grade("S004") == 4
