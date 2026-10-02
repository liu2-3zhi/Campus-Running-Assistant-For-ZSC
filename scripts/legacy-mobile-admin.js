// Legacy mobile admin panel initialization extracted from main.js.
async function initMobileAdminPanel(prefix) {
  // 获取当前用户的组别信息，用于权限判断
  // 如果currentUserData未定义或缺少group属性，默认为"user"
  const userGroup = currentUserData?.group || "user";

  // 【权限判断】判断当前用户是否为管理员
  // 管理员包括"admin"和"super_admin"两种组别
  const isAdmin = userGroup === "admin" || userGroup === "super_admin";

  // ========================================
  // 【关键修复】获取require_payment配置
  // 用于实现与PC端相同的支付历史标签显示逻辑：
  // - require_payment = true 时，所有用户都能看到支付历史
  // - require_payment = false 时，只有管理员能看到支付历史
  // ========================================
  let requirePayment = false; // 默认值：不需要付费（安全默认值）

  try {
    // [异步请求] 向后端API发起GET请求，获取价格配置
    // 这个配置包含了require_payment字段，用于判断是否启用付费功能
    const pricingConfigResponse = await fetch("/api/admin/pricing_config", {
      method: "GET", // HTTP方法：GET（查询数据）
      headers: {
        "Content-Type": "application/json", // 请求头：指定返回内容类型为JSON
        "X-Session-ID": sessionUUID, // 请求头：传递会话UUID用于身份验证
      },
      credentials: "include", // 包含认证凭证（cookies），确保有权访问
    });

    // [JSON解析] 将响应体解析为JavaScript对象
    const pricingConfigData = await pricingConfigResponse.json();

    // [成功检查] 验证API调用是否成功，并提取require_payment字段
    if (pricingConfigData.success && pricingConfigData.config) {
      // 从配置对象中提取require_payment字段
      // 这个布尔值决定了是否对普通用户启用付费相关功能
      requirePayment = pricingConfigData.config.require_payment || false;

      // [调试日志] 记录成功获取的配置信息
      console.log("[移动端支付历史标签] 成功获取require_payment配置:", {
        requirePayment: requirePayment, // 是否需要付费
        userGroup: userGroup, // 当前用户组别
        isAdmin: isAdmin, // 是否为管理员
      });
    } else {
      // [警告日志] API调用失败或返回数据格式不正确
      console.warn(
        "[移动端支付历史标签] 获取require_payment配置失败，使用默认值false:",
        {
          success: pricingConfigData.success, // API调用是否成功
          hasConfig: !!pricingConfigData.config, // 是否包含config字段
        },
      );
    }
  } catch (error) {
    // [错误捕获] 如果网络请求失败或发生其他异常，记录错误并使用默认值
    // 可能的错误原因：网络断开、服务器无响应、JSON解析失败等
    console.error("[移动端支付历史标签] 获取require_payment配置时发生异常:", {
      error: error, // 错误对象
      errorMessage: error.message, // 错误消息
      defaultValue: requirePayment, // 使用的默认值
    });
    // 发生异常时保持requirePayment为默认值false（安全策略）
  }

  // 根据prefix参数确定标签导航容器和内容容器的ID
  let tabsNavId, contentId;
  if (prefix === "mobile-multi-admin") {
    tabsNavId = "mobile-multi-admin-tabs-nav";
    contentId = "mobile-multi-admin-panel-content";
  } else if (prefix === "mobile-admin-panel-unified") {
    // 统一移动端管理面板
    tabsNavId = "mobile-multi-admin-tabs-nav-panel";
    contentId = "mobile-multi-admin-content-panel";
  } else if (prefix === "mobile-admin-panel") {
    // 单账号模式管理面板，复用统一面板的标签导航
    tabsNavId = "mobile-admin-tabs-nav-panel";
    contentId = "mobile-admin-panel-content-panel";
  } else {
    tabsNavId = "mobile-admin-tabs-nav";
    contentId = "mobile-admin-panel-content";
  }
  const tabsNav = document.getElementById(tabsNavId);
  if (!tabsNav) {
    console.error(`[移动端管理面板] 找不到标签页导航容器: ${tabsNavId}`);
    return;
  }
  const allTabs = [
    {
      id: "users",
      label: "用户",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>',
      permission: "admin",
    },
    {
      id: "groups",
      label: "权限组",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>',
      permission: "admin",
    },
    {
      id: "logs",
      label: "日志",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
      permission: "admin",
    },
    {
      id: "health",
      label: "状态",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>',
      permission: "all",
    },
    {
      id: "profile",
      label: "资料",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>',
      permission: "no_guest",
    },
    {
      id: "sessions",
      label: "会话",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
      permission: "all",
    },
    {
      id: "messages",
      label: "留言",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>',
      permission: "all",
    },
    {
      id: "ipban",
      label: "IP封禁",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path></svg>',
      permission: "admin",
    },
    {
      id: "sms",
      label: "短信",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 00-2-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>',
      permission: "admin",
    },
    {
      id: "config",
      label: "配置",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>',
      permission: "admin",
    },
    {
      id: "captcha",
      label: "验证码",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
      permission: "admin",
    },
    {
      id: "reminders",
      label: "提醒",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
      permission: "admin",
    },
    {
      id: "ssl",
      label: "HTTPS",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>',
      permission: "admin",
    },
    // // ========================================
    // // 支付配置标签
    // // 管理员可以在此启用/禁用支付方式
    // // ========================================
    // {
    //   id: "payment-config",
    //   label: "支付配置",
    //   icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path></svg>',
    //   permission: "admin",
    // },
    // // ========================================
    // // 支付日志标签
    // // 管理员可以在此查看所有支付操作日志
    // // ========================================
    // {
    //   id: "payment-logs",
    //   label: "支付日志",
    //   icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>',
    //   permission: "admin",
    // },
    // 添加CDN缓存标签
    {
      id: "cdn",
      label: "CDN",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
      permission: "admin",
    },
    // 添加密码恢复标签 (权限设为 super_admin)
    {
      id: "bruteforce",
      label: "密码恢复",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path></svg>',
      permission: "super_admin",
    },
    // ========================================
    // 欠费查询标签
    // 管理员可以在此查看所有有欠费记录的学校账号
    // 功能：显示欠费账号列表，按欠费次数排序
    // 权限：管理员（admin）和超级管理员（super_admin）
    // ========================================
    // {
    //   id: "overdue", // 标签ID，用于标识和切换面板
    //   label: "欠费查询", // 标签显示的文本
    //   // 警告图标：表示欠费/异常状态
    //   icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
    //   permission: "admin", // 权限要求：管理员级别
    // },
    // ========================================
    // 支付历史标签
    // 移动端支付历史面板的标签，与PC端功能对应
    // 功能：查看支付相关操作日志，支持按操作类型、日期范围筛选
    // ========================================
    // 【特殊权限逻辑 - 与PC端保持一致】
    // 此标签的显示逻辑不同于其他管理员专属标签：
    // - require_payment = true（启用付费模式）：所有用户都能看到
    // - require_payment = false（免费模式）：只有管理员能看到
    // 使用特殊权限值 "payment-logs-special" 来标识这种特殊逻辑
    // ========================================
    {
      id: "payment-logs", // 标签ID，用于标识和切换面板
      label: "支付历史", // 标签显示的文本
      // 文档图标：表示日志/历史记录
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>',
      permission: "payment-logs-special", // 特殊权限：需要根据require_payment配置和用户角色共同判断
    },
    // ========================================
    // 支付设置标签
    // 移动端支付设置面板的标签，与PC端功能对应
    // 功能：配置支付方式、查询订单、处理退款、测试支付
    // 权限：管理员（admin）和超级管理员（super_admin）
    // ========================================
    {
      id: "payment-settings", // 标签ID，用于标识和切换面板
      label: "支付设置", // 标签显示的文本
      // 设置图标：表示支付配置
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>',
      permission: "admin", // 权限要求：管理员级别
    },
    // ========================================
    // 价格设置标签
    // 移动端价格设置面板的标签，与PC端功能对应
    // 功能：配置系统价格策略，包括是否启用付费、单次费用、免费次数
    // 权限：管理员（admin）和超级管理员（super_admin）
    // ========================================
    {
      id: "pricing", // 标签ID，用于标识和切换面板
      label: "价格设置", // 标签显示的文本
      // 价格图标：表示定价管理
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
      permission: "admin", // 权限要求：管理员级别
    },
    // ========================================
    // 水印控制标签
    // 移动端水印控制面板的标签，与PC端功能对应
    // 功能：配置用户是否可以使用高德地图去水印功能
    // 权限：管理员（admin）和超级管理员（super_admin）
    // ========================================
    {
      id: "watermark", // 标签ID，用于标识和切换面板
      label: "水印控制", // 标签显示的文本
      // 图层/文档图标：表示水印管理
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
      permission: "admin", // 权限要求：管理员级别
    },
    {
      id: "billing",
      label: "账单",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><g transform="scale(1.4) translate(-2.5, -3)"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2"d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8V7m0 1v8m0 0v1"></path></g></svg>',
      permission: "admin",
    },
    {
      id: "billing-logs",
      label: "账单日志",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>',
      permission: "admin",
    },
    {
      id: "restore-account",
      label: "账号恢复",
      icon: '<svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9"></path></svg>',
      permission: "admin",
    },
  ];
  // ========================================
  // 【标签权限过滤逻辑】
  // 根据用户权限组别和特殊权限配置过滤可见的标签
  // ========================================
  const visibleTabs = allTabs.filter((tab) => {
    // 权限类型1: "all" - 所有用户可见
    if (tab.permission === "all") return true;

    // 权限类型2: "admin" - 仅管理员和超级管理员可见
    if (
      tab.permission === "admin" &&
      (userGroup === "admin" || userGroup === "super_admin")
    )
      return true;

    // 权限类型3: "super_admin" - 仅超级管理员可见
    if (tab.permission === "super_admin" && userGroup === "super_admin")
      return true;

    // 权限类型4: "no_guest" - 仅非游客用户可见
    if (tab.permission === "no_guest" ){
      if ( currentUserIsGuest === true || currentUserIsGuest === 'true') {
        return false;}
      else{
        return true;}
    }

    // ========================================
    // 【关键修复】权限类型4: "payment-logs-special" - 支付历史标签的特殊权限逻辑
    // 与PC端保持一致的显示规则：
    // - 当 requirePayment = true（启用付费模式）时：所有用户都能看到
    // - 当 requirePayment = false（免费模式）时：只有管理员能看到
    //
    // 逻辑表达式：shouldShow = isAdmin || requirePayment
    // - 当 isAdmin = true 时：无论 requirePayment 值为何，结果都是 true（管理员始终可见）
    // - 当 isAdmin = false 且 requirePayment = true 时：结果是 true（普通用户在付费模式下可见）
    // - 当 isAdmin = false 且 requirePayment = false 时：结果是 false（普通用户在免费模式下不可见）
    // ========================================
    if (tab.permission === "payment-logs-special") {
      // 计算是否应该显示支付历史标签
      const shouldShowPaymentLogs = isAdmin || requirePayment;

      // [调试日志] 记录支付历史标签的显示决策过程
      console.log("[移动端支付历史标签] 显示状态判断:", {
        userGroup: userGroup, // 当前用户的组别
        isAdmin: isAdmin, // 是否拥有管理员权限
        requirePayment: requirePayment, // 系统是否启用付费功能
        shouldShowPaymentLogs: shouldShowPaymentLogs, // 最终是否显示标签
        决策说明: isAdmin
          ? "管理员：始终显示"
          : requirePayment
            ? "普通用户：系统启用付费，显示支付历史"
            : "普通用户：系统未启用付费，隐藏支付历史",
      });

      return shouldShowPaymentLogs;
    }

    return false;
  });
  tabsNav.innerHTML = "";
  visibleTabs.forEach((tab, index) => {
    const button = document.createElement("button");
    const isActive = index === 0;
    button.className = `px-4 py-2 font-semibold text-xs whitespace-nowrap rounded-lg transition ${
      isActive
        ? "text-sky-600 bg-sky-50 border-b-2 border-sky-600"
        : "text-slate-400 hover:text-slate-600 hover:bg-slate-50"
    }`;
    button.innerHTML = `${tab.icon}${tab.label}`;
    button.onclick = () => switchMobileAdminTab(tab.id, prefix);
    tabsNav.appendChild(button);
  });
  if (visibleTabs.length > 0) {
    // 修改：优先默认显示 'sessions' (会话列表)，如果该权限不可见则显示第一个
    const defaultTabId = visibleTabs.find((t) => t.id === "sessions")
      ? "sessions"
      : visibleTabs[0].id;
    switchMobileAdminTab(defaultTabId, prefix);
  }

  // ========================================
  // 【移动端多账号管理面板】绑定按钮事件
  // ========================================
  if (prefix === "mobile-admin-panel-unified") {
    initMobileMultiAdminButtonEvents();
  }
}

