'use strict';

const fs = require('node:fs');
const path = require('node:path');
const initSqlJs = require('../../vendor/sql.js/sql-wasm-inline.js');

const MIGRATIONS_DIR = path.join(__dirname, 'migrations');

/**
 * 对 sql.js（SQLite 的 WebAssembly 版本）的轻量封装。
 * 提供与普通数据库访问层一致的 API：all / get / run / insert / transaction。
 * 每次写事务提交后把数据库镜像写回磁盘文件，实现持久化。
 */
class Database {
  constructor(raw, file) {
    this.raw = raw;
    this.file = file;
  }

  static async open(file) {
    const SQL = await initSqlJs();
    const existed = fs.existsSync(file);
    let raw;
    if (existed) {
      raw = new SQL.Database(new Uint8Array(fs.readFileSync(file)));
    } else {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      raw = new SQL.Database();
    }
    const db = new Database(raw, file);
    db.migrate();
    if (!existed) db.save();
    return db;
  }

  migrate() {
    const row = this.get('PRAGMA user_version');
    const current = Number((row && row.user_version) || 0);
    const files = fs
      .readdirSync(MIGRATIONS_DIR)
      .filter((name) => name.endsWith('.sql'))
      .sort();

    for (const name of files) {
      const version = Number(name.split('_')[0]);
      if (!Number.isFinite(version) || version <= current) continue;
      const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, name), 'utf8');
      this.raw.exec(sql);
      this.raw.run(`PRAGMA user_version = ${version}`);
    }
  }

  all(sql, params = []) {
    const stmt = this.raw.prepare(sql);
    const rows = [];
    try {
      if (params.length > 0) stmt.bind(params);
      while (stmt.step()) rows.push(stmt.getAsObject());
      return rows;
    } finally {
      stmt.free();
    }
  }

  get(sql, params = []) {
    const rows = this.all(sql, params);
    return rows.length > 0 ? rows[0] : null;
  }

  run(sql, params = []) {
    this.raw.run(sql, params);
    return this.raw.getRowsModified();
  }

  insert(sql, params = []) {
    this.run(sql, params);
    const row = this.get('SELECT last_insert_rowid() AS id');
    return Number(row.id);
  }

  /** 在一个事务中执行 fn，提交后立即落盘；失败则回滚。 */
  transaction(fn) {
    this.raw.run('BEGIN');
    try {
      const result = fn();
      this.raw.run('COMMIT');
      this.save();
      return result;
    } catch (err) {
      try {
        this.raw.run('ROLLBACK');
      } catch (_) {
        /* 忽略回滚异常，保留原始错误 */
      }
      throw err;
    }
  }

  save() {
    const dir = path.dirname(this.file);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(this.file, Buffer.from(this.raw.export()));
  }

  close() {
    this.raw.close();
  }
}

module.exports = { Database };
