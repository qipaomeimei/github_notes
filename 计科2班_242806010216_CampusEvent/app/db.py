"""SQLite 连接、建库与演示数据初始化。"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash

from .utils import to_db_time


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_database(seed: bool = True) -> None:
    conn = get_db()
    with current_app.open_resource("schema.sql") as schema_file:
        conn.executescript(schema_file.read().decode("utf-8"))
    _apply_migrations(conn)
    conn.commit()

    if seed:
        row = conn.execute("SELECT COUNT(*) AS total FROM accounts").fetchone()
        if int(row["total"]) == 0:
            _seed_demo_data(conn)
            conn.commit()


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """把 baseline-v1 数据库平滑升级到 change-v2（幂等）。

    1. students 增加 email 列（邮件通知）；
    2. 有效报名唯一索引加入 waitlisted 状态；
    3. 为演示学生补齐邮箱。
    新库由 schema.sql 直接创建，本函数不会产生副作用。
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(students)")}
    if "email" not in columns:
        conn.execute("ALTER TABLE students ADD COLUMN email TEXT NOT NULL DEFAULT ''")

    index_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' "
        "AND name = 'ux_registration_active'"
    ).fetchone()
    if index_row is not None and "waitlisted" not in (index_row["sql"] or ""):
        conn.execute("DROP INDEX ux_registration_active")
        conn.execute(
            """
            CREATE UNIQUE INDEX ux_registration_active
                ON registrations(activity_id, student_id)
                WHERE status IN ('pending', 'approved', 'waitlisted')
            """
        )

    demo_emails = {
        "S001": "zhangsan@example.edu.cn",
        "S002": "lisi@example.edu.cn",
        "S003": "wangwu@example.edu.cn",
    }
    for student_id, email in demo_emails.items():
        conn.execute(
            "UPDATE students SET email = ? WHERE student_id = ? AND email = ''",
            (email, student_id),
        )


def _seed_demo_data(conn: sqlite3.Connection) -> None:
    """固定演示账号与活动；时间相对当前日期生成，避免部署后全部过期。"""
    students = [
        ("S001", "张三", "zhangsan@example.edu.cn"),
        ("S002", "李四", "lisi@example.edu.cn"),
        ("S003", "王五", "wangwu@example.edu.cn"),
    ]
    conn.executemany(
        "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?)", students
    )

    accounts = [
        ("admin", generate_password_hash("admin123"), "admin", None),
        ("s001", generate_password_hash("123456"), "student", "S001"),
        ("s002", generate_password_hash("123456"), "student", "S002"),
        ("s003", generate_password_hash("123456"), "student", "S003"),
    ]
    conn.executemany(
        "INSERT INTO accounts (username, password_hash, role, student_id) "
        "VALUES (?, ?, ?, ?)",
        accounts,
    )

    now = datetime.now()
    base = now.replace(minute=0, second=0, microsecond=0)

    def at(days: int, hour: int, minute: int = 0) -> str:
        return to_db_time((base + timedelta(days=days)).replace(hour=hour, minute=minute))

    timestamp = now.isoformat(timespec="seconds")
    activities = [
        (
            "校园迎新篮球赛",
            "文体活动",
            at(7, 18),
            "东区篮球场",
            20,
            "direct",
            "面向全校学生的迎新篮球赛，欢迎组队报名参加。",
        ),
        (
            "大学生程序设计竞赛校内选拔",
            "学术科技",
            at(12, 9),
            "实验楼 A302 机房",
            2,
            "approval",
            "校内选拔赛，名额有限，报名后需管理员审核。",
        ),
        (
            "校园歌手大赛",
            "文体活动",
            at(9, 19),
            "大学生活动中心",
            2,
            "waitlist",
            "名额已满时可加入候补队列，出现空位按顺序自动递补。",
        ),
        (
            "人工智能前沿讲座",
            "讲座报告",
            at(3, 19),
            "图书馆报告厅",
            100,
            "direct",
            "介绍大模型与智能体应用的最新进展。",
        ),
        (
            "青年志愿者社区服务",
            "志愿公益",
            at(18, 8, 30),
            "学校南门集合",
            15,
            "direct",
            "前往社区开展义务维修与科普服务。",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO activities
            (title, category, start_at, location, capacity, policy_type,
             description, is_deleted, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        [
            (title, category, start_at, location, capacity, policy, description, timestamp, timestamp)
            for (title, category, start_at, location, capacity, policy, description) in activities
        ],
    )

    # 一条待审核记录，便于直接演示管理员审批
    approval_activity = conn.execute(
        "SELECT activity_id, title FROM activities WHERE policy_type = 'approval' "
        "ORDER BY activity_id LIMIT 1"
    ).fetchone()
    if approval_activity is not None:
        conn.execute(
            """
            INSERT INTO registrations
                (activity_id, student_id, status, created_at, updated_at)
            VALUES (?, 'S001', 'pending', ?, ?)
            """,
            (approval_activity["activity_id"], timestamp, timestamp),
        )
        conn.execute(
            """
            INSERT INTO messages (student_id, activity_id, content, is_read, created_at)
            VALUES ('S001', ?, ?, 0, ?)
            """,
            (
                approval_activity["activity_id"],
                f"报名申请已提交：「{approval_activity['title']}」待管理员审核。",
                timestamp,
            ),
        )


@click.command("init-db")
@click.option("--no-seed", is_flag=True, help="只建表，不写入演示数据")
def init_db_command(no_seed: bool) -> None:
    """初始化数据库结构。"""
    init_database(seed=not no_seed)
    click.echo("数据库初始化完成。")


@click.command("reset-db")
def reset_db_command() -> None:
    """删除数据库文件并重新初始化（危险操作，仅用于演示环境）。"""
    path = current_app.config["DATABASE"]
    close_db()
    if os.path.exists(path):
        os.remove(path)
    init_database(seed=True)
    click.echo("数据库已重置并写入演示数据。")
