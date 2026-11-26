"""通用时间与文本工具。"""
from __future__ import annotations

from datetime import datetime


def now_str() -> str:
    """数据库统一使用 ISO-8601 秒级时间字符串，便于 SQLite 文本排序。"""
    return datetime.now().isoformat(timespec="seconds")


def to_db_time(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def parse_db_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_form_time(value: str) -> datetime:
    """解析 <input type="datetime-local"> 提交的时间。"""
    value = (value or "").strip()
    if not value:
        raise ValueError("时间不能为空")
    return datetime.fromisoformat(value)


def format_dt(value: str | datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime(fmt)
