"""学生端页面。"""
from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..auth import current_user, student_required
from ..db import get_db
from ..domain.models import RegistrationStatus
from ..errors import BusinessError
from ..repositories import MessageRepository, RegistrationRepository
from ..services import ActivityService, RegistrationService

bp = Blueprint("student", __name__)


@bp.route("/")
def index():
    user = current_user()
    if user is None:
        return redirect(url_for("auth.login"))
    if user.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("student.activity_list"))


@bp.route("/activities")
@student_required
def activity_list():
    user = current_user()
    keyword = (request.args.get("q") or "").strip()
    conn = get_db()
    activity_service = ActivityService(conn)
    registration_service = RegistrationService(conn)

    items = []
    for activity in activity_service.list_activities(keyword=keyword):
        items.append(
            {
                "activity": activity,
                "stats": activity_service.stats(activity.activity_id),
                "my": registration_service.active_registration(
                    activity.activity_id, user["student_id"]
                ),
            }
        )
    return render_template(
        "student/activities.html",
        items=items,
        keyword=keyword,
        now=datetime.now(),
    )


@bp.route("/activities/<int:activity_id>")
@student_required
def activity_detail(activity_id: int):
    user = current_user()
    conn = get_db()
    activity = ActivityService(conn).get_activity(activity_id)
    if activity is None:
        abort(404)

    activity_service = ActivityService(conn)
    registration_service = RegistrationService(conn)
    my_registration = registration_service.active_registration(
        activity_id, user["student_id"]
    )
    return render_template(
        "student/activity_detail.html",
        activity=activity,
        stats=activity_service.stats(activity_id),
        my_registration=my_registration,
        now=datetime.now(),
    )


@bp.post("/activities/<int:activity_id>/register")
@student_required
def register(activity_id: int):
    user = current_user()
    try:
        registration = RegistrationService(get_db()).register(
            activity_id, user["student_id"]
        )
    except BusinessError as exc:
        flash(str(exc), "error")
    else:
        if registration.status is RegistrationStatus.APPROVED:
            flash("报名成功，已生成站内消息。", "success")
        else:
            flash("报名申请已提交，请等待管理员审核。", "success")
    return redirect(url_for("student.activity_detail", activity_id=activity_id))


@bp.post("/registrations/<int:registration_id>/cancel")
@student_required
def cancel_registration(registration_id: int):
    user = current_user()
    try:
        RegistrationService(get_db()).cancel(registration_id, user["student_id"])
    except BusinessError as exc:
        flash(str(exc), "error")
    else:
        flash("报名已取消。", "success")
    return redirect(url_for("student.my_registrations"))


@bp.route("/my/registrations")
@student_required
def my_registrations():
    user = current_user()
    rows = RegistrationRepository(get_db()).list_for_student(user["student_id"])
    return render_template(
        "student/my_registrations.html", registrations=rows, now=datetime.now()
    )


@bp.route("/messages")
@student_required
def messages():
    user = current_user()
    rows = MessageRepository(get_db()).list_for_student(user["student_id"])
    return render_template("student/messages.html", messages=rows)


@bp.post("/messages/<int:message_id>/read")
@student_required
def mark_message_read(message_id: int):
    user = current_user()
    conn = get_db()
    MessageRepository(conn).mark_read(message_id, user["student_id"])
    conn.commit()
    return redirect(url_for("student.messages"))


@bp.post("/messages/read-all")
@student_required
def mark_all_messages_read():
    user = current_user()
    conn = get_db()
    MessageRepository(conn).mark_all_read(user["student_id"])
    conn.commit()
    flash("全部消息已标记为已读。", "success")
    return redirect(url_for("student.messages"))
