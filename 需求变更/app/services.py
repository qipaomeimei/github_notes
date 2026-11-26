"""业务服务层。

事务边界在此处控制：
1. 先提交报名状态变更；
2. 提交成功后再发布领域事件；
3. 通知异常只留痕，不回滚报名。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from .domain.events import (
    EVENT_APPROVED,
    EVENT_CANCELLED,
    EVENT_PENDING,
    EVENT_REJECTED,
    EventBus,
    new_event,
)
from .domain.models import (
    ACTIVE_STATUSES,
    Activity,
    ActivityStats,
    Registration,
    RegistrationStatus,
)
from .domain.policies import (
    POLICY_FACTORY,
    RegistrationContext,
    RegistrationPolicyFactory,
)
from .errors import BusinessError, ValidationError
from .notifications import build_event_bus
from .repositories import (
    ActivityRepository,
    RegistrationRepository,
    StudentRepository,
)
from .utils import parse_form_time


def _require_text(value: str | None, label: str, max_length: int) -> str:
    text = (value or "").strip()
    if not text:
        raise ValidationError(f"{label}不能为空")
    if len(text) > max_length:
        raise ValidationError(f"{label}不能超过 {max_length} 个字符")
    return text


def _parse_capacity(value: str | int | None) -> int:
    try:
        capacity = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("人数上限必须是正整数") from exc
    if capacity <= 0:
        raise ValidationError("人数上限必须大于 0")
    if capacity > 100000:
        raise ValidationError("人数上限不能超过 100000")
    return capacity


def _parse_start_at(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        start_at = value
    else:
        try:
            start_at = parse_form_time(value)
        except ValueError as exc:
            raise ValidationError("活动时间格式不正确") from exc
    if start_at <= datetime.now():
        raise ValidationError("活动开始时间必须晚于当前时间")
    return start_at


class ActivityService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        policy_factory: RegistrationPolicyFactory = POLICY_FACTORY,
    ) -> None:
        self.conn = conn
        self.activities = ActivityRepository(conn)
        self.registrations = RegistrationRepository(conn)
        self.policy_factory = policy_factory

    def list_activities(
        self, keyword: str | None = None, include_deleted: bool = False
    ) -> list[Activity]:
        return self.activities.list(
            keyword=(keyword or "").strip() or None,
            include_deleted=include_deleted,
        )

    def get_activity(self, activity_id: int, include_deleted: bool = False) -> Activity | None:
        return self.activities.get(activity_id, include_deleted=include_deleted)

    def create_activity(
        self,
        *,
        title: str,
        category: str,
        start_at: str | datetime,
        location: str,
        capacity: str | int,
        policy_type: str,
        description: str = "",
    ) -> Activity:
        payload = self._validate(
            title=title,
            category=category,
            start_at=start_at,
            location=location,
            capacity=capacity,
            policy_type=policy_type,
            description=description,
        )
        activity = self.activities.create(**payload)
        self.conn.commit()
        return activity

    def update_activity(
        self,
        activity_id: int,
        *,
        title: str,
        category: str,
        start_at: str | datetime,
        location: str,
        capacity: str | int,
        policy_type: str,
        description: str = "",
    ) -> Activity:
        activity = self.activities.get(activity_id)
        if activity is None:
            raise BusinessError("活动不存在或已下架")
        payload = self._validate(
            title=title,
            category=category,
            start_at=start_at,
            location=location,
            capacity=capacity,
            policy_type=policy_type,
            description=description,
        )
        updated = self.activities.update(activity_id, **payload)
        if updated is None:
            raise BusinessError("活动不存在或已下架")
        self.conn.commit()
        return updated

    def soft_delete_activity(self, activity_id: int) -> None:
        activity = self.activities.get(activity_id)
        if activity is None:
            raise BusinessError("活动不存在或已下架")
        if not self.activities.soft_delete(activity_id):
            raise BusinessError("活动删除失败，请刷新后重试")
        self.conn.commit()

    def stats(self, activity_id: int) -> ActivityStats:
        activity = self.activities.get(activity_id, include_deleted=True)
        if activity is None:
            raise BusinessError("活动不存在")
        approved = self.registrations.count(activity_id, RegistrationStatus.APPROVED)
        pending = self.registrations.count(activity_id, RegistrationStatus.PENDING)
        return ActivityStats(
            capacity=activity.capacity,
            approved=approved,
            pending=pending,
            remaining=max(activity.capacity - approved, 0),
        )

    def _validate(
        self,
        *,
        title: str,
        category: str,
        start_at: str | datetime,
        location: str,
        capacity: str | int,
        policy_type: str,
        description: str,
    ) -> dict:
        try:
            self.policy_factory.create(policy_type)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        description = (description or "").strip()
        if len(description) > 1000:
            raise ValidationError("活动描述不能超过 1000 个字符")

        return {
            "title": _require_text(title, "活动名称", 100),
            "category": _require_text(category, "活动类型", 30),
            "start_at": _parse_start_at(start_at),
            "location": _require_text(location, "活动地点", 100),
            "capacity": _parse_capacity(capacity),
            "policy_type": policy_type,
            "description": description,
        }


class RegistrationService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        event_bus: EventBus | None = None,
        policy_factory: RegistrationPolicyFactory = POLICY_FACTORY,
    ) -> None:
        self.conn = conn
        self.activities = ActivityRepository(conn)
        self.registrations = RegistrationRepository(conn)
        self.students = StudentRepository(conn)  # CR-01：查学生年级
        self.policy_factory = policy_factory
        self.bus = event_bus or build_event_bus(conn)

    def register(self, activity_id: int, student_id: str) -> Registration:
        activity = self.activities.get(activity_id)
        if activity is None:
            raise ValidationError("活动不存在或已下架")
        if activity.start_at <= datetime.now():
            raise ValidationError("活动已开始，不能报名")
        if self.registrations.find_active(activity_id, student_id) is not None:
            raise ValidationError("你已报名该活动，请勿重复提交")

        policy = self.policy_factory.create(activity.policy_type)
        approved_count = self.registrations.count(
            activity_id, RegistrationStatus.APPROVED
        )
        # CR-01：年级限定策略需要学生年级；旧策略忽略该字段
        grade = self.students.get_grade(student_id)
        decision = policy.decide(
            RegistrationContext(
                activity=activity,
                student_id=student_id,
                approved_count=approved_count,
                student_grade=grade,
            )
        )
        if not decision.accepted or decision.status is None:
            raise BusinessError(decision.reason or "报名失败")

        try:
            with self.conn:
                registration = self.registrations.create(
                    activity_id, student_id, decision.status
                )
        except sqlite3.IntegrityError as exc:
            raise BusinessError("你已报名该活动，请勿重复提交") from exc

        if decision.status is RegistrationStatus.APPROVED:
            event = new_event(
                EVENT_APPROVED,
                student_id,
                activity.activity_id,
                activity.title,
                f"报名成功：「{activity.title}」已确认，请按时参加。",
            )
        else:
            event = new_event(
                EVENT_PENDING,
                student_id,
                activity.activity_id,
                activity.title,
                f"报名申请已提交：「{activity.title}」待管理员审核。",
            )
        self.bus.publish(event)
        return registration

    def cancel(self, registration_id: int, student_id: str) -> Registration:
        registration = self.registrations.get(registration_id)
        if registration is None or registration.student_id != student_id:
            raise BusinessError("报名记录不存在")
        if registration.status not in ACTIVE_STATUSES:
            raise BusinessError("当前状态不可取消")

        activity = self.activities.get(registration.activity_id, include_deleted=True)
        if activity is None:
            raise BusinessError("活动不存在")

        with self.conn:
            self.registrations.update_status(
                registration_id, RegistrationStatus.CANCELLED
            )
        event = new_event(
            EVENT_CANCELLED,
            student_id,
            activity.activity_id,
            activity.title,
            f"你已取消「{activity.title}」的报名。",
        )
        self.bus.publish(event)
        updated = self.registrations.get(registration_id)
        assert updated is not None
        return updated

    def approve(self, registration_id: int) -> Registration:
        registration = self.registrations.get(registration_id)
        if registration is None:
            raise BusinessError("报名记录不存在")
        if registration.status is not RegistrationStatus.PENDING:
            raise BusinessError("只有待审核报名可以批准")

        activity = self.activities.get(registration.activity_id, include_deleted=True)
        if activity is None or activity.is_deleted:
            raise BusinessError("活动已下架，不能审批")

        approved_count = self.registrations.count(
            activity.activity_id, RegistrationStatus.APPROVED
        )
        if approved_count >= activity.capacity:
            raise BusinessError("名额已满，无法批准该报名")

        with self.conn:
            self.registrations.update_status(
                registration_id, RegistrationStatus.APPROVED
            )
        event = new_event(
            EVENT_APPROVED,
            registration.student_id,
            activity.activity_id,
            activity.title,
            f"报名申请已通过：「{activity.title}」，请按时参加。",
        )
        self.bus.publish(event)
        updated = self.registrations.get(registration_id)
        assert updated is not None
        return updated

    def reject(self, registration_id: int) -> Registration:
        registration = self.registrations.get(registration_id)
        if registration is None:
            raise BusinessError("报名记录不存在")
        if registration.status is not RegistrationStatus.PENDING:
            raise BusinessError("只有待审核报名可以拒绝")

        activity = self.activities.get(registration.activity_id, include_deleted=True)
        if activity is None:
            raise BusinessError("活动不存在")

        with self.conn:
            self.registrations.update_status(
                registration_id, RegistrationStatus.REJECTED
            )
        event = new_event(
            EVENT_REJECTED,
            registration.student_id,
            activity.activity_id,
            activity.title,
            f"报名申请未通过：「{activity.title}」。",
        )
        self.bus.publish(event)
        updated = self.registrations.get(registration_id)
        assert updated is not None
        return updated

    def active_registration(
        self, activity_id: int, student_id: str
    ) -> Registration | None:
        return self.registrations.find_active(activity_id, student_id)
