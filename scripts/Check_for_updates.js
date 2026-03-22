// 检查更新
async function checkVersion() {
  try {
    const res = await fetch('/api/version.json', { cache: 'no-cache' });
    const data = await res.json();
    const currentVersion = localStorage.getItem('siteVersion');

    if (currentVersion && currentVersion !== data.version) {
      // 版本不一致，清除所有缓存后强制刷新所有文件
      localStorage.setItem('siteVersion', data.version);

      // 1. 清除 Cache API 中的所有缓存（包括 Service Worker 缓存）
      if ('caches' in window) {
        const cacheNames = await caches.keys();
        await Promise.all(cacheNames.map(name => caches.delete(name)));
      }

      // 2. 注销所有 Service Worker，确保下次加载时重新安装新版本 SW
      if ('serviceWorker' in navigator) {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map(reg => reg.unregister()));
      }

      // 3. 重新加载页面（SW 已清除，浏览器将从服务器重新获取所有文件）
      location.reload();
    } else {
      // 首次或版本一致，更新本地版本号
      localStorage.setItem('siteVersion', data.version);
    }
  } catch (e) {
    console.error('版本检测失败', e);
  }
}

// 页面加载时执行
checkVersion();
