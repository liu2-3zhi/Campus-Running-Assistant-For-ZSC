// Legacy mobile initialization and session list UI extracted from main.js.
function initializeMobileUI() {
  console.log("[移动端UI] 初始化移动端UI功能 (重构版)");
  const loadingOverlayEl = document.getElementById("loading-overlay");
  if (loadingOverlayEl) loadingOverlayEl.classList.remove("hidden");

  function showMobileAuthForm(formToShow) {
    const loginTab = document.getElementById("mobile-auth-tab-login");
    const registerTab = document.getElementById("mobile-auth-tab-register");
    const loginForm = document.getElementById("mobile-login-form");
    const registerForm = document.getElementById("mobile-register-form");
    const tfaForm = document.getElementById("mobile-auth-2fa-form");

    if (loginForm) loginForm.classList.add("hidden");
    if (registerForm) registerForm.classList.add("hidden");
    if (tfaForm) tfaForm.classList.add("hidden");

    if (formToShow === "register") {
      if (registerForm) registerForm.classList.remove("hidden");
      if (loginTab)
        loginTab.className =
          "flex-1 py-3 font-semibold text-slate-400 border-b-2 border-transparent transition";
      if (registerTab)
        registerTab.className =
          "flex-1 py-3 font-semibold text-sky-600 border-b-2 border-sky-600 transition";

      loadCaptcha("register");
    } else {
      if (loginForm) loginForm.classList.remove("hidden");
      if (loginTab)
        loginTab.className =
          "flex-1 py-3 font-semibold text-sky-600 border-b-2 border-sky-600 transition";
      if (registerTab)
        registerTab.className =
          "flex-1 py-3 font-semibold text-slate-400 border-b-2 border-transparent transition";

      loadCaptcha("login");
    }

    showMobileMessage("", "clear");
  }

  const loginTabBtn = document.getElementById("mobile-auth-tab-login");
  const registerTabBtn = document.getElementById("mobile-auth-tab-register");
  if (loginTabBtn)
    loginTabBtn.addEventListener("click", () => showMobileAuthForm("login"));
  if (registerTabBtn)
    registerTabBtn.addEventListener("click", () =>
      showMobileAuthForm("register"),
    );

  const mobileUsernameBtn = document.getElementById(
    "mobile-login-username-btn",
  );
  const mobilePhoneBtn = document.getElementById("mobile-login-phone-btn");
  const mobileAuthInputContainer = document.getElementById(
    "mobile-username-container",
  );
  const mobileAuthLabel = document.getElementById("mobile-login-label");
  const mobileSwitchToSms = document.getElementById("mobile-switch-to-sms");

  if (
    mobileUsernameBtn &&
    mobilePhoneBtn &&
    mobileAuthInputContainer &&
    mobileAuthLabel &&
    mobileSwitchToSms
  ) {
    mobileUsernameBtn.addEventListener("click", function () {
      mobileUsernameBtn.className =
        "px-4 py-2 rounded-lg bg-sky-100 text-sky-700 font-semibold text-sm";
      mobilePhoneBtn.className =
        "px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm";

      const currentValue =
        mobileAuthInputContainer.querySelector("input").value;
      mobileAuthLabel.textContent = "用户名";
      mobileAuthInputContainer.innerHTML = `
            <input type="text" id="mobile-auth-username" class="w-full" placeholder="请输入用户名" autocomplete="username" value="${
              currentValue || ""
            }">
          `;
      mobileSwitchToSms.classList.add("hidden");
      document
        .getElementById("mobile-password-section")
        .classList.remove("hidden");
      document.getElementById("mobile-sms-section").classList.add("hidden");
    });

    mobilePhoneBtn.addEventListener("click", function () {
      mobilePhoneBtn.className =
        "px-4 py-2 rounded-lg bg-sky-100 text-sky-700 font-semibold text-sm";
      mobileUsernameBtn.className =
        "px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm";

      const currentValue =
        mobileAuthInputContainer.querySelector("input").value;
      mobileAuthLabel.textContent = "手机号";
      mobileAuthInputContainer.innerHTML = `
            <div class="phone-input-wrapper">
              <span class="phone-prefix">+86 </span>
              <input type="tel" id="mobile-auth-username" class="input-field" placeholder="请输入手机号" autocomplete="tel" inputmode="numeric" maxlength="11" pattern="[0-9]*" value="${
                currentValue || ""
              }">
            </div>
          `;
      mobileSwitchToSms.classList.remove("hidden");
    });
  }

  const mobileSwitchToSmsBtn = document.getElementById("mobile-switch-to-sms");
  const mobileSwitchToPassBtn = document.getElementById(
    "mobile-switch-to-password",
  );
  const mobilePassSection = document.getElementById("mobile-password-section");
  const mobileSmsSection = document.getElementById("mobile-sms-section");

  if (mobileSwitchToSmsBtn)
    mobileSwitchToSmsBtn.addEventListener("click", () => {
      if (mobilePassSection) mobilePassSection.classList.add("hidden");
      if (mobileSmsSection) mobileSmsSection.classList.remove("hidden");
    });
  if (mobileSwitchToPassBtn)
    mobileSwitchToPassBtn.addEventListener("click", () => {
      if (mobileSmsSection) mobileSmsSection.classList.add("hidden");
      if (mobilePassSection) mobilePassSection.classList.remove("hidden");
    });

  const mobileSendLoginCodeBtn = document.getElementById(
    "mobile-auth-send-login-code",
  );
  if (mobileSendLoginCodeBtn) {
    mobileSendLoginCodeBtn.addEventListener("click", async function () {
      const phone = document.getElementById("mobile-auth-username").value;
      if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
        // showModalAlert("请输入正确的手机号", "错误");
        Swal.fire({
          icon: "error",
          title: "手机号错误",
          text: "请输入正确的手机号",
        });
        return;
      }

      openCaptchaModal({
        phone: phone,
        button: mobileSendLoginCodeBtn,
        originalText: mobileSendLoginCodeBtn.textContent,
      });
    });
  }

  const mobileSendRegCodeBtn = document.getElementById(
    "mobile-reg-send-code-btn",
  );
  if (mobileSendRegCodeBtn) {
    mobileSendRegCodeBtn.addEventListener("click", async function () {
      const phone = document.getElementById("mobile-reg-phone").value;
      if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
        // showModalAlert("请输入正确的手机号", "错误");
        Swal.fire({
          icon: "error",
          title: "手机号错误",
          text: "请输入正确的手机号",
        });
        return;
      }

      openCaptchaModal({
        phone: phone,
        button: mobileSendRegCodeBtn,
        originalText: mobileSendRegCodeBtn.textContent,
      });
    });
  }

  refreshCaptcha("mobile-login");
  refreshCaptcha("mobile-register");

  const mobileLoginBtn = document.getElementById("mobile-login-btn");
  if (mobileLoginBtn)
    mobileLoginBtn.addEventListener("click", async () => {
      setButtonLoading("mobile-login-btn", true, "登录中...");

      try {
        document.getElementById("auth-username").value =
          document.getElementById("mobile-auth-username").value;
        document.getElementById("auth-password").value =
          document.getElementById("mobile-auth-password").value;
        document.getElementById("auth-sms-code").value =
          document.getElementById("mobile-auth-sms-code").value;
        document.getElementById("auth-login-captcha").value =
          document.getElementById("mobile-login-captcha").value;

        if (
          !document
            .getElementById("mobile-password-section")
            .classList.contains("hidden")
        ) {
          document
            .getElementById("auth-password-section")
            .classList.remove("hidden");
          document.getElementById("auth-sms-section").classList.add("hidden");
        } else {
          document
            .getElementById("auth-password-section")
            .classList.add("hidden");
          document
            .getElementById("auth-sms-section")
            .classList.remove("hidden");
        }

        const pcUsernameBtn = document.getElementById("auth-login-username-btn");
        const pcPhoneBtn = document.getElementById("auth-login-phone-btn");
        if (
          !document
            .getElementById("mobile-login-phone-btn")
            .classList.contains("text-slate-600")
        ) {
          if (pcPhoneBtn) {
            pcPhoneBtn.className =
              "px-4 py-2 rounded-lg bg-sky-100 text-sky-700 font-semibold text-sm";
          }
          if (pcUsernameBtn) {
            pcUsernameBtn.className =
              "px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm";
          }
        } else {
          if (pcUsernameBtn) {
            pcUsernameBtn.className =
              "px-4 py-2 rounded-lg bg-sky-100 text-sky-700 font-semibold text-sm";
          }
          if (pcPhoneBtn) {
            pcPhoneBtn.className =
              "px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm";
          }
        }

        await handleAuthLogin(true);

        const tfaForm = document.getElementById("auth-2fa-form");
        if (tfaForm && !tfaForm.classList.contains("hidden")) {
          document.getElementById("mobile-login-form").classList.add("hidden");
          document
            .getElementById("mobile-auth-2fa-form")
            .classList.remove("hidden");
          document.getElementById("mobile-2fa-code").value = "";
          document.getElementById("mobile-2fa-code").focus();
          showMobileMessage("密码验证成功，请输入验证码", "success");

          setButtonLoading("mobile-login-btn", false);
        } else {
          showButtonSuccess("mobile-login-btn", "登录成功", 800);
        }
      } catch (e) {
        console.error("代理[登录]失败:", e);
        showMobileMessage(e.message || "登录时发生内部错误", "error");
        showButtonError("mobile-login-btn", "登录失败");
      } finally {
        const tfaForm = document.getElementById("auth-2fa-form");
        if (!tfaForm || tfaForm.classList.contains("hidden")) {
          setButtonLoading("auth-login-btn", false);
          setButtonLoading("mobile-login-btn", false);
        }
      }
    });

  const mobileRegisterBtn = document.getElementById("mobile-register-btn");
  if (mobileRegisterBtn)
    mobileRegisterBtn.addEventListener("click", async () => {
      try {
        document.getElementById("auth-reg-username").value =
          document.getElementById("mobile-reg-username").value;
        document.getElementById("auth-reg-phone").value =
          document.getElementById("mobile-reg-phone").value;
        document.getElementById("auth-reg-sms-code").value =
          document.getElementById("mobile-reg-sms-code").value;
        document.getElementById("auth-reg-nickname").value =
          document.getElementById("mobile-reg-nickname").value;
        document.getElementById("auth-reg-password").value =
          document.getElementById("mobile-reg-password").value;
        document.getElementById("auth-reg-password-confirm").value =
          document.getElementById("mobile-reg-password-confirm").value;
        document.getElementById("auth-register-captcha").value =
          document.getElementById("mobile-register-captcha").value;
        await handleAuthRegister(true);
      } catch (e) {
        console.error("代理[注册]失败:", e);
        showMobileMessage("注册时发生内部错误", "error");
      }
    });

  const mobileGuestBtn = document.getElementById("mobile-guest-btn");
  if (mobileGuestBtn)
    mobileGuestBtn.addEventListener("click", async () => {
      try {
        await handleGuestLogin();
      } catch (e) {
        console.error("代理[游客登录]失败:", e);
        showMobileMessage("游客登录时发生内部错误", "error");
      }
    });

  const mobile2faBtn = document.getElementById("mobile-2fa-submit-btn");
  if (mobile2faBtn)
    mobile2faBtn.addEventListener("click", async () => {
      try {
        document.getElementById("auth-2fa-code").value =
          document.getElementById("mobile-2fa-code").value;
        await handle2FAVerify();
      } catch (e) {
        console.error("代理[2FA验证]失败:", e);
        showMobileMessage("2FA验证时发生内部错误", "error");
      }
    });

  const mobile2faBackBtn = document.getElementById("mobile-2fa-back-btn");
  if (mobile2faBackBtn)
    mobile2faBackBtn.addEventListener("click", () => {
      showMobileAuthForm("login");
      try {
        document.getElementById("auth-2fa-back-btn").click();
      } catch (e) {}
    });

  const mobileAvatarInput = document.getElementById("mobile-reg-avatar");
  if (mobileAvatarInput) {
    mobileAvatarInput.addEventListener("change", previewAvatarForRegistration);
  }

  const mobileGuestSection = document.getElementById(
    "mobile-guest-login-section",
  );
  if (mobileGuestSection) {
    // 修正：独立获取配置，不依赖桌面端 DOM 状态
    // 构建请求头，添加会话ID用于身份验证
    // X-Session-ID 是后端识别用户会话的关键header，几乎所有需要认证的API都需要
    const headers = {};
    if (sessionUUID) {
      headers["X-Session-ID"] = sessionUUID;
    }

    fetch("/auth/get_config", {
      headers: headers,
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success && data.allow_guest_login) {
          mobileGuestSection.classList.remove("hidden");
          console.log("[移动端UI] 游客登录已启用");
        } else {
          mobileGuestSection.classList.add("hidden");
          console.log("[移动端UI] 游客登录已禁用");
        }
      })
      .catch((e) => {
        console.error("[移动端UI] 获取游客配置失败:", e);
      });
  }

  const mobileSingleLoginBtn = document.getElementById(
    "mobile-single-login-btn",
  );
  if (mobileSingleLoginBtn) {
    mobileSingleLoginBtn.addEventListener("click", async function () {
      // 获取加载遮罩元素
      const mobileLoadingOverlay = document.getElementById(
        "mobile-loading-overlay",
      );

      try {
        const username = document
          .getElementById("mobile-username-entry")
          .value.trim();
        const password = document.getElementById("mobile-password-entry").value;

        if (!username || !password) {
          showMobileMessage("请输入用户名和密码", "error");
          return;
        }

        // 1. 设置按钮为加载状态
        mobileSingleLoginBtn.disabled = true;
        // 直接设置带图标的加载状态，无需保存 originalText，失败统一重置为 "登录"
        mobileSingleLoginBtn.innerHTML =
          '<span class="inline-block animate-spin mr-2">⏳</span>登录中...';

        // 2. 显示加载遮罩
        if (mobileLoadingOverlay) {
          mobileLoadingOverlay.classList.remove("hidden");
        }

        // 3. 同步输入到隐藏的 PC 端表单（onLogin 需要使用）
        document.getElementById("username-entry").value = username;
        document.getElementById("password-entry").value = password;

        logMessage_Info("[移动端UI] 触发单账号（学校）登录...");

        // 4. 执行登录请求
        let result_mobile_login = await onLogin();

        // 5. 处理结果
        if (result_mobile_login) {
          // --- 登录成功逻辑 ---
          const desktopMainApp = document.getElementById("main-app");
          if (desktopMainApp) {
            desktopMainApp.classList.add("hidden");
            desktopMainApp.classList.remove("grid");
          }

          document
            .getElementById("mobile-login-container")
            .classList.add("hidden");

          const mobileMainApp = document.getElementById("mobile-main-app");
          if (mobileMainApp) {
            mobileMainApp.classList.remove("hidden");
            logMessage_Info("[移动端UI] 已显示 mobile-main-app");
            switchMobileSinglePanel("mobile-control-panel");
          }

          updateMobileNavVisibility(true, "single");

          if (typeof mobileRefreshNotifications === "function") {
            await mobileRefreshNotifications((showalert = false));
          }

          // 成功后延迟隐藏遮罩，界面切换更平滑
          setTimeout(() => {
            if (mobileLoadingOverlay)
              mobileLoadingOverlay.classList.add("hidden");
            // 登录成功后通常跳转，这里可以重置按钮状态以备退出登录后使用
            mobileSingleLoginBtn.disabled = false;
            mobileSingleLoginBtn.textContent = "登录";
          }, 500);
        } else {
          // --- 登录失败逻辑 ---
          throw new Error("登录验证未通过"); // 抛出异常以转入 catch 统一处理重置
        }
      } catch (e) {
        // --- 异常/失败 统一处理逻辑 ---
        console.error("代理[学校登录]流程异常:", e);

        // 仅当不是主动抛出的逻辑控制错误时才显示通用错误提示
        if (e.message !== "登录验证未通过") {
          showMobileMessage("学校登录时发生内部错误: " + e.message, "error");
          logMessage_Error("代理[学校登录]失败:", e);
        }

        // 关键修复：确保按钮和遮罩状态被重置
        mobileSingleLoginBtn.disabled = false;
        mobileSingleLoginBtn.textContent = "登录"; // 显式重置为初始文本

        if (mobileLoadingOverlay) {
          mobileLoadingOverlay.classList.add("hidden");
        }
      }
    });
  }

  const mobileUserCombo = document.getElementById("mobile-user-combo");
  if (mobileUserCombo) {
    mobileUserCombo.addEventListener("change", onMobileUserChange);
  }

  const mobileUsernameEntry = document.getElementById("mobile-username-entry");
  if (mobileUsernameEntry && mobileUserCombo) {
    mobileUsernameEntry.addEventListener("input", async function () {
      const username = this.value.trim();
      const exists = [...mobileUserCombo.options].some(
        (o) => o.value === username,
      );
      mobileUserCombo.value = exists ? username : "";

      const mobilePasswordEntry = document.getElementById(
        "mobile-password-entry",
      );
      if (mobilePasswordEntry) mobilePasswordEntry.value = "";

      if (exists && username) {
        try {
          const data = await callPythonAPI("on_user_selected", username);
          if (data) {
            if (data.password && mobilePasswordEntry) {
              mobilePasswordEntry.value = data.password;
            }
            if (data.ua) {
              syncUAToMobile(data.ua);
            } else {
              syncUAToMobile("(新用户将在登录时自动生成)");
            }
          }
        } catch (error) {
          console.error("[Mobile] 获取用户数据失败:", error);
        }
      } else {
        syncUAToMobile("(未加载)");
      }
    });
  }

  const navButtons = document.querySelectorAll(".mobile-nav-btn");
  navButtons.forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      navButtons.forEach((b) => b.classList.remove("active"));
      this.classList.add("active");
      const navTarget = this.getAttribute("data-nav");
      console.log("[移动端UI] 切换导航到:", navTarget);
    });
  });

  const mobileMenuBtn = document.getElementById("mobile-menu-btn");
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", function () {
      console.log("[移动端UI] 菜单按钮点击 -> 切换侧边栏显示");
      // 修正：点击菜单按钮应该仅打开侧边栏，而不是跳转到管理面板
      toggleMobileSidebar();
    });
  }

  const mobileMultiAccountBtn = document.getElementById(
    "mobile-multi-account-btn",
  );
  if (mobileMultiAccountBtn) {
    mobileMultiAccountBtn.addEventListener("click", async function () {
      console.log("[移动端UI] 多账号模式按钮点击");

      stopBackgroundTaskPolling();
      try {
        await callPythonAPI_raw("/api/background_task/stop", "POST", null);
      } catch (_) {}
      onRunStopped();
      applyPendingMapProviderConfigIfAny();

      const result = await callPythonAPI("enter_multi_account_mode");
      if (!result.success) {
        // showModalAlert("进入多账号模式失败", "错误");
        Swal.fire({
          icon: "error",
          title: "进入多账号模式失败",
          text: "进入多账号模式失败",
        });
        return;
      }

      console.log("[移动端UI] 进入多账号模式成功");

      const mobileLoginContainer = document.getElementById(
        "mobile-login-container",
      );
      const mobileMultiApp = document.getElementById(
        "mobile-multi-account-app",
      );
      if (mobileLoginContainer) mobileLoginContainer.classList.add("hidden");
      if (mobileMultiApp) {
        mobileMultiApp.classList.remove("hidden");
        switchMobilePanel("mobile-multi-control-panel", "multi");
      }
      updateMobileNavVisibility(true, "multi");

      startMultiAccountAutoRefresh(500);
    });
  }

  const mobileRefreshSessionsBtn = document.getElementById(
    "mobile-refresh-sessions-btn",
  );
  if (mobileRefreshSessionsBtn) {
    mobileRefreshSessionsBtn.addEventListener("click", async function () {
      console.log("[移动端UI] 刷新会话列表");
      await loadMobileSessionsList();
    });
  }

  // ========================================
  // 为移动端上帝模式复选框绑定事件
  // ========================================
  const mobileMultiGodCheck = document.getElementById(
    "mobile-multi-god-mode-checkbox",
  );
  if (mobileMultiGodCheck) {
    mobileMultiGodCheck.addEventListener("change", function () {
      console.log("[移动端UI] 切换多账号面板上帝模式 (触发刷新)");
      loadMobileAdminSessionsList();
    });
  }

  const mobileSingleGodCheck = document.getElementById(
    "mobile-god-mode-checkbox-panel",
  );
  if (mobileSingleGodCheck) {
    mobileSingleGodCheck.addEventListener("change", function () {
      console.log("[移动端UI] 切换单账号面板上帝模式 (触发刷新)");
      loadMobileAdminSessionsList();
    });
  }
  // ========================================

  run_code_need_sessionuuid(() => {
    loadMobileUserCombo().catch((e) => {
      console.error("[Mobile UI] 移动端用户下拉框后台加载失败:", e);
    });
  });

  if (loadingOverlayEl) loadingOverlayEl.classList.add("hidden");

  console.log("[移动端UI] 移动端UI初始化完成");
}

