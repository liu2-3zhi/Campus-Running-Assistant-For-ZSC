# 12 · 移动端主容器解析（index.html 第 3577–10482 行）

> **覆盖范围**：`index.html` 第 3577 行 `<div id="mobile-container">` 起，至第 10482 行 `<div id="mobile-multi-account-app">`（该行属于下一大节的开始，本文档只作为边界标记，不展开）。
> **性质**：原始单文件前端“跑步助手”的**移动端主容器** `#mobile-container`，包含顶栏、内容区 `main#mobile-content` 及其三个核心子应用，另加一个独立同级的“统一管理面板”。
> **用途**：Vue 重构版逐元素复刻依据，务求不遗漏任何 id / class / 事件 / data-* / 文案 / 初始可见性。

---

## 0. 结构总览与顶层容器

### 0.1 `#mobile-container`（行 3577–10477 结束）
- 容器 `<div id="mobile-container">`，无 class。
- 直接子节点：
  1. `header#mobile-header`（行 3578–3621）
  2. `main#mobile-content`（行 3622–…，包含所有子应用）

### 0.2 顶栏 `header#mobile-header`（行 3578–3621）
- id：`mobile-header`；class：`mobile-header hidden relative flex items-center w-full h-14 px-2 bg-white shadow-sm`；**初始可见性**：`style="display: none"`（隐藏，且带 `hidden` 类）。
- 子元素：
  - `button#mobile-menu-btn`（行 3583）：class `p-2 -ml-5 text-slate-700 hover:bg-slate-100 rounded-md`，`aria-label="菜单"`，**初始 `style="display: none"`**，`onclick="toggleMobileSidebar()"`，内含汉堡三横线 SVG。
  - 居中 Logo 区（行 3606–3620）：跑步小人 SVG（`text-sky-600`）+ `<span>跑步助手</span>`（class `ml-2 text-lg font-bold text-slate-800`）。

### 0.3 内容区 `main#mobile-content`（行 3622）
- `<main class="mobile-content" id="mobile-content">`。
- 内部并列以下顶级块：
  - `#mobile-auth-login-container`（认证登录，默认可见）
  - `#mobile-login-container`（会话登录，`hidden`）
  - `#mobile-loading-overlay`（加载遮罩，`hidden`）
  - `#mobile-main-app`（主应用，`hidden`）
  - `#mobile-admin-panel-unified`（统一管理面板，`hidden`）
  - `#mobile-multi-account-app`（多账号模式，`hidden` —— 起于行 10482，超出本文档范围）

---

## 1. 子应用一：移动端认证登录 `#mobile-auth-login-container`（行 3623–4062）

- 容器 id：`mobile-auth-login-container`；class：`space-y-4`；**初始可见**（无 `hidden`）。
- 内含单张卡片 `div.mobile-card#mobile-auth-login-container-card`（行 3624）。

### 1.1 标题区（行 3625–3628）
- `h1.mobile-title`：**“欢迎使用跑步助手”**
- `p.mobile-subtitle`：**“请登录或注册以继续使用”**

### 1.2 登录/注册 Tab 切换（行 3630–3643）
| 按钮 id | 文案 | 初始态 |
|---|---|---|
| `mobile-auth-tab-login` | 登录 | 激活（`text-sky-600 border-b-2 border-sky-600`） |
| `mobile-auth-tab-register` | 注册 | 非激活（`text-slate-400 border-transparent`） |
- 无 inline onclick（由 JS 绑定事件）。

### 1.3 登录表单 `form#mobile-login-form`（行 3645–3823）
- 属性：`class="space-y-4"`、`autocomplete="on"`、`onsubmit="return false;"`。**初始可见**。
- **登录方式切换**（`#mobile-login-type-toggle`，行 3651）：
  - `button#mobile-login-username-btn` —— “用户名登录”（初始激活 `bg-sky-100 text-sky-700`）
  - `button#mobile-login-phone-btn` —— “手机号登录”（初始 `bg-slate-100`）
- **账号输入组**（行 3671–3685）：
  - `label#mobile-login-label` 文案“用户名”
  - 容器 `#mobile-username-container`，内含 `input#mobile-auth-username`（`name="username"`，placeholder“请输入用户名”，`autocomplete="username"`）
- **密码区** `#mobile-password-section`（行 3687–3706）：
  - `label` “密码”
  - `button#mobile-switch-to-sms`（“使用验证码”，初始 `hidden`）
  - `input#mobile-auth-password`（`type=password`，`name="password"`，placeholder“请输入密码”，`autocomplete="current-password"`）
- **短信验证码区** `#mobile-sms-section`（行 3708–3736，初始 `hidden`）：
  - `label` “验证码” + `button#mobile-switch-to-password`（“使用密码”）
  - `input#mobile-auth-sms-code`（placeholder“6位验证码”，`maxlength=6`，`inputmode=numeric`）
  - `button#mobile-auth-send-login-code`（“发送”）
- **图形验证码区**（行 3741–3775）：
  - `div#mobile-login-captcha-display`（`onclick="refreshCaptcha('mobile-login')"`，title“点击刷新验证码”，`min-height:64px`，初始文本“加载中...”）
  - `button#mobile-login-captcha-refresh`（“刷新验证码”，`onclick="refreshCaptcha('mobile-login')"`）
  - `input#mobile-login-captcha`（placeholder“请输入验证码”，`maxlength=6`，`autocomplete=off`）
- **登录提交** `button#mobile-login-btn`（class `mobile-primary-btn`，title/aria“登录”，文案“登录”，行 3777）。
- **游客登录区** `#mobile-guest-login-section`（行 3786–3822，初始 `hidden`）：
  - 分隔线“或”
  - `button#mobile-guest-btn`（class `mobile-secondary-btn`，“以游客身份继续”）
  - 琥珀色提示框 “⚠️ 游客模式提示”，列出 4 条：UUID 恢复需保存地址 / 丢失 URL 无法恢复 / 5 分钟不活跃自动清理 / 建议注册。

### 1.4 注册表单 `form#mobile-register-form`（行 3825–4017）
- class `space-y-4 hidden`（**初始隐藏**），`autocomplete="on"`，`onsubmit="return false;"`。
- 字段：
  - `input#mobile-reg-username`（`name=username`，placeholder“3-20字符，不含中文”）
  - `#mobile-reg-phone-wrapper` → `input#mobile-reg-phone`（`type=tel`，前缀“+86”，`maxlength=11`，`pattern=[0-9]*`）
  - `#mobile-reg-sms-wrapper` → `input#mobile-reg-sms-code`（6位验证码）+ `button#mobile-reg-send-code-btn`（“发送”，靛蓝色样式）
  - `input#mobile-reg-nickname`（placeholder“请输入昵称（可含中文）”）
  - 头像组 `#mobile-reg-avatar-group`：`img#mobile-reg-avatar-preview`（默认 `/static/default_avatar.png`）、`input#mobile-reg-avatar`（`type=file` `accept=image/*` 隐藏）、`button#mobile-reg-upload-avatar-btn`（inline onclick 触发 `mobile-reg-avatar` 的 `.click()`，“上传头像”）
  - `input#mobile-reg-password`（`name=new-password`，placeholder“请输入密码（至少6字符）”）
  - `input#mobile-reg-password-confirm`（`name=new-password-confirm`，placeholder“请再次输入密码”）
  - 图形验证码：`div#mobile-register-captcha-display`（`onclick="refreshCaptcha('mobile-register')"`）、`button#mobile-register-captcha-refresh`（同 onclick）、`input#mobile-register-captcha`
  - available_runs 提示 `#mobile-register-available-runs-hint`（初始 `hidden`，内含 `span#mobile-register-runs-text`，前缀🎁）
  - `button#mobile-register-btn`（class `mobile-primary-btn`，绿色渐变内联样式，“注册”）

