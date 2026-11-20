'use strict';

const { PolicyLabel, PolicyDescription, RegistrationStatusLabel, Role } = require('./enums');

/** 活动实体 */
class Activity {
  constructor(props) {
    this.id = props.id;
    this.title = props.title;
    this.category = props.category;
    this.startAt = props.startAt;
    this.location = props.location;
    this.capacity = props.capacity;
    this.policyType = props.policyType;
    this.status = props.status || 'active';
    this.createdAt = props.createdAt;
  }

  get policyLabel() {
    return PolicyLabel[this.policyType] || this.policyType;
  }

  get policyDescription() {
    return PolicyDescription[this.policyType] || '';
  }

  hasStarted(now = new Date()) {
    return new Date(this.startAt).getTime() <= now.getTime();
  }

  isArchived() {
    return this.status === 'archived';
  }

  remainingSeats(approvedCount) {
    return Math.max(this.capacity - approvedCount, 0);
  }

  static fromRow(row) {
    if (!row) return null;
    return new Activity({
      id: Number(row.id),
      title: row.title,
      category: row.category,
      startAt: row.start_at,
      location: row.location,
      capacity: Number(row.capacity),
      policyType: row.policy_type,
      status: row.status,
      createdAt: row.created_at,
    });
  }
}

/** 学生 / 管理员账号实体 */
class Student {
  constructor(props) {
    this.id = props.id;
    this.name = props.name;
    this.role = props.role;
    this.passwordHash = props.passwordHash;
    this.passwordSalt = props.passwordSalt;
  }

  isAdmin() {
    return this.role === Role.ADMIN;
  }

  static fromRow(row) {
    if (!row) return null;
    return new Student({
      id: row.id,
      name: row.name,
      role: row.role,
      passwordHash: row.password_hash,
      passwordSalt: row.password_salt,
    });
  }
}

/** 报名记录实体 */
class Registration {
  constructor(props) {
    this.id = props.id;
    this.activityId = props.activityId;
    this.studentId = props.studentId;
    this.status = props.status;
    this.waitlistSeq = props.waitlistSeq === undefined ? null : props.waitlistSeq;
    this.createdAt = props.createdAt;
    this.updatedAt = props.updatedAt;
  }

  get statusLabel() {
    return RegistrationStatusLabel[this.status] || this.status;
  }

  isActive() {
    return this.status === 'pending' || this.status === 'approved' || this.status === 'waitlisted';
  }

  canCancel() {
    return this.isActive();
  }

  static fromRow(row) {
    if (!row) return null;
    return new Registration({
      id: Number(row.id),
      activityId: Number(row.activity_id),
      studentId: row.student_id,
      status: row.status,
      waitlistSeq: row.waitlist_seq,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    });
  }
}

/** 站内消息实体 */
class Message {
  constructor(props) {
    this.id = props.id;
    this.studentId = props.studentId;
    this.activityId = props.activityId;
    this.content = props.content;
    this.createdAt = props.createdAt;
    this.isRead = Boolean(props.isRead);
  }

  static fromRow(row) {
    if (!row) return null;
    return new Message({
      id: Number(row.id),
      studentId: row.student_id,
      activityId: row.activity_id === null ? null : Number(row.activity_id),
      content: row.content,
      createdAt: row.created_at,
      isRead: row.is_read,
    });
  }
}

module.exports = { Activity, Student, Registration, Message };
