'use strict';

const { BusinessError } = require('../domain/errors');
const { verifyPassword } = require('../domain/password');

class AuthService {
  constructor({ studentRepository }) {
    this.studentRepository = studentRepository;
  }

  login(account, password) {
    const student = this.studentRepository.findById(String(account || '').trim());
    if (!student || !verifyPassword(String(password || ''), student.passwordSalt, student.passwordHash)) {
      throw new BusinessError('LOGIN_FAILED', '账号或密码错误');
    }
    return student;
  }
}

module.exports = { AuthService };
