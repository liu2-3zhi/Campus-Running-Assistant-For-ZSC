# MySQL 数据存储与迁移

应用默认仍使用文件存储。启用 MySQL 后，受管的结构化业务文件由数据库保存，原文件保留作为迁移前快照。日志继续使用现有目录、文件名、写入方式与归档机制。此功能不自动迁移数据，也不会在数据库断线时回退写入旧文件。

## 范围与限制

迁移范围由应用和工具共用的 `StoragePolicy` 决定，包括系统账号、学校账号 JSON/INI、权限、会话、Token、后台任务、订单、账单、留言、提醒、删除账号备份，以及策略允许的其他结构化配置。索引文件原样保存，不重新计算 Token 或重建账号身份。

以下内容继续保留在磁盘，不进入迁移或导出：

- 整棵默认或自定义日志目录，包括 JSON/JSONL、支付日志、审计日志和归档。
- 本地引导配置 `configs/config.json`。其中的目录配置用于确定迁移范围，文件本身不存入数据库。
- 图片、上传文件、地图及其他缓存、SSL 证书和私钥。
- 未被策略明确允许的其他文件。

本版本仍按**单个应用实例**运行。启用 MySQL 不会把进程内的任务执行锁、账号锁和账单锁自动变成分布式锁；不要据此启动多个应用副本同时操作同一数据库。

数据库需要预先创建；应用不会创建数据库或数据库账号。准备专用账号，使用 UTF-8/utf8mb4 数据库，并为迁移初始化授予建表权限、为运行期授予相应表的读写权限。安装依赖使用 `python -m pip install -r ssl/requirements.txt`。

## 配置

连接信息来自环境变量，不写入前端配置或迁移输出。示例中的密码为占位符，部署时使用实际环境变量或部署系统的 secret。

```dotenv
# 不配置时仍为 file。迁移前保持 file，核验完成后再改成 mysql。
APP_STORAGE_BACKEND=file
APP_STORAGE_ROOT=/app

MYSQL_HOST=database.example.com
MYSQL_PORT=3306
MYSQL_USER=campus_app
MYSQL_PASSWORD=replace-with-your-own-password
MYSQL_DATABASE=campus_running
MYSQL_TABLE_PREFIX=app_
MYSQL_CONNECT_TIMEOUT=5
MYSQL_READ_TIMEOUT=15
MYSQL_WRITE_TIMEOUT=15
# 远端 MySQL 配置受信任 CA 时启用；未使用时不设置此变量。
# MYSQL_SSL_CA=/run/secrets/mysql-ca.pem
```

MySQL 必需配置为 `MYSQL_USER`、`MYSQL_DATABASE` 及实际连接所需凭据。`MYSQL_HOST`、端口、超时和表前缀可覆盖默认值；`MYSQL_TABLE_PREFIX` 只允许以字母开头的字母、数字和下划线。配置 `MYSQL_SSL_CA` 时，路径指向应用/迁移进程可读的 CA 文件。不要把生产连接密码放入 Git、命令参数、测试样本或问题截图。

首版运行期要求 `APP_STORAGE_ROOT` 与实际应用代码根目录一致，例如容器内为 `/app`；应用中仍有按模块 `__file__` 构造的路径，不能仅改变此变量或当前工作目录来重定向运行数据。运行时还须在应用代码根目录启动；设置不同运行根目录或工作目录会显式拒绝启动，避免出现一部分写数据库、一部分写磁盘的混合状态。

离线迁移 CLI 的 `--root` 允许任意可信的源数据目录，优先于 `APP_STORAGE_ROOT`，缺省为项目目录。它不启动应用，也不受上述运行根目录限制。工具从源根目录的 `configs/config.json` 读取 `System` 的学校账号、系统账号、会话及 Token 自定义目录，以及 `Logging.log_dir`；默认日志目录始终排除。

`init/import/verify/export` 命令显式连接 MySQL，即使当前 `APP_STORAGE_BACKEND=file`，也不会修改该环境变量或应用配置。`plan` 不要求 MySQL 连接信息，不建立数据库连接。

## 停服迁移

先备份当前数据、引导配置、图片/上传等磁盘资源。备份应位于业务根目录之外。停止应用及所有可能修改业务数据的进程，保留 MySQL 服务运行。迁移工具不会代替用户停止进程；`--stopped` 表示你已完成停写确认。

在已设置上述 `MYSQL_*` 环境变量的终端中执行：

