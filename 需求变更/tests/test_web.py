"""页面与权限的 HTTP 验收。"""
from __future__ import annotations

from datetime import datetime, timedelta

from app import create_app
from app.db import get_db
from app.services import ActivityService, RegistrationService

from tests.helpers import create_activity, login


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "演示账号" in response.get_data(as_text=True)


def test_student_login_and_navigation(client):
    response = login(client, "s001", "123456")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "活动广场" in body
    assert "我的报名" in body


def test_admin_login_goes_to_dashboard(client):
    response = login(client, "admin", "admin123")
    assert response.status_code == 200
    assert "活动管理" in response.get_data(as_text=True)


def test_student_cannot_access_admin(client):
    login(client, "s001", "123456")
    response = client.get("/admin/")
    assert response.status_code == 403


def test_admin_creates_activity_through_form(app, client):
    login(client, "admin", "admin123")
    start_at = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        "/admin/activities/new",
        data={
            "title": "网页创建的讲座",
            "category": "讲座报告",
            "start_at": start_at,
            "location": "报告厅",
            "capacity": "30",
            "policy_type": "direct",
            "description": "通过管理员表单创建。",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "创建成功" in response.get_data(as_text=True)

    with app.app_context():
        activities = ActivityService(get_db()).list_activities()
        assert len(activities) == 1
        assert activities[0].title == "网页创建的讲座"


def test_invalid_activity_form_rejected(app, client):
    login(client, "admin", "admin123")
    start_at = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M")
    response = client.post(
        "/admin/activities/new",
        data={
            "title": "非法名额活动",
            "category": "讲座报告",
            "start_at": start_at,
            "location": "报告厅",
            "capacity": "0",
            "policy_type": "direct",
            "description": "",
        },
    )
    assert response.status_code == 400
    assert "人数上限" in response.get_data(as_text=True)

    with app.app_context():
        row = get_db().execute("SELECT COUNT(*) AS total FROM activities").fetchone()
        assert row["total"] == 0


def test_student_register_and_view_message(app, client):
    with app.app_context():
        activity = create_activity(get_db(), capacity=2)

    login(client, "s001", "123456")
    response = client.post(
        f"/activities/{activity.activity_id}/register", follow_redirects=True
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "报名成功" in body
    assert "已通过" in body

    messages = client.get("/messages")
    assert "报名成功" in messages.get_data(as_text=True)


def test_student_cancel_registration(app, client):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, capacity=2)
        from app.services import RegistrationService

        registration = RegistrationService(conn).register(activity.activity_id, "S001")
        registration_id = registration.registration_id

    login(client, "s001", "123456")
    response = client.post(
        f"/registrations/{registration_id}/cancel", follow_redirects=True
    )
    assert response.status_code == 200
    assert "报名已取消" in response.get_data(as_text=True)


def test_admin_approves_registration_through_form(app, client):
    with app.app_context():
        conn = get_db()
        activity = create_activity(conn, policy_type="approval", capacity=2)
        from app.services import RegistrationService

        registration = RegistrationService(conn).register(activity.activity_id, "S001")
        registration_id = registration.registration_id

    login(client, "admin", "admin123")
    response = client.post(
        f"/admin/registrations/{registration_id}/approve", follow_redirects=True
    )
    assert response.status_code == 200
    assert "已批准" in response.get_data(as_text=True)


def test_csrf_rejects_post_without_token(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "csrf.db"),
            "SECRET_KEY": "csrf-test",
            "SEED_DEMO": False,
            "CSRF_ENABLED": True,
        }
    )
    client = app.test_client()
    client.get("/login")  # 生成 session 中的 CSRF token
    response = client.post(
        "/login", data={"username": "s001", "password": "123456"}
    )
    assert response.status_code == 400
    assert "表单已过期" in response.get_data(as_text=True)
