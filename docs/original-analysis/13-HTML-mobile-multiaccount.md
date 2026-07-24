# 13 · 移动端多账号应用 + 共享模态框 + PC 管理面板（index.html 10482–19524）

> 覆盖范围：`index.html` 第 **10482** 行至第 **19524** 行（约 9000 行）。
> 逐行、无遗漏解析，供 Vue 重构版完整复刻对照。
> 生成时间：2026-07-14

---

## 0. 段落总体地图

本段落起点是移动端多账号应用（`#mobile-multi-account-app`），但实际跨越到 PC 端管理面板的开头。按行号顺序，共分五大区块：

| 区块 | 行号范围 | 容器 | 说明 |
|---|---|---|---|
| A | 10482–11494 | `#mobile-multi-account-app` … `</main>` | 移动端多账号应用（5 个 panel） |
| B | 11500–12637 | 一组 `#mobile-*-modal` | 移动端 13 个模态框 |
| C | 12643–13314 | `#mobile-sidebar-*` / `#mobile-beian-footer` | 移动端侧边栏（单/多账号）+ 备案 footer |
| D | 13317–14394 | 一组顶层模态框 | 会话选择 / 通知 / 告警 / 支付相关（PC+移动共享） |
| E | 14401–19524 | `#admin-panel-modal` | **PC 端管理面板模态框**（含用户/权限组/日志/健康/个人信息/短信/IP封禁/验证码/定时提醒/SSL/CDN/密码恢复/支付日志/支付设置等全套管理 UI）。19524 行为 `#admin-pricing-panel_modal` 起始，其内容延续到本段之外。 |

> 注意：任务描述中提到的"管理面板全套功能（用户管理、日志、健康、短信、IP封禁、验证码、定时提醒、权限组、个人信息等）"，其**静态 HTML 模板**位于区块 E 的 PC `#admin-panel-modal` 内。移动端的管理面板（`#mobile-admin-panel-modal`，见区块 B）为空壳，内容由 JS 动态注入。

---

## A. 移动端多账号应用 `#mobile-multi-account-app`（10482–11493）

- 容器：`<div id="mobile-multi-account-app" class="space-y-4 hidden">`（10482）
- 初始可见性：`hidden`（默认隐藏，进入多账号模式时显示）
- 子面板均为 `.mobile-card`，通过侧边栏 `switchMobilePanel(id,'multi')` 切换显隐。

### A1. 返回首页条（10483–10504）
- 外层 `.mobile-card py-3`，`style="display:none"`（默认隐藏）。
- 按钮 `#multi_exit_account`：`onclick="exitMobileMultiAccount()"`，文案「返回首页」（左箭头图标）。

### A2. 账号管理面板 `#mobile-multi-account-panel`（10506–10850）
标题区：账号图标 + `<h3>账号管理</h3>`；右侧计数徽章 `#mobile-multi-account-count`（初始「0 个账号」）。

**添加账号卡（10537–10627）** 标题「➕ 添加账号」：
- `<select id="mobile-multi-config-user-select">`：首项 `<option value="">-- 请选择配置文件 --</option>`（其余由 JS 填充）。
- 按钮网格（grid-cols-3）：
  - 「添加选中」`onclick="addMobileSelectedConfig()"`
  - 「添加全部」`onclick="addMobileAllConfigs()"`
  - 「手动添加」`#mobile_multi_account_manual_input_button` `onclick="openManualAccountModal()"` `style="display:none"`

**全选/启停条（10629–10661）**：
- `<input type="checkbox" id="mobile-select-all-accounts" onchange="mobileToggleSelectAllAccounts()">` + 文案「✅ 全选账号」
- 「▶️ 启动」`onclick="mobileStartSelectedAccounts()"`
- 「⏹️ 停止」`onclick="mobileStopSelectedAccounts()"`

**账号列表容器（10663–10685）**：`#mobile-multi-account-list`（`space-y-3 overflow-y-auto`）。初始空状态：图标 + 「暂无账号，请先添加」+「从上方选择配置文件或手动添加」。

**批量操作卡（10687–10849）** 标题「🔧 批量操作」，容器 `#mobile-multi-account-batch-operations`：
- 第一行（grid-cols-3）：「导入」`importMobileAccountList()`、「导出」`exportMobileAccountList()`、「模板」`downloadMobileAccountTemplate()`
- 第二行（grid-cols-2）：「刷新选中」`mobileRefreshSelectedAccounts()`、「刷新全部」`mobileRefreshAllAccounts()`
- 第三行（grid-cols-2）：「删除选中」`deleteMobileSelectedAccounts()`、「删除全部」`deleteMobileAllAccounts()`

### A3. 批量控制面板 `#mobile-multi-control-panel`（10852–11184）
标题「批量控制」（闪电图标）。

- **全局状态卡** `#mobile-multi-global-status-panel`（10879）：文案「🎯 全局状态」，状态徽章 `#mobile-multi-global-status`（初始「就绪」）。
- **快速操作卡**（10912）标题「快速操作」，grid-cols-3：
  - 「▶️ 全部启动」`mobileStartAllAccounts()`
  - 「⏹️ 全部停止」`mobileStopAllAccounts()`
  - 「🔄 全部刷新」`mobileRefreshAllAccounts()`
- **运行统计卡** `#mobile-multi-running-stats-panel-2`（11010）标题「📊 运行统计」，grid-cols-3：
  - 运行中 `#mobile-multi-running-count`（0，绿色）
  - 已暂停 `#mobile-multi-paused-count`（0，`style="display:none"` 隐藏）
  - 已停止 `#mobile-multi-stopped-count`（0，灰色）
- **批量执行选项（11114–11183）**：
  - 随机启动延迟块：`<input type="checkbox" id="mobile-multi-random-delay-check" checked>`「启用随机启动延迟」；范围「延迟范围：」`#mobile-multi-random-delay-min`（value=0,min=0,max=300）~ `#mobile-multi-random-delay-max`（value=300,min=0,max=600）秒。
  - `<input type="checkbox" id="mobile-multi-only-incomplete-check" checked>`「仅启动未完成任务」。
  - 注释掉的「忽略任务具体时间」复选框（`#mobile-multi-param-ignore_task_time`，已禁用）。

