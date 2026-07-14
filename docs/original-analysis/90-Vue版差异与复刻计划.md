# Vue 版 vs Original 差异分析 & 复刻计划

> 生成时间：2026-07-14。基于 original 逐段解析文档（10–14 HTML / 20–24 JS / 30 CSS / 40 API）与 Vue 版源码逐项对照。
> 目标：Vue 版完全复刻 original 页面与功能。

## A. 总体结论

- Vue 版组件骨架较完整：路由（login/session/main/multi）、Pinia store（app/auth/theme/map/network/notification/task）、service（api/socket）、22 个 admin 子面板已在 `AdminPanel.vue` 注册。
- **Socket.IO 层已完全复刻**（14 事件 + heartbeat/join），见 `40-API与Socket对照.md`。
- 但存在大量**未实现/占位/参数不符**的缺口，下列为权威清单。

## B. 一级缺口：9 个 Admin 面板为 10 行 stub（"功能开发中"）

| Vue 组件 | 对应 original 功能 | original 参考文档 | 关键 API |
|---|---|---|---|
| `AdminBilling.vue` | 账单管理（增删改查） | 24-JS §7 | `/api/admin/billing/{list,add,update,delete}` |
| `AdminBillingLogs.vue` | 账单日志 | 24-JS §7 | `/api/admin/billing/logs` |
| `AdminBruteforce.vue` | 密码恢复（暴力破解任务） | 23-JS（49162 起）| `/api/admin/bruteforce/{start,status,stop}` |
| `AdminCaptcha.vue` | 验证码配置/历史/测试 | 22/23-JS | `/api/captcha/{config,save_settings,history,detail/,test_generate}` |
| `AdminPaymentLogs.vue` | 支付日志（管理员） | 20/24-JS | `/api/admin/payment/config`、`/payment_logs` |
| `AdminPaymentSettings.vue` | 支付设置（6 个子 Tab：支付方式/订单查询/退款/测试支付/易支付配置） | 20-JS（2386 起）| `/api/admin/payment/*`、`/api/admin/yipay_config` |
| `AdminReminders.vue` | 定时提醒（增删改查） | 23-JS（49524 起）| `/api/reminders/{list,check,update,delete}` |
| `AdminRestoreAccount.vue` | 恢复已删除账号 | 22-JS | `/api/admin/removed_accounts`、`/restore_account` |
| `AdminWatermark.vue` | 高德地图去水印控制 | 20-JS（12046 起）| `/api/amap/watermark_control/config` |

> 注：`AdminPricing.vue` 工作区已有未提交改动（从 stub 补至 ~169 行），说明补全工作正在进行。

## C. 二级缺口：已实现 Admin 面板 vs original 的功能差异（待逐一核对）

现有实现（行数）：AdminUsers(358)、AdminGroups(312)、AdminProfile(266)、AdminConfig(252)、AdminLogs(202)、AdminSMS(173)、AdminPricing(169*)、AdminSSL(167)、AdminHealth(166)、AdminSessions(136)、AdminIPBan(132)、AdminMessages(123)、AdminCDN(116)。
→ 需对照 21/22-JS 文档核对每个面板的字段/按钮/交互是否与 original 一致（待 JS 文档齐全后进行）。

## D. 三级缺口：主应用（MainView / ControlTabs）

### D.1 MainView 移动端占位面板（`views/MainView.vue`）
以下移动端面板当前为纯占位文本（"…加载区域"），需复刻真实内容：
- `checkpoints`（打卡点）、`attendance`（签到）、`history`（历史记录）、`settings`（参数设置）、`task-details`（任务详情）
- 注：这些功能在 `ControlTabs.vue` 中已实现，移动端应复用而非占位。

