// Reminder management UI extracted from main.js.
async function loadReminders() {
  const listContainer = $("admin-reminders-list_modal");
  listContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch("/api/reminders/list", {
      method: "GET",
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();
    if (!result.success) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10">${
        result.message || "加载失败"
      }</p>`;
      return;
    }
    const reminders = result.reminders || [];
    const total = reminders.length;
    const enabled = reminders.filter((r) => r.enabled).length;
    const disabled = total - enabled;
    $("reminder-stat-total").textContent = total;
    $("reminder-stat-enabled").textContent = enabled;
    $("reminder-stat-disabled").textContent = disabled;
    if (reminders.length === 0) {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无提醒，点击"添加提醒"创建新提醒</p>';
      return;
    }
    listContainer.innerHTML = "";
    reminders.forEach((reminder, index) => {
      const itemDiv = document.createElement("div");
      itemDiv.className =
        "p-4 bg-white border border-slate-200 rounded-lg hover:shadow-md transition-shadow";
      const isCrossDay = reminder.start_time > reminder.end_time;
      const timeRangeClass = isCrossDay ? "text-purple-600" : "text-blue-600";
      const timeRangeIcon = isCrossDay ? "🌙" : "☀️";
      const timeRangeHint = isCrossDay ? "（跨天）" : "";
      // 为每个提醒的 Markdown 内容创建唯一ID
      const messageContainerId = `pc-reminder-message-${reminder.id}-${index}`;
      itemDiv.innerHTML = `
      <div class="flex justify-between items-start">
        <!-- 左侧：提醒信息 -->
        <div class="flex-1">
          <!-- 标题和状态标签 -->
          <div class="flex items-center gap-2 mb-2">
            <h5 class="font-semibold text-slate-800 text-base">${escapeHtml(
              reminder.title,
            )}</h5>
            ${
              reminder.enabled
                ? '<span class="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded">启用</span>'
                : '<span class="px-2 py-0.5 text-xs bg-slate-100 text-slate-600 rounded">禁用</span>'
            }
          </div>
          <!-- 提醒内容（Markdown渲染） -->
          <div id="${messageContainerId}" class="text-sm text-slate-600 mb-3 pc-reminder-markdown-content"></div>
          <!-- 时间范围 -->
          <div class="flex items-center gap-2 text-sm ${timeRangeClass}">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <span>${timeRangeIcon} ${reminder.start_time} - ${
              reminder.end_time
            } ${timeRangeHint}</span>
          </div>
          <!-- 创建和更新时间 -->
          <div class="mt-2 text-xs text-slate-400 space-y-0.5">
            <div>创建时间: ${formatTimestamp(reminder.created_at)}</div>
            ${
              reminder.updated_at && reminder.updated_at !== reminder.created_at
                ? `<div>更新时间: ${formatTimestamp(reminder.updated_at)}</div>`
                : ""
            }
          </div>
        </div>
        <!-- 右侧：操作按钮 -->
        <div class="flex flex-col gap-2 ml-4">
          <!-- 编辑按钮 -->
          <button onclick="openReminderEditModal(${escapeInlineJsArg(reminder.id)})"
            class="btn btn-ghost !py-1 !px-3 text-xs whitespace-nowrap hover:bg-sky-50 hover:text-sky-600"
            title="编辑提醒">
            <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
            </svg>
            编辑
          </button>
          <!-- 启用/禁用切换按钮 -->
          <button onclick="toggleReminderEnabled('${
            reminder.id
          }', ${!reminder.enabled})" 
            class="btn btn-ghost !py-1 !px-3 text-xs whitespace-nowrap ${
              reminder.enabled
                ? "hover:bg-yellow-50 hover:text-yellow-600"
                : "hover:bg-green-50 hover:text-green-600"
            }"
            title="${reminder.enabled ? "禁用提醒" : "启用提醒"}">
            <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="${
                  reminder.enabled
                    ? "M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                    : "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                }"></path>
            </svg>
            ${reminder.enabled ? "禁用" : "启用"}
          </button>

          <!-- 删除按钮 -->
          <button onclick="deleteReminder(${escapeInlineJsArg(reminder.id)}, ${escapeInlineJsArg(
            reminder.title,
          )})"
            class="btn btn-ghost !py-1 !px-3 text-xs whitespace-nowrap hover:bg-red-50 hover:text-red-600"
            title="删除提醒">
            <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
            </svg>
            删除
          </button>
        </div>
      </div>
    `;
      listContainer.appendChild(itemDiv);
    });
    
    // 使用 Editor.md 渲染所有提醒内容的 Markdown（与留言板 admin-messages-list_modal 相同方式）
    (function renderRemindersMarkdown(remindersList) {
      if (!remindersList || !remindersList.length) return;
      remindersList.forEach((reminder, index) => {
        const messageContainerId = `pc-reminder-message-${reminder.id}-${index}`;
        const container = document.getElementById(messageContainerId);
        if (!container) return;
        const markdownText = normalizeMarkdownText(reminder.message);

        // 优先使用 editormd.markdownToHTML（如果已加载 editormd）
        if (window.editormd && typeof editormd.markdownToHTML === "function") {
          try {
            // editormd.markdownToHTML 会替换指定容器内容
            editormd.markdownToHTML(messageContainerId, {
              markdown: markdownText,
              htmlDecode: "style,iframe,image",
              toc: false,
              tocContainer: "",
              gfm: true,
              tocDropdown: false,
              markdownSourceCode: false,
              emoji: true,
              taskList: true,
              tex: false,
              flowChart: false,
              sequenceDiagram: false,
            });
            return;
          } catch (e) {
            console.warn("[定时提醒] PC端Markdown渲染失败，回退为纯文本显示", e);
          }
        }

        // 最后回退：以转义文本并保留换行展示
        container.innerHTML = escapeHtml(markdownText).replace(
          /\n/g,
          "<br>",
        );
      });
    })(reminders);
    
    console.log(`[定时提醒] 已加载 ${reminders.length} 条提醒`);
  } catch (error) {
    console.error("[定时提醒] 加载失败:", error);
    listContainer.innerHTML = `<p class="text-red-500 text-center py-10">加载提醒时发生错误: ${error.message}</p>`;
  }
}
async function openReminderEditModal(reminderId = "") {
  const modal = $("reminder-edit-modal");
  const title = $("reminder-modal-title");
  const idField = $("reminder-id-field");
  const titleField = $("reminder-title-field");
  const messageField = $("reminder-message-field");
  // reminder 编辑器实例（按需初始化）
  const ensureReminderEditor = async () => {
    if (window._reminderEditorInitialized) return window.reminderEditor;
    const editorRoot = document.getElementById("reminder-editor");
    if (!editorRoot) return null;
    try {
      // 动态加载 editormd CSS/JS（如果尚未加载）
      const loadOnce = (url, isCss) => {
        return new Promise((resolve, reject) => {
          if (
            document.querySelector(
              isCss ? `link[href="${url}"]` : `script[src="${url}"]`,
            )
          )
            return resolve();
          const el = isCss
            ? document.createElement("link")
            : document.createElement("script");
          if (isCss) {
            el.rel = "stylesheet";
            el.href = url;
          } else {
            el.src = url;
          }
          el.onload = () => resolve();
          el.onerror = (e) => reject(e);
          if (isCss) document.head.appendChild(el);
          else document.body.appendChild(el);
        });
      };
      // 这里使用相对路径，项目中已有 editor.md 资源（若使用 CDN，请替换为 CDN 地址）
      await loadOnce("/editor.md/css/editormd.css", true).catch(() => {});
      // // 先加载 editormd 依赖库，再加载主体脚本，减少 race condition
      // await loadOnce("https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js", false).catch(() => {});
      // await loadOnce("https://cdn.jsdelivr.net/gh/google/code-prettify@master/loader/run_prettify.js", false).catch(() => {});
      // await loadOnce("/editor.md/editormd.js", false).catch(() => {});
      // 依赖库已经预价值 


      // 等待 window.editormd 可用（轮询），最长等待1500ms
      const waitForGlobal = (name, timeout = 1500) =>
        new Promise((resolve) => {
          const start = Date.now();
          const iv = setInterval(() => {
            if (window[name]) {
              clearInterval(iv);
              return resolve(true);
            }
            if (Date.now() - start > timeout) {
              clearInterval(iv);
              return resolve(false);
            }
          }, 50);
        });

      const ready = await waitForGlobal("editormd", 1500).catch(() => false);
      if (ready && window.editormd) {
        window.reminderEditor = editormd("reminder-editor", {
          // ===== 基本配置 =====
          // 编辑器模式：
          // gfm：GitHub Flavored Markdown，与 Markdown 语法基本相同，但增加了一些扩展语法，如表格、任务列表等
          // markdown：标准 Markdown 语法
          mode: "gfm",
          // 表单元素名称，用于提交表单时标识该编辑器
          name: "reminder-message-field",
          // CodeMirror 的值，如果模式不是 gfm/markdown（通常不需要设置，留空即可）
          value: "",
          // 编辑器主题，可选值：default（默认主题）, dark（暗色主题）
          theme: "default",
          // 编辑区域主题（代码编辑区域的样式），可选值包括：
          // default, 3024-day, 3024-night, ambiance, ambiance-mobile, base16-dark, base16-light,
          // blackboard, cobalt, eclipse, elegant, erlang-dark, lesser-dark, mbo, mdn-like,
          // midnight, monokai, neat, neo, night, paraiso-dark, paraiso-light, pastel-on-dark,
          // rubyblue, solarized, the-matrix, tomorrow-night-eighties, twilight, vibrant-ink,
          // xq-dark, xq-light
          editorTheme: "default",
          // 预览区域主题，默认空表示使用默认主题，可选值：default（默认主题）, dark（暗色主题）
          previewTheme: "default",
          // Markdown 源代码（编辑器初始化时显示的内容，可以是预填的 Markdown 文本）
          markdown: "",
          // 如果初始化时 textarea 值不为空，则追加 markdown 到 textarea（通常用于追加内容到现有文本）
          appendMarkdown: "",
          // 编辑器宽度（支持百分比如"100%"或像素值如"800px"）
          width: "auto",
          // 编辑器高度（支持百分比如"100%"或像素值如"600px"）
          height: "400px",
          // 依赖模块文件目录（Editor.md 所需的文件路径，通常使用 CDN 地址）
          path: "/editor.md/lib/",
          // 插件路径，如果为空，默认使用 settings.path + "../plugins/"（插件存放目录）
          pluginPath: "/editor.md/plugins/",
          // 延迟解析 markdown 到 html，单位：毫秒（避免频繁解析，提升性能，默认300ms）
          delay: 300,
          // 自动加载依赖模块文件（推荐保持 true，确保所有功能正常工作）
          autoLoadModules: true,
          // ===== 编辑器行为配置 =====
          // 监听模式（是否实时预览，true 为开启监听，false 为手动预览）
          watch: true,
          // 占位符文本（当编辑器为空时显示的提示文本，引导用户输入）
          placeholder: "请输入提醒内容（支持 Markdown）",
          // 启用/禁用 跳转到行功能（Ctrl+G 快捷键，快速跳转到指定行）
          gotoLine: true,
          // 代码折叠（是否允许折叠代码块，方便查看长代码）
          codeFold: false,
          // 自动高度（是否根据内容自动调整编辑器高度，true 时高度自适应）
          autoHeight: false,
          // 启用/禁用 自动聚焦编辑器左侧输入区域（页面加载后自动聚焦到编辑器）
          autoFocus: true,
          // 自动关闭标签（输入 < 时自动补全标签，提高 HTML 编写效率）
          autoCloseTags: true,
          // 启用/禁用 搜索和替换功能（CodeMirror 的搜索功能，Ctrl+F 激活）
          searchReplace: true,
          // 同步滚动选项：true（同步滚动）| false（不同步）| "single"（单向同步），默认 true
          syncScrolling: true,
          // 启用/禁用 只读模式（设为 true 后无法编辑，只能查看）
          readOnly: false,
          // 制表符大小（Tab 键缩进的空格数，通常设为 4）
          tabSize: 4,
          // 缩进单位（每次缩进的空格数，通常与 tabSize 保持一致）
          indentUnit: 4,
          // 显示编辑器行号（左侧显示行号，便于定位代码位置）
          lineNumbers: true,
          // 行换行（是否自动换行，true 时长行会自动换行）
          lineWrapping: true,
          // 自动关闭括号（输入左括号时自动补全右括号，支持 (), [], {}）
          autoCloseBrackets: true,
          // 显示尾随空格（显示行末的空格字符，帮助保持代码整洁）
          showTrailingSpace: true,
          // 匹配括号（高亮匹配的括号对，方便检查括号匹配）
          matchBrackets: true,
          // 使用制表符缩进（true 使用 Tab 字符，false 使用空格）
          indentWithTabs: true,
          // 样式化选中文本（选中的文本是否有特殊样式，如背景色）
          styleSelectedText: true,
          // 匹配单词高亮：true（高亮所有相同单词）| false（不高亮）| "onselected"（只在选中时高亮）
          matchWordHighlight: true,
          // 高亮当前行（当前行是否有背景色，方便定位）
          styleActiveLine: true,
          // ===== 对话框配置 =====
          // 对话框锁定屏幕（对话框弹出时是否锁定背景，防止误操作）
          dialogLockScreen: true,
          // 对话框显示遮罩（是否显示半透明遮罩层）
          dialogShowMask: true,
          // 对话框可拖拽（对话框是否可以拖动位置）
          dialogDraggable: true,
          // 对话框遮罩背景色（遮罩的颜色，通常使用白色或半透明）
          dialogMaskBgColor: "#fff",
          // 对话框遮罩不透明度（0.0 到 1.0，控制遮罩透明度）
          dialogMaskOpacity: 0.1,
          // 字体大小（编辑器内文字的大小，影响可读性）
          fontSize: "13px",
          // 如果启用，编辑器将创建一个 <textarea> 标签保存 HTML 代码用于表单提交
          saveHTMLToTextarea: true,
          // 禁用的键映射（禁用某些快捷键，数组格式，如 ["Ctrl-B", "Ctrl-I"]）
          disabledKeyMaps: [],

          // ===== 事件回调函数 =====
          // 加载完成回调（编辑器初始化完成后触发）
          onload: function () {},
          // 调整大小回调（编辑器大小改变时触发）
          onresize: function () {},
          // 内容改变回调（编辑器内容发生变化时触发）
          onchange: function () {},
          // 监听开始回调（开始监听模式时触发）
          onwatch: null,
          // 监听结束回调（结束监听模式时触发）
          onunwatch: null,
          // 预览中回调（正在生成预览时触发）
          onpreviewing: function () {},
          // 预览完成回调（预览生成完成后触发）
          onpreviewed: function () {},
          // 全屏回调（进入全屏模式时触发）
          onfullscreen: function () {},
          // 退出全屏回调（退出全屏模式时触发）
          onfullscreenExit: function () {},
          // 滚动回调（编辑器滚动时触发）
          onscroll: function () {},
          // 预览滚动回调（预览区域滚动时触发）
          onpreviewscroll: function () {},

          // ===== 图片上传配置 =====
          // 启用/禁用 上传功能（是否允许上传图片到服务器）
          imageUpload: true,
          // 支持的图片格式（允许上传的图片文件类型数组）
          imageFormats: ["jpg", "jpeg", "gif", "png", "bmp", "webp"],
          // 上传 URL（图片上传的服务器端点地址）
          imageUploadURL: "/upload",
          // 启用/禁用 跨域上传（是否支持跨域上传图片）
          crossDomainUpload: false,
          // 跨域上传回调 URL（跨域上传时的回调地址，用于处理上传结果）
          // uploadCallbackURL: "",

          // ===== 目录和扩展功能配置 =====
          // 启用/禁用 目录功能（是否自动生成文章目录）
          toc: true,
          // 使用 [TOCM]，自动创建目录下拉菜单（在标题前添加 [TOCM] 标记启用）
          tocm: false,
          // 目录下拉菜单按钮标题（下拉菜单的显示文本）
          tocTitle: "",
          // 启用/禁用 目录下拉菜单（是否显示目录下拉菜单按钮）
          tocDropdown: false,
          // 自定义目录容器选择器（目录插入的 DOM 元素选择器，默认插入编辑器内部）
          tocContainer: "",
          // 从 H1 开始创建目录（目录从哪一级标题开始生成，1表示H1，2表示H2）
          tocStartLevel: 1,
          // 打开 HTML 标签识别（是否解析和显示 HTML 标签）
          htmlDecode: true,
          // 启用解析分页符 [========]（是否支持分页符语法，用于分隔内容）
          pageBreak: true,
          // 启用 @链接功能（@用户名 自动转换为链接）
          atLink: false,
          // 邮箱地址自动链接（自动识别邮箱地址并转换为可点击链接）
          emailLink: true,
          // 启用 GitHub Flavored Markdown 任务列表（支持 - [ ] 任务列表语法）
          taskList: true,
          // 启用表情符号支持：
          // :emoji: 支持 GitHub 表情、Twitter 表情 (Twemoji)
          // :fa-xxx: 使用 FontAwesome 图标 web 字体
          // :editormd-logo: :editormd-logo-1x: > 1~8x 支持 Editor.md logo 图标
          emoji: true,
          // 启用 TeX(LaTeX) 数学公式支持，基于 KaTeX 库
          tex: true,
          // 启用流程图支持（flowChart.js，只支持 IE9+，用于绘制流程图）
          flowChart: true,
          // 启用时序图支持（sequenceDiagram.js，只支持 IE9+，用于绘制时序图）
          sequenceDiagram: true,
          // 启用/禁用 编辑器预览区域代码高亮（预览区代码是否进行语法高亮）
          previewCodeHighlight: true,

          // ===== 工具栏配置 =====
          // 显示或隐藏工具栏
          toolbar: true,
          // 窗口滚动时自动固定工具栏位置
          toolbarAutoFixed: true,
          // 工具栏图标模式：full（完整）| simple（简单）| mini（最小），参见 `editormd.toolbarModes` 属性
          toolbarIcons: "full",
          // 工具栏标题（自定义工具栏按钮的提示文本）
          toolbarTitles: {},
          // 工具栏处理程序（自定义工具栏按钮的点击事件）
          toolbarHandlers: {},
          // 使用 HTML 标签创建工具栏图标，未使用默认 <a> 标签（自定义工具栏图标的 HTML）
          toolbarCustomIcons: {},
          // 工具栏图标文本（自定义工具栏按钮的文本）
          toolbarIconTexts: {},
          // 父容器层级（用于解决全屏模式下的定位问题）
          parentContainerLayer:"3",
        });
        window._reminderEditorInitialized = true;
        // 在初始化完成后，短延迟刷新编辑器以确保首次打开时预览/渲染正常
        setTimeout(() => {
          try {
            if (
              window.reminderEditor &&
              window.reminderEditor.codeMirror &&
              typeof window.reminderEditor.codeMirror.refresh === "function"
            ) {
              window.reminderEditor.codeMirror.refresh();
            }
            if (
              window.reminderEditor &&
              typeof window.reminderEditor.recreate === "function"
            ) {
              try {
                window.reminderEditor.recreate();
              } catch (e) {}
            }
          } catch (e) {}
        }, 60);

        if (reminderId == "-1") {
          messageField.value = true;
        }
        // 如果之前有值，确保编辑器同步
        if (messageField && messageField.value) {
          try {
            if (
              window.reminderEditor &&
              typeof window.reminderEditor.setMarkdown === "function"
            ) {
              window.reminderEditor.setMarkdown(messageField.value);
            } else if (
              window.reminderEditor &&
              window.reminderEditor.codeMirror
            ) {
              window.reminderEditor.codeMirror.setValue(messageField.value);
            }
          } catch (e) {
            console.warn("同步提醒内容到编辑器失败:", e);
          }
        }
        return window.reminderEditor;
      }
      return null;
    } catch (e) {
      console.warn("初始化 reminder 编辑器失败:", e);
      return null;
    }
  };
  const startTimeField = $("reminder-start-time-field");
  const endTimeField = $("reminder-end-time-field");
  const enabledField = $("reminder-enabled-field");
  if (reminderId) {
    console.log("[定时提醒] 加载提醒数据，ID:", reminderId);
    title.textContent = "✏️ 编辑定时提醒";
    if (reminderId === "-1") {
      console.log("[定时提醒] 使用示例数据填充编辑器");
      idField.value = "example-001";
      titleField.value = "示例提醒标题";
      messageField.value =
        "# 示例提醒内容\n这是一个定时提醒的**示例内容**，支持 _Markdown_ 语法。";
      startTimeField.value = "00:00";
      endTimeField.value = "00:00";
      enabledField.checked = true;
    } else {
      try {
        const response = await fetch("/api/reminders/list", {
          method: "GET",
          headers: { "X-Session-ID": sessionUUID },
        });
        const result = await response.json();
        if (result.success) {
          const reminder = result.reminders.find((r) => r.id === reminderId);
          if (reminder) {
            idField.value = reminder.id;
            titleField.value = reminder.title;
            // 如果编辑器已初始化，设置编辑器内容；否则设置隐藏 textarea 值
            if (window._reminderEditorInitialized && window.reminderEditor) {
              try {
                if (typeof window.reminderEditor.setMarkdown === "function") {
                  window.reminderEditor.setMarkdown(reminder.message || "");
                } else if (window.reminderEditor.codeMirror) {
                  window.reminderEditor.codeMirror.setValue(
                    reminder.message || "",
                  );
                }
              } catch (e) {
                messageField.value = reminder.message || "";
              }
            } else {
              messageField.value = reminder.message || "";
            }
            startTimeField.value = reminder.start_time;
            endTimeField.value = reminder.end_time;
            enabledField.checked = reminder.enabled;
          } else {
            showModalAlert("提醒不存在", "错误");
            return;
          }
        }
      } catch (error) {
        console.error("[定时提醒] 加载提醒数据失败:", error);
        showModalAlert("加载提醒数据失败", "错误");
        return;
      }
    }
  } else {
    title.textContent = "⏰ 添加定时提醒";
    idField.value = "";
    titleField.value = "";
    messageField.value = "";
    startTimeField.value = "";
    endTimeField.value = "";
    enabledField.checked = true;
    try {
      if (
        typeof window.reminderEditor !== "undefined" &&
        window.reminderEditor
      ) {
        if (typeof window.reminderEditor.clear === "function") {
          window.reminderEditor.clear();
        } else if (typeof window.reminderEditor.setMarkdown === "function") {
          window.reminderEditor.setMarkdown("");
        } else if (
          window.reminderEditor.codeMirror &&
          typeof window.reminderEditor.codeMirror.setValue === "function"
        ) {
          window.reminderEditor.codeMirror.setValue("");
        }
      }
    } catch (e) {
      console.warn("清空 reminder 编辑器失败:", e);
    }
  }
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  // 延迟初始化编辑器以避免每次打开都加载资源
  setTimeout(() => {
    ensureReminderEditor().then((editor) => {
      try {
        if (!reminderId) {
          const ed = editor || window.reminderEditor;
          if (ed) {
            if (typeof ed.clear === "function") {
              ed.clear();
            } else if (typeof ed.setMarkdown === "function") {
              ed.setMarkdown("");
            } else if (
              ed.codeMirror &&
              typeof ed.codeMirror.setValue === "function"
            ) {
              ed.codeMirror.setValue("");
            } else {
              const msgF = $("reminder-message-field");
              if (msgF) msgF.value = "";
            }
          }
        }
      } catch (e) {
        console.warn("延迟清空 reminder 编辑器失败:", e);
      }
      titleField.focus();
    });
  }, 50);
}
function closeReminderEditModal() {
  const modal = $("reminder-edit-modal");
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}
async function saveReminder() {
  const id = $("reminder-id-field").value.trim();
  const title = $("reminder-title-field").value.trim();
  let message = "";
  if (
    window._reminderEditorInitialized &&
    window.reminderEditor &&
    typeof window.reminderEditor.getMarkdown === "function"
  ) {
    try {
      message = window.reminderEditor.getMarkdown().trim();
    } catch (e) {
      message = $("reminder-message-field").value.trim();
    }
  } else {
    message = $("reminder-message-field").value.trim();
  }
  const startTime = $("reminder-start-time-field").value;
  const endTime = $("reminder-end-time-field").value;
  const enabled = $("reminder-enabled-field").checked;
  if (!title) {
    showModalAlert("请输入提醒标题", "错误");
    return;
  }
  if (title.length > 50) {
    showModalAlert("提醒标题不能超过50个字符", "错误");
    return;
  }
  if (!message) {
    showModalAlert("请输入提醒内容", "错误");
    return;
  }
  if (message.length > 500) {
    showModalAlert("提醒内容不能超过500个字符", "错误");
    return;
  }
  if (!startTime || !endTime) {
    showModalAlert("请选择开始时间和结束时间", "错误");
    return;
  }
  const timePattern = /^([0-1][0-9]|2[0-3]):[0-5][0-9]$/;
  if (!timePattern.test(startTime) || !timePattern.test(endTime)) {
    showModalAlert("时间格式错误，应为 HH:MM（如 19:00）", "错误");
    return;
  }

  try {
    const isUpdate = !!id;
    const apiUrl = isUpdate ? "/api/reminders/update" : "/api/reminders/add";
    const requestData = {
      title: title,
      message: message,
      start_time: startTime,
      end_time: endTime,
      enabled: enabled,
    };
    if (isUpdate) {
      requestData.id = id;
    }
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(requestData),
    });
    const result = await response.json();
    if (result.success) {
      showModalAlert(
        isUpdate ? "提醒更新成功" : "提醒添加成功",
        "成功",
        "success",
      );
      // 清空输入（兼容 editormd 编辑器或普通 textarea）
      try {
        const idF = $("reminder-id-field");
        const titleF = $("reminder-title-field");
        const msgF = $("reminder-message-field");
        const startF = $("reminder-start-time-field");
        const endF = $("reminder-end-time-field");
        const enabledF = $("reminder-enabled-field");
        if (idF) idF.value = "";
        if (titleF) titleF.value = "";
        if (startF) startF.value = "";
        if (endF) endF.value = "";
        if (enabledF) enabledF.checked = true;
        if (
          typeof window.reminderEditor !== "undefined" &&
          window.reminderEditor
        ) {
          if (typeof window.reminderEditor.clear === "function") {
            window.reminderEditor.clear();
          } else if (typeof window.reminderEditor.setMarkdown === "function") {
            window.reminderEditor.setMarkdown("");
          } else if (
            window.reminderEditor.codeMirror &&
            typeof window.reminderEditor.codeMirror.setValue === "function"
          ) {
            window.reminderEditor.codeMirror.setValue("");
          }
        } else if (msgF) {
          msgF.value = "";
        }
      } catch (e) {
        console.warn("清空提醒输入失败:", e);
      }

      closeReminderEditModal();
      loadReminders();
    } else {
      showModalAlert(result.message || "保存失败", "错误");
    }
  } catch (error) {
    console.error("[定时提醒] 保存失败:", error);
    showModalAlert("保存提醒时发生错误: " + error.message, "错误");
  }
}
async function toggleReminderEnabled(reminderId, newEnabledState) {
  try {
    const response = await fetch("/api/reminders/update", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        id: reminderId,
        enabled: newEnabledState,
      }),
    });

    const result = await response.json();

    if (result.success) {
      console.log(
        `[定时提醒] 提醒状态已更新: ID=${reminderId}, enabled=${newEnabledState}`,
      );
      loadReminders();
    } else {
      showModalAlert(result.message || "更新状态失败", "错误");
    }
  } catch (error) {
    console.error("[定时提醒] 更新状态失败:", error);
    showModalAlert("更新提醒状态时发生错误: " + error.message, "错误");
  }
}
async function deleteReminder(reminderId, reminderTitle) {
  const confirmed = await Swal.fire({
    title: "确认删除？",
    html: `确定要删除提醒 <strong>${escapeHtml(
      reminderTitle,
    )}</strong> 吗？<br><span class="text-sm text-slate-500">此操作不可恢复</span>`,
    icon: "warning",
    showCancelButton: true,
    confirmButtonText: "确认删除",
    cancelButtonText: "取消",
    confirmButtonColor: "#ef4444",
    cancelButtonColor: "#64748b",
  });
  if (!confirmed.isConfirmed) {
    return;
  }
  try {
    const response = await fetch("/api/reminders/delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ id: reminderId }),
    });
    const result = await response.json();
    if (result.success) {
      showModalAlert("提醒已删除", "成功", "success");
      loadReminders();
    } else {
      showModalAlert(result.message || "删除失败", "错误");
    }
  } catch (error) {
    console.error("[定时提醒] 删除失败:", error);
    showModalAlert("删除提醒时发生错误: " + error.message, "错误");
  }
}
function formatTimestamp(timestamp) {
  const date = new Date(timestamp * 1000);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const seconds = String(date.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}
let shownReminders = new Set();
/**
 * 检查并显示定时提醒
 *
 * 功能说明：
 * 1. 定期向后端查询需要显示的提醒
 * 2. 过滤出尚未显示的新提醒（避免重复显示）
 * 3. 根据提醒数量决定显示方式：
 *    - 单个提醒：独立弹窗显示
 *    - 多个提醒：合并到一个弹窗中显示（解决覆盖问题）
 *
 * 修复说明：
 * - 原有问题：使用 for 循环逐个调用 Swal.fire()，导致后一个提醒覆盖前一个
 * - 解决方案：先收集所有新提醒，然后根据数量选择合适的显示方式
 */
async function checkAndShowReminders() {
  // 验证 sessionUUID 是否存在
  // sessionUUID 是用户会话的唯一标识符，用于后端识别当前用户
  if (!sessionUUID) {
    // 尝试从 URL 中获取 UUID（用户进入系统时会生成）
    sessionUUID = getUUIDFromURL();
    if (!sessionUUID) {
      // 如果仍然无法获取 UUID，记录错误并退出
      // 这种情况通常发生在用户未正确登录或会话已过期
      logMessage_Error("跳过提醒检查: sessionUUID 未定义");
      return;
    }
  }

  try {
    // 向后端 API 发起请求，检查是否有需要显示的提醒
    const response = await fetch("/api/reminders/check", {
      method: "GET", // 使用 GET 方法查询数据
      headers: {
        // 在请求头中携带 sessionUUID，让后端知道是哪个用户在查询
        "X-Session-ID": sessionUUID,
      },
    });

    // 解析后端返回的 JSON 数据
    const result = await response.json();

    // 检查后端是否成功处理请求
    if (!result.success) {
      // 如果失败，记录错误信息并退出
      console.error("[定时提醒] 检查失败:", result.message);
      return;
    }

    // 获取后端返回的提醒列表
    // 如果后端没有返回 reminders 字段，使用空数组作为默认值
    const reminders = result.reminders || [];

    // ==================== 核心修复逻辑开始 ====================

    // 过滤出尚未显示过的新提醒
    // shownReminders 是一个 Set 集合，用于记录已显示过的提醒 ID
    // 这样可以避免同一个提醒被重复显示
    const newReminders = reminders.filter((r) => !shownReminders.has(r.id));

    // 如果没有新提醒需要显示，直接返回，不做任何操作
    if (newReminders.length === 0) {
      return;
    }

    // 将所有新提醒的 ID 添加到已显示集合中
    // 这样下次检查时就不会再显示这些提醒了
    newReminders.forEach((r) => shownReminders.add(r.id));

    // 注入提醒弹窗专用样式，确保不同标题层级显示区别
    const ensureReminderAlertStyles = () => {
      if (document.getElementById("reminder-alert-styles")) return;
      const style = document.createElement("style");
      style.id = "reminder-alert-styles";
      style.textContent = `
      .reminder-alert-popup .swal2-title { font-size: 1.25rem; font-weight: 600; }
      .reminder-alert-popup .reminder-alert-content h1 { font-size: 1.5rem; margin: 0 0 .5rem; }
      .reminder-alert-popup .reminder-alert-content h2 { font-size: 1.25rem; margin: 0 0 .45rem; }
      .reminder-alert-popup .reminder-alert-content h3 { font-size: 1.1rem; margin: 0 0 .4rem; }
      .reminder-alert-popup .reminder-alert-content h4 { font-size: 1rem; margin: 0 0 .35rem; }
      .reminder-alert-popup .reminder-alert-content h5 { font-size: .9rem; margin: 0 0 .3rem; }
      .reminder-alert-popup .reminder-alert-content h6 { font-size: .8rem; margin: 0 0 .25rem; color: #6b7280; }
      .reminder-alert-popup .reminder-alert-content { line-height: 1.45; }
      `;
      document.head.appendChild(style);
    };

    // 预加载 editormd 及其依赖，避免在渲染时缺少 marked/prettify 导致错误
    const preloadEditormdDeps = async () => {
      const loadOnce = (url, isCss) => {
        return new Promise((resolve, reject) => {
          try {
            if (
              document.querySelector(
                isCss ? `link[href="${url}"]` : `script[src="${url}"]`,
              )
            )
              return resolve();
            const el = isCss
              ? document.createElement("link")
              : document.createElement("script");
            if (isCss) {
              el.rel = "stylesheet";
              el.href = url;
            } else {
              el.src = url;
            }
            el.onload = () => resolve();
            el.onerror = (e) => reject(e);
            if (isCss) document.head.appendChild(el);
            else document.body.appendChild(el);
          } catch (e) {
            reject(e);
          }
        });
      };

      try {
        // editormd 样式与核心脚本
        await loadOnce("/editor.md/css/editormd.css", true).catch(() => {});
        await loadOnce("/editor.md/editormd.js", false).catch(() => {});
        // // editormd 渲染依赖
        // await loadOnce("https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js", false).catch(() => {});
        // await loadOnce("https://cdn.jsdelivr.net/gh/google/code-prettify@master/loader/run_prettify.js", false).catch(() => {});
        // 依赖库已经预加载

        console.log("[定时提醒] 预加载 editormd 及依赖完成");
      } catch (e) {
        console.warn("[定时提醒] 预加载 editormd 及依赖时发生错误:", e);
      }
    };

    // 尝试预加载（不阻塞太久）并注入样式
    // preloadEditormdDeps();
    // ensureReminderAlertStyles();

    // Helper: 将 Markdown 转为 HTML（仅使用 editormd.markdownToHTML，若不可用则回退为转义文本）
    const renderMarkdownToHtml = async (md) => {
      const normalizedMd = typeof md === "string" ? md : md == null ? "" : String(md);
      if (!normalizedMd) {
        console.log("[定时提醒] 提醒内容为空，跳过渲染");
        return "";
      }

      const loadOnce = (url, isCss) => {
        return new Promise((resolve, reject) => {
          try {
            if (
              document.querySelector(
                isCss ? `link[href="${url}"]` : `script[src="${url}"]`,
              )
            )
              return resolve();
            const el = isCss
              ? document.createElement("link")
              : document.createElement("script");
            if (isCss) {
              el.rel = "stylesheet";
              el.href = url;
            } else {
              el.src = url;
            }
            el.onload = () => resolve();
            el.onerror = (e) => reject(e);
            if (isCss) document.head.appendChild(el);
            else document.body.appendChild(el);
          } catch (e) {
            reject(e);
          }
        });
      };

      const loadAllDependencies = async () => {
        setTimeout(async () => {
          await loadOnce("/editor.md/editormd.js", false).catch(() => {
            console.warn("延迟加载 editormd.js 失败");
          });
          // await loadOnce("https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js", false).catch(() => {
          //   console.warn("延迟加载 marked 失败");
          // });
          // await loadOnce("https://cdn.jsdelivr.net/gh/google/code-prettify@master/loader/run_prettify.js", false).catch(() => {
          //   console.warn("延迟加载 prettify 失败");
          // });

          // await loadOnce("/editor.md/lib/flowchart.min.js", false).catch(() => {
          //   console.warn("延迟加载 flowchart 失败");
          // });
          // await loadOnce("/editor.md/lib/jquery.flowchart.min.js", false).catch(
          //   () => {
          //     console.warn("延迟加载 jquery.flowchart 失败");
          //   },
          // );
          // await loadOnce("/editor.md/lib/raphael.min.js", false).catch(() => {
          //   console.warn("延迟加载 raphael 失败");
          // });
          // await loadOnce("/editor.md/lib/sequence-diagram.min.js", false).catch(
          //   () => {
          //     console.warn("延迟加载 sequence-diagram 失败");
          //   },
          // );
          // await loadOnce("/editor.md/lib/underscore.min.js", false).catch(
          //   () => {
          //     console.warn("延迟加载 underscore 失败");
          //   },
          // );
          // 依赖库已经预加载
        }, 500);
      };

      // await loadAllDependencies();

      const tryRender = () => {
        if (window.editormd && typeof editormd.markdownToHTML === "function") {
          const tmpId =
            "md-to-html-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
          const tmp = document.createElement("div");
          tmp.id = tmpId;
          tmp.style.display = "none";
          tmp.innerHTML =
            '<link rel="stylesheet" href="/editor.md/css/editormd.css" /> <link rel="stylesheet" href="/editor.md/css/editormd.preview.css" />';
          console.log(
            "[定时提醒] 使用 editormd.renderMarkdownToHtml 渲染内容: ",
            normalizedMd,
          );
          document.body.appendChild(tmp);
          try {
            editormd.markdownToHTML(tmpId, {
              markdown: normalizedMd,
              htmlDecode: true, // 开启 HTML 标签解析，为了安全性，默认不开启
              // htmlDecode: "style,iframe,image,div,p,br,hr,strong,em,span,blockquote,q,cite,code,pre",  // 允许解析的 HTML 标签
              htmlDecode: "style,iframe,image",
              toc: false, // 是否生成目录
              tocContainer: "", // 自定义 ToC 容器层
              gfm: true, // 是否使用 GitHub Flavored Markdown
              tocDropdown: false, // 是否启用目录下拉菜单
              markdownSourceCode: false, // 是否保留 Markdown 源码，即是否删除保存源码的 Textarea 标签
              emoji: true,
              taskList: true,
              tex: true, // 默认不解析
              flowChart: true, // 默认不解析
              sequenceDiagram: true, // 默认不解析
            });
            const html = tmp.innerHTML;
            console.log(
              "[定时提醒] editormd.markdownToHTML 渲染完成，结果：",
              html,
            );
            document.body.removeChild(tmp);
            console.log(
              "[定时提醒] 使用 editormd.renderMarkdownToHtml 渲染内容成功，内容：",
              html,
            );
            return html;
          } catch (e) {
            document.body.removeChild(tmp);
            throw e;
          }
        }
        return null;
      };

      try {
        const r = tryRender();
        if (r !== null) return r;
      } catch (err) {
        console.warn(
          "[定时提醒] 使用 editormd.renderMarkdownToHtml 渲染内容失败，尝试加载依赖并重试:",
          err,
        );

        try {
          // await loadOnce("https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js", false).catch(() => {});
          // await loadOnce("https://cdn.jsdelivr.net/gh/google/code-prettify@master/loader/run_prettify.js", false).catch(
          //   () => {},
          // );
          // 依赖库已经预加载
        } catch (e) {
          console.warn("[定时提醒] 加载 editormd 依赖失败:", e);
        }

        try {
          const r2 = tryRender();
          if (r2 !== null) return r2;
        } catch (err2) {
          console.warn(
            "[定时提醒] 重试 editormd.renderMarkdownToHtml 仍然失败，回退为转义文本:",
            err2,
          );
        }
      }

      // 回退：转义后换行
      return escapeHtml(normalizedMd).replace(/\n/g, "<br>");
    };

    // 根据新提醒的数量，选择不同的显示方式
    if (newReminders.length === 1) {
      // ==================== 单个提醒的处理 ====================
      // 只有一个提醒时，使用原有的简洁显示方式

      const reminder = newReminders[0];

      let swalHtmlContent = await renderMarkdownToHtml(reminder.message);

      console.log(
        `[定时提醒] 准备显示单个提醒: ${reminder.title}, 内容： ${swalHtmlContent}`,
      );

      // 使用 SweetAlert2 显示提醒弹窗
      Swal.fire({
        title: reminder.title, // 提醒标题
        // 使用 Markdown 渲染为 HTML（优先 marked/editormd），回退为换行处理
        html: swalHtmlContent,
        icon: "warning", // 使用信息图标
        confirmButtonText: "知道了", // 确认按钮文字
        allowOutsideClick: true, // 允许点击弹窗外部关闭
        allowEscapeKey: true, // 允许按 ESC 键关闭
        customClass: {
          // 自定义样式类名，用于统一提醒弹窗的外观
          popup: "reminder-alert-popup",
          title: "reminder-alert-title",
          htmlContainer: "reminder-alert-content",
        },
      });

      // 在控制台记录日志，便于调试
      console.log(`[定时提醒] 已显示提醒: ${reminder.title}`);
    } else {
      // ==================== 多个提醒的处理（核心修复） ====================
      // 有多个提醒时，依次显示多个独立的弹窗，而不是合并到一个弹窗中
      // 这样可以让用户更清楚地看到每一条提醒的完整信息

      // 在控制台记录即将显示的提醒数量，便于调试
      console.log(`[定时提醒] 准备依次显示 ${newReminders.length} 条提醒`);

      // 使用立即执行的异步函数来处理多个弹窗的依次显示
      // 必须使用 async/await 才能确保弹窗按顺序显示，避免同时弹出
      (async () => {
        // 遍历所有新提醒，为每个提醒显示一个独立的弹窗
        for (let i = 0; i < newReminders.length; i++) {
          // 获取当前索引对应的提醒对象
          const reminder = newReminders[i];

          // 显示当前提醒的独立弹窗
          // 使用 await 等待用户关闭当前弹窗后，再显示下一个
          const htmlContent = await renderMarkdownToHtml(reminder.message);
          await Swal.fire({
            // 标题：显示提醒的标题，并标注这是第几条提醒（例如：1/3）
            // 这样用户可以知道还有多少提醒需要查看
            title: `${reminder.title} (${i + 1}/${newReminders.length})`,

            // 内容：使用 Markdown 渲染为 HTML（优先 marked/editormd），回退为换行处理
            html: htmlContent,

            // 图标：使用信息图标，表明这是一条通知性质的提醒
            icon: "info",

            // 确认按钮文字：使用友好的中文提示
            confirmButtonText: "知道了",

            // 允许用户点击弹窗外部区域来关闭弹窗
            // 这样提供了更灵活的关闭方式
            allowOutsideClick: true,

            // 允许用户按 ESC 键关闭弹窗
            // 这是用户习惯的快捷键操作
            allowEscapeKey: true,

            // 自定义样式类名，保持与单个提醒相同的外观
            // 这样确保界面风格的一致性
            customClass: {
              popup: "reminder-alert-popup", // 弹窗容器的样式类
              title: "reminder-alert-title", // 标题的样式类
              htmlContainer: "reminder-alert-content", // 内容区域的样式类
            },
          });

          // 在控制台记录已显示的提醒，便于调试和问题排查
          console.log(
            `[定时提醒] 已显示第 ${i + 1}/${newReminders.length} 条提醒: ${
              reminder.title
            }`,
          );

          // 如果不是最后一个提醒，添加一个延迟
          // 这样可以避免用户关闭一个弹窗后，下一个弹窗立即出现造成的突兀感
          if (i < newReminders.length - 1) {
            // 使用 Promise 和 setTimeout 实现异步延迟
            // 延迟时间设置为 700 毫秒（0.7 秒），既不会太快也不会太慢
            await new Promise((resolve) => setTimeout(resolve, 700));
          }
        }

        // 所有提醒显示完毕后，在控制台记录完成信息
        console.log(`[定时提醒] 所有 ${newReminders.length} 条提醒已显示完毕`);
      })();
    }

    // ==================== 核心修复逻辑结束 ====================
  } catch (error) {
    // 捕获并记录任何网络请求或 JSON 解析过程中发生的错误
    // 这样即使提醒功能出错，也不会影响应用的其他功能
    console.error("[定时提醒] 检查提醒时发生错误:", error);
  }
}