### A4. 地图面板 `#mobile-multi-map-panel`（11186–11268）
- `.mobile-card p-0 overflow-hidden h-screen`。
- 地图容器 `#mobile-multi-map-container`（`height:calc(100vh - 60px)`），初始占位「地图加载中...」。
- 复位按钮 `#mobile-multi-map-reset-btn`（`style="display:none"`）`onclick="resetMultiMapView()"` title「复位视角」。
- 底部控制条（grid 4 按钮）：「放大 +」`mobileMultiZoomIn()`、「缩小 -」`mobileMultiZoomOut()`、「适应 ⊡」`mobileMultiFitView()`、「复位 ⊙」`resetMultiMapView()`。

### A5. 全局参数面板 `#mobile-multi-settings-panel`（11273–11420）
- `.mobile-card hidden`（初始隐藏）。标题「全局参数」。
- **自动签到设置区（amber 卡, 11299–11391）**：
  - 开关 `<input type="checkbox" id="mobile-multi-auto_attendance_enabled" data-key="auto_attendance_enabled" class="sr-only peer">`（滑动开关），文案「开启自动签到」，提示「⏱ 自动签到启用后将在 120 分钟内自动关闭。」
  - `<input type="number" id="mobile-multi-auto_attendance_refresh_s" data-key="auto_attendance_refresh_s" min="10" step="5">`「刷新间隔（秒）」，提示「最小10秒，默认15秒」。
  - `<input type="number" id="mobile-multi-attendance_user_radius_m" data-key="attendance_user_radius_m" min="0" step="1">`「随机半径（米）」，提示「0为精确签到」及超限警告。
- 动态参数容器 `#mobile-multi-global-params-container`（11393，JS 填充）。
- 底部「保存全局设置」按钮 `onclick="saveMobileMultiGlobalSettings()"`。

### A6. 全局日志面板 `#mobile-multi-log-panel`（11422–11492）
- `.mobile-card hidden`。标题「全局日志」。
- `<textarea id="mobile-multi-log-text" readonly placeholder="等待日志输出...">`。
- 按钮：「清空日志」`clearMobileMultiLog()`、「滚到底部」`scrollMobileMultiLogToBottom()`。

> 11493 `</div>` 关闭 `#mobile-multi-account-app`；11494 `</main>` 关闭移动端主内容区。

---

## B. 移动端模态框组（11500–12637）

所有 `.mobile-modal z-50` 均以底部弹出（`.mobile-modal-content rounded-t-3xl`），点击遮罩关闭；顶部有拖动指示条。

| # | id | 行号 | 打开/关闭函数 | 关键元素 |
|---|---|---|---|---|
| B1 | `#mobile-user-details-modal` | 11500 | `toggleMobileUserDetails(false)` | 内容 `#mobile-user-details-content`；底部「返回登录」（`toggleMobileUserDetails(false); mobileLogout();`）、「关闭」 |
| B2 | `#mobile-task-details-modal` | 11561 | `toggleMobileTaskDetails(false)` | 内容 `#mobile-task-details-content`；「关闭」 |
| B3 | `#mobile-history-modal` | 11601 | `closeMobileHistoryModal()` | 标题「历史记录」、任务名 `#mobile-history-task-name`、列表 `#mobile-history-list-content`（初始「加载中...」） |
| B4 | `#mobile-track-modal` | 11646 | `closeMobileTrackModal()` | 标题「跑步路径」、时间 `#mobile-track-time`；摘要 `#mobile-track-summary`（距离 `#mobile-track-distance`、时长 `#mobile-track-duration`、配速 `#mobile-track-pace`）；地图 `#mobile-track-map-container`；缩放按钮 `mobileTrackZoomIn()`/`mobileTrackZoomOut()`/`mobileTrackFitView()`；「关闭」 |
| B5 | `#mobile-map-attendance-modal` | 11764 | `closeMobileMapAttendanceModal()` | 标题「📍 地图选点签到」；坐标显示 `#mobile-map-attendance-coords`（初始「未选择」）；地图 `#mobile-map-attendance-container`；「取消」+ 确认按钮 `#mobile-map-attendance-confirm-btn`（`onclick="confirmMobileMapAttendance()"` disabled，文案「确认签到」） |
| B6 | `#mobile-captcha-history-modal` | 11919 | `closeMobileCaptchaHistoryModal()` | 标题「📜 验证码历史记录」；刷新 `loadMobileCaptchaHistoryModal()`；日期 `#mobile-captcha-history-modal-date`、状态 `#mobile-captcha-history-modal-status`（选项：全部/✅验证成功 verified_success/❌验证失败 verified_failed/🧪测试生成 test_generated/⏳待验证 created/⏰已过期 expired）；列表 `#mobile-captcha-history-modal-list`；「关闭」 |
| B7 | `#mobile-notifications-modal` | 12001 | `toggleMobileNotifications(false)` | 标题「通知中心」；内容 `#mobile-notifications-content`；底部「刷新」`#mobile-refresh-notifications-modal-btn`、「一键已读」`#mobile-mark-all-read-modal-btn`、「关闭」 |
| B8 | `#mobile-admin-panel-modal` | 12054 | `toggleMobileAdminPanel(false)` | 标题「管理面板」；tab 导航 `#mobile-admin-tabs-nav`（JS 填充）；内容 `#mobile-admin-panel-content`（初始「加载中...」）；「关闭」 |
| B9 | `#mobile-account-params-modal` | 12117 | `closeMobileAccountParams()` | 标题 `#mobile-account-params-title`（「账号参数设置」）；容器 `#mobile-account-params-container`；底部「取消」+ 保存 `#mobile-save-account-params-btn` |
| B10 | `#mobile-manual-account-modal` | 12165 | `closeManualAccountModal()` | 标题「手动添加账号」；`#manual-account-username`（用户名）、`#manual-account-password`（密码）；提示卡；「取消」+「添加」`confirmManualAccountAdd()` |
| B11 | `#mobile-create-user-modal` | 12256 | `closeMobileCreateUserModal()`（z-[60]） | 标题「创建新用户」；`#mobile-new-username`（账号,必填）、`#mobile-new-password`（密码,`type="txt"`,必填）、`#mobile-new-nickname`（昵称）、`#mobile-new-phone`（手机号,+86,maxlength=11）；验证码组 `#mobile-new-sms-group`（`display:none`）内 `#mobile-new-sms-code` + 发送按钮 `#mobile-new-send-code-btn` `onclick="sendMobileNewUserCode()"`；底部「取消」+「立即创建」`#mobile-new-user-confirm-btn` `onclick="submitMobileCreateUser()"` |
| B12 | `#mobile-more-menu-modal` | 12404 | `toggleMobileMoreMenu(false)` | 标题「更多功能」；四项：签到管理（切 `mobile-notification-panel`→`switchMobileNotifTab('attendance')`）、管理面板（`openMobileAdminPanelUnified('single')`）、我的资料（`toggleMobileUserDetails(true)`）、退出登录（`mobileLogout()`）；底部「关闭」 |
| B13 | `#mobile-confirm-modal` | 12556 | 自定义确认框（z-[60]） | 标题 `#mobile-confirm-title`（「确认操作」）、消息 `#mobile-confirm-message`（「确定要执行此操作吗？」）、取消 `#mobile-confirm-cancel-btn`、确认 `#mobile-confirm-ok-btn` |