### 1.5 两步验证表单 `#mobile-auth-2fa-form`（行 4019–4050，初始 `hidden`）
- 标题“两步验证”、副标题“请输入您的验证码”
- `input#mobile-2fa-code`（placeholder“请输入6位验证码”，`maxlength=6`，`autocomplete=one-time-code`）
- `button#mobile-2fa-submit-btn`（“验证”）
- `button#mobile-2fa-back-btn`（“返回登录”）

### 1.6 提示区
- `div#mobile-auth-error`（行 4052，`hidden`，红色）
- `div#mobile-auth-success`（行 4057，`hidden`，绿色）

---

## 2. 子应用二：移动端会话登录 `#mobile-login-container`（行 4067–4548）

- id：`mobile-login-container`；class `space-y-4 hidden`（**初始隐藏**）。三栏卡片布局。

### 2.1 区域1 · 单账号登录卡 `#mobile-single-login-card`（行 4071–4200）
- 标题 “单账号登录”，副文案 “掌上莲峰跑步助手”。
- `select#mobile-user-combo`（“选择用户”，首项 `option value="" 请选择用户`）
- `input#mobile-username-entry`（placeholder“请输入学号或工号”）
- `input#mobile-password-entry`（`type=password`，placeholder“请输入密码，一般为身份证后六位”）
- `button#mobile-single-login-btn`（class `mobile-primary-btn`，“登录”）
- 分隔线
- `button#mobile-import-button`（绿色渐变，“导入离线文件”，title“导入”）
- **User-Agent 区**（行 4148–4199）：
  - 标签 “User-Agent 标识”
  - `button#mobile-random-ua-btn`（title“随机生成新的User-Agent…”，文案“随机”）
  - `p#mobile-ua-label`（初始文本 “(未加载)”）

### 2.2 区域2 · 多账号入口卡 `#mobile-multi-account-card`（行 4205–4251）
- 紫色多人 SVG 图标。
- `h2.mobile-title` “多账号模式”，副标题 “批量管理多个账号，一键执行任务”。
- 三个特性行：✨支持批量导入账号 / 🎯统一管理所有任务 / ⚡一键执行全部流程。
- `button#mobile-multi-account-btn`（class `mobile-primary-btn`，紫色渐变，“进入多账号控制台”）。

### 2.3 区域3 · 会话管理卡 `#mobile-session-panel-card`（行 4256–4398）
- 装饰渐变圆背景两枚。
- 头部：会话锁图标 + `h3` “会话列表” + `div#mobile-session-count-display`（初始“统计中...”）。
- `button#mobile-refresh-sessions-btn`（title“刷新列表”，刷新 SVG）。
- `div#mobile-session-guest-msg`（初始 `hidden`）：👋 “游客模式”提示，正文“当前会话如下。如需使用多个会话或保存数据，请注册账号。”
- `button#mobile-create-session-btn`（`onclick="createNewSessionFromPicker()"`，蓝色渐变，“创建新会话”）。
- 操作提示条：“长按会话可删除，双击即可切换”。
- `div#mobile-sessions-list`（`space-y-3 max-h-[50vh] overflow-y-auto`；初始占位 spinner + “正在同步会话数据...”）。

### 2.4 快速操作卡 `#mobile-quick-actions`（行 4403–4547，初始 `hidden`）
- `h2.mobile-title` “快速操作”。
- 4 个 `button.mobile-list-item`（**无 onclick**，均为静态占位）：开始跑步 / 查看任务 / 历史记录 / 设置，每个带图标与右箭头。

---

## 3. 加载遮罩 `#mobile-loading-overlay`（行 4554–4564）
- id：`mobile-loading-overlay`；class `fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-white/90 backdrop-blur-sm hidden`（**初始隐藏**）。
- 内含旋转 spinner + 文案 “加载中，请稍候...”。

---

## 4. 子应用三：移动端主应用 `#mobile-main-app`（行 4566–6200）

- id：`mobile-main-app`；class `space-y-4 hidden`（**初始隐藏**）。
- 内部为多个功能面板，通过 `switchMobileSinglePanel(panelId)` / 侧边栏进行切换显示（各面板默认布局见下）。

> 说明：面板的显隐通过 JS 控制（`switchMobileSinglePanel` 出现在签到面板“重置”按钮 onclick 中）。多数面板初始并无 `hidden` 类（如通知、任务、地图、控制、打卡点、历史、签到、任务详情、资料），日志与设置面板初始带 `hidden`。

### 4.1 通知面板 `#mobile-notification-panel`（行 4570–4689）
- class `mobile-card p-0 overflow-hidden h-screen flex flex-col max-h-full`。
- 头部：铃铛图标 + `span#mobile-notification-badge`（初始 `hidden`，红点角标）+ `h3` “通知中心”。
- 列表 `div#mobile-all-notifications-list`（初始占位：铃铛 SVG + “暂无通知” / “点击底部刷新按钮获取最新通知”）。
- 底部按钮：
  - `button#mobile-refresh-notifications-btn`（`onclick="mobileRefreshNotifications()"`，aria“刷新通知”，“刷新”）
  - `button#mobile-mark-all-read-panel-btn`（`onclick="mobileMarkAllAsRead()"`，“一键已读”）
  - 隐藏按钮（`style="display:none"`）`onclick="expandMobileNotifications()"`（“查看更多”）

### 4.2 任务列表面板 `#mobile-task-panel`（行 4694–4773）
- class `mobile-card p-0 min-h-screen flex flex-col`。
- 头部：绿色任务图标 + `h3` “任务列表” + `div#mobile-task-count`（初始“0 个任务”）。
- `div#mobile-task-list`（初始“暂无任务”）。
- 底部两按钮（grid-cols-2）：
  - “刷新” `onclick="mobileRefreshTasks()"`
  - “新增” `onclick="mobileAddTask()"`（**初始 `style="display:none"`**）

