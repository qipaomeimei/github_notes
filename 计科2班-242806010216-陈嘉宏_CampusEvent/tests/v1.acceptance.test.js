'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  BASE_TIME,
  silentLogger,
  HttpClient,
  setupTestContext,
  createActivity,
  loginAs,
  queryParam,
  bodyOf,
} = require('./helpers');
const { createApp } = require('../project/src/app');

test('登录：演示账号可登录，错误密码被拒绝', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const failed = await loginAs(ctx.client, 's1001', 'wrong-password');
  assert.equal(failed.status, 303);
  assert.match(queryParam(failed, 'error'), /账号或密码错误/);

  const ok = await loginAs(ctx.client, 's1001', '123456');
  assert.equal(ok.status, 302);
  assert.match(ctx.client.cookie, /sid=/);

  const page = await ctx.client.get('/');
  assert.equal(page.status, 200);
  assert.match(await bodyOf(page), /校园活动/);
});

test('权限：未登录访问受保护页面重定向登录，学生不能进入管理后台', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const anonymous = await ctx.client.get('/');
  assert.equal(anonymous.status, 302);
  assert.match(anonymous.headers.get('location'), /^\/login/);

  await loginAs(ctx.client, 's1001', '123456');
  const adminPage = await ctx.client.get('/admin');
  assert.equal(adminPage.status, 403);
});

test('C1 管理员可以创建直接报名活动', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  await loginAs(ctx.client, 'admin', 'admin123');
  const response = await ctx.client.post('/admin/activities', {
    title: '新生杯篮球赛',
    category: '体育活动',
    startAt: '2026-12-22T15:30',
    location: '东区篮球场',
    capacity: '20',
    policyType: 'direct',
  });
  assert.equal(response.status, 303);
  assert.match(queryParam(response, 'notice'), /创建成功/);

  const created = ctx.app.repositories.activityRepository
    .listAll()
    .find((item) => item.title === '新生杯篮球赛');
  assert.ok(created);
  assert.equal(created.capacity, 20);
  assert.equal(created.policyType, 'direct');
});

test('C1 活动字段非法时提示错误且不写入脏数据', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  await loginAs(ctx.client, 'admin', 'admin123');
  const before = ctx.app.repositories.activityRepository.listAll().length;
  const response = await ctx.client.post('/admin/activities', {
    title: '',
    category: '讲座',
    startAt: '2026-12-22T15:30',
    location: '报告厅',
    capacity: '0',
    policyType: 'direct',
  });
  assert.equal(response.status, 303);
  assert.match(queryParam(response, 'error'), /活动名称必填/);
  assert.equal(ctx.app.repositories.activityRepository.listAll().length, before);
});

test('C2 学生报名直接报名活动：自动通过并收到站内消息', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C2 直接报名活动', capacity: 2 });
  await loginAs(ctx.client, 's1001', '123456');

  const response = await ctx.client.post(`/activities/${activity.id}/register`, {});
  assert.equal(response.status, 303);
  assert.match(queryParam(response, 'notice'), /直接通过/);

  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);
  assert.equal(registration.status, 'approved');

  const stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 1);
  assert.equal(stats.remaining, 1);

  const messages = ctx.app.repositories.messageRepository.listByStudent('s1001');
  assert.equal(messages.length, 1);
  assert.match(messages[0].content, /报名成功/);
  assert.match(messages[0].content, /C2 直接报名活动/);

  const page = await bodyOf(await ctx.client.get('/messages'));
  assert.match(page, /报名成功/);
});

test('C3 同一活动重复报名被拒绝', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C3 重复报名活动', capacity: 5 });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});

  const second = await ctx.client.post(`/activities/${activity.id}/register`, {});
  assert.equal(second.status, 303);
  assert.match(queryParam(second, 'error'), /不能重复提交/);

  assert.throws(
    () => ctx.app.services.registrationService.register('s1001', activity.id),
    (err) => err.code === 'DUPLICATE_REGISTRATION'
  );
  const total = ctx.app.repositories.registrationRepository.countByActivity(activity.id);
  assert.equal(total, 1);
});

