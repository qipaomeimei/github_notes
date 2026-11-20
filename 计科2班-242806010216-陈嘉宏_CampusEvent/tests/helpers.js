'use strict';

const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const { createApp } = require('../project/src/app');

const BASE_TIME = new Date('2026-12-01T01:00:00.000Z'); // 2026-12-01 09:00（东八区）
const silentLogger = { log() {}, warn() {}, error() {} };

class HttpClient {
  constructor(base) {
    this.base = base;
    this.cookie = '';
  }

  async request(method, pathname, options = {}) {
    const headers = { Connection: 'close', ...(options.headers || {}) };
    if (this.cookie) headers.Cookie = this.cookie;
    let body;
    if (options.form) {
      body = new URLSearchParams(options.form).toString();
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    const response = await fetch(`${this.base}${pathname}`, {
      method,
      headers,
      body,
      redirect: 'manual',
    });
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) {
      const matched = /sid=([^;]*)/.exec(setCookie);
      if (matched) this.cookie = `sid=${matched[1]}`;
    }
    return response;
  }

  get(pathname) {
    return this.request('GET', pathname);
  }

  post(pathname, form = {}) {
    return this.request('POST', pathname, { form });
  }
}

async function setupTestContext({ seed = true } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'campus-event-test-'));
  const dbPath = path.join(dir, 'campus_event.sqlite');
  const app = await createApp({
    dbPath,
    seed,
    now: () => new Date(BASE_TIME),
    logger: silentLogger,
  });

  const server = http.createServer((req, res) => app.handle(req, res));
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;

  return {
    app,
    server,
    base,
    dbPath,
    dir,
    client: new HttpClient(base),
    async cleanup() {
      await new Promise((resolve) => server.close(() => resolve()));
      try {
        app.close();
      } catch (_) {
        /* 测试中可能已手动关闭 */
      }
      fs.rmSync(dir, { recursive: true, force: true });
    },
  };
}

let activitySeq = 0;

function createActivity(app, overrides = {}) {
  activitySeq += 1;
  return app.services.activityService.create({
    title: `测试活动${activitySeq}`,
    category: '测试分类',
    location: '测试地点',
    capacity: 2,
    policyType: 'direct',
    startAt: '2026-12-20T10:00',
    ...overrides,
  });
}

async function loginAs(client, account, password = '123456') {
  const response = await client.post('/login', { account, password });
  return response;
}

function locationOf(response) {
  return response.headers.get('location') || '';
}

function queryParam(response, key) {
  const location = locationOf(response);
  const query = new URL(location, 'http://localhost').searchParams;
  return query.get(key) || '';
}

async function bodyOf(response) {
  return response.text();
}

module.exports = {
  BASE_TIME,
  silentLogger,
  HttpClient,
  setupTestContext,
  createActivity,
  loginAs,
  locationOf,
  queryParam,
  bodyOf,
};
