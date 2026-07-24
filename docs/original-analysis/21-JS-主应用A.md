# 21 · JS 主应用 A — 函数级完整解析

> **覆盖范围**：`scripts/main.new.js` 第 **14139 – 26329** 行（对应脚本块 9 的前半部分，banner 标记「JavaScript代码部分」）。
> 本段是「跑步助手」原始前端主逻辑核心，包含：网络错误状态机、移动端设备检测与 UI 容器切换、自动签到提示、`callPythonAPI` 统一后端调用、主题背景/风格管理、认证登录/注册/2FA/游客、图形验证码与短信验证码、管理面板（权限判定 + 标签切换）、日志查看、健康检测与倒计时、个人信息管理、头像裁剪上传、密码修改（短信验证模式）、2FA 管理、校园账号管理、创建用户/权限组、管理员用户列表渲染。
> 生成时间：2026-07-14。用途：Vue 重构版逐一复刻的权威依据。

---

## 0. 阅读约定

- **`$(id)`**（第 17166 行）= `document.getElementById(id)` 简写，全文大量使用。
- 弹窗统一用 **SweetAlert2**（`Swal.fire`）；旧 `showModalAlert` 被保留但内部也转调 `Swal.fire`。
- **socket.io**：本段**未注册任何 socket 事件监听/发射**，仅在网络错误状态机中操作全局 `socket` 对象（`socket.io.opts.reconnection`、`socket.connect()`、`socket.disconnect()`、`socket.connected`）。真正的 socket 事件名不在此范围。
- **关键全局变量**在 §1 集中列出；后续函数条目仅注明「读/写」。
- 后端 API 有两类：`/api/<method>`（经 `callPythonAPI`，POST + `X-Session-ID`）与直接 `fetch` 的 REST 端点（`/auth/*`、`/logs/*`、`/health` 等）。

---

## 1. 全局变量与常量（14145–14322, 16316–17347）

| 变量 | 初值 | 作用 |
|---|---|---|
| `refreshUserListInterval` | null | 用户列表刷新定时器句柄（30s） |
| `isInNetworkErrorState` | false | 网络错误状态机标志 |
| `networkRetryInProgress` | false | 请求级重试进行中 |
| `NETWORK_RETRY_MAX` | 3 | 请求失败最大重试次数 |
| `NETWORK_RETRY_DELAY_MS` | 2000 | 重试间隔 |
| `NETWORK_DIALOG_AUTO_RETRY_MAX` | 5 | 网络错误弹窗后台自动重试上限 |
| `NETWORK_DIALOG_AUTO_RETRY_INTERVAL_MS` | 8000 | 后台自动重试间隔 |
| `networkDialogAutoRetryCount` / `...Timer` | 0 / null | 后台自动重试计数 / 定时器 |
| `cdnErrorCount` / `cdnErrorTimer` / `appInitialized` | 0 / null / false | CDN 资源加载失败计数与遮罩定时 |
| `currentUserIsGuest` | false | 当前是否游客 |
| `currentAuthUsername` | null | 当前认证用户名 |
| `healthAutoRefreshInterval` / `multiAccountAutoRefreshInterval` | null | 健康/多账号自动刷新定时器 |
| `avatarCropper` | null | Cropper.js 实例 |
| `isRegistrationCrop` / `registrationCroppedAvatarBlob` | false / null | 注册头像裁剪状态与结果 blob |
| `croppedAvatarFile` | null | 个人资料头像裁剪结果 |
| `currentLogPage` | 1 | 日志分页当前页 |
| `LOG_HIGHLIGHT_RULES` | 数组 | 日志高亮规则（error/warning/info/debug 正则 + class） |
| `currentSessionInfo` | `{maxSessions:1,currentCount:0}` | 会话计数缓存 |
| `isMobileMode` | false | 是否移动端 UI 模式（全局关键开关） |
| `DEFAULT_VIEWPORT_CONTENT` | `"width=device-width, initial-scale=1"` | 默认 viewport |
| `_desktopViewportForced` | false | 是否强制桌面视口 |
| `AMAP_API_KEY` | "" | 高德 key |
| `IS_OFFLINE` | false | 离线标志 |
| `authSessionUUID` | null | 认证会话（登录后颁发，区别于业务会话 `sessionUUID`） |
| `authRequestGeneration` | 0 | 认证请求代次（防旧响应误判多设备登出） |
| `authLoginInProgress` | false | 登录流程进行中 |
| `AUTH_CONTEXT_API_METHODS` | `Set(["get_initial_data"])` | 允许无会话兜底的方法 |
| `$` | `(id)=>getElementById` | DOM 简写 |
| 地图相关 | `AMapInstance,map,providerMapInstances...` | 地图实例集合（本段仅声明） |
| `currentTasks/selectedTaskIndex/currentUserData/currentRunData` | 空 | 任务/用户/运行数据 |
| `polylines/markers/runnerMarker` 等 | 空 | 地图覆盖物 |
| `userColors` | 16 色数组 | 多账号标记颜色 |
| `paramDefs` / `paramGroups` | 对象/数组 | 参数元数据（label/unit/help/type：采样速度、任务间隔、路径规划重试、自动生成目标、自动签到、主题风格 `theme_selector`、主题色 `color_picker`、checkbox） |
| `pythonParams/currentThemeConfig/availableThemeStyles` | 空 | 后端参数 / 主题配置 / 可用主题风格 |
| `cachedMultiAccounts` | [] | 多账号缓存 |
| 验证码 ID | `captchaIds_login/register/mobile-login/mobile-register/modal` | 各表单图形验证码 ID（分离变量，非对象） |

---

## 2. 网络错误状态机（14155–14264）

### `checkServerHealth()` — 14155
- **职责**：`AbortController` 5s 超时探测服务器是否存活。
- **API**：`GET /health`（`cache:"no-cache"`）。
- **返回**：`Promise<boolean>`（`res.ok`；异常/超时→false）。

### `enterNetworkErrorState()` — 14171
- **职责**：进入网络错误态；幂等（已进入则返回）。副作用：清 `refreshUserListInterval`；关闭 socket 重连 `socket.io.opts.reconnection=false` 并 `socket.disconnect()`。写 `isInNetworkErrorState=true`。日志 `logMessage_Info`。

### `exitNetworkErrorState()` — 14186
- **职责**：退出网络错误态。`stopDialogAutoRetry()`，重置计数。延迟 1s 后重建 `refreshUserListInterval`（`setInterval(refreshUserList,30000)`）并在有 `sessionUUID` 时恢复 socket 重连 + `socket.connect()`。

### `stopDialogAutoRetry()` — 14204 / `startDialogAutoRetry()` — 14211
- 管理网络错误弹窗的**后台自动重试**定时器：每 8s 探测 `checkServerHealth()`，成功则 `Swal.close()` + `exitNetworkErrorState()`；达上限（5 次）停止等待用户手动。

### `showNetworkErrorDialog()` — 14234
- **职责**：弹出「网络错误」`Swal.fire`（html=`getServerConnectionGuidanceMessage()`，icon error，`allowOutsideClick/EscapeKey:false`，`didOpen` 内只允许 Enter 键）。确认→再 `checkServerHealth()`，存活则退出错误态，否则递归重弹。

### `safeRemoveModalVisible()` — 14266
- **职责**：若无任何 `.flex` 模态（`#admin-panel-modal / #mobile-admin-panel-modal / #amap-key-modal / #user-details-modal / #task-details-modal / #account-params-modal`）打开，则移除 `body.modal-visible`。

---

## 3. 移动端检测与 UI 容器切换（14317–14587, 16149–16158）

### `shouldForceDesktopLayout()` — 14325
- 触屏且视口宽度 `0<w<1024` → true（用于平板强制桌面版）。

### `applyDesktopForcedViewport(forceDesktop)` — 14337
- 操作 `meta[name=viewport]`：强制时设 `width=1280, initial-scale=0.25, minimum-scale=0.25`；否则恢复默认。用 `_desktopViewportForced` 去抖。

