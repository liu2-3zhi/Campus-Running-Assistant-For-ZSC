# 14 · index.html 尾部模态框逐行解析（覆盖范围：index.html 19524–22894 / 文件结尾）

> 本文件是对 original 前端单文件 `index.html` **第 19524 行至第 22894 行（含 `</body></html>`）** 的逐行、无遗漏解析，作为 Vue 重构版复刻的权威依据。
> 生成时间：2026-07-14
>
> 该段落是整个 `index.html` 的最尾部，主要由**两类内容**组成：
> 1. `#admin-modal-content` 容器内的**管理员多功能面板子页**（`*_modal` 后缀，通过标签切换在同一管理模态框中显示，初始 `hidden`）。此段落起始处的 4 个面板（定价 / 水印 / 账单 / 账单日志 / 恢复账号）仍属于上文（19524 行之前）打开的管理模态框 `#admin-modal-content`，其闭合标签在 20404–20405 行。
> 2. 一大批**独立的顶层模态框**（`fixed inset-0 ... hidden z-[...]`），以及末尾两个使用 `.modal` 类的支付/订单弹窗。
> 3. 文件结尾的**内联 `<script>`**：无障碍名称自动注入器。
>
> 说明：本段所有交互元素采用**内联 `onclick`/`onchange`/`onkeyup`/`oninput` 引用全局 JS 函数**（函数定义在 `scripts/main.new.js`）。本文只登记引用名，不含函数实现。

---

## 目录（按出现顺序 / 行号）

| # | 行号 | 容器 id | 类型 | 标题 | 初始可见性 |
|---|---|---|---|---|---|
| 1 | 19524 | `admin-pricing-panel_modal` | 管理面板子页 | 价格配置管理 | `hidden` |
| 2 | 19963 | `admin-watermark-control-panel_modal` | 管理面板子页 | 高德地图去水印控制 | `hidden` |
| 3 | 20162 | `admin-billing-panel_modal` | 管理面板子页 | 账单管理 | `hidden` |
| 4 | 20299 | `admin-billing-logs-panel_modal` | 管理面板子页 | 账单日志 | `hidden` |
| 5 | 20377 | `admin-restore-account-panel_modal` | 管理面板子页 | 恢复账号 | `hidden` |
| — | 20404 | （`#admin-modal-content` 容器闭合 `</div></div>`） | — | — | — |
| 6 | 20415 | `add-watermark-user-modal` | 顶层模态框 | 添加用户到水印控制 | `hidden` `z-[20001]` |
| 7 | 20537 | `reminder-edit-modal` | 顶层模态框 | 添加/编辑定时提醒 | `hidden` `z-[1055]` |
| 8 | 20699 | `sms-balance-modal` | 顶层模态框 | 短信余额 | `hidden` `z-[1055]` |
| 9 | 20761 | `sms-history-modal` | 顶层模态框 | 短信发送历史 | `hidden` `z-[1054]` |
| 10 | 20819 | `verification-codes-modal` | 顶层模态框 | 验证码状态管理 | `hidden` `z-[1054]` |
| 11 | 20896 | `admin-modify-nickname-modal` | 顶层模态框 | 修改用户昵称 | `hidden` `z-[1053]` |
| 12 | 20973 | `admin-modify-phone-modal` | 顶层模态框 | 修改用户手机号 | `hidden` `z-[1053]` |
| 13 | 21089 | `user-logs-secondary-modal` | 顶层模态框 | 用户日志查看 | `hidden` `z-[1053]` |
| 14 | 21160 | `confirm-modal` | 顶层模态框 | 请确认（通用确认框） | `hidden` `z-[50000]` |
| 15 | 21192 | `session-picker-modal` | 顶层模态框 | 会话管理 | `hidden` `z-[1052]` |
| 16 | 21268 | `sms-test-modal` | 顶层模态框 | 短信测试发送 | `hidden` `z-[1054]` |
| 17 | 21425 | `sms-reply-logs-modal` | 顶层模态框 | 短信回复记录 | `hidden` `z-[1054]` |
| 18 | 21531 | `captcha-detail-modal` | 顶层模态框 | 验证码详细信息 | `hidden` `z-[1054]` |
| 19 | 21705 | `create-group-modal` | 顶层模态框 | 创建权限组 | `hidden` `z-[1054]` |
| 20 | 21778 | `edit-group-permissions-modal` | 顶层模态框 | 编辑权限组 | `hidden` `z-[1054]` |
| 21 | 21830 | `manage-user-permissions-modal` | 顶层模态框 | 管理用户权限 | `hidden` `z-[1054]` |
| 22 | 21893 | `manage-school-accounts-modal` | 顶层模态框 | 管理学校账户（PC） | `hidden` `z-[1054]` |
| 23 | 22015 | `mobile-user-school-accounts-modal` | 顶层模态框（移动端） | 管理学校账户（移动） | `hidden` `z-[1055]` |
| 24 | 22242 | `edit-school-account-modal-simple` | 顶层模态框 | 编辑学校账户 | `hidden` `z-[1055]` |
| 25 | 22310 | `set-max-sessions-modal` | 顶层模态框 | 设置会话限制 | `hidden` `z-[1054]` |
| 26 | 22366 | `reset-user-password-modal` | 顶层模态框 | 重置用户密码 | `hidden` `z-[1054]` |
| 27 | 22426 | `avatar-crop-modal` | 顶层模态框 | 裁剪头像 | `hidden` `z-[1055]` |
| 28 | 22461 | `modify-phone-modal` | `.modal` 弹窗 | 修改绑定手机号 | `.modal`（CSS 控制） |
| 29 | 22586 | `payment-modal` | `.modal` 弹窗 | 在线支付 | `.modal`（CSS 控制） |
| 30 | 22697 | `orders-modal` | `.modal` 弹窗 | 我的订单 | `.modal`（CSS 控制） |
| 31 | 22803 | 内联 `<script>` | 脚本 | 无障碍名称注入器 | — |

> **可见性约定**：
> - `hidden` = Tailwind 隐藏类，由 JS 增删 `hidden` 控制显隐。
> - `z-[...]` = 层叠顺序；`confirm-modal` 使用最高 `z-[50000]`，`add-watermark-user-modal` 使用 `z-[20001]`。
> - 末尾三个弹窗（28/29/30）用自定义 `.modal` / `.modal-content` 类（CSS 中定义显隐动画），JS 通过增删 `.show` 或 `style.display` 控制，而非 `hidden`。

---

## 1. `#admin-pricing-panel_modal` — 价格配置管理（19524–19944）

- **容器**：`<div id="admin-pricing-panel_modal" class="hidden overflow-y-auto">`（19524）
- **初始可见性**：`hidden`（管理模态框内的标签子页）
- **顶部标题区**（19526–19550）：渐变背景 `from-sky-50 to-blue-50`，价格图标 SVG + 标题 **“价格配置管理”**；描述文本：“配置系统的价格策略，包括是否启用付费模式、单次跑步费用和新用户的默认免费次数。”

