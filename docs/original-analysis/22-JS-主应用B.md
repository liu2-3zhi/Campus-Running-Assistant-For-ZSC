# 22 - JS 主应用 B（用户管理 / 会话 / 短信 / 地图 / 任务执行）

> 覆盖范围：`scripts/main.new.js` **第 26329 行 ~ 第 43148 行**
> 目标：为 Vue 重构版提供"逐函数复刻依据"。本文档对该区间内的**每一个函数、事件处理器、后端 API、DOM 操作、副作用**进行编目。
>
> 通用约定（本区间内几乎所有函数共享）：
> - `$(id)` == `document.getElementById(id)` 的简写工具函数。
> - `sessionUUID` / `authSessionUUID`：全局会话 UUID；请求头统一带 `X-Session-ID`。
> - `getAuthenticatedSessionHeaderValue()`：返回用于会话类接口鉴权的 session id（管理员/上帝模式相关接口使用）。
> - `callPythonAPI(method, ...args)`：调用后端 pywebview/JSON-RPC 风格接口；`callPythonAPI_raw(url, method, body)`：直接 REST 调用。
> - `jsShowConfirm(title, htmlMsg)`：异步确认框，返回 `Promise<boolean>`。
> - `Swal.fire({...})` / `swal.fire({...})`：SweetAlert2 弹窗（注意后半段代码大量使用小写 `swal`）。
> - `logMessage_Info/Warning/Error/Debug/Critical`：分级日志（详见文末日志模块）。
> - `escapeHtml(str)`：HTML 转义，防 XSS（定义于第 32196 行）。
> - 大量"成功后刷新"函数会调用 `loadAdminUsers()` 并链式同步移动端面板 `copyAdminContentToMultiPanel("users")` / `copyAdminContentToPanelVersion("users")`。

---

## 目录

1. 用户管理功能（封禁/解封/2FA/重置密码/删除/强制登出/头像/可用次数）
2. 学校账户管理（PC 端 + 移动端）
3. 用户权限管理与权限组
4. 管理员修改手机号 / 昵称
5. 权限组增删改（groups）与设备探测
6. 管理员会话列表（PC + 移动端长按删除）
7. 留言板（含 IP 封禁检查）
8. 用户日志查看（登录/操作，主 + 二级模态框）
9. IP 封禁管理与模态框验证
10. 短信服务配置 / 余额 / 历史 / 测试发送
11. 短信回复记录查看
12. 验证码管理（PC + 移动端，轮询回退）
13. 上帝模式：销毁会话 / 切换 / 删除会话
14. 会话选择器模态框（创建/选择/删除）
15. 会话有效性检查
16. 应用初始化 `initializeApp` 与 WebSocket
17. 多地图提供方运行时（高德/腾讯/天地图/百度）与坐标系转换
18. 单账号地图 / 控件 / 绘制
19. 登录/登出/用户切换/任务列表
20. 多账号模式（进入/退出/增删/导入导出/启停/自动刷新）
21. 移动端创建用户模态框
22. 仪表盘 / 路径绘制 / 后台任务轮询 / 历史轨迹
23. 日志批处理与拦截、参数输入、详情弹窗、通知与签到

---

## 1. 用户管理功能（26329–26982）

区段头注释：`// 用户管理功能函数`。

### `banUser(username)` — 26331
- 职责：封禁指定用户。参数 `username`，无返回值（`async`）。
- 交互：`jsShowConfirm("确认封禁", ...)` 二次确认。
- API：`POST /auth/admin/ban_user`，body `{ username }`，头 `X-Session-ID`。
- 成功：`Swal.fire(成功)`；`loadAdminUsers().then(...)` 后同步移动端多账号/单账号面板（`copyAdminContentToMultiPanel/PanelVersion("users")`）。
- 失败/异常：`Swal.fire(错误)`。

### `unbanUser(username)` — 26387
- 与 `banUser` 结构完全对称。API：`POST /auth/admin/unban_user`，body `{ username }`。成功后同样 `loadAdminUsers().then(...)` 双端同步。

### `forceDisable2FA(username)` — 26442
- 职责：强制关闭用户双因素认证。确认框"强制关闭2FA"。
- API：`POST /auth/admin/force_disable_2fa`，body `{ target_username: username }`。
- 成功：刷新用户列表 + 双端面板同步。

### `resetUserPassword(username)` — 26496
- 职责：重置用户密码（**动态创建**弹窗版本，区别于 §3 的 `showResetPasswordModal`）。
- DOM：`document.createElement` 生成 `.fixed inset-0` 模态框，内含 `#reset-password-input`、`#confirm-reset-password`。点击背景 `this.parentElement.remove()` 关闭。
- 校验：密码长度 ≥ 6，否则 `Swal.fire(错误)`。
- API：`POST /auth/admin/force_reset_password`，body `{ target_username, new_password }`。
- 副作用：以 Promise 收集输入的新密码。

### `deleteUser(username)` — 26576
- 确认框"确认删除"（不可恢复）。API：`POST /auth/admin/delete_user`，body `{ username }`。
- 成功：`loadAdminUsers().then(...)` 强制双端面板同步。

### `forceLogoutUser(username)` — 26636
- 区段头注释：`// 新增：强制登出用户前端逻辑`。
- 职责：强制销毁目标用户所有活跃会话。确认框含 `<strong>` HTML。
- API：`POST /auth/admin/force_logout_user`，body `{ username }`。
- 成功：`Swal.fire(成功)` + `loadAdminUsers()`（刷新列表）。异常：`console.error` + `Swal.fire`。

### `loadUserAvatar(username)` — 26681
- 职责：加载并渲染用户头像。
- API：`GET /auth/user/avatar?username=<enc>`，头 `X-Session-ID`。
- DOM：`querySelectorAll("[id='avatar-<username>']")`（同时匹配 PC/移动端同 id 容器）。有 `avatar_url` 时插入 `<img src=avatar_url?session_id=...>`（`onerror` 回退 👤 占位）；否则显示 👤。
- 失败：`logMessage_Error`。

### `clearUserAvatar(username)` — 26713
- 确认框"确认清除头像"。API：`POST /auth/admin/clear_user_avatar`，body `{ username }`。成功后 `loadUserAvatar(username)` 重载。

### `setUserMaxSessions(username, currentMax)` — 26757
- 职责：打开"设置最大会话数"模态框并预填。
- DOM：`#sessions-username`(textContent)、`#sessions-current-max`（-1→"无限制"）、`#new-max-sessions`(value，-1→0)。`showModal("set-max-sessions-modal")`。

### `submitSetMaxSessions()` — 26766
- 读取 `#sessions-username`、`#new-max-sessions`。校验为非负整数；`0` 映射为 `-1`（无限制）。
- API：`POST /auth/admin/update_max_sessions`，body `{ username, max_sessions }`。
- 成功：`Swal.fire` + `hideModal("set-max-sessions-modal")` + `loadAdminUsers()`。

### `editAvailableRuns(username, currentRuns)` — 26841
- 职责：弹 `Swal.fire`（`input:"number"`）编辑用户可用执行次数；`-1`=无限、`0`=无、正数=具体。
- `inputValidator` 校验整数且 ≥ -1。确认后调用 `updateAvailableRuns(username, parseInt(newRuns))`。

### `updateAvailableRuns(username, newRuns)` — 26918
- 显示"处理中"Loading（`allowOutsideClick:false`）。
- API：`POST /api/admin/update_available_runs`，body `{ username, available_runs: newRuns }`。
- 成功：`Swal.fire(更新成功)` + `loadAdminUsers()`。异常：`console.error` + `Swal.fire(网络错误)`。

---

## 2. 学校账户管理（PC 端 27009–27824 / 移动端 27854–28456）

### `showUserSchoolAccounts(username)` — 27009（PC 端）
- 职责：加载并渲染某认证用户名下所有"学校账号"。
- 输入验证（前端多层）：非空、字符串类型、长度 ≤ 200(`MAX_USERNAME_LENGTH`)、`USERNAME_PATTERN=/^[a-zA-Z0-9_\-.@]+$/`、`sessionUUID` 存在。
- 请求：`AbortController` + `setTimeout` 10 秒超时；`GET /auth/get_user_school_accounts_only?username=<enc>`，头 `X-Session-ID`，`signal`。
- HTTP 错误映射：401→会话过期、403→权限不足、404→用户不存在、≥500→服务器错误。JSON 解析失败/缺 `success` 字段亦分别提示。
- DOM：`#school-accounts-username`(textContent)、`#school-accounts-count`、`#school-accounts-list`(innerHTML)。
- 渲染每个账号卡片：兼容旧格式（字符串=密码）与新格式（`{password, ua}`）。按钮：
  - **编辑**：`data-account` 存 JSON（仅 `'`→`&apos;` 转义，保持 JSON.parse 可解析），`onclick` 内 `JSON.parse` 后调 `editSchoolAccount(...)`。
  - **删除**：`data-auth-username`/`data-school-username`（`escapeHtml`），调 `deleteSchoolAccount(...)`。
  - **查看详情**：调 `View_details_of_users_with_outstanding_payments(schoolUsername)`。
- 结尾 `showModal("manage-school-accounts-modal")`。异常按 NetworkError/AbortError/SyntaxError 分类提示。

### `closeManageSchoolAccountsModal()` — 27500
- `hideModal("manage-school-accounts-modal")`。

### `editSchoolAccount(authUsername, schoolUsername, password, ua)` — 27503
- 填充隐藏字段 `#edit-school-account-auth-username`/`-school-username`/`-password`/`-ua` 及展示元素 `#edit-auth-username`/`#edit-school-username`(textContent)、`#edit-school-password`/`#edit-school-ua`(value)。`showModal("edit-school-account-modal")`。

### `addNewSchoolAccount()` — 27550
- 从 `#school-accounts-username` 取当前认证用户名预填；清空学校用户名/密码/UA；`#edit-school-account-school-username.readOnly=false`；标题 `#edit-school-account-modal-title="新增学校账户"`；`showModal`。

### `generateRandomUAForSchoolAccount()` — 27602
- `callPythonAPI("generate_new_ua")`，将结果填入 `#edit-school-account-ua` 与 `#edit-school-ua`。成功/失败 `Swal.fire`。

### `closeEditSchoolAccountModal()` — 27656
- `hideModal("edit-school-account-modal")`；并兼容隐藏备用 `#edit-school-account-modal-simple`。

### `submitEditSchoolAccount()` — 27668
- 读取 `#edit-auth-username`/`#edit-school-username`(textContent)、`#edit-school-password`/`#edit-school-ua`(value.trim)。密码非空校验。
- API：`POST /api/admin/school_account/update`，body `{ auth_username, school_username, password, ua }`。
- 成功：`closeEditSchoolAccountModal()`；根据 `#mobile-user-school-accounts-modal` 是否可见，刷新移动端 `showMobileUserSchoolAccounts` 或 PC 端 `showUserSchoolAccounts`。