### `detectMobileDevice()` — 14357
- 依据 `navigator.userAgent` 正则（`Android|webOS|iPhone|iPad|...|Mobile|CriOS`）判定，返回布尔。仅 UA，不监听 resize。

### `switchUIContainer()` — 14369 ★核心
- **职责**：在 PC 容器 `#desktop-container` 与移动容器 `#mobile-container` 之间切换，并**跨端保持当前界面态**。
- **DOM**：`#mobile-container`、`#desktop-container`；桌面四态 `#auth-login-container / #login-container / #main-app / #multi-account-app`；移动四态 `#mobile-login-container / #mobile-auth-login-container / #mobile-main-app / #mobile-multi-account-app`；`#mobile-loading-overlay`、`#newbie-help-btn`、`#admin-panel-modal`、`#session-picker-modal`。
- **逻辑**：
  - `isMobile` 写 `isMobileMode`；`desktopForced` 时 `body.desktop-forced-mode` 切换 + 强制视口。
  - **移动分支**：隐藏所有桌面元素（`display/visibility/pointer-events !important`），根据当前哪个桌面态可见，显示对应移动态并调 `updateMobileNavVisibility` + `switchMobileSinglePanel("mobile-control-panel")` / `switchMobilePanel("mobile-multi-control-panel","multi")`；销毁另一模式地图（`destroyMobileMultiMap`/`destroyMobileSingleMap`）；auth 态下把 `#newbie-help-btn` 固定右上并 `makeDraggable`；`body.mobile-mode` + `initializeMobileUI()`。
  - **桌面分支**：还原桌面元素样式，恢复 `#newbie-help-btn` 原始样式，按移动态可见性显示对应桌面态（`main-app` 加 `grid`）。
- **绑定**：`DOMContentLoaded`（16149）→ `switchUIContainer()` + `syncThemeBackgroundTarget()`。

---

## 4. 自动签到提示（14589–14908）

### `saveMobileAttendanceParams()` — 14589
- **DOM**：`#mobile-param-auto_attendance_enabled`(checkbox)、`#mobile-param-auto_attendance_refresh_s`、`#mobile-param-attendance_user_radius_m`。
- **校验**：刷新间隔 ≥10s。
- **API**：三次 `callPythonAPI("update_param", key, value)`（`auto_attendance_enabled` / `auto_attendance_refresh_s` / `attendance_user_radius_m`）。同步写 `pythonParams`。
- **副作用**：成功 `Swal`（1.5s timer）后调 `showAutoAttendanceToggleAlert(enabled,true)`。

### `showAutoAttendanceToggleAlert(enabled, isMobile)` — 14665
- 依据 `currentUserData`（name/student_id）构建卡片（移动）或表格（PC）HTML，`Swal.fire` 展示自动签到开/关状态；开启时提示「120 分钟内自动关闭」。读 `cachedMultiAccounts`（判断是否有账号）。

### `showMultiAutoAttendanceToggleAlert(enabled, isMobile)` — 14782
- 多账号版：无账号时提示「后续添加的账号将自动开启」；有账号则列表（卡片/表格）展示 `cachedMultiAccounts`；开启提示 120 分钟自动关闭。

---

## 5. sessionUUID 守卫（14910–14953）

### `isSessionUUIDInvalid(uuid)` — 14910
- 空/`"null"`/纯空白 → true。

### `run_code_need_sessionuuid(codeToRun)` — 14914
- 若 `sessionUUID` 无效则尝试 `getUUIDFromURL()` 提取；仍无效→报错不执行，有效→执行回调。

### `run_code_not_need_sessionuuid(codeToRun)` — 14935
- 逻辑相反：仅当**无有效 sessionUUID** 时才执行回调（用于「未登录时跳过」的守卫）。

---

## 6. 移动端 UI 初始化与登录（14955–15561）

### `initializeMobileUI()` — 14955 ★大函数
- **职责**：绑定移动端认证/登录页全部交互。内部含闭包 `showMobileAuthForm(formToShow)`。
- **内部 `showMobileAuthForm(formToShow)`**：切换 `#mobile-login-form / #mobile-register-form / #mobile-auth-2fa-form`，更新 tab 样式（`#mobile-auth-tab-login/register`），调 `loadCaptcha("register"/"login")` + `showMobileMessage("","clear")`。
- **绑定事件（全部 addEventListener）**：
  - Tab：`#mobile-auth-tab-login/register` → click。
  - 用户名/手机切换：`#mobile-login-username-btn` / `#mobile-login-phone-btn` 重写 `#mobile-username-container` 内输入框（用户名 vs `+86` 手机号），切换 `#mobile-password-section`/`#mobile-sms-section`、`#mobile-switch-to-sms` 显隐。
  - 密码↔短信：`#mobile-switch-to-sms` / `#mobile-switch-to-password`。
  - 发送登录验证码：`#mobile-auth-send-login-code` → 校验手机号 `^1[3-9]\d{9}$` → `openCaptchaModal({phone,button,originalText})`。
  - 发送注册验证码：`#mobile-reg-send-code-btn`（读 `#mobile-reg-phone`）→ `openCaptchaModal`。
  - 初始 `refreshCaptcha("mobile-login")` + `refreshCaptcha("mobile-register")`。
  - **登录按钮 `#mobile-login-btn`**：把移动端字段同步到隐藏 PC 表单（`#auth-username/password/sms-code/login-captcha`），同步 password/sms section 与 PC 用户名/手机按钮态，调 `handleAuthLogin(true)`；若出现 `#auth-2fa-form` 则切到 `#mobile-auth-2fa-form`。
  - 注册按钮 `#mobile-register-btn`：同步注册字段到 PC 表单后 `handleAuthRegister(true)`。
  - 游客 `#mobile-guest-btn` → `handleGuestLogin()`。
  - 2FA：`#mobile-2fa-submit-btn` 同步 `#auth-2fa-code` 后 `handle2FAVerify()`；`#mobile-2fa-back-btn` 返回登录并触发 `#auth-2fa-back-btn`.click()。
  - 头像：`#mobile-reg-avatar` change → `previewAvatarForRegistration`。
  - 游客区显隐：`fetch("/auth/get_config")`（带 `X-Session-ID`）→ `data.allow_guest_login` 控制 `#mobile-guest-login-section`。
  - **学校登录 `#mobile-single-login-btn`**：读 `#mobile-username-entry/#mobile-password-entry`，显示 `#mobile-loading-overlay`，同步到 `#username-entry/#password-entry`，调 `onLogin()`；成功切到 `#mobile-main-app` + `switchMobileSinglePanel` + `updateMobileNavVisibility(true,"single")` + `mobileRefreshNotifications(false)`。
  - `#mobile-user-combo` change → `onMobileUserChange`；`#mobile-username-entry` input → `callPythonAPI("on_user_selected", username)` 回填密码/UA（`syncUAToMobile`）。
  - `.mobile-nav-btn` 导航高亮（`data-nav`）。
  - `#mobile-menu-btn` → `toggleMobileSidebar()`。
  - **`#mobile-multi-account-btn`**：`stopBackgroundTaskPolling()` + `callPythonAPI_raw("/api/background_task/stop","POST")` + `onRunStopped()` → `callPythonAPI("enter_multi_account_mode")`，成功切到 `#mobile-multi-account-app` + `switchMobilePanel(...,"multi")` + `startMultiAccountAutoRefresh(500)`。
  - `#mobile-refresh-sessions-btn` → `loadMobileSessionsList()`。
  - 上帝模式复选框 `#mobile-multi-god-mode-checkbox` / `#mobile-god-mode-checkbox-panel` change → `loadMobileAdminSessionsList()`。
  - `run_code_need_sessionuuid(() => loadMobileUserCombo())`。
- **副作用**：进出隐藏 `#loading-overlay`。

