let sessionUUID = null;

function buildLegacyUiPath(path = "/") {
  const normalizedPath = String(path || "/");
  const pathname = window.location.pathname || "/";
  const basePath =
    pathname === "/old" || pathname.startsWith("/old/") ? "/old" : "";
  if (!basePath) {
    return normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`;
  }
  if (normalizedPath === "/") {
    return `${basePath}/`;
  }
  return `${basePath}${normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`}`;
}

// ============================================================
// [安全配置] 输入验证常量
// 这些常量与Python后端保持一致，确保前后端验证规则统一
// ============================================================
const SECURITY_CONSTRAINTS = {
  MAX_USERNAME_LENGTH: 200, // 用户名最大长度
  MAX_PASSWORD_LENGTH: 1000, // 密码最大长度
  MAX_TAG_LENGTH: 200, // 标签最大长度
  MAX_UA_LENGTH: 2000, // User-Agent最大长度
  MIN_PASSWORD_LENGTH: 6, // 密码最小长度
  // 用户名格式验证：只允许字母、数字、下划线、连字符、点和@符号
  USERNAME_PATTERN: /^[a-zA-Z0-9_\-\.@]+$/,
};

const CLIENT_LOG_SENSITIVE_KEYS = new Set([
  "apikey",
  "mapkey",
  "jskey",
  "amapkey",
  "amapjskey",
  "tencentmapkey",
  "tianditutoken",
  "baidumapak",
  "key",
  "token",
  "password",
  "secret",
  "privatekey",
  "accesskey",
  "authorization",
  "cookie",
  "captcha",
  "captchaid",
  "smscode",
  "twofacode",
  "signature",
  "authcode",
  "subopenid",
  "openid",
  "appid",
  "sign",
  "payurl",
  "paymenturl",
  "payinfo",
  "returnurl",
  "notifyurl",
  "requesturl",
]);

const CLIENT_LOG_SENSITIVE_QUERY_PATTERN = /([?&](?:api[_-]?key|key|token|password|secret|authorization|cookie|captcha(?:[_-]?id)?|sms[_-]?code|verification[_-]?code|auth[_-]?code|openid|appid|signature|sign|p)=)[^&#\s]+/gi;
const CLIENT_LOG_SENSITIVE_ASSIGNMENT_PATTERN = /((?:api[_-]?key|map[_-]?key|js[_-]?key|token|password|secret|authorization|cookie|captcha(?:[_-]?id)?|sms[_-]?code|verification[_-]?code|auth[_-]?code|openid|appid|signature|sign)\s*[:=]\s*)(["']?)[^,\s;&}"']+\2/gi;

function createSafeClientLogValue(value, depth = 0) {
  if (depth > 5) {
    return "[已省略]";
  }
  if (typeof value === "string") {
    return value
      .replace(CLIENT_LOG_SENSITIVE_QUERY_PATTERN, "$1[已隐藏]")
      .replace(CLIENT_LOG_SENSITIVE_ASSIGNMENT_PATTERN, "$1$2[已隐藏]$2");
  }
  if (Array.isArray(value)) {
    return value
      .slice(0, 50)
      .map((item) => createSafeClientLogValue(item, depth + 1));
  }
  if (value && typeof value === "object") {
    const safeValue = {};
    Object.entries(value).forEach(([key, item]) => {
      const normalizedKey = key.toLowerCase().replace(/[^a-z0-9]/g, "");
      if (
        CLIENT_LOG_SENSITIVE_KEYS.has(normalizedKey) ||
        normalizedKey.includes("apikey") ||
        normalizedKey.includes("mapkey") ||
        normalizedKey.includes("password") ||
        normalizedKey.includes("token") ||
        normalizedKey.includes("secret") ||
        normalizedKey.includes("captcha") ||
        normalizedKey.includes("signature")
      ) {
        safeValue[key] = "[已隐藏]";
      } else {
        safeValue[key] = createSafeClientLogValue(item, depth + 1);
      }
    });
    return safeValue;
  }
  return value;
}

const mobileAdminUnifiedScrollState = {
  tabType: null,
  scrollTop: 0,
  scrollHeight: 0,
  clientHeight: 0,
};

function captureMobileAdminUnifiedScrollState(tabType) {
  const panel = document.getElementById("mobile-admin-panel-unified");
  if (!panel) {
    return null;
  }
  const snapshot = {
    tabType: tabType || mobileAdminUnifiedScrollState.tabType || null,
    scrollTop: Number(panel.scrollTop || 0),
    scrollHeight: Number(panel.scrollHeight || 0),
    clientHeight: Number(panel.clientHeight || 0),
  };
  mobileAdminUnifiedScrollState.tabType = snapshot.tabType;
  mobileAdminUnifiedScrollState.scrollTop = snapshot.scrollTop;
  mobileAdminUnifiedScrollState.scrollHeight = snapshot.scrollHeight;
  mobileAdminUnifiedScrollState.clientHeight = snapshot.clientHeight;
  return snapshot;
}

function restoreMobileAdminUnifiedScrollState(snapshot, options = {}) {
  const panel = document.getElementById("mobile-admin-panel-unified");
  if (!panel || !snapshot) {
    return;
  }
  const restoreMode = options.restoreMode || "replace";
  const restore = () => {
    if (restoreMode === "append") {
      const previousBottomOffset = Math.max(
        0,
        Number(snapshot.scrollHeight || 0) - Number(snapshot.scrollTop || 0),
      );
      const nextScrollTop = Math.max(0, Number(panel.scrollHeight || 0) - previousBottomOffset);
      panel.scrollTop = nextScrollTop;
    } else {
      panel.scrollTop = Math.max(0, Number(snapshot.scrollTop || 0));
    }
    mobileAdminUnifiedScrollState.tabType = snapshot.tabType || null;
    mobileAdminUnifiedScrollState.scrollTop = Number(panel.scrollTop || 0);
    mobileAdminUnifiedScrollState.scrollHeight = Number(panel.scrollHeight || 0);
    mobileAdminUnifiedScrollState.clientHeight = Number(panel.clientHeight || 0);
  };

  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(restore);
    return;
  }
  restore();
}

function withMobileAdminUnifiedScrollGuard(tabType, renderFn, options = {}) {
  const snapshot = captureMobileAdminUnifiedScrollState(tabType);
  const finalize = () => restoreMobileAdminUnifiedScrollState(snapshot, options);
  try {
    const result = renderFn();
    if (result && typeof result.then === "function") {
      return result.finally(finalize);
    }
    finalize();
    return result;
  } catch (error) {
    finalize();
    throw error;
  }
}

function syncMobileAdminUnifiedPanelScroll(tabType, options = {}) {
  return withMobileAdminUnifiedScrollGuard(tabType, () => {}, options);
}

// let captchaIds = {
//   login: null,
//   register: null,
//   modal: null,
//   "mobile-login": null,
//   "mobile-register": null,
// };
captchaIds_login = null;
captchaIds_register = null;
captchaIds_modal = null;
captchaIds_mobile_login = null;
captchaIds_mobile_register = null;

const RUNTIME_CAPTCHA_PROVIDER_DEFAULT = {
  provider: "image",
  behavior_type: "SLIDER",
};
const BEHAVIOR_CAPTCHA_VERIFIED_CODE = "behavior-verified";
let runtimeCaptchaProviderConfig = null;
let runtimeCaptchaProviderConfigPromise = null;
let behaviorCaptchaLoaderPromise = null;
const behaviorCaptchaInstances = {};
const BEHAVIOR_CAPTCHA_MAX_AUTO_RETRIES = 2;
const BEHAVIOR_CAPTCHA_RETRY_DELAY_MS = 600;
const behaviorCaptchaRetryQueue = new Map();
let behaviorCaptchaRetryTimer = null;

const configLoadState = {
  sms: false,
  system: false,
  captcha: false,
  ssl: false,
  cdn: false,
  yipay: false,
  pricing: false,
  watermark: false,
};

function ensureConfigLoaded(key, label) {
  if (configLoadState[key]) {
    return true;
  }
  Swal.fire({
    icon: "warning",
    title: "配置未加载",
    text: `${label}配置尚未加载，请先点击刷新或等待加载完成`,
  });
  return false;
}

function getUUIDFromURL() {
  const urlPath = window.location.pathname;

  const match = urlPath.match(
    /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i,
  );

  if (match && match[1]) {
    return match[1];
  } else {
    return null;
  }
}
/**
 * 打开SMS回复记录Modal
 * 功能说明：
 * 1. 显示SMS回复记录modal
 * 2. 自动加载回复记录数据
 *
 * 调用时机：
 * - 用户点击"查看回复记录"按钮时
 *
 * 实现细节：
 * - 移除modal的hidden类，使其显示
 * - 调用loadSMSReplyLogs()函数加载数据
 */
const LEGACY_MAP_KEY_RUNTIME_NAMESPACE = "__MAP_KEY_RUNTIME__";
const LEGACY_MAP_KEY_RUNTIME_RETRY_DELAYS = [100, 300];
let legacyMapKeyRuntimeLoadPromise = null;
let legacyMapKeyRuntimeLoadVersion = "";
let legacyMapKeyRuntimeLoadSession = "";

function getLegacyMapKeyRuntimeUrl(scriptUrl, runtimeVersion) {
  const baseUrl = scriptUrl || "/api/map_key_runtime.js";
  const version = String(runtimeVersion || "").trim();
  if (!version || /[?&]v=/.test(baseUrl)) {
    return baseUrl;
  }
  return `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}v=${encodeURIComponent(version)}`;
}

function getLegacyMapKeyRuntimeSessionId(explicitSessionId) {
  const explicit = String(explicitSessionId || "").trim();
  if (
    explicit &&
    (
      typeof isUsableClientSessionUUID !== "function" ||
      isUsableClientSessionUUID(explicit)
    )
  ) {
    return explicit;
  }
  const urlSession = getUUIDFromURL();
  if (
    typeof isUsableClientSessionUUID === "function" &&
    isUsableClientSessionUUID(urlSession)
  ) {
    return urlSession;
  }
  if (
    typeof isUsableClientSessionUUID === "function" &&
    isUsableClientSessionUUID(sessionUUID)
  ) {
    return sessionUUID;
  }
  try {
    const storedSession = window.sessionStorage
      ? window.sessionStorage.getItem("session_uuid")
      : "";
    if (
      typeof isUsableClientSessionUUID === "function" &&
      isUsableClientSessionUUID(storedSession)
    ) {
      return storedSession;
    }
  } catch (_error) {
    // Restricted storage is non-fatal; URL fallback remains available.
  }
  return "";
}

function createLegacyMapKeyRuntimeLoadError(message, details = {}) {
  const error = new Error(message);
  Object.assign(error, details);
  return error;
}

function waitForLegacyMapKeyRuntimeRetry(delayMs) {
  return new Promise((resolve) => setTimeout(resolve, delayMs));
}

async function fetchLegacyMapKeyRuntimeScript(
  runtimeUrl,
  expectedVersion,
  explicitSessionId,
) {
  let lastError = null;
  for (let attempt = 0; attempt <= LEGACY_MAP_KEY_RUNTIME_RETRY_DELAYS.length; attempt += 1) {
    const sessionId = getLegacyMapKeyRuntimeSessionId(explicitSessionId);
    const headers = {};
    if (sessionId) {
      headers["X-Session-ID"] = sessionId;
      addAdminViewOriginSessionHeader(headers, sessionId);
    }
    let response;
    try {
      response = await fetch(runtimeUrl, {
        credentials: "include",
        cache: "no-store",
        headers,
      });
    } catch (error) {
      throw createLegacyMapKeyRuntimeLoadError(
        "地图密钥运行时脚本加载失败",
        {
          cause: error,
          runtimeVersion: expectedVersion,
          attempt: attempt + 1,
        },
      );
    }
    if (response.ok) {
      return {
        scriptText: await response.text(),
        sessionId,
      };
    }
    lastError = createLegacyMapKeyRuntimeLoadError(
      `地图密钥运行时脚本加载失败: HTTP ${response.status}`,
      {
        status: response.status,
        runtimeVersion: expectedVersion,
        attempt: attempt + 1,
      },
    );
    if (
      response.status === 404 &&
      attempt < LEGACY_MAP_KEY_RUNTIME_RETRY_DELAYS.length
    ) {
      await waitForLegacyMapKeyRuntimeRetry(
        LEGACY_MAP_KEY_RUNTIME_RETRY_DELAYS[attempt],
      );
      continue;
    }
    break;
  }
  throw lastError || createLegacyMapKeyRuntimeLoadError(
    "地图密钥运行时脚本加载失败",
    { runtimeVersion: expectedVersion },
  );
}

function removeLegacyMapKeyRuntimeScripts(expectedVersion) {
  Array.from(document.querySelectorAll('script[data-map-key-runtime="1"]'))
    .forEach((script) => {
      if (
        !expectedVersion ||
        String(script.dataset.mapKeyRuntimeVersion || "") === expectedVersion
      ) {
        script.remove();
      }
    });
}

function injectLegacyMapKeyRuntimeScript(scriptText, expectedVersion) {
  const script = document.createElement("script");
  script.async = false;
  script.dataset.mapKeyRuntime = "1";
  script.dataset.mapKeyRuntimeVersion = expectedVersion;
  script.text = scriptText;
  script.textContent = scriptText;
  document.head.appendChild(script);
  return script;
}

function loadLegacyMapKeyRuntime(keyBundle, explicitSessionId) {
  const bundle = keyBundle && typeof keyBundle === "object" ? keyBundle : {};
  const expectedVersion = String(bundle.runtime_version || "").trim();
  const runtimeSessionId = getLegacyMapKeyRuntimeSessionId(explicitSessionId);
  const currentRuntime = window[LEGACY_MAP_KEY_RUNTIME_NAMESPACE];
  if (
    expectedVersion &&
    currentRuntime &&
    currentRuntime.version === expectedVersion
  ) {
    return Promise.resolve();
  }
  if (
    legacyMapKeyRuntimeLoadPromise &&
    legacyMapKeyRuntimeLoadVersion === expectedVersion &&
    legacyMapKeyRuntimeLoadSession === runtimeSessionId
  ) {
    return legacyMapKeyRuntimeLoadPromise;
  }

  legacyMapKeyRuntimeLoadVersion = expectedVersion;
  legacyMapKeyRuntimeLoadSession = runtimeSessionId;
  legacyMapKeyRuntimeLoadPromise = (async () => {
    const existingScripts = Array.from(
      document.querySelectorAll('script[data-map-key-runtime="1"]'),
    );
    const existingScript = existingScripts.find(
      (script) =>
        String(script.dataset.mapKeyRuntimeVersion || "") === expectedVersion,
    );
    if (existingScript) {
      if (
        !expectedVersion ||
        window[LEGACY_MAP_KEY_RUNTIME_NAMESPACE]?.version === expectedVersion
      ) {
        return;
      } else {
        existingScript.remove();
      }
      if (
        !expectedVersion ||
        window[LEGACY_MAP_KEY_RUNTIME_NAMESPACE]?.version === expectedVersion
      ) {
        return;
      }
    }

    const runtimeUrl = getLegacyMapKeyRuntimeUrl(
      bundle.runtime_script,
      expectedVersion,
    );
    let script = null;
    try {
      const { scriptText } = await fetchLegacyMapKeyRuntimeScript(
        runtimeUrl,
        expectedVersion,
        runtimeSessionId,
      );
      removeLegacyMapKeyRuntimeScripts(expectedVersion);
      script = injectLegacyMapKeyRuntimeScript(scriptText, expectedVersion);
      if (
        expectedVersion &&
        window[LEGACY_MAP_KEY_RUNTIME_NAMESPACE]?.version !== expectedVersion
      ) {
        throw createLegacyMapKeyRuntimeLoadError(
          "地图密钥运行时版本不匹配",
          { runtimeVersion: expectedVersion },
        );
      }
    } catch (error) {
      if (script && typeof script.remove === "function") {
        script.remove();
      } else {
        removeLegacyMapKeyRuntimeScripts(expectedVersion);
      }
      throw error;
    }
  })().catch((error) => {
    legacyMapKeyRuntimeLoadPromise = null;
    legacyMapKeyRuntimeLoadVersion = "";
    legacyMapKeyRuntimeLoadSession = "";
    throw error;
  });
  return legacyMapKeyRuntimeLoadPromise;
}

async function hydrateMapProviderSecretsForLegacy(initialData, explicitSessionId) {
  if (!initialData || typeof initialData !== "object") {
    return initialData;
  }
  const keyBundle = initialData.map_provider_key_bundle;
  if (!keyBundle || typeof keyBundle !== "object") {
    return initialData;
  }
  if (keyBundle.available === false) {
    return initialData;
  }

  const runtimeSessionId = getLegacyMapKeyRuntimeSessionId(explicitSessionId);
  if (!runtimeSessionId) {
    throw new Error("地图密钥运行时缺少会话ID");
  }
  await loadLegacyMapKeyRuntime(keyBundle, runtimeSessionId);
  const runtime = window[LEGACY_MAP_KEY_RUNTIME_NAMESPACE];
  if (!runtime || typeof runtime.decryptMapProviderKeys !== "function") {
    throw new Error("地图密钥运行时不可用");
  }

  const runtimeHeaders = {};
  addAdminViewOriginSessionHeader(runtimeHeaders, runtimeSessionId);
  const decryptedProviders = await runtime.decryptMapProviderKeys(
    keyBundle,
    runtimeSessionId,
    runtimeHeaders["X-Admin-Origin-Session-ID"] || "",
  );
  const nextProviders = { ...(initialData.map_providers || {}) };
  Object.entries(decryptedProviders || {}).forEach(([provider, secrets]) => {
    const current = nextProviders[provider];
    nextProviders[provider] = {
      ...(current && typeof current === "object" ? current : {}),
      ...(secrets && typeof secrets === "object" ? secrets : {}),
    };
  });
  return {
    ...initialData,
    map_providers: nextProviders,
  };
}

function createLegacyPublicConfigSnapshot(config) {
  const snapshot = { ...(config || {}) };
  [
    "amap_key",
    "amap_js_key",
    "tencent_map_key",
    "tianditu_token",
    "baidu_map_ak",
    "map_key",
    "js_key",
    "token",
    "ak",
    "security_js_code",
    "backend_page_origin",
  ].forEach((field) => {
    delete snapshot[field];
  });
  const providers = config && config.map_providers;
  if (!providers || typeof providers !== "object") {
    return snapshot;
  }
  snapshot.map_providers = {};
  Object.entries(providers).forEach(([provider, value]) => {
    const safeValue = { ...(value || {}) };
    ["js_key", "map_key", "token", "ak", "security_js_code", "backend_page_origin"].forEach((field) => {
      delete safeValue[field];
    });
    snapshot.map_providers[provider] = safeValue;
  });
  return snapshot;
}

function applyLegacyAppConfig(config, explicitSessionId) {
  const safeConfig = config && typeof config === "object" ? config : {};
  window.__mapKeyRuntimeReady = hydrateMapProviderSecretsForLegacy(
    safeConfig,
    explicitSessionId,
  )
    .then((hydratedConfig) => {
      window.APP_CONFIG = hydratedConfig;
      window.dispatchEvent(
        new CustomEvent("appConfigLoaded", {
          detail: createLegacyPublicConfigSnapshot(hydratedConfig),
        }),
      );
      return hydratedConfig;
    })
    .catch((error) => {
      console.error("[配置] 地图密钥运行时加载失败，使用脱敏配置:", error);
      window.APP_CONFIG = safeConfig;
      window.dispatchEvent(
        new CustomEvent("appConfigLoaded", {
          detail: createLegacyPublicConfigSnapshot(safeConfig),
        }),
      );
      return safeConfig;
    });
  return window.__mapKeyRuntimeReady;
}

// 初始化前端配置：从API加载配置或使用服务端注入的配置
(function initAppConfig() {
  // 默认配置（集中定义，避免重复）
  var DEFAULT_CONFIG = {
    sms_enabled: false,
    reg_verify_enabled: false,
    enable_phone_modification: false,
    map_provider: "amap",
    map_providers: {
      amap: { provider: "amap", display_name: "高德地图", js_key: "", coordinate_system: "gcj02", business_coordinate_system: "gcj02" },
      tencent: { provider: "tencent", display_name: "腾讯地图", map_key: "", coordinate_system: "gcj02", business_coordinate_system: "gcj02" },
      tianditu: { provider: "tianditu", display_name: "天地图", token: "", coordinate_system: "wgs84", business_coordinate_system: "gcj02" },
      baidu: { provider: "baidu", display_name: "百度地图", ak: "", coordinate_system: "bd09", business_coordinate_system: "gcj02" },
    },
  };

  // 如果服务端已经注入了配置（旧方式，用于兼容），直接使用
  if (typeof window.APP_CONFIG !== "undefined") {
    console.log("[配置] 使用服务端注入的配置");
    applyLegacyAppConfig(window.APP_CONFIG, getLegacyMapKeyRuntimeSessionId());
    return;
  }

  // 否则，从API异步加载配置（新方式，减轻后端压力）
  console.log("[配置] 从API加载前端配置...");

  // 先设置默认配置，避免页面加载时出错
  window.APP_CONFIG = DEFAULT_CONFIG;

  // 创建带超时的 AbortController
  var controller = new AbortController();
  var timeoutId = setTimeout(function () {
    controller.abort();
  }, 10000); // 10秒超时

  // 尝试从 URL 中提取 session UUID，用于身份验证
  // URL 格式通常为: /uuid=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  var extractedSessionUUID = null;
  var urlPath = window.location.pathname;
  var uuidMatch = urlPath.match(
    /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i,
  );
  if (uuidMatch && uuidMatch[1]) {
    extractedSessionUUID = uuidMatch[1]; // 提取到的 UUID
  }
  if (!extractedSessionUUID) {
    extractedSessionUUID = getLegacyMapKeyRuntimeSessionId();
  }

  // 构建请求配置对象，包含超时控制和会话认证
  var fetchOptions = {
    signal: controller.signal, // 用于超时控制
    cache: "no-cache", // 禁用缓存，确保获取最新配置
  };

  // 如果提取到了 session UUID，添加认证 header
  // X-Session-ID header 用于后端识别用户会话，几乎所有 API 都需要此 header
  if (extractedSessionUUID) {
    fetchOptions.headers = {
      "X-Session-ID": extractedSessionUUID,
    };
  }

  // 异步获取真实配置
  fetch("/api/frontend-config", fetchOptions)
    .then(function (response) {
      clearTimeout(timeoutId);
      if (!response.ok) {
        throw new Error("配置加载失败: " + response.status);
      }
      return response.json();
    })
    .then(function (config) {
      console.log("[配置] API配置加载完成");
      applyLegacyAppConfig(config, extractedSessionUUID);
    })
    .catch(function (error) {
      clearTimeout(timeoutId);
      if (error.name === "AbortError") {
        console.warn("[配置] 加载配置超时，使用默认配置");
      } else {
        console.error("[配置] 加载配置失败，使用默认配置:", error);
      }
      // 保持默认配置
      applyLegacyAppConfig(DEFAULT_CONFIG, extractedSessionUUID);
    });
})();

// ========================================
// 支付方式配置（从后端动态加载）
// ========================================

/**
 * 全局变量：支付方式配置对象
 *
 * 功能：存储从后端加载的所有支付方式配置信息
 * 数据来源：通过 /api/payment/methods_config 接口从后端动态获取
 * 加载时机：页面加载完成后（DOMContentLoaded事件）自动调用 loadPaymentMethodsConfig() 函数
 *
 * 数据结构：
 * {
 *   'alipay': {
 *     name: '支付宝支付',
 *     icon: 'svg',
 *     svg: '<svg>...</svg>',
 *     borderColor: 'hover:border-sky-500',
 *     textColor: 'text-sky-600',
 *     description: '支持支付宝扫码支付'
 *   },
 *   'wxpay': { ... },
 *   ...
 * }
 *
 * 注意事项：
 * 1. 初始值为空对象，必须等待 loadPaymentMethodsConfig() 加载完成后才有数据
 * 2. 所有使用此变量的代码应确保配置已加载完成
 * 3. 支持SVG图标，icon字段为'svg'时使用svg字段的SVG代码
 * 4. 配置完全由后端.\configs\config.json管理，添加新支付方式无需修改前端代码
 */
let PAYMENT_METHODS = {}; // 将在页面加载时从后端获取

/**
 * 从后端加载支付方式配置
 *
 * 功能说明：
 * 调用后端 /api/payment/methods_config 接口，获取所有支付方式的配置信息
 * 包括支付方式的名称、SVG图标、描述、样式等，并存储到全局变量 PAYMENT_METHODS 中
 *
 * 调用时机：
 * 页面加载完成后自动调用（通过DOMContentLoaded事件监听器）
 *
 * 错误处理：
 * 1. 网络请求失败：记录错误日志，PAYMENT_METHODS保持为空对象
 * 2. 接口返回失败：记录错误信息，PAYMENT_METHODS保持为空对象
 * 3. 数据解析失败：记录异常信息，PAYMENT_METHODS保持为空对象
 *
 * 后续影响：
 * 1. 如果配置加载失败，支付方式选择界面可能无法正常显示
 * 2. 相关功能会检查PAYMENT_METHODS是否为空，以提供降级方案
 *
 * @returns {Promise<void>} 异步函数，无返回值
 */
// async function loadPaymentMethodsConfig_before() {

//     try {
//         // 记录开始加载的日志，便于追踪配置加载流程
//         console.log('[支付方式配置] 开始从后端加载配置...');

//         // 调用后端API接口获取支付方式配置
//         // 使用fetch发起GET请求到 /api/payment/methods_config 端点
//         const response = await fetch('/api/payment/methods_config', {
//             method: 'GET', // GET请求，获取数据
//             headers: {
//                 'Content-Type': 'application/json', // 设置请求头，告知服务器期望返回JSON格式数据
//                 'X-Session-ID': sessionUUID  // 添加会话ID用于身份验证，解决"未登录或会话无效"的问题
//             }
//         });

//         // 解析响应的JSON数据
//         // response.json() 返回一个Promise，解析后得到JavaScript对象
//         const data = await response.json();

//         // 检查接口返回的success字段，判断请求是否成功
//         if (data.success) {
//             // 请求成功，将后端返回的支付方式配置存储到全局变量
//             // data.methods 包含所有支付方式的配置信息（名称、图标、描述等）
//             PAYMENT_METHODS = data.methods;

//             // 记录成功日志，输出配置内容便于调试
//             // 这样开发者可以在浏览器控制台看到完整的配置数据
//             console.log('[支付方式配置] 配置加载成功:', PAYMENT_METHODS);
//         } else {
//             // 请求失败，记录错误信息
//             // data.message 包含服务器返回的具体错误原因
//             console.error('[支付方式配置] 加载失败:', data.message);
//         }
//     } catch (error) {
//         // 捕获所有异常情况（网络错误、JSON解析失败、其他运行时错误等）
//         // 确保即使加载失败也不会导致整个页面崩溃
//         console.error('[支付方式配置] 加载异常:', error);
//     }
// }

// ========================================
// 页面加载完成后的初始化逻辑
// ========================================

// ============================================================
// 高德地图去水印控制配置管理函数（PC端和移动端）
// 用于管理用户的高德地图去水印权限
// ============================================================

/**
 * 加载水印控制配置（PC端）
 *
 * 功能说明：
 * 从服务器获取高德地图去水印控制配置，包括：
 * 1. 系统默认值（从 .\configs\config.json 读取）
 * 2. 所有用户的个性化设置（从 amap_watermark_control.json 读取）
 * 3. 系统中所有用户的列表
 *
 * 然后将这些数据填充到PC端管理面板的表单中。
 *
 * API端点：GET /api/amap/watermark_control/config
 * 权限要求：管理员权限
 *
 * 表单元素：
 * - watermark-default-value_modal：系统默认值开关（checkbox）
 * - watermark-default-label_modal：显示默认值标签（允许/禁止）
 * - watermark-user-count_modal：显示用户总数
 * - watermark-users-list_modal：用户权限列表容器
 */

/**
 * 更新默认水印显示标签
 *
 * 功能：根据默认值开关的状态更新标签文本
 * - 开关打开（checked=true）：显示"允许"
 * - 开关关闭（checked=false）：显示"禁止"
 */
/**
 * 更新水印默认值标签显示
 *
 * 功能说明：
 * 根据系统默认值开关的状态（checked/unchecked），更新标签文本显示为"允许"或"禁止"。
 *
 * 支持平台：
 * - PC端：使用ID "watermark-default-value_modal" 和 "watermark-default-label_modal"
 * - 移动端：使用ID "watermark-default-value-mobile" 和 "watermark-default-label-mobile"
 *
 * 【问题45修复】此函数现在同时支持PC端和移动端
 * 原问题：只支持PC端
 * 修复方案：检测移动端元素，如果存在则同步更新移动端标签
 *
 * 调用时机：
 * 1. 页面加载完成后，初次设置开关状态时
 * 2. 用户手动切换开关时（通过onchange事件触发）
 * 3. 从服务器加载配置后，根据服务器返回的默认值更新显示
 *
 * 实现细节：
 * 1. 查找PC端的默认值开关元素（checkbox）
 * 2. 查找PC端的默认值标签元素
 * 3. 如果两个元素都存在，根据checkbox的checked状态设置标签文本
 * 4. 同样处理移动端的元素（新增）
 */
function handleCdnError(resourceName) {
  resourceName = resourceName || "未指定";
  cdnErrorCount++;
  console.warn(
    "CDN资源[" + resourceName + "]加载失败 (" + cdnErrorCount + "/3)",
  );

  if (cdnErrorTimer) {
    clearTimeout(cdnErrorTimer);
  }

  cdnErrorTimer = setTimeout(function () {
    if (!appInitialized && cdnErrorCount > 0) {
      var errorOverlay = document.getElementById("cdn-error-overlay");
      if (errorOverlay) {
        errorOverlay.style.display = "flex";
        errorOverlay.classList.remove("hidden");
        console.error("应用初始化超时，CDN资源加载失败，已显示错误提示。");
      }
    }
  }, 3000);
}

/**
 * 检查密码强度，判断是否为弱密码
 */
function checkWeakPassword(password) {
  // 1. 长度检查
  // 密码长度必须至少8个字符，这是安全的基本要求
  if (password.length < 6) {
    return { isWeak: true, reason: "密码长度不能少于6个字符" };
  }

  // 2. 纯数字检查
  // 使用正则表达式检查密码是否只包含数字（0-9）
  // 纯数字密码容易被暴力破解，安全性极低
  if (/^\d+$/.test(password)) {
    return { isWeak: true, reason: "密码不能为纯数字" };
  }

  // 3. 纯字母检查
  // 使用正则表达式检查密码是否只包含字母（大小写）
  // 纯字母密码缺乏复杂性，容易被字典攻击破解
  if (/^[a-zA-Z]+$/.test(password)) {
    return { isWeak: true, reason: "密码不能为纯字母，需包含数字或特殊字符" };
  }

  // 4. 常见弱密码列表
  // 这些密码在各种密码泄露事件中出现频率极高，黑客工具都会优先尝试
  var commonWeak = [
    "password",
    "password123",
    "admin123",
    "admin",
    "12345678",
    "123456789",
    "87654321",
    "qwerty",
    "qwerty123",
    "abc123",
    "abcd1234",
    "11111111",
    "00000000",
    "test1234",
    "user1234",
    "pass1234",
    "a1b2c3d4",
    "1q2w3e4r",
    "qwertyui",
    "asdfghjk",
  ];
  // 将密码转换为小写进行比较，防止用户使用大小写混淆绕过检测
  if (commonWeak.includes(password.toLowerCase())) {
    return { isWeak: true, reason: "密码过于简单，请使用更复杂的密码" };
  }

  // 5. 键盘序列检查
  // 键盘序列容易被猜测，因为人们倾向于使用手指在键盘上连续按键的模式
  var patterns = [
    "123456",
    "234567",
    "345678",
    "456789",
    "567890",
    "qwerty",
    "asdfgh",
    "zxcvbn",
    "qazwsx",
    "zaq12wsx",
  ];
  // 将密码转换为小写后检查是否包含键盘序列
  var passwordLower = password.toLowerCase();
  for (var i = 0; i < patterns.length; i++) {
    if (passwordLower.includes(patterns[i])) {
      return { isWeak: true, reason: "密码包含键盘序列，请使用更复杂的密码" };
    }
  }

  // 6. 检查字符重复
  // 统计密码中不同字符的数量
  // 如果不同字符种类少于4种，说明密码重复性太高，缺乏多样性
  var uniqueChars = {};
  for (var i = 0; i < password.length; i++) {
    uniqueChars[password[i]] = true;
  }
  var uniqueCount = Object.keys(uniqueChars).length;
  if (uniqueCount < 4) {
    return { isWeak: true, reason: "密码字符重复过多，请使用更多样化的字符" };
  }

  // 通过所有检查，密码强度合格
  // 返回 isWeak: false 表示不是弱密码，reason 为空字符串
  return { isWeak: false, reason: "" };
}

// 新增：返回管理员会话逻辑
function returnToAdminSession() {
  const originSession = getStoredAdminReturnOriginSession();
  if (originSession) {
    // 清除记录并跳转回原会话
    localStorage.removeItem(ADMIN_RETURN_ORIGIN_STORAGE_KEY);
    window.location.href = buildLegacyUiPath(`/uuid=${originSession}`);
  } else {
    // 异常情况，回首页
    window.location.href = buildLegacyUiPath("/");
  }
}

// 新增：清除"返回管理员会话"记录并隐藏按钮
function clearAdminReturnOriginState(reason = "") {
  legacyAdminViewContext = null;
  legacyAdminViewRejected = false;
  adminReturnOriginVerifyToken++;
  adminReturnOriginVerifiedFor = "";
  try {
    localStorage.removeItem(ADMIN_RETURN_ORIGIN_STORAGE_KEY);
  } catch (_error) {
    // Storage may be unavailable in restricted browser contexts.
  }
  const overlay = document.getElementById("admin-return-overlay");
  if (overlay) {
    overlay.classList.add("hidden");
  }
  if (reason) {
    logMessage_Info("[上帝模式] 已清除返回按钮记录：" + reason);
  }
}

// 来源会话（管理员自己的会话）可能已经被销毁：例如管理员在查看他人会话时
// 关闭浏览器，来源会话被回收；之后再登录并新建会话，localStorage 里的旧记录
// 会让右上角继续显示"返回管理员会话"，点进去只会跳到已销毁的 UUID。
// 这里向后端确认来源会话是否还存在（/auth/check_uuid_type 返回 unknown 表示
// 会话文件已删除），不存在就清掉记录并隐藏按钮。
let adminReturnOriginVerifyToken = 0;
let adminReturnOriginVerifiedFor = "";
let adminReturnOriginVerifyPromise = null;

function verifyAdminReturnOriginSession(originSession, currentUUID) {
  if (!originSession || !currentUUID || originSession === currentUUID) {
    return Promise.resolve();
  }
  if (getStoredAdminReturnOriginSession() !== originSession) return Promise.resolve();
  if (adminReturnOriginVerifiedFor === originSession) {
    // 同一来源会话只校验一次；重复调用复用正在进行的请求。
    return adminReturnOriginVerifyPromise || Promise.resolve();
  }
  adminReturnOriginVerifiedFor = originSession;

  const requestToken = ++adminReturnOriginVerifyToken;
  adminReturnOriginVerifyPromise = fetch("/auth/check_uuid_type", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uuid: originSession }),
  })
    .then((response) => response.json())
    .then((result) => {
      if (requestToken !== adminReturnOriginVerifyToken) return;
      if (getStoredAdminReturnOriginSession() !== originSession) return;
      if (getCurrentLegacySessionUUID() !== currentUUID) return;
      if (result && result.success && result.uuid_type === "unknown") {
        clearAdminReturnOriginState("来源会话已不存在: " + originSession);
        legacyAdminViewRejected = true;
      }
    })
    .catch((error) => {
      logMessage_Warning("[上帝模式] 校验来源会话状态失败:", error);
    });
  return adminReturnOriginVerifyPromise;
}

// 新增：检查是否需要显示返回按钮
function checkAdminReturnState() {
  const originSession = getStoredAdminReturnOriginSession();
  const overlay = document.getElementById("admin-return-overlay");

  logMessage_Info(
    "[上帝模式] 检查管理员返回按钮显示状态，来源会话UUID：" + originSession,
  );
  logMessage_Info("[上帝模式] 当前页面URL：" + window.location.pathname);

  if (!overlay) return;

  const currentUUID = getCurrentLegacySessionUUID();

  // 只有当存在来源记录，且当前页面UUID与来源UUID不一致时才显示
  if (
    originSession &&
    currentUUID &&
    originSession !== currentUUID &&
    originSession !== "null" &&
    originSession !== "undefined" &&
    originSession !== "" &&
    originSession !== "NaN"
  ) {
    overlay.classList.remove("hidden");
    console.log("[上帝模式] 检测到管理员查看他人会话，显示返回按钮");
    // 初始化拖拽功能
    initDraggableAdminBtn();
    // 显示之前先确认来源会话是否仍然存在，避免留下失效的返回按钮
    verifyAdminReturnOriginSession(originSession, currentUUID);
  } else {
    overlay.classList.add("hidden");
    // 修正：如果当前就在来源会话（管理员自己的会话），则清理掉localStorage标记
    // 防止脏数据导致逻辑混乱
    if (originSession && currentUUID && originSession === currentUUID) {
      localStorage.removeItem(ADMIN_RETURN_ORIGIN_STORAGE_KEY);
      console.log("[上帝模式] 检测到已位于管理员原会话，自动清除返回记录");
    }
  }
}

// 新增：使管理员按钮可拖拽
function initDraggableAdminBtn() {
  const overlay = document.getElementById("admin-return-overlay");
  const btn = document.getElementById("admin-return-btn");
  if (!overlay || !btn || overlay.dataset.initDrag) return;

  overlay.dataset.initDrag = "true"; // 防止重复绑定

  let isDragging = false;
  let hasMoved = false; // 用于区分点击和拖拽
  let startX, startY, initialLeft, initialTop;

  // 获取当前位置 (兼容 touch 和 mouse)
  const getClientXY = (e) => {
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return { x: clientX, y: clientY };
  };

  const onStart = (e) => {
    // 如果是鼠标右键，不触发
    if (e.type === "mousedown" && e.button !== 0) return;

    isDragging = true;
    hasMoved = false;

    const { x, y } = getClientXY(e);
    startX = x;
    startY = y;

    // 获取当前计算后的样式位置
    const rect = overlay.getBoundingClientRect();
    initialLeft = rect.left;
    initialTop = rect.top;

    // 移除 fixed 的定位类（top-4 left-4），改为直接操作 style
    // 这样拖拽时更平滑
    overlay.classList.remove("top-4", "left-4", "bottom-4", "right-4");
    overlay.style.left = `${initialLeft}px`;
    overlay.style.top = `${initialTop}px`;
    overlay.style.right = "auto";
    overlay.style.bottom = "auto";

    // 绑定移动和结束事件到 document，防止拖出元素范围失效
    document.addEventListener("mousemove", onMove, { passive: false });
    document.addEventListener("touchmove", onMove, { passive: false });
    document.addEventListener("mouseup", onEnd);
    document.addEventListener("touchend", onEnd);
  };

  const onMove = (e) => {
    if (!isDragging) return;

    const { x, y } = getClientXY(e);
    const dx = x - startX;
    const dy = y - startY;

    // 只有移动超过 5px 才视为拖拽，防止手抖误触
    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
      hasMoved = true;
      // 阻止默认滚动行为（仅在移动时）
      if (e.cancelable) e.preventDefault();
    }

    // 更新位置
    let newLeft = initialLeft + dx;
    let newTop = initialTop + dy;

    // 边界限制 (防止拖出屏幕)
    const maxLeft = window.innerWidth - overlay.offsetWidth;
    const maxTop = window.innerHeight - overlay.offsetHeight;

    newLeft = Math.max(0, Math.min(newLeft, maxLeft));
    newTop = Math.max(0, Math.min(newTop, maxTop));

    overlay.style.left = `${newLeft}px`;
    overlay.style.top = `${newTop}px`;
  };

  const onEnd = () => {
    isDragging = false;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("touchmove", onMove);
    document.removeEventListener("mouseup", onEnd);
    document.removeEventListener("touchend", onEnd);
  };

  // 绑定开始事件
  overlay.addEventListener("mousedown", onStart);
  overlay.addEventListener("touchstart", onStart, { passive: false });

  // 绑定点击事件
  btn.addEventListener("click", (e) => {
    // 如果发生了拖拽移动，则拦截点击事件
    if (hasMoved) {
      e.preventDefault();
      e.stopPropagation();
      console.log("拖拽结束，拦截点击");
    } else {
      // 纯点击，执行原有逻辑
      returnToAdminSession();
    }
  });
}

// --- Next Script Block ---

if (typeof tailwind !== "undefined") {
  tailwind.config = {
    theme: {
      extend: {
        fontFamily: {
          sans: ["Noto Sans SC", "system-ui", "sans-serif"],
          display: ["Zilla Slab", "serif"],
        },
        colors: { base: "#7dd3fc" },
      },
    },
  };
} else {
  console.error("Tailwind CSS 未加载，跳过配置。");
  if (typeof handleCdnError === "function") handleCdnError("TailwindCSS");
}

// --- Next Script Block ---

async function loadMobileSessionPickerList() {
  const listEl = $("mobile-session-picker-list");
  if (!listEl) {
    logMessage_Error(
      "loadMobileSessionPickerList: 无法找到 'mobile-session-picker-list' 容器。",
    );
    return;
  }

  listEl.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const headers = { "X-Session-ID": getAuthenticatedSessionHeaderValue() };
    const response = await fetch("/auth/user/sessions", {
      headers: headers,
    });
    const result = await response.json();

    if (!result.success) {
      listEl.innerHTML = `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      return;
    }

    const sessions = result.sessions || [];

    currentSessionInfo.maxSessions = result.max_sessions || 1;
    const validSessions = sessions.filter(
      (session) =>
        session.session_id &&
        session.session_id !== "null" &&
        session.session_id.trim() !== "",
    );
    currentSessionInfo.currentCount = validSessions.length;

    const countEl = $("mobile-session-picker-count-display");
    if (countEl) {
      const { currentCount, maxSessions } = currentSessionInfo;
      if (maxSessions === -1) {
        countEl.innerHTML = `<span class="text-green-600">会话数: ${currentCount} / 无限制</span>`;
      } else {
        const colorClass =
          currentCount >= maxSessions ? "text-red-600" : "text-slate-600";
        countEl.innerHTML = `<span class="${colorClass}">会话数: ${currentCount} / ${maxSessions}</span>`;
      }
    }

    if (validSessions.length === 0) {
      listEl.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无会话，请创建新会话</p>';
      return;
    }

    listEl.innerHTML = validSessions
      .map((session) => {
        const createdDate = session.created_at
          ? new Date(session.created_at * 1000).toLocaleString()
          : "未知";
        const isCurrent =
          session.is_current || session.session_id === sessionUUID;
        const sessionHash =
          session.session_hash || session.session_id.substring(0, 16);
        const ownerUsername = String(session.username || currentAuthUsername || "");
        const sessionIdArg = escapeInlineJsArg(session.session_id);
        const ownerUsernameArg = escapeInlineJsArg(ownerUsername);

        const is_multi_mode = session.is_multi_account_mode;
        const session_login_success = session.login_success;

        let statusStyles = "";
        let statusText = "";

        if (is_multi_mode) {
          statusStyles = session_login_success
            ? "bg-purple-100 text-purple-700"
            : "bg-gray-100 text-gray-700";
          statusText = session_login_success ? "✓ 已登录" : "○ 未登录";
        } else {
          statusStyles = session_login_success
            ? "bg-green-100 text-green-700"
            : "bg-gray-100 text-gray-700";
          statusText = session_login_success ? "✓ 已登录" : "○ 未登录";
        }

        return `
      <div class="mobile-list-item justify-between ${
        isCurrent ? "border-2 border-sky-500 bg-sky-50" : "bg-white"
      }" 
           ${
              !isCurrent
                ? `onclick='selectSessionFromPicker(${sessionIdArg}, ${ownerUsernameArg})' style="cursor: pointer;"`
                : 'style="cursor: default;"'
            }
           title="${!isCurrent ? "点击进入此会话" : "这是当前会话"}">
        
        <div class="flex-1 min-w-0 pr-3">
          <div class="flex flex-col"> <div class="flex items-center mb-1">
               <span class="text-sm font-bold text-slate-800">会话</span>
               ${
                 isCurrent
                   ? '<span class="text-xs text-sky-600 ml-2 px-2 py-0.5 bg-sky-100 rounded-full flex-shrink-0">(当前)</span>'
                   : ""
               }
            </div>
            <p class="font-mono text-xs text-slate-600 break-all select-all bg-slate-50 p-1 rounded border border-slate-100" title="${
              session.session_id
            }">
              ${session.session_id}
            </p>
          </div>
          <p class="text-xs text-slate-500 mt-1">${createdDate}</p>
          <p class="text-xs mt-2">
            <span class="px-2 py-0.5 rounded-full text-xs font-semibold ${statusStyles}">
              ${statusText}
            </span>
          </p>
        </div>
        
        <div class="flex-shrink-0 flex items-center justify-center pl-2">
          ${
            !isCurrent
              ? `
            <button class="btn btn-ghost !text-red-500 !py-3 !px-4 !rounded-lg" 
                    onclick="event.stopPropagation(); deleteSessionFromPicker(${escapeInlineJsArg(session.session_id)});"
                    title="删除此会话">
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path>
              </svg>
            </button>
          `
              : `
            <div class="px-4" title="这是当前会话">
              <svg class="w-6 h-6 text-sky-500" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path></svg>
            </div>
          `
          }
        </div>
      </div>
    `;
      })
      .join("");
  } catch (e) {
    logMessage_Error("加载会话列表失败:", e);
    listEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

function showMobileSessionPicker() {
  const modal = $("mobile-session-picker-modal");
  if (!modal) {
    console.error("Mobile session picker modal DOM not found!");
    return;
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
  modal.classList.add("show");
  document.body.classList.add("modal-visible");

  loadMobileSessionPickerList();
}

function closeMobileSessionPicker() {
  const modal = $("mobile-session-picker-modal");
  if (!modal) return;

  modal.classList.remove("show");

  setTimeout(() => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }, 300);

  document.body.classList.remove("modal-visible");
}

function refreshMobileSessionPicker() {
  loadMobileSessionPickerList();
}

// --- Next Script Block ---

// ==============================================================================
// JavaScript代码部分
// ==============================================================================

let refreshUserListInterval = null;
let isInNetworkErrorState = false;
let networkRetryInProgress = false;
const NETWORK_RETRY_MAX = 10;
const NETWORK_RETRY_DELAY_MS = 2000;
const NETWORK_DIALOG_AUTO_RETRY_MAX = 5;
const NETWORK_DIALOG_AUTO_RETRY_INTERVAL_MS = 8000;
let networkDialogAutoRetryCount = 0;
let networkDialogAutoRetryTimer = null;

function isWebSocketConnected() {
  return !!(socket && socket.connected);
}

function stopUserListPollingFallback() {
  if (!refreshUserListInterval) return;
  clearInterval(refreshUserListInterval);
  refreshUserListInterval = null;
}

function startUserListPollingFallback() {
  if (
    refreshUserListInterval ||
    isInNetworkErrorState ||
    isWebSocketConnected()
  ) {
    return;
  }
  refreshUserListInterval = setInterval(refreshUserList, 30000);
  logMessage_Info("refreshUserList fallback interval started.");
}

function syncUserListPollingBySocketState() {
  if (isWebSocketConnected() || isInNetworkErrorState) {
    stopUserListPollingFallback();
    return;
  }
  startUserListPollingFallback();
}

async function checkServerHealth() {
  try {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch("/health", {
      method: "GET",
      cache: "no-cache",
      signal: ctrl.signal,
    });
    clearTimeout(tid);
    return res.ok;
  } catch (_) {
    return false;
  }
}

function enterNetworkErrorState() {
  if (isInNetworkErrorState) return;
  isInNetworkErrorState = true;
  logMessage_Info("[网络] 进入网络错误状态");

  stopUserListPollingFallback();
  if (socket) {
    if (socket.io) socket.io.opts.reconnection = false;
    if (socket.connected) socket.disconnect();
  }
}

function exitNetworkErrorState() {
  if (!isInNetworkErrorState) return;
  isInNetworkErrorState = false;
  logMessage_Info("[网络] 退出网络错误状态，恢复连接");
  stopDialogAutoRetry();
  networkDialogAutoRetryCount = 0;

  setTimeout(() => {
    syncUserListPollingBySocketState();
    if (socket && !socket.connected && sessionUUID) {
      if (socket.io) socket.io.opts.reconnection = true;
      socket.connect();
    }
  }, 1000);
}

function stopDialogAutoRetry() {
  if (networkDialogAutoRetryTimer) {
    clearInterval(networkDialogAutoRetryTimer);
    networkDialogAutoRetryTimer = null;
  }
}

function startDialogAutoRetry() {
  stopDialogAutoRetry();
  if (networkDialogAutoRetryCount >= NETWORK_DIALOG_AUTO_RETRY_MAX) {
    logMessage_Info(`[网络] 后台自动重试已达上限 (${NETWORK_DIALOG_AUTO_RETRY_MAX})，等待用户操作`);
    return;
  }
  networkDialogAutoRetryTimer = setInterval(async () => {
    networkDialogAutoRetryCount++;
    logMessage_Info(`[网络] 后台自动重试 ${networkDialogAutoRetryCount}/${NETWORK_DIALOG_AUTO_RETRY_MAX}`);
    const alive = await checkServerHealth();
    if (alive) {
      logMessage_Info("[网络] 后台自动重试成功，服务器恢复");
      Swal.close();
      exitNetworkErrorState();
      return;
    }
    if (networkDialogAutoRetryCount >= NETWORK_DIALOG_AUTO_RETRY_MAX) {
      stopDialogAutoRetry();
      logMessage_Info("[网络] 后台自动重试用尽，等待用户手动重试");
    }
  }, NETWORK_DIALOG_AUTO_RETRY_INTERVAL_MS);
}

async function showNetworkErrorDialog() {
  stopDialogAutoRetry();

  const result = await Swal.fire({
    title: "网络错误",
    html: getServerConnectionGuidanceMessage(),
    icon: "error",
    confirmButtonText: "重试连接",
    allowOutsideClick: false,
    allowEscapeKey: false,
    didOpen: (popup) => {
      popup.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") {
          e.preventDefault();
          e.stopPropagation();
        }
      });
    },
  });

  if (!result.isConfirmed) return;

  logMessage_Info("[网络] 用户点击重试连接");
  stopDialogAutoRetry();
  const alive = await checkServerHealth();
  if (alive) {
    exitNetworkErrorState();
  } else {
    showNetworkErrorDialog();
  }
}

function safeRemoveModalVisible() {
  const openModals = document.querySelectorAll(
    "#admin-panel-modal.flex, #mobile-admin-panel-modal.flex, " +
    "#amap-key-modal.flex, #user-details-modal.flex, " +
    "#task-details-modal.flex, #account-params-modal.flex"
  );
  if (openModals.length === 0) {
    document.body.classList.remove("modal-visible");
  }
}
let cdnErrorCount = 0;
let cdnErrorTimer = null;
let appInitialized = false;

let currentUserIsGuest = false;
let currentAuthUsername = null;
let healthAutoRefreshInterval = null;
let multiAccountAutoRefreshInterval = null;
let avatarCropper = null;
let isRegistrationCrop = false;
let registrationCroppedAvatarBlob = null;
let currentLogPage = 1;
const LOG_HIGHLIGHT_RULES = [
  {
    key: "error",
    pattern: /\b(error|err|fatal|critical)\b/gi,
    className: "text-red-300 font-semibold",
  },
  {
    key: "warning",
    pattern: /\b(warning|warn)\b/gi,
    className: "text-amber-200 font-semibold",
  },
  {
    key: "info",
    pattern: /\b(info|notice)\b/gi,
    className: "text-sky-200 font-semibold",
  },
  {
    key: "debug",
    pattern: /\b(debug|trace)\b/gi,
    className: "text-violet-200 font-semibold",
  },
];
let croppedAvatarFile = null;

let currentSessionInfo = {
  maxSessions: 1,
  currentCount: 0,
};

// ============================================================
// 移动端设备检测与UI容器切换功能
// ============================================================

let isMobileMode = false;
const DEFAULT_VIEWPORT_CONTENT = "width=device-width, initial-scale=1";
let _desktopViewportForced = false;

function shouldForceDesktopLayout() {
  const viewportWidth = Math.max(
    window.innerWidth || 0,
    document.documentElement?.clientWidth || 0,
  );
  const hasTouch =
    "maxTouchPoints" in navigator
      ? Number(navigator.maxTouchPoints) > 0
      : "ontouchstart" in window;
  return hasTouch && viewportWidth > 0 && viewportWidth < 1024;
}

function applyDesktopForcedViewport(forceDesktop) {
  const viewportMeta = document.querySelector('meta[name="viewport"]');
  if (!viewportMeta) return;

  if (forceDesktop) {
    if (!_desktopViewportForced) {
      viewportMeta.setAttribute(
        "content",
        "width=1280, initial-scale=0.25, minimum-scale=0.25",
      );
      _desktopViewportForced = true;
      console.log("[视口控制] 已强制桌面视口: width=1280");
    }
  } else if (_desktopViewportForced) {
    viewportMeta.setAttribute("content", DEFAULT_VIEWPORT_CONTENT);
    _desktopViewportForced = false;
    console.log("[视口控制] 已恢复默认移动视口");
  }
}

function detectMobileDevice() {
  const userAgent = navigator.userAgent || navigator.vendor || window.opera;
  const mobileRegex =
    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile|CriOS/i;
  const isMobile = mobileRegex.test(userAgent);

  console.log("[移动端检测] User-Agent:", userAgent);
  console.log("[移动端检测] 最终判定:", isMobile ? "移动设备" : "桌面设备");

  return isMobile;
}

function switchUIContainer() {
  const mobileContainer = document.getElementById("mobile-container");
  const desktopContainer = document.getElementById("desktop-container");

  if (!mobileContainer || !desktopContainer) {
    console.warn("[UI切换] 警告：移动端或桌面端容器未找到");
    return;
  }

  const isMobile = detectMobileDevice();
  isMobileMode = isMobile;
  const desktopForced = !isMobile && shouldForceDesktopLayout();
  applyDesktopForcedViewport(desktopForced);
  document.body.classList.toggle("desktop-forced-mode", desktopForced);

  if (isMobile) {
    console.log("[UI切换] 切换到移动端模式");

    const desktopLoginVisible =
      !$("login-container").classList.contains("hidden");
    const desktopAuthVisible = !$("auth-login-container").classList.contains(
      "hidden",
    );
    const desktopMainAppVisible = !$("main-app").classList.contains("hidden");
    const desktopMultiAccountVisible =
      !$("multi-account-app").classList.contains("hidden");

    mobileContainer.style.display = "block";
    desktopContainer.style.setProperty("display", "none", "important");

    const desktopElements = [
      "auth-login-container",
      "login-container",
      "main-app",
      "multi-account-app",
    ];
    desktopElements.forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.style.setProperty("display", "none", "important");
        el.style.setProperty("visibility", "hidden", "important");
        el.style.setProperty("pointer-events", "none", "important");
      }
    });

    $("mobile-login-container").classList.add("hidden");
    $("mobile-auth-login-container").classList.add("hidden");
    $("mobile-main-app").classList.add("hidden");
    $("mobile-multi-account-app").classList.add("hidden");

    if (desktopMainAppVisible) {
      if (typeof destroyMobileMultiMap === "function") {
        destroyMobileMultiMap();
        console.log("[UI切换] 已销毁多账号地图（切换到单账号模式）");
      }

      const mobileLoadingOverlay = document.getElementById(
        "mobile-loading-overlay",
      );
      if (mobileLoadingOverlay) {
        mobileLoadingOverlay.classList.remove("hidden");
      }

      $("mobile-main-app").classList.remove("hidden");
      updateMobileNavVisibility(true, "single");
      console.log("[UI切换] PC端main-app可见，显示移动端mobile-main-app");
      switchMobileSinglePanel("mobile-control-panel");
      console.log("[UI切换] 已默认激活mobile-control-panel");

      setTimeout(() => {
        if (mobileLoadingOverlay) {
          mobileLoadingOverlay.classList.add("hidden");
        }
      }, 500);
    } else if (desktopMultiAccountVisible) {
      if (typeof destroyMobileSingleMap === "function") {
        destroyMobileSingleMap();
        console.log("[UI切换] 已销毁单账号地图（切换到多账号模式）");
      }

      $("mobile-multi-account-app").classList.remove("hidden");
      updateMobileNavVisibility(true, "multi");
      console.log(
        "[UI切换] PC端multi-account-app可见，显示移动端mobile-multi-account-app",
      );
      switchMobilePanel("mobile-multi-control-panel", "multi");
      console.log("[UI切换] 已默认激活mobile-multi-control-panel");
    } else if (desktopLoginVisible) {
      clearLogoutElsewhereOverlay();
      $("mobile-login-container").classList.remove("hidden");
      updateMobileNavVisibility(false);
      console.log(
        "[UI切换] PC端login-container可见，显示移动端mobile-login-container",
      );
    } else if (desktopAuthVisible) {
      clearLogoutElsewhereOverlay();
      $("mobile-auth-login-container").classList.remove("hidden");
      updateMobileNavVisibility(false);
      console.log(
        "[UI切换] PC端auth-login-container可见，显示移动端mobile-auth-login-container",
      );
      try {
        (function () {
          var btn = document.getElementById("newbie-help-btn");
          if (btn) {
            if (!btn._origStyle) {
              btn._origStyle = {
                top: btn.style.top,
                right: btn.style.right,
                bottom: btn.style.bottom,
                left: btn.style.left,
                position: btn.style.position,
                display: btn.style.display,
              };
            }
            // 在移动模式下将按钮置于右上角并确保可见与可拖拽
            btn.style.position = "fixed";
            btn.style.top = "1rem";
            btn.style.right = "1rem";
            btn.style.bottom = "auto";
            btn.style.left = "auto";
            btn.style.display = "flex";
            try {
              if (typeof makeDraggable === "function") {
                makeDraggable("newbie-help-btn");
              }
            } catch (e) {}
          }
        })();
      } catch (e) {
        console.error(e);
      }
    }

    const modalElements = ["admin-panel-modal", "session-picker-modal"];
    modalElements.forEach((id) => {
      const el = document.getElementById(id);
      if (el && !el.classList.contains("hidden")) {
        el.classList.add("hidden");
      }
    });

    document.body.classList.add("mobile-mode");

    initializeMobileUI();
  } else {
    console.log("[UI切换] 切换到桌面端模式");

    const mobileLoginVisible = !$("mobile-login-container").classList.contains(
      "hidden",
    );
    const mobileAuthVisible = !$(
      "mobile-auth-login-container",
    ).classList.contains("hidden");
    const mobileMainAppVisible =
      !$("mobile-main-app").classList.contains("hidden");
    const mobileMultiAccountVisible = !$(
      "mobile-multi-account-app",
    ).classList.contains("hidden");

    mobileContainer.style.display = "none";
    desktopContainer.style.display = "block";

    document.body.classList.remove("mobile-mode");
    try {
      var btn = document.getElementById("newbie-help-btn");
      if (btn && btn._origStyle) {
        btn.style.top = btn._origStyle.top || "";
        btn.style.right = btn._origStyle.right || "";
        btn.style.bottom = btn._origStyle.bottom || "";
        btn.style.left = btn._origStyle.left || "";
        btn.style.position = btn._origStyle.position || "";
        btn.style.display = btn._origStyle.display || "";
      }
    } catch (e) {
      console.error(e);
    }

    const desktopElements = [
      "auth-login-container",
      "login-container",
      "main-app",
      "multi-account-app",
    ];
    desktopElements.forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.style.removeProperty("display");
        el.style.removeProperty("visibility");
        el.style.removeProperty("pointer-events");
      }
    });

    $("login-container").classList.add("hidden");
    $("auth-login-container").classList.add("hidden");
    $("main-app").classList.add("hidden");
    $("multi-account-app").classList.add("hidden");

    if (mobileMainAppVisible) {
      $("main-app").classList.remove("hidden");
      $("main-app").classList.add("grid");
      console.log("[UI切换] 移动端mobile-main-app可见，显示PC端main-app");
    } else if (mobileMultiAccountVisible) {
      $("multi-account-app").classList.remove("hidden");
      $("multi-account-app").classList.add("grid");
      console.log(
        "[UI切换] 移动端mobile-multi-account-app可见，显示PC端multi-account-app",
      );
    } else if (mobileLoginVisible) {
      clearLogoutElsewhereOverlay();
      $("login-container").classList.remove("hidden");
      console.log(
        "[UI切换] 移动端mobile-login-container可见，显示PC端login-container",
      );
    } else if (mobileAuthVisible) {
      clearLogoutElsewhereOverlay();
      $("auth-login-container").classList.remove("hidden");
      console.log(
        "[UI切换] 移动端mobile-auth-login-container可见，显示PC端auth-login-container",
      );
    }
  }
}

async function saveMobileAttendanceParams() {
  const enabledInput = document.getElementById(
    "mobile-param-auto_attendance_enabled",
  );
  const refreshInput = document.getElementById(
    "mobile-param-auto_attendance_refresh_s",
  );
  const radiusInput = document.getElementById(
    "mobile-param-attendance_user_radius_m",
  );
  const stopAfterSuccessInput = document.getElementById(
    "mobile-param-auto_attendance_stop_after_success",
  );
  const successLimitInput = document.getElementById(
    "mobile-param-auto_attendance_success_limit",
  );

  if (
    !enabledInput ||
    !refreshInput ||
    !radiusInput ||
    !stopAfterSuccessInput ||
    !successLimitInput
  ) {
    // showModalAlert("无法获取参数输入框", "错误");
    Swal.fire({
      icon: "error",
      title: "参数获取失败",
      text: "无法获取参数输入框，请刷新页面重试。",
    });
    return;
  }

  const enabled = enabledInput.checked;
  const refresh = parseInt(refreshInput.value);
  const radius = parseInt(radiusInput.value);
  const stopAfterSuccess = stopAfterSuccessInput.checked;
  const successLimit = parseInt(successLimitInput.value);

  if (isNaN(refresh) || refresh < 10 || isNaN(successLimit) || successLimit < 1) {
    // showModalAlert("刷新间隔不能小于10秒", "错误");
    Swal.fire({
      icon: "error",
      title: "参数错误",
      text: "刷新间隔不能小于10秒",
    });
    return;
  }

  try {
    await callPythonAPI("update_param", "auto_attendance_enabled", enabled);
    await callPythonAPI(
      "update_param",
      "auto_attendance_stop_after_success",
      stopAfterSuccess,
    );
    await callPythonAPI(
      "update_param",
      "auto_attendance_success_limit",
      successLimit,
    );
    await callPythonAPI("update_param", "auto_attendance_refresh_s", refresh);
    await callPythonAPI("update_param", "attendance_user_radius_m", radius);

    if (typeof pythonParams !== "undefined") {
      pythonParams["auto_attendance_enabled"] = enabled;
      pythonParams["auto_attendance_stop_after_success"] = stopAfterSuccess;
      pythonParams["auto_attendance_success_limit"] = successLimit;
      pythonParams["auto_attendance_refresh_s"] = refresh;
      pythonParams["attendance_user_radius_m"] = radius;
    }

    // showModalAlert("自动签到配置已保存", "成功");
    // 使用队列方式显示提示，避免与其他提示冲突
    // 先显示配置保存提示
    await Swal.fire({
      icon: "success",
      title: "配置已保存",
      text: "自动签到配置已成功保存。",
      timer: 1500,
      showConfirmButton: false,
    });

    // 然后显示自动签到状态提示
    showAutoAttendanceToggleAlert(enabled, true); // true = 移动端
  } catch (e) {
    console.error("保存签到配置失败:", e);
    // showModalAlert("保存失败: " + e.message, "错误");
    Swal.fire({
      icon: "error",
      title: "保存失败",
      text: "保存失败: " + e.message,
    });
  }
}

/**
 * 显示自动签到开关状态变更提示
 * 根据设备类型显示不同格式的账号信息
 * @param {boolean} enabled - 是否开启自动签到
 * @param {boolean} isMobile - 是否为移动端
 */
function showAutoAttendanceToggleAlert(enabled, isMobile) {
  // 获取当前用户信息
  const userName = currentUserData?.name || "未知";
  const studentId = currentUserData?.student_id || "未知";
  
  // 检查账号列表是否为空（多账号模式下使用）
  const hasAccounts = cachedMultiAccounts && cachedMultiAccounts.length > 0;
  
  // 构建提示内容
  let htmlContent = "";
  
  if (enabled) {
    // 开启自动签到的提示
    htmlContent = `
      <div class="text-left">
        <p class="mb-3 text-green-600 font-semibold">✅ 自动签到已开启</p>
    `;
    
    // 如果有当前用户信息（单账号模式）
    if (currentUserData && currentUserData.student_id) {
      if (isMobile) {
        // 移动端：卡片式展示
        htmlContent += `
          <div class="bg-gradient-to-br from-sky-50 to-blue-50 rounded-xl p-3 border border-sky-100 shadow-sm mb-3">
            <p class="text-xs text-slate-500 mb-1">当前账号</p>
            <p class="font-semibold text-slate-800">${escapeHtml(userName)}</p>
            <p class="text-sm text-slate-600 font-mono">${escapeHtml(studentId)}</p>
          </div>
        `;
      } else {
        // PC端：表格式展示
        htmlContent += `
          <table class="w-full text-sm border-collapse mb-3">
            <thead>
              <tr class="bg-slate-100">
                <th class="px-3 py-2 text-left border border-slate-200 font-semibold">姓名</th>
                <th class="px-3 py-2 text-left border border-slate-200 font-semibold">学号</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="px-3 py-2 border border-slate-200">${escapeHtml(userName)}</td>
                <td class="px-3 py-2 border border-slate-200 font-mono">${escapeHtml(studentId)}</td>
              </tr>
            </tbody>
          </table>
        `;
      }
    }
    
    htmlContent += `
        <p class="text-xs text-amber-600 bg-amber-50 p-2 rounded-lg">
          ⏱ 自动签到将在 120 分钟内自动关闭
        </p>
      </div>
    `;
  } else {
    // 关闭自动签到的提示
    htmlContent = `
      <div class="text-left">
        <p class="mb-3 text-slate-600 font-semibold">⏸️ 自动签到已关闭</p>
    `;
    
    // 如果有当前用户信息
    if (currentUserData && currentUserData.student_id) {
      if (isMobile) {
        // 移动端：卡片式展示
        htmlContent += `
          <div class="bg-gradient-to-br from-slate-50 to-gray-50 rounded-xl p-3 border border-slate-200 shadow-sm">
            <p class="text-xs text-slate-500 mb-1">当前账号</p>
            <p class="font-semibold text-slate-800">${escapeHtml(userName)}</p>
            <p class="text-sm text-slate-600 font-mono">${escapeHtml(studentId)}</p>
          </div>
        `;
      } else {
        // PC端：表格式展示
        htmlContent += `
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="bg-slate-100">
                <th class="px-3 py-2 text-left border border-slate-200 font-semibold">姓名</th>
                <th class="px-3 py-2 text-left border border-slate-200 font-semibold">学号</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="px-3 py-2 border border-slate-200">${escapeHtml(userName)}</td>
                <td class="px-3 py-2 border border-slate-200 font-mono">${escapeHtml(studentId)}</td>
              </tr>
            </tbody>
          </table>
        `;
      }
    }
    
    htmlContent += `</div>`;
  }
  
  // 显示Swal弹窗
  Swal.fire({
    title: enabled ? "自动签到已开启" : "自动签到已关闭",
    html: htmlContent,
    icon: enabled ? "success" : "info",
    confirmButtonText: "我知道了",
    confirmButtonColor: enabled ? "#22c55e" : "#64748b",
    customClass: {
      popup: isMobile ? "swal2-popup-mobile" : "",
    },
  });
}

/**
 * 显示多账号模式下自动签到开关状态变更提示
 * 当账号列表为空时，提醒用户后续添加的账号也会应用此设置
 * @param {boolean} enabled - 是否开启自动签到
 * @param {boolean} isMobile - 是否为移动端
 */
function showMultiAutoAttendanceToggleAlert(enabled, isMobile) {
  // 检查是否有账号
  const hasAccounts = cachedMultiAccounts && cachedMultiAccounts.length > 0;
  
  let htmlContent = "";
  
  if (enabled) {
    htmlContent = `<div class="text-left">`;
    
    if (!hasAccounts) {
      // 账号列表为空的提示
      htmlContent += `
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-3">
          <p class="text-amber-700 font-semibold mb-1">⚠️ 当前暂无账号</p>
          <p class="text-sm text-amber-600">
            后续添加到账号列表的账号将自动开启自动签到功能。
          </p>
        </div>
      `;
    } else {
      // 显示账号列表
      if (isMobile) {
        // 移动端：卡片式展示
        htmlContent += `<div class="space-y-2 max-h-48 overflow-y-auto mb-3">`;
        cachedMultiAccounts.forEach((account) => {
          htmlContent += `
            <div class="bg-gradient-to-br from-sky-50 to-blue-50 rounded-xl p-2 border border-sky-100">
              <p class="font-semibold text-sm text-slate-800">${escapeHtml(account.name || account.username)}</p>
              <p class="text-xs text-slate-600 font-mono">${escapeHtml(account.username)}</p>
            </div>
          `;
        });
        htmlContent += `</div>`;
      } else {
        // PC端：表格式展示
        htmlContent += `
          <div class="max-h-48 overflow-y-auto mb-3">
            <table class="w-full text-sm border-collapse">
              <thead class="sticky top-0">
                <tr class="bg-slate-100">
                  <th class="px-3 py-2 text-left border border-slate-200 font-semibold">姓名</th>
                  <th class="px-3 py-2 text-left border border-slate-200 font-semibold">账号</th>
                </tr>
              </thead>
              <tbody>
        `;
        cachedMultiAccounts.forEach((account) => {
          htmlContent += `
            <tr>
              <td class="px-3 py-2 border border-slate-200">${escapeHtml(account.name || "-")}</td>
              <td class="px-3 py-2 border border-slate-200 font-mono">${escapeHtml(account.username)}</td>
            </tr>
          `;
        });
        htmlContent += `</tbody></table></div>`;
      }
    }
    
    htmlContent += `
      <p class="text-xs text-amber-600 bg-amber-50 p-2 rounded-lg">
        ⏱ 自动签到将在 120 分钟内自动关闭
      </p>
    </div>`;
  } else {
    htmlContent = `<div class="text-left">`;
    
    if (!hasAccounts) {
      htmlContent += `
        <div class="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <p class="text-slate-600 font-semibold mb-1">⏸️ 自动签到已关闭</p>
          <p class="text-sm text-slate-500">
            当前暂无账号，后续添加的账号不会自动开启签到。
          </p>
        </div>
      `;
    } else {
      htmlContent += `<p class="mb-3 text-slate-600 font-semibold">⏸️ 以下账号的自动签到已关闭</p>`;
      
      if (isMobile) {
        htmlContent += `<div class="space-y-2 max-h-48 overflow-y-auto">`;
        cachedMultiAccounts.forEach((account) => {
          htmlContent += `
            <div class="bg-slate-50 rounded-xl p-2 border border-slate-200">
              <p class="font-semibold text-sm text-slate-800">${escapeHtml(account.name || account.username)}</p>
              <p class="text-xs text-slate-600 font-mono">${escapeHtml(account.username)}</p>
            </div>
          `;
        });
        htmlContent += `</div>`;
      } else {
        htmlContent += `
          <div class="max-h-48 overflow-y-auto">
            <table class="w-full text-sm border-collapse">
              <thead class="sticky top-0">
                <tr class="bg-slate-100">
                  <th class="px-3 py-2 text-left border border-slate-200 font-semibold">姓名</th>
                  <th class="px-3 py-2 text-left border border-slate-200 font-semibold">账号</th>
                </tr>
              </thead>
              <tbody>
        `;
        cachedMultiAccounts.forEach((account) => {
          htmlContent += `
            <tr>
              <td class="px-3 py-2 border border-slate-200">${escapeHtml(account.name || "-")}</td>
              <td class="px-3 py-2 border border-slate-200 font-mono">${escapeHtml(account.username)}</td>
            </tr>
          `;
        });
        htmlContent += `</tbody></table></div>`;
      }
    }
    
    htmlContent += `</div>`;
  }
  
  Swal.fire({
    title: enabled ? "自动签到已开启" : "自动签到已关闭",
    html: htmlContent,
    icon: enabled ? "success" : "info",
    confirmButtonText: "我知道了",
    confirmButtonColor: enabled ? "#22c55e" : "#64748b",
    customClass: {
      popup: isMobile ? "swal2-popup-mobile" : "",
    },
  });
}

function isSessionUUIDInvalid(uuid) {
  return !uuid || uuid.trim() === "" || uuid === "null";
}

function run_code_need_sessionuuid(codeToRun) {
  let isInvalid = isSessionUUIDInvalid(sessionUUID);

  if (isInvalid) {
    logMessage_Warning("sessionUUID 为空，尝试从 URL 中提取");
    sessionUUID = getUUIDFromURL();

    isInvalid = isSessionUUIDInvalid(sessionUUID);

    if (!isInvalid) {
      logMessage_Info("成功从 URL 中提取 sessionUUID: " + sessionUUID);
    }
  }

  if (isInvalid) {
    logMessage_Error("未找到有效的 sessionUUID，所需操作无法执行");
  } else {
    codeToRun();
  }
}

function run_code_not_need_sessionuuid(codeToRun) {
  let isInvalid = isSessionUUIDInvalid(sessionUUID);

  if (isInvalid) {
    logMessage_Warning("sessionUUID 为空，尝试从 URL 中提取");
    sessionUUID = getUUIDFromURL();

    isInvalid = isSessionUUIDInvalid(sessionUUID);

    if (!isInvalid) {
      logMessage_Info("成功从 URL 中提取 sessionUUID: " + sessionUUID);
    }
  }

  if (isInvalid) {
    logMessage_Error("未找到有效的 sessionUUID，所需操作无法执行");
    codeToRun();
  }
}

function showMobileMessage(message, type = "info") {
  // const errorDiv = document.getElementById("mobile-auth-error");
  // const successDiv = document.getElementById("mobile-auth-success");

  if (type === "clear") {
    const modal = $("alert-modal");
    modal.classList.add("hidden");
    return;
  }

  if (type === "error") {
    // showModalAlert(message, "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: message,
    });
  } else if (type === "success") {
    // showModalAlert(message, "成功");
    Swal.fire({
      icon: "success",
      title: "成功",
      text: message,
    });
  } else {
    // showModalAlert(message, "提示");
    Swal.fire({
      icon: "info",
      title: "提示",
      text: message,
    });
  }
}
document.addEventListener("DOMContentLoaded", function () {
  console.log("[页面加载] DOM内容已加载，开始执行设备检测和UI切换");

  switchUIContainer();
  syncThemeBackgroundTarget();

  console.log(
    "[页面加载] 移动端检测和UI切换完成（基于User-Agent，不监听窗口变化）",
  );
});

// ==============移动端设备检测与UI容器切换功能==================

function handleCdnError(resourceName = "未指定") {
  cdnErrorCount++;
  logMessage_Warning(
    `CDN资源[${resourceName}]加载失败 (${cdnErrorCount}/3)，等待应用初始化...`,
  );

  if (cdnErrorTimer) {
    clearTimeout(cdnErrorTimer);
  }

  cdnErrorTimer = setTimeout(() => {
    if (!appInitialized && cdnErrorCount > 0) {
      const errorOverlay = document.getElementById("cdn-error-overlay");
      if (errorOverlay) {
        try {
          errorOverlay.style.setProperty("display", "flex", "important");
        } catch (e) {
          errorOverlay.style.display = "flex";
        }
        errorOverlay.classList.remove("hidden");
        logMessage_Error(
          `应用初始化超时，CDN资源加载失败 (${cdnErrorCount}个资源)`,
        );
      }
    }
  }, 3000);
}

function showModalAlert(message, title = "提示", onCloseCallback = null) {
  // 兼容旧调用，但统一使用 SweetAlert2 的 Swal.fire
  // title: 作为弹窗标题；message: 支持换行
  try {
    const icon = (function (t) {
      if (!t) return undefined;
      if (t.indexOf("成功") !== -1) return "success";
      if (t.indexOf("错误") !== -1 || t.indexOf("失败") !== -1) return "error";
      if (t.indexOf("警告") !== -1) return "warning";
      return "info";
    })(String(title));

    Swal.fire({
      title: String(title || "提示"),
      html: String(message || "").replace(/\n/g, "<br>"),
      icon: icon,
    }).then(() => {
      if (onCloseCallback && typeof onCloseCallback === "function") {
        try {
          onCloseCallback();
        } catch (e) {
          logMessage_Error("showModalAlert 关闭时回调错误: " + e);
        }
      }
    });
  } catch (e) {
    // 如果 Swal 不可用，回退到原生 alert
    alert(`${title}:\n${message}`);
    if (onCloseCallback && typeof onCloseCallback === "function")
      onCloseCallback();
  }
}

function showModal(modalId) {
  const modal = $(modalId);
  if (modal) {
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    document.body.classList.add("modal-visible");
  }
}

function hideModal(modalId) {
  const modal = $(modalId);
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
  const otherModals = document.querySelectorAll('.modal, [id$="-modal"]');
  let stillVisible = false;
  otherModals.forEach((m) => {
    if (
      !m.classList.contains("hidden") &&
      (m.classList.contains("flex") || m.style.display === "flex")
    ) {
      stillVisible = true;
    }
  });
  if (!stillVisible) {
    document.body.classList.remove("modal-visible");
  }
}

let resolveConfirmPromise = null;

function jsShowConfirm(title, message) {
  return new Promise((resolve) => {
    const modal = $("confirm-modal");
    const titleEl = $("confirm-modal-title");
    const msgEl = $("confirm-modal-message");
    const okBtn = $("confirm-modal-ok-btn");
    const cancelBtn = $("confirm-modal-cancel-btn");

    if (!modal || !titleEl || !msgEl || !okBtn || !cancelBtn) {
      logMessage_Error(
        "Confirm modal DOM not found. Falling back to native confirm.",
      );
      resolve(confirm(`${title}:\n${message}`));
      return;
    }

    resolveConfirmPromise = resolve;

    titleEl.textContent = title || "请确认";
    msgEl.innerHTML = String(message).replace(/\n/g, "<br>");

    okBtn.onclick = null;
    cancelBtn.onclick = null;

    okBtn.onclick = () => handleConfirm(true);
    cancelBtn.onclick = () => handleConfirm(false);

    modal.classList.remove("hidden");
    modal.classList.add("flex");
    document.body.classList.add("modal-visible");
  });
}

function handleConfirm(result) {
  const modal = $("confirm-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }

  const otherModals = document.querySelectorAll('.modal, [id$="-modal"]');
  let stillVisible = false;
  otherModals.forEach((m) => {
    if (
      m.id !== "confirm-modal" &&
      !m.classList.contains("hidden") &&
      (m.classList.contains("flex") || m.style.display === "flex")
    ) {
      stillVisible = true;
    }
  });
  if (!stillVisible) {
    document.body.classList.remove("modal-visible");
  }

  if (resolveConfirmPromise) {
    resolveConfirmPromise(result);
    resolveConfirmPromise = null;
  }
}

let AMAP_API_KEY = "";
let isRefreshingNotifications = false;

let isRefreshingTasks = false;

let IS_OFFLINE = null;
let legacyBusinessSession = "";
let legacyBusinessGeneration = 0;

function captureLegacyBusinessContext(modeChange = false) {
  if (legacyBusinessSession !== sessionUUID) {
    legacyBusinessSession = sessionUUID;
    legacyBusinessGeneration++;
    IS_OFFLINE = null;
  }
  if (modeChange) legacyBusinessGeneration++;
  return { session: sessionUUID, generation: legacyBusinessGeneration };
}

function isCurrentLegacyBusinessContext(context) {
  return !!context && context.session === sessionUUID && context.generation === legacyBusinessGeneration;
}

function applyLegacyBusinessMode(data, context) {
  if (!isCurrentLegacyBusinessContext(context) || data?.success === false || typeof data?.is_offline_mode !== "boolean") return false;
  IS_OFFLINE = data.is_offline_mode;
  return true;
}

async function ensureLegacyBusinessMode() {
  const context = captureLegacyBusinessContext();
  if (typeof IS_OFFLINE === "boolean") return IS_OFFLINE;
  const result = await callPythonAPI("get_session_mode_info");
  if (!applyLegacyBusinessMode(result, context)) throw new Error("会话模式尚未确认，请刷新后重试");
  return IS_OFFLINE;
}
let authSessionUUID = null;
let authRequestGeneration = 0;
let authLoginInProgress = false;
let authLogoutInProgress = false;

function isUsableClientSessionUUID(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return false;
  }
  if (["null", "undefined", "none"].includes(normalized.toLowerCase())) {
    return false;
  }
  return /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i.test(
    normalized,
  );
}

const ADMIN_RETURN_ORIGIN_STORAGE_KEY = "admin_return_origin";
const ADMIN_VIEW_ORIGIN_HEADER = "X-Admin-Origin-Session-ID";
let legacyAdminViewContext = null;
let legacyAdminViewRejected = false;

function getLegacyActorIdentity(fallback = {}) {
  return legacyAdminViewContext || fallback;
}

function applyLegacyAdminViewContext(result, requestSession, requestOrigin) {
  if (!requestOrigin || !result || result.success !== true) return;
  if (normalizeClientSessionUUID(requestSession) !== getCurrentLegacySessionUUID()) return;
  if (normalizeClientSessionUUID(requestOrigin) !== getStoredAdminReturnOriginSession()) return;
  const context = result.admin_view_context;
  if (
    context && context.view_all_sessions === true &&
    normalizeClientSessionUUID(context.session_id) === requestOrigin &&
    typeof context.auth_username === "string" && context.auth_username.trim() &&
    typeof context.auth_group === "string" && context.auth_group.trim()
  ) {
    legacyAdminViewContext = { ...context };
    legacyAdminViewRejected = false;
    authSessionUUID = context.session_id;
  } else {
    clearAdminReturnOriginState("来源会话认证已失效");
    legacyAdminViewRejected = true;
  }
}

function normalizeClientSessionUUID(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return isUsableClientSessionUUID(normalized) ? normalized : "";
}

function getStoredAdminReturnOriginSession() {
  try {
    return normalizeClientSessionUUID(
      localStorage.getItem(ADMIN_RETURN_ORIGIN_STORAGE_KEY),
    );
  } catch (_error) {
    return "";
  }
}

function getCurrentLegacySessionUUID() {
  return (
    normalizeClientSessionUUID(sessionUUID) ||
    normalizeClientSessionUUID(getUUIDFromURL())
  );
}

function getAdminViewOriginSessionUUID(currentSessionId = getCurrentLegacySessionUUID()) {
  const originSession = getStoredAdminReturnOriginSession();
  const currentSession = normalizeClientSessionUUID(currentSessionId);
  if (!originSession || !currentSession || originSession === currentSession) {
    return "";
  }
  return originSession;
}

function addAdminViewOriginSessionHeader(headers, currentSessionId) {
  const originSession = getAdminViewOriginSessionUUID(currentSessionId);
  if (originSession) {
    headers[ADMIN_VIEW_ORIGIN_HEADER] = originSession;
  }
  return headers;
}

function isAdminLikeLegacyUser() {
  if (legacyAdminViewContext?.view_all_sessions === true) return true;
  const group = String(
    currentUserData?.group || currentUserData?.auth_group || "",
  ).trim();
  if (group === "admin" || group === "super_admin") {
    return true;
  }
  const permissions =
    currentUserData?.permissions ||
    currentUserData?.all_permissions ||
    currentUserData?.group_permissions ||
    {};
  return Boolean(permissions.view_all_sessions || permissions.manage_user_sessions);
}

function rememberAdminReturnOriginSession() {
  const existingOrigin = getStoredAdminReturnOriginSession();
  if (existingOrigin) {
    return existingOrigin;
  }
  const currentSession = getCurrentLegacySessionUUID();
  if (currentSession) {
    try {
      localStorage.setItem(ADMIN_RETURN_ORIGIN_STORAGE_KEY, currentSession);
    } catch (_error) {
      // Storage failures should not force a token-switching fallback.
    }
  }
  return currentSession;
}

function shouldUseAdminSessionViewMode(targetSessionId, targetUsername = "") {
  const targetSession = normalizeClientSessionUUID(targetSessionId);
  const currentSession = getCurrentLegacySessionUUID();
  if (!targetSession || !currentSession || targetSession === currentSession) {
    return false;
  }
  if (getAdminViewOriginSessionUUID(currentSession)) return true;
  if (!isAdminLikeLegacyUser()) {
    return false;
  }
  const normalizedTargetUsername = String(targetUsername || "").trim();
  const normalizedCurrentUsername = String(currentAuthUsername || "").trim();
  if (
    normalizedTargetUsername &&
    normalizedCurrentUsername &&
    normalizedTargetUsername === normalizedCurrentUsername
  ) {
    return false;
  }
  return true;
}

function ensureAuthLoginSessionUUID() {
  if (isUsableClientSessionUUID(sessionUUID)) {
    return sessionUUID;
  }

  const uuidFromUrl = getUUIDFromURL();
  if (isUsableClientSessionUUID(uuidFromUrl)) {
    return setActiveLegacySession(uuidFromUrl, { promoteAuth: false });
  }

  return null;
}

function getAuthRequestSessionUUID() {
  return isUsableClientSessionUUID(authSessionUUID)
    ? authSessionUUID
    : ensureAuthLoginSessionUUID();
}

function getAuthenticatedSessionHeaderValue() {
  if (legacyAdminViewContext) return legacyAdminViewContext.session_id;
  if (isUsableClientSessionUUID(authSessionUUID)) {
    return authSessionUUID;
  }
  if (isUsableClientSessionUUID(sessionUUID)) {
    return sessionUUID;
  }
  return "";
}

function setActiveLegacySession(sessionId, options = {}) {
  const normalized = String(sessionId || "").trim();
  if (!isUsableClientSessionUUID(normalized)) {
    return "";
  }
  if (sessionUUID !== normalized && typeof resetLegacyRunnerExecution === "function") {
    resetLegacyRunnerExecution();
  }
  sessionUUID = normalized;
  if (options.promoteAuth !== false && !getAdminViewOriginSessionUUID(normalized)) {
    authSessionUUID = normalized;
  }
  try {
    sessionStorage.setItem("session_uuid", normalized);
  } catch (_error) {
    // Storage may be unavailable in restricted browser contexts.
  }
  return normalized;
}

const AUTH_CONTEXT_API_METHODS = new Set(["get_initial_data"]);

function isAuthContextApiMethod(method) {
  return AUTH_CONTEXT_API_METHODS.has(String(method || "").trim());
}

function getApiRequestSessionHeaderValue(method) {
  if (getAdminViewOriginSessionUUID()) return getCurrentLegacySessionUUID();
  if (authLoginInProgress && isUsableClientSessionUUID(authSessionUUID)) {
    return authSessionUUID;
  }

  if (isUsableClientSessionUUID(sessionUUID)) {
    return sessionUUID;
  }

  const uuidFromUrl = getUUIDFromURL();
  if (isUsableClientSessionUUID(uuidFromUrl)) {
    if (!isUsableClientSessionUUID(authSessionUUID)) {
      return setActiveLegacySession(uuidFromUrl, { promoteAuth: false });
    }
  }

  sessionUUID = null;
  if (
    isAuthContextApiMethod(method) &&
    isUsableClientSessionUUID(authSessionUUID)
  ) {
    return authSessionUUID;
  }

  return "";
}

function shouldSuppressLoggedOutElsewhereNotice(
  errorData,
  requestContext,
  currentContext,
) {
  requestContext = requestContext || {};
  currentContext = currentContext || {};

  if (!errorData || !errorData.logged_out_elsewhere) {
    return false;
  }

  if (currentContext.authLoginInProgress) {
    return true;
  }

  const requestGeneration = Number(requestContext.authGeneration || 0);
  const currentGeneration = Number(currentContext.authGeneration || 0);
  if (requestGeneration !== currentGeneration) {
    return true;
  }

  const normalizeSession = (value) => {
    const normalized = String(value || "").trim();
    if (!normalized) {
      return "";
    }
    if (["null", "undefined", "none"].includes(normalized.toLowerCase())) {
      return "";
    }
    return normalized;
  };
  const requestSessionUUID = normalizeSession(requestContext.sessionUUID);
  const currentSessionUUID = normalizeSession(currentContext.sessionUUID);

  if (currentContext.authLoginVisible) {
    return true;
  }

  if (!requestSessionUUID || !currentSessionUUID) {
    return true;
  }

  return Boolean(
    requestSessionUUID &&
      currentSessionUUID &&
      requestSessionUUID !== currentSessionUUID,
  );
}

function shouldSuppressSessionExpiredNotice(
  method,
  requestContext,
  currentContext,
) {
  requestContext = requestContext || {};
  currentContext = currentContext || {};

  if (currentContext.authLoginInProgress || currentContext.authLoginVisible) {
    return true;
  }

  const normalizedMethod = String(method || "").trim();
  if (normalizedMethod === "get_theme_styles" && !requestContext.sessionUUID) {
    return true;
  }

  const normalizeSession = (value) => {
    const normalized = String(value || "").trim();
    if (!normalized) {
      return "";
    }
    if (["null", "undefined", "none"].includes(normalized.toLowerCase())) {
      return "";
    }
    return normalized;
  };

  const requestSessionUUID = normalizeSession(requestContext.sessionUUID);
  const currentSessionUUID = normalizeSession(currentContext.sessionUUID);
  if (!requestSessionUUID || !currentSessionUUID) {
    return true;
  }

  return requestSessionUUID !== currentSessionUUID;
}

function clearLogoutElsewhereOverlay() {
  const overlay = document.getElementById("logout-elsewhere-overlay");
  if (overlay && overlay.parentNode) {
    if (typeof overlay._clearCountdown === "function") overlay._clearCountdown();
    overlay.parentNode.removeChild(overlay);
  }
}

function isAuthLoginViewVisible() {
  const visibleIds = [
    "auth-login-container",
    "mobile-auth-login-container",
    "mobile-auth-container",
    "login-container",
    "mobile-login-container",
  ];

  return visibleIds.some((id) => {
    const element = document.getElementById(id);
    return element && !element.classList.contains("hidden");
  });
}

function getServerConnectionGuidanceMessage() {
  return `

  <div style="
    text-align:left;
    font-size:13px;
    color:#334155;
    line-height:1.6;
  ">

    <div style="
      background:#f8fafc;
      border:1px solid #e2e8f0;
      border-radius:10px;
      padding:10px;
      margin-bottom:10px;
    ">
      <div style="
        font-weight:600;
        color:#0f172a;
        margin-bottom:4px;
      ">
        🔗 连接检查
      </div>
      <div>
        请确认设备已正常联网。
      </div>
    </div>

    <div style="
      background:#fffbeb;
      border:1px solid #fde68a;
      border-radius:10px;
      padding:10px;
      margin-bottom:10px;
    ">
      <div style="
        font-weight:600;
        color:#92400e;
        margin-bottom:4px;
      ">
        ⚠️ 网络访问异常
      </div>

      <div>
        若您位于
        <strong>福建 / 江苏 / 贵州 / 广西</strong>
        ，可能存在运营商网络干扰，可尝试：
      </div>

      <ul style="
        margin:6px 0 0 18px;
        padding:0;
      ">
        <li>切换网络</li>
        <li>启用加密 DNS</li>
        <li>使用国际联网工具</li>
      </ul>
    </div>

    <div style="
      background:#eff6ff;
      border:1px solid #bfdbfe;
      border-radius:10px;
      padding:10px;
      margin-bottom:10px;
    ">
      <div style="
        font-weight:600;
        color:#1d4ed8;
        margin-bottom:4px;
      ">
        🛡️ 本地环境检查
      </div>

      <div>
        请检查是否启用了广告拦截工具、浏览器插件或安全软件。
      </div>
    </div>

    <div style="
      background:#fdf2f8;
      border:1px solid #fbcfe8;
      border-radius:10px;
      padding:10px;
      margin-bottom:10px;
    ">
      <div style="
        font-weight:600;
        color:#be185d;
        margin-bottom:4px;
      ">
        🔄 DNS 刷新
      </div>

      <div>
        <strong>手机：</strong>开关飞行模式并重启浏览器<br>
        <strong>电脑：</strong>刷新 DNS 缓存后重新访问
      </div>
    </div>

    <div style="
      border-top:1px solid #e2e8f0;
      padding-top:10px;
    ">
      <div style="
        font-weight:600;
        color:#0f172a;
        margin-bottom:4px;
      ">
        📋 快速排查
      </div>

      <div>
        ✅ 确认联网<br>
        ✅ 切换网络<br>
        ✅ 关闭拦截工具<br>
        ✅ 刷新 DNS
      </div>

      <div style="
        margin-top:8px;
        font-size:12px;
        color:#64748b;
      ">
        若问题持续存在，请联系支持人员。
      </div>
    </div>

  </div>


  `;
}

function getUUIDFromURL() {
  const urlPath = window.location.pathname;

  const match = urlPath.match(
    /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i,
  );

  if (match && match[1]) {
    return match[1];
  } else {
    return null;
  }
}

async function callPythonAPI(method, ...args) {
  if (isInNetworkErrorState) {
    logMessage_Warning(`[API调用] ✗ 已跳过 (${method}): 网络错误状态已激活`);
    throw new Error("网络连接已断开。");
  }

  logMessage_Info(`[API调用] 方法: ${method}, 参数数量: ${args.length}`);
  const headers = {
    "Content-Type": "application/json",
  };

  const requestSessionHeaderValue = getApiRequestSessionHeaderValue(method);
  const requestAdminOriginSession = getAdminViewOriginSessionUUID(requestSessionHeaderValue);
  if (isUsableClientSessionUUID(requestSessionHeaderValue)) {
    headers["X-Session-ID"] = requestSessionHeaderValue;
    addAdminViewOriginSessionHeader(headers, requestSessionHeaderValue);
    logMessage_Info(`[API调用] 会话ID: ${requestSessionHeaderValue}`);
  } else if (isAuthContextApiMethod(method)) {
    logMessage_Warning(
      `[API调用] ${method} 未找到可用会话，将使用后端只读初始化兜底`,
    );
  } else {
    logMessage_Warning(
      `[API调用] 警告: sessionUUID为空，${method} 可能返回会话无效`,
    );
  }

  const requestAuthContext = {
    authGeneration: authRequestGeneration,
    sessionUUID,
  };

  logMessage_Info(`[API调用] 发送请求到 /api/${method}`);
  let response;
  try {
    response = await fetch(`/api/${method}`, {
      method: "POST",
      headers: headers,
      credentials: "include",
      body: JSON.stringify(
        args.length === 1 &&
          typeof args[0] === "object" &&
          args[0] !== null &&
          !Array.isArray(args[0])
          ? args[0]
          : args,
      ),
    });
  } catch (networkError) {
    logMessage_Error(`[API调用] ✗ 网络请求失败 (${method}):`, networkError);

    if (!networkRetryInProgress) {
      networkRetryInProgress = true;
      logMessage_Info(`[网络] 请求 ${method} 失败，启动 health 探测与重试`);

      const alive = await checkServerHealth();
      if (alive) {
        logMessage_Info("[网络] health 探测成功，服务器仍在运行，开始重试");
        for (let attempt = 1; attempt <= NETWORK_RETRY_MAX; attempt++) {
          await new Promise((r) => setTimeout(r, NETWORK_RETRY_DELAY_MS));
          try {
            response = await fetch(`/api/${method}`, {
              method: "POST",
              headers: headers,
              credentials: "include",
              body: JSON.stringify(
                args.length === 1 &&
                  typeof args[0] === "object" &&
                  args[0] !== null &&
                  !Array.isArray(args[0])
                  ? args[0]
                  : args,
              ),
            });
            logMessage_Info(`[网络] 重试第 ${attempt} 次成功 (${method})`);
            networkRetryInProgress = false;
            break;
          } catch (retryErr) {
            logMessage_Warning(`[网络] 重试第 ${attempt}/${NETWORK_RETRY_MAX} 次失败 (${method})`);
            if (attempt === NETWORK_RETRY_MAX) {
              networkRetryInProgress = false;
              enterNetworkErrorState();
              showNetworkErrorDialog();
              throw retryErr;
            }
          }
        }
      } else {
        logMessage_Error("[网络] health 探测失败，服务器不可达");
        networkRetryInProgress = false;
        enterNetworkErrorState();
        showNetworkErrorDialog();
        throw networkError;
      }
    } else {
      throw networkError;
    }
  }

  if (!response.ok) {
    logMessage_Info(
      `[API调用] ✗ 响应错误: ${response.status} ${response.statusText}`,
    );
    let errorData = null;
    try {
      errorData = await response.json();
    } catch (parseError) {
      logMessage_Warning("[API调用] ✗ 无法解析错误响应体为 JSON:", parseError);
    }

    if (authLogoutInProgress && response.status === 401) {
      throw new Error(errorData?.message || "退出登录中，会话已失效");
    }

    if (
      response.status === 403 &&
      errorData &&
      errorData.message &&
      errorData.message.includes("账号已被封禁")
    ) {
      logMessage_Error("[API调用] ✗ 账号已被封禁！");
      enterNetworkErrorState();

      // 检查遮罩是否已存在，防止重复创建
      if (!document.getElementById("account-banned-overlay")) {
        const bannedOverlay = document.createElement("div");
        bannedOverlay.id = "account-banned-overlay";
        bannedOverlay.style.cssText = `
          position: fixed; top: 0; left: 0; width: 100%; height: 100%;
          background: rgba(0, 0, 0, 0.85); z-index: 9999;
          display: flex; align-items: center; justify-content: center;
        `;

        const modalContent = document.createElement("div");
        modalContent.style.cssText = `
          background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
          padding: 40px;
          border-radius: 20px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
          max-width: 500px;
          width: 90%;
          text-align: center;
          color: white;
          animation: slideIn 0.3s ease-out;
        `;

        const icon = document.createElement("div");
        icon.innerHTML = `
          <svg style="width: 80px; height: 80px; margin: 0 auto 20px; filter: drop-shadow(0 4px 8px rgba(0,0,0,0.2));" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clip-rule="evenodd"/>
          </svg>
        `;

        const title = document.createElement("h2");
        title.textContent = "账号已被封禁";
        title.style.cssText = `
          font-size: 28px; 
          font-weight: bold; 
          margin: 0 0 20px 0;
          text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        `;

        const text = document.createElement("p");
        text.textContent =
          "您的账号已被管理员封禁，无法继续使用该服务。如有疑问，请联系管理员。";
        text.style.cssText = `
          font-size: 16px; 
          line-height: 1.8; 
          margin: 0 0 30px 0; 
          opacity: 0.95;
        `;

        const button = document.createElement("button");
        button.textContent = "返回登录页面";
        button.style.cssText = `
          background: white; 
          color: #f5576c; 
          border: none; 
          padding: 14px 36px;
          border-radius: 25px; 
          font-size: 16px; 
          font-weight: bold; 
          cursor: pointer; 
          transition: all 0.3s;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        button.onmouseover = () => {
          button.style.transform = "translateY(-2px) scale(1.05)";
          button.style.boxShadow = "0 6px 20px rgba(255, 255, 255, 0.4)";
        };
        button.onmouseout = () => {
          button.style.transform = "translateY(0) scale(1)";
          button.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
        };
        button.onclick = () => {
          window.location.href = buildLegacyUiPath("/");
        };

        modalContent.appendChild(icon);
        modalContent.appendChild(title);
        modalContent.appendChild(text);
        modalContent.appendChild(button);
        bannedOverlay.appendChild(modalContent);
        document.body.appendChild(bannedOverlay);
      }

      throw new Error("账号已被封禁。");
    } else if (
      response.status === 401 &&
      errorData &&
      errorData.message &&
      errorData.message.includes("会话已过期或无效")
    ) {
      const shouldSuppressSessionExpiredModal = shouldSuppressSessionExpiredNotice(
        method,
        requestAuthContext,
        {
          authGeneration: authRequestGeneration,
          sessionUUID,
          authLoginInProgress,
          authLoginVisible: isAuthLoginViewVisible(),
        },
      );
      if (shouldSuppressSessionExpiredModal) {
        clearLogoutElsewhereOverlay();
        logMessage_Info(
          `[API调用] ${method} 返回会话失效，但当前处于登录流程中或未登录状态，跳过弹窗`,
        );
        throw new Error("会话已过期或无效");
      }

      logMessage_Error("[API调用] ✗ 会话已过期或无效！");
      logMessage_Info("[系统] 您的会话已过期或无效，请重新登录。");

      if (refreshUserListInterval) {
        logMessage_Info("[API调用] 停止用户列表刷新定时器 (因会话过期)");
        clearInterval(refreshUserListInterval);
        refreshUserListInterval = null;
      }

      if (isMobileMode) {
        showMobileMessage("您的会话已过期或无效，请重新登录", "error");
        if (redirectToLoginAfterSessionExpiry()) {
          throw new Error("会话已过期或无效");
        }

        const mobileMainApp = document.getElementById("mobile-main-app");
        const mobileMultiApp = document.getElementById(
          "mobile-multi-account-app",
        );
        const mobileLoginContainer = document.getElementById(
          "mobile-login-container",
        );

        if (mobileMainApp) mobileMainApp.classList.add("hidden");
        if (mobileMultiApp) mobileMultiApp.classList.add("hidden");
        if (mobileLoginContainer)
          mobileLoginContainer.classList.remove("hidden");

        logMessage_Info("[移动端] 已切换到登录页面");
      } else {
        // ==================== 修改开始：使用全屏遮罩替代简单弹窗 ====================
        // 检查遮罩是否已存在，防止重复创建
        if (!document.getElementById("logout-elsewhere-overlay")) {
          const logoutOverlay = document.createElement("div");
          logoutOverlay.id = "logout-elsewhere-overlay";
          logoutOverlay.style.cssText = `
                  position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                  background: rgba(0, 0, 0, 0.85); z-index: 9999;
                  display: flex; align-items: center; justify-content: center;
                `;

          const modalContent = document.createElement("div");
          modalContent.style.cssText = `
                  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                  padding: 40px;
                  border-radius: 20px;
                  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                  max-width: 500px;
                  width: 90%;
                  text-align: center;
                  color: white;
                `;

          const icon = document.createElement("div");
          icon.innerHTML = `
                  <svg style="width: 80px; height: 80px; margin: 0 auto 20px;" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                  </svg>
                `;

          const title = document.createElement("h2");
          title.textContent = "会话已失效";
          title.style.cssText =
            "font-size: 24px; font-weight: bold; margin: 0 0 20px 0;";

          const text = document.createElement("p");
          text.textContent = "您的会话已过期或无效，为了安全起见请重新登录。";
          text.style.cssText =
            "font-size: 16px; line-height: 1.6; margin: 0 0 30px 0; opacity: 0.95;";

          const countdown = document.createElement("div");
          countdown.style.cssText =
            "font-size: 24px; font-weight: bold; margin: 0 0 30px 0;";

          const button = document.createElement("button");
          button.textContent = "立即返回登录";
          button.style.cssText = `
                  background: white; color: #667eea; border: none; padding: 12px 30px;
                  border-radius: 25px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s;
                `;
          button.onmouseover = () => {
            button.style.transform = "scale(1.05)";
            button.style.boxShadow = "0 5px 15px rgba(255, 255, 255, 0.3)";
          };
          button.onmouseout = () => {
            button.style.transform = "scale(1)";
            button.style.boxShadow = "none";
          };

          modalContent.appendChild(icon);
          modalContent.appendChild(title);
          modalContent.appendChild(text);
          modalContent.appendChild(countdown);
          modalContent.appendChild(button);
          logoutOverlay.appendChild(modalContent);
          document.body.appendChild(logoutOverlay);

          let remainingSeconds = 120; // 设置为120秒倒计时
          const updateCountdown = () => {
            const minutes = Math.floor(remainingSeconds / 60);
            const seconds = remainingSeconds % 60;
            countdown.textContent = `${minutes}:${seconds
              .toString()
              .padStart(2, "0")}`;
          };
          updateCountdown();

          const countdownInterval = setInterval(() => {
            remainingSeconds--;
            updateCountdown();
            if (remainingSeconds <= 0) {
              clearInterval(countdownInterval);
              window.location.href = buildLegacyUiPath("/");
            }
          }, 1000);

          button.onclick = () => {
            clearInterval(countdownInterval);
            window.location.href = buildLegacyUiPath("/");
          };
        }
        // ==================== 修改结束 ====================
      }

      throw new Error("会话已过期或无效");
      return;
    }
    if (errorData && errorData.need_login) {
      let errorMsg = errorData.message || "API调用失败";
      logMessage_Info(`[API调用] ✗ 需要重新登录: ${errorMsg}`);

      if (errorData.logged_out_elsewhere) {
        if (
          shouldSuppressLoggedOutElsewhereNotice(
            errorData,
            requestAuthContext,
            {
              authGeneration: authRequestGeneration,
              sessionUUID,
              authLoginInProgress,
              authLoginVisible: isAuthLoginViewVisible(),
            },
          )
        ) {
          clearLogoutElsewhereOverlay();
          logMessage_Info(
            "[安全提示] 已忽略登录过程中的旧多设备登出响应",
          );
          return {
            success: false,
            stale_auth_response: true,
            suppressed: true,
            message: errorMsg,
          };
        }

        // ==================== 修复开始 ====================
        // 检查遮罩是否已存在，防止重复创建和倒计时重置
        if (document.getElementById("logout-elsewhere-overlay")) {
          return;
        }
        // ==================== 修复结束 ====================

        logMessage_Info("[安全提示] 检测到账号在其他设备登录，已自动登出");
        logMessage_Info("[API调用] ✗ 多设备登录检测");

        const logoutOverlay = document.createElement("div");
        logoutOverlay.id = "logout-elsewhere-overlay";
        logoutOverlay.style.cssText = `
                          position: fixed;
                          top: 0;
                          left: 0;
                          width: 100%;
                          height: 100%;
                          background: rgba(0, 0, 0, 0.85);
                          z-index: 20002; /* 修正：提升层级以覆盖移动端容器 */
                          display: flex;
                          align-items: center;
                          justify-content: center;
                        `;

        const modalContent = document.createElement("div");
        modalContent.style.cssText = `
                          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                          padding: 40px;
                          border-radius: 20px;
                          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                          max-width: 500px;
                          width: 90%;
                          text-align: center;
                          color: white;
                        `;

        const icon = document.createElement("div");
        icon.innerHTML = `
                          <svg style="width: 80px; height: 80px; margin: 0 auto 20px;" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
                          </svg>
                        `;

        const title = document.createElement("h2");
        title.textContent = "多设备登录检测";
        title.style.cssText = `
                          font-size: 24px;
                          font-weight: bold;
                          margin: 0 0 20px 0;
                        `;

        const text = document.createElement("p");
        text.textContent =
          "您的账号已在其他设备登录，本设备已自动登出。2分钟后将自动跳转到登录页面。";
        text.style.cssText = `
                          font-size: 16px;
                          line-height: 1.6;
                          margin: 0 0 30px 0;
                          opacity: 0.95;
                        `;

        const countdown = document.createElement("div");
        countdown.style.cssText = `
                          font-size: 32px;
                          font-weight: bold;
                          margin: 0 0 30px 0;
                        `;

        const button = document.createElement("button");
        button.textContent = "立即返回登录";
        button.style.cssText = `
                          background: white;
                          color: #667eea;
                          border: none;
                          padding: 12px 30px;
                          border-radius: 25px;
                          font-size: 16px;
                          font-weight: bold;
                          cursor: pointer;
                          transition: all 0.3s;
                        `;
        button.onmouseover = () => {
          button.style.transform = "scale(1.05)";
          button.style.boxShadow = "0 5px 15px rgba(255, 255, 255, 0.3)";
        };
        button.onmouseout = () => {
          button.style.transform = "scale(1)";
          button.style.boxShadow = "none";
        };

        modalContent.appendChild(icon);
        modalContent.appendChild(title);
        modalContent.appendChild(text);
        modalContent.appendChild(countdown);
        modalContent.appendChild(button);
        logoutOverlay.appendChild(modalContent);
        document.body.appendChild(logoutOverlay);

        let remainingSeconds = 120;
        const updateCountdown = () => {
          const minutes = Math.floor(remainingSeconds / 60);
          const seconds = remainingSeconds % 60;
          countdown.textContent = `${minutes}:${seconds
            .toString()
            .padStart(2, "0")}`;
        };
        updateCountdown();

        const countdownInterval = setInterval(() => {
          remainingSeconds--;
          updateCountdown();

          if (remainingSeconds <= 0) {
            clearInterval(countdownInterval);
            window.location.href = buildLegacyUiPath("/");
          }
        }, 1000);

        // 修正：移除用户活动监听，强制执行倒计时
        button.onclick = () => {
          clearInterval(countdownInterval);
          window.location.href = buildLegacyUiPath("/");
        };
      } else {
        logMessage_Info(`[安全提示] ${errorMsg}`);

        // if (isMobileMode) {
        //   showMobileMessage(errorMsg || "需要重新登录", "error");

        //   const mobileMainApp = document.getElementById("mobile-main-app");
        //   const mobileMultiApp = document.getElementById(
        //     "mobile-multi-account-app"
        //   );
        //   const mobileLoginContainer = document.getElementById(
        //     "mobile-login-container"
        //   );

        //   if (mobileMainApp) mobileMainApp.classList.add("hidden");
        //   if (mobileMultiApp) mobileMultiApp.classList.add("hidden");
        //   if (mobileLoginContainer)
        //     mobileLoginContainer.classList.remove("hidden");

        //   logMessage_Info("[移动端] 已切换到登录页面（因need_login）");
        // } else {
        Swal.fire({
          icon: "warning",
          title: "需要重新登录",
          text: errorMsg,
          confirmButtonText: "返回登录",
          allowOutsideClick: false,
          allowEscapeKey: false,
        }).then((result) => {
          if (result.isConfirmed) {
            window.location.href = buildLegacyUiPath("/");
          }
        });
        // }
      }

      if (refreshUserListInterval) {
        logMessage_Info("[API调用] 停止用户列表刷新定时器 (因需重新登录)");
        clearInterval(refreshUserListInterval);
        refreshUserListInterval = null;
      }

      throw new Error(errorMsg);
    }

    if (response.status === 403 && errorData && errorData.message) {
      logMessage_Error(
        `[API调用] ✗ 权限不足 (${method}): ${errorData.message}`,
      );
      // showModalAlert(`操作失败: ${errorData.message}`, "权限不足");
      Swal.fire({
        icon: "error",
        title: "权限不足",
        text: `操作失败: ${errorData.message}`,
      });
      throw new Error(`权限不足: ${errorData.message}`);
    }

    const genericErrorMessage =
      errorData && errorData.message ? errorData.message : response.statusText;
    logMessage_Error(
      `[API调用] ✗ 未处理的错误 (${method}): ${genericErrorMessage}`,
    );
    throw new Error(`API调用失败 (${response.status}): ${genericErrorMessage}`);
  }

  logMessage_Info(`[API调用] ✓ 请求成功 (${method})`);
  const result = await response.json();
  if (method === "get_initial_data") {
    if (
      normalizeClientSessionUUID(requestSessionHeaderValue) !==
        normalizeClientSessionUUID(getApiRequestSessionHeaderValue(method)) ||
      requestAdminOriginSession !== getAdminViewOriginSessionUUID(requestSessionHeaderValue)
    ) {
      throw new Error("会话已切换，已忽略旧会话响应");
    }
    applyLegacyAdminViewContext(
      result, requestSessionHeaderValue, requestAdminOriginSession,
    );
  }
  logMessage_Info(
    `[API调用] ✓ 返回结果 (${method}):`,
    result.success ? "成功" : "失败",
  );
  if (method === "get_initial_data" && typeof displayRoutePlanningFailures === "function") {
    displayRoutePlanningFailures(result.route_planning_failures);
  }
  return result;
}

async function callPythonAPI_raw(path, method = "POST", data = null) {
  const headers = {
    "Content-Type": "application/json",
  };

  if (sessionUUID) {
    headers["X-Session-ID"] = sessionUUID;
  }

  // 管理员查看态（上帝模式）：每个 API 请求都要带上来源会话，
  // 否则后端无法识别查看态，来源会话也收不到"仍在使用"的续期信号。
  addAdminViewOriginSessionHeader(headers, sessionUUID);

  const options = {
    method: method,
    headers: headers,
    credentials: "include",
  };

  if (data && method !== "GET") {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(path, options);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    if (headers["X-Session-ID"] !== sessionUUID) return { success: false };
    if (path === "/api/background_task/status" && typeof displayRoutePlanningFailures === "function") {
      displayRoutePlanningFailures(result.task_status?.route_planning_failures);
    }
    return result;
  } catch (error) {
    logMessage_Error(`API调用失败 (${path}):`, error);
    throw error;
  }
}

let singleProcessedPoints = 0;
let singleTotalPoints = 0;

let AMapInstance, map;
let amapLoadingPromise = null;
let AMapReady = false;
let tencentMapLoadingPromise = null;
let tiandituMapLoadingPromise = null;
let baiduMapLoadingPromise = null;
let providerMapInstances = {};
let providerMapInstanceProviders = {};
let providerMapEventsBound = {};
let providerMapOverlays = {};
let providerMapLastFitCoords = {};
let providerRunnerMarkers = {};

let currentTasks = [];
let selectedTaskIndex = -1;
let selectedHistoryTrid = null;
let currentUserData = {};
let currentRunData = {};
let polylines = {
  recommended: [],
  draft: null,
  run: null,
  history: null,
};
let markers = [];
let runnerMarker = null;
let drawingInfoMarker = null;
let singleRunProgressVisualActive = false;
let tempAttendanceMarker = null;
let tempAttendanceCircle = null;
let isDrawing = false;
let isPathDrawing = false;
let leftMouseDown = false;
const $ = (id) => document.getElementById(id);

// 高德运行路线分段缓存：{ lines, segments }，供就地着色更新复用
let amapRouteProgressSegments = null;
let multiAccountMap;
let multiAccountMarkers = {};
let multiAccountMarkerColors = {};
const userColors = [
  "#F44336",
  "#E91E63",
  "#9C27B0",
  "#673AB7",
  "#3F51B5",
  "#2196F3",
  "#03A9F4",
  "#00BCD4",
  "#009688",
  "#4CAF50",
  "#8BC34A",
  "#CDDC39",
  "#FFEB3B",
  "#FFC107",
  "#FF9800",
  "#FF5722",
];
let colorIndex = 0;
let path_planning_queue = [];
let is_planning_path = false;

let currentSessionUA = "";

let pendingMultiPositions = [];

let mapReadyPromise = null;
let resolveMapReady = null;

const paramDefs = {
  interval_ms: {
    label: "采样间隔",
    unit: "ms",
    help: "相邻 GPS 点之间的时间间隔，用于模拟上报节奏。",
  },
  interval_random_ms: {
    label: "间隔随机范围",
    unit: "ms",
    help: "在采样间隔的基础上上下浮动的随机抖动幅度。",
  },
  speed_mps: {
    label: "平均速度",
    unit: "m/s",
    help: "生成/处理路径时的目标平均速度。",
  },
  speed_random_mps: {
    label: "速度随机范围",
    unit: "m/s",
    help: "速度的上下浮动范围，用于模拟自然波动。",
  },
  location_random_m: {
    label: "定位随机偏移半径",

    unit: "m",
    help: "对每个 GPS 点施加的随机偏移的半径，模拟定位噪声。",
  },

  task_gap_min_s: {
    label: "任务间隙下限",
    unit: "s",
    help: "确认还有下一个可执行任务后，两个任务之间的最短等待时间（默认 600 秒）。",
  },
  task_gap_max_s: {
    label: "任务间隙上限",
    unit: "s",
    help: "确认还有下一个可执行任务后，两个任务之间的最长等待时间（默认 1800 秒）。",
  },

  api_fallback_line: {
    label: "规划失败时使用直线连接",
    unit: "",
    help: "启用后，当某段步行路径规划失败时，使用起终点直线代替。",
  },
  api_retries: {
    label: "API重试次数",
    unit: "次",
    help: "步行路径每一段失败后的重试次数。",
  },

  api_retry_delay_s: {
    label: "API重试间隔",
    unit: "s",
    help: "步行路径失败后发起下一次重试前的等待时间。",
  },
  api_queue_interval_s: {
    label: "API排队间隔",
    unit: "s",
    help: "批量规划多段路径时，相邻请求发起之间的排队间隔。",
  },
  ignore_task_time: {
    label: "忽略任务时间仅对比日期",
    unit: "",
    help: "勾选后，判断任务是否“未开始”或“已过期”时，只对比年月日，忽略具体时分秒。",
  },

  min_time_m: {
    label: "目标时长下限",
    unit: "分钟",
    help: "自动生成路径的总时长最小值。",
  },
  max_time_m: {
    label: "目标时长上限",
    unit: "分钟",
    help: "自动生成路径的总时长最大值。",
  },
  min_dist_m: {
    label: "目标距离下限",
    unit: "m",
    help: "自动生成路径的总距离下限。上限按 1.0–1.15 倍随机浮动。",
  },

  theme_style: {
    label: "界面主题风格",
    unit: "",
    help: "切换应用界面的外观。主题切换后将自动保存。",
    type: "theme_selector",
  },
  theme_base_color: {
    label: "主题基础颜色",
    unit: "",
    help: "界面主色调（点击颜色块进行选择）。",
    type: "color_picker",
  },
  auto_attendance_enabled: {
    label: "开启自动签到",
    unit: "",
    help: "开启后，将在后台自动刷新通知并尝试签到",
    type: "checkbox",
  },
  auto_attendance_stop_after_success: {
    label: "完成指定次数后自动关闭",
    unit: "",
    help: "勾选后，后台成功提交指定次数的新签到任务就会自动关闭自动签到。",
    type: "checkbox",
  },
  auto_attendance_success_limit: {
    label: "自动关闭次数",
    unit: "次",
    help: "达到该成功签到次数后自动关闭，最小值为1。",
    type: "number",
    min: 1,
  },
  auto_attendance_refresh_s: {
    label: "刷新间隔",
    unit: "秒",
    help: "自动刷新通知的间隔时间（秒），最小10秒",
  },
  attendance_user_radius_m: {
    label: "随机半径",
    unit: "米",
    help: "自动签到时，在服务器允许范围内的最大随机偏移半径。设为0为精确签到。",
  },
};

const paramGroups = [
  {
    title: "采样与速度",
    keys: [
      "interval_ms",
      "interval_random_ms",
      "speed_mps",
      "speed_random_mps",
      "location_random_m",
    ],
  },
  {
    title: "任务间隔",
    keys: ["task_gap_min_s", "task_gap_max_s", "ignore_task_time"],
  },
  {
    title: "路径规划重试策略",
    keys: [
      "api_fallback_line",
      "api_retries",
      "api_retry_delay_s",
      "api_queue_interval_s",
    ],
  },
  {
    title: "自动生成目标",
    keys: ["min_time_m", "max_time_m", "min_dist_m"],
  },
  {
    title: "自动签到",
    keys: [
      "auto_attendance_enabled",
      "auto_attendance_stop_after_success",
      "auto_attendance_success_limit",
      "auto_attendance_refresh_s",
      "attendance_user_radius_m",
    ],
  },
];

let pythonParams = {};
let currentThemeConfig = {};
let currentThemeBackgroundAssignment = null;
let availableThemeStyles = [];

let cachedMultiAccounts = [];
let activeExpandedMultiAccountRefresh = null;

let runAccumulatedMs = 0;
let draftTotalDist = 0;



function updateMultiGlobalButtons(startDisabled, stopDisabled) {
  const startBtn = document.getElementById("multi-start-all-btn");
  const stopBtn = document.getElementById("multi-stop-all-btn");
  if (!startBtn || !stopBtn) return;
  startBtn.disabled = !!startDisabled;
  stopBtn.disabled = !!stopDisabled;
}

function safeResizeAndFitView() {
  try {
    map.resize();
    requestAnimationFrame(() => {
      resetMapView();
      if (markers.length > 0) {
        map.setFitView(markers, false, [50, 50, 50, 50]);
      }
    });
  } catch (e) {
    logMessage_Warning("safeResizeAndFitView error:", e);
  }
}



function applyThemeGlobalEnvironmentVariables(themeConfig, options = {}) {
  const config = mergeThemeBackgroundConfig(currentThemeConfig, themeConfig);
  const env =
    config.global_environment_variables &&
    typeof config.global_environment_variables === "object"
      ? config.global_environment_variables
      : {};

  currentThemeConfig = config;
  window.themeConfig = config;
  window.themeGlobalEnvironmentVariables = env;

  Object.keys(window).forEach((key) => {
    if (key.startsWith("themeEnv_")) {
      try {
        delete window[key];
      } catch (_) {}
    }
  });

  Object.entries(env).forEach(([key, value]) => {
    if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)) return;
    window[`themeEnv_${key}`] = value;
  });

  applyThemeLoginContainerStyle(config, options);
  scheduleThemeBackgroundConsumed();
}

function mergeThemeBackgroundConfig(previousConfig, nextConfig) {
  const previous = previousConfig && typeof previousConfig === "object" ? previousConfig : {};
  const next = nextConfig && typeof nextConfig === "object" ? nextConfig : {};
  const previousEnv = previous.global_environment_variables && typeof previous.global_environment_variables === "object"
    ? previous.global_environment_variables
    : {};
  const nextEnv = next.global_environment_variables && typeof next.global_environment_variables === "object"
    ? next.global_environment_variables
    : {};
  const mergedEnv = { ...nextEnv };
  ["auth_login_container_background", "mobile_auth_login_content_background"].forEach((key) => {
    if (!String(mergedEnv[key] || "").trim() && String(previousEnv[key] || "").trim()) {
      mergedEnv[key] = previousEnv[key];
    }
  });
  const nextStyleId = String(next.basic_information?.id || previous.basic_information?.id || "default").trim();
  if (nextStyleId === "default") {
    for (const [target, key] of [
      ["pc", "auth_login_container_background"],
      ["mobile", "mobile_auth_login_content_background"],
    ]) {
      const assignedUrl = String(currentThemeBackgroundAssignment?.[target]?.image_url || "").trim();
      if (!assignedUrl) continue;
      const previousBackground = String(previousEnv[key] || "");
      mergedEnv[key] = extractThemeBackgroundImageUrl(previousBackground) === assignedUrl
        ? previousBackground
        : `url("${assignedUrl}") center / cover no-repeat${target === "pc" ? " fixed" : ""}`;
    }
  }
  return { ...previous, ...next, global_environment_variables: mergedEnv };
}

let currentThemeBackgroundTarget = null;
let currentThemeBackgroundImageUrl = "";
let themeBackgroundLoginSyncInFlight = false;
let themeBackgroundFeedbackInFlight = false;
let activeThemeBackgroundFeedback = null;
let pendingThemeBackgroundFeedback = null;
let themeBackgroundConsumeDebounceTimer = null;
const THEME_BACKGROUND_CONSUME_DEBOUNCE_MS = 300;
let initialConsumeCompleted = false;
let themeBackgroundAuthStateResolved = false;
let themeBackgroundAuthenticatedSession = false;
const sessionBindEnsured = { pc: false, mobile: false };
const anonConsumedBackgroundByTarget = { pc: "", mobile: "" };
const preLoginBackgroundSnapshot = { pc: "", mobile: "" };
const initialLoadBackgroundCandidateByTarget = { pc: "", mobile: "" };
const themeBackgroundRequestCache = new Set();
let themeBackgroundInitialLoadSettled =
  typeof document !== "undefined" && document.readyState === "complete";
if (typeof window !== "undefined") {
  window.addEventListener("load", () => {
    themeBackgroundInitialLoadSettled = true;
    scheduleThemeBackgroundConsumed();
  });
}

function applyThemeBackgroundAssignment(assignment, options = {}) {
  if (!assignment || typeof assignment !== "object") return false;
  const pcUrl = String(assignment.pc?.image_url || "").trim();
  const mobileUrl = String(assignment.mobile?.image_url || "").trim();
  if (!pcUrl && !mobileUrl) return false;
  currentThemeBackgroundAssignment = assignment;
  const env = {
    ...(currentThemeConfig?.global_environment_variables || {}),
  };
  if (pcUrl) {
    env.auth_login_container_background = `linear-gradient(rgba(255,255,255,0.10), rgba(255,255,255,0.10)), url("${pcUrl}") center / cover no-repeat fixed`;
  }
  if (mobileUrl) {
    env.mobile_auth_login_content_background = `linear-gradient(rgba(255,255,255,0.12), rgba(255,255,255,0.12)), url("${mobileUrl}") center / cover no-repeat`;
  }
  currentThemeConfig = { ...(currentThemeConfig || {}), global_environment_variables: env };
  if (options.bound === true) {
    if (pcUrl) sessionBindEnsured.pc = true;
    if (mobileUrl) sessionBindEnsured.mobile = true;
    initialConsumeCompleted = true;
    preLoginBackgroundSnapshot.pc = "";
    preLoginBackgroundSnapshot.mobile = "";
  }
  applyThemeLoginContainerStyle(currentThemeConfig, { skipVisualRewrite: true });
  return true;
}

function getCurrentThemeBackgroundTarget() {
  return isMobileMode ? "mobile" : "pc";
}

function getThemeBackgroundImageUrlByTarget(target) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const env =
    currentThemeConfig &&
    currentThemeConfig.global_environment_variables &&
    typeof currentThemeConfig.global_environment_variables === "object"
      ? currentThemeConfig.global_environment_variables
      : {};
  return normalizedTarget === "mobile"
    ? extractThemeBackgroundImageUrl(env.mobile_auth_login_content_background || "")
    : extractThemeBackgroundImageUrl(env.auth_login_container_background || "");
}

function getThemeBackgroundRequestCacheKey(target, imageUrl, isLoggedIn) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const userScope = isLoggedIn && sessionUUID ? `session:${sessionUUID}` : "anon";
  return `${userScope}|${normalizedTarget}|${imageUrl || ""}`;
}

function getRenderedThemeBackgroundImageUrlByTarget(target) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const sourceElement =
    normalizedTarget === "mobile"
      ? document.getElementById("mobile-content")
      : document.getElementById("auth-login-container");

  if (!sourceElement) {
    return "";
  }

  const inlineBackgroundImage = sourceElement.style?.backgroundImage || "";
  const inlineBackground = sourceElement.style?.background || "";
  const computedBackgroundImage = window.getComputedStyle(sourceElement).backgroundImage || "";

  return (
    extractThemeBackgroundImageUrl(inlineBackgroundImage) ||
    extractThemeBackgroundImageUrl(inlineBackground) ||
    extractThemeBackgroundImageUrl(computedBackgroundImage) ||
    ""
  );
}

function capturePreLoginBackgroundSnapshot(preferredTarget = null) {
  const normalizedTarget = preferredTarget === "mobile" ? "mobile" : "pc";
  const renderedImageUrl = getRenderedThemeBackgroundImageUrlByTarget(normalizedTarget);
  const imageUrl = renderedImageUrl || getThemeBackgroundImageUrlByTarget(normalizedTarget);
  if (imageUrl) {
    preLoginBackgroundSnapshot[normalizedTarget] = imageUrl;
  }
}

function getThemeBackgroundFeedbackMode(params) {
  const normalizedParams = params && typeof params === "object" ? params : {};
  const sessionId = Object.prototype.hasOwnProperty.call(normalizedParams, "sessionId")
    ? normalizedParams.sessionId
    : sessionUUID;
  const authStateResolved = Object.prototype.hasOwnProperty.call(normalizedParams, "authStateResolved")
    ? normalizedParams.authStateResolved
    : themeBackgroundAuthStateResolved;
  const isAuthenticated = Object.prototype.hasOwnProperty.call(normalizedParams, "isAuthenticated")
    ? normalizedParams.isAuthenticated
    : themeBackgroundAuthenticatedSession;
  const isGuest = Object.prototype.hasOwnProperty.call(normalizedParams, "isGuest")
    ? normalizedParams.isGuest
    : currentUserIsGuest;
  const normalizedSessionId = typeof sessionId === "string" ? sessionId.trim() : "";
  const hasSessionId = !!(normalizedSessionId && normalizedSessionId !== "null");
  if (!hasSessionId) {
    return "public";
  }
  if (!authStateResolved) {
    return "defer";
  }
  if (isAuthenticated && !isGuest) {
    return "session";
  }
  return "defer";
}

function scheduleThemeBackgroundConsumed() {
  const target = getCurrentThemeBackgroundTarget();
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const imageUrl = getThemeBackgroundImageUrlByTarget(normalizedTarget);
  if (!imageUrl) {
    return;
  }

  if (shouldSkipThemeBackgroundConsumeDuringLogin(normalizedTarget, imageUrl)) {
    return;
  }

  if (!initialLoadBackgroundCandidateByTarget[normalizedTarget]) {
    initialLoadBackgroundCandidateByTarget[normalizedTarget] = imageUrl;
  }

  const isLoggedIn = !!sessionUUID;
  const cacheKey = getThemeBackgroundRequestCacheKey(
    normalizedTarget,
    imageUrl,
    isLoggedIn,
  );
  if (themeBackgroundRequestCache.has(cacheKey)) {
    return;
  }
  if (!isLoggedIn) {
    if (!themeBackgroundInitialLoadSettled || initialConsumeCompleted) {
      return;
    }
    const initialCandidate = initialLoadBackgroundCandidateByTarget[normalizedTarget];
    if (initialCandidate && imageUrl !== initialCandidate) {
      return;
    }
  } else if (sessionBindEnsured[normalizedTarget]) {
    return;
  }

  if (
    activeThemeBackgroundFeedback &&
    activeThemeBackgroundFeedback.target === normalizedTarget &&
    activeThemeBackgroundFeedback.imageUrl === imageUrl
  ) {
    return;
  }

  if (themeBackgroundConsumeDebounceTimer) {
    clearTimeout(themeBackgroundConsumeDebounceTimer);
  }
  themeBackgroundConsumeDebounceTimer = setTimeout(() => {
    themeBackgroundConsumeDebounceTimer = null;
    notifyThemeBackgroundConsumed(normalizedTarget, imageUrl);
  }, THEME_BACKGROUND_CONSUME_DEBOUNCE_MS);
}

async function notifyThemeBackgroundConsumed(target, imageUrlOverride = null) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const imageUrl =
    typeof imageUrlOverride === "string" && imageUrlOverride
      ? imageUrlOverride
      : getThemeBackgroundImageUrlByTarget(normalizedTarget);

  if (!imageUrl) {
    return;
  }

  if (shouldSkipThemeBackgroundConsumeDuringLogin(normalizedTarget, imageUrl)) {
    return;
  }

  const feedbackMode = getThemeBackgroundFeedbackMode();
  if (feedbackMode === "defer") {
    return;
  }

  const isLoggedIn = feedbackMode === "session";
  const cacheKey = getThemeBackgroundRequestCacheKey(
    normalizedTarget,
    imageUrl,
    isLoggedIn,
  );
  if (themeBackgroundRequestCache.has(cacheKey)) {
    return;
  }
  if (!isLoggedIn && (!themeBackgroundInitialLoadSettled || initialConsumeCompleted)) {
    return;
  }
  if (!isLoggedIn) {
    const initialCandidate = initialLoadBackgroundCandidateByTarget[normalizedTarget];
    if (initialCandidate && imageUrl !== initialCandidate) {
      return;
    }
  }
  if (isLoggedIn && sessionBindEnsured[normalizedTarget]) {
    return;
  }

  if (themeBackgroundFeedbackInFlight) {
    if (!isLoggedIn) {
      return;
    }
    if (
      activeThemeBackgroundFeedback &&
      activeThemeBackgroundFeedback.target === normalizedTarget &&
      activeThemeBackgroundFeedback.imageUrl === imageUrl
    ) {
      return;
    }
    pendingThemeBackgroundFeedback = { target: normalizedTarget, imageUrl };
    return;
  }

  if (
    currentThemeBackgroundTarget === normalizedTarget &&
    currentThemeBackgroundImageUrl === imageUrl &&
    ((!isLoggedIn && initialConsumeCompleted) ||
      (isLoggedIn && sessionBindEnsured[normalizedTarget]))
  ) {
    return;
  }

  themeBackgroundFeedbackInFlight = true;
  themeBackgroundRequestCache.add(cacheKey);
  activeThemeBackgroundFeedback = { target: normalizedTarget, imageUrl };

  try {
    let result = null;
    if (feedbackMode === "session") {
      const payload = {
        target: normalizedTarget,
        image_url: imageUrl,
        login_context: !sessionBindEnsured[normalizedTarget],
      };
      const snapshotCandidate = preLoginBackgroundSnapshot[normalizedTarget];
      const candidateImage =
        snapshotCandidate || anonConsumedBackgroundByTarget[normalizedTarget];
      if (payload.login_context && snapshotCandidate) {
        payload.image_url = snapshotCandidate;
      }
      if (payload.login_context && candidateImage) {
        payload.candidate_image_url = candidateImage;
      }
      result = await callPythonAPI("mark_theme_background_consumed", payload);
    } else {
      const response = await fetch("/api/public/theme_background/consume", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ target: normalizedTarget, image_url: imageUrl }),
      });
      if (!response.ok) {
        throw new Error(`HTTP错误: ${response.status}`);
      }
      result = await response.json();
    }

    if (result && result.success) {
      currentThemeBackgroundTarget = normalizedTarget;
      currentThemeBackgroundImageUrl = imageUrl;
      if (feedbackMode === "session") {
        sessionBindEnsured[normalizedTarget] = true;
        preLoginBackgroundSnapshot[normalizedTarget] = "";
      } else {
        initialConsumeCompleted = true;
        anonConsumedBackgroundByTarget[normalizedTarget] = imageUrl;
        initialLoadBackgroundCandidateByTarget[normalizedTarget] = imageUrl;
      }
      if (isLoggedIn && result.theme_config && typeof result.theme_config === "object") {
        currentThemeConfig = result.theme_config;
        applyThemeLoginContainerStyle(currentThemeConfig, {
          skipVisualRewrite: themeBackgroundLoginSyncInFlight,
        });
      }
    }
  } catch (e) {
    themeBackgroundRequestCache.delete(cacheKey);
    logMessage_Warning("[主题] 上报已使用背景失败:", e);
  } finally {
    themeBackgroundFeedbackInFlight = false;
    activeThemeBackgroundFeedback = null;
    if (pendingThemeBackgroundFeedback) {
      const nextFeedback = pendingThemeBackgroundFeedback;
      pendingThemeBackgroundFeedback = null;
      notifyThemeBackgroundConsumed(nextFeedback.target, nextFeedback.imageUrl);
    }
  }
}

function extractThemeBackgroundImageUrl(backgroundValue) {
  const normalizedValue = typeof backgroundValue === "string" ? backgroundValue : "";
  const match = normalizedValue.match(/url\(["']?(\/theme-assets\/[^"')]+)["']?\)/i);
  return match && match[1] ? match[1] : "";
}

function syncThemeBackgroundTarget() {
  scheduleThemeBackgroundConsumed();
}

window.addEventListener("resize", syncThemeBackgroundTarget);

let pcThemeBackgroundContextMenuInitialized = false;
let pcThemeBackgroundContextMenuElement = null;

function shouldEnablePcThemeBackgroundContextMenu(params) {
  const normalizedParams = params && typeof params === "object" ? params : {};
  const target = normalizedParams.target;
  const imageUrl = normalizedParams.imageUrl;
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const normalizedImageUrl = typeof imageUrl === "string" ? imageUrl.trim() : "";
  return normalizedTarget === "pc" && !!normalizedImageUrl;
}

function buildThemeBackgroundDownloadFilename(imageUrl) {
  const now = new Date();
  const pad2 = (value) => String(value).padStart(2, "0");
  const timestamp = `${now.getFullYear()}${pad2(now.getMonth() + 1)}${pad2(now.getDate())}-${pad2(now.getHours())}${pad2(now.getMinutes())}${pad2(now.getSeconds())}`;
  const normalizedImageUrl = typeof imageUrl === "string" ? imageUrl.trim() : "";
  const withoutQuery = normalizedImageUrl.split("?")[0].split("#")[0];
  const extensionMatch = withoutQuery.match(/\.(jpg|jpeg|png|webp|gif|bmp|svg)$/i);
  const extension = extensionMatch ? `.${extensionMatch[1].toLowerCase()}` : ".jpg";
  return `pc-theme-background-${timestamp}${extension}`;
}

function hidePcThemeBackgroundContextMenu() {
  if (pcThemeBackgroundContextMenuElement) {
    pcThemeBackgroundContextMenuElement.style.display = "none";
    pcThemeBackgroundContextMenuElement.dataset.imageUrl = "";
  }
}

function triggerPcThemeBackgroundDownload(imageUrl) {
  const normalizedImageUrl = typeof imageUrl === "string" ? imageUrl.trim() : "";
  if (!normalizedImageUrl) {
    return;
  }
  const normalizedHref = /^https?:\/\//i.test(normalizedImageUrl)
    ? normalizedImageUrl
    : `${window.location.origin}${normalizedImageUrl.startsWith("/") ? "" : "/"}${normalizedImageUrl}`;
  const link = document.createElement("a");
  link.href = normalizedHref;
  link.download = buildThemeBackgroundDownloadFilename(normalizedImageUrl);
  link.rel = "noopener";
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function ensurePcThemeBackgroundContextMenuElement() {
  if (pcThemeBackgroundContextMenuElement) {
    return pcThemeBackgroundContextMenuElement;
  }
  const menu = document.createElement("div");
  menu.id = "pc-theme-background-context-menu";
  menu.style.position = "fixed";
  menu.style.display = "none";
  menu.style.minWidth = "150px";
  menu.style.padding = "6px";
  menu.style.borderRadius = "10px";
  menu.style.border = "1px solid rgba(15, 23, 42, 0.12)";
  menu.style.background = "rgba(255, 255, 255, 0.98)";
  menu.style.backdropFilter = "blur(4px)";
  menu.style.boxShadow = "0 12px 24px rgba(2, 6, 23, 0.18)";
  menu.style.zIndex = "2147483000";

  const saveButton = document.createElement("button");
  saveButton.type = "button";
  saveButton.textContent = "保存背景图";
  saveButton.style.width = "100%";
  saveButton.style.border = "none";
  saveButton.style.background = "transparent";
  saveButton.style.textAlign = "left";
  saveButton.style.padding = "8px 10px";
  saveButton.style.borderRadius = "8px";
  saveButton.style.fontSize = "14px";
  saveButton.style.color = "#0f172a";
  saveButton.style.cursor = "pointer";

  saveButton.addEventListener("mouseenter", () => {
    saveButton.style.background = "rgba(37, 99, 235, 0.10)";
  });
  saveButton.addEventListener("mouseleave", () => {
    saveButton.style.background = "transparent";
  });
  saveButton.addEventListener("click", () => {
    const currentImageUrl = menu.dataset.imageUrl || "";
    hidePcThemeBackgroundContextMenu();
    triggerPcThemeBackgroundDownload(currentImageUrl);
  });

  menu.appendChild(saveButton);
  document.body.appendChild(menu);
  pcThemeBackgroundContextMenuElement = menu;
  return menu;
}

function setupPcThemeBackgroundContextMenu() {
  if (pcThemeBackgroundContextMenuInitialized) {
    return;
  }
  pcThemeBackgroundContextMenuInitialized = true;

  const desktopContainer = document.getElementById("auth-login-container");
  if (!desktopContainer) {
    return;
  }

  const menu = ensurePcThemeBackgroundContextMenuElement();
  const contextMenuHandler = (event) => {
    const currentTarget = getCurrentThemeBackgroundTarget();
    const renderedImageUrl = getRenderedThemeBackgroundImageUrlByTarget("pc");
    const imageUrl = renderedImageUrl || getThemeBackgroundImageUrlByTarget("pc");

    if (!shouldEnablePcThemeBackgroundContextMenu({ target: currentTarget, imageUrl })) {
      hidePcThemeBackgroundContextMenu();
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    menu.dataset.imageUrl = imageUrl;
    menu.style.display = "block";

    const offsetX = 6;
    const offsetY = 6;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const rect = menu.getBoundingClientRect();
    const maxLeft = Math.max(viewportWidth - rect.width - 8, 0);
    const maxTop = Math.max(viewportHeight - rect.height - 8, 0);
    const left = Math.min(event.clientX + offsetX, maxLeft);
    const top = Math.min(event.clientY + offsetY, maxTop);
    menu.style.left = `${Math.max(left, 0)}px`;
    menu.style.top = `${Math.max(top, 0)}px`;
  };

  desktopContainer.addEventListener("contextmenu", contextMenuHandler);

  document.addEventListener("click", (event) => {
    if (!menu || menu.style.display !== "block") {
      return;
    }
    if (menu.contains(event.target)) {
      return;
    }
    hidePcThemeBackgroundContextMenu();
  });
  window.addEventListener("blur", hidePcThemeBackgroundContextMenu);
  window.addEventListener("resize", hidePcThemeBackgroundContextMenu);
  document.addEventListener("scroll", hidePcThemeBackgroundContextMenu, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hidePcThemeBackgroundContextMenu();
    }
  });
}

setupPcThemeBackgroundContextMenu();

function shouldSkipThemeBackgroundVisualRewrite(target, nextBackgroundValue, options = {}) {
  const normalizedTarget = target === "mobile" ? "mobile" : "pc";
  const renderedImageUrl = getRenderedThemeBackgroundImageUrlByTarget(normalizedTarget);
  const incomingImageUrl = extractThemeBackgroundImageUrl(nextBackgroundValue || "");

  return !!(renderedImageUrl && incomingImageUrl && renderedImageUrl === incomingImageUrl);
}

function shouldSkipThemeBackgroundConsumeDuringLogin(target, imageUrl) {
  return themeBackgroundLoginSyncInFlight || authLoginInProgress;
}

function applyThemeLoginContainerStyle(themeConfig, options = {}) {
  const config = themeConfig && typeof themeConfig === "object" ? themeConfig : {};
  const env =
    config.global_environment_variables &&
    typeof config.global_environment_variables === "object"
      ? config.global_environment_variables
      : {};

  const desktopContainer = document.getElementById("auth-login-container");
  const desktopPanel = document.getElementById("auth-login-container_panel");
  const mobileContent = document.getElementById("mobile-content");
  const mobileContainer = document.getElementById("mobile-auth-login-container");
  const mobileCard = document.getElementById("mobile-auth-login-container-card");

  const desktopBackground = env.auth_login_container_background || "";
  const panelBackground = env.auth_login_panel_background || "";
  const mobileContentBackground = env.mobile_auth_login_content_background || "";
  const mobileCardBackground = env.mobile_auth_login_card_background || "";
  const panelShadow = env.auth_login_panel_shadow || "";
  const mobileShadow = env.mobile_auth_login_card_shadow || "";
  const panelBorder = env.auth_login_panel_border || "";

  if (desktopContainer) {
    if (desktopBackground && !shouldSkipThemeBackgroundVisualRewrite("pc", desktopBackground, options)) {
      desktopContainer.style.background = desktopBackground;
    }
  }

  if (desktopPanel) {
    desktopPanel.style.background = panelBackground;
    desktopPanel.style.boxShadow = panelShadow;
    desktopPanel.style.borderColor = panelBorder;
  }

  if (mobileContent && mobileContentBackground && !shouldSkipThemeBackgroundVisualRewrite("mobile", mobileContentBackground, options)) {
    mobileContent.style.background = mobileContentBackground;
    mobileContent.style.backgroundSize = mobileContentBackground ? "cover" : "";
    mobileContent.style.backgroundPosition = mobileContentBackground ? "center" : "";
    mobileContent.style.backgroundRepeat = mobileContentBackground ? "no-repeat" : "";
  }

  if (mobileContainer) {
    mobileContainer.style.background = "";
    mobileContainer.style.borderRadius = "";
    mobileContainer.style.padding = "";
  }

  if (mobileCard) {
    mobileCard.style.background = mobileCardBackground;
    mobileCard.style.boxShadow = mobileShadow;
    mobileCard.style.borderColor = panelBorder;
  }
}

function getThemeStyleConfig(styleId) {
  const normalizedStyle = normalizeThemeStyle(styleId);
  const styles = Array.isArray(availableThemeStyles) ? availableThemeStyles : [];
  const matchedStyle = styles.find((style) => style && style.id === normalizedStyle);

  if (matchedStyle && typeof matchedStyle === "object") {
    return {
      basic_information: {
        id: matchedStyle.id || normalizedStyle,
        label: matchedStyle.label || matchedStyle.id || normalizedStyle,
        description: matchedStyle.description || "",
        svg: matchedStyle.svg || "",
      },
      global_environment_variables:
        matchedStyle.global_environment_variables &&
        typeof matchedStyle.global_environment_variables === "object"
          ? matchedStyle.global_environment_variables
          : {},
    };
  }

  return currentThemeConfig && typeof currentThemeConfig === "object"
    ? currentThemeConfig
    : {};
}

function syncThemeStyleSelectionState(styleId) {
  const cachedStyle = cacheThemeStyle(styleId);
  pythonParams.theme_style = cachedStyle;

  document.querySelectorAll('[data-theme-style]').forEach((btn) => {
    if (btn.dataset.themeStyle === cachedStyle) {
      btn.classList.add("border-2", "border-sky-500");
    } else {
      btn.classList.remove("border-2", "border-sky-500");
    }
  });

  return cachedStyle;
}

function setThemeStyle(styleName, save = true, applyConfig = true) {
  const normalizedStyle = normalizeThemeStyle(styleName);
  const nextThemeConfig = getThemeStyleConfig(normalizedStyle);
  const cachedStyle = syncThemeStyleSelectionState(normalizedStyle);

  if (applyConfig) {
    applyThemeGlobalEnvironmentVariables(nextThemeConfig);
  }

  if (save) {
    callPythonAPI("update_param", "theme_style", cachedStyle);
    logMessage_Info(`主题样式已切换为: ${cachedStyle}`);
  }
}

const THEME_STORAGE_KEY = "theme_preference";
const THEME_STYLE_STORAGE_KEY = "theme_style";
let currentThemePreference = "light";
let currentThemeStyle = "default";
window.currentThemePreference = currentThemePreference;
window.currentThemeStyle = currentThemeStyle;

function normalizeThemePreference(theme) {
  return theme === "dark" ? "dark" : "light";
}

function updateGlobalThemePreference(theme) {
  currentThemePreference = normalizeThemePreference(theme);
  window.currentThemePreference = currentThemePreference;
  return currentThemePreference;
}

function cacheThemePreference(theme) {
  const normalizedTheme = updateGlobalThemePreference(theme);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, normalizedTheme);
  } catch (e) {
    logMessage_Warning("[主题] 写入本地主题缓存失败:", e);
  }
  return normalizedTheme;
}

function getCachedThemePreference() {
  try {
    return normalizeThemePreference(localStorage.getItem(THEME_STORAGE_KEY));
  } catch (e) {
    logMessage_Warning("[主题] 读取本地主题缓存失败:", e);
    return "light";
  }
}

function syncThemeSelects(theme) {
  const normalizedTheme = normalizeThemePreference(theme);
  const profileThemeSelect = $("profile-theme-select");
  if (profileThemeSelect) {
    profileThemeSelect.value = normalizedTheme;
  }

  const mobileThemeSelect = document.getElementById("mobile-unified-theme-select");
  if (mobileThemeSelect) {
    mobileThemeSelect.value = normalizedTheme;
  }
}

function updateGlobalThemeStyle(styleId) {
  currentThemeStyle = normalizeThemeStyle(styleId);
  window.currentThemeStyle = currentThemeStyle;
  return currentThemeStyle;
}

function cacheThemeStyle(styleId) {
  const normalizedStyle = updateGlobalThemeStyle(styleId);
  try {
    localStorage.setItem(THEME_STYLE_STORAGE_KEY, normalizedStyle);
  } catch (e) {
    logMessage_Warning("[主题] 写入本地主题风格缓存失败:", e);
  }
  return normalizedStyle;
}

function getCachedThemeStyle() {
  try {
    return updateGlobalThemeStyle(localStorage.getItem(THEME_STYLE_STORAGE_KEY));
  } catch (e) {
    logMessage_Warning("[主题] 读取本地主题风格缓存失败:", e);
    return updateGlobalThemeStyle("default");
  }
}

const KNOWN_THEME_STYLE_IDS = [
  "default",
  "theme-anime",
  "theme-minimalist",
  "theme-corporate",
  "theme-creative",
  "theme-futuristic",
  "theme-retro",
];

function normalizeThemeStyle(styleId) {
  if (typeof styleId !== "string" || !styleId.trim()) {
    return "default";
  }

  const normalizedStyle = styleId.trim();
  const styles = Array.isArray(availableThemeStyles) ? availableThemeStyles : [];
  if (styles.some((style) => style && style.id === normalizedStyle)) {
    return normalizedStyle;
  }

  if (KNOWN_THEME_STYLE_IDS.includes(normalizedStyle)) {
    return normalizedStyle;
  }

  return "default";
}

function renderThemeStyleButtons(container, currentStyle = "default", options = {}) {
  if (!container) return;

  const styles = Array.isArray(availableThemeStyles) ? availableThemeStyles : [];
  const normalizedCurrentStyle = normalizeThemeStyle(currentStyle);
  const { mobile = false } = options;
  const clickHandler = mobile ? "setMobileUnifiedThemeStyle" : "setThemeStyle";

  if (mobile) {
    container.className = "space-y-3";
  } else {
    container.className = "grid grid-cols-2 gap-2";
  }

  container.innerHTML = "";
  styles.forEach((style) => {
    if (!style || !style.id) return;

    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("onclick", `${clickHandler}('${style.id}')`);
    button.title = style.description || style.label || style.id;
    button.dataset.themeStyle = style.id;

    const safeLabel = escapeHtml(style.label || style.id);
    const safeDescription = escapeHtml(style.description || "");
    const safeSvg = style.svg ? sanitizeSVG(style.svg) : "";

    button.className = mobile
      ? "w-full rounded-2xl border-2 border-transparent bg-white p-3 text-left shadow-sm overflow-hidden"
      : "btn btn-ghost !rounded-lg !py-2 !px-2 border-2 border-transparent text-left overflow-hidden";

    button.innerHTML = mobile
      ? `
        <div class="flex items-start gap-3">
          <div class="w-28 h-20 shrink-0 rounded-xl overflow-hidden border border-slate-200 bg-slate-50 flex items-center justify-center">
            ${safeSvg || '<span class="text-xs text-slate-400">暂无预览</span>'}
          </div>
          <div class="min-w-0 flex-1 pt-0.5">
            <div class="text-sm font-semibold text-slate-800 break-words">${safeLabel}</div>
            ${safeDescription ? `<div class="text-xs text-slate-500 mt-1 break-words">${safeDescription}</div>` : ""}
          </div>
        </div>
      `
      : `
        <div class="space-y-2">
          <div class="h-24 rounded-xl overflow-hidden border border-slate-200 bg-slate-50 flex items-center justify-center">
            ${safeSvg || '<span class="text-xs text-slate-400">暂无预览</span>'}
          </div>
          <div>
            <div class="text-sm font-medium text-slate-800">${safeLabel}</div>
            ${safeDescription ? `<div class="text-xs text-slate-500 mt-1 line-clamp-2">${safeDescription}</div>` : ""}
          </div>
        </div>
      `;

    if (style.id === normalizedCurrentStyle) {
      button.classList.add("border-2", "border-sky-500");
    }

    container.appendChild(button);
  });
}

function resolveThemeRequestSessionUUID(sessionId = sessionUUID, pathname = window.location.pathname) {
  if (typeof sessionId === "string" && sessionId.trim()) {
    return sessionId.trim();
  }

  const normalizedPath = typeof pathname === "string" ? pathname : "";
  const match = normalizedPath.match(
    /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i,
  );
  return match && match[1] ? match[1] : "";
}

function buildPublicThemeStylesUrl(styleId, backgroundTarget, sessionId = sessionUUID, pathname = window.location.pathname) {
  const resolvedUuid = resolveThemeRequestSessionUUID(sessionId, pathname);
  const searchParams = new URLSearchParams({
    style_id: encodeURIComponent(styleId),
    background_target: encodeURIComponent(backgroundTarget),
  });
  if (resolvedUuid) {
    searchParams.set("uuid", encodeURIComponent(resolvedUuid));
  }
  return `/api/public/theme_styles?${searchParams.toString()}`
    .replace(/style_id=([^&]+)/, (_, value) => `style_id=${decodeURIComponent(value)}`)
    .replace(/background_target=([^&]+)/, (_, value) => `background_target=${decodeURIComponent(value)}`)
    .replace(/uuid=([^&]+)/, (_, value) => `uuid=${decodeURIComponent(value)}`);
}

function shouldApplyThemeConfigImmediately(params) {
  const normalizedParams = params && typeof params === "object" ? params : {};
  const pathname = Object.prototype.hasOwnProperty.call(normalizedParams, "pathname")
    ? normalizedParams.pathname
    : window.location.pathname;
  const authStateResolved = Object.prototype.hasOwnProperty.call(normalizedParams, "authStateResolved")
    ? normalizedParams.authStateResolved
    : themeBackgroundAuthStateResolved;
  const normalizedPath = typeof pathname === "string" ? pathname : "";
  const routeMatch = normalizedPath.match(
    /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i,
  );
  const routeUuid = routeMatch && routeMatch[1] ? routeMatch[1] : "";
  if (!routeUuid) {
    return true;
  }
  return authStateResolved === true;
}

async function ensureThemeStylesLoaded(force = false, options = {}) {
  if (!force && Array.isArray(availableThemeStyles) && availableThemeStyles.length > 0) {
    return availableThemeStyles;
  }

  const normalizedOptions = options && typeof options === "object" ? options : {};
  const applyThemeConfig = Object.prototype.hasOwnProperty.call(normalizedOptions, "applyThemeConfig")
    ? normalizedOptions.applyThemeConfig
    : shouldApplyThemeConfigImmediately();

  try {
    const requestedThemeStyle = normalizeThemeStyle(getCachedThemeStyle());
    const requestedTarget = getCurrentThemeBackgroundTarget();
    const shouldUseSessionThemeApi =
      themeBackgroundAuthStateResolved === true &&
      themeBackgroundAuthenticatedSession === true &&
      !!sessionUUID;
    const result = shouldUseSessionThemeApi
      ? await callPythonAPI("get_theme_styles", requestedTarget)
      : await fetch(buildPublicThemeStylesUrl(requestedThemeStyle, requestedTarget), {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        }).then((response) => {
            if (!response.ok) {
              throw new Error(`HTTP错误: ${response.status}`);
            }
            return response.json();
          });

    if (result && result.success && Array.isArray(result.theme_styles)) {
      availableThemeStyles = result.theme_styles;
      if (result.theme_config && typeof result.theme_config === "object") {
        currentThemeConfig = typeof mergeThemeBackgroundConfig === "function"
          ? mergeThemeBackgroundConfig(currentThemeConfig, result.theme_config)
          : result.theme_config;
        if (applyThemeConfig) {
          applyThemeGlobalEnvironmentVariables(currentThemeConfig);
        }
      }
      if (typeof applyThemeBackgroundAssignment === "function") {
        applyThemeBackgroundAssignment(result.theme_background, {
          bound: result.theme_background?.source !== "anonymous_preview",
        });
      }
      return availableThemeStyles;
    }
  } catch (e) {
    logMessage_Warning("[主题] 加载主题风格列表失败:", e);
  }

  availableThemeStyles = [];
  return availableThemeStyles;
}

function applyTheme(theme, options = {}) {
  const normalizedTheme = normalizeThemePreference(theme);
  const { cache = true, syncControls = true } = options;

  if (normalizedTheme === "dark") {
    document.body.classList.add("dark-mode");
    logMessage_Info("[主题] 已应用深色模式");
  } else {
    document.body.classList.remove("dark-mode");
    logMessage_Info("[主题] 已应用浅色模式");
  }

  if (cache) {
    cacheThemePreference(normalizedTheme);
  } else {
    updateGlobalThemePreference(normalizedTheme);
  }

  if (syncControls) {
    syncThemeSelects(normalizedTheme);
  }

  return normalizedTheme;
}

async function saveThemePreference(theme) {
  const normalizedTheme = applyTheme(theme);

  if (!sessionUUID) {
    logMessage_Info(`[主题] 当前未登录，仅保存本地主题: ${normalizedTheme}`);
    return { success: true, theme: normalizedTheme, localOnly: true };
  }

  try {
    const response = await fetch("/auth/user/update_theme", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ theme: normalizedTheme }),
    });
    const result = await response.json();

    if (result.success) {
      logMessage_Info(`[主题] 主题设置已保存: ${normalizedTheme}`);
      return { ...result, theme: normalizeThemePreference(result.theme || normalizedTheme) };
    }

    logMessage_Warning(`[主题] 保存主题设置失败: ${result.message}`);
    return result;
  } catch (e) {
    logMessage_Error("[主题] 保存主题设置时出错:", e);
    return { success: false, message: e.message || "保存主题失败" };
  }
}

async function syncThemeFromServer(themeFromResponse = null, themeStyleFromResponse = null, backgroundAssignment = null) {
  applyThemeBackgroundAssignment(backgroundAssignment, { bound: true });
  themeBackgroundAuthStateResolved = true;
  themeBackgroundAuthenticatedSession = !!sessionUUID;
  const responseTheme =
    typeof themeFromResponse === "string" && themeFromResponse
      ? normalizeThemePreference(themeFromResponse)
      : null;
  const responseThemeStyle =
    typeof themeStyleFromResponse === "string" && themeStyleFromResponse
      ? normalizeThemeStyle(themeStyleFromResponse)
      : null;

  if (!sessionUUID) {
    const fallbackTheme = responseTheme || getCachedThemePreference();
    const fallbackThemeStyle = responseThemeStyle || getCachedThemeStyle();
    applyTheme(fallbackTheme);
    setThemeStyle(fallbackThemeStyle, false, !themeBackgroundLoginSyncInFlight);
    applyThemeGlobalEnvironmentVariables(currentThemeConfig);
    return { theme: fallbackTheme, theme_style: fallbackThemeStyle };
  }

  let serverTheme = responseTheme;
  let serverThemeStyle = responseThemeStyle;

  if (!serverTheme) {
    try {
      const response = await fetch("/auth/user/theme", {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      });
      const result = await response.json();
      if (result.success) {
        serverTheme = normalizeThemePreference(result.theme);
      } else {
        logMessage_Warning(`[主题] 读取服务器主题失败: ${result.message}`);
      }
    } catch (e) {
      logMessage_Warning("[主题] 同步服务器主题失败:", e);
    }
  }

  if (!serverThemeStyle) {
    try {
      const paramsResult = await callPythonAPI("get_params");
      if (paramsResult && paramsResult.theme_style) {
        serverThemeStyle = normalizeThemeStyle(paramsResult.theme_style);
      }
    } catch (e) {
      logMessage_Warning("[主题] 同步服务器主题风格失败:", e);
    }
  }

  const finalTheme = serverTheme || getCachedThemePreference();
  const finalThemeStyle = serverThemeStyle || getCachedThemeStyle();

  applyTheme(finalTheme);
  if (responseThemeStyle || themeBackgroundLoginSyncInFlight) {
    setThemeStyle(finalThemeStyle, false, false);
  } else {
    setThemeStyle(finalThemeStyle, false);
  }
  if (currentThemeConfig && typeof currentThemeConfig === "object") {
    applyThemeLoginContainerStyle(currentThemeConfig, {
      skipVisualRewrite: themeBackgroundLoginSyncInFlight,
    });
  }
  logMessage_Info(`[主题] 已同步服务器主题: ${finalTheme}`);
  logMessage_Info(`[主题] 已同步服务器主题风格: ${finalThemeStyle}`);

  return { theme: finalTheme, theme_style: finalThemeStyle };
}

function resetBaseColorToDefault(prefix) {
  const defaultColor = "#7dd3fc";
  const key = "theme_base_color";

  const colorPicker = document.getElementById(`${prefix}-${key}-picker`);
  const textInput = document.getElementById(`${prefix}-${key}`);
  if (colorPicker) colorPicker.value = defaultColor;
  if (textInput) textInput.value = defaultColor;

  setBaseColor(defaultColor, defaultColor);

  if (pythonParams) {
    pythonParams[key] = defaultColor;
  }

  logMessage_Info("主题颜色已恢复为默认。");
}

function setBaseColor(c, deep, save = true) {
  // 增加 save 参数
  document.documentElement.style.setProperty("--base-color", c);
  document.documentElement.style.setProperty("--base-color-600", deep);
  document.documentElement.style.setProperty("--base-color-300", c);
  // 仅当 save 为 true 时调用 API
  if (save) {
    callPythonAPI("update_param", "theme_base_color", c);
  }
  if ($("base-color-input")) $("base-color-input").value = c;
}
function onColorPicked(val) {
  setBaseColor(val, val);
}

/**
 * 统一管理面板主题颜色保存函数
 * 该函数用于处理 mobile-admin-panel-unified 中的主题颜色保存
 *
 * @description
 *   根据 window.mobileAdminPanelMode 判断当前是单账号还是多账号模式：
 *   - 单账号模式('single')：调用 callPythonAPI('update_param', ...) 写入 params
 *   - 多账号模式('multi')：同样调用 update_param，因为全局参数对所有账号生效
 *
 * @param {string} value - 主题颜色值（如 '#7dd3fc'）
 */
function saveUnifiedThemeColor(value) {
  // 获取当前模式，默认为多账号模式
  const mode = window.mobileAdminPanelMode || "multi";
  // 记录日志，便于调试
  console.log(`[统一管理面板] 保存主题颜色: ${value}, 模式: ${mode}`);

  // 更新本地参数对象
  if (typeof pythonParams !== "undefined") {
    pythonParams.theme_base_color = value;
  }

  // 无论是单账号还是多账号模式，都调用 update_param API
  // 因为单账号模式下参数存储在 sessions 的 params 中
  // 多账号模式下参数存储在 sessions 的 global_params 中
  // 后端会根据当前会话模式自动写入正确的位置
  callPythonAPI("update_param", "theme_base_color", value);

  // 同时更新颜色选择器和输入框的同步
  const colorPicker = document.getElementById(
    "mobile-unified-theme_base_color-picker",
  );
  const colorInput = document.getElementById("mobile-unified-theme_base_color");
  if (colorPicker) colorPicker.value = value;
  if (colorInput) colorInput.value = value;
}

async function checkAuthStatus() {
  try {
    // 调用统一的初始数据加载函数进行认证状态检查
    const result = await loadInitialData();
    logMessage_Info(
      "[认证状态] 检查结果:",
      createSafeClientLogValue(result),
    );
    if (result && result.is_authenticated) {
      return true;
    }
  } catch (e) {
    logMessage_Info("未认证或会话过期");
  }

  return false;
}

function showAuthLogin() {
  clearLogoutElsewhereOverlay();
  $("loading-overlay").classList.add("hidden");
  $("auth-login-container").classList.remove("hidden");
  $("login-container").classList.add("hidden");
  $("main-app").classList.add("hidden");

  // 新增：在认证登录界面隐藏退出应用按钮
  const exitBtn = $("exit-app-btn");
  if (exitBtn) exitBtn.classList.add("hidden");

  loadSiteIdentityBootstrap();
  checkGuestLoginEnabled();
}

async function checkGuestLoginEnabled() {
  try {
    // 构建请求头，添加会话ID用于身份验证
    // X-Session-ID header 用于后端识别用户会话，几乎所有需要认证的API都需要此header
    const headers = {};
    if (sessionUUID) {
      headers["X-Session-ID"] = sessionUUID;
    }

    // 发起请求获取认证配置，检查是否启用游客登录功能
    const result = await fetch("/auth/get_config", {
      headers: headers,
    });
    const data = await result.json();
    if (data.success && data.allow_guest_login) {
      $("guest-login-section").classList.remove("hidden");
      const guestBtn = $("auth-guest-btn");
      if (guestBtn && data.guest_capacity_available === false) {
        guestBtn.disabled = true;
        guestBtn.textContent = "访客名额已满";
      }
    } else {
      $("guest-login-section").classList.add("hidden");
    }
  } catch (e) {
    logMessage_Error("获取配置失败:", e);
  }
}

function switchAuthTab(tab) {
  const loginTab = $("auth-tab-login");
  const registerTab = $("auth-tab-register");
  const loginForm = $("auth-login-form");
  const registerForm = $("auth-register-form");

  if (!loginTab || !registerTab || !loginForm || !registerForm) {
    return;
  }

  if (tab === "login") {
    loginTab.classList.add("text-sky-600", "border-sky-600");
    loginTab.classList.remove("text-slate-400", "border-transparent");
    registerTab.classList.remove("text-sky-600", "border-sky-600");
    registerTab.classList.add("text-slate-400", "border-transparent");
    loginForm.classList.remove("hidden");
    registerForm.classList.add("hidden");
  } else {
    registerTab.classList.add("text-sky-600", "border-sky-600");
    registerTab.classList.remove("text-slate-400", "border-transparent");
    loginTab.classList.remove("text-sky-600", "border-sky-600");
    loginTab.classList.add("text-slate-400", "border-transparent");
    registerForm.classList.remove("hidden");
    loginForm.classList.add("hidden");
  }

  $("auth-error-msg").classList.add("hidden");
  $("auth-success-msg").classList.add("hidden");
}

function showAuthError(message) {
  const errorMsg = $("auth-error-msg");
  errorMsg.textContent = message;
  errorMsg.classList.remove("hidden");
  $("auth-success-msg").classList.add("hidden");
}

function showAuthSuccess(message) {
  const successMsg = $("auth-success-msg");
  successMsg.textContent = message;
  successMsg.classList.remove("hidden");
  $("auth-error-msg").classList.add("hidden");
}

function setButtonLoading(buttonId, loading, originalText = "") {
  const btn = $(buttonId);
  if (!btn) return;

  if (loading) {
    btn.dataset.originalText = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = `<span class="inline-block animate-spin mr-2">⏳</span>${
      originalText || "处理中..."
    }`;
    btn.classList.add("opacity-75", "cursor-not-allowed");
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText || originalText;
    btn.classList.remove("opacity-75", "cursor-not-allowed");
    delete btn.dataset.originalText;
  }
}

function showButtonSuccess(buttonId, message = "成功", duration = 1500) {
  const btn = $(buttonId);
  if (!btn) return;

  btn.disabled = false;
  btn.classList.remove("opacity-75", "cursor-not-allowed");

  const originalText = btn.dataset.originalText || btn.textContent;
  delete btn.dataset.originalText;

  btn.innerHTML = `<span class="mr-1">✓</span>${message}`;
  btn.classList.add("!bg-green-600");

  setTimeout(() => {
    btn.textContent = originalText;
    btn.classList.remove("!bg-green-600");
    btn.disabled = false;
  }, duration);
}

function showButtonError(buttonId, message = "失败", duration = 2000) {
  const btn = $(buttonId);
  if (!btn) return;

  btn.disabled = false;
  btn.classList.remove("opacity-75", "cursor-not-allowed");

  const originalText = btn.dataset.originalText || btn.textContent;
  delete btn.dataset.originalText;

  btn.innerHTML = `<span class="mr-1">✗</span>${message}`;
  btn.classList.add("!bg-red-600");

  setTimeout(() => {
    btn.textContent = originalText;
    btn.classList.remove("!bg-red-600");
    btn.disabled = false;
  }, duration);
}

const captchaDimensions = {
  login: { width: 343, height: 119 },
  register: { width: 343, height: 119 },
  modal: { width: 343, height: 119 },
};

// 当打开短信验证码模态框时，记录请求期望的宽度（以便传给后端并设置iframe）
let captchaModalRequestedWidth = null;

function normalizeRuntimeCaptchaProviderConfig(settings = {}) {
  const provider =
    String(settings.provider || "image").trim().toLowerCase() === "behavior"
      ? "behavior"
      : "image";
  const behaviorType = String(
    settings.behavior_type || RUNTIME_CAPTCHA_PROVIDER_DEFAULT.behavior_type,
  )
    .trim()
    .toUpperCase();
  return {
    provider,
    behavior_type: behaviorType || RUNTIME_CAPTCHA_PROVIDER_DEFAULT.behavior_type,
  };
}

function setRuntimeCaptchaProviderConfig(settings) {
  runtimeCaptchaProviderConfig = normalizeRuntimeCaptchaProviderConfig(settings);
  runtimeCaptchaProviderConfigPromise = null;
  return runtimeCaptchaProviderConfig;
}

function invalidateRuntimeCaptchaProviderConfig() {
  runtimeCaptchaProviderConfig = null;
  runtimeCaptchaProviderConfigPromise = null;
}

async function fetchRuntimeCaptchaProviderConfig() {
  if (runtimeCaptchaProviderConfig) {
    return runtimeCaptchaProviderConfig;
  }
  if (runtimeCaptchaProviderConfigPromise) {
    return runtimeCaptchaProviderConfigPromise;
  }

  runtimeCaptchaProviderConfigPromise = fetch("/api/captcha/provider", {
    method: "GET",
    credentials: "include",
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (!data || data.success === false) {
        throw new Error(data?.message || "验证码提供方配置读取失败");
      }
      return setRuntimeCaptchaProviderConfig(data);
    })
    .catch((error) => {
      console.warn("[验证码] 读取提供方配置失败，回退图片验证码:", error);
      return setRuntimeCaptchaProviderConfig(RUNTIME_CAPTCHA_PROVIDER_DEFAULT);
    });

  return runtimeCaptchaProviderConfigPromise;
}

async function isBehaviorCaptchaProvider() {
  const providerConfig = await fetchRuntimeCaptchaProviderConfig();
  return providerConfig.provider === "behavior";
}

function isMissingCaptchaId(value) {
  const normalized = String(value ?? "").trim().toLowerCase();
  return !normalized || normalized === "null" || normalized === "undefined";
}

function ensureBehaviorCaptchaLoader() {
  if (window.initTAC) {
    return Promise.resolve();
  }
  if (behaviorCaptchaLoaderPromise) {
    return behaviorCaptchaLoaderPromise;
  }
  behaviorCaptchaLoaderPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/api/captcha/behavior/loader.js";
    script.async = true;
    script.onload = () => {
      if (window.initTAC) {
        resolve();
      } else {
        reject(new Error("TAC loader 未暴露 initTAC"));
      }
    };
    script.onerror = () => reject(new Error("验证码 SDK 加载失败"));
    document.head.appendChild(script);
  }).catch((error) => {
    behaviorCaptchaLoaderPromise = null;
    throw error;
  });
  return behaviorCaptchaLoaderPromise;
}

function createBehaviorCaptchaTriggerStyle() {
  return {
    triggerMode: "click",
    popupMode: true,
    logoUrl: null,
    i18n: {
      trigger_text: "点击进行人机验证码",
    },
  };
}

function getCaptchaDisplayIdForForm(formType) {
  if (formType === "login") return "auth-login-captcha-display";
  if (formType === "register") return "auth-register-captcha-display";
  if (formType === "mobile-login") return "mobile-login-captcha-display";
  if (formType === "mobile-register") return "mobile-register-captcha-display";
  return "";
}

function getCaptchaInputIdForForm(formType) {
  if (formType === "login") return "auth-login-captcha";
  if (formType === "register") return "auth-register-captcha";
  if (formType === "mobile-login") return "mobile-login-captcha";
  if (formType === "mobile-register") return "mobile-register-captcha";
  return "";
}

function setCaptchaIdForForm(formType, captchaId) {
  if (formType === "login") {
    captchaIds_login = captchaId;
  } else if (formType === "register") {
    captchaIds_register = captchaId;
  } else if (formType === "mobile-login") {
    captchaIds_mobile_login = captchaId;
  } else if (formType === "mobile-register") {
    captchaIds_mobile_register = captchaId;
  }
}

function getCaptchaIdForForm(formType) {
  if (formType === "login") return captchaIds_login;
  if (formType === "register") return captchaIds_register;
  if (formType === "mobile-login") return captchaIds_mobile_login;
  if (formType === "mobile-register") return captchaIds_mobile_register;
  return "";
}

function resetBehaviorCaptchaForForm(formType) {
  setCaptchaIdForForm(formType, "");
  setCaptchaInputValueForForm(formType, "");
}

function resetBehaviorCaptchaModal() {
  captchaIds_modal = "";
  const modalInput = document.getElementById("captcha-modal-input");
  if (modalInput) {
    modalInput.value = "";
  }
}

function setCaptchaInputValueForForm(formType, value) {
  const inputId = getCaptchaInputIdForForm(formType);
  const input = inputId ? document.getElementById(inputId) : null;
  if (input) {
    input.value = value;
  }
}

function setCaptchaInputBehaviorMode(formType, enabled) {
  const inputId = getCaptchaInputIdForForm(formType);
  const input = inputId ? document.getElementById(inputId) : null;
  if (!input) return;

  if (enabled) {
    if (input.dataset.imageCaptchaPlaceholder === undefined) {
      input.dataset.imageCaptchaPlaceholder = input.getAttribute("placeholder") || "";
    }
    input.classList.add("hidden");
    input.setAttribute("aria-hidden", "true");
    input.setAttribute("tabindex", "-1");
    return;
  }

  input.classList.remove("hidden");
  input.removeAttribute("aria-hidden");
  input.removeAttribute("tabindex");
  if (input.dataset.imageCaptchaPlaceholder !== undefined) {
    input.setAttribute("placeholder", input.dataset.imageCaptchaPlaceholder);
  }
}

function setCaptchaDisplayBehaviorMode(displayElement, enabled) {
  if (!displayElement) return;
  const refreshButtonId = {
    "auth-login-captcha-display": "auth-login-captcha-refresh",
    "auth-register-captcha-display": "auth-register-captcha-refresh",
    "mobile-login-captcha-display": "mobile-login-captcha-refresh",
    "mobile-register-captcha-display": "mobile-register-captcha-refresh",
    "captcha-modal-display": "modal-login-captcha-refresh",
  }[displayElement.id];
  const refreshButton = refreshButtonId
    ? document.getElementById(refreshButtonId)
    : null;
  if (refreshButton) {
    refreshButton.style.display = enabled ? "none" : "";
  }

  if (enabled) {
    displayElement.dataset.behaviorCaptcha = "true";
    if (
      displayElement.hasAttribute("onclick") &&
      displayElement.dataset.imageCaptchaOnclick === undefined
    ) {
      displayElement.dataset.imageCaptchaOnclick =
        displayElement.getAttribute("onclick") || "";
    }
    displayElement.removeAttribute("onclick");
    displayElement.onclick = null;
    return;
  }

  delete displayElement.dataset.behaviorCaptcha;
  if (displayElement.dataset.imageCaptchaOnclick !== undefined) {
    displayElement.setAttribute("onclick", displayElement.dataset.imageCaptchaOnclick);
  }
}

function destroyBehaviorCaptchaInstance(instanceKey) {
  const instance = behaviorCaptchaInstances[instanceKey];
  if (!instance) return;
  try {
    if (typeof instance.destroyWindow === "function") {
      instance.destroyWindow();
    } else if (typeof instance.destroy === "function") {
      instance.destroy();
    }
  } catch (error) {
    console.warn("[验证码] 销毁行为验证码实例失败:", error);
  }
  behaviorCaptchaInstances[instanceKey] = null;
}

function resetBehaviorCaptchaSdkRuntime() {
  document
    .querySelectorAll('script[data-tac-loader], link[data-tac-loader]')
    .forEach((element) => element.remove());
  behaviorCaptchaLoaderPromise = null;
  try {
    delete window.initTAC;
    delete window.initCaptchaLocal;
    delete window.CaptchaLocal;
  } catch (_) {
    window.initTAC = undefined;
    window.initCaptchaLocal = undefined;
    window.CaptchaLocal = undefined;
  }
}

function queueBehaviorCaptchaRetry(key, retryFn, delayMs) {
  behaviorCaptchaRetryQueue.set(key, retryFn);
  if (behaviorCaptchaRetryTimer) return;
  behaviorCaptchaRetryTimer = setTimeout(() => {
    const retries = Array.from(behaviorCaptchaRetryQueue.values());
    behaviorCaptchaRetryQueue.clear();
    behaviorCaptchaRetryTimer = null;
    resetBehaviorCaptchaSdkRuntime();
    retries.forEach((retry) => retry());
  }, delayMs);
}

function retryBehaviorCaptchaLoad(formType, attempt) {
  resetBehaviorCaptchaSdkRuntime();
  return loadBehaviorCaptcha(formType, attempt);
}

function retryBehaviorCaptchaModalLoad(attempt) {
  resetBehaviorCaptchaSdkRuntime();
  return loadBehaviorCaptchaModal(attempt);
}

async function loadBehaviorCaptcha(formType, attempt = 0) {
  const displayId = getCaptchaDisplayIdForForm(formType);
  const displayElement = displayId ? document.getElementById(displayId) : null;
  if (!displayElement) {
    console.error(`[验证码-behavior] 未找到验证码显示元素: ${displayId || formType}`);
    return;
  }

  const hasVerifiedBehaviorCaptcha = !isMissingCaptchaId(getCaptchaIdForForm(formType));
  if (!hasVerifiedBehaviorCaptcha) {
    setCaptchaIdForForm(formType, "");
    setCaptchaInputValueForForm(formType, "");
  } else {
    setCaptchaInputValueForForm(formType, "behavior-verified");
  }
  setCaptchaInputBehaviorMode(formType, true);
  setCaptchaDisplayBehaviorMode(displayElement, true);

  const widgetId = `behavior-captcha-${formType}`;
  const statusId = `${widgetId}-status`;
  displayElement.style.width = "";
  displayElement.style.height = "";
  displayElement.innerHTML = `
    <div class="w-full" style="min-height:60px;">
      <div id="${widgetId}" style="min-height:60px;"></div>
      <p id="${statusId}" class="mt-1 text-xs ${hasVerifiedBehaviorCaptcha ? "text-green-600" : "text-slate-400"}">${hasVerifiedBehaviorCaptcha ? "验证通过" : "请完成上方人机验证"}</p>
    </div>
  `;

  try {
    const providerConfig = await fetchRuntimeCaptchaProviderConfig();
    await ensureBehaviorCaptchaLoader();
    destroyBehaviorCaptchaInstance(formType);
    const behaviorType =
      providerConfig.behavior_type || RUNTIME_CAPTCHA_PROVIDER_DEFAULT.behavior_type;
    const preserveSuccessOnClose = () => !isMissingCaptchaId(getCaptchaIdForForm(formType));
    const tac = await window.initTAC("/api/captcha/behavior/tac/", {
      requestCaptchaDataUrl:
        "/api/captcha/behavior/gen?type=" + encodeURIComponent(behaviorType),
      validCaptchaUrl: "/api/captcha/behavior/check",
      bindEl: `#${widgetId}`,
      btnCloseFun: (event, tacInstance) => {
        if (
          tacInstance &&
          typeof tacInstance.isClickTriggerMode === "function" &&
          tacInstance.isClickTriggerMode() &&
          typeof tacInstance.renderTrigger === "function"
        ) {
          tacInstance.renderTrigger(preserveSuccessOnClose());
        } else if (tacInstance && typeof tacInstance.destroyWindow === "function") {
          tacInstance.destroyWindow();
        }
      },
      validSuccess: (res, c, tacInstance) => {
        const captchaId = res && res.data ? res.data.id : "";
        setCaptchaIdForForm(formType, captchaId);
        setCaptchaInputValueForForm(formType, "behavior-verified");
        const statusElement = document.getElementById(statusId);
        if (statusElement) {
          statusElement.textContent = "验证通过";
          statusElement.className = "mt-1 text-xs text-green-600";
        }
        if (tacInstance && typeof tacInstance.showTriggerSuccess === "function") {
          tacInstance.showTriggerSuccess();
        }
      },
      validFail: (res, code, tacInstance) => {
        if (getCaptchaIdForForm(formType)) {
          if (tacInstance && typeof tacInstance.showTriggerSuccess === "function") {
            tacInstance.showTriggerSuccess();
          }
        } else if (tacInstance && typeof tacInstance.reloadCaptcha === "function") {
          tacInstance.reloadCaptcha();
        }
      },
    }, createBehaviorCaptchaTriggerStyle());
    behaviorCaptchaInstances[formType] = tac;
    if (tac && typeof tac.init === "function") {
      tac.init();
    }
    if (hasVerifiedBehaviorCaptcha && tac && typeof tac.showTriggerSuccess === "function") {
      tac.showTriggerSuccess();
    }
  } catch (error) {
    const nextAttempt = attempt + 1;
    if (attempt < BEHAVIOR_CAPTCHA_MAX_AUTO_RETRIES) {
      displayElement.innerHTML = `<span class="text-amber-600 text-xs">人机验证加载失败，正在自动重试（${nextAttempt}/${BEHAVIOR_CAPTCHA_MAX_AUTO_RETRIES}）...</span>`;
      console.warn("[验证码-behavior] 加载异常，准备自动重试:", error);
      queueBehaviorCaptchaRetry(
        formType,
        () => loadBehaviorCaptcha(formType, nextAttempt),
        BEHAVIOR_CAPTCHA_RETRY_DELAY_MS * nextAttempt,
      );
      return;
    }
    displayElement.innerHTML =
      `<span class="text-red-500 text-xs">人机验证加载失败 <button type="button" class="ml-1 underline" onclick="retryBehaviorCaptchaLoad('${formType}', 0)">重新加载</button></span>`;
    console.error("[验证码-behavior] 加载异常:", error);
  }
}

function setCaptchaModalInputBehaviorMode(enabled) {
  const modalInput = document.getElementById("captcha-modal-input");
  if (!modalInput) return;
  const inputGroup = modalInput.closest(".space-y-2");
  if (enabled) {
    modalInput.dataset.behaviorCaptcha = "true";
    modalInput.value = "";
    modalInput.classList.add("hidden");
    modalInput.setAttribute("aria-hidden", "true");
    modalInput.setAttribute("tabindex", "-1");
    if (inputGroup) inputGroup.classList.add("hidden");
    return;
  }

  delete modalInput.dataset.behaviorCaptcha;
  modalInput.classList.remove("hidden");
  modalInput.removeAttribute("aria-hidden");
  modalInput.removeAttribute("tabindex");
  if (inputGroup) inputGroup.classList.remove("hidden");
}

async function loadBehaviorCaptchaModal(attempt = 0) {
  const displayElement = document.getElementById("captcha-modal-display");
  const modalInput = document.getElementById("captcha-modal-input");
  if (!displayElement) {
    console.error("[验证码模态窗-behavior] 未找到验证码显示元素");
    return;
  }

  const hasVerifiedBehaviorCaptcha = !isMissingCaptchaId(captchaIds_modal);
  if (!hasVerifiedBehaviorCaptcha) {
    captchaIds_modal = "";
  }
  setCaptchaModalInputBehaviorMode(true);
  if (hasVerifiedBehaviorCaptcha && modalInput) {
    modalInput.value = "behavior-verified";
  }
  setCaptchaDisplayBehaviorMode(displayElement, true);
  displayElement.style.width = "100%";
  displayElement.style.height = "auto";
  displayElement.innerHTML = `
    <div class="w-full" style="min-height:60px;">
      <div id="captcha-modal-tac" style="min-height:60px;"></div>
      <p id="captcha-modal-tac-status" class="mt-1 text-xs ${hasVerifiedBehaviorCaptcha ? "text-green-600" : "text-slate-400"}">${hasVerifiedBehaviorCaptcha ? "验证通过，请点击确认发送" : "请完成上方人机验证"}</p>
    </div>
  `;

  try {
    const providerConfig = await fetchRuntimeCaptchaProviderConfig();
    await ensureBehaviorCaptchaLoader();
    destroyBehaviorCaptchaInstance("modal");
    const behaviorType =
      providerConfig.behavior_type || RUNTIME_CAPTCHA_PROVIDER_DEFAULT.behavior_type;
    const preserveSuccessOnClose = () => !isMissingCaptchaId(captchaIds_modal);
    const tac = await window.initTAC("/api/captcha/behavior/tac/", {
      requestCaptchaDataUrl:
        "/api/captcha/behavior/gen?type=" + encodeURIComponent(behaviorType),
      validCaptchaUrl: "/api/captcha/behavior/check",
      bindEl: "#captcha-modal-tac",
      btnCloseFun: (event, tacInstance) => {
        if (
          tacInstance &&
          typeof tacInstance.isClickTriggerMode === "function" &&
          tacInstance.isClickTriggerMode() &&
          typeof tacInstance.renderTrigger === "function"
        ) {
          tacInstance.renderTrigger(preserveSuccessOnClose());
        } else if (tacInstance && typeof tacInstance.destroyWindow === "function") {
          tacInstance.destroyWindow();
        }
      },
      validSuccess: (res, c, tacInstance) => {
        const captchaId = res && res.data ? res.data.id : "";
        captchaIds_modal = captchaId;
        if (modalInput) {
          modalInput.value = "behavior-verified";
        }
        const statusElement = document.getElementById("captcha-modal-tac-status");
        if (statusElement) {
          statusElement.textContent = "验证通过，请点击确认发送";
          statusElement.className = "mt-1 text-xs text-green-600";
        }
        if (tacInstance && typeof tacInstance.showTriggerSuccess === "function") {
          tacInstance.showTriggerSuccess();
        }
      },
      validFail: (res, code, tacInstance) => {
        if (captchaIds_modal) {
          if (tacInstance && typeof tacInstance.showTriggerSuccess === "function") {
            tacInstance.showTriggerSuccess();
          }
        } else if (tacInstance && typeof tacInstance.reloadCaptcha === "function") {
          tacInstance.reloadCaptcha();
        }
      },
    }, createBehaviorCaptchaTriggerStyle());
    behaviorCaptchaInstances.modal = tac;
    if (tac && typeof tac.init === "function") {
      tac.init();
    }
    if (hasVerifiedBehaviorCaptcha && tac && typeof tac.showTriggerSuccess === "function") {
      tac.showTriggerSuccess();
    }
  } catch (error) {
    const nextAttempt = attempt + 1;
    if (attempt < BEHAVIOR_CAPTCHA_MAX_AUTO_RETRIES) {
      displayElement.innerHTML = `<span class="text-amber-600 text-xs">人机验证加载失败，正在自动重试（${nextAttempt}/${BEHAVIOR_CAPTCHA_MAX_AUTO_RETRIES}）...</span>`;
      console.warn("[验证码模态窗-behavior] 加载异常，准备自动重试:", error);
      queueBehaviorCaptchaRetry(
        "modal",
        () => loadBehaviorCaptchaModal(nextAttempt),
        BEHAVIOR_CAPTCHA_RETRY_DELAY_MS * nextAttempt,
      );
      return;
    }
    displayElement.innerHTML =
      `<span class="text-red-500 text-xs">人机验证加载失败 <button type="button" class="ml-1 underline" onclick="retryBehaviorCaptchaModalLoad(0)">重新加载</button></span>`;
    console.error("[验证码模态窗-behavior] 加载异常:", error);
  }
}

async function loadCaptcha(formType) {
  if (await isBehaviorCaptchaProvider()) {
    return loadBehaviorCaptcha(formType);
  }

  let displayId = undefined;

  if (formType === "login") {
    displayId = "auth-login-captcha-display";
  } else if (formType === "register") {
    displayId = "auth-register-captcha-display";
  } else if (formType === "mobile-login") {
    displayId = "mobile-login-captcha-display";
  } else if (formType === "mobile-register") {
    displayId = "mobile-register-captcha-display";
  } else {
    console.error(`[验证码] 未知的表单类型: ${formType}`);
    return;
  }

  const displayElement = document.getElementById(displayId);
  if (!displayElement) {
    console.error(`[验证码] 未找到验证码显示元素: ${displayId}`);
    return;
  }
  destroyBehaviorCaptchaInstance(formType);
  setCaptchaInputBehaviorMode(formType, false);
  setCaptchaInputValueForForm(formType, "");
  setCaptchaDisplayBehaviorMode(displayElement, false);
  displayElement.innerHTML =
    '<span class="text-slate-400 text-xs">加载中...</span>';

  // 自动获取容器宽度
  // let containerWidth = 343;
  // if (formType === "login") {
  let container = undefined;
  if (formType === "login" || formType === "register") {
    container = document.getElementById("auth-login-container_panel");
  } else if (formType === "mobile-login" || formType === "mobile-register") {
    container = document.getElementById("mobile-auth-login-container-card");
  } else {
    console.error(`[验证码] 无法找到容器元素: ${displayId}`);
    return;
  }
  if (container) {
    // 取padding后内容区宽度
    const style = window.getComputedStyle(container);
    // console.log("[验证码] 容器计算样式:", style);
    const paddingLeft = parseFloat(style.paddingLeft) || 0;
    const paddingRight = parseFloat(style.paddingRight) || 0;
    if (formType === "login" || formType === "register") {
      containerWidth = container.clientWidth - paddingLeft - paddingRight - 200;
    } else if (formType === "mobile-login" || formType === "mobile-register") {
      containerWidth = container.clientWidth - paddingLeft - paddingRight - 0;
    } else {
      console.error(`[验证码] 无法计算容器宽度: ${displayId}`);
      return;
    }
    console.log(
      "[验证码] 容器宽度计算细节: 背景宽度",
      container.clientWidth,
      "减去左内边距",
      paddingLeft,
      "减去右内边距",
      paddingRight,
    );
    console.log(`[验证码] 登录表单容器宽度: ${containerWidth}px`);
    // 限制最大宽度
    if (containerWidth > 600) containerWidth = 600;
    if (containerWidth < 200) containerWidth = 200;
  }
  // }

  try {
    // 传递width参数给后端
    const response = await fetch(`/api/captcha/get?width=${containerWidth}`, {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });

    const result = await response.json();
    if (result.success && result.captcha_id) {
      const uuidRegex =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (!uuidRegex.test(result.captcha_id)) {
        console.error("[验证码] 无效的captcha_id格式，可能存在安全风险");
        displayElement.innerHTML =
          '<span class="text-red-500 text-xs">验证码ID格式错误</span>';
        return;
      }
      // captchaIds[formType] = result.captcha_id;
      if (formType === "login") {
        captchaIds_login = result.captcha_id;
      } else if (formType === "register") {
        captchaIds_register = result.captcha_id;
      } else if (formType === "mobile-login") {
        captchaIds_mobile_login = result.captcha_id;
      } else if (formType === "mobile-register") {
        captchaIds_mobile_register = result.captcha_id;
      }
      captchaDimensions[formType] = {
        width: result.width || 343,
        height: result.height || 119,
      };

      displayId.width = captchaDimensions[formType].width;
      displayId.height = captchaDimensions[formType].height;

      const timestamp = Date.now();
      const captchaWidth = captchaDimensions[formType].width;
      const captchaHeight = captchaDimensions[formType].height;
      console.log(`[验证码] 验证码尺寸: ${captchaWidth}x${captchaHeight}`);

      // 传递width参数给iframe
      const iframeHtml = `
            <iframe 
              src="/api/captcha/html/${result.captcha_id}?t=${timestamp}&width=${captchaWidth}"
              style="max-width: ${captchaWidth}px; max-height: ${captchaHeight}px; width: ${captchaWidth}px; height: ${captchaHeight}px; border: none; overflow: hidden; display: block; margin: 0 auto;"
              scrolling="no"
              frameborder="0"
              title="验证码">
            </iframe>
          `;

      displayElement.innerHTML = iframeHtml;

      console.log("[验证码] 已加载验证码 iframe:", {
        width: captchaWidth,
        height: captchaHeight,
      });

      // loadMobileCaptcha(formType);
    } else {
      displayElement.innerHTML =
        '<span class="text-red-500 text-xs">加载失败</span>';
      console.error(`[验证码] 加载失败: ${result.message || "未知错误"}`);
    }
  } catch (error) {
    displayElement.innerHTML =
      '<span class="text-red-500 text-xs">网络错误</span>';
    console.error(`[验证码] 加载异常:`, error);
  }
}

function refreshCaptcha(formType) {
  // const actualFormType = formType.replace("mobile-", "");
  console.log(`[验证码] 刷新${formType}表单验证码`);
  loadCaptcha(formType);
}
// ==================== 验证码模态窗相关函数 ====================
let pendingSMSContext = null;

async function loadCaptchaModal(requestedWidth) {
  if (await isBehaviorCaptchaProvider()) {
    return loadBehaviorCaptchaModal();
  }

  const displayElement = document.getElementById("captcha-modal-display");

  if (!displayElement) {
    console.error("[验证码模态窗] 未找到验证码显示元素");
    return;
  }

  destroyBehaviorCaptchaInstance("modal");
  setCaptchaModalInputBehaviorMode(false);
  setCaptchaDisplayBehaviorMode(displayElement, false);
  captchaIds_modal = "";
  displayElement.innerHTML =
    '<span class="text-slate-400 text-xs">加载中...</span>';

  try {
    // 优先使用调用者传入的宽度，其次使用全局记录的modal请求宽度
    let containerWidth = requestedWidth || captchaModalRequestedWidth || null;
    console.log(`[验证码模态窗] 请求容器宽度: ${containerWidth || "默认"}`);
    const url = containerWidth
      ? `/api/captcha/get?width=${containerWidth}`
      : `/api/captcha/get`;

    const response = await fetch(url, {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });

    const result = await response.json();

    if (result.success && result.captcha_id) {
      const uuidRegex =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
      if (!uuidRegex.test(result.captcha_id)) {
        console.error("[验证码模态窗] 无效的captcha_id格式，可能存在安全风险");
        displayElement.innerHTML =
          '<span class="text-red-500 text-xs">验证码ID格式错误</span>';
        return;
      }

      // captchaIds.modal = result.captcha_id;
      captchaIds_modal = result.captcha_id;

      // 如果后端返回了宽高信息，则以后端优先，否则以请求的containerWidth回退，再以默认值回退
      const returnedWidth = result.width || containerWidth || 343;
      const returnedHeight = result.height || 119;

      console.log(
        `[验证码模态窗] 使用验证码尺寸: ${returnedWidth}x${returnedHeight}`,
      );

      displayElement.style.width = `${returnedWidth}px`;
      displayElement.style.height = `${returnedHeight}px`;

      console.log(
        `[验证码模态窗] 设置显示元素尺寸: ${displayElement.style.width}x${displayElement.style.height}`,
      );

      const timestamp = Date.now();
      const captchaWidth = returnedWidth;
      const captchaHeight = returnedHeight;

      console.log(
        `[验证码模态窗] 验证码尺寸: ${captchaWidth}x${captchaHeight}`,
      );

      // 确保在modal中显示容器的宽度与iframe一致
      const containerElem = document.getElementById(
        "send_sms_code_captcha_container",
      );
      if (containerElem) {
        containerElem.style.width = `${captchaWidth}px`;
      }

      const iframeHtml = `
            <iframe 
              src="/api/captcha/html/${result.captcha_id}?t=${timestamp}&width=${captchaWidth}"
              style="max-width: ${captchaWidth}px; max-height: ${captchaHeight}px; width: ${captchaWidth}px; height: ${captchaHeight}px; border: none; overflow: hidden; display: block; margin: 0 auto;"
              scrolling="no"
              frameborder="0"
              title="验证码">
            </iframe>
          `;

      displayElement.innerHTML = iframeHtml;

      console.log("[验证码模态窗] 验证码加载成功");
    } else {
      displayElement.innerHTML =
        '<span class="text-red-500 text-xs">加载失败</span>';
      console.error("[验证码模态窗] 加载失败:", result.message || "未知错误");
    }
  } catch (error) {
    displayElement.innerHTML =
      '<span class="text-red-500 text-xs">网络错误</span>';
    console.error("[验证码模态窗] 加载异常:", error);
  }
}

function refreshCaptchaModal(options = {}) {
  console.log("[验证码模态窗] 刷新验证码");
  if (options.resetBehaviorCaptcha === true) {
    resetBehaviorCaptchaModal();
  }
  // 使用上次打开模态框时记录的宽度（如果有）
  loadCaptchaModal(captchaModalRequestedWidth);
}

function openCaptchaModal(context) {
  pendingSMSContext = context;

  const modal = document.getElementById("captcha-verification-modal");
  const input = document.getElementById("captcha-modal-input");

  if (!modal) {
    logMessage_Error("[验证码模态窗] 找不到captcha-verification-modal元素");
    // showModalAlert("验证码模态框加载失败，请刷新页面重试", "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "验证码模态框加载失败，请刷新页面重试",
    });
    return;
  }

  if (!input) {
    logMessage_Error("[验证码模态窗] 找不到captcha-modal-input输入框");
    // showModalAlert("验证码输入框加载失败，请刷新页面重试", "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "验证码输入框加载失败，请刷新页面重试",
    });
    return;
  }

  try {
    modal.classList.remove("hidden");
    // 计算模态框内部内容包装器的可用宽度，以便传给后端并设置验证码容器宽度
    let requestedWidth = null;
    const wrapper = document.getElementById(
      "send_sms_code_modal_content_wrapper",
    );
    // const containerElem = document.getElementById("send_sms_code_captcha_container");
    if (wrapper) {
      const style = window.getComputedStyle(wrapper);
      const paddingLeft = parseFloat(style.paddingLeft) || 0;
      const paddingRight = parseFloat(style.paddingRight) || 0;
      // 参考 auth-login 计算方式，保留一定内边距
      requestedWidth = wrapper.clientWidth - paddingLeft - paddingRight - 200;
      console.log(`[验证码模态窗] 计算容器宽度: ${requestedWidth}px`);
      if (requestedWidth > 600) requestedWidth = 600;
      if (requestedWidth < 200) requestedWidth = 200;
      // 将计算到的宽度应用到容器（视觉一致）
      // containerElem.style.width = `${requestedWidth}px`;
    }

    // 记录为全局请求宽度，供后续刷新使用
    captchaModalRequestedWidth = requestedWidth;
    console.log(`[验证码模态窗] 计算请求宽度: ${requestedWidth}px`);

    modal.style.display = "flex";
    modal.style.zIndex = "20001";
    input.value = "";

    // 加载验证码并传入期望的宽度
    loadCaptchaModal(requestedWidth);

    setTimeout(() => {
      if (input && modal.style.display !== "none") {
        input.focus();
        logMessage_Info("[验证码模态窗] 模态框已打开并聚焦到输入框");
      }
    }, 300);
  } catch (error) {
    logMessage_Error("[验证码模态窗] 打开模态框时发生错误:", error);
    // showModalAlert("打开验证码窗口时出错", "错误");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: "打开验证码窗口时出错",
    });
  }
}

function closeCaptchaModal() {
  const modal = document.getElementById("captcha-verification-modal");
  const input = document.getElementById("captcha-modal-input");

  if (modal) {
    modal.style.display = "none";
    modal.classList.add("hidden");

    if (input) input.value = "";

    // 修复：如果存在挂起的上下文（说明流程被取消），恢复来源按钮状态
    if (pendingSMSContext && pendingSMSContext.button) {
      pendingSMSContext.button.disabled = false;
      if (pendingSMSContext.originalText) {
        pendingSMSContext.button.textContent = pendingSMSContext.originalText;
      }
    }

    pendingSMSContext = null;
  }
}

async function confirmCaptchaAndSendSMS() {
  const captchaInput = document.getElementById("captcha-modal-input");
  const isBehaviorMode = captchaInput?.dataset.behaviorCaptcha === "true";
  const captcha = isBehaviorMode
    ? BEHAVIOR_CAPTCHA_VERIFIED_CODE
    : captchaInput?.value?.trim() || "";

  if (isBehaviorMode && isMissingCaptchaId(captchaIds_modal)) {
    Swal.fire({
      icon: "warning",
      title: "请完成人机验证",
      text: "请先完成上方人机验证",
    });
    return;
  }

  if (!isBehaviorMode && !captcha) {
    // showModalAlert("请输入验证码");
    Swal.fire({
      icon: "warning",
      title: "请输入验证码",
      text: "请输入图形验证码",
    });
    return;
  }

  if (!pendingSMSContext) {
    console.error("[验证码模态窗] 没有待发送的SMS上下文");
    closeCaptchaModal();
    return;
  }

  const confirmBtn = document.getElementById("captcha-modal-confirm-btn");
  confirmBtn.disabled = true;
  const originalText = confirmBtn.textContent;
  confirmBtn.textContent = "发送中...";

  try {
    await sendSMSWithCaptcha(
      pendingSMSContext.phone,
      captcha,
      pendingSMSContext.button,
      pendingSMSContext.originalText,
      pendingSMSContext.scene,
    );

    // 修复：发送成功后清除上下文，防止 closeCaptchaModal 错误地重置倒计时按钮
    pendingSMSContext = null;

    closeCaptchaModal();
  } catch (error) {
    console.error("[验证码模态窗] 发送SMS失败:", error);
    refreshCaptchaModal({ resetBehaviorCaptcha: true });
    const captchaModalInput = document.getElementById("captcha-modal-input");
    if (captchaModalInput) {
      captchaModalInput.value = "";
      captchaModalInput.focus();
    }
  } finally {
    confirmBtn.disabled = false;
    confirmBtn.textContent = originalText;
  }
}

async function sendSMSWithCaptcha(
  phone,
  captcha,
  button,
  originalText,
  scene = null,
) {
  // if(captchaIds.modal===null || captchaIds.modal===undefined || captchaIds.modal==="" || captchaIds.modal=="null" || captchaIds.modal=="undefined" || captchaIds.modal=="NULL"){
  if (isMissingCaptchaId(captchaIds_modal)) {
    const modalInput = document.getElementById("captcha-modal-input");
    const isBehaviorMode = modalInput?.dataset.behaviorCaptcha === "true";
    if (modalInput) {
      modalInput.value = "";
      modalInput.focus();
    }
    // showModalAlert("验证码未加载或已过期，请刷新后重试", "登录失败");
    Swal.fire({
      icon: "warning",
      title: "发生失败",
      text: isBehaviorMode
        ? "请先完成人机验证"
        : "验证码未加载或已过期，请刷新后重试",
    });

    // document.getElementById("modal-login-captcha-refresh").click();
    loadCaptcha("register");
    return;
  }
  try {
    const requestBody = {
      phone: phone,
      captcha: captcha,
      // captcha_id: captchaIds.modal,
      captcha_id: captchaIds_modal,
    };
    if (scene) {
      requestBody.scene = scene;
    }
    const response = await fetch("/api/sms/send_code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(requestBody),
    });

    const result = await response.json();

    if (result.success) {
      // showModalAlert("验证码已发送，请查收短信");
      Swal.fire({
        icon: "success",
        title: "提示",
        text: "验证码已发送，请查收短信",
      });

      let countdown = 60;
      button.disabled = true;

      const timer = setInterval(() => {
        if (countdown > 0) {
          button.textContent = `${countdown}秒后重试`;
          countdown--;
        } else {
          clearInterval(timer);
          button.disabled = false;
          button.textContent = originalText;
        }
      }, 1000);
    } else {
      const modalInput = document.getElementById("captcha-modal-input");
      if (modalInput) {
        modalInput.value = "";
        modalInput.focus();
      }
      throw new Error(result.message || "发送失败，请重试");
    }
  } catch (error) {
    console.error("[SMS] 发送异常:", error);
    // showModalAlert(error.message || "发送失败，请重试");
    Swal.fire({
      icon: "error",
      title: "错误",
      text: error.message || "发送失败，请重试",
    });
    throw error;
  }
}

async function handleAuthLogin(isMobile_use = false) {
  const loginBtn = $("auth-login-btn");
  const login_id = $("auth-username").value.trim();
  const password = $("auth-password").value.trim();
  const sms_code = $("auth-sms-code").value.trim();
  const captcha = $("auth-login-captcha").value.trim();
  const isBehaviorCaptchaMode =
    typeof isBehaviorCaptchaProvider === "function" &&
    (await isBehaviorCaptchaProvider());
  const resetLoginCaptcha = () => {
    if (typeof resetBehaviorCaptchaForForm === "function") {
      resetBehaviorCaptchaForForm(
        isMobile_use === false ? "login" : "mobile-login",
      );
    }
  };
  const isMissingLoginCaptchaId = (value) => {
    if (typeof isMissingCaptchaId === "function") {
      return isMissingCaptchaId(value);
    }
    const normalized = String(value ?? "").trim().toLowerCase();
    return !normalized || normalized === "null" || normalized === "undefined";
  };

  let login_mode = "username";
  let login_verification_method = "password";

  if ($("auth-login-phone-btn").classList.contains("font-semibold")) {
    login_mode = "phone";
  }
  if (!$("auth-sms-section").classList.contains("hidden")) {
    login_verification_method = "sms";
  }
  if (!isBehaviorCaptchaMode && !captcha) {
    // showModalAlert("请输入图形验证码", "登录失败");
    Swal.fire({
      icon: "warning",
      title: "登录失败",
      text: "请输入图形验证码",
    });
    if (isMobile_use === false) {
      refreshCaptcha("login");
    } else {
      refreshCaptcha("mobile-login");
    }
    $("auth-login-captcha").value = "";
    const mobileLoginCaptcha = document.getElementById("mobile-login-captcha");
    if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
    return;
  }
  if (!login_id) {
    // showModalAlert("请输入用户名或手机号", "登录失败");
    Swal.fire({
      icon: "warning",
      title: "登录失败",
      text: "请输入用户名或手机号",
    });
    if (isMobile_use === false) {
      refreshCaptcha("login");
    } else {
      refreshCaptcha("mobile-login");
    }
    $("auth-login-captcha").value = "";
    const mobileLoginCaptcha = document.getElementById("mobile-login-captcha");
    if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
    return;
  }

  if (login_mode === "username") {
    if (!password) {
      // showModalAlert("请输入密码", "登录失败");
      Swal.fire({
        icon: "warning",
        title: "登录失败",
        text: "请输入密码",
      });
      resetLoginCaptcha();
      if (isMobile_use === false) {
        refreshCaptcha("login");
      } else {
        refreshCaptcha("mobile-login");
      }
      $("auth-login-captcha").value = "";
      const mobileLoginCaptcha = document.getElementById("mobile-login-captcha");
      if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
      return;
    }
    if (password.length < 6 && login_id !== "admin") {
      // showModalAlert("密码长度至少6个字符", "登录失败");
      Swal.fire({
        icon: "warning",
        title: "登录失败",
        text: "密码长度至少6个字符",
      });
      if (isMobile_use === false) {
        refreshCaptcha("login");
      } else {
        refreshCaptcha("mobile-login");
      }
      $("auth-login-captcha").value = "";
      const mobileLoginCaptcha = document.getElementById("mobile-login-captcha");
      if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
      return;
    }
  } else if (login_mode === "phone") {
    if (!validateInput(login_id, "phone").valid) {
      // showModalAlert("手机号格式不正确", "登录失败");
      Swal.fire({
        icon: "warning",
        title: "登录失败",
        text: "手机号格式不正确",
      });
      return;
    }

    if (login_verification_method === "password") {
      if (!password) {
        // showModalAlert("请输入密码", "登录失败");
        Swal.fire({
          icon: "warning",
          title: "登录失败",
          text: "请输入密码",
        });
        if (isMobile_use === false) {
          refreshCaptcha("login");
        } else {
          refreshCaptcha("mobile-login");
        }
        $("auth-login-captcha").value = "";
        const mobileLoginCaptcha = document.getElementById("mobile-login-captcha");
        if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
        return;
      }
      if (password.length < 6) {
        // showModalAlert("密码长度至少6个字符", "登录失败");
        Swal.fire({
          icon: "warning",
          title: "登录失败",
          text: "密码长度至少6个字符",
        });
        if (isMobile_use === false) {
          refreshCaptcha("login");
        } else {
          refreshCaptcha("mobile-login");
        }
        $("auth-login-captcha").value = "";
        const mobileLoginCaptcha = document.getElementById("mobile-login-captcha");
        if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
        return;
      }
    } else if (login_verification_method === "sms") {
      if (!sms_code) {
        // showModalAlert("请输入短信验证码", "登录失败");
        Swal.fire({
          icon: "warning",
          title: "登录失败",
          text: "请输入短信验证码",
        });
        return;
      }
      if (sms_code.length !== 6 || !/^\d{6}$/.test(sms_code)) {
        // showModalAlert("短信验证码格式不正确", "登录失败");
        Swal.fire({
          icon: "warning",
          title: "登录失败",
          text: "短信验证码格式不正确",
        });
        return;
      }
    }
  }
  const request_body = {};
  capturePreLoginBackgroundSnapshot(isMobile_use ? "mobile" : "pc");
  request_body.background_preview = getBackgroundPreviewPayload();

  if (login_mode === "username") {
    request_body.auth_username = login_id;
  } else if (login_mode === "phone") {
    request_body.auth_phone = login_id;
  }
  if (login_verification_method === "password") {
    request_body.auth_password = password;
  } else if (login_verification_method === "sms") {
    request_body.auth_sms_code = sms_code;
  }

  request_body.captcha = isBehaviorCaptchaMode
    ? BEHAVIOR_CAPTCHA_VERIFIED_CODE
    : captcha;

  console.log("[登录] isMobile_use:", isMobile_use);
  console.log("[登录] 验证码状态:", {
    desktop: Boolean(captchaIds_login),
    mobile: Boolean(captchaIds_mobile_login),
  });
  if (isMobile_use === true) {
    // request_body.captcha_id = captchaIds["mobile-login"];
    request_body.captcha_id = captchaIds_mobile_login;
  } else {
    // request_body.captcha_id = captchaIds.login;
    request_body.captcha_id = captchaIds_login;
  }
  console.log("[登录] 已附带验证码ID:", Boolean(request_body.captcha_id));

  if (isMissingLoginCaptchaId(request_body.captcha_id)) {
    // showModalAlert("验证码未加载或已过期，请刷新后重试", "登录失败");
    Swal.fire({
      icon: "warning",
      title: "登录失败",
      text: isBehaviorCaptchaMode
        ? "请先完成人机验证"
        : "验证码未加载或已过期，请刷新后重试",
    });

    // document.getElementById("auth-login-captcha-refresh").click();
    // document.getElementById("mobile-login-captcha-refresh").click();

    resetLoginCaptcha();
    if (isMobile_use === false) {
      refreshCaptcha("login");
    } else {
      refreshCaptcha("mobile-login");
    }

    return;
  }
  authLoginInProgress = true;
  themeBackgroundLoginSyncInFlight = true;
  authRequestGeneration += 1;
  const authRequestSessionUUID = getAuthRequestSessionUUID();
  setButtonLoading("auth-login-btn", true, "登录中...");

  try {
    const headers = {
      "Content-Type": "application/json",
    };
    if (isUsableClientSessionUUID(authRequestSessionUUID)) {
      headers["X-Session-ID"] = authRequestSessionUUID;
    }

    const response = await fetch("/auth/login", {
      method: "POST",
      headers: headers,
      credentials: "include",
      body: JSON.stringify(request_body),
    });

    const result = await response.json();

    if (result.success) {
      if (result.requires_2fa) {
        window.temp2FAUsername = result.auth_username || login_id;
        window.temp2FAChallenge = result.two_fa_challenge || "";

        setButtonLoading("auth-login-btn", false);

        const loginForm = $("auth-login-form");
        const tfaForm = $("auth-2fa-form");
        if (loginForm) loginForm.classList.add("hidden");
        if (tfaForm) tfaForm.classList.remove("hidden");

        const tfaCodeInput = $("auth-2fa-code");
        if (tfaCodeInput) {
          tfaCodeInput.value = "";
          tfaCodeInput.focus();
        }

        showAuthSuccess("密码验证成功，请输入验证码");
        return;
      }

      if (result.session_id) {
        const activeSessionId = setActiveLegacySession(result.session_id, {
          promoteAuth: false,
        });
        authSessionUUID = result.auth_session_id || activeSessionId;
        // 重新登录说明用户回到了自己的会话，旧的"返回管理员会话"记录已失效。
        clearAdminReturnOriginState("重新登录");
        logMessage_Info(
          "[登录成功] 会话ID已设置:",
          sessionUUID.substring(0, 16) + "...",
        );
      } else if (result.auth_session_id) {
        authSessionUUID = result.auth_session_id;
        if (typeof resetLegacyRunnerExecution === "function") resetLegacyRunnerExecution();
        sessionUUID = null;
        clearAdminReturnOriginState("重新登录");
        logMessage_Info(
          "[登录成功] 认证会话已建立，请选择或创建业务会话:",
          authSessionUUID.substring(0, 16) + "...",
        );
      }
      authRequestGeneration += 1;

      themeBackgroundLoginSyncInFlight = true;
      await syncThemeFromServer(result.theme, result.theme_style, result.theme_background);

      let successMessage = "登录成功！";

      if (result.multi_device_warning) {
        successMessage += "\n" + result.multi_device_warning;
      }

      if (result.cleanup_message) {
        successMessage += "\n" + result.cleanup_message;
      }

      showAuthSuccess(successMessage);

      // ── 账号注销等待期检测 ──────────────────────────────────────────────────
      // 若该账号正在注销等待期内，弹窗提示管理员并提供撤销选项
      if (
        result.account_cancellation &&
        result.account_cancellation.status === "pending"
      ) {
        const executeAt = result.account_cancellation.execute_at;
        const executeDate = executeAt
          ? new Date(executeAt * 1000).toLocaleString("zh-CN")
          : "未知";
        const cancelResult = await Swal.fire({
          title: "⚠️ 账号注销等待中",
          html: `
            <div style="text-align:left;padding:6px 0;">
              <p style="color:#475569;font-size:14px;margin-bottom:10px;">
                该账号已申请注销，将在 <strong style="color:#dc2626;">${executeDate}</strong> 自动删除。
              </p>
              <p style="color:#64748b;font-size:13px;">继续登录即视为撤销注销申请，账号将恢复正常状态。</p>
            </div>`,
          icon: "warning",
          showCancelButton: true,
          confirmButtonText: "✅ 继续登录（撤销注销）",
          confirmButtonColor: "#16a34a",
          cancelButtonText: "退出登录",
          cancelButtonColor: "#dc2626",
          customClass: { popup: "swal2-neumorphism-popup" },
          reverseButtons: true,
          allowOutsideClick: false,
        });
        if (cancelResult.isConfirmed) {
          // 调用撤销注销接口
          try {
            const revokeResp = await fetch(
              "/auth/user/cancel_account_cancellation",
              {
                method: "POST",
                headers: { "X-Session-ID": getAuthenticatedSessionHeaderValue() },
              },
            );
            const revokeData = await revokeResp.json();
            if (revokeData.success) {
              await Swal.fire({
                title: "注销已撤销",
                text: "账号注销申请已撤销，账号已恢复正常。",
                icon: "success",
                timer: 2000,
                timerProgressBar: true,
                showConfirmButton: false,
                customClass: { popup: "swal2-neumorphism-popup" },
              });
            }
          } catch (_e) {
            /* 静默失败，不阻断登录 */
          }
        } else {
          // 用户选择退出 — 不进入主界面，保持在登录页
          setButtonLoading("auth-login-btn", false);
          return;
        }
      }
      // ── 账号注销等待期检测结束 ───────────────────────────────────────────────

      if (result.token) {
        logMessage_Info("Received auth token (stored in cookie)");
        logMessage_Info("[安全] 登录令牌已生成，有效期1小时");
      }

      if (!result.is_guest) {
        currentUserData.group = result.group || "user";
        currentAuthUsername = result.auth_username;
        currentUserIsGuest = false;
        logMessage_Info(`[系统登录] 权限组已设置为: ${currentUserData.group}`);

        showButtonSuccess("auth-login-btn", "登录成功", 800);

        setTimeout(() => {
          setButtonLoading("auth-login-btn", false);

          $("auth-login-container").classList.add("hidden");
          if (isMobileMode) {
            $("mobile-auth-login-container").classList.add("hidden");
            showMobileSessionPicker();
          } else {
            showSessionPicker();
          }

          logMessage_Info("[会话选择] 请选择要进入的会话，或创建新会话");
          logMessage_Info("[提示] 每个会话都是独立的学校账号登录状态");

          if (result.kicked_sessions_count > 0) {
            logMessage_Info(
              `[多设备检测] 已自动登出该账号在其他 ${result.kicked_sessions_count} 个设备上的会话`,
            );
          }
        }, 1000);
        return;
      }

      setTimeout(async () => {
        $("auth-login-container").classList.add("hidden");
        $("login-container").classList.remove("hidden");

        try {
          await initializeInlineAdminPanel();
        } catch (e) {
          logMessage_Error("初始化管理面板失败:", e);
        }

        const adminBtnLogin = $("show-admin-panel-login");
        if (adminBtnLogin) adminBtnLogin.classList.remove("hidden");
        const adminBtnMulti = $("show-admin-panel-multi");
        if (adminBtnMulti) adminBtnMulti.classList.remove("hidden");
        const sessionsBtnMain = $("show-admin-panel");
        if (sessionsBtnMain) sessionsBtnMain.classList.remove("hidden");

        if (result.is_guest) {
          logMessage_Info(
            "[游客模式] 部分功能受限：无法标记通知已读、无法使用签到功能、无法执行多账号任务",
          );
          logMessage_Info(
            "[游客提示] 请保存当前地址，丢失后无法恢复您的数据！5分钟不活跃会话将被清理。",
          );
        } else {
          logMessage_Info(
            "[注册用户] 您的状态已关联到账号，可在任何设备登录恢复。",
          );
        }
      }, 1000);
    } else {
      setButtonLoading("auth-login-btn", false);
      showButtonError("auth-login-btn", "登录失败");
      
      // 检查是否是手机号未注册的错误
      const isPhoneNotRegistered = result.message && (
        result.message.includes("未注册") ||
        result.message.includes("不存在") ||
        result.message.includes("not registered") ||
        result.message.includes("手机号未绑定")
      );
      
      // 如果是手机号登录且手机号未注册，提示跳转到注册页面
      if (isPhoneNotRegistered && login_mode === "phone") {
        const phoneNumber = login_id;
        const currentSmsCode = sms_code;
        
        Swal.fire({
          icon: "info",
          title: "手机号未注册",
          html: `
            <div class="text-left">
              <p class="mb-3">手机号 <strong class="font-mono">${escapeHtml(phoneNumber)}</strong> 尚未注册。</p>
              <p class="text-sm text-slate-600">是否立即注册？</p>
            </div>
          `,
          showCancelButton: true,
          confirmButtonText: "立即注册",
          confirmButtonColor: "#22c55e",
          cancelButtonText: "取消",
          cancelButtonColor: "#64748b",
        }).then((swalResult) => {
          if (swalResult.isConfirmed) {
            // 跳转到注册选项卡
            handlePhoneNotRegisteredRedirect(phoneNumber, currentSmsCode, isMobile_use);
          }
        });
      } else {
        // 普通登录失败提示
        Swal.fire({
          icon: "error",
          title: "登录失败",
          text: result.message || "登录失败",
        });
      }

      if (isBehaviorCaptchaMode) {
        resetLoginCaptcha();
      }
      if (isMobile_use === false) {
        refreshCaptcha("login");
      } else {
        refreshCaptcha("mobile-login");
      }
      $("auth-login-captcha").value = "";
      const mobileLoginCaptcha = document.getElementById(
        "mobile-login-captcha",
      );
      if (mobileLoginCaptcha) mobileLoginCaptcha.value = "";
    }
  } catch (e) {
    logMessage_Error("登录请求失败:", e);
    setButtonLoading("auth-login-btn", false);
    showButtonError("auth-login-btn", "网络错误");
    // showModalAlert("网络错误，请检查连接后重试", "登录失败");
    Swal.fire({
      icon: "error",
      title: "网络错误",
      text: "网络错误，请检查连接后重试",
    });

    if (isBehaviorCaptchaMode) {
      resetLoginCaptcha();
    }
    if (isMobile_use === false) {
      refreshCaptcha("login");
    } else {
      refreshCaptcha("mobile-login");
    }
    $("auth-login-captcha").value = "";
    const mobileLoginCaptchaErr = document.getElementById(
      "mobile-login-captcha",
    );
    if (mobileLoginCaptchaErr) mobileLoginCaptchaErr.value = "";
  } finally {
    themeBackgroundLoginSyncInFlight = false;
    authLoginInProgress = false;
  }
}

/**
 * 处理手机号未注册时跳转到注册页面
 * 自动填充手机号和验证码，并延迟验证码有效期
 * @param {string} phoneNumber - 用户输入的手机号
 * @param {string} smsCode - 用户输入的短信验证码
 * @param {boolean} isMobile - 是否为移动端
 */
function handlePhoneNotRegisteredRedirect(phoneNumber, smsCode, isMobile) {
  console.log("[手机号未注册跳转] 开始处理:", {
    isMobile,
    hasPhoneNumber: Boolean(phoneNumber),
    hasSmsCode: Boolean(smsCode),
  });

  if (isMobile) {
    const mobileRegisterTab = document.getElementById("mobile-auth-tab-register");
    if (mobileRegisterTab) {
      mobileRegisterTab.click();
    } else {
      const mobileLoginTab = document.getElementById("mobile-auth-tab-login");
      const mobileLoginForm = document.getElementById("mobile-login-form");
      const mobileRegisterForm = document.getElementById("mobile-register-form");
      const mobile2FAForm = document.getElementById("mobile-auth-2fa-form");

      if (mobileLoginForm) mobileLoginForm.classList.add("hidden");
      if (mobile2FAForm) mobile2FAForm.classList.add("hidden");
      if (mobileRegisterForm) mobileRegisterForm.classList.remove("hidden");

      if (mobileLoginTab) {
        mobileLoginTab.className =
          "flex-1 py-3 font-semibold text-slate-400 border-b-2 border-transparent transition";
      }
      if (mobileRegisterTab) {
        mobileRegisterTab.className =
          "flex-1 py-3 font-semibold text-sky-600 border-b-2 border-sky-600 transition";
      }
    }
  } else {
    switchAuthTab("register");
    const loginTab = document.getElementById("auth-tab-login");
    const registerTab = document.getElementById("auth-tab-register");
    const loginForm = document.getElementById("auth-login-form");
    const registerForm = document.getElementById("auth-register-form");
    if (loginTab && registerTab && loginForm && registerForm) {
      loginTab.classList.remove("text-sky-600", "border-sky-600");
      loginTab.classList.add("text-slate-400", "border-transparent");
      registerTab.classList.add("text-sky-600", "border-sky-600");
      registerTab.classList.remove("text-slate-400", "border-transparent");
      loginForm.classList.add("hidden");
      registerForm.classList.remove("hidden");
    }
  }

  // 填充手机号到注册表单
  const regPhoneInput = document.getElementById(
    isMobile ? "mobile-reg-phone" : "auth-reg-phone",
  );
  if (regPhoneInput) {
    regPhoneInput.value = phoneNumber;
    console.log("[手机号未注册跳转] 已填充手机号:", phoneNumber);
  }

  // 填充验证码到注册表单
  const regSmsCodeInput = document.getElementById(
    isMobile ? "mobile-reg-sms-code" : "auth-reg-sms-code",
  );
  if (regSmsCodeInput && smsCode) {
    regSmsCodeInput.value = smsCode;
    console.log("[手机号未注册跳转] 已填充短信验证码");

    // 调用后端API延长验证码有效期（拒绝/异常也不阻断注册流程）
    (async () => {
      let extendStatusText = "延期状态未知，请尽快完成注册。";
      let effectiveExpireAt = 0;

      try {
        const response = await fetch("/api/sms/extend_code", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            phone: phoneNumber,
          }),
        });

        const data = await response.json();
        const expireAtFromResponse = Number(data.expires_at || 0);
        const remainFromResponse = Number(data.remaining_seconds || 0);

        if (data.success) {
          extendStatusText = "验证码已延期一次。";
        } else if (data.error_code === "EXTEND_LIMIT_REACHED") {
          extendStatusText = "该验证码已达延期上限，本次未再次延期，请尽快完成注册。";
        } else {
          extendStatusText = data.message || "延期状态获取失败，请尽快完成注册。";
        }

        if (expireAtFromResponse > 0) {
          effectiveExpireAt = expireAtFromResponse;
        } else if (remainFromResponse > 0) {
          effectiveExpireAt = Math.floor(Date.now() / 1000) + remainFromResponse;
        }
      } catch (error) {
        console.error("[手机号未注册跳转] 延长验证码请求失败:", error);
        extendStatusText = "延期状态获取失败，请尽快完成注册。";
      }

      let countdownTimer = null;
      fireVerificationCodesModalSwal({
        icon: "success",
        title: "信息已自动填充",
        html: `
          <div class="text-left">
            <p class="mb-2 text-green-600">✅ 手机号和验证码已自动填充</p>
            <p id="reg-sms-expire-countdown" class="text-sm text-slate-600">验证码剩余有效时间：计算中...</p>
            <p class="text-sm text-slate-600 mt-2">${escapeHtml(extendStatusText)}</p>
            <p class="text-sm text-slate-600 mt-2">请设置用户名和密码完成注册。</p>
          </div>
        `,
        confirmButtonText: "我知道了",
        confirmButtonColor: "#22c55e",
        allowOutsideClick: false,
        allowEscapeKey: true,
        didOpen: () => {
          const el = document.getElementById("reg-sms-expire-countdown");
          const update = () => {
            if (!el) return;
            const now = Math.floor(Date.now() / 1000);
            const remain = effectiveExpireAt > 0 ? Math.max(0, effectiveExpireAt - now) : 0;
            if (remain <= 0) {
              el.textContent = "验证码可能已过期，请重新获取。";
              return;
            }
            const m = Math.floor(remain / 60);
            const s = remain % 60;
            el.textContent = `验证码剩余有效时间：${m}分${s}秒`;
          };
          update();
          countdownTimer = setInterval(update, 1000);
        },
        willClose: () => {
          if (countdownTimer) {
            clearInterval(countdownTimer);
            countdownTimer = null;
          }
        },
      }).then(() => {
        const regUsernameInput = document.getElementById(
          isMobile ? "mobile-reg-username" : "auth-reg-username",
        );
        if (regUsernameInput) {
          regUsernameInput.focus();
        }
      });
    })();
  }

  // 刷新注册页验证码
  refreshCaptcha(isMobile ? "mobile-register" : "register");
}

async function handle2FAVerify() {
  const codeInput = $("auth-2fa-code");
  const code = codeInput ? codeInput.value.trim() : "";
  if (!code || code.length !== 6 || !/^[0-9]{6}$/.test(code)) {
    // showModalAlert("请输入有效的6位数字验证码", "2FA验证失败");
    Swal.fire({
      icon: "warning",
      title: "2FA验证失败",
      text: "请输入有效的6位数字验证码",
    });
    return;
  }

  if (!window.temp2FAUsername) {
    // showModalAlert("会话已过期，请重新登录", "2FA验证失败");
    Swal.fire({
      icon: "error",
      title: "会话已过期，请重新登录",
      text: "2FA验证失败",
    });
    const loginForm = $("auth-login-form");
    const tfaForm = $("auth-2fa-form");
    if (loginForm) loginForm.classList.remove("hidden");
    if (tfaForm) tfaForm.classList.add("hidden");
    return;
  }

  authLoginInProgress = true;
  themeBackgroundLoginSyncInFlight = true;
  authRequestGeneration += 1;
  setButtonLoading("auth-2fa-verify-btn", true, "验证中...");

  try {
    const response = await fetch("/auth/2fa/verify_login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      credentials: "include",
      body: JSON.stringify({
        auth_username: window.temp2FAUsername,
        challenge: window.temp2FAChallenge,
        code: code,
        background_preview: getBackgroundPreviewPayload(),
      }),
    });

    const result = await response.json();

    if (result.success) {
      delete window.temp2FAUsername;
      delete window.temp2FAChallenge;

      if (result.session_id) {
        const activeSessionId = setActiveLegacySession(result.session_id, {
          promoteAuth: false,
        });
        authSessionUUID = result.auth_session_id || activeSessionId;
        clearAdminReturnOriginState("2FA验证成功，重新登录");
        logMessage_Info(
          "[2FA验证成功] 会话ID已设置:",
          sessionUUID.substring(0, 16) + "...",
        );
      } else if (result.auth_session_id) {
        authSessionUUID = result.auth_session_id;
        if (typeof resetLegacyRunnerExecution === "function") resetLegacyRunnerExecution();
        sessionUUID = null;
        clearAdminReturnOriginState("2FA验证成功，重新登录");
        logMessage_Info(
          "[2FA验证成功] 认证会话已建立，请选择或创建业务会话:",
          authSessionUUID.substring(0, 16) + "...",
        );
      }
      authRequestGeneration += 1;

      await syncThemeFromServer(result.theme, result.theme_style, result.theme_background);
      showButtonSuccess("auth-2fa-verify-btn", "验证成功", 800);
      showAuthSuccess("2FA验证成功！");
      $("mobile-auth-login-container").classList.add("hidden");
      


      if (!result.is_guest) {
        setTimeout(() => {
          setButtonLoading("auth-2fa-verify-btn", false);

          $("auth-login-container").classList.add("hidden");
          if (isMobileMode) {
            showMobileSessionPicker();}
            else {
          showSessionPicker();
            }

          logMessage_Info("[会话选择] 请选择要进入的会话，或创建新会话");
          logMessage_Info("[提示] 每个会话都是独立的学校账号登录状态");

          const loginForm = $("auth-login-form");
          const tfaForm = $("auth-2fa-form");
          if (loginForm) loginForm.classList.remove("hidden");
          if (tfaForm) tfaForm.classList.add("hidden");
          if (codeInput) codeInput.value = "";
        }, 1000);
      }
    } else {
      setButtonLoading("auth-2fa-verify-btn", false);
      showButtonError("auth-2fa-verify-btn", "验证失败");
      // showModalAlert(result.message || "验证码错误", "2FA验证失败");
      Swal.fire({
        icon: "error",
        title: "2FA验证失败",
        text: result.message || "验证码错误",
      });
      if (codeInput) {
        codeInput.value = "";
        codeInput.focus();
      }
    }
  } catch (e) {
    logMessage_Error("2FA验证请求失败:", e);
    setButtonLoading("auth-2fa-verify-btn", false);
    showButtonError("auth-2fa-verify-btn", "网络错误");
    // showModalAlert("网络错误，请检查连接后重试", "2FA验证失败");
    Swal.fire({
      icon: "error",
      title: "网络错误",
      text: "网络错误，请检查连接后重试",
    });
  } finally {
    themeBackgroundLoginSyncInFlight = false;
    authLoginInProgress = false;
  }
}

async function handleAuthRegister(isMobile_use = false) {
  // ── 读取注册表单字段（PC 端与移动端共用同一组字段 ID）──
  const username = $("auth-reg-username").value.trim();
  const phone = $("auth-reg-phone").value.trim();
  const smsCode = $("auth-reg-sms-code").value.trim();
  const nickname_Raw = $("auth-reg-nickname").value.trim();
  const captcha = $("auth-register-captcha").value.trim();
  const isBehaviorCaptchaMode = await isBehaviorCaptchaProvider();

  // 昵称为空时默认使用用户名
  let nickname;
  if (nickname_Raw === "" || nickname_Raw === null) {
    nickname = username;
  } else {
    nickname = nickname_Raw;
  }

  const avatarFile = registrationCroppedAvatarBlob;
  const password = $("auth-reg-password").value.trim();
  const passwordConfirm = $("auth-reg-password-confirm").value.trim();

  if (!isBehaviorCaptchaMode && !captcha) {
    // showModalAlert("请输入图形验证码", "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: "请输入图形验证码",
    });
    return;
  }

  if (!username || !password || !passwordConfirm) {
    // showModalAlert("请填写所有必填字段（用户名、密码）", "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: "请填写所有必填字段（用户名、密码）",
    });
    return;
  }

  const usernameValidation = validateInput(username, "username");
  if (!usernameValidation.valid) {
    // showModalAlert(usernameValidation.message, "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: usernameValidation.message,
    });
    return;
  }
  if (/[一-龥]/.test(username)) {
    // showModalAlert("用户名不能包含中文字符", "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: "用户名不能包含中文字符",
    });
    return;
  }

  const passwordValidation = validateInput(password, "password");
  if (!passwordValidation.valid) {
    // showModalAlert(passwordValidation.message, "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: passwordValidation.message,
    });
    return;
  }

  if (password !== passwordConfirm) {
    // showModalAlert("两次输入的密码不一致", "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: "两次输入的密码不一致",
    });
    return;
  }

  // 检查弱密码
  // 在发送注册请求之前，先在前端进行弱密码检测
  // 这可以减少不必要的网络请求，提高用户体验
  var weakCheck = checkWeakPassword(password);
  if (weakCheck.isWeak) {
    // 如果密码过弱，显示具体的错误原因
    // showModalAlert(weakCheck.reason, "密码强度不足");
    Swal.fire({
      icon: "warning",
      title: "密码强度不足",
      text: weakCheck.reason,
    });
    return;
  }

  if (phone && !/^1[3-9]\d{9}$/.test(phone)) {
    // showModalAlert("请输入正确的手机号格式", "注册失败");
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: "请输入正确的手机号格式",
    });
    return;
  }

  if (phone) {
    try {
      const bindResult = await callPythonAPI_raw(
        "/api/auth/check_phone",
        "POST",
        { phone: phone },
      );

      if (bindResult && bindResult.is_bound) {
        const confirmed = await jsShowConfirm(
          "手机号已被绑定",
          `您输入的手机号 ${phone} 已被用户 ${bindResult.bound_to_user} 绑定。\n\n是否继续注册？\n\n如果继续，该手机号将从原账号上强制解绑。`,
        );

        if (!confirmed) {
          logMessage_Info("[注册] 用户取消操作，因为手机号已被绑定。");
          return;
        }
        logMessage_Info("[注册] 用户已确认强制解绑手机号，继续注册...");
      }
    } catch (e) {
      logMessage_Error("检查手机号绑定失败:", e);
      // showModalAlert(`检查手机号失败: ${e.message}，请稍后重试`, "网络错误");
      Swal.fire({
        icon: "error",
        title: "网络错误",
        text: `检查手机号失败: ${e.message}，请稍后重试`,
      });
      return;
    }
  }

  const formData = new FormData();
  formData.append("auth_username", username);
  formData.append("auth_password", password);
  formData.append("phone", phone);
  formData.append("nickname", nickname);
  formData.append("sms_code", smsCode);
  formData.append(
    "captcha",
    isBehaviorCaptchaMode ? BEHAVIOR_CAPTCHA_VERIFIED_CODE : captcha,
  );
  console.log("isMobile_use:", isMobile_use);
  if (isMobile_use === true) {
    // formData.append("captcha_id", captchaIds["mobile-register"]);
    formData.append("captcha_id", captchaIds_mobile_register);
    console.log(
      "获取注册验证码ID（移动端）:",
      Boolean(captchaIds_mobile_register),
    );
  } else {
    // formData.append("captcha_id", captchaIds.register);
    formData.append("captcha_id", captchaIds_register);
    console.log(
      "获取注册验证码ID（桌面端）:",
      Boolean(captchaIds_register),
    );
  }

  if (avatarFile) {
    formData.append("avatar", avatarFile, avatarFile.name || "avatar.jpg");
  }

  if (isMissingCaptchaId(formData.get("captcha_id"))) {
    Swal.fire({
      icon: "warning",
      title: "注册失败",
      text: isBehaviorCaptchaMode
        ? "请先完成人机验证"
        : "验证码未加载或已过期，请刷新后重试",
    });

    // document.getElementById("auth-register-btn").click();
    // document.getElementById("mobile-register-captcha-refresh").click();
    if (isMobile_use === false) {
      refreshCaptcha("register");
    } else {
      refreshCaptcha("mobile-register");
    }

    return;
  }
  setButtonLoading("auth-register-btn", true, "注册中...");

  try {
    const response = await fetch("/auth/register", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (result.success) {
      showButtonSuccess("auth-register-btn", "注册成功");

      if (isMobile_use === false) {
        // ── PC 端：清空注册表单 ──
        document.getElementById("auth-reg-username").value = "";
        document.getElementById("auth-reg-phone").value = "";
        document.getElementById("auth-reg-sms-code").value = "";
        document.getElementById("auth-reg-nickname").value = "";
        document.getElementById("auth-reg-password").value = "";
        document.getElementById("auth-reg-password-confirm").value = "";
        document.getElementById("auth-register-captcha").value = "";
        setRegistrationAvatarPreview("auth-reg-avatar-preview", null);

        // 切换回登录 Tab，并预填注册时使用的用户名 / 密码
        switchAuthTab("login");
        document.getElementById("auth-username").value = username;
        document.getElementById("auth-password").value = password;
      } else {
        // ── 移动端：清空注册表单 ──
        document.getElementById("mobile-reg-username").value = "";
        document.getElementById("mobile-reg-phone").value = "";
        document.getElementById("mobile-reg-sms-code").value = "";
        document.getElementById("mobile-reg-nickname").value = "";
        setRegistrationAvatarPreview("mobile-reg-avatar-preview", null);
        document.getElementById("mobile-reg-password").value = "";
        document.getElementById("mobile-reg-password-confirm").value = "";
        document.getElementById("mobile-register-captcha").value = "";

        // 切换回登录 Tab，并预填注册时使用的用户名 / 密码
        const mobileLoginTab = document.getElementById("mobile-auth-tab-login");
        if (mobileLoginTab) mobileLoginTab.click();
        document.getElementById("mobile-auth-username").value = username;
        document.getElementById("mobile-auth-password").value = password;
      }

      // 刷新注册验证码（以备用户下次再打开注册表单）
      setTimeout(() => {
        refreshCaptcha(isMobile_use ? "mobile-register" : "register");
      }, 500);

      // 通知用户注册成功，并告知凭据已自动填入登录框
      Swal.fire({
        icon: "success",
        title: "注册成功！",
        // text: "已自动填写登录信息，请直接点击「登录」按钮登录。",
        text: "注册成功！请点击[登录]按钮进行登录。",
      });
    } else {
      setButtonLoading("auth-register-btn", false);
      showButtonError("auth-register-btn", "注册失败");
      // showModalAlert(result.message || "注册失败", "注册失败");
      Swal.fire({
        icon: "error",
        title: "注册失败",
        text: result.message || "注册失败",
      });

      resetBehaviorCaptchaForForm(isMobile_use === false ? "register" : "mobile-register");
      if (isMobile_use === false) {
        refreshCaptcha("register");
      } else {
        refreshCaptcha("mobile-register");
      }
      $("auth-register-captcha").value = "";
      const mobileRegCaptcha = document.getElementById(
        "mobile-register-captcha",
      );
      if (mobileRegCaptcha) mobileRegCaptcha.value = "";
    }
  } catch (e) {
    logMessage_Error("注册请求失败:", e);
    setButtonLoading("auth-register-btn", false);
    showButtonError("auth-register-btn", "网络错误");
    // showModalAlert("网络错误，请检查连接后重试", "注册失败");
    Swal.fire({
      icon: "error",
      title: "注册失败",
      text: "网络错误，请检查连接后重试",
    });

    resetBehaviorCaptchaForForm(isMobile_use === false ? "register" : "mobile-register");
    if (isMobile_use === false) {
      refreshCaptcha("register");
    } else {
      refreshCaptcha("mobile-register");
    }
    $("auth-register-captcha").value = "";
    const mobileRegCaptchaErr = document.getElementById(
      "mobile-register-captcha",
    );
    if (mobileRegCaptchaErr) mobileRegCaptchaErr.value = "";
  } finally {
    registrationCroppedAvatarBlob = null;
    setButtonLoading("auth-register-btn", false);
  }
}

function getBackgroundPreviewPayload() {
  return currentThemeBackgroundAssignment
    ? {
        bundle_id: currentThemeBackgroundAssignment.bundle_id || "",
        pc: currentThemeBackgroundAssignment.pc || null,
        mobile: currentThemeBackgroundAssignment.mobile || null,
      }
    : null;
}

function buildQuickLoginSessionViewModel(payload) {
  const sessions = Array.isArray(payload?.sessions) ? payload.sessions : [];
  return sessions
    .filter((item) => item && item.session_id)
    .sort((left, right) => {
      if (left.is_current !== right.is_current) {
        return left.is_current ? -1 : 1;
      }
      return Number(right.last_activity || 0) - Number(left.last_activity || 0);
    });
}

async function loadSiteIdentityBootstrap() {
  try {
    const bootstrapUuid = resolveThemeRequestSessionUUID();
    const endpoint = bootstrapUuid
      ? `/api/site/bootstrap?uuid=${encodeURIComponent(bootstrapUuid)}`
      : "/api/site/bootstrap";
    const response = await fetch(endpoint, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    const result = await response.json();
    if (!response.ok || !result.success) return result;
    applyThemeBackgroundAssignment(result.theme_background, { bound: result.theme_background?.source !== "anonymous_preview" });
    if (result.identity?.quick_login_available) {
      const confirmation = await Swal.fire({
        icon: "question",
        title: "检测到之前的登录记录",
        text: "是否使用已有会话快捷登录？",
        confirmButtonText: "快捷登录",
        cancelButtonText: "稍后",
        showCancelButton: true,
      });
      if (confirmation.isConfirmed) {
        const sessionsResponse = await fetch("/auth/quick_login/sessions", {
          credentials: "include",
        });
        const sessionsResult = await sessionsResponse.json();
        if (sessionsResponse.ok && sessionsResult.success) {
          window.quickLoginSessions = buildQuickLoginSessionViewModel(
            sessionsResult,
          );
          showSessionPicker();
        }
      }
    }
    return result;
  } catch (error) {
    logMessage_Warning("[站点初始化] 身份检查失败:", error);
    return null;
  }
}

async function handleGuestLogin() {
  try {
    const newUUID = generateUUID();

    const response = await fetch("/auth/guest_login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": newUUID,
      },
      credentials: "include",
      body: JSON.stringify({
        background_preview: getBackgroundPreviewPayload(),
      }),
    });

    const result = await response.json();

    if (result.success) {
      showAuthSuccess("以游客身份登录成功！正在跳转...");
      setTimeout(() => {
        window.location.href = buildLegacyUiPath(`/uuid=${newUUID}`);
      }, 1000);
    } else {
      if (result.code === "guest_limit_reached") {
        Swal.fire({
          icon: "warning",
          title: "访客名额已满",
          text: result.message || "当前访客数量已达上限，请稍后重试或注册账号",
        });
        return;
      }
      // showModalAlert(result.message || "游客登录失败", "登录失败");
      Swal.fire({
        icon: "error",
        title: "登录失败",
        text: result.message || "游客登录失败",
      });
    }
  } catch (e) {
    // showModalAlert("游客登录请求失败：" + e.message, "登录失败");
    Swal.fire({
      icon: "error",
      title: "登录失败",
      text: "游客登录请求失败：" + e.message,
    });
  }
}

function generateUUID() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
if (typeof window !== "undefined") {
  window.addEventListener("load", () => {
    const loginTab = $("auth-tab-login");
    const registerTab = $("auth-tab-register");
    if (loginTab)
      loginTab.addEventListener("click", () => switchAuthTab("login"));
    if (registerTab)
      registerTab.addEventListener("click", () => switchAuthTab("register"));

    const loginBtn = $("auth-login-btn");
    if (loginBtn) loginBtn.addEventListener("click", () => handleAuthLogin());

    const registerBtn = $("auth-register-btn");
    if (registerBtn)
      registerBtn.addEventListener("click", () => handleAuthRegister());

    const guestBtn = $("auth-guest-btn");
    if (guestBtn) guestBtn.addEventListener("click", handleGuestLogin);

    const tfa2VerifyBtn = $("auth-2fa-verify-btn");
    if (tfa2VerifyBtn) tfa2VerifyBtn.addEventListener("click", handle2FAVerify);

    const tfa2BackBtn = $("auth-2fa-back-btn");
    if (tfa2BackBtn)
      tfa2BackBtn.addEventListener("click", () => {
        const loginForm = $("auth-login-form");
        const tfaForm = $("auth-2fa-form");
        if (loginForm) loginForm.classList.remove("hidden");
        if (tfaForm) tfaForm.classList.add("hidden");
        delete window.temp2FAUsername;
        delete window.temp2FAChallenge;
        const tfaCodeInput = $("auth-2fa-code");
        if (tfaCodeInput) tfaCodeInput.value = "";
      });

    const authUsername = $("auth-username");
    const authPassword = $("auth-password");
    if (authUsername)
      authUsername.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleAuthLogin();
      });
    if (authPassword)
      authPassword.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleAuthLogin();
      });

    const auth2FACode = $("auth-2fa-code");
    if (auth2FACode)
      auth2FACode.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handle2FAVerify();
      });

    const authRegPassword = $("auth-reg-password-confirm");
    if (authRegPassword)
      authRegPassword.addEventListener("keypress", (e) => {
        if (e.key === "Enter") handleAuthRegister();
      });

    const authLoginCaptcha = $("auth-login-captcha");
    if (authLoginCaptcha) {
      authLoginCaptcha.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          handleAuthLogin();
        }
      });
    }

    const authRegisterCaptcha = $("auth-register-captcha");
    if (authRegisterCaptcha) {
      authRegisterCaptcha.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          handleAuthRegister();
        }
      });
    }

    const adminUsersSearchInput = $("admin-users-search-input_modal");
    if (adminUsersSearchInput) {
      adminUsersSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          loadAdminUsers();
        }
      });
    }

    const mobileAdminUsersSearchInput = $("mobile-multi-admin-users-search-input");
    if (mobileAdminUsersSearchInput) {
      mobileAdminUsersSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          loadAdminUsers();
        }
      });
    }

    const adminBillingSearchInput = $("admin-billing-search-input");
    if (adminBillingSearchInput) {
      adminBillingSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          loadAdminBillingList();
        }
      });
    }

    const adminBillingLogsSearchInput = $("admin-billing-logs-search-input_modal");
    if (adminBillingLogsSearchInput) {
      adminBillingLogsSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          loadAdminBillingLogs(1);
        }
      });
    }

    const mobileAdminBillingSearchInput = $("mobile-multi-admin-billing-search-input");
    if (mobileAdminBillingSearchInput) {
      mobileAdminBillingSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          loadMobileMultiAdminBillingList();
        }
      });
    }

    const mobileBillingLogsSearchInput = $("mobile-billing-logs-search-input");
    if (mobileBillingLogsSearchInput) {
      mobileBillingLogsSearchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          loadMobileBillingLogs(1);
        }
      });
    }

    const profileConfirmPassword = $("profile-confirm-password");
    if (profileConfirmPassword) {
      profileConfirmPassword.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          updatePassword();
        }
      });
    }

    const modifyPhoneCode = $("modify-phone-code");
    if (modifyPhoneCode) {
      modifyPhoneCode.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          confirmModifyPhone();
        }
      });
    }

    const adminPanelBtn = $("show-admin-panel");
    if (adminPanelBtn)
      adminPanelBtn.addEventListener("click", () => toggleAdminPanel(true));

    const adminPanelBtnLogin = $("show-admin-panel-login");
    if (adminPanelBtnLogin)
      adminPanelBtnLogin.addEventListener("click", () =>
        toggleAdminPanel(true),
      );

    const adminPanelBtnMulti = $("show-admin-panel-multi");
    if (adminPanelBtnMulti)
      adminPanelBtnMulti.addEventListener("click", () =>
        toggleAdminPanel(true),
      );

    // --- 新增：使元素可拖拽的通用函数（优先使用 Pointer Events，回退到鼠标/触摸） ---
    function makeDraggable(elementId) {
      const el = document.getElementById(elementId);
      if (!el) return;

      let isDragging = false;
      let hasMoved = false;
      let startX = 0,
        startY = 0,
        initialLeft = 0,
        initialTop = 0;
      let longPressTimer = null;
      const LONG_PRESS_MS = 260;

      const beginDrag = (x, y) => {
        isDragging = true;
        hasMoved = false;
        startX = x;
        startY = y;

        const rect = el.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        el.classList.remove("bottom-4", "right-4", "top-4", "left-4");
        el.style.position = "fixed";
        el.style.left = `${initialLeft}px`;
        el.style.top = `${initialTop}px`;
        el.style.bottom = "auto";
        el.style.right = "auto";
        el.style.transition = "none";
        try {
          if (typeof el._origTouchAction === "undefined")
            el._origTouchAction = el.style.touchAction || "";
          if (typeof el._origUserSelect === "undefined")
            el._origUserSelect = el.style.userSelect || "";
          el.style.touchAction = "none";
          el.style.userSelect = "none";
          el.style.webkitUserSelect = "none";
        } catch (ex) {}
      };

      const clampAndSet = (dx, dy) => {
        let newLeft = initialLeft + dx;
        let newTop = initialTop + dy;
        const maxLeft = window.innerWidth - el.offsetWidth;
        const maxTop = window.innerHeight - el.offsetHeight;
        newLeft = Math.max(0, Math.min(newLeft, maxLeft));
        newTop = Math.max(0, Math.min(newTop, maxTop));
        el.style.left = `${newLeft}px`;
        el.style.top = `${newTop}px`;
      };

      if (window.PointerEvent) {
        // 使用 Pointer Events，兼容鼠标与触摸
        let activePointerId = null;

        const onPointerDown = (e) => {
          if (e.pointerType === "mouse" && e.button !== 0) return;
          const x = e.clientX,
            y = e.clientY;

          if (e.pointerType === "touch") {
            // 触摸使用长按进入拖拽
            startX = x;
            startY = y;
            longPressTimer = setTimeout(() => {
              beginDrag(startX, startY);
              try {
                el.setPointerCapture(e.pointerId);
                activePointerId = e.pointerId;
              } catch (ex) {}
              if (e.cancelable)
                try {
                  e.preventDefault();
                } catch (ex) {}
            }, LONG_PRESS_MS);
          } else {
            // 鼠标或笔：立即拖拽
            beginDrag(x, y);
            try {
              el.setPointerCapture(e.pointerId);
              activePointerId = e.pointerId;
            } catch (ex) {}
          }
        };

        const onPointerMove = (e) => {
          const x = e.clientX,
            y = e.clientY;
          const dx = x - startX,
            dy = y - startY;

          if (!isDragging) {
            if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
              clearTimeout(longPressTimer);
              longPressTimer = null;
            }
            return;
          }

          if (e.cancelable)
            try {
              e.preventDefault();
            } catch (ex) {}
          if (Math.abs(dx) > 5 || Math.abs(dy) > 5) hasMoved = true;
          clampAndSet(dx, dy);
        };

        const onPointerUp = (e) => {
          clearTimeout(longPressTimer);
          longPressTimer = null;
          if (isDragging) {
            isDragging = false;
            el.style.transition = "";
          }
          try {
            if (typeof el._origTouchAction !== "undefined")
              el.style.touchAction = el._origTouchAction || "";
            if (typeof el._origUserSelect !== "undefined")
              el.style.userSelect = el._origUserSelect || "";
            el.style.webkitUserSelect = "";
          } catch (ex) {}
          // 在短时间后清除移动标记，允许用户在拖拽结束后正常点击
          setTimeout(() => {
            hasMoved = false;
          }, 300);
          try {
            if (activePointerId !== null)
              el.releasePointerCapture(activePointerId);
          } catch (ex) {}
          activePointerId = null;
        };

        el.addEventListener("pointerdown", onPointerDown, { passive: false });
        window.addEventListener("pointermove", onPointerMove, {
          passive: false,
        });
        window.addEventListener("pointerup", onPointerUp);
      } else {
        // 回退到鼠标/触摸事件（旧逻辑）
        const getClientXY = (e) => {
          const clientX = e.touches ? e.touches[0].clientX : e.clientX;
          const clientY = e.touches ? e.touches[0].clientY : e.clientY;
          return { x: clientX, y: clientY };
        };

        const onStart = (e) => {
          if (e.type === "mousedown" && e.button !== 0) return;
          const { x, y } = getClientXY(e);

          if (e.type === "mousedown") {
            if (e.cancelable) e.preventDefault();
            beginDrag(x, y);
            document.addEventListener("mousemove", onMove, { passive: false });
            document.addEventListener("mouseup", onEnd);
            return;
          }

          startX = x;
          startY = y;
          hasMoved = false;
          longPressTimer = setTimeout(() => {
            beginDrag(startX, startY);
            if (e.cancelable)
              try {
                e.preventDefault();
              } catch (ex) {}
          }, LONG_PRESS_MS);

          document.addEventListener("touchmove", onMove, { passive: false });
          document.addEventListener("touchend", onEnd);
        };

        const onMove = (e) => {
          const { x, y } = getClientXY(e);
          const dx = x - startX;
          const dy = y - startY;

          if (!isDragging) {
            if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
              clearTimeout(longPressTimer);
              longPressTimer = null;
              document.removeEventListener("touchmove", onMove);
              document.removeEventListener("touchend", onEnd);
            }
            return;
          }

          if (e.cancelable)
            try {
              e.preventDefault();
            } catch (ex) {}
          if (Math.abs(dx) > 5 || Math.abs(dy) > 5) hasMoved = true;
          clampAndSet(dx, dy);
        };

        const onEnd = () => {
          clearTimeout(longPressTimer);
          longPressTimer = null;
          if (isDragging) {
            isDragging = false;
            el.style.transition = "";
          }
          try {
            if (typeof el._origTouchAction !== "undefined")
              el.style.touchAction = el._origTouchAction || "";
            if (typeof el._origUserSelect !== "undefined")
              el.style.userSelect = el._origUserSelect || "";
            el.style.webkitUserSelect = "";
          } catch (ex) {}
          // 在短时间后清除移动标记，允许用户在拖拽结束后正常点击
          setTimeout(() => {
            hasMoved = false;
          }, 300);
          document.removeEventListener("mousemove", onMove);
          document.removeEventListener("touchmove", onMove);
          document.removeEventListener("mouseup", onEnd);
          document.removeEventListener("touchend", onEnd);
        };

        el.addEventListener("mousedown", onStart);
        el.addEventListener("touchstart", onStart, { passive: false });
      }

      // 暴露状态给外部点击事件使用
      el._hasMoved = () => hasMoved;
    }

    // 初始化退出按钮与新手帮助按钮的拖拽功能
    makeDraggable("exit-app-btn");
    try {
      makeDraggable("newbie-help-btn");
    } catch (e) {}

    const exitAppBtn = $("exit-app-btn");
    if (exitAppBtn) {
      exitAppBtn.addEventListener("click", async (e) => {
        // 如果发生了拖拽移动，则阻止点击事件
        if (exitAppBtn._hasMoved && exitAppBtn._hasMoved()) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }

        const isGuestSession =
          typeof currentUserIsGuest !== "undefined" && currentUserIsGuest;
        const confirmed = await jsShowConfirm(
          isGuestSession ? "退出访客会话" : "退出应用",
          isGuestSession
            ? "退出后将销毁当前访客会话，未保存的数据无法恢复。是否继续？"
            : "您确定要退出跑步助手应用吗？",
        );
        if (!confirmed) return;

        authLogoutInProgress = true;
        stopReminderChecker(true);
        try {
          if (isGuestSession) {
            const response = await fetch("/auth/logout", {
              method: "POST",
              credentials: "include",
              headers: {
                "Content-Type": "application/json",
                "X-Session-ID": sessionUUID || "",
              },
            });
            const result = await response.json();
            if (!response.ok || !result.success) {
              throw new Error(result.message || "访客会话退出失败");
            }
            resetLegacyRunnerExecution();
            showSessionMissingOverlay();
            return;
          }
          const result = await callPythonAPI_raw("/api/shutdown", "POST");
          if (!result?.success) throw new Error(result?.message || "退出登录失败");
          resetLegacyRunnerExecution();
          showSessionMissingOverlay();
        } catch (error) {
          console.error("[退出应用] 调用shutdown API失败:", error);
          authLogoutInProgress = false;
          startReminderChecker(sessionUUID, true);
          Swal.fire({
            icon: "error",
            title: "未知错误",
            text: "退出应用失败: " + (error.message || "未知错误"),
          });
        }
      });
    }

    const modalAdminPanel = $("admin-panel-modal");
    if (modalAdminPanel) {
      const modalUsersTab = $("admin-tab-users_modal");
      const modalGroupsTab = $("admin-tab-groups_modal");
      const modalLogsTab = $("admin-tab-logs_modal");
      const modalHealthTab = $("admin-tab-health_modal");
      const modalProfileTab = $("admin-tab-profile_modal");
      const modalSessionsTab = $("admin-tab-sessions_modal");
      const modalMessagesTab = $("admin-tab-messages_modal");
      const modalIpbanTab = $("admin-tab-ipban_modal");
      const modalSmsTab = $("admin-tab-sms_modal");
      const modalConfigTab = $("admin-tab-config_modal");
      const modalCaptchaTab = $("admin-tab-captcha_modal");
      const modalRemindersTab = $("admin-tab-reminders_modal");

      if (modalUsersTab)
        modalUsersTab.addEventListener("click", () => switchAdminTab("users"));
      if (modalGroupsTab)
        modalGroupsTab.addEventListener("click", () =>
          switchAdminTab("groups"),
        );
      if (modalLogsTab)
        modalLogsTab.addEventListener("click", () => switchAdminTab("logs"));
      if (modalHealthTab)
        modalHealthTab.addEventListener("click", () =>
          switchAdminTab("health"),
        );
      if (modalProfileTab)
        modalProfileTab.addEventListener("click", () =>
          switchAdminTab("profile"),
        );
      if (modalSessionsTab)
        modalSessionsTab.addEventListener("click", () =>
          switchAdminTab("sessions"),
        );
      if (modalMessagesTab)
        modalMessagesTab.addEventListener("click", () =>
          switchAdminTab("messages"),
        );
      if (modalIpbanTab)
        modalIpbanTab.addEventListener("click", () => switchAdminTab("ipban"));
      if (modalSmsTab)
        modalSmsTab.addEventListener("click", () => switchAdminTab("sms"));
      if (modalConfigTab)
        modalConfigTab.addEventListener("click", () =>
          switchAdminTab("config"),
        );
      if (modalCaptchaTab)
        modalCaptchaTab.addEventListener("click", () =>
          switchAdminTab("captcha"),
        );
      if (modalRemindersTab)
        modalRemindersTab.addEventListener("click", () =>
          switchAdminTab("reminders"),
        );
      const modalSslTab = $("admin-tab-ssl_modal");
      if (modalSslTab)
        modalSslTab.addEventListener("click", () => switchAdminTab("ssl"));

      // 绑定CDN和密码恢复标签页的点击事件
      //
      // 功能说明：
      // 为管理面板中的CDN和密码恢复标签按钮添加点击事件监听器
      // 点击后调用switchAdminTab函数切换到对应的管理面板
      //
      // CDN标签：用于配置和管理内容分发网络（CDN）设置
      // 密码恢复标签：用于执行密码破解/恢复任务（仅超级管理员）
      const modalCdnTab = $("admin-tab-cdn_modal"); // 获取CDN标签按钮元素
      const modalBruteforceTab = $("admin-tab-bruteforce_modal"); // 获取密码恢复标签按钮元素

      // [CDN标签事件绑定]
      // 检查CDN标签元素是否存在（防止空指针错误）
      if (modalCdnTab) {
        // 添加点击事件监听器
        // 当用户点击CDN标签时，调用switchAdminTab("cdn")切换到CDN管理面板
        modalCdnTab.addEventListener("click", () => switchAdminTab("cdn"));
        // [调试日志] 记录事件绑定成功
        console.log("[事件绑定] CDN标签点击事件已绑定");
      } else {
        // [警告] 如果找不到CDN标签元素，记录警告信息
        // 这可能意味着HTML结构有变化或元素ID不匹配
        console.warn(
          "[事件绑定警告] 未找到CDN标签元素 (ID: admin-tab-cdn_modal)",
        );
      }

      // [密码恢复标签事件绑定]
      // 检查密码恢复标签元素是否存在（防止空指针错误）
      if (modalBruteforceTab) {
        // 添加点击事件监听器
        // 当用户点击密码恢复标签时，调用switchAdminTab("bruteforce")切换到密码恢复面板
        modalBruteforceTab.addEventListener("click", () =>
          switchAdminTab("bruteforce"),
        );
        // [调试日志] 记录事件绑定成功
        console.log("[事件绑定] 密码恢复标签点击事件已绑定");
      } else {
        // [警告] 如果找不到密码恢复标签元素，记录警告信息
        // 可能原因：
        // 1. HTML中元素ID拼写错误
        // 2. 元素尚未加载到DOM中
        // 3. 元素被移除或修改
        console.warn(
          "[事件绑定警告] 未找到密码恢复标签元素 (ID: admin-tab-bruteforce_modal)",
        );
      }

      const tabsContainer = modalAdminPanel.querySelector(
        ".flex.border-b-2.border-slate-200",
      );
      if (tabsContainer) {
        tabsContainer.addEventListener(
          "wheel",
          (event) => {
            event.preventDefault();
            tabsContainer.scrollLeft += event.deltaY;
          },
          { passive: false },
        );

        logMessage_Info("[标签页导航] 已添加滚轮水平滚动支持");
      }

      const viewHistoryBtn = $("view-captcha-history-btn");
      const backToSettingsBtn = $("back-to-captcha-settings-btn");

      if (viewHistoryBtn) {
        viewHistoryBtn.addEventListener("click", () => {
          const captchaPanel = $("admin-captcha-panel_modal");
          const captchaHistoryPanel = $("admin-captcha-history-panel_modal");
          if (captchaPanel) captchaPanel.classList.add("hidden");
          if (captchaHistoryPanel)
            captchaHistoryPanel.classList.remove("hidden");

          loadCaptchaHistory();
          logMessage_Info("[验证码管理] 切换到历史记录视图");
        });
      }

      if (backToSettingsBtn) {
        backToSettingsBtn.addEventListener("click", () => {
          const captchaPanel = $("admin-captcha-panel_modal");
          const captchaHistoryPanel = $("admin-captcha-history-panel_modal");
          if (captchaHistoryPanel) captchaHistoryPanel.classList.add("hidden");
          if (captchaPanel) captchaPanel.classList.remove("hidden");

          logMessage_Info("[验证码管理] 返回设置视图");
        });
      }

      logMessage_Info(
        "Admin Panel Modal Tabs event listeners bound (using _modal IDs).",
      );
    } else {
      logMessage_Error(
        "Could not find admin panel modal element to bind tab events.",
      );
    }

    const refreshUsersBtnModal = $("admin-refresh-users_modal");
    const refreshGroupsBtnModal = $("admin-refresh-groups_modal");
    const refreshLogsBtnModal = $("admin-refresh-logs_modal");
    const refreshHealthBtnModal = $("admin-refresh-health_modal");
    const refreshProfileBtnModal = $("admin-refresh-profile_modal");
    const refreshSessionsBtnModal = $("admin-refresh-sessions_modal");

    if (refreshUsersBtnModal)
      refreshUsersBtnModal.addEventListener("click", () => loadAdminUsers());
    if (refreshGroupsBtnModal)
      refreshGroupsBtnModal.addEventListener("click", loadAdminGroups);
    if (refreshLogsBtnModal) {
      refreshLogsBtnModal.addEventListener("click", () => {
        loadAdminLogs(1);
      });
    }
    const logPrevPageBtn = $("log-prev-page");
    const logNextPageBtn = $("log-next-page");
    const logLimitSelect = $("log-limit-select_modal");
    const logFilterSelect = $("log-level-filter_modal");
    const logKeywordInput = $("log-keyword-filter_modal");

    if (logPrevPageBtn) {
      logPrevPageBtn.addEventListener("click", () => {
        if (currentLogPage > 1) {
          loadAdminLogs(currentLogPage - 1);
        }
      });
    }
    if (logNextPageBtn) {
      logNextPageBtn.addEventListener("click", () => {
        loadAdminLogs(currentLogPage + 1);
      });
    }
    if (logLimitSelect) {
      logLimitSelect.addEventListener("change", () => {
        loadAdminLogs(1);
      });
    }
    if (logFilterSelect) {
      logFilterSelect.addEventListener("change", () => {
        loadAdminLogs(currentLogPage);
      });
    }
    if (logKeywordInput) {
      logKeywordInput.addEventListener("input", () => {
        loadAdminLogs(currentLogPage);
      });
    }

    const logPageSelect = $("log-page-select");
    if (logPageSelect) {
      logPageSelect.addEventListener("change", () => {
        const newPage = parseInt(logPageSelect.value, 10);
        if (newPage && newPage !== currentLogPage) {
          loadAdminLogs(newPage);
        }
      });
    }

    if (refreshHealthBtnModal)
      refreshHealthBtnModal.addEventListener("click", loadHealthStatus);
    if (refreshProfileBtnModal)
      refreshProfileBtnModal.addEventListener("click", () => {
        loadPersonalInfo();
        loadUserBillingList();
      });
    if (refreshSessionsBtnModal)
      refreshSessionsBtnModal.addEventListener("click", loadAdminSessions);
    logMessage_Info(
      "Admin Panel Modal Refresh Buttons event listeners bound (using _modal IDs).",
    );

    const banTypeSelect = $("ban-type");
    const banTargetInput = $("ban-target");
    const banTargetHint = $("ban-target-hint");
    const banTargetError = $("ban-target-error");

    if (banTargetInput) {
      banTargetInput.addEventListener("input", validateIPBanTarget);
    }

    if (banTypeSelect) {
      banTypeSelect.addEventListener("change", () => {
        const type = banTypeSelect.value;
        if (type === "ip") {
          if (banTargetInput)
            banTargetInput.placeholder = "请输入IP地址 (例如: 1.2.3.4)";
          if (banTargetHint) banTargetHint.textContent = "示例: 1.2.3.4";
        } else if (type === "range") {
          if (banTargetInput)
            banTargetInput.placeholder =
              "请输入IP范围 (例如: 192.168.1.1-192.168.1.100)";
          if (banTargetHint)
            banTargetHint.textContent = "示例: 192.168.1.1-192.168.1.100";
        }
        validateIPBanTarget();
      });
    }
    if (banTargetInput) {
      banTargetInput.addEventListener("input", validateIPBanTarget);
    }

    const showSessionsLogin = $("show-sessions-login");
    const showSessionsMain = $("show-admin-panel");
    const showSessionsMulti = $("show-admin-panel-multi");
    if (showSessionsLogin)
      showSessionsLogin.addEventListener("click", () => {
        toggleAdminPanel(true);
        switchAdminTab("sessions");
      });
    if (showSessionsMain)
      showSessionsMain.addEventListener("click", () => {
        toggleAdminPanel(true);
        switchAdminTab("sessions");
      });
    if (showSessionsMulti)
      showSessionsMulti.addEventListener("click", () => {
        toggleAdminPanel(true);
        switchAdminTab("sessions");
      });

    const refreshSessionsInlineBtn = $("admin-refresh-sessions-inline");
    if (refreshSessionsInlineBtn)
      refreshSessionsInlineBtn.addEventListener(
        "click",
        loadAdminSessions_inline,
      );

    const createUserModalBtn = $("admin-create-user_modal");
    const createGroupModalBtn = $("admin-create-group_modal");
    if (createUserModalBtn)
      createUserModalBtn.addEventListener("click", showCreateUserModal);
    if (createGroupModalBtn)
      createGroupModalBtn.addEventListener("click", showCreateGroupModal);

    const viewSchoolAccountsBtn = $("admin-view-school-accounts_modal");
    if (viewSchoolAccountsBtn)
      viewSchoolAccountsBtn.addEventListener("click", showSchoolAccountsModal);

    const schoolAccountsClose = $("school-accounts-close");
    const schoolAccountsOk = $("school-accounts-ok");
    const schoolAccountsRefresh = $("school-accounts-refresh");
    if (schoolAccountsClose)
      schoolAccountsClose.addEventListener("click", closeSchoolAccountsModal);
    if (schoolAccountsOk)
      schoolAccountsOk.addEventListener("click", closeSchoolAccountsModal);
    if (schoolAccountsRefresh)
      schoolAccountsRefresh.addEventListener("click", loadSchoolAccounts);

    const godModeCheckbox = $("god-mode-checkbox");
    const godModeCheckboxModal = $("god-mode-checkbox_modal");
    if (godModeCheckbox)
      godModeCheckbox.addEventListener("change", () =>
        loadAdminSessions_inline(),
      );
    if (godModeCheckboxModal)
      godModeCheckboxModal.addEventListener("change", () =>
        loadAdminSessions(),
      );

    const healthAutoRefreshToggle = $("health-auto-refresh-toggle");
    if (healthAutoRefreshToggle) {
      healthAutoRefreshToggle.addEventListener("change", (e) => {
        if (e.target.checked) {
          startHealthAutoRefresh();
        } else {
          stopHealthAutoRefresh();
        }
      });
    }

    const multiAddClose = $("multi-add-user-close");
    const multiAddCancel = $("multi-add-user-cancel");
    const multiAddConfirm = $("multi-add-user-confirm");

    // 补密码流程中关闭弹窗不能绕过队列：否则队列卡住、且登记了收尾回调的
    // 调用方（导入结果弹窗）永远等不到。按"跳过当前账号"处理。
    const handleMultiAddDismiss = () => {
      if (isMissingPasswordFlowActive()) {
        advanceMissingPasswordQueue();
        return;
      }
      closeMultiAddUserModal();
    };

    if (multiAddClose)
      multiAddClose.addEventListener("click", handleMultiAddDismiss);
    if (multiAddCancel)
      multiAddCancel.addEventListener("click", handleMultiAddDismiss);
    if (multiAddConfirm)
      multiAddConfirm.addEventListener("click", submitMultiAddUser);

    const importResultCloseBtn = $("import-result-close-btn");
    if (importResultCloseBtn)
      importResultCloseBtn.addEventListener("click", closeImportResultModal);

    // [修正] 绑定移动端多账号管理面板的“新增用户”和“刷新用户”按钮
    const mobileMultiCreateUserBtn = $("mobile-multi-admin-create-user");
    const mobileMultiRefreshUsersBtn = $("mobile-multi-admin-refresh-users");

    // --- 新增代码开始: 绑定权限组按钮 ---
    // const mobileMultiCreateGroupBtn = $("mobile-multi-admin-create-group");
    const mobileMultiRefreshGroupsBtn = $("mobile-multi-admin-refresh-groups");
    // --- 新增代码结束 ---

    // 同时处理 单账号模式下 管理面板的新增按钮
    const mobileSingleCreateUserBtn = $("mobile-admin-create-user-panel");

    // --- 新增代码开始: 单账号模式下的权限组按钮 (可选，保持一致性) ---
    const mobileSingleCreateGroupBtn = $("mobile-admin-create-group-panel");
    const mobileSingleRefreshGroupsBtn = $("mobile-admin-refresh-groups-panel");
    // --- 新增代码结束 ---

    if (mobileMultiCreateUserBtn) {
      // 修改：绑定到新的移动端专用模态框函数，而不是 PC 端的 showCreateUserModal
      mobileMultiCreateUserBtn.addEventListener(
        "click",
        openMobileCreateUserModal,
      );
    }

    if (mobileSingleCreateUserBtn) {
      mobileSingleCreateUserBtn.addEventListener(
        "click",
        openMobileCreateUserModal,
      );
    }

    if (mobileMultiRefreshUsersBtn) {
      mobileMultiRefreshUsersBtn.addEventListener("click", () => {
        // 加载数据并同步到多账号面板
        loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"));
      });
    }

    // --- 新增代码开始: 绑定权限组逻辑 ---
    // if (mobileMultiCreateGroupBtn) {
    //   mobileMultiCreateGroupBtn.addEventListener("click", showCreateGroupModal);
    // }

    if (mobileMultiRefreshGroupsBtn) {
      mobileMultiRefreshGroupsBtn.addEventListener("click", () => {
        // 先加载数据，完成后同步到移动端面板
        loadAdminGroups().then(() => copyAdminContentToMultiPanel("groups"));
      });
    }

    if (mobileSingleCreateGroupBtn) {
      mobileSingleCreateGroupBtn.addEventListener(
        "click",
        showCreateGroupModal,
      );
    }

    if (mobileSingleRefreshGroupsBtn) {
      mobileSingleRefreshGroupsBtn.addEventListener("click", () => {
        loadAdminGroups().then(() => copyAdminContentToPanelVersion("groups"));
      });
    }
    // --- 新增代码结束 ---
  });
}

// ====================
// 管理面板功能
// ====================
const permissionTranslations = {
  view_tasks: "查看任务",
  create_tasks: "创建任务",
  delete_tasks: "删除任务",
  start_tasks: "启动任务",
  stop_tasks: "停止任务",
  execute_tasks: "执行任务",
  modify_tasks: "修改任务",
  schedule_tasks: "定时任务",
  view_history: "查看历史记录",

  view_map: "查看地图",
  record_path: "记录路径",
  auto_generate_path: "自动生成路径",

  view_notifications: "查看通知",
  mark_notifications_read: "标记通知已读",
  send_notifications: "发送通知",
  manage_notifications: "管理通知",

  view_user_details: "查看用户详情",
  modify_user_settings: "修改用户设置",
  view_users: "查看用户",
  ban_users: "封禁用户",

  execute_multi_account: "执行多账号任务",
  use_attendance: "使用签到功能",

  view_logs: "查看日志",
  clear_logs: "清空日志",

  manage_users: "管理用户",
  create_users: "创建用户",
  delete_users: "删除用户",
  manage_permissions: "管理权限",
  manage_groups: "管理权限组",
  assign_permissions: "分配权限",
  reset_user_password: "重置用户密码",
  view_audit_logs: "查看审计日志",
  view_all_sessions: "查看系统中的所有会话",
  force_logout_users: "强制用户登出",
  manage_system: "修改系统配置",
  create_permission_groups: "创建权限组",
  delete_permission_groups: "删除权限组",
  modify_permission_groups: "修改权限组",

  auto_fill_password: "查看所有学校账号密码",
  view_school_account_passwords: "查看本账号学校账号密码",
  bypass_overdue: "绕过欠费强制执行",
  import_offline: "导入离线文件",
  export_data: "导出数据",
  import_data: "导入数据",
  backup_data: "备份数据",
  modify_params: "修改参数",
  manage_own_sessions: "管理自己的会话",
  manage_user_sessions: "管理用户会话",
  view_session_details: "查看会话详情",
  view_captcha_history: "查看图形化验证码历史",
  god_mode: "查看所有会话",

  use_login_button: "使用登录按钮",
  use_multi_account_button: "使用多账号控制台按钮",
  use_import_button: "导入离线文件",

  view_messages: "查看留言板",
  post_messages: "发表留言",
  delete_own_messages: "删除自己的留言",
  delete_any_messages: "删除任何留言",
  view_all_messages: "查看所有留言",

  manage_sessions: "管理会话",
  delete_sessions: "删除会话",

  system_settings: "系统设置",
  manage_api: "管理API",

  admin_panel: "管理面板",
  debug_mode: "调试模式",
  modify_config: "修改图片验证码配置",
};

function translatePermission(permissionKey) {
  if (permissionTranslations[permissionKey]) {
    return permissionTranslations[permissionKey];
  }

  const verbMap = {
    view: "查看",
    create: "创建",
    delete: "删除",
    edit: "编辑",
    modify: "修改",
    update: "更新",
    manage: "管理",
    start: "启动",
    stop: "停止",
    execute: "执行",
    run: "运行",
    use: "使用",
    access: "访问",
    add: "添加",
    remove: "移除",
    export: "导出",
    import: "导入",
    backup: "备份",
    restore: "恢复",
    assign: "分配",
    revoke: "撤销",
    grant: "授予",
    clear: "清空",
    reset: "重置",
    force: "强制",
    post: "发表",
    send: "发送",
    receive: "接收",
    download: "下载",
    upload: "上传",
    approve: "审批",
    reject: "拒绝",
    enable: "启用",
    disable: "禁用",
    configure: "配置",
    monitor: "监控",
  };
  const nounMap = {
    users: "用户",
    user: "用户",
    tasks: "任务",
    task: "任务",
    logs: "日志",
    log: "日志",
    sessions: "会话",
    session: "会话",
    notifications: "通知",
    notification: "通知",
    messages: "留言",
    message: "留言",
    permissions: "权限",
    permission: "权限",
    groups: "权限组",
    group: "权限组",
    settings: "设置",
    setting: "设置",
    system: "系统",
    api: "API",
    data: "数据",
    files: "文件",
    file: "文件",
    accounts: "账号",
    account: "账号",
    password: "密码",
    passwords: "密码",
    panel: "面板",
    mode: "模式",
    button: "按钮",
    buttons: "按钮",
    audit: "审计",
    details: "详情",
    detail: "详情",
    params: "参数",
    param: "参数",
    offline: "离线文件",
    multi: "多",
    own: "自己的",
    all: "所有",
    any: "任何",
    attendance: "签到",
    console: "控制台",
    logout: "登出",
    login: "登录",
    admin: "管理",
    god: "上帝",
    debug: "调试",
  };
  const words = permissionKey.toLowerCase().split("_");
  const translatedWords = [];
  for (let i = 0; i < words.length; i++) {
    const word = words[i];
    if (i === 0 && verbMap[word]) {
      translatedWords.push(verbMap[word]);
    } else if (nounMap[word]) {
      translatedWords.push(nounMap[word]);
    } else {
      translatedWords.push(word.charAt(0).toUpperCase() + word.slice(1));
    }
  }

  const result = translatedWords.join("");

  return result || permissionKey;
}

/**
 * 检查当前用户是否拥有指定的管理员权限
 *
 * 功能说明：
 * 1. 向后端API发送权限检查请求
 * 2. 使用当前会话ID (sessionUUID) 进行身份验证
 * 3. 返回布尔值表示用户是否拥有该权限
 *
 * @param {string} permissionName - 要检查的权限名称（如 "god_mode", "manage_users" 等）
 * @returns {Promise<boolean>} - 如果用户拥有该权限返回true，否则返回false
 */
async function checkAdminPermission(permissionName) {
  try {
    // [调试日志] 记录权限检查的开始，便于追踪问题
    console.log(
      `[权限检查] 开始检查权限: ${permissionName}, sessionUUID: ${
        sessionUUID ? "已设置" : "未设置"
      }`,
    );

    // 向后端发送POST请求，检查指定权限
    // API端点: /auth/check_permission
    // 请求体: { permission: "权限名称" }
    const response = await fetch("/auth/check_permission", {
      method: "POST",
      headers: {
        "Content-Type": "application/json", // 指定请求体格式为JSON
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      body: JSON.stringify({ permission: permissionName }), // 将权限名称序列化为JSON字符串
    });

    // 解析服务器返回的JSON响应
    const result = await response.json();

    // [调试日志] 记录权限检查的结果，包含完整的响应数据
    console.log(`[权限检查] ${permissionName} 检查结果:`, {
      success: result.success, // API调用是否成功
      has_permission: result.has_permission, // 用户是否拥有该权限
      response: result, // 完整的响应对象（用于调试）
    });

    // 返回权限检查结果
    // 只有当API调用成功(success=true)且用户拥有权限(has_permission=true)时才返回true
    return result.success && result.has_permission;
  } catch (e) {
    // 捕获任何异常（网络错误、解析错误等）
    // 使用自定义错误日志函数记录详细错误信息
    logMessage_Error(`检查权限 ${permissionName} 失败:`, e);

    // [调试日志] 额外记录错误详情，便于调试
    console.error(`[权限检查ERROR] ${permissionName} 检查失败:`, {
      error: e,
      message: e.message,
      stack: e.stack,
    });

    // 发生错误时，出于安全考虑，默认返回false（无权限）
    return false;
  }
}

async function toggleAdminPanel(show, skipAuthCheck = false) {
  const modal = $("admin-panel-modal");
  const usersTab = $("admin-tab-users_modal");
  const groupsTab = $("admin-tab-groups_modal");
  const logsTab = $("admin-tab-logs_modal");
  const healthTab = $("admin-tab-health_modal");
  const profileTab = $("admin-tab-profile_modal");
  const sessionsTab = $("admin-tab-sessions_modal");
  const messagesTab = $("admin-tab-messages_modal");
  const ipbanTab = $("admin-tab-ipban_modal");
  const smsTab = $("admin-tab-sms_modal");
  const configTab = $("admin-tab-config_modal");
  const godModeToggle = $("god-mode-toggle_modal");
  const modalCaptchaTab = $("admin-tab-captcha_modal");
  // 获取CDN和密码恢复标签页元素
  const cdnTab = $("admin-tab-cdn_modal");
  const bruteforceTab = $("admin-tab-bruteforce_modal");
  // 获取水印控制标签页元素
  const watermarkControlTab = $("admin-tab-watermark-control_modal");

  if (show) {
    resetAdminUsersSearchFilters();
    let canViewMessages = false;
    let canManageSystem = false;
    let hasGodMode = false;
    let isAuthenticated = skipAuthCheck;
    let canManageUsers = false;
    let canViewLogs = false;
    let canViewCaptchaHistory = false;
    let canManageBilling = false;
    let canRestoreAccount = false;
    if (!skipAuthCheck) {
      try {
        // [权限检查] 并行执行多个权限检查，提高效率
        //
        // 使用Promise.all并行执行所有权限检查API调用
        // 这比串行调用快得多，因为不需要等待每个请求完成后再发起下一个
        //
        // 权限检查数组索引说明：
        // [0] manage_users        - 管理用户权限（创建、编辑、删除用户）
        // [1] view_messages       - 查看消息权限（查看用户间的消息记录）
        // [2] manage_system       - 系统管理权限（配置系统参数、CDN等）
        // [3] god_mode            - 上帝模式权限（最高权限，包括密码恢复等危险操作）
        // [4] (auth status check) - 身份验证状态检查
        // [5] view_logs           - 查看日志权限（系统日志、操作日志）
        // [6] view_captcha_history- 查看验证码历史权限
        // [7] manage_billing      - 账单管理权限
        // [8] restore_account     - 恢复账号权限
        const permissionChecks = await Promise.all([
          checkAdminPermission("manage_users"), // 索引0: 用户管理权限
          checkAdminPermission("view_messages"), // 索引1: 消息查看权限
          checkAdminPermission("manage_system"), // 索引2: 系统管理权限
          checkAdminPermission("god_mode"), // 索引3: 上帝模式权限 ← bruteforce需要此权限
          checkAuthStatus(), // 索引4: 身份验证状态
          checkAdminPermission("view_logs"), // 索引5: 日志查看权限
          checkAdminPermission("view_captcha_history"), // 索引6: 验证码历史查看权限
          checkAdminPermission("manage_system"), // 索引7: 账单管理权限
          checkAdminPermission("manage_system"), // 索引8: 恢复账号权限
        ]);

        // [权限赋值] 从Promise.all的结果数组中提取各项权限
        // 每个权限对应上面数组的索引位置
        canManageUsers = permissionChecks[0]; // 用户管理权限结果
        canViewMessages = permissionChecks[1]; // 消息查看权限结果
        canManageSystem = permissionChecks[2]; // 系统管理权限结果
        hasGodMode = permissionChecks[3]; // 上帝模式权限结果 ← 这是bruteforce标签的关键
        isAuthenticated = permissionChecks[4]; // 身份验证状态结果
        canViewLogs = permissionChecks[5]; // 日志查看权限结果
        canViewCaptchaHistory = permissionChecks[6]; // 验证码历史查看权限结果
        canManageBilling = permissionChecks[7]; // 账单管理权限结果
        canRestoreAccount = permissionChecks[8]; // 恢复账号权限结果

        // [调试日志] 记录所有权限检查的完整结果
        // 这对于调试权限问题非常重要，可以一目了然地看到用户拥有哪些权限
        console.log("[权限检查汇总] 所有权限检查完成:", {
          canManageUsers: canManageUsers, // 是否可管理用户
          canViewMessages: canViewMessages, // 是否可查看消息
          canManageSystem: canManageSystem, // 是否可管理系统
          hasGodMode: hasGodMode, // 是否有上帝模式（重要：影响bruteforce显示）
          isAuthenticated: isAuthenticated, // 是否已认证
          canViewLogs: canViewLogs, // 是否可查看日志
          canViewCaptchaHistory: canViewCaptchaHistory, // 是否可查看验证码历史
          canManageBilling: canManageBilling, // 是否可管理账单
          canRestoreAccount: canRestoreAccount, // 是否可恢复账号
          userGroup: currentUserData?.group || "未知", // 当前用户组
          username: currentUserData?.username || "未知", // 当前用户名
        });
      } catch (e) {
        // [异常处理] 如果并行检查过程中发生任何错误，记录错误并设置所有权限为false
        //
        // 可能的错误原因：
        // 1. 网络连接失败
        // 2. 服务器返回错误状态
        // 3. 响应JSON解析失败
        // 4. sessionUUID无效或未设置
        logMessage_Error("并行检查权限时出错:", e);

        // [调试日志] 记录详细的错误信息
        console.error("[权限检查错误] 并行检查失败，错误详情:", {
          error: e,
          message: e.message,
          stack: e.stack,
          sessionUUID: sessionUUID ? "已设置" : "未设置",
          currentUserData: currentUserData,
        });

        // 出于安全考虑，发生错误时将所有权限设置为false
        // 这确保在权限检查失败时，用户不会意外获得不应有的权限
        canManageUsers = false;
        canViewMessages = false;
        canManageSystem = false;
        hasGodMode = false; // ← bruteforce标签将被隐藏
        isAuthenticated = false;
        canViewLogs = false;
        canViewCaptchaHistory = false;
        canManageBilling = false;
        canRestoreAccount = false;
      }
    }

    const isGuest = currentUserIsGuest;

    if (usersTab) usersTab.style.display = canManageUsers ? "block" : "none";
    if (groupsTab) groupsTab.style.display = canManageUsers ? "block" : "none";
    if (logsTab) logsTab.style.display = canViewLogs ? "block" : "none";
    if (healthTab) healthTab.style.display = "block";

    if (ipbanTab) ipbanTab.style.display = canManageUsers ? "block" : "none";
    if (smsTab) smsTab.style.display = canManageUsers ? "block" : "none";

    if (configTab) configTab.style.display = canManageSystem ? "block" : "none";

    // 显示CDN缓存标签 (通常绑定系统管理权限)
    if (cdnTab) cdnTab.style.display = canManageSystem ? "block" : "none";

    // 显示密码恢复标签 - 使用用户组别判断而非权限判断
    //
    // 修复原因：
    // 系统采用差分权限管理，允许普通用户(user组)通过配置拥有管理员权限
    // 例如：user组的用户可能被配置为拥有 manage_users 或 god_mode 权限
    // 因此，不能通过检查权限来判断用户是否是真正的管理员
    // 必须直接读取用户组别（group）来准确判断用户的管理员身份
    //
    // 功能说明：
    // 1. 根据用户的组别决定是否显示"密码恢复"标签
    // 2. 只有 "admin" 组和 "super_admin" 组的用户可以看到此标签
    // 3. 该功能用于合法的账号密码恢复，因此必须严格限制为管理员专属
    //
    // 技术实现：
    // - 从 currentUserData 全局对象中读取用户组别（group属性）
    // - currentUserData.group 在用户登录时由后端API设置
    // - 如果未设置或无效，默认为 "guest" 以确保安全
    // - 使用严格的字符串比较判断组别是否为管理员
    //
    // 安全考虑：
    // - 密码恢复功能是高风险操作，只应对真正的管理员开放
    // - 即使普通用户拥有管理员权限，也不应该访问此功能
    // - 通过组别判断可以严格控制访问权限，避免权限滥用
    //
    // 与旧版本的区别：
    // - 旧版本：使用 (canManageUsers || hasGodMode) 权限判断
    // - 新版本：使用 (userGroup === "admin" || userGroup === "super_admin") 组别判断
    // - 优势：组别判断更加直接和准确，不会因为差分权限配置而误判
    if (bruteforceTab) {
      // 从全局对象 currentUserData 中获取用户组别
      // currentUserData 由登录流程设置，包含用户的完整身份信息
      // 如果 currentUserData 未定义或 group 属性缺失，默认为 "guest"
      const userGroup = currentUserData?.group || "guest";

      // 判断用户是否是管理员或超级管理员（通过组别）
      // 只有这两个组别的用户才能访问密码恢复功能
      const isAdmin = userGroup === "admin" || userGroup === "super_admin";

      // [调试日志] 记录密码恢复Tab的显示控制信息
      // 这对于调试权限问题非常重要，可以清楚地看到判断依据
      console.log("[密码恢复Tab] 组别检查:", {
        userGroup: userGroup, // 用户的组别（来自 currentUserData.group）
        isAdmin: isAdmin, // 是否是管理员（基于组别判断）
        elementFound: !!bruteforceTab, // 是否找到了按钮元素
        currentDisplay: bruteforceTab.style.display, // 当前的display样式
        willDisplay: isAdmin ? "block" : "none", // 即将设置的display值
      });

      // 根据组别设置按钮的显示状态
      // 如果 isAdmin 为 true（用户组为 admin 或 super_admin），设置display为"block"（显示）
      // 如果 isAdmin 为 false（用户组为其他），设置display为"none"（隐藏）
      bruteforceTab.style.display = isAdmin ? "block" : "none";

      // [调试日志] 验证display属性是否设置成功
      // 使用getComputedStyle获取元素的实际计算样式（包括CSS影响）
      const computedDisplay = window.getComputedStyle(bruteforceTab).display;
      console.log("[密码恢复Tab] 显示状态设置完成:", {
        setDisplay: bruteforceTab.style.display, // 设置的display值
        computedDisplay: computedDisplay, // 实际计算的display值
        isVisible: computedDisplay !== "none", // 是否可见
      });

      // [健壮性检查] 如果设置后仍然不可见，记录警告
      // 这可能表示有CSS规则覆盖了我们的设置
      if (isAdmin && computedDisplay === "none") {
        console.warn(
          "[密码恢复Tab警告] 尽管用户是管理员，但按钮仍然不可见。可能的原因:",
          {
            inlineStyle: bruteforceTab.style.cssText, // 内联样式
            classList: Array.from(bruteforceTab.classList), // 应用的CSS类
            parentDisplay: bruteforceTab.parentElement
              ? window.getComputedStyle(bruteforceTab.parentElement).display
              : null, // 父元素显示状态
          },
        );
      }
    } else {
      // [错误日志] 如果找不到按钮元素，记录错误
      // 这表示HTML结构可能有问题，或者元素ID不匹配
      console.error(
        "[密码恢复Tab错误] 未找到ID为'admin-tab-bruteforce_modal'的元素",
      );
    }

    // ========== 添加4个新标签的显示控制逻辑（支付日志标签需根据require_payment配置） ==========
    // 这4个标签分别是：欠费查询、支付日志、支付设置、价格设置
    // 其中：
    // - 欠费查询、支付设置、价格设置：仅对admin和super_admin用户组可见
    // - 支付日志：需要根据require_payment配置和用户权限共同决定

    // 步骤1：通过ID获取4个标签的DOM元素
    // 使用 $ 函数（document.getElementById 的简写）查找元素
    const overdueTab = $("admin-tab-overdue_modal"); // 欠费查询标签
    const paymentLogsTab = $("admin-tab-payment-logs_modal"); // 支付日志标签
    const paymentSettingsTab = $("admin-tab-payment-settings_modal"); // 支付设置标签
    const pricingTab = $("admin-tab-pricing_modal"); // 价格设置标签

    // 步骤2：从全局对象中获取当前登录用户的组别信息
    // currentUserData 是一个全局对象，在用户登录成功后由登录流程设置
    // 如果 currentUserData 未定义或其 group 属性缺失，使用安全的默认值 "guest"
    const userGroup = currentUserData?.group || "guest";

    // 步骤3：判断当前用户是否具有管理员权限
    // 只有 "admin" 或 "super_admin" 组别的用户才能查看管理功能标签
    const isAdmin = userGroup === "admin" || userGroup === "super_admin";

    // 步骤4：【关键】获取pricing配置中的require_payment设置
    // 这个配置决定了是否需要对普通用户启用付费功能
    // 需要调用后端API获取最新的配置数据
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
        console.log("[支付日志Tab配置] 成功获取require_payment配置:", {
          requirePayment: requirePayment, // 是否需要付费
          fullConfig: pricingConfigData.config, // 完整的配置对象（用于调试）
        });
      } else {
        // [警告日志] API调用失败或返回数据格式不正确
        console.warn(
          "[支付日志Tab配置] 获取require_payment配置失败，使用默认值false:",
          {
            success: pricingConfigData.success, // API调用是否成功
            hasConfig: !!pricingConfigData.config, // 是否包含config字段
            response: pricingConfigData, // 完整响应（用于调试）
          },
        );
      }
    } catch (error) {
      // [错误捕获] 如果网络请求失败或发生其他异常，记录错误并使用默认值
      // 可能的错误原因：网络断开、服务器无响应、JSON解析失败等
      console.error("[支付日志Tab配置] 获取require_payment配置时发生异常:", {
        error: error, // 错误对象
        errorMessage: error.message, // 错误消息
        errorStack: error.stack, // 错误堆栈（用于调试）
        defaultValue: requirePayment, // 使用的默认值
      });
      // 发生异常时保持requirePayment为默认值false（安全策略）
    }

    // 步骤5：设置"欠费查询"标签的显示状态
    // 逻辑：仅管理员可见
    if (overdueTab) {
      // 根据管理员权限设置显示/隐藏
      // isAdmin 为 true 时显示（display: "block"），否则隐藏（display: "none"）
      overdueTab.style.display = isAdmin ? "block" : "none";

      // [调试日志] 记录欠费查询标签的显示控制信息
      // 这对于调试权限问题和UI状态非常有用
      console.log("[欠费查询Tab] 显示状态:", {
        userGroup: userGroup, // 当前用户的组别
        isAdmin: isAdmin, // 是否拥有管理员权限
        display: overdueTab.style.display, // 设置后的display属性值
      });
    } else {
      // [错误日志] 如果找不到欠费查询标签元素，记录警告
      // 这可能表示HTML结构中缺少对应的元素，或ID不匹配
      console.warn(
        "[欠费查询Tab警告] 未找到ID为'admin-tab-overdue_modal'的元素",
      );
    }

    // 步骤6：设置"支付日志"标签的显示状态
    // ========================================================================
    // 【业务需求说明】
    // 支付历史标签的显示需要根据 .\configs\config.json 中的 [Payment_Settings].require_payment 配置：
    //
    // 场景A: require_payment = true（启用付费模式）
    //   → 显示条件：所有用户都能看到
    //   → 原因：用户需要查看自己的支付记录、消费明细等
    //   → 管理员额外功能：可以查看所有用户的支付记录
    //
    // 场景B: require_payment = false（免费模式）
    //   → 显示条件：只有管理员可以看到
    //   → 原因：系统免费使用，普通用户无需查看支付信息
    //   → 管理员用途：监控、审计、历史记录查询等
    //
    // 【逻辑表达式】shouldShowPaymentLogs = isAdmin || requirePayment
    //   - 当 isAdmin = true 时：无论 requirePayment 值为何，结果都是 true（管理员始终可见）
    //   - 当 isAdmin = false 且 requirePayment = true 时：结果是 true（普通用户在付费模式下可见）
    //   - 当 isAdmin = false 且 requirePayment = false 时：结果是 false（普通用户在免费模式下不可见）
    // ========================================================================
    if (paymentLogsTab) {
      // [显示逻辑判断]
      // 使用逻辑或（||）运算符组合两个条件：
      // - 条件1 (isAdmin)：用户是管理员或超级管理员 → 管理员始终可以查看所有用户的支付日志
      // - 条件2 (requirePayment)：系统启用了付费功能 → 即使是普通用户，也应该能看到自己的支付记录
      // 只要满足其中任一条件，就显示支付日志标签
      const shouldShowPaymentLogs = isAdmin || requirePayment;

      // 设置DOM元素的display样式属性
      paymentLogsTab.style.display = shouldShowPaymentLogs ? "block" : "none";

      // [调试日志] 记录支付日志标签的显示控制信息（包含详细的决策过程）
      console.log("[支付日志Tab] 显示状态（根据require_payment和用户权限）:", {
        userGroup: userGroup, // 当前用户的组别
        isAdmin: isAdmin, // 是否拥有管理员权限
        requirePayment: requirePayment, // 系统是否启用付费功能
        shouldShowPaymentLogs: shouldShowPaymentLogs, // 最终是否显示标签
        display: paymentLogsTab.style.display, // 设置后的display属性值
        决策说明: isAdmin
          ? "管理员：始终显示"
          : requirePayment
            ? "普通用户：系统启用付费，显示支付历史"
            : "普通用户：系统未启用付费，隐藏支付历史",
      });
    } else {
      // [错误日志] 如果找不到支付日志标签元素，记录警告
      console.warn(
        "[支付日志Tab警告] 未找到ID为'admin-tab-payment-logs_modal'的元素",
      );
    }

    // 步骤7：设置"支付设置"标签的显示状态
    // 逻辑：仅管理员可见（用于配置支付方式，如支付宝、微信等）
    if (paymentSettingsTab) {
      // 与欠费查询标签相同的显示逻辑
      paymentSettingsTab.style.display = isAdmin ? "block" : "none";

      // [调试日志] 记录支付设置标签的显示控制信息
      console.log("[支付设置Tab] 显示状态:", {
        userGroup: userGroup, // 当前用户的组别
        isAdmin: isAdmin, // 是否拥有管理员权限
        display: paymentSettingsTab.style.display, // 设置后的display属性值
      });
    } else {
      // [错误日志] 如果找不到支付设置标签元素，记录警告
      console.warn(
        "[支付设置Tab警告] 未找到ID为'admin-tab-payment-settings_modal'的元素",
      );
    }

    // 步骤8：设置"价格设置"标签的显示状态
    // 逻辑：仅管理员可见（用于配置单次跑步费用、默认免费次数等）
    if (pricingTab) {
      // 与前面管理员专属标签相同的显示逻辑
      pricingTab.style.display = isAdmin ? "block" : "none";

      // [调试日志] 记录价格设置标签的显示控制信息
      console.log("[价格设置Tab] 显示状态:", {
        userGroup: userGroup, // 当前用户的组别
        isAdmin: isAdmin, // 是否拥有管理员权限
        display: pricingTab.style.display, // 设置后的display属性值
      });
    } else {
      // [错误日志] 如果找不到价格设置标签元素，记录警告
      console.warn(
        "[价格设置Tab警告] 未找到ID为'admin-tab-pricing_modal'的元素",
      );
    }

    // 步骤9：设置"水印控制"标签的显示状态
    // 逻辑：仅管理员可见（用于配置用户的高德地图去水印权限）
    if (watermarkControlTab) {
      // 与其他管理员专属标签相同的显示逻辑
      watermarkControlTab.style.display = isAdmin ? "block" : "none";

      // [调试日志] 记录水印控制标签的显示控制信息
      console.log("[水印控制Tab] 显示状态:", {
        userGroup: userGroup, // 当前用户的组别
        isAdmin: isAdmin, // 是否拥有管理员权限
        display: watermarkControlTab.style.display, // 设置后的display属性值
      });
    } else {
      // [错误日志] 如果找不到水印控制标签元素，记录警告
      console.warn(
        "[水印控制Tab警告] 未找到ID为'admin-tab-watermark-control_modal'的元素",
      );
    }

    adminBillingTab = $("admin-tab-billing_modal");

    restoreAccountTab=$("admin-tab-restore-account_modal");

    if (adminBillingTab) {
      adminBillingTab.style.display = canManageBilling ? "block" : "none";
    }

    if (restoreAccountTab) {
      restoreAccountTab.style.display = canRestoreAccount ? "block" : "none";
    }

    if (modalCaptchaTab)
      modalCaptchaTab.style.display = canViewCaptchaHistory ? "block" : "none";

    const remindersTab = $("admin-tab-reminders_modal");
    if (remindersTab)
      remindersTab.style.display = canViewLogs ? "block" : "none";

    const sslTab = $("admin-tab-ssl_modal");
    if (sslTab) sslTab.style.display = canManageUsers ? "block" : "none";
    if (isGuest) {
      if (profileTab) profileTab.style.display = "none";
      if (sessionsTab) sessionsTab.style.display = "block";
      if (messagesTab) messagesTab.style.display = "block";
    } else {
      if (profileTab) profileTab.style.display = "block";
      if (sessionsTab) sessionsTab.style.display = "block";
    }
    if (godModeToggle)
      godModeToggle.style.display = hasGodMode ? "flex" : "none";
    switchAdminTab("sessions");
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    document.body.classList.add("modal-visible");
  } else {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    document.body.classList.remove("modal-visible");
    const captchaHistoryPanel = $("admin-captcha-history-panel_modal");
    if (captchaHistoryPanel) captchaHistoryPanel.classList.add("hidden");
    stopHealthAutoRefresh();
  }
}
async function initializeInlineAdminPanel() {
  const sessionsPanel = $("admin-sessions-panel");
  if (sessionsPanel) {
    loadAdminSessions_inline();
  }
}

let messageEditor = null;
let mobileMultiMessageEditor = null;
let mobileReminderEditor = null;
let accountCancellationCooldowns = { pc: 0, mobile: 0 };

function formatCancellationTimeText(ts) {
  if (!ts) return "未申请";
  const ms = Number(ts) * 1000;
  if (Number.isNaN(ms)) return "已申请";
  return `等待至 ${new Date(ms).toLocaleString()}`;
}

function updateAccountCancellationStatusDisplay(status) {
  const text =
    status && status.status === "pending"
      ? formatCancellationTimeText(status.execute_at)
      : "未申请";
  const pcEl = document.getElementById("pc-account-cancel-status");
  const mobileEl = document.getElementById("mobile-account-cancel-status");
  if (pcEl) pcEl.textContent = text;
  if (mobileEl) mobileEl.textContent = text;
}

function getAccountCancelElements(platform) {
  if (platform === "mobile") {
    return {
      passwordInput: document.getElementById(
        "mobile-account-cancel-current-password",
      ),
      smsInput: document.getElementById("mobile-account-cancel-sms-code"),
      statusEl: document.getElementById("mobile-account-cancel-status"),
      smsButtonSelector:
        "button[onclick=\"sendAccountCancelSmsCode('mobile')\"]",
    };
  }
  return {
    passwordInput: document.getElementById(
      "pc-account-cancel-current-password",
    ),
    smsInput: document.getElementById("pc-account-cancel-sms-code"),
    statusEl: document.getElementById("pc-account-cancel-status"),
    smsButtonSelector: "button[onclick=\"sendAccountCancelSmsCode('pc')\"]",
  };
}

async function sendAccountCancelSmsCode(platform = "pc") {
  const { smsButtonSelector } = getAccountCancelElements(platform);
  const sendBtn = document.querySelector(smsButtonSelector);
  if (accountCancellationCooldowns[platform] > 0) {
    showModalAlert(
      `请等待 ${accountCancellationCooldowns[platform]} 秒后再发送`,
      "提示",
    );
    return;
  }
  try {
    const profile = await callPythonAPI_raw("/api/user/profile", "GET");
    if (!profile.success || !profile.phone) {
      showModalAlert("未绑定手机号，无法发送验证码", "错误");
      return;
    }
    if (sendBtn) sendBtn.disabled = true;
    openCaptchaModal({
      phone: profile.phone,
      button: sendBtn,
      originalText: "发送验证码",
      scene: "password_reset",
    });
    accountCancellationCooldowns[platform] = 60;
    const timer = setInterval(() => {
      accountCancellationCooldowns[platform] -= 1;
      if (sendBtn) {
        sendBtn.textContent =
          accountCancellationCooldowns[platform] > 0
            ? `${accountCancellationCooldowns[platform]}s`
            : "发送验证码";
      }
      if (accountCancellationCooldowns[platform] <= 0) {
        clearInterval(timer);
        if (sendBtn) sendBtn.disabled = false;
      }
    }, 1000);
  } catch (e) {
    if (sendBtn) sendBtn.disabled = false;
    showModalAlert("发送验证码失败: " + e.message, "错误");
  }
}

async function requestAccountCancellation(platform = "pc") {
  const { passwordInput, smsInput, statusEl } =
    getAccountCancelElements(platform);
  const currentPassword = passwordInput ? passwordInput.value.trim() : "";
  const smsCode = smsInput ? smsInput.value.trim() : "";
  if (!currentPassword || !smsCode) {
    showModalAlert("请填写当前密码和短信验证码", "提示");
    return;
  }
  if (!/^\d{6}$/.test(smsCode)) {
    showModalAlert("短信验证码格式错误", "提示");
    return;
  }

  const confirmed = await jsShowConfirm(
    "确认账号注销申请",
    "提交后将进入默认24小时等待期，期间账号仍可登录。确定继续？",
  );
  if (!confirmed) return;

  try {
    const resp = await fetch("/auth/user/request_account_cancellation", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        current_password: currentPassword,
        sms_code: smsCode,
        wait_hours: 24,
      }),
    });
    const result = await resp.json();
    if (!result.success) {
      showModalAlert(result.message || "申请失败", "错误");
      return;
    }
    updateAccountCancellationStatusDisplay(result.status);
    if (statusEl && result.status && result.status.execute_at) {
      statusEl.textContent = formatCancellationTimeText(
        result.status.execute_at,
      );
    }
    if (passwordInput) passwordInput.value = "";
    if (smsInput) smsInput.value = "";
    showModalAlert(result.message || "已提交注销申请", "成功");
  } catch (e) {
    showModalAlert("申请失败: " + e.message, "错误");
  }
}
function switchAdminTab(tab) {
  const userGroup = currentUserData?.group || "user";
  const usersTab = $("admin-tab-users_modal");
  const groupsTab = $("admin-tab-groups_modal");
  const logsTab = $("admin-tab-logs_modal");
  const healthTab = $("admin-tab-health_modal");
  const profileTab = $("admin-tab-profile_modal");
  const sessionsTab = $("admin-tab-sessions_modal");
  const messagesTab = $("admin-tab-messages_modal");
  const ipbanTab = $("admin-tab-ipban_modal");
  const smsTab = $("admin-tab-sms_modal");
  const configTab = $("admin-tab-config_modal");
  const captchaTab = $("admin-tab-captcha_modal");
  const remindersTab = $("admin-tab-reminders_modal");
  const sslTab = $("admin-tab-ssl_modal");
  // 获取CDN和密码恢复的Tab元素
  const cdnTab = $("admin-tab-cdn_modal");
  const bruteforceTab = $("admin-tab-bruteforce_modal");
  // 获取欠费查询标签元素
  const overdueTab = $("admin-tab-overdue_modal");
  // 获取支付日志标签元素
  const paymentLogsTab = $("admin-tab-payment-logs_modal");
  // 获取支付设置标签元素
  const paymentSettingsTab = $("admin-tab-payment-settings_modal");
  // 获取价格设置标签元素
  const pricingTab = $("admin-tab-pricing_modal");
  // 获取水印控制标签元素
  const watermarkControlTab = $("admin-tab-watermark-control_modal");
  const billingLogsTab = $("admin-tab-billing-logs_modal");

  const usersPanel = $("admin-users-panel_modal");
  const groupsPanel = $("admin-groups-panel_modal");
  const logsPanel = $("admin-logs-panel_modal");
  const healthPanel = $("admin-health-panel_modal");
  const profilePanel = $("admin-profile-panel_modal");
  const sessionsPanel = $("admin-sessions-panel_modal");
  const messagesPanel = $("admin-messages-panel_modal");
  const ipbanPanel = $("admin-ip-ban-modal");
  const smsPanel = $("admin-sms-config-modal");
  const configPanel = $("admin-config-panel_modal");
  const captchaPanel = $("admin-captcha-panel_modal");
  const remindersPanel = $("admin-reminders-panel_modal");
  const sslPanel = $("admin-ssl-panel_modal");
  // 获取CDN和密码恢复的Panel元素
  const cdnPanel = $("admin-cdn-panel_modal");
  const bruteforcePanel = $("admin-bruteforce-panel_modal");
  // 获取欠费查询面板元素
  const overduePanel = $("admin-billing-panel_modal");
  // 获取支付日志面板元素
  const paymentLogsPanel = $("admin-payment-logs-panel_modal");
  // 获取支付设置面板元素
  const paymentSettingsPanel = $("admin-payment-settings-panel_modal");
  // 获取价格设置面板元素
  const pricingPanel = $("admin-pricing-panel_modal");
  // 获取水印控制面板元素
  const watermarkControlPanel = $("admin-watermark-control-panel_modal");
  const billingLogsPanel = $("admin-billing-logs-panel_modal");
  // 获取账单管理和恢复账号标签/面板元素
  const adminBillingTab = $("admin-tab-billing_modal");
  const restoreAccountTab = $("admin-tab-restore-account_modal");
  const adminBillingPanel = $("admin-billing-panel_modal");
  const restoreAccountPanel = $("admin-restore-account-panel_modal");

  if (!sessionsTab || !sessionsPanel) {
    logMessage_Error("switchAdminTab: 无法找到必要的管理面板元素");
    return;
  }
  [
    usersTab,
    groupsTab,
    logsTab,
    healthTab,
    profileTab,
    sessionsTab,
    messagesTab,
    ipbanTab,
    smsTab,
    configTab,
    captchaTab,
    remindersTab,
    sslTab,
    cdnTab, // 添加CDN Tab
    bruteforceTab, // 添加密码恢复 Tab
    overdueTab, // 添加欠费查询 Tab
    paymentLogsTab, // 添加支付日志 Tab
    paymentSettingsTab, // 添加支付设置 Tab
    pricingTab, // 添加价格设置 Tab
    watermarkControlTab, // 添加水印控制 Tab
    billingLogsTab,
    adminBillingTab, // 添加账单管理 Tab
    restoreAccountTab, // 添加恢复账号 Tab
  ]
    .filter((t) => t)
    .forEach((t) => {
      t.classList.remove("text-sky-600", "border-sky-600");
      t.classList.add("text-slate-400", "border-transparent");
    });

  [
    usersPanel,
    groupsPanel,
    logsPanel,
    healthPanel,
    profilePanel,
    sessionsPanel,
    messagesPanel,
    ipbanPanel,
    smsPanel,
    configPanel,
    captchaPanel,
    remindersPanel,
    sslPanel,
    cdnPanel, // 添加CDN Panel
    bruteforcePanel, // 添加密码恢复 Panel
    overduePanel, // 添加欠费查询 Panel
    paymentLogsPanel, // 添加支付日志 Panel
    paymentSettingsPanel, // 添加支付设置 Panel
    pricingPanel, // 添加价格设置 Panel
    watermarkControlPanel, // 添加水印控制 Panel
    billingLogsPanel,
    adminBillingPanel, // 添加账单管理 Panel
    restoreAccountPanel, // 添加恢复账号 Panel
  ]
    .filter((p) => p)
    .forEach((p) => {
      p.classList.add("hidden");
    });

  const captchaHistoryPanel = $("admin-captcha-history-panel_modal");
  if (captchaHistoryPanel) captchaHistoryPanel.classList.add("hidden");

  if (tab === "users") {
    usersTab.classList.add("text-sky-600", "border-sky-600");
    usersTab.classList.remove("text-slate-400", "border-transparent");
    usersPanel.classList.remove("hidden");
    loadAdminUsers();
    stopHealthAutoRefresh();
  } else if (tab === "groups") {
    groupsTab.classList.add("text-sky-600", "border-sky-600");
    groupsTab.classList.remove("text-slate-400", "border-transparent");
    groupsPanel.classList.remove("hidden");
    loadAdminGroups();
    stopHealthAutoRefresh();
  } else if (tab === "logs") {
    logsTab.classList.add("text-sky-600", "border-sky-600");
    logsTab.classList.remove("text-slate-400", "border-transparent");
    logsPanel.classList.remove("hidden");
    loadAdminLogs(1);
    stopHealthAutoRefresh();
  } else if (tab === "health") {
    healthTab.classList.add("text-sky-600", "border-sky-600");
    healthTab.classList.remove("text-slate-400", "border-transparent");
    healthPanel.classList.remove("hidden");
    loadHealthStatus();
    startHealthAutoRefresh();
  } else if (tab === "profile") {
    profileTab.classList.add("text-sky-600", "border-sky-600");
    profileTab.classList.remove("text-slate-400", "border-transparent");
    profilePanel.classList.remove("hidden");
    loadPersonalInfo();
    stopHealthAutoRefresh();
    loadUserBillingList();
  } else if (tab === "sessions") {
    sessionsTab.classList.add("text-sky-600", "border-sky-600");
    sessionsTab.classList.remove("text-slate-400", "border-transparent");
    sessionsPanel.classList.remove("hidden");
    loadAdminSessions();
    stopHealthAutoRefresh();
  } else if (tab === "messages") {
    // ============================================================
    // IP封禁检查：留言板功能
    // ============================================================
    if (messagesTab && messagesPanel) {
      checkIPBanAndProceed("messages_only")
        .then((isBanned) => {
          if (isBanned) {
            // showModalAlert("您的IP已被限制访问留言功能", "访问被拒绝");
            Swal.fire({
              icon: "error",
              title: "访问被拒绝",
              text: "您的IP已被限制访问留言功能",
              confirmButtonText: "确定",
            });
            return;
          }

          messagesTab.classList.add("text-sky-600", "border-sky-600");
          messagesTab.classList.remove("text-slate-400", "border-transparent");
          messagesPanel.classList.remove("hidden");
          loadMessages();
          stopHealthAutoRefresh();
          // 在消息面板可见后，再动态加载并初始化 Markdown 编辑器（只初始化一次）
          if (!window._messageEditorInitialized) {
            // 标记为正在初始化，避免重复触发
            window._messageEditorInitialized = false;

            // 动态加载样式（如果尚未加载）
            try {
              if (
                !document.querySelector(
                  'link[href="/editor.md/css/editormd.css"]',
                )
              ) {
                const css = document.createElement("link");
                css.rel = "stylesheet";
                css.href = "/editor.md/css/editormd.css";
                document.head.appendChild(css);
              }
            } catch (e) {
              console.warn("无法注入 editormd CSS:", e);
            }

            const loadScript = (src) =>
              new Promise((resolve, reject) => {
                if (document.querySelector(`script[src="${src}"]`))
                  return resolve();
                const s = document.createElement("script");
                s.src = src;
                s.onload = () => resolve();
                s.onerror = () => reject(new Error("加载脚本失败: " + src));
                document.body.appendChild(s);
              });

            (async () => {
              try {
                // 如果页面没有 jQuery，则尝试加载本地副本

                // 初始化编辑器，将 name 设为 message-content，以便与现有提交逻辑兼容
                messageEditor = editormd("message-editor", {
                  // ===== 基本配置 =====
                  // 编辑器模式：
                  // gfm：GitHub Flavored Markdown，与 Markdown 语法基本相同，但增加了一些扩展语法，如表格、任务列表等
                  // markdown：标准 Markdown 语法
                  mode: "gfm",
                  // 表单元素名称，用于提交表单时标识该编辑器
                  name: "message-content",
                  // CodeMirror 的值，如果模式不是 gfm/markdown（通常不需要设置，留空即可）
                  value: "",
                  // 编辑器主题，可选值：default（默认主题）, dark（暗色主题）
                  theme: "default",
                  // 编辑区域主题（代码编辑区域的样式），可选值包括：
                  // default, 3024-day, 3024-night, ambiance, ambiance-mobile, base16-dark, base16-light,
                  // blackboard, cobalt, eclipse, elegant, erlang-dark, lesser-dark, mbo, mdn-like,
                  // midnight, monokai, neat, neo, night, paraiso-dark, paraiso-light, pastel-on-dark,
                  // rubyblue, solarized, the-matrix, tomorrow-night-eighties, twilight, vibrant-ink,
                  // xq-dark, xq-light
                  editorTheme: "default",
                  // 预览区域主题，默认空表示使用默认主题，可选值：default（默认主题）, dark（暗色主题）
                  previewTheme: "default",
                  // Markdown 源代码（编辑器初始化时显示的内容，可以是预填的 Markdown 文本）
                  markdown: "",
                  // 如果初始化时 textarea 值不为空，则追加 markdown 到 textarea（通常用于追加内容到现有文本）
                  appendMarkdown: "",
                  // 编辑器宽度（支持百分比如"100%"或像素值如"800px"）
                  width: "100%",
                  // 编辑器高度（支持百分比如"100%"或像素值如"600px"）
                  height: "300px",
                  // 依赖模块文件目录（Editor.md 所需的文件路径，通常使用 CDN 地址）
                  path: "/editor.md/lib/",
                  // 插件路径，如果为空，默认使用 settings.path + "../plugins/"（插件存放目录）
                  pluginPath: "/editor.md/plugins/",
                  // 延迟解析 markdown 到 html，单位：毫秒（避免频繁解析，提升性能，默认300ms）
                  delay: 300,
                  // 自动加载依赖模块文件（推荐保持 true，确保所有功能正常工作）
                  autoLoadModules: true,
                  // ===== 编辑器行为配置 =====
                  // 监听模式（是否实时预览，true 为开启监听，false 为手动预览）
                  watch: true,
                  // 占位符文本（当编辑器为空时显示的提示文本，引导用户输入）
                  placeholder: "请输入留言（支持 Markdown）",
                  // 启用/禁用 跳转到行功能（Ctrl+G 快捷键，快速跳转到指定行）
                  gotoLine: true,
                  // 代码折叠（是否允许折叠代码块，方便查看长代码）
                  codeFold: false,
                  // 自动高度（是否根据内容自动调整编辑器高度，true 时高度自适应）
                  autoHeight: false,
                  // 启用/禁用 自动聚焦编辑器左侧输入区域（页面加载后自动聚焦到编辑器）
                  autoFocus: true,
                  // 自动关闭标签（输入 < 时自动补全标签，提高 HTML 编写效率）
                  autoCloseTags: true,
                  // 启用/禁用 搜索和替换功能（CodeMirror 的搜索功能，Ctrl+F 激活）
                  searchReplace: true,
                  // 同步滚动选项：true（同步滚动）| false（不同步）| "single"（单向同步），默认 true
                  syncScrolling: true,
                  // 启用/禁用 只读模式（设为 true 后无法编辑，只能查看）
                  readOnly: false,
                  // 制表符大小（Tab 键缩进的空格数，通常设为 4）
                  tabSize: 4,
                  // 缩进单位（每次缩进的空格数，通常与 tabSize 保持一致）
                  indentUnit: 4,
                  // 显示编辑器行号（左侧显示行号，便于定位代码位置）
                  lineNumbers: true,
                  // 行换行（是否自动换行，true 时长行会自动换行）
                  lineWrapping: true,
                  // 自动关闭括号（输入左括号时自动补全右括号，支持 (), [], {}）
                  autoCloseBrackets: true,
                  // 显示尾随空格（显示行末的空格字符，帮助保持代码整洁）
                  showTrailingSpace: true,
                  // 匹配括号（高亮匹配的括号对，方便检查括号匹配）
                  matchBrackets: true,
                  // 使用制表符缩进（true 使用 Tab 字符，false 使用空格）
                  indentWithTabs: true,
                  // 样式化选中文本（选中的文本是否有特殊样式，如背景色）
                  styleSelectedText: true,
                  // 匹配单词高亮：true（高亮所有相同单词）| false（不高亮）| "onselected"（只在选中时高亮）
                  matchWordHighlight: true,
                  // 高亮当前行（当前行是否有背景色，方便定位）
                  styleActiveLine: true,
                  // ===== 对话框配置 =====
                  // 对话框锁定屏幕（对话框弹出时是否锁定背景，防止误操作）
                  dialogLockScreen: true,
                  // 对话框显示遮罩（是否显示半透明遮罩层）
                  dialogShowMask: true,
                  // 对话框可拖拽（对话框是否可以拖动位置）
                  dialogDraggable: true,
                  // 对话框遮罩背景色（遮罩的颜色，通常使用白色或半透明）
                  dialogMaskBgColor: "#fff",
                  // 对话框遮罩不透明度（0.0 到 1.0，控制遮罩透明度）
                  dialogMaskOpacity: 0.1,
                  // 字体大小（编辑器内文字的大小，影响可读性）
                  fontSize: "13px",
                  // 如果启用，编辑器将创建一个 <textarea> 标签保存 HTML 代码用于表单提交
                  saveHTMLToTextarea: true,
                  // 禁用的键映射（禁用某些快捷键，数组格式，如 ["Ctrl-B", "Ctrl-I"]）
                  disabledKeyMaps: [],

                  // ===== 事件回调函数 =====
                  // 加载完成回调（编辑器初始化完成后触发）
                  onload: function () {},
                  // 调整大小回调（编辑器大小改变时触发）
                  onresize: function () {},
                  // 内容改变回调（编辑器内容发生变化时触发）
                  onchange: function () {
                    logMessage_Info(
                      "留言内容已更改, 当前长度: " +
                        this.getMarkdown().length +
                        " 字符",
                    );
                    const countEl =
                      document.getElementById("message-char-count");
                    if (this && countEl)
                      countEl.textContent = String(this.getMarkdown().length);
                  },
                  // 监听开始回调（开始监听模式时触发）
                  onwatch: null,
                  // 监听结束回调（结束监听模式时触发）
                  onunwatch: null,
                  // 预览中回调（正在生成预览时触发）
                  onpreviewing: function () {},
                  // 预览完成回调（预览生成完成后触发）
                  onpreviewed: function () {},
                  // 全屏回调（进入全屏模式时触发）
                  onfullscreen: function () {},
                  // 退出全屏回调（退出全屏模式时触发）
                  onfullscreenExit: function () {},
                  // 滚动回调（编辑器滚动时触发）
                  onscroll: function () {},
                  // 预览滚动回调（预览区域滚动时触发）
                  onpreviewscroll: function () {},

                  // ===== 图片上传配置 =====
                  // 启用/禁用 上传功能（是否允许上传图片到服务器）
                  imageUpload: true,
                  // 支持的图片格式（允许上传的图片文件类型数组）
                  imageFormats: ["jpg", "jpeg", "gif", "png", "bmp", "webp"],
                  // 上传 URL（图片上传的服务器端点地址）
                  imageUploadURL: "/upload",
                  // 启用/禁用 跨域上传（是否支持跨域上传图片）
                  crossDomainUpload: false,
                  // 跨域上传回调 URL（跨域上传时的回调地址，用于处理上传结果）
                  // uploadCallbackURL: "",

                  // ===== 目录和扩展功能配置 =====
                  // 启用/禁用 目录功能（是否自动生成文章目录）
                  toc: true,
                  // 使用 [TOCM]，自动创建目录下拉菜单（在标题前添加 [TOCM] 标记启用）
                  tocm: false,
                  // 目录下拉菜单按钮标题（下拉菜单的显示文本）
                  tocTitle: "",
                  // 启用/禁用 目录下拉菜单（是否显示目录下拉菜单按钮）
                  tocDropdown: false,
                  // 自定义目录容器选择器（目录插入的 DOM 元素选择器，默认插入编辑器内部）
                  tocContainer: "",
                  // 从 H1 开始创建目录（目录从哪一级标题开始生成，1表示H1，2表示H2）
                  tocStartLevel: 1,
                  // 打开 HTML 标签识别（是否解析和显示 HTML 标签）
                  htmlDecode: true,
                  // 启用解析分页符 [========]（是否支持分页符语法，用于分隔内容）
                  pageBreak: true,
                  // 启用 @链接功能（@用户名 自动转换为链接）
                  atLink: false,
                  // 邮箱地址自动链接（自动识别邮箱地址并转换为可点击链接）
                  emailLink: true,
                  // 启用 GitHub Flavored Markdown 任务列表（支持 - [ ] 任务列表语法）
                  taskList: true,
                  // 启用表情符号支持：
                  // :emoji: 支持 GitHub 表情、Twitter 表情 (Twemoji)
                  // :fa-xxx: 使用 FontAwesome 图标 web 字体
                  // :editormd-logo: :editormd-logo-1x: > 1~8x 支持 Editor.md logo 图标
                  emoji: true,
                  // 启用 TeX(LaTeX) 数学公式支持，基于 KaTeX 库
                  tex: true,
                  // 启用流程图支持（flowChart.js，只支持 IE9+，用于绘制流程图）
                  flowChart: true,
                  // 启用时序图支持（sequenceDiagram.js，只支持 IE9+，用于绘制时序图）
                  sequenceDiagram: true,
                  // 启用/禁用 编辑器预览区域代码高亮（预览区代码是否进行语法高亮）
                  previewCodeHighlight: true,

                  // ===== 工具栏配置 =====
                  // 显示或隐藏工具栏
                  toolbar: true,
                  // 窗口滚动时自动固定工具栏位置
                  toolbarAutoFixed: true,
                  // 工具栏图标模式：full（完整）| simple（简单）| mini（最小），参见 `editormd.toolbarModes` 属性
                  toolbarIcons: "full",
                  // 工具栏标题（自定义工具栏按钮的提示文本）
                  toolbarTitles: {},
                  // 工具栏处理程序（自定义工具栏按钮的点击事件）
                  toolbarHandlers: {},
                  // 使用 HTML 标签创建工具栏图标，未使用默认 <a> 标签（自定义工具栏图标的 HTML）
                  toolbarCustomIcons: {},
                  // 工具栏图标文本（自定义工具栏按钮的文本）
                  toolbarIconTexts: {},
                  // 父容器层级（用于解决全屏模式下的定位问题）
                  parentContainerLayer: '5',
                });

                // 将编辑器内部生成的对话框（.editormd-dialog）移动到 body，并固定定位，避免被父容器裁剪
                (function ensureDialogsOnBody() {
                  const editorRoot = document.getElementById("message-editor");
                  if (!editorRoot) return;

                  const relocate = (dialog) => {
                    if (!dialog || dialog.__moved_to_body) return;
                    try {
                      const r = dialog.getBoundingClientRect();
                      // 保持原始宽度（防止被拉伸）
                      const w = dialog.offsetWidth;
                      const h = dialog.offsetHeight;
                      dialog.style.position = "fixed";
                      dialog.style.left = Math.max(0, r.left) + "px";
                      dialog.style.top = Math.max(0, r.top) + "px";
                      dialog.style.width = w ? w + "px" : "auto";
                      dialog.style.height = h ? h + "px" : "auto";
                      dialog.style.zIndex = 20000;
                      // 遮罩（mask）通常是紧邻的元素，尝试将同一对话框相关的遮罩也移动
                      const origMask =
                        dialog.parentElement &&
                        dialog.parentElement.querySelector &&
                        dialog.parentElement.querySelector(
                          ".editormd-dialog-mask",
                        );
                      if (origMask) {
                        // 尝试克隆遮罩并将克隆放到 body 中，避免受原父容器的 overflow/clipping 限制
                        try {
                          const clone = origMask.cloneNode(true);
                          clone.__orig_display = origMask.style.display || "";
                          clone.style.position = "fixed";
                          clone.style.left = "0";
                          clone.style.top = "0";
                          clone.style.width = "100%";
                          clone.style.height = "100%";
                          clone.style.zIndex = 19990;
                          clone.classList.add("editormd-dialog-mask");
                          document.body.appendChild(clone);
                          // 隐藏原遮罩，保留其原始 display 以便未来恢复
                          origMask.__orig_display =
                            origMask.style.display || "";
                          origMask.style.display = "none";
                          clone.__moved_for_dialog = dialog;
                          dialog.__moved_mask = clone;
                          dialog.__orig_mask = origMask;
                        } catch (e) {
                          // 克隆失败则回退为直接移动原始遮罩
                          origMask.__orig_display =
                            origMask.style.display || "";
                          document.body.appendChild(origMask);
                          origMask.style.position = "fixed";
                          origMask.style.left = "0";
                          origMask.style.top = "0";
                          origMask.style.width = "100%";
                          origMask.style.height = "100%";
                          origMask.style.zIndex = 19990;
                          origMask.__moved_for_dialog = dialog;
                          dialog.__moved_mask = origMask;
                        }
                      }
                      document.body.appendChild(dialog);
                      dialog.__moved_to_body = true;

                      // 根据对话框的可见性，切换遮罩显示；并监听属性变化以实时更新
                      const checkVisibilityAndToggleMask = () => {
                        try {
                          const curMask = dialog.__moved_mask;
                          if (!curMask) return;
                          const style = window.getComputedStyle(dialog);
                          const isVisible =
                            style &&
                            style.display !== "none" &&
                            style.visibility !== "hidden" &&
                            dialog.offsetParent !== null &&
                            dialog.getBoundingClientRect().width > 0 &&
                            dialog.getBoundingClientRect().height > 0;
                          if (isVisible) {
                            curMask.style.display =
                              curMask.__orig_display || "";
                          } else {
                            curMask.style.display = "none";
                          }
                        } catch (e) {
                          // 忽略
                        }
                      };

                      // 初次同步一次
                      checkVisibilityAndToggleMask();

                      // 监听对话框的属性变化（style/class 等）以决定遮罩显示/隐藏
                      try {
                        const attrObserver = new MutationObserver(() =>
                          checkVisibilityAndToggleMask(),
                        );
                        attrObserver.observe(dialog, {
                          attributes: true,
                          attributeFilter: ["style", "class"],
                        });
                        // 保存 observer 引用以便未来可清理（如果需要）
                        dialog.__visibilityAttrObserver = attrObserver;
                      } catch (e) {
                        // 忽略
                      }
                    } catch (e) {
                      console.warn("relocate dialog failed", e);
                    }
                  };

                  // 观察器：当编辑器动态插入对话框时触发
                  const mo = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                      for (const node of m.addedNodes) {
                        if (!(node instanceof HTMLElement)) continue;
                        if (
                          node.classList &&
                          node.classList.contains("editormd-dialog")
                        ) {
                          relocate(node);
                        } else {
                          // 也检查子元素
                          const found =
                            node.querySelector &&
                            node.querySelectorAll &&
                            node.querySelectorAll(".editormd-dialog");
                          if (found && found.length) {
                            found.forEach((d) => relocate(d));
                          }
                        }
                      }
                    }
                  });

                  // 启动观察器，监视整个编辑器容器的子树
                  mo.observe(editorRoot, { childList: true, subtree: true });

                  // 也立即处理当前已存在的对话框
                  const existing =
                    editorRoot.querySelectorAll(".editormd-dialog");
                  existing.forEach((d) => relocate(d));
                })();

                window._messageEditorInitialized = true;
                loadMessages();

                // 为 reminder-editor 也注册相同的对话框移动与遮罩可见性控制逻辑
                (function ensureReminderDialogsOnBody() {
                  const editorRoot = document.getElementById("reminder-editor");
                  if (!editorRoot) return;

                  const relocate = (dialog) => {
                    if (!dialog || dialog.__moved_to_body) return;
                    try {
                      const r = dialog.getBoundingClientRect();
                      const w = dialog.offsetWidth;
                      const h = dialog.offsetHeight;
                      dialog.style.position = "fixed";
                      dialog.style.left = Math.max(0, r.left) + "px";
                      dialog.style.top = Math.max(0, r.top) + "px";
                      dialog.style.width = w ? w + "px" : "auto";
                      dialog.style.height = h ? h + "px" : "auto";
                      dialog.style.zIndex = 20000;
                      const origMask =
                        dialog.parentElement &&
                        dialog.parentElement.querySelector &&
                        dialog.parentElement.querySelector(
                          ".editormd-dialog-mask",
                        );
                      if (origMask) {
                        try {
                          const clone = origMask.cloneNode(true);
                          clone.__orig_display = origMask.style.display || "";
                          clone.style.position = "fixed";
                          clone.style.left = "0";
                          clone.style.top = "0";
                          clone.style.width = "100%";
                          clone.style.height = "100%";
                          clone.style.zIndex = 19990;
                          clone.classList.add("editormd-dialog-mask");
                          document.body.appendChild(clone);
                          origMask.__orig_display =
                            origMask.style.display || "";
                          origMask.style.display = "none";
                          clone.__moved_for_dialog = dialog;
                          dialog.__moved_mask = clone;
                          dialog.__orig_mask = origMask;
                        } catch (e) {
                          origMask.__orig_display =
                            origMask.style.display || "";
                          document.body.appendChild(origMask);
                          origMask.style.position = "fixed";
                          origMask.style.left = "0";
                          origMask.style.top = "0";
                          origMask.style.width = "100%";
                          origMask.style.height = "100%";
                          origMask.style.zIndex = 19990;
                          origMask.__moved_for_dialog = dialog;
                          dialog.__moved_mask = origMask;
                        }
                      }
                      document.body.appendChild(dialog);
                      dialog.__moved_to_body = true;

                      const checkVisibilityAndToggleMask = () => {
                        try {
                          const curMask = dialog.__moved_mask;
                          if (!curMask) return;
                          const style = window.getComputedStyle(dialog);
                          const isVisible =
                            style &&
                            style.display !== "none" &&
                            style.visibility !== "hidden" &&
                            dialog.offsetParent !== null &&
                            dialog.getBoundingClientRect().width > 0 &&
                            dialog.getBoundingClientRect().height > 0;
                          if (isVisible) {
                            curMask.style.display =
                              curMask.__orig_display || "";
                          } else {
                            curMask.style.display = "none";
                          }
                        } catch (e) {}
                      };

                      checkVisibilityAndToggleMask();

                      try {
                        const attrObserver = new MutationObserver(() =>
                          checkVisibilityAndToggleMask(),
                        );
                        attrObserver.observe(dialog, {
                          attributes: true,
                          attributeFilter: ["style", "class"],
                        });
                        dialog.__visibilityAttrObserver = attrObserver;
                      } catch (e) {}
                    } catch (e) {
                      console.warn("relocate dialog failed", e);
                    }
                  };

                  const mo = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                      for (const node of m.addedNodes) {
                        if (!(node instanceof HTMLElement)) continue;
                        if (
                          node.classList &&
                          node.classList.contains("editormd-dialog")
                        ) {
                          relocate(node);
                        } else {
                          const found =
                            node.querySelector &&
                            node.querySelectorAll &&
                            node.querySelectorAll(".editormd-dialog");
                          if (found && found.length) {
                            found.forEach((d) => relocate(d));
                          }
                        }
                      }
                    }
                  });

                  mo.observe(editorRoot, { childList: true, subtree: true });

                  const existing =
                    editorRoot.querySelectorAll(".editormd-dialog");
                  existing.forEach((d) => relocate(d));
                })();
              } catch (err) {
                console.error("初始化留言板 Markdown 编辑器失败:", err);
              }
            })();
          }
        })
        .catch((err) => {
          logMessage_Error("[IP封禁检查] 检查失败:", err);
          // showModalAlert("无法验证访问权限，请稍后重试", "错误");
          Swal.fire({
            icon: "error",
            title: "错误",
            text: "无法验证访问权限，请稍后重试",
          });
        });
    }
  } else if (tab === "ipban") {
    if (ipbanTab && ipbanPanel) {
      ipbanTab.classList.add("text-sky-600", "border-sky-600");
      ipbanTab.classList.remove("text-slate-400", "border-transparent");
      ipbanPanel.classList.remove("hidden");
      loadIPBans();
      stopHealthAutoRefresh();
    }
  } else if (tab === "sms") {
    if (smsTab && smsPanel) {
      smsTab.classList.add("text-sky-600", "border-sky-600");
      smsTab.classList.remove("text-slate-400", "border-transparent");
      smsPanel.classList.remove("hidden");
      loadSMSConfig();
      stopHealthAutoRefresh();
    }
  } else if (tab === "config") {
    if (configTab && configPanel) {
      configTab.classList.add("text-sky-600", "border-sky-600");
      configTab.classList.remove("text-slate-400", "border-transparent");
      configPanel.classList.remove("hidden");
      loadSystemConfig();
      stopHealthAutoRefresh();
    }
  } else if (tab === "captcha") {
    if (captchaTab && captchaPanel) {
      captchaTab.classList.add("text-sky-600", "border-sky-600");
      captchaTab.classList.remove("text-slate-400", "border-transparent");
      captchaPanel.classList.remove("hidden");

      const dateInput = $("captcha-history-date");
      if (dateInput) {
        const today = new Date().toISOString().split("T")[0];
        dateInput.value = today;
      }

      loadCaptchaSettings((ShowSwalFire = false));

      need_weight = document.getElementById(
        "admin-captcha-panel_modal",
      ).clientWidth;

      // 不需要预加载历史记录，改为用户点击按钮之后再加载
      // loadCaptchaHistory(need_weight);

      stopHealthAutoRefresh();
    }
  } else if (tab === "reminders") {
    const remindersTab = $("admin-tab-reminders_modal");
    const remindersPanel = $("admin-reminders-panel_modal");
    if (remindersTab && remindersPanel) {
      remindersTab.classList.add("text-sky-600", "border-sky-600");
      remindersTab.classList.remove("text-slate-400", "border-transparent");
      remindersPanel.classList.remove("hidden");
      loadReminders();
      stopHealthAutoRefresh();
      // 预加载 Editor.md 的资源以避免首次打开编辑模态时渲染问题
      // 注意：这里只加载资源，不实例化编辑器（按需实例化在 openReminderEditModal 中完成）
      if (!window._reminderEditorResourcesLoaded) {
        window._reminderEditorResourcesLoaded = true;
        const loadOnce = (url, isCss) =>
          new Promise((resolve, reject) => {
            try {
              if (
                document.querySelector(
                  isCss ? `link[href="${url}"]` : `script[src="${url}"]`,
                )
              )
                return resolve();
              const el = isCss
                ? document.createElement("link")
                : document.createElement("script");
              if (isCss) {
                el.rel = "stylesheet";
                el.href = url;
                document.head.appendChild(el);
              } else {
                el.src = url;
                document.body.appendChild(el);
              }
              el.onload = () => resolve();
              el.onerror = (e) => reject(e);
            } catch (e) {
              resolve();
            }
          });

        (async () => {
          try {
            await loadOnce("/editor.md/css/editormd.css", true).catch(() => {});
            // 先加载依赖库，再加载 editormd 本体，减少 race condition
            // await loadOnce("https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js", false).catch(
            //   () => {},
            // );
            // await loadOnce("https://cdn.jsdelivr.net/gh/google/code-prettify@master/loader/run_prettify.js", false).catch(
            //   () => {},
            // );
            // 依赖库已经预加载
            await loadOnce("/editor.md/editormd.js", false).catch(() => {});
            // 尝试在资源加载后触发已存在实例的刷新（若实例已存在）
            setTimeout(() => {
              try {
                if (
                  window.reminderEditor &&
                  typeof window.reminderEditor.recreate === "function"
                ) {
                  window.reminderEditor.recreate();
                } else if (
                  window.reminderEditor &&
                  window.reminderEditor.codeMirror &&
                  typeof window.reminderEditor.codeMirror.refresh === "function"
                ) {
                  window.reminderEditor.codeMirror.refresh();
                }
              } catch (e) {}
            }, 50);
          } catch (e) {}
        })();
      }
      // 如果还未初始化编辑器，使用一次性打开-关闭模态来强制初始化（使用示例数据）
      if (!window._reminderEditorInitialized) {
        try {
          const modalEl = document.getElementById("reminder-edit-modal");
          // 尽量避免可见闪烁：临时隐藏 modal
          let origOpacity, origPointer;
          if (modalEl) {
            origOpacity = modalEl.style.opacity || "";
            origPointer = modalEl.style.pointerEvents || "";
            modalEl.style.opacity = "0";
            modalEl.style.pointerEvents = "none";
          }
          // 打开示例编辑器初始化
          openReminderEditModal("-1");
          // 等待足够时间让编辑器完成实例化，然后关闭并恢复样式
          setTimeout(() => {
            try {
              closeReminderEditModal();
              if (modalEl) {
                modalEl.style.opacity = origOpacity;
                modalEl.style.pointerEvents = origPointer;
              }
            } catch (e) {}
          }, 700);
        } catch (e) {}
      }
      // setTimeout(() => {
      //   document.getElementById("reminder-edit-modal").style.zIndex = "0";
      //   document.getElementById("reminder-edit-modal").style.display = "hidden";
      //   document.getElementById(
      //     "reminder-edit-modal_background"
      //   ).style.display = "none";
      //   openReminderEditModal("-1");
      // }, 500);
      // setTimeout(() => {
      //   closeReminderEditModal();
      //   document.getElementById("reminder-edit-modal").style.zIndex = "";
      //   document.getElementById("reminder-edit-modal").style.display = "";
      //   document.getElementById(
      //     "reminder-edit-modal_background"
      //   ).style.display = "";
      // }, 1000);
    }
  } else if (tab === "ssl") {
    const sslTab = $("admin-tab-ssl_modal");
    const sslPanel = $("admin-ssl-panel_modal");
    if (sslTab && sslPanel) {
      sslTab.classList.add("text-sky-600", "border-sky-600");
      sslTab.classList.remove("text-slate-400", "border-transparent");
      sslPanel.classList.remove("hidden");
      loadSSLInfo();
      stopHealthAutoRefresh();
    }
  } else if (tab === "cdn") {
    // 添加CDN切换逻辑
    const cdnTab = $("admin-tab-cdn_modal");
    const cdnPanel = $("admin-cdn-panel_modal");
    if (cdnTab && cdnPanel) {
      cdnTab.classList.add("text-sky-600", "border-sky-600");
      cdnTab.classList.remove("text-slate-400", "border-transparent");
      cdnPanel.classList.remove("hidden");
      loadCDNConfig();
      stopHealthAutoRefresh();
    }
  } else if (tab === "bruteforce") {
    // 密码恢复标签切换逻辑
    //
    // 功能说明：
    // 当用户点击"密码恢复"标签时，此代码块负责：
    // 1. 高亮显示当前选中的标签（改变颜色和边框）
    // 2. 显示密码恢复管理面板
    // 3. 加载当前的密码恢复任务状态
    // 4. 停止健康状态自动刷新（因为切换到了其他面板）
    //
    // 安全说明：
    // 密码恢复功能仅供拥有god_mode权限的超级管理员使用
    // 用于合法的账号密码找回场景，切勿滥用

    // 获取密码恢复标签按钮元素（ID: admin-tab-bruteforce_modal）
    const bruteforceTab = $("admin-tab-bruteforce_modal");

    // 获取密码恢复面板容器元素（ID: admin-bruteforce-panel_modal）
    const bruteforcePanel = $("admin-bruteforce-panel_modal");

    // [调试日志] 记录标签切换操作
    console.log("[标签切换] 切换到密码恢复标签:", {
      tabElement: !!bruteforceTab, // 标签元素是否存在
      panelElement: !!bruteforcePanel, // 面板元素是否存在
      currentTab: tab, // 当前标签名称
    });

    // 检查标签和面板元素是否都存在
    // 只有两者都存在时才执行切换操作，避免空指针错误
    if (bruteforceTab && bruteforcePanel) {
      // [样式更新] 为选中的标签添加高亮样式
      // text-sky-600: 天蓝色文字
      // border-sky-600: 天蓝色边框
      bruteforceTab.classList.add("text-sky-600", "border-sky-600");

      // [样式更新] 移除未选中状态的样式
      // text-slate-400: 灰色文字（未选中状态）
      // border-transparent: 透明边框（未选中状态）
      bruteforceTab.classList.remove("text-slate-400", "border-transparent");

      // [显示面板] 移除hidden类，使密码恢复面板可见
      // Tailwind CSS的hidden类会设置display: none
      bruteforcePanel.classList.remove("hidden");

      // [调试日志] 记录样式更新成功
      console.log("[标签切换] 密码恢复标签样式已更新:", {
        tabClasses: Array.from(bruteforceTab.classList), // 标签的所有CSS类
        panelClasses: Array.from(bruteforcePanel.classList), // 面板的所有CSS类
        panelVisible: !bruteforcePanel.classList.contains("hidden"), // 面板是否可见
      });

      // [加载数据] 调用loadBruteforceStatus函数加载密码恢复任务状态
      // 该函数会从后端获取所有正在进行的密码恢复任务
      // 并更新界面上的任务列表
      console.log("[数据加载] 开始加载密码恢复任务状态...");
      loadBruteforceStatus();

      // [停止自动刷新] 停止健康状态面板的自动刷新
      // 因为已经切换到了密码恢复面板，不再需要刷新健康状态
      stopHealthAutoRefresh();

      console.log("[标签切换] 密码恢复面板切换完成");
    } else {
      // [错误处理] 如果标签或面板元素不存在，记录错误信息
      console.error("[标签切换错误] 无法切换到密码恢复标签，元素缺失:", {
        bruteforceTab: !!bruteforceTab, // 标签元素是否存在
        bruteforcePanel: !!bruteforcePanel, // 面板元素是否存在
        missingElement: !bruteforceTab
          ? "admin-tab-bruteforce_modal"
          : !bruteforcePanel
            ? "admin-bruteforce-panel_modal"
            : "未知",
      });
    }
  } else if (tab === "overdue") {
    // [标签切换] 处理欠费查询标签的切换逻辑
    // 当用户点击"欠费查询"标签时，需要显示欠费账号列表
    console.log("[标签切换] 正在切换到欠费查询标签...");

    // [获取元素] 获取欠费查询标签和面板的DOM元素
    const overdueTab = $("admin-tab-overdue_modal");
    const overduePanel = $("admin-billing-panel_modal");

    // [元素验证] 检查标签和面板元素是否存在
    if (overdueTab && overduePanel) {
      // [激活标签] 为欠费查询标签添加激活状态的CSS类
      // text-sky-600: 设置文字颜色为天蓝色，表示当前标签被选中
      // border-sky-600: 设置边框颜色为天蓝色，增强选中效果
      overdueTab.classList.add("text-sky-600", "border-sky-600");

      // [移除未激活样式] 移除未激活状态的CSS类
      // text-slate-400: 移除灰色文字（未选中状态）
      // border-transparent: 移除透明边框（未选中状态）
      overdueTab.classList.remove("text-slate-400", "border-transparent");

      // [显示面板] 移除hidden类，使欠费查询面板可见
      overduePanel.classList.remove("hidden");

      // [加载数据] 调用loadOverdueAccounts函数加载欠费账号列表
      // 该函数会从后端获取所有欠费的用户账号
      // 并在界面上显示账号信息、欠费金额、欠费时长等数据
      console.log("[数据加载] 开始加载欠费账号列表...");
      loadOverdueAccounts();

      // [停止自动刷新] 停止健康状态面板的自动刷新
      // 因为已经切换到了欠费查询面板，不再需要刷新健康状态
      stopHealthAutoRefresh();

      console.log("[标签切换] 欠费查询面板切换完成");
    } else {
      // [错误处理] 如果标签或面板元素不存在，记录错误信息
      console.error("[标签切换错误] 无法切换到欠费查询标签，元素缺失:", {
        overdueTab: !!overdueTab, // 标签元素是否存在
        overduePanel: !!overduePanel, // 面板元素是否存在
        missingElement: !overdueTab
          ? "admin-tab-overdue_modal"
          : !overduePanel
            ? "admin-billing-panel_modal"
            : "未知",
      });
    }
  } else if (tab === "payment-logs") {
    // [标签切换] 处理支付日志标签的切换逻辑
    // 当用户点击"支付日志"标签时，需要显示所有支付记录
    console.log("[标签切换] 正在切换到支付日志标签...");

    // [获取元素] 获取支付日志标签和面板的DOM元素
    const paymentLogsTab = $("admin-tab-payment-logs_modal");
    const paymentLogsPanel = $("admin-payment-logs-panel_modal");

    // [元素验证] 检查标签和面板元素是否存在
    if (paymentLogsTab && paymentLogsPanel) {
      // [激活标签] 为支付日志标签添加激活状态的CSS类
      // text-sky-600: 设置文字颜色为天蓝色，表示当前标签被选中
      // border-sky-600: 设置边框颜色为天蓝色，增强选中效果
      paymentLogsTab.classList.add("text-sky-600", "border-sky-600");

      // [移除未激活样式] 移除未激活状态的CSS类
      // text-slate-400: 移除灰色文字（未选中状态）
      // border-transparent: 移除透明边框（未选中状态）
      paymentLogsTab.classList.remove("text-slate-400", "border-transparent");

      // [显示面板] 移除hidden类，使支付日志面板可见
      paymentLogsPanel.classList.remove("hidden");

      // [加载数据] 调用loadPaymentLogs函数加载支付日志
      // 参数1: 表示从第1页开始加载数据
      // 该函数会从后端获取所有支付记录，包括：
      // - 支付时间、支付金额、支付方式
      // - 支付用户、订单号、支付状态等信息
      console.log("[数据加载] 开始加载支付日志（第1页）...");
      loadAdminPaymentLogs(1);

      // [停止自动刷新] 停止健康状态面板的自动刷新
      // 因为已经切换到了支付日志面板，不再需要刷新健康状态
      stopHealthAutoRefresh();

      console.log("[标签切换] 支付日志面板切换完成");
    } else {
      // [错误处理] 如果标签或面板元素不存在，记录错误信息
      console.error("[标签切换错误] 无法切换到支付日志标签，元素缺失:", {
        paymentLogsTab: !!paymentLogsTab, // 标签元素是否存在
        paymentLogsPanel: !!paymentLogsPanel, // 面板元素是否存在
        missingElement: !paymentLogsTab
          ? "admin-tab-payment-logs_modal"
          : !paymentLogsPanel
            ? "admin-payment-logs-panel_modal"
            : "未知",
      });
    }
  } else if (tab === "payment-settings") {
    // [标签切换] 处理支付设置标签的切换逻辑
    // 当用户点击"支付设置"标签时，需要显示支付配置界面
    console.log("[标签切换] 正在切换到支付设置标签...");

    // [获取元素] 获取支付设置标签和面板的DOM元素
    const paymentSettingsTab = $("admin-tab-payment-settings_modal");
    const paymentSettingsPanel = $("admin-payment-settings-panel_modal");

    // [元素验证] 检查标签和面板元素是否存在
    if (paymentSettingsTab && paymentSettingsPanel) {
      // [激活标签] 为支付设置标签添加激活状态的CSS类
      // text-sky-600: 设置文字颜色为天蓝色，表示当前标签被选中
      // border-sky-600: 设置边框颜色为天蓝色，增强选中效果
      paymentSettingsTab.classList.add("text-sky-600", "border-sky-600");

      // [移除未激活样式] 移除未激活状态的CSS类
      // text-slate-400: 移除灰色文字（未选中状态）
      // border-transparent: 移除透明边框（未选中状态）
      paymentSettingsTab.classList.remove(
        "text-slate-400",
        "border-transparent",
      );

      // [显示面板] 移除hidden类，使支付设置面板可见
      paymentSettingsPanel.classList.remove("hidden");

      // [面板说明] 支付设置面板有自己的子标签系统
      // 该面板内部可能包含多个子标签，如：
      // - 支付宝配置、微信支付配置、PayPal配置等
      // 这些子标签的切换由面板内部的逻辑处理，无需在此处调用额外的加载函数
      console.log("[面板说明] 支付设置面板已显示，子标签系统将自行初始化");

      // [停止自动刷新] 停止健康状态面板的自动刷新
      // 因为已经切换到了支付设置面板，不再需要刷新健康状态
      stopHealthAutoRefresh();

      console.log("[标签切换] 支付设置面板切换完成");
    } else {
      // [错误处理] 如果标签或面板元素不存在，记录错误信息
      console.error("[标签切换错误] 无法切换到支付设置标签，元素缺失:", {
        paymentSettingsTab: !!paymentSettingsTab, // 标签元素是否存在
        paymentSettingsPanel: !!paymentSettingsPanel, // 面板元素是否存在
        missingElement: !paymentSettingsTab
          ? "admin-tab-payment-settings_modal"
          : !paymentSettingsPanel
            ? "admin-payment-settings-panel_modal"
            : "未知",
      });
    }
  } else if (tab === "pricing") {
    // [标签切换] 处理价格设置标签的切换逻辑
    // 当用户点击"价格设置"标签时，需要显示价格配置界面
    console.log("[标签切换] 正在切换到价格设置标签...");

    // [获取元素] 获取价格设置标签和面板的DOM元素
    const pricingTab = $("admin-tab-pricing_modal");
    const pricingPanel = $("admin-pricing-panel_modal");

    // [元素验证] 检查标签和面板元素是否存在
    if (pricingTab && pricingPanel) {
      // [激活标签] 为价格设置标签添加激活状态的CSS类
      // text-sky-600: 设置文字颜色为天蓝色，表示当前标签被选中
      // border-sky-600: 设置边框颜色为天蓝色，增强选中效果
      pricingTab.classList.add("text-sky-600", "border-sky-600");

      // [移除未激活样式] 移除未激活状态的CSS类
      // text-slate-400: 移除灰色文字（未选中状态）
      // border-transparent: 移除透明边框（未选中状态）
      pricingTab.classList.remove("text-slate-400", "border-transparent");

      // [显示面板] 移除hidden类，使价格设置面板可见
      pricingPanel.classList.remove("hidden");

      // [加载数据] 调用loadPricingConfig函数加载当前的价格配置
      // 该函数会从后端获取价格策略配置，包括：
      // - 是否需要付费（require_payment）
      // - 单次跑步费用（per_run_cost）
      // - 新用户默认免费次数（default_available_runs）
      console.log("[数据加载] 开始加载价格配置...");
      loadPricingConfig();

      // [停止自动刷新] 停止健康状态面板的自动刷新
      // 因为已经切换到了价格设置面板，不再需要刷新健康状态
      stopHealthAutoRefresh();

      console.log("[标签切换] 价格设置面板切换完成");
    } else {
      // [错误处理] 如果标签或面板元素不存在，记录错误信息
      console.error("[标签切换错误] 无法切换到价格设置标签，元素缺失:", {
        pricingTab: !!pricingTab, // 标签元素是否存在
        pricingPanel: !!pricingPanel, // 面板元素是否存在
        missingElement: !pricingTab
          ? "admin-tab-pricing_modal"
          : !pricingPanel
            ? "admin-pricing-panel_modal"
            : "未知",
      });
    }
  } else if (tab === "watermark-control") {
    // [标签切换] 处理水印控制标签的切换逻辑
    // 当用户点击"水印控制"标签时，需要显示高德地图去水印控制界面
    console.log("[标签切换] 正在切换到水印控制标签...");

    // [获取元素] 获取水印控制标签和面板的DOM元素
    const watermarkControlTab = $("admin-tab-watermark-control_modal");
    const watermarkControlPanel = $("admin-watermark-control-panel_modal");

    // [元素验证] 检查标签和面板元素是否存在
    if (watermarkControlTab && watermarkControlPanel) {
      // [激活标签] 为水印控制标签添加激活状态的CSS类
      // text-sky-600: 设置文字颜色为天蓝色，表示当前标签被选中
      // border-sky-600: 设置边框颜色为天蓝色，增强选中效果
      watermarkControlTab.classList.add("text-sky-600", "border-sky-600");

      // [移除未激活样式] 移除未激活状态的CSS类
      // text-slate-400: 移除灰色文字（未选中状态）
      // border-transparent: 移除透明边框（未选中状态）
      watermarkControlTab.classList.remove(
        "text-slate-400",
        "border-transparent",
      );

      // [显示面板] 移除hidden类，使水印控制面板可见
      watermarkControlPanel.classList.remove("hidden");

      // [加载数据] 调用loadWatermarkControlConfig函数加载水印控制配置
      // 该函数会从后端获取水印控制配置，包括：
      // - 系统默认值（是否允许去水印）
      // - 各个用户的个性化配置（用户级别的权限控制）
      console.log("[数据加载] 开始加载水印控制配置...");
      loadWatermarkControlConfig();

      // [停止自动刷新] 停止健康状态面板的自动刷新
      // 因为已经切换到了水印控制面板，不再需要刷新健康状态
      stopHealthAutoRefresh();
      loadWatermarkControlConfig();

      console.log("[标签切换] 水印控制面板切换完成");
    } else {
      // [错误处理] 如果标签或面板元素不存在，记录错误信息
      console.error("[标签切换错误] 无法切换到水印控制标签，元素缺失:", {
        watermarkControlTab: !!watermarkControlTab, // 标签元素是否存在
        watermarkControlPanel: !!watermarkControlPanel, // 面板元素是否存在
        missingElement: !watermarkControlTab
          ? "admin-tab-watermark-control_modal"
          : !watermarkControlPanel
            ? "admin-watermark-control-panel_modal"
            : "未知",
      });
    }
  } else if (tab === "admin-billing") {
    // 账单管理面板
    if (adminBillingTab && adminBillingPanel) {
      adminBillingTab.classList.add("text-sky-600", "border-sky-600");
      adminBillingTab.classList.remove("text-slate-400", "border-transparent");
      adminBillingPanel.classList.remove("hidden");
    }
    stopHealthAutoRefresh();
    loadAdminBillingList();
  } else if (tab === "admin-billing-logs") {
    if (billingLogsTab && billingLogsPanel) {
      billingLogsTab.classList.add("text-sky-600", "border-sky-600");
      billingLogsTab.classList.remove("text-slate-400", "border-transparent");
      billingLogsPanel.classList.remove("hidden");
    }
    stopHealthAutoRefresh();
    loadAdminBillingLogs(1);
  } else if (tab === "restore-account") {
    // 恢复账号面板
    if (restoreAccountTab && restoreAccountPanel) {
      restoreAccountTab.classList.add("text-sky-600", "border-sky-600");
      restoreAccountTab.classList.remove(
        "text-slate-400",
        "border-transparent",
      );
      restoreAccountPanel.classList.remove("hidden");
    }
    stopHealthAutoRefresh();
    loadRemovedAccountsList();
  } else {
    if (profileTab && profilePanel) {
      profileTab.classList.add("text-sky-600", "border-sky-600");
      profileTab.classList.remove("text-slate-400", "border-transparent");
      profilePanel.classList.remove("hidden");
      loadPersonalInfo();
    }
    stopHealthAutoRefresh();
  }
}
async function updatePassword() {
  // 弹出确认对话框，询问用户是否确认修改密码
  const confirmed = await jsShowConfirm(
    "确认修改密码",
    "您确定要修改您的登录密码吗？\n\n修改后需要使用新密码重新登录。",
  );
  // 如果用户取消操作，则直接返回
  if (!confirmed) {
    logMessage_Info("[修改密码] 用户取消了密码修改操作");
    return;
  }

  // 获取各个密码输入框的DOM元素
  const currentPassword = $("profile-current-password"); // 当前密码输入框
  const newPassword = $("profile-new-password"); // 新密码输入框
  const confirmPassword = $("profile-confirm-password"); // 确认新密码输入框

  // 检查必要的DOM元素是否存在
  if (!newPassword || !confirmPassword) return;

  // 判断当前是否使用短信验证模式
  const useSmsVerify = pcPasswordVerifyMode === "sms";
  // 如果是短信验证模式，获取短信验证码
  const smsCode = useSmsVerify
    ? document.getElementById("pc-password-sms-code")?.value?.trim()
    : null;

  // 根据验证模式进行不同的校验
  if (!useSmsVerify) {
    // 密码验证模式：检查原密码是否填写
    if (!currentPassword || !currentPassword.value) {
      // showModalAlert(
      //   '请填写当前密码，或点击"使用短信验证"通过短信验证码修改密码',
      //   "提示"
      // );
      Swal.fire({
        title: "提示",
        text: '请填写当前密码，或点击"使用短信验证"通过短信验证码修改密码',
        icon: "info",
      });
      return;
    }
  } else {
    // 短信验证模式：检查验证码是否填写
    if (!smsCode) {
      // showModalAlert("请填写短信验证码", "提示");
      Swal.fire({
        title: "提示",
        text: "请填写短信验证码",
        icon: "info",
      });
      return;
    }
    // 验证码格式校验（6位数字）
    if (!/^\d{6}$/.test(smsCode)) {
      // showModalAlert("短信验证码格式不正确，请输入6位数字", "提示");
      Swal.fire({
        title: "提示",
        text: "短信验证码格式不正确，请输入6位数字",
        icon: "info",
      });
      return;
    }
  }

  // 检查新密码是否填写
  if (!newPassword.value || !confirmPassword.value) {
    // showModalAlert("请填写新密码和确认新密码", "提示");
    Swal.fire({
      title: "提示",
      text: "请填写新密码和确认新密码",
      icon: "info",
    });
    return;
  }

  // 检查两次输入的新密码是否一致
  if (newPassword.value !== confirmPassword.value) {
    // showModalAlert("两次输入的密码不一致", "错误");
    Swal.fire({
      title: "错误",
      text: "两次输入的密码不一致",
      icon: "error",
    });
    return;
  }

  // 检查新密码强度
  // 在提交密码修改请求之前，先检查新密码是否为弱密码
  // 这可以防止用户设置不安全的密码，提高账户安全性
  var weakCheck = checkWeakPassword(newPassword.value);
  if (weakCheck.isWeak) {
    // 如果新密码过弱，显示具体的错误原因
    // showModalAlert(weakCheck.reason, "密码强度不足");
    Swal.fire({
      title: "错误",
      text: weakCheck.reason,
      icon: "error",
    });
    return;
  }

  // 检查新密码长度是否符合要求（最少6位）
  if (newPassword.value.length < 6) {
    // showModalAlert("密码长度至少为6个字符", "错误");
    Swal.fire({
      title: "错误",
      text: "密码长度至少为6个字符",
      icon: "error",
    });
    return;
  }

  // 检查当前用户信息是否可用
  if (!currentAuthUsername) {
    // showModalAlert("无法获取当前用户信息，请重新加载个人信息", "错误");
    Swal.fire({
      title: "错误",
      text: "无法获取当前用户信息，请重新加载个人信息",
      icon: "error",
    });
    return;
  }

  try {
    // 构建API请求体
    const requestBody = {
      username: currentAuthUsername, // 当前用户名
      new_password: newPassword.value, // 新密码
    };

    // 根据验证模式添加不同的验证字段
    if (useSmsVerify) {
      // 短信验证模式：传递短信验证码，原密码设为null
      requestBody.sms_code = smsCode;
      requestBody.old_password = null;
      logMessage_Info("[密码修改] PC端使用短信验证模式提交");
    } else {
      // 密码验证模式：传递原密码
      requestBody.old_password = currentPassword.value;
      logMessage_Info("[密码修改] PC端使用密码验证模式提交");
    }

    // 发送密码修改请求到后端API
    const response = await fetch("/auth/admin/reset_password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(requestBody),
    });

    // 解析API响应
    const result = await response.json();

    if (result.success) {
      // 密码修改成功
      // showModalAlert("密码修改成功！", "成功");
      Swal.fire({
        title: "成功",
        text: "密码修改成功！",
        icon: "success",
      });
      // 清空所有输入框
      if (currentPassword) currentPassword.value = "";
      newPassword.value = "";
      confirmPassword.value = "";
      // 重置验证模式到默认状态（密码验证）
      resetPasswordVerifyMode("pc");
    } else {
      // 密码修改失败，显示错误信息
      const errorMsg = useSmsVerify
        ? result.message || "请检查短信验证码是否正确"
        : result.message || "请检查当前密码是否正确";
      // showModalAlert(`修改失败: ${errorMsg}`, "错误");
      Swal.fire({
        title: "错误",
        text: `修改失败: ${errorMsg}`,
        icon: "error",
      });
    }
  } catch (e) {
    // 捕获网络错误或其他异常
    logMessage_Error("修改密码失败:", e);
    // showModalAlert(`修改失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: `修改失败: ${e.message}`,
      icon: "error",
    });
  }
}

async function generate2FA() {
  try {
    const response = await fetch("/auth/2fa/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();

    if (!result.success) {
      // showModalAlert(`生成2FA失败: ${result.message}`, "错误");
      Swal.fire({
        title: "错误",
        text: `生成2FA失败: ${result.message}`,
        icon: "error",
      });
      return;
    }
    const setupDiv = $("profile-2fa-setup");
    const actionsDiv = $("profile-2fa-actions");
    if (setupDiv) setupDiv.classList.remove("hidden");
    if (actionsDiv) actionsDiv.classList.add("hidden");
    const secretSpan = $("profile-2fa-secret");
    if (secretSpan && result.secret) {
      secretSpan.textContent = result.secret;
    }
    const qrCanvas = $("profile-2fa-qr");
    if (qrCanvas && result.qr_uri) {
      if (typeof QRCode !== "undefined") {
        qrCanvas.width = 200;
        qrCanvas.height = 200;

        QRCode.toCanvas(
          qrCanvas,
          result.qr_uri,
          { width: 200 },
          function (error) {
            if (error) {
              logMessage_Error("QR Code generation error:", error);
              // showModalAlert("二维码生成失败", "错误");
              Swal.fire({
                title: "错误",
                text: "二维码生成失败",
                icon: "error",
              });
            } else {
              logMessage_Info("QR Code generated successfully");
            }
          },
        );
      } else {
        logMessage_Error("QRCode库未加载");
        // showModalAlert("QRCode库未加载，请刷新页面重试", "错误");
        Swal.fire({
          title: "错误",
          text: "QRCode库未加载，请刷新页面重试",
          icon: "error",
        });
      }
    }
  } catch (e) {
    logMessage_Error("生成2FA失败:", e);
    // showModalAlert(`生成失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: `生成失败: ${e.message}`,
      icon: "error",
    });
  }
}

async function enable2FA() {
  const codeInput = $("profile-2fa-code");
  if (!codeInput || !codeInput.value) {
    // showModalAlert("请输入验证码", "提示");
    Swal.fire({
      title: "提示",
      text: "请输入验证码",
      icon: "info",
    });
    return;
  }

  try {
    const response = await fetch("/auth/2fa/enable", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        code: codeInput.value,
      }),
    });
    const result = await response.json();

    if (result.success) {
      // showModalAlert("2FA启用成功！", "成功");
      Swal.fire({
        title: "成功",
        text: "2FA启用成功！",
        icon: "success",
      });
      const setupDiv = $("profile-2fa-setup");
      const actionsDiv = $("profile-2fa-actions");
      if (setupDiv) setupDiv.classList.add("hidden");
      if (actionsDiv) actionsDiv.classList.remove("hidden");
      loadPersonalInfo();
    } else {
      // showModalAlert(`启用失败: ${result.message}`, "错误");
      Swal.fire({
        title: "错误",
        text: `启用失败: ${result.message}`,
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("启用2FA失败:", e);
    // showModalAlert(`启用失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: `启用失败: ${e.message}`,
      icon: "error",
    });
  }
}

async function disable2FA() {
  const confirmed = await jsShowConfirm(
    "确认关闭2FA",
    "关闭双因素认证后，账号安全性将降低。确定要继续吗？",
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/2fa/disable", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();

    if (result.success) {
      // showModalAlert("2FA已关闭", "成功");
      Swal.fire({
        title: "成功",
        text: "2FA已关闭",
        icon: "success",
      });
      loadPersonalInfo();
    } else {
      // showModalAlert(`关闭失败: ${result.message}`, "错误");
      Swal.fire({
        title: "错误",
        text: `关闭失败: ${result.message}`,
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("关闭2FA失败:", e);
    // showModalAlert(`关闭失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: `关闭失败: ${e.message}`,
      icon: "error",
    });
  }
}

function showMobileTest2FAModal() {
  return new Promise((resolve) => {
    let modal = document.getElementById("mobile-test-2fa-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "mobile-test-2fa-modal";
      modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
      modal.onclick = function (e) {
        if (e.target === modal) closeMobileTest2FAModal();
      };
      modal.innerHTML = `
        <div class="absolute inset-0 bg-black/40" onclick="closeMobileTest2FAModal()"></div>
        <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
          <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileTest2FAModal()">
            <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
          </div>
          <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileTest2FAModal()">
            <svg class="w-6 h-6 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 11c0-1.657 1.343-3 3-3h1a3 3 0 013 3v7a3 3 0 01-3 3H8a3 3 0 01-3-3v-7a3 3 0 013-3h1c1.657 0 3 1.343 3 3zm0 0V8a3 3 0 116 0v3m-6 0h6"></path>
            </svg>
            <h3 class="text-xl font-bold text-sky-600 text-center">测试2FA</h3>
          </div>
          <div class="space-y-3">
            <div>
              <label class="block text-xs font-medium text-slate-600 mb-1">验证码</label>
              <input
                type="text"
                id="mobile-test-2fa-code"
                class="input-field !text-xs !py-1.5 w-full"
                placeholder="请输入验证器中的6位验证码"
                maxlength="6"
                inputmode="numeric"
              />
            </div>
          </div>
          <div class="flex gap-3 pt-4 border-t border-slate-100">
            <button onclick="closeMobileTest2FAModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
            <button id="mobile-test-2fa-confirm" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">验证</button>
          </div>
        </div>
      `;
      document.body.appendChild(modal);
    }

    const codeInput = document.getElementById("mobile-test-2fa-code");
    const confirmBtn = document.getElementById("mobile-test-2fa-confirm");

    if (codeInput) codeInput.value = "";

    const cleanup = () => {
      window._mobileTest2FAResolver = null;
      if (confirmBtn) confirmBtn.onclick = null;
      if (codeInput) codeInput.onkeypress = null;
    };

    window._mobileTest2FAResolver = (code = null) => {
      cleanup();
      resolve(code);
    };

    if (confirmBtn) {
      confirmBtn.onclick = () => {
        const code = codeInput ? codeInput.value.trim() : "";
        if (!/^[0-9]{6}$/.test(code)) {
          showModalAlert("请输入有效的6位数字验证码", "错误");
          return;
        }
        closeMobileTest2FAModal(code);
      };
    }

    if (codeInput) {
      codeInput.onkeypress = (e) => {
        if (e.key === "Enter") {
          confirmBtn?.click();
        }
      };
    }

    modal.classList.remove("hidden");
    setTimeout(() => {
      modal.classList.add("show");
      codeInput?.focus();
    }, 10);
  });
}

function closeMobileTest2FAModal(code = null) {
  const modal = document.getElementById("mobile-test-2fa-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
      if (typeof window._mobileTest2FAResolver === "function") {
        const resolver = window._mobileTest2FAResolver;
        window._mobileTest2FAResolver = null;
        resolver(code);
      }
    }, 300);
  } else if (typeof window._mobileTest2FAResolver === "function") {
    const resolver = window._mobileTest2FAResolver;
    window._mobileTest2FAResolver = null;
    resolver(code);
  }
}

async function test2FA() {
  const testCode = await new Promise((resolve) => {
    if (isMobileMode) {
      showMobileTest2FAModal().then(resolve);
      return;
    }

    const modal = document.createElement("div");
    modal.className = "fixed inset-0 flex items-center justify-center z-50";
    modal.innerHTML = `
          <div class="fixed inset-0 bg-black bg-opacity-50" onclick="this.parentElement.remove()"></div>
          <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 relative z-10">
            <h3 class="text-lg font-semibold text-slate-800 mb-4">测试2FA</h3>
            <div class="mb-4">
              <label class="block text-sm font-semibold text-slate-700 mb-2">请输入验证器中的6位验证码</label>
              <input type="text" id="test-2fa-code-input" class="input-field w-full" placeholder="输入6位验证码" maxlength="6" inputmode="numeric">
            </div>
            <div class="flex gap-2 justify-end">
              <button class="btn btn-ghost" onclick="this.closest('.fixed').remove()">取消</button>
              <button class="btn btn-primary" id="confirm-test-2fa">验证</button>
            </div>
          </div>
        `;
    document.body.appendChild(modal);

    const confirmBtn = modal.querySelector("#confirm-test-2fa");
    const codeInput = modal.querySelector("#test-2fa-code-input");

    const finish = (code = null) => {
      if (modal.parentNode) {
        modal.remove();
      }
      resolve(code);
    };

    modal.querySelector(".bg-black")?.addEventListener("click", () => finish(null));
    modal.querySelector(".btn-ghost")?.addEventListener("click", () => finish(null));

    confirmBtn.onclick = () => {
      const code = codeInput.value.trim();
      if (!code || code.length !== 6 || !/^[0-9]{6}$/.test(code)) {
        Swal.fire({
          title: "错误",
          text: "请输入有效的6位数字验证码",
          icon: "error",
        });
        return;
      }
      finish(code);
    };

    codeInput?.addEventListener("keypress", (e) => {
      if (e.key === "Enter") {
        confirmBtn.click();
      }
    });
  });

  if (!testCode) return;

  try {
    const response = await fetch("/auth/2fa/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        code: testCode,
      }),
    });
    const result = await response.json();

    if (result.success) {
      // showModalAlert("2FA验证成功！您的双因素认证工作正常。", "成功");
      Swal.fire({
        title: "成功",
        text: "2FA验证成功！您的双因素认证工作正常。",
        icon: "success",
      });
    } else {
      // showModalAlert(`验证失败: ${result.message || "验证码错误"}`, "错误");
      Swal.fire({
        title: "错误",
        text: `验证失败: ${result.message || "验证码错误"}`,
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("测试2FA失败:", e);
    // showModalAlert(`测试失败: ${e.message}`, "错误");
    Swal.fire({
      title: "错误",
      text: `测试失败: ${e.message}`,
      icon: "error",
    });
  }
}

// =======创建用户对话框
function Get_YiPAi_device() {
  const ua = navigator.userAgent.toLowerCase();

  // 1. 支付宝
  if (ua.includes("alipayclient") || ua.includes("alipay")) {
    return "alipay";
  }

  // 2. 微信
  if (ua.includes("micromessenger")) {
    return "wechat";
  }

  // 3. QQ 内置浏览器（注意：QQ 浏览器和 QQ 内置浏览器 UA 不同）
  if (
    ua.includes("qq/") ||
    (ua.includes("mqqbrowser") && ua.includes("mobile"))
  ) {
    return "qq";
  }

  // 4. 手机浏览器（只要 UA 里出现 mobile 字样，就认为是手机浏览器）
  if (/mobile|android|touch|webos|hpwos/.test(ua)) {
    return "mobile";
  }

  // 5. 默认返回 pc
  return "pc";
}

async function deleteGroup(groupKey) {
  const confirmed = await jsShowConfirm(
    "确认删除",
    `确定要删除权限组 ${groupKey} 吗？\n此操作不可恢复！`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/delete_group", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ group_key: groupKey }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`权限组 ${groupKey} 已删除`, "成功");
      Swal.fire({
        title: "成功",
        text: `权限组 ${groupKey} 已删除`,
        icon: "success",
      });
      loadAdminGroups();
    } else {
      // showModalAlert(result.message || "删除失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "删除失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function editGroupPermissions(groupKey) {
  currentEditGroupKey = groupKey;
  if (groupKey === null || groupKey === undefined) return;
  if (groupKey === "super_admin") {
    // showModalAlert("无法编辑超级管理员权限组", "错误");
    Swal.fire({
      title: "错误",
      text: "无法编辑超级管理员权限组",
      icon: "error",
    });
    return;
  }
  const modal = $("edit-group-permissions-modal");
  if (!modal) return;

  try {
    const response = await fetch("/auth/admin/list_groups", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (!result.success || !result.groups || !result.groups[groupKey]) {
      // showModalAlert("无法加载权限组信息", "错误");
      Swal.fire({
        title: "错误",
        text: "无法加载权限组信息",
        icon: "error",
      });
      return;
    }

    const group = result.groups[groupKey];
    const nameEl = $("edit-group-name");
    if (nameEl) {
      nameEl.textContent = `${group.name} (${groupKey})`;
    }

    const permissionsContainer = $("edit-group-permissions-list");
    if (permissionsContainer && group.permissions) {
      permissionsContainer.innerHTML = Object.keys(group.permissions)
        .map(
          (perm) => `
            <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded cursor-pointer">
              <input type="checkbox" class="w-4 h-4 rounded" data-permission="${perm}" ${
                group.permissions[perm] ? "checked" : ""
              }>
              <span class="text-sm text-slate-700">${translatePermission(
                perm,
              )}</span>
            </label>
          `,
        )
        .join("");
    }

    modal.classList.remove("hidden");
    modal.classList.add("flex");
  } catch (e) {
    // showModalAlert("加载失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "加载失败: " + e.message,
      icon: "error",
    });
  }
}

function closeEditGroupPermissionsModal() {
  const modal = $("edit-group-permissions-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
  currentEditGroupKey = null;
}

async function submitEditGroupPermissions() {
  if (!currentEditGroupKey) return;

  const permissionsContainer = $("edit-group-permissions-list");
  if (!permissionsContainer) return;

  const permissions = {};
  const checkboxes = permissionsContainer.querySelectorAll(
    'input[type="checkbox"]',
  );
  checkboxes.forEach((cb) => {
    const perm = cb.getAttribute("data-permission");
    permissions[perm] = cb.checked;
  });

  try {
    const response = await fetch("/auth/admin/update_group", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        group_key: currentEditGroupKey,
        permissions: permissions,
      }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`权限组 ${currentEditGroupKey} 已更新`, "成功");
      Swal.fire({
        title: "成功",
        text: `权限组 ${currentEditGroupKey} 已更新`,
        icon: "success",
      });
      closeEditGroupPermissionsModal();
      loadAdminGroups();
    } else {
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function loadAdminGroups() {
  try {
    const response = await fetch("/auth/admin/list_groups", {
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();

    if (!result.success) {
      $("admin-groups-list").innerHTML =
        `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      return;
    }

    const listEl = $("admin-groups-list_modal");
    const groups = result.groups;

    listEl.innerHTML = Object.keys(groups)
      .map((groupKey) => {
        const group = groups[groupKey];
        const perms = group.permissions;
        const isSystemGroup =
          group.system ||
          ["guest", "user", "admin", "super_admin"].includes(groupKey);
        const systemBadge = isSystemGroup
          ? '<span class="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full ml-2">系统预设</span>'
          : "";
        const displayGroupKey = groupKey
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");

        return `
        <div class="border border-slate-200 rounded-lg p-4 mb-2">
          <div class="flex justify-between items-start mb-2">
            <h5 class="font-semibold text-slate-800">${
              group.name
            } (${displayGroupKey})${systemBadge}</h5>
            <div class="flex gap-2">
              <button class="btn btn-ghost !py-0.5 !px-2 !text-xs" onclick="editGroupPermissions(${escapeInlineJsArg(groupKey)})">编辑权限</button>
              ${
                !isSystemGroup
                  ? `<button class="btn btn-danger !py-0.5 !px-2 !text-xs" onclick="deleteGroup(${escapeInlineJsArg(groupKey)})">删除</button>`
                  : ""
              }
            </div>
          </div>
          <div class="grid grid-cols-2 gap-2 text-sm">
            ${Object.keys(perms)
              .map(
                (perm) => `
              <div class="flex items-center gap-2">
                <span class="${
                  perms[perm] ? "text-green-600" : "text-slate-400"
                }">${perms[perm] ? "✓" : "✗"}</span>
                <span class="text-slate-600">${translatePermission(perm)}</span>
              </div>
            `,
              )
              .join("")}
          </div>
        </div>
      `;
      })
      .join("");
  } catch (e) {
    $("admin-groups-list").innerHTML =
      `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

async function loadAdminSessions() {
  const listEl = $("admin-sessions-list_modal");

  if (!listEl) {
    logMessage_Error(
      "loadAdminSessions: 无法找到会话列表容器 'admin-sessions-list_modal'。",
    );
    // showModalAlert("无法加载会话列表：界面元素丢失。", "错误");
    Swal.fire({
      title: "错误",
      text: "无法加载会话列表：界面元素丢失。",
      icon: "error",
    });
    return;
  }

  try {
    listEl.innerHTML =
      '<p class="text-slate-400 text-center py-10">加载中...</p>';
    const godModeCheckbox = $("god-mode-checkbox_modal");
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
      updateAdminSessionCountDisplay(validSessions.length, -1, true);
    } else {
      updateAdminSessionCountDisplay(validSessions.length, maxSessions);
    }

    let html = "";
    const isGuest = currentUserIsGuest;
    if (!isGodMode) {
      if (!isGuest) {
        html = `
      <div class="mb-4 p-3 bg-sky-50 border border-sky-200 rounded-lg">
        <p class="text-sm text-slate-700 mb-2">选择现有会话或创建新会话</p>
        <button class="btn btn-primary w-full" onclick="createNewSessionFromPicker()">创建新会话</button>
      </div>
    `;
      } else {
        html = `
      <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p class="text-sm text-blue-700">游客模式：当前会话如下。如需使用多个会话，请注册账号。</p>
      </div>
    `;
      }
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
            isCurrent ? "border-sky-500 bg-sky-50" : "border-slate-200"
          } rounded-lg p-3 mb-2">
            <div class="flex justify-between items-start">
              <div class="flex-1">
                <p class="font-semibold text-slate-800 break-all">会话 ${
                  session.session_id
                }</p>
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
    listEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

// 移动端专用：加载管理员会话列表（复用移动端卡片样式）
async function loadMobileAdminSessionsList() {
  // 同时支持多账号面板和单账号面板的容器
  const containers = [
    document.getElementById("mobile-multi-admin-sessions-list"),
    document.getElementById("mobile-admin-sessions-list-panel"),
  ];

  const activeContainer = containers.find((c) => c && !c.closest(".hidden"));
  if (!activeContainer) return;

  activeContainer.innerHTML =
    '<div class="flex flex-col items-center justify-center py-10"><div class="w-8 h-8 border-4 border-sky-100 border-t-sky-500 rounded-full animate-spin mb-3"></div><span class="text-xs text-slate-400 font-medium">正在加载会话...</span></div>';

  try {
    // 检查上帝模式复选框 (兼容多账号面板和单账号面板的ID)
    const godChkMulti = document.getElementById(
      "mobile-multi-god-mode-checkbox",
    );
    const godChkSingle = document.getElementById(
      "mobile-god-mode-checkbox-panel",
    );

    // 判断哪个复选框是可见的/有效的
    const isGodMode =
      (godChkMulti &&
        godChkMulti.offsetParent !== null &&
        godChkMulti.checked) ||
      (godChkSingle &&
        godChkSingle.offsetParent !== null &&
        godChkSingle.checked);

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
        headers: { "X-Session-ID": getAuthenticatedSessionHeaderValue() },
      });
    }

    const result = await response.json();
    if (!result.success) {
      activeContainer.innerHTML = `<div class="mx-4 mt-4 p-3 bg-red-50 border border-red-100 rounded-xl text-center"><p class="text-red-500 text-xs font-medium">${result.message}</p></div>`;
      return;
    }

    const sessions = result.sessions || [];
    // 过滤无效会话
    const validSessions = sessions.filter(
      (s) =>
        s.session_id && s.session_id !== "null" && s.session_id.trim() !== "",
    );

    // 更新计数显示
    const countElMulti = document.getElementById(
      "mobile-multi-admin-session-count-display",
    );
    const countElSingle = document.getElementById(
      "mobile-admin-session-count-display-panel",
    );

    // 新增：处理创建按钮显示状态
    const createContainerMulti = document.getElementById(
      "mobile-multi-admin-create-session-container",
    );

    // 计算显示文本
    let countText = "";
    const currentCount = validSessions.length;

    if (isGodMode) {
      // 上帝模式：只显示总数，隐藏创建按钮
      countText = `系统总会话: ${currentCount}`;
      if (createContainerMulti) createContainerMulti.classList.add("hidden");
    } else {
      // 普通模式
      const maxSessions =
        result.max_sessions !== undefined ? result.max_sessions : -1;

      if (typeof currentUserIsGuest !== "undefined" && currentUserIsGuest) {
        // 游客模式
        countText = `会话: 1 / 1 (游客)`;
        if (createContainerMulti) createContainerMulti.classList.add("hidden");
      } else {
        // 注册用户
        if (maxSessions === -1) {
          countText = `会话: ${currentCount} / ∞`;
        } else {
          countText = `会话: ${currentCount} / ${maxSessions}`;
        }
        if (createContainerMulti)
          createContainerMulti.classList.remove("hidden");
      }
    }

    if (countElMulti) countElMulti.textContent = countText;
    if (countElSingle) countElSingle.textContent = countText;

    if (validSessions.length === 0) {
      activeContainer.innerHTML =
        '<div class="flex flex-col items-center justify-center py-12 opacity-60"><div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mb-3"><svg class="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg></div><p class="text-slate-500 text-sm font-medium">暂无会话</p></div>';
      return;
    }

    // 清空容器准备重新渲染
    activeContainer.innerHTML = "";

    // 按时间倒序
    validSessions.sort((a, b) => (b.created_at || 0) - (a.created_at || 0));

    validSessions.forEach((session) => {
      // ... (时间格式化代码保持不变) ...
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
      const fullSessionId = session.session_id;
      const ownerUsername = String(
        session.username || (isGodMode ? "" : currentAuthUsername || ""),
      );
      const isMulti = session.is_multi_account_mode;
      const loginStatus = session.login_success;

      // 构建拥有者信息
      let ownerBadge = "";
      if (session.username) {
        ownerBadge = `<div class="flex items-center gap-1 text-[10px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full"><span class="font-bold">👤</span> ${escapeHtml(
          session.username,
        )}</div>`;
      } else {
        ownerBadge = `<div class="flex items-center gap-1 text-[10px] text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">👤 游客</div>`;
      }

      const itemDiv = document.createElement("div");
      const activeClass = isCurrent
        ? "border-blue-400/30 bg-gradient-to-br from-sky-50 via-white to-blue-50 shadow-md ring-1 ring-blue-200"
        : "border-slate-100 bg-white shadow-sm hover:border-slate-200 hover:shadow-md";

      itemDiv.className = `relative group rounded-2xl border p-4 mb-4 transition-all duration-300 active:scale-[0.98] touch-manipulation select-none ${activeClass}`;

      // 统一使用带有 press-overlay 的 HTML 结构
      itemDiv.innerHTML = `
                <div class="flex flex-col gap-2 relative z-10">
                    <div class="flex flex-col">
                        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">会话 UUID</span>
                        <div class="font-mono text-xs font-bold text-slate-700 break-all select-all bg-slate-50 px-3 py-2 rounded-lg border border-slate-100">
                            ${fullSessionId}
                        </div>
                    </div>
                    <div class="flex justify-between items-center border-b border-slate-50 pb-2 pt-1">
                        <span class="text-xs text-slate-400 font-medium">创建时间</span>
                        <span class="text-xs font-mono text-slate-600 bg-white px-2 py-0.5 rounded border border-slate-100">${dateStr}</span>
                    </div>
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-400 font-medium">登录状态</span>
                         ${
                           loginStatus
                             ? `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-emerald-50 text-emerald-600 text-xs font-bold border border-emerald-100"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> 已登录</span>`
                             : `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-slate-100 text-slate-500 text-xs font-bold border border-slate-200"><span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span> 未登录</span>`
                         }
                    </div>
                    ${
                      session.username && isGodMode
                        ? `<div class="flex justify-between items-center pt-2 mt-1 border-t border-red-50"><span class="text-xs font-medium text-red-300">创建者</span>${ownerBadge}</div>`
                        : ""
                    }
                    ${
                      isCurrent
                        ? `<div class="mt-2 pt-2 border-t border-blue-50 flex justify-center"><span class="inline-flex items-center gap-1 px-4 py-1 rounded-full bg-gradient-to-r from-blue-500 to-sky-500 text-white text-xs font-bold shadow-sm">当前会话</span></div>`
                        : ""
                    }
                </div>

                <div class="press-overlay absolute inset-0 bg-slate-800/90 backdrop-blur-[2px] rounded-2xl flex flex-col items-center justify-center opacity-0 transition-all duration-300 pointer-events-none z-20 scale-95">
                     <div class="w-14 h-14 ${
                       isCurrent ? "bg-slate-500" : "bg-red-500"
                     } rounded-full flex items-center justify-center mb-3 shadow-lg animate-pulse">
                        ${
                          isCurrent
                            ? '<svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>'
                            : '<svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>'
                        }
                     </div>
                     <span class="font-bold text-white text-sm tracking-widest">${
                       isCurrent ? "当前会话无法删除" : "松手即删除"
                     }</span>
                </div>
            `;

      // 绑定交互逻辑 (支持长按)
      let timer = null;
      let isLongPress = false;
      let startX = 0,
        startY = 0;
      const overlay = itemDiv.querySelector(".press-overlay");
      const overlayContent = overlay ? overlay.querySelector("div") : null;

      const startPress = (e) => {
        isLongPress = false;
        const touch = e.touches ? e.touches[0] : e;
        startX = touch.clientX;
        startY = touch.clientY;

        timer = setTimeout(() => {
          isLongPress = true;
          if (navigator.vibrate) navigator.vibrate(50);
          if (overlay) {
            overlay.classList.remove("opacity-0");
            if (overlayContent) {
              overlayContent.classList.remove("scale-95");
              overlayContent.classList.add("scale-100");
            }
          }
        }, 500);
      };

      const movePress = (e) => {
        if (!timer) return;
        const touch = e.touches ? e.touches[0] : e;
        if (
          Math.abs(touch.clientX - startX) > 10 ||
          Math.abs(touch.clientY - startY) > 10
        ) {
          clearTimeout(timer);
          timer = null;
          if (overlay) overlay.classList.add("opacity-0");
        }
      };

      const endPress = (e) => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        if (overlay) {
          overlay.classList.add("opacity-0");
          if (overlayContent) {
            overlayContent.classList.add("scale-95");
            overlayContent.classList.remove("scale-100");
          }
        }

        if (isLongPress) {
          e.preventDefault();
          if (isCurrent) {
            // showModalAlert(
            //   "当前会话处于活动状态，无法删除。\n如需删除，请先切换到其他会话。",
            //   "操作受限"
            // );
            Swal.fire({
              title: "操作受限",
              text: "当前会话处于活动状态，无法删除。如需删除，请先切换到其他会话。",
              icon: "warning",
            });
          } else {
            const confirmText = isGodMode
              ? `确定要销毁此会话吗？\nUUID: ${fullSessionId}\n(上帝模式强制销毁)`
              : `确定要删除此会话吗？\nUUID: ${fullSessionId}`;

            showMobileConfirm("删除会话", confirmText, () => {
              if (isGodMode) {
                // 传入 false 以跳过 destroySession 内部的二次确认
                destroySession(session.session_id, false);
              } else {
                // 传入 false 以跳过 deleteSession 内部的二次确认
                deleteSession(session.session_id, false);
              }
            });
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
          // 两次点击间隔小于 350ms 视为双击
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
      itemDiv.addEventListener("mousedown", startPress);
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

      activeContainer.appendChild(itemDiv);
    });
  } catch (e) {
    console.error("加载移动端管理员会话列表失败:", e);
    activeContainer.innerHTML = `<div class="flex flex-col items-center justify-center py-8 text-red-400 bg-red-50 rounded-xl border border-red-100 m-4"><svg class="w-8 h-8 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg><p class="text-xs font-medium">加载失败: ${e.message}</p></div>`;
  }
}

// ========== 留言板功能 ========== //
async function checkIPBanAndProceed(scope = "all") {
  try {
    const response = await fetch("/api/admin/check_ip_ban", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ scope: scope }),
    });

    const result = await response.json();

    return result.is_banned === true;
  } catch (err) {
    logMessage_Error("[IP封禁检查] 检查失败:", err);
    return false;
  }
}

async function loadMessages() {
  const listEl = $("admin-messages-list_modal");
  const guestFields = $("message-guest-fields");

  if (!listEl) {
    logMessage_Error("loadMessages: 无法找到留言列表容器");
    return;
  }
  const isGuest = currentUserIsGuest;
  if (guestFields) {
    guestFields.style.display = isGuest ? "block" : "none";
  }
  const contentInput = $("message-content");
  const charCount = $("message-char-count");
  if (contentInput && charCount) {
    contentInput.addEventListener("input", () => {
      charCount.textContent = contentInput.value.length;
    });
  }

  try {
    listEl.innerHTML =
      '<p class="text-slate-400 text-center py-10">加载中...</p>';

    const response = await fetch("/api/messages/list", {
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();

    if (!result.success) {
      listEl.innerHTML = `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      return;
    }

    const messages = result.messages || [];

    if (messages.length === 0) {
      listEl.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无留言</p>';
      return;
    }
    const canDeleteAny = await checkAdminPermission("delete_any_messages");
    const canDeleteOwn = await checkAdminPermission("delete_own_messages");
    const currentUsername = currentAuthUsername;

    const html = messages
      .map((msg) => {
        const isOwnMessage =
          !msg.is_guest && msg.auth_username === currentUsername;
        const canDelete = canDeleteAny || (canDeleteOwn && isOwnMessage);
        const displayName =
          msg.nickname || msg.username || msg.auth_username || "匿名";
        const date = new Date(msg.timestamp * 1000);
        const dateStr = date.toLocaleString("zh-CN");
        const rawAvatarUrl = msg.avatar_url || "default_avatar.png";
        const ipCity = msg.ip_city || "";

        let finalAvatarSrc;
        if (rawAvatarUrl.startsWith("/api/avatar/")) {
          finalAvatarSrc = rawAvatarUrl;
        } else {
          finalAvatarSrc = `/api/avatar/${rawAvatarUrl}`;
        }
        if (typeof sessionUUID !== "undefined" && sessionUUID) {
          // 检查URL是否已有查询参数
          if (finalAvatarSrc.includes("?")) {
            finalAvatarSrc += `&session_id=${sessionUUID}`;
          } else {
            finalAvatarSrc += `?session_id=${sessionUUID}`;
          }
        }

        return `
            <div class="bg-white border border-slate-200 rounded-lg p-4 space-y-2">
              <div class="flex justify-between items-start gap-3">
                <!-- 左侧：头像和用户信息 -->
                <div class="flex gap-3 flex-1">
                  <!-- 用户头像 -->
                  <div class="flex-shrink-0 w-12 h-12 rounded-full bg-slate-200 overflow-hidden border-2 border-slate-300">
                    <img src="${finalAvatarSrc}" alt="头像" class="w-full h-full object-cover"
                      onerror="const p = this.parentElement; p.innerHTML='<span class=\\'text-2xl text-slate-400\\'>👤</span>'; p.classList.add('flex', 'items-center', 'justify-center');">
                  </div>
                  <!-- 用户信息 -->
                  <div class="flex-1">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="font-semibold text-slate-700">${escapeHtml(
                        displayName,
                      )}</span>
                      ${
                        msg.is_guest
                          ? '<span class="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">游客</span>'
                          : ""
                      }
                      ${
                        ipCity
                          ? `<span class="text-xs text-slate-500">来自 ${escapeHtml(
                              ipCity,
                            )}</span>`
                          : ""
                      }
                    </div>
                    ${
                      msg.email
                        ? `<p class="text-xs text-slate-500">${escapeHtml(
                            msg.email,
                          )}</p>`
                        : ""
                    }
                    <p class="text-xs text-slate-400">${dateStr}</p>
                  </div>
                </div>
                <!-- 右侧：删除按钮 -->
                ${
                  canDelete
                    ? `
                  <button class="btn btn-ghost !py-1 !px-2 !text-red-600 text-xs" 
                    onclick="deleteMessage(${escapeInlineJsArg(msg.id)})">删除</button>
                `
                    : ""
                }
              </div>
              <!-- 留言内容 (支持 Markdown 渲染) -->
              <!-- <div id="message-md-${
                msg.id
              }" class="text-slate-700 break-words pl-15 message-markdown">${escapeHtml(
                // 放一个占位，实际HTML由后续脚本替换
                msg.content,
              )}</div> -->
              <div id="message-md-${
                msg.id
              }" class="text-slate-700 break-words pl-15 message-markdown" style="padding-top: 0px;margin-top: 0px;"></div>
            </div>
          `;
      })
      .join("");
    listEl.innerHTML = html;
    // 尝试将每条留言的 Markdown 转换为 HTML
    (function renderMessagesMarkdown(msgs) {
      if (!msgs || !msgs.length) return;
      msgs.forEach((m) => {
        const id = `message-md-${m.id}`;
        const container = document.getElementById(id);
        if (!container) return;
        const markdownText = normalizeMarkdownText(m.content);

        // 优先使用 editormd.markdownToHTML（如果已加载 editormd）
        if (window.editormd && typeof editormd.markdownToHTML === "function") {
          try {
            container.innerHTML =
              '<link rel="stylesheet" href="/editor.md/css/editormd.css" /> <link rel="stylesheet" href="/editor.md/css/editormd.preview.css" />';
            // editormd.markdownToHTML 会替换指定容器内容
            // 我们传入 markdown 字符串并禁止 htmlDecode 以防注入
            editormd.markdownToHTML(id, {
              markdown: markdownText,
              htmlDecode: true, // 开启 HTML 标签解析，为了安全性，默认不开启
              // htmlDecode: "style,iframe,image,div,p,br,hr,strong,em,span,blockquote,q,cite,code,pre",  // 允许解析的 HTML 标签
              htmlDecode: "style,iframe,image",
              toc: false, // 是否生成目录
              tocContainer: "", // 自定义 ToC 容器层
              gfm: true, // 是否使用 GitHub Flavored Markdown
              tocDropdown: false, // 是否启用目录下拉菜单
              markdownSourceCode: false, // 是否保留 Markdown 源码，即是否删除保存源码的 Textarea 标签
              emoji: true,
              taskList: true,
              tex: true, // 默认不解析
              flowChart: false, // 默认不解析
              sequenceDiagram: true, // 默认不解析
            });
            return;
          } catch (e) {
            console.warn("marked 渲染失败，回退为纯文本显示", e);
          }
        }

        // 最后回退：以转义文本并保留换行展示
        container.innerHTML = escapeHtml(markdownText).replace(
          /\n/g,
          "<br>",
        );
      });
    })(messages);
  } catch (e) {
    logMessage_Error("加载留言失败:", e);
    listEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

async function postMessage() {
  // ============================================================
  // IP封禁检查：发表留言功能
  // ============================================================
  const isBanned = await checkIPBanAndProceed("messages_only");
  if (isBanned) {
    // showModalAlert("您的IP已被限制访问留言功能", "访问被拒绝");
    Swal.fire({
      title: "访问被拒绝",
      text: "您的IP已被限制访问留言功能",
      icon: "error",
    });
    return;
  }

  const contentInput = $("message-editor");
  const nicknameInput = $("message-nickname");
  const emailInput = $("message-email");
  const postBtn = $("post-message-btn");

  if (!contentInput || !postBtn) return;

  const content = messageEditor.getMarkdown().trim();
  console.log("留言内容:", content);
  const nickname = nicknameInput ? nicknameInput.value.trim() : "";
  const email = emailInput ? emailInput.value.trim() : "";

  if (!content) {
    // showModalAlert("请输入留言内容", "提示");
    Swal.fire({
      title: "提示",
      text: "请输入留言内容",
      icon: "warning",
    });
    return;
  }

  const isGuest = currentUserData?.is_guest;

  if (isGuest) {
    if (!nickname) {
      // showModalAlert("游客必须填写昵称", "提示");
      Swal.fire({
        title: "提示",
        text: "游客必须填写昵称",
        icon: "warning",
      });
      return;
    }
    if (!email) {
      // showModalAlert("游客必须填写邮箱", "提示");
      Swal.fire({
        title: "提示",
        text: "游客必须填写邮箱",
        icon: "warning",
      });
      return;
    }
  }

  try {
    postBtn.disabled = true;
    postBtn.textContent = "发表中...";

    const response = await fetch("/api/messages/post", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        content: content,
        nickname: nickname,
        email: email,
      }),
    });

    const result = await response.json();

    if (result.success) {
      try {
        if (
          typeof messageEditor !== "undefined" &&
          messageEditor &&
          typeof messageEditor.clear === "function"
        ) {
          messageEditor.clear();
        } else if (contentInput) {
          contentInput.value = "";
        }
        // 兼容性：确保可能存在的 textarea 值也被清空
        try {
          const ta =
            document.querySelector(
              "#message-editor textarea.editormd-markdown-textarea",
            ) || document.querySelector('textarea[name="message-content"]');
          if (ta) ta.value = "";
        } catch (e) {}
      } catch (e) {
        console.warn("清空留言编辑器失败:", e);
      }

      if (nicknameInput) nicknameInput.value = "";
      if (emailInput) emailInput.value = "";
      const charCount = $("message-char-count");
      if (charCount) charCount.textContent = "0";

      // showModalAlert("留言发表成功", "成功");
      Swal.fire({
        title: "成功",
        text: "留言发表成功",
        icon: "success",
      });
      await loadMessages();
    } else {
      // showModalAlert(result.message || "发表留言失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "发表留言失败",
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("发表留言失败:", e);
    // showModalAlert("发表留言失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "发表留言失败: " + e.message,
      icon: "error",
    });
  } finally {
    postBtn.disabled = false;
    postBtn.textContent = "发表留言";
  }
}

async function deleteMessage(messageId) {
  const confirmed = await jsShowConfirm("确认删除", "确定要删除这条留言吗？");
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch("/api/messages/delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        message_id: messageId,
      }),
    });

    const result = await response.json();

    if (result.success) {
      // showModalAlert("留言已删除", "成功");
      Swal.fire({
        title: "成功",
        text: "留言已删除",
        icon: "success",
      });
      await loadMessages();

      // 增加延时确保PC端列表DOM渲染完成后再同步到移动端
      setTimeout(() => {
        // // 1. 同步多账号管理面板 (增加安全检查)
        // const multiModal = document.getElementById(
        //   "mobile-multi-admin-panel-modal"
        // );
        // if (multiModal && !multiModal.classList.contains("hidden")) {
        //   if (typeof copyAdminContentToMultiPanel === "function") {
        //     copyAdminContentToMultiPanel("messages");
        //   }
        // }

        // 2. 同步单账号管理面板 (增加安全检查)
        const singleModal = document.getElementById("mobile-admin-panel-modal");
        if (singleModal && !singleModal.classList.contains("hidden")) {
          if (typeof copyAdminContentToPanelVersion === "function") {
            copyAdminContentToPanelVersion("messages");
          }
        }
      }, 100); // 给予100ms缓冲时间
    } else {
      // showModalAlert(result.message || "删除留言失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "删除留言失败",
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("删除留言失败:", e);
    // showModalAlert("删除留言失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "删除留言失败: " + e.message,
      icon: "error",
    });
  }
}

// =============用户日志查看功能================
function showUserLogs(username) {
  $("user-logs-secondary-modal").classList.remove("hidden");
  const usernameDisplay = $("current-log-username-secondary");
  if (usernameDisplay) usernameDisplay.textContent = username;
  const loginTab = $("log-tab-login-secondary");
  const auditTab = $("log-tab-audit-secondary");
  const loginContent = $("log-login-content-secondary");
  const auditContent = $("log-audit-content-secondary");

  if (loginTab) {
    loginTab.classList.add("text-sky-600", "border-sky-600");
    loginTab.classList.remove("text-slate-400", "border-transparent");
  }
  if (auditTab) {
    auditTab.classList.add("text-slate-400", "border-transparent");
    auditTab.classList.remove("text-sky-600", "border-sky-600");
  }
  if (loginContent) loginContent.classList.remove("hidden");
  if (auditContent) auditContent.classList.add("hidden");
  loadUserLoginLogsSecondary(username);
}

function closeUserLogsSecondaryModal() {
  $("user-logs-secondary-modal").classList.add("hidden");
}

function switchUserLogTab(tab) {
  const loginTab = $("log-tab-login-secondary");
  const auditTab = $("log-tab-audit-secondary");
  const loginContent = $("log-login-content-secondary");
  const auditContent = $("log-audit-content-secondary");
  const username = $("current-log-username-secondary").textContent;

  if (tab === "login") {
    loginTab.classList.add("text-sky-600", "border-sky-600");
    loginTab.classList.remove("text-slate-400", "border-transparent");
    auditTab.classList.add("text-slate-400", "border-transparent");
    auditTab.classList.remove("text-sky-600", "border-sky-600");
    loginContent.classList.remove("hidden");
    auditContent.classList.add("hidden");
    loadUserLoginLogsSecondary(username);
  } else if (tab === "audit") {
    auditTab.classList.add("text-sky-600", "border-sky-600");
    auditTab.classList.remove("text-slate-400", "border-transparent");
    loginTab.classList.add("text-slate-400", "border-transparent");
    loginTab.classList.remove("text-sky-600", "border-sky-600");
    auditContent.classList.remove("hidden");
    loginContent.classList.add("hidden");
    loadUserAuditLogsSecondary(username);
  }
}
function getLoginStatusBadge(log) {
  if (log.success) {
    if (log.reason === "guest_login") {
      return '<span class="text-xs px-2 py-1 rounded bg-blue-100 text-blue-600">游客登录</span>';
    }
    return '<span class="text-xs px-2 py-1 rounded bg-green-100 text-green-600">登录成功</span>';
  }
  let reasonText = "登录失败";
  let reasonClass = "bg-red-100 text-red-700";

  switch (log.reason) {
    case "brute_force_locked":
      reasonText = "尝试过多";
      break;
    case "user_not_found":
      reasonText = "用户不存在";
      break;
    case "user_banned":
      reasonText = "账号已封禁";
      break;
    case "wrong_password":
      reasonText = "密码错误";
      break;
    case "2fa_failed":
      reasonText = "2FA验证失败";
      reasonClass = "bg-orange-100 text-orange-700";
      break;
  }
  return `<span class="text-xs px-2 py-1 rounded ${reasonClass}">${reasonText}</span>`;
}
async function loadUserLoginLogsSecondary(username) {
  const content = $("log-login-content-secondary");
  if (!content) return;
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch(
      `/api/admin/logs/login_history?username=${encodeURIComponent(username)}`,
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );

    const data = await response.json();

    if (data.success && data.logs && data.logs.length > 0) {
      content.innerHTML = data.logs
        .map(
          (log) => `
            <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div class="flex justify-between items-start">
                <div class="flex-1">
                  <p class="text-sm font-semibold text-slate-700">
                    登录时间: ${(log.datetime || "N/A").replace("T", " ")}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    IP地址: ${log.ip_address || "N/A"}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    设备信息: ${log.user_agent || "N/A"}
                  </p>
                  ${
                    log.location
                      ? `<p class="text-sm text-slate-600 mt-1">位置: ${log.location}</p>`
                      : ""
                  }
                </div>
                <div class="flex-shrink-0">
                  ${getLoginStatusBadge(log)}
                </div>
              </div>
            </div>
          `,
        )
        .join("");
    } else {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无登录记录</p>';
    }
  } catch (e) {
    content.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

async function loadUserAuditLogsSecondary(username) {
  const content = $("log-audit-content-secondary");
  if (!content) return;
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch(
      `/api/admin/logs/audit?username=${encodeURIComponent(username)}`,
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );

    const data = await response.json();

    if (data.success && data.logs && data.logs.length > 0) {
      content.innerHTML = data.logs
        .slice()
        .reverse()
        .map(
          (log) => `
            <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div class="flex justify-between items-start">
                <div class="flex-1">
                  <p class="text-sm font-semibold text-slate-700">
                    时间: ${(log.datetime || "N/A").replace("T", " ")}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    操作类型: ${log.action || "N/A"}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    详情: ${log.details || "N/A"}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    IP地址: ${log.ip_address || "N/A"}
                  </p>
                </div>
              </div>
            </div>
          `,
        )
        .join("");
    } else {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无操作记录</p>';
    }
  } catch (e) {
    content.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}
async function loadUserLoginLogs(username) {
  const content = $("log-login-content");
  if (!content) return;
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch(
      `/api/admin/logs/login_history?username=${encodeURIComponent(username)}`,
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );

    const data = await response.json();

    if (data.success && data.logs && data.logs.length > 0) {
      content.innerHTML = data.logs
        .map(
          (log) => `
            <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div class="flex justify-between items-start">
                <div class="flex-1">
                  <p class="text-sm font-semibold text-slate-700">
                    登录时间: ${(log.datetime || "N/A").replace("T", " ")}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    IP地址: ${log.ip_address || "N/A"}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    设备信息: ${log.user_agent || "N/A"}
                  </p>
                  ${
                    log.location
                      ? `<p class="text-sm text-slate-600 mt-1">位置: ${log.location}</p>`
                      : ""
                  }
                </div>
                <div class="flex-shrink-0">
                  ${getLoginStatusBadge(log)}
                </div>
              </div>
            </div>
          `,
        )
        .join("");
    } else {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无登录记录</p>';
    }
  } catch (e) {
    logMessage_Error("加载登录记录失败:", e);
    content.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}
async function loadUserAuditLogs(username) {
  const content = $("log-audit-content");
  if (!content) return;
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch(
      `/api/admin/logs/audit?username=${encodeURIComponent(username)}`,
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );

    const data = await response.json();

    if (data.success && data.logs && data.logs.length > 0) {
      content.innerHTML = data.logs
        .slice()
        .reverse()
        .map(
          (log) => `
            <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <div class="flex justify-between items-start">
                <div class="flex-1">
                  <p class="text-sm font-semibold text-slate-700">
                    ${(log.datetime || "N/A").replace("T", " ")}
                  </p>
                  <p class="text-sm text-slate-600 mt-1">
                    操作: ${log.action || "N/A"}
                  </p>
                  ${
                    log.details
                      ? `<p class="text-sm text-slate-500 mt-1">${log.details}</p>`
                      : ""
                  }
                  ${
                    log.ip_address
                      ? `<p class="text-xs text-slate-400 mt-1">IP: ${log.ip_address}</p>`
                      : ""
                  }
                </div>
          `,
        )
        .join("");
    } else {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无操作记录</p>';
    }
  } catch (e) {
    logMessage_Error("加载操作记录失败:", e);
    content.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}
function closeUserLogsModal() {
  const logsModal = $("admin-user-logs-modal");
  if (logsModal) logsModal.classList.add("hidden");
  const usersPanel = $("admin-users-panel_modal");
  if (usersPanel) usersPanel.classList.remove("hidden");
}

// =======IP封禁管理函数==========
async function loadIPBans() {
  try {
    const response = await fetch("/api/admin/ip_bans", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    const listEl = $("ip-ban-list");
    if (result.success && result.bans && result.bans.length > 0) {
      listEl.innerHTML = result.bans
        .map(
          (ban) => `
            <div class="border p-2 rounded flex justify-between items-center">
              <div>
                <span class="font-semibold">${escapeHtml(ban.target)}</span>
                <span class="text-xs text-slate-500 ml-2">[${ban.type}]</span>
                <span class="text-xs text-slate-500 ml-2">${
                  ban.scope === "all" ? "全部" : "仅留言板"
                }</span>
              </div>
              <button onclick="removeIPBan('${
                ban.id
              }')" class="btn btn-danger !py-1 !px-2 !text-xs min-h-[44px]">删除</button>
            </div>
          `,
        )
        .join("");
    } else {
      listEl.innerHTML = '<p class="text-center py-4">暂无封禁规则</p>';
    }
  } catch (e) {
    // showModalAlert("加载失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "加载失败: " + e.message,
    });
  }
}
// ====================
// IP封禁管理函数
// ====================
const ipRegex =
  /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;

function ipToInt(ip) {
  try {
    return (
      ip
        .split(".")
        .reduce((int, octet) => (int << 8) + parseInt(octet, 10), 0) >>> 0
    );
  } catch (e) {
    return 0;
  }
}
// ============================================================
// IP封禁模态框验证逻辑
// ============================================================
function validateIPBanTarget() {
  const banTypeSelect = $("ban-type");
  const banTargetInput = $("ban-target");
  const banTargetError = $("ban-target-error");

  if (!banTypeSelect || !banTargetInput || !banTargetError) {
    logMessage_Error("validateIPBanTarget: 无法找到IP封禁模态框的DOM元素");
    return false;
  }

  const type = banTypeSelect.value;
  const target = banTargetInput.value.trim();

  if (!target) {
    banTargetError.textContent = "封禁目标不能为空";
    banTargetError.classList.remove("hidden");
    banTargetInput.classList.add("border-red-500");
    return false;
  }

  if (type === "ip" && !ipRegex.test(target)) {
    banTargetError.textContent =
      "格式错误，请输入有效的单个IP地址 (例如: 1.2.3.4)";
    banTargetError.classList.remove("hidden");
    banTargetInput.classList.add("border-red-500");
    return false;
  }

  if (type === "range") {
    const parts = target.split("-");
    if (
      parts.length !== 2 ||
      !ipRegex.test(parts[0].trim()) ||
      !ipRegex.test(parts[1].trim())
    ) {
      banTargetError.textContent =
        "格式错误，请输入有效的IP范围 (例如: 192.168.1.1-192.168.1.100)";
      banTargetError.classList.remove("hidden");
      banTargetInput.classList.add("border-red-500");
      return false;
    }
    const startIpInt = ipToInt(parts[0].trim());
    const endIpInt = ipToInt(parts[1].trim());
    if (startIpInt > endIpInt) {
      banTargetError.textContent = "格式错误：起始IP必须小于或等于结束IP";
      banTargetError.classList.remove("hidden");
      banTargetInput.classList.add("border-red-500");
      return false;
    }
  }

  banTargetError.classList.add("hidden");
  banTargetInput.classList.remove("border-red-500");
  return true;
}

async function addIPBan() {
  if (!validateIPBanTarget()) {
    // showModalAlert("输入格式不正确，请检查红色提示", "添加失败");
    Swal.fire({
      title: "添加失败",
      text: "输入格式不正确，请检查红色提示",
      icon: "error",
    });
    return;
  }
  const target = $("ban-target").value.trim();
  const type = $("ban-type").value;
  const scope = $("ban-scope").value;

  try {
    const response = await fetch("/api/admin/ip_bans", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ target, type, scope }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert("封禁规则已添加");
      // 清空输入框
      Swal.fire({
        title: "成功",
        text: "封禁规则已添加",
        icon: "success",
      });
      $("ban-target").value = "";

      const banTargetError = $("ban-target-error");
      const banTargetInput = $("ban-target");

      if (banTargetError) banTargetError.classList.add("hidden");

      banTargetError.classList.add("hidden");
      banTargetInput.classList.remove("border-red-500");
      loadIPBans();
    } else {
      // showModalAlert(result.message || "添加失败");
      Swal.fire({
        title: "错误",
        text: result.message || "添加失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function removeIPBan(banId) {
  const confirmed = await jsShowConfirm("确认删除", "确定要删除此封禁规则吗？");
  if (!confirmed) return;

  try {
    const response = await fetch(`/api/admin/ip_bans/${banId}`, {
      method: "DELETE",
      headers: { "X-Session-ID": sessionUUID },
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert("封禁规则已删除");
      Swal.fire({
        title: "成功",
        text: "封禁规则已删除",
        icon: "success",
      });
      // 刷新PC端列表
      loadIPBans();
      // 【修复】同时刷新移动端IP封禁列表
      mobileRefreshIPBanList();
    } else {
      // showModalAlert(result.message || "删除失败");
      Swal.fire({
        title: "错误",
        text: result.message || "删除失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

// ====================
// 短信服务配置函数
// ====================
function normalizeSmsSignature(signature) {
  const normalizedSignature = String(signature || "").trim();
  if (!normalizedSignature) {
    return "";
  }

  let unwrappedSignature = normalizedSignature;
  while (
    unwrappedSignature.startsWith("【") &&
    unwrappedSignature.endsWith("】") &&
    unwrappedSignature.length >= 2
  ) {
    unwrappedSignature = unwrappedSignature.slice(1, -1).trim();
  }

  return unwrappedSignature ? `【${unwrappedSignature}】` : "";
}

function getSmsSignatureInnerValue(signature) {
  const normalizedSignature = normalizeSmsSignature(signature);
  if (!normalizedSignature) {
    return "";
  }

  return normalizedSignature.slice(1, -1);
}

function stripSmsSignatureFixedBrackets(value) {
  return String(value || "").replace(/[【】]/g, "");
}

function sanitizeSmsSignatureInputValue(input) {
  if (!input) {
    return;
  }

  const sanitizedValue = stripSmsSignatureFixedBrackets(input.value);
  if (input.value !== sanitizedValue) {
    input.value = sanitizedValue;
  }
}

function bindSmsSignatureInputSanitization(input) {
  if (!input) {
    return;
  }

  if (input.dataset.smsSignatureSanitizationBound === "true") {
    sanitizeSmsSignatureInputValue(input);
    return;
  }

  input.addEventListener("input", () => {
    sanitizeSmsSignatureInputValue(input);
  });
  input.dataset.smsSignatureSanitizationBound = "true";
  sanitizeSmsSignatureInputValue(input);
}

async function loadSMSConfig() {
  configLoadState.sms = false;
  try {
    const response = await fetch("/api/admin/sms/config", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();
    if (result.success) {
      $("sms-enabled").checked = result.config.enable_sms_service || false;
      $("sms-enable-phone-modification").checked =
        result.config.enable_phone_modification || false;
      $("sms-enable-phone-login").checked =
        result.config.enable_phone_login || false;
      $("sms-enable-phone-registration-verify").checked =
        result.config.enable_phone_registration_verify || false;
      $("sms-username").value = result.config.username || "";
      $("sms-apikey").value = result.config.api_key || "";
      $("sms-signature").value = getSmsSignatureInnerValue(result.config.signature || "");
      bindSmsSignatureInputSanitization($("sms-signature"));
      $("sms-template").value = result.config.template_register || "";
      $("sms-code-expire").value = result.config.code_expire_minutes || 5;
      $("sms-limit-account").value =
        result.config.rate_limit_per_account_day || 10;
      $("sms-limit-ip").value = result.config.rate_limit_per_ip_day || 20;
      $("sms-limit-phone").value = result.config.rate_limit_per_phone_day || 5;
      $("sms-webhook-url").value =
        `${window.location.origin}/sms-reply-webhook`;
      configLoadState.sms = true;
    } else {
      configLoadState.sms = false;
      Swal.fire({
        title: "错误",
        text: result.message || "加载配置失败",
        icon: "error",
      });
    }
  } catch (e) {
    configLoadState.sms = false;
    // showModalAlert("加载配置失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "加载配置失败: " + e.message,
      icon: "error",
    });
  }
}
async function saveSMSConfig() {
  if (!ensureConfigLoaded("sms", "短信服务")) {
    return;
  }
  const config = {
    enable_sms_service: $("sms-enabled").checked,
    enable_phone_modification: $("sms-enable-phone-modification").checked,
    enable_phone_login: $("sms-enable-phone-login").checked,
    enable_phone_registration_verify: $("sms-enable-phone-registration-verify")
      .checked,
    username: $("sms-username").value.trim(),
    api_key: $("sms-apikey").value.trim(),
    signature: normalizeSmsSignature($("sms-signature").value),
    template_register: $("sms-template").value.trim(),
    code_expire_minutes: parseInt($("sms-code-expire").value) || 5,
    rate_limit_per_account_day: parseInt($("sms-limit-account").value) || 10,
    rate_limit_per_ip_day: parseInt($("sms-limit-ip").value) || 20,
    rate_limit_per_phone_day: parseInt($("sms-limit-phone").value) || 5,
  };

  try {
    const response = await fetch("/api/admin/sms/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(config),
    });
    const result = await response.json();
    if (result.success) {
      // showModalAlert("配置已保存");
      Swal.fire({
        title: "成功",
        text: "配置已保存",
        icon: "success",
      });
    } else {
      // showModalAlert(result.message || "保存失败");
      Swal.fire({
        title: "错误",
        text: result.message || "保存失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}
function handleSmsMainSwitchChange() {
  const mainSwitchEnabled = $("sms-enabled").checked;
  if (!mainSwitchEnabled) {
    $("sms-enable-phone-modification").checked = false;
    $("sms-enable-phone-login").checked = false;
    $("sms-enable-phone-registration-verify").checked = false;
  }
}
async function checkSMSBalance() {
  const btn = $("btn-check-sms-balance");
  const originalText = "💰 查询余额";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "查询中...";
  }

  try {
    const response = await fetch("/api/admin/sms/check_balance", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (result.success) {
      const valEl = $("sms-balance-modal-value");
      const sentEl = $("sms-balance-modal-sent");
      const msgEl = $("sms-balance-modal-message");

      if (valEl) valEl.textContent = result.balance;
      if (sentEl) sentEl.textContent = result.sent_today;
      if (msgEl) {
        msgEl.textContent = result.message;
        if (
          result.message &&
          (result.message.includes("频繁") || result.message.includes("失败"))
        ) {
          msgEl.classList.add("text-amber-600", "bg-amber-50");
          msgEl.classList.remove("text-slate-500", "bg-slate-50");
        } else {
          msgEl.classList.remove("text-amber-600", "bg-amber-50");
          msgEl.classList.add("text-slate-500", "bg-slate-50");
        }
      }

      openSMSBalanceModal();
    } else {
      // showModalAlert(result.message || "查询失败");
      Swal.fire({
        title: "错误",
        text: result.message || "查询失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }
}

function openSMSBalanceModal() {
  showModal("sms-balance-modal");
}

function closeSMSBalanceModal() {
  hideModal("sms-balance-modal");
}

// ==================== 短信发送历史功能 ====================
function openSMSHistoryModal() {
  $("sms-history-modal").classList.remove("hidden");
  loadSMSHistory();
}

function closeSMSHistoryModal() {
  $("sms-history-modal").classList.add("hidden");
}
async function loadSMSHistory() {
  try {
    const dateFilter = $("sms-history-date-filter").value;
    const phoneFilter = $("sms-history-phone-filter").value.trim();

    const params = new URLSearchParams();
    if (dateFilter) params.append("date", dateFilter);
    if (phoneFilter) params.append("phone", phoneFilter);

    const response = await fetch(
      `/api/admin/sms/history?${params.toString()}`,
      {
        headers: { "X-Session-ID": sessionUUID },
      },
    );
    const result = await response.json();

    const listContainer = $("sms-history-list");

    if (result.success && result.records && result.records.length > 0) {
      listContainer.innerHTML = result.records
        .map(
          (record) => `
            <div class="border-2 border-slate-200 rounded-lg p-4 hover:border-sky-300 transition-colors bg-white">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <span class="text-xs text-slate-500">📱 手机号</span>
                  <p class="font-semibold text-slate-700">+86 ${
                    record.phone || "N/A"
                  }<span class="phone-location-badge text-[11px] text-slate-400 ml-1" data-phone="${record.phone || ""}"></span></p>
                </div>
                <div>
                  <span class="text-xs text-slate-500">👤 用户名</span>
                  <p class="font-semibold text-slate-700">${
                    record.username || "未知"
                  }</p>
                </div>
                <div>
                  <span class="text-xs text-slate-500">🕐 时间</span>
                  <p class="text-sm text-slate-600">${
                    record.datetime || "N/A"
                  }</p>
                </div>
                <div>
                  <span class="text-xs text-slate-500">🌐 IP地址</span>
                  <p class="text-sm text-slate-600">${record.ip || "N/A"}</p>
                </div>
                <div class="md:col-span-2">
                  <span class="text-xs text-slate-500">💬 短信内容</span>
                  <p class="text-sm text-slate-600 bg-slate-50 p-2 rounded mt-1">${escapeHtml(
                    record.content || "",
                  )}</p>
                </div>
                ${
                  record.session_id &&
                  record.session_id !== "" &&
                  record.session_id !== "null"
                    ? `
                <div class="md:col-span-2">
                  <span class="text-xs text-slate-500">🔐 会话ID</span>
                  <p class="text-xs text-slate-400 font-mono">${record.session_id}</p>
                </div>
                `
                    : ""
                }
              </div>
            </div>
          `,
        )
        .join("");
      listContainer.querySelectorAll(".phone-location-badge[data-phone]").forEach(async (span) => {
        const info = await fetchPhoneInfo(span.dataset.phone);
        if (info) { const p = [info.province, info.city, info.sp].filter(Boolean); if (p.length) span.textContent = `(${p.join(" ")})`; }
      });
    } else {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无记录</p>';
    }
  } catch (e) {
    // showModalAlert("加载历史记录失败: " + e.message);
    Swal.fire({
      title: "错误",
      text: "加载历史记录失败: " + e.message,
      icon: "error",
    });
  }
}

// ==================== 短信测试发送功能 ====================
function openSMSTestModal() {
  const modal = $("sms-test-modal");
  if (modal) {
    modal.classList.remove("hidden");
    document.body.classList.add("modal-visible");
    const phoneInput = $("sms-test-phone");
    if (phoneInput) {
      phoneInput.value = "";
    }
    const codeInput = $("sms-test-code-input");
    if (codeInput) {
      codeInput.value = "";
    }
    const resultDiv = $("sms-test-result");
    if (resultDiv) {
      resultDiv.classList.add("hidden");
    }
    const sendBtn = $("btn-send-test-sms");
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.innerHTML = `
            <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
            </svg>
            发送测试短信
          `;
    }
  }
}
function closeSMSTestModal() {
  const modal = $("sms-test-modal");
  if (modal) {
    modal.classList.add("hidden");
  }
}

async function sendTestSMS() {
  const phoneInput = $("sms-test-phone");
  const codeInput = $("sms-test-code-input");
  const sendBtn = $("btn-send-test-sms");
  const resultDiv = $("sms-test-result");
  const codeDisplay = $("sms-test-code");
  const phoneDisplay = $("sms-test-phone-display");

  if (!phoneInput || !sendBtn) {
    // showModalAlert("界面元素未找到，请刷新页面重试");
    Swal.fire({
      title: "错误",
      text: "界面元素未找到，请刷新页面重试",
      icon: "error",
    });
    return;
  }

  const phone = phoneInput.value.trim();
  const customCode = codeInput ? codeInput.value.trim() : "";

  if (!phone) {
    // showModalAlert("请输入手机号");
    Swal.fire({
      title: "错误",
      text: "请输入手机号",
      icon: "error",
    });
    phoneInput.focus();
    return;
  }

  if (!/^1[3-9]\d{9}$/.test(phone)) {
    // showModalAlert("手机号格式不正确，请输入11位有效手机号");
    Swal.fire({
      title: "错误",
      text: "手机号格式不正确，请输入11位有效手机号",
      icon: "error",
    });
    phoneInput.focus();
    return;
  }

  if (customCode && !/^\d{4,8}$/.test(customCode)) {
    // showModalAlert("自定义验证码格式不正确，仅支持4-8位数字");
    Swal.fire({
      title: "错误",
      text: "自定义验证码格式不正确，仅支持4-8位数字",
      icon: "error",
    });
    if (codeInput) codeInput.focus();
    return;
  }

  sendBtn.disabled = true;
  sendBtn.innerHTML = `
        <svg class="w-5 h-5 inline mr-1 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        发送中...
      `;

  if (resultDiv) {
    resultDiv.classList.add("hidden");
  }

  try {
    const requestData = { phone };
    if (customCode) {
      requestData.code = customCode;
    }
    const response = await fetch("/api/sms/test_send", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(requestData),
    });

    const result = await response.json();

    if (result.success) {
      if (codeDisplay) {
        codeDisplay.textContent = result.code || "------";
      }
      if (phoneDisplay) {
        phoneDisplay.textContent = result.phone || phone;
      }
      if (resultDiv) {
        resultDiv.classList.remove("hidden");
      }
      // showModalAlert("测试短信发送成功！请检查手机是否收到", "成功");
      Swal.fire({
        title: "成功",
        text: "测试短信发送成功！请检查手机是否收到",
        icon: "success",
      });
      sendBtn.innerHTML = `
            <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M5 13l4 4L19 7"></path>
            </svg>
            已发送
          `;
      setTimeout(() => {
        if (sendBtn) {
          sendBtn.disabled = false;
          sendBtn.innerHTML = `
                <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                </svg>
                再次发送
              `;
        }
      }, 5000);
    } else {
      // showModalAlert(result.message || "发送失败，请检查配置和余额");
      Swal.fire({
        title: "错误",
        text: result.message || "发送失败，请检查配置和余额",
        icon: "error",
      });
      sendBtn.disabled = false;
      sendBtn.innerHTML = `
            <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
            </svg>
            发送测试短信
          `;
    }
  } catch (error) {
    // console.error("[短信测试] 发送失败:", error);
    logMessage_Error("[短信测试] 发送失败:" + error);
    // showModalAlert("网络错误：" + error.message);
    Swal.fire({
      title: "错误",
      text: "网络错误：" + error.message,
      icon: "error",
    });
    sendBtn.disabled = false;
    sendBtn.innerHTML = `
          <svg class="w-5 h-5 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
          </svg>
          发送测试短信
        `;
  }
}

// ====================
// 短信回复记录查看功能
// ====================

/**
 * 打开短信回复记录弹窗（SweetAlert2版本）
 *
 * 功能说明：
 * 这个函数用于查看和展示用户通过短信回复的内容记录。
 * 它会调用后端API获取数据，并使用SweetAlert2弹窗以表格形式美观地展示。
 *
 * 主要功能：
 * 1. 显示加载提示：在获取数据时显示"加载中"的提示
 * 2. 调用后端API：从 /api/sms/reply-logs 获取短信回复记录
 * 3. 权限检查：处理403权限不足的情况
 * 4. 数据展示：将记录以表格形式展示在弹窗中
 * 5. 错误处理：处理网络错误、空数据等各种异常情况
 * 6. XSS防护：使用escapeHtml函数防止跨站脚本攻击
 *
 * 权限要求：
 * - 需要管理员或超级管理员权限（admin 或 super_admin 组）
 * - 后端会自动验证X-Session-ID和用户组别
 *
 * 调用位置：
 * - PC端：index.html 第7199行的按钮
 * - 移动端：index.html 第3729行和第5295行的按钮
 *
 * 技术实现：
 * - 使用async/await处理异步操作
 * - 使用fetch API调用后端接口
 * - 使用SweetAlert2.fire()显示各种状态的弹窗
 * - 使用HTML模板字符串构建表格
 *
 * 错误处理：
 * - 403权限错误：显示权限不足提示
 * - 网络错误：显示网络连接失败提示
 * - 空数据：显示暂无记录提示
 * - API失败：显示具体的错误信息
 *
 * 安全考虑：
 * - 使用sessionUUID进行身份认证
 * - 对所有用户输入内容使用escapeHtml转义，防止XSS攻击
 * - 后端进行严格的权限验证
 *
 * @returns {Promise<void>} 无返回值，通过弹窗展示结果
 * @async
 */
async function openSMSReplyLogsModal() {
  try {
    // ========================================
    // 步骤1：显示加载提示
    // ========================================
    // 使用SweetAlert2显示一个"加载中"的提示弹窗
    // 这个弹窗会阻止用户点击外部区域（allowOutsideClick: false）
    // 不显示确认按钮（showConfirmButton: false）
    // 显示一个旋转的加载动画（Swal.showLoading()）
    Swal.fire({
      title: "加载中...", // 弹窗标题
      text: "正在获取短信回复记录", // 提示文本
      allowOutsideClick: false, // 禁止点击外部关闭弹窗
      showConfirmButton: false, // 不显示确认按钮
      willOpen: () => {
        // 弹窗打开时的回调函数
        // 显示SweetAlert2内置的加载动画（旋转图标）
        Swal.showLoading();
      },
    });

    // ========================================
    // 步骤2：调用后端API获取数据
    // ========================================
    // 使用fetch API向后端发送GET请求
    // API端点：/api/sms/reply-logs
    // 查询参数：limit=50 限制返回最近50条记录
    // 请求头：X-Session-ID 用于身份认证
    const response = await fetch("/api/sms/reply-logs?limit=50", {
      method: "GET", // 使用GET方法
      headers: {
        // 设置请求头，包含会话ID用于身份验证
        // sessionUUID 是全局变量，在用户登录后设置
        "X-Session-ID": sessionUUID,
      },
    });

    // 解析响应的JSON数据
    // result格式：{ success: bool, logs: array, total: int, message: string }
    const result = await response.json();

    // ========================================
    // 步骤3：处理权限不足的情况（HTTP 403）
    // ========================================
    // 检查HTTP状态码是否为403（Forbidden - 禁止访问）
    // 这表示用户没有管理员权限，无法访问此功能
    if (response.status === 403) {
      // 显示权限不足的错误提示
      Swal.fire({
        icon: "error", // 错误图标（红色X）
        title: "权限不足", // 错误标题
        text: result.message || "仅管理员可查看短信回复记录", // 错误信息
        confirmButtonText: "我知道了", // 确认按钮文本
      });
      return; // 提前退出函数，不再继续执行
    }

    // ========================================
    // 步骤4：检查API调用是否成功
    // ========================================
    // 检查返回数据中的success字段
    // 如果为false，表示API调用失败（例如：服务器错误、读取文件失败等）
    if (!result.success) {
      // 显示API返回的错误信息
      Swal.fire({
        icon: "error", // 错误图标
        title: "获取失败", // 错误标题
        text: result.message || "无法获取短信回复记录", // 显示具体错误信息
        confirmButtonText: "确定", // 确认按钮文本
      });
      return; // 提前退出
    }

    // 获取日志数组，如果不存在则使用空数组作为默认值
    // logs是一个数组，每个元素包含：timestamp, datetime, phone, content, ip
    const logs = result.logs || [];

    // ========================================
    // 步骤5：处理空数据的情况
    // ========================================
    // 如果日志数组长度为0，表示还没有任何短信回复记录
    if (logs.length === 0) {
      // 显示提示信息
      Swal.fire({
        icon: "info", // 信息图标（蓝色i）
        title: "暂无记录", // 提示标题
        text: "还没有收到任何短信回复", // 提示内容
        confirmButtonText: "知道了", // 确认按钮文本
      });
      return; // 提前退出
    }

    // ========================================
    // 步骤6：构建HTML表格
    // ========================================
    // 使用模板字符串构建一个HTML表格
    // 表格包含表头（时间、手机号、回复内容、IP地址）和数据行
    let tableHTML = `
            <div class="overflow-x-auto max-h-96">
              <!-- 外层div设置：
                   - overflow-x-auto: 横向溢出时显示滚动条
                   - max-h-96: 最大高度为24rem（384px），超出则显示纵向滚动条
              -->
              <table class="w-full text-left text-sm">
                <!-- 表格样式：
                     - w-full: 宽度100%
                     - text-left: 文本左对齐
                     - text-sm: 小号字体
                -->
                <thead class="bg-slate-100 sticky top-0">
                  <!-- 表头样式：
                       - bg-slate-100: 浅灰色背景
                       - sticky top-0: 固定在顶部，滚动时不动（粘性定位）
                  -->
                  <tr>
                    <th class="px-4 py-2">时间</th>
                    <th class="px-4 py-2">手机号</th>
                    <th class="px-4 py-2">回复内容</th>
                    <th class="px-4 py-2">IP地址</th>
                  </tr>
                </thead>
                <tbody>
          `;

    // ========================================
    // 步骤7：遍历日志数组，为每条记录生成一行表格
    // ========================================
    // 使用forEach循环遍历logs数组中的每个log对象
    logs.forEach((log) => {
      // 为每条记录生成一个<tr>行
      // log对象包含以下字段：
      // - timestamp: Unix时间戳（数字）
      // - datetime: 可读时间字符串（例如："2024-01-01 12:00:00"）
      // - phone: 回复的手机号
      // - content: 短信回复内容
      // - ip: 请求来源IP地址

      tableHTML += `
                <tr class="border-b hover:bg-slate-50">
                  <!-- 表格行样式：
                       - border-b: 底部边框
                       - hover:bg-slate-50: 鼠标悬停时背景变为浅灰色
                  -->
                  <td class="px-4 py-2 whitespace-nowrap">${
                    log.datetime || "未知"
                  }</td>
                  <!-- 时间列：
                       - whitespace-nowrap: 文本不换行
                       - 使用 || '未知' 提供默认值，防止显示undefined
                  -->
                  <td class="px-4 py-2">${log.phone || "未知"}</td>
                  <!-- 手机号列：显示回复的手机号 -->
                  <td class="px-4 py-2">${escapeHtml(log.content || "")}</td>
                  <!-- 回复内容列：
                       - 使用escapeHtml()函数转义HTML特殊字符
                       - 这是关键的安全措施，防止XSS（跨站脚本）攻击
                       - 例如：如果用户回复了 "<script>alert('XSS')</script>"
                         escapeHtml会将其转换为 "&lt;script&gt;alert('XSS')&lt;/script&gt;"
                         这样就只会显示文本，不会执行脚本代码
                  -->
                  <td class="px-4 py-2">${log.ip || "未知"}</td>
                  <!-- IP地址列：显示请求来源IP -->
                </tr>
            `;
    });

    // ========================================
    // 步骤8：完成表格HTML并添加统计信息
    // ========================================
    // 关闭tbody和table标签
    tableHTML += `
                </tbody>
              </table>
            </div>
            <div class="mt-4 text-sm text-slate-600 text-center">
              <!-- 统计信息区域：
                   - mt-4: 顶部外边距（1rem）
                   - text-sm: 小号字体
                   - text-slate-600: 深灰色文本
                   - text-center: 居中对齐
              -->
              共 ${result.total || logs.length} 条记录，显示最近 ${
                logs.length
              } 条
              <!-- 显示总记录数和当前显示数量
                   - result.total: 后端返回的总记录数
                   - logs.length: 当前显示的记录数（受limit参数限制）
              -->
            </div>
          `;

    // ========================================
    // 步骤9：使用SweetAlert2显示最终的表格弹窗
    // ========================================
    // 显示包含表格的弹窗
    Swal.fire({
      title: "短信回复记录", // 弹窗标题
      html: tableHTML, // 弹窗内容（HTML格式）
      width: "800px", // 弹窗宽度，足够宽以容纳表格
      showCloseButton: true, // 显示右上角的关闭按钮（X）
      confirmButtonText: "关闭", // 底部确认按钮的文本
      customClass: {
        // 自定义CSS类，用于更好的样式控制
        container: "sms-reply-logs-modal", // 可用于添加额外的CSS样式
      },
    });
  } catch (error) {
    // ========================================
    // 步骤10：处理所有未预期的错误
    // ========================================
    // catch块捕获try块中的所有错误
    // 常见错误类型：
    // - 网络错误：无法连接到服务器
    // - JSON解析错误：响应不是有效的JSON
    // - 其他JavaScript运行时错误

    // 在控制台输出错误信息，方便开发者调试
    // console.error会在浏览器开发者工具中显示为红色错误
    console.error("获取短信回复记录失败:", error);

    // 显示用户友好的错误提示
    Swal.fire({
      icon: "error", // 错误图标
      title: "网络错误", // 错误标题
      text: "无法连接到服务器，请稍后重试", // 错误信息
      confirmButtonText: "确定", // 确认按钮文本
      footer:
        '<span class="text-xs text-slate-400">如果问题持续存在，请联系技术支持</span>', // 底部附加信息
    });
  }
}

// ==================== 验证码管理功能 ====================
let verificationCodesCountdownInterval = null;

function updateVerificationCodeCountdowns() {
  const countdownElements = document.querySelectorAll(
    ".verification-code-countdown",
  );
  if (countdownElements.length === 0) {
    stopVerificationCodesCountdown();
    return;
  }

  const now = Math.floor(Date.now() / 1000);

  countdownElements.forEach((el) => {
    const expiresAt = parseInt(el.dataset.expiresAt, 10);
    if (isNaN(expiresAt)) {
      el.textContent = "已失效";
      return;
    }

    const expiresIn = Math.max(0, expiresAt - now);
    const minutes = Math.floor(expiresIn / 60);
    const seconds = expiresIn % 60;

    el.textContent = `${minutes}分${seconds}秒`;

    if (expiresIn <= 0) {
      el.textContent = "已失效";
      el.classList.add("text-red-600", "font-semibold");
    } else if (expiresIn < 120) {
      el.classList.add("text-red-600", "font-semibold");
      el.classList.remove("text-slate-600");
    }
  });
}

function startVerificationCodesCountdown() {
  stopVerificationCodesCountdown();
  updateVerificationCodeCountdowns();
  verificationCodesCountdownInterval = setInterval(
    updateVerificationCodeCountdowns,
    1000,
  );
}
function stopVerificationCodesCountdown() {
  if (verificationCodesCountdownInterval) {
    clearInterval(verificationCodesCountdownInterval);
    verificationCodesCountdownInterval = null;
  }
}

let verificationCodesPollingTimer = null;
const VERIFICATION_CODES_POLLING_MS = 30000;
let verificationCodesSocketHealthy = false;

function isVerificationCodesModalOpen() {
  const modal = $("verification-codes-modal");
  return !!modal && !modal.classList.contains("hidden");
}

function isMobileVerificationCodesModalOpen() {
  const modal = document.getElementById("mobile-verification-codes-modal");
  return !!modal && !modal.classList.contains("hidden");
}

function refreshOpenVerificationCodeModals() {
  if (isVerificationCodesModalOpen()) {
    loadVerificationCodes();
  }
  if (isMobileVerificationCodesModalOpen()) {
    loadMobileVerificationCodes();
  }
}

function startVerificationCodesPollingFallback() {
  if (verificationCodesPollingTimer) return;
  verificationCodesPollingTimer = setInterval(() => {
    if (!verificationCodesSocketHealthy) {
      refreshOpenVerificationCodeModals();
    }
  }, VERIFICATION_CODES_POLLING_MS);
}

function stopVerificationCodesPollingFallback() {
  if (!verificationCodesPollingTimer) return;
  clearInterval(verificationCodesPollingTimer);
  verificationCodesPollingTimer = null;
}

function syncVerificationCodesPollingByModalState() {
  if (!isVerificationCodesModalOpen() && !isMobileVerificationCodesModalOpen()) {
    stopVerificationCodesPollingFallback();
    return;
  }
  if (!verificationCodesSocketHealthy) {
    startVerificationCodesPollingFallback();
  }
}

function openVerificationCodesModal() {
  $("verification-codes-modal").classList.remove("hidden");
  loadVerificationCodes();
  syncVerificationCodesPollingByModalState();
}
function closeVerificationCodesModal() {
  $("verification-codes-modal").classList.add("hidden");
  stopVerificationCodesCountdown();
  syncVerificationCodesPollingByModalState();
}
async function loadVerificationCodes() {
  try {
    const response = await fetch("/api/admin/sms/verification_codes", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    const listContainer = $("verification-codes-list");

    if (result.success && result.codes && result.codes.length > 0) {
      listContainer.innerHTML = result.codes
        .map((item) => {
          const expiresIn = Math.max(0, Math.floor(item.expires_in / 60));
          const expiresSec = Math.max(0, item.expires_in % 60);
          return `
            <div class="border-2 border-slate-200 rounded-lg p-4 bg-white hover:border-sky-300 transition-colors">
              <div class="flex items-center justify-between gap-4">
                <div class="flex-1 grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <span class="text-xs text-slate-500">📱 手机号</span>
                    <p class="font-semibold text-slate-700">+86 ${
                      item.phone
                    }<span class="phone-location-badge text-[11px] text-slate-400 ml-1" data-phone="${item.phone || ""}"></span></p>
                  </div>
                  <div>
                    <span class="text-xs text-slate-500">🔢 验证码</span>
                    <p class="font-mono text-lg font-bold text-sky-600">${
                      item.code
                    }</p>
                  </div>
                  <div>
                    <span class="text-xs text-slate-500">⏰ 剩余时间</span>
                    <p class="verification-code-countdown text-sm ${
                      expiresIn < 2
                        ? "text-red-600 font-semibold"
                        : "text-slate-600"
                    }"
                       data-expires-at="${item.expires_at}">
                      ${expiresIn}分${expiresSec}秒
                    </p>
                  </div>
                </div>
                <button onclick="invalidateVerificationCode(${escapeInlineJsArg(item.phone)})"
                  class="btn btn-ghost border border-red-300 text-red-600 hover:bg-red-50 whitespace-nowrap">
                  ❌ 失效
                </button>
              </div>
            </div>
          `;
        })
        .join("");
      listContainer
        .querySelectorAll(".phone-location-badge[data-phone]")
        .forEach(async (span) => {
          const info = await fetchPhoneInfo(span.dataset.phone);
          if (info) {
            const p = [info.province, info.city, info.sp].filter(Boolean);
            if (p.length) span.textContent = `(${p.join(" ")})`;
          }
        });
    } else {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10">当前没有有效的验证码</p>';
    }

    startVerificationCodesCountdown();
  } catch (e) {
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "加载验证码列表失败: " + e.message,
      icon: "error",
    });
    stopVerificationCodesCountdown();
  }
}
async function invalidateVerificationCode(phone) {
  const confirmed = await jsShowConfirm(
    "确认失效",
    `确定要使手机号 +86 ${phone} 的验证码失效吗？`,
  );
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch("/api/admin/sms/invalidate_code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ phone: phone }),
    });
    const result = await response.json();

    if (result.success) {
      fireVerificationCodesModalSwal({
        title: "成功",
        text: "验证码已失效",
        icon: "success",
      });
      loadVerificationCodes();
    } else {
      fireVerificationCodesModalSwal({
        title: "错误",
        text: result.message || "操作失败",
        icon: "error",
      });
    }
  } catch (e) {
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}
function fireVerificationCodesModalSwal(options = {}) {
  const originalDidOpen = options.didOpen;
  return Swal.fire({
    target: document.body,
    ...options,
    didOpen: (popup) => {
      const swalContainer =
        popup?.closest(".swal2-container") ||
        popup?.parentElement ||
        Swal.getContainer();
      if (swalContainer) {
        swalContainer.style.zIndex = "2147483647";
        swalContainer.style.position = "fixed";
        swalContainer.style.inset = "0";
      }
      if (popup) {
        popup.style.zIndex = "2147483647";
      }
      if (typeof originalDidOpen === "function") {
        originalDidOpen(popup);
      }
    },
  });
}

async function addManualVerificationCode() {
  const phone = $("manual-code-phone").value.trim();
  let code = $("manual-code-value").value.trim();
  if (!code) {
    code = Math.floor(100000 + Math.random() * 900000).toString();
    $("manual-code-value").value = code;
  } else if (!/^\d{6}$/.test(code)) {
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "验证码必须是6位数字",
      icon: "error",
    });
    return;
  }
  if (!code || !/^\d{6}$/.test(code)) {
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "请输入6位数字验证码",
      icon: "error",
    });
    return;
  }

  try {
    const response = await fetch("/api/admin/sms/add_manual_code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        phone: phone,
        code: code,
      }),
    });
    const result = await response.json();

    if (result.success) {
      fireVerificationCodesModalSwal({
        title: "成功",
        text: "验证码已添加",
        icon: "success",
      });
      $("manual-code-phone").value = "";
      $("manual-code-value").value = "";
      loadVerificationCodes();
    } else {
      fireVerificationCodesModalSwal({
        title: "错误",
        text: result.message || "添加失败",
        icon: "error",
      });
    }
  } catch (e) {
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

// ==================== 移动端验证码管理功能 ====================
// 移动端验证码管理倒计时定时器引用，用于在关闭模态框时清理
let mobileVerificationCodesCountdownInterval = null;

/**
 * 更新移动端验证码倒计时显示
 * 此函数会遍历所有带有 .mobile-verification-code-countdown 类的元素，
 * 并根据其 data-expires-at 属性计算并显示剩余时间
 */
function updateMobileVerificationCodeCountdowns() {
  // 获取所有移动端验证码倒计时元素
  const countdownElements = document.querySelectorAll(
    ".mobile-verification-code-countdown",
  );
  // 如果没有任何倒计时元素，停止定时器以节省资源
  if (countdownElements.length === 0) {
    stopMobileVerificationCodesCountdown();
    return;
  }

  // 获取当前的Unix时间戳（秒）
  const now = Math.floor(Date.now() / 1000);

  // 遍历每个倒计时元素并更新显示
  countdownElements.forEach((el) => {
    // 从 data-expires-at 属性获取过期时间戳
    const expiresAt = parseInt(el.dataset.expiresAt, 10);
    // 检查过期时间戳是否有效
    if (isNaN(expiresAt)) {
      el.textContent = "已失效";
      return;
    }

    // 计算剩余时间（秒），确保不为负数
    const expiresIn = Math.max(0, expiresAt - now);
    // 将秒数转换为分钟和秒
    const minutes = Math.floor(expiresIn / 60);
    const seconds = expiresIn % 60;

    // 更新显示文本
    el.textContent = `${minutes}分${seconds}秒`;

    // 根据剩余时间调整样式
    if (expiresIn <= 0) {
      // 已过期：显示红色并加粗
      el.textContent = "已失效";
      el.classList.add("text-red-600", "font-semibold");
    } else if (expiresIn < 120) {
      // 剩余时间少于2分钟：显示红色警告
      el.classList.add("text-red-600", "font-semibold");
      el.classList.remove("text-slate-600");
    }
  });
}

/**
 * 启动移动端验证码倒计时
 * 首次更新并设置每秒更新一次的定时器
 */
function startMobileVerificationCodesCountdown() {
  // 先停止任何已存在的定时器，避免重复
  stopMobileVerificationCodesCountdown();
  // 立即执行一次更新
  updateMobileVerificationCodeCountdowns();
  // 设置每秒更新一次的定时器
  mobileVerificationCodesCountdownInterval = setInterval(
    updateMobileVerificationCodeCountdowns,
    1000,
  );
}

/**
 * 停止移动端验证码倒计时
 * 清理定时器资源
 */
function stopMobileVerificationCodesCountdown() {
  if (mobileVerificationCodesCountdownInterval) {
    clearInterval(mobileVerificationCodesCountdownInterval);
    mobileVerificationCodesCountdownInterval = null;
  }
}

/**
 * 打开移动端验证码管理模态框
 * 如果模态框不存在，则动态创建；然后显示模态框并加载验证码列表
 */
function openMobileVerificationCodesModal() {
  // 尝试获取已存在的移动端验证码模态框
  let modal = document.getElementById("mobile-verification-codes-modal");
  // 如果模态框不存在，则动态创建
  if (!modal) {
    // 创建模态框容器元素
    modal = document.createElement("div");
    modal.id = "mobile-verification-codes-modal";
    // 设置移动端模态框的基本样式类
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    // 点击背景区域时关闭模态框
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileVerificationCodesModal();
    };
    // 设置模态框的HTML内容
    modal.innerHTML = `
            <!-- 半透明黑色背景遮罩 -->
            <div class="absolute inset-0 bg-black/40" onclick="closeMobileVerificationCodesModal()"></div>
            <!-- 模态框内容区域，底部弹出样式 -->
            <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
              <!-- 拖拽手柄，符合移动端设计规范 -->
              <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileVerificationCodesModal()">
                <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
              </div>
              <!-- 模态框标题区域 -->
              <div class="flex items-center justify-between pb-3 border-b border-slate-200">
                <h3 class="text-xl font-bold text-sky-600">🔑 验证码管理</h3>
                <!-- 关闭按钮 -->
                <button onclick="closeMobileVerificationCodesModal()" class="text-slate-400 hover:text-slate-600 text-2xl leading-none">&times;</button>
              </div>

              <!-- 手动添加验证码区域 -->
              <div class="bg-green-50 border border-green-200 rounded-xl p-4 space-y-3">
                <h5 class="font-semibold text-green-900 text-sm">➕ 手动添加验证码</h5>
                <!-- 手机号输入框 -->
                <div class="phone-input-wrapper">
                  <span class="phone-prefix">+86 </span>
                  <input type="tel" id="mobile-manual-code-phone" class="input-field text-sm" placeholder="手机号" pattern="[0-9]*" maxlength="11">
                </div>
                <!-- 验证码输入框 -->
                <input type="text" id="mobile-manual-code-value" class="input-field text-sm w-full" placeholder="验证码（6位数字，留空自动生成）" maxlength="6" pattern="[0-9]{6}">
                <!-- 添加按钮 -->
                <button onclick="addMobileManualVerificationCode()" class="btn btn-primary w-full !py-2 text-sm min-h-[44px]">添加验证码</button>
                <p class="text-xs text-slate-600">💡 此功能用于测试或紧急情况下手动添加验证码，不会实际发送短信</p>
              </div>

              <!-- 刷新按钮 -->
              <div class="flex justify-end">
                <button onclick="loadMobileVerificationCodes()" class="btn btn-ghost text-sm">🔄 刷新列表</button>
              </div>

              <!-- 验证码列表容器 -->
              <div id="mobile-verification-codes-list" class="space-y-3 max-h-[40vh] overflow-y-auto">
                <p class="text-slate-400 text-center py-10 text-sm">加载中...</p>
              </div>

              <!-- 底部操作按钮 -->
              <div class="flex justify-end pt-3 border-t border-slate-100">
                <button onclick="closeMobileVerificationCodesModal()" class="btn btn-ghost border border-slate-300 !py-2 text-sm min-h-[44px]">关闭</button>
              </div>
            </div>
          `;
    // 将模态框添加到文档body中
    document.body.appendChild(modal);
  }

  // 显示模态框：添加show类并移除hidden类
  modal.classList.add("show");
  modal.classList.remove("hidden");
  // 加载验证码列表数据
  loadMobileVerificationCodes();
  syncVerificationCodesPollingByModalState();
  // 记录日志
  console.log("[移动端验证码管理] 模态框已打开");
}

/**
 * 关闭移动端验证码管理模态框
 * 隐藏模态框并停止倒计时定时器
 */
function closeMobileVerificationCodesModal() {
  // 获取模态框元素
  const modal = document.getElementById("mobile-verification-codes-modal");
  if (modal) {
    // 隐藏模态框：移除show类并添加hidden类
    modal.classList.remove("show");
    modal.classList.add("hidden");
  }
  // 停止倒计时定时器以释放资源
  stopMobileVerificationCodesCountdown();
  syncVerificationCodesPollingByModalState();
  // 记录日志
  console.log("[移动端验证码管理] 模态框已关闭");
}

/**
 * 加载移动端验证码列表
 * 从后端API获取当前有效的验证码列表并渲染到界面上
 */
async function loadMobileVerificationCodes() {
  try {
    // 调用后端API获取验证码列表
    const response = await fetch("/api/admin/sms/verification_codes", {
      headers: { "X-Session-ID": sessionUUID },
    });
    // 解析JSON响应
    const result = await response.json();

    // 获取验证码列表容器元素
    const listContainer = document.getElementById(
      "mobile-verification-codes-list",
    );

    // 检查请求是否成功且有数据
    if (result.success && result.codes && result.codes.length > 0) {
      // 使用map生成每个验证码项的HTML，然后join拼接
      listContainer.innerHTML = result.codes
        .map((item) => {
          // 计算剩余分钟数和秒数
          const expiresIn = Math.max(0, Math.floor(item.expires_in / 60));
          const expiresSec = Math.max(0, item.expires_in % 60);
          // 返回单个验证码项的HTML结构
          return `
                  <div class="border border-slate-200 rounded-xl p-4 bg-white shadow-sm">
                    <!-- 验证码信息区域 -->
                    <div class="grid grid-cols-3 gap-2 mb-3">
                      <!-- 手机号显示 -->
                      <div>
                        <span class="text-xs text-slate-500">📱 手机号</span>
                        <p class="font-semibold text-slate-700 text-sm">+86 ${
                          item.phone
                        }</p>
                      </div>
                      <!-- 验证码显示 -->
                      <div>
                        <span class="text-xs text-slate-500">🔢 验证码</span>
                        <p class="font-mono text-lg font-bold text-sky-600">${
                          item.code
                        }</p>
                      </div>
                      <!-- 剩余时间显示，使用特殊类名用于倒计时更新 -->
                      <div>
                        <span class="text-xs text-slate-500">⏰ 剩余时间</span>
                        <p class="mobile-verification-code-countdown text-sm ${
                          expiresIn < 2
                            ? "text-red-600 font-semibold"
                            : "text-slate-600"
                        }"
                           data-expires-at="${item.expires_at}">
                          ${expiresIn}分${expiresSec}秒
                        </p>
                      </div>
                    </div>
                    <!-- 操作按钮 -->
                    <button onclick="invalidateMobileVerificationCode('${
                      item.phone
                    }')" 
                      class="btn btn-ghost border border-red-300 text-red-600 w-full !py-2 text-sm min-h-[40px]">
                      ❌ 使验证码失效
                    </button>
                  </div>
                `;
        })
        .join("");
    } else {
      // 无数据时显示提示信息
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-sm">当前没有有效的验证码</p>';
    }

    // 启动倒计时更新
    startMobileVerificationCodesCountdown();
    // 记录日志
    console.log(
      "[移动端验证码管理] 验证码列表已加载，共",
      result.codes?.length || 0,
      "条",
    );
  } catch (e) {
    // 错误处理：显示错误提示
    console.error("[移动端验证码管理] 加载失败:", e);
    // showModalAlert("加载验证码列表失败: " + e.message);
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "加载验证码列表失败: " + e.message,
      icon: "error",
    });
    // 停止倒计时
    stopMobileVerificationCodesCountdown();
  }
}

/**
 * 移动端使验证码失效
 * @param {string} phone - 要使验证码失效的手机号
 */
async function invalidateMobileVerificationCode(phone) {
  // 弹出确认对话框
  const confirmed = await jsShowConfirm(
    "确认失效",
    `确定要使手机号 +86 ${phone} 的验证码失效吗？`,
  );
  // 用户取消则直接返回
  if (!confirmed) {
    return;
  }

  try {
    // 调用后端API使验证码失效
    const response = await fetch("/api/admin/sms/invalidate_code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ phone: phone }),
    });
    // 解析响应
    const result = await response.json();

    // 根据结果显示相应提示
    if (result.success) {
      // showModalAlert("验证码已失效", "成功");
      fireVerificationCodesModalSwal({
        title: "成功",
        text: "验证码已失效",
        icon: "success",
      });
      // 重新加载验证码列表
      loadMobileVerificationCodes();
    } else {
      // showModalAlert(result.message || "操作失败");
      fireVerificationCodesModalSwal({
        title: "错误",
        text: result.message || "操作失败",
        icon: "error",
      });
    }
  } catch (e) {
    // 错误处理
    console.error("[移动端验证码管理] 使验证码失效失败:", e);
    // showModalAlert("操作失败: " + e.message);
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

/**
 * 移动端手动添加验证码
 * 用于测试或紧急情况下手动添加验证码（不会实际发送短信）
 */
async function addMobileManualVerificationCode() {
  // 获取手机号输入框的值
  const phone = document
    .getElementById("mobile-manual-code-phone")
    .value.trim();
  // 获取验证码输入框的值
  let code = document.getElementById("mobile-manual-code-value").value.trim();

  // 如果验证码为空，自动生成6位随机数字
  if (!code) {
    code = Math.floor(100000 + Math.random() * 900000).toString();
    document.getElementById("mobile-manual-code-value").value = code;
  } else if (!/^\d{6}$/.test(code)) {
    // 验证码格式校验：必须是6位数字
    // showModalAlert("验证码必须是6位数字");
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "验证码必须是6位数字",
      icon: "error",
    });
    return;
  }

  // 再次校验验证码格式（防止自动生成的也出问题）
  if (!code || !/^\d{6}$/.test(code)) {
    // showModalAlert("请输入6位数字验证码");
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "请输入6位数字验证码",
      icon: "error",
    });
    return;
  }

  try {
    // 调用后端API添加验证码
    const response = await fetch("/api/admin/sms/add_manual_code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        phone: phone,
        code: code,
      }),
    });
    // 解析响应
    const result = await response.json();

    // 根据结果显示相应提示
    if (result.success) {
      // showModalAlert("验证码已添加", "成功");
      fireVerificationCodesModalSwal({
        title: "成功",
        text: "验证码已添加",
        icon: "success",
      });
      // 清空输入框
      document.getElementById("mobile-manual-code-phone").value = "";
      document.getElementById("mobile-manual-code-value").value = "";
      // 重新加载验证码列表
      loadMobileVerificationCodes();
    } else {
      // showModalAlert(result.message || "添加失败");
      fireVerificationCodesModalSwal({
        title: "错误",
        text: result.message || "添加失败",
        icon: "error",
      });
    }
  } catch (e) {
    // 错误处理
    console.error("[移动端验证码管理] 添加验证码失败:", e);
    // showModalAlert("操作失败: " + e.message);
    fireVerificationCodesModalSwal({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ========== 按钮权限校验 ========== //

async function checkButtonPermission(buttonId, permissionName) {
  const hasPermission = await checkAdminPermission(permissionName);
  if (!hasPermission) {
    // showModalAlert(
    //   `您没有权限使用此功能，缺少 ${permissionName} 权限。`,
    //   "权限不足"
    // );
    Swal.fire({
      title: "错误",
      text: `您没有权限使用此功能，缺少 ${permissionName} 权限。`,
      icon: "error",
    });
    return false;
  }
  return true;
}

function updateAdminSessionCountDisplay(
  currentCount,
  maxSessions,
  isGodMode = false,
) {
  const countEl = $("admin-session-count-display");
  if (!countEl) return;

  if (isGodMode) {
    countEl.innerHTML = `<span class="text-purple-600">系统总会话数: ${currentCount}</span>`;
  } else if (currentUserIsGuest) {
    countEl.innerHTML = `<span class="text-blue-600">会话数: 1 / 游客仅限单会话</span>`;
  } else if (maxSessions === -1) {
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

// ====================
// 上帝模式：销毁会话
// ====================
// 增加 confirm 参数，默认为 true
async function destroySession(sessionId, confirm = true) {
  const sessionHash = sessionId.substring(0, 16);
  if (confirm) {
    const confirmed = await jsShowConfirm(
      "确认销毁",
      `确定要销毁会话\n${sessionHash}...\n吗？\n此操作将强制终止该会话！`,
    );
    if (!confirmed) return;
  }

  try {
    const response = await fetch("/auth/admin/destroy_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      body: JSON.stringify({ session_id: sessionId }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`会话 ${sessionId} 已销毁`, "成功");
      Swal.fire({
        title: "成功",
        text: `会话 ${sessionId} 已销毁`,
        icon: "success",
      });
      loadAdminSessions();
      loadAdminSessions_inline();
    } else {
      // showModalAlert(result.message || "销毁失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "销毁失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function selectSession(sessionId, sessionUsername = "") {
  if (legacyAdminViewRejected) {
    await Swal.fire({ icon: "warning", title: "需要重新登录", text: "管理员来源会话已失效，请重新登录后再查看。" });
    return;
  }
  if (normalizeClientSessionUUID(sessionId) === getStoredAdminReturnOriginSession()) {
    returnToAdminSession();
    return;
  }
  const confirmed = await jsShowConfirm(
    "确认切换",
    `确定要切换到会话\n ${sessionId} \n吗？`,
  );

  if (!confirmed) {
    logMessage_Info("[会话切换] 用户取消操作。");
    return;
  }

  if (shouldUseAdminSessionViewMode(sessionId, sessionUsername)) {
    logMessage_Info("[管理员查看] 保留管理员Token并直接进入目标会话...");
    rememberAdminReturnOriginSession();

    Swal.fire({
      icon: "success",
      title: "正在切换会话...",
      text: "正在以管理员身份进入会话...",
      timer: 800,
      showConfirmButton: false,
    }).then(() => {
      window.location.href = buildLegacyUiPath(`/uuid=${sessionId}`);
    });
    return; // 直接返回，不执行后续的 switch_session
  }

  Swal.fire({
    title: "正在切换会话...",
    text: "正在更新认证信息，请稍候",
    allowOutsideClick: false,
    didOpen: () => {
      Swal.showLoading();
    },
  });

  logMessage_Info(`[会话切换] 准备切换到会话 ${sessionId.substring(0, 16)}...`);

  try {
    const response = await fetch("/auth/switch_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      credentials: "include",
      body: JSON.stringify({
        target_session_id: sessionId,
      }),
    });

    const result = await response.json();

    Swal.close();

    if (response.ok && result.success) {
      logMessage_Info(
        `[会话切换] ✓ 认证信息更新成功，准备跳转到 ${sessionId.substring(
          0,
          16,
        )}...`,
      );
      Swal.fire({
        icon: "success",
        title: "切换准备就绪",
        text: "即将跳转到目标会话...",
        timer: 1000,
        showConfirmButton: false,
      }).then(() => {
        window.location.href = buildLegacyUiPath(`/uuid=${sessionId}`);
      });
    } else {
      logMessage_Info(`[会话切换] ✗ 切换失败: ${result.message}`);
      Swal.fire({
        icon: "error",
        title: "切换失败",
        text: result.message || "无法更新认证信息，请稍后重试。",
      });
      if (result.need_login) {
        Swal.fire({
          icon: "warning",
          title: "需要重新登录",
          text: result.message || "认证已失效，请重新登录",
          confirmButtonText: "返回登录",
          allowOutsideClick: false,
          allowEscapeKey: false,
        }).then((r) => {
          if (r.isConfirmed) window.location.href = buildLegacyUiPath("/");
        });
      }
    }
  } catch (e) {
    Swal.close();
    logMessage_Info(`[会话切换] ✗ 切换时发生网络或脚本错误: ${e.message}`);
    Swal.fire({
      icon: "error",
      title: "切换出错",
      text: `网络或脚本错误: ${e.message}`,
    });
  }
}

// 增加 confirm 参数，默认为 true
async function deleteSession(sessionId, confirm = true) {
  if (confirm) {
    const confirmed = await jsShowConfirm(
      "确认删除",
      `确定要删除会话\n ${sessionId} \n吗？\n此操作不可恢复！`,
    );

    if (!confirmed) {
      logMessage_Info("[会话删除] 用户取消操作。");
      return;
    }
  }
  title: ("正在删除会话...",
    Swal.fire({
      title: "正在删除会话...",
      text: "请稍候",
      allowOutsideClick: false,
      didOpen: () => {
        Swal.showLoading();
      },
    }));

  logMessage_Info(`[会话删除] 准备删除会话 ${sessionId}...`);

  try {
    const response = await fetch("/auth/user/delete_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      body: JSON.stringify({
        session_id: sessionId,
      }),
    });

    const result = await response.json();

    Swal.close();

    if (result.success) {
      logMessage_Info(`[会话删除] ✓ 会话 ${sessionId} 已删除。`);
      Swal.fire({
        icon: "success",
        title: "删除成功",
        timer: 1500,
        showConfirmButton: false,
      }).then(() => {
        const adminModal = document.getElementById("admin-panel-modal");
        if (adminModal && !adminModal.classList.contains("hidden")) {
          loadAdminSessions();
        } else {
          loadAdminSessions_inline();
        }

        // [修正] 刷新移动端会话列表 (包含 mobile-multi-admin-sessions-list)
        if (typeof loadMobileAdminSessionsList === "function") {
          loadMobileAdminSessionsList();
        }
      });
    } else {
      logMessage_Info(`[会话删除] ✗ 删除失败: ${result.message}`);
      Swal.fire({
        icon: "error",
        title: "删除失败",
        text: result.message || "无法删除会话，请稍后重试。",
      });
    }
  } catch (e) {
    Swal.close();
    logMessage_Info(`[会话删除] ✗ 删除时发生网络或脚本错误: ${e.message}`);
    Swal.fire({
      icon: "error",
      title: "删除出错",
      text: `网络或脚本错误: ${e.message}`,
    });
  }
}

// ====================
// 会话选择器模态框函数
// ====================

function showSessionPicker() {
  const modal = $("session-picker-modal");
  if (!modal) return;

  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.body.classList.add("modal-visible");

  loadSessionPickerList();
}

function closeSessionPicker() {
  const modal = $("session-picker-modal");
  if (!modal) return;

  modal.classList.add("hidden");
  modal.classList.remove("flex");
  document.body.classList.remove("modal-visible");
}

async function loadSessionPickerList() {
  const listEl = $("session-picker-list");
  if (!listEl) return;

  listEl.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  if (Array.isArray(window.quickLoginSessions)) {
    const quickSessions = window.quickLoginSessions;
    window.quickLoginSessions = null;
    listEl.innerHTML =
      quickSessions.length === 0
        ? '<p class="text-slate-400 text-center py-10">暂无可恢复会话</p>'
        : quickSessions
            .map((session) => {
              const sessionIdArg = escapeInlineJsArg(session.session_id);
              const ownerArg = escapeInlineJsArg(
                session.username || currentAuthUsername || "",
              );
              return `
                <div class="border border-slate-200 rounded-lg p-3">
                  <p class="font-semibold text-slate-800 break-all">会话 ${session.session_id}</p>
                  <p class="text-xs text-slate-500 mt-1">${session.is_current ? "当前会话" : "可选择"}</p>
                  <button class="btn btn-primary mt-3 !py-1 !px-3 text-xs" onclick='selectSessionFromPicker(${sessionIdArg}, ${ownerArg})'>进入</button>
                </div>
              `;
            })
            .join("");
    return;
  }

  try {
    const headers = {
      "X-Session-ID": getAuthenticatedSessionHeaderValue(),
    };

    const response = await fetch("/auth/user/sessions", {
      headers: headers,
    });
    const result = await response.json();

    if (!result.success) {
      listEl.innerHTML = `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      return;
    }

    const sessions = result.sessions || [];

    currentSessionInfo.maxSessions = result.max_sessions || 1;
    const validSessions = sessions.filter(
      (session) =>
        session.session_id &&
        session.session_id !== "null" &&
        session.session_id.trim() !== "",
    );

    currentSessionInfo.currentCount = validSessions.length;
    updateSessionCountDisplay();

    if (validSessions.length === 0) {
      listEl.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无会话，请创建新会话</p>';
      return;
    }

    listEl.innerHTML = validSessions
      .map((session) => {
        // 修改为使用 toLocaleString 的自定义格式，或者保持原样，
        // 原代码使用的是 toLocaleString()，它本身就会包含年份 (如 2023/12/5 14:30:00)。
        // 如果您希望这里也统一格式为 YYYY-MM-DD HH:mm，请使用以下代码：

        let createdDate = "未知";
        if (session.created_at) {
          const d = new Date(session.created_at * 1000);
          createdDate = `${d.getFullYear()}-${(d.getMonth() + 1)
            .toString()
            .padStart(2, "0")}-${d.getDate().toString().padStart(2, "0")} ${d
            .getHours()
            .toString()
            .padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
        }

        const isCurrent =
          session.is_current || session.session_id === sessionUUID;
        const sessionHash =
          session.session_hash || session.session_id.substring(0, 16);
        const ownerUsername = String(session.username || currentAuthUsername || "");
        const sessionIdArg = escapeInlineJsArg(session.session_id);
        const ownerUsernameArg = escapeInlineJsArg(ownerUsername);

        return `
            <div class="border ${
              isCurrent ? "border-sky-500 bg-sky-50" : "border-slate-200"
            } rounded-lg p-3 hover:shadow-md transition-shadow">
              <div class="flex justify-between items-start">
                <div class="flex-1">
                  <p class="font-semibold text-slate-800 break-all"> 会话 ${
                    session.session_id
                  }
                    
                  </p>
                  ${
                    isCurrent
                      ? '<p class="text-right"><span class="text-xs text-sky-600 ml-2 px-2 py-0.5 bg-sky-100 rounded-full">(当前)</span></p>'
                      : ""
                  }
                  <p class="text-xs text-slate-500 mt-1">创建时间: ${createdDate}</p>
                  <p class="text-xs mt-1">
                    <span class="px-2 py-0.5 rounded-full text-xs font-semibold ${
                      session.is_multi_account_mode
                        ? session.login_success
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-700"
                        : session.login_success
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-700"
                    }">
                      ${
                        session.is_multi_account_mode
                          ? session.login_success
                            ? "✓ 已登录"
                            : "○ 未登录"
                          : session.login_success
                            ? "✓ 已登录"
                            : "○ 未登录"
                      }
                    </span>
                  </p>
                </div>
                <div class="flex flex-col gap-2">
                  ${
                    !isCurrent
                      ? `
                    <button class="btn btn-primary !py-1 !px-3 text-xs" onclick='selectSessionFromPicker(${sessionIdArg}, ${ownerUsernameArg})'>
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                      </svg>
                      进入
                    </button>
                    <button class="btn btn-ghost !py-1 !px-3 !text-red-600 text-xs border border-red-200 hover:bg-red-50" onclick="deleteSessionFromPicker(${escapeInlineJsArg(session.session_id)})">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                      </svg>
                      删除
                    </button>
                  `
                      : '<span class="text-xs text-slate-400">当前会话</span>'
                  }
                </div>
              </div>
            </div>
          `;
      })
      .join("");
  } catch (e) {
    logMessage_Error("加载会话列表失败:", e);
    listEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}

function refreshSessionPicker() {
  loadSessionPickerList();
}

function updateSessionCountDisplay() {
  const countEl = $("session-count-display");
  if (!countEl) return;

  const { currentCount, maxSessions } = currentSessionInfo;

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

async function selectSessionFromPicker(sessionId, sessionUsername = "") {
  if (legacyAdminViewRejected) {
    await Swal.fire({ icon: "warning", title: "需要重新登录", text: "管理员来源会话已失效，请重新登录后再查看。" });
    return;
  }
  if (normalizeClientSessionUUID(sessionId) === getStoredAdminReturnOriginSession()) {
    returnToAdminSession();
    return;
  }
  logMessage_Info(`准备切换到会话 ${sessionId.substring(0, 16)}...`);
  closeSessionPicker();

  if (shouldUseAdminSessionViewMode(sessionId, sessionUsername)) {
    logMessage_Info(
      "[管理员查看-移动端] 保留管理员Token并直接进入目标会话...",
    );
    rememberAdminReturnOriginSession();
    window.location.href = buildLegacyUiPath(`/uuid=${sessionId}`);
    return;
  }

  try {
    logMessage_Info(
      `正在为目标会话 ${sessionId.substring(0, 16)} 刷新认证令牌...`,
    );

    const response = await fetch("/auth/switch_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      credentials: "include",
      body: JSON.stringify({
        target_session_id: sessionId,
      }),
    });
    const result = await response.json();
    if (response.ok && result.success) {
      logMessage_Info(
        `令牌更新成功，正在跳转到会话 ${sessionId.substring(0, 16)}...`,
      );
      window.location.href = buildLegacyUiPath(`/uuid=${sessionId}`);
    } else {
      logMessage_Info(`[错误] 无法切换会话: ${result.message}`);
      // showModalAlert(`无法切换会话: ${result.message}`, "切换失败");
      Swal.fire({
        icon: "error",
        title: "切换失败",
        text: result.message || "无法更新认证信息，请稍后重试。",
      });
      if (result.need_login) {
        Swal.fire({
          icon: "warning",
          title: "需要重新登录",
          text: result.message || "认证已失效，请重新登录",
          confirmButtonText: "返回登录",
          allowOutsideClick: false,
          allowEscapeKey: false,
        }).then((r) => {
          if (r.isConfirmed) window.location.href = buildLegacyUiPath("/");
        });
      }
    }
  } catch (e) {
    logMessage_Error("切换会话失败:", e);
    logMessage_Info(`[错误] 切换会话时发生网络或脚本错误: ${e.message}`);
    // showModalAlert(`切换会话时发生网络或脚本错误: ${e.message}`, "切换失败");
    Swal.fire({
      icon: "error",
      title: "切换失败",
      text: `切换会话时发生网络或脚本错误: ${e.message}`,
    });
  }
}

async function createNewSessionFromPicker() {
  try {
    logMessage_Info("[会话创建] 正在获取最新会话信息...");
    const response = await fetch("/auth/user/sessions", {
      headers: {
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
    });
    const result = await response.json();

    if (result.success) {
      currentSessionInfo.maxSessions =
        result.max_sessions !== undefined && result.max_sessions !== null
          ? result.max_sessions
          : -1;
      const validSessions = (result.sessions || []).filter(
        (session) =>
          session.session_id &&
          session.session_id !== "null" &&
          session.session_id.trim() !== "",
      );
      currentSessionInfo.currentCount = validSessions.length;
      logMessage_Info(
        `[会话创建] 会话信息已更新: 当前 ${
          currentSessionInfo.currentCount
        } / 最大 ${
          currentSessionInfo.maxSessions === -1
            ? "无限制"
            : currentSessionInfo.maxSessions
        }`,
      );
      updateSessionCountDisplay();
      updateAdminSessionCountDisplay(
        currentSessionInfo.currentCount,
        currentSessionInfo.maxSessions,
      );
      updateAdminSessionCountDisplayInline(
        currentSessionInfo.currentCount,
        currentSessionInfo.maxSessions,
      );
    } else {
      logMessage_Info(
        `[会话创建] 警告: 获取最新会话信息失败: ${result.message}`,
      );
      // showModalAlert("无法获取最新的会话限制信息，将继续尝试创建。", "警告");
      Swal.fire({
        title: "警告",
        text: "无法获取最新的会话限制信息，将继续尝试创建。",
        icon: "warning",
      });
    }
  } catch (error) {
    logMessage_Info(
      `[会话创建] 错误: 获取最新会话信息时发生网络错误: ${error}`,
    );
    // showModalAlert(
    //   `获取最新的会话限制信息时发生网络错误: ${error.message}，将继续尝试创建。`,
    //   "网络错误"
    // );
    Swal.fire({
      title: "网络错误",
      text: `获取最新的会话限制信息时发生网络错误: ${error.message}，将继续尝试创建。`,
      icon: "error",
    });
  }
  if (
    currentSessionInfo.maxSessions !== -1 &&
    currentSessionInfo.currentCount >= currentSessionInfo.maxSessions
  ) {
    const result = await Swal.fire({
      title: "会话数量已达上限",
      html: `您已达到最大会话数量限制（${currentSessionInfo.maxSessions}个）。<br><br>是否要自动删除最早的会话并创建新会话？`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "确定，删除最旧会话",
      cancelButtonText: "取消",
      confirmButtonColor: "#3085d6",
      cancelButtonColor: "#d33",
    });

    if (!result.isConfirmed) {
      logMessage_Info("[会话创建] 用户取消操作：会话数已达上限。");
      return;
    }
    try {
      const response = await fetch("/auth/user/sessions", {
        headers: { "X-Session-ID": getAuthenticatedSessionHeaderValue() },
      });
      const sessionsResult = await response.json();

      if (
        sessionsResult.success &&
        sessionsResult.sessions &&
        sessionsResult.sessions.length > 0
      ) {
        const validSessions = sessionsResult.sessions.filter(
          (s) =>
            s.session_id &&
            s.session_id !== "null" &&
            s.session_id.trim() !== "" &&
            s.session_id !== sessionUUID,
        );

        if (validSessions.length > 0) {
          validSessions.sort(
            (a, b) => (a.created_at || 0) - (b.created_at || 0),
          );
          const oldestSession = validSessions[0];

          logMessage_Info(
            `[会话管理] 正在删除最旧的会话: ${oldestSession.session_id.substring(
              0,
              16,
            )}...`,
          );
          const deleteResponse = await fetch("/auth/user/delete_session", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Session-ID": getAuthenticatedSessionHeaderValue(),
            },
            body: JSON.stringify({
              session_id: oldestSession.session_id,
            }),
          });

          const deleteResult = await deleteResponse.json();
          if (deleteResult.success) {
            logMessage_Info(`[会话管理] 已删除最旧的会话`);
          } else {
            logMessage_Info(`[会话管理] 删除会话失败: ${deleteResult.message}`);
          }
        }
      }
    } catch (e) {
      logMessage_Info(`[会话管理] 删除旧会话时出错: ${e.message}`);
    }
  }

  const newUUID = generateUUID();
  logMessage_Info(`正在创建新会话 ${newUUID}`);
  const confirmed = await jsShowConfirm(
    "确认操作",
    "您确定要创建一个新的会话吗？",
  );

  if (!confirmed) {
    logMessage_Info("[会话创建] 用户取消操作。");
    return;
  }
  let mobileButton = null;
  if (isMobileMode) {
    mobileButton = $("mobile-create-session-btn");
    if (mobileButton) {
      mobileButton.disabled = true;
      mobileButton.innerHTML = "正在创建...";
    }
  } else {
    Swal.fire({
      title: "正在创建新会话...",
      text: "请稍候",
      allowOutsideClick: false,
      didOpen: () => {
        Swal.showLoading();
      },
    });
  }

  logMessage_Info(`[会话创建] 准备创建新会话...`);
  try {
    const response = await fetch("/auth/user/create_session_persistence", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      body: JSON.stringify({
        session_id: newUUID,
      }),
    });

    const result = await response.json();

    if (result.success) {
      logMessage_Info(`会话持久化文件已创建: ${result.message}`);
      setActiveLegacySession(result.session_id || newUUID);
      // 新会话属于当前调用者自己，"返回管理员会话"的旧记录已无意义。
      clearAdminReturnOriginState("创建新会话");
      if (result.cleanup_message) {
        logMessage_Info(`提示: ${result.cleanup_message}`);
      }
      if (isMobileMode) {
        closeMobileSessionPicker();
      } else {
        closeSessionPicker();
      }
      window.location.replace(buildLegacyUiPath(`/uuid=${sessionUUID}`));
    } else {
      logMessage_Info(`创建会话失败: ${result.message}`);
      if (isMobileMode) {
        // showModalAlert(result.message, "创建失败");
        Swal.fire({
          icon: "error",
          title: "创建失败",
          text: 创建会话失败,
        });
        if (mobileButton) {
          mobileButton.disabled = false;
          mobileButton.innerHTML = `
              <svg class="w-5 h-5 inline-block mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
              </svg>
              创建新会话
            `;
        }
      } else {
        Swal.fire({
          icon: "error",
          title: "创建失败",
          text: result.message,
        });
      }
    }
  } catch (e) {
    logMessage_Info(`创建会话时发生错误: ${e.message}`);
    if (isMobileMode) {
      if (mobileButton) {
        mobileButton.disabled = false;
        mobileButton.innerHTML = `
              <svg class="w-5 h-5 inline-block mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
              </svg>
              创建新会话
            `;
      }
    } else {
      Swal.close();
    }
    // showModalAlert(`创建会话失败: ${e.message}`, "创建失败");
    Swal.fire({
      icon: "error",
      title: "创建失败",
      text: `创建会话失败: ${e.message}`,
    });
  }
}

async function deleteSessionFromPicker(sessionId, confirm = true) {
  // 如果 confirm 为 true，则显示内部确认框；否则直接执行
  if (confirm) {
    const confirmed = await jsShowConfirm(
      "确认删除",
      "确定要删除此会话吗？<br>此操作不可恢复！",
    );
    if (!confirmed) return;
  }

  Swal.fire({
    title: "正在删除会话...",
    text: "请稍候",
    allowOutsideClick: false,
    didOpen: () => {
      Swal.showLoading();
    },
  });
  try {
    const response = await fetch("/auth/user/delete_session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getAuthenticatedSessionHeaderValue(),
      },
      body: JSON.stringify({
        session_id: sessionId,
      }),
    });

    const result = await response.json();
    Swal.close();

    if (result.success) {
      // showModalAlert("会话已删除", "成功");
      Swal.fire({
        icon: "success",
        title: "删除成功",
        text: "会话已删除",
      });
      const mobilePicker = $("mobile-session-picker-modal");
      const desktopPicker = $("session-picker-modal");

      // 1. 刷新选择器模态框列表 (如果打开)
      if (mobilePicker && !mobilePicker.classList.contains("hidden")) {
        logMessage_Info("[会话删除] 正在刷新移动端会话选择列表...");
        loadMobileSessionPickerList();
      } else if (desktopPicker && !desktopPicker.classList.contains("hidden")) {
        logMessage_Info("[会话删除] 正在刷新桌面端会话选择列表...");
        loadSessionPickerList();
      } else {
        logMessage_Info("[会话删除] 正在刷新（兜底）...");
        if (isMobileMode) {
          loadMobileSessionPickerList();
        } else {
          loadSessionPickerList();
        }
      }

      // 2. 新增：刷新移动端主面板列表
      if (typeof loadMobileSessionsList === "function") {
        logMessage_Info("[会话删除] 正在刷新移动端主面板列表...");
        loadMobileSessionsList();
      }
    } else {
      // showModalAlert("删除失败: " + result.message, "错误");
      Swal.fire({
        icon: "error",
        title: "删除失败",
        text: "删除失败: " + result.message,
      });
    }
  } catch (e) {
    Swal.close();
    // showModalAlert("删除失败: " + e.message, "错误");
    Swal.fire({
      icon: "error",
      title: "删除失败",
      text: "删除失败: " + e.message,
    });
  }
}
function validateInput(input, type) {
  if (!input || input.trim() === "") {
    return { valid: false, message: "输入不能为空" };
  }

  switch (type) {
    case "username":
      if (input.length < 3 || input.length > 50) {
        return { valid: false, message: "用户名长度应在3-50个字符之间" };
      }
      if (!/^[a-zA-Z0-9_-]+$/.test(input)) {
        return {
          valid: false,
          message: "用户名只能包含字母、数字、下划线和连字符",
        };
      }
      break;
    case "password":
      if (input.length < 6) {
        return { valid: false, message: "密码长度至少6个字符" };
      }
      break;
    case "email":
      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailPattern.test(input)) {
        return { valid: false, message: "请输入有效的邮箱地址" };
      }
      break;
  }

  return { valid: true };
}
let sessionValidityCheckInterval = null;
function redirectToLoginAfterSessionExpiry() {
  if (typeof stopReminderChecker === "function") stopReminderChecker();
  const legacyHomePath = buildLegacyUiPath("/");
  if (window.location.pathname === legacyHomePath) {
    return false;
  }

  logMessage_Info("[会话检查] 会话已失效，正在返回登录页面");
  window.location.replace(legacyHomePath);
  return true;
}

async function checkSessionValidity() {
  if (!sessionUUID) {
    logMessage_Info("[会话检查] 无UUID，跳过检查");
    return;
  }

  try {
    const response = await fetch("/auth/check_uuid_type", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ uuid: sessionUUID }),
    });

    const result = await response.json();

    if (result.success && result.uuid_type === "unknown") {
      stopReminderChecker();
      logMessage_Warning("[会话检查] 会话不存在，UUID类型为unknown");
      if (sessionValidityCheckInterval) {
        clearInterval(sessionValidityCheckInterval);
        sessionValidityCheckInterval = null;
      }

      // 检查遮罩是否已存在，防止重复创建
      if (document.getElementById("logout-elsewhere-overlay")) {
        return;
      }

      const logoutOverlay = document.createElement("div");
      logoutOverlay.id = "logout-elsewhere-overlay";
      logoutOverlay.style.cssText = `
              position: fixed;
              top: 0;
              left: 0;
              width: 100%;
              height: 100%;
              background: rgba(0, 0, 0, 0.85);
              z-index: 20002; /* 修正：提升层级以覆盖移动端容器 */
              display: flex;
              align-items: center;
              justify-content: center;
            `;

      const modalContent = document.createElement("div");
      modalContent.style.cssText = `
              background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
              padding: 40px;
              border-radius: 20px;
              box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
              max-width: 500px;
              width: 90%;
              text-align: center;
              color: white;
            `;

      const icon = document.createElement("div");
      icon.innerHTML = `
              <svg style="width: 80px; height: 80px; margin: 0 auto 20px;" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
              </svg>
            `;

      const title = document.createElement("h2");
      title.textContent = "会话已失效";
      title.style.cssText = `
              font-size: 24px;
              font-weight: bold;
              margin: 0 0 20px 0;
            `;

      const text = document.createElement("p");
      text.textContent =
        "UUID不存在\n您的会话已过期或不存在，请重新登录";
      text.style.cssText = `
              font-size: 16px;
              line-height: 1.6;
              margin: 0 0 30px 0;
              opacity: 0.95;
              white-space: pre-wrap;
            `;

      const button = document.createElement("button");
      button.textContent = "返回登录";
      button.style.cssText = `
              background: white;
              color: #667eea;
              border: none;
              padding: 12px 30px;
              border-radius: 25px;
              font-size: 16px;
              font-weight: bold;
              cursor: pointer;
              transition: all 0.3s;
            `;
      button.onmouseover = () => {
        button.style.transform = "scale(1.05)";
        button.style.boxShadow = "0 5px 15px rgba(255, 255, 255, 0.3)";
      };
      button.onmouseout = () => {
        button.style.transform = "scale(1)";
        button.style.boxShadow = "none";
      };

      button.onclick = () => {
        logMessage_Info("[会话检查] 用户确认会话失效，跳转到登录页面");
        redirectToLoginAfterSessionExpiry();
      };

      modalContent.appendChild(icon);
      modalContent.appendChild(title);
      modalContent.appendChild(text);
      modalContent.appendChild(button);
      logoutOverlay.appendChild(modalContent);
      document.body.appendChild(logoutOverlay);
    } else if (!result.success) {
      logMessage_Warning("[会话检查] 检查失败:", result.message);
    } else {
      logMessage_Info("[会话检查] 会话有效，UUID类型:", result.uuid_type);
    }
  } catch (error) {
    logMessage_Error("[会话检查] 检查请求失败:", error);
  }
}
function startSessionValidityCheck() {
  if (sessionValidityCheckInterval) {
    logMessage_Info("[会话检查] 定期检查已在运行");
    return;
  }

  logMessage_Info("[会话检查] 启动定期检查，间隔5分钟");
  checkSessionValidity();
  sessionValidityCheckInterval = setInterval(
    checkSessionValidity,
    5 * 60 * 1000,
  );
}
// function updateMobileGuestVisibility() {
//   console.log("[移动端] 更新游客用户相关元素的可见性，当前用户是否为游客:",
//     currentUserIsGuest);
//   const mobileSidebarUserDetailsLink = document.getElementById(
//     "mobile-sidebar-user-details-link",
//   );

//   if (mobileSidebarUserDetailsLink) {
//     mobileSidebarUserDetailsLink.style.display = currentUserIsGuest
//       ? "none"
//       : "";
//   }
// }

function installGenericMapRuntimeGuards() {
  window.__genericMapRuntimeGuardsInstalled = true;
}

function installAmapRuntimeGuards(provider) {
  if (provider === "amap") {
    window.__amapRuntimeGuardsInstalled = true;
  }
}

function loadAMapOnce() {
  const provider = getActiveMapProvider();
  if (provider !== "amap") {
    installGenericMapRuntimeGuards();
    return Promise.resolve(null);
  }
  if (AMapReady && AMapInstance) return Promise.resolve(AMapInstance);
  if (amapLoadingPromise) return amapLoadingPromise;
  if (window.AMap && window.AMap.ControlBar) {
    AMapInstance = window.AMap;
    AMapReady = true;
    amapLoadingPromise = Promise.resolve(AMapInstance);
    return amapLoadingPromise;
  }
  if (!AMAP_API_KEY) {
    logMessage_Info("[错误] 尝试加载地图失败：API Key为空。");
    showMissingMapProviderKeyModal("amap");
    return Promise.reject("API Key is missing.");
  }
  const securityJsCode = String(getMapProviderConfig("amap").security_js_code || "").trim();
  if (securityJsCode) {
    window._AMapSecurityConfig = { securityJsCode };
  } else if (window._AMapSecurityConfig) {
    delete window._AMapSecurityConfig.securityJsCode;
  }
  amapLoadingPromise = AMapLoader.load({
    key: AMAP_API_KEY,
    version: "2.0",
    plugins: ["AMap.ControlBar", "AMap.BuildingLayer", "AMap.Walking"],
  })
    .then((AMap) => {
      AMapInstance = AMap;
      AMapReady = true;
      logMessage_Info("高德地图SDK及所有插件加载成功。");
      return AMapInstance;
    })
    .catch((err) => {
      logMessage_Error("AMap 加载失败", err);
      logMessage_Info("[JS-Error] 高德地图SDK加载失败！地图功能将不可用。");
      AMapReady = false;
      AMapInstance = null;
      amapLoadingPromise = null;
      throw err;
    });

  return amapLoadingPromise;
}
async function ensureSingleMap() {
  applyPendingMapProviderConfigIfAny();
  if (getActiveMapProvider() !== "amap") {
    try {
      const isReady = await ensureActiveMapProviderRuntimeIfNeeded("单账号地图初始化");
      if (isReady) {
        initProviderMap("map-container", false);
      }
    } catch (e) {
      logMessage_Error("单账号地图供应商运行时加载失败:", e);
    }
    return;
  }
  if (map || !AMapReady || !AMapInstance) return;
  const container = document.getElementById("map-container");
  if (!container) return;
  const isHidden = container.offsetParent === null;
  if (isHidden) return;
  initMap(AMapInstance);
}
function forceProjectionRefresh() {
  if (!map) return;
  try {
    map.setStatus({ dragEnable: false });
    map.resize();
    requestAnimationFrame(() => {
      const overlays = collectSingleMapFitOverlays(false);

      if (overlays.length > 0) {
        map.setFitView(overlays, false, [60, 60, 60, 60]);
      } else if (
        currentRunData &&
        Array.isArray(currentRunData.target_points) &&
        currentRunData.target_points.length > 0
      ) {
        const pts = currentRunData.target_points.map(
          (p) => new AMapInstance.LngLat(p[0], p[1]),
        );
        map.setFitView(pts, false, [60, 60, 60, 60]);
      } else {
        map.setZoomAndCenter(17, [113.390342, 22.527403]);
      }
      map.setStatus({ dragEnable: true });
    });
  } catch (e) {
    logMessage_Warning("forceProjectionRefresh warning:", e);
  }
}
/**
 * 移动端单账号设置面板参数刷新函数
 *
 * @description
 *   此函数用于从后端刷新 mobile-settings-panel 中的参数配置
 *   mobile-settings-panel 是移动端单账号模式的专属设置面板
 *   参数从 sessions 持久化文件的 `params` 字段读取
 *   而不是多账号模式使用的 `multi_global_params` 字段
 *
 * @workflow
 *   1. 调用后端 get_params API 获取当前参数
 *   2. 后端根据 is_multi_account_mode 状态返回正确的参数
 *   3. 单账号模式下返回 params，多账号模式下返回 global_params
 *   4. 更新前端参数缓存和界面显示
 */
async function refreshMobileSettings() {
  // 获取移动端参数容器元素
  // mobile-params-container 是单账号模式设置面板的参数输入区域
  const container = document.getElementById("mobile-params-container");
  // 如果容器不存在，则直接返回，不执行任何操作
  if (!container) return;

  // 显示正在刷新的提示信息
  // showModalAlert("正在刷新参数...", "提示");
  logMessage_Info("[移动端单账号] 正在刷新设置参数...");

  // 记录日志：开始刷新单账号模式参数
  console.log("[移动端单账号] 开始刷新设置面板参数，来源: params (单账号模式)");

  try {
    // 调用后端 API 获取参数
    // get_params API 会根据后端 is_multi_account_mode 状态返回对应的参数：
    //   - 单账号模式 (is_multi_account_mode=false): 返回 params
    //   - 多账号模式 (is_multi_account_mode=true): 返回 global_params
    // mobile-settings-panel 专属于单账号模式，因此获取的是 params
    const params = await callPythonAPI("get_params");

    // 检查是否成功获取到参数
    if (params) {
      // 更新前端本地参数缓存
      pythonParams = params;

      // 如果 updateParamInputs 函数存在，则更新界面上的参数输入控件
      if (typeof updateParamInputs === "function") {
        updateParamInputs(container, "mobile-param", pythonParams);
      }

      // 如果参数中包含主题颜色，则同步更新主题
      if (params.theme_base_color) {
        // 调用 setBaseColor 更新界面主题颜色
        // 第三个参数 false 表示不触发保存操作，仅更新显示
        setBaseColor(params.theme_base_color, params.theme_base_color, false);
      }

      // 记录刷新成功日志
      console.log("[移动端单账号] 设置面板参数刷新完成，来源: params");

      // 显示刷新成功提示
      // showModalAlert("参数已刷新", "成功");
      logMessage_Info("[移动端单账号] 参数已刷新");
    } else {
      // 未获取到数据，显示错误提示
      // showModalAlert("刷新失败：未获取到数据", "错误");
      logMessage_Error("[移动端单账号] 刷新失败：未获取到数据");
    }
  } catch (e) {
    // 捕获刷新过程中的错误
    console.error("[移动端单账号] 刷新参数失败:", e);
    // 显示错误提示
    // showModalAlert("刷新失败", "错误");
    swal.fire({
      title: "错误",
      text: "刷新失败: " + e.message,
      icon: "error",
    });
  }
}
/**
 * 移动端单账号设置面板参数保存函数
 *
 * @description
 *   此函数用于保存 mobile-settings-panel 中的所有参数配置
 *   mobile-settings-panel 是移动端单账号模式的专属设置面板
 *   参数应该被写入 sessions 持久化文件的 `params` 字段
 *   而不是多账号模式使用的 `multi_global_params` 字段
 *
 * @workflow
 *   1. 获取参数容器中的所有输入元素
 *   2. 遍历并收集每个参数的键值对
 *   3. 调用后端 update_param API 保存参数
 *   4. 后端会根据 is_multi_account_mode 状态自动写入正确位置
 *   5. 单账号模式下 is_multi_account_mode=false，参数写入 params
 */
async function saveMobileSettings() {
  // 获取移动端参数容器元素
  // mobile-params-container 是单账号模式设置面板的参数输入区域
  const container = document.getElementById("mobile-params-container");
  // 如果容器不存在，则直接返回，不执行任何操作
  if (!container) return;

  // 显示正在保存的提示信息
  // showModalAlert("正在保存设置...", "提示");
  swal.fire({
    title: "提示",
    text: "正在保存设置...",
    icon: "info",
  });

  // 记录日志：开始保存单账号模式参数
  console.log("[移动端单账号] 开始保存设置面板参数，目标: params (单账号模式)");

  try {
    // 查询容器内所有的 input 和 select 元素
    // 这些元素包含用户配置的参数值
    const inputs = container.querySelectorAll("input, select");
    // 初始化保存计数器，用于统计成功保存的参数数量
    let savedCount = 0;

    // 遍历每个输入元素，收集并保存参数
    for (const input of inputs) {
      // 从元素的 data-key 属性获取参数键名
      const key = input.dataset.key;
      // 如果没有 data-key 属性，跳过该元素
      if (!key) continue;

      // 根据输入元素的类型，获取对应的值
      let value;
      if (input.type === "checkbox") {
        // 复选框类型：获取选中状态（布尔值）
        value = input.checked;
      } else if (input.type === "number") {
        // 数字类型：解析为浮点数，无效值默认为 0
        value = parseFloat(input.value) || 0;
      } else {
        // 其他类型（文本、下拉框等）：直接获取字符串值
        value = input.value;
      }

      // 更新前端本地参数缓存
      // pythonParams 是前端保存的参数副本，用于界面显示
      pythonParams[key] = value;

      // 调用后端 API 保存参数
      // update_param API 会根据后端 is_multi_account_mode 状态决定写入位置：
      //   - 单账号模式 (is_multi_account_mode=false): 写入 params
      //   - 多账号模式 (is_multi_account_mode=true): 写入 global_params
      // mobile-settings-panel 专属于单账号模式，因此参数会写入 params
      await callPythonAPI("update_param", key, value);

      // 增加保存成功计数
      savedCount++;

      // 不记录参数值，避免把密码、令牌或其他敏感配置写入控制台。
      console.log("[移动端单账号] 参数已保存");
    }

    // 记录保存完成日志
    console.log(
      `[移动端单账号] 设置保存完成，共保存 ${savedCount} 个参数到 params`,
    );

    // 显示保存成功提示
    // showModalAlert("设置已保存", "成功");
    swal.fire({
      title: "成功",
      text: "设置已保存",
      icon: "success",
    });
  } catch (e) {
    // 捕获保存过程中的错误
    console.error("[移动端单账号] 保存参数失败:", e);
    // 显示错误提示，包含错误信息
    // showModalAlert("保存失败: " + e.message, "错误");
    swal.fire({
      title: "错误",
      text: "保存失败: " + e.message,
      icon: "error",
    });
  }
}

function ensureSingleControls() {
  const container = document.getElementById("map-container");
  if (!container) return;
  const zoomIn = document.getElementById("zoom-in");
  const zoomOut = document.getElementById("zoom-out");
  const reset = document.getElementById("reset-view-btn");
  const hasZoomIn = !!zoomIn && isElementInsideContainer(container, zoomIn);
  const hasZoomOut = !!zoomOut && isElementInsideContainer(container, zoomOut);
  const hasReset = !!reset && isElementInsideContainer(container, reset);

  if (hasZoomIn && hasZoomOut && hasReset) {
    attachSingleControlHandlers();
    return;
  }
  [zoomIn, zoomOut, reset].forEach((element) => {
    if (element && !isElementInsideContainer(container, element)) {
      removeElementOrParentOverlay(element);
    }
  });
  const overlay = document.createElement("div");
  overlay.dataset.providerMapControlOverlay = "true";
  overlay.className =
    "absolute top-4 right-3 z-[1000] bg-white/80 backdrop-blur-sm rounded-full shadow-md flex items-center space-x-1 p-1 border border-slate-200";
  overlay.innerHTML = `
    <button id="zoom-in" class="w-9 h-9 font-bold text-xl text-center hover:bg-slate-100 rounded-full text-slate-700">+</button>
    <span id="zoom-level" class="text-xs font-mono select-none w-8 text-center">17</span>
    <button id="zoom-out" class="w-9 h-9 font-bold text-xl text-center hover:bg-slate-100 rounded-full text-slate-700">-</button>
    <button id="reset-view-btn" class="w-9 h-9 font-bold text-lg flex items-center justify-center hover:bg-slate-100 rounded-full text-slate-700" title="复位视角">🎯</button>
  `;
  container.appendChild(overlay);

  attachSingleControlHandlers();
}

function attachSingleControlHandlers() {
  const zi = document.getElementById("zoom-in");
  const zo = document.getElementById("zoom-out");
  const rv = document.getElementById("reset-view-btn");
  const provider = getActiveMapProvider();
  const instance = getProviderMapInstance("map-container");
  const bind = (button, action) => {
    if (!button || button._bound) return;
    const handler = () => {
      if (provider !== "amap" && !isCurrentProviderMapInstance("map-container", instance)) return;
      action();
    };
    button.addEventListener("click", handler);
    button._bound = true;
    if (provider !== "amap" && instance) {
      (instance.__providerDomCleanups ||= []).push(() => {
        button.removeEventListener("click", handler);
        button._bound = false;
      });
    }
  };
  bind(zi, () => {
    zoomProviderMap("map-container", 1);
  });
  bind(zo, () => {
    zoomProviderMap("map-container", -1);
  });
  bind(rv, () => {
    clearTaskMapAutoResetTimer();
    resetTaskMapView("map-container");
  });
}

function ensureMultiControls() {
  const container = document.getElementById("multi-map-container");
  if (!container) return;

  const zoomIn = document.getElementById("multi-zoom-in");
  const zoomOut = document.getElementById("multi-zoom-out");
  const reset = document.getElementById("multi-reset-view-btn");
  const hasZoomIn = !!zoomIn && isElementInsideContainer(container, zoomIn);
  const hasZoomOut = !!zoomOut && isElementInsideContainer(container, zoomOut);
  const hasReset = !!reset && isElementInsideContainer(container, reset);

  if (hasZoomIn && hasZoomOut && hasReset) {
    attachMultiControlHandlers();
    return;
  }
  [zoomIn, zoomOut, reset].forEach((element) => {
    if (element && !isElementInsideContainer(container, element)) {
      removeElementOrParentOverlay(element);
    }
  });

  const overlay = document.createElement("div");
  overlay.dataset.providerMapControlOverlay = "true";
  overlay.className =
    "absolute top-4 right-3 z-[1000] bg-white/80 backdrop-blur-sm rounded-full shadow-md flex items-center space-x-1 p-1 border border-slate-200";
  overlay.innerHTML = `
    <button id="multi-zoom-in" class="w-9 h-9 font-bold text-xl text-center hover:bg-slate-100 rounded-full text-slate-700">+</button>
    <span id="multi-zoom-level" class="text-xs font-mono select-none w-8 text-center">17</span>
    <button id="multi-zoom-out" class="w-9 h-9 font-bold text-xl text-center hover:bg-slate-100 rounded-full text-slate-700">-</button>
    <button id="multi-reset-view-btn" class="w-9 h-9 font-bold text-lg flex items-center justify-center hover:bg-slate-100 rounded-full text-slate-700" title="复位视角">🎯</button>
  `;
  container.appendChild(overlay);

  attachMultiControlHandlers();
}

function attachMultiControlHandlers() {
  const zi = document.getElementById("multi-zoom-in");
  const zo = document.getElementById("multi-zoom-out");
  const rv = document.getElementById("multi-reset-view-btn");
  const provider = getActiveMapProvider();
  const instance = getProviderMapInstance("multi-map-container");
  const bind = (button, action) => {
    if (!button || button._bound) return;
    const handler = () => {
      if (provider !== "amap" && !isCurrentProviderMapInstance("multi-map-container", instance)) return;
      action();
    };
    button.addEventListener("click", handler);
    button._bound = true;
    if (provider !== "amap" && instance) {
      (instance.__providerDomCleanups ||= []).push(() => {
        button.removeEventListener("click", handler);
        button._bound = false;
      });
    }
  };
  bind(zi, () => {
    zoomProviderMap("multi-map-container", 1);
  });
  bind(zo, () => {
    zoomProviderMap("multi-map-container", -1);
  });
  bind(rv, () => {
    clearTaskMapAutoResetTimer();
    resetTaskMapView("multi-map-container");
  });
}

function removeAmapLicenseOverlay(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const remove = () => {
    container.querySelectorAll("div").forEach((el) => {
      if (
        el.style.position === "absolute" &&
        el.style.zIndex === "9999" &&
        el.textContent.includes("经识别")
      ) {
        el.remove();
      }
    });
  };
  remove();
  const observer = new MutationObserver(() => remove());
  observer.observe(container, { childList: true, subtree: true });
  setTimeout(() => observer.disconnect(), 10000);
}

async function initMap(AMap) {
  if (getActiveMapProvider() !== "amap") {
    if (map && typeof map.destroy === "function") {
      try {
        map.destroy();
      } catch (e) {
        logMessage_Warning("销毁旧高德地图实例失败:", e);
      }
    }
    map = null;
    try {
      const isReady = await ensureActiveMapProviderRuntimeIfNeeded("主地图初始化");
      if (isReady) {
        initProviderMap("map-container", false);
        logMessage_Info(
          `当前地图提供方为${getMapProviderDisplayName()}，已使用对应前端地图初始化。`,
        );
      }
    } catch (e) {
      logMessage_Error("主地图供应商运行时加载失败:", e);
    }
    return;
  }
  if (map) {
    const container = map.getContainer();
    if (container && container.id === "map-container") {
      return;
    }
    try {
      map.destroy();
    } catch (e) {}
    map = null;
  }

  AMapInstance = AMap;
  map = new AMapInstance.Map("map-container", {
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
  map.addControl(ctrlBar);

  try {
    const buildings = new AMapInstance.BuildingLayer();
    buildings.setMap(map);
  } catch (e) {
    logMessage_Warning("BuildingLayer not available:", e);
  }

  map.on("mousedown", onMapMouseDown);
  map.on("mousemove", onMapMouseMove);
  map.on("mouseup", onMapMouseUp);
  map.on("zoomchange", () => {
    if (!map) return;
    const z = map.getZoom();
    const zoomLevelEl = $("zoom-level");
    if (zoomLevelEl) zoomLevelEl.textContent = String(z.toFixed(1));
  });
  bindTaskMapSdkInteractionTracking("map-container", map);
  bindTaskMapUserInteractionTracking("map-container", map.getContainer && map.getContainer());
  bindTaskMapUserInteractionTracking("map-container", document.getElementById("map-container"));

  if (window.mapCleanup) window.mapCleanup();
  window.mapCleanup = enhanceMapInteraction(map);
  map.setStatus({
    doubleClickZoom: true,
    dragEnable: true,
    scrollWheel: true,
    keyboardEnable: true,
  });

  map.on("complete", () => {
    logMessage_Info("地图实例已加载。");
    removeAmapLicenseOverlay("map-container");
    if (resolveMapReady) {
      resolveMapReady(map);
    }
  });
}

function appendSingleMapOverlay(overlays, overlay) {
  if (!overlay) return;
  if (Array.isArray(overlay)) {
    overlay.forEach((item) => appendSingleMapOverlay(overlays, item));
    return;
  }
  overlays.push(overlay);
}

function collectSingleMapFitOverlays(includeMarkers = true) {
  const overlays = [];
  appendSingleMapOverlay(overlays, polylines.recommended);
  if (includeMarkers) {
    appendSingleMapOverlay(overlays, markers);
  }
  appendSingleMapOverlay(overlays, polylines.draft);
  appendSingleMapOverlay(overlays, polylines.run);
  appendSingleMapOverlay(overlays, polylines.history);
  return overlays;
}

function removeSingleMapOverlay(overlay) {
  if (!map || !overlay) return;
  if (Array.isArray(overlay)) {
    overlay.forEach((item) => removeSingleMapOverlay(item));
    return;
  }
  map.remove(overlay);
}

function showMainApp() {
  applyPendingMapProviderConfigIfAny();
  mapReadyPromise = new Promise((resolve) => {
    resolveMapReady = resolve;
  });

  // 新增：进入主应用时恢复显示退出应用按钮
  const exitBtn = $("exit-app-btn");
  if (exitBtn) exitBtn.classList.remove("hidden");

  if (isMobileMode) {
    const mobileMainApp = document.getElementById("mobile-main-app");
    const mobileLoginContainer = document.getElementById(
      "mobile-login-container",
    );
    const mobileAuthContainer = document.getElementById(
      "mobile-auth-login-container",
    );
    const mobileMultiApp = document.getElementById("mobile-multi-account-app");

    if (mobileMainApp) {
      mobileMainApp.classList.remove("hidden");
      console.log("[单账号模式] 移动端：显示 mobile-main-app");
    }
    if (mobileLoginContainer) mobileLoginContainer.classList.add("hidden");
    if (mobileAuthContainer) mobileAuthContainer.classList.add("hidden");
    if (mobileMultiApp) mobileMultiApp.classList.add("hidden");

    updateMobileNavVisibility(true, "single");

    switchMobileSinglePanel("mobile-control-panel");
    console.log("[单账号模式] 移动端：已默认激活 mobile-control-panel");

    $("main-app").classList.add("hidden");
    $("multi-account-app").classList.add("hidden");
    $("login-container").classList.add("hidden");
    $("auth-login-container").classList.add("hidden");
  } else {
    $("auth-login-container").classList.add("hidden");
    $("login-container").classList.add("hidden");
    $("main-app").classList.remove("hidden");
    $("main-app").classList.add("grid");
    console.log("[单账号模式] 桌面端：显示 main-app");
  }

  logMessage_Info("已进入单账号模式。");

  destroySingleMap();

  logMessage_Info("等待UI渲染稳定...");
  setTimeout(() => {
    logMessage_Info("UI稳定，开始初始化地图...");
    ensureActiveMapProviderRuntimeIfNeeded("主应用地图初始化")
      .then((isReady) => {
        if (!isReady) return;
        if (getActiveMapProvider() === "amap" && AMapInstance) {
          initMap(AMapInstance);
          ensureSingleControls();
        } else {
          initProviderMap("map-container", false);
          ensureSingleControls();
          if (resolveMapReady) {
            resolveMapReady(null);
          }
        }
      })
      .catch((e) => logMessage_Error("地图加载失败（延迟创建阶段）", e));
  }, 100);
}

function resetUI() {
  legacyBusinessGeneration++;
  // 新增：重置UI时恢复显示退出应用按钮
  const exitBtn = $("exit-app-btn");
  if (exitBtn) exitBtn.classList.remove("hidden");

  $("main-app").classList.add("hidden");
  $("main-app").classList.remove("grid");
  $("login-container").classList.remove("hidden");
  $("user-name-label").textContent = "姓名: NULL";
  $("user-id-label").textContent = "学号: NULL";
  const logoutBtn = $("logout-button");
  logoutBtn.classList.remove("!text-amber-500");
  logoutBtn.classList.add("!text-red-600");
  currentTasks = [];
  selectedTaskIndex = -1;
  currentUserData = {};
  currentRunData = {};
  singleRunProgressVisualActive = false;
  $("task-list").innerHTML = "";
  $("history-list").innerHTML = "";
  $("target-points-text").innerHTML = "";

  IS_OFFLINE = null;
  const uaLabel = $("ua-label");
  if (uaLabel) uaLabel.textContent = " (未加载) ";
  const uaBtn = $("random-ua-btn");
  if (uaBtn) uaBtn.disabled = false;

  try {
    const container = document.getElementById("map-container");
    if (container) container.classList.remove("drawing");
  } catch (_) {}
  isDrawing = false;
  isPathDrawing = false;
  leftMouseDown = false;
  pendingUnlockMap = false;
  draftPath = [];
  draftPathLngLat = [];
  pendingPoints = [];
  isUpdating = false;
  lastMouseMoveTime = 0;
  try {
    safeRemoveModalVisible();
  } catch (_) {}

  $("start-run-button").textContent = "开始执行";
  $("start-run-button").classList.remove("btn-danger");
  $("start-run-button").classList.add("btn-primary");
  $("start-all-button").textContent = "执行所有";
  $("start-all-button").classList.remove("btn-danger");
  $("start-all-button").classList.add("btn-secondary");

  stopBackgroundTaskPolling();

  updateDashboard();

  destroySingleMap();

  onUserChange();
}

function clearMapOverlays() {
  if (!map) return;
  removeSingleMapOverlay(polylines.recommended);
  polylines.recommended = [];
  removeSingleMapOverlay(polylines.draft);
  removeSingleMapOverlay(polylines.run);
  removeSingleMapOverlay(polylines.history);
  polylines.draft = polylines.run = polylines.history = null;
  amapRouteProgressSegments = null;
  removeSingleMapOverlay(markers);
  markers = [];
  if (runnerMarker) {
    removeSingleMapOverlay(runnerMarker);
    runnerMarker = null;
  }
  if (drawingInfoMarker) {
    removeSingleMapOverlay(drawingInfoMarker);
    drawingInfoMarker = null;
  }
}

function destroySingleMap() {
  try {
    if (window.mapCleanup) {
      window.mapCleanup();
      window.mapCleanup = null;
    }
    if (map && typeof map.destroy === "function") {
      map.destroy();
    }
    destroyProviderMapInstance("map-container");
    destroyProviderMapInstance("mobile-map-container");
  } catch (e) {
    logMessage_Warning("destroySingleMap warning:", e);
  } finally {
    map = null;
    polylines.recommended = [];
    polylines.draft = null;
    polylines.run = null;
    polylines.history = null;
    markers = [];
    runnerMarker = null;
    drawingInfoMarker = null;

    try {
      const container = document.getElementById("map-container");
      if (container) container.classList.remove("drawing");
    } catch (_) {}
    isDrawing = false;
    isPathDrawing = false;
    leftMouseDown = false;
    pendingUnlockMap = false;
    draftPath = [];
    draftPathLngLat = [];
    pendingPoints = [];
    isUpdating = false;
    lastMouseMoveTime = 0;

    try {
      safeRemoveModalVisible();
    } catch (_) {}
  }
}

$("user-combo").addEventListener("change", onUserChange);
$("username-entry").addEventListener("input", async (e) => {
  const loginBtn = $("login-button");
  if (loginBtn) {
    loginBtn.disabled = true;
  }

  try {
    const username = e.target.value.trim();
    $("password-entry").value = "";
    const userCombo = $("user-combo");
    const exists = [...userCombo.options].some((o) => o.value === username);
    userCombo.value = exists ? username : "";
    const data = await callPythonAPI("on_user_selected", username);
    if (data && data.password) $("password-entry").value = data.password;
    logMessage_Info("获取到的data.ua:", data ? data.ua : "null");
    const ua_data = data && data.ua ? data.ua : "(新用户将在登录时自动生成)";
    $("ua-label").textContent = ua_data;
    syncUAToMobile(ua_data);
    logMessage_Info("User ua label set to:", ua_data);
    pythonParams = data && data.params ? data.params : pythonParams;
    updateParamInputs($("params-container"), "param", pythonParams);
    const base = pythonParams.theme_base_color || "#7dd3fc";
    setBaseColor(base, base);
  } finally {
    if (loginBtn) {
      loginBtn.disabled = false;
    }
  }
});
$("random-ua-btn").addEventListener("click", async () => {
  const newUA = await callPythonAPI("generate_new_ua");
  $("ua-label").textContent = newUA;
  // ================同步UA到移动端标签====================
  syncUAToMobile(newUA);
});
$("login-button").addEventListener("click", async (e) => {
  if (!(await checkButtonPermission("login-button", "use_login_button"))) {
    return;
  }
  await onLogin();
});
$("logout-button").addEventListener("click", onLogout);
$("refresh-button").addEventListener("click", refreshTasks);
$("record-button").addEventListener("click", toggleRecordMode);
$("clear-button").addEventListener("click", () => clearCurrentPath(true));
$("process-button").addEventListener("click", processCurrentPath);
$("start-run-button").addEventListener("click", toggleRun);
$("start-all-button").addEventListener("click", toggleAllRuns);
$("export-button").addEventListener("click", exportTask);

// 移动端仅保留自动生成、清除和导出路径
if ($("mobile-auto-gen-button")) $("mobile-auto-gen-button").addEventListener("click", () => { const modal = $("auto-gen-modal"); if (modal) { modal.classList.remove("hidden"); modal.classList.add("flex"); document.body.classList.add("modal-visible"); } });
if ($("mobile-clear-button")) $("mobile-clear-button").addEventListener("click", () => clearCurrentPath(true));
if ($("mobile-export-button")) $("mobile-export-button").addEventListener("click", exportTask);

$("import-button").addEventListener("click", async (e) => {
  if (!(await checkButtonPermission("import-button", "use_import_button"))) {
    return;
  }
  await importTask();
});
$("show-user-details").addEventListener("click", (e) => {
  e.stopPropagation();
  showUserDetails();
});
$("show-task-details").addEventListener("click", (e) => {
  e.stopPropagation();
  showTaskDetails();
});
$("auto-gen-button").addEventListener("click", () => {
  $("auto-gen-modal").classList.remove("hidden");
  $("auto-gen-modal").classList.add("flex");
  document.body.classList.add("modal-visible");
});
$("cancel-gen-button").addEventListener("click", () => {
  $("auto-gen-modal").classList.add("hidden");
  $("auto-gen-modal").classList.remove("flex");
  safeRemoveModalVisible();
});
$("confirm-gen-button").addEventListener("click", onConfirmAutoGenerate);

$("show-notifications-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  showNotifications();
});

$("mark-all-read-btn").addEventListener("click", markAllAsRead);
$("refresh-notifications-btn").addEventListener("click", () =>
  refreshNotificationsUI(true, true),
);

$("multi-download-template-btn").addEventListener(
  "click",
  multi_downloadTemplate,
);
async function onConfirmAmapKey() {
  const input = $("amap-key-input");
  const provider = input.dataset.provider || getActiveMapProvider();
  const requirement = getMapProviderKeyRequirement(provider);
  const newKey = input.value.trim();
  if (!newKey) {
    // showModalAlert("API Key 不能为空！");
    swal.fire({
      title: "错误",
      text: "API Key 不能为空！",
      icon: "error",
    });
    return;
  }

  const btn = $("confirm-amap-key-btn");
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = `<span class="inline-block animate-spin mr-2">⏳</span>保存中...`;

  try {
    const mapProviderSessionUUID = getAuthenticatedSessionHeaderValue();
    let result = await callPythonAPI("save_map_provider_key", {
      provider: requirement.provider,
      api_key: newKey,
    });
    result = await hydrateMapProviderSecretsForLegacy(result, mapProviderSessionUUID);
    if (result.success) {
      syncMapProviderConfigFromInitialData(result);
      const modal = $("amap-key-modal");
      modal.classList.add("hidden");
      modal.classList.remove("flex");
      safeRemoveModalVisible();
      logMessage_Info(`${requirement.displayName} API Key已更新，正在尝试重新加载地图...`);
      try {
        await ensureActiveMapProviderRuntimeIfNeeded("保存 Key 后刷新");
        await ensureSingleMap();
      } catch (e) {
        logMessage_Error("保存Key后加载地图失败", e);
        logMessage_Info(
          "[错误] 新的API Key似乎无效，地图加载失败。请检查后重试。",
        );
        modal.classList.remove("hidden");
        modal.classList.add("flex");
        document.body.classList.add("modal-visible");
      }
    } else {
      // showModalAlert(`保存失败: ${result.message}`);
      swal.fire({
        title: "错误",
        text: `保存失败: ${result.message}`,
        icon: "error",
      });
    }
  } catch (e) {
    logMessage_Error("保存API Key时发生网络错误:", e);
    // showModalAlert(`保存失败: ${e.message}`);
    swal.fire({
      title: "错误",
      text: `保存失败: ${e.message}`,
      icon: "error",
    });
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

function bindImmediateRefreshForUserSelects() {
  const loginSelect = $("user-combo");
  const multiSelect = $("multi-config-user-select");
  const mobileMultiSelect = $("mobile-multi-config-user-select");

  if (loginSelect && !loginSelect._refreshBound) {
    loginSelect.addEventListener("focus", refreshUserList);
    loginSelect.addEventListener("click", refreshUserList);
    loginSelect._refreshBound = true;
  }

  if (multiSelect && !multiSelect._refreshBound) {
    multiSelect.addEventListener("focus", refreshUserList);
    multiSelect.addEventListener("click", refreshUserList);
    multiSelect._refreshBound = true;
  }

  if (mobileMultiSelect && !mobileMultiSelect._refreshBound) {
    mobileMultiSelect.addEventListener("focus", refreshUserList);
    mobileMultiSelect.addEventListener("click", refreshUserList);
    mobileMultiSelect._refreshBound = true;
  }
}
async function multi_downloadTemplate() {
  const result = await callPythonAPI("multi_download_import_template");
  if (!result || !result.success) {
    // showModalAlert(result?.message || "模板下载失败");
    swal.fire({
      title: "错误",
      text: result?.message || "模板下载失败",
      icon: "error",
    });
    return;
  }
  if (result.content && result.filename) {
    const binaryString = atob(result.content);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], {
      type: result.mimetype || "application/octet-stream",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    logMessage_Info(`模板已下载：${result.filename}`);
  }
}
async function refreshUserList() {
  // 如果已经显示了被踢出的遮罩，不再发送请求
  if (document.getElementById("logout-elsewhere-overlay")) {
    return;
  }
  if (isInNetworkErrorState) {
    return;
  }
  if (!sessionUUID || sessionUUID === "null" || sessionUUID.trim() === "") {
    return;
  }
  try {
    // 获取初始数据用于用户列表渲染，同时触发任务列表自动更新
    const initialData = await loadInitialData();
    syncMapProviderConfigFromInitialData(initialData);
    const users = Array.isArray(initialData?.users) ? initialData.users : [];

    const select = document.getElementById("user-combo");
    const multiSelect = document.getElementById("multi-config-user-select");
    const mobileMultiSelect = document.getElementById(
      "mobile-multi-config-user-select",
    );
    function updateSelect(selectElem, users) {
      if (!selectElem) return;
      const previousValue = selectElem.value;
      const previousScrollTop = selectElem.scrollTop;
      selectElem.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "(新用户/手动输入)";
      selectElem.appendChild(opt);

      users.forEach((u) => {
        const o = document.createElement("option");
        o.value = u;
        o.textContent = u;
        o.title = u;
        selectElem.appendChild(o);
      });
      if (users.includes(previousValue)) {
        selectElem.value = previousValue;
      } else {
        selectElem.value = "";
      }
      selectElem.scrollTop = previousScrollTop;
    }

    updateSelect(select, users);
    updateSelect(multiSelect, users);
    updateSelect(mobileMultiSelect, users);
  } catch (err) {
    logMessage_Error("刷新用户列表失败", err);
  }
}

startUserListPollingFallback();

async function onUserChange() {
  const loginBtn = $("login-button");
  if (loginBtn) {
    loginBtn.disabled = true;
  }

  try {
    const username = $("user-combo").value;
    const data = await callPythonAPI("on_user_selected", username);
    $("username-entry").value = username;
    $("password-entry").value = data.password || "";

    const uaText = data.ua || "(新用户将在登录时自动生成)";
    $("ua-label").textContent = uaText;
    // ========================================
    // 【移动端同步】
    // ========================================
    syncUAToMobile(uaText);

    pythonParams = data.params || pythonParams;
    updateParamInputs($("params-container"), "param", pythonParams);

    const base = pythonParams.theme_base_color || "#7dd3fc";
    setBaseColor(base, base, false); // 传入 false，不保存

    const style = pythonParams.theme_style || "default";
    setThemeStyle(style, false); // 传入 false，不保存

    if (sessionUUID && currentAuthUsername) {
      try {
        const response = await fetch("/auth/get_user_school_accounts", {
          method: "GET",
          headers: {
            "X-Session-ID": sessionUUID,
          },
        });

        if (response.ok) {
          const result = await response.json();

          if (result.success && result.accounts) {
            const accountData = result.accounts[username];

            let password = null;
            let ua = null;

            if (typeof accountData === "string") {
              password = accountData;
            } else if (
              typeof accountData === "object" &&
              accountData !== null
            ) {
              password = accountData.password;
              ua = accountData.ua;
            }

            if (password) {
              $("password-entry").value = password;

              logMessage_Info(
                `[用户选择] 已从 school_accounts 加载用户 ${username} 的密码`,
              );
            }

            if (ua) {
              $("ua-label").textContent = ua;
              syncUAToMobile(ua);
              logMessage_Info(
                `[用户选择] 已从 school_accounts 加载用户 ${username} 的UA`,
              );
            }
          }
        }
      } catch (error) {
        logMessage_Warning(
          `[用户选择] 无法加载 school_accounts: ${error.message}`,
        );
      }
    }
  } finally {
    if (loginBtn) {
      loginBtn.disabled = false;
    }
  }
}

async function onLogin() {
  logMessage_Info("[前端-登录] 开始登录流程...");
  const user = $("username-entry").value.trim();
  const pass = $("password-entry").value;

  logMessage_Info(`[前端-登录] 用户名: ${user}`);
  if (!user) {
    logMessage_Info("[前端-登录] 错误: 用户名为空");
    // showModalAlert("请输入用户名");
    swal.fire({
      title: "错误",
      text: "请输入用户名",
      icon: "error",
    });
    return;
  }

  const modeContext = captureLegacyBusinessContext(true);
  const uaBtn = $("random-ua-btn");
  if (uaBtn) uaBtn.disabled = false;

  const uaOnLoginScreen = $("ua-label")?.textContent || "";
  logMessage_Info(`[前端-登录] 当前UA: ${uaOnLoginScreen.substring(0, 50)}...`);

  setButtonLoading("login-button", true, "登录中...");

  logMessage_Info("[前端-登录] 调用后端API进行登录验证...");
  const mapProviderSessionUUID = getApiRequestSessionHeaderValue("login");
  let result = await callPythonAPI("login", user, pass);
  if (!isCurrentLegacyBusinessContext(modeContext)) return;
  if (result.success) {
    applyLegacyBusinessMode(result, modeContext);
    // 学校账号登录不会结束管理员查看链。
    if (!getStoredAdminReturnOriginSession()) clearAdminReturnOriginState("重新登录");
    try {
      result = await hydrateMapProviderSecretsForLegacy(
        result,
        mapProviderSessionUUID,
      );
    } catch (error) {
      logMessage_Error("[前端-登录] 地图密钥运行时解密失败:", error);
    }
    if (!isCurrentLegacyBusinessContext(modeContext)) return;
    await syncThemeFromServer(result.theme, result.theme_style);
    if (!isCurrentLegacyBusinessContext(modeContext)) return;
    logMessage_Info("[前端-登录] ✓ 登录成功！");
    showButtonSuccess("login-button", "登录成功");
    syncMapProviderConfigFromInitialData(result);
    if (getActiveMapProviderApiKey()) {
      logMessage_Info(`[前端-登录] 加载${getMapProviderDisplayName()}地图配置...`);
      try {
        await ensureActiveMapProviderRuntimeIfNeeded("登录成功");
        logMessage_Info("[前端-登录] ✓ 地图加载成功");
      } catch (e) {
        logMessage_Error("[前端-登录] ✗ 地图加载失败:", e);
      }
    } else {
      showMissingMapProviderKeyModal(getActiveMapProvider());
    }

    if (!isCurrentLegacyBusinessContext(modeContext)) return;
    logMessage_Info("[前端-登录] 显示主应用界面...");
    showMainApp();
    $("loading-overlay").classList.add("hidden");
    currentUserData = result.userInfo;
    // 从API返回的result中获取group字段，而不是auth_group
    // 原因：后端登录API（main.py第16868行）返回的字段名是"group"，不是"auth_group"
    // 错误使用auth_group会导致currentUserData.group总是默认为"user"
    // 这会使管理员权限验证失败（如第5326行的isAdmin判断）
    // currentUserData.group = result.group || "user";

    // 添加调试日志，验证 group 字段是否正确设置
    // console.log('[登录成功] currentUserData.group =', currentUserData.group);
    // console.log('[登录成功] result.group =', result.group);
    // console.log('[登录成功] currentUserData 完整数据:', currentUserData);
    // logMessage_Info(
    //   `[登录成功] 权限组设置为: ${currentUserData.group}`
    // );

    currentSessionUA = uaOnLoginScreen;
    const name = currentUserData.name || "";
    $("user-name-label").textContent = `姓名: ${name}`;
    $("user-id-label").textContent = `学号: ${currentUserData.student_id}`;
    logMessage_Info(
      `[前端-登录] 用户信息已更新: ${name} (${currentUserData.student_id})`,
    );

    logMessage_Info("[前端-登录] 更新仪表盘...");
    updateDashboard();

    logMessage_Info("[前端-登录] 刷新任务列表...");
    await refreshTasks();

    logMessage_Info("[前端-登录] 获取通知...");
    const notificationBadge = $("notification-badge");
    if (notificationBadge) {
      notificationBadge.classList.add("hidden");
    }
    if (
      result.cached_notifications &&
      result.cached_notifications.notices.length > 0
    ) {
      logMessage_Info(
        `使用登录时预加载的 ${result.cached_notifications.notices.length} 条通知`,
      );
      if (result.cached_notifications.unreadCount > 0) {
        notificationBadge.textContent =
          result.cached_notifications.unreadCount > 9
            ? "9+"
            : result.cached_notifications.unreadCount;
        notificationBadge.classList.remove("hidden");
      }
      window.currentNotifications = result.cached_notifications.notices;
    } else {
      await fetchNotifications();
    }

    const base = pythonParams.theme_base_color || "#7dd3fc";
    setBaseColor(base, base);
    const adminBtn = $("show-admin-panel");
    if (adminBtn) adminBtn.classList.remove("hidden");
    const adminBtnLogin = $("show-admin-panel-login");
    if (adminBtnLogin) adminBtnLogin.classList.remove("hidden");
    $("loading-overlay").classList.add("hidden");
    logMessage_Info("[前端-登录] ✓ 登录流程完成！");
    return true;
  } else {
    logMessage_Info(`[前端-登录] ✗ 登录失败: ${result.message}`);
    setButtonLoading("login-button", false);
    showButtonError("login-button", "登录失败");
    // showModalAlert(result.message, "登录失败");
    swal.fire({
      title: "错误",
      text: result.message,
      icon: "error",
    });
    return false;
  }
}

async function onLogout() {
  await callPythonAPI("logout");
  resetLegacyRunnerExecution();
  currentSessionUA = "";
  resetUI();

  if (refreshUserListInterval) {
    clearInterval(refreshUserListInterval);
    refreshUserListInterval = null;
    logMessage_Info("refreshUserList interval cleared on logout.");
  }

  await new Promise((resolve) => setTimeout(resolve, 500));
  loadAdminSessions_inline();
}

async function refreshTasks() {
  if (isRefreshingTasks) {
    return;
  }
  isRefreshingTasks = true;

  const btn = $("refresh-button");
  if (btn) btn.disabled = true;

  try {
    const taskResult = await callPythonAPI("load_tasks");
    if (taskResult && taskResult.success) {
      currentTasks = taskResult.tasks;
      renderTaskList();
      return;
    }

    await new Promise((r) => setTimeout(r, 300));
    const retry = await callPythonAPI("load_tasks");
    if (retry && retry.success) {
      currentTasks = retry.tasks;
      renderTaskList();

      await fetchNotifications();
    } else {
      logMessage_Info("加载任务列表失败，请点击左侧“刷新”重试。");
    }
  } finally {
    isRefreshingTasks = false;
    if (btn) btn.disabled = false;
  }
}

function renderTaskList() {
  const taskListDiv = $("task-list");
  taskListDiv.innerHTML = "";
  if (currentTasks.length === 0) {
    taskListDiv.innerHTML = `<div class="text-slate-400 text-center py-10">暂无任务</div>`;
    return;
  }
  currentTasks.forEach((task, index) => {
    const item = document.createElement("div");
    const pathStatus =
      task.run_coords?.length > 0
        ? "已生成"
        : task.draft_coords?.length > 0
          ? "草稿"
          : "无路径";
    let statusClass = "text-amber-600",
      statusText = "未完成",
      statusIcon = "🕒";

    if (task.status == 1) {
      statusClass = "text-emerald-600";
      statusText = "已完成";
      statusIcon = "✅";
    }

    if (task.info_text === "已过期") {
      statusClass = "text-red-600";
      statusText = "已过期";
      statusIcon = "⛔";
    }

    if (!(task.status == 1)) {
      if (
        typeof task.info_text === "string" &&
        task.info_text.startsWith("开始于")
      ) {
        statusClass = "text-slate-600";
        statusText = "未开始";
        statusIcon = "⏳";
      }
    }

    item.className =
      "p-3 rounded-xl cursor-pointer border border-transparent transition-colors duration-200 hover:bg-white/70";
    item.innerHTML = `
      <div class="flex items-center gap-3">
        <p class="font-bold text-slate-700 text-sm truncate">${
          task.run_name
        }</p>
      </div>
      <div class="flex justify-between items-center mt-2 text-xs">
        <span class="font-semibold ${statusClass} flex items-center gap-1">${statusIcon} ${statusText}</span>
        <span class="text-slate-500">${task.info_text || ""}</span>
        <span class="badge">${pathStatus}</span>
      </div>
    `;
    item.dataset.index = index;
    if (task.status === 1) item.classList.add("opacity-60");
    if (index === selectedTaskIndex) item.classList.add("selected");
    item.addEventListener("click", () => selectTask(index));
    taskListDiv.appendChild(item);
  });

  renderMobileTaskList();
}
function renderMobileTaskList() {
  const mobileTaskListDiv = $("mobile-task-list");
  if (!mobileTaskListDiv) return;
  mobileTaskListDiv.innerHTML = "";

  const taskCountElem = $("mobile-task-count");
  if (taskCountElem) {
    taskCountElem.textContent = `${currentTasks.length} 个任务`;
  }

  if (currentTasks.length === 0) {
    mobileTaskListDiv.innerHTML = `<p class="text-slate-400 text-center py-8 text-sm">暂无任务</p>`;
    return;
  }

  currentTasks.forEach((task, index) => {
    const item = document.createElement("div");

    let statusClass = "text-amber-600";
    let statusText = "未完成";
    let statusIcon = "🕒";

    if (task.status == 1) {
      statusClass = "text-emerald-600";
      statusText = "已完成";
      statusIcon = "✅";
    }

    if (task.info_text === "已过期") {
      statusClass = "text-red-600";
      statusText = "已过期";
      statusIcon = "⛔";
    }

    if (!(task.status == 1)) {
      if (
        typeof task.info_text === "string" &&
        task.info_text.startsWith("开始于")
      ) {
        statusClass = "text-slate-600";
        statusText = "未开始";
        statusIcon = "⏳";
      }
    }

    item.className =
      "bg-white rounded-lg p-3 border border-slate-200 cursor-pointer transition-all duration-200 hover:shadow-md active:scale-98 w-full max-w-full break-words";
    item.id = `Mobile_Task_List_Sub_project${task.errand_id}`;

    item.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-2 w-full">
        <p class="font-semibold text-slate-800 text-sm break-words w-full">
          ${task.run_name}
        </p>
      </div>

      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between text-xs w-full gap-1">
        <span class="font-medium ${statusClass} flex items-center gap-1">
          <span>${statusIcon}</span>
          <span>${statusText}</span>
        </span>

        <span class="text-slate-500 break-words w-full sm:w-auto">
          ${task.info_text || ""}
        </span>
      </div>
    `;

    item.dataset.index = index;

    if (task.status === 1) {
      item.style.opacity = "0.6";
    }

    if (index === selectedTaskIndex) {
      item.style.backgroundColor = "#eff6ff";
      item.style.border = "2px solid #3b82f6";
      item.style.borderLeft = "6px solid #2563eb";
      item.style.boxShadow =
        "0 4px 6px -1px rgba(59, 130, 246, 0.2), 0 2px 4px -1px rgba(59, 130, 246, 0.1)";
      item.style.transform = "scale(1.01)";
      item.style.zIndex = "10";
      item.style.position = "relative";
      item.querySelectorAll("p, span").forEach((el) => {
        if (el.classList.contains("text-slate-800")) el.style.color = "#1e40af";
      });
    } else {
      item.style.backgroundColor = "#ffffff";
      item.style.border = "1px solid #e2e8f0";
      item.style.borderLeft = "1px solid #e2e8f0";
      item.style.boxShadow = "none";
      item.style.transform = "none";
      item.style.zIndex = "auto";
      item.style.position = "static";
      item.querySelectorAll("p, span").forEach((el) => {
        if (el.classList.contains("text-slate-800")) el.style.color = "";
      });
    }

    item.addEventListener("click", async () => {
      if (index === selectedTaskIndex) {
        selectTask(index);
        return;
      }

      const statusRes = await callPythonAPI_raw(
        "/api/background_task/status",
        "GET",
        null,
      );

      const isBackendRunning =
        statusRes.success &&
        statusRes.task_status &&
        statusRes.task_status.status === "running";

      if (isBackendRunning) {
        swal.fire({
          title: "错误",
          text: "任务正在运行中，禁止切换任务！",
          icon: "error",
        });
        mobileTaskRunning = true;
        updateMobileTaskUI("运行中", "任务执行中");
        return;
      }

      selectTask(index);
    });

    mobileTaskListDiv.appendChild(item);
  });
}

function renderMobileCheckpointsList() {
  const checkpointsListDiv = $("mobile-checkpoints-list");
  const taskInfoDiv = $("mobile-checkpoints-task-info");
  if (!checkpointsListDiv) return;

  if (
    selectedTaskIndex === -1 ||
    !currentRunData ||
    !currentRunData.target_points ||
    currentRunData.target_points.length === 0
  ) {
    checkpointsListDiv.innerHTML =
      '<p class="text-slate-400 text-center py-8 text-sm">请先选择一个有打卡点的任务</p>';

    if (taskInfoDiv) {
      if (selectedTaskIndex === -1) {
        taskInfoDiv.textContent = "请先选择一个任务以查看打卡点";
        // showModalAlert("请先在任务列表中选择一个任务", "警告");
        swal.fire({
          title: "警告",
          text: "请先在任务列表中选择一个任务",
          icon: "warning",
        });
      } else {
        taskInfoDiv.textContent = "当前任务没有打卡点";
      }
    }
    return;
  }

  if (taskInfoDiv) {
    const taskName = currentTasks[selectedTaskIndex]?.run_name || "未知任务";
    taskInfoDiv.textContent = `任务: ${taskName}`;
  }
  // showModalAlert(
  //   "正在加载打卡点列表，请稍候...",
  //   "信息",
  // );

  checkpointsListDiv.innerHTML = "";

  const targetPoints = currentRunData.target_points;
  const targetNames = (currentRunData.target_point_names || "").split("|");
  const currentSequence = currentRunData.target_sequence || 1;

  targetPoints.forEach((point, index) => {
    const item = document.createElement("div");

    const seq = index + 1;
    const name = targetNames[index] || `打卡点${seq}`;
    const [lon, lat] = point;

    const isReached = currentSequence > seq;
    const isCurrent = currentSequence === seq;
    let statusClass = "bg-white border-slate-200";
    let statusBadge =
      '<span class="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">未到达</span>';

    if (isReached) {
      statusClass = "bg-green-50 border-green-200";
      statusBadge =
        '<span class="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-600 flex items-center gap-1"><span>✓</span><span>已到达</span></span>';
    } else if (isCurrent) {
      statusClass = "bg-blue-50 border-blue-400 ring-2 ring-blue-300";
      statusBadge =
        '<span class="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-600 flex items-center gap-1"><span>🎯</span><span>目标</span></span>';
    }
    item.className = `${statusClass} rounded-lg p-3 border transition-all duration-200 cursor-pointer hover:shadow-md`;
    item.innerHTML = `
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-center gap-2 flex-1">
              <span class="text-lg font-bold ${
                isCurrent
                  ? "text-blue-600"
                  : isReached
                    ? "text-green-600"
                    : "text-slate-400"
              }">
                ${seq}
              </span>
              <div class="flex-1">
                <p class="font-semibold text-slate-800 text-sm">${name}</p>
                <p class="text-xs text-slate-500 mt-1">坐标: ${lat.toFixed(
                  6,
                )}, ${lon.toFixed(6)}</p>
              </div>
            </div>
            ${statusBadge}
          </div>
        `;
    // item.addEventListener("click", () => {
    //   if (window.map) {
    //     window.map.setCenter([lon, lat]);
    //     window.map.setZoom(16);
    //     showModalAlert(`已定位到 ${name}`, "成功");
    //   } else {
    //     showModalAlert("地图未初始化", "错误");
    //   }
    // });
    checkpointsListDiv.appendChild(item);
  });
}
let pollingTaskMapRequest = 0;
let pollingTaskMapPending = null;
function getLegacyTaskMapSnapshotKey(taskIndex) {
  return `${sessionUUID}:${legacyRunnerExecutionState.id}:${taskIndex}`;
}
async function forceLoadTaskDataForPolling(taskIndex, taskStatus = null) {
  if (taskIndex < 0 || taskIndex >= currentTasks.length) return false;
  if (taskStatus?.route_ready === false) {
    pollingTaskMapRequest++;
    pollingTaskMapPending = null;
    legacyRunnerExecutionState.mapSnapshotKey = "";
    const hadGeometry = currentRunData?.run_coords?.length;
    currentRunData = currentRunData?.task_index === taskIndex
      ? { ...currentRunData, run_coords: [], status: taskStatus.status }
      : { task_index: taskIndex, run_coords: [], status: taskStatus.status };
    if (hadGeometry) drawOnMap();
    return true;
  }
  const snapshotKey = getLegacyTaskMapSnapshotKey(taskIndex);
  if (currentRunData?.task_index === taskIndex && currentRunData.run_coords?.length && legacyRunnerExecutionState.mapSnapshotKey === snapshotKey) return true;
  if (pollingTaskMapPending?.key === snapshotKey && pollingTaskMapPending.request === pollingTaskMapRequest) {
    if (taskStatus?.status) pollingTaskMapPending.status = taskStatus.status;
    return pollingTaskMapPending.promise;
  }
  const request = ++pollingTaskMapRequest;
  const requestSession = sessionUUID;
  const requestExecution = legacyRunnerExecutionState.id;
  const pending = { key: snapshotKey, request, status: taskStatus?.status, promise: null };
  pollingTaskMapPending = pending;

  logMessage_Info(`[Polling] 强制加载任务 #${taskIndex} 的数据...`);
  pending.promise = (async () => {
    try {
      const result = await callPythonAPI("get_task_map_snapshot", taskIndex);
      if (
        request !== pollingTaskMapRequest ||
        requestSession !== sessionUUID || requestExecution !== legacyRunnerExecutionState.id ||
        selectedTaskIndex !== taskIndex
      ) return false;
      if (result.success) {
        const details = { ...result.details, task_index: taskIndex };
        if (pending.status) details.status = pending.status;
        if (details.target_sequence != null) details.target_sequence = Number(details.target_sequence) + 1;
        if (currentRunData?.task_index === taskIndex && Number(currentRunData.current_point_index) > 0 && Number(currentRunData.current_point_index) >= Number(details.current_point_index ?? -1)) {
          for (const field of ["current_point_index", "point_index", "current_position", "current_lon", "current_lat", "distance_covered_m", "current_distance", "target_sequence", "checked_targets_count"]) {
            if (currentRunData[field] != null) details[field] = currentRunData[field];
          }
        }
        currentRunData = details;
        legacyRunnerExecutionState.mapSnapshotKey = result.route_ready === true || (result.route_ready == null && currentRunData.run_coords?.length) ? snapshotKey : "";
        updateDashboard();
        drawOnMap();
        loadHistory(taskIndex);
        singleTotalPoints = currentRunData.run_coords?.length || 0;
        singleProcessedPoints = Math.max(0, Math.min(singleTotalPoints, Math.floor(Number(currentRunData.current_point_index) || 0)));
        updateSingleProgress(Math.floor(singleProcessedPoints * 100 / Math.max(1, singleTotalPoints)), `${singleProcessedPoints} / ${singleTotalPoints} 点`);
        return true;
      } else {
        logMessage_Error(`[Polling] 强制加载任务数据失败: ${result.message}`);
      }
    } catch (e) {
      logMessage_Error(`[Polling] 强制加载任务时出错: ${e}`);
    } finally {
      if (pollingTaskMapPending === pending) pollingTaskMapPending = null;
    }
    return false;
  })();
  return pending.promise;
}

async function selectTask(index, Update_Dashboard = true) {
  logMessage_Info(`[任务选择] 开始选择任务，索引: ${index}`, "DEBUG");
  logMessage_Info(`[前端-任务选择] 选择任务 #${index}`);
  if (backgroundTaskPollInterval && selectedTaskIndex !== index) {
    logMessage_Warning("任务执行中，无法切换任务！请先停止当前任务。");
    // showModalAlert("任务执行中，无法切换任务！请先停止当前任务。");
    swal.fire({
      title: "错误",
      text: "任务执行中，无法切换任务！请先停止当前任务。",
      icon: "error",
    });
    return;
  }

  if (isDrawing) {
    logMessage_Info("请先结束当前路径绘制！", "WARN");
    return;
  }

  if (selectedTaskIndex === index) {
    logMessage_Info(`[任务选择] 任务已选中，无需重复选择: ${index}`, "DEBUG");
    return;
  }

  const taskListDiv = $("task-list");
  if (selectedTaskIndex > -1 && taskListDiv.children[selectedTaskIndex]) {
    taskListDiv.children[selectedTaskIndex].classList.remove("selected");
    logMessage_Info(
      `[任务选择] 取消选中上一个任务: ${selectedTaskIndex}`,
      "DEBUG",
    );
  }

  selectedTaskIndex = index;

  if (taskListDiv.children[selectedTaskIndex]) {
    taskListDiv.children[selectedTaskIndex].classList.add("selected");
    logMessage_Info(`[任务选择] 高亮显示当前任务: ${index}`, "DEBUG");
  }

  if (isMobileMode) {
    renderMobileTaskList();
  }

  const selectedTask = currentTasks[index];
  if (selectedTask && selectedTask.info_text === "离线") {
    logMessage_Info(`[任务选择] 离线模式任务，使用本地数据`, "INFO");
    currentRunData = selectedTask;
    if (Update_Dashboard) {
      updateDashboard();
    }
    drawOnMap();
    loadHistory(index);
    singleProcessedPoints = 0;
    singleTotalPoints = currentRunData.run_coords?.length || 0;
    updateSingleProgress(0, "0 / " + singleTotalPoints + " 点");
    logMessage_Info(
      `[任务选择] ✓ 离线任务加载完成，总点数: ${singleTotalPoints}`,
      "INFO",
    );
  } else {
    logMessage_Info(`[任务选择] 在线模式，从后端获取任务详情...`, "INFO");
    const result = await callPythonAPI("get_task_details", index);

    if (result.success) {
      logMessage_Info(`[任务选择] ✓ 任务详情获取成功`, "INFO");
      currentRunData = result.details;
      updateDashboard();

      drawOnMap();
      if (isMobileMode && window.mobile_map_panel_initialize_mark) {
        logMessage_Info(
          "[移动端] 地图面板已初始化，正在将任务打卡点绘制到地图上...",
        );

        switchMobileSinglePanel("mobile-map-panel");

        setTimeout(function () {
          drawOnMap();
        }, 400);
        // setTimeout(function () {
        //   drawOnMap();
        // }, 400);

        // switchMobileSinglePanel("mobile-task-panel", (showalert = false));
      }

      loadHistory(index);
      singleProcessedPoints = 0;
      singleTotalPoints = currentRunData.run_coords?.length || 0;
      updateSingleProgress(0, "0 / " + singleTotalPoints + " 点");
      logMessage_Info(
        `[任务选择] ✓ 在线任务加载完成，总点数: ${singleTotalPoints}`,
        "INFO",
      );
    } else {
      logMessage_Info(
        `[任务选择] ✗ 获取任务详情失败: ${result.message}`,
        "ERROR",
      );
      logMessage_Info(result.message);
    }
  }
}

$("multi-account-btn").addEventListener("click", async (e) => {
  if (
    !(await checkButtonPermission(
      "multi-account-btn",
      "use_multi_account_button",
    ))
  ) {
    return;
  }
  await switchToMultiMode();
});
$("exit-multi-mode-btn").addEventListener("click", exitMultiMode);
$("multi-start-all-btn").addEventListener("click", multi_startAll);
$("multi-stop-all-btn").addEventListener("click", multi_stopAll);
$("multi-load-all-from-config-btn").addEventListener(
  "click",
  multi_loadAllFromConfig,
);
$("multi-add-from-config-btn").addEventListener("click", multi_addFromConfig);
$("multi-import-excel-btn").addEventListener("click", multi_importFromExcel);
$("multi-expand-btn").addEventListener("click", openMultiAccountExpandedView);
$("multi-export-excel-btn").addEventListener("click", multi_exportToExcel);
$("multi-remove-all-btn").addEventListener("click", () => multi_removeAll());
$("multi-remove-selected-btn").addEventListener("click", () => multi_removeSelected());
$("multi-refresh-all-btn").addEventListener("click", multi_refreshAll);
$("multi-select-all-check").addEventListener("change", multi_toggleSelectAll);
$("multi-start-selected-btn").addEventListener("click", multi_startSelected);
$("multi-stop-selected-btn").addEventListener("click", multi_stopSelected);
$("multi-refresh-selected-btn").addEventListener(
  "click",
  multi_refreshSelected,
);

$("admin-tab-users_modal")?.addEventListener("click", () =>
  switchAdminTab("users"),
);
$("admin-tab-groups_modal")?.addEventListener("click", () =>
  switchAdminTab("groups"),
);
$("admin-tab-logs_modal")?.addEventListener("click", () =>
  switchAdminTab("logs"),
);
$("admin-tab-health_modal")?.addEventListener("click", () =>
  switchAdminTab("health"),
);
$("admin-tab-profile_modal")?.addEventListener("click", () =>
  switchAdminTab("profile"),
);
$("admin-tab-sessions_modal")?.addEventListener("click", () =>
  switchAdminTab("sessions"),
);
$("admin-tab-messages_modal")?.addEventListener("click", () =>
  switchAdminTab("messages"),
);
$("admin-tab-ipban_modal")?.addEventListener("click", () =>
  switchAdminTab("ipban"),
);
$("admin-tab-sms_modal")?.addEventListener("click", () =>
  switchAdminTab("sms"),
);

const loginTabBtn = $("log-tab-login");
if (loginTabBtn) {
  loginTabBtn.addEventListener("click", () => {
    loginTabBtn.classList.add("text-sky-600", "border-sky-600");
    loginTabBtn.classList.remove("text-slate-400", "border-transparent");

    const auditTabBtn = $("log-tab-audit");
    if (auditTabBtn) {
      auditTabBtn.classList.remove("text-sky-600", "border-sky-600");
      auditTabBtn.classList.add("text-slate-400", "border-transparent");
    }

    const loginContent = $("log-login-content");
    const auditContent = $("log-audit-content");
    if (loginContent) loginContent.classList.remove("hidden");
    if (auditContent) auditContent.classList.add("hidden");

    const username = $("current-log-username")?.textContent;
    if (username && username !== "N/A") {
      loadUserLoginLogs(username);
    }
  });
}
const auditTabBtn = $("log-tab-audit");
if (auditTabBtn) {
  auditTabBtn.addEventListener("click", () => {
    auditTabBtn.classList.add("text-sky-600", "border-sky-600");
    auditTabBtn.classList.remove("text-slate-400", "border-transparent");
    const loginTabBtn = $("log-tab-login");
    if (loginTabBtn) {
      loginTabBtn.classList.remove("text-sky-600", "border-sky-600");
      loginTabBtn.classList.add("text-slate-400", "border-transparent");
    }
    const loginContent = $("log-login-content");
    const auditContent = $("log-audit-content");
    if (loginContent) loginContent.classList.add("hidden");
    if (auditContent) auditContent.classList.remove("hidden");

    const username = $("current-log-username")?.textContent;
    if (username && username !== "N/A") {
      loadUserAuditLogs(username);
    }
  });
}
$("admin-refresh-messages_modal")?.addEventListener("click", loadMessages);
const guestWarningCloseBtn = $("guest-warning-close-btn");
const guestWarningOverlay = $("guest_warning_overlay");
if (guestWarningCloseBtn) {
  guestWarningCloseBtn.addEventListener("click", () => {
    const guestToast = $("guest-warning-toast");
    if (guestToast) {
      guestToast.classList.add("hidden");
    }
    if (guestWarningOverlay) {
      guestWarningOverlay.classList.add("hidden");
    }
  });
}
if (guestWarningOverlay) {
  guestWarningOverlay.addEventListener("click", () => {
    const guestToast = $("guest-warning-toast");
    if (guestToast) {
      guestToast.classList.add("hidden");
    }
    guestWarningOverlay.classList.add("hidden");
  });
}
async function switchToMultiMode() {
  $("multi-account-count").textContent = 0;

  // 新增：进入多账号模式时恢复显示退出应用按钮
  const exitBtn = $("exit-app-btn");
  if (exitBtn) exitBtn.classList.remove("hidden");

  stopBackgroundTaskPolling();
  try {
    await callPythonAPI_raw("/api/background_task/stop", "POST", null);
  } catch (_) {}
  onRunStopped();
  applyPendingMapProviderConfigIfAny();

  const result = await callPythonAPI("enter_multi_account_mode");
  if (!result.success) return;
  if (isMobileMode) {
    if (typeof destroyMobileSingleMap === "function") {
      destroyMobileSingleMap();
      console.log("[切换模式] 移动端：已销毁单账号地图");
    }
    const mobileLoginContainer = document.getElementById(
      "mobile-login-container",
    );
    const mobileMultiApp = document.getElementById("mobile-multi-account-app");
    const mobileMainApp = document.getElementById("mobile-main-app");

    if (mobileLoginContainer) mobileLoginContainer.classList.add("hidden");
    if (mobileMainApp) mobileMainApp.classList.add("hidden");
    if (mobileMultiApp) {
      mobileMultiApp.classList.remove("hidden");
      switchMobilePanel("mobile-multi-control-panel", "multi");
      console.log("[切换模式] 移动端：显示 mobile-multi-account-app");
    }
    updateMobileNavVisibility(true, "multi");
    $("login-container").classList.add("hidden");
    $("main-app").classList.add("hidden");
    $("multi-account-app").classList.add("hidden");
  } else {
    $("login-container").classList.add("hidden");
    $("main-app").classList.add("hidden");
    $("multi-account-app").classList.remove("hidden");
    $("multi-account-app").classList.add("grid");
    console.log("[切换模式] 桌面端：显示 multi-account-app");
  }

  document.body.classList.remove("modal-visible");
  try {
    await ensureActiveMapProviderRuntimeIfNeeded("进入多账号模式");
  } catch (e) {
    logMessage_Error("地图未就绪，无法进入多账号地图", e);
    return;
  }
  if (!multiAccountMap && getActiveMapProvider() === "amap" && AMapInstance) {
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
      const z = multiAccountMap.getZoom();
      $("multi-zoom-level").textContent = String(z.toFixed(1));
    });

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
  } else if (getActiveMapProvider() !== "amap") {
    initProviderMap("multi-map-container", true);
    ensureMultiControls();
  }

  const configUsers = await callPythonAPI("multi_get_all_config_users");
  const select = $("multi-config-user-select");
  const mobileSelect = $("mobile-multi-config-user-select");

  const populateConfigUsers = (sel) => {
    if (!sel) return;
    sel.innerHTML = '<option value="">(新用户/手动输入)</option>';
    configUsers.users.forEach((u) => {
      const opt = document.createElement("option");
      opt.value = opt.textContent = u;
      sel.appendChild(opt);
    });
  };

  populateConfigUsers(select);
  populateConfigUsers(mobileSelect);
  const container = $("multi-global-params-container");
  container.innerHTML = "";
  createParamInputs(container, "multi-param", onGlobalParamChange);
  pythonParams = result.params;
  updateParamInputs(container, "multi-param", pythonParams);

  await callPythonAPI(
    "set_multi_run_only_incomplete",
    document.getElementById("multi-run-only-incomplete-check").checked,
  );
  bindImmediateRefreshForUserSelects();

  updateMultiGlobalButtons(true, true);

  const desktopCheckbox = document.getElementById(
    "multi-run-only-incomplete-check",
  );
  if (desktopCheckbox) {
    desktopCheckbox.removeEventListener("change", updateAllAccountsStatusText);
    desktopCheckbox.addEventListener("change", updateAllAccountsStatusText);
    console.log('[事件监听器] 已为桌面端"仅执行未完成"复选框绑定change事件');
  } else {
    console.warn(
      '[事件监听器] 未找到桌面端"仅执行未完成"复选框 (multi-run-only-incomplete-check)',
    );
  }
  const mobileCheckbox = document.getElementById(
    "mobile-multi-only-incomplete-check",
  );
  if (mobileCheckbox) {
    mobileCheckbox.removeEventListener("change", updateAllAccountsStatusText);
    mobileCheckbox.addEventListener("change", updateAllAccountsStatusText);

    console.log('[事件监听器] 已为移动端"仅执行未完成"复选框绑定change事件');
  } else {
    console.warn(
      '[事件监听器] 未找到移动端"仅执行未完成"复选框 (mobile-multi-only-incomplete-check)',
    );
  }
  const pcCheck = document.getElementById("multi-run-only-incomplete-check");
  const mbCheck = document.getElementById("mobile-multi-only-incomplete-check");

  // 定义新的处理函数：同步状态到后端并刷新
  const handleIncompleteCheckChange = async (e) => {
    const isChecked = e.target.checked;

    // 1. 同步 PC 和 移动端 复选框状态
    if (pcCheck && pcCheck !== e.target) pcCheck.checked = isChecked;
    if (mbCheck && mbCheck !== e.target) mbCheck.checked = isChecked;

    // 2. 立即在前端更新 UI 显示（提供即时反馈）
    updateAllAccountsStatusText();

    // 3. 同步配置到后端 (不需要等待刷新，直接使用缓存更新状态)
    try {
      console.log(`[设置同步] 正在同步 '仅执行未完成' 设置: ${isChecked}`);
      const result = await callPythonAPI(
        "set_multi_run_only_incomplete",
        isChecked,
      );
      // 后端已用缓存任务按新开关重算 summary/status_text；立即重渲染，
      // 否则「可跑 / 过期 / 未开始」这些数字会停留在旧规则的结果上。
      if (result && Array.isArray(result.accounts)) {
        renderMultiAccountList(result.accounts);
      } else {
        updateAllAccountsStatusText();
      }
    } catch (err) {
      console.error("[设置同步] 同步失败:", err);
    }
  };

  if (pcCheck) {
    // 移除旧的监听器引用（如果有）
    pcCheck.removeEventListener("change", updateAllAccountsStatusText);
    // 移除可能存在的自身引用（防止多次绑定）
    pcCheck.removeEventListener("change", handleIncompleteCheckChange);
    // 绑定新处理函数
    pcCheck.addEventListener("change", handleIncompleteCheckChange);
  }
  if (mbCheck) {
    mbCheck.removeEventListener("change", updateAllAccountsStatusText);
    mbCheck.removeEventListener("change", handleIncompleteCheckChange);
    mbCheck.addEventListener("change", handleIncompleteCheckChange);
  }

  // ========== 处理 "忽略任务具体时间" 复选框变化 ==========
  // 获取桌面端和移动端的 ignore_task_time 复选框元素
  const pcIgnoreTimeCheck = document.getElementById(
    "multi-param-ignore_task_time",
  );
  // const mobileIgnoreTimeCheck = document.getElementById("mobile-multi-param-ignore_task_time");

  // 定义处理函数：当用户勾选/取消"忽略任务具体时间"时触发
  const handleIgnoreTimeChange = () => {
    // 根据当前运行模式（移动端/桌面端）读取对应复选框的当前状态
    // const isChecked = typeof isMobileMode !== "undefined" && isMobileMode && mobileIgnoreTimeCheck
    //   ? mobileIgnoreTimeCheck.checked  // 移动端模式：读取移动端复选框
    //   : (pcIgnoreTimeCheck ? pcIgnoreTimeCheck.checked : true); // 桌面端模式或移动端复选框不存在：读取桌面端复选框（默认true）
    const isChecked = pcIgnoreTimeCheck ? pcIgnoreTimeCheck.checked : true;
    // 同步两个复选框的状态（确保桌面端和移动端保持一致）
    if (pcIgnoreTimeCheck) pcIgnoreTimeCheck.checked = isChecked;
    if (mobileIgnoreTimeCheck) mobileIgnoreTimeCheck.checked = isChecked;

    // 立即更新所有账号的状态文本（根据新的 ignore_task_time 设置重新计算可执行任务数）
    updateAllAccountsStatusText();
  };

  // 为桌面端复选框绑定 change 事件监听器
  if (pcIgnoreTimeCheck) {
    // 先移除可能存在的旧监听器（防止重复绑定）
    pcIgnoreTimeCheck.removeEventListener("change", handleIgnoreTimeChange);
    // 绑定新的监听器
    pcIgnoreTimeCheck.addEventListener("change", handleIgnoreTimeChange);
    console.log(
      '[事件监听器] 已为桌面端"忽略任务具体时间"复选框绑定change事件',
    );
  } else {
    console.warn(
      '[事件监听器] 未找到桌面端"忽略任务具体时间"复选框 (multi-param-ignore_task_time)',
    );
  }

  // // 为移动端复选框绑定 change 事件监听器
  // if (mobileIgnoreTimeCheck) {
  //   // 先移除可能存在的旧监听器（防止重复绑定）
  //   mobileIgnoreTimeCheck.removeEventListener("change", handleIgnoreTimeChange);
  //   // 绑定新的监听器
  //   mobileIgnoreTimeCheck.addEventListener("change", handleIgnoreTimeChange);
  //   // console.log('[事件监听器] 已为移动端"忽略任务具体时间"复选框绑定change事件');
  // }
  // } else {
  // console.warn('[事件监听器] 未找到移动端"忽略任务具体时间"复选框 (mobile-multi-param-ignore_task_time)');
  // }
  // ========== 结束：处理 "忽略任务具体时间" 复选框变化 ==========

  try {
    console.log("[多账号模式] 初始加载账号列表...");
    // 使用loadInitialData替代直接调用API
    const initialData = await loadInitialData({ force: true });
    if (initialData && initialData.accounts) {
      renderMultiAccountList(initialData.accounts);
      console.log(
        `[多账号模式] 初始加载完成，当前有 ${initialData.accounts.length} 个账号`,
      );
    } else {
      console.log("[多账号模式] 初始加载完成，当前有 0 个账号");
      renderMultiAccountList([]);
    }
  } catch (error) {
    console.error("[多账号模式] 初始加载账号列表失败:", error);
    renderMultiAccountList([]);
  }
  updateAllAccountsStatusText();

  startMultiAccountAutoRefresh(500);
}

async function exitMultiMode() {
  stopMultiAccountAutoRefresh();

  path_planning_queue = [];
  is_planning_path = false;
  await callPythonAPI("exit_multi_account_mode");
  if (isMobileMode) {
    if (typeof destroyMobileMultiMap === "function") {
      destroyMobileMultiMap();
      console.log("[退出多账号] 移动端：已销毁多账号地图");
    }
    const mobileMultiApp = document.getElementById("mobile-multi-account-app");
    const mobileLoginContainer = document.getElementById(
      "mobile-login-container",
    );

    if (mobileMultiApp) mobileMultiApp.classList.add("hidden");
    if (mobileLoginContainer) mobileLoginContainer.classList.remove("hidden");
    updateMobileNavVisibility(false);

    console.log(
      "[退出多账号] 移动端：隐藏 mobile-multi-account-app，显示 mobile-login-container",
    );
  } else {
    $("multi-account-app").classList.add("hidden");
    $("multi-account-app").classList.remove("grid");
    $("login-container").classList.remove("hidden");
    console.log(
      "[退出多账号] 桌面端：隐藏 multi-account-app，显示 login-container",
    );
  }

  document.body.classList.remove("modal-visible");

  $("multi-account-list").innerHTML =
    '<p class="text-slate-400 text-center py-10">请先添加或导入账号</p>';
  if (multiAccountMap) {
    if (window.multiMapCleanup) {
      window.multiMapCleanup();
      window.multiMapCleanup = null;
    }
    try {
      multiAccountMap.remove(Object.values(multiAccountMarkers));
    } catch (_) {}
    try {
      if (typeof multiAccountMap.destroy === "function")
        multiAccountMap.destroy();
    } catch (e) {
      logMessage_Warning("destroy multiAccountMap warning:", e);
    }
  }
  destroyProviderMapInstance("multi-map-container");
  destroyProviderMapInstance("mobile-multi-map-container");
  multiAccountMarkers = {};
  multiAccountMarkerColors = {};
  colorIndex = 0;
  multiAccountMap = null;

  resetUI();
  if (refreshUserListInterval) {
    clearInterval(refreshUserListInterval);
    refreshUserListInterval = null;
    logMessage_Info("refreshUserList interval cleared on exiting multi mode.");
  }

  await new Promise((resolve) => setTimeout(resolve, 500));
  loadAdminSessions_inline();
}

async function multi_loadAllFromConfig() {
  // const result = await callPythonAPI("multi_load_accounts_from_config");

  const confirmed = await jsShowConfirm(
    "确认添加全部配置用户",
    "将把配置中的所有用户添加到多账号列表，是否继续？",
  );
  if (!confirmed) return;

  const confirmedAgain = await jsShowConfirm(
    "再次确认批量添加",
    "请再次确认：即将批量添加全部配置用户，并可能需要补充缺失密码。",
  );
  if (!confirmedAgain) return;

  const result = await callPythonAPI_raw(
    "/api/multi_load_accounts_from_config",
    "POST",
    {
      auth_username: currentAuthUsername,
    },
  );

  if (result && result.accounts) {
    if (sessionUUID && currentAuthUsername) {
      try {
        const response = await fetch("/auth/get_user_school_accounts", {
          method: "GET",
          headers: {
            "X-Session-ID": sessionUUID,
          },
        });
        if (response.ok) {
          const schoolAccountsResult = await response.json();
          if (schoolAccountsResult.success && schoolAccountsResult.accounts) {
            const accountDataMap = schoolAccountsResult.accounts;
            let updatedCount = 0;
            result.accounts.forEach((account) => {
              // [安全修复] 验证account.username是否为有效字符串，防止原型链污染
              if (
                account &&
                account.username &&
                typeof account.username === "string" &&
                account.username.length > 0 &&
                accountDataMap.hasOwnProperty(account.username)
              ) {
                const accountData = accountDataMap[account.username];
                // [安全修复] 只处理字符串密码，防止XSS和对象注入攻击
                if (typeof accountData === "string") {
                  // [安全修复] 使用统一的安全常量验证密码长度
                  if (
                    accountData.length > 0 &&
                    accountData.length <=
                      SECURITY_CONSTRAINTS.MAX_PASSWORD_LENGTH
                  ) {
                    account.password = accountData;
                    updatedCount++;
                  }
                } else if (
                  typeof accountData === "object" &&
                  accountData !== null
                ) {
                  // [安全修复] 严格验证对象属性，防止注入攻击
                  if (
                    accountData.hasOwnProperty("password") &&
                    typeof accountData.password === "string" &&
                    accountData.password.length > 0 &&
                    accountData.password.length <=
                      SECURITY_CONSTRAINTS.MAX_PASSWORD_LENGTH
                  ) {
                    account.password = accountData.password;
                  }
                  // [安全修复] 使用统一的安全常量验证User-Agent长度
                  if (
                    accountData.hasOwnProperty("ua") &&
                    typeof accountData.ua === "string" &&
                    accountData.ua.length > 0 &&
                    accountData.ua.length <= SECURITY_CONSTRAINTS.MAX_UA_LENGTH
                  ) {
                    account.device_ua = accountData.ua;
                  }
                  updatedCount++;
                }
              }
            });
            if (updatedCount > 0) {
              logMessage_Info(
                `[多账号-加载全部] 已从 school_accounts 更新 ${updatedCount} 个账号的密码和UA`,
              );
            }
          }
        }
      } catch (error) {
        logMessage_Warning(
          `[多账号-加载全部] 无法加载 school_accounts: ${error.message}`,
        );
      }
    }
    renderMultiAccountList(result.accounts);
  }
  if (
    result &&
    result.accounts_missing_password &&
    result.accounts_missing_password.length > 0
  ) {
    // 缺密码账号交给统一的四阶段流程（阶段 1 询问是否补密码）
    startMissingPasswordFlow(result.accounts_missing_password);
  }
}

function openNewUserModal() {
  $("newUsername").value = "";
  $("newPassword").value = "";
  $("newUserPhone").value = "";
  $("newUserNickname").value = "";
  $("newUserSmsCode").value = "";
  $("newUserSmsGroup").style.display = "none";
  $("newUserModal").style.display = "flex";
  $("newPasswordConfirm").value = "";
  const phoneInput = $("newUserPhone");
  phoneInput.oninput = () => {
    const phone = phoneInput.value.trim();
    if (phone) {
      $("newUserSmsGroup").style.display = "block";
    } else {
      $("newUserSmsGroup").style.display = "none";
    }
  };
}

// ========== 缺失密码补全流程（四阶段） ==========
//
// 阶段 1  缺密码清单：告知共 N 个账号缺少密码，问是否要补
// 阶段 2  勾选表格：「补全部分账号密码」时让用户勾选
// 阶段 3  密码弹窗：逐个补密码，显示"当前进度 i/N，还有 N-i 个待补"
// 阶段 4  导入结果：整个流程收尾后才弹（若调用方登记了收尾回调）
//
// 关键约定：
//   1) 缺密码账号**不限数量**，一律用可滚动卡片完整显示，不做任何截断；
//   2) 阶段 2 一个都不勾选 == 放弃全部，必须正常收尾（不得卡死）；
//   3) 所有退出路径必须汇聚到 flushMissingFlowDone()，
//      否则登记了收尾回调的调用方（导入）永远等不到结果弹窗。
let missingQueue = [];
let missingIndex = 0;
let missingFlowStage = null; // "list" | "select" | "password" | null
let missingFlowDoneCallback = null;
// 阶段 2 的勾选状态（按用户名）
let missingSelectSet = new Set();

function flushMissingFlowDone() {
  const cb = missingFlowDoneCallback;
  missingFlowDoneCallback = null;
  missingFlowStage = null;
  if (typeof cb === "function") {
    try {
      cb();
    } catch (e) {
      logMessage_Warning(`[缺密码流程] 收尾提示失败: ${e.message}`);
    }
  }
}

function isMissingPasswordFlowActive() {
  return missingFlowStage !== null;
}

/** 阶段 1：展示缺密码清单 */
function startMissingPasswordFlow(missingList) {
  missingQueue = Array.isArray(missingList) ? missingList.slice() : [];
  missingIndex = 0;
  missingSelectSet = new Set();
  if (!missingQueue.length) {
    // 没有缺密码账号则无需进入本流程
    flushMissingFlowDone();
    return;
  }

  missingFlowStage = "list";

  const msgEl = $("missing-password-message");
  if (msgEl) {
    msgEl.textContent = `共 ${missingQueue.length} 个账号缺少密码`;
  }

  // 卡片列表：全部渲染，不限数量，靠容器滚动完整查看
  const listEl = $("missing-password-list");
  if (listEl) {
    listEl.innerHTML = "";
    missingQueue.forEach((item) => {
      const card = document.createElement("div");
      card.className =
        "px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-700 break-all";
      card.textContent = item.tag
        ? `${item.username}（${item.tag}）`
        : item.username;
      listEl.appendChild(card);
    });
  }

  bindMissingPasswordListButtons();
  openModalElement("missing-password-modal");
}

function bindMissingPasswordListButtons() {
  const btnAll = $("missing-pass-abandon-all-btn");
  const btnFillAll = $("missing-pass-fill-all-btn");
  const btnFillSome = $("missing-pass-fill-some-btn");

  if (btnAll) btnAll.onclick = () => abandonRemainingMissingPasswords();
  if (btnFillAll)
    btnFillAll.onclick = () => startMissingPasswordQueue(missingQueue.slice());
  if (btnFillSome) btnFillSome.onclick = () => openMissingPasswordSelection();
}

/** 阶段 2：勾选要补密码的账号 */
function openMissingPasswordSelection() {
  missingFlowStage = "select";
  missingSelectSet = new Set();

  const tbody = $("missing-pass-select-tbody");
  if (tbody) {
    tbody.innerHTML = "";
    missingQueue.forEach((item, index) => {
      const tr = document.createElement("tr");
      tr.className = "border-t border-slate-100 hover:bg-slate-50";

      const tdCheck = document.createElement("td");
      tdCheck.className = "py-2 px-3";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "w-4 h-4 accent-sky-600";
      cb.dataset.missingIndex = String(index);
      cb.checked = false;
      cb.addEventListener("change", () => {
        if (cb.checked) missingSelectSet.add(item.username);
        else missingSelectSet.delete(item.username);
        updateMissingSelectionCount();
      });
      tdCheck.appendChild(cb);

      const tdName = document.createElement("td");
      tdName.className = "py-2 px-3 text-slate-700 break-all";
      tdName.textContent = item.tag
        ? `${item.username}（${item.tag}）`
        : item.username;

      tr.appendChild(tdCheck);
      tr.appendChild(tdName);
      tbody.appendChild(tr);
    });
  }

  const selectAll = $("missing-pass-select-all");
  if (selectAll) {
    selectAll.checked = false;
    selectAll.onchange = () => {
      const checked = selectAll.checked;
      const tbodyEl = $("missing-pass-select-tbody");
      if (tbodyEl) {
        tbodyEl.querySelectorAll("input[type=checkbox]").forEach((cb) => {
          cb.checked = checked;
          const idx = Number(cb.dataset.missingIndex);
          const target = missingQueue[idx];
          if (!target) return;
          if (checked) missingSelectSet.add(target.username);
          else missingSelectSet.delete(target.username);
        });
      }
      updateMissingSelectionCount();
    };
  }

  const backBtn = $("missing-pass-select-back-btn");
  if (backBtn) backBtn.onclick = () => startMissingPasswordFlow(missingQueue);

  const confirmBtn = $("missing-pass-select-confirm-btn");
  if (confirmBtn)
    confirmBtn.onclick = () => {
      const selected = missingQueue.filter((item) =>
        missingSelectSet.has(item.username),
      );
      closeModalElement("missing-password-select-modal");
      // 一个都没勾选：等价于放弃全部，直接收尾，绝不进入阶段 3
      if (!selected.length) {
        logMessage_Info("[缺密码流程] 未勾选任何账号，已跳过补密码。");
        abandonRemainingMissingPasswords({ keepModalClosed: true });
        return;
      }
      startMissingPasswordQueue(selected);
    };

  updateMissingSelectionCount();
  openModalElement("missing-password-select-modal");
}

function updateMissingSelectionCount() {
  const el = $("missing-pass-select-count");
  if (el) {
    el.textContent = `已选 ${missingSelectSet.size} / 共 ${missingQueue.length}`;
  }
}

/** 阶段 3：逐个补密码 */
function startMissingPasswordQueue(accounts) {
  missingQueue = Array.isArray(accounts) ? accounts.slice() : [];
  missingIndex = 0;
  if (!missingQueue.length) {
    abandonRemainingMissingPasswords({ keepModalClosed: true });
    return;
  }
  missingFlowStage = "password";
  closeModalElement("missing-password-modal");
  closeModalElement("missing-password-select-modal");
  showMissingPasswordProgress();
}

function showMissingPasswordProgress() {
  const cur = missingQueue[missingIndex];
  if (!cur) {
    finishMissingPasswordQueue();
    return;
  }

  const total = missingQueue.length;
  const remaining = total - missingIndex;

  const accountEl = $("multi-add-password-account");
  if (accountEl) accountEl.textContent = cur.username;

  // 进度：明确"当前第几个 / 还剩几个"，不限总数
  const progressEl = $("multi-add-password-progress-text");
  if (progressEl) {
    progressEl.textContent = `当前进度 ${missingIndex + 1}/${total}，还有 ${remaining} 个账号待补密码`;
  }

  // 第一个账号显示"放弃所有"，之后显示"放弃剩余 N 个"
  const abandonBtn = $("multi-add-abandon-all-btn");
  if (abandonBtn) {
    abandonBtn.textContent =
      missingIndex === 0 ? "放弃所有无密码账号" : `放弃剩余 ${remaining} 个账号`;
  }

  const skipBtn = $("multi-add-skip-current-btn");
  if (skipBtn) skipBtn.onclick = () => advanceMissingPasswordQueue();

  if (abandonBtn)
    abandonBtn.onclick = () => abandonRemainingMissingPasswords();

  openMultiAddUserModalForPassword(cur.username, cur.tag);
}

function advanceMissingPasswordQueue() {
  if (missingFlowStage !== "password") {
    closeMultiAddUserModal();
    return;
  }
  missingIndex += 1;
  if (missingIndex >= missingQueue.length) {
    finishMissingPasswordQueue();
    return;
  }
  closeMultiAddUserModal();
  showMissingPasswordProgress();
}

function finishMissingPasswordQueue() {
  missingQueue = [];
  missingIndex = 0;
  closeMultiAddUserModal();
  closeModalElement("missing-password-modal");
  closeModalElement("missing-password-select-modal");
  flushMissingFlowDone();
}

/** 放弃所有剩余（含当前）无密码账号；所有放弃路径都走这里 */
function abandonRemainingMissingPasswords(options) {
  const opts = options || {};
  const abandoned = missingQueue.length - missingIndex;
  missingQueue = [];
  missingIndex = 0;
  if (abandoned > 0) {
    logMessage_Info(`[缺密码流程] 已放弃 ${abandoned} 个无密码账号。`);
  }
  if (!opts.keepModalClosed) {
    closeModalElement("missing-password-select-modal");
    closeModalElement("missing-password-modal");
  }
  closeMultiAddUserModal();
  flushMissingFlowDone();
}

/** 兼容旧调用名：外部仍可能调用 closeMissingPasswordModal() */
function closeMissingPasswordModal() {
  closeModalElement("missing-password-modal");
  closeModalElement("missing-password-select-modal");
}

function openModalElement(id) {
  const modal = $(id);
  if (!modal) return;
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.body.classList.add("modal-visible");
}

function closeModalElement(id) {
  const modal = $(id);
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

// ============================================================
// 新增：移动端创建用户模态框逻辑
// ============================================================
function openMobileCreateUserModal() {
  const modal = document.getElementById("mobile-create-user-modal");
  if (!modal) return;

  // 重置表单
  document.getElementById("mobile-new-username").value = "";
  document.getElementById("mobile-new-password").value = "";
  document.getElementById("mobile-new-nickname").value = "";
  document.getElementById("mobile-new-phone").value = "";

  // 重置验证码相关
  const smsGroup = document.getElementById("mobile-new-sms-group");
  const smsCode = document.getElementById("mobile-new-sms-code");
  if (smsGroup) smsGroup.style.display = "none";
  if (smsCode) smsCode.value = "";

  // 监听手机号输入，显示/隐藏验证码区域
  const phoneInput = document.getElementById("mobile-new-phone");
  if (phoneInput) {
    phoneInput.oninput = () => {
      const phone = phoneInput.value.trim();
      if (smsGroup) {
        smsGroup.style.display = phone ? "block" : "none";
      }
    };
  }

  // 显示模态框 (模拟底部滑出效果)
  modal.classList.remove("hidden");
  // 这里利用 requestAnimationFrame 或 setTimeout 确保 transition 生效（如果有的话）
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

// 移动端创建用户 - 发送验证码
let mobileNewUserCodeCooldown = 0;
async function sendMobileNewUserCode() {
  if (mobileNewUserCodeCooldown > 0) {
    // showModalAlert(`请等待 ${mobileNewUserCodeCooldown} 秒后再发送`, "提示");
    swal.fire({
      title: "提示",
      text: `请等待 ${mobileNewUserCodeCooldown} 秒后再发送`,
      icon: "info",
    });
    return;
  }

  const phone = document.getElementById("mobile-new-phone").value.trim();
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
    // showModalAlert("请输入正确的手机号", "提示");
    swal.fire({
      title: "提示",
      text: "请输入正确的手机号",
      icon: "info",
    });
    return;
  }

  const sendBtn = document.getElementById("mobile-new-send-code-btn");
  const originalText = "发送";

  // 打开图形验证码模态框
  openCaptchaModal({
    phone: phone,
    button: sendBtn,
    originalText: originalText,
    scene: "register",
  });
}

function closeMobileCreateUserModal() {
  const modal = document.getElementById("mobile-create-user-modal");
  if (!modal) return;

  modal.classList.remove("show");
  setTimeout(() => {
    modal.classList.add("hidden");
  }, 300); // 与 CSS transition 时间匹配
}

async function submitMobileCreateUser() {
  const username = document.getElementById("mobile-new-username").value.trim();
  const password = document.getElementById("mobile-new-password").value;
  const nickname = document.getElementById("mobile-new-nickname").value.trim();
  const phone = document.getElementById("mobile-new-phone").value.trim();
  // 获取验证码（可选）
  const smsCodeEl = document.getElementById("mobile-new-sms-code");
  const smsCode = smsCodeEl ? smsCodeEl.value.trim() : "";
  const confirmBtn = document.getElementById("mobile-new-user-confirm-btn");

  // ========== 输入验证 ==========

  // 验证账号和密码是否为空
  if (!username || !password) {
    // showModalAlert("账号和密码为必填项", "错误");
    swal.fire({
      title: "错误",
      text: "账号和密码为必填项",
      icon: "error",
    });
    return;
  }

  // 验证密码长度（至少6个字符）
  if (password.length < 6) {
    // showModalAlert("密码长度至少为6个字符", "错误");
    swal.fire({
      title: "错误",
      text: "密码长度至少为6个字符",
      icon: "error",
    });
    return;
  }

  // 如果填写了手机号，验证格式（中国大陆手机号：1开头的11位数字）
  if (phone && !/^1[3-9]\d{9}$/.test(phone)) {
    // showModalAlert("请输入正确的手机号格式", "错误");
    swal.fire({
      title: "错误",
      text: "请输入正确的手机号格式",
      icon: "error",
    });
    return;
  }

  // ========== 禁用按钮，防止重复提交 ==========
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML =
      '<span class="animate-spin inline-block mr-2">⏳</span>创建中...';
  }

  try {
    // ========== 调用后端API创建用户 ==========

    // 移动端管理员创建用户API：/auth/admin/create_user
    //
    // available_runs（可用次数）处理说明：
    // - 此API请求中**不需要**传递 available_runs 参数
    // - 后端会自动从 .\configs\config.json 的 [Payment_Settings] -> default_available_runs 读取默认值
    // - 这确保了通过 移动端管理员界面（mobile-new-user-confirm-btn）创建的用户
    //   与其他方式（PC端、自助注册）创建的用户使用统一的默认 available_runs
    // - 配置路径：.\configs\config.json -> [Payment_Settings] -> default_available_runs
    // - 如需修改某个用户的 available_runs，请在用户创建后通过用户管理功能进行修改
    //
    // 请求参数说明：
    // - username: 用户名（必填）
    // - password: 密码（必填）
    // - group: 用户组（此处固定为 "user"）
    // - nickname: 昵称（可选，如不填则使用用户名作为昵称）
    // - phone: 手机号（可选，如填写则会绑定到用户）
    // - sms_code: 短信验证码（可选，如填写则会进行校验）
    const response = await fetch("/auth/admin/create_user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 使用会话UUID进行身份验证
      },
      body: JSON.stringify({
        username: username,
        password: password,
        group: "user", // 默认为普通用户
        // 扩展字段支持 (如果后端支持这些字段)
        nickname: nickname,
        phone: phone || "",
        sms_code: smsCode || "", // 验证码可选，如非空则校验
      }),
    });

    // ========== 解析API响应 ==========
    const result = await response.json();

    // ========== 处理创建结果 ==========
    if (result.success) {
      // ===== 创建成功 =====
      // showModalAlert("用户创建成功！", "成功");
      swal.fire({
        title: "成功",
        text: "用户创建成功！",
        icon: "success",
      });
      closeMobileCreateUserModal();

      // 刷新用户列表，显示新创建的用户
      if (typeof loadAdminUsers === "function") {
        await loadAdminUsers();

        // 尝试同步到移动端面板
        if (typeof copyAdminContentToMultiPanel === "function") {
          copyAdminContentToMultiPanel("users");
        }
        if (typeof copyAdminContentToPanelVersion === "function") {
          copyAdminContentToPanelVersion("users");
        }
      }
    } else {
      // ===== 创建失败 =====
      // showModalAlert(`创建失败: ${result.message || "未知错误"}`, "错误");
      swal.fire({
        title: "错误",
        text: `创建失败: ${result.message || "未知错误"}`,
        icon: "error",
      });
    }
  } catch (e) {
    // ========== 异常处理 ==========
    // 捕获网络错误、解析错误等异常
    console.error("创建用户失败:", e);
    // showModalAlert(`请求出错: ${e.message}`, "错误");
    swal.fire({
      title: "错误",
      text: `请求出错: ${e.message}`,
      icon: "error",
    });
  } finally {
    // ========== 恢复按钮状态 ==========
    // 无论成功或失败，都要恢复按钮的正常状态
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = "立即创建";
    }
  }
}

function closeNewUserModal() {
  $("newUserModal").style.display = "none";
}
$("newUserClose").onclick = closeNewUserModal;
$("newUserCancel").onclick = closeNewUserModal;

// 标记多账号添加弹窗的来源（例如：从配置按钮进入）
let multiAddModalSource = null;

function openMultiAddUserModal() {
  if ($("multi-add-username")) $("multi-add-username").value = "";
  if ($("multi-add-password")) $("multi-add-password").value = "";
  // 修复：多账号添加模态框中不存在 password-confirm 字段，移除该行以防止报错
  // $("multi-add-password-confirm").value = "";
  if ($("multi-add-tag")) $("multi-add-tag").value = "";

  const modal = $("multi-add-user-modal");
  const passwordInput = $("multi-add-password");
  const passwordLabel = document.querySelector(
    'label[for="multi-add-password"]',
  );

  // 如果是从配置按钮进入，密码改为可选并更新占位提示
  if (multiAddModalSource === "from-config") {
    if (passwordLabel) passwordLabel.textContent = "密码 (可选)";
    if (passwordInput) passwordInput.placeholder = "可留空，后端将尝试查找";
  } else {
    if (passwordLabel) passwordLabel.textContent = "密码 (必填)";
    if (passwordInput) passwordInput.placeholder = "请输入密码 (至少6字符)";
  }
  if (modal) modal.style.display = "flex";
}

function closeMultiAddUserModal() {
  const usernameInput = $("multi-add-username");
  const passwordInput = $("multi-add-password");
  const passwordLabel = document.querySelector(
    'label[for="multi-add-password"]',
  );
  const title = document.querySelector("#multi-add-user-modal .card-title");

  // 恢复补密码模式下隐藏/改写过的元素，避免影响正常"添加新账号"
  const usernameGroup = $("multi-add-username-group");
  const tagGroup = $("multi-add-tag-group");
  const progressBox = $("multi-add-password-progress");
  const actionsBox = $("multi-add-password-actions");

  if (usernameGroup) usernameGroup.classList.remove("hidden");
  if (tagGroup) tagGroup.classList.remove("hidden");
  if (progressBox) progressBox.classList.add("hidden");
  if (actionsBox) {
    actionsBox.classList.add("hidden");
    actionsBox.classList.remove("flex");
  }
  if (title) title.textContent = "添加新账号";

  if (usernameInput) {
    usernameInput.readOnly = false;
    usernameInput.classList.remove("bg-slate-100", "cursor-not-allowed");
  }
  if (passwordInput) {
    passwordInput.placeholder = "请输入密码 (至少6字符)";
  }
  if (passwordLabel) {
    passwordLabel.textContent = "密码 (必填)";
  }

  // 重置来源标记
  multiAddModalSource = null;

  $("multi-add-user-modal").style.display = "none";
}

function openMultiAddUserModalForPassword(username, tag) {
  const usernameInput = $("multi-add-username");
  const tagInput = $("multi-add-tag");
  const passwordInput = $("multi-add-password");
  const title = document.querySelector("#multi-add-user-modal .card-title");

  // 补密码模式只让用户填密码：账号以只读文本显示，隐藏账号输入与"标记"输入
  const usernameGroup = $("multi-add-username-group");
  const tagGroup = $("multi-add-tag-group");
  const progressBox = $("multi-add-password-progress");
  const actionsBox = $("multi-add-password-actions");

  if (usernameGroup) usernameGroup.classList.add("hidden");
  if (tagGroup) tagGroup.classList.add("hidden");
  if (progressBox) progressBox.classList.remove("hidden");
  if (actionsBox) {
    actionsBox.classList.remove("hidden");
    actionsBox.classList.add("flex");
  }
  if (title) title.textContent = "补全账号密码";

  // 保留隐藏输入框的值，提交时仍然要带上账号
  if (usernameInput) {
    usernameInput.value = username;
    usernameInput.readOnly = true;
  }
  if (tagInput) {
    tagInput.value = tag || "";
  }
  if (passwordInput) {
    passwordInput.value = "";
    passwordInput.placeholder = "该账号缺少密码，请补全";
  }
  $("multi-add-user-modal").style.display = "flex";
  if (passwordInput) {
    passwordInput.focus();
  }
}
$("newUserSendCode").onclick = async function () {
  const phone = $("newUserPhone").value.trim();
  if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
    // showModalAlert("请输入正确的手机号");
    swal.fire({
      title: "提示",
      text: "请输入正确的手机号格式",
      icon: "warning",
    });
    return;
  }

  const sendCodeBtn = $("newUserSendCode");
  const originalText = sendCodeBtn.textContent;

  // 打开图形验证码模态框发送短信
  openCaptchaModal({
    phone: phone,
    button: sendCodeBtn,
    originalText: originalText,
    scene: "register",
  });
};

async function multi_addFromConfig() {
  const user = $("multi-config-user-select").value;

  if (!user) {
    // 从配置按钮进入“添加账号”弹窗，允许空密码交由后端查找
    multiAddModalSource = "from-config";
    openMultiAddUserModal();
    return;
  }
  let passwordToUse = "";
  let uaToUse = "";
  if (sessionUUID && currentAuthUsername) {
    try {
      const response = await fetch("/auth/get_user_school_accounts", {
        method: "GET",
        headers: {
          "X-Session-ID": sessionUUID,
        },
      });

      if (response.ok) {
        const result = await response.json();

        if (result.success && result.accounts) {
          const accountData = result.accounts[user];

          if (accountData) {
            if (typeof accountData === "string") {
              passwordToUse = accountData;
              logMessage_Info(
                `[多账号-添加] 已从 school_accounts 加载用户 ${user} 的密码（旧格式）`,
              );
            } else if (
              typeof accountData === "object" &&
              accountData !== null
            ) {
              passwordToUse = accountData.password || "";
              uaToUse = accountData.ua || "";
              logMessage_Info(
                `[多账号-添加] 已从 school_accounts 加载用户 ${user} 的密码和UA`,
              );
            }
          }
        }
      }
    } catch (error) {
      logMessage_Warning(
        `[多账号-添加] 无法加载 school_accounts: ${error.message}`,
      );
    }
  }
  const result = await callPythonAPI("multi_add_account", user, passwordToUse);
  if (
    result &&
    result.success === false &&
    result.action === "request_password"
  ) {
    // showModalAlert(
    //   `账号 ${result.username} 缺少密码，请在弹窗中补全。`,
    //   "缺少密码"
    // );
    swal.fire({
      title: "缺少密码",
      text: `账号 ${result.username} 缺少密码，请在弹窗中补全。`,
      icon: "warning",
    });
    openMultiAddUserModalForPassword(result.username, result.tag);
  } else if (result && result.success === false && result.reason === "already_exists") {
    // 账号已存在且状态正常：不是"添加成功"，也不是"缺少密码"
    showModalAlert(result.message || `账号 ${user} 已存在，未重复添加。`);
    if (result.accounts) renderMultiAccountList(result.accounts);
  } else if (result && result.success === false && result.reason === "account_running") {
    showModalAlert(result.message || "该账号正在执行任务，请先停止后再试。");
    if (result.accounts) renderMultiAccountList(result.accounts);
  } else if (result && result.accounts) {
    renderMultiAccountList(result.accounts);
  }
}
async function submitMultiAddUser() {
  const inputUsername = $("multi-add-username");
  const inputPassword = $("multi-add-password");
  const inputTag = $("multi-add-tag");

  const usernameVal = inputUsername.value.trim();
  const passwordVal = inputPassword.value;
  const tagVal = inputTag.value.trim();
  const allowEmptyPassword =
    typeof multiAddModalSource !== "undefined" &&
    multiAddModalSource === "from-config";

  // 基本验证：用户名不能为空；密码可在特定来源为空
  if (!usernameVal) {
    // showModalAlert("账号不能为空");
    swal.fire({
      title: "提示",
      text: "账号不能为空",
      icon: "warning",
    });
    return;
  }
  if (!allowEmptyPassword && !passwordVal) {
    // showModalAlert("密码不能为空");
    swal.fire({
      title: "提示",
      text: "密码不能为空",
      icon: "warning",
    });
    return;
  }

  // [安全修复] 使用统一的安全常量验证用户名长度
  if (usernameVal.length > SECURITY_CONSTRAINTS.MAX_USERNAME_LENGTH) {
    // showModalAlert(
    //   `用户名过长（最多${SECURITY_CONSTRAINTS.MAX_USERNAME_LENGTH}个字符）`,
    //   "错误"
    // );
    swal.fire({
      title: "错误",
      text: `用户名过长（最多${SECURITY_CONSTRAINTS.MAX_USERNAME_LENGTH}个字符）`,
      icon: "error",
    });
    return;
  }

  // [安全修复] 使用统一的正则表达式验证用户名格式
  if (!SECURITY_CONSTRAINTS.USERNAME_PATTERN.test(usernameVal)) {
    // showModalAlert(
    //   "用户名只能包含字母、数字、下划线、连字符、点和@符号",
    //   "错误"
    // );
    swal.fire({
      title: "错误",
      text: "用户名只能包含字母、数字、下划线、连字符、点和@符号",
      icon: "error",
    });
    return;
  }

  // [安全修复] 使用统一的安全常量验证密码长度范围（当密码非空或必须提供时）
  if (!allowEmptyPassword || passwordVal.length > 0) {
    if (passwordVal.length < SECURITY_CONSTRAINTS.MIN_PASSWORD_LENGTH) {
      // showModalAlert(
      //   `密码长度至少为${SECURITY_CONSTRAINTS.MIN_PASSWORD_LENGTH}个字符`,
      //   "错误"
      // );
      swal.fire({
        title: "错误",
        text: `密码长度至少为${SECURITY_CONSTRAINTS.MIN_PASSWORD_LENGTH}个字符`,
        icon: "error",
      });
      return;
    }
    if (passwordVal.length > SECURITY_CONSTRAINTS.MAX_PASSWORD_LENGTH) {
      // showModalAlert(
      //   `密码过长（最多${SECURITY_CONSTRAINTS.MAX_PASSWORD_LENGTH}个字符）`,
      //   "错误"
      // );
      swal.fire({
        title: "错误",
        text: `密码过长（最多${SECURITY_CONSTRAINTS.MAX_PASSWORD_LENGTH}个字符）`,
        icon: "error",
      });
      return;
    }
  }

  // [安全修复] 使用统一的安全常量验证标签长度
  if (tagVal.length > SECURITY_CONSTRAINTS.MAX_TAG_LENGTH) {
    // showModalAlert(
    //   `标签过长（最多${SECURITY_CONSTRAINTS.MAX_TAG_LENGTH}个字符）`,
    //   "错误"
    // );
    swal.fire({
      title: "错误",
      text: `标签过长（最多${SECURITY_CONSTRAINTS.MAX_TAG_LENGTH}个字符）`,
      icon: "error",
    });
    return;
  }

  setButtonLoading("multi-add-user-confirm", true, "添加中...");
  try {
    const result = await callPythonAPI(
      "multi_add_account",
      usernameVal,
      passwordVal,
      tagVal,
    );

    if (result && result.success === false && result.reason === "already_exists") {
      // 账号已存在且状态正常：不算添加成功，给出准确提示
      showModalAlert(result.message || `账号 ${usernameVal} 已存在，未重复添加。`);
      closeMultiAddUserModal();
      if (result.accounts) renderMultiAccountList(result.accounts);
      if (isMissingPasswordFlowActive()) advanceMissingPasswordQueue();
    } else if (
      result &&
      result.success === false &&
      result.reason === "account_running"
    ) {
      showModalAlert(result.message || "该账号正在执行任务，请先停止后再试。");
      closeMultiAddUserModal();
      if (isMissingPasswordFlowActive()) advanceMissingPasswordQueue();
    } else if (result && result.accounts) {
      // showModalAlert("账号添加成功", "成功");
      swal.fire({
        text: "账号添加成功",
        title: "成功",
        icon: "success",
      });
      closeMultiAddUserModal();
      renderMultiAccountList(result.accounts);
      // 正在补密码队列中：推进到下一个账号
      if (isMissingPasswordFlowActive()) advanceMissingPasswordQueue();
    } else {
      // showModalAlert(result?.message || "添加失败");
      swal.fire({
        title: "错误",
        text: result?.message || "添加失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert(`添加时发生错误: ${e.message}`);
    swal.fire({
      title: "错误",
      text: `添加时发生错误: ${e.message}`,
      icon: "error",
    });
    logMessage_Error("添加新账号时发生错误:", e);
  } finally {
    setButtonLoading("multi-add-user-confirm", false, "确认添加");
    if (inputUsername && inputUsername.readOnly) {
      inputUsername.readOnly = false;
      inputUsername.classList.remove("bg-slate-100", "cursor-not-allowed");
      $("multi-add-password").placeholder = "请输入密码 (至少6字符)";
    }
    // 提交结束后重置来源标记，避免影响后续操作
    multiAddModalSource = null;
  }
}

/** 导入结果弹窗：汇总成功 / 跳过 / 失败**全部**结果
 *
 * 刻意不做任何截断或折叠：缺密码、已存在这些名单可能很长，
 * 截断会让人无法判断到底哪些账号没导进来。每个段落用卡片列表完整显示，
 * 超出可视高度时靠容器滚动查看。
 */
function showImportResultModal(result, fileName) {
  const sections = [];

  const pushSection = (title, names, colorClass) => {
    if (!names || !names.length) return;
    sections.push({ title: `${title} ${names.length} 个`, names, colorClass });
  };

  pushSection("【成功导入】", result.added, "text-emerald-700");
  pushSection("【已存在，未重复添加】", result.already_exists, "text-amber-700");
  pushSection(
    "【缺少密码，已跳过】",
    (result.accounts_missing_password || []).map((it) =>
      it && it.username ? it.username : it,
    ),
    "text-amber-700",
  );
  pushSection(
    "【执行中，已跳过】",
    result.skipped_running,
    "text-amber-700",
  );
  pushSection("【文件内重复行】", result.duplicate_in_file, "text-slate-500");
  pushSection(
    "【学号格式不对，已跳过】",
    result.invalid_username,
    "text-red-700",
  );
  pushSection(
    "【密码包含中文，已跳过】",
    result.invalid_password,
    "text-red-700",
  );
  pushSection("【失败】", result.failed_names, "text-red-700");

  const subtitleEl = $("import-result-subtitle");
  if (subtitleEl) {
    const rows = result.total_rows != null ? `共 ${result.total_rows} 行` : "";
    subtitleEl.textContent = `${fileName ? `文件：${fileName}　　` : ""}${rows}`;
  }

  const container = $("import-result-sections");
  if (container) {
    container.innerHTML = "";
    if (!sections.length) {
      const empty = document.createElement("p");
      empty.className = "text-slate-500 text-center py-6";
      empty.textContent = result.message || "文件中没有可导入的账号。";
      container.appendChild(empty);
    }
    sections.forEach((section) => {
      const wrap = document.createElement("div");

      const head = document.createElement("div");
      head.className = `text-sm font-semibold ${section.colorClass} mb-2`;
      head.textContent = section.title;
      wrap.appendChild(head);

      const list = document.createElement("div");
      list.className = "flex flex-col gap-1";
      section.names.forEach((name) => {
        const card = document.createElement("div");
        card.className =
          "px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-700 break-all";
        card.textContent = name;
        list.appendChild(card);
      });
      wrap.appendChild(list);
      container.appendChild(wrap);
    });
  }

  openModalElement("import-result-modal");
}

function closeImportResultModal() {
  closeModalElement("import-result-modal");
}

async function multi_importFromExcel() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".xlsx, .xls, .csv";

  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) {
      logMessage_Info("未选择文件。");
      return;
    }

    const fileName = file.name;
    const fileExt = fileName.split(".").pop().toLowerCase();
    if (!["xlsx", "xls", "csv"].includes(fileExt)) {
      // showModalAlert("文件格式不支持，请选择 .xlsx, .xls, 或 .csv 文件。");
      swal.fire({
        title: "错误",
        text: "文件格式不支持，请选择 .xlsx, .xls, 或 .csv 文件。",
        icon: "error",
      });
      return;
    }

    logMessage_Info(`正在读取文件: ${fileName}`);
    const reader = new FileReader();
    reader.readAsDataURL(file);

    reader.onload = async () => {
      try {
        const base64Content = reader.result.split(",")[1];
        const result = await callPythonAPI(
          "multi_import_accounts",
          fileName,
          base64Content,
        );

        if (result && result.success) {
          logMessage_Info(result.message || "导入完成。");
          if (result.accounts) {
            renderMultiAccountList(result.accounts);
          }
          // 导入结果只出一个弹窗，且必须等缺密码补全流程结束后再弹
          missingFlowDoneCallback = () => showImportResultModal(result, fileName);
          if (
            result.accounts_missing_password &&
            result.accounts_missing_password.length > 0
          ) {
            // 缺密码账号逐个弹窗让用户补密码
            startMissingPasswordFlow(result.accounts_missing_password);
          } else {
            flushMissingFlowDone();
          }
        } else {
          // showModalAlert(`导入失败: ${result.message || "未知错误"}`);
          swal.fire({
            title: "错误",
            text: `导入失败: ${result.message || "未知错误"}`,
            icon: "error",
          });
        }
      } catch (err) {
        logMessage_Error("导入文件时出错:", err);
        // showModalAlert(`导入失败: ${err.message}`);
        swal.fire({
          title: "错误",
          text: `导入失败: ${err.message}`,
          icon: "error",
        });
      }
    };

    reader.onerror = () => {
      logMessage_Error("读取文件失败。");
      // showModalAlert("读取文件失败。");
      swal.fire({
        title: "错误",
        text: "读取文件失败。",
        icon: "error",
      });
    };
  };
  input.click();
}

async function multi_exportToExcel() {
  const result = await callPythonAPI("multi_export_accounts_summary");
  if (!result || !result.success) {
    // showModalAlert(result?.message || "导出失败");
    swal.fire({
      title: "错误",
      text: result?.message || "导出失败",
      icon: "error",
    });
    return;
  }
  if (result.content && result.filename) {
    const binaryString = atob(result.content);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], {
      type: result.mimetype || "application/octet-stream",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    logMessage_Info(`汇总已导出：${result.filename}`);
  }
}
async function multi_startAll() {
  // ========== 步骤1：检查账号数量 ==========
  // 从页面上显示的账号计数元素获取账号总数
  const count = parseInt($("multi-account-count").textContent || "0", 10);
  if (!count || count <= 0) {
    // 如果账号列表为空，提示用户并退出
    // showModalAlert("账号列表为空，无法开始。请先添加账号。");
    swal.fire({
      title: "提示",
      text: "账号列表为空，无法开始。请先添加账号。",
      icon: "info",
    });
    return;
  }

  // 只检查当前多账号界面实际显示的账号，避免管理员把全部系统账号混入检查。
  let skipOverdue = false;
  const canStart = await _checkOverdueBeforeStartByCurrentMode({
    allowSkip: true,
    onSkip: () => {
      skipOverdue = true;
    },
  });
  if (!canStart) {
    return;
  }
  const overdueOverride = _consumeOverdueForceOverride();

  const use_delay = $("multi-use-delay-check").checked;
  const min_delay = parseInt($("multi-min-delay-input").value) || 0;
  const max_delay = parseInt($("multi-max-delay-input").value) || 300;
  const run_only_incomplete = $("multi-run-only-incomplete-check").checked;

  const result = await callPythonAPI(
    "multi_start_all_accounts",
    min_delay,
    max_delay,
    use_delay,
    run_only_incomplete,
    skipOverdue,
    overdueOverride.bypass_overdue,
    overdueOverride.waive_charge,
  );

  // 检查是否是欠费错误
  // 后端在检测到欠费时会返回特定的错误代码
  if (!result.success && result.error_code === "OVERDUE_PAYMENT") {
    // 构建欠费账号列表的显示文本
    let overdueList = "";
    if (result.overdue_accounts && result.overdue_accounts.length > 0) {
      // 遍历每个欠费账号，格式化为易读的文本
      // 例如：账号1 (欠费3次)
      overdueList = result.overdue_accounts
        .map((acc) => `${acc.school_username} (欠费${acc.overdue_count}次)`)
        .join("\n");
    }

    // 构建完整的提示消息
    const message = `检测到以下账号存在欠费：\n\n${overdueList}\n\n请先完成缴费后再执行任务。`;

    // 显示友好的弹窗提示
    // showModalAlert(message, "欠费提示");

    // 可选：自动跳转到缴费页面（如果需要的话）
    // switchToTab('tab4'); // 取消注释此行以启用自动跳转

    // 阻止任务启动，直接返回
    return;
  }

  if (!result || !result.success) {
    // 其他错误（非欠费），显示标准错误消息
    // showModalAlert(result?.message || "无法开始全部账号任务。");
    swal.fire({
      title: "错误",
      text: result?.message || "无法开始全部账号任务。",
      icon: "error",
    });
    return;
  }
}

async function multi_stopAll() {
  await callPythonAPI("multi_stop_all_accounts");
}

function selectTaskFromBackend(index) {
  if (selectedTaskIndex !== index) selectTask(index);
}

function updateDashboard() {
  const formatMMSS = (sec) => {
    const s = Math.max(0, Math.floor(Number(sec) || 0));
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(
      s % 60,
    ).padStart(2, "0")}`;
  };
  if (!currentRunData || Object.keys(currentRunData).length === 0) {
    $("run-stats-label").textContent = `-- km / --:--`;
    $("live-dist-label").textContent = "0.00 km";
    $("total-dist-label").textContent = "0.00 km";
    $("live-time-label").textContent = "00:00";
    $("total-time-label").textContent = "00:00";
    const remainLabel = $("remaining-time-label");
    if (remainLabel) remainLabel.textContent = "00:00";
    const mobileRemainLabel = document.getElementById("mobile-remaining-time-label");
    if (mobileRemainLabel) mobileRemainLabel.textContent = "00:00";
    $("target-points-text").innerHTML =
      '<p class="text-slate-400 text-center text-xs pt-4">请选择一个任务</p>';
    $("current-location-label").textContent = "当前位置GPS坐标: --, --";
    return;
  }
  const isDrawingNow = isDrawing && !currentRunData.run_coords?.length;
  if (isDrawingNow && draftTotalDist > 0) {
    const drawKm = (draftTotalDist / 1000).toFixed(2);
    const avgSpeed = pythonParams.speed_mps || 1.5;
    const estMin = avgSpeed > 0 ? draftTotalDist / avgSpeed / 60 : 0;
    $("run-stats-block").innerHTML =
      `<p class="text-sm text-slate-500">当前绘制</p><p class="font-bold text-2xl text-emerald-600">${drawKm} km / ~${estMin.toFixed(
        1,
      )} min</p>`;
  } else {
    const dist = ((currentRunData.total_run_distance_m || 0) / 1000).toFixed(2);
    const timeMin = Math.floor((currentRunData.total_run_time_s || 0) / 60);
    const timeSec = Math.floor((currentRunData.total_run_time_s || 0) % 60);
    $("run-stats-block").innerHTML =
      `<p class="text-sm text-slate-500">已选任务总览</p><p id="run-stats-label" class="font-bold text-2xl text-sky-600">${dist} km / ${String(
        timeMin,
      ).padStart(2, "0")}:${String(timeSec).padStart(2, "0")}</p>`;
  }
  const liveKm = ((currentRunData.distance_covered_m || 0) / 1000).toFixed(2);
  const liveMs = runAccumulatedMs || 0;
  const mm = String(Math.floor(liveMs / 60000)).padStart(2, "0");
  const ss = String(Math.floor((liveMs % 60000) / 1000)).padStart(2, "0");
  $("live-dist-label").textContent = `${liveKm} km`;
  $("live-time-label").textContent = `${mm}:${ss}`;

  const totalDistKm = (
    (currentRunData.total_run_distance_m || 0) / 1000
  ).toFixed(2);
  $("total-dist-label").textContent = `${totalDistKm} km`;
  const totalTimeMin = Math.floor((currentRunData.total_run_time_s || 0) / 60);
  const totalTimeSec = Math.floor((currentRunData.total_run_time_s || 0) % 60);
  $("total-time-label").textContent = `${String(totalTimeMin).padStart(
    2,
    "0",
  )}:${String(totalTimeSec).padStart(2, "0")}`;
  const remainingTimeS = Math.max(
    0,
    (currentRunData.total_run_time_s || 0) - liveMs / 1000,
  );
  const remainingLabel = $("remaining-time-label");
  if (remainingLabel) {
    remainingLabel.textContent = formatMMSS(remainingTimeS);
  }

  const targetDiv = $("target-points-text");
  targetDiv.innerHTML = "";
  const names = (currentRunData.target_point_names || "").split("|");
  const sequence = currentRunData.target_sequence || 0;
  if (names.length === 0 || (names.length === 1 && names[0] === "")) {
    targetDiv.innerHTML =
      '<p class="text-slate-400 text-center text-xs pt-4">此任务无打卡点</p>';
  } else {
    names.forEach((name, i) => {
      if (!name) return;
      const p = document.createElement("p");
      let textClass = "text-slate-500";
      if (sequence > 0) {
        if (i + 1 < sequence) textClass = "text-slate-400 line-through";
        else if (i + 1 === sequence) textClass = "font-bold text-sky-600";
      }
      p.className = `transition-colors p-1 rounded ${textClass}`;
      p.innerHTML = `<span class="font-mono w-6 inline-block">${
        i + 1
      }.</span>${name}`;
      targetDiv.appendChild(p);
    });
    centerTargetList(sequence);
  }
  const mobileRunStatsLabel = document.getElementById("mobile-run-stats-label");
  if (mobileRunStatsLabel) {
    if (isDrawingNow && draftTotalDist > 0) {
      const drawKm = (draftTotalDist / 1000).toFixed(2);
      const avgSpeed = pythonParams.speed_mps || 1.5;
      const estMin = avgSpeed > 0 ? draftTotalDist / avgSpeed / 60 : 0;
      mobileRunStatsLabel.textContent = `${drawKm} km / ~${estMin.toFixed(
        1,
      )} min`;
    } else {
      const dist = ((currentRunData.total_run_distance_m || 0) / 1000).toFixed(
        2,
      );
      const timeMin = Math.floor((currentRunData.total_run_time_s || 0) / 60);
      const timeSec = Math.floor((currentRunData.total_run_time_s || 0) % 60);
      mobileRunStatsLabel.textContent = `${dist} km / ${String(
        timeMin,
      ).padStart(2, "0")}:${String(timeSec).padStart(2, "0")}`;
    }
  }
  const mobileLiveDistLabel = document.getElementById("mobile-live-dist-label");
  const mobileLiveTimeLabel = document.getElementById("mobile-live-time-label");
  const mobileTotalDistLabel = document.getElementById(
    "mobile-total-dist-label",
  );
  const mobileTotalTimeLabel = document.getElementById(
    "mobile-total-time-label",
  );
  const mobileRemainingTimeLabel = document.getElementById(
    "mobile-remaining-time-label",
  );
  const mobileCurrentLocationLabel = document.getElementById(
    "mobile-current-location-label",
  );

  if (mobileLiveDistLabel) {
    mobileLiveDistLabel.textContent = `${liveKm} km`;
  }
  if (mobileLiveTimeLabel) {
    mobileLiveTimeLabel.textContent = `${mm}:${ss}`;
  }
  if (mobileTotalDistLabel) {
    mobileTotalDistLabel.textContent = `${totalDistKm} km`;
  }
  if (mobileTotalTimeLabel) {
    const totalTimeMin = Math.floor(
      (currentRunData.total_run_time_s || 0) / 60,
    );
    const totalTimeSec = Math.floor(
      (currentRunData.total_run_time_s || 0) % 60,
    );
    mobileTotalTimeLabel.textContent = `${String(totalTimeMin).padStart(
      2,
      "0",
    )}:${String(totalTimeSec).padStart(2, "0")}`;
  }
  if (mobileRemainingTimeLabel) {
    mobileRemainingTimeLabel.textContent = formatMMSS(remainingTimeS);
  }
  if (mobileCurrentLocationLabel && currentRunData) {
    const currentLocationLabel = document.getElementById(
      "current-location-label",
    );
    if (currentLocationLabel) {
      const coordsText = currentLocationLabel.textContent.replace(
        "当前位置GPS坐标: ",
        "",
      );
      mobileCurrentLocationLabel.textContent = `当前位置: ${coordsText}`;
    }
  }
  renderMobileCheckpointsList();
}
function centerTargetList(sequence) {
  const targetDiv = $("target-points-text");
  if (!targetDiv || !targetDiv.children || targetDiv.children.length === 0)
    return;
  const idx = Math.max(
    0,
    Math.min(targetDiv.children.length - 1, (sequence || 1) - 1),
  );
  const child = targetDiv.children[idx];
  if (child && typeof child.scrollIntoView === "function") {
    try {
      child.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (_) {}
  }
}
function resetMapView() {
  if (!map) return;
  const overlays = collectSingleMapFitOverlays(true);

  if (overlays.length > 0) {
    map.setFitView(overlays, false, [60, 60, 60, 60]);
  } else if (currentRunData && currentRunData.target_points?.length > 0) {
    const targetLngLats = currentRunData.target_points.map(
      (p) => new AMapInstance.LngLat(p[0], p[1]),
    );
    map.setFitView(targetLngLats, false, [60, 60, 60, 60]);
  } else {
    map.setZoomAndCenter(17, [113.390342, 22.527403]);
  }
}

function forceProjectionRefresh() {
  if (!map) return;
  try {
    map.setStatus({ dragEnable: false });
    map.resize();
    requestAnimationFrame(() => {
      const overlays = collectSingleMapFitOverlays(false);
      if (overlays.length > 0) {
        map.setFitView(overlays, false, [60, 60, 60, 60]);
      } else if (
        currentRunData &&
        Array.isArray(currentRunData.target_points) &&
        currentRunData.target_points.length > 0
      ) {
        const pts = currentRunData.target_points.map(
          (p) => new AMapInstance.LngLat(p[0], p[1]),
        );
        map.setFitView(pts, false, [60, 60, 60, 60]);
      } else {
        map.setZoomAndCenter(17, [113.390342, 22.527403]);
      }
      map.setStatus({ dragEnable: true });
    });
  } catch (e) {
    logMessage_Warning("forceProjectionRefresh warning:", e);
  }
}
function forceProjectionRefresh() {
  if (!map) return;
  try {
    map.setStatus({ dragEnable: false });
    map.resize();
    requestAnimationFrame(() => {
      const overlays = collectSingleMapFitOverlays(false);
      if (overlays.length > 0) {
        map.setFitView(overlays, false, [60, 60, 60, 60]);
      } else if (
        currentRunData &&
        Array.isArray(currentRunData.target_points) &&
        currentRunData.target_points.length > 0
      ) {
        const pts = currentRunData.target_points.map(
          (p) => new AMapInstance.LngLat(p[0], p[1]),
        );
        map.setFitView(pts, false, [60, 60, 60, 60]);
      } else {
        map.setZoomAndCenter(17, [113.390342, 22.527403]);
      }
      map.setStatus({ dragEnable: true });
    });
  } catch (e) {
    logMessage_Warning("forceProjectionRefresh warning:", e);
  }
}

function drawAmapRunRoute(data) {
  const runCoords = normalizeRouteCoords(data?.run_coords || []);
  if (runCoords.length < 2) return;
  const routeSegments = hasActiveRouteProgress(data)
    ? buildProviderRouteProgressSegmentsByProgress(runCoords, data)
    : null;
  const drawableSegments = Array.isArray(routeSegments) && routeSegments.length > 0
    ? routeSegments
    : splitRouteCoordsIntoDrawableSegments(runCoords).map((segment) => ({
        styleId: "route",
        coords: segment,
      }));
  const lines = drawableSegments
    .map((segment) => {
      const segmentCoords = normalizeRouteCoords(segment.coords);
      if (segmentCoords.length < 2) return null;
      const styleId = segment.styleId || "route";
      return new AMapInstance.Polyline({
        path: segmentCoords.map((p) => new AMapInstance.LngLat(p.lng, p.lat)),
        // 与其它供应商一致：灰=已跑、蓝=正在走、红=待执行
        strokeColor: resolveProviderRouteSegmentColor(styleId, "#ef4444", {}),
        strokeWeight: styleId === "completed" ? 4 : 5,
        strokeStyle: "dashed",
        lineCap: "round",
        strokeOpacity: 0.85,
        zIndex: styleId === "current" ? 55 : 50,
      });
    })
    .filter(Boolean);
  if (lines.length === 0) return;
  polylines.run = lines;
  map.add(lines);
  amapRouteProgressSegments = { lines, segments: drawableSegments };
}

/** 运行中就地更新分段着色（不整图重绘、不重新适配视野）。
 *
 * 返回 true 表示已就地更新完成，调用方不应再走整图重绘。
 */
function updateTaskProgressSegmentsInPlace(data) {
  if (!data || !data.run_coords?.length || !hasActiveRouteProgress(data)) {
    return false;
  }
  const provider = getActiveMapProvider();

  if (provider === "amap") {
    if (!AMapInstance || !map) return false;
    const cached = amapRouteProgressSegments;
    if (!cached || !Array.isArray(cached.lines) || cached.lines.length === 0) {
      return false;
    }
    const route = normalizeRouteCoords(data.run_coords);
    const segments = buildProviderRouteProgressSegmentsByProgress(route, data);
    if (!Array.isArray(segments) || segments.length === 0) return false;
    if (segments.length !== cached.lines.length) return false;
    try {
      segments.forEach((segment, index) => {
        const line = cached.lines[index];
        if (!line) return;
        const styleId = segment.styleId || "route";
        const segmentCoords = normalizeRouteCoords(segment.coords);
        const options = {
          strokeColor: resolveProviderRouteSegmentColor(styleId, "#ef4444", {}),
          strokeWeight: styleId === "completed" ? 4 : 5,
          zIndex: styleId === "current" ? 55 : 50,
        };
        if (typeof line.setOptions === "function") line.setOptions(options);
        if (typeof line.setPath === "function") {
          line.setPath(
            segmentCoords.map((p) => new AMapInstance.LngLat(p.lng, p.lat)),
          );
        }
      });
    } catch (e) {
      logMessage_Warning("[地图] 就地更新高德分段失败:", e);
      return false;
    }
    cached.segments = segments;
    return true;
  }

  if (typeof updateProviderRouteProgressSegmentsInPlace !== "function") {
    return false;
  }
  const results = getSingleProviderMapContainerIds().map((containerId) =>
    updateProviderRouteProgressSegmentsInPlace(containerId, data),
  );
  return results.length > 0 && results.every(Boolean);
}

function drawOnMap_signature(options = {}) {
  const data = currentRunData;
  if (!data) return;

  // 运行中进度推进：只就地更新分段折线颜色/几何，
  // 不重建覆盖物、不重新适配视野（否则地图会在每次 GPS 更新时复位）
  if (
    options.resetView === false &&
    data.run_coords?.length > 1 &&
    typeof updateTaskProgressSegmentsInPlace === "function" &&
    updateTaskProgressSegmentsInPlace(data)
  ) {
    return;
  }

  if (getActiveMapProvider() !== "amap") {
    getSingleProviderMapContainerIds().forEach((containerId) => {
      drawProviderTaskOnMap(containerId, data);
    });
    return;
  }
  if (!AMapInstance) return;
  if (!map) return;
  clearMapOverlays();

  if (data.recommended_coords?.length > 0) {
    let segment = [];
    data.recommended_coords.forEach((p) => {
      if (p[0] === 0 && p[1] === 0) {
        if (segment.length > 1)
          polylines.recommended.push(
            new AMapInstance.Polyline({
              path: segment,
              strokeColor: "#10b981",
              strokeWeight: 5,
              lineCap: "round",
              strokeOpacity: 0.6,
              zIndex: 40,
            }),
          );
        segment = [];
      } else {
        segment.push(new AMapInstance.LngLat(p[0], p[1]));
      }
    });
    if (segment.length > 1)
      polylines.recommended.push(
        new AMapInstance.Polyline({
          path: segment,
          strokeColor: "#10b981",
          strokeWeight: 5,
          lineCap: "round",
          strokeOpacity: 0.6,
          zIndex: 40,
        }),
      );
    map.add(polylines.recommended);
  }
  if (data.draft_coords?.length > 0) {
    polylines.draft = new AMapInstance.Polyline({
      path: data.draft_coords.map((p) => new AMapInstance.LngLat(p[0], p[1])),
      strokeColor: "#1f2937",
      strokeWeight: 6,
      zIndex: 45,
    });
    map.add(polylines.draft);
  }
  if (data.run_coords?.length > 0) {
    drawAmapRunRoute(data);
  }
  drawMarkers();
  // 只有在调用方明确要求时才复位视野。
  // 历史实现在这里无条件 resetMapView()，而 updateRunnerPosition 每次 GPS
  // 更新都会调用本函数，导致地图被反复复位（用户无法缩放/拖动）。
  if (options.resetView !== false) {
    resetMapView();
  }
}

function drawOnMap() {
  drawOnMap_signature();
  setTimeout(() => {
    logMessage_Info("执行二次渲染以修正初始位移...", "DEBUG");
    drawOnMap_signature();
  }, 100);
}

function drawMarkers() {
  if (!map) return;
  map.remove(markers);
  markers = [];
  const data = currentRunData;
  if (!data?.target_points?.length) return;
  const sequence = resolveVisualTaskProgressSequence(
    data,
    data.run_coords?.length ? data.run_coords : data.draft_coords || [],
  );
  const names = (data.target_point_names || "").split("|");
  data.target_points.forEach((p, i) => {
    let bgColor = "bg-emerald-600",
      textColor = "text-white",
      zIndex = 100,
      pulseClass = "";
    if (i + 1 < sequence) {
      bgColor = "bg-slate-400";
    } else if (i + 1 === sequence) {
      bgColor = "bg-sky-600";
      zIndex = 110;
      pulseClass = "pulsing-marker";
    }
    const pointName = names[i] || `点 ${i + 1}`;
    const markerContent = `<div class="relative flex flex-col items-center pointer-events-none"><div class="${pulseClass} text-xs font-bold whitespace-nowrap px-2 py-1 rounded-full shadow-lg ${bgColor} ${textColor}">${pointName}</div><div class="w-0 h-0 border-x-4 border-x-transparent border-t-4 ${bgColor.replace(
      "bg-",
      "border-t-",
    )}"></div></div>`;
    const marker = new AMapInstance.Marker({
      position: new AMapInstance.LngLat(p[0], p[1]),
      content: markerContent,
      anchor: "bottom-center",
      zIndex: zIndex,
    });
    markers.push(marker);
  });
  map.add(markers);
}

let draftPath = [],
  draftPathLngLat = [],
  pendingPoints = [],
  isUpdating = false,
  lastMouseMoveTime = 0;
const MOUSE_MOVE_THROTTLE_MS = 70;
const MIN_DRAW_DISTANCE_M = 12;

function fastDistanceMeters(lon1, lat1, lon2, lat2) {
  return Math.sqrt(
    Math.pow((lon1 - lon2) * 102834.74, 2) +
      Math.pow((lat1 - lat2) * 111712.69, 2),
  );
}

function scheduleUpdate() {
  if (isUpdating) return;
  isUpdating = true;
  requestAnimationFrame(() => {
    if (pendingPoints.length > 0) {
      const batch = pendingPoints.splice(0, pendingPoints.length);
      batch.forEach((pt) => {
        const lngLat = new AMapInstance.LngLat(pt.lng, pt.lat);
        draftPath.push(pt);
        draftPathLngLat.push(lngLat);
        if (draftPathLngLat.length > 1) {
          const prev = draftPathLngLat[draftPathLngLat.length - 2];
          draftTotalDist += fastDistanceMeters(
            prev.lng,
            prev.lat,
            pt.lng,
            pt.lat,
          );
        }
        checkTargetReachedOnDraw(lngLat, pt.isKey === 1);
      });
      if (!polylines.draft) {
        polylines.draft = new AMapInstance.Polyline({
          path: draftPathLngLat,
          strokeColor: "#1f2937",
          strokeWeight: 6,
          zIndex: 45,
        });
        map.add(polylines.draft);
      } else {
        polylines.draft.setPath(draftPathLngLat);
      }
      updateDrawingInfo(draftPathLngLat[draftPathLngLat.length - 1]);
      updateDashboard();
    }
    isUpdating = false;
    if (pendingPoints.length > 0) scheduleUpdate();
  });
}

function onMapMouseDown(e) {
  if (e.originEvent.button !== 0) return;
  leftMouseDown = true;
  if (isDrawing) {
    isPathDrawing = true;
    pendingPoints.push({
      lng: e.lnglat.lng,
      lat: e.lnglat.lat,
      isKey: 0,
    });
    scheduleUpdate();
  }
}
function onMapMouseMove(e) {
  const now = performance.now();
  if (now - lastMouseMoveTime < MOUSE_MOVE_THROTTLE_MS) return;
  lastMouseMoveTime = now;
  if (isDrawing && isPathDrawing && leftMouseDown) {
    const lastPos = draftPath[draftPath.length - 1];
    if (
      !lastPos ||
      fastDistanceMeters(lastPos.lng, lastPos.lat, e.lnglat.lng, e.lnglat.lat) >
        MIN_DRAW_DISTANCE_M
    ) {
      pendingPoints.push({
        lng: e.lnglat.lng,
        lat: e.lnglat.lat,
        isKey: 0,
      });
      scheduleUpdate();
    } else {
      updateDrawingInfo(e.lnglat);
    }
  }
}
function onMapMouseUp(e) {
  leftMouseDown = false;
  if (isDrawing && isPathDrawing) {
    isPathDrawing = false;
    scheduleUpdate();
  }
  if (pendingUnlockMap) {
    map.setStatus({ dragEnable: true });
    pendingUnlockMap = false;
  }
}
function checkTargetReachedOnDraw(currentLngLat, isForcedKeyPoint = false) {
  if (
    !currentRunData?.target_points ||
    currentRunData.target_points.length === 0
  )
    return;
  let seq = currentRunData.target_sequence || 1;
  if (seq > currentRunData.target_points.length) return;
  const [tarLon, tarLat] = currentRunData.target_points[seq - 1];
  const dist = fastDistanceMeters(
    currentLngLat.lng,
    currentLngLat.lat,
    tarLon,
    tarLat,
  );
  const range = currentRunData.target_range_m || 0.0;
  if (dist <= range && !currentRunData.isInTargetZone) {
    currentRunData.isInTargetZone = true;
    const targetName =
      (currentRunData.target_point_names || "").split("|")[seq - 1] ||
      `打卡点${seq}`;
    logMessage_Info(`到达打卡点 ${seq}: ${targetName}`);
    if (isForcedKeyPoint) {
      pendingPoints.push({ lng: tarLon, lat: tarLat, isKey: 1 });
      scheduleUpdate();
    }
    if (seq < currentRunData.target_points.length) {
      currentRunData.target_sequence = seq + 1;
      updateDashboard();
      drawMarkers();
    } else {
      logMessage_Info("已到达所有打卡点！");
      if (isDrawing) {
        toggleRecordMode(true);
      }
    }
  } else if (dist > range && currentRunData.isInTargetZone) {
    currentRunData.isInTargetZone = false;
  }
}
function updateDrawingInfo(lnglat) {
  if (!isDrawing) {
    if (drawingInfoMarker) drawingInfoMarker.hide();
    return;
  }
  const avgSpeed = pythonParams.speed_mps || 1.5;
  const estTime = avgSpeed > 0 ? draftTotalDist / avgSpeed : 0;
  const timeStr = `${Math.floor(estTime / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(estTime % 60)
    .toString()
    .padStart(2, "0")}`;
  if (!drawingInfoMarker) {
    drawingInfoMarker = new AMapInstance.Text({
      anchor: "bottom-left",
      offset: new AMapInstance.Pixel(10, -10),
      style: {
        "background-color": "rgba(255, 255, 255, 0.9)",
        border: "1px solid #94a3b8",
        padding: "4px 8px",
        "border-radius": "10px",
        "font-size": "12px",
        color: "#1e293b",
      },
    });
    map.add(drawingInfoMarker);
  }
  drawingInfoMarker.setText(
    `距离: ${draftTotalDist.toFixed(0)} m | 预估: ~${timeStr}`,
  );
  drawingInfoMarker.setPosition(lnglat);
  drawingInfoMarker.show();
}

let pendingUnlockMap = false;

async function toggleRecordMode() {
  const btn = $("record-button");
  isDrawing = !isDrawing;
  if (isDrawing) {
    if (selectedTaskIndex === -1) {
      // showModalAlert("请先选择一个任务！");
      swal.fire({
        title: "请先选择一个任务！",
        icon: "info",
        text: "在录制路径前，需要先从任务列表中选择一个任务。",
      });
      isDrawing = false;
      return;
    }
    btn.innerHTML = "结束绘制";
    btn.classList.remove("btn-success");
    btn.classList.add("btn-danger");
    $("map-container").classList.add("drawing");
    // 先等待清理完成，避免异步重置 target_sequence 导致首个打卡点样式偶发错误
    await clearCurrentPath((confirm = false), (showAlert = false));
    currentRunData.target_sequence = 1;
    currentRunData.isInTargetZone = false;
    draftTotalDist = 0;
    updateDashboard();
    drawMarkers();
    map.setStatus({ dragEnable: false });
    resetMapView();
    logMessage_Info("进入录制模式。请在地图上按下左键并拖动来绘制路径。");
  } else {
    btn.innerHTML = "录制路径";
    btn.classList.remove("btn-danger");
    btn.classList.add("btn-success");
    $("map-container").classList.remove("drawing");
    pendingUnlockMap = true;
    isPathDrawing = false;
    if (drawingInfoMarker) drawingInfoMarker.hide();

    // ========== 路径距离校验 ==========
    if (draftTotalDist > 50000) {
      showModalAlert(
        "路径过长（>" +
          (draftTotalDist / 1000).toFixed(2) +
          "km > 50km），请重新录制",
      );
      discardBlackDraftPolyline();
      logMessage_Warning(
        `路径录制失败：距离${(draftTotalDist / 1000).toFixed(2)}km超过50km限制`,
      );
      currentRunData.target_sequence = 0;
      draftTotalDist = 0;
      updateDashboard();
      drawMarkers();
      resetMapView();
      return;
    }
    const totalTargets = currentRunData.target_points?.length || 0;
    const inLastZone =
      totalTargets > 0 &&
      currentRunData.target_sequence >= totalTargets &&
      currentRunData.isInTargetZone === true;
    if (inLastZone) {
      if (draftPath.length > 0) {
        await callPythonAPI("set_draft_path", draftPath);
        await processCurrentPath();
      }
    } else {
      discardBlackDraftPolyline();
      logMessage_Info("未达到最后打卡点，已舍弃路径。");
    }
    currentRunData.target_sequence = 0;
    draftTotalDist = 0;
    updateDashboard();
    drawMarkers();
    resetMapView();
  }
}
async function clearCurrentPath(confirm = true, showAlert = true) {
  // 步骤1: 检查 currentRunData 中的 draft_coords 和 run_coords 是否同时为空或不存在
  // 如果两者都没有数据，则提示用户"当前任务没有可清除的路径"并返回
  const draftEmpty =
    !currentRunData?.draft_coords || currentRunData.draft_coords.length === 0; // 检查 draft_coords 是否为空或不存在
  const runEmpty =
    !currentRunData?.run_coords || currentRunData.run_coords.length === 0; // 检查 run_coords 是否为空或不存在
  if (draftEmpty && runEmpty) {
    // 如果两者都为空，向用户显示提示信息
    if (showAlert) {
      showModalAlert("当前任务没有可清除的路径");
    }
    return; // 提前返回，不执行后续清除逻辑
  }

  // 步骤2: 检查后台任务是否正在执行中
  // 调用 /api/background_task/status API 获取任务状态
  try {
    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status", // 使用完整的API路径
      "GET", // HTTP GET 请求
      null, // 无请求体
    );
    // 如果任务状态为 "running"，说明任务正在执行，无法清除路径
    if (statusRes?.success && statusRes?.task_status?.status === "running") {
      showModalAlert("任务正在执行中，无法清除路径"); // 提示用户任务正在执行
      return; // 提前返回，不执行后续清除逻辑
    }
  } catch (e) {
    // 如果获取任务状态失败，使用项目统一的日志函数记录错误
    logMessage_Error("获取后台任务状态失败:", e);
    // 这里选择继续执行清除逻辑，因为无法确定任务状态
  }

  // 步骤3: 如果需要用户确认，则弹出确认对话框
  if (confirm) {
    const userConfirmed = await jsShowConfirm(
      "确认操作",
      "确认清除当前任务已生成的路径吗？",
    );
    if (!userConfirmed) return; // 用户取消操作，提前返回
  }

  // 步骤4: 调用后端API清除当前任务的草稿数据
  const clearResult = await callPythonAPI("clear_current_task_draft");
  if (!clearResult?.success) {
    if (confirm) {
      // 用户主动确认清除时，若后端失败则中止并提示，避免前后端数据不一致
      showModalAlert(
        "清除路径失败: " + (clearResult?.message || "未知错误"),
        "错误",
      );
      return;
    }
    // 非交互模式（如录制路径前重置）记录警告后继续执行本地清除
    logMessage_Warning(
      "后端清除路径失败，继续清除本地状态: " +
        (clearResult?.message || "未知错误"),
    );
  }

  // 步骤5: 清除地图上的各种折线图层
  if (polylines.draft) {
    removeSingleMapOverlay(polylines.draft); // 移除草稿路径折线
    polylines.draft = null; // 将引用置为null
  }
  if (polylines.history) {
    removeSingleMapOverlay(polylines.history); // 移除历史路径折线
    polylines.history = null; // 将引用置为null
  }
  if (polylines.run) {
    removeSingleMapOverlay(polylines.run); // 移除运行路径折线
    polylines.run = null; // 将引用置为null
  }

  // 步骤6: 删除地图上的当前位置标记（runnerMarker）
  if (runnerMarker) {
    removeSingleMapOverlay(runnerMarker); // 移除跑步者位置标记
    runnerMarker = null; // 将引用置为null
  }

  // 步骤7: 隐藏绘制信息标记（如果存在）
  if (drawingInfoMarker) drawingInfoMarker.hide();

  // 步骤8: 调用 drawMarkers() 来恢复地图上的打卡点样式
  drawMarkers();

  // 步骤9: 重置本地草稿路径相关变量
  draftPath = []; // 清空草稿路径数组
  draftPathLngLat = []; // 清空草稿路径经纬度数组
  draftTotalDist = 0; // 重置草稿总距离

  // 步骤10: 重置 currentRunData 中的相关数据
  if (currentRunData) {
    currentRunData.draft_coords = []; // 清空草稿坐标
    currentRunData.run_coords = []; // 清空运行坐标
    currentRunData.total_run_distance_m = 0; // 重置总运行距离
    currentRunData.total_run_time_s = 0; // 重置总运行时间
    // 重置打卡点状态 (恢复到刚拉取时的状态)
    currentRunData.target_sequence = 0;
    currentRunData.isInTargetZone = false;
  }

  // 步骤11: 更新当前任务列表中对应任务的数据
  if (selectedTaskIndex !== -1 && currentTasks[selectedTaskIndex]) {
    currentTasks[selectedTaskIndex].draft_coords = []; // 清空任务的草稿坐标
    currentTasks[selectedTaskIndex].run_coords = []; // 清空任务的运行坐标
  }

  // 步骤12: 更新仪表盘显示
  updateDashboard();

  // 步骤13: 重新渲染任务列表
  renderTaskList();

  // 步骤14: 重新绘制地图标记 (应用重置后的状态)
  drawMarkers();
}
async function discardBlackDraftPolyline() {
  try {
    if (polylines.draft) {
      map.remove(polylines.draft);
      polylines.draft = null;
    }
    draftPath = [];
    draftPathLngLat = [];
    pendingPoints = [];
    isUpdating = false;
    isPathDrawing = false;
    leftMouseDown = false;
    draftTotalDist = 0;
    if (drawingInfoMarker) drawingInfoMarker.hide();
    await callPythonAPI("set_draft_path", []);
    if (selectedTaskIndex !== -1 && currentTasks[selectedTaskIndex]) {
      currentTasks[selectedTaskIndex].draft_coords = [];
      renderTaskList();
    }
    if (currentRunData) currentRunData.draft_coords = [];
  } catch (e) {
    logMessage_Error("discardBlackDraftPolyline() error:", e);
  }
}
async function processCurrentPath() {
  if (draftPath && draftPath.length > 0) {
    logMessage_Info("正在保存草稿路径...");
    await callPythonAPI("set_draft_path", draftPath);
  }
  const result = await callPythonAPI("process_path");
  if (result.success) {
    currentRunData.run_coords = result.run_coords;
    currentRunData.total_run_distance_m = result.total_dist;
    currentRunData.total_run_time_s = result.total_time;
    drawOnMap();
    updateDashboard();
    renderTaskList();
    discardBlackDraftPolyline();
    singleProcessedPoints = 0;
    singleTotalPoints = currentRunData.run_coords?.length || 0;
    updateSingleProgress(0, "0 / " + singleTotalPoints + " 点");
  } else {
    showModalAlert(result.message);
  }
}
async function toggleRun() {
  const btn = $("start-run-button");
  runAccumulatedMs = 0;

  if (btn.textContent === "开始执行") {
    // ========== 添加欠费检查 ==========
    // 按当前模式执行欠费检查：
    // - 单账号模式：只检查当前账号
    // - 多账号模式：只检查 multi-account-list / mobile-multi-account-list 中的账号
    // - 仅在 pricing-require-payment_modal 启用时执行
    const canStart = await _checkOverdueBeforeStartByCurrentMode();
    if (!canStart) {
      // 欠费检查未通过，直接返回不启动任务
      return;
    }
    const overdueOverride = _consumeOverdueForceOverride();
    // ========== 欠费检查结束 ==========

    const autoGen = $("auto-gen-all-check").checked;
    if (selectedTaskIndex < 0) {
      showModalAlert("请先选择任务");
      return;
    }
    if (currentRunData) {
      currentRunData.target_sequence = 1;
      currentRunData.isInTargetZone = false;
      updateDashboard();
      drawMarkers();
    }
    const currentSchoolUsername = String(
      currentUserData?.student_id || "",
    ).trim();
    const result = await callPythonAPI_raw(
      "/api/background_task/start",
      "POST",
      {
        task_indices: [selectedTaskIndex],
        auto_generate: autoGen,
        school_username: currentSchoolUsername || undefined,
        ...overdueOverride,
      },
    );

    // 检查是否是欠费错误
    // 后端在检测到欠费时会返回特定的错误代码
    if (!result.success && result.error_code === "OVERDUE_PAYMENT") {
      // 构建欠费账号列表的显示文本
      let overdueList = "";
      if (result.overdue_accounts && result.overdue_accounts.length > 0) {
        // 遍历每个欠费账号，格式化为易读的文本
        // 例如：账号1 (欠费3次)
        overdueList = result.overdue_accounts
          .map((acc) => `${acc.school_username} (欠费${acc.overdue_count}次)`)
          .join("\n");
      }

      // 构建完整的提示消息
      const message = `检测到以下账号存在欠费：\n\n${overdueList}\n\n请先完成缴费后再执行任务。`;

      // 显示友好的弹窗提示
      // 使用 showModalAlert 确保用户看到提示信息
      showModalAlert(message, "欠费提示");

      // 可选：自动跳转到缴费页面（如果需要的话）
      // switchToTab('tab4'); // 取消注释此行以启用自动跳转

      // 阻止任务启动，直接返回
      return;
    }

    if (result.success) {
      activeTaskMapProviderLock = getActiveMapProvider();
      btn.textContent = "停止";
      btn.classList.remove("btn-primary");
      btn.classList.add("btn-danger");
      updateSingleProgress(0, "0 / 0 点");
      setTimeout(() => startBackgroundTaskPolling(), 500);
    } else {
      // 其他错误（非欠费），显示标准错误消息
      showModalAlert(result.message);
    }
  } else {
    await callPythonAPI_raw("/api/background_task/stop", "POST", {});
    btn.textContent = "开始执行";
    btn.classList.remove("btn-danger");
    btn.classList.add("btn-primary");
    clearTaskMapAutoResetTimer();
    stopBackgroundTaskPolling();
    clearSingleExecutionVisuals();
  }
}
async function toggleAllRuns() {
  const btn = $("start-all-button");
  runAccumulatedMs = 0;

  if (btn.textContent === "执行所有") {
    // ========== 添加欠费检查 ==========
    // 按当前模式执行欠费检查：
    // - 单账号模式：只检查当前账号
    // - 多账号模式：只检查 multi-account-list / mobile-multi-account-list 中的账号
    // - 仅在 pricing-require-payment_modal 启用时执行
    const canStart = await _checkOverdueBeforeStartByCurrentMode();
    if (!canStart) {
      // 欠费检查未通过，直接返回不启动任务
      return;
    }
    const overdueOverride = _consumeOverdueForceOverride();
    // ========== 欠费检查结束 ==========

    const ignoreCompleted = $("run-completed-check").checked;
    const autoGen = $("auto-gen-all-check").checked;
    const taskIndices = [];
    for (let i = 0; i < currentTasks.length; i++) {
      const task = currentTasks[i];
      if (task.status == 1 && !ignoreCompleted) continue;
      const infoText = task.info_text || "";

      if (infoText === "已过期") {
        continue;
      }
      if (infoText.startsWith("开始于")) {
        continue;
      }
      taskIndices.push(i);
    }
    if (taskIndices.length === 0) {
      showModalAlert("没有可执行的任务");
      return;
    }
    if (currentRunData) {
      currentRunData.target_sequence = 1;
      currentRunData.isInTargetZone = false;
      updateDashboard();
      drawMarkers();
    }
    const multiUsernames = _isInMultiAccountModeForOverdueCheck()
      ? _getMultiAccountListUsernames()
      : [];
    const currentSchoolUsername = String(
      currentUserData?.student_id || "",
    ).trim();
    const result = await callPythonAPI_raw(
      "/api/background_task/start",
      "POST",
      {
        task_indices: taskIndices,
        auto_generate: autoGen,
        school_usernames: multiUsernames.length ? multiUsernames : undefined,
        school_username:
          !multiUsernames.length && currentSchoolUsername
            ? currentSchoolUsername
            : undefined,
        ...overdueOverride,
      },
    );
    if (!result.success && result.error_code === "OVERDUE_PAYMENT") {
      let overdueList = "";
      if (result.overdue_accounts && result.overdue_accounts.length > 0) {
        overdueList = result.overdue_accounts
          .map((acc) => `${acc.school_username} (欠费${acc.overdue_count}次)`)
          .join("\n");
      }
      const message = `检测到以下账号存在欠费：\n\n${overdueList}\n\n请先完成缴费后再执行任务。`;
      showModalAlert(message, "欠费提示");
      return;
    }
    if (result.success) {
      activeTaskMapProviderLock = getActiveMapProvider();
      btn.textContent = "全部停止";
      btn.classList.remove("btn-secondary");
      btn.classList.add("btn-danger");
      updateSingleProgress(0, `0 / ${taskIndices.length} 任务`);
      setTimeout(() => startBackgroundTaskPolling(), 500);
    } else {
      showModalAlert(result.message);
    }
  } else {
    await callPythonAPI_raw("/api/background_task/stop", "POST", {});
    btn.textContent = "执行所有";
    btn.classList.remove("btn-danger");
    btn.classList.add("btn-secondary");
    clearTaskMapAutoResetTimer();
    stopBackgroundTaskPolling();
    clearSingleExecutionVisuals();
  }
}
// ========== 后台任务管理函数 ==========
let backgroundTaskPollInterval = null;
let backgroundTaskStartTime = 0;
let backgroundTaskStatusRequest = 0;

function startBackgroundTaskPolling() {
  if (backgroundTaskPollInterval) {
    clearInterval(backgroundTaskPollInterval);
  }
  backgroundTaskStartTime = Date.now();
  pollBackgroundTaskStatus();
  backgroundTaskPollInterval = setInterval(pollBackgroundTaskStatus, 3000);
}
function stopBackgroundTaskPolling() {
  backgroundTaskStatusRequest++;
  pollingTaskMapRequest++;
  pollingTaskMapPending = null;
  if (backgroundTaskPollInterval) {
    clearInterval(backgroundTaskPollInterval);
    backgroundTaskPollInterval = null;
  }
  backgroundTaskStartTime = 0;
}
function getLegacyActiveTaskIndex(status) {
  const index = Object.prototype.hasOwnProperty.call(status, "active_task_index")
    ? status.active_task_index
    : status.task_indices?.[status.current_task_index];
  return Number.isInteger(index) && index >= 0 ? index : null;
}
function mergeLegacyRunnerProgress(status) {
  const previousPoint = Number(status.current_position?.point_index ?? status.singleProcessedPoints ?? -1);
  const latestPoint = Number(currentRunData?.current_point_index ?? -1);
  if (currentRunData?.task_index !== getLegacyActiveTaskIndex(status) || !Number.isFinite(latestPoint) || latestPoint <= previousPoint) return status;
  const position = currentRunData.current_position;
  const lon = position?.lon ?? position?.lng ?? currentRunData.current_lon;
  const lat = position?.lat ?? currentRunData.current_lat;
  const distance = currentRunData.distance_covered_m ?? status.current_distance_m;
  const sequence = currentRunData.target_sequence;
  return {
    ...status, singleProcessedPoints: latestPoint,
    current_distance_m: distance,
    checked_targets_count: sequence ?? status.checked_targets_count,
    elapsed_time_s: Math.max(Number(status.elapsed_time_s) || 0, runAccumulatedMs / 1000),
    ...(Number.isFinite(lon) && Number.isFinite(lat) ? {
      current_position: { lon, lat, distance, point_index: latestPoint, target_sequence: Math.max(0, (Number(sequence) || 1) - 1) },
    } : {}),
  };
}
async function pollBackgroundTaskStatus() {
  const request = ++backgroundTaskStatusRequest;
  const requestSession = sessionUUID;
  try {
    const result = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    if (request !== backgroundTaskStatusRequest || requestSession !== sessionUUID) return;
    if (result.success && result.task_status) {
      let status = result.task_status;
      if (!acceptLegacyRunnerExecution(status, true)) return;
      if (status.status === "stopped") {
        activeTaskMapProviderLock = null;
        clearTaskMapAutoResetTimer();
        clearSingleExecutionVisuals();
        return;
      }
      if (status.status === "running") {
        activeTaskMapProviderLock =
          normalizeSupportedMapProvider(status.map_provider) ||
          activeTaskMapProviderLock ||
          getActiveMapProvider();
        singleRunProgressVisualActive = true;
      }
      const activeTaskIndex = getLegacyActiveTaskIndex(status);
      if (activeTaskIndex != null && (
        activeTaskIndex !== selectedTaskIndex || currentRunData?.task_index !== activeTaskIndex ||
        legacyRunnerExecutionState.mapSnapshotKey !== getLegacyTaskMapSnapshotKey(activeTaskIndex) ||
        (status.route_ready === true && !currentRunData?.run_coords?.length) ||
        (status.route_ready === false && currentRunData?.run_coords?.length)
      )) {
        logMessage_Info(`[Polling] 检测到任务切换: ${selectedTaskIndex} -> ${activeTaskIndex}`);
        selectedTaskIndex = activeTaskIndex;
        renderTaskList();
        if (!(await forceLoadTaskDataForPolling(activeTaskIndex, status))) return;
        if (request !== backgroundTaskStatusRequest || requestSession !== sessionUUID) return;
      }
      status = mergeLegacyRunnerProgress(status);
      if (status.run_coords && status.run_coords.length > 0) {
        if (
          !currentRunData ||
          !currentRunData.run_coords ||
          currentRunData.run_coords.length === 0
        ) {
          logMessage_Info("检测到后端已自动生成路径，正在更新前端地图...");
          currentRunData.run_coords = status.run_coords || [];
          currentRunData.target_points = status.target_points || [];
          currentRunData.target_point_names = status.target_point_names || "";
          currentRunData.recommended_coords = status.recommended_coords || [];

          currentRunData.total_run_time_s = status.estimated_total_time_s || 0;
          currentRunData.total_run_distance_m =
            status.estimated_total_distance_m || 0;
          drawOnMap();
          updateDashboard();
        }
      }
      const completedTasks = status.completed_tasks || 0;
      const totalTasks = status.total_tasks || 0;
      const progressPercent = status.progress_percent || 0;
      const currentTaskProgress = status.current_task_progress || 0;
      let pct = 0;
      let displayText = "";
      if (
        status.singleTotalPoints !== undefined &&
        status.singleProcessedPoints !== undefined
      ) {
        singleTotalPoints = status.singleTotalPoints;
        singleProcessedPoints = status.singleProcessedPoints;
        pct = Math.floor(
          (singleProcessedPoints * 100) / Math.max(1, singleTotalPoints),
        );
        displayText = `${singleProcessedPoints} / ${singleTotalPoints} 点`;
      } else if (
        currentRunData &&
        Array.isArray(currentRunData.run_coords) &&
        currentRunData.run_coords.length > 0
      ) {
        singleTotalPoints = currentRunData.run_coords.length;

        if (status.current_position) {
          const currentPointIndex = status.current_position.point_index || 0;
          singleProcessedPoints = Math.min(
            currentPointIndex,
            singleTotalPoints,
          );
        } else {
          singleProcessedPoints = Math.floor(
            (currentTaskProgress / 100) * singleTotalPoints,
          );
        }

        pct = Math.floor(
          (singleProcessedPoints * 100) / Math.max(1, singleTotalPoints),
        );
        displayText = `${singleProcessedPoints} / ${singleTotalPoints} 点`;
      } else {
        singleTotalPoints = 0;
        singleProcessedPoints = 0;
        pct = 0;
        displayText = `${singleProcessedPoints} / ${singleTotalPoints} 点`;
      }

      updateSingleProgress(pct, displayText);
      if (status.elapsed_time_s !== undefined) {
        runAccumulatedMs = status.elapsed_time_s * 1000;
      }
      if (status.current_distance_m !== undefined && currentRunData) {
        currentRunData.distance_covered_m = status.current_distance_m;
      }
      if (status.checked_targets_count !== undefined && currentRunData) {
        currentRunData.target_sequence = status.checked_targets_count;
      }
      updateDashboard();

      drawMarkers();
      if (status.current_position) {
        const pos = status.current_position;
        updateRunnerPosition(
          pos.lon,
          pos.lat,
          pos.distance || 0,
          pos.target_sequence || 0,
          0,
          false,
          pos.point_index,
        );
      }
      const taskStartTime = (status.start_time || 0) * 1000;
      const isOldTask =
        backgroundTaskStartTime > 0 &&
        taskStartTime < backgroundTaskStartTime - 2000;
      if (status.status === "completed") {
        if (!isOldTask) {
          logMessage_Info("后台任务全部完成！");
          showModalAlert("后台任务全部完成！");
        }
        stopBackgroundTaskPolling();
        activeTaskMapProviderLock = null;
        clearTaskMapAutoResetTimer();
        $("start-run-button").textContent = "开始执行";
        $("start-run-button").classList.remove("btn-danger");
        $("start-run-button").classList.add("btn-primary");
        $("start-all-button").textContent = "执行所有";
        $("start-all-button").classList.remove("btn-danger");
        $("start-all-button").classList.add("btn-secondary");
        updateMobileTaskUI("已完成", "所有任务已完成");
        if (!isOldTask) {
          refreshTasks();
        }
      } else if (status.status === "error") {
        const failures = status.route_planning_failures || [];
        const latestFailure = failures[failures.length - 1];
        const errorMsg = latestFailure
          ? `${latestFailure.message}（诊断编号：${latestFailure.diagnostic_id}）`
          : status.error || "未知错误";
        if (!latestFailure) logMessage_Error("后台任务执行出错: " + errorMsg);
        if (!isOldTask) {
          showModalAlert("后台任务执行出错: " + errorMsg);
        }
        stopBackgroundTaskPolling();
        activeTaskMapProviderLock = null;
        clearTaskMapAutoResetTimer();
        $("start-run-button").textContent = "开始执行";
        $("start-run-button").classList.remove("btn-danger");
        $("start-run-button").classList.add("btn-primary");
        $("start-all-button").textContent = "执行所有";
        $("start-all-button").classList.remove("btn-danger");
        $("start-all-button").classList.add("btn-secondary");
        updateMobileTaskUI("错误", errorMsg || "任务执行出错");
      }
    }
  } catch (e) {
    logMessage_Debug("轮询后台任务状态失败:", e);
  }
}
async function checkBackgroundTaskOnLoad() {
  const request = ++backgroundTaskStatusRequest;
  const requestSession = sessionUUID;
  try {
    const result = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    if (request !== backgroundTaskStatusRequest || requestSession !== sessionUUID) return false;

    if (result.success && result.task_status) {
      let status = result.task_status;
      if (!acceptLegacyRunnerExecution(status, true)) return false;
      if (status.status === "running") {
        activeTaskMapProviderLock =
          normalizeSupportedMapProvider(status.map_provider) ||
          activeTaskMapProviderLock ||
          getActiveMapProvider();
        singleRunProgressVisualActive = true;
        logMessage_Info("检测到后台任务正在运行，已恢复状态显示");
        const totalTasks = status.total_tasks || 0;
        if (totalTasks === 1) {
          $("start-run-button").textContent = "停止";
          $("start-run-button").classList.remove("btn-primary");
          $("start-run-button").classList.add("btn-danger");
        } else if (totalTasks > 1) {
          $("start-all-button").textContent = "全部停止";
          $("start-all-button").classList.remove("btn-secondary");
          $("start-all-button").classList.add("btn-danger");
        }
        const global_task_index = getLegacyActiveTaskIndex(status);
        if (global_task_index != null) {
          logMessage_Info(
            `正在恢复运行中的任务 (索引: ${global_task_index}) 的地图数据...`,
          );

          selectedTaskIndex = global_task_index;
          renderTaskList();
          if (!(await forceLoadTaskDataForPolling(global_task_index, status))) return false;
          if (request !== backgroundTaskStatusRequest || requestSession !== sessionUUID) return false;
        }
        status = mergeLegacyRunnerProgress(status);
        const completedTasks = status.completed_tasks || 0;
        const progressPercent = status.progress_percent || 0;
        const currentTaskProgress = status.current_task_progress || 0;
        let pct = 0;
        let displayText = "";
        if (
          status.singleTotalPoints !== undefined &&
          status.singleProcessedPoints !== undefined
        ) {
          singleTotalPoints = status.singleTotalPoints;
          singleProcessedPoints = status.singleProcessedPoints;
          pct = Math.floor(
            (singleProcessedPoints * 100) / Math.max(1, singleTotalPoints),
          );
          displayText = `${singleProcessedPoints} / ${singleTotalPoints} 点`;
        } else if (
          currentRunData &&
          Array.isArray(currentRunData.run_coords) &&
          currentRunData.run_coords.length > 0
        ) {
          singleTotalPoints = currentRunData.run_coords.length;

          if (status.current_position) {
            const currentPointIndex = status.current_position.point_index || 0;
            singleProcessedPoints = Math.min(
              currentPointIndex,
              singleTotalPoints,
            );
          } else {
            singleProcessedPoints = Math.floor(
              (currentTaskProgress / 100) * singleTotalPoints,
            );
          }

          pct = Math.floor(
            (singleProcessedPoints * 100) / Math.max(1, singleTotalPoints),
          );
          displayText = `${singleProcessedPoints} / ${singleTotalPoints} 点`;
        } else {
          singleTotalPoints = 0;
          singleProcessedPoints = 0;
          pct = 0;
          displayText = `${singleProcessedPoints} / ${singleTotalPoints} 点`;
        }

        updateSingleProgress(pct, displayText);
        if (status.elapsed_time_s !== undefined) {
          runAccumulatedMs = status.elapsed_time_s * 1000;
        }
        if (status.current_distance_m !== undefined && currentRunData) {
          currentRunData.distance_covered_m = status.current_distance_m;
        }
        if (status.checked_targets_count !== undefined && currentRunData) {
          currentRunData.target_sequence = status.checked_targets_count;
        }
        updateDashboard();
        if (status.current_position) {
          const pos = status.current_position;
          updateRunnerPosition(
            pos.lon,
            pos.lat,
            pos.distance || 0,
            pos.target_sequence || 0,
            0,
            true,
            pos.point_index,
          );
        }

        startBackgroundTaskPolling();
        return true;
      }
    }
  } catch (e) {
    logMessage_Debug("检查后台任务状态失败:", e);
    return false;
  }
}

function ensureRunnerMarker() {
  if (getActiveMapProvider() !== "amap" || !map || !AMapInstance) return;
  if (runnerMarker) return;
  const content =
    '<div class="w-5 h-5 rounded-full border-2 border-white shadow-lg" style="background:linear-gradient(135deg,var(--base-color-300),var(--base-color-600));"></div>';
  runnerMarker = new AMapInstance.Marker({
    position: map.getCenter(),
    content,
    anchor: "center",
    zIndex: 200,
  });
  map.add(runnerMarker);
}
const legacyRunnerExecutionState = { id: "", startedAt: 0, taskIndex: null, mapSnapshotKey: "", retired: new Set() };
function resetLegacyRunnerExecution() {
  if (legacyRunnerExecutionState.id) legacyRunnerExecutionState.retired.add(legacyRunnerExecutionState.id);
  while (legacyRunnerExecutionState.retired.size > 32) {
    legacyRunnerExecutionState.retired.delete(legacyRunnerExecutionState.retired.values().next().value);
  }
  legacyRunnerExecutionState.id = "";
  legacyRunnerExecutionState.startedAt = 0;
  legacyRunnerExecutionState.taskIndex = null;
  legacyRunnerExecutionState.mapSnapshotKey = "";
}
function acceptLegacyRunnerExecution(data, allowStart = false) {
  if (!data?.execution_id) return !legacyRunnerExecutionState.id;
  const id = String(data.execution_id);
  if (legacyRunnerExecutionState.retired.has(id)) return false;
  const startedAt = Number(data.execution_started_at || 0);
  const taskIndex = data.task_index ?? data.active_task_index;
  const changed = id !== legacyRunnerExecutionState.id;
  if (changed) {
    if (!allowStart && legacyRunnerExecutionState.id) return false;
    if (legacyRunnerExecutionState.id && startedAt <= legacyRunnerExecutionState.startedAt) return false;
  }
  if (changed || (allowStart && Number.isInteger(taskIndex) && taskIndex !== legacyRunnerExecutionState.taskIndex)) {
    if (changed && legacyRunnerExecutionState.id) {
      legacyRunnerExecutionState.retired.add(legacyRunnerExecutionState.id);
      while (legacyRunnerExecutionState.retired.size > 32) {
        legacyRunnerExecutionState.retired.delete(legacyRunnerExecutionState.retired.values().next().value);
      }
    }
    legacyRunnerExecutionState.id = id;
    legacyRunnerExecutionState.startedAt = Math.max(startedAt, legacyRunnerExecutionState.startedAt);
    legacyRunnerExecutionState.taskIndex = taskIndex ?? null;
    legacyRunnerExecutionState.mapSnapshotKey = "";
    if (typeof singleProcessedPoints !== "undefined") singleProcessedPoints = 0;
    if (typeof runAccumulatedMs !== "undefined") runAccumulatedMs = 0;
    if (typeof currentRunData !== "undefined" && currentRunData && (taskIndex == null || currentRunData.task_index === taskIndex)) {
      currentRunData.current_point_index = 0;
      currentRunData.point_index = 0;
      currentRunData.distance_covered_m = 0;
      currentRunData.target_sequence = 0;
      currentRunData.status = "running";
      delete currentRunData.current_position;
    }
  }
  return id === legacyRunnerExecutionState.id;
}
function updateRunnerPosition(
  lon,
  lat,
  distance,
  targetSequence,
  duration,
  centerNow = false,
  currentPointIndex = null,
) {
  if (getActiveMapProvider() !== "amap" || !map || !AMapInstance) {
    runAccumulatedMs += duration || 0;
    const wasVisualActive = singleRunProgressVisualActive;
    singleRunProgressVisualActive = true;
    const previousProgressIndex = currentRunData
      ? resolveRouteProgressIndex(currentRunData, currentRunData.run_coords || [])
      : -1;
    if (currentRunData) {
      currentRunData.current_position = { lng: +lon, lat: +lat };
      if (Number.isFinite(+currentPointIndex) && +currentPointIndex > 0) {
        currentRunData.current_point_index = Math.floor(+currentPointIndex);
      }
    }
    const jsTargetSequence = resolveRunnerTargetSequence(
      targetSequence,
      currentRunData,
    );
    const nextProgressIndex = currentRunData
      ? resolveRouteProgressIndex(currentRunData, currentRunData.run_coords || [])
      : previousProgressIndex;
    // 进度推进时只做「就地着色」：不清空覆盖物、不重新适配视野。
    // 历史实现每前进一个点都会整图重绘并 resetMapView()，导致地图反复复位。
    const progressAdvanced = previousProgressIndex !== nextProgressIndex;
    const structuralChange =
      !wasVisualActive ||
      (!!currentRunData && currentRunData.target_sequence !== jsTargetSequence);
    if (currentRunData) {
      currentRunData.distance_covered_m = distance || 0;
      currentRunData.target_sequence = jsTargetSequence;
    }
    if (getActiveMapProvider() !== "amap" && !getProviderMapInstance("map-container")) {
      initProviderMap("map-container", false);
    }
    if (structuralChange) {
      // 打卡点推进/首次进入运行态：重建标记与分段（此时允许重新适配视野）
      drawOnMap_signature();
    } else if (progressAdvanced) {
      // 仅灰/蓝分界点移动：就地更新颜色，保持当前视野
      drawOnMap_signature({ resetView: false });
    }
    const providerContainerIds = getSingleProviderMapContainerIds();
    providerContainerIds.forEach((containerId) => {
      updateProviderRunnerMarker(containerId, { lng: lon, lat });
    });
    if (centerNow) {
      providerContainerIds.forEach((containerId) => {
        fitProviderMapToCoordinates(containerId, [{ lng: lon, lat }]);
      });
    }
    $("current-location-label").textContent = `当前位置GPS坐标: ${(+lon).toFixed(
      4,
    )}, ${(+lat).toFixed(4)}`;
    const mobileCurrentLocationLabel = document.getElementById(
      "mobile-current-location-label",
    );
    if (mobileCurrentLocationLabel) {
      mobileCurrentLocationLabel.textContent = `当前位置: ${(+lon).toFixed(
        4,
      )}, ${(+lat).toFixed(4)}`;
    }
    updateDashboard();
    return;
  }
  runAccumulatedMs += duration || 0;
  const wasVisualActive = singleRunProgressVisualActive;
  singleRunProgressVisualActive = true;
  const previousProgressIndex = currentRunData
    ? resolveRouteProgressIndex(currentRunData, currentRunData.run_coords || [])
    : -1;
  if (currentRunData) {
    currentRunData.current_position = { lng: +lon, lat: +lat };
    if (Number.isFinite(+currentPointIndex) && +currentPointIndex > 0) {
      currentRunData.current_point_index = Math.floor(+currentPointIndex);
    }
    currentRunData.distance_covered_m = distance || 0;
  }
  $("current-location-label").textContent = `当前位置GPS坐标: ${(+lon).toFixed(
    4,
  )}, ${(+lat).toFixed(4)}`;

  const mobileCurrentLocationLabel = document.getElementById(
    "mobile-current-location-label",
  );
  if (mobileCurrentLocationLabel) {
    mobileCurrentLocationLabel.textContent = `当前位置: ${(+lon).toFixed(
      4,
      )}, ${(+lat).toFixed(4)}`;
  }
  const jsTargetSequence = resolveRunnerTargetSequence(targetSequence, currentRunData);
  const nextProgressIndex = currentRunData
    ? resolveRouteProgressIndex(currentRunData, currentRunData.run_coords || [])
    : previousProgressIndex;
  const progressAdvanced = previousProgressIndex !== nextProgressIndex;
  const structuralChange =
    !wasVisualActive ||
    (!!currentRunData && currentRunData.target_sequence !== jsTargetSequence);
  if (currentRunData) {
    currentRunData.target_sequence = jsTargetSequence;
  }
  if (structuralChange) {
    // 打卡点推进/首次进入运行态：重建标记与分段（允许重新适配视野）
    drawOnMap_signature();
  } else if (progressAdvanced) {
    // 仅灰/蓝分界点移动：就地更新颜色，保持当前视野
    drawOnMap_signature({ resetView: false });
  }
  ensureRunnerMarker();
  const pos = new AMapInstance.LngLat(lon, lat);
  if (runnerMarker) {
    runnerMarker.setPosition(pos);
  }
  if (map && centerNow) map.setCenter(pos);
  updateDashboard();
  if (
    Array.isArray(currentRunData.run_coords) &&
    currentRunData.run_coords.length > 0
  ) {
    singleTotalPoints = currentRunData.run_coords.length;
    singleProcessedPoints = Math.min(
      currentPointIndex != null && Number.isFinite(Number(currentPointIndex))
        ? Math.max(0, Math.floor(Number(currentPointIndex)))
        : singleProcessedPoints + 1,
      singleTotalPoints,
    );
    const pct = Math.floor(
      (singleProcessedPoints * 100) / Math.max(1, singleTotalPoints),
    );
    updateSingleProgress(
      pct,
      `${singleProcessedPoints} / ${singleTotalPoints} 点`,
    );
  }
}

function clearSingleExecutionVisuals() {
  singleRunProgressVisualActive = false;
  if (getActiveMapProvider() === "amap") {
    if (runnerMarker) {
      removeSingleMapOverlay(runnerMarker);
      runnerMarker = null;
    }
  } else {
    getSingleProviderMapContainerIds().forEach((containerId) => {
      clearProviderRunnerMarkers(containerId);
    });
  }
  if (currentRunData && Object.keys(currentRunData).length > 0) {
    drawOnMap_signature();
  }
}

function onTaskCompleted(taskIndex) {
  if (currentTasks[taskIndex]) {
    currentTasks[taskIndex].status = 1;
    renderTaskList();
  }
}
function onRunStopped() {
  logMessage_Info("后台任务已停止（来自服务器推送）。");
  activeTaskMapProviderLock = null;
  clearTaskMapAutoResetTimer();
  stopBackgroundTaskPolling();
  clearSingleExecutionVisuals();
  const startBtn = $("start-run-button");
  if (startBtn) {
    startBtn.textContent = "开始执行";
    startBtn.classList.remove("btn-danger");
    startBtn.classList.add("btn-primary");
    startBtn.disabled = false;
  }
  const startAllBtn = $("start-all-button");
  if (startAllBtn) {
    startAllBtn.textContent = "执行所有";
    startAllBtn.classList.remove("btn-danger");
    startAllBtn.classList.add("btn-secondary");
    startAllBtn.disabled = false;
  }
}

async function exportTask() {
  if (selectedTaskIndex === -1) {
    showModalAlert("请先选择一个要导出的任务！");
    return;
  }
  const result = await callPythonAPI("export_task_data");
  if (result && result.success && result.data) {
    const jsonStr = JSON.stringify(result.data, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.filename || "task_export.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    logMessage_Info("导出成功");
  } else if (result && !result.success) {
    showModalAlert(`导出失败: ${result.message}`);
  }
}
async function importTask() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const modeContext = captureLegacyBusinessContext(true);
    try {
      const text = await file.text();
      if (!isCurrentLegacyBusinessContext(modeContext)) return;
      const result = await callPythonAPI("import_task_data", text);
      if (!isCurrentLegacyBusinessContext(modeContext)) return;
      if (result.success) {
        applyLegacyBusinessMode(result, modeContext);
        currentSessionUA = "NULL";
        const uaLabel = $("ua-label");
        if (uaLabel) uaLabel.textContent = "NULL";
        const uaBtn = $("random-ua-btn");
        if (uaBtn) uaBtn.disabled = true;
        if (result.userInfo) {
          currentUserData = result.userInfo;
          const name = currentUserData.name || "离线调试";
          const sid = currentUserData.student_id || "NULL";
          $("user-name-label").textContent = `姓名: ${name}`;
          $("user-id-label").textContent = `学号: ${sid}`;
        }
        showMainApp();
        const adminBtn = $("show-admin-panel");
        if (adminBtn) {
          adminBtn.classList.remove("hidden");
          logMessage_Info("[离线导入] 管理面板按钮已显示");
        }
        await mapReadyPromise;
        if (!isCurrentLegacyBusinessContext(modeContext)) return;
        currentTasks = result.tasks;
        renderTaskList();
        selectTask(0);
        requestAnimationFrame(() => drawOnMap());
        logMessage_Info("导入成功");
      } else {
        showModalAlert(result.message || "导入失败");
      }
    } catch (error) {
      showModalAlert(`导入失败: ${error.message}`);
    }
  };
  input.click();
}
async function getWalkingPath(waypoints) {
  if (getActiveMapProvider() !== "amap") {
    throw new Error("getWalkingPath 仅支持高德地图；当前供应商请使用后端多地图路径规划。");
  }
  if (!AMapInstance || waypoints.length < 2)
    throw new Error("地图实例未加载或路径点少于2");
  const useFallback = pythonParams.api_fallback_line ?? false,
    maxRetries = pythonParams.api_retries ?? 2,
    retryDelayMs = (pythonParams.api_retry_delay_s ?? 0.5) * 1000,
    queueIntervalMs = (pythonParams.api_queue_interval_s ??0.1) * 1000;
  const maxFailedWaves =2;
  callPythonAPI(
    "js_log",
    "INFO",
    `开始路径规划: 重试=${maxRetries}次, 延迟=${retryDelayMs}ms, 排队间隔=${queueIntervalMs}ms, 备用直线=${useFallback}`,
  );
  const all_path = [];
  const areCoordsEqual = (c1, c2) =>
    Math.abs(c1.lng - c2.lng) < 1e-6 && Math.abs(c1.lat - c2.lat) < 1e-6;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, Math.max(0, ms)));
  const searchSegment = (segmentIndex, start, end) =>
    new Promise((resolve) => {
      callPythonAPI(
        "js_log",
        "DEBUG",
        `AMap API请求 --> 第 ${segmentIndex + 1} 段步行路径: ${start.toString()} 至 ${end.toString()}`,
      );
      new AMap.Walking({
        map: null,
        panel: "",
        hideMarkers: true,
      }).search(start, end, (status, result) => {
        if (status === "complete" && result.routes?.length > 0) {
          const p = [];
          result.routes[0].steps.forEach((s) =>
            s.path.forEach((pt) => p.push({ lng: pt.lng, lat: pt.lat })),
          );
          callPythonAPI(
            "js_log",
            "DEBUG",
            `AMap API响应 <-- 成功，点数: ${p.length}`,
          );
          resolve({ path: p });
        } else {
          let info = result ? result.info || JSON.stringify(result) : "NULL";
          callPythonAPI(
            "js_log",
            "ERROR",
            `AMap API响应 <-- 失败. 状态: ${status}, 结果: ${info}`,
          );
          resolve({ path: [], error: info });
        }
      });
    });
  const segmentCount = waypoints.length - 1;
  const segmentPaths = Array(segmentCount).fill(null);
  const segmentErrors = Array(segmentCount).fill(null);
  const pendingIndexes = Array.from({ length: segmentCount }, (_, index) => index);
  let consecutiveFailedWaves =0;

  while (pendingIndexes.length >0) {
    const waveIndexes = pendingIndexes.splice(0, pendingIndexes.length);
    logMessage_Info(`正在排队规划 ${waveIndexes.length} 段路径...`);
    const waveResults = await Promise.all(waveIndexes.map(async (segmentIndex, order) => {
      await sleep(queueIntervalMs * order);
      const realStart = waypoints[segmentIndex],
        realEnd = waypoints[segmentIndex + 1];
      const result = await searchSegment(segmentIndex, realStart, realEnd);
      return { segmentIndex, result };
    }));
    let waveSuccessCount = 0;
    waveResults.forEach(({ segmentIndex, result }) => {
      if (Array.isArray(result.path) && result.path.length > 0) {
        segmentPaths[segmentIndex] = result.path;
        segmentErrors[segmentIndex] = null;
        waveSuccessCount += 1;
      } else {
        segmentErrors[segmentIndex] = result.error || "路径规划失败";
        pendingIndexes.push(segmentIndex);
      }
    });
    if (waveSuccessCount ===0) {
      consecutiveFailedWaves += 1;
      if (consecutiveFailedWaves >= maxFailedWaves) {
        break;
      }
    } else {
      consecutiveFailedWaves =0;
    }
    if (pendingIndexes.length >0) {
      logMessage_Info(
        `仍有 ${pendingIndexes.length} 段路径未成功，${retryDelayMs / 1000}秒后按限流重试...`,
      );
      await sleep(retryDelayMs);
    }
  }

  for (let i = 0; i < segmentCount; i++) {
    const realStart = waypoints[i],
      realEnd = waypoints[i + 1];
    let segmentPath = segmentPaths[i];
    if (!Array.isArray(segmentPath) || segmentPath.length === 0) {
      if (useFallback) {
        logMessage_Info(`第 ${i + 1} 段路径规划最终失败，启用直线连接。`);
        segmentPath = [
          { lng: realStart.lng, lat: realStart.lat },
          { lng: realEnd.lng, lat: realEnd.lat },
        ];
      } else
        throw new Error(`第 ${i + 1} 段路径规划失败 (${segmentErrors[i] || `连续 ${maxFailedWaves} 次失败`})`);
    }
    if (
      !areCoordsEqual(segmentPath[0], {
        lng: realStart.lng,
        lat: realStart.lat,
      })
    )
      segmentPath.unshift({ lng: realStart.lng, lat: realStart.lat });
    if (
      !areCoordsEqual(segmentPath[segmentPath.length - 1], {
        lng: realEnd.lng,
        lat: realEnd.lat,
      })
    )
      segmentPath.push({ lng: realEnd.lng, lat: realEnd.lat });
    all_path.push(...(i > 0 ? segmentPath.slice(1) : segmentPath));
  }
  return all_path;
}
async function onConfirmAutoGenerate() {
  const minTime = parseInt($("min-time-input").value),
    maxTime = parseInt($("max-time-input").value),
    minDist = parseInt($("min-dist-input").value);
  if (minTime > maxTime) {
    showModalAlert("最短时间不能大于最长时间");
    return;
  }
  $("auto-gen-modal").classList.add("hidden");
  $("auto-gen-modal").classList.remove("flex");
  document.body.classList.remove("modal-visible");

  if (
    selectedTaskIndex === -1 ||
    !currentRunData.target_points ||
    currentRunData.target_points.length === 0
  ) {
    showModalAlert("请先选择一个有打卡点的任务");
    return;
  }
  logMessage_Info(`正在按当前地图供应商（${getMapProviderDisplayName()}）进行路径规划...`);
  try {
    const result = await callPythonAPI("auto_generate_path_with_provider", {
      min_t_m: minTime,
      max_t_m: maxTime,
      min_d_m: minDist,
    });
    if (result.success) {
      if (Array.isArray(result.notices)) {
        result.notices.forEach((notice) => logMessage_Info(notice));
      }
      currentRunData.run_coords = result.run_coords;
      currentRunData.total_run_distance_m = result.total_dist;
      currentRunData.total_run_time_s = result.total_time;
      drawOnMap();
      updateDashboard();
      renderTaskList();
      singleProcessedPoints = 0;
      singleTotalPoints = currentRunData.run_coords?.length || 0;
      updateSingleProgress(0, "0 / " + singleTotalPoints + " 点");
    } else {
      logMessage_Info(`生成失败: ${result.message}`);
      showModalAlert(`生成失败: ${result.message}`);
    }
  } catch (error) {
    logMessage_Info(`路径规划或生成失败: ${error}`);
    showModalAlert(`路径规划或生成失败: ${error}`);
  }
}
async function loadHistory(index) {
  selectedHistoryTrid = null;
  $("history-placeholder").textContent = "正在加载...";
  $("history-list").innerHTML = "";
  const result = await callPythonAPI("get_task_history", index);
  if (result.success && result.history.length > 0) {
    $("history-placeholder").classList.add("hidden");
    result.history.forEach((rec) => {
      const item = document.createElement("div");
      item.className =
        "grid grid-cols-3 gap-2 text-xs p-2 border-b border-slate-100 cursor-pointer hover:bg-white/70 rounded";
      item.innerHTML = `<span class="text-slate-600">${rec.time}</span><span class="font-semibold text-emerald-700">${rec.len}</span><span class="font-semibold text-sky-700">${rec.used_time}</span>`;
      item.addEventListener("click", () => {
        $("history-list")
          .querySelectorAll(".selected")
          .forEach((selectedItem) => selectedItem.classList.remove("selected"));
        item.classList.add("selected");
        selectedHistoryTrid = rec.trid;
        showHistoricalTrack(rec.trid);
      });
      $("history-list").appendChild(item);
    });
  } else {
    $("history-placeholder").textContent = "无历史记录或加载失败";
    $("history-placeholder").classList.remove("hidden");
  }
}

function clearHistoricalTrack() {
  const hasHistoricalTrack = selectedHistoryTrid !== null || polylines.history;
  selectedHistoryTrid = null;
  if (hasHistoricalTrack) drawOnMap();
}

async function showHistoricalTrack(trid) {
  if (backgroundTaskPollInterval) {
    logMessage_Warning("任务执行中，无法查看历史记录！请先停止当前任务。");
    showModalAlert("任务执行中，无法查看历史记录！请先停止当前任务。");
    return;
  }
  const result = await callPythonAPI("get_historical_track", trid);
  if (result.success) {
    logMessage_Info(
      `[历史轨迹] API返回数据 - coords长度: ${
        result.coords?.length || 0
      }, target_points长度: ${result.target_points?.length || 0}`,
    );

    if (isMobileMode) {
      const modal = $("mobile-track-modal");
      if (modal) {
        $("mobile-track-modal").classList.add("show");
        modal.classList.remove("hidden");
        modal.style.display = "flex";
        await ensureActiveMapProviderRuntimeIfNeeded("历史轨迹地图");
        await initMobileTrackMap();
        clearMobileTrackMap();
        if (getActiveMapProvider() !== "amap") {
          drawProviderRouteOnMap("mobile-track-map-container", result.coords || [], {
            strokeColor: "#8b5cf6",
            strokeWeight: 5,
            strokeOpacity: 0.8,
            showEndpoints: true,
          });
          return;
        }
      }
    }

    if (getActiveMapProvider() !== "amap") {
      await ensureActiveMapProviderRuntimeIfNeeded("历史轨迹地图");
      initProviderMap("map-container", false);
      drawProviderRouteOnMap("map-container", result.coords || [], {
        strokeColor: "#8b5cf6",
        strokeWeight: 5,
        strokeOpacity: 0.8,
        showEndpoints: true,
      });
      return;
    }
    if (!AMapInstance) return;

    if (isMobileMode) {
      const modal = $("mobile-track-modal");
      if (modal) {
        const path = result.coords.map(
          (p) => new AMapInstance.LngLat(p[0], p[1]),
        );

        if (path.length > 0) {
          mobileTrackPolyline = new AMapInstance.Polyline({
            path: path,
            strokeColor: "#8b5cf6",
            strokeWeight: 5,
            strokeOpacity: 0.8,
            zIndex: 55,
            map: mobileTrackMapInstance,
          });
          const startMarker = new AMapInstance.Marker({
            position: path[0],
            content:
              '<div style="width:12px;height:12px;background:#10b981;border:2px solid white;border-radius:50%;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
            anchor: "center",
            map: mobileTrackMapInstance,
          });
          mobileTrackMarkers.push(startMarker);
          const endMarker = new AMapInstance.Marker({
            position: path[path.length - 1],
            content:
              '<div style="width:12px;height:12px;background:#ef4444;border:2px solid white;border-radius:50%;box-shadow:0 2px 4px rgba(0,0,0,0.3);"></div>',
            anchor: "center",
            map: mobileTrackMapInstance,
          });
          mobileTrackMarkers.push(endMarker);
          let totalDist = 0;
          if (AMapInstance.GeometryUtil) {
            totalDist = AMapInstance.GeometryUtil.distanceOfLine(path);
          }
          const distance = result.distance || totalDist / 1000;
          const duration = result.duration || result.used_time || "--:--";
          const checkpoints =
            result.checkpoints || result.target_points?.length || 0;
          const distEl = $("mobile-track-distance");
          const durEl = $("mobile-track-duration");
          const paceEl = $("mobile-track-pace");
          if (distEl) {
            distEl.textContent = `${
              typeof distance === "number" ? distance.toFixed(2) : distance
            } km`;
          }
          if (durEl) {
            durEl.textContent = duration;
          }
          if (paceEl && typeof distance === "number" && duration !== "--:--") {
            const durationMatch = duration.match(/(\d+):(\d+)/);
            if (durationMatch) {
              const totalMinutes =
                parseInt(durationMatch[1]) + parseInt(durationMatch[2]) / 60;
              const pace = distance > 0 ? totalMinutes / distance : 0;
              const paceMin = Math.floor(pace);
              const paceSec = Math.round((pace - paceMin) * 60);
              paceEl.textContent = `${paceMin}:${paceSec
                .toString()
                .padStart(2, "0")}/km`;
            } else {
              paceEl.textContent = "--:--";
            }
          }

          logMessage_Info(
            `[历史轨迹] 摘要信息已更新 - 距离: ${distance} km, 时长: ${duration}, 打卡点: ${checkpoints}`,
          );
          logMessage_Info(
            `[历史轨迹] 检查打卡点数据 - target_points存在: ${!!result.target_points}, 长度: ${
              result.target_points?.length || 0
            }`,
          );
          if (result.target_points && result.target_points.length > 0) {
            const targetNames = result.target_point_names
              ? result.target_point_names.split("|")
              : [];
            result.target_points.forEach((point, index) => {
              const pointName = targetNames[index] || `点 ${index + 1}`;
              const checkpointMarker = new AMapInstance.Marker({
                position: new AMapInstance.LngLat(point[0], point[1]),
                content: `<div class="flex flex-col items-center">
                      <div class="text-xs font-bold whitespace-nowrap px-2 py-1 rounded-full shadow-lg bg-emerald-600 text-white">
                        ${pointName}
                      </div>
                      <div class="w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-emerald-600"></div>
                    </div>`,
                anchor: "bottom-center",
                zIndex: 100,
                map: mobileTrackMapInstance,
              });
              mobileTrackMarkers.push(checkpointMarker);
            });
            logMessage_Info(
              `[历史轨迹] 已绘制 ${result.target_points.length} 个打卡点`,
            );
          }
          mobileTrackMapInstance.setFitView();
        }
      }
      return;
    }
    if (polylines.history) map.remove(polylines.history);
    polylines.history = new AMapInstance.Polyline({
      path: result.coords.map((p) => new AMapInstance.LngLat(p[0], p[1])),
      strokeColor: "#8b5cf6",
      strokeWeight: 6,
      strokeOpacity: 0.8,
      zIndex: 55,
    });
    map.add(polylines.history);
    map.setFitView([polylines.history]);
  } else showModalAlert("无法加载历史轨迹");
}
function updateSingleProgress(pct, text, extra) {
  const fill = $("single-progress-fill");
  const label = $("single-progress-text");
  const extraEl = $("single-progress-extra");
  if (fill) fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  if (label) label.textContent = `进度 · ${pct}%`;
  if (extraEl) extraEl.textContent = extra || text || "";
  const mobileFill = document.getElementById("mobile-single-progress-fill");
  const mobileLabel = document.getElementById("mobile-single-progress-text");
  const mobileExtraEl = document.getElementById("mobile-single-progress-extra");
  if (mobileFill)
    mobileFill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  if (mobileLabel) mobileLabel.textContent = `进度 · ${pct}%`;
  if (mobileExtraEl) mobileExtraEl.textContent = extra || text || "";
}
function getCallerInfo(linesToSkip = null) {
  try {
    const err = new Error();
    const stack = err.stack;
    if (!stack) return { source: "unknown (no stack)" };
    const lines = stack.split("\n");

    let callerLine;

    if (linesToSkip !== null) {
      try {
        callerLine = lines[linesToSkip + 1] || "";
      } catch (error) {
        logMessage_Error("Error accessing stack line:", error);
        callerLine = lines[4] || lines[3] || lines[2] || lines[1] || "";
      }
    } else {
      callerLine = lines[4] || lines[3] || lines[2] || lines[1] || "";
    }
    if (typeof callerLine !== "string") {
      callerLine = "";
    }
    callerLine = callerLine.trim();
    let match = callerLine.match(
      /at\s+(?:(.+)\s+\()?(?:.+\/)?([^:]+:\d+:\d+)\)?/,
    );
    if (match) {
      const functionName = match[1] || "anonymous";
      const fileInfo = match[2] || "";
      return {
        source: `${functionName} (${fileInfo})`,
        functionName: functionName,
        fileInfo: fileInfo,
      };
    }
    match = callerLine.match(/^(?:([^@]+)@)?(?:.+\/)?([^:]+:\d+:\d+)$/);
    if (match) {
      const functionName = match[1] || "anonymous";
      const fileInfo = match[2] || "";
      return {
        source: `${functionName}@${fileInfo}`,
        functionName: functionName,
        fileInfo: fileInfo,
      };
    }
    return { source: callerLine || "unknown (parse failed)" };
  } catch (e) {
    return { source: "unknown (error parsing stack)" };
  }
}
function extractCleanSource(sourceString) {
  if (typeof sourceString !== "string") {
    return "unknown";
  }
  let result = "";
  const marker = "(uuid=";
  let markerIndex = sourceString.indexOf(marker);
  if (markerIndex === -1) {
    return sourceString.trim();
  }
  let relevantPart = sourceString.substring(0, markerIndex);
  result = relevantPart.trimEnd();
  return result || "未知";
}

// ==================== 日志批处理逻辑 ====================
let logQueue = [];
let logFlushTimer = null;
const LOG_FLUSH_INTERVAL = 2000; // 2秒间隔

function flushLogQueue() {
  if (logQueue.length === 0) {
    logFlushTimer = null;
    return;
  }

  // 取出当前队列所有内容并清空
  const batchToSend = [...logQueue];
  logQueue = [];

  if (!isInNetworkErrorState && sessionUUID) {
    // 使用loadInitialData发送日志，而不是直接fetch
    loadInitialData({
      frontend_logs: batchToSend,
      force: true, // 强制发送，因为日志需要及时传输
    }).catch((err) => {
      if (console._original && console._original.error) {
        console._original.error("[日志批量发送失败]", err);
      }
    });
  }

  // 重置定时器引用，允许下次触发
  logFlushTimer = null;

  // 如果在发送过程中又有新日志进入（极端情况），重新启动定时器
  if (logQueue.length > 0) {
    scheduleLogFlush();
  }
}

function scheduleLogFlush() {
  if (!logFlushTimer) {
    logFlushTimer = setTimeout(flushLogQueue, LOG_FLUSH_INTERVAL);
  }
}

// 页面关闭时尝试发送剩余日志
window.addEventListener("beforeunload", () => {
  if (logQueue.length > 0) {
    // 使用 sendBeacon 保证页面关闭时数据能发出 (如果浏览器支持且数据量不大)
    // 这里为了兼容性简单调用 flush，但 fetch 在 unload 时可能被取消
    // 尝试直接调用一次 flush，虽然不能保证成功
    flushLogQueue();
  }
});

function formatSafeClientLogArgs(args) {
  return args
    .map((arg) => {
      if (arg instanceof Error) {
        const safeName = createSafeClientLogValue(arg.name);
        const safeMessage = createSafeClientLogValue(arg.message);
        const safeStack = createSafeClientLogValue(arg.stack || "");
        return `${safeName}: ${safeMessage}${
          safeStack ? `\n${safeStack}` : ""
        }`;
      }
      const safeValue = createSafeClientLogValue(arg);
      if (typeof safeValue === "string") return safeValue;
      try {
        return JSON.stringify(safeValue);
      } catch (error) {
        return "[已省略]";
      }
    })
    .join(" ");
}

function resetAdminUsersSearchFilters() {
  const usersSearchInput = $("admin-users-search-input_modal");
  const mobileUsersSearchInput = $("mobile-multi-admin-users-search-input");
  if (usersSearchInput) usersSearchInput.value = "";
  if (mobileUsersSearchInput) mobileUsersSearchInput.value = "";
}

(function () {
  const originalConsole = {
    log: console.log.bind(console),
    info: console.info.bind(console),
    warn: console.warn.bind(console),
    error: console.error.bind(console),
    debug: console.debug.bind(console),
  };
  let isIntercepting = false;

  function interceptConsole(level, args, originalFn) {
    const message = formatSafeClientLogArgs(args);
    originalFn.call(console, message);
    if (isIntercepting) return;

    try {
      isIntercepting = true;
      if (
        message.includes("[前端日志]") ||
        message.includes("[日志发送失败]") ||
        message.includes("Failed to fetch") ||
        message.includes("NetworkError")
      ) {
        return;
      }
      if (!isInNetworkErrorState && sessionUUID) {
        const now = new Date();
        const timestamp = `${String(now.getHours()).padStart(2, "0")}:${String(
          now.getMinutes(),
        ).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

        // 使用队列逻辑
        logQueue.push({
          level: level.toUpperCase(),
          message: message,
          timestamp: timestamp,
          source: "第三方JS",
        });
        scheduleLogFlush();
      }
    } finally {
      isIntercepting = false;
    }
  }
  console.log = function (...args) {
    interceptConsole("info", args, originalConsole.log);
  };

  console.info = function (...args) {
    interceptConsole("info", args, originalConsole.info);
  };

  console.warn = function (...args) {
    interceptConsole("warning", args, originalConsole.warn);
  };

  console.error = function (...args) {
    interceptConsole("error", args, originalConsole.error);
  };

  console.debug = function (...args) {
    interceptConsole("debug", args, originalConsole.debug);
  };
  console._original = originalConsole;
})();
const routeDiagnosticMessages = new Map();

function displayRoutePlanningNotification(data) {
  if (!data?.msg) return;
  const id = data.diagnostic_id;
  if (id && routeDiagnosticMessages.has(id)) return;
  logMessage(data.msg, data.level || "INFO", "Backend");
  if (id) {
    routeDiagnosticMessages.set(id, { message: data.msg, detailed: false });
    if (routeDiagnosticMessages.size > 100) routeDiagnosticMessages.delete(routeDiagnosticMessages.keys().next().value);
  }
}

function displayRoutePlanningFailures(failures) {
  if (!Array.isArray(failures)) return;
  for (const failure of failures) {
    if (!failure?.diagnostic_id || typeof failure.message !== "string") continue;
    const previous = routeDiagnosticMessages.get(failure.diagnostic_id);
    if (previous?.detailed) continue;
    const context = [
      failure.segment != null ? `路段：${failure.segment}` : "",
      failure.error_code != null && failure.error_code !== "" ? `错误码：${failure.error_code}` : "",
      failure.error_explanation && !failure.message.includes(failure.error_explanation) ? failure.error_explanation : "",
      failure.error_hint && !failure.message.includes(failure.error_hint) ? `建议：${failure.error_hint}` : "",
    ].filter(Boolean).join("；");
    const message = `[${failure.provider || "地图服务"}] ${context ? context + "；" : ""}${failure.message}（诊断编号：${failure.diagnostic_id}）`;
    let replaced = false;
    if (previous) {
      for (const id of ["log-text", "multi-log-text", "mobile-log-text"]) {
        const area = document.getElementById(id);
        if (area?.value?.includes(previous.message)) {
          area.value = area.value.replace(previous.message, message);
          replaced = true;
        }
      }
    }
    if (!replaced) logMessage(message, "ERROR", "Backend");
    routeDiagnosticMessages.set(failure.diagnostic_id, { message, detailed: true });
    if (routeDiagnosticMessages.size > 100) routeDiagnosticMessages.delete(routeDiagnosticMessages.keys().next().value);
  }
}

function logMessage(msg, level = "INFO", source = null) {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  const timestamp = `[${h}:${m}:${s}]`;
  const timestamp2 = `${h}:${m}:${s}`;
  const line = formatSafeClientLogArgs([msg]);

  let level_new = "INFO";
  let callerInfo;
  if (source) {
    callerInfo = source;
  } else {
    let orange_callerInfo = getCallerInfo();
    callerInfo = extractCleanSource(orange_callerInfo.source);
  }

  let new_message = `${timestamp}[前端日志][${callerInfo}] ${line}`;
  const fullMessage = `${timestamp}[${callerInfo}] ${line}`;

  if (level === "DEBUG") {
    level_new = "DEBUG";
    if (console._original) {
      console._original.debug(new_message);
    } else {
      console.debug(new_message);
    }
  } else if (level === "INFO") {
    level_new = "INFO";
    if (console._original) {
      console._original.info(new_message);
    } else {
      console.info(new_message);
    }
  } else if (level === "ERROR") {
    level_new = "ERROR";
    if (console._original) {
      console._original.error(new_message);
    } else {
      console.error(new_message);
    }
  } else if (level === "WARNING") {
    level_new = "WARNING";
    if (console._original) {
      console._original.warn(new_message);
    } else {
      console.warn(new_message);
    }
  } else if (level === "CRITICAL") {
    level_new = "CRITICAL";
    if (console._original) {
      console._original.error(new_message);
    } else {
      console.error(new_message);
    }
  } else {
    if (console._original) {
      console._original.log(new_message);
    } else {
      console.log(new_message);
    }
  }
  if (!isInNetworkErrorState && source !== "Backend") {
    try {
      // 将单条发送改为推入队列并调度
      logQueue.push({
        level: level_new,
        message: line,
        timestamp: timestamp2,
        source: callerInfo,
      });
      scheduleLogFlush();
    } catch (e) {
      if (console._original && console._original.error) {
        console._original.error("[日志入队异常]", e);
      }
    }
  }
  const isCoreLog = (message, logLevel) => {
    if (
      logLevel === "ERROR" ||
      logLevel === "WARNING" ||
      logLevel === "CRITICAL"
    ) {
      return true;
    }
    const coreKeywords = [
      "路径规划",
      "路径生成",
      "自动生成",
      "处理路径",
      "清除路径",
      "录制路径",
      "导出路径",
      "开始执行",
      "执行完成",
      "执行所有",
      "停止执行",
      "任务完成",
      "任务失败",
      "提交成功",
      "提交失败",
      "上传成功",
      "上传失败",
      "数据提交",
      "登录成功",
      "登录失败",
      "登出",
      "进入多账号模式",
      "退出多账号模式",
      "账号列表",
      "签到成功",
      "签到失败",
      "补签",
      "加载任务",
      "刷新任务",
      "选择任务",
      "[JS-Queue]",
      "无打卡点",
      "跳过: 任务",
    ];

    return coreKeywords.some((keyword) => message.includes(keyword));
  };
  const shouldShowInUI = isCoreLog(line, level);

  if (shouldShowInUI) {
    const single = $("log-text");
    if (single) {
      single.value += fullMessage + "\n";
      single.scrollTop = single.scrollHeight;
    }
    const multi = $("multi-log-text");
    if (multi) {
      multi.value += fullMessage + "\n";
      multi.scrollTop = multi.scrollHeight;
    }
    // ========================================
    // 【移动端日志同步】
    // ========================================
    const mobileLog = document.getElementById("mobile-log-text");
    if (mobileLog) {
      mobileLog.value += fullMessage + "\n";
      mobileLog.scrollTop = mobileLog.scrollHeight;
    }
  }
}
function logMessage_Debug(...args) {
  logMessage(formatSafeClientLogArgs(args), "DEBUG");
}
function logMessage_Info(...args) {
  logMessage(formatSafeClientLogArgs(args), "INFO");
}
function logMessage_Warning(...args) {
  logMessage(formatSafeClientLogArgs(args), "WARNING");
}
function logMessage_Error(...args) {
  logMessage(formatSafeClientLogArgs(args), "ERROR");
}
function logMessage_Critical(...args) {
  logMessage(formatSafeClientLogArgs(args), "CRITICAL");
}
function showTab(tabName, element) {
  if (tabName !== "attendance" && notificationAutoRefreshTimer) {
    clearTimeout(notificationAutoRefreshTimer);
    notificationAutoRefreshTimer = null;
    logMessage_Info("[自动刷新] 已停止（切换到其他标签）");
  }
  [
    "run-control",
    "path-tools",
    "history",
    "params",
    "log",
    "checkpoints",
    "attendance",
  ].forEach((name) => {
    $(`${name}-tab`).classList.add("hidden");
    const b = document.querySelector(
      `button[onclick="showTab('${name}', this)"]`,
    );
    if (b) b.classList.remove("active");
  });
  if (tabName !== "history") clearHistoricalTrack();
  $(`${tabName}-tab`).classList.remove("hidden");
  if (element) element.classList.add("active");
  if (tabName === "attendance") {
    // refreshNotificationsUI() 会获取最新通知
    // onNotificationsUpdated() (由后台调用或 refreshNotificationsUI 间接调用) 会填充 attendance-list
    // refreshNotificationsUI() 自带防抖，所以这里直接调用是安全的
    logMessage_Info("[自动刷新] 切换到签到标签，启动自动刷新");
    refreshNotificationsUI(
      (useCache = true),
      (isManual = false),
      (show_Modal = false),
    ); // 切换tab视为自动刷新，将开启定时刷新
  }
}

function autoLogin(user, pass) {
  if (!user || !pass) return;
  const userCombo = $("user-combo");
  userCombo.addEventListener("focus", refreshUserList);
  userCombo.addEventListener("click", refreshUserList);
  if ([...userCombo.options].some((o) => o.value === user))
    userCombo.value = user;
  else {
    const opt = document.createElement("option");
    opt.value = opt.textContent = user;
    userCombo.appendChild(opt);
    userCombo.value = user;
  }
  $("username-entry").value = user;
  $("password-entry").value = pass;
  onUserChange().then(() => $("login-button").click());
}

function createParamInputs(
  container,
  prefix,
  changeHandler,
  excludeGroups = [],
) {
  container.innerHTML = "";
  let finalExclude = [...excludeGroups];
  if (prefix !== "multi-param") {
    finalExclude.push("自动签到");
  }
  paramGroups.forEach((group, index) => {
    if (finalExclude.includes(group.title)) {
      return;
    }
    if (excludeGroups.includes(group.title)) {
      return;
    }

    const header = document.createElement("h3");
    const marginTopClass = index === 0 ? "" : "mt-4";
    header.className = `text-base font-bold text-sky-700 ${marginTopClass} mb-2 border-b border-slate-200 pb-1`;
    header.textContent = group.title;
    container.appendChild(header);

    for (const key of group.keys) {
      const def = paramDefs[key];
      if (!def) continue;

      const div = document.createElement("div");
      div.className = "text-sm mb-3";

      const step = key.endsWith("_s") || key.endsWith("_mps") ? "0.1" : "1";
      const unitHtml = def.unit
        ? `<span class="ml-2 text-xs text-slate-500 select-none">${def.unit}</span>`
        : "";

      if (def.type === "theme_selector") {
        div.innerHTML = `
          <label class="block text-slate-700 font-semibold">${def.label}</label>
          <p class="mt-1 text-xs text-slate-500">${def.help}</p>
          <div id="${prefix}-theme-style-buttons" class="grid grid-cols-2 gap-2 mt-2"></div>
        `;
        const buttonsContainer = div.querySelector(`#${prefix}-theme-style-buttons`);
        renderThemeStyleButtons(
          buttonsContainer,
          pythonParams.theme_style || currentThemeStyle || "default",
        );
      } else if (def.type === "color_picker") {
        div.innerHTML = `
          <label for="${prefix}-${key}" class="block text-slate-700 font-semibold">${def.label}</label>
          <div class="flex items-center gap-3 mt-1">
            <input type="color" id="${prefix}-${key}-picker" data-key="${key}" class="w-10 h-10 rounded-full cursor-pointer border-2 border-white shadow-md" title="点击选择颜色">
            <input type="text" id="${prefix}-${key}" data-key="${key}" class="input-field !py-1 w-full" placeholder="#7dd3fc" title="${def.help}">
            <button onclick="resetBaseColorToDefault('${prefix}')" class="btn btn-ghost !py-1 !px-3 !text-xs flex-shrink-0">恢复默认</button>
          </div>
           <p class="mt-1 text-xs text-slate-500">${def.help}</p>
        `;
      } else if (
        def.type === "checkbox" ||
        key === "api_fallback_line" ||
        key === "ignore_task_time"
      ) {
        div.innerHTML = `
          <label class="flex items-center gap-2 cursor-pointer" title="${def.help}">
            <input type="checkbox" id="${prefix}-${key}" data-key="${key}" class="w-5 h-5 accent-sky-600 rounded cursor-pointer flex-shrink-0">
            <span class="text-slate-700 font-semibold">${def.label}</span>
          </label>
          <p class="mt-1 text-xs text-slate-500">${def.help}</p>
        `;
      } else {
        div.innerHTML = `
          <label for="${prefix}-${key}" class="block mb-1 text-slate-700 font-semibold">${def.label}</label>
          <div class="flex items-center">
            <input type="number" step="${step}" id="${prefix}-${key}" data-key="${key}" class="input-field !py-1 w-full" title="${def.help}">
            ${unitHtml}
          </div>
          <p class="mt-1 text-xs text-slate-500">${def.help}</p>
        `;
      }

      container.appendChild(div);

      const inputs = div.querySelectorAll("input");
      inputs.forEach((input) => {
        if (input.type === "color") {
          input.addEventListener("input", (e) => {
            const hexColor = e.target.value;
            const textInput = document.getElementById(`${prefix}-${key}`);
            if (textInput) textInput.value = hexColor;
            setBaseColor(hexColor, hexColor);
          });
          input.addEventListener("change", changeHandler);
        } else if (input.type === "text" && key === "theme_base_color") {
          input.addEventListener("change", (e) => {
            const hexColor = e.target.value;
            const colorPicker = document.getElementById(
              `${prefix}-${key}-picker`,
            );
            if (colorPicker) colorPicker.value = hexColor;
            setBaseColor(hexColor, hexColor);
            changeHandler(e);
          });
        } else {
          input.addEventListener("change", changeHandler);
        }
      });
    }
  });
}

function updateParamInputs(container, prefix, params) {
  for (const key of Object.keys(paramDefs)) {
    const input = document.getElementById(`${prefix}-${key}`);
    if (!input || !params) continue;
    if (!(key in params)) continue;
    if (input.type === "checkbox") {
      input.checked = Boolean(params[key]);
    } else {
      input.value = params[key];
      if (key === "theme_base_color") {
        const colorPicker = document.getElementById(`${prefix}-${key}-picker`);
        if (colorPicker) {
          colorPicker.value = params[key];
        }
      }
    }
  }
}

function onParamChange(event) {
  const key = event.target.dataset.key;
  let value;
  if (event.target.type === "checkbox") value = event.target.checked;
  else value = event.target.value;
  pythonParams[key] = value;
  callPythonAPI("update_param", key, value);
  if (key === "ignore_task_time") {
    logMessage_Info("参数 'ignore_task_time' 已更改，正在自动刷新任务列表...");
    refreshTasks();
  }
  // 自动签到开关变更时显示提示
  if (key === "auto_attendance_enabled") {
    showAutoAttendanceToggleAlert(value, false); // false = PC端
  }
}
function onGlobalParamChange(event) {
  const key = event.target.dataset.key;
  let value =
    event.target.type === "checkbox"
      ? event.target.checked
      : event.target.value;
  pythonParams[key] = value;
  callPythonAPI("update_param", key, value);
  if (key === "ignore_task_time") {
    updateAllAccountsStatusText();
  }
  // 多账号模式下自动签到开关变更时显示提示
  if (key === "auto_attendance_enabled") {
    showMultiAutoAttendanceToggleAlert(value, false); // false = PC端
  }
}
async function openAccountParamsModal(username) {
  const result = await callPythonAPI("multi_get_account_params", username);
  if (!result.success) {
    showModalAlert(result.message);
    return;
  }
  $("account-params-title").textContent = `[${username}] 参数设置`;
  const container = $("account-params-container");
  createParamInputs(container, "acc-param", () => {}, ["主题与外观"]);
  updateParamInputs(container, "acc-param", result.params);

  $("save-account-params-btn").onclick = async () => {
    const inputs = container.querySelectorAll("input");
    for (const input of inputs) {
      const key = input.dataset.key;
      const value = input.type === "checkbox" ? input.checked : input.value;
      await callPythonAPI("multi_update_account_param", username, key, value);
    }
    const modal = $("account-params-modal");
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    document.body.classList.remove("modal-visible");
  };
  const modal = $("account-params-modal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.body.classList.add("modal-visible");
}
function toggleUserDetails(show) {
  const modal = $("user-details-modal");
  modal.classList.toggle("hidden", !show);
  modal.classList.toggle("flex", show);
  const mapToToggle = !$("multi-account-app").classList.contains("hidden")
    ? multiAccountMap
    : map;
  if (show) {
    if (mapToToggle)
      mapToToggle.setStatus({
        dragEnable: false,
        scrollWheel: false,
        doubleClickZoom: false,
      });
    document.body.classList.add("modal-visible");
  } else {
    if (mapToToggle)
      mapToToggle.setStatus({
        dragEnable: true,
        scrollWheel: true,
        doubleClickZoom: true,
      });
    document.body.classList.remove("modal-visible");
  }
}
function toggleTaskDetails(show) {
  const modal = $("task-details-modal");
  modal.classList.toggle("hidden", !show);
  modal.classList.toggle("flex", show);

  const mapToToggle = !$("multi-account-app").classList.contains("hidden")
    ? multiAccountMap
    : map;
  if (show) {
    if (mapToToggle)
      mapToToggle.setStatus({
        dragEnable: false,
        scrollWheel: false,
        doubleClickZoom: false,
      });
    document.body.classList.add("modal-visible");
  } else {
    if (mapToToggle)
      mapToToggle.setStatus({
        dragEnable: true,
        scrollWheel: true,
        doubleClickZoom: true,
      });
    document.body.classList.remove("modal-visible");
  }
}
function showUserDetails() {
  if (!currentUserData || !currentUserData.student_id) {
    showModalAlert("请先成功登录");
    return;
  }
  const info = currentUserData;
  const content = $("user-details-content");
  content.innerHTML = "";
  const kv = {
    姓名: info.name,
    学号: info.student_id,
    用户名: info.username,
    性别: info.gender,
    学校: info.school_name,
    属性: info.attribute_type,
    手机号: info.phone,
    用户ID: info.id,
    身份证号: info.id_card,
    注册时间: info.registration_time,
    首次登录: info.first_login_time,
    上次登录: info.last_login_time,
    当前登录: info.current_login_time,
  };
  Object.entries(kv).forEach(([k, v]) => {
    const p = document.createElement("p");
    p.innerHTML = `<span class="font-bold w-24 inline-block text-left pr-2 text-slate-500">${k}:</span><span class="break-all">${
      v || "NULL"
    }</span>`;
    content.appendChild(p);
  });
  const uaText = getCurrentSessionUAText();
  const p_ua = document.createElement("p");
  p_ua.innerHTML = `<span class="font-bold w-24 inline-block text-left pr-2 text-slate-500">UA:</span><span class="break-all">${uaText}</span>`;
  content.appendChild(p_ua);

  toggleUserDetails(true);
}

function showTaskDetails() {
  if (!currentRunData || !currentRunData.run_name) {
    showModalAlert("请先选择任务");
    return;
  }
  const content = $("task-details-content");
  content.innerHTML = "";
  const kv = {
    任务名称: currentRunData.run_name,
    任务状态: currentRunData.status == 1 ? "已完成" : "未完成",
    任务ID: currentRunData.errand_id,
    计划ID: currentRunData.errand_schedule,
    开始时间: currentRunData.start_time,
    结束时间: currentRunData.end_time,
    上传时间: currentRunData.upload_time,
  };
  Object.entries(kv).forEach(([k, v]) => {
    const p = document.createElement("p");
    p.innerHTML = `<span class="font-bold w-28 inline-block text-left pr-2 text-slate-500">${k}:</span><span>${
      v || "NULL"
    }</span>`;
    content.appendChild(p);
  });
  const tpTitle = document.createElement("p");
  tpTitle.className = "font-bold text-slate-500 mt-2";
  tpTitle.textContent = "打卡点列表:";
  content.appendChild(tpTitle);
  (currentRunData.target_points || []).forEach((p, i) => {
    const name =
      (currentRunData.target_point_names || "").split("|")[i] ||
      `打卡点${i + 1}`;
    const div = document.createElement("div");
    div.className = "flex items-center gap-2 text-slate-600 ml-4";
    const numSpan = document.createElement("span");
    numSpan.className = "font-mono w-6 inline-block";
    numSpan.textContent = `${i + 1}.`;
    const nameSpan = document.createElement("span");
    nameSpan.textContent = name;
    const coordsSpan = document.createElement("span");
    coordsSpan.className = "text-xs text-slate-400";
    coordsSpan.textContent = `(${p[0].toFixed(5)}, ${p[1].toFixed(5)})`;
    div.append(numSpan, nameSpan, coordsSpan);
    content.appendChild(div);
  });
  toggleTaskDetails(true);
}

function toggleNotifications(show, forceDisableMap = false) {
  const modal = $("notifications-modal");
  modal.classList.toggle("hidden", !show);
  modal.classList.toggle("flex", show);

  const mapToToggle = !$("multi-account-app").classList.contains("hidden")
    ? multiAccountMap
    : map;

  if (show) {
    if (mapToToggle)
      mapToToggle.setStatus({
        dragEnable: false,
        scrollWheel: false,
        doubleClickZoom: false,
      });
    document.body.classList.add("modal-visible");
  } else {
    if (forceDisableMap) {
      if (mapToToggle)
        mapToToggle.setStatus({
          dragEnable: false,
          scrollWheel: false,
          doubleClickZoom: false,
        });
    } else {
      if (mapToToggle)
        mapToToggle.setStatus({
          dragEnable: true,
          scrollWheel: true,
          doubleClickZoom: true,
        });
    }
    document.body.classList.remove("modal-visible");
  }
}

async function fetchNotifications(limit = null, offset = 0) {
  if (IS_OFFLINE) {
    logMessage_Info("[通知] 离线模式下无法获取通知");
    return {
      success: true,
      unreadCount: 0,
      notices: [],
    };
  }

  logMessage_Debug("开始刷新通知", { limit, offset });
  const badge = $("notification-badge");
  let result = null;
  try {
    const params = {};
    if (limit !== null) {
      params.request_limit = limit;
      params.request_offset = offset;
    }

    result = await callPythonAPI("get_notifications", params);
    if (result && result.success) {
      if (offset === 0) {
        window.currentNotifications = result.notices || [];
      } else {
        window.currentNotifications = (
          window.currentNotifications || []
        ).concat(result.notices || []);
      }
      if (result.unreadCount > 0) {
        badge.textContent = result.unreadCount > 9 ? "9+" : result.unreadCount;
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
      if (limit === null || offset === 0) {
        window.currentNotifications = result.notices || [];
      } else {
        window.currentNotifications = (
          window.currentNotifications || []
        ).concat(result.notices || []);
      }
    } else {
      badge.classList.add("hidden");
    }
  } catch (e) {
    logMessage_Error("Fetch notifications failed", e);
    badge.classList.add("hidden");
  }
  return result;
}
let notificationAutoRefreshTimer = null;
async function refreshNotificationsUI(
  useCache = true,
  isManual = false,
  show_Modal = true,
) {
  if (isRefreshingNotifications) {
    logMessage_Info("通知刷新已在进行中，跳过本次请求");
    return;
  }
  if (show_Modal) {
    showModalAlert("正在刷新通知列表，请稍候...", "提示");
  }
  isRefreshingNotifications = true;
  const content = $("notifications-content");
  const refreshBtn = $("refresh-notifications-btn");
  const markReadBtn = $("mark-all-read-btn");
  if (refreshBtn) {
    refreshBtn.disabled = true;
    refreshBtn.textContent = "刷新中...";
  }
  if (markReadBtn) markReadBtn.disabled = true;

  try {
    let cachedDisplayed = false;
    if (useCache && content) {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">正在加载缓存通知...</p>';
      try {
        const cachedResult = await callPythonAPI("get_cached_notifications");
        if (
          cachedResult &&
          cachedResult.success &&
          cachedResult.cached &&
          cachedResult.notices.length > 0
        ) {
          logMessage_Info(`显示缓存的 ${cachedResult.notices.length} 条通知`);

          content.innerHTML = "";
          renderNotificationBatch(cachedResult.notices, content);
          cachedDisplayed = true;
          const badge = $("notification-badge");
          if (cachedResult.unreadCount > 0) {
            badge.textContent =
              cachedResult.unreadCount > 9 ? "9+" : cachedResult.unreadCount;
            badge.classList.remove("hidden");
          } else {
            badge.classList.add("hidden");
          }
          const hasUnread = cachedResult.notices.some(
            (n) => n.isRead == 0 || n.isRead === false,
          );
          if (markReadBtn) markReadBtn.disabled = !hasUnread;
          const refreshingIndicator = document.createElement("div");
          refreshingIndicator.id = "refreshing-indicator";
          refreshingIndicator.className =
            "p-3 text-center text-slate-400 text-sm";
          refreshingIndicator.innerHTML = "正在刷新最新通知...";
          if (content) content.appendChild(refreshingIndicator);
        }
      } catch (e) {
        logMessage_Warning("获取缓存通知失败，将直接加载最新通知", e);
      }
    }
    if (!cachedDisplayed && content) {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">正在加载通知...</p>';
    }
    let currentOffset = 0;
    const batchSize = cachedDisplayed ? 5000 : 5;
    let hasMore = true;
    let firstLoad = true;
    let finalResult = null;
    function startAutoRefreshTimer() {
      if (!isManual) {
        if (notificationAutoRefreshTimer) {
          clearTimeout(notificationAutoRefreshTimer);
          notificationAutoRefreshTimer = null;
        }
        const refreshIntervalInput = $("param-auto_attendance_refresh_s");
        const refreshInterval = refreshIntervalInput
          ? parseInt(refreshIntervalInput.value)
          : 300;
        if (refreshInterval > 0) {
          logMessage_Info(
            `[自动刷新] (加载完成) 将在 ${refreshInterval} 秒后自动刷新通知`,
          );
          notificationAutoRefreshTimer = setTimeout(() => {
            logMessage_Info("[自动刷新] 正在自动刷新通知...");
            refreshNotificationsUI(true, false, false);
          }, refreshInterval * 1000);
        }
      }
    }
    const loadNextBatch = async () => {
      if (!hasMore) {
        if (finalResult) {
          onNotificationsUpdated(finalResult);
        }
        logMessage_Info("所有通知加载完成（模态框）");
        startAutoRefreshTimer();
        return;
      }
      logMessage_Info(
        `正在加载通知：offset=${currentOffset}, limit=${batchSize}`,
      );
      const result = await fetchNotifications(batchSize, currentOffset);
      if (firstLoad) {
        finalResult = result;
      }
      if (!result || !result.success) {
        if (firstLoad && !cachedDisplayed) {
          content.innerHTML =
            '<p class="text-red-500 text-center py-10">加载失败，请稍后重试</p>';
        }
        return;
      }
      const notices = result.notices || [];

      if (firstLoad && content) {
        content.innerHTML = "";
        firstLoad = false;
        logMessage_Info(
          `首批新通知加载完成，${
            cachedDisplayed ? "已替换" : "正在显示"
          }缓存数据`,
        );
      }

      if (notices.length === 0 && currentOffset === 0 && content) {
        content.innerHTML =
          '<p class="text-slate-400 text-center py-10">暂无通知</p>';
        if (markReadBtn) markReadBtn.disabled = true;
        return;
      }
      const oldIndicator = $("loading-more-indicator");
      if (oldIndicator) {
        oldIndicator.remove();
      }
      if (notices.length > 0 && content) {
        logMessage_Info(
          `第${Math.floor(currentOffset / batchSize) + 1}批加载完成：显示 ${
            notices.length
          } 条通知`,
        );
        renderNotificationBatch(notices, content);
        const allNotices = window.currentNotifications || [];
        const hasUnread = allNotices.some(
          (n) => n.isRead == 0 || n.isRead === false,
        );
        if (markReadBtn) markReadBtn.disabled = !hasUnread;
      }
      currentOffset += batchSize;
      hasMore = result.hasMore || false;
      if (hasMore && content) {
        const loadingMore = document.createElement("div");
        loadingMore.id = "loading-more-indicator";
        loadingMore.className = "p-3 text-center text-slate-400 text-sm";
        loadingMore.innerHTML = "正在加载更多通知...";
        content.appendChild(loadingMore);
        setTimeout(loadNextBatch, 100);
      } else {
        if (finalResult) {
          onNotificationsUpdated(finalResult);
        }
        logMessage_Info("所有通知加载完成（模态框）");

        startAutoRefreshTimer();
      }
    };

    await loadNextBatch();
    if (show_Modal) {
      showModalAlert("通知列表刷新完成", "提示");
    }
  } catch (e) {
    logMessage_Error("刷新通知列表失败", e);
    showModalAlert("通知列表刷新失败，请稍后重试", "错误");
    content.innerHTML =
      '<p class="text-red-500 text-center py-10">刷新失败，请稍后重试</p>';
  } finally {
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.textContent = "刷新";
    }
    isRefreshingNotifications = false;
  }
}
function formatNotificationTime(value) {
  const text = String(value ?? "").trim();
  if (!text) return "-";
  const numeric = Number(text);
  const date = new Date(
    Number.isFinite(numeric)
      ? Math.abs(numeric) < 1e12
        ? numeric * 1000
        : numeric
      : text,
  );
  if (Number.isNaN(date.getTime())) return text;
  const pad = (part) => String(part).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  );
}

function renderNotificationBatch(notices, container) {
  if (!notices || notices.length === 0) return;

  for (const n of notices) {
    const item = document.createElement("div");
    item.className = "p-3 border-b border-slate-200";
    item.id = `notice-${n.id}`;

    const isEffectivelyRead = n.isRead == 1 || n.isRead === true;
    const isReadClass = isEffectivelyRead ? "opacity-60" : "font-bold";
    let readButtonHtml = "";
    if (!isEffectivelyRead) {
      readButtonHtml = `<button class="btn btn-ghost !py-0 !px-2 !text-xs text-sky-600" onclick="markAsRead(event, ${escapeInlineJsArg(n.id)})">设为已读</button>`;
    }
    let attendanceHtml = "";
    const isAttendanceTask =
      n.image === "attendance" || (n.title && n.title.includes("签到"));

    if (isAttendanceTask && n.id) {
      switch (n.attendance_code) {
        case -1:
          try {
            const coordsStr = (n.updateBy || "").trim();
            const [lat, lon] = coordsStr.split(",").map(Number);
            if (isNaN(lon) || isNaN(lat)) {
              attendanceHtml = `<span class="text-xs font-semibold text-red-500 px-2 py-0.5 rounded-full bg-red-100">已过期</span> <span class="text-xs text-slate-400">(坐标无效)</span>`;
            } else {
              const targetCoords = `[${lon}, ${lat}]`;
              attendanceHtml = `
                      <span class="text-xs font-semibold text-red-500 px-2 py-0.5 rounded-full bg-red-100">已过期</span>
                      <div class="relative inline-block group">
                        <button class="btn btn-warning !py-0 !px-2 !text-xs inline-flex items-center" title="补签此任务">
                          <span>补签</span>
                          <svg class="w-2.5 h-2.5 ml-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6"><path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4"/></svg>
                        </button>
                        <div class="hidden group-hover:block absolute right-0 z-[1051] pt-1 w-32 bg-white/90 backdrop-blur-sm rounded-lg shadow-xl border border-slate-200 p-1 space-y-1">
                          <button class="btn btn-warning !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">随机补签</button>
                          <button class="btn btn-warning !bg-orange-400 hover:!bg-orange-500 !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleManualMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">手动选点补签</button>
                        </div>
                      </div>
                    `;
            }
          } catch (e) {
            attendanceHtml = `<span class="text-xs font-semibold text-red-500 px-2 py-0.5 rounded-full bg-red-100">已过期</span> <span class="text-xs text-slate-400">(坐标解析失败)</span>`;
          }
          break;
        case 1:
          attendanceHtml = `<span class="text-xs font-semibold text-emerald-600 px-2 py-0.5 rounded-full bg-emerald-100">已签到</span>`;
          break;
        case 0:
          try {
            const coordsStr = (n.updateBy || "").trim();
            const [lat, lon] = coordsStr.split(",").map(Number);

            if (!isNaN(lon) && !isNaN(lat)) {
              const rollCallId = n.id;
              const targetCoords = `[${lon}, ${lat}]`;

              attendanceHtml = `
                    <div class="relative inline-block group">
                      <button class="btn btn-secondary !py-0 !px-2 !text-xs inline-flex items-center">
                        <span>签到</span>
                        <svg class="w-2.5 h-2.5 ml-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6"><path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4"/></svg>
                      </button>
                      <div class="hidden group-hover:block absolute right-0 z-[1051] pt-1 w-28 bg-white/90 backdrop-blur-sm rounded-lg shadow-xl border border-slate-200 p-1 space-y-1">
                        <button class="btn btn-success !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleAttendance(event, ${escapeInlineJsArg(rollCallId)}, ${targetCoords})">随机签到</button>
                        <button class="btn btn-secondary !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleManualAttendance(event, ${escapeInlineJsArg(rollCallId)}, ${targetCoords})">手动选点</button>
                      </div>
                    </div>
                    <button class="btn btn-warning !py-0 !px-2 !text-xs" onclick="handleMakeupAttendance(event, ${escapeInlineJsArg(rollCallId)}, ${targetCoords})">
                      补签
                    </button>
                  `;
            } else {
              attendanceHtml = `<span class="text-xs text-slate-400">坐标无效</span>`;
            }
          } catch (e) {
            logMessage_Error("解析签到坐标失败:", e, n.updateBy);
            attendanceHtml = `<span class="text-xs text-red-500">数据错误</span>`;
          }
          break;
        default:
          attendanceHtml = `<span class="text-xs text-slate-400">状态未知</span>`;
      }
    }

    item.innerHTML = `
          <div class="flex justify-between items-center">
            <span class="text-base text-slate-800 ${isReadClass}">${n.title}</span>
            <div class="flex items-center gap-2">
              ${readButtonHtml}
              ${attendanceHtml}
              <span class="text-xs text-slate-500 flex-shrink-0">${escapeHtml(formatNotificationTime(n.createtime))}</span>
            </div>
          </div>
          <p class="text-sm text-slate-600 mt-1 ${isReadClass}">${n.content}</p>
        `;
    container.appendChild(item);
  }
}

function showNotifications() {
  if (IS_OFFLINE) {
    const content = $("notifications-content");
    if (content) {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">离线模式下无法获取通知</p>';
    }
    toggleNotifications(true);

    logMessage_Info("[通知] 离线模式下无法获取通知，已显示提示信息");
    return;
  }
  toggleNotifications(true);
  refreshNotificationsUI(true, true);
}
function onNotificationsUpdated(result) {
  if (!result || !result.success) {
    logMessage_Info("[后台刷新] 获取通知失败");
    return;
  }

  logMessage_Info(
    `[后台刷新] 收到 ${result.unreadCount} 未读, ${result.notices.length} 总数`,
  );
  const badge = $("notification-badge");
  if (result.unreadCount > 0) {
    badge.textContent = result.unreadCount > 9 ? "9+" : result.unreadCount;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
  const attList = $("attendance-list");
  if (attList) {
    attList.innerHTML = "";
    const attendanceNotices = (window.currentNotifications || []).filter(
      (n) => n.image === "attendance" || (n.title && n.title.includes("签到")),
    );
    if (attendanceNotices.length === 0) {
      attList.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">暂无签到任务</p>';
    } else {
      attendanceNotices.forEach((n) => {
        const item = document.createElement("div");
        item.className = "p-2 border-b border-slate-100";
        let statusText = "未知";
        let statusClass = "text-slate-500";
        let buttonHtml = "";
        let targetCoords = "null";
        let canSign = false;
        try {
          const coordsStr = (n.updateBy || "").trim();
          const [lat, lon] = coordsStr.split(",").map(Number);
          if (!isNaN(lon) && !isNaN(lat)) {
            targetCoords = `[${lon}, ${lat}]`;
            canSign = true;
          }
        } catch (e) {}
        switch (n.attendance_code) {
          case -1:
            statusText = "已过期";
            statusClass = "text-red-600 font-semibold";
            if (canSign) {
              buttonHtml = `
                <div class="relative inline-block group">
                  <button class="btn btn-warning !py-0 !px-2 !text-xs inline-flex items-center" title="补签此任务">
                    <span>补签</span>
                    <svg class="w-2.5 h-2.5 ml-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6"><path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4"/></svg>
                  </button>
                  <div class="hidden group-hover:block absolute right-0 z-[1051] pt-1 w-32 bg-white/90 backdrop-blur-sm rounded-lg shadow-xl border border-slate-200 p-1 space-y-1">
                    <button class="btn btn-warning !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">随机补签</button>
                    <button class="btn btn-warning !bg-orange-400 hover:!bg-orange-500 !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleManualMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">手动选点补签</button>
                  </div>
                </div>
              `;
            }
            break;
          case 1:
            statusText = "已签到";
            statusClass = "text-emerald-600 font-semibold";
            break;
          case 0:
            statusText = "待签到";
            statusClass = "text-sky-600 font-bold";
            if (canSign) {
              buttonHtml = `
                <div class="relative inline-block group">
                  <button class="btn btn-secondary !py-0 !px-2 !text-xs inline-flex items-center">
                    <span>签到</span>
                    <svg class="w-2.5 h-2.5 ml-1" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6"><path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m1 1 4 4 4-4"/></svg>
                  </button>
                  <div class="hidden group-hover:block absolute right-0 z-[1051] pt-1 w-28 bg-white/90 backdrop-blur-sm rounded-lg shadow-xl border border-slate-200 p-1 space-y-1">
                    <button class="btn btn-success !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">随机签到</button>
                    <button class="btn btn-secondary !py-1 !px-3 !text-xs !w-full !justify-start" onclick="handleManualAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">手动选点</button>
                  </div>
                </div>
                <button class="btn btn-warning !py-0 !px-2 !text-xs" onclick="handleMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">
                  补签
                </button>
              `;
            }
            break;
          default:
            statusText = "状态未知";
            statusClass = "text-slate-400";
        }
        if (
          n.attendance_status_text &&
          n.attendance_status_text.includes("失败")
        ) {
          statusText = n.attendance_status_text;
          statusClass = "text-red-700 font-bold";
        }
        item.innerHTML = `
          <div class="flex justify-between items-center">
            <span class="text-sm font-semibold text-slate-700">${n.title}</span>
            <span class="text-xs ${statusClass} flex-shrink-0">${statusText}</span>
          </div>
          <div class="flex justify-between items-center mt-1">
            <span class="text-xs text-slate-500">${n.content}</span>
            <div class="flex items-center gap-2 flex-shrink-0">
              <span class="text-xs text-slate-400">${escapeHtml(formatNotificationTime(n.createtime))}</span>
              ${buttonHtml}
            </div>
          </div>
        `;
        attList.appendChild(item);
      });
    }
  }
  const modal = $("notifications-modal");
  syncMobileAttendanceList();
}
async function handleAttendance(event, rollCallId, targetCoords) {
  event.stopPropagation();
  logMessage_Info(`正在为您自动签到... 活动ID: ${rollCallId}`);
  const result = await callPythonAPI(
    "trigger_attendance",
    rollCallId,
    targetCoords,
    "random",
    null,
    false,
  );
  if (result.success) {
    logMessage_Info(`签到成功: ${result.message}`);
    showModalAlert(`签到成功: ${result.message}`);
  } else {
    logMessage_Info(`签到失败: ${result.message}`);
    showModalAlert(`签到失败: ${result.message}`);
  }
  await fetchNotifications();
  showNotifications();
}

const svgIconNormal = `<div style="pointer-events: none;">
  <svg width="28" height="36" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
    <path fill="#22d3ee" d="M512 0C321.6 0 160 161.6 160 352c0 89.6 35.2 172.8 96 233.6l249.6 432c6.4 12.8 19.2 19.2 32 19.2s25.6-6.4 32-19.2l249.6-432c60.8-60.8 96-144 96-233.6C864 161.6 702.4 0 512 0z m0 512c-89.6 0-160-70.4-160-160s70.4-160 160-160 160 70.4 160 160-70.4 160-160 160z"></path>
  </svg>
</div>`;

const svgIconMakeup = `<div style="pointer-events: none;">
  <svg width="28" height="36" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
    <path fill="#f59e0b" d="M512 0C321.6 0 160 161.6 160 352c0 89.6 35.2 172.8 96 233.6l249.6 432c6.4 12.8 19.2 19.2 32 19.2s25.6-6.4 32-19.2l249.6-432c60.8-60.8 96-144 96-233.6C864 161.6 702.4 0 512 0z m0 512c-89.6 0-160-70.4-160-160s70.4-160 160-160 160 70.4 160 160-70.4 160-160 160z"></path>
  </svg>
</div>`;

async function handleManualAttendance(event, rollCallId, targetCoords) {
  event.stopPropagation();
  if (getActiveMapProvider() !== "amap" || !map || !AMapInstance) {
    showModalAlert(
      `当前地图提供方为${getMapProviderDisplayName()}，手动地图选点暂仅支持高德地图。`,
      "提示",
    );
    return;
  }
  toggleNotifications(false, true);

  selectedTaskIndex = -1;
  renderTaskList();
  drawOnMap();

  logMessage_Info("请在地图上单击选择签到点...");

  if (tempAttendanceMarker && map) {
    map.remove(tempAttendanceMarker);
    tempAttendanceMarker = null;
  }
  if (tempAttendanceCircle && map) {
    map.remove(tempAttendanceCircle);
    tempAttendanceCircle = null;
  }
  const radius =
    currentUserData && currentUserData.server_attendance_radius_m
      ? currentUserData.server_attendance_radius_m
      : 0.0;
  const position = new AMapInstance.LngLat(targetCoords[0], targetCoords[1]);
  tempAttendanceMarker = new AMapInstance.Marker({
    position: position,
    content: svgIconNormal,
    clickable: false,
    anchor: "bottom-center",
    zIndex: 200,
  });
  tempAttendanceCircle = new AMapInstance.Circle({
    center: position,
    radius: radius,
    strokeColor: "#00BFFF",
    strokeOpacity: 1,
    strokeWeight: 2,
    fillColor: "#00BFFF",
    fillOpacity: 0.2,
    zIndex: 199,
    bubble: true,
    clickable: false,
  });
  map.add(tempAttendanceMarker);
  map.add(tempAttendanceCircle);

  map.setFitView([tempAttendanceCircle], false, [120, 120, 120, 120]);
  const infoMarker = new AMapInstance.Text({
    text: "已显示签到区域，请在地图上单击选点",
    position: position,
    anchor: "bottom-center",
    offset: new AMapInstance.Pixel(0, -40),
    clickable: false,
    style: {
      "background-color": "#fff",
      padding: "5px 10px",
      "border-radius": "5px",
      "box-shadow": "0 2px 4px rgba(0,0,0,0.2)",
      "pointer-events": "none",
    },
  });
  map.add(infoMarker);
  const onMapClick = async (e) => {
    map.off("click", onMapClick);
    map.remove(infoMarker);
    const clickedLngLat = e.lnglat;
    const specificCoords = [clickedLngLat.lng, clickedLngLat.lat];
    const distance = fastDistanceMeters(
      clickedLngLat.lng,
      clickedLngLat.lat,
      targetCoords[0],
      targetCoords[1],
    );
    if (distance > radius) {
      logMessage_Info(
        `选点失败：距离 ${distance.toFixed(1)}m > ${radius.toFixed(1)}m`,
      );
      showModalAlert(
        "您选择的点不在签到范围内，请重新在地图上单击选点。",
        "选点无效",
      );
      map.add(infoMarker);
      map.on("click", onMapClick);
      return;
    }
    logMessage_Info(
      `已选择签到点: ${specificCoords.join(", ")} (距离 ${distance.toFixed(
        1,
      )}m)`,
    );
    try {
      const result = await callPythonAPI(
        "trigger_attendance",
        rollCallId,
        targetCoords,
        "specific",
        specificCoords,
        false,
      );
      if (result.success) {
        logMessage_Info(`签到成功: ${result.message}`);
        showModalAlert(`签到成功: ${result.message}`);
      } else {
        logMessage_Info(`签到失败: ${result.message}`);
        showModalAlert(`签到失败: ${result.message}`);
      }
    } catch (err) {
      logMessage_Info(`签到时发生JS错误: ${err}`);
    } finally {
      if (tempAttendanceMarker && map) {
        map.remove(tempAttendanceMarker);
        tempAttendanceMarker = null;
      }
      if (tempAttendanceCircle && map) {
        map.remove(tempAttendanceCircle);
        tempAttendanceCircle = null;
      }
      if (map) {
        map.setStatus({
          dragEnable: true,
          scrollWheel: true,
          doubleClickZoom: true,
        });
      }

      await fetchNotifications();
    }
  };

  map.on("click", onMapClick);
}

async function handleMakeupAttendance(event, rollCallId, targetCoords) {
  event.stopPropagation();
  logMessage_Info(`正在为您 [补签]... 活动ID: ${rollCallId}`);
  const result = await callPythonAPI(
    "trigger_attendance",
    rollCallId,
    targetCoords,
    "random",
    null,
    true,
  );
  if (result.success) {
    logMessage_Info(`补签成功: ${result.message}`);
    showModalAlert(`补签成功: ${result.message}`);
  } else {
    logMessage_Info(`补签失败: ${result.message}`);
    showModalAlert(`补签失败: ${result.message}`);
  }
  await fetchNotifications();
}
async function handleManualMakeupAttendance(event, rollCallId, targetCoords) {
  event.stopPropagation();
  if (getActiveMapProvider() !== "amap" || !map || !AMapInstance) {
    showModalAlert(
      `当前地图提供方为${getMapProviderDisplayName()}，手动地图选点暂仅支持高德地图。`,
      "提示",
    );
    return;
  }
  toggleNotifications(false, true);
  selectedTaskIndex = -1;
  renderTaskList();
  drawOnMap();
  logMessage_Info("请在地图上单击选择 [补签] 点...");
  if (tempAttendanceMarker && map) {
    map.remove(tempAttendanceMarker);
    tempAttendanceMarker = null;
  }
  if (tempAttendanceCircle && map) {
    map.remove(tempAttendanceCircle);
    tempAttendanceCircle = null;
  }
  const radius =
    currentUserData && currentUserData.server_attendance_radius_m
      ? currentUserData.server_attendance_radius_m
      : 0.0;
  const position = new AMapInstance.LngLat(targetCoords[0], targetCoords[1]);
  logMessage_Info(
    `系统签到点: ${targetCoords[0]}, ${targetCoords[1]} (半径: ${radius}米)`,
  );
  tempAttendanceMarker = new AMapInstance.Marker({
    position: position,
    content: svgIconMakeup,
    clickable: false,
    anchor: "bottom-center",
    zIndex: 200,
  });
  tempAttendanceCircle = new AMapInstance.Circle({
    center: position,
    radius: radius,
    strokeColor: "#F7B731",
    strokeOpacity: 1,
    strokeWeight: 2,
    fillColor: "#F7B731",
    fillOpacity: 0.2,
    zIndex: 199,
    bubble: true,
    clickable: false,
  });

  map.add(tempAttendanceMarker);
  map.add(tempAttendanceCircle);
  map.setFitView([tempAttendanceCircle], false, [120, 120, 120, 120]);
  const infoMarker = new AMapInstance.Text({
    text: "已显示签到区域，请在地图上单击选点 [补签]",
    position: position,
    anchor: "bottom-center",
    offset: new AMapInstance.Pixel(0, -40),
    clickable: false,
    style: {
      "background-color": "#fff",
      padding: "5px 10px",
      "border-radius": "5px",
      "box-shadow": "0 2px 4px rgba(0,0,0,0.2)",
      "pointer-events": "none",
    },
  });
  map.add(infoMarker);
  const onMapClick = async (e) => {
    map.off("click", onMapClick);
    map.remove(infoMarker);
    const clickedLngLat = e.lnglat;
    const specificCoords = [clickedLngLat.lng, clickedLngLat.lat];
    const distance = fastDistanceMeters(
      clickedLngLat.lng,
      clickedLngLat.lat,
      targetCoords[0],
      targetCoords[1],
    );
    if (distance > radius) {
      logMessage_Info(
        `[补签] 选点失败：距离 ${distance.toFixed(1)}m > ${radius.toFixed(1)}m`,
      );
      showModalAlert(
        "您选择的点不在签到范围内，请重新在地图上单击选点。",
        "选点无效",
      );
      map.add(infoMarker);
      map.on("click", onMapClick);
      return;
    }
    logMessage_Info(
      `已选择 [补签] 点: ${specificCoords.join(", ")} (距离 ${distance.toFixed(
        1,
      )}m)`,
    );

    try {
      const result = await callPythonAPI(
        "trigger_attendance",
        rollCallId,
        targetCoords,
        "specific",
        specificCoords,
        true,
      );
      if (result.success) {
        logMessage_Info(`补签成功: ${result.message}`);
        showModalAlert(`补签成功: ${result.message}`);
      } else {
        logMessage_Info(`补签失败: ${result.message}`);
        showModalAlert(`补签失败: ${result.message}`);
      }
    } catch (err) {
      logMessage_Info(`补签时发生JS错误: ${err}`);
    } finally {
      if (tempAttendanceMarker && map) {
        map.remove(tempAttendanceMarker);
        tempAttendanceMarker = null;
      }
      if (tempAttendanceCircle && map) {
        map.remove(tempAttendanceCircle);
        tempAttendanceCircle = null;
      }
      if (map) {
        map.setStatus({
          dragEnable: true,
          scrollWheel: true,
          doubleClickZoom: true,
        });
      }

      await fetchNotifications();
    }
  };

  map.on("click", onMapClick);
}

async function markAsRead(event, noticeId) {
  event.stopPropagation();
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = "...";

  try {
    const result = await callPythonAPI("mark_notification_read", noticeId);
    if (result.success) {
      await fetchNotifications();
      showNotifications();
    } else {
      showModalAlert(result.message || "标记已读失败");
      btn.disabled = false;
      btn.textContent = "设为已读";
    }
  } catch (e) {
    logMessage_Error("markAsRead failed:", e);
    btn.disabled = false;
    btn.textContent = "设为已读";
  }
}
async function markAllAsRead() {
  const btn = $("mark-all-read-btn");
  btn.disabled = true;
  btn.textContent = "处理中...";
  const unreadNotices = (window.currentNotifications || []).filter(
    (n) => !n.isRead,
  );
  if (unreadNotices.length === 0) {
    btn.textContent = "一键已读";
    return;
  }
  try {
    const promises = unreadNotices.map((n) =>
      callPythonAPI("mark_notification_read", n.id),
    );
    await Promise.all(promises);
    logMessage_Info(`“一键已读”操作完成，共处理 ${unreadNotices.length} 条。`);
  } catch (e) {
    logMessage_Error("markAllAsRead failed:", e);
    logMessage_Info(`“一键已读”时发生错误: ${e}`);
  } finally {
    await fetchNotifications();
    showNotifications();
    btn.disabled =
      (window.currentNotifications || []).filter((n) => !n.isRead).length === 0;
    btn.textContent = "一键已读";
  }
}
$("multi-remove-all-btn").addEventListener("click", () => multi_removeAll());
$("multi-remove-selected-btn").addEventListener("click", () => multi_removeSelected());
$("multi-refresh-all-btn").addEventListener("click", multi_refreshAll);
$("multi-select-all-check").addEventListener("change", multi_toggleSelectAll);
$("multi-start-selected-btn").addEventListener("click", multi_startSelected);
$("multi-stop-selected-btn").addEventListener("click", multi_stopSelected);
$("multi-refresh-selected-btn").addEventListener(
  "click",
  multi_refreshSelected,
);

// --- Next Script Block ---

window.mobile_multi_map_panel_initialize_mark = false;
window.mobile_map_panel_initialize_mark = false;

// ==================== 移动端UI交互函数 ====================
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
function switchMobileNotifTab(tabName) {
  const allTab = document.getElementById("mobile-notif-tab-all");
  const attTab = document.getElementById("mobile-notif-tab-attendance");
  const allList = document.getElementById("mobile-all-notifications-list");
  const attList = document.getElementById(
    "mobile-attendance-notifications-list",
  );
  if (tabName === "all") {
    allTab.className =
      "flex-1 py-2 text-sm font-semibold text-sky-600 border-b-2 border-sky-600 transition";
    attTab.className =
      "flex-1 py-2 text-sm font-semibold text-slate-400 border-b-2 border-transparent transition";
    allList.classList.remove("hidden");
    attList.classList.add("hidden");
  } else {
    attTab.className =
      "flex-1 py-2 text-sm font-semibold text-sky-600 border-b-2 border-sky-600 transition";
    allTab.className =
      "flex-1 py-2 text-sm font-semibold text-slate-400 border-b-2 border-transparent transition";
    attList.classList.remove("hidden");
    allList.classList.add("hidden");
  }
}
async function mobileRefreshNotifications(showalert = true) {
  if (showalert) {
    showModalAlert("正在刷新通知，请稍候...", "提示");
  }
  logMessage_Info("移动端：正在刷新通知...");
  const btn = document.getElementById("mobile-refresh-notifications-btn");
  if (btn) {
    btn.disabled = true;
    const originalText = (btn.textContent || "").trim();
  }

  try {
    await fetchNotifications();
    updateMobileNotificationUI();
    if (showalert) {
      showModalAlert("通知刷新完成", "成功");
    }
    logMessage_Info("移动端：通知刷新完成");
  } catch (error) {
    console.error("刷新通知失败:", error);
    showModalAlert("刷新通知失败，请稍后重试", "错误");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent =
        typeof originalText !== "undefined" ? originalText : "刷新";
    }
  }
}
function updateMobileNotificationUI() {
  const notifications = window.currentNotifications || [];
  const badge = document.getElementById("mobile-notification-badge");
  const unreadCount = notifications.filter((n) => !n.isRead).length;
  if (badge) {
    if (unreadCount > 0) {
      badge.textContent = unreadCount > 9 ? "9+" : unreadCount;
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }
  const attendanceNotices = notifications.filter(
    (n) => n.image === "attendance" || (n.title && n.title.includes("签到")),
  );
  const regularNotices = notifications;
  const allList = document.getElementById("mobile-all-notifications-list");
  if (allList) {
    if (regularNotices.length === 0) {
      allList.innerHTML =
        '<p class="text-slate-400 text-center py-8 text-sm">暂无通知</p>';
    } else {
      allList.innerHTML = "";
      regularNotices.forEach((notice) => {
        const item = document.createElement("div");
        item.className =
          "mobile-list-item " + (notice.isRead ? "opacity-60" : "");
        item.innerHTML = `
        <div class="flex-1">
          <div class="flex items-center justify-between mb-1">
            <span class="text-sm font-semibold text-slate-800">${escapeHtml(
              notice.title,
            )}</span>
            <span class="text-xs text-slate-400">${escapeHtml(
              formatNotificationTime(notice.createtime),
            )}</span>
          </div>
          <p class="text-xs text-slate-600">${escapeHtml(notice.content)}</p>
        </div>
        ${
          !notice.isRead
            ? '<span class="ml-2 w-2 h-2 bg-red-500 rounded-full flex-shrink-0"></span>'
            : ""
        }
      `;
        item.addEventListener("click", () =>
          markMobileNotificationRead(notice.id),
        );
        allList.appendChild(item);
      });
    }
  }

  const attList = document.getElementById(
    "mobile-attendance-notifications-list",
  );
  if (attList) {
    if (attendanceNotices.length === 0) {
      attList.innerHTML =
        '<p class="text-slate-400 text-center py-8 text-sm">暂无签到任务</p>';
    } else {
      attList.innerHTML = "";
      attendanceNotices.forEach((notice) => {
        const item = document.createElement("div");
        item.className = "mobile-list-item";
        let statusBadge = "";
        let actionButtons = "";

        if (notice.attendance_code === -1) {
          statusBadge =
            '<span class="text-xs font-semibold px-2 py-1 rounded-full bg-red-100 text-red-600">已过期</span>';
        } else if (notice.attendance_code === 1) {
          statusBadge =
            '<span class="text-xs font-semibold px-2 py-1 rounded-full bg-green-100 text-green-600">已签到</span>';
        } else if (notice.attendance_code === 0) {
          statusBadge =
            '<span class="text-xs font-semibold px-2 py-1 rounded-full bg-yellow-100 text-yellow-600">待签到</span>';
          actionButtons = `
          <button class="py-1 px-3 bg-sky-500 text-white rounded-lg text-xs font-medium hover:bg-sky-600 transition" onclick="event.stopPropagation(); mobileHandleAttendance(${escapeInlineJsArg(notice.id)})">
            签到
          </button>
        `;
        }

        item.innerHTML = `
        <div class="flex-1">
          <div class="flex items-center justify-between mb-1">
            <span class="text-sm font-semibold text-slate-800">${escapeHtml(
              notice.title,
            )}</span>
            ${statusBadge}
          </div>
          <div class="flex items-center justify-between">
            <span class="text-xs text-slate-600">${escapeHtml(
              notice.content,
            )}</span>
            <span class="text-xs text-slate-400 ml-2">${escapeHtml(
              formatNotificationTime(notice.createtime),
            )}</span>
          </div>
        </div>
        ${actionButtons}
      `;
        attList.appendChild(item);
      });
    }
  }
}
function syncMobileAttendanceList() {
  const mobileAttList = document.getElementById("mobile-attendance-list");
  if (!mobileAttList) return;
  const notifications = window.currentNotifications || [];
  const attendanceNotices = notifications.filter(
    (n) => n.image === "attendance" || (n.title && n.title.includes("签到")),
  );
  mobileAttList.innerHTML = "";
  if (attendanceNotices.length === 0) {
    mobileAttList.innerHTML =
      '<p class="text-slate-400 text-center py-8 text-sm">暂无签到任务</p>';
    return;
  }
  attendanceNotices.forEach((n) => {
    const item = document.createElement("div");
    item.className = "bg-white rounded-lg p-3 border border-slate-200 mb-2";
    let statusText = "未知";
    let statusClass = "text-slate-500";
    let buttonHtml = "";
    let targetCoords = "null";
    let canSign = false;
    try {
      const coordsStr = (n.updateBy || "").trim();
      const [lat, lon] = coordsStr.split(",").map(Number);
      if (!isNaN(lon) && !isNaN(lat)) {
        targetCoords = `[${lon}, ${lat}]`;
        canSign = true;
      }
    } catch (e) {}
    switch (n.attendance_code) {
      case -1:
        statusText = "已过期";
        statusClass = "text-red-600 font-semibold";
        if (canSign) {
          buttonHtml = `
          <button class="w-full mt-2 py-2 px-4 bg-orange-500 text-white rounded-lg text-sm font-medium hover:bg-orange-600 transition" 
            onclick="event.stopPropagation(); handleMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">
            随机补签
          </button>
        `;
        }
        break;
      case 1:
        statusText = "已签到";
        statusClass = "text-emerald-600 font-semibold";
        break;
      case 0:
        statusText = "待签到";
        statusClass = "text-sky-600 font-bold";
        if (canSign) {
          buttonHtml = `
          <div class="space-y-2 mt-2">
            <!-- 第一行：随机签到和随机补签 -->
            <div class="flex gap-2">
              <button class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 transition" 
                onclick="event.stopPropagation(); handleAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">
                随机签到
              </button>
              <button class="flex-1 py-2 px-4 bg-orange-500 text-white rounded-lg text-sm font-medium hover:bg-orange-600 transition" 
                onclick="event.stopPropagation(); handleMakeupAttendance(event, ${escapeInlineJsArg(n.id)}, ${targetCoords})">
                随机补签
              </button>
            </div>
            <!-- 第二行：地图选点签到按钮 -->
            <button class="w-full py-2 px-4 bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-lg text-sm font-bold hover:from-purple-600 hover:to-purple-700 transition-all shadow-md flex items-center justify-center gap-2" 
              onclick="event.stopPropagation(); openMobileMapAttendanceModal(${escapeInlineJsArg(n.id)}, ${targetCoords})">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              📍 地图选点签到
            </button>
          </div>
        `;
        }
        break;
      default:
        statusText = "状态未知";
        statusClass = "text-slate-400";
    }
    if (n.attendance_status_text && n.attendance_status_text.includes("失败")) {
      statusText = n.attendance_status_text;
      statusClass = "text-red-700 font-bold";
    }
    item.innerHTML = `
    <div class="flex justify-between items-start mb-2">
      <div class="flex-1">
        <p class="text-sm font-semibold text-slate-800 mb-1">${n.title}</p>
        <p class="text-xs text-slate-600">${n.content}</p>
      </div>
      <span class="text-xs ${statusClass} ml-2 flex-shrink-0">${statusText}</span>
    </div>
    <div class="text-xs text-slate-400">${escapeHtml(formatNotificationTime(n.createtime))}</div>
    ${buttonHtml}
  `;
    mobileAttList.appendChild(item);
  });
}
async function markMobileNotificationRead(noticeId) {
  try {
    const result = await callPythonAPI("mark_notification_read", noticeId);
    if (result.success) {
      await mobileRefreshNotifications();
    }
  } catch (error) {
    console.error("标记已读失败:", error);
  }
}
async function mobileMarkAllAsRead() {
  const notifications = window.currentNotifications || [];
  const unreadNotices = notifications.filter((n) => !n.isRead);

  if (unreadNotices.length === 0) {
    showModalAlert("没有未读通知", "提示");
    return;
  }
  try {
    const promises = unreadNotices.map((n) =>
      callPythonAPI("mark_notification_read", n.id),
    );
    await Promise.all(promises);

    await mobileRefreshNotifications();
    showModalAlert("已全部标记为已读", "成功");
  } catch (error) {
    console.error("一键已读失败:", error);
    showModalAlert("操作失败，请稍后重试", "错误");
  }
}
function expandMobileNotifications() {
  showNotifications();
}
async function mobileHandleAttendance(rollCallId) {
  const notifications = window.currentNotifications || [];
  const notice = notifications.find((n) => n.id === rollCallId);

  if (!notice) {
    showModalAlert("未找到签到活动信息", "错误");
    return;
  }
  try {
    const coordsStr = (notice.updateBy || "").trim();
    const [lat, lon] = coordsStr.split(",").map(Number);
    if (isNaN(lon) || isNaN(lat)) {
      showModalAlert("签到坐标无效", "错误");
      return;
    }
    const targetCoords = [lon, lat];
    const result = await callPythonAPI(
      "trigger_attendance",
      rollCallId,
      targetCoords,
      "random",
      null,
      false,
    );
    if (result.success) {
      showModalAlert("签到成功！", "成功");
      await mobileRefreshNotifications();
    } else {
      showModalAlert("签到失败: " + result.message, "错误");
    }
  } catch (error) {
    console.error("签到失败:", error);
    showModalAlert("签到失败，请稍后重试", "错误");
  }
}
async function mobileRefreshTasks(showalert = true) {
  try {
    if (showalert) {
      showModalAlert("正在刷新任务列表...", "提示");
    }
    await refreshTasks();
    if (showalert) {
      showModalAlert("任务列表已刷新", "成功");
    }
  } catch (error) {
    console.error("[移动端] 刷新任务列表失败:", error);
    showModalAlert("刷新任务列表失败", "错误");
  }
}
let mobileTaskRunning = false;
let mobileTaskPaused = false;
function updateMobileTaskUI(status, detail = "") {
  const statusIndicator = $("mobile-status-indicator");
  const statusDetail = $("mobile-status-detail");
  const startBtn = $("mobile-start-btn");
  const stopBtn = $("mobile-stop-btn");
  if (statusIndicator) {
    statusIndicator.textContent = status;
    statusIndicator.className = "text-xs font-semibold px-2 py-1 rounded-full";
    if (status === "运行中") {
      statusIndicator.className += " bg-green-200 text-green-600";
    } else if (status === "已暂停") {
      statusIndicator.className += " bg-yellow-200 text-yellow-600";
    } else if (status === "已停止") {
      statusIndicator.className += " bg-red-200 text-red-600";
    } else if (status === "已完成") {
      statusIndicator.className += " bg-blue-200 text-blue-600";
    } else {
      statusIndicator.className += " bg-slate-200 text-slate-600";
    }
  }
  if (statusDetail) {
    statusDetail.textContent = detail || "等待执行任务";
  }
  if (startBtn && stopBtn) {
    if (status === "运行中") {
      startBtn.disabled = true;
      stopBtn.disabled = false;
    } else if (status === "已暂停") {
      startBtn.disabled = false;
      stopBtn.disabled = false;
    } else if (status === "已完成") {
      startBtn.disabled = false;
      stopBtn.disabled = true;
      mobileTaskRunning = false;
      mobileTaskPaused = false;
    } else {
      startBtn.disabled = false;
      stopBtn.disabled = true;
    }
  }
}
function updateMobileProgress(percent, text) {
  const progressBar = $("mobile-progress-bar");
  const progressText = $("mobile-progress-text");
  if (progressBar) {
    progressBar.style.width = percent + "%";
  }
  if (progressText) {
    progressText.textContent = text || percent + "%";
  }
}
function mobileAddTask() {
  addTask();
}
async function mobileStartTask() {
  try {
    // ========== 检查是否选择了任务 ==========
    // selectedTaskIndex 是全局变量，表示当前选中的任务索引
    // -1 表示未选择任何任务
    if (selectedTaskIndex < 0 || selectedTaskIndex === -1) {
      showModalAlert("请先选择一个任务再开始执行", "未选择任务");
      return;
    }

    // ========== 添加欠费检查 ==========
    // 按当前模式执行欠费检查（仅在 require_payment 启用时）：
    // - 单账号模式：只检查当前账号
    // - 多账号模式：只检查列表中的账号
    const canStart = await _checkOverdueBeforeStartByCurrentMode();
    if (!canStart) {
      // 用户有欠费且未完成缴费，阻止任务启动
      return;
    }
    const overdueOverride = _consumeOverdueForceOverride();
    // ========== 欠费检查结束 ==========

    // ========== 检查后端是否已有任务在运行 ==========
    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    const isBackendRunning =
      statusRes.success &&
      statusRes.task_status &&
      statusRes.task_status.status === "running";
    if (isBackendRunning) {
      mobileTaskRunning = true;
      mobileTaskPaused = false;
      updateMobileTaskUI("运行中", "后台已有任务在运行");
      showModalAlert("后台已有任务在运行，无法启动新任务", "警告");
      if (!backgroundTaskPollInterval) {
        startBackgroundTaskPolling();
      }
      return;
    }
    if (mobileTaskRunning && !mobileTaskPaused) {
      showModalAlert("任务正在运行中", "提示");
      return;
    }
    updateMobileTaskUI("准备中", "正在启动任务...");
    if (currentRunData) {
      currentRunData.target_sequence = 1;
      currentRunData.isInTargetZone = false;
    }
    const result = await callPythonAPI_raw(
      "/api/background_task/start",
      "POST",
      {
        task_indices: [selectedTaskIndex],
        auto_generate: true,
        ...overdueOverride,
      },
    );
    if (result && result.success) {
      mobileTaskRunning = true;
      mobileTaskPaused = false;
      updateMobileTaskUI("运行中", "任务执行中");
      updateMobileProgress(0, "0%");
      showModalAlert("任务已启动", "成功");
      setTimeout(() => startBackgroundTaskPolling(), 500);
    } else {
      const isRunning = await syncMobileBtnStateFromBackend();
      if (!isRunning) {
        updateMobileTaskUI("未启动", result?.message || "启动失败");
      }
      showModalAlert(result?.message || "启动失败", "错误");
    }
  } catch (error) {
    console.error("[移动端] 启动任务失败:", error);
    const isRunning = await syncMobileBtnStateFromBackend();
    if (!isRunning) {
      updateMobileTaskUI("错误", "启动失败");
    }
    showModalAlert("启动任务时发生错误", "错误");
  }
}
async function syncMobileBtnStateFromBackend() {
  try {
    const res = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    if (
      res.success &&
      res.task_status &&
      res.task_status.status === "running"
    ) {
      singleRunProgressVisualActive = true;
      mobileTaskRunning = true;
      mobileTaskPaused = false;
      updateMobileTaskUI("运行中", "任务执行中 (已恢复)");
      if (!backgroundTaskPollInterval) {
        startBackgroundTaskPolling();
      }
      return true;
    }
  } catch (e) {
    console.error("同步状态失败:", e);
  }
  mobileTaskRunning = false;
  return false;
}
async function mobileStopTask() {
  try {
    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    const isBackendRunning =
      statusRes.success &&
      statusRes.task_status &&
      statusRes.task_status.status === "running";

    if (!isBackendRunning) {
      mobileTaskRunning = false;
      updateMobileTaskUI("未启动", "没有正在运行的任务");
      showModalAlert("没有正在运行的任务", "提示");
      return;
    }

    updateMobileTaskUI("停止中", "正在停止任务...");

    const result = await callPythonAPI_raw(
      "/api/background_task/stop",
      "POST",
      {},
    );

    if (result && result.success) {
      mobileTaskRunning = false;
      mobileTaskPaused = false;
      updateMobileTaskUI("已停止", "任务已停止");
      showModalAlert("任务已停止", "成功");
      stopBackgroundTaskPolling();
      clearSingleExecutionVisuals();
    } else {
      const isRunning = await syncMobileBtnStateFromBackend();
      if (isRunning) {
        updateMobileTaskUI("运行中", result?.message || "停止失败");
      } else {
        updateMobileTaskUI("已停止", "任务已停止 (修正状态)");
      }
      showModalAlert(result?.message || "停止失败", "错误");
    }
  } catch (error) {
    console.error("[移动端] 停止任务失败:", error);
    const isRunning = await syncMobileBtnStateFromBackend();
    if (isRunning) {
      updateMobileTaskUI("运行中", "停止请求异常");
    } else {
      updateMobileTaskUI("已停止", "连接异常 (假设已停)");
    }
    showModalAlert("停止任务时发生错误", "错误");
  }
}
async function mobilePauseTask() {
  try {
    if (!mobileTaskRunning) {
      showModalAlert("没有正在运行的任务", "提示");
      return;
    }

    if (mobileTaskPaused) {
      showModalAlert("任务已暂停", "提示");
      return;
    }

    const result = await callPythonAPI("pause_run");
    if (result && result.success) {
      mobileTaskPaused = true;
      updateMobileTaskUI("已暂停", "任务已暂停");
      showModalAlert("任务已暂停", "成功");
    } else {
      showModalAlert(result?.message || "暂停失败", "错误");
    }
  } catch (error) {
    console.error("[移动端] 暂停任务失败:", error);
    showModalAlert("暂停任务时发生错误", "错误");
  }
}
async function mobileResumeTask() {
  try {
    if (!mobileTaskPaused) {
      showModalAlert("任务未暂停", "提示");
      return;
    }

    const result = await callPythonAPI("resume_run");
    if (result && result.success) {
      mobileTaskPaused = false;
      updateMobileTaskUI("运行中", "任务继续执行");
      showModalAlert("任务已继续", "成功");
    } else {
      showModalAlert(result?.message || "继续失败", "错误");
    }
  } catch (error) {
    console.error("[移动端] 继续任务失败:", error);
    showModalAlert("继续任务时发生错误", "错误");
  }
}
async function mobileResetTask() {
  try {
    showMobileConfirm(
      "重置任务",
      "确定要重置任务吗？这将清除当前进度。",
      async () => {
        const result = await callPythonAPI("reset_run");
        if (result && result.success) {
          mobileTaskRunning = false;
          mobileTaskPaused = false;
          updateMobileTaskUI("未启动", "任务已重置");
          updateMobileProgress(0, "0%");
          showModalAlert("任务已重置", "成功");
        } else {
          showModalAlert(result?.message || "重置失败", "错误");
        }
      },
    );
  } catch (error) {
    console.error("[移动端] 重置任务失败:", error);
    showModalAlert("重置任务时发生错误", "错误");
  }
}
async function exitMobileMultiAccount() {
  const adminPanelEl = document.getElementById("mobile-admin-panel-unified");
  if (adminPanelEl) {
    adminPanelEl.style.display = "none";
    adminPanelEl.classList.add("hidden");
  }
  try {
    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    const isTaskRunning =
      statusRes.success &&
      statusRes.task_status &&
      statusRes.task_status.status === "running";
    if (isTaskRunning || mobileTaskRunning) {
      showMobileConfirm(
        "警告：任务正在运行",
        "检测到有跑步任务正在执行中。退出多账号模式将停止当前任务，可能导致数据不完整。\n\n确定要继续退出吗？",
        async () => {
          try {
            await callPythonAPI_raw("/api/background_task/stop", "POST", {});
            stopBackgroundTaskPolling();
            clearSingleExecutionVisuals();
            updateMobileTaskUI("已停止", "任务已停止（退出多账号模式）");
            mobileTaskRunning = false;
            mobileTaskPaused = false;
            performExitMobileMultiAccount();
          } catch (error) {
            console.error("[移动端] 停止任务失败:", error);
            showModalAlert("停止任务时出错，但仍将退出多账号模式", "警告");
            performExitMobileMultiAccount();
          }
        },
        () => {
          if (adminPanelEl) {
            adminPanelEl.style.display = "";
            adminPanelEl.classList.remove("hidden");
          }
          showModalAlert("已取消退出多账号模式", "提示");
        },
      );
      return;
    }
  } catch (error) {
    console.error("[移动端] 检查任务状态失败:", error);
    showModalAlert("无法检查任务状态，将继续退出", "警告");
  }
  performExitMobileMultiAccount();
}
async function performExitMobileMultiAccount() {
  stopMultiAccountAutoRefresh();
  const adminPanel = document.getElementById("mobile-admin-panel-unified");
  if (adminPanel) {
    adminPanel.style.display = "none";
    adminPanel.classList.add("hidden");
  }
  await callPythonAPI("exit_multi_account_mode");
  document.getElementById("mobile-multi-account-app").classList.add("hidden");
  document.getElementById("mobile-login-container").classList.remove("hidden");
  updateMobileNavVisibility(false);
}
async function exitMobileSingleAccount() {
  try {
    console.log("[移动端] 开始退出单账号模式...");
    const adminPanelEl = document.getElementById("mobile-admin-panel-unified");
    if (adminPanelEl) {
      adminPanelEl.style.display = "none";
      adminPanelEl.classList.add("hidden");
    }
    const result = await callPythonAPI("logout");
    if (!result || !result.success) {
      console.error(
        "[移动端] 退出单账号模式失败:",
        result?.message || "未知错误",
      );
      showModalAlert("退出失败: " + (result?.message || "未知错误"), "错误");
      return;
    }
    console.log("[移动端] 退出单账号模式成功，开始切换界面...");
    resetLegacyRunnerExecution();
    if (typeof destroyMobileSingleMap === "function") {
      destroyMobileSingleMap();
      console.log("[退出单账号] 移动端：已销毁单账号地图");
    }
    const mobileMainApp = document.getElementById("mobile-main-app");
    if (mobileMainApp) {
      mobileMainApp.classList.add("hidden");
    }
    const loginContainer = document.getElementById("mobile-login-container");
    if (loginContainer) {
      loginContainer.classList.remove("hidden");
    }
    updateMobileNavVisibility(false);
    setTimeout(async () => {
      console.log("[移动端] 开始刷新会话列表...");
      if (typeof loadMobileSessionsList === "function") {
        await loadMobileSessionsList();
        console.log("[移动端] 会话列表刷新完成 (loadMobileSessionsList)");
      } else {
        console.warn("[移动端] 未找到 loadMobileSessionsList 函数");
      }
    }, 200);
    showModalAlert("已退出单账号模式", "成功");
    console.log("[移动端] 退出单账号模式流程完成");
  } catch (error) {
    console.error("[移动端] 退出单账号模式时发生错误:", error);
    showModalAlert("退出时发生错误: " + error.message, "错误");
  }
}
async function exitMobileSingleAccountSafe() {
  const adminPanelEl = document.getElementById("mobile-admin-panel-unified");
  if (adminPanelEl) {
    adminPanelEl.style.display = "none";
    adminPanelEl.classList.add("hidden");
  }
  try {
    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    const isTaskRunning =
      statusRes.success &&
      statusRes.task_status &&
      statusRes.task_status.status === "running";
    if (isTaskRunning || mobileTaskRunning) {
      showMobileConfirm(
        "警告：任务正在运行",
        "检测到有跑步任务正在执行中。退出单账号模式将停止当前任务，可能导致数据不完整。\n\n确定要继续退出吗？",
        async () => {
          try {
            await callPythonAPI_raw("/api/background_task/stop", "POST", {});
            stopBackgroundTaskPolling();
            clearSingleExecutionVisuals();
            updateMobileTaskUI("已停止", "任务已停止（退出单账号模式）");
            mobileTaskRunning = false;
            mobileTaskPaused = false;
            await exitMobileSingleAccount();
          } catch (error) {
            console.error("[移动端] 停止任务失败:", error);
            showModalAlert("停止任务时出错，但仍将退出单账号模式", "警告");
            await exitMobileSingleAccount();
          }
        },
        () => {
          if (adminPanelEl) {
            adminPanelEl.style.display = "";
            adminPanelEl.classList.remove("hidden");
          }
          showModalAlert("已取消退出单账号模式", "提示");
        },
      );
      return;
    }
    await exitMobileSingleAccount();
  } catch (error) {
    console.error("[移动端] 检查任务状态失败:", error);
    showModalAlert("无法检查任务状态，将继续退出", "警告");
    await exitMobileSingleAccount();
  }
}
async function exitMobileMultiAccountToSessions() {
  try {
    console.log("[移动端] 开始退出多账号模式...");
    stopMultiAccountAutoRefresh();
    const adminPanelEl2 = document.getElementById("mobile-admin-panel-unified");
    if (adminPanelEl2) {
      adminPanelEl2.style.display = "none";
      adminPanelEl2.classList.add("hidden");
    }
    const result = await callPythonAPI("exit_multi_account_mode");
    if (!result || !result.success) {
      console.error(
        "[移动端] 退出多账号模式失败:",
        result?.message || "未知错误",
      );
      showModalAlert("退出失败: " + (result?.message || "未知错误"), "错误");
      return;
    }

    console.log("[移动端] 退出多账号模式成功，开始切换界面...");
    const mobileMultiApp = document.getElementById("mobile-multi-account-app");
    if (mobileMultiApp) {
      mobileMultiApp.classList.add("hidden");
    }
    const loginContainer = document.getElementById("mobile-login-container");
    if (loginContainer) {
      loginContainer.classList.remove("hidden");
    }
    updateMobileNavVisibility(false);
    setTimeout(async () => {
      console.log("[移动端] 开始刷新会话列表...");
      if (typeof loadMobileSessionsList === "function") {
        await loadMobileSessionsList();
        console.log("[移动端] 会话列表刷新完成 (loadMobileSessionsList)");
      } else {
        console.warn("[移动端] 未找到 loadMobileSessionsList 函数");
      }
    }, 200);
    showModalAlert("已退出多账号模式", "成功");
    console.log("[移动端] 退出多账号模式流程完成");
  } catch (error) {
    console.error("[移动端] 退出多账号模式时发生错误:", error);
    showModalAlert("退出时发生错误: " + error.message, "错误");
  }
}
function mobileToggleSelectAllAccounts() {
  const checkbox = document.getElementById("mobile-select-all-accounts");
  const accountCheckboxes = document.querySelectorAll(
    '#mobile-multi-account-list input[type="checkbox"]',
  );
  accountCheckboxes.forEach((cb) => {
    cb.checked = checkbox.checked;
  });
}
async function mobileStartSelectedAccounts() {
  try {
    // ========== 步骤1：获取选中的账号复选框 ==========
    // 在移动端多账号列表中查找所有被勾选的账号复选框
    const selected = document.querySelectorAll(
      '#mobile-multi-account-list input[type="checkbox"]:checked',
    );

    // ========== 步骤2：验证是否选择了账号 ==========
    if (selected.length === 0) {
      // 如果没有选中任何账号，提示用户并退出
      showModalAlert("请先选择要启动的账号", "错误");
      return;
    }

    // ========== 步骤3：提取选中账号的用户名列表 ==========
    // 从每个复选框的父元素中获取data-username属性
    const selectedUsernames = Array.from(selected)
      .map((checkbox) => {
        // 向上查找包含data-username属性的父元素
        const accountElement = checkbox.closest("[data-username]");
        // 返回用户名，如果找不到则返回null
        return accountElement ? accountElement.dataset.username : null;
      })
      .filter(Boolean); // 过滤掉null和undefined值

    // ========== 步骤4：欠费检查（只检查选中的账号）==========
    // 【重要】传入选中的账号列表，只检查这些账号的欠费情况
    // 避免显示未选中账号的欠费信息
    const canStart = await checkOverdueBeforeStart(selectedUsernames);
    if (!canStart) {
      // 欠费检查未通过，用户选择不缴费或取消，直接返回不启动任务
      return;
    }
    // ========== 欠费检查结束 ==========

    // ========== 步骤5：执行启动操作 ==========
    await multi_startSelected();
    showModalAlert(`正在启动 ${selected.length} 个账号`, "成功");
  } catch (error) {
    console.error("[移动端] 启动选中账号失败:", error);
    showModalAlert("启动选中账号失败", "错误");
  }
}
async function mobileStopSelectedAccounts() {
  try {
    const selected = document.querySelectorAll(
      '#mobile-multi-account-list input[type="checkbox"]:checked',
    );
    if (selected.length === 0) {
      showModalAlert("请先选择要停止的账号", "错误");
      return;
    }
    await multi_stopSelected();
    showModalAlert(`正在停止 ${selected.length} 个账号`, "成功");
  } catch (error) {
    console.error("[移动端] 停止选中账号失败:", error);
    showModalAlert("停止选中账号失败", "错误");
  }
}
function mobileAddMultiAccount() {
  try {
    multi_addFromConfig();
  } catch (error) {
    console.error("[移动端] 添加账号失败:", error);
    showModalAlert("添加账号失败", "错误");
  }
}
async function mobileRefreshMultiAccounts() {
  try {
    showModalAlert("正在刷新账号列表...", "提示");
    await multi_refreshAll();
    showModalAlert("账号列表已刷新", "成功");
  } catch (error) {
    console.error("[移动端] 刷新账号列表失败:", error);
    showModalAlert("刷新账号列表失败", "错误");
  }
}
async function mobileStartAllAccounts() {
  try {
    // ========== 步骤1：获取账号总数 ==========
    // 从页面元素中读取账号计数
    const count = parseInt($("multi-account-count")?.textContent || "0", 10);

    // ========== 步骤2：验证账号列表是否为空 ==========
    if (!count || count <= 0) {
      showModalAlert("账号列表为空，无法启动", "错误");
      return;
    }

    // 与 PC 端统一：只检查当前多账号界面实际显示的账号。
    let skipOverdue = false;
    const canStart = await _checkOverdueBeforeStartByCurrentMode({
      allowSkip: true,
      onSkip: () => {
        skipOverdue = true;
      },
    });
    if (!canStart) {
      return;
    }
    const overdueOverride = _consumeOverdueForceOverride();

    // ========== 步骤3：读取启动配置 ==========
    const randomDelayCheck = document.getElementById(
      "mobile-multi-random-delay-check",
    );
    const onlyIncompleteCheck = document.getElementById(
      "mobile-multi-only-incomplete-check",
    );
    const use_delay = randomDelayCheck ? randomDelayCheck.checked : true;
    const min_delay = 0;
    const max_delay = 300;
    const run_only_incomplete = onlyIncompleteCheck
      ? onlyIncompleteCheck.checked
      : true;

    // ========== 步骤4：调用后端API启动所有账号 ==========
    showModalAlert(`正在启动全部 ${count} 个账号...`, "提示");
    const result = await callPythonAPI(
      "multi_start_all_accounts",
      min_delay,
      max_delay,
      use_delay,
      run_only_incomplete,
      skipOverdue,
      overdueOverride.bypass_overdue,
      overdueOverride.waive_charge,
    );

    // ========== 步骤5：处理返回结果 ==========
    if (!result || !result.success) {
      showModalAlert(result?.message || "启动全部账号失败", "错误");
      return;
    }

    showModalAlert("已发送全部启动指令", "成功");
  } catch (error) {
    console.error("[移动端] 启动全部账号失败:", error);
    showModalAlert("启动全部账号失败", "错误");
  }
}
async function mobileStopAllAccounts() {
  try {
    await multi_stopAll();
    showModalAlert("已发送全部停止指令", "成功");
  } catch (error) {
    console.error("[移动端] 停止全部账号失败:", error);
    showModalAlert("停止全部账号失败", "错误");
  }
}
async function mobileRefreshAllAccounts() {
  try {
    showModalAlert("正在刷新所有账号...", "提示");
    await multi_refreshAll();
    showModalAlert("所有账号已刷新", "成功");
  } catch (error) {
    console.error("[移动端] 刷新所有账号失败:", error);
    showModalAlert("刷新所有账号失败", "错误");
  }
}
async function mobileRemoveSelectedAccounts() {
  try {
    const selected = document.querySelectorAll(
      '#mobile-multi-account-list input[type="checkbox"]:checked',
    );
    if (selected.length === 0) {
      showModalAlert("请先选择要删除的账号", "错误");
      return;
    }
    showMobileConfirm(
      "删除账号",
      `确定要删除选中的 ${selected.length} 个账号吗？`,
      async () => {
        await multi_removeSelected();
        showModalAlert(`已删除 ${selected.length} 个账号`, "成功");
      },
    );
  } catch (error) {
    console.error("[移动端] 删除选中账号失败:", error);
    showModalAlert("删除选中账号失败", "错误");
  }
}
function toggleMobileMoreMenu(show) {
  const modal = document.getElementById("mobile-more-menu-modal");
  if (modal) {
    if (show) {
      modal.classList.remove("hidden");
    } else {
      modal.classList.add("hidden");
    }
  }
}
function toggleMobileAdminPanel(show) {
  const modal = document.getElementById("mobile-admin-panel-modal");
  if (modal) {
    if (show) {
      modal.classList.remove("hidden");
      initMobileAdminPanel("mobile-admin");
    } else {
      modal.classList.add("hidden");
    }
  }
}
function toggleMobileUserDetails(show) {
  if (!isMobileMode) {
    toggleUserDetails(show);
    return;
  }
  const modal = document.getElementById("mobile-user-details-modal");
  if (modal) {
    if (show) {
      modal.classList.remove("hidden");
    } else {
      modal.classList.add("hidden");
    }
  }
}
function toggleMobileTaskDetails(show) {
  const modal = document.getElementById("mobile-task-details-modal");
  if (modal) {
    if (show) {
      modal.classList.remove("hidden");
    } else {
      modal.classList.add("hidden");
    }
  }
}
function toggleMobileNotifications(show) {
  const modal = document.getElementById("mobile-notifications-modal");

  // 检查元素是否存在，防止空指针错误
  if (modal) {
    // 根据show参数决定显示或隐藏
    if (show) {
      // 移除hidden类，显示模态框
      modal.classList.remove("hidden");
      // 加载通知内容（调用已存在的函数）
      // updateMobileNotificationUI();
    } else {
      // 添加hidden类，隐藏模态框
      modal.classList.add("hidden");
    }
  }
}
function showMobileConfirm(title, message, onConfirm, onCancel) {
  const modal = document.getElementById("mobile-confirm-modal");
  if (!modal) {
    console.error("找不到移动端确认对话框元素");
    return;
  }
  const titleElement = document.getElementById("mobile-confirm-title");
  if (titleElement) {
    titleElement.textContent = title;
  }
  const messageElement = document.getElementById("mobile-confirm-message");
  if (messageElement) {
    messageElement.textContent = message;
  }
  const cancelBtn = document.getElementById("mobile-confirm-cancel-btn");
  const okBtn = document.getElementById("mobile-confirm-ok-btn");
  const closeModal = () => {
    modal.classList.add("hidden");
  };
  const newCancelBtn = cancelBtn.cloneNode(true);
  const newOkBtn = okBtn.cloneNode(true);
  cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
  okBtn.parentNode.replaceChild(newOkBtn, okBtn);
  newCancelBtn.addEventListener("click", () => {
    closeModal();
    if (onCancel && typeof onCancel === "function") {
      onCancel();
    }
  });
  newOkBtn.addEventListener("click", () => {
    closeModal();
    if (onConfirm && typeof onConfirm === "function") {
      onConfirm();
    }
  });
  modal.onclick = (e) => {
    if (e.target === modal) {
      closeModal();
      if (onCancel && typeof onCancel === "function") {
        onCancel();
      }
    }
  };
  modal.classList.remove("hidden");
}
async function mobileLogout() {
  try {
    const statusRes = await callPythonAPI_raw(
      "/api/background_task/status",
      "GET",
      null,
    );
    const isTaskRunning =
      statusRes.success &&
      statusRes.task_status &&
      statusRes.task_status.status === "running";
    if (isTaskRunning || mobileTaskRunning) {
      showMobileConfirm(
        "警告：任务正在运行",
        "检测到有跑步任务正在执行中。退出登录将停止当前任务，可能导致数据不完整。\n\n确定要继续退出吗？",
        async () => {
          try {
            await callPythonAPI_raw("/api/background_task/stop", "POST", {});
            stopBackgroundTaskPolling();
            clearSingleExecutionVisuals();
            updateMobileTaskUI("已停止", "任务已停止（退出登录）");
            mobileTaskRunning = false;
            mobileTaskPaused = false;
            performMobileLogout();
          } catch (error) {
            console.error("[移动端] 停止任务失败:", error);
            showModalAlert("停止任务时出错，但仍将退出登录", "警告");
            performMobileLogout();
          }
        },
        () => {
          showModalAlert("已取消退出登录", "提示");
        },
      );
      return;
    }
  } catch (error) {
    console.error("[移动端] 检查任务状态失败:", error);
    showModalAlert("无法检查任务状态，将继续退出", "警告");
  }
  performMobileLogout();
}
function performMobileLogout() {
  showMobileConfirm("退出登录", "确定要退出登录吗？", () => {
    resetLegacyRunnerExecution();
    const mobileMainApp = document.getElementById("mobile-main-app");
    if (mobileMainApp) {
      mobileMainApp.classList.add("hidden");
    }
    const loginContainer = document.getElementById("mobile-login-container");
    if (loginContainer) {
      loginContainer.classList.remove("hidden");
    }
    updateMobileNavVisibility(false);
    showModalAlert("已退出登录", "成功");
  });
}
async function loadMobileUserDetails() {
  try {
    if (!currentUserData || !currentUserData.student_id) {
      const emptyDiv = document.getElementById("mobile-user-details-empty");
      const avatarDiv = document.getElementById("mobile-user-details-avatar");
      const basicDiv = document.getElementById("mobile-user-details-basic");
      const schoolDiv = document.getElementById("mobile-user-details-school");
      const loginDiv = document.getElementById("mobile-user-details-login");
      const uaDiv = document.getElementById("mobile-user-details-ua");
      if (emptyDiv) emptyDiv.classList.remove("hidden");
      if (avatarDiv) avatarDiv.classList.add("hidden");
      if (basicDiv) basicDiv.classList.add("hidden");
      if (schoolDiv) schoolDiv.classList.add("hidden");
      if (loginDiv) loginDiv.classList.add("hidden");
      if (uaDiv) uaDiv.classList.add("hidden");
      showModalAlert("请先登录", "警告");
      return;
    }
    const user_data = currentUserData;
    const emptyDiv = document.getElementById("mobile-user-details-empty");
    const avatarDiv = document.getElementById("mobile-user-details-avatar");
    const basicDiv = document.getElementById("mobile-user-details-basic");
    const schoolDiv = document.getElementById("mobile-user-details-school");
    const loginDiv = document.getElementById("mobile-user-details-login");
    const uaDiv = document.getElementById("mobile-user-details-ua");
    if (emptyDiv) emptyDiv.classList.add("hidden");
    if (avatarDiv) avatarDiv.classList.remove("hidden");
    if (basicDiv) basicDiv.classList.remove("hidden");
    if (schoolDiv) schoolDiv.classList.remove("hidden");
    if (loginDiv) loginDiv.classList.remove("hidden");
    if (uaDiv) uaDiv.classList.remove("hidden");
    const avatarImg = document.getElementById("mobile-user-details-avatar-img");
    const nameText = document.getElementById("mobile-user-details-name");

    if (avatarImg && user_data.avatar) {
      avatarImg.src = user_data.avatar;
    }
    if (nameText) {
      nameText.textContent = user_data.name || "未知用户";
    }
    const basicList = document.getElementById("mobile-user-details-basic-list");
    if (basicList) {
      basicList.innerHTML = "";
      const basicInfo = {
        学号: user_data.student_id,
        用户名: user_data.username,
        性别: user_data.gender,
        手机号: user_data.phone,
        用户ID: user_data.id,
        身份证号: user_data.id_card,
      };
      Object.entries(basicInfo).forEach(([label, value]) => {
        const p = document.createElement("div");
        p.className = "flex items-start gap-2";
        p.innerHTML = `
        <span class="font-semibold text-slate-600 min-w-[80px]">${label}:</span>
        <span class="text-slate-800 break-all flex-1">${value || "NULL"}</span>
      `;
        basicList.appendChild(p);
      });
    }
    const schoolList = document.getElementById(
      "mobile-user-details-school-list",
    );
    if (schoolList) {
      schoolList.innerHTML = "";
      const schoolInfo = {
        学校: user_data.school_name,
        属性: user_data.attribute_type,
      };
      Object.entries(schoolInfo).forEach(([label, value]) => {
        const p = document.createElement("div");
        p.className = "flex items-start gap-2";
        p.innerHTML = `
        <span class="font-semibold text-slate-600 min-w-[80px]">${label}:</span>
        <span class="text-slate-800 break-all flex-1">${value || "NULL"}</span>
      `;
        schoolList.appendChild(p);
      });
    }
    const loginList = document.getElementById("mobile-user-details-login-list");
    if (loginList) {
      loginList.innerHTML = "";
      const loginInfo = {
        注册时间: user_data.registration_time,
        首次登录: user_data.first_login_time,
        上次登录: user_data.last_login_time,
        当前登录: user_data.current_login_time,
      };
      Object.entries(loginInfo).forEach(([label, value]) => {
        const p = document.createElement("div");
        p.className = "flex items-start gap-2";
        p.innerHTML = `
        <span class="font-semibold text-slate-600 min-w-[80px]">${label}:</span>
        <span class="text-slate-800 break-all flex-1">${value || "NULL"}</span>
      `;
        loginList.appendChild(p);
      });
    }
    const uaText = document.getElementById("mobile-user-details-ua-text");
    if (uaText) {
      const uaString = getCurrentSessionUAText();
      uaText.textContent = uaString;
    }
    // showModalAlert("用户详情加载成功", "成功");
    logMessage_Info("用户详情加载成功");
  } catch (error) {
    console.error("加载用户详情失败:", error);
    showModalAlert("加载用户详情失败: " + error.message, "错误");
  }
}
async function loadMobileProfile() {
  await loadMobileUserDetails();
}
function loadMobileTaskDetails() {
  if (!currentRunData || !currentRunData.run_name) {
    const emptyDiv = document.getElementById("mobile-task-details-empty");
    const basicDiv = document.getElementById("mobile-task-details-basic");
    const timeDiv = document.getElementById("mobile-task-details-time");
    const pointsDiv = document.getElementById("mobile-task-details-points");
    const historyDiv = document.getElementById("mobile-task-details-history");
    if (emptyDiv) emptyDiv.classList.remove("hidden");
    if (basicDiv) basicDiv.classList.add("hidden");
    if (timeDiv) timeDiv.classList.add("hidden");
    if (pointsDiv) pointsDiv.classList.add("hidden");
    if (historyDiv) historyDiv.classList.add("hidden");
    showModalAlert("请先在任务列表中选择一个任务", "警告");
    return;
  }
  const emptyDiv = document.getElementById("mobile-task-details-empty");
  const basicDiv = document.getElementById("mobile-task-details-basic");
  const timeDiv = document.getElementById("mobile-task-details-time");
  const pointsDiv = document.getElementById("mobile-task-details-points");
  const historyDiv = document.getElementById("mobile-task-details-history");
  if (emptyDiv) emptyDiv.classList.add("hidden");
  if (basicDiv) basicDiv.classList.remove("hidden");
  if (timeDiv) timeDiv.classList.remove("hidden");
  if (pointsDiv) pointsDiv.classList.remove("hidden");
  if (historyDiv) historyDiv.classList.remove("hidden");
  const basicList = document.getElementById("mobile-task-details-basic-list");
  if (basicList) {
    basicList.innerHTML = "";
    const basicInfo = {
      任务名称: currentRunData.run_name,
      任务状态: currentRunData.status == 1 ? "已完成 ✓" : "未完成",
      任务ID: currentRunData.errand_id,
      计划ID: currentRunData.errand_schedule,
    };
    Object.entries(basicInfo).forEach(([label, value]) => {
      const p = document.createElement("div");
      p.className = "flex items-start gap-2";
      p.innerHTML = `
      <span class="font-semibold text-slate-600 min-w-[80px]">${label}:</span>
      <span class="text-slate-800 break-all flex-1">${value || "NULL"}</span>
    `;
      basicList.appendChild(p);
    });
  }
  const timeList = document.getElementById("mobile-task-details-time-list");
  if (timeList) {
    timeList.innerHTML = "";
    const timeInfo = {
      开始时间: currentRunData.start_time,
      结束时间: currentRunData.end_time,
      上传时间: currentRunData.upload_time,
    };
    Object.entries(timeInfo).forEach(([label, value]) => {
      const p = document.createElement("div");
      p.className = "flex items-start gap-2";
      p.innerHTML = `
      <span class="font-semibold text-slate-600 min-w-[80px]">${label}:</span>
      <span class="text-slate-800 break-all flex-1">${value || "NULL"}</span>
    `;
      timeList.appendChild(p);
    });
  }
  const pointsList = document.getElementById("mobile-task-details-points-list");
  if (pointsList) {
    pointsList.innerHTML = "";
    const targetPoints = currentRunData.target_points || [];
    const pointNames = (currentRunData.target_point_names || "").split("|");
    if (targetPoints.length > 0) {
      targetPoints.forEach((point, index) => {
        const name = pointNames[index] || `打卡点${index + 1}`;
        const pointCard = document.createElement("div");
        pointCard.className =
          "bg-white border border-purple-200 rounded-lg p-3 space-y-1";
        pointCard.innerHTML = `
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center justify-center w-6 h-6 bg-purple-500 text-white rounded-full text-xs font-bold">${
            index + 1
          }</span>
          <span class="font-medium text-slate-800">${name}</span>
        </div>
        <div class="text-xs text-slate-500 pl-8">
          坐标: ${point[0].toFixed(5)}, ${point[1].toFixed(5)}
        </div>
      `;
        pointsList.appendChild(pointCard);
      });
    } else {
      pointsList.innerHTML =
        '<p class="text-slate-400 text-center py-4 text-sm">该任务暂无打卡点数据</p>';
    }
  }
  const historyList = document.getElementById(
    "mobile-task-details-history-list",
  );
  if (historyList) {
    historyList.innerHTML = "";
    if (currentRunData.history && currentRunData.history.length > 0) {
      currentRunData.history.forEach((record, index) => {
        const p = document.createElement("div");
        p.className =
          "flex items-start gap-2 pb-2 border-b border-amber-200 last:border-0";
        p.innerHTML = `
        <span class="font-semibold text-slate-600">${index + 1}.</span>
        <span class="text-slate-800 break-all flex-1">${
          record.time || "NULL"
        } - ${record.status || "未知状态"}</span>
      `;
        historyList.appendChild(p);
      });
    } else {
      historyList.innerHTML =
        '<p class="text-slate-400 text-center py-4 text-sm">暂无历史记录</p>';
    }
  }
  showModalAlert("任务详情加载成功", "成功");
}
function destroyMobileSingleMap() {
  try {
    if (map) {
      map.destroy();
      map = null;
      console.log("[移动端] 单账号地图已销毁");
    }
    destroyProviderMapInstance("mobile-map-container");
    window.mobile_map_panel_initialize_mark = false;
    const container = document.getElementById("mobile-map-container");
    if (container) container.innerHTML = "";
  } catch (e) {
    console.warn("[移动端] 销毁单账号地图失败:", e);
  }
}
function destroyMobileMultiMap() {
  try {
    if (multiAccountMap) {
      multiAccountMap.destroy();
      multiAccountMap = null;
      console.log("[移动端] 多账号地图已销毁");
    }
    destroyProviderMapInstance("mobile-multi-map-container");
    window.mobile_multi_map_panel_initialize_mark = false;
    const container = document.getElementById("mobile-multi-map-container");
    if (container) container.innerHTML = "";
  } catch (e) {
    console.warn("[移动端] 销毁多账号地图失败:", e);
  }
}
async function initMobileMap(
  containerId,
  isMultiAccount = false,
  retryCount = 0,
) {
  const MAX_RETRIES = 3;
  const RETRY_DELAY = 1000;
  const container = document.getElementById(containerId);
  if (!container) {
    logMessage_Warning(`[移动端地图] 容器 ${containerId} 不存在`);
    if (retryCount < MAX_RETRIES) {
      logMessage_Info(
        `[移动端地图] 将在 ${RETRY_DELAY}ms 后重试 (${
          retryCount + 1
        }/${MAX_RETRIES})`,
      );
      setTimeout(() => {
        initMobileMap(containerId, isMultiAccount, retryCount + 1);
      }, RETRY_DELAY);
    }
    return false;
  }
  const containerStyle = window.getComputedStyle(container);
  const containerWidth = container.offsetWidth;
  const containerHeight = container.offsetHeight;

  if (
    containerWidth === 0 ||
    containerHeight === 0 ||
    containerStyle.display === "none"
  ) {
    logMessage_Warning(
      `[移动端地图] 容器 ${containerId} 不可见或尺寸为0 (${containerWidth}x${containerHeight})`,
    );
    if (retryCount < MAX_RETRIES) {
      logMessage_Info(
        `[移动端地图] 将在 ${RETRY_DELAY}ms 后重试 (${
          retryCount + 1
        }/${MAX_RETRIES})`,
      );
      setTimeout(() => {
        initMobileMap(containerId, isMultiAccount, retryCount + 1);
      }, RETRY_DELAY);
    }
    return false;
  }
  if (getActiveMapProvider() !== "amap") {
    try {
      const isReady = await ensureActiveMapProviderRuntimeIfNeeded("移动端地图初始化");
      if (isReady) {
        initProviderMap(containerId, isMultiAccount);
        logMessage_Info(
          `[移动端地图] 当前提供方为${getMapProviderDisplayName()}，已使用对应前端地图初始化`,
        );
      }
    } catch (e) {
      logMessage_Error("[移动端地图] 地图供应商运行时加载失败:", e);
    }
    return true;
  }
  if (typeof AMapInstance === "undefined") {
    logMessage_Error("[移动端地图] 高德地图API未加载");
    container.innerHTML = `
    <div class="absolute inset-0 flex items-center justify-center text-slate-400">
      <div class="text-center">
        <svg class="w-12 h-12 mx-auto mb-2 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p class="text-sm">地图加载失败</p>
        <p class="text-xs mt-1">高德地图API未加载</p>
      </div>
    </div>
  `;
    if (retryCount < MAX_RETRIES) {
      logMessage_Info(
        `[移动端地图] 将在 ${RETRY_DELAY}ms 后重试加载 (${
          retryCount + 1
        }/${MAX_RETRIES})`,
      );
      setTimeout(() => {
        initMobileMap(containerId, isMultiAccount, retryCount + 1);
      }, RETRY_DELAY);
    }
    return false;
  }
  container.innerHTML = `
  <div class="absolute inset-0 flex items-center justify-center text-slate-400">
    <div class="text-center">
      <svg class="w-12 h-12 mx-auto mb-2 text-blue-300 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      <p class="text-sm">地图初始化中...</p>
    </div>
  </div>
`;
  if (isMultiAccount) {
    if (multiAccountMap && multiAccountMap.getZoom) {
      const currentContainer = multiAccountMap.getContainer();
      if (currentContainer && currentContainer.id === containerId) {
        logMessage_Info(
          "[移动端地图] 多账号地图已初始化且容器匹配，执行Resize刷新",
        );
        container.innerHTML = "";
        setTimeout(() => {
          multiAccountMap.resize();
        }, 200);
        return true;
      } else {
        logMessage_Info(
          `[移动端地图] 多账号地图容器不匹配 (旧: ${currentContainer?.id}, 新: ${containerId})，正在销毁旧实例...`,
        );
        try {
          multiAccountMap.destroy();
        } catch (e) {
          console.warn("销毁多账号地图失败:", e);
        }
        multiAccountMap = null;
        multiAccountMarkers = {};
      }
    }
    logMessage_Info(`[移动端地图] 初始化多账号地图容器: ${containerId}`);
    try {
      multiAccountMap = new AMapInstance.Map(containerId, {
        zoom: 15,
        center: [113.390342, 22.527403],
        mapStyle: "amap://styles/normal",
      });
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("地图加载超时"));
        }, 5000);

        multiAccountMap.on("complete", () => {
          clearTimeout(timeout);
          resolve();
        });
      });
      const ctrlBar = new AMapInstance.ControlBar({
        position: { top: "10px", right: "10px" },
      });
      multiAccountMap.addControl(ctrlBar);
      try {
        const buildings = new AMapInstance.BuildingLayer();
        buildings.setMap(multiAccountMap);
      } catch (e) {
        logMessage_Warning("[移动端地图] 3D建筑图层不可用:", e);
      }

      logMessage_Info("[移动端地图] 多账号地图初始化成功");
      return true;
    } catch (error) {
      logMessage_Error("[移动端地图] 多账号地图初始化失败:", error);
      container.innerHTML = `
      <div class="absolute inset-0 flex items-center justify-center text-slate-400">
        <div class="text-center">
          <svg class="w-12 h-12 mx-auto mb-2 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p class="text-sm">地图初始化失败</p>
          <p class="text-xs mt-1">${error.message || "未知错误"}</p>
        </div>
      </div>
    `;
      if (retryCount < MAX_RETRIES) {
        logMessage_Info(
          `[移动端地图] 将在 ${RETRY_DELAY}ms 后重试 (${
            retryCount + 1
          }/${MAX_RETRIES})`,
        );
        setTimeout(() => {
          initMobileMap(containerId, isMultiAccount, retryCount + 1);
        }, RETRY_DELAY);
      }
      return false;
    }
  } else {
    if (map && map.getZoom) {
      const currentContainer = map.getContainer();
      if (currentContainer && currentContainer.id === containerId) {
        logMessage_Info(
          "[移动端地图] 单账号地图已初始化且容器匹配，执行Resize刷新",
        );
        container.innerHTML = "";
        setTimeout(() => {
          map.resize();
          if (typeof drawOnMap === "function") {
          }
        }, 200);
        return true;
      } else {
        logMessage_Info(
          `[移动端地图] 单账号地图容器不匹配 (旧: ${currentContainer?.id}, 新: ${containerId})，正在销毁旧实例...`,
        );
        try {
          if (runnerMarker) runnerMarker = null;
          map.destroy();
        } catch (e) {
          console.warn("销毁单账号地图失败:", e);
        }
        map = null;
        markers = [];
        polylines = {
          recommended: [],
          draft: null,
          run: null,
          history: null,
        };
      }
    }

    logMessage_Info(`[移动端地图] 初始化单账号地图容器: ${containerId}`);

    try {
      if (runnerMarker) {
        runnerMarker = null;
        logMessage_Info(
          "[移动端地图] 已清除旧的runner marker，准备为新地图创建",
        );
      }
      map = new AMapInstance.Map(containerId, {
        zoom: 15,
        center: [113.390342, 22.527403],
        mapStyle: "amap://styles/normal",
      });
      await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("地图加载超时"));
        }, 5000);
        map.on("complete", () => {
          clearTimeout(timeout);
          resolve();
        });
      });
      const ctrlBar = new AMapInstance.ControlBar({
        position: { top: "10px", right: "10px" },
      });
      map.addControl(ctrlBar);
      try {
        const buildings = new AMapInstance.BuildingLayer();
        buildings.setMap(map);
      } catch (e) {
        logMessage_Warning("[移动端地图] 3D建筑图层不可用:", e);
      }
      logMessage_Info("[移动端地图] 单账号地图初始化成功");
      return true;
    } catch (error) {
      logMessage_Error("[移动端地图] 单账号地图初始化失败:", error);
      container.innerHTML = `
      <div class="absolute inset-0 flex items-center justify-center text-slate-400">
        <div class="text-center">
          <svg class="w-12 h-12 mx-auto mb-2 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p class="text-sm">地图初始化失败</p>
          <p class="text-xs mt-1">${error.message || "未知错误"}</p>
        </div>
      </div>
    `;
      if (retryCount < MAX_RETRIES) {
        logMessage_Info(
          `[移动端地图] 将在 ${RETRY_DELAY}ms 后重试 (${
            retryCount + 1
          }/${MAX_RETRIES})`,
        );
        setTimeout(() => {
          initMobileMap(containerId, isMultiAccount, retryCount + 1);
        }, RETRY_DELAY);
      }
      return false;
    }
  }
}
async function loadMobileTaskHistoryPanel() {
  const listContainer = document.getElementById("mobile-task-history-list");
  const infoDiv = document.getElementById("mobile-history-task-info");

  if (!listContainer) return;
  if (selectedTaskIndex === -1 || !currentRunData || !currentRunData.run_name) {
    listContainer.innerHTML =
      '<p class="text-slate-400 text-center py-8 text-sm">请先在任务列表中选择一个任务</p>';
    if (infoDiv) infoDiv.textContent = "未选择任务";
    showModalAlert("请先在任务列表中选择一个任务", "警告");
    return;
  }
  if (infoDiv) infoDiv.textContent = `任务: ${currentRunData.run_name}`;
  showModalAlert("正在加载历史记录，请稍候...", "提示");
  listContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';
  try {
    const result = await callPythonAPI("get_task_history", selectedTaskIndex);
    if (result.success && result.history && result.history.length > 0) {
      listContainer.innerHTML = "";
      result.history.forEach((rec, idx) => {
        const item = document.createElement("div");
        item.className =
          "bg-white rounded-lg p-3 border border-amber-100 shadow-sm mb-2";
        item.innerHTML = `
        <div class="flex justify-between items-center mb-1">
          <span class="text-xs font-bold text-slate-600">#${idx + 1}</span>
          <span class="text-xs text-slate-400">${rec.time}</span>
        </div>
        <div class="flex justify-between items-center">
          <div>
            <p class="text-xs text-slate-500">距离</p>
            <p class="text-sm font-bold text-emerald-600">${rec.len}</p>
          </div>
          <div>
            <p class="text-xs text-slate-500">用时</p>
            <p class="text-sm font-bold text-sky-600">${rec.used_time}</p>
          </div>
          <div>
            <p class="text-xs text-slate-500">配速</p>
            <p class="text-sm font-bold text-purple-600">${rec.speed}</p>
          </div>
        </div>
        <button class="w-full mt-2 py-1 text-xs bg-slate-50 text-slate-600 rounded border border-slate-200 hover:bg-slate-100" 
          onclick="showHistoricalTrack(${escapeInlineJsArg(rec.trid)})">
          查看轨迹
        </button>
      `;
        listContainer.appendChild(item);
      });
    } else {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-sm">暂无历史记录</p>';
    }
    showModalAlert("历史记录加载完成", "成功");
  } catch (e) {
    console.error("加载历史记录失败:", e);
    showModalAlert(`加载历史记录失败: ${e.message}`, "错误");
    listContainer.innerHTML = `<p class="text-red-500 text-center py-8 text-sm">加载失败: ${e.message}</p>`;
  }
}

/**
 * 打开统一的移动端管理面板
 * 该函数用于统一处理单账号和多账号模式下的管理面板打开逻辑
 *
 * @description
 *   - 单账号模式('single')：复用 mobile-admin-panel-unified，主题设置写入 params
 *   - 多账号模式('multi')：使用 mobile-admin-panel-unified，主题设置写入 multi_global_params
 *
 * @param {string} mode - 'single' 或 'multi'，区分单账号和多账号模式
 */
function openMobileAdminPanelUnified(mode) {
  // 【第一步】记录日志，便于调试
  console.log(`[移动端管理面板] 打开统一面板，模式: ${mode}`);
  resetAdminUsersSearchFilters();

  // 【第二步】保存当前模式到全局变量
  window.mobileAdminPanelMode = mode;

  // 【第三步】更新面板状态显示
  const statusEl = document.getElementById("mobile-admin-panel-unified-status");
  if (statusEl) {
    statusEl.textContent = mode === "single" ? "单账号管理" : "多账号管理";
  }

  // 【第四步】调用对应模式的面板切换逻辑
  // [修正] switchMobileSinglePanel/switchMobilePanel 现在会正确移除 'hidden' 类
  if (mode === "single") {
    switchMobileSinglePanel("mobile-admin-panel-unified");
  } else {
    switchMobilePanel("mobile-admin-panel-unified", "multi");
  }

  // 【第五步】初始化管理面板
  if (typeof initMobileAdminPanel === "function") {
    // 稍微增加延时，确保 DOM 类名切换导致的重绘已完成
    setTimeout(() => {
      initMobileAdminPanel("mobile-admin-panel-unified");
    }, 50);
  }
}

function switchMobileSinglePanel(panelId, showalert = true) {
  // 单账号模式面板数组，添加 mobile-admin-panel-unified 以支持复用多账号管理面板
  const singleModePanels = [
    "mobile-control-panel",
    "mobile-map-panel",
    "mobile-task-panel",
    "mobile-task-details-panel",
    "mobile-notification-panel",
    "mobile-log-panel",
    "mobile-checkpoints-panel",
    "mobile-attendance-panel",
    "mobile-admin-panel",
    "mobile-admin-panel-unified", // 统一管理面板（单账号模式复用）
    "mobile-settings-panel",
    "mobile-profile-panel",
    "mobile-task-history-panel",
  ];
  // [修正] switchMobileSinglePanel 专用于单账号模式，无需判断 mode，直接使用 singleModePanels
  const panelList = singleModePanels;
  panelList.forEach((id) => {
    const panel = document.getElementById(id);
    if (panel) {
      panel.style.display = "none";
      // [修正] 显式添加 hidden 类
      panel.classList.add("hidden");
    }
  });
  const targetPanel = document.getElementById(panelId);
  if (targetPanel) {
    targetPanel.style.display = "";
    // [修正] 显式移除 hidden 类
    targetPanel.classList.remove("hidden");

    if (panelId === "mobile-control-panel") {
      logMessage_Info("[移动端单账号] 激活控制面板");
      if (!window.mobile_map_panel_initialize_mark) {
        switchMobileSinglePanel("mobile-map-panel");
        logMessage_Info("[移动端单账号] 首次激活控制面板，初始化地图...");
        setTimeout(function () {
          window.mobile_map_panel_initialize_mark = true;
          initMobileMap("mobile-map-container", false);
        }, 200);
        setTimeout(function () {
          switchMobileSinglePanel("mobile-control-panel");
        }, 400);
        logMessage_Info("[移动端单账号] 地图初始化完成，返回控制面板");
      }
    }
    if (panelId === "mobile-settings-panel") {
      logMessage_Info("[移动端单账号] 激活设置面板，开始加载配置...");
      const mobileParamsContainer = document.getElementById(
        "mobile-params-container",
      );
      if (
        mobileParamsContainer &&
        typeof pythonParams !== "undefined" &&
        typeof updateParamInputs === "function"
      ) {
        updateParamInputs(mobileParamsContainer, "mobile-param", pythonParams);
        logMessage_Info("[移动端单账号] 设置面板配置已自动加载");
      } else {
        logMessage_Warning("[移动端单账号] 无法加载配置：容器或函数未定义");
      }
      if (typeof refreshMobileSettings === "function") {
        refreshMobileSettings();
        logMessage_Info("[移动端单账号] 设置面板已自动刷新");
      } else {
        logMessage_Warning("[移动端单账号] refreshMobileSettings函数未定义");
      }
    }
    if (panelId === "mobile-map-panel") {
      logMessage_Info("[移动端单账号] 激活地图面板，初始化地图...");
      if (
        currentRunData &&
        currentRunData.run_coords &&
        currentRunData.run_coords.length > 0
      ) {
        logMessage_Info("[移动端单账号] 开始绘制任务路径和打卡点...");
        if (typeof drawOnMap === "function") {
          drawOnMap();

          drawOnMap();
          logMessage_Info("[移动端单账号] 任务路径和打卡点已绘制");
          ensureRunnerMarker();
        }
      } else {
        logMessage_Info("[移动端单账号] 无任务数据，跳过绘制");
      }
    }
    if (panelId === "mobile-attendance-panel") {
      logMessage_Info("[移动端单账号] 激活签到面板，开始加载配置...");
      setTimeout(() => {
        const attendanceEnabled = document.getElementById(
          "mobile-attendance-enabled",
        );
        if (attendanceEnabled && typeof pythonParams !== "undefined") {
          attendanceEnabled.checked = pythonParams.attendance_enabled !== false;
        }
        const attendanceTime = document.getElementById(
          "mobile-attendance-time",
        );
        if (attendanceTime && typeof pythonParams !== "undefined") {
          attendanceTime.value = pythonParams.attendance_time || "08:00";
        }
        const attendanceDelayMin = document.getElementById(
          "mobile-attendance-delay-min",
        );
        const attendanceDelayMax = document.getElementById(
          "mobile-attendance-delay-max",
        );
        if (
          attendanceDelayMin &&
          attendanceDelayMax &&
          typeof pythonParams !== "undefined"
        ) {
          attendanceDelayMin.value = pythonParams.attendance_delay_min || 0;
          attendanceDelayMax.value = pythonParams.attendance_delay_max || 300;
        }
        const autoRefreshInterval = document.getElementById(
          "mobile-param-auto_attendance_refresh_s",
        );
        if (autoRefreshInterval && typeof pythonParams !== "undefined") {
          autoRefreshInterval.value =
            pythonParams.auto_attendance_refresh_s || 15;
          logMessage_Info(
            "[移动端单账号] 自动刷新间隔已加载:",
            autoRefreshInterval.value,
            "秒",
          );
        }
        const userRadius = document.getElementById(
          "mobile-param-attendance_user_radius_m",
        );
        if (userRadius && typeof pythonParams !== "undefined") {
          userRadius.value = pythonParams.attendance_user_radius_m || 0;
          logMessage_Info(
            "[移动端单账号] 签到随机半径已加载:",
            userRadius.value,
            "米",
          );
        }
        const stopAfterSuccess = document.getElementById(
          "mobile-param-auto_attendance_stop_after_success",
        );
        if (stopAfterSuccess && typeof pythonParams !== "undefined") {
          stopAfterSuccess.checked =
            pythonParams.auto_attendance_stop_after_success !== false;
        }
        const successLimit = document.getElementById(
          "mobile-param-auto_attendance_success_limit",
        );
        if (successLimit && typeof pythonParams !== "undefined") {
          successLimit.value = pythonParams.auto_attendance_success_limit || 1;
        }
        logMessage_Info("[移动端单账号] 签到面板配置已自动加载");
        refreshNotificationsUI(true, true);
      }, 50);
    }
    if (panelId === "mobile-task-details-panel") {
      logMessage_Info("[移动端单账号] 激活任务详情面板，开始加载任务详情...");
      setTimeout(() => {
        if (typeof loadMobileTaskDetails === "function") {
          loadMobileTaskDetails();
          logMessage_Info("[移动端单账号] 任务详情已自动加载");
        } else {
          logMessage_Warning("[移动端单账号] loadMobileTaskDetails函数未定义");
        }
      }, 50);
    }
    if (panelId === "mobile-profile-panel") {
      logMessage_Info("[移动端单账号] 激活用户详情面板，开始加载用户详情...");
      setTimeout(() => {
        if (typeof loadMobileUserDetails === "function") {
          loadMobileUserDetails();
          logMessage_Info("[移动端单账号] 用户详情已自动加载");
        } else {
          logMessage_Warning("[移动端单账号] loadMobileUserDetails函数未定义");
        }
      }, 50);
    }

    // 【管理面板】激活时初始化
    // 当用户切换到管理面板时，自动初始化管理面板的标签页和内容
    // 原因：管理面板包含多个标签页（用户管理、角色管理等），需要根据用户权限动态创建
    if (panelId === "mobile-admin-panel") {
      logMessage_Info("[移动端单账号] 激活管理面板，开始初始化...");
      // 调用 initMobileAdminPanel 函数初始化管理面板
      // 参数 'mobile-admin-panel' 是前缀，用于区分单账号和多账号的管理面板
      if (typeof initMobileAdminPanel === "function") {
        initMobileAdminPanel("mobile-admin-panel");
      } else {
        logMessage_Warning("[移动端单账号] initMobileAdminPanel函数未定义");
      }
    }

    // 统一管理面板（mobile-admin-panel-unified）在单账号模式下的激活处理
    // 单账号模式复用多账号管理面板，但需要设置正确的模式标识
    // [修正] initMobileAdminPanel 由 openMobileAdminPanelUnified 通过 setTimeout 统一调用，
    //        此处不再重复调用，避免产生竞态条件导致面板隐藏失败
    if (panelId === "mobile-admin-panel-unified") {
      logMessage_Info("[移动端单账号] 激活统一管理面板（复用多账号面板）");
      // 设置当前模式为单账号，供主题保存等功能判断
      window.mobileAdminPanelMode = "single";
      // 更新面板状态显示为单账号管理
      const statusEl = document.getElementById(
        "mobile-admin-panel-unified-status",
      );
      if (statusEl) {
        statusEl.textContent = "单账号管理";
      }
    }

    // 【通知面板】激活时自动刷新
    if (panelId === "mobile-notification-panel") {
      logMessage_Info("[移动端单账号] 激活通知面板，自动刷新...");
      setTimeout(() => {
        mobileRefreshNotifications();
      }, 50);
    }

    if (panelId === "mobile-task-history-panel") {
      logMessage_Info("[移动端单账号] 激活历史记录面板...");
      setTimeout(() => {
        loadMobileTaskHistoryPanel();
      }, 50);
    }

    // 【任务列表面板】激活时自动刷新任务列表
    if (panelId === "mobile-task-panel") {
      logMessage_Info("[移动端单账号] 激活任务列表面板，自动刷新任务...");
      setTimeout(() => {
        if (typeof mobileRefreshTasks === "function") {
          mobileRefreshTasks(showalert);
          logMessage_Info("[移动端单账号] 任务列表已自动刷新");
        } else {
          logMessage_Warning("[移动端单账号] mobileRefreshTasks函数未定义");
        }
      }, 50);
    }

    // 【打卡点面板】激活时自动渲染打卡点列表
    if (panelId === "mobile-checkpoints-panel") {
      logMessage_Info("[移动端单账号] 激活打卡点面板，自动渲染打卡点列表...");
      setTimeout(() => {
        if (typeof renderMobileCheckpointsList === "function") {
          renderMobileCheckpointsList();
          logMessage_Info("[移动端单账号] 打卡点列表已自动渲染");
        } else {
          logMessage_Warning(
            "[移动端单账号] renderMobileCheckpointsList函数未定义",
          );
        }
      }, 50);
    }

    // 第四步：滚动到页面顶部
    // 切换面板后，自动滚动到页面顶部，确保用户看到面板的完整内容
    // 使用平滑滚动效果（smooth），提供更好的用户体验
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    // 如果找不到目标面板，输出警告信息
    // 这可能是因为传入了错误的panelId，或者HTML结构发生了变化
    logMessage_Warning(`[移动端单账号] 找不到ID为 ${panelId} 的面板`);
  }

  // 第五步：更新导航栏和侧边栏的激活状态
  // 当面板切换后，需要更新底部导航栏和侧边栏菜单的视觉状态
  // 让当前激活的菜单项高亮显示，其他菜单项恢复默认样式
  updateMobileNavActiveState(panelId); // 更新底部导航栏的激活状态
  updateMobileSidebarActive(panelId); // 更新侧边栏菜单的激活状态
}

/**
 * 【移动端多账号面板切换】专用函数
 * 重命名自 switchMobilePanel，现在仅用于多账号模式
 * 单账号模式使用 switchMobileSinglePanel
 */
function switchMobileMulitPanel(panelId, mode = "multi") {
  // 根据模式定义面板列表
  const singleModePanels = [
    "mobile-control-panel",
    "mobile-map-panel",
    "mobile-task-panel",
    "mobile-task-details-panel", // 【问题11修复】新增：任务详情面板
    "mobile-notification-panel",
    "mobile-log-panel", // 新增：日志面板
    "mobile-checkpoints-panel", // 【问题6修复】新增：打卡点面板
    "mobile-attendance-panel",
    "mobile-admin-panel", // 【问题15&18修复】新增：管理面板
    "mobile-settings-panel",
    "mobile-profile-panel", // 新增：我的资料面板
  ];

  const multiModePanels = [
    "mobile-multi-account-panel",
    "mobile-multi-map-panel",
    "mobile-multi-control-panel",
    "mobile-admin-panel-unified",
    "mobile-multi-settings-panel",
    "mobile-multi-log-panel",
  ];
  const panelList = mode === "single" ? singleModePanels : multiModePanels;
  panelList.forEach((id) => {
    const panel = document.getElementById(id);
    if (panel) {
      panel.style.display = "none";
      // [修正] 显式添加 hidden 类，确保面板被隐藏
      panel.classList.add("hidden");
    }
  });
  const targetPanel = document.getElementById(panelId);
  if (targetPanel) {
    targetPanel.style.display = "";
    // [修正] 显式移除 hidden 类，确保面板显示 (修复 mobile-admin-panel-unified 无法显示的问题)
    targetPanel.classList.remove("hidden");

    if (panelId === "mobile-multi-control-panel") {
      logMessage_Info("[移动端多账号] 激活多账号控制面板");
      if (!window.mobile_multi_map_panel_initialize_mark) {
        switchMobileMulitPanel("mobile-multi-map-panel");
        logMessage_Info("[移动端多账号] 首次激活多账号控制面板，初始化地图...");
        setTimeout(function () {
          window.mobile_multi_map_panel_initialize_mark = true;
          initMobileMap("mobile-multi-map-container", true);
        }, 200);
        setTimeout(function () {
          switchMobileMulitPanel("mobile-multi-control-panel");
        }, 400);
        logMessage_Info("[移动端多账号] 多账号地图初始化完成，返回控制面板");
      }
    }
    if (panelId === "mobile-settings-panel") {
      console.log("[移动端] 激活设置面板，开始加载配置...");
      const mobileParamsContainer = document.getElementById(
        "mobile-params-container",
      );
      if (
        mobileParamsContainer &&
        typeof pythonParams !== "undefined" &&
        typeof updateParamInputs === "function"
      ) {
        updateParamInputs(mobileParamsContainer, "mobile-param", pythonParams);
        console.log("[移动端] 设置面板配置已自动加载");
      } else {
        console.warn("[移动端] 无法加载配置：容器或函数未定义");
      }
    }
    if (panelId === "mobile-multi-settings-panel") {
      console.log("[移动端] 激活多账号全局设置面板，开始加载配置...");
      // 获取全局参数容器元素
      const mobileMultiParamsContainer = document.getElementById(
        "mobile-multi-global-params-container",
      );
      // 检查必要的容器和函数是否存在
      if (
        mobileMultiParamsContainer &&
        typeof pythonParams !== "undefined" &&
        typeof updateParamInputs === "function"
      ) {
        // 使用 updateParamInputs 函数更新全局参数容器中的输入值
        updateParamInputs(
          mobileMultiParamsContainer,
          "mobile-multi-param",
          pythonParams,
        );
        console.log("[移动端] 多账号全局设置面板配置已自动加载");
      }

      /**
       * 【自动签到设置区域初始化】
       * 为自动签到相关的输入元素填充当前配置值
       * 这些元素的 ID 使用 mobile-multi- 前缀，需要单独初始化
       */
      if (typeof pythonParams !== "undefined") {
        // 初始化自动签到开关 (checkbox)
        const autoAttendanceEnabled = document.getElementById(
          "mobile-multi-auto_attendance_enabled",
        );
        if (autoAttendanceEnabled) {
          // 设置 checked 状态为 pythonParams 中的值，默认为 false
          autoAttendanceEnabled.checked =
            pythonParams["auto_attendance_enabled"] || false;
        }

        // 初始化刷新间隔输入框 (number)
        const autoAttendanceRefresh = document.getElementById(
          "mobile-multi-auto_attendance_refresh_s",
        );
        if (autoAttendanceRefresh) {
          // 设置值为 pythonParams 中的值，默认为空字符串
          autoAttendanceRefresh.value =
            pythonParams["auto_attendance_refresh_s"] || "";
        }

        // 初始化随机半径输入框 (number)
        const attendanceRadius = document.getElementById(
          "mobile-multi-attendance_user_radius_m",
        );
        if (attendanceRadius) {
          // 设置值为 pythonParams 中的值，默认为空字符串
          attendanceRadius.value =
            pythonParams["attendance_user_radius_m"] || "";
        }

        console.log("[移动端] 自动签到设置已初始化");
      }
    }
    if (panelId === "mobile-multi-map-panel") {
      console.log("[移动端] 激活多账号地图面板，初始化地图...");
      setTimeout(() => {}, 100);
    }
    if (panelId === "mobile-admin-panel") {
      console.log("[移动端] 激活管理面板，开始初始化...");
      if (typeof initMobileAdminPanel === "function") {
        initMobileAdminPanel("mobile-admin-panel");
      } else {
        console.warn("[移动端] initMobileAdminPanel函数未定义");
      }
    }
    if (panelId === "mobile-admin-panel-unified") {
      console.log("[移动端] 激活多账号管理面板");
      // 设置当前模式为多账号，供主题保存等功能判断
      // [修正] initMobileAdminPanel 由 openMobileAdminPanelUnified 通过 setTimeout 统一调用，
      //        此处不再重复调用，避免产生竞态条件导致面板隐藏失败
      window.mobileAdminPanelMode = "multi";
      // 更新面板状态显示为多账号管理
      const statusEl = document.getElementById(
        "mobile-admin-panel-unified-status",
      );
      if (statusEl) {
        statusEl.textContent = "多账号管理";
      }
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    console.warn(`找不到ID为 ${panelId} 的面板`);
  }
  updateMobileNavActiveState(panelId);
  updateMobileSidebarActive(panelId);
}
function switchMobilePanel(panelId, mode = "multi") {
  return switchMobileMulitPanel(panelId, mode);
}
function scrollToMobileSection(sectionId) {
  const section = document.getElementById(sectionId);
  if (section) {
    section.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
    updateMobileNavActiveState(sectionId);
  } else {
    console.warn(`找不到ID为 ${sectionId} 的面板`);
  }
}
function updateMobileNavActiveState(activeSectionId) {
  const navButtons = document.querySelectorAll(".mobile-nav-btn");
  const sectionNavMap = {
    "mobile-control-panel": "control",
    "mobile-map-panel": "map",
    "mobile-task-panel": "task",
    "mobile-notification-panel": "notifications",
    "mobile-attendance-panel": "attendance",
    "mobile-settings-panel": "settings",
    "mobile-admin-panel": "admin",
    "mobile-admin-panel-unified": "admin", // 统一管理面板的导航映射
    "mobile-multi-account-panel": "accounts",
    "mobile-multi-control-panel": "control",
    "mobile-multi-map-panel": "map",
    "mobile-multi-settings-panel": "settings",
  };
  const targetNav = sectionNavMap[activeSectionId];
  navButtons.forEach((btn) => {
    const navType = btn.getAttribute("data-nav");
    if (navType === targetNav) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });
}
function updateMobileSidebarActive(panelId) {
  const panelToMenuText = {
    "mobile-control-panel": "控制",
    "mobile-map-panel": "地图",
    "mobile-task-panel": "任务",
    "mobile-notification-panel": "通知",
    "mobile-log-panel": "日志",
    "mobile-checkpoints-panel": "打卡点",
    "mobile-attendance-panel": "签到",
    "mobile-admin-panel": "管理",
    "mobile-settings-panel": "设置",
    "mobile-profile-panel": "我的",
    "mobile-task-details-panel": "任务详情",
    "mobile-task-history-panel": "历史记录",
    "mobile-multi-control-panel": "控制",
    "mobile-multi-map-panel": "地图",
    "mobile-multi-account-panel": "账号",
    "mobile-admin-panel-unified": "管理",
    "mobile-multi-settings-panel": "设置",
    "mobile-multi-log-panel": "日志",
  };
  const targetMenuText = panelToMenuText[panelId];
  if (!targetMenuText) {
    console.log(`[侧边栏active] 面板 ${panelId} 没有对应的侧边栏菜单项`);
    const sidebarItems = document.querySelectorAll(".mobile-sidebar-item");
    sidebarItems.forEach((item) => {
      item.classList.remove("mobile-sidebar-active");
      item.style.backgroundColor = "";
      item.style.color = "";
      item.style.fontWeight = "";
    });
    return;
  }
  // 判断应该更新哪个侧边栏的高亮状态
  // 原逻辑仅通过 panelId.includes("multi") 判断，但 mobile-admin-panel-unified 不包含 "multi"
  // 因此需要额外处理：当面板是 mobile-admin-panel-unified 时，根据 window.mobileAdminPanelMode 判断
  let targetSidebar;
  // 判断是否为多账号模式：
  // 1. panelId 包含 "multi" 字符串（如 mobile-multi-control-panel）
  // 2. 或者 panelId 是 mobile-admin-panel-unified 且当前模式为 'multi'
  const isMultiAccountMode =
    panelId.includes("multi") ||
    (panelId === "mobile-admin-panel-unified" &&
      window.mobileAdminPanelMode === "multi");
  if (isMultiAccountMode) {
    // 多账号模式：选择多账号侧边栏
    targetSidebar = document.getElementById("mobile-sidebar-multi-account");
  } else {
    // 单账号模式：选择单账号侧边栏
    targetSidebar = document.getElementById("mobile-sidebar-single-account");
  }
  if (!targetSidebar) {
    console.warn(`[侧边栏active] 找不到对应的侧边栏容器`);
    return;
  }
  const sidebarItems = targetSidebar.querySelectorAll(".mobile-sidebar-item");
  sidebarItems.forEach((item) => {
    const span = item.querySelector("span");
    if (span) {
      const menuText = span.textContent.trim();
      if (menuText === targetMenuText) {
        item.classList.add("mobile-sidebar-active");
        item.style.backgroundColor = "rgba(59, 130, 246, 0.1)";
        item.style.color = "#3b82f6";
        item.style.fontWeight = "600";
      } else {
        item.classList.remove("mobile-sidebar-active");
        item.style.backgroundColor = "";
        item.style.color = "";
        item.style.fontWeight = "";
      }
    }
  });

  console.log(
    `[侧边栏active] 已更新active状态: ${targetMenuText} (面板: ${panelId})`,
  );
}
async function openMobileAccountParams(username) {
  if (!username) return;
  const modal = document.getElementById("mobile-account-params-modal");
  const titleEl = document.getElementById("mobile-account-params-title");
  const container = document.getElementById("mobile-account-params-container");
  const saveBtn = document.getElementById("mobile-save-account-params-btn");
  if (!modal || !container) return;
  container.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';
  modal.classList.remove("hidden");

  if (titleEl) titleEl.textContent = `[${username}] 参数设置`;

  try {
    const result = await callPythonAPI("multi_get_account_params", username);
    if (!result.success) {
      showModalAlert(result.message);
      modal.classList.add("hidden");
      return;
    }
    createParamInputs(container, "mobile-acc-param", () => {}, ["主题与外观"]);
    updateParamInputs(container, "mobile-acc-param", result.params);
    if (saveBtn) {
      saveBtn.onclick = async () => {
        showModalAlert("正在保存...", "提示");
        const inputs = container.querySelectorAll("input, select");
        try {
          for (const input of inputs) {
            const key = input.dataset.key;
            if (!key) continue;
            const value =
              input.type === "checkbox" ? input.checked : input.value;
            await callPythonAPI(
              "multi_update_account_param",
              username,
              key,
              value,
            );
          }
          showModalAlert("设置已保存", "成功");
          closeMobileAccountParams();
        } catch (e) {
          showModalAlert("保存失败: " + e.message, "错误");
        }
      };
    }
  } catch (e) {
    container.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
  }
}
// ==================== 移动端地图控制函数 ====================
function mobileZoomIn() {
  zoomProviderMap("map-container", 1);
}
function mobileZoomOut() {
  zoomProviderMap("map-container", -1);
}
// function mobileFitView() {
//   if (map && markers && markers.length > 0) {
//     map.setFitView(markers, false, [50, 50, 50, 50]);
//   }
// }
function resetMobileMapView() {
  clearTaskMapAutoResetTimer();
  if (getActiveMapProvider() !== "amap") {
    fitProviderMapToLastRoute("map-container");
    return;
  }
  if (map) {
    if (markers && markers.length > 0) {
      map.setFitView(markers, false, [50, 50, 50, 50]);
      console.log("[单账号地图] 复位视角：自动适应所有标记点");
    } else {
      const defaultCenter = [116.397128, 39.916527];
      const defaultZoom = 11;
      map.setCenter(defaultCenter);
      map.setZoom(defaultZoom);
      console.log("[单账号地图] 复位视角：重置到默认位置");
    }
  } else {
    console.warn("[单账号地图] 无法复位视角：地图实例未初始化");
  }
}
function mobileMultiZoomIn() {
  zoomProviderMap("multi-map-container", 1);
}
function mobileMultiZoomOut() {
  zoomProviderMap("multi-map-container", -1);
}
function mobileMultiFitView() {
  clearTaskMapAutoResetTimer();
  if (getActiveMapProvider() !== "amap") {
    fitProviderMapToLastRoute("multi-map-container");
    return;
  }
  if (multiAccountMap) {
    const allOverlays = multiAccountMap.getAllOverlays();
    if (allOverlays && allOverlays.length > 0) {
      multiAccountMap.setFitView(allOverlays, false, [50, 50, 50, 50]);
    }
  }
}
function resetMultiMapView() {
  clearTaskMapAutoResetTimer();
  if (getActiveMapProvider() !== "amap") {
    fitProviderMapToLastRoute("multi-map-container");
    return;
  }
  if (multiAccountMap) {
    const allOverlays = multiAccountMap.getAllOverlays();
    if (allOverlays && allOverlays.length > 0) {
      multiAccountMap.setFitView(allOverlays, false, [50, 50, 50, 50]);
      console.log("[多账号地图] 复位视角：自动适应所有路线");
    } else {
      const defaultCenter = [113.390342, 22.527403];
      const defaultZoom = 11;
      multiAccountMap.setCenter(defaultCenter);
      multiAccountMap.setZoom(defaultZoom);
      console.log(
        "[多账号地图] 复位视角：重置到指定位置 [113.390342, 22.527403]",
      );
    }
  } else {
    console.warn("[多账号地图] 无法复位视角：地图实例未初始化");
  }
}
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
// ==================== 移动端专用辅助函数 ====================
function clearMobileLog() {
  const mobileLogText = document.getElementById("mobile-log-text");
  if (mobileLogText) {
    mobileLogText.value = "";
    console.log("[移动端] 日志已清空");
  }
}
function syncUAToMobile(uaText) {
  // 同步时一并更新当前会话UA，避免详情面板显示旧值
  if (!IS_OFFLINE) {
    currentSessionUA = normalizeSessionUA(uaText);
  }
  const mobileUALabel = document.getElementById("mobile-ua-label");
  if (mobileUALabel) {
    mobileUALabel.textContent = uaText || "(未加载)";
    console.log("[移动端] UA已同步:", uaText);
  }
}

function normalizeSessionUA(uaText) {
  const text = (uaText || "").toString().trim();
  if (!text) return "";
  if (text === "(未加载)" || text === "(新用户将在登录时自动生成)") return "";
  return text;
}

function getCurrentSessionUAText() {
  if (IS_OFFLINE) return "NULL";
  const pcLabelUA = normalizeSessionUA($("ua-label")?.textContent);
  const mobileLabelUA = normalizeSessionUA(
    document.getElementById("mobile-ua-label")?.textContent,
  );
  const sessionUA = normalizeSessionUA(currentSessionUA);
  return sessionUA || pcLabelUA || mobileLabelUA || "NULL";
}
// async function loadMobileCaptcha(formType) {
//   const displayId =
//     formType === "login"
//       ? "mobile-login-captcha-display"
//       : "mobile-register-captcha-display";
//   const displayElement = document.getElementById(displayId);
//   if (!displayElement) {
//     console.log(`[移动端验证码] 未找到验证码显示元素: ${displayId}`);
//     return;
//   }
//   const captchaId = captchaIds[formType];

//   if (!captchaId) {
//     displayElement.innerHTML =
//       '<span class="text-slate-400 text-xs">等待加载...</span>';
//     console.log(`[移动端验证码] captchaId尚未生成，等待PC端加载: ${formType}`);
//     return;
//   }
//   const captchaDims = captchaDimensions[formType] || {
//     width: 343,
//     height: 119,
//   };
//   // ========================================
//   // 【移动端验证码缩放】
//   // ========================================

//   const viewportWidth =
//     window.innerWidth || document.documentElement.clientWidth;
//   const padding = 80 + 40;
//   const availableWidth = viewportWidth - padding;
//   const needsScaling = availableWidth < captchaDims.width;
//   const targetWidth = needsScaling
//     ? Math.floor(availableWidth)
//     : captchaDims.width;
//   const scaleFactor = needsScaling ? targetWidth / captchaDims.width : 1;
//   const targetHeight = Math.floor(captchaDims.height * scaleFactor);

//   console.log(
//     `[移动端验证码缩放] 屏幕宽度${viewportWidth}px，可用${availableWidth}px，验证码原始${captchaDims.width}x${captchaDims.height}px，目标${targetWidth}x${targetHeight}px`
//   );
//   const timestamp = Date.now();
//   let iframeSrc = `/api/captcha/html/${captchaId}?t=${timestamp}`;
//   if (needsScaling) {
//     iframeSrc += `&width=${targetWidth}`;
//   }
//   const iframeHtml = `
//   <iframe
//     src="${iframeSrc}"
//     style="width: ${targetWidth}px; height: ${targetHeight}px; border: none; overflow: hidden; display: block; max-width: 100%;"
//     scrolling="no"
//     frameborder="0"
//     title="验证码">
//   </iframe>
// `;
//   displayElement.innerHTML = iframeHtml;

//   console.log(
//     `[移动端验证码] ${formType}表单验证码同步成功，复用ID: ${captchaId.substring(
//       0,
//       8
//     )}... (时间戳: ${timestamp})`
//   );
// }
// ==================== 注册登录和个人资料功能 ====================
let isPhoneLogin = false;
const pcLoginModeDrafts = {
  username_mode: { username: "", password: "" },
  phone_mode: { phone: "", sms_code: "", password: "" },
};

function sanitizePhoneDigits(value) {
  return String(value || "").replace(/\D/g, "").slice(0, 11);
}

function sanitizeSmsCodeDigits(value) {
  return String(value || "").replace(/\D/g, "");
}

function applyDigitSanitizer(input, sanitizer) {
  if (!input || input.dataset.digitSanitizerBound === "true") {
    return;
  }
  const sanitize = () => {
    const sanitizedValue = sanitizer(input.value);
    if (input.value !== sanitizedValue) {
      input.value = sanitizedValue;
    }
  };
  input.addEventListener("input", sanitize);
  input.addEventListener("paste", function () {
    requestAnimationFrame(sanitize);
  });
  sanitize();
  input.dataset.digitSanitizerBound = "true";
}

function bindAuthPhoneLoginInput() {
  const phoneInput = document.getElementById("auth-username");
  if (phoneInput && isPhoneLogin) {
    applyDigitSanitizer(phoneInput, sanitizePhoneDigits);
  }
}

function bindAuthSmsCodeInput() {
  const smsInput = document.getElementById("auth-sms-code");
  if (smsInput) {
    applyDigitSanitizer(smsInput, sanitizeSmsCodeDigits);
  }
}

function bindRegistrationDigitInputs() {
  const regPhoneInput = document.getElementById("auth-reg-phone");
  if (regPhoneInput) {
    applyDigitSanitizer(regPhoneInput, sanitizePhoneDigits);
  }
  const regSmsInput = document.getElementById("auth-reg-sms-code");
  if (regSmsInput) {
    applyDigitSanitizer(regSmsInput, sanitizeSmsCodeDigits);
  }
}

function savePcLoginModeDraft() {
  if (isPhoneLogin) {
    const phoneInput = document.getElementById("auth-username");
    const passwordInput = document.getElementById("auth-password");
    const smsInput = document.getElementById("auth-sms-code");
    pcLoginModeDrafts.phone_mode = {
      phone: sanitizePhoneDigits(phoneInput ? phoneInput.value : ""),
      sms_code: sanitizeSmsCodeDigits(smsInput ? smsInput.value : ""),
      password: passwordInput ? passwordInput.value : "",
    };
    return;
  }

  const usernameInput = document.getElementById("auth-username");
  const passwordInput = document.getElementById("auth-password");
  pcLoginModeDrafts.username_mode = {
    username: usernameInput ? usernameInput.value : "",
    password: passwordInput ? passwordInput.value : "",
  };
}

function clearPcLoginModeDraftFields(mode) {
  const passwordInput = document.getElementById("auth-password");
  const smsInput = document.getElementById("auth-sms-code");
  const usernameInput = document.getElementById("auth-username");

  if (mode === "phone_mode") {
    if (usernameInput) usernameInput.value = "";
    if (smsInput) smsInput.value = "";
    if (passwordInput) passwordInput.value = "";
    return;
  }

  if (usernameInput) usernameInput.value = "";
  if (passwordInput) passwordInput.value = "";
}

function restorePcLoginModeDraft(mode) {
  const draft = pcLoginModeDrafts[mode] || {};
  const hasDraft = Object.values(draft).some((value) => String(value || "") !== "");
  if (!hasDraft) {
    clearPcLoginModeDraftFields(mode);
    return;
  }

  const passwordInput = document.getElementById("auth-password");
  const smsInput = document.getElementById("auth-sms-code");
  const usernameInput = document.getElementById("auth-username");

  if (mode === "phone_mode") {
    if (usernameInput) usernameInput.value = sanitizePhoneDigits(draft.phone || "");
    if (smsInput) smsInput.value = sanitizeSmsCodeDigits(draft.sms_code || "");
    if (passwordInput) passwordInput.value = draft.password || "";
    bindAuthPhoneLoginInput();
    bindAuthSmsCodeInput();
    return;
  }

  if (usernameInput) usernameInput.value = draft.username || "";
  if (passwordInput) passwordInput.value = draft.password || "";
}

document.addEventListener("DOMContentLoaded", function () {
  const usernameBtn = document.getElementById("auth-login-username-btn");
  const phoneBtn = document.getElementById("auth-login-phone-btn");
  const authInput = document.getElementById("auth-username");
  const authLabel = document.getElementById("auth-login-label");
  const authUsernameContainer = document.getElementById(
    "auth-username-container",
  );
  if (usernameBtn && phoneBtn) {
    const getCurrentAuthInput = () =>
      document.getElementById("auth-username") || authInput;

    usernameBtn.addEventListener("click", function () {
      savePcLoginModeDraft();
      isPhoneLogin = false;
      usernameBtn.className =
        "px-4 py-2 rounded-lg bg-sky-100 text-sky-700 font-semibold text-sm";
      phoneBtn.className =
        "px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm";
      if (authLabel) authLabel.textContent = "用户名";
      if (authUsernameContainer) {
        authUsernameContainer.innerHTML = `
        <input type="text" id="auth-username" class="input-field mt-1"
               placeholder="请输入用户名" autocomplete="username">
      `;
        const newAuthInput = document.getElementById("auth-username");
        newAuthInput.removeAttribute("inputmode");
        newAuthInput.removeAttribute("maxlength");
      }
      restorePcLoginModeDraft("username_mode");
      const switchToSms = document.getElementById("auth-switch-to-sms");
      if (switchToSms) switchToSms.classList.add("hidden");
      const passwordSection = document.getElementById("auth-password-section");
      const smsSection = document.getElementById("auth-sms-section");
      if (passwordSection) passwordSection.classList.remove("hidden");
      if (smsSection) smsSection.classList.add("hidden");
    });
    phoneBtn.addEventListener("click", function () {
      savePcLoginModeDraft();
      isPhoneLogin = true;
      phoneBtn.className =
        "px-4 py-2 rounded-lg bg-sky-100 text-sky-700 font-semibold text-sm";
      usernameBtn.className =
        "px-4 py-2 rounded-lg bg-slate-100 text-slate-600 text-sm";
      if (authLabel) authLabel.textContent = "手机号";
      if (authUsernameContainer) {
        authUsernameContainer.innerHTML = `
        <div class="phone-input-wrapper mt-1">
          <span class="phone-prefix">+86 </span>
          <input type="tel" id="auth-username" class="input-field"
                 placeholder="请输入手机号" autocomplete="tel" inputmode="numeric" maxlength="11" pattern="[0-9]*" >
        </div>
      `;
      }
      restorePcLoginModeDraft("phone_mode");
      const switchToSms = document.getElementById("auth-switch-to-sms");
      if (switchToSms) switchToSms.classList.remove("hidden");
    });
  }

  const switchToSms = document.getElementById("auth-switch-to-sms");
  const switchToPassword = document.getElementById("auth-switch-to-password");
  const passwordSection = document.getElementById("auth-password-section");
  const smsSection = document.getElementById("auth-sms-section");

  if (switchToSms) {
    switchToSms.addEventListener("click", function () {
      passwordSection.classList.add("hidden");
      smsSection.classList.remove("hidden");
    });
  }

  if (switchToPassword) {
    switchToPassword.addEventListener("click", function () {
      smsSection.classList.add("hidden");
      passwordSection.classList.remove("hidden");
    });
  }
  const sendLoginCodeBtn = document.getElementById("auth-send-login-code");
  if (sendLoginCodeBtn) {
    sendLoginCodeBtn.addEventListener("click", function () {
      const phoneInput = document.getElementById("auth-username");
      const phone = sanitizePhoneDigits(phoneInput.value.trim());
      phoneInput.value = phone;

      if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
        showModalAlert("请输入正确的手机号");
        return;
      }
      openCaptchaModal({
        phone: phone,
        button: sendLoginCodeBtn,
        originalText: sendLoginCodeBtn.textContent,
        scene: "login",
      });
    });
  }
  const regUsernameInput = document.getElementById("auth-reg-username");
  if (regUsernameInput) {
    regUsernameInput.addEventListener("input", function (e) {
      const value = e.target.value;
      const noChinese = value.replace(/[一-龥]/g, "");
      if (value !== noChinese) {
        e.target.value = noChinese;
        showModalAlert("用户名不能包含中文字符", "警告");
      }
    });
  }
  const avatarInput = document.getElementById("auth-reg-avatar");
  if (avatarInput) {
    avatarInput.addEventListener("change", function (e) {
      if (typeof previewAvatarForRegistration === "function") {
        previewAvatarForRegistration(e);
      } else {
        console.error("previewAvatarForRegistration 函数尚未加载");
      }
    });
  }
  const sendCodeBtn = document.getElementById("auth-reg-send-code-btn");
  if (sendCodeBtn) {
    sendCodeBtn.addEventListener("click", async function () {
      const phoneInput = document.getElementById("auth-reg-phone");
      const phone = sanitizePhoneDigits(phoneInput.value);
      phoneInput.value = phone;
      if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
        showModalAlert("请输入正确的手机号");
        return;
      }
      openCaptchaModal({
        phone: phone,
        button: sendCodeBtn,
        originalText: sendCodeBtn.textContent,
      });
    });
  }
  // ============================================================
  // 验证码相关事件监听器
  // ============================================================
  const loginCaptchaRefreshBtn = document.getElementById(
    "auth-login-captcha-refresh",
  );
  if (loginCaptchaRefreshBtn) {
    loginCaptchaRefreshBtn.addEventListener("click", function (e) {
      e.preventDefault();
      refreshCaptcha("login");
    });
  }
  const loginCaptchaDisplay = document.getElementById(
    "auth-login-captcha-display",
  );
  if (loginCaptchaDisplay) {
    loginCaptchaDisplay.addEventListener("click", function () {
      if (loginCaptchaDisplay.dataset.behaviorCaptcha === "true") {
        return;
      }
      refreshCaptcha("login");
    });
  }
  const registerCaptchaRefreshBtn = document.getElementById(
    "auth-register-captcha-refresh",
  );
  if (registerCaptchaRefreshBtn) {
    registerCaptchaRefreshBtn.addEventListener("click", function (e) {
      e.preventDefault();
      refreshCaptcha("register");
    });
  }
  const registerCaptchaDisplay = document.getElementById(
    "auth-register-captcha-display",
  );
  if (registerCaptchaDisplay) {
    registerCaptchaDisplay.addEventListener("click", function () {
      if (registerCaptchaDisplay.dataset.behaviorCaptcha === "true") {
        return;
      }
      refreshCaptcha("register");
    });
  }
  const authLoginContainer = document.getElementById("auth-login-container");
  if (authLoginContainer && !authLoginContainer.classList.contains("hidden")) {
    setTimeout(() => {
      loadCaptcha("login");
      loadCaptcha("register");
    }, 100);
  }

  bindAuthPhoneLoginInput();
  bindAuthSmsCodeInput();
  bindRegistrationDigitInputs();

  // 手机号归属地：注册/登录输入框实时显示
  ["auth-reg-phone", "mobile-reg-phone", "auth-username"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    let _debounce = null;
    el.addEventListener("input", function () {
      clearTimeout(_debounce);
      _debounce = setTimeout(() => _showPhoneLocationNearInput(el, el.value.trim()), 500);
    });
  });
  // mobile-username-container 内动态创建的 mobile-auth-username（手机登录）
  const mobileUsernameContainer = document.getElementById("mobile-username-container");
  if (mobileUsernameContainer) {
    let _mobileDebounce = null;
    mobileUsernameContainer.addEventListener("input", function (e) {
      if (e.target && e.target.id === "mobile-auth-username") {
        clearTimeout(_mobileDebounce);
        _mobileDebounce = setTimeout(() => _showPhoneLocationNearInput(e.target, e.target.value.trim()), 500);
      }
    });
  }
  // auth-username-container 内动态创建的 auth-username（手机登录）
  // const authUsernameContainer = document.getElementById("auth-username-container");
  if (authUsernameContainer) {
    let _authDebounce = null;
    authUsernameContainer.addEventListener("input", function (e) {
      if (e.target && e.target.id === "auth-username") {
        clearTimeout(_authDebounce);
        _authDebounce = setTimeout(() => _showPhoneLocationNearInput(e.target, e.target.value.trim()), 500);
      }
    });
  }
});
function modifyPhone() {
  const currentPhone = document.getElementById("profile-phone").value;
  document.getElementById("modify-phone-current").value = currentPhone;
  document.getElementById("modify-phone-new").value = "";
  document.getElementById("modify-phone-code").value = "";
  document.getElementById("modify-phone-modal").style.display = "flex";
  document.getElementById("modify-phone-password").value = "";
  _showPhoneLocationNearInput(document.getElementById("modify-phone-current"), currentPhone);
  document.body.classList.add("modal-visible");

  const currentPhoneInput = document.getElementById("modify-phone-current");
  const currentPhoneWrapper = currentPhoneInput
    ? currentPhoneInput.closest(".phone-input-wrapper")
    : null;
  if (currentPhoneWrapper) {
    const prefix = currentPhoneWrapper.querySelector(".phone-prefix");
    const isUnbound =
      !currentPhoneInput.value || currentPhoneInput.value === "未绑定";

    if (prefix) {
      prefix.style.display = isUnbound ? "none" : "inline";
    }
    currentPhoneWrapper.classList.toggle("prefix-hidden", isUnbound);
  }
}
function closeModifyPhoneModal() {
  document.getElementById("modify-phone-modal").style.display = "none";
}
async function sendModifyPhoneCode() {
  const newPhone = document.getElementById("modify-phone-new").value;
  if (!newPhone || !/^1[3-9]\d{9}$/.test(newPhone)) {
    showModalAlert("请输入正确的新手机号");
    return;
  }
  const btn = document.getElementById("modify-phone-send-btn");
  const originalText = btn.textContent;
  openCaptchaModal({
    phone: newPhone,
    button: btn,
    originalText: originalText,
    scene: "modify",
  });
  logMessage_Info("[修改手机号] 已打开图形验证码模态框");
}
async function confirmModifyPhone() {
  // 获取用户输入的原密码，用于身份验证
  const password = document.getElementById("modify-phone-password").value;
  // 验证原密码是否已填写，这是安全验证的必要步骤
  if (!password) {
    showModalAlert("请输入原密码进行验证");
    return;
  }
  const newPhone = document.getElementById("modify-phone-new").value;
  const code = document.getElementById("modify-phone-code").value;
  if (!/^1[3-9]\d{9}$/.test(newPhone)) {
    showModalAlert("请输入正确的新手机号格式");
    return;
  }
  try {
    const bindResult = await callPythonAPI_raw(
      "/api/auth/check_phone",
      "POST",
      { phone: newPhone },
    );
    if (
      bindResult &&
      bindResult.is_bound &&
      bindResult.bound_to_user !== currentAuthUsername
    ) {
      const confirmed = await jsShowConfirm(
        "手机号已被绑定",
        `您输入的新手机号 ${newPhone} 已被用户 ${bindResult.bound_to_user} 绑定。\n\n是否继续？\n\n如果继续，该手机号将从原账号上强制解绑并绑定到您的账号上。`,
      );
      if (!confirmed) {
        logMessage_Info("[修改手机号] 用户取消操作，因为手机号已被绑定。");
        return;
      }
      logMessage_Info("[修改手机号] 用户已确认强制解绑，继续操作...");
    } else if (
      bindResult &&
      bindResult.is_bound &&
      bindResult.bound_to_user === currentAuthUsername
    ) {
      showModalAlert("此手机号已绑定到您的账号。", "提示");
      closeModifyPhoneModal();
      return;
    }
    if (!newPhone || !code) {
      showModalAlert("请填写完整信息");
      return;
    }
  } catch (e) {
    logMessage_Error("检查手机号绑定失败:", e);
    showModalAlert(`检查手机号失败: ${e.message}，请稍后重试`, "网络错误");
    return;
  }
  try {
    const result = await callPythonAPI_raw("/api/user/update_phone", "POST", {
      new_phone: newPhone,
      sms_code: code,
      password: password, // 添加原密码参数用于身份验证
    });
    if (result && result.success) {
      showModalAlert("手机号修改成功");
      document.getElementById("profile-phone").value = newPhone;
      closeModifyPhoneModal();
    } else {
      showModalAlert(result?.message || "修改失败");
    }
  } catch (error) {
    showModalAlert("修改失败: " + error.message);
  }
}
async function loadSystemConfig() {
  configLoadState.system = false;
  const formContainer = $("admin-config-form");
  formContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch("/api/admin/config/load", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (!result.success) {
      formContainer.innerHTML = `<p class="text-red-500 text-center py-10">加载配置失败: ${result.message}</p>`;
      configLoadState.system = false;
      return;
    }

    const config = result.config;
    formContainer.innerHTML = "";

    // ==================== 旧配置迁移逻辑 ====================
    // 如果存在旧的 query_method 配置，自动迁移到 query_order
    // 迁移规则：将旧的优先方式放到查询顺序的最前面
    if (config.IP_Location && config.IP_Location.query_method) {
      const oldMethod = String(config.IP_Location.query_method || "").trim().toLowerCase();
      const currentOrder = String(config.IP_Location.query_order || "uapipro,amap,baidu").trim().toLowerCase();
      const orderList = currentOrder.split(",").map(s => s.trim()).filter(s => s);
      
      // 如果旧配置的方式不在第一位，则将其移到第一位
      if (oldMethod && orderList.includes(oldMethod) && orderList[0] !== oldMethod) {
        const newOrderList = [oldMethod, ...orderList.filter(s => s !== oldMethod)];
        config.IP_Location.query_order = newOrderList.join(",");
        console.log("[配置迁移] IP归属地查询顺序已迁移:", config.IP_Location.query_order);
      } else if (oldMethod && !orderList.includes(oldMethod)) {
        // 如果旧方式不在列表中，添加到最前面
        config.IP_Location.query_order = [oldMethod, ...orderList].join(",");
        console.log("[配置迁移] IP归属地查询顺序已添加旧方式:", config.IP_Location.query_order);
      }
      // 标记配置已迁移（前端不再显示query_method）
      delete config.IP_Location.query_method;
    }

    // ==================== 美化版 createInput 函数 ====================
    const createInput = (section, key, label, type = "text", help = "", options = {}) => {
      // 获取原始配置值
      const rawValue = section.split(".").reduce((acc, part) => (acc ? acc[part] : undefined), config)?.[key];

      // 标准化布尔值
      let value = rawValue ?? options.defaultValue;
      if (type === "boolean") {
        if (typeof rawValue === "boolean") {
          value = rawValue;
        } else if (typeof rawValue === "string") {
          value = rawValue.toLowerCase().trim() === "true";
        } else if (typeof rawValue === "number") {
          value = rawValue === 1;
        } else {
          value = false;
        }
      }

      // 根据类型选择图标
      let iconSvg = "";
      if (type === "boolean") {
        iconSvg = `<svg class="w-4 h-4 text-sky-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
      } else if (type === "number") {
        iconSvg = `<svg class="w-4 h-4 text-sky-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14"></path></svg>`;
      } else if (type === "password_storage" || key.includes("key") || key.includes("secret")) {
        iconSvg = `<svg class="w-4 h-4 text-sky-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path></svg>`;
      } else if (type === "ip_query_order") {
        iconSvg = `<svg class="w-4 h-4 text-sky-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>`;
      } else {
        iconSvg = `<svg class="w-4 h-4 text-sky-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>`;
      }

      let inputHtml = "";
      if (type === "boolean") {
        inputHtml = `
        <select id="config-${section}-${key}" ${section === "Map" && key === "frontend_proxy_enabled" ? 'onchange="toggleMapTileCacheSettings(this)"' : ''} class="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all duration-200 hover:border-slate-300">
          <option value="true" ${value === true ? "selected" : ""}>✅ 启用</option>
          <option value="false" ${value === false ? "selected" : ""}>❌ 禁用</option>
        </select>
      `;
      } else if (type === "number") {
        inputHtml = `<input type="number" step="${options.step || 1}" id="config-${section}-${key}" value="${value}" class="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all duration-200 hover:border-slate-300">`;
      } else if (type === "password_storage") {
        inputHtml = `
        <select id="config-${section}-${key}" class="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all duration-200 hover:border-slate-300">
          <option value="plaintext" ${value === "plaintext" ? "selected" : ""}>🔓 明文</option>
          <option value="sha256" ${value === "sha256" ? "selected" : ""}>🔐 SHA256</option>
          <option value="bcrypt" ${value === "bcrypt" ? "selected" : ""}>🛡️ BCrypt (自动加盐)</option>
        </select>
      `;
      } else if (type === "select") {
        const selectOptions = Array.isArray(options.selectOptions) ? options.selectOptions : [];
        inputHtml = `
        <select id="config-${section}-${key}" class="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all duration-200 hover:border-slate-300">
          ${selectOptions
            .map((option) => {
              const optionValue = String(option.value ?? "");
              const optionLabel = String(option.label ?? optionValue);
              return `<option value="${optionValue}" ${value === optionValue ? "selected" : ""}>${optionLabel}</option>`;
            })
            .join("")}
        </select>
      `;
      } else if (type === "ip_query_order") {
        // IP归属地查询顺序 - 拖拽排序
        const allMethods = [
          { key: "uapipro", name: "UapiPro", icon: "🌐" },
          { key: "amap", name: "高德地图", icon: "🗺️" },
          { key: "baidu", name: "百度开放数据", icon: "📍" },
          { key: "pconline", name: "PConline", icon: "💻" },
        ];
        const currentOrderStr = String(value || "uapipro,amap,baidu").trim().toLowerCase();
        const currentOrder = currentOrderStr.split(",").map(s => s.trim()).filter(s => s);
        
        // 根据当前顺序排列，未包含的放在后面
        const sortedMethods = [
          ...currentOrder.map(key => allMethods.find(m => m.key === key)).filter(Boolean),
          ...allMethods.filter(m => !currentOrder.includes(m.key))
        ];
        
        inputHtml = `
        <div id="config-${section}-${key}-container" class="space-y-1.5">
          <ul id="config-${section}-${key}-sortable" class="space-y-1.5">
            ${sortedMethods.map((m, idx) => `
              <li data-key="${m.key}" class="flex items-center gap-3 px-3 py-2.5 bg-white border border-slate-200 rounded-lg cursor-grab active:cursor-grabbing hover:bg-slate-50 hover:border-sky-300 transition-all duration-200 group">
                <span class="text-slate-400 group-hover:text-sky-500 transition-colors">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"></path></svg>
                </span>
                <span class="flex-shrink-0 w-6 h-6 flex items-center justify-center bg-sky-100 text-sky-600 rounded-full text-xs font-bold">${idx + 1}</span>
                <span class="text-lg">${m.icon}</span>
                <span class="flex-1 text-sm font-medium text-slate-700">${m.name}</span>
                <span class="text-xs text-slate-400 font-mono">${m.key}</span>
              </li>
            `).join("")}
          </ul>
          <input type="hidden" id="config-${section}-${key}" value="${currentOrder.join(",")}" />
        </div>
      `;
      } else if (type === "origin") {
        const escapedValue = String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
        inputHtml = `<div class="flex flex-col sm:flex-row gap-2"><input type="text" id="config-${section}-${key}" value="${escapedValue}" data-map-origin class="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm" placeholder="https://example.com"><button type="button" onclick="useCurrentMapPageOrigin(this)" data-use-map-origin="config-${section}-${key}" class="px-3 py-2 border border-slate-200 rounded-lg text-sm whitespace-nowrap">使用当前页面来源</button></div>`;
      } else if (type === "password") {
        const escapedValue = String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
        inputHtml = `<input type="password" autocomplete="off" id="config-${section}-${key}" value="${escapedValue}" class="w-full px-3 py-2.5 border border-slate-200 rounded-lg text-sm">`;
      } else {
        inputHtml = `<input type="text" id="config-${section}-${key}" value="${value || ""}" class="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500 outline-none transition-all duration-200 hover:border-slate-300" placeholder="${options.placeholder || ""}">`;
      }
      return `
      <div class="mb-4 p-4 bg-gradient-to-r from-slate-50 to-white border border-slate-100 rounded-xl hover:shadow-sm transition-shadow duration-200">
        <label for="config-${section}-${key}" class="flex items-center gap-2 mb-2">
          ${iconSvg}
          <span class="text-sm font-semibold text-slate-700">${label}</span>
        </label>
        ${inputHtml}
        ${help ? `<p class="text-xs text-slate-500 mt-2 flex items-start gap-1"><svg class="w-3.5 h-3.5 text-slate-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span>${help}</span></p>` : ""}
      </div>
    `;
    };
    let html = "";
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mb-2">界面配置</h5>';
    html += createInput(
      "Config",
      "default_ui",
      "默认 UI",
      "select",
      "控制访问 / 时默认显示的前端版本；固定入口 /old/ 与 /frontend/ 不受影响。",
      {
        selectOptions: [
          { value: "old", label: "旧版 UI（/old/）" },
          { value: "new", label: "新版 UI（/frontend/）" },
        ],
      },
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mb-2">游客配置</h5>';
    html += createInput(
      "Guest",
      "allow_guest_login",
      "允许游客登录",
      "boolean",
      "是否允许未注册用户以游客身份使用系统。",
    );
    html += createInput(
      "Guest",
      "max_active_guest_sessions",
      "最大活跃访客会话数",
      "number",
      "创建访客会话前检查；达到上限后直接拒绝，0 表示禁止创建。",
    );
    html += createInput(
      "Guest",
      "guest_session_inactivity_timeout",
      "访客会话闲置超时（秒）",
      "number",
      "访客会话超过该时间未活动后允许清理。",
    );
    html += createInput(
      "Guest",
      "guest_token_ttl_seconds",
      "访客 Token 最小有效期（秒）",
      "number",
      "访客 Token 至少保持有效的时间，实际不会早于访客会话过期。",
    );
    html += createInput(
      "Guest",
      "guest_token_grace_seconds",
      "Token 宽限期（秒）",
      "number",
      "访客 Token 至少比会话到期时间多保留的秒数。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mb-2">帮助配置</h5>';
    // 新手帮助相关配置
    html += createInput(
      "Guest",
      "show_newbie_help",
      "显示新手帮助",
      "boolean",
      "是否显示新手帮助提示。",
    );
    html += createInput(
      "Guest",
      "newbie_help_url",
      "新手帮助链接",
      "text",
      "指向新手帮助页面或文档的URL地址。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">系统配置</h5>';
    html += createInput(
      "System",
      "session_expiry_days",
      "会话过期时间 (天)",
      "number",
      "超过此时间未访问的会话将被自动清理。",
    );
    html += createInput(
      "System",
      "school_accounts_dir",
      "学校账号目录",
      "text",
      "存储 school_accounts/*.ini 文件的目录。",
    );
    html += createInput(
      "System",
      "system_accounts_dir",
      "系统账号目录",
      "text",
      "存储 system_accounts/*.json 文件的目录。",
    );
    html += createInput(
      "System",
      "permissions_file",
      "权限文件名",
      "text",
      "存储权限配置的JSON文件名。",
    );
    html += createInput(
      "System",
      "session_monitor_check_interval",
      "会话监控间隔 (秒)",
      "number",
      "系统检查会话活跃状态的间隔。",
    );
    html += createInput(
      "System",
      "session_inactivity_timeout",
      "会话不活跃超时 (秒)",
      "number",
      "会话无活动超过此时间将被清理。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">每日自动重启</h5>';
    html += createInput(
      "Daily_Restart",
      "enabled",
      "启用每日自动重启",
      "boolean",
      "关闭时不会触发每日自动完全重启。",
    );
    html += createInput(
      "Daily_Restart",
      "time",
      "触发时间 (HH:MM)",
      "text",
      "使用 24 小时制时间，例如 00:00 或 23:45。",
      { placeholder: "00:00" },
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">日志配置</h5>';
    html += createInput(
      "Logging",
      "log_rotation_size_mb",
      "日志轮转大小 (MB)",
      "number",
      "单个日志文件最大大小。",
    );
    html += createInput(
      "Logging",
      "archive_max_size_mb",
      "归档目录最大 (MB)",
      "number",
      "归档目录总大小限制，0为不限制。",
    );
    html += createInput(
      "Logging",
      "random_background_cache_max_size_mb",
      "背景缓存最大 (MB)",
      "number",
      "random_background_image 目录总大小限制，0为不限制。",
    );
    html += createInput(
      "Logging",
      "log_dir",
      "日志目录",
      "text",
      "存储 zx-slm-tool.log 文件的目录。",
    );
    html += createInput(
      "Logging",
      "archive_dir",
      "归档目录",
      "text",
      "存储压缩日志 (logs/archive) 的目录。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">安全配置</h5>';
    html += createInput(
      "Security",
      "password_storage",
      "密码存储方式",
      "password_storage",
      "修改此项可能导致旧密码失效。",
    );
    html += createInput(
      "Security",
      "brute_force_protection",
      "启用暴力破解防护",
      "boolean",
      "限制登录尝试次数。",
    );
    html += createInput(
      "Security",
      "login_log_retention_days",
      "登录日志保留 (天)",
      "number",
      "登录审计日志的保留天数。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">账号功能配置</h5>';
    html += createInput(
      "Features",
      "account_cancellation_wait_hours",
      "账号注销冷静期（小时）",
      "number",
      "用户申请注销账号后，在此时间段内登录可撤销注销，到期后账号将被自动删除。默认 24 小时。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">地图配置</h5>';
    html += '<p class="text-sm text-slate-600 mb-4">后端路径规划与前端地图代理共用以下页面来源。前端启用后端代理后使用配置来源；关闭代理时使用当前页面来源。各地图的来源优先于全局来源。</p>';
    html += createInput(
      "Map",
      "provider",
      "地图提供方",
      "select",
      "全局单选地图提供方：amap、tencent、tianditu、baidu。PC 与移动端配置页共享同一后端真相源。",
      {
        selectOptions: [
          { value: "amap", label: "高德地图" },
          { value: "tencent", label: "腾讯地图" },
          { value: "tianditu", label: "天地图" },
          { value: "baidu", label: "百度地图" },
        ],
      },
    );
    html += createInput(
      "Map.providers.amap",
      "js_key",
      "高德地图 JS Key",
      "text",
      "主配置改为 provider 嵌套字段；Map.amap_js_key 仅作为兼容读取来源。",
    );
    html += createInput("Map.providers.amap", "security_js_code", "高德安全密钥（选填）", "password", "需与高德 JS Key 配套；旧 Key 可留空。");
    html += createInput("Map", "backend_page_origin", "地图页面来源（选填）", "origin", "用于后端路径规划和前端地图代理。留空自动使用应用请求来源；粘贴完整 URL 后仅保留协议、域名和端口。");
    html += createInput("Map", "frontend_proxy_enabled", "启用地图请求后端代理", "boolean", "默认关闭。开启由服务器转发地图请求并使用配置来源；关闭由浏览器直连地图服务，使用当前页面来源。保存后刷新页面生效；已加载地图时，下次加载切换模式会自动刷新页面。");
    html += '<div data-map-tile-cache-settings>';
    html += createInput("Map", "tile_cache_ttl_days", "地图瓦片缓存时间（天）", "number", "正整数；上游更短的有效期优先。私有响应或带 Cookie 的资源不缓存；关闭代理时保留此设置。", { defaultValue: 20 });
    html += createInput("Map", "tile_cache_max_size_gb", "地图瓦片缓存最大大小（GB）", "number", "所有地图供应商共享此缓存总容量，各供应商缓存数据独立；1 GB = 10 亿字节，最多两位小数。", { defaultValue: 10, step: 0.01 });
    html += '</div>';
    for (const [provider, label] of [["amap", "高德地图"], ["tencent", "腾讯地图"], ["tianditu", "天地图"], ["baidu", "百度地图"]]) {
      html += createInput(`Map.providers.${provider}`, "backend_page_origin", `${label}页面来源（选填）`, "origin", "同时用于该地图的后端规划和前端代理；留空继承全局来源。");
    }
    html += createInput(
      "Map.providers.tencent",
      "map_key",
      "腾讯地图 Key",
      "text",
      "用于腾讯地图路线规划与地图渲染。",
    );
    html += createInput(
      "Map.providers.tianditu",
      "token",
      "天地图 Token",
      "text",
      "用于天地图正式业务接入；内部坐标仍统一按 GCJ02 处理。",
    );
    html += createInput(
      "Map.providers.baidu",
      "ak",
      "百度地图 AK",
      "text",
      "用于百度地图正式业务接入；当前先纳入 provider 契约与配置路径。",
    );
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">🌐 IP 归属地查询配置</h5>';
    html += createInput(
      "IP_Location",
      "query_order",
      "查询顺序（拖拽排序）",
      "ip_query_order",
      "拖拽调整查询优先级。查询失败时会自动尝试下一个服务。",
    );
    html += createInput(
      "IP_Location",
      "amap_web_api_key",
      "高德 Web API Key",
      "text",
      "用于调用高德地图的 Web API 进行 IP 归属地查询等",
    );
    html += createInput(
      "IP_Location",
      "uapipro_api_key",
      "UapiPro API Key",
      "text",
      "用于调用 UapiPro 的 API 进行 IP 归属地查询、手机号归属地查询、随机图片等",
    );
    // html +=
    //   '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">第三方 API 配置</h5>';
    // ==================== 网站备案信息配置 ====================
    // 添加网站备案（Beian）相关配置项，包括ICP备案号和公安网备案号
    // 这些配置项用于在网站底部显示合规信息，满足中国大陆网站的备案要求
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">网站备案信息</h5>';
    // ICP备案号配置项
    // 用于显示工信部颁发的ICP备案号，例如：京ICP备12345678号
    html += createInput(
      "Beian",
      "icp_number",
      "ICP备案号",
      "text",
      "工信部ICP备案号，如：京ICP备12345678号",
    );
    // 是否显示ICP备案信息的开关
    // 管理员可以选择是否在页面底部展示ICP备案号
    html += createInput(
      "Beian",
      "show_icp",
      "显示ICP备案",
      "boolean",
      "是否在页面底部显示ICP备案信息",
    );
    // 公安网备案号配置项
    // 用于显示公安部网络安全备案号，例如：京公网安备 11010802012345号
    html += createInput(
      "Beian",
      "police_number",
      "公安网备案号",
      "text",
      "公安部网络安全备案号，如：京公网安备 11010802012345号",
    );
    // 是否显示公安网备案信息的开关
    // 管理员可以选择是否在页面底部展示公安网备案号
    html += createInput(
      "Beian",
      "show_police",
      "显示公安备案",
      "boolean",
      "是否在页面底部显示公安网备案信息",
    );

    // ==================== 百度云审核服务配置 ====================
    // 添加百度云文本审核API相关配置项
    // 用途：对用户发布的留言内容进行智能审核，检测违规信息
    // 依赖：需要在百度智能云控制台创建"内容审核"应用
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">🔍 百度云审核服务</h5>';
    // 添加说明文字，引导管理员了解此配置的用途
    html +=
      '<p class="text-xs text-slate-500 mb-3">用于留言内容审核，检测违规信息（色情、暴力、政治敏感等）</p>';

    // API Key 配置项
    // 用于身份验证，从百度智能云控制台获取
    // 类型：text（普通文本输入框）
    html += createInput(
      "baidu_cloud",
      "api_key",
      "API Key",
      "text",
      "在百度云控制台创建应用后获取的API密钥",
    );

    // Secret Key 配置项
    // 与 API Key 配合使用，用于生成访问令牌
    // 类型：password（密码输入框，隐藏输入内容保护隐私）
    // 注意：虽然这里使用 type="text"，但由于 createInput 函数的限制，
    // 实际会创建普通文本输入框。如需真正的密码框，需要修改 createInput 函数
    html += createInput(
      "baidu_cloud",
      "secret_key",
      "Secret Key",
      "text",
      "在百度云控制台创建应用后获取的密钥",
    );

    // 策略ID 配置项（可选）
    // 百度云支持自定义审核策略，可以设置不同的审核严格程度
    // 留空则使用百度云的默认审核策略
    html += createInput(
      "baidu_cloud",
      "strategy_id",
      "策略ID（可选）",
      "text",
      "自定义审核策略的ID，留空则使用百度云默认审核策略",
    );

    // ==================== 留言内容审核功能配置 ====================
    // 添加内容审核功能的总开关
    // 控制是否启用留言内容的自动审核
    html +=
      '<h5 class="font-bold text-base text-sky-800 border-b pb-1 mt-4 mb-2">📝 留言内容审核</h5>';

    // 添加警告提示，提醒管理员需要先配置百度云API密钥
    // 使用醒目的黄色背景色和警告图标，增强视觉提示效果
    html +=
      '<p class="text-xs text-amber-600 bg-amber-50 p-2 rounded mb-3">⚠️ 启用此功能需要先配置上方的百度云API密钥</p>';

    // 是否启用留言审核的开关
    // 类型：boolean（布尔值选择器，显示"启用"或"禁用"）
    // 启用后，用户提交的留言将先通过百度云API检测，检测通过才能发布
    html += createInput(
      "Content_Review",
      "enable_message_review",
      "启用留言审核",
      "boolean",
      "启用后，留言将通过百度云文本审核服务检测后才能发布",
    );

    formContainer.innerHTML = html;
    const proxyToggle = formContainer.querySelector('[id="config-Map-frontend_proxy_enabled"]');
    if (proxyToggle) toggleMapTileCacheSettings(proxyToggle);
    formContainer.querySelectorAll("[data-map-origin]").forEach((input) => {
      input.addEventListener("blur", () => {
        try { input.value = normalizeBackendPageOrigin(input.value); input.setCustomValidity(""); }
        catch (error) { input.setCustomValidity(error.message); input.reportValidity(); }
      });
    });
    
    // ==================== 初始化 SortableJS 拖拽排序 ====================
    // 为 IP 归属地查询顺序的拖拽列表初始化 SortableJS
    const sortableContainer = document.getElementById("config-IP_Location-query_order-sortable");
    if (sortableContainer && typeof Sortable !== "undefined") {
      new Sortable(sortableContainer, {
        animation: 150,
        ghostClass: "bg-sky-100",
        chosenClass: "shadow-lg",
        dragClass: "opacity-50",
        handle: ".cursor-grab",
        onEnd: function () {
          // 获取排序后的顺序
          const items = sortableContainer.querySelectorAll("li[data-key]");
          const order = Array.from(items).map(item => item.dataset.key);
          // 更新隐藏输入框的值
          const hiddenInput = document.getElementById("config-IP_Location-query_order");
          if (hiddenInput) {
            hiddenInput.value = order.join(",");
          }
          // 更新序号显示
          items.forEach((item, idx) => {
            const numSpan = item.querySelector(".bg-sky-100");
            if (numSpan) {
              numSpan.textContent = idx + 1;
            }
          });
          console.log("[配置] IP归属地查询顺序已更新:", order.join(","));
        },
      });
      console.log("[配置] SortableJS 拖拽排序已初始化");
    }
    
    configLoadState.system = true;
  } catch (e) {
    configLoadState.system = false;
    formContainer.innerHTML = `<p class="text-red-500 text-center py-10">加载配置时发生错误: ${e.message}</p>`;
  }
}
/**
 * 加载验证码配置参数（PC端）
 * 从后端 /api/captcha/config API 获取验证码配置参数并填充到表单中
 *
 * 功能说明：
 * - 调用 /api/captcha/config API 获取最新的验证码配置
 * - 将获取到的配置值填充到PC端的三个输入框中
 * - 提供友好的错误提示和日志记录
 *
 * 涉及的表单字段：
 * - captcha-length: 验证码字符长度（3-6）
 * - captcha-scale-factor: 图像缩放因子（2-4）
 * - captcha-noise-level: 噪声级别（0.0-0.3）
 *
 * @returns {Promise<void>} 无返回值
 */
const DEFAULT_CAPTCHA_PROVIDER_SETTINGS = {
  provider: "image",
  behavior_base_url: "",
  behavior_api_key: "",
  behavior_type: "SLIDER",
};

// captcha-local API 验证码服务器支持的类型。
const BEHAVIOR_CAPTCHA_TYPES = [
  { value: "SLIDER", label: "滑块验证码" },
  { value: "SLIDER2", label: "滑块验证码 V2（旋转图块）" },
  { value: "ROTATE", label: "旋转验证码" },
  { value: "CONCAT", label: "滑动还原验证码" },
  { value: "WORD_IMAGE_CLICK", label: "文字点选验证码" },
  { value: "GESTURE", label: "曲线绘制验证码" },
  { value: "CURVE", label: "滑动曲线验证码" },
  { value: "CURVE2", label: "滑动曲线验证码 V2" },
  { value: "CURVE3", label: "滑动曲线验证码 V3" },
  { value: "WORD_ORDER_CLICK", label: "语序点选验证码" },
  { value: "POW", label: "工作量证明验证码" },
  { value: "MATH", label: "数学计算验证码" },
  { value: "ICON_CLICK", label: "图标点选验证码" },
  { value: "DIRECTION_CLICK", label: "方向识别验证码" },
  { value: "RANDOM", label: "随机验证码" },
];

function getCaptchaFormElement(id) {
  return document.getElementById(id);
}

function populateBehaviorCaptchaTypeSelects() {
  const optionsHtml = BEHAVIOR_CAPTCHA_TYPES.map(
    (item) => `<option value="${item.value}">${item.label}（${item.value}）</option>`,
  ).join("");

  ["captcha-behavior-type", "mobile-captcha-behavior-type"].forEach((id) => {
    const select = getCaptchaFormElement(id);
    if (!select || select.dataset.behaviorCaptchaTypesReady === "true") {
      return;
    }
    const currentValue = select.value || DEFAULT_CAPTCHA_PROVIDER_SETTINGS.behavior_type;
    select.innerHTML = optionsHtml;
    select.dataset.behaviorCaptchaTypesReady = "true";
    select.value = BEHAVIOR_CAPTCHA_TYPES.some((item) => item.value === currentValue)
      ? currentValue
      : DEFAULT_CAPTCHA_PROVIDER_SETTINGS.behavior_type;
  });
}

function normalizeCaptchaProviderSettings(settings = {}) {
  settings = settings || {};
  const provider =
    String(settings.provider || DEFAULT_CAPTCHA_PROVIDER_SETTINGS.provider)
      .trim()
      .toLowerCase() === "behavior"
      ? "behavior"
      : "image";
  const behaviorType = String(
    settings.behavior_type || DEFAULT_CAPTCHA_PROVIDER_SETTINGS.behavior_type,
  )
    .trim()
    .toUpperCase();

  return {
    provider,
    behavior_base_url: String(settings.behavior_base_url || "").trim(),
    behavior_api_key: String(settings.behavior_api_key || ""),
    behavior_type: BEHAVIOR_CAPTCHA_TYPES.some((item) => item.value === behaviorType)
      ? behaviorType
      : DEFAULT_CAPTCHA_PROVIDER_SETTINGS.behavior_type,
  };
}

function toggleCaptchaProviderFields(prefix = "") {
  const behaviorRadio = getCaptchaFormElement(`${prefix}captcha-provider-behavior`);
  const serverFields = getCaptchaFormElement(`${prefix}captcha-behavior-fields`);
  const imageFields = getCaptchaFormElement(`${prefix}captcha-image-fields`);
  const provider = behaviorRadio && behaviorRadio.checked ? "behavior" : "image";
  if (serverFields) {
    serverFields.classList.toggle("hidden", provider !== "behavior");
  }
  if (imageFields) {
    imageFields.classList.toggle("hidden", provider === "behavior");
  }
  setCaptchaProviderCardStates(prefix, provider);
  setCaptchaProviderActionText(prefix, provider);
}

function setCaptchaProviderCardStates(prefix = "", provider = "image") {
  ["image", "behavior"].forEach((item) => {
    const radio = getCaptchaFormElement(`${prefix}captcha-provider-${item}`);
    const card = radio ? radio.closest("[data-captcha-provider-card]") : null;
    if (!card) return;
    const active = item === provider;
    card.classList.toggle("border-sky-400", active);
    card.classList.toggle("bg-sky-50", active);
    card.classList.toggle("ring-1", active);
    card.classList.toggle("ring-sky-200", active);
    card.classList.toggle("border-slate-200", !active);
  });
}

function setCaptchaProviderActionText(prefix = "", provider = "image") {
  const testButton = getCaptchaFormElement(`${prefix}test-captcha-btn`);
  if (!testButton) return;
  testButton.textContent = provider === "behavior" ? "🔄 测试服务器" : "🔄 测试生成";
}

function applyCaptchaProviderSettings(settings = {}, prefix = "") {
  populateBehaviorCaptchaTypeSelects();
  const normalized = normalizeCaptchaProviderSettings(settings);
  const imageRadio = getCaptchaFormElement(`${prefix}captcha-provider-image`);
  const behaviorRadio = getCaptchaFormElement(`${prefix}captcha-provider-behavior`);
  const baseUrlInput = getCaptchaFormElement(`${prefix}captcha-behavior-base-url`);
  const apiKeyInput = getCaptchaFormElement(`${prefix}captcha-behavior-api-key`);
  const typeSelect = getCaptchaFormElement(`${prefix}captcha-behavior-type`);

  if (imageRadio) imageRadio.checked = normalized.provider === "image";
  if (behaviorRadio) behaviorRadio.checked = normalized.provider === "behavior";
  if (baseUrlInput) baseUrlInput.value = normalized.behavior_base_url;
  if (apiKeyInput) apiKeyInput.value = normalized.behavior_api_key;
  if (typeSelect) typeSelect.value = normalized.behavior_type;
  toggleCaptchaProviderFields(prefix);
}

function readCaptchaProviderForm(prefix = "") {
  populateBehaviorCaptchaTypeSelects();
  const behaviorRadio = getCaptchaFormElement(`${prefix}captcha-provider-behavior`);
  const baseUrlInput = getCaptchaFormElement(`${prefix}captcha-behavior-base-url`);
  const apiKeyInput = getCaptchaFormElement(`${prefix}captcha-behavior-api-key`);
  const typeSelect = getCaptchaFormElement(`${prefix}captcha-behavior-type`);
  return normalizeCaptchaProviderSettings({
    provider: behaviorRadio && behaviorRadio.checked ? "behavior" : "image",
    behavior_base_url: baseUrlInput ? baseUrlInput.value : "",
    behavior_api_key: apiKeyInput ? apiKeyInput.value : "",
    behavior_type: typeSelect ? typeSelect.value : "SLIDER",
  });
}

function handleCaptchaProviderChange(prefix = "") {
  toggleCaptchaProviderFields(prefix);
}

function getCaptchaTestPreviewElements(prefix = "") {
  return {
    container: getCaptchaFormElement(`${prefix}captcha-test-preview`),
    display: getCaptchaFormElement(`${prefix}captcha-preview-display`),
    answerLabel: getCaptchaFormElement(`${prefix}captcha-preview-answer-label`),
    answer: getCaptchaFormElement(`${prefix}captcha-preview-answer`),
  };
}

function renderCaptchaTestPreview(result, prefix = "") {
  const { container, display, answerLabel, answer } =
    getCaptchaTestPreviewElements(prefix);
  if (!container || !display || !answer) {
    return;
  }

  container.classList.remove("hidden");
  if (result.provider === "behavior") {
    const captcha = result.captcha || {};
    const captchaId = result.captcha_id || captcha.id || "-";
    const captchaType = result.behavior_type || captcha.type || "-";
    const backgroundImage = captcha.backgroundImage || "";
    const templateImage = captcha.templateImage || "";
    const imageHtml = backgroundImage
      ? `<img src="${escapeHtml(backgroundImage)}" alt="验证码背景" class="max-w-full rounded border border-slate-200 bg-white">`
      : '<div class="text-xs text-slate-500 bg-slate-50 rounded border border-slate-200 px-3 py-6">验证码服务器未返回可预览图片</div>';
    const templateHtml = templateImage
      ? `<img src="${escapeHtml(templateImage)}" alt="验证码模板" class="max-h-20 rounded border border-slate-200 bg-white p-1">`
      : "";
    display.innerHTML = `
      <div class="w-full max-w-full space-y-2">
        <div class="flex items-center justify-center overflow-hidden">${imageHtml}</div>
        ${templateHtml ? `<div class="flex items-center justify-center">${templateHtml}</div>` : ""}
        <div class="text-[11px] text-slate-500 break-all">
          类型：<span class="font-mono">${escapeHtml(captchaType)}</span>
        </div>
      </div>
    `;
    if (answerLabel) answerLabel.textContent = "验证码 ID：";
    answer.textContent = captchaId;
    return;
  }

  const captchaWidth = result.width || 343;
  const captchaHeight = result.height || 119;
  const timestamp = Date.now();
  display.innerHTML = `
    <iframe
      src="/api/captcha/html/${result.captcha_id}?t=${timestamp}&width=${captchaWidth}"
      style="max-width: ${captchaWidth}px; max-height: ${captchaHeight}px; width: ${captchaWidth}px; height: ${captchaHeight}px; border: none; overflow: hidden; display: block; margin: 0 auto;"
      scrolling="no"
      frameborder="0"
      title="验证码预览">
    </iframe>
  `;
  if (answerLabel) answerLabel.textContent = "验证码答案：";
  answer.textContent = result.code || "-";
}

async function loadCaptchaSettings(ShowSwalFire = true) {
  configLoadState.captcha = false;
  try {
    // 步骤1：记录开始加载的日志，便于调试和追踪
    console.log(
      "[验证码设置] 开始从 /api/captcha/config 加载验证码配置参数...",
    );

    // 步骤2：调用后端API获取验证码配置
    // 使用fetch进行HTTP GET请求
    const response = await fetch("/api/captcha/config", {
      method: "GET", // 使用GET方法获取数据
      headers: {
        // 发送Session ID用于身份验证，确保只有已登录的管理员可以访问
        "X-Session-ID": sessionUUID,
        // 指定期望的响应内容类型为JSON
        "Content-Type": "application/json",
      },
      // 包含cookie凭证，确保会话状态正确传递
      credentials: "include",
    });

    // 步骤3：解析响应的JSON数据
    // await确保等待JSON解析完成
    const result = await response.json();

    // 步骤4：检查API调用是否成功
    // result.success 表示后端是否成功返回了配置数据
    // result.config 包含实际的配置参数对象
    if (result && result.success && result.config) {
      // 步骤5：从返回的config对象中提取配置参数
      const settings = result.config;

      // 步骤6：填充PC端的验证码长度输入框
      // 【修复】使用 !== undefined 判断，正确区分"值为0"和"未设置"
      // 原代码：settings.length || 4 会将0误判为falsy值
      // 新代码：只有在undefined时才使用默认值4
      $("captcha-length").value =
        settings.length !== undefined ? settings.length : 4;

      // 步骤7：填充PC端的细分倍数输入框
      // 【修复】使用 !== undefined 判断，正确区分"值为0"和"未设置"
      // 默认值为2，这是一个适中的缩放比例
      // 原代码：settings.scale_factor || 2 可能将0误判为falsy值（虽然scale_factor不太可能为0）
      $("captcha-scale-factor").value =
        settings.scale_factor !== undefined ? settings.scale_factor : 2;

      // 步骤8：填充PC端的噪点比例输入框
      // 【修复】使用 !== undefined 判断，正确区分"值为0.0"和"未设置"
      // ⚠️ 关键修复：当noise_level为0.0时，原代码 settings.noise_level || 0.08 会错误地返回0.08
      // 因为JavaScript中0.0是falsy值，|| 运算符会跳过它并使用默认值
      // 新代码：只有在noise_level === undefined时才使用默认值0.08，允许用户设置0.0
      // 默认值为0.08（8%），这是一个适中的噪点密度
      $("captcha-noise-level").value =
        settings.noise_level !== undefined ? settings.noise_level : 0.08;
      applyCaptchaProviderSettings(settings, "");
      applyCaptchaProviderSettings(settings, "mobile-");

      // 只记录加载状态，避免把验证码服务配置写入控制台。
      console.log("[验证码设置] 已从 /api/captcha/config 加载配置");

      // 步骤10：显示成功提示（可选，避免过多打扰用户）
      // 使用Swal.fire显示简短的成功提示，2秒后自动关闭
      if (ShowSwalFire) {
        Swal.fire({
          icon: "success", // 成功图标（绿色对号）
          title: "加载成功", // 标题
          text: "验证码配置已加载", // 提示文本
          timer: 1500, // 1.5秒后自动关闭
          showConfirmButton: false, // 不显示确认按钮，自动关闭
        });
      }
      configLoadState.captcha = true;
    } else {
      // 步骤11：处理API返回成功但没有配置数据的情况
      // 这通常表示配置文件不存在或格式错误
      console.warn("[验证码设置] API返回成功但未包含配置数据，使用默认值");

      // 步骤12：使用默认值填充表单
      $("captcha-length").value = 4; // 默认长度4个字符
      $("captcha-scale-factor").value = 2; // 默认缩放因子2倍
      $("captcha-noise-level").value = 0.08; // 默认噪点比例8%
      applyCaptchaProviderSettings(DEFAULT_CAPTCHA_PROVIDER_SETTINGS, "");
      applyCaptchaProviderSettings(DEFAULT_CAPTCHA_PROVIDER_SETTINGS, "mobile-");

      // 步骤13：显示警告提示，告知用户正在使用默认值
      Swal.fire({
        icon: "warning", // 警告图标（黄色感叹号）
        title: "使用默认配置", // 标题
        text: "未找到配置文件，已加载默认值", // 提示文本
        timer: 2000, // 2秒后自动关闭
        showConfirmButton: false, // 不显示确认按钮
      });
      configLoadState.captcha = true;
    }
  } catch (error) {
    configLoadState.captcha = false;
    // 步骤14：捕获并处理所有可能的异常（网络错误、解析错误等）
    // 记录详细的错误日志，包含错误对象的完整信息
    console.error("[验证码设置] 从 /api/captcha/config 加载配置失败:", error);

    // 步骤15：在发生错误时，仍然提供默认值，确保用户可以继续使用
    $("captcha-length").value = 4; // 默认长度
    $("captcha-scale-factor").value = 2; // 默认缩放因子
    $("captcha-noise-level").value = 0.08; // 默认噪点比例
    applyCaptchaProviderSettings(DEFAULT_CAPTCHA_PROVIDER_SETTINGS, "");
    applyCaptchaProviderSettings(DEFAULT_CAPTCHA_PROVIDER_SETTINGS, "mobile-");

    // 步骤16：显示友好的错误提示给用户
    // 使用Swal.fire显示错误对话框，用户需要点击确认才能关闭
    Swal.fire({
      icon: "error", // 错误图标（红色叉号）
      title: "加载失败", // 标题
      text: "无法加载验证码配置: " + error.message, // 错误信息，包含具体的错误原因
      confirmButtonText: "确定", // 确认按钮文本
    });
  }
}
async function saveCaptchaSettings() {
  if (!ensureConfigLoaded("captcha", "验证码")) {
    return;
  }
  try {
    console.log("[验证码设置] 开始保存验证码配置...");
    const length = parseInt($("captcha-length").value);
    const scale_factor = parseInt($("captcha-scale-factor").value);
    const noise_level = parseFloat($("captcha-noise-level").value);
    if (isNaN(length) || length < 3 || length > 6) {
      Swal.fire({
        icon: "error",
        title: "参数错误",
        text: "验证码长度必须在3-6之间",
      });
      return;
    }
    if (isNaN(scale_factor) || scale_factor < 2 || scale_factor > 32) {
      Swal.fire({
        icon: "error",
        title: "参数错误",
        text: "细分倍数必须在2-32之间",
      });
      return;
    }
    if (isNaN(noise_level) || noise_level < 0 || noise_level > 0.3) {
      Swal.fire({
        icon: "error",
        title: "参数错误",
        text: "噪点比例必须在0.0-0.3之间",
      });
      return;
    }
    const providerConfig = readCaptchaProviderForm("");
    if (providerConfig.provider === "behavior" && !providerConfig.behavior_base_url) {
      Swal.fire({
        icon: "error",
        title: "参数错误",
        text: "选择验证码服务器时，服务地址不能为空",
      });
      return;
    }
    const providerConfigSummary = {
      behavior_base_url: providerConfig.behavior_base_url,
      behavior_api_key: providerConfig.behavior_api_key ? "******" : "",
      behavior_type: providerConfig.behavior_type,
    };
    console.log("[验证码设置] 参数验证通过:", {
      length,
      scale_factor,
      noise_level,
      provider: providerConfig.provider,
      ...providerConfigSummary,
    });
    const response = await fetch("/api/captcha/save_settings", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      credentials: "include",
      body: JSON.stringify({
        length,
        scale_factor,
        noise_level,
        ...providerConfig,
      }),
    });
    const result = await response.json();
    if (result && result.success) {
      console.log("[验证码设置] 保存成功");
      Swal.fire({
        icon: "success",
        title: "保存成功",
        text: "验证码设置已保存",
        showConfirmButton: true,   // 显示关闭按钮
        confirmButtonText: "关闭"  // 可自定义按钮文字
      });

      if (window.initialData) {
        window.initialData.captcha_settings = {
          length,
          scale_factor,
          noise_level,
          ...providerConfig,
        };
      }
      applyCaptchaProviderSettings(providerConfig, "mobile-");
      setRuntimeCaptchaProviderConfig(providerConfig);
    } else {
      throw new Error(result?.message || "保存失败");
    }
  } catch (error) {
    console.error("[验证码设置] 保存失败:", error);
    Swal.fire({
      icon: "error",
      title: "保存失败",
      text: error.message || "无法保存验证码设置",
    });
  }
}
async function testGenerateCaptcha() {
  // UI反馈：禁用按钮并显示加载状态
  try {
    const testCaptchaBtnEl = $("test-captcha-btn");
    if (testCaptchaBtnEl) {
      testCaptchaBtnEl.classList.add("btn-loading");
      testCaptchaBtnEl.setAttribute("disabled", "disabled");
    }
  } catch (e) {
    console.error("设置测试按钮加载状态失败:", e);
  }

  try {
    console.log("[验证码设置] 开始测试生成验证码...");
    const providerConfig = readCaptchaProviderForm("");
    if (providerConfig.provider === "behavior" && !providerConfig.behavior_base_url) {
      Swal.fire({
        icon: "error",
        title: "参数错误",
        text: "选择验证码服务器时，服务地址不能为空",
      });
      return;
    }
    const length = parseInt($("captcha-length").value) || 4;
    const scale_factor = parseInt($("captcha-scale-factor").value) || 2;
    const noise_level = parseFloat($("captcha-noise-level").value) || 0.08;
    if (providerConfig.provider !== "behavior") {
      if (isNaN(length) || length < 3 || length > 6) {
        Swal.fire({
          icon: "error",
          title: "参数错误",
          text: "验证码长度必须在3-6之间",
        });
        return;
      }
      if (isNaN(scale_factor) || scale_factor < 2 || scale_factor > 32) {
        Swal.fire({
          icon: "error",
          title: "参数错误",
          text: "细分倍数必须在2-32之间",
        });
        return;
      }
      if (isNaN(noise_level) || noise_level < 0 || noise_level > 0.3) {
        Swal.fire({
          icon: "error",
          title: "参数错误",
          text: "噪点比例必须在0.0-0.3之间",
        });
        return;
      }
    }

    // if (!need_weight || (need_weight == '' || need_weight == "NULL" || need_weight == "null" || need_weight == "undefined")) {
    try {
      need_weight =
        document.getElementById("admin-captcha-panel_modal").clientWidth - 400;
      console.log("获取验证码历史面板宽度：", need_weight);
    } catch (e) {
      console.error("获取验证码历史面板宽度失败:", e);
    }
    // }

    if (
      need_weight !== "" &&
      need_weight !== "NULL" &&
      need_weight !== "null" &&
      need_weight !== "undefined"
    ) {
      if (need_weight > 1000) need_weight = 1000;
      if (need_weight < 200) need_weight = 200;
      console.log("验证码显示区域宽度：", need_weight);
    }

    const response = await fetch("/api/captcha/test_generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      credentials: "include",
      body: JSON.stringify({
        length,
        scale_factor,
        noise_level,
        weight: need_weight,
        ...providerConfig,
      }),
    });
    const result = await response.json();
    if (result && result.success) {
      if (result.provider === "behavior") {
        console.log("[验证码设置] 验证码服务器测试生成成功");
      } else {
        console.log("[验证码设置] 测试生成成功");
      }
      renderCaptchaTestPreview(result, "");
    } else {
      throw new Error(result?.message || "生成失败");
    }
  } catch (error) {
    console.error("[验证码设置] 测试生成失败:", error);
    Swal.fire({
      icon: "error",
      title: "生成失败",
      text: error.message || "无法生成测试验证码",
    });
  } finally {
    try {
      const testCaptchaBtnEl = $("test-captcha-btn");
      if (testCaptchaBtnEl) {
        testCaptchaBtnEl.classList.remove("btn-loading");
        testCaptchaBtnEl.removeAttribute("disabled");
      }
    } catch (e) {
      console.error("恢复测试按钮状态失败:", e);
    }
  }
}
document.addEventListener("DOMContentLoaded", function () {
  populateBehaviorCaptchaTypeSelects();
  ["", "mobile-"].forEach((prefix) => {
    ["image", "behavior"].forEach((provider) => {
      const radio = getCaptchaFormElement(`${prefix}captcha-provider-${provider}`);
      if (radio) {
        radio.addEventListener("change", () => handleCaptchaProviderChange(prefix));
      }
    });
    toggleCaptchaProviderFields(prefix);
  });

  const saveCaptchaSettingsBtn = $("save-captcha-settings-btn");
  if (saveCaptchaSettingsBtn) {
    saveCaptchaSettingsBtn.addEventListener("click", saveCaptchaSettings);
    console.log("[验证码设置] 已注册保存按钮事件");
  }
  const testCaptchaBtn = $("test-captcha-btn");
  if (testCaptchaBtn) {
    testCaptchaBtn.addEventListener("click", testGenerateCaptcha);
    console.log("[验证码设置] 已注册测试按钮事件");
  }
  const refreshCaptchaHistoryBtn = $("refresh-captcha-history-btn");
  if (refreshCaptchaHistoryBtn) {
    refreshCaptchaHistoryBtn.addEventListener("click", () => loadCaptchaHistory());
    console.log("[验证码历史] 已注册刷新按钮事件");
  }
});

function isBehaviorCaptchaRecord(record) {
  if (!record) return false;
  const provider = String(
    record.provider || record.captcha_provider || "",
  ).toLowerCase();
  return provider === "behavior" || !!record.behavior_type;
}

function getCaptchaHistoryDisplayText(record) {
  if (isBehaviorCaptchaRecord(record)) {
    return "使用验证码服务器";
  }
  return record.code || record.captcha_code || "N/A";
}

async function loadCaptchaHistory(need_weight = "") {
  const listContainer = $("admin-captcha-list_modal");
  if (!listContainer) {
    console.error("找不到容器 admin-captcha-list_modal");
    return;
  }
  listContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';
  try {
    const dateInput = $("captcha-history-date");
    const statusSelect = $("captcha-history-status");

    if (!dateInput || !statusSelect) return;
    const date = dateInput.value.replace(/-/g, "");
    const status = statusSelect.value;
    const params = new URLSearchParams({ date });
    if (status) {
      params.append("status", status);
    }

    if (
      !need_weight ||
      need_weight == "" ||
      need_weight == "NULL" ||
      need_weight == "null" ||
      need_weight == "undefined"
    ) {
      try {
        need_weight =
          document.getElementById("admin-captcha-history-panel_modal")
            .clientWidth - 200;
        console.log("获取验证码历史面板宽度：", need_weight);
      } catch (e) {
        console.error("获取验证码历史面板宽度失败:", e);
      }
    }

    if (
      need_weight !== "" &&
      need_weight !== "NULL" &&
      need_weight !== "null" &&
      need_weight !== "undefined"
    ) {
      if (need_weight > 1000) need_weight = 1000;
      if (need_weight < 200) need_weight = 200;
      console.log("验证码显示区域宽度：", need_weight);
    }

    let response;

    if (
      need_weight !== "" &&
      need_weight !== "NULL" &&
      need_weight !== "null" &&
      need_weight !== "undefined"
    ) {
      response = await fetch(
        `/api/captcha/history?${params}&weight=${need_weight}`,
        {
          headers: { "X-Session-ID": sessionUUID },
        },
      );
    } else {
      response = await fetch(`/api/captcha/history?${params}`, {
        headers: { "X-Session-ID": sessionUUID },
      });
    }

    const result = await response.json();
    if (!result.success) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      return;
    }
    const records = result.data || [];
    const total = records.length;
    const success = records.filter(
      (r) => r.status === "verified_success",
    ).length;
    const failed = records.filter((r) => r.status === "verified_failed").length;
    const pending = records.filter((r) => r.status === "created").length;
    const expired = records.filter((r) => r.status === "expired").length;
    const testGenerated = records.filter(
      (r) => r.status === "test_generated",
    ).length;
    const statTotal = $("captcha-stat-total");
    const statSuccess = $("captcha-stat-success");
    const statFailed = $("captcha-stat-failed");
    const statPending = $("captcha-stat-pending");
    const statExpired = $("captcha-stat-expired");
    const statTestGenerated = $("captcha-stat-test");
    if (statTotal) statTotal.textContent = total;
    if (statSuccess) statSuccess.textContent = success;
    if (statFailed) statFailed.textContent = failed;
    if (statPending) statPending.textContent = pending;
    if (statExpired) statExpired.textContent = expired;
    if (statTestGenerated) statTestGenerated.textContent = testGenerated;
    if (records.length === 0) {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10">该日期没有验证码记录</p>';
      return;
    }
    listContainer.innerHTML = "";
    // 遍历所有验证码记录并渲染到列表中
    records.forEach((record) => {
      // 根据验证状态设置不同的背景色和文字颜色
      const statusClass =
        {
          created: "bg-yellow-100 text-yellow-800", // 待验证 - 黄色
          verified_success: "bg-green-100 text-green-800", // 成功 - 绿色
          verified_failed: "bg-red-100 text-red-800", // 失败 - 红色
          expired: "bg-gray-100 text-gray-800", // 过期 - 灰色
        }[record.status] || "bg-gray-100 text-gray-800";
      // 根据验证状态设置显示的中文文本
      const statusText =
        {
          created: "待验证",
          verified_success: "验证成功",
          verified_failed: "验证失败",
          expired: "已过期",
          test_generated: "测试生成",
        }[record.status] || record.status;
      const captchaCode = getCaptchaHistoryDisplayText(record);
      // 创建列表项元素
      const itemDiv = document.createElement("div");
      itemDiv.className =
        "p-3 bg-white border border-slate-200 rounded-lg hover:shadow-md transition-shadow mb-2";
      itemDiv.innerHTML = `
      <div class="flex justify-between items-start mb-2">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-mono text-sm text-slate-600">ID: ${
              record.captcha_id ? record.captcha_id : "N/A"
            }</span>
            <span class="px-2 py-0.5 text-xs rounded ${statusClass}">${statusText}</span>
          </div>
          <div class="text-xs text-slate-500 space-y-0.5">
            <div>验证码: <span class="font-semibold text-slate-700 ${
              isBehaviorCaptchaRecord(record) ? "" : "font-mono"
            }">${captchaCode}</span></div>
            <div>创建时间: ${
              record.timestamp_readable ||
              new Date(record.timestamp * 1000).toLocaleString("zh-CN")
            }</div>
            ${
              record.verified_at_readable
                ? `<div>验证时间: ${record.verified_at_readable}</div>`
                : ""
            }
            ${
              record.verified_input
                ? `<div>用户输入: <span class="${
                    record.status === "verified_success"
                      ? "text-green-600"
                      : "text-red-600"
                  } font-semibold">${record.verified_input}</span></div>`
                : ""
            }
            <div>客户端IP: ${record.client_ip || "N/A"}</div>
          </div>
        </div>
        <button onclick="showCaptchaDetail(${escapeInlineJsArg(record.captcha_id)})"
          class="text-sm text-blue-600 hover:text-blue-800 ml-2 bg-blue-50 px-2 py-1 rounded">
          详情
        </button>
      </div>
      ${
        !isBehaviorCaptchaRecord(record) && record.html
          ? `
        <div class="mt-2 pt-2 border-t border-slate-100">
          <div class="text-xs text-slate-500 mb-1">验证码图片:</div>
          <div class="flex items-center justify-center bg-slate-50 p-2 rounded overflow-hidden">
            <div class="scale-75 origin-center">${record.html}</div>
          </div>
        </div>
      `
          : ""
      }
    `;
      listContainer.appendChild(itemDiv);
    });

    console.log(`[验证码历史] 已加载 ${records.length} 条记录`);
  } catch (e) {
    console.error("[验证码历史] 加载失败:", e);
    listContainer.innerHTML = `<p class="text-red-500 text-center py-10">加载验证码历史时发生错误: ${e.message}</p>`;
  }
}
function showCaptchaDetail(captchaId) {
    console.log("显示验证码详情，已收到验证码标识:", Boolean(captchaId));
  fetch(`/api/captcha/detail/${captchaId}`, {
    headers: {
      "X-Session-ID": sessionUUID,
    },
  })
    .then((response) => response.json())
    .then((result) => {
      if (result.success && result.data) {
        const captcha = result.data;
        if (captcha) {
          populateCaptchaDetailModal(captcha);
          const modal = $("captcha-detail-modal");
          if (modal) {
            modal.classList.remove("hidden");
            document.body.classList.add("modal-visible");
          }
        } else {
          showModalAlert("未找到该验证码的详细信息");
        }
      } else {
        showModalAlert("获取验证码详情失败：" + (result.message || "未知错误"));
      }
    })
    .catch((error) => {
      console.error("[验证码详情] 获取失败:", error);
      showModalAlert("获取验证码详情时发生错误：" + error.message);
    });
}
function populateCaptchaDetailModal(captcha) {
  $("detail-captcha-id").textContent = captcha.captcha_id || "-";
  $("detail-code").textContent = getCaptchaHistoryDisplayText(captcha);
  const statusElement = $("detail-status");
  const statusConfig = {
    created: { text: "待验证", class: "bg-yellow-100 text-yellow-800" },
    verified_success: {
      text: "验证成功",
      class: "bg-green-100 text-green-800",
    },
    verified_failed: {
      text: "验证失败",
      class: "bg-red-100 text-red-800",
    },
    expired: { text: "已过期", class: "bg-gray-100 text-gray-800" },
    test_generated: {
      text: "测试生成",
      class: "bg-blue-100 text-blue-800",
    },
  };
  const statusInfo = statusConfig[captcha.status] || {
    text: captcha.status,
    class: "bg-gray-100 text-gray-800",
  };
  statusElement.textContent = statusInfo.text;
  statusElement.className = `px-2 py-1 text-xs rounded ${statusInfo.class}`;
  $("detail-created-time").textContent =
    captcha.timestamp_readable ||
    new Date(captcha.timestamp * 1000).toLocaleString("zh-CN");
  const verifiedTimeContainer = $("detail-verified-time-container");
  if (captcha.verified_at_readable) {
    $("detail-verified-time").textContent = captcha.verified_at_readable;
    verifiedTimeContainer.classList.remove("hidden");
  } else {
    verifiedTimeContainer.classList.add("hidden");
  }
  const expiredTimeContainer = $("detail-expired-time-container");
  if (captcha.expired_at_readable) {
    $("detail-expired-time").textContent = captcha.expired_at_readable;
    expiredTimeContainer.classList.remove("hidden");
  } else {
    expiredTimeContainer.classList.add("hidden");
  }
  const verificationCard = $("detail-verification-card");
  if (captcha.verified_input) {
    $("detail-user-input").textContent = captcha.verified_input;
    $("detail-user-input").className =
      captcha.status === "verified_success"
        ? "font-mono font-bold text-green-600"
        : "font-mono font-bold text-red-600";
    const resultText =
      captcha.status === "verified_success" ? "✅ 验证成功" : "❌ 验证失败";
    const resultClass =
      captcha.status === "verified_success"
        ? "text-green-600 font-semibold"
        : "text-red-600 font-semibold";
    $("detail-verification-result").textContent = resultText;
    $("detail-verification-result").className = resultClass;

    verificationCard.classList.remove("hidden");
  } else {
    verificationCard.classList.add("hidden");
  }
  $("detail-client-ip").textContent = captcha.client_ip || "N/A";
  $("detail-user-agent").textContent = captcha.user_agent || "N/A";
  const imageCard = $("detail-captcha-image-card");
  const htmlContainer = $("detail-captcha-html");
  if (!isBehaviorCaptchaRecord(captcha) && captcha.html) {
    htmlContainer.innerHTML = captcha.html;
    imageCard.classList.remove("hidden");
  } else {
    htmlContainer.innerHTML = isBehaviorCaptchaRecord(captcha)
      ? '<p class="text-slate-400">使用验证码服务器</p>'
      : '<p class="text-slate-400">验证码图片不可用</p>';
    imageCard.classList.add("hidden");
  }
}

function closeCaptchaDetailModal() {
  const modal = $("captcha-detail-modal");
  if (modal) {
    modal.classList.add("hidden");
  }
}
function getInitialDataFailureNotice(response) {
  if (!response || response.success !== false) {
    return null;
  }
  if (response.stale_auth_response || response.suppressed) {
    return null;
  }

  const message = String(response.message || "").trim();
  if (!response.offline && !message) {
    return null;
  }

  return {
    title: response.offline ? "后端连接异常" : "初始化失败",
    text:
      message ||
      (response.offline
        ? "暂时无法连接到后端服务器，请刷新重试。如果问题依旧，请联系管理员。"
        : "初始化失败，请稍后重试。"),
    icon: response.offline ? "warning" : "error",
  };
}

async function hydrateInitialDataMapProviderSecrets(response, sessionId) {
  try {
    return await hydrateMapProviderSecretsForLegacy(response, sessionId);
  } catch (error) {
    logMessage_Warning(
      "[初始化] 地图密钥运行时加载失败，保留已认证的初始数据:",
      error,
    );
    return response;
  }
}

/**
 * 加载应用初始数据的统一函数（带限流机制）
 *
 * 功能：
 * 1. 调用后端 get_initial_data API
 * 2. 处理返回的用户列表、最后登录用户等信息
 * 3. 如果是超级管理员，自动更新密码恢复任务列表
 * 4. 如果在多账号模式，自动获取并更新所有账号状态
 * 5. 支持发送前端日志到后端
 * 6. 实现限流：0.5秒内只允许一次请求，重复请求返回缓存数据
 *
 * 参数：
 *   options (Object, 可选) - 配置选项：
 *     - frontend_logs (Array|Object): 要发送到后端的前端日志
 *     - force (Boolean): 是否强制请求（忽略限流，默认false）
 *
 * 返回值：
 *   Promise<Object> - 包含初始数据的对象
 */
let lastInitialDataContextKey = "";
async function loadInitialData(options = {}) {
  // 使用try-catch块进行错误处理，这是异步函数的最佳实践
  try {
    // ====================================================================
    // 步骤1：限流检查
    // ====================================================================

    // 获取当前时间戳（毫秒）
    const now = Date.now();
    const initialDataSessionUUID = getApiRequestSessionHeaderValue("get_initial_data");
    const businessContext = captureLegacyBusinessContext();
    const initialDataOriginUUID = getAdminViewOriginSessionUUID(initialDataSessionUUID);
    const initialDataContextKey = `${initialDataSessionUUID}|${initialDataOriginUUID}`;

    // 计算距离上次请求的时间间隔
    const timeSinceLastRequest = now - lastInitialDataRequest;

    // 检查是否需要应用限流
    // 如果不是强制请求，且距离上次请求时间小于限流时间，且有缓存数据
    if (
      !options.force &&
      timeSinceLastRequest < INITIAL_DATA_RATE_LIMIT &&
      lastInitialDataContextKey === initialDataContextKey &&
      lastInitialDataResponse
    ) {
      // 记录日志：请求被限流
      console.log(
        `[初始化] 请求被限流，返回缓存数据（距上次请求 ${timeSinceLastRequest}ms）`,
      );

      // 直接返回缓存的响应数据
      // 这样可以减少对后端的压力，提高响应速度
      syncMapProviderConfigFromInitialData(lastInitialDataResponse);
      return lastInitialDataResponse;
    }

    // ====================================================================
    // 步骤2：准备API调用参数
    // ====================================================================

    // 构建传递给后端的参数对象
    const params = {};

    // 如果提供了前端日志，添加到参数中
    if (options.frontend_logs) {
      params.frontend_logs = options.frontend_logs;
      console.log(
        "[初始化] 携带前端日志数据，数量:",
        Array.isArray(options.frontend_logs) ? options.frontend_logs.length : 1,
      );
    }

    // ====================================================================
    // 步骤3：调用后端API获取初始数据
    // ====================================================================

    // 更新最后请求时间戳
    lastInitialDataRequest = now;

    // 使用await关键字等待callPythonAPI的Promise完成
    // callPythonAPI是应用中已存在的函数，负责与Python后端通信
    // "get_initial_data"是API端点的标识符，后端会据此返回相应数据
    let response = await callPythonAPI("get_initial_data", params);
    response = await hydrateInitialDataMapProviderSecrets(
      response,
      initialDataSessionUUID,
    );
    if (
      initialDataSessionUUID !== getApiRequestSessionHeaderValue("get_initial_data") ||
      !isCurrentLegacyBusinessContext(businessContext) ||
      initialDataOriginUUID !== getAdminViewOriginSessionUUID(initialDataSessionUUID)
    ) {
      throw new Error("会话已切换，已忽略旧会话响应");
    }

    // 此时response已包含后端返回的完整数据对象
    // 如果API调用失败，callPythonAPI可能会抛出异常，会被catch块捕获

    // ====================================================================
    // 步骤4：缓存响应数据
    // ====================================================================

    // 将响应数据缓存起来，供下次限流时使用
    lastInitialDataResponse = response;
    lastInitialDataContextKey = initialDataContextKey;
    syncMapProviderConfigFromInitialData(response);

    // ====================================================================
    // 步骤5：检查响应的有效性和成功状态
    // ====================================================================

    const notice = getInitialDataFailureNotice(response);
    if (notice) {
      Swal.fire({
        title: notice.title,
        text: notice.text,
        icon: notice.icon,
        confirmButtonText: "确定",
      });
    }

    if (response && response.success) {
      // response对象存在且表示操作成功

      // ================================================================
      // 步骤6：处理密码恢复任务列表（仅超级管理员）
      // ================================================================

      // 条件判断：检查response中是否存在bruteforce_task_list字段
      // 这个字段只有在以下情况下才会存在：
      //   1. 当前登录用户是超级管理员
      //   2. 后端配置了密码恢复功能
      //   3. 存在正在进行或已完成的密码恢复任务
      if (response.bruteforce_task_list) {
        // 如果存在任务列表数据，说明当前用户有权限查看

        // 调用 updateBruteforceTaskList 函数更新UI
        // 将后端返回的任务数组传递给该函数进行渲染
        // 这个调用是自动的、透明的，调用loadInitialData的代码
        // 无需关心任务列表的更新，实现了关注点分离
        updateBruteforceTaskList(response.bruteforce_task_list);

        // 日志记录：帮助开发者调试，了解任务列表更新的触发情况
        console.log(
          "[初始化] 已自动更新密码恢复任务列表，任务数量:",
          response.bruteforce_task_list.length,
        );
      }
      // 如果bruteforce_task_list不存在，说明：
      //   - 当前用户不是超级管理员，或
      //   - 没有任何密码恢复任务
      // 这种情况下不执行任何操作，保持界面原样

      // ================================================================
      // 步骤7：处理多账号模式的账号状态（如果在多账号模式）
      // ================================================================

      // 检查是否返回了accounts字段（多账号状态信息）
      if (response.accounts && Array.isArray(response.accounts)) {
        // 如果存在accounts数据，说明当前用户在多账号模式

        // 日志记录：记录获取到的账号数量
        console.log(
          "[初始化] 已自动获取多账号状态，账号数量:",
          response.accounts.length,
        );

        // 注意：accounts数据已经在response中
        // 调用方可以直接从response.accounts中提取并使用
        // 这里不需要额外处理，因为调用方会处理这些数据
      }

      if (response.auth_group) {
        logMessage_Info("[初始化] 获取到用户权限组:", response.auth_group);
        if (
          currentUserData.auth_group !== response.auth_group ||
          currentUserData.group !== response.auth_group
        ) {
          currentUserData.auth_group = response.auth_group;
          currentUserData.group = response.auth_group;
          console.log("[初始化] 用户权限组已更新为:", response.auth_group);
        }
      }
    }

    // ====================================================================
    // 步骤8：返回完整的响应对象
    // ====================================================================

  logMessage_Info("[初始化] 初始数据加载完成");

    // 将response返回给调用者
    // 调用者可以从中提取需要的数据（如用户列表、权限信息等）
    // 注意：即使response.success为false，我们仍然返回它
    // 让调用者自行决定如何处理失败情况（更灵活的设计）
    return response;
  } catch (error) {
    // ====================================================================
    // 错误处理块：捕获任何在try块中发生的异常
    // ====================================================================

    // 可能的错误来源：
    //   1. callPythonAPI内部的网络错误（如超时、连接失败）
    //   2. 后端返回的非预期响应格式导致的解析错误
    //   3. updateBruteforceTaskList中的DOM操作错误（较少见）

    // 使用console.error输出错误到浏览器控制台
    // '[初始化]' 前缀便于在控制台中过滤和定位相关日志
    // error对象包含完整的错误堆栈信息，有助于调试
    console.error("[初始化] 加载初始数据失败:", error);

    // 重新抛出错误（re-throw）
    // 这样做的目的是让调用者也能感知到错误的发生
    // 调用者可以决定如何响应错误：
    //   - 显示错误提示给用户
    //   - 重试加载
    //   - 回退到默认状态
    //   - 记录错误日志到服务器
    throw error;

    // 注意：如果不re-throw，调用者会认为函数成功执行（返回undefined）
    // 这会导致错误被静默吞噬，难以发现和调试问题
  }

  // 函数结束
  // 正常情况下，执行流程会在return response处结束
  // 错误情况下，会在throw error处结束
}

// ============================================================================
// 彩虹易支付系统 - 前端JavaScript实现
// ============================================================================
// 本模块实现了彩虹易支付系统的所有前端交互功能
// 包括：创建订单、查询状态、订单列表管理、支付配置、日志查看等
// 所有函数都有详细的中文注释，便于理解和维护
// ============================================================================

// ========================================
// 全局变量定义区域
// ========================================

// 订单轮询定时器：用于定时查询订单支付状态
// 当用户创建订单后，会启动定时器每3秒查询一次订单状态
// 支付成功或超时后会自动清除定时器
let paymentPollingTimer = null;

// 订单轮询计数器：记录已经轮询的次数
// 最多轮询20次（约1分钟），避免无限轮询浪费资源
let paymentPollingCount = 0;

// 订单列表当前页码：用于分页显示订单列表
// 默认从第1页开始，点击"下一页"/"上一页"会更新此值
let currentOrdersPage = 1;

// 订单列表每页显示数量：控制每页显示多少条订单
// 设置为10条，既不会太多导致加载慢，也不会太少需要频繁翻页
let ordersPerPage = 10;

// 当前筛选的订单状态：用于过滤订单列表
// 可选值：'all'（全部）、'pending'（待支付）、'paid'（已支付）、'closed'（已关闭）
let currentOrderStatus = "all";

// ========================================
// 打开支付弹窗函数
// ========================================
/**
 * 打开支付弹窗，让用户输入支付金额和选择支付方式
 *
 * 功能说明：
 * 1. 显示支付弹窗（payment-modal）
 * 2. 从后端加载启用的支付方式并动态显示
 * 3. 重置表单到初始状态
 *
 * 调用时机：
 * - 用户点击个人中心的"在线支付"按钮时
 * - 用户点击订单列表中的"继续支付"按钮时
 *
 * @returns {void} 无返回值
 */
async function loadAdminBillingList(usernameOverride = null) {
  const container = document.getElementById("admin-billing-list-container");
  const schoolInput = document.getElementById("admin-billing-school-input");
  const keywordInput = document.getElementById("admin-billing-search-input");
  if (!container) return;
  const schoolUsername =
    usernameOverride != null
      ? String(usernameOverride).trim()
      : schoolInput
        ? schoolInput.value.trim()
        : "";
  const keyword = keywordInput ? keywordInput.value.trim() : "";
  container.innerHTML = `
    <div class="flex items-center justify-center py-10 gap-3 text-slate-400">
      <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
      </svg>
      <span class="text-sm">加载中...</span>
    </div>`;
  try {
    const params = new URLSearchParams();
    if (schoolUsername) params.set("school_username", schoolUsername);
    if (keyword) params.set("keyword", keyword);
    params.set("page", "1");
    params.set("page_size", "50");
    const url = `/api/admin/billing/list?${params.toString()}`;
    const resp = await fetch(url, { headers: { "X-Session-ID": sessionUUID } });
    const data = await resp.json();
    if (!data.success) {
      container.innerHTML = `<div class="flex items-center gap-2 text-red-500 bg-red-50 border border-red-200 rounded-lg p-3 text-sm"><svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>加载失败：${data.message || "未知错误"}</span></div>`;
      return;
    }
    const records = data.records || [];
    const summary = data.summary || {};
    if (records.length === 0) {
      container.innerHTML = `<div class="flex flex-col items-center justify-center py-12 text-slate-400 gap-2"><svg class="w-10 h-10 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg><p class="text-sm">暂无账单记录</p><p class="text-xs text-slate-400">默认展示你有权限的学校账号账单</p></div>`;
      return;
    }
    const totalCount = Number(summary.total_count || 0);
    const paidCount = Number(summary.paid_count || 0);
    const pendingCount = Number(summary.pending_count || 0);
    const clearedCount = Number(summary.admin_cleared_count || 0);
    const totalAmount = Number(summary.total_amount || 0).toFixed(2);
    const paidAmount = Number(summary.paid_amount || 0).toFixed(2);
    const pendingAmount = Number(summary.pending_amount || 0).toFixed(2);
    const clearedAmount = Number(summary.admin_cleared_amount || 0).toFixed(2);
    const scopeTip = schoolUsername
      ? `当前筛选：学校账号 ${_escapeAttr(schoolUsername)}`
      : "当前范围：所有学校账号的全部账单";
    let html = `
      <div class="mb-3 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">${scopeTip}</div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div class="bg-slate-50 border border-slate-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-slate-700">${totalCount}</p>
          <p class="text-xs text-slate-500 mt-0.5">总记录数</p>
        </div>
        <div class="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-green-600">${paidCount}</p>
          <p class="text-xs text-green-600 mt-0.5">已支付</p>
        </div>
        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-amber-600">${pendingCount}</p>
          <p class="text-xs text-amber-600 mt-0.5">待支付</p>
        </div>
        <div class="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-cyan-600">${clearedCount}</p>
          <p class="text-xs text-cyan-600 mt-0.5">管理员清除</p>
        </div>
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-blue-600">¥${totalAmount}</p>
          <p class="text-xs text-blue-600 mt-0.5">总金额</p>
        </div>
        <div class="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-emerald-600">¥${paidAmount}</p>
          <p class="text-xs text-emerald-600 mt-0.5">已支付金额</p>
        </div>
        <div class="bg-orange-50 border border-orange-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-orange-600">¥${pendingAmount}</p>
          <p class="text-xs text-orange-600 mt-0.5">待支付金额</p>
        </div>
        <div class="bg-sky-50 border border-sky-200 rounded-lg p-3 text-center">
          <p class="text-2xl font-bold text-sky-600">¥${clearedAmount}</p>
          <p class="text-xs text-sky-600 mt-0.5">管理员清除金额</p>
        </div>
      </div>
      <div class="rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        <div class="overflow-x-auto">
          <table class="w-full text-xs" id="admin-billing-table">
            <thead>
              <tr class="bg-gradient-to-r from-slate-100 to-slate-50 text-slate-600">
                <th class="px-3 py-2.5 text-left font-semibold">学校账号</th>
                <th class="px-3 py-2.5 text-left font-semibold">姓名</th>
                <th class="px-3 py-2.5 text-left font-semibold">原因/描述</th>
                <th class="px-3 py-2.5 text-right font-semibold">金额</th>
                <th class="px-3 py-2.5 text-center font-semibold admin-status-th whitespace-nowrap">状态</th>
                <th class="px-3 py-2.5 text-left font-semibold">创建时间</th>
                <th class="px-3 py-2.5 text-left font-semibold">支付时间</th>
                <th class="px-3 py-2.5 text-center font-semibold whitespace-nowrap">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">`;
    records.forEach((r, idx) => {
      let statusBadge;
      if (r.status === "paid") {
        statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-green-500 font-medium">✓ 已支付</span>`;
      } else if (r.status === "admin_cleared") {
        statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-sky-500 font-medium">✓ 管理员清除</span>`;
      } else {
        statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white bg-amber-500 font-medium">⏳ 待支付</span>`;
      }
      const rowBg = idx % 2 === 0 ? "" : "bg-slate-50/60";
      const schoolName = _escapeAttr(r.school_name || "-");
      html += `<tr class="${rowBg} hover:bg-sky-50/40 transition-colors">
        <td class="px-3 py-2.5 text-slate-800 font-medium">${_escapeAttr(r.school_username || "-")}</td>
        <td class="px-3 py-2.5 text-slate-600">${schoolName}</td>
        <td class="px-3 py-2.5 text-slate-600">${_escapeAttr(r.reason || "-")}</td>
        <td class="px-3 py-2.5 text-right font-semibold ${r.status === "paid" ? "text-green-600" : "text-amber-600"}">${r.amount != null ? "¥" + _escapeAttr(r.amount) : "-"}</td>
        <td class="px-3 py-2.5 text-center admin-status-td whitespace-nowrap">${statusBadge}</td>
        <td class="px-3 py-2.5 text-slate-500">${_fmtBillTime(_getBillingTime(r, "created_at"))}</td>
        <td class="px-3 py-2.5 text-slate-500">${_fmtBillTime(_getBillingTime(r, "paid_at"))}</td>
        <td class="px-3 py-2.5 text-center">
          <div class="flex items-center justify-center gap-1.5">
            <button onclick='View_details_of_users_with_outstanding_payments(${escapeInlineJsonArg(r.school_username || "")})'
              class="px-2 py-1 text-xs bg-indigo-100 hover:bg-indigo-200 text-indigo-700 rounded-md border border-indigo-200 transition-colors whitespace-nowrap">🔍 查看详情</button>
            <button onclick='adminEditBilling(${escapeInlineJsonArg(r)})'
              class="px-2 py-1 text-xs bg-sky-100 hover:bg-sky-200 text-sky-700 rounded-md border border-sky-200 transition-colors whitespace-nowrap">✏️ 修改账单</button>
            <button onclick='adminDeleteBilling(${escapeInlineJsonArg(r.billing_id)},${escapeInlineJsonArg(r.school_username || "")})'
              class="px-2 py-1 text-xs bg-rose-100 hover:bg-rose-200 text-rose-700 rounded-md border border-rose-200 transition-colors whitespace-nowrap">🗑 删除</button>
          </div>
        </td>
      </tr>`;
    });
    html += `</tbody></table></div></div>`;
    if (clearedCount > 0) {
      html += `<p class="text-xs text-slate-400 mt-2 text-right">其中 ${clearedCount} 条已由管理员清除</p>`;
    }
    withMobileAdminUnifiedScrollGuard("billing", () => {
      container.innerHTML = html;
    }, { restoreMode: "replace" });
    (function () {
      const statusCells = container.querySelectorAll(
        ".admin-status-td, .admin-status-th",
      );
      if (!statusCells.length) return;
      const applyWrap = () => {
        const containerW = container.getBoundingClientRect().width;
        statusCells.forEach((c) => {
          c.style.whiteSpace = "nowrap";
        });
        const statusW = statusCells[0].getBoundingClientRect().width;
        const wrap = containerW > 0 && containerW < 5 * statusW;
        statusCells.forEach((c) => {
          c.style.whiteSpace = wrap ? "" : "nowrap";
        });
      };
      applyWrap();
      if (window.ResizeObserver) {
        const ro = new ResizeObserver(applyWrap);
        ro.observe(container);
      }
    })();
  } catch (e) {
    container.innerHTML = `<div class="flex items-center gap-2 text-red-500 bg-red-50 border border-red-200 rounded-lg p-3 text-sm"><svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg><span>加载异常：${e.message}</span></div>`;
  }
}

/**
 * 管理员加载已删除账号列表
 */
/**
 * 管理员编辑账单描述
 */
async function adminEditBilling(record) {
  const billingId = record && record.billing_id ? record.billing_id : "";
  const schoolUsername =
    record && record.school_username ? record.school_username : "";
  const currentReason = record && record.reason ? record.reason : "";
  const currentAmount =
    record && record.amount != null ? String(record.amount) : "";
  const currentStatus =
    record && record.status ? String(record.status) : "pending";

  const result = await Swal.fire({
    title: "修改账单",
    html: `
      <div style="text-align:left;padding:6px 0 2px;">
        <p style="color:#475569;font-size:13px;margin-bottom:6px;">
          账单 ID:
          <code style="
            font-size:12px;
            background:#f1f5f9;
            padding:2px 6px;
            border-radius:4px;
            color:#334155;
          ">${billingId}</code>
        </p>

        <p style="color:#475569;font-size:13px;margin-bottom:10px;">
          学校账号: <strong style="color:#0f172a;">${schoolUsername || "-"}</strong>
        </p>

        <label style="display:block;color:#475569;font-size:12px;margin:0 0 4px;">金额</label>
        <input
          id="swal-billing-amount"
          class="swal2-input"
          style="width:100%;margin:0 0 10px;box-sizing:border-box;height:38px;font-size:13px;padding:8px 10px;border-radius:6px;border:1px solid #cbd5e1;background:#f8fafc;color:#334155;outline:none;box-shadow:none !important;"
          value="${currentAmount}"
          placeholder="例如 1.00"
        />

        <label style="display:block;color:#475569;font-size:12px;margin:0 0 4px;">状态</label>
        <select
          id="swal-billing-status"
          class="swal2-input"
          style="width:100%;margin:0 0 10px;box-sizing:border-box;height:38px;font-size:13px;padding:8px 10px;border-radius:6px;border:1px solid #cbd5e1;background:#f8fafc;color:#334155;outline:none;box-shadow:none !important;"
        >
          <option value="pending" ${currentStatus === "pending" ? "selected" : ""}>待支付</option>
          <option value="paid" ${currentStatus === "paid" ? "selected" : ""}>已支付</option>
          <option value="admin_cleared" ${currentStatus === "admin_cleared" ? "selected" : ""}>管理员清除</option>
        </select>

        <label style="display:block;color:#475569;font-size:12px;margin:0 0 4px;">原因/描述</label>
        <textarea
          id="swal-billing-reason"
          rows="3"
          class="swal2-textarea"
          style="
            width:100%;
            margin:0;
            box-sizing:border-box;
            font-size:13px;
            padding:8px 10px;
            border-radius:6px;
            border:1px solid #cbd5e1;
            background:#f8fafc;
            color:#334155;
            resize: vertical;
            outline:none;
            box-shadow:none !important;
          "
        >${currentReason}</textarea>
      </div>
    `,
    icon: "info",
    showCancelButton: true,
    confirmButtonText: "保存",
    confirmButtonColor: "#2563eb",
    cancelButtonText: "取消",
    cancelButtonColor: "#64748b",
    customClass: {
      popup: "swal2-clean-popup",
      confirmButton: "swal2-clean-btn",
      cancelButton: "swal2-clean-btn",
    },
    reverseButtons: true,
    preConfirm: () => {
      const amount = document
        .getElementById("swal-billing-amount")
        .value.trim();
      const status = document.getElementById("swal-billing-status").value;
      const reason = document
        .getElementById("swal-billing-reason")
        .value.trim();
      if (!amount || Number.isNaN(Number(amount)) || Number(amount) <= 0) {
        Swal.showValidationMessage("请输入大于 0 的有效金额");
        return false;
      }
      return { amount, status, reason };
    },
  });

  if (!result.isConfirmed) return;
  try {
    const resp = await fetch("/api/admin/billing/update", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        billing_id: billingId,
        school_username: schoolUsername,
        reason: result.value.reason,
        amount: result.value.amount,
        status: result.value.status,
      }),
    });
    const data = await resp.json();
    if (data.success) {
      await Swal.fire({
        title: "保存成功",
        text: "账单已更新",
        icon: "success",

        timer: undefined,
        timerProgressBar: false,

        showConfirmButton: true,
        confirmButtonText: "关闭",

        buttonsStyling: false, // 禁用默认按钮样式
        customClass: {
          popup: "swal-flat-popup",
          confirmButton: "swal-flat-button",
        },
      });

      await loadAdminBillingList();
      loadMobileMultiAdminBillingList();
    } else {
      await Swal.fire({
        title: "保存失败",
        text: data.message || "未知错误",
        icon: "error",
        confirmButtonText: "确定",
        confirmButtonColor: "#dc2626",
        customClass: { popup: "swal2-neumorphism-popup" },
      });
    }
  } catch (e) {
    await Swal.fire({
      title: "请求异常",
      text: e.message,
      icon: "error",
      confirmButtonText: "确定",
      confirmButtonColor: "#dc2626",
      customClass: { popup: "swal2-neumorphism-popup" },
    });
  }
}

async function adminDeleteBilling(billingId, schoolUsername) {
  const result = await Swal.fire({
    title: "确认删除账单？",
    html: `
      <div style="text-align:left;font-size:13px;color:#475569;line-height:1.7;">
        <p>账单 ID：<code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;color:#334155;">${billingId}</code></p>
        <p>学校账号：<strong style="color:#0f172a;">${schoolUsername || "-"}</strong></p>
        <!-- <p style="margin-top:6px;color:#b45309;">删除后不会直接销毁，而是移动到 <code style="background:#fef3c7;padding:2px 6px;border-radius:4px;">./User_Billing/Reomve/</code> 目录。</p> -->
      </div>
    `,
    icon: "warning",
    showCancelButton: true,
    confirmButtonText: "确认删除",
    cancelButtonText: "取消",
    confirmButtonColor: "#dc2626",
    cancelButtonColor: "#64748b",
    reverseButtons: true,
    customClass: {
      popup: "swal2-clean-popup",
      confirmButton: "swal2-clean-btn",
      cancelButton: "swal2-clean-btn",
    },
  });

  if (!result.isConfirmed) return;
  try {
    const resp = await fetch("/api/admin/billing/delete", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        billing_id: billingId,
        school_username: schoolUsername,
      }),
    });
    const data = await resp.json();
    if (data.success) {
      await Swal.fire({
        title: "删除成功",
        text: data.message || "账单已删除",
        icon: "success",
        confirmButtonText: "确定",
        confirmButtonColor: "#16a34a",
      });
      await loadAdminBillingList();
      loadMobileMultiAdminBillingList();
    } else {
      await Swal.fire({
        title: "删除失败",
        text: data.message || "未知错误",
        icon: "error",
        confirmButtonText: "确定",
        confirmButtonColor: "#dc2626",
      });
    }
  } catch (e) {
    await Swal.fire({
      title: "请求异常",
      text: e.message,
      icon: "error",
      confirmButtonText: "确定",
      confirmButtonColor: "#dc2626",
    });
  }
}

/**
 * 管理员添加账单对话框
 * 支持两种模式：次数模式（count）和金额模式（amount）
 * 原因为空时服务器自动生成
 */
async function adminAddBillingDialog() {
  const { value: formValues, isConfirmed } = await Swal.fire({
    title: "添加账单",
    html: `
      <div style="text-align:left;font-size:13px;color:#374151;">
        <div style="margin-bottom:10px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;color:#111827;">学校账号 <span style="color:#ef4444;">*</span></label>
          <input id="swal-add-billing-school" class="swal2-input" style="margin:0;width:100%;box-sizing:border-box;" placeholder="school_username（学校学号/账号）">
        </div>
        <div style="margin-bottom:10px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;color:#111827;">计费方式</label>
          <div style="display:flex;gap:8px;">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
              <input type="radio" name="swal-billing-mode" value="count" checked onchange="document.getElementById('swal-billing-count-row').style.display='';document.getElementById('swal-billing-amount-row').style.display='none';">
              按次数（默认）
            </label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;">
              <input type="radio" name="swal-billing-mode" value="amount" onchange="document.getElementById('swal-billing-count-row').style.display='none';document.getElementById('swal-billing-amount-row').style.display='';">
              按金额
            </label>
          </div>
        </div>
        <div id="swal-billing-count-row" style="margin-bottom:10px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;color:#111827;">欠费次数</label>
          <input id="swal-add-billing-count" class="swal2-input" style="margin:0;width:100%;box-sizing:border-box;" type="number" min="1" value="1" placeholder="次数">
        </div>
        <div id="swal-billing-amount-row" style="display:none;margin-bottom:10px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;color:#111827;">自定义金额（元）</label>
          <input id="swal-add-billing-amount" class="swal2-input" style="margin:0;width:100%;box-sizing:border-box;" type="number" min="0.01" step="0.01" placeholder="如 5.00">
        </div>
        <div style="margin-bottom:4px;">
          <label style="display:block;font-weight:600;margin-bottom:4px;color:#111827;">原因/描述 <span style="color:#9ca3af;font-weight:400;">（留空自动生成）</span></label>
          <input id="swal-add-billing-reason" class="swal2-input" style="margin:0;width:100%;box-sizing:border-box;" placeholder="如：手动补录欠费">
        </div>
      </div>
    `,
    icon: "info",
    showCancelButton: true,
    confirmButtonText: "创建账单",
    confirmButtonColor: "#2563eb",
    cancelButtonText: "取消",
    cancelButtonColor: "#64748b",
    reverseButtons: true,
    preConfirm: () => {
      const school = document
        .getElementById("swal-add-billing-school")
        .value.trim();
      const mode = document.querySelector(
        'input[name="swal-billing-mode"]:checked',
      ).value;
      const count = document
        .getElementById("swal-add-billing-count")
        .value.trim();
      const amount = document
        .getElementById("swal-add-billing-amount")
        .value.trim();
      const reason = document
        .getElementById("swal-add-billing-reason")
        .value.trim();
      if (!school) {
        Swal.showValidationMessage("请填写学校账号");
        return false;
      }
      if (mode === "count" && (!count || parseInt(count) < 1)) {
        Swal.showValidationMessage("次数必须大于 0");
        return false;
      }
      if (mode === "amount" && (!amount || parseFloat(amount) <= 0)) {
        Swal.showValidationMessage("金额必须大于 0");
        return false;
      }
      return {
        school,
        mode,
        count: parseInt(count) || 1,
        amount: parseFloat(amount) || 0,
        reason,
      };
    },
  });

  if (!isConfirmed || !formValues) return;

  try {
    const body = {
      school_username: formValues.school,
      mode: formValues.mode,
      reason: formValues.reason,
    };
    if (formValues.mode === "count") body.count = formValues.count;
    else body.amount = formValues.amount;

    const resp = await fetch("/api/admin/billing/add", {
      method: "POST",
      headers: {
        "X-Session-ID": sessionUUID,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (data.success) {
      await Swal.fire({
        title: "账单已创建",
        html: `<p style="color:#374151;font-size:14px;">账单 ID：<code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;">${data.billing_id}</code></p><p style="margin-top:6px;color:#16a34a;font-weight:600;">金额：¥${data.amount}</p>`,
        icon: "success",
        confirmButtonText: "确定",
        confirmButtonColor: "#2563eb",
      });
      await loadAdminBillingList();
    } else {
      await Swal.fire({
        title: "创建失败",
        text: data.message || "未知错误",
        icon: "error",
        confirmButtonText: "确定",
        confirmButtonColor: "#dc2626",
      });
    }
  } catch (e) {
    await Swal.fire({
      title: "请求异常",
      text: e.message,
      icon: "error",
      confirmButtonText: "确定",
      confirmButtonColor: "#dc2626",
    });
  }
}

async function loadRemovedAccountsList() {
  const container = document.getElementById("removed-accounts-list-container");
  if (!container) return;
  container.innerHTML = '<p class="text-xs text-slate-400">加载中...</p>';
  try {
    const resp = await fetch("/api/admin/removed_accounts", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    if (!data.success) {
      container.innerHTML =
        '<p class="text-xs text-red-500">加载失败: ' +
        (data.message || "未知错误") +
        "</p>";
      return;
    }
    const accounts = data.removed_accounts || {};
    const keys = Object.keys(accounts);
    if (keys.length === 0) {
      container.innerHTML =
        '<p class="text-slate-700 text-sm">暂无已删除账号记录</p>';
      return;
    }
    let html = '<div class="space-y-3">';
    keys.forEach((username) => {
      const entry = accounts[username];
      const avatarRaw = String(entry?.avatar_url || "default_avatar.png");
      const avatarUrl = avatarRaw.startsWith("/api/avatar/")
        ? `${avatarRaw}${avatarRaw.includes("?") ? "&" : "?"}session_id=${encodeURIComponent(sessionUUID)}&t=${Date.now()}`
        : "/default_avatar.png";
      const nickname = _escapeAttr(entry?.nickname || username);
      const phoneText = _escapeAttr(entry?.phone || "未绑定");
      const createdAtText = _escapeAttr(_formatUnixOrIsoTime(entry?.created_at));
      const lastLoginText = _escapeAttr(_formatUnixOrIsoTime(entry?.last_login));
      const loginIpText = _escapeAttr(entry?.last_login_ip || "无记录");
      const loginCityText = _escapeAttr(entry?.last_login_city || "未知");
      const maxSessions =
        Number(entry?.max_sessions) === -1
          ? "无限制"
          : `${Number(entry?.max_sessions || 1)}个`;
      const availableRunsNum = Number(entry?.available_runs ?? 0);
      const availableRunsText =
        availableRunsNum === -1 ? "无限制" : `${availableRunsNum}次`;
      const tfaEnabled = !!entry?.["2fa_enabled"];
      const safeDeletedAt = _escapeAttr(entry?.deleted_at || "-");
      html += `
        <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden hover:shadow-md transition-shadow">
          <div class="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
              <img src="${_escapeAttr(avatarUrl)}" class="w-11 h-11 rounded-full object-cover border-2 border-white shadow-sm ring-1 ring-slate-200" onerror="this.onerror=null;this.src='/default_avatar.png';">
              <div class="min-w-0">
                <div class="font-mono text-xs text-slate-800 break-all">用户名: ${_escapeAttr(username)}</div>
                <div class="text-[11px] text-slate-500 truncate">昵称: ${nickname}</div>
              </div>
            </div>
            <div class="text-right shrink-0">
              <div class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-rose-50 text-rose-600 border border-rose-200">已删除</div>
              <div class="text-[11px] text-slate-700 mt-1">删除时间: ${safeDeletedAt}</div>
            </div>
          </div>
          <div class="px-4 py-3">
            <div class="grid grid-cols-2 xl:grid-cols-4 gap-2 text-[11px] mb-3">
              <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2"><div class="text-slate-500">手机号</div><div class="text-slate-700 mt-0.5 break-all">${phoneText}<span class="phone-location-badge text-[11px] text-slate-400 ml-1" data-phone="${_escapeAttr(entry?.phone || "")}"></span></div></div>
              <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2"><div class="text-slate-500">创建时间</div><div class="text-slate-700 mt-0.5 break-all">${createdAtText}</div></div>
              <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2"><div class="text-slate-500">最后登录</div><div class="text-slate-700 mt-0.5 break-all">${lastLoginText}</div></div>
              <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-2"><div class="text-slate-500">登录IP</div><div class="text-slate-700 mt-0.5 break-all">${loginIpText} (${loginCityText})</div></div>
            </div>
            <div class="flex flex-wrap items-center gap-2 mb-3">
              <span class="px-2 py-1 rounded-lg bg-slate-100 text-slate-600 text-[11px] border border-slate-200">会话限制: ${_escapeAttr(maxSessions)}</span>
              <span class="px-2 py-1 rounded-lg bg-slate-100 text-slate-600 text-[11px] border border-slate-200">可用次数: ${_escapeAttr(availableRunsText)}</span>
              <span class="px-2 py-1 rounded-lg text-[11px] border ${tfaEnabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-400 border-slate-200"}">2FA: ${tfaEnabled ? "已启用" : "未启用"}</span>
            </div>
            <div class="flex items-center justify-end gap-2">
              <button class="px-2.5 py-1 text-[11px] font-medium bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg border border-indigo-200 transition-colors" onclick='showRemovedAccountDetail(${escapeInlineJsonArg(username)})'>查看详情</button>
              <button class="px-2.5 py-1 text-[11px] font-medium bg-amber-50 hover:bg-amber-100 text-amber-700 rounded-lg border border-amber-200 transition-colors" onclick='restoreAccount(${escapeInlineJsonArg(username)})'>恢复</button>
            </div>
          </div>
        </div>`;
    });
    html += "</div>";
    container.innerHTML = html;
    container.querySelectorAll(".phone-location-badge[data-phone]").forEach(async (span) => {
      const info = await fetchPhoneInfo(span.dataset.phone);
      if (info) { const p = [info.province, info.city, info.sp].filter(Boolean); if (p.length) span.textContent = `(${p.join(" ")})`; }
    });
  } catch (e) {
    container.innerHTML =
      '<p class="text-slate-700 text-red-500">加载异常: ' + e.message + "</p>";
  }
}

async function loadMobileMultiAdminBillingList() {
  captureMobileAdminUnifiedScrollState("billing");
  const schoolInput = document.getElementById(
    "mobile-multi-admin-billing-school-input",
  );
  const keywordInput = document.getElementById(
    "mobile-multi-admin-billing-search-input",
  );
  const schoolUsername = schoolInput ? schoolInput.value.trim() : "";
  const keyword = keywordInput ? keywordInput.value.trim() : "";
  const container = document.getElementById("mobile-multi-admin-billing-list");
  if (!container) return;
  container.innerHTML = `
    <div class="flex flex-col items-center justify-center py-8 text-slate-400 gap-2">
      <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
      </svg>
      <p class="text-xs">加载中...</p>
    </div>`;
  try {
    const params = [];
    if (schoolUsername) {
      params.push(
        `school_username=${encodeURIComponent(schoolUsername)}`,
      );
    }
    if (keyword) {
      params.push(`keyword=${encodeURIComponent(keyword)}`);
    }
    params.push("page=1");
    params.push("page_size=50");
    const url = `/api/admin/billing/list?${params.join("&")}`;
    const resp = await fetch(url, { headers: { "X-Session-ID": sessionUUID } });
    const data = await resp.json();
    if (!data.success) {
      container.innerHTML = `<p class="text-xs text-red-500">加载失败：${_escapeAttr(data.message || "未知错误")}</p>`;
      return;
    }
    const records = data.records || [];
    const summary = data.summary || {};
    const billingStats = {
      total: Number(summary.total_count || 0),
      pending: Number(summary.pending_count || 0),
      paid: Number(summary.paid_count || 0),
      admin_cleared: Number(summary.admin_cleared_count || 0),
      total_amount: Number(summary.total_amount || 0),
      pending_amount: Number(summary.pending_amount || 0),
      paid_amount: Number(summary.paid_amount || 0),
      admin_cleared_amount: Number(summary.admin_cleared_amount || 0),
    };
    const scopeTip = schoolUsername
      ? `当前筛选：学校账号 ${_escapeAttr(schoolUsername)}`
      : "当前范围：所有学校账号的全部账单";
    const keywordTip = keyword
      ? `关键词：${_escapeAttr(keyword)}`
      : "关键词：未设置";
    let html = `<div class="mb-2 text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1.5">${scopeTip}<br>${keywordTip}</div>`;
    html += `<div class="grid grid-cols-2 gap-2 mb-2">
      <div class="bg-slate-50 border border-slate-200 rounded-lg px-2 py-1.5 text-slate-700">总账单：${_escapeAttr(String(billingStats.total))}</div>
      <div class="bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 text-amber-700">待支付：${_escapeAttr(String(billingStats.pending))}</div>
      <div class="bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-1.5 text-emerald-700">已支付：${_escapeAttr(String(billingStats.paid))}</div>
      <div class="bg-sky-50 border border-sky-200 rounded-lg px-2 py-1.5 text-sky-700">已清除：${_escapeAttr(String(billingStats.admin_cleared))}</div>
      <div class="bg-indigo-50 border border-indigo-200 rounded-lg px-2 py-1.5 text-indigo-700">总金额：¥${_escapeAttr(String(Number(billingStats.total_amount).toFixed(2)))}</div>
      <div class="bg-orange-50 border border-orange-200 rounded-lg px-2 py-1.5 text-orange-700">待支付金额：¥${_escapeAttr(String(Number(billingStats.pending_amount).toFixed(2)))}</div>
      <div class="bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-1.5 text-emerald-700">已支付金额：¥${_escapeAttr(String(Number(billingStats.paid_amount).toFixed(2)))}</div>
      <div class="bg-cyan-50 border border-cyan-200 rounded-lg px-2 py-1.5 text-cyan-700">管理员清除金额：¥${_escapeAttr(String(Number(billingStats.admin_cleared_amount).toFixed(2)))}</div>
    </div>`;
    html += `<div class="mb-2 flex items-center gap-1 justify-end">
      <button class="btn btn-ghost border border-slate-300 !py-0.5 !px-1.5 text-[11px]" onclick="loadMobileMultiAdminBillingList()">刷新</button>
    </div>`;
    if (!records.length) {
      html += `<div class="flex flex-col items-center justify-center py-8 text-slate-400 gap-1"><p class="text-xs">暂无账单记录</p></div>`;
      withMobileAdminUnifiedScrollGuard("billing", () => {
        container.innerHTML = html;
      }, { restoreMode: "replace" });
      return;
    }
    html += `<div class="space-y-3">`;
    records.forEach((r) => {
      const school = _escapeAttr(r.school_username || "-");
      const schoolName = _escapeAttr(r.school_name || "-");
      const reason = _escapeAttr(r.reason || "-");
      const amount = r.amount != null ? "¥" + _escapeAttr(r.amount) : "-";
      const timeRow =
        r.status === "paid"
          ? `<div class="text-[11px] text-slate-400">支付时间：${_escapeAttr(_fmtBillTime(_getBillingTime(r, "paid_at")))}</div>`
          : r.status === "admin_cleared"
            ? `<div class="text-[11px] text-slate-400">清除时间：${_escapeAttr(_fmtBillTime(_getBillingTime(r, "admin_cleared_at")))}</div>`
            : `<div class="text-[11px] text-slate-400">等待支付中…</div>`;
      html += `
        <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
          <!-- 顶栏：账号 + 状态徽章 -->
          <div class="flex items-center gap-2 px-3 py-2.5 bg-slate-50 border-b border-slate-200">
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
            <!-- 金额 + 创建时间 两列 -->
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
            <!-- 时间 + 操作按钮 -->
            <div class="flex items-center justify-between gap-2">
              ${timeRow}
              <div class="flex-shrink-0 flex items-center gap-1">
                <button class="px-2 py-1 text-[11px] font-medium bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg border border-indigo-200 transition-colors" onclick='View_details_of_users_with_outstanding_payments(${escapeInlineJsonArg(r.school_username || "")})'>详情</button>
                <button class="px-2 py-1 text-[11px] font-medium bg-sky-50 hover:bg-sky-100 text-sky-700 rounded-lg border border-sky-200 transition-colors" onclick='adminEditBilling(${escapeInlineJsonArg(r)})'>修改</button>
                <button class="px-2 py-1 text-[11px] font-medium bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg border border-rose-200 transition-colors" onclick='adminDeleteBilling(${escapeInlineJsonArg(r.billing_id)}, ${escapeInlineJsonArg(r.school_username || "")})'>删除</button>
              </div>
            </div>
          </div>
        </div>`;
    });
    html += `</div>`;
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="text-xs text-red-500">加载异常：${_escapeAttr(e.message)}</p>`;
  }
}

async function loadMobileMultiRemovedAccountsList() {
  const container = document.getElementById("mobile-multi-removed-accounts-list");
  if (!container) return;
  container.innerHTML = `
    <div class="flex flex-col items-center justify-center py-8 text-slate-400 gap-2">
      <svg class="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
      </svg>
      <p class="text-xs">加载中...</p>
    </div>`;
  try {
    const resp = await fetch("/api/admin/removed_accounts", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    if (!data.success) {
      container.innerHTML = `<p class="text-xs text-red-500">加载失败：${_escapeAttr(data.message || "未知错误")}</p>`;
      return;
    }
    const accounts = data.removed_accounts || {};
    const keys = Object.keys(accounts);
    if (!keys.length) {
      container.innerHTML = `<div class="flex flex-col items-center justify-center py-8 text-slate-400 gap-1"><p class="text-xs">暂无已删除账号记录</p></div>`;
      return;
    }
    let html = `<div class="mb-2 flex items-center gap-1 justify-start">
      <button class="btn btn-ghost border border-slate-300 !py-0.5 !px-1.5 text-[11px]" onclick="loadMobileMultiRemovedAccountsList()">刷新</button>
    </div><div class="space-y-2.5">`;
    keys.forEach((username) => {
      const entry = accounts[username] || {};
      const safeUsername = _escapeAttr(username);
      const safeDeletedAt = _escapeAttr(entry.deleted_at || "-");
      const safeNickname = _escapeAttr(entry.nickname || username);
      const safePhone = _escapeAttr(entry.phone || "未绑定");
      const safeCreatedAt = _escapeAttr(_formatUnixOrIsoTime(entry.created_at));
      const safeLastLogin = _escapeAttr(_formatUnixOrIsoTime(entry.last_login));
      const safeLoginIp = _escapeAttr(entry.last_login_ip || "无记录");
      const safeLoginCity = _escapeAttr(entry.last_login_city || "未知");
      const maxSessions =
        Number(entry.max_sessions) === -1
          ? "无限制"
          : `${Number(entry.max_sessions || 1)}个`;
      const availableRunsNum = Number(entry.available_runs ?? 0);
      const availableRunsText =
        availableRunsNum === -1 ? "无限制" : `${availableRunsNum}次`;
      const tfaEnabled = !!entry["2fa_enabled"];
      const avatarRaw = String(entry.avatar_url || "default_avatar.png");
      const avatarUrl = avatarRaw.startsWith("/api/avatar/")
        ? `${avatarRaw}${avatarRaw.includes("?") ? "&" : "?"}session_id=${encodeURIComponent(sessionUUID)}&t=${Date.now()}`
        : "/default_avatar.png";
      html += `
      <div class="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden active:scale-[0.998] transition-transform">
        <div class="px-3.5 py-3 bg-gradient-to-r from-slate-50 to-slate-100/80 border-b border-slate-200 text-left">
          <div class="flex items-start justify-start gap-2.5">
            <div class="flex items-center gap-2.5 min-w-0">
              <img src="${_escapeAttr(avatarUrl)}" class="w-11 h-11 rounded-full object-cover border-2 border-white shadow-sm ring-1 ring-slate-200" onerror="this.onerror=null;this.src='/default_avatar.png';">
              <div class="min-w-0">
                <div class="text-xs font-semibold text-slate-800 font-mono break-all">用户名: ${safeUsername}</div>
                <div class="text-[11px] text-slate-500 truncate">昵称: ${safeNickname}</div>
              </div>
            </div>
          </div>
          <div class="mt-2">
            <span class="inline-flex px-2.5 py-1 rounded-full text-[11px] font-medium bg-rose-50 text-rose-600 border border-rose-200">已删除</span>
          </div>
        </div>
        <div class="px-3.5 py-3">
          <div class="space-y-2 text-[12px] mb-2.5">
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 break-all">删除时间: ${safeDeletedAt}</div>
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 break-all">手机号: ${safePhone}</div>
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 break-all">创建时间: ${safeCreatedAt}</div>
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 break-all">最后登录: ${safeLastLogin}</div>
            <div class="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-700 break-all">登录IP: ${safeLoginIp} (${safeLoginCity})</div>
          </div>
          <div class="space-y-1.5 text-left mb-3">
            <div class="px-3 py-2 rounded-xl bg-slate-50 text-slate-700 text-[12px] border border-slate-200">会话限制: ${_escapeAttr(maxSessions)}</div>
            <div class="px-3 py-2 rounded-xl bg-slate-50 text-slate-700 text-[12px] border border-slate-200">可用次数: ${_escapeAttr(availableRunsText)}</div>
            <div class="px-3 py-2 rounded-xl text-[12px] border ${tfaEnabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200"}">2FA: ${tfaEnabled ? "已启用" : "未启用"}</div>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button class="w-full min-h-[38px] px-3 py-2 text-[12px] font-medium bg-indigo-50 active:bg-indigo-100 text-indigo-700 rounded-xl border border-indigo-200 transition-colors" onclick='showRemovedAccountDetail(${escapeInlineJsonArg(username)})'>查看详情</button>
            <button class="w-full min-h-[38px] px-3 py-2 text-[12px] font-medium bg-amber-50 active:bg-amber-100 text-amber-700 rounded-xl border border-amber-200 transition-colors" onclick='restoreAccountAndRefreshMobile(${escapeInlineJsonArg(username)})'>恢复账号</button>
          </div>
        </div>
      </div>`;
    });
    html += `</div>`;
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="text-xs text-red-500">加载异常：${_escapeAttr(e.message)}</p>`;
  }
}

function _formatUnixOrIsoTime(v) {
  if (v == null || v === "") return "-";
  const num = Number(v);
  if (!Number.isNaN(num) && Number.isFinite(num)) {
    const ms = num > 1e12 ? num : num * 1000;
    const d = new Date(ms);
    if (!Number.isNaN(d.getTime())) return d.toLocaleString("zh-CN");
  }
  const d2 = new Date(String(v));
  if (!Number.isNaN(d2.getTime())) return d2.toLocaleString("zh-CN");
  return _escapeAttr(String(v));
}

function _buildRemovedSchoolAccountsHtml(schoolAccounts) {
  const list = Array.isArray(schoolAccounts) ? schoolAccounts : [];
  if (!list.length) return '<div class="text-xs text-slate-500">无</div>';
  return list
    .map((school) => {
      const safeSchool = _escapeAttr(school);
      return `<div class="flex items-center justify-between gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5">
        <span class="text-xs font-mono text-slate-700 break-all">${safeSchool}</span>
        <button class="px-2 py-0.5 text-[11px] font-medium bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-md border border-indigo-200 transition-colors"
          onclick='View_details_of_users_with_outstanding_payments(${escapeInlineJsonArg(school)})'>查看账号详情</button>
      </div>`;
    })
    .join("");
}

async function showRemovedAccountDetail(authUsername) {
  const username = String(authUsername || "").trim();
  if (!username) return;
  try {
    Swal.fire({
      title: "加载中...",
      allowOutsideClick: false,
      didOpen: () => Swal.showLoading(),
    });
    const resp = await fetch(
      `/api/admin/removed_account_detail?auth_username=${encodeURIComponent(username)}`,
      { headers: { "X-Session-ID": sessionUUID } },
    );
    const data = await resp.json();
    Swal.close();
    if (!data.success || !data.detail) {
      await Swal.fire({
        title: "查看失败",
        text: data.message || "无法获取已删除账号详情",
        icon: "error",
        confirmButtonText: "确定",
      });
      return;
    }
    const detail = data.detail || {};
    const avatarRaw = String(detail.avatar_url || "default_avatar.png");
    const avatarUrl = avatarRaw.startsWith("/api/avatar/")
      ? `${avatarRaw}${avatarRaw.includes("?") ? "&" : "?"}session_id=${encodeURIComponent(sessionUUID)}&t=${Date.now()}`
      : "/default_avatar.png";
    const schoolAccountsHtml = _buildRemovedSchoolAccountsHtml(detail.school_accounts);
    const permissionGroup = detail.permission_group || {};
    const permissions = detail.permissions || {};
    const enabledPermissions = Array.isArray(permissions.enabled_permissions)
      ? permissions.enabled_permissions
      : [];
    const groupPermissionMap =
      permissions.group_permissions && typeof permissions.group_permissions === "object"
        ? permissions.group_permissions
        : {};
    const groupEnabledPermissions = Object.keys(groupPermissionMap).filter(
      (key) => !!groupPermissionMap[key],
    );
    const userCustomPermissions =
      permissions.user_custom_permissions && typeof permissions.user_custom_permissions === "object"
        ? permissions.user_custom_permissions
        : {};
    const addedPermissions = Array.isArray(userCustomPermissions.added)
      ? userCustomPermissions.added
      : [];
    const removedPermissions = Array.isArray(userCustomPermissions.removed)
      ? userCustomPermissions.removed
      : [];

    const permissionBadgesHtml = enabledPermissions.length
      ? enabledPermissions
          .map(
            (perm) =>
              `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">${_escapeAttr(translatePermission(String(perm)))}</span>`,
          )
          .join("")
      : '<span class="text-xs text-slate-500">无</span>';
    const groupPermissionBadgesHtml = groupEnabledPermissions.length
      ? groupEnabledPermissions
          .map(
            (perm) =>
              `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-sky-50 text-sky-700 border border-sky-200">${_escapeAttr(translatePermission(String(perm)))}</span>`,
          )
          .join("")
      : '<span class="text-xs text-slate-500">无</span>';
    const addedPermissionBadgesHtml = addedPermissions.length
      ? addedPermissions
          .map(
            (perm) =>
              `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">+ ${_escapeAttr(translatePermission(String(perm)))}</span>`,
          )
          .join("")
      : '<span class="text-xs text-slate-500">无</span>';
    const removedPermissionBadgesHtml = removedPermissions.length
      ? removedPermissions
          .map(
            (perm) =>
              `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">- ${_escapeAttr(translatePermission(String(perm)))}</span>`,
          )
          .join("")
      : '<span class="text-xs text-slate-500">无</span>';

    const messages = detail.messages || {};
    const messageRecords = Array.isArray(messages.records) ? messages.records : [];
    const messageRowsHtml = messageRecords.length
      ? messageRecords
          .slice(0, 30)
          .map((msg) => {
            const statusText = String(msg.status_text || (msg.source === "deleted" ? "已删" : "现存"));
            const statusClass =
              statusText === "已删"
                ? "bg-rose-50 text-rose-700 border-rose-200"
                : "bg-emerald-50 text-emerald-700 border-emerald-200";
            const timeRaw = msg.timestamp != null && msg.timestamp !== "" ? msg.timestamp : msg.deleted_at;
            return `<div class="border border-slate-200 rounded-lg p-2 bg-white">
              <div class="flex items-center justify-between gap-2 mb-1">
                <span class="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium border ${statusClass}">${_escapeAttr(statusText)}</span>
                <span class="text-[11px] text-slate-500">${_escapeAttr(_formatUnixOrIsoTime(timeRaw))}</span>
              </div>
              <div class="text-xs text-slate-700 break-words whitespace-pre-wrap">${_escapeAttr(msg.content || "")}</div>
            </div>`;
          })
          .join("")
      : '<div class="text-xs text-slate-500">无</div>';

    const billing = detail.billing || {};
    const billingStats = billing.stats || {};
    const billingRecords = Array.isArray(billing.records) ? billing.records : [];
    const billingRowsHtml = billingRecords.length
      ? billingRecords
          .slice(0, 40)
          .map((rec) => {
            const amountNumber = Number(rec.amount);
            const amountText = Number.isFinite(amountNumber) ? amountNumber.toFixed(2) : "0.00";
            const status = String(rec.status || "pending");
            const statusLabelMap = { pending: "待支付", paid: "已支付", admin_cleared: "管理员清除" };
            const statusLabel = statusLabelMap[status] || status;
            const statusClass =
              status === "paid"
                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                : status === "admin_cleared"
                  ? "bg-slate-100 text-slate-700 border-slate-300"
                  : "bg-amber-50 text-amber-700 border-amber-200";
            return `<div class="border border-slate-200 rounded-lg p-2 bg-white">
              <div class="flex items-center justify-between gap-2 mb-1">
                <div class="text-xs font-mono text-slate-700 break-all">${_escapeAttr(rec.school_username || "-")}</div>
                <span class="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium border ${statusClass}">${_escapeAttr(statusLabel)}</span>
              </div>
              <div class="text-xs text-slate-700 break-words">${_escapeAttr(rec.reason || "-")}</div>
              <div class="mt-1 text-[11px] text-slate-500 flex items-center justify-between gap-2">
                <span>金额：¥${_escapeAttr(amountText)}</span>
                <span>${_escapeAttr(_formatUnixOrIsoTime(rec.created_at))}</span>
              </div>
            </div>`;
          })
          .join("")
      : '<div class="text-xs text-slate-500">无</div>';
    await Swal.fire({
      title: "已删除账号详情",
      width: isMobileMode ? "95vw" : "680px",
      html: `
      <div class="text-left">
        <div class="flex items-center gap-3 mb-3 p-3 rounded-xl bg-slate-50 border border-slate-200">
          <img src="${_escapeAttr(avatarUrl)}" class="w-14 h-14 rounded-full object-cover border border-slate-200" onerror="this.onerror=null;this.src='/default_avatar.png';">
          <div class="min-w-0">
            <div class="text-xs text-slate-500 mb-0.5">用户名</div>
            <div class="text-sm font-semibold text-slate-800 font-mono break-all">${_escapeAttr(detail.auth_username || username)}</div>
            <div class="text-xs text-slate-500 mt-0.5">昵称：${_escapeAttr(detail.nickname || detail.auth_username || username)}</div>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs mb-3">
          <div class="bg-white border border-slate-200 rounded-lg px-2.5 py-2"><div class="text-slate-500 mb-0.5">绑定手机</div><div class="text-slate-700 break-all">${_escapeAttr(detail.phone || "未绑定")}</div></div>
          <div class="bg-white border border-slate-200 rounded-lg px-2.5 py-2"><div class="text-slate-500 mb-0.5">登录 IP</div><div class="text-slate-700 break-all">${_escapeAttr(detail.last_login_ip || "-")}</div></div>
          <div class="bg-white border border-slate-200 rounded-lg px-2.5 py-2"><div class="text-slate-500 mb-0.5">最后登录时间</div><div class="text-slate-700 break-all">${_escapeAttr(_formatUnixOrIsoTime(detail.last_login))}</div></div>
          <div class="bg-white border border-slate-200 rounded-lg px-2.5 py-2"><div class="text-slate-500 mb-0.5">注册时间</div><div class="text-slate-700 break-all">${_escapeAttr(_formatUnixOrIsoTime(detail.register_time))}</div></div>
          <div class="bg-white border border-slate-200 rounded-lg px-2.5 py-2"><div class="text-slate-500 mb-0.5">注销时间</div><div class="text-slate-700 break-all">${_escapeAttr(_formatUnixOrIsoTime(detail.deleted_at))}</div></div>
        </div>
        <div class="bg-white border border-slate-200 rounded-xl p-2.5">
          <div class="text-xs font-semibold text-slate-700 mb-2">有权限的学校账号</div>
          <div class="space-y-1.5 max-h-56 overflow-y-auto">${schoolAccountsHtml}</div>
        </div>
        <div class="bg-white border border-slate-200 rounded-xl p-2.5 mt-3">
          <div class="text-xs font-semibold text-slate-700 mb-2">权限组</div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            <div class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2">
              <div class="text-slate-500 mb-0.5">组标识</div>
              <div class="text-slate-700 font-mono break-all">${_escapeAttr(permissionGroup.key || "-")}</div>
            </div>
            <div class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-2">
              <div class="text-slate-500 mb-0.5">组名称</div>
              <div class="text-slate-700 break-all">${_escapeAttr(permissionGroup.name || permissionGroup.key || "-")}</div>
            </div>
          </div>
          <div class="mt-2">
            <div class="text-[11px] text-slate-500 mb-1">组内权限</div>
            <div class="flex flex-wrap gap-1.5">${groupPermissionBadgesHtml}</div>
          </div>
          <div class="mt-2">
            <div class="text-[11px] text-slate-500 mb-1">自定义追加权限</div>
            <div class="flex flex-wrap gap-1.5">${addedPermissionBadgesHtml}</div>
          </div>
          <div class="mt-2">
            <div class="text-[11px] text-slate-500 mb-1">自定义移除权限</div>
            <div class="flex flex-wrap gap-1.5">${removedPermissionBadgesHtml}</div>
          </div>
          <div class="mt-2">
            <div class="text-[11px] text-slate-500 mb-1">最终生效权限</div>
            <div class="flex flex-wrap gap-1.5">${permissionBadgesHtml}</div>
          </div>
        </div>
        <div class="bg-white border border-slate-200 rounded-xl p-2.5 mt-3">
          <div class="flex items-center justify-between gap-2 mb-2">
            <div class="text-xs font-semibold text-slate-700">留言记录</div>
            <div class="text-[11px] text-slate-500">现存 ${_escapeAttr(String(messages.total_current || 0))} / 已删 ${_escapeAttr(String(messages.total_deleted || 0))}</div>
          </div>
          <div class="space-y-1.5 max-h-56 overflow-y-auto">${messageRowsHtml}</div>
        </div>
        <div class="bg-white border border-slate-200 rounded-xl p-2.5 mt-3">
          <div class="flex items-center justify-between gap-2 mb-2">
            <div class="text-xs font-semibold text-slate-700">账单记录</div>
            <div class="text-[11px] text-slate-500">共 ${_escapeAttr(String(billingStats.total || 0))} 条</div>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] mb-2">
            <div class="bg-amber-50 border border-amber-200 rounded-lg px-2 py-1.5 text-amber-700">待支付：${_escapeAttr(String(billingStats.pending || 0))}</div>
            <div class="bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-1.5 text-emerald-700">已支付：${_escapeAttr(String(billingStats.paid || 0))}</div>
            <div class="bg-slate-100 border border-slate-300 rounded-lg px-2 py-1.5 text-slate-700">管理员清除：${_escapeAttr(String(billingStats.admin_cleared || 0))}</div>
            <div class="bg-indigo-50 border border-indigo-200 rounded-lg px-2 py-1.5 text-indigo-700">待支付金额：¥${_escapeAttr(String(Number(billingStats.pending_amount || 0).toFixed(2)))}</div>
          </div>
          <div class="space-y-1.5 max-h-64 overflow-y-auto">${billingRowsHtml}</div>
        </div>
      </div>
      `,
      showConfirmButton: true,
      confirmButtonText: "关闭",
      confirmButtonColor: "#3b82f6",
    });
  } catch (e) {
    await Swal.fire({
      title: "查看失败",
      text: e.message || "请求异常",
      icon: "error",
      confirmButtonText: "确定",
    });
  }
}

/**
 * 管理员恢复指定账号（含冲突处理：用户名冲突 / 手机号冲突）
 */
async function restoreAccount(auth_username) {
  // ── 步骤1：二次确认 ──────────────────────────────────────────────────────
  const confirmResult = await Swal.fire({
    title: "恢复账号确认",
    html: `
      <div style="text-align:left;padding:8px 0;line-height:1.6;">

        <!-- 顶部说明 -->
        <p style="font-size:14px;color:#475569;margin-bottom:12px;">
          请确认是否要恢复以下账号：
        </p>

        <!-- 红色警告（纯色、无发光、无渐变） -->
        <div style="
          background:#fee2e2;
          border-left:4px solid #dc2626;
          padding:12px 14px;
          border-radius:6px;
          margin-bottom:14px;
        ">
          <p style="
            font-size:14px;
            color:#b91c1c;
            margin:0;
            font-weight:600;
          ">
            ⚠️ 恢复后该账号将重新可以登录，且所有历史数据将被完整还原。
          </p>
        </div>

        <!-- 账号展示（绿色提示块） -->
        <div style="
          background:#e7f7eb;
          border-left:4px solid #16a34a;
          padding:10px 14px;
          border-radius:6px;
          margin-bottom:10px;
        ">
          <p style="
            font-size:16px;
            font-weight:700;
            color:#15803d;
            margin:0;
            font-family:monospace;
          ">
            ${auth_username}
          </p>
        </div>

        <!-- 底部说明 -->
        <p style="font-size:12px;color:#64748b;margin-top:6px;">
          请谨慎操作，此操作不可撤销。
        </p>
      </div>
    `,
    icon: "warning",
    showCancelButton: true,

    /* 按钮文本 */
    confirmButtonText: "<strong>🔄 确认恢复</strong>",
    cancelButtonText: "<strong>✖️ 取消</strong>",

    /* 按钮颜色（纯色、无发光） */
    confirmButtonColor: "#dc2626",
    cancelButtonColor: "#64748b",

    /* 自定义类（用于去除发光、统一风格） */
    customClass: {
      popup: "swal2-clean-popup",
      title: "swal2-clean-title",
      confirmButton: "swal2-clean-btn",
      cancelButton: "swal2-clean-btn",
    },

    reverseButtons: true,
  });

  if (!confirmResult.isConfirmed) return false;

  // ── 步骤2：调用恢复接口（含冲突解决参数）──────────────────────────────────
  let restoreAs = auth_username; // 可被用户名冲突处理修改
  let phoneOverride = undefined; // undefined=不覆盖; ""=清空; "xxx"=新号码
  let forcePhoneClear = false;

  // 循环：每次遇到冲突时弹窗让管理员解决，然后重试
  for (let attempt = 0; attempt < 10; attempt++) {
    const payload = { auth_username, restore_as: restoreAs };
    if (phoneOverride !== undefined) payload.phone_override = phoneOverride;
    if (forcePhoneClear) payload.force_phone_clear = true;

    let resp, data;
    try {
      resp = await fetch("/api/admin/restore_account", {
        method: "POST",
        headers: {
          "X-Session-ID": sessionUUID,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      data = await resp.json();
    } catch (e) {
      await Swal.fire({
        title: "请求异常",
        text: e.message,
        icon: "error",
        confirmButtonText: "确定",
        confirmButtonColor: "#dc2626",
        customClass: { popup: "swal2-neumorphism-popup" },
      });
      return false;
    }

    // ── 成功 ────────────────────────────────────────────────────────────────
    if (data.success) {
      const restoredAs = data.restored_as || restoreAs;
      await Swal.fire({
        title: "恢复成功",
        html: `账号 <strong style="font-family:monospace;">${restoredAs}</strong> 已成功恢复`,
        icon: "success",
        confirmButtonText: "确定",
        confirmButtonColor: "#16a34a",
        timer: 3000,
        timerProgressBar: true,
        customClass: { popup: "swal2-neumorphism-popup" },
      });
      loadRemovedAccountsList();
      return true;
    }

    // ── 用户名冲突 ───────────────────────────────────────────────────────────
    if (data.conflict === "username") {
      const usernameResult = await Swal.fire({
        title: "⚠️ 用户名冲突",
        html: `
          <div style="text-align:left;padding:4px 0;">
            <p style="color:#475569;font-size:14px;margin-bottom:12px;">
              用户名 <code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:13px;">${data.conflicting_username || restoreAs}</code> 已存在，请输入新的用户名：
            </p>
            <input id="swal-new-username" type="text" class="swal2-input"
              placeholder="新用户名"
              value="${data.conflicting_username || restoreAs}"
              style="margin:0;width:100%;box-sizing:border-box;">
          </div>`,
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "确认",
        confirmButtonColor: "#2563eb",
        cancelButtonText: "取消",
        cancelButtonColor: "#64748b",
        customClass: { popup: "swal2-neumorphism-popup" },
        reverseButtons: true,
        preConfirm: () => {
          const val = document.getElementById("swal-new-username").value.trim();
          if (!val) {
            Swal.showValidationMessage("用户名不能为空");
            return false;
          }
          return val;
        },
      });
      if (!usernameResult.isConfirmed) return false;
      restoreAs = usernameResult.value;
      continue;
    }

    // ── 手机号冲突 ───────────────────────────────────────────────────────────
    if (data.conflict === "phone") {
      const conflictPhone = data.phone || "";
      const conflictUser = data.conflicting_user || "";
      const phoneResult = await Swal.fire({
        title: "⚠️ 手机号冲突",
        html: `
          <div style="text-align:left;padding:4px 0;">
            <p style="color:#475569;font-size:14px;margin-bottom:12px;">
              手机号 <code style="background:#fef3c7;padding:2px 6px;border-radius:4px;font-size:13px;">${conflictPhone}</code>
              已被用户 <strong style="font-family:monospace;">${conflictUser}</strong> 绑定。
            </p>
            <p style="color:#64748b;font-size:13px;margin-bottom:8px;">
              请输入新手机号（留空或直接确认则<strong>清空手机号</strong>）：
            </p>
            <input id="swal-new-phone" type="tel" class="swal2-input"
              placeholder="新手机号（留空则清空）"
              style="margin:0;width:100%;box-sizing:border-box;">
          </div>`,
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "确认",
        confirmButtonColor: "#d97706",
        cancelButtonText: "取消",
        cancelButtonColor: "#64748b",
        customClass: { popup: "swal2-neumorphism-popup" },
        reverseButtons: true,
        preConfirm: () => {
          return document.getElementById("swal-new-phone").value.trim();
        },
      });
      if (!phoneResult.isConfirmed) return false;
      const newPhone = phoneResult.value || "";
      if (!newPhone || newPhone === conflictPhone) {
        // 管理员留空或输入了相同冲突号码 → 强制清空
        phoneOverride = "";
        forcePhoneClear = true;
      } else {
        phoneOverride = newPhone;
        forcePhoneClear = false;
      }
      continue;
    }

    // ── 其他错误 ─────────────────────────────────────────────────────────────
    await Swal.fire({
      title: "恢复失败",
      text: data.message || "未知错误",
      icon: "error",
      confirmButtonText: "确定",
      confirmButtonColor: "#dc2626",
      customClass: { popup: "swal2-neumorphism-popup" },
    });
    return false;
  }

  // 超过最大重试次数
  await Swal.fire({
    title: "操作失败",
    text: "解决冲突的尝试次数过多，请刷新后重试",
    icon: "error",
    confirmButtonText: "确定",
    confirmButtonColor: "#dc2626",
    customClass: { popup: "swal2-neumorphism-popup" },
  });
  return false;
}

async function restoreAccountAndRefreshMobile(auth_username) {
  const ok = await restoreAccount(auth_username);
  if (ok) await loadMobileMultiRemovedAccountsList();
}

function handleApplicationInitializationFailure(err) {
  logMessage_Error("应用初始化失败:", err);
  appInitialized = false;
  if (cdnErrorCount > 0) {
    if (cdnErrorTimer) clearTimeout(cdnErrorTimer);
    const errorOverlay = document.getElementById("cdn-error-overlay");
    if (errorOverlay) {
      errorOverlay.style.setProperty("display", "flex", "important");
    }
  }
}

function bootstrapLegacyApplication() {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initializeApp().catch(handleApplicationInitializationFailure);
    });
    return;
  }
  initializeApp().catch(handleApplicationInitializationFailure);
}

bootstrapLegacyApplication();