### `deleteSchoolAccount(authUsername, schoolUsername)` — 27753
- 确认框（含 `escapeHtml` 的 `<strong>`）。API：`POST /api/admin/school_account/delete`，body `{ auth_username, school_username }`。
- 成功：按移动端/ PC 端可见性刷新对应列表。

### 移动端学校账户管理（27854–28456）
- `closeMobileUserSchoolAccountsModal()` — 27854：操作 `#mobile-user-school-accounts-modal`，移除 `show` 类，300ms 后加 `hidden`（配合 CSS 过渡）。
- `mobileRefreshSchoolAccounts()` — 27907：从 `#mobile-school-accounts-username` 取用户名，调 `showMobileUserSchoolAccounts`。
- `mobileAddNewSchoolAccount()` — 27970：复用 `edit-school-account-modal`；`#edit-school-account-auth-username.readOnly=true` 预填当前用户；清空其它字段；标题设"新增学校账户"。
- `mobileEditSchoolAccount(authUsername, schoolUsername, password, ua)` — 28082：预填并将 auth/school 用户名设为只读；标题"编辑学校账户"。
- `showMobileUserSchoolAccounts(username)` — 28181：
  - API：`GET /auth/get_user_school_accounts_only?username=<enc>`，头 `X-Session-ID`。
  - DOM：`#mobile-school-accounts-username`、`#mobile-school-accounts-count`、`#mobile-school-accounts-list`。
  - 渲染移动端卡片（编辑=`mobileEditSchoolAccount`，删除=`deleteSchoolAccount`，详情=`View_details_of_users_with_outstanding_payments`）。`showModal("mobile-user-school-accounts-modal")`。

---

## 3. 用户权限管理（28458–28711）

### `manageUserPermissions(username)` — 28458
- 设 `currentManageUsername=username`（全局）。
- API：`POST /auth/admin/get_user_permissions`，body `{ username }`。
- DOM：`#manage-user-name`(textContent)、`#user-base-group`(组名，缺省 "guest")、`#manage-user-permissions-list`（渲染 checkbox 列表）。
- 渲染逻辑：对 `all_permissions` 每项，比对 `group_permissions`/`added_permissions`/`removed_permissions`，标注"(新增)"绿色 / "(移除)"红色。checkbox `data-permission`、`data-group-value`。文案经 `translatePermission(perm)` 翻译。
- 显示：`modal.classList.remove("hidden"); add("flex")`。

### `closeManageUserPermissionsModal()` — 28554
- 隐藏 `#manage-user-permissions-modal`；`currentManageUsername=null`。

### `submitManageUserPermissions()` — 28563
- 遍历 checkbox，比较 `checked` 与 `data-group-value`，得出 `addedPermissions`/`removedPermissions`。
- API：`POST /auth/admin/set_user_permission`，body `{ username, added_permissions, removed_permissions }`。
- 成功：关闭模态框 + `loadAdminUsers()`。

### `showResetPasswordModal(username)` — 28631
- 预填 `#reset-password-username`(textContent)、清空 `#reset-new-password`/`#reset-confirm-password`；`showModal("reset-user-password-modal")`。

### `submitResetUserPassword()` — 28638
- 校验：两字段非空、长度 ≥ 6、两次一致。
- API：`POST /auth/admin/reset_password`，body `{ username, new_password }`。
- 成功：`hideModal("reset-user-password-modal")`。

---

## 4. 管理员修改手机号 / 昵称（28713–28945）

### `modifyUserPhone(username, currentPhone)` — 28713
- 预填 `#admin-modify-phone-username`(value)、`#admin-modify-phone-current`(value，缺省"未绑定")、清空 `#admin-modify-phone-new`/`#admin-modify-phone-code`；`#admin-modify-phone-modal` 去 `hidden`。
- 调 `_showPhoneLocationNearInput(...)` 显示归属地；根据是否未绑定切换 `.phone-prefix` 显示与 `.prefix-hidden` 类。

### `closeAdminModifyPhoneModal()` — 28738
- `#admin-modify-phone-modal` 加 `hidden`。

### `sendAdminModifyPhoneCode()` — 28742
- 读取 `#admin-modify-phone-new`；校验 `/^1[3-9]\d{9}$/`。
- 调 `openCaptchaModal({ phone, button:#admin-modify-phone-send-btn, originalText:"发送验证码", scene:"modify" })`（图形验证码 + 短信发送流程）。

### `submitAdminModifyPhone()` — 28767
- 读取 username/newPhone/code；手机号格式校验。
- 预检查绑定：`callPythonAPI_raw("/api/auth/check_phone", "POST", { phone })`。若已绑定到他人 → 确认框（强制解绑）；已绑定到本人 → 提示并关闭。
- API：`POST /auth/admin/update_user_phone`，body `{ username, new_phone, sms_code }`。成功后关闭 + `loadAdminUsers()`。

### `modifyUserNickname(username, currentNickname)` — 28881
- 预填 `#admin-modify-nickname-username`/`-current`/`-new`；去 `hidden`。

### `closeAdminModifyNicknameModal()` — 28888 / `submitAdminModifyNickname()` — 28892
- 提交 API：`POST /auth/admin/update_user_nickname`，body `{ username, nickname }`。成功后关闭 + `loadAdminUsers()`。

---

## 5. 设备探测与权限组增删改（28947–29225）

### `Get_YiPAi_device()` — 28947
- 纯函数，基于 `navigator.userAgent` 返回 `"alipay"|"wechat"|"qq"|"mobile"|"pc"`。

### `deleteGroup(groupKey)` — 28977
- 确认框（不可恢复）。API：`POST /auth/admin/delete_group`，body `{ group_key }`。成功后 `loadAdminGroups()`。

### `editGroupPermissions(groupKey)` — 29021
- 设 `currentEditGroupKey`；`"super_admin"` 禁止编辑。
- API：`GET /auth/admin/list_groups`，头 `X-Session-ID`。取 `groups[groupKey]`。
- DOM：`#edit-group-name`(textContent = `name (key)`)、`#edit-group-permissions-list`（checkbox，`data-permission`，`translatePermission`）。显示模态框（`remove hidden`/`add flex`）。

### `closeEditGroupPermissionsModal()` — 29088
- 隐藏并 `currentEditGroupKey=null`。

### `submitEditGroupPermissions()` — 29097
- 收集 checkbox → `permissions{}`。API：`POST /auth/admin/update_group`，body `{ group_key, permissions }`。成功后关闭 + `loadAdminGroups()`。

### `loadAdminGroups()` — 29153
- API：`GET /auth/admin/list_groups`。
- DOM：错误写入 `#admin-groups-list`；正常渲染进 `#admin-groups-list_modal`。
- 系统预设组（`guest/user/admin/super_admin` 或 `group.system`）显示"系统预设"徽章，且不显示删除按钮。转义 `groupKey`（`&#39;`/`&quot;`/`&lt;`/`&gt;`）。每组内 grid 展示各权限 ✓/✗。按钮 onclick：`editGroupPermissions()` / `deleteGroup()`。

---

## 6. 管理员会话列表（29227–29710）

### `loadAdminSessions()` — 29227（PC 端模态框）
- 容器 `#admin-sessions-list_modal`（缺失则 `Swal.fire` 报错返回）。
- 上帝模式判定：`#god-mode-checkbox_modal.checked`。
  - 上帝模式：`GET /auth/admin/all_sessions`；否则 `GET /auth/user/sessions`。均带 `X-Session-ID: getAuthenticatedSessionHeaderValue()`。
- 过滤无效 `session_id`（null/空）。调 `updateAdminSessionCountDisplay(validCount, maxSessions|-1, isGodMode)`。
- 渲染：非上帝模式且非游客显示"创建新会话"按钮（`createNewSessionFromPicker()`）；游客显示提示。每条会话卡片：`selectSession()`/`deleteSession()`/`destroySession()` 按钮（上帝模式显示销毁）。全局变量：`currentUserIsGuest`、`sessionUUID`。

### `loadMobileAdminSessionsList()` — 29381（移动端）
- 容器：`#mobile-multi-admin-sessions-list` 或 `#mobile-admin-sessions-list-panel`（取未隐藏者）。
- 上帝模式复选框：`#mobile-multi-god-mode-checkbox` / `#mobile-god-mode-checkbox-panel`（需 `offsetParent!==null` 可见）。
- API 同上（`all_sessions` / `user/sessions`）。
- 计数显示 `#mobile-multi-admin-session-count-display` / `#mobile-admin-session-count-display-panel`；上帝模式隐藏创建按钮容器 `#mobile-multi-admin-create-session-container`。
- 每条卡片带 **长按删除交互**：`touchstart/touchmove/touchend/mousedown/mouseup/dblclick`。长按 500ms → 显示 `.press-overlay` + `navigator.vibrate(50)`；松手若 `isLongPress`：当前会话 `Swal.fire(操作受限)`，否则 `showMobileConfirm` 后 `destroySession(id,false)`（上帝）或 `deleteSession(id,false)`。双击（<350ms）/dblclick → `showMobileConfirm` 切换会话 `selectSessionFromPicker(id)`。

---

## 7. 留言板（29712–30124）

### `checkIPBanAndProceed(scope="all")` — 29713
- API：`POST /api/admin/check_ip_ban`，body `{ scope }`。返回 `result.is_banned === true`（布尔）。异常返回 `false`。

### `loadMessages()` — 29733
- 容器 `#admin-messages-list_modal`；游客字段 `#message-guest-fields` 显隐由 `currentUserIsGuest` 决定。
- 绑定 `#message-content` input → 更新 `#message-char-count`。
- API：`GET /api/messages/list`，头 `X-Session-ID`。
- 权限：`checkAdminPermission("delete_any_messages")` / `("delete_own_messages")`。
- 渲染每条留言（头像、昵称、游客徽章、IP 城市、邮箱、时间、删除按钮 `deleteMessage(id)`）。头像 URL 归一化到 `/api/avatar/...?session_id=`。
- Markdown 渲染：IIFE `renderMessagesMarkdown` 用 `editormd.markdownToHTML`（`htmlDecode:"style,iframe,image"`）；失败回退 `escapeHtml + <br>`。

### `postMessage()` — 29922
- **IP 封禁检查**：`checkIPBanAndProceed("messages_only")`，被禁则 `Swal.fire(访问被拒绝)` 返回。
- 读取 `messageEditor.getMarkdown()`（editor.md 实例）、`#message-nickname`、`#message-email`。游客必须填昵称与邮箱。
- API：`POST /api/messages/post`，body `{ content, nickname, email }`。
- 成功：清空编辑器/输入/字数，`Swal.fire(成功)` + `loadMessages()`。按钮 `#post-message-btn` disabled 切换。

