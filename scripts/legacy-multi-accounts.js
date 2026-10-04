// Multi-account status, list rendering, and monitoring helpers.

function onAccountsUpdated(accounts) {
  try {
    renderMultiAccountList(accounts);
  } catch (e) {
    logMessage_Error("onAccountsUpdated render failed:", e);
  }
}

function calculateStatusText(
  account,
  onlyIncomplete = false,
  ignoreTaskTime = false,
) {
  if (!account || !account.tasks || !Array.isArray(account.tasks)) {
    return "无任务数据";
  }

  let executableCount = 0;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  account.tasks.forEach((task) => {
    if (onlyIncomplete && task.status == 1) {
      return;
    }
    let isExpired = false;
    let isNotStarted = false;

    const startTimeStr = task.start_time
      ? task.start_time.replace(/-/g, "/")
      : null;
    const endTimeStr = task.end_time ? task.end_time.replace(/-/g, "/") : null;

    const startTime = startTimeStr ? new Date(startTimeStr) : null;
    const endTime = endTimeStr ? new Date(endTimeStr) : null;

    if (ignoreTaskTime) {
      if (startTime) {
        const startDate = new Date(
          startTime.getFullYear(),
          startTime.getMonth(),
          startTime.getDate(),
        );
        if (today < startDate) isNotStarted = true;
      }
      if (endTime) {
        const endDate = new Date(
          endTime.getFullYear(),
          endTime.getMonth(),
          endTime.getDate(),
        );
        if (today > endDate) isExpired = true;
      }
    } else {
      if (startTime && now < startTime) isNotStarted = true;
      if (endTime && now > endTime) isExpired = true;
    }

    if (isNotStarted || isExpired) {
      return;
    }

    executableCount++;
  });

  if (executableCount === 0) {
    return "无任务可执行";
  } else {
    return `有 ${executableCount} 个任务可执行`;
  }
}

function formatMultiAccountStatusText(
  statusText,
  summary,
  onlyIncomplete = true,
) {
  if (statusText !== "Have_Tasks") return statusText || "";
  if (!summary) return "有任务可执行";

  const unexpiredCount = Number(
    onlyIncomplete
      ? summary.unexpired_incomplete_count
      : summary.unexpired_count,
  ) || 0;
  const notStartedCount = Number(summary.not_started) || 0;
  const taskCount = Math.max(0, unexpiredCount - notStartedCount);
  return taskCount > 0
    ? `有 ${taskCount} 个任务可执行`
    : "无可执行任务";
}

function getMultiAccountStatusClass(statusText) {
  const baseClass =
    "status-text font-semibold text-xs px-2 py-0.5 rounded-full flex-shrink-0 whitespace-nowrap";
  const normalizedStatus = String(statusText || "").trim();

  if (normalizedStatus === "全部完成") {
    return `${baseClass} text-emerald-700 bg-emerald-100`;
  }
  if (normalizedStatus === "全部失败") {
    return `${baseClass} text-red-700 bg-red-100`;
  }
  if (normalizedStatus.startsWith("部分成功")) {
    return `${baseClass} text-amber-700 bg-amber-100`;
  }
  if (
    normalizedStatus.includes("无任务") ||
    normalizedStatus.includes("无可执行")
  ) {
    return `${baseClass} text-slate-500 bg-slate-100`;
  }
  return `${baseClass} text-sky-600 bg-sky-100`;
}

function updateAllAccountsStatusText() {
  try {
    if (
      !cachedMultiAccounts ||
      !Array.isArray(cachedMultiAccounts) ||
      cachedMultiAccounts.length === 0
    ) {
      return;
    }
    let onlyIncomplete = true;
    const mbChk = document.getElementById("mobile-multi-only-incomplete-check");
    const pcChk = document.getElementById("multi-run-only-incomplete-check");
    if (typeof isMobileMode !== "undefined" && isMobileMode && mbChk) {
      onlyIncomplete = mbChk.checked;
      if (pcChk) pcChk.checked = onlyIncomplete;
    } else if (pcChk) {
      onlyIncomplete = pcChk.checked;
      if (mbChk) mbChk.checked = onlyIncomplete;
    }
    // 读取 ignore_task_time 复选框状态（支持移动端和桌面端）
    // 不再从 pythonParams 读取，而是直接从页面上的复选框实时读取当前用户的选择
    let ignoreTaskTime = true; // 默认值：忽略任务时间

    // 获取移动端的 ignore_task_time 复选框元素
    // const mbIgnoreTimeChk = document.getElementById("mobile-multi-param-ignore_task_time");
    // 获取桌面端（PC端）的 ignore_task_time 复选框元素
    const pcIgnoreTimeChk = document.getElementById(
      "multi-param-ignore_task_time",
    );

    // 根据当前运行模式（移动端/桌面端）读取对应复选框的状态
    // if (typeof isMobileMode !== "undefined" && isMobileMode && mbIgnoreTimeChk) {
    //   // 如果当前是移动端模式，且移动端复选框存在，则从移动端复选框读取状态
    //   ignoreTaskTime = mbIgnoreTimeChk.checked;
    //   // 同步状态到桌面端复选框（保持两端状态一致）
    //   if (pcIgnoreTimeChk) pcIgnoreTimeChk.checked = ignoreTaskTime;
    // }

    // } else if (pcIgnoreTimeChk) {
    //   // 如果当前是桌面端模式，或移动端复选框不存在，则从桌面端复选框读取状态
    //   ignoreTaskTime = pcIgnoreTimeChk.checked;
    //   // 同步状态到移动端复选框（保持两端状态一致）
    //   if (mbIgnoreTimeChk) mbIgnoreTimeChk.checked = ignoreTaskTime;
    // }
    // 如果两个复选框都不存在，则使用默认值 true

    ignoreTaskTime = pcIgnoreTimeChk.checked;

    let updatedCount = 0;
    cachedMultiAccounts.forEach((account) => {
      // 按当前“仅执行未完成”和日期规则重算，不能直接使用未过期总数。
      const newStatusText = calculateStatusText(
        account,
        onlyIncomplete,
        ignoreTaskTime,
      );

      account.status_text = newStatusText;
      const pcItem = document.getElementById(`multi-acc-${account.username}`);
      if (pcItem) {
        const statusEl = pcItem.querySelector(".status-text");
        if (statusEl) {
          statusEl.textContent = newStatusText;
          statusEl.className = getMultiAccountStatusClass(newStatusText);
          updatedCount++;
        }
      }
      const mobileItem = document.getElementById(
        `mobile-multi-acc-${account.username}`,
      );
      if (mobileItem) {
        const statusEl = mobileItem.querySelector(".status-text");
        if (statusEl) {
          statusEl.textContent = newStatusText;
          statusEl.className = getMultiAccountStatusClass(newStatusText);
          updatedCount++;
        }
      }
    });
    console.log(
      `[状态刷新] 根据本地缓存已更新 ${updatedCount} 个账号状态 (OnlyIncomplete: ${onlyIncomplete}, IgnoreTime: ${ignoreTaskTime})`,
    );
  } catch (error) {
    console.error("[更新账号状态] 更新状态文本时发生错误:", error);
  }
}

