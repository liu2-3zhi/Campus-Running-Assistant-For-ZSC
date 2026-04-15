# 验证码实时刷新、延期限制与登录前背景绑定设计

**日期：** 2026-04-09  
**范围：** `verification-codes-modal`（PC+移动端）、手机号未注册跳转注册流程、登录前背景图绑定

---

## 1. 目标

在不扩大改动面的前提下完成三个需求：

1. 验证码管理弹窗与后端建立 WebSocket 实时更新；连接失败或断开时回退到 30s 轮询。
2. 手机号未注册后的验证码延期只能一次（维度：`phone + code`），且前端在延期被拒时不阻断注册流程。
3. 用户点击登录按钮后立即记录“登录前背景图快照”，后续登录成功绑定时绑定该登录前背景图。

---

## 2. 方案选择

采用**最小改动补丁方案**（已确认）：

- 不引入大型新模块；在现有 `main.new.js` 和后端对应接口上增量修改。
- 复用现有 socket 事件 `verification_codes_updated`。
- 保留现有手机号未注册重定向交互，补足延期限制与提示文案。
- 保留现有背景上报机制，增加“登录点击快照”优先绑定。

---

## 3. 详细设计

### 3.1 验证码弹窗：WebSocket + 30s轮询回退（PC+移动端）

#### 3.1.1 前端状态（`scripts/main.new.js`）

新增状态变量：

- `verificationCodesPollingTimer = null`
- `VERIFICATION_CODES_POLLING_MS = 30000`
- `verificationCodesSocketHealthy = false`

#### 3.1.2 统一刷新入口

新增函数：

- `refreshOpenVerificationCodeModals()`
  - 如果 PC `verification-codes-modal` 可见，则调用 `loadVerificationCodes()`。
  - 如果移动端 `mobile-verification-codes-modal` 可见，则调用 `loadMobileVerificationCodes()`。

#### 3.1.3 轮询启停

新增函数：

- `startVerificationCodesPollingFallback()`：若未启动则每 30s 调用 `refreshOpenVerificationCodeModals()`。
- `stopVerificationCodesPollingFallback()`：清理定时器。

策略：

- socket connect/reconnect：标记 healthy，停止轮询。
- socket disconnect/connect_error：标记 unhealthy，启动轮询。
- 收到 `verification_codes_updated`：立即刷新已打开弹窗。
- 当两个弹窗都关闭时可停止轮询，避免空转。

---

### 3.2 手机号未注册：延期一次限制（`phone+code`）+ 前端非阻断

#### 3.2.1 后端规则

在 `/api/sms/extend_code` 对应逻辑中新增一次性限制：

- 键：`extend_key = f"{phone}:{code}"`
- 首次命中：允许延期并记录已使用。
- 再次命中：拒绝延期，返回明确错误码（例如 `EXTEND_LIMIT_REACHED`）和提示信息。

说明：

- 限制只针对同 `phone+code`，符合已确认边界。
- 记录存储在当前验证码运行态数据结构（无需额外持久化）。

#### 3.2.2 前端处理（`handlePhoneNotRegisteredRedirect`）

无论延期成功/被拒/异常，都不阻断注册引导：

- 保持手机号和验证码已填充状态。
- 不跳回登录，不清空输入。
- 焦点保持引导到注册用户名输入框。

提示分支：

- 延期成功：显示“已延期（仅一次）”。
- 延期被拒：显示“已达到延期上限，本次未再次延期，请尽快完成注册”。
- 网络异常：显示“延期状态获取失败，请尽快完成注册”。

---

### 3.3 “信息已自动填充”弹窗改造：实时显示验证码剩余时间

#### 3.3.1 需求约束（已补充确认）

在 `Swal.fire({ title: "信息已自动填充" ... })` 中：

- 不再固定写“已自动延长5分钟”。
- 改为显示**当前验证码真实剩余有效时间**。
- 用户长时间不点击确认时，剩余时间需持续动态更新。

#### 3.3.2 实现方式

- 在弹窗 `didOpen` 启动 `setInterval(1000)`。
- 每秒更新剩余时间 DOM（例如 `#reg-sms-expire-countdown`）。
- `willClose`/`didDestroy` 清理 interval。
- 倒计时归零后切换为“验证码可能已过期，请重新获取”。

#### 3.3.3 文案结构

弹窗统一包含：

1. 已自动填充手机号和验证码；
2. 当前验证码剩余时间（动态）；
3. 延期结果状态（成功/已达上限/状态未知）；
4. 请尽快完成注册。

---

### 3.4 登录前背景图快照绑定（A方案）

#### 3.4.1 前端快照采集

在登录按钮点击入口（PC/移动端）执行前：

- 记录 `preLoginBackgroundSnapshot[target] = 当前可见背景图URL`。
- 仅记录，不立即上报。

#### 3.4.2 登录成功后绑定

在后续背景消费上报（`notifyThemeBackgroundConsumed`）时：

- 优先使用 `preLoginBackgroundSnapshot[target]` 作为登录绑定候选图。
- 若快照不存在，回退现有逻辑。
- 绑定成功后清理对应 target 的快照，避免污染下一次登录。

---

## 4. 错误处理

1. **WebSocket 不可用**：自动回退 30s 轮询；socket 恢复后自动停轮询。  
2. **延期被拒**：按业务可预期分支处理（warning/info），不作为流程错误中断。  
3. **延期网络失败**：提示用户尽快注册，但不阻断。  
4. **弹窗计时器泄漏**：统一在 `willClose`/`didDestroy` 清理。  
5. **背景快照缺失**：使用当前背景作为兜底。

---

## 5. 验收标准

### 5.1 验证码管理弹窗

- 在 PC 弹窗打开时，后端推送后可即时刷新。
- 在移动端弹窗打开时，后端推送后可即时刷新。
- 人为断开 socket 后，30s 周期刷新生效。
- socket 恢复后轮询自动停止。

### 5.2 延期一次限制

- 同 `phone+code` 第一次延期成功。
- 同 `phone+code` 第二次延期被拒并返回明确码。
- 前端收到拒绝后仍保持注册表单状态，不阻断后续注册。

### 5.3 自动填充提示弹窗

- 无论延期结果如何，都显示动态“剩余时间”。
- 用户不点击确认，时间每秒递减更新。
- 弹窗关闭后无残留定时器。

### 5.4 背景绑定

- 登录点击后生成登录前快照。
- 登录成功后绑定使用该快照图。
- 使用后快照被清理。

---

## 6. 影响文件（预期）

前端：
- `scripts/main.new.js`

后端：
- `main.py`（`extend_code` 及背景绑定相关路径）

测试：
- `tests/test_theme_background_binding.py`（补充登录前快照绑定用例）
- 新增或扩展 `extend_code` 相关测试（若已有短信模块测试文件则优先复用）

---

## 7. 非目标

- 不重构现有 socket 框架。
- 不引入新的持久化表结构。
- 不改动非验证码/非登录背景绑定的其他功能路径。
