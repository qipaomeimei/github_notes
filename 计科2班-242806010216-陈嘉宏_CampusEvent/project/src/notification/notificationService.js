'use strict';

/**
 * 通知服务（观察者模式中的 Observer）：
 * - 订阅报名领域事件，按渠道分别投递；
 * - 单渠道失败只留痕，不影响报名事务，也不阻断其他渠道；
 * - 依据 notification_log 的 (event_id, channel) 唯一约束实现幂等，避免重复通知。
 */
class NotificationService {
  constructor({ channels, logRepository, db, logger = console }) {
    this.channels = channels;
    this.logRepository = logRepository;
    this.db = db;
    this.logger = logger;
  }

  subscribeTo(bus, eventTypes) {
    for (const type of eventTypes) {
      bus.subscribe(type, (event) => this.handle(event));
    }
  }

  handle(event) {
    try {
      this.db.transaction(() => this.deliver(event));
    } catch (err) {
      // 通知层彻底失败也必须吞掉异常：报名已经提交成功，不能因通知失败而回滚
      this.logger.error(`[notification] 事件 ${event.id} 处理失败: ${err.message}`);
    }
  }

  deliver(event) {
    for (const channel of this.channels) {
      if (this.logRepository.has(event.id, channel.name)) continue;
      try {
        channel.send(event);
        this.logRepository.record(event.id, channel.name, 'sent');
      } catch (err) {
        this.logRepository.record(event.id, channel.name, 'failed', err.message);
        this.logger.error(`[notification] 渠道 ${channel.name} 投递失败: ${err.message}`);
      }
    }
  }
}

module.exports = { NotificationService };
