'use strict';

const { Registration } = require('../domain/entities');
const { ACTIVE_REGISTRATION_STATUSES } = require('../domain/enums');

class RegistrationRepository {
  constructor(db) {
    this.db = db;
  }

  findById(id) {
    const row = this.db.get('SELECT * FROM registrations WHERE id = ?', [id]);
    return Registration.fromRow(row);
  }

  /** 同一学生对同一活动的有效报名（待审核 / 已通过） */
  findActive(activityId, studentId) {
    const placeholders = ACTIVE_REGISTRATION_STATUSES.map(() => '?').join(', ');
    const row = this.db.get(
      `SELECT * FROM registrations
        WHERE activity_id = ? AND student_id = ? AND status IN (${placeholders})
        ORDER BY id DESC LIMIT 1`,
      [activityId, studentId, ...ACTIVE_REGISTRATION_STATUSES]
    );
    return Registration.fromRow(row);
  }

  create({ activityId, studentId, status, waitlistSeq = null, now = new Date().toISOString() }) {
    const id = this.db.insert(
      `INSERT INTO registrations (activity_id, student_id, status, waitlist_seq, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
      [activityId, studentId, status, waitlistSeq, now, now]
    );
    return this.findById(id);
  }

  updateStatus(id, status) {
    this.db.run('UPDATE registrations SET status = ?, updated_at = ? WHERE id = ?', [
      status,
      new Date().toISOString(),
      id,
    ]);
    return this.findById(id);
  }

  countByStatus(activityId, status) {
    const row = this.db.get(
      'SELECT COUNT(*) AS total FROM registrations WHERE activity_id = ? AND status = ?',
      [activityId, status]
    );
    return Number(row.total);
  }

  countByActivity(activityId) {
    const row = this.db.get('SELECT COUNT(*) AS total FROM registrations WHERE activity_id = ?', [activityId]);
    return Number(row.total);
  }

  statusCounts(activityId) {
    const rows = this.db.all(
      'SELECT status, COUNT(*) AS total FROM registrations WHERE activity_id = ? GROUP BY status',
      [activityId]
    );
    const result = { pending: 0, approved: 0, rejected: 0, cancelled: 0, waitlisted: 0 };
    for (const row of rows) {
      result[row.status] = Number(row.total);
    }
    return result;
  }

  /** 候补队首：按候补序号、提交时间排序 */
  findWaitlistHead(activityId) {
    const row = this.db.get(
      `SELECT * FROM registrations
        WHERE activity_id = ? AND status = 'waitlisted'
        ORDER BY waitlist_seq ASC, created_at ASC, id ASC
        LIMIT 1`,
      [activityId]
    );
    return Registration.fromRow(row);
  }

  /** 某学生全部报名（含活动信息），按创建时间倒序 */
  listByStudent(studentId) {
    return this.db.all(
      `SELECT r.id, r.status, r.waitlist_seq, r.created_at, r.updated_at,
              a.id AS activity_id, a.title, a.category, a.start_at, a.location, a.capacity, a.policy_type
         FROM registrations r
         JOIN activities a ON a.id = r.activity_id
        WHERE r.student_id = ?
        ORDER BY r.created_at DESC, r.id DESC`,
      [studentId]
    );
  }

  /** 管理员待审核列表（含学生与活动信息） */
  listPending() {
    return this.db.all(
      `SELECT r.id, r.status, r.created_at,
              s.id AS student_id, s.name AS student_name,
              a.id AS activity_id, a.title, a.start_at, a.capacity, a.policy_type
         FROM registrations r
         JOIN students s ON s.id = r.student_id
         JOIN activities a ON a.id = r.activity_id
        WHERE r.status = 'pending'
        ORDER BY r.created_at ASC, r.id ASC`
    );
  }

  listByActivity(activityId) {
    return this.db.all(
      `SELECT r.id, r.status, r.created_at, s.id AS student_id, s.name AS student_name
         FROM registrations r
         JOIN students s ON s.id = r.student_id
        WHERE r.activity_id = ?
        ORDER BY r.created_at ASC, r.id ASC`,
      [activityId]
    );
  }
}

module.exports = { RegistrationRepository };