### 4.3 地图面板 `#mobile-map-panel`（行 4778–4854）
- class `mobile-card p-0 overflow-hidden h-screen flex flex-col`。
- `div#mobile-map-container`（`height: calc(100vh - 60px)`；初始占位“地图加载中...”）。
- `button#mobile-map-reset-btn`（初始 `style="display:none"`，`onclick="resetMobileMapView()"`，title“复位视角”）。
- 底部工具条：
  - “放大 +” `onclick="mobileZoomIn()"`
  - “缩小 -” `onclick="mobileZoomOut()"`
  - （注释掉的“适应 ⊡” `mobileFitView()`）
  - “复位 ⊙” `onclick="resetMobileMapView()"`

### 4.4 控制面板 `#mobile-control-panel`（行 4859–5172）
- class `mobile-card`。头部橙色图标 + `h3` “控制面板”。
- **状态块**（行 4880）：`span#mobile-status-indicator`（初始“未启动”）、`div#mobile-status-detail`（初始“等待执行任务”）。
- **主控按钮**（grid-cols-2，行 4895）：
  - `button#mobile-start-btn`（`onclick="mobileStartTask()"`，绿色，“开始”）
  - `button#mobile-stop-btn`（`onclick="mobileStopTask()"`，红色，`disabled`，“停止”）
- **隐藏三按钮组**（`style="display:none"`）：暂停 `mobilePauseTask()` / 继续 `mobileResumeTask()` / 重置 `mobileResetTask()`。
- **隐藏进度条块**（`display:none`）：`span#mobile-progress-text`（0%）、`div#mobile-progress-bar`。
- **任务统计块** `#mobile-run-stats-block`（行 4997）：`p#mobile-run-stats-label`（初始 “-- km / --:--”）。
- **单任务进度块** `#mobile-single-progress-block`：`div#mobile-single-progress-fill`、`span#mobile-single-progress-text`（初始“未开始”）、`span#mobile-single-progress-extra`。
- **隐藏执行选项**（`display:none`）：`input#mobile-run-completed-check`（“忽略已完成状态”）、`input#mobile-auto-gen-all-check`（`checked`，“自动生成路径”，其 label 亦 `display:none`）。
- **路径工具**（行 5072）：
  - `button#mobile-path-tools-toggle`（inline onclick 切换 `#mobile-path-tools-area` 的 `hidden` 并旋转箭头，“路径工具”）
  - `div#mobile-path-tools-area`（初始 `hidden`），内含 5 个按钮（均无 onclick，由 JS 绑定 id）：
    - `mobile-record-button`（录制路径）
    - `mobile-auto-gen-button`（自动生成）
    - `mobile-process-button`（处理路径）
    - `mobile-clear-button`（清除路径）
    - `mobile-export-button`（导出，`col-span-2`）
- **实时状态面板**（行 5099，`#mobile-live-stats-grid`）：
  - `p#mobile-live-dist-label`（已跑距离，0.00 km）
  - `p#mobile-total-dist-label`（总距离，0.00 km）
  - `p#mobile-live-time-label`（已用时间，00:00）
  - `p#mobile-total-time-label`（预计时间，00:00）
  - `p#mobile-remaining-time-label`（预估剩余时间，00:00，`col-span-2`）
  - `p#mobile-current-location-label`（初始“当前位置: --, --”）

### 4.5 日志面板 `#mobile-log-panel`（行 5177–5246，初始 `hidden`）
- 头部“运行日志”。
- `textarea#mobile-log-text`（`readonly`，placeholder“等待日志输出...”）。
- 底部：“清空日志” `onclick="clearMobileMultiLog()"`、“滚到底部” `onclick="scrollMobileMultiLogToBottom()"`。

### 4.6 打卡点面板 `#mobile-checkpoints-panel`（行 5251–5319）
- class `mobile-card flex flex-col h-full mobile-card-fullscreen`。头部红色定位图标 + “打卡点”。
- `p#mobile-checkpoints-task-info`（初始“请先选择一个任务以查看打卡点”）。
- `div#mobile-checkpoints-list`（初始“开始任务后将显示打卡点”）。
- 底部刷新按钮（inline onclick：`renderMobileCheckpointsList(); showModalAlert('打卡点列表已刷新','成功');`，“刷新列表”）。

### 4.7 历史记录面板 `#mobile-task-history-panel`（行 5321–5385）
- class `mobile-card h-full flex flex-col mobile-card-fullscreen`。头部琥珀色时钟图标 + “历史记录”。
- `p#mobile-history-task-info`（初始“请先选择一个任务以查看历史记录”）。
- `div#mobile-task-history-list`（初始“加载中...”）。
- 底部刷新按钮 `onclick="loadMobileTaskHistoryPanel()"`（“刷新列表”）。

### 4.8 自动签到面板 `#mobile-attendance-panel`（行 5390–5676）
- class `mobile-card`。头部蓝色对勾图标 + “自动签到”。
- **参数配置卡**（行 5417）：
  - `input#mobile-param-auto_attendance_enabled`（`type=checkbox`，`data-key="auto_attendance_enabled"`）——“🎯 开启自动签到”，副文“后台自动刷新通知并尝试签到”，警示“⏱ 启用后 120 分钟内将自动关闭”。
  - `input#mobile-param-auto_attendance_refresh_s`（`type=number`，`step=5 min=10`，`data-key="auto_attendance_refresh_s"`，placeholder 15，title“自动刷新通知的间隔时间（秒），最小10秒”）——“⏰ 刷新间隔”，单位“秒”。
  - `input#mobile-param-attendance_user_radius_m`（`type=number step=1`，`data-key="attendance_user_radius_m"`，placeholder 0）——“📍 随机半径”，单位“米”，警示“⚠ 若随机半径超过签到允许的最大范围，将自动缩减至该上限。”
  - 底部按钮：
    - “重置” `onclick="switchMobileSinglePanel('mobile-attendance-panel')"`
    - “保存配置” `onclick="saveMobileAttendanceParams()"`
- **签到任务卡**（行 5604）：
  - 标题 “📋 签到任务”
  - `button#mobile-refresh-attendance-list-btn`（`onclick="refreshNotificationsUI(true, true)"`，“刷新”）
  - `div#mobile-attendance-list`（初始占位“点击"刷新"按钮查看签到任务”）。

### 4.9 参数设置面板 `#mobile-settings-panel`（行 5681–5754，初始 `hidden`）
- 头部靛蓝齿轮图标 + “参数设置”。
- `div#mobile-params-container`（空，由 JS 填充）。
- 底部：“刷新” `onclick="refreshMobileSettings()"`、“保存” `onclick="saveMobileSettings()"`。

### 4.10 任务详情面板 `#mobile-task-details-panel`（行 5759–5956）
- class `mobile-card h-screen w-full flex flex-col bg-white`。头部 “任务详情”。
- `div#mobile-task-details-panel-content`：
  - `#mobile-task-details-empty`（“请先选择一个任务”）
  - `#mobile-task-details-basic`（`hidden`，“基本信息”，列表 `#mobile-task-details-basic-list`）
  - `#mobile-task-details-time`（`hidden`，“时间信息”，列表 `#mobile-task-details-time-list`）
  - `#mobile-task-details-points`（`hidden`，“打卡点列表”，列表 `#mobile-task-details-points-list`）
  - `#mobile-task-details-history`（`hidden` 且 `display:none`，“历史记录”，列表 `#mobile-task-details-history-list`）
