# 数据库存储与离线迁移

运行后端只有 SQLite 和 MySQL/MariaDB。默认创建本地 `data/application.sqlite3` 供开发测试使用；`APP_STORAGE_BACKEND=file` 已冻结并显式拒绝。数据库不可用、未初始化或迁移未完成时不会回退旧 JSON/INI。架构边界见[数据库优先存储设计](database-first-design.md)和[实施计划](database-first-plan.md)。

本版本只支持**单个应用实例**。数据库事务和修订号不能替代任务、账号执行和账单操作的进程内锁；不要启动多个应用副本共同操作同一数据库。

## 范围与关系化结构

运行期和迁移工具共用 `StoragePolicy` 白名单，覆盖系统账号、学校账号 JSON/INI、权限、会话、Token、后台任务、订单、账单、留言、提醒、背景绑定、删除账号归档及受管配置。`configs/config.json`、`trusted_ips.txt` 也进入数据库，不再作为持续更新的本地权威配置。

SQLite 与 MySQL v2 使用相同的领域表：身份/权限、学校账号及用户绑定、会话/Token、任务、支付/账单/退款、内容、背景和配置。兼容 registry 只保存文档定位、结构布局、修订号、时间及摘要，不以通用 BLOB 保存整份业务正文。核心字段由独立类型列决定，动态扩展留在实体的扩展 JSON；兼容重建保留字段存在性与原 JSON 类型，并反映核心 SQL 列的改动。

- 金额使用整数分，迁移以 `Decimal` 严格检查精度，不静默舍入。时间戳等数值在 SQLite 使用双精度，在 MySQL 使用 `DECIMAL(65,30)` 并以 Decimal 精确传输；扩展 JSON 的浮点数以十六进制表示编码、大整数以字符串表示编码，重建时恢复原类型，避免原生 MySQL JSON 的末位舍入。
- 学校账号全局资料与用户绑定分离，UA 按系统用户 owner + 学校账号绑定隔离；同一学号绑定给不同用户时不能共用 UA。
- 订单、账单关联和退款拆表。账单仍属于学校账号，不因创建订单的系统用户删除而级联丢失。
- 用户 Token 仍按用户保存，游客 Token 按 UUID 保存；兼容旧索引不改变生命周期。
- 应用配置按 section/key 或叶子值拆行，不把整份配置正文塞入一个通用 JSON 记录。

日志位置、文件名、归档和挂载**保持不变**。默认或自定义日志目录整棵排除，包括 JSON/JSONL 状态、支付/账单日志及审计归档。图片、头像、上传、随机背景、地图和其他缓存、SSL 证书与私钥及白名单外文件继续留在原磁盘路径。

来源文档数不等于实体行数，不能只比较总行数判断成功。v2 校验比较重建后的语义、类型、摘要及来源映射；导出可能使用规范化 JSON/INI 排版，不保证与原文件逐字节相同。源文件保持只读。

## 配置与启动

依赖安装使用 `python -m pip install -r ssl/requirements.txt`。全新环境首次启动可初始化默认 SQLite 数据库、配置和管理员；发现尚未迁移的旧受管文件时会拒绝直接启动空库，应先离线导入。MySQL 数据库和专用账号须预先创建，使用 UTF-8/utf8mb4；初始化需要建表权限，运行需要相应表读写权限。应用不创建数据库或数据库账号。

| 变量 | 用途 |
| --- | --- |
| `APP_STORAGE_BACKEND` | `sqlite`（默认）或 `mysql`；拒绝 `file` |
| `APP_STORAGE_ROOT` | 应用根目录，容器内为 `/app` |
| `SQLITE_DATABASE_PATH` | SQLite 文件位置，默认 `data/application.sqlite3` |
| `MYSQL_HOST` / `MYSQL_PORT` | 外部数据库地址和端口 |
| `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` | 专用账号、密码和数据库 |
| `MYSQL_TABLE_PREFIX` | 表前缀，仅允许以字母开头的字母、数字、下划线 |
| `MYSQL_CONNECT_TIMEOUT` / `MYSQL_READ_TIMEOUT` / `MYSQL_WRITE_TIMEOUT` | 连接、读、写超时秒数 |
| `MYSQL_SSL_CA` | 进程可读的受信任 CA 文件，使用时同时挂载证书 |

Docker 直接在 Compose `environment` 填写连接变量，不使用 `.env`、`env_file` 或 `--env-file`。仓库示例仅含占位值；实际值在本地部署配置中修改，**不得提交真实凭据**。离线测试可使用当前进程环境，不把密码放入命令参数、报告、测试样本或文档。

运行期代码根目录、`APP_STORAGE_ROOT` 和当前工作目录必须一致，防止数据库与物理路径混用。离线 CLI 的 `--root` 可指向独立可信源目录；工具从源 `configs/config.json` 读取自定义业务目录和日志目录以确定迁移范围，不启动应用。

