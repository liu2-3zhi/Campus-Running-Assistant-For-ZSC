// Legacy admin configuration, SSL, SMS, and CDN UI extracted from main.js.
async function loadSSLInfo() {
  configLoadState.ssl = false;
  try {
    const response = await fetch("/api/admin/ssl/info", {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
    });
    const data = await response.json();
    if (data.success) {
      const sslEnabledToggle = $("ssl-enabled-toggle");
      const httpsOnlyToggle = $("https-only-toggle");
      if (sslEnabledToggle) {
        sslEnabledToggle.checked = data.config.ssl_enabled || false;
      }

      if (httpsOnlyToggle) {
        httpsOnlyToggle.checked = data.config.https_only || false;
      }
      updateSSLStatusBadge(data.config.ssl_enabled);
      const certInfoContent = $("ssl-cert-info-content");

      if (certInfoContent) {
        if (
          data.cert_info &&
          Object.keys(data.cert_info).length > 0 &&
          !data.cert_info.error
        ) {
          let html = '<div class="space-y-2">';
          if (data.cert_info.error) {
            html += `<div class="text-red-600">⚠️ ${data.cert_info.error}</div>`;
            if (data.cert_info.install_hint) {
              html += `<div class="text-sm text-slate-500">${data.cert_info.install_hint}</div>`;
            }
          } else if (!data.cert_info.subject) {
            html +=
              '<p class="text-amber-600 text-center py-4">无法解析证书，请检查路径是否正确。</p>';
          } else {
            if (data.cert_info.subject) {
              html += `<div class="flex justify-between">
              <span class="text-slate-600">主题 (Subject):</span>
              <span class="font-mono text-sm">${escapeHtml(
                data.cert_info.subject,
              )}</span>
            </div>`;
            }

            if (data.cert_info.issuer) {
              html += `<div class="flex justify-between">
              <span class="text-slate-600">颁发者 (Issuer):</span>
              <span class="font-mono text-sm">${escapeHtml(
                data.cert_info.issuer,
              )}</span>
            </div>`;
            }

            if (data.cert_info.not_before) {
              html += `<div class="flex justify-between">
              <span class="text-slate-600">生效日期:</span>
              <span class="text-sm">${formatDate(
                data.cert_info.not_before,
              )}</span>
            </div>`;
            }

            if (data.cert_info.not_after) {
              const isExpired = data.cert_info.is_expired || false;
              const expiryClass = isExpired ? "text-red-600" : "text-green-600";
              html += `<div class="flex justify-between">
              <span class="text-slate-600">过期日期:</span>
              <span class="text-sm ${expiryClass}">${formatDate(
                data.cert_info.not_after,
              )}</span>
            </div>`;

              if (isExpired) {
                html += `<div class="text-red-600 text-sm mt-2">⚠️ 证书已过期</div>`;
              }
            }

            if (data.cert_info.san && data.cert_info.san.length > 0) {
              html += `<div class="mt-2">
              <span class="text-slate-600">域名 (SAN):</span>
              <div class="mt-1 flex flex-wrap gap-1">`;
              data.cert_info.san.forEach((domain) => {
                html += `<span class="px-2 py-1 bg-slate-100 rounded text-xs">${escapeHtml(
                  domain,
                )}</span>`;
              });
              html += `</div></div>`;
            }
          }

          html += "</div>";
          certInfoContent.innerHTML = html;
        } else {
          if (data.config.ssl_enabled) {
            let errorMsg = "SSL已启用，但证书路径为空或证书无效。";
            if (data.cert_info && data.cert_info.error) {
              errorMsg = `SSL已启用，但证书加载失败: ${data.cert_info.error}`;
            }
            certInfoContent.innerHTML = `<p class="text-amber-600 text-center py-4">${escapeHtml(
              errorMsg,
            )}</p>`;
          } else {
            certInfoContent.innerHTML =
              '<p class="text-slate-400 text-center py-4">HTTPS/SSL 证书未上传</p>';
          }
        }
      }
      console.log("[SSL管理] SSL信息加载成功");
      configLoadState.ssl = true;
    } else {
      configLoadState.ssl = false;
      showModalAlert(data.message || "SSL信息加载失败", "错误");
    }
  } catch (error) {
    configLoadState.ssl = false;
    console.error("[SSL管理] 加载SSL信息失败:", error);
    showModalAlert("加载SSL信息失败", "错误");
  }
}
function updateSSLStatusBadge(sslEnabled) {
  const badge = $("ssl-status-badge");
  if (!badge) return;

  if (sslEnabled) {
    badge.className =
      "px-3 py-1 rounded-full text-sm font-semibold bg-green-100 text-green-700";
    badge.textContent = "✓ HTTPS 已启用";
  } else {
    badge.className =
      "px-3 py-1 rounded-full text-sm font-semibold bg-slate-100 text-slate-600";
    badge.textContent = "HTTP 模式";
  }
}
async function uploadSSLCertificate() {
  const certFileInput = $("ssl-cert-file-input");
  const keyFileInput = $("ssl-key-file-input");
  const uploadBtn = $("ssl-upload-btn");
  if (!certFileInput.files || certFileInput.files.length === 0) {
    showModalAlert("请选择证书文件", "错误");
    return;
  }
  if (!keyFileInput.files || keyFileInput.files.length === 0) {
    showModalAlert("请选择密钥文件", "错误");
    return;
  }
  setButtonLoading(uploadBtn, true, "上传中...");
  try {
    const formData = new FormData();
    formData.append("cert_file", certFileInput.files[0]);
    formData.append("key_file", keyFileInput.files[0]);
    const response = await fetch("/api/admin/ssl/upload", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
      },
      body: formData,
    });
    const data = await response.json();
    if (data.success) {
      showModalAlert("证书上传成功", "成功");
      certFileInput.value = "";
      keyFileInput.value = "";
      await loadSSLInfo();
    } else {
      showModalAlert(data.message || "证书上传失败", "错误");
    }
  } catch (error) {
    console.error("[SSL管理] 上传证书失败:", error);
    showModalAlert("上传失败: " + error.message, "错误");
  } finally {
    setButtonLoading(uploadBtn, false, "上传证书");
  }
}
async function saveSSLConfig() {
  if (!ensureConfigLoaded("ssl", "SSL")) {
    return;
  }
  const saveBtn = $("ssl-save-config-btn");
  const sslEnabledToggle = $("ssl-enabled-toggle");
  const httpsOnlyToggle = $("https-only-toggle");
  setButtonLoading(saveBtn, true, "保存中...");
  try {
    const configData = {
      ssl_enabled: sslEnabledToggle.checked,
      https_only: httpsOnlyToggle.checked,
    };
    const response = await fetch("/api/admin/ssl/config", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(configData),
    });
    const data = await response.json();
    if (data.success) {
      showModalAlert("配置已保存，需要重启服务器才能生效", "保存成功");
      updateSSLStatusBadge(configData.ssl_enabled);
    } else {
      showModalAlert(data.message || "保存配置失败", "保存失败");
    }
  } catch (error) {
    console.error("[SSL管理] 保存配置失败:", error);
    showModalAlert("保存失败: " + error.message, "网络错误");
  } finally {
    setButtonLoading(saveBtn, false, "保存配置");
  }
}

// ============================================================================
// CDN缓存配置管理
// 这个部分负责CDN缓存设置的加载和保存
// ============================================================================

/**
 * 加载CDN缓存配置
 * 功能：从服务器获取当前的CDN缓存配置并更新UI
 *
 * 执行流程：
 * 1. 向服务器发送GET请求获取CDN配置
 * 2. 解析返回的JSON数据
 * 3. 更新页面上的开关状态和缓存时间输入框
 * 4. 处理可能出现的错误情况
 */
