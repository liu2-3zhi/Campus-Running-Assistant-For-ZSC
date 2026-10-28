// Legacy application initialization, websocket, and map interaction helpers.

function showSessionMissingOverlay() {
  if (typeof stopReminderChecker === "function") stopReminderChecker();
  if (document.getElementById("logout-elsewhere-overlay")) return;

  const overlay = document.createElement("div");
  overlay.id = "logout-elsewhere-overlay";
  overlay.style.cssText = `
    position: fixed; inset: 0; background: rgba(0, 0, 0, 0.85);
    z-index: 20002; display: flex; align-items: center; justify-content: center;
  `;

  const content = document.createElement("div");
  content.style.cssText = `
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 40px; border-radius: 20px; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    max-width: 500px; width: 90%; text-align: center; color: white;
  `;
  const icon = document.createElement("div");
  icon.innerHTML = `
    <svg style="width: 80px; height: 80px; margin: 0 auto 20px;" fill="currentColor" viewBox="0 0 20 20">
      <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
    </svg>
  `;
  const title = document.createElement("h2");
  title.textContent = "会话不存在";
  title.style.cssText = "font-size: 24px; font-weight: bold; margin: 0 0 20px 0;";
  const text = document.createElement("p");
  text.textContent = "该会话已过期或不存在，请重新登录";
  text.style.cssText = "font-size: 16px; line-height: 1.6; margin: 0 0 30px 0; opacity: 0.95; white-space: pre-wrap;";
  const countdown = document.createElement("div");
  countdown.style.cssText = "font-size: 24px; font-weight: bold; margin: 0 0 30px 0;";
  const button = document.createElement("button");
  button.textContent = "返回登录";
  button.style.cssText = "background: white; color: #667eea; border: none; padding: 12px 30px; border-radius: 25px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s;";
  button.onmouseover = () => {
    button.style.transform = "scale(1.05)";
    button.style.boxShadow = "0 5px 15px rgba(255, 255, 255, 0.3)";
  };
  button.onmouseout = () => {
    button.style.transform = "scale(1)";
    button.style.boxShadow = "none";
  };

  let remainingSeconds = 10;
  countdown.textContent = `${remainingSeconds}秒后自动跳转`;
  const goToLogin = () => {
    clearInterval(countdownInterval);
    window.location.replace(buildLegacyUiPath("/"));
  };
  const countdownInterval = setInterval(() => {
    remainingSeconds--;
    countdown.textContent = `${remainingSeconds}秒后自动跳转`;
    if (remainingSeconds <= 0) goToLogin();
  }, 1000);
  overlay._clearCountdown = () => clearInterval(countdownInterval);
  button.onclick = goToLogin;

  content.appendChild(icon);
  content.appendChild(title);
  content.appendChild(text);
  content.appendChild(countdown);
  content.appendChild(button);
  overlay.appendChild(content);
  document.body.appendChild(overlay);
}

