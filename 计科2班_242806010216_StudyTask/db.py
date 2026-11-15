"""StudyTask 数据库访问层（SQLite）。"""

import sqlite3
from datetime import datetime

PRIORITIES = ("高", "中", "低")
STATUSES = ("待完成", "进行中", "已完成")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    course      TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    due_date    TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT '中',
    status      TEXT NOT NULL DEFAULT '待完成',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_course ON tasks(course);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
"""


def connect(path):
    """打开数据库连接，行以字典方式访问。"""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path):
    """创建数据表（幂等）。"""
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_tasks(path, course=None, status=None, priority=None):
    """按课程/状态/优先级筛选任务，支持组合条件。"""
    sql = "SELECT * FROM tasks WHERE 1 = 1"
    params = []
    if course:
        sql += " AND course = ?"
        params.append(course)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    # 未完成的任务排在前面，其次按截止日期升序、创建顺序倒序
    sql += """
        ORDER BY CASE status WHEN '已完成' THEN 1 ELSE 0 END,
                 due_date ASC, id DESC
    """
    conn = connect(path)
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_task(path, task_id):
    conn = connect(path)
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_task(path, data):
    now = _now()
    conn = connect(path)
    try:
        cur = conn.execute(
            """INSERT INTO tasks
               (title, course, description, due_date, priority, status,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"],
                data["course"],
                data["description"],
                data["due_date"],
                data["priority"],
                data["status"],
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_task(path, task_id, data):
    conn = connect(path)
    try:
        conn.execute(
            """UPDATE tasks SET title = ?, course = ?, description = ?,
                   due_date = ?, priority = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (
                data["title"],
                data["course"],
                data["description"],
                data["due_date"],
                data["priority"],
                data["status"],
                _now(),
                task_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_status(path, task_id, status):
    conn = connect(path)
    try:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), task_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_task(path, task_id):
    conn = connect(path)
    try:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()


def list_courses(path):
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT course FROM tasks ORDER BY course COLLATE NOCASE"
        ).fetchall()
        return [row["course"] for row in rows]
    finally:
        conn.close()


def statistics(path):
    """返回任务总数、已完成数、完成率（总数为 0 时完成率为 0）。"""
    conn = connect(path)
    try:
        row = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status = '已完成' THEN 1 ELSE 0 END) AS done
               FROM tasks"""
        ).fetchone()
        total = row["total"] or 0
        done = row["done"] or 0
        rate = round(done * 100 / total) if total else 0
        return {"total": total, "done": done, "rate": rate}
    finally:
        conn.close()