## 停服后迁移文件副本

先停止应用及所有写入进程，备份源文件、数据库和磁盘资源。`--stopped` 表示操作人员已确认停写，不会自动停止服务。来源必须完整、可信、反映当前业务状态；迁移期间不得重启写入者。

全局参数放在子命令前。`plan` 仅扫描、解析和预检文件，不连接数据库；`init/import/verify/export` 由 `--backend sqlite/mysql` 选择目标。示例 `/legacy` 为只读源挂载，连接配置由进程或 Compose 提供：

```bash
python tools/migrate_storage.py --root /legacy --backend mysql plan
python tools/migrate_storage.py --root /legacy --backend mysql init
python tools/migrate_storage.py --root /legacy --backend mysql import --stopped
python tools/migrate_storage.py --root /legacy --backend mysql verify
```

`init` 只创建/检查 v2 表，不导入、不标记就绪。导入前预检全部来源及类型，开始后关闭就绪标志；重新核对来源与目标全部通过才标记可运行。`import` 和独立 `verify` 均成功后再启动应用。

测试 SQLite 时改用 `--backend sqlite`，并把 `SQLITE_DATABASE_PATH` 设置在**源目录之外**。未显式指定时，CLI 的默认数据库位于 `--root` 下的 `data/application.sqlite3`，不能让目标落入只读源挂载。Compose 已将其固定为 `/app/data/application.sqlite3`。

空文件或纯空白文件默认拒绝。确认只是预建占位文件时，可在 `plan/import/verify` 分别添加 `--skip-empty`，输出会显示跳过数；不能以此掩盖应有数据损坏。JSON 拒绝非标准 NaN 等数值，INI 使用兼容解析器预检。

默认 `--conflict error` 拒绝同标识不同内容，一致记录幂等跳过。`--conflict overwrite` 显式以来源覆盖冲突；`--conflict skip` 保留冲突，但最终不一致仍使校验失败。`--batch-size` 默认 100，每批事务独立提交；失败回滚当前批，已提交批次保留，修复后用相同来源和参数重试。数据库多余记录不会自动删除，也不能在存在差异时标记就绪。身份或权限归属冲突必须明确处理，不推断默认 owner 或更宽权限。

## Docker Compose

`run/docker-compose.yml` 默认 SQLite，通过 `./data:/app/data` 持久化。`run/docker-compose.mysql.yml` 只覆盖应用的外部 MySQL 连接变量，**没有内置 MySQL 服务、数据库卷或数据库启动依赖**。确认镜像包含当前代码后，在本地编辑占位连接值。容器内 `localhost` 指向自身，应使用应用容器可达的数据库地址。

旧配置、账号、会话、Token 等受管目录的运行挂载已移除。升级需将停写后的完整旧数据根目录另行只读挂载到 `/legacy`，不能假定旧文件仍位于容器 `/app`。以下从 `run` 目录执行，替换示例源路径：

```bash
docker compose -f docker-compose.yml -f docker-compose.mysql.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.mysql.yml stop python-running-helper

docker compose -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python -v "/path/to/stopped-data:/legacy:ro" python-running-helper tools/migrate_storage.py --root /legacy --backend mysql plan
docker compose -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python -v "/path/to/stopped-data:/legacy:ro" python-running-helper tools/migrate_storage.py --root /legacy --backend mysql init
docker compose -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python -v "/path/to/stopped-data:/legacy:ro" python-running-helper tools/migrate_storage.py --root /legacy --backend mysql import --stopped
docker compose -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python -v "/path/to/stopped-data:/legacy:ro" python-running-helper tools/migrate_storage.py --root /legacy --backend mysql verify

# 只有导入和独立校验均成功后才启动。
docker compose -f docker-compose.yml -f docker-compose.mysql.yml up -d python-running-helper
```

SQLite 容器迁移沿用相同只读源挂载，去掉 MySQL 覆盖文件并改用 `--backend sqlite`；数据库保留在 `./data`。数据库或导出结果不能仅保存在一次性容器可写层。原 `./logs:/app/logs`、Docker 日志轮转及 SSL、上传和图片资源挂载保留；自定义日志仍按原位置挂载。数据库可用性、TLS、账号授权及长期备份由现有外部数据库部署负责。

## 从 v1 MySQL 文档表升级

`--source legacy-mysql` 在 `import/verify` 时只读 v1 文档表。当前 MySQL 连接变量用于来源，目标由 `--backend` 选择；同库 MySQL 目标必须使用不同前缀，不能覆盖旧表。示例先把进程或本地 Compose 中 `MYSQL_TABLE_PREFIX` 改为 `app_v2_`，来源前缀单独指定：

