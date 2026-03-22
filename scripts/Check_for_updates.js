// 检查更新
async function checkVersion() {
  try {
    const res = await fetch('/api/version.json', { cache: 'no-cache' });
    const data = await res.json();
    const currentVersion = localStorage.getItem('siteVersion');

    if (currentVersion && currentVersion !== data.version) {
      // 版本不一致，强制刷新
      localStorage.setItem('siteVersion', data.version);
      location.reload(true);
    } else {
      // 首次或一致，更新本地版本号
      localStorage.setItem('siteVersion', data.version);
    }
  } catch (e) {
    console.error('版本检测失败', e);
  }
}

// 页面加载时执行
checkVersion();