### D.2 ControlTabs（`components/main/ControlTabs.vue`）对照桌面文档（11-HTML §2.1.3）
- ❌ **路径 Tab 缺"录制路径"按钮**（original `record-button`，2780 行）。当前仅 4 键，original 为 5 项。
- ❌ **签到 Tab 参数 key 不符**：
  - original：`auto_attendance_refresh_s`（刷新间隔）、`attendance_user_radius_m`（随机半径）
  - Vue：`auto_attendance_interval`、`auto_attendance_radius` → **需改为 original 的 data-key**，否则后端不识别。
- ❌ **签到 Tab 缺"签到任务列表"区**（original `attendance-list` + `refresh-attendance-list-btn` onclick=`refreshNotificationsUI(true,true)`，2887–2906）。
- ⚠️ 执行 Tab：original 为"开始执行 + 执行所有"两键 + 独立统计块/单任务进度块；Vue 为三键（含停止）。需核对布局与 id（`run-stats-label`/`single-progress-fill` 等）。
- ⚠️ 打卡点/历史：original 通过 `target-points-text`/`history-list` 由 JS 渲染，数据来源需对照 21-JS。

## E. 待补充（依赖 JS 文档 20/21/22/23）
- 登录/认证页（AuthPanel 918 行）对照 12-HTML + 21-JS：用户名/手机号切换、密码/短信登录、图形验证码、2FA、游客登录的完整流程。
- 多账号视图（MultiAccountView 1097 行）对照 13-HTML + 23-JS。
- 会话选择器 / 会话管理（上帝模式）对照 22-JS（32492 起）。
- 个人信息 / 修改手机号 / 2FA / 头像裁剪 对照 21/23-JS。
- 顶层模态框（新手帮助、支付、订单、修改手机号等）对照 10/14-HTML。

## F. 复刻执行顺序（建议）
1. 修正 ControlTabs 已确认的 3 处差异（参数 key、录制按钮、签到列表）。
2. 补全 9 个 stub 面板（按 API 契约实现，参考对应 JS 文档）。
3. 复刻 MainView 移动端占位面板（复用 ControlTabs 逻辑）。
4. 逐一核对已实现 admin 面板与 original 差异并补齐。
5. 核对登录/多账号/会话/个人信息等主流程细节。
6. 样式核对（30-CSS：.panel/.btn/.modal/移动端组件/CSS 变量/深色模式/动画）。

> 本文档随 JS 文档（20–23）完成持续更新。

---

## G. 修改进展（2026-07-14 复刻实施）

### G.1 已补全的 9 个 stub Admin 面板（全部通过 vite 编译）
| 组件 | 实现要点 | API |
|---|---|---|
| `AdminWatermark.vue` | 去水印总开关 + 用户级增删/开关 + 添加弹窗 | `/api/amap/watermark_control/config` GET/PUT |
| `AdminReminders.vue` | 提醒列表/新增/编辑/删除/启停/立即检查（跨天时间） | `/api/reminders/{list,add,update,delete,check}` |
| `AdminBruteforce.vue` | 启动破解/3s 状态轮询/停止/任务卡片 | `/api/admin/bruteforce/{start,status,stop}` |
| `AdminBillingLogs.vue` | 日志卡片/事件徽章/筛选/分页/详情 | `/api/admin/billing/logs` |
| `AdminCaptcha.vue` | 配置保存/测试生成预览/历史/详情 | `/api/captcha/{config,save_settings,test_generate,history,detail}` |
| `AdminBilling.vue` | 账单列表/搜索/统计/增删改 | `/api/admin/billing/{list,add,update,delete}` |
| `AdminPaymentLogs.vue` | 支付日志/筛选/分页/详情 | `/api/admin/payment_logs`、`/payment/log_detail` |
| `AdminRestoreAccount.vue` | 已删除账号列表/详情/恢复（用户名/手机号冲突循环） | `/api/admin/{removed_accounts,removed_account_detail,restore_account}` |
| `AdminPaymentSettings.vue` | 6 子 Tab：支付方式/订单查询/退款/测试支付/易支付配置 | `/api/admin/payment*`、`/payment_methods`、`/yipay_config` |

