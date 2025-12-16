// ============================================================
// 高德地图去水印脚本加载器（带权限控制）
// 在加载去水印脚本前，先调用API检查用户是否有权限使用该功能
// ============================================================

(function () {
  // 使用立即执行函数表达式（IIFE）避免污染全局命名空间
  // 这样可以防止变量冲突，保持代码的封装性

  /**
   * 从当前页面获取 session UUID
   *
   * 此函数尝试从多个可能的位置获取 session ID：
   * 1. 全局变量 window.sessionUUID（如果页面设置了该变量）
   * 2. localStorage 中存储的 sessionUUID（持久化存储）
   * 3. sessionStorage 中存储的 sessionUUID（会话级存储）
   *
   * @returns {string|null} Session UUID，如果未找到则返回 null
   */
  function getUUIDFromURL() {
    const urlPath = window.location.pathname;

    const match = urlPath.match(
      /\/uuid=([a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})/i
    );

    if (match && match[1]) {
      return match[1];
    } else {
      return null;
    }
  }

  /**
   * 加载高德地图去水印脚本
   *
   * 此函数动态创建一个 <script> 标签，并将其添加到页面的 <head> 中。
   * 这样可以在运行时按需加载去水印脚本，而不是在页面加载时就加载。
   */
  function loadWatermarkRemovalScript() {
    // 创建一个新的 <script> 元素
    const script = document.createElement("script");

    // 设置脚本的源路径，指向去水印脚本文件
    script.src = "/scripts/Remove_watermark_from_Amap_Map.js";

    // 设置 async 为 false，确保脚本按顺序执行
    // 如果为 true，脚本会异步加载，可能导致执行顺序不确定
    script.async = false;

    // 将脚本元素添加到页面的 <head> 中，浏览器会自动开始下载并执行
    document.head.appendChild(script);

    // 记录日志，便于调试和跟踪
    console.log("[水印控制] 去水印脚本已加载");
  }

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

  /**
   * 检查用户是否有权限使用去水印功能
   *
   * 此函数向后端API发送请求，检查当前用户是否被允许使用去水印功能。
   * 如果允许，则加载去水印脚本；如果不允许，则不加载。
   */
  function checkWatermarkPermission() {
    // 步骤1: 获取当前用户的 session UUID
    const sessionUUID = getUUIDFromURL();

    console.log("[水印控制] 检查权限，Session UUID:", sessionUUID);

    // 步骤2: 构建请求头
    // 创建一个 Headers 对象，用于存储HTTP请求头
    const headers = new Headers();

    // 添加 Content-Type 头，告诉服务器我们期望接收JSON格式的响应
    headers.append("Content-Type", "application/json");

    // 如果成功获取到 session UUID，将其添加到请求头中
    // 服务器会根据这个 session ID 来识别用户身份
    if (sessionUUID) {
      headers.append("X-Session-ID", sessionUUID);
    }
    // 如果没有 session UUID，请求头中不包含 X-Session-ID
    // 服务器会认为这是一个未登录的请求，返回 {"allowed": false}

    // 步骤3: 发送HTTP GET请求到权限检查API
    fetch("/api/amap/watermark_control", {
      method: "GET", // 使用 GET 方法
      headers: headers, // 传递请求头
      // 添加错误处理的超时设置（可选）
      // timeout: 5000  // 5秒超时（需要使用 AbortController 实现）
    })
      .then((response) => {
        // 步骤4: 处理HTTP响应

        // 检查HTTP状态码是否为成功（200-299范围）
        if (!response.ok) {
          // HTTP状态码不是成功状态（例如 404、500 等）
          // 记录错误日志
          console.error("[水印控制] API请求失败，HTTP状态码:", response.status);

          // 抛出错误，让 catch 块处理
          throw new Error(`HTTP错误: ${response.status}`);
        }

        // 解析响应体为JSON格式
        // response.json() 返回一个 Promise
        return response.json();
      })
      .then((data) => {
        // 步骤5: 处理API返回的数据

        // 检查返回的数据中是否包含 "allowed" 字段
        if (data && typeof data.allowed === "boolean") {
          // 数据格式正确，检查是否允许去水印
          if (data.allowed === true) {
            // 用户有权限，加载去水印脚本
            console.log("[水印控制] 用户有权限，正在加载去水印脚本...");
            loadWatermarkRemovalScript();
            loadAmapScript();
          } else {
            // 用户没有权限，不加载去水印脚本
            console.log("[水印控制] 用户无权限，不加载去水印脚本");
            loadAmapScript();
          }
        } else {
          // 数据格式不正确，记录错误
          console.error("[水印控制] API返回数据格式错误:", data);
          console.log("[水印控制] 出于安全考虑，不加载去水印脚本");

          loadAmapScript();
        }
      })
      .catch((error) => {
        // 步骤6: 处理所有错误情况

        // 捕获网络错误、超时、解析错误等所有异常
        console.error("[水印控制] 检查权限时发生错误:", error);

        // 出错时采用保守策略：不加载去水印脚本
        // 这样可以避免因网络问题或其他错误导致的安全隐患
        console.log("[水印控制] 由于错误，不加载去水印脚本");

        loadAmapScript();
      });
    // .finally(() => {
    //     // 无论 Promise 是 fulfilled (成功) 还是 rejected (失败)
    //     // 都会执行 finally 中的代码，确保 loadAmapScript 是流程的最后一步
    //     try {
    //         console.log('[水印控制] 权限检查流程结束，准备加载高德地图脚本...');
    //         loadAmapScript();
    //     } catch (error) {
    //         console.error('[水印控制] 加载高德地图脚本时发生错误:', error);
    //     }

    // })
  }

  // ============================================================
  // 脚本入口点
  // 当此脚本被加载时，立即执行权限检查
  // ============================================================

  // // 确保DOM已经加载完成再执行
  // // 如果DOM未加载完成，某些操作可能会失败
  // if (document.readyState === 'loading') {
  //     // DOM 还在加载中，等待 DOMContentLoaded 事件
  //     document.addEventListener('DOMContentLoaded', function() {
  //         // DOM 加载完成后，执行权限检查
  //         checkWatermarkPermission();
  //     });
  // } else {
  //     // DOM 已经加载完成，直接执行权限检查
  //     checkWatermarkPermission();
  // }
  checkWatermarkPermission();
})();
// 立即执行函数表达式结束
