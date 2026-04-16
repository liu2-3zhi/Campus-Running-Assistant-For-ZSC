# 支付 `app_host` 随机 API 探针校验设计

## 背景与目标

当前支付链路里，`app_host` 与部分回跳逻辑曾依赖“服务器公网 IP 自检”来判断“这是不是本站”。这个做法在前置 CDN、反向代理、多层转发场景下不稳定，已经出现：

1. 外部 IP 获取失败导致校验链路误拒绝；
2. 站点前置 CDN 时，“外部可访问地址”与“源站公网 IP”不再等价；
3. 固定校验接口路径容易形成长期存在的静态验证入口。

本次目标是把支付站点验证收敛为**唯一的一套动态校验链路**：

- 只采用“随机路径 + 随机文本”探针校验；
- 探针路径必须以 `/api` 开头，降低 CDN / 浏览器缓存影响；
- 不再以公网 IP 作为支付 `app_host` 验证主依据；
- `return_url` 与 `app_host` 的职责拆开：
  - `app_host` 负责“本站证明”；
  - `return_url` 只负责“禁止跨站跳转”；
- 删除旧的固定 challenge 主流程，统一为一次性随机探针。

---

## 已确认约束

1. 主机前面可能套 CDN。
2. 主校验方式只采用：**随机路径 + 随机文本**。
3. 随机路径必须走 **`/api/...`** 前缀，防止缓存。
4. `return_url` 允许**本站任意路径**，但不允许跨站跳转。
5. 本次设计**不把公网 IP 获取接口接入支付主校验链路**。

---

## 范围与非范围

### In Scope

1. 改造 `/api/payment/verify_host` 的内部验证逻辑。
2. 新增一次性随机 probe 校验机制。
3. 新增 `/api/payment/verify_probe/<token>` 模式路由。
4. 改造 `IPVerifier.check_app_host()`，切换到新 probe 机制。
5. 调整 `create_order()` 中 `app_host` / `return_url` 相关校验。
6. 清理旧固定 challenge 主流程及其依赖状态。
7. 增加后端回归测试。

### Out of Scope

1. 不新增基于公网 IP 的新主链路。
2. 不把 `https://openapi.lddgo.net/base/gtool/api/v1/GetIp` 接入本次支付主验证流程。
3. 不改动第三方支付平台协议。
4. 不新增独立管理后台配置项来切换多种校验模式。

---

## 核心设计决策

### 1) 本站验证只靠一次性随机 probe

`app_host` 是否是本站，不再通过“公网 IP 是否相同”判断，而是通过：

1. 服务端生成一次性随机 token；
2. 服务端生成一次性随机 challenge 文本；
3. 服务端将 probe 暂存到当前进程内存；
4. 服务端主动请求 `{app_host}/api/payment/verify_probe/<token>`；
5. 只有当前进程中对应 probe 被正确消费，才算验证成功。

### 2) 随机 URL 通过 token 路径段实现

不在运行时动态注册大量 Flask 路由，而是保留一个模式路由：

`/api/payment/verify_probe/<token>`

这样从外部看仍然是随机 URL；从实现上则更稳定、可测试。

### 3) 不信任远端 JSON，必须校验本机消费状态

不能仅凭远端返回 `{"success": true}` 就认定成功。因为如果 `app_host` 指向其他服务，对方也可以伪造成功响应。

因此 `check_app_host()` 返回成功必须同时满足：

- 远端 HTTP 响应成功；
- 本机内存中的 probe 已被对应 token 正确消费。

只有这样才能证明请求真的回到了当前进程。

### 4) `return_url` 与 `app_host` 解耦

- `app_host`：负责“本站证明”，只走随机 probe。
- `return_url`：不再走 `is_allowed_ip()`；只校验是否是本站 URL。

`return_url` 规则：

- 允许本站任意路径和查询参数；
- 拒绝跨站 URL；
- 不再参与“本机证明”。

### 5) 不保留双轨逻辑

本次直接收敛为唯一主链路，不再长期保留：