### 配置表单区（19553–19881，`space-y-4`）—— 共 7 个配置项

| 配置项 | 行号 | 控件 id | 类型 | 关键属性 | 标题 / 说明文案 |
|---|---|---|---|---|---|
| 1 是否需要付费 | 19555–19603 | `pricing-require-payment_modal` | checkbox（`sr-only peer` 开关样式） | `aria-label`/`title="pricing require payment_modal"` | 标题“是否需要付费”；说明“开启后，用户需要支付才能使用跑步服务；关闭后，所有用户可免费使用。” |
| 2 单次跑步费用 | 19606–19645 | `pricing-per-run-cost_modal` | `number` | `min="0"` `step="0.01"` `required` `placeholder="例如：1.0"` | 标题“单次跑步费用（元）”；说明“用于计算用户欠费金额 = 欠费次数 × 单次费用。设置为0表示免费。”；提示“支持小数，最多两位小数（如1.50）” |
| 3 新用户默认免费次数 | 19648–19687 | `pricing-default-runs_modal` | `number` | `min="0"` `step="1"` `required` `placeholder="例如：10"` | 标题“新用户默认免费次数”；说明“新用户注册时自动获得的免费跑步次数。设置为0表示无免费次数。”；提示“必须是非负整数（如0、10、100）” |
| 4 个人资料页显示剩余次数 | 19692–19746 | `pricing-show-available-runs_modal` | checkbox 开关 | `aria-label`/`title="pricing show available runs_modal"` | 标题“个人资料页显示剩余次数”；说明“开启后，用户在个人资料页面可以看到自己的剩余跑步次数。” |
| 5 剩余次数显示格式 | 19749–19787 | `pricing-available-runs-format_modal` | `text` | `required` `placeholder="例如：剩余免费次数：{available_runs} 次"` | 标题“剩余次数显示格式”；说明含占位符 `{available_runs}`；提示“示例：剩余免费次数：{available_runs} 次 → 剩余免费次数：10 次” |
| 6 注册页显示免费次数提示 | 19790–19838 | `pricing-show-register-hint_modal` | checkbox 开关 | `aria-label`/`title="pricing show register hint_modal"` | 标题“注册页显示免费次数提示”；说明“开启后，用户在注册页面可以看到注册即可获得的免费次数提示。” |
| 7 注册页提示文本 | 19841–19880 | `pricing-register-hint-text_modal` | `text` | `required` `placeholder="例如：注册即可得 {available_runs} 次校园跑"` | 标题“注册页提示文本”；说明含占位符 `{available_runs}`；提示“示例：注册即可得 {available_runs} 次校园跑 → 注册即可得 10 次校园跑” |

> **注释分组标记**（19689）：`<!-- ==================== UI显示配置 ==================== -->`，将配置项 1–3（价格策略）与 4–7（UI 显示）分组。
> checkbox 开关的视觉表现均用 Tailwind `peer` 特性实现（`peer-checked:bg-sky-600` 等，19599 / 19742 / 19834）。

### 操作按钮组（19890–19943，`grid grid-cols-2 gap-3`）

| 按钮 | 行号 | `onclick` | 样式 | 文案 / title |
|---|---|---|---|---|
| 刷新配置 | 19894–19916 | `loadPricingConfig()` | `bg-slate-500`（辅助操作） | 文案“刷新配置”；`title="点击从服务器重新加载价格配置"` |
| 保存配置 | 19921–19942 | `savePricingConfig()` | `bg-sky-600`（主操作） | 文案“保存配置”；`title="点击保存当前的价格配置"` |

> 面板内长注释（19883–19889）说明按钮组参考 `admin-payment-settings-content-yipay_modal` 面板样式。
> **复刻要点**：7 项配置 → JS 从 `loadPricingConfig()` 拉取后填充，`savePricingConfig()` 读取 7 个控件（2 个 number、2 个 text、3 个 checkbox）提交。

---

## 2. `#admin-watermark-control-panel_modal` — 高德地图去水印控制（19963–20156）

- **容器**：`<div id="admin-watermark-control-panel_modal" class="hidden overflow-y-auto overflow-x-hidden">`（19963–19965）
- **权限**：需要 `modify_config` 权限；API：`GET/PUT /api/amap/watermark_control/config`（见 19946–19961 注释）。默认值取自 `configs/config.json` 的 `[Map] watermark_removal_default`，个性化存 `amap_watermark_control.json`。
- **顶部标题区**（19967–19992）：渐变 `from-blue-50 to-cyan-50`，标题 **“高德地图去水印控制”**；描述“配置用户是否可以使用高德地图去水印功能。未配置的用户使用系统默认值。”

### 默认值配置区（19995–20037，`bg-amber-50`）

| 元素 | 行号 | id | 事件 | 说明 |
|---|---|---|---|---|
| 系统默认开关 | 20018–20024 | `watermark-default-value_modal` | `onchange="updateWatermarkDefaultLabel()"` | checkbox 开关，`aria-label="系统默认去水印权限开关"`；前缀文案“系统默认值：” |
| 默认值标签 | 20028–20031 | `watermark-default-label_modal` | — | 空 `<span>`，由 JS 填充（“开启/关闭”文案） |
| 提示文案 | 20034–20036 | — | — | “未在下方列表中配置的用户将使用此默认值” |

### 用户权限列表区（20040–20099）

| 元素 | 行号 | id | 事件 / 属性 | 说明 |
|---|---|---|---|---|
| 小标题 | 20042–20058 | — | — | “用户权限配置” |
| 添加用户按钮 | 20061–20081 | — | `onclick="openAddWatermarkUserModal()"` | 文案“添加用户”，`title="点击添加用户到水印控制列表"` |
| 用户计数 | 20082–20086 | `watermark-user-count_modal` | — | 初始文案“共 0 个用户” |
| 用户列表容器 | 20092–20098 | `watermark-users-list_modal` | — | `max-h-[50vh] overflow-y-auto`，初始占位“加载中...”，JS 动态填充每个用户开关 |

### 操作按钮组（20107–20155，`grid grid-cols-2`）

| 按钮 | 行号 | `onclick` | 样式 | 文案 / title |
|---|---|---|---|---|
| 刷新配置 | 20110–20130 | `loadWatermarkControlConfig()` | `bg-slate-500` | “刷新配置”；`title="点击从服务器重新加载水印控制配置"` |
| 保存配置 | 20134–20154 | `saveWatermarkControlConfig()` | `bg-sky-600` | “保存配置”；`title="点击保存当前的水印控制配置"` |

---

## 3. `#admin-billing-panel_modal` — 账单管理（20162–20297）

- **容器**：`<div id="admin-billing-panel_modal" class="hidden overflow-y-auto overflow-x-hidden p-4 space-y-4" style="margin-top: 0px">`（20162–20166）
- **顶部标题区**（20167–20239）：渐变 `from-green-50 to-emerald-50`，账单图标 + 标题 **“账单管理”**；副标题“查询所有用户或指定用户的账单记录”。
  - 右侧按钮组：
    - 刷新按钮（20198–20216）`onclick="loadAdminBillingList()"`，文案“刷新”。
    - 添加账单按钮（20217–20236）`onclick="adminAddBillingDialog()"`，`aria-label="添加账单"`，文案“添加账单”。