### `loadMobileSessionsList()` — 15563 ★
- **DOM**：`#mobile-sessions-list`、`#mobile-session-count-display`、`#mobile-create-session-btn`、`#mobile-session-guest-msg`。
- **游客**：隐藏创建按钮、显示游客提示。
- **API**：`GET /auth/user/sessions`（`X-Session-ID`=`getAuthenticatedSessionHeaderValue()`）。
- **渲染**：过滤有效 session，按 `created_at` 倒序；每卡片显示完整 UUID / 创建时间 / 登录状态 / 当前会话徽标。
- **交互**：长按 500ms（`navigator.vibrate(50)`）显示删除遮罩→松手删除（`deleteSessionFromPicker`，当前会话禁止删除并 `Swal` 提示）；双击/双指切换会话（`showMobileConfirm` → `selectSessionFromPicker`）。绑定 `touchstart/touchmove/touchend/mousedown/mouseup/dblclick`。

### `loadMobileUserCombo()` — 15905
- 守卫无 sessionUUID 跳过；调 `loadInitialData()` 填充 `#mobile-user-combo`（含「(新用户)」），有 `lastUser` 则选中并 `onMobileUserChange()`。

### `onMobileUserChange()` — 15945
- 读 `#mobile-user-combo` 选中项 → 写 `#mobile-username-entry`，清 `#mobile-password-entry`；`callPythonAPI("on_user_selected", username)` 回填密码与 UA（`syncUAToMobile`）。

---

## 7. 移动端侧边栏与消息（15985–16148）

### `toggleMobileSidebar()` — 15985
- 依据 `#mobile-multi-account-app` 可见性选择 `#mobile-sidebar-single-account` 或 `#mobile-sidebar-multi-account`；配合 `#mobile-sidebar-backdrop` 打开/关闭（`show` class + 延时）。

### `closeMobileSidebar()` — 16023
- 移除 backdrop 与两个侧边栏的 `show`，300ms 后加 `hidden`。

### `updateMobileNavVisibility(show, mode="single")` — 16049
- 控制 `#mobile-menu-btn`、`#mobile-header`、两个侧边栏、底部导航 `#mobile-bottom-nav-single-account` / `#mobile-bottom-nav-multi-account` 的显隐（按 mode）。

### `showMobileMessage(message, type="info")` — 16116
- `type==="clear"`→隐藏 `#alert-modal`；否则 `Swal.fire`（error/success/info）。

---

## 8. 通用弹窗/模态（16162–16314）

### `handleCdnError(resourceName)` — 16162
- CDN 资源加载失败计数（`cdnErrorCount++`），3s 后若应用仍未初始化则显示 `#cdn-error-overlay`。由 HTML 中 `<script onerror>` 调用。

### `showModalAlert(message,title,onCloseCallback)` — 16190
- 兼容旧接口，内部据 title 关键词推断 icon（成功/错误/失败/警告）后 `Swal.fire`，关闭回调；Swal 不可用回退原生 `alert`。

### `showModal(modalId)` — 16223 / `hideModal(modalId)` — 16232
- 增删 `hidden`/`flex`；`hideModal` 会检查 `.modal, [id$="-modal"]` 是否仍有可见者决定是否移除 `body.modal-visible`。

### `jsShowConfirm(title,message)` — 16255 / `handleConfirm(result)` — 16288
- 基于 `#confirm-modal`（`#confirm-modal-title/message/ok-btn/cancel-btn`）的 Promise 化确认框；DOM 缺失回退原生 `confirm`。用模块级 `resolveConfirmPromise` 传递结果。

---

## 9. 认证会话工具（16326–16499）

| 函数 | 行 | 说明 |
|---|---|---|
| `isUsableClientSessionUUID(value)` | 16326 | 校验是否为合法 v4 UUID（排除 null/undefined/none） |
| `ensureAuthLoginSessionUUID()` | 16339 | 有效则返回 `sessionUUID`，否则从 URL 提取并写回 |
| `getAuthRequestSessionUUID()` | 16353 | 优先 `authSessionUUID`，否则 `ensureAuthLoginSessionUUID()` |
| `getAuthenticatedSessionHeaderValue()` | 16359 | 返回可用的 `authSessionUUID`→`sessionUUID`→"" |
| `isAuthContextApiMethod(method)` | 16371 | 是否属 `AUTH_CONTEXT_API_METHODS` |
| `getApiRequestSessionHeaderValue(method)` | 16375 | 登录中优先 authSession；否则 sessionUUID/URL 兜底逻辑 |
| `shouldSuppressLoggedOutElsewhereNotice(errorData,reqCtx,curCtx)` | 16400 | 判定是否忽略「多设备登出」旧响应（比对 authGeneration 与 sessionUUID） |
| `getServerConnectionGuidanceMessage()` | 16442 | 返回网络错误弹窗 HTML（含福建/江苏/贵州/广西运营商干扰、DNS 刷新建议等） |
| `getUUIDFromURL()` | 16487 | 从 `window.location.pathname` 的 `/uuid=<v4>` 提取 |

---

## 10. 后端调用核心（16501–17130）

### `callPythonAPI(method, ...args)` — 16501 ★★核心
- **API**：`POST /api/<method>`，`headers` 含 `Content-Type:application/json` 与（若可用）`X-Session-ID`；`credentials:"include"`；body：单对象参数直接透传，否则包成数组。
- **网络错误状态**：`isInNetworkErrorState` 时直接抛「网络连接已断开」。
- **失败重试**：`fetch` 抛异常时若无重试进行中→`checkServerHealth()`，存活则重试至多 `NETWORK_RETRY_MAX` 次（间隔 2s），否则 `enterNetworkErrorState()`+`showNetworkErrorDialog()`。
- **HTTP 错误分支处理**：
  - `403` + 「账号已被封禁」→ 创建全屏 `#account-banned-overlay`（渐变卡片 + 返回登录按钮 → `location.href="/"`），进入网络错误态，抛错。
  - `401` + 「会话已过期或无效」→ 登录流程/未登录场景静默；否则移动端切登录页，PC 端创建 `#logout-elsewhere-overlay`（120s 倒计时全屏遮罩）。
  - `errorData.need_login`：`logged_out_elsewhere` 分支创建 `#logout-elsewhere-overlay`（z-index 20002，120s 倒计时）— 用 `shouldSuppressLoggedOutElsewhereNotice` 抑制旧响应；否则 `Swal warning`「需要重新登录」→ 返回登录。
  - `403` + message → `Swal error`「权限不足」。
  - 其它 → 抛「API调用失败 (status)」。
- **返回**：`response.json()`；含大量 `logMessage_Info/Warning/Error`。写读 `authRequestGeneration`、`sessionUUID`、`refreshUserListInterval`。

### `callPythonAPI_raw(path, method="POST", data=null)` — 17068
- 直接对任意 `path` 发 REST（`X-Session-ID` if `sessionUUID`，`credentials:include`，GET 不带 body）。返回 json，失败抛 HTTP error。

### `executeServerJS(script, ...args)` — 17102
- `POST /execute_js`，body `{script,args}`，返回 `data.result`。

---

## 11. 主题背景（已使用背景上报）机制（17374–17949）

一组用于「用户看到的登录背景图上报给后端标记已消费」的复杂状态机。关键全局：`currentThemeConfig`、`currentThemeBackgroundTarget/ImageUrl`、`themeBackgroundLoginSyncInFlight`、`sessionBindEnsured{pc,mobile}`、`anonConsumedBackgroundByTarget`、`preLoginBackgroundSnapshot`、`themeBackgroundRequestCache(Set)`、`themeBackgroundAuthStateResolved/AuthenticatedSession`。

