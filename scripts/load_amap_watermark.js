// 获取去水印权限并加载脚本
(async function() {
  try {
    // 获取sessionUUID（如果存在）
    const sessionUUID = window.sessionUUID || null;
    
    // 调用API检查权限
    const response = await fetch('/api/watermark/permission', {
      method: 'GET',
      headers: {
        'X-Session-ID': sessionUUID || ''
      }
    });
    
    // 解析响应
    const result = await response.json();
    
    // 检查是否允许去水印
    if (result.allowed === true) {
      // 允许去水印，加载脚本
      console.log('[地图去水印] 权限检查通过，加载去水印脚本');
      const amap_watermark = document.createElement('script');
      amap_watermark.src = '/scripts/Remove_watermark_from_Amap_Map.js';
      amap_watermark.async = false;
      document.head.appendChild(amap_watermark);
    } else {
      // 不允许去水印
      console.log('[地图去水印] 权限检查未通过，跳过加载去水印脚本');
    }
  } catch (error) {
    // 发生错误时，为了保持向后兼容，默认加载脚本
    console.warn('[地图去水印] 权限检查失败，默认加载去水印脚本', error);
    const amap_watermark = document.createElement('script');
    amap_watermark.src = '/scripts/Remove_watermark_from_Amap_Map.js';
    amap_watermark.async = false;
    document.head.appendChild(amap_watermark);
  }
})();