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
    """幂等迁移：给已存在的数据库补上新增列，不破坏已有数据。"""
    cols = {
        row["name"] for row in conn.execute("PRAGMA table_info(students)")
    }
    if "grade" not in cols:
        conn.execute("ALTER TABLE students ADD COLUMN grade INTEGER NOT NULL DEFAULT 0")
        # 把历史演示学生设为大二/大三，便于展示年级限定活动
        conn.execute("UPDATE students SET grade = 2 WHERE student_id = 'S001'")
        conn.execute("UPDATE students SET grade = 3 WHERE student_id = 'S002'")
        conn.execute("UPDATE students SET grade = 1 WHERE student_id = 'S003'")


def _seed_demo_data(conn: sqlite3.Connection) -> None:
    """固定演示账号与活动；时间相对当前日期生成，避免部署后全部过期。"""
    students = [
        # 年级：1 大一、2 大二、3 大三、4 大四
        ("S001", "张三", 2),
        ("S002", "李四", 3),
        ("S003", "王五", 1),
    ]
    conn.executemany(
        "INSERT INTO students (student_id, name, grade) VALUES (?, ?, ?)", students
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
        (
            "大二大三实习经验分享会",
            "就业指导",
            at(9, 19),
            "学生活动中心报告厅",
            80,
            "grade-restricted-direct",
            "仅面向大二、大三学生的求职经验分享；大一、大四无法报名。",
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
