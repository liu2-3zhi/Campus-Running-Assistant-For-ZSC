// 去水印功能 - 调用新的API检查用户是否有权限
(async function() {
  try {
    // 获取当前 session ID
    const sessionId = sessionStorage.getItem('sessionUUID') || localStorage.getItem('sessionUUID');
    
    if (!sessionId) {
      console.log('[去水印] 未找到 Session ID，跳过加载');
      return;
    }
    
    // 调用 API 检查去水印功能是否启用
    const response = await fetch('/api/feature/watermark', {
      method: 'GET',
      headers: {
        'X-Session-ID': sessionId
      }
    });
    
    if (!response.ok) {
      console.log('[去水印] API 调用失败，跳过加载');
      return;
    }
    
    const result = await response.json();
    
    // 如果返回 true，则加载去水印脚本
    if (result.success && result.watermark_enabled === true) {
      console.log('[去水印] 功能已启用，加载去水印脚本');
      const amap_watermark = document.createElement('script');
      amap_watermark.src = '/scripts/Remove_watermark_from_Amap_Map.js';
      amap_watermark.async = false;
      document.head.appendChild(amap_watermark);
    } else {
      console.log('[去水印] 功能未启用');
    }
  } catch (error) {
    console.error('[去水印] 加载失败:', error);
  }
})();