// ========================================
// 【移动端多账号管理面板】按钮事件初始化
// 修复问题：权限组、日志、健康状态、留言板等按钮无效
// ========================================
function initMobileMultiAdminButtonEvents() {
  // ========== 权限组管理相关按钮 ==========
  // 新增权限组按钮
  const createGroupBtn = document.getElementById(
    "mobile-multi-admin-create-group",
  );
  if (createGroupBtn) {
    createGroupBtn.onclick = function () {
      showMobileCreateGroupModal();
    };
  }

  // 刷新权限组按钮
  const refreshGroupsBtn = document.getElementById(
    "mobile-multi-admin-refresh-groups",
  );
  if (refreshGroupsBtn) {
    refreshGroupsBtn.onclick = function () {
      loadAdminGroups().then(() => copyAdminContentToMultiPanel("groups"));
    };
  }

  // ========== 日志查看相关控件 ==========
  // 日志行数选择变化时重新加载
  const logLimitSelect = document.getElementById(
    "mobile-multi-log-limit-select",
  );
  const logFilterSelect = document.getElementById(
    "mobile-multi-log-level-filter",
  );
  const logKeywordInput = document.getElementById(
    "mobile-multi-log-keyword-filter",
  );
  if (logLimitSelect) {
    logLimitSelect.onchange = function () {
      loadMobileMultiAdminLogs(1);
    };
  }
  if (logFilterSelect) {
    logFilterSelect.onchange = function () {
      loadMobileMultiAdminLogs(mobileMultiLogCurrentPage);
    };
  }
  if (logKeywordInput) {
    logKeywordInput.oninput = function () {
      loadMobileMultiAdminLogs(mobileMultiLogCurrentPage);
    };
  }

  // 日志页码选择变化时跳转
  const logPageSelect = document.getElementById("mobile-multi-log-page-select");
  if (logPageSelect) {
    logPageSelect.onchange = function () {
      const newPage = parseInt(logPageSelect.value, 10);
      if (!isNaN(newPage) && newPage > 0) {
        loadMobileMultiAdminLogs(newPage);
      }
    };
  }

  // 日志刷新按钮
  const refreshLogsBtn = document.getElementById(
    "mobile-multi-admin-refresh-logs",
  );
  if (refreshLogsBtn) {
    refreshLogsBtn.onclick = function () {
      loadMobileMultiAdminLogs(1);
    };
  }

  // 日志分页上一页/下一页按钮
  const logPrevBtn = document.getElementById("mobile-multi-log-prev-page");
  if (logPrevBtn) {
    logPrevBtn.onclick = function () {
      const pageSelect = document.getElementById(
        "mobile-multi-log-page-select",
      );
      const currentPage = pageSelect ? parseInt(pageSelect.value, 10) : 1;
      if (currentPage > 1) {
        loadMobileMultiAdminLogs(currentPage - 1);
      }
    };
  }

  const logNextBtn = document.getElementById("mobile-multi-log-next-page");
  if (logNextBtn) {
    logNextBtn.onclick = function () {
      const pageSelect = document.getElementById(
        "mobile-multi-log-page-select",
      );
      const totalPages = parseInt(pageSelect?.dataset.totalPages || "1", 10);
      const currentPage = pageSelect ? parseInt(pageSelect.value, 10) : 1;
      if (currentPage < totalPages) {
        loadMobileMultiAdminLogs(currentPage + 1);
      }
    };
  }

  // ========== 健康状态相关控件 ==========
  // 自动刷新开关
  const healthAutoRefreshToggle = document.getElementById(
    "mobile-multi-health-auto-refresh-toggle",
  );
  if (healthAutoRefreshToggle) {
    healthAutoRefreshToggle.onchange = function () {
      if (healthAutoRefreshToggle.checked) {
        startMobileMultiHealthAutoRefresh();
      } else {
        stopMobileMultiHealthAutoRefresh();
      }
    };
    // 如果默认选中，启动自动刷新
    if (healthAutoRefreshToggle.checked) {
      startMobileMultiHealthAutoRefresh();
    }
  }

  // 手动刷新按钮
  const refreshHealthBtn = document.getElementById(
    "mobile-multi-admin-refresh-health",
  );
  if (refreshHealthBtn) {
    refreshHealthBtn.onclick = function () {
      loadMobileMultiHealthStatus();
    };
  }

  // ========== 留言板相关 ==========
  // 刷新留言按钮
  const refreshMessagesBtn = document.getElementById(
    "mobile-multi-admin-refresh-messages",
  );
  if (refreshMessagesBtn) {
    refreshMessagesBtn.onclick = function () {
      loadMobileMultiMessages();
    };
  }

  // 发送留言按钮
  const sendMessageBtn = document.getElementById(
    "mobile-multi-post-message-btn",
  );
  if (sendMessageBtn) {
    sendMessageBtn.onclick = function () {
      submitMobileMultiMessage();
    };
  }

  // 留言内容字符计数
  const messageContentInput = document.getElementById(
    "mobile-multi-message-content",
  );
  const charCountDisplay = document.getElementById(
    "mobile-multi-message-char-count",
  );
  if (messageContentInput && charCountDisplay) {
    messageContentInput.oninput = function () {
      charCountDisplay.textContent = messageContentInput.value.length;
    };
  }

  // ========== 验证码管理相关 (修复无法点击问题) ==========
  const saveCaptchaBtn = document.getElementById(
    "mobile-save-captcha-settings-btn",
  );
  if (saveCaptchaBtn) {
    saveCaptchaBtn.onclick = function () {
      mobileSaveCaptchaSettings();
    };
  }

  const testCaptchaBtn = document.getElementById("mobile-test-captcha-btn");
  if (testCaptchaBtn) {
    testCaptchaBtn.onclick = function () {
      mobileTestCaptcha();
    };
  }

  // 确保切换视图的按钮也能正常工作 (虽然HTML中有inline onclick，但这里增强健壮性)
  // 这里的逻辑是：如果是在JS中动态绑定的，确保函数全局可用
}

