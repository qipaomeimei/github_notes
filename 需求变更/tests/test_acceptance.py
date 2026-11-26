"""实验二初始版本 C1—C10 验收用例（服务层，固定可复现）。"""
from __future__ import annotations

import pytest

from app import create_app
from app.db import get_db
from app.domain.events import new_event
from app.domain.models import RegistrationStatus
from app.errors import BusinessError
from app.handlers import SiteMessageHandler
from app.notifications import build_event_bus
from app.repositories import (
    MessageRepository,
    NotificationFailureRepository,
    RegistrationRepository,
)
from app.services import ActivityService, RegistrationService
from tests.helpers import create_activity


def test_c1_create_direct_activity(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, title="直接报名活动", capacity=2)
        stats = ActivityService(conn).stats(activity.activity_id)
        assert activity.policy_type == "direct"
        assert stats.capacity == 2
        assert stats.approved == 0
        assert stats.pending == 0
        assert stats.remaining == 2


def test_c2_student_registers_direct_activity(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        registration = RegistrationService(conn).register(activity.activity_id, "S001")

        assert registration.status is RegistrationStatus.APPROVED
        messages = MessageRepository(conn).list_for_student("S001")
        assert len(messages) == 1
        assert "报名成功" in messages[0]["content"]


def test_c3_duplicate_active_registration_is_rejected(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        service = RegistrationService(conn)
        service.register(activity.activity_id, "S001")

        with pytest.raises(BusinessError, match="已报名"):
            service.register(activity.activity_id, "S001")
        assert len(
            RegistrationRepository(conn).list_for_activity(activity.activity_id)
        ) == 1


def test_c4_capacity_limit_for_direct_registration(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        service = RegistrationService(conn)
        service.register(activity.activity_id, "S001")
        service.register(activity.activity_id, "S002")

        with pytest.raises(BusinessError, match="名额已满"):
            service.register(activity.activity_id, "S003")

        stats = ActivityService(conn).stats(activity.activity_id)
        assert stats.approved == 2
        assert stats.remaining == 0


def test_c5_approval_activity_creates_pending_registration(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=2)
        registration = RegistrationService(conn).register(activity.activity_id, "S001")

        assert registration.status is RegistrationStatus.PENDING
        stats = ActivityService(conn).stats(activity.activity_id)
        assert stats.pending == 1
        assert stats.approved == 0
        assert stats.remaining == 2


def test_c6_admin_approves_pending_registration(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=2)
        registration = RegistrationService(conn).register(activity.activity_id, "S001")

        approved = RegistrationService(conn).approve(registration.registration_id)
        assert approved.status is RegistrationStatus.APPROVED

        messages = MessageRepository(conn).list_for_student("S001")
        assert len(messages) == 2
        assert "通过" in messages[0]["content"]


def test_c7_admin_rejects_pending_registration(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=2)
        service = RegistrationService(conn)
        first = service.register(activity.activity_id, "S001")
        second = service.register(activity.activity_id, "S002")

        service.approve(first.registration_id)
        rejected = service.reject(second.registration_id)

        assert rejected.status is RegistrationStatus.REJECTED
        messages = MessageRepository(conn).list_for_student("S002")
        assert len(messages) == 2
        assert "未通过" in messages[0]["content"]


def test_c8_approval_rechecks_capacity(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=1)
        service = RegistrationService(conn)
        first = service.register(activity.activity_id, "S001")
        second = service.register(activity.activity_id, "S002")

        service.approve(first.registration_id)
        with pytest.raises(BusinessError, match="名额已满"):
            service.approve(second.registration_id)

        stats = ActivityService(conn).stats(activity.activity_id)
        assert stats.approved == 1
        assert stats.remaining == 0
        assert (
            RegistrationRepository(conn).get(second.registration_id).status
            is RegistrationStatus.PENDING
        )


def test_c9_cancel_pending_and_approved_registrations(app):
    with app.app_context():
        conn = get_db()
        service = RegistrationService(conn)

        direct = create_activity(conn, capacity=2)
        approved = service.register(direct.activity_id, "S001")
        cancelled = service.cancel(approved.registration_id, "S001")
        assert cancelled.status is RegistrationStatus.CANCELLED
        assert ActivityService(conn).stats(direct.activity_id).approved == 0

        approval = create_activity(conn, policy_type="approval", capacity=2)
        pending = service.register(approval.activity_id, "S001")
        cancelled_pending = service.cancel(pending.registration_id, "S001")
        assert cancelled_pending.status is RegistrationStatus.CANCELLED
        assert ActivityService(conn).stats(approval.activity_id).pending == 0

        with pytest.raises(BusinessError, match="不可取消"):
            service.cancel(pending.registration_id, "S001")


def test_c10_data_persists_after_restart(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        registration = RegistrationService(conn).register(activity.activity_id, "S001")
        activity_id = activity.activity_id
        registration_id = registration.registration_id

    restarted = create_app(
        {
            "TESTING": True,
            "DATABASE": app.config["DATABASE"],
            "SECRET_KEY": "restart-test",
            "CSRF_ENABLED": False,
            "SEED_DEMO": False,
        }
    )
    with restarted.app_context():
        conn = get_db()
        persisted = RegistrationRepository(conn).get(registration_id)
        assert persisted is not None
        assert persisted.status is RegistrationStatus.APPROVED
        assert ActivityService(conn).get_activity(activity_id) is not None
        assert len(MessageRepository(conn).list_for_student("S001")) == 1


def test_soft_delete_keeps_history_and_blocks_registration(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        service = RegistrationService(conn)
        service.register(activity.activity_id, "S001")

        ActivityService(conn).soft_delete_activity(activity.activity_id)

        assert ActivityService(conn).get_activity(activity.activity_id) is None
        assert ActivityService(conn).list_activities() == []
        assert len(ActivityService(conn).list_activities(include_deleted=True)) == 1
        assert len(
            RegistrationRepository(conn).list_for_activity(activity.activity_id)
        ) == 1
        with pytest.raises(Exception, match="不存在或已下架"):
            service.register(activity.activity_id, "S002")


def test_notification_failure_is_logged_without_losing_registration(app, monkeypatch):
    def broken_handler(self, event):
        raise RuntimeError("通知服务不可用")

    monkeypatch.setattr(SiteMessageHandler, "handle", broken_handler)

    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        registration = RegistrationService(conn).register(activity.activity_id, "S001")

        assert registration.status is RegistrationStatus.APPROVED
        assert len(MessageRepository(conn).list_for_student("S001")) == 0
        assert NotificationFailureRepository(conn).count() == 1


def test_duplicate_event_is_dispatched_once(app):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        bus = build_event_bus(conn)
        event = new_event(
            "registration.approved",
            "S001",
            activity.activity_id,
            activity.title,
            "报名成功",
        )

        assert bus.publish(event) is True
        assert bus.publish(event) is False
        assert len(MessageRepository(conn).list_for_student("S001")) == 1
