// Legacy end-user payment, overdue, and billing UI extracted from main.js.
async function openPaymentModal() {
  // 步骤1：获取支付弹窗DOM元素
  const modal = document.getElementById("payment-modal");

  // 步骤2：检查弹窗元素是否存在
  // 如果不存在，说明HTML结构有问题，输出错误并返回
  if (!modal) {
    console.error("[支付] 支付弹窗元素不存在");
    return;
  }

  // 步骤3：显示支付弹窗
  // 移除'hidden'类名（如果存在），并添加'flex'类名使弹窗居中显示
  modal.classList.remove("hidden");
  modal.style.display = "flex";

  // 步骤4：重置表单到初始状态
  // 清空金额输入框，避免显示上次输入的金额
  document.getElementById("payment-amount").value = "";
  // 恢复商品描述为默认值"在线支付"
  document.getElementById("payment-product-name").value = "在线支付";

  // 步骤5：从后端加载启用的支付方式
  // 管理员可能随时修改支付配置，所以每次打开弹窗都需要重新加载
  try {
    // 调用后端API获取支付配置
    // 使用await等待异步请求完成，确保数据加载后再继续
    const response = await fetch("/api/admin/payment/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    // 将响应转换为JSON格式
    const result = await response.json();

    // 步骤6：检查API调用是否成功
    if (result.success && result.enabled_payment_methods) {
      // 获取启用的支付方式列表
      // 例如：["alipay", "wxpay"]
      const enabledMethods = result.enabled_payment_methods;

      // 获取支付方式容器DOM元素
      const container = document.getElementById("payment-methods-container");

      // 步骤7：动态生成支付方式选项
      // 清空容器，准备重新生成
      container.innerHTML = "";

      // 检查是否有启用的支付方式
      // 如果后端没有返回任何启用的支付方式，显示提示信息
      if (enabledMethods.length === 0) {
        // 创建提示HTML并插入容器
        container.innerHTML = `
                    <div class="text-center py-6 text-slate-500">
                        <p class="text-sm">暂无可用的支付方式</p>
                        <p class="text-xs mt-1">请联系管理员启用支付方式</p>
                    </div>
                `;
        return; // 直接返回，不再继续执行
      }

      // 遍历启用的支付方式，为每个方式创建一个单选按钮
      enabledMethods.forEach((method, index) => {
        // 从全局配置对象(PAYMENT_METHODS)中获取当前支付方式的配置
        // 如果配置不存在（未知的支付方式），使用默认配置
        const config = PAYMENT_METHODS[method] || {
          name: method.toUpperCase(), // 使用代码本身作为显示名称，转为大写
          icon: "emoji", // 默认使用emoji图标类型
          svg: "💳", // 使用通用的信用卡emoji作为备用
          borderColor: "hover:border-slate-500", // 使用中性的灰色边框
          textColor: "text-slate-600", // 使用中性的灰色文字
          description: "在线支付",
        };

        // 根据图标类型生成图标HTML
        // 如果icon字段为'svg'，使用svg字段的SVG代码
        // 否则使用icon字段作为emoji图标
        const iconHtml =
          config.icon === "svg"
            ? config.svg // 直接使用SVG代码（已包含样式类）
            : `<span class="text-lg">${config.icon}</span>`; // emoji图标，包裹在span中

        // 创建支付方式选项的HTML字符串
        // 使用模板字符串拼接，支持变量插值
        // 注意：第一个选项(index === 0)会被自动选中(checked属性)
        const optionHTML = `
                    <label class="flex items-center p-3 border-2 border-slate-200 rounded-lg cursor-pointer ${
                      config.borderColor
                    } transition-colors">
                        <!-- 单选按钮：name属性保证同组单选，value属性用于提交数据 -->
                        <input type="radio" name="payment-method" value="${method}" 
                            class="w-4 h-4 ${config.textColor}" ${
                              index === 0 ? "checked" : ""
                            } />
                        <!-- 支付方式图标：SVG或emoji，根据配置动态生成 -->
                        <span class="ml-3 flex items-center gap-2">
                            ${iconHtml}
                            <!-- 支付方式名称：显示给用户的中文名称 -->
                            <span class="text-sm font-medium text-slate-700">${
                              config.name
                            }</span>
                        </span>
                    </label>
                `;

        // 将HTML字符串插入到容器的末尾
        // insertAdjacentHTML比innerHTML更高效，不会重新解析整个容器
        container.insertAdjacentHTML("beforeend", optionHTML);
      });

      // 输出日志：记录成功加载的支付方式
      console.log("[支付] 已加载启用的支付方式:", enabledMethods);
    } else {
      // API调用失败或没有启用的支付方式
      // 使用Swal.fire显示友好的错误提示
      Swal.fire({
        icon: "warning",
        title: "提示",
        text: "暂无可用的支付方式，请联系管理员",
        confirmButtonText: "确定",
      });

      // 输出警告日志
      console.warn("[支付] 获取支付方式失败:", result.message);
    }
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[支付] 加载支付方式时出错:", error);

    // 显示错误提示
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "加载支付方式失败，请稍后重试",
      confirmButtonText: "确定",
    });
  }
}

// ========================================
// 关闭支付弹窗函数
// ========================================
/**
 * 关闭支付弹窗
 *
 * 功能说明：
 * 1. 隐藏支付弹窗
 * 2. 清理表单数据
 *
 * 调用时机：
 * - 用户点击"取消"按钮时
 * - 用户点击弹窗外部区域时
 * - 用户点击关闭按钮（X）时
 *
 * @returns {void} 无返回值
 */
function closePaymentModal() {
  // 获取支付弹窗DOM元素
  const modal = document.getElementById("payment-modal");

  // 检查元素是否存在
  if (!modal) return;

  // 隐藏弹窗：添加'hidden'类名
  modal.classList.add("hidden");
  modal.style.display = "none";

  // 输出日志
  console.log("[支付] 支付弹窗已关闭");
}

// ========================================
// 创建支付订单函数
// ========================================
/**
 * 创建支付订单并跳转到支付页面
 *
 * 功能说明：
 * 1. 验证用户输入（金额、支付方式、商品名称）
 * 2. 获取当前页面的app_host并验证其有效性
 * 3. 调用后端API创建支付订单
 * 4. 在新窗口打开支付URL
 * 5. 启动订单状态轮询，实时查询支付结果
 *
 * 参数验证规则：
 * - amount: 必须大于0.01元
 * - pay_type: 必须选择一个支付方式
 * - product_name: 不能为空
 *
 * @returns {Promise<void>} 无返回值的Promise
 */
async function createPaymentOrder() {
  // 步骤1：获取用户输入的支付金额
  // 使用trim()去除首尾空格，避免用户误输入空格
  const amount = document.getElementById("payment-amount").value.trim();

  // 步骤2：获取选中的支付方式
  // querySelector获取被选中的单选按钮的value属性
  const payType = document.querySelector(
    'input[name="payment-method"]:checked',
  )?.value;

  // 步骤3：获取商品名称
  const productName = document
    .getElementById("payment-product-name")
    .value.trim();

  // 步骤4：参数验证 - 检查金额是否为空
  if (!amount) {
    // 使用showModalAlert显示友好的错误提示
    // showModalAlert是移动端兼容的弹窗函数，避免使用Swal.fire
    showModalAlert("请输入支付金额", "提示");
    return; // 验证失败，终止函数执行
  }

  // 步骤5：参数验证 - 检查金额是否小于最低限额
  // parseFloat将字符串转换为浮点数，便于数值比较
  if (parseFloat(amount) < 0.01) {
    // 使用showModalAlert显示最低金额限制的提示
    showModalAlert("支付金额不能低于0.01元", "提示");
    return;
  }

  // 步骤6：参数验证 - 检查是否选择了支付方式
  if (!payType) {
    // 使用showModalAlert提示用户选择支付方式
    showModalAlert("请选择支付方式", "提示");
    return;
  }

  // 步骤7：参数验证 - 检查商品名称是否为空
  if (!productName) {
    // 使用showModalAlert提示用户输入商品描述
    showModalAlert("请输入商品描述", "提示");
    return;
  }

  // 步骤8：获取当前页面的app_host（完整URL，包含协议和域名）
  // location.protocol 返回协议（如：https:）
  // location.host 返回域名和端口（如：example.com:8080）
  const appHost = window.location.protocol + "//" + window.location.host;

  // 输出日志：记录即将创建的订单信息
  console.log("[支付] 准备创建订单:", {
    amount,
    payType,
    productName,
    appHost,
  });

  try {
    // 步骤9：验证app_host是否有效
    // 调用后端API验证当前域名是否允许创建订单
    const verifyResponse = await fetch("/api/payment/verify_host", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ app_host: appHost }),
    });

    // 解析验证结果
    const verifyResult = await verifyResponse.json();

    // 步骤10：检查验证结果
    if (!verifyResult.success) {
      // 域名验证失败，显示错误提示
      // 使用showModalAlert显示域名验证失败的错误信息
      showModalAlert(
        verifyResult.message || "当前域名未授权，无法创建订单",
        "验证失败",
      );
      console.error("[支付] app_host验证失败:", verifyResult.message);
      return;
    }

    // 步骤11：创建支付订单
    // 调用后端API，传入金额、支付方式、商品名称等参数
    const createResponse = await fetch("/api/payment/create", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        amount: amount,
        payment_type: "jump",
        payment_method: payType,
        product_name: productName,
        app_host: appHost,
        return_url: window.location.href,
        sub_openid: subOpenid,
        sub_appid: subAppid,
        device: Get_YiPAi_device(),
      }),
    });

    // 解析创建结果
    const createResult = await createResponse.json();

    // 步骤12：检查订单创建结果
    if (!createResult.success) {
      // 订单创建失败，显示错误提示
      // 使用showModalAlert显示创建失败的错误信息
      showModalAlert(
        createResult.message || "创建订单时出错，请稍后重试",
        "创建订单失败",
      );
      console.error("[支付] 创建订单失败:", createResult.message);
      return;
    }

    // 步骤13：订单创建成功，提取支付URL和订单号
    const payUrl = createResult.pay_url;
    const orderId = createResult.order_id;

    // 输出日志：记录订单创建成功
    console.log("[支付] 订单创建成功:", { orderId, hasPayUrl: Boolean(payUrl) });

    // 步骤14：关闭支付弹窗
    closePaymentModal();

    // 步骤15：在新窗口打开支付URL
    // 使用window.open在新标签页打开支付页面，避免离开当前页面
    window.open(payUrl, "_blank");

    // 步骤16：显示支付提示
    // 使用showModalAlert提示用户订单已创建，请在新页面完成支付
    showModalAlert(
      "请在新打开的页面完成支付，支付完成后会自动刷新订单状态",
      "订单已创建",
    );

    // 步骤17：启动订单状态轮询
    // 每3秒查询一次订单状态，最多查询20次（1分钟）
    startOrderPolling(orderId);
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[支付] 创建订单时出错:", error);

    // 显示错误提示
    // 使用showModalAlert显示网络错误信息
    showModalAlert("网络错误，请检查网络连接后重试", "错误");
  }
}

// ========================================
// 查询订单状态函数
// ========================================
/**
 * 查询指定订单的支付状态
 *
 * 功能说明：
 * 1. 调用后端API查询订单状态
 * 2. 返回订单详细信息（状态、金额、时间等）
 *
 * 订单状态说明：
 * - pending: 待支付（用户还未完成支付）
 * - paid: 已支付（支付成功）
 * - closed: 已关闭（订单已取消或超时）
 *
 * @param {string} orderId - 订单号
 * @returns {Promise<Object>} 返回订单信息对象，包含status、order等字段
 */
async function queryOrderStatus(orderId) {
  // 步骤1：参数验证 - 检查订单号是否为空
  if (!orderId) {
    console.error("[支付] 订单号不能为空");
    return { success: false, message: "订单号不能为空" };
  }

  try {
    // 步骤2：调用后端API查询订单状态
    const response = await fetch("/api/payment/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ order_id: orderId }),
    });

    // 步骤3：解析响应数据
    const result = await response.json();

    // 步骤4：输出日志 - 记录查询结果
    console.log("[支付] 查询订单状态:", {
      orderId,
      success: Boolean(result && result.success),
      status: result && result.status,
    });

    // 步骤5：返回查询结果
    return result;
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[支付] 查询订单状态时出错:", error);

    // 返回错误对象
    return { success: false, message: "查询订单状态失败" };
  }
}

// ========================================
// 启动订单状态轮询函数
// ========================================
/**
 * 启动定时轮询，每3秒查询一次订单状态
 *
 * 功能说明：
 * 1. 使用setInterval创建定时器，每3秒执行一次
 * 2. 每次查询订单状态，如果已支付则停止轮询
 * 3. 最多轮询20次（1分钟），超时后自动停止
 *
 * 使用场景：
 * - 用户创建订单后自动启动轮询
 * - 用户在订单列表点击"查询状态"时启动轮询
 *
 * 注意事项：
 * - 同一时间只能有一个订单在轮询
 * - 轮询前会先清除之前的定时器，避免内存泄漏
 *
 * @param {string} orderId - 订单号
 * @returns {void} 无返回值
 */
function startOrderPolling(orderId) {
  // 步骤1：清除之前的定时器（如果存在）
  // 避免多个订单同时轮询，导致资源浪费
  if (paymentPollingTimer) {
    clearInterval(paymentPollingTimer);
    paymentPollingTimer = null;
  }

  // 步骤2：重置轮询计数器
  paymentPollingCount = 0;

  // 输出日志：记录开始轮询
  console.log("[支付] 开始轮询订单状态:", orderId);

  // 步骤3：创建定时器，每3秒执行一次
  paymentPollingTimer = setInterval(async () => {
    // 步骤4：增加轮询计数
    paymentPollingCount++;

    // 输出日志：记录轮询次数
    console.log(`[支付] 第${paymentPollingCount}次查询订单状态:`, orderId);

    // 步骤5：查询订单状态
    const result = await queryOrderStatus(orderId);

    // 步骤6：检查查询结果
    if (result.success) {
      // 查询成功，获取订单状态
      const status = result.status;

      // 步骤7：判断订单状态
      if (status === "paid") {
        // 订单已支付，停止轮询
        clearInterval(paymentPollingTimer);
        paymentPollingTimer = null;

        // 显示支付成功提示
        Swal.fire({
          icon: "success",
          title: "支付成功",
          text: "订单已支付，感谢您的支持！",
          confirmButtonText: "确定",
        });

        // 输出日志
        console.log("[支付] 订单支付成功:", orderId);

        // 刷新订单列表（如果订单列表弹窗是打开的）
        const ordersModal = document.getElementById("orders-modal");
        if (ordersModal && ordersModal.style.display !== "none") {
          loadPaymentOrders(currentOrderStatus, currentOrdersPage);
        }
      } else if (status === "closed") {
        // 订单已关闭，停止轮询
        clearInterval(paymentPollingTimer);
        paymentPollingTimer = null;

        // 显示订单关闭提示
        Swal.fire({
          icon: "info",
          title: "订单已关闭",
          text: "订单已被关闭或取消",
          confirmButtonText: "确定",
        });

        console.log("[支付] 订单已关闭:", orderId);
      }
    }

    // 步骤8：检查是否达到最大轮询次数
    if (paymentPollingCount >= 20) {
      // 达到最大次数（20次 * 3秒 = 1分钟），停止轮询
      clearInterval(paymentPollingTimer);
      paymentPollingTimer = null;

      // 显示超时提示
      Swal.fire({
        icon: "warning",
        title: "查询超时",
        text: '订单状态查询超时，请稍后在"我的订单"中手动查询',
        confirmButtonText: "确定",
      });

      console.log("[支付] 订单状态查询超时:", orderId);
    }
  }, 3000); // 每3秒执行一次
}

// ========================================
// 打开订单列表弹窗函数
// ========================================
/**
 * 打开订单列表弹窗，显示用户的所有订单
 *
 * 功能说明：
 * 1. 显示订单列表弹窗（orders-modal）
 * 2. 重置筛选条件和分页
 * 3. 加载第一页的订单数据
 *
 * 调用时机：
 * - 用户点击个人中心的"我的订单"按钮时
 * - 用户在支付成功后查看订单时
 *
 * @returns {void} 无返回值
 */
function openOrdersModal() {
  // 步骤1：获取订单列表弹窗DOM元素
  const modal = document.getElementById("orders-modal");

  // 步骤2：检查弹窗元素是否存在
  if (!modal) {
    console.error("[支付] 订单列表弹窗元素不存在");
    return;
  }

  // 步骤3：显示订单列表弹窗
  modal.classList.remove("hidden");
  modal.style.display = "flex";

  // 步骤4：重置筛选条件和分页
  currentOrderStatus = "all"; // 重置为显示全部订单
  currentOrdersPage = 1; // 重置为第1页

  // 步骤5：更新筛选按钮的激活状态
  // 获取所有筛选按钮，移除'active'类，只给"全部"按钮添加
  document.querySelectorAll(".orders-filter-btn").forEach((btn) => {
    btn.classList.remove("active", "bg-sky-500", "text-white");
    if (btn.dataset.status === "all") {
      btn.classList.add("active", "bg-sky-500", "text-white");
    }
  });

  // 步骤6：加载第一页的订单数据
  loadPaymentOrders("all", 1);

  // 输出日志
  console.log("[支付] 订单列表弹窗已打开");
}

// ========================================
// 关闭订单列表弹窗函数
// ========================================
/**
 * 关闭订单列表弹窗
 *
 * 功能说明：
 * 1. 隐藏订单列表弹窗
 * 2. 停止订单轮询（如果正在轮询）
 *
 * @returns {void} 无返回值
 */
function closeOrdersModal() {
  // 获取订单列表弹窗DOM元素
  const modal = document.getElementById("orders-modal");

  // 检查元素是否存在
  if (!modal) return;

  // 隐藏弹窗
  modal.classList.add("hidden");
  modal.style.display = "none";

  // 停止订单轮询
  if (paymentPollingTimer) {
    clearInterval(paymentPollingTimer);
    paymentPollingTimer = null;
  }

  // 输出日志
  console.log("[支付] 订单列表弹窗已关闭");
}

// ========================================
// 加载订单列表函数
// ========================================
/**
 * 从后端加载订单列表并渲染到页面
 *
 * 功能说明：
 * 1. 调用后端API获取订单列表
 * 2. 根据筛选条件和分页参数加载数据
 * 3. 渲染订单卡片到页面
 * 4. 更新分页控件状态
 *
 * 参数说明：
 * @param {string} status - 订单状态筛选，可选值：'all'、'pending'、'paid'、'closed'
 * @param {number} page - 页码，从1开始
 *
 * @returns {Promise<void>} 无返回值的Promise
 */
async function loadPaymentOrders(status, page) {
  // 步骤1：更新全局变量
  currentOrderStatus = status;
  currentOrdersPage = page;

  // 步骤2：获取订单列表容器DOM元素
  const container = document.getElementById("orders-list-container");

  // 步骤3：检查容器是否存在
  if (!container) {
    console.error("[支付] 订单列表容器不存在");
    return;
  }

  // 步骤4：显示加载提示
  container.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-sm">加载中...</p>';

  // 输出日志：记录加载参数
  console.log("[支付] 加载订单列表:", { status, page });

  try {
    // 步骤5：构建API请求URL
    // 拼接查询参数：status、page、per_page
    let url = `/api/payment/orders?page=${page}&per_page=${ordersPerPage}`;

    // 如果status不是'all'，添加status参数进行筛选
    if (status !== "all") {
      url += `&status=${status}`;
    }

    // 步骤6：调用后端API获取订单列表
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    // 步骤7：解析响应数据
    const result = await response.json();

    // 步骤8：检查API调用结果
    if (!result.success) {
      // 加载失败，显示错误提示
      container.innerHTML = `<p class="text-red-500 text-center py-10 text-sm">${
        result.message || "加载订单失败"
      }</p>`;
      console.error("[支付] 加载订单失败:", result.message);
      return;
    }

    // 步骤9：获取订单列表数据
    const orders = result.orders || [];
    const total = result.total || 0;
    const totalPages = Math.ceil(total / ordersPerPage);

    // 输出日志：记录加载结果
    console.log("[支付] 订单列表加载成功:", { total, orders: orders.length });

    // 步骤10：检查是否有订单数据
    if (orders.length === 0) {
      // 没有订单，显示空状态提示
      container.innerHTML = `
                <div class="text-center py-10">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-16 h-16 mx-auto text-slate-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                    </svg>
                    <p class="text-slate-400 text-sm">暂无订单</p>
                </div>
            `;
    } else {
      // 步骤11：渲染订单列表
      // 清空容器，准备插入订单卡片
      container.innerHTML = "";

      // 遍历订单数组，为每个订单创建一个卡片
      orders.forEach((order) => {
        // 创建订单卡片HTML
        const orderCard = createOrderCard(order);

        // 插入到容器中
        container.insertAdjacentHTML("beforeend", orderCard);
      });
    }

    // 步骤12：更新分页控件
    updateOrdersPagination(page, totalPages);
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[支付] 加载订单列表时出错:", error);

    // 显示错误提示
    container.innerHTML =
      '<p class="text-red-500 text-center py-10 text-sm">网络错误，请稍后重试</p>';
  }
}

// ========================================
// 创建订单卡片HTML函数
// ========================================
/**
 * 根据订单数据生成订单卡片的HTML字符串
 *
 * 功能说明：
 * 1. 根据订单状态选择不同的样式颜色
 * 2. 格式化订单信息（金额、时间等）
 * 3. 根据订单状态显示不同的操作按钮
 *
 * @param {Object} order - 订单对象，包含order_id、amount、status等字段
 * @returns {string} 返回订单卡片的HTML字符串
 */
function createOrderCard(order) {
  // 步骤1：根据订单状态选择样式颜色和显示文本
  let statusConfig = {};

  switch (order.status) {
    case "pending":
      statusConfig = {
        text: "待支付",
        color: "amber",
        bgColor: "bg-amber-50",
        borderColor: "border-amber-200",
        textColor: "text-amber-700",
      };
      break;
    case "paid":
      statusConfig = {
        text: "已支付",
        color: "green",
        bgColor: "bg-green-50",
        borderColor: "border-green-200",
        textColor: "text-green-700",
      };
      break;
    case "closed":
      statusConfig = {
        text: "已关闭",
        color: "slate",
        bgColor: "bg-slate-50",
        borderColor: "border-slate-200",
        textColor: "text-slate-700",
      };
      break;
    default:
      statusConfig = {
        text: "未知",
        color: "slate",
        bgColor: "bg-slate-50",
        borderColor: "border-slate-200",
        textColor: "text-slate-700",
      };
  }

  // 步骤2：格式化支付方式显示文本
  let payTypeText = "";
  switch (order.pay_type) {
    case "alipay":
      payTypeText = "支付宝";
      break;
    case "wxpay":
      payTypeText = "微信支付";
      break;
    case "bank":
      payTypeText = "网银支付";
      break;
    default:
      payTypeText = order.pay_type || "未知";
  }

  // 步骤3：格式化创建时间
  // 将ISO格式的时间转换为易读格式（如：2024-12-10 10:30:45）
  const createTime = new Date(order.create_time).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  // 步骤4：生成操作按钮HTML
  let actionButtons = "";

  if (order.status === "pending") {
    // 待支付订单：显示"继续支付"和"查询状态"按钮
    actionButtons = `
            <button onclick="continuePay(${escapeInlineJsArg(order.order_id)})"
                class="flex-1 py-2 px-3 bg-sky-500 text-white rounded-lg text-xs font-medium hover:bg-sky-600 transition">
                继续支付
            </button>
            <button onclick="refreshOrderStatus(${escapeInlineJsArg(order.order_id)})"
                class="flex-1 py-2 px-3 bg-slate-100 text-slate-700 rounded-lg text-xs font-medium hover:bg-slate-200 transition">
                查询状态
            </button>
        `;
  } else {
    // 已支付或已关闭订单：只显示"查询状态"按钮
    actionButtons = `
            <button onclick="refreshOrderStatus(${escapeInlineJsArg(order.order_id)})"
                class="w-full py-2 px-3 bg-slate-100 text-slate-700 rounded-lg text-xs font-medium hover:bg-slate-200 transition">
                查询状态
            </button>
        `;
  }

  // 步骤5：拼接完整的订单卡片HTML
  // 使用模板字符串，支持变量插值和换行
  return `
        <div class="border-2 ${statusConfig.borderColor} ${
          statusConfig.bgColor
        } rounded-xl p-4 space-y-3">
            <!-- 订单头部：订单号和状态 -->
            <div class="flex justify-between items-start">
                <!-- 订单号：使用等宽字体显示，便于复制 -->
                <div>
                    <p class="text-xs text-slate-500">订单号</p>
                    <p class="text-sm font-mono font-semibold text-slate-800">${
                      order.order_id
                    }</p>
                </div>
                <!-- 订单状态徽章 -->
                <span class="px-3 py-1 ${statusConfig.bgColor} ${
                  statusConfig.textColor
                } rounded-full text-xs font-semibold border ${statusConfig.borderColor}">
                    ${statusConfig.text}
                </span>
            </div>
            
            <!-- 订单详情：金额、支付方式、商品名称 -->
            <div class="space-y-2 text-sm">
                <!-- 支付金额：突出显示，使用大号字体 -->
                <div class="flex justify-between">
                    <span class="text-slate-600">支付金额</span>
                    <span class="font-bold text-lg text-sky-600">¥${parseFloat(
                      order.amount,
                    ).toFixed(2)}</span>
                </div>
                <!-- 支付方式 -->
                <div class="flex justify-between">
                    <span class="text-slate-600">支付方式</span>
                    <span class="text-slate-800">${payTypeText}</span>
                </div>
                <!-- 商品名称 -->
                <div class="flex justify-between">
                    <span class="text-slate-600">商品名称</span>
                    <span class="text-slate-800">${
                      order.product_name || "在线支付"
                    }</span>
                </div>
                <!-- 创建时间 -->
                <div class="flex justify-between">
                    <span class="text-slate-600">创建时间</span>
                    <span class="text-slate-500 text-xs">${createTime}</span>
                </div>
            </div>
            
            <!-- 操作按钮区域 -->
            <div class="flex gap-2 pt-2 border-t border-slate-200">
                ${actionButtons}
            </div>
        </div>
    `;
}

