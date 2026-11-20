# CampusEvent · 校园活动报名与管理系统

> 《软件工程》实验二 —— 基于设计模式的校园活动报名与管理系统
>
> 班级：计科2班　学号：242806010216　姓名：陈嘉宏

## 1. 在线访问地址

**公网地址：** https://37ko2b6o3sj5uocthcq.traesite.cn

> 说明：本项目部署在支持 Node.js 运行时的云托管平台，地址为公网可访问的 https 域名，不是 localhost / 127.0.0.1 本机地址。

## 2. 项目简介

校园活动信息的浏览、报名、审批与结果通知平台。系统支持两种活动报名方式：

- **直接报名**：名额充足时立即通过，满员即失败；
- **审核报名**：先提交申请进入待审核，由管理员批准/拒绝，批准时再次检查名额。

学生可查看活动、报名、取消报名、查询报名状态、接收站内通知；管理员可创建/编辑/归档活动、审批报名、查看报名统计与待审核列表。

需求变更（CR-01）后新增：**候补队列**（满员可排队、名额释放自动递补）、**邮件通知渠道**（与站内消息双通道，失败留痕、不重复通知）、**活动软删除**（保留历史报名记录）。

## 3. 功能清单（对应实验指导书 P2-F01 ~ P2-F08）

| 编号 | 功能 | 状态 |
| --- | --- | --- |
| P2-F01 | 学生浏览活动列表，按名称/分类/报名方式筛选 | 已实现 |
| P2-F02 | 直接报名、审核报名两种报名方式 | 已实现（变更后新增候补报名） |
| P2-F03 | 名额上限控制，满员拒绝报名 | 已实现 |
| P2-F04 | 管理员审核报名（批准 / 拒绝） | 已实现 |
| P2-F05 | 同一学生不能重复报名同一活动 | 已实现 |
| P2-F06 | 学生取消报名 | 已实现 |
| P2-F07 | 报名结果、审核结果写入站内消息 | 已实现（变更后增加邮件渠道） |
| P2-F08 | 管理员查看报名统计（已通过 / 待审核 / 剩余名额） | 已实现（变更后增加候补人数） |

## 4. 技术栈与架构

| 层次 | 技术 |
| --- | --- |
| 运行时 | Node.js 20+（无第三方运行时依赖） |
| Web 层 | Node.js 原生 `http` + 服务端渲染模板（自研轻量视图层） |
| 业务层 | 领域服务 `ActivityService` / `RegistrationService` + 策略模式 + 观察者模式 |
| 持久化 | SQLite（sql.js WebAssembly 版，随项目内置，无需安装数据库） |
| 测试 | Node.js 内置测试运行器 `node --test`（共 23 个用例） |

> **关于技术选型**：实验指导书推荐 Python + Flask。本项目需要部署到公网，而当前可用的云托管通道只支持 Node.js 服务端或静态站点，无法托管 Python 进程。为保证“公网可访问”这一硬性验收要求，后端采用 Node.js；分层结构、设计模式、SOLID 实践与测试策略与语言无关，设计文档中的类图、时序图、模式决策均按同一套领域模型编写。

分层依赖方向（由外向内）：

```
Web（server.js / web/router.js / web/views.js）
        ↓
Service（service/*.js：事务边界、业务规则编排）
        ↓
Domain（domain/*.js、policy/*.js、events/*.js、notification/*.js）
        ↓
Repository（repository/*.js：SQL 访问）
        ↓
Database（db/database.js：sql.js 封装、迁移、落盘）
```

## 5. 设计模式应用

| 模式 | 位置 | 解决的问题 |
| --- | --- | --- |
| 策略模式 | `project/src/policy/registrationPolicy.js` | 报名方式（直接/审核/候补）可独立扩展，主流程不随新规则修改 |
| 工厂 + 注册表 | `PolicyFactory` | 由活动配置驱动策略选择，新增策略只需注册 |
| 观察者模式 | `events/domainEvents.js`、`notification/notificationService.js` | 报名状态变化与通知解耦，通知失败不影响报名事务 |
| 仓储模式 | `repository/*.js` | 隔离 SQL 与业务逻辑，便于替换持久化实现与测试 |
| 依赖注入 | `app.js` 装配根 | 所有依赖显式注入，测试可替换数据库路径与时钟 |

