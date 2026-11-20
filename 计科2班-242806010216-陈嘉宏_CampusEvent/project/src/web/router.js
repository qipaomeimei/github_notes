'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const views = require('./views');
const { BusinessError, AccessError } = require('../domain/errors');

const PUBLIC_DIR = path.join(__dirname, '..', '..', 'public');
const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

function parseCookies(header = '') {
  const cookies = {};
  for (const part of String(header).split(';')) {
    const index = part.indexOf('=');
    if (index < 0) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    if (key) cookies[key] = decodeURIComponent(value);
  }
  return cookies;
}

function readBody(req, limit = 1_000_000) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > limit) {
        reject(new BusinessError('BODY_TOO_LARGE', '请求内容过大'));
        req.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(Object.fromEntries(new URLSearchParams(data)));
      } catch (_) {
        resolve({});
      }
    });
    req.on('error', reject);
  });
}

function safeLocalPath(value) {
  if (!value || typeof value !== 'string') return null;
  try {
    const url = new URL(value, 'http://localhost');
    return url.pathname.startsWith('/') ? `${url.pathname}${url.search}` : null;
  } catch (_) {
    return null;
  }
}

function withQuery(target, key, value) {
  const url = new URL(target, 'http://localhost');
  url.searchParams.set(key, value);
  return `${url.pathname}?${url.searchParams.toString()}`;
}

class Router {
  constructor({ authService, activityService, registrationService, messageRepository, emailRepository, studentRepository, policyFactory, sessions, sessionTtlMs }) {
    this.authService = authService;
    this.activityService = activityService;
    this.registrationService = registrationService;
    this.messageRepository = messageRepository;
    this.emailRepository = emailRepository;
    this.studentRepository = studentRepository;
    this.policyFactory = policyFactory;
    this.sessions = sessions;
    this.sessionTtlMs = sessionTtlMs;

    this.routes = [];
    this.defineRoutes();
  }

  add(method, pattern, handler, options = {}) {
    const keys = [];
    const regex = new RegExp(
      `^${pattern
        .split('/')
        .map((segment) => {
          if (segment.startsWith(':')) {
            keys.push(segment.slice(1));
            return '([^/]+)';
          }
          return segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        })
        .join('/')}$`
    );
    this.routes.push({ method, regex, keys, handler, ...options });
  }

  defineRoutes() {
    this.add('GET', '/login', (ctx) => this.renderLogin(ctx), { public: true });
    this.add('POST', '/login', (ctx) => this.login(ctx), { public: true });
    this.add('POST', '/logout', (ctx) => this.logout(ctx), { role: 'any' });
    this.add('GET', '/healthz', (ctx) => this.sendJson(ctx.res, { status: 'ok' }), { public: true });

    this.add('GET', '/', (ctx) => this.renderActivities(ctx), { role: 'any' });
    this.add('GET', '/activities/:id', (ctx) => this.renderActivityDetail(ctx), { role: 'any' });
    this.add('POST', '/activities/:id/register', (ctx) => this.register(ctx), { role: 'student' });
    this.add('POST', '/registrations/:id/cancel', (ctx) => this.cancel(ctx), { role: 'student' });

    this.add('GET', '/my/registrations', (ctx) => this.renderMyRegistrations(ctx), { role: 'student' });
    this.add('GET', '/messages', (ctx) => this.renderMessages(ctx), { role: 'any' });
    this.add('POST', '/messages/read', (ctx) => this.markMessagesRead(ctx), { role: 'any' });

    this.add('GET', '/admin', (ctx) => this.renderAdminDashboard(ctx), { role: 'admin' });
    this.add('GET', '/admin/activities/new', (ctx) => this.renderActivityForm(ctx), { role: 'admin' });
    this.add('POST', '/admin/activities', (ctx) => this.createActivity(ctx), { role: 'admin' });
    this.add('GET', '/admin/activities/:id/edit', (ctx) => this.renderActivityForm(ctx), { role: 'admin' });
    this.add('POST', '/admin/activities/:id/update', (ctx) => this.updateActivity(ctx), { role: 'admin' });
    this.add('POST', '/admin/activities/:id/delete', (ctx) => this.deleteActivity(ctx), { role: 'admin' });
    this.add('POST', '/admin/activities/:id/restore', (ctx) => this.restoreActivity(ctx), { role: 'admin' });
    this.add('GET', '/admin/emails', (ctx) => this.renderEmails(ctx), { role: 'admin' });
    this.add('GET', '/admin/approvals', (ctx) => this.renderApprovals(ctx), { role: 'admin' });
    this.add('POST', '/admin/registrations/:id/approve', (ctx) => this.approveRegistration(ctx), { role: 'admin' });
    this.add('POST', '/admin/registrations/:id/reject', (ctx) => this.rejectRegistration(ctx), { role: 'admin' });
  }

