'use strict';

const { buildInAppMessage } = require('./templates');

/** 站内消息渠道：把报名事件写入消息表 */
class InAppNotificationChannel {
  constructor({ messageRepository }) {
    this.messageRepository = messageRepository;
    this.name = 'in_app';
  }

  send(event) {
    this.messageRepository.create({
      studentId: event.studentId,
      activityId: event.activityId,
      content: buildInAppMessage(event),
      now: event.occurredAt,
    });
  }
}

module.exports = { InAppNotificationChannel };
