# /health 分级监控增强设计（token-only + 全面覆盖）

## 背景与目标

当前 `/health` 已返回基础运行指标，但缺少：

1. 组件重要性驱动的 `ok / degraded / error` 聚合。
2. 基于访问身份的分级可见性（公开简版、管理员详版）。
3. 兼容 JSON 的中文说明字段。

本次目标：在保持 `/health` 公开可访问前提下，增强为可观测优先端点：

- 核心组件异常 => `status=error`，HTTP `503`。
- 非核心组件异常 => `status=degraded`，HTTP `200`。
- 非管理员只看简版；管理员可看组件级详版。

---

## 关键代码现状（已核对）

基于 `main.py` 已有实现，确认以下事实：

1. `/health` 当前是公开端点，未走 `login_required/admin_required`。
2. 现有 `/health` 已读取：`web_sessions`、`background_task_manager.tasks`、`chrome_pool._contexts`、`CDN_FILES/js_cache_storage`。
3. `TokenManager.verify_token(username, session_id, token)` 的实现中 **实际只校验 token 文件值与过期时间**，`session_id` 参数未参与判断逻辑。
4. URL 场景下 `X-Session-ID` 不稳定，不能作为 `/health` 身份判定前提。

因此本设计改为：`/health` 的管理员视图判定 **只依赖 `auth_token` cookie**（token-only）。

---

## 范围与非范围

### 范围

- 改造 `main.py` 中 `@app.route("/health")`。
- 新增组件级健康检查与状态聚合。
- 新增基于 `auth_token` 的管理员视图判定与响应裁剪。
- 在 JSON 中增加中文说明字段（非注释语法）。
- 增加后端测试覆盖分级状态与可见性策略。

### 非范围

- 不新增 `/health/admin` 路由。
- 不改动现有业务接口鉴权体系。
- 不接入 Prometheus / OpenTelemetry 等外部监控系统。
- 不重构 TokenManager 与用户权限系统。

---

## 关键设计决策

### 1) 单端点 + 分级输出

保留 `/health` 单端点：

- 先执行统一组件检查。
- 再根据 token-only 身份结果返回简版或详版字段。

### 2) 组件重要性驱动状态

- **核心组件**：`running_core`（跑步执行主链路）
- **非核心组件**：`payment_system`、`sms_system`

聚合规则：

- 任一核心组件 `error` => 总体 `error` + HTTP 503
- 无核心 `error` 且存在非核心 `degraded/error` => 总体 `degraded` + HTTP 200
- 全部正常 => 总体 `ok` + HTTP 200

### 3) token-only 管理员识别

新增内部函数 `_is_admin_health_view_from_token()`：

1. 从 cookie 读取 `auth_token`。
2. 若 token 缺失：直接按非管理员处理。
3. 若 token 存在：通过 `_resolve_username_by_token(token)` 反查用户名：
   - 遍历用户集合（来源于 `auth_system.list_users()` 或等价可用用户源）。
   - 对每个用户读取该用户 token 文件并比对 token 且检查过期。
4. 反查成功后，调用 `auth_system.get_user_group(username)`。
5. `group in {admin, super_admin}` 才返回详版；其余全部简版。

异常策略：任一步异常都降级为简版（最小暴露原则）。

### 4) JSON 可读性字段

- 简版：`_comment`
- 详版：`_meta_zh`

不使用非标准 JSON 注释语法，确保监控系统可解析。

---

## 响应结构设计

### 非管理员（未登录/普通用户/无效token）简版

固定返回：

- `status`
- `uptime_seconds`
- `response_time_ms`
- `uptime_formatted`
- `_comment`

不返回组件明细与内部诊断。

### 管理员详版

在简版基础上增加：

- `components`
  - `running_core`
  - `payment_system`
  - `sms_system`
- `summary`
  - `critical_failed_count`
  - `non_critical_failed_count`
- `_meta_zh`

### 组件对象统一结构

每个组件至少包含：

- `name`
- `critical`
- `status`（`ok/degraded/error`）
- `message`
- `checks`（子检查项明细，管理员详版展示）

---

## 监控覆盖矩阵（全面覆盖）

### A. running_core（核心）

> 目标：覆盖“跑步执行链路”关键依赖，避免只看单一计数。

1. 任务执行器可用性（`background_task_manager`）
   - 检查对象存在、`tasks` 可读、锁可用。
   - 失败 => `error`。

