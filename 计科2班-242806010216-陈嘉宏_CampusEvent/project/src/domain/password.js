'use strict';

const crypto = require('node:crypto');

/** 生成随机盐 */
function createSalt() {
  return crypto.randomBytes(16).toString('hex');
}

/** 口令散列：sha256(salt + password)，演示项目不引入第三方加密库 */
function hashPassword(password, salt) {
  return crypto.createHash('sha256').update(`${salt}:${password}`, 'utf8').digest('hex');
}

function verifyPassword(password, salt, expectedHash) {
  return hashPassword(password, salt) === expectedHash;
}

module.exports = { createSalt, hashPassword, verifyPassword };
