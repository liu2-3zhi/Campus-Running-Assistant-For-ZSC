# 数据库优先实施计划

> 此计划为 v2 历史实施记录，当前结构与操作指南见[业务数据库 v3](database-v3.md)。

> 执行方式：superpowers:subagent-driven-development；任务先写失败测试，再实现，再复审。

**Goal:** 冻结文件运行后端，以默认 SQLite 和外部 MySQL 共用的关系化存储替换通用文档运行表，并验证真实副本迁移。

**Architecture:** persistence 提供引擎、领域表、关系化记录编码与事务；旧局部 I/O 仅保留数据库兼容接口。迁移输入与运行存储隔离，日志及图片等资源不变。

**Tech Stack:** Python 3.11、SQLAlchemy Core、SQLite、PyMySQL、pytest。

**Spec:** docs/database-first-design.md

## 全局约束

不提交真实连接参数或数据；指定远端库清空前须完成完整备份与校验；源副本只读；禁止内置 MySQL 容器和 env 文件依赖；日志不移动。

## Task 1：数据库引擎与关系化编码协议

- [x] 新增 persistence 核心、schema、codec 与默认 SQLite 契约测试，先验证模块缺失失败。
- [x] 核心 Store 保持 get/put/delete/list/namespaces/transaction 文档兼容协议，但正文拆解到独立实体表；元表仅保存定位、布局、修订、时间与摘要。
- [x] 核心提供 encode_record、encode_tree、decode_tree 等可复用协议，动态扩展与类型/字段存在性保留，领域模块只声明表及拆解规则。
- [x] 验证创建、CAS、跨表事务、嵌套失败回滚、SQLite 线程连接与外键。

## Task 2：身份与学校账号关系

- [x] 新增 persistence/identity.py 和测试：用户、权限、owner-school 绑定、会话及 Token。
- [x] 先验证同学号不同 owner 的密码/UA 隔离、用户 Token 不绑定会话、会话字段无损重建和权限冲突。
- [x] 使实体列承担筛选/关联语义，兼容层不保存完整原始账号文件正文。

## Task 3：支付、任务、内容与背景

- [x] 新增 persistence/domains.py 和领域测试，覆盖订单/账单/退款/关联、任务、留言/提醒、背景绑定和归档。
- [x] 验证整数分、订单账单关系、动态 JSON 重建、删除归档保留和原日志路径。
- [x] 为核心查询提供按 owner、状态、会话、学校账号的 SQL 索引。

## Task 4：运行接入与默认行为

- [x] 修改 business_storage.py 配置与运行工厂，默认 SQLite，显式拒绝 file 后端。
- [x] storage_io 同时支持 SQLite/MySQL 的关系化 Store；config_adapter 不经磁盘临时文件保存数据库配置。
- [x] 接入启动旧数据检测、初始化、容器 SSL 读取与信任 IP 设置，保留所有资源与日志路径。
- [x] Compose 直接配置环境变量，删除 mysql.env.example；更新测试、使用说明和 agent.md。

## Task 5：迁移与真实数据验收

- [x] 更新 tools/migrate_storage.py 与迁移模块，显式文件/旧数据库来源、SQLite/MySQL 目标、只读源及完整校验。
- [x] 创建可重复的真实副本迁移测试入口，连接凭据只来自进程环境或输入流；先在 SQLite 完成语义往返。
- [ ] 完整备份和校验指定远端库；新实现就绪后按用户授权清空库内对象，执行迁移、独立核验和报告。
- [x] 全量回归与独立代码复审，修复实质问题，验证工作区后中文本地提交，不推送。

## 接口复核与执行裁决

| 任务对 | 共享边界 | 约束 |
|---|---|---|
| 1 / 2 | 核心 codec 与 schema 注册 | identity 只修改领域模块和对应测试，核心统一注册 |
| 1 / 3 | 核心 codec 与 schema 注册 | domains 只修改领域模块和对应测试，不复制完整文档表 |
| 1 / 4 | Store get/put 协议 | SQLite/MySQL 共用，同一套 CAS/事务语义 |
| 2 / 3 | 用户、学校账号引用 | UA 归 owner 绑定，账单归学校账号，禁止错误级联 |
| 4 / 5 | runtime 与 migration | 运行期不自动导入；离线工具允许指定只读源根目录 |

Ruling: 使用当前用户指定的仓库就地实施，不另建工作树，保持用户可直接检查已有工作区。

Ruling: 用户补充了迁移测试和清空指定 MySQL 库的明确要求，执行该测试授权；备份完成前及程序验证前不做清空。

## 远端执行检查点

指定远端库目前只读确认仍为 v1 两张 InnoDB 表。完整备份在清点 routines 时遇到服务器错误 1558：系统表版本与服务器版本不匹配，需要数据库管理员完成 mariadb-upgrade。备份保护按设计拒绝继续，尚未对指定远端库执行清表、建表或写入业务记录。管理员修复之前，不得以跳过对象清点或只备份部分表的方式绕过该保护。SQLite 及隔离 MySQL 验证继续独立进行；此远端检查项不得提前标为完成。

## Final verification

Python: 2317 passed, 3 skipped; JavaScript: 638 passed. Real isolated MySQL 8.4 completed full-copy import, verified backup, reset of 41 tables, re-import and export/SQLite round-trip with zero differences. Source inventory remained unchanged. Independent review findings were fixed and rechecked. The authorized remote reset remains blocked by server error 1558 during full object inventory; no remote tables or business records were changed.