  match(method, pathname) {
    for (const route of this.routes) {
      if (route.method !== method) continue;
      const matched = route.regex.exec(pathname);
      if (!matched) continue;
      const params = {};
      route.keys.forEach((key, index) => {
        params[key] = decodeURIComponent(matched[index + 1]);
      });
      return { ...route, params };
    }
    return null;
  }

  currentUser(req) {
    const token = parseCookies(req.headers.cookie).sid;
    if (!token) return null;
    const session = this.sessions.get(token);
    if (!session) return null;
    if (session.expiresAt < Date.now()) {
      this.sessions.delete(token);
      return null;
    }
    return this.studentRepository.findById(session.studentId);
  }

  async handle(req, res) {
    let user = null;
    try {
      const url = new URL(req.url, 'http://localhost');
      if (this.serveStatic(res, url.pathname)) return;

      const method = req.method.toUpperCase();
      const route = this.match(method, url.pathname);
      if (!route) {
        return this.sendHtml(res, views.errorPage({ status: 404, message: '页面不存在' }), 404);
      }

      user = this.currentUser(req);
      if (route.role && !user) {
        if (method === 'GET') {
          const target = `${url.pathname}${url.search}`;
          return this.redirect(res, `/login?redirect=${encodeURIComponent(target)}`);
        }
        return this.redirect(res, '/login');
      }
      if (route.role === 'admin' && (!user || user.role !== 'admin')) {
        return this.sendHtml(res, views.errorPage({ user, status: 403, message: '需要管理员权限' }), 403);
      }
      if (route.role === 'student' && user.role !== 'student') {
        return this.sendHtml(res, views.errorPage({ user, status: 403, message: '管理员账号不参与学生报名' }), 403);
      }

      const body = method === 'POST' ? await readBody(req) : {};
      const ctx = {
        req,
        res,
        url,
        params: route.params,
        query: Object.fromEntries(url.searchParams.entries()),
        body,
        user,
      };
      await route.handler(ctx);
    } catch (err) {
      this.handleError(req, res, err, user);
    }
  }

  handleError(req, res, err, user) {
    const isBusiness = err instanceof BusinessError || err instanceof AccessError;
    const status = err.status || 500;
    if (!isBusiness) console.error('[server] 未处理异常', err);

    const message = isBusiness ? err.message : '服务器内部错误，请稍后重试';
    if (req.method === 'POST') {
      const fallback = safeLocalPath(req.headers.referer) || '/';
      return this.redirect(res, withQuery(fallback, 'error', message), 303);
    }
    return this.sendHtml(res, views.errorPage({ user, status, message }), status);
  }

  // ---------- 页面 ----------

  renderLogin(ctx) {
    const accounts = [
      { id: 's1001', password: '123456', name: '张三（学生）' },
      { id: 's1002', password: '123456', name: '李四（学生）' },
      { id: 'admin', password: 'admin123', name: '系统管理员' },
    ];
    const redirect = safeLocalPath(ctx.query.redirect) || '/';
    this.sendHtml(ctx.res, views.loginPage({ error: ctx.query.error || '', redirect, accounts }));
  }

  login(ctx) {
    const student = this.authService.login(ctx.body.account, ctx.body.password);
    const token = crypto.randomBytes(24).toString('hex');
    this.sessions.set(token, { studentId: student.id, expiresAt: Date.now() + this.sessionTtlMs });
    ctx.res.setHeader(
      'Set-Cookie',
      `sid=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${Math.floor(this.sessionTtlMs / 1000)}`
    );
    const target = safeLocalPath(ctx.body.redirect) || (student.isAdmin() ? '/admin' : '/');
    this.redirect(ctx.res, target);
  }

  logout(ctx) {
    const token = parseCookies(ctx.req.headers.cookie).sid;
    if (token) this.sessions.delete(token);
    ctx.res.setHeader('Set-Cookie', 'sid=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0');
    this.redirect(ctx.res, '/login');
  }