## 6. 目录结构

```
.
├── project/                     # 应用源代码
│   ├── src/
│   │   ├── server.js            # 进程入口
│   │   ├── app.js               # 装配根（依赖注入）
│   │   ├── config.js            # 端口、数据库路径
│   │   ├── db/                  # 数据库封装、迁移脚本、演示数据
│   │   ├── domain/              # 实体、枚举、错误、口令散列
│   │   ├── policy/              # 报名策略（策略模式）
│   │   ├── events/              # 领域事件与事件总线（观察者模式)
│   │   ├── notification/        # 通知服务与渠道
│   │   ├── repository/          # 仓储（SQL）
│   │   ├── service/             # 业务服务
│   │   └── web/                 # 路由与视图
│   ├── public/                  # 样式表
│   ├── vendor/sql.js/           # 内置 SQLite（WASM）
│   └── package.json
├── tests/                       # 自动化测试（验收 + 回归）
├── docs/                        # 实验文档（需求、UML、决策报告、变更、测试、总结）
├── build.sh / run.sh            # 云托管构建与启动脚本
├── README.md                    # 本文件
└── AI_DEV_LOG.md                # AI 辅助开发日志
```

## 7. 本地运行

环境要求：Node.js 20 或更高版本（无需 `npm install`，项目零运行时依赖）。

```bash
# 在仓库根目录执行
node project/src/server.js
# 浏览器打开 http://127.0.0.1:8000
```

自定义端口/数据目录：

```bash
# Windows PowerShell
$env:PORT=8080; $env:CAMPUS_DATA_DIR=".\data"; node project/src/server.js
```

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 监听端口 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `CAMPUS_DATA_DIR` | 系统临时目录下 `campus-event-data` | SQLite 数据目录 |
| `CAMPUS_DB_PATH` | `CAMPUS_DATA_DIR/campus_event.sqlite` | 数据库文件路径 |

首次启动自动建表并写入演示数据与演示账号。

## 8. 自动化测试

```bash
# 在仓库根目录执行（Node.js 20+）
node --test
```

- `tests/v1.acceptance.test.js`：C1–C10 验收用例及边界（登录/权限/字段校验/已开始活动/归档规则/页面渲染）；
- `tests/v1.notification.test.js`：通知失败隔离、重复通知幂等、订阅者异常隔离；
- `tests/v2.change.test.js`：候补入队与递补、邮件双通道通知、活动软删除与归档审批限制。

当前结果：**23 个用例全部通过（0 失败）**，详细执行记录见 `docs/09_回归测试表.md`。

测试使用独立临时数据库，不会污染运行数据；断言失败信息可直接定位业务规则。

## 9. 云端部署

项目已适配“构建产物 + 启动命令”的 Node.js 托管约定：

```bash
# 构建：把运行所需文件收集到 dist/
sh build.sh
# 启动：在 dist/ 内执行，监听 $PORT
sh run.sh
```

- `build.sh` 只复制运行时必需文件（`src/`、`public/`、`vendor/`、`package.json`），不包含测试与文档；
- `run.sh` 读取平台注入的 `PORT`，绑定 `0.0.0.0`；
- 数据写入系统临时目录，平台重启/重新部署后会自动重建演示数据（详见第 11 节）。

若部署到自有服务器，也可直接 `node project/src/server.js` 并用 Nginx 反向代理。

### 部署记录