const pendingMultiAccountStatusRefreshes = new Set();
const lastMultiAccountStatusRefreshRequest = new Map();
const MULTI_ACCOUNT_STATUS_REFRESH_COOLDOWN_MS = 10000;

async function requestMultiAccountStatusRefresh(username) {
  if (!username) return;
  const now = Date.now();
  const lastRequest = lastMultiAccountStatusRefreshRequest.get(username) || 0;
  if (
    pendingMultiAccountStatusRefreshes.has(username) ||
    now - lastRequest < MULTI_ACCOUNT_STATUS_REFRESH_COOLDOWN_MS
  ) {
    return;
  }

  pendingMultiAccountStatusRefreshes.add(username);
  lastMultiAccountStatusRefreshRequest.set(username, now);
  try {
    await callPythonAPI("multi_refresh_single_status", username);
  } catch (error) {
    logMessage_Debug(`自动刷新 Have_Tasks 账号 ${username} 失败:`, error);
  } finally {
    pendingMultiAccountStatusRefreshes.delete(username);
  }
}

function getMultiAccountProgressState(account) {
  const rawProgressPct = Number(account?.progress_pct);
  const progressPct = Number.isFinite(rawProgressPct)
    ? Math.max(0, Math.min(100, rawProgressPct))
    : 0;
  const progressText =
    typeof account?.progress_text === "string" &&
    account.progress_text.trim()
      ? account.progress_text
      : "未开始";
  const progressExtra =
    typeof account?.progress_extra === "string"
      ? account.progress_extra
      : "";

  return { progressPct, progressText, progressExtra };
}

function getMultiAccountStatusCategory(statusText) {
  const normalizedStatus = String(statusText || "").trim();
  if (
    normalizedStatus === "全部完成" ||
    normalizedStatus === "任务已完成" ||
    normalizedStatus.includes("执行流程完成")
  ) {
    return "已完成";
  }
  if (normalizedStatus === "全部失败") {
    return "全部失败";
  }
  if (normalizedStatus.startsWith("部分成功")) {
    return "部分成功";
  }
  if (
    normalizedStatus.includes("无任务") ||
    normalizedStatus.includes("无可执行")
  ) {
    return "无任务可执行";
  }
  if (
    ["运行", "登录", "分析", "等待", "延迟", "排队", "正在"].some((keyword) =>
      normalizedStatus.includes(keyword),
    )
  ) {
    return "运行中";
  }
  if (normalizedStatus.includes("待命")) {
    return "待命";
  }
  return "其他";
}

function normalizeMultiAccountGender(gender) {
  const normalizedGender = String(gender ?? "").trim().toLowerCase();
  if (["男", "male", "m", "1"].includes(normalizedGender)) {
    return "男";
  }
  if (["女", "female", "f", "2"].includes(normalizedGender)) {
    return "女";
  }
  return "未知";
}

function filterMultiAccountExpandedAccounts(accounts, filters = {}) {
  const statusFilter = String(filters.status || "全部");
  const genderFilter = String(filters.gender || "全部");
  const executableFilter = String(filters.executable || "全部");
  const attendanceFilter = String(filters.attendance || "全部");
  const tagFilter = String(filters.tag || "全部");
  const keywordFilter = String(filters.keyword || "").trim().toLowerCase();

  return (Array.isArray(accounts) ? accounts : []).filter((account) => {
    const displayStatus = formatMultiAccountStatusText(
      account.status_text,
      account.summary,
      true,
    );
    const statusCategory = getMultiAccountStatusCategory(displayStatus);
    const gender = normalizeMultiAccountGender(
      account.gender ?? account.user_data?.gender,
    );
    const executableCount = Number(account.summary?.executable) || 0;
    const attPending = Number(account.summary?.att_pending) || 0;
    const attCompleted = Number(account.summary?.att_completed) || 0;
    const attExpired = Number(account.summary?.att_expired) || 0;
    const tag = String(account.tag || "").trim();

    if (keywordFilter) {
      const searchableText = [
        account.username,
        account.name,
        tag,
      ]
        .map((value) => String(value || "").toLowerCase())
        .join(" ");
      if (!searchableText.includes(keywordFilter)) {
        return false;
      }
    }

    if (statusFilter !== "全部" && statusCategory !== statusFilter) {
      return false;
    }
    if (genderFilter !== "全部" && gender !== genderFilter) {
      return false;
    }
    if (
      executableFilter === "有可执行任务" &&
      executableCount <= 0
    ) {
      return false;
    }
    if (
      executableFilter === "无可执行任务" &&
      executableCount > 0
    ) {
      return false;
    }
    if (tagFilter !== "全部" && tag !== tagFilter) {
      return false;
    }
    if (attendanceFilter === "有待签任务" && attPending <= 0) {
      return false;
    }
    if (attendanceFilter === "无待签任务" && attPending > 0) {
      return false;
    }
    if (attendanceFilter === "有已签任务" && attCompleted <= 0) {
      return false;
    }
    if (attendanceFilter === "有签到过期" && attExpired <= 0) {
      return false;
    }
    return true;
  });
}

function buildExpandedMultiAccountCard(account) {
  const summary = account.summary || {};
  const displayStatus = formatMultiAccountStatusText(
    account.status_text,
    summary,
    true,
  );
  const gender = normalizeMultiAccountGender(
    account.gender ?? account.user_data?.gender,
  );
  const { progressPct, progressText, progressExtra } =
    getMultiAccountProgressState(account);
  const safeName = escapeHtml(account.name || account.username || "---");
  const safeUsername = escapeHtml(account.username || "");
  const safeTag = account.tag ? escapeHtml(account.tag) : "";

  return `
    <div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-white via-white to-slate-50 p-4 text-left shadow-sm transition-shadow hover:shadow-md">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="truncate text-sm font-bold text-slate-800">${safeName}</div>
          <div class="text-xs text-slate-500">${safeUsername} · ${gender}</div>
          ${safeTag ? `<div class="mt-1 text-xs font-medium text-purple-600">🏷️ ${safeTag}</div>` : ""}
        </div>
        <span class="${getMultiAccountStatusClass(displayStatus)}">${escapeHtml(
          displayStatus,
        )}</span>
      </div>
      <div class="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-slate-50 p-3 text-center text-xs text-slate-600 sm:grid-cols-5">
        <div>总数 <strong class="text-slate-800">${summary.total || 0}</strong></div>
        <div>完成 <strong class="text-emerald-600">${summary.completed || 0}</strong></div>
        <div>未开始 <strong class="text-slate-700">${summary.not_started || 0}</strong></div>
        <div>可跑 <strong class="text-amber-600">${summary.executable || 0}</strong></div>
        <div>过期 <strong class="text-red-600">${summary.expired || 0}</strong></div>
      </div>
      <div class="mt-2 grid grid-cols-3 gap-2 rounded-xl border border-slate-100 bg-white p-3 text-center text-xs text-slate-600">
        <div>待签 <strong class="text-sky-600">${summary.att_pending || 0}</strong></div>
        <div>已签 <strong class="text-emerald-600">${summary.att_completed || 0}</strong></div>
        <div>过期 <strong class="text-red-600">${summary.att_expired || 0}</strong></div>
      </div>
      <div class="mt-3">
        <div class="h-2 overflow-hidden rounded-full bg-slate-200">
          <div class="h-2 rounded-full bg-sky-500" style="width:${progressPct}%"></div>
        </div>
        <div class="mt-1 flex justify-between gap-3 text-xs">
          <span class="text-slate-600">${escapeHtml(progressText)}</span>
          <span class="text-slate-400">${escapeHtml(progressExtra)}</span>
        </div>
      </div>
      <div class="mt-3 flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-3">
        <button type="button" data-expanded-action="remove" data-username="${safeUsername}" class="btn btn-danger !py-1 !px-3 !text-xs">移除</button>
        <button type="button" data-expanded-action="refresh" data-username="${safeUsername}" class="btn btn-ghost !py-1 !px-3 !text-xs">刷新</button>
        <button type="button" data-expanded-action="start" data-username="${safeUsername}" class="btn btn-success !py-1 !px-3 !text-xs">开始</button>
        <button type="button" data-expanded-action="stop" data-username="${safeUsername}" class="btn btn-warning !py-1 !px-3 !text-xs">停止</button>
      </div>
    </div>
  `;
}

