# CampusEvent 初始需求分析（SRS 分析）

- 班级：计科2班
- 学号：242806010216
- 姓名：＿＿＿＿＿＿
- 项目代号：CampusEvent
- 版本：baseline-v1（初始验收版本）
- 依据：《软件工程》实验指导书 3.2、3.5、附录 B

## 1. 项目目标与范围

校园管理员发布活动，学生浏览活动并报名。初始版本必须支持两类报名规则：

1. **直接报名**：名额充足时提交即通过；
2. **管理员审核**：提交后进入待审核，由管理员批准或拒绝。

报名与审核结果通过**站内消息**通知。系统面向课程演示，使用固定演示账号，不实现注册、复杂权限、邮件/短信、支付等功能。

### 1.1 范围内

- 活动创建、编辑、下架（软删除）；
- 活动列表、名称搜索、活动详情；
- 学生报名、取消报名；
- 直接报名与审核报名两类策略；
- 管理员批准、拒绝待审核申请；
- 报名状态管理与名额统计；
- 站内消息通知；
- SQLite 持久化。

### 1.2 范围外

- 用户注册、找回密码、第三方登录；
- 多管理员审批流、角色细分；
- 邮件、短信、微信推送；
- 活动签到、支付、评论；
- 消息队列、分布式事务；
- 移动端 App。

## 2. 角色与权限

| 角色 | 演示账号 | 权限 |
| --- | --- | --- |
| 学生 Student | s001 / s002 / s003（密码 123456） | 浏览活动、报名、取消自己的报名、查看自己的站内消息 |
| 管理员 Admin | admin（密码 admin123） | 创建/编辑/下架活动、查看报名、批准/拒绝待审核申请 |

固定账号仅用于课程演示。密码以哈希形式存储在 SQLite 中，不在仓库保存明文凭据文件。

## 3. 领域数据

### 3.1 Student（学生）

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| student_id | TEXT | 主键，唯一 |
| name | TEXT | 必填 |

### 3.2 Activity（活动）

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| activity_id | INTEGER | 主键，自增 |
| title | TEXT | 必填，1—100 字 |
| category | TEXT | 必填，1—30 字 |
| start_at | TEXT | 必填，ISO-8601 时间；新建/修改时必须晚于当前时间 |
| location | TEXT | 必填，1—100 字 |
| capacity | INTEGER | 正整数，≤ 100000 |
| policy_type | TEXT | `direct` 或 `approval` |
| description | TEXT | 可选，≤ 1000 字 |
| is_deleted | INTEGER | 0/1，软删除标记 |
| created_at / updated_at | TEXT | 系统维护 |

### 3.3 Registration（报名记录）

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| registration_id | INTEGER | 主键，自增 |
| activity_id | INTEGER | 外键 → Activity |
| student_id | TEXT | 外键 → Student |
| status | TEXT | `pending` / `approved` / `rejected` / `cancelled` |
| created_at / updated_at | TEXT | 系统维护 |

数据库使用**部分唯一索引**保证同一学生对同一活动最多一条 `pending` 或 `approved` 记录；`rejected`、`cancelled` 作为历史保留，允许再次申请。

### 3.4 Message（站内消息）

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| message_id | INTEGER | 主键，自增 |
| student_id | TEXT | 接收学生 |
| activity_id | INTEGER | 关联活动，可为空 |
| content | TEXT | 消息内容 |
| is_read | INTEGER | 0/1 |
| created_at | TEXT | 创建时间 |

## 4. 功能性需求

| 编号 | 需求 | 验收要点 |
| --- | --- | --- |
| P2-F01 | 管理员创建、编辑、删除活动，设置名称、类型、时间、地点、人数上限、报名方式 | 字段校验；删除采用软删除并保留历史 |
| P2-F02 | 学生浏览活动列表与详情，可按名称筛选 | 搜索只返回名称匹配的活动 |
| P2-F03 | 学生报名、取消；禁止同一活动重复有效报名 | 重复提交被拒绝，历史记录保留 |
| P2-F04 | 直接报名自动通过；审核型报名进入待审核 | 两种策略由配置驱动，不在服务中硬编码分支 |
| P2-F05 | 管理员批准/拒绝待审核申请，批准时再次检查名额 | 满员时批准失败，状态保持待审核 |
| P2-F06 | 状态包含待审核、已通过、已拒绝、已取消，转换符合规则 | 非法状态转换被拒绝 |
| P2-F07 | 报名结果与审核结果写入站内消息 | 报名成功、待审核、批准、拒绝、取消均产生消息 |
| P2-F08 | 按活动查看已通过数、待审核数和剩余名额 | 剩余名额 = max(容量 − 已通过数, 0) |

