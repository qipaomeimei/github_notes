'use strict';

const { Activity } = require('../domain/entities');

class ActivityRepository {
  constructor(db) {
    this.db = db;
  }

  findById(id) {
    const row = this.db.get('SELECT * FROM activities WHERE id = ?', [id]);
    return Activity.fromRow(row);
  }

  listAll() {
    return this.db.all('SELECT * FROM activities ORDER BY start_at ASC, id ASC').map(Activity.fromRow);
  }

  /**
   * 学生端活动列表：只展示未归档活动，支持名称关键字与报名方式筛选。
   */
  listForStudents({ keyword = '', policyType = '' } = {}) {
    const conditions = ["status = 'active'"];
    const params = [];
    if (keyword) {
      conditions.push('title LIKE ?');
      params.push(`%${keyword}%`);
    }
    if (policyType) {
      conditions.push('policy_type = ?');
      params.push(policyType);
    }
    const where = `WHERE ${conditions.join(' AND ')}`;
    return this.db
      .all(`SELECT * FROM activities ${where} ORDER BY start_at ASC, id ASC`, params)
      .map(Activity.fromRow);
  }

  create(data) {
    const id = this.db.insert(
      `INSERT INTO activities (title, category, start_at, location, capacity, policy_type, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [data.title, data.category, data.startAt, data.location, data.capacity, data.policyType, data.createdAt]
    );
    return this.findById(id);
  }

  update(id, data) {
    this.db.run(
      `UPDATE activities
          SET title = ?, category = ?, start_at = ?, location = ?, capacity = ?, policy_type = ?
        WHERE id = ?`,
      [data.title, data.category, data.startAt, data.location, data.capacity, data.policyType, id]
    );
    return this.findById(id);
  }

  remove(id) {
    this.db.run('DELETE FROM activities WHERE id = ?', [id]);
  }

  setStatus(id, status) {
    this.db.run('UPDATE activities SET status = ? WHERE id = ?', [status, id]);
    return this.findById(id);
  }
}

module.exports = { ActivityRepository };
