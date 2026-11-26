"""事件总线装配点。"""
from __future__ import annotations

from .domain.events import EventBus
from .handlers import EmailNotificationHandler, SiteMessageHandler


def build_event_bus(conn) -> EventBus:
    handlers = [
        SiteMessageHandler(conn),
        # v2 新增订阅者：报名服务无需知道邮件渠道存在
        EmailNotificationHandler(conn),
    ]
    return EventBus(conn, handlers)