### 搜索栏（20240–20276）

| 元素 | 行号 | id | 属性 | 占位/文案 |
|---|---|---|---|---|
| 学校账号筛选输入 | 20256–20261 | `admin-billing-school-input` | `text` | placeholder“输入学校账号筛选（留空查询有权限全部）” |
| 关键词搜索输入 | 20262–20267 | `admin-billing-search-input` | `text` | placeholder“搜索昵称 / 用户名 / 手机号 / 学号 / 账单号 / 订单号 / 流水号” |
| 搜索按钮 | 20268–20275 | `admin-billing-search-btn` | `onclick="loadAdminBillingList()"` | 文案“搜索” |

### 列表容器（20277–20296）

- `<div id="admin-billing-list-container">`，初始空状态占位（图标 + “点击查询加载账单记录”）。

---

## 4. `#admin-billing-logs-panel_modal` — 账单日志（20299–20371）

- **容器**：`<div id="admin-billing-logs-panel_modal" class="hidden overflow-y-auto overflow-x-hidden p-4 space-y-4" style="margin-top: 0px">`（20299–20303）
- **顶部标题区**（20304–20318）：渐变 `from-sky-50 to-cyan-50`，标题 **“账单日志”**；副标题“查看账单创建、修改、清除与删除等审计记录”；刷新按钮 `onclick="loadAdminBillingLogs()"` 文案“刷新”。

### 筛选栏（20320–20347）

| 元素 | 行号 | id | 事件/属性 | 说明 |
|---|---|---|---|---|
| 关键词输入 | 20321–20326 | `admin-billing-logs-search-input_modal` | `text` | placeholder“搜索账单号 / 用户 / 手机 / 学校账号” |
| 事件类型下拉 | 20327–20338 | `admin-billing-logs-event-type_modal` | `select` | 选项见下表 |
| 搜索按钮 | 20339–20346 | `admin-billing-logs-search-btn_modal` | `onclick="loadAdminBillingLogs(1)"` | 文案“搜索” |

**事件类型 `<select>` 选项**（20331–20337）：

| value | 文案 |
|---|---|
| `""` | 全部事件 |
| `billing_created` | 创建 |
| `billing_amount_changed` | 金额变化 |
| `billing_status_changed` | 状态变化 |
| `billing_admin_cleared` | 管理员清除 |
| `billing_reason_changed` | 原因变化 |
| `billing_deleted` | 删除 |

### 列表 + 分页（20348–20369）

| 元素 | 行号 | id | 事件 | 说明 |
|---|---|---|---|---|
| 日志列表容器 | 20348–20350 | `admin-billing-logs-list_modal` | — | `max-h-[50vh]`，初始占位“点击搜索加载账单日志” |
| 上一页 | 20352–20359 | `admin-billing-logs-prev-btn_modal` | `onclick="loadAdminBillingLogsPrev()"` | 文案“上一页” |
| 页码显示 | 20360 | `admin-billing-logs-page-info_modal` | — | 初始“第 1 页” |
| 下一页 | 20361–20368 | `admin-billing-logs-next-btn_modal` | `onclick="loadAdminBillingLogsNext()"` | 文案“下一页” |

---

## 5. `#admin-restore-account-panel_modal` — 恢复账号（20377–20403）

- **容器**：`<div id="admin-restore-account-panel_modal" class="hidden overflow-y-auto overflow-x-hidden p-4 space-y-4" style="margin-top: 0px">`（20377–20381）
- **顶部标题区**（20382–20399）：渐变 `from-amber-50 to-orange-50`，标题 **“恢复账号”**；副标题“从删除记录中恢复已删除的用户账号”；刷新按钮 `onclick="loadRemovedAccountsList()"` 文案“刷新”。
- **列表容器**（20400–20402）：`<div id="removed-accounts-list-container" class="overflow-x-auto">`，初始占位“点击刷新加载已删除账号记录”。

> **20404–20405**：`</div></div>` 闭合上文的 `#admin-modal-content` 及其外层管理模态框容器。以上 5 个 `*_modal` 面板均为该管理模态框内的标签切换子页。

---

## 6. `#add-watermark-user-modal` — 添加用户到水印控制（20415–20535）

- **容器**：`<div id="add-watermark-user-modal" class="fixed inset-0 flex items-center justify-center hidden z-[20001]">`（20415–20418）
- **背景遮罩**（20420–20423）：`bg-black/70`，`onclick="closeAddWatermarkUserModal()"`。
- **标题栏**（20430–20479）：标题 **“添加用户到水印控制”**（用户+图标 SVG）。右侧按钮组：
  - 刷新按钮 `onclick="refreshWatermarkUserList()"`，`title="刷新用户列表"`（20451–20469）。
  - 关闭按钮 `onclick="closeAddWatermarkUserModal()"`，`×`，`title="关闭"`（20471–20477）。
- **内容区**（20482–20522）：
  - 说明文字（20484–20486）：“从下方列表中选择要添加到水印控制配置的用户。添加后，您可以为该用户设置是否允许使用去水印功能。”
  - 搜索框（20490–20497）：id `watermark-user-search`，`onkeyup="filterWatermarkUsers()"`，placeholder“搜索用户名...”，`aria-label="搜索用户"`（内含搜索图标 SVG）。
  - 可用用户列表容器（20515–20521）：id `available-watermark-users-list`，`max-h-[50vh]`，初始占位“加载中...”。
- **底部按钮**（20524–20533）：关闭按钮 `onclick="closeAddWatermarkUserModal()"`，文案“关闭”，`title="关闭对话框"`。

---

## 7. `#reminder-edit-modal` — 添加/编辑定时提醒（20537–20697）

- **容器**：`fixed ... hidden z-[1055]`；背景遮罩 id `reminder-edit-modal_background`，`onclick="closeReminderEditModal()"`（20541–20545）。
- **标题**（20551–20553）：id `reminder-modal-title`，初始文案 **“⏰ 添加定时提醒”**（编辑时 JS 改文案）。关闭 `×` → `closeReminderEditModal()`（20554–20559）。

### 表单字段