async function loadMobileSessionsList() {
  const listEl = document.getElementById("mobile-sessions-list");
  const countEl = document.getElementById("mobile-session-count-display");

  // 游客模式支持：切换显示
  const createBtn = document.getElementById("mobile-create-session-btn");
  const guestMsg = document.getElementById("mobile-session-guest-msg");

  if (typeof currentUserIsGuest !== "undefined" && currentUserIsGuest) {
    if (createBtn) createBtn.classList.add("hidden");
    if (guestMsg) guestMsg.classList.remove("hidden");
  } else {
    if (createBtn) createBtn.classList.remove("hidden");
    if (guestMsg) guestMsg.classList.add("hidden");
  }

  if (!listEl) return;

  // 优化加载中动画
  listEl.innerHTML =
    '<div class="flex flex-col items-center justify-center py-10"><div class="w-8 h-8 border-4 border-sky-100 border-t-sky-500 rounded-full animate-spin mb-3"></div><span class="text-xs text-slate-400 font-medium">正在同步会话...</span></div>';

  try {
    const headers = { "X-Session-ID": getAuthenticatedSessionHeaderValue() };
    const response = await fetch("/auth/user/sessions", {
      headers: headers,
    });
    const result = await response.json();

    if (!result.success) {
      listEl.innerHTML = `<div class="mx-4 mt-4 p-3 bg-red-50 border border-red-100 rounded-xl text-center"><p class="text-red-500 text-xs font-medium">${result.message}</p></div>`;
      return;
    }

    const sessions = result.sessions || [];
    const validSessions = sessions.filter(
      (session) =>
        session.session_id &&
        session.session_id !== "null" &&
        session.session_id.trim() !== "",
    );

    // 更新计数器显示
    if (countEl) {
      if (typeof currentUserIsGuest !== "undefined" && currentUserIsGuest) {
        countEl.innerHTML = `<span class="text-blue-600 text-[10px] font-bold">会话: 1 / 游客限单会话</span>`;
      } else {
        const maxSessions = result.max_sessions || 1;
        const currentCount = validSessions.length;
        let countHtml = "";
        if (maxSessions === -1) {
          countHtml = `<span class="text-slate-600">${currentCount}</span> <span class="text-slate-400 text-[10px]">/ ∞</span>`;
        } else {
          const isFull = currentCount >= maxSessions;
          countHtml = `<span class="${
            isFull ? "text-red-500" : "text-slate-600"
          }">${currentCount}</span> <span class="text-slate-400 text-[10px]">/ ${maxSessions}</span>`;
        }
        countEl.innerHTML = countHtml;
      }
    }

    if (validSessions.length === 0) {
      listEl.innerHTML =
        '<div class="flex flex-col items-center justify-center py-12 opacity-60"><div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-3"><svg class="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg></div><p class="text-slate-500 text-sm font-medium">暂无会话</p></div>';
      return;
    }

    listEl.innerHTML = "";

    // 按时间排序，最新的在前面
    validSessions.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));

    validSessions.forEach((session) => {
      // 格式化时间，显示 年-月-日 时:分
      const dateObj = new Date(session.created_at * 1000);
      const dateStr = `${dateObj.getFullYear()}-${(dateObj.getMonth() + 1)
        .toString()
        .padStart(2, "0")}-${dateObj
        .getDate()
        .toString()
        .padStart(2, "0")} ${dateObj
        .getHours()
        .toString()
        .padStart(2, "0")}:${dateObj.getMinutes().toString().padStart(2, "0")}`;

      const isCurrent =
        session.is_current || session.session_id === sessionUUID;
      // 【修改点1】不再截断UUID，保存完整字符串
      const fullSessionId = session.session_id || "未知";
      const ownerUsername = String(session.username || currentAuthUsername || "");

      const isMulti = session.is_multi_account_mode;
      const loginStatus = session.login_success;

      // 提取用户名
      let displayTitle = "未登录会话";
      let displayIcon = "👤"; // 默认单人图标
      let iconBgClass = "bg-slate-100 text-slate-400";

      if (
        session.user_data &&
        session.user_data.username &&
        session.user_data.username !== "guest"
      ) {
        displayTitle = session.user_data.username;
        if (isMulti) {
          displayIcon = "👥"; // 多人图标
          iconBgClass = loginStatus
            ? "bg-purple-100 text-purple-600"
            : "bg-slate-100 text-slate-400";
        } else {
          displayIcon = "👤";
          iconBgClass = loginStatus
            ? "bg-green-100 text-green-600"
            : "bg-slate-100 text-slate-400";
        }
      } else if (isMulti) {
        displayTitle = "多账号控制台";
        displayIcon = "🎛️";
        iconBgClass = "bg-purple-50 text-purple-500";
      }

      // 构建标签 HTML
      let badgesHtml = "";
      if (isCurrent) {
        badgesHtml += `<span class="px-2 py-0.5 bg-sky-100 text-sky-600 text-[10px] font-bold rounded-full border border-sky-200 mr-1 shadow-sm">当前</span>`;
      }
      if (loginStatus) {
        badgesHtml += `<span class="px-2 py-0.5 bg-emerald-50 text-emerald-600 text-[10px] font-medium rounded-full border border-emerald-100">已登录</span>`;
      } else {
        badgesHtml += `<span class="px-2 py-0.5 bg-slate-50 text-slate-400 text-[10px] font-medium rounded-full border border-slate-100">未登录</span>`;
      }

      const itemDiv = document.createElement("div");

      // 【美化修改】更现代的卡片样式
      // 当前会话使用渐变边框和蓝色背景，未选中使用白色悬浮卡片
      const activeClass = isCurrent
        ? "border-blue-400/30 bg-gradient-to-br from-sky-50 via-white to-blue-50 shadow-md ring-1 ring-blue-200"
        : "border-slate-100 bg-white shadow-sm hover:border-slate-200 hover:shadow-md";

      itemDiv.className = `relative group rounded-2xl border p-4 mb-4 transition-all duration-300 active:scale-[0.98] touch-manipulation select-none ${activeClass}`;

      // 【美化修改】重构卡片内部结构：纯信息流布局
      itemDiv.innerHTML = `
                <div class="flex flex-col gap-3">
                    <div class="flex flex-col gap-1">
                        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider">会话 UUID</span>
                        <div class="font-mono text-xs font-bold text-slate-700 break-all select-all bg-slate-50 px-2 py-2 rounded-lg border border-slate-100 group-hover:border-blue-200 transition-colors">
                            ${fullSessionId}
                        </div>
                    </div>

                    <div class="flex items-center justify-between px-1">
                        <span class="text-xs text-slate-400 font-medium">创建时间</span>
                        <div class="flex items-center gap-1.5 text-xs text-slate-500 font-mono bg-white px-2 py-0.5 rounded-md border border-slate-100 shadow-sm">
                            <svg class="w-3 h-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            ${dateStr}
                        </div>
                    </div>

                    <div class="flex items-center justify-between px-1">
                        <span class="text-xs text-slate-400 font-medium">登录状态</span>
                        ${
                          loginStatus
                            ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-600 text-xs font-bold border border-emerald-100">
                                 <div class="w-1.5 h-1.5 rounded-full bg-emerald-500"></div> 已登录
                               </span>`
                            : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-500 text-xs font-bold border border-slate-200">
                                 <div class="w-1.5 h-1.5 rounded-full bg-slate-400"></div> 未登录
                               </span>`
                        }
                    </div>

                    ${
                      isCurrent
                        ? `
                    <div class="mt-1 pt-2 border-t border-slate-50 flex justify-end px-1">
                        <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gradient-to-r from-blue-500 to-sky-500 text-white text-[10px] font-bold shadow-md shadow-blue-200">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414-1.414z" clip-rule="evenodd"/></svg>
                            当前会话
                        </span>
                    </div>`
                        : ""
                    }
                </div>

                <div class="press-overlay absolute inset-0 bg-slate-900/80 backdrop-blur-[2px] rounded-2xl flex items-center justify-center opacity-0 transition-opacity duration-300 pointer-events-none z-20">
                     <div class="flex flex-col items-center text-white transform scale-90 transition-transform duration-300">
                        <div class="w-14 h-14 ${
                          isCurrent ? "bg-slate-500" : "bg-red-500"
                        } rounded-full flex items-center justify-center mb-2 shadow-lg ${
                          isCurrent
                            ? "shadow-slate-500/30"
                            : "shadow-red-500/30"
                        } animate-pulse">
                            ${
                              isCurrent
                                ? '<svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>'
                                : '<svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>'
                            }
                        </div>
                        <span class="font-bold text-base tracking-wide">${
                          isCurrent ? "当前会话无法删除" : "松手即删除"
                        }</span>
                     </div>
                </div>
            `;

      // 长按逻辑
      let timer = null;
      let isLongPress = false;
      let startX = 0,
        startY = 0;
      const overlay = itemDiv.querySelector(".press-overlay");
      const overlayContent = overlay.querySelector("div");

      const startPress = (e) => {
        // 当前会话不允许删除
        // if(isCurrent) return;

        isLongPress = false;
        const touch = e.touches ? e.touches[0] : e;
        startX = touch.clientX;
        startY = touch.clientY;

        timer = setTimeout(() => {
          isLongPress = true;
          if (navigator.vibrate) navigator.vibrate(50);
          if (overlay) {
            overlay.classList.remove("opacity-0");
            overlayContent.classList.remove("scale-90");
            overlayContent.classList.add("scale-100");
          }
        }, 500); // 500ms 长按触发
      };

      const movePress = (e) => {
        if (!timer) return;
        const touch = e.touches ? e.touches[0] : e;
        // 如果移动超过一定距离，取消长按
        if (
          Math.abs(touch.clientX - startX) > 10 ||
          Math.abs(touch.clientY - startY) > 10
        ) {
          clearTimeout(timer);
          timer = null;
          if (overlay) {
            overlay.classList.add("opacity-0");
            overlayContent.classList.add("scale-90");
            overlayContent.classList.remove("scale-100");
          }
        }
      };

      const endPress = (e) => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }

        if (overlay) {
          overlay.classList.add("opacity-0");
          overlayContent.classList.add("scale-90");
          overlayContent.classList.remove("scale-100");
        }

        if (isLongPress) {
          e.preventDefault();
          // 判断是否为当前会话
          if (isCurrent) {
            // showModalAlert(
            //   "当前会话处于活动状态，无法删除。\n如需删除，请先切换到其他会话。",
            //   "无法删除"
            // );
            Swal.fire({
              icon: "error",
              title: "无法删除",
              text: "当前会话处于活动状态，无法删除。\n如需删除，请先切换到其他会话。",
            });
          } else {
            // 触发删除确认
            showMobileConfirm(
              "删除会话",
              `确定要删除此会话（会话 UUID：${fullSessionId}）吗？\n`,
              () => deleteSessionFromPicker(session.session_id, false),
            );
          }
        }
        isLongPress = false;
      };

      // 双击/双指轻触切换会话
      let lastTapTime = 0;
      const handleDoubleTap = (e) => {
        if (isLongPress) return;
        const now = Date.now();
        if (now - lastTapTime < 350) {
          if (!isCurrent) {
            showMobileConfirm(
              "切换会话",
              `确定要切换到此会话吗？\nUUID: ${fullSessionId}`,
              () => {
                selectSessionFromPicker(session.session_id, ownerUsername);
              },
            );
          }
          lastTapTime = 0;
        } else {
          lastTapTime = now;
        }
      };

      itemDiv.addEventListener("touchstart", startPress, {
        passive: true,
      });
      itemDiv.addEventListener("touchmove", movePress, { passive: true });
      itemDiv.addEventListener("touchend", endPress);
      itemDiv.addEventListener("touchend", handleDoubleTap);
      itemDiv.addEventListener("mousedown", startPress); // 兼容鼠标
      itemDiv.addEventListener("mouseup", endPress);
      itemDiv.addEventListener("dblclick", () => {
        if (!isCurrent) {
          showMobileConfirm(
            "切换会话",
            `确定要切换到此会话吗？\nUUID: ${fullSessionId}`,
            () => {
              selectSessionFromPicker(session.session_id, ownerUsername);
            },
          );
        }
      });

      listEl.appendChild(itemDiv);
    });
  } catch (error) {
    console.error("[Mobile] 加载会话列表失败:", error);
    listEl.innerHTML =
      '<div class="flex flex-col items-center justify-center py-8 text-red-400 bg-red-50 rounded-xl border border-red-100 m-4"><svg class="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><p class="text-xs font-medium">加载失败，请检查网络</p></div>';
  }
}