---

## C. 移动端侧边栏与备案 footer（12643–13314）

### C1. 遮罩 `#mobile-sidebar-backdrop`（12643）
`onclick="closeMobileSidebar()"`。

### C2. 单账号侧边栏 `#mobile-sidebar-single-account`（12649–13018）
`<nav class="mobile-sidebar w-[200px] hidden">`，头部品牌「跑步助手」。菜单项（`.mobile-sidebar-item`，均 `onclick=... closeMobileSidebar(); return false;`）：

| 文案 | 目标/动作 | id |
|---|---|---|
| 控制 | `switchMobileSinglePanel('mobile-control-panel')` | — |
| 地图 | `switchMobileSinglePanel('mobile-map-panel')` | — |
| 任务 | `switchMobileSinglePanel('mobile-task-panel')` | — |
| 任务详情 | `switchMobileSinglePanel('mobile-task-details-panel')` | `#mobile-sidebar-task-details-link` |
| 通知 | `switchMobileSinglePanel('mobile-notification-panel')` | — |
| 签到 | `switchMobileSinglePanel('mobile-attendance-panel')` | — |
| 日志 | `switchMobileSinglePanel('mobile-log-panel')` | — |
| 打卡点 | `switchMobileSinglePanel('mobile-checkpoints-panel')` | — |
| 历史记录 | `switchMobileSinglePanel('mobile-task-history-panel')` | — |
| 管理 | `openMobileAdminPanelUnified('single')` | `#mobile-sidebar-admin-link` |
| 设置 | `switchMobileSinglePanel('mobile-settings-panel')` | — |
| 我的资料（`hidden`） | `switchMobileSinglePanel('mobile-profile-panel')` | — |
| 我的 | `switchMobileSinglePanel('mobile-profile-panel')` | `#mobile-sidebar-user-details-link` |
| 返回（`.danger`） | `closeMobileSidebar(); exitMobileSingleAccountSafe();` | `#mobile-single-back-button` |

### C3. 多账号侧边栏 `#mobile-sidebar-multi-account`（13020–13209）
`<nav class="mobile-sidebar hidden">`，头部品牌「跑步助手」。菜单项（`switchMobilePanel(id,'multi'); closeMobileSidebar(); return false;`）：

| 文案 | 目标/动作 | id |
|---|---|---|
| 控制 | `switchMobilePanel('mobile-multi-control-panel','multi')` | — |
| 地图 | `switchMobilePanel('mobile-multi-map-panel','multi')` | — |
| 账号 | `switchMobilePanel('mobile-multi-account-panel','multi')` | — |
| 管理 | `openMobileAdminPanelUnified('multi')` | `#mobile_multi_admin_panel_bnt` |
| 设置 | `switchMobilePanel('mobile-multi-settings-panel','multi')` | `#mobile_multi_settings_panel_bnt` |
| 日志 | `switchMobilePanel('mobile-multi-log-panel','multi')` | `#mobile_multi_log_panel_bnt` |
| 返回（`.danger`） | `closeMobileSidebar(); exitMobileMultiAccount();` | `#mobile-multi-back-button` |

### C4. 备案 footer `#mobile-beian-footer`（13235–13314）
- 容器**无** `hidden`（始终占位以稳定布局）。
- ICP 链接 `#mobile-icp-beian-link`（`href="https://beian.miit.gov.cn"`, `display:none`），文本容器 `#mobile-icp-beian-text`。
- 公安备案链接 `#mobile-police-beian-link`（`href="https://beian.mps.gov.cn"`, `display:none`），文本 `#mobile-police-beian-text`。
- 由 `updateBeianSection("mobile-")` 依后端配置控制显隐。

> 13315 `</div>` 关闭 `#mobile-container`。

---

## D. 顶层共享模态框（13317–14394）

### D1. `#mobile-session-picker-modal`（13317–13404）
- `.fixed inset-0 hidden mobile-modal`，**外层 `onclick="window.location.reload()"`**（注意：非 `closeMobileSessionPicker`，拖动条才调 `closeMobileSessionPicker()`）。
- 标题「会话管理」、计数 `#mobile-session-picker-count-display`。
- 「创建新会话」`#mobile-create-session-picker-btn` `onclick="createNewSessionFromPicker()"`。
- 刷新按钮 `refreshMobileSessionPicker()`；列表 `#mobile-session-picker-list`（初始「加载中...」）。
- 底部提示文案（每个会话独立学校账号登录状态）。

### D2. `#account-params-modal`（13406–13448）
- PC 版账号参数设置。遮罩 `onclick` 内联移除 `hidden`/`flex`/`modal-visible`。
- 标题 `#account-params-title`「账号参数设置」；容器 `#account-params-container`；「关闭」（内联）+「保存」`#save-account-params-btn`。

### D3. `#notifications-modal`（13450–13489）
- PC 通知中心。标题「通知中心」；内容 `#notifications-content`；「刷新」`#refresh-notifications-btn`、「一键已读」`#mark-all-read-btn`、「关闭」`toggleNotifications(false)`。

### D4. `#alert-modal`（13491–13518, z-[50000]）
- 遮罩 `closeModalAlert()`；标题 `#alert-modal-title`（「操作失败」）、消息 `#alert-modal-message`、关闭 `#alert-modal-close-btn`。

### D5. `#missing-password-modal`（13521–13554, z-[51000]）
- 遮罩 `closeMissingPasswordModal()`；标题 `#missing-password-modal-title`「账号缺少密码」、消息 `#missing-password-message`。
- 三按钮：`#missing-pass-complete-btn`「补全当前账号密码」、`#missing-pass-skip-btn`「跳过当前账号」、`#missing-pass-abort-btn`「放弃补全」。