```bash
python tools/migrate_storage.py --root /legacy --backend mysql init
python tools/migrate_storage.py --root /legacy --backend mysql --source legacy-mysql --legacy-table-prefix app_ import --stopped
python tools/migrate_storage.py --root /legacy --backend mysql --source legacy-mysql --legacy-table-prefix app_ verify
```

当前 CLI 没有独立的第二组源连接参数，不能分别指定另一台源服务器；迁入 SQLite 时将目标文件置于源目录之外。`plan` 始终是文件来源预检，不是 v1 数据库清点。

v1 未保存原本地主配置 `configs/config.json` 和信任 IP，单独升级文档表不能代表这些资料已补齐；必须另行核对保留配置及完整范围。整理统一文件迁移源时，要包含 v1 上线后的最新业务内容，不能直接使用陈旧物理快照。不能把资料缺失静默当成成功迁移或默认重建。

## 可复现迁移测试与受控清库

`tools/test_storage_migration.py` 默认使用临时 SQLite，读取副本、导入、幂等重试、独立核验，再导出至新目录并重新导入第二个 SQLite。源目录全部文件的 SHA256、大小和修改时间在前后核对。报告必须是源目录外的全新文件：

```bash
python tools/test_storage_migration.py --source-root /legacy --report /reports/sqlite-migration.json
```

临时 SQLite 测试结束后清理，不代替部署的持久 `init/import/verify`。报告不包含业务正文和凭据，源副本始终只读。

目标 MySQL 显式传 `--backend mysql`。只有已授权清理专用测试库、且确认所有写入进程停止时才使用：

```bash
python tools/test_storage_migration.py --source-root /legacy --backend mysql --reset-target --stopped --backup-dir /backups/mysql --report /reports/mysql-migration.json
```

清库前先完成 SQLite 全量预检、复核源未变，再备份指定库并重新读取备份校验，锁内比对当前数据库与备份后才清理。目标库不符、无有效备份、内容变化或无法完整盘点时拒绝；不删除数据库和账号，不操作其他库。连接凭据仅从进程环境读取。测试连接默认校验 TLS；确有受信任指纹时可显式设置测试工具 `MYSQL_SSL_CERT_SHA256`，不能把首次得到的未知指纹直接视为信任依据。

备份格式 v2 保存 DDL、全部显式列、列元数据、数据和多级摘要，包含 INVISIBLE 列。生成列值参与校验，恢复 INSERT 只写 `writable_columns`。TIMESTAMP 固定 UTC 读取，清单记录时区、SQL mode、客户端字符集和连接排序规则，结束后恢复原会话设置。备份目录必须位于仓库和源目录之外，按敏感业务数据保管。

当前工具仅接受可完整盘点的 InnoDB 基础表及无环库内外键。视图、触发器、例程、事件、非 InnoDB 表、外库引用、外键环或不足权限均明确拒绝，不会漏备后继续清理；需要目标库完整对象可见性及锁表权限。删除时保持外键检查，按子表先于父表执行。MySQL DDL 隐式提交，删除途中失败不能靠事务回滚；应保留已校验备份，停止后续迁移，按清单恢复 DDL、会话语义及可写列数据。当前没有自动恢复命令，备份成功不等于已完成恢复演练。

权限检查接受目标数据库或全局作用域的 `ALL PRIVILEGES`，也接受 MySQL 8.4 将完整数据库级静态权限展开后的等价显式枚举；缺少任一必需权限、仅表级/其他库授权或存在部分撤销时仍拒绝，不因此放宽对象盘点。

## 导出、恢复与验收

导出只写全新目录，校验记录、命名空间、键及路径范围，拒绝路径穿越和白名单外位置，不覆盖旧目录。容器导出必须显式挂载输出目录：

```bash
docker compose -f docker-compose.yml -f docker-compose.mysql.yml stop python-running-helper
docker compose -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python -v "/path/to/exports:/restore" python-running-helper tools/migrate_storage.py --root /app --backend mysql export --stopped --output /restore/campus-data
```

导出包含数据库主配置、信任 IP 和受管业务资料，按当前策略映射目录并保留可用修改时间；不包含日志、图片、上传、缓存和证书。根目录以外的自定义业务目录会被拒绝导出，需先规划可信相对布局。磁盘资源仍需独立备份；导出写盘失败返回非零并保留现场，检查后换全新目录重试。

导出用于备份、交换和再次导入 SQLite/MySQL，**不表示恢复文件运行后端**。上线后旧文件不会同步更新，禁止将陈旧来源与导出合并，避免删除记录复活。恢复目标仍为独立数据库，停写导入和独立核验后再切换连接配置。

数据层报告不代替登录、多账号 UA、会话、支付和任务验收。SQLite 测试不能证明外部 MySQL 联通、权限和部署成功；实际部署须检查独立 `verify`、数据库 ready 状态、日志和关键业务入口。