async function loadMobileUserCombo() {
  if (
    run_code_not_need_sessionuuid(() => {
      console.warn("[Mobile UI] sessionUUID 无效，跳过加载用户下拉框");
      return false;
    }) === false
  ) {
    return;
  }
  const mobileUserCombo = document.getElementById("mobile-user-combo");
  if (!mobileUserCombo) {
    logMessage_Error("[Mobile] 找不到 mobile-user-combo 元素");
    return;
  }

  try {
    // 调用统一的初始数据加载函数，该函数会自动处理密码恢复任务列表更新
    const initialData = await loadInitialData();

    mobileUserCombo.innerHTML = '<option value="">(新用户)</option>';

    if (initialData.users && initialData.users.length > 0) {
      initialData.users.forEach((user) => {
        const option = document.createElement("option");
        option.value = option.textContent = user;
        mobileUserCombo.appendChild(option);
      });
    }

    if (initialData.lastUser) {
      mobileUserCombo.value = initialData.lastUser;
      await onMobileUserChange();
    }

    console.log("[Mobile] 用户下拉框已加载");
  } catch (error) {
    console.error("[Mobile] 加载用户列表失败:", error);
  }
}

async function onMobileUserChange() {
  const mobileUserCombo = document.getElementById("mobile-user-combo");
  const mobileUsernameEntry = document.getElementById("mobile-username-entry");
  const mobilePasswordEntry = document.getElementById("mobile-password-entry");

  if (!mobileUserCombo) return;

  const username = mobileUserCombo.value;

  if (mobileUsernameEntry) {
    mobileUsernameEntry.value = username;
  }

  if (mobilePasswordEntry) {
    mobilePasswordEntry.value = "";
  }

  if (username) {
    try {
      const data = await callPythonAPI("on_user_selected", username);
      if (data) {
        if (data.password && mobilePasswordEntry) {
          mobilePasswordEntry.value = data.password;
        }
        if (data.ua) {
          syncUAToMobile(data.ua);
        } else {
          syncUAToMobile("(新用户将在登录时自动生成)");
        }
      }
    } catch (error) {
      console.error("[Mobile] 获取用户数据失败:", error);
    }
  } else {
    syncUAToMobile("(未加载)");
  }
}