async function loadCDNConfig() {
  configLoadState.cdn = false;
  try {
    // 向服务器发送GET请求，获取CDN配置信息
    // 使用fetch API进行异步HTTP请求
    const response = await fetch("/api/admin/cdn/config", {
      method: "GET", // HTTP方法：GET表示获取资源
      headers: {
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
        "Content-Type": "application/json", // 指定内容类型为JSON
      },
    });

    // 将响应体解析为JSON对象
    const data = await response.json();

    // 检查服务器返回的success字段，判断请求是否成功
    if (data.success) {
      // 获取CDN启用状态的开关元素（桌面版）
      // $()是自定义的document.getElementById()的简写函数
      const cdnEnabledToggle = $("cdn-enabled-toggle");

      // 获取缓存时间输入框元素（桌面版）
      const cdnCacheTime = $("cdn-cache-time");

      // 获取移动端的CDN开关元素
      const mobileCdnEnabledToggle = $("mobile-cdn-enabled-toggle");

      // 获取移动端的缓存时间输入框
      const mobileCdnCacheTime = $("mobile-cdn-cache-time");

      // 如果桌面版开关元素存在，则更新其选中状态
      // 使用逻辑或运算符(||)提供默认值false，防止undefined错误
      if (cdnEnabledToggle) {
        cdnEnabledToggle.checked = data.config.cdn_enabled || false;
      }

      // 如果桌面版缓存时间输入框存在，则更新其值
      // 默认值为3600秒（1小时）
      if (cdnCacheTime) {
        cdnCacheTime.value = data.config.cache_time || 3600;
      }

      // 同步更新移动端UI元素
      // 如果移动端开关存在，更新其状态
      if (mobileCdnEnabledToggle) {
        mobileCdnEnabledToggle.checked = data.config.cdn_enabled || false;
      }

      // 如果移动端输入框存在，更新其值
      if (mobileCdnCacheTime) {
        mobileCdnCacheTime.value = data.config.cache_time || 3600;
      }
      _syncCDNForceRefreshAvailability(!!(data.config.cdn_enabled || false));

      // 在控制台输出日志，方便调试
      console.log(
        "[CDN配置] 配置加载成功:",
        createSafeClientLogValue(data.config),
      );
      configLoadState.cdn = true;
    } else {
      configLoadState.cdn = false;
      // 如果服务器返回success: false，显示错误消息
      showModalAlert(data.message || "加载CDN配置失败", "加载失败");
    }
  } catch (error) {
    configLoadState.cdn = false;
    // 捕获网络错误或其他异常
    console.error("[CDN配置] 加载配置失败:", error);
    showModalAlert("加载失败: " + error.message, "网络错误");
  }
}

/**
 * 保存CDN缓存配置
 * 功能：将用户在UI上设置的CDN配置保存到服务器
 *
 * 执行流程：
 * 1. 获取UI上的配置值（开关状态和缓存时间）
 * 2. 验证输入值的有效性
 * 3. 向服务器发送POST请求保存配置
 * 4. 根据服务器响应显示成功或失败消息
 * 5. 更新按钮状态（加载中/正常）
 */
async function saveCDNConfig() {
  if (!ensureConfigLoaded("cdn", "CDN")) {
    return;
  }
  // 获取保存按钮元素，用于后续更新其状态
  const saveBtn = $("cdn-save-config-btn");

  // 获取CDN启用开关元素
  const cdnEnabledToggle = $("cdn-enabled-toggle");

  // 获取缓存时间输入框元素
  const cdnCacheTime = $("cdn-cache-time");

  // 设置按钮为加载状态，防止用户重复点击
  // setButtonLoading是一个辅助函数，用于显示按钮加载状态
  setButtonLoading(saveBtn, true, "保存中...");

  try {
    // 从输入框获取缓存时间值，并转换为整数
    const cacheTime = parseInt(cdnCacheTime.value, 10);

    // 验证缓存时间是否为有效数字且大于等于0
    if (isNaN(cacheTime) || cacheTime < 0) {
      // 如果验证失败，显示错误提示并终止保存操作
      showModalAlert("缓存时间必须是大于等于0的整数", "输入错误");
      return; // 提前返回，不继续执行后续代码
    }

    // 构建要发送到服务器的配置数据对象
    const configData = {
      cdn_enabled: cdnEnabledToggle.checked, // CDN是否启用（布尔值）
      cache_time: cacheTime, // 缓存时间（秒）
    };

    // 向服务器发送POST请求，保存CDN配置
    const response = await fetch("/api/admin/cdn/config", {
      method: "POST", // HTTP方法：POST表示提交数据
      headers: {
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
        "Content-Type": "application/json", // 指定发送的内容类型为JSON
      },
      body: JSON.stringify(configData), // 将配置对象转换为JSON字符串
    });

    // 解析服务器返回的JSON响应
    const data = await response.json();

    // 检查服务器是否成功保存配置
    if (data.success) {
      // 显示成功消息，告知用户配置已保存
      showModalAlert("CDN配置已保存，立即生效", "保存成功");
      _syncCDNForceRefreshAvailability(!!cdnEnabledToggle.checked);

      // 在控制台输出成功日志
      console.log("[CDN配置] 配置保存成功");
    } else {
      // 如果保存失败，显示服务器返回的错误消息
      showModalAlert(data.message || "保存配置失败", "保存失败");
    }
  } catch (error) {
    // 捕获并处理任何错误（网络错误、解析错误等）
    console.error("[CDN配置] 保存配置失败:", error);
    showModalAlert("保存失败: " + error.message, "网络错误");
  } finally {
    // finally块确保无论成功或失败，都会执行清理操作
    // 恢复按钮为正常状态，移除加载动画
    setButtonLoading(saveBtn, false, "保存配置");
  }
}

/**
 * 移动端保存CDN缓存配置
 * 功能：从移动端UI获取CDN配置并保存到服务器
 * 这是loadCDNConfig和saveCDNConfig的移动端版本
 *
 * 主要区别：
 * 1. 使用mobile-前缀的元素ID
 * 2. 适配移动端的UI元素和交互
 * 3. 其他逻辑与桌面版相同
 */
async function saveMobileCDNConfig() {
  // 获取移动端保存按钮元素
  const saveBtn = $("mobile-cdn-save-config-btn");

  // 获取移动端CDN启用开关元素
  const cdnEnabledToggle = $("mobile-cdn-enabled-toggle");

  // 获取移动端缓存时间输入框元素
  const cdnCacheTime = $("mobile-cdn-cache-time");

  // 设置按钮为加载状态
  setButtonLoading(saveBtn, true, "保存中...");

  try {
    // 解析并验证缓存时间输入值
    const cacheTime = parseInt(cdnCacheTime.value, 10);

    // 验证输入值的有效性
    if (isNaN(cacheTime) || cacheTime < 0) {
      showModalAlert("缓存时间必须是大于等于0的整数", "输入错误");
      return; // 验证失败，提前返回
    }

    // 构建配置数据对象
    const configData = {
      cdn_enabled: cdnEnabledToggle.checked, // CDN启用状态
      cache_time: cacheTime, // 缓存时间（秒）
    };

    // 发送POST请求保存配置
    const response = await fetch("/api/admin/cdn/config", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(configData),
    });

    // 解析响应
    const data = await response.json();

    // 检查保存是否成功
    if (data.success) {
      showModalAlert("CDN配置已保存，立即生效", "保存成功");
      _syncCDNForceRefreshAvailability(!!cdnEnabledToggle.checked);
      console.log("[移动端CDN配置] 配置保存成功");
    } else {
      showModalAlert(data.message || "保存配置失败", "保存失败");
    }
  } catch (error) {
    // 错误处理
    console.error("[移动端CDN配置] 保存配置失败:", error);
    showModalAlert("保存失败: " + error.message, "网络错误");
  } finally {
    // 恢复按钮状态
    setButtonLoading(saveBtn, false, "保存配置");
  }
}

// CDN 强制刷新（异步后台执行，防重复点击，自动重试）
let cdnForceRefreshInFlight = false;
let cdnForceRefreshRetryTimer = null;

function _setCDNForceRefreshButtonState(disabled, text = "强制刷新服务器缓存") {
  const btnIds = ["cdn-force-refresh-btn", "mobile-cdn-force-refresh-btn"];
  btnIds.forEach((id) => {
    const btn = $(id);
    if (!btn) return;
    btn.disabled = disabled;
    btn.textContent = text;
  });
}

function _syncCDNForceRefreshAvailability(cdnEnabled) {
  const shouldDisable = !cdnEnabled || cdnForceRefreshInFlight;
  _setCDNForceRefreshButtonState(
    shouldDisable,
    cdnForceRefreshInFlight ? "后台刷新中..." : "强制刷新服务器缓存",
  );
}

