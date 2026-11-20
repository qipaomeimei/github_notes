'use strict';

/** 通知投递留痕：同一事件的同一渠道只记录一条，作为“避免重复通知”的幂等依据 */
class NotificationLogRepository {
  constructor(db) {
    this.db = db;
  }

  has(eventId, channel) {
    const row = this.db.get('SELECT id FROM notification_log WHERE event_id = ? AND channel = ?', [
      eventId,
      channel,
    ]);
    return Boolean(row);
  }

  record(eventId, channel, status, detail = null) {
    this.db.run(
      `INSERT INTO notification_log (event_id, channel, status, detail, created_at)
       VALUES (?, ?, ?, ?, ?)`,
      [eventId, channel, status, detail, new Date().toISOString()]
    );
  }

  listByEvent(eventId) {
    return this.db.all('SELECT * FROM notification_log WHERE event_id = ?', [eventId]);
  }

  countFailed() {
    const row = this.db.get("SELECT COUNT(*) AS total FROM notification_log WHERE status = 'failed'");
    return Number(row.total);
  }
}

module.exports = { NotificationLogRepository };
