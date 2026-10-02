// Provider map configuration, SDK loading, and map runtime helpers.

function normalizeSupportedMapProvider(provider) {
  const normalized = String(provider || "").trim().toLowerCase();
  return ["amap", "tencent", "tianditu", "baidu"].includes(normalized)
    ? normalized
    : "";
}

function getActiveMapProvider() {
  const config = window.APP_CONFIG || {};
  return normalizeSupportedMapProvider(config.map_provider) || "amap";
}

function getMapProviderDisplayName(provider) {
  const normalizedProvider = String(provider || getActiveMapProvider()).trim().toLowerCase();
  const displayNames = {
    amap: "高德地图",
    tencent: "腾讯地图",
    tianditu: "天地图",
    baidu: "百度地图",
  };
  return displayNames[normalizedProvider] || displayNames.amap;
}

function getMapProviderConfig(provider) {
  const config = window.APP_CONFIG || {};
  const mapProviders = config.map_providers || {};
  const normalizedProvider = String(provider || getActiveMapProvider()).trim().toLowerCase();
  return mapProviders[normalizedProvider] || mapProviders.amap || {};
}

function getMapProviderKeyRequirement(provider) {
  const normalizedProvider = String(provider || getActiveMapProvider()).trim().toLowerCase();
  const requirements = {
    amap: {
      provider: "amap",
      displayName: "高德地图",
      platformName: "高德开放平台",
      applyUrl: "https://console.amap.com/dev/key/app",
      fieldKey: "js_key",
      fieldLabel: "JS Key",
      applyHint: "申请 Key 时类型选择“Web端(JS API)”。",
    },
    tencent: {
      provider: "tencent",
      displayName: "腾讯地图",
      platformName: "腾讯位置服务控制台",
      applyUrl: "https://lbs.qq.com/dev/console/application/mine",
      fieldKey: "map_key",
      fieldLabel: "地图 Key",
      applyHint: "申请 WebService/JavaScript API 可用的 Key。",
    },
    tianditu: {
      provider: "tianditu",
      displayName: "天地图",
      platformName: "天地图控制台",
      applyUrl: "https://console.tianditu.gov.cn/api/key",
      fieldKey: "token",
      fieldLabel: "Token",
      applyHint: "申请浏览器端或服务端可用的天地图 Token。",
    },
    baidu: {
      provider: "baidu",
      displayName: "百度地图",
      platformName: "百度地图开放平台",
      applyUrl: "https://lbsyun.baidu.com/apiconsole/key",
      fieldKey: "ak",
      fieldLabel: "AK",
      applyHint: "申请浏览器端或服务端可用的百度地图 AK。",
    },
  };
  const requirement = requirements[normalizedProvider] || requirements.amap;
  const providerConfig = getMapProviderConfig(requirement.provider);
  const value = String(
    providerConfig[requirement.fieldKey] ||
      (requirement.provider === "amap" ? AMAP_API_KEY : "") ||
      "",
  ).trim();
  return {
    ...requirement,
    value,
    configPath: `Map.providers.${requirement.provider}.${requirement.fieldKey}`,
  };
}

function getActiveMapProviderApiKey() {
  return getMapProviderKeyRequirement(getActiveMapProvider()).value;
}

let pendingMapProviderRuntimeConfig = null;
let activeTaskMapProviderLock = null;
const TASK_MAP_AUTO_RESET_IDLE_MS = 120000;
let taskMapAutoResetTimer = null;
let taskMapAutoResetContainerId = "";

function createMapProviderRuntimeConfigSnapshot(data) {
  if (!data || typeof data !== "object") {
    return null;
  }
  const snapshot = {};
  const provider = normalizeSupportedMapProvider(data.map_provider);
  if (provider) {
    snapshot.map_provider = provider;
  }
  if (data.map_providers && typeof data.map_providers === "object") {
    snapshot.map_providers = { ...data.map_providers };
  }
  if (data.amap_key) {
    snapshot.amap_key = data.amap_key;
  }
  return Object.keys(snapshot).length ? snapshot : null;
}

function queuePendingMapProviderConfig(data) {
  const snapshot = createMapProviderRuntimeConfigSnapshot(data);
  if (!snapshot) {
    return false;
  }
  pendingMapProviderRuntimeConfig = snapshot;
  return true;
}

function getRunningTaskMapProvider(data) {
  const taskStatus =
    data && typeof data === "object" && data.task_status && typeof data.task_status === "object"
      ? data.task_status
      : null;
  if (!taskStatus) {
    return "";
  }
  const status = String(taskStatus.status || "").trim().toLowerCase();
  if (status !== "running" && status !== "paused") {
    return "";
  }
  return (
    normalizeSupportedMapProvider(
      taskStatus.map_provider || taskStatus.mapProvider || taskStatus.provider,
    ) || getActiveMapProvider()
  );
}

function isCurrentPageMapTaskActive() {
  if (backgroundTaskPollInterval) {
    return true;
  }
  if (singleRunProgressVisualActive) {
    return true;
  }
  const data = currentRunData || {};
  const status = String(data.status || data.run_status || data.task_status || "").trim().toLowerCase();
  return status === "running" || status === "paused";
}

function isMapProviderRuntimeSwitchLocked(data) {
  return !!getRunningTaskMapProvider(data) || !!activeTaskMapProviderLock || isCurrentPageMapTaskActive();
}

function applyPendingMapProviderConfigIfAny() {
  if (!pendingMapProviderRuntimeConfig || isMapProviderRuntimeSwitchLocked()) {
    return false;
  }
  const pendingConfig = pendingMapProviderRuntimeConfig;
  pendingMapProviderRuntimeConfig = null;
  syncMapProviderConfigFromInitialData(pendingConfig);
  return true;
}

function isTaskMapAutoResetExecutionActive() {
  return !!activeTaskMapProviderLock || isCurrentPageMapTaskActive();
}

function resetTaskMapView(containerId = "map-container") {
  if (containerId === "multi-map-container") {
    if (getActiveMapProvider() !== "amap") {
      return fitProviderMapToLastRoute(containerId);
    }
    if (typeof multi_resetMapView === "function") {
      multi_resetMapView();
      return true;
    }
    return false;
  }
  if (getActiveMapProvider() !== "amap") {
    return fitProviderMapToLastRoute(containerId);
  }
  resetMapView();
  return true;
}

