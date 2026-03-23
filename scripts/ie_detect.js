// ============================================================
// 浏览器兼容性检测与拦截脚本
//
// 此脚本在页面 <head> 最顶部同步执行（无 async/defer），
// 确保在任何页面内容渲染之前完成检测，将不兼容的浏览器
// 重定向到专用的浏览器升级提示页面。
//
// ── 拦截目标（按检测顺序）────────────────────────────────
//  1. IE 6 / 7 / 8 / 9      HTML 条件注释（已在 index.html 处理）
//  2. IE 10 / IE 11          document.documentMode
//  3. 旧版 Edge              EdgeHTML 引擎，UA 含 "Edge/版本"
//  4. 国产双核浏览器         Trident 兼容模式（UA 含 Trident/ + 品牌）
//  5. Opera（Presto 引擎）   2013 年前旧版，UA 含 "Opera/" 不含 "OPR/"
//  6. Opera Mini             服务端渲染，JS 支持极为有限
//  7. UC 浏览器              私有内核，现代 Web API 支持不完整
//  8. 百度浏览器             兼容性差，频繁出现页面异常
//  9. Samsung Internet < 10  2019 年以前的旧版
// 10. Firefox < 68           2019 年以前的旧版
// 11. Chrome / Chromium < 70 2018 年以前的旧版
// 12. Safari < 12            2018 年以前的旧版（缺少 Service Worker 等）
// 13. Android 内置浏览器     Android ≤ 4.x 的默认 WebKit 浏览器
// 14. 功能特性兜底检测       Promise / fetch / Symbol / Map 缺失则拦截
//
// ── 允许通过的浏览器（示例）───────────────────────────────
//  - Chrome / Chromium ≥ 70（含 Chromium Edge、现代 Opera OPR/）
//  - Firefox ≥ 68
//  - Safari ≥ 12（macOS / iOS）
//  - Samsung Internet ≥ 10
//  - 360 / 搜狗 / QQ 等国产浏览器的极速模式（Blink 内核）
//
// ── 注意事项──────────────────────────────────────────────
//  - 本脚本全部使用 ES5 语法（var / function），确保自身可在
//    需要检测的老旧浏览器中正常解析并执行。
//  - 使用 indexOf / 正则，不使用 ES6 的 includes() / startsWith()。
// ============================================================

