"""登录与退出。"""
from __future__ import annotations

import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from ..auth import current_user
from ..db import get_db
from ..repositories import AccountRepository, StudentRepository

bp = Blueprint("auth", __name__)


def _home_for(role: str):
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("student.activity_list"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    user = current_user()
    if user is not None:
        return _home_for(user.get("role", "student"))

    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        conn = get_db()
        account = AccountRepository(conn).find_by_username(username)
        if account is None or not check_password_hash(account["password_hash"], password):
            flash("用户名或密码错误，请重试。", "error")
            return render_template("login.html", username=username), 401

        display_name = "管理员"
        student_id = account["student_id"]
        if student_id:
            student = StudentRepository(conn).get(student_id)
            display_name = student["name"] if student else student_id

        session.clear()
        session["user"] = {
            "username": account["username"],
            "role": account["role"],
            "student_id": student_id,
            "display_name": display_name,
        }
        session["_csrf_token"] = secrets.token_hex(16)
        flash(f"欢迎回来，{display_name}。", "success")
        return _home_for(account["role"])

    return render_template("login.html", username=username)


@bp.post("/logout")
def logout():
    session.clear()
    flash("你已退出登录。", "info")
    return redirect(url_for("auth.login"))
