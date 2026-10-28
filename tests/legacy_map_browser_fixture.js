// Opt-in real SDK fixture. Credentials are supplied only as runtime arguments.
(function () {
  "use strict";

  const frame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const clone = value => JSON.parse(JSON.stringify(value));
  const baseCoords = [
    [116.397128, 39.916527], [116.397428, 39.916527], [116.397728, 39.916527],
    [116.398128, 39.916527], [116.398528, 39.916527],
  ];
  let scriptsReady;

  function script(url) {
    return new Promise((resolve, reject) => {
      const element = document.createElement("script");
      element.src = url;
      element.onload = resolve;
      element.onerror = () => reject(new Error("Legacy production script failed to load"));
      document.head.appendChild(element);
    });
  }

  function readPoint(point) {
    if (!point) return null;
    if (Array.isArray(point)) return point.map(Number);
    return [
      Number(typeof point.getLng === "function" ? point.getLng() : point.lng),
      Number(typeof point.getLat === "function" ? point.getLat() : point.lat),
    ];
  }

  window.mountLegacyMapAcceptance = async function (options) {
    if (window.legacyMapAcceptance) await window.legacyMapAcceptance.destroy();
    const {provider, key, securityJsCode = "", sessionId, mobile = false, frontendProxyEnabled = true} = options;
    if (!["amap", "tencent", "baidu", "tianditu"].includes(provider)) {
      throw new Error("Unsupported legacy fixture provider");
    }
    const keyField = {amap: "js_key", tencent: "map_key", baidu: "ak", tianditu: "token"}[provider];
    window.APP_CONFIG = {
      map_provider: provider, frontend_proxy_enabled: frontendProxyEnabled,
      map_providers: {[provider]: {[keyField]: key, security_js_code: securityJsCode}},
    };
    Object.assign(window, {
      AMAP_API_KEY: provider === "amap" ? key : "", AMapInstance: window.AMap,
      map: null, multiAccountMap: null, mobileTrackMapInstance: null,
      providerMapInstances: {}, providerMapInstanceProviders: {}, providerMapEventsBound: {},
      providerMapOverlays: {}, providerMapLastFitCoords: {}, providerRunnerMarkers: {},
      tencentMapLoadingPromise: null, tiandituMapLoadingPromise: null, baiduMapLoadingPromise: null,
      currentRunData: {}, singleRunProgressVisualActive: false, backgroundTaskPollInterval: null,
      ensureSingleControls() {}, ensureMultiControls() {},
      getApiRequestSessionHeaderValue: () => sessionId,
      getAdminViewOriginSessionUUID: () => "",
      loadAMapOnce: async () => window.AMap,
      installGenericMapRuntimeGuards: () => { window.__genericMapRuntimeGuardsInstalled = true; },
      escapeHtml: value => String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
      })[char]),
    });
    let renderErrors = 0;
    window.logMessage_Info = () => {};
    window.logMessage_Warning = () => {};
    window.logMessage_Error = () => { renderErrors++; };
    if (!scriptsReady) {
      const base = options.scriptBase || "/legacy-scripts/";
      scriptsReady = script(base + "legacy-map-runtime.js")
        .then(() => script(base + "legacy-map-render.js"));
    }
    await scriptsReady;
    if (!await ensureActiveMapProviderRuntimeIfNeeded("acceptance")) {
      throw new Error("Legacy runtime initialization failed");
    }
    const host = document.createElement("section");
    host.id = "legacy-acceptance-root";
    host.style.cssText = "position:fixed;top:0;left:0;z-index:2000;display:block;background:white;margin:0;max-width:100vw;width:" +
      (mobile ? "375px" : "900px") + ";height:420px";
    const container = document.createElement("div");
    const containerId = mobile ? "mobile-map-container" : "map-container";
    container.id = containerId;
    container.style.cssText = "position:relative;width:100%;height:100%;overflow:hidden";
    host.appendChild(container);
    document.body.appendChild(host);
    let nativeMap;
    if (provider === "amap") {
      nativeMap = new AMap.Map(containerId, {center: baseCoords[0], zoom: 17, viewMode: "2D"});
      window.map = nativeMap;
    } else {
      if (!initProviderMap(containerId)) throw new Error("Legacy native map initialization failed");
      nativeMap = getProviderMapInstance(containerId);
    }
    let cameraWrites = 0;
    const originals = new Map();
    for (const name of ["setFitView", "setCenter", "setZoom", "setViewport", "centerAndZoom", "fitBounds"]) {
      if (typeof nativeMap[name] !== "function") continue;
      const original = nativeMap[name];
      originals.set(name, original);
      nativeMap[name] = function (...args) {
        cameraWrites++;
        return original.apply(this, args);
      };
    }
    let coords = clone(baseCoords);
    let destroyed = false;
    const expectedPoint = coord => {
      const point = Array.isArray(coord) ? {lng: coord[0], lat: coord[1]} : coord;
      const converted = convertGcj02ToProviderCoordinates(provider, point);
      if (provider === "tianditu") return readPoint(new T.LngLat(converted.lng, converted.lat));
      return [converted.lng, converted.lat];
    };
    const markerPosition = marker => {
      if (!marker) return null;
      if (typeof marker.getGeometries === "function") return readPoint(marker.getGeometries()[0]?.position);
      if (typeof marker.getPosition === "function") return readPoint(marker.getPosition());
      if (typeof marker.getLngLat === "function") return readPoint(marker.getLngLat());
      return null;
    };
    function snapshot() {
      const cached = providerRouteSegmentOverlays[containerId];
      const lines = [];
      const colors = [];
      for (const line of cached ? (Array.isArray(cached.lines) ? cached.lines : [cached.lines]) : []) {
        if (typeof line.getGeometries === "function") {
          for (const geometry of line.getGeometries()) {
            if (geometry.paths) lines.push(geometry.paths.map(readPoint));
            colors.push(geometry.styleId || "");
          }
        } else {
          const path = typeof line.getPath === "function" ? line.getPath() : line.getLngLats?.();
          if (Array.isArray(path)) lines.push(path.map(readPoint));
          colors.push(line.getStrokeColor?.() || line.getColor?.() || line.getOptions?.().strokeColor || "");
        }
      }
      const runner = markerPosition(providerRunnerMarkers[containerId]);
      const runnerIndex = Number(window.currentRunData.current_point_index || 0) - 1;
      return {
        provider, mobile, lines, colors, points: runner ? [runner] : [], runner,
        lineCount: lines.length, overlayCount: getProviderOverlayBucket(containerId).length,
        center: readPoint(nativeMap.getCenter()), zoom: Number(nativeMap.getZoom()), cameraWrites,
        expectedRunner: runnerIndex >= 0 ? expectedPoint(coords[runnerIndex]) : null,
        businessPoint: runnerIndex >= 0 ? clone(coords[runnerIndex]) : null,
        expectedRoute: coords.map(expectedPoint), taskIndex: window.currentRunData.task_index,
        width: container.clientWidth, height: container.clientHeight, renderErrors,
      };
    }
    async function render() {
      drawProviderTaskOnMap(containerId, window.currentRunData);
      const index = Number(window.currentRunData.current_point_index || 0) - 1;
      if (index >= 0) updateProviderRunnerMarker(containerId, coords[index]);
      await frame();
      return snapshot();
    }
    window.legacyMapAcceptance = {
      ready: () => !destroyed && !!getProviderMapInstance(containerId) && container.clientWidth > 0,
      seed: async (taskIndex = 0, pointIndex = 0) => {
        coords = baseCoords.map(([lng, lat]) => [lng, lat + taskIndex * 0.0008]);
        clearProviderRunnerMarkers(containerId);
        window.singleRunProgressVisualActive = false;
        window.currentRunData = {
          task_index: taskIndex, run_coords: clone(coords), current_point_index: pointIndex,
          target_points: [clone(coords[2]), clone(coords[4])], target_point_names: "Midpoint|Finish",
        };
        if (pointIndex > 0) {
          window.singleRunProgressVisualActive = true;
          window.currentRunData.current_position = clone(coords[pointIndex - 1]);
        }
        return render();
      },
      progress: async index => {
        if (!Number.isInteger(index) || index < 1 || index > coords.length) throw new Error("Invalid fixture progress index");
        window.singleRunProgressVisualActive = true;
        Object.assign(window.currentRunData, {current_point_index: index, current_position: clone(coords[index - 1])});
        return render();
      },
      finish: async () => { window.currentRunData.status = 1; return render(); },
      moveView: async () => {
        const point = expectedPoint([baseCoords[0][0] + 0.004, baseCoords[0][1] + 0.003]);
        if (provider === "tencent") nativeMap.setCenter(new TMap.LatLng(point[1], point[0]));
        else if (provider === "baidu") nativeMap.setCenter(new BMap.Point(...point));
        else if (provider === "tianditu") nativeMap.panTo(new T.LngLat(...point));
        else nativeMap.setCenter(point);
        nativeMap.setZoom(16);
        await new Promise(resolve => setTimeout(resolve, 250));
        return snapshot();
      },
      snapshot, expectedPoint,
      destroy: async () => {
        if (destroyed) return;
        destroyed = true;
        clearTaskMapAutoResetTimer();
        let released = false;
        try {
          if (provider === "amap") {
            clearProviderMapOverlays(containerId, {clearRunnerMarkers: true});
            nativeMap.destroy();
            window.map = null;
          } else {
            if (await destroyProviderMapInstance(containerId) === false) throw new Error("Legacy SDK destruction failed");
            if (typeof waitForProviderMapDestruction === "function" && await waitForProviderMapDestruction(containerId) === false) {
              throw new Error("Legacy SDK destruction failed");
            }
          }
          released = true;
        } finally {
          for (const [name, original] of originals) nativeMap[name] = original;
          if (released) host.remove();
        }
        return {instrumentation_restored: true};
      },
    };
    await frame();
    return {provider, mobile, width: container.clientWidth, height: container.clientHeight};
  };
})();