| 字段 | 行号 | id | 类型 | 关键属性 / 文案 |
|---|---|---|---|---|
| 隐藏 ID | 20563–20569 | `reminder-id-field` | `hidden` | 存提醒 ID |
| 提醒标题 | 20575–20581 | `reminder-title-field` | `text` | `maxlength="50"`；placeholder“例如：学校服务器关闭提醒”；提示“最多50个字符”；标签“📌 提醒标题 *” |
| 提醒内容（回退） | 20590–20597 | `reminder-message-field` | `textarea` | `rows="4"` `maxlength="500"`，`style="display:none"`（Editor.md 无 JS 回退） |
| Editor.md 容器 | 20598–20607 | `reminder-editor` | div | `min-height:220px`；提示“最多500个字符（支持 Markdown）”；标签“📝 提醒内容 *” |
| 开始时间 | 20618–20625 | `reminder-start-time-field` | `time` | 提示“24小时制（如 19:00）”；标签“⏰ 开始时间 *” |
| 结束时间 | 20633–20640 | `reminder-end-time-field` | `time` | 提示“24小时制（如 20:00）”；标签“⏰ 结束时间 *” |
| 启用开关 | 20655–20662 | `reminder-enabled-field` | `checkbox` | `checked`；`for` 标签“✅ 启用此提醒（取消勾选则暂时禁用，不会删除数据）” |

- **跨天说明蓝框**（20645–20652）：“💡 跨天时间说明”，含跨天/正常时间示例。
- **底部按钮**（20672–20695）：取消 `onclick="closeReminderEditModal()"`；保存 `onclick="saveReminder()"` 文案“保存提醒”（含对勾 SVG）。

---

## 8. `#sms-balance-modal` — 短信余额（20699–20758）

- **容器**：`fixed ... hidden z-[1055]`；遮罩 `onclick="closeSMSBalanceModal()"`（20704–20706）。
- **标题**（20711）：**“💰 短信余额”**；关闭 `×` → `closeSMSBalanceModal()`。
- **内容展示**（20720–20747）：
  - 剩余条数 id `sms-balance-modal-value`，初始 `--`。
  - 今日已发送 id `sms-balance-modal-sent`，初始 `--`。
  - 消息栏 id `sms-balance-modal-message`，初始“查询中...”。
- **底部按钮**（20749–20756）：关闭 `onclick="closeSMSBalanceModal()"`，文案“关闭”。

---

## 9. `#sms-history-modal` — 短信发送历史（20761–20816）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeSMSHistoryModal()"`（20766–20768）。
- **标题**（20773）：**“📋 短信发送历史”**；关闭 `×` → `closeSMSHistoryModal()`。
- **过滤栏**（20782–20801）：
  - 日期过滤 id `sms-history-date-filter`（`date`，placeholder“按日期过滤”）。
  - 手机号过滤 id `sms-history-phone-filter`（`text`，placeholder“按手机号过滤”）。
  - 刷新按钮 `onclick="loadSMSHistory()"`，文案“🔄 刷新”。
- **列表容器**（20803–20808）：id `sms-history-list`，`max-h-[55vh]`，初始“加载中...”。
- **底部按钮**（20810–20814）：关闭 `onclick="closeSMSHistoryModal()"`，文案“关闭”。

---

## 10. `#verification-codes-modal` — 验证码状态管理（20819–20894）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeVerificationCodesModal()"`（20824–20826）。
- **标题**（20831）：**“🔑 验证码状态管理”**；关闭 `×` → `closeVerificationCodesModal()`。
- **手动添加验证码区**（20840–20873，`bg-green-50`）：小标题“➕ 手动添加验证码”。
  - 手机号输入 id `manual-code-phone`（`tel`，`pattern="[0-9]*"` `maxlength="11"`，前缀 `+86`），placeholder“手机号”。
  - 验证码输入 id `manual-code-value`（`text`，`maxlength="6"` `pattern="[0-9]{6}"`），placeholder“验证码（6位数字）”。
  - 添加按钮 `onclick="addManualVerificationCode()"`，文案“添加验证码”。
  - 提示（20870–20872）：“💡 此功能用于测试或紧急情况下手动添加验证码，不会实际发送短信”。
- **刷新按钮**（20876–20878）：`onclick="loadVerificationCodes()"`，文案“🔄 刷新列表”。
- **列表容器**（20881–20886）：id `verification-codes-list`，`max-h-[45vh]`，初始“加载中...”。
- **底部按钮**（20888–20892）：关闭 `onclick="closeVerificationCodesModal()"`，文案“关闭”。

---

## 11. `#admin-modify-nickname-modal` — 修改用户昵称（20896–20971）

- **容器**：`fixed ... hidden z-[1053]`；遮罩 `onclick="closeAdminModifyNicknameModal()"`（20900–20903）。
- **标题**（20906）：**“修改用户昵称”**；关闭 `×` → `closeAdminModifyNicknameModal()`。
- **字段**：
  - 用户名 id `admin-modify-nickname-username`（`text` `readonly`，20920–20928）。
  - 当前昵称 id `admin-modify-nickname-current`（`text` `readonly`，20935–20943）。
  - 新昵称 id `admin-modify-nickname-new`（`text`，placeholder“请输入新昵称 (可含中文)”，20950–20955）。
- **底部按钮**（20959–20968）：取消 `onclick="closeAdminModifyNicknameModal()"`；确认修改 `onclick="submitAdminModifyNickname()"`。

---

## 12. `#admin-modify-phone-modal` — 修改用户手机号（20973–21087）

- **容器**：`fixed ... hidden z-[1053]`；遮罩 `onclick="closeAdminModifyPhoneModal()"`（20977–20980）。
- **标题**（20983）：**“修改用户手机号”**；关闭 `×` → `closeAdminModifyPhoneModal()`。
- **字段**：
  - 用户名 id `admin-modify-phone-username`（`text` `readonly`，20997–21005）。
  - 当前手机号 id `admin-modify-phone-current`（`tel` `readonly`，前缀 `+86`，21014–21022）。
  - 新手机号 id `admin-modify-phone-new`（`tel`，`inputmode="numeric"` `pattern="[0-9]*"` `maxlength="11"`，前缀 `+86`，21032–21040）。
  - 验证码组 `<div id="admin-modify-phone-sms-group">`（21044–21072）：
    - 验证码输入 id `admin-modify-phone-code`（`text`，`maxlength="6"` `inputmode="numeric"` `pattern="[0-9]{6}"`，placeholder“验证码”）。
    - 发送验证码按钮 id `admin-modify-phone-send-btn`，`onclick="sendAdminModifyPhoneCode()"`，文案“发送验证码”。
    - 提示 id `admin-modify-phone-sms-hint`：“管理员修改手机号不强制要求验证码，如填写将进行校验”。
- **底部按钮**（21075–21085）：取消 `onclick="closeAdminModifyPhoneModal()"`；确认修改 `onclick="submitAdminModifyPhone()"`。

---

## 13. `#user-logs-secondary-modal` — 用户日志查看（21089–21158）

- **容器**：`fixed ... hidden z-[1053]`；遮罩 `onclick="closeUserLogsSecondaryModal()"`（21093–21096）。
- **标题**（21101）：**“用户日志查看”**；关闭 `×` → `closeUserLogsSecondaryModal()`。
- **当前用户信息**（21110–21119）：id `current-log-username-secondary`，初始“N/A”。
- **Tab 切换**（21121–21136）：
  - 登录记录 tab id `log-tab-login-secondary`，`onclick="switchUserLogTab('login')"`（默认激活，`text-sky-600 border-b-2 border-sky-600`）。
  - 操作记录 tab id `log-tab-audit-secondary`，`onclick="switchUserLogTab('audit')"`（默认非激活）。
