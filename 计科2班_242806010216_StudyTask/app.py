"""StudyTask 个人学习任务管理系统（Flask + SQLite）。"""

import os
import re
from datetime import date, datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

import db

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOON_DAYS = 3


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="studytask-local-secret",
        DATABASE=os.path.join(app.instance_path, "studytask.db"),
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_db(app.config["DATABASE"])

    # ---------- 工具函数 ----------

    def days_left(due_date):
        """返回距截止日期的天数（负数为已逾期）。"""
        return (datetime.strptime(due_date, "%Y-%m-%d").date() - date.today()).days

    def decorate(task):
        """给任务补充逾期状态，供模板展示。"""
        left = days_left(task["due_date"])
        if task["status"] == "已完成":
            task["due_state"] = "done"
        elif left < 0:
            task["due_state"] = "overdue"
        elif left <= SOON_DAYS:
            task["due_state"] = "soon"
        else:
            task["due_state"] = "normal"
        task["days_left"] = left
        return task

    def parse_date(value):
        if not DATE_PATTERN.match(value or ""):
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def validate(form):
        """校验表单，返回 (数据, 错误字典)。"""
        data = {
            "title": (form.get("title") or "").strip(),
            "course": (form.get("course") or "").strip(),
            "description": (form.get("description") or "").strip(),
            "due_date": (form.get("due_date") or "").strip(),
            "priority": (form.get("priority") or "中").strip(),
            "status": (form.get("status") or "待完成").strip(),
        }
        errors = {}

        if not data["title"]:
            errors["title"] = "任务名称不能为空"
        elif len(data["title"]) > 100:
            errors["title"] = "任务名称不能超过 100 个字符"

        if not data["course"]:
            errors["course"] = "所属课程不能为空"
        elif len(data["course"]) > 60:
            errors["course"] = "所属课程不能超过 60 个字符"

        if len(data["description"]) > 1000:
            errors["description"] = "任务描述不能超过 1000 个字符"

        if not data["due_date"]:
            errors["due_date"] = "截止日期不能为空"
        elif parse_date(data["due_date"]) is None:
            errors["due_date"] = "截止日期格式应为 YYYY-MM-DD，且必须是真实存在的日期"

        if data["priority"] not in db.PRIORITIES:
            errors["priority"] = "优先级只能是高、中、低"

        if data["status"] not in db.STATUSES:
            errors["status"] = "状态只能是待完成、进行中、已完成"

        return data, errors

    # ---------- 路由 ----------

    @app.route("/")
    def index():
        filters = {
            "course": (request.args.get("course") or "").strip(),
            "status": (request.args.get("status") or "").strip(),
            "priority": (request.args.get("priority") or "").strip(),
        }
        # 非法的筛选值按“不筛选”处理，避免误报为空
        if filters["status"] and filters["status"] not in db.STATUSES:
            filters["status"] = ""
        if filters["priority"] and filters["priority"] not in db.PRIORITIES:
            filters["priority"] = ""

        tasks = [
            decorate(t)
            for t in db.list_tasks(
                app.config["DATABASE"],
                filters["course"],
                filters["status"],
                filters["priority"],
            )
        ]
        return render_template(
            "index.html",
            tasks=tasks,
            filters=filters,
            courses=db.list_courses(app.config["DATABASE"]),
            stats=db.statistics(app.config["DATABASE"]),
            today=date.today().isoformat(),
        )

    @app.route("/tasks/new", methods=["GET", "POST"])
    def new_task():
        if request.method == "POST":
            data, errors = validate(request.form)
            if errors:
                for message in errors.values():
                    flash(message, "error")
                return render_template(
                    "task_form.html", task=data, errors=errors, mode="new"
                ), 400
            task_id = db.create_task(app.config["DATABASE"], data)
            flash("任务创建成功", "success")
            return redirect(url_for("task_detail", task_id=task_id))

        empty = {"priority": "中", "status": "待完成", "title": "", "course": "", "description": "", "due_date": ""}
        return render_template("task_form.html", task=empty, errors={}, mode="new")

    @app.route("/tasks/<int:task_id>")
    def task_detail(task_id):
        task = db.get_task(app.config["DATABASE"], task_id)
        if task is None:
            abort(404)
        return render_template("task_detail.html", task=decorate(task))

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    def edit_task(task_id):
        task = db.get_task(app.config["DATABASE"], task_id)
        if task is None:
            abort(404)

        if request.method == "POST":
            data, errors = validate(request.form)
            if errors:
                for message in errors.values():
                    flash(message, "error")
                return render_template(
                    "task_form.html", task=data, errors=errors, mode="edit", task_id=task_id
                ), 400
            db.update_task(app.config["DATABASE"], task_id, data)
            flash("任务修改成功", "success")
            return redirect(url_for("task_detail", task_id=task_id))

        return render_template(
            "task_form.html", task=task, errors={}, mode="edit", task_id=task_id
        )

    @app.route("/tasks/<int:task_id>/status", methods=["POST"])
    def change_status(task_id):
        task = db.get_task(app.config["DATABASE"], task_id)
        if task is None:
            abort(404)
        status = (request.form.get("status") or "").strip()
        if status not in db.STATUSES:
            flash("非法的任务状态", "error")
            return redirect(url_for("task_detail", task_id=task_id))
        db.update_status(app.config["DATABASE"], task_id, status)
        flash(f"任务状态已更新为“{status}”", "success")
        return redirect(url_for("task_detail", task_id=task_id))

    @app.route("/tasks/<int:task_id>/delete", methods=["GET", "POST"])
    def delete_task(task_id):
        task = db.get_task(app.config["DATABASE"], task_id)
        if task is None:
            abort(404)
        if request.method == "GET":
            # 二次确认：先展示确认页，不执行删除
            return render_template("task_delete.html", task=decorate(task))
        db.delete_task(app.config["DATABASE"], task_id)
        flash(f"任务“{task['title']}”已删除", "success")
        return redirect(url_for("index"))

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
