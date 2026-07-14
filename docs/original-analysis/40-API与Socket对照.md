# API 端点 & Socket 事件对照（Original vs Vue）

> 生成时间：2026-07-14。用于量化 Vue 版相对 original 的功能缺口。以子代理详细文档为准，本表为快速索引。

## 1. Socket.IO 事件 — ✅ 已完全复刻

original 与 Vue 版 `socket.on` 事件完全一致（14 个）：
`connect` / `disconnect` / `connect_error` / `heartbeat_ack` / `log_message` / `multi_status_update` / `accounts_updated` / `multi_global_buttons_update` / `runner_position_update_new` / `multi_position_update` / `task_completed` / `run_stopped` / `onNotificationsUpdated` / `verification_codes_updated`

emit：`heartbeat` / `join`。均已在 `frontend/src/services/socket.js` 复刻。

## 2. Vue 版已调用的 API（callAPI 方法名）

add_account, admin_ssl_status, admin_ssl_toggle, auto_generate_path_with_provider, check_overdue, clear_current_task_draft, create_message, delete_message, enter_multi_account_mode, export_accounts_excel, export_task_data, get_accounts_template, get_initial_data, get_messages, get_multi_accounts, get_notifications, get_params, get_task_details, get_task_history, get_theme_config, get_theme_styles, import_accounts_excel, load_tasks, login, logout, mark_notification_read, on_user_selected, process_path, refresh_account, refresh_accounts, refresh_all_accounts, remove_account, remove_accounts, remove_all_accounts, set_global_params, set_multi_run_only_incomplete, start_all_accounts, start_all_runs, start_selected_accounts, start_single_account, stop_all_accounts, stop_selected_accounts, stop_single_account, update_param

Vue 版已用的 REST：`/auth/*`（register/login/guest_login/switch_session/check_uuid_type/get_config/2fa verify_login/admin 用户组管理/user details+theme+avatar+sessions）、`/api/admin/{cdn,config,ip_bans,pricing_config,sms/config}`、`/api/background_task/*`、`/api/sms/{send_code,test_send}`、`/api/captcha/get`、`/api/multi_load_accounts_from_config`、`/health`。

## 3. Original 独有 / Vue 版疑似缺失的 API（重点补齐对象）

### 账单 Billing
- `/api/admin/billing/add`、`/delete`、`/logs`、`/update`
- `/api/billing/list`

### 欠费 Overdue
- `/api/admin/overdue`、`/api/admin/clear_overdue`、`/api/check_overdue`（Vue 有 check_overdue）

### 密码恢复（暴力破解）Bruteforce
- `/api/admin/bruteforce/start`、`/status`、`/stop`

### 支付 Payment（彩虹易支付）
- `/api/payment/create`、`/query`、`/refund`、`/methods_config`、`/verify_host`、`/query_billing_active`、`/query_billing_local`
- `/api/admin/payment/config`、`/fetch_orders`、`/local_orders`、`/log_detail`、`/order_detail`、`/query_order`
- `/api/admin/payment_methods/`、`/api/admin/yipay_config`
- `/api/admin/generate_product_name`

### 验证码 Captcha
- `/api/captcha/config`、`/detail/`、`/history`、`/save_settings`、`/test_generate`（Vue 仅有 /get）

### 短信 SMS（扩展）
- `/api/admin/sms/add_manual_code`、`/check_balance`、`/invalidate_code`、`/verification_codes`
- `/api/sms/extend_code`、`/api/sms/reply`

### 定时提醒 Reminders
- `/api/reminders/check`、`/delete`、`/list`、`/update`

### SSL
- `/api/admin/ssl/config`、`/info`、`/upload`（Vue 有 admin_ssl_status/toggle + admin_ssl_upload）

### 恢复账号 / 校园账号
- `/api/admin/removed_accounts`、`/api/admin/restore_account`
- `/api/admin/school_account/delete`、`/update`、`/api/admin/get_all_users_school_accounts`
- `/api/school_account/stats`、`/auth/get_user_school_accounts`

### 用户/资料/2FA
- `/auth/2fa/enable`、`/disable`、`/generate`、`/verify`（Vue 仅 verify_login）
- `/api/user/profile`、`/api/user/update_phone`、`/auth/modify_phone`、`/auth/send_modify_phone_code`、`/api/phone_info`
- `/auth/user/request_account_cancellation`、`/auth/user/theme`、`/auth/user/update_avatar`
- `/auth/admin/{all_sessions,ban_user,unban_user,clear_user_avatar,force_disable_2fa,force_logout_user,get_user_permissions,set_user_permission,update_max_sessions,update_user_group,update_user_nickname,update_user_phone,update_available_runs}`
- `/api/admin/check_ip_ban`、`/api/admin/update_available_runs`

### 配置/展示/其他
- `/api/config/pricing`、`/profile_display`、`/registration_display`
- `/api/amap/watermark_control/config`（高德水印）
- `/api/public/theme_background/consume`（随机背景）
- `/api/history/`、`/execute_js`

> ⚠️ 注意：以上"缺失"是基于 URL 字符串静态匹配的初判；部分功能 Vue 版可能以不同封装存在。最终以各子代理详细文档 + 后续逐项核验为准。
