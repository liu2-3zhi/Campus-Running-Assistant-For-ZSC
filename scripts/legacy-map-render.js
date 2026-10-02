// Provider map coordinate conversion and route rendering helpers.

const MAP_COORD_PI = Math.PI;
const MAP_COORD_X_PI = Math.PI * 3000.0 / 180.0;
const MAP_COORD_A = 6378245.0;
const MAP_COORD_EE = 0.00669342162296594323;

function isCoordinateOutOfChina(lng, lat) {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
}

function transformMapCoordLat(x, y) {
  let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  ret += (20.0 * Math.sin(6.0 * x * MAP_COORD_PI) + 20.0 * Math.sin(2.0 * x * MAP_COORD_PI)) * 2.0 / 3.0;
  ret += (20.0 * Math.sin(y * MAP_COORD_PI) + 40.0 * Math.sin(y / 3.0 * MAP_COORD_PI)) * 2.0 / 3.0;
  ret += (160.0 * Math.sin(y / 12.0 * MAP_COORD_PI) + 320 * Math.sin(y * MAP_COORD_PI / 30.0)) * 2.0 / 3.0;
  return ret;
}

function transformMapCoordLng(x, y) {
  let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  ret += (20.0 * Math.sin(6.0 * x * MAP_COORD_PI) + 20.0 * Math.sin(2.0 * x * MAP_COORD_PI)) * 2.0 / 3.0;
  ret += (20.0 * Math.sin(x * MAP_COORD_PI) + 40.0 * Math.sin(x / 3.0 * MAP_COORD_PI)) * 2.0 / 3.0;
  ret += (150.0 * Math.sin(x / 12.0 * MAP_COORD_PI) + 300.0 * Math.sin(x / 30.0 * MAP_COORD_PI)) * 2.0 / 3.0;
  return ret;
}

function wgs84ToGcj02(lng, lat) {
  lng = Number(lng);
  lat = Number(lat);
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || isCoordinateOutOfChina(lng, lat)) {
    return { lng, lat };
  }
  let dLat = transformMapCoordLat(lng - 105.0, lat - 35.0);
  let dLng = transformMapCoordLng(lng - 105.0, lat - 35.0);
  const radLat = lat / 180.0 * MAP_COORD_PI;
  let magic = Math.sin(radLat);
  magic = 1 - MAP_COORD_EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / ((MAP_COORD_A * (1 - MAP_COORD_EE)) / (magic * sqrtMagic) * MAP_COORD_PI);
  dLng = (dLng * 180.0) / (MAP_COORD_A / sqrtMagic * Math.cos(radLat) * MAP_COORD_PI);
  return { lng: lng + dLng, lat: lat + dLat };
}

function gcj02ToWgs84(lng, lat) {
  lng = Number(lng);
  lat = Number(lat);
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || isCoordinateOutOfChina(lng, lat)) {
    return { lng, lat };
  }
  let minLng = lng - 0.02;
  let maxLng = lng + 0.02;
  let minLat = lat - 0.02;
  let maxLat = lat + 0.02;
  let resultLng = lng;
  let resultLat = lat;
  for (let i = 0; i < 32; i += 1) {
    resultLng = (minLng + maxLng) / 2;
    resultLat = (minLat + maxLat) / 2;
    const converted = wgs84ToGcj02(resultLng, resultLat);
    const diffLng = converted.lng - lng;
    const diffLat = converted.lat - lat;
    if (Math.abs(diffLng) < 1e-10 && Math.abs(diffLat) < 1e-10) {
      break;
    }
    if (diffLng > 0) {
      maxLng = resultLng;
    } else {
      minLng = resultLng;
    }
    if (diffLat > 0) {
      maxLat = resultLat;
    } else {
      minLat = resultLat;
    }
  }
  return { lng: resultLng, lat: resultLat };
}

function gcj02ToBd09(lng, lat) {
  lng = Number(lng);
  lat = Number(lat);
  const z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * MAP_COORD_X_PI);
  const theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * MAP_COORD_X_PI);
  return {
    lng: z * Math.cos(theta) + 0.0065,
    lat: z * Math.sin(theta) + 0.006,
  };
}

function bd09ToGcj02(lng, lat) {
  lng = Number(lng);
  lat = Number(lat);
  const x = lng - 0.0065;
  const y = lat - 0.006;
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * MAP_COORD_X_PI);
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * MAP_COORD_X_PI);
  return {
    lng: z * Math.cos(theta),
    lat: z * Math.sin(theta),
  };
}

function renderMapProviderFrontendPlaceholder(containerId, isMultiAccount = false, errorReason = "") {
  const container = document.getElementById(containerId);
  if (!container) {
    return false;
  }
  const provider = getActiveMapProvider();
  const displayName = getMapProviderDisplayName();
  const requirement = getMapProviderKeyRequirement(provider);
  const hasKey = !!requirement.value;
  let statusHtml;
  if (!hasKey) {
    statusHtml = `
      <p class="text-sm font-medium text-amber-600">${displayName}未配置 ${requirement.fieldLabel}</p>
      <p class="text-xs mt-1">请在系统设置中配置${displayName} ${requirement.fieldLabel}以显示地图。</p>
      <p class="text-xs mt-1 text-slate-400">路线规划仍由后端执行。</p>`;
  } else if (errorReason) {
    statusHtml = `
      <p class="text-sm font-medium text-red-500">${displayName}加载失败</p>
      <p class="text-xs mt-1">${errorReason}</p>
      <p class="text-xs mt-1 text-slate-400">路线规划仍由后端执行。</p>`;
  } else {
    statusHtml = `
      <p class="text-sm font-medium">${displayName}已启用</p>
      <p class="text-xs mt-1">路线规划由后端按当前地图供应商执行。</p>`;
  }
  container.innerHTML = `
    <div class="absolute inset-0 flex items-center justify-center text-slate-500 bg-slate-50/80">
      <div class="text-center px-4">
        <svg class="w-12 h-12 mx-auto mb-2 ${hasKey ? "text-sky-300" : "text-amber-400"}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
        </svg>
        ${statusHtml}
      </div>
    </div>
  `;
  return true;
}

