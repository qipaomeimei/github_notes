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
            "INSERT INTO students (student_id, name, grade) VALUES (?, ?, ?)",
            [
                ("S001", "张三", 2),  # 大二
                ("S002", "李四", 3),  # 大三
                ("S003", "王五", 1),  # 大一
                ("S004", "赵六", 4),  # 大四
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