- **内容容器**：
  - 登录内容 id `log-login-content-secondary`（默认可见，21138–21143），初始“加载中...”。
  - 操作内容 id `log-audit-content-secondary`（默认 `hidden`，21145–21150），初始“加载中...”。
- **底部按钮**（21152–21156）：关闭 `onclick="closeUserLogsSecondaryModal()"`。

---

## 14. `#confirm-modal` — 通用确认框（21160–21190）

- **容器**：`fixed ... hidden z-[50000]`（最高层级）；遮罩 `bg-black/60`（**无 onclick**，不可点击背景关闭）。
- **标题**（21166–21171）：id `confirm-modal-title`，初始“请确认”（`text-amber-600`）。
- **消息**（21172–21177）：id `confirm-modal-message`，初始“你确定要执行此操作吗？”。
- **按钮**（21178–21188）：
  - 取消 id `confirm-modal-cancel-btn`（**无内联 onclick**，由 JS 动态绑定回调）。
  - 确认 id `confirm-modal-ok-btn`（**无内联 onclick**，由 JS 动态绑定回调）。

> **复刻要点**：这是一个通用确认对话框，回调通过 JS 动态挂载到 `ok-btn` / `cancel-btn`，而非固定函数。

---

## 15. `#session-picker-modal` — 会话管理（21192–21266）

- **容器**：`fixed ... hidden z-[1052]`；遮罩 `bg-black/60`（无 onclick）。
- **标题栏**（21200–21203）：**“会话管理”**；右侧会话计数 id `session-count-display`（空，JS 填充）。
- **创建区**（21205–21226，`bg-sky-50`）：文案“选择现有会话或创建新会话”；创建按钮 `onclick="createNewSessionFromPicker()"`，文案“创建新会话”（含 + SVG）。
- **现有会话区**（21228–21257）：
  - 小标题“现有会话”；刷新按钮 `onclick="refreshSessionPicker()"`，文案“刷新”（含刷新 SVG）。
  - 列表容器 id `session-picker-list`，`max-h-[40vh]`，初始“加载中...”。
- **底部提示**（21259–21264）：“💡 提示：每个会话都是独立的学校账号登录状态。您可以创建多个会话来管理不同的账号。”

---

## 16. `#sms-test-modal` — 短信测试发送（21268–21417）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeSMSTestModal()"`（21272–21275）。
- **标题**（21278）：**“🧪 短信测试发送”**（`text-green-600`）；关闭按钮 `onclick="closeSMSTestModal()"`（X 图标 SVG，`aria-label="按钮"`）。
- **功能说明蓝框**（21300–21308）：“💡 功能说明”，列 4 条（测试短信配置、发随机/指定验证码、界面显示验证码、记录入历史）。
- **字段**：
  - 目标手机号 id `sms-test-phone`（`tel`，`maxlength="11"` `inputmode="numeric"` `pattern="[0-9]*"`，placeholder“请输入要测试的手机号（11位）”）；标签“📱 目标手机号”；提示“⚠️ 请输入真实有效的手机号，确保能收到短信”。
  - 验证码（可选）id `sms-test-code-input`（`text`，`maxlength="8"` `inputmode="numeric"`，placeholder“留空则自动生成随机验证码”）；标签“🔢 验证码（可选）”；提示“💡 可输入4-8位数字作为测试验证码，留空则自动生成6位随机验证码”。

### 测试结果区 `#sms-test-result`（21347–21382，初始 `hidden`）

- 成功卡片（绿色渐变）：标题“测试短信发送成功！”。
  - 验证码显示 id `sms-test-code`，初始 `------`。
  - 手机号显示 id `sms-test-phone-display`，初始 `-----------`。
  - 底部提示：“💡 请检查手机是否收到包含上述验证码的短信。如果收到，说明短信配置正确。”

### 底部按钮（21384–21411）

| 按钮 | id | onclick | 文案 |
|---|---|---|---|
| 取消 | — | `closeSMSTestModal()` | 取消 |
| 发送测试短信 | `btn-send-test-sms` | `sendTestSMS()` | 发送测试短信（含发送 SVG，`btn-success`） |

- **底部说明**（21413–21415）：`测试记录会自动保存到"短信发送历史"中，场景标记为"admin_test"`。

---

## 17. `#sms-reply-logs-modal` — 短信回复记录（21425–21529）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `bg-black/70`，`onclick="closeSMSReplyLogsModal()"`（21430–21433）。
- **头部标题**（21440–21453）：渐变文字 **“💬 短信回复记录”**；关闭 `×` → `closeSMSReplyLogsModal()`。
- **说明紫框**（21456–21463）：“💡 提示：此处显示用户通过短信回复到您的短信宝号码的内容记录。”
- **筛选区**（21466–21483）：
  - 手机号筛选 id `sms-reply-phone-filter`（`text`，placeholder“输入手机号筛选（可选）”）。
  - 查询按钮 `onclick="loadSMSReplyLogs()"`，文案“🔍 查询”。
- **列表容器 `#sms-reply-logs-list`**（21486–21511，`flex-1 overflow-y-auto`）：初始为旋转加载 SVG + “加载中...”。
- **底部按钮**（21513–21527）：
  - 刷新 `onclick="loadSMSReplyLogs()"`，文案“🔄 刷新”。
  - 关闭 `onclick="closeSMSReplyLogsModal()"`，文案“关闭”。
- **数据来源**（21419–21424 注释）：`/api/sms/reply-logs`，需管理员权限。

---

## 18. `#captcha-detail-modal` — 验证码详细信息（21531–21703）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeCaptchaDetailModal()"`（21535–21538）。
- **标题**（21543）：**“🔍 验证码详细信息”**（`text-blue-600`）；关闭按钮 `onclick="closeCaptchaDetailModal()"`（X SVG，`aria-label="按钮"`）。

### 内容区 `#captcha-detail-content`（21565–21692）——多张信息卡片

| 卡片 | 行号 | 字段 id | 初始值 / 说明 |
|---|---|---|---|
| 📋 基本信息 | 21566–21599 | `detail-captcha-id`（验证码ID）、`detail-code`（验证码）、`detail-status`（状态） | 全部初始 `-` |
| ⏰ 时间信息 | 21601–21624 | `detail-created-time`（创建时间）；`detail-verified-time-container`（含 `detail-verified-time`，默认 `hidden`）；`detail-expired-time-container`（含 `detail-expired-time`，默认 `hidden`） | 初始 `-` |
| ✅ 验证信息 | 21626–21648 | 卡片 id `detail-verification-card`（默认 `hidden`）；含 `detail-user-input`（用户输入）、`detail-verification-result`（验证结果） | 初始 `-` |
| 🌐 客户端信息 | 21650–21675 | `detail-client-ip`（IP地址）、`detail-user-agent`（User Agent） | 初始 `-` |
| 🖼️ 验证码图片 | 21677–21691 | 卡片 id `detail-captcha-image-card`（默认 `hidden`）；图片挂载容器 `detail-captcha-html` | JS 注入图片 HTML |

