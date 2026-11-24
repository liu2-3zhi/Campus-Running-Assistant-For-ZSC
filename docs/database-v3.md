# 业务数据库 v3

SQLite 与 MySQL 使用同一业务模型。程序启动和迁移目标都固定使用无前缀表，并忽略遗留的 `MYSQL_TABLE_PREFIX`。迁移旧库时通过 `--legacy-table-prefix` 指定源表前缀。

学校登录页和多账号选择器直接查询学校账号、绑定及所选账号的凭据列。批量详情按需查询两项统计，省去逐账号重建配置记录。登录成功只更新当前学校账号配置和当前系统账号的绑定。已有 v3 数据库可以直接使用这些查询。

## 表与职责

| 表 | 内容 |
| --- | --- |
| `system_accounts` | 系统登录账号、密码哈希、手机、状态、次数、主题和会话 ID 集合 |
| `school_accounts` | 学校账号、配置、参数、统计、标签，每个账号配置一行 |
| `account_school_links` | 系统账号与学校账号关联，唯一 owner＋school，保存绑定密码和独立 UA |
| `school_account_information` | 学校账号资料、学校／部门信息、更新时间和历史统计 |
| `system_settings` | 按配置分组保存设置，一组一行，不按 JSON 叶子拆行 |
| `access_permissions` | 权限组定义、账号权限组、额外允许／拒绝项 |
| `account_sessions` | 会话元数据、参数、Cookie、任务快照、资料及多账号状态 |
| `authentication_tokens` | 系统账号／游客 Token、主体、会话及有效期 |
| `deleted_account_archives` | 删除账号的历史快照，不作为活跃账号恢复 |
| `payment_orders` | 支付订单、金额分、状态、渠道、交易号和时间 |
| `payment_order_bills` | 订单与账单／学校账号关联明细 |
| `payment_refunds` | 退款金额分、退款号、状态、操作人和时间 |
| `billing_records` | 学校账号账单、归属、支付及清账状态 |
| `sms_records` | 短信发送、拒绝、异常、测试和手动添加的审计记录 |
| `messages`、`reminders` | 留言、通知及展示时间和权限 |
| `background_tasks` | 后台执行状态、任务序列及进度 |
| `background_image_state` | 背景分配、组合、绑定和领取状态 |
| `storage_indexes` | 旧版本索引兼容信息 |

19 张业务表加两张元数据表，共 21 张，替代原 41 张表。`storage_documents` 只保存兼容标识、结构、版本和摘要；`schema_migrations` 保存版本与就绪状态。业务字段以对应业务表为权威，元数据不另存完整业务正文。

`document_id` 外键用于原子级联清理，`row_id` 是稳定记录标识。关联表对完整 owner／school 标识建立唯一约束；旧版未解析归属保留告警，不会自动创建有权限账号。学校全局配置里的历史密码／UA 与 owner 绑定凭据分开保留，不覆盖其他绑定，也不合并冲突的统计来源。财务金额继续使用整数分。

会话和配置使用命名 JSON 列。普通对象、数组、字符串可直接读写；浮点数及大整数使用保留标识包装保持跨引擎精度，业务读取恢复原类型。v3 重建内容使用稳定键顺序，避免 MySQL JSON 排序导致摘要误报；v2 读取规则保持兼容。

## 本地默认运行

直接 `python main.py`，未设置存储变量时在程序目录创建 `data/application.sqlite3`，与调用者工作目录无关。启动日志显示 `backend=SQLite` 和数据库位置。显式 `APP_STORAGE_ROOT` 仍需匹配程序目录。日志、图片、上传、缓存和证书保持原位置。

全新 SQLite 将可信代理默认规则的注释保存到数据库，写入成功后标记数据库就绪。IPv4 和 IPv6 的内网、回环及链路本地地址自动信任。已有数据库中的代理规则保持原样，空白或缺失规则沿用全信任模式。仅保留注释时，只使用内置规则。

发现未迁移旧业务文件时拒绝静默创建空库。停止应用后先迁移：

```bash
python tools/migrate_storage.py --root . --backend sqlite plan
python tools/migrate_storage.py --root . --backend sqlite import --stopped --remove-source
python tools/migrate_storage.py --root . --backend sqlite verify --database-only
```

`--remove-source` 不备份。完整导入、重读源和校验目标后，检查全部路径和原始摘要，仅删除 root 内受管业务文件。日志、旧短信 JSONL、图片、证书及源码不删除；源变化、符号链接、越界路径或校验不符均阻止清理。

## 旧数据库迁移

停止旧版，使用新版程序迁移。源和目标可在同一数据库中，表名集合必须互不重叠。Compose 仍提供空值覆盖，以便兼容尚未支持自动忽略的旧镜像。更换镜像或容器环境后用 `docker compose up -d --force-recreate` 重建。

```bash
python tools/migrate_storage.py --backend mysql --source relational-v2 --source-backend mysql --legacy-table-prefix app_ import --stopped
python tools/migrate_storage.py --backend mysql --source relational-v2 --source-backend mysql --legacy-table-prefix app_ verify
```

旧 SQLite 使用 `--source-backend sqlite --source-sqlite-path data/old.sqlite3` 指定来源，`SQLITE_DATABASE_PATH` 指定目标。旧表带前缀时可在同一 SQLite 文件中升级。

默认保留旧表；在 `import` 后加 `--drop-legacy`，可在完整校验后删除明确选中的旧表，不备份、不删除其他表。MySQL DDL 不承诺事务回滚，只能停写执行。

损坏记录默认中止。仅明确添加 `--skip-corrupt-sessions` 时允许跳过无法解码的普通业务会话并报告位置；索引、账号、支付损坏及连接错误仍中止。不会根据残留快照猜回身份或权限。

Docker 默认入口会先检查业务库，迁移时覆盖入口：

```bash
docker compose run --rm --entrypoint python python-running-helper tools/migrate_storage.py --backend mysql --source relational-v2 --source-backend mysql --legacy-table-prefix app_ import --stopped
```

Docker 文件迁移须另行只读挂载来源并指定 `--root`，SQLite 目标放在只读来源外。`--remove-source` 仅用于明确允许删除的可写本地来源。v1 MySQL 文档库继续使用 `--source legacy-mysql --legacy-table-prefix app_`。`export --output <new-directory> --stopped` 支持完整导出，包括短信记录，只接受全新目录，不恢复文件运行后端。

## 运行缓存

直接启动默认使用有容量和过期限制的进程内缓存。Compose 通过内部网络使用 Redis，服务没有宿主机端口，断线时回退到内存。缓存仅保存按调用者和权限范围划分的账号名列表，查询前仍检查权限。应用提交学校账号改动后使用新的缓存键。直接 SQL 修改后等待短期缓存过期即可重新读取。

## 短信与日志

旧 `sms_history.jsonl` 单独只读导入并保留原文件、字段和类型。新审计只保存元数据，不存验证码或发送正文，不从历史恢复有效验证码。SQL 先过滤、倒序、限制 100 条再重建；接口保留审计权限和展示脱敏。

学校账号批量日志记录真实 `storage`、owner、数量和 `elapsed_ms`，取消逐账号“成功读取 INI 文件”刷屏；异常保留后端与堆栈。会话日志使用“会话记录／持久化会话／记录键”。日志目录、分流和归档位置不变。
