"""通知事件订阅者。

每个订阅者只关心“事件发生了”，不反向依赖报名服务。
新增通知渠道时只需新增一个实现并在 build_event_bus 中注册。
"""
from __future__ import annotations

from .domain.events import (
    EVENT_APPROVED,
    EVENT_CANCELLED,
    EVENT_PENDING,
    EVENT_PROMOTED,
    EVENT_REJECTED,
    EVENT_WAITLISTED,
    RegistrationEvent,
)
from .repositories import EmailOutboxRepository, MessageRepository, StudentRepository

EMAIL_SUBJECTS = {
    EVENT_APPROVED: "报名结果：已通过",
    EVENT_PENDING: "报名申请已提交",
    EVENT_REJECTED: "报名结果：未通过",
    EVENT_CANCELLED: "报名已取消",
    EVENT_WAITLISTED: "报名结果：已进入候补队列",
    EVENT_PROMOTED: "候补递补成功",
}


class SiteMessageHandler:
    """站内消息通知：把事件消息写入 message 表。"""

    name = "site_message"

    def __init__(self, conn) -> None:
        self.messages = MessageRepository(conn)

    def handle(self, event: RegistrationEvent) -> None:
        if event.message:
            self.messages.add(event.student_id, event.activity_id, event.message)


class EmailNotificationHandler:
    """v2 新增：模拟邮件通知。

    课程环境不连接真实 SMTP，写入 email_outbox 即视为已排队；
    学生邮箱为空时跳过，不影响其他渠道。
    """

    name = "email"

    def __init__(self, conn) -> None:
        self.students = StudentRepository(conn)
        self.outbox = EmailOutboxRepository(conn)

    def handle(self, event: RegistrationEvent) -> None:
        student = self.students.get(event.student_id)
        if student is None:
            return
        email = (student["email"] or "").strip()
        if not email:
            return
        subject = EMAIL_SUBJECTS.get(event.event_type, "CampusEvent 通知")
        self.outbox.add(
            event.student_id,
            email,
            subject,
            event.message,
            event.event_id,
        )
