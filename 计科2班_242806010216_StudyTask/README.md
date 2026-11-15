# StudyTask 个人学习任务管理系统

《软件工程》实验一项目：AI 驱动的个人学习任务管理系统。单用户、本地运行，用于记录课程作业、实验与考试准备等学习任务，支持任务的增删改查、状态流转、组合筛选、逾期提醒和完成率统计。

- 班级/学号/姓名：计科 2 班 / 242806010216 / 陈嘉宏
- 技术栈：Python 3.11+ / Flask 3.1 / SQLite
- 数据库文件：`instance/studytask.db`（首次启动自动创建，无需手工初始化）

## 功能清单

| 编号 | 功能 | 说明 |
| --- | --- | --- |
| P1-F01 | 新建任务 | 任务名称、课程、描述、截止日期、优先级；必填项与长度校验 |
| P1-F02 | 查看 / 编辑 / 删除 | 列表、详情页、编辑页；删除需在确认页二次确认 |
| P1-F03 | 任务状态 | 待完成 / 进行中 / 已完成，修改后立即持久化 |
| P1-F04 | 组合筛选 | 按课程、状态、优先级任意组合筛选 |
| P1-F05 | 逾期与即将到期 | 未完成且已过截止日期显示“逾期 N 天”；未来 3 天内到期显示“即将到期” |
| P1-F06 | 统计 | 首页显示任务总数、已完成数、完成率（无任务时完成率为 0%） |
| P1-F07 | 持久化 | 数据保存在 SQLite，重启服务后仍可查询 |

## 快速开始（从零运行）

### 1. 准备环境

需要 Python 3.11 或更高版本（开发验证环境为 Python 3.14.3）。

```powershell
# 进入项目目录
cd 计科2班_242806010216_StudyTask

# 创建并激活虚拟环境（Windows PowerShell）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 启动系统

```powershell
python app.py
```

浏览器打开 <http://127.0.0.1:5000>。首次启动会自动创建 `instance/studytask.db` 并建表，不需要额外初始化脚本。

### 4. 运行自动化测试

```powershell
python -m pytest
```

预期结果：`21 passed`。测试使用临时数据库，不会影响 `instance/studytask.db` 中的实际数据。

## 项目结构

```
计科2班_242806010216_StudyTask/
├── app.py                  # Flask 应用：路由、表单校验、逾期计算
├── db.py                   # SQLite 数据访问层（建表、增删改查、统计）
├── templates/              # Jinja2 模板（列表、表单、详情、删除确认、404）
├── static/style.css        # 页面样式
├── tests/test_studytask.py # pytest 验收测试（覆盖 T1—T10 与输入校验）
├── docs/                   # 测试记录、实验报告、演示 PPT、运行截图
├── AI_DEV_LOG.md           # AI 协作过程记录
├── requirements.txt
├── pytest.ini
└── README.md
```

## 主要页面

| 路径 | 说明 |
| --- | --- |
| `GET /` | 任务列表、统计、组合筛选 |
| `GET/POST /tasks/new` | 新建任务 |
| `GET /tasks/<id>` | 任务详情与状态切换 |
| `GET/POST /tasks/<id>/edit` | 编辑任务 |
| `POST /tasks/<id>/status` | 更新任务状态 |
| `GET /tasks/<id>/delete` | 删除确认页（不删除数据） |
| `POST /tasks/<id>/delete` | 确认后删除 |

## 关键实现说明

- **输入校验在服务端完成**：任务名称 1—100 字、课程 1—60 字、描述不超过 1000 字、截止日期必须为 `YYYY-MM-DD` 格式的真实日期；非法优先级/状态一律拒绝，校验失败不会写入数据库。
- **逾期规则**：已完成任务不显示逾期或即将到期标识；未完成任务按“截止日期 − 今天”的差值判断（小于 0 为逾期，0—3 天为即将到期）。
- **统计口径**：首页三项统计始终针对全部任务，不受筛选条件影响；筛选只影响列表展示。
- **删除确认**：列表和详情页的“删除”只打开确认页，只有提交确认表单才会执行 `DELETE`。

## 已知限制

- 按实验一需求范围为单用户本地系统，不含注册登录、多用户协作、邮件/短信提醒和移动端。
- 使用 Flask 内置开发服务器，仅适合本机演示，未配置生产级 WSGI 服务。
- 未实现 CSRF Token（单用户本地场景），如需公网部署应先补充。
- 实验一按附录 A.5 不要求云部署；如需部署，可将 `app.run()` 改为 WSGI 服务并设置反向代理。

## 提交材料

- 源代码、`requirements.txt`、`README.md`
- `tests/` 自动化测试与 `docs/测试记录.md` 需求验收表（T1—T10）
- `AI_DEV_LOG.md` AI 协作记录
- `docs/实验一报告.docx` 实验报告（不超过 4 页）
- `docs/演示PPT.pptx` 演示文稿
- `docs/screenshots/` 关键运行截图
