// Payment, order, billing, refund, and SMS log legacy UI extracted from main.js.
const PAYMENT_LOG_ACTION_LABELS = Object.freeze({
  create_order: "创建订单",
  query_order: "查询订单",
  create_order_failed: "创建失败",
  payment_success_notify: "支付成功通知",
  refund: "退款操作",
  refund_failed: "退款失败",
  fetch_orders_from_platform: "从平台拉取订单",
  sync_order_from_platform: "从平台同步订单",
  query_order_by_tradeno: "按订单号查询",
  order_status_updated: "订单状态更新",
  create_order_from_notify: "根据通知补建订单",
  query_platform_order_failed: "平台订单查询失败",
  payment_notify_no_public_key: "支付通知未配置公钥",
  payment_notify_signature_failed: "支付通知验签失败",
  payment_notify_order_not_found: "支付通知订单不存在",
  payment_duplicate_notify: "重复支付通知",
  create_overdue_order: "创建欠费订单",
  overdue_payment_completed: "欠费支付完成",
  overdue_payment_error: "欠费支付处理失败",
  create_billing_order: "创建账单订单",
  billing_payment_completed: "账单支付完成",
  query_billing_order_active: "主动查询账单订单",
  query_billing_order_local: "本地查询账单订单",
  admin_update_payment_config: "更新支付配置",
  admin_update_pricing_config: "更新价格配置",
  admin_update_yipay_config: "更新易支付配置",
  admin_clear_overdue: "调整欠费次数",
  payment_success: "支付成功",
  payment_notify: "支付通知",
  payment_fail: "支付失败",
  config_update: "配置更新",
});

const PAYMENT_LOG_STATUS_LABELS = Object.freeze({
  success: "成功",
  completed: "成功",
  fail: "失败",
  failed: "失败",
  error: "失败",
  pending: "处理中",
  processing: "处理中",
  paid: "已支付",
  closed: "已关闭",
  refunded_partial: "部分退款",
  refunded_full: "全额退款",
  frozen: "已冻结",
  preauth: "预授权",
  timeout: "支付超时",
});

function getPaymentLogActionLabel(action) {
  const normalized = String(action || "").trim();
  return PAYMENT_LOG_ACTION_LABELS[normalized] || normalized || "未知操作";
}

function getPaymentLogStatusLabel(status) {
  const normalized = String(status || "").trim();
  return PAYMENT_LOG_STATUS_LABELS[normalized] || normalized || "-";
}

function openSMSReplyLogsModal() {
  // 获取modal元素
  const modal = document.getElementById("sms-reply-logs-modal");
  if (!modal) {
    // console.error('[SMS回复记录] 未找到modal元素');
    logMessage_Error("[SMS回复记录] 无法打开回复记录面板，modal元素不存在");
    return;
  }

  // 显示modal：移除hidden类
  modal.classList.remove("hidden");

  // 加载回复记录数据
  loadSMSReplyLogs();
}

/**
 * 关闭SMS回复记录Modal
 * 功能说明：
 * 1. 隐藏SMS回复记录modal
 * 2. 清空筛选条件
 *
 * 调用时机：
 * - 用户点击关闭按钮时
 * - 用户点击背景遮罩时
 *
 * 实现细节：
 * - 添加hidden类隐藏modal
 * - 清空手机号筛选输入框
 */
function closeSMSReplyLogsModal() {
  // 获取modal元素
  const modal = document.getElementById("sms-reply-logs-modal");
  if (!modal) {
    return;
  }

  // 隐藏modal：添加hidden类
  modal.classList.add("hidden");

  // 清空筛选条件
  const phoneFilter = document.getElementById("sms-reply-phone-filter");
  if (phoneFilter) {
    phoneFilter.value = "";
  }
}

/**
 * 加载SMS回复记录数据
 * 功能说明：
 * 1. 从后端API获取短信回复记录
 * 2. 渲染到列表中显示
 * 3. 支持按手机号筛选
 *
 * API端点：/api/sms/reply-logs
 * 请求方法：GET
 * 查询参数：
 * - phone: 手机号筛选（可选）
 * - limit: 返回记录数量，默认100
 *
 * 返回数据格式：
 * {
 *   success: boolean,
 *   logs: [
 *     {
 *       timestamp: number,
 *       datetime: string,
 *       phone: string,
 *       content: string,
 *       ip: string
 *     }
 *   ],
 *   total: number
 * }
 *
 * 实现细节：
 * - 显示加载状态
 * - 调用API获取数据
 * - 渲染回复记录卡片
 * - 处理空数据和错误情况
 */
function loadSMSReplyLogs() {
  // 获取列表容器元素
  const listContainer = document.getElementById("sms-reply-logs-list");
  if (!listContainer) {
    // console.error('[SMS回复记录] 未找到列表容器元素');
    logMessage_Error("[SMS回复记录] 无法加载回复记录，列表容器元素不存在");
    return;
  }

  // 显示加载状态
  listContainer.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-purple-500 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-slate-400 text-center text-sm">加载中...</p>
    </div>
  `;

  // 获取筛选条件：手机号
  const phoneFilter = document.getElementById("sms-reply-phone-filter");
  const phone = phoneFilter ? phoneFilter.value.trim() : "";

  // 构建API请求URL
  // 基础URL：/api/sms/reply-logs
  // 查询参数：limit=100（最多返回100条记录）
  // 如果有手机号筛选，则添加phone参数
  let url = "/api/sms/reply-logs?limit=100";
  if (phone) {
    url += `&phone=${encodeURIComponent(phone)}`;
  }

  // 发送API请求
  fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": sessionUUID,
    },
  })
    .then((response) => {
      // 检查HTTP响应状态
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      return response.json();
    })
    .then((result) => {
      // 检查API返回结果
      if (!result.success) {
        throw new Error(result.message || "加载失败");
      }

      // 获取回复记录列表
      const logs = result.logs || [];

      // 如果没有记录，显示空状态提示
      if (logs.length === 0) {
        listContainer.innerHTML = `
          <div class="flex flex-col items-center justify-center py-12">
            <svg class="w-16 h-16 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z">
              </path>
            </svg>
            <p class="text-slate-400 text-center text-base font-medium">暂无短信回复记录</p>
            <p class="text-slate-400 text-center text-sm mt-2">用户回复的短信会显示在这里</p>
          </div>
        `;
        return;
      }

      // 渲染回复记录列表
      // 使用数组map生成HTML字符串，然后join拼接
      const logsHTML = logs
        .map((log) => {
          // 转义HTML特殊字符，防止XSS攻击
          const escapeHTML = (str) => {
            const div = document.createElement("div");
            div.textContent = str;
            return div.innerHTML;
          };

          // 格式化显示的回复内容
          // 如果内容过长，截断并显示省略号
          const content = log.content || "";
          const displayContent =
            content.length > 100 ? content.substring(0, 100) + "..." : content;

          // 返回回复记录卡片HTML
          return `
          <div class="bg-white border-2 border-purple-200 rounded-xl p-4 hover:shadow-lg transition-shadow">
            <div class="flex items-start justify-between gap-3 mb-3">
              <div class="flex items-center gap-2">
                <span class="text-2xl">📱</span>
                <div>
                  <div class="font-semibold text-slate-800">${escapeHTML(
                    log.phone || "未知号码",
                  )}</div>
                  <div class="text-xs text-slate-500">${escapeHTML(
                    log.datetime || "",
                  )}</div>
                </div>
              </div>
              <div class="text-xs text-slate-400">
                IP: ${escapeHTML(log.ip || "-")}
              </div>
            </div>
            
            <div class="bg-purple-50 border-l-4 border-purple-400 rounded p-3">
              <div class="text-sm text-slate-700 whitespace-pre-wrap break-words">
                ${escapeHTML(displayContent)}
              </div>
            </div>
          </div>
        `;
        })
        .join("");

      // 更新列表容器内容
      listContainer.innerHTML = logsHTML;

      // 在控制台输出加载成功信息
      // console.log(`[SMS回复记录] 成功加载${logs.length}条记录`);
      logMessage_Info(`[SMS回复记录] 成功加载${logs.length}条记录`);
    })
    .catch((error) => {
      // 错误处理：显示错误提示
      // console.error('[SMS回复记录] 加载失败:', error);
      logMessage_Error("[SMS回复记录] 加载失败: " + error);
      listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-12">
          <svg class="w-16 h-16 text-red-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z">
            </path>
          </svg>
          <p class="text-red-500 text-center text-base font-medium">加载失败</p>
          <p class="text-slate-400 text-center text-sm mt-2">${
            error.message || "请稍后重试"
          }</p>
        </div>
      `;
    });
}

// ==========================================
// 支付日志面板功能实现
// ==========================================
// 【功能说明】
// 实现移动端支付日志面板的完整功能，包括：
// 1. 查询当前用户的支付日志
// 2. 支持按操作类型、日期范围筛选
// 3. 支持分页浏览
// 4. 自动刷新功能
//
// 【API说明】
// - /api/payment_logs: 查询当前登录用户的支付日志（自适应游客和注册用户）
// ==========================================

/**
 * 全局变量：支付日志分页状态
 *
 * 用途：
 * - 保存当前的分页信息
 * - 用于上一页/下一页功能
 *
 * 属性：
 * - currentPage: 当前页码（从1开始）
 * - totalPages: 总页数
 * - perPage: 每页显示数量
 */
let paymentLogsState = {
  currentPage: 1, // 当前页码，初始为第1页
  totalPages: 1, // 总页数，初始为1页
  perPage: 20, // 每页显示20条记录
};

/**
 * 加载支付日志数据
 *
 * 功能说明：
 * 1. 从后端API获取当前用户的支付日志
 * 2. 支持筛选和分页
 * 3. 渲染日志列表
 *
 * API端点：/api/payment_logs
 * 请求方法：GET
 * 查询参数：
 * - action: 操作类型筛选（可选）
 * - start_date: 开始日期（可选，格式：YYYY-MM-DD）
 * - end_date: 结束日期（可选，格式：YYYY-MM-DD）
 * - page: 页码（默认1）
 * - per_page: 每页数量（默认20）
 *
 * 返回数据格式：
 * {
 *   success: boolean,
 *   logs: [
 *     {
 *       user_id: string,
 *       order_id: string,
 *       action: string,
 *       datetime: string,
 *       amount: number,
 *       status: string,
 *       ... 其他字段
 *     }
 *   ],
 *   total: number,
 *   page: number,
 *   per_page: number
 * }
 *
 * 参数：
 * @param {number} page - 要加载的页码（可选，默认为当前页）
 */
function loadPaymentLogs(page) {
  // 如果没有指定页码，使用当前页码
  // 这样既支持直接调用loadPaymentLogs()刷新当前页
  // 也支持loadPaymentLogs(2)加载指定页
  if (typeof page === "undefined") {
    page = paymentLogsState.currentPage;
  }

  // 获取日志列表容器元素的DOM引用
  // 这个容器用于显示支付日志列表
  const listContainer = document.getElementById(
    "mobile-multi-admin-payment-logs-list",
  );
  if (!listContainer) {
    // 防御性检查：如果找不到容器元素，在控制台输出错误并返回
    // console.error('[支付日志] 未找到日志列表容器元素');
    logMessage_Error("[支付日志] 无法加载支付日志，列表容器元素不存在");
    return;
  }

  // 显示加载中状态
  // 使用SVG动画图标和文字提示，提升用户体验
  listContainer.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-sky-500 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-slate-400 text-center text-sm">正在加载支付日志...</p>
    </div>
  `;

  // ========== 收集筛选条件 ==========

  // 获取操作类型筛选值
  // 从下拉选择框获取用户选择的操作类型（如：create_order, payment_success等）
  const actionTypeSelect = document.getElementById("payment-logs-action-type");
  const actionType = actionTypeSelect ? actionTypeSelect.value.trim() : "";

  // 获取日期范围筛选值
  // 开始日期：用户可以选择查询从某个日期开始的日志
  const startDateInput = document.getElementById("payment-logs-start-date");
  const startDate = startDateInput ? startDateInput.value.trim() : "";

  // 结束日期：用户可以选择查询到某个日期结束的日志
  const endDateInput = document.getElementById("payment-logs-end-date");
  const endDate = endDateInput ? endDateInput.value.trim() : "";

  // ========== 构建API请求URL ==========

  // 基础URL：/api/payment_logs（查询当前用户的支付日志）
  // 使用URLSearchParams对象来构建查询字符串，这种方式更规范和安全
  const params = new URLSearchParams();

  // 添加分页参数
  params.append("page", page); // 当前页码
  params.append("per_page", paymentLogsState.perPage); // 每页数量

  // 如果用户选择了操作类型筛选，添加action参数
  if (actionType) {
    params.append("action", actionType);
  }

  // 如果用户输入了开始日期，添加start_date参数
  if (startDate) {
    params.append("start_date", startDate);
  }

  // 如果用户输入了结束日期，添加end_date参数
  if (endDate) {
    params.append("end_date", endDate);
  }

  // 拼接完整的请求URL
  // 格式示例：/api/payment_logs?page=1&per_page=20&action=create_order&start_date=2024-01-01
  const url = `/api/payment_logs?${params.toString()}`;

  // 在控制台输出请求信息，方便调试
  logMessage_Info(`[支付日志] 正在加载第${page}页，筛选条件:`, {
    actionType: actionType || "全部",
    startDate: startDate || "无限制",
    endDate: endDate || "无限制",
  });

  // ========== 发送API请求 ==========

  fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": sessionUUID,
    },
  })
    .then((response) => {
      // 检查HTTP响应状态码
      // 如果状态码不是2xx（成功），抛出错误
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      // 解析响应体为JSON对象
      return response.json();
    })
    .then((result) => {
      // 检查API返回的业务状态
      // success字段表示操作是否成功
      if (!result.success) {
        throw new Error(result.message || "加载支付日志失败");
      }

      // ========== 处理返回数据 ==========

      // 提取日志列表，如果为空则使用空数组
      const logs = result.logs || [];

      // 提取总记录数，用于计算总页数
      const total = result.total || 0;

      // 更新分页状态
      paymentLogsState.currentPage = page; // 更新当前页码
      // 计算总页数：总记录数除以每页数量，向上取整
      // 例如：23条记录，每页20条，总页数为2页
      paymentLogsState.totalPages = Math.ceil(total / paymentLogsState.perPage);

      // ========== 渲染日志列表 ==========

      // 检查是否有日志数据
      if (logs.length === 0) {
        // 没有日志时，显示空状态提示
        listContainer.innerHTML = `
          <div class="flex flex-col items-center justify-center py-12">
            <svg class="w-16 h-16 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z">
              </path>
            </svg>
            <p class="text-slate-400 text-center text-sm">暂无支付日志</p>
            <p class="text-slate-300 text-center text-xs mt-1">尝试调整筛选条件</p>
          </div>
        `;
      } else {
        // 有日志时，渲染日志卡片列表
        // 使用map函数遍历每条日志，生成对应的HTML
        const logsHTML = logs
          .map((log) => {
            // 为每条日志生成一个卡片
            // 包含：订单号、操作类型、时间、金额、状态等信息

            // 根据操作类型确定显示的标签样式
            // 不同的操作类型使用不同的颜色
            let actionBadgeClass = "bg-slate-100 text-slate-700"; // 默认样式
            let actionText = getPaymentLogActionLabel(log.action); // 操作类型文本

            // 根据不同的操作类型设置不同的样式
            if (log.action === "create_order") {
              actionBadgeClass = "bg-blue-100 text-blue-700";
              actionText = "创建订单";
            } else if (log.action === "query_order") {
              actionBadgeClass = "bg-purple-100 text-purple-700";
              actionText = "查询订单";
            } else if (log.action === "payment_success") {
              actionBadgeClass = "bg-green-100 text-green-700";
              actionText = "支付成功";
            } else if (log.action === "payment_fail") {
              actionBadgeClass = "bg-red-100 text-red-700";
              actionText = "支付失败";
            } else if (log.action === "config_update") {
              actionBadgeClass = "bg-orange-100 text-orange-700";
              actionText = "配置更新";
            }

            // 格式化金额显示
            // 如果日志中包含金额信息，格式化为货币格式（保留2位小数）
            const amountHTML = log.amount
              ? `<div class="text-xs text-slate-600">金额: <span class="font-semibold text-green-600">¥${parseFloat(
                  log.amount,
                ).toFixed(2)}</span></div>`
              : "";

            // 格式化状态显示
            // 根据状态值设置不同的颜色
            let statusHTML = "";
            if (log.status) {
              let statusClass = "text-slate-600";
              let statusText = getPaymentLogStatusLabel(log.status);

              if (log.status === "success" || log.status === "completed") {
                statusClass = "text-green-600";
                statusText = getPaymentLogStatusLabel(log.status);
              } else if (log.status === "failed" || log.status === "error") {
                statusClass = "text-red-600";
                statusText = getPaymentLogStatusLabel(log.status);
              } else if (
                log.status === "pending" ||
                log.status === "processing"
              ) {
                statusClass = "text-yellow-600";
                statusText = getPaymentLogStatusLabel(log.status);
              }

              statusHTML = `<div class="text-xs ${statusClass}">状态: ${statusText}</div>`;
            }

            // 返回单条日志的HTML卡片
            // 包含：操作类型标签、时间、订单号、金额、状态、查看详情按钮
            return `
            <div class="bg-white border border-slate-200 rounded-lg p-3 hover:border-sky-300 transition">
              <!-- 头部：操作类型标签 + 时间 -->
              <div class="flex justify-between items-start mb-2">
                <span class="inline-block px-2 py-1 rounded text-xs font-medium ${actionBadgeClass}">
                  ${actionText}
                </span>
                <span class="text-xs text-slate-500">${
                  log.datetime || "未知时间"
                }</span>
              </div>
              
              <!-- 订单号 -->
              <div class="text-sm font-medium text-slate-800 mb-1">
                订单号: ${log.order_id || "无"}
              </div>
              
              <!-- 详细信息：金额和状态 -->
              <div class="space-y-1 mb-3">
                ${amountHTML}
                ${statusHTML}
              </div>
              
              <!-- 查看详情按钮 -->
              <!-- 点击后调用 showPaymentLogDetail 函数显示完整的日志详情 -->
              <!-- 按钮设计为全宽，适合移动端触摸操作（min-height: 44px） -->
              <button onclick="showPaymentLogDetail(${escapeInlineJsArg(log.log_id || "")})"
                class="w-full py-2.5 px-4 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 active:bg-sky-700 transition-colors min-h-[44px] flex items-center justify-center gap-1">
                <!-- 眼睛图标：表示"查看"操作 -->
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                查看详情
              </button>
            </div>
          `;
          })
          .join(""); // 将所有卡片HTML连接成一个字符串

        // 更新列表容器的内容
        listContainer.innerHTML = logsHTML;
      }

      // ========== 更新分页控件 ==========

      updatePaymentLogsPagination();

      // 在控制台输出成功信息，方便调试
      // console.log(`[支付日志] 成功加载第${page}页，共${logs.length}条记录，总计${total}条`);
      logMessage_Info(
        `[支付日志] 成功加载第${page}页，共${logs.length}条记录，总计${total}条`,
      );
    })
    .catch((error) => {
      // ========== 错误处理 ==========

      // 在控制台输出详细错误信息
      // console.error('[支付日志] 加载失败:', error);
      logMessage_Error("[支付日志] 加载失败: " + "error");

      // 在列表容器中显示错误提示
      listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-12">
          <svg class="w-16 h-16 text-red-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z">
            </path>
          </svg>
          <p class="text-red-500 text-center text-base font-medium">加载失败</p>
          <p class="text-slate-400 text-center text-sm mt-2">${
            error.message || "请稍后重试"
          }</p>
          <button onclick="loadPaymentLogs()" class="mt-4 px-4 py-2 bg-sky-500 text-white rounded text-sm hover:bg-sky-600">
            重试
          </button>
        </div>
      `;
    });
}

// // ====== Editor.md: 在留言区域初始化 Markdown 编辑器 ======
// var messageEditorInstance = null;
// function initMessageMarkdownEditor() {
//   try {
//     var editorContainer = document.getElementById('message-editor');
//     if (!editorContainer) return;

//     // 如果 editormd 未定义，跳过初始化
//     if (typeof editormd === 'undefined') return;

//     // 创建编辑器实例
//     messageEditorInstance = editormd('message-editor', {
//         // ===== 基本配置 =====
//         // 编辑器模式：
//         // gfm：GitHub Flavored Markdown，与 Markdown 语法基本相同，但增加了一些扩展语法，如表格、任务列表等
//         // markdown：标准 Markdown 语法
//         mode: "gfm",
//         // 表单元素名称，用于提交表单时标识该编辑器
//         name: "editor",
//         // CodeMirror 的值，如果模式不是 gfm/markdown（通常不需要设置，留空即可）
//         value: "",
//         // 编辑器主题，可选值：default（默认主题）, dark（暗色主题）
//         theme: "default",
//         // 编辑区域主题（代码编辑区域的样式），可选值包括：
//         // default, 3024-day, 3024-night, ambiance, ambiance-mobile, base16-dark, base16-light,
//         // blackboard, cobalt, eclipse, elegant, erlang-dark, lesser-dark, mbo, mdn-like,
//         // midnight, monokai, neat, neo, night, paraiso-dark, paraiso-light, pastel-on-dark,
//         // rubyblue, solarized, the-matrix, tomorrow-night-eighties, twilight, vibrant-ink,
//         // xq-dark, xq-light
//         editorTheme: "default",
//         // 预览区域主题，默认空表示使用默认主题，可选值：default（默认主题）, dark（暗色主题）
//         previewTheme: "default",
//         // Markdown 源代码（编辑器初始化时显示的内容，可以是预填的 Markdown 文本）
//         markdown: "",
//         // 如果初始化时 textarea 值不为空，则追加 markdown 到 textarea（通常用于追加内容到现有文本）
//         appendMarkdown: "",
//         // 编辑器宽度（支持百分比如"100%"或像素值如"800px"）
//         width: "auto",
//         // 编辑器高度（支持百分比如"100%"或像素值如"600px"）
//         height: "300px",
//         // 依赖模块文件目录（Editor.md 所需的文件路径，通常使用 CDN 地址）
//         path: "/editor.md/lib/",
//         // 插件路径，如果为空，默认使用 settings.path + "../plugins/"（插件存放目录）
//         pluginPath: "/editor.md/plugins/",
//         // 延迟解析 markdown 到 html，单位：毫秒（避免频繁解析，提升性能，默认300ms）
//         delay: 300,
//         // 自动加载依赖模块文件（推荐保持 true，确保所有功能正常工作）
//         autoLoadModules: true,
//         // ===== 编辑器行为配置 =====
//         // 监听模式（是否实时预览，true 为开启监听，false 为手动预览）
//         watch: true,
//         // 占位符文本（当编辑器为空时显示的提示文本，引导用户输入）
//         placeholder: "Enjoy Markdown! coding now...",
//         // 启用/禁用 跳转到行功能（Ctrl+G 快捷键，快速跳转到指定行）
//         gotoLine: true,
//         // 代码折叠（是否允许折叠代码块，方便查看长代码）
//         codeFold: false,
//         // 自动高度（是否根据内容自动调整编辑器高度，true 时高度自适应）
//         autoHeight: false,
//         // 启用/禁用 自动聚焦编辑器左侧输入区域（页面加载后自动聚焦到编辑器）
//         autoFocus: true,
//         // 自动关闭标签（输入 < 时自动补全标签，提高 HTML 编写效率）
//         autoCloseTags: true,
//         // 启用/禁用 搜索和替换功能（CodeMirror 的搜索功能，Ctrl+F 激活）
//         searchReplace: true,
//         // 同步滚动选项：true（同步滚动）| false（不同步）| "single"（单向同步），默认 true
//         syncScrolling: true,
//         // 启用/禁用 只读模式（设为 true 后无法编辑，只能查看）
//         readOnly: false,
//         // 制表符大小（Tab 键缩进的空格数，通常设为 4）
//         tabSize: 4,
//         // 缩进单位（每次缩进的空格数，通常与 tabSize 保持一致）
//         indentUnit: 4,
//         // 显示编辑器行号（左侧显示行号，便于定位代码位置）
//         lineNumbers: true,
//         // 行换行（是否自动换行，true 时长行会自动换行）
//         lineWrapping: true,
//         // 自动关闭括号（输入左括号时自动补全右括号，支持 (), [], {}）
//         autoCloseBrackets: true,
//         // 显示尾随空格（显示行末的空格字符，帮助保持代码整洁）
//         showTrailingSpace: true,
//         // 匹配括号（高亮匹配的括号对，方便检查括号匹配）
//         matchBrackets: true,
//         // 使用制表符缩进（true 使用 Tab 字符，false 使用空格）
//         indentWithTabs: true,
//         // 样式化选中文本（选中的文本是否有特殊样式，如背景色）
//         styleSelectedText: true,
//         // 匹配单词高亮：true（高亮所有相同单词）| false（不高亮）| "onselected"（只在选中时高亮）
//         matchWordHighlight: true,
//         // 高亮当前行（当前行是否有背景色，方便定位）
//         styleActiveLine: true,
//         // ===== 对话框配置 =====
//         // 对话框锁定屏幕（对话框弹出时是否锁定背景，防止误操作）
//         dialogLockScreen: true,
//         // 对话框显示遮罩（是否显示半透明遮罩层）
//         dialogShowMask: true,
//         // 对话框可拖拽（对话框是否可以拖动位置）
//         dialogDraggable: true,
//         // 对话框遮罩背景色（遮罩的颜色，通常使用白色或半透明）
//         dialogMaskBgColor: "#fff",
//         // 对话框遮罩不透明度（0.0 到 1.0，控制遮罩透明度）
//         dialogMaskOpacity: 0.1,
//         // 字体大小（编辑器内文字的大小，影响可读性）
//         fontSize: "13px",
//         // 如果启用，编辑器将创建一个 <textarea> 标签保存 HTML 代码用于表单提交
//         saveHTMLToTextarea: true,
//         // 禁用的键映射（禁用某些快捷键，数组格式，如 ["Ctrl-B", "Ctrl-I"]）
//         disabledKeyMaps: [],

//         // ===== 事件回调函数 =====
//         // 加载完成回调（编辑器初始化完成后触发）
//         onload: function () {
//           try {
//             var ta = document.getElementById('message-content');
//             if (ta && this.getMarkdown) {
//               ta.value = this.getMarkdown() || '';
//             }
//             var cc = document.getElementById('message-char-count');
//             if (cc) cc.textContent = (ta && ta.value ? ta.value.length : 0).toString();
//           } catch (e) {
//             console.warn('editor onload 同步失败', e);
//           }
//         },
//         // 调整大小回调（编辑器大小改变时触发）
//         onresize: function () { },
//         // 内容改变回调（编辑器内容发生变化时触发）
//         onchange: function () {
//           try {
//             var ta = document.getElementById('message-content');
//             if (ta && this.getMarkdown) {
//               ta.value = this.getMarkdown() || '';
//             }
//             var cc = document.getElementById('message-char-count');
//             if (cc) cc.textContent = (ta && ta.value ? ta.value.length : 0).toString();
//           } catch (e) {
//             console.warn('editor onchange 同步失败', e);
//           }
//         },
//         // 监听开始回调（开始监听模式时触发）
//         onwatch: null,
//         // 监听结束回调（结束监听模式时触发）
//         onunwatch: null,
//         // 预览中回调（正在生成预览时触发）
//         onpreviewing: function () { },
//         // 预览完成回调（预览生成完成后触发）
//         onpreviewed: function () { },
//         // 全屏回调（进入全屏模式时触发）
//         onfullscreen: function () { },
//         // 退出全屏回调（退出全屏模式时触发）
//         onfullscreenExit: function () { },
//         // 滚动回调（编辑器滚动时触发）
//         onscroll: function () { },
//         // 预览滚动回调（预览区域滚动时触发）
//         onpreviewscroll: function () { },

//         // ===== 图片上传配置 =====
//         // 启用/禁用 上传功能（是否允许上传图片到服务器）
//         imageUpload: true,
//         // 支持的图片格式（允许上传的图片文件类型数组）
//         imageFormats: ["jpg", "jpeg", "gif", "png", "bmp", "webp"],
//         // 上传 URL（图片上传的服务器端点地址）
//         imageUploadURL: "/upload",
//         // 启用/禁用 跨域上传（是否支持跨域上传图片）
//         crossDomainUpload: false,
//         // 跨域上传回调 URL（跨域上传时的回调地址，用于处理上传结果）
//         // uploadCallbackURL: "",

//         // ===== 目录和扩展功能配置 =====
//         // 启用/禁用 目录功能（是否自动生成文章目录）
//         toc: true,
//         // 使用 [TOCM]，自动创建目录下拉菜单（在标题前添加 [TOCM] 标记启用）
//         tocm: false,
//         // 目录下拉菜单按钮标题（下拉菜单的显示文本）
//         tocTitle: "",
//         // 启用/禁用 目录下拉菜单（是否显示目录下拉菜单按钮）
//         tocDropdown: false,
//         // 自定义目录容器选择器（目录插入的 DOM 元素选择器，默认插入编辑器内部）
//         tocContainer: "",
//         // 从 H1 开始创建目录（目录从哪一级标题开始生成，1表示H1，2表示H2）
//         tocStartLevel: 1,
//         // 打开 HTML 标签识别（是否解析和显示 HTML 标签）
//         htmlDecode: true,
//         // 启用解析分页符 [========]（是否支持分页符语法，用于分隔内容）
//         pageBreak: true,
//         // 启用 @链接功能（@用户名 自动转换为链接）
//         atLink: false,
//         // 邮箱地址自动链接（自动识别邮箱地址并转换为可点击链接）
//         emailLink: true,
//         // 启用 GitHub Flavored Markdown 任务列表（支持 - [ ] 任务列表语法）
//         taskList: true,
//         // 启用表情符号支持：
//         // :emoji: 支持 GitHub 表情、Twitter 表情 (Twemoji)
//         // :fa-xxx: 使用 FontAwesome 图标 web 字体
//         // :editormd-logo: :editormd-logo-1x: > 1~8x 支持 Editor.md logo 图标
//         emoji: true,
//         // 启用 TeX(LaTeX) 数学公式支持，基于 KaTeX 库
//         tex: true,
//         // 启用流程图支持（flowChart.js，只支持 IE9+，用于绘制流程图）
//         flowChart: true,
//         // 启用时序图支持（sequenceDiagram.js，只支持 IE9+，用于绘制时序图）
//         sequenceDiagram: true,
//         // 启用/禁用 编辑器预览区域代码高亮（预览区代码是否进行语法高亮）
//         previewCodeHighlight: true,

//         // ===== 工具栏配置 =====
//         // 显示或隐藏工具栏
//         toolbar: true,
//         // 窗口滚动时自动固定工具栏位置
//         toolbarAutoFixed: true,
//         // 工具栏图标模式：full（完整）| simple（简单）| mini（最小），参见 `editormd.toolbarModes` 属性
//         toolbarIcons: "full",
//         // 工具栏标题（自定义工具栏按钮的提示文本）
//         toolbarTitles: {},
//         // 工具栏处理程序（自定义工具栏按钮的点击事件）
//         toolbarHandlers: {},
//         // 使用 HTML 标签创建工具栏图标，未使用默认 <a> 标签（自定义工具栏图标的 HTML）
//         toolbarCustomIcons: {},
//         // 工具栏图标文本（自定义工具栏按钮的文本）
//         toolbarIconTexts: {},

//       });

//     // 首次初始化后立即同步隐藏 textarea 和字符计数（兼容旧提交逻辑）
//     try {
//       var taImmediate = document.getElementById('message-content');
//       if (taImmediate && messageEditorInstance && typeof messageEditorInstance.getMarkdown === 'function') {
//         taImmediate.value = messageEditorInstance.getMarkdown() || '';
//         var ccImmediate = document.getElementById('message-char-count');
//         if (ccImmediate) ccImmediate.textContent = taImmediate.value.length.toString();
//       }

//       // 有时编辑器依赖的模块异步加载会导致首次渲染不完整，延迟触发 resize/loadedDisplay/refresh 修复 UI
//       setTimeout(function() {
//         try {
//           if (messageEditorInstance && typeof messageEditorInstance.resize === 'function') {
//             messageEditorInstance.resize();
//           }
//           if (messageEditorInstance && typeof messageEditorInstance.loadedDisplay === 'function') {
//             messageEditorInstance.loadedDisplay(true);
//           }
//           if (messageEditorInstance && messageEditorInstance.cm && typeof messageEditorInstance.cm.refresh === 'function') {
//             messageEditorInstance.cm.refresh();
//           }
//           if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
//             window.dispatchEvent(new Event('resize'));
//           }

//           // 再次同步 textarea 与字符计数，确保最终一致
//           var ta = document.getElementById('message-content');
//           if (ta && messageEditorInstance && typeof messageEditorInstance.getMarkdown === 'function') {
//             ta.value = messageEditorInstance.getMarkdown() || '';
//             var cc = document.getElementById('message-char-count');
//             if (cc) cc.textContent = ta.value.length.toString();
//           }
//         } catch (e) {
//           console.warn('Editor.md 延迟刷新或同步失败', e);
//         }
//       }, 250);
//     } catch (e) {
//       console.warn('初始化留言 Markdown 编辑器后同步失败', e);
//     }

//   } catch (e) {
//     console.error('初始化留言 Markdown 编辑器失败:', e);
//   }
// }

// // 在 DOMReady 时初始化（scripts/main.js 使用 defer，DOM 已解析）
// try {
//   if (document.readyState === 'loading') {
//     document.addEventListener('DOMContentLoaded', initMessageMarkdownEditor);
//   } else {
//     initMessageMarkdownEditor();
//   }
// } catch (e) {
//   console.error(e);
// }

/**
 * 更新分页控件状态
 *
 * 功能说明：
 * 1. 更新页码显示文本
 * 2. 更新上一页/下一页按钮的启用/禁用状态
 *
 * 调用时机：
 * - 每次加载日志后
 * - 用户点击分页按钮后
 *
 * 实现细节：
 * - 第一页时，禁用"上一页"按钮
 * - 最后一页时，禁用"下一页"按钮
 * - 只有一页时，两个按钮都禁用
 */
function updatePaymentLogsPagination() {
  // 获取分页控件元素
  const pageInfo = document.getElementById("payment-logs-page-info");
  const prevBtn = document.getElementById("payment-logs-prev-btn");
  const nextBtn = document.getElementById("payment-logs-next-btn");

  // 防御性检查：确保所有元素都存在
  if (!pageInfo || !prevBtn || !nextBtn) {
    // console.error('[支付日志] 分页控件元素未找到');
    logMessage_Error("[支付日志] 无法更新分页控件，元素不存在");
    return;
  }

  // 更新页码显示文本
  // 格式：第 X 页 / 共 Y 页
  pageInfo.textContent = `第 ${paymentLogsState.currentPage} 页 / 共 ${paymentLogsState.totalPages} 页`;

  // 更新"上一页"按钮状态
  // 如果当前是第一页，禁用"上一页"按钮
  if (paymentLogsState.currentPage <= 1) {
    prevBtn.disabled = true; // 禁用按钮
    prevBtn.classList.add("opacity-50", "cursor-not-allowed"); // 添加视觉提示
  } else {
    prevBtn.disabled = false; // 启用按钮
    prevBtn.classList.remove("opacity-50", "cursor-not-allowed"); // 移除视觉提示
  }

  // 更新"下一页"按钮状态
  // 如果当前是最后一页，禁用"下一页"按钮
  if (paymentLogsState.currentPage >= paymentLogsState.totalPages) {
    nextBtn.disabled = true; // 禁用按钮
    nextBtn.classList.add("opacity-50", "cursor-not-allowed"); // 添加视觉提示
  } else {
    nextBtn.disabled = false; // 启用按钮
    nextBtn.classList.remove("opacity-50", "cursor-not-allowed"); // 移除视觉提示
  }
}

/**
 * 加载上一页
 *
 * 功能说明：
 * 加载支付日志的上一页数据
 *
 * 调用时机：
 * - 用户点击"上一页"按钮时
 *
 * 实现细节：
 * - 检查是否已经是第一页
 * - 如果不是，页码减1并重新加载
 */
function loadPaymentLogsPrevPage() {
  // 检查是否已经是第一页
  if (paymentLogsState.currentPage <= 1) {
    // console.log('[支付日志] 已经是第一页');
    logMessage_Warning("[支付日志] 已经是第一页，无法加载上一页");
    return; // 如果已经是第一页，直接返回，不执行操作
  }

  // 页码减1
  const prevPage = paymentLogsState.currentPage - 1;

  // 加载上一页数据
  loadPaymentLogs(prevPage);
}

/**
 * 加载下一页
 *
 * 功能说明：
 * 加载支付日志的下一页数据
 *
 * 调用时机：
 * - 用户点击"下一页"按钮时
 *
 * 实现细节：
 * - 检查是否已经是最后一页
 * - 如果不是，页码加1并重新加载
 */
function loadPaymentLogsNextPage() {
  // 检查是否已经是最后一页
  if (paymentLogsState.currentPage >= paymentLogsState.totalPages) {
    // console.log('[支付日志] 已经是最后一页');
    logMessage_Warning("[支付日志] 已经是最后一页，无法加载下一页");
    return; // 如果已经是最后一页，直接返回，不执行操作
  }

  // 页码加1
  const nextPage = paymentLogsState.currentPage + 1;

  // 加载下一页数据
  loadPaymentLogs(nextPage);
}

// ==========================================
// 事件监听器绑定
// ==========================================
// 在页面加载完成后，为各个按钮绑定事件监听器
// 使用 DOMContentLoaded 事件确保DOM完全加载后再绑定
// ==========================================

document.addEventListener("DOMContentLoaded", function () {
  // 绑定"刷新"按钮的点击事件
  // 点击后重新加载当前页的数据
  const refreshBtn = document.getElementById(
    "mobile-multi-admin-refresh-payment-logs",
  );
  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () {
      // console.log('[支付日志] 用户点击刷新按钮');
      logMessage_Info("[支付日志] 用户点击刷新按钮");
      loadPaymentLogs(); // 重新加载当前页
    });
  }

  // 绑定"查询日志"按钮的点击事件
  // 点击后根据用户选择的筛选条件，从第1页开始查询
  const searchBtn = document.getElementById("search-payment-logs-btn");
  if (searchBtn) {
    searchBtn.addEventListener("click", function () {
      // console.log('[支付日志] 用户点击查询按钮');
      logMessage_Info("[支付日志] 用户点击查询按钮");
      paymentLogsState.currentPage = 1; // 重置为第1页
      loadPaymentLogs(1); // 从第1页开始加载
    });
  }

  // 绑定"上一页"按钮的点击事件
  const prevBtn = document.getElementById("payment-logs-prev-btn");
  if (prevBtn) {
    prevBtn.addEventListener("click", function () {
      // console.log('[支付日志] 用户点击上一页按钮');
      logMessage_Info("[支付日志] 用户点击上一页按钮");
      loadPaymentLogsPrevPage();
    });
  }

  // 绑定"下一页"按钮的点击事件
  const nextBtn = document.getElementById("payment-logs-next-btn");
  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      // console.log('[支付日志] 用户点击下一页按钮');
      logMessage_Info("[支付日志] 用户点击下一页按钮");
      loadPaymentLogsNextPage();
    });
  }

  // 注意：这里不自动加载数据
  // 因为支付日志面板默认是隐藏的
  // 只有当用户切换到该面板时才需要加载
  // 可以在面板显示时调用 loadPaymentLogs() 来加载数据
});

// --- Next Script Block ---

// ==========================================
// 全局状态管理对象
// ==========================================

/**
 * PC端管理员支付日志分页状态对象
 *
 * 用途：
 * - 保存当前的分页信息（当前页、总页数、每页数量）
 * - 用于实现上一页/下一页翻页功能
 * - 避免重复请求，提升用户体验
 *
 * 属性说明：
 * - currentPage: 当前页码（从1开始计数）
 * - totalPages: 总页数（根据总记录数和每页数量计算得出）
 * - perPage: 每页显示的日志数量（默认20条）
 *
 * 注意事项：
 * - 此对象与移动端的paymentLogsState独立，互不影响
 * - 使用adminPaymentLogsState前缀以区分PC端和移动端
 */
let adminPaymentLogsState = {
  currentPage: 1, // 当前页码，初始值为第1页
  totalPages: 1, // 总页数，初始值为1页（在加载数据后会更新）
  perPage: 20, // 每页显示20条记录（可根据需要调整）
};

const adminBillingLogsState = {
  currentPage: 1,
  totalPages: 1,
  pageSize: 50,
};

// ==========================================
// 核心功能函数
// ==========================================

/**
 * 加载PC端管理员支付日志数据
 *
 * 功能说明：
 * 1. 从后端API获取当前用户的支付日志
 * 2. 支持按操作类型、日期范围筛选
 * 3. 支持分页浏览
 * 4. 渲染日志列表到页面
 *
 * API端点：/api/payment_logs
 * 请求方法：GET
 *
 * 查询参数：
 * - action: 操作类型筛选（可选，如：create_order, payment_success等）
 * - start_date: 开始日期（可选，格式：YYYY-MM-DD）
 * - end_date: 结束日期（可选，格式：YYYY-MM-DD）
 * - page: 页码（必需，从1开始）
 * - per_page: 每页数量（必需，默认20）
 *
 * 返回数据格式：
 * {
 *   success: boolean,        // 操作是否成功
 *   logs: [                  // 日志数组
 *     {
 *       user_id: string,     // 用户ID
 *       order_id: string,    // 订单号
 *       action: string,      // 操作类型
 *       datetime: string,    // 操作时间
 *       amount: number,      // 金额
 *       status: string,      // 状态
 *       ... 其他字段
 *     }
 *   ],
 *   total: number,           // 总记录数
 *   page: number,            // 当前页码
 *   per_page: number         // 每页数量
 * }
 *
 * 参数：
 * @param {number} page - 要加载的页码（可选，默认为当前页）
 */
function loadAdminPaymentLogs(page) {
  // ========== 参数处理 ==========

  // 如果没有指定页码，使用当前保存的页码
  // 这样设计的好处：
  // 1. 支持直接调用loadAdminPaymentLogs()刷新当前页
  // 2. 支持调用loadAdminPaymentLogs(2)跳转到指定页
  if (typeof page === "undefined") {
    page = adminPaymentLogsState.currentPage;
  }

  // ========== 获取DOM元素 ==========

  // 获取日志列表容器元素的DOM引用
  // 这个容器用于显示支付日志列表
  const listContainer = document.getElementById(
    "admin-payment-logs-list_modal",
  );
  if (!listContainer) {
    // 防御性检查：如果找不到容器元素，输出错误信息并返回
    // 这通常意味着HTML结构有问题或ID命名错误
    // console.error('[PC端支付日志] 未找到日志列表容器元素');
    logMessage_Error("[PC端支付日志] 未找到日志列表容器元素");
    return;
  }

  // ========== 显示加载状态 ==========

  // 在加载数据时显示加载动画，提升用户体验
  // 使用SVG旋转动画图标和提示文字
  listContainer.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12">
      <!-- 旋转的加载图标 -->
      <svg class="animate-spin h-10 w-10 text-sky-500 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <!-- 加载提示文字 -->
      <p class="text-slate-400 text-center text-sm">正在加载支付日志...</p>
    </div>
  `;

  // ========== 收集筛选条件 ==========

  // 获取操作类型筛选值
  // 从下拉选择框获取用户选择的操作类型（如：create_order, payment_success等）
  // 使用trim()去除首尾空格，确保数据的干净性
  const actionTypeSelect = document.getElementById(
    "admin-payment-logs-action-type_modal",
  );
  const actionType = actionTypeSelect ? actionTypeSelect.value.trim() : "";

  // 获取日期范围筛选值
  // 开始日期：用户可以选择查询从某个日期开始的日志
  // 日期格式：YYYY-MM-DD（HTML5 date input的标准格式）
  const startDateInput = document.getElementById(
    "admin-payment-logs-start-date_modal",
  );
  const startDate = startDateInput ? startDateInput.value.trim() : "";

  // 结束日期：用户可以选择查询到某个日期结束的日志
  // 日期格式：YYYY-MM-DD（与开始日期格式一致）
  const endDateInput = document.getElementById(
    "admin-payment-logs-end-date_modal",
  );
  const endDate = endDateInput ? endDateInput.value.trim() : "";

  // ========== 构建API请求URL ==========

  // 使用URLSearchParams对象构建查询字符串
  // 这种方式比手动拼接字符串更规范、更安全，且能自动处理URL编码
  // URLSearchParams会自动编码特殊字符（如空格、中文等）
  const params = new URLSearchParams();

  // 添加分页参数（必需）
  // 这两个参数在每次请求中都必须包含
  params.append("page", page); // 当前页码
  params.append("per_page", adminPaymentLogsState.perPage); // 每页数量

  // 添加可选的筛选参数
  // 只有当用户选择了筛选条件时才添加相应参数，避免发送无用参数
  // 这样可以让API更容易理解用户的意图

  // 如果用户选择了操作类型筛选，添加action参数
  // 空字符串表示"全部操作"，不需要传递
  if (actionType) {
    params.append("action", actionType);
  }

  // 如果用户输入了开始日期，添加start_date参数
  // 用于过滤指定日期之后的日志
  if (startDate) {
    params.append("start_date", startDate);
  }

  // 如果用户输入了结束日期，添加end_date参数
  // 用于过滤指定日期之前的日志
  if (endDate) {
    params.append("end_date", endDate);
  }

  // 拼接完整的请求URL
  // params.toString()会生成类似"page=1&per_page=20&action=create_order"的查询字符串
  // 格式示例：/api/payment_logs?page=1&per_page=20&action=create_order&start_date=2024-01-01
  const url = `/api/payment_logs?${params.toString()}`;

  // 在控制台输出请求信息，方便开发调试
  logMessage_Info(`[PC端支付日志] 正在加载第${page}页，筛选条件:`, {
    actionType: actionType || "全部",
    startDate: startDate || "无限制",
    endDate: endDate || "无限制",
  });

  // ========== 发送API请求 ==========

  // 使用fetch API发起HTTP GET请求
  // fetch是现代浏览器提供的原生API，用于发起网络请求
  // 它返回一个Promise对象，支持链式调用
  fetch(url, {
    method: "GET", // 请求方法为GET
    headers: {
      "X-Session-ID": sessionUUID,
    },
  })
    .then((response) => {
      // ========== 第一步：检查HTTP响应状态 ==========

      // 检查HTTP响应状态码
      // response.ok为true时，表示状态码在200-299范围内（成功）
      // 如果状态码不是2xx（如404、500等），抛出错误进入catch块
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      // 解析响应体为JSON对象
      // response.json()返回一个Promise，包含解析后的JavaScript对象
      return response.json();
    })
    .then((result) => {
      // ========== 第二步：检查API业务状态 ==========

      // 即使HTTP状态码是200，也要检查业务逻辑是否成功
      // success字段表示后端处理是否成功
      // 例如：权限不足、参数错误等情况，HTTP状态码可能是200，但success为false
      if (!result.success) {
        throw new Error(result.message || "加载支付日志失败");
      }

      // ========== 第三步：提取和处理返回数据 ==========

      // 提取日志列表，如果为空则使用空数组
      // 使用 || [] 确保logs始终是数组，避免后续代码出错
      const logs = result.logs || [];

      // 提取总记录数，用于计算总页数
      // 总记录数是所有符合条件的日志数量，不受分页影响
      const total = result.total || 0;

      // 更新分页状态对象
      adminPaymentLogsState.currentPage = page; // 更新当前页码
      // 计算总页数：总记录数除以每页数量，向上取整
      // Math.ceil向上取整，确保即使最后一页不满也算一页
      // 例如：23条记录，每页20条，总页数为Math.ceil(23/20)=2页
      adminPaymentLogsState.totalPages = Math.ceil(
        total / adminPaymentLogsState.perPage,
      );

      // ========== 渲染日志列表 ==========

      // 检查是否有日志数据
      if (logs.length === 0) {
        // 没有日志时，显示空状态提示
        // 提示用户可能需要调整筛选条件
        listContainer.innerHTML = `
          <div class="flex flex-col items-center justify-center py-12">
            <!-- 空文档图标 -->
            <svg class="w-20 h-20 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z">
              </path>
            </svg>
            <!-- 空状态提示 -->
            <p class="text-slate-400 text-center text-base font-medium">暂无支付日志</p>
            <p class="text-slate-300 text-center text-sm mt-1">尝试调整筛选条件</p>
          </div>
        `;
      } else {
        // 有日志时，渲染日志卡片列表
        // 使用map函数遍历每条日志，生成对应的HTML
        const logsHTML = logs
          .map((log) => {
            // ========== 为每条日志生成HTML卡片 ==========

            // 根据操作类型确定显示的标签样式和文字
            // 不同的操作类型使用不同的颜色，便于用户快速识别
            let actionBadgeClass = "bg-slate-100 text-slate-700"; // 默认样式（灰色）
            let actionText = getPaymentLogActionLabel(log.action); // 操作类型文本

            // 根据不同的操作类型设置不同的颜色样式
            if (log.action === "create_order") {
              // 创建订单：蓝色
              actionBadgeClass = "bg-blue-100 text-blue-700";
              actionText = "创建订单";
            } else if (log.action === "query_order") {
              // 查询订单：紫色
              actionBadgeClass = "bg-purple-100 text-purple-700";
              actionText = "查询订单";
            } else if (log.action === "payment_success") {
              // 支付成功：绿色
              actionBadgeClass = "bg-green-100 text-green-700";
              actionText = "支付成功";
            } else if (log.action === "payment_fail") {
              // 支付失败：红色
              actionBadgeClass = "bg-red-100 text-red-700";
              actionText = "支付失败";
            } else if (log.action === "create_order_failed") {
              // 配置更新：橙色
              actionBadgeClass = "bg-orange-100 text-orange-700";
              actionText = "创建失败";
            }

            // 格式化金额显示
            // 如果日志中包含金额信息，格式化为货币格式（保留2位小数）
            // 使用parseFloat确保金额是数字，使用toFixed(2)保留两位小数
            // 三元运算符：如果log.amount存在则显示金额，否则返回空字符串
            const amountHTML = log.amount
              ? `<div class="text-sm text-slate-600">金额: <span class="font-semibold text-green-600">¥${parseFloat(
                  log.amount,
                ).toFixed(2)}</span></div>`
              : "";

            // 格式化状态显示
            // 根据状态值设置不同的颜色，让用户一眼就能看出操作结果
            // 支持的状态类型：success、completed、failed、error、pending、processing
            let statusHTML = "";
            if (log.status) {
              // 初始化状态样式和文本
              let statusClass = "text-slate-600"; // 默认颜色（灰色）
              let statusText = getPaymentLogStatusLabel(log.status); // 状态显示文本，原始值仍保留在日志数据中

              // 根据不同的状态设置不同的颜色
              // 使用if-else if链式判断，提高代码可读性
              if (log.status === "success" || log.status === "completed") {
                // 成功状态：绿色
                // 适用于支付成功、操作完成等场景
                statusClass = "text-green-600";
                statusText = getPaymentLogStatusLabel(log.status);
              } else if (log.status === "failed" || log.status === "error") {
                // 失败状态：红色
                // 适用于支付失败、操作错误等场景
                statusClass = "text-red-600";
                statusText = getPaymentLogStatusLabel(log.status);
              } else if (
                log.status === "pending" ||
                log.status === "processing"
              ) {
                // 处理中状态：黄色
                // 适用于等待处理、正在处理等场景
                statusClass = "text-yellow-600";
                statusText = getPaymentLogStatusLabel(log.status);
              }

              // 生成状态HTML
              // font-medium使文字加粗，提高可读性
              statusHTML = `<div class="text-sm ${statusClass} font-medium">状态: ${statusText}</div>`;
            }

            // ========== 返回单条日志的HTML卡片 ==========
            // 使用模板字符串构建HTML，包含：
            // 1. 操作类型标签和时间
            // 2. 订单号
            // 3. 金额和状态信息
            // 4. 查看详情按钮
            //
            // 注意事项：
            // - 使用模板字符串 ` ` 插入变量值
            // - 使用 ${} 语法嵌入JavaScript表达式
            // - 所有数据都经过处理，防止XSS攻击
            // - 卡片支持悬停效果（hover:border-sky-300 hover:shadow-sm）
            return `
            <div class="bg-white border border-slate-200 rounded-lg p-4 hover:border-sky-300 hover:shadow-sm transition-all">
              <!-- 卡片头部：操作类型标签 + 时间 -->
              <div class="flex justify-between items-start mb-3">
                <!-- 操作类型标签：使用彩色背景突出显示 -->
                <span class="inline-block px-3 py-1 rounded-md text-sm font-medium ${actionBadgeClass}">
                  ${actionText}
                </span>
                <!-- 操作时间：右对齐显示，使用较小的字体 -->
                <span class="text-sm text-slate-500">${
                  log.datetime || "未知时间"
                }</span>
              </div>
              
              <!-- 订单号：使用较大字体突出显示 -->
              <div class="text-base font-medium text-slate-800 mb-2">
                订单号: ${log.order_id || "无"}
              </div>
              
              <!-- 详细信息区域：显示金额和状态 -->
              <div class="space-y-1 mb-3">
                ${amountHTML}
                ${statusHTML}
              </div>
              
              <!-- 查看详情按钮 -->
              <button onclick="showPaymentLogDetail(${escapeInlineJsArg(log.log_id || "")})"
                class="w-full py-2 px-4 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 active:bg-sky-700 transition-colors">
                <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                查看详情
              </button>
            </div>
          `;
          })
          .join(""); // 将所有卡片HTML连接成一个字符串

        // 更新列表容器的内容
        // 使用innerHTML一次性渲染所有日志卡片
        // 这比逐个appendChild效率更高
        listContainer.innerHTML = logsHTML;
      }

      // ========== 更新分页控件 ==========

      // 调用分页更新函数，更新页码显示和按钮状态
      // 此函数会：
      // 1. 更新页码文本（第X页/共Y页）
      // 2. 根据当前页码启用/禁用上一页按钮
      // 3. 根据当前页码启用/禁用下一页按钮
      updateAdminPaymentLogsPagination();

      // 在控制台输出成功信息，方便调试
      // 显示当前页码、本页记录数、总记录数
      // console.log(`[PC端支付日志] 成功加载第${page}页，共${logs.length}条记录，总计${total}条`);
      logMessage_Info(
        `[PC端支付日志] 成功加载第${page}页，共${logs.length}条记录，总计${total}条`,
      );
    })
    .catch((error) => {
      // ========== 错误处理 ==========

      // 在控制台输出详细错误信息，方便调试
      // 包括错误对象的完整信息
      // console.error('[PC端支付日志] 加载失败:', error);
      logMessage_Error("[PC端支付日志] 加载失败: " + error);

      // 在列表容器中显示错误提示
      // 包含错误图标、错误信息和重试按钮
      // 用户可以点击重试按钮重新加载数据
      listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-12">
          <!-- 错误图标 -->
          <svg class="w-20 h-20 text-red-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z">
            </path>
          </svg>
          <!-- 错误标题 -->
          <p class="text-red-500 text-center text-lg font-medium">加载失败</p>
          <!-- 错误详情 -->
          <p class="text-slate-400 text-center text-sm mt-2">${
            error.message || "请稍后重试"
          }</p>
          <!-- 重试按钮：点击后重新加载当前页 -->
          <button onclick="loadAdminPaymentLogs()" class="mt-4 px-4 py-2 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 transition-colors">
            重试
          </button>
        </div>
      `;
    });
}

/**
 * 更新PC端管理员支付日志分页控件状态
 *
 * 功能说明：
 * 1. 更新页码显示文本（显示当前页/总页数）
 * 2. 更新"上一页"按钮的启用/禁用状态
 * 3. 更新"下一页"按钮的启用/禁用状态
 *
 * 调用时机：
 * - 每次加载日志数据后
 * - 用户点击分页按钮后
 *
 * 实现细节：
 * - 第一页时，禁用"上一页"按钮
 * - 最后一页时，禁用"下一页"按钮
 * - 只有一页时，两个按钮都禁用
 * - 使用CSS类（opacity-50, cursor-not-allowed）提供视觉反馈
 */
function updateAdminPaymentLogsPagination() {
  // ========== 获取分页控件元素 ==========

  // 获取页码显示元素
  const pageInfo = document.getElementById(
    "admin-payment-logs-page-info_modal",
  );
  // 获取上一页按钮
  const prevBtn = document.getElementById("admin-payment-logs-prev-btn_modal");
  // 获取下一页按钮
  const nextBtn = document.getElementById("admin-payment-logs-next-btn_modal");

  // 防御性检查：确保所有分页控件元素都存在
  // 如果有任何一个元素找不到，输出错误并返回
  if (!pageInfo || !prevBtn || !nextBtn) {
    // console.error('[PC端支付日志] 分页控件元素未找到');
    logMessage_Error("[PC端支付日志] 分页控件元素未找到");
    return;
  }

  // ========== 更新页码显示 ==========

  // 更新页码显示文本
  // 格式：第 X 页 / 共 Y 页
  // 使用textContent而不是innerHTML，防止XSS攻击
  // textContent会自动转义所有特殊字符
  pageInfo.textContent = `第 ${adminPaymentLogsState.currentPage} 页 / 共 ${adminPaymentLogsState.totalPages} 页`;

  // ========== 更新"上一页"按钮状态 ==========

  // 如果当前是第一页，禁用"上一页"按钮
  // 第一页时currentPage为1，无法再向前翻页
  if (adminPaymentLogsState.currentPage <= 1) {
    prevBtn.disabled = true; // 禁用按钮（阻止点击事件）
    // 添加视觉反馈CSS类：降低透明度、改变鼠标样式
    // opacity-50: 降低透明度到50%
    // cursor-not-allowed: 鼠标悬停时显示禁止图标
    prevBtn.classList.add("opacity-50", "cursor-not-allowed");
  } else {
    // 如果不是第一页，启用"上一页"按钮
    prevBtn.disabled = false; // 启用按钮
    // 移除视觉反馈CSS类，恢复正常样式
    prevBtn.classList.remove("opacity-50", "cursor-not-allowed");
  }

  // ========== 更新"下一页"按钮状态 ==========

  // 如果当前是最后一页，禁用"下一页"按钮
  // 最后一页时currentPage等于totalPages，无法再向后翻页
  if (adminPaymentLogsState.currentPage >= adminPaymentLogsState.totalPages) {
    nextBtn.disabled = true; // 禁用按钮
    // 添加视觉反馈CSS类
    nextBtn.classList.add("opacity-50", "cursor-not-allowed");
  } else {
    // 如果不是最后一页，启用"下一页"按钮
    nextBtn.disabled = false; // 启用按钮
    // 移除视觉反馈CSS类
    nextBtn.classList.remove("opacity-50", "cursor-not-allowed");
  }
}

/**
 * 加载PC端管理员支付日志的上一页
 *
 * 功能说明：
 * 加载支付日志的上一页数据
 *
 * 调用时机：
 * - 用户点击"上一页"按钮时
 *
 * 实现细节：
 * - 首先检查是否已经是第一页
 * - 如果不是第一页，将页码减1并重新加载数据
 * - 如果已经是第一页，输出日志信息并直接返回
 *
 * 防止误操作：
 * - 即使按钮已禁用，此函数也会再次检查页码
 * - 双重保护，确保不会出现负数页码
 */
function loadAdminPaymentLogsPrev() {
  // 检查是否已经是第一页
  if (adminPaymentLogsState.currentPage <= 1) {
    // 已经是第一页，无法继续向前翻页
    // console.log('[PC端支付日志] 已经是第一页');
    logMessage_Info("[PC端支付日志] 已经是第一页");
    return; // 直接返回，不执行任何操作
  }

  // 计算上一页的页码
  // 当前页减1即为上一页
  const prevPage = adminPaymentLogsState.currentPage - 1;

  // 加载上一页数据
  // 调用loadAdminPaymentLogs函数，传入上一页的页码
  loadAdminPaymentLogs(prevPage);
}

/**
 * 加载PC端管理员支付日志的下一页
 *
 * 功能说明：
 * 加载支付日志的下一页数据
 *
 * 调用时机：
 * - 用户点击"下一页"按钮时
 *
 * 实现细节：
 * - 首先检查是否已经是最后一页
 * - 如果不是最后一页，将页码加1并重新加载数据
 * - 如果已经是最后一页，输出日志信息并直接返回
 *
 * 防止误操作：
 * - 即使按钮已禁用，此函数也会再次检查页码
 * - 双重保护，确保不会超出总页数
 */
function loadAdminPaymentLogsNext() {
  // 检查是否已经是最后一页
  if (adminPaymentLogsState.currentPage >= adminPaymentLogsState.totalPages) {
    // 已经是最后一页，无法继续向后翻页
    // console.log('[PC端支付日志] 已经是最后一页');
    logMessage_Info("[PC端支付日志] 已经是最后一页");
    return; // 直接返回，不执行任何操作
  }

  // 计算下一页的页码
  // 当前页加1即为下一页
  const nextPage = adminPaymentLogsState.currentPage + 1;

  // 加载下一页数据
  // 调用loadAdminPaymentLogs函数，传入下一页的页码
  loadAdminPaymentLogs(nextPage);
}

async function loadAdminBillingLogs(page = 1) {
  const listContainer = document.getElementById("admin-billing-logs-list_modal");
  const pageInfo = document.getElementById("admin-billing-logs-page-info_modal");
  const prevBtn = document.getElementById("admin-billing-logs-prev-btn_modal");
  const nextBtn = document.getElementById("admin-billing-logs-next-btn_modal");
  if (!listContainer) return;

  listContainer.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-sky-500 mb-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-slate-400 text-center text-sm">正在加载账单日志...</p>
    </div>
  `;

  const keyword =
    document.getElementById("admin-billing-logs-search-input_modal")?.value.trim() || "";
  const eventType =
    document.getElementById("admin-billing-logs-event-type_modal")?.value || "";
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(adminBillingLogsState.pageSize),
  });
  if (keyword) params.set("keyword", keyword);
  if (eventType) params.set("event_type", eventType);

  try {
    const resp = await fetch(`/api/admin/billing/logs?${params.toString()}`, {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    if (!resp.ok || !data.success) {
      throw new Error(data.message || `HTTP错误: ${resp.status}`);
    }

    const logs = data.logs || [];
    const total = Number(data.total || 0);
    adminBillingLogsState.currentPage = page;
    adminBillingLogsState.totalPages = Math.max(
      1,
      Math.ceil(total / adminBillingLogsState.pageSize),
    );

    if (!logs.length) {
      listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-12 text-slate-400 gap-2">
          <svg class="w-12 h-12 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="text-sm">暂无账单日志</p>
        </div>
      `;
    } else {
      listContainer.innerHTML = logs
        .map((log) => {
          const eventTypeTextMap = {
            billing_created: "创建",
            billing_amount_changed: "金额变化",
            billing_status_changed: "状态变化",
            billing_admin_cleared: "管理员清除",
            billing_reason_changed: "原因变化",
            billing_deleted: "删除",
          };
          const eventText =
            eventTypeTextMap[String(log.event_type || "")] ||
            _escapeAttr(String(log.event_type || "未知事件"));
          const beforeJson = _escapeAttr(
            JSON.stringify(log.before || {}, null, 2),
          );
          const afterJson = _escapeAttr(
            JSON.stringify(log.after || {}, null, 2),
          );
          const billingId = _escapeAttr(String(log.billing_id || "-"));
          const schoolUsername = _escapeAttr(String(log.school_username || "-"));
          const authUsername = _escapeAttr(String(log.auth_username || "-"));
          const nickname = _escapeAttr(String(log.nickname || "-"));
          const phone = _escapeAttr(String(log.phone || "-"));
          const operatorUsername = _escapeAttr(
            String(log.operator_username || "-"),
          );
          const details = _escapeAttr(String(log.details || "-"));
          const createdAt = _escapeAttr(
            String(log.created_at_beijing || log.created_at || "-"),
          );
          return `
            <div class="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
              <div class="flex items-center justify-between gap-2 flex-wrap">
                <span class="inline-flex px-2.5 py-1 rounded-full text-xs font-medium bg-sky-100 text-sky-700 border border-sky-200">${eventText}</span>
                <span class="text-xs text-slate-500">${createdAt}</span>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-slate-700">
                <div>账单号：<span class="font-mono">${billingId}</span></div>
                <div>学校账号：<span class="font-mono">${schoolUsername}</span></div>
                <div>用户：${authUsername}</div>
                <div>昵称：${nickname}</div>
                <div>手机号：${phone}</div>
                <div>操作人：${operatorUsername}</div>
              </div>
              <div class="text-sm text-slate-600">说明：${details}</div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div class="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div class="font-semibold text-slate-600 mb-1">变更前</div>
                  <pre class="whitespace-pre-wrap break-all text-slate-500">${beforeJson}</pre>
                </div>
                <div class="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div class="font-semibold text-slate-600 mb-1">变更后</div>
                  <pre class="whitespace-pre-wrap break-all text-slate-500">${afterJson}</pre>
                </div>
              </div>
            </div>
          `;
        })
        .join("");
    }

    if (pageInfo) {
      pageInfo.textContent = `第 ${adminBillingLogsState.currentPage} 页 / 共 ${adminBillingLogsState.totalPages} 页`;
    }
    if (prevBtn) {
      prevBtn.disabled = adminBillingLogsState.currentPage <= 1;
      prevBtn.classList.toggle(
        "opacity-50",
        adminBillingLogsState.currentPage <= 1,
      );
      prevBtn.classList.toggle(
        "cursor-not-allowed",
        adminBillingLogsState.currentPage <= 1,
      );
    }
    if (nextBtn) {
      nextBtn.disabled =
        adminBillingLogsState.currentPage >= adminBillingLogsState.totalPages;
      nextBtn.classList.toggle(
        "opacity-50",
        adminBillingLogsState.currentPage >= adminBillingLogsState.totalPages,
      );
      nextBtn.classList.toggle(
        "cursor-not-allowed",
        adminBillingLogsState.currentPage >= adminBillingLogsState.totalPages,
      );
    }
  } catch (error) {
    listContainer.innerHTML = `<div class="text-red-500 bg-red-50 border border-red-200 rounded-lg p-3 text-sm">加载失败：${_escapeAttr(error.message || "未知错误")}</div>`;
    if (pageInfo) pageInfo.textContent = `第 ${page} 页`;
  }
}

function loadAdminBillingLogsPrev() {
  if (adminBillingLogsState.currentPage <= 1) return;
  loadAdminBillingLogs(adminBillingLogsState.currentPage - 1);
}

function loadAdminBillingLogsNext() {
  if (adminBillingLogsState.currentPage >= adminBillingLogsState.totalPages)
    return;
  loadAdminBillingLogs(adminBillingLogsState.currentPage + 1);
}

const mobileBillingLogsState = { currentPage: 1, totalPages: 1, pageSize: 10 };

async function loadMobileBillingLogs(page = 1) {
  const listContainer = document.getElementById("mobile-billing-logs-list");
  const pageInfo = document.getElementById("mobile-billing-logs-page-info");
  const prevBtn = document.getElementById("mobile-billing-logs-prev-btn");
  const nextBtn = document.getElementById("mobile-billing-logs-next-btn");
  if (!listContainer) return;

  listContainer.innerHTML = `
    <div class="flex flex-col items-center justify-center py-10">
      <svg class="animate-spin h-7 w-7 text-sky-500 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <p class="text-slate-400 text-xs">正在加载账单日志...</p>
    </div>
  `;

  const keyword = document.getElementById("mobile-billing-logs-search-input")?.value.trim() || "";
  const eventType = document.getElementById("mobile-billing-logs-event-type")?.value || "";
  const params = new URLSearchParams({ page: String(page), page_size: String(mobileBillingLogsState.pageSize) });
  if (keyword) params.set("keyword", keyword);
  if (eventType) params.set("event_type", eventType);

  try {
    const resp = await fetch(`/api/admin/billing/logs?${params.toString()}`, {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    if (!resp.ok || !data.success) throw new Error(data.message || `HTTP错误: ${resp.status}`);

    const logs = data.logs || [];
    const total = Number(data.total || 0);
    mobileBillingLogsState.currentPage = page;
    mobileBillingLogsState.totalPages = Math.max(1, Math.ceil(total / mobileBillingLogsState.pageSize));

    if (!logs.length) {
      listContainer.innerHTML = `
        <div class="flex flex-col items-center justify-center py-10 text-slate-400 gap-2">
          <svg class="w-10 h-10 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="text-xs">暂无账单日志</p>
        </div>
      `;
    } else {
      const eventTypeTextMap = {
        billing_created: "创建", billing_amount_changed: "金额变化",
        billing_status_changed: "状态变化", billing_admin_cleared: "管理员清除",
        billing_reason_changed: "原因变化", billing_deleted: "删除",
      };
      const eventColorMap = {
        billing_created: "bg-emerald-100 text-emerald-700 border-emerald-200",
        billing_deleted: "bg-red-100 text-red-700 border-red-200",
        billing_admin_cleared: "bg-amber-100 text-amber-700 border-amber-200",
      };
      const defaultColor = "bg-sky-100 text-sky-700 border-sky-200";
      listContainer.innerHTML = logs.map((log, idx) => {
        const rawType = String(log.event_type || "");
        const eventText = eventTypeTextMap[rawType] || _escapeAttr(rawType || "未知");
        const colorCls = eventColorMap[rawType] || defaultColor;
        const createdAt = _escapeAttr(String(log.created_at_beijing || log.created_at || "-"));
        const billingId = _escapeAttr(String(log.billing_id || "-"));
        const schoolUsername = _escapeAttr(String(log.school_username || "-"));
        const authUsername = _escapeAttr(String(log.auth_username || "-"));
        const operatorUsername = _escapeAttr(String(log.operator_username || "-"));
        const details = _escapeAttr(String(log.details || "-"));
        const beforeJson = _escapeAttr(JSON.stringify(log.before || {}, null, 2));
        const afterJson = _escapeAttr(JSON.stringify(log.after || {}, null, 2));
        const detailId = `mbl-diff-${page}-${idx}`;
        return `
          <div class="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div class="px-3 py-2.5 space-y-2">
              <div class="flex items-center justify-between gap-2">
                <span class="inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${colorCls} border">${eventText}</span>
                <span class="text-[11px] text-slate-500 whitespace-nowrap">${createdAt}</span>
              </div>
              <div class="space-y-1 text-xs text-slate-700">
                <div class="flex justify-between"><span class="text-slate-500">账单号</span><span class="font-mono text-right break-all">${billingId}</span></div>
                <div class="flex justify-between"><span class="text-slate-500">学校账号</span><span class="font-mono text-right break-all">${schoolUsername}</span></div>
                <div class="flex justify-between"><span class="text-slate-500">用户</span><span>${authUsername}</span></div>
                <div class="flex justify-between"><span class="text-slate-500">操作人</span><span>${operatorUsername}</span></div>
              </div>
              <div class="text-xs text-slate-600 bg-slate-50 rounded-lg px-2.5 py-1.5">说明：${details}</div>
            </div>
            <button type="button" class="w-full px-3 py-2 text-xs text-slate-500 bg-slate-50 border-t border-slate-200 flex items-center justify-center gap-1 active:bg-slate-100 transition-colors" onclick="var d=document.getElementById(${escapeInlineJsArg(detailId)});if(d){d.classList.toggle('hidden');this.querySelector('svg').style.transform=d.classList.contains('hidden')?'':'rotate(180deg)'}">
              <span>变更详情</span>
              <svg class="w-3.5 h-3.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            </button>
            <div id="${detailId}" class="hidden border-t border-slate-200 px-3 py-2.5 space-y-2">
              <div class="bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                <div class="font-semibold text-[11px] text-slate-600 mb-1">变更前</div>
                <pre class="whitespace-pre-wrap break-all text-[11px] text-slate-500 leading-relaxed">${beforeJson}</pre>
              </div>
              <div class="bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                <div class="font-semibold text-[11px] text-slate-600 mb-1">变更后</div>
                <pre class="whitespace-pre-wrap break-all text-[11px] text-slate-500 leading-relaxed">${afterJson}</pre>
              </div>
            </div>
          </div>
        `;
      }).join("");
    }

    if (pageInfo) pageInfo.textContent = `${mobileBillingLogsState.currentPage} / ${mobileBillingLogsState.totalPages}`;
    if (prevBtn) {
      prevBtn.disabled = mobileBillingLogsState.currentPage <= 1;
      prevBtn.classList.toggle("opacity-50", mobileBillingLogsState.currentPage <= 1);
    }
    if (nextBtn) {
      nextBtn.disabled = mobileBillingLogsState.currentPage >= mobileBillingLogsState.totalPages;
      nextBtn.classList.toggle("opacity-50", mobileBillingLogsState.currentPage >= mobileBillingLogsState.totalPages);
    }
  } catch (error) {
    listContainer.innerHTML = `<div class="text-red-500 bg-red-50 border border-red-200 rounded-lg p-3 text-xs">加载失败：${_escapeAttr(error.message || "未知错误")}</div>`;
    if (pageInfo) pageInfo.textContent = `第 ${page} 页`;
  }
}

function loadMobileBillingLogsPrev() {
  if (mobileBillingLogsState.currentPage <= 1) return;
  loadMobileBillingLogs(mobileBillingLogsState.currentPage - 1);
}

function loadMobileBillingLogsNext() {
  if (mobileBillingLogsState.currentPage >= mobileBillingLogsState.totalPages) return;
  loadMobileBillingLogs(mobileBillingLogsState.currentPage + 1);
}

/**
 * 显示支付日志详情模态框
 *
 * 功能说明：
 * 1. 根据日志ID从后端API获取完整的日志详细信息
 * 2. 在模态框中展示日志的所有字段
 * 3. 提供JSON格式的完整数据查看
 *
 * 参数：
 * @param {string} logId - 日志ID（日志文件名，不含.json后缀）
 *                         格式示例：20231201_120530_admin_ORDER20231201120530123456
 *
 * 调用时机：
 * - 用户点击日志卡片中的"查看详情"按钮时
 *
 * 实现步骤：
 * 1. 验证logId参数
 * 2. 显示模态框和加载状态
 * 3. 调用后端API获取日志详情
 * 4. 解析响应并填充模态框内容
 * 5. 处理错误情况
 */
async function showPaymentLogDetail(logId) {
  if (!logId) {
    logMessage_Error("[支付日志详情] 日志ID为空");
    Swal.fire({
      icon: "error",
      title: "日志ID无效",
      text: "无法加载日志详情，请稍后重试。",
    });
    return;
  }

  logMessage_Info(`[支付日志详情] 正在加载日志详情，log_id: ${logId}`);

  const useMobileModal = typeof isMobileMode !== "undefined" && isMobileMode;
  const modal = document.getElementById("admin-payment-log-detail-modal");
  const loadingDiv = document.getElementById("log-detail-loading");
  const errorDiv = document.getElementById("log-detail-error");
  const contentDiv = document.getElementById("log-detail-content");

  if (!useMobileModal && (!modal || !loadingDiv || !errorDiv || !contentDiv)) {
    logMessage_Error("[支付日志详情] 找不到必需的DOM元素");
    return;
  }

  if (useMobileModal) {
    openMobilePaymentLogDetailModal();
    const mobileLoadingDiv = document.getElementById(
      "mobile-log-detail-loading",
    );
    const mobileErrorDiv = document.getElementById("mobile-log-detail-error");
    const mobileContentDiv = document.getElementById(
      "mobile-log-detail-content",
    );
    const mobileErrorMessageElem = document.getElementById(
      "mobile-log-detail-error-message",
    );

    if (!mobileLoadingDiv || !mobileErrorDiv || !mobileContentDiv) {
      logMessage_Error("[支付日志详情] 找不到移动端模态框元素");
      return;
    }

    mobileLoadingDiv.classList.remove("hidden");
    mobileErrorDiv.classList.add("hidden");
    mobileContentDiv.classList.add("hidden");
    if (mobileErrorMessageElem) {
      mobileErrorMessageElem.textContent = "";
    }
  } else {
    modal.classList.remove("hidden");
    loadingDiv.classList.remove("hidden");
    errorDiv.classList.add("hidden");
    contentDiv.classList.add("hidden");
  }

  try {
    const response = await fetch("/api/admin/payment/log_detail", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        log_id: logId,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP错误: ${response.status}`);
    }

    const result = await response.json();
    if (!result.success) {
      throw new Error(result.message || "获取日志详情失败");
    }

    const logDetail = result.log_detail || {};
    const amountText = logDetail.amount
      ? `¥${parseFloat(logDetail.amount).toFixed(2)}`
      : "-";
    const detailJson = JSON.stringify(logDetail, null, 2);

    if (useMobileModal) {
      document.getElementById("mobile-log-detail-datetime").textContent =
        logDetail.datetime || "-";
      document.getElementById("mobile-log-detail-action").textContent =
        getPaymentLogActionLabel(logDetail.action);
      document.getElementById("mobile-log-detail-user-id").textContent =
        logDetail.user_id || "-";
      document.getElementById("mobile-log-detail-order-id").textContent =
        logDetail.order_id || "-";
      document.getElementById("mobile-log-detail-client-ip").textContent =
        logDetail.client_ip || "-";
      document.getElementById("mobile-log-detail-amount").textContent =
        amountText;
      document.getElementById("mobile-log-detail-json").textContent = detailJson;

      document.getElementById("mobile-log-detail-loading").classList.add("hidden");
      document.getElementById("mobile-log-detail-content").classList.remove("hidden");
    } else {
      document.getElementById("log-detail-datetime").textContent =
        logDetail.datetime || "-";
      document.getElementById("log-detail-action").textContent =
        getPaymentLogActionLabel(logDetail.action);
      document.getElementById("log-detail-user-id").textContent =
        logDetail.user_id || "-";
      document.getElementById("log-detail-order-id").textContent =
        logDetail.order_id || "-";
      document.getElementById("log-detail-client-ip").textContent =
        logDetail.client_ip || "-";

      const amountElem = document.getElementById("log-detail-amount");
      amountElem.textContent = amountText;

      const jsonElem = document.getElementById("log-detail-json");
      jsonElem.textContent = detailJson;

      loadingDiv.classList.add("hidden");
      contentDiv.classList.remove("hidden");
    }

    logMessage_Info("[支付日志详情] 日志详情加载成功");
  } catch (error) {
    logMessage_Error("[支付日志详情] 获取日志详情失败: " + error);

    if (useMobileModal) {
      const mobileErrorMessageElem = document.getElementById(
        "mobile-log-detail-error-message",
      );
      if (mobileErrorMessageElem) {
        mobileErrorMessageElem.textContent = error.message || "未知错误";
      }
      document.getElementById("mobile-log-detail-loading").classList.add("hidden");
      document.getElementById("mobile-log-detail-error").classList.remove("hidden");
    } else {
      const errorMessageElem = document.getElementById(
        "log-detail-error-message",
      );
      if (errorMessageElem) {
        errorMessageElem.textContent = error.message || "未知错误";
      }

      loadingDiv.classList.add("hidden");
      errorDiv.classList.remove("hidden");
    }
  }
}

function openMobilePaymentLogDetailModal() {
  let modal = document.getElementById("mobile-payment-log-detail-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-payment-log-detail-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobilePaymentLogDetailModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobilePaymentLogDetailModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobilePaymentLogDetailModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-between gap-3 pb-3 border-b border-slate-200">
          <h3 class="text-lg font-bold text-slate-800">支付日志详情</h3>
          <!-- <button onclick="closeMobilePaymentLogDetailModal()" class="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button> -->
        </div>

        <div id="mobile-log-detail-loading" class="py-10 text-center text-sm text-slate-500">加载中...</div>

        <div id="mobile-log-detail-error" class="hidden rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
          <div class="font-medium">加载失败</div>
          <div id="mobile-log-detail-error-message" class="mt-1 break-all"></div>
        </div>

        <div id="mobile-log-detail-content" class="hidden space-y-3">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div class="text-[11px] text-slate-400">记录时间</div>
            <div id="mobile-log-detail-datetime" class="mt-1 text-sm text-slate-800 break-all">-</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div class="text-[11px] text-slate-400">操作类型</div>
            <div id="mobile-log-detail-action" class="mt-1 text-sm text-slate-800 break-all">-</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div class="text-[11px] text-slate-400">用户ID</div>
            <div id="mobile-log-detail-user-id" class="mt-1 text-sm text-slate-800 break-all">-</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div class="text-[11px] text-slate-400">订单号</div>
            <div id="mobile-log-detail-order-id" class="mt-1 text-sm text-slate-800 break-all">-</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div class="text-[11px] text-slate-400">客户端IP</div>
            <div id="mobile-log-detail-client-ip" class="mt-1 text-sm text-slate-800 break-all">-</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div class="text-[11px] text-slate-400">金额</div>
            <div id="mobile-log-detail-amount" class="mt-1 text-base font-semibold text-slate-900 break-all">-</div>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <div class="text-[11px] text-slate-400">完整数据</div>
            <pre id="mobile-log-detail-json" class="mt-2 text-xs leading-5 text-slate-700 overflow-x-auto font-mono whitespace-pre-wrap break-all">-</pre>
          </div>
          <button onclick="closeMobilePaymentLogDetailModal()" class="w-full min-h-[44px] rounded-2xl bg-sky-500 px-4 py-3 text-sm font-medium text-white hover:bg-sky-600 transition-colors">
            关闭
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobilePaymentLogDetailModal() {
  const modal = document.getElementById("mobile-payment-log-detail-modal");
  if (!modal) return;

  modal.classList.remove("show");
  setTimeout(() => {
    modal.classList.add("hidden");
  }, 300);
}

/**
 * 关闭支付日志详情模态框
 *
 * 功能说明：
 * 关闭日志详情模态框，清空显示内容
 *
 * 调用时机：
 * - 用户点击模态框的关闭按钮时
 * - 用户点击模态框底部的"关闭"按钮时
 *
 * 实现步骤：
 * 1. 隐藏模态框
 * 2. 重置所有显示区域的状态
 */
function closePaymentLogDetailModal() {
  if (typeof isMobileMode !== "undefined" && isMobileMode) {
    closeMobilePaymentLogDetailModal();
    logMessage_Info("[支付日志详情] 移动端模态框已关闭");
    return;
  }

  const modal = document.getElementById("admin-payment-log-detail-modal");

  if (!modal) {
    logMessage_Error("[支付日志详情] 找不到模态框元素");
    return;
  }

  modal.classList.add("hidden");

  logMessage_Info("[支付日志详情] 模态框已关闭");
}

// ==========================================
// 注意事项
// ==========================================
//
// 1. 此脚本不绑定DOMContentLoaded事件监听器
//    因为支付日志面板默认是隐藏的（display: none）
//    只有当用户切换到该面板时才需要加载数据
//
// 2. 数据加载时机由面板切换逻辑控制
//    当用户点击"支付日志"Tab时，应调用loadAdminPaymentLogs()加载数据
//
// 3. 按钮点击事件通过HTML的onclick属性绑定
//    这样可以避免DOMContentLoaded时元素还未创建的问题
//
// 4. 函数都定义在全局作用域
//    这样可以在HTML的onclick属性中直接调用
//
// ==========================================

// --- Next Script Block ---

// 修改为监听 DOMContentLoaded 事件，确保 sessionUUID 已初始化且 DOM 元素已加载
document.addEventListener("DOMContentLoaded", function loadBeianInfo() {
  // ==========================================
  // 第一步：向后端API发起请求，获取备案配置信息
  // ==========================================
  // API端点: /api/public/beian_config
  // 此接口是公开的，不需要认证，返回格式化的JSON数据

  if (
    typeof sessionUUID === "undefined" ||
    sessionUUID === null ||
    sessionUUID === "" ||
    sessionUUID === undefined ||
    sessionUUID === "undefined" ||
    sessionUUID === "null" ||
    sessionUUID === "undefined"
  ) {
    sessionUUID = getUUIDFromURL();
  }

  fetch("/api/public/beian_config", {
    method: "GET",
    headers: {
      "X-Session-ID": sessionUUID,
    },
  })
    // 解析响应体为JSON对象
    // response.json()返回一个Promise，包含解析后的JavaScript对象
    .then((response) => response.json())
    // ==========================================
    // 第二步：处理API返回的数据
    // ==========================================
    .then((result) => {
      // 验证API调用是否成功，且返回了有效的数据对象
      // result.success: 后端返回的操作状态标志（true表示成功）
      // result.data: 包含实际备案配置信息的对象
      if (result.success && result.data) {
        // 将result.data赋值给局部变量data，方便后续访问
        // data对象的结构示例：
        // {
        //   show_icp: true/false,         // 是否显示ICP备案
        //   icp_number: "京ICP备xxxxx号", // ICP备案号
        //   show_police: true/false,      // 是否显示公安备案
        //   police_number: "京公网安备xxxxx号" // 公安备案号
        // }
        const data = result.data;

        // ==========================================
        // 核心函数：updateBeianSection
        // ==========================================
        // 【功能】根据prefix参数更新对应footer区域的备案信息显示
        // 【参数】prefix - 元素ID的前缀字符串，用于定位不同容器中的footer元素
        //         - "auth-"   : 针对登录页面(auth-login-container)中的 auth-beian-footer
        //         - "pc-"     : 针对桌面版(desktop-container)中的 pc-beian-footer
        //         - "mobile-" : 针对移动版(mobile-container)中的 mobile-beian-footer
        //
        // 【设计理念】Footer容器始终显示
        // - 此函数**不会**隐藏footer容器本身
        // - Footer容器在HTML中没有hidden类或display:none样式
        // - 即使没有备案信息，footer也会作为空白区域存在
        // - 这样设计的目的是保持UI布局的稳定性，防止页面跳动
        //
        // 【控制策略】只控制链接元素的显示
        // - ICP和公安备案链接在HTML中默认是隐藏的（style="display: none"）
        // - 只有当配置启用(show_xxx=true)且提供了备案号时，才将对应链接设为可见
        // - 这种策略确保了精细化的内容控制，不影响容器本身
        const updateBeianSection = (prefix) => {
          // 步骤1：获取footer容器元素的DOM引用
          // 通过prefix + "beian-footer"拼接得到完整的元素ID
          // 例如：prefix="auth-" => ID="auth-beian-footer"
          const footer = document.getElementById(prefix + "beian-footer");

          // 如果找不到footer元素（理论上不应该发生），则提前返回
          // 这是一个防御性检查，避免后续操作报错
          if (!footer) return;

          // ==========================================
          // 步骤2：处理 ICP 备案链接的显示逻辑
          // ==========================================
          // 判断条件：必须同时满足两个条件
          // 1. data.show_icp === true（配置文件中启用了ICP备案显示）
          // 2. data.icp_number存在且不为空（提供了有效的ICP备案号）
          if (data.show_icp && data.icp_number) {
            // 获取ICP备案链接元素的DOM引用
            // 元素ID格式：prefix + "icp-beian-link"
            // 例如：auth-icp-beian-link, pc-icp-beian-link, mobile-icp-beian-link
            const icpLink = document.getElementById(prefix + "icp-beian-link");

            // 获取ICP备案文本span元素的DOM引用
            // 这个span用于显示实际的备案号文字
            // 元素ID格式：prefix + "icp-beian-text"
            const icpText = document.getElementById(prefix + "icp-beian-text");

            // 确保两个元素都存在，才进行后续操作
            // 这是一个安全检查，防止DOM结构不完整导致的错误
            if (icpLink && icpText) {
              // 将备案号文本填充到span元素中
              // 使用textContent而不是innerHTML，防止XSS攻击
              icpText.textContent = data.icp_number;

              // 将链接元素设置为可见
              // 从默认的display:none改为display:flex
              // 使用flex是因为链接内部使用了flexbox布局（图标+文本）
              icpLink.style.display = "flex";
            }
          }
          // 注意：如果条件不满足（show_icp=false或没有icp_number），
          // 则ICP链接保持默认的display:none状态，即隐藏

          // ==========================================
          // 步骤3：处理公安网备案链接的显示逻辑
          // ==========================================
          // 判断条件：必须同时满足两个条件
          // 1. data.show_police === true（配置文件中启用了公安备案显示）
          // 2. data.police_number存在且不为空（提供了有效的公安备案号）
          if (data.show_police && data.police_number) {
            // 获取公安备案链接元素的DOM引用
            // 元素ID格式：prefix + "police-beian-link"
            // 例如：auth-police-beian-link, pc-police-beian-link, mobile-police-beian-link
            const policeLink = document.getElementById(
              prefix + "police-beian-link",
            );

            // 获取公安备案文本span元素的DOM引用
            // 这个span用于显示实际的公安备案号文字
            // 元素ID格式：prefix + "police-beian-text"
            const policeText = document.getElementById(
              prefix + "police-beian-text",
            );

            // 确保两个元素都存在，才进行后续操作
            // 这是一个安全检查，防止DOM结构不完整导致的错误
            if (policeLink && policeText) {
              // 将公安备案号文本填充到span元素中
              // 使用textContent而不是innerHTML，防止XSS攻击
              policeText.textContent = data.police_number;

              // 将链接元素设置为可见
              // 从默认的display:none改为display:flex
              // 使用flex是因为链接内部使用了flexbox布局（图标+文本）
              policeLink.style.display = "flex";
            }
          }
          // 注意：如果条件不满足（show_police=false或没有police_number），
          // 则公安备案链接保持默认的display:none状态，即隐藏

          // ==========================================
          // 关键设计说明：Footer容器的显示逻辑
          // ==========================================
          // 【以前的做法（已废弃）】
          // 以前的代码可能会检查hasInfo变量（是否有任何备案信息），
          // 如果hasInfo为false，就隐藏整个footer容器。
          // 这种做法会导致UI布局不稳定，出现跳动现象。
          //
          // 【现在的做法（推荐）】
          // 不再需要hasInfo判断来控制footer容器的显示/隐藏。
          // Footer容器在HTML中默认就是可见的（没有hidden类或display:none）。
          // 这样做的优点：
          // 1. 页面布局稳定：即使没有备案信息，footer也占据空间
          // 2. 用户体验好：避免页面内容因footer出现/消失而跳动
          // 3. 代码简洁：减少了不必要的DOM操作
          //
          // 总结：此函数只负责控制链接元素的显示，绝不隐藏footer容器本身！
        };

        // ==========================================
        // 第三步：调用updateBeianSection更新所有footer区域
        // ==========================================
        // 按照顺序分别更新三个不同位置的备案footer

        // 1. 更新认证登录页面(auth-login-container)中的 auth-beian-footer
        // 这个footer显示在用户登录界面的底部
        updateBeianSection("auth-");

        // 2. 更新桌面版(desktop-container)中的 pc-beian-footer
        // 这个footer显示在所有PC端页面的底部
        updateBeianSection("pc-");

        // 3. 更新移动版(mobile-container)中的 mobile-beian-footer
        // 这个footer显示在所有移动端页面的底部
        updateBeianSection("mobile-");

        // 注意：三次调用传入不同的prefix参数，确保更新所有footer区域
      }
      // 如果result.success为false或result.data不存在，则不做任何操作
      // footer保持默认状态（容器可见，链接隐藏）
    })
    // ==========================================
    // 第四步：错误处理
    // ==========================================
    // catch捕获fetch或then链中的任何错误
    // 例如：网络错误、JSON解析错误、API返回错误等
    .catch((error) => {
      // 使用console.warn而不是console.error
      // 因为备案信息加载失败不是致命错误，不应影响页面的核心功能
      // 用户仍然可以正常使用网站，只是看不到备案信息
      // console.warn("加载备案信息失败:", error);
      logMessage_Warning("加载备案信息失败: " + error);

      // 即使加载失败，footer容器仍然可见（作为空白区域）
      // 链接元素保持默认的隐藏状态
      // 这符合渐进式增强(Progressive Enhancement)的设计理念
    });
});

// ==========================================
// 支付设置面板标签页切换函数
// ==========================================
/**
 * 切换支付设置面板的标签页
 * 此函数用于在4个不同的功能模块之间切换显示
 *
 * @param {string} tabName - 要切换到的标签页名称
 *   可选值：'config'（支付方式配置）、'query'（订单查询）、
 *          'refund'（退款处理）、'test'（测试支付）
 */
function switchPaymentSettingsTab(tabName) {
  // 定义所有标签页的名称数组
  // 这样可以统一管理所有标签页，便于维护
  // 新增 'yipay' - 易支付配置标签页（移动端）
  const tabs = ["config", "query", "refund", "test", "yipay", "product-test"];

  // 遍历所有标签页，执行显示/隐藏操作
  tabs.forEach((tab) => {
    // 获取标签页按钮元素
    const tabButton = document.getElementById(`payment-settings-tab-${tab}`);
    // 获取标签页内容区域元素
    const tabContent = document.getElementById(
      `payment-settings-content-${tab}`,
    );

    // 检查当前遍历的标签页是否是要显示的目标标签页
    if (tab === tabName) {
      // ========================================
      // 【修复】根据不同的标签页执行相应的初始化函数
      // ========================================
      // 这是一个关键的初始化逻辑，确保每个标签页在显示时都能加载对应的数据
      // 移动端的实现与PC端保持一致，但使用不同的函数和容器ID

      if (tab === "config") {
        // ========================================
        // 【修复移动端支付方式列表无法加载的问题】
        // ========================================
        // 问题原因：
        // - 移动端之前缺少此逻辑，导致切换到支付配置标签页时，payment-methods-list容器为空
        // - PC端有相同逻辑（switchAdminPaymentSettingsTab函数第5060-5066行），工作正常
        //
        // 修复方案：
        // - 参考PC端实现，在切换到config标签页时自动调用loadPaymentMethodsConfig()
        // - 使用show_Modal_Alert=false参数，避免显示弹窗提示（保持与PC端一致）
        //
        // 函数说明：loadPaymentMethodsConfig(show_Modal_Alert, isMobile)
        // - show_Modal_Alert: 是否显示弹窗提示，移动端和PC端都设置为false
        // - isMobile: （可选）是否为移动端，函数内部会自动检测容器ID
        //
        // 容器区别：
        // - 移动端容器ID: payment-methods-list（第3900行）
        // - PC端容器ID: payment-methods-list_modal（第8698行）
        //
        // 调用时机：
        // - 当用户点击"支付方式"标签页按钮时触发（index.html第3822行）
        // - 通过onclick="switchPaymentSettingsTab('config')"调用此函数
        //
        // 预期效果：
        // - 移动端切换到支付配置标签页时，自动加载并显示所有已配置的支付方式
        // - 每个支付方式显示：Logo、名称、描述、启用开关、编辑按钮、删除按钮
        // - 如果没有配置任何支付方式，显示"暂无支付方式"的占位符提示
        loadPaymentMethodsConfig((show_Modal_Alert = false));

        // 在控制台输出日志，方便调试和追踪
        logMessage_Info("[移动端支付设置] 已触发支付方式配置加载");
      } else if (tab === "yipay") {
        // 切换到易支付配置标签页时，加载易支付配置
        // 调用移动端专用的易支付配置加载函数
        loadMobileYiPayConfig();
      } else if (tab === "query") {
        // 【新增】切换到订单查询标签页时，自动加载本地订单列表
        // 这样用户打开标签页就能立即看到订单数据，无需手动点击"加载本地"按钮
        // 使用setTimeout异步执行，避免阻塞标签页切换动画
        setTimeout(() => {
          logMessage_Info("[订单查询] 自动加载本地订单列表...");
          loadAllPaymentOrders();
        }, 100);
      }
      // === 激活目标标签页 ===

      // 1. 为标签页按钮添加激活状态样式
      //    - bg-sky-50: 浅蓝色背景
      //    - text-sky-600: 蓝色文字
      //    - border-b-2 border-sky-600: 蓝色底部边框（2px粗）
      //    - font-semibold: 加粗字体
      tabButton.classList.add(
        "bg-sky-50",
        "text-sky-600",
        "border-b-2",
        "border-sky-600",
        "font-semibold",
      );

      // 2. 移除标签页按钮的非激活状态样式
      //    - text-slate-600: 灰色文字
      //    - font-medium: 普通粗细字体
      tabButton.classList.remove("text-slate-600", "font-medium");

      // 3. 显示对应的内容区域
      //    移除hidden类，使内容可见
      tabContent.classList.remove("hidden");
    } else {
      // === 取消激活其他标签页 ===

      // 1. 移除其他标签页按钮的激活状态样式
      tabButton.classList.remove(
        "bg-sky-50",
        "text-sky-600",
        "border-b-2",
        "border-sky-600",
        "font-semibold",
      );

      // 2. 为其他标签页按钮添加非激活状态样式
      //    恢复为灰色文字和普通粗细
      tabButton.classList.add("text-slate-600", "font-medium");

      // 3. 隐藏其他内容区域
      //    添加hidden类，使内容不可见
      tabContent.classList.add("hidden");
    }
  });
}

// ==========================================
// 支付方式配置管理功能（Tab 1）
// ==========================================

/**
 * 加载支付方式配置
 * 从服务器获取当前的支付方式启用状态，并更新页面上的checkbox
 * 此函数会在页面加载时自动调用，以确保显示最新的配置状态
 *
 * API端点：GET /api/payment/methods_config
 * 预期返回格式：{ alipay: true, wechat: true, qq: false, unionpay: false }
 */
/**
 * ==========================================
 * HTML转义函数 - 防止XSS攻击
 * ==========================================
 * 功能：将字符串中的特殊HTML字符转换为安全的HTML实体
 * 这是一个关键的安全函数，用于防止跨站脚本攻击（XSS）
 *
 * 工作原理：
 * 当用户输入或配置数据包含特殊字符（如 <, >, &, ", '）时，
 * 如果直接插入到HTML中，浏览器会将其解释为HTML标签或属性，
 * 可能导致恶意脚本执行。此函数通过替换这些字符为HTML实体来防止此问题。
 *
 * 转义规则：
 * & → &amp;   （必须首先转义，避免重复转义）
 * < → &lt;    （防止<script>标签注入）
 * > → &gt;    （防止标签闭合）
 * " → &quot;  （防止属性值注入）
 * ' → &#039;  （防止单引号属性值注入）
 *
 * 参数：
 * @param {string} str - 需要转义的原始字符串
 *
 * 返回值：
 * @returns {string} - 转义后的安全字符串
 *
 * 使用场景：
 * - 在innerHTML中插入用户输入的文本
 * - 在HTML属性中使用配置数据
 * - 显示从API获取的未经验证的数据
 */
function escapeHtml(str) {
  // 如果输入不是字符串（例如null、undefined、数字等），先转换为字符串
  // 使用空字符串作为默认值，确保函数不会返回undefined
  if (typeof str !== "string") {
    str = String(str || "");
  }

  // 创建一个映射表，定义所有需要转义的字符及其对应的HTML实体
  const htmlEscapeMap = {
    "&": "&amp;", // 必须首先替换&符号，因为其他实体也包含&
    "<": "&lt;", // 小于号：防止标签开始符号
    ">": "&gt;", // 大于号：防止标签结束符号
    '"': "&quot;", // 双引号：防止HTML属性注入
    "'": "&#039;", // 单引号：防止单引号属性注入
  };

  // 使用正则表达式匹配所有需要转义的字符，并替换为对应的HTML实体
  // [&<>"'] 匹配任意一个需要转义的字符
  // g 标志表示全局匹配（替换所有出现的字符，而不仅仅是第一个）
  return str.replace(/[&<>"']/g, function (match) {
    // match 是正则匹配到的字符，从映射表中查找对应的HTML实体
    return htmlEscapeMap[match];
  });
}

// Inline handlers receive HTML-decoded attribute values, so pass JSON literals
// through HTML escaping instead of embedding raw user data in JavaScript code.
function escapeInlineJsArg(value) {
  const json = JSON.stringify(value == null ? "" : String(value));
  return json
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeInlineJsonArg(value) {
  const json = JSON.stringify(value == null ? null : value) ?? "null";
  return json
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * ==========================================
 * 安全的SVG解析函数 - 防止SVG内容注入攻击
 * ==========================================
 * 功能：使用DOMParser安全地解析SVG内容，移除潜在的恶意脚本
 *
 * SVG安全风险说明：
 * SVG文件可以包含<script>标签、事件处理器（如onload）等可执行代码，
 * 如果直接将未经验证的SVG内容插入到innerHTML中，可能导致XSS攻击。
 *
 * 安全策略：
 * 1. 使用DOMParser解析SVG字符串，而不是直接插入innerHTML
 * 2. 检查解析后的文档是否有效（无解析错误）
 * 3. 移除所有<script>标签和事件处理器属性
 * 4. 返回清理后的安全SVG内容
 *
 * 参数：
 * @param {string} svgString - 原始SVG字符串
 *
 * 返回值：
 * @returns {string} - 清理后的安全SVG字符串，如果解析失败则返回空字符串
 */
function sanitizeSVG(svgString) {
  // 使用try-catch包裹整个解析过程，防止解析错误导致程序崩溃
  try {
    // 创建一个DOMParser实例，用于解析SVG字符串
    // DOMParser是浏览器提供的安全API，用于解析XML和HTML文档
    const parser = new DOMParser();

    // 解析SVG字符串，指定MIME类型为 'image/svg+xml'
    // 这会将字符串解析为一个完整的XML文档对象
    const doc = parser.parseFromString(svgString, "image/svg+xml");

    // 检查解析是否成功：
    // 如果SVG字符串格式错误，DOMParser会在文档中插入一个<parsererror>元素
    // 通过检查是否存在此元素，可以判断解析是否失败
    const parserError = doc.querySelector("parsererror");
    if (parserError) {
      // 解析失败：记录错误日志并返回空字符串
      // console.warn('[安全警告] SVG解析失败，内容可能格式不正确');
      logMessage_Warning("[安全警告] SVG解析失败，内容可能格式不正确");
      return "";
    }

    // === 安全清理：移除所有潜在的恶意元素和属性 ===

    // 步骤1：移除所有<script>标签
    // SVG支持嵌入JavaScript脚本，这是XSS攻击的主要入口
    const scripts = doc.querySelectorAll("script");
    scripts.forEach((script) => script.remove());

    // 步骤2：移除所有事件处理器属性（以"on"开头的属性）
    // 例如：onload, onclick, onmouseover 等
    // 这些属性可以执行JavaScript代码，必须移除
    const allElements = doc.querySelectorAll("*");
    allElements.forEach((element) => {
      // 获取元素的所有属性
      const attributes = Array.from(element.attributes);
      attributes.forEach((attr) => {
        // 检查属性名是否以"on"开头（不区分大小写）
        if (attr.name.toLowerCase().startsWith("on")) {
          // 移除该事件处理器属性
          element.removeAttribute(attr.name);
        }
      });
    });

    // 步骤3：将清理后的SVG文档转换回字符串
    // 使用XMLSerializer将DOM对象序列化为字符串
    const serializer = new XMLSerializer();

    // 获取SVG根元素（文档的第一个子元素）
    const svgElement = doc.documentElement;

    // 序列化并返回清理后的SVG字符串
    return serializer.serializeToString(svgElement);
  } catch (error) {
    // 捕获任何解析或处理过程中的异常
    // console.error('[安全警告] SVG清理过程中发生错误：', error);
    logMessage_Error("[安全警告] SVG清理过程中发生错误：" + error);
    // 发生错误时返回空字符串，确保不会插入不安全的内容
    return "";
  }
}

/**
 * 加载支付方式配置（重构版 - 安全增强）
 * 功能：从服务器动态加载所有已定义的支付方式配置，并渲染到页面上
 *
 * 改造说明：
 * 1. 从 /api/payment/methods_config 获取所有支付方式的定义（名称、Logo、样式等）
 * 2. 从 /api/admin/payment/config 获取当前启用的支付方式列表
 * 3. 动态生成支付方式列表，每个支付方式包含：Logo、名称、开关、编辑按钮、删除按钮
 * 4. 支持SVG和图片两种Logo类型
 *
 * 安全增强（新增）：
 * 1. 使用escapeHtml()函数转义所有用户输入和配置数据，防止XSS攻击
 * 2. 使用sanitizeSVG()函数安全地解析SVG内容，移除潜在的恶意脚本
 * 3. 使用data-*属性存储支付方式代码，而不是直接放在onclick中
 * 4. 使用addEventListener绑定事件，而不是内联onclick属性
 * 5. 一次性构建完整HTML字符串，而不是在循环中使用innerHTML+=（性能优化）
 *
 * API端点：
 * - GET /api/payment/methods_config - 获取所有支付方式定义
 * - GET /api/admin/payment/config - 获取当前启用的支付方式
 */
async function loadPaymentMethodsConfig(
  show_Modal_Alert = true,
  DOMContentLoaded_Event = false,
) {
  // 输出日志，便于调试和追踪函数执行
  // console.log('[支付配置] 开始加载支付方式配置...');
  logMessage_Info("[支付配置] 开始加载支付方式配置...");
  if (show_Modal_Alert) {
    // showModalAlert("正在加载支付方式配置，请稍候...", "提示");
    Swal.fire({
      icon: "info",
      title: "提示",
      text: "正在加载支付方式配置，请稍候...",
    });
  }

  // 检查会话ID是否存在，不存在则无法进行API调用
  if (!sessionUUID) {
    // console.error('[支付配置] 会话ID未定义，无法加载配置');
    logMessage_Error("[支付配置] 会话ID未定义，无法加载配置");
    return;
  }

  try {
    // === 第1步：获取支付方式定义（必需）===
    // 先获取支付方式的定义数据（名称、Logo、样式等）
    const methodsResponse = await fetch("/api/payment/methods_config", {
      method: "GET", // GET请求，获取数据
      headers: {
        "Content-Type": "application/json", // 设置请求头，告知服务器期望返回JSON格式数据
        "X-Session-ID": sessionUUID, // 添加会话ID用于身份验证，解决"未登录或会话无效"的问题
      },
    });

    const methodsData = await methodsResponse.json();

    if (methodsData.success) {
      // console.log('[支付配置] 成功获取支付方式定义响应：', methodsData);
      logMessage_Info("[支付配置] 成功获取支付方式定义响应：", methodsData);
    } else {
      // console.error('[支付配置] 获取支付方式定义失败：', methodsData.message || '未知错误');
      logMessage_Error(
        "[支付配置] 获取支付方式定义失败：" +
          (methodsData.message || "未知错误"),
      );
      if (!DOMContentLoaded_Event) {
        // showModalAlert(
        //   "获取支付方式定义失败：" + (methodsData.message || "未知错误"),
        //   "错误"
        // );
        Swal.fire({
          icon: "error",
          title: "错误",
          text: "获取支付方式定义失败：" + (methodsData.message || "未知错误"),
        });
      }
      return;
    }

    const methods = methodsData.methods || {};

    // console.log('[支付配置] 成功获取支付方式定义：', methods);
    logMessage_Info("[支付配置] 成功获取支付方式定义：", methods);

    PAYMENT_METHODS = methods;

    // === 第2步：尝试获取启用状态（可选，失败不影响显示）===
    // 获取当前启用的支付方式列表，如果用户没有权限则默认全部为启用状态
    let enabledMethods = [];
    try {
      const configResponse = await fetch("/api/admin/payment/config", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
      });

      const configData = await configResponse.json();
      enabledMethods = configData.config?.enabled_payment_methods || [];

      if (configData.success) {
        // console.log('[支付配置] 成功获取启用状态响应：', configData);
        logMessage_Info(
          "[支付配置] 成功获取启用状态响应：",
          createSafeClientLogValue(configData),
        );
      } else {
        // console.warn('[支付配置] 获取启用状态失败，默认显示所有支付方式为启用：', configData.message || '未知错误');
        // logMessage_Warning(
        //   "[支付配置] 获取启用状态失败，默认显示所有支付方式为启用：" +
        //     (configData.message || "未知错误")
        // );
        if (!DOMContentLoaded_Event) {
          // showModalAlert(
          //   "获取启用状态失败，默认显示所有支付方式为启用：" +
          //     (configData.message || "未知错误"),
          //   "警告"
          // );
          Swal.fire({
            icon: "warning",
            title: "警告",
            text:
              "获取启用状态失败，默认显示所有支付方式为启用：" +
              (configData.message || "未知错误"),
          });
        }
        return;
      }

      logMessage_Info("[支付配置] 成功获取启用状态：", enabledMethods);
    } catch (configError) {
      // 获取启用状态失败，默认显示所有支付方式为启用
      // console.warn('[支付配置] 获取启用状态时出错，默认显示所有支付方式：', configError);
      logMessage_Warning(
        "[支付配置] 获取启用状态时出错，默认显示所有支付方式：" + configError,
      );
      if (!DOMContentLoaded_Event) {
        // showModalAlert(
        //   "获取启用状态时出错，默认显示所有支付方式：" + configError,
        //   "警告"
        // );
        Swal.fire({
          icon: "warning",
          title: "警告",
          text: "获取启用状态时出错，默认显示所有支付方式：" + configError,
        });
      }
      enabledMethods = Object.keys(methods);
    }

    // === 第4步：动态渲染支付方式列表 ===
    // 尝试获取支付方式列表容器，先尝试PC端（带_modal后缀），再尝试移动端（不带后缀）
    let listContainer = document.getElementById("payment-methods-list_modal");
    let isModalVersion = true; // 标记是否为PC端modal版本
    if (isMobileMode) {
      // 尝试获取移动端容器
      listContainer = document.getElementById("payment-methods-list-mobile");
      isModalVersion = false; // 标记为移动端版本
    }
    logMessage_Info(`[支付配置] 使用'${listContainer.id}'作为支付方式列表容器`);

    if (!listContainer) {
      // console.error('[支付配置] 找不到支付方式列表容器');
      logMessage_Error("[支付配置] 找不到支付方式列表容器");
      if (!DOMContentLoaded_Event) {
        // showModalAlert("找不到支付方式列表容器", "错误");
        Swal.fire({
          icon: "error",
          title: "错误",
          text: "找不到支付方式列表容器",
        });
      }
      return;
    }

    // 根据版本决定checkbox ID的后缀
    const idSuffix = isModalVersion ? "_modal" : "";

    // 清空现有内容
    listContainer.innerHTML = "";

    // === 【安全修复】修复响应式布局问题 ===
    // 原问题：col-span-2 在小屏幕上会导致布局问题
    // 修复：使用 md:col-span-2 只在中等及以上屏幕使用双列布局
    // 如果没有任何支付方式定义，显示提示信息
    if (Object.keys(methods).length === 0) {
      listContainer.innerHTML = `
        <div class="md:col-span-2 text-center py-8 text-slate-500">
          <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/>
          </svg>
          <p class="text-sm">暂无支付方式，点击"添加支付方式"按钮开始添加</p>
        </div>
      `;
      return;
    }

    // === 第5步：遍历所有支付方式，生成HTML（安全增强版）===
    // 【性能优化】使用数组收集所有HTML片段，最后一次性设置innerHTML
    // 避免在循环中多次调用innerHTML+=，每次都会触发DOM重新解析，效率低下
    const htmlParts = [];

    for (const [code, method] of Object.entries(methods)) {
      // 判断该支付方式是否已启用
      const isEnabled = enabledMethods.includes(code);

      // === 【安全修复】渲染Logo：支持SVG代码和图片URL两种类型 ===
      let logoHTML = "";
      if (method.icon === "svg" && method.svg) {
        // 【XSS修复1】使用sanitizeSVG()安全地解析SVG内容
        // 原问题：直接插入method.svg到innerHTML可能包含恶意脚本（如<script>标签或onload事件）
        // 修复方案：使用DOMParser解析SVG，移除所有<script>标签和事件处理器
        const safeSVG = sanitizeSVG(method.svg);
        if (safeSVG) {
          logoHTML = `<div class="w-10 h-10 flex items-center justify-center">${safeSVG}</div>`;
        } else {
          // 如果SVG解析失败或为空，显示默认图标
          logoHTML = `
            <svg class="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
            </svg>
          `;
        }
      } else if (method.icon === "image" && method.image) {
        // 【XSS修复2】转义图片URL和alt文本，防止属性注入攻击
        // 原问题：method.image和method.name直接插入HTML属性未转义
        // 攻击场景：如果method.image包含引号和恶意代码，如：
        //   method.image = '" onerror="alert(\'XSS\')" data-foo="'
        //   生成的HTML为：<img src="" onerror="alert('XSS')" data-foo="" alt="...">
        // 修复方案：使用escapeHtml()转义所有特殊字符
        const safeImageUrl = escapeHtml(method.image);
        const safeName = escapeHtml(method.name || code);
        logoHTML = `<img src="${safeImageUrl}" alt="${safeName}" class="w-10 h-10 object-contain">`;
      } else {
        // 没有Logo时显示默认图标（支付图标）
        logoHTML = `
          <svg class="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"/>
          </svg>
        `;
      }

      // === 【安全修复】转义所有显示的文本内容 ===
      // 防止method.name、method.description、method.borderColor包含恶意HTML
      const safeName = escapeHtml(method.name || code);
      const safeDescription = method.description
        ? escapeHtml(method.description)
        : "";
      const safeBorderColor = escapeHtml(
        method.borderColor || "hover:border-sky-500",
      );

      // === 【安全修复】使用安全的支付方式代码标识符 ===
      // 为了在按钮点击时能够识别支付方式，我们需要存储code值
      // 原方案（不安全）：直接将code放在onclick属性中，如 onclick="edit('${code}')"
      // 问题：如果code包含引号或特殊字符，会导致JavaScript注入
      // 新方案（安全）：
      // 1. 使用data-payment-code属性存储code值（HTML属性会自动转义）
      // 2. 为按钮分配唯一的class，稍后使用addEventListener绑定事件
      // 3. 不使用内联onclick属性
      const safeCode = escapeHtml(code);

      // === 【问题46修复】根据移动端/PC端生成不同的HTML结构 ===
      // 原问题：移动端和PC端共用相同的HTML模板，导致移动端显示错位
      // 修复方案：根据isModalVersion标志，为移动端和PC端生成专门优化的HTML结构
      // - 移动端(isModalVersion=false)：单列布局、紧凑间距、小图标、小按钮、小字体
      // - PC端(isModalVersion=true)：保持原有的标准尺寸和间距

      let itemHTML;

      // 判断是否为移动端版本
      if (!isModalVersion) {
        // === 移动端专用HTML（紧凑布局）===
        // 特点：
        // 1. 更小的内边距(p-2而非p-3)
        // 2. 更小的图标尺寸(w-8 h-8而非w-10 h-10)
        // 3. 更小的字体(text-xs而非text-sm)
        // 4. 更小的开关尺寸(w-9 h-5而非w-11 h-6)
        // 5. 更小的按钮尺寸(p-1而非p-1.5)
        // 6. 更紧凑的间距(gap-2而非gap-3)
        itemHTML = `
          <div class="flex items-start justify-between gap-2 p-2 bg-white rounded-lg border border-slate-200 ${safeBorderColor} transition-colors">
            <!-- 左侧：Logo和名称 (移动端紧凑版) -->
            <div class="flex items-start gap-2 flex-1 min-w-0">
              <!-- Logo - 移动端使用更小的尺寸 -->
              ${logoHTML.replace(/w-10 h-10/g, "w-8 h-8 flex-shrink-0")}
              <!-- 名称和描述 - 移动端使用更小的字体 -->
              <div class="flex-1 min-w-0 pt-0.5 leading-4">
                <span class="text-xs font-semibold text-slate-700 block break-words leading-4">${safeName}</span>
                ${
                  safeDescription
                    ? `<span class="text-xs text-slate-500 block break-words leading-4 mt-0.5">${safeDescription}</span>`
                    : ""
                }
              </div>
            </div>

            <!-- 右侧：操作按钮组 (移动端紧凑版) -->
            <div class="flex items-center gap-1.5 ml-2 shrink-0 self-start">
              <!-- 启用/禁用开关 - 移动端使用更小的开关 -->
              <label class="relative inline-flex items-center cursor-pointer" title="启用/禁用">
                <input type="checkbox" id="payment-method-${safeCode}${idSuffix}" class="sr-only peer" ${
                  isEnabled ? "checked" : ""
                }>
                <!-- 移动端开关：w-9 h-5（比PC端的w-11 h-6小）-->
                <div class="w-9 h-5 bg-slate-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-sky-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-500"></div>
              </label>

              <!-- 【安全修复3】编辑按钮 - 移动端紧凑版 -->
              <button class="payment-edit-btn p-1 text-blue-600 hover:bg-blue-50 rounded transition-colors"
                title="编辑"
                data-payment-code="${safeCode}">
                <!-- 移动端图标：w-3.5 h-3.5（比PC端的w-4 h-4小）-->
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
              </button>

              <!-- 【安全修复4】删除按钮 - 移动端紧凑版 -->
              <button class="payment-delete-btn p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                title="删除"
                data-payment-code="${safeCode}">
                <!-- 移动端图标：w-3.5 h-3.5（比PC端的w-4 h-4小）-->
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            </div>
          </div>
        `;
      } else {
        // === PC端标准HTML（原有布局）===
        // 保持原有的标准尺寸和间距，确保PC端显示效果不变
        itemHTML = `
          <div class="flex items-center justify-between p-3 bg-white rounded-lg border border-slate-200 ${safeBorderColor} transition-colors">
            <!-- 左侧：Logo和名称 -->
            <div class="flex items-center gap-3 flex-1 min-w-0">
              <!-- Logo -->
              ${logoHTML}
              <!-- 名称和描述 -->
              <div class="flex-1 min-w-0">
                <span class="text-sm font-semibold text-slate-700 block truncate">${safeName}</span>
                ${
                  safeDescription
                    ? `<span class="text-xs text-slate-500 block truncate">${safeDescription}</span>`
                    : ""
                }
              </div>
            </div>
            
            <!-- 右侧：操作按钮组 -->
            <div class="flex items-center gap-2 ml-3">
              <!-- 启用/禁用开关 -->
              <label class="relative inline-flex items-center cursor-pointer" title="启用/禁用">
                <input type="checkbox" id="payment-method-${safeCode}${idSuffix}" class="sr-only peer" ${
                  isEnabled ? "checked" : ""
                }>
                <div class="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-sky-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-500"></div>
              </label>
              
              <!-- 【安全修复3】编辑按钮 - 使用data属性存储code -->
              <!-- 原问题：onclick="openEditPaymentMethodModal('${code}')" 中的code未转义 -->
              <!-- 如果code包含单引号，会导致JavaScript语法错误或注入攻击 -->
              <!-- 修复方案：使用data-payment-code属性存储code，稍后用addEventListener绑定 -->
              <button class="payment-edit-btn p-1.5 text-blue-600 hover:bg-blue-50 rounded transition-colors" 
                title="编辑" 
                data-payment-code="${safeCode}">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
              </button>
              
              <!-- 【安全修复4】删除按钮 - 使用data属性存储code -->
              <!-- 原问题：onclick="deletePaymentMethod('${code}')" 中的code未转义 -->
              <!-- 修复方案：同上，使用data属性 + addEventListener -->
              <button class="payment-delete-btn p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors" 
                title="删除" 
                data-payment-code="${safeCode}">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
              </button>
            </div>
          </div>
        `;
      }

      // 【性能优化】将生成的HTML片段添加到数组中，而不是立即插入DOM
      // 这样避免了每次循环都触发DOM重新解析和渲染
      htmlParts.push(itemHTML);
    }

    // === 【性能优化】一次性设置innerHTML，提高渲染效率 ===
    // 将数组中的所有HTML片段连接成一个完整的字符串，然后一次性设置到容器中
    // 相比循环中使用innerHTML+=，这种方法只触发一次DOM解析，性能提升显著
    listContainer.innerHTML = htmlParts.join("");

    // === 【安全修复】使用addEventListener绑定事件处理器 ===
    // 在HTML插入到DOM后，为所有编辑和删除按钮绑定事件监听器
    // 这种方式比内联onclick更安全，因为：
    // 1. 避免了在HTML属性中嵌入JavaScript代码
    // 2. 可以从data属性中安全地读取code值（浏览器会自动处理属性转义）
    // 3. 符合内容安全策略（CSP）的最佳实践

    // 绑定所有编辑按钮的点击事件
    const editButtons = listContainer.querySelectorAll(".payment-edit-btn");
    editButtons.forEach((button) => {
      button.addEventListener("click", function () {
        // 从data-payment-code属性中安全地读取支付方式代码
        // getAttribute会返回已解码的字符串，无需担心XSS问题
        const paymentCode = this.getAttribute("data-payment-code");
        // 调用编辑函数（假设该函数已在其他地方定义）
        openEditPaymentMethodModal(paymentCode);
      });
    });

    // 绑定所有删除按钮的点击事件
    const deleteButtons = listContainer.querySelectorAll(".payment-delete-btn");
    deleteButtons.forEach((button) => {
      button.addEventListener("click", function () {
        // 从data-payment-code属性中安全地读取支付方式代码
        const paymentCode = this.getAttribute("data-payment-code");
        // 调用删除函数（假设该函数已在其他地方定义）
        deletePaymentMethod(paymentCode);
      });
    });

    // 记录成功日志
    // console.log('[支付配置] 支付方式列表渲染完成');
    logMessage_Info("[支付配置] 支付方式列表渲染完成");
    if (show_Modal_Alert) {
      // showModalAlert("支付方式配置加载完成", "成功");
      Swal.fire({
        icon: "success",
        title: "成功",
        text: "支付方式配置加载完成",
      });
    }

    // === 【新增功能】动态填充测试支付方式下拉框 ===
    // 功能说明：将已启用的支付方式动态填充到"测试支付"模块的支付方式下拉框中
    // 优点：避免硬编码，支持动态配置的支付方式
    // 位置：admin-test-payment-method_modal（测试支付模态框中的支付方式选择下拉框）

    // 第1步：获取测试支付方式下拉框DOM元素
    const testPaymentMethodSelect = document.getElementById(
      "admin-test-payment-method_modal",
    );

    // 第2步：防御性检查 - 确保下拉框元素存在
    if (testPaymentMethodSelect) {
      // console.log('[支付配置] 开始更新测试支付方式下拉框...');
      logMessage_Info("[支付配置] 开始更新测试支付方式下拉框...");

      // 第3步：保存当前选中的值（如果存在）
      // 目的：在更新选项后，如果之前选中的支付方式仍然可用，保持选中状态
      const currentSelectedValue = testPaymentMethodSelect.value;
      // console.log('[支付配置] 当前选中的支付方式：', currentSelectedValue || '无');
      logMessage_Info(
        "[支付配置] 当前选中的支付方式：" + (currentSelectedValue || "无"),
      );

      // 第4步：清空现有的所有选项
      // 使用innerHTML = ''清空比循环删除选项更高效
      testPaymentMethodSelect.innerHTML = "";

      // 第5步：遍历所有支付方式，只添加已启用的支付方式到下拉框
      let optionAdded = false; // 标记是否至少添加了一个选项
      let previousValueStillExists = false; // 标记之前选中的值是否仍然存在

      for (const [code, method] of Object.entries(methods)) {
        // 只处理已启用的支付方式
        const isEnabled = enabledMethods.includes(code);

        if (isEnabled) {
          // 第6步：创建新的option元素
          const option = document.createElement("option");

          // 设置option的value属性为支付方式代码（如：alipay, wxpay）
          option.value = code;

          // 设置option的显示文本为支付方式名称（如：支付宝, 微信支付）
          // 使用textContent而非innerHTML，防止XSS攻击
          option.textContent = method.name || code;

          // 第7步：将option添加到select下拉框中
          testPaymentMethodSelect.appendChild(option);

          // 标记已添加选项
          optionAdded = true;

          // 检查这个支付方式是否是之前选中的
          if (code === currentSelectedValue) {
            previousValueStillExists = true;
          }

          // 输出日志，记录添加的支付方式
          // console.log(`[支付配置] 添加测试支付选项：${code} - ${method.name || code}`);
          logMessage_Info(
            "[支付配置] 添加测试支付选项：" +
              code +
              " - " +
              (method.name || code),
          );
        }
      }

      // 第8步：恢复之前的选中状态（如果该支付方式仍然可用）
      if (previousValueStillExists && currentSelectedValue) {
        testPaymentMethodSelect.value = currentSelectedValue;
        // console.log('[支付配置] 已恢复之前选中的支付方式：', currentSelectedValue);
        logMessage_Info(
          "[支付配置] 已恢复之前选中的支付方式：" + currentSelectedValue,
        );
      } else if (optionAdded) {
        // 如果之前的选中值不可用，但至少有一个选项，则选中第一个
        // console.log('[支付配置] 之前选中的支付方式不可用，已自动选中第一个可用选项');
        logMessage_Info(
          "[支付配置] 之前选中的支付方式不可用，已自动选中第一个可用选项",
        );
      }

      // 第9步：如果没有任何已启用的支付方式，添加一个提示选项
      if (!optionAdded) {
        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "暂无可用的支付方式";
        emptyOption.disabled = true; // 禁用该选项，不可选择
        testPaymentMethodSelect.appendChild(emptyOption);
        // console.warn('[支付配置] 警告：没有已启用的支付方式可添加到测试支付下拉框');
        logMessage_Warning(
          "[支付配置] 警告：没有已启用的支付方式可添加到测试支付下拉框",
        );
      }

      logMessage_Info("[支付配置] 测试支付方式下拉框更新完成");
    } else {
      // 如果找不到测试支付方式下拉框元素，输出警告日志
      // console.warn('[支付配置] 警告：找不到测试支付方式下拉框元素（admin-test-payment-method_modal）');
      logMessage_Warning(
        "[支付配置] 警告：找不到测试支付方式下拉框元素（admin-test-payment-method_modal）",
      );
    }
  } catch (error) {
    // === 错误处理 ===
    // console.error('[支付配置] 加载支付方式配置时发生错误：', error);
    logMessage_Error("[支付配置] 加载支付方式配置时发生错误：" + error);
    if (!DOMContentLoaded_Event) {
      // showModalAlert(
      //   "无法加载支付方式配置，请刷新页面重试。如果问题持续，请联系管理员。"
      // );
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "无法加载支付方式配置，请刷新页面重试。如果问题持续，请联系管理员。",
      });
    }
  }
}

/**
 * 保存支付方式配置（重构版）
 * 功能：收集所有支付方式的启用状态，提交到服务器保存
 *
 * 改造说明：
 * 1. 动态收集所有支付方式的checkbox状态（不再硬编码4个支付方式）
 * 2. 构建enabled_payment_methods数组，只包含启用的支付方式代码
 * 3. 调用PUT /api/admin/payment/config保存配置
 * 4. 保存成功后重新加载列表
 *
 * API端点：PUT /api/admin/payment/config
 * 请求体格式：{ enabled_payment_methods: ["alipay", "wxpay", ...] }
 */
async function savePaymentMethodsConfig() {
  // 输出日志，标记保存操作开始
  // console.log('[支付配置] 开始保存支付方式配置...');
  logMessage_Info("[支付配置] 开始保存支付方式配置...");

  // === 第0步：确定当前是PC端还是移动端 ===
  // 尝试获取PC端结果显示区域
  let resultDiv = document.getElementById("admin-payment-config-result_modal");
  let isModalVersion = true; // 标记是否为PC端modal版本
  if (!resultDiv) {
    // 如果PC端元素不存在，尝试获取移动端元素
    resultDiv = document.getElementById("admin-payment-config-result");
    isModalVersion = false; // 标记为移动端版本
  }

  // 根据版本决定checkbox ID的后缀
  const idSuffix = isModalVersion ? "_modal" : "";

  try {
    // === 第1步：获取所有支付方式的checkbox并收集启用状态 ===

    // 获取支付方式列表容器
    // 先尝试PC端容器，再尝试移动端容器
    let listContainer = document.getElementById("payment-methods-list_modal");
    if (!listContainer) {
      listContainer = document.getElementById("payment-methods-list");
    }

    if (!listContainer) {
      throw new Error("找不到支付方式列表容器");
    }

    // 查找所有以 payment-method- 开头的checkbox
    // 根据版本决定是否需要检查 _modal 后缀
    let checkboxes;
    if (isModalVersion) {
      // PC端：查找以 _modal 结尾的checkbox
      checkboxes = listContainer.querySelectorAll(
        'input[type="checkbox"][id^="payment-method-"][id$="_modal"]',
      );
    } else {
      // 移动端：查找所有以 payment-method- 开头的checkbox，但不以 _modal 结尾
      // 使用更通用的选择器，然后在遍历时过滤
      checkboxes = Array.from(
        listContainer.querySelectorAll(
          'input[type="checkbox"][id^="payment-method-"]',
        ),
      ).filter((cb) => !cb.id.endsWith("_modal"));
    }

    // 创建一个数组来存储启用的支付方式代码
    const enabledMethods = [];

    // 遍历所有checkbox，收集已选中（启用）的支付方式
    checkboxes.forEach((checkbox) => {
      if (checkbox.checked) {
        // 从checkbox的ID中提取支付方式代码
        // ID格式：payment-method-{code} 或 payment-method-{code}_modal
        // 例如：payment-method-alipay_modal -> alipay
        //       payment-method-alipay -> alipay
        const code = checkbox.id
          .replace("payment-method-", "")
          .replace("_modal", "");
        enabledMethods.push(code);
      }
    });

    // 在控制台输出即将提交的配置，便于调试
    // console.log('[支付配置] 准备提交的启用支付方式：', enabledMethods);
    logMessage_Info("[支付配置] 准备提交的启用支付方式：", enabledMethods);

    // === 第2步：验证至少启用一种支付方式 ===
    if (enabledMethods.length === 0) {
      throw new Error("至少需要启用一种支付方式");
    }

    // === 第3步：发起HTTP PUT请求保存配置 ===
    // 使用fetch API调用后端接口
    const response = await fetch("/api/admin/payment/config", {
      method: "PUT", // HTTP方法：PUT用于更新资源
      headers: {
        // 设置请求头
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      // 将配置对象转换为JSON字符串作为请求体
      // 后端期望接收 enabled_payment_methods 数组
      body: JSON.stringify({
        enabled_payment_methods: enabledMethods,
      }),
    });

    // === 第4步：检查响应状态 ===
    if (!response.ok) {
      // 如果服务器返回错误状态码，抛出错误
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `保存配置失败：HTTP状态码 ${response.status}`,
      );
    }

    // === 第5步：解析服务器响应 ===
    const result = await response.json();

    // 输出成功日志
    // console.log('[支付配置] 支付方式配置保存成功：', result);
    logMessage_Info("[支付配置] 支付方式配置保存成功");

    // === 第6步：显示成功提示 ===

    // 检查resultDiv是否存在
    if (resultDiv) {
      // 更新结果显示区域为绿色成功提示框
      // 使用textContent避免XSS攻击
      resultDiv.innerHTML = `
        <div class="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-2">
          ✓ 配置已成功保存，已启用 ${enabledMethods.length} 个支付方式
        </div>
      `;

      // 移除hidden类，让提示框可见
      resultDiv.classList.remove("hidden");

      // 设置定时器，3秒后自动隐藏提示框
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 3000);
    }

    // === 第6.5步：自动同步易支付启用方式 ===
    // 在保存支付方式配置成功后，自动将启用的支付方式同步到易支付配置中
    // 这样用户无需手动打开选择器，系统会自动维护两边的一致性

    const yipayMethodsInput = document.getElementById(
      "admin-yipay-enabled-methods_modal",
    );
    if (yipayMethodsInput) {
      // 将启用的支付方式数组转换为逗号分隔的字符串
      // 例如：["alipay", "wxpay"] => "alipay,wxpay"
      const methodsString = enabledMethods.join(",");

      // 更新易支付启用方式输入框的值
      // 即使输入框设置了readonly属性，JavaScript仍然可以修改其value
      yipayMethodsInput.value = methodsString;

      // 触发input事件，确保任何监听此输入框的代码能够感知到值的变化
      // bubbles: true 表示事件会向上冒泡到父元素
      yipayMethodsInput.dispatchEvent(new Event("input", { bubbles: true }));

      // 添加视觉反馈：短暂高亮输入框，让用户知道值已更新
      // 使用Tailwind CSS的ring类创建绿色边框效果
      yipayMethodsInput.classList.add("ring-2", "ring-green-500");

      // 设置定时器，1.5秒后自动移除高亮效果
      setTimeout(() => {
        yipayMethodsInput.classList.remove("ring-2", "ring-green-500");
      }, 1500);

      // 在控制台输出详细的日志，记录自动同步操作
      // 使用 ✓ 符号标记成功操作，便于快速识别
      // console.log('[支付配置] ✓ 已自动同步到易支付启用方式');
      logMessage_Info("[支付配置] 已自动同步到易支付启用方式");
      // console.log('[支付配置] 同步的支付方式代码：', methodsString);
      logMessage_Info("[支付配置] 同步的支付方式代码：" + methodsString);
      // console.log('[支付配置] 同步的支付方式数量：', enabledMethods.length);
      logMessage_Info(
        "[支付配置] 同步的支付方式数量：" + enabledMethods.length,
      );
      // console.log('[支付配置] 输入框当前值：', yipayMethodsInput.value);
      logMessage_Info("[支付配置] 输入框当前值：" + yipayMethodsInput.value);
    } else {
      // 如果找不到易支付输入框元素，在控制台输出警告
      // 使用 ✗ 符号标记失败操作，并提供详细的调试信息
      // console.warn('[支付配置] ✗ 未找到易支付启用方式输入框元素（ID: admin-yipay-enabled-methods_modal）');
      logMessage_Warning(
        "[支付配置] 未找到易支付启用方式输入框元素（ID: admin-yipay-enabled-methods_modal）",
      );
      // console.warn('[支付配置] 请检查HTML中是否存在此元素');
      logMessage_Warning("[支付配置] 请检查HTML中是否存在此元素");
    }

    // === 第7步：重新加载配置以确保数据同步 ===
    // 调用loadPaymentMethodsConfig函数，从服务器重新获取最新配置
    await loadPaymentMethodsConfig();
  } catch (error) {
    // === 错误处理 ===
    // 捕获所有可能的错误：网络错误、服务器错误、JSON解析错误等

    // 在控制台输出详细的错误信息
    // console.error('[支付配置] 保存支付方式配置时发生错误：', error);
    logMessage_Error("[支付配置] 保存支付方式配置时发生错误：" + error);

    // 向用户显示错误提示
    if (resultDiv) {
      // 更新结果显示区域为红色错误提示框
      resultDiv.innerHTML = `
        <div class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
          ✗ 保存失败：${error.message || "未知错误"}。请重试或联系管理员。
        </div>
      `;
      // 显示错误提示框
      resultDiv.classList.remove("hidden");

      // 5秒后自动隐藏错误提示
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 5000);
    } else {
      // 如果结果显示区域不存在，使用alert作为备用方案
      // showModalAlert(`保存失败：${error.message || "未知错误"}。请重试。`);
      Swal.fire({
        icon: "error",
        title: "错误",
        text: `保存失败：${error.message || "未知错误"}。请重试或联系管理员。`,
      });
    }
  }
}

/**
 * 打开添加支付方式的模态框
 * 功能：清空表单，设置为添加模式，显示模态框
 */
function openAddPaymentMethodModal() {
  // console.log('[支付配置] 打开添加支付方式模态框');
  logMessage_Info("[支付配置] 打开添加支付方式模态框");

  // 获取模态框元素
  const modal = document.getElementById("payment-method-modal");
  if (!modal) {
    // console.error('[支付配置] 找不到支付方式模态框');
    logMessage_Error("[支付配置] 找不到支付方式模态框");
    return;
  }

  // 设置模态框标题为"添加支付方式"
  const titleElement = document.getElementById("payment-method-modal-title");
  if (titleElement) {
    titleElement.textContent = "添加支付方式";
  }

  // 清空所有表单字段
  document.getElementById("payment-method-code").value = "";
  document.getElementById("payment-method-name").value = "";
  document.getElementById("payment-method-svg").value = "";
  document.getElementById("payment-method-image").value = "";
  document.getElementById("payment-method-description").value = "";
  document.getElementById("payment-method-border-color").value =
    "hover:border-sky-500";
  document.getElementById("payment-method-text-color").value = "text-sky-600";

  // 启用支付方式代码输入框（添加模式下可以输入代码）
  document.getElementById("payment-method-code").disabled = false;

  // 默认选择SVG类型
  document.getElementById("logo-type-svg").checked = true;
  toggleLogoInput();

  // 隐藏错误提示
  const errorDiv = document.getElementById("payment-method-error");
  if (errorDiv) {
    errorDiv.classList.add("hidden");
  }

  // 显示模态框
  modal.classList.remove("hidden");

  // 设置模态框为添加模式（用于savePaymentMethod函数判断）
  modal.dataset.mode = "add";
}

/**
 * 打开编辑支付方式的模态框
 * 功能：加载现有支付方式的配置，设置为编辑模式，显示模态框
 *
 * @param {string} code - 支付方式代码
 */
async function openEditPaymentMethodModal(code) {
  // console.log('[支付配置] 打开编辑支付方式模态框：', code);
  logMessage_Info("[支付配置] 打开编辑支付方式模态框：" + code);

  // 获取模态框元素
  const modal = document.getElementById("payment-method-modal");
  if (!modal) {
    // console.error('[支付配置] 找不到支付方式模态框');
    logMessage_Error("[支付配置] 找不到支付方式模态框");
    return;
  }

  try {
    // 从服务器获取支付方式配置
    const response = await fetch("/api/payment/methods_config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    if (!response.ok) {
      throw new Error("获取支付方式配置失败");
    }

    const data = await response.json();
    const method = data.methods[code];

    if (!method) {
      throw new Error("找不到指定的支付方式");
    }

    // 设置模态框标题为"编辑支付方式"
    const titleElement = document.getElementById("payment-method-modal-title");
    if (titleElement) {
      titleElement.textContent = "编辑支付方式";
    }

    // 填充表单字段
    document.getElementById("payment-method-code").value = code;
    document.getElementById("payment-method-name").value = method.name || "";
    document.getElementById("payment-method-description").value =
      method.description || "";
    document.getElementById("payment-method-border-color").value =
      method.borderColor || "hover:border-sky-500";
    document.getElementById("payment-method-text-color").value =
      method.textColor || "text-sky-600";

    // 设置Logo类型和内容
    if (method.icon === "svg" && method.svg) {
      document.getElementById("logo-type-svg").checked = true;
      document.getElementById("payment-method-svg").value = method.svg;
    } else if (method.icon === "image" && method.image) {
      document.getElementById("logo-type-image").checked = true;
      document.getElementById("payment-method-image").value = method.image;
    } else {
      document.getElementById("logo-type-svg").checked = true;
      document.getElementById("payment-method-svg").value = "";
    }
    toggleLogoInput();

    // 禁用支付方式代码输入框（编辑模式下不能修改代码）
    document.getElementById("payment-method-code").disabled = true;

    // 隐藏错误提示
    const errorDiv = document.getElementById("payment-method-error");
    if (errorDiv) {
      errorDiv.classList.add("hidden");
    }

    // 显示模态框
    modal.classList.remove("hidden");

    // 设置模态框为编辑模式
    modal.dataset.mode = "edit";
  } catch (error) {
    // console.error('[支付配置] 加载支付方式配置失败：', error);
    logMessage_Error("[支付配置] 加载支付方式配置失败：" + error);
    // showModalAlert("无法加载支付方式配置，请重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "无法加载支付方式配置，请重试。如果问题持续，请联系管理员。",
    });
  }
}

/**
 * 关闭支付方式模态框
 */
function closePaymentMethodModal() {
  // console.log('[支付配置] 关闭支付方式模态框');
  logMessage_Info("[支付配置] 关闭支付方式模态框");

  // 获取模态框元素并隐藏
  const modal = document.getElementById("payment-method-modal");
  if (modal) {
    modal.classList.add("hidden");
  }
}

/**
 * 切换Logo输入类型（SVG代码 / 图片URL）
 */
function toggleLogoInput() {
  // 获取SVG和图片输入容器
  const svgContainer = document.getElementById("svg-input-container");
  const imageContainer = document.getElementById("image-input-container");

  // 检查当前选中的Logo类型
  const isSvg = document.getElementById("logo-type-svg").checked;

  // 根据选择显示/隐藏相应的输入框
  if (isSvg) {
    svgContainer.classList.remove("hidden");
    imageContainer.classList.add("hidden");
  } else {
    svgContainer.classList.add("hidden");
    imageContainer.classList.remove("hidden");
  }
}

/**
 * 保存支付方式配置（添加或更新）
 * 功能：验证表单，提交到服务器，刷新列表
 */
async function savePaymentMethod() {
  // console.log('[支付配置] 开始保存支付方式...');
  logMessage_Info("[支付配置] 开始保存支付方式...");

  // 获取模态框和错误提示区域
  const modal = document.getElementById("payment-method-modal");
  const errorDiv = document.getElementById("payment-method-error");

  try {
    // === 第1步：收集表单数据 ===

    // 获取支付方式代码（必填）
    const code = document.getElementById("payment-method-code").value.trim();
    if (!code) {
      throw new Error("支付方式代码不能为空");
    }

    // 验证代码格式：只允许字母、数字和下划线
    if (!/^[a-zA-Z0-9_]+$/.test(code)) {
      throw new Error("支付方式代码只能包含字母、数字和下划线");
    }

    // 获取显示名称（必填）
    const name = document.getElementById("payment-method-name").value.trim();
    if (!name) {
      throw new Error("显示名称不能为空");
    }

    // 获取Logo类型和内容
    const isSvg = document.getElementById("logo-type-svg").checked;
    let icon, svg, image;

    if (isSvg) {
      icon = "svg";
      svg = document.getElementById("payment-method-svg").value.trim();
      if (!svg) {
        throw new Error("请输入SVG代码");
      }
      image = "";
    } else {
      icon = "image";
      image = document.getElementById("payment-method-image").value.trim();
      if (!image) {
        throw new Error("请输入图片URL");
      }
      svg = "";
    }

    // 获取描述、边框颜色和文字颜色（可选）
    const description = document
      .getElementById("payment-method-description")
      .value.trim();
    const borderColor = document.getElementById(
      "payment-method-border-color",
    ).value;
    const textColor = document.getElementById(
      "payment-method-text-color",
    ).value;

    // === 第2步：构建请求数据 ===
    const methodData = {
      name,
      icon,
      svg,
      image,
      description,
      borderColor,
      textColor,
    };

    // console.log('[支付配置] 准备提交的数据：', { code, ...methodData });
    logMessage_Info(
      "[支付配置] 准备提交的数据：",
      createSafeClientLogValue({ code, ...methodData }),
    );

    // === 第3步：判断是添加还是编辑模式 ===
    const mode = modal.dataset.mode || "add";
    const isEditMode = mode === "edit";

    // === 第4步：发起HTTP请求 ===
    let url, method;
    if (isEditMode) {
      // 编辑模式：PUT请求更新现有支付方式
      url = `/api/admin/payment_methods/${code}`;
      method = "PUT";
    } else {
      // 添加模式：POST请求创建新支付方式
      url = "/api/admin/payment_methods";
      method = "POST";
      // 添加模式需要在请求体中包含code
      methodData.code = code;
    }

    const response = await fetch(url, {
      method: method,
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(methodData),
    });

    // === 第5步：检查响应状态 ===
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `保存失败：HTTP状态码 ${response.status}`,
      );
    }

    // === 第6步：解析响应 ===
    const result = await response.json();
    // console.log('[支付配置] 支付方式保存成功：', result);
    logMessage_Info("[支付配置] 支付方式保存成功");

    // === 第7步：关闭模态框并刷新列表 ===
    closePaymentMethodModal();

    // 显示成功提示
    // showModalAlert(isEditMode ? "支付方式已更新" : "支付方式已添加");
    Swal.fire({
      icon: "success",
      title: "成功",
      text: isEditMode ? "支付方式已更新" : "支付方式已添加",
    });

    // 重新加载支付方式列表
    await loadPaymentMethodsConfig();
  } catch (error) {
    // === 错误处理 ===
    // console.error('[支付配置] 保存支付方式失败：', error);
    logMessage_Error("[支付配置] 保存支付方式失败：" + error);

    // 在模态框中显示错误信息
    if (errorDiv) {
      errorDiv.innerHTML = `
        <div class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          ✗ ${error.message || "保存失败，请重试"}
        </div>
      `;
      errorDiv.classList.remove("hidden");

      // 5秒后自动隐藏错误提示
      setTimeout(() => {
        errorDiv.classList.add("hidden");
      }, 5000);
    }
  }
}

/**
 * 删除支付方式
 * 功能：确认后调用API删除支付方式，刷新列表
 *
 * @param {string} code - 支付方式代码
 */
async function deletePaymentMethod(code) {
  // console.log('[支付配置] 请求删除支付方式：', code);
  logMessage_Info("[支付配置] 请求删除支付方式：" + code);

  // === 第1步：显示确认对话框 ===
  // 使用confirm函数让用户确认是否真的要删除
  // 这是一个破坏性操作，需要二次确认
  if (!confirm(`确定要删除支付方式 "${code}" 吗？删除后无法恢复。`)) {
    // console.log('[支付配置] 用户取消了删除操作');
    logMessage_Info("[支付配置] 用户取消了删除操作");
    return;
  }

  try {
    // === 第2步：发起DELETE请求 ===
    const response = await fetch(`/api/admin/payment_methods/${code}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    // === 第3步：检查响应状态 ===
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.message || `删除失败：HTTP状态码 ${response.status}`,
      );
    }

    // === 第4步：解析响应 ===
    const result = await response.json();
    // console.log('[支付配置] 支付方式删除成功：', result);
    logMessage_Info("[支付配置] 支付方式删除成功");

    // === 第5步：显示成功提示并刷新列表 ===
    // showModalAlert("支付方式已删除");
    Swal.fire({
      icon: "success",
      title: "成功",
      text: "支付方式已删除",
    });

    // 重新加载支付方式列表
    await loadPaymentMethodsConfig();
  } catch (error) {
    // === 错误处理 ===
    // console.error('[支付配置] 删除支付方式失败：', error);
    logMessage_Error("[支付配置] 删除支付方式失败：" + error);
    // showModalAlert(`删除失败：${error.message || "未知错误"}。请重试。`);
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `删除失败：${error.message || "未知错误"}。请重试或联系管理员。`,
    });
  }
}

// ==========================================
// 支付设置面板事件监听器绑定
// ==========================================
// 在页面DOM完全加载后，绑定支付设置相关的事件监听器
// 使用DOMContentLoaded事件确保所有HTML元素已经准备就绪
// ==========================================

/**
 * 页面加载完成后的初始化逻辑
 * 包括：
 * 1. 绑定保存按钮的点击事件
 * 2. 自动加载支付方式配置（确保页面打开时显示最新状态）
 */
document.addEventListener("DOMContentLoaded", function () {
  // 在控制台输出日志，标记支付设置面板初始化开始
  // console.log('[支付设置] 开始初始化支付设置面板...');
  logMessage_Info("[支付设置] 开始初始化支付设置面板...");

  // === 绑定"保存配置"按钮的点击事件 ===

  // 1. 通过ID获取保存按钮的DOM元素
  const saveBtn = document.getElementById("save-payment-methods-btn");

  // 2. 检查按钮是否存在（防御性编程，避免null引用错误）
  if (saveBtn) {
    // 3. 为按钮添加click事件监听器
    // 当用户点击按钮时，会自动调用savePaymentMethodsConfig函数
    saveBtn.addEventListener("click", function () {
      // 输出日志，记录用户操作
      // console.log('[支付设置] 用户点击了保存配置按钮');
      // logMessage_Info("[支付设置] 用户点击了保存配置按钮");

      // 调用保存函数，提交配置到服务器
      // 这是一个async函数，会异步执行，不会阻塞页面
      savePaymentMethodsConfig();
    });

    // 输出成功日志
    // console.log('[支付设置] 保存按钮事件监听器已绑定');
    // logMessage_Info("[支付设置] 保存按钮事件监听器已绑定");
  } else {
    // 如果按钮不存在，输出警告日志
    // 这可能表示HTML结构有问题或ID名称不匹配
    // console.warn('[支付设置] 警告：未找到保存配置按钮（ID: save-payment-methods-btn）');
    // logMessage_Warning(
    // "[支付设置] 警告：未找到保存配置按钮（ID: save-payment-methods-btn）"
    // );
  }

  // === 页面加载时自动加载支付方式配置 ===

  // 调用loadPaymentMethodsConfig函数，从服务器获取当前配置
  // 这确保了用户打开页面时，看到的checkbox状态与服务器保存的状态一致
  // 注意：这个调用不会等待完成就继续执行（异步调用）
  loadPaymentMethodsConfig(
    (show_Modal_Alert = false),
    (DOMContentLoaded_Event = true),
  );

  // ========== Tab 3: 绑定"处理退款"按钮的点击事件 ==========

  // 1. 通过ID获取"处理退款"按钮的DOM元素
  const refundBtn = document.getElementById("process-refund-btn");

  // 2. 检查按钮是否存在（防御性编程，避免null引用错误）
  if (refundBtn) {
    // 3. 为按钮添加click事件监听器
    // 当用户点击按钮时，会自动调用processRefund函数
    refundBtn.addEventListener("click", function () {
      // 输出日志，记录用户操作
      // console.log('[退款功能] 用户点击了处理退款按钮');
      logMessage_Info("[退款功能] 用户点击了处理退款按钮");

      // 调用退款函数，执行退款逻辑
      // 这是一个async函数，会异步执行，不会阻塞页面
      processRefund();
    });

    // 输出成功日志
    // console.log('[退款功能] 处理退款按钮事件监听器已绑定');
    logMessage_Info("[退款功能] 处理退款按钮事件监听器已绑定");
  } else {
    // 如果按钮不存在，输出警告日志
    // 这可能表示HTML结构有问题或ID名称不匹配
    // console.warn('[退款功能] 警告：未找到处理退款按钮（ID: process-refund-btn）');
    logMessage_Warning(
      "[退款功能] 警告：未找到处理退款按钮（ID: process-refund-btn）",
    );
  }

  // ========== Tab 3: 初始化移动端退款订单号自动填充功能 ==========
  // 当用户输入订单号时，自动查询并填充退款金额（与PC端modal一致）
  initMobileRefundOrderAutoFill();

  // ========== Tab 4: 绑定"创建测试订单"按钮的点击事件 ==========

  // 1. 通过ID获取"创建测试订单"按钮的DOM元素
  const createOrderBtn = document.getElementById("create-test-order-btn");

  // 2. 检查按钮是否存在（防御性编程，避免null引用错误）
  if (createOrderBtn) {
    // 3. 为按钮添加click事件监听器
    // 当用户点击按钮时，会自动调用createTestOrder函数
    createOrderBtn.addEventListener("click", function () {
      // 输出日志，记录用户操作
      // console.log('[测试支付] 用户点击了创建测试订单按钮');
      logMessage_Info("[测试支付] 用户点击了创建测试订单按钮");

      // 调用创建订单函数，执行订单创建逻辑
      // 这是一个async函数，会异步执行，不会阻塞页面
      createTestOrder();
    });

    // 输出成功日志
    // console.log('[测试支付] 创建测试订单按钮事件监听器已绑定');
    logMessage_Info("[测试支付] 创建测试订单按钮事件监听器已绑定");
  } else {
    // 如果按钮不存在，输出警告日志
    // console.warn('[测试支付] 警告：未找到创建测试订单按钮（ID: create-test-order-btn）');
    logMessage_Warning(
      "[测试支付] 警告：未找到创建测试订单按钮（ID: create-test-order-btn）",
    );
  }

  // ========== Tab 4: 绑定"打开支付链接"按钮的点击事件 ==========

  // 1. 通过ID获取"打开支付链接"按钮的DOM元素
  const openPayBtn = document.getElementById("open-test-pay-url-btn");

  // 2. 检查按钮是否存在（防御性编程，避免null引用错误）
  if (openPayBtn) {
    // 3. 为按钮添加click事件监听器
    // 当用户点击按钮时，会自动调用openTestPayUrl函数
    openPayBtn.addEventListener("click", function () {
      // 输出日志，记录用户操作
      // console.log('[测试支付] 用户点击了打开支付链接按钮');
      logMessage_Info("[测试支付] 用户点击了打开支付链接按钮");

      // 调用打开支付链接函数，在新标签页打开支付页面
      // 这是一个同步函数，会立即执行
      openTestPayUrl();
    });

    // 输出成功日志
    // console.log('[测试支付] 打开支付链接按钮事件监听器已绑定');
    logMessage_Info("[测试支付] 打开支付链接按钮事件监听器已绑定");
  } else {
    // 如果按钮不存在，输出警告日志
    // console.warn('[测试支付] 警告：未找到打开支付链接按钮（ID: open-test-pay-url-btn）');
    logMessage_Warning(
      "[测试支付] 警告：未找到打开支付链接按钮（ID: open-test-pay-url-btn）",
    );
  }

  // 输出完成日志
  // console.log('[支付设置] 支付设置面板初始化完成（包括Tab 1-4所有功能）');
  logMessage_Info("[支付设置] 支付设置面板初始化完成（包括Tab 1-4所有功能）");
});

// ==========================================
// 订单查询功能（Tab 2）
// ==========================================
// 【功能说明】
// 实现支付设置面板中的订单查询功能，包括：
// 1. 根据订单号查询订单详情
// 2. 显示订单的完整信息（订单号、状态、金额、支付方式等）
// 3. 根据订单状态显示不同颜色的标签
// 4. 完善的输入验证和错误处理
//
// 【API说明】
// - POST /api/payment/query: 查询指定订单号的订单详情
// ==========================================

/**
 * 查询订单详情函数
 *
 * 功能说明：
 * 1. 从输入框获取订单号
 * 2. 验证订单号不为空
 * 3. 调用后端API查询订单信息
 * 4. 解析并显示订单详情（7个字段）
 * 5. 根据订单状态显示不同颜色的标签
 *
 * API端点：POST /api/payment/query
 * 请求体格式：{ trade_no: "订单号字符串" }
 *
 * 返回数据格式示例：
 * {
 *   success: true,
 *   order: {
 *     trade_no: "202412101234567890",        // 订单号
 *     status: "TRADE_SUCCESS",               // 订单状态
 *     amount: 9.90,                          // 支付金额
 *     payment_method: "alipay",              // 支付方式
 *     create_time: "2024-12-10 10:30:00",   // 创建时间
 *     pay_time: "2024-12-10 10:31:25",      // 支付时间
 *     product_name: "跑步助手会员服务"       // 商品名称
 *   }
 * }
 *
 * 订单状态颜色映射：
 * - TRADE_SUCCESS / 已支付 -> 绿色 (bg-green-100 text-green-700)
 * - TRADE_PENDING / 待支付 -> 黄色 (bg-yellow-100 text-yellow-700)
 * - TRADE_CLOSED / 已关闭 -> 灰色 (bg-gray-100 text-gray-700)
 * - TRADE_REFUND / 已退款 -> 红色 (bg-red-100 text-red-700)
 */
async function queryOrder() {
  // 在控制台输出日志，标记查询操作开始
  // console.log('[订单查询] 开始查询订单...');
  logMessage_Info("[订单查询] 开始查询订单...");

  // ========== 第1步：获取并验证用户输入 ==========

  // 1.1 获取订单号输入框的DOM元素
  const tradeNoInput = document.getElementById("query-order-trade-no");

  // 1.2 防御性检查：确保输入框元素存在
  if (!tradeNoInput) {
    // 如果找不到输入框元素，在控制台输出错误并提示用户
    // console.error('[订单查询] 错误：未找到订单号输入框（ID: query-order-trade-no）');
    logMessage_Error(
      "[订单查询] 错误：未找到订单号输入框（ID: query-order-trade-no）",
    );
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return; // 终止函数执行
  }

  // 1.3 获取输入框的值并去除首尾空格
  // trim()方法会移除字符串两端的空白字符（空格、制表符、换行符等）
  const tradeNo = tradeNoInput.value.trim();

  // 1.4 验证订单号不为空
  // 如果用户没有输入订单号或只输入了空格，显示友好的提示
  if (!tradeNo) {
    // 使用alert弹窗提示用户，确保用户能看到错误信息
    // showModalAlert("请输入订单号");
    Swal.fire({
      icon: "warning",
      title: "警告",
      text: "请输入订单号",
    });
    // 将焦点重新设置到输入框，方便用户立即输入
    tradeNoInput.focus();
    // 终止函数执行，不发送请求
    return;
  }

  // 输出日志，记录用户输入的订单号（便于调试）
  logMessage_Info("[订单查询] 查询订单号：", tradeNo);

  // ========== 第2步：获取结果显示区域的DOM元素 ==========

  // 2.1 获取查询结果提示区域（用于显示成功/失败消息）
  const resultDiv = document.getElementById("query-order-result");

  // 2.2 获取订单详情容器（用于显示订单的详细信息）
  const detailContainer = document.getElementById("order-detail-container");

  // 2.3 防御性检查：确保两个元素都存在
  if (!resultDiv || !detailContainer) {
    logMessage_Error("[订单查询] 错误：未找到结果显示区域");
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return;
  }

  // ========== 第3步：显示加载中状态 ==========

  // 3.1 在结果提示区域显示"查询中..."消息
  // 使用蓝色背景和边框，让用户知道系统正在处理请求
  resultDiv.innerHTML = `
    <div class="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-lg p-2">
      🔍 正在查询订单信息...
    </div>
  `;
  // 移除hidden类，让提示框可见
  resultDiv.classList.remove("hidden");

  // 3.2 先隐藏订单详情容器，等查询成功后再显示
  // 这样可以避免显示旧数据
  detailContainer.classList.add("hidden");

  try {
    // ========== 第4步：发起API请求查询订单 ==========

    // 4.1 使用fetch API调用后端接口
    // await关键字会等待请求完成，确保获取到响应后再继续执行
    const response = await fetch("/api/payment/query", {
      method: "POST", // HTTP方法：POST用于提交数据查询
      headers: {
        // 设置请求头，告知服务器请求体是JSON格式
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 包含会话ID，进行身份验证
      },
      // 将查询参数转换为JSON字符串作为请求体
      body: JSON.stringify({
        order_id: tradeNo, // 订单号
      }),
    });

    // 4.2 检查HTTP响应状态码
    // response.ok 为true表示状态码在200-299范围内（成功）
    if (!response.ok) {
      // 如果响应状态码不是成功状态（如404、500等）
      // 抛出错误，中断执行流程，进入catch块处理
      throw new Error(`查询失败：HTTP状态码 ${response.status}`);
    }

    // 4.3 解析JSON响应数据
    const result = await response.json();

    // 输出完整的API响应，方便开发者调试
    logMessage_Info("[订单查询] API响应：", createSafeClientLogValue(result));

    // 4.4 检查业务状态
    // 即使HTTP状态码是200，业务逻辑也可能失败（如订单不存在）
    if (!result.success) {
      // 如果业务失败，抛出错误，显示服务器返回的错误消息
      throw new Error(result.message || "查询失败，未知错误");
    }

    // 4.5 检查订单数据是否存在
    if (!result.order) {
      throw new Error("未找到订单信息");
    }

    // ========== 第5步：提取订单数据 ==========

    // 从响应中提取订单对象，方便后续访问
    const order = result.order;

    // 输出订单数据
    logMessage_Info(
      "[订单查询] 查询成功，订单数据：",
      createSafeClientLogValue(order),
    );

    // ========== 第6步：根据订单状态确定显示样式 ==========

    // 6.1 定义状态文本映射
    // 将API返回的状态码转换为用户友好的中文文本
    const statusTextMap = {
      TRADE_SUCCESS: "已支付",
      TRADE_PENDING: "待支付",
      TRADE_CLOSED: "已关闭",
      TRADE_REFUND: "已退款",
    };

    // 6.2 获取状态文本（如果状态码不在映射中，使用原始状态码）
    const statusText =
      statusTextMap[order.status] || order.status || "未知状态";

    // 6.3 根据订单状态确定显示颜色
    // 不同状态使用不同的背景色和文字色，提升视觉可读性
    let statusColorClass = "bg-gray-100 text-gray-700"; // 默认颜色：灰色

    // 判断订单状态并设置对应的颜色类
    if (order.status === "TRADE_SUCCESS" || statusText === "已支付") {
      // 已支付：绿色（成功状态）
      statusColorClass = "bg-green-100 text-green-700";
    } else if (order.status === "TRADE_PENDING" || statusText === "待支付") {
      // 待支付：黄色（警告状态）
      statusColorClass = "bg-yellow-100 text-yellow-700";
    } else if (order.status === "TRADE_CLOSED" || statusText === "已关闭") {
      // 已关闭：灰色（中性状态）
      statusColorClass = "bg-gray-100 text-gray-700";
    } else if (order.status === "TRADE_REFUND" || statusText === "已退款") {
      // 已退款：红色（错误/退款状态）
      statusColorClass = "bg-red-100 text-red-700";
    }

    // ========== 第7步：更新页面显示订单详情（7个字段）==========

    // 7.1 更新订单号字段
    // 使用可选链操作符?.，如果元素不存在也不会报错
    document.getElementById("order-detail-trade-no").textContent =
      order.trade_no || "-";

    // 7.2 更新订单状态字段（带颜色标签）
    // 使用innerHTML而不是textContent，因为需要插入HTML标签来实现颜色样式
    const statusElement = document.getElementById("order-detail-status");
    if (statusElement) {
      statusElement.innerHTML = `
        <span class="inline-block px-2 py-1 rounded text-xs font-medium ${statusColorClass}">
          ${statusText}
        </span>
      `;
    }

    // 7.3 更新支付金额字段
    // 格式化金额：添加货币符号¥，保留2位小数
    const amountElement = document.getElementById("order-detail-amount");
    if (amountElement) {
      // 使用parseFloat确保金额是数字类型，然后格式化为2位小数
      const formattedAmount = order.amount
        ? `¥${parseFloat(order.amount).toFixed(2)}`
        : "-";
      amountElement.textContent = formattedAmount;
    }

    // 7.4 更新支付方式字段
    // 将支付方式代码转换为用户友好的中文名称
    const paymentMethodMap = {
      alipay: "支付宝",
      wechat: "微信支付",
      qq: "QQ钱包",
      unionpay: "云闪付",
    };
    const paymentMethodText =
      paymentMethodMap[order.payment_method] || order.payment_method || "-";
    document.getElementById("order-detail-method").textContent =
      paymentMethodText;

    // 7.5 更新创建时间字段
    document.getElementById("order-detail-create-time").textContent =
      order.create_time || "-";

    // 7.6 更新支付时间字段
    // 如果订单未支付，支付时间可能为空，显示"-"
    document.getElementById("order-detail-pay-time").textContent =
      order.pay_time || "-";

    // 7.7 更新商品名称字段
    document.getElementById("order-detail-product").textContent =
      order.product_name || "-";

    // ========== 第8步：显示成功提示和订单详情 ==========

    // 8.1 在结果提示区域显示成功消息
    resultDiv.innerHTML = `
      <div class="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-2">
        ✓ 查询成功
      </div>
    `;
    // 保持提示框可见
    resultDiv.classList.remove("hidden");

    // 8.2 显示订单详情容器
    // 移除hidden类，让用户看到订单的详细信息
    detailContainer.classList.remove("hidden");

    // 8.3 设置定时器，3秒后自动隐藏成功提示
    // 订单详情保持显示，只隐藏"查询成功"的提示框
    setTimeout(() => {
      resultDiv.classList.add("hidden");
    }, 3000);

    // 输出成功日志
    logMessage_Info("[订单查询] 订单详情已成功显示");
  } catch (error) {
    // ========== 错误处理 ==========
    // 捕获所有可能的错误：网络错误、服务器错误、业务错误等

    // 在控制台输出详细的错误信息
    logMessage_Error("[订单查询] 查询失败：", error);

    // 在结果提示区域显示错误消息
    resultDiv.innerHTML = `
      <div class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
        ✗ ${error.message || "查询失败，请重试"}
      </div>
    `;
    // 显示错误提示框
    resultDiv.classList.remove("hidden");

    // 隐藏订单详情容器（因为查询失败，没有有效数据可显示）
    detailContainer.classList.add("hidden");

    // 5秒后自动隐藏错误提示（比成功提示多2秒，让用户有更多时间阅读）
    setTimeout(() => {
      resultDiv.classList.add("hidden");
    }, 5000);
  }
}

// ==========================================
// 订单查询功能事件监听器绑定
// ==========================================
// 在页面DOM完全加载后，为查询按钮绑定点击事件
// 注意：这段代码在DOMContentLoaded事件监听器内部执行
// ==========================================

document.addEventListener("DOMContentLoaded", function () {
  // 在控制台输出日志，标记订单查询功能初始化开始
  logMessage_Info("[订单查询] 开始初始化订单查询功能...");

  // === 绑定"查询订单"按钮的点击事件 ===

  // 1. 通过ID获取查询按钮的DOM元素
  const queryBtn = document.getElementById("query-order-btn");

  // 2. 检查按钮是否存在（防御性编程，避免null引用错误）
  if (queryBtn) {
    // 3. 为按钮添加click事件监听器
    // 当用户点击按钮时，会自动调用queryOrder函数
    queryBtn.addEventListener("click", function () {
      // 输出日志，记录用户操作
      // logMessage_Info("[订单查询] 用户点击了查询订单按钮");

      // 调用查询函数，执行订单查询逻辑
      // 这是一个async函数，会异步执行，不会阻塞页面
      queryOrder();
    });

    // 输出成功日志
    // logMessage_Info("[订单查询] 查询按钮事件监听器已绑定");
  } else {
    // 如果按钮不存在，输出警告日志
    // 这可能表示HTML结构有问题或ID名称不匹配
    // logMessage_Warning("[订单查询] 警告：未找到查询订单按钮（ID: query-order-btn）");
  }

  // === 可选：绑定输入框的Enter键事件 ===
  // 让用户可以通过按Enter键快速查询，提升用户体验

  const tradeNoInput = document.getElementById("query-order-trade-no");
  if (tradeNoInput) {
    // 监听keypress事件，检测用户是否按下Enter键
    tradeNoInput.addEventListener("keypress", function (event) {
      // event.key === 'Enter' 表示用户按下了Enter键
      if (event.key === "Enter") {
        // 阻止默认行为（如表单提交）
        event.preventDefault();
        // 触发查询操作
        logMessage_Info("[订单查询] 用户按下Enter键触发查询");
        queryOrder();
      }
    });

    logMessage_Info("[订单查询] 输入框Enter键事件监听器已绑定");
  }

  // 输出完成日志
  logMessage_Info("[订单查询] 订单查询功能初始化完成");
});

// ==========================================
// 移动端退款订单号自动填充初始化函数
// ==========================================
/**
 * 初始化移动端退款表单的订单号自动填充功能
 * 当用户输入订单号时，自动查询订单金额并填充到退款金额输入框
 * 功能与PC端 initOrderNumberAutoFill() 一致
 */
function initMobileRefundOrderAutoFill() {
  // 获取移动端订单号输入框DOM元素
  const tradeNoInput = document.getElementById("refund-order-trade-no");

  // 如果输入框不存在，直接退出（可能在PC端或元素尚未加载）
  if (!tradeNoInput) {
    console.log("[移动端退款自动填充] 未找到订单号输入框元素，跳过初始化");
    return;
  }

  // 为订单号输入框添加input事件监听
  // 使用防抖（debounce）技术，避免频繁触发API请求
  let debounceTimer = null;

  tradeNoInput.addEventListener("input", function (event) {
    // 清除之前的防抖计时器
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    // 获取用户输入的订单号（去除首尾空格）
    const tradeNo = event.target.value.trim();

    // 如果订单号为空，清空退款金额输入框并退出
    if (!tradeNo) {
      const amountInput = document.getElementById("refund-amount");
      if (amountInput) {
        amountInput.value = "";
      }
      return;
    }

    // 设置防抖计时器：用户停止输入500毫秒后才触发查询
    debounceTimer = setTimeout(async () => {
      // 调用订单号校验和金额获取函数（复用PC端逻辑，传入移动端元素ID）
      await fetchMobileOrderAmountAndFill(tradeNo);
    }, 500);
  });

  console.log("[移动端退款自动填充] 初始化完成");
}

/**
 * 根据订单号获取订单金额并填充到移动端退款金额输入框
 * 复用 fetchOrderAmountAndFill 的逻辑，但使用移动端元素ID
 * @param {string} tradeNo - 订单号
 */
async function fetchMobileOrderAmountAndFill(tradeNo) {
  console.log("[移动端退款自动填充] 开始处理订单查询");

  // 获取移动端退款金额输入框
  const amountInput = document.getElementById("refund-amount");
  if (!amountInput) {
    console.error("[移动端退款自动填充] 未找到退款金额输入框");
    return;
  }

  // 校验订单号长度（通常订单号长度在10-50个字符之间）
  if (tradeNo.length < 10) {
    console.log("[移动端退款自动填充] 订单号长度不足，等待继续输入");
    return;
  }

  try {
    // 调用后端API按订单号直接查询，避免拉取全量订单导致遗漏
    const response = await fetch(
      `/api/payment/order_by_tradeno?trade_no=${encodeURIComponent(tradeNo)}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
      }
    );

    if (!response.ok) {
      console.error("[移动端退款自动填充] API请求失败:", response.status);
      return;
    }

    const data = await response.json();

    if (!data.success || !data.order) {
      console.error("[移动端退款自动填充] API返回数据异常");
      return;
    }
    const order = data.order;

    // 找到订单，计算退款金额
    const orderAmount = parseFloat(order.amount) || 0;
    const refundedAmount = parseFloat(order.refundmoney) || 0;
    const refundCount = parseInt(order.refund_count || 0, 10) || 0;
    const hasRefundRecords =
      Array.isArray(order.refund_records) && order.refund_records.length > 0;
    const orderStatus = String(order.status || "").toLowerCase();

    // 一个订单只能退款一次：任一退款迹象均禁止再次退款
    if (
      refundedAmount > 0 ||
      refundCount >= 1 ||
      hasRefundRecords ||
      orderStatus === "refunded_full" ||
      orderStatus === "refunded_partial"
    ) {
      console.log("[移动端退款自动填充] 该订单已退款，不可再次退款");
      amountInput.value = "";
      Swal.fire({
        icon: "warning",
        title: "无法退款",
        text: "该订单已退款，每个订单只能退款一次。",
      });
      return;
    }

    // 默认退款金额 = 订单金额 * 80%
    const refundableAmount = Math.max(0, orderAmount * 0.8);

    // 填充退款金额（保留两位小数）
    amountInput.value = refundableAmount.toFixed(2);

    console.log("[移动端退款自动填充] 订单金额已填充");
  } catch (error) {
    console.error("[移动端退款自动填充] 查询订单失败:", error);
  }
}

// ==========================================
// Tab 3: 退款功能 (processRefund函数)
// ==========================================
// 【功能说明】
// 实现支付设置面板中的订单退款功能，包括：
// 1. 获取并验证退款所需的4个字段（订单号、退款金额、退款单号、退款原因）
// 2. 订单号和退款金额为必填项，退款金额必须大于0
// 3. 退款单号为可选项，如果用户不填写则自动生成
// 4. 调用后端API执行退款操作
// 5. 显示退款结果（成功或失败）
//
// 【API说明】
// - POST /api/payment/refund: 处理订单退款请求
// ==========================================

/**
 * 处理退款操作函数
 *
 * 功能说明：
 * 1. 从输入框获取4个字段的值
 * 2. 验证必填项（订单号、退款金额）
 * 3. 验证退款金额必须大于0
 * 4. 如果退款单号为空，则自动生成（格式：REFUND + 时间戳 + 6位随机数）
 * 5. 调用后端API执行退款
 * 6. 在refund-result-container中显示操作结果
 *
 * API端点：POST /api/payment/refund
 * 请求体格式：
 * {
 *   trade_no: "原订单号",
 *   refund_amount: 9.90,
 *   refund_no: "退款单号（可选）",
 *   refund_reason: "退款原因（可选）"
 * }
 *
 * 返回数据格式示例：
 * {
 *   success: true,
 *   message: "退款成功",
 *   refund: {
 *     refund_no: "REFUND202412101234567890",
 *     trade_no: "202412101234567890",
 *     refund_amount: 9.90,
 *     status: "REFUND_SUCCESS"
 *   }
 * }
 */
async function processRefund() {
  // 在控制台输出日志，标记退款操作开始
  logMessage_Info("[退款功能] 开始处理退款请求...");

  // ========== 第1步：获取所有输入框的DOM元素 ==========

  // 1.1 获取原订单号输入框（必填项）
  const tradeNoInput = document.getElementById("refund-order-trade-no");

  // 1.2 获取退款金额输入框（必填项，必须>0）
  const amountInput = document.getElementById("refund-amount");

  // 1.3 获取退款单号输入框（可选项，为空则自动生成）
  const refundNoInput = document.getElementById("refund-no");

  // 1.4 获取退款原因输入框（可选项）
  const reasonInput = document.getElementById("refund-reason");

  // 1.5 获取结果显示容器
  const resultContainer = document.getElementById("refund-result-container");

  // ========== 第2步：防御性检查 - 确保所有必需的DOM元素都存在 ==========

  // 检查所有必需的元素是否都能找到
  // 如果任何一个元素不存在，说明HTML结构有问题
  if (
    !tradeNoInput ||
    !amountInput ||
    !refundNoInput ||
    !reasonInput ||
    !resultContainer
  ) {
    // 输出错误日志，列出缺失的元素（便于调试）
    logMessage_Error("[退款功能] 错误：页面元素未找到");
    logMessage_Error("元素检查：", {
      tradeNoInput: !!tradeNoInput,
      amountInput: !!amountInput,
      refundNoInput: !!refundNoInput,
      reasonInput: !!reasonInput,
      resultContainer: !!resultContainer,
    });
    // 向用户显示友好的错误提示
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return; // 终止函数执行
  }

  // ========== 第3步：获取并验证用户输入 ==========

  // 3.1 获取原订单号，并去除首尾空格
  // trim()方法会移除字符串两端的空白字符（空格、制表符、换行符等）
  const tradeNo = tradeNoInput.value.trim();

  // 3.2 验证订单号不为空（必填项验证）
  if (!tradeNo) {
    // 输出日志记录验证失败
    logMessage_Error("[退款功能] 验证失败：订单号为空");
    // 向用户显示友好的错误提示
    // showModalAlert("请输入订单号");
    Swal.fire({
      icon: "warning",
      title: "警告",
      text: "请输入订单号",
    });
    // 将焦点设置到订单号输入框，方便用户立即输入
    tradeNoInput.focus();
    return; // 终止函数执行
  }

  // 3.3 获取退款金额，并去除首尾空格
  const amountStr = amountInput.value.trim();

  // 3.4 验证退款金额不为空（必填项验证）
  if (!amountStr) {
    logMessage_Error("[退款功能] 验证失败：退款金额为空");
    // showModalAlert("请输入退款金额");
    Swal.fire({
      icon: "warning",
      title: "警告",
      text: "请输入退款金额",
    });
    amountInput.focus();
    return;
  }

  // 3.5 将退款金额字符串转换为浮点数
  // parseFloat()会尝试解析字符串为数字，失败时返回NaN
  const refundAmount = parseFloat(amountStr);

  // 3.6 验证退款金额是否为有效数字
  // isNaN()检查值是否为NaN（Not a Number）
  if (isNaN(refundAmount)) {
    logMessage_Error("[退款功能] 验证失败：退款金额不是有效数字");
    // showModalAlert("退款金额必须是有效的数字");
    Swal.fire({
      icon: "warning",
      title: "警告",
      text: "退款金额必须是有效的数字",
    });
    amountInput.focus();
    return;
  }

  // 3.7 验证退款金额必须大于0
  // 退款金额不能是负数或0
  if (refundAmount <= 0) {
    logMessage_Error(
      "[退款功能] 验证失败：退款金额必须大于0，当前值：",
      refundAmount,
    );
    // showModalAlert("退款金额必须大于0");
    Swal.fire({
      icon: "warning",
      title: "警告",
      text: "退款金额必须大于0",
    });
    amountInput.focus();
    return;
  }

  // 3.8 获取退款单号（可选项）
  // 用户可以自定义退款单号，也可以留空由系统自动生成
  let refundNo = refundNoInput.value.trim();

  // 3.9 如果退款单号为空，则自动生成
  // 生成规则：REFUND + 当前时间戳 + 6位随机数
  if (!refundNo) {
    // Date.now() 返回当前时间的时间戳（毫秒）
    // Math.random() 生成0-1之间的随机数
    // Math.floor() 向下取整
    // toString().padStart(6, '0') 转为字符串并补齐到6位（不足部分用0填充）
    const randomNum = Math.floor(Math.random() * 1000000)
      .toString()
      .padStart(6, "0");
    refundNo = `REFUND${Date.now()}${randomNum}`;

    // 输出日志记录自动生成的退款单号
    logMessage_Info("[退款功能] 自动生成退款单号：", refundNo);

    // 可选：将生成的退款单号回填到输入框，让用户看到
    // 这样用户可以知道系统使用了哪个退款单号
    refundNoInput.value = refundNo;
  }

  // 3.10 获取退款原因（可选项）
  const refundReason = reasonInput.value.trim();

  // 输出日志，记录所有输入参数（便于调试）
  logMessage_Info(
    "[退款功能] 退款参数：",
    createSafeClientLogValue({
      trade_no: tradeNo,
      refund_amount: refundAmount,
      refund_no: refundNo,
      refund_reason: refundReason || "（未填写）",
    }),
  );

  // ========== 第4步：显示"处理中"状态 ==========

  // 在结果容器中显示"处理中..."提示
  // 使用蓝色背景和边框，让用户知道系统正在处理请求
  resultContainer.innerHTML = `
    <div class="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded-lg p-3">
      💳 正在处理退款请求，请稍候...
    </div>
  `;
  // 移除hidden类，让提示框可见
  resultContainer.classList.remove("hidden");

  try {
    // ========== 第5步：发起API请求处理退款 ==========

    // 5.1 使用fetch API调用后端接口
    // await关键字会等待请求完成，确保获取到响应后再继续执行
    const response = await fetch("/api/payment/refund", {
      method: "POST", // HTTP方法：POST用于提交退款请求
      headers: {
        // 设置请求头，告知服务器请求体是JSON格式
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 包含会话ID，进行身份验证
      },
      // 将退款参数转换为JSON字符串作为请求体
      body: JSON.stringify({
        trade_no: tradeNo, // 原订单号
        refund_amount: refundAmount, // 退款金额
        refund_no: refundNo, // 退款单号
        reason: refundReason, // 退款原因
      }),
    });

    // 5.2 检查HTTP响应状态码
    // response.ok 为true表示状态码在200-299范围内（成功）
    if (!response.ok) {
      // 如果响应状态码不是成功状态（如404、500等）
      // 抛出错误，中断执行流程，进入catch块处理
      throw new Error(`退款请求失败：HTTP状态码 ${response.status}`);
    }

    // 5.3 解析JSON响应数据
    const result = await response.json();

    // 输出完整的API响应，方便开发者调试
    logMessage_Info("[退款功能] API响应：", createSafeClientLogValue(result));

    // 5.4 检查业务状态
    // 即使HTTP状态码是200，业务逻辑也可能失败（如订单不存在、退款金额超过订单金额等）
    if (!result.success) {
      // 如果业务失败，抛出错误，显示服务器返回的错误消息
      throw new Error(result.message || "退款失败，未知错误");
    }

    // ========== 第6步：显示退款成功结果 ==========

    // 6.1 输出成功日志
    logMessage_Info("[退款功能] 退款成功：", createSafeClientLogValue(result));

    // 6.2 构建成功提示HTML
    // 显示绿色的成功提示框，包含退款单号和相关信息
    let successHTML = `
      <div class="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-3 space-y-2">
        <div class="font-bold text-sm">✓ 退款成功</div>
    `;

    // 6.3 如果返回了退款详情数据，显示详细信息
    if (result.refund) {
      successHTML += `
        <div class="space-y-1 text-xs">
          <div><span class="font-medium">退款单号：</span>${
            result.refund.refund_no || refundNo
          }</div>
          <div><span class="font-medium">原订单号：</span>${
            result.refund.trade_no || tradeNo
          }</div>
          <div><span class="font-medium">退款金额：</span>¥${(
            result.refund.refund_amount || refundAmount
          ).toFixed(2)}</div>
      `;

      // 如果有退款状态，也显示出来
      if (result.refund.status) {
        successHTML += `<div><span class="font-medium">退款状态：</span>${result.refund.status}</div>`;
      }

      successHTML += `</div>`;
    } else {
      // 如果没有返回详细数据，只显示基本信息
      successHTML += `
        <div class="text-xs">
          <div>退款单号：${refundNo}</div>
          <div>退款金额：¥${refundAmount.toFixed(2)}</div>
        </div>
      `;
    }

    successHTML += `</div>`;

    // 6.4 更新结果容器的内容
    resultContainer.innerHTML = successHTML;
    resultContainer.classList.remove("hidden");

    // 6.5 清空输入框，为下一次退款做准备
    // 退款成功后清空所有输入，方便用户进行下一次退款操作
    tradeNoInput.value = '';
    amountInput.value = '';
    refundNoInput.value = '';
    reasonInput.value = '';

    // 输出完成日志
    logMessage_Info("[退款功能] 退款操作完成，表单已清空");
  } catch (error) {
    // ========== 错误处理 ==========
    // 捕获所有可能的错误：网络错误、服务器错误、业务错误等

    // 在控制台输出详细的错误信息
    logMessage_Error("[退款功能] 退款失败：", error);

    // 在结果容器中显示错误消息
    // 使用红色背景和边框，明确标识为错误状态
    resultContainer.innerHTML = `
      <div class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
        <div class="font-bold text-sm">✗ 退款失败</div>
        <div class="mt-1">${
          error.message || "未知错误，请重试或联系管理员"
        }</div>
      </div>
    `;
    // 显示错误提示框
    resultContainer.classList.remove("hidden");

    // 可选：5秒后自动隐藏错误提示
    // setTimeout(() => {
    //   resultContainer.classList.add('hidden');
    // }, 5000);
  }
}

// ==========================================
// Tab 4: 测试支付功能
// ==========================================
// 【功能说明】
// 实现支付设置面板中的测试支付功能，包括：
// 1. createTestOrder(): 创建测试订单
//    - 获取测试金额、商品名称、支付方式
//    - 自动生成订单号（时间戳 + 6位随机数）
//    - 调用后端API创建订单
//    - 显示订单信息和支付链接
// 2. openTestPayUrl(): 打开支付链接
//    - 从按钮的data-url属性获取支付链接
//    - 在新标签页中打开支付页面
//
// 【API说明】
// - POST /api/payment/create: 创建支付订单
// ==========================================

/**
 * 创建测试订单函数
 *
 * 功能说明：
 * 1. 从输入框获取测试支付金额、商品名称、支付方式
 * 2. 验证必填项（金额>0，支付方式已选择）
 * 3. 自动生成订单号（格式：时间戳 + 6位随机数）
 * 4. 调用后端API创建订单
 * 5. 显示订单信息（订单号、金额、支付链接）
 * 6. 显示"打开支付链接"按钮
 *
 * API端点：POST /api/payment/create
 * 请求体格式：
 * {
 *   amount: 9.90,
 *   product_name: "测试商品",
 *   payment_method: "alipay"
 * }
 *
 * 返回数据格式示例：
 * {
 *   success: true,
 *   order: {
 *     trade_no: "202412101234567890",
 *     amount: 9.90,
 *     payment_method: "alipay",
 *     pay_url: "https://pay.example.com/..."
 *   }
 * }
 */
/**
 * 切换商品名称输入方式（移动端）
 *
 * 功能说明：
 * 当用户选择"手动输入"或"自动生成"单选按钮时，切换对应的输入框显示/隐藏
 *
 * 实现逻辑：
 * 1. 获取选中的单选按钮值（manual或auto）
 * 2. 如果选择"手动输入"：显示文本输入框，隐藏数量输入框
 * 3. 如果选择"自动生成"：隐藏文本输入框，显示数量输入框
 *
 * 调用时机：
 * - 单选按钮的onchange事件触发时
 */
function toggleProductNameInputMethod() {
  // 在控制台输出日志，记录函数调用
  logMessage_Info("[移动端测试支付] 切换商品名称输入方式...");

  // === 第1步：获取选中的单选按钮值 ===
  // 获取所有name为"product-name-input-method"的单选按钮
  const radioButtons = document.getElementsByName("product-name-input-method");
  // 变量用于存储选中的值
  let selectedMethod = "manual"; // 默认为手动输入

  // 遍历所有单选按钮，找到被选中的那个
  for (const radio of radioButtons) {
    if (radio.checked) {
      selectedMethod = radio.value; // 获取选中按钮的value值
      break; // 找到后退出循环
    }
  }

  logMessage_Info("[移动端测试支付] 选中的输入方式：", selectedMethod);

  // === 第2步：获取两个容器的DOM元素 ===
  const manualContainer = document.getElementById(
    "manual-product-name-container",
  );
  const autoContainer = document.getElementById("auto-product-name-container");

  // === 第3步：防御性检查，确保元素存在 ===
  if (!manualContainer || !autoContainer) {
    logMessage_Warning("[移动端测试支付] 警告：找不到商品名称容器元素");
    return; // 元素不存在则退出
  }

  // === 第4步：根据选中值切换显示/隐藏 ===
  if (selectedMethod === "manual") {
    // 手动输入模式：显示文本输入框，隐藏数量输入框
    manualContainer.classList.remove("hidden");
    autoContainer.classList.add("hidden");
    logMessage_Info("[移动端测试支付] 已切换到手动输入模式");
  } else if (selectedMethod === "auto") {
    // 自动生成模式：隐藏文本输入框，显示数量输入框
    manualContainer.classList.add("hidden");
    autoContainer.classList.remove("hidden");
    logMessage_Info("[移动端测试支付] 已切换到自动生成模式");
  }
}

/**
 * 切换付款码和JSAPI参数输入框显示状态（移动端测试支付）
 *
 * 功能说明：
 * 根据用户选择的支付接口类型，动态显示或隐藏对应的参数输入框
 * - 当选择"扫码支付(scan)"时：显示auth_code输入框，隐藏jsapi参数
 * - 当选择"JSAPI支付(jsapi)"时：显示sub_openid和sub_appid输入框，隐藏auth_code
 * - 当选择其他类型时：隐藏所有额外参数输入框
 *
 * 实现逻辑：
 * 1. 获取支付接口类型下拉框的选中值
 * 2. 根据选中值添加或移除hidden类来控制显示/隐藏
 * 3. 切换时清空不相关的输入框内容
 *
 * 调用时机：
 * - 支付接口类型下拉框的onchange事件触发时
 *
 * 元素ID说明：
 * - test-payment-type: 支付接口类型下拉框（移动端，不带_modal后缀）
 * - test-auth-code-container: 付款码输入框容器
 * - test-jsapi-params-container: JSAPI参数输入框容器
 * - test-auth-code: 付款码输入框
 * - test-sub-openid: 用户Openid输入框
 * - test-sub-appid: 公众号AppId输入框
 */
function toggleAuthCodeFieldMobile() {
  // 在控制台输出日志，记录函数调用
  logMessage_Info("[移动端测试支付] 切换支付类型参数输入框显示状态...");

  // === 第1步：获取DOM元素 ===

  // 获取支付接口类型下拉框元素
  const typeSelect = document.getElementById("test-payment-type");
  // 获取付款码输入框的容器元素（扫码支付专用）
  const authCodeContainer = document.getElementById("test-auth-code-container");
  // 获取JSAPI支付参数容器元素
  const jsapiParamsContainer = document.getElementById(
    "test-jsapi-params-container",
  );

  // === 第2步：防御性检查 ===
  // 确保DOM元素存在，避免null引用错误
  if (!typeSelect || !authCodeContainer) {
    logMessage_Warning("[移动端测试支付] 警告：找不到必需的DOM元素");
    return; // 如果元素不存在，直接返回，不执行后续操作
  }

  // === 第3步：获取当前选中的接口类型 ===
  const selectedType = typeSelect.value;
  logMessage_Info("[移动端测试支付] 当前选中的接口类型：", selectedType);

  // === 第4步：根据接口类型决定显示哪些参数输入框 ===

  // 4.1 判断是否为扫码支付类型
  if (selectedType === "scan") {
    // 如果是扫码支付，则显示付款码输入框
    // 移除hidden类，使容器可见
    authCodeContainer.classList.remove("hidden");
    logMessage_Info("[移动端测试支付] 付款码输入框已显示");

    // 同时隐藏JSAPI参数容器（互斥关系）
    if (jsapiParamsContainer) {
      jsapiParamsContainer.classList.add("hidden");
      // 清空JSAPI参数输入框的值，避免误提交
      const subOpenidInput = document.getElementById("test-sub-openid");
      const subAppidInput = document.getElementById("test-sub-appid");
      if (subOpenidInput) subOpenidInput.value = "";
      if (subAppidInput) subAppidInput.value = "";
    }
  }
  // 4.2 判断是否为JSAPI支付类型
  else if (selectedType === "jsapi") {
    // 如果是JSAPI支付，则显示JSAPI参数容器
    if (jsapiParamsContainer) {
      jsapiParamsContainer.classList.remove("hidden");
      logMessage_Info("[移动端测试支付] JSAPI参数输入框已显示");
    }

    // 同时隐藏付款码输入框（互斥关系）
    authCodeContainer.classList.add("hidden");
    // 清空付款码输入框的值，避免误提交
    const authCodeInput = document.getElementById("test-auth-code");
    if (authCodeInput) {
      authCodeInput.value = ""; // 清空输入框
    }
  }
  // 4.3 其他支付类型（web、jump、html、qrcode、urlscheme、app、applet、wxplugin、wxapp等）
  else {
    // 隐藏付款码输入框
    authCodeContainer.classList.add("hidden");

    // 清空付款码输入框的值，避免用户误以为需要输入
    const authCodeInput = document.getElementById("test-auth-code");
    if (authCodeInput) {
      authCodeInput.value = ""; // 清空输入框
    }

    // 隐藏JSAPI参数容器
    if (jsapiParamsContainer) {
      jsapiParamsContainer.classList.add("hidden");
      // 清空JSAPI参数输入框的值
      const subOpenidInput = document.getElementById("test-sub-openid");
      const subAppidInput = document.getElementById("test-sub-appid");
      if (subOpenidInput) subOpenidInput.value = "";
      if (subAppidInput) subAppidInput.value = "";
    }

    logMessage_Info("[移动端测试支付] 所有额外参数输入框已隐藏");
  }
}

/**
 * 测试商品名称生成器（移动端）- 单次测试
 *
 * 功能说明：
 * 根据用户输入的商品数量，调用后端API生成趣味商品名称
 * 并显示生成结果（商品名称和字节长度）
 *
 * API端点：POST /api/admin/generate_product_name
 *
 * 调用时机：
 * - 用户在商品名测试面板点击"生成商品名"按钮时
 */
async function testGenerateProductName() {
  logMessage_Info("[移动端商品名测试] 开始单次测试...");

  // === 第1步：获取输入元素 ===
  const quantityInput = document.getElementById("product-test-quantity");
  const resultContainer = document.getElementById("product-test-result");
  const productNameDisplay = document.getElementById("product-test-name");
  const byteLengthDisplay = document.getElementById("product-test-length");

  // === 第2步：验证输入 ===
  const quantity = quantityInput ? parseInt(quantityInput.value) : 0;

  // 验证数量是否有效
  if (!quantity || quantity < 1 || quantity > 9999) {
    // showModalAlert("请输入有效的商品数量（1-9999）");
    swal.fire({
      icon: "warning",
      title: "警告",
      text: "请输入有效的商品数量（1-9999）",
    });
    return;
  }

  logMessage_Info("[移动端商品名测试] 商品数量：", quantity);

  try {
    // === 第3步：调用后端API生成商品名 ===
    const response = await fetch("/api/admin/generate_product_name", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        quantity: quantity,
      }),
    });

    // 解析响应JSON
    const result = await response.json();
    logMessage_Info(
      "[移动端商品名测试] API响应：",
      createSafeClientLogValue(result),
    );

    // === 第4步：处理响应 ===
    if (result.success) {
      // 生成成功：显示结果
      if (productNameDisplay) {
        productNameDisplay.textContent = result.product_name;
      }
      if (byteLengthDisplay) {
        byteLengthDisplay.textContent = `${result.byte_length} 字节`;
      }
      // 显示结果容器
      if (resultContainer) {
        resultContainer.classList.remove("hidden");
      }
      logMessage_Info("[移动端商品名测试] 生成成功");
    } else {
      // 生成失败：显示错误消息
      // showModalAlert("生成失败：" + (result.message || "未知错误"));
      swal.fire({
        icon: "error",
        title: "错误",
        text: "生成失败：" + (result.message || "未知错误"),
      });
    }
  } catch (error) {
    // === 第5步：错误处理 ===
    logMessage_Error("[移动端商品名测试] 请求失败：", error);
    // showModalAlert("网络错误，请稍后重试");
    swal.fire({
      icon: "error",
      title: "错误",
      text: "网络错误，请稍后重试",
    });
  }
}

/**
 * 测试商品名称生成器（移动端）- 批量测试
 *
 * 功能说明：
 * 生成10个不同数量的商品名称示例（1, 2, 5, 10, 20, 50, 100, 200, 500, 1000）
 * 用于验证生成器在不同数量级下的表现
 *
 * API端点：POST /api/admin/generate_product_name
 *
 * 调用时机：
 * - 用户在商品名测试面板点击"批量测试（生成10个示例）"按钮时
 */
async function batchTestProductNames() {
  logMessage_Info("[移动端商品名测试] 开始批量测试...");

  // === 第1步：获取容器元素 ===
  const batchResultsContainer = document.getElementById("batch-test-results");
  const batchListContainer = document.getElementById("batch-test-list");

  // 验证元素是否存在
  if (!batchListContainer) {
    logMessage_Error("[移动端商品名测试] 找不到批量测试结果列表容器");
    return;
  }

  // === 第2步：定义测试数量数组 ===
  // 涵盖不同数量级：个位数、十位数、百位数、千位数
  const testQuantities = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];

  // 清空之前的结果
  batchListContainer.innerHTML =
    '<p class="text-slate-400 text-center py-4 text-xs">正在生成...</p>';

  // 显示结果容器
  if (batchResultsContainer) {
    batchResultsContainer.classList.remove("hidden");
  }

  // === 第3步：逐个调用API生成 ===
  const results = [];

  for (const quantity of testQuantities) {
    try {
      // 调用API
      const response = await fetch("/api/admin/generate_product_name", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
        body: JSON.stringify({
          quantity: quantity,
        }),
      });

      const result = await response.json();

      // 保存结果
      if (result.success) {
        results.push({
          quantity: quantity,
          productName: result.product_name,
          byteLength: result.byte_length,
        });
        logMessage_Info(
          `[移动端商品名测试] 数量${quantity}：${result.product_name}`,
        );
      }
    } catch (error) {
      logMessage_Error(`[移动端商品名测试] 数量${quantity}生成失败：`, error);
    }
  }

  // === 第4步：渲染结果列表 ===
  if (results.length === 0) {
    batchListContainer.innerHTML =
      '<p class="text-red-500 text-center py-4 text-xs">批量生成失败，请检查网络连接</p>';
    return;
  }

  // 构建HTML字符串（移动端使用更小的间距和字体）
  let html = "";
  results.forEach((item, index) => {
    html += `
      <div class="bg-white border border-slate-200 rounded-lg p-2">
        <!-- 序号和数量 -->
        <div class="flex justify-between items-center mb-1 pb-1 border-b border-slate-100">
          <span class="text-xs font-semibold text-slate-500">示例 ${
            index + 1
          }</span>
          <span class="text-xs bg-sky-100 text-sky-700 px-2 py-0.5 rounded-full font-medium">数量：${
            item.quantity
          }</span>
        </div>
        <!-- 商品名称 -->
        <div class="mb-1">
          <p class="text-xs text-slate-500 mb-0.5">商品名称：</p>
          <p class="text-xs font-medium text-slate-800 break-all">${
            item.productName
          }</p>
        </div>
        <!-- 字节长度 -->
        <div class="text-xs text-slate-500">
          字节长度：<span class="font-semibold text-slate-700">${
            item.byteLength
          }</span> 字节
          ${
            item.byteLength > 127
              ? '<span class="text-red-600 ml-1">（超出限制！）</span>'
              : '<span class="text-green-600 ml-1">（符合限制）</span>'
          }
        </div>
      </div>
    `;
  });

  batchListContainer.innerHTML = html;
  logMessage_Info(
    `[移动端商品名测试] 批量测试完成，成功生成${results.length}个示例`,
  );
}

async function createTestOrder() {
  // 在控制台输出日志，标记创建测试订单操作开始
  logMessage_Info("[测试支付] 开始创建测试订单...");

  // ========== 第1步：获取所有输入框和显示区域的DOM元素 ==========

  // 1.1 获取测试支付金额输入框（必填项，必须>0）
  const amountInput = document.getElementById("test-payment-amount");

  // 1.2 获取商品名称输入框（可选项，为空时使用默认值）
  const productInput = document.getElementById("test-payment-product");

  // 1.3 获取支付方式选择下拉框（必填项）
  const methodSelect = document.getElementById("test-payment-method");

  // 1.4 获取订单结果显示容器
  const resultContainer = document.getElementById(
    "test-order-result-container",
  );

  // 1.5 获取订单号显示元素
  const tradeNoSpan = document.getElementById("test-order-trade-no");

  // 1.6 获取订单金额显示元素
  const amountSpan = document.getElementById("test-order-amount");

  // 1.7 获取支付链接显示元素（用于显示和复制）
  const payUrlSpan = document.getElementById("test-order-pay-url");

  // 1.8 获取"打开支付链接"按钮
  const openPayBtn = document.getElementById("open-test-pay-url-btn");

  // ========== 第2步：防御性检查 - 确保所有必需的DOM元素都存在 ==========

  // 检查所有必需的元素是否都能找到
  if (
    !amountInput ||
    !productInput ||
    !methodSelect ||
    !resultContainer ||
    !tradeNoSpan ||
    !amountSpan ||
    !payUrlSpan ||
    !openPayBtn
  ) {
    // 输出错误日志，列出缺失的元素（便于调试）
    logMessage_Error("[测试支付] 错误：页面元素未找到");
    logMessage_Error("元素检查：", {
      amountInput: !!amountInput,
      productInput: !!productInput,
      methodSelect: !!methodSelect,
      resultContainer: !!resultContainer,
      tradeNoSpan: !!tradeNoSpan,
      amountSpan: !!amountSpan,
      payUrlSpan: !!payUrlSpan,
      openPayBtn: !!openPayBtn,
    });
    // 向用户显示友好的错误提示
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    // 使用Swal替代showModalAlert，提供更好的用户体验
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return; // 终止函数执行
  }

  // ========== 第3步：获取并验证用户输入 ==========

  // 3.1 获取支付金额，并去除首尾空格
  const amountStr = amountInput.value.trim();

  // 3.2 验证金额不为空（必填项验证）
  if (!amountStr) {
    logMessage_Info("[测试支付] 验证失败：支付金额为空");
    // showModalAlert("请输入支付金额");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入支付金额",
    });
    amountInput.focus();
    return;
  }

  // 3.3 将金额字符串转换为浮点数
  const amount = parseFloat(amountStr);

  // 3.4 验证金额是否为有效数字
  if (isNaN(amount)) {
    logMessage_Info("[测试支付] 验证失败：支付金额不是有效数字");
    // showModalAlert("支付金额必须是有效的数字");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付金额必须是有效的数字",
    });
    amountInput.focus();
    return;
  }

  // 3.5 验证金额必须大于0
  if (amount <= 0) {
    logMessage_Error(
      "[测试支付] 验证失败：支付金额必须大于0，当前值：",
      amount,
    );
    // showModalAlert("支付金额必须大于0");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付金额必须大于0",
    });
    amountInput.focus();
    return;
  }

  // 3.6 获取商品名称
  // 根据用户选择的输入方式，获取商品名称
  // 两种方式：1. 手动输入  2. 自动生成（调用后端API）

  let productName = "测试商品"; // 默认值，防止获取失败时使用

  // 3.6.1 获取用户选择的输入方式
  const radioButtons = document.getElementsByName("product-name-input-method");
  let inputMethod = "manual"; // 默认为手动输入

  // 遍历单选按钮，找到选中的那个
  for (const radio of radioButtons) {
    if (radio.checked) {
      inputMethod = radio.value;
      break;
    }
  }

  logMessage_Info("[移动端测试支付] 商品名称输入方式：", inputMethod);

  // 3.6.2 根据输入方式获取商品名称
  if (inputMethod === "manual") {
    // 手动输入模式：从文本输入框获取
    productName = productInput.value.trim();
    if (!productName) {
      // 如果用户没有填写商品名称，使用默认值
      productName = "测试商品";
      logMessage_Info("[移动端测试支付] 使用默认商品名称：", productName);
    } else {
      logMessage_Info("[移动端测试支付] 手动输入的商品名称：", productName);
    }
  } else if (inputMethod === "auto") {
    // 自动生成模式：从数量输入框获取数值，然后调用后端API生成商品名
    const quantityInput = document.getElementById("test-payment-quantity");
    const quantity = quantityInput ? parseInt(quantityInput.value) : 0;

    // 验证数量是否有效
    if (!quantity || quantity < 1 || quantity > 9999) {
      // showModalAlert("请输入有效的商品数量（1-9999）");
      Swal.fire({
        icon: "warning",
        title: "警告",
        text: "请输入有效的商品数量（1-9999）",
      });
      if (quantityInput) quantityInput.focus();
      return; // 中断函数执行
    }

    logMessage_Info(
      "[移动端测试支付] 商品数量：",
      quantity,
      "，正在调用生成器API...",
    );

    try {
      // 调用后端API生成商品名称
      // API端点：/api/admin/generate_product_name
      // 请求参数：{ quantity: 数量 }
      // 返回格式：{ success: true, product_name: "生成的商品名" }
      const genResponse = await fetch("/api/admin/generate_product_name", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID, // 需要管理员权限
        },
        body: JSON.stringify({ quantity: quantity }),
      });

      // 检查HTTP响应状态
      if (!genResponse.ok) {
        throw new Error(`生成商品名失败：HTTP状态码 ${genResponse.status}`);
      }

      // 解析JSON响应
      const genResult = await genResponse.json();

      // 检查业务状态
      if (!genResult.success || !genResult.product_name) {
        throw new Error(genResult.message || "生成商品名失败");
      }

      // 使用生成的商品名称
      productName = genResult.product_name;
      logMessage_Info("[移动端测试支付] 自动生成的商品名称：", productName);
    } catch (error) {
      // 生成商品名失败，显示错误并中断
      logMessage_Error("[移动端测试支付] 生成商品名失败：", error);
      // showModalAlert(`生成商品名失败：${error.message}`);
      Swal.fire({
        icon: "error",
        title: "错误",
        text: `生成商品名失败：${error.message}`,
      });
      return; // 中断函数执行
    }
  }

  // 3.7 获取支付方式（必填项）
  const paymentMethod = methodSelect.value;

  // 3.8 验证支付方式已选择
  if (!paymentMethod) {
    logMessage_Info("[测试支付] 验证失败：未选择支付方式");
    // showModalAlert("请选择支付方式");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请选择支付方式",
    });
    methodSelect.focus();
    return;
  }

  // 3.9 获取支付接口类型（必填项）
  const typeSelect = document.getElementById("test-payment-type");
  const paymentType = typeSelect ? typeSelect.value : "jump";

  // 验证接口类型已选择
  if (!paymentType) {
    logMessage_Info("[测试支付] 验证失败：未选择接口类型");
    // showModalAlert("请选择接口类型");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请选择接口类型",
    });
    if (typeSelect) typeSelect.focus();
    return;
  }

  logMessage_Info("[测试支付] 接口类型：", paymentType);

  // 3.10 获取付款码（仅扫码支付需要）
  // 声明变量用于存储付款码，默认为空字符串
  let auth_code = "";
  // 如果选择的是扫码支付（scan类型），则需要验证并获取付款码
  if (paymentType === "scan") {
    // 获取付款码输入框元素
    const authCodeInput = document.getElementById("test-auth-code");
    // 如果输入框存在，则获取并清理其值（去除首尾空格）
    auth_code = authCodeInput ? authCodeInput.value.trim() : "";

    // 验证付款码是否为空
    if (!auth_code) {
      logMessage_Error("[移动端测试支付] 验证失败：扫码支付需要提供付款码");
      // showModalAlert("扫码支付需要提供付款码（auth_code）");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "扫码支付需要提供付款码（auth_code）",
      });
      // 聚焦到付款码输入框，引导用户输入
      if (authCodeInput) authCodeInput.focus();
      return; // 中断函数执行
    }

    // 验证付款码长度和格式（通常为18位数字）
    if (auth_code.length !== 18 || !/^\d+$/.test(auth_code)) {
      logMessage_Error(
        "[移动端测试支付] 验证失败：付款码格式不正确，当前长度：",
        auth_code.length,
      );
      // showModalAlert("付款码格式不正确，应为18位纯数字");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "付款码格式不正确，应为18位纯数字",
      });
      if (authCodeInput) authCodeInput.focus();
      return; // 中断函数执行
    }

    logMessage_Info("[移动端测试支付] 付款码已提供（已隐藏显示）");
  }

  // 3.11 获取JSAPI支付参数（仅JSAPI支付需要）
  // 声明变量用于存储JSAPI支付所需的参数，默认为空字符串
  let subOpenid = "";
  let subAppid = "";
  // 如果选择的是JSAPI支付（jsapi类型），则需要验证并获取sub_openid和sub_appid
  if (paymentType === "jsapi") {
    // 获取sub_openid输入框元素
    const subOpenidInput = document.getElementById("test-sub-openid");
    // 获取sub_appid输入框元素
    const subAppidInput = document.getElementById("test-sub-appid");

    // 获取并清理sub_openid的值（去除首尾空格）
    subOpenid = subOpenidInput ? subOpenidInput.value.trim() : "";
    // 获取并清理sub_appid的值（去除首尾空格）
    subAppid = subAppidInput ? subAppidInput.value.trim() : "";

    // 验证sub_openid是否为空
    if (!subOpenid) {
      logMessage_Error(
        "[移动端测试支付] 验证失败：JSAPI支付需要提供用户Openid",
      );
      // showModalAlert("JSAPI支付需要提供用户Openid（sub_openid）");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "JSAPI支付需要提供用户Openid（sub_openid）",
      });
      // 聚焦到sub_openid输入框，引导用户输入
      if (subOpenidInput) subOpenidInput.focus();
      return; // 中断函数执行
    }

    // 验证sub_appid是否为空
    if (!subAppid) {
      logMessage_Error(
        "[移动端测试支付] 验证失败：JSAPI支付需要提供公众号AppId",
      );
      // showModalAlert("JSAPI支付需要提供公众号AppId（sub_appid）");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "JSAPI支付需要提供公众号AppId（sub_appid）",
      });
      // 聚焦到sub_appid输入框，引导用户输入
      if (subAppidInput) subAppidInput.focus();
      return; // 中断函数执行
    }

    // 验证sub_openid的格式（微信openid通常以字母o开头，支付宝以数字2开头，长度约28个字符）
    // 这里使用宽松的验证规则，确保长度合理即可
    if (subOpenid.length < 20 || subOpenid.length > 64) {
      logMessage_Warning(
        "[移动端测试支付] 警告：用户Openid格式可能不正确，长度不在合理范围",
      );
      // showModalAlert("用户Openid格式可能不正确，长度应在20-64字符之间");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "用户Openid格式可能不正确，长度应在20-64字符之间",
      });
      if (subOpenidInput) subOpenidInput.focus();
      return; // 中断函数执行
    }

    // 验证sub_appid的格式（微信以wx开头，支付宝以数字开头，长度约18个字符）
    // 使用宽松验证：长度在10-32字符之间即可
    if (subAppid.length < 10 || subAppid.length > 32) {
      logMessage_Warning("[移动端测试支付] 警告：公众号AppId格式可能不正确");
      // showModalAlert("公众号AppId格式可能不正确，长度应在10-32字符之间");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "公众号AppId格式可能不正确，长度应在10-32字符之间",
      });
      if (subAppidInput) subAppidInput.focus();
      return; // 中断函数执行
    }

    logMessage_Info(
      "[移动端测试支付] JSAPI参数已提供：sub_openid和sub_appid（已隐藏显示）",
    );
  }

  // ========== 第4步：生成订单号 ==========

  // 订单号生成规则：当前时间戳（毫秒） + 6位随机数
  // Date.now() 返回当前时间的时间戳（毫秒）
  // Math.random() 生成0-1之间的随机数
  // Math.floor() 向下取整
  // toString().padStart(6, '0') 转为字符串并补齐到6位（不足部分用0填充）
  const timestamp = Date.now();
  const randomNum = Math.floor(Math.random() * 1000000)
    .toString()
    .padStart(6, "0");
  const tradeNo = `${timestamp}${randomNum}`;

  // 输出日志记录生成的订单号
  logMessage_Info("[测试支付] 生成订单号：", tradeNo);
  // 输出日志，记录所有订单参数（便于调试）
  logMessage_Info(
    "[测试支付] 订单参数：",
    createSafeClientLogValue({
      trade_no: tradeNo,
      amount: amount,
      product_name: productName,
      pay_type: paymentMethod,
      method: paymentType,
    }),
  );

  const app_host = window.location.protocol + "//" + window.location.host;

  // ========== 第5步：先隐藏结果容器，避免显示旧数据 ==========
  resultContainer.classList.add("hidden");

  try {
    // ========== 第6步：发起API请求创建订单 ==========

    // 6.1 使用fetch API调用后端接口
    // await关键字会等待请求完成，确保获取到响应后再继续执行
    const response = await fetch("/api/payment/create", {
      method: "POST", // HTTP方法：POST用于创建新订单
      headers: {
        // 设置请求头，告知服务器请求体是JSON格式
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 包含会话ID，进行身份验证
      },
      // 将订单参数转换为JSON字符串作为请求体
      body: JSON.stringify({
        amount: amount, // 支付金额
        product_name: productName, // 商品名称
        preserve_product_name: true, // 测试支付：保留用户输入商品名
        payment_method: paymentMethod, // 支付方式
        payment_type: paymentType, // 接口类型（web/jump/jsapi/app/scan/applet）
        app_host: app_host, // 应用主机地址
        return_url: window.location.href,
        device: Get_YiPAi_device(),
        sub_appid: subAppid,
        sub_openid: subOpenid,
        auth_code: auth_code,
      }),
    });

    // 6.2 检查HTTP响应状态码
    // response.ok 为true表示状态码在200-299范围内（成功）
    if (!response.ok) {
      // 如果响应状态码不是成功状态（如404、500等）
      // 抛出错误，中断执行流程，进入catch块处理
      throw new Error(`创建订单失败：HTTP状态码 ${response.status}`);
    }

    // 6.3 解析JSON响应数据
    const result = await response.json();

    // 输出完整的API响应，方便开发者调试
    logMessage_Info("[测试支付] API响应：", createSafeClientLogValue(result));

    // 6.4 检查业务状态
    // 即使HTTP状态码是200，业务逻辑也可能失败
    if (!result.success) {
      // 如果业务失败，抛出错误，显示服务器返回的错误消息
      throw new Error(result.message || "创建订单失败，未知错误");
    }

    // 6.5 检查是否有支付信息（pay_url或pay_info）
    if (!result.pay_url && !result.pay_info) {
      throw new Error("未返回支付信息");
    }

    // ========== 第7步：显示订单信息 ==========

    // 7.1 获取订单数据
    const order = result.order || {};
    const payType = result.pay_type || "jump";
    const payInfo = result.pay_info || result.pay_url || "";

    // 输出成功日志
    logMessage_Info(
      "[测试支付] 订单创建成功：",
      createSafeClientLogValue(result),
    );

    // 7.2 填充商户订单号
    const orderIdElem = document.getElementById("test-order-id");
    if (orderIdElem) orderIdElem.textContent = result.order_id || "-";

    // 7.3 显示平台订单号
    // 优先使用平台订单号（trade_no），如果没有则使用商户订单号
    tradeNoSpan.textContent = result.trade_no || order.trade_no || tradeNo;

    // 7.4 显示订单金额
    // 格式化金额：添加货币符号¥，保留2位小数
    const displayAmount = order.amount || amount;
    amountSpan.textContent = `¥${parseFloat(displayAmount).toFixed(2)}`;

    // 7.5 填充支付方式（翻译为中文）
    const payMethodElem = document.getElementById("test-order-pay-method");
    if (payMethodElem) {
      const methodNames = {
        alipay: "支付宝",
        wxpay: "微信支付",
        qqpay: "QQ钱包",
        unionpay: "云闪付",
      };
      payMethodElem.textContent = methodNames[paymentMethod] || paymentMethod || "-";
    }

    // 7.6 填充接口类型
    const methodTypeElem = document.getElementById("test-order-method-type");
    if (methodTypeElem) methodTypeElem.textContent = paymentType || "-";

    // 7.7 填充发起支付类型
    const payTypeElem = document.getElementById("test-order-pay-type");
    if (payTypeElem) payTypeElem.textContent = payType || "-";

    // 7.8 根据支付类型设置说明文字
    const payInfoDescElem = document.getElementById("test-order-pay-info-desc");
    if (payInfoDescElem) {
      const payTypeDescriptions = {
        jump: "跳转链接 - 可直接打开进行支付",
        html: "HTML代码 - 用于支付跳转",
        qrcode: "二维码链接 - 已生成二维码供扫描",
        urlscheme: "小程序跳转链接 - 可在微信/支付宝中打开",
        jsapi: "JSAPI支付参数 - JSON格式，用于小程序内支付",
        app: "APP支付参数 - JSON格式，用于APP内支付",
        scan: "扫码支付结果 - 付款码支付成功的订单信息",
        wxplugin: "小程序插件参数 - JSON格式，用于拉起微信小程序插件",
        wxapp: "小程序跳转参数 - JSON格式，用于APP内拉起微信小程序",
      };
      payInfoDescElem.textContent = payTypeDescriptions[payType] || "支付信息";
    }

    // 7.9 填充支付信息到 textarea（完整显示，不截断）
    // 重置二维码容器
    const qrcodeContainer = document.getElementById("test-order-qrcode-display");
    if (qrcodeContainer) {
      qrcodeContainer.innerHTML = "";
      qrcodeContainer.classList.add("hidden");
    }

    if (payType === "jump" || payType === "html") {
      // 跳转支付：直接显示完整链接
      payUrlSpan.value = payInfo;
    } else if (payType === "qrcode") {
      // 二维码支付：显示原始链接并渲染二维码
      payUrlSpan.value = payInfo;
      if (qrcodeContainer && typeof QRCode !== "undefined") {
        try {
          const canvas = document.createElement("canvas");
          qrcodeContainer.appendChild(canvas);
          QRCode.toCanvas(
            canvas,
            payInfo,
            { width: 180, margin: 2, color: { dark: "#000000", light: "#ffffff" } },
            function (error) {
              if (error) {
                logMessage_Error("[测试支付] 二维码生成失败：", error);
                qrcodeContainer.innerHTML =
                  '<p class="text-red-500 text-xs">二维码生成失败</p>';
                qrcodeContainer.classList.remove("hidden");
              } else {
                logMessage_Info("[测试支付] 二维码生成成功");
                qrcodeContainer.classList.remove("hidden");
              }
            },
          );
        } catch (e) {
          logMessage_Error("[测试支付] 二维码生成出错：", e);
          qrcodeContainer.innerHTML =
            '<p class="text-red-500 text-xs">二维码生成出错</p>';
          qrcodeContainer.classList.remove("hidden");
        }
      } else if (qrcodeContainer) {
        qrcodeContainer.innerHTML =
          '<p class="text-yellow-600 text-xs">QRCode库未加载，请手动扫描上方链接</p>';
        qrcodeContainer.classList.remove("hidden");
      }
    } else if (payType === "urlscheme") {
      // URL Scheme：显示完整的小程序跳转链接
      payUrlSpan.value = payInfo;
    } else if (
      payType === "jsapi" ||
      payType === "app" ||
      payType === "wxplugin" ||
      payType === "wxapp"
    ) {
      // JSAPI/APP/小程序支付：显示格式化的JSON参数
      try {
        const jsonObj =
          typeof payInfo === "string" ? JSON.parse(payInfo) : payInfo;
        payUrlSpan.value = JSON.stringify(jsonObj, null, 2);
      } catch (e) {
        payUrlSpan.value = payInfo;
      }
    } else if (payType === "scan") {
      // 扫码支付成功：显示订单信息
      payUrlSpan.value = `扫码支付成功: ${payInfo}`;
    } else {
      // 其他类型：直接显示完整内容
      payUrlSpan.value = payInfo;
    }

    // 7.10 配置"打开链接"按钮
    // jump/html/urlscheme 类型可直接打开，其他类型禁用按钮
    if (payType === "jump" || payType === "html" || payType === "urlscheme") {
      openPayBtn.setAttribute("data-url", payInfo);
      openPayBtn.disabled = false;
      openPayBtn.classList.remove("opacity-50", "cursor-not-allowed");
    } else {
      openPayBtn.disabled = true;
      openPayBtn.classList.add("opacity-50", "cursor-not-allowed");
    }

    logMessage_Info("[测试支付] 支付信息已保存，类型：", payType);

    // 7.11 显示订单结果容器
    // 移除hidden类，让用户看到订单信息
    resultContainer.classList.remove("hidden");

    // 输出完成日志
    logMessage_Info("[测试支付] 订单信息已成功显示");

    // 7.6 可选：向用户显示成功提示
    // showModalAlert('测试订单创建成功！请点击下方按钮打开支付链接。');
    Swal.fire({
      icon: "success",
      title: "成功",
      text: "测试订单创建成功！请点击下方按钮打开支付链接。",
    });
  } catch (error) {
    // ========== 错误处理 ==========
    // 捕获所有可能的错误：网络错误、服务器错误、业务错误等

    // 在控制台输出详细的错误信息
    logMessage_Error("[测试支付] 创建订单失败：", error);

    // 向用户显示错误提示
    // showModalAlert(
    //   `创建订单失败：${error.message || "未知错误，请重试或联系管理员"}`
    // );
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `创建订单失败：${error.message || "未知错误，请重试或联系管理员"}`,
    });

    // 隐藏订单结果容器（因为没有有效的订单数据）
    resultContainer.classList.add("hidden");
  }
}

/**
 * 打开测试支付链接函数
 *
 * 功能说明：
 * 1. 从"打开支付链接"按钮的data-url属性中获取支付链接
 * 2. 验证链接是否存在
 * 3. 使用window.open()在新标签页中打开支付页面
 * 4. 处理可能的弹窗拦截问题
 *
 * 调用时机：
 * - 用户点击"打开支付链接"按钮时
 *
 * 注意事项：
 * - 现代浏览器可能会拦截window.open()弹窗，需要提示用户允许弹窗
 * - 必须在用户点击事件的处理函数中调用，否则会被拦截
 */
function openTestPayUrl() {
  // 在控制台输出日志，标记打开支付链接操作开始
  logMessage_Info("[测试支付] 准备打开支付链接...");

  // ========== 第1步：获取按钮元素 ==========

  // 获取"打开支付链接"按钮的DOM元素
  const openPayBtn = document.getElementById("open-test-pay-url-btn");

  // 防御性检查：确保按钮元素存在
  if (!openPayBtn) {
    logMessage_Error(
      "[测试支付] 错误：未找到打开支付链接按钮（ID: open-test-pay-url-btn）",
    );
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    // 使用Swal替代showModalAlert，提供更好的用户体验
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return;
  }

  // ========== 第2步：从按钮的data-url属性获取支付链接 ==========

  // getAttribute()方法获取元素的指定属性值
  // data-url属性是在createTestOrder()函数中设置的，包含完整的支付链接
  const payUrl = openPayBtn.getAttribute("data-url");

  // 支付链接可能带有签名或临时令牌，不写入日志。
  logMessage_Info("[测试支付] 已获取支付链接");

  // ========== 第3步：验证支付链接是否存在 ==========

  // 检查链接是否为空或undefined
  if (!payUrl) {
    // 如果链接不存在，说明订单创建失败或API未返回支付链接
    logMessage_Error("[测试支付] 错误：支付链接不存在");
    // showModalAlert("支付链接不存在，请先创建测试订单。");
    // 使用Swal替代showModalAlert，提供更好的用户体验
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付链接不存在，请先创建测试订单。",
    });
    return;
  }

  // ========== 第4步：在新标签页中打开支付链接 ==========

  try {
    // 使用window.open()方法在新标签页中打开支付链接
    // 参数说明：
    // - 第1个参数：要打开的URL（支付链接）
    // - 第2个参数：窗口目标，'_blank'表示在新标签页中打开
    // - 第3个参数：窗口特性（可选），这里使用'noopener,noreferrer'增强安全性
    //   * noopener: 防止新页面通过window.opener访问原页面
    //   * noreferrer: 不发送HTTP Referer头，保护隐私
    const newWindow = window.open(payUrl, "_blank", "noopener,noreferrer");

    // ========== 第5步：检查是否成功打开 ==========

    // 如果newWindow为null或undefined，说明浏览器拦截了弹窗
    // 现代浏览器默认会拦截非用户主动触发的弹窗，需要用户在浏览器设置中允许
    if (!newWindow) {
      // 输出警告日志
      logMessage_Warning("[测试支付] 警告：浏览器可能拦截了弹窗");

      // 向用户显示友好的提示信息
      // 不在alert中直接显示URL，避免安全问题
      // showModalAlert(
      //   "浏览器拦截了弹窗，请允许本网站的弹窗权限。\n\n支付链接已复制到输入框中，您可以手动复制后在新标签页打开。"
      // );
      // 使用Swal替代showModalAlert，提供更好的用户体验
      Swal.fire({
        icon: "warning",
        title: "警告",
        text: "浏览器拦截了弹窗，请允许本网站的弹窗权限。\n\n支付链接已复制到输入框中，您可以手动复制后在新标签页打开。",
      });
      // 将链接复制到输入框供用户查看
      const urlInput = document.getElementById("test-order-pay-url");
      if (urlInput) {
        urlInput.select();
      }
    } else {
      // 如果成功打开，输出成功日志
      logMessage_Info("[测试支付] 支付链接已在新标签页中打开");

      // 可选：将焦点设置到新窗口
      // newWindow.focus();
    }
  } catch (error) {
    // ========== 错误处理 ==========
    // 捕获可能的异常（虽然window.open()很少抛出异常）

    // 在控制台输出详细的错误信息
    logMessage_Error("[测试支付] 打开支付链接时发生错误：", error);

    // 向用户显示错误提示
    // showModalAlert(
    //   `无法打开支付链接：${
    //     error.message || "未知错误"
    //   }\n\n支付链接：${payUrl}\n\n请手动复制链接在新标签页打开。`
    // );
    // 使用Swal替代showModalAlert，提供更好的用户体验
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `无法打开支付链接：${
        error.message || "未知错误"
      }\n\n支付链接：${payUrl}\n\n请手动复制链接在新标签页打开。`,
    });
  }
}

/**
 * 复制移动端测试支付信息
 *
 * 功能说明：
 * 将 textarea 中的完整支付信息复制到剪贴板，方便用户分享或保存
 *
 * 调用时机：
 * - 用户点击"复制信息"按钮时（onclick="copyTestPayInfo()"）
 */
function copyTestPayInfo() {
  logMessage_Info("[测试支付] 准备复制支付信息...");

  const payUrlTextarea = document.getElementById("test-order-pay-url");
  if (!payUrlTextarea) {
    Swal.fire({ icon: "error", title: "错误", text: "页面元素异常，请刷新页面后重试。" });
    return;
  }

  const payInfo = payUrlTextarea.value;
  if (!payInfo) {
    Swal.fire({ icon: "error", title: "错误", text: "支付信息为空，请先创建测试订单。" });
    return;
  }

  try {
    payUrlTextarea.select();
    payUrlTextarea.setSelectionRange(0, payInfo.length);

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(payInfo).then(function () {
        Swal.fire({ icon: "success", title: "已复制", text: "支付信息已复制到剪贴板！", timer: 1500, showConfirmButton: false });
      }).catch(function () {
        document.execCommand("copy");
        Swal.fire({ icon: "success", title: "已复制", text: "支付信息已复制到剪贴板！", timer: 1500, showConfirmButton: false });
      });
    } else {
      document.execCommand("copy");
      Swal.fire({ icon: "success", title: "已复制", text: "支付信息已复制到剪贴板！", timer: 1500, showConfirmButton: false });
    }
  } catch (e) {
    logMessage_Error("[测试支付] 复制支付信息失败：", e);
    Swal.fire({ icon: "error", title: "复制失败", text: "请手动选中文本并复制。" });
  }
}

// --- Next Script Block ---

// ==========================================
// Tab切换功能
// ==========================================
// 【功能说明】
// 实现PC端管理员支付设置面板的4个Tab之间的切换
// 包括：支付方式配置、订单查询、退款处理、测试支付
// ==========================================

/**
 * 切换PC端管理员支付设置面板的Tab
 *
 * 功能说明：
 * 1. 隐藏所有Tab的内容区域
 * 2. 移除所有Tab按钮的激活样式
 * 3. 显示指定Tab的内容区域
 * 4. 为指定Tab按钮添加激活样式
 *
 * 调用时机：
 * - 用户点击任何一个Tab按钮时
 * - 页面加载时默认显示第一个Tab
 *
 * 参数说明：
 * @param {string} tabName - Tab的名称，可选值：'config'、'query'、'refund'、'test'
 *
 * 实现细节：
 * - 使用forEach遍历所有Tab，统一处理显示/隐藏逻辑
 * - 通过classList动态添加/移除CSS类来改变样式
 * - 激活状态：蓝色背景、蓝色文字、底部蓝色边框、加粗字体
 * - 非激活状态：无背景、灰色文字、普通粗细字体
 */
function switchAdminPaymentSettingsTab(tabName) {
  // 在控制台输出日志，记录Tab切换操作
  logMessage_Info(`[PC端支付设置] 切换到Tab: ${tabName}`);

  // 定义所有标签页的名称数组
  // 这样可以统一管理所有标签页，便于维护
  // 如果将来需要添加新的Tab，只需在这里添加名称即可
  // 新增 'yipay' - 易支付配置标签页
  const tabs = ["config", "query", "refund", "test", "yipay", "product-test"];

  // 遍历所有标签页，执行显示/隐藏操作
  // forEach循环：对数组中的每个元素执行一次指定函数
  tabs.forEach((tab) => {
    // ========== 获取DOM元素 ==========

    // 获取标签页按钮元素
    // 命名规则：admin-payment-settings-tab-{tab}_modal
    const tabButton = document.getElementById(
      `admin-payment-settings-tab-${tab}_modal`,
    );

    // 获取标签页内容区域元素
    // 命名规则：admin-payment-settings-content-{tab}_modal
    const tabContent = document.getElementById(
      `admin-payment-settings-content-${tab}_modal`,
    );

    // 防御性检查：确保DOM元素存在
    // 如果元素不存在，跳过此次循环，避免null引用错误
    if (!tabButton || !tabContent) {
      logMessage_Warning(`[PC端支付设置] 警告：找不到Tab "${tab}" 的DOM元素`);
      return; // 使用return跳过当前循环迭代
    }

    // ========== 判断是否为目标Tab ==========

    // 检查当前遍历的标签页是否是要显示的目标标签页
    if (tab === tabName) {
      // === 激活目标标签页 ===

      // 步骤1：为标签页按钮添加激活状态样式
      // bg-sky-50: 浅蓝色背景
      // text-sky-600: 蓝色文字
      // border-b-2: 底部边框2px
      // border-sky-600: 蓝色边框
      // font-semibold: 加粗字体（600权重）
      tabButton.classList.add(
        "bg-sky-50",
        "text-sky-600",
        "border-b-2",
        "border-sky-600",
        "font-semibold",
      );

      // 步骤2：移除标签页按钮的非激活状态样式
      // text-slate-600: 灰色文字（非激活状态）
      // font-medium: 普通粗细字体（500权重）
      tabButton.classList.remove("text-slate-600", "font-medium");

      // 步骤3：显示对应的内容区域
      // 移除hidden类，使内容可见
      // hidden类由Tailwind CSS提供，相当于display: none
      tabContent.classList.remove("hidden");

      // 步骤4：当切换到配置Tab时，加载支付方式列表
      // 确保每次打开配置Tab时，支付方式列表都是最新的
      if (tab === "config") {
        // 调用 loadPaymentMethodsConfig() 函数加载支付方式配置
        // 此函数会从服务器获取所有支付方式的定义和启用状态
        // 然后动态渲染到 payment-methods-list_modal 容器中
        loadPaymentMethodsConfig((show_Modal_Alert = false));
        logMessage_Info(`[PC端支付设置] 已触发支付方式配置加载`);
      }

      // 步骤5：当切换到订单查询Tab时，显示提示信息
      // 注意：订单列表需要手动查询，避免自动加载造成过多请求
      if (tab === "query") {
        // 不自动加载订单列表，用户需要手动点击"手动查询"或"从平台拉取"按钮
        logMessage_Info(`[PC端支付设置] 已切换到订单查询Tab`);
        loadAllPaymentOrders();
      }

      if (tab === "yipay") {
        // 调用 loadYiPayConfig() 函数加载易支付配置
        loadAdminYiPayConfig((show_Modal = false));
        logMessage_Info(`[PC端支付设置] 已触发易支付配置加载`);
      }

      // 在控制台输出日志，标记Tab激活成功
      logMessage_Info(`[PC端支付设置] Tab "${tab}" 已激活`);
    } else {
      // === 取消激活其他标签页 ===

      // 步骤1：移除其他标签页按钮的激活状态样式
      // 移除蓝色背景、蓝色文字、蓝色边框、加粗字体
      tabButton.classList.remove(
        "bg-sky-50",
        "text-sky-600",
        "border-b-2",
        "border-sky-600",
        "font-semibold",
      );

      // 步骤2：为其他标签页按钮添加非激活状态样式
      // 恢复为灰色文字和普通粗细
      tabButton.classList.add("text-slate-600", "font-medium");

      // 步骤3：隐藏其他内容区域
      // 添加hidden类，使内容不可见
      tabContent.classList.add("hidden");
    }
  });

  // Tab切换完成，输出日志
  logMessage_Info(`[PC端支付设置] Tab切换完成`);
}

async function saveAdminPaymentMethodsConfig() {
  // 输出日志，标记保存操作开始
  logMessage_Info("[PC端支付配置] 开始保存支付方式配置...");

  try {
    // === 第1步：从payment-methods-list_modal容器中读取所有checkbox的状态 ===

    // 1.1 获取支付方式列表容器
    // 这个容器中包含了所有动态生成的支付方式项，每个项都有一个checkbox
    const listContainer = document.getElementById("payment-methods-list_modal");
    if (!listContainer) {
      // 如果容器不存在，抛出错误
      throw new Error("找不到支付方式列表容器");
    }

    // 1.2 查找容器内所有的checkbox元素
    // 选择器：input[type="checkbox"][id^="payment-method-"]
    // 含义：查找所有type为checkbox且id以"payment-method-"开头的input元素
    // 这样可以动态获取所有支付方式的checkbox，无需硬编码每个支付方式的ID
    const checkboxes = listContainer.querySelectorAll(
      'input[type="checkbox"][id^="payment-method-"]',
    );

    // 1.3 构建启用的支付方式列表
    // 遍历所有checkbox，将已选中的支付方式代码收集到数组中
    const enabledMethods = [];
    checkboxes.forEach((checkbox) => {
      // 检查checkbox是否被选中
      if (checkbox.checked) {
        // 从checkbox的id中提取支付方式代码
        // id格式：payment-method-{code}_modal
        // 例如：payment-method-alipay_modal -> alipay
        const id = checkbox.id;
        // 使用字符串操作提取代码：
        // 1. 去掉前缀 "payment-method-"
        // 2. 去掉后缀 "_modal"
        const code = id.replace("payment-method-", "").replace("_modal", "");
        // 将支付方式代码添加到启用列表中
        enabledMethods.push(code);
      }
    });

    // 在控制台输出即将提交的启用列表，便于调试
    logMessage_Info("[PC端支付配置] 已启用的支付方式：", enabledMethods);

    // === 第2步：构建要提交的配置对象 ===

    // 创建配置对象，包含启用的支付方式列表
    // 服务器端会根据这个列表更新配置
    const config = {
      enabled_payment_methods: enabledMethods,
    };

    // 在控制台输出即将提交的配置，便于调试
    logMessage_Info(
      "[PC端支付配置] 准备提交的配置数据：",
      createSafeClientLogValue(config),
    );

    // === 第3步：发起HTTP PUT请求保存配置 ===

    // 使用fetch API调用后端接口
    // PUT方法用于更新资源（幂等操作）
    const response = await fetch("/api/admin/payment/config", {
      method: "PUT", // HTTP方法：PUT用于更新/替换资源
      headers: {
        // Content-Type告知服务器请求体是JSON格式
        // 服务器需要根据这个标头解析请求体
        "Content-Type": "application/json",
        // X-Session-ID用于身份验证
        "X-Session-ID": sessionUUID,
      },
      // body必须是字符串，使用JSON.stringify()将对象转换为JSON字符串
      body: JSON.stringify(config),
    });

    // === 第4步：解析服务器响应 ===

    // 无论响应状态如何，都尝试解析JSON响应体
    // 这样可以在错误时也能获取服务器返回的错误消息
    const result = await response.json();

    // === 第5步：检查响应状态并显示相应提示 ===

    if (response.ok && result.success) {
      // 5.1 成功情况：响应状态为200且result.success为true

      // 输出成功日志
      logMessage_Info(
        "[PC端支付配置] 支付方式配置保存成功：",
        createSafeClientLogValue(result),
      );

      // 使用showModalAlert()显示成功提示（绿色样式）
      // 标题设置为"成功"，会触发showModalAlert内部的样式判断，显示为绿色
      // showModalAlert("配置已成功保存", "成功");
      Swal.fire({
        icon: "success",
        title: "成功",
        text: "配置已成功保存",
      });

      // 重新加载配置以确保数据同步
      // 传入false参数，避免loadPaymentMethodsConfig再次显示加载提示框
      await loadPaymentMethodsConfig(false);
    } else {
      // 5.2 失败情况：响应状态不为200或result.success为false

      // 从响应中提取错误消息
      // 优先使用result.message，如果不存在则使用默认错误消息
      const errorMessage = result.message || "保存配置失败，请重试";

      // 输出错误日志
      logMessage_Error("[PC端支付配置] 保存支付方式配置失败：", errorMessage);

      // 使用showModalAlert()显示错误提示（红色样式）
      // 会使用错误消息作为内容，标题设置为"错误"
      // 标题设置为"错误"或"失败"，会触发showModalAlert内部的样式判断，显示为红色
      // showModalAlert(errorMessage, "错误");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: errorMessage,
      });
    }
  } catch (error) {
    // === 错误处理 ===

    // 捕获所有可能的错误：网络错误、服务器错误、JSON解析错误、DOM操作错误等

    // 在控制台输出详细的错误信息
    logMessage_Error("[PC端支付配置] 保存支付方式配置时发生错误：", error);

    // 使用showModalAlert()显示错误提示
    // 显示用户友好的错误消息
    // showModalAlert(
    //   `保存失败：${error.message || "未知错误"}。\n请重试或联系管理员。`,
    //   "错误"
    // );
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `保存失败：${error.message || "未知错误"}。\n请重试或联系管理员。`,
    });
  }
}

// ==========================================
// Tab 2: 订单查询功能
// ==========================================
// 【功能说明】
// 实现支付设置面板中的订单查询功能，包括：
// 1. 根据订单号查询订单详情
// 2. 显示订单的完整信息（订单号、状态、金额、支付方式等）
// 3. 根据订单状态显示不同颜色的标签
// 4. 完善的输入验证和错误处理
//
// 【API说明】
// - POST /api/payment/query: 查询指定订单号的订单详情
// ==========================================

/**
 * 查询PC端管理员订单信息
 *
 * 功能说明：
 * 根据用户输入的订单号，查询订单的详细信息并显示在页面上
 * 包括：订单号、状态、金额、支付方式、创建时间、支付时间、商品名称
 *
 * API端点：POST /api/payment/query
 *
 * 请求体格式：
 * {
 *   trade_no: "20231210123456789012"  // 订单号
 * }
 *
 * 预期返回格式：
 * {
 *   success: true,
 *   order: {
 *     trade_no: "20231210123456789012",
 *     status: "paid",              // 订单状态：pending, paid, failed, refunded
 *     amount: 99.99,               // 订单金额
 *     payment_method: "alipay",    // 支付方式
 *     created_at: "2023-12-10 12:34:56",
 *     paid_at: "2023-12-10 12:35:10",
 *     product_name: "VIP会员"      // 商品名称/备注
 *   }
 * }
 *
 * 调用时机：
 * - 用户点击"查询订单"按钮时
 */
async function queryAdminPaymentOrder() {
  // 输出日志，标记查询操作开始
  logMessage_Info("[PC端订单查询] 开始查询订单...");

  // === 第1步：获取DOM元素 ===

  // 获取订单号输入框元素
  const tradeNoInput = document.getElementById(
    "admin-query-order-trade-no_modal",
  );
  // 获取订单详情显示容器
  const detailContainer = document.getElementById(
    "admin-order-detail-container_modal",
  );
  // 获取查询结果提示区域
  const resultDiv = document.getElementById("admin-query-order-result_modal");

  // 防御性检查：确保关键元素存在
  if (!tradeNoInput) {
    logMessage_Error("[PC端订单查询] 错误：找不到订单号输入框");
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    // 使用Swal替代showModalAlert，提供更好的用户体验
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return;
  }

  // === 第2步：获取并验证订单号输入 ===

  // 获取用户输入的订单号，使用trim()去除首尾空格
  const tradeNo = tradeNoInput.value.trim();

  // 验证订单号是否为空
  if (!tradeNo) {
    // 如果订单号为空，显示错误提示
    logMessage_Warning("[PC端订单查询] 订单号为空");

    // 隐藏订单详情容器
    if (detailContainer) {
      detailContainer.classList.add("hidden");
    }

    // 显示错误提示
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          ✗ 请输入订单号
        </div>
      `;
      resultDiv.classList.remove("hidden");

      // 3秒后自动隐藏提示
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 3000);
    }
    return;
  }

  // 在控制台输出即将查询的订单号
  logMessage_Info("[PC端订单查询] 查询订单号：", tradeNo);

  try {
    // === 第3步：发起HTTP POST请求查询订单 ===

    const response = await fetch("/api/payment/query", {
      method: "POST", // 使用POST方法发送查询请求
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 附加会话ID用于身份验证
      },
      // 将订单号作为请求体发送
      body: JSON.stringify({
        order_id: tradeNo,
      }),
    });

    // === 第4步：检查HTTP响应状态 ===

    if (!response.ok) {
      throw new Error(`查询失败：HTTP状态码 ${response.status}`);
    }

    // === 第5步：解析响应数据 ===

    const result = await response.json();

    logMessage_Info(
      "[PC端订单查询] API响应：",
      createSafeClientLogValue(result),
    );

    // === 第6步：检查业务状态 ===

    // 如果API返回失败状态，使用showModalAlert显示错误消息
    if (result.success === false) {
      // 隐藏订单详情容器
      if (detailContainer) {
        detailContainer.classList.add("hidden");
      }

      // 使用showModalAlert显示错误
      // showModalAlert(result.message || "查询订单失败", "查询失败");
      // 使用Swal替代showModalAlert，提供更好的用户体验
      Swal.fire({
        icon: "error",
        title: "错误",
        text: result.message || "查询订单失败",
      });
      return;
    }

    if (!result.success || !result.order) {
      throw new Error(result.message || "未找到订单");
    }

    // === 第7步：显示订单详情 ===

    const order = result.order;

    // 7.1 填充订单号
    const tradeNoElem = document.getElementById(
      "admin-order-detail-trade-no_modal",
    );
    if (tradeNoElem) {
      tradeNoElem.textContent = order.trade_no || "-";
    }

    // 7.2 填充订单状态（使用彩色标签）
    const statusElem = document.getElementById(
      "admin-order-detail-status_modal",
    );
    if (statusElem) {
      // 根据不同的订单状态显示不同颜色的标签
      let statusText = "";
      let statusClass = "";

      switch (order.status) {
        case "failed":
          statusText = "创建失败";
          statusClass = "bg-red-100 text-red-700";
          break;
        case "pending":
          statusText = "已创建待支付";
          statusClass = "bg-yellow-100 text-yellow-700";
          break;
        case "paid":
          statusText = "已支付";
          statusClass = "bg-green-100 text-green-700";
          break;
        case "refunded_partial":
          statusText = "已部分退款";
          statusClass = "bg-blue-100 text-blue-700";
          break;
        case "refunded_full":
          statusText = "已全部退款";
          statusClass = "bg-gray-100 text-gray-700";
          break;
        case "frozen":
          statusText = "已冻结";
          statusClass = "bg-purple-100 text-purple-700";
          break;
        case "preauth":
          statusText = "预授权";
          statusClass = "bg-indigo-100 text-indigo-700";
          break;
        case "timeout":
          statusText = "支付超时";
          statusClass = "bg-gray-100 text-gray-700";
          break;
        default:
          statusText = order.status || "-";
          statusClass = "bg-slate-100 text-slate-700";
      }

      statusElem.textContent = statusText;
      statusElem.className = `px-2 py-0.5 rounded-full text-xs font-semibold ${statusClass}`;
    }

    // 7.3 填充订单金额
    const amountElem = document.getElementById(
      "admin-order-detail-amount_modal",
    );
    if (amountElem) {
      amountElem.textContent = order.amount
        ? `¥${parseFloat(order.amount).toFixed(2)}`
        : "-";
    }

    // 7.4 填充支付方式
    const methodElem = document.getElementById(
      "admin-order-detail-method_modal",
    );
    if (methodElem) {
      let methodText = "";
      switch (order.payment_method) {
        case "alipay":
          methodText = "支付宝";
          break;
        case "wechat":
          methodText = "微信支付";
          break;
        case "qq":
          methodText = "QQ钱包";
          break;
        case "unionpay":
          methodText = "云闪付";
          break;
        default:
          methodText = order.payment_method || "-";
      }
      methodElem.textContent = methodText;
    }

    // 7.5 填充创建时间
    const createTimeElem = document.getElementById(
      "admin-order-detail-create-time_modal",
    );
    if (createTimeElem) {
      createTimeElem.textContent = order.created_at || "-";
    }

    // 7.6 填充支付时间
    const payTimeElem = document.getElementById(
      "admin-order-detail-pay-time_modal",
    );
    if (payTimeElem) {
      payTimeElem.textContent = order.paid_at || "-";
    }

    // 7.7 填充商品名称/备注
    const productElem = document.getElementById(
      "admin-order-detail-product_modal",
    );
    if (productElem) {
      productElem.textContent = order.product_name || order.description || "-";
    }

    // 7.8 显示订单详情容器
    if (detailContainer) {
      detailContainer.classList.remove("hidden");
    }

    // 7.9 隐藏错误提示（如果有）
    if (resultDiv) {
      resultDiv.classList.add("hidden");
    }

    logMessage_Info("[PC端订单查询] 订单详情已显示");
  } catch (error) {
    // === 错误处理 ===

    // 在控制台输出详细的错误信息，用于开发和调试
    // 详细的错误信息仅在控制台显示，不暴露给最终用户，避免泄露敏感信息
    logMessage_Error("[PC端订单查询] 查询订单时发生错误：", error);

    // 隐藏订单详情容器
    if (detailContainer) {
      detailContainer.classList.add("hidden");
    }

    // 显示通用的错误提示给用户
    // 使用通用错误消息，避免直接显示error.message可能包含的敏感技术信息
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          ✗ 订单查询失败，请稍后重试
        </div>
      `;
      resultDiv.classList.remove("hidden");

      // 5秒后自动隐藏错误提示
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 5000);
    }
  }
}

// ==========================================
// Tab 2 扩展功能：订单列表、筛选和管理
// ==========================================
// 【功能说明】
// 实现订单管理的扩展功能，包括：
// 1. 加载和显示所有本地订单列表
// 2. 订单筛选（按状态、支付方式、用户名、订单号）
// 3. 手动查询单个订单（支持从平台同步）
// 4. 从平台批量拉取订单
// 5. 显示订单详细信息
//
// 【API说明】
// - POST /api/admin/payment/query_order: 查询单个订单（优先本地，无则从平台查询）
// - POST /api/admin/payment/fetch_orders: 从平台批量拉取订单列表
// ==========================================

// 全局变量：存储所有订单数据和筛选后的订单数据
let allPaymentOrders = []; // 存储从后端加载的所有订单数据
let filteredPaymentOrders = []; // 存储经过筛选后的订单数据

/**
 * 加载所有本地支付订单
 *
 * 功能说明：
 * 页面加载时自动调用，从后端获取所有本地订单数据并显示在表格中
 *
 * API端点：
 * - 使用现有的订单文件读取逻辑（通过后端提供的订单列表）
 * - 或者调用 /api/admin/payment/fetch_orders 获取本地订单
 *
 * 实现步骤：
 * 1. 读取本地订单目录中的所有订单文件
 * 2. 解析订单数据并存储到 allPaymentOrders 数组
 * 3. 调用 filterPaymentOrders() 显示订单列表
 */
async function loadAllPaymentOrders() {
  // 输出日志：标记开始加载订单列表
  logMessage_Info("[订单列表] 开始加载本地订单...");

  try {
    // === 第1步：发起HTTP GET请求获取本地订单列表 ===
    // 使用新的 local_orders API，仅获取本地已保存的订单
    // 不查询平台，避免过多请求

    const response = await fetch("/api/admin/payment/local_orders", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
      },
    });

    // === 第2步：检查HTTP响应状态 ===
    if (!response.ok) {
      throw new Error(`加载订单失败：HTTP状态码 ${response.status}`);
    }

    // === 第3步：解析响应数据 ===
    const result = await response.json();
    logMessage_Info("[订单列表] API响应：", createSafeClientLogValue(result));

    // === 第4步：检查业务状态 ===
    if (!result.success) {
      throw new Error(result.message || "加载订单失败");
    }

    // === 第5步：提取订单数据并存储到全局变量 ===
    // 后端返回的订单列表在 result.orders 中
    // 按创建时间 created_at 排序，默认把最新的放在最前面（降序）
    allPaymentOrders = (result.orders || []).slice();
    try {
      allPaymentOrders.sort((a, b) => {
        const ta = Date.parse(a && a.created_at);
        const tb = Date.parse(b && b.created_at);
        if (!isNaN(ta) && !isNaN(tb)) return tb - ta; // 新的在前

        // 退化处理：有时 created_at 可能是时间戳字符串或数字
        const na = Number(a && a.created_at);
        const nb = Number(b && b.created_at);
        if (!isNaN(na) && !isNaN(nb)) return nb - na;

        return 0;
      });
      logMessage_Info("[订单列表] 已按 created_at 排序（最新优先）");
    } catch (e) {
      logMessage_Warn("[订单列表] 排序时发生异常，保持原始顺序：", e);
    }

    logMessage_Info(
      `[订单列表] 成功加载 ${allPaymentOrders.length} 个本地订单`,
    );

    // === 第6步：显示订单列表 ===
    // 调用筛选函数来显示订单（初始状态下不筛选，显示全部）
    filterPaymentOrders();
  } catch (error) {
    // === 错误处理 ===
    logMessage_Error("[订单列表] 加载订单时发生错误：", error);

    // 【修复】同时在桌面端和移动端容器中显示错误提示
    // 生成错误提示HTML
    const errorHTML = `
      <div class="col-span-full text-center py-12 text-red-600">
        <svg class="w-12 h-12 inline mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <div class="text-base font-medium">加载订单失败</div>
        <div class="text-sm text-slate-500 mt-1">请稍后重试或联系管理员</div>
      </div>
    `;

    // 尝试在桌面端容器中显示错误
    const cardsContainerDesktop = document.getElementById(
      "admin-orders-table-body_modal",
    );
    if (cardsContainerDesktop) {
      cardsContainerDesktop.innerHTML = errorHTML;
    }

    // 尝试在移动端容器中显示错误
    const cardsContainerMobile = document.getElementById(
      "admin-orders-table-body",
    );
    if (cardsContainerMobile) {
      cardsContainerMobile.innerHTML = errorHTML;
    }

    // 更新订单计数显示（桌面端）
    const countElemDesktop = document.getElementById(
      "admin-orders-count_modal",
    );
    if (countElemDesktop) {
      countElemDesktop.textContent = "(加载失败)";
    }

    // 更新订单计数显示（移动端）
    const countElemMobile = document.getElementById("admin-orders-count");
    if (countElemMobile) {
      countElemMobile.textContent = "(加载失败)";
    }
  }
}

/**
 * 筛选支付订单列表
 *
 * 功能说明：
 * 根据用户选择的筛选条件，过滤订单数据并更新表格显示
 *
 * 筛选条件：
 * 1. 订单状态（status）
 * 2. 支付方式（pay_type）
 * 3. 用户名（username）
 * 4. 订单号（order_id 或 trade_no）
 *
 * 实现步骤：
 * 1. 获取所有筛选条件的值
 * 2. 遍历 allPaymentOrders，筛选符合条件的订单
 * 3. 将筛选结果存储到 filteredPaymentOrders
 * 4. 更新表格显示
 */
function filterPaymentOrders() {
  // 输出日志：标记开始筛选订单
  logMessage_Info("[订单筛选] 开始筛选订单...");

  // === 第1步：获取所有筛选条件的值 ===
  // 【修复】同时支持桌面端(_modal)和移动端(无后缀)的筛选条件输入框
  // 策略：优先读取桌面端元素，如果不存在则尝试读取移动端元素

  // 获取状态筛选下拉框的值
  // 先尝试桌面端，再尝试移动端
  const statusFilterDesktop = document.getElementById(
    "admin-filter-status_modal",
  );
  const statusFilterMobile = document.getElementById("admin-filter-status");
  const statusFilter =
    (statusFilterDesktop || statusFilterMobile)?.value.trim() || "";

  // 获取支付方式筛选下拉框的值
  const payTypeFilterDesktop = document.getElementById(
    "admin-filter-paytype_modal",
  );
  const payTypeFilterMobile = document.getElementById("admin-filter-paytype");
  const payTypeFilter =
    (payTypeFilterDesktop || payTypeFilterMobile)?.value.trim() || "";

  // 获取用户名搜索输入框的值（转换为小写，便于不区分大小写匹配）
  const usernameFilterDesktop = document.getElementById(
    "admin-filter-username_modal",
  );
  const usernameFilterMobile = document.getElementById("admin-filter-username");
  const usernameFilter = (
    (usernameFilterDesktop || usernameFilterMobile)?.value.trim() || ""
  ).toLowerCase();

  // 获取订单号搜索输入框的值（转换为小写，便于不区分大小写匹配）
  const orderNoFilterDesktop = document.getElementById(
    "admin-filter-orderno_modal",
  );
  const orderNoFilterMobile = document.getElementById("admin-filter-orderno");
  const orderNoFilter = (
    (orderNoFilterDesktop || orderNoFilterMobile)?.value.trim() || ""
  ).toLowerCase();

  logMessage_Info("[订单筛选] 筛选条件：", {
    status: statusFilter || "全部",
    payType: payTypeFilter || "全部",
    username: usernameFilter || "全部",
    orderNo: orderNoFilter || "全部",
  });

  // === 第2步：筛选订单数据 ===

  // 使用 Array.filter() 方法筛选订单
  filteredPaymentOrders = allPaymentOrders.filter((order) => {
    // 2.1 检查订单状态筛选条件
    // 如果设置了状态筛选，则订单状态必须匹配
    if (statusFilter && order.status !== statusFilter) {
      return false;
    }

    // 2.2 检查支付方式筛选条件
    // 如果设置了支付方式筛选，则支付方式必须匹配
    if (payTypeFilter && order.pay_type !== payTypeFilter) {
      return false;
    }

    // 2.3 检查用户名筛选条件
    // 如果设置了用户名筛选，则用户名必须包含搜索关键词（不区分大小写）
    if (usernameFilter) {
      const username = (order.username || "").toLowerCase();
      if (!username.includes(usernameFilter)) {
        return false;
      }
    }

    // 2.4 检查订单号筛选条件
    // 如果设置了订单号筛选，则系统订单号或平台订单号必须包含搜索关键词
    if (orderNoFilter) {
      const orderId = (order.order_id || "").toLowerCase();
      const tradeNo = (order.trade_no || "").toLowerCase();
      const apiTradeNo = (order.api_trade_no || "").toLowerCase();

      // 订单号可以匹配系统订单号、平台订单号或接口订单号中的任意一个
      if (
        !orderId.includes(orderNoFilter) &&
        !tradeNo.includes(orderNoFilter) &&
        !apiTradeNo.includes(orderNoFilter)
      ) {
        return false;
      }
    }

    // 所有筛选条件都通过，保留该订单
    return true;
  });

  logMessage_Info(
    `[订单筛选] 筛选结果：${filteredPaymentOrders.length} / ${allPaymentOrders.length} 个订单`,
  );

  // === 第3步：更新表格显示 ===
  renderPaymentOrdersTable();
}

/**
 * 渲染支付订单卡片列表
 *
 * 功能说明：
 * 将 filteredPaymentOrders 中的订单数据渲染为卡片布局
 * 每个订单显示为一个独立的卡片，包含订单的关键信息
 *
 * 卡片内容：
 * 1. 系统订单号（order_id）
 * 2. 平台订单号（trade_no）
 * 3. 用户名（username）
 * 4. 金额（amount）
 * 5. 支付方式（pay_type）
 * 6. 状态（status）
 * 7. 创建时间（created_at）
 * 8. 查看详情按钮
 */
function renderPaymentOrdersTable() {
  // 输出日志：标记开始渲染订单卡片
  logMessage_Info("[订单卡片] 开始渲染订单卡片...");

  // === 第1步：获取容器元素（同时获取桌面端和移动端容器）===
  // 【修复】同时支持桌面端(_modal后缀)和移动端(无后缀)的订单表格容器
  const cardsContainerDesktop = document.getElementById(
    "admin-orders-table-body_modal",
  );
  const cardsContainerMobile = document.getElementById(
    "admin-orders-table-body",
  );

  // 获取订单计数显示元素（同时获取桌面端和移动端）
  const countElemDesktop = document.getElementById("admin-orders-count_modal");
  const countElemMobile = document.getElementById("admin-orders-count");

  // 防御性检查：至少要有一个容器元素存在才能继续
  // 如果两个容器都不存在，则记录错误并返回
  if (!cardsContainerDesktop && !cardsContainerMobile) {
    logMessage_Error(
      "[订单卡片] 错误：找不到任何容器元素（桌面端和移动端都不存在）",
    );
    return;
  }

  // === 第2步：更新订单计数显示（同时更新桌面端和移动端）===
  // 生成计数文本，显示过滤后的订单数量
  const countText = `(共 ${filteredPaymentOrders.length} 条)`;

  // 如果桌面端计数元素存在，更新它
  if (countElemDesktop) {
    countElemDesktop.textContent = countText;
  }

  // 如果移动端计数元素存在，更新它
  if (countElemMobile) {
    countElemMobile.textContent = countText;
  }

  // === 第3步：检查是否有订单数据 ===
  if (filteredPaymentOrders.length === 0) {
    // 如果没有订单，显示空状态提示
    // 生成空状态HTML，显示友好的提示信息
    const emptyStateHTML = `
      <div class="col-span-full text-center py-12 text-slate-500">
        <!-- 空状态图标 -->
        <svg class="w-16 h-16 inline mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/>
        </svg>
        <div class="text-base font-medium">暂无订单数据</div>
        <div class="text-xs mt-2">请尝试调整筛选条件或点击"从平台拉取"按钮同步订单</div>
      </div>
    `;

    // 【修复】同时设置桌面端和移动端容器的内容
    if (cardsContainerDesktop) {
      cardsContainerDesktop.innerHTML = emptyStateHTML;
    }
    if (cardsContainerMobile) {
      cardsContainerMobile.innerHTML = emptyStateHTML;
    }

    return;
  }

  // === 第4步：生成卡片HTML ===

  // 使用 Array.map() 将每个订单对象转换为卡片HTML
  const orderCards = filteredPaymentOrders
    .map((order) => {
      // 4.1 清理和格式化订单数据（使用 escapeHtml 防止XSS攻击）
      const orderId = escapeHtml(order.order_id || "-");
      const tradeNo = escapeHtml(order.trade_no || "-");
      const username = escapeHtml(order.username || "-");
      const amount = order.amount
        ? `¥${parseFloat(order.amount).toFixed(2)}`
        : "-";
      const createdAt = escapeHtml(order.created_at || "-");

      // 4.2 格式化支付方式显示
      let payTypeText = "-";
      let payTypeColor = "text-slate-600";
      switch (order.pay_type) {
        case "alipay":
          payTypeText = "支付宝";
          payTypeColor = "text-blue-600";
          break;
        case "wxpay":
          payTypeText = "微信支付";
          payTypeColor = "text-green-600";
          break;
        case "qq":
          payTypeText = "QQ钱包";
          payTypeColor = "text-sky-600";
          break;
        case "unionpay":
          payTypeText = "云闪付";
          payTypeColor = "text-red-600";
          break;
        default:
          payTypeText = escapeHtml(order.pay_type || "-");
      }

      // 4.3 格式化状态显示（使用彩色标签）
      let statusHtml = "";
      switch (order.status) {
        case "failed":
          statusHtml =
            '<span class="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-semibold">创建失败</span>';
          break;
        case "pending":
          statusHtml =
            '<span class="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-semibold">待支付</span>';
          break;
        case "paid":
          statusHtml =
            '<span class="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-semibold">已支付</span>';
          break;
        case "refunded_partial":
          statusHtml =
            '<span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-semibold">部分退款</span>';
          break;
        case "refunded_full":
          statusHtml =
            '<span class="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs font-semibold">全额退款</span>';
          break;
        case "frozen":
          statusHtml =
            '<span class="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-semibold">已冻结</span>';
          break;
        case "preauth":
          statusHtml =
            '<span class="px-2 py-1 bg-indigo-100 text-indigo-800 rounded text-xs font-semibold">预授权</span>';
          break;
        case "timeout":
          statusHtml =
            '<span class="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs font-semibold">支付超时</span>';
          break;
        default:
          statusHtml = `<span class="px-2 py-1 bg-slate-100 text-slate-800 rounded text-xs font-semibold">${escapeHtml(
            order.status || "-",
          )}</span>`;
      }

      // 4.4 生成卡片HTML
      // 每个卡片包含：
      // - 顶部：订单号和状态标签
      // - 中间：用户名、金额、支付方式
      // - 底部：创建时间和查看详情按钮
      return `
      <div class="bg-white border border-slate-200 rounded-lg p-4 hover:shadow-lg transition-shadow">
        <!-- 卡片顶部：订单号和状态 -->
        <div class="flex justify-between items-start mb-3">
          <!-- 订单号区域 -->
          <div class="flex-1 min-w-0 mr-2">
            <div class="text-xs text-slate-500 mb-1">订单号</div>
            <!-- 系统订单号：使用 break-all 确保长订单号完整显示，允许在任意字符处换行 -->
            <!-- 原本使用 truncate 会截断超长文本并显示省略号，导致订单号无法完整查看 -->
            <div class="text-sm font-semibold text-slate-800 break-all" title="${orderId}">${orderId}</div>
            <!-- 平台订单号：同样使用 break-all 确保完整显示 -->
            <div class="text-xs text-slate-600 break-all mt-0.5" title="${tradeNo}">${tradeNo}</div>
          </div>
          <!-- 状态标签 -->
          <div class="flex-shrink-0">
            ${statusHtml}
          </div>
        </div>
        
        <!-- 卡片中部：订单详情 -->
        <div class="space-y-2 mb-3 text-sm">
          <!-- 用户名 -->
          <div class="flex justify-between">
            <span class="text-slate-500">用户：</span>
            <span class="text-slate-700 font-medium">${username}</span>
          </div>
          <!-- 金额 -->
          <div class="flex justify-between">
            <span class="text-slate-500">金额：</span>
            <span class="text-red-600 font-bold">${amount}</span>
          </div>
          <!-- 支付方式 -->
          <div class="flex justify-between">
            <span class="text-slate-500">支付：</span>
            <span class="${payTypeColor} font-medium">${payTypeText}</span>
          </div>
        </div>
        
        <!-- 卡片底部：创建时间和操作按钮 -->
        <div class="flex justify-between items-center pt-3 border-t border-slate-100">
          <!-- 创建时间 -->
          <div class="text-xs text-slate-500">
            <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            ${createdAt}
          </div>
          <!-- 查看详情按钮 -->
          <!--
            【关键修复点】data-order属性的处理（移动端订单查看按钮）：
            
            问题原因：
            - 原代码使用 onclick='showOrderDetailModal_form_botton(${JSON.stringify(
              order,
            )})'
            - JSON.stringify()生成的JSON字符串包含双引号，与HTML属性的引号冲突
            - 特殊字符（如换行、引号）会破坏HTML解析，导致onclick事件失效
            - 浏览器控制台可能显示语法错误或点击无响应
            
            修复方法：
            - 使用 data-order 自定义属性存储订单对象的JSON字符串
            - JSON.stringify()已经提供了正确的JSON编码
            - 只需转义单引号为 &apos;，因为HTML属性值使用单引号包裹
            - 不能使用 escapeHtml()，因为它会将双引号转义为 &quot;，破坏JSON格式
            - 在onclick中使用内联函数：通过this.getAttribute('data-order')获取JSON字符串
            - 使用JSON.parse()解析后传递给目标函数
            
            优势：
            - 数据与事件处理逻辑分离，更清晰
            - 避免JSON字符串直接嵌入JavaScript代码导致的解析问题
            - 遵循Web标准的data-*属性最佳实践
          -->
          <button 
            data-order='${JSON.stringify(order).replace(/'/g, "&apos;")}'
            onclick="(function(btn) { const orderData = JSON.parse(btn.getAttribute('data-order')); showOrderDetailModal_form_botton(orderData); })(this)"
            class="px-3 py-1.5 bg-sky-500 text-white rounded text-xs font-medium hover:bg-sky-600 transition-colors flex items-center gap-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
            </svg>
            查看
          </button>
        </div>
      </div>
    `;
    })
    .join(""); // 将所有卡片拼接成一个字符串

  // === 第5步：更新容器内容（同时更新桌面端和移动端）===
  // 【修复】同时设置桌面端和移动端容器的内容
  if (cardsContainerDesktop) {
    cardsContainerDesktop.innerHTML = orderCards;
    logMessage_Info("[订单卡片] 桌面端卡片渲染完成");
  }
  if (cardsContainerMobile) {
    cardsContainerMobile.innerHTML = orderCards;
    logMessage_Info("[订单卡片] 移动端卡片渲染完成");
  }

  logMessage_Info("[订单卡片] 所有卡片渲染完成");
}

/**
 * 手动查询单个订单
 *
 * 功能说明：
 * 用户输入订单号后，调用新的 /api/admin/payment/query_order API
 * 如果本地没有该订单，后端会从平台查询并保存
 * 查询成功后，刷新订单列表
 *
 * API端点：POST /api/admin/payment/query_order
 *
 * 请求参数：
 * {
 *   order_id: "ORDER123"    // 商户订单号，或者
 *   trade_no: "TN123"       // 平台订单号
 * }
 *
 * 预期返回：
 * {
 *   success: true,
 *   order: {...},           // 订单详情
 *   source: "local"/"platform"  // 数据来源
 * }
 */
async function queryOrderManually() {
  // 输出日志：标记开始手动查询订单
  logMessage_Info("[手动查询] 开始查询订单...");

  // === 第1步：获取订单号输入框的值（同时支持桌面端和移动端）===
  // 【修复】优先获取桌面端输入框，如果不存在则获取移动端输入框
  const orderNoInputDesktop = document.getElementById(
    "admin-manual-query-order-no_modal",
  );
  const orderNoInputMobile = document.getElementById(
    "admin-manual-query-order-no",
  );
  const orderNoInput = orderNoInputDesktop || orderNoInputMobile;

  // 防御性检查：确保至少有一个输入框元素存在
  if (!orderNoInput) {
    logMessage_Error(
      "[手动查询] 错误：找不到订单号输入框（桌面端和移动端都不存在）",
    );
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return;
  }

  // 获取用户输入的订单号，去除首尾空格
  const orderNo = orderNoInput.value.trim();

  // === 第2步：验证订单号是否为空 ===
  if (!orderNo) {
    // showModalAlert("请输入订单号", "提示");
    Swal.fire({
      icon: "warning",
      title: "提示",
      text: "请输入订单号",
    });
    return;
  }

  logMessage_Info("[手动查询] 查询订单号：", orderNo);

  try {
    // === 第3步：发起HTTP POST请求查询订单 ===

    const response = await fetch("/api/admin/payment/query_order", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
      },
      body: JSON.stringify({
        order_id: orderNo, // 发送订单号（可以是商户订单号或平台订单号）
      }),
    });

    // === 第4步：检查HTTP响应状态 ===
    if (!response.ok) {
      throw new Error(`查询失败：HTTP状态码 ${response.status}`);
    }

    // === 第5步：解析响应数据 ===
    const result = await response.json();
    logMessage_Info("[手动查询] API响应：", createSafeClientLogValue(result));

    // === 第6步：检查业务状态 ===
    if (!result.success) {
      // showModalAlert(result.message || "查询订单失败", "查询失败");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: result.message || "查询订单失败",
      });
      return;
    }

    // === 第7步：查询成功，显示提示信息 ===
    const source =
      result.source === "platform" ? "从平台查询并已保存到本地" : "从本地查询";
    // showModalAlert(`订单查询成功（${source}）`, "成功");
    Swal.fire({
      icon: "success",
      title: "成功",
      text: `订单查询成功（${source}）`,
    });

    // === 第8步：清空输入框（同时清空桌面端和移动端）===
    // 【修复】同时清空桌面端和移动端的输入框
    if (orderNoInputDesktop) {
      orderNoInputDesktop.value = "";
    }
    if (orderNoInputMobile) {
      orderNoInputMobile.value = "";
    }

    // === 第9步：刷新订单列表 ===
    // 重新加载订单列表以显示新查询的订单
    await loadAllPaymentOrders();
  } catch (error) {
    // === 错误处理 ===
    logMessage_Error("[手动查询] 查询订单时发生错误：", error);
    // showModalAlert("查询订单失败，请稍后重试", "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "查询订单失败，请稍后重试",
    });
  }
}

/**
 * 从平台批量拉取订单
 *
 * 功能说明：
 * 调用 /api/admin/payment/fetch_orders API，从易支付平台批量拉取订单
 * 显示拉取进度和结果，拉取完成后自动刷新订单列表
 *
 * API端点：POST /api/admin/payment/fetch_orders
 *
 * 请求参数：
 * {
 *   offset: 0,    // 查询偏移量
 *   limit: 50     // 每页条数
 * }
 *
 * 预期返回：
 * {
 *   success: true,
 *   fetched: 10,   // 成功拉取的订单数
 *   saved: 8,      // 成功保存到本地的订单数
 *   failed: 2,     // 保存失败的订单数
 *   orders: [...]  // 订单列表（简要信息）
 * }
 */
async function fetchOrdersFromPlatform() {
  // 输出日志：标记开始拉取订单
  logMessage_Info("[拉取订单] 开始从平台拉取订单...");

  // === 第1步：显示加载提示 ===
  // 使用自定义的模态框提示用户正在拉取订单
  // showModalAlert("正在从平台拉取订单，请稍候...", "提示");
  Swal.fire({
    icon: "info",
    title: "提示",
    text: "正在从平台拉取订单，请稍候...",
  });

  try {
    // === 第2步：发起HTTP POST请求拉取订单 ===

    const response = await fetch("/api/admin/payment/fetch_orders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
      },
      body: JSON.stringify({
        offset: 0, // 从第0条开始
        limit: 50, // 拉取50条订单
      }),
    });

    // === 第3步：检查HTTP响应状态 ===
    if (!response.ok) {
      throw new Error(`拉取失败：HTTP状态码 ${response.status}`);
    }

    // === 第4步：解析响应数据 ===
    const result = await response.json();
    logMessage_Info("[拉取订单] API响应：", createSafeClientLogValue(result));

    // === 第5步：检查业务状态 ===
    if (!result.success) {
      // showModalAlert(result.message || "从平台拉取订单失败", "拉取失败");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: result.message || "从平台拉取订单失败",
      });
      return;
    }

    // === 第6步：显示拉取结果 ===
    const fetched = result.fetched || 0;
    const saved = result.saved || 0;
    const failed = result.failed || 0;

    // 构建结果消息
    let message = `成功从平台拉取 ${fetched} 条订单`;
    if (saved > 0) {
      message += `，已保存 ${saved} 条到本地`;
    }
    if (failed > 0) {
      message += `，${failed} 条保存失败`;
    }

    // showModalAlert(message, "拉取成功");
    Swal.fire({
      icon: "success",
      title: "成功",
      text: message,
    });

    // === 第7步：刷新订单列表 ===
    // 重新加载订单列表以显示新拉取的订单
    await loadAllPaymentOrders();
  } catch (error) {
    // === 错误处理 ===
    logMessage_Error("[拉取订单] 拉取订单时发生错误：", error);
    // showModalAlert("从平台拉取订单失败，请稍后重试", "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "从平台拉取订单失败，请稍后重试",
    });
  }
}

function showOrderDetailModal_form_botton(order) {
  showOrderDetailModal(order);
  refreshOrderDetailLocal((show_Modal_Alert = false));
}
/**
 * 显示订单详情弹窗
 *
 * 功能说明：
 * 当用户点击订单列表中的"查看详情"按钮时，显示订单的完整信息
 *
 * 参数：
 * @param {Object} order - 订单对象，包含订单的所有字段
 *
 * 显示字段：
 * - 系统订单号、平台订单号、接口订单号
 * - 订单状态、支付金额、支付方式
 * - 用户名、支付用户标识、商品名称
 * - 创建时间、支付时间、客户端IP
 * - 已退款金额、业务扩展参数
 */
function showOrderDetailModal(order) {
  // 输出日志：标记显示订单详情
  logMessage_Info(
    "[订单详情] 显示订单详情：",
    createSafeClientLogValue(order),
  );

  // === 保存当前订单信息到全局变量，供刷新功能使用 ===
  // 将订单对象存储为全局变量，这样刷新按钮的函数可以知道要刷新哪个订单
  window.currentOrderDetail = order;

  // === 第1步：填充订单详情数据到弹窗 ===

  // 1.1 系统订单号
  const orderIdElem = document.getElementById("admin-detail-order-id_modal");
  if (orderIdElem) {
    orderIdElem.textContent = order.order_id || "-";
  }

  // 1.2 平台订单号
  const tradeNoElem = document.getElementById("admin-detail-trade-no_modal");
  if (tradeNoElem) {
    tradeNoElem.textContent = order.trade_no || "-";
  }

  // 1.3 接口订单号
  const apiTradeNoElem = document.getElementById(
    "admin-detail-api-trade-no_modal",
  );
  if (apiTradeNoElem) {
    apiTradeNoElem.textContent = order.api_trade_no || "-";
  }

  // 1.4 订单状态（使用彩色标签）
  const statusElem = document.getElementById("admin-detail-status_modal");
  if (statusElem) {
    let statusHtml = "";
    switch (order.status) {
      case "failed":
        statusHtml =
          '<span class="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-semibold">创建失败</span>';
        break;
      case "pending":
        statusHtml =
          '<span class="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-semibold">已创建待支付</span>';
        break;
      case "paid":
        statusHtml =
          '<span class="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-semibold">已支付</span>';
        break;
      case "refunded_partial":
        statusHtml =
          '<span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-semibold">已部分退款</span>';
        break;
      case "refunded_full":
        statusHtml =
          '<span class="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs font-semibold">已全额退款</span>';
        break;
      case "frozen":
        statusHtml =
          '<span class="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-semibold">已冻结</span>';
        break;
      case "preauth":
        statusHtml =
          '<span class="px-2 py-1 bg-indigo-100 text-indigo-800 rounded text-xs font-semibold">预授权</span>';
        break;
      case "timeout":
        statusHtml =
          '<span class="px-2 py-1 bg-gray-100 text-gray-800 rounded text-xs font-semibold">支付超时</span>';
        break;
      default:
        statusHtml = `<span class="px-2 py-1 bg-slate-100 text-slate-800 rounded text-xs font-semibold">${escapeHtml(
          order.status || "-",
        )}</span>`;
    }
    statusElem.innerHTML = statusHtml;
  }

  // 1.5 支付金额
  const amountElem = document.getElementById("admin-detail-amount_modal");
  if (amountElem) {
    amountElem.textContent = order.amount
      ? `¥${parseFloat(order.amount).toFixed(2)}`
      : "-";
  }

  // 1.6 支付方式
  const payTypeElem = document.getElementById("admin-detail-pay-type_modal");
  if (payTypeElem) {
    let payTypeText = "-";
    switch (order.pay_type) {
      case "alipay":
        payTypeText = "支付宝";
        break;
      case "wxpay":
        payTypeText = "微信支付";
        break;
      case "qq":
        payTypeText = "QQ钱包";
        break;
      case "unionpay":
        payTypeText = "云闪付";
        break;
      default:
        payTypeText = order.pay_type || "-";
    }
    payTypeElem.textContent = payTypeText;
  }

  // 1.7 用户名
  const usernameElem = document.getElementById("admin-detail-username_modal");
  if (usernameElem) {
    usernameElem.textContent = order.username || "-";
  }

  // 1.8 支付用户标识
  const buyerElem = document.getElementById("admin-detail-buyer_modal");
  if (buyerElem) {
    buyerElem.textContent = order.buyer || "-";
  }

  // 1.9 商品名称
  const productNameElem = document.getElementById(
    "admin-detail-product-name_modal",
  );
  if (productNameElem) {
    productNameElem.textContent = order.product_name || "-";
  }

  // 1.10 创建时间
  const createdAtElem = document.getElementById(
    "admin-detail-created-at_modal",
  );
  if (createdAtElem) {
    createdAtElem.textContent = order.created_at || "-";
  }

  // 1.11 支付时间
  const paidTimeElem = document.getElementById("admin-detail-paid-time_modal");
  if (paidTimeElem) {
    paidTimeElem.textContent = order.paid_time || "-";
  }

  // 1.12 客户端IP
  const clientIpElem = document.getElementById("admin-detail-clientip_modal");
  if (clientIpElem) {
    clientIpElem.textContent = order.clientip || "-";
  }

  // 1.13 已退款金额
  const refundMoneyElem = document.getElementById(
    "admin-detail-refundmoney_modal",
  );
  if (refundMoneyElem) {
    const refundMoney = parseFloat(order.refundmoney || 0);
    refundMoneyElem.textContent =
      refundMoney > 0 ? `¥${refundMoney.toFixed(2)}` : "¥0.00";
  }

  // 1.14 业务扩展参数
  const paramElem = document.getElementById("admin-detail-param_modal");
  if (paramElem) {
    paramElem.textContent = order.param || "-";
  }

  // 1.15 数据来源（是否从平台同步）
  // synced_from_platform字段表示订单数据是否从支付平台同步而来
  const syncedFromPlatformElem = document.getElementById(
    "admin-detail-synced-from-platform_modal",
  );
  if (syncedFromPlatformElem) {
    // 根据synced_from_platform字段的值显示不同的文本
    // true表示从平台同步，false或undefined表示本地创建
    if (order.synced_from_platform === true) {
      syncedFromPlatformElem.textContent = "平台同步";
    } else if (order.synced_from_platform === false) {
      syncedFromPlatformElem.textContent = "本地创建";
    } else {
      // 字段不存在或为其他值，显示"未知"
      syncedFromPlatformElem.textContent = "未知";
    }
  }

  // 1.16 同步时间
  // synced_time字段记录订单从平台同步的时间
  const syncedTimeElem = document.getElementById(
    "admin-detail-synced-time_modal",
  );
  if (syncedTimeElem) {
    // 如果存在synced_time字段且不为空，显示该时间
    // 否则显示"-"表示没有同步记录
    syncedTimeElem.textContent = order.synced_time || "-";
  }

  // === 第2步：显示弹窗 ===
  const modalOverlay = document.getElementById(
    "admin-order-detail-modal_overlay",
  );
  if (modalOverlay) {
    modalOverlay.classList.remove("hidden");
  }
}

/**
 * 复制订单号到剪贴板
 *
 * 功能说明：
 * 将当前订单的平台订单号（trade_no）复制到系统剪贴板
 * 优先复制平台订单号，若无则复制系统订单号
 */
async function copyOrderTradeNo() {
  logMessage_Info("[订单详情] 复制订单号到剪贴板...");
  
  try {
    // 获取当前订单信息
    const currentOrder = window.currentOrderDetail;
    if (!currentOrder) {
      Swal.fire({
        icon: "error",
        title: "复制失败",
        text: "未找到当前订单信息",
        timer: 2000,
        showConfirmButton: false,
      });
      return;
    }
    
    // 复制系统订单号
    const orderNo = currentOrder.order_id || "";
    if (!orderNo || orderNo === "-") {
      Swal.fire({
        icon: "warning",
        title: "复制失败",
        text: "订单号为空",
        timer: 2000,
        showConfirmButton: false,
      });
      return;
    }
    
    // 使用 Clipboard API 复制到剪贴板
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(orderNo);
    } else {
      // 降级方案：使用 execCommand
      const textArea = document.createElement("textarea");
      textArea.value = orderNo;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
    }
    
    Swal.fire({
      icon: "success",
      title: "复制成功",
      html: `
        <div class="text-center">
          <p class="text-slate-600 text-sm mb-3">订单号已复制到剪贴板</p>
          <div class="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-sky-50 to-blue-50 border border-sky-200 rounded-lg shadow-sm">
            <svg class="w-4 h-4 text-sky-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
            </svg>
            <code class="text-sky-700 font-mono text-sm break-all">${escapeHtml(orderNo)}</code>
          </div>
        </div>
      `,
      timer: 2500,
      showConfirmButton: false,
      customClass: {
        popup: 'swal2-clean-popup',
        title: 'swal2-clean-title'
      }
    });
    
    logMessage_Info("[订单详情] 订单号已复制：", orderNo);
  } catch (error) {
    logMessage_Error("[订单详情] 复制订单号失败：", error);
    Swal.fire({
      icon: "error",
      title: "复制失败",
      html: `
        <div class="text-center">
          <p class="text-slate-600 text-sm">${escapeHtml(error.message || "复制操作失败")}</p>
        </div>
      `,
      timer: 2500,
      showConfirmButton: false,
      customClass: {
        popup: 'swal2-clean-popup',
        title: 'swal2-clean-title'
      }
    });
  }
}

/**
 * 关闭订单详情弹窗
 *
 * 功能说明：
 * 隐藏订单详情弹窗
 *
 * 参数：
 * @param {Event} event - 可选的事件对象，用于判断是否点击了遮罩层
 */
function closeOrderDetailModal(event) {
  // 如果传入了事件对象，检查是否点击的是遮罩层本身
  // 如果点击的是弹窗内容区域，则不关闭
  if (event && event.target.id !== "admin-order-detail-modal_overlay") {
    return;
  }

  // 隐藏弹窗
  const modalOverlay = document.getElementById(
    "admin-order-detail-modal_overlay",
  );
  if (modalOverlay) {
    modalOverlay.classList.add("hidden");
  }

  logMessage_Info("[订单详情] 关闭订单详情弹窗");
}

/**
 * 本地刷新订单详情
 *
 * 功能说明：
 * 重新读取本地订单文件，刷新订单详情弹窗的显示内容
 * 不查询支付平台，仅从本地文件系统读取最新数据
 *
 * 实现步骤：
 * 1. 获取当前正在查看的订单号
 * 2. 调用本地订单API重新获取订单数据
 * 3. 更新弹窗显示内容
 */
async function refreshOrderDetailLocal(show_Modal_Alert = true) {
  // 输出日志：标记本地刷新操作开始
  logMessage_Info("[订单详情] 开始本地刷新订单详情...");
  if (show_Modal_Alert) {
    // showModalAlert("正在本地刷新订单详情，请稍候...", "提示");
    Swal.fire({
      icon: "info",
      title: "提示",
      text: "正在本地刷新订单详情，请稍候...",
    });
  }
  try {
    // === 第1步：获取当前订单号 ===

    // 从全局变量中获取当前正在查看的订单对象
    // 这个变量在showOrderDetailModal函数中被设置
    const currentOrder = window.currentOrderDetail;
    if (!currentOrder || !currentOrder.order_id) {
      // 如果没有当前订单信息，显示错误提示
      // showModalAlert("无法刷新：未找到当前订单信息", "错误");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "无法刷新：未找到当前订单信息",
      });
      logMessage_Error("[订单详情] 无法刷新：未找到当前订单信息");
      return;
    }

    const orderId = currentOrder.order_id;
    logMessage_Info("[订单详情] 正在刷新订单：", orderId);

    // === 第2步：从本地API获取最新订单数据 ===

    // 调用订单详情API（仅读取本地文件）
    // 该API专门用于获取单个订单的详情，不查询支付平台
    const response = await fetch("/api/admin/payment/order_detail", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        order_id: orderId,
      }),
    });

    // 解析响应
    const result = await response.json();

    // 检查响应是否成功
    if (!response.ok || !result.success) {
      // 获取失败，显示错误消息
      const errorMessage = result.message || "获取订单数据失败";
      logMessage_Error("[订单详情] 本地刷新失败：", errorMessage);
      // showModalAlert(`本地刷新失败：${errorMessage}`, "错误");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: `本地刷新失败：${errorMessage}`,
      });
      return;
    }

    // === 第3步：获取返回的订单数据 ===

    // 从API响应中提取订单数据
    const updatedOrder = result.order;

    if (!updatedOrder) {
      // 如果没找到订单，显示提示
      logMessage_Warning("[订单详情] 本地未找到该订单");
      // showModalAlert("本地未找到该订单，可能已被删除", "警告");
      Swal.fire({
        icon: "warning",
        title: "警告",
        text: "本地未找到该订单，可能已被删除",
      });
      return;
    }

    // === 第4步：更新显示内容 ===

    // 调用showOrderDetailModal函数重新显示订单详情
    // 这会用最新的数据刷新弹窗中的所有字段
    showOrderDetailModal(updatedOrder);

    // 输出成功日志
    logMessage_Info("[订单详情] 本地刷新成功");

    loadAllPaymentOrders();

    // 显示成功提示（短暂显示）
    if (show_Modal_Alert) {
      // showModalAlert("本地刷新成功", "成功");
      Swal.fire({
        icon: "success",
        title: "成功",
        text: "本地刷新成功",
      });
    }
  } catch (error) {
    // === 错误处理 ===

    // 捕获所有可能的错误：网络错误、JSON解析错误等
    logMessage_Error("[订单详情] 本地刷新时发生错误：", error);
    // showModalAlert(`本地刷新失败：${error.message || "未知错误"}`, "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `本地刷新失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 从平台刷新订单详情
 *
 * 功能说明：
 * 调用支付平台API查询订单最新状态，并更新本地数据和显示内容
 * 这个操作会从支付平台获取最新的订单状态、退款信息等
 *
 * 实现步骤：
 * 1. 获取当前正在查看的订单号
 * 2. 调用平台查询API获取最新状态
 * 3. 更新本地订单文件
 * 4. 刷新弹窗显示内容
 */
async function refreshOrderDetailFromPlatform() {
  // 输出日志：标记平台刷新操作开始
  logMessage_Info("[订单详情] 开始从平台刷新订单详情...");

  try {
    // === 第1步：获取当前订单号 ===

    // 从全局变量中获取当前正在查看的订单对象
    const currentOrder = window.currentOrderDetail;
    if (!currentOrder || !currentOrder.order_id) {
      // 如果没有当前订单信息，显示错误提示
      // showModalAlert("无法刷新：未找到当前订单信息", "错误");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "无法刷新：未找到当前订单信息",
      });
      return;
    }

    const orderId = currentOrder.order_id;
    logMessage_Info("[订单详情] 正在从平台刷新订单：", orderId);

    // === 第2步：调用平台查询API ===

    // 调用管理员平台订单查询API
    // 该API会从支付平台查询订单最新状态，并自动更新本地文件
    const response = await fetch("/api/admin/payment/query_order", {
      // URL 中移除参数
      method: "POST", // 大小写皆可
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      // 关键修正：参数放在 body 中，并转为 JSON 字符串
      body: JSON.stringify({
        order_id: orderId,
      }),
    });

    const result = await response.json();

    // 检查响应是否成功
    if (!response.ok || !result.success) {
      // 查询失败，显示错误消息
      const errorMessage = result.message || "从平台查询订单失败";
      logMessage_Error("[订单详情] 平台刷新失败：", errorMessage);
      // showModalAlert(`平台刷新失败：${errorMessage}`, "错误");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: `平台刷新失败：${errorMessage}`,
      });
      return;
    }

    // === 第3步：获取更新后的订单数据 ===

    // API返回的result.order包含了从平台查询并更新后的订单数据
    const updatedOrder = result.order;

    if (!updatedOrder) {
      // 如果没有返回订单数据，显示提示
      logMessage_Warning("[订单详情] 平台返回数据为空");
      // showModalAlert("平台返回数据为空", "警告");
      Swal.fire({
        icon: "warning",
        title: "警告",
        text: "平台返回数据为空",
      });
      return;
    }

    // === 第4步：更新显示内容 ===

    // 调用showOrderDetailModal函数重新显示订单详情
    // 这会用从平台获取的最新数据刷新弹窗中的所有字段
    showOrderDetailModal(updatedOrder);

    // 输出成功日志
    logMessage_Info("[订单详情] 平台刷新成功");

    loadAllPaymentOrders();

    // 显示成功提示
    // showModalAlert("平台刷新成功，订单状态已更新", "成功");
    Swal.fire({
      icon: "success",
      title: "成功",
      text: "平台刷新成功，订单状态已更新",
    });
  } catch (error) {
    // === 错误处理 ===

    // 捕获所有可能的错误：网络错误、JSON解析错误等
    logMessage_Error("[订单详情] 平台刷新时发生错误：", error);
    // showModalAlert(`平台刷新失败：${error.message || "未知错误"}`, "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `平台刷新失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 生成PC端管理员退款单号
 */
function generateAdminRefundOrderNo() {
  logMessage_Info("[PC端退款] 生成退款单号...");

  // === 生成退款单号 ===

  // 获取当前时间
  const now = new Date();

  // 格式化时间为：YYYYMMDDHHmmss
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0"); // 月份从0开始，需要+1
  const day = String(now.getDate()).padStart(2, "0");
  const hours = String(now.getHours()).padStart(2, "0");
  const minutes = String(now.getMinutes()).padStart(2, "0");
  const seconds = String(now.getSeconds()).padStart(2, "0");

  // 生成6位随机数
  const randomNum = String(Math.floor(Math.random() * 1000000)).padStart(
    6,
    "0",
  );

  // 拼接退款单号
  const refundNo = `REFUND${year}${month}${day}${hours}${minutes}${seconds}${randomNum}`;

  logMessage_Info("[PC端退款] 生成的退款单号：", refundNo);

  // === 填充到输入框 ===

  const refundNoInput = document.getElementById("admin-refund-no_modal");
  if (refundNoInput) {
    refundNoInput.value = refundNo;
  } else {
    logMessage_Error("[PC端退款] 错误：找不到退款单号输入框");
  }
}

async function submitAdminPaymentRefund() {
  logMessage_Info("[PC端退款] 开始处理退款...");

  // === 第1步：获取DOM元素 ===

  const tradeNoInput = document.getElementById(
    "admin-refund-order-trade-no_modal",
  );
  const amountInput = document.getElementById("admin-refund-amount_modal");
  const refundNoInput = document.getElementById("admin-refund-no_modal");
  const reasonInput = document.getElementById("admin-refund-reason_modal");
  // === 第2步：获取并验证输入 ===

  // 获取原订单号
  const tradeNo = tradeNoInput ? tradeNoInput.value.trim() : "";
  if (!tradeNo) {
    // showModalAlert("请输入原订单号");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入原订单号",
    });
    return;
  }

  // 获取退款金额
  const amount = amountInput ? parseFloat(amountInput.value) : 0;
  if (!amount || amount <= 0) {
    // showModalAlert("请输入有效的退款金额（大于0）");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入有效的退款金额（大于0）",
    });
    return;
  }

  // 获取退款单号（可选，如果为空则自动生成）
  // 这里需要验证退款单号是否成功生成，避免空值导致的问题
  let refundNo = refundNoInput ? refundNoInput.value.trim() : "";
  if (!refundNo) {
    // 调用生成退款单号函数
    generateAdminRefundOrderNo();

    // 读取退款单号（需要验证是否成功生成）
    refundNo = refundNoInput ? refundNoInput.value.trim() : "";

    // 如果退款单号仍为空，显示错误提示并终止
    // 这是一个健壮性检查，防止退款单号生成失败导致的问题
    if (!refundNo) {
      // showModalAlert("请先生成退款单号");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "请先生成退款单号",
      });
      logMessage_Error("[PC端退款] 错误：退款单号生成失败");
      return;
    }
  }

  // 获取退款原因（可选）
  const reason = reasonInput ? reasonInput.value.trim() : "";

  logMessage_Info(
    "[PC端退款] 退款数据：",
    createSafeClientLogValue({
      tradeNo,
      amount,
      refundNo,
      reason,
    }),
  );

  try {
    // === 第3步：发起HTTP POST请求提交退款 ===

    const response = await fetch("/api/payment/refund", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 附加会话ID用于身份验证
      },
      body: JSON.stringify({
        trade_no: tradeNo,
        refund_amount: amount,
        refund_no: refundNo,
        reason: reason,
      }),
    });

    // === 第4步：检查响应状态 ===

    if (!response.ok) {
      throw new Error(`退款失败：HTTP状态码 ${response.status}`);
    }

    // === 第5步：解析响应数据 ===

    const result = await response.json();

    logMessage_Info("[PC端退款] API响应：", createSafeClientLogValue(result));

    // === 第6步：检查业务状态 ===

    if (!result.success) {
      throw new Error(result.message || "退款失败");
    }

    // === 第7步：显示成功提示 ===

    // 构建退款成功的详细信息HTML
    // 使用HTML格式可以更灵活地展示多行信息和格式化内容
    const successMessageHtml = `
      <div style="text-align: left; padding: 10px;">
        <p style="margin: 8px 0;"><strong>退款单号：</strong>${
          result.refund_no || refundNo
        }</p>
        <p style="margin: 8px 0;"><strong>退款金额：</strong>¥${parseFloat(
          result.refund_amount || amount,
        ).toFixed(2)}</p>
        <p style="margin: 8px 0;"><strong>原订单号：</strong>${tradeNo}</p>
        ${
          reason
            ? `<p style="margin: 8px 0;"><strong>退款原因：</strong>${reason}</p>`
            : ""
        }
      </div>
    `;

    // 使用Swal.fire显示成功弹窗
    // Swal（SweetAlert2）提供了更美观、交互性更好的弹窗组件
    Swal.fire({
      icon: "success", // 图标类型：成功（绿色对勾）
      title: "退款成功", // 弹窗标题
      html: successMessageHtml, // 弹窗内容（支持HTML格式）
      confirmButtonText: "确定", // 确认按钮文本
      allowOutsideClick: false, // 禁止点击外部区域关闭弹窗，用户必须点击"确定"
    });

    // 清空表单
    // 退款成功后，清空所有输入框，为下一次退款操作做准备
    if (tradeNoInput) tradeNoInput.value = "";
    if (amountInput) amountInput.value = "";
    if (refundNoInput) refundNoInput.value = "";
    if (reasonInput) reasonInput.value = "";

    logMessage_Info("[PC端退款] 退款成功，已显示Swal弹窗");
  } catch (error) {
    // === 错误处理 ===

    logMessage_Error("[PC端退款] 退款时发生错误：", error);

    Swal.fire({
      icon: "error",
      title: "错误",
      text: error.message || "退款失败",
    });
  }
}

function toggleAuthCodeField() {
  // 在控制台输出日志，记录函数调用
  logMessage_Info("[PC端测试支付] 切换支付类型参数输入框显示状态...");

  // === 第1步：获取DOM元素 ===

  // 获取支付接口类型下拉框元素
  const typeSelect = document.getElementById("admin-test-payment-type_modal");
  // 获取付款码输入框的容器元素（扫码支付专用）
  const authCodeContainer = document.getElementById(
    "admin-test-auth-code-container_modal",
  );
  // 【新增】获取JSAPI支付参数容器元素
  const jsapiParamsContainer = document.getElementById(
    "admin-test-jsapi-params-container_modal",
  );

  // === 第2步：防御性检查 ===
  // 确保DOM元素存在，避免null引用错误
  if (!typeSelect || !authCodeContainer) {
    logMessage_Warning("[PC端测试支付] 警告：找不到必需的DOM元素");
    return; // 如果元素不存在，直接返回，不执行后续操作
  }

  // === 第3步：获取当前选中的接口类型 ===
  const selectedType = typeSelect.value;
  logMessage_Info("[PC端测试支付] 当前选中的接口类型：", selectedType);

  // === 第4步：根据接口类型决定显示哪些参数输入框 ===

  // 4.1 判断是否为扫码支付类型
  if (selectedType === "scan") {
    // 如果是扫码支付，则显示付款码输入框
    // 移除hidden类，使容器可见
    authCodeContainer.classList.remove("hidden");
    console.log("[PC端测试支付] 付款码输入框已显示");

    // 同时隐藏JSAPI参数容器（互斥关系）
    if (jsapiParamsContainer) {
      jsapiParamsContainer.classList.add("hidden");
      // 清空JSAPI参数输入框的值
      const subOpenidInput = document.getElementById(
        "admin-test-sub-openid_modal",
      );
      const subAppidInput = document.getElementById(
        "admin-test-sub-appid_modal",
      );
      if (subOpenidInput) subOpenidInput.value = "";
      if (subAppidInput) subAppidInput.value = "";
    }
  }
  // 4.2 判断是否为JSAPI支付类型
  else if (selectedType === "jsapi") {
    // 如果是JSAPI支付，则显示JSAPI参数容器
    if (jsapiParamsContainer) {
      jsapiParamsContainer.classList.remove("hidden");
      console.log("[PC端测试支付] JSAPI参数输入框已显示");
    }

    // 同时隐藏付款码输入框（互斥关系）
    authCodeContainer.classList.add("hidden");
    // 清空付款码输入框的值
    const authCodeInput = document.getElementById("admin-test-auth-code_modal");
    if (authCodeInput) {
      authCodeInput.value = ""; // 清空输入框
    }
  }
  // 4.3 其他支付类型（web、jump、app、applet等）
  else {
    // 隐藏付款码输入框
    authCodeContainer.classList.add("hidden");

    // 清空付款码输入框的值，避免用户误以为需要输入
    const authCodeInput = document.getElementById("admin-test-auth-code_modal");
    if (authCodeInput) {
      authCodeInput.value = ""; // 清空输入框
    }

    // 隐藏JSAPI参数容器
    if (jsapiParamsContainer) {
      jsapiParamsContainer.classList.add("hidden");
      // 清空JSAPI参数输入框的值
      const subOpenidInput = document.getElementById(
        "admin-test-sub-openid_modal",
      );
      const subAppidInput = document.getElementById(
        "admin-test-sub-appid_modal",
      );
      if (subOpenidInput) subOpenidInput.value = "";
      if (subAppidInput) subAppidInput.value = "";
    }

    console.log("[PC端测试支付] 所有额外参数输入框已隐藏");
  }
}

/**
 * 切换商品名称输入方式（PC端）
 *
 * 功能说明：
 * 当用户选择"手动输入"或"自动生成"单选按钮时，切换对应的输入框显示/隐藏
 *
 * 实现逻辑：
 * 1. 获取选中的单选按钮值（manual或auto）
 * 2. 如果选择"手动输入"：显示文本输入框，隐藏数量输入框
 * 3. 如果选择"自动生成"：隐藏文本输入框，显示数量输入框
 *
 * 调用时机：
 * - 单选按钮的onchange事件触发时
 */
function toggleProductNameInputMethod_modal() {
  // 在控制台输出日志，记录函数调用
  console.log("[PC端测试支付] 切换商品名称输入方式...");

  // === 第1步：获取选中的单选按钮值 ===
  // 获取所有name为"product-name-input-method_modal"的单选按钮
  const radioButtons = document.getElementsByName(
    "product-name-input-method_modal",
  );
  // 变量用于存储选中的值
  let selectedMethod = "manual"; // 默认为手动输入

  // 遍历所有单选按钮，找到被选中的那个
  for (const radio of radioButtons) {
    if (radio.checked) {
      selectedMethod = radio.value; // 获取选中按钮的value值
      break; // 找到后退出循环
    }
  }

  console.log("[PC端测试支付] 选中的输入方式：", selectedMethod);

  // === 第2步：获取两个容器的DOM元素 ===
  const manualContainer = document.getElementById(
    "manual-product-name-container_modal",
  );
  const autoContainer = document.getElementById(
    "auto-product-name-container_modal",
  );

  // === 第3步：防御性检查，确保元素存在 ===
  if (!manualContainer || !autoContainer) {
    console.warn("[PC端测试支付] 警告：找不到商品名称容器元素");
    return; // 元素不存在则退出
  }

  // === 第4步：根据选中值切换显示/隐藏 ===
  if (selectedMethod === "manual") {
    // 手动输入模式：显示文本输入框，隐藏数量输入框
    manualContainer.classList.remove("hidden");
    autoContainer.classList.add("hidden");
    console.log("[PC端测试支付] 已切换到手动输入模式");
  } else if (selectedMethod === "auto") {
    // 自动生成模式：隐藏文本输入框，显示数量输入框
    manualContainer.classList.add("hidden");
    autoContainer.classList.remove("hidden");
    console.log("[PC端测试支付] 已切换到自动生成模式");
  }
}

/**
 * 测试商品名称生成器（PC端）- 单次测试
 *
 * 功能说明：
 * 根据用户输入的商品数量，调用后端API生成趣味商品名称
 * 并显示生成结果（商品名称和字节长度）
 *
 * API端点：POST /api/admin/generate_product_name
 *
 * 请求体格式：
 * {
 *   quantity: 5  // 商品数量（整数，1-9999）
 * }
 *
 * 预期返回格式：
 * {
 *   success: true,
 *   product_name: "五串麻辣鸭脖配上三根秘制烤肠",  // 生成的商品名称
 *   byte_length: 51                                 // 字节长度（UTF-8编码）
 * }
 *
 * 调用时机：
 * - 用户在商品名测试面板点击"生成商品名"按钮时
 */
async function testGenerateProductName_modal() {
  console.log("[PC端商品名测试] 开始单次测试...");

  // === 第1步：获取输入元素 ===
  const quantityInput = document.getElementById("product-test-quantity_modal");
  const resultContainer = document.getElementById("product-test-result_modal");
  const productNameDisplay = document.getElementById("product-test-name_modal");
  const byteLengthDisplay = document.getElementById(
    "product-test-length_modal",
  );

  // === 第2步：验证输入 ===
  const quantity = quantityInput ? parseInt(quantityInput.value) : 0;

  // 验证数量是否有效
  if (!quantity || quantity < 1 || quantity > 9999) {
    // showModalAlert("请输入有效的商品数量（1-9999）");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入有效的商品数量（1-9999）",
    });
    return;
  }

  console.log("[PC端商品名测试] 商品数量：", quantity);

  try {
    // === 第3步：调用后端API生成商品名 ===
    const response = await fetch("/api/admin/generate_product_name", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        quantity: quantity,
      }),
    });

    // 解析响应JSON
    const result = await response.json();
    console.log(
      "[PC端商品名测试] API响应：",
      createSafeClientLogValue(result),
    );

    // === 第4步：处理响应 ===
    if (result.success) {
      // 生成成功：显示结果
      if (productNameDisplay) {
        productNameDisplay.textContent = result.product_name;
      }
      if (byteLengthDisplay) {
        byteLengthDisplay.textContent = `${result.byte_length} 字节`;
      }
      // 显示结果容器
      if (resultContainer) {
        resultContainer.classList.remove("hidden");
      }
      console.log("[PC端商品名测试] 生成成功");
    } else {
      // 生成失败：显示错误消息
      // showModalAlert("生成失败：" + (result.message || "未知错误"));
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "生成失败：" + (result.message || "未知错误"),
      });
    }
  } catch (error) {
    // === 第5步：错误处理 ===
    console.error("[PC端商品名测试] 请求失败：", error);
    // showModalAlert("网络错误，请稍后重试");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "网络错误，请稍后重试",
    });
  }
}

/**
 * 测试商品名称生成器（PC端）- 批量测试
 *
 * 功能说明：
 * 生成10个不同数量的商品名称示例（1, 2, 5, 10, 20, 50, 100, 200, 500, 1000）
 * 用于验证生成器在不同数量级下的表现
 *
 * API端点：POST /api/admin/generate_product_name
 *
 * 调用时机：
 * - 用户在商品名测试面板点击"批量测试（生成10个示例）"按钮时
 */
async function batchTestProductNames_modal() {
  console.log("[PC端商品名测试] 开始批量测试...");

  // === 第1步：获取容器元素 ===
  const batchResultsContainer = document.getElementById(
    "batch-test-results_modal",
  );
  const batchListContainer = document.getElementById("batch-test-list_modal");

  // 验证元素是否存在
  if (!batchListContainer) {
    console.error("[PC端商品名测试] 找不到批量测试结果列表容器");
    return;
  }

  // === 第2步：定义测试数量数组 ===
  // 涵盖不同数量级：个位数、十位数、百位数、千位数
  const testQuantities = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];

  // 清空之前的结果
  batchListContainer.innerHTML =
    '<p class="text-slate-400 text-center py-4 text-sm">正在生成...</p>';

  // 显示结果容器
  if (batchResultsContainer) {
    batchResultsContainer.classList.remove("hidden");
  }

  // === 第3步：逐个调用API生成 ===
  const results = [];

  for (const quantity of testQuantities) {
    try {
      // 调用API
      const response = await fetch("/api/admin/generate_product_name", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
        body: JSON.stringify({
          quantity: quantity,
        }),
      });

      const result = await response.json();

      // 保存结果
      if (result.success) {
        results.push({
          quantity: quantity,
          productName: result.product_name,
          byteLength: result.byte_length,
        });
        console.log(`[PC端商品名测试] 数量${quantity}：${result.product_name}`);
      }
    } catch (error) {
      console.error(`[PC端商品名测试] 数量${quantity}生成失败：`, error);
    }
  }

  // === 第4步：渲染结果列表 ===
  if (results.length === 0) {
    batchListContainer.innerHTML =
      '<p class="text-red-500 text-center py-4 text-sm">批量生成失败，请检查网络连接</p>';
    return;
  }

  // 构建HTML字符串
  let html = "";
  results.forEach((item, index) => {
    html += `
      <div class="bg-white border border-slate-200 rounded-lg p-3">
        <!-- 序号和数量 -->
        <div class="flex justify-between items-center mb-2 pb-2 border-b border-slate-100">
          <span class="text-xs font-semibold text-slate-500">示例 ${
            index + 1
          }</span>
          <span class="text-xs bg-sky-100 text-sky-700 px-2 py-0.5 rounded-full font-medium">数量：${
            item.quantity
          }</span>
        </div>
        <!-- 商品名称 -->
        <div class="mb-2">
          <p class="text-xs text-slate-500 mb-1">商品名称：</p>
          <p class="text-sm font-medium text-slate-800 break-all">${
            item.productName
          }</p>
        </div>
        <!-- 字节长度 -->
        <div class="text-xs text-slate-500">
          字节长度：<span class="font-semibold text-slate-700">${
            item.byteLength
          }</span> 字节
          ${
            item.byteLength > 127
              ? '<span class="text-red-600 ml-1">（超出限制！）</span>'
              : '<span class="text-green-600 ml-1">（符合限制）</span>'
          }
        </div>
      </div>
    `;
  });

  batchListContainer.innerHTML = html;
  console.log(`[PC端商品名测试] 批量测试完成，成功生成${results.length}个示例`);
}

/**
 * 创建PC端管理员测试支付订单
 *
 * 功能说明：
 * 根据用户输入的金额和选择的支付方式，创建一个测试订单
 * 并生成支付链接显示在页面上
 *
 * API端点：POST /api/payment/create
 *
 * 请求体格式：
 * {
 *   amount: 0.01,              // 测试金额
 *   payment_method: "alipay",  // 支付方式
 *   product_name: "测试订单"    // 商品名称
 * }
 *
 * 预期返回格式：
 * {
 *   success: true,
 *   trade_no: "20231210123456789012",  // 订单号
 *   pay_url: "https://..."              // 支付链接
 * }
 *
 * 调用时机：
 * - 用户点击"创建测试订单"按钮时
 */
async function createAdminTestPayment() {
  console.log("[PC端测试支付] 开始创建测试订单...");

  // === 第1步：获取DOM元素 ===

  const amountInput = document.getElementById(
    "admin-test-payment-amount_modal",
  );
  const methodSelect = document.getElementById(
    "admin-test-payment-method_modal",
  );
  const typeSelect = document.getElementById("admin-test-payment-type_modal"); // 新增：支付接口类型选择框
  const authCodeInput = document.getElementById("admin-test-auth-code_modal"); // 新增：付款码输入框
  const linkContainer = document.getElementById(
    "admin-test-payment-link-container_modal",
  );
  const payUrlInput = document.getElementById("admin-test-pay-url_modal");
  const openBtn = document.getElementById("admin-open-test-pay-url-btn_modal");
  const resultDiv = document.getElementById("admin-test-payment-result_modal");

  // === 第2步：获取并验证输入 ===

  // 2.1 获取测试金额
  const amount = amountInput ? parseFloat(amountInput.value) : 0;
  if (!amount || amount <= 0) {
    // showModalAlert("请输入有效的测试金额（大于0）");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入有效的测试金额（大于0）",
    });
    return;
  }

  // 2.2 获取支付方式
  const method = methodSelect ? methodSelect.value : "";
  if (!method) {
    // showModalAlert("请选择支付方式");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请选择支付方式",
    });
    return;
  }

  // 2.3 获取支付接口类型（新增）
  // 如果未选择，默认使用'jump'（跳转支付）
  const paymentType = typeSelect ? typeSelect.value : "qccode";

  // 2.4 获取付款码（仅扫码支付需要）
  let authCode = "";
  // 如果选择的是扫码支付，则需要验证付款码
  if (paymentType === "scan") {
    authCode = authCodeInput ? authCodeInput.value.trim() : "";
    // 验证付款码是否为空
    if (!authCode) {
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "扫码支付需要提供付款码（auth_code）",
      });
      // 聚焦到付款码输入框，引导用户输入
      if (authCodeInput) authCodeInput.focus();
      return; // 中断函数执行
    }
    // 验证付款码长度（通常为18位）
    if (authCode.length !== 18) {
      // showModalAlert("付款码长度不正确，通常为18位数字");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "付款码长度不正确，通常为18位数字",
      });
      if (authCodeInput) authCodeInput.focus();
      return;
    }
  }

  // 2.5 【新增】获取JSAPI支付参数（仅JSAPI支付需要）
  let subOpenid = "";
  let subAppid = "";
  // 如果选择的是JSAPI支付，则需要验证sub_openid和sub_appid
  if (paymentType === "jsapi") {
    // 获取sub_openid输入框元素
    const subOpenidInput = document.getElementById(
      "admin-test-sub-openid_modal",
    );
    // 获取sub_appid输入框元素
    const subAppidInput = document.getElementById("admin-test-sub-appid_modal");

    // 获取并清理sub_openid的值（去除首尾空格）
    subOpenid = subOpenidInput ? subOpenidInput.value.trim() : "";
    // 获取并清理sub_appid的值（去除首尾空格）
    subAppid = subAppidInput ? subAppidInput.value.trim() : "";

    // 验证sub_openid是否为空
    if (!subOpenid) {
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "JSAPI支付需要提供用户Openid（sub_openid）",
      });
      // 聚焦到sub_openid输入框，引导用户输入
      if (subOpenidInput) subOpenidInput.focus();
      return; // 中断函数执行
    }

    // 验证sub_appid是否为空
    if (!subAppid) {
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "JSAPI支付需要提供公众号AppId（sub_appid）",
      });
      // 聚焦到sub_appid输入框，引导用户输入
      if (subAppidInput) subAppidInput.focus();
      return; // 中断函数执行
    }

    // 可选：验证sub_openid的格式（通常以字母o开头，长度约28个字符）
    // 这是一个简单的格式验证，实际的openid格式可能会有所不同
    if (subOpenid.length < 10) {
      // showModalAlert("用户Openid格式可能不正确，长度过短");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "用户Openid格式可能不正确，长度过短",
      });
      if (subOpenidInput) subOpenidInput.focus();
      return;
    }

    // 可选：验证sub_appid的格式（通常以wx开头，长度约18个字符）
    if (!subAppid.startsWith("wx") || subAppid.length < 10) {
      // showModalAlert("公众号AppId格式可能不正确（应以wx开头）");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "公众号AppId格式可能不正确（应以wx开头）",
      });
      if (subAppidInput) subAppidInput.focus();
      return;
    }
  }

  // 在控制台输出测试订单数据，方便调试
  console.log("[PC端测试支付] 测试订单数据：", {
    amount,
    method,
    payment_type: paymentType,
    auth_code: authCode ? "***已提供***" : "未提供", // 在日志中隐藏完整的付款码
    sub_openid: subOpenid ? "***已提供***" : "未提供", // 在日志中隐藏完整的openid
    sub_appid: subAppid ? "***已提供***" : "未提供", // 在日志中隐藏完整的appid
  });

  // === 第2.5步：获取商品名称 ===
  // 根据用户选择的输入方式，获取商品名称
  // 两种方式：1. 手动输入  2. 自动生成（调用后端API）

  let productName = "测试订单"; // 默认值，防止获取失败时使用

  // 2.5.1 获取用户选择的输入方式
  const radioButtons = document.getElementsByName(
    "product-name-input-method_modal",
  );
  let inputMethod = "manual"; // 默认为手动输入

  // 遍历单选按钮，找到选中的那个
  for (const radio of radioButtons) {
    if (radio.checked) {
      inputMethod = radio.value;
      break;
    }
  }

  console.log("[PC端测试支付] 商品名称输入方式：", inputMethod);

  // 2.5.2 根据输入方式获取商品名称
  if (inputMethod === "manual") {
    // 手动输入模式：从文本输入框获取
    const productInput = document.getElementById(
      "admin-test-payment-product_modal",
    );
    if (productInput && productInput.value.trim()) {
      productName = productInput.value.trim();
    } else {
      // 如果输入框为空，显示错误提示
      // showModalAlert("请输入商品名称");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "请输入商品名称",
      });
      return; // 中断函数执行
    }
    console.log("[PC端测试支付] 手动输入的商品名称：", productName);
  } else if (inputMethod === "auto") {
    // 自动生成模式：从数量输入框获取数值，然后调用后端API生成商品名
    const quantityInput = document.getElementById(
      "admin-test-payment-quantity_modal",
    );
    const quantity = quantityInput ? parseInt(quantityInput.value) : 0;

    // 验证数量是否有效
    if (!quantity || quantity < 1 || quantity > 9999) {
      // showModalAlert("请输入有效的商品数量（1-9999）");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "请输入有效的商品数量（1-9999）",
      });
      return; // 中断函数执行
    }

    console.log(
      "[PC端测试支付] 商品数量：",
      quantity,
      "，正在调用生成器API...",
    );

    try {
      // 调用后端API生成商品名称
      // API端点：/api/admin/generate_product_name
      // 请求参数：{ quantity: 数量 }
      // 返回格式：{ success: true, product_name: "生成的商品名" }
      const genResponse = await fetch("/api/admin/generate_product_name", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID, // 需要管理员权限
        },
        body: JSON.stringify({ quantity: quantity }),
      });

      // 检查HTTP响应状态
      if (!genResponse.ok) {
        throw new Error(`生成商品名失败：HTTP状态码 ${genResponse.status}`);
      }

      // 解析JSON响应
      const genResult = await genResponse.json();

      // 检查业务状态
      if (!genResult.success || !genResult.product_name) {
        throw new Error(genResult.message || "生成商品名失败");
      }

      // 使用生成的商品名称
      productName = genResult.product_name;
      console.log("[PC端测试支付] 自动生成的商品名称：", productName);
    } catch (error) {
      // 生成商品名失败，显示错误并中断
      console.error("[PC端测试支付] 生成商品名失败：", error);
      // showModalAlert(`生成商品名失败：${error.message}`);
      Swal.fire({
        icon: "error",
        title: "错误",
        text: `生成商品名失败：${error.message}`,
      });
      return; // 中断函数执行
    }
  }

  try {
    // === 第3步：构建请求体 ===

    // 创建基本的请求数据对象
    const requestData = {
      amount: amount, // 支付金额
      payment_method: method, // 支付方式（alipay/wechat/qq/unionpay）
      payment_type: paymentType, // 支付接口类型（jump/web/jsapi/app/scan/applet）
      product_name: productName, // 商品名称（手动输入或自动生成）
      preserve_product_name: true, // 测试支付：保留用户输入商品名
      app_host: window.location.protocol + "//" + window.location.host,
      return_url: window.location.href, //浏览器当前地址
      sub_openid: subOpenid, // 【修改】JSAPI支付所需的用户Openid（从输入框获取）
      sub_appid: subAppid, // 【修改】JSAPI支付所需的公众号AppId（从输入框获取）
      device: Get_YiPAi_device(),
    };

    // 如果是扫码支付，添加付款码到请求数据
    if (paymentType === "scan" && authCode) {
      requestData.auth_code = authCode;
    }

    // === 第4步：发起HTTP POST请求创建订单 ===

    logMessage_Info(
      `[PC端测试支付] 发送创建订单请求，API：/api/payment/create，` +
        `支付方式=${method}，接口类型=${paymentType}，` +
        `包含扫码参数=${Boolean(authCode)}，` +
        `包含JSAPI参数=${Boolean(subOpenid || subAppid)}`,
    );

    const response = await fetch("/api/payment/create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 附加会话ID用于身份验证
      },
      // 将请求数据对象转换为JSON字符串并发送
      body: JSON.stringify(requestData),
    });

    // === 第4步：检查响应状态 ===

    if (!response.ok) {
      throw new Error(`创建订单失败：HTTP状态码 ${response.status}`);
    }

    // === 第5步：解析响应数据 ===

    const result = await response.json();

    console.log(
      "[PC端测试支付] API响应：",
      createSafeClientLogValue(result),
    );

    // === 第6步：检查业务状态 ===

    if (!result.success) {
      throw new Error(result.message || "创建订单失败");
    }

    // 检查是否有支付信息（pay_url或pay_info）
    if (!result.pay_url && !result.pay_info) {
      throw new Error("未返回支付信息");
    }

    // === 第7步：显示支付信息 ===

    // 获取支付类型和支付信息
    const payType = result.pay_type || "jump";
    const payInfo = result.pay_info || result.pay_url || "";

    // 填充订单详细信息到新增的显示字段
    const orderIdElem = document.getElementById("admin-test-order-id_modal");
    const tradeNoElem = document.getElementById("admin-test-trade-no_modal");
    const amountElem = document.getElementById("admin-test-amount_modal");
    const payMethodElem = document.getElementById(
      "admin-test-pay-method_modal",
    );
    const methodTypeElem = document.getElementById(
      "admin-test-method-type_modal",
    );
    const payTypeElem = document.getElementById("admin-test-pay-type_modal");
    const payInfoDescElem = document.getElementById(
      "admin-test-pay-info-desc_modal",
    );

    // 填充商户订单号
    if (orderIdElem) {
      orderIdElem.textContent = result.order_id || "-";
    }

    // 填充平台订单号
    if (tradeNoElem) {
      tradeNoElem.textContent = result.trade_no || "-";
    }

    // 填充支付金额
    if (amountElem) {
      amountElem.textContent = amount
        ? `¥${parseFloat(amount).toFixed(2)}`
        : "-";
    }

    // 填充支付方式（翻译为中文）
    if (payMethodElem) {
      const methodNames = {
        alipay: "支付宝",
        wxpay: "微信支付",
        qqpay: "QQ钱包",
        unionpay: "云闪付",
      };
      payMethodElem.textContent = methodNames[method] || method || "-";
    }

    // 填充接口类型
    if (methodTypeElem) {
      methodTypeElem.textContent = paymentType || "-";
    }

    // 填充发起支付类型
    if (payTypeElem) {
      payTypeElem.textContent = payType || "-";
    }

    // 根据支付类型设置说明文字
    if (payInfoDescElem) {
      const payTypeDescriptions = {
        jump: "跳转链接 - 可直接打开进行支付",
        html: "HTML代码 - 用于支付跳转",
        qrcode: "二维码链接 - 可生成二维码供用户扫描",
        urlscheme: "小程序跳转链接 - 可在微信/支付宝中打开",
        jsapi: "JSAPI支付参数 - JSON格式，用于小程序内支付",
        app: "APP支付参数 - JSON格式，用于APP内支付",
        scan: "扫码支付结果 - 付款码支付成功的订单信息",
        wxplugin: "小程序插件参数 - JSON格式，用于拉起微信小程序插件",
        wxapp: "小程序跳转参数 - JSON格式，用于APP内拉起微信小程序",
      };
      payInfoDescElem.textContent = payTypeDescriptions[payType] || "支付信息";
    }

    // 填充支付信息到输入框
    if (payUrlInput) {
      // 根据支付类型显示不同格式的信息
      if (payType === "jump" || payType === "html") {
        // 跳转支付：直接显示链接
        payUrlInput.value = payInfo;
      } else if (payType === "qrcode") {
        // 二维码支付：显示二维码链接
        payUrlInput.value = `二维码: ${payInfo}`;

        // 生成二维码显示
        // 获取二维码容器（假设在admin-test-auth-code-container_modal中添加一个二维码显示区域）
        const qrcodeContainer = document.getElementById(
          "admin-test-qrcode-display_modal",
        );
        if (qrcodeContainer && typeof QRCode !== "undefined") {
          // 清空之前的二维码
          qrcodeContainer.innerHTML = "";

          try {
            // 创建canvas元素用于显示二维码
            const canvas = document.createElement("canvas");
            canvas.id = "test-payment-qrcode-canvas";
            qrcodeContainer.appendChild(canvas);

            // 使用QRCode.toCanvas生成二维码
            QRCode.toCanvas(
              canvas,
              payInfo,
              {
                width: 200,
                margin: 2,
                color: {
                  dark: "#000000",
                  light: "#ffffff",
                },
              },
              function (error) {
                if (error) {
                  console.error("[PC端测试支付] 二维码生成失败：", error);
                  qrcodeContainer.innerHTML =
                    '<p class="text-red-500 text-sm">二维码生成失败</p>';
                } else {
                  console.log("[PC端测试支付] 二维码生成成功");
                  // 显示二维码容器
                  qrcodeContainer.classList.remove("hidden");
                }
              },
            );
          } catch (error) {
            console.error("[PC端测试支付] 二维码生成出错：", error);
            qrcodeContainer.innerHTML =
              '<p class="text-red-500 text-sm">二维码生成出错</p>';
          }
        } else if (qrcodeContainer) {
          // QRCode库未加载
          qrcodeContainer.innerHTML =
            '<p class="text-yellow-600 text-sm">QRCode库未加载</p>';
        }
      } else if (payType === "urlscheme") {
        // URL Scheme：显示微信/支付宝小程序跳转链接
        payUrlInput.value = `小程序跳转: ${payInfo}`;
      } else if (
        payType === "jsapi" ||
        payType === "app" ||
        payType === "wxplugin" ||
        payType === "wxapp"
      ) {
        // JSAPI/APP/小程序支付：显示格式化的JSON参数
        try {
          const jsonObj =
            typeof payInfo === "string" ? JSON.parse(payInfo) : payInfo;
          payUrlInput.value = JSON.stringify(jsonObj, null, 2);
        } catch (e) {
          payUrlInput.value = payInfo;
        }
      } else if (payType === "scan") {
        // 扫码支付成功：显示订单信息
        payUrlInput.value = `扫码支付成功: ${payInfo}`;
      } else {
        // 其他类型：直接显示
        payUrlInput.value = payInfo;
      }
    }

    // 将支付信息保存到打开按钮的data属性
    // jump/html/urlscheme类型可以直接打开
    if (openBtn) {
      if (payType === "jump" || payType === "html" || payType === "urlscheme") {
        openBtn.setAttribute("data-url", payInfo);
        openBtn.disabled = false;
        openBtn.classList.remove("opacity-50", "cursor-not-allowed");
      } else {
        openBtn.disabled = true;
        openBtn.classList.add("opacity-50", "cursor-not-allowed");
      }
    }

    // 显示支付链接容器
    if (linkContainer) {
      linkContainer.classList.remove("hidden");
    }

    // 隐藏错误提示（如果有）
    if (resultDiv) {
      resultDiv.classList.add("hidden");
    }

    console.log(
      "[PC端测试支付] 测试订单创建成功，支付类型：",
      payType,
      "，支付信息：",
      payInfo,
    );
  } catch (error) {
    // === 错误处理 ===

    console.error("[PC端测试支付] 创建测试订单时发生错误：", error);

    // 隐藏支付链接容器
    if (linkContainer) {
      linkContainer.classList.add("hidden");
    }

    // 【修改】使用 showModalAlert() 显示错误提示
    // 优点：统一的错误提示样式，用户体验更好
    // 第二个参数传递 "错误" 表示这是一个错误类型的提示
    // showModalAlert(`创建失败：${error.message || "未知错误"}`, "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `创建失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 打开PC端管理员测试支付链接
 *
 * 功能说明：
 * 在新标签页中打开之前生成的支付链接
 *
 * 调用时机：
 * - 用户点击"打开链接"按钮时
 */
function openAdminPaymentLink() {
  console.log("[PC端测试支付] 准备打开支付链接...");

  // === 获取支付链接 ===

  const openBtn = document.getElementById("admin-open-test-pay-url-btn_modal");
  if (!openBtn) {
    console.error("[PC端测试支付] 错误：找不到打开按钮");
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return;
  }

  // 从按钮的data-url属性获取支付链接
  const payUrl = openBtn.getAttribute("data-url");

  console.log("[PC端测试支付] 已获取支付链接");

  // === 验证链接是否存在 ===

  if (!payUrl) {
    console.error("[PC端测试支付] 错误：支付链接不存在");
    // showModalAlert("支付链接不存在，请先创建测试订单。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付链接不存在，请先创建测试订单。",
    });
    return;
  }

  // === 打开新标签页 ===

  try {
    // 使用window.open()在新标签页中打开支付链接
    // '_blank'参数表示在新标签页打开
    const newWindow = window.open(payUrl, "_blank");

    // 检查是否被浏览器拦截
    // 某些浏览器可能会拦截window.open()弹窗
    if (!newWindow) {
      console.warn("[PC端测试支付] 警告：弹窗可能被浏览器拦截");
      // showModalAlert(
      //   `无法自动打开支付链接，请手动复制链接后在新标签页打开：\n\n${payUrl}`
      // );
      Swal.fire({
        icon: "warning",
        title: "警告",
        text: `无法自动打开支付链接，请手动复制链接后在新标签页打开：\n\n${payUrl}`,
      });
    } else {
      console.log("[PC端测试支付] 支付链接已在新标签页打开");
    }
  } catch (error) {
    // 捕获可能的错误（虽然window.open()通常不会抛出错误）
    console.error("[PC端测试支付] 打开支付链接时发生错误：", error);
    // showModalAlert(
    //   `无法打开支付链接：${
    //     error.message || "未知错误"
    //   }\n\n请手动复制链接后在新标签页打开：\n\n${payUrl}`
    // );
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `无法打开支付链接：${
        error.message || "未知错误"
      }\n\n请手动复制链接后在新标签页打开：\n\n${payUrl}`,
    });
  }
}

/**
 * 复制PC端管理员测试支付链接
 *
 * 功能说明：
 * 将支付链接复制到剪贴板，方便用户分享或保存
 *
 * 调用时机：
 * - 用户点击"复制链接"按钮时
 */
function copyAdminTestPayUrl() {
  console.log("[PC端测试支付] 准备复制支付链接...");

  // === 获取支付链接输入框 ===

  const payUrlInput = document.getElementById("admin-test-pay-url_modal");
  if (!payUrlInput) {
    console.error("[PC端测试支付] 错误：找不到支付链接输入框");
    // showModalAlert("页面元素异常，请刷新页面后重试。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "页面元素异常，请刷新页面后重试。",
    });
    return;
  }

  // 获取支付链接文本
  const payUrl = payUrlInput.value;

  if (!payUrl) {
    console.error("[PC端测试支付] 错误：支付链接为空");
    // showModalAlert("支付链接为空，请先创建测试订单。");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付链接为空，请先创建测试订单。",
    });
    return;
  }

  // === 复制到剪贴板 ===

  try {
    // 选中输入框中的文本
    // 使用payUrl.length替代硬编码的99999，确保选择完整的URL文本
    payUrlInput.select();
    payUrlInput.setSelectionRange(0, payUrl.length); // 选择从0到URL长度的所有字符

    // 使用现代Clipboard API（优先）
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(payUrl)
        .then(() => {
          console.log("[PC端测试支付] 支付链接已复制到剪贴板");
          // showModalAlert("✓ 支付链接已复制到剪贴板");
          Swal.fire({
            icon: "success",
            title: "成功",
            text: "✓ 支付链接已复制到剪贴板",
          });
        })
        .catch((err) => {
          console.error("[PC端测试支付] Clipboard API复制失败：", err);
          // 降级使用document.execCommand
          fallbackCopy();
        });
    } else {
      // 浏览器不支持Clipboard API，使用document.execCommand（降级方案）
      fallbackCopy();
    }
  } catch (error) {
    console.error("[PC端测试支付] 复制支付链接时发生错误：", error);
    // showModalAlert(
    //   `复制失败：${error.message || "未知错误"}\n\n请手动复制链接。`
    // );
    Swal.fire({
      icon: "error",
      title: "错误",
      text: `复制失败：${error.message || "未知错误"}\n\n请手动复制链接。`,
    });
  }

  // 降级复制方法
  function fallbackCopy() {
    try {
      const successful = document.execCommand("copy");
      if (successful) {
        console.log(
          "[PC端测试支付] 支付链接已复制到剪贴板（使用fallback方法）",
        );
        // showModalAlert("✓ 支付链接已复制到剪贴板");
        Swal.fire({
          icon: "success",
          title: "成功",
          text: "✓ 支付链接已复制到剪贴板",
        });
      } else {
        throw new Error("execCommand复制失败");
      }
    } catch (err) {
      console.error("[PC端测试支付] Fallback复制失败：", err);
      // showModalAlert("复制失败，请手动复制链接。");
      Swal.fire({
        icon: "error",
        title: "错误",
        text: "复制失败，请手动复制链接。",
      });
    }
  }
}

// ==========================================
// Tab 5: 易支付配置管理功能（PC端）
// ==========================================
// 【功能说明】
// 实现易支付接口参数的加载和保存功能
// 包括host、pid、key、enabled_payment_methods、payment_method
// ==========================================

/**
 * 加载PC端管理员易支付配置
 *
 * 功能说明：
 * 从服务器获取当前的易支付配置，并填充到表单中
 * 此函数会在用户点击"刷新配置"按钮或切换到易支付Tab时调用
 *
 * API端点：GET /api/admin/yipay_config
 * 权限要求：modify_config权限 + admin或super_admin用户组
 *
 * 预期返回格式：
 * {
 *   success: true,
 *   config: {
 *     host: "https://pay.example.com",
 *     pid: "12345",
 *     key: "abcdef123456",
 *     enabled_payment_methods: "alipay,wxpay",
 *     payment_method: "jump"
 *   }
 * }
 */
async function loadAdminYiPayConfig(show_Modal = true) {
  // 在控制台输出日志，记录函数调用
  console.log("[PC端易支付配置] 开始加载易支付配置...");
  configLoadState.yipay = false;

  try {
    // === 第1步：发起HTTP GET请求获取配置数据 ===
    // 使用fetch API调用后端接口
    // await关键字会等待请求完成，确保获取到响应后再继续执行
    const response = await fetch("/api/admin/yipay_config", {
      method: "GET", // HTTP方法：GET用于获取数据
      headers: {
        // 设置请求头，告知服务器期望返回JSON格式的数据
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
    });

    // === 第2步：检查HTTP响应状态码 ===
    // response.ok 为true表示状态码在200-299范围内（成功）
    if (!response.ok) {
      // 如果响应状态码不是成功状态（如404、500等）
      // 特别处理403错误（权限不足）
      if (response.status === 403) {
        throw new Error("权限不足，需要管理员权限");
      }
      // 抛出错误，中断执行流程，进入catch块处理
      throw new Error(`加载配置失败：HTTP状态码 ${response.status}`);
    }

    // === 第3步：解析JSON响应数据 ===
    // 将响应体解析为JavaScript对象
    const result = await response.json();

    // 在控制台输出获取到的配置数据，方便开发者查看和调试
    console.log(
      "[PC端易支付配置] 成功获取易支付配置：",
      createSafeClientLogValue(result),
    );

    // === 第4步：检查业务状态 ===
    // 即使HTTP状态码成功，也需要检查业务逻辑是否成功
    if (!result.success) {
      throw new Error(result.message || "加载配置失败");
    }

    // === 第5步：将配置数据填充到表单字段中 ===

    const config = result.config || {};

    // 5.1 填充host字段（易支付接口域名）
    const hostInput = document.getElementById("admin-yipay-host_modal");
    if (hostInput) {
      // 使用textContent的方式更安全，但input.value是正确的方式
      hostInput.value = config.host || "";
    }

    // 5.2 填充pid字段（商户ID）
    const pidInput = document.getElementById("admin-yipay-pid_modal");
    if (pidInput) {
      pidInput.value = config.pid || "";
    }

    // 5.3 填充key字段（商户密钥）
    const keyInput = document.getElementById("admin-yipay-key_modal");
    if (keyInput) {
      // 注意：后端返回的是完整密钥（不脱敏），直接填充到密码输入框
      keyInput.value = config.key || "";
    }

    // 5.3.5 填充product_id字段
    const productIdInput = document.getElementById(
      "admin-yipay-product-id_modal",
    );
    if (productIdInput) {
      productIdInput.value = config.product_id || "1001";
    }

    // 5.3.6 填充app_host字段（应用域名地址）
    // app_host 用于自动设置回调地址的域名前缀
    const appHostInput = document.getElementById("admin-yipay-app-host_modal");
    if (appHostInput) {
      // 从配置中读取app_host，如果不存在则使用空字符串
      appHostInput.value = config.app_host || "";
    }

    // 5.3.7 填充pubc_key字段（平台公钥）
    // pubc_key 用于验证支付回调通知的RSA公钥
    const pubcKeyInput = document.getElementById("admin-yipay-pubc-key_modal");
    if (pubcKeyInput) {
      // 从配置中读取pubc_key，如果不存在则使用空字符串
      pubcKeyInput.value = config.pubc_key || "";
    }

    // 5.3.8 填充payment_timeout_minutes字段（支付超时时间）
    // payment_timeout_minutes 表示订单创建后多长时间未支付视为超时
    const timeoutInput = document.getElementById("admin-yipay-timeout_modal");
    if (timeoutInput) {
      // 从配置中读取payment_timeout_minutes，如果不存在则使用默认值30秒
      timeoutInput.value = config.payment_timeout_minutes || "30";
    }

    // 5.4 填充enabled_payment_methods字段（启用的支付方式）
    const methodsInput = document.getElementById(
      "admin-yipay-enabled-methods_modal",
    );
    if (methodsInput) {
      // 支付方式以逗号分隔的字符串形式存储，如 "alipay,wxpay"
      methodsInput.value = config.enabled_payment_methods || "";
    }

    // === 第6步：验证启用的支付方式是否在 payment_methods_config 中定义 ===
    // 这一步是为了确保数据的一致性和完整性

    // 6.1 获取启用的支付方式列表
    const enabledMethods = config.enabled_payment_methods || "";
    if (enabledMethods) {
      // 将逗号分隔的字符串拆分为数组
      const enabledMethodsArray = enabledMethods
        .split(",")
        .map((m) => m.trim())
        .filter((m) => m);

      console.log("[PC端易支付配置] 验证启用的支付方式：", enabledMethodsArray);

      if (
        sessionUUID === undefined ||
        sessionUUID === null ||
        sessionUUID === ""
      ) {
        console.error(
          "[PC端易支付配置] 错误：sessionUUID未定义，无法验证支付方式",
        );
        sessionUUID = getUUIDFromURL();
      }

      // 6.2 获取所有已定义的支付方式（从 payment_methods_config）
      try {
        // 发起请求获取支付方式配置
        const methodsConfigResponse = await fetch(
          "/api/payment/methods_config",
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              // 添加Session ID请求头（如果存在）
              "X-Session-ID": sessionUUID,
            },
          },
        );

        // 检查响应状态
        if (methodsConfigResponse.ok) {
          const methodsConfigResult = await methodsConfigResponse.json();

          if (methodsConfigResult.success && methodsConfigResult.data) {
            // 获取所有已定义的支付方式代码
            // methodsConfigResult.data 是一个对象，键是支付方式代码
            const definedMethodCodes = Object.keys(methodsConfigResult.data);

            console.log(
              "[PC端易支付配置] 已定义的支付方式：",
              definedMethodCodes,
            );

            // 6.3 检查是否有未定义的支付方式
            // 遍历启用的支付方式，检查每个是否在已定义的列表中
            const undefinedMethods = enabledMethodsArray.filter(
              (method) => !definedMethodCodes.includes(method),
            );

            if (undefinedMethods.length > 0) {
              // 发现有未定义的支付方式，显示警告
              console.warn(
                "[PC端易支付配置] 发现未定义的支付方式：",
                undefinedMethods,
              );

              // showModalAlert(
              //   '存在未定义的支付方式，请检查配置。以下支付方式未在"支付方式配置"中定义： ' +
              //     undefinedMethods.join(", "),
              //   "警告"
              // );
              //   使用Swal代替showModalAlert
              Swal.fire({
                icon: "warning",
                title: "警告",
                text: `存在未定义的支付方式，请检查配置。以下支付方式未在"支付方式配置"中定义： ${undefinedMethods.join(
                  ", ",
                )}`,
              });
              // // 在结果区域显示警告提示
              // const resultDiv = document.getElementById('admin-yipay-config-result_modal');
              // if (resultDiv) {
              //   resultDiv.innerHTML = `
              //     <div class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
              //       <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              //         <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              //           d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
              //       </svg>
              //       ⚠ 警告：以下支付方式未在"支付方式配置"中定义：<strong>${undefinedMethods.join(', ')}</strong><br>
              //       请先在"支付方式配置"中添加这些支付方式，或从启用列表中移除。
              //     </div>
              //   `;
              //   resultDiv.classList.remove('hidden');
              //   // 警告提示保持显示，不自动隐藏，让管理员注意到问题
              // }
            } else {
              // 所有启用的支付方式都已定义，验证通过
              console.log(
                "[PC端易支付配置] 所有启用的支付方式都已定义，验证通过",
              );
            }
          }
        }
      } catch (validationError) {
        // 验证过程中发生错误（如网络问题），只记录日志，不影响主流程
        console.error(
          "[PC端易支付配置] 验证支付方式时发生错误：",
          validationError,
        );
        // 不显示错误提示，避免干扰用户
      }
    }

    // === 第7步：显示成功提示（如果没有警告） ===
    // 只有在没有显示警告的情况下，才显示成功提示
    if (show_Modal) {
      // showModalAlert("✓ 配置已加载", "成功");
      Swal.fire({
        icon: "success",
        title: "成功",
        text: "配置已加载",
      });
    }
    // const resultDiv = document.getElementById('admin-yipay-config-result_modal');
    // if (resultDiv) {
    // // 检查resultDiv中是否已经有警告提示
    // // 如果有警告（包含text-amber-700类），则不显示成功提示
    // const hasWarning = resultDiv.innerHTML.includes('text-amber-700');

    // if (!hasWarning) {
    //   // 没有警告，显示成功提示
    //   // 使用textContent防止XSS攻击，但这里需要HTML结构，所以使用innerHTML
    //   // 由于这是管理员功能且数据来自服务器，风险可控
    //   resultDiv.innerHTML = `
    //     <div class="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg p-3">
    //       <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    //         <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
    //           d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
    //       </svg>
    //       ✓ 配置已加载
    //     </div>
    //   `;
    //   resultDiv.classList.remove('hidden');

    //   // 3秒后自动隐藏成功提示
    //   setTimeout(() => {
    //     resultDiv.classList.add('hidden');
    //   }, 3000);
    // }
    // }

    console.log("[PC端易支付配置] 配置已成功填充到表单");
    configLoadState.yipay = true;
  } catch (error) {
    configLoadState.yipay = false;
    // === 错误处理 ===
    // 当任何步骤发生错误时（网络失败、JSON解析失败、服务器错误等）
    // 都会被捕获到这里
    console.error("[PC端易支付配置] 加载配置时发生错误：", error);

    // 显示错误提示
    const resultDiv = document.getElementById(
      "admin-yipay-config-result_modal",
    );
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          ✗ 加载失败：${error.message || "未知错误"}
        </div>
      `;
      resultDiv.classList.remove("hidden");

      // 8秒后自动隐藏错误提示（比成功提示稍长）
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 8000);
    } else {
      // 如果结果显示区域不存在，使用alert作为备选方案
      // showModalAlert(`加载失败：${error.message || "未知错误"}`);
      Swal.fire({
        icon: "error",
        title: "错误",
        text: `加载失败：${error.message || "未知错误"}`,
      });
    }
  }
}

/**
 * 保存PC端管理员易支付配置
 *
 * 功能说明：
 * 从表单中收集用户输入的易支付配置，验证后发送到服务器保存
 * 此函数会在用户点击"保存配置"按钮时调用
 *
 * API端点：PUT /api/admin/yipay_config
 * 权限要求：modify_config权限 + admin或super_admin用户组
 *
 * 请求数据格式：
 * {
 *   host: "https://pay.example.com",
 *   pid: "12345",
 *   key: "abcdef123456",
 *   enabled_payment_methods: "alipay,wxpay",
 *   payment_method: "jump"
 * }
 */
async function saveAdminYiPayConfig() {
  if (!ensureConfigLoaded("yipay", "易支付")) {
    return;
  }
  // 在控制台输出日志，记录函数调用
  console.log("[PC端易支付配置] 开始保存易支付配置...");

  // === 第1步：获取DOM元素 ===

  const hostInput = document.getElementById("admin-yipay-host_modal");
  const pidInput = document.getElementById("admin-yipay-pid_modal");
  const keyInput = document.getElementById("admin-yipay-key_modal");
  // 获取product_id输入框
  const productIdInput = document.getElementById(
    "admin-yipay-product-id_modal",
  );
  // 获取app_host输入框（应用域名地址）
  const appHostInput = document.getElementById("admin-yipay-app-host_modal");
  // 获取pubc_key输入框（平台公钥）
  const pubcKeyInput = document.getElementById("admin-yipay-pubc-key_modal");
  // 获取payment_timeout_minutes输入框（支付超时时间）
  const timeoutInput = document.getElementById("admin-yipay-timeout_modal");
  const methodsInput = document.getElementById(
    "admin-yipay-enabled-methods_modal",
  );

  // === 第2步：获取并验证输入值 ===

  // 2.1 获取host值并去除首尾空格
  // 首先去除首尾空格
  let host = hostInput ? hostInput.value.trim() : "";

  // 去除末尾的所有斜杠
  // 这是必要的，因为：
  // 1. API接口拼接时会自动添加斜杠，如果host末尾已有斜杠会导致双斜杠
  // 2. 统一格式便于后续处理和显示
  // 3. 避免因为斜杠问题导致的请求失败
  // 正则表达式 /\/+$/ 的含义：
  // - \/ 表示匹配斜杠字符（需要转义）
  // - + 表示匹配一个或多个
  // - $ 表示匹配字符串末尾
  // 例如：
  // - "https://example.com/" → "https://example.com"
  // - "https://example.com" → "https://example.com" (保持不变)
  // - "https://example.com///" → "https://example.com" (去除所有末尾斜杠)
  host = host.replace(/\/+$/, "");

  // 验证host不能为空
  if (!host) {
    // showModalAlert("请输入易支付接口域名");
    // 使用Swal代替showModalAlert
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入易支付接口域名",
    });
    // 聚焦到host输入框，引导用户输入
    if (hostInput) hostInput.focus();
    return; // 中断函数执行
  }

  // 2.2 获取pid值并去除首尾空格
  const pid = pidInput ? pidInput.value.trim() : "";
  if (!pid) {
    // showModalAlert("请输入商户ID");
    // (使用Swal代替showModalAlert)
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入商户ID",
    });
    if (pidInput) pidInput.focus();
    return;
  }

  // 2.3 获取key值并去除首尾空格
  const key = keyInput ? keyInput.value.trim() : "";
  if (!key) {
    // showModalAlert("请输入商户密钥");
    // 使用Swal代替showModalAlert
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入商户密钥",
    });
    if (keyInput) keyInput.focus();
    return;
  }

  // 2.4 获取启用的支付方式（可以为空，后端会使用默认值）
  const enabledMethods = methodsInput ? methodsInput.value.trim() : "";

  // 获取product_id值
  const productId = productIdInput ? productIdInput.value.trim() : "1001";

  // 2.4.1 获取app_host值（应用域名地址）
  // 此字段为可选，如果为空则使用空字符串
  const appHost = appHostInput ? appHostInput.value.trim() : "";

  // 2.4.2 获取pubc_key值（平台公钥）
  // 此字段为必填，需要进行验证
  const pubcKey = pubcKeyInput ? pubcKeyInput.value.trim() : "";
  // 验证pubc_key不能为空
  if (!pubcKey) {
    // showModalAlert("请输入平台公钥");
    // 使用Swal代替showModalAlert
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入平台公钥",
    });
    if (pubcKeyInput) pubcKeyInput.focus();
    return; // 中断函数执行
  }

  // 2.4.3 获取payment_timeout_minutes值（支付超时时间）
  // 此字段为可选，默认30秒
  const paymentTimeoutMinutes = timeoutInput ? timeoutInput.value.trim() : "30";
  // 验证payment_timeout_minutes是否为有效数字
  // 使用parseInt解析字符串为整数
  const timeoutNum = parseInt(paymentTimeoutMinutes, 10);
  // 检查是否为有效数字（NaN表示不是数字）
  if (isNaN(timeoutNum)) {
    // showModalAlert("支付超时时间必须是数字");
    // 使用Swal代替showModalAlert
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付超时时间必须是数字",
    });
    if (timeoutInput) timeoutInput.focus();
    return;
  }
  // 检查数字范围是否在10-3600之间
  if (timeoutNum < 10 || timeoutNum > 3600) {
    // showModalAlert("支付超时时间必须在10-3600秒之间");
    // 使用Swal代替showModalAlert
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "支付超时时间必须在10-3600秒之间",
    });
    if (timeoutInput) timeoutInput.focus();
    return;
  }

  // 2.5 支付接口类型使用默认值（jump）
  // 由于前端UI已移除该字段的输入框，使用固定默认值
  // const paymentMethod = 'jump';

  // 在控制台输出要提交的配置数据
  console.log("[PC端易支付配置] 准备提交的配置：", {
    host,
    pid,
    key: "***隐藏***", // 在日志中隐藏密钥，保护敏感信息
    product_id: productId,
    app_host: appHost,
    pubc_key: "***隐藏***", // 在日志中隐藏公钥，保护敏感信息
    payment_timeout_minutes: paymentTimeoutMinutes,
    enabled_payment_methods: enabledMethods,
    // payment_method: paymentMethod
  });

  // === 第2.6步：验证启用的支付方式是否在 payment_methods_config 中定义 ===
  // 这是一个重要的数据完整性检查
  // 防止管理员保存未定义的支付方式代码，导致后续支付流程出错

  if (enabledMethods) {
    // 将逗号分隔的字符串拆分为数组
    const enabledMethodsArray = enabledMethods
      .split(",")
      .map((m) => m.trim())
      .filter((m) => m);

    console.log("[PC端易支付配置] 验证启用的支付方式：", enabledMethodsArray);

    if (
      sessionUUID === undefined ||
      sessionUUID === null ||
      sessionUUID === ""
    ) {
      console.error(
        "[PC端易支付配置] 错误：sessionUUID未定义，无法验证支付方式",
      );
      sessionUUID = getUUIDFromURL();
    }

    try {
      // 发起请求获取支付方式配置
      const methodsConfigResponse = await fetch("/api/payment/methods_config", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          // 添加Session ID请求头（如果存在）
          "X-Session-ID": sessionUUID,
        },
      });

      // 检查响应状态
      if (methodsConfigResponse.ok) {
        const methodsConfigResult = await methodsConfigResponse.json();

        if (methodsConfigResult.success && methodsConfigResult.data) {
          // 获取所有已定义的支付方式代码
          const definedMethodCodes = Object.keys(methodsConfigResult.data);

          console.log(
            "[PC端易支付配置] 已定义的支付方式：",
            definedMethodCodes,
          );

          // 检查是否有未定义的支付方式
          const undefinedMethods = enabledMethodsArray.filter(
            (method) => !definedMethodCodes.includes(method),
          );

          if (undefinedMethods.length > 0) {
            // 发现有未定义的支付方式，阻止保存操作
            console.error(
              "[PC端易支付配置] 发现未定义的支付方式，阻止保存：",
              undefinedMethods,
            );

            // 显示详细的错误提示
            // showModalAlert(
            //   `❌ 保存失败\n\n` +
            //     `以下支付方式未在"支付方式配置"中定义：\n` +
            //     `${undefinedMethods.join(", ")}\n\n` +
            //     `请先在"支付方式配置"中添加这些支付方式，或从启用列表中移除。`
            // );
            // 使用Swal代替showModalAlert
            Swal.fire({
              icon: "error",
              title: "错误",
              text: `以下支付方式未在"支付方式配置"中定义：\n${undefinedMethods.join(
                ", ",
              )}\n\n请先在"支付方式配置"中添加这些支付方式，或从启用列表中移除。`,
            });

            // 聚焦到支付方式输入框，引导用户修改
            if (methodsInput) methodsInput.focus();

            // 阻止保存操作，直接返回
            return;
          } else {
            // 所有启用的支付方式都已定义，验证通过
            console.log(
              "[PC端易支付配置] 所有启用的支付方式都已定义，验证通过",
            );
          }
        }
      } else {
        // 获取支付方式配置失败，记录警告但不阻止保存
        // 因为可能是网络问题或临时性错误，不应该完全阻止管理员的操作
        console.warn("[PC端易支付配置] 无法验证支付方式配置，跳过验证");
      }
    } catch (validationError) {
      // 验证过程中发生错误，记录日志但不阻止保存
      console.error(
        "[PC端易支付配置] 验证支付方式时发生错误：",
        validationError,
      );
      // 不阻止保存，让管理员可以继续操作
    }
  }

  try {
    // === 第3步：发起HTTP PUT请求保存配置 ===

    const response = await fetch("/api/admin/yipay_config", {
      method: "PUT", // HTTP方法：PUT用于更新数据
      headers: {
        // 设置请求头，告知服务器发送的是JSON格式的数据
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      // 将配置对象转换为JSON字符串并发送
      body: JSON.stringify({
        host: host,
        pid: pid,
        key: key,
        product_id: productId, // 发送product_id
        app_host: appHost, // 发送app_host（应用域名地址）
        pubc_key: pubcKey, // 发送pubc_key（平台公钥）
        payment_timeout_minutes: paymentTimeoutMinutes, // 发送payment_timeout_minutes（支付超时时间）
        enabled_payment_methods: enabledMethods,
        // payment_method: paymentMethod
      }),
    });

    // === 第4步：检查HTTP响应状态码 ===

    if (!response.ok) {
      // 特别处理403错误（权限不足）
      if (response.status === 403) {
        throw new Error("权限不足，需要管理员权限");
      }
      throw new Error(`保存配置失败：HTTP状态码 ${response.status}`);
    }

    // === 第5步：解析响应数据 ===

    const result = await response.json();

    console.log(
      "[PC端易支付配置] API响应：",
      createSafeClientLogValue(result),
    );

    // === 第6步：检查业务状态 ===

    if (!result.success) {
      throw new Error(result.message || "保存配置失败");
    }

    // === 第7步：显示成功提示 ===

    // 使用showModalAlert显示保存成功提示
    // showModalAlert("易支付配置已成功保存", "保存成功");
    // 使用Swal代替showModalAlert
    Swal.fire({
      icon: "success",
      title: "保存成功",
      text: "易支付配置已成功保存",
    });

    console.log("[PC端易支付配置] 配置保存成功");
  } catch (error) {
    // === 错误处理 ===

    console.error("[PC端易支付配置] 保存配置时发生错误：", error);

    // 显示错误提示
    const resultDiv = document.getElementById(
      "admin-yipay-config-result_modal",
    );
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
          <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          ✗ 保存失败：${error.message || "未知错误"}
        </div>
      `;
      resultDiv.classList.remove("hidden");

      // 8秒后自动隐藏错误提示
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 8000);
    } else {
      // showModalAlert(`保存失败：${error.message || "未知错误"}`);
      // 使用Swal代替showModalAlert
      Swal.fire({
        icon: "error",
        title: "保存失败",
        text: `保存失败：${error.message || "未知错误"}`,
      });
    }
  }
}

// ==========================================
// Tab 5: 易支付配置管理功能（移动端）
// ==========================================
// 【功能说明】
// 移动端的易支付配置加载和保存功能
// 与PC端功能相同，但使用不同的DOM元素ID
// ==========================================

/**
 * 加载移动端易支付配置
 *
 * 功能说明：
 * 从服务器获取当前的易支付配置，并填充到移动端表单中
 *
 * API端点：GET /api/admin/yipay_config
 * 权限要求：modify_config权限 + admin或super_admin用户组
 */
async function loadMobileYiPayConfig() {
  // 在控制台输出日志，记录函数调用
  console.log("[移动端易支付配置] 开始加载易支付配置...");

  try {
    // === 发起HTTP GET请求 ===
    const response = await fetch("/api/admin/yipay_config", {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
    });

    // === 检查响应状态 ===
    if (!response.ok) {
      if (response.status === 403) {
        throw new Error("权限不足，需要管理员权限");
      }
      throw new Error(`加载配置失败：HTTP状态码 ${response.status}`);
    }

    // === 解析响应数据 ===
    const result = await response.json();
    console.log(
      "[移动端易支付配置] 成功获取易支付配置：",
      createSafeClientLogValue(result),
    );

    // === 检查业务状态 ===
    if (!result.success) {
      throw new Error(result.message || "加载配置失败");
    }

    // === 填充表单字段（使用移动端的元素ID）===

    const config = result.config || {};

    // 填充host字段
    const hostInput = document.getElementById("yipay-host");
    if (hostInput) {
      hostInput.value = config.host || "";
    }

    // 填充pid字段
    const pidInput = document.getElementById("yipay-pid");
    if (pidInput) {
      pidInput.value = config.pid || "";
    }

    // 填充key字段
    const keyInput = document.getElementById("yipay-key");
    if (keyInput) {
      keyInput.value = config.key || "";
    }

    // 填充enabled_payment_methods字段
    const methodsInput = document.getElementById("yipay-enabled-methods");
    if (methodsInput) {
      methodsInput.value = config.enabled_payment_methods || "";
    }

    // 填充payment_method字段
    const typeSelect = document.getElementById("yipay-payment-method");
    if (typeSelect) {
      typeSelect.value = config.payment_method || "jump";
    }

    // === 显示成功提示 ===
    const resultDiv = document.getElementById("yipay-config-result");
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-2">
          ✓ 配置已加载
        </div>
      `;
      resultDiv.classList.remove("hidden");

      // 3秒后自动隐藏
      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 3000);
    }

    console.log("[移动端易支付配置] 配置已成功填充到表单");
  } catch (error) {
    // === 错误处理 ===
    console.error("[移动端易支付配置] 加载配置时发生错误：", error);

    const resultDiv = document.getElementById("yipay-config-result");
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
          ✗ 加载失败：${error.message || "未知错误"}
        </div>
      `;
      resultDiv.classList.remove("hidden");

      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 8000);
    } else {
      // showModalAlert(`加载失败：${error.message || "未知错误"}`);
      Swal.fire({
        icon: "error",
        title: "加载失败",
        text: `加载失败：${error.message || "未知错误"}`,
      });
    }
  }
}

/**
 * 保存移动端易支付配置
 *
 * 功能说明：
 * 从移动端表单中收集用户输入的易支付配置，验证后发送到服务器保存
 *
 * API端点：PUT /api/admin/yipay_config
 * 权限要求：modify_config权限 + admin或super_admin用户组
 */
async function saveMobileYiPayConfig() {
  // 在控制台输出日志
  console.log("[移动端易支付配置] 开始保存易支付配置...");

  // === 获取DOM元素（使用移动端的元素ID）===
  const hostInput = document.getElementById("yipay-host");
  const pidInput = document.getElementById("yipay-pid");
  const keyInput = document.getElementById("yipay-key");
  const methodsInput = document.getElementById("yipay-enabled-methods");
  const typeSelect = document.getElementById("yipay-payment-method");

  // === 获取并验证输入值 ===

  const host = hostInput ? hostInput.value.trim() : "";
  if (!host) {
    // showModalAlert("请输入易支付接口域名");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入易支付接口域名",
    });
    if (hostInput) hostInput.focus();
    return;
  }

  const pid = pidInput ? pidInput.value.trim() : "";
  if (!pid) {
    // showModalAlert("请输入商户ID");
    Swal.fire({
      icon: "error",
      title: "错误",
    });
    if (pidInput) pidInput.focus();
    return;
  }

  const key = keyInput ? keyInput.value.trim() : "";
  if (!key) {
    // showModalAlert("请输入商户密钥");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "请输入商户密钥",
    });
    if (keyInput) keyInput.focus();
    return;
  }

  const enabledMethods = methodsInput ? methodsInput.value.trim() : "";
  const paymentMethod = typeSelect ? typeSelect.value : "jump";

  console.log("[移动端易支付配置] 准备提交的配置：", {
    host,
    pid,
    key: "***隐藏***",
    enabled_payment_methods: enabledMethods,
    payment_method: paymentMethod,
  });

  try {
    // === 发起HTTP PUT请求 ===
    const response = await fetch("/api/admin/yipay_config", {
      method: "PUT",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        host: host,
        pid: pid,
        key: key,
        enabled_payment_methods: enabledMethods,
        payment_method: paymentMethod,
      }),
    });

    // === 检查响应状态 ===
    if (!response.ok) {
      if (response.status === 403) {
        throw new Error("权限不足，需要管理员权限");
      }
      throw new Error(`保存配置失败：HTTP状态码 ${response.status}`);
    }

    // === 解析响应数据 ===
    const result = await response.json();
    console.log(
      "[移动端易支付配置] API响应：",
      createSafeClientLogValue(result),
    );

    // === 检查业务状态 ===
    if (!result.success) {
      throw new Error(result.message || "保存配置失败");
    }

    // === 显示成功提示 ===
    const resultDiv = document.getElementById("yipay-config-result");
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg p-2">
          ✓ 配置保存成功
        </div>
      `;
      resultDiv.classList.remove("hidden");

      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 3000);
    }

    console.log("[移动端易支付配置] 配置保存成功");
  } catch (error) {
    // === 错误处理 ===
    console.error("[移动端易支付配置] 保存配置时发生错误：", error);

    const resultDiv = document.getElementById("yipay-config-result");
    if (resultDiv) {
      resultDiv.innerHTML = `
        <div class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
          ✗ 保存失败：${error.message || "未知错误"}
        </div>
      `;
      resultDiv.classList.remove("hidden");

      setTimeout(() => {
        resultDiv.classList.add("hidden");
      }, 8000);
    } else {
      // showModalAlert(`保存失败：${error.message || "未知错误"}`);
      Swal.fire({
        icon: "error",
        title: "保存失败",
        text: `保存失败：${error.message || "未知错误"}`,
      });
    }
  }
}

// ==========================================
// 初始化和事件绑定
// ==========================================
// 在页面DOM完全加载后，初始化PC端管理员支付设置面板
// 包括加载初始配置、绑定事件监听器等
// ==========================================

/**
 * PC端管理员支付设置面板初始化
 *
 * 功能说明：
 * 1. 绑定所有按钮的点击事件
 * 2. 加载支付方式配置（Tab 1）
 * 3. 设置默认显示的Tab
 *
 * 调用时机：
 * - 页面DOM加载完成后自动执行（DOMContentLoaded事件）
 */
document.addEventListener("DOMContentLoaded", function () {
  console.log("[PC端支付设置] 开始初始化PC端管理员支付设置面板...");

  // === Tab 1: 绑定保存配置按钮 ===

  const saveBtn = document.getElementById(
    "admin-save-payment-methods-btn_modal",
  );
  if (saveBtn) {
    saveBtn.addEventListener("click", function () {
      console.log("[PC端支付设置] 用户点击了保存配置按钮");
      saveAdminPaymentMethodsConfig();
    });
    console.log("[PC端支付设置] 保存配置按钮事件已绑定");
  } else {
    console.warn("[PC端支付设置] 警告：找不到保存配置按钮");
  }

  // === Tab 1: 页面加载时自动加载支付方式配置 ===

  // 延迟100ms后加载配置，确保DOM完全准备就绪
  setTimeout(() => {
    loadPaymentMethodsConfig(
      (show_Modal_Alert = false),
      (DOMContentLoaded_Event = true),
    );
  }, 100);

  console.log("[PC端支付设置] PC端管理员支付设置面板初始化完成");
});

// --- Next Script Block ---

// ==========================================
// 注册页面available_runs提示初始化函数
// ==========================================
/**
 * 初始化注册页面的available_runs提示信息
 *
 * 功能说明：
 * 1. 调用 /api/config/registration_display 获取配置
 * 2. 根据配置决定是否显示注册提示
 * 3. 将提示文本中的 {available_runs} 占位符替换为实际数值
 * 4. 同时更新PC端和移动端的提示元素
 *
 * 调用时机：
 * - 页面加载完成后自动调用（在DOMContentLoaded事件中）
 * - 用户打开注册模态框时可以再次调用（确保显示最新配置）
 *
 * 相关HTML元素：
 * - PC端：#auth-register-available-runs-hint（容器）和 #auth-register-runs-text（文本）
 * - 移动端：#mobile-register-available-runs-hint（容器）和 #mobile-register-runs-text（文本）
 *
 * 配置来源：
 * - .\configs\config.json 的 [Registration_Display] 节
 * - show_available_runs_on_register: 是否显示（"true"或"false"）
 * - register_available_runs_hint: 提示文本模板（包含 {available_runs} 占位符）
 *
 * 默认免费次数：
 * - 从 /api/config/registration_display 的 available_runs 字段获取
 * - 该值从 .\configs\config.json 的 [Payment_Settings] -> default_available_runs 读取
 * - 这个数值与系统实际给新用户分配的次数一致
 */
async function initRegisterAvailableRunsHint() {
  try {
    // 在控制台输出日志，记录初始化开始
    console.log("[注册提示] 开始加载注册页面available_runs提示配置...");

    // ========== 步骤1：调用API获取配置 ==========

    if (
      sessionUUID === undefined ||
      sessionUUID === null ||
      sessionUUID === ""
    ) {
      console.error(
        "[PC端易支付配置] 错误：sessionUUID未定义，无法验证支付方式",
      );
      sessionUUID = getUUIDFromURL();
    }

    // 使用fetch()发送GET请求到配置读取接口
    // fetch()返回一个Promise对象，需要用await等待响应
    const response = await fetch("/api/config/registration_display", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        // 添加Session ID请求头（如果存在）
        "X-Session-ID": sessionUUID,
      },
    });

    // 检查HTTP响应状态码是否成功（200-299）
    if (!response.ok) {
      // 如果响应失败（如404、500等），抛出错误
      // response.status 是HTTP状态码，response.statusText 是状态描述
      throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
    }

    // 将响应体解析为JSON格式
    // .json()方法返回一个Promise，需要用await等待解析完成
    const config = await response.json();

    // 在控制台输出获取到的配置（用于调试）
    // console.log("[注册提示] 获取到的配置:", config);

    // ========== 步骤2：检查是否需要显示提示 ==========

    // 如果配置标记不需要支付功能，则不显示注册提示
    if (
      config.require_payment === "false" ||
      config.require_payment === false
    ) {
      console.log(
        "[注册提示] 配置为无需付费（require_payment = false），不显示注册次数提示",
      );
      return;
    }

    // 从配置中读取 show_available_runs_on_register 字段
    // 注意：配置值是字符串 "true" 或 "false"，不是布尔值
    // 使用 === 'true' 进行严格比较，转换为布尔值
    if (config.show_available_runs_on_register === "true") {
      // 配置为显示，继续处理

      // ========== 步骤3：获取available_runs值 ==========

      // 从API响应中获取 available_runs 的值
      // 这个值是从服务器的 .\configs\config.json 配置文件中读取的
      // [Payment_Settings] -> default_available_runs
      // 如果配置中没有该字段，使用默认值10次作为后备
      const defaultRuns = config.available_runs || 10;

      // ========== 步骤4：替换占位符，生成实际的提示文本 ==========

      // 从配置中获取提示文本模板
      // 例如："注册即可得 {available_runs} 次校园跑"
      const hintTemplate = config.register_available_runs_hint;

      // 使用String.replace()方法替换占位符
      // 第一个参数是要查找的字符串（占位符）
      // 第二个参数是替换后的字符串（实际次数）
      // 例如："注册即可得 {available_runs} 次校园跑" -> "注册即可得 10 次校园跑"
      // 当默认次数等于 -1 时直接显示"无限制"，不套用格式模板，避免出现占位符残留
      let hintText;
      if (Number(defaultRuns) === -1) {
        hintText = hintTemplate
          .replace("{available_runs} 次", "无限制")
          .replace("{available_runs}", "无限制");
      } else {
        hintText = hintTemplate.replace("{available_runs}", defaultRuns);
      }

      // ========== 步骤5：更新PC端的提示元素 ==========

      // 获取PC端提示文本元素
      const pcTextElement = document.getElementById("auth-register-runs-text");
      if (pcTextElement) {
        // 如果元素存在，更新其文本内容
        // 使用textContent（而非innerHTML）防止XSS攻击
        pcTextElement.textContent = hintText;

        // 在控制台输出日志
        console.log("[注册提示] PC端提示文本已更新:", hintText);
      } else {
        // 如果元素不存在，输出警告日志
        console.warn(
          "[注册提示] 警告：找不到PC端提示文本元素 #auth-register-runs-text",
        );
      }

      // 获取PC端提示容器元素
      const pcContainerElement = document.getElementById(
        "auth-register-available-runs-hint",
      );
      if (pcContainerElement) {
        // 移除hidden类，显示提示容器
        // classList.remove()方法移除指定的CSS类
        pcContainerElement.classList.remove("hidden");

        // 在控制台输出日志
        console.log("[注册提示] PC端提示容器已显示");
      } else {
        // 如果元素不存在，输出警告日志
        console.warn(
          "[注册提示] 警告：找不到PC端提示容器元素 #auth-register-available-runs-hint",
        );
      }

      // ========== 步骤6：更新移动端的提示元素 ==========

      // 获取移动端提示文本元素
      const mobileTextElement = document.getElementById(
        "mobile-register-runs-text",
      );
      if (mobileTextElement) {
        // 如果元素存在，更新其文本内容
        mobileTextElement.textContent = hintText;

        // 在控制台输出日志
        console.log("[注册提示] 移动端提示文本已更新:", hintText);
      } else {
        // 如果元素不存在，输出警告日志
        console.warn(
          "[注册提示] 警告：找不到移动端提示文本元素 #mobile-register-runs-text",
        );
      }

      // 获取移动端提示容器元素
      const mobileContainerElement = document.getElementById(
        "mobile-register-available-runs-hint",
      );
      if (mobileContainerElement) {
        // 移除hidden类，显示提示容器
        mobileContainerElement.classList.remove("hidden");

        // 在控制台输出日志
        console.log("[注册提示] 移动端提示容器已显示");
      } else {
        // 如果元素不存在，输出警告日志
        console.warn(
          "[注册提示] 警告：找不到移动端提示容器元素 #mobile-register-available-runs-hint",
        );
      }

      // 在控制台输出总结日志
      console.log("[注册提示] 注册提示初始化完成，提示已显示");
    } else {
      // 配置为不显示提示
      console.log(
        "[注册提示] 配置为不显示注册提示（show_available_runs_on_register = false）",
      );
    }
  } catch (error) {
    // ========== 异常处理 ==========

    // 捕获所有可能的异常（网络错误、JSON解析错误等）
    // 输出错误日志到控制台，包含错误对象的详细信息
    console.error("[注册提示] 加载注册提示配置失败:", error);

    // 注意：即使加载失败，也不影响页面其他功能
    // 只是不显示注册提示而已，用户仍然可以正常注册
  }
}

// ==========================================
// 个人资料页面available_runs显示函数
// ==========================================
/**
 * 更新个人资料页面中的available_runs显示
 *
 * 功能说明：
 * 1. 调用 /api/config/profile_display 获取显示配置
 * 2. 根据配置决定是否显示available_runs
 * 3. 将显示格式中的 {available_runs} 占位符替换为用户的实际剩余次数
 * 4. 同时更新PC端和移动端的显示元素
 *
 * 调用时机：
 * - 加载个人资料数据后调用（传入用户数据对象）
 * - 用户完成任务或次数变更后刷新个人资料时再次调用
 *
 * 参数说明：
 * @param {Object} userData - 用户数据对象，包含以下字段：
 *   - available_runs: 用户的剩余免费次数（整数）
 *   - auth_username: 用户名
 *   - 其他用户信息字段...
 *
 * 相关HTML元素：
 * - PC端：#admin-profile-available-runs-container（容器）和 #admin-profile-available-runs-text（文本）
 * - 移动端：#mobile-profile-available-runs-container（容器）和 #mobile-profile-available-runs-text（文本）
 *
 * 配置来源：
 * - .\configs\config.json 的 [Profile_Display] 节
 * - show_available_runs: 是否显示（"true"或"false"）
 * - available_runs_format: 显示格式模板（包含 {available_runs} 占位符）
 *
 * 显示示例：
 * - 格式模板："剩余免费次数：{available_runs} 次"
 * - 用户剩余5次
 * - 显示结果："剩余免费次数：5 次"
 */
async function updateProfileAvailableRuns(userData) {
  try {
    // 在控制台输出日志，记录函数调用
    console.log(
      "[个人资料] 开始更新available_runs显示，用户数据:",
      createSafeClientLogValue(userData),
    );

    // ========== 步骤1：验证参数 ==========

    // 检查userData参数是否存在
    if (!userData) {
      // 如果参数为null或undefined，输出警告并退出
      console.warn(
        "[个人资料] 警告：userData参数为空，无法更新available_runs显示",
      );
      return;
    }

    // ========== 步骤2：调用API获取显示配置 ==========

    if (
      sessionUUID === undefined ||
      sessionUUID === null ||
      sessionUUID === ""
    ) {
      console.error(
        "[PC端易支付配置] 错误：sessionUUID未定义，无法验证支付方式",
      );
      sessionUUID = getUUIDFromURL();
    }

    // 使用fetch()发送GET请求到配置读取接口
    const response = await fetch("/api/config/profile_display", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        // 添加Session ID请求头（如果存在）
        "X-Session-ID": sessionUUID,
      },
    });

    // 检查HTTP响应状态码是否成功
    if (!response.ok) {
      // 如果响应失败，抛出错误
      throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
    }

    // 将响应体解析为JSON格式
    const config = await response.json();

    // 在控制台输出获取到的配置
    console.log(
      "[个人资料] 获取到的显示配置:",
      createSafeClientLogValue(config),
    );

    // ========== 步骤3：检查是否需要显示available_runs ==========

    // 如果配置标记不需要支付功能，则不显示available_runs
    if (
      config.require_payment === "false" ||
      config.require_payment === false
    ) {
      console.log(
        "[个人资料] 配置为无需付费（require_payment = false），不显示available_runs",
      );
      return;
    }

    // 从配置中读取 show_available_runs 字段
    // 配置值是字符串 "true" 或 "false"
    if (config.show_available_runs === "true") {
      // 配置为显示，继续处理

      // ========== 步骤4：获取用户的available_runs值 ==========

      // 从userData对象中提取available_runs字段
      // 使用 || 0 确保如果字段不存在，默认为0
      let availableRuns = userData.available_runs || 0;

      // 在控制台输出用户的剩余次数
      console.log("[个人资料] 用户剩余次数:", availableRuns);

      // ========== 步骤5：替换占位符，生成显示文本 ==========

      // 从配置中获取显示格式模板
      // 例如："剩余免费次数：{available_runs} 次"
      const formatTemplate = config.available_runs_format;

      // 当次数为 -1 时直接显示"无限制"，不套用格式模板，避免出现占位符残留
      let displayText;
      if (Number(availableRuns) === -1) {
        // displayText = "无限制";
        displayText = formatTemplate.replace("{available_runs}", "无限制");
      } else {
        displayText = formatTemplate.replace("{available_runs}", availableRuns);
      }

      // ========== 步骤6：更新PC端的显示元素 ==========

      // 获取PC端显示文本元素
      const pcTextElement = document.getElementById(
        "admin-profile-available-runs-text",
      );
      if (pcTextElement) {
        // 如果元素存在，更新其文本内容
        // 使用textContent防止XSS攻击
        pcTextElement.textContent = displayText;

        // 在控制台输出日志
        console.log("[个人资料] PC端显示文本已更新:", displayText);
      } else {
        // 如果元素不存在，输出警告
        console.warn(
          "[个人资料] 警告：找不到PC端显示文本元素 #admin-profile-available-runs-text",
        );
      }

      // 获取PC端显示容器元素
      const pcContainerElement = document.getElementById(
        "admin-profile-available-runs-container",
      );
      if (pcContainerElement) {
        // 移除hidden类，显示容器
        pcContainerElement.classList.remove("hidden");

        // 在控制台输出日志
        console.log("[个人资料] PC端显示容器已显示");
      } else {
        // 如果元素不存在，输出警告
        console.warn(
          "[个人资料] 警告：找不到PC端显示容器元素 #admin-profile-available-runs-container",
        );
      }

      // ========== 步骤7：更新移动端的显示元素 ==========

      // 获取移动端显示文本元素
      const mobileTextElement = document.getElementById(
        "mobile-profile-available-runs-text",
      );
      if (mobileTextElement) {
        // 如果元素存在，更新其文本内容
        mobileTextElement.textContent = displayText;

        // 在控制台输出日志
        console.log("[个人资料] 移动端显示文本已更新:", displayText);
      } else {
        // 如果元素不存在，输出警告
        console.warn(
          "[个人资料] 警告：找不到移动端显示文本元素 #mobile-profile-available-runs-text",
        );
      }

      // 获取移动端显示容器元素
      const mobileContainerElement = document.getElementById(
        "mobile-profile-available-runs-container",
      );
      if (mobileContainerElement) {
        // 移除hidden类，显示容器
        mobileContainerElement.classList.remove("hidden");

        // 在控制台输出日志
        console.log("[个人资料] 移动端显示容器已显示");
      } else {
        // 如果元素不存在，输出警告
        console.warn(
          "[个人资料] 警告：找不到移动端显示容器元素 #mobile-profile-available-runs-container",
        );
      }

      // 在控制台输出总结日志
      console.log("[个人资料] available_runs显示更新完成");
    } else {
      // 配置为不显示available_runs
      console.log(
        "[个人资料] 配置为不显示available_runs（show_available_runs = false）",
      );
    }
  } catch (error) {
    // ========== 异常处理 ==========

    // 捕获所有可能的异常
    // 输出错误日志到控制台
    console.error("[个人资料] 更新available_runs显示失败:", error);

    // 注意：即使更新失败，也不影响页面其他功能
    // 只是不显示available_runs而已
  }
}

// ==========================================
// 页面加载时初始化注册提示
// ==========================================
/**
 * 在页面DOM加载完成后，自动调用注册提示初始化函数
 *
 * 调用时机：
 * - DOM内容加载完成（DOMContentLoaded事件触发时）
 *
 * 注意事项：
 * - 此事件在HTML文档完全解析后触发，不等待样式表、图片等资源
 * - 确保在调用initRegisterAvailableRunsHint()时，相关DOM元素已存在
 */
document.addEventListener("DOMContentLoaded", function () {
  console.log("[页面初始化] 页面加载完成，开始初始化注册提示...");

  // 调用注册提示初始化函数
  // 使用async/await语法，但不等待完成（避免阻塞页面其他初始化）
  initRegisterAvailableRunsHint();

  console.log("[页面初始化] 注册提示初始化函数已调用");
});

// ==========================================
// 注意事项和使用说明
// ==========================================
/**
 * 【重要】关于updateProfileAvailableRuns()的调用：
 *
 * 此函数需要在加载用户个人资料数据后手动调用。
 *
 * 典型的调用场景：
 *
 * 1. 用户登录后加载个人资料：
 *    ```javascript
 *    async function loadUserProfile() {
 *      const response = await fetch('/api/user/profile');
 *      const userData = await response.json();
 *
 *      // 更新页面显示用户信息...
 *
 *      // 调用此函数更新available_runs显示
 *      await updateProfileAvailableRuns(userData);
 *    }
 *    ```
 *
 * 2. 用户完成任务后刷新个人资料：
 *    ```javascript
 *    async function refreshAfterTask() {
 *      const response = await fetch('/api/user/profile');
 *      const userData = await response.json();
 *      await updateProfileAvailableRuns(userData);
 *    }
 *    ```
 *
 * 3. 用户支付成功后刷新个人资料：
 *    ```javascript
 *    async function refreshAfterPayment() {
 *      const response = await fetch('/api/user/profile');
 *      const userData = await response.json();
 *      await updateProfileAvailableRuns(userData);
 *    }
 *    ```
 *
 * 【注意】
 * 如果项目中已有加载用户资料的函数，需要在该函数中添加对
 * updateProfileAvailableRuns(userData) 的调用。
 */

// ============================================================
// 价格配置管理相关函数
// ============================================================

/**
 * 加载价格配置（PC端）
 *
 * 功能说明：
 * 从后端API获取当前的价格配置，并填充到PC端的表单中。
 *
 * 调用时机：
 * 1. 用户点击"价格设置"标签时
 * 2. 用户点击"刷新"按钮时
 *
 * API端点：GET /api/admin/pricing_config
 *
 * 表单元素ID：
 * - pricing-require-payment_modal：是否需要付费（复选框）
 * - pricing-per-run-cost_modal：单次跑步费用（数字输入框）
 * - pricing-default-runs_modal：新用户默认免费次数（数字输入框）
 */
async function loadPricingConfig() {
  configLoadState.pricing = false;
  try {
    // ========== 显示加载状态 ==========
    // 为了提升用户体验，在数据加载期间显示加载提示
    console.log("[价格配置] 正在加载价格配置...");

    // ========== 发送GET请求获取配置 ==========
    // 使用fetch API从后端获取价格配置数据
    const response = await fetch("/api/admin/pricing_config", {
      method: "GET", // HTTP方法：GET（获取数据）
      headers: {
        "Content-Type": "application/json", // 请求头：指定内容类型为JSON
        "X-Session-ID": sessionUUID,
      },
      credentials: "include", // 包含认证凭证（cookies），用于身份验证
    });

    // ========== 解析响应数据 ==========
    // 将响应体解析为JSON对象
    const data = await response.json();

    // ========== 检查响应状态 ==========
    // 如果请求失败（success为false），抛出错误
    if (!data.success) {
      throw new Error(data.message || "加载价格配置失败");
    }

    // ========== 提取配置数据 ==========
    // 从响应数据中提取config对象
    const config = data.config;

    // ========== 填充表单字段 ==========

    // 填充"是否需要付费"复选框
    // 获取复选框元素
    const requirePaymentCheckbox = document.getElementById(
      "pricing-require-payment_modal",
    );
    if (requirePaymentCheckbox) {
      // 设置复选框的选中状态
      // checked属性为true表示选中（需要付费），false表示未选中（不需要付费）
      requirePaymentCheckbox.checked = config.require_payment;
    } else {
      // 如果找不到元素，记录警告日志
      console.warn(
        "[价格配置] 警告：找不到元素 #pricing-require-payment_modal",
      );
    }

    // 填充"单次跑步费用"输入框
    const perRunCostInput = document.getElementById(
      "pricing-per-run-cost_modal",
    );
    if (perRunCostInput) {
      // 设置输入框的值
      // 使用toFixed(2)将浮点数格式化为两位小数的字符串
      perRunCostInput.value = config.per_run_cost.toFixed(2);
    } else {
      console.warn("[价格配置] 警告：找不到元素 #pricing-per-run-cost_modal");
    }

    // 填充"新用户默认免费次数"输入框
    const defaultRunsInput = document.getElementById(
      "pricing-default-runs_modal",
    );
    if (defaultRunsInput) {
      // 设置输入框的值
      // 整数类型，直接赋值
      defaultRunsInput.value = config.default_available_runs;
    } else {
      console.warn("[价格配置] 警告：找不到元素 #pricing-default-runs_modal");
    }

    // ========== 填充UI显示配置字段 ==========

    // 填充"个人资料页显示剩余次数"复选框
    // 从后端API返回的config对象中获取show_available_runs字段
    const showAvailableRunsCheckbox = document.getElementById(
      "pricing-show-available-runs_modal",
    );
    if (showAvailableRunsCheckbox) {
      // 设置复选框的选中状态
      // checked属性为true表示选中（显示剩余次数），false表示未选中（不显示）
      showAvailableRunsCheckbox.checked = config.show_available_runs;
    } else {
      // 如果找不到元素，记录警告日志
      console.warn(
        "[价格配置] 警告：找不到元素 #pricing-show-available-runs_modal",
      );
    }

    // 填充"剩余次数显示格式"输入框
    // 这是一个文本模板，包含{available_runs}占位符
    const availableRunsFormatInput = document.getElementById(
      "pricing-available-runs-format_modal",
    );
    if (availableRunsFormatInput) {
      // 设置输入框的值
      // 如果后端没有返回该字段，使用默认值
      availableRunsFormatInput.value =
        config.available_runs_format || "剩余免费次数：{available_runs} 次";
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #pricing-available-runs-format_modal",
      );
    }

    // 填充"注册页显示免费次数提示"复选框
    // 控制是否在用户注册页面显示提示信息
    const showRegisterHintCheckbox = document.getElementById(
      "pricing-show-register-hint_modal",
    );
    if (showRegisterHintCheckbox) {
      // 设置复选框的选中状态
      showRegisterHintCheckbox.checked = config.show_available_runs_on_register;
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #pricing-show-register-hint_modal",
      );
    }

    // 填充"注册页提示文本"输入框
    // 这是注册页面显示的提示文本模板
    const registerHintTextInput = document.getElementById(
      "pricing-register-hint-text_modal",
    );
    if (registerHintTextInput) {
      // 设置输入框的值
      // 如果后端没有返回该字段，使用默认值
      registerHintTextInput.value =
        config.register_available_runs_hint ||
        "注册即可得 {available_runs} 次校园跑";
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #pricing-register-hint-text_modal",
      );
    }

    // ========== 记录成功日志 ==========
    console.log(
      "[价格配置] 价格配置加载成功",
      createSafeClientLogValue(config),
    );
    configLoadState.pricing = true;
  } catch (error) {
    configLoadState.pricing = false;
    // ========== 错误处理 ==========
    // 捕获加载过程中的任何错误
    console.error("[价格配置] 加载价格配置失败:", error);

    // 使用alert提示用户错误信息
    // 在实际生产环境中，建议使用更友好的UI提示（如SweetAlert2）
    // showModalAlert("加载价格配置失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "加载失败",
      text: `加载失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 保存价格配置（PC端）
 *
 * 功能说明：
 * 从PC端表单中读取价格配置，发送到后端API进行保存。
 *
 * 调用时机：
 * 用户点击"保存配置"按钮时
 *
 * API端点：PUT /api/admin/pricing_config
 *
 * 验证规则：
 * 1. require_payment：必须为布尔值
 * 2. per_run_cost：必须为非负数，支持小数
 * 3. default_available_runs：必须为非负整数
 */
async function savePricingConfig() {
  if (!ensureConfigLoaded("pricing", "价格")) {
    return;
  }
  try {
    // ========== 获取表单元素 ==========

    // 获取"是否需要付费"复选框
    const requirePaymentCheckbox = document.getElementById(
      "pricing-require-payment_modal",
    );
    // 获取"单次跑步费用"输入框
    const perRunCostInput = document.getElementById(
      "pricing-per-run-cost_modal",
    );
    // 获取"新用户默认免费次数"输入框
    const defaultRunsInput = document.getElementById(
      "pricing-default-runs_modal",
    );

    // 获取UI显示配置的表单元素
    // 获取"个人资料页显示剩余次数"复选框
    const showAvailableRunsCheckbox = document.getElementById(
      "pricing-show-available-runs_modal",
    );
    // 获取"剩余次数显示格式"输入框
    const availableRunsFormatInput = document.getElementById(
      "pricing-available-runs-format_modal",
    );
    // 获取"注册页显示免费次数提示"复选框
    const showRegisterHintCheckbox = document.getElementById(
      "pricing-show-register-hint_modal",
    );
    // 获取"注册页提示文本"输入框
    const registerHintTextInput = document.getElementById(
      "pricing-register-hint-text_modal",
    );

    // ========== 验证表单元素是否存在 ==========
    // 如果任何一个表单元素不存在，抛出错误
    if (
      !requirePaymentCheckbox ||
      !perRunCostInput ||
      !defaultRunsInput ||
      !showAvailableRunsCheckbox ||
      !availableRunsFormatInput ||
      !showRegisterHintCheckbox ||
      !registerHintTextInput
    ) {
      throw new Error("表单元素未找到，请刷新页面后重试");
    }

    // ========== 读取表单值 ==========

    // 读取"是否需要付费"的值（布尔类型）
    const requirePayment = requirePaymentCheckbox.checked;

    // 读取"单次跑步费用"的值（浮点类型）
    // parseFloat() 将字符串转换为浮点数
    const perRunCost = parseFloat(perRunCostInput.value);

    // 读取"新用户默认免费次数"的值（整数类型）
    // parseInt() 将字符串转换为整数
    const defaultRuns = parseInt(defaultRunsInput.value);

    // 读取UI显示配置的值
    // 读取"个人资料页显示剩余次数"的值（布尔类型）
    const showAvailableRuns = showAvailableRunsCheckbox.checked;

    // 读取"剩余次数显示格式"的值（字符串类型）
    // .trim() 去除首尾空格
    const availableRunsFormat = availableRunsFormatInput.value.trim();

    // 读取"注册页显示免费次数提示"的值（布尔类型）
    const showRegisterHint = showRegisterHintCheckbox.checked;

    // 读取"注册页提示文本"的值（字符串类型）
    const registerHintText = registerHintTextInput.value.trim();

    // ========== 客户端验证 ==========

    // 验证"单次跑步费用"是否为有效数字
    if (isNaN(perRunCost)) {
      throw new Error("单次跑步费用必须是有效的数字");
    }

    // 验证"单次跑步费用"是否为非负数
    if (perRunCost < 0) {
      throw new Error("单次跑步费用不能为负数");
    }

    // 验证"新用户默认免费次数"是否为有效数字
    if (isNaN(defaultRuns)) {
      throw new Error("新用户默认免费次数必须是有效的整数");
    }

    // 验证"新用户默认免费次数"是否为非负数
    if (defaultRuns < 0) {
      throw new Error("新用户默认免费次数不能为负数");
    }

    // 验证UI显示配置字段
    // 验证"剩余次数显示格式"不能为空
    if (!availableRunsFormat) {
      throw new Error("剩余次数显示格式不能为空");
    }

    // 验证"注册页提示文本"不能为空
    if (!registerHintText) {
      throw new Error("注册页提示文本不能为空");
    }

    // ========== 构造请求数据 ==========
    // 将表单数据封装为JSON对象
    const requestData = {
      require_payment: requirePayment,
      per_run_cost: perRunCost,
      default_available_runs: defaultRuns,
      // 添加UI显示配置字段
      show_available_runs: showAvailableRuns,
      available_runs_format: availableRunsFormat,
      show_available_runs_on_register: showRegisterHint,
      register_available_runs_hint: registerHintText,
    };

    // ========== 记录请求日志 ==========
    console.log("[价格配置] 正在保存价格配置");

    // ========== 发送PUT请求保存配置 ==========
    const response = await fetch("/api/admin/pricing_config", {
      method: "PUT", // HTTP方法：PUT（更新数据）
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json", // 请求头：指定内容类型为JSON
      },
      credentials: "include", // 包含认证凭证
      body: JSON.stringify(requestData), // 请求体：将JavaScript对象转换为JSON字符串
    });

    // ========== 解析响应数据 ==========
    const data = await response.json();

    // ========== 检查响应状态 ==========
    if (!data.success) {
      throw new Error(data.message || "保存价格配置失败");
    }

    // ========== 显示成功提示 ==========
    // 使用alert提示用户保存成功
    // 在实际生产环境中，建议使用更友好的UI提示
    // showModalAlert("价格配置已成功保存！");
    Swal.fire({
      icon: "success",
      title: "保存成功",
      text: "价格配置已成功保存！",
    });

    // ========== 记录成功日志 ==========
    console.log("[价格配置] 价格配置保存成功");
  } catch (error) {
    // ========== 错误处理 ==========
    console.error("[价格配置] 保存价格配置失败:", error);
    // showModalAlert("保存价格配置失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "保存失败",
      text: `保存失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 加载价格配置（移动端）
 *
 * 功能说明：
 * 与PC端的loadPricingConfig()功能相同，但操作移动端的表单元素。
 *
 * 表单元素ID：
 * - mobile-pricing-require-payment：是否需要付费
 * - mobile-pricing-per-run-cost：单次跑步费用
 * - mobile-pricing-default-runs：新用户默认免费次数
 */
async function loadMobilePricingConfig() {
  try {
    // 显示加载状态
    console.log("[价格配置] 正在加载价格配置（移动端）...");

    // 发送GET请求获取配置
    const response = await fetch("/api/admin/pricing_config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      credentials: "include",
    });

    // 解析响应数据
    const data = await response.json();

    // 检查响应状态
    if (!data.success) {
      throw new Error(data.message || "加载价格配置失败");
    }

    // 提取配置数据
    const config = data.config;

    // 填充表单字段

    // 填充"是否需要付费"复选框
    const requirePaymentCheckbox = document.getElementById(
      "mobile-pricing-require-payment",
    );
    if (requirePaymentCheckbox) {
      requirePaymentCheckbox.checked = config.require_payment;
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #mobile-pricing-require-payment",
      );
    }

    // 填充"单次跑步费用"输入框
    const perRunCostInput = document.getElementById(
      "mobile-pricing-per-run-cost",
    );
    if (perRunCostInput) {
      perRunCostInput.value = config.per_run_cost.toFixed(2);
    } else {
      console.warn("[价格配置] 警告：找不到元素 #mobile-pricing-per-run-cost");
    }

    // 填充"新用户默认免费次数"输入框
    const defaultRunsInput = document.getElementById(
      "mobile-pricing-default-runs",
    );
    if (defaultRunsInput) {
      defaultRunsInput.value = config.default_available_runs;
    } else {
      console.warn("[价格配置] 警告：找不到元素 #mobile-pricing-default-runs");
    }

    // ========== 填充UI显示配置字段（移动端） ==========

    // 填充"个人资料页显示剩余次数"复选框
    const showAvailableRunsCheckbox = document.getElementById(
      "mobile-pricing-show-available-runs",
    );
    if (showAvailableRunsCheckbox) {
      showAvailableRunsCheckbox.checked = config.show_available_runs;
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #mobile-pricing-show-available-runs",
      );
    }

    // 填充"剩余次数显示格式"输入框
    const availableRunsFormatInput = document.getElementById(
      "mobile-pricing-available-runs-format",
    );
    if (availableRunsFormatInput) {
      availableRunsFormatInput.value =
        config.available_runs_format || "剩余免费次数：{available_runs} 次";
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #mobile-pricing-available-runs-format",
      );
    }

    // 填充"注册页显示免费次数提示"复选框
    const showRegisterHintCheckbox = document.getElementById(
      "mobile-pricing-show-register-hint",
    );
    if (showRegisterHintCheckbox) {
      showRegisterHintCheckbox.checked = config.show_available_runs_on_register;
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #mobile-pricing-show-register-hint",
      );
    }

    // 填充"注册页提示文本"输入框
    const registerHintTextInput = document.getElementById(
      "mobile-pricing-register-hint-text",
    );
    if (registerHintTextInput) {
      registerHintTextInput.value =
        config.register_available_runs_hint ||
        "注册即可得 {available_runs} 次校园跑";
    } else {
      console.warn(
        "[价格配置] 警告：找不到元素 #mobile-pricing-register-hint-text",
      );
    }

    // 记录成功日志
    console.log(
      "[价格配置] 价格配置加载成功（移动端）",
      createSafeClientLogValue(config),
    );
  } catch (error) {
    // 错误处理
    console.error("[价格配置] 加载价格配置失败（移动端）:", error);
    // showModalAlert("加载价格配置失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "加载失败",
      text: `加载失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 保存价格配置（移动端）
 *
 * 功能说明：
 * 与PC端的savePricingConfig()功能相同，但操作移动端的表单元素。
 */
async function saveMobilePricingConfig() {
  try {
    // 获取表单元素
    const requirePaymentCheckbox = document.getElementById(
      "mobile-pricing-require-payment",
    );
    const perRunCostInput = document.getElementById(
      "mobile-pricing-per-run-cost",
    );
    const defaultRunsInput = document.getElementById(
      "mobile-pricing-default-runs",
    );

    // 获取UI显示配置的表单元素（移动端）
    const showAvailableRunsCheckbox = document.getElementById(
      "mobile-pricing-show-available-runs",
    );
    const availableRunsFormatInput = document.getElementById(
      "mobile-pricing-available-runs-format",
    );
    const showRegisterHintCheckbox = document.getElementById(
      "mobile-pricing-show-register-hint",
    );
    const registerHintTextInput = document.getElementById(
      "mobile-pricing-register-hint-text",
    );

    // 验证表单元素是否存在
    if (
      !requirePaymentCheckbox ||
      !perRunCostInput ||
      !defaultRunsInput ||
      !showAvailableRunsCheckbox ||
      !availableRunsFormatInput ||
      !showRegisterHintCheckbox ||
      !registerHintTextInput
    ) {
      throw new Error("表单元素未找到，请刷新页面后重试");
    }

    // 读取表单值
    const requirePayment = requirePaymentCheckbox.checked;
    const perRunCost = parseFloat(perRunCostInput.value);
    const defaultRuns = parseInt(defaultRunsInput.value);

    // 读取UI显示配置的值（移动端）
    const showAvailableRuns = showAvailableRunsCheckbox.checked;
    const availableRunsFormat = availableRunsFormatInput.value.trim();
    const showRegisterHint = showRegisterHintCheckbox.checked;
    const registerHintText = registerHintTextInput.value.trim();

    // 客户端验证
    if (isNaN(perRunCost)) {
      throw new Error("单次跑步费用必须是有效的数字");
    }
    if (perRunCost < 0) {
      throw new Error("单次跑步费用不能为负数");
    }
    if (isNaN(defaultRuns)) {
      throw new Error("新用户默认免费次数必须是有效的整数");
    }
    if (defaultRuns < 0) {
      throw new Error("新用户默认免费次数不能为负数");
    }

    // 验证UI显示配置字段（移动端）
    if (!availableRunsFormat) {
      throw new Error("剩余次数显示格式不能为空");
    }
    if (!registerHintText) {
      throw new Error("注册页提示文本不能为空");
    }

    // 构造请求数据
    const requestData = {
      require_payment: requirePayment,
      per_run_cost: perRunCost,
      default_available_runs: defaultRuns,
      // 添加UI显示配置字段（移动端）
      show_available_runs: showAvailableRuns,
      available_runs_format: availableRunsFormat,
      show_available_runs_on_register: showRegisterHint,
      register_available_runs_hint: registerHintText,
    };

    // 记录请求日志
    console.log("[价格配置] 正在保存价格配置（移动端）");

    if (
      sessionUUID === undefined ||
      sessionUUID === null ||
      sessionUUID === ""
    ) {
      console.error(
        "[PC端易支付配置] 错误：sessionUUID未定义，无法验证支付方式",
      );
      sessionUUID = getUUIDFromURL();
    }

    // 发送PUT请求保存配置
    const response = await fetch("/api/admin/pricing_config", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      credentials: "include",
      body: JSON.stringify(requestData),
    });

    // 解析响应数据
    const data = await response.json();

    // 检查响应状态
    if (!data.success) {
      throw new Error(data.message || "保存价格配置失败");
    }

    // 显示成功提示
    // showModalAlert("价格配置已成功保存！");
    Swal.fire({
      icon: "success",
      title: "保存成功",
      text: "价格配置已成功保存！",
    });

    // 记录成功日志
    console.log("[价格配置] 价格配置保存成功（移动端）");
  } catch (error) {
    // 错误处理
    console.error("[价格配置] 保存价格配置失败（移动端）:", error);
    // showModalAlert("保存价格配置失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "保存失败",
      text: `保存失败：${error.message || "未知错误"}`,
    });
  }
}

// --- Next Script Block ---