| 项目 | 内容 |
| --- | --- |
| 平台 | Trae 云托管（FunctionWeb，Node.js 20） |
| 站点 ID | `37ko2b6o3sj5uocthcq` |
| 部署 ID | `dep_6afeb8c5147cfc2e46c0daf5` |
| 部署时间 | 2026-11-19 |
| 访问地址 | https://37ko2b6o3sj5uocthcq.traesite.cn |
| 验证结果 | 公网可访问，登录页与演示账号正常 |

云端构建时由 `build.sh` 收集 `project/src`、`project/public`、`project/vendor` 与 `package.json` 到 `dist/`，再由 `run.sh` 以 `$PORT` 启动；SQLite 数据写在实例临时目录。

## 10. 演示账号

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 管理员 | `admin` | `admin123` |
| 学生 | `s1001` 张三 | `123456` |
| 学生 | `s1002` 李四 | `123456` |
| 学生 | `s1003` 王五 | `123456` |
| 学生 | `s1004` 赵六 | `123456` |

## 11. 数据与持久化

- 首次启动执行 `project/src/db/migrations/` 中的迁移脚本，建表并写入 4 个演示活动；
- 报名、消息、通知留痕都写入 SQLite 文件，事务提交后立即落盘，重启服务数据仍在；
- 云托管环境只允许写临时目录，因此数据目录默认使用系统临时目录；平台重建实例后会重新初始化演示数据（只影响演示数据，不影响功能验收）。

## 12. 实验文档索引

| 文档 | 说明 |
| --- | --- |
| `docs/01_初始SRS分析.md` | 需求分析、参与者、功能与非功能需求、业务规则 |
| `docs/02_用例说明.md` | 用例图与用例规约 |
| `docs/03_UML类图_baseline_v1.md` | 初版类图（含职责说明） |
| `docs/04_UML类图_change_v2.md` | 变更版类图与差异高亮 |
| `docs/05_时序图.md` | 报名、审批、候补递补、通知时序 |
| `docs/06_设计模式决策报告.md` | 候选方案比较与选择依据 |
| `docs/07_变更单CR-01.md` | 模拟教师发布的需求变更单 |
| `docs/08_变更影响分析.md` | 影响范围、风险评估、实施步骤 |
| `docs/09_回归测试表.md` | 两版测试执行记录与回归结果 |
| `docs/10_设计评审记录.md` | 设计评审检查表与评审意见 |
| `docs/11_项目总结.docx` | 5–8 页项目总结报告 |
| `docs/12_答辩PPT.pptx` | 答辩演示文稿 |

## 13. 交付物清单（对照实验要求）

| 实验要求 | 交付位置 |
| --- | --- |
| 初始 SRS 分析 | `docs/01_初始SRS分析.md` |
| 用例说明 + 用例图 | `docs/02_用例说明.md`、`docs/images/use_case.png` |
| 初版 UML 类图 | `docs/03_UML类图_baseline_v1.md`、`docs/images/class_v1.png`、`docs/uml/class_v1.mmd` |
| 变更版 UML 类图 | `docs/04_UML类图_change_v2.md`、`docs/images/class_v2.png`、`docs/uml/class_v2.mmd` |
| 关键交互时序图（≥2） | `docs/05_时序图.md`、`docs/images/sequence_*.png` |
| 设计模式决策报告 + 可维护性对比 | `docs/06_设计模式决策报告.md` |
| 两版源码与 Git 标签 | `project/src`、标签 `baseline-v1` / `change-v2` |
| 需求变更单 | `docs/07_变更单CR-01.md` |
| 变更影响分析 | `docs/08_变更影响分析.md` |
| 回归测试表 | `docs/09_回归测试表.md`、`tests/` |
| AI_DEV_LOG.md | `AI_DEV_LOG.md` |
| 项目总结（5–8 页 docx） | `docs/11_项目总结.docx`（实测 6 页） |
| 答辩 PPT | `docs/12_答辩PPT.pptx`（13 页） |
| 设计评审记录（含签名） | `docs/10_设计评审记录.md` |
| 部署与运行说明 + 公网地址 | `README.md`、`build.sh`、`run.sh` |