async function openMultiAccountExpandedView() {
  let accounts = Array.isArray(cachedMultiAccounts)
    ? cachedMultiAccounts.slice()
    : [];

  if (!accounts.length) {
    const response = await callPythonAPI("multi_get_all_accounts_status");
    accounts = Array.isArray(response?.accounts) ? response.accounts : [];
    cachedMultiAccounts = accounts;
  }

  const availableTags = Array.from(
    new Set(
      accounts
        .map((account) => String(account.tag || "").trim())
        .filter(Boolean),
    ),
  ).sort((left, right) => left.localeCompare(right, "zh-CN"));
  const tagOptionsHtml = availableTags
    .map(
      (tag) =>
        `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`,
    )
    .join("");

  const filterHtml = `
    <div class="mb-4 grid grid-cols-1 gap-3 rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-sky-50/50 p-4 text-left sm:grid-cols-2 lg:grid-cols-3">
      <label class="text-xs font-semibold text-slate-600">
        关键词
        <input data-expanded-filter="keyword" type="search" placeholder="账号 / 姓名 / 标签" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100">
      </label>
      <label class="text-xs font-semibold text-slate-600">
        任务状态
        <select data-expanded-filter="status" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="全部">全部任务状态</option>
          <option value="运行中">运行中</option>
          <option value="已完成">已完成</option>
          <option value="全部失败">全部失败</option>
          <option value="部分成功">部分成功</option>
          <option value="无任务可执行">无任务可执行</option>
          <option value="待命">待命</option>
          <option value="其他">其他</option>
        </select>
      </label>
      <label class="text-xs font-semibold text-slate-600">
        性别
        <select data-expanded-filter="gender" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="全部">全部性别</option>
          <option value="男">男</option>
          <option value="女">女</option>
          <option value="未知">未知</option>
        </select>
      </label>
      <label class="text-xs font-semibold text-slate-600">
        可执行任务
        <select data-expanded-filter="executable" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="全部">全部</option>
          <option value="有可执行任务">有可执行任务</option>
          <option value="无可执行任务">无可执行任务</option>
        </select>
      </label>
      <label class="text-xs font-semibold text-slate-600">
        签到状态
        <select data-expanded-filter="attendance" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="全部">全部签到状态</option>
          <option value="有待签任务">有待签任务</option>
          <option value="无待签任务">无待签任务</option>
          <option value="有已签任务">有已签任务</option>
          <option value="有签到过期">有签到过期</option>
        </select>
      </label>
      <label class="text-xs font-semibold text-slate-600">
        标签
        <select data-expanded-filter="tag" class="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
          <option value="全部">全部标签</option>
          ${tagOptionsHtml}
        </select>
      </label>
    </div>
    <div class="mb-3 flex items-center justify-between text-xs text-slate-500">
      <span id="expanded-multi-account-count"></span>
      <button type="button" id="expanded-multi-account-reset" class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-600 hover:bg-slate-100">重置筛选</button>
    </div>
    <div id="expanded-multi-account-cards" class="max-h-[62vh] space-y-3 overflow-y-auto pr-1"></div>
  `;

  await Swal.fire({
    title: "多账号列表",
    html: filterHtml,
    width: "min(1100px, 96vw)",
    showCloseButton: true,
    showCancelButton: true,
    showConfirmButton: false,
    cancelButtonText: "关闭",
    didOpen: () => {
      const root = document.querySelector(".swal2-html-container");
      if (!root) return;
      const statusSelect = root.querySelector(
        '[data-expanded-filter="status"]',
      );
      const genderSelect = root.querySelector(
        '[data-expanded-filter="gender"]',
      );
      const executableSelect = root.querySelector(
        '[data-expanded-filter="executable"]',
      );
      const attendanceSelect = root.querySelector(
        '[data-expanded-filter="attendance"]',
      );
      const tagSelect = root.querySelector(
        '[data-expanded-filter="tag"]',
      );
      const keywordInput = root.querySelector(
        '[data-expanded-filter="keyword"]',
      );
      const countEl = root.querySelector("#expanded-multi-account-count");
      const cardsEl = root.querySelector("#expanded-multi-account-cards");

      const renderFilteredCards = () => {
        const currentAccounts = Array.isArray(cachedMultiAccounts)
          ? cachedMultiAccounts
          : accounts;
        const filteredAccounts = filterMultiAccountExpandedAccounts(currentAccounts, {
          status: statusSelect?.value,
          gender: genderSelect?.value,
          executable: executableSelect?.value,
          attendance: attendanceSelect?.value,
          tag: tagSelect?.value,
          keyword: keywordInput?.value,
        });
        countEl.textContent = `显示 ${filteredAccounts.length} / ${currentAccounts.length} 个账号`;
        cardsEl.innerHTML = filteredAccounts.length
          ? filteredAccounts.map(buildExpandedMultiAccountCard).join("")
          : '<div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">没有符合筛选条件的账号</div>';
      };

      [
        statusSelect,
        genderSelect,
        executableSelect,
        attendanceSelect,
        tagSelect,
      ].forEach((select) => {
        select?.addEventListener("change", renderFilteredCards);
      });
      keywordInput?.addEventListener("input", renderFilteredCards);

      cardsEl?.addEventListener("click", async (event) => {
        const actionButton = event.target.closest("[data-expanded-action]");
        if (!actionButton) return;
        const username = actionButton.dataset.username;
        const action = actionButton.dataset.expandedAction;
        if (!username || !action) return;

        actionButton.disabled = true;
        try {
          if (action === "remove") {
            await multi_removeAccount(username);
          } else if (action === "refresh") {
            await callPythonAPI("multi_refresh_single_status", username);
          } else if (action === "start") {
            const canStart = await checkOverdueBeforeStart(username);
            if (canStart) {
              const runOnly =
                document.getElementById(
                  "multi-run-only-incomplete-check",
                )?.checked ?? true;
              const result = await callPythonAPI(
                "multi_start_single_account",
                username,
                runOnly,
              );
              if (!result?.success) {
                showModalAlert(result?.message || "启动失败", "错误");
              }
            }
          } else if (action === "stop") {
            await callPythonAPI("multi_stop_single_account", username);
          }
        } catch (error) {
          logMessage_Error(`展开列表操作失败: ${error}`);
        } finally {
          if (document.body.contains(actionButton)) {
            actionButton.disabled = false;
          }
          renderFilteredCards();
        }
      });

      root
        .querySelector("#expanded-multi-account-reset")
        ?.addEventListener("click", () => {
          if (statusSelect) statusSelect.value = "全部";
          if (genderSelect) genderSelect.value = "全部";
          if (executableSelect) executableSelect.value = "全部";
          if (attendanceSelect) attendanceSelect.value = "全部";
          if (tagSelect) tagSelect.value = "全部";
          if (keywordInput) keywordInput.value = "";
          renderFilteredCards();
        });
      activeExpandedMultiAccountRefresh = renderFilteredCards;
      renderFilteredCards();
    },
    willClose: () => {
      activeExpandedMultiAccountRefresh = null;
    },
  });
}