// ========================================
// 更新订单列表分页控件函数
// ========================================
/**
 * 更新订单列表的分页控件状态
 *
 * 功能说明：
 * 1. 更新页码显示
 * 2. 更新"上一页"/"下一页"按钮的禁用状态
 *
 * @param {number} currentPage - 当前页码
 * @param {number} totalPages - 总页数
 * @returns {void} 无返回值
 */
function updateOrdersPagination(currentPage, totalPages) {
  // 步骤1：获取分页控件DOM元素
  const pageInfo = document.getElementById("orders-page-info");
  const prevBtn = document.getElementById("orders-prev-btn");
  const nextBtn = document.getElementById("orders-next-btn");

  // 步骤2：更新页码显示
  if (pageInfo) {
    pageInfo.textContent = `第 ${currentPage} / ${totalPages} 页`;
  }

  // 步骤3：更新"上一页"按钮状态
  if (prevBtn) {
    // 如果当前是第1页，禁用"上一页"按钮
    if (currentPage <= 1) {
      prevBtn.disabled = true;
      prevBtn.classList.add("opacity-50", "cursor-not-allowed");
    } else {
      prevBtn.disabled = false;
      prevBtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }

  // 步骤4：更新"下一页"按钮状态
  if (nextBtn) {
    // 如果当前是最后一页，禁用"下一页"按钮
    if (currentPage >= totalPages) {
      nextBtn.disabled = true;
      nextBtn.classList.add("opacity-50", "cursor-not-allowed");
    } else {
      nextBtn.disabled = false;
      nextBtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }
}

// ========================================
// 继续支付函数
// ========================================
/**
 * 继续支付未完成的订单
 *
 * 功能说明：
 * 1. 查询订单详情获取支付URL
 * 2. 在新窗口打开支付页面
 * 3. 启动订单状态轮询
 *
 * @param {string} orderId - 订单号
 * @returns {Promise<void>} 无返回值的Promise
 */
async function continuePay(orderId) {
  try {
    // 步骤1：查询订单详情
    const result = await queryOrderStatus(orderId);

    // 步骤2：检查查询结果
    if (!result.success) {
      Swal.fire({
        icon: "error",
        title: "错误",
        text: result.message || "查询订单失败",
        confirmButtonText: "确定",
      });
      return;
    }

    // 步骤3：检查订单状态
    if (result.status !== "pending") {
      Swal.fire({
        icon: "info",
        title: "提示",
        text: "该订单不是待支付状态",
        confirmButtonText: "确定",
      });
      return;
    }

    // 步骤4：获取支付URL
    const payUrl = result.order.pay_url;

    // 步骤5：在新窗口打开支付页面
    window.open(payUrl, "_blank");

    // 步骤6：启动订单状态轮询
    startOrderPolling(orderId);

    // 步骤7：显示提示
    Swal.fire({
      icon: "info",
      title: "提示",
      text: "请在新打开的页面完成支付",
      confirmButtonText: "确定",
      timer: 2000,
    });
  } catch (error) {
    console.error("[支付] 继续支付时出错:", error);
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "操作失败，请稍后重试",
      confirmButtonText: "确定",
    });
  }
}

// ========================================
// 刷新订单状态函数
// ========================================
/**
 * 手动刷新订单状态
 *
 * 功能说明：
 * 1. 查询最新的订单状态
 * 2. 更新订单列表显示
 * 3. 显示查询结果提示
 *
 * @param {string} orderId - 订单号
 * @returns {Promise<void>} 无返回值的Promise
 */
async function refreshOrderStatus(orderId) {
  try {
    // 显示加载提示
    Swal.fire({
      title: "查询中...",
      text: "正在查询订单状态",
      allowOutsideClick: false,
      didOpen: () => {
        Swal.showLoading();
      },
    });

    // 步骤1：查询订单状态
    const result = await queryOrderStatus(orderId);

    // 步骤2：关闭加载提示
    Swal.close();

    // 步骤3：检查查询结果
    if (!result.success) {
      Swal.fire({
        icon: "error",
        title: "查询失败",
        text: result.message || "查询订单状态失败",
        confirmButtonText: "确定",
      });
      return;
    }

    // 步骤4：显示查询结果
    let statusText = "";
    let icon = "info";

    switch (result.status) {
      case "paid":
        statusText = "订单已支付";
        icon = "success";
        break;
      case "pending":
        statusText = "订单待支付";
        icon = "info";
        break;
      case "closed":
        statusText = "订单已关闭";
        icon = "warning";
        break;
      default:
        statusText = "订单状态未知";
        icon = "question";
    }

    Swal.fire({
      icon: icon,
      title: statusText,
      text: `订单号：${orderId}`,
      confirmButtonText: "确定",
    });

    // 步骤5：重新加载订单列表
    loadPaymentOrders(currentOrderStatus, currentOrdersPage);
  } catch (error) {
    Swal.close();
    console.error("[支付] 刷新订单状态时出错:", error);
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "查询失败，请稍后重试",
      confirmButtonText: "确定",
    });
  }
}

// ========================================
// 事件监听器绑定区域
// ========================================
// 在DOM加载完成后绑定所有事件监听器
document.addEventListener("DOMContentLoaded", function () {
  // ========== 支付弹窗相关事件 ==========

  // 绑定支付弹窗关闭按钮点击事件
  const paymentCloseBtn = document.getElementById("payment-close-btn");
  if (paymentCloseBtn) {
    paymentCloseBtn.addEventListener("click", closePaymentModal);
  }

  // 绑定支付弹窗取消按钮点击事件
  const paymentCancelBtn = document.getElementById("payment-cancel-btn");
  if (paymentCancelBtn) {
    paymentCancelBtn.addEventListener("click", closePaymentModal);
  }

  // 绑定支付弹窗提交按钮点击事件
  const paymentSubmitBtn = document.getElementById("payment-submit-btn");
  if (paymentSubmitBtn) {
    paymentSubmitBtn.addEventListener("click", createPaymentOrder);
  }

  // 绑定支付弹窗背景点击事件（点击弹窗外部关闭）
  const paymentModal = document.getElementById("payment-modal");
  if (paymentModal) {
    paymentModal.addEventListener("click", function (e) {
      // 只有点击背景（modal本身）时才关闭，点击内容区域不关闭
      if (e.target === paymentModal) {
        closePaymentModal();
      }
    });
  }

  // ========== 订单列表弹窗相关事件 ==========

  // 绑定订单列表弹窗关闭按钮点击事件
  const ordersCloseBtn = document.getElementById("orders-close-btn");
  if (ordersCloseBtn) {
    ordersCloseBtn.addEventListener("click", closeOrdersModal);
  }

  // 绑定订单列表弹窗刷新按钮点击事件
  const ordersRefreshBtn = document.getElementById("orders-refresh-btn");
  if (ordersRefreshBtn) {
    ordersRefreshBtn.addEventListener("click", function () {
      // 重新加载当前页的订单列表
      loadPaymentOrders(currentOrderStatus, currentOrdersPage);
    });
  }

  // 绑定订单列表弹窗背景点击事件
  const ordersModal = document.getElementById("orders-modal");
  if (ordersModal) {
    ordersModal.addEventListener("click", function (e) {
      if (e.target === ordersModal) {
        closeOrdersModal();
      }
    });
  }

  // ========== 订单状态筛选按钮事件 ==========

  // 获取所有筛选按钮并绑定点击事件
  document.querySelectorAll(".orders-filter-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      // 获取点击按钮的状态值
      const status = this.dataset.status;

      // 更新所有按钮的激活状态
      document.querySelectorAll(".orders-filter-btn").forEach((b) => {
        b.classList.remove("active", "bg-sky-500", "text-white");
      });

      // 给当前按钮添加激活样式
      this.classList.add("active", "bg-sky-500", "text-white");

      // 重新加载订单列表（第1页）
      loadPaymentOrders(status, 1);
    });
  });

  // ========== 订单列表分页按钮事件 ==========

  // 绑定"上一页"按钮点击事件
  const ordersPrevBtn = document.getElementById("orders-prev-btn");
  if (ordersPrevBtn) {
    ordersPrevBtn.addEventListener("click", function () {
      // 检查是否已经是第1页
      if (currentOrdersPage > 1) {
        // 加载上一页
        loadPaymentOrders(currentOrderStatus, currentOrdersPage - 1);
      }
    });
  }

  // 绑定"下一页"按钮点击事件
  const ordersNextBtn = document.getElementById("orders-next-btn");
  if (ordersNextBtn) {
    ordersNextBtn.addEventListener("click", function () {
      // 加载下一页
      loadPaymentOrders(currentOrderStatus, currentOrdersPage + 1);
    });
  }

  // 输出日志：记录事件绑定完成
  console.log("[支付] 支付系统事件监听器已绑定");
});

// ============================================================================
// 彩虹易支付系统 - 管理员功能实现
// ============================================================================
// 本模块实现管理员专用的支付管理功能
// 包括：支付配置管理、支付日志查看等
// ============================================================================

// ========================================
// 支付日志分页全局变量
// ========================================

// 支付日志当前页码
let currentPaymentLogsPage = 1;

// 支付日志每页显示数量
let paymentLogsPerPage = 20;

// ========================================
// 加载支付配置函数（管理员）
// ========================================
/**
 * 从后端加载当前的支付配置并显示到管理面板
 *
 * 功能说明：
 * 1. 调用后端API获取当前启用的支付方式
 * 2. 更新复选框的选中状态
 * 3. 隐藏加载提示，显示配置内容
 *
 * 调用时机：
 * - 管理员首次打开支付配置面板时
 * - 管理员点击"刷新"按钮时
 *
 * @returns {Promise<void>} 无返回值的Promise
 */
async function loadPaymentConfig() {
  // 输出日志：记录开始加载配置
  console.log("[管理员-支付配置] 开始加载支付配置");

  try {
    // 步骤1：调用后端API获取支付配置
    const response = await fetch("/api/admin/payment/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    // 步骤2：解析响应数据
    const result = await response.json();

    // 步骤3：检查API调用结果
    if (!result.success) {
      // 加载失败，显示错误提示
      Swal.fire({
        icon: "error",
        title: "加载失败",
        text: result.message || "无法加载支付配置",
        confirmButtonText: "确定",
      });
      console.error("[管理员-支付配置] 加载失败:", result.message);
      return;
    }

    // 步骤4：获取启用的支付方式列表
    // 例如：["alipay", "wxpay"]
    const enabledMethods = result.enabled_payment_methods || [];

    // 输出日志：记录当前启用的支付方式
    console.log("[管理员-支付配置] 当前启用的支付方式:", enabledMethods);

    // 步骤5：动态生成支付方式配置复选框
    // 获取配置内容容器
    const configContent = document.getElementById(
      "mobile-multi-admin-payment-config-content",
    );

    // 检查容器是否存在
    if (!configContent) {
      console.error("[管理员-支付配置] 配置容器元素不存在");
      return;
    }

    // 5.1 生成支付方式复选框HTML
    // 创建一个HTML字符串，包含所有支付方式的复选框
    let checkboxesHTML = `
            <!-- 提示信息卡片 -->
            <div class="bg-sky-50 border border-sky-200 rounded-lg p-3">
                <p class="text-xs text-sky-700">
                    <strong>提示：</strong>请至少启用一种支付方式。修改后立即生效，无需重启服务。
                </p>
            </div>

            <!-- 支付方式选择区域 -->
            <div class="space-y-3">
                <!-- 支付方式标题 -->
                <h5 class="text-sm font-semibold text-slate-700">启用的支付方式</h5>
        `;

    // 5.2 遍历全局配置对象(PAYMENT_METHODS)，为每个支付方式创建复选框
    // 使用Object.entries()获取所有的键值对
    Object.entries(PAYMENT_METHODS).forEach(([methodCode, methodConfig]) => {
      // methodCode: 支付方式代码，如 'alipay'
      // methodConfig: 支付方式配置对象，包含 name、icon、svg、borderColor、textColor、description

      // 检查当前支付方式是否在启用列表中
      const isChecked = enabledMethods.includes(methodCode);

      // 根据图标类型生成图标HTML
      // 如果icon字段为'svg'，使用svg字段的SVG代码
      // 否则使用icon字段作为emoji图标
      const iconHtml =
        methodConfig.icon === "svg"
          ? methodConfig.svg // 直接使用SVG代码（已包含样式类）
          : `<span class="text-xl">${methodConfig.icon}</span>`; // emoji图标，包裹在span中

      // 生成复选框HTML
      // 每个复选框包含：图标（SVG或emoji）、名称、描述
      checkboxesHTML += `
                <label class="flex items-center p-3 bg-white border-2 border-slate-200 rounded-lg cursor-pointer ${
                  methodConfig.borderColor
                } transition-colors">
                    <!-- 复选框输入元素 -->
                    <input type="checkbox" 
                           id="payment-method-${methodCode}" 
                           value="${methodCode}" 
                           class="w-4 h-4 ${methodConfig.textColor} rounded" 
                           ${isChecked ? "checked" : ""} />
                    
                    <!-- 支付方式图标：SVG或emoji，根据配置动态生成 -->
                    <span class="ml-3 flex items-center">
                        ${iconHtml}
                    </span>
                    
                    <!-- 支付方式信息：名称和描述 -->
                    <div class="ml-2 flex-1">
                        <span class="text-sm font-medium text-slate-800">${
                          methodConfig.name
                        }</span>
                        <p class="text-xs text-slate-500 mt-0.5">${
                          methodConfig.description
                        }</p>
                    </div>
                </label>
            `;
    });

    // 5.3 添加保存按钮和加载提示
    checkboxesHTML += `
            </div>

            <!-- 保存按钮 -->
            <button id="save-payment-config-btn" 
                class="w-full py-2.5 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 active:bg-sky-700 transition">
                保存配置
            </button>

            <!-- 加载提示（初始显示） -->
            <div id="payment-config-loading" class="hidden text-center py-4">
                <p class="text-sm text-slate-500">加载中...</p>
            </div>
        `;

    // 5.4 将生成的HTML插入到配置容器中
    configContent.innerHTML = checkboxesHTML;

    // 5.5 重新绑定保存按钮的点击事件
    // 因为innerHTML会替换所有内容，之前绑定的事件会失效
    const saveBtn = document.getElementById("save-payment-config-btn");
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        // 调用保存配置函数
        savePaymentConfig();
      });
    }

    // 步骤6：隐藏加载提示（如果存在的话）
    const loadingElement = document.getElementById("payment-config-loading");
    if (loadingElement) {
      loadingElement.style.display = "none";
    }
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[管理员-支付配置] 加载时出错:", error);

    // 显示错误提示
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "网络错误，请稍后重试",
      confirmButtonText: "确定",
    });
  }
}

// ========================================
// 保存支付配置函数（管理员）
// ========================================
/**
 * 将管理员修改的支付配置保存到后端
 *
 * 功能说明：
 * 1. 收集复选框的选中状态
 * 2. 验证至少启用了一种支付方式
 * 3. 调用后端API更新配置
 * 4. 显示保存结果提示
 *
 * 调用时机：
 * - 管理员点击"保存配置"按钮时
 *
 * @returns {Promise<void>} 无返回值的Promise
 */
async function savePaymentConfig() {
  // 输出日志：记录开始保存配置
  console.log("[管理员-支付配置] 开始保存支付配置");

  try {
    // 步骤1：动态收集所有支付方式复选框的选中状态
    const enabledMethods = [];

    // 遍历全局配置对象(PAYMENT_METHODS)，检查每个支付方式的复选框
    // 使用Object.keys()获取所有支付方式代码
    Object.keys(PAYMENT_METHODS).forEach((methodCode) => {
      // 根据支付方式代码获取对应的复选框元素
      // 元素ID格式: payment-method-{code}，例如 payment-method-alipay
      const checkbox = document.getElementById(`payment-method-${methodCode}`);

      // 检查复选框是否存在且已勾选
      if (checkbox && checkbox.checked) {
        // 将选中的支付方式代码添加到数组中
        enabledMethods.push(methodCode);
      }
    });

    // 步骤2：验证至少选择了一种支付方式
    if (enabledMethods.length === 0) {
      // 没有选择任何支付方式，显示警告
      Swal.fire({
        icon: "warning",
        title: "提示",
        text: "请至少启用一种支付方式",
        confirmButtonText: "确定",
      });
      return;
    }

    // 步骤3：将数组转换为逗号分隔的字符串
    // 例如：["alipay", "wxpay"] -> "alipay,wxpay"
    const enabledMethodsStr = enabledMethods.join(",");

    // 输出日志：记录即将保存的配置
    console.log("[管理员-支付配置] 即将保存的配置:", enabledMethodsStr);

    // 步骤4：调用后端API更新配置
    const response = await fetch("/api/admin/payment/config", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        enabled_payment_methods: enabledMethodsStr,
      }),
    });

    // 步骤5：解析响应数据
    const result = await response.json();

    // 步骤6：检查保存结果
    if (result.success) {
      // 保存成功，显示成功提示
      Swal.fire({
        icon: "success",
        title: "保存成功",
        text: "支付配置已更新，立即生效",
        confirmButtonText: "确定",
        timer: 2000,
      });

      // 输出日志：记录保存成功
      console.log("[管理员-支付配置] 保存成功");
    } else {
      // 保存失败，显示错误提示
      Swal.fire({
        icon: "error",
        title: "保存失败",
        text: result.message || "无法保存支付配置",
        confirmButtonText: "确定",
      });

      // 输出错误日志
      console.error("[管理员-支付配置] 保存失败:", result.message);
    }
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[管理员-支付配置] 保存时出错:", error);

    // 显示错误提示
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "网络错误，请稍后重试",
      confirmButtonText: "确定",
    });
  }
}

// ========================================
// 加载支付日志函数（管理员）
// ========================================
/**
 * 从后端加载支付日志列表并渲染到管理面板
 *
 * 功能说明：
 * 1. 收集筛选条件（用户ID、操作类型、日期范围）
 * 2. 调用后端API获取日志数据
 * 3. 渲染日志列表到页面
 * 4. 更新分页控件状态
 *
 * 参数说明：
 * @param {number} page - 页码，从1开始
 *
 * @returns {Promise<void>} 无返回值的Promise
 */