function triggerCDNForceRefresh() {
  if (cdnForceRefreshInFlight) {
    showModalAlert("CDN缓存正在后台刷新中，请勿重复点击", "提示");
    return;
  }

  cdnForceRefreshInFlight = true;
  if (cdnForceRefreshRetryTimer) {
    clearTimeout(cdnForceRefreshRetryTimer);
    cdnForceRefreshRetryTimer = null;
  }
  _setCDNForceRefreshButtonState(true, "后台刷新中...");
  showModalAlert("已启动后台强制刷新，任务正在执行中", "已提交");

  const maxAttempts = 3;
  let attempt = 0;

  const doRefresh = async () => {
    attempt += 1;
    try {
      const response = await fetch("/api/cdn/refresh", {
        method: "POST",
        headers: {
          "X-Session-ID": sessionUUID,
          "Content-Type": "application/json",
        },
      });
      const result = await response.json().catch(() => ({}));
      if (response.ok && result && result.success) {
        // showTempMessage(
        //   `CDN后台刷新完成（成功 ${result.success_count || 0}，失败 ${result.fail_count || 0}）`,
        //   "success",
        // );
        swal.fire({
          title: "CDN后台刷新完成",
          html: `成功 <strong>${result.success_count || 0}</strong>，失败 <strong>${result.fail_count || 0}</strong>`,
          icon: "success",
          confirmButtonText: "知道了",
        });
        cdnForceRefreshInFlight = false;
        _setCDNForceRefreshButtonState(false);
        return;
      }

      if (attempt < maxAttempts) {
        // showTempMessage(`CDN刷新失败，准备第 ${attempt + 1} 次重试...`, "warning");
        swal.fire({
          title: "CDN刷新失败",
          html: `准备第 <strong>${attempt + 1}</strong> 次重试...`,
          icon: "warning",
          showConfirmButton: false,
          timer: 1200,
        });
        cdnForceRefreshRetryTimer = setTimeout(doRefresh, 1200);
      } else {
        showModalAlert(
          `CDN后台刷新失败：${(result && result.message) || `HTTP ${response.status}`}`,
          "刷新失败",
        );
        cdnForceRefreshInFlight = false;
        _setCDNForceRefreshButtonState(false);
      }
    } catch (e) {
      if (attempt < maxAttempts) {
        // showTempMessage(`CDN刷新网络异常，准备第 ${attempt + 1} 次重试...`, "warning");
        swal.fire({
          title: "CDN刷新网络异常",
          html: `准备第 <strong>${attempt + 1}</strong> 次重试...`,
          icon: "warning",
          showConfirmButton: false,
          timer: 1200,
        });
        cdnForceRefreshRetryTimer = setTimeout(doRefresh, 1200);
      } else {
        showModalAlert(`CDN后台刷新失败：${e.message}`, "刷新失败");
        cdnForceRefreshInFlight = false;
        _setCDNForceRefreshButtonState(false);
      }
    }
  };

  // 立即后台执行，不阻塞当前UI
  setTimeout(doRefresh, 0);
}

// ============================================================================
// 密码恢复（暴力破解）功能
// 警告：此功能仅用于合法的账号密码恢复，需超级管理员权限
// 所有操作都会被详细记录在审计日志中
// ============================================================================

/**
 * 加载密码恢复任务状态
 * 功能：从服务器获取所有密码恢复任务的当前状态并更新UI
 *
 * 执行流程：
 * 1. 向服务器发送GET请求获取任务状态
 * 2. 解析返回的JSON数据
 * 3. 更新桌面版和移动版的任务列表
 * 4. 显示每个任务的状态、进度、已尝试密码数等信息
 */
async function loadBruteforceStatus() {
  try {
    // 向服务器发送GET请求，获取所有密码恢复任务的状态
    const response = await fetch("/api/admin/bruteforce/status", {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID, // 会话ID用于身份验证
        "Content-Type": "application/json",
      },
    });

    // 解析响应体为JSON对象
    const data = await response.json();

    // 检查请求是否成功
    if (data.success) {
      // 获取桌面版任务列表容器
      const taskList = $("bruteforce-task-list");
      // 获取移动版任务列表容器
      const mobileTaskList = $("mobile-bruteforce-task-list");

      // 检查是否有任务数据
      if (data.tasks && data.tasks.length > 0) {
        // 构建任务列表HTML
        let html = "";

        // 遍历每个任务，生成对应的HTML卡片
        data.tasks.forEach((task) => {
          // 根据任务状态设置不同的颜色和图标
          let statusClass = "";
          let statusIcon = "";
          let statusText = "";

          // 判断任务状态并设置对应的样式
          if (task.status === "running") {
            // 运行中：蓝色
            statusClass = "bg-blue-100 border-blue-300 text-blue-800";
            statusIcon = "🔄";
            statusText = "运行中";
          } else if (task.status === "success") {
            // 成功：绿色
            statusClass = "bg-green-100 border-green-300 text-green-800";
            statusIcon = "✅";
            statusText = "已找到密码";
          } else if (task.status === "failed") {
            // 失败：红色
            statusClass = "bg-red-100 border-red-300 text-red-800";
            statusIcon = "❌";
            statusText = "未找到密码";
          } else if (task.status === "stopped") {
            // 已停止：灰色
            statusClass = "bg-gray-100 border-gray-300 text-gray-800";
            statusIcon = "⏹️";
            statusText = "已停止";
          } else {
            // 未知状态：黄色
            statusClass = "bg-yellow-100 border-yellow-300 text-yellow-800";
            statusIcon = "⚠️";
            statusText = task.status || "未知";
          }

          // 构建单个任务卡片的HTML
          html += `
            <div class="p-3 rounded-lg border-2 ${statusClass}">
              <div class="flex justify-between items-start mb-2">
                <div class="flex-1">
                  <div class="font-semibold text-sm">
                    ${statusIcon} 账号：<span class="font-mono">${escapeHtml(
                      task.account,
                    )}</span>
                  </div>
                  <div class="text-xs mt-1">状态：${statusText}</div>
                </div>
                ${
                  task.status === "running"
                    ? `<button class="btn btn-sm btn-secondary !py-1 !px-2 text-xs" onclick="stopBruteforce(${escapeInlineJsArg(
                        task.account,
                      )})">停止</button>`
                    : ""
                }
              </div>
              <div class="text-xs space-y-1">
                <div>已尝试：<span class="font-mono">${
                  task.attempts || 0
                }</span> 个密码</div>
                ${
                  task.status === "success" && task.password
                    ? `<div class="font-semibold text-green-900">密码：<span class="font-mono bg-white px-2 py-1 rounded">${escapeHtml(
                        task.password,
                      )}</span></div>`
                    : ""
                }
                ${
                  task.start_time
                    ? `<div>开始时间：${formatDate(task.start_time)}</div>`
                    : ""
                }
                ${
                  task.end_time
                    ? `<div>结束时间：${formatDate(task.end_time)}</div>`
                    : ""
                }
              </div>
            </div>
          `;
        });

        // 更新桌面版任务列表
        if (taskList) {
          taskList.innerHTML = html;
        }

        // 更新移动版任务列表（使用相同的HTML）
        if (mobileTaskList) {
          mobileTaskList.innerHTML = html;
        }
      } else {
        // 没有任务时显示提示
        const emptyHtml =
          '<div class="text-slate-400 text-center py-8 text-sm">暂无任务</div>';
        if (taskList) taskList.innerHTML = emptyHtml;
        if (mobileTaskList) mobileTaskList.innerHTML = emptyHtml;
      }

      console.log("[密码恢复] 任务状态加载成功");
    } else {
      // 服务器返回失败
      showModalAlert(data.message || "加载任务状态失败", "加载失败");
    }
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("[密码恢复] 加载任务状态失败:", error);
    showModalAlert("加载失败: " + error.message, "网络错误");
  }
}

/**
 * 开始密码恢复任务
 * 功能：解析用户输入的账号，向服务器提交密码恢复请求
 *
 * 执行流程：
 * 1. 获取用户输入的账号列表（支持换行或逗号分隔）
 * 2. 解析并清理账号列表
 * 3. 验证输入的有效性
 * 4. 向服务器发送POST请求开始破解
 * 5. 显示操作结果并刷新任务列表
 */
async function startBruteforce() {
  // 获取按钮元素以添加UI反馈
  const startBtn = $("bruteforce-start-btn");
  let originalBtnText = "";

  // 获取桌面版的账号输入框
  const accountsInput = $("bruteforce-accounts");
  // 获取移动版的账号输入框
  const mobileAccountsInput = $("mobile-bruteforce-accounts");

  // 优先使用桌面版输入，如果为空则使用移动版输入
  let accountsText = "";
  if (accountsInput && accountsInput.value.trim()) {
    accountsText = accountsInput.value.trim();
  } else if (mobileAccountsInput && mobileAccountsInput.value.trim()) {
    accountsText = mobileAccountsInput.value.trim();
  }

  // 验证输入是否为空
  if (!accountsText) {
    showModalAlert("请输入至少一个账号", "输入错误");
    return; // 输入为空，提前返回
  }

  // 解析账号列表：支持换行符和逗号作为分隔符
  // 1. 先按换行符分割
  // 2. 再按逗号分割
  // 3. 去除每个账号的首尾空格
  // 4. 过滤掉空字符串
  const accounts = accountsText
    .split(/[\n,]/) // 按换行符或逗号分割
    .map((acc) => acc.trim()) // 去除首尾空格
    .filter((acc) => acc.length > 0); // 过滤空字符串

  // 验证是否成功解析出账号
  if (accounts.length === 0) {
    showModalAlert("未能解析出有效的账号", "输入错误");
    return;
  }

  // 设置按钮加载状态
  if (startBtn) {
    originalBtnText = startBtn.innerHTML;
    startBtn.disabled = true;
    startBtn.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span>启动中...`;
  }

  try {
    // 向服务器发送POST请求，开始密码恢复任务
    const response = await fetch("/api/admin/bruteforce/start", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ accounts: accounts }), // 发送账号列表
    });

    // 解析响应
    const data = await response.json();

    // 检查是否成功
    if (data.success) {
      // 显示成功消息
      showModalAlert(
        `已成功启动 ${accounts.length} 个账号的密码恢复任务`,
        "启动成功",
      );

      // 清空输入框
      if (accountsInput) accountsInput.value = "";
      if (mobileAccountsInput) mobileAccountsInput.value = "";

      // 刷新任务列表以显示新任务
      loadBruteforceStatus();

      console.log("[密码恢复] 任务启动成功");
    } else {
      // 显示错误消息
      showModalAlert(data.message || "启动任务失败", "启动失败");
    }
  } catch (error) {
    // 捕获并处理错误
    console.error("[密码恢复] 启动任务失败:", error);
    showModalAlert("启动失败: " + error.message, "网络错误");
  } finally {
    // 恢复按钮状态
    if (startBtn) {
      startBtn.disabled = false;
      startBtn.innerHTML = originalBtnText;
    }
  }
}