test('C4 名额上限：B 通过，C 因名额不足失败', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C4 容量限制活动', capacity: 2 });
  const studentA = new HttpClient(ctx.base);
  const studentB = new HttpClient(ctx.base);
  const studentC = new HttpClient(ctx.base);
  await loginAs(studentA, 's1001', '123456');
  await loginAs(studentB, 's1002', '123456');
  await loginAs(studentC, 's1003', '123456');

  await studentA.post(`/activities/${activity.id}/register`, {});
  await studentB.post(`/activities/${activity.id}/register`, {});

  const third = await studentC.post(`/activities/${activity.id}/register`, {});
  assert.equal(third.status, 303);
  assert.match(queryParam(third, 'error'), /名额已满/);

  const stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 2);
  assert.equal(stats.remaining, 0);
});

test('C5 审核型活动：提交后状态为待审核', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, {
    title: 'C5 审核型活动',
    capacity: 10,
    policyType: 'approval',
  });
  await loginAs(ctx.client, 's1001', '123456');
  const response = await ctx.client.post(`/activities/${activity.id}/register`, {});
  assert.equal(response.status, 303);

  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);
  assert.equal(registration.status, 'pending');

  const messages = ctx.app.repositories.messageRepository.listByStudent('s1001');
  assert.match(messages[0].content, /待审核/);
});

test('C6 管理员批准待审核报名，状态变为已通过并生成通知', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C6 审批通过活动', capacity: 10, policyType: 'approval' });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});
  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);

  await loginAs(ctx.client, 'admin', 'admin123');
  const approved = await ctx.client.post(`/admin/registrations/${registration.id}/approve`, {});
  assert.equal(approved.status, 303);
  assert.match(queryParam(approved, 'notice'), /已批准/);

  const updated = ctx.app.repositories.registrationRepository.findById(registration.id);
  assert.equal(updated.status, 'approved');
  const messages = ctx.app.repositories.messageRepository.listByStudent('s1001');
  assert.ok(messages.some((message) => message.content.includes('审核通过')));
});

test('C7 管理员拒绝待审核报名，状态变为已拒绝并生成通知', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C7 审批拒绝活动', capacity: 10, policyType: 'approval' });
  await loginAs(ctx.client, 's1002', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});
  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1002', activity.id);

  await loginAs(ctx.client, 'admin', 'admin123');
  await ctx.client.post(`/admin/registrations/${registration.id}/reject`, {});

  const updated = ctx.app.repositories.registrationRepository.findById(registration.id);
  assert.equal(updated.status, 'rejected');
  const messages = ctx.app.repositories.messageRepository.listByStudent('s1002');
  assert.ok(messages.some((message) => message.content.includes('报名未通过')));
});

test('C8 满员时批准失败，人数不超过上限', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C8 批准满员活动', capacity: 1, policyType: 'approval' });

  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});
  const first = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);

  const studentB = new HttpClient(ctx.base);
  await loginAs(studentB, 's1002', '123456');
  await studentB.post(`/activities/${activity.id}/register`, {});
  const second = ctx.app.services.registrationService.findMyActiveRegistration('s1002', activity.id);

  await loginAs(ctx.client, 'admin', 'admin123');
  const ok = await ctx.client.post(`/admin/registrations/${first.id}/approve`, {});
  assert.equal(ok.status, 303);

  const blocked = await ctx.client.post(`/admin/registrations/${second.id}/approve`, {});
  assert.equal(blocked.status, 303);
  assert.match(queryParam(blocked, 'error'), /名额已满/);

  const stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 1);
  assert.equal(stats.pending, 1);
  assert.equal(ctx.app.repositories.registrationRepository.findById(second.id).status, 'pending');
});

