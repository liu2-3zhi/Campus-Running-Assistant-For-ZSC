// Legacy admin sessions, health monitoring, and profile UI extracted from main.js.
async function loadAdminSessions_inline() {
  const listEl = $("admin-sessions-list-inline");

  if (!listEl) {
    logMessage_Error(
      "loadAdminSessions_inline: 无法找到会话列表容器 'admin-sessions-list-inline'。",
    );
    return;
  }

  listEl.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const godModeCheckbox = $("god-mode-checkbox");
    const isGodMode = godModeCheckbox && godModeCheckbox.checked;

    let response;
    if (isGodMode) {
      const headers = {
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      };
      addAdminViewOriginSessionHeader(headers, headers["X-Session-ID"]);
      response = await fetch("/auth/admin/all_sessions", {
        headers,
      });
    } else {
      response = await fetch("/auth/user/sessions", {
        headers: {
          "X-Session-ID": getAuthenticatedSessionHeaderValue(),
        },
      });
    }

    if (!response.ok) {
      let errorMsg = `HTTP error ${response.status}`;
      try {
        const errorData = await response.json();
        errorMsg = errorData.message || errorMsg;
      } catch (parseError) {}
      throw new Error(errorMsg);
    }

    const result = await response.json();

    if (!result.success) {
      listEl.innerHTML = `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      return;
    }

    const sessions = result.sessions || [];
    const maxSessions =
      result.max_sessions !== undefined && result.max_sessions !== null
        ? result.max_sessions
        : -1;
    const validSessions = sessions.filter(
      (session) =>
        session.session_id &&
        session.session_id !== "null" &&
        session.session_id.trim() !== "",
    );
    if (isGodMode) {
      updateAdminSessionCountDisplayInline(validSessions.length, -1, true);
    } else {
      updateAdminSessionCountDisplayInline(validSessions.length, maxSessions);
    }

    let html = "";
    if (!currentUserIsGuest) {
      html += `
                  <div class="mb-4 p-3 bg-sky-50 border border-sky-200 rounded-lg">
                    <p class="text-sm text-slate-700 mb-2">选择现有会话或创建新会话</p>
                    <button class="btn btn-primary w-full" onclick="createNewSessionFromPicker()">创建新会话</button>
                  </div>
                `;
    } else {
      html += `
                  <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p class="text-sm text-blue-700">游客模式：当前会话如下。如需使用多个会话，请注册账号。</p>
                  </div>
                `;
    }

    if (validSessions.length === 0) {
      html += '<p class="text-slate-400 text-center py-10">暂无会话</p>';
    } else {
      html += validSessions
        .map((session) => {
          const createdDate = session.created_at
            ? new Date(session.created_at * 1000).toLocaleString()
            : "未知";
          const isCurrent =
            session.is_current || session.session_id === sessionUUID;
          const sessionHash =
            session.session_hash || session.session_id.substring(0, 16);
          const ownerUsername = String(
            session.username || (isGodMode ? "" : currentAuthUsername || ""),
          );
          const sessionIdArg = escapeInlineJsArg(session.session_id);
          const ownerUsernameArg = escapeInlineJsArg(ownerUsername);

          let ownerInfo = "";
          if (isGodMode) {
            if (session.username) {
              ownerInfo = `<p class="text-xs text-slate-500">创建者: ${session.username}</p>`;
            } else {
              ownerInfo = `<p class="text-xs text-amber-600">创建者: 游客模式</p>`;
            }
          }

          return `
                      <div class="border ${
                        isCurrent
                          ? "border-sky-500 bg-sky-50"
                          : "border-slate-200"
                      } rounded-lg p-3 mb-2">
                        <div class="flex justify-between items-start">
                          <div class="flex-1">
                            <p class="font-semibold text-slate-800 break-all"> 会话 ${
                              session.session_id
                            } </p>
                             ${
                               isCurrent
                                 ? '<p class="text-right"><span class="text-xs text-sky-600 ml-2">(当前会话)</span></p>'
                                 : ""
                             }
                            <p class="text-xs text-slate-500">创建时间: ${createdDate}</p>
                            <p class="text-xs text-slate-500">状态: ${
                              session.is_multi_account_mode
                                ? session.login_success
                                  ? '<span class="font-semibold text-green-600">已登录</span>'
                                  : '<span class="font-semibold ">未登录</span>'
                                : session.login_success
                                  ? '<span class="font-semibold text-green-600">已登录</span>'
                                  : "未登录"
                            }</p>
                            ${ownerInfo}
                          </div>
                          <div class="flex gap-2">
                            ${
                              !isCurrent
                                ? `
                              <button class="btn btn-ghost !py-1 !px-2 text-xs" onclick='selectSession(${sessionIdArg}, ${ownerUsernameArg})'>选择</button>
                              <button class="btn btn-ghost !py-1 !px-2 !text-red-600 text-xs" onclick="deleteSession(${escapeInlineJsArg(session.session_id)})">删除</button>
                            `
                                : ""
                            }
                            ${
                              isGodMode
                                ? `<button class="btn btn-danger !py-1 !px-2 text-xs" onclick="destroySession(${escapeInlineJsArg(session.session_id)})">销毁</button>`
                                : ""
                            }
                          </div>
                        </div>
                      </div>
                    `;
        })
        .join("");
    }

    listEl.innerHTML = html;
  } catch (e) {
    logMessage_Error("加载会话列表失败:", e);
    listEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

function updateAdminSessionCountDisplayInline(
  currentCount,
  maxSessions,
  isGodMode = false,
) {
  const countEl = $("admin-session-count-display-inline");
  if (!countEl) return;

  if (isGodMode) {
    countEl.innerHTML = `<span class="text-purple-600">系统总会话数: ${currentCount}</span>`;
  } else if (currentUserIsGuest) {
    countEl.innerHTML = `<span class="text-blue-600">会话数: 1 / 游客仅限单会话</span>`;
  } else {
    if (maxSessions === -1) {
      countEl.innerHTML = `<span class="text-green-600">会话数: ${currentCount} / 无限制</span>`;
    } else {
      const isNearLimit = currentCount >= maxSessions * 0.8;
      const isAtLimit = currentCount >= maxSessions;
      const colorClass = isAtLimit
        ? "text-red-600"
        : isNearLimit
          ? "text-amber-600"
          : "text-slate-600";
      countEl.innerHTML = `<span class="${colorClass}">会话数: ${currentCount} / ${maxSessions}</span>`;
    }
  }
}

// ====================
// 日志查看
// ====================
async function loadAdminLogs(newPage = 1) {
  currentLogPage = newPage;

  const contentEl = $("admin-logs-content_modal");
  const limitSelect = $("log-limit-select_modal");
  const filterSelect = $("log-level-filter_modal");
  const keywordInput = $("log-keyword-filter_modal");
  const pageSelect = $("log-page-select");
  const pageTotal = $("log-page-total");
  const prevBtn = $("log-prev-page");
  const nextBtn = $("log-next-page");

  if (
    !contentEl ||
    !limitSelect ||
    !pageSelect ||
    !pageTotal ||
    !prevBtn ||
    !nextBtn
  ) {
    logMessage_Error("loadAdminLogs: 无法找到日志面板的必要DOM元素");
    return;
  }

  contentEl.textContent = "加载中...";
  prevBtn.disabled = true;
  nextBtn.disabled = true;
  pageSelect.disabled = true;

  try {
    const limit = limitSelect ? limitSelect.value : 100;
    const keywordValue = keywordInput ? keywordInput.value.trim() : "";
    const response = await fetch(
      `/logs/view?page=${currentLogPage}&limit=${limit}&keyword=${encodeURIComponent(keywordValue)}`,
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );
    const result = await response.json();

    if (!result.success) {
      contentEl.textContent = `加载失败: ${result.message}`;
      pageSelect.innerHTML = '<option value="1">1</option>';
      pageTotal.textContent = "(加载失败)";
      return;
    }

    const rawLogs = Array.isArray(result.logs) ? result.logs : [];
    const filteredLogs = filterLogsByLevel(
      rawLogs,
      filterSelect ? filterSelect.value : "all",
    );

    if (filteredLogs.length === 0) {
      contentEl.textContent = rawLogs.length === 0 ? "暂无日志" : "当前筛选条件下暂无日志";
      pageSelect.innerHTML = '<option value="1">第 1 / 1 页</option>';
      pageTotal.textContent = rawLogs.length === 0 ? "(共 0 行)" : `(本页筛选后 0 / ${rawLogs.length} 行)`;
      return;
    }

    renderHighlightedLogs(contentEl, filteredLogs, keywordValue);

    const pagination = result.pagination;
    pageTotal.textContent =
      (filterSelect && filterSelect.value !== "all") || keywordValue
        ? `(本页筛选后 ${filteredLogs.length} / ${rawLogs.length} 行，总计 ${pagination.total_lines} 行)`
        : `(共 ${pagination.total_lines} 行)`;

    pageSelect.innerHTML = "";
    for (let i = 1; i <= pagination.total_pages; i++) {
      const option = document.createElement("option");
      option.value = i;
      option.textContent = `第 ${i} / ${pagination.total_pages} 页`;
      if (i === pagination.current_page) {
        option.selected = true;
      }
      pageSelect.appendChild(option);
    }

    prevBtn.disabled = pagination.current_page <= 1;
    nextBtn.disabled = pagination.current_page >= pagination.total_pages;
    pageSelect.disabled = false;
  } catch (e) {
    logMessage_Error("加载日志失败:", e);
    contentEl.textContent = `加载失败: ${e.message}`;
    pageSelect.innerHTML = '<option value="1">1</option>';
    pageTotal.textContent = "(加载失败)";
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function normalizeMarkdownText(value) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (
    typeof value === "number" ||
    typeof value === "boolean" ||
    typeof value === "bigint"
  ) {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch (e) {
    return String(value);
  }
}

function highlightCustomKeyword(text, keyword) {
  if (!keyword) {
    return text;
  }

  const keywordParts = keyword
    .split(/[|&]/)
    .map((part) => part.trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  if (!keywordParts.length) {
    return text;
  }

  const escapedKeyword = keywordParts.map((part) => escapeRegExp(part)).join("|");
  if (!escapedKeyword) {
    return text;
  }

  return text.replace(
    new RegExp(`(${escapedKeyword})`, "gi"),
    '<span class="bg-yellow-300 text-slate-900 font-bold px-0.5 rounded">$1</span>',
  );
}

function getLogLineClass(line) {
  const text = String(line || "");
  let matchedRule = null;
  let matchedIndex = Number.POSITIVE_INFINITY;

  LOG_HIGHLIGHT_RULES.forEach((rule) => {
    rule.pattern.lastIndex = 0;
    const match = rule.pattern.exec(text);
    rule.pattern.lastIndex = 0;
    if (match && match.index < matchedIndex) {
      matchedIndex = match.index;
      matchedRule = rule;
    }
  });

  return matchedRule ? matchedRule.className : "";
}

function highlightLogLine(line, keyword = "") {
  const html = highlightCustomKeyword(escapeHtml(line), keyword);
  const lineClass = getLogLineClass(line);
  return lineClass ? `<span class="${lineClass}">${html}</span>` : html;
}

function renderHighlightedLogs(contentEl, logs, keyword = "") {
  contentEl.innerHTML = logs.map((line) => highlightLogLine(line, keyword)).join("");
}

function filterLogsByLevel(logs, level) {
  if (!Array.isArray(logs) || level === "all") {
    return Array.isArray(logs) ? logs : [];
  }

  const rule = LOG_HIGHLIGHT_RULES.find((item) => item.key === level);
  if (!rule) {
    return logs;
  }

  return logs.filter((line) => {
    rule.pattern.lastIndex = 0;
    return rule.pattern.test(line);
  });
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function getHealthStatusPresentation(status) {
  switch (String(status || "").toLowerCase()) {
    case "ok":
      return { color: "green", text: "运行正常" };
    case "degraded":
      return { color: "yellow", text: "部分异常" };
    case "error":
      return { color: "red", text: "核心异常" };
    default:
      return { color: "red", text: "状态未知" };
  }
}

function getHealthScrollableElements(contentEl) {
  if (!contentEl) {
    return [];
  }

  const elements = [];
  const visited = new Set();
  let current = contentEl;
  while (current && !visited.has(current)) {
    visited.add(current);
    const style =
      typeof window !== "undefined" && typeof window.getComputedStyle === "function"
        ? window.getComputedStyle(current)
        : null;
    const overflowY = style ? style.overflowY : "";
    const canScroll =
      current === contentEl ||
      current.scrollHeight > current.clientHeight ||
      /auto|scroll|overlay/i.test(overflowY);
    if (canScroll) {
      elements.push(current);
    }
    current = current.parentElement;
  }

  const scrollingElement =
    typeof document !== "undefined" ? document.scrollingElement : null;
  if (scrollingElement && !visited.has(scrollingElement)) {
    elements.push(scrollingElement);
  }

  return elements;
}

function captureHealthScrollPositions(contentEl) {
  const elements = getHealthScrollableElements(contentEl);
  return {
    elements: elements.map((element) => ({
      element,
      scrollTop: element.scrollTop,
      scrollLeft: element.scrollLeft,
    })),
    windowX: typeof window !== "undefined" ? window.scrollX || 0 : 0,
    windowY: typeof window !== "undefined" ? window.scrollY || 0 : 0,
  };
}

function restoreHealthScrollPositions(snapshot) {
  if (!snapshot) {
    return;
  }

  const restore = () => {
    snapshot.elements.forEach(({ element, scrollTop, scrollLeft }) => {
      if (!element) {
        return;
      }
      element.scrollTop = scrollTop;
      element.scrollLeft = scrollLeft;
    });

    if (
      typeof window !== "undefined" &&
      typeof window.scrollTo === "function"
    ) {
      try {
        window.scrollTo(snapshot.windowX, snapshot.windowY);
      } catch (error) {
        // Ignore browser-specific scroll restoration failures.
      }
    }
  };

  restore();
  if (
    typeof window !== "undefined" &&
    typeof window.requestAnimationFrame === "function"
  ) {
    window.requestAnimationFrame(restore);
  } else if (typeof setTimeout === "function") {
    setTimeout(restore, 0);
  }
}

function renderHealthMemoryDiagnostics(result, compact = false) {
  const diagnostics =
    result && result.memory_diagnostics
      ? result.memory_diagnostics
      : null;
  if (!diagnostics || typeof diagnostics !== "object") {
    return "";
  }

  const formatValue = (value) => {
    if (value === null || typeof value === "undefined") {
      return "-";
    }
    if (Array.isArray(value)) {
      return escapeHtml(value.join(", "));
    }
    return escapeHtml(String(value));
  };
  const fields = [
    ["进程 PID", diagnostics.process_id],
    ["启动时间", diagnostics.server_start_time_formatted],
    ["当前 RSS", diagnostics.rss_mb === null ? null : `${diagnostics.rss_mb} MB`],
    [
      "峰值 RSS",
      diagnostics.max_rss_mb === null ? null : `${diagnostics.max_rss_mb} MB`,
    ],
    ["活动线程", diagnostics.active_threads],
    ["账号刷新线程", diagnostics.account_refresh_threads],
    ["多账号监控线程", diagnostics.multi_monitor_threads],
    ["Playwright 上下文", diagnostics.playwright_contexts],
    ["网页会话", diagnostics.web_sessions],
    ["IP 缓存", diagnostics.ip_cache],
    ["手机号缓存", diagnostics.phone_cache],
    ["短信验证码", diagnostics.sms_codes],
    ["GC 计数", diagnostics.gc_counts],
  ];
  const wrapperClass = compact
    ? "bg-sky-50 border border-sky-200 rounded-lg p-3 mb-3"
    : "mt-4 bg-sky-50 border border-sky-200 rounded-lg p-4";
  const gridClass = compact
    ? "grid grid-cols-2 gap-2"
    : "grid grid-cols-2 md:grid-cols-3 gap-3";

  return `
    <div class="${wrapperClass}">
      <h5 class="font-semibold text-sky-800 mb-3">运行时内存诊断</h5>
      <div class="${gridClass}">
        ${fields
          .map(
            ([label, value]) => `
              <div class="bg-white/70 rounded p-2">
                <div class="text-xs text-slate-500">${label}</div>
                <div class="text-sm font-semibold text-slate-700 break-words">${formatValue(value)}</div>
              </div>
            `,
          )
          .join("")}
      </div>
      <p class="text-xs text-sky-700 mt-3">连续刷新时重点观察 RSS、峰值 RSS、线程数、浏览器上下文和会话数是否持续增长。</p>
    </div>
  `;
}

function showHealthRefreshFailure(contentEl, error) {
  if (!contentEl) {
    return;
  }

  const errorMessage = escapeHtml(
    error && error.message ? error.message : "未知错误",
  );
  const lastSuccess = contentEl.dataset.healthLastSuccess;
  const lastSuccessText = lastSuccess
    ? `上次成功刷新：${escapeHtml(lastSuccess)}。`
    : "";
  const errorHtml = `
    <div data-health-refresh-error class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      刷新失败，以下健康数据可能已过期。${lastSuccessText} ${errorMessage}
    </div>
  `;
  const existingError = contentEl.querySelector("[data-health-refresh-error]");
  if (existingError) {
    existingError.outerHTML = errorHtml;
  } else {
    contentEl.insertAdjacentHTML("afterbegin", errorHtml);
  }
}

// ====================
// 健康状态检测
// ====================
async function loadHealthStatus() {
  const contentEl = $("admin-health-content_modal");

  if (!contentEl) {
    logMessage_Error("loadHealthStatus: 无法找到健康状态容器");
    return;
  }

  const scrollSnapshot = captureHealthScrollPositions(contentEl);
  const hasRenderedHealth = contentEl.dataset.healthLoaded === "true";
  if (!hasRenderedHealth) {
    contentEl.innerHTML =
      '<p class="text-slate-400 text-center py-10">检测中...</p>';
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
          <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-rose-50 border border-rose-200 rounded-lg p-4">
              <h5 class="font-semibold text-rose-800 mb-2">核心异常数</h5>
              <p class="text-2xl font-bold text-rose-600">${summary.critical_failed_count || 0}</p>
            </div>
            <div class="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <h5 class="font-semibold text-amber-800 mb-2">非核心异常数</h5>
              <p class="text-2xl font-bold text-amber-600">${summary.non_critical_failed_count || 0}</p>
            </div>
          </div>
        `
      : "";

    const componentsHtml = components.length
      ? `
          <div class="mt-4 bg-white border border-slate-200 rounded-lg p-4">
            <h5 class="font-semibold text-slate-800 mb-3">组件详情</h5>
            <div class="space-y-3">
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
                  const checksCount =
                    component.checks && typeof component.checks === "object"
                      ? Object.keys(component.checks).length
                      : 0;
                  const criticalText = component.critical ? "核心组件" : "非核心组件";
                  return `
                    <div class="border border-slate-200 rounded-lg p-3 bg-slate-50">
                      <div class="flex items-center justify-between gap-3 mb-2">
                        <div class="font-semibold text-slate-800">${componentName}</div>
                        <span class="px-2 py-1 rounded text-xs bg-${componentColor}-100 text-${componentColor}-700">${componentText}</span>
                      </div>
                      <div class="text-sm text-slate-600 mb-2">${componentMessage}</div>
                      <div class="text-xs text-slate-500">${criticalText} · 检查项 ${checksCount} 个</div>
                    </div>
                  `;
                })
                .join("")}
            </div>
          </div>
        `
      : "";
    const memoryDiagnosticsHtml = renderHealthMemoryDiagnostics(result, false);

    contentEl.innerHTML = `
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-${statusColor}-50 border border-${statusColor}-200 rounded-lg p-4">
              <h5 class="font-semibold text-${statusColor}-800 mb-2">服务器状态</h5>
              <p class="text-2xl font-bold text-${statusColor}-600">${statusText}</p>
            </div>
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h5 class="font-semibold text-blue-800 mb-2">响应时间</h5>
              <p class="text-2xl font-bold text-blue-600">${responseTime}ms</p>
            </div>
            <div class="bg-slate-50 border border-slate-200 rounded-lg p-4">
              <h5 class="font-semibold text-slate-800 mb-2">运行时长</h5>
              <p class="text-2xl font-bold text-slate-700">${uptimeText}</p>
            </div>
          </div>
          ${summaryHtml}
          ${componentsHtml}
          ${memoryDiagnosticsHtml}
          <div class="mt-4 bg-slate-50 border border-slate-200 rounded-lg p-4">
            <h5 class="font-semibold text-slate-800 mb-2">JSON 原文</h5>
            <pre class="text-xs text-slate-600 whitespace-pre-wrap"></pre>
          </div>
        `;
    const detailPre = contentEl.querySelector("pre");
    if (detailPre) {
      detailPre.textContent = JSON.stringify(result, null, 2);
    }
    contentEl.dataset.healthLoaded = "true";
    contentEl.dataset.healthLastSuccess = new Date().toLocaleString();
  } catch (e) {
    logMessage_Error("加载健康状态失败:", e);
    if (!hasRenderedHealth) {
      contentEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${escapeHtml(e.message || "未知错误")}</p>`;
    } else {
      showHealthRefreshFailure(contentEl, e);
    }
  } finally {
    restoreHealthScrollPositions(scrollSnapshot);
  }
}

// ============================================================
// 健康面板倒计时功能
// ============================================================

let healthCountdownInterval = null;
let healthCountdownSeconds = 5;

function startHealthAutoRefresh() {
  stopHealthAutoRefresh();

  const autoRefreshToggle = $("health-auto-refresh-toggle");
  if (!autoRefreshToggle || !autoRefreshToggle.checked) {
    return;
  }

  healthCountdownSeconds = 5;
  updateHealthCountdown();

  healthCountdownInterval = setInterval(() => {
    healthCountdownSeconds--;
    updateHealthCountdown();

    if (healthCountdownSeconds <= 0) {
      healthCountdownSeconds = 5;
    }
  }, 1000);

  healthAutoRefreshInterval = setInterval(() => {
    const toggle = $("health-auto-refresh-toggle");
    if (toggle && toggle.checked) {
      loadHealthStatus();
      healthCountdownSeconds = 5;
    } else {
      stopHealthAutoRefresh();
    }
  }, 5000);
}

function updateHealthCountdown() {
  const countdownDisplay = $("health-countdown-display");
  if (countdownDisplay) {
    if (healthCountdownSeconds > 0) {
      countdownDisplay.textContent = ` - ${healthCountdownSeconds}秒后刷新`;
    } else {
      countdownDisplay.textContent = " - 刷新中...";
    }
  }
}

function stopHealthAutoRefresh() {
  if (healthAutoRefreshInterval) {
    clearInterval(healthAutoRefreshInterval);
    healthAutoRefreshInterval = null;
  }
  if (healthCountdownInterval) {
    clearInterval(healthCountdownInterval);
    healthCountdownInterval = null;
  }
  const countdownDisplay = $("health-countdown-display");
  if (countdownDisplay) {
    countdownDisplay.textContent = "";
  }
}

// ====================
// 个人信息管理
// ====================
async function loadPersonalInfo() {
  try {
    const response = await fetch("/auth/user/details", {
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();
    if (!result.success) {
      // showModalAlert(`加载个人信息失败: ${result.message}`, "错误");
      Swal.fire({
        title: "错误",
        text: "加载个人信息失败: " + result.message,
        icon: "error",
        confirmButtonText: "确定",
      });
      return;
    }
    const user = result.user;
    updateAccountCancellationStatusDisplay(user.account_cancellation);
    if (user.auth_username) {
      currentAuthUsername = user.auth_username;
    }
    const nicknameInput = $("profile-nickname");
    const authUsernameInput = $("profile-auth-username");
    const phoneInput = $("profile-phone");
    if (authUsernameInput) authUsernameInput.value = user.auth_username || currentAuthUsername || "";
    if (nicknameInput) nicknameInput.value = user.nickname || "";
    if (phoneInput) phoneInput.value = user.phone || "未绑定";
    _showPhoneLocationNearInput(phoneInput, user.phone);

    const phoneWrapper = phoneInput
      ? phoneInput.closest(".phone-input-wrapper")
      : null;
    if (phoneWrapper) {
      const prefix = phoneWrapper.querySelector(".phone-prefix");
      const isUnbound = !phoneInput.value || phoneInput.value === "未绑定";

      if (prefix) {
        prefix.style.display = isUnbound ? "none" : "inline";
      }
      phoneWrapper.classList.toggle("prefix-hidden", isUnbound);
    }

    const modifyPhoneBtn = $("profile-modify-phone-btn");
    const phoneHint = $("profile-phone-hint");

    const config = window.APP_CONFIG || {
      enable_phone_modification: false,
    };

    if (config.enable_phone_modification) {
      if (modifyPhoneBtn) modifyPhoneBtn.style.display = "block";
      if (phoneHint) phoneHint.style.display = "block";
    } else {
      if (modifyPhoneBtn) modifyPhoneBtn.style.display = "none";
      if (phoneHint) phoneHint.style.display = "none";
      if (phoneInput) phoneInput.readOnly = true;
    }
    const pcForgotPasswordHint = $("pc-forgot-password-hint");
    if (pcForgotPasswordHint) {
      pcForgotPasswordHint.style.display = config.enable_phone_modification
        ? ""
        : "none";
    }
    const avatarDisplay = $("profile-avatar-display");
    const avatarInput = $("profile-avatar-input");
    if (avatarDisplay) {
      const avatarUrl = user.avatar_url || user.avatar || "";
      logMessage_Info("[loadPersonalInfo] Processing avatar URL:", avatarUrl);
      if (avatarUrl) {
        // [修正] 改为直接拼接 session_id，不再使用 loadAvatarWithAuth (Blob方式)
        // 这种方式更稳定，避免了 Fetch Blob 过程中的潜在错误
        let finalUrl = avatarUrl;
        if (
          finalUrl.startsWith("/api/avatar/") &&
          typeof sessionUUID !== "undefined" &&
          sessionUUID
        ) {
          // 只有当是本地API且未包含session_id时才添加
          if (!finalUrl.includes("session_id=")) {
            finalUrl = finalUrl.includes("?")
              ? `${finalUrl}&session_id=${sessionUUID}`
              : `${finalUrl}?session_id=${sessionUUID}`;
          }
        }

        const timestamp = new Date().getTime();
        const urlWithTimestamp = finalUrl.includes("?")
          ? `${finalUrl}&t=${timestamp}`
          : `${finalUrl}?t=${timestamp}`;

        logMessage_Info(
          "[loadPersonalInfo] Setting avatar display src to:",
          urlWithTimestamp,
        );
        avatarDisplay.src = urlWithTimestamp;
      } else {
        logMessage_Info("[loadPersonalInfo] No avatar URL, using default icon");
        avatarDisplay.src =
          "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22%3E%3Crect width=%22100%22 height=%22100%22 fill=%22%23ddd%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 font-size=%2240%22 text-anchor=%22middle%22 dy=%22.3em%22%3E👤%3C/text%3E%3C/svg%3E";
      }
    }
    if (avatarInput) {
      avatarInput.value = user.avatar_url || user.avatar || "";
    }

    const tfaStatus = $("profile-2fa-enabled");
    const tfaActions = $("profile-2fa-actions");
    const tfaEnabledActions = $("profile-2fa-enabled-actions");
    const tfaSetup = $("profile-2fa-setup");

    const tfaEnabled = user["2fa_enabled"] || user.tfa_enabled || false;

    if (tfaStatus) {
      tfaStatus.textContent = tfaEnabled ? "已启用" : "未启用";
      tfaStatus.className = tfaEnabled
        ? "text-green-600 font-semibold"
        : "text-slate-600";
    }

    if (tfaEnabled) {
      if (tfaActions) tfaActions.classList.add("hidden");
      if (tfaSetup) tfaSetup.classList.add("hidden");
      if (tfaEnabledActions) tfaEnabledActions.classList.remove("hidden");
    } else {
      if (tfaActions) tfaActions.classList.remove("hidden");
      if (tfaEnabledActions) tfaEnabledActions.classList.add("hidden");
      if (tfaSetup) tfaSetup.classList.add("hidden");
    }

    const themeSelect = $("profile-theme-select");
    if (themeSelect && user.theme) {
      themeSelect.value = user.theme;
    }
    try {
      const paramsResult = await callPythonAPI("get_params");
      if (paramsResult && paramsResult.theme_base_color) {
        const themeColor = paramsResult.theme_base_color;
        const colorPicker = $("profile-theme_base_color-picker");
        const colorInput = $("profile-theme_base_color");
        if (colorPicker) colorPicker.value = themeColor;
        if (colorInput) colorInput.value = themeColor;
        onColorPicked(themeColor);
      }
      if (paramsResult && paramsResult.theme_style) {
        setThemeStyle(paramsResult.theme_style);
      }
      if (user.theme) {
        applyTheme(user.theme);
      }
    } catch (e) {
      logMessage_Warning("[loadPersonalInfo] 加载主题设置失败:", e);
    }

    // === 更新 available_runs 显示 ===
    // 调用 updateProfileAvailableRuns 函数来更新个人资料中的 available_runs 显示
    // 该函数会根据 config[Profile_Display].available_runs_format 的格式来显示可用次数
    // 传入完整的用户数据对象，函数内部会提取 available_runs 字段并格式化显示
    try {
      // 调用更新函数，传入用户数据
      await updateProfileAvailableRuns(user);
      // 记录成功日志
      logMessage_Info("[loadPersonalInfo] ✓ 已更新 available_runs 显示");
    } catch (e) {
      // 如果更新失败，记录警告日志但不影响主流程
      // 这是一个增强功能，即使失败也不应该阻断个人信息的加载
      logMessage_Warning("[loadPersonalInfo] 更新 available_runs 显示失败:", e);
    }
  } catch (e) {
    logMessage_Error("加载个人信息失败:", e);
    // showModalAlert(`加载失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: "加载失败: " + (e.message || "未知错误"),
      icon: "error",
    });
  }
}

