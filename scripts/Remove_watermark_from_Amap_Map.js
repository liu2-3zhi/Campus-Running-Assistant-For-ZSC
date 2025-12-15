function loadAmapScript() {
  // 1. 创建 script 元素
  var script = document.createElement("script");

  // 2. 设置主要源地址
  script.src = "/api/cdn/amap-loader";

  // 3. 设置加载失败时的处理逻辑 (对应 onerror)
  script.onerror = function () {
    console.warn("CDN加载失败，切换至官方源...");
    this.src = "https://webapi.amap.com/loader.js";
    // 防止死循环，移除 onerror 事件
    this.onerror = null;
  };

  // 4. 将 script 插入到 head (你提到的 "Heard")
  document.head.appendChild(script);

  // 记录日志，便于调试和跟踪
  console.log("[水印控制] 高德地图脚本已加载");
}

document.addEventListener("DOMContentLoaded", function loadBeianInfo() {
  console.log("[Interceptor] 高德地图去水印脚本启动 ");
  // ================= 配置区域 =================
  const CONFIG = {
    // 需要拦截的 URL 特征 (高德主库及相关插件)
    targetMatch: ["webapi.amap.com/maps", "webapi.amap.com/count"],
    // 替换规则 (支持正则)
    replaceRules: [
      { pattern: /未获得高德地图商用授权/g, replacement: "" },
      {
        pattern:
          /\\u672a\\u83b7\\u5f97\\u9ad8\\u5fb7\\u5730\\u56fe\\u5546\\u7528\\u6388\\u6743/g,
        replacement: "",
      },
    ],
    // 请求超时时间 (毫秒)，超时则直接放行原链接
    timeout: 5000,
  };

  // ================= 工具函数 =================
  const requestCache = new Map();
  const originalCreateElement = document.createElement;
  const originalSrcDescriptor = Object.getOwnPropertyDescriptor(
    HTMLScriptElement.prototype,
    "src"
  );

  // 带超时的 fetch
  function fetchWithTimeout(url, timeout) {
    return Promise.race([
      fetch(url),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Request timeout")), timeout)
      ),
    ]);
  }

  // 核心净化逻辑
  async function interceptAndModify(src) {
    // 1. 缓存检查
    if (requestCache.has(src)) return requestCache.get(src);

    const task = (async () => {
      try {
        console.log(`[Interceptor] ⚡ 捕获高德脚本: ${src}`);

        const response = await fetchWithTimeout(src, CONFIG.timeout);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        let content = await response.text();

        // 2. 执行替换规则
        let modified = false;
        CONFIG.replaceRules.forEach((rule) => {
          if (rule.pattern.test(content)) {
            content = content.replace(rule.pattern, rule.replacement);
            modified = true;
          }
        });

        if (modified) {
          console.log("[Interceptor] ✂️ 水印关键词已剔除");
        }

        // 3. 生成 Blob URL
        const blob = new Blob([content], { type: "text/javascript" });
        return URL.createObjectURL(blob);
      } catch (error) {
        console.warn(
          `[Interceptor] ⚠️ 处理失败 (${error.message})，回退原始链接: ${src}`
        );
        return src; // 失败回退
      }
    })();

    requestCache.set(src, task);
    return task;
  }

  // ================= 注入逻辑 =================
  document.createElement = function (tagName) {
    const element = originalCreateElement.call(document, tagName);

    // 只处理 script 标签
    if (tagName.toLowerCase() === "script") {
      Object.defineProperty(element, "src", {
        set: function (newSrc) {
          // 检查是否命中拦截规则
          const shouldIntercept =
            newSrc &&
            CONFIG.targetMatch.some((match) => newSrc.indexOf(match) !== -1);

          if (shouldIntercept) {
            interceptAndModify(newSrc).then((blobUrl) => {
              // 使用原始 setter 设置处理后的 URL
              originalSrcDescriptor.set.call(this, blobUrl);
            });
            // 阻止当前的赋值，等待异步处理
            return;
          }

          // 未命中规则，正常放行
          originalSrcDescriptor.set.call(this, newSrc);
        },
        get: function () {
          return originalSrcDescriptor.get.call(this);
        },
      });
    }
    return element;
  };

  console.log("[Interceptor] 高德地图去水印已激活 ");

  loadAmapScript();
});