test('C9 取消报名后统计同步，允许重新申请', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C9 取消报名活动', capacity: 2 });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});
  const registration = ctx.app.services.registrationService.findMyActiveRegistration('s1001', activity.id);

  const cancelled = await ctx.client.post(`/registrations/${registration.id}/cancel`, {});
  assert.equal(cancelled.status, 303);
  assert.match(queryParam(cancelled, 'notice'), /已取消/);

  const updated = ctx.app.repositories.registrationRepository.findById(registration.id);
  assert.equal(updated.status, 'cancelled');
  let stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 0);
  assert.equal(stats.remaining, 2);

  await ctx.client.post(`/activities/${activity.id}/register`, {});
  stats = ctx.app.services.activityService.getStats(activity.id);
  assert.equal(stats.approved, 1);
});

test('C10 重启服务后活动、报名与通知仍然存在', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: 'C10 持久化活动', capacity: 3 });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});

  await new Promise((resolve) => ctx.server.close(() => resolve()));
  ctx.app.close();

  const reopened = await createApp({
    dbPath: ctx.dbPath,
    seed: false,
    now: () => new Date(BASE_TIME),
    logger: silentLogger,
  });
  t.after(() => reopened.close());

  const saved = reopened.repositories.activityRepository.findById(activity.id);
  assert.ok(saved);
  assert.equal(saved.title, 'C10 持久化活动');
  assert.equal(reopened.repositories.registrationRepository.countByStatus(activity.id, 'approved'), 1);
  assert.equal(reopened.repositories.messageRepository.listByStudent('s1001').length, 1);
});

test('活动开始后不允许新增报名', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const started = ctx.app.repositories.activityRepository.create({
    title: '已开始的活动',
    category: '测试',
    startAt: new Date('2026-11-20T10:00:00+08:00').toISOString(),
    location: '测试地点',
    capacity: 10,
    policyType: 'direct',
    createdAt: new Date(BASE_TIME).toISOString(),
  });

  assert.throws(
    () => ctx.app.services.registrationService.register('s1001', started.id),
    (err) => err.code === 'ACTIVITY_STARTED'
  );
});

test('管理员归档活动（软删除）：保留报名记录，学生端不再展示，可恢复', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: '待归档活动', capacity: 2 });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});

  await loginAs(ctx.client, 'admin', 'admin123');
  const archived = await ctx.client.post(`/admin/activities/${activity.id}/delete`, {});
  assert.equal(archived.status, 303);
  assert.match(queryParam(archived, 'notice'), /已归档/);

  const stored = ctx.app.repositories.activityRepository.findById(activity.id);
  assert.ok(stored);
  assert.equal(stored.status, 'archived');
  assert.equal(ctx.app.repositories.registrationRepository.countByActivity(activity.id), 1);

  const studentList = ctx.app.services.activityService.listForStudents({});
  assert.ok(studentList.every(({ activity: item }) => item.id !== activity.id));
  assert.throws(
    () => ctx.app.services.registrationService.register('s1002', activity.id),
    (err) => err.code === 'ACTIVITY_ARCHIVED'
  );

  const restored = await ctx.client.post(`/admin/activities/${activity.id}/restore`, {});
  assert.equal(restored.status, 303);
  assert.match(queryParam(restored, 'notice'), /已恢复/);
  assert.equal(ctx.app.repositories.activityRepository.findById(activity.id).status, 'active');
});

test('页面展示：活动详情包含容量与剩余名额，我的报名展示状态', async (t) => {
  const ctx = await setupTestContext();
  t.after(() => ctx.cleanup());

  const activity = createActivity(ctx.app, { title: '页面展示活动', capacity: 2 });
  await loginAs(ctx.client, 's1001', '123456');
  await ctx.client.post(`/activities/${activity.id}/register`, {});

  const detail = await bodyOf(await ctx.client.get(`/activities/${activity.id}`));
  assert.match(detail, /页面展示活动/);
  assert.match(detail, /报名统计/);
  assert.match(detail, /已通过/);

  const mine = await bodyOf(await ctx.client.get('/my/registrations'));
  assert.match(mine, /页面展示活动/);
  assert.match(mine, /已通过/);

  const list = await bodyOf(await ctx.client.get('/?q=' + encodeURIComponent('页面展示活动')));
  assert.match(list, /页面展示活动/);
});
