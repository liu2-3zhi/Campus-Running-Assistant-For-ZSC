(function installMapRequestProxy(globalScope, factory) {
  const api = factory(globalScope);
  if (typeof module === "object" && module.exports) module.exports = api;
  if (globalScope) globalScope.ZXMapRequestProxy = api;
})(typeof window !== "undefined" ? window : typeof self !== "undefined" ? self : globalThis, function createMapRequestProxy(globalScope) {
  "use strict";

  const DEFAULT_BASE_PATH = "/map-proxy";
  const CONTEXT_TIMEOUT_MS = 30000;
  const HOST_RULES = Object.freeze({
    amap: [/^webapi\.amap\.com$/, /^mapplugin\.amap\.com$/, /^restapi\.amap\.com$/, /^vdata\.amap\.com$/, /^a\.amap\.com$/, /^jsapi\.amap\.com$/, /^o4\.amap\.com$/, /^jsapi-data[1-5]\.amap\.com$/, /^(?:webrd|wprd|webst)0[1-4]\.is\.autonavi\.com$/],
    tencent: [/^map\.qq\.com$/, /^mapapi\.qq\.com$/, /^apis\.map\.qq\.com$/, /^pr\.map\.qq\.com$/, /^apikey\.map\.qq\.com$/, /^overseactrl\.map\.qq\.com$/, /^confinfo\.map\.qq\.com$/, /^vectorsdk\.map\.qq\.com$/, /^mapstyle\.qpic\.cn$/, /^(?:rt|p)[0-3]\.map\.gtimg\.com$/],
    baidu: [/^api\.map\.baidu\.com$/, /^(?:api|online|shangetu)[0-3]\.map\.bdimg\.com$/, /^apimaponline[0-3]\.bdimg\.com$/, /^maponline[0-3]\.bdimg\.com$/, /^d[0-3]\.map\.baidu\.com$/, /^(?:dlswbr|miao)\.baidu\.com$/, /^webmap0\.bdimg\.com$/],
    tianditu: [/^api\.tianditu\.gov\.cn$/, /^api\.tianditu\.com$/, /^t[0-7]\.tianditu\.gov\.cn$/, /^t[0-7]\.tianditu\.com$/],
  });
  const state = { config: { enabled: false, provider: "amap", basePath: DEFAULT_BASE_PATH }, installed: false, restorers: [], contextGeneration: 0, refreshTimer: null, contextRequest: null, initializedMode: null, reloadRequired: false, reloadMessage: null, contextIdentity: null };
  const baiduFrames = new Set();

  function createBaiduMapFrame({ host, key }) {
    if (!host || !key) throw new Error("百度地图容器或 AK 未配置");
    let frame = globalScope.document.createElement("iframe");
    frame.title = "百度地图";
    frame.referrerPolicy = "origin";
    frame.dataset.baiduMapRealm = "true";
    frame.style.cssText = "display:block;width:100%;height:100%;border:0";
    const realm = { frame, window: null, container: null, sdk: null, ready: null, dispose: null };
    const config = { ...state.config };
    let stopped = false, settled = false, timer, rejectReady;
    const clear = () => {
      globalScope.clearTimeout(timer);
      frame.onload = null;
      if (realm.window) delete realm.window.__zxBaiduReady;
    };
    const fail = error => {
      if (settled) return;
      settled = true;
      clear();
      rejectReady(error);
      realm.dispose();
    };
    realm.dispose = () => {
      if (stopped) return;
      stopped = true;
      if (!settled) fail(new Error("百度地图初始化已取消"));
      clear();
      frame.remove();
      frame = null;
      realm.frame = null;
      baiduFrames.delete(realm);
      realm.sdk = null;
      realm.container = null;
      realm.window = null;
    };
    realm.ready = new Promise((resolve, reject) => {
      rejectReady = reject;
      timer = globalScope.setTimeout(() => fail(new Error("百度地图 SDK 加载超时，请重试")), 20000);
      frame.onload = () => {
        if (stopped || settled) return;
        frame.onload = null;
        try {
          const win = realm.window = frame.contentWindow;
          realm.container = win.document.getElementById("baidu-map");
          const proxy = win.document.createElement("script");
          proxy.src = new URL("/scripts/map-request-proxy.js", globalScope.location.href).href;
          proxy.onerror = () => fail(new Error("百度地图隔离运行时加载失败"));
          proxy.onload = () => {
            if (stopped || settled) return;
            try {
              win.ZXMapRequestProxy.install(config);
              win.__zxBaiduReady = () => {
                if (stopped || settled) return;
                if (typeof win.BMap?.Map !== "function") { fail(new Error("百度地图 SDK 不可用")); return; }
                realm.sdk = win.BMap;
                settled = true;
                clear();
                resolve(realm);
              };
              const sdk = win.document.createElement("script");
              sdk.onerror = () => fail(new Error("百度地图 SDK 脚本加载失败"));
              sdk.src = `https://api.map.baidu.com/api?v=4.0&ak=${encodeURIComponent(key)}&callback=__zxBaiduReady`;
              win.document.head.appendChild(sdk);
            } catch (error) { fail(error); }
          };
          win.document.head.appendChild(proxy);
        } catch (error) { fail(error); }
      };
    });
    // Removing the browsing context cancels SDK-owned callbacks and network work.
    frame.srcdoc = '<!doctype html><meta name="referrer" content="origin"><meta charset="utf-8"><style>html,body,#baidu-map{width:100%;height:100%;margin:0;overflow:hidden}</style><div id="baidu-map"></div>';
    baiduFrames.add(realm);
    host.appendChild(frame);
    return realm;
  }

  function normalizeConfig(input) {
    const config = input || {};
    const provider = String(config.provider || "amap").trim().toLowerCase();
    if (!HOST_RULES[provider]) throw new TypeError("unsupported map proxy provider");
    let basePath = String(config.basePath || DEFAULT_BASE_PATH).trim();
    if (!basePath.startsWith("/")) basePath = `/${basePath}`;
    basePath = basePath.replace(/\/+$/, "") || DEFAULT_BASE_PATH;
    if (!/^\/[A-Za-z0-9._~-]+(?:\/[A-Za-z0-9._~-]+)*$/.test(basePath)) throw new TypeError("invalid map proxy basePath");
    if (basePath.split("/").some((part) => part === "." || part === "..")) throw new TypeError("invalid map proxy basePath");
    const contextToken = config.contextToken;
    if (contextToken !== undefined && (typeof contextToken !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(contextToken))) throw new TypeError("invalid map proxy context token");
    const mapConfigId = config.map_config_id ?? config.mapConfigId;
    return { enabled: config.enabled === true, provider, basePath,
      ...(contextToken ? { contextToken } : {}), ...(mapConfigId ? { map_config_id: String(mapConfigId) } : {}) };
  }

  function providerForHost(host) {
    const normalized = String(host || "").toLowerCase().replace(/\.$/, "");
    if (!normalized || normalized.includes(":") || /^[\d.]+$/.test(normalized)) return null;
    for (const [provider, rules] of Object.entries(HOST_RULES)) if (rules.some((rule) => rule.test(normalized))) return provider;
    return null;
  }

  function sameOriginProxyPath(pathname, basePath) {
    const normalized = String(pathname || "");
    return normalized === basePath || normalized.startsWith(`${basePath}/`);
  }

  function resourceBaseUrl() {
    const inheritedBase = globalScope?.document?.baseURI;
    if (/^https?:\/\//.test(inheritedBase || "")) return inheritedBase;
    return globalScope?.location?.href || `${globalScope?.location?.origin || "http://localhost"}/`;
  }

  function rewriteUrl(input, config = state.config) {
    const effective = normalizeConfig(config);
    if (!effective.enabled || typeof input !== "string") return input;
    const sourceUrl = resourceBaseUrl();
    const appOrigin = /^https?:\/\//.test(globalScope?.location?.origin || "")
      ? globalScope.location.origin : new URL(sourceUrl).origin;
    const workerContext = !globalScope?.document && /^https?:\/\//.test(appOrigin);
    const base = workerContext && sourceUrl.startsWith("blob:") ? `${appOrigin}/` : sourceUrl;
    let parsed;
    try { parsed = new URL(input, base); } catch (_) { return input; }
    if (sameOriginProxyPath(parsed.pathname, effective.basePath) && parsed.origin === appOrigin) {
      if (!effective.contextToken || parsed.searchParams.has("__map_context")) return workerContext ? parsed.href : input;
      return `${workerContext || /^https?:\/\//.test(input) ? appOrigin : ""}${parsed.pathname}${parsed.search}${parsed.search ? "&" : "?"}__map_context=${effective.contextToken}`;
    }
    if (!/^https?:$/.test(parsed.protocol) || parsed.username || parsed.password || parsed.port) return input;
    const provider = providerForHost(parsed.hostname);
    if (!provider) return input;
    if (parsed.hostname === "mapplugin.amap.com" && parsed.pathname !== "/maps/checkredirectcdn") return input;
    // 供应商资源统一通过后端 HTTPS 连接，避免代理因页面中的 http 绝对地址
    // 退回明文上游；浏览器侧仍保持同源请求。
    return `${workerContext ? appOrigin : ""}${effective.basePath}/${provider}/https/${parsed.hostname}${parsed.pathname || "/"}${parsed.search}${effective.contextToken ? `${parsed.search ? "&" : "?"}__map_context=${effective.contextToken}` : ""}`;
  }

  function rewriteModuleUrl(specifier, moduleUrl) {
    if (typeof specifier !== "string" || !/^(?:\.{1,2}\/|\/|https?:\/\/)/.test(specifier)) return specifier;
    const base = new URL(moduleUrl, resourceBaseUrl());
    const appOrigin = new URL(resourceBaseUrl()).origin;
    if (base.origin === appOrigin && sameOriginProxyPath(base.pathname, state.config.basePath)) {
      const parts = base.pathname.slice(state.config.basePath.length + 1).split("/");
      if (parts[1] === "https" && providerForHost(parts[2]) === parts[0]) {
        base.searchParams.delete("__map_context");
        base.searchParams.delete("__map_module");
        base.href = `https://${parts[2]}/${parts.slice(3).join("/")}${base.search}`;
      }
    }
    const absolute = new URL(specifier, base).href;
    const rewritten = rewriteUrl(absolute);
    const parsed = new URL(rewritten, resourceBaseUrl());
    if (parsed.origin !== appOrigin || !sameOriginProxyPath(parsed.pathname, state.config.basePath)) return specifier;
    if (!parsed.searchParams.has("__map_module")) parsed.searchParams.set("__map_module", "1");
    return parsed.href;
  }

  function rewriteCssUrls(value, config = state.config) {
    return String(value).replace(/\burl\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*?))\s*\)/gi, (all, doubleQuoted, singleQuoted, unquoted) => {
      const url = doubleQuoted ?? singleQuoted ?? unquoted ?? "";
      const rewritten = rewriteUrl(url, config);
      if (rewritten === url) return all;
      const quote = doubleQuoted !== undefined ? '"' : singleQuoted !== undefined ? "'" : "";
      return `url(${quote}${rewritten}${quote})`;
    });
  }

  function rewriteStringMarkup(value, config = state.config) {
    return rewriteCssUrls(String(value).replace(/(\b(?:src|href)\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/gi, (all, prefix, doubleQuoted, singleQuoted, unquoted) => {
      const url = doubleQuoted ?? singleQuoted ?? unquoted ?? "";
      const quote = doubleQuoted !== undefined ? '"' : singleQuoted !== undefined ? "'" : "";
      return `${prefix}${quote}${rewriteUrl(url, config)}${quote}`;
    }), config);
  }

  function replaceMethod(target, property, createWrapper) {
    if (!target || typeof target[property] !== "function") return;
    const descriptor = Object.getOwnPropertyDescriptor(target, property);
    const original = target[property];
    target[property] = createWrapper(original);
    state.restorers.push(() => {
      if (descriptor) Object.defineProperty(target, property, descriptor);
      else delete target[property];
    });
  }

  function replaceSetter(target, property, transform) {
    const descriptor = target && Object.getOwnPropertyDescriptor(target, property);
    if (!descriptor?.set || descriptor.configurable === false) return;
    Object.defineProperty(target, property, { ...descriptor, set(value) { return descriptor.set.call(this, transform(value, this)); } });
    state.restorers.push(() => Object.defineProperty(target, property, descriptor));
  }

  function installHooks() {
    if (state.installed) return;
    const win = globalScope;
    if (!win) return;
    if (typeof win.fetch === "function") {
      replaceMethod(win, "fetch", (original) => function proxiedFetch(input, init) {
        if (typeof input === "string" || input instanceof URL) return original.call(this, rewriteUrl(String(input), state.config), init);
        const RequestType = win.Request;
        if (input && RequestType && input instanceof RequestType) {
          const rewritten = rewriteUrl(input.url, state.config);
          const base = resourceBaseUrl();
          return original.call(this, rewritten === input.url ? input : new RequestType(new URL(rewritten, base).href, input), init);
        }
        return original.call(this, input, init);
      });
    }
    const xhr = win.XMLHttpRequest?.prototype;
    replaceMethod(xhr, "open", (original) => function proxiedOpen(method, url, ...rest) {
      return original.call(this, method, rewriteUrl(String(url), state.config), ...rest);
    });
    replaceMethod(win, "importScripts", (original) => function proxiedImports(...urls) {
      return original.apply(this, urls.map((url) => rewriteUrl(String(url), state.config)));
    });
    for (const [ctorName, attr] of [["HTMLScriptElement", "src"], ["HTMLImageElement", "src"], ["HTMLLinkElement", "href"]]) {
      const proto = win[ctorName]?.prototype;
      replaceSetter(proto, attr, (value) => rewriteUrl(String(value), state.config));
      if (!win.Element) replaceMethod(proto, "setAttribute", (original) => function proxiedSetAttribute(name, value) {
        return original.call(this, name, String(name).toLowerCase() === attr ? rewriteUrl(String(value), state.config) : value);
      });
    }
    // SDKs build controls with innerHTML and inline CSS, which bypass src setters.
    const element = win.Element?.prototype;
    replaceMethod(element, "setAttribute", (original) => function proxiedAttribute(name, value) {
      const attr = String(name).toLowerCase();
      const rewritten = attr === "src" || attr === "href" ? rewriteUrl(String(value), state.config)
        : attr === "style" ? rewriteCssUrls(value, state.config) : value;
      return original.call(this, name, rewritten);
    });
    for (const property of ["innerHTML", "outerHTML"]) replaceSetter(element, property, (value) => rewriteStringMarkup(value, state.config));
    replaceMethod(element, "insertAdjacentHTML", (original) => function proxiedAdjacentHtml(position, html) {
      return original.call(this, position, rewriteStringMarkup(html, state.config));
    });
    const style = win.CSSStyleDeclaration?.prototype;
    for (const property of ["cssText", "background", "backgroundImage", "borderImage", "listStyleImage", "cursor", "maskImage"]) {
      replaceSetter(style, property, (value) => rewriteCssUrls(value, state.config));
    }
    replaceMethod(style, "setProperty", (original) => function proxiedStyleProperty(name, value, priority) {
      return original.call(this, name, rewriteCssUrls(value, state.config), priority);
    });
    // Chromium exposes named CSS properties on each declaration object rather
    // than its prototype. Bind them as soon as a DOM style getter returns it.
    const hookedStyles = new WeakSet();
    function bindStyleDeclaration(declaration) {
      if (!declaration || hookedStyles.has(declaration) || typeof declaration.getPropertyValue !== "function") return declaration;
      hookedStyles.add(declaration);
      for (const [property, cssName] of [["background", "background"], ["backgroundImage", "background-image"],
        ["borderImage", "border-image"], ["listStyleImage", "list-style-image"], ["cursor", "cursor"], ["maskImage", "mask-image"]]) {
        for (const name of new Set([property, cssName])) {
          const descriptor = Object.getOwnPropertyDescriptor(declaration, name);
          if (!descriptor || descriptor.set || descriptor.configurable === false) continue;
          Object.defineProperty(declaration, name, { configurable: true, enumerable: descriptor.enumerable,
            get() { return this.getPropertyValue(cssName); },
            set(value) { this.setProperty(cssName, rewriteCssUrls(value, state.config)); },
          });
          const reference = typeof WeakRef === "function" ? new WeakRef(declaration) : { deref: () => declaration };
          state.restorers.push(() => { const current = reference.deref(); if (current) delete current[name]; });
        }
      }
      return declaration;
    }
    for (const constructor of ["HTMLElement", "SVGElement", "CSSStyleRule"]) {
      const target = win[constructor]?.prototype;
      const descriptor = target && Object.getOwnPropertyDescriptor(target, "style");
      if (!descriptor?.get || descriptor.configurable === false) continue;
      Object.defineProperty(target, "style", { ...descriptor, get() { return bindStyleDeclaration(descriptor.get.call(this)); } });
      state.restorers.push(() => Object.defineProperty(target, "style", descriptor));
    }
    const styleSheet = win.CSSStyleSheet?.prototype;
    for (const method of ["insertRule", "replace", "replaceSync"]) replaceMethod(styleSheet, method, (original) => function proxiedCss(rule, ...args) {
      return original.call(this, rewriteCssUrls(rule, state.config), ...args);
    });
    const objectUrlBlobs = new Map();
    const nativeCreateObjectUrl = win.URL?.createObjectURL;
    const nativeRevokeObjectUrl = win.URL?.revokeObjectURL;
    if (win.Blob && nativeCreateObjectUrl && nativeRevokeObjectUrl) {
      replaceMethod(win.URL, "createObjectURL", (original) => function trackedObjectUrl(object) {
        const url = original.call(this, object);
        if (object instanceof win.Blob) objectUrlBlobs.set(url, object);
        return url;
      });
      replaceMethod(win.URL, "revokeObjectURL", (original) => function releasedObjectUrl(url) {
        objectUrlBlobs.delete(String(url));
        return original.call(this, url);
      });
      state.restorers.push(() => objectUrlBlobs.clear());
    }
    replaceMethod(win, "Worker", (Original) => {
      function ProxiedWorker(url, options) {
        if (!new.target) throw new TypeError("Worker constructor requires new");
        const originalBlob = objectUrlBlobs.get(String(url));
        if (!originalBlob) return Reflect.construct(Original, [options?.type === "module" && state.config.contextToken
          ? rewriteModuleUrl(String(url), resourceBaseUrl()) : rewriteUrl(String(url), state.config), options], new.target);
        if (options?.type === "module") throw new Error("地图代理暂不支持 Blob 模块 Worker，请关闭前端地图代理并刷新页面后重试。");
        const bootstrap = `;(${createMapRequestProxy.toString()})(self).install(${JSON.stringify(state.config)});\n`;
        const wrappedBlob = new win.Blob([bootstrap, originalBlob], { type: "application/javascript" });
        const wrappedUrl = nativeCreateObjectUrl.call(win.URL, wrappedBlob);
        try { return Reflect.construct(Original, [wrappedUrl, options], new.target); }
        finally { nativeRevokeObjectUrl.call(win.URL, wrappedUrl); }
      }
      ProxiedWorker.prototype = Original.prototype;
      Object.setPrototypeOf(ProxiedWorker, Original);
      return ProxiedWorker;
    });
    if (win.document) {
      for (const method of ["write", "writeln"]) replaceMethod(win.document, method, (original) => function proxiedMarkup(...args) {
        return original.call(this, rewriteStringMarkup(args.map(String).join(""), state.config));
      });
    }
    state.installed = true;
  }

  function restoreHooks() {
    state.restorers.reverse().forEach((restore) => restore());
    state.restorers = [];
    state.installed = false;
  }

  function install(input) {
    state.contextGeneration += 1;
    if (state.refreshTimer !== null) globalScope.clearTimeout?.(state.refreshTimer);
    state.refreshTimer = null;
    cancelContextRequest();
    state.config = normalizeConfig(input);
    if (!state.config.enabled) restoreHooks(); else installHooks();
    return { ...state.config };
  }

  function cancelContextRequest() {
    const pending = state.contextRequest;
    state.contextRequest = null;
    pending?.cancel(new Error('地图代理上下文认证已取消，请重试'));
  }

  function scheduleContextRefresh(input, generation, delay) {
    if (state.reloadMessage || generation !== state.contextGeneration || !state.config.enabled || typeof globalScope.setTimeout !== 'function') return;
    if (state.refreshTimer !== null) globalScope.clearTimeout?.(state.refreshTimer);
    state.refreshTimer = globalScope.setTimeout(async () => {
      state.refreshTimer = null;
      if (generation !== state.contextGeneration || !state.config.enabled) return;
      try { await requestContext(input, generation); }
      catch (_) {
        // Keep existing SDK traffic behind the proxy while authentication recovers.
        scheduleContextRefresh(input, generation, 30000);
      }
    }, delay);
  }

  async function requestContext(input, generation) {
    const headers = { 'Content-Type': 'application/json' };
    if (input.sessionId) headers['X-Session-ID'] = String(input.sessionId);
    if (input.originSessionId) headers['X-Admin-Origin-Session-ID'] = String(input.originSessionId);
    const controller = typeof globalScope.AbortController === 'function' ? new globalScope.AbortController() : null;
    cancelContextRequest();
    let rejectInterrupted;
    const interrupted = new Promise((_, reject) => { rejectInterrupted = reject; });
    const pending = {
      deadline: null, failure: null,
      cancel(error) {
        if (pending.failure) return;
        pending.failure = error;
        if (pending.deadline !== null) globalScope.clearTimeout?.(pending.deadline);
        rejectInterrupted(error);
        controller?.abort();
      },
    };
    state.contextRequest = pending;
    const isCurrent = () => generation === state.contextGeneration && state.contextRequest === pending;
    try {
      pending.deadline = globalScope.setTimeout(() => {
        pending.cancel(new Error('地图代理上下文认证超时，请重试'));
      }, CONTEXT_TIMEOUT_MS);
      const payload = await Promise.race([
        (async () => {
          const response = await globalScope.fetch(input.contextUrl || '/api/map-proxy/context', {
            method: 'POST', credentials: 'include', cache: 'no-store', headers,
            body: JSON.stringify({ pin_context: true, ...(input.mapConfigId ? { map_config_id: input.mapConfigId } : {}),
              ...(input.contextToken ? { context_token: input.contextToken } : {}) }), ...(controller ? { signal: controller.signal } : {}),
          });
          if (!isCurrent()) return { stale: true };
          if (!response || !response.ok) {
            let detail = "";
            try { const failure = await response?.json?.(); if (typeof failure?.message === "string") detail = failure.message.slice(0, 200); } catch (_) {}
            if (response?.status === 409 && isCurrent()) {
              state.reloadMessage = "地图代理上下文已失效，需要刷新页面以重新应用地图配置；如未自动刷新，请手动刷新后重试。";
              if (!state.reloadRequired) {
                state.reloadRequired = true;
                if (state.refreshTimer !== null) globalScope.clearTimeout?.(state.refreshTimer);
                state.refreshTimer = null;
                try { globalScope.location?.reload?.(); } catch (_) {}
              }
              throw new Error(state.reloadMessage);
            }
            throw new Error(`地图代理上下文认证失败（HTTP ${response?.status || 0}）${detail ? `：${detail}` : ""}`);
          }
          try { return await response.json(); } catch (_) { return {}; }
        })(),
        interrupted,
      ]);
      if (!isCurrent()) return { stale: true };
      if (payload?.success !== true) throw new Error('地图代理上下文认证失败');
      if (payload.context_token !== undefined) {
        if (typeof payload.context_token !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(payload.context_token)) throw new Error('地图代理上下文格式无效');
        input.contextToken = payload.context_token;
        state.config = { ...state.config, contextToken: payload.context_token };
      }
      if (typeof payload.map_config_id === "string") {
        input.mapConfigId = payload.map_config_id;
        state.config = { ...state.config, map_config_id: payload.map_config_id };
      }
      const expiresIn = Math.max(1, Number(payload.expires_in) || 1800);
      scheduleContextRefresh(input, generation, Math.max(500, Math.min(expiresIn * 800, 1440000)));
      return payload;
    } catch (error) {
      if (!isCurrent()) return { stale: true };
      throw pending.failure || error;
    } finally {
      if (pending.deadline !== null) globalScope.clearTimeout?.(pending.deadline);
      if (state.contextRequest === pending) state.contextRequest = null;
    }
  }

  async function initialize(input = {}) {
    const config = normalizeConfig(input);
    const identity = String(input.originSessionId || input.sessionId || "");
    if (state.reloadRequired && state.reloadMessage) throw new Error(state.reloadMessage);
    if (!config.map_config_id && state.contextIdentity === identity && state.config.contextToken) {
      config.map_config_id = state.config.map_config_id;
    }
    // Reauthentication of the same page renews its original origin snapshot.
    if (!config.contextToken && state.contextIdentity === identity &&
        config.map_config_id === state.config.map_config_id && state.config.contextToken) {
      config.contextToken = state.config.contextToken;
    }
    const modeChanged = state.initializedMode !== null && state.initializedMode !== config.enabled;
    const sdkLoaded = baiduFrames.size > 0 || ["AMap", "TMap", "T", "BMap"].some((name) => typeof globalScope?.[name]?.Map === "function");
    // Executed SDKs and their workers retain rewritten URLs after hooks are removed.
    if (state.reloadRequired || (modeChanged && sdkLoaded)) {
      if (!state.reloadRequired) {
        state.reloadRequired = true;
        if (typeof globalScope?.location?.reload !== "function") {
          throw new Error("地图代理模式已更改，无法自动刷新页面，请手动刷新当前页面后重试。");
        }
        try { globalScope.location.reload(); }
        catch (error) {
          throw new Error("地图代理模式已更改，自动刷新失败，请手动刷新当前页面后重试。", { cause: error });
        }
      }
      throw new Error("地图代理模式已更改，需要刷新当前页面后生效；如未自动刷新，请手动刷新后重试。");
    }
    // Install first so failed reauthentication cannot restore direct vendor requests.
    install(config);
    state.contextIdentity = identity;
    state.initializedMode = config.enabled;
    if (!config.enabled) return { ...config };
    const generation = state.contextGeneration;
    const contextInput = { sessionId: input.sessionId, originSessionId: input.originSessionId, contextUrl: input.contextUrl,
      mapConfigId: config.map_config_id, contextToken: config.contextToken };
    try {
      const payload = await requestContext(contextInput, generation);
      return { ...config, expires_in: payload.expires_in, ...(payload.stale ? { stale: true } : {}) };
    } catch (error) {
      if (generation !== state.contextGeneration) return { ...config, stale: true };
      scheduleContextRefresh(contextInput, generation, 30000);
      throw error;
    }
  }
  return { initialize, install, rewriteUrl, rewriteModuleUrl, createBaiduMapFrame, getConfig: () => ({ ...state.config }) };
});
