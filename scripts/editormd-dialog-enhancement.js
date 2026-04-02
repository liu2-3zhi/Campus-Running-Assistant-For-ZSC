/**
 * Editor.md 对话框增强脚本
 * 功能：
 * 1. PC端和移动端支持拖动
 * 2. 移动端点击遮罩层关闭对话框
 * 3. 确保对话框居中显示
 */

(function() {
  'use strict';
  
  console.log('[Editor.md Enhancement] 脚本已加载');
  
  // 等待DOM加载完成
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEditorMdDialogEnhancements);
  } else {
    initEditorMdDialogEnhancements();
  }
  
  function initEditorMdDialogEnhancements() {
    console.log('[Editor.md Enhancement] 开始初始化');
    
    // 使用MutationObserver监听对话框的创建
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === 1) { // Element node
            // 检查是否是Editor.md对话框
            if (node.classList && node.classList.contains('editormd-dialog')) {
              console.log('[Editor.md Enhancement] 检测到对话框:', node);
              enhanceDialog(node);
            }
            // 检查是否是遮罩层
            if (node.classList && (node.classList.contains('editormd-dialog-mask') || node.classList.contains('editormd-mask'))) {
              console.log('[Editor.md Enhancement] 检测到遮罩层:', node);
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
    document.querySelectorAll('.editormd-dialog').forEach(function(dialog) {
      console.log('[Editor.md Enhancement] 发现已存在的对话框:', dialog);
      enhanceDialog(dialog);
    });
    document.querySelectorAll('.editormd-dialog-mask, .editormd-mask').forEach(function(mask) {
      console.log('[Editor.md Enhancement] 发现已存在的遮罩层:', mask);
      enhanceMask(mask);
    });
    
    console.log('[Editor.md Enhancement] 初始化完成');
  }
  
  function enhanceDialog(dialog) {
    // 避免重复增强
    if (dialog.dataset.enhanced === 'true') {
      console.log('[Editor.md Enhancement] 对话框已被增强，跳过');
      return;
    }
    dialog.dataset.enhanced = 'true';
    
    console.log('[Editor.md Enhancement] 正在增强对话框:', dialog);
    
    // 添加拖动功能
    makeDraggable(dialog);
    
    // 确保对话框居中
    centerDialog(dialog);
    
    console.log('[Editor.md Enhancement] 对话框增强完成');
  }
  
  function enhanceMask(mask) {
    // 避免重复增强
    if (mask.dataset.enhanced === 'true') {
      return;
    }
    mask.dataset.enhanced = 'true';
    
    console.log('[Editor.md Enhancement] 正在增强遮罩层:', mask);
    
    // 移动端点击遮罩层关闭对话框
    if (isMobile()) {
      mask.addEventListener('click', function(e) {
        // 确保点击的是遮罩层本身，而不是对话框
        if (e.target === mask) {
          console.log('[Editor.md Enhancement] 点击遮罩层，关闭对话框');
          closeDialog();
        }
      });
    }
  }
  
  function makeDraggable(dialog) {
    const header = dialog.querySelector('.editormd-dialog-header');
    if (!header) {
      console.warn('[Editor.md Enhancement] 未找到对话框标题栏');
      return;
    }
    
    console.log('[Editor.md Enhancement] 为对话框添加拖动功能');
    
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;
    
    // 记录对话框的初始位置
    let dialogLeft = 0;
    let dialogTop = 0;
    
    function dragStart(e) {
      // 如果点击的是关闭按钮或输入框，不启动拖动
      if (e.target.classList.contains('editormd-dialog-close') || 
          e.target.closest('.editormd-dialog-close') ||
          e.target.tagName === 'INPUT' ||
          e.target.tagName === 'TEXTAREA' ||
          e.target.tagName === 'SELECT' ||
          e.target.tagName === 'BUTTON') {
        return;
      }
      
      console.log('[Editor.md Enhancement] 开始拖动');
      
      // 获取当前对话框位置
      const rect = dialog.getBoundingClientRect();
      dialogLeft = rect.left;
      dialogTop = rect.top;
      
      if (e.type === 'touchstart') {
        initialX = e.touches[0].clientX;
        initialY = e.touches[0].clientY;
      } else {
        initialX = e.clientX;
        initialY = e.clientY;
      }
      
      isDragging = true;
      
      // 添加拖动样式
      dialog.classList.add('dragging');
      
      // 移除transform，改用top/left定位
      dialog.style.transform = 'none';
      dialog.style.left = dialogLeft + 'px';
      dialog.style.top = dialogTop + 'px';
      
      e.preventDefault();
    }
    
    function drag(e) {
      if (!isDragging) return;
      
      e.preventDefault();
      
      if (e.type === 'touchmove') {
        currentX = e.touches[0].clientX;
        currentY = e.touches[0].clientY;
      } else {
        currentX = e.clientX;
        currentY = e.clientY;
      }
      
      const deltaX = currentX - initialX;
      const deltaY = currentY - initialY;
      
      setPosition(dialogLeft + deltaX, dialogTop + deltaY);
    }
    
    function dragEnd(e) {
      if (isDragging) {
        console.log('[Editor.md Enhancement] 结束拖动');
        isDragging = false;
        dialog.classList.remove('dragging');
      }
    }
    
    function setPosition(left, top) {
      // 限制在视口内
      const maxLeft = window.innerWidth - dialog.offsetWidth;
      const maxTop = window.innerHeight - dialog.offsetHeight;
      
      left = Math.max(0, Math.min(left, maxLeft));
      top = Math.max(0, Math.min(top, maxTop));
      
      dialog.style.left = left + 'px';
      dialog.style.top = top + 'px';
    }
    
    // 绑定事件
    header.addEventListener('mousedown', dragStart);
    header.addEventListener('touchstart', dragStart, { passive: false });
    
    document.addEventListener('mousemove', drag);
    document.addEventListener('touchmove', drag, { passive: false });
    
    document.addEventListener('mouseup', dragEnd);
    document.addEventListener('touchend', dragEnd);
    
    console.log('[Editor.md Enhancement] 拖动功能已添加');
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
      
      console.log('[Editor.md Enhancement] 对话框已居中');
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
      const mask = document.querySelector('.editormd-dialog-mask, .editormd-mask');
      if (dialog) dialog.remove();
      if (mask) mask.remove();
    }
  }
  
  function isMobile() {
    return window.innerWidth <= 768;
  }
})();
