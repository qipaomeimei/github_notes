'use strict';

const { BusinessError } = require('../domain/errors');

/**
 * 活动管理服务：活动 CRUD、报名统计、审批列表。
 * 活动字段校验与“容量不得小于已通过人数”等规则集中在此。
 */
class ActivityService {
  constructor({ db, activityRepository, registrationRepository, policyFactory, now }) {
    this.db = db;
    this.activityRepository = activityRepository;
    this.registrationRepository = registrationRepository;
    this.policyFactory = policyFactory;
    this.now = now;
  }

  listForStudents({ keyword = '', policyType = '' } = {}) {
    const activities = this.activityRepository.listForStudents({ keyword, policyType });
    return activities.map((activity) => ({ activity, stats: this.getStats(activity.id) }));
  }

  listForAdmin() {
    const activities = this.activityRepository.listAll();
    return activities.map((activity) => ({ activity, stats: this.getStats(activity.id) }));
  }

  getActivity(activityId) {
    return this.activityRepository.findById(activityId);
  }

  getStats(activityId) {
    const activity = this.activityRepository.findById(activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    const counts = this.registrationRepository.statusCounts(activityId);
    return {
      approved: counts.approved,
      pending: counts.pending,
      rejected: counts.rejected,
      cancelled: counts.cancelled,
      waitlisted: counts.waitlisted,
      remaining: Math.max(activity.capacity - counts.approved, 0),
    };
  }

  create(input) {
    const data = this.validate(input);
    return this.activityRepository.create({ ...data, createdAt: this.now().toISOString() });
  }

  update(activityId, input) {
    const activity = this.activityRepository.findById(activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    if (activity.isArchived()) {
      throw new BusinessError('ACTIVITY_ARCHIVED', '活动已归档，请先恢复后再编辑');
    }
    const data = this.validate(input);

    const approved = this.registrationRepository.countByStatus(activityId, 'approved');
    if (data.capacity < approved) {
      throw new BusinessError('CAPACITY_TOO_SMALL', `容量不能小于已通过人数（当前已通过 ${approved} 人）`);
    }
    const activeTotal = this.registrationRepository.countByActivity(activityId);
    if (activeTotal > 0 && data.policyType !== activity.policyType) {
      throw new BusinessError('POLICY_CHANGE_FORBIDDEN', '活动已有报名记录，不能修改报名方式');
    }
    return this.activityRepository.update(activityId, data);
  }

  /**
   * CR-01 变更：删除改为“软删除（归档）”。
   * 历史报名记录完整保留，学生端不再展示，管理员可恢复。
   */
  delete(activityId) {
    const activity = this.activityRepository.findById(activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    if (activity.isArchived()) return activity;
    this.db.transaction(() => this.activityRepository.setStatus(activityId, 'archived'));
    return this.activityRepository.findById(activityId);
  }

  /** 恢复已归档活动 */
  restore(activityId) {
    const activity = this.activityRepository.findById(activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    if (!activity.isArchived()) return activity;
    this.db.transaction(() => this.activityRepository.setStatus(activityId, 'active'));
    return this.activityRepository.findById(activityId);
  }

  listApprovals() {
    return this.registrationRepository.listPending();
  }

  validate(input) {
    const title = String(input.title || '').trim();
    if (title.length < 1 || title.length > 80) {
      throw new BusinessError('INVALID_TITLE', '活动名称必填，长度 1—80 字');
    }
    const category = String(input.category || '').trim();
    if (category.length < 1 || category.length > 40) {
      throw new BusinessError('INVALID_CATEGORY', '活动分类必填，长度 1—40 字');
    }
    const location = String(input.location || '').trim();
    if (location.length < 1 || location.length > 100) {
      throw new BusinessError('INVALID_LOCATION', '活动地点必填，长度 1—100 字');
    }
    const capacity = Number(input.capacity);
    if (!Number.isInteger(capacity) || capacity < 1 || capacity > 5000) {
      throw new BusinessError('INVALID_CAPACITY', '人数上限必须为 1—5000 的整数');
    }
    const startRaw = String(input.startAt || '').trim();
    const startDate = new Date(startRaw);
    if (!startRaw || Number.isNaN(startDate.getTime())) {
      throw new BusinessError('INVALID_START_AT', '请填写有效的活动开始时间');
    }
    if (startDate.getTime() <= this.now().getTime()) {
      throw new BusinessError('INVALID_START_AT', '活动开始时间必须晚于当前时间');
    }
    const policyType = String(input.policyType || '').trim();
    if (!this.policyFactory.has(policyType)) {
      throw new BusinessError('INVALID_POLICY', '请选择有效的报名方式');
    }
    return {
      title,
      category,
      location,
      capacity,
      policyType,
      startAt: startDate.toISOString(),
    };
  }
}

module.exports = { ActivityService };