function clearTaskMapAutoResetTimer() {
  if (taskMapAutoResetTimer !== null && taskMapAutoResetTimer !== undefined) {
    const timerHost = typeof window !== "undefined" ? window : globalThis;
    const clearTimer =
      timerHost && typeof timerHost.clearTimeout === "function"
        ? timerHost.clearTimeout.bind(timerHost)
        : clearTimeout;
    clearTimer(taskMapAutoResetTimer);
  }
  taskMapAutoResetTimer = null;
  taskMapAutoResetContainerId = "";
}

function scheduleTaskMapAutoResetAfterUserInteraction(containerId = "map-container") {
  if (!isTaskMapAutoResetExecutionActive()) {
    clearTaskMapAutoResetTimer();
    return false;
  }
  clearTaskMapAutoResetTimer();
  const timerHost = typeof window !== "undefined" ? window : globalThis;
  const setTimer =
    timerHost && typeof timerHost.setTimeout === "function"
      ? timerHost.setTimeout.bind(timerHost)
      : setTimeout;
  taskMapAutoResetContainerId = containerId || "map-container";
  taskMapAutoResetTimer = setTimer(() => {
    const resetContainerId = taskMapAutoResetContainerId || containerId || "map-container";
    taskMapAutoResetTimer = null;
    taskMapAutoResetContainerId = "";
    if (isTaskMapAutoResetExecutionActive()) {
      resetTaskMapView(resetContainerId);
    }
  }, TASK_MAP_AUTO_RESET_IDLE_MS);
  return true;
}

function syncMapProviderConfigFromInitialData(data) {
  if (!data || typeof data !== "object") {
    return;
  }

  const runningTaskProvider = getRunningTaskMapProvider(data);
  if (runningTaskProvider) {
    activeTaskMapProviderLock = runningTaskProvider;
  } else if (data.task_status) {
    activeTaskMapProviderLock = null;
  }

  const incomingProvider = normalizeSupportedMapProvider(data.map_provider);
  if (runningTaskProvider && incomingProvider && incomingProvider !== runningTaskProvider) {
    queuePendingMapProviderConfig(data);
  } else if (!runningTaskProvider && incomingProvider) {
    pendingMapProviderRuntimeConfig = null;
  }

  const currentConfig = window.APP_CONFIG || {};
  const nextConfig = {
    ...currentConfig,
    map_providers: {
      ...(currentConfig.map_providers || {}),
    },
  };

  if (runningTaskProvider) {
    nextConfig.map_provider = runningTaskProvider;
  } else if (incomingProvider) {
    nextConfig.map_provider = incomingProvider;
  }
  if (data.map_providers && typeof data.map_providers === "object") {
    Object.entries(data.map_providers).forEach(([provider, value]) => {
      const currentProviderConfig = nextConfig.map_providers[provider];
      nextConfig.map_providers[provider] = {
        ...(currentProviderConfig && typeof currentProviderConfig === "object"
          ? currentProviderConfig
          : {}),
        ...(value && typeof value === "object" ? value : {}),
      };
    });
  }
  if (data.amap_key) {
    nextConfig.map_providers.amap = {
      ...(nextConfig.map_providers.amap || {}),
      provider: "amap",
      display_name: "高德地图",
      js_key: data.amap_key,
      coordinate_system: "gcj02",
      business_coordinate_system: "gcj02",
    };
  }

  window.APP_CONFIG = nextConfig;
  AMAP_API_KEY = getMapProviderKeyRequirement("amap").value || "";
}