### D6. `#payment-method-modal`（13562–13863, z-[20001]）
添加/编辑支付方式（需 modify_config）。标题 `#payment-method-modal-title`「添加支付方式」，关闭 `closePaymentMethodModal()`。
- `#payment-method-code`（代码,必填）、`#payment-method-name`（显示名称,必填）。
- Logo 类型单选：`#logo-type-svg`(value=svg,checked)、`#logo-type-image`(value=image)，均 `onchange="toggleLogoInput()"`；
  - SVG 容器 `#svg-input-container` 内 `<textarea id="payment-method-svg">`；
  - 图片容器 `#image-input-container`（`hidden`）内 `#payment-method-image`。
- `#payment-method-description`（描述）。
- 样式：`#payment-method-border-color`（边框颜色，8 色 hover:border-*）、`#payment-method-text-color`（文字颜色，8 色 text-*）。
- 错误区 `#payment-method-error`（hidden）。
- 底部「取消」`closePaymentMethodModal()`、「保存」`savePaymentMethod()`。

### D7. `#admin-order-detail-modal_overlay`（13866–14141, z-[20001]）
订单详情弹窗。遮罩 `closeOrderDetailModal(event)`；标题「订单详情」，关闭 `closeOrderDetailModal()`。
- 卡片：订单号信息（`#admin-detail-order-id_modal`、`#admin-detail-trade-no_modal`、`#admin-detail-api-trade-no_modal`）；金额状态（`#admin-detail-status_modal`、`#admin-detail-amount_modal`、`#admin-detail-refundmoney_modal`、`#admin-detail-pay-type_modal`）；用户信息（`#admin-detail-username_modal`、`#admin-detail-buyer_modal`、`#admin-detail-product-name_modal`、`#admin-detail-clientip_modal`）；时间信息（`#admin-detail-created-at_modal`、`#admin-detail-paid-time_modal`、`#admin-detail-synced-from-platform_modal`、`#admin-detail-synced-time_modal`）；业务扩展参数（`#admin-detail-param_modal`）。
- 底部按钮：「复制单号」`copyOrderTradeNo()`、「本地刷新」`refreshOrderDetailLocal()`、「从平台刷新」`refreshOrderDetailFromPlatform()`、「关闭」`closeOrderDetailModal()`（移动/桌面各一）。

### D8. `#admin-payment-log-detail-modal`（14158–14394, z-[51]）
支付日志详情。关闭 `closePaymentLogDetailModal()`。
- 加载态 `#log-detail-loading`、错误态 `#log-detail-error`（消息 `#log-detail-error-message`）、内容 `#log-detail-content`。
- 基本信息：`#log-detail-datetime`、`#log-detail-action`、`#log-detail-user-id`、`#log-detail-order-id`、`#log-detail-client-ip`、`#log-detail-amount`。
- 完整数据 `<pre id="log-detail-json">`。底部「关闭」`closePaymentLogDetailModal()`。

---

## E. PC 端管理面板 `#admin-panel-modal`（14401–19524→）

- 容器：`<div id="admin-panel-modal" class="fixed inset-0 hidden items-center justify-center z-50">`（14401）。
- 初始 `hidden`。遮罩 `onclick="toggleAdminPanel(false)"`。
- 面板卡：`w-[65rem] max-h-[85vh]`，标题「管理面板」，右上关闭 `#admin-modal-close-btn` `onclick="toggleAdminPanel(false)"`。

### E1. Tab 导航栏（14465–15023）
一排 tab 按钮（多数 `style="display:none"`，按权限由 JS 显隐）。部分按钮 `onclick` 直接调 `switchAdminTab(...)`，其余在 JS 中绑定。

| tab 按钮 id | 文案 | 初始 display | onclick |
|---|---|---|---|
| `#admin-tab-users_modal` | 用户管理 | none（默认激活样式） | （JS 绑定） |
| `#admin-tab-groups_modal` | 权限组 | none | （JS） |
| `#admin-tab-logs_modal` | 日志查看 | none | （JS） |
| `#admin-tab-health_modal` | 系统状态 | none | （JS） |
| `#admin-tab-profile_modal` | 个人信息 | 显示 | （JS） |
| `#admin-tab-sessions_modal` | 会话管理 | 显示 | （JS） |
| `#admin-tab-messages_modal` | 留言板 | 显示 | （JS） |
| `#admin-tab-ipban_modal` | IP封禁 | none | （JS） |
| `#admin-tab-sms_modal` | 短信配置 | none | （JS） |
| `#admin-tab-config_modal` | 系统配置 | none | （JS） |
| `#admin-tab-captcha_modal` | 验证码管理 | 显示 | （JS） |
| `#admin-tab-reminders_modal` | 定时提醒 | none | （JS） |
| `#admin-tab-ssl_modal` | HTTPS设置 | none | （JS） |
| `#admin-tab-cdn_modal` | CDN缓存 | none | （JS） |
| `#admin-tab-bruteforce_modal` | 密码恢复 | none | （JS，超管） |
| `#admin-tab-overdue_modal` | 欠费查询 | （整块被注释） | `switchAdminTab('overdue')` |
| `#admin-tab-payment-logs_modal` | 支付日志 | none | `switchAdminTab('payment-logs')` |
| `#admin-tab-payment-settings_modal` | 支付设置 | none | `switchAdminTab('payment-settings')` |
| `#admin-tab-pricing_modal` | 价格设置 | none | `switchAdminTab('pricing')` |
| `#admin-tab-watermark-control_modal` | 水印控制 | 显示 | `switchAdminTab('watermark-control')` |
| `#admin-tab-billing_modal` | 账单管理 | 显示 | `switchAdminTab('admin-billing')` |
| `#admin-tab-billing-logs_modal` | 账单日志 | 显示 | `switchAdminTab('admin-billing-logs')` |
| `#admin-tab-restore-account_modal` | 恢复账号 | 显示 | `switchAdminTab('restore-account')` |

> 支付日志 tab 显示逻辑：`shouldShowPaymentLogs = isAdmin || requirePayment`（见注释 14816–14835）。

### E2. 滚动内容区（15025 `<div class="overflow-x-hidden flex-grow min-h-0">` … 17344 `</div>`）
以下面板均为该滚动容器直接子级，`switchAdminTab` 控制 `hidden`。