- **底部按钮**（21694–21701）：关闭 `onclick="closeCaptchaDetailModal()"`，文案“关闭”。

> **复刻要点**：3 处默认 `hidden`（验证时间容器、过期时间容器、验证信息卡片、验证码图片卡片），由 JS 依据数据决定显隐。

---

## 19. `#create-group-modal` — 创建权限组（21705–21776）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeCreateGroupModal()"`（21709–21712）。
- **标题**（21717）：**“创建权限组”**；关闭按钮 `onclick="closeCreateGroupModal()"`，文案“关闭”。
- **字段**：
  - 权限组键名 id `new-group-key`（`text`，placeholder“例如: custom_group”，提示“英文字母、数字、下划线，用于内部标识”）。
  - 权限组名称 id `new-group-name`（`text`，placeholder“例如: 自定义权限组”，提示“显示名称，用于界面展示”）。
  - 权限设置容器 id `create-group-permissions`（`grid grid-cols-2`，JS 动态填充权限勾选项）。
- **底部按钮**（21764–21774）：取消 `onclick="closeCreateGroupModal()"`；创建 `onclick="submitCreateGroup()"`。

---

## 20. `#edit-group-permissions-modal` — 编辑权限组（21778–21828）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeEditGroupPermissionsModal()"`（21782–21785）。
- **标题**（21790–21792）：“编辑权限组: `<span id="edit-group-name">`”（组名 JS 填充）；关闭按钮 `onclick="closeEditGroupPermissionsModal()"`。
- **权限列表容器**（21806–21809）：id `edit-group-permissions-list`（`grid grid-cols-2 max-h-[50vh]`），JS 填充。
- **底部按钮**（21813–21826）：取消 `onclick="closeEditGroupPermissionsModal()"`；保存 `onclick="submitEditGroupPermissions()"`。

---

## 21. `#manage-user-permissions-modal` — 管理用户权限（21830–21891）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeManageUserPermissionsModal()"`（21834–21837）。
- **标题**（21842–21844）：“管理用户权限: `<span id="manage-user-name">`”；关闭按钮 `onclick="closeManageUserPermissionsModal()"`。
- **权限组信息蓝框**（21853–21862）：`<strong>权限组:</strong> <span id="user-base-group">`；说明“💡 以下为用户相对于权限组的差分化权限。绿色表示额外添加的权限，红色表示移除的权限。”
- **权限调整容器**（21869–21872）：id `manage-user-permissions-list`（`grid grid-cols-2 max-h-[45vh]`），JS 填充。
- **底部按钮**（21876–21889）：取消 `onclick="closeManageUserPermissionsModal()"`；保存 `onclick="submitManageUserPermissions()"`。

---

## 22. `#manage-school-accounts-modal` — 管理学校账户（PC，21893–22007）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="closeManageSchoolAccountsModal()"`（21897–21900）。
- **标题**（21906–21909）：“管理学校账户: `<span id="school-accounts-username">`”；关闭按钮 `onclick="closeManageSchoolAccountsModal()"`。
- **统计+操作区**（21918–21991，`bg-blue-50`）：
  - 账户总数 id `school-accounts-count`（初始 `0`）；提示“💡 您可以查看、编辑或删除此用户的学校账户信息”。
  - 刷新按钮 `onclick="refreshSchoolAccounts()"`，文案“刷新”（含刷新 SVG）。
  - 新增账户按钮 `onclick="addNewSchoolAccount()"`，文案“新增账户”（含 + SVG）。
- **列表容器**（21993–21996）：id `school-accounts-list`，`max-h-[50vh]`，空（JS 填充）。
- **底部按钮**（21998–22005）：关闭 `onclick="closeManageSchoolAccountsModal()"`。

---

## 23. `#mobile-user-school-accounts-modal` — 管理学校账户（移动端，22015–22239）

- **容器**：`<div id="mobile-user-school-accounts-modal" class="fixed inset-0 hidden mobile-modal z-[1055]">`（22015–22018）。**外层不加 onclick**（避免误关）。
- **背景遮罩**（22022–22025）：`bg-black/40`，`onclick="closeMobileUserSchoolAccountsModal()"`。
- **内容区**（22036–22038）：`mobile-modal-content bg-white rounded-t-3xl`，底部弹出式，`onclick="event.stopPropagation()"`（阻止冒泡）。
- **拖动指示器**（22042–22051）：`onclick="closeMobileUserSchoolAccountsModal()"`（点击可关闭）。
- **标题区**（22058–22076）：`onclick="closeMobileUserSchoolAccountsModal()"`；标题“管理学校账户: `<span id="mobile-school-accounts-username">`”。
- **统计+操作卡**（22085–22190，`bg-blue-50`）：
  - 账户总数 id `mobile-school-accounts-count`（初始 `0`）；提示“💡 您可以查看、编辑或删除此用户的学校账户信息”。
  - 刷新按钮 `onclick="mobileRefreshSchoolAccounts()"`，文案“刷新”（`flex-1 min-h-[44px]`，含刷新 SVG）。
  - 新增账号按钮 `onclick="mobileAddNewSchoolAccount()"`，文案“新增账号”（含 + SVG）。
- **列表容器**（22199–22212）：id `mobile-school-accounts-list`，`max-h-[50vh]`，初始“正在加载账户列表...”。
- **底部按钮**（22230–22235）：关闭 `onclick="closeMobileUserSchoolAccountsModal()"`（`min-h-[44px]`）。

> 该模态框含大量逐元素中文注释（22009–22238），说明移动端触控友好设计（`min-h-[44px]` 符合 iOS 人机指南），功能与 PC 端 `manage-school-accounts-modal` 一致。

---

## 24. `#edit-school-account-modal-simple` — 编辑学校账户（22242–22308）

> 注释（22241）：`修复ID冲突：重命名为 edit-school-account-modal-simple，这是简洁样式的编辑模态框（区别于现代化样式）`。

- **容器**：`fixed ... hidden z-[1055]`；遮罩 `onclick="closeEditSchoolAccountModal()"`（22246–22249）。
- **标题**（22252）：**“编辑学校账户”**（`text-amber-600`）。
- **只读信息**（22254–22269）：认证用户 id `edit-auth-username`；学校账户 id `edit-school-username`（JS 填充）。
- **字段**：
  - 密码 id `edit-school-password`（`text`，placeholder“输入新密码”）。
  - User-Agent（可选）id `edit-school-ua`（`textarea` `rows="3"`，placeholder“输入User-Agent（可选）”）。
- **底部按钮**（22296–22306）：取消 `onclick="closeEditSchoolAccountModal()"`；保存 `onclick="submitEditSchoolAccount()"`。

---

