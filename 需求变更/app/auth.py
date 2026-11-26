"""登录状态与角色校验。"""
from __future__ import annotations

from functools import wraps

from flask import abort, flash, redirect, session, url_for


def current_user() -> dict | None:
    return session.get("user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("请先登录。", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def student_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("请先登录。", "error")
            return redirect(url_for("auth.login"))
        if user.get("role") != "student":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("请先登录。", "error")
            return redirect(url_for("auth.login"))
        if user.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