2. 运行任务状态一致性（`background_task_manager.tasks`）
   - 统计 `status=running` 任务数。
   - 若存在 running 任务但任务状态结构异常（缺少关键字段如 `last_update`）=> `error`。
   - 若 running 任务长期无更新时间（例如超过阈值）=> `degraded`（疑似卡住）。

3. 浏览器执行上下文可用性（`chrome_pool._contexts`）
   - 检查 `chrome_pool` 存在且 `_contexts` 可读取。
   - 若 running 任务>0 且 contexts 明显不可用 => `error`。
   - 无运行任务时 contexts=0 可接受（`ok`）。

4. 会话运行态可见性（`web_sessions`）
   - 检查 `web_sessions` 可读与类型正确。
   - 若结构异常（非字典）=> 直接判定核心 `error`（会话层已不可观测）。

### B. payment_system（非核心）

> 目标：支付链路异常不阻断健康端点，但能显式降级。

1. 配置读取可用性
   - `Rainbow_YiPay` 节可读取。
   - `payment_timeout_minutes` 可解析且 >0。

2. 支付开关语义一致性
   - 当 `Payment_Settings.require_payment=true` 时，关键支付参数缺失（如 `host/pid/key`）=> `degraded`。
   - 当 `require_payment=false` 时，支付配置缺失仅记录信息，不降级。

3. 支付缓存/订单目录可达性（轻量检查）
   - 本地目录可达性检查（`PAYMENT_ORDERS_DIR`）。
   - 二维码缓存索引可读性检查（`_load_qr_cache_index`）。
   - 索引损坏或读取失败 => `degraded`（不阻断整体服务）。

### C. sms_system（非核心）

> 目标：短信功能可用性监控，不对公网发短信。

1. 短信总开关
   - `Features.enable_sms_service=false` => 标记 `ok`（已禁用，不视为故障）。

2. 短信配置完整性（启用时）
   - 启用短信时，`SMS_Service_SMSBao` 基础参数缺失（如 `username/api_key/signature/template_register`）=> `degraded`。

3. 本地验证码存储与速率参数可用性
   - 检查验证码缓存结构可访问。
   - 检查 `send_interval_seconds`、`code_expire_minutes` 可解析且 > 0。
   - 速率或时效参数无效 => `degraded`。

---

## 实现策略（函数级）

在 `/health` 附近新增内部函数：

1. `_check_running_core_health()`
2. `_check_payment_system_health()`
3. `_check_sms_system_health()`
4. `_aggregate_health_status(components)`
5. `_resolve_username_by_token(token)`
6. `_is_admin_health_view_from_token()`
7. `_build_health_comment_fields(is_admin)`

约束：

- 单个组件检查异常只影响该组件，不中断整体 `/health`。
- `/health` 始终返回结构化 JSON（极端进程级故障除外）。

---

## 错误处理与回退

- 组件检查异常：
  - 捕获异常并落到该组件 `message/checks`。
  - 根据组件 `critical` 参与聚合。
- token 解析异常：
  - 一律降级简版。
- 中文说明字段构建异常：
  - 不影响核心字段返回。

---

## 安全与信息暴露控制

- 非管理员响应不包含组件明细、内部计数、检查细项。
- 管理员详版不返回敏感值原文（如 API key、token、密钥）。
- token-only 仅用于“是否展示详版”，不改变业务接口鉴权边界。

---

## 测试设计

新增/扩展测试覆盖：

1. 无 token 访问 `/health`：仅简版字段。
2. token 无效访问 `/health`：仅简版字段。
3. 普通用户 token 访问 `/health`：仅简版字段。
4. 管理员 token 访问 `/health`：返回详版字段（`components/summary/_meta_zh`）。
5. 仅非核心组件失败：`status=degraded` 且 HTTP 200。
6. 核心组件失败：`status=error` 且 HTTP 503。
7. 全部正常：`status=ok` 且 HTTP 200。
9. `web_sessions` 结构异常：`running_core=error` 且 HTTP 503。
10. 支付二维码缓存索引异常：`payment_system=degraded` 且总体遵循聚合规则。
11. 短信速率/验证码时效配置无效：`sms_system=degraded` 且总体遵循聚合规则。

---

## 兼容性与发布影响

- `/health` URL 不变。
- 非管理员调用方读取基础字段行为保持兼容。
- 管理员新增字段为增量，不影响旧消费者。

---

## 实施顺序

1. 重构组件检查与聚合函数。
2. 接入 token-only 管理员判定与响应裁剪。
3. 增加 `_comment / _meta_zh`。
4. 完成测试并验证状态码与字段契约。