## 25. `#set-max-sessions-modal` — 设置会话限制（22310–22364）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="hideModal('set-max-sessions-modal')"`（22314–22317）。
- **标题**（22319）：**“设置会话限制”**。
- **只读信息**（22321–22336）：用户 id `sessions-username`；当前限制 id `sessions-current-max`（JS 填充）。
- **字段**：新会话限制 id `new-max-sessions`（`number` `min="0"`，placeholder“输入会话数量”，提示“0 = 无限制”）。
- **底部按钮**（22352–22362）：取消 `onclick="hideModal('set-max-sessions-modal')"`；确认 `onclick="submitSetMaxSessions()"`。

---

## 26. `#reset-user-password-modal` — 重置用户密码（22366–22424）

- **容器**：`fixed ... hidden z-[1054]`；遮罩 `onclick="hideModal('reset-user-password-modal')"`（22370–22373）。
- **标题**（22375）：**“重置用户密码”**（`text-amber-600`）。
- **目标用户**（22377–22385）：id `reset-password-username`（JS 填充）。
- **字段**：
  - 新密码 id `reset-new-password`（`password`，placeholder“输入新密码”）。
  - 确认密码 id `reset-confirm-password`（`password`，placeholder“再次输入新密码”）。
- **底部按钮**（22412–22422）：取消 `onclick="hideModal('reset-user-password-modal')"`；重置密码 `onclick="submitResetUserPassword()"`。

---

## 27. `#avatar-crop-modal` — 裁剪头像（22426–22460）

- **容器**：`fixed ... hidden z-[1055]`；遮罩 `bg-black/80`，`onclick="closeCropModal()"`（22430–22433）。
- **标题**（22437）：**“裁剪头像”**。
- **图片区**（22439–22446）：`<img id="crop-image" src="" alt="待裁剪图片">`（cropperjs 挂载目标，`max-h-96 overflow-hidden`）。
- **底部按钮**（22448–22458）：取消 `onclick="closeCropModal()"`；确认并上传 `onclick="confirmCropAndUpload()"`。

---

## 28. `#modify-phone-modal` — 修改绑定手机号（用户自助，22461–22579）

> 使用 `.modal` / `.modal-content`（CSS 类控制显隐，非 Tailwind `hidden`），`modal-content style="max-width:500px"`。

- **容器**：`<div id="modify-phone-modal" class="modal">`（22461）。
- **标题**（22464）：**“修改绑定手机号”**；关闭按钮 `onclick="closeModifyPhoneModal()"`（X SVG，`aria-label="按钮"`）。
- **字段**：

| 字段 | 行号 | id | 类型 | 关键属性 / 文案 |
|---|---|---|---|---|
| 当前手机号 | 22493–22501 | `modify-phone-current` | `tel` `readonly` | 前缀 `+86`；标签“当前手机号” |
| 验证原密码 * | 22508–22514 | `modify-phone-password` | `password` | `min-height:44px`；placeholder“请输入当前账号密码进行验证”；标签“验证原密码 *” |
| 新手机号 | 22522–22531 | `modify-phone-new` | `tel` | `inputmode="numeric"` `pattern="[0-9]*"` `maxlength="11"` `min-height:44px`；前缀 `+86`；placeholder“请输入新手机号” |
| 短信验证码 | 22540–22549 | `modify-phone-code` | `text` | `maxlength="6"` `inputmode="numeric"` `pattern="[0-9]{6}"` `min-height:44px`；placeholder“请输入验证码” |
| 发送验证码按钮 | 22550–22557 | `modify-phone-send-btn` | button | `onclick="sendModifyPhoneCode()"`，文案“发送验证码” |

- **底部按钮**（22561–22576）：
  - 确认修改 `onclick="confirmModifyPhone()"`（`btn-success flex-1`）。
  - 取消 `onclick="closeModifyPhoneModal()"`（`btn-ghost flex-1`）。

---

## 29. `#payment-modal` — 在线支付（22586–22689）

> 使用 `.modal` 类；容器注释（22581–22585）：用户输入支付金额、选择支付方式、填写商品描述，点击“立即支付”调后端 API 创建订单并跳转支付页。

- **容器**：`<div id="payment-modal" class="modal">`（22586）。
- **关闭按钮**（22592–22610）：id `payment-close-btn`（**无内联 onclick**，由 JS 绑定），右上角 X SVG，`aria-label="payment close btn"`。
- **标题**（22613–22615）：**“在线支付”**（`card-title`）。
- **字段**：

| 字段 | 行号 | id | 类型 | 关键属性 / 文案 |
|---|---|---|---|---|
| 支付金额 * | 22627–22635 | `payment-amount` | `number` | `min="0.01"` `step="0.01"` `inputmode="decimal"`；placeholder“请输入支付金额（最低0.01元）”；标签“支付金额 *” |
| 支付方式 * | 22647–22657 | 容器 `payment-methods-container` | 动态 | `space-y-2`，由 `loadPaymentMethods()` JS 动态加载；初始占位“正在加载支付方式...” |
| 商品描述 | 22670–22676 | `payment-product-name` | `text` | 默认 `value="在线支付"`；placeholder“商品描述（例如：跑步服务费用）” |

> 注释（22648–22653）说明支付方式动态加载：管理员可在配置面板启用/禁用、新增只需改 JS、支持未来扩展（QQ钱包、云闪付等）。

- **底部按钮**（22680–22687）：
  - 取消 id `payment-cancel-btn`（**无内联 onclick**，JS 绑定），`btn-ghost`，文案“取消”。
  - 立即支付 id `payment-submit-btn`（**无内联 onclick**，JS 绑定），`btn-primary`，文案“立即支付”。

> **复刻要点**：此弹窗关闭/取消/提交按钮均**无内联 onclick**，全部由 `scripts/main.new.js` 事件绑定（`addEventListener`）驱动。

---

## 30. `#orders-modal` — 我的订单（22697–22801）

> 使用 `.modal` 类；容器注释（22691–22696）：显示用户所有支付订单（订单号/金额/支付方式/状态/创建时间），提供查询状态和继续支付功能。

- **容器**：`<div id="orders-modal" class="modal">`（22697），内容容器 `max-w-2xl max-h-[90vh] flex flex-col`。
- **关闭按钮**（22703–22720）：id `orders-close-btn`（**无内联 onclick**），右上角 X SVG，`aria-label="orders close btn"`，`z-10`。
- **标题栏**（22722–22732）：标题 **“我的订单”**（`card-title`）；刷新按钮 id `orders-refresh-btn`（**无内联 onclick**），文案“刷新”。

### 状态筛选标签（22734–22764，`.orders-filter-btn`）

| 标签 | 行号 | `data-status` | 文案 | 初始激活 |
|---|---|---|---|---|
| 全部 | 22737–22742 | `all` | 全部 | 是（`active`） |
| 待支付 | 22744–22749 | `pending` | 待支付 | 否 |
| 已支付 | 22751–22756 | `paid` | 已支付 | 否 |
| 已关闭 | 22758–22763 | `closed` | 已关闭 | 否 |

> 4 个筛选按钮共用类 `orders-filter-btn`，通过 `data-status` 区分；JS 委托监听点击切换 `active`。

