'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  HttpClient,
  setupTestContext,
  createActivity,
  loginAs,
  queryParam,
  bodyOf,
} = require('./helpers');

test('CR-01 候补报名：满员后进入候补队列，站内消息与邮件双渠道通知', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, {
    title: '候补容量活动',
    capacity: 1,
    policyType: 'waitlist',
  });

  const first = new HttpClient(ctx.base);
  const second = new HttpClient(ctx.base);
  await loginAs(first, 's1001', '123456');
  await loginAs(second, 's1002', '123456');

  const approved = await first.post(`/activities/${activity.id}/register`, {});
  assert.match(queryParam(approved, 'notice'), /直接通过/);

  const waitlisted = await second.post(`/activities/${activity.id}/register`, {});
  assert.equal(waitlisted.status, 303);
  assert.match(queryParam(waitlisted, 'notice'), /候补队列/);

  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1002', activity.id);
  assert.equal(registration.status, 'waitlisted');
  assert.equal(registration.waitlistSeq, 1);

  const stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 1);
  assert.equal(stats.waitlisted, 1);

  const messages = ctx.app.repositories.messageRepository.listByStudent('s1002');
  assert.ok(messages.some((message) => /候补队列/.test(message.content)));

  const emails = ctx.app.repositories.emailRepository.listRecent();
  assert.ok(emails.some((email) => email.student_id === 's1002' && /候补队列/.test(email.body)));

  const page = await bodyOf(await second.get('/my/registrations'));
  assert.match(page, /候补中/);
});

test('CR-01 名额释放后按候补顺序自动递补，并发送递补通知', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, {
    title: '候补递补活动',
    capacity: 1,
    policyType: 'waitlist',
  });

  const first = new HttpClient(ctx.base);
  const second = new HttpClient(ctx.base);
  const third = new HttpClient(ctx.base);
  await loginAs(first, 's1001', '123456');
  await loginAs(second, 's1002', '123456');
  await loginAs(third, 's1003', '123456');

  await first.post(`/activities/${activity.id}/register`, {});
  await second.post(`/activities/${activity.id}/register`, {});
  await third.post(`/activities/${activity.id}/register`, {});

  assert.equal(ctx.app.services.registrationService.findMyActiveRegistration('s1002', activity.id).waitlistSeq, 1);
  assert.equal(ctx.app.services.registrationService.findMyActiveRegistration('s1003', activity.id).waitlistSeq, 2);

  const seatHolder = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);
  const cancelled = await first.post(`/registrations/${seatHolder.id}/cancel`, {});
  assert.match(queryParam(cancelled, 'notice'), /已取消/);

  const promoted = ctx.app.repositories.registrationRepository.findById(
    ctx.app.services.registrationService.findMyActiveRegistration('s1002', activity.id).id
  );
  assert.equal(promoted.status, 'approved');

  const stillWaiting = ctx.app.services.registrationService.findMyActiveRegistration('s1003', activity.id);
  assert.equal(stillWaiting.status, 'waitlisted');

  const stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 1);
  assert.equal(stats.waitlisted, 1);
  assert.equal(stats.cancelled, 1);

  const messages = ctx.app.repositories.messageRepository.listByStudent('s1002');
  assert.ok(messages.some((message) => /递补成功/.test(message.content)));

  const emails = ctx.app.repositories.emailRepository.listRecent();
  assert.ok(emails.some((email) => email.student_id === 's1002' && /递补成功/.test(email.body)));
});

test('CR-01 邮件渠道为模拟发件箱：同一事件写入一次，管理员可在页面查看', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: '邮件通知活动', capacity: 5 });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});

  const before = ctx.app.repositories.emailRepository.count();
  assert.equal(before, 1);

  // 重复提交通知事件不会重复写发件箱（业务层重复报名已被拒绝）
  const duplicated = await ctx.client.post(`/activities/${activity.id}/register`, {});
  assert.match(queryParam(duplicated, 'error'), /不能重复提交/);
  assert.equal(ctx.app.repositories.emailRepository.count(), 1);

  const studentPage = await ctx.client.get('/admin/emails');
  assert.equal(studentPage.status, 403);

  await loginAs(ctx.client, 'admin', 'admin123');
  const page = await ctx.client.get('/admin/emails');
  assert.equal(page.status, 200);
  const html = await bodyOf(page);
  assert.match(html, /邮件通知记录/);
  assert.match(html, /邮件通知活动/);
});

test('CR-01 归档活动：学生端隐藏，且不能报名或审批', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, {
    title: '归档审批活动',
    capacity: 5,
    policyType: 'approval',
  });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});
  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);

  await loginAs(ctx.client, 'admin', 'admin123');
  await ctx.client.post(`/admin/activities/${activity.id}/delete`, {});

  const blocked = await ctx.client.post(`/admin/registrations/${registration.id}/approve`, {});
  assert.equal(blocked.status, 303);
  assert.match(queryParam(blocked, 'error'), /已归档/);

  const detail = await ctx.client.get(`/activities/${activity.id}`);
  const html = await bodyOf(detail);
  assert.match(html, /已归档/);
});
