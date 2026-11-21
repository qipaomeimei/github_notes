"""CampusEvent 应用工厂。"""
from __future__ import annotations

import hmac
import os

from flask import Flask, abort, jsonify, render_template, request, session

from .db import close_db, init_database, init_db_command, reset_db_command
from .web import register_template_helpers


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", os.path.join(app.instance_path, "campus_event.db")
        ),
        SEED_DEMO=os.environ.get("SEED_DEMO", "1") == "1",
        CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    database_dir = os.path.dirname(os.path.abspath(app.config["DATABASE"]))
    os.makedirs(database_dir, exist_ok=True)

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(reset_db_command)

    from .routes import admin, auth, student

    app.register_blueprint(auth.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(admin.bp)

    register_template_helpers(app)
    _register_csrf(app)
    _register_error_handlers(app)

    @app.route("/healthz")
    def healthz():
        return jsonify(status="ok")

    with app.app_context():
        init_database(seed=app.config.get("SEED_DEMO", True))

    return app


def _register_csrf(app: Flask) -> None:
    @app.before_request
    def _csrf_protect():
        if not app.config.get("CSRF_ENABLED", True):
            return None
        if request.method != "POST":
            return None
        expected = session.get("_csrf_token") or ""
        supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            abort(400, description="表单已过期，请刷新页面后重试。")
        return None


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(error):
        message = getattr(error, "description", "请求无效。")
        return render_template("error.html", code=400, message=message), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", code=403, message="你没有权限访问该页面。"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404, message="页面或活动不存在。"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("error.html", code=500, message="服务器内部错误，请稍后重试。"), 500