// ========================================
// 【移动端多账号】日志加载专用函数
// ========================================
let mobileMultiLogCurrentPage = 1;

async function loadMobileMultiAdminLogs(newPage = 1) {
  mobileMultiLogCurrentPage = newPage;

  const contentEl = document.getElementById("mobile-multi-admin-logs-content");
  const limitSelect = document.getElementById("mobile-multi-log-limit-select");
  const filterSelect = document.getElementById("mobile-multi-log-level-filter");
  const keywordInput = document.getElementById("mobile-multi-log-keyword-filter");
  const pageSelect = document.getElementById("mobile-multi-log-page-select");
  const pageTotal = document.getElementById("mobile-multi-log-page-total");
  const prevBtn = document.getElementById("mobile-multi-log-prev-page");
  const nextBtn = document.getElementById("mobile-multi-log-next-page");

  if (!contentEl) {
    console.error("[移动端日志] 找不到日志内容容器");
    return;
  }

  contentEl.textContent = "加载中...";
  if (prevBtn) prevBtn.disabled = true;
  if (nextBtn) nextBtn.disabled = true;
  if (pageSelect) pageSelect.disabled = true;

  try {
    const limit = limitSelect ? limitSelect.value : 100;
    const keywordValue = keywordInput ? keywordInput.value.trim() : "";
    const response = await fetch(
      `/logs/view?page=${newPage}&limit=${limit}&keyword=${encodeURIComponent(keywordValue)}`,
      {
        headers: { "X-Session-ID": sessionUUID },
      },
    );
    const result = await response.json();

    if (!result.success) {
      contentEl.textContent = `加载失败: ${result.message}`;
      if (pageSelect)
        pageSelect.innerHTML = '<option value="1">第 1 / 1 页</option>';
      if (pageTotal) pageTotal.textContent = "(加载失败)";
      return;
    }

    const rawLogs = Array.isArray(result.logs) ? result.logs : [];
    const filteredLogs = filterLogsByLevel(
      rawLogs,
      filterSelect ? filterSelect.value : "all",
    );

    if (filteredLogs.length === 0) {
      contentEl.textContent = rawLogs.length === 0 ? "暂无日志" : "当前筛选条件下暂无日志";
      if (pageSelect)
        pageSelect.innerHTML = '<option value="1">第 1 / 1 页</option>';
      if (pageTotal) {
        pageTotal.textContent =
          rawLogs.length === 0 ? "(共 0 行)" : `(本页筛选后 0 / ${rawLogs.length} 行)`;
      }
      return;
    }

    renderHighlightedLogs(contentEl, filteredLogs, keywordValue);

    const pagination = result.pagination;
    if (pageTotal) {
      pageTotal.textContent =
        (filterSelect && filterSelect.value !== "all") || keywordValue
          ? `(本页筛选后 ${filteredLogs.length} / ${rawLogs.length} 行，总计 ${pagination.total_lines} 行)`
          : `(共 ${pagination.total_lines} 行)`;
    }

    if (pageSelect) {
      pageSelect.innerHTML = "";
      pageSelect.dataset.totalPages = pagination.total_pages;
      for (let i = 1; i <= pagination.total_pages; i++) {
        const option = document.createElement("option");
        option.value = i;
        option.textContent = `第 ${i} / ${pagination.total_pages} 页`;
        if (i === pagination.current_page) {
          option.selected = true;
        }
        pageSelect.appendChild(option);
      }
      pageSelect.disabled = false;
    }

    if (prevBtn) prevBtn.disabled = pagination.current_page <= 1;
    if (nextBtn)
      nextBtn.disabled = pagination.current_page >= pagination.total_pages;
  } catch (e) {
    console.error("[移动端日志] 加载失败:", e);
    contentEl.textContent = `加载失败: ${e.message}`;
    if (pageSelect) pageSelect.innerHTML = '<option value="1">1</option>';
    if (pageTotal) pageTotal.textContent = "(加载失败)";
  }
}

