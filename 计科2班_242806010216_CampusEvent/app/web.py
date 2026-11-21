"""模板过滤器与全局模板变量。"""
from __future__ import annotations

import secrets

from flask import session

from .auth import current_user
from .db import get_db
from .domain.models import STATUS_CLASSES, STATUS_LABELS, status_label
from .domain.policies import POLICY_FACTORY
from .repositories import MessageRepository
from .utils import format_dt


def register_template_helpers(app) -> None:
    @app.template_filter("dt")
    def _dt_filter(value, fmt: str = "%Y-%m-%d %H:%M"):
        return format_dt(value, fmt)

    @app.context_processor
    def inject_globals():
        user = current_user()
        unread = 0
        if user and user.get("role") == "student":
            try:
                unread = MessageRepository(get_db()).unread_count(user["student_id"])
            except Exception:  # 页面渲染不因统计失败而中断
                unread = 0

        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_hex(16)
            session["_csrf_token"] = token

        return {
            "current_user": user,
            "unread_count": unread,
            "csrf_token": token,
            "status_labels": STATUS_LABELS,
            "status_classes": STATUS_CLASSES,
            "status_label": status_label,
            "policy_choices": POLICY_FACTORY.choices(),
            "policy_label": POLICY_FACTORY.display_name,
            "policy_description": POLICY_FACTORY.description,
        }
