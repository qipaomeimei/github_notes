'use strict';

const { createSalt, hashPassword } = require('../domain/password');

const DEMO_STUDENTS = [
  { id: 'admin', name: '系统管理员', role: 'admin', password: 'admin123' },
  { id: 's1001', name: '张三', role: 'student', password: '123456' },
  { id: 's1002', name: '李四', role: 'student', password: '123456' },
  { id: 's1003', name: '王五', role: 'student', password: '123456' },
  { id: 's1004', name: '赵六', role: 'student', password: '123456' },
];

function addDays(base, days, hour = 14, minute = 0) {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

/**
 * 演示数据：仅在数据库为空时写入。
 * 活动时间相对当前时间生成，保证任何时候启动都处于“可报名”状态。
 */
function seedDatabase(db, now = () => new Date()) {
  const row = db.get('SELECT COUNT(*) AS total FROM students');
  if (Number(row.total) > 0) return false;

  const base = now();
  db.transaction(() => {
    for (const student of DEMO_STUDENTS) {
      const salt = createSalt();
      db.run(
        'INSERT INTO students (id, name, role, password_hash, password_salt) VALUES (?, ?, ?, ?, ?)',
        [student.id, student.name, student.role, hashPassword(student.password, salt), salt]
      );
    }

    const activities = [
      ['校园歌手大赛', '文艺活动', addDays(base, 18, 19, 0), '大学生活动中心', 2, 'direct'],
      ['程序设计竞赛', '学科竞赛', addDays(base, 25, 14, 0), '信息楼 A301', 30, 'approval'],
      ['图书馆志愿服务', '志愿服务', addDays(base, 9, 9, 0), '图书馆一楼', 1, 'direct'],
      ['人工智能前沿讲座', '学术讲座', addDays(base, 5, 15, 30), '学术报告厅', 100, 'direct'],
    ];
    const createdAt = base.toISOString();
    for (const activity of activities) {
      db.run(
        `INSERT INTO activities (title, category, start_at, location, capacity, policy_type, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [...activity, createdAt]
      );
    }
  });
  return true;
}

module.exports = { seedDatabase, DEMO_STUDENTS };