| 函数 | 行 | 说明 |
|---|---|---|
| `updateMultiGlobalButtons(startDisabled,stopDisabled)` | 17350 | 启停 `#multi-start-all-btn`/`#multi-stop-all-btn` |
| `safeResizeAndFitView()` | 17358 | `map.resize()` + `resetMapView()` + `setFitView(markers)` |
| `applyThemeGlobalEnvironmentVariables(themeConfig,options)` | 17374 | 写 `window.themeConfig`、`themeEnv_*`，调 `applyThemeLoginContainerStyle` + `scheduleThemeBackgroundConsumed` |
| `getCurrentThemeBackgroundTarget()` | 17428 | `isMobileMode?"mobile":"pc"` |
| `getThemeBackgroundImageUrlByTarget(target)` | 17432 | 从 env 提取 `auth_login_container_background`/`mobile_auth_login_content_background` 的图 URL |
| `getThemeBackgroundRequestCacheKey(...)` | 17445 | 去重键 `userScope|target|url` |
| `getRenderedThemeBackgroundImageUrlByTarget(target)` | 17451 | 读 `#auth-login-container`/`#mobile-content` 实际渲染背景 |
| `capturePreLoginBackgroundSnapshot(preferredTarget)` | 17474 | 登录前抓当前背景快照 |
| `getThemeBackgroundFeedbackMode(params)` | 17483 | 返回 `public`/`defer`/`session` |
| `scheduleThemeBackgroundConsumed()` | 17511 | 去抖 300ms 后调 `notifyThemeBackgroundConsumed` |
| `notifyThemeBackgroundConsumed(target,imageUrlOverride)` | 17565 | **session 模式**→`callPythonAPI("mark_theme_background_consumed",payload)`；**public 模式**→`POST /api/public/theme_background/consume`(`{target,image_url}`) |
| `extractThemeBackgroundImageUrl(bg)` | 17699 | 正则提取 `url(/theme-assets/...)` |
| `syncThemeBackgroundTarget()` | 17705 | = `scheduleThemeBackgroundConsumed`；绑定 `window.resize`（17709） |
| `shouldEnablePcThemeBackgroundContextMenu(params)` | 17714 | PC 且有图 URL |
| `buildThemeBackgroundDownloadFilename(imageUrl)` | 17723 | 生成 `pc-theme-background-<时间戳>.<ext>` |
| `hidePcThemeBackgroundContextMenu()` | 17734 | 隐藏右键菜单 |
| `triggerPcThemeBackgroundDownload(imageUrl)` | 17741 | 创建 `<a download>` 下载背景图 |
| `ensurePcThemeBackgroundContextMenuElement()` | 17759 | 创建 `#pc-theme-background-context-menu`（「保存背景图」按钮） |
| `setupPcThemeBackgroundContextMenu()` | 17807 | 给 `#auth-login-container` 绑 `contextmenu`；`click/blur/resize/scroll/keydown(Esc)` 关闭。**顶层立即调用**（17869） |
| `shouldSkipThemeBackgroundVisualRewrite(...)` | 17871 | 登录同步时避免重写相同背景 |
| `shouldSkipThemeBackgroundConsumeDuringLogin(...)` | 17883 | 登录同步期间跳过上报 |
| `applyThemeLoginContainerStyle(themeConfig,options)` | 17897 | 写 `#auth-login-container(_panel)`、`#mobile-content`、`#mobile-auth-login-container(-card)` 背景/阴影/边框 |

---

## 12. 主题风格与偏好（17951–18465）

| 函数 | 行 | 关键点 |
|---|---|---|
| `getThemeStyleConfig(styleId)` | 17951 | 从 `availableThemeStyles` 找配置，返回 `{basic_information,global_environment_variables}` |
| `syncThemeStyleSelectionState(styleId)` | 17977 | 缓存风格，高亮 `[data-theme-style]` 按钮边框 |
| `setThemeStyle(styleName,save=true,applyConfig=true)` | 17992 | 应用全局 env；`save`→`callPythonAPI("update_param","theme_style",...)` |
| `normalizeThemePreference/updateGlobalThemePreference/cacheThemePreference/getCachedThemePreference` | 18014– | **localStorage** key `theme_preference`（light/dark） |
| `syncThemeSelects(theme)` | 18043 | 同步 `#profile-theme-select`、`#mobile-unified-theme-select` |
| `updateGlobalThemeStyle/cacheThemeStyle/getCachedThemeStyle` | 18056– | **localStorage** key `theme_style` |
| `KNOWN_THEME_STYLE_IDS` / `normalizeThemeStyle` | 18081/18091 | 7 种内置风格 id |
| `renderThemeStyleButtons(container,current,options)` | 18109 | 渲染风格按钮网格（PC/移动），`onclick=setThemeStyle/setMobileUnifiedThemeStyle`，SVG 经 `sanitizeSVG` |
| `resolveThemeRequestSessionUUID/buildPublicThemeStylesUrl` | 18173/18185 | 构建 `/api/public/theme_styles?style_id=&background_target=&uuid=` |
| `shouldApplyThemeConfigImmediately(params)` | 18200 | 有 `/uuid=` 路由时需 `authStateResolved` |
| `ensureThemeStylesLoaded(force,options)` | 18219 | 已认证→`callPythonAPI("get_theme_styles",target)`；否则→`GET /api/public/theme_styles`，写 `availableThemeStyles` |
| `applyTheme(theme,options)` | 18268 | 切 `body.dark-mode`，缓存、同步控件 |
| `saveThemePreference(theme)` | 18293 | 未登录仅本地；否则 `POST /auth/user/update_theme`(`{theme}`) |
| `syncThemeFromServer(themeFromResponse,themeStyleFromResponse)` | 18325 | 未登录用本地；已登录读 `GET /auth/user/theme` + `callPythonAPI("get_params")`（取 theme_style），应用 |
| `resetBaseColorToDefault(prefix)` | 18397 | 默认色 `#7dd3fc`，写 `-picker`/输入框 |
| `setBaseColor(c,deep,save=true)` | 18415 | 写 CSS 变量 `--base-color/-600/-300`；`save`→`callPythonAPI("update_param","theme_base_color",c)` |
| `onColorPicked(val)` | 18426 | = `setBaseColor(val,val)` |
| `saveUnifiedThemeColor(value)` | 18441 | 统一面板保存主题色（依 `window.mobileAdminPanelMode`），写 `#mobile-unified-theme_base_color(-picker)` |

---

## 13. 认证状态与登录 UI 辅助（18467–18620）

| 函数 | 行 | 关键点 |
|---|---|---|
| `checkAuthStatus()` | 18467 | 调 `loadInitialData()`，`result.is_authenticated`→true |
| `showAuthLogin()` | 18482 | 显示 `#auth-login-container`，隐藏 loading/login/main-app，隐藏 `#exit-app-btn`，`checkGuestLoginEnabled()` |
| `checkGuestLoginEnabled()` | 18495 | `GET /auth/get_config`→控制 `#guest-login-section` |
| `switchAuthTab(tab)` | 18519 | 切 `#auth-tab-login/register` 与 `#auth-login-form/#auth-register-form`，隐藏 `#auth-error-msg/#auth-success-msg` |
| `showAuthError(message)` / `showAuthSuccess(message)` | 18549/18556 | 写 `#auth-error-msg`/`#auth-success-msg` |
| `setButtonLoading(buttonId,loading,originalText)` | 18563 | 按钮 loading 态（`dataset.originalText`，spin 图标） |
| `showButtonSuccess/showButtonError(buttonId,message,duration)` | 18582/18602 | 临时绿/红态后恢复 |

---

## 14. 图形验证码（18622–18980）

| 函数 | 行 | API / DOM |
|---|---|---|
| `captchaDimensions` | 18622 | 各表单默认宽高 343×119 |
| `loadCaptcha(formType)` | 18630 | `GET /api/captcha/get?width=`（`X-Session-ID`）→写 `captchaIds_<formType>`；据容器算宽度；渲染 iframe `/api/captcha/html/<id>?t=&width=` 到 `#..-captcha-display`。formType：login/register/mobile-login/mobile-register |
| `refreshCaptcha(formType)` | 18767 | = `loadCaptcha` |
| `loadCaptchaModal(requestedWidth)` | 18775 | `GET /api/captcha/get?width=`→`captchaIds_modal`，渲染 iframe 到 `#captcha-modal-display`、`#send_sms_code_captcha_container` |
| `refreshCaptchaModal()` | 18877 | 用 `captchaModalRequestedWidth` 重载 |
| `openCaptchaModal(context)` | 18883 | 打开 `#captcha-verification-modal`（z-index 20001），算 `#send_sms_code_modal_content_wrapper` 宽度，`loadCaptchaModal`，聚焦 `#captcha-modal-input`。`context={phone,button,originalText,scene}` 存 `pendingSMSContext` |
| `closeCaptchaModal()` | 18960 | 关闭并（若取消）恢复来源按钮 |