#### 用户管理 `#admin-users-panel_modal`（15026–15100，默认显示）
- 头部按钮：`#admin-view-school-accounts_modal`「查看 School Accounts」（`display:none`）、`#admin-create-user_modal`「新增用户」、`#admin-refresh-users_modal`「刷新」。
- 搜索栏：`#admin-users-search-input_modal`（placeholder「搜索昵称 / 用户名 / 手机号 / 学校账号」）+ `#admin-users-search-btn_modal`「搜索」`onclick="loadAdminUsers()"`。
- 排序：`#admin-users-sort-field_modal` `onchange="resortAdminUsers()"`（选项：created_at 创建时间 / auth_username 用户名 / nickname 昵称 / last_login 最后登录时间 / max_sessions 会话限制数量 / available_runs 可用次数 / tfa 2FA）；方向按钮 `#admin-users-sort-dir_modal` `onclick="toggleAdminUsersSort()"` `data-dir="desc"`（「↓ 降序」）。
- 列表 `#admin-users-list_modal`（初始「加载中...」）。

#### 权限组 `#admin-groups-panel_modal`（15102–15126，hidden）
- `#admin-create-group_modal`「新增权限组」、`#admin-refresh-groups_modal`「刷新」；列表 `#admin-groups-list_modal`。

#### 日志查看 `#admin-logs-panel_modal`（15128–15211，hidden）
- 过滤：`#log-level-filter_modal`（all/debug/info/warning/error）、`#log-keyword-filter_modal`（关键词）、`#log-limit-select_modal`（每页 100/200/500/1000 行）、`#admin-refresh-logs_modal`「刷新」。
- 内容 `<pre id="admin-logs-content_modal">`（暗底绿字）。
- 分页 `#admin-logs-pagination`：`#log-prev-page`「上一页」、`#log-page-select`（页码 select）、`#log-page-total`（「(共 0 行)」）、`#log-next-page`「下一页」。

#### 会话管理 `#admin-sessions-panel_modal`（15213–15251，hidden）
- 上帝模式开关 `#god-mode-toggle_modal`（`display:none`）内 `#god-mode-checkbox_modal`「查看所有会话」；计数 `#admin-session-count-display`；`#admin-refresh-sessions_modal`「刷新」。
- 列表 `#admin-sessions-list_modal`。

#### 系统健康 `#admin-health-panel_modal`（15253–15285，hidden）
- 自动刷新开关 `#health-auto-refresh-toggle`（checked，「自动刷新(5秒)」）+ 倒计时 `#health-countdown-display`；`#admin-refresh-health_modal`「手动刷新」。
- 内容 `#admin-health-content_modal`。

#### 个人信息 `#admin-profile-panel_modal`（15287–15793，hidden）
- 头部「个人信息」+ `#admin-refresh-profile_modal`「刷新」。
- 内容 `#admin-profile-content_modal`：
  - **头像卡**：`<img id="profile-avatar-display">`（onerror 内联占位 SVG）；隐藏文件 `#profile-avatar-file` `onchange="previewAvatar(event)"`；「上传头像」按钮触发点击。
  - **基本信息卡**：剩余次数容器 `#admin-profile-available-runs-container`（hidden）内 `#admin-profile-available-runs-text`；`#profile-auth-username`（用户名, readonly）；`#profile-nickname`（昵称）；「保存基本信息」`updateBasicInfo()`；手机号 `#profile-phone`（readonly）+「修改手机号」`#profile-modify-phone-btn` `onclick="modifyPhone()"`；提示 `#profile-phone-hint`。
  - **修改密码卡**：密码验证区 `#pc-password-verify-section` 内 `#profile-current-password` + 忘记密码提示 `#pc-forgot-password-hint`（`#pc-sms-toggle-btn` `onclick="toggleSmsVerifyMode('pc')"`）；短信验证区 `#pc-sms-verify-section`（hidden）内 `#pc-password-sms-code` + `#pc-send-sms-btn` `onclick="sendPasswordResetSmsCode('pc')"` + 返回按钮；`#profile-new-password`、`#profile-confirm-password`；「修改密码」`updatePassword()`。
  - **2FA 卡**：状态 `#profile-2fa-status`/`#profile-2fa-enabled`；设置区 `#profile-2fa-setup`（hidden）含 `<canvas id="profile-2fa-qr">`、`#profile-2fa-secret`、`#profile-2fa-code` + 「启用2FA」`enable2FA()`；动作区 `#profile-2fa-actions`「生成2FA密钥」`generate2FA()`；已启用动作 `#profile-2fa-enabled-actions`（hidden）「测试2FA」`test2FA()`、「关闭2FA」`disable2FA()`。
  - **主题设置卡**：`#profile-theme-select` `onchange="updateTheme()"`（light/dark）；样式按钮容器 `#profile-theme-style-buttons`（JS 填充）；基础颜色 `#profile-theme_base_color-picker`（color, 默认 #7dd3fc, onchange 同步文本+`onColorPicked`+`callPythonAPI('update_param','theme_base_color',...)`）与 `#profile-theme_base_color`（文本, 同逻辑）；「恢复默认」`resetBaseColorToDefault('profile')`。
  - **我的账单卡**（15704）：「刷新」`loadUserBillingList()`；容器 `#user-billing-list-container` 内「批量支付」`paySelectedBilling('user-billing-list-container')`。
  - **账号注销卡**（rose, 15744）：状态 `#pc-account-cancel-status`（「未申请」）；`#pc-account-cancel-current-password`、`#pc-account-cancel-sms-code` + 「发送验证码」`sendAccountCancelSmsCode('pc')`；「申请注销」`requestAccountCancellation('pc')`。

#### 留言板 `#admin-messages-panel_modal`（15795–15865，hidden）
- `#admin-refresh-messages_modal`「刷新」。
- 发表留言卡：游客字段 `#message-guest-fields`（hidden）含 `#message-nickname`、`#message-email`；Markdown 编辑器占位 `#message-editor`；字数 `#message-char-count`（0/1000）；「发表留言」`#post-message-btn` `onclick="postMessage()"`。
- 列表 `#admin-messages-list_modal`。

#### 用户日志查看 `#admin-user-logs-modal`（15870–15918，hidden）
- 当前用户 `#current-log-username`（N/A）；tab `#log-tab-login`「登录记录」、`#log-tab-audit`「操作记录」；内容 `#log-login-content`、`#log-audit-content`（hidden）；「返回」`closeUserLogsModal()`。

#### IP 封禁 `#admin-ip-ban-modal`（15923–16020，hidden）
- 「刷新」`#admin-refresh-ipban_modal` `onclick="loadIPBans()"`。
- 现有规则列表 `#ip-ban-list`。
- 添加规则：`#ban-type`（ip 单个IP / range IP范围）；`#ban-target`（目标）+提示 `#ban-target-hint`/错误 `#ban-target-error`；`#ban-scope`（all 封禁所有功能 / messages_only 仅封禁留言板）；「添加封禁」`addIPBan()`。

