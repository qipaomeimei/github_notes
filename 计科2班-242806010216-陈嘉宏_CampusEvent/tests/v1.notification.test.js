'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { silentLogger, setupTestContext, createActivity } = require('./helpers');
const { NotificationService } = require('../project/src/notification/notificationService');
const { RegistrationEvent, RegistrationEventType } = require('../project/src/events/domainEvents');

test('通知失败不影响报名结果，且失败会留痕', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: '通知失败隔离活动', capacity: 5 });
  const failingChannel = {
    name: 'email_mock',
    send() {
      throw new Error('SMTP 连接超时');
    },
  };
  const extraService = new NotificationService({
    channels: [failingChannel],
    logRepository: ctx.app.repositories.notificationLogRepository,
    db: ctx.app.db,
    logger: silentLogger,
  });
  extraService.subscribeTo(ctx.app.eventBus, [RegistrationEventType.SUBMITTED]);

  const { registration } = await ctx.app.services.registrationService.register('s1001', activity.id);
  assert.equal(registration.status, 'approved');

  const messages = ctx.app.repositories.messageRepository.listByStudent('s1001');
  assert.equal(messages.length, 1, '站内消息渠道应投递成功');

  const failedLogs = ctx.app.db.all("SELECT * FROM notification_log WHERE channel = 'email_mock'");
  assert.equal(failedLogs.length, 1);
  assert.equal(failedLogs[0].status, 'failed');
  assert.match(failedLogs[0].detail, /SMTP/);
});

test('同一事件重复处理不会重复发送站内消息', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: '通知幂等活动', capacity: 5 });
  const event = new RegistrationEvent(RegistrationEventType.SUBMITTED, {
    registrationId: 9999,
    activityId: activity.id,
    activityTitle: activity.title,
    studentId: 's1001',
    status: 'approved',
  });

  ctx.app.notificationService.handle(event);
  ctx.app.notificationService.handle(event);

  const messages = ctx.app.repositories.messageRepository.listByStudent('s1001');
  assert.equal(messages.length, 1);
  // CR-01 起通知有两个渠道：站内消息与邮件发件箱；每个渠道各记录一次
  const logs = ctx.app.repositories.notificationLogRepository.listByEvent(event.id);
  assert.equal(logs.length, 2);
  assert.ok(logs.every((log) => log.status === 'sent'));
  assert.deepEqual(
    logs.map((log) => log.channel).sort(),
    ['email', 'in_app']
  );
  assert.equal(ctx.app.repositories.emailRepository.count(), 1);
});

test('事件订阅者抛出异常不会影响报名事务', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: '订阅者异常活动', capacity: 5 });
  ctx.app.eventBus.subscribe(RegistrationEventType.SUBMITTED, () => {
    throw new Error('订阅者内部错误');
  });

  const { registration } = await ctx.app.services.registrationService.register('s1002', activity.id);
  assert.equal(registration.status, 'approved');
  assert.equal(
    ctx.app.repositories.registrationRepository.countByStatus(activity.id, 'approved'),
    1
  );
});
