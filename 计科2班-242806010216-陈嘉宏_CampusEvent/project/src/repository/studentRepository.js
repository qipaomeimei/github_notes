'use strict';

const { Student } = require('../domain/entities');

class StudentRepository {
  constructor(db) {
    this.db = db;
  }

  findById(id) {
    return Student.fromRow(this.db.get('SELECT * FROM students WHERE id = ?', [id]));
  }

  listStudents() {
    return this.db.all("SELECT * FROM students WHERE role = 'student' ORDER BY id ASC").map(Student.fromRow);
  }
}

module.exports = { StudentRepository };