#### 短信服务配置 `#admin-sms-config-modal`（16023–16442，hidden）
- 「刷新」`#admin-refresh-sms_modal` `onclick="loadSMSConfig()"`。
- **功能开关卡**：`#sms-enabled`「启用短信服务」`onchange="handleSmsMainSwitchChange()"`；子项 `#sms-enable-phone-modification`「允许用户修改手机号」、`#sms-enable-phone-login`「允许手机号登录」、`#sms-enable-phone-registration-verify`「注册时需要短信验证」。
- **短信宝配置卡**：`#sms-username`（用户名）、`#sms-apikey`（API Key,password）、`#sms-signature`（签名,maxlength=10）、`#sms-template`（模板 textarea，含 {code}/{minutes}）、`#sms-code-expire`（有效期分钟,min=1,max=60）。
- **速率限制卡**：`#sms-limit-account`（账户,条/天）、`#sms-limit-ip`（IP）、`#sms-limit-phone`（手机号）。
- **Webhook 卡**：`#sms-webhook-url`（readonly）。
- **操作卡**：`#btn-check-sms-balance`「💰 查询余额」`checkSMSBalance()`、「💾 保存配置」`saveSMSConfig()`、「📋 短信发送历史」`openSMSHistoryModal()`、「🔑 验证码管理」`openVerificationCodesModal()`、「🧪 测试发送」`openSMSTestModal()`、「💬 查看回复记录」`openSMSReplyLogsModal()`；余额显示 `#sms-balance-display`（hidden）内 `#sms-balance-value`。

#### 系统配置 `#admin-config-panel_modal`（16444–16476，hidden）
- 「刷新」`#admin-refresh-config_modal` `onclick="loadSystemConfig()"`、「保存配置」`#admin-save-config_modal` `onclick="saveSystemConfig()"`。
- 警告文案（部分需重启）+ 地图 provider 说明。
- 表单容器 `#admin-config-form`（JS 填充）。

#### 验证码生成设置 `#admin-captcha-panel_modal`（16478–16646，hidden）
- 「🔄 刷新配置」`#admin-refresh-captcha-btn` `onclick="loadCaptchaSettings()"`。
- 输入：`#captcha-length`（长度,3-6,default4）、`#captcha-scale-factor`（细分倍数,2-4,default2）、`#captcha-noise-level`（噪点,0-0.3,step0.01,default0.08）。
- 按钮：`#save-captcha-settings-btn`「💾 保存设置」、`#test-captcha-btn`「🔄 测试生成」、`#view-captcha-history-btn`「📜 查看历史」。
- 预览 `#captcha-test-preview`（hidden）：显示 `#captcha-preview-display`、答案 `#captcha-preview-answer`。
- 参数说明区（长度/细分倍数/噪点比例）。

#### 验证码历史 `#admin-captcha-history-panel_modal`（16648–16771，hidden）
- 返回 `#back-to-captcha-settings-btn`；筛选 `#captcha-history-date`（date）、`#captcha-history-status`（全部/created 待验证/verified_success 验证成功/verified_failed 验证失败/expired 已过期/test_generated 测试生成）；「刷新」`#admin-refresh-captcha_modal` `onclick="loadCaptchaHistory()"`。
- 列表 `#admin-captcha-list_modal`。
- 统计 `#captcha-stats`（6 格）：总计 `#captcha-stat-total`、成功 `#captcha-stat-success`、失败 `#captcha-stat-failed`、待验证 `#captcha-stat-pending`、已过期 `#captcha-stat-expired`、测试生成 `#captcha-stat-test`。

#### 定时提醒 `#admin-reminders-panel_modal`（16773–16850，hidden）
- 「刷新」`#admin-refresh-reminders_modal` `onclick="loadReminders()"`、「添加提醒」`#admin-add-reminder_modal` `onclick="openReminderEditModal()"`。
- 功能说明块。
- 列表 `#admin-reminders-list_modal`（初始「暂无提醒，点击"添加提醒"创建新提醒」）。
- 统计（3 格）：总计 `#reminder-stat-total`、启用 `#reminder-stat-enabled`、禁用 `#reminder-stat-disabled`。

#### HTTPS/SSL `#admin-ssl-panel_modal`（16852–17017，hidden）
- 状态徽章 `#ssl-status-badge`；「刷新」`#ssl-refresh-btn` `onclick="loadSSLInfo()"`。
- 开关：`#ssl-enabled-toggle`「启用 HTTPS」、`#https-only-toggle`「仅 HTTPS 模式」。
- 证书信息 `#ssl-cert-info-container`/`#ssl-cert-info-content`。
- 上传：`#ssl-cert-file-input`（.pem,.crt）、`#ssl-key-file-input`（.key,.pem）、「上传证书」`#ssl-upload-btn` `onclick="uploadSSLCertificate()"`。
- 「保存配置」`#ssl-save-config-btn` `onclick="saveSSLConfig()"`。

#### CDN 缓存 `#admin-cdn-panel_modal`（17021–17196，hidden）
- 「刷新」`#cdn-refresh-btn` `onclick="loadCDNConfig()"`。
- 开关 `#cdn-enabled-toggle`「启用 CDN 缓存」。
- 缓存时间 `#cdn-cache-time`（default3600）；快捷按钮内联设值：1小时(3600)、6小时(21600)、24小时(86400)、7天(604800)。
- 「保存配置」`#cdn-save-config-btn` `onclick="saveCDNConfig()"`；「强制刷新服务器缓存」`#cdn-force-refresh-btn` `onclick="triggerCDNForceRefresh()"`。

#### 密码恢复（超管）`#admin-bruteforce-panel_modal`（17201–17343，hidden）
- 「刷新」`#bruteforce-refresh-btn` `onclick="loadBruteforceStatus()"`。
- 警告块（`display:none`）+ 功能说明块。
- `#bruteforce-accounts`（textarea，多账号）。
- 「开始恢复密码」`#bruteforce-start-btn` `onclick="startBruteforce()"`；「停止全部任务」`#bruteforce-stop-all-btn` `onclick="stopAllBruteforce()"`。
- 任务列表 `#bruteforce-task-list`（初始「暂无任务...」）。

> 17344 `</div>` 关闭滚动内容区。以下面板为 `#admin-panel-modal` 直接子级（在滚动区外）。

