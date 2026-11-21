# CampusEvent 校园活动报名与管理系统

《软件工程》实验二 · 计科2班 · 学号 242806010216

基于 **Python + Flask + SQLite** 的校园活动发布、报名、审核与通知系统。初始版本包含两类报名规则（直接报名、管理员审核），变更版本新增**候补报名与自动递补**、**模拟邮件通知**，采用策略模式与观察者/事件总线实现可扩展设计。

## 1. 公网访问地址

> **部署后必须填写云服务器公网地址（不能使用 localhost / 127.0.0.1）：**

**公网访问地址：** `http://<云服务器公网IP>/`（部署完成后替换为实际地址）

示例：`http://123.45.67.89/`

健康检查：`http://<云服务器公网IP>/healthz` 应返回 `{"status":"ok"}`。

> 教师验收时请从公网网络访问上述地址；`http://127.0.0.1:5000` 仅用于本机开发，不作为提交地址。

## 2. 演示账号

| 角色 | 用户名 | 密码 | 说明 |
| --- | --- | --- | --- |
| 管理员 | `admin` | `admin123` | 创建/编辑/下架活动、审批报名 |
| 学生 | `s001` | `123456` | 张三 |
| 学生 | `s002` | `123456` | 李四 |
| 学生 | `s003` | `123456` | 王五 |

> 公网部署属于演示环境。如需长期开放，请在首次登录后修改演示密码或限制访问来源。

## 3. 技术栈

- Python 3.11+（开发环境 3.14 已验证）
- Flask 3.x
- SQLite（标准库 `sqlite3`，无 ORM）
- Jinja2 模板 + 原生 CSS
- pytest 自动化测试
- 生产部署：gunicorn（Linux）/ waitress（Windows）+ Nginx 反向代理

## 4. 功能清单

| 编号 | 功能 | 状态 |
| --- | --- | --- |
| P2-F01 | 管理员创建、编辑、下架活动 | 已实现 |
| P2-F02 | 学生浏览活动列表/详情，按名称搜索 | 已实现 |
| P2-F03 | 学生报名、取消，禁止重复有效报名 | 已实现 |
| P2-F04 | 直接报名自动通过；审核型进入待审核 | 已实现 |
| P2-F05 | 管理员批准/拒绝，批准时复查名额 | 已实现 |
| P2-F06 | 待审核/已通过/已拒绝/已取消状态管理 | 已实现 |
| P2-F07 | 报名与审核结果写入站内消息 | 已实现 |
| P2-F08 | 已通过数、待审核数、剩余名额统计 | 已实现 |
| CR-01 | 候补报名：满员进入候补，取消后按顺序自动递补 | change-v2 |
| CR-02 | 模拟邮件通知：事件写入 `email_outbox`，邮箱为空自动跳过 | change-v2 |

## 5. 目录结构

```
计科2班_242806010216_CampusEvent/
├── app/
│   ├── __init__.py          # 应用工厂、CSRF、错误处理
│   ├── schema.sql           # SQLite 表结构
│   ├── db.py                # 连接、建库、演示数据
│   ├── auth.py              # 登录与角色校验
│   ├── web.py               # 模板过滤器与全局变量
│   ├── repositories.py      # 仓储层（全部 SQL）
│   ├── services.py          # 活动服务、报名服务（事务边界）
│   ├── handlers.py          # 站内消息 / 模拟邮件订阅者
│   ├── notifications.py     # 事件总线装配（注册全部订阅者）
│   ├── domain/
│   │   ├── models.py        # 领域模型与状态
│   │   ├── policies.py      # 策略模式：报名规则
│   │   └── events.py        # 观察者/事件总线
│   ├── routes/              # 登录、学生端、管理员端路由
│   ├── templates/           # Jinja2 页面
│   └── static/style.css
├── tests/                   # pytest：C1—C19 与 HTTP 验收
├── docs/                    # 设计材料与报告
│   └── diagrams/            # PlantUML 源文件与导出图
├── wsgi.py                  # WSGI 入口
├── requirements.txt
├── pytest.ini
├── AI_DEV_LOG.md
└── README.md
```

## 6. 本地运行（从零开始）

### 6.1 Windows PowerShell

```powershell
cd 计科2班_242806010216_CampusEvent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 可选：显式初始化数据库（首次启动也会自动建库并写入演示数据）
$env:FLASK_APP = "wsgi"
flask init-db

# 开发模式启动
$env:FLASK_DEBUG = "1"
flask --app wsgi run --host 0.0.0.0 --port 5000
```

浏览器打开 `http://127.0.0.1:5000`。

### 6.2 Linux / macOS

```bash
cd 计科2班_242806010216_CampusEvent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=wsgi
flask init-db
flask --app wsgi run --host 0.0.0.0 --port 5000
```

### 6.3 数据库说明

- 默认路径：`instance/campus_event.db`，首次启动自动建表并写入演示数据；
- 可通过环境变量 `DATABASE_PATH` 指定绝对路径；
- `flask --app wsgi reset-db` 会删除并重建数据库（仅演示环境使用）；
- 从 `baseline-v1` 升级到 `change-v2` 时，应用启动会自动执行幂等迁移（补 `students.email`、重建唯一索引、创建 `email_outbox`），**不要**为此清空旧库；
- 数据文件已在 `.gitignore` 中排除，不会提交到仓库。

## 7. 自动化测试

```bash
python -m pytest
```

