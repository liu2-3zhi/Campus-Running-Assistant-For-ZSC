/**
 * Editor.md 对话框增强脚本
 * 功能：
 * 1. PC端和移动端支持拖动
 * 2. 移动端点击遮罩层关闭对话框
 * 3. 确保对话框居中显示
 */

(function() {
  'use strict';
  
  // 等待DOM加载完成
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEditorMdDialogEnhancements);
  } else {
    initEditorMdDialogEnhancements();
  }
  
  function initEditorMdDialogEnhancements() {
    // 使用MutationObserver监听对话框的创建
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === 1) { // Element node
            // 检查是否是Editor.md对话框
            if (node.classList && node.classList.contains('editormd-dialog')) {
              enhanceDialog(node);
            }
            // 检查是否是遮罩层
            if (node.classList && node.classList.contains('editormd-dialog-mask')) {
              enhanceMask(node);
            }
          }
        });
      });
    });
    
    // 开始观察document.body的子节点变化
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    
    // 检查是否已经存在对话框（针对已经加载的情况）
    document.querySelectorAll('.editormd-dialog').forEach(enhanceDialog);
    document.querySelectorAll('.editormd-dialog-mask').forEach(enhanceMask);
  }
  
  function enhanceDialog(dialog) {
    // 避免重复增强
    if (dialog.dataset.enhanced === 'true') {
      return;
    }
    dialog.dataset.enhanced = 'true';
    
    console.log('[Editor.md] 增强对话框:', dialog);
    
    // 添加拖动功能
    makeDraggable(dialog);
    
    // 确保对话框居中
    centerDialog(dialog);
  }
  
  function enhanceMask(mask) {
    // 避免重复增强
    if (mask.dataset.enhanced === 'true') {
      return;
    }
    mask.dataset.enhanced = 'true';
    
    console.log('[Editor.md] 增强遮罩层:', mask);
    
    // 移动端点击遮罩层关闭对话框
    if (isMobile()) {
      mask.addEventListener('click', function(e) {
        // 确保点击的是遮罩层本身，而不是对话框
        if (e.target === mask) {
          closeDialog();
        }
      });
    }
  }
  
  function makeDraggable(dialog) {
    const header = dialog.querySelector('.editormd-dialog-header');
    if (!header) {
      console.warn('[Editor.md] 未找到对话框标题栏');
      return;
    }
    
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;
    let xOffset = 0;
    let yOffset = 0;
    
    header.addEventListener('mousedown', dragStart);
    header.addEventListener('touchstart', dragStart, { passive: false });
    
    document.addEventListener('mousemove', drag);
    document.addEventListener('touchmove', drag, { passive: false });
    
    document.addEventListener('mouseup', dragEnd);
    document.addEventListener('touchend', dragEnd);
    
    function dragStart(e) {
      // 如果点击的是关闭按钮，不启动拖动
      if (e.target.classList.contains('editormd-dialog-close') || 
          e.target.closest('.editormd-dialog-close')) {
        return;
      }
      
      if (e.type === 'touchstart') {
        initialX = e.touches[0].clientX - xOffset;
        initialY = e.touches[0].clientY - yOffset;
      } else {
        initialX = e.clientX - xOffset;
        initialY = e.clientY - yOffset;
      }
      
      isDragging = true;
      
      // 移除transform，改用top/left定位
      dialog.style.transform = 'none';
      dialog.style.top = dialog.offsetTop + 'px';
      dialog.style.left = dialog.offsetLeft + 'px';
    }
    
    function drag(e) {
      if (!isDragging) return;
      
      e.preventDefault();
      
      if (e.type === 'touchmove') {
        currentX = e.touches[0].clientX - initialX;
        currentY = e.touches[0].clientY - initialY;
      } else {
        currentX = e.clientX - initialX;
        currentY = e.clientY - initialY;
      }
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, dialog);
    }
    
    function dragEnd() {
      isDragging = false;
    }
    
    function setTranslate(xPos, yPos, el) {
      el.style.left = xPos + 'px';
      el.style.top = yPos + 'px';
    }
  }
  
  function centerDialog(dialog) {
    // 确保对话框在视口中居中
    setTimeout(function() {
      const rect = dialog.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      
      // 计算居中位置
      const left = (viewportWidth - rect.width) / 2;
      const top = (viewportHeight - rect.height) / 2;
      
      // 设置位置
      dialog.style.left = Math.max(0, left) + 'px';
      dialog.style.top = Math.max(0, top) + 'px';
      dialog.style.transform = 'none';
    }, 100);
  }
  
  function closeDialog() {
    // 查找并点击关闭按钮
    const closeBtn = document.querySelector('.editormd-dialog-close');
    if (closeBtn) {
      closeBtn.click();
    } else {
      // 如果没有关闭按钮，直接移除对话框和遮罩
      const dialog = document.querySelector('.editormd-dialog');
      const mask = document.querySelector('.editormd-dialog-mask');
      if (dialog) dialog.remove();
      if (mask) mask.remove();
    }
  }
  
  function isMobile() {
    return window.innerWidth <= 768;
  }
})();
