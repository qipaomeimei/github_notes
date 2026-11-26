"""管理员端页面。"""
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

from ..auth import admin_required
from ..db import get_db
from ..domain.models import STATUS_LABELS
from ..errors import BusinessError
from ..repositories import RegistrationRepository
from ..services import ActivityService, RegistrationService

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _form_payload(form) -> dict:
    return {
        "title": form.get("title", ""),
        "category": form.get("category", ""),
        "start_at": form.get("start_at", ""),
        "location": form.get("location", ""),
        "capacity": form.get("capacity", ""),
        "policy_type": form.get("policy_type", ""),
        "description": form.get("description", ""),
    }


@bp.route("/")
@admin_required
def dashboard():
    conn = get_db()
    service = ActivityService(conn)
    activities = service.list_activities(include_deleted=True)
    items = [
        {"activity": activity, "stats": service.stats(activity.activity_id)}
        for activity in activities
    ]
    return render_template("admin/dashboard.html", items=items, now=datetime.now())


@bp.route("/activities/new", methods=["GET", "POST"])
@admin_required
def new_activity():
    if request.method == "POST":
        try:
            activity = ActivityService(get_db()).create_activity(**_form_payload(request.form))
        except BusinessError as exc:
            flash(str(exc), "error")
            return render_template(
                "admin/activity_form.html", activity=None, form=request.form, mode="new"
            ), 400
        flash(f"活动「{activity.title}」创建成功。", "success")
        return redirect(url_for("admin.activity_detail", activity_id=activity.activity_id))
    return render_template(
        "admin/activity_form.html", activity=None, form=None, mode="new"
    )


@bp.route("/activities/<int:activity_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_activity(activity_id: int):
    service = ActivityService(get_db())
    activity = service.get_activity(activity_id)
    if activity is None:
        abort(404)

    if request.method == "POST":
        try:
            updated = service.update_activity(activity_id, **_form_payload(request.form))
        except BusinessError as exc:
            flash(str(exc), "error")
            return render_template(
                "admin/activity_form.html",
                activity=activity,
                form=request.form,
                mode="edit",
            ), 400
        flash(f"活动「{updated.title}」已更新。", "success")
        return redirect(url_for("admin.activity_detail", activity_id=activity_id))

    return render_template(
        "admin/activity_form.html", activity=activity, form=None, mode="edit"
    )


@bp.post("/activities/<int:activity_id>/delete")
@admin_required
def delete_activity(activity_id: int):
    try:
        ActivityService(get_db()).soft_delete_activity(activity_id)
    except BusinessError as exc:
        flash(str(exc), "error")
    else:
        flash("活动已下架（软删除），历史报名与通知记录仍保留。", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/activities/<int:activity_id>")
@admin_required
def activity_detail(activity_id: int):
    conn = get_db()
    service = ActivityService(conn)
    activity = service.get_activity(activity_id, include_deleted=True)
    if activity is None:
        abort(404)

    status_filter = request.args.get("status", "").strip()
    if status_filter not in STATUS_LABELS:
        status_filter = ""
    registrations = RegistrationRepository(conn).list_for_activity(
        activity_id, status_filter or None
    )
    return render_template(
        "admin/activity_detail.html",
        activity=activity,
        stats=service.stats(activity_id),
        registrations=registrations,
        status_filter=status_filter,
        now=datetime.now(),
    )


@bp.post("/registrations/<int:registration_id>/approve")
@admin_required
def approve_registration(registration_id: int):
    conn = get_db()
    registration = RegistrationRepository(conn).get(registration_id)
    if registration is None:
        abort(404)
    try:
        RegistrationService(conn).approve(registration_id)
    except BusinessError as exc:
        flash(str(exc), "error")
    else:
        flash("已批准该报名申请，并生成站内通知。", "success")
    return redirect(
        url_for("admin.activity_detail", activity_id=registration.activity_id)
    )


@bp.post("/registrations/<int:registration_id>/reject")
@admin_required
def reject_registration(registration_id: int):
    conn = get_db()
    registration = RegistrationRepository(conn).get(registration_id)
    if registration is None:
        abort(404)
    try:
        RegistrationService(conn).reject(registration_id)
    except BusinessError as exc:
        flash(str(exc), "error")
    else:
        flash("已拒绝该报名申请，并生成站内通知。", "success")
    return redirect(
        url_for("admin.activity_detail", activity_id=registration.activity_id)
    )