### `deleteMessage(messageId)` — 30058
- 确认框。API：`POST /api/messages/delete`，body `{ message_id }`。
- 成功：`loadMessages()`；100ms 后同步移动端单账号面板（`#mobile-admin-panel-modal` 可见时 `copyAdminContentToPanelVersion("messages")`）。

---

## 8. 用户日志查看（30126–30436）

### `showUserLogs(username)` — 30127
- 去 `#user-logs-secondary-modal` 的 `hidden`；`#current-log-username-secondary` 设名；默认激活登录 Tab（`#log-tab-login-secondary` 高亮，`#log-audit-content-secondary` 隐藏）；`loadUserLoginLogsSecondary(username)`。

### `closeUserLogsSecondaryModal()` — 30149 / `switchUserLogTab(tab)` — 30153
- 切换 login/audit 两个 Tab 的高亮与内容显隐；分别调 `loadUserLoginLogsSecondary` / `loadUserAuditLogsSecondary`。

### `getLoginStatusBadge(log)` — 30178
- 纯函数：根据 `log.success`/`log.reason` 返回状态徽章 HTML（游客登录/登录成功/尝试过多/用户不存在/账号已封禁/密码错误/2FA验证失败）。

### `loadUserLoginLogsSecondary(username)` — 30208
- API：`GET /api/admin/logs/login_history?username=<enc>`。渲染进 `#log-login-content-secondary`（时间/IP/设备/位置 + `getLoginStatusBadge`）。

### `loadUserAuditLogsSecondary(username)` — 30265
- API：`GET /api/admin/logs/audit?username=<enc>`。渲染进 `#log-audit-content-secondary`（`.reverse()` 倒序；时间/操作类型/详情/IP）。

### `loadUserLoginLogs(username)` — 30318 / `loadUserAuditLogs(username)` — 30375
- 主模态框版本，容器分别为 `#log-login-content` / `#log-audit-content`。API 同上。

### `closeUserLogsModal()` — 30431
- 隐藏 `#admin-user-logs-modal`，显示 `#admin-users-panel_modal`。

---

## 9. IP 封禁管理（30438–30652）

### `loadIPBans()` — 30439
- API：`GET /api/admin/ip_bans`。渲染进 `#ip-ban-list`：每条封禁 `target`（`escapeHtml`）、`type`、`scope`（all→"全部" / 其它→"仅留言板"）、删除按钮 `removeIPBan(id)`。

### 全局 `ipRegex` — 30480 / `ipToInt(ip)` — 30483
- IPv4 校验正则；`ipToInt` 将点分 IP 转为 32 位无符号整数（用于范围比较）。

### `validateIPBanTarget()` — 30497
- 区段头注释：`// IP封禁模态框验证逻辑`。读取 `#ban-type`/`#ban-target`/`#ban-target-error`。
- 校验：目标非空；`type==="ip"` 用 `ipRegex`；`type==="range"` 拆分 `-`，两端均须合法且起始 ≤ 结束（用 `ipToInt` 比较）。
- 错误时：`#ban-target-error` 显示文案并去 `hidden`，`#ban-target` 加 `border-red-500`；成功隐藏错误、去红边，返回 `true`。

### `addIPBan()` — 30553
- 先 `validateIPBanTarget()`，不通过 `Swal.fire(添加失败)`。
- 读取 `#ban-target`/`#ban-type`/`#ban-scope`。API：`POST /api/admin/ip_bans`，body `{ target, type, scope }`。
- 成功：清空输入、隐藏错误、`loadIPBans()`。

### `removeIPBan(banId)` — 30614
- 确认框。API：`DELETE /api/admin/ip_bans/<banId>`，头 `X-Session-ID`。
- 成功：`loadIPBans()` + `mobileRefreshIPBanList()`（移动端同步）。

---

## 10. 短信服务配置（30654–31178）

### 签名工具（纯函数）
- `normalizeSmsSignature(signature)` — 30657：去首尾空白，剥离多层 `【】`，最终包裹为 `【x】`（空则返回 `""`）。
- `getSmsSignatureInnerValue(signature)` — 30675：返回去括号后的内层文本。
- `stripSmsSignatureFixedBrackets(value)` — 30684：移除所有 `【` `】`。
- `sanitizeSmsSignatureInputValue(input)` — 30688：清洗输入框值。
- `bindSmsSignatureInputSanitization(input)` — 30699：绑定 `input` 事件实时清洗（`dataset.smsSignatureSanitizationBound` 防重复绑定）。

### `loadSMSConfig()` — 30716
- `configLoadState.sms=false`；API：`GET /api/admin/sms/config`。
- 填充 DOM：`#sms-enabled`、`#sms-enable-phone-modification`、`#sms-enable-phone-login`、`#sms-enable-phone-registration-verify`（checkbox）；`#sms-username`、`#sms-apikey`、`#sms-signature`（内层值 + 绑定清洗）、`#sms-template`、`#sms-code-expire`、`#sms-limit-account`、`#sms-limit-ip`、`#sms-limit-phone`；`#sms-webhook-url` = `${origin}/sms-reply-webhook`。成功置 `configLoadState.sms=true`。

### `saveSMSConfig()` — 30762
- 前置 `ensureConfigLoaded("sms","短信服务")`。
- 收集 config（含 `normalizeSmsSignature(#sms-signature)`、各限流 parseInt 默认值）。
- API：`POST /api/admin/sms/config`，body=config。成功 `Swal.fire(配置已保存)`。

### `handleSmsMainSwitchChange()` — 30816
- 主开关 `#sms-enabled` 关闭时，联动关闭修改/登录/注册验证三个子开关。

### `checkSMSBalance()` — 30824
- 按钮 `#btn-check-sms-balance` loading。API：`GET /api/admin/sms/check_balance`。
- 成功填充 `#sms-balance-modal-value`/`-sent`/`-message`（含"频繁"/"失败"时切换琥珀色样式），`openSMSBalanceModal()`。

### `openSMSBalanceModal()` — 30883 / `closeSMSBalanceModal()` — 30887
- `showModal/hideModal("sms-balance-modal")`。

### 短信历史
- `openSMSHistoryModal()` — 30892：去 `#sms-history-modal` 的 `hidden` + `loadSMSHistory()`。
- `closeSMSHistoryModal()` — 30897。
- `loadSMSHistory()` — 30900：读取 `#sms-history-date-filter`/`#sms-history-phone-filter`，`GET /api/admin/sms/history?date=&phone=`。渲染进 `#sms-history-list`（手机号/用户名/时间/IP/内容/会话ID）；异步 `fetchPhoneInfo(phone)` 填充 `.phone-location-badge` 归属地。

### 短信测试发送
- `openSMSTestModal()` — 30989：去 `#sms-test-modal` 的 `hidden`，`body.modal-visible`；清空 `#sms-test-phone`/`#sms-test-code-input`；隐藏 `#sms-test-result`；恢复按钮 `#btn-send-test-sms`。
- `closeSMSTestModal()` — 31019。
- `sendTestSMS()` — 31026：读取 `#sms-test-phone`/`#sms-test-code-input`；校验手机号 `/^1[3-9]\d{9}$/`、自定义码 `/^\d{4,8}$/`。API：`POST /api/sms/test_send`，body `{ phone, code? }`。成功填 `#sms-test-code`/`#sms-test-phone-display`，显示 `#sms-test-result`，按钮态"已发送→5s 后再次发送"。

---

## 11. 短信回复记录查看（31180–31457）

### `openSMSReplyLogsModal()` — 31227
- 区段头注释：`// 短信回复记录查看功能`。
- 步骤：`Swal.fire(加载中...)` → API `GET /api/sms/reply-logs?limit=50`（头 `X-Session-ID`）。
- 分支：`response.status===403`→权限不足弹窗；`!result.success`→获取失败；`logs.length===0`→暂无记录。
- 正常：构建 HTML 表格（时间/手机号/回复内容(`escapeHtml`)/IP），`Swal.fire({ html, width:"800px", showCloseButton, customClass.container:"sms-reply-logs-modal" })`。异常 `console.error` + `Swal.fire(网络错误)`。

---

## 12. 验证码管理（31459–32194）

### 全局与倒计时（PC 端）
- `verificationCodesCountdownInterval`（31460）。
- `updateVerificationCodeCountdowns()` — 31462：遍历 `.verification-code-countdown`，用 `dataset.expiresAt` 计算剩余；<120s 变红，≤0 显示"已失效"。
- `startVerificationCodesCountdown()` — 31496 / `stopVerificationCodesCountdown()` — 31504：1s 定时器管理。

### 轮询回退机制
- 全局：`verificationCodesPollingTimer`、`VERIFICATION_CODES_POLLING_MS=30000`、`verificationCodesSocketHealthy`。
- `isVerificationCodesModalOpen()` — 31515 / `isMobileVerificationCodesModalOpen()` — 31520：判断模态框是否可见。
- `refreshOpenVerificationCodeModals()` — 31525：对已打开的 PC/移动端模态框分别 `loadVerificationCodes` / `loadMobileVerificationCodes`。
- `startVerificationCodesPollingFallback()` — 31534：Socket 不健康时每 30s 刷新。
- `stopVerificationCodesPollingFallback()` — 31543 / `syncVerificationCodesPollingByModalState()` — 31549：按模态框状态与 Socket 健康度启停轮询。

### PC 端模态框
- `openVerificationCodesModal()` — 31559：去 `#verification-codes-modal` 的 `hidden` + `loadVerificationCodes()` + 同步轮询。
- `closeVerificationCodesModal()` — 31564：加 `hidden`、停倒计时、同步轮询。
- `loadVerificationCodes()` — 31569：API `GET /api/admin/sms/verification_codes`。渲染进 `#verification-codes-list`（手机号 + 归属地 badge、验证码、剩余时间 `.verification-code-countdown`、失效按钮 `invalidateVerificationCode(phone)`）；`fetchPhoneInfo` 填归属地；`startVerificationCodesCountdown()`。
- `invalidateVerificationCode(phone)` — 31644：确认框。API `POST /api/admin/sms/invalidate_code`，body `{ phone }`。成功 `fireVerificationCodesModalSwal` + 重载。
- `fireVerificationCodesModalSwal(options)` — 31686：封装 `Swal.fire`，`didOpen` 内将 `.swal2-container` 与 popup 的 `z-index=2147483647`（确保覆盖模态框）。
- `addManualVerificationCode()` — 31711：读取 `#manual-code-phone`/`#manual-code-value`；空则自动生成 6 位；校验 `/^\d{6}$/`。API `POST /api/admin/sms/add_manual_code`，body `{ phone, code }`。