- 底部刷新按钮 `onclick="loadMobileTaskDetails()"`（“刷新数据”）。

### 4.11 我的资料面板 `#mobile-profile-panel`（行 5961–6199）
- class `mobile-card flex flex-col h-full`。头部 “用户详情”。
- 内容区 `div#mobile-user-details-content-panel`：
  - `#mobile-user-details-empty`（“请先登录”）
  - `#mobile-user-details-avatar`（`hidden`）：`img#mobile-user-details-avatar-img`（`onerror` 内联 SVG 占位👤）+ `p#mobile-user-details-name`
  - `#mobile-user-details-basic`（`hidden`，“基本信息”，列表 `#mobile-user-details-basic-list`）
  - `#mobile-user-details-school`（`hidden`，“学校信息”，列表 `#mobile-user-details-school-list`）
  - `#mobile-user-details-login`（`hidden`，“登录信息”，列表 `#mobile-user-details-login-list`）
  - `#mobile-user-details-ua`（`hidden`，“User-Agent”，`#mobile-user-details-ua-text`）
  - 隐藏退出按钮（`display:none`）`onclick="mobileLogout()"`（“退出登录”）
- 底部刷新按钮 `onclick="loadMobileUserDetails()"`（“刷新信息”）。

---

## 5. 统一管理面板 `#mobile-admin-panel-unified`（行 6209–10477）

- id：`mobile-admin-panel-unified`；class `mobile-card relative overflow-hidden !p-5 hidden`（**初始隐藏**）。原名 `mobile-multi-admin-panel`。
- 装饰渐变圆背景两枚。
- 头部：齿轮图标 + `h3` “管理面板” + `div#mobile-admin-panel-unified-status`（初始“多账号管理”）。
- **标签导航容器** `div#mobile-multi-admin-tabs-nav-panel`（行 6270，**空，由 JS 动态生成 tab 按钮**，水平滚动）。
- **内容容器** `div#mobile-multi-admin-content-panel`（行 6284）。

> 切换机制：`switchMobileAdminTab(tabId, 'mobile-admin-panel-unified')`。子面板 id 规则 `mobile-multi-admin-{tabId}-panel`，列表 id 规则 `mobile-multi-admin-{tabId}-list`。除 `users` 面板外，其余子面板初始均带 `hidden`。

### 5.1 用户管理 `#mobile-multi-admin-users-panel`（行 6291–6367，**初始可见**，tabId=users）
- 标题“用户列表”。
- 操作：`button#mobile-multi-admin-create-user`（“新增”）、`button#mobile-multi-admin-refresh-users`（“刷新”）——无 inline onclick。
- 搜索：`input#mobile-multi-admin-users-search-input`（placeholder“搜索昵称 / 用户名 / 手机号 / 学校账号”）+ `button#mobile-multi-admin-users-search-btn`（`onclick="loadAdminUsers()"`，“搜索”）。
- 排序：`select#mobile-admin-users-sort-field`（`onchange="resortAdminUsers()"`，选项：created_at 创建时间 / auth_username 用户名 / nickname 昵称 / last_login 最后登录时间 / max_sessions 会话限制数量 / available_runs 可用次数 / tfa 2FA）；`button#mobile-admin-users-sort-dir`（`onclick="toggleAdminUsersSort()"`，`data-dir="desc"`，初始“↓ 降序”）。
- 列表 `div#mobile-multi-admin-users-list`（初始“加载中...”）。

### 5.2 权限组 `#mobile-multi-admin-groups-panel`（行 6374–6407，`hidden`，tabId=groups）
- 标题“权限组列表”。
- `button#mobile-multi-admin-create-group`（“新增”）、`button#mobile-multi-admin-refresh-groups`（“刷新”）。
- 列表 `div#mobile-multi-admin-groups-list`（“加载中...”）。

### 5.3 日志查看 `#mobile-multi-admin-logs-panel`（行 6414–6512，`hidden`，tabId=logs）
- 标题“系统日志”。
- 过滤控件：
  - `select#mobile-multi-log-level-filter`（全部级别 / debug / info / warning / error）
  - `input#mobile-multi-log-keyword-filter`（placeholder“输入关键词过滤”）
  - `select#mobile-multi-log-limit-select`（每页100/200/500/1000行）
  - `button#mobile-multi-admin-refresh-logs`（“刷新”）
- 内容 `pre#mobile-multi-admin-logs-content`（终端风格，初始“加载中...”）。
- 分页 `#mobile-multi-admin-logs-pagination`：`button#mobile-multi-log-prev-page`（上一页）、`select#mobile-multi-log-page-select`（初始“第 1 / 1 页”）、`span#mobile-multi-log-page-total`（“(共 0 行)”）、`button#mobile-multi-log-next-page`（下一页）。

### 5.4 系统状态 `#mobile-multi-admin-health-panel`（行 6519–6562，`hidden`，tabId=health）
- 标题“系统状态”。
- `input#mobile-multi-health-auto-refresh-toggle`（`checkbox`，`checked`，“自动刷新”）+ `span#mobile-multi-health-countdown-display`（倒计时）。
- `button#mobile-multi-admin-refresh-health`（“刷新”）。
- 内容 `div#mobile-multi-admin-health-content`（“加载中...”）。

