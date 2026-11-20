'use strict';

const { buildEmailSubject, buildEmailBody } = require('./templates');

/**
 * 邮件通知渠道（CR-01 新增）。
 * 作为独立观察者接入，不改动站内消息渠道与报名主流程；
 * 实际不发送外部邮件，而是写入 email_outbox 发件箱供验收查看。
 */
class EmailNotificationChannel {
  constructor({ emailRepository }) {
    this.emailRepository = emailRepository;
    this.name = 'email';
  }

  send(event) {
    this.emailRepository.create({
      studentId: event.studentId,
      eventId: event.id,
      subject: buildEmailSubject(event),
      body: buildEmailBody(event),
      now: event.occurredAt,
    });
  }
}

module.exports = { EmailNotificationChannel };
