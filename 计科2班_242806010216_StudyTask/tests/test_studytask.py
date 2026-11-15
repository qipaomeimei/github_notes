"""StudyTask 自动化验收测试，覆盖实验一 T1—T10 及输入校验。"""

import os
import sys
from datetime import date, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db  # noqa: E402
from app import create_app  # noqa: E402


def make_app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
            "SECRET_KEY": "test",
        }
    )


@pytest.fixture
def app(tmp_path):
    return make_app(tmp_path)


@pytest.fixture
def client(app):
    return app.test_client()


def create_task(client, **overrides):
    data = {
        "title": "完成链表实验报告",
        "course": "数据结构",
        "description": "包括算法分析与测试",
        "due_date": (date.today() + timedelta(days=1)).isoformat(),
        "priority": "高",
        "status": "待完成",
    }
    data.update(overrides)
    return client.post("/tasks/new", data=data, follow_redirects=False)


def test_t1_create_task_appears_in_list(client, app):
    """T1：新建课程/日期/优先级正确的任务后，列表显示该任务。"""
    resp = create_task(client)
    assert resp.status_code == 302

    page = client.get("/").get_data(as_text=True)
    assert "完成链表实验报告" in page
    assert "数据结构" in page

    rows = db.list_tasks(app.config["DATABASE"])
    assert len(rows) == 1
    assert rows[0]["priority"] == "高"
    assert rows[0]["status"] == "待完成"


def test_t2_empty_title_rejected_without_dirty_data(client, app):
    """T2：名称为空提交时提示错误且不产生脏数据。"""
    resp = create_task(client, title="   ")
    assert resp.status_code == 400

    page = resp.get_data(as_text=True)
    assert "任务名称不能为空" in page
    assert db.list_tasks(app.config["DATABASE"]) == []


def test_t3_edit_description_and_priority_persists(client, app):
    """T3：修改描述与优先级后，刷新仍保留。"""
    page_id = int(
        create_task(client).headers["Location"].rstrip("/").split("/")[-1]
    )

    resp = client.post(
        f"/tasks/{page_id}/edit",
        data={
            "title": "完成链表实验报告",
            "course": "数据结构",
            "description": "改为包含单元测试",
            "due_date": (date.today() + timedelta(days=2)).isoformat(),
            "priority": "低",
            "status": "待完成",
        },
    )
    assert resp.status_code == 302

    detail = client.get(f"/tasks/{page_id}").get_data(as_text=True)
    assert "改为包含单元测试" in detail
    assert "优先级：低" in detail

    saved = db.get_task(app.config["DATABASE"], page_id)
    assert saved["description"] == "改为包含单元测试"
    assert saved["priority"] == "低"


def test_t4_status_changes_sequentially_and_persists(client, app):
    """T4：待完成→进行中→已完成，逐次正确更新并持久化。"""
    task_id = int(
        create_task(client).headers["Location"].rstrip("/").split("/")[-1]
    )

    for status in ["进行中", "已完成"]:
        resp = client.post(f"/tasks/{task_id}/status", data={"status": status})
        assert resp.status_code == 302
        assert db.get_task(app.config["DATABASE"], task_id)["status"] == status

    detail = client.get(f"/tasks/{task_id}").get_data(as_text=True)
    assert "状态：已完成" in detail


def test_t5_filters_by_course_status_and_priority(client, app):
    """T5：按课程、状态、优先级及其组合筛选，结果只包含匹配任务。"""
    create_task(client, title="任务A", course="数据结构", priority="高")
    create_task(client, title="任务B", course="数据结构", priority="低")
    create_task(client, title="任务C", course="数据库原理", priority="高")

    b = next(t for t in db.list_tasks(app.config["DATABASE"]) if t["title"] == "任务B")
    client.post(f"/tasks/{b['id']}/status", data={"status": "已完成"})

    page = client.get("/?course=数据结构").get_data(as_text=True)
    assert "任务A" in page and "任务B" in page and "任务C" not in page

    page = client.get("/?status=已完成").get_data(as_text=True)
    assert "任务B" in page and "任务A" not in page and "任务C" not in page

    page = client.get("/?priority=高").get_data(as_text=True)
    assert "任务A" in page and "任务C" in page and "任务B" not in page

    page = client.get("/?course=数据结构&status=待完成&priority=高").get_data(as_text=True)
    assert "任务A" in page
    assert "任务B" not in page and "任务C" not in page


