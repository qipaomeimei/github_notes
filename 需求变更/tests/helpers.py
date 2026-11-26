from __future__ import annotations

from datetime import datetime, timedelta

from app.services import ActivityService


def create_activity(
    conn,
    *,
    title: str = "测试活动",
    policy_type: str = "direct",
    capacity: int = 2,
    days: int = 7,
    category: str = "文体活动",
    location: str = "测试地点",
):
    return ActivityService(conn).create_activity(
        title=title,
        category=category,
        start_at=datetime.now() + timedelta(days=days),
        location=location,
        capacity=capacity,
        policy_type=policy_type,
        description="自动化测试创建的活动",
    )


def login(client, username: str = "s001", password: str = "123456"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