// ========================================
// 【移动端多账号】健康状态自动刷新
// ========================================
let mobileMultiHealthAutoRefreshInterval = null;
let mobileMultiHealthCountdownInterval = null;
let mobileMultiHealthCountdownSeconds = 5;

function startMobileMultiHealthAutoRefresh() {
  stopMobileMultiHealthAutoRefresh();

  const autoRefreshToggle = document.getElementById(
    "mobile-multi-health-auto-refresh-toggle",
  );
  if (!autoRefreshToggle || !autoRefreshToggle.checked) {
    return;
  }

  mobileMultiHealthCountdownSeconds = 5;
  updateMobileMultiHealthCountdown();

  // 倒计时显示
  mobileMultiHealthCountdownInterval = setInterval(() => {
    mobileMultiHealthCountdownSeconds--;
    updateMobileMultiHealthCountdown();

    if (mobileMultiHealthCountdownSeconds <= 0) {
      mobileMultiHealthCountdownSeconds = 5;
    }
  }, 1000);

  // 自动刷新
  mobileMultiHealthAutoRefreshInterval = setInterval(() => {
    const toggle = document.getElementById(
      "mobile-multi-health-auto-refresh-toggle",
    );
    if (toggle && toggle.checked) {
      loadMobileMultiHealthStatus();
      mobileMultiHealthCountdownSeconds = 5;
    } else {
      stopMobileMultiHealthAutoRefresh();
    }
  }, 5000);
}