def test_t6_overdue_badge_for_unfinished_task(client, app):
    """T6：昨日到期且未完成的任务显示逾期标识。"""
    task_id = int(
        create_task(
            client, due_date=(date.today() - timedelta(days=1)).isoformat()
        ).headers["Location"].rstrip("/").split("/")[-1]
    )

    page = client.get("/").get_data(as_text=True)
    assert "逾期 1 天" in page

    # 完成后不再显示逾期提醒
    client.post(f"/tasks/{task_id}/status", data={"status": "已完成"})
    page = client.get("/").get_data(as_text=True)
    assert "逾期" not in page


def test_t7_due_soon_badge(client, app):
    """T7：明日到期且未完成的任务显示即将到期标识。"""
    create_task(client, due_date=(date.today() + timedelta(days=1)).isoformat())
    page = client.get("/").get_data(as_text=True)
    assert "即将到期" in page


def test_t8_statistics_five_tasks_two_done(client, app):
    """T8：创建 5 项、完成 2 项，统计为 5 / 2 / 40%。"""
    for i in range(5):
        create_task(client, title=f"统计任务{i}")

    tasks = db.list_tasks(app.config["DATABASE"])
    for task in tasks[:2]:
        client.post(f"/tasks/{task['id']}/status", data={"status": "已完成"})

    stats = db.statistics(app.config["DATABASE"])
    assert stats == {"total": 5, "done": 2, "rate": 40}

    page = client.get("/").get_data(as_text=True)
    assert "40%" in page


def test_t9_delete_requires_confirmation(client, app):
    """T9：取消不删除；确认后删除。"""
    task_id = int(
        create_task(client).headers["Location"].rstrip("/").split("/")[-1]
    )

    confirm_page = client.get(f"/tasks/{task_id}/delete").get_data(as_text=True)
    assert "确认删除任务" in confirm_page
    assert db.get_task(app.config["DATABASE"], task_id) is not None

    resp = client.post(f"/tasks/{task_id}/delete")
    assert resp.status_code == 302
    assert db.get_task(app.config["DATABASE"], task_id) is None


def test_t10_data_persists_after_restart(tmp_path):
    """T10：关闭并重新启动应用后，已保存数据仍可查询。"""
    app1 = make_app(tmp_path)
    client1 = app1.test_client()
    create_task(client1, title="重启后仍应存在")

    app2 = make_app(tmp_path)
    page = app2.test_client().get("/").get_data(as_text=True)
    assert "重启后仍应存在" in page


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"course": ""}, "所属课程不能为空"),
        ({"due_date": ""}, "截止日期不能为空"),
        ({"due_date": "2026-02-30"}, "截止日期格式应为"),
        ({"due_date": "2026/11/20"}, "截止日期格式应为"),
        ({"title": "长" * 101}, "任务名称不能超过"),
        ({"course": "课" * 61}, "所属课程不能超过"),
        ({"description": "字" * 1001}, "任务描述不能超过"),
        ({"priority": "紧急"}, "优先级只能是"),
        ({"status": "搁置"}, "状态只能是"),
    ],
)
def test_invalid_input_rejected(client, app, overrides, message):
    """非法输入被拒绝且不落库。"""
    resp = create_task(client, **overrides)
    assert resp.status_code == 400
    assert message in resp.get_data(as_text=True)
    assert db.list_tasks(app.config["DATABASE"]) == []


def test_unknown_task_returns_404(client):
    """访问不存在的任务返回 404 页面，应用不崩溃。"""
    resp = client.get("/tasks/9999")
    assert resp.status_code == 404
    assert "页面或任务不存在" in resp.get_data(as_text=True)


def test_empty_statistics_show_zero(client):
    """没有任何任务时，总数为 0 且完成率为 0%。"""
    page = client.get("/").get_data(as_text=True)
    assert "0%" in page
