"""通知事件订阅者（Observer Pattern）。

每个订阅者只关心"事件发生了"，不反向依赖报名服务。
新增通知渠道时只需新增一个实现并在 build_event_bus 中注册。
"""
from __future__ import annotations

import logging

from .domain.events import (
    EVENT_APPROVED,
    EVENT_CANCELLED,
    EVENT_PENDING,
    EVENT_REJECTED,
    RegistrationEvent,
)
from .mock_email import MockEmailSender
from .repositories import EmailOutboxRepository, MessageRepository, StudentRepository

logger = logging.getLogger(__name__)


class SiteMessageHandler:
    """站内消息通知：把事件消息写入 message 表。"""

    name = "site_message"

    def __init__(self, conn) -> None:
        self.messages = MessageRepository(conn)

    def handle(self, event: RegistrationEvent) -> None:
        if event.message:
            self.messages.add(event.student_id, event.activity_id, event.message)


# CR-02 邮件主题映射
_EMAIL_SUBJECTS = {
    EVENT_APPROVED: "CampusEvent 报名通过通知",
    EVENT_PENDING: "CampusEvent 报名申请已提交",
    EVENT_REJECTED: "CampusEvent 报名申请未通过",
    EVENT_CANCELLED: "CampusEvent 报名已取消",
}


class EmailNotificationHandler:
    """CR-02 邮件通知：调用 MockEmailSender 投递，结果写入 email_outbox。

    邮件发送故障不影响 EventBus 主流程：异常由 EventBus.publish 捕获，
    并记录到 notification_failures（handlers.py 不做二次 try/except，
    让上层统一隔离）。
    """

    name = "email"

    def __init__(self, conn, *, sender: MockEmailSender | None = None) -> None:
        self.conn = conn
        self.students = StudentRepository(conn)
        self.outbox = EmailOutboxRepository(conn)
        self.sender = sender or MockEmailSender()

    def _student_email(self, student_id: str) -> str | None:
        row = self.students.get(student_id)
        if row is None:
            return None
        # 演示环境：用学号构造模拟邮箱，便于测试
        grade = int(row["grade"]) if row["grade"] is not None else 0
        return f"{student_id.lower()}_g{grade}@campus.edu.cn"

    def handle(self, event: RegistrationEvent) -> None:
        to_email = self._student_email(event.student_id)
        if not to_email:
            logger.warning("学生 %s 无邮箱，跳过邮件通知", event.student_id)
            return

        subject = _EMAIL_SUBJECTS.get(event.event_type, "CampusEvent 通知")
        body = (
            f"你好，\n\n"
            f"CampusEvent 活动通知：\n"
            f"  活动：{event.activity_title}\n"
            f"  详情：{event.message}\n\n"
            f"—— CampusEvent 校园活动系统\n"
        )

        try:
            self.sender.send(to_email=to_email, subject=subject, body=body)
            self.outbox.add(
                student_id=event.student_id,
                to_email=to_email,
                subject=subject,
                body=body,
                event_id=event.event_id,
                status="sent",
                error=None,
            )
        except Exception as exc:
            # 邮件投递失败：先独立提交一条 failed 记录到 outbox，
            # 避免 EventBus 的 conn.rollback 把它一并清掉；
            # 然后重新 raise，让 EventBus 统一做故障隔离 + notification_failures 留痕。
            try:
                self.outbox.add(
                    student_id=event.student_id,
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    event_id=event.event_id,
                    status="failed",
                    error=repr(exc),
                )
                self.conn.commit()
            except Exception:
                self.conn.rollback()
            raise