function renderMultiAccountList(accounts) {
  cachedMultiAccounts = accounts;
  const renderToContainer = (containerId, isMobile) => {
    const listDiv = document.getElementById(containerId);
    if (!listDiv) return;

    listDiv.innerHTML = "";
    const countId = isMobile
      ? "mobile-multi-account-count"
      : "multi-account-count";
    const countEl = document.getElementById(countId);
    if (countEl)
      countEl.textContent = isMobile
        ? `${accounts.length} 个账号`
        : accounts.length;

    if (accounts.length === 0) {
      listDiv.innerHTML =
        '<p class="text-slate-400 text-center py-10">请先添加或导入账号</p>';
      return;
    }

    accounts.forEach((acc) => {
      const s = acc.summary;
      const onlyIncomplete =
        document.getElementById(
          isMobile
            ? "mobile-multi-only-incomplete-check"
            : "multi-run-only-incomplete-check",
        )?.checked ?? true;
      const displayStatusText = formatMultiAccountStatusText(
        acc.status_text,
        s,
        onlyIncomplete,
      );
      const { progressPct, progressText, progressExtra } =
        getMultiAccountProgressState(acc);
      if (acc.status_text === "Have_Tasks") {
        void requestMultiAccountStatusRefresh(acc.username);
      } else {
        lastMultiAccountStatusRefreshRequest.delete(acc.username);
      }
      const item = document.createElement("div");
      const prefix = isMobile ? "mobile-multi-acc-" : "multi-acc-";
      item.id = `${prefix}${acc.username}`;
      item.dataset.username = acc.username;
      item.className =
        "p-3 rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50/80 mb-2 text-sm relative min-w-0 overflow-hidden shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md";
      item.innerHTML = `
                    <div class="${isMobile ? "flex flex-col gap-2 min-w-0" : "flex items-start justify-between gap-3 min-w-0"}">
                        <div class="font-bold text-slate-800 flex items-start gap-2 min-w-0 ${isMobile ? "" : "flex-1"}">
                            <input type="checkbox" class="account-checkbox w-4 h-4 accent-sky-600 rounded flex-shrink-0 mt-1" style="position: static !important; transform: none !important;">
                            <div class="min-w-0 flex-1">
                                <span class="account-name block truncate">${
                                  acc.name
                                }</span>
                                <span class="text-xs text-slate-500 font-normal block">(${
                                  acc.username
                                })</span>
                                ${
                                  acc.tag
                                    ? `<span class="text-xs text-purple-600 font-medium block">🏷️ ${acc.tag}</span>`
                                    : ""
                                }
                            </div>
                        </div>
                        <span class="${getMultiAccountStatusClass(
                          displayStatusText,
                        )}">${
                          displayStatusText
                        }</span>
                    </div>

                    <div class="grid grid-cols-5 gap-2 rounded-xl bg-slate-50/80 p-2 text-center text-xs mt-2 text-slate-600">
                        <div>总数: <span class="summary-total font-bold">${
                          s.total
                        }</span></div>
                        <div>完成: <span class="summary-completed font-bold text-emerald-600">${
                          s.completed
                        }</span></div>
                        <div>未开始: <span class="summary-notstarted font-bold text-slate-600">${
                          s.not_started
                        }</span></div>
                        <div>可跑: <span class="summary-executable font-bold text-amber-600">${
                          s.executable
                        }</span></div>
                        <div>过期: <span class="summary-expired font-bold text-red-600">${
                          s.expired
                        }</span></div>
                    </div>

                    <div class="grid grid-cols-3 gap-2 rounded-xl bg-sky-50/50 p-2 text-center text-xs mt-2 text-slate-600">
                        <div title="待签到任务">待签: <span class="summary-att-pending font-bold text-sky-600">${
                          s.att_pending || 0
                        }</span></div>
                        <div title="已签到任务">已签: <span class="summary-att-completed font-bold text-emerald-600">${
                          s.att_completed || 0
                        }</span></div>
                        <div title="已过期签到">过期: <span class="summary-att-expired font-bold text-red-600">${
                          s.att_expired || 0
                        }</span></div>
                    </div>

                    <div class="flex justify-end items-center gap-2 mt-2 pt-2 border-t">
                        <button class="btn-account-remove btn btn-danger !py-1 !px-3 !text-xs" data-username="${
                          acc.username
                        }">移除</button>
                        <button class="btn-account-refresh btn btn-ghost !py-1 !px-3 !text-xs" data-username="${
                          acc.username
                        }">刷新</button>
                        <button class="btn-account-start btn btn-success !py-1 !px-3 !text-xs" data-username="${
                          acc.username
                        }">开始</button>
                        <button class="btn-account-stop btn btn-warning !py-1 !px-3 !text-xs" data-username="${
                          acc.username
                        }">停止</button>
                        <button class="btn-account-params btn btn-ghost !py-1 !px-3 !text-xs" data-username="${
                          acc.username
                        }" style="display:none">设置</button>
                    </div>
                    <div class="mt-2">
                        <div class="h-2 bg-slate-200 rounded-full overflow-hidden">
                            <div class="progress-fill h-2 bg-sky-500" style="width:${progressPct}%"></div>
                        </div>
                        <div class="flex justify-between text-xs mt-1">
                            <span class="progress-text text-slate-600">${progressText}</span>
                            <span class="progress-extra text-slate-400">${progressExtra}</span>
                        </div>
                    </div>
                `;
      listDiv.appendChild(item);
    });

    listDiv.querySelectorAll(".btn-account-start").forEach(
      (b) =>
        (b.onclick = async (e) => {
          // ========== 添加欠费检查 ==========
          // 在开始单个账号前，检查该账号是否有欠费
          const username = e.target.dataset.username;
          const canStart = await checkOverdueBeforeStart(username);
          if (!canStart) {
            // 欠费检查未通过，直接返回不启动任务
            return;
          }
          // ========== 欠费检查结束 ==========

          const checkboxId = isMobile
            ? "mobile-multi-only-incomplete-check"
            : "multi-run-only-incomplete-check";
          const runOnly = document.getElementById(checkboxId)?.checked ?? true;
          const result = await callPythonAPI(
            "multi_start_single_account",
            username,
            runOnly,
          );
          if (!result || !result.success) {
            Swal.fire({
              title: "无法启动任务",
              text: result?.message || "启动失败",
              icon: "warning",
            });
          }
        }),
    );

    listDiv
      .querySelectorAll(".btn-account-stop")
      .forEach(
        (b) =>
          (b.onclick = (e) =>
            callPythonAPI(
              "multi_stop_single_account",
              e.target.dataset.username,
            )),
      );

    listDiv.querySelectorAll(".btn-account-remove").forEach((b) => {
      b.onclick = async (e) => {
        await multi_removeAccount(e.currentTarget.dataset.username);
      };
    });

    listDiv.querySelectorAll(".btn-account-refresh").forEach((b) => {
      b.onclick = async (e) => {
        const u = e.currentTarget.dataset.username;
        const itemPrefix = isMobile ? "mobile-multi-acc-" : "multi-acc-";
        const item = document.getElementById(`${itemPrefix}${u}`);
        if (item) {
          const statusEl = item.querySelector(".status-text");
          if (statusEl) statusEl.textContent = "刷新中...";
        }
        const result = await callPythonAPI("multi_refresh_single_status", u);
        if (!result || !result.success) {
          // showModalAlert(result?.message || "刷新失败");
          swal.fire({
            title: "错误",
            text: result?.message || "刷新失败",
            icon: "error",
          });
        }
      };
    });

    listDiv.querySelectorAll(".btn-account-params").forEach((b) => {
      b.onclick = (e) => {
        if (isMobile) {
          openMobileAccountParams(e.target.dataset.username);
        } else {
          openAccountParamsModal(e.target.dataset.username);
        }
      };
    });
  };

  renderToContainer("multi-account-list", false);

  renderToContainer("mobile-multi-account-list", true);

  if (typeof updateSelectAllCheckboxState === "function")
    updateSelectAllCheckboxState();
  if (typeof updateMobileSelectAllCheckboxState === "function")
    updateMobileSelectAllCheckboxState();
  if (typeof activeExpandedMultiAccountRefresh === "function")
    activeExpandedMultiAccountRefresh();
}