```bash
# 1. 查看允许范围、数量、字节数并校验全部源文件；不连接 MySQL。
python tools/migrate_storage.py --root /app plan

# 2. 显式创建/检查所需数据表；此命令不导入文件、不标记迁移完成。
python tools/migrate_storage.py --root /app init

# 3. 导入并校验全部记录。原文件不改动；默认遇到不同内容即中止。
python tools/migrate_storage.py --root /app import --stopped

# 4. 独立核对受管文件与数据库的记录数量及 SHA256。
python tools/migrate_storage.py --root /app verify
```

Windows 原生部署将 `/app` 换成自己的项目或数据根目录；工具可从任意工作目录通过脚本绝对路径调用。Docker 部署在应用停止后，用相同镜像、原持久化挂载及相同 `MYSQL_*` 环境运行一次性迁移容器，并将命令入口覆盖为 `python`；不要同时启动原应用进程。

确认 `import` 和 `verify` 都以退出码 0 结束后，将应用环境中的 `APP_STORAGE_BACKEND` 改为 `mysql`，再启动应用。保留原有日志目录和磁盘资源挂载。MySQL 未初始化、未完成迁移或连接失败时，应用应报告错误；不要通过清空数据库、自动创建默认数据或写回旧文件掩盖错误。

工具只输出操作、记录数、字节数、冲突/校验数量及错误类型，不打印密码、Token、连接 DSN 或记录正文。退出码 0 表示命令成功；`verify` 不一致返回 1；配置、格式、冲突或运行错误返回 2。

## Docker Compose 覆盖配置

新增 run/docker-compose.mysql.yml 是可选覆盖文件；原 run/docker-compose.yml 保持不变。覆盖文件仅给应用传入外部 MySQL 的主机、端口和连接凭据，不内置数据库服务、数据库卷、专用网络或启动依赖。请事先准备可从应用容器访问的外部 MySQL 实例及专用数据库账号。

以下示例从 `run` 目录执行。先确认使用的应用镜像包含本次数据库和迁移工具代码；旧镜像不会因增加覆盖文件而自动获得新功能。

```bash
cd run
cp mysql.env.example mysql.env
# 编辑 mysql.env，设置外部 MYSQL_HOST/PORT 和应用账号凭据。不要将 mysql.env 加入 Git。
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml config --quiet

# 停止已有应用，保留原数据和日志挂载。此时不启动应用服务。
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml stop python-running-helper
# 按顺序执行一次性工具容器；--no-deps 避免附带启动应用进程。
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python python-running-helper tools/migrate_storage.py --root /app plan
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python python-running-helper tools/migrate_storage.py --root /app init
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python python-running-helper tools/migrate_storage.py --root /app import --stopped
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python python-running-helper tools/migrate_storage.py --root /app verify

# 只有导入和独立校验均成功后，才启动应用。
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml up -d python-running-helper
```

覆盖配置不会替换或移动原日志挂载 `./logs:/app/logs`，也不改变应用的 Docker 日志轮转设置。配置文件里的自定义日志路径继续按原部署挂载；数据库只保存允许的业务文件。

外部 MySQL 的创建、备份、账号授权、TLS 和可用性由现有数据库部署负责；此覆盖文件不负责安装或启动数据库。MYSQL_HOST 必须是应用容器可达的地址，不能用容器内的 localhost 指代宿主机数据库。迁移工具会实际检查连接，数据库不可用时不会启动文件回退。

导出容器必须显式挂载恢复目录，否则一次性容器删除后导出文件也会丢失。例如先停应用，再执行：

```bash
docker compose --env-file mysql.env -f docker-compose.yml -f docker-compose.mysql.yml run --rm --no-deps --entrypoint python -v "$PWD/mysql-export:/restore" python-running-helper tools/migrate_storage.py --root /app export --stopped --output /restore/campus-data
```

## 空文件、冲突与恢复

导入前先验证全部 JSON/INI。JSON 需要有效 UTF-8（可带 BOM），不接受 NaN 等非标准数值；INI 按无插值、兼容重复选项的解析器验证。原始字节原样存储，不统一重排 JSON、不重新编码密码和 Token。

空文件或只有空白的文件默认拒绝，避免把损坏数据当默认配置。若确认这些是部署预创建的占位文件，可显式跳过：

```bash
python tools/migrate_storage.py --root /app plan --skip-empty
python tools/migrate_storage.py --root /app import --stopped --skip-empty
python tools/migrate_storage.py --root /app verify --skip-empty
```

跳过数量会显示在输出中。这不会把空文件导入数据库，也不会修改源文件。若源文件应包含真实数据，应从备份恢复，不能用 `--skip-empty` 掩盖数据损坏。