async function loadPaymentLogs(page) {
  // 步骤1：更新全局页码变量
  currentPaymentLogsPage = page;

  // 步骤2：获取日志列表容器DOM元素
  const container = document.getElementById(
    "mobile-multi-admin-payment-logs-list",
  );

  // 步骤3：检查容器是否存在
  if (!container) {
    console.error("[管理员-支付日志] 日志列表容器不存在");
    return;
  }

  // 步骤4：显示加载提示
  container.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  // 步骤5：收集筛选条件
  // 获取用户ID输入框的值
  const userId =
    document.getElementById("payment-logs-user-id")?.value.trim() || "";

  // 获取操作类型下拉框的值
  const actionType =
    document.getElementById("payment-logs-action-type")?.value || "";

  // 获取开始日期输入框的值
  const startDate =
    document.getElementById("payment-logs-start-date")?.value || "";

  // 获取结束日期输入框的值
  const endDate = document.getElementById("payment-logs-end-date")?.value || "";

  // 输出日志：记录筛选条件
  console.log("[管理员-支付日志] 筛选条件:", {
    userId,
    actionType,
    startDate,
    endDate,
    page,
  });

  try {
    // 步骤6：构建API请求URL
    // 基础URL包含页码和每页数量
    let url = `/api/admin/payment_logs?page=${page}&per_page=${paymentLogsPerPage}`;

    // 如果有用户ID筛选条件，添加到URL
    if (userId) {
      url += `&user_id=${encodeURIComponent(userId)}`;
    }

    // 如果有操作类型筛选条件，添加到URL
    if (actionType) {
      url += `&action_type=${encodeURIComponent(actionType)}`;
    }

    // 如果有开始日期筛选条件，添加到URL
    if (startDate) {
      url += `&start_date=${encodeURIComponent(startDate)}`;
    }

    // 如果有结束日期筛选条件，添加到URL
    if (endDate) {
      url += `&end_date=${encodeURIComponent(endDate)}`;
    }

    // 步骤7：调用后端API获取日志列表
    // 添加X-Session-ID请求头，用于后端身份验证
    // sessionUUID是全局会话标识符，在用户登录时由服务器生成并存储在客户端
    // 后端通过此header验证请求的合法性，防止未授权访问
    const response = await fetch(url, {
      method: "GET", // 明确指定HTTP方法为GET
      headers: {
        "X-Session-ID": sessionUUID, // 添加会话ID用于身份验证
      },
    });

    // 步骤8：检查HTTP状态码
    // 在尝试解析响应数据之前，首先验证HTTP请求是否成功
    // 这样可以更准确地捕获和处理各种HTTP错误（401未授权、403禁止访问、404未找到、500服务器错误等）
    if (!response.ok) {
      // HTTP错误（401, 403, 404, 500等）
      // 首先尝试读取响应体文本，它可能包含详细的错误信息
      const errorText = await response.text();
      // 初始化错误消息，默认显示HTTP状态码
      let errorMessage = `HTTP错误: ${response.status}`;

      try {
        // 尝试将错误文本解析为JSON对象
        // 如果后端返回的是结构化的错误信息，我们可以提取message字段
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.message || errorMessage;
      } catch (e) {
        // 解析失败，使用状态码文本
        // 这种情况下，后端可能返回的是纯文本或HTML错误页面
      }

      // 根据状态码显示不同的错误提示
      // 这样可以为用户提供更友好、更具体的错误说明
      if (response.status === 401) {
        // 401 Unauthorized: 用户未登录或会话已过期
        errorMessage = "未登录或会话已过期，请重新登录";
      } else if (response.status === 403) {
        // 403 Forbidden: 用户已登录但没有足够的权限访问此资源
        errorMessage = "权限不足，需要审计日志查看权限";
      }

      // 在页面上显示错误消息
      // 使用红色文本和居中对齐，确保用户能够清楚地看到错误提示
      container.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">${errorMessage}</p>`;

      // 在控制台记录详细的错误信息，方便开发人员调试
      console.error("[管理员-支付日志] HTTP错误:", {
        status: response.status,
        message: errorMessage,
      });
      return; // 提前返回，不再继续处理
    }

    // 步骤9：解析响应数据（修改原来的步骤8）
    // 只有在HTTP请求成功（status 200-299）时，才会执行到这里
    const result = await response.json();

    // 步骤10：检查API调用结果（修改原来的步骤9）
    // 即使HTTP请求成功（200 OK），API调用本身也可能失败
    // 例如：后端业务逻辑检测到错误、数据库查询失败等
    if (!result.success) {
      // 加载失败，显示错误提示
      // result.message包含后端返回的具体错误信息
      container.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">${
        result.message || "加载日志失败"
      }</p>`;
      console.error("[管理员-支付日志] 加载失败:", result.message);
      return; // 提前返回，不再继续处理
    }

    // 步骤11：获取日志列表数据（修改原来的步骤10）
    const logs = result.logs || [];
    const total = result.total || 0;
    const totalPages = Math.ceil(total / paymentLogsPerPage);

    // 输出日志：记录加载结果
    console.log("[管理员-支付日志] 日志列表加载成功:", {
      total,
      logs: logs.length,
    });

    // 步骤12：检查是否有日志数据（修改原来的步骤11）
    if (logs.length === 0) {
      // 没有日志，显示空状态提示
      container.innerHTML = `
                <div class="text-center py-10">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 mx-auto text-slate-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <p class="text-slate-400 text-xs">暂无日志记录</p>
                </div>
            `;
    } else {
      // 步骤13：渲染日志列表（修改原来的步骤12）
      // 清空容器，准备插入日志卡片
      container.innerHTML = "";

      // 遍历日志数组，为每条日志创建一个卡片
      logs.forEach((log) => {
        // 创建日志卡片HTML
        const logCard = createPaymentLogCard(log);

        // 插入到容器中
        container.insertAdjacentHTML("beforeend", logCard);
      });
    }

    // 步骤13：更新分页控件
    updatePaymentLogsPagination(page, totalPages);
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[管理员-支付日志] 加载时出错:", error);

    // 显示错误提示
    container.innerHTML =
      '<p class="text-red-500 text-center py-10 text-xs">网络错误，请稍后重试</p>';
  }
}

// ========================================
// 创建支付日志卡片HTML函数
// ========================================
/**
 * 根据日志数据生成日志卡片的HTML字符串
 *
 * 功能说明：
 * 1. 根据操作类型选择不同的样式颜色
 * 2. 格式化日志信息（时间、数据等）
 * 3. 将JSON数据格式化显示
 *
 * @param {Object} log - 日志对象，包含user_id、action、log_data等字段
 * @returns {string} 返回日志卡片的HTML字符串
 */
function createPaymentLogCard(log) {
  let actionConfig = {};

  switch (log.action) {
    case "create_order":
      actionConfig = {
        text: "创建订单",
        bgClass: "bg-blue-50",
        borderClass: "border-blue-200",
        badgeClass: "bg-blue-100 text-blue-700 border-blue-200",
        valueClass: "text-blue-700",
        buttonClass: "bg-blue-500 hover:bg-blue-600",
      };
      break;
    case "query_order":
      actionConfig = {
        text: "查询订单",
        bgClass: "bg-purple-50",
        borderClass: "border-purple-200",
        badgeClass: "bg-purple-100 text-purple-700 border-purple-200",
        valueClass: "text-purple-700",
        buttonClass: "bg-purple-500 hover:bg-purple-600",
      };
      break;
    case "payment_success":
      actionConfig = {
        text: "支付成功",
        bgClass: "bg-emerald-50",
        borderClass: "border-emerald-200",
        badgeClass: "bg-emerald-100 text-emerald-700 border-emerald-200",
        valueClass: "text-emerald-700",
        buttonClass: "bg-emerald-500 hover:bg-emerald-600",
      };
      break;
    case "payment_fail":
      actionConfig = {
        text: "支付失败",
        bgClass: "bg-red-50",
        borderClass: "border-red-200",
        badgeClass: "bg-red-100 text-red-700 border-red-200",
        valueClass: "text-red-700",
        buttonClass: "bg-red-500 hover:bg-red-600",
      };
      break;
    case "config_update":
      actionConfig = {
        text: "配置更新",
        bgClass: "bg-amber-50",
        borderClass: "border-amber-200",
        badgeClass: "bg-amber-100 text-amber-700 border-amber-200",
        valueClass: "text-amber-700",
        buttonClass: "bg-amber-500 hover:bg-amber-600",
      };
      break;
    default:
      actionConfig = {
        text: getPaymentLogActionLabel(log.action),
        bgClass: "bg-slate-50",
        borderClass: "border-slate-200",
        badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
        valueClass: "text-slate-700",
        buttonClass: "bg-slate-600 hover:bg-slate-700",
      };
  }

  const createTime = new Date(log.create_time).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  let logDataHTML = "";
  if (log.log_data) {
    try {
      const logDataObj =
        typeof log.log_data === "string"
          ? JSON.parse(log.log_data)
          : log.log_data;
      const logDataStr = JSON.stringify(logDataObj, null, 2);
      logDataHTML = `
                <div class="rounded-2xl border border-slate-200 bg-white px-3 py-3">
                    <div class="mb-2 text-[11px] font-medium text-slate-500">详细数据</div>
                    <pre class="text-xs leading-5 text-slate-700 overflow-x-auto font-mono whitespace-pre-wrap break-all">${logDataStr}</pre>
                </div>
            `;
    } catch (e) {
      logDataHTML = `
                <div class="rounded-2xl border border-slate-200 bg-white px-3 py-3">
                    <div class="mb-2 text-[11px] font-medium text-slate-500">详细数据</div>
                    <div class="text-xs leading-5 text-slate-700 break-all">${log.log_data}</div>
                </div>
            `;
    }
  }

  const safeLogId = escapeInlineJsArg(log.log_id || "");
  const amountText =
    log.amount !== undefined && log.amount !== null && log.amount !== ""
      ? `¥${parseFloat(log.amount).toFixed(2)}`
      : "-";
  const statusText = getPaymentLogStatusLabel(log.status);
  const detailButton = log.log_id
    ? `
            <button onclick="showPaymentLogDetail(${safeLogId})" class="w-full min-h-[44px] rounded-2xl px-4 py-3 text-sm font-medium text-white transition-colors ${actionConfig.buttonClass}">
                查看详情
            </button>
        `
    : "";

  const detailRows = [
    { label: "订单号", value: log.order_id || "未关联订单", valueClass: "text-slate-800" },
    { label: "用户ID", value: log.user_id || "系统", valueClass: "text-slate-800" },
    { label: "状态", value: statusText, valueClass: actionConfig.valueClass },
    { label: "金额", value: amountText, valueClass: "text-slate-900 font-semibold" },
    { label: "记录时间", value: createTime, valueClass: "text-slate-700" },
    { label: "日志ID", value: log.log_id || "-", valueClass: "text-slate-500 font-mono text-[11px]" },
  ];

  const detailRowsHTML = detailRows
    .map(
      (item) => `
            <div class="rounded-2xl border border-slate-200 bg-white px-3 py-3">
                <div class="text-[11px] font-medium text-slate-400">${item.label}</div>
                <div class="mt-1 text-sm break-all ${item.valueClass}">${item.value}</div>
            </div>
        `,
    )
    .join("");

  return `
        <div class="rounded-3xl border ${actionConfig.borderClass} ${actionConfig.bgClass} p-4 shadow-sm space-y-3">
            <div class="flex items-center justify-between gap-3">
                <span class="inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${actionConfig.badgeClass}">
                    ${actionConfig.text}
                </span>
            </div>

            <div class="space-y-2">
                ${detailRowsHTML}
            </div>

            ${logDataHTML}

            ${detailButton}
        </div>
    `;
}

// ========================================
// 更新支付日志分页控件函数
// ========================================
/**
 * 更新支付日志的分页控件状态
 *
 * 功能说明：
 * 1. 更新页码显示
 * 2. 更新"上一页"/"下一页"按钮的禁用状态
 *
 * @param {number} currentPage - 当前页码
 * @param {number} totalPages - 总页数
 * @returns {void} 无返回值
 */
function updatePaymentLogsPagination(currentPage, totalPages) {
  // 步骤1：获取分页控件DOM元素
  const pageInfo = document.getElementById("payment-logs-page-info");
  const prevBtn = document.getElementById("payment-logs-prev-btn");
  const nextBtn = document.getElementById("payment-logs-next-btn");

  // 步骤2：更新页码显示
  if (pageInfo) {
    pageInfo.textContent = `第 ${currentPage} / ${totalPages} 页`;
  }

  // 步骤3：更新"上一页"按钮状态
  if (prevBtn) {
    // 如果当前是第1页，禁用"上一页"按钮
    if (currentPage <= 1) {
      prevBtn.disabled = true;
      prevBtn.classList.add("opacity-50", "cursor-not-allowed");
    } else {
      prevBtn.disabled = false;
      prevBtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }

  // 步骤4：更新"下一页"按钮状态
  if (nextBtn) {
    // 如果当前是最后一页，禁用"下一页"按钮
    if (currentPage >= totalPages) {
      nextBtn.disabled = true;
      nextBtn.classList.add("opacity-50", "cursor-not-allowed");
    } else {
      nextBtn.disabled = false;
      nextBtn.classList.remove("opacity-50", "cursor-not-allowed");
    }
  }
}

// ========================================
// 管理员事件监听器绑定区域
// ========================================
// 在DOM加载完成后绑定管理员相关的事件监听器
document.addEventListener("DOMContentLoaded", function () {
  // ========== 支付配置面板相关事件 ==========

  // 绑定刷新支付配置按钮点击事件
  const refreshPaymentConfigBtn = document.getElementById(
    "mobile-multi-admin-refresh-payment-config",
  );
  if (refreshPaymentConfigBtn) {
    refreshPaymentConfigBtn.addEventListener("click", function () {
      // 重新加载支付配置
      loadPaymentConfig();
    });
  }

  // 绑定保存支付配置按钮点击事件
  const savePaymentConfigBtn = document.getElementById(
    "save-payment-config-btn",
  );
  if (savePaymentConfigBtn) {
    savePaymentConfigBtn.addEventListener("click", function () {
      // 保存支付配置
      savePaymentConfig();
    });
  }

  // ========== 支付日志面板相关事件 ==========

  // 绑定刷新支付日志按钮点击事件
  const refreshPaymentLogsBtn = document.getElementById(
    "mobile-multi-admin-refresh-payment-logs",
  );
  if (refreshPaymentLogsBtn) {
    refreshPaymentLogsBtn.addEventListener("click", function () {
      // 重新加载当前页的支付日志
      loadPaymentLogs(currentPaymentLogsPage);
    });
  }

  // 绑定查询支付日志按钮点击事件
  const searchPaymentLogsBtn = document.getElementById(
    "search-payment-logs-btn",
  );
  if (searchPaymentLogsBtn) {
    searchPaymentLogsBtn.addEventListener("click", function () {
      // 使用筛选条件重新加载第1页
      loadPaymentLogs(1);
    });
  }

  // 绑定支付日志"上一页"按钮点击事件
  const paymentLogsPrevBtn = document.getElementById("payment-logs-prev-btn");
  if (paymentLogsPrevBtn) {
    paymentLogsPrevBtn.addEventListener("click", function () {
      // 检查是否已经是第1页
      if (currentPaymentLogsPage > 1) {
        // 加载上一页
        loadPaymentLogs(currentPaymentLogsPage - 1);
      }
    });
  }

  // 绑定支付日志"下一页"按钮点击事件
  const paymentLogsNextBtn = document.getElementById("payment-logs-next-btn");
  if (paymentLogsNextBtn) {
    paymentLogsNextBtn.addEventListener("click", function () {
      // 加载下一页
      loadPaymentLogs(currentPaymentLogsPage + 1);
    });
  }

  // 输出日志：记录管理员事件绑定完成
  console.log("[管理员-支付] 管理员事件监听器已绑定");
});

// ============================================================================
// 彩虹易支付系统 - 管理员功能实现结束
// ============================================================================

// ============================================================================
// 彩虹易支付系统 - 前端JavaScript实现结束
// ============================================================================

// ============================================================================
// 欠费检查功能
// ============================================================================

/**
 * 检查账号是否有欠费，在开始任务前调用
 *
 * 功能说明：
 * - 调用后端 /api/check_overdue 接口检查指定账号或所有账号的欠费状态
 * - 如果存在欠费，显示欠费弹窗并返回 false 阻止任务启动
 * - 如果没有欠费或检查失败（容错），返回 true 允许任务继续
 *
 * @param {string|string[]|null} schoolUsernameOrList - 可选参数，支持以下三种类型：
 *   - null：检查当前用户的所有账号
 *   - string：检查单个指定的学校账号（例如："20210001"）
 *   - string[]：检查多个指定的学校账号（例如：["20210001", "20210002"]）
 *
 * @returns {Promise<boolean>} - true 表示可以继续启动任务，false 表示被欠费阻止
 *
 * 调用示例：
 * // 示例1：检查所有账号
 * const canStart1 = await checkOverdueBeforeStart();
 *
 * // 示例2：检查单个账号
 * const canStart2 = await checkOverdueBeforeStart('20210001');
 *
 * // 示例3：检查选中的多个账号
 * const selectedUsernames = ['20210001', '20210002', '20210003'];
 * const canStart3 = await checkOverdueBeforeStart(selectedUsernames);
 */
// “强制执行 / 此次不计费”决策：欠费弹窗写入，各启动入口在调用后端前消费。
let _overdueForceOverride = { bypass_overdue: false, waive_charge: false };

function _setOverdueForceOverride(waiveCharge) {
  _overdueForceOverride = {
    bypass_overdue: true,
    waive_charge: waiveCharge === true,
  };
}

function _consumeOverdueForceOverride() {
  const options = { ..._overdueForceOverride };
  _overdueForceOverride = { bypass_overdue: false, waive_charge: false };
  return options;
}

function normalizeOverdueAccounts(value) {
  return [...new Set((Array.isArray(value) ? value : [value])
    .filter(item => typeof item === "string")
    .map(item => item.trim()).filter(item => item && !/^(null|none|undefined)$/i.test(item)))];
}

async function checkOverdueBeforeStart(schoolUsernameOrList = null, options = {}) {
  const context = captureLegacyBusinessContext();
  try { if (await ensureLegacyBusinessMode()) return true; } catch (_) { return false; }
  if (!isCurrentLegacyBusinessContext(context)) return false;
  const accounts = normalizeOverdueAccounts(schoolUsernameOrList);
  if (!accounts.length) return true;
  const requestedAccountCount = Array.isArray(schoolUsernameOrList)
    ? schoolUsernameOrList.length
    : typeof schoolUsernameOrList === "string" && schoolUsernameOrList
      ? 1
      : 0;
  console.log("检查欠费状态，账号数量:", requestedAccountCount);
  try {
    // 启动前只检查本次执行明确选中的账号，不使用省略范围的全量语义。
    const requestBody = { school_usernames: accounts };

    // ========== 步骤2：调用后端检查欠费接口 ==========
    // 使用 fetch 而不是 callPythonAPI，因为需要更精细的错误处理
    console.log(
      "调用 /api/check_overdue 接口，账号数量:",
      requestedAccountCount,
    );
    const overdueCheckHeaders = {
      "Content-Type": "application/json",
      // 使用全局 sessionUUID 进行会话认证
      "X-Session-ID": sessionUUID,
    };
    // 管理员查看态（上帝模式）：必须带上来源会话，后端才能按管理员身份校验。
    // 缺少该请求头时目标会话 owner 与管理员 cookie token 不匹配，接口会直接 401。
    if (typeof addAdminViewOriginSessionHeader === "function") {
      addAdminViewOriginSessionHeader(overdueCheckHeaders, sessionUUID);
    }
    const response = await fetch("/api/check_overdue", {
      method: "POST",
      headers: overdueCheckHeaders,
      body: JSON.stringify(requestBody),
    });

    // ========== 步骤3：解析响应数据 ==========
    const result = await response.json();
    if (!isCurrentLegacyBusinessContext(context)) return false;

    // ========== 步骤4：检查接口调用是否成功 ==========
    if (!result.success) {
      // 接口返回失败，显示错误信息
      showModalAlert(result.message, "错误");
      // 容错：即使检查失败，也允许任务继续（避免阻塞正常用户）
      return true;
    }

    // ========== 步骤5：处理欠费情况 ==========
    // 如果存在欠费账号
    if (result.has_overdue) {
      const overdueAccounts = result.overdue_accounts || [];
      const allowSkip =
        options.allowSkip === true &&
        requestedAccountCount > 0 &&
        overdueAccounts.length < requestedAccountCount;
      // 显示欠费弹窗，等待用户处理
      const action = await showOverduePaymentModal(overdueAccounts, {
        allowSkip,
        allowForce: result.can_bypass_overdue === true,
        isAdmin: result.is_admin === true,
        availableRuns: result.available_runs,
      });
      if (!isCurrentLegacyBusinessContext(context)) return false;
      if (action === "skip") {
        if (typeof options.onSkip === "function") {
          options.onSkip(overdueAccounts);
        }
        return true;
      }
      if (action === "force") {
        // 点“强制执行”后校验可用执行次数：不足则弹警告；
        // 管理员可以在警告里选择“此次不计费”，使其跳过扣减与账单生成。
        const availableRuns = Number(result.available_runs);
        const isAdmin = result.is_admin === true;
        const runsExhausted =
          Number.isFinite(availableRuns) &&
          availableRuns !== -1 &&
          availableRuns <= 0;
        if (runsExhausted) {
          const warning = await Swal.fire({
            icon: "warning",
            title: "执行次数不足",
            text: "强制执行将继续执行任务，并会为本次执行生成欠费账单。",
            confirmButtonText: "继续执行",
            confirmButtonColor: "#ef4444",
            showCancelButton: isAdmin,
            cancelButtonText: "此次不计费",
            cancelButtonColor: "#10b981",
            allowOutsideClick: false,
          });
          if (!isCurrentLegacyBusinessContext(context)) return false;
          if (warning.isConfirmed) {
            _setOverdueForceOverride(false);
          } else if (
            warning.isDismissed &&
            String(warning.dismiss || "") === "cancel"
          ) {
            _setOverdueForceOverride(true);
          } else {
            return false;
          }
        } else {
          _setOverdueForceOverride(false);
        }
        return true;
      }
      // 返回 false 阻止任务启动
      return false;
    }

    // ========== 步骤6：没有欠费，允许任务继续 ==========
    return true;
  } catch (error) {
    if (!isCurrentLegacyBusinessContext(context)) return false;
    // 捕获所有异常（网络错误、JSON解析错误等）
    console.error("检查欠费失败:", error);
    // 容错：检查失败不阻止任务执行，避免因网络问题影响正常用户
    return true;
  }
}

let _requirePaymentForOverdueCache = {
  value: null,
  ts: 0,
};

async function _isPaymentRequiredForOverdueCheck() {
  // 离线导入的任务不涉及真实账号与计费：既不查欠费也不产生支付订单
  if (await ensureLegacyBusinessMode()) {
    console.log("[欠费检查] 当前为离线测试模式，跳过欠费检查。");
    return false;
  }
  const now = Date.now();
  if (
    _requirePaymentForOverdueCache.value !== null &&
    now - _requirePaymentForOverdueCache.ts < 30 * 1000
  ) {
    return _requirePaymentForOverdueCache.value;
  }

  try {
    const headers = {};
    if (typeof sessionUUID !== "undefined" && sessionUUID) {
      headers["X-Session-ID"] = sessionUUID;
    }
    addAdminViewOriginSessionHeader(headers, sessionUUID);
    const response = await fetch("/api/config/pricing", {
      method: "GET",
      headers,
    });
    const result = await response.json();
    if (
      response.ok &&
      result &&
      result.success &&
      result.config &&
      typeof result.config.require_payment !== "undefined"
    ) {
      const enabled =
        result.config.require_payment === true ||
        String(result.config.require_payment).toLowerCase() === "true";
      _requirePaymentForOverdueCache = { value: enabled, ts: now };
      return enabled;
    }
  } catch (error) {
    console.warn(
      "[欠费检查] 获取后端 require_payment 配置失败，回退本地状态",
      error,
    );
  }

  const requirePaymentCheckbox = document.getElementById(
    "pricing-require-payment_modal",
  );
  if (!requirePaymentCheckbox) return true;
  return !!requirePaymentCheckbox.checked;
}

function _isInMultiAccountModeForOverdueCheck() {
  const pcMultiApp = document.getElementById("multi-account-app");
  const mobileMultiApp = document.getElementById("mobile-multi-account-app");
  return (
    (pcMultiApp && !pcMultiApp.classList.contains("hidden")) ||
    (mobileMultiApp && !mobileMultiApp.classList.contains("hidden")) ||
    window.mobileAdminPanelMode === "multi"
  );
}

function _getMultiAccountListUsernames() {
  const usernames = new Set();
  ["multi-account-list", "mobile-multi-account-list"].forEach((containerId) => {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll("[data-username]").forEach((el) => {
      const username = (el.dataset.username || "").trim();
      if (username) usernames.add(username);
    });
  });
  return Array.from(usernames);
}

async function _checkOverdueBeforeStartByCurrentMode(options = {}) {
  const context = captureLegacyBusinessContext();
  try {
    const offline = await ensureLegacyBusinessMode();
    if (!isCurrentLegacyBusinessContext(context)) return false;
    if (offline) return true;
  } catch (_) { return false; }
  const paymentRequired = await _isPaymentRequiredForOverdueCheck();
  if (!isCurrentLegacyBusinessContext(context)) return false;
  if (!paymentRequired) {
    console.log("未开启欠费检查，允许继续。");
    return true;
  }
  if (_isInMultiAccountModeForOverdueCheck()) {
    console.log("多账号模式，检查所有账号的欠费状态。");
    const usernames = _getMultiAccountListUsernames();
    console.log("多账号模式，账号数量:", usernames.length);
    return usernames.length > 0
      ? await checkOverdueBeforeStart(usernames, options)
      : true;
  }
  console.log("单账号模式，检查当前账号的欠费状态。");
  const currentSchoolUsername = String(
    currentUserData?.student_id || "",
  ).trim();
  return normalizeOverdueAccounts(currentSchoolUsername).length
    ? await checkOverdueBeforeStart(currentSchoolUsername, options)
    : true;
}

/**
 * 显示欠费提示弹窗
 */
/**
 * 显示欠费账号选择弹窗
 * 用户可以勾选要缴费的账号，查看预估金额
 * @param {Array} overdueAccounts - 欠费账号列表，格式：[{username, name, overdue_count, school_username}, ...]
 */
async function showOverduePaymentModal(overdueAccounts, options = {}) {
  const context = captureLegacyBusinessContext();
  if (await ensureLegacyBusinessMode() || !isCurrentLegacyBusinessContext(context)) return "cancel";
  const allowSkip = options.allowSkip === true;
  // 有 bypass_overdue 权限时额外提供“强制执行”按钮。
  const allowForce = options.allowForce === true;
  // 显示加载提示
  Swal.fire({
    title: "正在获取欠费账单",
    allowOutsideClick: false,
    didOpen: () => {
      Swal.showLoading();
    },
  });

  // 收集所有欠费账号的 school_username 集合
  const overdueSet = new Set(normalizeOverdueAccounts((overdueAccounts || []).map(a => a.school_username || a.username || "")));
  if (!overdueSet.size) { Swal.close(); return "cancel"; }

  // 服务端先限定到本次欠费账号，前端再筛选待支付状态。
  let pendingBills = [];
  try {
    const query = new URLSearchParams();
    overdueSet.forEach(username => query.append("school_usernames", username));
    const headers = { "X-Session-ID": context.session };
    addAdminViewOriginSessionHeader(headers, context.session);
    const resp = await fetch(`/api/billing/list?${query}`, { headers });
    const result = await resp.json();
    if (!isCurrentLegacyBusinessContext(context)) return "cancel";
    if (result.success) {
      pendingBills = (result.records || []).filter(
        (r) => r.status === "pending" && overdueSet.has(r.school_username),
      );
    }
  } catch (e) {
    if (!isCurrentLegacyBusinessContext(context)) return "cancel";
    console.warn("[showOverduePaymentModal] 获取账单失败:", e);
  }

  Swal.close();

  if (!pendingBills.length) {
    const emptyResult = await Swal.fire({
      title: "暂无待支付账单",
      text: "未找到对应的待支付账单记录，请联系管理员确认。",
      icon: "info",
      confirmButtonText: "确定",
      showDenyButton: allowSkip || allowForce,
      denyButtonText: allowForce ? "强制执行" : "跳过欠费账号并开始",
      denyButtonColor: allowForce ? "#ef4444" : "#f59e0b",
    });
    if (emptyResult.isDenied) return allowForce ? "force" : "skip";
    return "cancel";
  }

  const totalAmount = pendingBills
    .reduce((s, r) => s + (parseFloat(r.amount) || 0), 0)
    .toFixed(2);

  // 点击卡片/行切换选中状态并更新合计
  const updateTotal = `document.getElementById('overdue-total-amount').textContent='¥'+[...document.querySelectorAll('[data-overdue-bill-select]')].filter(c=>c.checked).reduce((s,c)=>s+parseFloat(c.dataset.amount||0),0).toFixed(2);`;

  let bodyHtml, modalWidth;

  if (isMobileMode) {
    // ── 移动端：全卡片式 ────────────────────────────────────────────────
    const cardsHtml = pendingBills
      .map((r, idx) => {
        const safeId = escapeHtml(r.billing_id || "");
        const safeSchool = escapeHtml(r.school_username || "-");
        const safeName = escapeHtml(r.school_name || r.school_username || "-");
        const safeReason = escapeHtml(r.reason || "-");
        const amount = r.amount != null ? parseFloat(r.amount) : 0;
        const fmtAmount = "¥" + amount.toFixed(2);
        return `
<div class="bg-white border-2 border-slate-200 rounded-2xl shadow-sm overflow-hidden transition-all cursor-pointer"
     style="tap-highlight-color:transparent"
     onclick="const cb=document.getElementById('ob-${idx}');cb.checked=!cb.checked;${updateTotal}this.style.borderColor=cb.checked?'#3b82f6':'#e2e8f0';">

  <!-- 顶栏：小屏垂直，大屏水平 -->
  <div class="flex flex-col sm:flex-row sm:items-center gap-2 px-3 py-2.5 bg-slate-50 border-b border-slate-200 text-center sm:text-left">

    <input id="ob-${idx}" type="checkbox" data-overdue-bill-select="1"
      data-billing-id="${safeId}" data-school-username="${safeSchool}"
      data-amount="${amount}" checked
      onclick="event.stopPropagation();${updateTotal}this.closest('[onclick]').style.borderColor=this.checked?'#3b82f6':'#e2e8f0';"
      class="w-4 h-4 mx-auto sm:mx-0 flex-shrink-0 accent-blue-500">

    <div class="flex-1 min-w-0">
      <div class="text-[10px] text-slate-500 leading-none mb-0.5">学校账号</div>
      <div class="text-xs font-semibold text-slate-800 truncate">${safeSchool}</div>
    </div>

  </div>

  <!-- 内容区 -->
  <div class="px-3 pt-2 pb-2.5">

    <div class="flex items-center gap-1.5 mb-1.5">
      <span class="text-[10px] text-slate-500 flex-shrink-0">姓名</span>
      <span class="text-[11px] font-medium text-slate-700 truncate">${safeName}</span>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px] mb-1.5">
      <div class="bg-amber-50 border border-amber-100 rounded-xl px-2.5 py-1.5">
        <div class="text-amber-600/70 leading-none mb-0.5 text-[10px]">金额</div>
        <div class="text-amber-700 font-bold">${fmtAmount}</div>
      </div>

      <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5">
        <div class="text-slate-500 leading-none mb-0.5 text-[10px]">创建时间</div>
        <div class="text-slate-700 break-all text-[10px]">${escapeHtml(_fmtBillTime(_getBillingTime(r, "created_at")) || "-")}</div>
      </div>
    </div>

    <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5 text-[10px]">
      <div class="text-slate-500 leading-none mb-0.5">详情</div>
      <div class="text-slate-800 break-all">${safeReason}</div>
    </div>

  </div>
</div>
`;
      })
      .join("");

    bodyHtml = `
      <div class="text-left space-y-3">
        <p class="text-[11px] text-slate-500">💡 点击卡片或勾选可切换选中状态</p>
        <div class="space-y-2 max-h-[55vh] overflow-y-auto pr-0.5">
          ${cardsHtml}
        </div>
        <div class="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl p-3 text-center shadow-md">
          <div class="text-white/70 text-[10px] mb-0.5">合计金额</div>
          <div id="overdue-total-amount" class="text-white text-2xl font-bold">¥${totalAmount}</div>
        </div>
      </div>`;
    modalWidth = "95vw";
  } else {
    // ── PC端：列表式 ─────────────────────────────────────────────────────
    const rowsHtml = pendingBills
      .map((r, idx) => {
        const safeId = escapeHtml(r.billing_id || "");
        const safeSchool = escapeHtml(r.school_username || "-");
        const safeName = escapeHtml(r.school_name || r.school_username || "-");
        const safeReason = escapeHtml(r.reason || "-");
        const amount = r.amount != null ? parseFloat(r.amount) : 0;
        const fmtAmount = "¥" + amount.toFixed(2);
        const fmtTime = escapeHtml(_fmtBillTime(_getBillingTime(r, "created_at")) || "-");
        return `
        <tr class="border-b border-slate-100 hover:bg-blue-50/40 cursor-pointer transition-colors"
            onclick="const cb=document.getElementById('ob-${idx}');cb.checked=!cb.checked;${updateTotal}">
          <td class="py-2.5 pl-3 pr-2 text-center">
            <input id="ob-${idx}" type="checkbox" data-overdue-bill-select="1"
              data-billing-id="${safeId}" data-school-username="${safeSchool}"
              data-amount="${amount}" checked
              onclick="event.stopPropagation();${updateTotal}"
              class="w-4 h-4 accent-blue-500">
          </td>
          <td class="py-2.5 px-2">
            <div class="text-sm font-medium text-slate-800">${safeSchool}</div>
          </td>
          <td class="py-2.5 px-2">
            <div class="text-xs text-slate-500">${safeName}</div>
          </td>
          <td class="py-2.5 px-2 text-sm text-slate-600 max-w-[180px]">
            <div class="break-words whitespace-normal" title="${safeReason}">
              ${safeReason}
            </div>
          </td>

          <td class="py-2.5 px-2 text-sm font-semibold text-amber-600 whitespace-nowrap">${fmtAmount}</td>
          <td class="py-2.5 px-2 text-xs text-slate-400 whitespace-nowrap">${fmtTime}</td>
        </tr>`;
      })
      .join("");

    bodyHtml = `
      <div class="text-left">
        <p class="text-xs text-slate-500 mb-3">💡 点击行可切换勾选，勾选后点击"确认支付"合并发起支付</p>
        <div class="rounded-xl border border-slate-200 overflow-hidden mb-3">
          <div class="overflow-x-auto max-h-72 overflow-y-auto">
            <table class="w-full text-left border-collapse text-xs text-center">
              <thead>
                <tr class="bg-slate-100 sticky top-0 z-10">
                  <th class="py-2.5 pl-3 pr-2 w-8">
                    <input type="checkbox" checked
                      onclick="document.querySelectorAll('[data-overdue-bill-select]').forEach(c=>c.checked=this.checked);${updateTotal}"
                      class="w-4 h-4 accent-blue-500">
                  </th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600 whitespace-nowrap">学校账号</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600">姓名</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600">详情</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600 whitespace-nowrap">金额</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600 whitespace-nowrap">创建时间</th>
                </tr>
              </thead>
              <tbody class="bg-white divide-y divide-slate-50">
                ${rowsHtml}
              </tbody>
            </table>
          </div>
        </div>
        <div class="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl px-5 py-3 flex items-center justify-between shadow-md">
          <span class="text-white/80 text-sm">合计金额</span>
          <span id="overdue-total-amount" class="text-white text-2xl font-bold">¥${totalAmount}</span>
        </div>
      </div>`;
    modalWidth = "780px";
  }

  const result = await Swal.fire({
    title: "选择要支付的账单",
    html: bodyHtml,
    showCancelButton: true,
    confirmButtonText: "确认支付",
    cancelButtonText: "取消",
    confirmButtonColor: "#3b82f6",
    cancelButtonColor: "#94a3b8",
    showDenyButton: allowSkip || allowForce,
    denyButtonText: allowForce ? "强制执行" : "跳过欠费账号并开始",
    denyButtonColor: allowForce ? "#ef4444" : "#f59e0b",
    width: modalWidth,
  });

  if (!isCurrentLegacyBusinessContext(context)) return "cancel";
  if (result.isDenied) return allowForce ? "force" : "skip";
  if (!result.isConfirmed) return "cancel";

  // 收集选中的账单
  const selectedBills = [];
  document.querySelectorAll("[data-overdue-bill-select]").forEach((cb) => {
    if (cb.checked) {
      selectedBills.push({
        billing_id: cb.dataset.billingId,
        school_username: cb.dataset.schoolUsername,
      });
    }
  });

  if (!selectedBills.length) {
    await Swal.fire({
      title: "提示",
      text: "请至少选择一条账单",
      icon: "info",
      confirmButtonText: "确定",
    });
    return "cancel";
  }

  const selectedPayType = await _chooseBillingPayType({
    title: "选择支付方式",
    totalAmount,
  });
  if (!isCurrentLegacyBusinessContext(context)) return "cancel";
  if (!selectedPayType) return "cancel";
  await _runBillingPaymentFlow(selectedBills, selectedPayType);
  return "paid";
}

/**
 * 支付流程主函数
 * 实现完整的支付流程：选择支付方式 → 创建订单 → 显示支付页面 → 轮询状态 → 支付成功
 * @param {Array} selectedAccounts - 选中的欠费账号列表，格式：[{school_username, overdue_count}, ...]
 * @param {Number} singleRunCost - 单次费用（从后端配置获取）
 */
async function clearOverduePlaceholder(selectedAccounts, singleRunCost) {
  // ========== 第一步：获取启用的支付方式和完整配置 ==========

  // 声明两个变量用于存储支付方式数据
  // enabledPaymentMethods: 存储已启用的支付方式代码列表，如 ["alipay", "wxpay"]
  // paymentMethodsFullConfig: 存储完整的支付方式配置对象，包含SVG、名称、颜色等详细信息
  let enabledPaymentMethods = [];
  let paymentMethodsFullConfig = {};

  try {
    // ========== 第一步A：获取启用的支付方式列表 ==========
    // 调用 /api/payment/methods_config 接口获取当前启用的支付方式列表
    // 该接口返回已启用的支付方式的代码数组
    const methodsResponse = await fetch("/api/payment/methods_config", {
      method: "GET", // 使用 GET 方法获取数据
      headers: {
        "Content-Type": "application/json", // 设置请求头，声明期望返回JSON格式
        "X-Session-ID": sessionUUID, // 携带会话ID进行身份验证，防止未登录访问
      },
    });

    // 解析响应体为JSON对象
    const methodsResult = await methodsResponse.json();

    // 检查API调用是否成功，并且返回了支付方式配置
    // result.success 表示服务端处理成功
    // result.enabled_methods 是启用的支付方式代码数组
    if (methodsResult.success && methodsResult.enabled_methods) {
      // 将启用的支付方式列表赋值给变量
      // 例如：["alipay", "wxpay", "qqpay"]
      enabledPaymentMethods = methodsResult.enabled_methods;

      // 输出日志，便于调试
      console.log(
        "[欠费支付] 成功获取启用的支付方式列表:",
        enabledPaymentMethods,
      );
    }

    // ========== 第一步B：获取完整的支付方式配置（包含SVG、名称等） ==========
    // 调用 /api/admin/payment/config 接口获取支付方式的完整配置
    // 该接口返回每个支付方式的详细信息：SVG图标、中文名称、品牌颜色等
    const configResponse = await fetch("/api/admin/payment/config", {
      method: "GET", // 使用 GET 方法获取数据
      headers: {
        "Content-Type": "application/json", // 设置请求头
        "X-Session-ID": sessionUUID, // 携带会话ID
      },
    });

    // 解析响应体为JSON对象
    const configResult = await configResponse.json();

    // 检查API调用是否成功，并且返回了支付方式配置对象
    // configResult.payment_methods 是一个对象，键是支付方式代码，值是配置详情
    // 例如：{ "alipay": { "name": "支付宝", "svg": "<svg>...</svg>", ... }, ... }
    if (configResult.success && configResult.payment_methods) {
      // 将完整配置对象赋值给变量
      paymentMethodsFullConfig = configResult.payment_methods;

      // 输出日志，便于调试
      console.log(
        "[欠费支付] 成功获取支付方式完整配置:",
        Object.keys(paymentMethodsFullConfig),
      );
    }
  } catch (e) {
    // 如果任何API调用失败，捕获异常并记录错误
    // 这可能是网络错误、服务器错误或解析JSON失败
    console.error("[欠费支付] 获取支付方式配置失败:", e);

    // 可以选择在这里显示一个更友好的错误提示
    // 但为了不中断流程，我们继续执行，让后续的检查来处理
  }

  // ========== 验证：检查是否有可用的支付方式 ==========
  // 如果没有启用任何支付方式，无法创建支付订单
  // 此时需要提示用户联系管理员配置支付方式
  if (enabledPaymentMethods.length === 0) {
    // 使用 showModalAlert 显示友好的错误提示
    // showModalAlert是移动端兼容的弹窗函数
    showModalAlert("管理员尚未配置支付方式，请联系管理员", "无可用支付方式");

    // 退出函数，不继续执行后续代码
    return;
  }

  // ========== 第二步：显示支付方式选择对话框 ==========

  // ========== 生成支付方式选项HTML ==========
  // 遍历每个启用的支付方式，为其创建一个可点击的卡片
  // 使用 .map() 方法将支付方式代码数组转换为HTML字符串数组
  const paymentMethodsHtml = enabledPaymentMethods
    .map((method) => {
      // ========== 从完整配置中获取该支付方式的详细信息 ==========
      // paymentMethodsFullConfig 是从后端获取的完整配置对象
      // 包含：name（中文名称）、svg（SVG图标代码）、textColor（文字颜色）等
      const config = paymentMethodsFullConfig[method] || {};

      // 提取支付方式名称
      // 如果配置中没有 name 字段，则使用支付方式代码作为默认值
      // 例如：config.name = "支付宝支付"，否则使用 "alipay"
      const name = config.name || method;

      // 提取SVG图标代码
      // 如果配置中没有 svg 字段，则使用默认的通用支付图标
      // 默认图标是一个信用卡的SVG矢量图
      const svg =
        config.svg ||
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path></svg>';

      // 提取文字颜色类
      // Tailwind CSS 颜色类，用于设置图标和文字的颜色
      // 例如：'text-blue-600' 表示蓝色（支付宝）
      const textColor = config.textColor || "text-blue-600";

      // 提取边框颜色类（悬停时使用）
      // 例如：'hover:border-blue-500' 表示鼠标悬停时边框变为蓝色
      const borderColor = config.borderColor || "hover:border-blue-500";

      // ========== 生成HTML字符串 ==========
      // 返回一个包含支付方式卡片的HTML代码
      return `
            <div class="payment-method-option ${borderColor}" 
                 data-method="${escapeHtml(method)}"
                 onclick="selectPaymentMethod(${escapeInlineJsArg(method)})"
                 style="
                     padding: 15px 20px;
                     margin: 10px 0;
                     border: 2px solid #e2e8f0;
                     border-radius: 10px;
                     cursor: pointer;
                     transition: all 0.2s;
                     display: flex;
                     align-items: center;
                     background: white;
                 "
                 onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';"
                 onmouseout="this.style.boxShadow='none';">
                <div class="${textColor}" style="margin-right: 15px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
                    ${svg}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 16px; color: #1e293b;">
                        ${escapeHtml(name)}
                    </div>
                </div>
                <input type="radio" 
                       name="payment-method" 
                       value="${escapeHtml(method)}"
                       style="width: 20px; height: 20px; cursor: pointer;">
            </div>
        `;
    })
    .join(""); // 使用 .join('') 将数组中的所有HTML字符串连接成一个完整的字符串

  // 计算总金额：所有选中账号的欠费次数 × 单次费用
  const totalAmount = selectedAccounts
    .reduce((sum, acc) => sum + acc.overdue_count * singleRunCost, 0)
    .toFixed(2);

  // 显示支付方式选择对话框
  const paymentMethodResult = await Swal.fire({
    title: "选择支付方式",
    html: `
            <div style="text-align: left;">
                <div style="
                    padding: 12px;
                    background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
                    border-radius: 12px;
                    margin-bottom: 20px;
                    text-align: center;
                    box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
                ">
                    <div style="color: #64748b; font-size: 13px; margin-bottom: 5px;">💰 应付金额</div>
                    <div style="color: #dc2626; font-size: 28px; font-weight: bold;">¥${totalAmount}</div>
                </div>
                <div class="payment-methods-container" style="
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 10px;
                    max-height: calc(100vh - 350px);
                    overflow-y: auto;
                    padding: 4px;
                ">
                    ${paymentMethodsHtml}
                </div>
            </div>
        `,
    showCancelButton: true,
    confirmButtonText: "确认支付",
    cancelButtonText: "返回",
    confirmButtonColor: "#3b82f6",
    cancelButtonColor: "#94a3b8",
    width: "auto",
    customClass: {
      popup: "swal2-payment-popup",
    },
    didOpen: () => {
      // 根据屏幕高度动态调整
      const popup = Swal.getPopup();
      const container = popup.querySelector(".payment-methods-container");
      if (container) {
        const viewportHeight = window.innerHeight;
        const methodsCount = paymentMethods.length;
        if (viewportHeight > 600 && methodsCount <= 4) {
          container.style.maxHeight = "none";
          container.style.overflowY = "visible";
        }
        popup.style.maxWidth = methodsCount > 2 ? "550px" : "400px";
        popup.style.minWidth = "320px";
      }
      // 绑定点击事件，点击整个div时选中对应的radio按钮
      window.selectPaymentMethod = (method) => {
        const radio = document.querySelector(
          `input[name="payment-method"][value="${method}"]`,
        );
        if (radio) {
          radio.checked = true;
          // 添加选中视觉效果
          document.querySelectorAll(".payment-method-option").forEach(el => {
            el.style.borderColor = "#e2e8f0";
            el.style.background = "white";
          });
          const parentDiv = radio.closest(".payment-method-option");
          if (parentDiv) {
            parentDiv.style.borderColor = "#3b82f6";
            parentDiv.style.background = "#f0f9ff";
          }
        }
      };
    },
    preConfirm: () => {
      // 在用户点击"确认支付"时，验证是否选择了支付方式
      const selectedMethod = document.querySelector(
        'input[name="payment-method"]:checked',
      );
      if (!selectedMethod) {
        Swal.showValidationMessage("请选择一种支付方式");
        return false;
      }
      return selectedMethod.value; // 返回选中的支付方式
    },
  });

  // 如果用户点击了"返回"按钮，退出支付流程
  if (!paymentMethodResult.isConfirmed) {
    return;
  }

  // 获取用户选择的支付方式
  const selectedPaymentMethod = paymentMethodResult.value;

  // ========== 第三步：创建支付订单 ==========

  // 显示加载动画
  Swal.fire({
    title: "正在创建订单...",
    text: "请稍候",
    allowOutsideClick: false, // 不允许点击外部关闭
    allowEscapeKey: false, // 不允许按ESC关闭
    didOpen: () => {
      Swal.showLoading(); // 显示加载动画
    },
  });
  subOpenid = "";
  subAppid = "";
  auth_code = "";
  try {
    // 调用后端API创建支付订单
    const createOrderResponse = await fetch(
      "/api/payment/create_order_for_overdue",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
        body: JSON.stringify({
          overdue_accounts: selectedAccounts, // 选中的欠费账号列表
          pay_type: selectedPaymentMethod, // 用户选择的支付方式
          device: Get_YiPAi_device(),
          payment_type: "web",
          app_host: window.location.protocol + "//" + window.location.host,
          sub_openid: subOpenid,
          sub_appid: subAppid,
          auth_code: auth_code,
        }),
      },
    );

    const orderResult = await createOrderResponse.json();

    // 如果订单创建失败，抛出错误
    if (!orderResult.success) {
      throw new Error(orderResult.message || "创建订单失败");
    }

    // 订单创建成功，获取订单信息
    const orderId = orderResult.order_id; // 订单号
    const payUrl = orderResult.pay_url; // 支付跳转URL
    const totalCount = orderResult.total_count; // 总欠费次数
    const pay_type = orderResult.pay_type;

    // ========== 第四步：显示支付页面并开始轮询 ==========

    await showPaymentPageWithPolling(
      orderId,
      payUrl,
      totalAmount,
      selectedPaymentMethod,
      pay_type,
    );
  } catch (error) {
    // 捕获创建订单过程中的所有错误
    console.error("创建订单失败:", error);
    // 使用showModalAlert显示错误信息
    Swal.close();

    showModalAlert(error.message || "网络错误或服务器异常", "创建订单失败");
  }
}

/**
 * 显示支付页面并轮询支付状态
 * 实现核心功能：显示支付二维码/链接 + 每0.5秒轮询订单状态
 * @param {String} orderId - 订单号
 * @param {String} payUrl - 支付URL（用户需要打开此链接完成支付）
 * @param {String} totalAmount - 总金额（字符串格式，例如："15.00"）
 * @param {String} paymentMethod - 支付方式（alipay/wxpay/qqpay等）
 */
async function showPaymentPageWithPolling(
  orderId,
  payUrl,
  totalAmount,
  paymentMethod,
  pay_type,
) {
  // ========== 动态获取支付方式名称映射 ==========
  // 初始化支付方式名称映射对象，用于将后端的支付方式代码（如'alipay'）转换为用户友好的显示名称（如'支付宝'）
  let paymentMethodNames = {};

  try {
    // 向后端API发起GET请求，获取支付方式配置信息
    // 该接口返回所有可用的支付方式及其对应的显示名称
    const methodsResponse = await fetch("/api/payment/methods_config", {
      method: "GET", // 使用GET方法获取数据
      headers: {
        "Content-Type": "application/json", // 指定请求内容类型为JSON
        "X-Session-ID": sessionUUID, // 携带会话ID用于身份验证，确保请求合法性
      },
    });

    // 检查HTTP响应状态是否成功（状态码200-299）
    if (methodsResponse.ok) {
      // 将响应体解析为JSON对象
      const methodsData = await methodsResponse.json();

      // 验证返回数据的有效性：
      // 1. success字段为true表示接口调用成功
      // 2. methods字段存在且不为空，包含支付方式数组
      if (methodsData.success && methodsData.methods) {
        // 遍历methods数组，构建支付方式代码到显示名称的映射对象
        // 每个method对象包含code（代码）和name（显示名称）两个字段
        methodsData.methods.forEach((method) => {
          // 将支付方式代码作为key，显示名称作为value存入映射对象
          // 例如：{ 'alipay': '支付宝', 'wxpay': '微信支付' }
          paymentMethodNames[method.code] = method.name;
        });
      }
    }
  } catch (error) {
    // 捕获网络请求过程中可能出现的各种错误（网络异常、解析失败等）
    // 记录错误信息到控制台，便于调试和问题追踪
    console.error("获取支付方式配置失败:", error);
    // 注意：此处不抛出异常，而是继续执行，让程序使用fallback机制
  }

  // ========== Fallback机制：使用默认映射 ==========
  // 如果动态获取失败（网络错误、接口异常、返回数据为空等情况），
  // 则使用预定义的默认支付方式映射，确保程序能够正常运行
  if (Object.keys(paymentMethodNames).length === 0) {
    // 定义默认的支付方式映射，包含常见的支付方式
    paymentMethodNames = {
      alipay: "支付宝", // 支付宝支付
      wxpay: "微信", // 微信支付
      qqpay: "QQ钱包", // QQ钱包支付
      bank: "网银", // 网上银行支付
      unionpay: "云闪付", // 中国银联云闪付
    };
  }

  // 根据传入的支付方式代码，从映射对象中获取对应的显示名称
  // 如果找不到对应的映射（例如新增的支付方式尚未配置），则直接使用原始代码作为显示名称
  const methodName = paymentMethodNames[paymentMethod] || paymentMethod;

  // 轮询控制变量
  let pollingInterval = null; // 轮询定时器ID
  let pollingCount = 0; // 已轮询次数
  const maxPollingCount = 600; // 最多轮询600次（0.5秒 × 600 = 5分钟）

  // 显示支付页面
  await Swal.fire({
    title: "请完成支付",
    html: `
            <div style="text-align: center;">
                <!-- ========== 订单号显示区域 ========== -->
                <div style="margin-bottom: 20px;">
                    <div style="color: #64748b; font-size: 14px; margin-bottom: 5px;">订单号</div>
                    <div style="
                        font-family: monospace; 
                        font-size: 13px; 
                        color: #475569; 
                        background: #f1f5f9; 
                        padding: 8px; 
                        border-radius: 6px;
                        word-break: break-all;
                    ">
                        ${escapeHtml(orderId)}
                    </div>
                </div>
                
                <!-- ========== 支付金额显示区域 ========== -->
                <div style="
                    padding: 15px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 10px;
                    margin-bottom: 20px;
                ">
                    <div style="color: rgba(255,255,255,0.9); font-size: 13px;">支付方式：${methodName}</div>
                    <div style="color: white; font-size: 28px; font-weight: bold; margin-top: 5px;">¥${totalAmount}</div>
                </div>

                <!-- ========== 支付链接显示区域（文本格式，可复制）========== -->
                <!-- 该区域显示完整的支付链接，用户可以直接复制 -->
                <div style="margin-bottom: 15px; padding: 10px; background: #f8fafc; border-radius: 6px;">
                    <div style="color: #64748b; font-size: 12px; margin-bottom: 5px;">支付链接</div>
                    <div style="
                        font-family: monospace;
                        font-size: 11px;
                        color: #475569;
                        word-break: break-all;
                        max-height: 60px;
                        overflow-y: auto;
                    ">
                        ${escapeHtml(payUrl)}
                    </div>
                </div>

                <!-- ========== 根据pay_type条件显示：二维码容器（仅qrcode类型）========== -->
                <!-- 当支付类型为'qrcode'时，显示此容器用于展示二维码 -->
                <!-- 二维码将在didOpen回调中通过QRCode库动态生成 -->
                ${
                  pay_type === "qrcode"
                    ? `
                    <div id="payment-qrcode-container" style="margin-bottom: 20px; padding: 15px; background: white; border-radius: 8px;">
                        <div style="color: #64748b; font-size: 13px; margin-bottom: 10px;">请扫描二维码支付</div>
                        <canvas id="payment-qrcode-canvas" style="display: block; margin: 0 auto;"></canvas>
                    </div>
                `
                    : ""
                }

                <!-- ========== 根据pay_type条件显示：跳转按钮（非qrcode类型）========== -->
                <!-- 当支付类型不是'qrcode'时（如jump、html、app等），显示此跳转按钮 -->
                <!-- 点击按钮将在新标签页中打开支付链接 -->
                ${
                  pay_type !== "qrcode"
                    ? `
                    <div style="margin-bottom: 20px;">
                        <a href="${escapeHtml(payUrl)}" 
                           target="_blank" 
                           style="
                               display: inline-block;
                               padding: 12px 40px;
                               background: #3b82f6;
                               color: white;
                               text-decoration: none;
                               border-radius: 8px;
                               font-weight: 600;
                               transition: all 0.2s;
                           "
                           onmouseover="this.style.background='#2563eb'"
                           onmouseout="this.style.background='#3b82f6'">
                            🔗 打开支付页面
                        </a>
                    </div>
                `
                    : ""
                }

                <!-- ========== 支付状态指示器 ========== -->
                <!-- 显示当前支付状态，包含动画效果和提示文字 -->
                <!-- 该状态会在轮询过程中动态更新（成功、失败、超时等） -->
                <div id="payment-status-indicator" style="
                    padding: 15px;
                    background: #fef3c7;
                    border: 2px solid #fbbf24;
                    border-radius: 8px;
                    color: #92400e;
                    font-size: 14px;
                ">
                    <div style="display: flex; align-items: center; justify-content: center;">
                        <div class="spinner" style="
                            width: 20px;
                            height: 20px;
                            border: 3px solid #fbbf24;
                            border-top-color: transparent;
                            border-radius: 50%;
                            animation: spin 1s linear infinite;
                            margin-right: 10px;
                        "></div>
                        <span>正在等待支付...</span>
                    </div>
                    <div style="margin-top: 8px; font-size: 12px; color: #78350f;">
                        系统正在实时检测支付状态
                    </div>
                </div>
            </div>

            <!-- ========== CSS动画定义 ========== -->
            <style>
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
            </style>
        `,
    icon: "info",
    showCancelButton: true,
    showConfirmButton: false,
    cancelButtonText: "取消支付",
    cancelButtonColor: "#94a3b8",
    allowOutsideClick: false,
    allowEscapeKey: false,
    width: "550px",
    didOpen: async () => {
      // ========== 二维码生成逻辑（仅qrcode类型）==========
      // 如果支付类型是'qrcode'（二维码支付），则在弹窗打开后生成二维码
      if (pay_type === "qrcode") {
        try {
          // 等待Swal弹窗完全显示，确保DOM元素已经渲染完成
          // 这里延迟100毫秒，确保canvas元素已经插入到页面中
          await new Promise((resolve) => setTimeout(resolve, 100));

          // 获取用于显示二维码的canvas元素
          const canvas = document.getElementById("payment-qrcode-canvas");

          // 检查canvas元素是否存在，以及QRCode库是否已加载
          // QRCode库通过CDN引入，需要确保在使用前已经加载完成
          if (canvas && typeof QRCode !== "undefined") {
            // 使用QRCode库的toCanvas方法生成二维码
            // 参数说明：
            // - canvas: 用于渲染二维码的canvas元素
            // - payUrl: 要编码到二维码中的支付链接
            // - options: 二维码生成选项
            await QRCode.toCanvas(canvas, payUrl, {
              width: 200, // 二维码宽度（像素）
              height: 200, // 二维码高度（像素）
              margin: 2, // 二维码边距（单位：模块数）
              color: {
                dark: "#000000", // 二维码深色部分（前景色）
                light: "#ffffff", // 二维码浅色部分（背景色）
              },
            });
            // 二维码生成成功，记录日志
            console.log("[支付二维码] 二维码生成成功");
          } else {
            // 如果canvas元素不存在或QRCode库未加载，记录警告
            // 这种情况可能是因为：
            // 1. HTML模板中的条件判断错误，canvas元素未生成
            // 2. QRCode库的CDN加载失败
            console.warn(
              "[支付二维码] 无法生成二维码：canvas元素不存在或QRCode库未加载",
            );
          }
        } catch (error) {
          // 捕获二维码生成过程中的任何错误
          // 例如：QRCode库方法调用异常、URL格式不正确等
          // 注意：此处仅记录错误，不中断程序执行，确保支付流程不受影响
          console.error("[支付二维码] 生成二维码失败:", error);
        }
      }

      // ========== 开始轮询支付状态 ==========

      // 使用setInterval
      pollingInterval = setInterval(async () => {
        pollingCount++; // 增加轮询计数

        // 如果超过最大轮询次数（5分钟），停止轮询并显示超时提示
        if (pollingCount > maxPollingCount) {
          clearInterval(pollingInterval);
          updatePaymentStatus("timeout", "支付超时，请重新发起支付");
          return;
        }

        try {
          // 调用后端API查询订单状态
          const queryResponse = await fetch("/api/payment/query", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Session-ID": sessionUUID,
            },
            body: JSON.stringify({
              order_id: orderId, // 传入订单号
            }),
          });

          const queryResult = await queryResponse.json();

          // 如果查询成功且返回了订单信息
          if (queryResult.success && queryResult.order) {
            const orderStatus = queryResult.order.status;

            // 支付成功（订单状态为 paid 或 completed）
            if (orderStatus === "paid" || orderStatus === "completed") {
              clearInterval(pollingInterval); // 停止轮询
              updatePaymentStatus("success", "支付成功！");

              // 延迟1秒后关闭弹窗并刷新页面
              setTimeout(async () => {
                Swal.close(); // 关闭当前弹窗
                await Swal.fire({
                  title: "支付成功！",
                  text: "欠费已清零，感谢您的支付",
                  icon: "success",
                  confirmButtonText: "确定",
                });

                // 刷新页面，重新加载用户数据
                // window.location.reload();
              }, 1000);
            }
            // 支付失败（订单状态为 failed 或 closed）
            else if (orderStatus === "failed" || orderStatus === "closed") {
              clearInterval(pollingInterval); // 停止轮询
              updatePaymentStatus("failed", "支付失败");
            }
            // 其他状态（pending等）继续轮询
          }
        } catch (error) {
          // 查询订单状态失败，记录错误但不中断轮询
          // 可能是网络波动导致的暂时性错误
          console.error("查询订单状态失败:", error);
        }
      }, 2000); // 每2秒（2000毫秒）查询一次
    },
    willClose: () => {
      // 弹窗关闭时停止轮询（无论是用户主动关闭还是支付完成自动关闭）
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    },
  });

  /**
   * 更新支付状态显示
   * 根据不同的状态显示不同的样式和文字
   * @param {String} status - 状态：success（成功）, failed（失败）, timeout（超时）
   * @param {String} message - 显示的消息
   */
  function updatePaymentStatus(status, message) {
    const indicator = document.getElementById("payment-status-indicator");
    if (!indicator) return; // 如果元素不存在，直接返回

    // 不同状态的样式配置
    const statusConfig = {
      success: {
        background: "#dcfce7", // 绿色背景
        border: "#22c55e", // 绿色边框
        color: "#14532d", // 深绿色文字
        icon: "✅", // 勾选图标
      },
      failed: {
        background: "#fee2e2", // 红色背景
        border: "#ef4444", // 红色边框
        color: "#7f1d1d", // 深红色文字
        icon: "❌", // 叉号图标
      },
      timeout: {
        background: "#f3f4f6", // 灰色背景
        border: "#9ca3af", // 灰色边框
        color: "#1f2937", // 深灰色文字
        icon: "⏱️", // 计时器图标
      },
    };

    // 获取对应状态的配置，如果状态不存在使用失败状态的配置
    const config = statusConfig[status] || statusConfig["failed"];

    // 更新元素样式
    indicator.style.background = config.background;
    indicator.style.borderColor = config.border;
    indicator.style.color = config.color;

    // 更新元素内容
    indicator.innerHTML = `
            <div style="font-size: 16px; font-weight: 600;">
                ${config.icon} ${escapeHtml(message)}
            </div>
        `;
  }
}

// ============================================================================
// 欠费检查功能 - 结束
// ============================================================================
// ============================================================================

// ============================================================================
// 欠费账号查询功能 - 开始
// ============================================================================

/**
 * 加载欠费账号列表（管理员功能）
 *
 * 功能说明：
 * - 调用后端API获取所有有欠费记录的学校账号
 * - 同时更新PC端和移动端的欠费账号列表
 * - 按欠费次数从高到低排序显示
 * - 提供查看详情按钮，可查看账号的完整备份信息
 *
 * 权限要求：
 * - 仅管理员（admin）和超级管理员（super_admin）可调用
 *
 * 使用场景：
 * - 管理员面板的"欠费查询"标签页加载时自动调用
 * - 点击"刷新"按钮手动调用
 *
 * @returns {Promise<void>}
 */
async function loadOverdueAccounts() {
  try {
    // ========== 调用后端API获取欠费账号列表 ==========
    // 发送GET请求到 /api/admin/overdue-accounts
    const response = await fetch("/api/admin/overdue-accounts", {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
      },
    });

    // 解析响应体为JSON对象
    const result = await response.json();

    // ========== 检查请求是否成功 ==========
    if (!result.success) {
      // 请求失败，显示错误提示
      showModalAlert(result.message || "加载欠费账号失败", "错误");
      return;
    }

    // ========== 获取欠费账号列表数据 ==========
    const accounts = result.accounts || [];

    // ========== 按 school_username 合并同一学校账号在多个所属账号下的重复条目 ==========
    // 同一 school_username 可能属于多个 auth_username，需要合并显示
    const mergedMap = new Map();
    accounts.forEach((account) => {
      const key = account.school_username;
      if (mergedMap.has(key)) {
        const existing = mergedMap.get(key);
        // 追加所属账号（去重），同时记录该账号是否为管理员
        if (
          !existing.auth_usernames.find((u) => u.name === account.auth_username)
        ) {
          existing.auth_usernames.push({
            name: account.auth_username,
            is_admin: !!account.is_admin,
          });
        }
        // has_backup 取任意一个有备份的即可
        if (account.has_backup) existing.has_backup = true;
      } else {
        mergedMap.set(key, {
          ...account,
          auth_usernames: [
            { name: account.auth_username, is_admin: !!account.is_admin },
          ],
        });
      }
    });
    const mergedAccounts = Array.from(mergedMap.values());

    // ========== 获取PC端和移动端的列表容器元素 ==========
    // PC端列表容器
    const pcList = document.getElementById("overdue-accounts-list");
    // 移动端列表容器
    const mobileList = document.getElementById("mobile-overdue-accounts-list");

    // ========== 构建HTML内容 ==========
    let pcHtml = "";
    let mobileHtml = "";

    // 检查是否有欠费账号
    if (mergedAccounts.length === 0) {
      // 没有欠费账号，显示提示信息
      pcHtml =
        '<div class="text-center py-10 text-slate-500">暂无欠费账号</div>';
      mobileHtml = pcHtml;
    } else {
      // 有欠费账号，遍历生成每个账号的卡片
      mergedAccounts.forEach((account) => {
        // 优先显示非管理员账号；若全部为管理员则显示为"(管理员)"
        const nonAdminOwners = account.auth_usernames
          .filter((u) => !u.is_admin)
          .map((u) => u.name);
        const ownersHtml =
          nonAdminOwners.length > 0
            ? escapeHtml(nonAdminOwners.join("、"))
            : "(管理员)";
        // PC端卡片：按钮与账号信息同行
        pcHtml += `
                    <div class="p-4 bg-white border border-slate-200 rounded-lg hover:shadow-md transition">
                        <div class="flex justify-between items-start">
                            <!-- 左侧：账号信息 -->
                            <div class="flex-1 min-w-0">
                                <!-- 账号姓名和欠费标签 -->
                                <div class="flex items-center gap-2">
                                    <!-- 姓名（加粗显示） -->
                                    <h4 class="font-bold text-slate-800">${escapeHtml(
                                      account.name,
                                    )}</h4>
                                    <!-- 欠费次数标签（红色背景） -->
                                    <span class="px-2 py-1 bg-red-100 text-red-700 text-xs rounded">
                                        欠费 ${account.overdue_count} 次
                                    </span>
                                </div>
                                <!-- 详细信息：学号 + 所属账号（多个时合并，换行不超出） -->
                                <p class="text-sm text-slate-600 mt-1 break-all">
                                    学号：${escapeHtml(account.student_id)} | 所属账号：${ownersHtml}
                                </p>
                            </div>
                            <!-- 右侧：操作按钮组 -->
                            <div class="flex gap-2 ml-2 flex-shrink-0">
                                <!-- 查看详情按钮：只有在有备份数据时才启用 -->
                                <button onclick="View_details_of_users_with_outstanding_payments(${escapeInlineJsArg(
                                  account.school_username,
                                )})"
                                        class="btn btn-sm btn-primary"
                                        ${
                                          !account.has_backup ? "disabled" : ""
                                        }>
                                    查看详情
                                </button>
                                <!-- 结清按钮：无论是否有备份数据都可以使用 -->
                                <!-- 使用 escapeHtml() 防止XSS攻击 -->
                                <!-- auth_username传空字符串，让后端自动查找该学校账号所属的用户 -->
                                <button onclick="adminClearOverdue(${escapeInlineJsArg(
                                  account.school_username,
                                )}, '', false)"
                                        class="px-3 py-1.5 bg-emerald-500 text-white text-xs rounded-lg hover:bg-emerald-600 transition-colors">
                                    结算
                                </button>
                            </div>
                        </div>
                    </div>
                `;
        // 移动端卡片：按钮独占一行，避免压缩文字
        mobileHtml += `
                    <div class="p-3 bg-white border border-slate-200 rounded-lg">
                        <!-- 账号信息 -->
                        <div class="mb-2">
                            <div class="flex items-center gap-2 flex-wrap">
                                <h4 class="font-bold text-slate-800 text-sm">${escapeHtml(
                                  account.name,
                                )}</h4>
                                <span class="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded">
                                    欠费 ${account.overdue_count} 次
                                </span>
                            </div>
                            <p class="text-xs text-slate-600 mt-1 break-all">
                                学号：${escapeHtml(account.student_id)}<br>所属账号：${ownersHtml}
                            </p>
                        </div>
                        <!-- 操作按钮独占一行 -->
                        <div class="flex gap-2">
                            <button onclick="View_details_of_users_with_outstanding_payments(${escapeInlineJsArg(
                              account.school_username,
                            )})"
                                    class="flex-1 py-2 px-3 bg-sky-500 text-white text-xs rounded-lg hover:bg-sky-600 active:bg-sky-700 transition-colors font-medium"
                                    ${!account.has_backup ? "disabled" : ""}>
                                查看详情
                            </button>
                            <button onclick="adminClearOverdue(${escapeInlineJsArg(
                              account.school_username,
                            )}, '', false)"
                                    class="flex-1 py-2 px-3 bg-emerald-500 text-white text-xs rounded-lg hover:bg-emerald-600 active:bg-emerald-700 transition-colors font-medium">
                                结算
                            </button>
                        </div>
                    </div>
                `;
      });
    }

    // ========== 更新页面显示 ==========
    // 更新PC端列表（如果容器存在）
    if (pcList) pcList.innerHTML = pcHtml;
    // 更新移动端列表（如果容器存在）
    if (mobileList) mobileList.innerHTML = mobileHtml;
  } catch (error) {
    // ========== 异常处理 ==========
    // 捕获网络错误等异常
    console.error("加载欠费账号失败:", error);
    showModalAlert("加载欠费账号失败", "错误");
  }
}

/**
 * 管理员添加欠费功能
 *
 * 【功能说明】
 * 允许管理员为指定的学校账号添加欠费次数。
 * 此功能使用 /api/admin/clear_overdue 接口，传递正数的 new_overdue_count 参数。
 *
 * 【业务逻辑】
 * 1. 从输入框获取学校账号和欠费次数
 * 2. 验证输入的有效性（账号不为空、欠费次数大于0）
 * 3. 弹出确认对话框，让管理员确认操作
 * 4. 调用后端API添加欠费
 * 5. 根据API返回结果显示成功或失败提示
 * 6. 操作成功后清空输入框
 *
 * 【安全机制】
 * - 后端接口有 @admin_required 装饰器，确保只有管理员可调用
 * - 使用 escapeHtml() 处理用户输入，防止XSS攻击
 * - 添加二次确认对话框，防止误操作
 *
 * 【注意事项】
 * - add_mode=true 表示叠加模式：将输入的次数累加到已有欠费次数上，而非覆盖
 * - auth_username 传空字符串，让后端自动查找该学校账号所属的用户
 *
 * @returns {Promise<void>}
 */
async function adminAddOverdue() {
  try {
    // ========== 步骤1：获取并验证输入值 ==========

    // 获取输入框中的学校账号，并去除首尾空格
    const schoolUsername = document
      .getElementById("admin-add-overdue-school-username")
      .value.trim();

    // 获取输入框中的欠费次数，并转换为整数
    // parseInt() 将字符串转换为整数，如果转换失败返回 NaN
    const overdueCount = parseInt(
      document.getElementById("admin-add-overdue-count").value,
    );

    // ========== 验证学校账号是否为空 ==========
    if (!schoolUsername) {
      // 如果学校账号为空，弹出警告对话框
      await Swal.fire({
        title: "输入错误",
        text: "请输入学校账号",
        icon: "warning",
        confirmButtonText: "确定",
      });
      // 提前返回，不继续执行后续代码
      return;
    }

    // ========== 验证欠费次数是否有效 ==========
    // 检查是否为有效数字且大于等于1
    if (!overdueCount || overdueCount < 1) {
      // 如果欠费次数无效，弹出警告对话框
      await Swal.fire({
        title: "输入错误",
        text: "请输入有效的欠费次数（大于0）",
        icon: "warning",
        confirmButtonText: "确定",
      });
      // 提前返回
      return;
    }

    // ========== 步骤2：显示确认对话框 ==========

    // 弹出确认对话框，让管理员再次确认操作
    // 这是一个重要的安全机制，防止误操作
    const confirmResult = await Swal.fire({
      title: "确认添加欠费",
      // 使用 HTML 格式显示详细信息
      // escapeHtml() 函数用于防止XSS攻击（转义特殊字符）
      html: `
                <p>学校账号：<strong>${escapeHtml(schoolUsername)}</strong></p>
                <p>欠费次数：<strong>${overdueCount}</strong></p>
            `,
      icon: "question",
      showCancelButton: true, // 显示取消按钮
      confirmButtonText: "确认添加",
      cancelButtonText: "取消",
    });

    // ========== 检查用户是否点击了取消按钮 ==========
    if (!confirmResult.isConfirmed) {
      // 如果用户点击了取消按钮，直接返回，不执行添加操作
      return;
    }

    // ========== 步骤3：显示加载动画 ==========

    // 显示"正在处理"的加载动画，防止用户重复点击
    Swal.fire({
      title: "正在处理...",
      text: "请稍候",
      allowOutsideClick: false, // 禁止点击外部区域关闭对话框
      didOpen: () => {
        // 对话框打开后显示加载动画
        Swal.showLoading();
      },
    });

    // ========== 步骤4：调用后端API添加欠费 ==========

    // 发送POST请求到 /api/admin/clear_overdue
    const response = await fetch("/api/admin/clear_overdue", {
      method: "POST",
      headers: {
        "Content-Type": "application/json", // 指定请求体格式为JSON
        "X-Session-ID": sessionUUID, // 传递会话ID用于身份验证
      },
      // 将请求数据转换为JSON字符串
      body: JSON.stringify({
        school_username: schoolUsername, // 学校账号
        auth_username: "", // 空字符串，让后端自动查找该学校账号所属的用户
        new_overdue_count: overdueCount, // 欠费次数（叠加到已有欠费次数上）
        add_mode: true, // 叠加模式：累加而非覆盖
      }),
    });

    // 解析响应体为JSON对象
    const result = await response.json();

    // ========== 步骤5：根据API返回结果显示提示 ==========

    if (result.success) {
      // ========== 操作成功 ==========

      // 弹出成功提示对话框
      await Swal.fire({
        title: "添加成功",
        text: `已为账号 ${schoolUsername} 添加 ${overdueCount} 次欠费`,
        icon: "success",
        confirmButtonText: "确定",
      });

      // ========== 步骤6：清空输入框 ==========
      // 操作成功后清空输入框，方便管理员继续添加其他账号的欠费
      document.getElementById("admin-add-overdue-school-username").value = "";
      document.getElementById("admin-add-overdue-count").value = "";

      // ========== 步骤7：刷新欠费账号列表 ==========
      // 调用 loadOverdueAccounts() 函数重新加载欠费账号列表
      // 这样可以立即看到新添加的欠费记录
      await loadOverdueAccounts();
    } else {
      // ========== 操作失败 ==========

      // 弹出失败提示对话框，显示后端返回的错误信息
      await Swal.fire({
        title: "添加失败",
        text: result.message || "未知错误", // 如果message字段为空，显示"未知错误"
        icon: "error",
        confirmButtonText: "确定",
      });
    }
  } catch (error) {
    // ========== 异常处理 ==========

    // 捕获所有异常（如网络错误、JSON解析失败等）
    console.error("添加欠费失败:", error);

    // 弹出错误提示对话框
    await Swal.fire({
      title: "添加失败",
      text: "网络错误或服务器异常",
      icon: "error",
      confirmButtonText: "确定",
    });
  }
}

async function mobileAdminAddOverdue() {
  const schoolUsername = (
    document.getElementById("mobile-add-overdue-school-username")?.value || ""
  ).trim();
  const overdueCount = parseInt(
    document.getElementById("mobile-add-overdue-count")?.value || "",
  );

  if (!schoolUsername) {
    await Swal.fire({
      title: "输入错误",
      text: "请输入学校账号",
      icon: "warning",
      confirmButtonText: "确定",
    });
    return;
  }
  if (!overdueCount || overdueCount < 1) {
    await Swal.fire({
      title: "输入错误",
      text: "请输入有效的欠费次数（大于0）",
      icon: "warning",
      confirmButtonText: "确定",
    });
    return;
  }

  const confirmResult = await Swal.fire({
    title: "确认添加欠费",
    html: `<p>学校账号：<strong>${escapeHtml(schoolUsername)}</strong></p><p>欠费次数：<strong>${overdueCount}</strong></p>`,
    icon: "question",
    showCancelButton: true,
    confirmButtonText: "确认添加",
    cancelButtonText: "取消",
  });
  if (!confirmResult.isConfirmed) return;

  Swal.fire({
    title: "正在处理...",
    text: "请稍候",
    allowOutsideClick: false,
    didOpen: () => Swal.showLoading(),
  });

  try {
    const response = await fetch("/api/admin/clear_overdue", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        school_username: schoolUsername,
        auth_username: "",
        new_overdue_count: overdueCount,
        add_mode: true, // 叠加模式：累加而非覆盖
      }),
    });
    const result = await response.json();

    if (result.success) {
      await Swal.fire({
        title: "添加成功",
        text: `已为账号 ${schoolUsername} 添加 ${overdueCount} 次欠费`,
        icon: "success",
        confirmButtonText: "确定",
      });
      const usernameEl = document.getElementById(
        "mobile-add-overdue-school-username",
      );
      const countEl = document.getElementById("mobile-add-overdue-count");
      if (usernameEl) usernameEl.value = "";
      if (countEl) countEl.value = "";
      await loadOverdueAccounts();
    } else {
      await Swal.fire({
        title: "添加失败",
        text: result.message || "未知错误",
        icon: "error",
        confirmButtonText: "确定",
      });
    }
  } catch (error) {
    console.error("移动端添加欠费失败:", error);
    await Swal.fire({
      title: "添加失败",
      text: "网络错误或服务器异常",
      icon: "error",
      confirmButtonText: "确定",
    });
  }
}

/**
 * 查看账号备份详情（美化版）
 * 解析后端返回的 JSON 数据并友好展示
 */
async function View_details_of_users_with_outstanding_payments(
  school_username,
) {
  // 显示加载动画
  Swal.fire({
    title: "正在获取数据",
    text: "请稍候...",
    allowOutsideClick: false,
    didOpen: () => {
      Swal.showLoading();
    },
  });

  try {
    const response = await fetch(
      `/api/admin/backup-info?school_username=${encodeURIComponent(
        school_username,
      )}`,
      {
        method: "GET",
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );
    const result = await response.json();

    if (result.success) {
      let data = result.data;
      // 如果data是字符串，尝试解析
      if (typeof data === "string") {
        try {
          data = JSON.parse(data);
        } catch (e) {
          console.error("JSON解析失败", e);
        }
      }

      // 获取实时欠费/统计信息，以 API 为准
      try {
        const statsResponse = await fetch("/api/school_account/stats", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-ID": sessionUUID,
          },
          body: JSON.stringify({ school_username: school_username }),
        });
        const statsResult = await statsResponse.json();
        if (statsResult.success && statsResult.data) {
          // 覆盖备份数据中的统计信息 (欠费次数和完成次数)
          // 如果API返回的数据中存在这些字段，则优先使用API的数据
          if (statsResult.data.overdue_count !== undefined) {
            data.overdue_count = statsResult.data.overdue_count;
          }
          if (statsResult.data.completed_count !== undefined) {
            data.completed_count = statsResult.data.completed_count;
          }
          console.log(
            `[View_details_of_users_with_outstanding_payments] 已更新 ${school_username} 的实时统计: 欠费=${data.overdue_count}, 完成=${data.completed_count}`,
          );
        }
      } catch (e) {
        console.warn(
          "[View_details_of_users_with_outstanding_payments] 获取实时统计失败，将显示备份中的旧数据:",
          e,
        );
      }

      // 格式化数据的辅助函数
      const formatTime = (ts) => {
        if (!ts) return "未知";
        // 如果是时间戳（数字），假定为秒
        if (typeof ts === "number") return new Date(ts * 1000).toLocaleString();
        return ts; // 如果已经是字符串
      };
      const safeStr = (str) =>
        str === null || str === undefined || str === "" ? "-" : str;

      // 提取关键数据对象
      const backupTime = formatTime(data.backup_timestamp);
      const dept = data.deptInfo || {};
      const user = data.userInfo || {};

      const studentNumber = String(dept.studentNum || dept.account || "").trim();
      let linkedUsers = [];
      if (studentNumber) {
        try {
          const linkedResp = await fetch(
            `/api/admin/school-account-linked-users?student_number=${encodeURIComponent(studentNumber)}`,
            { headers: { "X-Session-ID": sessionUUID } },
          );
          const linkedResult = await linkedResp.json();
          if (linkedResult.success && Array.isArray(linkedResult.users)) {
            linkedUsers = linkedResult.users;
          }
        } catch (e) {
          console.warn("[View_details] 获取关联账号失败:", e);
        }
      }

      const linkedUsersHtml = linkedUsers.length
        ? linkedUsers
            .map(
              (item) => `
                <div class="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                  <div class="text-xs text-slate-700 font-medium">${escapeHtml(item.username || "-")}</div>
                  <div class="text-[11px] text-slate-500 mt-1">昵称：${escapeHtml(item.nickname || "-")}</div>
                  <div class="text-[11px] text-slate-500">手机号：${escapeHtml(item.phone || "未绑定")}</div>
                  <div class="text-[11px] text-slate-500">学校账号：${escapeHtml(item.school_username || "-")}</div>
                </div>`,
            )
            .join("")
        : '<div class="text-xs text-slate-400 text-center py-3">暂无关联账号</div>';

      // 获取该学校账号的账单记录
      let billingRecords = [];
      try {
        const billResp = await fetch(
          `/api/admin/billing/list?school_username=${encodeURIComponent(school_username)}`,
          { headers: { "X-Session-ID": sessionUUID } },
        );
        const billResult = await billResp.json();
        if (billResult.success) {
          billingRecords = billResult.records || [];
        }
      } catch (e) {
        console.warn("[View_details] 获取账单记录失败:", e);
      }

      // 构建账单卡片 HTML
      const buildBillingCardsHtml = (records) => {
        if (!records.length) {
          return `<div class="text-xs text-slate-400 text-center py-3">暂无账单记录</div>`;
        }
        const statusLabel = (s) => {
          if (s === "paid")
            return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-800">✓ 已支付</span>`;
          if (s === "admin_cleared")
            return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-sky-100 text-sky-800">✓ 管理员清除</span>`;
          return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800">⏳ 待支付</span>`;
        };
        return records
          .map(
            (r) => `
          <div class="bg-white border border-slate-200 rounded-xl p-3 shadow-sm mb-2">
            <div class="flex items-center justify-between mb-2">
              <div>
                <div class="text-[10px] text-slate-400">创建时间</div>
                <div class="text-xs text-slate-700">${escapeHtml(_fmtBillTime(_getBillingTime(r, "created_at")) || "-")}</div>
              </div>
              ${statusLabel(r.status)}
            </div>
            <div class="text-[10px] text-slate-400 mb-0.5">描述</div>
            <div class="text-xs text-slate-800 mb-2">${escapeHtml(r.reason || "-")}</div>
            <div class="flex items-center justify-between">
              <div>
                <span class="text-[10px] text-slate-400">金额：</span>
                <span class="text-sm font-bold ${r.status === "paid" ? "text-green-600" : "text-amber-600"}">${r.amount != null ? "¥" + escapeHtml(String(r.amount)) : "-"}</span>
              </div>
              ${r.status === "pending" ? `<button onclick="Swal.close();paySingleBilling(${escapeInlineJsArg("admin-billing-list-container")}, ${escapeInlineJsArg(r.billing_id || "")}, ${escapeInlineJsArg(r.school_username || "")})" class="px-2 py-1 text-[11px] bg-emerald-100 hover:bg-emerald-200 text-emerald-700 rounded-md border border-emerald-200 transition-colors">支付</button>` : ""}
            </div>
          </div>`,
          )
          .join("");
      };

      // 构建HTML内容 - 使用现代化的渐变背景和卡片设计
      const htmlContent = `
                <div class="text-left space-y-4 font-sans text-sm max-h-[65vh] overflow-y-auto px-1 pr-2">
                    
                    <!-- 统计卡片 - 使用渐变背景和阴影效果 -->
                    <div class="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-xl shadow-lg border border-blue-100">
                        <div class="flex justify-between items-center">
                            <!-- 备份时间信息 -->

                            <div class="flex flex-col">
                                <span class="text-xs text-indigo-600 font-medium mb-1">
                                    📅 备份时间
                                </span>
                                <span class="font-bold text-slate-800 text-xs">${backupTime}</span>
                            </div>
                            
                            <!-- 统计数据区域 -->
                            <div class="flex gap-6 items-center">
                                <!-- 欠费统计 -->
                                <div class="text-center">
                                    <div class="text-3xl font-bold ${
                                      data.overdue_count > 0
                                        ? "text-red-500"
                                        : "text-green-500"
                                    } mb-1">
                                        ${data.overdue_count}
                                    </div>
                                    <div class="text-xs text-slate-600 font-medium">欠费次数</div>
                                </div>
                                
                                <!-- 分隔线 -->
                                <div class="h-12 w-px bg-slate-300"></div>
                                
                                <!-- 完成统计 -->
                                <div class="text-center">
                                    <div class="text-3xl font-bold text-blue-500 mb-1">
                                        ${data.completed_count}
                                    </div>
                                    <div class="text-xs text-slate-600 font-medium">已完成</div>
                                </div>
                            </div>
                            
                            <!-- 结清按钮 - 只在有欠费时显示 -->
                            ${
                              data.overdue_count > 0
                                ? `
                                <button onclick="adminClearOverdue(${escapeInlineJsArg(
                                  school_username,
                                )}, ${escapeInlineJsArg(user.username || "")})"
                                    class="ml-3 px-4 py-2 bg-gradient-to-r from-emerald-500 to-green-500 text-white text-xs font-bold rounded-lg hover:from-emerald-600 hover:to-green-600 active:from-emerald-700 active:to-green-700 transition-all shadow-md hover:shadow-lg transform hover:-translate-y-0.5"
                                    title="管理员：清除此账号的欠费">
                                    <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                                    </svg>
                                    结算欠费
                                </button>
                            `
                                : `
                                <div class="ml-3 px-4 py-2 bg-green-100 text-green-700 text-xs font-bold rounded-lg">
                                    ✓ 无欠费
                                </div>
                            `
                            }
                        </div>
                    </div>

                    <div class="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <!-- 表单标题栏 - 使用渐变背景和图标 -->
                        <div class="bg-gradient-to-r from-blue-50 via-purple-50 to-white px-3 py-2 border-b border-blue-100 flex items-center gap-2">
                            <!-- 图标容器：使用带背景的圆角方块 -->
                            <div class="p-1 bg-gradient-to-br from-blue-100 to-purple-100 rounded text-blue-600">
                                <!-- SVG图标：用户信息图标 -->
                                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
                                </svg>
                            </div>
                            <!-- 标题文本 -->
                            <span class="font-bold text-blue-800 text-xs">账号详细信息</span>
                        </div>
                        
                        <!-- 表单内容区域 - 使用Grid布局自动调整列数 -->
                        <!-- grid-cols-2: 默认2列布局 -->
                        <!-- gap-y-3: 行间距3单位 -->
                        <!-- gap-x-2: 列间距2单位 -->
                        <div class="p-3 grid grid-cols-2 gap-y-3 gap-x-2 text-slate-700 bg-white">
                            
                            <!-- ========== 基本信息部分 ========== -->
                            
                            <!-- 姓名字段 -->
                            <div>
                                <!-- 字段标签：小写字母、灰色、上边距 -->
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">姓名</span>
                                <!-- 字段值：中等字重，使用safeStr确保安全显示 -->
                                <span class="font-medium">${safeStr(
                                  dept.name,
                                )}</span>
                            </div>
                            
                            <!-- 学号字段 -->
                            <div>
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">学号</span>
                                <!-- 学号使用等宽字体，背景高亮显示 -->
                                <span class="font-mono text-xs bg-slate-100 px-1.5 py-0.5 rounded">${safeStr(
                                  dept.studentNum || dept.account,
                                )}</span>
                            </div>
                            
                            <!-- 学校字段 - 占据整行 -->
                            <!-- col-span-2: 跨越2列 -->
                            <!-- border-t: 上边框分隔线 -->
                            <div class="col-span-2 border-t border-dashed border-slate-100 pt-2">
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">学校</span>
                                <span class="font-medium">${safeStr(
                                  dept.schoolName,
                                )}</span>
                            </div>
                            
                            <!-- 性别字段 -->
                            <div>
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">性别</span>
                                <span>${safeStr(dept.sexValue)}</span>
                            </div>
                            
                            <!-- 身份字段 -->
                            <div>
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">身份</span>
                                <span>${safeStr(dept.typeValue)}</span>
                            </div>
                            
                            <!-- ========== 账号状态部分（合并原"账号详情"卡片的内容）========== -->
                            
                            <!-- 账号状态字段 - 使用彩色标签显示 -->
                            <div>
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">状态</span>
                                <!-- 根据status值显示不同颜色的标签 -->
                                <!-- status === 1: 绿色"正常"标签 -->
                                <!-- status !== 1: 红色"异常"标签 -->
                                ${
                                  user.status === 1
                                    ? '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-800">正常</span>'
                                    : '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-800">异常</span>'
                                }
                            </div>
                            
                            <!-- 占位div，保持2列布局的对称性 -->
                            <div></div>
                            
                            <!-- 注册时间字段 - 占据整行 -->
                            <div class="col-span-2">
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">注册时间</span>
                                <span class="text-xs text-slate-600">${safeStr(
                                  user.createtime,
                                )}</span>
                            </div>
                            
                            <!-- 首次登录字段 - 占据整行 -->
                            <div class="col-span-2">
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">首次登录</span>
                                <span class="text-xs text-slate-600">${safeStr(
                                  user.firstlogin,
                                )}</span>
                            </div>
                            
                            <!-- 最近登录字段 - 占据整行 -->
                            <div class="col-span-2">
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">最近登录 (APP)</span>
                                <span class="text-xs text-slate-600">${safeStr(
                                  dept.logintime,
                                )}</span>
                            </div>
                            
                            <!-- 账号密码字段 - 占据整行，使用边框分隔 -->
                            <div class="col-span-2 pt-1 border-t border-dashed border-slate-100">
                                <span class="text-slate-400 text-[10px] block mb-0.5 uppercase tracking-wide">账号密码</span>
                                <!-- 密码显示区域：使用flex布局，包含密码文本和"明文"标签 -->
                                <div class="flex items-center gap-2">
                                    <!-- 密码文本：使用等宽字体，可全选，背景和边框高亮 -->
                                    <span class="font-mono bg-slate-100 border border-slate-200 px-2 py-1 rounded text-slate-600 select-all">${safeStr(
                                      user.text_password,
                                    )}</span>
                                    <!-- "明文"标签：提示用户这是明文密码 -->
                                    <span class="text-[10px] text-slate-400">(明文)</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-gradient-to-r from-cyan-50 via-sky-50 to-white px-3 py-2 border-b border-cyan-100 flex items-center gap-2">
                            <div class="p-1 bg-gradient-to-br from-cyan-100 to-sky-100 rounded text-cyan-600">
                                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5V4H2v16h5m10 0v-2a4 4 0 00-4-4H9a4 4 0 00-4 4v2m12 0H7m10-10a4 4 0 11-8 0 4 4 0 018 0z"/>
                                </svg>
                            </div>
                            <span class="font-bold text-cyan-800 text-xs">关联账号</span>
                        </div>
                        <div class="p-3 space-y-2">
                            ${linkedUsersHtml}
                        </div>
                    </div>

                    <div class="border border-slate-200 rounded-lg overflow-hidden">
                        <button onclick="const el = this.nextElementSibling; el.classList.toggle('hidden'); this.querySelector('svg').style.transform = el.classList.contains('hidden') ? 'rotate(0deg)' : 'rotate(180deg)';" 
                                class="w-full text-left px-3 py-2 bg-slate-50 text-xs text-slate-500 flex justify-between items-center hover:bg-slate-100 transition cursor-pointer">
                            <span>原始 JSON 数据</span>
                            <svg class="w-3 h-3 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                        </button>
                        <div class="hidden bg-slate-800 p-0">
                            <pre class="text-[10px] text-green-400 font-mono whitespace-pre-wrap break-all p-3 max-h-40 overflow-auto">${JSON.stringify(
                              data,
                              null,
                              2,
                            )}</pre>
                        </div>
                    </div>

                    <!-- 账单记录卡片区域 -->
                    <div class="border border-slate-200 rounded-lg overflow-hidden shadow-sm">
                        <div class="bg-gradient-to-r from-amber-50 via-orange-50 to-white px-3 py-2 border-b border-amber-100 flex items-center gap-2">
                            <div class="p-1 bg-gradient-to-br from-amber-100 to-orange-100 rounded text-amber-600">
                                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                                </svg>
                            </div>
                            <span class="font-bold text-amber-800 text-xs">账单记录（共 ${billingRecords.length} 条）</span>
                        </div>
                        <div class="p-3">
                            ${buildBillingCardsHtml(billingRecords)}
                        </div>
                    </div>
                </div>
            `;

      Swal.fire({
        title: `${dept.name || school_username}`,
        html: htmlContent,
        width: "480px",
        showConfirmButton: true,
        confirmButtonText: "关闭",
        confirmButtonColor: "#3b82f6",
        customClass: {
          popup: "rounded-2xl",
          title: "text-lg font-bold text-slate-800 pt-4 pb-0",
          htmlContainer: "!px-4 !pb-4 !pt-2 !overflow-visible !m-0 w-full",
        },
      });
    } else {
      // 备份数据不存在或无权限时，使用新的轻量详情视图（仅展示姓名 + 账单）
      const resolvedName = await fetchSchoolAccountName(school_username);

      // 获取该账号账单记录（非管理员走 /api/billing/list，管理员走 /api/admin/billing/list）
      let fallbackBills = [];
      try {
        const billResp = await fetch(
          `/api/billing/list?school_username=${encodeURIComponent(school_username)}`,
          { headers: { "X-Session-ID": sessionUUID } },
        );
        const billData = await billResp.json();
        if (billData.success) fallbackBills = billData.records || [];
      } catch (_e) {}

      const statusLabelFb = (s) => {
        if (s === "paid")
          return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-800">✓ 已支付</span>`;
        if (s === "admin_cleared")
          return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-sky-100 text-sky-800">✓ 管理员清除</span>`;
        return `<span class="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800">⏳ 待支付</span>`;
      };
      const billCardsHtmlFb = fallbackBills.length
        ? fallbackBills
            .map(
              (r) => `
          <div class="bg-white border border-slate-200 rounded-xl p-3 shadow-sm mb-2">
            <div class="flex items-center justify-between mb-2">
              <div class="text-xs text-slate-600">${escapeHtml(_fmtBillTime(_getBillingTime(r, "created_at")) || "-")}</div>
              ${statusLabelFb(r.status)}
            </div>
            <div class="text-[11px] text-slate-400 mb-0.5">描述</div>
            <div class="text-xs text-slate-800 mb-2">${escapeHtml(r.reason || "-")}</div>
            <div class="flex items-center justify-between">
              <span class="text-[10px] text-slate-400">金额：</span>
              <span class="text-sm font-bold ${r.status === "pending" ? "text-amber-600" : "text-green-600"}">${r.amount != null ? "¥" + escapeHtml(String(r.amount)) : "-"}</span>
            </div>
          </div>`,
            )
            .join("")
        : `<div class="text-xs text-slate-400 text-center py-3">暂无账单记录</div>`;

      Swal.fire({
        title: resolvedName || school_username,
        html: `
          <div class="text-left space-y-3 max-h-[60vh] overflow-y-auto px-1 pr-2">
            <div class="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-600">
              <div class="text-[10px] text-slate-400 mb-0.5">学校账号</div>
              <div class="font-mono font-semibold text-slate-800">${escapeHtml(school_username)}</div>
              ${resolvedName ? `<div class="text-[10px] text-slate-400 mt-1.5 mb-0.5">姓名</div><div class="font-medium text-slate-800">${escapeHtml(resolvedName)}</div>` : ""}
            </div>
            <div class="border border-slate-200 rounded-lg overflow-hidden">
              <div class="bg-amber-50 px-3 py-2 border-b border-amber-100 text-xs font-bold text-amber-800">
                账单记录（共 ${fallbackBills.length} 条）
              </div>
              <div class="p-3">${billCardsHtmlFb}</div>
            </div>
          </div>`,
        width: "420px",
        showConfirmButton: true,
        confirmButtonText: "关闭",
        confirmButtonColor: "#3b82f6",
        customClass: {
          popup: "rounded-2xl",
          title: "text-lg font-bold text-slate-800 pt-4 pb-0",
          htmlContainer: "!px-4 !pb-4 !pt-2 !overflow-visible !m-0 w-full",
        },
      });
    }
  } catch (error) {
    console.error("获取备份失败:", error);
    Swal.fire({
      icon: "error",
      title: "获取失败",
      text: "网络请求出错或数据解析失败",
      confirmButtonText: "确定",
    });
  }
}