### E3. 支付日志面板 `#admin-payment-logs-panel_modal`（17361–17612，hidden）
- 标题「支付日志」；「刷新」`#admin-refresh-payment-logs_modal` `onclick="loadAdminPaymentLogs()"`。
- 说明块。
- 筛选：`#admin-payment-logs-action-type_modal`（全部/create_order 创建订单/query_order 查询订单/payment_success 支付成功/create_order_failed 创建失败/payment_notify 支付通知/refund 退款操作）；`#admin-payment-logs-start-date_modal`、`#admin-payment-logs-end-date_modal`；「查询日志」`#admin-search-payment-logs-btn_modal`（内联：置 `adminPaymentLogsState.currentPage=1; loadAdminPaymentLogs(1)`）。
- 列表 `#admin-payment-logs-list_modal`。
- 分页 `#admin-payment-logs-pagination_modal`：「上一页」`#admin-payment-logs-prev-btn_modal` `onclick="loadAdminPaymentLogsPrev()"`（disabled）、页码 `#admin-payment-logs-page-info_modal`（「第 1 页」）、「下一页」`#admin-payment-logs-next-btn_modal` `onclick="loadAdminPaymentLogsNext()"`。

### E4. 支付设置面板 `#admin-payment-settings-panel_modal`（17646–19505，hidden）
标题「支付设置」+ 说明块。子 tab 导航（`switchAdminPaymentSettingsTab(...)`）：

| tab 按钮 id | 文案 | 参数 |
|---|---|---|
| `#admin-payment-settings-tab-config_modal` | 支付方式配置（默认激活） | `'config'` |
| `#admin-payment-settings-tab-query_modal` | 订单查询 | `'query'` |
| `#admin-payment-settings-tab-refund_modal` | 退款处理 | `'refund'` |
| `#admin-payment-settings-tab-test_modal` | 测试支付 | `'test'` |
| `#admin-payment-settings-tab-yipay_modal` | 易支付配置 | `'yipay'` |
| `#admin-payment-settings-tab-product-test_modal` | 商品名测试 | `'product-test'` |

**Tab1 支付方式配置 `#admin-payment-settings-content-config_modal`（17874）**：
- 「添加支付方式」`openAddPaymentMethodModal()`；列表容器 `#payment-methods-list_modal`（JS 填充，grid 2 列）。
- 「刷新配置」`loadPaymentMethodsConfig()`、「保存配置」`#admin-save-payment-methods-btn_modal`；结果区 `#admin-payment-config-result_modal`（hidden）。

**Tab2 订单查询 `#admin-payment-settings-content-query_modal`（18009, hidden）**：
- 筛选：`#admin-filter-status_modal`（`onchange="filterPaymentOrders()"`；选项：全部/pending 已创建待支付/paid 已支付/refunded_partial 已部分退款/refunded_full 已全额退款/frozen 已冻结/preauth 预授权/timeout 支付超时/failed 创建失败）；`#admin-filter-paytype_modal`（全部/alipay 支付宝/wxpay 微信支付，onchange 同）；`#admin-filter-username_modal`（oninput filterPaymentOrders）；`#admin-filter-orderno_modal`（oninput）。
- 手动查询：`#admin-manual-query-order-no_modal`；「加载本地」`loadAllPaymentOrders()`、「查询」`queryOrderManually()`、「从平台拉取」`fetchOrdersFromPlatform()`。
- 订单容器 `#admin-orders-table-container_modal`：计数 `#admin-orders-count_modal`；卡片网格 `#admin-orders-table-body_modal`（JS 渲染，1/2/3 列响应式）。

**Tab3 退款处理 `#admin-payment-settings-content-refund_modal`（18267, hidden）**：
- 警告块。表单：`#admin-refund-order-trade-no_modal`（原订单号,必填）、`#admin-refund-amount_modal`（退款金额,必填,min0.01）、`#admin-refund-no_modal`（退款单号,可选）+「自动生成」`generateAdminRefundOrderNo()`、`#admin-refund-reason_modal`（退款原因,textarea）。
- 「确认退款」`#admin-process-refund-btn_modal` `onclick="submitAdminPaymentRefund()"`。
- 成功区 `#admin-refund-result-container_modal`（hidden）：退款单号 `#admin-refund-result-no_modal`、金额 `#admin-refund-result-amount_modal`。
- 失败区 `#admin-refund-error-result_modal`（hidden）：消息 `#admin-refund-error-message_modal`。

**Tab4 测试支付 `#admin-payment-settings-content-test_modal`（18607, hidden）**：
- `#admin-test-payment-amount_modal`（金额,default0.5）、`#admin-test-payment-method_modal`（alipay/wxpay/qqpay/unionpay）、`#admin-test-payment-type_modal`（`onchange="toggleAuthCodeField()"`；选项 web/jump/jsapi/app/jsapi/applet/scan，含重复 jsapi 项）。
- 付款码容器 `#admin-test-auth-code-container_modal`（hidden）内 `#admin-test-auth-code_modal`（maxlength18）。
- JSAPI 参数容器 `#admin-test-jsapi-params-container_modal`（hidden）：`#admin-test-sub-openid_modal`、`#admin-test-sub-appid_modal`。
- 商品名：单选 `name="product-name-input-method_modal"`（manual checked / auto，`onchange="toggleProductNameInputMethod_modal()"`）；手动容器 `#manual-product-name-container_modal` 内 `#admin-test-payment-product_modal`（default「测试商品」）；自动容器 `#auto-product-name-container_modal`（hidden）内 `#admin-test-payment-quantity_modal`（1-9999）。
- 「创建测试订单」`#admin-create-test-order-btn_modal` `onclick="createAdminTestPayment()"`。
- 结果区 `#admin-test-payment-link-container_modal`（hidden）：订单信息（`#admin-test-order-id_modal`、`#admin-test-trade-no_modal`、`#admin-test-amount_modal`、`#admin-test-pay-method_modal`、`#admin-test-method-type_modal`、`#admin-test-pay-type_modal`）；支付信息卡 `#admin-test-pay-info-card_modal_modal` 内 `<textarea id="admin-test-pay-url_modal" readonly>`、说明 `#admin-test-pay-info-desc_modal`、二维码 `#admin-test-qrcode-display_modal`（hidden）；按钮「打开链接」`#admin-open-test-pay-url-btn_modal` `onclick="openAdminPaymentLink()"`、「复制信息」`copyAdminTestPayUrl()`。结果提示 `#admin-test-payment-result_modal`（hidden）。

