"""领域模型。

只包含领域数据与状态常量，不依赖 Flask，便于被服务层与测试复用。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RegistrationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    # v2 新增：满员活动的候补队列
    WAITLISTED = "waitlisted"


# 同一学生对同一活动视为“有效报名”的状态
ACTIVE_STATUSES = (
    RegistrationStatus.PENDING,
    RegistrationStatus.APPROVED,
    RegistrationStatus.WAITLISTED,
)

STATUS_LABELS = {
    RegistrationStatus.PENDING.value: "待审核",
    RegistrationStatus.APPROVED.value: "已通过",
    RegistrationStatus.REJECTED.value: "已拒绝",
    RegistrationStatus.CANCELLED.value: "已取消",
    RegistrationStatus.WAITLISTED.value: "候补中",
}

STATUS_CLASSES = {
    RegistrationStatus.PENDING.value: "badge-pending",
    RegistrationStatus.APPROVED.value: "badge-approved",
    RegistrationStatus.REJECTED.value: "badge-rejected",
    RegistrationStatus.CANCELLED.value: "badge-cancelled",
    RegistrationStatus.WAITLISTED.value: "badge-waitlisted",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


@dataclass
class Activity:
    activity_id: int | None
    title: str
    category: str
    start_at: datetime
    location: str
    capacity: int
    policy_type: str
    description: str = ""
    is_deleted: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        """活动未开始且未下架时才允许报名。"""
        return not self.is_deleted and self.start_at > datetime.now()


@dataclass
class Registration:
    registration_id: int | None
    activity_id: int
    student_id: str
    status: RegistrationStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ActivityStats:
    capacity: int
    approved: int
    pending: int
    remaining: int
    waitlisted: int = 0