/**
 * 管理员清除欠费功能
 *
 * 功能说明：
 * 此函数允许管理员修改指定用户的指定学校账号的欠费次数。
 * 可以清零欠费（设置为0），也可以设置为其他非负整数。
 *
 * 工作流程：
 * 1. 显示输入对话框，让管理员输入新的欠费次数
 * 2. 验证输入是否为有效的非负整数
 * 3. 调用后端API执行修改操作
 * 4. 显示操作结果并刷新界面
 *
 * @param {string} school_username - 学校账号用户名（如：2021001）
 * @param {string} auth_username - 账号所属用户名（认证系统中的用户名）
 *
 * @returns {Promise<void>} - 无返回值（异步函数）
 *
 * 使用场景：
 * - 用户线下支付后，管理员手动清零欠费
 * - 系统误判导致欠费错误，管理员纠正数据
 * - 特殊情况需要调整欠费次数
 */
async function adminClearOverdue(
  school_username,
  auth_username = "",
  is_detail_view = true,
) {
  try {
    // ========== 步骤1：加载该学校账号的待支付账单 ==========
    Swal.fire({
      title: "加载账单中...",
      allowOutsideClick: false,
      didOpen: () => { Swal.showLoading(); },
    });

    const resp = await fetch(
      "/api/admin/billing/list?school_username=" + encodeURIComponent(school_username),
      { headers: { "X-Session-ID": sessionUUID } }
    );
    const data = await resp.json();

    if (!data.success) {
      await Swal.fire({
        title: "加载失败",
        text: data.message || "未知错误",
        icon: "error",
        confirmButtonText: "确定",
      });
      return;
    }

    const pendingBills = (data.records || []).filter(r => r.status === "pending");

    if (pendingBills.length === 0) {
      await Swal.fire({
        title: "无待支付账单",
        text: `学校账号 ${school_username} 暂无待支付账单`,
        icon: "info",
        confirmButtonText: "确定",
      });
      return;
    }

    // ========== 步骤2：显示账单选择弹窗 ==========
    const billRows = pendingBills.map((r, i) => {
      const amount = r.amount != null ? "¥" + r.amount : "-";
      const reason = (r.reason || "-").replace(/</g, "&lt;").replace(/>/g, "&gt;");
      const created = _getBillingTime(r, "created_at");
      return `
        <tr style="border-bottom:1px solid #e2e8f0;">
          <td style="padding:6px 8px;text-align:center;">
            <input type="checkbox" id="clear-bill-${i}" data-billing-id="${(r.billing_id || "").replace(/"/g, "&quot;")}" class="admin-clear-bill-check" checked style="width:14px;height:14px;accent-color:#0ea5e9;">
          </td>
          <td style="padding:6px 8px;font-size:12px;color:#334155;">${reason}</td>
          <td style="padding:6px 8px;font-size:12px;color:#334155;font-weight:600;white-space:nowrap;">${amount}</td>
          <td style="padding:6px 8px;font-size:11px;color:#94a3b8;white-space:nowrap;">${created}</td>
        </tr>`;
    }).join("");

    const result = await Swal.fire({
      title: "结算欠费账单",
      html: `
        <p style="font-size:13px;color:#475569;margin-bottom:6px;">学校账号：<strong>${school_username}</strong></p>
        <p style="font-size:12px;color:#94a3b8;margin-bottom:10px;">勾选要清除的账单，确认后标记为管理员清除</p>
        <div style="overflow-x:auto;max-height:300px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:6px;">
          <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <thead>
              <tr style="background:#f1f5f9;position:sticky;top:0;">
                <th style="padding:6px 8px;text-align:center;">
                  <input type="checkbox" id="clear-bill-all" checked
                    onchange="document.querySelectorAll('.admin-clear-bill-check').forEach(c=>c.checked=this.checked)"
                    style="accent-color:#0ea5e9;">
                </th>
                <th style="padding:6px 8px;text-align:left;color:#64748b;">原因</th>
                <th style="padding:6px 8px;text-align:left;color:#64748b;white-space:nowrap;">金额</th>
                <th style="padding:6px 8px;text-align:left;color:#64748b;white-space:nowrap;">创建时间</th>
              </tr>
            </thead>
            <tbody>${billRows}</tbody>
          </table>
        </div>`,
      showCancelButton: true,
      confirmButtonText: "确认清除",
      cancelButtonText: "取消",
      confirmButtonColor: "#0ea5e9",
      width: "520px",
      preConfirm: () => {
        const selected = [...document.querySelectorAll(".admin-clear-bill-check")].filter(c => c.checked);
        if (selected.length === 0) {
          Swal.showValidationMessage("请至少选择一条账单");
          return false;
        }
        return selected.map(c => c.dataset.billingId);
      },
    });

    if (!result.isConfirmed) return;

    const selectedIds = result.value;

    // ========== 步骤3：依次调用账单更新接口 ==========
    Swal.fire({
      title: "正在清除...",
      text: `共 ${selectedIds.length} 条账单`,
      allowOutsideClick: false,
      didOpen: () => { Swal.showLoading(); },
    });

    let successCount = 0;
    let failCount = 0;
    for (const billingId of selectedIds) {
      try {
        const updateResp = await fetch("/api/admin/billing/update", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-ID": sessionUUID,
          },
          body: JSON.stringify({
            billing_id: billingId,
            school_username: school_username,
            status: "admin_cleared",
          }),
        });
        const updateResult = await updateResp.json();
        if (updateResult.success) {
          successCount++;
        } else {
          failCount++;
        }
      } catch {
        failCount++;
      }
    }

    // ========== 步骤4：显示结果 ==========
    const msg = failCount === 0
      ? `已成功清除 ${successCount} 条账单`
      : `成功 ${successCount} 条，失败 ${failCount} 条`;

    await Swal.fire({
      title: failCount === 0 ? "清除成功" : "部分完成",
      text: msg,
      icon: failCount === 0 ? "success" : "warning",
      confirmButtonText: "确定",
    });

    // ========== 步骤5：刷新页面显示 ==========
    if (typeof loadOverdueAccounts === "function") loadOverdueAccounts();
    if (is_detail_view && typeof View_details_of_users_with_outstanding_payments === "function") {
      await View_details_of_users_with_outstanding_payments(school_username);
    }
    if (typeof loadAdminBillingList === "function") loadAdminBillingList();
  } catch (error) {
    console.error("管理员清除欠费失败:", error);
    await Swal.fire({
      title: "操作失败",
      text: "网络错误或服务器异常",
      icon: "error",
      confirmButtonText: "确定",
    });
  }
}

