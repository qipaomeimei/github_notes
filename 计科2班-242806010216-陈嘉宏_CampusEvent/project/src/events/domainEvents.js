'use strict';

/** 领域事件基类：id 由“报名记录 + 事件类型”构成，便于通知幂等 */
class RegistrationEvent {
  constructor(type, payload) {
    this.type = type;
    this.id = `${payload.registrationId}:${type}`;
    this.registrationId = payload.registrationId;
    this.activityId = payload.activityId;
    this.activityTitle = payload.activityTitle;
    this.studentId = payload.studentId;
    this.status = payload.status;
    this.source = payload.source || 'system';
    this.occurredAt = payload.occurredAt || new Date().toISOString();
  }
}

const RegistrationEventType = Object.freeze({
  SUBMITTED: 'registration.submitted',
  APPROVED: 'registration.approved',
  REJECTED: 'registration.rejected',
  CANCELLED: 'registration.cancelled',
});

/**
 * 同步事件总线（观察者模式的 Subject）。
 * 订阅者异常不会向上抛出，保证报名事务不因通知失败而失败。
 */
class DomainEventBus {
  constructor(logger = console) {
    this.handlers = new Map();
    this.logger = logger;
  }

  subscribe(eventType, handler) {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, []);
    this.handlers.get(eventType).push(handler);
    return this;
  }

  publish(event) {
    const handlers = this.handlers.get(event.type) || [];
    for (const handler of handlers) {
      try {
        handler(event);
      } catch (err) {
        this.logger.error(`[event] 处理 ${event.type} 失败: ${err.message}`);
      }
    }
  }
}

module.exports = { RegistrationEvent, RegistrationEventType, DomainEventBus };