function showMissingMapProviderKeyModal(provider) {
  const requirement = getMapProviderKeyRequirement(provider);
  const modal = $("amap-key-modal");
  if (!modal) {
    return;
  }

  const title = $("map-provider-key-modal-title");
  const description = $("map-provider-key-modal-description");
  const link = $("map-provider-key-modal-link");
  const extra = $("map-provider-key-modal-extra");
  const label = $("map-provider-key-input-label");
  const input = $("amap-key-input");
  const confirmButton = $("confirm-amap-key-btn");

  if (title) {
    title.textContent = `缺少${requirement.displayName} ${requirement.fieldLabel}`;
  }
  if (description) {
    description.firstChild.textContent = `当前地图提供方是${requirement.displayName}，程序需要一个有效的 ${requirement.fieldLabel} 才能使用对应地图功能。请前往`;
  }
  if (link) {
    link.href = requirement.applyUrl;
    link.textContent = requirement.platformName;
  }
  if (extra) {
    extra.textContent = `${requirement.applyHint} 配置路径：${requirement.configPath}。`;
  }
  if (label) {
    label.textContent = `${requirement.displayName} ${requirement.fieldLabel}:`;
  }
  if (input) {
    input.value = "";
    input.placeholder = `请在此处粘贴${requirement.displayName} ${requirement.fieldLabel}`;
    input.dataset.provider = requirement.provider;
  }
  if (confirmButton) {
    confirmButton.textContent = "确认并保存";
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.body.classList.add("modal-visible");
}

async function ensureActiveMapProviderRuntimeIfNeeded(contextLabel = "地图") {
  const provider = getActiveMapProvider();
  const requirement = getMapProviderKeyRequirement(provider);
  if (!requirement.value) {
    logMessage_Info(
      `[警告] 未配置${requirement.displayName} ${requirement.fieldLabel}，请在弹窗中输入。`,
    );
    showMissingMapProviderKeyModal(provider);
    return false;
  }

  if (provider !== "amap") {
    await loadActiveMapProviderRuntime(provider);
    logMessage_Info(
      `[地图] ${requirement.displayName}前端地图运行时已就绪（${contextLabel}）。`,
    );
    return true;
  }

  AMAP_API_KEY = requirement.value;
  await loadAMapOnce();
  return true;
}

function loadScriptOnce(scriptSelector, scriptUrl, onBeforeAppend, errorMessage) {
  return new Promise((resolve, reject) => {
    const existingScript = document.querySelector(scriptSelector);
    if (existingScript) {
      existingScript.remove();
    }

    const script = document.createElement("script");
    script.src = scriptUrl;
    script.async = true;
    script.defer = true;
    if (typeof onBeforeAppend === "function") {
      onBeforeAppend(script, resolve, reject);
    } else {
      script.onload = () => resolve();
    }
    script.onerror = () => reject(new Error(errorMessage || "地图脚本加载失败"));
    document.head.appendChild(script);
  });
}

function loadTencentMapOnce(key) {
  if (window.TMap && window.TMap.Map && window.TMap.LatLng) {
    return Promise.resolve(window.TMap);
  }
  if (tencentMapLoadingPromise) return tencentMapLoadingPromise;

  tencentMapLoadingPromise = loadScriptOnce(
    'script[data-qq-map-api="true"]',
    `https://map.qq.com/api/gljs?v=1.exp&key=${encodeURIComponent(key)}`,
    (script, resolve, reject) => {
      script.dataset.qqMapApi = "true";
      script.onload = () => {
        if (window.TMap && window.TMap.Map && window.TMap.LatLng) {
          resolve(window.TMap);
          return;
        }
        reject(new Error("腾讯地图脚本加载完成但运行时不可用，请检查 Key、域名白名单或网络连接。"));
      };
    },
    "腾讯地图脚本加载失败，请检查 Key 或网络连接。",
  ).catch((error) => {
    tencentMapLoadingPromise = null;
    throw error;
  });
  return tencentMapLoadingPromise;
}

function loadTianDiTuMapOnce(token) {
  if (window.T && window.T.Map) {
    return Promise.resolve(window.T);
  }
  if (tiandituMapLoadingPromise) return tiandituMapLoadingPromise;

  tiandituMapLoadingPromise = loadScriptOnce(
    'script[data-tianditu-api="true"]',
    `https://api.tianditu.gov.cn/api?v=4.0&tk=${encodeURIComponent(token)}`,
    (script, resolve, reject) => {
      script.dataset.tiandituApi = "true";
      script.onload = () => {
        if (window.T && window.T.Map) {
          resolve(window.T);
          return;
        }
        reject(new Error("天地图脚本加载完成但运行时不可用，请检查 Token、域名白名单或网络连接。"));
      };
    },
    "天地图脚本加载失败，请检查 Token 或网络连接。",
  ).catch((error) => {
    tiandituMapLoadingPromise = null;
    throw error;
  });
  return tiandituMapLoadingPromise;
}

function loadBaiduMapOnce(ak) {
  if (window.BMapGL && typeof window.BMapGL.Map === "function") {
    return Promise.resolve(window.BMapGL);
  }
  if (baiduMapLoadingPromise) return baiduMapLoadingPromise;

  baiduMapLoadingPromise = loadScriptOnce(
    'script[data-baidu-map-api="true"]',
    `https://api.map.baidu.com/api?v=1.0&type=webgl&ak=${encodeURIComponent(ak)}&callback=__onBaiduMapApiLoaded`,
    (script, resolve, reject) => {
      script.dataset.baiduMapApi = "true";
      window.__onBaiduMapApiLoaded = function () {
        try {
          delete window.__onBaiduMapApiLoaded;
        } catch (_) {
          window.__onBaiduMapApiLoaded = undefined;
        }
        if (window.BMapGL && typeof window.BMapGL.Map === "function") {
          resolve(window.BMapGL);
          return;
        }
        reject(new Error("百度地图脚本加载完成但运行时不可用，请检查 AK、域名白名单或网络连接。"));
      };
    },
    "百度地图脚本加载失败，请检查 AK 或网络连接。",
  ).catch((error) => {
    baiduMapLoadingPromise = null;
    throw error;
  });
  return baiduMapLoadingPromise;
}

async function loadActiveMapProviderRuntime(provider = getActiveMapProvider()) {
  const requirement = getMapProviderKeyRequirement(provider);
  installGenericMapRuntimeGuards();
  switch (requirement.provider) {
    case "tencent":
      return loadTencentMapOnce(requirement.value);
    case "tianditu":
      return loadTianDiTuMapOnce(requirement.value);
    case "baidu":
      return loadBaiduMapOnce(requirement.value);
    case "amap":
      return loadAMapOnce();
    default:
      throw new Error(`不支持的地图提供方: ${requirement.provider}`);
  }
}

function getProviderMapSurfaceId(containerId) {
  return `${containerId}-provider-surface`;
}

function getProviderMapSurface(containerId) {
  return document.getElementById(getProviderMapSurfaceId(containerId));
}

function clearProviderMapContainerChildren(container) {
  if (!container) return;
  if (container.firstChild) {
    while (container.firstChild) {
      container.removeChild(container.firstChild);
    }
  } else if (Array.isArray(container.children)) {
    [...container.children].forEach((child) => {
      if (child && typeof container.removeChild === "function") {
        container.removeChild(child);
      }
    });
  }
  container.innerHTML = "";
}

function ensureProviderMapSurface(containerId, shouldReset = false) {
  const container = document.getElementById(containerId);
  if (!container) return null;
  if (container.classList && typeof container.classList.add === "function") {
    container.classList.add("relative", "overflow-hidden");
  }

  let surface = getProviderMapSurface(containerId);
  if (shouldReset || !surface || surface.parentNode !== container) {
    clearProviderMapContainerChildren(container);
    surface = document.createElement("div");
    surface.id = getProviderMapSurfaceId(containerId);
    surface.className = "absolute inset-0 w-full h-full";
    surface.style.position = "absolute";
    surface.style.inset = "0";
    surface.style.width = "100%";
    surface.style.height = "100%";
    surface.style.zIndex = "0";
    container.appendChild(surface);
  }
  return surface;
}

function isElementInsideContainer(container, element) {
  let current = element;
  while (current) {
    if (current === container) return true;
    current = current.parentNode;
  }
  return false;
}

function findProviderControlOverlayElement(element) {
  let current = element;
  while (current) {
    if (
      current.dataset &&
      (current.dataset.providerMapViewControl === "true" ||
        current.dataset.providerMapControlOverlay === "true")
    ) {
      return current;
    }
    current = current.parentNode;
  }
  return null;
}

function removeElementOrParentOverlay(element) {
  if (!element) return;
  const target = findProviderControlOverlayElement(element) || element;
  if (target && typeof target.remove === "function") {
    target.remove();
  } else if (target && target.parentNode && typeof target.parentNode.removeChild === "function") {
    target.parentNode.removeChild(target);
  }
}

function destroyProviderMapInstance(containerId) {
  clearProviderMapOverlays(containerId, { clearRunnerMarkers: true });
  const instance = providerMapInstances[containerId];
  if (!instance) return;
  try {
    if (typeof instance.destroy === "function") {
      instance.destroy();
    } else if (typeof instance.remove === "function") {
      instance.remove();
    } else if (typeof instance.clearOverLays === "function") {
      instance.clearOverLays();
    } else if (typeof instance.clearOverlays === "function") {
      instance.clearOverlays();
    }
  } catch (e) {
    logMessage_Warning(`[地图] 销毁${containerId}供应商地图实例失败:`, e);
  }
  delete providerMapInstances[containerId];
  delete providerMapInstanceProviders[containerId];
  delete providerMapEventsBound[containerId];
  delete providerMapLastFitCoords[containerId];
  delete providerRunnerMarkers[containerId];
}

function getProviderOverlayBucket(containerId) {
  if (!providerMapOverlays[containerId]) {
    providerMapOverlays[containerId] = [];
  }
  return providerMapOverlays[containerId];
}

function clearProviderRunnerMarkers(containerId) {
  Object.keys(providerRunnerMarkers).forEach((markerKey) => {
    if (markerKey === containerId || markerKey.startsWith(`${containerId}:`)) {
      removeProviderOverlayFromMap(containerId, providerRunnerMarkers[markerKey]);
      delete providerRunnerMarkers[markerKey];
    }
  });
}

function clearProviderMapOverlays(containerId, options = {}) {
  const overlays = providerMapOverlays[containerId] || [];
  overlays.forEach((overlay) => {
    removeProviderOverlayFromMap(containerId, overlay);
  });
  providerMapOverlays[containerId] = [];
  providerMapLastFitCoords[containerId] = [];
  if (options.clearRunnerMarkers === true) {
    clearProviderRunnerMarkers(containerId);
  }
}

function removeProviderOverlayFromMap(containerId, overlay) {
  if (!overlay) return false;
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  try {
    if (provider === "tencent" && typeof overlay.setMap === "function") {
      overlay.setMap(null);
      return true;
    }
    if (provider === "tianditu" && instance && typeof instance.removeOverLay === "function") {
      instance.removeOverLay(overlay);
      return true;
    }
    if (provider === "baidu" && instance && typeof instance.removeOverlay === "function") {
      instance.removeOverlay(overlay);
      return true;
    }
    if (overlay && typeof overlay.setMap === "function") {
      overlay.setMap(null);
      return true;
    }
  } catch (e) {
    logMessage_Warning(`[地图] 移除${containerId}覆盖物失败:`, e);
  }
  return false;
}

function getProviderMapDefaultZoom(provider) {
  if (provider === "baidu") return 18;
  if (provider === "tianditu") return 17;
  return 17;
}

function getProviderMapDefaultCenter() {
  return { lng: 113.390342, lat: 22.527403 };
}

function applyProviderMapDefaultOrientation(containerId) {
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  if (!instance) return false;
  try {
    if (provider === "tencent") {
      if (typeof instance.setViewMode === "function") instance.setViewMode("3D");
      if (typeof instance.setPitch === "function") instance.setPitch(55);
      if (typeof instance.setRotation === "function") instance.setRotation(0);
      return true;
    }
    if (provider === "baidu") {
      if (typeof instance.setTilt === "function") instance.setTilt(55);
      if (typeof instance.setHeading === "function") instance.setHeading(0);
      return true;
    }
  } catch (e) {
    logMessage_Warning(`[地图] 恢复${containerId}默认视角姿态失败:`, e);
  }
  return false;
}

function applyProviderMapDefaultView(containerId) {
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  if (!instance) return false;
  const center = getProviderMapDefaultCenter();
  const providerCenter = convertGcj02ToProviderCoordinates(provider, center);
  const zoom = getProviderMapDefaultZoom(provider);
  try {
    if (provider === "tencent" && window.TMap) {
      if (typeof instance.setViewMode === "function") instance.setViewMode("3D");
      if (typeof instance.setCenter === "function") {
        instance.setCenter(new TMap.LatLng(providerCenter.lat, providerCenter.lng));
      }
      if (typeof instance.setZoom === "function") instance.setZoom(zoom);
      applyProviderMapDefaultOrientation(containerId);
      return true;
    }
    if (provider === "tianditu" && window.T && typeof instance.centerAndZoom === "function") {
      instance.centerAndZoom(new T.LngLat(providerCenter.lng, providerCenter.lat), zoom);
      return true;
    }
    if (provider === "baidu" && window.BMapGL && typeof instance.centerAndZoom === "function") {
      instance.centerAndZoom(new BMapGL.Point(providerCenter.lng, providerCenter.lat), zoom);
      applyProviderMapDefaultOrientation(containerId);
      return true;
    }
  } catch (e) {
    logMessage_Warning(`[地图] 恢复${containerId}默认视角失败:`, e);
  }
  return false;
}

function addBaiduProvider3DControl(instance) {
  if (
    !instance ||
    instance.__provider3DControlAdded ||
    !window.BMapGL ||
    typeof BMapGL.NavigationControl3D !== "function" ||
    typeof instance.addControl !== "function"
  ) {
    return false;
  }
  const options = {};
  if (typeof BMAP_ANCHOR_TOP_LEFT !== "undefined") {
    options.anchor = BMAP_ANCHOR_TOP_LEFT;
  }
  if (typeof BMapGL.Size === "function") {
    options.offset = new BMapGL.Size(12, 12);
  }
  try {
    instance.addControl(new BMapGL.NavigationControl3D(options));
    instance.__provider3DControlAdded = true;
    return true;
  } catch (e) {
    logMessage_Warning("[地图] 添加百度地图3D视角控件失败:", e);
    return false;
  }
}

function getProvider3DViewButtonId(containerId) {
  return getProvider3DViewControlButtonId(containerId, "reset");
}

function getProvider3DViewControlButtonId(containerId, action) {
  const prefix =
    containerId === "multi-map-container" ? "multi-provider-3d-view" : "provider-3d-view";
  if (action === "reset") return `${prefix}-btn`;
  return `${prefix}-${action}-btn`;
}

function removeProvider3DViewControl(containerId) {
  const button = document.getElementById(getProvider3DViewButtonId(containerId));
  removeElementOrParentOverlay(button);
}

function getProvider3DViewNumber(instance, getterName, propertyName, fallback) {
  try {
    if (instance && typeof instance[getterName] === "function") {
      const value = Number(instance[getterName]());
      if (Number.isFinite(value)) return value;
    }
    if (instance && Number.isFinite(Number(instance[propertyName]))) {
      return Number(instance[propertyName]);
    }
  } catch (e) {
    logMessage_Warning(`[地图] 读取3D视角参数失败: ${getterName}`, e);
  }
  return fallback;
}

function normalizeProvider3DViewRotation(rotation) {
  const value = Number(rotation);
  if (!Number.isFinite(value)) return 0;
  return ((value % 360) + 360) % 360;
}

function clampProvider3DViewPitch(pitch, maxPitch) {
  const value = Number(pitch);
  if (!Number.isFinite(value)) return 0;
  return Math.min(maxPitch, Math.max(0, value));
}

function adjustProvider3DViewOrientation(containerId, action) {
  if (action === "reset") {
    return applyProviderMapDefaultOrientation(containerId);
  }
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  if (!instance) return false;

  try {
    if (provider === "tencent") {
      if (typeof instance.setViewMode === "function") instance.setViewMode("3D");
      if (action === "pitch-up" || action === "pitch-down") {
        const pitch = getProvider3DViewNumber(instance, "getPitch", "pitch", 55);
        const delta = action === "pitch-up" ? 10 : -10;
        const nextPitch = clampProvider3DViewPitch(pitch + delta, 80);
        if (typeof instance.pitchTo === "function") {
          instance.pitchTo(nextPitch, { duration: 180 });
        } else if (typeof instance.setPitch === "function") {
          instance.setPitch(nextPitch);
        }
        return true;
      }
      if (action === "rotate-left" || action === "rotate-right") {
        const rotation = getProvider3DViewNumber(instance, "getRotation", "rotation", 0);
        const delta = action === "rotate-left" ? -30 : 30;
        const nextRotation = normalizeProvider3DViewRotation(rotation + delta);
        if (typeof instance.rotateTo === "function") {
          instance.rotateTo(nextRotation, { duration: 180 });
        } else if (typeof instance.setRotation === "function") {
          instance.setRotation(nextRotation);
        }
        return true;
      }
    }
    if (provider === "baidu") {
      if (action === "pitch-up" || action === "pitch-down") {
        const tilt = getProvider3DViewNumber(instance, "getTilt", "tilt", 55);
        const delta = action === "pitch-up" ? 10 : -10;
        const nextTilt = clampProvider3DViewPitch(tilt + delta, 87);
        if (typeof instance.setTilt === "function") instance.setTilt(nextTilt, { duration: 180 });
        return true;
      }
      if (action === "rotate-left" || action === "rotate-right") {
        const heading = getProvider3DViewNumber(instance, "getHeading", "heading", 0);
        const delta = action === "rotate-left" ? -30 : 30;
        const nextHeading = normalizeProvider3DViewRotation(heading + delta);
        if (typeof instance.setHeading === "function") {
          instance.setHeading(nextHeading, { duration: 180 });
        }
        return true;
      }
    }
  } catch (e) {
    logMessage_Warning(`[地图] 调整${containerId} 3D视角失败:`, e);
  }
  return false;
}

function attachProvider3DViewControlHandler(containerId) {
  ["reset", "pitch-up", "pitch-down", "rotate-left", "rotate-right"].forEach((action) => {
    const button = document.getElementById(getProvider3DViewControlButtonId(containerId, action));
    if (!button || button._provider3DViewBound) return;
    button.addEventListener("click", () => {
      adjustProvider3DViewOrientation(containerId, action);
    });
    button._provider3DViewBound = true;
  });
}

function getProvider3DViewControlMarkup(buttonId) {
  const baseId = buttonId.replace(/-btn$/, "");
  const pitchUpId = `${baseId}-pitch-up-btn`;
  const pitchDownId = `${baseId}-pitch-down-btn`;
  const rotateLeftId = `${baseId}-rotate-left-btn`;
  const rotateRightId = `${baseId}-rotate-right-btn`;
  return `
    <div class="provider-3d-view-controlbar relative w-[78px] h-[78px] rounded-full bg-white/90 shadow-lg border border-slate-200 text-slate-500 select-none">
      <button id="${pitchUpId}" type="button" class="absolute top-1 left-1/2 -translate-x-1/2 w-5 h-5 flex items-center justify-center rounded-full hover:bg-slate-100 transition-colors" title="增大俯仰角" aria-label="增大俯仰角">
        <svg class="w-3.5 h-3.5" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 4l4 5H4l4-5z" fill="#94a3b8"></path></svg>
      </button>
      <button id="${rotateLeftId}" type="button" class="absolute left-2 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-100 transition-colors" title="向左旋转" aria-label="向左旋转">
        <svg class="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8.8 7.2A7 7 0 0 1 19 13.4" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-linecap="round"></path><path d="M8 3.8v4.8h4.8" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      </button>
      <button id="${buttonId}" type="button" class="provider-3d-view-btn absolute left-1/2 top-1/2 w-11 h-11 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center rounded-full bg-white/95 shadow-inner hover:bg-slate-50 transition-colors" title="复位3D视角" aria-label="复位3D视角">
        <svg class="provider-3d-view-icon w-9 h-9" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
          <circle cx="24" cy="24" r="18" fill="#f8fafc" stroke="#cbd5e1" stroke-width="2"></circle>
          <path d="M24 8l6.5 18.5L24 23.5l-6.5 3L24 8z" fill="#ef4444"></path>
          <path d="M24 40l-5.5-14.5L24 28l5.5-2.5L24 40z" fill="#94a3b8"></path>
          <path d="M24 4v5M24 39v5M4 24h5M39 24h5" stroke="#94a3b8" stroke-width="2.5" stroke-linecap="round"></path>
          <circle cx="24" cy="24" r="4" fill="#ffffff" stroke="#94a3b8" stroke-width="1.5"></circle>
        </svg>
      </button>
      <button id="${rotateRightId}" type="button" class="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center rounded-full hover:bg-slate-100 transition-colors" title="向右旋转" aria-label="向右旋转">
        <svg class="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M15.2 7.2A7 7 0 0 0 5 13.4" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-linecap="round"></path><path d="M16 3.8v4.8h-4.8" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      </button>
      <button id="${pitchDownId}" type="button" class="absolute bottom-1 left-1/2 -translate-x-1/2 w-5 h-5 flex items-center justify-center rounded-full hover:bg-slate-100 transition-colors" title="减小俯仰角" aria-label="减小俯仰角">
        <svg class="w-3.5 h-3.5" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M8 12L4 7h8l-4 5z" fill="#94a3b8"></path></svg>
      </button>
    </div>
  `;
}

function renderProvider3DViewControlOverlay(overlay, buttonId) {
  overlay.dataset.providerMapViewControl = "true";
  overlay.dataset.providerMapViewControlVersion = "compass-v1";
  overlay.className =
    "absolute top-4 left-3 z-[1000] bg-white/85 backdrop-blur-sm rounded-full shadow-md flex items-center p-1 border border-slate-200";
  overlay.innerHTML = getProvider3DViewControlMarkup(buttonId);
}

function ensureProvider3DViewControl(containerId) {
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  if (provider === "baidu" || provider === "tencent") {
    removeProvider3DViewControl(containerId);
    return;
  }
  const container = document.getElementById(containerId);
  if (!container) return;
  const buttonId = getProvider3DViewButtonId(containerId);
  const existingButton = document.getElementById(buttonId);

  if (provider !== "baidu" && provider !== "tencent") {
    removeProvider3DViewControl(containerId);
    return;
  }

  if (existingButton && isElementInsideContainer(container, existingButton)) {
    const existingOverlay = existingButton.parentNode;
    if (
      existingOverlay &&
      existingOverlay.dataset &&
      existingOverlay.dataset.providerMapViewControl === "true"
    ) {
      renderProvider3DViewControlOverlay(existingOverlay, buttonId);
    }
    attachProvider3DViewControlHandler(containerId);
    return;
  }
  removeElementOrParentOverlay(existingButton);

  const overlay = document.createElement("div");
  renderProvider3DViewControlOverlay(overlay, buttonId);
  container.appendChild(overlay);
  attachProvider3DViewControlHandler(containerId);
}

function getProviderMapZoomLevelElementId(containerId) {
  return containerId === "multi-map-container" ? "multi-zoom-level" : "zoom-level";
}

function formatProviderMapZoomLevel(zoom) {
  const value = Number(zoom);
  if (!Number.isFinite(value)) return "";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function updateProviderMapZoomLabel(containerId) {
  const label = document.getElementById(getProviderMapZoomLevelElementId(containerId));
  const instance = getProviderMapInstance(containerId);
  if (!label || !instance) return false;
  let zoom;
  try {
    if (typeof instance.getZoom === "function") {
      zoom = instance.getZoom();
    } else if (Number.isFinite(Number(instance.zoom))) {
      zoom = instance.zoom;
    }
  } catch (e) {
    logMessage_Warning(`[地图] 读取${containerId}缩放等级失败:`, e);
    return false;
  }
  const text = formatProviderMapZoomLevel(zoom);
  if (!text) return false;
  label.textContent = text;
  return true;
}

function bindProviderMapZoomEvent(instance, eventName, handler) {
  if (!instance || !eventName || typeof handler !== "function") {
    return false;
  }
  if (typeof instance.on === "function") {
    instance.on(eventName, handler);
    return true;
  }
  if (typeof instance.addEventListener === "function") {
    instance.addEventListener(eventName, handler);
    return true;
  }
  return false;
}

function bindProviderMapZoomSync(containerId, provider, instance) {
  if (!instance) return false;
  if (!instance.__providerZoomSyncBound) {
    const eventNames =
      provider === "tencent"
        ? ["zoom", "zoomend"]
        : provider === "baidu"
          ? ["zoomend", "zoom_changed"]
          : provider === "tianditu"
            ? ["zoomend", "zoom"]
            : [];
    const syncZoom = () => {
      updateProviderMapZoomLabel(containerId);
    };
    let hasBoundEvent = false;
    eventNames.forEach((eventName) => {
      hasBoundEvent = bindProviderMapZoomEvent(instance, eventName, syncZoom) || hasBoundEvent;
    });
    instance.__providerZoomSyncBound = hasBoundEvent;
  }
  updateProviderMapZoomLabel(containerId);
  return true;
}

function bindTaskMapSdkInteractionTracking(containerId, instance) {
  if (!instance || instance.__taskMapAutoResetSdkBound) {
    return !!(instance && instance.__taskMapAutoResetSdkBound);
  }
  const handler = () => {
    scheduleTaskMapAutoResetAfterUserInteraction(containerId);
  };
  const eventNames = [
    "dragstart",
    "dragend",
  ];
  let hasBoundEvent = false;
  eventNames.forEach((eventName) => {
    hasBoundEvent = bindProviderMapZoomEvent(instance, eventName, handler) || hasBoundEvent;
  });
  instance.__taskMapAutoResetSdkBound = hasBoundEvent;
  return hasBoundEvent;
}

function bindTaskMapUserInteractionTracking(containerId, target) {
  if (!target || target.__taskMapAutoResetDomBound || typeof target.addEventListener !== "function") {
    return false;
  }
  const handler = () => {
    scheduleTaskMapAutoResetAfterUserInteraction(containerId);
  };
  ["mousedown", "pointerdown", "touchstart", "wheel"].forEach((eventName) => {
    const options = eventName === "wheel" ? { passive: true } : true;
    target.addEventListener(eventName, handler, options);
  });
  target.__taskMapAutoResetDomBound = true;
  return true;
}

function enableTianDiTuRightDragPan(containerId, instance) {
  const surface = getProviderMapSurface(containerId);
  if (!surface || surface._providerTianDiTuRightDragBound || !instance) return;

  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  surface.addEventListener("mousedown", (event) => {
    if (getActiveMapProvider() !== "tianditu" || !event || event.button !== 2) return;
    dragging = true;
    lastX = Number(event.clientX) || 0;
    lastY = Number(event.clientY) || 0;
    if (typeof event.preventDefault === "function") event.preventDefault();
    if (typeof event.stopPropagation === "function") event.stopPropagation();
  });

  document.addEventListener("mousemove", (event) => {
    if (!dragging || !event) return;
    const currentX = Number(event.clientX) || lastX;
    const currentY = Number(event.clientY) || lastY;
    const dx = currentX - lastX;
    const dy = currentY - lastY;
    lastX = currentX;
    lastY = currentY;
    const activeInstance = getProviderMapInstance(containerId);
    if (activeInstance && typeof activeInstance.panBy === "function" && (dx || dy)) {
      activeInstance.panBy(dx, dy);
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
    }
    if (typeof event.preventDefault === "function") event.preventDefault();
    if (typeof event.stopPropagation === "function") event.stopPropagation();
  });

  document.addEventListener("mouseup", (event) => {
    if (!dragging) return;
    dragging = false;
    if (event && typeof event.preventDefault === "function") event.preventDefault();
    if (event && typeof event.stopPropagation === "function") event.stopPropagation();
  });

  surface._providerTianDiTuRightDragBound = true;
}

function configureTencentNativeViewControls(instance) {
  if (!instance || typeof instance.removeControl !== "function") {
    return false;
  }
  const defaults =
    window.TMap &&
    window.TMap.constants &&
    window.TMap.constants.DEFAULT_CONTROL_ID
      ? window.TMap.constants.DEFAULT_CONTROL_ID
      : {};
  const controlIds = [
    defaults.SCALE || "scale",
    defaults.ZOOM || "zoom",
  ].filter((id) => id !== undefined && id !== null && id !== "");
  let changed = false;

  controlIds.forEach((id) => {
    try {
      if (typeof instance.getControl === "function" && !instance.getControl(id)) {
        return;
      }
      instance.removeControl(id);
      changed = true;
    } catch (e) {
      logMessage_Warning(`[地图] 移除腾讯地图默认控件失败(${id}):`, e);
    }
  });

  const rotationId = defaults.ROTATION || "rotation";
  try {
    const rotationControl =
      typeof instance.getControl === "function" ? instance.getControl(rotationId) : null;
    const positions =
      window.TMap && window.TMap.constants && window.TMap.constants.CONTROL_POSITION
        ? window.TMap.constants.CONTROL_POSITION
        : {};
    if (rotationControl && typeof rotationControl.setPosition === "function") {
      rotationControl.setPosition(positions.TOP_LEFT || "top-left");
      changed = true;
    }
    if (rotationControl && typeof rotationControl.setClassName === "function") {
      rotationControl.setClassName("provider-tencent-native-rotation-control");
    }
  } catch (e) {
    logMessage_Warning("[地图] 设置腾讯地图原生视角控件位置失败:", e);
  }
  return changed;
}

function enableProviderMapInteractions(containerId, provider, instance) {
  if (!instance) return;
  try {
    if (provider === "tencent") {
      if (typeof instance.setDraggable === "function") instance.setDraggable(true);
      if (typeof instance.setScrollable === "function") instance.setScrollable(true);
      if (typeof instance.setPitchable === "function") instance.setPitchable(true);
      if (typeof instance.setRotatable === "function") instance.setRotatable(true);
      configureTencentNativeViewControls(instance);
    } else if (provider === "baidu") {
      if (typeof instance.enableScrollWheelZoom === "function") instance.enableScrollWheelZoom(true);
      if (typeof instance.enableRotate === "function") instance.enableRotate();
      if (typeof instance.enableTilt === "function") instance.enableTilt();
      if (typeof instance.enableRotateGestures === "function") instance.enableRotateGestures();
      if (typeof instance.enableTiltGestures === "function") instance.enableTiltGestures();
      addBaiduProvider3DControl(instance);
    } else if (provider === "tianditu") {
      if (typeof instance.enableDrag === "function") instance.enableDrag();
      if (typeof instance.enableScrollWheelZoom === "function") instance.enableScrollWheelZoom();
      enableTianDiTuRightDragPan(containerId, instance);
    }
  } catch (e) {
    logMessage_Warning(`[地图] 启用${containerId}地图交互失败:`, e);
  }
}

function ensureProviderMapContextMenuGuard(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const bindGuard = (target) => {
    if (!target || target._providerMapContextMenuGuardBound) return;
    target.addEventListener("contextmenu", (event) => {
      if (getActiveMapProvider() !== "amap" && event && typeof event.preventDefault === "function") {
        event.preventDefault();
      }
    }, true);
    target._providerMapContextMenuGuardBound = true;
  };
  bindGuard(container);
  bindGuard(getProviderMapSurface(containerId));
}

function getTianDiTuToken() {
  return getMapProviderKeyRequirement("tianditu").value;
}

function createTianDiTuTileLayer(layerName, maxZoom = 18) {
  if (!window.T || typeof T.TileLayer !== "function") return null;
  const token = encodeURIComponent(getTianDiTuToken());
  const layer = new T.TileLayer("", {
    minZoom: 1,
    maxZoom,
  });
  layer.getTileUrl = function (tile) {
    const subdomain = Math.floor(Math.random() * 8);
    return `https://t${subdomain}.tianditu.gov.cn/${layerName}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${layerName}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&tk=${token}&TILECOL=${tile.x}&TILEROW=${tile.y}&TILEMATRIX=${tile.z}`;
  };
  return layer;
}

function applyTianDiTuDefaultMapType(instance) {
  if (!instance || !window.T || typeof T.MapType !== "function") return;
  const vectorLayer = createTianDiTuTileLayer("vec");
  const labelLayer = createTianDiTuTileLayer("cva");
  if (!vectorLayer || !labelLayer) return;
  try {
    instance.setMapType(new T.MapType([vectorLayer, labelLayer], "TIANDITU_VECTOR_APP"));
  } catch (e) {
    logMessage_Warning("[地图] 设置天地图默认底图失败:", e);
  }
}

function initProviderMap(containerId, isMultiAccount = false) {
  applyPendingMapProviderConfigIfAny();
  const provider = getActiveMapProvider();
  if (provider === "amap") {
    return false;
  }

  const container = document.getElementById(containerId);
  if (!container) {
    return false;
  }

  const center = getProviderMapDefaultCenter();
  const providerCenter = convertGcj02ToProviderCoordinates(provider, center);
  const zoom = getProviderMapDefaultZoom(provider);
  let instance = providerMapInstances[containerId];
  if (instance && providerMapInstanceProviders[containerId] !== provider) {
    destroyProviderMapInstance(containerId);
    instance = null;
  }
  let surface = getProviderMapSurface(containerId);
  if (instance && (!surface || surface.parentNode !== container)) {
    destroyProviderMapInstance(containerId);
    instance = null;
  }
  surface = ensureProviderMapSurface(containerId, !instance);
  if (!surface) {
    return false;
  }

  try {
    if (provider === "tencent") {
      if (!window.TMap || !window.TMap.Map || !window.TMap.LatLng) {
        throw new Error("腾讯地图运行时未加载");
      }
      if (!instance) {
        instance = new TMap.Map(surface, {
          center: new TMap.LatLng(providerCenter.lat, providerCenter.lng),
          zoom,
          pitch: 55,
          rotation: 0,
          viewMode: "3D",
          draggable: true,
          scrollable: true,
          pitchable: true,
          rotatable: true,
          showControl: true,
        });
        providerMapInstances[containerId] = instance;
      } else {
        instance.setCenter(new TMap.LatLng(providerCenter.lat, providerCenter.lng));
        instance.setZoom(zoom);
      }
      if (!providerMapEventsBound[containerId] && typeof instance.on === "function") {
        instance.on("click", (event) => {
          const latLng = event && event.latLng ? event.latLng : null;
          if (!latLng) return;
          const lat = typeof latLng.getLat === "function" ? latLng.getLat() : latLng.lat;
          const lng = typeof latLng.getLng === "function" ? latLng.getLng() : latLng.lng;
          logMessage_Info(`[地图] 腾讯地图点击坐标: ${Number(lng).toFixed(6)}, ${Number(lat).toFixed(6)}`);
        });
        providerMapEventsBound[containerId] = true;
      }
    } else if (provider === "tianditu") {
      if (!window.T || !window.T.Map || !window.T.LngLat) {
        throw new Error("天地图运行时未加载");
      }
      if (!instance) {
        instance = new T.Map(surface.id);
        providerMapInstances[containerId] = instance;
        applyTianDiTuDefaultMapType(instance);
      }
      if (!providerMapEventsBound[containerId] && typeof instance.addEventListener === "function") {
        instance.addEventListener("click", (event) => {
          const lngLat = event && event.lnglat ? event.lnglat : null;
          if (!lngLat) return;
          const lng = typeof lngLat.getLng === "function" ? lngLat.getLng() : lngLat.lng;
          const lat = typeof lngLat.getLat === "function" ? lngLat.getLat() : lngLat.lat;
          logMessage_Info(`[地图] 天地图点击坐标: ${Number(lng).toFixed(6)}, ${Number(lat).toFixed(6)}`);
        });
        providerMapEventsBound[containerId] = true;
      }
    } else if (provider === "baidu") {
      if (!window.BMapGL || typeof window.BMapGL.Map !== "function") {
        throw new Error("百度地图运行时未加载");
      }
      if (!instance) {
        instance = new BMapGL.Map(surface.id, {
          forceRenderType: "webgl",
          showControls: false,
          enableIconClick: false,
          enableDragging: true,
          enableWheelZoom: true,
          enableRotate: true,
          enableTilt: true,
          displayOptions: {
            poi: true,
            poiText: true,
            poiIcon: true,
            building: true,
          },
        });
        providerMapInstances[containerId] = instance;
      }
      if (!providerMapEventsBound[containerId] && typeof instance.addEventListener === "function") {
        instance.addEventListener("click", (event) => {
          const point = event && event.point ? event.point : null;
          if (!point) return;
          logMessage_Info(`[地图] 百度地图点击坐标: ${Number(point.lng).toFixed(6)}, ${Number(point.lat).toFixed(6)}`);
        });
        providerMapEventsBound[containerId] = true;
      }
    } else {
      throw new Error(`不支持的地图提供方: ${provider}`);
    }

    providerMapInstanceProviders[containerId] = provider;
    enableProviderMapInteractions(containerId, provider, instance);
    applyProviderMapDefaultView(containerId);
    ensureProviderMapContextMenuGuard(containerId);
    ensureProvider3DViewControl(containerId);
    if (containerId === "map-container") {
      ensureSingleControls();
    } else if (containerId === "multi-map-container") {
      ensureMultiControls();
    }
    bindProviderMapZoomSync(containerId, provider, instance);
    bindTaskMapSdkInteractionTracking(containerId, instance);
    bindTaskMapUserInteractionTracking(containerId, getProviderMapSurface(containerId));
    bindTaskMapUserInteractionTracking(containerId, document.getElementById(containerId));
    logMessage_Info(`[地图] ${getMapProviderDisplayName(provider)}前端地图已加载: ${containerId}`);
    return true;
  } catch (error) {
    logMessage_Error(`[地图] ${getMapProviderDisplayName(provider)}前端地图初始化失败:`, error);
    renderMapProviderFrontendPlaceholder(containerId, isMultiAccount, error.message || "初始化失败");
    return false;
  }
}
