from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


@pytest.fixture
def app(tmp_path):
    database = tmp_path / "test.db"
    application = create_app(
        {
            "TESTING": True,
            "DATABASE": str(database),
            "SECRET_KEY": "test-secret",
            "CSRF_ENABLED": False,
            "SEED_DEMO": False,
        }
    )
    with application.app_context():
        conn = get_db()
        conn.executemany(
            "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?)",
            [
                ("S001", "张三", "zhangsan@example.edu.cn"),
                ("S002", "李四", "lisi@example.edu.cn"),
                ("S003", "王五", "wangwu@example.edu.cn"),
            ],
        )
        conn.executemany(
            "INSERT INTO accounts (username, password_hash, role, student_id) "
            "VALUES (?, ?, ?, ?)",
            [
                ("admin", generate_password_hash("admin123"), "admin", None),
                ("s001", generate_password_hash("123456"), "student", "S001"),
                ("s002", generate_password_hash("123456"), "student", "S002"),
                ("s003", generate_password_hash("123456"), "student", "S003"),
            ],
        )
        conn.commit()
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_path(app):
    return app.config["DATABASE"]