- 固定 `/api/payment/verify_challenge` 主流程；
- `payment_verify_challenge_get` 全局变量；
- 支付验证对公网 IP 查询结果的依赖；
- `PAYMENT_APP_HOST_SELF_CHECK_ENABLED` 这类临时双轨开关。

---

## Probe 数据模型

内存中的 probe 至少包含以下字段：

```python
{
    "token": str,
    "challenge": str,
    "created_at": float,
    "expires_at": float,
    "consumed": bool,
}
```

设计约束：

- `token`：高熵随机字符串，用于构成随机 `/api/...` 路径；
- `challenge`：独立于 token 的随机文本，用于正文校验；
- `expires_at`：短 TTL；
- `consumed`：只允许成功消费一次。

TTL 明确设为：**15 秒**。

---

## API 设计

### 1) 保留固定外层入口：`/api/payment/verify_host`

职责不变：接收前端提交的 `app_host`。

职责调整为：

- 生成随机 probe；
- 发起一次性验证请求；
- 返回验证结果。

前端调用入口保持兼容，不要求前端改路由。

### 2) 新增随机 probe 模式路由：`/api/payment/verify_probe/<token>`

约束：

- 只接受 `POST`；
- 请求体必须包含 challenge 文本；
- 校验 token 是否存在、未过期、未消费；
- 校验 challenge 是否完全一致；
- 成功后立即标记 probe 为已消费。

成功响应：

```json
{"success": true}
```

失败响应原则：

- 对无效 token、已过期、已消费、challenge 不匹配等情况返回模糊失败；
- 不回显完整 token 或 challenge；
- 不提供可用于枚举或重放的细节。

### 3) 防缓存响应头

probe 路由固定返回：

```http
Cache-Control: no-store, no-cache, must-revalidate, max-age=0
Pragma: no-cache
Expires: 0
```

再叠加：

- `/api/...` 前缀；
- `POST` 方法；
- 一次性 token。

共同降低缓存命中风险。

---

## `check_app_host()` 新流程

`IPVerifier.check_app_host(client_app_host)` 改造后流程如下：

1. 解析并标准化 `client_app_host`；
2. 若 URL 无法构造，直接失败；
3. 创建一次性 probe：生成 token + challenge，并登记到内存；
4. 拼出目标 URL：
   - `{base_url}/api/payment/verify_probe/<token>`
5. 以 `POST` 方式请求目标 URL，请求体中发送 challenge；
6. 校验 HTTP 状态与 JSON 基本格式；
7. 额外检查：本机 probe 是否已被成功消费；
8. 若任一条件不满足，则失败；
9. 成功或失败后都进行惰性清理。

建议超时：**5 秒**。

---

## `return_url` 新规则

`return_url` 不再调用 `is_allowed_ip()`。

改为：

1. 若为空，维持现有默认回退逻辑；
2. 若非空，必须是完整 URL；
3. 仅允许与当前站点同源；
4. 同源下允许任意路径和查询参数；
5. 跨站地址直接拒绝，不再静默放行。

这里的“当前站点”以当前请求头推导出的外部站点语义为准，而不是源站公网 IP。

---

## 失败分支与安全边界

以下情况一律视为验证失败：

1. `app_host` 无法解析或 URL 无法构造；
2. 请求超时；
3. 连接失败；
4. 返回非 200；
5. JSON 格式错误；
6. token 不存在；
7. token 已过期；
8. token 已消费；
9. challenge 不匹配；
10. 远端虽然返回成功，但本机 probe 未被消费。

为了降低暴露面：

- 日志中不打印完整 challenge；
- token 仅打印截断前缀；
- probe 路由对失败原因尽量模糊化；
- probe 成功后立即失效，防止重放。

---

## 清理策略

不新增后台清理线程。

采用惰性清理：

- 创建 probe 前先清理过期 probe；
- 消费 probe 后再次清理；
- `verify_host` 请求完成后再次清理。

理由：

- probe TTL 很短；
- 读写频率只在支付验证发生时出现；
- 惰性清理足够简单，不引入额外线程复杂度。

---

