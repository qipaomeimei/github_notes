"""SQLite 仓储层。

所有 SQL 集中在此，服务层只处理业务规则与事务边界。
仓储对象持有同一个 sqlite3.Connection，事务由服务层统一控制。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from .domain.models import (
    ACTIVE_STATUSES,
    Activity,
    Registration,
    RegistrationStatus,
)
from .utils import now_str, to_db_time


def _to_activity(row: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=row["activity_id"],
        title=row["title"],
        category=row["category"],
        start_at=datetime.fromisoformat(row["start_at"]),
        location=row["location"],
        capacity=row["capacity"],
        policy_type=row["policy_type"],
        description=row["description"],
        is_deleted=bool(row["is_deleted"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _to_registration(row: sqlite3.Row) -> Registration:
    return Registration(
        registration_id=row["registration_id"],
        activity_id=row["activity_id"],
        student_id=row["student_id"],
        status=RegistrationStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class StudentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get(self, student_id: str):
        return self.conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()

    def get_grade(self, student_id: str) -> int:
        row = self.conn.execute(
            "SELECT grade FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        return int(row["grade"]) if row else 0

    def list_all(self):
        return self.conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()


class AccountRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def find_by_username(self, username: str):
        return self.conn.execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()


class ActivityRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self,
        *,
        title: str,
        category: str,
        start_at: datetime,
        location: str,
        capacity: int,
        policy_type: str,
        description: str,
    ) -> Activity:
        timestamp = now_str()
        cursor = self.conn.execute(
            """
            INSERT INTO activities
                (title, category, start_at, location, capacity, policy_type,
                 description, is_deleted, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                title,
                category,
                to_db_time(start_at),
                location,
                capacity,
                policy_type,
                description,
                timestamp,
                timestamp,
            ),
        )
        activity = self.get(cursor.lastrowid)
        assert activity is not None
        return activity

    def get(self, activity_id: int, include_deleted: bool = False) -> Activity | None:
        sql = "SELECT * FROM activities WHERE activity_id = ?"
        params: list = [activity_id]
        if not include_deleted:
            sql += " AND is_deleted = 0"
        row = self.conn.execute(sql, params).fetchone()
        return _to_activity(row) if row else None

    def list(self, keyword: str | None = None, include_deleted: bool = False) -> list[Activity]:
        sql = "SELECT * FROM activities WHERE 1 = 1"
        params: list = []
        if not include_deleted:
            sql += " AND is_deleted = 0"
        if keyword:
            sql += " AND title LIKE ?"
            params.append(f"%{keyword}%")
        sql += " ORDER BY start_at ASC, activity_id ASC"
        return [_to_activity(row) for row in self.conn.execute(sql, params).fetchall()]

    def update(
        self,
        activity_id: int,
        *,
        title: str,
        category: str,
        start_at: datetime,
        location: str,
        capacity: int,
        policy_type: str,
        description: str,
    ) -> Activity | None:
        self.conn.execute(
            """
            UPDATE activities
               SET title = ?, category = ?, start_at = ?, location = ?,
                   capacity = ?, policy_type = ?, description = ?, updated_at = ?
             WHERE activity_id = ? AND is_deleted = 0
            """,
            (
                title,
                category,
                to_db_time(start_at),
                location,
                capacity,
                policy_type,
                description,
                now_str(),
                activity_id,
            ),
        )
        return self.get(activity_id)

    def soft_delete(self, activity_id: int) -> bool:
        cursor = self.conn.execute(
            "UPDATE activities SET is_deleted = 1, updated_at = ? "
            "WHERE activity_id = ? AND is_deleted = 0",
            (now_str(), activity_id),
        )
        return cursor.rowcount > 0


class RegistrationRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(
        self, activity_id: int, student_id: str, status: RegistrationStatus
    ) -> Registration:
        timestamp = now_str()
        cursor = self.conn.execute(
            """
            INSERT INTO registrations
                (activity_id, student_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (activity_id, student_id, status.value, timestamp, timestamp),
        )
        registration = self.get(cursor.lastrowid)
        assert registration is not None
        return registration

    def get(self, registration_id: int) -> Registration | None:
        row = self.conn.execute(
            "SELECT * FROM registrations WHERE registration_id = ?",
            (registration_id,),
        ).fetchone()
        return _to_registration(row) if row else None

    def find_active(self, activity_id: int, student_id: str) -> Registration | None:
        placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
        row = self.conn.execute(
            f"""
            SELECT * FROM registrations
             WHERE activity_id = ? AND student_id = ?
               AND status IN ({placeholders})
             ORDER BY registration_id DESC LIMIT 1
            """,
            (activity_id, student_id, *(status.value for status in ACTIVE_STATUSES)),
        ).fetchone()
        return _to_registration(row) if row else None

    def update_status(self, registration_id: int, status: RegistrationStatus) -> None:
        self.conn.execute(
            "UPDATE registrations SET status = ?, updated_at = ? WHERE registration_id = ?",
            (status.value, now_str(), registration_id),
        )

    def count(self, activity_id: int, status: RegistrationStatus) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM registrations "
            "WHERE activity_id = ? AND status = ?",
            (activity_id, status.value),
        ).fetchone()
        return int(row["total"])

    def list_for_student(self, student_id: str):
        return self.conn.execute(
            """
            SELECT r.*, a.title, a.start_at, a.location, a.capacity,
                   a.policy_type, a.is_deleted
              FROM registrations r
              JOIN activities a ON a.activity_id = r.activity_id
             WHERE r.student_id = ?
             ORDER BY r.created_at DESC, r.registration_id DESC
            """,
            (student_id,),
        ).fetchall()

    def list_for_activity(self, activity_id: int, status: str | None = None):
        sql = """
            SELECT r.*, s.name AS student_name
              FROM registrations r
              JOIN students s ON s.student_id = r.student_id
             WHERE r.activity_id = ?
        """
        params: list = [activity_id]
        if status:
            sql += " AND r.status = ?"
            params.append(status)
        sql += " ORDER BY r.created_at ASC, r.registration_id ASC"
        return self.conn.execute(sql, params).fetchall()


class MessageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, student_id: str, activity_id: int | None, content: str) -> None:
        self.conn.execute(
            """
            INSERT INTO messages (student_id, activity_id, content, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (student_id, activity_id, content, now_str()),
        )

    def list_for_student(self, student_id: str):
        return self.conn.execute(
            """
            SELECT m.*, a.title AS activity_title
              FROM messages m
              LEFT JOIN activities a ON a.activity_id = m.activity_id
             WHERE m.student_id = ?
             ORDER BY m.created_at DESC, m.message_id DESC
            """,
            (student_id,),
        ).fetchall()

    def mark_read(self, message_id: int, student_id: str) -> None:
        self.conn.execute(
            "UPDATE messages SET is_read = 1 WHERE message_id = ? AND student_id = ?",
            (message_id, student_id),
        )

    def mark_all_read(self, student_id: str) -> None:
        self.conn.execute(
            "UPDATE messages SET is_read = 1 WHERE student_id = ? AND is_read = 0",
            (student_id,),
        )

    def unread_count(self, student_id: str) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM messages "
            "WHERE student_id = ? AND is_read = 0",
            (student_id,),
        ).fetchone()
        return int(row["total"])


class EventLogRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def reserve(self, event_id: str) -> bool:
        """成功插入表示首次分发；主键冲突表示已分发过。"""
        try:
            self.conn.execute(
                "INSERT INTO dispatched_events (event_id, dispatched_at) VALUES (?, ?)",
                (event_id, now_str()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


class NotificationFailureRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def record(self, event_id: str, handler: str, error: str) -> None:
        self.conn.execute(
            """
            INSERT INTO notification_failures (event_id, handler, error, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, handler, error, now_str()),
        )

    def count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM notification_failures"
        ).fetchone()
        return int(row["total"])


class EmailOutboxRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(
        self,
        *,
        student_id: str,
        to_email: str,
        subject: str,
        body: str,
        event_id: str | None,
        status: str = "sent",
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO email_outbox
                (student_id, to_email, subject, body, event_id, status, error, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                to_email,
                subject,
                body,
                event_id,
                status,
                error,
                now_str(),
            ),
        )

    def list_for_student(self, student_id: str):
        return self.conn.execute(
            """
            SELECT * FROM email_outbox
             WHERE student_id = ?
             ORDER BY sent_at DESC, outbox_id DESC
            """,
            (student_id,),
        ).fetchall()

    def count(self, status: str | None = None) -> int:
        sql = "SELECT COUNT(*) AS total FROM email_outbox"
        params: list = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        row = self.conn.execute(sql, params).fetchone()
        return int(row["total"])