- 覆盖 C1—C10 初始验收、C11—C19 变更验收、权限、表单校验、CSRF、通知失败隔离、事件幂等、数据库迁移；
- 使用临时 SQLite 数据库，不污染演示数据；
- 当前测试结果：**32 passed**（详见 `docs/08_回归测试表.md` 与终端输出）。

## 8. 云服务器部署（公网可访问）

以下以 Ubuntu 22.04/24.04 + Nginx + gunicorn 为例。

### 8.1 上传代码

```bash
sudo mkdir -p /opt/campus_event
sudo chown -R $USER:$USER /opt/campus_event
git clone <你的仓库地址> /opt/campus_event
cd /opt/campus_event
```

> 如果直接上传压缩包，请确保解压后 `wsgi.py`、`app/`、`requirements.txt` 位于 `/opt/campus_event` 根目录。

### 8.2 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 8.3 初始化数据库

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export DATABASE_PATH="/opt/campus_event/instance/campus_event.db"
flask --app wsgi init-db
```

请把 `SECRET_KEY` 写入下面的 systemd 配置或 `.env` 加载脚本，**不要提交到 Git**。

### 8.4 使用 gunicorn 启动

```bash
gunicorn -w 1 --threads 4 -b 127.0.0.1:8000 wsgi:app
```

- SQLite 同一时刻只允许一个写者，因此使用 **1 个 worker + 多线程**，避免多进程写锁冲突；
- 应用已绑定反向代理端口，不要直接暴露 8000 到公网。

### 8.5 systemd 托管

创建 `/etc/systemd/system/campus-event.service`：

```ini
[Unit]
Description=CampusEvent Flask App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/campus_event
Environment="SECRET_KEY=请替换为随机字符串"
Environment="DATABASE_PATH=/opt/campus_event/instance/campus_event.db"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/campus_event/.venv/bin/gunicorn -w 1 --threads 4 -b 127.0.0.1:8000 wsgi:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /opt/campus_event/instance
sudo systemctl daemon-reload
sudo systemctl enable --now campus-event
sudo systemctl status campus-event
```

### 8.6 Nginx 反向代理

创建 `/etc/nginx/sites-available/campus-event`：

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/campus-event /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8.7 安全组 / 防火墙

- 云服务器安全组放行 **TCP 80**（如需 HTTPS 再放行 443）；
- 不要对公网放行 5000 / 8000；
- Ubuntu 防火墙示例：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 8.8 公网验收

在**非服务器本机**的网络中执行：

```bash
curl http://<云服务器公网IP>/healthz
# 期望：{"status":"ok"}
```

浏览器访问 `http://<云服务器公网IP>/`，使用演示账号登录并完成一次报名。请将实际地址填写到本文档第 1 节。

### 8.9 HTTPS（可选）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

没有域名时可先用公网 IP 访问 HTTP；答辩演示建议配置域名 + HTTPS。

### 8.10 Windows 云服务器（可选）

```powershell
pip install waitress
waitress-serve --listen=0.0.0.0:8000 wsgi:app
```

在 Windows 防火墙与云安全组放行 8000，然后通过 `http://<公网IP>:8000/` 访问；更推荐使用域名 + 反向代理。

## 9. 版本与 Git 标签

| 标签 | 内容 |
| --- | --- |
| `baseline-v1` | 初始验收版本：两类报名策略 + 站内消息 |
| `change-v2` | 需求变更完成版本（见变更影响分析） |

切换版本：

```bash
git checkout baseline-v1
git checkout change-v2
```

`change-v2` 的数据库结构会自动迁移，切换标签后重启应用即可；两个版本使用同一个 `DATABASE_PATH` 时无需手工改表。

## 10. 设计文档

- [初始 SRS 分析](docs/01_初始SRS分析.md)
- [用例说明](docs/02_用例说明.md)
- [UML 类图 v1](docs/03_UML类图_v1.md)
- [时序图 v1](docs/04_时序图_v1.md)
- [设计模式决策报告](docs/05_设计模式决策报告.md)
- [设计评审记录](docs/06_设计评审记录.md)
- [变更影响分析](docs/07_变更影响分析.md)
- [回归测试表](docs/08_回归测试表.md)
- [项目总结（实验报告）](docs/09_项目总结.md)
- [变更版 UML 类图 v2](docs/10_变更版UML类图_v2.md)
- [AI 协作记录](AI_DEV_LOG.md)

## 11. 已知限制

1. SQLite 适合单机演示，不支持高并发写入；生产部署使用单 worker。
2. 通知为进程内事件，失败只留痕，不自动重试。
3. 邮件为 `email_outbox` 模拟发件箱，未接入真实 SMTP；未实现用户注册与找回密码。
4. 默认 HTTP 部署；公网长期使用请配置 HTTPS 并修改演示密码。
5. 活动时间按服务器本地时区解释，建议服务器设置 `Asia/Shanghai`。

## 12. 提交前自查清单

- [ ] 已把第 1 节的 `http://<云服务器公网IP>/` 替换为实际公网地址（不能是 `localhost` / `127.0.0.1`）；
- [ ] 云服务器安全组已放行 TCP 80（HTTPS 再放行 443），未对公网开放 5000/8000；
- [ ] 在非服务器本机网络访问 `http://<公网IP>/healthz` 返回 `{"status":"ok"}`；
- [ ] 使用 `admin`、`s001` 各完成一次登录、报名/审批操作；
- [ ] 本地执行 `python -m pytest -q` 显示 `32 passed`；
- [ ] 仓库中已包含 `baseline-v1` 与 `change-v2` 两个标签。
