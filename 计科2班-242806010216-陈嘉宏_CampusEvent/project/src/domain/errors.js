'use strict';

const { PolicyLabel, PolicyDescription, RegistrationStatusLabel } = require('./enums');

/** 业务异常：携带稳定的错误码，供界面层转换为提示信息 */
class BusinessError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'BusinessError';
    this.code = code;
    this.status = 400;
  }
}

/** 需要登录 / 权限不足等访问控制异常 */
class AccessError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'AccessError';
    this.status = status;
  }
}

module.exports = { BusinessError, AccessError };