### 移动端模态框（31773–32194）
- 全局 `mobileVerificationCodesCountdownInterval`。`updateMobileVerificationCodeCountdowns()`(31782)/`start...`(31832)/`stop...`(31848)：类似 PC 端，作用于 `.mobile-verification-code-countdown`。
- `openMobileVerificationCodesModal()` — 31859：若 `#mobile-verification-codes-modal` 不存在则**动态 `createElement` 生成**（底部弹出样式，含手动添加区、刷新、列表容器 `#mobile-verification-codes-list`）；`onclick` 背景关闭；添加 `show` 去 `hidden`；`loadMobileVerificationCodes()` + 同步轮询。
- `closeMobileVerificationCodesModal()` — 31939：移除 `show` 加 `hidden`、停倒计时、同步轮询。
- `loadMobileVerificationCodes()` — 31958：API 同 PC；渲染进 `#mobile-verification-codes-list`；失效按钮 `invalidateMobileVerificationCode(phone)`。
- `invalidateMobileVerificationCode(phone)` — 32055：确认框 + `POST /api/admin/sms/invalidate_code`。
- `addMobileManualVerificationCode()` — 32113：读取 `#mobile-manual-code-phone`/`#mobile-manual-code-value`；`POST /api/admin/sms/add_manual_code`。

### 工具
- `escapeHtml(unsafe)` — 32196：转义 `& < > " '`。
- `checkButtonPermission(buttonId, permissionName)` — 32207：`checkAdminPermission(permissionName)`，无权限 `Swal.fire` 并返回 `false`。

---

## 13. 上帝模式：销毁 / 切换 / 删除会话（32224–32489）

### `updateAdminSessionCountDisplay(currentCount, maxSessions, isGodMode=false)` — 32224
- 更新 `#admin-session-count-display`：上帝模式=紫色"系统总会话数"；游客=蓝色"1/游客仅限单会话"；-1=绿色"无限制"；否则按 80% 阈值切色（红/琥珀/灰）。

### `destroySession(sessionId, confirm=true)` — 32254
- 区段头注释：`// 上帝模式：销毁会话`。`confirm` 为 true 时二次确认（截断 hash 16 位）。
- API：`POST /auth/admin/destroy_session`，body `{ session_id }`，头 `getAuthenticatedSessionHeaderValue()`。
- 成功：`Swal.fire` + `loadAdminSessions()` + `loadAdminSessions_inline()`。

### `selectSession(sessionId)` — 32302
- 确认框。**上帝模式分支**：`currentUserData.group==="super_admin"` 时，若无 `localStorage["admin_return_origin"]` 则存当前 `sessionUUID`，`Swal.fire` 800ms 后 `window.location.href="/uuid=<id>"` 直接跳转（不调 switch_session）。
- 普通：`Swal.fire(loading)` → `POST /auth/switch_session`（`credentials:"include"`，body `{ target_session_id }`）。成功跳转 `/uuid=<id>`；失败 `Swal.fire`，`result.need_login` 时跳登录页。

### `deleteSession(sessionId, confirm=true)` — 32412
- `confirm` 时确认框。`Swal.fire(正在删除...)`。API：`POST /auth/user/delete_session`，body `{ session_id }`。
- 成功：按 `#admin-panel-modal` 可见性刷新 `loadAdminSessions()` 或 `loadAdminSessions_inline()`；并 `loadMobileAdminSessionsList()`。
- 注：32424 行存在一处冗余/无效的 `title:(...)` 表达式（原始代码瑕疵，复刻时可忽略）。

---

## 14. 会话选择器模态框（32491–33071）

### `showSessionPicker()` — 32495 / `closeSessionPicker()` — 32506
- 操作 `#session-picker-modal`（`hidden`/`flex` 切换 + `body.modal-visible`）；打开时 `loadSessionPickerList()`。

### `loadSessionPickerList()` — 32515
- 容器 `#session-picker-list`。API：`GET /auth/user/sessions`，头 `getAuthenticatedSessionHeaderValue()`。
- 过滤无效会话；更新全局 `currentSessionInfo.maxSessions`/`.currentCount` 并 `updateSessionCountDisplay()`。
- 渲染每条：当前会话高亮、创建时间、登录状态徽章、"进入"(`selectSessionFromPicker`)/"删除"(`deleteSessionFromPicker`)。

### `refreshSessionPicker()` — 32648 / `updateSessionCountDisplay()` — 32652
- `updateSessionCountDisplay` 更新 `#session-count-display`（-1→无限制，否则按阈值切色）。

### `selectSessionFromPicker(sessionId)` — 32672
- 先 `closeSessionPicker()`。上帝模式（super_admin）：存 `admin_return_origin`，直接 `window.location.href="/uuid=<id>"`。
- 普通：`POST /auth/switch_session`（`credentials:"include"`，body `{ target_session_id }`）。成功跳转；失败 `Swal.fire`，`need_login` 跳登录。

### `createNewSessionFromPicker()` — 32744
- 先 `GET /auth/user/sessions` 刷新 `currentSessionInfo`，更新三处计数显示（`updateSessionCountDisplay`/`updateAdminSessionCountDisplay`/`updateAdminSessionCountDisplayInline`）。
- 若达上限（非 -1 且 count≥max）：`Swal.fire` 询问是否删最旧会话；确认后 `GET /auth/user/sessions` 取列表，排除当前会话、按 `created_at` 升序取最旧，`POST /auth/user/delete_session` 删除。
- `generateUUID()` 生成新 UUID，确认框后：移动端禁用 `#mobile-create-session-btn`，PC 端 `Swal.fire(loading)`。
- API：`POST /auth/user/create_session_persistence`，body `{ session_id: newUUID }`。成功更新 `sessionUUID`/`authSessionUUID`，关闭 picker，跳转 `/uuid=<newUUID>`。
- 注：32947 行 `text: 创建会话失败`（未加引号的标识符，原始代码 bug，复刻时应用字符串）。

### `deleteSessionFromPicker(sessionId, confirm=true)` — 32990
- `confirm` 时确认框；`Swal.fire(正在删除...)`。API：`POST /auth/user/delete_session`，body `{ session_id }`。
- 成功：按移动端/PC picker 可见性刷新对应列表（`loadMobileSessionPickerList`/`loadSessionPickerList`），并刷新移动端主面板 `loadMobileSessionsList()`。

---

## 15. 输入校验与会话有效性检查（33072–33255）

### `validateInput(input, type)` — 33072
- 纯函数，返回 `{valid, message?}`。`username`：3–50 字符且 `/^[a-zA-Z0-9_-]+$/`；`password`：≥6；`email`：`/^[^\s@]+@[^\s@]+\.[^\s@]+$/`。

### `checkSessionValidity()` — 33105（全局 `sessionValidityCheckInterval`）
- API：`POST /auth/check_uuid_type`，body `{ uuid: sessionUUID }`（**无** X-Session-ID 头）。
- `uuid_type==="unknown"`：停止定时器，动态创建全屏遮罩 `#logout-elsewhere-overlay`（渐变卡片、"会话已失效"、"返回登录"按钮跳 `/`）。防重复创建。

### `startSessionValidityCheck()` — 33229
- 每 5 分钟调 `checkSessionValidity`，防重复启动。

---

## 16. 应用初始化 `initializeApp`（33256–34431）与 WebSocket（34233–34403）

### `initializeApp()` — 33256（`async`，核心入口）
- 内部辅助：`ShowMobileLoadingOverlay`/`HiddenMobileLoadingOverlay`/`ShowLoadingOverlay`/`HiddenLoadingOverlay`；`isValidUUID`；`showMobileLoadingOverlay`/`hideMobileLoadingOverlay`/`hideLoadingOverlays`；`showUserFriendlyError`。
- 主题：`applyTheme(getCachedThemePreference())`、`setThemeStyle(cachedThemeStyle,...)`、`ensureThemeStylesLoaded()`；根据路径 UUID 决定是否延迟应用主题配置。
- URL 解析：`window.location.pathname.match(/\/uuid=(...)/)` 提取 `sessionUUID`。无效格式 → `Swal.fire` 跳登录。
- UUID 类型检查：`POST /auth/check_uuid_type` body `{ uuid }`。分支处理 `guest` / `system_account` / 未知（动态创建 `#logout-elsewhere-overlay` 带 10 秒倒计时自动跳转 `/`，并禁用登录/注册输入框）。
- 无 UUID：显示认证登录页（移动端 `#mobile-auth-login-container` / 桌面 `showAuthLogin()`）。
- 鉴权：`checkAuthStatus()`；置 `themeBackgroundAuthenticatedSession`。
- 已认证：`appInitialized=true`；`connectWebSocket()`；`loadInitialData()` + `syncMapProviderConfigFromInitialData()`；处理 `getInitialDataFailureNotice`；主题样式渲染（`renderThemeStyleButtons` 两处）；`syncThemeFromServer`。
- 全局赋值：`currentUserIsGuest`、`currentAuthUsername`；填充 `#user-combo`、`#multi-config-user-select`、`#mobile-multi-config-user-select`（`populateUserSelect`）；`createParamInputs($("params-container"),...)`；`onUserChange()`。
- 会话模式：`callPythonAPI("get_session_mode_info")`。分支：
  - **多账号模式恢复**：`enter_multi_account_mode`；显示 multi-app（移动端/桌面端）；初始化高德/供应商地图；`multi_get_all_config_users` 填选择器；`createParamInputs("multi-param")`；`renderMultiAccountList`；`initializeInlineAdminPanel`；`startMultiAccountAutoRefresh(500)`。
  - **单账号（hasSchoolLogin || hasLoadedTasks）**：设 `currentUserData`/`currentSessionUA`；`refreshUserListInterval=setInterval(refreshUserList,30000)`；`showMainApp()`；`updateDashboard()`；`refreshTasks()`；`checkBackgroundTaskOnLoad()`；`fetchNotifications()`；显示 `#show-admin-panel`。
  - **系统认证 / 游客（hasSystemAuth||isGuestMode）**：显示登录/会话管理页；`loadMobileSessionsList`（移动端）；`onUserChange`；游客模式显示 `#guest-warning-toast`/`#guest_warning_overlay`；显示管理面板按钮。
  - **其它**：`ensureActiveMapProviderRuntimeIfNeeded("ready 阶段")`。
- 收尾：主题、`refreshUserList()`、隐藏 `#loading-overlay`（淡出）、绑定签到参数事件（`#param-auto_attendance_enabled`/`_refresh_s`/`attendance_user_radius_m`）、`#confirm-amap-key-btn` 点击 → `onConfirmAmapKey`、`startSessionValidityCheck()`、移动端 `restoreMobileTaskState()`、`checkAdminReturnState()`。
- 异常：`Swal.fire(网络错误)` + `IS_OFFLINE=true`。