// ============================================================================
// 欠费账号查询功能 - 结束

// ============================================================================
// 订单号自动获取金额并填充退款金额功能 - 开始
// ============================================================================

/**
 * 初始化订单号输入框的自动填充功能
 * 功能说明：
 * 1. 为订单号输入框添加input事件监听
 * 2. 当用户输入完订单号后，自动获取订单金额
 * 3. 检查是否已退款（一个订单只能退款一次）
 * 4. 计算金额的80%并填充到退款金额输入框
 *
 * 调用时机：
 * - 页面加载完成后自动初始化
 *
 * 实现细节：
 * - 监听订单号输入框的input事件
 * - 进行订单号格式校验（长度、字符等）
 * - 调用后端API获取订单信息
 * - 检查订单是否已退款
 * - 计算80%金额并自动填充
 * - 提供友好的错误提示
 */
function initOrderNumberAutoFill() {
  // 获取订单号输入框DOM元素
  const tradeNoInput = document.getElementById(
    "admin-refund-order-trade-no_modal",
  );

  // 如果输入框不存在，记录错误并退出
  if (!tradeNoInput) {
    console.error("[订单号自动填充] 未找到订单号输入框元素");
    return;
  }

  // 为订单号输入框添加input事件监听
  // 使用防抖（debounce）技术，避免频繁触发API请求
  let debounceTimer = null; // 防抖计时器

  tradeNoInput.addEventListener("input", function (event) {
    // 清除之前的防抖计时器
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    // 获取用户输入的订单号（去除首尾空格）
    const tradeNo = event.target.value.trim();

    // 如果订单号为空，清空退款金额输入框并退出
    if (!tradeNo) {
      const amountInput = document.getElementById("admin-refund-amount_modal");
      if (amountInput) {
        amountInput.value = "";
      }
      return;
    }

    // 设置防抖计时器：用户停止输入500毫秒后才触发查询
    // 这样可以避免用户输入过程中频繁调用API，提升性能和用户体验
    debounceTimer = setTimeout(async () => {
      // 调用订单号校验和金额获取函数
      await fetchOrderAmountAndFill(tradeNo);
    }, 500); // 500毫秒的防抖延迟
  });

  console.log("[订单号自动填充] 初始化完成");
}