async function updateAvatar() {
  const avatarInput = $("profile-avatar-input");
  if (!avatarInput || !avatarInput.value.trim()) {
    // showModalAlert("请输入头像URL", "提示");
    Swal.fire({
      title: "提示",
      text: "请输入头像URL",
      icon: "info",
    });
    return;
  }

  try {
    const response = await fetch("/auth/user/update_avatar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        avatar_url: avatarInput.value.trim(),
      }),
    });
    const result = await response.json();

    if (result.success) {
      // showModalAlert("头像更新成功！", "成功");
      Swal.fire({
        title: "成功",
        text: "头像已成功更新",
        icon: "success",
      });
      loadPersonalInfo();
    } else {
      // showModalAlert(`更新失败: ${result.message}`, "错误");
      Swal.fire({
        title: "错误",
        text: "更新失败: " + (result.message || "未知错误"),
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("更新头像失败:", e);
    // showModalAlert(`更新失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: "更新失败: " + (e.message || "未知错误"),
      icon: "error",
    });
  }
}

async function loadAvatarWithAuth(avatarUrl, imgElement, retryCount = 0) {
  const defaultSvg =
    "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22%3E%3Crect width=%22100%22 height=%22100%22 fill=%22%23ddd%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 font-size=%2240%22 text-anchor=%22middle%22 dy=%22.3em%22%3E👤%3C/text%3E%3C/svg%3E";

  try {
    logMessage_Info(
      `[loadAvatarWithAuth] Fetching avatar (Attempt ${
        retryCount + 1
      }): ${avatarUrl}`,
    );

    // 增加时间戳防止缓存
    const urlWithTs = avatarUrl.includes("?")
      ? `${avatarUrl}&t=${Date.now()}`
      : `${avatarUrl}?t=${Date.now()}`;

    const response = await fetch(urlWithTs, {
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP Status ${response.status}`);
    }

    const blob = await response.blob();
    if (blob.size === 0) throw new Error("Empty blob received");

    const url = URL.createObjectURL(blob);
    imgElement.onload = () => {
      URL.revokeObjectURL(url); // 释放内存
      logMessage_Info("[loadAvatarWithAuth] Avatar loaded successfully");
    };
    imgElement.onerror = () => {
      logMessage_Error("[loadAvatarWithAuth] Blob image failed to render");
      imgElement.src = defaultSvg;
    };
    imgElement.src = url;
  } catch (e) {
    logMessage_Error(`[loadAvatarWithAuth] Error loading avatar: ${e.message}`);

    // 重试机制：最多重试2次
    if (retryCount < 2) {
      setTimeout(
        () => {
          loadAvatarWithAuth(avatarUrl, imgElement, retryCount + 1);
        },
        1000 * (retryCount + 1),
      ); // 延迟 1s, 2s
    } else {
      imgElement.src = defaultSvg;
    }
  }
}

function previewAvatar(event) {
  isRegistrationCrop = false;
  const file = event.target.files[0];
  if (!file) return;

  if (!file.type.startsWith("image/")) {
    // showModalAlert("请选择图片文件", "错误");
    Swal.fire({
      title: "错误",
      text: "请选择图片文件",
      icon: "error",
    });
    event.target.value = "";
    return;
  }

  const reader = new FileReader();
  reader.onload = function (e) {
    const cropImage = $("crop-image");
    if (cropImage) {
      cropImage.src = e.target.result;

      if (avatarCropper) {
        avatarCropper.destroy();
      }

      avatarCropper = new Cropper(cropImage, {
        aspectRatio: 1,
        viewMode: 1,
        minContainerWidth: 300,
        minContainerHeight: 300,
        autoCropArea: 0.8,
        responsive: true,
        guides: true,
        center: true,
        highlight: true,
        cropBoxResizable: true,
        cropBoxMovable: true,
        toggleDragModeOnDblclick: false,
      });
      showModal("avatar-crop-modal");
    }
  };
  reader.readAsDataURL(file);
}
function previewAvatarForRegistration(event) {
  isRegistrationCrop = true;
  const file = event.target.files[0];
  if (!file) return;

  if (!file.type.startsWith("image/")) {
    // showModalAlert("请选择图片文件", "错误");
    Swal.fire({
      title: "错误",
      text: "请选择图片文件",
      icon: "error",
    });
    event.target.value = "";
    return;
  }

  const reader = new FileReader();
  reader.onload = function (e) {
    const cropImage = $("crop-image");
    if (cropImage) {
      cropImage.src = e.target.result;
      if (avatarCropper) avatarCropper.destroy();
      avatarCropper = new Cropper(cropImage, {
        aspectRatio: 1,
        viewMode: 1,
        minContainerWidth: 300,
        minContainerHeight: 300,
        autoCropArea: 0.8,
        responsive: true,
        guides: true,
        center: true,
        highlight: true,
        cropBoxResizable: true,
        cropBoxMovable: true,
        toggleDragModeOnDblclick: false,
      });
      showModal("avatar-crop-modal");
    }
  };
  reader.readAsDataURL(file);
}
function closeCropModal() {
  if (avatarCropper) {
    avatarCropper.destroy();
    avatarCropper = null;
  }
  const fileInput = $("profile-avatar-file");
  if (fileInput) fileInput.value = "";
  const regFileInput = $("auth-reg-avatar");
  if (regFileInput) regFileInput.value = "";
  const mobileRegFileInput = $("mobile-reg-avatar");
  if (mobileRegFileInput) mobileRegFileInput.value = "";
  isRegistrationCrop = false;
  hideModal("avatar-crop-modal");
}
function revokeRegistrationAvatarPreview(previewImg) {
  if (!previewImg) return;
  if (!previewImg.dataset) previewImg.dataset = {};
  const currentObjectUrl = previewImg.dataset.objectUrl;
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    delete previewImg.dataset.objectUrl;
  }
  previewImg.onload = null;
  previewImg.onerror = null;
}
function setRegistrationAvatarPreview(previewId, file) {
  const previewImg = $(previewId);
  if (!previewImg) return;
  if (!previewImg.dataset) previewImg.dataset = {};
  revokeRegistrationAvatarPreview(previewImg);
  if (!file) {
    previewImg.src = "/static/images/default_avatar.png";
    return;
  }
  const objectUrl = URL.createObjectURL(file);
  previewImg.dataset.objectUrl = objectUrl;
  previewImg.onload = () => {
    if (previewImg.dataset && previewImg.dataset.objectUrl === objectUrl) {
      URL.revokeObjectURL(objectUrl);
      delete previewImg.dataset.objectUrl;
    }
    previewImg.onload = null;
    previewImg.onerror = null;
  };
  previewImg.onerror = () => {
    if (previewImg.dataset && previewImg.dataset.objectUrl === objectUrl) {
      URL.revokeObjectURL(objectUrl);
      delete previewImg.dataset.objectUrl;
    }
    previewImg.onload = null;
    previewImg.onerror = null;
  };
  previewImg.src = objectUrl;
}
function resetRegistrationAvatarPreviews() {
  setRegistrationAvatarPreview("auth-reg-avatar-preview", null);
  setRegistrationAvatarPreview("mobile-reg-avatar-preview", null);
}
async function confirmCropForRegistration() {
  if (!avatarCropper) {
    // showModalAlert("裁剪器未初始化", "错误");
    Swal.fire({
      title: "错误",
      text: "裁剪器未初始化",
      icon: "error",
    });
    return;
  }
  const canvas = avatarCropper.getCroppedCanvas({
    width: 200,
    height: 200,
    imageSmoothingQuality: "high",
  });
  if (!canvas) {
    // showModalAlert("裁剪失败", "错误");
    Swal.fire({
      title: "错误",
      text: "裁剪失败",
      icon: "error",
    });
    return;
  }
  canvas.toBlob(
    function (blob) {
      registrationCroppedAvatarBlob = new File([blob], "avatar.jpg", {
        type: "image/jpeg",
      });
      setRegistrationAvatarPreview(
        "auth-reg-avatar-preview",
        registrationCroppedAvatarBlob,
      );
      setRegistrationAvatarPreview(
        "mobile-reg-avatar-preview",
        registrationCroppedAvatarBlob,
      );
      closeCropModal();
    },
    "image/jpeg",
    0.9,
  );
}

async function confirmCropAndUpload() {
  if (isRegistrationCrop) {
    await confirmCropForRegistration();
  } else {
    if (!avatarCropper) {
      // showModalAlert("裁剪器未初始化", "错误");
      Swal.fire({
        title: "错误",
        text: "裁剪器未初始化",
        icon: "error",
      });
      return;
    }

    const canvas = avatarCropper.getCroppedCanvas({
      width: 200,
      height: 200,
      imageSmoothingEnabled: true,
      imageSmoothingQuality: "high",
    });

    if (!canvas) {
      // showModalAlert("裁剪失败", "错误");
      Swal.fire({
        title: "错误",
        text: "裁剪失败",
        icon: "error",
      });
      return;
    }

    canvas.toBlob(
      async function (blob) {
        const avatarFile = new File([blob], "avatar.jpg", {
          type: "image/jpeg",
        });

        closeCropModal();

        const formData = new FormData();
        formData.append("avatar", avatarFile);

        try {
          const response = await fetch("/auth/user/upload_avatar", {
            method: "POST",
            headers: {
              "X-Session-ID": sessionUUID,
            },
            body: formData,
          });
          const result = await response.json();

          if (result.success) {
            // showModalAlert("头像上传成功！", "成功");
            Swal.fire({
              title: "成功",
              text: "头像上传成功！",
              icon: "success",
            });

            croppedAvatarFile = null;

            const fileInput = $("profile-avatar-file");
            if (fileInput) {
              fileInput.value = "";
            }

            await loadPersonalInfo();
          } else {
            // showModalAlert(`上传失败: ${result.message}`, "错误");
            Swal.fire({
              title: "错误",
              text: `上传失败: ${result.message}`,
              icon: "error",
            });
          }
        } catch (e) {
          logMessage_Error("上传头像失败:", e);
          // showModalAlert(
          //   `上传失败: ${e.message}\n\n⚠️ 此功能需要后端API /auth/user/upload_avatar 支持`,
          //   "错误"
          // );
          Swal.fire({
            title: "错误",
            text: `上传失败: ${e.message}\n\n⚠️ 此功能需要后端API /auth/user/upload_avatar 支持`,
            icon: "error",
          });
        }
      },
      "image/jpeg",
      0.9,
    );
  }
}

async function uploadAvatar() {
  let fileToUpload = croppedAvatarFile;

  if (!fileToUpload) {
    const fileInput = $("profile-avatar-file");
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
      // showModalAlert("请先选择并裁剪图片文件", "提示");
      Swal.fire({
        title: "提示",
        text: "请先选择并裁剪图片文件",
        icon: "warning",
      });
      return;
    }
    fileToUpload = fileInput.files[0];
  }

  const formData = new FormData();
  formData.append("avatar", fileToUpload);

  try {
    const response = await fetch("/auth/user/upload_avatar", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
      },
      body: formData,
    });
    const result = await response.json();

    if (result.success) {
      // showModalAlert("头像上传成功！", "成功");
      Swal.fire({
        title: "成功",
        text: "头像上传成功！",
        icon: "success",
      });

      croppedAvatarFile = null;
      const fileInput = $("profile-avatar-file");
      if (fileInput) {
        fileInput.value = "";
      }
      await loadPersonalInfo();
    } else {
      // showModalAlert(`上传失败: ${result.message}`, "错误");
      Swal.fire({
        title: "错误",
        text: `上传失败: ${result.message}`,
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("上传头像失败:", e);
    // showModalAlert(`上传失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: `上传失败: ${e.message}`,
      icon: "error",
    });
  }
}
async function updateBasicInfo() {
  const nickname = $("profile-nickname");
  const phone = $("profile-phone");

  if (!nickname || !phone) return;

  if (!nickname.value.trim()) {
    // showModalAlert("昵称不能为空", "提示");
    Swal.fire({
      title: "提示",
      text: "昵称不能为空",
      icon: "warning",
    });
    return;
  }

  if (!currentAuthUsername) {
    // showModalAlert("无法获取当前用户信息，请重新加载", "错误");
    Swal.fire({
      title: "错误",
      text: "无法获取当前用户信息，请重新加载",
      icon: "error",
    });
    return;
  }

  try {
    const response = await fetch(
      "/api/admin/users/" +
        encodeURIComponent(currentAuthUsername) +
        "/basic_info",
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
        body: JSON.stringify({
          nickname: nickname.value.trim(),
        }),
      },
    );

    const result = await response.json();
    if (result.success) {
      // showModalAlert("基本信息更新成功", "成功");
      Swal.fire({
        title: "成功",
        text: "基本信息更新成功",
        icon: "success",
      });
    } else {
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (error) {
    logMessage_Error("更新基本信息失败", error);
    // showModalAlert("网络错误，请稍后重试", "错误");
    Swal.fire({
      title: "错误",
      text: "网络错误，请稍后重试",
      icon: "error",
    });
  }
}
// ========================================
// 【密码修改】短信验证模式相关全局状态和函数
// ========================================

// 全局状态：当前验证模式 ('password' 或 'sms')
// PC端密码验证模式状态，默认为'password'（使用原密码验证）
let pcPasswordVerifyMode = "password";
// 移动端密码验证模式状态，默认为'password'（使用原密码验证）
let mobilePasswordVerifyMode = "password";

/**
 * 切换密码验证模式（密码验证 <-> 短信验证）
 * 该函数用于在修改密码时切换使用原密码验证还是短信验证码验证
 *
 * @param {string} platform - 平台标识，'pc' 或 'mobile'
 */
function toggleSmsVerifyMode(platform) {
  // 根据平台选择对应的DOM元素和状态变量
  if (platform === "pc") {
    // 获取PC端的密码输入区域
    const passwordSection = document.getElementById(
      "pc-password-verify-section",
    );
    // 获取PC端的短信验证区域
    const smsSection = document.getElementById("pc-sms-verify-section");
    // 获取切换按钮
    const toggleBtn = document.getElementById("pc-sms-toggle-btn");

    // 判断当前模式并切换
    if (pcPasswordVerifyMode === "password") {
      // 从密码验证模式切换到短信验证模式
      passwordSection.classList.add("hidden"); // 隐藏密码输入区域
      smsSection.classList.remove("hidden"); // 显示短信验证区域
      toggleBtn.textContent = "返回密码验证"; // 更新按钮文字
      pcPasswordVerifyMode = "sms"; // 更新状态为短信验证模式
      logMessage_Info("[密码修改] PC端切换到短信验证模式");
    } else {
      // 从短信验证模式切换回密码验证模式
      passwordSection.classList.remove("hidden"); // 显示密码输入区域
      smsSection.classList.add("hidden"); // 隐藏短信验证区域
      toggleBtn.textContent = "使用短信验证"; // 更新按钮文字
      pcPasswordVerifyMode = "password"; // 更新状态为密码验证模式
      // 清空短信验证码输入框
      const smsCodeInput = document.getElementById("pc-password-sms-code");
      if (smsCodeInput) smsCodeInput.value = "";
      logMessage_Info("[密码修改] PC端切换到密码验证模式");
    }
  } else if (platform === "mobile") {
    // 获取移动端的密码输入区域
    const passwordSection = document.getElementById(
      "mobile-password-verify-section",
    );
    // 获取移动端的短信验证区域
    const smsSection = document.getElementById("mobile-sms-verify-section");
    // 获取切换按钮
    const toggleBtn = document.getElementById("mobile-sms-toggle-btn");

    // 判断当前模式并切换
    if (mobilePasswordVerifyMode === "password") {
      // 从密码验证模式切换到短信验证模式
      passwordSection.classList.add("hidden"); // 隐藏密码输入区域
      smsSection.classList.remove("hidden"); // 显示短信验证区域
      toggleBtn.textContent = "返回密码验证"; // 更新按钮文字
      mobilePasswordVerifyMode = "sms"; // 更新状态为短信验证模式
      logMessage_Info("[密码修改] 移动端切换到短信验证模式");
    } else {
      // 从短信验证模式切换回密码验证模式
      passwordSection.classList.remove("hidden"); // 显示密码输入区域
      smsSection.classList.add("hidden"); // 隐藏短信验证区域
      toggleBtn.textContent = "使用短信验证"; // 更新按钮文字
      mobilePasswordVerifyMode = "password"; // 更新状态为密码验证模式
      // 清空短信验证码输入框
      const smsCodeInput = document.getElementById("mobile-password-sms-code");
      if (smsCodeInput) smsCodeInput.value = "";
      logMessage_Info("[密码修改] 移动端切换到密码验证模式");
    }
  }
}

/**
 * 发送密码重置短信验证码
 * 该函数用于在短信验证模式下发送验证码到用户绑定的手机号
 *
 * @param {string} platform - 平台标识，'pc' 或 'mobile'
 */
async function sendPasswordResetSmsCode(platform) {
  // 根据平台获取对应的发送按钮
  const btn = document.getElementById(
    platform === "pc" ? "pc-send-sms-btn" : "mobile-send-sms-btn",
  );

  try {
    // 首先获取当前用户的绑定手机号
    // 通过API获取用户资料信息
    const response = await callPythonAPI_raw("/api/user/profile", "GET");

    // 检查API响应是否成功
    if (!response.success) {
      // showModalAlert("获取用户信息失败，请稍后重试", "错误");
      Swal.fire({
        title: "错误",
        text: "获取用户信息失败，请稍后重试",
        icon: "error",
      });
      return;
    }

    // 检查用户是否已绑定手机号
    if (!response.phone) {
      // showModalAlert(
      //   '您尚未绑定手机号，无法使用短信验证。\n请先在"安全设置"中绑定手机号。',
      //   "提示"
      // );
      Swal.fire({
        title: "提示",
        text: '您尚未绑定手机号，无法使用短信验证。\n请先在"个人信息"中绑定手机号。',
        icon: "info",
      });
      return;
    }

    // 调用验证码模态框，发送短信验证码到绑定的手机号
    // openCaptchaModal 会弹出图形验证码窗口，验证通过后发送短信
    openCaptchaModal({
      phone: response.phone, // 用户绑定的手机号
      button: btn, // 触发按钮，用于显示倒计时
      originalText: "发送验证码", // 按钮原始文字，倒计时结束后恢复
      scene: "password_reset", // 场景标识，后端可据此做不同处理
    });

    logMessage_Info(
      `[密码修改] ${platform}端请求发送短信验证码到手机: ${response.phone}`,
    );
  } catch (e) {
    // 捕获网络错误或其他异常
    logMessage_Error("[密码修改] 获取手机号失败:", e);
    // showModalAlert("获取手机号失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "获取手机号失败: " + e.message,
      icon: "error",
    });
  }
}