  renderActivities(ctx) {
    const keyword = ctx.query.q || '';
    const policyType = ctx.query.type || '';
    const items = this.activityService.listForStudents({ keyword, policyType });
    this.sendHtml(
      ctx.res,
      views.activityListPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        items,
        q: keyword,
        type: policyType,
        policies: this.policyFactory.list(),
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  renderActivityDetail(ctx) {
    const activityId = Number(ctx.params.id);
    if (!Number.isInteger(activityId)) throw new BusinessError('INVALID_ID', '活动编号无效');
    const activity = this.activityService.getActivity(activityId);
    if (!activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    const stats = this.activityService.getStats(activityId);
    const myRegistration =
      ctx.user.role === 'student'
        ? this.registrationService.findMyActiveRegistration(ctx.user.id, activityId)
        : null;

    this.sendHtml(
      ctx.res,
      views.activityDetailPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        activity,
        stats,
        myRegistration,
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  register(ctx) {
    const activityId = Number(ctx.params.id);
    if (!Number.isInteger(activityId)) throw new BusinessError('INVALID_ID', '活动编号无效');
    const { decision, registration } = this.registrationService.register(ctx.user.id, activityId);
    const label = registration.statusLabel;
    this.redirect(
      ctx.res,
      `/activities/${activityId}?notice=${encodeURIComponent(`${decision.note}（当前状态：${label}）`)}`,
      303
    );
  }

  cancel(ctx) {
    const registrationId = Number(ctx.params.id);
    if (!Number.isInteger(registrationId)) throw new BusinessError('INVALID_ID', '报名编号无效');
    this.registrationService.cancel(registrationId, ctx.user.id);
    this.redirect(ctx.res, `/my/registrations?notice=${encodeURIComponent('已取消报名')}`, 303);
  }

  renderMyRegistrations(ctx) {
    this.sendHtml(
      ctx.res,
      views.myRegistrationsPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        rows: this.registrationService.myRegistrations(ctx.user.id),
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  renderMessages(ctx) {
    this.sendHtml(
      ctx.res,
      views.messagesPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        messages: this.messageRepository.listByStudent(ctx.user.id),
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  markMessagesRead(ctx) {
    this.messageRepository.markAllRead(ctx.user.id);
    this.redirect(ctx.res, '/messages?notice=' + encodeURIComponent('已全部标记为已读'), 303);
  }

  renderAdminDashboard(ctx) {
    this.sendHtml(
      ctx.res,
      views.adminDashboardPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        items: this.activityService.listForAdmin(),
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  renderActivityForm(ctx) {
    const activity = ctx.params.id ? this.activityService.getActivity(Number(ctx.params.id)) : null;
    if (ctx.params.id && !activity) throw new BusinessError('ACTIVITY_NOT_FOUND', '活动不存在');
    this.sendHtml(
      ctx.res,
      views.activityFormPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        activity,
        policies: this.policyFactory.list(),
        error: ctx.query.error || '',
      })
    );
  }

  createActivity(ctx) {
    const activity = this.activityService.create(ctx.body);
    this.redirect(ctx.res, '/admin?notice=' + encodeURIComponent(`活动《${activity.title}》创建成功`), 303);
  }

  updateActivity(ctx) {
    const id = Number(ctx.params.id);
    const activity = this.activityService.update(id, ctx.body);
    this.redirect(ctx.res, '/admin?notice=' + encodeURIComponent(`活动《${activity.title}》已更新`), 303);
  }

  deleteActivity(ctx) {
    const id = Number(ctx.params.id);
    this.activityService.delete(id);
    this.redirect(ctx.res, '/admin?notice=' + encodeURIComponent('活动已归档，历史报名记录已保留'), 303);
  }

  restoreActivity(ctx) {
    const id = Number(ctx.params.id);
    const activity = this.activityService.restore(id);
    this.redirect(ctx.res, '/admin?notice=' + encodeURIComponent(`活动《${activity.title}》已恢复`), 303);
  }

  renderEmails(ctx) {
    this.sendHtml(
      ctx.res,
      views.emailsPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        emails: this.emailRepository.listRecent(),
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  renderApprovals(ctx) {
    this.sendHtml(
      ctx.res,
      views.approvalsPage({
        user: ctx.user,
        unread: this.messageRepository.unreadCount(ctx.user.id),
        rows: this.activityService.listApprovals(),
        notice: ctx.query.notice || '',
        error: ctx.query.error || '',
      })
    );
  }

  approveRegistration(ctx) {
    const id = Number(ctx.params.id);
    this.registrationService.approve(id, ctx.user.id);
    this.redirect(ctx.res, '/admin/approvals?notice=' + encodeURIComponent('已批准该报名'), 303);
  }

  rejectRegistration(ctx) {
    const id = Number(ctx.params.id);
    this.registrationService.reject(id, ctx.user.id);
    this.redirect(ctx.res, '/admin/approvals?notice=' + encodeURIComponent('已拒绝该报名'), 303);
  }

  // ---------- 基础设施 ----------

  serveStatic(res, pathname) {
    if (!pathname.startsWith('/static/')) return false;
    const relative = pathname.slice('/static/'.length);
    const filePath = path.join(PUBLIC_DIR, relative);
    if (!filePath.startsWith(PUBLIC_DIR)) return false;
    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) return false;
    const type = MIME_TYPES[path.extname(filePath)] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Cache-Control': 'public, max-age=300' });
    res.end(fs.readFileSync(filePath));
    return true;
  }

  sendHtml(res, html, status = 200) {
    res.writeHead(status, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(html);
  }

  sendJson(res, data, status = 200) {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
    res.end(JSON.stringify(data));
  }

  redirect(res, location, status = 302) {
    res.writeHead(status, { Location: location, 'Cache-Control': 'no-store' });
    res.end();
  }
}

module.exports = { Router };
