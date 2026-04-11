# 账单订单超时关闭与二维码复用设计

## 背景与目标

当前账单支付流程存在两个问题：

1. 订单创建后若长期未支付，缺少统一的超时关闭机制（`pending` 长期悬挂）。
2. 同一账单项在短时间内重复发起同渠道支付，会重复向支付平台创建订单，增加重复支付风险。

本设计目标：

- 引入订单生命周期状态机：`pending` / `paid` / `closed` / `refunded_partial` / `refunded_full`。
- 使用 `Rainbow_YiPay.payment_timeout_minutes` 作为统一超时变量，控制：
  - 待支付订单超时转 `closed`
  - 二维码缓存复用有效期
- 防止重复支付：对“同学号 + 同账单项 + 同渠道”在有效期内复用同一二维码。
- 兼容异步通知：即使订单已 `closed`，收到支付成功通知后仍必须转为 `paid`。

---

## 范围

### In Scope

1. 支付订单状态扩展与状态迁移。
2. 账单项发起支付时的二维码缓存与复用。
3. 管理端配置项文案与行为统一（复用现有 `payment_timeout_minutes`）。
4. 异步支付成功、退款通知对订单状态的幂等更新。
5. 前端账单状态展示扩展。

### Out of Scope

1. 新增独立支付超时配置项（不新增，复用现有项）。
2. 变更第三方支付平台协议。
3. 历史旧订单一次性离线迁移脚本（运行时按读取兼容补默认）。

---

## 术语与关键键

- 学号：`school_id`
- 账单项标识：`billing_id`（来源于 `User_Billing/School_Bills/<school_id>/<billing_id>.json`）
- 支付渠道：`pay_type`（如 `wxpay`、`alipay`）
- 二维码缓存键：`{school_id}:{billing_id}:{pay_type}`

---

## 状态机设计

### 状态枚举

- `pending`：待支付
- `paid`：已支付
- `closed`：已关闭（超时关闭）
- `refunded_partial`：部分退款
- `refunded_full`：全额退款

### 迁移规则

1. `pending` 且当前时间超过 `expires_at` -> `closed`
2. `pending | closed` 收到合法支付成功通知 -> `paid`
3. `paid` 收到退款通知：
   - 累计退款金额 `< 实付金额` -> `refunded_partial`
   - 累计退款金额 `== 实付金额` -> `refunded_full`
4. `refunded_partial` 再收到退款，累计至全额 -> `refunded_full`
5. `paid/refunded_partial/refunded_full` 均视为终态（不可继续支付原单）

---

## 数据模型

### 1) 订单文件（`payment_orders/*.json`）

在现有字段基础上补充/规范：

- `status`: `pending|paid|closed|refunded_partial|refunded_full`
- `created_at`: 订单创建时间
- `expires_at`: 超时时间（`created_at + payment_timeout_minutes`）
- `closed_at`: 关闭时间（可空）
- `paid_time`: 支付时间（可空）
- `pay_type`: 渠道
- `billing_scope`:
  - `school_id`
  - `billing_id`
- `refund_total`: 累计退款金额（默认 0）
- `last_qr_cache_key`: 最近二维码缓存键（可空）

读取兼容策略：
- 若旧订单无 `expires_at`，运行时按 `created_at + timeout` 推导；
- 若旧订单无 `refund_total`，按 0 处理。

### 2) 二维码缓存索引（新增）

文件：`payment_orders/qr_cache_index.json`

结构：

```json
{
  "<school_id>:<billing_id>:<pay_type>": {
    "order_id": "...",
    "qr_payload": "...",
    "created_at": "...",
    "expires_at": "...",
    "status_snapshot": "pending"
  }
}
```

写入条件：仅当支付接口返回类型被解析为二维码时写入。

失效条件：
- 当前时间超过 `expires_at`
- 对应订单进入 `paid/refunded_partial/refunded_full`
- 被新二维码覆盖

---

## 核心流程

### A. 用户发起“单独支付账单项”

1. 根据 `school_id + billing_id + pay_type` 生成缓存键。
2. 读取该账单项关联订单，先执行状态推进（超时关单）。
3. 若存在终态订单（`paid/refunded_partial/refunded_full`），直接返回“不可重复支付”。
4. 查二维码缓存：
   - 命中且未过期：直接返回缓存二维码（`reused_qr=true`）。
   - 否则发起新下单。
5. 新下单成功后：
   - 写订单文件（`pending` + `expires_at`）
   - 关联到对应账单项 `payment_orders`
   - 若返回二维码则写缓存索引

### B. 订单列表查询/账单列表刷新

每次读取订单前先执行状态推进：
- `pending` 超时 -> `closed`

确保前端展示实时一致。

### C. 异步支付成功通知

1. 校验签名与金额。
2. 定位本地订单。
3. 无论当前是 `pending` 还是 `closed`，都更新为 `paid`。
4. 清理对应二维码缓存键，避免继续复用。

### D. 异步退款通知

1. 校验通知。
2. 增加 `refund_total`。
3. 按累计退款金额更新：`refunded_partial` 或 `refunded_full`。
4. 对应订单保持不可重新支付。

---

## 配置与界面

### 配置

复用：`Rainbow_YiPay.payment_timeout_minutes`

管理端文案调整：
- “订单待支付超时分钟数（同时用于二维码缓存复用时长）”

### 前端状态文案映射

- `pending` -> 待支付
- `paid` -> 已支付
- `closed` -> 已关闭
- `refunded_partial` -> 部分退款
- `refunded_full` -> 全额退款

支付按钮交互：
- `paid/refunded_partial/refunded_full`：禁止再支付并提示
- `closed`：提示旧单已关闭，将创建新订单
- 命中缓存二维码：提示复用二维码

---

## 并发与一致性

1. 对订单文件与二维码缓存索引读写加锁（沿用项目现有锁风格）。
2. 通知处理幂等：重复通知不会破坏终态。
3. 缓存读取命中后仍需二次检查对应订单终态，防止脏缓存。

---

## 测试计划

### 后端测试

1. 新订单在 N 分钟后：`pending -> closed`
2. `closed` 收到支付成功通知：`closed -> paid`
3. `paid` 收到部分退款：`paid -> refunded_partial`
4. `refunded_partial` 再退款到全额：`-> refunded_full`
5. 同 `school_id+billing_id+pay_type` 在 N 分钟内重复发起：复用同二维码
6. 不同 `pay_type` 不复用二维码
7. 超过 N 分钟缓存失效：不复用，重新下单
8. 命中缓存但订单已终态：拒绝支付并清理缓存

### 前端回归点

1. 五种状态文案展示正确
2. 终态订单支付按钮行为正确
3. 缓存复用提示与新建订单提示正确

---

## 受影响文件（预估）

- `main.py`（支付创建、订单状态推进、异步通知、退款处理、配置读取）
- `scripts/main.new.js`（账单支付按钮行为、状态展示、提示）
- `index.html`（管理端配置项说明文本、状态筛选文案）
- `tests/*`（新增后端/前端回归测试）

---

## 风险与缓解

1. 风险：历史订单缺字段导致解析失败。
   - 缓解：读取兼容补默认。
2. 风险：缓存与订单状态不一致。
   - 缓解：返回缓存前二次校验订单状态。
3. 风险：通知乱序（先退款后支付）。
   - 缓解：按平台事件时间与状态幂等规则处理，终态保护。
