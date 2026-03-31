// 检查更新
(function () {
  function getSessionId() {
    try {
      if (typeof sessionUUID !== "undefined" && sessionUUID)
        return String(sessionUUID);
    } catch (_) {}
    return "";
  }

  async function sendUpdateLog(level, message, extra) {
    const payload = {
      level: String(level || "INFO").toUpperCase(),
      message: `[检查更新] ${message}${extra ? ` | ${JSON.stringify(extra)}` : ""}`,
      source: "check_for_updates.js",
      timestamp: new Date().toISOString(),
    };
    const headers = { "Content-Type": "application/json" };
    const sid = getSessionId();
    if (sid) headers["X-Session-ID"] = sid;
    try {
      await fetch("/api/log_frontend", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        keepalive: true,
      });
    } catch (_) {}
    console.log(`[检查更新] ${message}`, extra || "");
  }

  async function forceReloadWithBustTag() {
    const url = new URL(window.location.href);
    url.searchParams.set("__cache_bust", Date.now().toString());
    await sendUpdateLog("INFO", "准备跳转到强制刷新URL", {
      url: url.toString(),
    });
    window.location.replace(url.toString());
  }

  async function checkVersion() {
    try {
      const res = await fetch("/api/version.json", { cache: "no-store" });
      if (!res.ok) {
        await sendUpdateLog("WARNING", "版本接口返回非200", {
          status: res.status,
        });
        return;
      }
      const data = await res.json();
      const latestVersion = String(data?.version || "").trim();
      const currentVersion = String(
        localStorage.getItem("siteVersion") || "",
      ).trim();

      await sendUpdateLog("INFO", "版本信息获取成功", {
        currentVersion,
        latestVersion,
      });
      if (!latestVersion) return;

      if (currentVersion && currentVersion !== latestVersion) {
        await sendUpdateLog("WARNING", "检测到版本变更，开始清理缓存并刷新", {
          from: currentVersion,
          to: latestVersion,
        });
        localStorage.setItem("siteVersion", latestVersion);

        // 1) 清除 Cache API 缓存
        if ("caches" in window) {
          const cacheNames = await caches.keys();
          await Promise.all(cacheNames.map((name) => caches.delete(name)));
          await sendUpdateLog("INFO", "Cache API 缓存清理完成", {
            count: cacheNames.length,
          });
        }

        // 2) 注销 Service Worker
        if ("serviceWorker" in navigator) {
          const registrations =
            await navigator.serviceWorker.getRegistrations();
          await Promise.all(registrations.map((reg) => reg.unregister()));
          await sendUpdateLog("INFO", "Service Worker 注销完成", {
            count: registrations.length,
          });
        }

        // 3) 强制缓存击穿刷新（避免普通 reload 命中旧缓存）
        await sendUpdateLog("INFO", "即将执行强制刷新以加载新版本");
        await forceReloadWithBustTag();
        return;
      } else {
        await sendUpdateLog("INFO", "版本一致，无需刷新");
      }

      localStorage.setItem("siteVersion", latestVersion);
      await sendUpdateLog("DEBUG", "版本一致或首次加载，无需刷新");
    } catch (e) {
      await sendUpdateLog("ERROR", "版本检测失败", {
        error: e && e.message ? e.message : String(e),
      });
    }
  }

  checkVersion();
})();