---

## 15. 短信验证码与登录/注册/2FA/游客（18982–20238）

### `confirmCaptchaAndSendSMS()` — 18982
- 读 `#captcha-modal-input`，据 `pendingSMSContext` 调 `sendSMSWithCaptcha(phone,captcha,button,originalText,scene)`，成功清上下文关闭，失败刷新验证码。按钮 `#captcha-modal-confirm-btn`。

### `sendSMSWithCaptcha(phone,captcha,button,originalText,scene)` — 19034
- **API**：`POST /api/sms/send_code`（`{phone,captcha,captcha_id:captchaIds_modal,scene?}`，`X-Session-ID`）。成功 `Swal`+60s 倒计时锁按钮；失败抛错。

### `handleAuthLogin(isMobile_use=false)` — 19128 ★
- **DOM**：`#auth-username/#auth-password/#auth-sms-code/#auth-login-captcha`；模式判定 `#auth-login-phone-btn`(font-semibold)、`#auth-sms-section`。
- **前端校验**：验证码/账号/密码≥6（admin 除外）/手机格式 `validateInput(...,"phone")`/短信 6 位；失败刷新验证码。
- **API**：`POST /auth/login`（body：`auth_username|auth_phone` + `auth_password|auth_sms_code` + `captcha` + `captcha_id`（移动用 `captchaIds_mobile_login`，PC 用 `captchaIds_login`）；`credentials:include`，`X-Session-ID`=authRequestSessionUUID）。写 `authLoginInProgress=true`、`authRequestGeneration+=1`。
- **成功处理**：
  - `requires_2fa`→显示 `#auth-2fa-form`，存 `window.temp2FAUsername`。
  - 设 `sessionUUID`/`authSessionUUID`；`themeBackgroundLoginSyncInFlight=true` + `syncThemeFromServer(result.theme,result.theme_style)`。
  - 多设备/清理提示；**账号注销等待期**（`result.account_cancellation.status==="pending"`）→`Swal` 二选一，继续则 `POST /auth/user/cancel_account_cancellation` 撤销注销。
  - 非游客：设 `currentUserData.group`、`currentAuthUsername`，1s 后隐藏登录容器，移动 `showMobileSessionPicker()` / PC `showSessionPicker()`。
  - 游客：进入 `#login-container` + `initializeInlineAdminPanel()` + 显示管理入口按钮。
- **失败**：手机号未注册（message 含「未注册/不存在/手机号未绑定」）+ phone 模式→`Swal` 提示跳转注册 `handlePhoneNotRegisteredRedirect`；否则普通 `Swal error` + 刷新验证码。
- `finally`：`themeBackgroundLoginSyncInFlight=false`、`authLoginInProgress=false`。

### `handlePhoneNotRegisteredRedirect(phoneNumber,smsCode,isMobile)` — 19629
- 切到注册 Tab（移动点 `#mobile-auth-tab-register` / PC `switchAuthTab("register")`），填充 `#..-reg-phone`/`#..-reg-sms-code`；调 `POST /api/sms/extend_code`(`{phone}`) 延长验证码有效期；`fireVerificationCodesModalSwal` 弹窗带剩余有效期倒计时（`didOpen/willClose` 管理 `setInterval`）；`refreshCaptcha`。

### `handle2FAVerify()` — 19780
- 校验 6 位码与 `window.temp2FAUsername`。**API**：`POST /auth/2fa/verify_login`(`{auth_username,code}`，`X-Session-ID`=`getAuthenticatedSessionHeaderValue()`，`credentials:include`)。成功设会话、`showSessionPicker`/`showMobileSessionPicker`；写 `authLoginInProgress`。

### `handleAuthRegister(isMobile_use=false)` — 19903 ★
- **DOM**：`#auth-reg-username/phone/sms-code/nickname/password/password-confirm/#auth-register-captcha`；头像 `registrationCroppedAvatarBlob`。
- **校验**：验证码/必填/用户名格式（`validateInput`，禁中文）/密码 `validateInput` + `checkWeakPassword`/两次一致/手机格式。
- **手机占用检查**：`callPythonAPI_raw("/api/auth/check_phone","POST",{phone})`，被绑定则 `jsShowConfirm` 强制解绑。
- **API**：`POST /auth/register`（`FormData`：auth_username/auth_password/phone/nickname/sms_code/captcha/captcha_id（移动/PC）/avatar?）。成功清表单、切登录 Tab 预填账号密码、`refreshCaptcha`、`Swal success`；失败刷新验证码。`finally` 清 `registrationCroppedAvatarBlob`。

### `handleGuestLogin()` — 20195
- `generateUUID()`→`POST /auth/guest_login`(`X-Session-ID`=新 UUID)。成功 `location.href="/uuid=<uuid>"`。

### `generateUUID()` — 20232
- 生成 v4 UUID 字符串。

---

## 16. window.load 事件绑定 + makeDraggable（20239–21087）

`window.addEventListener("load", ...)`（20240）内绑定大量事件，并定义 `makeDraggable`。

### 认证/表单事件
- `#auth-tab-login/register` click → `switchAuthTab`；`#auth-login-btn`→`handleAuthLogin`；`#auth-register-btn`→`handleAuthRegister`；`#auth-guest-btn`→`handleGuestLogin`；`#auth-2fa-verify-btn`→`handle2FAVerify`；`#auth-2fa-back-btn`→返回登录。
- Enter 键提交：`#auth-username/#auth-password`→login；`#auth-2fa-code`→2FA；`#auth-reg-password-confirm`→register；`#auth-login-captcha`/`#auth-register-captcha`→对应提交。
- 搜索框 Enter：`#admin-users-search-input_modal`/`#mobile-multi-admin-users-search-input`→`loadAdminUsers`；`#admin-billing-search-input`→`loadAdminBillingList`；`#admin-billing-logs-search-input_modal`→`loadAdminBillingLogs(1)`；`#mobile-multi-admin-billing-search-input`→`loadMobileMultiAdminBillingList`；`#mobile-billing-logs-search-input`→`loadMobileBillingLogs(1)`。
- `#profile-confirm-password` Enter→`updatePassword`；`#modify-phone-code` Enter→`confirmModifyPhone`。
- 管理入口：`#show-admin-panel`/`#show-admin-panel-login`/`#show-admin-panel-multi`→`toggleAdminPanel(true)`。

### `makeDraggable(elementId)` — 20402
- 通用可拖拽（优先 Pointer Events，回退 mouse/touch）：触摸长按 260ms 进入拖拽，鼠标立即拖拽；`clampAndSet` 边界约束；暴露 `el._hasMoved()`。用于 `#exit-app-btn`、`#newbie-help-btn`。

### 退出应用 `#exit-app-btn` — 20636
- 拖拽后阻止 click；`jsShowConfirm`→`callPythonAPI_raw("/api/shutdown","POST")`→`Swal`。

