# 业务数据库 v4

v4 将通用文档关系替换为业务主键、唯一键和外键。建表定义支持 SQLite 与 MySQL，表名统一使用无前缀名称。v3 运行程序仍使用原存储适配器。切换需要先完成 v4 业务读写和数据迁移。

## 账号与访问控制

| 表 | 键和用途 |
| --- | --- |
| `system_accounts` | 整数 `id`，`auth_username` 唯一。保存密码哈希、权限组、可用次数、状态和主题。 |
| `school_accounts` | 整数 `id`，`school_username` 唯一。学号按字符串保存，保留前导零。 |
| `account_school_links` | 联合主键 `(system_account_id, school_account_id)`。绑定密码和 UA 存在同一行，每行有独立 `revision`。 |
| `school_account_information` | 学校账号 ID 为主键，保存校方用户资料、部门资料和更新时间。 |
| `school_account_settings` | 学校账号 ID 为主键，保存运行参数、默认值、标签之外的选项及计数。 |
| `school_account_legacy_credentials` | 学校账号 ID 为主键，单独保存已验证来源的旧全局凭据。访问沿用管理权限及旧回退规则。 |
| `permission_groups`、`group_permissions`、`account_permission_overrides` | 权限组、组权限、账号覆盖各有独立约束。用户组通过系统账号外键关联。 |
| `account_sessions` | `session_id` 主键，账号、生命周期、模式和 UA 用类型列。任务和界面等快照保存在所属会话的 JSON 中。 |
| `system_account_tokens`、`guest_session_tokens` | 系统令牌按账号唯一，游客令牌按会话唯一。令牌摘要用于查找，值和有效期用于现有令牌生命周期。 |

账号与学号的唯一性按完整文本比较。MySQL 用 `VARBINARY` 比较 UTF-8 字节，SQLite 用 `BINARY` 排序规则。单条绑定更新同时匹配两个外键和预期 `revision`，并在同一条 SQL 中增加修订号。已验证登录可创建绑定，UA 修复只更新已有行。密码为空的已有绑定保留手动补全含义。

## 财务与业务状态

| 表 | 键和用途 |
| --- | --- |
| `billing_records` | 同一学校账号内 `billing_id` 唯一，按学校账号、状态和时间查询。 |
| `payment_orders` | 商户 `order_id` 唯一。第三方交易号独立索引。 |
| `payment_order_bills` | 联合主键 `(payment_order_id, billing_record_id)`，用两个真实外键关联订单与账单。 |
| `payment_refunds` | 订单外键和订单内序号唯一。第三方退款号单独记录，允许旧数据为空。 |
| `system_settings` | 联合主键 `(scope, setting_key)`，值分为纯文本和 JSON。缺行、空文本、空对象和 JSON `null` 独立表示。 |
| `sms_records`、`messages`、`reminders` | 每条短信审计、留言和提醒有独立业务键。审计保留历史账号名。 |
| `background_tasks`、`background_image_state` | 一个会话对应一条当前后台任务状态。背景分配、组合与绑定存为单组状态。 |
| `deleted_account_archives` | `archive_id` 主键，按独立历史快照保存已删除账号。 |
| `schema_migrations` | 保存结构版本和建表时间。 |

金额统一按整数分保存。订单、账单、退款和审计记录在系统账号删除后保留。账号的绑定、权限覆盖、会话和系统令牌由外键清理。需保留账单的学校账号应继续保留身份记录。

## 创建验证库

```powershell
python tools/init_database_v4.py --sqlite-path data/schema-v4-review.sqlite3
```

MySQL 先创建独立空数据库，使用现有 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD` 环境变量连接，再把目标库名传给工具。

```powershell
python tools/init_database_v4.py --mysql-database schema_v4_review
```

SQLite 目标必须是新文件，MySQL 目标必须为空。工具只写结构版本行和表定义。结构版本行表示建表完成，应用切换需要独立的数据验证。

## v3 数据迁移映射

1. 只读解码 v3 的记录布局和实体，按领域生成转换清单。先列出超长或缺失标识、重复业务键、孤儿引用、无法解码记录和金额异常。问题记录保留在旧库或受控迁移档案，不自动创建可登录账号、有效令牌或财务关系。
2. 先迁权限组、系统账号和学校账号，再建立旧账号别名到新 ID 的映射。绑定按两个 ID 写入，保留密码与 UA 的归属、空凭据与旧字段别名。学校设置、公开资料和全局旧凭据分别迁移。未解析归属的旧绑定单独审查其管理员可见性。
3. 会话按经校验的会话 UUID 写入。核对旧索引和快照内容是否一致，配置并验证会话归属。系统令牌按账号合并，游客令牌按会话迁移。权限组和覆盖项按现有拒绝优先语义核对。
4. 用商户订单号和学校账单业务键对照财务记录。比对订单明细与账单侧付款关系的一致性。同一关联存在冲突时在预检报告中保留两侧来源。按原分值逐项核验金额、退款和可用次数。旧本地时间转换成约定时区后保存，无法判定时区时保留原值供核对。
5. 设置按业务域和键映射。可信代理需区分缺失、空白、仅注释、通配符和具体规则。未由类型列表达的 JSON 仅保留属于该领域的快照或扩展数据。日志文件继续由现有日志系统管理。
6. 在独立目标完成迁移预演，逐域比较数量、业务唯一键、金额和数据摘要，再用 v4 的实际调用入口验证登录、权限、会话恢复、单行凭据更新、账单和支付。正式切换时停写，重新核对源数据，验证后再切换连接。源库保留到切换验收结束。