/**
 * 重置密码修改面板的验证模式到默认状态
 * 当面板关闭或需要重置时调用
 *
 * @param {string} platform - 平台标识，'pc'、'mobile' 或 'all'
 */
function resetPasswordVerifyMode(platform) {
  // 重置PC端
  if (platform === "pc" || platform === "all") {
    pcPasswordVerifyMode = "password";
    const pcPasswordSection = document.getElementById(
      "pc-password-verify-section",
    );
    const pcSmsSection = document.getElementById("pc-sms-verify-section");
    const pcToggleBtn = document.getElementById("pc-sms-toggle-btn");
    const pcSmsCodeInput = document.getElementById("pc-password-sms-code");

    if (pcPasswordSection) pcPasswordSection.classList.remove("hidden");
    if (pcSmsSection) pcSmsSection.classList.add("hidden");
    if (pcToggleBtn) pcToggleBtn.textContent = "使用短信验证";
    if (pcSmsCodeInput) pcSmsCodeInput.value = "";
  }

  // 重置移动端
  if (platform === "mobile" || platform === "all") {
    mobilePasswordVerifyMode = "password";
    const mobilePasswordSection = document.getElementById(
      "mobile-password-verify-section",
    );
    const mobileSmsSection = document.getElementById(
      "mobile-sms-verify-section",
    );
    const mobileToggleBtn = document.getElementById("mobile-sms-toggle-btn");
    const mobileSmsCodeInput = document.getElementById(
      "mobile-password-sms-code",
    );

    if (mobilePasswordSection) mobilePasswordSection.classList.remove("hidden");
    if (mobileSmsSection) mobileSmsSection.classList.add("hidden");
    if (mobileToggleBtn) mobileToggleBtn.textContent = "使用短信验证";
    if (mobileSmsCodeInput) mobileSmsCodeInput.value = "";
  }
}

/**
 * PC端修改密码函数
 * 支持两种验证模式：原密码验证 或 短信验证码验证
 */
