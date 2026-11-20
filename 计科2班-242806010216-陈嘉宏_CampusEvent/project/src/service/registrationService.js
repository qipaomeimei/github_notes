'use strict';

const { BusinessError, AccessError } = require('../domain/errors');
const { RegistrationEvent, RegistrationEventType } = require('../events/domainEvents');

/**
 * 报名业务服务：承载“所有报名方式共有”的规则
 * （活动存在/已开始、重复报名、取消权限、审批名额校验），
 * 把“报名后初始状态”的差异交给 RegistrationPolicy 策略。
 */
class RegistrationService {
  constructor({ db, activityRepository, registrationRepository, studentRepository, policyFactory, eventBus, now }) {
    this.db = db;
    this.activityRepository = activityRepository;
    this.registrationRepository = registrationRepository;
    this.studentRepository = studentRepository;
    this.policyFactory = policyFactory;
    this.eventBus = eventBus;
    this.now = now;
  }

  register(studentId, activityId) {
    const student = this.studentRepository.findById(studentId);
    if (!student) throw new BusinessError('STUDENT_NOT_FOUND', '学生不存在');

    const { registration, decision } = this.db.transaction(() => {
      const activity = this.activityRepository.findById(activityId);
      if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
      if (activity.isArchived()) {
        throw new BusinessError('ACTIVITY_ARCHIVED', '活动已归档，不能报名');
      }
      if (activity.hasStarted(this.now())) {
        throw new BusinessError('ACTIVITY_STARTED', '活动已开始，不能再报名');
      }
      if (this.registrationRepository.findActive(activityId, studentId)) {
        throw new BusinessError('DUPLICATE_REGISTRATION', '你已有该活动的有效报名，不能重复提交');
      }

      const approvedCount = this.registrationRepository.countByStatus(activityId, 'approved');
      const policy = this.policyFactory.create(activity.policyType);
      const decision = policy.decide({ activity, approvedCount, now: this.now() });

      const waitlistSeq =
        decision.status === 'waitlisted'
          ? this.registrationRepository.countByStatus(activityId, 'waitlisted') + 1
          : null;

      const created = this.registrationRepository.create({
        activityId,
        studentId,
        status: decision.status,
        waitlistSeq,
        now: this.now().toISOString(),
      });
      return { registration: created, decision, activity };
    });

    const activity = this.activityRepository.findById(activityId);
    this.eventBus.publish(
      new RegistrationEvent(RegistrationEventType.SUBMITTED, {
        registrationId: registration.id,
        activityId,
        activityTitle: activity.title,
        studentId,
        status: registration.status,
        waitlistPosition: registration.waitlistSeq,
        occurredAt: this.now().toISOString(),
      })
    );
    return { registration, decision };
  }

  cancel(registrationId, studentId) {
    const registration = this.registrationRepository.findById(registrationId);
    if (!registration) throw new BusinessError('REGISTRATION_NOT_FOUND', '报名记录不存在');
    if (registration.studentId !== studentId) {
      throw new AccessError(403, '只能取消自己的报名');
    }
    if (!registration.canCancel()) {
      throw new BusinessError('INVALID_STATUS', '当前报名状态不允许取消');
    }
    const activity = this.activityRepository.findById(registration.activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');

    const promoted = this.db.transaction(() => {
      this.registrationRepository.updateStatus(registrationId, 'cancelled');
      if (activity.isArchived()) return [];
      return this.promoteWaitlist(activity);
    });

    this.eventBus.publish(
      new RegistrationEvent(RegistrationEventType.CANCELLED, {
        registrationId,
        activityId: activity.id,
        activityTitle: activity.title,
        studentId,
        status: 'cancelled',
        occurredAt: this.now().toISOString(),
      })
    );

    // 候补递补通知：每个被递补的学生收到“候补成功”消息
    for (const item of promoted) {
      this.eventBus.publish(
        new RegistrationEvent(RegistrationEventType.APPROVED, {
          registrationId: item.id,
          activityId: activity.id,
          activityTitle: activity.title,
          studentId: item.studentId,
          status: 'approved',
          source: 'waitlist-promotion',
          occurredAt: this.now().toISOString(),
        })
      );
    }

    return this.registrationRepository.findById(registrationId);
  }

  /**
   * 名额释放后按候补顺序递补。
   * 必须在调用方的事务内执行，保证“取消 + 递补”原子完成。
   */
  promoteWaitlist(activity) {
    const promoted = [];
    let seats = activity.capacity - this.registrationRepository.countByStatus(activity.id, 'approved');
    while (seats > 0) {
      const head = this.registrationRepository.findWaitlistHead(activity.id);
      if (!head) break;
      this.registrationRepository.updateStatus(head.id, 'approved');
      promoted.push(head);
      seats -= 1;
    }
    return promoted;
  }

  approve(registrationId, adminId) {
    this.assertAdmin(adminId);
    const registration = this.registrationRepository.findById(registrationId);
    if (!registration) throw new BusinessError('REGISTRATION_NOT_FOUND', '报名记录不存在');
    if (registration.status !== 'pending') {
      throw new BusinessError('INVALID_STATUS', '只有待审核的报名可以批准');
    }

    const activity = this.activityRepository.findById(registration.activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    if (activity.isArchived()) {
      throw new BusinessError('ACTIVITY_ARCHIVED', '活动已归档，不能审批报名');
    }

    this.db.transaction(() => {
      const approvedCount = this.registrationRepository.countByStatus(activity.id, 'approved');
      if (approvedCount >= activity.capacity) {
        throw new BusinessError('CAPACITY_FULL', '名额已满，批准失败');
      }
      this.registrationRepository.updateStatus(registrationId, 'approved');
    });

    this.eventBus.publish(
      new RegistrationEvent(RegistrationEventType.APPROVED, {
        registrationId,
        activityId: activity.id,
        activityTitle: activity.title,
        studentId: registration.studentId,
        status: 'approved',
        source: 'admin',
        occurredAt: this.now().toISOString(),
      })
    );
    return this.registrationRepository.findById(registrationId);
  }

  reject(registrationId, adminId) {
    this.assertAdmin(adminId);
    const registration = this.registrationRepository.findById(registrationId);
    if (!registration) throw new BusinessError('REGISTRATION_NOT_FOUND', '报名记录不存在');
    if (registration.status !== 'pending') {
      throw new BusinessError('INVALID_STATUS', '只有待审核的报名可以拒绝');
    }
    const activity = this.activityRepository.findById(registration.activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    if (activity.isArchived()) {
      throw new BusinessError('ACTIVITY_ARCHIVED', '活动已归档，不能审批报名');
    }

    this.db.transaction(() => {
      this.registrationRepository.updateStatus(registrationId, 'rejected');
    });

    this.eventBus.publish(
      new RegistrationEvent(RegistrationEventType.REJECTED, {
        registrationId,
        activityId: activity.id,
        activityTitle: activity.title,
        studentId: registration.studentId,
        status: 'rejected',
        source: 'admin',
        occurredAt: this.now().toISOString(),
      })
    );
    return this.registrationRepository.findById(registrationId);
  }

  myRegistrations(studentId) {
    return this.registrationRepository.listByStudent(studentId);
  }

  findMyActiveRegistration(studentId, activityId) {
    return this.registrationRepository.findActive(activityId, studentId);
  }

  assertAdmin(adminId) {
    const admin = this.studentRepository.findById(adminId);
    if (!admin || !admin.isAdmin()) {
      throw new AccessError(403, '需要管理员权限');
    }
  }
}

module.exports = { RegistrationService };
