"""事件总线装配点。"""
from __future__ import annotations

from .domain.events import EventBus
from .handlers import EmailNotificationHandler, SiteMessageHandler


def build_event_bus(conn) -> EventBus:
    handlers = [
        SiteMessageHandler(conn),
        EmailNotificationHandler(conn),  # CR-02：邮件通知
    ]
    return EventBus(conn, handlers)