### 5.5 个人信息 `#mobile-multi-admin-profile-panel`（行 6569–7076，`hidden`，tabId=profile）
- 标题“个人信息”，`button#mobile-unified-refresh-profile`（`onclick="loadMobileUnifiedProfile()"`，“刷新”）。
- 内容 `div#mobile-unified-profile-content`：
  - **头像**：`img#mobile-unified-profile-avatar-display`（`onerror` SVG 占位）、`input#mobile-unified-profile-avatar-file`（`type=file`，`onchange="handleMobileUnifiedAvatarFile(this.files[0])"`）、`button#mobile-unified-avatar-upload-btn`（inline onclick 触发上传，“选择图片”）。
  - **基本信息**：
    - `#mobile-profile-available-runs-container`（`hidden`）→ `p#mobile-profile-available-runs-text`（“剩余次数”，初始“加载中...”）
    - `input#mobile-unified-profile-auth-username`（“用户名”，`readonly`）
    - `input#mobile-unified-profile-nickname`（“昵称”，placeholder“输入昵称”）
    - `button` “保存基本信息” `onclick="updateMobileUnifiedBasicInfo()"`
    - 手机号：`input#mobile-unified-profile-phone`（前缀+86，`readonly`）+ `button#mobile-unified-modify-phone-btn`（`onclick="showMobileUnifiedModifyPhoneModal()"`，“修改手机号”）+ 提示 `p#mobile-unified-modify-phone-hint`（“💡 修改手机号需要短信验证”）
  - **修改密码**：
    - `#mobile-password-verify-section`：`input#mobile-unified-current-password`（“当前密码”）；提示 `p#mobile-forgot-password-hint` 含 `button#mobile-sms-toggle-btn`（`onclick="toggleSmsVerifyMode('mobile')"`，“使用短信验证”）
    - `#mobile-sms-verify-section`（`hidden`）：`input#mobile-password-sms-code`（短信验证码）+ `button#mobile-send-sms-btn`（`onclick="sendPasswordResetSmsCode('mobile')"`，“发送验证码”）+ 返回按钮 `toggleSmsVerifyMode('mobile')`
    - `input#mobile-unified-new-password`（“新密码”）
    - `input#mobile-unified-confirm-password`（“确认新密码”）
    - `button` “修改密码” `onclick="updateMobileUnifiedPassword()"`
  - **双因素认证(2FA)**：状态 `span#mobile-unified-2fa-status`（“检测中...”）；`#mobile-unified-2fa-setup`（`hidden`：`canvas#mobile-unified-2fa-qr`、`span#mobile-unified-2fa-secret`、`input#mobile-unified-2fa-code`、`button` “启用2FA” `enableMobileUnified2FA()`）；`#mobile-unified-2fa-actions`（`button` “生成2FA密钥” `generateMobileUnified2FA()`）；`#mobile-unified-2fa-enabled-actions`（`hidden`：`button` “测试2FA” `test2FA()`、“关闭2FA” `disableMobileUnified2FA()`）。
  - **主题设置**：`select#mobile-unified-theme-select`（`onchange="updateMobileUnifiedTheme()"`，浅色/深色）；`#mobile-unified-theme-style-presets` → `#mobile-unified-theme-style-buttons`（JS 填充）；基础颜色 `input#mobile-unified-theme_base_color-picker`（`type=color`，`onchange` 同步文本+`onColorPicked`+`saveUnifiedThemeColor`）、`input#mobile-unified-theme_base_color`（文本 hex，`onchange` 校验后同步）、`button` “恢复默认” `resetBaseColorToDefault('mobile-unified')`。
  - **我的账单** `#mobile-user-billing-section`：`button` “刷新” `loadMobileUserBillingList()`；容器 `#mobile-user-billing-list-container`，内 `button` “批量支付” `paySelectedBilling('mobile-user-billing-list-container')`，初始“点击刷新加载账单记录”。
  - **账号注销**：`span#mobile-account-cancel-status`（“未申请”）；`input#mobile-account-cancel-current-password`（当前密码）；`input#mobile-account-cancel-sms-code` + `button` “发送验证码” `sendAccountCancelSmsCode('mobile')`；`button` “申请注销” `requestAccountCancellation('mobile')`。提示“需验证当前密码和短信验证码，提交后进入默认24小时等待期。”

### 5.6 会话管理 `#mobile-multi-admin-sessions-panel`（行 7083–7179，`hidden`，tabId=sessions）
- `h4` “会话列表”。
- `#mobile-multi-god-mode-toggle`（`display:none`）：`input#mobile-multi-god-mode-checkbox` + 文案“查看系统中的所有会话”。
- `div#mobile-multi-admin-session-count-display`（会话计数）。
- `button#mobile-multi-admin-refresh-sessions`（`onclick="loadMobileAdminSessionsList()"`，“刷新”）。
- `#mobile-multi-admin-create-session-container`：`button` “创建新会话” `createNewSessionFromPicker()`。
- 提示条“长按会话可删除，双击即可切换”。
- 列表 `div#mobile-multi-admin-sessions-list`（“加载中...”）。

### 5.7 留言板 `#mobile-multi-admin-messages-panel`（行 7186–7304，`hidden`，tabId=messages）
- `h4` “留言板”，`button#mobile-multi-admin-refresh-messages`（`onclick="switchMobileAdminTab('messages','mobile-admin-panel-unified')"`，“刷新”）。
- 发表区：`#mobile-multi-message-guest-fields`（`hidden`：`input#mobile-multi-message-nickname`、`input#mobile-multi-message-email`）；`textarea#mobile-multi-message-content`（无JS回退，maxlength 1000）；`div#mobile-multi-message-editor`（Editor.md 容器）；`span#mobile-multi-message-char-count`（0/1000）；`button#mobile-multi-post-message-btn`（`onclick="submitMobileMultiMessage()"`，“发表”）。
- 列表 `div#mobile-multi-admin-messages-list`（初始 spinner + “加载中...”）。

### 5.8 账单管理 `#mobile-multi-admin-billing-panel`（行 7306–7430，`hidden`，tabId=billing）
- 头部“账单管理 / 查询账单记录”；`button` “刷新” `loadMobileMultiAdminBillingList()`；`button` “添加” `adminAddBillingDialog()`。
- 搜索：`input#mobile-multi-admin-billing-school-input`（“学校账号（留空查询有权限全部）”）、`input#mobile-multi-admin-billing-search-input`（“搜索账单关键词”）、`button#mobile-multi-admin-billing-search-btn`（`onclick="loadMobileMultiAdminBillingList()"`，“搜索”）。
- 列表 `div#mobile-multi-admin-billing-list`（初始“点击查询加载账单记录”）。

### 5.9 账单日志 `#mobile-multi-admin-billing-logs-panel`（行 7432–7480，`hidden`，tabId=billing-logs）
- 头部“账单日志 / 审计账单创建、修改、清除等记录”；`button` “刷新” `loadMobileBillingLogs(1)`。
- 搜索：`input#mobile-billing-logs-search-input`（“搜索账单号 / 用户 / 手机”）；`select#mobile-billing-logs-event-type`（全部事件 / billing_created 创建 / billing_amount_changed 金额变化 / billing_status_changed 状态变化 / billing_admin_cleared 管理员清除 / billing_reason_changed 原因变化 / billing_deleted 删除）；`button` “搜索” `loadMobileBillingLogs(1)`。
- 列表 `div#mobile-billing-logs-list`（初始“点击搜索加载账单日志”）。
- 分页：`button#mobile-billing-logs-prev-btn`（`onclick="loadMobileBillingLogsPrev()"`，“上一页”）、`span#mobile-billing-logs-page-info`（“1 / 1”）、`button#mobile-billing-logs-next-btn`（`onclick="loadMobileBillingLogsNext()"`，“下一页”）。

### 5.10 账号恢复 `#mobile-multi-admin-restore-account-panel`（行 7482–7501，`hidden`，tabId=restore-account）
- `h4` “账号恢复”，`button` “刷新” `loadMobileMultiRemovedAccountsList()`。
- 列表 `div#mobile-multi-removed-accounts-list`（初始“点击刷新加载已删除账号记录”）。