(function () {
  // 使用立即执行函数表达式（IIFE），避免污染全局命名空间

  // 获取 User-Agent 字符串，供后续各项检测使用
  var ua = navigator.userAgent;

  /**
   * 跳转到浏览器不兼容提示页面
   * 在执行 window.location.href 赋值后，JS 引擎仍会继续执行后续
   * 代码，因此每次调用本函数时都要配合 return 语句提前退出 IIFE。
   */
  function block() {
    window.location.href = '/ie.html';
  }

  // ----------------------------------------------------------------
  // 检测 1：IE 10 / IE 11
  //
  // Trident 引擎在 document 对象上暴露 documentMode 属性，
  // 值为当前文档的 IE 兼容模式版本号（10 或 11）。
  // IE 6–9 已由 index.html 中的 HTML 条件注释拦截，无需在此重复。
  //
  // 示例值：IE10 → 10，IE11 → 11
  // ----------------------------------------------------------------
  if (document.documentMode) {
    return block(); // IE 10 或 IE 11，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 2：旧版 Edge（EdgeHTML 引擎）
  //
  // 旧版 Edge（Windows 10 自带，2015–2018）使用 EdgeHTML 排版引擎，
  // UA 中含 "Edge/版本号"（有尾部字母 'e'）。
  // 2020 年后发布的 Chromium 版 Edge 在 UA 中使用 "Edg/"（无 'e'），
  // 兼容性良好，不在拦截范围内。
  //
  // EdgeHTML UA 示例：  "... Edge/18.17763"
  // Chromium Edge UA 示例："... Edg/114.0.1823.82"
  //
  // 使用 \b 单词边界防止误匹配 "Edged/" 等其他字符串。
  // ----------------------------------------------------------------
  if (/\bEdge\/\d+/.test(ua)) {
    return block(); // 旧版 EdgeHTML，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 3：国产双核浏览器的 Trident/IE 兼容模式
  //
  // 360、搜狗、QQ、遨游等国产浏览器内置 Trident（IE内核）
  // 与 Blink（极速内核）两套引擎。
  // 切换到"兼容模式"时，UA 同时含有 "Trident/" 和品牌标识。
  // 切换到"极速模式"时，UA 不含 "Trident/"，可正常使用应用。
  //
  // 品牌标识列表：
  //   360EE / 360SE  ── 360极速/安全浏览器
  //   QIHU           ── 奇虎（360 Trident 模式的另一标识）
  //   Sogou / MetaSr ── 搜狗浏览器
  //   QQBrowser      ── QQ浏览器
  //   TheWorld       ── 世界之窗浏览器
  //   Maxthon        ── 遨游浏览器
  //   2345Explorer   ── 2345加速浏览器
  // ----------------------------------------------------------------
  if (
    /Trident\//.test(ua) &&
    /360EE|360SE|QIHU|Sogou|MetaSr|QQBrowser|TheWorld|Maxthon|2345Explorer/i.test(ua)
  ) {
    return block(); // 国产双核浏览器处于兼容模式，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 4：旧版 Opera（Presto 引擎，2013 年及以前）
  //
  // 2013 年之前，Opera 使用自研的 Presto 排版引擎（Opera ≤ 12.x）。
  // UA 以 "Opera/" 开头，且不含 "OPR/"（现代 Chromium 版 Opera 的标识）。
  // Presto 引擎对现代 Web 标准的支持非常有限，无法运行本应用。
  //
  // Presto Opera UA 示例：  "Opera/9.80 (Windows NT 6.1) Presto/2.12.388 Version/12.18"
  // Chromium Opera UA 示例："... Chrome/114.0.0.0 Safari/537.36 OPR/100.0.0.0"
  // ----------------------------------------------------------------
  if (/Opera\//.test(ua) && !/OPR\//.test(ua)) {
    return block(); // Presto 引擎旧版 Opera，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 5：Opera Mini
  //
  // Opera Mini 通过服务端代理进行页面渲染后再下发到客户端，
  // JavaScript 执行环境极为有限，无法运行本应用的 Socket.IO
  // 及现代 Web API。
  //
  // UA 示例："Opera/9.80 (J2ME/MIDP; Opera Mini/9.80 (S60; ...))"
  // ----------------------------------------------------------------
  if (/Opera Mini/i.test(ua)) {
    return block(); // Opera Mini，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 6：UC 浏览器（UCBrowser）
  //
  // UC Browser 使用私有内核，对现代 Web API（Promise、fetch、
  // Service Worker 等）的支持存在缺陷，在本应用中频繁出现异常。
  //
  // UA 示例："... UCBrowser/13.3.0.1303 Mobile Safari/537.36"
  // ----------------------------------------------------------------
  if (/UCBrowser\//i.test(ua)) {
    return block(); // UC 浏览器，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 7：百度浏览器（Baidu Browser）
  //
  // 百度浏览器（手机百度/百度浏览器）的内核对现代 Web 标准支持
  // 不够完整，且版本更新较慢，常导致页面渲染或功能异常。
  //
  // UA 示例："... BIDUBrowser/8.9.12.10 Mobile Safari/537.36"
  //          "... baidubrowser/..."
  // ----------------------------------------------------------------
  if (/BIDUBrowser|baidubrowser/i.test(ua)) {
    return block(); // 百度浏览器，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 8：Samsung Internet 版本过低（< 10）
  //
  // Samsung Internet 10（2019 年发布，基于 Chrome 71）是支持
  // 本应用所需 Web API 的最低版本。10 以下版本缺少 Service Worker、
  // CSS 自定义属性等特性。
  //
  // UA 示例："SamsungBrowser/10.2 Chrome/71.0.3578.99 Mobile Safari/537.36"
  //          "SamsungBrowser/7.4 Chrome/59.0.3071.128 Mobile Safari/537.36"
  // ----------------------------------------------------------------
  var samsungMatch = ua.match(/SamsungBrowser\/(\d+)/i);;
  if (samsungMatch && parseInt(samsungMatch[1], 10) < 10) {
    return block(); // Samsung Internet < 10，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 9：Firefox 版本过低（< 68）
  //
  // Firefox 68（2019 年 7 月发布，同时也是 ESR 长期支持版本）
  // 是支持本应用所需全部 Web API 的最低版本。
  // 更早版本缺少完整的 CSS 自定义属性、Service Worker 等支持。
  //
  // UA 示例："Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0)
  //           Gecko/20100101 Firefox/89.0"
  // ----------------------------------------------------------------
  var firefoxMatch = ua.match(/Firefox\/(\d+)/);
  if (firefoxMatch && parseInt(firefoxMatch[1], 10) < 68) {
    return block(); // Firefox < 68，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 10：Chrome / Chromium 版本过低（< 70）
  //
  // Chrome 70（2018 年 10 月发布）是支持本应用的最低版本。
  // 70 以下版本缺少部分 CSS Grid、Web Components 等特性。
  //
  // 排除项（各自有独立的版本检测或已允许通过）：
  //   - Chromium Edge（"Edg/"）：最低版本为 79，始终 ≥ 70
  //   - Samsung Internet（"SamsungBrowser/"）：已在检测 8 中单独处理
  //
  // 说明：现代 Opera（OPR/）、Brave、Vivaldi 等 Chromium 系浏览器
  //       均会在 UA 中携带 Chrome/版本，若其内核版本 < 70 同样拦截。
  //
  // UA 示例（Chrome）：
  //   "Mozilla/5.0 ... Chrome/91.0.4472.124 Safari/537.36"
  // UA 示例（Chromium Edge，排除）：
  //   "Mozilla/5.0 ... Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59"
  // ----------------------------------------------------------------
  var chromeMatch = ua.match(/\bChrome\/(\d+)/);
  if (
    chromeMatch &&
    !/\bEdg\//.test(ua) &&           // 排除 Chromium Edge
    !/SamsungBrowser\//.test(ua) &&  // 排除 Samsung Internet（已单独检测）
    parseInt(chromeMatch[1], 10) < 70
  ) {
    return block(); // Chrome/Chromium < 70，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 11：Safari 版本过低（< 12）
  //
  // Safari 12（2018 年 9 月发布，macOS Mojave / iOS 12 预装）是
  // 支持本应用的最低版本。Safari 12 起正式支持 Service Worker，
  // 并补全了多项 ES2017 特性。
  //
  // 检测逻辑：
  //   - UA 需同时含 "Version/版本" 和 "Safari"（纯 Safari 的特征）
  //   - 排除含 "Chrome/" 的浏览器（Chrome UA 中也含 "Safari" 字样）
  //   - 排除 Android WebView（格式不同，由检测 12 负责）
  //
  // Safari UA 示例：
  //   "Mozilla/5.0 (Mac; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15
  //    (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
  // ----------------------------------------------------------------
  var safariMatch = ua.match(/Version\/(\d+).*Safari/);
  if (
    safariMatch &&
    !/Chrome\//.test(ua) &&  // 排除 Chrome（UA 中也含 "Safari"）
    !/Android/.test(ua) &&   // 排除 Android 平台（由检测 12 处理）
    parseInt(safariMatch[1], 10) < 12
  ) {
    return block(); // Safari < 12，跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 12：Android 内置浏览器（Android ≤ 4.x）
  //
  // Android 4.x 及更早版本预装了基于 WebKit 的内置浏览器（非 Chrome）。
  // 该浏览器不支持 Promise、fetch 等现代 API，无法运行本应用。
  //
  // 特征组合（三者同时满足）：
  //   1. UA 含 "Android 1.x/2.x/3.x/4.x"（Android ≤ 4.x 系统）
  //   2. UA 含 "Version/"（WebKit 内置浏览器的标识）
  //   3. UA 不含 "Chrome/"（排除 Android 上的 Chrome 浏览器）
  //
  // Android WebView UA 示例：
  //   "Mozilla/5.0 (Linux; U; Android 4.0.3; ...) AppleWebKit/534.30
  //    (KHTML, like Gecko) Version/4.0 Mobile Safari/534.30"
  //
  // 注意：UC Browser、百度浏览器运行在 Android 4.x 上时，其 UA 含
  //       自有品牌标识，已被检测 6、7 提前拦截，不会到达此处。
  // ----------------------------------------------------------------
  if (
    /Android [1-4]\.\d/.test(ua) &&
    /Version\//.test(ua) &&
    !/Chrome\//.test(ua)
  ) {
    return block(); // Android 内置浏览器（Android ≤ 4.x），跳转到升级提示页
  }

  // ----------------------------------------------------------------
  // 检测 13：功能特性兜底检测（Feature Detection）
  //
  // 通过检测关键 Web API 是否存在，捕获所有未被前述 UA 检测覆盖的
  // 不兼容浏览器。这是最后一道防线，能处理以下情况：
  //   - 篡改 UA 字符串的浏览器或爬虫
  //   - 未在上方列出的小众不兼容浏览器
  //   - 未来新出现的不兼容浏览器
  //
  // 检测项目：
  //   Promise   ── ES2015 异步编程基础，Socket.IO 等核心库的依赖
  //   fetch     ── 现代网络请求 API（Chrome 42+，Firefox 39+，Safari 10.1+）
  //   Symbol    ── ES2015 基础特性，许多现代框架的依赖
  //   Map       ── ES2015 集合类型
  //   Set       ── ES2015 集合类型
  // ----------------------------------------------------------------
  var requiredAPIs = ['Promise', 'fetch', 'Symbol', 'Map', 'Set'];
  for (var i = 0; i < requiredAPIs.length; i++) {
    if (typeof window[requiredAPIs[i]] === 'undefined') {
      return block(); // 缺少必需的现代 Web API，跳转到升级提示页
    }
  }

  // ----------------------------------------------------------------
  // 通过全部检测：浏览器为受支持的现代浏览器，继续正常加载页面
  // ----------------------------------------------------------------
}());