function cloneMapCoordinate(coord) {
  const normalized = normalizeRouteCoord(coord);
  return { lng: normalized.lng, lat: normalized.lat };
}

function convertMapCoordinatesToGcj02(provider, coord) {
  if (!coord) return coord;
  const normalizedProvider = String(provider || getActiveMapProvider()).trim().toLowerCase();
  const normalizedCoord = cloneMapCoordinate(coord);
  if (normalizedProvider === "tianditu") {
    return wgs84ToGcj02(normalizedCoord.lng, normalizedCoord.lat);
  }
  if (normalizedProvider === "baidu") {
    return bd09ToGcj02(normalizedCoord.lng, normalizedCoord.lat);
  }
  return normalizedCoord;
}

function convertGcj02ToProviderCoordinates(provider, coord) {
  if (!coord) return coord;
  const normalizedProvider = String(provider || getActiveMapProvider()).trim().toLowerCase();
  const normalizedCoord = cloneMapCoordinate(coord);
  if (normalizedProvider === "tianditu") {
    return gcj02ToWgs84(normalizedCoord.lng, normalizedCoord.lat);
  }
  if (normalizedProvider === "baidu") {
    return gcj02ToBd09(normalizedCoord.lng, normalizedCoord.lat);
  }
  return normalizedCoord;
}

function normalizeRouteCoord(coord) {
  if (Array.isArray(coord)) {
    return { lng: Number(coord[0]), lat: Number(coord[1]) };
  }
  if (coord && typeof coord === "object") {
    return {
      lng: Number(coord.lng ?? coord.lon ?? coord.longitude),
      lat: Number(coord.lat ?? coord.latitude),
    };
  }
  return { lng: NaN, lat: NaN };
}

function isRouteSegmentSeparator(coord) {
  const normalized = normalizeRouteCoord(coord);
  return (
    Number.isFinite(normalized.lng) &&
    Number.isFinite(normalized.lat) &&
    Math.abs(normalized.lng) < 1e-9 &&
    Math.abs(normalized.lat) < 1e-9
  );
}

function normalizeRouteCoords(coords) {
  if (!Array.isArray(coords)) return [];
  return coords
    .map(normalizeRouteCoord)
    .filter((coord) => Number.isFinite(coord.lng) && Number.isFinite(coord.lat));
}

function splitRouteCoordsIntoDrawableSegments(coords) {
  if (!Array.isArray(coords)) return [];
  const segments = [];
  let currentSegment = [];
  coords.forEach((rawCoord) => {
    if (isRouteSegmentSeparator(rawCoord)) {
      if (currentSegment.length > 0) {
        segments.push(currentSegment);
        currentSegment = [];
      }
      return;
    }
    const coord = normalizeRouteCoord(rawCoord);
    if (Number.isFinite(coord.lng) && Number.isFinite(coord.lat)) {
      currentSegment.push(coord);
    }
  });
  if (currentSegment.length > 0) {
    segments.push(currentSegment);
  }
  return segments.filter((segment) => segment.length > 0);
}

function getProviderMapInstance(containerId) {
  const provider = getActiveMapProvider();
  if (provider === "amap") {
    if (containerId === "mobile-track-map-container") {
      return mobileTrackMapInstance;
    }
    if (containerId === "multi-map-container") {
      return multiAccountMap;
    }
    return map;
  }
  return providerMapInstances[containerId];
}

function fitProviderMapToCoordinates(containerId, coords, overlay = null) {
  const provider = getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  if (!instance || !Array.isArray(coords) || coords.length === 0) return;
  try {
    if (provider === "amap") {
      const overlays = Array.isArray(overlay)
        ? overlay
        : overlay
          ? [overlay]
          : coords.map((coord) => new AMapInstance.LngLat(coord.lng, coord.lat));
      instance.setFitView(overlays, false, [60, 60, 60, 60]);
    } else if (provider === "tencent") {
      const bounds = new TMap.LatLngBounds();
      coords.forEach((coord) => bounds.extend(new TMap.LatLng(coord.lat, coord.lng)));
      instance.fitBounds(bounds, { padding: 60 });
    } else if (provider === "tianditu" && typeof instance.setViewport === "function") {
      instance.setViewport(coords.map((coord) => new T.LngLat(coord.lng, coord.lat)));
    } else if (provider === "baidu" && typeof instance.setViewport === "function" && window.BMapGL) {
      instance.setViewport(coords.map((coord) => new BMapGL.Point(coord.lng, coord.lat)));
    }
  } catch (e) {
    logMessage_Warning(`[地图] 调整${containerId}视野失败:`, e);
  }
}

