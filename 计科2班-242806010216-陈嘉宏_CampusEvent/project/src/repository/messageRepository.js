'use strict';

const { Message } = require('../domain/entities');

class MessageRepository {
  constructor(db) {
    this.db = db;
  }

  create({ studentId, activityId = null, content, now = new Date().toISOString() }) {
    const id = this.db.insert(
      'INSERT INTO messages (student_id, activity_id, content, created_at, is_read) VALUES (?, ?, ?, ?, 0)',
      [studentId, activityId, content, now]
    );
    return Message.fromRow(this.db.get('SELECT * FROM messages WHERE id = ?', [id]));
  }

  listByStudent(studentId) {
    return this.db
      .all('SELECT * FROM messages WHERE student_id = ? ORDER BY created_at DESC, id DESC', [studentId])
      .map(Message.fromRow);
  }

  markAllRead(studentId) {
    this.db.run('UPDATE messages SET is_read = 1 WHERE student_id = ?', [studentId]);
  }

  unreadCount(studentId) {
    const row = this.db.get('SELECT COUNT(*) AS total FROM messages WHERE student_id = ? AND is_read = 0', [
      studentId,
    ]);
    return Number(row.total);
  }
}

module.exports = { MessageRepository };