### G.2 ControlTabs 已修正（3 处）
- ✅ 签到参数 key 改为 original 的 `auto_attendance_enabled`/`auto_attendance_refresh_s`/`attendance_user_radius_m`，并加 `@change` 持久化。
- ✅ 路径 Tab 新增「录制路径」按钮（录制态高亮切换）。⚠️ 交互式地图绘制（isDrawing/draftPath）尚未移植，属已知后续大缺口。
- ✅ 签到 Tab 新增「签到任务列表」区（refresh + 列表）。

### G.3 MainView 移动端占位面板已复刻
- ✅ checkpoints/attendance/history/settings 导航路由到「控制」面板对应 Tab（`NAV_TO_CONTROL_TAB` + ControlTabs `openTab` prop）。
- ✅ task-details 面板实现真实任务详情内容。

### G.4 深度对照核验并修正的现有组件（发现大量真实契约错配）
> 第二轮深核对照 21/22-JS 文档与 `main.py` 端点契约，发现现有面板普遍存在**字段名/端点错配**（原实现多为臆造，近乎不可用），已全部修正并通过 `@vue/compiler-sfc` 校验：
- **登录域**：AuthPanel（登录方式文案、2FA 标题、注册校验/占位、手机号未注册引导注册、2FA auth_username 隐患）、SessionLogin（已保存账号下拉、UA 回填、UA 区重构）、LoginView（三栏文案、上帝模式）、MultiAccountEntry（多账号引导文案）。
- **MultiAccountView**：标题/按钮/空态/计数/延迟上限等文案与结构对齐。
- **AdminUsers**：字段全部对齐 `list_users`（auth_username/nickname/group/phone/max_sessions/available_runs/2fa_enabled），补齐强制关闭2FA/强制登出/清头像/最大会话/可用次数/改昵称/改手机/权限组下拉/重置密码传参。
- **AdminGroups**：改为后端 dict 契约（is_system/permissions），保存传 `{group_key,permissions}`。
- **AdminSessions**：上帝模式路由修正（all_sessions/user_sessions），字段/踢出逻辑对齐。
- **AdminProfile**：新增 2FA 管理（generate/enable/disable）。
- **AdminConfig**：重建为真实 config 节（Guest/Help/System/Logging/Security/...）。
- **AdminHealth**：组件名修正（running_core/payment_system/sms_system）+ uptime/response_time 字段。
- **AdminMessages**：改 REST `/api/messages/*`，发帖前 IP 封禁检查，游客字段。
- **AdminIPBan**：字段模型改 `{target,type,scope}` + 校验。
- **AdminSMS**：重建为真实字段（主开关+子开关/限流/webhook/余额/历史/回复）。
- **AdminLogs**：端点改 `/logs/view`。**AdminCDN**：字段改 `cdn_enabled/cache_time`。**AdminSSL**：端点改 `/api/admin/ssl/info|toggle|upload`。**AdminPricing**：补校验。

### G.5 用户端支付/欠费/账单流程（已实现，见 §I）
- 新建 `composables/usePayment.js` + `PaymentModal.vue` + `OrdersModal.vue` + `BillingModal.vue`。
- 接入 `ControlTabs` 开始执行前的欠费拦截 `checkOverdueBeforeStartByCurrentMode`；`UserInfoBar`/`MobileSidebar` 增加订单/账单/支付入口。
- 二维码走 `/api/cdn/qrcode` CDN 动态加载 + 降级链接。

### G.6 整体 vite build ✅ 通过（125 模块，3 次全量构建均成功）

