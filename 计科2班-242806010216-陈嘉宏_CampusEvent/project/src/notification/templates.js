'use strict';

const { RegistrationEventType } = require('../events/domainEvents');

/** 站内消息文案：由事件类型、报名状态与事件来源决定 */
function buildInAppMessage(event) {
  const title = event.activityTitle;
  switch (event.type) {
    case RegistrationEventType.SUBMITTED:
      if (event.status === 'waitlisted') {
        return `活动《${title}》名额已满，你已加入候补队列（第 ${event.waitlistPosition} 位），有名额释放时将按顺序自动递补。`;
      }
      return event.status === 'approved'
        ? `报名成功：《${title}》，当前状态为“已通过”。`
        : `报名申请已提交：《${title}》，当前状态为“待审核”。`;
    case RegistrationEventType.APPROVED:
      if (event.source === 'waitlist-promotion') {
        return `候补递补成功：《${title}》名额已释放，你的报名状态为“已通过”。`;
      }
      return event.source === 'admin'
        ? `报名审核通过：《${title}》，当前状态为“已通过”。`
        : `报名成功：《${title}》，当前状态为“已通过”。`;
    case RegistrationEventType.REJECTED:
      return `报名未通过：《${title}》，如有疑问请联系活动管理员。`;
    case RegistrationEventType.CANCELLED:
      return `已取消报名：《${title}》。`;
    default:
      return `活动《${title}》的报名状态已更新。`;
  }
}

function buildEmailSubject(event) {
  return `【CampusEvent】${event.activityTitle} 报名状态通知`;
}

function buildEmailBody(event) {
  return `同学你好：\n\n${buildInAppMessage(event)}\n\n——校园活动报名与管理系统`;
}

module.exports = { buildInAppMessage, buildEmailSubject, buildEmailBody };