### 管理面板 Tab 绑定 `#admin-panel-modal` — 20680
- 绑定 `#admin-tab-<x>_modal` 全套：users/groups/logs/health/profile/sessions/messages/ipban/sms/config/captcha/reminders/ssl/cdn/bruteforce → `switchAdminTab("<x>")`。
- Tab 容器滚轮横向滚动；验证码历史 `#view-captcha-history-btn`/`#back-to-captcha-settings-btn` 切换 `#admin-captcha-panel_modal`↔`#admin-captcha-history-panel_modal`。
- 刷新按钮：`#admin-refresh-users/groups/logs/health/profile/sessions_modal` → `loadAdminUsers/Groups/Logs(1)/loadHealthStatus/loadPersonalInfo+loadUserBillingList/loadAdminSessions`。
- 日志分页：`#log-prev-page/#log-next-page/#log-limit-select_modal/#log-level-filter_modal/#log-keyword-filter_modal/#log-page-select` → `loadAdminLogs`。
- IP 封禁：`#ban-type`/`#ban-target`（`validateIPBanTarget`）。
- 会话入口 `#show-sessions-login/#show-admin-panel/#show-admin-panel-multi`→`toggleAdminPanel(true)`+`switchAdminTab("sessions")`；`#admin-refresh-sessions-inline`→`loadAdminSessions_inline`。
- 创建：`#admin-create-user_modal`→`showCreateUserModal`；`#admin-create-group_modal`→`showCreateGroupModal`；`#admin-view-school-accounts_modal`→`showSchoolAccountsModal`。
- 校园账号模态：`#school-accounts-close/ok/refresh`。
- 上帝模式：`#god-mode-checkbox`→`loadAdminSessions_inline`；`#god-mode-checkbox_modal`→`loadAdminSessions`。
- 健康自动刷新开关 `#health-auto-refresh-toggle`→`startHealthAutoRefresh/stopHealthAutoRefresh`。
- 多账号添加：`#multi-add-user-close/cancel/confirm`→`closeMultiAddUserModal/submitMultiAddUser`。
- 移动端多账号面板：`#mobile-multi-admin-create-user`→`openMobileCreateUserModal`；`#mobile-multi-admin-refresh-users`→`loadAdminUsers().then(copyAdminContentToMultiPanel("users"))`；`#mobile-multi-admin-refresh-groups`→`loadAdminGroups().then(copyAdminContentToMultiPanel("groups"))`；单账号版类似（`#mobile-admin-create-user-panel` 等）。

---

## 17. 管理面板权限与标签（21092–23213）

### `permissionTranslations` / `translatePermission(key)` — 21092/21171
- 权限键→中文映射表（含 view_tasks、god_mode、manage_users…）；未命中则用 `verbMap`/`nounMap` 词典拼接翻译。

### `checkAdminPermission(permissionName)` — 21293
- **API**：`POST /auth/check_permission`(`{permission}`，`X-Session-ID`)。返回 `success && has_permission`；异常默认 false。

### `toggleAdminPanel(show, skipAuthCheck=false)` — 21344 ★
- **权限并行检查**（`Promise.all`）：`manage_users / view_messages / manage_system / god_mode / checkAuthStatus / view_logs / view_captcha_history / manage_system×2`。
- **标签显隐**：users/groups/ipban/sms/ssl→`canManageUsers`；logs/reminders→`canViewLogs`；health 始终；config/cdn→`canManageSystem`；captcha→`canViewCaptchaHistory`；**bruteforce（密码恢复）用 `currentUserData.group ∈ {admin,super_admin}` 判定**（非权限）。
- **支付相关标签**：`GET /api/admin/pricing_config`（`X-Session-ID`，`credentials:include`）取 `require_payment`；`overdue/payment-settings/pricing/watermark-control`→仅 admin；`payment-logs`→`isAdmin || requirePayment`。
- `admin-billing`→`canManageBilling`；`restore-account`→`canRestoreAccount`；profile/sessions/messages 按游客态；`#god-mode-toggle_modal` 按 hasGodMode。
- 显示时默认 `switchAdminTab("sessions")`，`modal` 加 `flex`+`body.modal-visible`；隐藏时 `stopHealthAutoRefresh()`。

### `initializeInlineAdminPanel()` — 21812
- 若存在 `#admin-sessions-panel` 则 `loadAdminSessions_inline()`。

### 账号注销相关（21819–21957）
- 全局：`messageEditor`、`mobileMultiMessageEditor`、`mobileReminderEditor`、`accountCancellationCooldowns{pc,mobile}`。
- `formatCancellationTimeText(ts)` — 21824；`updateAccountCancellationStatusDisplay(status)` — 21831（写 `#pc-account-cancel-status`/`#mobile-account-cancel-status`）。
- `getAccountCancelElements(platform)` — 21842：返回 pc/mobile 的密码/短信输入、状态元素、短信按钮选择器。
- `sendAccountCancelSmsCode(platform="pc")` — 21864：`callPythonAPI_raw("/api/user/profile","GET")` 取手机→`openCaptchaModal({...,scene:"password_reset"})`，60s 冷却。
- `requestAccountCancellation(platform="pc")` — 21907：校验密码+短信 6 位→`jsShowConfirm`→`POST /auth/user/request_account_cancellation`(`{current_password,sms_code,wait_hours:24}`)。

### `switchAdminTab(tab)` — 21958 ★★（超长分发器）
- 获取全部 `#admin-tab-*_modal` 与 `#admin-*-panel_modal`，先清所有 tab 高亮 + 隐藏所有 panel + 隐藏验证码历史面板，再据 `tab` 显示对应 panel 并调加载函数：
  | tab | 加载函数 | 备注 |
  |---|---|---|
  | users | `loadAdminUsers()` | |
  | groups | `loadAdminGroups()` | |
  | logs | `loadAdminLogs(1)` | |
  | health | `loadHealthStatus()`+`startHealthAutoRefresh()` | 唯一开启自动刷新 |
  | profile | `loadPersonalInfo()`+`loadUserBillingList()` | |
  | sessions | `loadAdminSessions()` | |
  | messages | `checkIPBanAndProceed("messages_only")` 通过后 `loadMessages()` + 动态初始化 editor.md（`editormd("message-editor",{...}`，`imageUploadURL:"/upload"`），并把对话框迁移到 body（MutationObserver + 遮罩克隆）| IP 封禁拦截 |
  | ipban | `loadIPBans()` | |
  | sms | `loadSMSConfig()` | |
  | config | `loadSystemConfig()` | |
  | captcha | `loadCaptchaSettings(false)`（默认日期今日）| |
  | reminders | `loadReminders()` + 预加载 editor.md 资源（`/editor.md/css/editormd.css`、`/editor.md/editormd.js`）+ 一次性初始化 `reminder-editor`（`openReminderEditModal("-1")`→`closeReminderEditModal()`）| |
  | ssl | `loadSSLInfo()` | |
  | cdn | `loadCDNConfig()` | |
  | bruteforce | `loadBruteforceStatus()` | 密码恢复 |
  | overdue | `loadOverdueAccounts()` | 面板复用 `#admin-billing-panel_modal` |
  | payment-logs | `loadAdminPaymentLogs(1)` | |
  | payment-settings | （子标签自初始化） | |
  | pricing | `loadPricingConfig()` | |
  | watermark-control | `loadWatermarkControlConfig()`（调用两次）| |
  | admin-billing | `loadAdminBillingList()` | |
  | admin-billing-logs | `loadAdminBillingLogs(1)` | |
  | restore-account | `loadRemovedAccountsList()` | |
  | 其它(默认) | `loadPersonalInfo()` | |
- 除 health 外均 `stopHealthAutoRefresh()`。

---

## 18. 内联会话列表（23214–23400）

### `loadAdminSessions_inline()` — 23214
- **DOM**：`#admin-sessions-list-inline`；上帝模式 `#god-mode-checkbox`。
- **API**：上帝→`GET /auth/admin/all_sessions`；否则→`GET /auth/user/sessions`（`X-Session-ID`=`getAuthenticatedSessionHeaderValue()`）。
- 过滤有效会话，`updateAdminSessionCountDisplayInline`；渲染卡片（创建时间、登录状态、创建者、当前会话高亮）；按钮 `onclick`：`selectSession/deleteSession/destroySession`；游客提示注册。

### `updateAdminSessionCountDisplayInline(currentCount,maxSessions,isGodMode=false)` — 23374
- 写 `#admin-session-count-display-inline`（上帝：系统总数；游客：1/单会话；否则 x/max，接近/达上限变色）。

---

## 19. 日志查看（23405–23608）

