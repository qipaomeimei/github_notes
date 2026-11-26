"""领域事件与事件总线（Observer Pattern）。

报名业务只负责产生“状态已变化”的事实并发布事件，
站内消息、邮件等通知渠道作为订阅者独立处理：
1. 通知失败只记录到 notification_failures，不回滚已提交的报名；
2. dispatched_events 以 event_id 做幂等，避免重复通知。
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from ..repositories import EventLogRepository, NotificationFailureRepository
from ..utils import now_str

logger = logging.getLogger(__name__)

EVENT_APPROVED = "registration.approved"
EVENT_PENDING = "registration.pending"
EVENT_REJECTED = "registration.rejected"
EVENT_CANCELLED = "registration.cancelled"


@dataclass(frozen=True)
class RegistrationEvent:
    event_id: str
    event_type: str
    student_id: str
    activity_id: int
    activity_title: str
    message: str
    created_at: str


def new_event(
    event_type: str,
    student_id: str,
    activity_id: int,
    activity_title: str,
    message: str,
) -> RegistrationEvent:
    return RegistrationEvent(
        event_id=uuid.uuid4().hex,
        event_type=event_type,
        student_id=student_id,
        activity_id=activity_id,
        activity_title=activity_title,
        message=message,
        created_at=now_str(),
    )


class EventHandler(Protocol):
    name: str

    def handle(self, event: RegistrationEvent) -> None: ...


class EventBus:
    def __init__(self, conn, handlers: list[EventHandler]) -> None:
        self.conn = conn
        self.handlers = handlers
        self.event_log = EventLogRepository(conn)
        self.failure_repo = NotificationFailureRepository(conn)

    def publish(self, event: RegistrationEvent) -> bool:
        """发布事件；同一 event_id 重复发布时直接忽略。"""
        if not self.event_log.reserve(event.event_id):
            logger.info("事件 %s 已分发，跳过重复通知", event.event_id)
            return False
        self.conn.commit()

        for handler in self.handlers:
            try:
                handler.handle(event)
                self.conn.commit()
            except Exception as exc:  # 通知渠道故障必须被隔离
                self.conn.rollback()
                logger.exception("通知处理器 %s 处理事件 %s 失败", handler.name, event.event_id)
                try:
                    self.failure_repo.record(event.event_id, handler.name, repr(exc))
                    self.conn.commit()
                except Exception:  # 留痕失败也不能影响主流程
                    self.conn.rollback()
                    logger.exception("记录通知失败日志时再次出错")
        return True