// ==================== 移动端侧边栏导航控制函数 ====================

function toggleMobileSidebar() {
  const backdrop = document.getElementById("mobile-sidebar-backdrop");
  const sidebarSingle = document.getElementById(
    "mobile-sidebar-single-account",
  );
  const sidebarMulti = document.getElementById("mobile-sidebar-multi-account");

  const multiAccountApp = document.getElementById("mobile-multi-account-app");
  const isMultiMode =
    multiAccountApp && !multiAccountApp.classList.contains("hidden");

  const activeSidebar = isMultiMode ? sidebarMulti : sidebarSingle;

  if (activeSidebar && activeSidebar.classList.contains("show")) {
    closeMobileSidebar();
  } else {
    if (sidebarSingle) {
      sidebarSingle.classList.remove("show");
      sidebarSingle.classList.add("hidden");
    }
    if (sidebarMulti) {
      sidebarMulti.classList.remove("show");
      sidebarMulti.classList.add("hidden");
    }

    if (backdrop) {
      backdrop.classList.add("show");
    }

    if (activeSidebar) {
      activeSidebar.classList.remove("hidden");
      setTimeout(() => {
        activeSidebar.classList.add("show");
      }, 10);
    }
  }
}

function closeMobileSidebar() {
  const backdrop = document.getElementById("mobile-sidebar-backdrop");
  const sidebarSingle = document.getElementById(
    "mobile-sidebar-single-account",
  );
  const sidebarMulti = document.getElementById("mobile-sidebar-multi-account");

  if (backdrop) {
    backdrop.classList.remove("show");
  }

  if (sidebarSingle) {
    sidebarSingle.classList.remove("show");
    setTimeout(() => {
      sidebarSingle.classList.add("hidden");
    }, 300);
  }

  if (sidebarMulti) {
    sidebarMulti.classList.remove("show");
    setTimeout(() => {
      sidebarMulti.classList.add("hidden");
    }, 300);
  }
}