/**
 * 停止指定账号的密码恢复任务
 * 功能：向服务器发送请求，停止指定账号的密码恢复任务
 *
 * @param {string} account - 要停止的账号
 */
async function stopBruteforce(account) {
  try {
    // 向服务器发送POST请求，停止指定账号的任务
    const response = await fetch("/api/admin/bruteforce/stop", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ accounts: [account] }), // 发送要停止的账号列表
    });

    // 解析响应
    const data = await response.json();

    // 检查是否成功
    if (data.success) {
      showModalAlert(`账号 ${account} 的任务已停止`, "停止成功");
      // 刷新任务列表以更新状态 (延迟1秒以确保后端线程已处理停止信号)
      setTimeout(() => loadBruteforceStatus(), 1000);
      console.log(`[密码恢复] 账号 ${account} 的任务已停止`);
    } else {
      showModalAlert(data.message || "停止任务失败", "停止失败");
    }
  } catch (error) {
    console.error("[密码恢复] 停止任务失败:", error);
    showModalAlert("停止失败: " + error.message, "网络错误");
  }
}

/**
 * 停止所有密码恢复任务
 * 功能：向服务器发送请求，停止所有正在运行的密码恢复任务
 */
async function stopAllBruteforce() {
  // 获取按钮元素以添加UI反馈
  const stopAllBtn = $("bruteforce-stop-all-btn");
  let originalBtnText = "";

  if (stopAllBtn) {
    originalBtnText = stopAllBtn.innerHTML;
    stopAllBtn.disabled = true;
    stopAllBtn.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span>停止中...`;
  }

  try {
    // 向服务器发送POST请求，停止所有任务
    const response = await fetch("/api/admin/bruteforce/stop", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ all: true }), // 使用all参数表示停止所有任务
    });

    // 解析响应
    const data = await response.json();

    // 检查是否成功
    if (data.success) {
      showModalAlert("所有任务已停止", "停止成功");
      // 刷新任务列表 (延迟1秒以确保后端线程已处理停止信号)
      setTimeout(() => loadBruteforceStatus(), 1000);
      console.log("[密码恢复] 所有任务已停止");
    } else {
      showModalAlert(data.message || "停止任务失败", "停止失败");
    }
  } catch (error) {
    console.error("[密码恢复] 停止所有任务失败:", error);
    showModalAlert("停止失败: " + error.message, "网络错误");
  } finally {
    // 恢复按钮状态
    if (stopAllBtn) {
      stopAllBtn.disabled = false;
      stopAllBtn.innerHTML = originalBtnText;
    }
  }
}

function formatDate(isoString) {
  try {
    const date = new Date(isoString);
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return isoString;
  }
}
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
function normalizeBackendPageOrigin(value) {
  const raw = String(value ?? "");
  if (/[\x00-\x1f\x7f-\x9f\\]/.test(raw)) throw new Error("后端规划页面来源不能包含控制字符或反斜杠");
  const input = raw.trim();
  if (!input) return "";
  try {
    const authority = input.match(/^https?:\/\/([^/?#]+)/i)?.[1];
    const url = new URL(input);
    if (!authority || authority.endsWith(":") || authority.includes("@") || url.username || url.password ||
        !["http:", "https:"].includes(url.protocol) || !url.hostname || url.port === "0") throw new Error();
    return url.origin;
  } catch {
    throw new Error("后端规划页面来源无效，请输入不含账号密码的 HTTP/HTTPS 地址");
  }
}

function useCurrentMapPageOrigin(button) {
  const input = button.parentElement.querySelector("[data-map-origin]");
  if (input) input.value = normalizeBackendPageOrigin(window.location.origin);
}

function toggleMapTileCacheSettings(select) {
  const form = select.closest('[id="admin-config-form"]');
  const settings = form?.querySelector('[data-map-tile-cache-settings]');
  if (settings) settings.hidden = select.value !== "true";
}

function getMapConfigProviderDetails() {
  return {
    amap: { label: "高德地图", key: "js_key", keyLabel: "JS Key" },
    tencent: { label: "腾讯地图", key: "map_key", keyLabel: "Key" },
    tianditu: { label: "天地图", key: "token", keyLabel: "Token" },
    baidu: { label: "百度地图", key: "ak", keyLabel: "AK" },
  };
}

function normalizeLegacyMapConfigSettings(map = {}) {
  const providers = getMapConfigProviderDetails();
  const legacyKeys = { amap: "amap_js_key", tencent: "tencent_map_key", tianditu: "tianditu_token", baidu: "baidu_map_ak" };
  const configs = Array.isArray(map.configs) && map.configs.length
    ? map.configs.map((entry) => ({ ...entry }))
    : Object.entries(providers).map(([provider, details]) => ({
      id: `legacy-${provider}`, name: details.label, provider,
      [details.key]: map.providers?.[provider]?.[details.key] ?? map[legacyKeys[provider]] ?? "",
      ...(provider === "amap" ? { security_js_code: map.providers?.amap?.security_js_code || "" } : {}),
      backend_page_origin: map.providers?.[provider]?.backend_page_origin || "",
    }));
  const fallback = configs.find((entry) => entry.provider === map.provider)?.id || configs[0].id;
  const validId = (id) => configs.some((entry) => entry.id === id) ? id : fallback;
  return { configs, frontend_config_id: validId(map.frontend_config_id), backend_config_id: validId(map.backend_config_id) };
}

function escapeMapConfigAttribute(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMapConfigCard(config) {
  const details = getMapConfigProviderDetails()[config.provider];
  if (!details) return "";
  const escape = escapeMapConfigAttribute;
  const field = (name, label, type = "text") => `<label class="block text-sm text-slate-700"><span class="block mb-1 font-medium">${label}</span><input type="${type}" data-map-config-field="${name}" value="${escape(config[name])}" ${name === "name" ? 'maxlength="100" oninput="syncMapConfigCardOptions(this.closest(\'[data-map-config-editor]\'))"' : 'autocomplete="off"'} class="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white"></label>`;
  return `<article data-map-config-card data-config-id="${escape(config.id)}" data-provider="${escape(config.provider)}" class="p-4 border border-slate-200 rounded-xl bg-gradient-to-br from-white to-slate-50 shadow-sm">
    <div class="flex items-center gap-2 mb-3 flex-wrap">
      <button type="button" data-map-drag-handle class="cursor-grab px-3 py-2 border border-slate-200 rounded-lg text-slate-500" style="touch-action:none" aria-label="拖动配置卡片排序" title="拖动排序">拖动</button>
      <strong class="text-sm text-sky-800 flex-1">${details.label}</strong><span data-map-config-position class="text-xs text-slate-500"></span>
      <button type="button" onclick="moveMapConfigCard(this,-1)" data-map-move-up class="px-2 py-2 border border-slate-200 rounded-lg text-xs disabled:opacity-40" aria-label="上移配置">上移</button>
      <button type="button" onclick="moveMapConfigCard(this,1)" data-map-move-down class="px-2 py-2 border border-slate-200 rounded-lg text-xs disabled:opacity-40" aria-label="下移配置">下移</button>
      <button type="button" onclick="removeMapConfigCard(this)" data-map-remove class="px-2 py-2 border border-red-100 text-red-600 rounded-lg text-xs disabled:opacity-40">删除</button>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">${field("name", "配置名称")}${field(details.key, details.keyLabel, "password")}${config.provider === "amap" ? field("security_js_code", "安全密钥（选填）", "password") : ""}</div>
    <label class="block text-sm text-slate-700 mt-3"><span class="block mb-1 font-medium">地图页面来源（选填）</span><div class="flex flex-col sm:flex-row gap-2"><input type="text" data-map-config-field="backend_page_origin" data-map-origin value="${escape(config.backend_page_origin)}" placeholder="https://example.com" onblur="validateMapConfigOrigin(this)" class="w-full px-3 py-2 border border-slate-200 rounded-lg bg-white"><button type="button" onclick="useCurrentMapPageOrigin(this)" class="px-3 py-2 border border-slate-200 rounded-lg whitespace-nowrap">使用当前页面来源</button></div></label>
    <p class="text-xs text-slate-500 mt-2">留空继承全局来源；前端直连地图时使用当前页面来源。</p>
  </article>`;
}

function renderMapConfigCards(map) {
  const settings = normalizeLegacyMapConfigSettings(map);
  const escape = escapeMapConfigAttribute;
  const options = (selected) => settings.configs.map((entry) => `<option value="${escape(entry.id)}" ${entry.id === selected ? "selected" : ""}>${escape(entry.name)}（${getMapConfigProviderDetails()[entry.provider]?.label || ""}）</option>`).join("");
  return `<div data-map-config-editor class="mb-4">
    <p class="text-sm text-slate-600 mb-3">同一地图供应商可以添加多份配置。前端地图与后端路径规划分别选择；拖动卡片只调整显示顺序。</p>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4"><label class="text-sm font-semibold text-slate-700">前端地图使用配置<select data-map-config-select="frontend" class="w-full mt-1 px-3 py-2.5 border border-slate-200 rounded-lg bg-white">${options(settings.frontend_config_id)}</select></label><label class="text-sm font-semibold text-slate-700">后端路径规划使用配置<select data-map-config-select="backend" class="w-full mt-1 px-3 py-2.5 border border-slate-200 rounded-lg bg-white">${options(settings.backend_config_id)}</select></label></div>
    <div data-map-config-list class="space-y-3">${settings.configs.map(renderMapConfigCard).join("")}</div>
    <div class="flex gap-2 mt-3"><select data-map-add-provider aria-label="添加配置的地图供应商" class="min-w-0 flex-1 px-3 py-2 border border-slate-200 rounded-lg bg-white">${Object.entries(getMapConfigProviderDetails()).map(([provider, details]) => `<option value="${provider}">${details.label}</option>`).join("")}</select><button type="button" onclick="addMapConfigCard(this)" class="px-4 py-2 text-sky-700 bg-sky-50 border border-sky-200 rounded-lg text-sm font-semibold">添加配置</button></div>
  </div>`;
}

function validateMapConfigOrigin(input) {
  try { input.value = normalizeBackendPageOrigin(input.value); input.setCustomValidity(""); }
  catch (error) { input.setCustomValidity(error.message); input.reportValidity(); }
}

function syncMapConfigCardOptions(editor) {
  if (!editor) return;
  const cards = Array.from(editor.querySelectorAll("[data-map-config-card]"));
  editor.querySelectorAll("[data-map-config-select]").forEach((select) => {
    const selected = select.value;
    select.innerHTML = cards.map((card) => `<option value="${escapeMapConfigAttribute(card.dataset.configId)}">${escapeMapConfigAttribute(card.querySelector('[data-map-config-field="name"]').value || "未命名配置")}（${getMapConfigProviderDetails()[card.dataset.provider].label}）</option>`).join("");
    select.value = cards.some((card) => card.dataset.configId === selected) ? selected : cards[0]?.dataset.configId || "";
  });
  cards.forEach((card, index) => {
    card.querySelector("[data-map-config-position]").textContent = `${index + 1} / ${cards.length}`;
    card.querySelector("[data-map-move-up]").disabled = index === 0;
    card.querySelector("[data-map-move-down]").disabled = index === cards.length - 1;
    card.querySelector("[data-map-remove]").disabled = cards.length <= 1;
  });
}

function initMapConfigCardsSort(container) {
  container.querySelectorAll("[data-map-config-editor]").forEach((editor) => {
    const list = editor.querySelector("[data-map-config-list]");
    if (typeof Sortable !== "undefined" && !list._mapConfigSortable) {
      list._mapConfigSortable = new Sortable(list, {
        animation: 150, handle: "[data-map-drag-handle]", draggable: "[data-map-config-card]",
        ghostClass: "opacity-50", delay: 120, delayOnTouchOnly: true,
        onEnd: () => syncMapConfigCardOptions(editor),
      });
    }
    syncMapConfigCardOptions(editor);
  });
}

function addMapConfigCard(button) {
  const editor = button.closest("[data-map-config-editor]");
  const provider = editor.querySelector("[data-map-add-provider]").value;
  const details = getMapConfigProviderDetails()[provider];
  if (!details) return;
  const count = Array.from(editor.querySelectorAll("[data-map-config-card]")).filter((card) => card.dataset.provider === provider).length;
  const id = `map-${typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2)}`;
  const config = { id, provider, name: `${details.label}${count + 1}`, [details.key]: "", security_js_code: "", backend_page_origin: "" };
  editor.querySelector("[data-map-config-list]").insertAdjacentHTML("beforeend", renderMapConfigCard(config));
  syncMapConfigCardOptions(editor);
  editor.querySelector("[data-map-config-list]").lastElementChild.querySelector('[data-map-config-field="name"]').focus();
}

function removeMapConfigCard(button) {
  const editor = button.closest("[data-map-config-editor]");
  if (editor.querySelectorAll("[data-map-config-card]").length <= 1) return;
  button.closest("[data-map-config-card]").remove();
  syncMapConfigCardOptions(editor);
}

function moveMapConfigCard(button, direction) {
  const card = button.closest("[data-map-config-card]");
  const sibling = direction < 0 ? card.previousElementSibling : card.nextElementSibling;
  if (!sibling) return;
  card.parentElement.insertBefore(direction < 0 ? card : sibling, direction < 0 ? sibling : card);
  syncMapConfigCardOptions(card.closest("[data-map-config-editor]"));
}

function readMapConfigCards(container) {
  const editor = container.querySelector("[data-map-config-editor]");
  if (!editor) throw new Error("地图配置尚未加载，请重新加载配置");
  const configs = Array.from(editor.querySelectorAll("[data-map-config-card]")).map((card) => {
    const config = { id: card.dataset.configId, provider: card.dataset.provider };
    card.querySelectorAll("[data-map-config-field]").forEach((input) => {
      config[input.dataset.mapConfigField] = input.value.trim();
    });
    if (!config.name) throw new Error("请填写地图配置名称");
    if (config.name.length > 100) throw new Error("地图配置名称不能超过 100 字符");
    config.backend_page_origin = normalizeBackendPageOrigin(config.backend_page_origin);
    return config;
  });
  return { configs, frontend_config_id: editor.querySelector('[data-map-config-select="frontend"]').value, backend_config_id: editor.querySelector('[data-map-config-select="backend"]').value };
}

function copyMapConfigEditorState(source, target) {
  // innerHTML cloning omits live input values and Sortable instances.
  const sourceInputs = source.querySelectorAll("[data-map-config-editor] input, [data-map-config-editor] select");
  const targetInputs = target.querySelectorAll("[data-map-config-editor] input, [data-map-config-editor] select");
  sourceInputs.forEach((input, index) => { if (targetInputs[index]) targetInputs[index].value = input.value; });
  initMapConfigCardsSort(target);
}

async function saveSystemConfig() {
  const sourceButton = arguments[0] || null;
  const panel = sourceButton?.closest('#admin-config-panel_modal, #mobile-admin-config-content-panel, #mobile-multi-admin-config-content, #mobile-admin-config-panel-panel') || document;
  const $ = (id) => panel.querySelector(`[id="${id}"]`) || document.getElementById(id);
  if (!ensureConfigLoaded("system", "系统")) {
    return;
  }
  const btn = $("admin-save-config_modal");
  setButtonLoading(btn, true, "保存中...");

  try {
    const tileCacheDays = Number($("config-Map-tile_cache_ttl_days")?.value ?? 20);
    const tileCacheSize = Number($("config-Map-tile_cache_max_size_gb")?.value ?? 10);
    if (!Number.isInteger(tileCacheDays) || tileCacheDays <= 0) throw new Error("地图瓦片缓存时间必须是正整数天数");
    if (!Number.isFinite(tileCacheSize) || tileCacheSize <= 0 || Number(tileCacheSize.toFixed(2)) !== tileCacheSize) throw new Error("地图瓦片缓存最大大小必须是最多两位小数的正数 GB");
    const configData = {
      Config: {
        default_ui: $("config-Config-default_ui").value,
      },
      Guest: {
        allow_guest_login: $("config-Guest-allow_guest_login").value === "true",
        max_active_guest_sessions: parseInt(
          $("config-Guest-max_active_guest_sessions").value,
          10,
        ),
        guest_session_inactivity_timeout: parseInt(
          $("config-Guest-guest_session_inactivity_timeout").value,
          10,
        ),
        guest_token_ttl_seconds: parseInt(
          $("config-Guest-guest_token_ttl_seconds").value,
          10,
        ),
        guest_token_grace_seconds: parseInt(
          $("config-Guest-guest_token_grace_seconds").value,
          10,
        ),
      },
      Help: {
        show_newbie_help: $("config-Guest-show_newbie_help").value === "true",
        newbie_help_url: $("config-Guest-newbie_help_url").value || "",
      },
      System: {
        session_expiry_days: parseInt(
          $("config-System-session_expiry_days").value,
          10,
        ),
        school_accounts_dir: $("config-System-school_accounts_dir").value,
        system_accounts_dir: $("config-System-system_accounts_dir").value,
        permissions_file: $("config-System-permissions_file").value,
        session_monitor_check_interval: parseInt(
          $("config-System-session_monitor_check_interval").value,
          10,
        ),
        session_inactivity_timeout: parseInt(
          $("config-System-session_inactivity_timeout").value,
          10,
        ),
      },
      Daily_Restart: {
        enabled: $("config-Daily_Restart-enabled").value === "true",
        time: ($("config-Daily_Restart-time").value || "").trim(),
      },
      Logging: {
        log_rotation_size_mb: parseInt(
          $("config-Logging-log_rotation_size_mb").value,
          10,
        ),
        archive_max_size_mb: parseInt(
          $("config-Logging-archive_max_size_mb").value,
          10,
        ),
        random_background_cache_max_size_mb: parseInt(
          $("config-Logging-random_background_cache_max_size_mb").value,
          10,
        ),
        log_dir: $("config-Logging-log_dir").value,
        archive_dir: $("config-Logging-archive_dir").value,
      },
      Security: {
        password_storage: $("config-Security-password_storage").value,
        brute_force_protection:
          $("config-Security-brute_force_protection").value === "true",
        login_log_retention_days: parseInt(
          $("config-Security-login_log_retention_days").value,
          10,
        ),
      },
      Map: {
        ...readMapConfigCards(panel),
        backend_page_origin: normalizeBackendPageOrigin($("config-Map-backend_page_origin").value),
        frontend_proxy_enabled: $("config-Map-frontend_proxy_enabled").value === "true",
        tile_cache_ttl_days: tileCacheDays,
        tile_cache_max_size_gb: tileCacheSize,
      },
      IP_Location: {
        query_order: ($("config-IP_Location-query_order").value || "").trim(),
        amap_web_api_key: ($("config-IP_Location-amap_web_api_key").value || "").trim(),
        uapipro_api_key: ($("config-IP_Location-uapipro_api_key").value || "").trim(),
      },
      IP_Location: {
        query_order: ($("config-IP_Location-query_order").value || "").trim(),
        amap_web_api_key: ($("config-IP_Location-amap_web_api_key").value || "").trim(),
        uapipro_api_key: ($("config-IP_Location-uapipro_api_key").value || "").trim(),
      },
      // ==================== 网站备案信息配置保存 ====================
      // 读取页面上的 Beian（网站备案）配置项，并保存到配置文件中
      // 这些配置项用于在网站底部显示合规的备案信息
      Beian: {
        // ICP备案号：工信部颁发的网站备案号
        icp_number: $("config-Beian-icp_number").value,
        // 是否显示ICP备案：布尔值，控制是否在页面底部展示ICP备案号
        show_icp: $("config-Beian-show_icp").value === "true",
        // 公安网备案号：公安部网络安全备案号
        police_number: $("config-Beian-police_number").value,
        // 是否显示公安备案：布尔值，控制是否在页面底部展示公安网备案号
        show_police: $("config-Beian-show_police").value === "true",
      },
      // ==================== 百度云文本审核服务配置保存 ====================
      // 读取页面上的 baidu_cloud（百度云审核服务）配置项
      // 这些配置用于调用百度云文本审核API，对用户留言进行内容审核
      baidu_cloud: {
        // API Key：百度智能云控制台获取的应用凭证
        // 用于标识应用身份，调用API时必须提供
        api_key: $("config-baidu_cloud-api_key").value || "",
        // Secret Key：百度智能云控制台获取的应用密钥
        // 与 API Key 配合生成访问令牌（Access Token）
        secret_key: $("config-baidu_cloud-secret_key").value || "",
        // 策略ID：自定义审核策略的ID（可选）
        // 留空则使用百度云默认审核策略
        strategy_id: $("config-baidu_cloud-strategy_id").value || "",
      },
      // ==================== 内容审核功能配置保存 ====================
      // 读取页面上的 Content_Review（内容审核）配置项
      // 控制是否启用留言内容的自动审核功能
      Content_Review: {
        // 是否启用留言审核：布尔值
        // true：启用审核，留言将通过百度云API检测后才能发布
        // false：禁用审核，留言直接发布（不推荐）
        //
        // 实现原理：
        // 1. 从页面的 select 元素读取值（"true" 或 "false" 字符串）
        // 2. 通过 === "true" 比较，转换为 JavaScript 布尔值
        // 3. 发送到后端时，后端会将布尔值转换为字符串保存到 .\configs\config.json
        // 4. 下次加载时，后端通过 config.getboolean() 转换回布尔值
        enable_message_review:
          $("config-Content_Review-enable_message_review").value === "true",
      },
      Features: {
        account_cancellation_wait_hours: parseInt(
          ($("config-Features-account_cancellation_wait_hours") || {}).value ||
            "24",
          10,
        ),
      },
    };
    const response = await fetch("/api/admin/config/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(configData),
    });
    const result = await response.json();
    if (result.success) {
      const previousProvider = getActiveMapProvider();
      const frontendConfig = configData.Map.configs.find((entry) => entry.id === configData.Map.frontend_config_id);
      const newProvider =
        normalizeSupportedMapProvider(frontendConfig?.provider) ||
        previousProvider;
      const providerChanged = previousProvider !== newProvider;
      let queuedMapProviderConfig = false;
      try {
        let freshConfig = await fetch("/api/frontend-config", {
          cache: "no-cache",
          credentials: "include",
          headers: {
            "X-Session-ID": sessionUUID,
          },
        }).then((r) => r.json());
        freshConfig = await hydrateMapProviderSecretsForLegacy(
          freshConfig,
          getAuthenticatedSessionHeaderValue(),
        );
        queuedMapProviderConfig = queuePendingMapProviderConfig(freshConfig);
      } catch (_syncErr) {
        const directUpdate = {
          map_provider: newProvider,
          map_config_id: configData.Map.frontend_config_id,
          frontend_proxy_enabled: configData.Map.frontend_proxy_enabled,
          map_providers: {},
        };
        if (frontendConfig) {
          const { id, name, provider, backend_page_origin, ...frontendKeys } = frontendConfig;
          directUpdate.map_providers[provider] = { ...frontendKeys, frontend_proxy_enabled: configData.Map.frontend_proxy_enabled };
        }
        queuedMapProviderConfig = queuePendingMapProviderConfig(directUpdate);
      }
      showModalAlert(
        providerChanged
          ? `配置已保存，地图提供方将在下次加载地图时切换为${getMapProviderDisplayName(newProvider)}，当前地图和执行中的任务不会被打断。部分配置需要重启程序才能生效。`
          : queuedMapProviderConfig
            ? "配置已保存。地图相关配置将在下次加载地图时生效；部分配置（如路径）需要重启程序才能生效。"
            : "配置已保存。请注意，部分配置（如路径）需要重启程序才能生效。",
        "保存成功",
      );
      showButtonSuccess(btn, "保存成功", 2000);
    } else {
      showModalAlert(`保存失败: ${result.message}`, "保存失败");
      showButtonError(btn, "保存失败", 2000);
    }
  } catch (e) {
    showModalAlert(`保存配置时发生错误: ${e.message}`, "保存失败");
    showButtonError(btn, "保存失败", 2000);
  } finally {
    setButtonLoading(btn, false, "保存配置");
  }
}
function showTempMessage(msg, type = "info") {
  const colors = {
    success: "bg-green-100 text-green-700 border-green-300",
    warning: "bg-amber-100 text-amber-700 border-amber-300",
    error: "bg-red-100 text-red-700 border-red-300",
    info: "bg-blue-100 text-blue-700 border-blue-300",
  };
  const div = document.createElement("div");
  // 修正：将 z-50 提高到 z-[100000]，防止被 z-60 的模态框遮挡
  div.className = `fixed top-4 right-4 px-4 py-2 rounded-lg border-2 ${colors[type]} z-[100000] shadow-lg`;
  div.textContent = msg;
  document.body.appendChild(div);
  setTimeout(() => {
    div.remove();
  }, 3000);
}

// --- Next Script Block ---

document.addEventListener("DOMContentLoaded", function () {
  if (typeof window.APP_CONFIG === "undefined") {
    console.error("APP_CONFIG 未定义, UI动态配置脚本跳过。");
    window.APP_CONFIG = { sms_enabled: false, reg_verify_enabled: false };
  }
  const config = window.APP_CONFIG;
  if (!config.sms_enabled) {
    console.log("短信服务已禁用，正在隐藏相关UI元素...");
    const switchToSmsBtn = document.getElementById("auth-switch-to-sms");
    if (switchToSmsBtn) switchToSmsBtn.style.display = "none";
    const smsSection = document.getElementById("auth-sms-section");
    if (smsSection) smsSection.style.display = "none";
    const adminModifySmsGroup = document.getElementById(
      "admin-modify-phone-sms-group",
    );
    if (adminModifySmsGroup) adminModifySmsGroup.style.display = "none";
    const newUserSmsGroup = document.getElementById("newUserSmsGroup");
    if (newUserSmsGroup) newUserSmsGroup.style.display = "none";
  }
  if (!config.reg_verify_enabled) {
    console.log("手机注册/验证已禁用，正在隐藏相关UI元素...");
    const regPhoneDiv = document.getElementById("auth-reg-phone-wrapper");
    if (regPhoneDiv) regPhoneDiv.style.display = "none";
    const regSmsDiv = document.getElementById("auth-reg-sms-wrapper");
    if (regSmsDiv) regSmsDiv.style.display = "none";
    // 移动端注册表单：隐藏手机号和短信验证码区域
    const mobileRegPhoneDiv = document.getElementById(
      "mobile-reg-phone-wrapper",
    );
    if (mobileRegPhoneDiv) mobileRegPhoneDiv.style.display = "none";
    const mobileRegSmsDiv = document.getElementById("mobile-reg-sms-wrapper");
    if (mobileRegSmsDiv) mobileRegSmsDiv.style.display = "none";
    const profileModifyBtn = document.getElementById(
      "profile-modify-phone-btn",
    );
    if (profileModifyBtn) profileModifyBtn.style.display = "none";
    const profilePhoneHint = document.getElementById("profile-phone-hint");
    if (profilePhoneHint) profilePhoneHint.style.display = "none";
  }
  if (!config.enable_phone_login) {
    console.log(
      "手机号验证码登录已禁用，隐藏登录类型切换按钮并启用手机号自动识别...",
    );
    // 隐藏 PC 端登录类型切换按钮组
    const loginTypeToggle = document.getElementById("auth-login-type-toggle");
    if (loginTypeToggle) loginTypeToggle.style.display = "none";
    // 隐藏移动端登录类型切换按钮组
    const mobileLoginTypeToggle = document.getElementById(
      "mobile-login-type-toggle",
    );
    if (mobileLoginTypeToggle) mobileLoginTypeToggle.style.display = "none";
    // 隐藏"使用验证码登录"入口（PC 和移动端）
    const switchToSmsBtn = document.getElementById("auth-switch-to-sms");
    if (switchToSmsBtn) switchToSmsBtn.style.display = "none";
    const mobileSwitchToSms = document.getElementById("mobile-switch-to-sms");
    if (mobileSwitchToSms) mobileSwitchToSms.style.display = "none";
  }
});
// ==================== 移动端事件绑定 (Phase 4b) ====================
document.addEventListener("DOMContentLoaded", function () {
  console.log("[移动端] 开始绑定Phase 4b功能...");
  const mobileRandomUABtn = document.getElementById("mobile-random-ua-btn");
  if (mobileRandomUABtn) {
    mobileRandomUABtn.addEventListener("click", async () => {
      try {
        const newUA = await callPythonAPI("generate_new_ua");
        const mobileUALabel = document.getElementById("mobile-ua-label");
        if (mobileUALabel) {
          mobileUALabel.textContent = newUA || "(生成失败)";
        }
        const pcUALabel = document.getElementById("ua-label");
        if (pcUALabel) {
          pcUALabel.textContent = newUA || "(生成失败)";
        }
        console.log("[移动端] 已生成新的UA:", newUA);
      } catch (error) {
        console.error("[移动端] 生成UA失败:", error);
        showModalAlert("生成UA失败，请重试");
      }
    });
    console.log("[移动端] 随机UA按钮已绑定");
  }
  const mobileImportBtn = document.getElementById("mobile-import-button");
  if (mobileImportBtn) {
    mobileImportBtn.addEventListener("click", async (e) => {
      if (typeof checkButtonPermission === "function") {
        if (
          !(await checkButtonPermission(
            "mobile-import-button",
            "use_import_button",
          ))
        ) {
          return;
        }
      }
      if (typeof importTask === "function") {
        await importTask();
      } else {
        console.error("[移动端] importTask函数未定义");
        showModalAlert("导入功能暂不可用");
      }
    });
    console.log("[移动端] 导入按钮已绑定");
  }
  // ========================================
  // 【移动端参数设置面板】
  // ========================================
  const mobileParamsContainer = document.getElementById(
    "mobile-params-container",
  );
  if (mobileParamsContainer && typeof createParamInputs === "function") {
    const excludeGroups = ["主题设置", "自动签到"];
    createParamInputs(
      mobileParamsContainer,
      "mobile-param",
      function (e) {
        const input = e.target;
        const key = input.dataset.key;
        let value;
        if (input.type === "checkbox") {
          value = input.checked;
        } else if (input.type === "number") {
          value = parseFloat(input.value) || 0;
        } else {
          value = input.value;
        }
        if (typeof callPythonAPI === "function") {
          callPythonAPI("update_param", key, value);
          console.log("[移动端] 参数已更新");
        }
      },
      excludeGroups,
    );
    console.log("[移动端] 参数设置面板已初始化");
  }
  console.log("[移动端] Phase 4b功能绑定完成");
});
document.addEventListener("DOMContentLoaded", function () {
  console.log("[移动端] 开始初始化Phase 4d全局设置面板...");
  // 获取多账号全局参数容器元素
  const mobileMultiGlobalParamsContainer = document.getElementById(
    "mobile-multi-global-params-container",
  );
  // 检查容器和创建函数是否存在
  if (
    mobileMultiGlobalParamsContainer &&
    typeof createParamInputs === "function"
  ) {
    // 定义要排除的参数组（主题设置由其他组件处理）
    const excludeGroups = ["主题设置"];
    // 创建参数输入元素，并绑定变更回调
    createParamInputs(
      mobileMultiGlobalParamsContainer,
      "mobile-multi-param",
      function (e) {
        // 获取触发事件的输入元素
        const input = e.target;
        // 获取参数键名
        const key = input.dataset.key;
        let value;
        // 根据输入类型获取值
        if (input.type === "checkbox") {
          value = input.checked;
        } else if (input.type === "number") {
          value = parseFloat(input.value) || 0;
        } else {
          value = input.value;
        }
        // 调用 API 保存参数
        if (typeof callPythonAPI === "function") {
          callPythonAPI("update_param", key, value);
          console.log("[移动端多账号] 全局参数已更新");
        }
      },
      excludeGroups,
    );
    // 检查是否可以自动填充配置值
    if (
      typeof pythonParams !== "undefined" &&
      typeof updateParamInputs === "function"
    ) {
      // 使用 updateParamInputs 函数填充全局参数容器
      updateParamInputs(
        mobileMultiGlobalParamsContainer,
        "mobile-multi-param",
        pythonParams,
      );
      console.log("[移动端] 多账号全局参数已自动填充配置数值");
    } else {
      console.warn(
        "[移动端] pythonParams或updateParamInputs未定义，无法自动填充配置",
      );
    }

    console.log("[移动端] 多账号全局参数面板已初始化");
  }

  /**
   * 【自动签到设置区域初始化】
   * 在 DOMContentLoaded 时为自动签到设置元素填充初始值
   * 并绑定 change 事件处理器，实现实时保存
   */
  if (typeof pythonParams !== "undefined") {
    // 初始化自动签到开关的值
    const autoAttendanceEnabled = document.getElementById(
      "mobile-multi-auto_attendance_enabled",
    );
    if (autoAttendanceEnabled) {
      // 设置复选框的选中状态
      autoAttendanceEnabled.checked =
        pythonParams["auto_attendance_enabled"] || false;
      // 绑定 change 事件，实现实时保存和提示
      autoAttendanceEnabled.addEventListener("change", function () {
        if (typeof callPythonAPI === "function") {
          callPythonAPI(
            "update_param",
            "auto_attendance_enabled",
            this.checked,
          );
          console.log(`[移动端多账号] 自动签到开关已更新: ${this.checked}`);
          // 显示多账号模式的自动签到提示
          showMultiAutoAttendanceToggleAlert(this.checked, true); // true = 移动端
        }
      });
    }

    // 初始化刷新间隔输入框的值
    const autoAttendanceRefresh = document.getElementById(
      "mobile-multi-auto_attendance_refresh_s",
    );
    if (autoAttendanceRefresh) {
      // 设置输入框的值
      autoAttendanceRefresh.value =
        pythonParams["auto_attendance_refresh_s"] || "";
      // 绑定 change 事件，实现实时保存
      autoAttendanceRefresh.addEventListener("change", function () {
        if (typeof callPythonAPI === "function") {
          const value = parseFloat(this.value) || 0;
          callPythonAPI("update_param", "auto_attendance_refresh_s", value);
          console.log(`[移动端多账号] 刷新间隔已更新: ${value}`);
        }
      });
    }

    const autoAttendanceStopAfterSuccess = document.getElementById(
      "mobile-multi-auto_attendance_stop_after_success",
    );
    if (autoAttendanceStopAfterSuccess) {
      autoAttendanceStopAfterSuccess.checked =
        pythonParams["auto_attendance_stop_after_success"] !== false;
      autoAttendanceStopAfterSuccess.addEventListener("change", function () {
        if (typeof callPythonAPI === "function") {
          callPythonAPI(
            "update_param",
            "auto_attendance_stop_after_success",
            this.checked,
          );
          console.log(`[移动端多账号] 自动关闭开关已更新: ${this.checked}`);
        }
      });
    }

    const autoAttendanceSuccessLimit = document.getElementById(
      "mobile-multi-auto_attendance_success_limit",
    );
    if (autoAttendanceSuccessLimit) {
      autoAttendanceSuccessLimit.value =
        pythonParams["auto_attendance_success_limit"] || 1;
      autoAttendanceSuccessLimit.addEventListener("change", function () {
        if (typeof callPythonAPI === "function") {
          const value = Math.max(1, parseInt(this.value, 10) || 1);
          this.value = value;
          callPythonAPI("update_param", "auto_attendance_success_limit", value);
          console.log(`[移动端多账号] 自动关闭次数已更新: ${value}`);
        }
      });
    }

    // 初始化随机半径输入框的值
    const attendanceRadius = document.getElementById(
      "mobile-multi-attendance_user_radius_m",
    );
    if (attendanceRadius) {
      // 设置输入框的值
      attendanceRadius.value = pythonParams["attendance_user_radius_m"] || "";
      // 绑定 change 事件，实现实时保存
      attendanceRadius.addEventListener("change", function () {
        if (typeof callPythonAPI === "function") {
          const value = parseFloat(this.value) || 0;
          callPythonAPI("update_param", "attendance_user_radius_m", value);
          console.log(`[移动端多账号] 随机半径已更新: ${value}`);
        }
      });
    }

    console.log("[移动端] 自动签到设置区域已初始化并绑定事件");
  }

  // 获取配置文件选择器元素
  const configSelect = document.getElementById(
    "mobile-multi-config-user-select",
  );
  if (configSelect) {
    if (!configSelect._refreshBound) {
      configSelect.addEventListener("focus", refreshUserList);
      configSelect.addEventListener("click", refreshUserList);
      configSelect._refreshBound = true;
      console.log("[移动端] 配置文件选择器已绑定自动刷新事件");
    }
    if (typeof refreshUserList === "function") {
      refreshUserList();
      console.log("[移动端] 配置文件选择器已执行初始刷新");
    }
  }

  console.log("[移动端] Phase 4d全局设置面板初始化完成");
});

// function toggleMobileMultiAdminPanel(show) {
//   const modal = document.getElementById("mobile-multi-admin-panel-modal");
//   if (modal) {
//     if (show) {
//       modal.classList.remove("hidden");
//       initMobileAdminPanel("mobile-multi-admin");
//     } else {
//       modal.classList.add("hidden");
//     }
//   }
// }
// ========================================
// 【移动端管理面板初始化函数】
// 负责初始化移动端管理面板的标签页导航和内容区域
// 【重要修改】将函数改为异步函数(async)，以便获取require_payment配置
// ========================================
