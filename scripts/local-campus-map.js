(function () {
  "use strict";

  const resource = "/api/local-map/";
  const sdkResource = resource + "sdk/";
  let sdkLoading;
  let nextLineId = 0;

  function sdkUrl(name, configId) {
    return sdkResource + name + (configId ? "?" + new URLSearchParams({ config_id: configId }) : "");
  }

  function asset(name, isStyle = false, configId = "") {
    return new Promise((resolve, reject) => {
      const node = document.createElement(isStyle ? "link" : "script");
      if (isStyle) {
        node.rel = "stylesheet";
        node.href = sdkUrl(name, configId);
      } else {
        node.src = sdkUrl(name, configId);
      }
      const timer = setTimeout(() => finish(new Error("校园离线地图组件加载超时")), 15000);
      function finish(error) {
        clearTimeout(timer);
        node.onload = node.onerror = null;
        if (error) {
          node.remove();
          reject(error);
        } else resolve(node);
      }
      node.onload = () => finish();
      node.onerror = () => finish(new Error("校园离线地图组件加载失败"));
      document.head.appendChild(node);
    });
  }

  async function load(configId) {
    if (!sdkLoading) {
      sdkLoading = Promise.allSettled([
        asset("maplibre-gl-csp.js", false, configId),
        asset("maplibre-gl.css", true, configId),
      ]).then((assets) => {
        if (assets.some(({ status }) => status === "rejected") || !window.maplibregl?.Map) {
          assets.forEach(({ value }) => value?.remove());
          throw new Error("校园离线地图组件加载失败");
        }
        return window.maplibregl;
      }).catch((error) => {
        sdkLoading = undefined;
        throw error;
      });
    }
    return sdkLoading;
  }

  async function create(host, { signal, configId } = {}) {
    const sdk = await load(configId);
    sdk.setWorkerUrl(new URL(sdkUrl("maplibre-gl-csp-worker.js", configId), location.origin).href);
    const timeout = AbortSignal.timeout(15000);
    const metadataUrl = resource + "map" + (configId ? "?" + new URLSearchParams({ config_id: configId }) : "");
    const response = await fetch(metadataUrl, {
      credentials: "same-origin",
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
    if (!response.ok) throw new Error("校园离线地图服务不可用");
    const { center, bounds, minzoom, maxzoom, version, coordinate_system: system,
      resource_context: context } = await response.json();
    if (system !== "GCJ-02" || !Array.isArray(center) || center.length !== 2 ||
        !center.every(Number.isFinite) || !Array.isArray(bounds) || bounds.length !== 4 ||
        !bounds.every(Number.isFinite) || !Number.isInteger(minzoom) || !Number.isInteger(maxzoom) ||
        minzoom < 0 || maxzoom < minzoom || maxzoom > 24 || typeof version !== "string" ||
        typeof context !== "string" || !context) {
      throw new Error("校园离线地图元数据无效");
    }
    if (signal?.aborted) throw signal.reason;
    const zoom = Math.min(maxzoom, Math.max(minzoom, 17));
    const tileQuery = new URLSearchParams({ v: version, context });
    const tileUrl = location.origin + resource + "tiles/{z}/{x}/{y}.png?" + tileQuery;
    const map = new sdk.Map({
      container: host,
      center,
      zoom,
      minZoom: minzoom,
      maxZoom: Math.max(zoom, Math.min(maxzoom + 2, 22)),
      renderWorldCopies: false,
      attributionControl: { compact: true },
      style: {
        version: 8,
        sources: {
          campus: {
            type: "raster",
            tiles: [tileUrl],
            tileSize: 256,
            // Limit raster requests while allowing the camera to fit labels at the edges.
            bounds, minzoom, maxzoom,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          },
        },
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#f5f4ef" } },
          { id: "campus", type: "raster", source: "campus" },
        ],
      },
    });
    map.once("style.load", () => { map.__campusStyleReady = true; });
    map.resetCampusView = () => map.jumpTo({ center, zoom, bearing: 0, pitch: 0 });
    try {
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => finish(new Error("校园离线底图加载超时")), 10000);
        const onLoad = () => finish();
        const onAbort = () => finish(signal.reason);
        function finish(error) {
          clearTimeout(timer);
          map.off("load", onLoad);
          signal?.removeEventListener("abort", onAbort);
          if (error) reject(error);
          else resolve();
        }
        map.on("load", onLoad);
        signal?.addEventListener("abort", onAbort, { once: true });
      });
    } catch (error) {
      map.remove();
      throw error;
    }
    return map;
  }

  function fit(map, coordinates) {
    const bounds = new window.maplibregl.LngLatBounds();
    for (const point of coordinates) bounds.extend(point);
    if (!bounds.isEmpty()) {
      const padding = Math.min(60, Math.max(10, (Math.min(map.getContainer().clientWidth, map.getContainer().clientHeight) - 20) / 4));
      map.fitBounds(bounds, { padding, maxZoom: Math.min(19, map.getMaxZoom()), duration: 0 });
    }
  }

  function addMarker(map, coordinate, options = {}) {
    const element = document.createElement("div");
    const anchor = options.anchor === "center" ? "center" : "bottom";
    const marker = new window.maplibregl.Marker({ element, anchor });
    function update(next) {
      element.replaceChildren();
      if (next.content instanceof HTMLElement) {
        element.appendChild(next.content);
      } else {
        const label = document.createElement("span");
        const color = next.markerColor || next.color || "#047857";
        label.textContent = next.label || next.title || "";
        if (anchor === "center") {
          Object.assign(label.style, { display: "block", width: "16px", height: "16px", border: "2px solid white",
            borderRadius: "50%", boxShadow: "0 1px 4px #334155", backgroundColor: color });
          label.textContent = "";
        } else {
          Object.assign(label.style, { display: "block", padding: "2px 6px", whiteSpace: "nowrap",
            borderRadius: "4px", backgroundColor: color, color: "white", fontSize: "12px" });
        }
        element.appendChild(label);
      }
      element.title = next.title || next.label || "";
      element.style.zIndex = String(next.zIndex || 100);
    }
    update(options);
    marker.updateCampusMarker = update;
    return marker.setLngLat(coordinate).addTo(map);
  }

  function addLine(map, coordinates, options = {}) {
    const id = "campus-path-" + ++nextLineId;
    const { weight = 5, opacity = 0.85, dashed = false } = options;
    let color = options.color || "#2563eb";
    function geometry() {
      // The progress renderer can represent a zero-length segment with one point.
      const path = coordinates.length === 1 ? [coordinates[0], coordinates[0]] : coordinates;
      return { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: path } };
    }
    function attach() {
      map.addSource(id, { type: "geojson", data: geometry() });
      map.addLayer({
        id, type: "line", source: id,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": color, "line-width": weight, "line-opacity": opacity,
          ...(dashed ? { "line-dasharray": [2, 2] } : {}),
        },
      });
    }
    if (map.__campusStyleReady || map.isStyleLoaded()) attach();
    else map.once("style.load", attach);
    return {
      setPath(path) {
        coordinates = path;
        map.getSource(id)?.setData(geometry());
      },
      setOptions({ strokeColor }) {
        color = strokeColor;
        if (map.getLayer(id)) map.setPaintProperty(id, "line-color", color);
      },
      remove() {
        map.off("style.load", attach);
        if (map.getLayer(id)) map.removeLayer(id);
        if (map.getSource(id)) map.removeSource(id);
      },
    };
  }

  window.ZXLocalCampusMap = Object.freeze({ load, create, fit, addMarker, addLine });
})();