/**
 * 根据订单号获取订单金额并填充80%到退款金额输入框
 * 功能说明：
 * 1. 校验订单号格式（长度、字符等）
 * 2. 调用后端API查询订单信息
 * 3. 检查是否已退款（一个订单只能退款一次）
 * 4. 获取订单金额
 * 5. 计算金额的80%
 * 6. 自动填充到退款金额输入框
 * 7. 提供详细的错误提示
 *
 * @param {string} tradeNo - 订单号
 *
 * @returns {Promise<void>} 无返回值的Promise
 *
 * API端点：/api/payment/orders
 * 请求方法：GET
 * 查询参数：page=1&per_page=1000&status=all（获取所有订单）
 *
 * 返回数据格式：
 * {
 *   success: boolean,
 *   orders: [
 *     {
 *       order_trade_no: string,  // 订单号
 *       amount: number,          // 订单金额
 *       status: string,          // 订单状态
 *       ...
 *     }
 *   ],
 *   total: number,
 *   page: number,
 *   per_page: number
 * }
 */
async function fetchOrderAmountAndFill(tradeNo) {
    console.log("[订单号自动填充] 开始处理订单号");

  // ========== 步骤1：订单号格式校验 ==========

  // 校验订单号长度（通常订单号长度在10-50个字符之间）
  if (tradeNo.length < 10) {
    console.warn("[订单号自动填充] 订单号长度过短，跳过查询");
    return; // 不显示错误提示，因为用户可能还在输入
  }

  if (tradeNo.length > 100) {
    console.warn("[订单号自动填充] 订单号长度过长");
    showModalAlert("订单号长度不能超过100个字符", "格式错误");
    return;
  }

  // 校验订单号字符（只允许字母、数字、下划线、连字符）
  // 这是一个基本的格式校验，具体格式取决于支付平台的规范
  const validPattern = /^[A-Za-z0-9_-]+$/;
  if (!validPattern.test(tradeNo)) {
    console.warn("[订单号自动填充] 订单号包含非法字符");
    showModalAlert("订单号只能包含字母、数字、下划线和连字符", "格式错误");
    return;
  }

  // ========== 步骤2：调用后端API查询订单信息 ==========
  try {
    // 构建API请求URL，通过订单号直接查询单个订单，避免查询所有订单后再遍历查找
    const url = `/api/payment/order_by_tradeno?trade_no=${encodeURIComponent(
      tradeNo,
    )}`;

    console.log("[订单号自动填充] 已调用订单查询 API");

    // 发起GET请求
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 使用全局会话UUID进行身份验证
      },
    });

    // ========== 步骤3：处理HTTP响应状态码 ==========

    // 解析JSON响应（无论成功还是失败都需要解析）
    const result = await response.json();

    // 处理不同的HTTP状态码
    if (!response.ok) {
      // HTTP状态码不是2xx，说明请求失败

      if (response.status === 404) {
        // 404：订单不存在
        console.warn("[订单号自动填充] 订单不存在");
        showModalAlert(
          result.message || "未找到该订单号对应的订单记录",
          "订单不存在",
        );

        // 清空退款金额输入框
        const amountInput = document.getElementById(
          "admin-refund-amount_modal",
        );
        if (amountInput) {
          amountInput.value = "";
        }
        return;
      } else if (response.status === 403) {
        // 403：无权限访问该订单（普通用户尝试查询其他用户的订单）
        console.warn("[订单号自动填充] 无权限访问订单");
        showModalAlert(result.message || "无权限访问该订单", "权限不足");
        return;
      } else {
        // 其他错误（400参数错误、500服务器错误等）
        throw new Error(result.message || `HTTP错误: ${response.status}`);
      }
    }

    // 检查API调用是否成功
    if (!result.success) {
      throw new Error(result.message || "获取订单信息失败");
    }

    // ========== 步骤4：获取订单数据 ==========

    // 从返回结果中直接获取订单对象
    // 新API直接返回单个订单，无需在数组中查找
    const matchedOrder = result.order;

    // 双重校验：确保订单对象存在
    if (!matchedOrder) {
      console.error("[订单号自动填充] API返回成功但订单数据为空");
      showModalAlert("订单数据异常，请联系管理员", "数据错误");
      return;
    }

    console.log(
      "[订单号自动填充] 成功获取订单数据:",
      createSafeClientLogValue(matchedOrder),
    );

    // ========== 步骤4.5：检查是否已退款（一个订单只能退款一次） ==========
    
    const refundedAmount = parseFloat(matchedOrder.refundmoney) || 0;
    const refundCount = parseInt(matchedOrder.refund_count || 0, 10) || 0;
    const hasRefundRecords =
      Array.isArray(matchedOrder.refund_records) &&
      matchedOrder.refund_records.length > 0;
    const orderStatus = String(matchedOrder.status || "").toLowerCase();
    if (
      refundedAmount > 0 ||
      refundCount >= 1 ||
      hasRefundRecords ||
      orderStatus === "refunded_full" ||
      orderStatus === "refunded_partial"
    ) {
      console.log("[订单号自动填充] 该订单已退款，不可再次退款");
      const amountInput = document.getElementById("admin-refund-amount_modal");
      if (amountInput) amountInput.value = "";
      Swal.fire({
        icon: "warning",
        title: "无法退款",
        text: "该订单已退款，每个订单只能退款一次。",
      });
      return;
    }

    // ========== 步骤5：获取订单金额并校验 ==========

    // 从订单对象中获取金额字段
    const orderAmount = parseFloat(matchedOrder.amount);

    // 校验金额是否有效（必须是正数）
    if (isNaN(orderAmount) || orderAmount <= 0) {
      console.error("[订单号自动填充] 订单金额无效");
      showModalAlert("该订单的金额数据无效，无法计算退款金额", "数据错误");
      return;
    }

    // ========== 步骤5.5：计算退款金额（80%） ==========

    // 计算退款金额：原金额 × 0.80
    const refundAmount = orderAmount * 0.80;

    // 保留2位小数，符合货币金额的标准格式
    const refundAmountFormatted = refundAmount.toFixed(2);

    console.log("[订单号自动填充] 计算退款金额:", {
      原订单金额: orderAmount,
      退款金额_80Percent: refundAmountFormatted,
    });

    // ========== 步骤6：填充退款金额到输入框 ==========

    // 获取退款金额输入框DOM元素
    const amountInput = document.getElementById("admin-refund-amount_modal");

    if (!amountInput) {
      console.error("[订单号自动填充] 未找到退款金额输入框元素");
      return;
    }

    // 自动填充计算好的退款金额
    amountInput.value = refundAmountFormatted;

    // 触发input事件，以便其他依赖此输入框的逻辑能够响应
    // 例如，可能有实时验证或计算的功能需要知道金额已更新
    amountInput.dispatchEvent(new Event("input", { bubbles: true }));

    // 在控制台输出成功日志
    console.log("[订单号自动填充] 成功填充退款金额:", refundAmountFormatted);

    // 可选：显示成功提示（可根据需要开启）
    // showModalAlert(`已自动填充退款金额：¥${refundAmountFormatted}（原金额的80%）`, '成功');
  } catch (error) {
    // ========== 异常处理 ==========

    // 捕获所有可能的错误（网络错误、解析错误、API错误等）
    console.error("[订单号自动填充] 获取订单信息失败:", error);

    // 显示友好的错误提示
    showModalAlert(`获取订单信息失败: ${error.message}`, "错误");

    // 清空退款金额输入框
    const amountInput = document.getElementById("admin-refund-amount_modal");
    if (amountInput) {
      amountInput.value = "";
    }
  }
}

