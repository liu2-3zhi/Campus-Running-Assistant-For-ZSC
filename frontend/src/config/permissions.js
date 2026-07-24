export const permissionTranslations = {
  manage_users: '管理用户',
  manage_groups: '管理权限组',
  view_logs: '查看日志',
  manage_sessions: '管理会话',
  view_health: '查看系统状态',
  manage_config: '系统配置',
  manage_ip_bans: 'IP封禁管理',
  manage_sms: '短信配置',
  manage_captcha: '验证码管理',
  manage_reminders: '定时提醒',
  manage_ssl: 'HTTPS管理',
  manage_cdn: 'CDN管理',
  manage_bruteforce: '暴力破解防护',
  manage_payments: '支付管理',
  manage_pricing: '定价管理',
  manage_watermark: '水印管理',
  manage_billing: '账单管理',
  restore_accounts: '恢复账号',
  god_mode: '上帝模式',
  manage_messages: '留言板管理',
}

export const adminTabs = [
  { key: 'users', label: '用户管理', permission: 'manage_users' },
  { key: 'groups', label: '权限组', permission: 'manage_groups' },
  { key: 'logs', label: '日志查看', permission: 'view_logs' },
  { key: 'sessions', label: '会话管理', permission: 'manage_sessions' },
  { key: 'health', label: '系统状态', permission: 'view_health' },
  { key: 'profile', label: '个人信息', permission: null },
  { key: 'messages', label: '留言板', permission: 'manage_messages' },
  { key: 'ipban', label: 'IP封禁', permission: 'manage_ip_bans' },
  { key: 'sms', label: '短信配置', permission: 'manage_sms' },
  { key: 'config', label: '系统配置', permission: 'manage_config' },
  { key: 'captcha', label: '验证码', permission: 'manage_captcha' },
  { key: 'reminders', label: '定时提醒', permission: 'manage_reminders' },
  { key: 'ssl', label: 'HTTPS', permission: 'manage_ssl' },
  { key: 'cdn', label: 'CDN', permission: 'manage_cdn' },
  { key: 'bruteforce', label: '暴力破解', permission: 'manage_bruteforce' },
  { key: 'payment-logs', label: '支付日志', permission: 'manage_payments' },
  { key: 'payment-settings', label: '支付设置', permission: 'manage_payments' },
  { key: 'pricing', label: '定价管理', permission: 'manage_pricing' },
  { key: 'watermark', label: '水印管理', permission: 'manage_watermark' },
  { key: 'billing', label: '账单管理', permission: 'manage_billing' },
  { key: 'billing-logs', label: '账单日志', permission: 'manage_billing' },
  { key: 'restore-account', label: '恢复账号', permission: 'restore_accounts' },
]

export function hasPermission(permissions, perm) {
  if (!perm) return true
  if (permissions?.is_admin) return true
  return !!permissions?.[perm]
}