function multi_toggleSelectAll(event) {
  const isChecked = event.target.checked;
  const container = document.getElementById("multi-account-list");
  if (container) {
    container
      .querySelectorAll(".account-checkbox")
      .forEach((cb) => (cb.checked = isChecked));
  }
}

function updateSelectAllCheckboxState() {
  const container = document.getElementById("multi-account-list");
  if (!container) return;

  const allCheckboxes = container.querySelectorAll(".account-checkbox");
  const checkedCount = container.querySelectorAll(
    ".account-checkbox:checked",
  ).length;
  const selectAllCheckbox = $("multi-select-all-check");
  if (allCheckboxes.length > 0) {
    selectAllCheckbox.checked = checkedCount === allCheckboxes.length;
    selectAllCheckbox.indeterminate =
      checkedCount > 0 && checkedCount < allCheckboxes.length;
  } else {
    selectAllCheckbox.checked = false;
    selectAllCheckbox.indeterminate = false;
  }
}

function bindMultiAccountListChangeHandler() {
  const container = document.getElementById("multi-account-list");
  if (!container || container.dataset.changeHandlerBound === "true") {
    return;
  }
  container.addEventListener("change", (event) => {
    if (event.target.classList.contains("account-checkbox")) {
      updateSelectAllCheckboxState();
    }
  });
  container.dataset.changeHandlerBound = "true";
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindMultiAccountListChangeHandler);
} else {
  bindMultiAccountListChangeHandler();
}

async function multi_removeAccount(username) {
  if (!username) return;

  const isConfirmed = await jsShowConfirm(
    "确认移除账号",
    `确定要移除账号 <span style='color:red;font-weight:bold;'>${escapeHtml(
      username,
    )}</span> 吗？<br>此操作不可撤销。`,
  );
  if (!isConfirmed) return;

  const result = await callPythonAPI("multi_remove_account", username);
  if (result && result.accounts) {
    renderMultiAccountList(result.accounts);
  }
}

async function multi_removeAll(confirm = false) {
  if (confirm && typeof confirm === "object" && confirm.type === "click") {
    confirm = false;
  }
  let isConfirmed = false;

  if (!confirm) {
    logMessage_Info("准备移除列表中的所有账号");
    isConfirmed = await jsShowConfirm(
      "确认移除全部",
      "确定要移除列表中的<span style='color:red;font-weight:bold;'>所有账号</span>吗？<br>此操作<span style='color:red;'>不可撤销</span>，所有账号数据将丢失！",
    );
  } else {
    logMessage_Info("移除列表中的所有账号");
    isConfirmed = true;
  }
  if (isConfirmed) {
    const result = await callPythonAPI("multi_remove_all_accounts");
    if (result && result.accounts) renderMultiAccountList(result.accounts);
  }
}

async function multi_removeSelected(confirm = false) {
  if (confirm && typeof confirm === "object" && confirm.type === "click") {
    confirm = false;
  }
  const container = document.getElementById("multi-account-list");
  if (!container) return;

  const selectedUsernames = Array.from(
    container.querySelectorAll(".account-checkbox:checked"),
  ).map((cb) => cb.closest("[data-username]").dataset.username);
  if (selectedUsernames.length === 0) {
    // showModalAlert("请至少选择一个要移除的账号。", "提示");
    swal.fire({
      title: "提示",
      text: "请至少选择一个要移除的账号。",
      icon: "info",
    });
    return;
  }
  let isConfirmed = false;

  if (!confirm) {
    logMessage_Info(`准备移除选中的账号: ${selectedUsernames.join(", ")}`);
    isConfirmed = await jsShowConfirm(
      "确认移除选中",
      `确定要移除选中的 <span style='color:red;font-weight:bold;'>${
        selectedUsernames.length
      }</span> 个账号吗？<br>账号: ${selectedUsernames.join(", ")}`,
    );
  } else {
    logMessage_Info(`移除选中的账号: ${selectedUsernames.join(", ")}`);
    isConfirmed = true;
  }
  if (isConfirmed) {
    const result = await callPythonAPI(
      "multi_remove_selected_accounts",
      selectedUsernames,
    );
    if (result && result.accounts) renderMultiAccountList(result.accounts);
  }
}

function multi_getSelectedUsernames() {
  const container = document.getElementById("multi-account-list");
  if (!container) return [];

  return Array.from(container.querySelectorAll(".account-checkbox:checked"))
    .map((cb) => cb.closest("[data-username]")?.dataset?.username)
    .filter(Boolean);
}