// 在页面加载完成后初始化订单号自动填充功能
// 使用DOMContentLoaded事件确保DOM元素已经加载
document.addEventListener("DOMContentLoaded", function () {
  // 延迟执行，确保其他初始化代码已经完成
  setTimeout(() => {
    initOrderNumberAutoFill();
  }, 100); // 延迟100毫秒执行
});

// ========================================================
// 账单相关函数
// ========================================================

/**
 * 获取学校账号对应姓名（带本地缓存，适用于管理员和普通用户）。
 * 调用 /api/school_account/name，无需管理员权限。
 * @param {string} school_username
 * @returns {Promise<string>} 姓名，获取失败时返回空字符串
 */
const _schoolNameCache = {};
async function fetchSchoolAccountName(school_username) {
  if (!school_username) return "";
  if (_schoolNameCache[school_username] !== undefined) {
    return _schoolNameCache[school_username];
  }
  try {
    const resp = await fetch(
      `/api/school_account/name?school_username=${encodeURIComponent(school_username)}`,
      { headers: { "X-Session-ID": sessionUUID } },
    );
    const result = await resp.json();
    const name = result.success && result.name ? result.name : "";
    _schoolNameCache[school_username] = name;
    return name;
  } catch (e) {
    console.warn("[fetchSchoolAccountName] 获取姓名失败:", school_username, e);
    _schoolNameCache[school_username] = "";
    return "";
  }
}

function _escapeAttr(v) {
  return String(v == null ? "" : v)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function _fmtBillTime(v) {
  if (!v) return "-";
  const raw = String(v).trim();
  if (!raw) return "-";
  const legacyUtcMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$/);
  if (legacyUtcMatch) {
    const [, y, mo, d, h, mi, s] = legacyUtcMatch;
    const beijingDate = new Date(
      Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s)) +
        8 * 60 * 60 * 1000,
    );
    const pad = (n) => String(n).padStart(2, "0");
    return `${beijingDate.getUTCFullYear()}-${pad(beijingDate.getUTCMonth() + 1)}-${pad(beijingDate.getUTCDate())} ${pad(beijingDate.getUTCHours())}:${pad(beijingDate.getUTCMinutes())}:${pad(beijingDate.getUTCSeconds())}`;
  }
  return raw.replace("T", " ").replace(/(?:Z|\+08:00)$/, "");
}

function _getBillingTime(record, key) {
  if (!record) return "-";
  return record[`${key}_beijing`] || _fmtBillTime(record[key]);
}

function getBillingStatusLabel(status) {
  const normalized = String(status || "").trim().toLowerCase();
  switch (normalized) {
    case "pending":
      return "待支付";
    case "paid":
      return "已支付";
    case "closed":
      return "已关闭";
    case "refunded_partial":
      return "部分退款";
    case "refunded_full":
      return "全额退款";
    case "admin_cleared":
      return "管理员清除";
    default:
      return "未知状态";
  }
}

function isBillingStatusPayable(status) {
  const normalized = String(status || "").trim().toLowerCase();
  return normalized === "pending" || normalized === "closed";
}

function _billStatusBadge(status) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "paid") {
    return '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-green-500 text-[11px]">✓ 已支付</span>';
  }
  if (normalized === "closed") {
    return '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-slate-500 text-[11px]">⛔ 已关闭</span>';
  }
  if (normalized === "refunded_partial") {
    return '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-orange-500 text-[11px]">↩ 部分退款</span>';
  }
  if (normalized === "refunded_full") {
    return '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-rose-500 text-[11px]">↩ 全额退款</span>';
  }
  if (normalized === "admin_cleared") {
    return '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-sky-500 text-[11px]">✓ 管理员清除</span>';
  }
  return '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-amber-500 text-[11px]">⏳ 待支付</span>';
}

function _billStatusText(status) {
  return getBillingStatusLabel(status);
}

function _collectSelectedBillingItems(containerId) {
  const root = document.getElementById(containerId);
  if (!root) return [];
  const items = [];
  root
    .querySelectorAll('input[data-billing-select="1"]:checked')
    .forEach((cb) => {
      const billingId = (cb.getAttribute("data-billing-id") || "").trim();
      const schoolUsername = (
        cb.getAttribute("data-school-username") || ""
      ).trim();
      if (billingId && schoolUsername) {
        items.push({ billing_id: billingId, school_username: schoolUsername });
      }
    });
  return items;
}

function _buildBillingSelectionDetailHtml(containerId, items) {
  const root = document.getElementById(containerId);
  const selectedInputs = root
    ? Array.from(root.querySelectorAll('input[data-billing-select="1"]'))
    : [];
  const rows = (items || []).map((item, idx) => {
    const billingId = String(item?.billing_id || "").trim();
    const schoolUsername = String(item?.school_username || "").trim();
    let schoolName = "-";
    let reason = "-";
    let amount = "-";
    let status = "-";
    let createdAt = "-";
    const el = selectedInputs.find(
      (input) =>
        String(input.getAttribute("data-billing-id") || "").trim() ===
          billingId &&
        String(input.getAttribute("data-school-username") || "").trim() ===
          schoolUsername,
    );
    if (el) {
      schoolName = (el.getAttribute("data-school-name") || "-").trim() || "-";
      reason = (el.getAttribute("data-reason") || "-").trim() || "-";
      amount = (el.getAttribute("data-amount") || "-").trim() || "-";
      status = _billStatusText(
        (el.getAttribute("data-status") || "-").trim() || "-",
      );
      createdAt = (el.getAttribute("data-created-at") || "-").trim() || "-";
    }
    return `<div class="text-left border border-slate-200 rounded-xl p-2.5 bg-slate-50 ${
      idx > 0 ? "mt-1.5" : ""
    }">
      <div class="grid grid-cols-1 gap-1.5">
        <div class="text-xs text-slate-800 break-all"><span class="text-slate-500">学校账号：</span>${_escapeAttr(schoolUsername || "-")}</div>
        <div class="text-xs text-slate-800"><span class="text-slate-500">姓名：</span>${_escapeAttr(schoolName)}</div>
        
        <div class="text-xs text-slate-700"><span class="text-slate-500">账单创建时间：</span>${_escapeAttr(_fmtBillTime(createdAt))}</div>
        <div class="text-xs text-slate-700 break-all"><span class="text-slate-500">账单描述：</span>${_escapeAttr(reason)}</div>
        <div class="text-xs text-slate-700"><span class="text-slate-500">金额：</span>${_escapeAttr(amount)}</div>
        <div class="text-xs text-slate-700"><span class="text-slate-500">状态：</span>${_escapeAttr(status)}</div>
        <div class="text-[11px] text-slate-500 break-all">账单ID：${_escapeAttr(billingId || "-")}</div>
      </div>
    </div>`;
  });
  return rows.join("");
}

function _renderMobileUserBillingCards(records, containerId) {
  let html = `<div class="space-y-3">`;
  records.forEach((r) => {
    const rawBillingId = r.billing_id || "";
    const rawSchool = r.school_username || "-";
    const billingId = _escapeAttr(rawBillingId);
    const school = _escapeAttr(rawSchool);
    const schoolName = _escapeAttr(r.school_name || r.school_username || "-");
    const reason = _escapeAttr(r.reason || "-");
    const amount = r.amount != null ? "¥" + _escapeAttr(r.amount) : "-";
    const canPay = isBillingStatusPayable(r.status);
    html += `
      <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
        <!-- 顶栏：复选框在最左 + 状态徽章在最右 -->
        <div class="flex items-center gap-2 px-3 py-2.5 bg-slate-50 border-b border-slate-200">
          <input
            type="checkbox"
            data-billing-select="1"
            data-billing-id="${billingId}"
            data-school-username="${school}"
            data-school-name="${schoolName}"
            data-reason="${reason}"
            data-amount="${amount}"
            data-status="${_escapeAttr(r.status || "-")}"
            data-created-at="${_escapeAttr(r.created_at || "")}"
            class="w-4 h-4 flex-shrink-0 accent-emerald-500"
            ${canPay ? "" : "disabled"}
          >
          <div class="flex-1 min-w-0">
            <div class="text-[11px] text-slate-500 leading-none mb-0.5">学校账号</div>
            <div class="text-xs font-semibold text-slate-800 truncate">${school}</div>
          </div>
          <div class="flex-shrink-0">${_billStatusBadge(r.status)}</div>
        </div>
        <!-- 内容区 -->
        <div class="px-3 pt-2.5 pb-3">
          <!-- 姓名行 -->
          <div class="flex items-center gap-1.5 mb-2">
            <span class="text-[11px] text-slate-500 flex-shrink-0">姓名</span>
            <span class="text-xs font-medium text-slate-700 truncate">${schoolName}</span>
          </div>
          <!-- 金额 + 创建时间 两列自适应 -->
          <div class="grid grid-cols-2 gap-2 text-[11px] mb-2">
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2">
              <div class="text-slate-500 leading-none mb-0.5">金额</div>
              <div class="text-slate-800 font-semibold">${amount}</div>
            </div>
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2">
              <div class="text-slate-500 leading-none mb-0.5">创建时间</div>
              <div class="text-slate-700 break-all">${_escapeAttr(_fmtBillTime(_getBillingTime(r, "created_at")))}</div>
            </div>
          </div>
          <!-- 原因 -->
          <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2 text-[11px] mb-2">
            <div class="text-slate-500 leading-none mb-0.5">原因</div>
            <div class="text-slate-800 break-all">${reason}</div>
          </div>
          <!-- 时间 + 操作按钮（按账单状态显示不同内容） -->
          <div class="flex items-center justify-between gap-2">
            <div class="text-[11px] text-slate-400 truncate">
              ${
                r.status === "paid"
                  ? `支付时间：${_escapeAttr(_fmtBillTime(_getBillingTime(r, "paid_at")))}`
                  : r.status === "admin_cleared"
                    ? `清除时间：${_escapeAttr(_fmtBillTime(_getBillingTime(r, "admin_cleared_at")))}`
                    : r.status === "closed"
                      ? "订单已关闭，可重新发起支付"
                      : r.status === "refunded_partial" || r.status === "refunded_full"
                        ? "该账单已退款，不能再次支付"
                        : ""
              }
            </div>
            ${
              canPay
                ? `<button class="flex-shrink-0 px-3 py-1 text-[11px] font-medium bg-emerald-100 hover:bg-emerald-200 text-emerald-700 rounded-lg border border-emerald-200 transition-colors" onclick="paySingleBilling(${escapeInlineJsArg(containerId)}, ${escapeInlineJsArg(rawBillingId)}, ${escapeInlineJsArg(rawSchool)})">支付</button>`
                : `<span class="flex-shrink-0 text-[11px] ${r.status === "admin_cleared" ? "text-sky-500" : "text-slate-500"}">${_escapeAttr(getBillingStatusLabel(r.status))}</span>`
            }
          </div>
        </div>
      </div>`;
  });
  html += `</div>`;
  return html;
}

function _renderBillingTableCommon(records, opts = {}) {
  const {
    tableClass = "w-full text-xs border-collapse",
    isMobile = false,
    containerId = "user-billing-list-container",
  } = opts;

  let html = `<div class="rounded-xl border border-slate-200 overflow-hidden"><div class="overflow-x-auto">`;
  html += `<table class="${tableClass}">`;
  html += `<thead><tr class="bg-slate-100">`;
  html += `<th class="p-2 text-center w-10"><input type="checkbox" onclick="toggleBillingSelectAll(${escapeInlineJsArg(containerId)}, this.checked)"></th>`;
  html += `<th class="p-2 text-left">学校账号</th><th class="p-2 text-left">姓名</th><th class="p-2 text-left">原因</th><th class="p-2 text-left">金额</th><th class="p-2 text-left whitespace-nowrap">状态</th><th class="p-2 text-left">创建时间</th><th class="p-2 text-left">支付/清除时间</th><th class="p-2 text-left whitespace-nowrap">操作</th>`;
  html += `</tr></thead><tbody class="divide-y divide-slate-100">`;
  records.forEach((r) => {
    const rawBillingId = r.billing_id || "";
    const rawSchool = r.school_username || "-";
    const billingId = _escapeAttr(rawBillingId);
    const school = _escapeAttr(rawSchool);
    const schoolName = _escapeAttr(r.school_name || "-");
    const reason = _escapeAttr(r.reason || "-");
    const amount = r.amount != null ? "¥" + _escapeAttr(r.amount) : "-";
    const statusBadge = _billStatusBadge(r.status);
    const canPay = isBillingStatusPayable(r.status);
    html += `<tr class="hover:bg-slate-50">`;
    html += `<td class="p-2 text-center"><input type="checkbox" data-billing-select="1" data-billing-id="${billingId}" data-school-username="${school}" data-school-name="${schoolName}" data-reason="${reason}" data-amount="${amount}" data-status="${_escapeAttr(r.status || "-")}" data-created-at="${_escapeAttr(r.created_at || "")}" ${canPay ? "" : "disabled"}></td>`;
    html += `<td class="p-2 text-slate-800">${school}</td>`;
    html += `<td class="p-2 text-slate-600">${schoolName}</td>`;
    html += `<td class="p-2">${reason}</td>`;
    html += `<td class="p-2">${amount}</td>`;
    html += `<td class="p-2 whitespace-nowrap">${statusBadge}</td>`;
    html += `<td class="p-2">${_escapeAttr(_fmtBillTime(_getBillingTime(r, "created_at")))}</td>`;
    html += `<td class="p-2">${r.status === "admin_cleared" ? _escapeAttr(_fmtBillTime(_getBillingTime(r, "admin_cleared_at"))) : _escapeAttr(_fmtBillTime(_getBillingTime(r, "paid_at")))}</td>`;
    html += `<td class="p-2 whitespace-nowrap">`;
    if (canPay) {
      html += `<button class="btn btn-ghost border border-emerald-300 !py-0.5 !px-2 ${isMobile ? "text-[11px]" : "text-xs"} text-emerald-700" onclick="paySingleBilling(${escapeInlineJsArg(containerId)}, ${escapeInlineJsArg(rawBillingId)}, ${escapeInlineJsArg(rawSchool)})">支付</button>`;
    } else {
      html += `<span class="text-slate-400 text-xs">-</span>`;
    }
    html += `</td></tr>`;
  });
  html += `</tbody></table></div></div>`;
  return html;
}

