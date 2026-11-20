'use strict';

/** 邮件发件箱（模拟邮件渠道，便于验收时查看通知内容） */
class EmailRepository {
  constructor(db) {
    this.db = db;
  }

  create({ studentId, eventId, subject, body, now = new Date().toISOString() }) {
    const id = this.db.insert(
      `INSERT INTO email_outbox (student_id, event_id, subject, body, created_at)
       VALUES (?, ?, ?, ?, ?)`,
      [studentId, eventId, subject, body, now]
    );
    return this.db.get('SELECT * FROM email_outbox WHERE id = ?', [id]);
  }

  listRecent(limit = 100) {
    return this.db.all(
      `SELECT e.*, s.name AS student_name
         FROM email_outbox e
         JOIN students s ON s.id = e.student_id
        ORDER BY e.created_at DESC, e.id DESC
        LIMIT ?`,
      [limit]
    );
  }

  count() {
    return Number(this.db.get('SELECT COUNT(*) AS total FROM email_outbox').total);
  }
}

module.exports = { EmailRepository };