### `loadAdminLogs(newPage=1)` — 23405
- 写 `currentLogPage`；**DOM**：`#admin-logs-content_modal/#log-limit-select_modal/#log-level-filter_modal/#log-keyword-filter_modal/#log-page-select/#log-page-total/#log-prev-page/#log-next-page`。
- **API**：`GET /logs/view?page=&limit=&keyword=`（`X-Session-ID`）。
- 客户端按级别过滤（`filterLogsByLevel`）+ 关键词高亮渲染（`renderHighlightedLogs`）；填充分页下拉与总行数、上下页禁用态。

### 辅助
- `escapeHtml(value)` — 23497（HTML 转义）。
- `normalizeMarkdownText(value)` — 23506。
- `highlightCustomKeyword(text,keyword)` — 23523（`|`/`&` 分词，正则高亮黄底）。
- `getLogLineClass(line)` — 23549（按 `LOG_HIGHLIGHT_RULES` 匹配返回 class）。
- `highlightLogLine(line,keyword)` — 23567；`renderHighlightedLogs(contentEl,logs,keyword)` — 23573。
- `filterLogsByLevel(logs,level)` — 23577；`escapeRegExp(value)` — 23593。

---

## 20. 健康状态检测与倒计时（23597–23794）

### `getHealthStatusPresentation(status)` — 23597
- ok→绿「运行正常」；degraded→黄「部分异常」；error/未知→红。

### `loadHealthStatus()` — 23613
- **DOM**：`#admin-health-content_modal`。**API**：`GET /health`（计算响应时间）。渲染服务器状态/响应时间/运行时长卡片 + summary（核心/非核心异常数）+ 组件详情（`componentNameMap`：running_core/payment_system/sms_system）+ JSON 原文 `<pre>`。

### 倒计时（23736–23794）
- 全局：`healthCountdownInterval`、`healthCountdownSeconds=5`。
- `startHealthAutoRefresh()` — 23739：需 `#health-auto-refresh-toggle` 勾选；每 1s 倒计时更新、每 5s `loadHealthStatus()`。
- `updateHealthCountdown()` — 23770：写 `#health-countdown-display`（「N秒后刷新」/「刷新中...」）。
- `stopHealthAutoRefresh()` — 23781：清两个定时器并清空显示。

---

## 21. 个人信息管理（23799–23977）

### `loadPersonalInfo()` — 23799 ★
- **API**：`GET /auth/user/details`（`X-Session-ID`）+ `callPythonAPI("get_params")`（取主题色/风格）。
- **DOM**：`#profile-nickname/#profile-auth-username/#profile-phone`（+`_showPhoneLocationNearInput` 归属地）、`.phone-input-wrapper`、`#profile-modify-phone-btn/#profile-phone-hint`（受 `window.APP_CONFIG.enable_phone_modification` 控制）、`#pc-forgot-password-hint`、`#profile-avatar-display/#profile-avatar-input`（头像带 `session_id` + 时间戳）、2FA 区（`#profile-2fa-enabled/#profile-2fa-actions/#profile-2fa-enabled-actions/#profile-2fa-setup`）、`#profile-theme-select`、`#profile-theme_base_color(-picker)`。
- 更新 `currentAuthUsername`、`updateAccountCancellationStatusDisplay`、`updateProfileAvailableRuns(user)`、`applyTheme`。

### `updateAvatar()` — 23979
- 读 `#profile-avatar-input`，`POST /auth/user/update_avatar`(`{avatar_url}`)，成功 `loadPersonalInfo()`。

### `loadAvatarWithAuth(avatarUrl,imgElement,retryCount=0)` — 24031
- 带 `X-Session-ID` fetch 头像 blob→`createObjectURL`，失败重试最多 2 次，最终回退默认 SVG。

---

## 22. 头像裁剪上传（24087–24431）

| 函数 | 行 | 说明 |
|---|---|---|
| `previewAvatar(event)` | 24087 | 个人资料头像：`FileReader`→`Cropper`（1:1）→`showModal("avatar-crop-modal")`，`isRegistrationCrop=false` |
| `previewAvatarForRegistration(event)` | 24132 | 注册头像，`isRegistrationCrop=true` |
| `closeCropModal()` | 24173 | 销毁 cropper，清 `#profile-avatar-file/#auth-reg-avatar/#mobile-reg-avatar`，`hideModal` |
| `revokeRegistrationAvatarPreview(previewImg)` | 24187 | 释放 objectURL |
| `setRegistrationAvatarPreview(previewId,file)` | 24198 | 设置预览（无 file→默认 `/static/images/default_avatar.png`） |
| `resetRegistrationAvatarPreviews()` | 24227 | 重置 `#auth-reg-avatar-preview`/`#mobile-reg-avatar-preview` |
| `confirmCropForRegistration()` | 24231 | `getCroppedCanvas(200×200)`→`toBlob`→写 `registrationCroppedAvatarBlob` + 预览 |
| `confirmCropAndUpload()` | 24275 | 注册态转上，否则裁剪后 `POST /auth/user/upload_avatar`(FormData avatar，`X-Session-ID`)→`loadPersonalInfo()` |
| `uploadAvatar()` | 24370 | 上传 `croppedAvatarFile` 或 `#profile-avatar-file`，`POST /auth/user/upload_avatar` |
| `updateBasicInfo()` | 24432 | 校验昵称非空→`PUT /api/admin/users/<currentAuthUsername>/basic_info`(`{nickname}`) |

---

## 23. 密码修改（短信验证模式）（24501–24886）

- 全局：`pcPasswordVerifyMode="password"`、`mobilePasswordVerifyMode="password"`。

### `toggleSmsVerifyMode(platform)` — 24517
- 切换 `#<p>-password-verify-section`↔`#<p>-sms-verify-section`，更新 `#<p>-sms-toggle-btn` 文案，清短信输入 `#<p>-password-sms-code`。

### `sendPasswordResetSmsCode(platform)` — 24586
- `callPythonAPI_raw("/api/user/profile","GET")` 取手机→无手机提示；有则 `openCaptchaModal({phone,button:#<p>-send-sms-btn,scene:"password_reset"})`。

### `resetPasswordVerifyMode(platform)` — 24652
- 重置 pc/mobile/all 的验证模式到密码验证默认态。

### `updatePassword()` — 24694 ★（PC 端）
- `jsShowConfirm`→读 `#profile-current-password/#profile-new-password/#profile-confirm-password`；`useSmsVerify = pcPasswordVerifyMode==="sms"`（读 `#pc-password-sms-code`）。
- 校验：短信 6 位 / 新密码非空 / 两次一致 / `checkWeakPassword` / 长度≥6 / `currentAuthUsername`。
- **API**：`POST /auth/admin/reset_password`（`{username,new_password, sms_code|old_password}`，`X-Session-ID`）。成功清输入 + `resetPasswordVerifyMode("pc")`。

---

## 24. 2FA 管理（24888–25264）

| 函数 | 行 | API |
|---|---|---|
| `generate2FA()` | 24888 | `POST /auth/2fa/generate`→写 `#profile-2fa-secret`，`QRCode.toCanvas(#profile-2fa-qr, qr_uri)` |
| `enable2FA()` | 24961 | `POST /auth/2fa/enable`(`{code}`)→`loadPersonalInfo()` |
| `disable2FA()` | 25017 | `jsShowConfirm`→`POST /auth/2fa/disable`→`loadPersonalInfo()` |
| `showMobileTest2FAModal()` | 25061 | 动态创建 `#mobile-test-2fa-modal`（底部抽屉），Promise 返回验证码；`window._mobileTest2FAResolver` |
| `closeMobileTest2FAModal(code)` | 25148 | 关闭并 resolve |
| `test2FA()` | 25167 | 移动用抽屉 / PC 动态弹窗取码→`POST /auth/2fa/verify`(`{code}`) |

---

## 25. 校园账号管理（25266–25893, 含 25267 创建用户）