function updateMobileMultiHealthCountdown() {
  const countdownDisplay = document.getElementById(
    "mobile-multi-health-countdown-display",
  );
  if (countdownDisplay) {
    if (mobileMultiHealthCountdownSeconds > 0) {
      countdownDisplay.textContent = `(${mobileMultiHealthCountdownSeconds}s)`;
    } else {
      countdownDisplay.textContent = "(刷新中...)";
    }
  }
}

function stopMobileMultiHealthAutoRefresh() {
  if (mobileMultiHealthAutoRefreshInterval) {
    clearInterval(mobileMultiHealthAutoRefreshInterval);
    mobileMultiHealthAutoRefreshInterval = null;
  }
  if (mobileMultiHealthCountdownInterval) {
    clearInterval(mobileMultiHealthCountdownInterval);
    mobileMultiHealthCountdownInterval = null;
  }
  const countdownDisplay = document.getElementById(
    "mobile-multi-health-countdown-display",
  );
  if (countdownDisplay) {
    countdownDisplay.textContent = "";
  }
}

async function loadMobileMultiHealthStatus() {
  const contentEl = document.getElementById(
    "mobile-multi-admin-health-content",
  );

  if (!contentEl) {
    console.error("[移动端健康状态] 找不到内容容器");
    return;
  }

  const scrollSnapshot = captureHealthScrollPositions(contentEl);
  const hasRenderedHealth = contentEl.dataset.healthLoaded === "true";
  if (!hasRenderedHealth) {
    contentEl.innerHTML =
      '<p class="text-slate-400 text-center py-10 text-xs">检测中...</p>';
  }

  try {
    const startTime = Date.now();
    const response = await fetch("/health", {
      method: "GET",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const responseTime = Date.now() - startTime;
    const result = await response.json();
    const memoryDiagnostics = result.memory_diagnostics;

    const presentation = getHealthStatusPresentation(result.status);
    const statusColor = presentation.color;
    const statusText = presentation.text;

    const summary =
      result.summary && typeof result.summary === "object" ? result.summary : null;
    const components =
      result.components && typeof result.components === "object"
        ? Object.values(result.components)
        : [];
    const uptimeText = escapeHtml(result.uptime_formatted || "-");
    const componentNameMap = {
      running_core: "跑步执行主链路",
      payment_system: "支付系统",
      sms_system: "短信系统",
    };

    const summaryHtml = summary
      ? `
          <div class="grid grid-cols-2 gap-2 mb-3">
            <div class="bg-rose-50 border border-rose-200 rounded-lg p-3">
              <h5 class="font-semibold text-rose-800 text-xs mb-1">核心异常数</h5>
              <p class="text-lg font-bold text-rose-600">${summary.critical_failed_count || 0}</p>
            </div>
            <div class="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <h5 class="font-semibold text-amber-800 text-xs mb-1">非核心异常数</h5>
              <p class="text-lg font-bold text-amber-600">${summary.non_critical_failed_count || 0}</p>
            </div>
          </div>
        `
      : "";

    const componentsHtml = components.length
      ? `
          <div class="bg-white border border-slate-200 rounded-lg p-3 mb-3">
            <h5 class="font-semibold text-slate-800 text-xs mb-2">组件详情</h5>
            <div class="space-y-2">
              ${components
                .map((component) => {
                  const componentPresentation = getHealthStatusPresentation(
                    component.status,
                  );
                  const componentColor = componentPresentation.color;
                  const componentText = componentPresentation.text;
                  const componentName = escapeHtml(
                    componentNameMap[component.name] || component.name || "未知组件",
                  );
                  const componentMessage = escapeHtml(component.message || "-");
                  return `
                    <div class="border border-slate-200 rounded-lg p-2 bg-slate-50">
                      <div class="flex items-center justify-between gap-2 mb-1">
                        <div class="font-semibold text-slate-800 text-xs">${componentName}</div>
                        <span class="px-2 py-0.5 rounded text-[10px] bg-${componentColor}-100 text-${componentColor}-700">${componentText}</span>
                      </div>
                      <div class="text-[10px] text-slate-600">${componentMessage}</div>
                    </div>
                  `;
                })
                .join("")}
            </div>
          </div>
        `
      : "";
    const memoryDiagnosticsHtml = renderHealthMemoryDiagnostics(
      { memory_diagnostics: memoryDiagnostics },
      true,
    );

    contentEl.innerHTML = `
      <div class="grid grid-cols-3 gap-2 mb-3">
        <div class="bg-${statusColor}-50 border border-${statusColor}-200 rounded-lg p-3">
          <h5 class="font-semibold text-${statusColor}-800 text-xs mb-1">服务器状态</h5>
          <p class="text-lg font-bold text-${statusColor}-600">${statusText}</p>
        </div>
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <h5 class="font-semibold text-blue-800 text-xs mb-1">响应时间</h5>
          <p class="text-lg font-bold text-blue-600">${responseTime}ms</p>
        </div>
        <div class="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <h5 class="font-semibold text-slate-800 text-xs mb-1">运行时长</h5>
          <p class="text-sm font-bold text-slate-700">${uptimeText}</p>
        </div>
      </div>
      ${summaryHtml}
      ${componentsHtml}
      ${memoryDiagnosticsHtml}
      <div class="bg-slate-50 border border-slate-200 rounded-lg p-3">
        <h5 class="font-semibold text-slate-800 text-xs mb-2">JSON 原文</h5>
        <pre class="text-[10px] text-slate-600 whitespace-pre-wrap font-mono overflow-x-auto"></pre>
      </div>
    `;
    const detailPre = contentEl.querySelector("pre");
    if (detailPre) {
      detailPre.textContent = JSON.stringify(result, null, 2);
    }
    contentEl.dataset.healthLoaded = "true";
    contentEl.dataset.healthLastSuccess = new Date().toLocaleString();
  } catch (e) {
    console.error("[移动端健康状态] 加载失败:", e);
    if (!hasRenderedHealth) {
      contentEl.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">检测失败: ${escapeHtml(e.message || "未知错误")}</p>`;
    } else {
      showHealthRefreshFailure(contentEl, e);
    }
  } finally {
    restoreHealthScrollPositions(scrollSnapshot);
  }
}

// ========================================
// 【移动端多账号】留言板功能
// ========================================