function updateMobileNavVisibility(show, mode = "single") {
  const mobileMenuBtn = document.getElementById("mobile-menu-btn");
  const mobileHeader = document.getElementById("mobile-header");
  const sidebarSingle = document.getElementById(
    "mobile-sidebar-single-account",
  );
  const sidebarMulti = document.getElementById("mobile-sidebar-multi-account");

  if (show) {
    if (mobileMenuBtn) {
      mobileMenuBtn.style.display = "";
    }

    if (mobileHeader) {
      mobileHeader.classList.remove("hidden");
      mobileHeader.style.display = "";
    }

    if (mode === "single" && sidebarSingle) {
      sidebarSingle.classList.remove("hidden");
    }
    if (mode === "multi" && sidebarMulti) {
      sidebarMulti.classList.remove("hidden");
    }
  } else {
    if (mobileMenuBtn) {
      mobileMenuBtn.style.display = "none";
    }

    if (sidebarSingle) {
      sidebarSingle.classList.add("hidden");
      sidebarSingle.classList.remove("show");
    }
    if (sidebarMulti) {
      sidebarMulti.classList.add("hidden");
      sidebarMulti.classList.remove("show");
    }
  }

  const mobileBottomNavSingle = document.getElementById(
    "mobile-bottom-nav-single-account",
  );
  const mobileBottomNavMulti = document.getElementById(
    "mobile-bottom-nav-multi-account",
  );

  if (show) {
    if (mode === "single" && mobileBottomNavSingle) {
      mobileBottomNavSingle.classList.remove("hidden");
      mobileBottomNavSingle.style.display = "";
    }
    if (mode === "multi" && mobileBottomNavMulti) {
      mobileBottomNavMulti.classList.remove("hidden");
      mobileBottomNavMulti.style.display = "";
    }
  } else {
    if (mobileBottomNavSingle) {
      mobileBottomNavSingle.classList.add("hidden");
      mobileBottomNavSingle.style.display = "none";
    }
    if (mobileBottomNavMulti) {
      mobileBottomNavMulti.classList.add("hidden");
      mobileBottomNavMulti.style.display = "none";
    }
  }
}