async function initializeApp() {
  const initializationContext = captureLegacyBusinessContext();
  if (window.__mapKeyRuntimeReady) {
    await window.__mapKeyRuntimeReady;
  }

  function ShowMobileLoadingOverlay() {
    const isMobile = detectMobileDevice();
    if (isMobile) {
      $("mobile-loading-overlay").classList.remove("hidden");
    }
  }

  function HiddenMobileLoadingOverlay() {
    $("mobile-loading-overlay").classList.add("hidden");
  }

  function ShowLoadingOverlay() {
    const isMobile = detectMobileDevice();
    if (!isMobile) {
      $("loading-overlay").classList.remove("hidden");
    }
  }

  function HiddenLoadingOverlay() {
    $("loading-overlay").classList.add("hidden");
  }

  ShowLoadingOverlay();
  ShowMobileLoadingOverlay();
  applyTheme(getCachedThemePreference());
  const cachedThemeStyle = getCachedThemeStyle();
  const initialUuidFromPath = resolveThemeRequestSessionUUID("", window.location.pathname);
  const shouldDeferInitialThemeConfigApply = !!initialUuidFromPath;
  setThemeStyle(cachedThemeStyle, false, false);
  await ensureThemeStylesLoaded(false, {
    applyThemeConfig: !shouldDeferInitialThemeConfigApply,
  });
  if (!shouldDeferInitialThemeConfigApply) {
    setThemeStyle(cachedThemeStyle, false);
  }

  try {
    function isValidUUID(uuid) {
      const uuidPattern =
        /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
      return uuidPattern.test(uuid);
    }
    function showMobileLoadingOverlay() {
      const mobileLoadingOverlay = document.getElementById(
        "mobile-loading-overlay",
      );
      if (mobileLoadingOverlay) {
        mobileLoadingOverlay.classList.remove("hidden");
        console.log("[加载遮罩] 显示移动端加载遮罩");
      }
    }
    function hideMobileLoadingOverlay() {
      const mobileLoadingOverlay = document.getElementById(
        "mobile-loading-overlay",
      );
      if (mobileLoadingOverlay) {
        mobileLoadingOverlay.classList.add("hidden");
        console.log("[加载遮罩] 隐藏移动端加载遮罩");
      }
    }
    function hideLoadingOverlays() {
      $("loading-overlay").classList.add("hidden");
      $("cdn-error-overlay").classList.add("hidden");
      hideMobileLoadingOverlay();
    }
    function showUserFriendlyError(title, message, isWarning = false) {
      const type = isWarning ? "warning" : "error";
      Swal.fire({
        title: title,
        text: message,
        icon: type,
        confirmButtonText: "确定",
      });
    }
    $("loading-overlay").classList.remove("hidden");
    if (isMobileMode) {
      showMobileLoadingOverlay();
    }
    const urlPath = window.location.pathname;
    const match = urlPath.match(
      /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i,
    );

    ShowLoadingOverlay();
    if (match) {
      sessionUUID = match[1];
      checkAdminReturnState();

      if (!isValidUUID(sessionUUID)) {
        hideLoadingOverlays();
        hideLoadingOverlays();
        logMessage_Error("无效的UUID格式:", sessionUUID);
        Swal.fire({
          title: "无效的会话",
          text: "UUID格式不正确\n将跳转到登录页面",
          icon: "warning",
          confirmButtonText: "确定",
        }).then(() => {
          logMessage_Info("用户确认无效UUID弹窗，正在跳转到登录页面...");
          redirectToLoginAfterSessionExpiry();
        });
        return;
      }
      $("loading-overlay").classList.remove("hidden");
      ShowLoadingOverlay();
      logMessage_Info("Web模式: 检测到有效UUID =", sessionUUID);
      let result = null;
      try {
        try {
          const response = await fetch("/auth/check_uuid_type", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ uuid: sessionUUID }),
          });

          result = await response.json();

          if (!result.success) {
            logMessage_Error("检查UUID失败:", result.message);
            hideLoadingOverlays();
            let message = "无法通过UUID判断会话列席\n将跳转到登录页面";
            if (result.message !== "") {
              message =
                "无法通过UUID判断会话列席\n" +
                result.message +
                "\n将跳转到登录页面";
            }

            Swal.fire({
              title: "无效的会话类型",
              text: message,
              icon: "warning",
              confirmButtonText: "确定",
            }).then(() => {
              logMessage_Info(
                "用户确认检查UUID失败弹窗，正在跳转到登录页面...",
              );
              redirectToLoginAfterSessionExpiry();
            });

            return;
          }

          applyThemeBackgroundAssignment(result.theme_background, { bound: true });
          themeBackgroundAuthStateResolved = true;
          if (currentThemeConfig && typeof currentThemeConfig === "object") {
            applyThemeGlobalEnvironmentVariables(currentThemeConfig);
          }
        } catch (e) {
          logMessage_Error("检查UUID请求失败:", e);
          throw e;
        }
        $("loading-overlay").classList.remove("hidden");
        try {
          if (result.uuid_type === "guest") {
            try {
              logMessage_Info("检测到游客UUID，直接恢复会话");
              hideLoadingOverlays();
              if (isMobileMode) {
                const mobileHeader = document.getElementById("mobile-header");
                const mobileBottomNavSingle = document.getElementById(
                  "mobile-bottom-nav-single-account",
                );
                if (mobileHeader) {
                  mobileHeader.classList.remove("hidden");
                  mobileHeader.style.display = "";
                }
                if (mobileBottomNavSingle) {
                  mobileBottomNavSingle.classList.remove("hidden");
                  mobileBottomNavSingle.style.display = "";
                }
              }
            } catch (e) {
              logMessage_Error("处理游客UUID失败:", e);
              throw e;
            }
          } else if (result.uuid_type === "system_account") {
            try {
              logMessage_Info(
                "检测到系统账号UUID，允许访问（后端将验证token）",
              );
              hideLoadingOverlays();
              if (isMobileMode) {
                const mobileHeader = document.getElementById("mobile-header");
                const mobileBottomNavSingle = document.getElementById(
                  "mobile-bottom-nav-single-account",
                );
                if (mobileHeader) {
                  mobileHeader.classList.remove("hidden");
                  mobileHeader.style.display = "";
                }
                if (mobileBottomNavSingle) {
                  mobileBottomNavSingle.classList.remove("hidden");
                  mobileBottomNavSingle.style.display = "";
                }
              }
            } catch (e) {
              logMessage_Error("处理系统账号UUID失败:", e);
              throw e;
            }
          } else {
            try {
              logMessage_Info("检测到未知UUID，准备弹窗提示后跳转到登录页面");

              const loginContainer = document.getElementById("login-container");
              const mainApp = document.getElementById("main-app");
              const multiApp = document.getElementById("multi-account-app");
              const authContainer = document.getElementById(
                "auth-login-container",
              );

              if (loginContainer) loginContainer.classList.add("hidden");
              if (mainApp) mainApp.classList.add("hidden");
              if (multiApp) multiApp.classList.add("hidden");

              if (authContainer) {
                authContainer.classList.remove("hidden");
                authContainer.classList.remove("h-full", "w-full");
                authContainer.classList.add(
                  "fixed",
                  "inset-0",
                  "flex",
                  "items-center",
                  "justify-center",
                );
              }

              const mobileAuthContainer = document.getElementById(
                "mobile-auth-container",
              );
              if (mobileAuthContainer) {
                mobileAuthContainer.classList.remove("hidden");
                mobileAuthContainer.classList.add("fixed", "inset-0");
              }

              const inputsToDisable = [
                "auth-username",
                "auth-password",
                "auth-reg-username",
                "auth-reg-password",
                "auth-reg-password-confirm",
              ];
              inputsToDisable.forEach((inputId) => {
                const inputElement = document.getElementById(inputId);
                if (inputElement) {
                  inputElement.disabled = true;
                }
              });

              const mobileInputsToDisable = [
                "mobile-auth-username",
                "mobile-auth-password",
                "mobile-reg-username",
                "mobile-reg-password",
                "mobile-reg-password-confirm",
              ];
              mobileInputsToDisable.forEach((inputId) => {
                const inputElement = document.getElementById(inputId);
                if (inputElement) {
                  inputElement.disabled = true;
                }
              });

              if (authContainer) authContainer.classList.remove("hidden");

              showSessionMissingOverlay();
              return;
            } catch (e) {
              logMessage_Error("处理未知UUID失败:", e);
              throw e;
            }
          }
        } catch (e) {
          logMessage_Error("处理UUID类型失败:", e);
          throw e;
        }
      } catch (e) {
        logMessage_Error("检查UUID类型失败:", e);
        hideLoadingOverlays();
        Swal.fire({
          title: "网络错误",
          text: "无法验证会话状态，请检查网络连接后重试",
          icon: "warning",
          confirmButtonText: "确定",
        }).then(() => {
          logMessage_Info(
            "用户确认检查UUID类型失败弹窗，正在跳转到登录页面...",
          );
          redirectToLoginAfterSessionExpiry();
        });
        return;
      }
    } else {
      logMessage_Info("Web模式: 未检测到UUID，显示认证登录页面");
      hideLoadingOverlays();
      HiddenMobileLoadingOverlay();
      if (isMobileMode) {
        console.log("[Mobile Init] 无UUID，显示移动端认证页面");
        clearLogoutElsewhereOverlay();
        $("mobile-auth-login-container").classList.remove("hidden");
        $("mobile-login-container").classList.add("hidden");
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.add("hidden");
      } else {
        showAuthLogin();
      }
      return;
    }

    $("loading-overlay").classList.remove("hidden");
    ShowMobileLoadingOverlay();
    const isAuthenticated = await checkAuthStatus();
    themeBackgroundAuthStateResolved = true;
    themeBackgroundAuthenticatedSession = !!isAuthenticated;
    if (!isAuthenticated) {
      hideLoadingOverlays();
      HiddenMobileLoadingOverlay();

      if (sessionUUID) {
        if (redirectToLoginAfterSessionExpiry()) return;
      }

      if (isMobileMode) {
        console.log("[Mobile Init] 未认证，显示移动端认证页面");
        clearLogoutElsewhereOverlay();
        $("mobile-auth-login-container").classList.remove("hidden");
        $("mobile-login-container").classList.add("hidden");
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.add("hidden");
      } else {
        console.log("[Desktop Init] 未认证，显示桌面端认证页面");
        showAuthLogin();
      }
      return;
    }
    $("loading-overlay").classList.remove("hidden");
    ShowMobileLoadingOverlay();
    appInitialized = true;

    if (sessionUUID) {
      connectWebSocket();
    }

    if (cdnErrorTimer) {
      clearTimeout(cdnErrorTimer);
      cdnErrorTimer = null;
    }

    logMessage_Info("应用初始化成功，CDN资源状态正常或可用替代方案");

    // 使用统一的加载函数获取初始数据，并自动更新管理员任务列表
    const initialData = await loadInitialData();
    syncMapProviderConfigFromInitialData(initialData);
    const initialDataFailureNotice = getInitialDataFailureNotice(initialData);
    if (initialDataFailureNotice) {
      hideLoadingOverlays();
      HiddenMobileLoadingOverlay();
      showUserFriendlyError(
        initialDataFailureNotice.title,
        initialDataFailureNotice.text,
        initialDataFailureNotice.icon === "warning",
      );
      return;
    }
    availableThemeStyles = Array.isArray(initialData?.theme_styles)
      ? initialData.theme_styles
      : [];
    currentThemeConfig =
      initialData?.theme_config && typeof initialData.theme_config === "object"
        ? initialData.theme_config
        : {};
    applyThemeGlobalEnvironmentVariables(currentThemeConfig);
    if (!availableThemeStyles.length) {
      await ensureThemeStylesLoaded();
    }
    renderThemeStyleButtons(
      document.getElementById("profile-theme-style-buttons"),
      pythonParams.theme_style || currentThemeStyle || "default",
    );
    renderThemeStyleButtons(
      document.getElementById("mobile-unified-theme-style-buttons"),
      pythonParams.theme_style || currentThemeStyle || "default",
      { mobile: true },
    );
    await syncThemeFromServer(initialData?.theme, initialData?.theme_style);

    currentUserIsGuest = initialData.is_guest || false;
    currentAuthUsername = getLegacyActorIdentity(initialData).auth_username || null;
    // updateMobileGuestVisibility();
    logMessage_Info(
      `initializeApp: currentUserIsGuest = ${currentUserIsGuest}, auth_username = ${currentAuthUsername}`,
    );

    const userCombo = $("user-combo");
    userCombo.innerHTML = '<option value="">(新用户)</option>';
    initialData.users.forEach((user) => {
      const option = document.createElement("option");
      option.value = option.textContent = user;
      userCombo.appendChild(option);
    });

    const multiConfigUserSelect = $("multi-config-user-select");
    const mobileMultiConfigUserSelect = $("mobile-multi-config-user-select");

    const populateUserSelect = (sel, users) => {
      if (!sel) return;
      sel.innerHTML = '<option value="">(新用户/手动输入)</option>';
      users.forEach((user) => {
        const option = document.createElement("option");
        option.value = option.textContent = user;
        option.title = user;
        sel.appendChild(option);
      });
    };

    if (multiConfigUserSelect)
      populateUserSelect(multiConfigUserSelect, initialData.users);
    if (mobileMultiConfigUserSelect)
      populateUserSelect(mobileMultiConfigUserSelect, initialData.users);

    logMessage_Info(
      `[初始化] multi-config-user-select 已更新，用户数: ${initialData.users.length}`,
    );

    createParamInputs($("params-container"), "param", onParamChange);
    if (initialData.lastUser) userCombo.value = initialData.lastUser;
    await onUserChange();

    const hasSchoolLogin = initialData.isLoggedIn && initialData.userInfo;
    const hasSystemAuth = initialData.is_authenticated && !initialData.is_guest;
    const isGuestMode = initialData.is_authenticated && initialData.is_guest;
    let sessionModeInfo = null;
    try {
      sessionModeInfo = await callPythonAPI("get_session_mode_info");
    } catch (e) {
      logMessage_Error("获取会话模式信息失败:", e);
      hideLoadingOverlays();
      Swal.fire({
        title: "网络错误",
        text: "获取会话模式信息失败，请检查网络连接后重试",
        icon: "warning",
        confirmButtonText: "确定",
      }).then(() => {
        logMessage_Info(
          "用户确认获取会话模式信息失败弹窗，正在跳转到登录页面...",
        );
        window.location.href = buildLegacyUiPath("/");
      });
      return;
    }

    const hasLoadedTasks = sessionModeInfo && sessionModeInfo.has_tasks;

    $("loading-overlay").classList.remove("hidden");
    ShowMobileLoadingOverlay();

    if (!isCurrentLegacyBusinessContext(initializationContext)) return;
    resetUI();
    const modeContext = captureLegacyBusinessContext();
    applyLegacyBusinessMode(sessionModeInfo, modeContext) || applyLegacyBusinessMode(initialData, modeContext);
    if (sessionModeInfo && sessionModeInfo.is_multi_account_mode) {
      logMessage_Info("检测到会话之前处于多账号模式，正在恢复...");
      currentUserData.group = initialData.auth_group || "user";
      try {
        const result = await callPythonAPI("enter_multi_account_mode");
        if (!result.success) {
          logMessage_Error("无法进入多账号模式，返回登录界面");
          return;
        }
        if (!sessionModeInfo.global_params && result.params) {
          pythonParams = result.params;
        }
      } catch (e) {
        logMessage_Error("调用 enter_multi_account_mode 失败:", e);
        return;
      }

      hideLoadingOverlays();
      HiddenMobileLoadingOverlay();
      try {
        await ensureActiveMapProviderRuntimeIfNeeded("多账号模式恢复");
      } catch (e) {
        logMessage_Error("地图加载失败（多账号模式恢复）", e);
      }
      $("loading-overlay").classList.remove("hidden");
      ShowMobileLoadingOverlay();
      if (isMobileMode) {
        const mobileMultiApp = document.getElementById(
          "mobile-multi-account-app",
        );
        const mobileLoginContainer = document.getElementById(
          "mobile-login-container",
        );
        const mobileAuthContainer = document.getElementById(
          "mobile-auth-login-container",
        );
        if (mobileMultiApp) {
          mobileMultiApp.classList.remove("hidden");
          console.log("[会话恢复] 移动端：显示 mobile-multi-account-app");
        }
        if (mobileLoginContainer) mobileLoginContainer.classList.add("hidden");
        if (mobileAuthContainer) mobileAuthContainer.classList.add("hidden");
        updateMobileNavVisibility(true, "multi");
        switchMobilePanel("mobile-multi-control-panel", "multi");
        console.log("[会话恢复] 移动端：已默认激活 mobile-multi-control-panel");
        $("multi-account-app").classList.add("hidden");
        $("main-app").classList.add("hidden");
      } else {
        $("multi-account-app").classList.remove("hidden");
        $("multi-account-app").classList.add("grid");
        $("main-app").classList.add("hidden");
        console.log("[会话恢复] 桌面端：显示 multi-account-app");
      }
      if (!multiAccountMap && getActiveMapProvider() === "amap" && AMapInstance) {
        try {
          multiAccountMap = new AMapInstance.Map("multi-map-container", {
            viewMode: "3D",
            pitch: 55,
            rotation: 0,
            zoom: 17,
            center: [113.390342, 22.527403],
            renderOptions: {
              willReadFrequently: true,
            },
          });
          const ctrlBar = new AMapInstance.ControlBar({
            position: { left: "12px", top: "12px" },
            showZoomBar: false,
            showControlButton: true,
          });
          multiAccountMap.addControl(ctrlBar);
          try {
            const buildings = new AMapInstance.BuildingLayer();
            buildings.setMap(multiAccountMap);
          } catch (e) {
            logMessage_Warning("BuildingLayer not available (multi):", e);
          }

          multiAccountMap.on("zoomchange", () => {
            if (!multiAccountMap) return;
            const z = multiAccountMap.getZoom();
            const zoomLevelEl = $("multi-zoom-level");
            if (zoomLevelEl) zoomLevelEl.textContent = String(z.toFixed(1));
          });
          bindTaskMapSdkInteractionTracking("multi-map-container", multiAccountMap);
          bindTaskMapUserInteractionTracking(
            "multi-map-container",
            multiAccountMap.getContainer && multiAccountMap.getContainer(),
          );
          bindTaskMapUserInteractionTracking(
            "multi-map-container",
            document.getElementById("multi-map-container"),
          );
          if (window.multiMapCleanup) window.multiMapCleanup();
          window.multiMapCleanup = enhanceMapInteraction(multiAccountMap);

          multiAccountMap.setStatus({
            doubleClickZoom: true,
            dragEnable: true,
            scrollWheel: true,
            keyboardEnable: true,
          });
          ensureMultiControls();
          removeAmapLicenseOverlay("multi-map-container");
        } catch (e) {
          logMessage_Error("初始化多账号地图失败:", e);
        }
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.add("hidden");
      } else if (getActiveMapProvider() !== "amap") {
        initProviderMap("multi-map-container", true);
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.add("hidden");
      }
      try {
        const configUsers = await callPythonAPI("multi_get_all_config_users");
        const select = $("multi-config-user-select");
        select.innerHTML = '<option value="">(新用户/手动输入)</option>';
        configUsers.users.forEach((u) => {
          const opt = document.createElement("option");
          opt.value = opt.textContent = u;
          select.appendChild(opt);
        });
      } catch (e) {
        logMessage_Error("加载配置用户列表失败:", e);
      }
      if (sessionModeInfo.global_params) {
        pythonParams = sessionModeInfo.global_params;
      }
      try {
        const container = $("multi-global-params-container");
        container.innerHTML = "";
        createParamInputs(container, "multi-param", onGlobalParamChange);
        updateParamInputs(container, "multi-param", pythonParams);
      } catch (e) {
        logMessage_Error("初始化全局参数UI失败:", e);
      }
      try {
        bindImmediateRefreshForUserSelects();
        updateMultiGlobalButtons(true, true);
        await callPythonAPI(
          "set_multi_run_only_incomplete",
          document.getElementById("multi-run-only-incomplete-check").checked,
        );
      } catch (e) {
        logMessage_Error("绑定多账号UI事件失败:", e);
      }
      try {
        // 使用loadInitialData替代直接调用API
        const initialData = await loadInitialData({ force: true });
        syncMapProviderConfigFromInitialData(initialData);
        if (initialData && initialData.accounts) {
          renderMultiAccountList(initialData.accounts);
          logMessage_Info(
            `已恢复多账号模式，当前有 ${initialData.accounts.length} 个账号`,
          );
        } else {
          logMessage_Info(`已恢复多账号模式，当前有 0 个账号`);
        }
      } catch (e) {
        logMessage_Error("恢复账号列表失败:", e);
        logMessage_Info(
          `已恢复多账号模式，当前有 ${
            sessionModeInfo.multi_account_count || 0
          } 个账号（列表加载失败）`,
        );
      }
      setTimeout(async () => {
        try {
          await initializeInlineAdminPanel();
        } catch (e) {
          logMessage_Error("初始化内嵌管理面板失败:", e);
        }
      }, 100);

      const base = pythonParams.theme_base_color || "#7dd3fc";
      setBaseColor(base, base, false); // 传入 false，不触发 API 保存

      // 显式恢复主题样式
      if (pythonParams.theme_style) {
        setThemeStyle(pythonParams.theme_style, false);
      }

      startMultiAccountAutoRefresh(500);

      hideLoadingOverlays();
      HiddenMobileLoadingOverlay();
    } else if (hasSchoolLogin || hasLoadedTasks) {
      currentUserData =
        initialData.userInfo ||
        (sessionModeInfo && sessionModeInfo.user_data) ||
        {};
      currentUserData.group = initialData.auth_group || "guest";

      if (initialData.device_ua) {
        currentSessionUA = initialData.device_ua;
        logMessage_Info(
          `[会话恢复] 成功恢复 User-Agent: ${currentSessionUA.substring(
            0,
            50,
          )}...`,
        );
      } else {
        logMessage_Warning("[会话恢复] 未能从 initialData 中恢复 User-Agent。");
        currentSessionUA = "NULL (Restored)";
      }

      hideLoadingOverlays();
      try {
        await ensureActiveMapProviderRuntimeIfNeeded("会话恢复");
      } catch (e) {
        logMessage_Error("地图加载失败（会话恢复）", e);
      }
      $("loading-overlay").classList.remove("hidden");

      syncUserListPollingBySocketState();

      showMainApp();
      const name = currentUserData.name || "离线模式";
      $("user-name-label").textContent = `姓名: ${name}`;
      $("user-id-label").textContent = `学号: ${
        currentUserData.student_id || "未登录"
      }`;
      updateDashboard();
      await refreshTasks();
      let isTaskRestored = false;
      try {
        isTaskRestored = await checkBackgroundTaskOnLoad();
      } catch (err) {
        logMessage_Warning("检查后台任务失败:", err);
      }
      const base = pythonParams.theme_base_color || "#7dd3fc";
      setBaseColor(base, base, false); // 传入 false，不触发 API 保存
      setTimeout(async () => {
        try {
          await initializeInlineAdminPanel();
        } catch (e) {
          logMessage_Error("初始化内嵌管理面板失败:", e);
        }
      }, 100);
      const adminBtn = $("show-admin-panel");
      if (adminBtn) adminBtn.classList.remove("hidden");
      hideLoadingOverlays();
      await fetchNotifications();
    } else if (hasSystemAuth || isGuestMode) {
      currentUserData.group = initialData.auth_group || "guest";
      logMessage_Info(
        `[Auth Restore] 恢复系统权限组: ${currentUserData.group}`,
      );

      $("loading-overlay").classList.remove("hidden");

      if (isMobileMode) {
        console.log("[Mobile Init] 已认证，显示移动端学校账号登录/会话管理");
        $("mobile-auth-login-container").classList.add("hidden");
        $("mobile-login-container").classList.remove("hidden");
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.add("hidden");
        updateMobileNavVisibility(false);
        setTimeout(async () => {
          try {
            await loadMobileSessionsList();
          } catch (e) {
            console.error("[Mobile Init] 加载移动端数据失败:", e);
          }
        }, 100);
      } else {
        console.log("[Desktop Init] 已认证，显示桌面端学校账号登录/会话管理");
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.remove("hidden");
      }
      await onUserChange();
      setTimeout(async () => {
        try {
          await initializeInlineAdminPanel();
        } catch (e) {
          logMessage_Error("初始化内嵌管理面板失败:", e);
        }
      }, 100);
      try {
        await ensureActiveMapProviderRuntimeIfNeeded("系统账号恢复");
      } catch (e) {
        logMessage_Error("地图加载失败（系统账号恢复）", e);
      }

      hideLoadingOverlays();
      if (isGuestMode) {
        logMessage_Info("[游客模式] 部分功能受限，请保存当前地址以便恢复会话");
        const guestToast = $("guest-warning-toast");
        const guestOverlay = $("guest_warning_overlay");
        if (guestToast) {
          if (guestOverlay) {
            guestOverlay.classList.remove("hidden");
          }
          guestToast.classList.remove("hidden");
        }
      }

      $("loading-overlay").classList.remove("hidden");

      const adminBtnLogin = $("show-admin-panel-login");
      if (adminBtnLogin) {
        adminBtnLogin.classList.remove("hidden");
      }
      const adminBtnMulti = $("show-admin-panel-multi");
      if (adminBtnMulti) adminBtnMulti.classList.remove("hidden");

      hideLoadingOverlays();
    } else {
      try {
        await ensureActiveMapProviderRuntimeIfNeeded("ready 阶段");
      } catch (e) {
        logMessage_Error("地图加载失败（ready 阶段）", e);
      }
      hideLoadingOverlays();
    }

    if (pythonParams.theme_style) {
      setThemeStyle(pythonParams.theme_style, false); // 传入 false
    }
    await refreshUserList();

    const loadingOverlay = $("loading-overlay");
    loadingOverlay.style.opacity = "0";
    setTimeout(() => {
      loadingOverlay.style.display = "none";
    }, 500);
    bindImmediateRefreshForUserSelects();

    const attEnabled = $("param-auto_attendance_enabled");
    const attStopAfterSuccess = $("param-auto_attendance_stop_after_success");
    const attSuccessLimit = $("param-auto_attendance_success_limit");
    const attRefresh = $("param-auto_attendance_refresh_s");
    const attRadius = $("param-attendance_user_radius_m");
    if (attEnabled) attEnabled.addEventListener("change", onParamChange);
    if (attStopAfterSuccess)
      attStopAfterSuccess.addEventListener("change", onParamChange);
    if (attSuccessLimit)
      attSuccessLimit.addEventListener("change", onParamChange);
    if (attRefresh) attRefresh.addEventListener("change", onParamChange);
    if (attRadius) attRadius.addEventListener("change", onParamChange);

    $("confirm-amap-key-btn").addEventListener("click", onConfirmAmapKey);
    if (sessionUUID) {
      startSessionValidityCheck();
      startReminderChecker(sessionUUID);
    }
    if (isMobileMode) {
      setTimeout(() => {
        restoreMobileTaskState();
        hideMobileLoadingOverlay();
      }, 1000);
    }

    // 新增：检查是否显示返回管理员按钮
    checkAdminReturnState();
  } catch (err) {
    hideLoadingOverlays();
    // showModalAlert("服务器无法连接，请检查网络或稍后重试。", "网络错误");
    Swal.fire({
      title: "网络错误",
      text: "服务器无法连接，请检查网络或稍后重试。",
      icon: "warning",
    });
  }
}
async function restoreMobileTaskState() {
  const request = ++backgroundTaskStatusRequest;
  const requestSession = sessionUUID;
  try {
    logMessage_Info("[移动端状态恢复] 开始检查后端任务状态...");

    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    if (request !== backgroundTaskStatusRequest || requestSession !== sessionUUID) return;

    if (statusRes.success && statusRes.task_status) {
      const status = statusRes.task_status;
      if (!acceptLegacyRunnerExecution(status, true)) return;
      if (status.status === "running" || status.status === "paused") {
        logMessage_Info("[移动端状态恢复] 检测到后端任务正在执行，恢复状态...");
        singleRunProgressVisualActive = true;
        const global_task_index = getLegacyActiveTaskIndex(status);
        if (global_task_index != null) {
          selectedTaskIndex = global_task_index;
          logMessage_Info(
            `[移动端状态恢复] 恢复任务索引: ${selectedTaskIndex}`,
          );

          if (currentTasks && currentTasks[selectedTaskIndex]) {
            if (!(await forceLoadTaskDataForPolling(selectedTaskIndex, status))) return;
            if (request !== backgroundTaskStatusRequest || requestSession !== sessionUUID) return;
          }
        }

        if (status.status === "running") {
          singleRunProgressVisualActive = true;
          mobileTaskRunning = true;
          mobileTaskPaused = false;
          updateMobileTaskUI("运行中", "任务执行中...");
          logMessage_Info("[移动端状态恢复] UI状态设置为运行中");
        } else if (status.status === "paused") {
          mobileTaskRunning = true;
          mobileTaskPaused = true;
          updateMobileTaskUI("已暂停", "任务已暂停");
          logMessage_Info("[移动端状态恢复] UI状态设置为已暂停");
        }

        startBackgroundTaskPolling();
        logMessage_Info("[移动端状态恢复] 已启动后台任务轮询");
      } else {
        logMessage_Info("[移动端状态恢复] 后端无正在执行的任务");
      }
    }
  } catch (error) {
    logMessage_Error("[移动端状态恢复] 恢复状态失败:", error);
  }
}