### 5.11 IP封禁 `#mobile-multi-admin-ipban-panel`（行 7508–7617，`hidden`，tabId=ipban）
- `h4` “IP封禁”，`button#mobile-multi-admin-refresh-ipban`（`onclick="mobileRefreshIPBanList()"`，“刷新”）。
- 现有规则列表 `div#mobile-multi-ip-ban-list`（“加载中...”）。
- 添加规则区 `#mobile-banip-basicopentic`（提示单IP/IP范围格式）：
  - `select#mobile-multi-ban-type`（`onchange="mobileUpdateBanTargetHint()"`，单个IP / IP范围）
  - `input#mobile-multi-ban-target`（`oninput="mobileValidateIPBanTarget()"`，placeholder“例如：192.168.1.1”）
  - `p#mobile-multi-ban-target-hint`（“示例: 192.168.1.1”）、`p#mobile-multi-ban-target-error`（`hidden`）
  - `select#mobile-multi-ban-scope`（封禁所有功能 all / 仅封禁留言板 messages_only）
  - `button#mobile-multi-add-ipban-btn`（`onclick="mobileAddIPBan()"`，“添加封禁规则”）

### 5.12 短信配置 `#mobile-multi-admin-sms-panel`（行 7624–7656，`hidden`，tabId=sms）
- `h4` “短信配置”，`button#mobile-multi-admin-refresh-sms`（“刷新”）。
- 内容 `div#mobile-multi-admin-sms-content`（“加载中...”）。
- `button` “💬 查看回复记录” `onclick="openSMSReplyLogsModal()"`。

### 5.13 系统配置 `#mobile-multi-admin-config-panel`（行 7663–7687，`hidden`，tabId=config）
- `h4` “系统配置”，`button#mobile-multi-admin-refresh-config`（“刷新”）。
- 提示条“地图提供方 provider 配置入口（PC / mobile 共用同一后端配置真相源）。”
- 内容 `div#mobile-multi-admin-config-content`（“加载中...”）。

### 5.14 验证码管理 `#mobile-multi-admin-captcha-panel`（行 7694–7814，`hidden`，tabId=captcha）
- `h4` “⚙️ 验证码设置”，`button#mobile-multi-admin-refresh-captcha`（`onclick="mobileLoadCaptchaSettings()"`，“刷新”）。
- 说明“本地验证码生成器：MicroPixelCaptcha…”。
- 设置项：`input#mobile-captcha-length`（长度3-6，默认4）、`input#mobile-captcha-scale-factor`（细分倍数，默认2）、`input#mobile-captcha-noise-level`（噪点比例，默认0.08）。
- 按钮：`button#mobile-save-captcha-settings-btn`（`onclick="mobileSaveCaptchaSettings()"`，“💾 保存设置”）、`button#mobile-test-captcha-btn`（`onclick="mobileTestCaptcha()"`，“🔄 测试生成”）、`button` “📜 查看历史记录” `openMobileCaptchaHistoryModal()`。
- 预览 `#mobile-captcha-test-preview`（`hidden`）：`#mobile-captcha-preview-display`、`span#mobile-captcha-preview-answer`。

### 5.15 定时提醒 `#mobile-multi-admin-reminders-panel`（行 7821–7926，`hidden`，tabId=reminders）
- `h4` “定时提醒”；`button#mobile-multi-admin-add-reminder`（`onclick="openMobileReminderEditModal()"`，“+ 添加”）；`button#mobile-multi-admin-refresh-reminders`（`onclick="mobileRefreshReminders()"`，“刷新”）。
- 统计：`#mobile-reminder-stat-total`（总计0）、`#mobile-reminder-stat-enabled`（启用0）、`#mobile-reminder-stat-disabled`（禁用0）。
- 内容 `div#mobile-multi-admin-reminders-content`（spinner + “加载中...”）。

### 5.16 HTTPS设置 `#mobile-multi-admin-ssl-panel`（行 7933–7953，`hidden`，tabId=ssl）
- `h4` “HTTPS设置”，`button#mobile-multi-admin-refresh-ssl`（“刷新”）。
- 内容 `div#mobile-multi-admin-ssl-content`（“加载中...”）。

### 5.17 CDN缓存设置 `#mobile-multi-admin-cdn-panel`（行 7959–8130，`hidden`，tabId=cdn）
- `h4` “CDN缓存设置”，`button#mobile-multi-admin-refresh-cdn`（`onclick="loadCDNConfig()"`，“刷新”）。
- 开关：`input#mobile-cdn-enabled-toggle`（`checkbox` 样式开关，“启用 CDN 缓存”）。
- `button#mobile-cdn-force-refresh-btn`（`onclick="triggerCDNForceRefresh()"`，“强制刷新服务器缓存”）。
- `input#mobile-cdn-cache-time`（`number`，默认3600），快捷按钮 1时=3600/6时=21600/24时=86400/7天=604800（inline onclick 直接赋值）。
- `button#mobile-cdn-save-config-btn`（`onclick="saveMobileCDNConfig()"`，“保存配置”）。

### 5.18 水印控制面板（版本A）`#mobile-multi-admin-watermark-panel`（行 8142–8374，`hidden`，tabId=watermark）
- 标题“高德地图去水印控制”，说明文案。
- 系统默认值区：`input#watermark-default-value-mobile`（`checkbox`，`onchange="updateWatermarkDefaultLabel()"`）+ `span#watermark-default-label-mobile`（JS 动态“允许/禁止”）。
- 用户权限配置：`button` “添加” `openAddWatermarkUserModal()`；`span#mobile-watermark-user-count`（“共 0 个用户”）；列表 `div#mobile-watermark-users-list`（“加载中...”）。
- 底部：`button` “刷新配置” `loadMobileWatermarkControlConfig()`、`button` “保存配置” `saveMobileWatermarkControlConfig()`。

### 5.19 支付日志 `#mobile-multi-admin-payment-logs-panel`（行 8388–8508，`hidden`，tabId=payment-logs）
- `h4` “支付日志”，`button#mobile-multi-admin-refresh-payment-logs`（“刷新”）。
- 筛选：`select#payment-logs-action-type`（全部操作 / create_order 创建订单 / query_order 查询订单 / payment_success 支付成功 / payment_fail 支付失败 / config_update 配置更新）；`input#payment-logs-start-date`（`type=date`）、`input#payment-logs-end-date`（`type=date`）；`button#search-payment-logs-btn`（“查询日志”）。
- 列表 `div#mobile-multi-admin-payment-logs-list`（“加载中...”）。
- 分页：`button#payment-logs-prev-btn`（`disabled`，上一页）、`span#payment-logs-page-info`（“第 1 页”）、`button#payment-logs-next-btn`（下一页）。

### 5.20 支付设置 `#mobile-multi-admin-payment-settings-panel`（行 8515–9907，`hidden`，tabId=payment-settings）
- `h4` “支付设置”。
- **子 Tab 导航**（`switchPaymentSettingsTab(tab)`）：
  - `button#payment-settings-tab-config`（“支付方式”，初始激活）→ `switchPaymentSettingsTab('config')`
  - `button#payment-settings-tab-query`（“订单查询”）→ `('query')`
  - `button#payment-settings-tab-refund`（“退款处理”）→ `('refund')`
  - `button#payment-settings-tab-test`（“测试支付”）→ `('test')`
  - `button#payment-settings-tab-yipay`（“易支付配置”）→ `('yipay')`
  - `button#payment-settings-tab-product-test`（“商品名测试”）→ `('product-test')`