### DOMContentLoaded 引导 — 34405
- `document.readyState==="loading"` 时 `DOMContentLoaded` 调 `initializeApp()`；否则立即调用。失败置 `appInitialized=false`，`cdnErrorCount>0` 时显示 `#cdn-error-overlay`。

### `restoreMobileTaskState()` — 34180
- API：`GET /api/background_task/status`（`callPythonAPI_raw`）。若 running/paused：恢复 `selectedTaskIndex`、`selectTask`，设 `mobileTaskRunning`/`mobileTaskPaused`、`updateMobileTaskUI`、`startBackgroundTaskPolling()`。

### WebSocket
- 全局：`socket`、`wsHeartbeatTimer`。
- `startWsHeartbeat()` — 34236 / `stopWsHeartbeat()` — 34245：每 20s `socket.emit("heartbeat",{ts})`。
- `connectWebSocket()` — 34252：`io({ autoConnect:false, reconnection:true, reconnectionDelay:1000, ...Infinity, pingTimeout:60000, pingInterval:25000 })`；`socket.connect()`；`socket.emit("join",{session_id})`。
  - **监听事件**：`connect`（置 `verificationCodesSocketHealthy=true`、`startWsHeartbeat`、`refreshUserList`）；`disconnect`；`connect_error`；`heartbeat_ack`；`log_message`→`logMessage(...,"Backend")`；`multi_status_update`→`multi_updateAccountStatus`；`accounts_updated`→`onAccountsUpdated`；`multi_global_buttons_update`→`updateMultiGlobalButtons`（并禁用 `#exit-multi-mode-btn`）；`multi_position_update`→`multi_updateRunnerPosition`；`runner_position_update_new`→`updateRunnerPosition`（含任务切换 `renderTaskList`）；`task_completed`→`onTaskCompleted`；`run_stopped`→`onRunStopped`；`onNotificationsUpdated`→`onNotificationsUpdated`；`verification_codes_updated`→`refreshOpenVerificationCodeModals`。

---

## 17. 多地图提供方运行时（34433–35576）

支持 `amap`（高德）/`tencent`（腾讯）/`tianditu`（天地图）/`baidu`（百度）四家，通过 `window.APP_CONFIG` 配置。

- `enhanceMapInteraction(mapInstance)` — 34433：为地图容器绑定滚轮缩放、右键/中键拖拽平移、`contextmenu` 屏蔽；返回清理函数（移除所有监听器）。
- `getActiveMapProvider()` — 34549：返回当前供应商（校验白名单，默认 amap）。
- `getMapProviderDisplayName(provider)` — 34558：中文名映射。
- `getMapProviderConfig(provider)` — 34569 / `getMapProviderKeyRequirement(provider)` — 34576：返回各供应商 key 字段需求（申请 URL、字段名 `js_key/map_key/token/ak`、配置路径 `Map.providers.<p>.<field>` 及当前值）。
- `getActiveMapProviderApiKey()` — 34630。
- `syncMapProviderConfigFromInitialData(data)` — 34634：将后端返回的 `map_provider`/`map_providers`/`amap_key` 合并进 `window.APP_CONFIG`，刷新 `AMAP_API_KEY`。
- `showMissingMapProviderKeyModal(provider)` — 34671：填充并显示 `#amap-key-modal`（标题/描述/链接/字段标签/输入框 `#amap-key-input` 带 `dataset.provider`）。
- `ensureActiveMapProviderRuntimeIfNeeded(contextLabel)` — 34716：无 key 则弹配置框返回 false；非 amap 调 `loadActiveMapProviderRuntime`；amap 设 key 后 `loadAMapOnce()`。
- 脚本加载：`loadScriptOnce(...)` — 34740；`loadTencentMapOnce(key)` — 34761（`map.qq.com/api/gljs`）；`loadTianDiTuMapOnce(token)` — 34788（`api.tianditu.gov.cn`）；`loadBaiduMapOnce(ak)` — 34815（`api.map.baidu.com`，全局回调 `__onBaiduMapApiLoaded`）；`loadActiveMapProviderRuntime(provider)` — 34847。
- 实例/覆盖物管理：`destroyProviderMapInstance` — 34864；`getProviderOverlayBucket` — 34888；`clearProviderMapOverlays` — 34895；`removeProviderOverlayFromMap` — 34905；`getProviderMapDefaultZoom` — 34932。
- 天地图瓦片：`getTianDiTuToken` — 34936；`createTianDiTuTileLayer` — 34940；`applyTianDiTuDefaultMapType` — 34954。
- `initProviderMap(containerId, isMultiAccount)` — 34966：为非 amap 供应商创建地图实例并绑定 click 日志。失败调 `renderMapProviderFrontendPlaceholder`。
- 坐标系转换（纯函数，34068 起常量 + 函数）：`isCoordinateOutOfChina`、`transformMapCoordLat/Lng`、`wgs84ToGcj02`、`gcj02ToWgs84`、`gcj02ToBd09`、`bd09ToGcj02`；`convertMapCoordinatesToGcj02`/`convertGcj02ToProviderCoordinates`。
- 路线工具：`normalizeRouteCoord`、`isRouteSegmentSeparator`、`normalizeRouteCoords`、`splitRouteCoordsIntoDrawableSegments`。
- `getProviderMapInstance(containerId)` — 35261：amap 时返回 `map`/`multiAccountMap`/`mobileTrackMapInstance`；否则 `providerMapInstances[containerId]`。
- 视野/缩放/标记/路线：`fitProviderMapToCoordinates` — 35275；`zoomProviderMap` — 35301；`fitProviderMapToLastRoute` — 35327；`addProviderMarker` — 35345；`updateProviderRunnerMarker` — 35397；`drawProviderRouteOnMap` — 35425（四供应商各自 Polyline 实现）；`renderMapProviderFrontendPlaceholder` — 35144。
- Guards：`installGenericMapRuntimeGuards` — 35526；`installAmapRuntimeGuards` — 35530。
- `loadAMapOnce()` — 35536：`AMapLoader.load({ key, version:"2.0", plugins:["AMap.ControlBar","AMap.BuildingLayer","AMap.Walking"] })`，设 `AMapInstance`/`AMapReady`。

---

## 18. 单/多账号地图、控件、绘制（35577–36215）

- `ensureSingleMap()` — 35577：非 amap 调 `initProviderMap("map-container")`；amap 调 `initMap`。
- `forceProjectionRefresh()` — 35596（**在 39873/39903 重复定义两次**）：`map.resize()` + `setFitView`。
- `refreshMobileSettings()` — 35642 / `saveMobileSettings()` — 35720：移动端单账号设置面板参数刷新/保存，调 `callPythonAPI("get_params")` / `("update_param", key, value)`，容器 `#mobile-params-container`。
- 地图控件：`ensureSingleControls` — 35808 / `attachSingleControlHandlers` — 35833（`#zoom-in`/`#zoom-out`/`#reset-view-btn`）；`ensureMultiControls` — 35861 / `attachMultiControlHandlers` — 35888（`#multi-zoom-*`）。
- `removeAmapLicenseOverlay(containerId)` — 35917：`MutationObserver` 移除含"经识别"的授权浮层。
- `initMap(AMap)` — 35937：创建高德 3D 地图（pitch 55、center `[113.390342,22.527403]`），`ControlBar`、`BuildingLayer`；绑定 `mousedown/mousemove/mouseup/zoomchange/complete`；`enhanceMapInteraction`；`resolveMapReady`。
- `showMainApp()` — 36025：新建 `mapReadyPromise`；显示 `#main-app`（移动端 `#mobile-main-app`）；`destroySingleMap()`；100ms 后按供应商初始化地图。
- `resetUI()` — 36094：重置各标签、清空 `currentTasks`/`currentUserData`/`currentRunData`、`#task-list`/`#history-list`/`#target-points-text`、`stopBackgroundTaskPolling`、`updateDashboard`、`destroySingleMap`、`onUserChange`。
- `clearMapOverlays()` — 36154 / `destroySingleMap()` — 36174：清理高德覆盖物/实例与状态标志。

---

## 19. 登录/登出/用户切换/任务（36217–37178）

### 顶层事件绑定（36217–36314、36490、37180–37306）
- `#user-combo` change→`onUserChange`；`#username-entry` input→查用户密码/UA（`callPythonAPI("on_user_selected")`，`setBaseColor`）；`#random-ua-btn` click→`generate_new_ua` + `syncUAToMobile`。
- `#login-button` click→`checkButtonPermission("use_login_button")` 后 `onLogin`；`#logout-button`→`onLogout`；`#refresh-button`→`refreshTasks`；`#record-button`→`toggleRecordMode`；`#clear-button`→`clearCurrentPath(true)`；`#process-button`→`processCurrentPath`；`#start-run-button`→`toggleRun`；`#start-all-button`→`toggleAllRuns`；`#export-button`→`exportTask`；`#import-button`→权限校验后 `importTask`；`#show-user-details`→`showUserDetails`；`#show-task-details`→`showTaskDetails`；`#auto-gen-button`/`#cancel-gen-button`/`#confirm-gen-button`；`#show-notifications-btn`→`showNotifications`；`#mark-all-read-btn`→`markAllAsRead`；`#refresh-notifications-btn`→`refreshNotificationsUI(true,true)`；`#multi-download-template-btn`→`multi_downloadTemplate`。
- 移动端路径工具按钮（36269–36273）：`#mobile-record-button`/`#mobile-auto-gen-button`/`#mobile-process-button`/`#mobile-clear-button`/`#mobile-export-button`。
- 多账号按钮（37180–37210）：`#multi-account-btn`（权限校验后 `switchToMultiMode`）、`#exit-multi-mode-btn`、`#multi-start-all-btn`、`#multi-stop-all-btn`、`#multi-load-all-from-config-btn`、`#multi-add-from-config-btn`、`#multi-import-excel-btn`、`#multi-export-excel-btn`、`#multi-remove-all-btn`、`#multi-remove-selected-btn`、`#multi-refresh-all-btn`、`#multi-select-all-check`、`#multi-start-selected-btn`、`#multi-stop-selected-btn`、`#multi-refresh-selected-btn`。
- 管理面板 Tab（37212–37238）：`#admin-tab-users_modal`/`groups`/`logs`/`health`/`profile`/`sessions`/`messages`/`ipban`/`sms`_modal → `switchAdminTab(...)`。
- 日志 Tab（37240–37283）：`#log-tab-login`/`#log-tab-audit` 切换 + `loadUserLoginLogs`/`loadUserAuditLogs`。
- `#admin-refresh-messages_modal`→`loadMessages`；游客警告关闭 `#guest-warning-close-btn`/`#guest_warning_overlay`。