function zoomProviderMap(containerId, delta) {
  const instance = getProviderMapInstance(containerId);
  if (!instance) return false;
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  try {
    if (provider === "tencent" && typeof instance.getZoom === "function" && typeof instance.setZoom === "function") {
      instance.setZoom(instance.getZoom() + delta);
      updateProviderMapZoomLabel(containerId);
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
      return true;
    }
    if (typeof instance.zoomBy === "function") {
      instance.zoomBy(delta);
      updateProviderMapZoomLabel(containerId);
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
      return true;
    }
    if (delta > 0 && typeof instance.zoomIn === "function") {
      instance.zoomIn();
      updateProviderMapZoomLabel(containerId);
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
      return true;
    }
    if (delta < 0 && typeof instance.zoomOut === "function") {
      instance.zoomOut();
      updateProviderMapZoomLabel(containerId);
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
      return true;
    }
    if (typeof instance.getZoom === "function" && typeof instance.setZoom === "function") {
      instance.setZoom(instance.getZoom() + delta);
      updateProviderMapZoomLabel(containerId);
      scheduleTaskMapAutoResetAfterUserInteraction(containerId);
      return true;
    }
  } catch (e) {
    logMessage_Warning(`[地图] 调整${containerId}缩放失败:`, e);
  }
  return false;
}

function fitProviderMapToLastRoute(containerId) {
  const coords = providerMapLastFitCoords[containerId] || [];
  if (coords.length > 0) {
    fitProviderMapToCoordinates(containerId, coords);
    applyProviderMapDefaultOrientation(containerId);
    return true;
  }
  const instance = getProviderMapInstance(containerId);
  if (instance && typeof instance.setFitView === "function") {
    try {
      instance.setFitView();
      return true;
    } catch (e) {
      logMessage_Warning(`[地图] 调整${containerId}视野失败:`, e);
    }
  }
  return applyProviderMapDefaultView(containerId);
}

function escapeProviderSvgText(value) {
  return String(value || "").replace(/[&<>\u0022\u0027]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[char]);
}

function normalizeProviderMarkerLabel(options = {}) {
  const label = typeof options.label === "string" ? options.label.trim() : "";
  if (label) return label;
  const title = typeof options.title === "string" ? options.title.trim() : "";
  if (title) return title;
  return "";
}

function resolveProviderMarkerColor(options = {}) {
  if (typeof options.markerColor === "string" && options.markerColor.trim()) {
    return options.markerColor.trim();
  }
  if (options.markerStatus === "completed") return "#94a3b8";
  if (options.markerStatus === "current") return "#0284c7";
  if (options.markerStatus === "start") return "#10b981";
  if (options.markerStatus === "end") return "#ef4444";

  const content = String(options.content || "");
  const inlineColor = content.match(/background-color:\s*([^;\u0022\u0027]+)/i);
  if (inlineColor && inlineColor[1]) {
    return inlineColor[1].trim();
  }
  if (content.includes("bg-slate-400")) return "#94a3b8";
  if (content.includes("bg-sky-600")) return "#0284c7";
  if (content.includes("bg-emerald-600")) return "#059669";

  return options.anchor === "center" ? "#2563eb" : "#059669";
}

function createTencentMarkerStyleOptions(label, options = {}) {
  const markerKind = options.markerKind || (options.anchor === "center" ? "runner" : "label");
  const color = resolveProviderMarkerColor(options);
  if (markerKind === "runner") {
    const svg = [
      '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">',
      '<circle cx="14" cy="14" r="10" fill="#ffffff" opacity="0.95"/>',
      '<circle cx="14" cy="14" r="7" fill="' + color + '"/>',
      '<circle cx="14" cy="14" r="12" fill="none" stroke="' + color + '" stroke-width="2" opacity="0.32"/>',
      '</svg>',
    ].join("");
    return {
      width: 28,
      height: 28,
      anchor: { x: 14, y: 14 },
      src: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
    };
  }

  const visibleLabel = Array.from(label || "标记").slice(0, 10).join("");
  const safeLabel = escapeProviderSvgText(visibleLabel);
  const textLength = Math.max(2, Array.from(visibleLabel).length);
  const width = Math.min(144, Math.max(48, 26 + textLength * 14));
  const height = 38;
  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    '<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#0f172a" flood-opacity="0.22"/></filter></defs>',
    '<g filter="url(#shadow)">',
    `<rect x="1" y="1" width="${width - 2}" height="26" rx="13" fill="${color}"/>`,
    `<path d="M ${width / 2 - 5} 27 L ${width / 2} 36 L ${width / 2 + 5} 27 Z" fill="${color}"/>`,
    '</g>',
    `<text x="${width / 2}" y="18" text-anchor="middle" font-size="12" font-weight="700" font-family="Arial, sans-serif" fill="#ffffff">${safeLabel}</text>`,
    '</svg>',
  ].join("");
  return {
    width,
    height,
    anchor: { x: width / 2, y: height },
    src: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
  };
}