### `showCreateUserModal()` — 25267（创建用户对话框）
- **DOM**：`#newUserModal`（`#newUsername/#newPassword/#newPasswordConfirm/#newUserPhone/#newUserNickname/#newUserSmsCode/#newUserSmsGroup/#newUserConfirm`）。
- 手机输入 oninput 控制 `#newUserSmsGroup` 显隐。
- `#newUserConfirm.onclick`：校验账号/密码≥6/手机格式；group 固定 `"user"`；**API**：`POST /auth/admin/create_user`（`{username,password,group,phone,nickname,sms_code}`，`X-Session-ID`）（`available_runs` 由后端默认）。成功 `closeNewUserModal()` + `loadAdminUsers()` + `copyAdminContentToMultiPanel("users")`。

### 权限组对话框
- 全局：`currentEditGroupKey`、`currentManageUsername`。
- `showCreateGroupModal()` — 25452：`GET /auth/admin/list_groups` 取首个组权限键，渲染 `#create-group-permissions` 复选框（`translatePermission`）；显示 `#create-group-modal`。
- `closeCreateGroupModal()` — 25895。
- `submitCreateGroup()` — 25903：读 `#new-group-key/#new-group-name` + 勾选权限→`POST /auth/admin/create_group`(`{group_name,display_name,permissions}`)→`loadAdminGroups()`。

### 校园账号
- `showSchoolAccountsModal()` — 25492 / `closeSchoolAccountsModal()` — 25500：`#school-accounts-modal` 显隐 + `loadSchoolAccounts()`。
- `loadSchoolAccounts()` — 25506：`GET /auth/admin/get_all_users_school_accounts`→渲染 `#school-accounts-content`（按认证用户分组，每账号显示密码/UA，含「添加/编辑/删除」按钮 `openSchoolAccountModal`/`deleteSchoolAccount`）。
- `openSchoolAccountModal(authUsername,schoolUsername,password,ua)` — 25660：填充 `#edit-school-account-*` 表单（编辑时锁定学校用户名），显示 `#edit-school-account-modal`。
- `closeEditSchoolAccountModal()` — 25715。
- `submitSchoolAccount()` — 25737：校验非空→`callPythonAPI_raw("/api/admin/school_account/save","POST",{auth_username,school_username,password,ua,original_username?})`→刷新列表（含 `#manage-school-accounts-modal` 的 `showUserSchoolAccounts`）。
- `deleteSchoolAccount(authUsername,schoolUsername)` — 25850：`jsShowConfirm`→`callPythonAPI_raw("/api/admin/school_account/delete","POST",{auth_username,school_username})`→`loadSchoolAccounts()`。

---

## 26. 管理员用户列表（25976–26326）

- 全局：`_adminUsersCacheData`（缓存 `{users,groups}`）、`_adminUsersSortField="created_at"`、`_adminUsersSortDir="desc"`。

### `_sortAdminUsersArray(users,field,dir)` — 25981
- 排序：`tfa`(2fa 启用) / `auth_username|nickname`(小写) / `max_sessions|available_runs`(-1 视为 Infinity) / 数值(created_at/last_login)。

### `_syncAdminUsersSortUI()` — 26010
- 同步 `#admin-users-sort-dir_modal`/`#mobile-admin-users-sort-dir`（↑/↓）与 `#admin-users-sort-field_modal`/`#mobile-admin-users-sort-field`。

### `resortAdminUsers()` — 26029 / `toggleAdminUsersSort()` — 26048
- 从当前焦点控件读排序字段 / 翻转方向，均调 `_rerenderAdminUsersList()`。

### `_rerenderAdminUsersList()` — 26053 ★
- 排序后渲染 `#admin-users-list_modal`：每用户卡片含头像占位 `#avatar-<user>`、昵称/手机（含归属地 badge）/创建时间/最后登录/登录IP+城市/会话限制/可用次数 `#available-runs-<user>`/2FA 状态、权限组下拉（`onchange=updateUserGroup`），及操作按钮组（`onclick`）：
  - `showUserSchoolAccounts` 账户密码、`showUserLogs` 查看日志、`setUserMaxSessions` 会话管理、`editAvailableRuns` 修改次数、`manageUserPermissions` 权限设置、`modifyUserNickname` 修改昵称、`modifyUserPhone` 修改手机、`resetUserPassword` 重置密码、`forceLogoutUser` 强制登出、`clearUserAvatar` 清除头像、`forceDisable2FA` 关闭2FA、`banUser`/`unbanUser` 封禁/解封、`deleteUser` 彻底删除。
- 渲染后异步填充 `.phone-location-badge`（`fetchPhoneInfo`），`copyAdminContentToMultiPanel("users")`，`loadUserAvatar(user.auth_username)`。

### 手机号归属地
- `_phoneInfoCache` 缓存；`fetchPhoneInfo(phone)` — 26168：`GET /api/phone_info?phone=`（`X-Session-ID`）→`{province,city,sp}`。
- `_phoneInfoBadge(info)` — 26186；`_showPhoneLocationNearInput(inputEl,phone)` — 26193（在输入框后插入 `.phone-location-tag`）。

### `loadAdminUsers(keywordOverride=null)` — 26210
- 读搜索框 `#admin-users-search-input_modal`/`#mobile-multi-admin-users-search-input`；**API**：`GET /auth/admin/list_users?keyword=`（`X-Session-ID`）+ `GET /auth/admin/list_groups`；缓存 `_adminUsersCacheData` 后 `_rerenderAdminUsersList()`。

### `updateUserGroup(username,newGroup)` — 26281
- `POST /auth/admin/update_user_group`(`{target_username,new_group}`)；失败 `Swal` 并回退（`loadAdminUsers()` + `copyAdminContentToMultiPanel/PanelVersion("users")`）。

> 本段结束于 `banUser(username)`（26331 起）——该函数属于下一文档 `22-JS-主应用B.md`（26329 起）覆盖范围。

---

## 27. API 端点汇总（本段出现）

**`callPythonAPI` 方法（POST /api/<method>）**：`update_param`、`on_user_selected`、`enter_multi_account_mode`、`get_theme_styles`、`get_params`、`mark_theme_background_consumed`。

**REST 端点**：
- 健康/网络：`GET /health`。
- 认证：`POST /auth/login`、`POST /auth/register`、`POST /auth/guest_login`、`POST /auth/2fa/verify_login`、`GET /auth/get_config`、`POST /auth/check_permission`、`POST /auth/user/cancel_account_cancellation`、`POST /auth/user/request_account_cancellation`。
- 会话：`GET /auth/user/sessions`、`GET /auth/admin/all_sessions`。
- 用户/管理：`GET /auth/user/details`、`POST /auth/user/update_avatar`、`POST /auth/user/upload_avatar`、`GET /auth/user/theme`、`POST /auth/user/update_theme`、`PUT /api/admin/users/<username>/basic_info`、`POST /auth/admin/reset_password`、`POST /auth/admin/create_user`、`POST /auth/admin/create_group`、`GET /auth/admin/list_users`、`GET /auth/admin/list_groups`、`POST /auth/admin/update_user_group`、`GET /auth/admin/get_all_users_school_accounts`。
- 2FA：`POST /auth/2fa/generate`、`POST /auth/2fa/enable`、`POST /auth/2fa/disable`、`POST /auth/2fa/verify`。
- 校园账号：`POST /api/admin/school_account/save`、`POST /api/admin/school_account/delete`。
- 短信/验证码：`POST /api/sms/send_code`、`POST /api/sms/extend_code`、`GET /api/captcha/get`、`GET /api/captcha/html/<id>`。
- 主题：`GET /api/public/theme_styles`、`POST /api/public/theme_background/consume`。
- 其它：`GET /api/user/profile`、`POST /api/auth/check_phone`、`GET /api/admin/pricing_config`、`GET /api/phone_info`、`POST /api/background_task/stop`、`POST /api/shutdown`、`POST /execute_js`、`GET /logs/view`、`POST /upload`（editor.md 图片上传）。

## 28. socket.io 说明

本段**无 socket 事件名**（无 `socket.on`/`socket.emit`）。仅在 `enterNetworkErrorState`/`exitNetworkErrorState` 中管理全局 `socket` 连接：读写 `socket.io.opts.reconnection`、调用 `socket.disconnect()`/`socket.connect()`、判断 `socket.connected`。真实事件名需在其它脚本块中查找。