### 函数
- `onConfirmAmapKey()` — 36315：读取 `#amap-key-input`（`dataset.provider`）；`callPythonAPI("save_map_provider_key",{provider,api_key})`；成功后 `syncMapProviderConfigFromInitialData`、隐藏 `#amap-key-modal`、`ensureActiveMapProviderRuntimeIfNeeded`+`ensureSingleMap`。
- `bindImmediateRefreshForUserSelects()` — 36381：为 `#user-combo`/`#multi-config-user-select`/`#mobile-multi-config-user-select` 绑定 focus/click→`refreshUserList`（`_refreshBound` 防重复）。
- `multi_downloadTemplate()` — 36404：`callPythonAPI("multi_download_import_template")`；base64→Blob→下载。
- `refreshUserList()` — 36435：网络错误/无 sessionUUID 时跳过；`loadInitialData()` 后用 `updateSelect` 刷新三个下拉（保留选中值/滚动位置）。**顶层 `setInterval(refreshUserList,30000)`（36490）**。
- `onUserChange()` — 36492：`callPythonAPI("on_user_selected",username)`；填充密码/UA/参数/主题；若有 `sessionUUID`+`currentAuthUsername`，`GET /auth/get_user_school_accounts` 加载该用户学校账号密码/UA。
- `onLogin()` — 36578：读取 `#username-entry`/`#password-entry`；`callPythonAPI("login",user,pass)`。成功：`syncThemeFromServer`、地图加载、`showMainApp`、`currentUserData=result.userInfo`、更新姓名/学号标签、`updateDashboard`、`refreshTasks`、通知（缓存或 `fetchNotifications`）、显示管理按钮。失败 `swal.fire`。
- `onLogout()` — 36702：`callPythonAPI("logout")`；`resetUI`；清 `refreshUserListInterval`；500ms 后 `loadAdminSessions_inline`。
- `refreshTasks()` — 36717：`isRefreshingTasks` 防重入；`callPythonAPI("load_tasks")`（失败重试一次）；`currentTasks=...`；`renderTaskList`。
- `renderTaskList()` — 36750：渲染 `#task-list`（任务名、状态图标/文案：已完成/已过期/未开始/未完成、路径状态、选中高亮）；click→`selectTask(index)`；末尾 `renderMobileTaskList()`。
- `renderMobileTaskList()` — 36815：渲染 `#mobile-task-list`，`#mobile-task-count`；选中态内联样式；click 时先查后台运行状态（禁止运行中切换）。
- `renderMobileCheckpointsList()` — 36949：渲染 `#mobile-checkpoints-list`（打卡点序号/名称/坐标/到达状态徽章）。
- `forceLoadTaskDataForPolling(taskIndex)` — 37051：轮询时强制加载任务详情（`get_task_details`），更新 `currentRunData`、`updateDashboard`、`drawOnMap`、`loadHistory`。
- `selectTask(index, Update_Dashboard=true)` — 37075：运行中禁止切换；离线任务用本地数据，在线 `callPythonAPI("get_task_details",index)`；`updateDashboard`/`drawOnMap`/`loadHistory`；移动端切到地图面板。

---

## 20. 多账号模式（37307–39670）

- `switchToMultiMode()` — 37307：`enter_multi_account_mode`；显示 multi-app；初始化地图（高德/供应商）；填充配置用户选择器；`createParamInputs("multi-param")`；绑定"仅执行未完成"/"忽略任务时间"复选框 change 事件（`handleIncompleteCheckChange` 同步 `set_multi_run_only_incomplete`、`handleIgnoreTimeChange`）；`renderMultiAccountList`；`startMultiAccountAutoRefresh(500)`。
- `exitMultiMode()` — 37577：`stopMultiAccountAutoRefresh`；`exit_multi_account_mode`；隐藏 multi-app；销毁多账号地图/marker；`resetUI`；清 `refreshUserListInterval`；`loadAdminSessions_inline`。
- `multi_loadAllFromConfig()` — 37644：`callPythonAPI_raw("/api/multi_load_accounts_from_config","POST",{auth_username})`；用 `GET /auth/get_user_school_accounts` 补全密码/UA（含 `SECURITY_CONSTRAINTS` 长度校验、原型链污染防护）；`renderMultiAccountList`；缺密码走 `openMissingPasswordModal`。
- `openNewUserModal()` — 37742：重置 `#newUsername`/`#newPassword`/`#newUserPhone`/`#newUserNickname`/`#newUserSmsCode`/`#newPasswordConfirm`；手机号 input 时显隐 `#newUserSmsGroup`；`#newUserModal.style.display="flex"`。
- 缺失密码队列（全局 `missingAccountsQueue`/`missingCurrentIndex`）：`openMissingPasswordModal(missingList)` — 37766（补全/跳过/放弃三按钮，`#missing-password-modal`）；`showMissingCurrent()` — 37824；`closeMissingPasswordModal()` — 37835。

### 移动端创建用户模态框（37844–38070）
> 区段头注释：`// 新增：移动端创建用户模态框逻辑`。
- `openMobileCreateUserModal()` — 37847：重置 `#mobile-new-username`/`-password`/`-nickname`/`-phone`；隐藏 `#mobile-new-sms-group`、清 `#mobile-new-sms-code`；手机号 input 显隐验证码区；`#mobile-create-user-modal` 去 `hidden`，10ms 后加 `show`（滑出）。
- 全局 `mobileNewUserCodeCooldown`；`sendMobileNewUserCode()` — 37884：冷却检查；手机号校验；`openCaptchaModal({ phone, button:#mobile-new-send-code-btn, originalText:"发送", scene:"register" })`。
- `closeMobileCreateUserModal()` — 37918：移除 `show`，300ms 后加 `hidden`。
- `submitMobileCreateUser()` — 37928：读取 username/password/nickname/phone/smsCode；校验账号密码必填、密码 ≥6、手机号格式。按钮 `#mobile-new-user-confirm-btn` loading。
  - API：`POST /auth/admin/create_user`，body `{ username, password, group:"user", nickname, phone, sms_code }`（`available_runs` 由后端读配置默认值）。
  - 成功：`swal.fire` + `closeMobileCreateUserModal` + `loadAdminUsers` + 双端面板同步。

### 多账号添加/导入/导出/启停
- `closeNewUserModal()` — 38072；`#newUserClose`/`#newUserCancel` onclick 绑定。
- 全局 `multiAddModalSource`。`openMultiAddUserModal()` — 38081（`#multi-add-user-modal`；from-config 时密码可选）；`closeMultiAddUserModal()` — 38105；`openMultiAddUserModalForPassword(username, tag)` — 38128（用户名只读）。
- `#newUserSendCode` onclick — 38150：手机号校验 + `openCaptchaModal(scene:"register")`。
- `multi_addFromConfig()` — 38174：读 `#multi-config-user-select`；空则打开手动添加；否则 `GET /auth/get_user_school_accounts` 取密码/UA，`callPythonAPI("multi_add_account",user,password)`；缺密码走 `openMultiAddUserModalForPassword`。
- `submitMultiAddUser()` — 38245：读 `#multi-add-username`/`-password`/`-tag`；`SECURITY_CONSTRAINTS` 校验（用户名长度/`USERNAME_PATTERN`、密码 MIN/MAX、标签长度）；`callPythonAPI("multi_add_account",u,p,tag)`；成功 `renderMultiAccountList`，推进缺失密码队列。
- `multi_importFromExcel()` — 38413：动态 `input[type=file]`（.xlsx/.xls/.csv）；`FileReader` 读 base64；`callPythonAPI("multi_import_accounts",fileName,base64)`；渲染结果。
- `multi_exportToExcel()` — 38498：`callPythonAPI("multi_export_accounts_summary")`；base64→Blob 下载。
- `multi_startAll()` — 38529：读 `#multi-account-count`；`loadInitialData` 取已添加账号名 → `checkOverdueBeforeStart`（欠费检查）；读延迟/仅未完成参数；`callPythonAPI("multi_start_all_accounts",min,max,useDelay,runOnly)`；`error_code==="OVERDUE_PAYMENT"` 特殊处理。
- `multi_stopAll()` — 38629：`callPythonAPI("multi_stop_all_accounts")`。
- `onAccountsUpdated(accounts)` — 38633：`renderMultiAccountList`。
- `calculateStatusText(account, onlyIncomplete, ignoreTaskTime)` — 38641：纯函数，计算可执行任务数文案。
- `updateAllAccountsStatusText()` — 38704：基于 `cachedMultiAccounts` 与复选框状态重算并更新 PC/移动端每个账号 `.status-text`（含 `Have_Tasks` 用 summary 计算）。
- `renderMultiAccountList(accounts)` — 38819：设 `cachedMultiAccounts`；`renderToContainer("multi-account-list",false)` 与 `("mobile-multi-account-list",true)`。每项：勾选框、姓名/用户名/标签、状态徽章、summary 网格（总数/完成/未开始/可跑/过期）、签到网格（待签/已签/过期）、按钮（刷新/开始/停止/设置）、进度条。绑定按钮：start（含 `checkOverdueBeforeStart` + `multi_start_single_account`）/stop（`multi_stop_single_account`）/refresh（`multi_refresh_single_status`）/params（`openMobileAccountParams`/`openAccountParamsModal`）。末尾更新全选框状态。
- `multi_toggleSelectAll(event)` — 39003；`updateSelectAllCheckboxState()` — 39013；`#multi-account-list` change 委托（39032）。
- `multi_removeAll(confirm)` — 39038 / `multi_removeSelected(confirm)` — 39060：确认后 `multi_remove_all_accounts`/`multi_remove_selected_accounts`。
- `multi_getSelectedUsernames()` — 39102。
- `multi_startSelected()` — 39111：选中账号 + 欠费检查 + 逐个 `multi_start_single_account`（含随机延迟、欠费中断）。
- `multi_stopSelected()` — 39197 / `multi_refreshSelected()` — 39217 / `multi_refreshAll()` — 39242。
- 自动刷新（全局 `lastAccountListSignature`/`isMultiAccountAutoRefreshRunning`/`multiAccountAutoRefreshInterval`）：`startMultiAccountAutoRefresh(interval=500)` — 39249（`refreshLoop`：网络错误退避 5s、界面不可见降频 2s、`loadInitialData` 取账号、签名变化重绘、逐账号 `multi_updateAccountStatus`/`multi_updateRunnerPosition`、更新移动端全局统计面板 `#mobile-multi-running/paused/stopped-count`/`#mobile-multi-global-status`）；`stopMultiAccountAutoRefresh()` — 39424。
- 路径规划队列：`process_path_queue()` — 39433（仅高德，`getWalkingPath` + `multi_path_generation_callback`）；`triggerPathGenerationForPy(username, waypoints)` — 39460。
- `updateMobileSelectAllCheckboxState()` — 39466；`#mobile-multi-account-list` change 委托（39490）。
- `multi_updateAccountStatus(username, data)` — 39499：更新 `multi-acc-<u>` 与 `mobile-multi-acc-<u>` 的状态/名称/summary/进度；非运行状态移除 runner marker。
- `multi_updateRunnerPosition(username, lon, lat, name)` — 39619：非高德用 `updateProviderRunnerMarker`；高德维护 `multiAccountMarkers[username]`（用 `userColors[colorIndex++]` 着色）。
- `multi_removeRunnerMarker(username)` — 39649；`multi_resetMapView()` — 39662；`selectTaskFromBackend(index)` — 39672。

