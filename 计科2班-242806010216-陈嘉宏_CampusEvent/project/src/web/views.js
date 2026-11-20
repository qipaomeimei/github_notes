'use strict';

const { RegistrationStatusLabel, ActivityStatusLabel } = require('../domain/enums');

function esc(value) {
  return String(value === null || value === undefined ? '' : value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function shanghaiParts(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  });
  const parts = {};
  for (const item of formatter.formatToParts(date)) {
    if (item.type !== 'literal') parts[item.type] = item.value;
  }
  return parts;
}

function fmtDateTime(iso) {
  const p = shanghaiParts(iso);
  return p ? `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}` : '-';
}

function toInputValue(iso) {
  const p = shanghaiParts(iso);
  return p ? `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}` : '';
}

function statusBadge(status) {
  const label = RegistrationStatusLabel[status] || status;
  return `<span class="badge badge-${esc(status)}">${esc(label)}</span>`;
}

function alerts({ notice, error }) {
  const items = [];
  if (notice) items.push(`<div class="alert alert-success">${esc(notice)}</div>`);
  if (error) items.push(`<div class="alert alert-error">${esc(error)}</div>`);
  return items.join('');
}

function layout({ title, user, active = '', unread = 0, notice = '', error = '', body = '' }) {
  const isAdmin = user && user.role === 'admin';
  const navItems = user
    ? [
        { key: 'activities', href: '/', label: '活动列表' },
        { key: 'mine', href: '/my/registrations', label: '我的报名' },
        { key: 'messages', href: '/messages', label: `站内消息${unread > 0 ? ` (${unread})` : ''}` },
        ...(isAdmin
          ? [
              { key: 'admin', href: '/admin', label: '管理后台' },
              { key: 'approvals', href: '/admin/approvals', label: '待审批' },
              { key: 'emails', href: '/admin/emails', label: '邮件通知' },
            ]
          : []),
      ]
    : [];

  const navHtml = navItems
    .map(
      (item) =>
        `<a class="nav-link${active === item.key ? ' active' : ''}" href="${item.href}">${esc(item.label)}</a>`
    )
    .join('');

  const userBox = user
    ? `<div class="user-box">
         <span class="avatar">${esc(user.name.slice(0, 1))}</span>
         <span class="user-name">${esc(user.name)}</span>
         <span class="role-tag">${isAdmin ? '管理员' : '学生'}</span>
         <form method="post" action="/logout" class="inline-form"><button class="btn btn-ghost btn-sm" type="submit">退出</button></form>
       </div>`
    : '';

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${esc(title)} · 校园活动报名与管理系统</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <header class="topbar">
    <div class="wrap topbar-inner">
      <a class="brand" href="/">
        <span class="brand-mark">CE</span>
        <span class="brand-text">校园活动报名与管理系统</span>
      </a>
      <nav class="nav">${navHtml}</nav>
      ${userBox}
    </div>
  </header>
  <main class="wrap main">
    ${alerts({ notice, error })}
    ${body}
  </main>
  <footer class="footer">
    <div class="wrap">软件工程实验二 · CampusEvent · 设计模式驱动的校园活动报名系统</div>
  </footer>
</body>
</html>`;
}

function loginPage({ error = '', redirect = '/', accounts = [] }) {
  const accountHtml = accounts
    .map(
      (item) =>
        `<li><code>${esc(item.id)}</code> / <code>${esc(item.password)}</code> — ${esc(item.name)}</li>`
    )
    .join('');

  return layout({
    title: '登录',
    error,
    body: `<section class="login-wrap">
      <div class="card login-card">
        <h1>登录 CampusEvent</h1>
        <p class="muted">校园活动浏览、报名与审批。请使用演示账号登录。</p>
        <form method="post" action="/login" class="form">
          <input type="hidden" name="redirect" value="${esc(redirect)}" />
          <label class="field">
            <span>账号</span>
            <input name="account" type="text" autocomplete="username" required placeholder="例如 s1001" />
          </label>
          <label class="field">
            <span>密码</span>
            <input name="password" type="password" autocomplete="current-password" required placeholder="请输入密码" />
          </label>
          <button class="btn btn-primary btn-block" type="submit">登录</button>
        </form>
        <div class="demo-accounts">
          <div class="demo-title">演示账号</div>
          <ul>${accountHtml}</ul>
        </div>
      </div>
    </section>`,
  });
}

function activityCard({ activity, stats }) {
  const remaining = stats.remaining;
  return `<article class="card activity-card">
    <div class="activity-head">
      <h3><a href="/activities/${activity.id}">${esc(activity.title)}</a></h3>
      <span class="chip">${esc(activity.category)}</span>
    </div>
    <dl class="meta">
      <div><dt>活动时间</dt><dd>${esc(fmtDateTime(activity.startAt))}</dd></div>
      <div><dt>活动地点</dt><dd>${esc(activity.location)}</dd></div>
      <div><dt>报名方式</dt><dd>${esc(activity.policyLabel)}</dd></div>
    </dl>
    <div class="capacity-bar">
      <div class="capacity-text">
        <span>已通过 <strong>${stats.approved}</strong> / ${activity.capacity}</span>
        <span class="${remaining > 0 ? 'text-ok' : 'text-danger'}">剩余 ${remaining}</span>
      </div>
      <div class="progress"><span style="width:${Math.min(100, Math.round((stats.approved / activity.capacity) * 100))}%"></span></div>
    </div>
    <div class="card-actions">
      <a class="btn btn-ghost" href="/activities/${activity.id}">查看详情</a>
      <form method="post" action="/activities/${activity.id}/register" class="inline-form">
        <button class="btn btn-primary" type="submit">${activity.policyType === 'approval' ? '提交申请' : '立即报名'}</button>
      </form>
    </div>
  </article>`;
}

function activityListPage({ user, unread, items, q = '', type = '', policies = [], notice, error }) {
  const cards = items.length
    ? items.map(activityCard).join('')
    : '<div class="empty">没有符合条件的活动</div>';
  const options = policies
    .map(
      (policy) =>
        `<option value="${esc(policy.type)}"${policy.type === type ? ' selected' : ''}>${esc(policy.label)}</option>`
    )
    .join('');

  return layout({
    title: '活动列表',
    user,
    unread,
    active: 'activities',
    notice,
    error,
    body: `<section class="page-head">
      <div>
        <h1>校园活动</h1>
        <p class="muted">共 ${items.length} 个活动，点击卡片查看详情并报名。</p>
      </div>
      <form class="filter" method="get" action="/">
        <input type="text" name="q" value="${esc(q)}" placeholder="按活动名称筛选" />
        <select name="type">
          <option value="">全部报名方式</option>
          ${options}
        </select>
        <button class="btn btn-ghost" type="submit">筛选</button>
      </form>
    </section>
    <section class="grid">${cards}</section>`,
  });
}

function activityDetailPage({ user, unread, activity, stats, myRegistration, notice, error }) {
  const canRegister = user.role === 'student' && !activity.hasStarted() && !myRegistration;
  let actionHtml = '';
  if (activity.isArchived()) {
    actionHtml = '<p class="text-danger">该活动已归档，报名通道已关闭。</p>';
  } else if (user.role !== 'student') {
    actionHtml = '<p class="muted">管理员账号可前往管理后台维护活动与审批报名。</p>';
  } else if (myRegistration) {
    actionHtml = `<div class="my-state">
        <span>我的报名状态：${statusBadge(myRegistration.status)}</span>
        ${
          myRegistration.status === 'waitlisted'
            ? `<span class="muted">候补序号：第 ${myRegistration.waitlistSeq || '-'} 位</span>`
            : ''
        }
        ${
          myRegistration.canCancel()
            ? `<form method="post" action="/registrations/${myRegistration.id}/cancel" class="inline-form">
                 <button class="btn btn-danger" type="submit">取消报名</button>
               </form>`
            : ''
        }
      </div>`;
  } else if (activity.hasStarted()) {
    actionHtml = '<p class="text-danger">活动已开始，报名通道已关闭。</p>';
  } else if (canRegister) {
    const isFull = stats.remaining <= 0;
    const buttonText =
      activity.policyType === 'approval'
        ? '提交报名申请'
        : activity.policyType === 'waitlist' && isFull
          ? '加入候补队列'
          : '立即报名';
    actionHtml = `<form method="post" action="/activities/${activity.id}/register" class="inline-form">
        <button class="btn btn-primary btn-lg" type="submit">${buttonText}</button>
      </form>`;
  }

  return layout({
    title: activity.title,
    user,
    unread,
    active: 'activities',
    notice,
    error,
    body: `<section class="detail-grid">
      <article class="card detail-card">
        <a class="back" href="/">返回活动列表</a>
        <h1>${esc(activity.title)}</h1>
        <div class="tags"><span class="chip">${esc(activity.category)}</span><span class="chip chip-alt">${esc(activity.policyLabel)}</span></div>
        <dl class="detail-meta">
          <div><dt>活动时间</dt><dd>${esc(fmtDateTime(activity.startAt))}</dd></div>
          <div><dt>活动地点</dt><dd>${esc(activity.location)}</dd></div>
          <div><dt>人数上限</dt><dd>${activity.capacity}</dd></div>
          <div><dt>报名说明</dt><dd>${esc(activity.policyDescription)}</dd></div>
        </dl>
        <div class="action-zone">${actionHtml}</div>
      </article>
      <aside class="card stat-card">
        <h2>报名统计</h2>
        <div class="stat-row"><span>已通过</span><strong>${stats.approved}</strong></div>
        <div class="stat-row"><span>待审核</span><strong>${stats.pending}</strong></div>
        <div class="stat-row"><span>候补中</span><strong>${stats.waitlisted}</strong></div>
        <div class="stat-row"><span>剩余名额</span><strong class="${stats.remaining > 0 ? 'text-ok' : 'text-danger'}">${stats.remaining}</strong></div>
        <div class="stat-row"><span>已拒绝 / 已取消</span><strong>${stats.rejected} / ${stats.cancelled}</strong></div>
      </aside>
    </section>`,
  });
}

function myRegistrationsPage({ user, unread, rows, notice, error }) {
  const body = rows.length
    ? rows
        .map(
          (row) => `<tr>
            <td><a href="/activities/${row.activity_id}">${esc(row.title)}</a></td>
            <td>${esc(fmtDateTime(row.start_at))}</td>
            <td>${esc(row.location)}</td>
            <td>${statusBadge(row.status)}${
              row.status === 'waitlisted' && row.waitlist_seq ? `<span class="muted small"> 第 ${row.waitlist_seq} 位</span>` : ''
            }</td>
            <td>${esc(fmtDateTime(row.created_at))}</td>
            <td>
              ${
                row.status === 'pending' || row.status === 'approved'
                  ? `<form method="post" action="/registrations/${row.id}/cancel" class="inline-form">
                       <button class="btn btn-danger btn-sm" type="submit">取消报名</button>
                     </form>`
                  : '<span class="muted">—</span>'
              }
            </td>
          </tr>`
        )
        .join('')
    : '<tr><td colspan="6" class="empty">还没有报名记录，去活动列表看看吧。</td></tr>';

  return layout({
    title: '我的报名',
    user,
    unread,
    active: 'mine',
    notice,
    error,
    body: `<section class="page-head"><div><h1>我的报名</h1><p class="muted">已取消或已拒绝的历史记录会保留。</p></div></section>
      <div class="card table-card">
        <table class="table">
          <thead><tr><th>活动</th><th>活动时间</th><th>地点</th><th>状态</th><th>提交时间</th><th>操作</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>`,
  });
}

function messagesPage({ user, unread, messages, notice, error }) {
  const list = messages.length
    ? messages
        .map(
          (message) => `<li class="message${message.isRead ? '' : ' unread'}">
            <div class="message-dot"></div>
            <div class="message-body">
              <p>${esc(message.content)}</p>
              <span class="muted">${esc(fmtDateTime(message.createdAt))}</span>
            </div>
          </li>`
        )
        .join('')
    : '<li class="empty">暂无站内消息</li>';

  return layout({
    title: '站内消息',
    user,
    unread,
    active: 'messages',
    notice,
    error,
    body: `<section class="page-head">
      <div><h1>站内消息</h1><p class="muted">报名结果与审核结果都会在这里通知。</p></div>
      <form method="post" action="/messages/read" class="inline-form">
        <button class="btn btn-ghost" type="submit">全部标记已读</button>
      </form>
    </section>
    <ul class="card message-list">${list}</ul>`,
  });
}

function adminDashboardPage({ user, unread, items, notice, error }) {
  const rows = items.length
    ? items
        .map(
          ({ activity, stats }) => `<tr class="${activity.isArchived() ? 'row-archived' : ''}">
            <td><strong>${esc(activity.title)}</strong><div class="muted small">${esc(activity.category)}</div></td>
            <td>${esc(fmtDateTime(activity.startAt))}</td>
            <td>${esc(activity.policyLabel)}</td>
            <td>${activity.capacity}</td>
            <td>${stats.approved}</td>
            <td>${stats.pending}</td>
            <td>${stats.waitlisted}</td>
            <td><span class="badge ${activity.isArchived() ? 'badge-cancelled' : 'badge-approved'}">${esc(ActivityStatusLabel[activity.status] || activity.status)}</span></td>
            <td class="row-actions">
              ${
                activity.isArchived()
                  ? `<form method="post" action="/admin/activities/${activity.id}/restore" class="inline-form">
                       <button class="btn btn-ghost btn-sm" type="submit">恢复</button>
                     </form>`
                  : `<a class="btn btn-ghost btn-sm" href="/admin/activities/${activity.id}/edit">编辑</a>
                     <form method="post" action="/admin/activities/${activity.id}/delete" class="inline-form" onsubmit="return confirm('归档后学生端将不再展示该活动，历史报名记录会保留。确认归档？');">
                       <button class="btn btn-danger btn-sm" type="submit">归档</button>
                     </form>`
              }
            </td>
          </tr>`
        )
        .join('')
    : '<tr><td colspan="9" class="empty">暂无活动，请先创建。</td></tr>';

  return layout({
    title: '管理后台',
    user,
    unread,
    active: 'admin',
    notice,
    error,
    body: `<section class="page-head">
      <div><h1>活动管理</h1><p class="muted">创建、编辑、归档活动，查看报名与候补统计。</p></div>
      <div class="head-actions">
        <a class="btn btn-ghost" href="/admin/approvals">待审批报名</a>
        <a class="btn btn-ghost" href="/admin/emails">邮件通知记录</a>
        <a class="btn btn-primary" href="/admin/activities/new">新建活动</a>
      </div>
    </section>
    <div class="card table-card">
      <table class="table">
        <thead><tr><th>活动</th><th>时间</th><th>报名方式</th><th>容量</th><th>已通过</th><th>待审核</th><th>候补</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`,
  });
}

function emailsPage({ user, unread, emails, notice, error }) {
  const rows = emails.length
    ? emails
        .map(
          (email) => `<tr>
            <td>${esc(email.student_name)}<div class="muted small">${esc(email.student_id)}</div></td>
            <td>${esc(email.subject)}</td>
            <td class="email-body">${esc(email.body)}</td>
            <td>${esc(fmtDateTime(email.created_at))}</td>
          </tr>`
        )
        .join('')
    : '<tr><td colspan="4" class="empty">暂无邮件通知记录</td></tr>';

  return layout({
    title: '邮件通知',
    user,
    unread,
    active: 'emails',
    notice,
    error,
    body: `<section class="page-head"><div><h1>邮件通知记录</h1><p class="muted">CR-01 新增的邮件渠道使用模拟发件箱，便于验收查看通知内容。</p></div></section>
      <div class="card table-card">
        <table class="table">
          <thead><tr><th>收件人</th><th>主题</th><th>正文</th><th>发送时间</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`,
  });
}

function activityFormPage({ user, unread, activity = null, policies, error }) {
  const isEdit = Boolean(activity);
  const value = {
    title: activity ? activity.title : '',
    category: activity ? activity.category : '',
    location: activity ? activity.location : '',
    capacity: activity ? activity.capacity : 30,
    policyType: activity ? activity.policyType : 'direct',
    startAt: activity ? toInputValue(activity.startAt) : '',
  };
  const options = policies
    .map(
      (policy) =>
        `<option value="${esc(policy.type)}"${policy.type === value.policyType ? ' selected' : ''}>${esc(policy.label)} — ${esc(policy.description)}</option>`
    )
    .join('');

  return layout({
    title: isEdit ? '编辑活动' : '新建活动',
    user,
    unread,
    active: 'admin',
    error,
    body: `<section class="page-head"><div><h1>${isEdit ? '编辑活动' : '新建活动'}</h1><p class="muted">容量必须为正整数，活动开始后不能再报名。</p></div></section>
      <form class="card form narrow" method="post" action="${isEdit ? `/admin/activities/${activity.id}/update` : '/admin/activities'}">
        <label class="field"><span>活动名称 *</span>
          <input name="title" type="text" maxlength="80" required value="${esc(value.title)}" />
        </label>
        <label class="field"><span>活动分类 *</span>
          <input name="category" type="text" maxlength="40" required value="${esc(value.category)}" placeholder="如：学术讲座、文艺活动" />
        </label>
        <label class="field"><span>活动开始时间 *</span>
          <input name="startAt" type="datetime-local" required value="${esc(value.startAt)}" />
        </label>
        <label class="field"><span>活动地点 *</span>
          <input name="location" type="text" maxlength="100" required value="${esc(value.location)}" />
        </label>
        <label class="field"><span>人数上限 *</span>
          <input name="capacity" type="number" min="1" max="5000" required value="${esc(value.capacity)}" />
        </label>
        <label class="field"><span>报名方式 *</span>
          <select name="policyType" required>${options}</select>
        </label>
        <div class="form-actions">
          <a class="btn btn-ghost" href="/admin">返回</a>
          <button class="btn btn-primary" type="submit">${isEdit ? '保存修改' : '创建活动'}</button>
        </div>
      </form>`,
  });
}

function approvalsPage({ user, unread, rows, notice, error }) {
  const body = rows.length
    ? rows
        .map(
          (row) => `<tr>
            <td>${esc(row.student_name)}<div class="muted small">${esc(row.student_id)}</div></td>
            <td>${esc(row.title)}</td>
            <td>${esc(fmtDateTime(row.start_at))}</td>
            <td>${esc(fmtDateTime(row.created_at))}</td>
            <td class="row-actions">
              <form method="post" action="/admin/registrations/${row.id}/approve" class="inline-form">
                <button class="btn btn-primary btn-sm" type="submit">批准</button>
              </form>
              <form method="post" action="/admin/registrations/${row.id}/reject" class="inline-form" onsubmit="return confirm('确认拒绝该报名申请吗？');">
                <button class="btn btn-danger btn-sm" type="submit">拒绝</button>
              </form>
            </td>
          </tr>`
        )
        .join('')
    : '<tr><td colspan="5" class="empty">暂无待审核报名</td></tr>';

  return layout({
    title: '待审批',
    user,
    unread,
    active: 'approvals',
    notice,
    error,
    body: `<section class="page-head"><div><h1>待审核报名</h1><p class="muted">批准时会再次检查名额，满员将批准失败。</p></div></section>
      <div class="card table-card">
        <table class="table">
          <thead><tr><th>学生</th><th>活动</th><th>活动时间</th><th>提交时间</th><th>操作</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>`,
  });
}

function errorPage({ user = null, status = 500, message = '服务器内部错误' }) {
  return layout({
    title: '请求失败',
    user,
    body: `<section class="card error-card">
      <h1>${status}</h1>
      <p>${esc(message)}</p>
      <a class="btn btn-primary" href="/">返回首页</a>
    </section>`,
  });
}

module.exports = {
  esc,
  fmtDateTime,
  layout,
  loginPage,
  activityListPage,
  activityDetailPage,
  myRegistrationsPage,
  messagesPage,
  adminDashboardPage,
  emailsPage,
  activityFormPage,
  approvalsPage,
  errorPage,
};