默认 `--conflict error` 在写入前发现目标同标识不同内容即中止。同标识且内容 SHA256 相同的记录幂等跳过，重复运行不会无谓增加修订号。`--conflict overwrite` 显式使用文件内容覆盖不同的数据库记录；已有修订号参与并发冲突检查。`--conflict skip` 保留冲突记录，但最终只要与源文件不同，校验仍失败，不会把不一致视为迁移成功。

`--batch-size` 默认为 100。每批在事务中写入，一批失败则回滚该批；前面已提交批次保留。修复问题后使用相同目录、数据库及参数重新执行导入，已一致记录自动跳过。迁移结束前会重新读取源文件并核对数据库，源数据变化、数据库缺失、多余或内容不同时均拒绝标记就绪。不要在导入过程中重新启动应用。

```bash
python tools/migrate_storage.py --root /app import --stopped --batch-size 100 --conflict overwrite
```

数据库多余记录不会被迁移工具自动删除。应先确认是否选错数据库、根目录或旧实例；需要删除时由操作人员备份并明确处理，然后重新核验。

## 导出与回退

MySQL 上线后，原文件不会持续更新。回退必须先停止应用，将数据库中的最新数据导出到**全新目录**，不能直接切回迁移前的旧文件。导出会验证命名空间、文档键和 SHA256，拒绝绝对键、`..`、反斜线、盘符和受管范围外路径；不覆盖已有目标目录。

```bash
python tools/migrate_storage.py --root /app export --stopped --output /restore/campus-data
```

导出保留原始字节及修改时间。目录布局按当前本地策略映射，包括位于 root 内的自定义账号/会话目录。若自定义业务目录位于 root 之外，当前版本明确拒绝导出；先规划统一根目录，不能丢失外部目录布局或把数据库键直接当系统路径写入。

导出不携带 `configs/config.json`、日志、图片、上传和证书。将对应的本地引导配置和磁盘资源从可信备份单独放回恢复目录；自定义目录部署必须保留相同的相对布局。离线核验或再次导入时，可将导出目录作为新的 `--root` 执行 `plan/import/verify`。

恢复文件模式时，先备份现有文件，再将导出内容恢复到干净的受管数据目录或对应容器挂载，不能直接与迁移前的 JSON/INI 合并，否则数据库中已经删除的旧记录会重新出现。混合目录中的图片和日志须按原位置单独保留。设置 APP_STORAGE_BACKEND=file 后按原部署方式启动；日志挂载和位置保持原配置，不随数据导出移动。

导出写盘失败会返回非零并保留目标目录现场，不会宣称成功；检查后选择另一个全新目录重试。恢复之前先完成文件备份与摘要核验。受控单元测试不能代替本机数据库联通、实际账号和业务流程的部署验收。

## 本轮验证记录

- 完整 Python 回归（启用隔离真实 MySQL 集成）：2059 项通过、3 项跳过；JavaScript 回归：638 项通过。Python 仅出现现有 Eventlet 弃用警告。
- MySQL 存储、I/O、迁移和真实业务入口专项：95 项通过；另有外部 MySQL Compose 合并配置检查通过。
- 迁移单元与 CLI 测试：32 项通过，使用临时目录、MemoryStore 和真实 StoragePolicy；包括 Windows 旧编码环境下 UTF-8 帮助输出。
- 使用隔离的真实 MySQL 8.4 测试库和临时数据运行 CLI：`plan → init → import → verify → export` 成功，导出数据重新导入第二个独立表前缀后再次校验成功。
- 六条测试记录包含自定义账号目录、INI、中文 JSON、系统账号索引、Token 和 Token 索引；原始字节与修改时间保持不变，默认/自定义日志及引导配置未进入数据库或导出目录。
- 重复导入六条记录全部幂等跳过；数据库多出一条记录时 `verify` 返回退出码 1。真实事务中注入第二批写入失败，验证当前批回滚、前批保留、就绪标志仍关闭；重试后成功补完。
- `docker compose --env-file mysql.env.example -f docker-compose.yml -f docker-compose.mysql.yml config` 验证通过。已确认合并后只有应用服务，没有内置 MySQL 服务、数据库卷或额外网络，且原应用全部挂载和日志配置不变；没有启动真实部署服务。

以上数据库测试只使用隔离临时样本和独立测试表，结束后删除本轮测试表；未迁移当前项目的真实业务数据，未证明真实账号登录、支付、签到或跑步流程的线上验收结果。