async function loadUserBillingList() {
  const container = document.getElementById("user-billing-list-container");
  const schoolInput = document.getElementById("user-billing-school-filter");
  if (!container) return;
  const schoolUsername = schoolInput ? schoolInput.value.trim() : "";
  container.innerHTML = `
    <div class="flex items-center justify-center py-8 gap-2 text-slate-400 text-xs">
      <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
      </svg>
      <span>加载中...</span>
    </div>`;
  try {
    const url = schoolUsername
      ? "/api/billing/list?school_username=" +
        encodeURIComponent(schoolUsername)
      : "/api/billing/list";
    const resp = await fetch(url, {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    if (!data.success) {
      container.innerHTML =
        '<p class="text-xs text-red-500">加载失败: ' +
        _escapeAttr(data.message || "未知错误") +
        "</p>";
      return;
    }
    const records = data.records || [];
    if (records.length === 0) {
      container.innerHTML = `<div class="flex flex-col items-center justify-center py-10 text-slate-400 gap-1.5"><p class="text-sm">暂无账单记录</p><p class="text-xs">${schoolUsername ? "当前筛选学校账号：" + _escapeAttr(schoolUsername) : "当前范围：有权限学校账号的全部账单"}</p></div>`;
      return;
    }
    const scopeTip = schoolUsername
      ? `当前筛选：学校账号 ${_escapeAttr(schoolUsername)}`
      : "当前范围：有权限学校账号的全部账单";
    let html = `<!-- <div class="mb-2 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">${scopeTip}</div> -->`;
    html += `<div class="mb-2 flex items-center gap-2 justify-end">
      <button class="btn btn-ghost border border-slate-300 !py-1 !px-2 text-xs" onclick="toggleBillingSelectAll('user-billing-list-container', true)">全选待支付</button>
      <button class="btn btn-ghost border border-slate-300 !py-1 !px-2 text-xs" onclick="toggleBillingSelectAll('user-billing-list-container', false)">清空选择</button>
      <button class="btn btn-primary !py-1 !px-3 text-xs" onclick="paySelectedBilling('user-billing-list-container')">批量支付</button>
    </div>`;
    html += _renderBillingTableCommon(records, {
      tableClass: "w-full text-xs border-collapse",
      isMobile: false,
      containerId: "user-billing-list-container",
    });
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML =
      '<p class="text-xs text-red-500">加载异常: ' +
      _escapeAttr(e.message) +
      "</p>";
  }
}

async function loadMobileUserBillingList() {
  const container = document.getElementById(
    "mobile-user-billing-list-container",
  );
  if (!container) return;
  container.innerHTML = `
    <div class="flex items-center justify-center py-8 gap-2 text-slate-400 text-xs">
      <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
      </svg>
      <span>加载中...</span>
    </div>`;
  try {
    const resp = await fetch("/api/billing/list", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    if (!data.success) {
      container.innerHTML = `<p class="text-xs text-red-500">加载失败: ${_escapeAttr(data.message || "未知错误")}</p>`;
      return;
    }
    const records = data.records || [];
    if (records.length === 0) {
      container.innerHTML = `<div class="flex flex-col items-center justify-center py-8 text-slate-400 gap-1"><p class="text-xs">暂无账单记录</p></div>`;
      return;
    }
    let html = `<!-- <div class="mb-2 text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1.5">当前范围：有权限学校账号的全部账单</div> -->`;
    html += `<div class="mb-2 flex items-center gap-1 justify-end">
      <button class="btn btn-ghost border border-slate-300 !py-0.5 !px-1.5 text-[11px]" onclick="toggleBillingSelectAll('mobile-user-billing-list-container', true)">全选</button>
      <button class="btn btn-ghost border border-slate-300 !py-0.5 !px-1.5 text-[11px]" onclick="toggleBillingSelectAll('mobile-user-billing-list-container', false)">清空</button>
      <button class="btn btn-primary !py-0.5 !px-2 text-[11px]" onclick="paySelectedBilling('mobile-user-billing-list-container')">批量支付</button>
    </div>`;
    html += _renderMobileUserBillingCards(
      records,
      "mobile-user-billing-list-container",
    );
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="text-xs text-red-500">加载异常: ${_escapeAttr(e.message)}</p>`;
  }
}

function toggleBillingSelectAll(containerId, checked) {
  const root = document.getElementById(containerId);
  if (!root) return;
  root.querySelectorAll('input[data-billing-select="1"]').forEach((cb) => {
    if (!cb.disabled) cb.checked = !!checked;
  });
}

async function _chooseBillingPayType(options = {}) {
  let enabledMethods = [];
  let methodsConfig = {};
  let paymentMethodsFullConfig = {};
  const normalizeMethodsConfig = (raw) => {
    if (!raw) return {};
    if (Array.isArray(raw)) {
      const obj = {};
      raw.forEach((item) => {
        const code = String(item?.code || "").trim();
        if (code) obj[code] = item;
      });
      return obj;
    }
    if (typeof raw === "object") return raw;
    return {};
  };
  try {
    const methodsResp = await fetch("/api/payment/methods_config", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const methodsData = await methodsResp.json();
    if (methodsData.success) {
      enabledMethods = Array.isArray(methodsData.enabled_methods)
        ? methodsData.enabled_methods
        : [];
      methodsConfig = normalizeMethodsConfig(methodsData.methods);
    }

    const configResp = await fetch("/api/admin/payment/config", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const configData = await configResp.json();
    if (configData.success && configData.payment_methods) {
      paymentMethodsFullConfig = normalizeMethodsConfig(
        configData.payment_methods,
      );
    }
  } catch (e) {
    console.warn("[账单支付] 获取支付方式失败:", e);
  }

  if (!enabledMethods.length) {
    await Swal.fire({
      title: "暂无可用支付方式",
      text: "请联系管理员启用支付方式后再试",
      icon: "warning",
      confirmButtonText: "确定",
    });
    return null;
  }
  const modalTitle = String(options.title || "").trim() || "选择支付方式";
  const totalAmount = options.totalAmount;

  const paymentMethodsHtml = enabledMethods
    .map((method) => {
      const config =
        paymentMethodsFullConfig[method] || methodsConfig[method] || {};
      const name = config.name || method;
      const svg =
        config.svg ||
        '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"></path></svg>';
      const textColor = config.textColor || "text-blue-600";
      const borderColor = config.borderColor || "hover:border-blue-500";
      return `
        <div class="payment-method-option ${borderColor}" 
             data-method="${escapeHtml(method)}"
             onclick="selectBillingPaymentMethod(${escapeInlineJsArg(method)})"
             style="
                 padding: 15px 20px;
                 margin: 10px 0;
                 border: 2px solid #e2e8f0;
                 border-radius: 10px;
                 cursor: pointer;
                 transition: all 0.2s;
                 display: flex;
                 align-items: center;
                 background: white;
             "
             onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';"
             onmouseout="this.style.boxShadow='none';">
            <div class="${textColor}" style="margin-right: 15px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
                ${svg}
            </div>
            <div style="flex: 1;">
                <div style="font-weight: 600; font-size: 16px; color: #1e293b;">
                    ${escapeHtml(name)}
                </div>
            </div>
            <input type="radio" 
                   name="billing-payment-method" 
                   value="${escapeHtml(method)}"
                   style="width: 20px; height: 20px; cursor: pointer;">
        </div>
      `;
    })
    .join("");

  const amountHtml =
    totalAmount != null && totalAmount !== ""
      ? `
      <div style="
          padding: 12px;
          background: #f1f5f9;
          border-radius: 8px;
          margin-bottom: 20px;
          text-align: center;
      ">
          <div style="color: #64748b; font-size: 13px; margin-bottom: 5px;">应付金额</div>
          <div style="color: #dc2626; font-size: 24px; font-weight: bold;">¥${escapeHtml(String(totalAmount))}</div>
      </div>
    `
      : "";

  const chooseResult = await Swal.fire({
    title: modalTitle,
    html: `
      <div style="text-align: left;">
        ${amountHtml}
        <div class="payment-methods-container" style="
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 12px;
          max-height: calc(100vh - 320px);
          overflow-y: auto;
          padding: 4px;
        ">
          ${paymentMethodsHtml}
        </div>
      </div>
    `,
    showCancelButton: true,
    confirmButtonText: "确认支付",
    cancelButtonText: "取消",
    confirmButtonColor: "#3b82f6",
    cancelButtonColor: "#94a3b8",
    width: "auto",
    customClass: {
      popup: "swal2-payment-popup",
      htmlContainer: "swal2-payment-html",
    },
    didOpen: () => {
      // 根据屏幕高度动态调整弹窗样式
      const popup = Swal.getPopup();
      const container = popup.querySelector(".payment-methods-container");
      if (container) {
        const viewportHeight = window.innerHeight;
        const methodsCount = enabledMethods.length;
        // 当屏幕高度足够时，移除滚动限制
        if (viewportHeight > 600 && methodsCount <= 4) {
          container.style.maxHeight = "none";
          container.style.overflowY = "visible";
        }
        // 设置弹窗最大宽度
        popup.style.maxWidth = methodsCount > 2 ? "600px" : "420px";
        popup.style.minWidth = "340px";
      }
      window.selectBillingPaymentMethod = (method) => {
        const radio = document.querySelector(
          `input[name="billing-payment-method"][value="${method}"]`,
        );
        if (radio) {
          radio.checked = true;
          // 添加选中效果
          document.querySelectorAll(".payment-method-option").forEach(el => {
            el.style.borderColor = "#e2e8f0";
            el.style.background = "white";
          });
          const parentDiv = radio.closest(".payment-method-option");
          if (parentDiv) {
            parentDiv.style.borderColor = "#3b82f6";
            parentDiv.style.background = "#f0f9ff";
          }
        }
      };
    },
    preConfirm: () => {
      const selectedMethod = document.querySelector(
        'input[name="billing-payment-method"]:checked',
      );
      if (!selectedMethod) {
        Swal.showValidationMessage("请选择一种支付方式");
        return false;
      }
      return selectedMethod.value;
    },
  });
  if (!chooseResult.isConfirmed) return null;
  return chooseResult.value;
}

async function createBillingPaymentOrderAndOpen(billingItems, selectedPayType) {
  const payType = String(selectedPayType || "").trim();
  if (!payType) {
    throw new Error("请选择支付方式");
  }
  const createOrderResponse = await fetch(
    "/api/payment/create_order_for_billing",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        billing_items: billingItems,
        pay_type: payType,
        device: Get_YiPAi_device(),
        payment_type: "web",
        app_host: window.location.protocol + "//" + window.location.host,
      }),
    },
  );
  const orderResult = await createOrderResponse.json();
  if (!orderResult.success) {
    throw new Error(orderResult.message || "创建订单失败");
  }
  const responsePayType = String(orderResult.pay_type || "").trim().toLowerCase();
  if (orderResult.reused_qr === true) {
    await Swal.fire({
      title: "已复用二维码",
      text: "已复用有效期内二维码",
      icon: "info",
      confirmButtonColor: "#3b82f6",
      confirmButtonText: "知道了",
    });
  }
  const payInfo = orderResult.pay_info || orderResult.pay_url;
  if (!payInfo) {
    throw new Error("支付链接为空");
  }
  console.log("[账单支付] 创建订单成功:", {
    paymentType: responsePayType,
    hasPaymentInfo: Boolean(payInfo),
  });

  if (responsePayType === "qrcode") {
    let qrPollTimer = null;
    let qrPollingStopped = false;
    let qrPaidByPolling = false;
    const scanConfirmResult = await Swal.fire({
      title: "请扫码支付",
      html: `
        <div style="text-align:center;">
          <div style="color:#64748b;font-size:13px;margin-bottom:10px;">请使用支付应用扫码完成支付</div>
          <div style="margin-bottom:14px;padding:12px;background:#fff;border-radius:8px;">
            <canvas id="billing-payment-qrcode-canvas" style="display:block;margin:0 auto;"></canvas>
          </div>
          <div id="billing-qrcode-local-status" style="font-size:12px;color:#0f766e;">正在同步本地订单状态...</div>
        </div>
      `,
      icon: "info",
      confirmButtonText: "我已扫码完成支付",
      showCancelButton: true,
      cancelButtonText: "稍后再查",
      cancelButtonColor: "#94a3b8",
      confirmButtonColor: "#3b82f6",
      didOpen: async () => {
        try {
          await new Promise((resolve) => setTimeout(resolve, 80));
          const canvas = document.getElementById("billing-payment-qrcode-canvas");
          const statusEl = document.getElementById("billing-qrcode-local-status");
          if (canvas && typeof QRCode !== "undefined") {
            await QRCode.toCanvas(canvas, String(payInfo), {
              width: 220,
              height: 220,
              margin: 2,
              color: { dark: "#000000", light: "#ffffff" },
            });
            const pollLocalStatus = async () => {
              if (qrPollingStopped) return;
              try {
                const resp = await fetch("/api/payment/query_billing_local", {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json",
                    "X-Session-ID": sessionUUID,
                  },
                  body: JSON.stringify({ order_id: orderResult.order_id }),
                });
                const result = await resp.json();
                if (qrPollingStopped) return;
                if (!result.success) {
                  if (statusEl) {
                    statusEl.textContent = "本地状态同步失败，正在重试...";
                    statusEl.style.color = "#b45309";
                  }
                  return;
                }
                const status = String(result?.order?.status || result?.status || "pending")
                  .trim()
                  .toLowerCase();
                if (status === "paid") {
                  qrPaidByPolling = true;
                  orderResult.active_query_result = result;
                  if (statusEl) {
                    statusEl.textContent = "已检测到支付成功，正在关闭窗口...";
                    statusEl.style.color = "#15803d";
                  }
                  Swal.close();
                  return;
                }
                if (status === "closed") {
                  if (statusEl) {
                    statusEl.textContent = "订单已关闭，请重新发起支付";
                    statusEl.style.color = "#475569";
                  }
                  return;
                }
                if (status === "refunded_partial" || status === "refunded_full") {
                  if (statusEl) {
                    statusEl.textContent = "订单已退款，不能重复支付";
                    statusEl.style.color = "#b45309";
                  }
                  return;
                }
                if (statusEl) {
                  statusEl.textContent = "本地状态：未支付，继续等待中...";
                  statusEl.style.color = "#0f766e";
                }
              } catch (_) {
                if (statusEl) {
                  statusEl.textContent = "本地状态同步异常，正在重试...";
                  statusEl.style.color = "#b45309";
                }
              }
            };
            pollLocalStatus();
            qrPollTimer = setInterval(pollLocalStatus, 3000);
          } else {
            console.warn("[账单支付] 无法生成二维码：QRCode库未加载或canvas不存在");
          }
        } catch (error) {
          console.error("[账单支付] 生成二维码失败:", error);
        }
      },
      willClose: () => {
        qrPollingStopped = true;
        if (qrPollTimer) {
          clearInterval(qrPollTimer);
          qrPollTimer = null;
        }
      },
    });
    if (qrPaidByPolling) {
      return orderResult;
    }
    if (!scanConfirmResult.isConfirmed) {
      return orderResult;
    }
    if (!orderResult.active_query_token) {
      const action = await _showBillingErrorNeumorphic(
        "支付系统返回异常（缺少主动查询令牌）。",
        {
          title: "系统错误",
          showRefreshButton: true,
        },
      );
      if (action === "refresh") {
        window.location.reload();
        throw new Error("__BILLING_REFRESH_REQUIRED__");
      }
      if (action === "retry") {
        throw new Error("__BILLING_RETRY_REQUIRED__");
      }
      // 允许用户放弃主动查询，继续等待常规轮询/支付回调
      return orderResult;
    }
    const activeQueryResp = await fetch("/api/payment/query_billing_active", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        order_id: orderResult.order_id,
        active_query_token: orderResult.active_query_token,
      }),
    });
    const activeQueryResult = await activeQueryResp.json();
    if (!activeQueryResult.success) {
      throw new Error(activeQueryResult.message || "主动查询订单状态失败");
    }
    orderResult.active_query_result = activeQueryResult;
  } else if (responsePayType === "html") {
    const htmlWindow = window.open("", "_blank", "noopener,noreferrer");
    if (!htmlWindow) {
      throw new Error("无法打开新窗口，请允许浏览器弹窗后重试");
    }
    htmlWindow.document.open();
    htmlWindow.document.write(String(payInfo));
    htmlWindow.document.close();
  } else if (responsePayType === "jump" || responsePayType === "") {
    const payUrl = String(orderResult.pay_url || orderResult.pay_info || "").trim();
    if (!payUrl) {
      throw new Error("支付链接为空");
    }
    const newWindow = window.open(payUrl, "_blank", "noopener,noreferrer");
    if (!newWindow) {
      throw new Error("无法打开新窗口，请允许浏览器弹窗后重试");
    }
  } else {
    await Swal.fire({
      title: "支付返回信息",
      html: `
        <div style="text-align:left;">
          <div style="color:#64748b;font-size:12px;margin-bottom:6px;">支付类型：${escapeHtml(responsePayType || "-")}</div>
          <pre style="margin:0;padding:12px;background:#f8fafc;border-radius:8px;color:#334155;font-size:12px;max-height:260px;overflow:auto;white-space:pre-wrap;word-break:break-all;">${escapeHtml(
            typeof payInfo === "string" ? payInfo : JSON.stringify(payInfo, null, 2),
          )}</pre>
        </div>
      `,
      icon: "info",
      confirmButtonText: "确定",
      confirmButtonColor: "#3b82f6",
      width: 620,
    });
  }
  return orderResult;
}

async function _showBillingErrorNeumorphic(
  message,
  { title = "支付发起失败", showRefreshButton = true } = {},
) {
  const result = await Swal.fire({
    title,
    html: `
      <div style="
        background:#eef2f7;
        border-radius:16px;
        padding:14px 16px;
        text-align:left;
        color:#334155;
        box-shadow:
          8px 8px 18px rgba(148,163,184,0.28),
          -8px -8px 18px rgba(255,255,255,0.9),
          inset 1px 1px 2px rgba(255,255,255,0.9),
          inset -1px -1px 2px rgba(148,163,184,0.15);
      ">
        <div style="font-size:13px;line-height:1.6;word-break:break-all;">
          ${escapeHtml(message || "未知错误")}
        </div>
      </div>
    `,
    icon: "error",
    showCancelButton: true,
    showDenyButton: showRefreshButton,
    confirmButtonText: "重试",
    cancelButtonText: "取消",
    denyButtonText: "刷新网页",
    confirmButtonColor: "#2563eb",
    denyButtonColor: "#dc2626",
    cancelButtonColor: "#94a3b8",
    width: 560,
  });
  if (result.isConfirmed) return "retry";
  if (result.isDenied) return "refresh";
  return "cancel";
}

async function _handleBillingPayErrorAndMaybeRetry(error) {
  const msg = String(error?.message || "未知错误");
  if (msg === "__BILLING_RETRY_REQUIRED__") return "retry";
  if (msg === "__BILLING_REFRESH_REQUIRED__") return "stop";
  if (msg === "__BILLING_ACTION_CANCELED__") return "stop";

  const action = await _showBillingErrorNeumorphic(msg, {
    title: "支付发起失败",
    showRefreshButton: true,
  });
  if (action === "refresh") {
    window.location.reload();
    return "stop";
  }
  if (action === "retry") return "retry";
  return "stop";
}

function _getBillingPayPendingHint(orderResult) {
  const resultPayType = String(orderResult?.pay_type || "")
    .trim()
    .toLowerCase();
  if (resultPayType === "qrcode") {
    const activeStatus = String(orderResult?.active_query_result?.status || "").trim().toLowerCase();
    return activeStatus === "pending"
      ? "已发起主动查询，系统仍将继续自动轮询支付状态"
      : "系统将持续轮询支付状态，请在支付应用内完成支付";
  }
  if (resultPayType === "jump" || resultPayType === "html") {
    return "请在新窗口完成支付，当前页面会自动轮询支付结果";
  }
  return "请按页面提示完成支付，当前页面会自动轮询支付结果";
}

async function _showBillingPaymentPollingModal(orderResult) {
  const orderId = String(orderResult?.order_id || "").trim();
  if (!orderId) {
    return { status: "unknown", paid: false };
  }
  const maxDurationMs = 10 * 60 * 1000;
  const pollIntervalMs = 3000;
  const startedAt = Date.now();
  let pollTimer = null;
  let elapsedTimer = null;
  let finalStatus = "pending";
  let paid = false;
  let isModalClosed = false;

  const modalResult = await Swal.fire({
    title: "正在等待支付结果",
    html: `
      <div style="
        background:#eef2f7;
        border-radius:16px;
        padding:14px 16px;
        text-align:left;
        color:#334155;
        box-shadow:
          8px 8px 18px rgba(148,163,184,0.28),
          -8px -8px 18px rgba(255,255,255,0.9),
          inset 1px 1px 2px rgba(255,255,255,0.9),
          inset -1px -1px 2px rgba(148,163,184,0.15);
      ">
        <div style="font-size:12px;color:#64748b;margin-bottom:8px;">订单号：${escapeHtml(orderId)}</div>
        <div style="font-size:13px;line-height:1.6;margin-bottom:8px;">${escapeHtml(_getBillingPayPendingHint(orderResult))}</div>
        <div id="billing-pay-poll-status" style="font-size:13px;color:#0f766e;font-weight:600;">轮询中：等待支付成功回调...</div>
        <div id="billing-pay-poll-elapsed" style="font-size:12px;color:#64748b;margin-top:6px;">已等待 0 秒（最长 600 秒）</div>
      </div>
    `,
    icon: "info",
    showCancelButton: true,
    cancelButtonText: "稍后查看",
    cancelButtonColor: "#94a3b8",
    showConfirmButton: false,
    allowOutsideClick: false,
    allowEscapeKey: false,
    width: 620,
    didOpen: () => {
      const statusEl = document.getElementById("billing-pay-poll-status");
      const elapsedEl = document.getElementById("billing-pay-poll-elapsed");

      const updateElapsed = () => {
        if (isModalClosed) return;
        const sec = Math.floor((Date.now() - startedAt) / 1000);
        if (elapsedEl) {
          elapsedEl.textContent = `已等待 ${sec} 秒（最长 600 秒）`;
        }
      };

      const pollOnce = async () => {
        if (isModalClosed) return;
        try {
          const resp = await fetch("/api/payment/query_billing_local", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Session-ID": sessionUUID,
            },
            body: JSON.stringify({ order_id: orderId }),
          });
          const result = await resp.json();
          if (isModalClosed) return;
          if (!result.success) {
            if (statusEl) {
              statusEl.textContent = "轮询中：查询失败，正在重试...";
              statusEl.style.color = "#b45309";
            }
            return;
          }
          const status = String(result?.order?.status || result?.status || "pending")
            .trim()
            .toLowerCase();
          finalStatus = status;
          if (status === "paid") {
            paid = true;
            if (statusEl) {
              statusEl.textContent = "已检测到支付成功，正在完成收尾...";
              statusEl.style.color = "#15803d";
            }
            if (!isModalClosed) Swal.close();
            return;
          }
          if (status === "closed") {
            if (statusEl) {
              statusEl.textContent = "订单已关闭，请重新发起支付";
              statusEl.style.color = "#475569";
            }
            if (!isModalClosed) Swal.close();
            return;
          }
          if (status === "refunded_partial" || status === "refunded_full") {
            if (statusEl) {
              statusEl.textContent = "订单已退款，不能重复支付";
              statusEl.style.color = "#b45309";
            }
            if (!isModalClosed) Swal.close();
            return;
          }
          if (statusEl) {
            statusEl.textContent = "轮询中：未收到支付成功回调，继续等待...";
            statusEl.style.color = "#0f766e";
          }
        } catch (_) {
          if (isModalClosed) return;
          if (statusEl) {
            statusEl.textContent = "轮询中：网络波动，正在自动重试...";
            statusEl.style.color = "#b45309";
          }
        }
      };

      updateElapsed();
      elapsedTimer = setInterval(updateElapsed, 1000);
      pollOnce();
      pollTimer = setInterval(() => {
        if (isModalClosed) return;
        if (Date.now() - startedAt >= maxDurationMs) {
          finalStatus = "timeout";
          if (statusEl) {
            statusEl.textContent = "等待超时：10分钟内未检测到支付成功回调";
            statusEl.style.color = "#b45309";
          }
          if (!isModalClosed) Swal.close();
          return;
        }
        pollOnce();
      }, pollIntervalMs);
    },
    willClose: () => {
      isModalClosed = true;
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
      if (elapsedTimer) {
        clearInterval(elapsedTimer);
        elapsedTimer = null;
      }
    },
  });

  if (paid) return { status: "paid", paid: true };
  if (finalStatus === "timeout") return { status: "timeout", paid: false };
  if (modalResult?.dismiss === Swal.DismissReason.cancel) {
    return { status: "canceled", paid: false };
  }
  return { status: finalStatus || "pending", paid: false };
}

async function _showBillingPollingResultSummary(pollingResult) {
  if (pollingResult?.paid) {
    await Swal.fire({
      title: "支付成功",
      text: "系统已收到支付成功通知，账单状态将自动更新。",
      icon: "success",
      confirmButtonText: "确定",
    });
    return;
  }
  if (pollingResult?.status === "timeout") {
    await Swal.fire({
      title: "等待超时",
      text: "10分钟内未收到支付成功通知。订单仍有效，可稍后刷新查看状态。",
      icon: "info",
      confirmButtonText: "确定",
    });
  }
}

async function _runBillingPaymentFlow(billingItems, selectedPayType) {
  while (true) {
    try {
      const orderResult = await createBillingPaymentOrderAndOpen(
        billingItems,
        selectedPayType,
      );
      const pollingResult = await _showBillingPaymentPollingModal(orderResult);
      await _showBillingPollingResultSummary(pollingResult);
      return;
    } catch (e) {
      const action = await _handleBillingPayErrorAndMaybeRetry(e);
      if (action === "retry") continue;
      return;
    }
  }
}

async function paySelectedBilling(containerId) {
  const selected = _collectSelectedBillingItems(containerId);
  if (!selected.length) {
    await Swal.fire({
      title: "提示",
      text: "请先勾选待支付账单",
      icon: "warning",
      confirmButtonText: "确定",
    });
    return;
  }
  const confirmResult = await Swal.fire({
    title: "确认批量支付",
    text: `将发起 ${selected.length} 笔账单的合并支付`,
    icon: "question",
    showCancelButton: true,
    confirmButtonText: "确认支付",
    cancelButtonText: "取消",
    confirmButtonColor: "#16a34a",
    cancelButtonColor: "#64748b",
  });
  if (!confirmResult.isConfirmed) return;
  const selectedPayType = await _chooseBillingPayType();
  if (!selectedPayType) return;
  await _runBillingPaymentFlow(selected, selectedPayType);
}

async function paySingleBilling(containerId, billingId, schoolUsername) {
  if (!billingId || !schoolUsername) {
    const action = await _showBillingErrorNeumorphic("账单信息不完整，请刷新后重试", {
      title: "参数错误",
      showRefreshButton: true,
    });
    if (action === "refresh") {
      window.location.reload();
    }
    return;
  }
  await paySelectedBillingWithPreset(containerId, [
    { billing_id: billingId, school_username: schoolUsername },
  ]);
}

async function paySelectedBillingWithPreset(containerId, items) {
  if (!Array.isArray(items) || !items.length) return;
  const detailHtml = _buildBillingSelectionDetailHtml(containerId, items);
  const confirmResult = await Swal.fire({
    title: items.length > 1 ? "确认批量支付" : "确认支付账单",
    html: `
      <div class="text-sm text-slate-600 mb-2">${items.length > 1 ? `将发起 ${items.length} 笔账单的合并支付` : "将发起该账单支付"}</div>
      <div class="max-h-64 overflow-y-auto">${detailHtml}</div>
    `,
    icon: "question",
    showCancelButton: true,
    confirmButtonText: "确认支付",
    cancelButtonText: "取消",
    confirmButtonColor: "#16a34a",
    cancelButtonColor: "#64748b",
    width: 560,
  });
  if (!confirmResult.isConfirmed) return;
  const selectedPayType = await _chooseBillingPayType({
    title: items.length > 1 ? "选择支付方式" : "选择支付方式",
  });
  if (!selectedPayType) return;
  await _runBillingPaymentFlow(items, selectedPayType);
}

/**
 * 管理员加载账单列表
 */