async function multi_startSelected() {
  // ========== 步骤1：获取选中的账号列表 ==========
  // 通过复选框获取用户选择要启动的账号
  const usernames = multi_getSelectedUsernames();

  // ========== 步骤2：验证是否选择了账号 ==========
  if (usernames.length === 0) {
    // 如果没有选中任何账号，提示用户并退出
    // showModalAlert('请至少选择一个账号再执行"开始选中"。');
    swal.fire({
      title: "提示",
      text: "请至少选择一个账号再执行“开始选中”。",
      icon: "info",
    });
    return;
  }

  // ========== 步骤3：欠费检查（只检查选中的账号）==========
  // 【重要】这里传入选中的账号列表，只检查这些账号的欠费情况
  // 不再检查用户的所有账号，避免误报未选中账号的欠费
  const canStart = await checkOverdueBeforeStart(usernames);
  if (!canStart) {
    // 欠费检查未通过，用户选择不缴费或取消，直接返回不启动任务
    return;
  }
  // ========== 欠费检查结束 ==========

  const use_delay = $("multi-use-delay-check")?.checked ?? true;
  const min_delay = parseInt($("multi-min-delay-input")?.value) || 0;
  const max_delay = parseInt($("multi-max-delay-input")?.value) || 300;
  const run_only_incomplete =
    $("multi-run-only-incomplete-check")?.checked ?? true;

  for (const u of usernames) {
    try {
      if (use_delay && max_delay >= min_delay) {
        const d = Math.random() * (max_delay - min_delay) + min_delay;
        await new Promise((res) => setTimeout(res, d * 10));
      }

      // 调用后端 API 启动单个账号
      const result = await callPythonAPI(
        "multi_start_single_account",
        u,
        run_only_incomplete,
      );

      // 检查是否是欠费错误
      // 后端在检测到欠费时会返回特定的错误代码
      if (
        result &&
        !result.success &&
        result.error_code === "OVERDUE_PAYMENT"
      ) {
        // 构建欠费账号列表的显示文本
        let overdueList = "";
        if (result.overdue_accounts && result.overdue_accounts.length > 0) {
          // 遍历每个欠费账号，格式化为易读的文本
          overdueList = result.overdue_accounts
            .map((acc) => `${acc.school_username} (欠费${acc.overdue_count}次)`)
            .join("\n");
        }

        // 构建完整的提示消息
        const message = `检测到以下账号存在欠费：\n\n${overdueList}\n\n请先完成缴费后再执行任务。`;

        // 显示友好的弹窗提示
        // showModalAlert(message, "欠费提示");
        swal.fire({
          title: "欠费提示",
          text: message,
          icon: "warning",
        });

        // 可选：自动跳转到缴费页面
        // switchToTab('tab4'); // 取消注释此行以启用自动跳转

        // 发现欠费后，停止启动其他账号
        break;
      }
    } catch (e) {
      logMessage_Error(`开始账号 ${u} 失败`, e);
    }
  }
}

async function multi_stopSelected() {
  const usernames = multi_getSelectedUsernames();
  if (usernames.length === 0) {
    // showModalAlert("请至少选择一个账号再执行“停止选中”。");
    swal.fire({
      title: "提示",
      text: "请至少选择一个账号再执行“停止选中”。",
      icon: "info",
    });
    return;
  }
  for (const u of usernames) {
    try {
      await callPythonAPI("multi_stop_single_account", u);
    } catch (e) {
      logMessage_Error(`停止账号 ${u} 失败`, e);
    }
  }
}

async function multi_refreshSelected() {
  const usernames = multi_getSelectedUsernames();
  if (usernames.length === 0) {
    // showModalAlert("请至少选择一个账号再执行“刷新选中”。");
    swal.fire({
      title: "提示",
      text: "请至少选择一个账号再执行“刷新选中”。",
      icon: "info",
    });
    return;
  }
  for (const u of usernames) {
    try {
      const item = document.getElementById(`multi-acc-${u}`);
      if (item) {
        const statusEl = item.querySelector(".status-text");
        if (statusEl) statusEl.textContent = "刷新中...";
      }
      await callPythonAPI("multi_refresh_single_status", u);
    } catch (e) {
      logMessage_Error(`刷新账号 ${u} 失败`, e);
    }
  }
}

async function multi_refreshAll() {
  await callPythonAPI("multi_refresh_all_statuses");
}

let lastAccountListSignature = "";
let isMultiAccountAutoRefreshRunning = false;
let isMultiAccountAutoRefreshDesired = false;
let multiAccountAutoRefreshGeneration = 0;

function markMultiAccountRealtimeUpdate() {
  multiAccountAutoRefreshGeneration++;
}

function clearMultiAccountAutoRefreshTimer() {
  isMultiAccountAutoRefreshRunning = false;
  if (multiAccountAutoRefreshInterval) {
    clearTimeout(multiAccountAutoRefreshInterval);
    multiAccountAutoRefreshInterval = null;
  }
}