### G.7 对抗式验证（Workflow：9 stub + 支付流程 对照 main.py 契约）
- **AdminPaymentSettings 发现并修复 2 个真实 bug**：① 新增/编辑支付方式的 `icon` 应发 Logo 类型 `svg/image`（后端 `add/manage_payment_method` 校验 icon∈{svg,image}），原发 emoji 会 400；② 保存易支付配置 `enabled_payment_methods` 应发**逗号分隔字符串**，原发数组会致后端 `.strip()` 抛 AttributeError 500。
- 其余 7 个目标（Watermark/Reminders/BillingLogs/Captcha/Billing/PaymentLogs/RestoreAccount）+ PaymentFlow：契约核验通过，无 CONFIRMED 问题。
- AdminBruteforce（自动核验被内容过滤器拦截）→ **手工核对 main.py 契约通过**：start `{accounts:[]}`、stop `{accounts:[]}|{all:true}`、status 读 `data.tasks`，全部一致。

### G.8 交互式路径绘制（✅ 已实现，⚠️ 需运行时联调）
- `stores/map.js` 增绘制协调状态（isDrawing/draftPoints/draftDistance + start/stop/clear/addDraftPoint，haversine 累距）。
- `MapContainer.vue` watch isDrawing → 绑定 provider 地图 click 加点、独立 draft 折线重绘、crosshair 光标、切换/销毁清理（amap 完整；tencent/tianditu/baidu 尽力）。
- `ControlTabs.vue` 录制按钮切换绘制、实时显示点数/距离；停止时 `callAPI('set_draft_path', points)` + `callAPI('process_path')`（契约对照 main.py `set_draft_path(coords)` 与 original 40309/40470 核实），清除用 `set_draft_path([])`。
- **已知差异（诚实记录）**：本版为逐点点击（original 为按住拖动自由绘制）；距离用 haversine（original 用平面近似）；tencent/tianditu/baidu 的坐标提取/解绑按常见 SDK 编写但未运行时验证；坐标系未归一化（与 original 一致直接用地图原始坐标）。

### H. 待续（后续核验/补齐）
- **[需运行时联调]** 交互式路径绘制（见 G.8）：非 amap provider 的点击事件、拖拽式绘制 UX、距离算法与 original 完全对齐。
- 头像裁剪上传（cropperjs）、学校账号增删改弹窗、逐用户差分权限弹窗（需完整弹窗基建）。
- 对抗式验证 Workflow 结果落地（9 stub + 支付流程契约二次核验）。
- 样式核对（30-CSS：移动端组件、深色模式、动画、CSS 变量；注意 Tailwind v3→v4 差异，见 §J）。

### I. 用户端支付/欠费/账单流程（✅ 已实现）
依据 24-JS §2/§4/§7 复刻，新建 `usePayment.js` + `PaymentModal/OrdersModal/BillingModal.vue` 并接入：
- `payment-modal`（用户支付弹窗：createPaymentOrder + 二维码 + startOrderPolling 3s×20 状态机）。
- `orders-modal`（用户订单列表：分页/继续支付/刷新状态）。
- 欠费拦截：开始跑步前 `checkOverdueBeforeStart` → `showOverduePaymentModal` → `showPaymentPageWithPolling`（二维码 + 2s 轮询）。
- 用户账单列表（`/api/billing/list`）+ `createBillingPaymentOrderAndOpen`（qrcode/html/jump 分发）。
→ 建议作为独立组件（如 `PaymentModal.vue`/`OrdersModal.vue`/`OverduePayment` 逻辑）接入 MainView 与 ControlTabs 的开始执行流程。属后续独立一轮实现。
- 实现约束：`frontend/package.json` **未装 qrcode 依赖**（original 用 CDN `window.QRCode`）。Vue 侧需 `npm i qrcode` 或运行时加载 CDN。`sweetalert2` 已装可直接用。

### J. 环境差异备注（非缺口，记录以免误判）
- **Tailwind 版本**：original 用 3.4.17，Vue 版用 **v4**（package.json）。v4 部分工具类/配置 API 与 v3 不同，属 Vue 版自身构建选择，不回退；样式核对时以视觉等效为准而非类名逐一对齐。