function createProviderLabelMarkerSvgOptions(label, options = {}) {
  const visibleLabel = Array.from(label || "标记").slice(0, 10).join("");
  const safeLabel = escapeProviderSvgText(visibleLabel);
  const color = resolveProviderMarkerColor(options);
  const textLength = Math.max(2, Array.from(visibleLabel).length);
  const width = Math.min(144, Math.max(48, 26 + textLength * 14));
  const height = 38;
  const svg = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    '<defs><filter id="shadow" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#0f172a" flood-opacity="0.22"/></filter></defs>',
    '<g filter="url(#shadow)">',
    `<rect x="1" y="1" width="${width - 2}" height="26" rx="13" fill="${color}"/>`,
    `<path d="M ${width / 2 - 5} 27 L ${width / 2} 36 L ${width / 2 + 5} 27 Z" fill="${color}"/>`,
    '</g>',
    `<text x="${width / 2}" y="18" text-anchor="middle" font-size="12" font-weight="700" font-family="Arial, sans-serif" fill="#ffffff">${safeLabel}</text>`,
    '</svg>',
  ].join("");
  return {
    width,
    height,
    anchor: { x: width / 2, y: height },
    src: `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
  };
}

function addProviderMarker(containerId, coord, options = {}) {
  const provider = getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  if (!instance || !coord) return null;
  const providerCoord = convertGcj02ToProviderCoordinates(provider, coord);
  const bucket = getProviderOverlayBucket(containerId);
  let marker = null;
  try {
    if (provider === "amap" && AMapInstance) {
      marker = new AMapInstance.Marker({
        position: new AMapInstance.LngLat(coord.lng, coord.lat),
        content: options.content,
        anchor: options.anchor || "bottom-center",
        zIndex: options.zIndex || 100,
        map: instance,
      });
    } else if (provider === "tencent" && window.TMap) {
      const label = normalizeProviderMarkerLabel(options);
      const markerStyleOptions = createTencentMarkerStyleOptions(label, options);
      const styleId = "marker";
      marker = new TMap.MultiMarker({
        id: `provider-marker-${containerId}-${Date.now()}-${bucket.length}`,
        map: instance,
        zIndex: options.zIndex || 100,
        styles: {
          [styleId]: new TMap.MarkerStyle(markerStyleOptions),
        },
        geometries: [{
          id: options.geometryId || `marker-${Date.now()}-${bucket.length}`,
          styleId,
          position: new TMap.LatLng(providerCoord.lat, providerCoord.lng),
          rank: options.zIndex || 100,
          properties: { title: options.title || label },
        }],
      });
    } else if (provider === "tianditu" && window.T) {
      const label = normalizeProviderMarkerLabel(options);
      const markerKind = options.markerKind || (options.anchor === "center" ? "runner" : "label");
      const markerOptions = {
        title: options.title || label || "",
        zIndexOffset: options.zIndex || 100,
      };
      if (label && markerKind !== "runner" && typeof T.Icon === "function") {
        const iconOptions = createProviderLabelMarkerSvgOptions(label, options);
        markerOptions.icon = new T.Icon({
          iconUrl: iconOptions.src,
          iconSize:
            typeof T.Point === "function"
              ? new T.Point(iconOptions.width, iconOptions.height)
              : [iconOptions.width, iconOptions.height],
          iconAnchor:
            typeof T.Point === "function"
              ? new T.Point(iconOptions.anchor.x, iconOptions.anchor.y)
              : [iconOptions.anchor.x, iconOptions.anchor.y],
        });
      }
      marker = new T.Marker(
        new T.LngLat(providerCoord.lng, providerCoord.lat),
        markerOptions,
      );
      instance.addOverLay(marker);
    } else if (provider === "baidu" && window.BMapGL) {
      const label = normalizeProviderMarkerLabel(options);
      const markerKind = options.markerKind || (options.anchor === "center" ? "runner" : "label");
      marker = new BMapGL.Marker(
        new BMapGL.Point(providerCoord.lng, providerCoord.lat),
        {
          title: options.title || label || "",
          zIndex: options.zIndex || 100,
        },
      );
      if (
        label &&
        markerKind !== "runner" &&
        typeof BMapGL.Label === "function" &&
        typeof BMapGL.Size === "function" &&
        typeof marker.setLabel === "function"
      ) {
        marker.setLabel(
          new BMapGL.Label(label, {
            offset: new BMapGL.Size(12, -24),
          }),
        );
      }
      instance.addOverlay(marker);
    }
    if (marker) {
      if (options.trackOverlay !== false) {
        bucket.push(marker);
      }
      if (options.trackFit !== false) {
        const fitCoords = providerMapLastFitCoords[containerId] || [];
        fitCoords.push(providerCoord);
        providerMapLastFitCoords[containerId] = fitCoords;
      }
    }
    return marker;
  } catch (e) {
    logMessage_Warning(`[地图] 添加${containerId}标记失败:`, e);
    return null;
  }
}

function updateProviderRunnerMarker(containerId, coord, options = {}) {
  const normalized = normalizeRouteCoord(coord);
  if (!Number.isFinite(normalized.lng) || !Number.isFinite(normalized.lat)) {
    return null;
  }
  const markerKey = options.markerKey || containerId;
  const previousMarker = providerRunnerMarkers[markerKey];
  const provider = providerMapInstanceProviders[containerId] || getActiveMapProvider();
  if (
    previousMarker &&
    provider === "tencent" &&
    window.TMap &&
    (typeof previousMarker.updateGeometries === "function" ||
      typeof previousMarker.setGeometries === "function")
  ) {
    try {
      const providerCoord = convertGcj02ToProviderCoordinates(provider, normalized);
      const label = normalizeProviderMarkerLabel(options);
      const nextGeometry = {
        id: options.geometryId || markerKey,
        styleId: "marker",
        position: new TMap.LatLng(providerCoord.lat, providerCoord.lng),
        rank: options.zIndex || 200,
        properties: {
          title: options.title || label,
        },
      };
      if (typeof previousMarker.updateGeometries === "function") {
        previousMarker.updateGeometries([nextGeometry]);
      } else {
        previousMarker.setGeometries([nextGeometry]);
      }
      return previousMarker;
    } catch (e) {
      logMessage_Warning(`[地图] 更新${containerId}腾讯标记失败，将重建标记:`, e);
    }
  }
  if (
    previousMarker &&
    provider === "tianditu" &&
    window.T &&
    typeof previousMarker.setLngLat === "function"
  ) {
    try {
      const providerCoord = convertGcj02ToProviderCoordinates(provider, normalized);
      previousMarker.setLngLat(new T.LngLat(providerCoord.lng, providerCoord.lat));
      return previousMarker;
    } catch (e) {
      logMessage_Warning(`[地图] 更新${containerId}天地图标记失败，将重建标记:`, e);
    }
  }
  if (
    previousMarker &&
    provider === "baidu" &&
    window.BMapGL &&
    typeof previousMarker.setPosition === "function"
  ) {
    try {
      const providerCoord = convertGcj02ToProviderCoordinates(provider, normalized);
      previousMarker.setPosition(new BMapGL.Point(providerCoord.lng, providerCoord.lat));
      return previousMarker;
    } catch (e) {
      logMessage_Warning(`[地图] 更新${containerId}百度标记失败，将重建标记:`, e);
    }
  }
  if (previousMarker) {
    removeProviderOverlayFromMap(containerId, previousMarker);
  }
  const title = options.title || "当前位置";
  const content = options.content || '<div class="w-5 h-5 rounded-full border-2 border-white shadow-lg" style="background:linear-gradient(135deg,var(--base-color-300),var(--base-color-600));"></div>';
  const marker = addProviderMarker(containerId, normalized, {
    title,
    label: options.label,
    content,
    anchor: options.anchor || "center",
    zIndex: options.zIndex || 200,
    markerColor: options.markerColor,
    markerKind: options.markerKind,
    geometryId: options.geometryId || markerKey,
    trackFit: false,
    trackOverlay: false,
  });
  if (marker) {
    providerRunnerMarkers[markerKey] = marker;
  } else {
    delete providerRunnerMarkers[markerKey];
  }
  return marker;
}

function resolveRunnerTargetSequence(targetSequence, data = currentRunData) {
  const incomingSequence = Number.isFinite(+targetSequence)
    ? Math.floor(+targetSequence) + 1
    : 1;
  const existingSequence = Number.isFinite(+data?.target_sequence)
    ? Math.floor(+data.target_sequence)
    : 0;
  const mergedSequence = Math.max(incomingSequence, existingSequence || incomingSequence);
  const sequenceData = Object.assign({}, data || {}, {
    target_sequence: mergedSequence,
  });
  return resolveTaskProgressSequence(sequenceData, sequenceData.run_coords || []);
}

function drawProviderRouteOnMap(containerId, coords, options = {}) {
  const provider = getActiveMapProvider();
  const instance = getProviderMapInstance(containerId);
  const routeSegments = Array.isArray(options.routeSegments)
    ? options.routeSegments
        .map((segment) => ({
          styleId: segment.styleId || "route",
          coords: normalizeRouteCoords(segment.coords || segment.path || []),
        }))
        .filter((segment) => segment.coords.length > 0)
    : splitRouteCoordsIntoDrawableSegments(coords).map((segment) => ({
        styleId: "route",
        coords: segment,
      }));
  const gcjSegments = routeSegments.map((segment) => segment.coords);
  const gcjCoords = gcjSegments.flat();
  if (!instance || gcjSegments.length === 0 || gcjCoords.length === 0) return null;

  clearProviderMapOverlays(containerId);

  const providerSegments = routeSegments.map((segment) => ({
    styleId: segment.styleId || "route",
    coords: segment.coords.map((coord) =>
      convertGcj02ToProviderCoordinates(provider, coord),
    ),
  }));
  const providerCoords = providerSegments.flatMap((segment) => segment.coords);
  providerMapLastFitCoords[containerId] = providerCoords;
  const bucket = getProviderOverlayBucket(containerId);
  let line = null;
  let fitOverlay = null;
  const color = options.strokeColor || options.color || "#ef4444";
  const weight = options.strokeWeight || options.weight || 5;
  try {
    if (provider === "amap" && AMapInstance) {
      line = routeSegments.map((segment) => {
        const segmentColor = resolveProviderRouteSegmentColor(
          segment.styleId,
          color,
          options,
        );
        const polyline = new AMapInstance.Polyline({
          path: segment.coords.map((coord) => new AMapInstance.LngLat(coord.lng, coord.lat)),
          strokeColor: segmentColor,
          strokeWeight: weight,
          strokeOpacity: options.strokeOpacity ?? 0.85,
          zIndex: options.zIndex || 50,
        });
        instance.add(polyline);
        bucket.push(polyline);
        return polyline;
      });
      fitOverlay = line;
    } else if (provider === "tencent" && window.TMap) {
      const styleConfigs = {
        route: {
          color,
          width: weight,
          borderWidth: 0,
          lineCap: "round",
        },
        active: {
          color: resolveProviderRouteSegmentColor("active", color, options),
          width: weight,
          borderWidth: 0,
          lineCap: "round",
        },
        current: {
          color: resolveProviderRouteSegmentColor("current", color, options),
          width: Math.max(weight, 6),
          borderWidth: 0,
          lineCap: "round",
        },
        completed: {
          color: resolveProviderRouteSegmentColor("completed", color, options),
          width: Math.max(3, weight - 1),
          borderWidth: 0,
          lineCap: "round",
        },
      };
      const styles = {};
      providerSegments.forEach((segment) => {
        const styleId = segment.styleId || "route";
        if (!styles[styleId]) {
          styles[styleId] = new TMap.PolylineStyle(
            styleConfigs[styleId] || styleConfigs.route,
          );
        }
      });
      line = new TMap.MultiPolyline({
        id: `provider-route-${containerId}`,
        map: instance,
        styles,
        geometries: providerSegments.map((segment, index) => ({
          id: `route-${index}`,
          styleId: segment.styleId || "route",
          paths: segment.coords.map((coord) => new TMap.LatLng(coord.lat, coord.lng)),
        })),
      });
      bucket.push(line);
      fitOverlay = line;
    } else if (provider === "tianditu" && window.T) {
      line = providerSegments.map((segment) => {
        const segmentColor = resolveProviderRouteSegmentColor(
          segment.styleId,
          color,
          options,
        );
        const polyline = new T.Polyline(
          segment.coords.map((coord) => new T.LngLat(coord.lng, coord.lat)),
          {
            color: segmentColor,
            weight,
            opacity: options.strokeOpacity ?? 0.85,
            lineStyle: options.strokeStyle === "dashed" ? "dashed" : "solid",
          },
        );
        instance.addOverLay(polyline);
        bucket.push(polyline);
        return polyline;
      });
    } else if (provider === "baidu" && window.BMapGL) {
      line = providerSegments.map((segment) => {
        const segmentColor = resolveProviderRouteSegmentColor(
          segment.styleId,
          color,
          options,
        );
        const polyline = new BMapGL.Polyline(
          segment.coords.map((coord) => new BMapGL.Point(coord.lng, coord.lat)),
          {
            strokeColor: segmentColor,
            strokeWeight: weight,
            strokeOpacity: options.strokeOpacity ?? 0.85,
          },
        );
        instance.addOverlay(polyline);
        bucket.push(polyline);
        return polyline;
      });
    }

    if (line) {
      if (options.showEndpoints !== false && gcjCoords.length > 0) {
        addProviderMarker(containerId, gcjCoords[0], {
          title: "起点",
          label: "起点",
          markerStatus: "start",
          markerColor: "#10b981",
        });
        if (gcjCoords.length > 1) {
          addProviderMarker(containerId, gcjCoords[gcjCoords.length - 1], {
            title: "终点",
            label: "终点",
            markerStatus: "end",
            markerColor: "#ef4444",
          });
        }
      }
      fitProviderMapToCoordinates(containerId, providerCoords, fitOverlay);
    }
    return line;
  } catch (e) {
    logMessage_Error(`[地图] 绘制${getMapProviderDisplayName(provider)}路线失败:`, e);
    return null;
  }
}

function getSingleProviderMapContainerIds() {
  const containerIds = [];
  if (getProviderMapInstance("map-container")) {
    containerIds.push("map-container");
  }
  if (getProviderMapInstance("mobile-map-container")) {
    containerIds.push("mobile-map-container");
  }
  if (containerIds.length === 0) {
    containerIds.push("map-container");
  }
  return containerIds;
}

function estimateProviderCoordDistanceMeters(firstCoord, secondCoord) {
  const first = normalizeRouteCoord(firstCoord);
  const second = normalizeRouteCoord(secondCoord);
  if (
    !Number.isFinite(first.lng) ||
    !Number.isFinite(first.lat) ||
    !Number.isFinite(second.lng) ||
    !Number.isFinite(second.lat)
  ) {
    return Number.POSITIVE_INFINITY;
  }
  const avgLatRad = ((first.lat + second.lat) / 2) * Math.PI / 180;
  const lngMeters = (first.lng - second.lng) * Math.cos(avgLatRad) * 111320;
  const latMeters = (first.lat - second.lat) * 110540;
  return Math.sqrt(lngMeters * lngMeters + latMeters * latMeters);
}

function getProviderMarkerDisplayCoord(coord, routeCoords, options = {}) {
  const normalized = normalizeRouteCoord(coord);
  if (!Number.isFinite(normalized.lng) || !Number.isFinite(normalized.lat)) {
    return normalized;
  }
  if (!Array.isArray(routeCoords) || routeCoords.length === 0) {
    return normalized;
  }
  const maxDistanceMeters = Number.isFinite(+options.maxDistanceMeters)
    ? +options.maxDistanceMeters
    : 80;
  const avoidExactRouteEndpoint = options.avoidExactRouteEndpoint === true;
  let best = null;
  routeCoords.forEach((routeCoordRaw, routeIndex) => {
    const routeCoord = normalizeRouteCoord(routeCoordRaw);
    if (!Number.isFinite(routeCoord.lng) || !Number.isFinite(routeCoord.lat)) {
      return;
    }
    const isRouteEndpoint =
      routeIndex === 0 || routeIndex === routeCoords.length - 1;
    const isExactSame =
      Math.abs(routeCoord.lng - normalized.lng) <= 1e-7 &&
      Math.abs(routeCoord.lat - normalized.lat) <= 1e-7;
    if (avoidExactRouteEndpoint && isRouteEndpoint && isExactSame) {
      return;
    }
    const distanceMeters = estimateProviderCoordDistanceMeters(normalized, routeCoord);
    if (!best || distanceMeters < best.distanceMeters) {
      best = { coord: routeCoord, distanceMeters };
    }
  });
  if (best && best.distanceMeters <= maxDistanceMeters) {
    return best.coord;
  }
  return normalized;
}

function findNearestProviderRouteIndex(routeCoords, coord, minIndex = 0) {
  const normalized = normalizeRouteCoord(coord);
  if (
    !Array.isArray(routeCoords) ||
    !Number.isFinite(normalized.lng) ||
    !Number.isFinite(normalized.lat)
  ) {
    return -1;
  }
  let best = null;
  const startIndex = Math.max(0, Math.min(routeCoords.length - 1, minIndex));
  for (let index = startIndex; index < routeCoords.length; index += 1) {
    const routeCoord = normalizeRouteCoord(routeCoords[index]);
    if (!Number.isFinite(routeCoord.lng) || !Number.isFinite(routeCoord.lat)) {
      continue;
    }
    const distanceMeters = estimateProviderCoordDistanceMeters(normalized, routeCoord);
    if (!best || distanceMeters < best.distanceMeters) {
      best = { index, distanceMeters };
    }
  }
  return best ? best.index : -1;
}

function resolveRouteProgressIndex(data, routeCoords) {
  const route = normalizeRouteCoords(routeCoords);
  if (route.length === 0) return -1;
  const rawPointIndex = Number(
    data?.current_point_index ??
      data?.currentPositionPointIndex ??
      data?.processed_points,
  );
  if (Number.isFinite(rawPointIndex) && rawPointIndex > 0) {
    return Math.max(0, Math.min(route.length - 1, Math.floor(rawPointIndex) - 1));
  }
  const currentPosition = normalizeRouteCoord(data?.current_position);
  if (
    Number.isFinite(currentPosition.lng) &&
    Number.isFinite(currentPosition.lat)
  ) {
    return findNearestProviderRouteIndex(route, currentPosition, 0);
  }
  return -1;
}

function resolveTaskProgressSequence(data, routeCoords = []) {
  const targetPoints = Array.isArray(data?.target_points)
    ? data.target_points
        .map(normalizeRouteCoord)
        .filter((coord) => Number.isFinite(coord.lng) && Number.isFinite(coord.lat))
    : [];
  const totalTargets = targetPoints.length;
  const configuredSequence = Number(data?.target_sequence);
  let sequence =
    Number.isFinite(configuredSequence) && configuredSequence > 0
      ? Math.floor(configuredSequence)
      : data?.status == 1 && totalTargets > 0
        ? totalTargets + 1
        : 0;
  const route = normalizeRouteCoords(
    Array.isArray(routeCoords) && routeCoords.length > 0
      ? routeCoords
      : data?.run_coords || [],
  );
  const progressIndex = resolveRouteProgressIndex(data, route);
  if (progressIndex >= 0 && totalTargets > 0 && route.length > 0) {
    let minRouteIndex = 0;
    let inferredCompletedTargets = 0;
    targetPoints.forEach((point, index) => {
      const routeIndex = findNearestProviderRouteIndex(route, point, minRouteIndex);
      if (routeIndex < 0) return;
      if (routeIndex < progressIndex) {
        inferredCompletedTargets = index + 1;
      }
      minRouteIndex = routeIndex;
    });
    sequence = Math.max(sequence, inferredCompletedTargets + 1);
  }
  if (totalTargets > 0 && sequence > 0) {
    sequence = Math.min(sequence, totalTargets + 1);
  }
  return Math.max(0, sequence);
}

function hasActiveRouteProgress(data) {
  if (!data) return false;
  if (data.status == 1) return true;
  return singleRunProgressVisualActive === true;
}

function resolveVisualTaskProgressSequence(data, routeCoords = []) {
  const totalTargets = Array.isArray(data?.target_points)
    ? data.target_points.length
    : 0;
  if (!hasActiveRouteProgress(data)) {
    return data?.status == 1 && totalTargets > 0 ? totalTargets + 1 : 0;
  }
  return resolveTaskProgressSequence(data, routeCoords);
}

function getProviderRouteProgressStatus(targetOrdinal, sequence, totalTargets) {
  if (sequence > totalTargets) {
    return "completed";
  }
  if (sequence > 0 && targetOrdinal < sequence) {
    return "completed";
  }
  if (sequence > 0 && targetOrdinal === sequence) {
    return "current";
  }
  return "active";
}

function resolveProviderRouteSegmentColor(styleId, fallbackColor, options = {}) {
  if (styleId === "completed") {
    return options.completedStrokeColor || "#94a3b8";
  }
  if (styleId === "current") {
    return options.currentStrokeColor || "#0284c7";
  }
  return fallbackColor;
}

function appendProviderRouteProgressSegment(segments, coords, styleId) {
  const normalizedCoords = normalizeRouteCoords(coords);
  if (normalizedCoords.length < 2) return;
  const lastSegment = segments[segments.length - 1];
  if (lastSegment && lastSegment.styleId === styleId) {
    const lastCoord = lastSegment.coords[lastSegment.coords.length - 1];
    const firstCoord = normalizedCoords[0];
    const connects =
      Math.abs(lastCoord.lng - firstCoord.lng) <= 1e-7 &&
      Math.abs(lastCoord.lat - firstCoord.lat) <= 1e-7;
    lastSegment.coords = lastSegment.coords.concat(
      connects ? normalizedCoords.slice(1) : normalizedCoords,
    );
    return;
  }
  segments.push({ styleId, coords: normalizedCoords });
}

function buildProviderRouteProgressSegments(routeCoords, data) {
  const route = normalizeRouteCoords(routeCoords);
  if (route.length < 2) {
    return null;
  }
  const targetPoints = Array.isArray(data?.target_points)
    ? data.target_points
        .map(normalizeRouteCoord)
        .filter((coord) => Number.isFinite(coord.lng) && Number.isFinite(coord.lat))
    : [];
  const progressIndex = resolveRouteProgressIndex(data, route);
  if (progressIndex >= 0) {
    const completedEndIndex = Math.min(progressIndex, route.length - 1);
    const targetIndexes = [];
    let minRouteIndex = 0;
    targetPoints.forEach((point) => {
      const routeIndex = findNearestProviderRouteIndex(route, point, minRouteIndex);
      if (routeIndex >= 0) {
        targetIndexes.push(routeIndex);
        minRouteIndex = routeIndex;
      }
    });
    const segments = [];
    if (completedEndIndex > 0) {
      appendProviderRouteProgressSegment(
        segments,
        route.slice(0, completedEndIndex + 1),
        "completed",
      );
    }
    if (data?.status == 1) {
      appendProviderRouteProgressSegment(
        segments,
        route.slice(completedEndIndex),
        "completed",
      );
      return segments.length > 0 ? segments : null;
    }
    const nextTargetIndex = targetIndexes.find(
      (targetIndex) => targetIndex > completedEndIndex,
    );
    const currentEndIndex = Number.isFinite(nextTargetIndex)
      ? nextTargetIndex
      : route.length - 1;
    appendProviderRouteProgressSegment(
      segments,
      route.slice(completedEndIndex, currentEndIndex + 1),
      "current",
    );
    if (currentEndIndex < route.length - 1) {
      appendProviderRouteProgressSegment(
        segments,
        route.slice(currentEndIndex),
        "active",
      );
    }
    return segments.length > 0 ? segments : null;
  }
  if (targetPoints.length === 0) {
    return null;
  }
  const sequence = resolveTaskProgressSequence(data, route);
  const targetIndexes = [];
  let minRouteIndex = 0;
  targetPoints.forEach((point) => {
    const routeIndex = findNearestProviderRouteIndex(route, point, minRouteIndex);
    if (routeIndex >= 0) {
      targetIndexes.push(routeIndex);
      minRouteIndex = routeIndex;
    }
  });
  if (targetIndexes.length === 0) {
    return null;
  }

  const segments = [];
  let startIndex = 0;
  targetIndexes.forEach((targetIndex, index) => {
    const styleId = getProviderRouteProgressStatus(
      index + 1,
      sequence,
      targetPoints.length,
    );
    appendProviderRouteProgressSegment(
      segments,
      route.slice(startIndex, targetIndex + 1),
      styleId,
    );
    startIndex = Math.max(startIndex, targetIndex);
  });
  if (startIndex < route.length - 1) {
    const tailStyleId =
      sequence > targetPoints.length ? "completed" : "active";
    appendProviderRouteProgressSegment(segments, route.slice(startIndex), tailStyleId);
  }
  return segments.length > 0 ? segments : null;
}

function drawProviderTaskOnMap(containerId, data) {
  if (!data) return;
  const routeCoords = data.run_coords?.length
    ? data.run_coords
    : data.draft_coords?.length
      ? data.draft_coords
      : data.recommended_coords || [];
  if (routeCoords.length > 0) {
    drawProviderRouteOnMap(containerId, routeCoords, {
      strokeColor: data.run_coords?.length ? "#ef4444" : "#10b981",
      strokeWeight: data.run_coords?.length ? 5 : 4,
      strokeStyle: data.run_coords?.length ? "dashed" : "solid",
      showEndpoints: false,
      routeSegments:
        data.run_coords?.length && hasActiveRouteProgress(data)
          ? buildProviderRouteProgressSegments(routeCoords, data)
          : null,
    });
  } else {
    clearProviderMapOverlays(containerId);
  }
  if (Array.isArray(data.target_points)) {
    const sequence = resolveVisualTaskProgressSequence(data, routeCoords);
    const names = (data.target_point_names || "").split("|");
    const shouldSnapMarkerToRoute = getActiveMapProvider() !== "amap";
    data.target_points.forEach((point, index) => {
      const coord = normalizeRouteCoord(point);
      if (Number.isFinite(coord.lng) && Number.isFinite(coord.lat)) {
        let bgColor = "bg-emerald-600",
          markerColor = "#059669",
          markerStatus = "pending",
          zIndex = 100,
          pulseClass = "";
        if (index + 1 < sequence) {
          bgColor = "bg-slate-400";
          markerColor = "#94a3b8";
          markerStatus = "completed";
        } else if (index + 1 === sequence) {
          bgColor = "bg-sky-600";
          markerColor = "#0284c7";
          markerStatus = "current";
          zIndex = 110;
          pulseClass = "pulsing-marker";
        }
        const pointName = names[index] || `点 ${index + 1}`;
        const markerContent = `<div class="relative flex flex-col items-center pointer-events-none"><div class="${pulseClass} text-xs font-bold whitespace-nowrap px-2 py-1 rounded-full shadow-lg ${bgColor} text-white">${pointName}</div><div class="w-0 h-0 border-x-4 border-x-transparent border-t-4 ${bgColor.replace(
          "bg-",
          "border-t-",
        )}"></div></div>`;
        const markerCoord = shouldSnapMarkerToRoute
          ? getProviderMarkerDisplayCoord(coord, routeCoords, {
              avoidExactRouteEndpoint:
                index === 0 || index === data.target_points.length - 1,
            })
          : coord;
        addProviderMarker(containerId, markerCoord, {
          title: pointName,
          label: pointName,
          content: markerContent,
          anchor: "bottom-center",
          zIndex,
          markerColor,
          markerStatus,
        });
      }
    });
  }
}