let socket = null;
let wsHeartbeatTimer = null;

function startWsHeartbeat() {
  stopWsHeartbeat();
  wsHeartbeatTimer = setInterval(() => {
    if (socket && socket.connected) {
      socket.emit("heartbeat", { ts: Date.now() });
    }
  }, 20000);
}

function stopWsHeartbeat() {
  if (wsHeartbeatTimer) {
    clearInterval(wsHeartbeatTimer);
    wsHeartbeatTimer = null;
  }
}

function connectWebSocket() {
  if (socket && socket.connected) {
    logMessage_Info("WebSocket 已连接.");
    return;
  }

  if (!sessionUUID) {
    logMessage_Warning("无法连接 WebSocket：缺少 sessionUUID。");
    return;
  }

  logMessage_Info("尝试连接 WebSocket...");
  socket = io({
    autoConnect: false,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 30000,
    reconnectionAttempts: Infinity,
    pingTimeout: 60000,
    pingInterval: 25000,
  });
  socket.connect();

  socket.on("connect", () => {
    verificationCodesSocketHealthy = true;
    stopVerificationCodesPollingFallback();
    syncUserListPollingBySocketState();
    syncMultiAccountAutoRefreshBySocketState();
    logMessage_Info("WebSocket 连接成功。SID:", socket.id);
    socket.emit("join", { session_id: sessionUUID, admin_origin_session_id: getAdminViewOriginSessionUUID(sessionUUID) });
    startWsHeartbeat();
    refreshUserList();
  });

  socket.on("disconnect", (reason) => {
    verificationCodesSocketHealthy = false;
    stopWsHeartbeat();
    syncVerificationCodesPollingByModalState();
    syncUserListPollingBySocketState();
    syncMultiAccountAutoRefreshBySocketState();
    logMessage_Info("WebSocket 连接已断开:", reason);
    logMessage_Info("[System] WebSocket 连接已断开，尝试重连...");
  });

  socket.on("connect_error", (error) => {
    verificationCodesSocketHealthy = false;
    syncVerificationCodesPollingByModalState();
    syncUserListPollingBySocketState();
    syncMultiAccountAutoRefreshBySocketState();
    if (!isInNetworkErrorState) {
      logMessage_Error("WebSocket 连接错误:", error);
      logMessage_Info("[System-Error] WebSocket 连接失败");
    }
  });

  socket.on("heartbeat_ack", () => {});

  socket.on("log_message", (data) => {
    if (data && data.msg) {
      displayRoutePlanningNotification(data);
    }
  });
  // ===============================================
  // === 监听后端推送的UI更新事件 ===
  // ===============================================
  socket.on("multi_status_update", (data) => {
    if (data && data.username && data.data) {
      markMultiAccountRealtimeUpdate();
      logMessage_Debug(`[Socket] 收到 ${data.username} 状态更新`);
      multi_updateAccountStatus(data.username, data.data);
    }
  });

  socket.on("accounts_updated", (data) => {
    if (data && data.accounts) {
      markMultiAccountRealtimeUpdate();
      logMessage(
        `[Socket] 收到账号列表更新，共 ${data.accounts.length} 个账号`,
        "INFO",
        "Socket",
      );
      onAccountsUpdated(data.accounts);
    }
  });

  socket.on("multi_global_buttons_update", (data) => {
    if (data) {
      logMessage_Debug(`[Socket] 收到全局按钮状态更新`);
      updateMultiGlobalButtons(data.start_disabled, data.stop_disabled);
      const exitBtn = document.getElementById("exit-multi-mode-btn");
      if (exitBtn) {
        exitBtn.disabled = !!data.exit_disabled;
      }
    }
  });

  socket.on("multi_position_update", (data) => {
    if (
      data &&
      data.username &&
      typeof data.lon === "number" &&
      typeof data.lat === "number"
    ) {
      markMultiAccountRealtimeUpdate();
      multi_updateRunnerPosition(
        data.username,
        data.lon,
        data.lat,
        data.name || data.username,
      );
    }
  });

  socket.on("runner_execution_started", (data) => {
    acceptLegacyRunnerExecution(data, true);
  });

  socket.on("runner_position_update_new", (data) => {
    logMessage_Debug("[Socket] 收到 runner_position_update 事件");
    if (data && acceptLegacyRunnerExecution(data)) {
      if (
        data.task_index !== undefined &&
        data.task_index !== selectedTaskIndex
      ) {
        logMessage_Info(`[Socket] 任务切换: 正在执行任务 #${data.task_index}`);
        selectedTaskIndex = data.task_index;

        renderTaskList();
      }

      if (data.elapsed_time != null) runAccumulatedMs = Math.max(0, Number(data.elapsed_time) * 1000);
      updateRunnerPosition(
        data.lon,
        data.lat,
        data.distance,
        data.target_sequence,
        data.elapsed_time != null ? 0 : data.duration,
        data.center_now,
        data.point_index,
      );
      logMessage_Debug(
        `[Socket] 收到当前位置更新: lon=${data.lon}, lat=${data.lat}`,
      );
    }
  });

  socket.on("task_completed", (data) => {
    if (data && acceptLegacyRunnerExecution(data) && typeof data.task_index !== "undefined") {
      onTaskCompleted(data.task_index);
    }
  });

  socket.on("run_stopped", (data) => {
    if (data?.execution_id && !acceptLegacyRunnerExecution(data)) return;
    onRunStopped();
  });
  socket.on("onNotificationsUpdated", (data) => {
    logMessage("收到后台推送的通知更新", "INFO", "Socket");
    if (data && data.success) {
      onNotificationsUpdated(data);
    }
  });

  socket.on("auto_attendance_updated", (data) => {
    if (!data || data.enabled !== false) return;
    if (typeof pythonParams !== "undefined") {
      pythonParams.auto_attendance_enabled = false;
    }
    [
      "param-auto_attendance_enabled",
      "mobile-param-auto_attendance_enabled",
      "mobile-multi-auto_attendance_enabled",
    ].forEach((id) => {
      const checkbox = $(id);
      if (checkbox) checkbox.checked = false;
    });
    logMessage_Info("自动签到已完成设定次数，已自动关闭");
  });

  socket.on("verification_codes_updated", () => {
    logMessage_Info("[Socket] 收到验证码列表更新推送");
    refreshOpenVerificationCodeModals();
  });
}