function startMultiAccountAutoRefresh(interval = 500) {
  clearMultiAccountAutoRefreshTimer();
  multiAccountAutoRefreshGeneration++;
  isMultiAccountAutoRefreshDesired = true;

  if (isWebSocketConnected()) {
    console.log("[多账号自动刷新] WebSocket 已连接，跳过轮询");
    return;
  }

  isMultiAccountAutoRefreshRunning = true;
  const refreshGeneration = multiAccountAutoRefreshGeneration;

  const refreshLoop = async () => {
    // 检查运行标志
    if (
      !isMultiAccountAutoRefreshDesired ||
      !isMultiAccountAutoRefreshRunning ||
      isWebSocketConnected()
    ) {
      return;
    }

    // 检查全局网络错误状态
    if (typeof isInNetworkErrorState !== "undefined" && isInNetworkErrorState) {
      // 如果处于网络错误状态，延长重试时间到 5 秒
      multiAccountAutoRefreshInterval = setTimeout(refreshLoop, 5000);
      return;
    }

    try {
      // 检查界面可见性
      const pcMultiApp = document.getElementById("multi-account-app");
      const mobileMultiApp = document.getElementById(
        "mobile-multi-account-app",
      );
      const isVisible =
        (pcMultiApp && !pcMultiApp.classList.contains("hidden")) ||
        (mobileMultiApp && !mobileMultiApp.classList.contains("hidden"));

      if (!isVisible) {
        // 如果界面不可见，降频到 2 秒一次
        multiAccountAutoRefreshInterval = setTimeout(refreshLoop, 2000);
        return;
      }

      // 使用loadInitialData替代直接调用API，利用其限流和缓存机制
      const response = await loadInitialData();

      if (
        refreshGeneration !== multiAccountAutoRefreshGeneration ||
        !isMultiAccountAutoRefreshDesired ||
        !isMultiAccountAutoRefreshRunning ||
        isWebSocketConnected()
      ) {
        return;
      }

      // 处理成功响应，从response.accounts中获取数据
      if (response && response.success && response.accounts) {
        const currentSignature = response.accounts
          .map((a) => a.username)
          .join("|");
        if (currentSignature !== lastAccountListSignature) {
          console.log("[多账号刷新] 账号列表结构变化，重绘 DOM");
          renderMultiAccountList(response.accounts);
          lastAccountListSignature = currentSignature;
        }

        // --- 全局统计变量 ---
        let runningCount = 0;
        let pausedCount = 0;
        let stoppedCount = 0;
        // -------------------------

        response.accounts.forEach((acc) => {
          if (!acc.username) return;

          // --- 统计逻辑 ---
          const s = acc.status_text || "";
          // 根据状态文本判断归类
          if (
            s.includes("运行") ||
            s.includes("登录") ||
            s.includes("等待") ||
            s.includes("延迟") ||
            s.includes("分析") ||
            s.includes("排队") ||
            s.includes("正在")
          ) {
            runningCount++;
          } else if (s.includes("暂停")) {
            pausedCount++;
          } else {
            stoppedCount++;
          }
          // ---------------------

          const updateData = {
            status_text: acc.status_text,
            name: acc.name,
            summary: acc.summary,
            progress_pct: acc.progress_pct,
            progress_text: acc.progress_text,
            progress_extra: acc.progress_extra,
          };
          multi_updateAccountStatus(acc.username, updateData);

          if (
            acc.current_position &&
            typeof acc.current_position.lon === "number" &&
            typeof acc.current_position.lat === "number"
          ) {
            multi_updateRunnerPosition(
              acc.username,
              acc.current_position.lon,
              acc.current_position.lat,
              acc.name || acc.username,
            );
          }
        });

        // --- 更新移动端全局状态面板 ---
        const mobileRunEl = document.getElementById(
          "mobile-multi-running-count",
        );
        if (mobileRunEl) mobileRunEl.textContent = runningCount;

        const mobilePauseEl = document.getElementById(
          "mobile-multi-paused-count",
        );
        if (mobilePauseEl) mobilePauseEl.textContent = pausedCount;
        // 如果有暂停的任务，显示暂停面板（原本是 display:none）
        const mobilePauseContainer = mobilePauseEl
          ? mobilePauseEl.closest(".text-center")
          : null;
        if (mobilePauseContainer) {
          mobilePauseContainer.style.display =
            pausedCount > 0 ? "block" : "none";
        }

        const mobileStopEl = document.getElementById(
          "mobile-multi-stopped-count",
        );
        if (mobileStopEl) mobileStopEl.textContent = stoppedCount;

        const mobileGlobalStatusEl = document.getElementById(
          "mobile-multi-global-status",
        );
        if (mobileGlobalStatusEl) {
          if (runningCount > 0) {
            mobileGlobalStatusEl.textContent = "运行中";
            mobileGlobalStatusEl.className =
              "text-sm font-bold px-4 py-1.5 rounded-full bg-green-100 text-green-700 shadow-sm";
          } else if (pausedCount > 0) {
            mobileGlobalStatusEl.textContent = "已暂停";
            mobileGlobalStatusEl.className =
              "text-sm font-bold px-4 py-1.5 rounded-full bg-yellow-100 text-yellow-700 shadow-sm";
          } else {
            mobileGlobalStatusEl.textContent = "就绪";
            mobileGlobalStatusEl.className =
              "text-sm font-bold px-4 py-1.5 rounded-full bg-gradient-to-r from-slate-100 to-slate-200 text-slate-700 shadow-sm";
          }
        }
        // ---------------------------------
      }

      // 请求成功，按正常间隔调度下一次
      if (
        isMultiAccountAutoRefreshDesired &&
        isMultiAccountAutoRefreshRunning &&
        !isWebSocketConnected()
      ) {
        multiAccountAutoRefreshInterval = setTimeout(refreshLoop, interval);
      }
    } catch (error) {
      console.error("[多账号自动刷新] 轮询请求失败:", error);

      // 严重错误检查：会话失效
      if (
        error.message &&
        (error.message.includes("会话已过期") ||
          error.message.includes("无效") ||
          error.message.includes("401"))
      ) {
        console.warn("[多账号自动刷新] 检测到会话失效，自动停止轮询。");
        stopMultiAccountAutoRefresh();
        return;
      }

      // 其他错误（如网络波动、服务器500等）：退避 5 秒后重试
      // 这里避免了死循环高频请求
      if (
        isMultiAccountAutoRefreshDesired &&
        isMultiAccountAutoRefreshRunning &&
        !isWebSocketConnected()
      ) {
        multiAccountAutoRefreshInterval = setTimeout(refreshLoop, 5000);
      }
    }
  };

  // 启动第一次执行
  refreshLoop();
  console.log(
    `[多账号自动刷新] 已启动 (间隔: ${interval}ms, 错误退避: 5000ms)`,
  );
}

function stopMultiAccountAutoRefresh() {
  isMultiAccountAutoRefreshDesired = false;
  multiAccountAutoRefreshGeneration++;
  const wasRunning = isMultiAccountAutoRefreshRunning;
  clearMultiAccountAutoRefreshTimer();
  if (wasRunning) {
    console.log("[多账号自动刷新] 已停止自动刷新");
  }
}

function syncMultiAccountAutoRefreshBySocketState() {
  if (isWebSocketConnected()) {
    clearMultiAccountAutoRefreshTimer();
    return;
  }
  if (
    isMultiAccountAutoRefreshDesired &&
    !isMultiAccountAutoRefreshRunning
  ) {
    startMultiAccountAutoRefresh(500);
  }
}

async function process_path_queue() {
  if (is_planning_path || path_planning_queue.length === 0) return;
  is_planning_path = true;
  const { username, waypoints } = path_planning_queue.shift();
  try {
    if (getActiveMapProvider() !== "amap") {
      throw new Error("旧版前端路径规划队列仅支持高德地图；请使用后端多地图供应商路径规划。");
    }
    logMessage_Info(`[JS-Queue] 开始处理 ${username} 的路径规划...`);
    const path = await getWalkingPath(waypoints);
    logMessage_Info(
      `[JS-Queue] 路径规划成功 for ${username}, 返回 ${path.length} 点给Python。`,
    );
    callPythonAPI("multi_path_generation_callback", username, true, path);
  } catch (error) {
    logMessage_Info(`[JS-Queue] 路径规划失败 for ${username}: ${error}`);
    callPythonAPI(
      "multi_path_generation_callback",
      username,
      false,
      String(error),
    );
  } finally {
    is_planning_path = false;
    setTimeout(process_path_queue, 100);
  }
}
function triggerPathGenerationForPy(username, waypoints) {
  logMessage_Info(`收到 ${username} 的路径规划请求，已加入队列。`);
  path_planning_queue.push({ username, waypoints });
  process_path_queue();
}

function updateMobileSelectAllCheckboxState() {
  const container = document.getElementById("mobile-multi-account-list");
  if (!container) return;

  const allCheckboxes = container.querySelectorAll(".account-checkbox");
  const checkedCount = container.querySelectorAll(
    ".account-checkbox:checked",
  ).length;
  const selectAllCheckbox = document.getElementById(
    "mobile-select-all-accounts",
  );

  if (selectAllCheckbox) {
    if (allCheckboxes.length > 0) {
      selectAllCheckbox.checked = checkedCount === allCheckboxes.length;
      selectAllCheckbox.indeterminate =
        checkedCount > 0 && checkedCount < allCheckboxes.length;
    } else {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
    }
  }
}