## 5. 初始业务规则

| 编号 | 规则 | 实现位置 |
| --- | --- | --- |
| BR-01 | 直接报名在名额充足时创建“已通过”报名并通知 | `DirectRegistrationPolicy` + `RegistrationService` |
| BR-02 | 审核型报名提交后为“待审核”，批准/拒绝由管理员执行 | `ApprovalRegistrationPolicy` + `RegistrationService` |
| BR-03 | 名额只统计“已通过”；待审核不占名额；满员不得再批准 | 仓储计数 + 审批服务 |
| BR-04 | 同一学生同一活动不得存在两条待审核/已通过有效报名 | 服务校验 + 部分唯一索引 |
| BR-05 | 学生可取消自己的待审核/已通过报名；活动开始后不允许新增报名 | `RegistrationService.cancel/register` |
| BR-06 | 通知失败必须留痕，但不得导致已合法提交的报名消失 | 事务提交后发布事件；失败写 `notification_failures` |
| BR-07 | 活动与报名持久化；删除有报名的活动采用软删除 | `activities.is_deleted` |

### 5.1 规则边界说明

- **取消时间**：指导书只限制“活动开始后不允许新增报名”，未限制取消。本实现允许学生在活动开始后取消待审核/已通过报名，保证规则与文档一致；若后续变更要求关闭取消通道，可在服务层增加时间校验。
- **删除策略**：选择软删除。管理员删除活动后，学生端不再展示，但历史报名、消息、统计仍可追溯；管理员活动详情保留“已下架”标记且不能继续审批。
- **通知事务**：报名状态先提交，再发布事件。站内消息写入失败时记录失败日志，报名仍有效；用户可在消息列表缺失时由管理员依据报名记录核实。

## 6. 非功能性需求

| 类别 | 要求 |
| --- | --- |
| 技术栈 | Python 3.11+、Flask、SQLite；无前端框架依赖 |
| 部署 | 可部署到云服务器，公网通过 HTTP 访问；绑定 `0.0.0.0`，生产使用 WSGI 服务器 |
| 安全 | 密码哈希存储；会话 Cookie HttpOnly/SameSite=Lax；所有 POST 带 CSRF Token；参数化 SQL |
| 可维护性 | 领域层、服务层、仓储层、路由层分离；策略与通知渠道可扩展 |
| 可测试性 | pytest 可在临时数据库上复现 C1—C10 |
| 可用性 | 中文界面，表单错误有明确提示；桌面浏览器可用，窄屏自适应 |
| 数据规模 | 演示规模（数百活动/报名）响应正常 |

## 7. 验收用例映射

| 用例 | 场景 | 自动化测试 |
| --- | --- | --- |
| C1 | 管理员创建直接报名活动，容量 2 | `tests/test_acceptance.py::test_c1_create_direct_activity` |
| C2 | 学生 A 报名直接报名活动 | `test_c2_student_registers_direct_activity` |
| C3 | 学生 A 重复报名 | `test_c3_duplicate_active_registration_is_rejected` |
| C4 | 名额满后学生 C 报名失败 | `test_c4_capacity_limit_for_direct_registration` |
| C5 | 审核型活动申请后为待审核 | `test_c5_approval_activity_creates_pending_registration` |
| C6 | 管理员批准待审核报名 | `test_c6_admin_approves_pending_registration` |
| C7 | 管理员拒绝待审核报名 | `test_c7_admin_rejects_pending_registration` |
| C8 | 批准时容量已满 | `test_c8_approval_rechecks_capacity` |
| C9 | 取消待审核/已通过报名 | `test_c9_cancel_pending_and_approved_registrations` |
| C10 | 重启后数据仍一致 | `test_c10_data_persists_after_restart` |

## 8. 关键假设

1. 课程演示不要求真实邮件/短信，通知以站内消息为准；后续变更可扩展通知渠道。
2. 时间使用服务器本地时区（部署时建议 `Asia/Shanghai`），数据库存 ISO-8601 字符串。
3. 管理员为可信角色，但仍需登录；学生只能操作自己的报名记录。
4. 活动一旦开始，已有报名与审批记录仍保留，但新报名被拒绝。
