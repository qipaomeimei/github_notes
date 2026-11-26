# 需求变更交付包（change-v2）

《软件工程》实验二 · 计科2班 · 学号 242806010216

本文件夹是**需求变更后的完整代码**与**变更设计分析文档**，对应教师专用材料的 CR-01、CR-02。

---

## 1. 文件夹结构

```
需求变更/
├── README.md                    ← 本文件：变更概述 + 运行说明
├── app/                         ← 变更后完整源码（可直接运行）
│   ├── mock_email.py            ← CR-02 新增：MockEmailSender
│   ├── handlers.py              ← 新增 EmailNotificationHandler
│   ├── domain/policies.py       ← 新增 GradeRestrictedDirectPolicy
│   ├── schema.sql               ← students.grade + email_outbox
│   └── ...（其余同基线）
├── tests/
│   ├── test_acceptance.py       ← 基线 C1—C10 回归
│   ├── test_change_v2.py        ← CR-01/CR-02 变更用例
│   └── test_web.py              ← 页面冒烟
├── wsgi.py
├── requirements.txt
├── pytest.ini
└── 设计文档/
    ├── 01_需求变更设计说明.md    ← 设计选择、类图、时序图、边界情况
    ├── 02_变更影响分析.md        ← 文件级影响、风险、指标
    ├── 03_回归测试报告.md        ← 36 条用例结果
    └── diagrams/
        ├── class_v2.puml / .png / .svg
        └── seq_email_v2.puml / .png / .svg
```

---

## 2. 变更内容

| 变更单 | 内容 | 关键实现 |
| --- | --- | --- |
| **CR-01** | 年级限定直接报名：仅大二（2）、大三（3）可报名，其他年级明确提示 | 新增 `GradeRestrictedDirectPolicy`（策略模式），服务层仅 3 行改动 |
| **CR-02** | 模拟邮件通知：站内消息之外增加邮件，故障不回滚报名，同一事件不重复发送 | 新增 `EmailNotificationHandler` + `MockEmailSender`（观察者模式），服务层 0 改动 |

**原有"直接报名""审核报名"行为完全不变**（基线 13 条用例全部通过）。

---

## 3. 运行方式

### 3.1 本地运行

```powershell
cd 需求变更
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

$env:FLASK_APP = "wsgi"
flask init-db
flask --app wsgi run --host 0.0.0.0 --port 5000
```

浏览器打开 `http://127.0.0.1:5000`。

### 3.2 演示账号

| 角色 | 用户名 | 密码 | 年级 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `admin123` | — |
| 学生 | `s001` | `123456` | 大二（可报年级限定） |
| 学生 | `s002` | `123456` | 大三（可报年级限定） |
| 学生 | `s003` | `123456` | 大一（不可报） |

### 3.3 演示路径（验证两条变更）

1. 用 `s003`（大一）报名"**大二大三实习经验分享会**" → 提示"仅面向大二、大三学生开放"
2. 用 `s001`（大二）报名同一活动 → 报名成功
3. 查看 `instance/campus_event.db` 的 `email_outbox` 表 → 有对应 `sent` 邮件记录（收件人、主题、正文、时间）
4. 取消报名 → `email_outbox` 新增一条"取消"主题邮件

### 3.4 运行测试

```bash
python -m pytest -v
# 期望：36 passed
```

### 3.5 查看邮件 / 故障记录

```bash
python - <<'PY'
import sqlite3
conn = sqlite3.connect("instance/campus_event.db")
conn.row_factory = sqlite3.Row
for row in conn.execute("SELECT * FROM email_outbox ORDER BY outbox_id DESC LIMIT 5"):
    print(dict(row))
PY
```

---

## 4. 云服务器部署

部署方式与项目根目录 `README.md` 第 8 节完全一致（gunicorn + Nginx + systemd，或 waitress）。

**公网访问地址**：`http://<云服务器公网IP>/`（部署后替换为实际地址，不可使用 localhost / 127.0.0.1）

健康检查：`http://<云服务器公网IP>/healthz` → `{"status":"ok"}`

快速启动（Linux）：

```bash
cd 需求变更
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
flask --app wsgi init-db
gunicorn -w 1 --threads 4 -b 127.0.0.1:8000 wsgi:app
```

---

## 5. 与基线版本的关系

| 版本 | 位置 | 说明 |
| --- | --- | --- |
| `baseline-v1` | 项目根目录 Git 标签 `baseline-v1` | 初始验收：两类报名策略 + 站内消息 |
| `change-v2` | 本文件夹 + 项目根目录 Git 标签 `change-v2` | 需求变更：年级限定 + 邮件通知 |

本文件夹是变更后的**独立可运行副本**，便于单独提交与评阅；Git 标签用于对比两版差异。

---

## 6. 文档索引

- [需求变更设计说明](设计文档/01_需求变更设计说明.md) —— 设计选择理由、类图、时序图、边界情况、兼容性
- [变更影响分析](设计文档/02_变更影响分析.md) —— 文件级改动、风险评估、质量指标
- [回归测试报告](设计文档/03_回归测试报告.md) —— 36 条用例明细与失败复盘
