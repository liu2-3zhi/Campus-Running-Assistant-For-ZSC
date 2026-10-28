// Drive the actual legacy multi-account marker functions with isolated accounts.
(function () {
  'use strict';
  let scriptsReady;
  const frame = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const readPoint = point => !point ? null : Array.isArray(point) ? point.map(Number) : [
    Number(typeof point.getLng === 'function' ? point.getLng() : point.lng),
    Number(typeof point.getLat === 'function' ? point.getLat() : point.lat),
  ];
  const load = url => new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = url;
    script.onload = resolve; script.onerror = () => reject(new Error('Legacy multi-account production script failed'));
    document.head.appendChild(script);
  });

  window.mountMultiMapAcceptance = async options => {
    await window.multiMapAcceptance?.destroy();
    const {provider, key, securityJsCode = '', sessionId, mobile = false, frontendProxyEnabled = true} = options;
    const keyField = {amap: 'js_key', tencent: 'map_key', baidu: 'ak', tianditu: 'token'}[provider];
    if (!keyField) throw new Error('Unsupported legacy multi-account provider');
    window.APP_CONFIG = {map_provider: provider, frontend_proxy_enabled: frontendProxyEnabled,
      map_providers: {[provider]: {[keyField]: key, security_js_code: securityJsCode}}};
    Object.assign(window, {
      sessionUUID: sessionId, map: null, multiAccountMap: null, mobileTrackMapInstance: null,
      AMapInstance: window.AMap, multiAccountMarkers: {}, multiAccountMarkerColors: {}, colorIndex: 0,
      userColors: ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444'],
      providerMapInstances: {}, providerMapInstanceProviders: {}, providerMapEventsBound: {},
      providerMapOverlays: {}, providerMapLastFitCoords: {}, providerRunnerMarkers: {},
      tencentMapLoadingPromise: null, tiandituMapLoadingPromise: null, baiduMapLoadingPromise: null,
      currentRunData: {}, singleRunProgressVisualActive: false, backgroundTaskPollInterval: null,
      ensureSingleControls() {}, ensureMultiControls() {}, logMessage_Info() {}, logMessage_Warning() {},
      logMessage_Error(...args) { console.error(...args) },
      getApiRequestSessionHeaderValue: () => window.sessionUUID,
      getAdminViewOriginSessionUUID: () => '', loadAMapOnce: async () => {
        if (window.AMap) return window.AMap;
        window._AMapSecurityConfig = securityJsCode ? {securityJsCode} : {};
        if (!window.AMapLoader) await load('https://webapi.amap.com/loader.js');
        const sdk = await AMapLoader.load({key, version: '2.0', plugins: []});
        window.AMapInstance = sdk;
        return sdk;
      },
      installGenericMapRuntimeGuards: () => {},
      escapeHtml: value => String(value).replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char])),
    });
    if (!scriptsReady) scriptsReady = load('/legacy-scripts/legacy-map-runtime.js')
      .then(() => load('/legacy-scripts/legacy-map-render.js'))
      .then(() => load('/legacy-scripts/legacy-multi-accounts.js'));
    await scriptsReady;
    if (!await ensureActiveMapProviderRuntimeIfNeeded('multi-acceptance')) throw new Error('Legacy multi SDK initialization failed');
    const host = document.createElement('section');
    host.id = 'legacy-multi-acceptance-root'; host.style.cssText = 'position:fixed;inset:0;width:100vw;height:95vh';
    const container = document.createElement('div');
    // The production mobile multi-account view also uses this container ID.
    const containerId = 'multi-map-container'; container.id = containerId;
    container.style.cssText = 'position:relative;width:100%;height:100%';
    host.appendChild(container); document.body.appendChild(host);
    let nativeMap;
    try {
      if (provider === 'amap') {
        nativeMap = new AMap.Map(containerId, {center: [116.397128, 39.916527], zoom: 17});
        window.multiAccountMap = nativeMap;
      } else {
        const ready = initProviderMap(containerId, true);
        if (typeof waitForProviderMapReady === 'function') await waitForProviderMapReady(containerId);
        else if (!ready) throw new Error('Legacy multi map initialization failed');
        nativeMap = getProviderMapInstance(containerId);
        if (!nativeMap) throw new Error('Legacy multi map initialization returned no instance');
      }
    } catch (error) {
      if (provider !== 'amap') await destroyProviderMapInstance(containerId);
      host.remove();
      throw error;
    }
    let destroyed = false;
    let positions = {};
    const identities = new WeakMap(); let nextIdentity = 0;
    const markerEntries = () => provider === 'amap' ? Object.entries(multiAccountMarkers)
      : Object.entries(providerRunnerMarkers).filter(([key]) => key.startsWith(containerId + ':')).map(([key, value]) => [key.slice(containerId.length + 1), value]);
    const markerPoint = marker => readPoint(marker?.getGeometries?.()[0]?.position || marker?.getPosition?.() || marker?.getLngLat?.());
    const snapshot = () => ({provider, mobile, sessionId: window.sessionUUID,
      markerIds: markerEntries().map(([username]) => username).sort(),
      markers: Object.fromEntries(markerEntries().map(([username, marker]) => {
        if (!identities.has(marker)) identities.set(marker, ++nextIdentity);
        return [username, {point: markerPoint(marker), identity: identities.get(marker)}];
      })), businessPositions: JSON.parse(JSON.stringify(positions)), mapReady: !destroyed && !!getProviderMapInstance(containerId)});
    const expectedPoint = point => {
      const converted = convertGcj02ToProviderCoordinates(provider, {lng: point[0], lat: point[1]});
      return provider === 'tianditu' ? readPoint(new T.LngLat(converted.lng, converted.lat)) : [converted.lng, converted.lat];
    };
    window.multiMapAcceptance = {
      ready: () => !destroyed && !!getProviderMapInstance(containerId) && container.clientWidth > 0,
      snapshot, expectedPoint,
      seed: async nextPositions => {
        for (const username of Object.keys(positions)) if (!nextPositions[username]) multi_removeRunnerMarker(username);
        positions = JSON.parse(JSON.stringify(nextPositions));
        for (const [username, pos] of Object.entries(positions)) multi_updateRunnerPosition(username, pos.lon, pos.lat, pos.name || username);
        await frame(); return snapshot();
      },
      update: async (username, position) => {
        positions[username] = {...positions[username], ...position};
        multi_updateRunnerPosition(username, position.lon, position.lat, position.name || username);
        await frame(); return snapshot();
      },
      remove: async username => { delete positions[username]; multi_removeRunnerMarker(username); await frame(); return snapshot(); },
      // Navigation destroys the old map before changing the session. The caller remounts immediately.
      switchSession: async nextSession => {
        await window.multiMapAcceptance.destroy(); window.sessionUUID = nextSession;
        return {sessionId: nextSession, markerIds: markerEntries().map(([name]) => name), oldMarkersCleared: markerEntries().length === 0, remountRequired: true};
      },
      destroy: async () => {
        if (destroyed) return;
        destroyed = true;
        clearTaskMapAutoResetTimer();
        if (provider === 'amap') {
          for (const username of Object.keys(positions)) multi_removeRunnerMarker(username);
          nativeMap.destroy(); window.multiAccountMap = null;
        } else if (await destroyProviderMapInstance(containerId) === false) throw new Error('Legacy multi map destruction failed');
        host.remove(); positions = {};
        return {rootEmpty: !document.getElementById(containerId), markersCleared: markerEntries().length === 0};
      },
    };
    await frame();
  };
})();