### 列表 + 分页

| 元素 | 行号 | id | 说明 |
|---|---|---|---|
| 订单列表容器 | 22766–22773 | `orders-list-container` | `flex-1 overflow-y-auto`，初始“加载中...” |
| 分页容器 | 22776–22799 | `orders-pagination` | — |
| 上一页 | 22781–22787 | `orders-prev-btn` | 初始 `disabled`，无内联 onclick（JS 绑定） |
| 页码显示 | 22788–22791 | `orders-page-info` | 初始“第 1 页” |
| 下一页 | 22793–22798 | `orders-next-btn` | 无内联 onclick（JS 绑定） |

> **复刻要点**：订单弹窗所有按钮（关闭/刷新/筛选/上下页）均**无内联 onclick**，由 JS 事件绑定；筛选靠 `data-status` 数据属性。

---

## 31. 文件末尾内联 `<script>` — 无障碍名称自动注入器（22803–22892）

一段 IIFE（立即执行函数），在 DOM 加载后自动为**缺少可访问名称**的表单控件/按钮注入 `aria-label` / `title` / `placeholder`。

### 逻辑分解

- **`getLabelTextFor(element)`**（22806–22831）：按优先级查找关联 label 文本：
  1. `label[for="<id>"]`（22809–22812）；
  2. 紧邻的前置兄弟 `<label>`（22814–22820）；
  3. 祖先中的 `<label>`（`element.closest("label")`，22822–22823）；
  4. 同一父容器内首个 `<label>`（22825–22829）；
  5. 均无则返回 `null`。

- **`ensureAccessibleNames()`**（22833–22884）：
  - 选取全部 `input, textarea, select, button`（22835–22837）。
  - 判定是否已有名称 `hasName`：`aria-label` / `aria-labelledby` / `title` / 按钮有可见文本 / `placeholder` / (`role="img"` 且 `alt`)（22840–22848）。
  - 若无名称，取 `labelText`：
    - **按钮**：仅当无可见文本时设 `aria-label`（22853–22857）。
    - **input/textarea/select**：非 `file`/`password` 类型才设 `placeholder`；再设 `title` 与 `aria-label`（22858–22872）。
    - 若找不到 label 文本，为无 `aria-label` 的按钮兜底设 `aria-label="按钮"`（22874–22878）。
  - 统计修复数 `fixed`，>0 时 `console.log("Accessibility helper: fixed", fixed, "elements")`（22882–22883）。

- **执行时机**（22886–22890）：`document.readyState === "loading"` 时挂 `DOMContentLoaded`，否则立即执行。

- **22892–22894**：`</script>` / `</body>` / `</html>`（文件结束）。

> **复刻要点**：本段落中大量表单控件的 `aria-label` / `title` / `placeholder="admin modify phone current"` 等“机械填充值”，正是此脚本或其构建期等价物注入的产物；Vue 版可用组件层的 label 关联替代，无需此运行时补丁。

---

## 复刻注意事项汇总

1. **两套显隐机制并存**：模态框 1–27 用 Tailwind `hidden` + `fixed inset-0`（JS 增删 `hidden`）；模态框 28–30 用自定义 `.modal` / `.modal-content` 类（CSS 动画，JS 用 `.show` 或 `style.display`）。Vue 版需区分。
2. **z-index 层级约定**：`confirm-modal`=50000（最高），`add-watermark-user-modal`=20001，其余在 1052–1055。`confirm-modal` 与 `session-picker-modal` 的遮罩**无 onclick**（不可点背景关闭）。
3. **内联事件 vs JS 绑定**：绝大多数按钮用内联 `onclick`；但 `confirm-modal`、`payment-modal`、`orders-modal` 的按钮**无内联 onclick**，回调全靠 `scripts/main.new.js` 的 `addEventListener` 动态绑定。
4. **默认隐藏子元素**：`captcha-detail-modal` 内 4 处容器默认 `hidden`（验证时间/过期时间/验证信息卡片/验证码图片卡片）；`sms-test-result` 默认 `hidden`；`user-logs-secondary-modal` 的 audit 内容默认 `hidden`。
5. **`_modal` 后缀面板**（定价/水印/账单/账单日志/恢复账号）属于上文管理模态框 `#admin-modal-content` 的标签子页，非独立顶层模态框。

---

## 关键 JS 函数名索引（本段引用）

- **定价**：`loadPricingConfig()`、`savePricingConfig()`
- **水印控制**：`updateWatermarkDefaultLabel()`、`openAddWatermarkUserModal()`、`loadWatermarkControlConfig()`、`saveWatermarkControlConfig()`、`refreshWatermarkUserList()`、`closeAddWatermarkUserModal()`、`filterWatermarkUsers()`
- **账单**：`loadAdminBillingList()`、`adminAddBillingDialog()`；`loadAdminBillingLogs([page])`、`loadAdminBillingLogsPrev()`、`loadAdminBillingLogsNext()`；`loadRemovedAccountsList()`
- **提醒**：`closeReminderEditModal()`、`saveReminder()`
- **短信**：`closeSMSBalanceModal()`、`loadSMSHistory()`、`closeSMSHistoryModal()`、`addManualVerificationCode()`、`loadVerificationCodes()`、`closeVerificationCodesModal()`、`sendTestSMS()`、`closeSMSTestModal()`、`loadSMSReplyLogs()`、`closeSMSReplyLogsModal()`
- **验证码详情**：`closeCaptchaDetailModal()`
- **用户管理**：`submitAdminModifyNickname()`/`closeAdminModifyNicknameModal()`；`sendAdminModifyPhoneCode()`/`submitAdminModifyPhone()`/`closeAdminModifyPhoneModal()`；`switchUserLogTab('login'|'audit')`/`closeUserLogsSecondaryModal()`；`submitSetMaxSessions()`/`submitResetUserPassword()`/`hideModal(id)`
- **权限组**：`submitCreateGroup()`/`closeCreateGroupModal()`；`submitEditGroupPermissions()`/`closeEditGroupPermissionsModal()`；`submitManageUserPermissions()`/`closeManageUserPermissionsModal()`
- **学校账户**：`refreshSchoolAccounts()`/`addNewSchoolAccount()`/`closeManageSchoolAccountsModal()`；移动端 `mobileRefreshSchoolAccounts()`/`mobileAddNewSchoolAccount()`/`closeMobileUserSchoolAccountsModal()`；`submitEditSchoolAccount()`/`closeEditSchoolAccountModal()`
- **会话**：`createNewSessionFromPicker()`、`refreshSessionPicker()`
- **头像**：`closeCropModal()`、`confirmCropAndUpload()`
- **修改手机号（用户）**：`sendModifyPhoneCode()`、`confirmModifyPhone()`、`closeModifyPhoneModal()`
- **支付/订单**：`loadPaymentMethods()`（动态加载支付方式）；`payment-modal` / `orders-modal` 其余按钮由 JS 事件绑定（无固定内联函数名）