**Tab5 易支付配置 `#admin-payment-settings-content-yipay_modal`（19095, hidden）**：
- `#admin-yipay-host_modal`（接口域名,必填）、`#admin-yipay-pid_modal`（商户ID,必填）、`#admin-yipay-key_modal`（商户密钥,password,必填）、`#admin-yipay-app-host_modal`（应用域名）、`#admin-yipay-pubc-key_modal`（平台公钥,textarea,必填）、`#admin-yipay-timeout_modal`（超时秒,10-3600）、`#admin-yipay-product-id_modal`（商品ID,default1001）、`#admin-yipay-enabled-methods_modal`（启用支付方式,readonly,自动同步）。
- 「刷新配置」`loadAdminYiPayConfig()`、「保存配置」`saveAdminYiPayConfig()`。

**Tab6 商品名测试 `#admin-payment-settings-content-product-test_modal`（19365, hidden）**：
- `#product-test-quantity_modal`（数量,1-9999,default5）；「生成商品名」`#generate-product-name-btn_modal` `onclick="testGenerateProductName_modal()"`。
- 结果 `#product-test-result_modal`（hidden）：名称 `#product-test-name_modal`、字节长度 `#product-test-length_modal`。
- 「批量测试」`#batch-test-product-names-btn_modal`（`display:none`）`onclick="batchTestProductNames_modal()"`；批量结果 `#batch-test-results_modal`（hidden）内列表 `#batch-test-list_modal`。

### E5. 价格设置面板 `#admin-pricing-panel_modal`（19524→，hidden）
- 本段最后一行 19524 仅为该面板的开标签：`<div id="admin-pricing-panel_modal" class="hidden overflow-y-auto">`，随后是标题区（19525+）。
- 完整内容（require_payment 开关 / per_run_cost / default_available_runs 等）延续到本文覆盖范围之外，见后续文档。

---

## 附录：本段全部 JS 函数名索引（onclick/onchange/oninput/onerror）

**多账号（移动端）**：`exitMobileMultiAccount`、`addMobileSelectedConfig`、`addMobileAllConfigs`、`openManualAccountModal`、`mobileToggleSelectAllAccounts`、`mobileStartSelectedAccounts`、`mobileStopSelectedAccounts`、`importMobileAccountList`、`exportMobileAccountList`、`downloadMobileAccountTemplate`、`mobileRefreshSelectedAccounts`、`mobileRefreshAllAccounts`、`deleteMobileSelectedAccounts`、`deleteMobileAllAccounts`、`mobileStartAllAccounts`、`mobileStopAllAccounts`、`resetMultiMapView`、`mobileMultiZoomIn`、`mobileMultiZoomOut`、`mobileMultiFitView`、`saveMobileMultiGlobalSettings`、`clearMobileMultiLog`、`scrollMobileMultiLogToBottom`。

**移动端模态框/侧边栏**：`toggleMobileUserDetails`、`mobileLogout`、`toggleMobileTaskDetails`、`closeMobileHistoryModal`、`closeMobileTrackModal`、`mobileTrackZoomIn/Out`、`mobileTrackFitView`、`closeMobileMapAttendanceModal`、`confirmMobileMapAttendance`、`closeMobileCaptchaHistoryModal`、`loadMobileCaptchaHistoryModal`、`toggleMobileNotifications`、`toggleMobileAdminPanel`、`closeMobileAccountParams`、`closeManualAccountModal`、`confirmManualAccountAdd`、`closeMobileCreateUserModal`、`sendMobileNewUserCode`、`submitMobileCreateUser`、`toggleMobileMoreMenu`、`switchMobileSinglePanel`、`switchMobileNotifTab`、`openMobileAdminPanelUnified`、`switchMobilePanel`、`closeMobileSidebar`、`exitMobileSingleAccountSafe`、`createNewSessionFromPicker`、`refreshMobileSessionPicker`、`closeMobileSessionPicker`。

**支付/订单/日志共享**：`toggleLogoInput`、`savePaymentMethod`、`closePaymentMethodModal`、`closeOrderDetailModal`、`copyOrderTradeNo`、`refreshOrderDetailLocal`、`refreshOrderDetailFromPlatform`、`closePaymentLogDetailModal`、`closeModalAlert`、`closeMissingPasswordModal`、`toggleNotifications`。

**PC 管理面板**：`toggleAdminPanel`、`switchAdminTab`、`loadAdminUsers`、`resortAdminUsers`、`toggleAdminUsersSort`、`previewAvatar`、`updateBasicInfo`、`modifyPhone`、`toggleSmsVerifyMode`、`sendPasswordResetSmsCode`、`updatePassword`、`generate2FA`、`enable2FA`、`test2FA`、`disable2FA`、`updateTheme`、`onColorPicked`、`callPythonAPI`、`resetBaseColorToDefault`、`loadUserBillingList`、`paySelectedBilling`、`sendAccountCancelSmsCode`、`requestAccountCancellation`、`postMessage`、`closeUserLogsModal`、`loadIPBans`、`addIPBan`、`loadSMSConfig`、`handleSmsMainSwitchChange`、`checkSMSBalance`、`saveSMSConfig`、`openSMSHistoryModal`、`openVerificationCodesModal`、`openSMSTestModal`、`openSMSReplyLogsModal`、`loadSystemConfig`、`saveSystemConfig`、`loadCaptchaSettings`、`loadCaptchaHistory`、`loadReminders`、`openReminderEditModal`、`loadSSLInfo`、`uploadSSLCertificate`、`saveSSLConfig`、`loadCDNConfig`、`saveCDNConfig`、`triggerCDNForceRefresh`、`loadBruteforceStatus`、`startBruteforce`、`stopAllBruteforce`。

**支付日志/设置**：`loadAdminPaymentLogs`、`loadAdminPaymentLogsPrev`、`loadAdminPaymentLogsNext`、`switchAdminPaymentSettingsTab`、`openAddPaymentMethodModal`、`loadPaymentMethodsConfig`、`filterPaymentOrders`、`loadAllPaymentOrders`、`queryOrderManually`、`fetchOrdersFromPlatform`、`generateAdminRefundOrderNo`、`submitAdminPaymentRefund`、`toggleAuthCodeField`、`toggleProductNameInputMethod_modal`、`createAdminTestPayment`、`openAdminPaymentLink`、`copyAdminTestPayUrl`、`loadAdminYiPayConfig`、`saveAdminYiPayConfig`、`testGenerateProductName_modal`、`batchTestProductNames_modal`。