#### 5.20.1 Tab 内容 · 支付方式配置 `#payment-settings-content-config`（行 8596，可见）
- `button` “添加支付方式” `openAddPaymentMethodModal()`。
- `div#payment-methods-list-mobile`（由 `loadPaymentMethodsConfig(false,true)` 填充）。
- `button` “刷新配置” `loadPaymentMethodsConfig()`；`button#admin-save-payment-methods-btn` “保存配置” `savePaymentMethodsConfig()`。
- 结果区 `div#admin-payment-config-result`（`hidden`）。

#### 5.20.2 Tab 内容 · 订单查询 `#payment-settings-content-query`（行 8713，`hidden`）
- 筛选：`select#admin-filter-status`（`onchange="filterPaymentOrders()"`，全部状态/pending 已创建待支付/paid 已支付/refunded_partial 已部分退款/refunded_full 已全额退款/frozen 已冻结/preauth 预授权/timeout 支付超时/failed 创建失败）；`select#admin-filter-paytype`（`onchange="filterPaymentOrders()"`，全部/alipay 支付宝/wxpay 微信支付）；`input#admin-filter-username`（`oninput="filterPaymentOrders()"`）；`input#admin-filter-orderno`（`oninput="filterPaymentOrders()"`）。
- 手动查询：`input#admin-manual-query-order-no`；`button` “加载本地” `loadAllPaymentOrders()`、`button` “查询” `queryOrderManually()`、`button` “从平台拉取” `fetchOrdersFromPlatform()`。
- 订单列表：`#admin-orders-table-container`，标题“订单列表” + `span#admin-orders-count`（“(加载中...)”），卡片容器 `div#admin-orders-table-body`（由 JS 渲染）。

#### 5.20.3 Tab 内容 · 退款处理 `#payment-settings-content-refund`（行 8984，`hidden`）
- 警告“退款操作不可撤销”。
- `input#refund-order-trade-no`（订单号*）、`input#refund-amount`（退款金额*，`type=number`）、`input#refund-no`（退款单号，可选）、`textarea#refund-reason`（退款原因，可选）。
- `button#process-refund-btn`（“确认退款”）。
- 结果：`#refund-result-container`（`hidden`，含 `span#refund-result-no`、`span#refund-result-amount`）、`#refund-error-result`（`hidden`，含 `span#refund-error-message`）。

#### 5.20.4 Tab 内容 · 测试支付 `#payment-settings-content-test`（行 9108，`hidden`）
- `input#test-payment-amount`（测试金额*，默认0.5）。
- 商品名方式：单选 `name="product-name-input-method"`（value=manual 手动输入（默认 checked）/ value=auto 自动生成，均 `onchange="toggleProductNameInputMethod()"`）；`#manual-product-name-container` → `input#test-payment-product`（默认“测试商品”）；`#auto-product-name-container`（`hidden`）→ `input#test-payment-quantity`（默认1，1-9999）。
- `select#test-payment-method`（alipay 支付宝/wxpay 微信支付/qqpay QQ钱包/unionpay 云闪付）。
- `select#test-payment-type`（`onchange="toggleAuthCodeFieldMobile()"`，jump 跳转支付 / html HTML支付 / qrcode 二维码支付 / urlscheme 小程序跳转 / jsapi JSAPI支付 / app APP支付 / scan 扫码支付 / wxplugin 小程序插件支付 / wxapp 小程序支付）。
- `#test-auth-code-container`（`hidden`，scan 用）→ `input#test-auth-code`（18位付款码）。
- `#test-jsapi-params-container`（`hidden`，jsapi 用）→ `input#test-sub-openid`、`input#test-sub-appid`。
- `button#create-test-order-btn`（“生成测试订单”）。
- 结果卡 `#test-order-result-container`（`hidden`）：订单信息（`#test-order-id`、`#test-order-trade-no`、`#test-order-amount`、`#test-order-pay-method`、`#test-order-method-type`、`#test-order-pay-type`），支付信息（`textarea#test-order-pay-url` 只读、`p#test-order-pay-info-desc`、`#test-order-qrcode-display` 隐藏），按钮 `button#open-test-pay-url-btn`（“打开链接”）、`button#copy-test-pay-url-btn`（`onclick="copyTestPayInfo()"`，“复制信息”）。
- 错误区 `#test-order-error-result`（`hidden`，含 `span#test-order-error-message`）。

#### 5.20.5 Tab 内容 · 易支付配置 `#payment-settings-content-yipay`（行 9596，`hidden`）
- `input#yipay-host`（域名*）、`input#yipay-pid`（商户ID*）、`input#yipay-key`（`type=password` 商户密钥*）、`input#yipay-enabled-methods`（启用支付方式*，逗号分隔）、`select#yipay-payment-method`（jump 跳转/web 网页/jsapi/app/scan 扫码/applet 小程序）。
- `button` “刷新配置” `loadMobileYiPayConfig()`、`button` “保存配置” `saveMobileYiPayConfig()`。
- 结果区 `div#yipay-config-result`（`hidden`）。

#### 5.20.6 Tab 内容 · 商品名测试 `#payment-settings-content-product-test`（行 9766，`hidden`）
- `input#product-test-quantity`（商品数量*，默认5，1-9999）。
- `button#generate-product-name-btn`（`onclick="testGenerateProductName()"`，“生成商品名”）。
- 结果 `#product-test-result`（`hidden`）：`p#product-test-name`、`p#product-test-length`。
- `button#batch-test-product-names-btn`（`hidden`，`onclick="batchTestProductNames()"`，“批量测试（生成10个示例）”）。
- 批量结果 `#batch-test-results`（`hidden`）→ `#batch-test-list`。

### 5.21 价格设置 `#mobile-multi-admin-pricing-panel`（行 9917–10239，`hidden`，tabId=pricing）
- `h4` “价格设置”，`button#mobile-multi-admin-refresh-pricing`（`onclick="loadMobilePricingConfig()"`，“刷新”）。
- 配置项：
  - `input#mobile-pricing-require-payment`（`checkbox` 开关，“是否需要付费”）
  - `input#mobile-pricing-per-run-cost`（`number`，“单次跑步费用（元）”）
  - `input#mobile-pricing-default-runs`（`number`，“新用户默认免费次数”）
  - `input#mobile-pricing-show-available-runs`（`checkbox` 开关，“个人资料页显示剩余次数”）
  - `input#mobile-pricing-available-runs-format`（文本，“剩余次数显示格式”，占位符 `{available_runs}`）
  - `input#mobile-pricing-show-register-hint`（`checkbox` 开关，“注册页显示免费次数提示”）
  - `input#mobile-pricing-register-hint-text`（文本，“注册页提示文本”，占位符 `{available_runs}`）