const mobileListDiv = document.getElementById("mobile-multi-account-list");
if (mobileListDiv) {
  mobileListDiv.addEventListener("change", (event) => {
    if (event.target.classList.contains("account-checkbox")) {
      updateMobileSelectAllCheckboxState();
    }
  });
}

function multi_updateAccountStatus(username, data) {
  const ids = [`multi-acc-${username}`, `mobile-multi-acc-${username}`];

  ids.forEach((id) => {
    const item = document.getElementById(id);
    if (!item) return;

    if (data.status_text) {
      if (data.status_text === "Have_Tasks") {
        void requestMultiAccountStatusRefresh(username);
      } else {
        lastMultiAccountStatusRefreshRequest.delete(username);
      }
      const statusEl = item.querySelector(".status-text");
      if (statusEl) {
        // 检查是否为"Have_Tasks"标记，需要前端计算实际状态
        if (data.status_text === "Have_Tasks" && data.summary) {
          const isMobile = id.startsWith("mobile-multi-acc-");
          const checkboxId = isMobile
            ? "mobile-multi-only-incomplete-check"
            : "multi-run-only-incomplete-check";
          const onlyIncomplete =
            document.getElementById(checkboxId)?.checked ?? true;
          statusEl.textContent = formatMultiAccountStatusText(
            data.status_text,
            data.summary,
            onlyIncomplete,
          );
        } else {
          statusEl.textContent = formatMultiAccountStatusText(
            data.status_text,
            data.summary,
          );
        }
        statusEl.className = getMultiAccountStatusClass(statusEl.textContent);
      }
    }
    if (data.name) {
      const nameEl = item.querySelector(".account-name");
      if (nameEl) nameEl.textContent = data.name;
    }

    if (data.summary) {
      const s = data.summary;
      const setVal = (sel, val) => {
        const el = item.querySelector(sel);
        if (el) el.textContent = val;
      };

      setVal(".summary-total", s.total);
      setVal(".summary-completed", s.completed);
      setVal(".summary-notstarted", s.not_started ?? 0);
      setVal(".summary-executable", s.executable);
      setVal(".summary-expired", s.expired);

      setVal(".summary-att-pending", s.att_pending || 0);
      setVal(".summary-att-completed", s.att_completed || 0);
      setVal(".summary-att-expired", s.att_expired || 0);
    }

    if (typeof data.progress_pct === "number") {
      const fill = item.querySelector(".progress-fill");
      if (fill)
        fill.style.width = `${Math.max(0, Math.min(100, data.progress_pct))}%`;
    }
    if (typeof data.progress_text === "string") {
      const label = item.querySelector(".progress-text");
      if (label) label.textContent = data.progress_text;
    }
    if (typeof data.progress_extra === "string") {
      const extra = item.querySelector(".progress-extra");
      if (extra) extra.textContent = data.progress_extra;
    }
  });

  const cachedAccount =
    typeof cachedMultiAccounts !== "undefined" &&
    Array.isArray(cachedMultiAccounts)
      ? cachedMultiAccounts.find((account) => account.username === username)
      : null;
  if (cachedAccount) {
    Object.assign(cachedAccount, data);
  }
  if (
    typeof activeExpandedMultiAccountRefresh !== "undefined" &&
    typeof activeExpandedMultiAccountRefresh === "function"
  ) {
    activeExpandedMultiAccountRefresh();
  }

  const currentStatus =
    typeof data.status_text === "string" && data.status_text.trim()
      ? data.status_text.trim()
      : "";
  const NON_RUNNING_STATUSES = new Set([
    "任务已完成",
    "全部完成",
    "全部失败",
    "无任务可执行",
    "无可执行任务",
    "已停止",
    "已中止",
    "待命",
  ]);

  if (
    NON_RUNNING_STATUSES.has(currentStatus) ||
    currentStatus.startsWith("部分成功")
  ) {
    if (typeof multi_removeRunnerMarker === "function")
      multi_removeRunnerMarker(username);
    return;
  }

  const s = data.summary;
  if (s && typeof s.executable === "number" && s.executable <= 0) {
    const maybeRunning = [
      "登录中...",
      "分析任务",
      "运行",
      "等待",
      "排队登录...",
      "延迟",
    ];
    const isLikelyRunning = maybeRunning.some((k) => currentStatus.includes(k));
    if (!isLikelyRunning) {
      if (typeof multi_removeRunnerMarker === "function")
        multi_removeRunnerMarker(username);
    }
  }
}

function multi_updateRunnerPosition(username, lon, lat, name) {
  const color = resolveMultiAccountRunnerColor(username);
  const markerContent = `<div style="background-color: ${color};" class="text-xs font-bold whitespace-nowrap px-2 py-1 rounded-full shadow-lg text-white">${name}</div>`;
  if (getActiveMapProvider() !== "amap") {
    updateProviderRunnerMarker("multi-map-container", { lng: lon, lat }, {
      markerKey: `multi-map-container:${username}`,
      title: `${name} (${username})`,
      label: name,
      content: markerContent,
      anchor: "bottom-center",
      zIndex: 110,
      markerColor: color,
      markerKind: "label",
    });
    return;
  }
  if (!AMapInstance) return;
  if (!multiAccountMap) return;
  const pos = new AMapInstance.LngLat(lon, lat);
  if (multiAccountMarkers[username]) {
    multiAccountMarkers[username].setPosition(pos);
  } else {
    multiAccountMarkers[username] = new AMapInstance.Marker({
      position: pos,
      content: markerContent,
      anchor: "bottom-center",
      zIndex: 110,
      title: `${name} (${username})`,
    });
    multiAccountMap.add(multiAccountMarkers[username]);
  }
}

function resolveMultiAccountRunnerColor(username) {
  const markerKey = String(username ?? "");
  if (!Object.prototype.hasOwnProperty.call(multiAccountMarkerColors, markerKey)) {
    multiAccountMarkerColors[markerKey] = userColors[colorIndex++ % userColors.length];
  }
  return multiAccountMarkerColors[markerKey];
}

function multi_removeRunnerMarker(username) {
  const providerMarkerKey = `multi-map-container:${username}`;
  if (providerRunnerMarkers[providerMarkerKey]) {
    removeProviderOverlayFromMap("multi-map-container", providerRunnerMarkers[providerMarkerKey]);
    delete providerRunnerMarkers[providerMarkerKey];
  }
  const marker = multiAccountMarkers[username];
  if (marker && multiAccountMap) {
    multiAccountMap.remove(marker);
  }
  delete multiAccountMarkers[username];
}

function multi_resetMapView() {
  if (!multiAccountMap) return;
  const overlays = Object.values(multiAccountMarkers).filter((m) => m.getMap());
  if (overlays.length > 0) {
    multiAccountMap.setFitView(overlays, false, [80, 80, 80, 80]);
  } else {
    multiAccountMap.setZoomAndCenter(17, [113.390342, 22.527403]);
  }
}
