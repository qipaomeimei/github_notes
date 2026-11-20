'use strict';

/** 角色 */
const Role = Object.freeze({
  STUDENT: 'student',
  ADMIN: 'admin',
});

/** 报名状态（数据库存储英文码，界面显示中文标签） */
const RegistrationStatus = Object.freeze({
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
  CANCELLED: 'cancelled',
  WAITLISTED: 'waitlisted',
});

const RegistrationStatusLabel = Object.freeze({
  pending: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  cancelled: '已取消',
  waitlisted: '候补中',
});

/** 有效报名：占用“唯一有效报名”约束的状态 */
const ACTIVE_REGISTRATION_STATUSES = [
  RegistrationStatus.PENDING,
  RegistrationStatus.APPROVED,
  RegistrationStatus.WAITLISTED,
];

/** 报名方式（策略标识） */
const PolicyType = Object.freeze({
  DIRECT: 'direct',
  APPROVAL: 'approval',
  WAITLIST: 'waitlist',
});

const PolicyLabel = Object.freeze({
  direct: '直接报名',
  approval: '审核报名',
  waitlist: '候补报名',
});

const PolicyDescription = Object.freeze({
  direct: '名额充足时报名立即通过',
  approval: '提交后需管理员审核，名额以审核通过为准',
  waitlist: '名额充足时立即通过；满员时进入候补队列，名额释放后按顺序自动递补',
});

/** 活动状态（变更单 CR-01 引入软删除） */
const ActivityStatus = Object.freeze({
  ACTIVE: 'active',
  ARCHIVED: 'archived',
});

const ActivityStatusLabel = Object.freeze({
  active: '进行中',
  archived: '已归档',
});

module.exports = {
  Role,
  RegistrationStatus,
  RegistrationStatusLabel,
  ACTIVE_REGISTRATION_STATUSES,
  PolicyType,
  PolicyLabel,
  PolicyDescription,
  ActivityStatus,
  ActivityStatusLabel,
};
