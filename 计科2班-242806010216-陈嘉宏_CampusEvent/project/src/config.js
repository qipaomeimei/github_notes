'use strict';

const os = require('node:os');
const path = require('node:path');

/**
 * 运行期配置。
 * - 数据目录默认位于系统临时目录：本地重启后数据仍在，且符合云平台“仅允许写临时目录”的约束。
 * - 可通过 CAMPUS_DATA_DIR / CAMPUS_DB_PATH 覆盖，便于本地把数据放到仓库外或指定目录。
 */
const DATA_DIR = process.env.CAMPUS_DATA_DIR || path.join(os.tmpdir(), 'campus-event-data');
const DB_FILE = process.env.CAMPUS_DB_PATH || path.join(DATA_DIR, 'campus_event.sqlite');

module.exports = {
  DATA_DIR,
  DB_FILE,
  PORT: Number(process.env.PORT || 8000),
  HOST: process.env.HOST || '0.0.0.0',
  SESSION_TTL_MS: 8 * 60 * 60 * 1000,
};
