'use strict';

const { BusinessError } = require('../domain/errors');

/** 报名规则抽象：新增报名方式时扩展新实现，而不是修改主流程 */
class RegistrationPolicy {
  get type() {
    throw new Error('RegistrationPolicy.type 未实现');
  }

  get label() {
    throw new Error('RegistrationPolicy.label 未实现');
  }

  get description() {
    throw new Error('RegistrationPolicy.description 未实现');
  }

  /**
   * 决定报名提交后的初始状态。
   * @param {{activity: import('../domain/entities').Activity, approvedCount: number, now: Date}} context
   * @returns {{status: string, note: string}}
   */
  decide(_context) {
    throw new Error('RegistrationPolicy.decide 未实现');
  }
}

/** 直接报名：名额充足即通过 */
class DirectRegistrationPolicy extends RegistrationPolicy {
  get type() {
    return 'direct';
  }

  get label() {
    return '直接报名';
  }

  get description() {
    return '名额充足时报名立即通过，满员后不能再报名';
  }

  decide({ activity, approvedCount }) {
    if (approvedCount >= activity.capacity) {
      throw new BusinessError('CAPACITY_FULL', `活动名额已满（上限 ${activity.capacity} 人），报名失败`);
    }
    return { status: 'approved', note: '名额充足，报名直接通过' };
  }
}

/** 审核报名：提交后进入待审核，由管理员决定 */
class ApprovalRegistrationPolicy extends RegistrationPolicy {
  get type() {
    return 'approval';
  }

  get label() {
    return '审核报名';
  }

  get description() {
    return '提交后进入待审核，管理员批准时才检查并占用名额';
  }

  decide() {
    return { status: 'pending', note: '报名申请已提交，等待管理员审核' };
  }
}

/**
 * 候补报名（CR-01 新增）：
 * 名额充足时立即通过；满员时不直接拒绝，而是进入候补队列。
 * 名额释放后的递补由 RegistrationService 在取消事务内完成。
 */
class WaitlistRegistrationPolicy extends RegistrationPolicy {
  get type() {
    return 'waitlist';
  }

  get label() {
    return '候补报名';
  }

  get description() {
    return '名额充足时立即通过；满员时加入候补队列，名额释放后按顺序自动递补';
  }

  decide({ activity, approvedCount }) {
    if (approvedCount >= activity.capacity) {
      return { status: 'waitlisted', note: '名额已满，已加入候补队列' };
    }
    return { status: 'approved', note: '名额充足，报名直接通过' };
  }
}

/**
 * 策略工厂 / 注册表：
 * RegistrationService 只依赖抽象，具体策略在装配阶段注册。
 */
class PolicyFactory {
  constructor() {
    this.policies = new Map();
  }

  register(policy) {
    this.policies.set(policy.type, policy);
    return this;
  }

  create(type) {
    const policy = this.policies.get(type);
    if (!policy) {
      throw new BusinessError('UNKNOWN_POLICY', '不支持的报名方式');
    }
    return policy;
  }

  has(type) {
    return this.policies.has(type);
  }

  list() {
    return [...this.policies.values()].map((policy) => ({
      type: policy.type,
      label: policy.label,
      description: policy.description,
    }));
  }
}

module.exports = {
  RegistrationPolicy,
  DirectRegistrationPolicy,
  ApprovalRegistrationPolicy,
  WaitlistRegistrationPolicy,
  PolicyFactory,
};