function enhanceMapInteraction(mapInstance) {
  if (!mapInstance) return () => {};
  const container = mapInstance.getContainer();
  if (!container) return () => {};
  const handlers = [];

  const addManagedListener = (element, type, listener, options) => {
    element.addEventListener(type, listener, options);
    handlers.push({ element, type, listener, options });
  };

  const wheelHandler = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!mapInstance) return;
    if (e.deltaY < 0) mapInstance.zoomIn();
    else mapInstance.zoomOut();
    const containerId = container.id || "map-container";
    scheduleTaskMapAutoResetAfterUserInteraction(containerId);
  };
  addManagedListener(container, "wheel", wheelHandler, {
    passive: false,
  });

  const contextMenuHandler = (e) => e.preventDefault();
  addManagedListener(container, "contextmenu", contextMenuHandler);

  const DRAG_SAME_DIRECTION = true;
  let rmbLongPressTimer = null,
    mmbLongPressTimer = null,
    rmbDragging = false,
    mmbDragging = false,
    lastClientX = 0,
    lastClientY = 0;

  function doPanBy(mouseX, mouseY) {
    if (!mapInstance) return;
    const dx = mouseX - lastClientX;
    const dy = mouseY - lastClientY;
    if (dx !== 0 || dy !== 0) {
      const panDx = DRAG_SAME_DIRECTION ? dx : -dx;
      const panDy = DRAG_SAME_DIRECTION ? dy : -dy;
      mapInstance.panBy(panDx, panDy);
      const containerId = container.id || "map-container";
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
      lastClientX = mouseX;
      lastClientY = mouseY;
    }
  }

  const mouseDownHandler = (e) => {
    if (e.button === 0) return;
    lastClientX = e.clientX;
    lastClientY = e.clientY;
    if (e.button === 1) {
      e.preventDefault();
      e.stopPropagation();
      mmbLongPressTimer = setTimeout(() => {
        mmbDragging = true;
      }, 0);
    }
    if (e.button === 2) {
      e.preventDefault();
      e.stopPropagation();
      rmbLongPressTimer = setTimeout(() => {
        rmbDragging = true;
      }, 0);
    }
  };
  addManagedListener(container, "mousedown", mouseDownHandler);

  const mouseMoveHandler = (e) => {
    if (rmbDragging || mmbDragging) {
      e.preventDefault();
      e.stopPropagation();
      doPanBy(e.clientX, e.clientY);
    }
  };
  addManagedListener(container, "mousemove", mouseMoveHandler);

  function endDrag(button) {
    if (button === 2) {
      clearTimeout(rmbLongPressTimer);
      rmbLongPressTimer = null;
      rmbDragging = false;
    }
    if (button === 1) {
      clearTimeout(mmbLongPressTimer);
      mmbLongPressTimer = null;
      mmbDragging = false;
    }
  }

  const mouseUpHandler = (e) => {
    endDrag(e.button);
    if (isDrawing && map) {
      map.setStatus({ dragEnable: false });
    }
  };
  addManagedListener(container, "mouseup", mouseUpHandler);

  const mouseLeaveHandler = () => {
    endDrag(1);
    endDrag(2);
  };
  addManagedListener(container, "mouseleave", mouseLeaveHandler);

  const windowMouseUpHandler = () => {
    leftMouseDown = false;
    isPathDrawing = false;
    endDrag(1);
    endDrag(2);
  };
  addManagedListener(window, "mouseup", windowMouseUpHandler, true);
  return () => {
    handlers.forEach(({ element, type, listener, options }) => {
      element.removeEventListener(type, listener, options);
    });
  };
}