- `button` “保存配置” `saveMobilePricingConfig()`。

### 5.22 水印控制面板（版本B）`#mobile-multi-admin-watermark-control-panel`（行 10249–10385，`hidden`，tabId=watermark-control）
- `h4` “水印控制”，`button#mobile-multi-admin-refresh-watermark`（`onclick="loadMobileWatermarkControlConfig()"`，“刷新”）。
- 系统默认区：`span#mobile-watermark-default-value-ctrl`（“加载中...”）。
- 用户权限配置：`span#mobile-watermark-user-count-ctrl`（“共 0 个用户”）；列表 `div#mobile-watermark-users-list-ctrl`（“加载中...”）。
- `button` “保存配置” `saveMobileWatermarkControlConfig()`。
- 注：与 5.18 版本A 共用 `loadMobileWatermarkControlConfig` / `saveMobileWatermarkControlConfig`，但用独立 `-ctrl` 后缀 id 避免冲突。

### 5.23 密码恢复（暴力破解，超级管理员）`#mobile-multi-admin-bruteforce-panel`（行 10391–10475，`hidden`，tabId=bruteforce）
- `h4` “密码恢复”，`button#mobile-bruteforce-refresh-btn`（`onclick="loadBruteforceStatus()"`，“刷新”）。
- 隐藏红色警告（`display:none`）+ 蓝色功能说明（身份证后六位尝试恢复等）。
- `textarea#mobile-bruteforce-accounts`（placeholder“输入账号，每行一个”）。
- `button#mobile-bruteforce-start-btn`（`onclick="startBruteforce()"`，“开始恢复”）、`button#mobile-bruteforce-stop-all-btn`（`onclick="stopAllBruteforce()"`，“停止全部”）。
- 任务列表 `div#mobile-bruteforce-task-list`（初始“暂无任务”）。

- 行 10476 `</div>` 关闭 `#mobile-multi-admin-content-panel`；行 10477 `</div>` 关闭 `#mobile-admin-panel-unified`。

---

## 6. 关键 JS 函数索引（按功能归类，供复刻绑定核对）

- **认证/会话**：`toggleMobileSidebar`、`refreshCaptcha('mobile-login'|'mobile-register')`、`createNewSessionFromPicker`、`mobileLogout`。
- **通知/任务**：`mobileRefreshNotifications`、`mobileMarkAllAsRead`、`expandMobileNotifications`、`mobileRefreshTasks`、`mobileAddTask`、`loadMobileTaskDetails`、`loadMobileTaskHistoryPanel`。
- **地图**：`resetMobileMapView`、`mobileZoomIn`、`mobileZoomOut`、`mobileFitView`(注释)。
- **控制/执行**：`mobileStartTask`、`mobileStopTask`、`mobilePauseTask`、`mobileResumeTask`、`mobileResetTask`、`clearMobileMultiLog`、`scrollMobileMultiLogToBottom`。
- **打卡/签到/设置**：`renderMobileCheckpointsList`、`showModalAlert`、`switchMobileSinglePanel`、`saveMobileAttendanceParams`、`refreshNotificationsUI`、`refreshMobileSettings`、`saveMobileSettings`。
- **资料**：`loadMobileUserDetails`、`loadMobileUnifiedProfile`、`handleMobileUnifiedAvatarFile`、`updateMobileUnifiedBasicInfo`、`showMobileUnifiedModifyPhoneModal`、`toggleSmsVerifyMode`、`sendPasswordResetSmsCode`、`updateMobileUnifiedPassword`、`generateMobileUnified2FA`、`enableMobileUnified2FA`、`test2FA`、`disableMobileUnified2FA`、`updateMobileUnifiedTheme`、`onColorPicked`、`saveUnifiedThemeColor`、`resetBaseColorToDefault`、`loadMobileUserBillingList`、`paySelectedBilling`、`sendAccountCancelSmsCode`、`requestAccountCancellation`。
- **管理面板**：`switchMobileAdminTab`、`loadAdminUsers`、`resortAdminUsers`、`toggleAdminUsersSort`、`loadMobileAdminSessionsList`、`submitMobileMultiMessage`、`loadMobileMultiAdminBillingList`、`adminAddBillingDialog`、`loadMobileBillingLogs`/`loadMobileBillingLogsPrev`/`loadMobileBillingLogsNext`、`loadMobileMultiRemovedAccountsList`、`mobileRefreshIPBanList`、`mobileUpdateBanTargetHint`、`mobileValidateIPBanTarget`、`mobileAddIPBan`、`openSMSReplyLogsModal`、`mobileLoadCaptchaSettings`、`mobileSaveCaptchaSettings`、`mobileTestCaptcha`、`openMobileCaptchaHistoryModal`、`openMobileReminderEditModal`、`mobileRefreshReminders`、`loadCDNConfig`、`triggerCDNForceRefresh`、`saveMobileCDNConfig`、`updateWatermarkDefaultLabel`、`openAddWatermarkUserModal`、`loadMobileWatermarkControlConfig`、`saveMobileWatermarkControlConfig`、`loadBruteforceStatus`、`startBruteforce`、`stopAllBruteforce`。
- **支付**：`switchPaymentSettingsTab`、`openAddPaymentMethodModal`、`loadPaymentMethodsConfig`、`savePaymentMethodsConfig`、`filterPaymentOrders`、`loadAllPaymentOrders`、`queryOrderManually`、`fetchOrdersFromPlatform`、`toggleProductNameInputMethod`、`toggleAuthCodeFieldMobile`、`copyTestPayInfo`、`loadMobileYiPayConfig`、`saveMobileYiPayConfig`、`testGenerateProductName`、`batchTestProductNames`、`loadMobilePricingConfig`、`saveMobilePricingConfig`。

---

## 7. 复刻注意点（可见性/边界）

1. `#mobile-header` 及其 `#mobile-menu-btn` 均带 `display:none` + `hidden`，需 JS 显式点亮。
2. 三个子应用互斥切换：`#mobile-auth-login-container`（默认显）、`#mobile-login-container`（`hidden`）、`#mobile-main-app`（`hidden`）、`#mobile-admin-panel-unified`（`hidden`）。
3. `#mobile-admin-panel-unified` 的 tab 按钮完全由 JS 生成（`#mobile-multi-admin-tabs-nav-panel` 初始为空）；子面板初始仅 `users` 面板可见，其余 `hidden`，由 `switchMobileAdminTab` 切换。
4. 存在两套水印面板（tabId `watermark` 与 `watermark-control`），共用加载/保存函数但 id 后缀不同（`-mobile` vs `-ctrl`），复刻须保留两套以免 id 冲突。
5. 大量按钮无 inline onclick（如用户/权限组的新增/刷新、短信/SSL 刷新等），事件在 JS 中按 id 绑定，复刻时需对照脚本逐一接线。
6. 表单验证码、注册、2FA、游客区、账单/注销等均带初始 `hidden`，属条件展示。