## 受影响代码（已核对位置）

主要落点集中在以下区域：

- `main.py:1081-1207`：`IPVerifier.check_app_host()`
- `main.py:41071-41072`：`return_url` 旧 IP 判断链路
- `main.py:5792-5951`：`RainbowYiPay.create_order()` 中 `app_host` / `return_url` 逻辑
- `main.py:43397-43552`：`/api/payment/verify_host`
- `main.py:43554-43627`：旧固定 challenge 路由（将退出主流程）
- `scripts/main.new.js:56653-56695`：前端仍调用 `/api/payment/verify_host`，入口保持兼容

---

## 实现建议（函数级）

建议在 `main.py` 新增或收敛以下内部 helper：

1. `_create_payment_verify_probe()`
2. `_consume_payment_verify_probe()`
3. `_cleanup_expired_payment_verify_probes()`
4. `_is_payment_verify_probe_consumed()`
5. `_build_payment_verify_probe_url(base_url, token)`
6. `_is_same_origin_return_url(url)` 或等价 helper

这样可把：

- probe 生命周期管理；
- URL 构建；
- `return_url` 校验

从支付业务主体里拆出来，便于测试与复用。

---

## 测试计划

### 1) Probe 机制单元测试

覆盖：

1. 创建 probe 成功；
2. 正确 challenge 可消费；
3. 错误 challenge 拒绝；
4. 已过期 probe 拒绝；
5. 已消费 probe 重放失败；
6. 惰性清理能移除过期项。

### 2) Probe 路由测试

覆盖：

1. 路由模式为 `/api/payment/verify_probe/<token>`；
2. 仅接受 `POST`；
3. 成功响应带 no-cache 头；
4. 成功后 probe 被标记为已消费；
5. 无效 token / 过期 / challenge 错误均失败。

### 3) `check_app_host()` 主链路测试

覆盖：

1. 生成的目标 URL 确实是随机 `/api/...` 路径；
2. 请求体确实带随机文本；
3. 只有“远端响应成功 + 本机 probe 已消费”才返回成功；
4. 请求超时返回失败；
5. 连接失败返回失败；
6. 伪造 `{"success": true}` 但未消费本机 probe 时仍失败。

### 4) 支付链路回归测试

覆盖：

1. `/api/payment/verify_host` 走新 probe 逻辑；
2. `create_order()` 不再依赖旧公网 IP 自检链路；
3. `return_url` 不再调用 `is_allowed_ip()`；
4. 同站 `return_url` 允许任意路径；
5. 跨站 `return_url` 被拒绝；
6. 旧 `/api/payment/verify_challenge` 不再是主流程入口。

---

## 实施顺序

建议按以下顺序落地，降低风险：

1. 引入 probe 内存管理 helper；
2. 新增 `/api/payment/verify_probe/<token>` 路由；
3. 改造 `IPVerifier.check_app_host()` 切到新链路；
4. 改造 `/api/payment/verify_host`；
5. 改造 `create_order()` 中 `return_url` 规则；
6. 删除旧固定 challenge 主流程与冗余全局状态；
7. 补充回归测试并跑验证。

---

## 风险与缓解

### 风险 1：误把远端成功响应当作本站证明

缓解：成功条件必须包含“本机 probe 已消费”。

### 风险 2：token / challenge 泄露导致重放

缓解：短 TTL、一次性消费、日志脱敏、成功即失效。

### 风险 3：CDN / 代理缓存干扰验证

缓解：`/api` 前缀、`POST` 方法、no-store 响应头、随机 token URL。

### 风险 4：`return_url` 与 `app_host` 逻辑纠缠

缓解：明确职责拆分：
- `app_host` = 本站证明
- `return_url` = 仅防跨站跳转

---

## 最终结论

本次支付站点验证收敛为：

> `app_host` 是否本站，只靠“一次性随机 `/api` 探针 + 随机 challenge 文本 + 本机内存消费成功”来证明。

这条链路能够适应 CDN / 反代环境，避免公网 IP 误判，并移除固定 challenge 主流程带来的长期静态验证入口。