'use strict';

const { Database } = require('./db/database');
const { seedDatabase } = require('./db/seed');
const { StudentRepository } = require('./repository/studentRepository');
const { ActivityRepository } = require('./repository/activityRepository');
const { RegistrationRepository } = require('./repository/registrationRepository');
const { MessageRepository } = require('./repository/messageRepository');
const { NotificationLogRepository } = require('./repository/notificationLogRepository');
const { EmailRepository } = require('./repository/emailRepository');
const {
  PolicyFactory,
  DirectRegistrationPolicy,
  ApprovalRegistrationPolicy,
  WaitlistRegistrationPolicy,
} = require('./policy/registrationPolicy');
const { DomainEventBus, RegistrationEventType } = require('./events/domainEvents');
const { NotificationService } = require('./notification/notificationService');
const { InAppNotificationChannel } = require('./notification/inAppNotificationChannel');
const { EmailNotificationChannel } = require('./notification/emailNotificationChannel');
const { AuthService } = require('./service/authService');
const { ActivityService } = require('./service/activityService');
const { RegistrationService } = require('./service/registrationService');
const { Router } = require('./web/router');

/**
 * 应用装配根：负责创建数据库、仓储、策略、事件总线、通知服务与路由。
 * 所有依赖显式注入，便于测试时替换数据库路径与时钟。
 */
async function createApp({ dbPath, seed = true, now = () => new Date(), logger = console } = {}) {
  const db = await Database.open(dbPath);
  if (seed) seedDatabase(db, now);

  const studentRepository = new StudentRepository(db);
  const activityRepository = new ActivityRepository(db);
  const registrationRepository = new RegistrationRepository(db);
  const messageRepository = new MessageRepository(db);
  const notificationLogRepository = new NotificationLogRepository(db);
  const emailRepository = new EmailRepository(db);

  // 策略注册表：CR-01 注册“候补报名”，其余策略与主流程保持不变
  const policyFactory = new PolicyFactory()
    .register(new DirectRegistrationPolicy())
    .register(new ApprovalRegistrationPolicy())
    .register(new WaitlistRegistrationPolicy());

  const eventBus = new DomainEventBus(logger);
  const notificationService = new NotificationService({
    channels: [
      new InAppNotificationChannel({ messageRepository }),
      new EmailNotificationChannel({ emailRepository }),
    ],
    logRepository: notificationLogRepository,
    db,
    logger,
  });
  notificationService.subscribeTo(eventBus, Object.values(RegistrationEventType));

  const activityService = new ActivityService({
    db,
    activityRepository,
    registrationRepository,
    policyFactory,
    now,
  });
  const registrationService = new RegistrationService({
    db,
    activityRepository,
    registrationRepository,
    studentRepository,
    policyFactory,
    eventBus,
    now,
  });
  const authService = new AuthService({ studentRepository });

  const sessions = new Map();
  const router = new Router({
    authService,
    activityService,
    registrationService,
    messageRepository,
    emailRepository,
    studentRepository,
    policyFactory,
    sessions,
    sessionTtlMs: 8 * 60 * 60 * 1000,
  });

  return {
    db,
    repositories: {
      studentRepository,
      activityRepository,
      registrationRepository,
      messageRepository,
      notificationLogRepository,
      emailRepository,
    },
    services: { authService, activityService, registrationService },
    policyFactory,
    eventBus,
    notificationService,
    sessions,
    handle: (req, res) => router.handle(req, res),
    close: () => db.close(),
  };
}

module.exports = { createApp };