---

## 21. 仪表盘与路径绘制（39676–40485）

- `updateDashboard()` — 39676：更新 `#run-stats-block`/`#run-stats-label`、`#live-dist-label`/`#live-time-label`/`#total-dist-label`/`#total-time-label`/`#remaining-time-label`、`#target-points-text`（打卡点列表，含删除线/高亮当前）、`#current-location-label`；同步移动端 `#mobile-*` 对应标签；`renderMobileCheckpointsList()`。空数据时显示占位。
- `centerTargetList(sequence)` — 39839：滚动当前打卡点入视野。
- `resetMapView()` — 39854 / `forceProjectionRefresh()` — 39873 & 39903（重复定义）：`setFitView`。
- `drawOnMap_signature()` — 39934：非高德用 `drawProviderRouteOnMap` + `addProviderMarker`；高德绘制 recommended（绿）/draft（黑）/run（红虚线）Polyline + `drawMarkers` + `resetMapView`。
- `drawOnMap()` — 40024：调 `drawOnMap_signature`，100ms 后二次渲染修正位移。
- `drawMarkers()` — 40032：绘制打卡点 Marker（已过/当前/未到 不同色，当前带 `pulsing-marker`）。
- 路径绘制全局：`draftPath`/`draftPathLngLat`/`pendingPoints`/`isUpdating`/`lastMouseMoveTime`/`MOUSE_MOVE_THROTTLE_MS=70`/`MIN_DRAW_DISTANCE_M=12`。
  - `fastDistanceMeters(lon1,lat1,lon2,lat2)` — 40078：快速近似距离。
  - `scheduleUpdate()` — 40085：`requestAnimationFrame` 批量处理待绘点、更新 draft Polyline、`checkTargetReachedOnDraw`、`updateDrawingInfo`、`updateDashboard`。
  - `onMapMouseDown/Move/Up` — 40125/40138/40160：录制模式下采集鼠标轨迹点。
  - `checkTargetReachedOnDraw(currentLngLat, isForcedKeyPoint)` — 40171：判断是否到达当前打卡点，推进 `target_sequence`，全部到达则结束录制。
  - `updateDrawingInfo(lnglat)` — 40211：显示距离/预估时间文本 Marker。
- 全局 `pendingUnlockMap`。
- `toggleRecordMode()` — 40247：进入/退出录制。进入需先选任务；`clearCurrentPath(false,false)`；设 `target_sequence=1`；`map.setStatus({dragEnable:false})`。退出：路径 >50km 舍弃；到达最后打卡点则 `set_draft_path` + `processCurrentPath`，否则 `discardBlackDraftPolyline`。
- `clearCurrentPath(confirm=true, showAlert=true)` — 40323：检查草稿/运行坐标空 → 提示；查后台任务状态（运行中禁止）；确认框；`callPythonAPI("clear_current_task_draft")`；清除地图折线/marker、重置 `currentRunData`/`currentTasks[i]`、`updateDashboard`/`renderTaskList`/`drawMarkers`。
- `discardBlackDraftPolyline()` — 40441：清除草稿折线与状态，`set_draft_path([])`。
- `processCurrentPath()` — 40465：`set_draft_path(draftPath)` + `callPythonAPI("process_path")`；成功更新 `run_coords`/距离/时间，`drawOnMap`/`updateDashboard`/`renderTaskList`。

---

## 22. 任务执行控制与后台轮询（40486–41069）

- `toggleRun()` — 40486：单任务开始/停止。开始前 `_checkOverdueBeforeStartByCurrentMode()`（欠费）；`POST /api/background_task/start`，body `{ task_indices:[selectedTaskIndex], auto_generate, school_username }`；`error_code==="OVERDUE_PAYMENT"` 特殊提示；成功切按钮态 + `startBackgroundTaskPolling`。停止：`POST /api/background_task/stop`。
- `toggleAllRuns()` — 40572：执行所有可执行任务。过滤已过期/未开始/已完成任务；`POST /api/background_task/start`，body `{ task_indices, auto_generate, school_usernames?/school_username? }`。
- 后台轮询（全局 `backgroundTaskPollInterval`/`backgroundTaskStartTime`）：
  - `startBackgroundTaskPolling()` — 40666：`pollBackgroundTaskStatus` 立即 + 每 3s。
  - `stopBackgroundTaskPolling()` — 40674。
  - `pollBackgroundTaskStatus()` — 40681：`GET /api/background_task/status`；同步 run_coords/target_points、进度 `updateSingleProgress`、任务切换 `forceLoadTaskDataForPolling`、`runAccumulatedMs`、`updateRunnerPosition`；`status==="completed"`→提示 + 停止 + 复位按钮 + `refreshTasks`；`status==="error"`→报错。
  - `checkBackgroundTaskOnLoad()` — 40838：页面加载时恢复运行中任务状态（按钮态、地图数据、进度、runner 位置、`startBackgroundTaskPolling`），返回是否恢复。
- Runner Marker：`ensureRunnerMarker()` — 40983；`updateRunnerPosition(lon,lat,distance,targetSequence,duration,centerNow)` — 40996：更新位置标记、`#current-location-label`/移动端标签、`runAccumulatedMs`、`target_sequence`、单任务进度。
- `onTaskCompleted(taskIndex)` — 41070：标记 `currentTasks[i].status=1` + `renderTaskList`。
- `onRunStopped()` — 41076：停止轮询，复位 `#start-run-button`/`#start-all-button`。

---

## 23. 导入导出 / 路径规划 / 历史轨迹（41095–41505）

- `exportTask()` — 41095：`callPythonAPI("export_task_data")`；JSON→Blob 下载。
- `importTask()` — 41117：`input[type=file].json`；`callPythonAPI("import_task_data",text)`；成功进入离线模式 `IS_OFFLINE=true`，`showMainApp`，`renderTaskList`，`selectTask(0)`，`drawOnMap`。
- `getWalkingPath(waypoints)` — 41162：**仅高德**；用 `AMap.Walking` 逐段规划（重试/直线回退），返回合并路径点；含 `callPythonAPI("js_log",...)` 日志。
- `onConfirmAutoGenerate()` — 41258：读取 `#min-time-input`/`#max-time-input`/`#min-dist-input`；`callPythonAPI("auto_generate_path_with_provider",{min_t_m,max_t_m,min_d_m})`；成功更新 `run_coords`/距离/时间，绘图/刷新。
- `loadHistory(index)` — 41307：`callPythonAPI("get_task_history",index)`；渲染 `#history-list`（时间/距离/用时，click→`showHistoricalTrack(trid)`）；占位 `#history-placeholder`。
- `showHistoricalTrack(trid)` — 41327：运行中禁止查看；`callPythonAPI("get_historical_track",trid)`；移动端在 `#mobile-track-modal` 绘制（含摘要 `#mobile-track-distance`/`-duration`/`-pace`、起终点 marker、打卡点 marker），桌面端绘 `polylines.history`。非高德用 `drawProviderRouteOnMap`。
- `updateSingleProgress(pct, text, extra)` — 41491：更新 `#single-progress-fill`/`-text`/`-extra` 及移动端 `#mobile-single-progress-*`。

---

## 24. 日志系统（41506–41866）

- `getCallerInfo(linesToSkip)` — 41506：解析 `Error().stack` 提取调用者函数名与文件位置。
- `extractCleanSource(sourceString)` — 41556：去除 `(uuid=` 之后的部分。
- 日志批处理（全局 `logQueue`/`logFlushTimer`/`LOG_FLUSH_INTERVAL=2000`）：
  - `flushLogQueue()` — 41576：批量通过 `loadInitialData({ frontend_logs, force:true })` 发送。
  - `scheduleLogFlush()` — 41607：2s 后触发 flush。
  - `window.beforeunload`（41614）：尝试发送剩余日志。
- console 拦截 IIFE（41623）：覆盖 `console.log/info/warn/error/debug`，将消息入队上报（过滤前端日志/网络错误自身）；`console._original` 保留原始方法。
- `logMessage(msg, level="INFO", source=null)` — 41699：格式化 `[HH:MM:SS][前端日志][caller] msg`；按级别输出到原始 console；非 Backend 来源入队上报；核心关键字（`isCoreLog`：路径/任务/登录/签到等）时写入 UI 日志框 `#log-text`/`#multi-log-text`/`#mobile-log-text`。
- `logMessage_Debug/Info/Warning/Error/Critical(...)` — 41847–41866：分级封装。

---

## 25. 标签切换 / 自动登录 / 参数输入 / 详情 / 通知与签到（41867–43148）

- `showTab(tabName, element)` — 41867：切换 run-control/path-tools/history/params/log/checkpoints/attendance 标签；attendance 时 `refreshNotificationsUI`（含自动刷新定时器 `notificationAutoRefreshTimer`）。
- `autoLogin(user, pass)` — 41903：预填 `#user-combo`/`#username-entry`/`#password-entry`，`onUserChange().then(()=>#login-button.click())`。
- `createParamInputs(container, prefix, changeHandler, excludeGroups)` — 41921：按 `paramGroups`/`paramDefs` 生成参数输入（`theme_selector`/`color_picker`/`checkbox`/`number`）；`color_picker` 含"恢复默认"按钮（`resetBaseColorToDefault`）；绑定 input/change 事件（含 `setBaseColor`）。
- `updateParamInputs(container, prefix, params)` — 42032：按 `paramDefs` 回填输入值。
- `onParamChange(event)` — 42051：`pythonParams[key]=value` + `callPythonAPI("update_param",key,value)`；`ignore_task_time` 改变刷新任务；`auto_attendance_enabled` 弹提示。
- `onGlobalParamChange(event)` — 42067：多账号版；`ignore_task_time` 改变调 `updateAllAccountsStatusText`。
- `openAccountParamsModal(username)` — 42083：`multi_get_account_params`；`createParamInputs("acc-param",... ["主题与外观"])`；`#save-account-params-btn` onclick 逐项 `multi_update_account_param`；显示 `#account-params-modal`。
- `toggleUserDetails(show)` — 42111 / `toggleTaskDetails(show)` — 42136 / `toggleNotifications(show, forceDisableMap)` — 42247：切换模态框显隐并锁定/解锁地图交互。
- `showUserDetails()` — 42162：渲染 `#user-details-content`（姓名/学号/用户名/性别/学校/手机号/身份证/各登录时间 + UA `getCurrentSessionUAText`）。
- `showTaskDetails()` — 42200：渲染 `#task-details-content`（任务名/状态/ID/时间 + 打卡点列表）。
- `fetchNotifications(limit, offset)` — 42284：`callPythonAPI("get_notifications",params)`；更新 `window.currentNotifications` 与 `#notification-badge`；离线模式返回空。
- `refreshNotificationsUI(useCache, isManual, show_Modal)` — 42336（全局 `notificationAutoRefreshTimer`）：`isRefreshingNotifications` 防重入；先显示缓存 `get_cached_notifications`，再分批 `fetchNotifications` 增量渲染 `renderNotificationBatch`；自动刷新定时器按 `#param-auto_attendance_refresh_s` 设置。
- `renderNotificationBatch(notices, container)` — 42523：渲染通知项；签到任务按 `attendance_code`（-1 已过期/补签、1 已签到、0 待签到/签到）生成按钮（`handleAttendance`/`handleManualAttendance`/`handleMakeupAttendance`/`handleManualMakeupAttendance`）；`markAsRead` 设为已读。
- `showNotifications()` — 42624：离线提示或 `toggleNotifications(true)` + `refreshNotificationsUI`。
- `onNotificationsUpdated(result)` — 42639：更新徽章 + `#attendance-list`（签到任务）+ `syncMobileAttendanceList`。
- 签到处理（含全局 SVG 图标 `svgIconNormal`/`svgIconMakeup`，42778/42784）：
  - `handleAttendance(event, rollCallId, targetCoords)` — 42756：`trigger_attendance(id,coords,"random",null,false)`。
  - `handleManualAttendance(...)` — 42790：仅高德；地图选点（`map.on("click")`），距离校验后 `trigger_attendance(...,"specific",specificCoords,false)`。
  - `handleMakeupAttendance(...)` — 42928：补签 `trigger_attendance(...,"random",null,true)`。
  - `handleManualMakeupAttendance(...)` — 42948：手动选点补签（`...,"specific",...,true`）。
- `markAsRead(event, noticeId)` — 43087：`callPythonAPI("mark_notification_read",id)` + 刷新。
- `markAllAsRead()` — 43109：对未读通知批量 `mark_notification_read`（`Promise.all`）。
- 末尾（43137–43146）：**重复绑定** `#multi-remove-all-btn`/`#multi-remove-selected-btn`/`#multi-refresh-all-btn`/`#multi-select-all-check`/`#multi-start-selected-btn`/`#multi-stop-selected-btn`/`#multi-refresh-selected-btn`（与 37201 段重复）。
- 43148：`// --- Next Script Block ---` 区块分隔，本区间结束（后续为移动端 UI 交互函数）。

---

## 附录 A：后端 API 端点汇总

### 认证/用户管理（/auth/admin/*, /auth/*）
| 端点 | 方法 | 用途 |
|---|---|---|
| `/auth/admin/ban_user` | POST | 封禁用户 |
| `/auth/admin/unban_user` | POST | 解封用户 |
| `/auth/admin/force_disable_2fa` | POST | 强制关闭 2FA（`target_username`） |
| `/auth/admin/force_reset_password` | POST | 强制重置密码（`target_username,new_password`） |
| `/auth/admin/reset_password` | POST | 重置密码（`username,new_password`） |
| `/auth/admin/delete_user` | POST | 删除用户 |
| `/auth/admin/force_logout_user` | POST | 强制登出用户 |
| `/auth/admin/clear_user_avatar` | POST | 清除头像 |
| `/auth/admin/update_max_sessions` | POST | 设置最大会话数 |
| `/auth/admin/get_user_permissions` | POST | 获取用户权限 |
| `/auth/admin/set_user_permission` | POST | 设置用户权限（added/removed） |
| `/auth/admin/update_user_phone` | POST | 修改手机号（`new_phone,sms_code`） |
| `/auth/admin/update_user_nickname` | POST | 修改昵称 |
| `/auth/admin/list_groups` | GET | 权限组列表 |
| `/auth/admin/delete_group` | POST | 删除权限组 |
| `/auth/admin/update_group` | POST | 更新组权限 |
| `/auth/admin/create_user` | POST | 创建用户（移动端） |
| `/auth/admin/all_sessions` | GET | 全部会话（上帝模式） |
| `/auth/admin/destroy_session` | POST | 销毁会话 |
| `/auth/user/sessions` | GET | 当前用户会话列表 |
| `/auth/user/delete_session` | POST | 删除会话 |
| `/auth/user/create_session_persistence` | POST | 创建新会话 |
| `/auth/switch_session` | POST | 切换会话（`target_session_id`, credentials:include） |
| `/auth/check_uuid_type` | POST | 校验 UUID 类型（无 X-Session-ID） |
| `/auth/user/avatar?username=` | GET | 用户头像 |
| `/auth/get_user_school_accounts_only?username=` | GET | 学校账号（管理视图） |
| `/auth/get_user_school_accounts` | GET | 学校账号（当前用户） |

### 管理/短信/留言/IP（/api/admin/*, /api/*）
| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/admin/update_available_runs` | POST | 更新可用次数 |
| `/api/admin/school_account/update` | POST | 更新学校账号 |
| `/api/admin/school_account/delete` | POST | 删除学校账号 |
| `/api/admin/check_ip_ban` | POST | IP 封禁检查（scope） |
| `/api/admin/ip_bans` | GET/POST | IP 封禁列表/新增 |
| `/api/admin/ip_bans/<id>` | DELETE | 删除 IP 封禁 |
| `/api/admin/sms/config` | GET/POST | 短信配置读/写 |
| `/api/admin/sms/check_balance` | GET | 短信余额 |
| `/api/admin/sms/history?date=&phone=` | GET | 短信历史 |
| `/api/sms/test_send` | POST | 测试发送 |
| `/api/sms/reply-logs?limit=` | GET | 短信回复记录 |
| `/api/admin/sms/verification_codes` | GET | 验证码列表 |
| `/api/admin/sms/invalidate_code` | POST | 使验证码失效 |
| `/api/admin/sms/add_manual_code` | POST | 手动添加验证码 |
| `/api/messages/list` | GET | 留言列表 |
| `/api/messages/post` | POST | 发表留言 |
| `/api/messages/delete` | POST | 删除留言 |
| `/api/admin/logs/login_history?username=` | GET | 登录日志 |
| `/api/admin/logs/audit?username=` | GET | 操作日志 |
| `/api/auth/check_phone` | POST | 手机号绑定检查 |
| `/api/background_task/start` `/stop` `/status` | POST/GET | 后台任务控制/查询 |
| `/api/multi_load_accounts_from_config` | POST | 从配置加载账号 |

### Python 桥接（callPythonAPI 方法名，节选）
`generate_new_ua`、`get_session_mode_info`、`enter_multi_account_mode`、`exit_multi_account_mode`、`multi_get_all_config_users`、`multi_add_account`、`multi_remove_all_accounts`、`multi_remove_selected_accounts`、`multi_start_all_accounts`、`multi_stop_all_accounts`、`multi_start_single_account`、`multi_stop_single_account`、`multi_refresh_single_status`、`multi_refresh_all_statuses`、`multi_import_accounts`、`multi_export_accounts_summary`、`multi_download_import_template`、`multi_get_account_params`、`multi_update_account_param`、`multi_path_generation_callback`、`login`、`logout`、`on_user_selected`、`load_tasks`、`get_task_details`、`get_task_history`、`get_historical_track`、`export_task_data`、`import_task_data`、`set_draft_path`、`process_path`、`clear_current_task_draft`、`auto_generate_path_with_provider`、`get_params`、`update_param`、`save_map_provider_key`、`get_notifications`、`get_cached_notifications`、`mark_notification_read`、`trigger_attendance`、`js_log`。

---

## 附录 B：关键全局变量 / 状态

- 会话：`sessionUUID`、`authSessionUUID`、`currentSessionInfo{maxSessions,currentCount}`、`sessionValidityCheckInterval`。
- 用户：`currentUserData`、`currentUserIsGuest`、`currentAuthUsername`、`currentManageUsername`、`currentEditGroupKey`、`currentSessionUA`。
- 任务/运行：`currentTasks`、`selectedTaskIndex`、`currentRunData`、`runAccumulatedMs`、`singleProcessedPoints/singleTotalPoints`、`backgroundTaskPollInterval/backgroundTaskStartTime`、`isRefreshingTasks`、`IS_OFFLINE`。
- 地图：`map`、`multiAccountMap`、`AMapInstance`、`AMapReady`、`AMAP_API_KEY`、`amapLoadingPromise`、`providerMapInstances/...Overlays/...Providers`、`polylines{recommended,draft,run,history}`、`markers`、`runnerMarker`、`drawingInfoMarker`、`multiAccountMarkers`、`window.APP_CONFIG`。
- 绘制：`isDrawing`、`isPathDrawing`、`leftMouseDown`、`draftPath/draftPathLngLat/pendingPoints`、`draftTotalDist`。
- 多账号：`cachedMultiAccounts`、`lastAccountListSignature`、`isMultiAccountAutoRefreshRunning`、`multiAccountAutoRefreshInterval`、`path_planning_queue`、`is_planning_path`、`missingAccountsQueue/missingCurrentIndex`、`multiAddModalSource`。
- 验证码：`verificationCodesCountdownInterval`、`verificationCodesPollingTimer`、`verificationCodesSocketHealthy`、`mobileVerificationCodesCountdownInterval`、`VERIFICATION_CODES_POLLING_MS=30000`。
- WebSocket：`socket`、`wsHeartbeatTimer`。
- 通知：`window.currentNotifications`、`notificationAutoRefreshTimer`、`isRefreshingNotifications`。
- 日志：`logQueue`、`logFlushTimer`、`LOG_FLUSH_INTERVAL=2000`、`console._original`。
- 移动端创建用户：`mobileNewUserCodeCooldown`。
- localStorage：`admin_return_origin`（上帝模式返回点）。

---

## 附录 C：已知原始代码瑕疵（复刻时注意）

- 32424：`deleteSession` 内 `title:("正在删除会话..." , Swal.fire({...}))` 为无效逗号表达式，应仅保留 `Swal.fire`。
- 32947：`Swal.fire({ text: 创建会话失败 })` 引用了未定义标识符，应为字符串（如 `result.message`）。
- `forceProjectionRefresh` 定义三次（35596 / 39873 / 39903），`multi-*` 事件绑定重复（37201 与 43137）。
- 后半段大量使用小写 `swal.fire`（依赖 `window.swal` 别名），前半段用 `Swal.fire`。
- 30733/30774：短信签名读写通过 `getSmsSignatureInnerValue`/`normalizeSmsSignature` 处理内外层 `【】`。
