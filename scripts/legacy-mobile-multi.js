// Legacy mobile multi-account, messages, maps, and admin settings UI extracted from main.js.
async function loadMobileMultiMessages() {
  console.log("[移动端留言板] 加载留言列表");
  const listEl = document.getElementById("mobile-multi-admin-messages-list");
  // 获取游客输入框容器
  const guestFields = document.getElementById(
    "mobile-multi-message-guest-fields",
  );

  if (!listEl) {
    console.error("[移动端留言板] 找不到留言列表容器");
    return;
  }

  // 根据当前登录状态显示/隐藏游客输入框
  if (guestFields) {
    // 使用全局变量 currentUserIsGuest 判断
    const isGuest =
      typeof currentUserIsGuest !== "undefined" ? currentUserIsGuest : true;
    guestFields.style.display = isGuest ? "block" : "none";
    if (!isGuest)
      guestFields.classList.add("hidden"); // 确保样式一致性
    else guestFields.classList.remove("hidden");
  }

  listEl.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  try {
    const response = await fetch("/api/messages/list", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (!result.success) {
      listEl.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">${result.message}</p>`;
      return;
    }

    const messages = result.messages || [];

    if (messages.length === 0) {
      listEl.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">暂无留言</p>';
      return;
    }

    const canDeleteAny = await checkAdminPermission("delete_any_messages");
    const canDeleteOwn = await checkAdminPermission("delete_own_messages");
    const currentUsername = currentAuthUsername;

    const html = messages
      .map((msg) => {
        const isOwnMessage =
          !msg.is_guest && msg.auth_username === currentUsername;
        const canDelete = canDeleteAny || (canDeleteOwn && isOwnMessage);
        const displayName =
          msg.nickname || msg.username || msg.auth_username || "匿名";
        const date = new Date(msg.timestamp * 1000);
        const dateStr = date.toLocaleString("zh-CN");
        const ipCity = msg.ip_city || "";

        let avatarUrl = msg.avatar_url || "default_avatar.png";
        if (!avatarUrl.startsWith("/api/avatar/")) {
          avatarUrl = `/api/avatar/${avatarUrl}`;
        }
        if (sessionUUID) {
          avatarUrl += avatarUrl.includes("?")
            ? `&session_id=${sessionUUID}`
            : `?session_id=${sessionUUID}`;
        }

        console.log(
          `[移动端留言板] 渲染留言 ID: ${msg.id}, 昵称: ${displayName}, IP城市: ${ipCity}, 是否游客: ${msg.is_guest}, 可删除: ${canDelete}`,
        );
        return `
        <div class="bg-gradient-to-br from-white to-slate-50 border border-slate-200 rounded-xl p-5 space-y-3 shadow-lg hover:shadow-xl transition-shadow duration-200 ease-in-out">
          <div class="flex justify-between items-start gap-4">
            <div class="flex gap-4 flex-1 min-w-0">
              <div class="flex-shrink-0 w-14 h-14 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 overflow-hidden border-2 border-slate-400 shadow-sm">
                <img src="${avatarUrl}" alt="头像" class="w-full h-full object-cover"
                  onerror="const p = this.parentElement; p.innerHTML='<span class=\\'text-3xl text-slate-500\\'>👤</span>'; p.classList.add('flex', 'items-center', 'justify-center');">
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap mb-1">
                  <span class="font-bold text-slate-800 text-base truncate">${escapeHtml(
                    displayName,
                  )}</span>
                  ${
                    msg.is_guest
                      ? '<span class="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full flex-shrink-0 font-medium">游客</span>'
                      : ""
                  }
                  ${
                    ipCity
                      ? `<span class="text-xs text-slate-600 bg-slate-100 px-2 py-1 rounded-full flex-shrink-0">📍 ${escapeHtml(
                          ipCity,
                        )}</span>`
                      : ""
                  }
                </div>
                ${
                  msg.email
                    ? `<p class="text-xs text-slate-600 truncate mb-1">${escapeHtml(
                        msg.email,
                      )}</p>`
                    : ""
                }
                <p class="text-xs text-slate-500">${dateStr}</p>
              </div>
            </div>
            
            ${
              canDelete
                ? `
              <button class="btn btn-ghost min-h-[44px] py-2 px-4 text-red-600 hover:bg-red-50 active:bg-red-100 text-sm flex-shrink-0 border border-red-300 rounded-lg shadow-sm transition-all duration-150 ease-in-out active:scale-95" 
                onclick="deleteMobileMultiMessage(${escapeInlineJsArg(msg.id)})">删除</button>
            `
                : ""
            }
          </div>
          <div class="pt-2 border-t border-slate-100">
              <div id="mobile-message-md-${
                msg.id
              }" class="text-base text-slate-800 whitespace-pre-wrap break-words leading-relaxed message-markdown"></div>
          </div>
        </div>
      `;
      })
      .join("");

    listEl.innerHTML = html;
    // 尝试将每条留言的 Markdown 转换为 HTML（移动端多账号）
    (function renderMobileMessagesMarkdown(msgs) {
      if (!msgs || !msgs.length) return;
      msgs.forEach((m) => {
        const id = `mobile-message-md-${m.id}`;
        const container = document.getElementById(id);
        if (!container) return;
        const markdownText = normalizeMarkdownText(m.content);

        if (window.editormd && typeof editormd.markdownToHTML === "function") {
          try {
            console.log(`[移动端留言板] 渲染 Markdown 留言 ID: ${m.id}`);
            editormd.markdownToHTML(id, {
              markdown: markdownText,
              htmlDecode: true,
              htmlDecode: "style,iframe,image",
              toc: false,
              tocContainer: "",
              gfm: true,
              tocDropdown: false,
              markdownSourceCode: false,
              emoji: true,
              taskList: true,
              tex: true,
              flowChart: false,
              sequenceDiagram: true,
            });
            return;
          } catch (e) {
            console.warn("移动端留言 Markdown 渲染失败，回退为纯文本显示", e);
          }
        } else {
          console.warn(
            `[移动端留言板] editormd 未加载，无法渲染 Markdown 留言 ID: ${m.id}`,
          );
        }
        container.innerHTML = escapeHtml(markdownText).replace(
          /\n/g,
          "<br>",
        );
      });
    })(messages);
  } catch (e) {
    console.error("[移动端留言板] 加载失败:", e);
    listEl.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${e.message}</p>`;
  }
}

async function submitMobileMultiMessage() {
  await ensureMobileMultiMessageEditorInitialized();
  // 1. 获取DOM元素
  const contentInput = document.getElementById("mobile-multi-message-content");
  const nicknameInput = document.getElementById(
    "mobile-multi-message-nickname",
  );
  const emailInput = document.getElementById("mobile-multi-message-email");
  const postBtn = document.getElementById("mobile-multi-post-message-btn");
  const charCount = document.getElementById("mobile-multi-message-char-count");

  if (!contentInput) return;

  // 2. 获取输入值
  const editorContent =
    mobileMultiMessageEditor &&
    typeof mobileMultiMessageEditor.getMarkdown === "function"
      ? mobileMultiMessageEditor.getMarkdown()
      : "";
  const content = (editorContent || contentInput.value || "").trim();
  const nickname = nicknameInput ? nicknameInput.value.trim() : "";
  const email = emailInput ? emailInput.value.trim() : "";

  // 3. 基础验证
  if (!content) {
    showModalAlert("请输入留言内容", "提示");
    return;
  }

  if (content.length > 1000) {
    showModalAlert("留言内容不能超过1000字", "提示");
    return;
  }

  // 4. 游客身份验证 (参照 postMessage 逻辑)
  // 使用全局变量或从 currentUserData 获取
  const isGuest =
    typeof currentUserIsGuest !== "undefined" ? currentUserIsGuest : true;

  if (isGuest) {
    if (!nickname) {
      showModalAlert("游客必须填写昵称", "提示");
      return;
    }
    if (!email) {
      showModalAlert("游客必须填写邮箱", "提示");
      return;
    }
    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!emailPattern.test(email)) {
      showModalAlert("邮箱格式不正确", "提示");
      return;
    }
  }

  // 5. 设置按钮加载状态
  if (postBtn) {
    postBtn.disabled = true;
    postBtn.textContent = "发表中...";
  }

  try {
    // 6. 发送请求
    const response = await fetch("/api/messages/post", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      // [修正] 补全 email 字段
      body: JSON.stringify({ content, nickname, email }),
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert("留言发送成功", "成功");
      // 清空输入
      contentInput.value = "";
      if (
        mobileMultiMessageEditor &&
        typeof mobileMultiMessageEditor.clear === "function"
      ) {
        mobileMultiMessageEditor.clear();
      }
      if (nicknameInput) nicknameInput.value = "";
      if (emailInput) emailInput.value = "";
      if (charCount) charCount.textContent = "0";

      // 刷新列表
      loadMobileMultiMessages();
    } else {
      showModalAlert(result.message || "发送失败", "错误");
    }
  } catch (e) {
    console.error("[移动端留言板] 发送失败:", e);
    showModalAlert("发送失败: " + e.message, "错误");
  } finally {
    // 7. 恢复按钮状态
    if (postBtn) {
      postBtn.disabled = false;
      postBtn.textContent = "发表";
    }
  }
}

async function ensureMobileMultiMessageEditorInitialized() {
  try {
    if (
      mobileMultiMessageEditor &&
      typeof mobileMultiMessageEditor.getMarkdown === "function"
    ) {
      return true;
    }
    if (typeof editormd === "undefined") return false;
    const editorEl = document.getElementById("mobile-multi-message-editor");
    if (!editorEl) return false;
    mobileMultiMessageEditor = editormd("mobile-multi-message-editor", {
          // ===== 基本配置 =====
          // 编辑器模式：
          // gfm：GitHub Flavored Markdown，与 Markdown 语法基本相同，但增加了一些扩展语法，如表格、任务列表等
          // markdown：标准 Markdown 语法
          mode: "gfm",
          // 表单元素名称，用于提交表单时标识该编辑器
          name: "mobile-multi-message-content",
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
          height: "600px",
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
          placeholder: "请输入留言（支持 Markdown）",
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
          onchange: function () {
            try {
              const md = mobileMultiMessageEditor.getMarkdown() || "";
              const ta = document.getElementById("mobile-multi-message-content");
              const count = document.getElementById(
                "mobile-multi-message-char-count",
              );
              if (ta) ta.value = md;
              if (count) count.textContent = String(md.length);
            } catch (_) {}
          },
          // 监听开始回调（开始监听模式时触发）
          onwatch: null,
          // 监听结束回调（结束监听模式时触发）
          onunwatch: null,
          // 预览中回调（正在生成预览时触发）
          onpreviewing: function () {},
          // 预览完成回调（预览生成完成后触发）
          onpreviewed: function () {},
          // 全屏回调（进入全屏模式时触发）
          onfullscreen: function () {
            document.getElementById("newbie-help-btn").style.setProperty("display", "none", "important");;
          },
          // 退出全屏回调（退出全屏模式时触发）
          onfullscreenExit: function () {
            document.getElementById("newbie-help-btn").style.removeProperty("display");;
          },
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
          /*
          toolbarIcons: function () {
            return [
              "undo",
              "redo",
              "|",
              "bold",
              "italic",
              "quote",
              "|",
              "list-ul",
              "list-ol",
              "|",
              "link",
              "image",
              "code-block",
              "|",
              "watch",
              "preview",
            ];
          },
          */
          // 工具栏标题（自定义工具栏按钮的提示文本）
          toolbarTitles: {},
          // 工具栏处理程序（自定义工具栏按钮的点击事件）
          toolbarHandlers: {},
          // 使用 HTML 标签创建工具栏图标，未使用默认 <a> 标签（自定义工具栏图标的 HTML）
          toolbarCustomIcons: {},
          // 工具栏图标文本（自定义工具栏按钮的文本）
          toolbarIconTexts: {},
          // 父容器层级（用于解决全屏模式下的定位问题）
          parentContainerLayer:"4",
          // 全屏的时候是否允许滚动
          fullScreenScrolling: true,
          // 全屏的时候编辑器位于父容器的坐标位置
          fullScreenCoordinatesX: null,
          fullScreenCoordinatesY: "0px",
          // 全屏的时候微调编辑器
          fullScreenHeightAdjustment: "-75px",
          // 进入全屏自动滚动
          fullScreenAutomaticScrolling: "0%",
          fullScreenAutomaticScrollingOuterHtml: true,
          // 锁定所有父容器
          fullScreenForceDisableAllScroll: true,
          // 弹窗打开时自动滚动位置
          dialogOpenAutoScroll: "75px",
          dialogOpenAutoScrollOuterHtml: true,
        });
    const ta = document.getElementById("mobile-multi-message-content");
    if (ta) ta.classList.add("hidden");
    return true;
  } catch (e) {
    console.warn("[移动端留言板] 初始化 Editor.md 失败，回退为 textarea", e);
    const ta = document.getElementById("mobile-multi-message-content");
    if (ta) ta.classList.remove("hidden");
    return false;
  }
}

/**
 * 删除移动端多人留言板的单条留言
 * 功能说明：
 * 1. 使用拟态风格的二次确认对话框，提升用户体验
 * 2. 确认后调用后端API删除留言
 * 3. 删除成功后刷新留言列表
 *
 * @param {string} msgId - 要删除的留言ID
 *
 * 调用时机：
 * - 用户点击移动端留言板中的"删除"按钮时
 *
 * 实现细节：
 * - 使用SweetAlert2库创建拟态风格的确认对话框
 * - 对话框包含警告图标、清晰的提示文字和两个操作按钮
 * - 只有用户点击"确认删除"按钮后才执行删除操作
 * - 提供详细的成功/失败提示
 */
async function deleteMobileMultiMessage(msgId) {
  // ========== 步骤1：显示拟态风格的二次确认对话框 ==========

  // 使用SweetAlert2创建美观的确认对话框
  // 应用拟态风格设计：柔和阴影、渐变背景、圆角边框
  const confirmResult = await Swal.fire({
    // 对话框标题：使用醒目的警告文字
    title: "⚠️ 删除确认",

    // 对话框内容：清晰说明删除操作的影响
    html: `
      <div style="text-align: left; padding: 10px;">
        <p style="font-size: 16px; color: #475569; margin-bottom: 12px;">
          您确定要删除这条留言吗？
        </p>
        <div style="
          background: linear-gradient(145deg, #fef2f2, #fee2e2);
          border-left: 4px solid #dc2626;
          padding: 12px;
          border-radius: 8px;
          margin-top: 10px;
        ">
          <p style="font-size: 14px; color: #991b1b; margin: 0;">
            <strong>⚠️ 注意：</strong>此操作不可恢复，删除后无法找回该留言的内容。
          </p>
        </div>
      </div>
    `,

    // 对话框图标：使用警告图标
    icon: "warning",

    // 显示两个按钮：取消和确认
    showCancelButton: true,

    // 确认按钮文字和样式
    confirmButtonText: "<strong>🗑️ 确认删除</strong>",
    confirmButtonColor: "#dc2626", // 红色，表示危险操作

    // 取消按钮文字和样式
    cancelButtonText: "<strong>✖️ 取消</strong>",
    cancelButtonColor: "#64748b", // 灰色，表示安全操作

    // 自定义CSS类，应用拟态风格
    customClass: {
      popup: "swal2-neumorphism-popup", // 对话框容器
      title: "swal2-neumorphism-title", // 标题
      confirmButton: "swal2-neumorphism-confirm", // 确认按钮
      cancelButton: "swal2-neumorphism-cancel", // 取消按钮
    },

    // 反向按钮顺序（取消在左，确认在右，符合用户习惯）
    reverseButtons: true,

    // 聚焦到取消按钮（防止用户误点确认）
    focusCancel: true,

    // 点击背景不关闭对话框（强制用户做出选择）
    allowOutsideClick: false,

    // 按Esc键不关闭对话框（强制用户做出选择）
    allowEscapeKey: false,
  });

  // ========== 步骤2：检查用户的选择 ==========

  // 如果用户点击了取消按钮或关闭了对话框，直接返回，不执行删除操作
  if (!confirmResult.isConfirmed) {
    console.log("[移动端留言板] 用户取消删除操作");
    return;
  }

  // ========== 步骤3：用户确认删除，执行删除操作 ==========

  console.log("[移动端留言板] 用户确认删除留言，留言ID:", msgId);

  try {
    // 调用后端API删除留言
    const response = await fetch("/api/messages/delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 使用全局会话UUID进行身份验证
      },
      body: JSON.stringify({ message_id: msgId }), // 传递留言ID
    });

    // 解析API响应
    const result = await response.json();

    // ========== 步骤4：处理API响应 ==========

    if (result.success) {
      // 删除成功
      console.log("[移动端留言板] 删除成功");

      // 显示成功提示（使用拟态风格）
      await Swal.fire({
        title: "删除成功",
        text: "该留言已被永久删除",
        icon: "success",
        confirmButtonText: "确定",
        confirmButtonColor: "#22c55e", // 绿色，表示成功
        timer: 2000, // 2秒后自动关闭
        timerProgressBar: true, // 显示进度条
        customClass: {
          popup: "swal2-neumorphism-popup",
          confirmButton: "swal2-neumorphism-confirm",
        },
      });

      // 刷新留言列表，显示最新数据
      loadMobileMultiMessages();
    } else {
      // 删除失败
      console.error("[移动端留言板] 删除失败:", result.message);

      // 显示失败提示
      await Swal.fire({
        title: "删除失败",
        text: result.message || "未知错误，请稍后重试",
        icon: "error",
        confirmButtonText: "确定",
        confirmButtonColor: "#dc2626", // 红色，表示错误
        customClass: {
          popup: "swal2-neumorphism-popup",
          confirmButton: "swal2-neumorphism-confirm",
        },
      });
    }
  } catch (e) {
    // ========== 异常处理 ==========

    // 捕获网络错误、解析错误等异常
    console.error("[移动端留言板] 删除失败:", e);

    // 显示友好的错误提示
    await Swal.fire({
      title: "删除失败",
      text: "网络错误或服务器异常: " + e.message,
      icon: "error",
      confirmButtonText: "确定",
      confirmButtonColor: "#dc2626",
      customClass: {
        popup: "swal2-neumorphism-popup",
        confirmButton: "swal2-neumorphism-confirm",
      },
    });
  }
}

// ========================================
// 【移动端多账号】创建权限组模态框
// ========================================
async function showMobileCreateGroupModal() {
  // 使用移动端专用模态框
  // [修正] 移除此处的 classList.add("show")，因为它在元素创建前执行会导致第一次点击无效

  let modal = document.getElementById("mobile-create-group-modal");
  if (!modal) {
    // 动态创建移动端权限组创建模态框
    modal = document.createElement("div");
    modal.id = "mobile-create-group-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileCreateGroupModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileCreateGroupModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileCreateGroupModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileCreateGroupModal()">
          <svg class="w-6 h-6 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
          </svg>
          <h3 class="text-xl font-bold text-sky-600 text-center">创建权限组</h3>
        </div>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">权限组标识符 (英文)</label>
            <input type="text" id="mobile-new-group-key" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="例如: vip_user">
          </div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">权限组名称</label>
            <input type="text" id="mobile-new-group-name" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="例如: VIP用户">
          </div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">权限设置</label>
            <div id="mobile-create-group-permissions" class="grid grid-cols-1 gap-1 max-h-[30vh] overflow-y-auto border border-slate-200 rounded-lg p-2"></div>
          </div>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileCreateGroupModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileCreateGroup()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">创建</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // 清空输入
  const keyInput = document.getElementById("mobile-new-group-key");
  const nameInput = document.getElementById("mobile-new-group-name");
  if (keyInput) keyInput.value = "";
  if (nameInput) nameInput.value = "";

  // 加载权限列表
  try {
    const response = await fetch("/auth/admin/list_groups", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (result.success && result.groups) {
      const firstGroup = Object.values(result.groups)[0];
      if (firstGroup && firstGroup.permissions) {
        const permissionsContainer = document.getElementById(
          "mobile-create-group-permissions",
        );
        if (permissionsContainer) {
          permissionsContainer.innerHTML = Object.keys(firstGroup.permissions)
            .map(
              (perm) => `
            <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded cursor-pointer">
              <input type="checkbox" class="w-4 h-4 rounded" data-permission="${perm}">
              <span class="text-sm text-slate-700">${translatePermission(
                perm,
              )}</span>
            </label>
          `,
            )
            .join("");
        }
      }
    }
  } catch (e) {
    console.error("[移动端创建权限组] 加载权限列表失败:", e);
  }

  // [修正] 确保元素存在后再显示，并添加 show 类触发动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileCreateGroupModal() {
  const modal = document.getElementById("mobile-create-group-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

async function submitMobileCreateGroup() {
  const keyInput = document.getElementById("mobile-new-group-key");
  const nameInput = document.getElementById("mobile-new-group-name");
  const permissionsContainer = document.getElementById(
    "mobile-create-group-permissions",
  );

  const groupKey = keyInput ? keyInput.value.trim() : "";
  const groupName = nameInput ? nameInput.value.trim() : "";

  if (!groupKey || !groupName) {
    showModalAlert("请填写权限组标识符和名称", "提示");
    return;
  }

  const permissions = {};
  if (permissionsContainer) {
    const checkboxes = permissionsContainer.querySelectorAll(
      'input[type="checkbox"]',
    );
    checkboxes.forEach((cb) => {
      const perm = cb.getAttribute("data-permission");
      permissions[perm] = cb.checked;
    });
  }

  try {
    const response = await fetch("/auth/admin/create_group", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        group_name: groupKey,
        display_name: groupName,
        permissions: permissions,
      }),
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert(`权限组 ${groupName} 创建成功`, "成功");
      closeMobileCreateGroupModal();
      loadAdminGroups().then(() => copyAdminContentToMultiPanel("groups"));
    } else {
      showModalAlert(result.message || "创建失败", "错误");
    }
  } catch (e) {
    console.error("[移动端创建权限组] 失败:", e);
    showModalAlert("创建失败: " + e.message, "错误");
  }
}

// ========================================
// 【移动端多账号】编辑权限组模态框
// ========================================
let mobileCurrentEditGroupKey = null;

async function showMobileEditGroupModal(groupKey) {
  mobileCurrentEditGroupKey = groupKey;

  let modal = document.getElementById("mobile-edit-group-modal");
  if (!modal) {
    // 修正：移除错误的 classList 调用，先创建元素
    modal = document.createElement("div");
    modal.id = "mobile-edit-group-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileEditGroupModal();
    };
    modal.innerHTML = `
        <div class="absolute inset-0 bg-black/40" onclick="closeMobileEditGroupModal()"></div>
        <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
          <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileEditGroupModal()">
            <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
          </div>
          <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileEditGroupModal()">
            <svg class="w-6 h-6 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
            </svg>
            <h3 class="text-xl font-bold text-sky-600 text-center">编辑权限组</h3>
          </div>
          <div class="text-center text-sm text-slate-600" id="mobile-edit-group-name-display"></div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">权限设置</label>
            <div id="mobile-edit-group-permissions" class="grid grid-cols-1 gap-1 max-h-[40vh] overflow-y-auto border border-slate-200 rounded-lg p-2"></div>
          </div>
          <div class="flex gap-3 pt-4 border-t border-slate-100">
            <button onclick="closeMobileEditGroupModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
            <button onclick="submitMobileEditGroup()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">保存</button>
          </div>
        </div>
      `;
    document.body.appendChild(modal);
  }

  try {
    const response = await fetch("/auth/admin/list_groups", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (!result.success || !result.groups || !result.groups[groupKey]) {
      showModalAlert("无法加载权限组信息", "错误");
      return;
    }

    const group = result.groups[groupKey];

    const nameDisplay = document.getElementById(
      "mobile-edit-group-name-display",
    );
    if (nameDisplay) {
      nameDisplay.textContent = `${group.name} (${groupKey})`;
    }

    const permissionsContainer = document.getElementById(
      "mobile-edit-group-permissions",
    );
    if (permissionsContainer && group.permissions) {
      permissionsContainer.innerHTML = Object.keys(group.permissions)
        .map(
          (perm) => `
              <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded cursor-pointer">
                <input type="checkbox" class="w-4 h-4 rounded" data-permission="${perm}" ${
                  group.permissions[perm] ? "checked" : ""
                }>
                <span class="text-sm text-slate-700">${translatePermission(
                  perm,
                )}</span>
              </label>
            `,
        )
        .join("");
    }

    // 显示模态框
    modal.classList.remove("hidden");
    // 修正：添加动画类，并增加微小延时以触发 CSS transition
    setTimeout(() => {
      modal.classList.add("show");
    }, 10);
  } catch (e) {
    console.error("[移动端编辑权限组] 加载失败:", e);
    showModalAlert("加载失败: " + e.message, "错误");
  }
}

function closeMobileEditGroupModal() {
  const modal = document.getElementById("mobile-edit-group-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
  mobileCurrentEditGroupKey = null;
}

async function submitMobileEditGroup() {
  if (!mobileCurrentEditGroupKey) return;

  const permissionsContainer = document.getElementById(
    "mobile-edit-group-permissions",
  );
  if (!permissionsContainer) return;

  const permissions = {};
  const checkboxes = permissionsContainer.querySelectorAll(
    'input[type="checkbox"]',
  );
  checkboxes.forEach((cb) => {
    const perm = cb.getAttribute("data-permission");
    permissions[perm] = cb.checked;
  });

  try {
    const response = await fetch("/auth/admin/update_group", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        group_key: mobileCurrentEditGroupKey,
        permissions: permissions,
      }),
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert(`权限组 ${mobileCurrentEditGroupKey} 已更新`, "成功");
      closeMobileEditGroupModal();
      loadAdminGroups().then(() => copyAdminContentToMultiPanel("groups"));
    } else {
      showModalAlert(result.message || "更新失败", "错误");
    }
  } catch (e) {
    console.error("[移动端编辑权限组] 更新失败:", e);
    showModalAlert("更新失败: " + e.message, "错误");
  }
}

// ========================================
// 【移动端多账号】删除权限组
// ========================================
async function deleteMobileGroup(groupKey) {
  if (!confirm(`确定要删除权限组 "${groupKey}" 吗？此操作不可撤销。`)) return;

  try {
    const response = await fetch("/auth/admin/delete_group", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ group_key: groupKey }),
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert(`权限组 ${groupKey} 已删除`, "成功");
      loadAdminGroups().then(() => copyAdminContentToMultiPanel("groups"));
    } else {
      showModalAlert(result.message || "删除失败", "错误");
    }
  } catch (e) {
    console.error("[移动端删除权限组] 失败:", e);
    showModalAlert("删除失败: " + e.message, "错误");
  }
}

function switchMobileAdminTab(tabId, prefix) {
  let tabsNavId, contentId;
  if (prefix === "mobile-multi-admin") {
    tabsNavId = "mobile-multi-admin-tabs-nav";
    contentId = "mobile-multi-admin-panel-content";
  } else if (prefix === "mobile-admin-panel-unified") {
    // 统一移动端管理面板
    tabsNavId = "mobile-multi-admin-tabs-nav-panel";
    contentId = "mobile-multi-admin-content-panel";
  } else if (prefix === "mobile-admin-panel") {
    tabsNavId = "mobile-admin-tabs-nav-panel";
    contentId = "mobile-admin-panel-content-panel";
  } else {
    tabsNavId = "mobile-admin-tabs-nav";
    contentId = "mobile-admin-panel-content";
  }
  const tabsNav = document.getElementById(tabsNavId);
  const content = document.getElementById(contentId);

  if (!tabsNav || !content) {
    console.error(
      `[移动端管理面板] 找不到容器元素: tabsNavId=${tabsNavId}, contentId=${contentId}`,
    );
    return;
  }
  Array.from(tabsNav.children).forEach((button) => {
    const buttonText = button.textContent.trim();
    // ========================================
    // 标签文本到ID的映射表
    // 用于将按钮上的中文标签文本转换为对应的标签ID
    // 这样可以根据按钮文本准确识别当前应该高亮哪个标签
    // ========================================
    const tabMap = {
      用户: "users", // 用户管理标签
      权限组: "groups", // 权限组管理标签
      日志: "logs", // 日志查看标签
      状态: "health", // 系统状态标签
      资料: "profile", // 个人信息标签
      会话: "sessions", // 会话管理标签
      留言: "messages", // 留言板标签
      IP封禁: "ipban", // IP封禁管理标签
      短信: "sms", // 短信配置标签
      配置: "config", // 系统配置标签
      验证码: "captcha", // 验证码管理标签
      提醒: "reminders", // 定时提醒标签
      HTTPS: "ssl", // HTTPS设置标签
      支付配置: "payment-config", // 支付配置标签映射
      支付历史: "payment-logs", // 支付历史标签映射
      支付设置: "payment-settings", // 支付设置标签映射
      价格设置: "pricing", // 价格设置标签映射
      欠费查询: "billing", // 欠费查询标签映射（复用账单面板）
      CDN: "cdn", // CDN缓存管理标签
      密码恢复: "bruteforce", // 密码恢复标签
      水印控制: "watermark", // 水印控制标签映射
      账单: "billing", // 账单管理标签映射
      账单日志: "billing-logs", // 账单日志标签映射
      账号恢复: "restore-account", // 账号恢复标签映射
    };
    const buttonTabId = tabMap[buttonText];
    if (buttonTabId === tabId) {
      button.className =
        "px-4 py-2 font-semibold text-xs whitespace-nowrap rounded-lg transition text-sky-600 bg-sky-50 border-b-2 border-sky-600";
    } else {
      button.className =
        "px-4 py-2 font-semibold text-xs whitespace-nowrap rounded-lg transition text-slate-400 hover:text-slate-600 hover:bg-slate-50";
    }
  });
  if (prefix === "mobile-admin-panel") {
    const allPanels = [
      "mobile-admin-users-panel-panel",
      "mobile-admin-groups-panel-panel",
      "mobile-admin-logs-panel-panel",
      "mobile-admin-health-panel-panel",
      "mobile-admin-profile-panel-panel",
      "mobile-admin-sessions-panel-panel",
      "mobile-admin-messages-panel-panel",
      "mobile-admin-ipban-panel-panel",
      "mobile-admin-sms-panel-panel",
      "mobile-admin-config-panel-panel",
      "mobile-admin-captcha-panel-panel",
      "mobile-admin-reminders-panel-panel",
      "mobile-admin-ssl-panel-panel",
    ];

    allPanels.forEach((panelId) => {
      const panel = document.getElementById(panelId);
      if (panel) panel.classList.add("hidden");
    });
    const captchaHistoryPanelMobile = document.getElementById(
      "admin-captcha-history-panel_modal",
    );
    if (captchaHistoryPanelMobile)
      captchaHistoryPanelMobile.classList.add("hidden");
    const targetPanelId = `mobile-admin-${tabId}-panel-panel`;
    const targetPanel = document.getElementById(targetPanelId);
    if (targetPanel) {
      targetPanel.classList.remove("hidden");
    } else {
      console.warn(`[移动端管理面板] 找不到目标面板: ${targetPanelId}`);
    }
    switch (tabId) {
      case "users":
        loadAdminUsers();
        setTimeout(() => copyAdminContentToPanelVersion("users"), 500);
        break;
      case "groups":
        loadAdminGroups();
        setTimeout(() => copyAdminContentToPanelVersion("groups"), 500);
        break;
      case "logs":
        loadAdminLogs(1);
        setTimeout(() => copyAdminContentToPanelVersion("logs"), 500);
        break;
      case "health":
        loadHealthStatus().finally(() =>
          copyAdminContentToPanelVersion("health"),
        );
        break;
      case "profile":
        loadPersonalInfo();
        setTimeout(() => copyAdminContentToPanelVersion("profile"), 500);
        break;
      case "sessions":
        // 移动端会话管理：调用专用函数，不再从PC端复制
        // loadAdminSessions();
        // setTimeout(() => copyAdminContentToPanelVersion("sessions"), 500);

        // 【修正】单账号面板：检查上帝模式权限
        checkAdminPermission("god_mode").then((hasPermission) => {
          const singleGodToggle = document.getElementById(
            "mobile-god-mode-toggle-panel",
          );
          if (singleGodToggle) {
            singleGodToggle.style.display = hasPermission ? "flex" : "none";
          }
        });

        loadMobileAdminSessionsList();
        break;
      case "messages":
        loadMessages();
        setTimeout(() => copyAdminContentToPanelVersion("messages"), 600);

        break;
      case "ipban":
        loadIPBans();
        setTimeout(() => copyAdminContentToPanelVersion("ipban"), 500);
        break;
      case "sms":
        loadSMSConfig();
        setTimeout(() => copyAdminContentToPanelVersion("sms"), 500);
        break;
      case "config":
        loadSystemConfig();
        setTimeout(() => copyAdminContentToPanelVersion("config"), 500);
        break;
      case "captcha":
        loadCaptchaSettings();
        const dateInput = $("captcha-history-date");
        if (dateInput) {
          const today = new Date().toISOString().split("T")[0];
          dateInput.value = today;
        }
        loadCaptchaHistory();
        setTimeout(() => copyAdminContentToPanelVersion("captcha"), 500);
        break;
      case "reminders":
        loadReminders();
        setTimeout(() => copyAdminContentToPanelVersion("reminders"), 500);
        break;
      case "ssl":
        loadSSLInfo();
        setTimeout(() => copyAdminContentToPanelVersion("ssl"), 500);
        break;
    }
    return;
  }

  // ========================================
  // 处理 mobile-admin-panel-unified 前缀
  // 这个前缀用于多账号模式下的统一管理面板
  // 面板ID命名规则：mobile-multi-admin-{tabId}-panel
  // 内容列表ID命名规则：mobile-multi-admin-{tabId}-list
  // ========================================
  if (prefix === "mobile-admin-panel-unified") {
    // 定义所有管理面板的ID列表
    // 这些面板会根据用户选择的标签页进行显示/隐藏切换
    const allMultiPanels = [
      "mobile-multi-admin-users-panel", // 用户管理面板
      "mobile-multi-admin-groups-panel", // 权限组管理面板
      "mobile-multi-admin-logs-panel", // 日志查看面板
      "mobile-multi-admin-health-panel", // 系统状态面板
      "mobile-multi-admin-profile-panel", // 个人信息面板
      "mobile-multi-admin-sessions-panel", // 会话管理面板
      "mobile-multi-admin-messages-panel", // 留言板面板
      "mobile-multi-admin-ipban-panel", // IP封禁面板
      "mobile-multi-admin-sms-panel", // 短信配置面板
      "mobile-multi-admin-config-panel", // 系统配置面板
      "mobile-multi-admin-captcha-panel", // 验证码管理面板
      "mobile-multi-admin-reminders-panel", // 定时提醒面板
      "mobile-multi-admin-ssl-panel", // HTTPS设置面板
      "mobile-multi-admin-payment-config-panel", // 支付配置面板（旧版，已弃用）
      "mobile-multi-admin-payment-logs-panel", // 支付历史面板
      "mobile-multi-admin-payment-settings-panel", // 支付设置面板
      "mobile-multi-admin-pricing-panel", // 价格设置面板
      "mobile-multi-admin-cdn-panel", // CDN缓存管理面板
      "mobile-multi-admin-bruteforce-panel", // 密码恢复面板
      "mobile-multi-admin-watermark-panel", // 水印控制面板
      "mobile-multi-admin-billing-panel", // 账单面板
      "mobile-multi-admin-billing-logs-panel", // 账单日志面板
      "mobile-multi-admin-restore-account-panel", // 账号恢复面板
    ];

    // 先隐藏所有面板，准备切换到目标面板
    allMultiPanels.forEach((panelId) => {
      const panel = document.getElementById(panelId);
      if (panel) panel.classList.add("hidden");
    });

    // 构建目标面板的ID并显示
    const targetMultiPanelId = `mobile-multi-admin-${tabId}-panel`;
    const targetMultiPanel = document.getElementById(targetMultiPanelId);
    if (targetMultiPanel) {
      // 移除hidden类以显示目标面板
      targetMultiPanel.classList.remove("hidden");
    } else {
      // 如果找不到目标面板，输出警告日志便于调试
      console.warn(
        `[移动端多账号管理面板] 找不到目标面板: ${targetMultiPanelId}`,
      );
    }

    // 根据选中的标签页加载对应的数据
    // 并使用copyAdminContentToMultiPanel函数将PC端内容复制到移动端
    // 根据选中的标签页加载对应的数据
    // 并使用copyAdminContentToMultiPanel函数将PC端内容复制到移动端
    switch (tabId) {
      case "users":
        // 加载用户列表数据，使用 .then 确保加载完成后再复制
        loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"));
        break;
      case "groups":
        // 加载权限组列表数据
        loadAdminGroups().then(() => copyAdminContentToMultiPanel("groups"));
        break;
      case "logs":
        // 【修改】使用移动端专用日志加载函数
        loadMobileMultiAdminLogs(1);
        break;
      case "health":
        // 【修改】使用移动端专用健康状态加载函数
        loadMobileMultiHealthStatus();
        // 检查是否需要启动自动刷新
        const healthToggle = document.getElementById(
          "mobile-multi-health-auto-refresh-toggle",
        );
        if (healthToggle && healthToggle.checked) {
          startMobileMultiHealthAutoRefresh();
        }
        break;
      case "profile":
        // 【修改】使用移动端专用个人信息加载函数
        loadMobileUnifiedProfile().then(() => loadMobileUserBillingList());
        break;
      case "billing":
        loadMobileMultiAdminBillingList();
        break;
      case "billing-logs":
        loadMobileBillingLogs(1);
        break;
      case "restore-account":
        loadMobileMultiRemovedAccountsList();
        break;
      case "sessions":
        // 【修正】检查上帝模式权限并控制开关显示
        checkAdminPermission("god_mode").then((hasPermission) => {
          const godToggle = document.getElementById(
            "mobile-multi-god-mode-toggle",
          );
          if (godToggle) {
            godToggle.style.display = hasPermission ? "flex" : "none";
          }
        });

        loadMobileAdminSessionsList();
        break;
      case "messages":
        // 【修改】使用移动端专用留言板加载函数
        loadMobileMultiMessages();
        ensureMobileMultiMessageEditorInitialized();
        break;
      case "ipban":
        // 加载IP封禁规则列表（使用移动端专用函数）
        mobileRefreshIPBanList();
        break;
      case "sms":
        // 加载短信服务配置（使用移动端专用函数自动读取配置）
        mobileLoadSMSConfig();
        break;
      case "config":
        // 加载系统配置
        loadSystemConfig().then(() => copyAdminContentToMultiPanel("config"));
        break;
      case "captcha":
        // 加载验证码设置（使用移动端专用函数）
        mobileLoadCaptchaSettings(false);
        break;
      case "reminders":
        // 加载定时提醒列表（使用移动端专用函数）
        mobileRefreshReminders();
        break;
      case "ssl":
        // 加载SSL/HTTPS配置信息
        loadSSLInfo().then(() => copyAdminContentToMultiPanel("ssl"));
        break;
      // ========================================
      // 支付配置面板加载逻辑
      // 当管理员切换到"支付配置"标签时，调用loadPaymentConfig函数
      // 该函数会从后端加载当前启用的支付方式并更新复选框状态
      // ========================================
      case "payment-config":
        // 加载支付配置
        loadPaymentConfig();
        break;
      // ========================================
      // 支付日志面板加载逻辑
      // 当管理员切换到"支付日志"标签时，调用loadPaymentLogs函数
      // 默认加载第1页的日志数据
      // ========================================
      case "payment-logs":
        // 加载支付日志（第1页）
        loadPaymentLogs(1);
        break;
      // 添加CDN加载逻辑
      case "cdn":
        loadCDNConfig(); // 该函数已适配移动端ID (mobile-cdn-*)
        break;
      // 添加密码恢复加载逻辑
      case "bruteforce":
        loadBruteforceStatus();
        break;
      // ========================================
      // 欠费查询面板加载逻辑
      // 当管理员切换到"欠费查询"标签时，自动调用loadOverdueAccounts函数
      // 该函数会从后端加载所有有欠费记录的学校账号，按欠费次数排序
      // ========================================
      case "overdue":
        // 自动触发加载欠费账号列表
        loadOverdueAccounts();
        break;
      // ========================================
      // 支付设置面板加载逻辑
      // 当管理员切换到"支付设置"标签时，需要初始化支付设置面板
      // 该面板包含4个子标签：支付方式配置、订单查询、退款处理、支付测试
      // 默认显示"支付方式配置"子标签
      // ========================================
      case "payment-settings":
        // 切换到支付设置面板的默认子标签（支付方式配置）
        // 该函数会自动调用loadPaymentConfig()加载支付方式配置
        switchPaymentSettingsTab("config");
        break;
      // ========================================
      // 价格设置面板加载逻辑
      // 当管理员切换到"价格设置"标签时，调用loadMobilePricingConfig函数
      // 该函数会从后端加载价格策略配置，包括：
      // - 是否启用付费模式（require_payment）
      // - 单次请求费用（price_per_request）
      // - 新用户免费次数（free_requests_for_new_users）
      // ========================================
      case "pricing":
        // 加载价格配置数据并填充到表单
        loadMobilePricingConfig();
        break;
      // ========================================
      // 水印控制面板加载逻辑
      // 当管理员切换到"水印控制"标签时，调用loadMobileWatermarkControlConfig函数
      // 该函数会从后端加载水印控制配置，包括：
      // - 系统默认值（default）：未配置用户使用的默认权限
      // - 用户个性化配置（users）：每个用户的自定义权限设置
      // ========================================
      case "watermark":
        // 加载移动端水印控制配置数据并填充到表单
        loadMobileWatermarkControlConfig();
        break;
    }
    // 处理完成后直接返回，不执行后续的通用处理逻辑
    return;
  }

  content.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-sm">加载中...</p>';
  switch (tabId) {
    case "users":
      loadAdminUsers();
      setTimeout(() => copyAdminContentToMobile("users", contentId), 500);
      break;
    case "groups":
      loadAdminGroups();
      setTimeout(() => copyAdminContentToMobile("groups", contentId), 500);
      break;
    case "logs":
      loadAdminLogs(1);
      setTimeout(() => copyAdminContentToMobile("logs", contentId), 500);
      break;
    case "health":
      loadHealthStatus().finally(() =>
        copyAdminContentToMobile("health", contentId),
      );
      break;
    case "profile":
      loadPersonalInfo();
      setTimeout(() => copyAdminContentToMobile("profile", contentId), 500);
      break;
    case "sessions":
      loadAdminSessions();
      setTimeout(() => copyAdminContentToMobile("sessions", contentId), 500);
      break;
    case "messages":
      loadMessages();
      setTimeout(() => copyAdminContentToMobile("messages", contentId), 600);
      break;
    case "ipban":
      loadIPBans();
      setTimeout(() => copyAdminContentToMobile("ipban", contentId), 500);
      break;
    case "sms":
      loadSMSConfig();
      setTimeout(() => copyAdminContentToMobile("sms", contentId), 500);
      break;
    case "config":
      loadSystemConfig();
      setTimeout(() => copyAdminContentToMobile("config", contentId), 500);
      break;
    case "captcha":
      loadCaptchaSettings();
      const dateInputEl = $("captcha-history-date");
      if (dateInputEl) {
        dateInputEl.value = new Date().toISOString().split("T")[0];
      }
      loadCaptchaHistory();

      setTimeout(() => copyAdminContentToMobile("captcha", contentId), 500);
      break;
    case "reminders":
      // 多账号移动端使用专用提醒列表渲染，避免被PC内容复制覆盖
      if (prefix === "mobile-multi-admin") {
        mobileRefreshReminders();
      } else {
        loadReminders();
        setTimeout(() => copyAdminContentToMobile("reminders", contentId), 500);
      }
      break;
    case "ssl":
      loadSSLInfo();
      setTimeout(() => copyAdminContentToMobile("ssl", contentId), 500);
      break;
    // ========================================
    // 支付设置面板加载逻辑（移动端）
    // 当管理员切换到"支付设置"标签时，显示支付设置面板
    // 移动端的支付设置面板已经存在（mobile-multi-admin-payment-settings-panel）
    // 包含：支付方式配置、订单查询、退款处理、测试支付等功能
    // ========================================
    case "payment-settings":
      // 移动端支付设置面板已经在HTML中定义，无需额外加载
      // 面板ID: mobile-multi-admin-payment-settings-panel
      // 默认显示第一个Tab（支付方式配置）
      content.innerHTML =
        '<p class="text-green-600 text-center py-10 text-sm">✓ 支付设置面板已加载</p>';
      break;
    // ========================================
    // 价格设置面板加载逻辑（移动端）
    // 当管理员切换到"价格设置"标签时，加载价格配置
    // 移动端的价格设置面板已经存在（mobile-multi-admin-pricing-panel）
    // 包含：是否需要付费、单次费用、默认免费次数等配置项
    // ========================================
    case "pricing":
      // 调用移动端专用的价格配置加载函数
      // 该函数会从后端API加载价格配置并填充到移动端输入框
      loadMobilePricingConfig();
      break;
    default:
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-sm">未知的标签页</p>';
  }
}
function copyAdminContentToMobile(tabType, mobileContentId) {
  const pcContainerMap = {
    users: "admin-users-panel_modal",
    groups: "admin-groups-panel_modal",
    logs: "admin-logs-panel_modal",
    health: "admin-health-panel_modal",
    profile: "admin-profile-panel_modal",
    sessions: "admin-sessions-panel_modal",
    messages: "admin-messages-panel_modal",
    ipban: "admin-ip-ban-modal",
    sms: "admin-sms-config-modal",
    config: "admin-config-panel_modal",
    captcha: "admin-captcha-panel_modal",
    reminders: "admin-reminders-panel_modal",
    ssl: "admin-ssl-panel_modal",
  };
  const pcContainerId = pcContainerMap[tabType];
  const pcContainer = document.getElementById(pcContainerId);
  const mobileContainer = document.getElementById(mobileContentId);

  if (!pcContainer || !mobileContainer) {
    console.error(
      `[移动端管理面板] 找不到容器: PC=${pcContainerId}, Mobile=${mobileContentId}`,
    );
    mobileContainer.innerHTML =
      '<p class="text-red-500 text-center py-10 text-sm">加载失败</p>';
    return;
  }
  const scrollSnapshot =
    tabType === "health"
      ? captureHealthScrollPositions(mobileContainer)
      : null;
  mobileContainer.innerHTML = pcContainer.innerHTML;
  if (tabType === "config") copyMapConfigEditorState(pcContainer, mobileContainer);
  mobileContainer.querySelectorAll("button").forEach((btn) => {
    btn.classList.add("!text-xs", "!py-1", "!px-2");
  });
  mobileContainer.querySelectorAll("h4, h5").forEach((heading) => {
    heading.classList.add("!text-sm");
  });
  restoreHealthScrollPositions(scrollSnapshot);
}
function copyAdminContentToPanelVersion(tabType) {
  const pcToMobileMap = {
    // users: {
    //   pc: "admin-users-list_modal",
    //   mobile: "mobile-admin-users-list-panel",
    // },
    groups: {
      pc: "admin-groups-list_modal",
      mobile: "mobile-admin-groups-list-panel",
    },
    logs: {
      pc: "admin-logs-content_modal",
      mobile: "mobile-admin-logs-content-panel",
    },
    health: {
      pc: "admin-health-content_modal",
      mobile: "mobile-admin-health-content-panel",
    },
    profile: {
      pc: "admin-profile-content_modal",
      mobile: "mobile-admin-profile-content-panel",
    },
    sessions: {
      pc: "admin-sessions-list_modal",
      mobile: "mobile-admin-sessions-list-panel",
    },
    messages: {
      pc: "admin-messages-list_modal",
      mobile: "mobile-admin-messages-list-panel",
    },
    ipban: { pc: "ip-ban-list", mobile: "mobile-ip-ban-list-panel" },
    sms: {
      pc: "admin-sms-config-modal",
      mobile: "mobile-admin-sms-content-panel",
    },
    config: {
      pc: "admin-config-panel_modal",
      mobile: "mobile-admin-config-content-panel",
    },
    captcha: {
      pc: "admin-captcha-list_modal",
      mobile: "mobile-admin-captcha-list-panel",
    },
    reminders: {
      pc: "admin-reminders-panel_modal",
      mobile: "mobile-admin-reminders-content-panel",
    },
    ssl: {
      pc: "admin-ssl-panel_modal",
      mobile: "mobile-admin-ssl-content-panel",
    },
  };
  const mapping = pcToMobileMap[tabType];
  if (!mapping) {
    logMessage_Error(`[移动端管理面板] 未定义的标签页类型: ${tabType}`);
    return;
  }
  const pcContainer = document.getElementById(mapping.pc);
  const mobileContainer = document.getElementById(mapping.mobile);

  if (!pcContainer || !mobileContainer) {
    logMessage_Error(
      `[移动端管理面板] 找不到容器: PC=${mapping.pc}, Mobile=${mapping.mobile}`,
    );
    if (mobileContainer) {
      mobileContainer.innerHTML =
        '<p class="text-red-500 text-center py-10 text-xs">加载失败</p>';
    }
    return;
  }
  const scrollSnapshot =
    tabType === "health"
      ? captureHealthScrollPositions(mobileContainer)
      : null;
  mobileContainer.innerHTML = pcContainer.innerHTML;
  if (tabType === "config") copyMapConfigEditorState(pcContainer, mobileContainer);
  mobileContainer.querySelectorAll("button").forEach((btn) => {
    btn.classList.add("!text-xs", "!py-1", "!px-2");
  });
  mobileContainer.querySelectorAll("h4, h5").forEach((heading) => {
    heading.classList.add("!text-xs");
  });
  mobileContainer
    .querySelectorAll("input, select, textarea")
    .forEach((input) => {
      input.classList.add("!text-xs");
    });
  restoreHealthScrollPositions(scrollSnapshot);
}
// ========================================
// 将PC端管理面板内容复制到多账号移动端面板
// 用于mobile-multi-admin-panel前缀的面板
// 面板ID命名规则：mobile-multi-admin-{tabId}-panel
// 内容列表ID命名规则：mobile-multi-admin-{tabId}-list
// ========================================
function copyAdminContentToMultiPanel(tabType) {
  // 定义PC端容器ID与多账号移动端容器ID的映射关系
  // pc: PC端管理面板中对应内容区域的元素ID
  // mobile: 多账号移动端管理面板中对应内容区域的元素ID
  const pcToMultiMobileMap = {
    users: {
      pc: "admin-users-list_modal", // PC端用户列表
      mobile: "mobile-multi-admin-users-list", // 多账号移动端用户列表
    },
    groups: {
      pc: "admin-groups-list_modal", // PC端权限组列表
      mobile: "mobile-multi-admin-groups-list", // 多账号移动端权限组列表
    },
    logs: {
      pc: "admin-logs-content_modal", // PC端日志内容
      mobile: "mobile-multi-admin-logs-content", // 多账号移动端日志内容
    },
    health: {
      pc: "admin-health-content_modal", // PC端系统状态内容
      mobile: "mobile-multi-admin-health-content", // 多账号移动端系统状态
    },
    profile: {
      pc: "admin-profile-content_modal", // PC端个人信息内容
      mobile: "mobile-multi-admin-profile-content", // 多账号移动端个人信息
    },
    billing: {
      pc: "admin-billing-list-container",
      mobile: "mobile-multi-admin-billing-list",
    },
    "restore-account": {
      pc: "removed-accounts-list-container",
      mobile: "mobile-multi-removed-accounts-list",
    },
    sessions: {
      pc: "admin-sessions-list_modal", // PC端会话列表
      mobile: "mobile-multi-admin-sessions-list", // 多账号移动端会话列表
    },
    messages: {
      pc: "admin-messages-list_modal", // PC端留言列表
      mobile: "mobile-multi-admin-messages-list", // 多账号移动端留言列表
    },
    ipban: {
      pc: "ip-ban-list", // PC端IP封禁列表
      mobile: "mobile-multi-ip-ban-list", // 多账号移动端IP封禁列表
    },
    sms: {
      pc: "admin-sms-config-modal", // PC端短信配置
      mobile: "mobile-multi-admin-sms-content", // 多账号移动端短信配置
    },
    config: {
      pc: "admin-config-panel_modal", // PC端系统配置
      mobile: "mobile-multi-admin-config-content", // 多账号移动端系统配置
    },
    captcha: {
      pc: "admin-captcha-list_modal", // PC端验证码列表
      mobile: "mobile-multi-admin-captcha-list", // 多账号移动端验证码列表
    },
    reminders: {
      pc: "admin-reminders-panel_modal", // PC端定时提醒
      mobile: "mobile-multi-admin-reminders-content", // 多账号移动端定时提醒
    },
    ssl: {
      pc: "admin-ssl-panel_modal", // PC端SSL配置
      mobile: "mobile-multi-admin-ssl-content", // 多账号移动端SSL配置
    },
  };

  // 获取当前标签页类型对应的映射配置
  const mapping = pcToMultiMobileMap[tabType];
  if (!mapping) {
    // 如果没有找到映射配置，输出错误日志
    logMessage_Error(`[多账号移动端管理面板] 未定义的标签页类型: ${tabType}`);
    return;
  }

  // 获取PC端和移动端的DOM容器元素
  const pcContainer = document.getElementById(mapping.pc);
  const mobileContainer = document.getElementById(mapping.mobile);

  // 检查容器元素是否存在
  if (!pcContainer || !mobileContainer) {
    // 输出错误日志，便于调试
    logMessage_Error(
      `[多账号移动端管理面板] 找不到容器: PC=${mapping.pc}, Mobile=${mapping.mobile}`,
    );
    // 如果移动端容器存在但PC端不存在，显示加载失败提示
    if (mobileContainer) {
      mobileContainer.innerHTML =
        '<p class="text-red-500 text-center py-10 text-xs">加载失败</p>';
    }
    return;
  }

  withMobileAdminUnifiedScrollGuard(tabType, () => {
    // 将PC端内容复制到移动端容器
    mobileContainer.innerHTML = pcContainer.innerHTML;
    if (tabType === "config") copyMapConfigEditorState(pcContainer, mobileContainer);
  }, { restoreMode: "replace" });

  syncMobileAdminUnifiedPanelScroll(tabType, { restoreMode: "replace" });

  // 【账单列表】移动端显示优化：缩小表格字号并强化横向滚动体验
  if (tabType === "billing") {
    mobileContainer.querySelectorAll(".overflow-x-auto").forEach((el) => {
      el.classList.add("pb-1", "[-webkit-overflow-scrolling:touch]");
    });
    mobileContainer.querySelectorAll("table").forEach((tb) => {
      tb.classList.add("text-[11px]");
    });
    mobileContainer.querySelectorAll("th, td").forEach((cell) => {
      cell.classList.add("!px-1.5", "!py-1.5");
    });
    mobileContainer.querySelectorAll("td div").forEach((box) => {
      if (
        box.classList.contains("flex") &&
        box.classList.contains("items-center") &&
        box.classList.contains("justify-center")
      ) {
        box.classList.remove("justify-center");
        box.classList.add("justify-start", "flex-wrap");
      }
    });
  }

  // 【账单列表】移动端显示优化：缩小表格字号并强化横向滚动体验
  if (tabType === "billing") {
    mobileContainer.querySelectorAll(".overflow-x-auto").forEach((el) => {
      el.classList.add("pb-1", "[-webkit-overflow-scrolling:touch]");
    });
    mobileContainer.querySelectorAll("table").forEach((tb) => {
      tb.classList.add("text-[11px]");
    });
    mobileContainer.querySelectorAll("th, td").forEach((cell) => {
      cell.classList.add("!px-1.5", "!py-1.5");
    });
    mobileContainer.querySelectorAll("td div").forEach((box) => {
      if (
        box.classList.contains("flex") &&
        box.classList.contains("items-center") &&
        box.classList.contains("justify-center")
      ) {
        box.classList.remove("justify-center");
        box.classList.add("justify-start", "flex-wrap");
      }
    });
  }

  // 【特殊处理】使用DOM API直接修改按钮的onclick属性，避免正则表达式匹配失败

  // 【用户列表】替换用户管理按钮为移动端专用函数
  if (tabType === "users") {
    mobileContainer.querySelectorAll(".phone-location-badge[data-phone]").forEach(async (span) => {
      const info = await fetchPhoneInfo(span.dataset.phone);
      span.innerHTML = _phoneInfoBadge(info);
    });
    mobileContainer.querySelectorAll("button").forEach((btn) => {
      const onclickAttr = btn.getAttribute("onclick");
      if (!onclickAttr) return;

      // 账户密码查看
      let match = onclickAttr.match(
        /showUserSchoolAccounts\(['"]([^'"]+)['"]\)/,
      );
      if (match) {
        btn.setAttribute(
          "onclick",
          `showMobileUserSchoolAccounts('${match[1]}')`,
        );
        return;
      }

      // 查看日志
      match = onclickAttr.match(/showUserLogs\(['"]([^'"]+)['"]\)/);
      if (match) {
        btn.setAttribute("onclick", `showMobileUserLogs('${match[1]}')`);
        return;
      }

      // 会话管理
      match = onclickAttr.match(
        /setUserMaxSessions\(['"]([^'"]+)['"],\s*(-?\d+)\)/,
      );
      if (match) {
        btn.setAttribute(
          "onclick",
          `showMobileUserSessions('${match[1]}', ${match[2]})`,
        );
        return;
      }

      // 权限设置
      match = onclickAttr.match(/manageUserPermissions\(['"]([^'"]+)['"]\)/);
      if (match) {
        btn.setAttribute("onclick", `showMobileUserPermissions('${match[1]}')`);
        return;
      }

      // 修改昵称
      match = onclickAttr.match(
        /modifyUserNickname\(['"]([^'"]+)['"],\s*['"]([^'"]*)['"]\)/,
      );
      if (match) {
        btn.setAttribute(
          "onclick",
          `showMobileModifyNickname('${match[1]}', '${match[2]}')`,
        );
        return;
      }

      // 修改手机
      match = onclickAttr.match(
        /modifyUserPhone\(['"]([^'"]+)['"],\s*['"]([^'"]*)['"]\)/,
      );
      if (match) {
        btn.setAttribute(
          "onclick",
          `showMobileAdminModifyPhone('${match[1]}', '${match[2]}')`,
        );
        return;
      }

      // 重置密码
      match = onclickAttr.match(/resetUserPassword\(['"]([^'"]+)['"]\)/);
      if (match) {
        btn.setAttribute("onclick", `showMobileResetPassword('${match[1]}')`);
        return;
      }
    });
  }

  // 【权限组列表】替换PC端按钮事件为移动端专用函数
  if (tabType === "groups") {
    // 1. 处理列表项中的编辑/删除按钮
    mobileContainer.querySelectorAll("button").forEach((btn) => {
      const onclickAttr = btn.getAttribute("onclick");
      if (!onclickAttr) return;

      // 编辑权限组
      let match = onclickAttr.match(/editGroupPermissions\(['"]([^'"]+)['"]\)/);
      if (match) {
        btn.setAttribute("onclick", `showMobileEditGroupModal('${match[1]}')`);
        return;
      }

      // 删除权限组
      match = onclickAttr.match(/deleteGroup\(['"]([^'"]+)['"]\)/);
      if (match) {
        btn.setAttribute("onclick", `deleteMobileGroup('${match[1]}')`);
        return;
      }
    });

    // 2. 【修复】手动查找并绑定 "新增权限组" 和 "刷新" 按钮
    // 这些按钮从PC端复制过来后失去了事件监听器，需要重新绑定
    const createGroupBtn = mobileContainer.querySelector(
      '[id="admin-create-group_modal"]',
    );
    if (createGroupBtn) {
      // 移除可能存在的旧ID避免冲突（可选），并绑定移动端新增函数
      createGroupBtn.setAttribute("onclick", "showMobileCreateGroupModal()");
    }

    const refreshGroupBtn = mobileContainer.querySelector(
      '[id="admin-refresh-groups_modal"]',
    );
    if (refreshGroupBtn) {
      // 绑定刷新逻辑：加载数据 -> 再次同步到移动端
      refreshGroupBtn.setAttribute(
        "onclick",
        "loadAdminGroups().then(() => copyAdminContentToMultiPanel('groups'))",
      );
    }
  }

  // 【个人信息面板】替换头像上传和手机号修改按钮
  if (tabType === "profile") {
    mobileContainer.querySelectorAll("button").forEach((btn) => {
      const onclickAttr = btn.getAttribute("onclick");
      if (!onclickAttr) return;

      // 上传头像
      if (onclickAttr.includes("avatar-upload")) {
        btn.setAttribute("onclick", "triggerMobileAvatarUpload()");
        return;
      }

      // 修改手机号
      if (onclickAttr.includes("openModifyPhoneModal")) {
        btn.setAttribute("onclick", "showMobileModifyPhoneModal()");
        return;
      }
    });
  }

  if (tabType === "billing" || tabType === "restore-account") {
    mobileContainer.querySelectorAll("button").forEach((btn) => {
      const onclickAttr = btn.getAttribute("onclick");
      if (!onclickAttr) return;
      if (
        tabType === "restore-account" &&
        onclickAttr.includes("restoreAccount(")
      ) {
        btn.setAttribute(
          "onclick",
          onclickAttr.replace(
            "restoreAccount(",
            "restoreAccountAndRefreshMobile(",
          ),
        );
      }
    });
  }

  // 调整按钮样式以适应移动端显示
  // 添加更小的字体、更紧凑的内边距
  mobileContainer.querySelectorAll("button").forEach((btn) => {
    btn.classList.add("!text-xs", "!py-1", "!px-2");
  });

  // 调整标题样式，使用更小的字体
  mobileContainer.querySelectorAll("h4, h5").forEach((heading) => {
    heading.classList.add("!text-xs");
  });

  // 调整表单元素样式，使用更小的字体
  mobileContainer
    .querySelectorAll("input, select, textarea")
    .forEach((input) => {
      input.classList.add("!text-xs");
    });
}

// ========================================
// 【移动端】头像上传触发函数
// ========================================
function triggerMobileAvatarUpload() {
  let fileInput = document.getElementById("mobile-avatar-upload-input");
  if (!fileInput) {
    // 创建隐藏的文件输入
    fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.id = "mobile-avatar-upload-input";
    fileInput.accept = "image/*";
    fileInput.style.display = "none";
    fileInput.onchange = function (e) {
      const file = e.target.files[0];
      if (file) {
        handleMobileAvatarFile(file);
      }
    };
    document.body.appendChild(fileInput);
  }
  fileInput.click();
}

async function handleMobileAvatarFile(file) {
  if (!file.type.startsWith("image/")) {
    showModalAlert("请选择图片文件", "错误");
    return;
  }

  // 显示移动端头像裁剪模态框
  showMobileAvatarCropModal(file);
}

function showMobileAvatarCropModal(file) {
  let modal = document.getElementById("mobile-avatar-crop-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-avatar-crop-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileAvatarCropModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/80" onclick="closeMobileAvatarCropModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileAvatarCropModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <h3 class="text-xl font-bold text-sky-600 text-center">裁剪头像</h3>
        <div class="max-h-80 overflow-hidden bg-slate-100 rounded-lg">
          <img id="mobile-crop-image" src="" alt="待裁剪图片" style="max-width: 100%">
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileAvatarCropModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="confirmMobileAvatarCrop()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">确认上传</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  const reader = new FileReader();
  reader.onload = function (e) {
    const cropImage = document.getElementById("mobile-crop-image");
    if (cropImage) {
      cropImage.src = e.target.result;

      // 销毁旧的 cropper
      if (window.mobileAvatarCropper) {
        window.mobileAvatarCropper.destroy();
      }

      // 初始化 cropper
      window.mobileAvatarCropper = new Cropper(cropImage, {
        aspectRatio: 1,
        viewMode: 1,
        dragMode: "move",
        autoCropArea: 0.8,
        restore: false,
        guides: true,
        center: true,
        highlight: false,
        cropBoxMovable: true,
        cropBoxResizable: true,
        toggleDragModeOnDblclick: false,
      });
    }
    // 添加 show 类以触发显示动画
    modal.classList.remove("hidden");
    setTimeout(() => {
      modal.classList.add("show");
    }, 10);
  };
  reader.readAsDataURL(file);
}

function closeMobileAvatarCropModal() {
  const modal = document.getElementById("mobile-avatar-crop-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
  if (window.mobileAvatarCropper) {
    window.mobileAvatarCropper.destroy();
    window.mobileAvatarCropper = null;
  }
}

async function confirmMobileAvatarCrop() {
  if (!window.mobileAvatarCropper) {
    showModalAlert("裁剪器未初始化", "错误");
    return;
  }

  const canvas = window.mobileAvatarCropper.getCroppedCanvas({
    width: 256,
    height: 256,
    imageSmoothingQuality: "high",
  });

  if (!canvas) {
    showModalAlert("裁剪失败", "错误");
    return;
  }

  canvas.toBlob(
    async (blob) => {
      if (!blob) {
        showModalAlert("生成图片失败", "错误");
        return;
      }

      const formData = new FormData();
      formData.append("avatar", blob, "avatar.png");

      try {
        const response = await fetch("/auth/user/upload_avatar", {
          // 修正为后端定义的正确路径
          method: "POST",
          headers: { "X-Session-ID": sessionUUID },
          body: formData,
        });

        const result = await response.json();

        if (result.success) {
          showModalAlert("头像上传成功", "成功");
          closeMobileAvatarCropModal();
          // 刷新个人信息
          loadMobileUnifiedProfile();
          loadMobileUserBillingList();
        } else {
          showModalAlert(result.message || "上传失败", "错误");
        }
      } catch (e) {
        console.error("[移动端头像上传] 失败:", e);
        showModalAlert("上传失败: " + e.message, "错误");
      }
    },
    "image/png",
    0.9,
  );
}

// ========================================
// 【移动端】修改手机号模态框
// ========================================
function showMobileModifyPhoneModal() {
  let modal = document.getElementById("mobile-modify-phone-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-modify-phone-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileModifyPhoneModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileModifyPhoneModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileModifyPhoneModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileModifyPhoneModal()">
          <svg class="w-6 h-6 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
          </svg>
          <h3 class="text-xl font-bold text-sky-600 text-center">修改绑定手机号</h3>
        </div>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">当前手机号</label>
            <div class="flex items-center gap-2">
              <span class="text-sm text-slate-500">+86</span>
              <input type="tel" id="mobile-modify-phone-current" class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-50" readonly>
            </div>
          </div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">新手机号</label>
            <div class="flex items-center gap-2">
              <span class="text-sm text-slate-500">+86</span>
              <input type="tel" id="mobile-modify-phone-new" class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="请输入新手机号" maxlength="11" inputmode="numeric" pattern="[0-9]*">
            </div>
          </div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">短信验证码</label>
            <div class="flex gap-2">
              <input type="text" id="mobile-modify-phone-code" class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="请输入验证码" maxlength="6" inputmode="numeric">
              <button id="mobile-modify-phone-send-code" onclick="sendMobileModifyPhoneCode()" class="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm whitespace-nowrap">发送验证码</button>
            </div>
          </div>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileModifyPhoneModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileModifyPhone()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">确认修改</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // 填入当前手机号
  const currentPhoneInput = document.getElementById(
    "mobile-modify-phone-current",
  );
  if (currentPhoneInput && currentUserData && currentUserData.phone) {
    currentPhoneInput.value = currentUserData.phone;
  }

  // 清空其他输入
  const newPhoneInput = document.getElementById("mobile-modify-phone-new");
  const codeInput = document.getElementById("mobile-modify-phone-code");
  if (newPhoneInput) newPhoneInput.value = "";
  if (codeInput) codeInput.value = "";

  // 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileModifyPhoneModal() {
  const modal = document.getElementById("mobile-modify-phone-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

let mobileModifyPhoneCooldown = 0;

async function sendMobileModifyPhoneCode() {
  if (mobileModifyPhoneCooldown > 0) {
    showModalAlert(`请等待 ${mobileModifyPhoneCooldown} 秒后再发送`, "提示");
    return;
  }

  const newPhoneInput = document.getElementById("mobile-modify-phone-new");
  const phone = newPhoneInput ? newPhoneInput.value.trim() : "";

  if (!phone || phone.length !== 11) {
    showModalAlert("请输入正确的11位手机号", "提示");
    return;
  }

  const sendBtn = document.getElementById("mobile-modify-phone-send-code");
  if (sendBtn) sendBtn.disabled = true;

  try {
    const response = await fetch("/auth/send_modify_phone_code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ phone }),
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert("验证码已发送", "成功");
      // 开始冷却倒计时
      mobileModifyPhoneCooldown = 60;
      const interval = setInterval(() => {
        mobileModifyPhoneCooldown--;
        if (sendBtn) {
          sendBtn.textContent = `${mobileModifyPhoneCooldown}s`;
        }
        if (mobileModifyPhoneCooldown <= 0) {
          clearInterval(interval);
          if (sendBtn) {
            sendBtn.textContent = "发送验证码";
            sendBtn.disabled = false;
          }
        }
      }, 1000);
    } else {
      showModalAlert(result.message || "发送失败", "错误");
      if (sendBtn) sendBtn.disabled = false;
    }
  } catch (e) {
    console.error("[移动端修改手机号] 发送验证码失败:", e);
    showModalAlert("发送失败: " + e.message, "错误");
    if (sendBtn) sendBtn.disabled = false;
  }
}

async function submitMobileModifyPhone() {
  const newPhoneInput = document.getElementById("mobile-modify-phone-new");
  const codeInput = document.getElementById("mobile-modify-phone-code");

  const phone = newPhoneInput ? newPhoneInput.value.trim() : "";
  const code = codeInput ? codeInput.value.trim() : "";

  if (!phone || phone.length !== 11) {
    showModalAlert("请输入正确的11位手机号", "提示");
    return;
  }

  if (!code || code.length !== 6) {
    showModalAlert("请输入6位验证码", "提示");
    return;
  }

  try {
    const response = await fetch("/auth/modify_phone", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ phone, code }),
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert("手机号修改成功", "成功");
      closeMobileModifyPhoneModal();
      // 刷新用户数据
      if (currentUserData) {
        currentUserData.phone = phone;
      }
      loadMobileUnifiedProfile();
      loadMobileUserBillingList();
    } else {
      showModalAlert(result.message || "修改失败", "错误");
    }
  } catch (e) {
    console.error("[移动端修改手机号] 失败:", e);
    showModalAlert("修改失败: " + e.message, "错误");
  }
}

// ========================================
// 【移动端统一面板】个人信息专用函数
// 用于 mobile-admin-panel-unified 的个人信息面板
// ========================================

// 【移动端统一面板】加载个人信息
async function loadMobileUnifiedProfile() {
  try {
    // 修正：将错误的 /auth/get_profile 替换为后端已存在的 /auth/user/details
    const response = await fetch("/auth/user/details", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (result.success) {
      // 修正：后端返回的键名为 'user' 而不是 'data'
      const data = result.user;
      updateAccountCancellationStatusDisplay(data.account_cancellation);

      // 更新头像
      const avatarDisplay = document.getElementById(
        "mobile-unified-profile-avatar-display",
      );
      if (avatarDisplay) {
        let avatarUrl = data.avatar_url || "default_avatar.png";

        // 如果路径不包含 / 且不是默认头像，说明是纯文件名，补全API路径
        if (!avatarUrl.includes("/") && avatarUrl !== "default_avatar.png") {
          avatarUrl = `/api/avatar/${avatarUrl}`;
        }

        // 关键修正：拼接 session_id 用于后端鉴权（img标签无法带header）
        if (typeof sessionUUID !== "undefined" && sessionUUID) {
          const separator = avatarUrl.includes("?") ? "&" : "?";
          avatarUrl += `${separator}session_id=${sessionUUID}`;
        }

        // 添加时间戳防止缓存
        const finalSeparator = avatarUrl.includes("?") ? "&" : "?";
        avatarDisplay.src = avatarUrl + finalSeparator + "t=" + Date.now();
      }

      // 更新昵称
      const authUsernameInput = document.getElementById(
        "mobile-unified-profile-auth-username",
      );
      if (authUsernameInput) {
        authUsernameInput.value = data.auth_username || currentAuthUsername || "";
      }

      // 更新昵称
      const nicknameInput = document.getElementById(
        "mobile-unified-profile-nickname",
      );
      if (nicknameInput) {
        nicknameInput.value = data.nickname || "";
      }

      // 更新手机号
      const phoneInput = document.getElementById(
        "mobile-unified-profile-phone",
      );
      if (phoneInput) {
        phoneInput.value = data.phone || "未绑定";
        _showPhoneLocationNearInput(phoneInput, data.phone);
        // 处理手机号显示
        const phoneWrapper = phoneInput.closest(".phone-input-wrapper");
        if (phoneWrapper) {
          const prefix = phoneWrapper.querySelector(".phone-prefix");
          const isUnbound = !data.phone || data.phone === "未绑定";
          if (prefix) {
            prefix.style.display = isUnbound ? "none" : "inline";
          }
          phoneWrapper.classList.toggle("prefix-hidden", isUnbound);
        }
        // 根据 enable_phone_modification 配置控制修改手机号按钮和提示的显示
        const appConfig = window.APP_CONFIG || {};
        const modifyPhoneBtn = document.getElementById(
          "mobile-unified-modify-phone-btn",
        );
        const modifyPhoneHint = document.getElementById(
          "mobile-unified-modify-phone-hint",
        );
        if (!appConfig.enable_phone_modification) {
          if (modifyPhoneBtn) modifyPhoneBtn.style.display = "none";
          if (modifyPhoneHint) modifyPhoneHint.style.display = "none";
          if (phoneInput) phoneInput.readOnly = true;
        } else {
          if (modifyPhoneBtn) modifyPhoneBtn.style.display = "";
          if (modifyPhoneHint) modifyPhoneHint.style.display = "";
        }
        const mobileForgotPasswordHint = document.getElementById(
          "mobile-forgot-password-hint",
        );
        if (mobileForgotPasswordHint) {
          mobileForgotPasswordHint.style.display =
            appConfig.enable_phone_modification ? "" : "none";
        }
        // --- 新增：更新 2FA 状态 ---
        const tfaStatus = document.getElementById("mobile-unified-2fa-status");
        const tfaActions = document.getElementById(
          "mobile-unified-2fa-actions",
        );
        const tfaEnabledActions = document.getElementById(
          "mobile-unified-2fa-enabled-actions",
        );
        const tfaSetup = document.getElementById("mobile-unified-2fa-setup");

        const tfaEnabled = data["2fa_enabled"] || data.tfa_enabled || false;

        if (tfaStatus) {
          tfaStatus.textContent = tfaEnabled ? "已启用" : "未启用";
          tfaStatus.className = tfaEnabled
            ? "font-bold text-green-600"
            : "text-slate-500";
        }

        if (tfaEnabled) {
          if (tfaActions) tfaActions.classList.add("hidden");
          if (tfaSetup) tfaSetup.classList.add("hidden");
          if (tfaEnabledActions) tfaEnabledActions.classList.remove("hidden");
        } else {
          if (tfaActions) tfaActions.classList.remove("hidden");
          if (tfaEnabledActions) tfaEnabledActions.classList.add("hidden");
          if (tfaSetup) tfaSetup.classList.add("hidden");
        }

        // --- 新增：更新主题设置 ---
        const themeSelect = document.getElementById(
          "mobile-unified-theme-select",
        );
        if (themeSelect && data.theme) {
          themeSelect.value = data.theme;
        }

        // 加载全局参数中的颜色
        try {
          const paramsResult = await callPythonAPI("get_params");
          if (paramsResult) {
            if (paramsResult.theme_base_color) {
              // 修正：同步更新取色器和文本框，使用新ID
              const colorPicker = document.getElementById(
                "mobile-unified-theme_base_color-picker",
              );
              const colorText = document.getElementById(
                "mobile-unified-theme_base_color",
              );
              if (colorPicker)
                colorPicker.value = paramsResult.theme_base_color;
              if (colorText) colorText.value = paramsResult.theme_base_color;
            }
            // 新增：初始化时自动高亮当前选中的样式按钮
            if (paramsResult.theme_style) {
              setMobileUnifiedThemeStyle(paramsResult.theme_style);
            }
          }
        } catch (e) {
          console.error("[移动端统一面板-个人信息] 加载全局参数失败:", e);
          showModalAlert("加载全局参数失败: " + e.message, "错误");
        }

        // === 更新 available_runs 显示 ===
        // 调用 updateProfileAvailableRuns 函数来更新移动端个人资料中的 available_runs 显示
        // 该函数会根据 config[Profile_Display].available_runs_format 的格式来显示可用次数
        // 传入完整的用户数据对象，函数内部会提取 available_runs 字段并格式化显示
        try {
          // 调用更新函数，传入用户数据
          await updateProfileAvailableRuns(data);
          // 记录成功日志，使用移动端统一面板的日志前缀便于调试
          console.log("[移动端统一面板-个人信息] ✓ 已更新 available_runs 显示");
        } catch (e) {
          // 如果更新失败，记录警告日志但不影响主流程
          // 这是一个增强功能，即使失败也不应该阻断个人信息的加载
          console.warn(
            "[移动端统一面板-个人信息] 更新 available_runs 显示失败:",
            e,
          );
        }
      }
    } else {
      showModalAlert(result.message || "加载个人信息失败", "错误");
    }
  } catch (e) {
    console.error("[移动端统一面板-个人信息] 加载失败:", e);
    showModalAlert("加载个人信息失败: " + e.message, "错误");
  }
}

// 【移动端统一面板】处理头像文件选择
async function handleMobileUnifiedAvatarFile(file) {
  if (!file) return;

  if (!file.type.startsWith("image/")) {
    showModalAlert("请选择图片文件", "错误");
    return;
  }

  // 显示移动端头像裁剪模态框
  showMobileUnifiedAvatarCropModal(file);
}

// 【移动端统一面板】头像裁剪模态框
function showMobileUnifiedAvatarCropModal(file) {
  let modal = document.getElementById("mobile-unified-avatar-crop-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-unified-avatar-crop-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileUnifiedAvatarCropModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/80" onclick="closeMobileUnifiedAvatarCropModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileUnifiedAvatarCropModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <h3 class="text-xl font-bold text-sky-600 text-center">裁剪头像</h3>
        <div class="max-h-80 overflow-hidden bg-slate-100 rounded-lg">
          <img id="mobile-unified-crop-image" src="" alt="待裁剪图片" style="max-width: 100%">
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileUnifiedAvatarCropModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="confirmMobileUnifiedAvatarCrop()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">确认上传</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  const reader = new FileReader();
  reader.onload = function (e) {
    const cropImage = document.getElementById("mobile-unified-crop-image");
    if (cropImage) {
      cropImage.src = e.target.result;

      // 销毁旧的 cropper
      if (window.mobileUnifiedAvatarCropper) {
        window.mobileUnifiedAvatarCropper.destroy();
      }

      // 初始化 cropper
      window.mobileUnifiedAvatarCropper = new Cropper(cropImage, {
        aspectRatio: 1,
        viewMode: 1,
        dragMode: "move",
        autoCropArea: 0.8,
        restore: false,
        guides: true,
        center: true,
        highlight: false,
        cropBoxMovable: true,
        cropBoxResizable: true,
        toggleDragModeOnDblclick: false,
      });
    }
    // 添加 show 类以触发显示动画
    modal.classList.remove("hidden");
    setTimeout(() => {
      modal.classList.add("show");
    }, 10);
  };
  reader.readAsDataURL(file);
}

function closeMobileUnifiedAvatarCropModal() {
  const modal = document.getElementById("mobile-unified-avatar-crop-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
  if (window.mobileUnifiedAvatarCropper) {
    window.mobileUnifiedAvatarCropper.destroy();
    window.mobileUnifiedAvatarCropper = null;
  }
}

async function confirmMobileUnifiedAvatarCrop() {
  if (!window.mobileUnifiedAvatarCropper) {
    showModalAlert("裁剪器未初始化", "错误");
    return;
  }

  const canvas = window.mobileUnifiedAvatarCropper.getCroppedCanvas({
    width: 256,
    height: 256,
    imageSmoothingQuality: "high",
  });

  if (!canvas) {
    showModalAlert("裁剪失败", "错误");
    return;
  }

  canvas.toBlob(
    async (blob) => {
      if (!blob) {
        showModalAlert("生成图片失败", "错误");
        return;
      }

      const formData = new FormData();
      formData.append("avatar", blob, "avatar.png");

      try {
        const response = await fetch("/auth/user/upload_avatar", {
          method: "POST",
          headers: { "X-Session-ID": sessionUUID },
          body: formData,
        });

        const result = await response.json();

        if (result.success) {
          showModalAlert("头像上传成功", "成功");
          closeMobileUnifiedAvatarCropModal();
          // 刷新个人信息
          loadMobileUnifiedProfile();
        } else {
          showModalAlert(result.message || "上传失败", "错误");
        }
      } catch (e) {
        console.error("[移动端统一面板-头像上传] 失败:", e);
        showModalAlert("上传失败: " + e.message, "错误");
      }
    },
    "image/png",
    0.9,
  );
}

// 【移动端统一面板】修改手机号模态框
function showMobileUnifiedModifyPhoneModal() {
  let modal = document.getElementById("mobile-unified-modify-phone-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-unified-modify-phone-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileUnifiedModifyPhoneModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileUnifiedModifyPhoneModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileUnifiedModifyPhoneModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileUnifiedModifyPhoneModal()">
          <svg class="w-6 h-6 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
          </svg>
          <h3 class="text-xl font-bold text-sky-600 text-center">修改绑定手机号</h3>
        </div>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">当前手机号</label>
            <div class="phone-input-wrapper">
              <span class="phone-prefix">+86 </span>
              <input
                type="tel"
                id="mobile-unified-modify-phone-current"
                class="input-field !text-xs !py-1.5"
                readonly
                disabled
              />
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">验证原密码 <span class="text-red-500">*</span></label>
            <input
              type="password"
              id="mobile-unified-modify-phone-password"
              class="input-field !text-xs !py-1.5 w-full"
              placeholder="请输入当前账号密码进行验证"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">新手机号</label>
            <div class="phone-input-wrapper">
              <span class="phone-prefix">+86 </span>
              <input
                type="tel"
                id="mobile-unified-modify-phone-new"
                class="input-field !text-xs !py-1.5"
                placeholder="请输入新手机号"
                inputmode="numeric"
                maxlength="11"
              />
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-slate-600 mb-1">验证码</label>
            <div class="flex gap-2">
              <input
                type="text"
                id="mobile-unified-modify-phone-code"
                class="input-field flex-1 !text-xs !py-1.5"
                placeholder="请输入验证码"
                maxlength="6"
                inputmode="numeric"
              />
              <button
                id="mobile-unified-modify-phone-send-code"
                onclick="sendMobileUnifiedModifyPhoneCode()"
                class="btn btn-ghost border border-slate-300 !py-1 !px-2 text-xs whitespace-nowrap"
              >
                发送验证码
              </button>
            </div>
          </div>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileUnifiedModifyPhoneModal()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="confirmMobileUnifiedModifyPhone()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">确认修改</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // 填充当前手机号
  const currentPhone = document.getElementById("mobile-unified-profile-phone");
  const currentPhoneModal = document.getElementById(
    "mobile-unified-modify-phone-current",
  );
  if (currentPhoneModal && currentPhone) {
    currentPhoneModal.value = currentPhone.value || "";
    _showPhoneLocationNearInput(currentPhoneModal, currentPhone.value);
    // 处理手机号显示
    const phoneWrapper = currentPhoneModal.closest(".phone-input-wrapper");
    if (phoneWrapper) {
      const prefix = phoneWrapper.querySelector(".phone-prefix");
      const isUnbound = !currentPhone.value || currentPhone.value === "未绑定";
      if (prefix) {
        prefix.style.display = isUnbound ? "none" : "inline";
      }
      phoneWrapper.classList.toggle("prefix-hidden", isUnbound);
    }
  }

  // 清空新手机号和验证码
  const newPhoneInput = document.getElementById(
    "mobile-unified-modify-phone-new",
  );
  const codeInput = document.getElementById("mobile-unified-modify-phone-code");
  if (newPhoneInput) newPhoneInput.value = "";
  if (codeInput) codeInput.value = "";
  document.getElementById("mobile-unified-modify-phone-password").value = "";

  // 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileUnifiedModifyPhoneModal() {
  const modal = document.getElementById("mobile-unified-modify-phone-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

let mobileUnifiedModifyPhoneCooldown = 0;

async function sendMobileUnifiedModifyPhoneCode() {
  if (mobileUnifiedModifyPhoneCooldown > 0) {
    showModalAlert(
      `请等待 ${mobileUnifiedModifyPhoneCooldown} 秒后再发送`,
      "提示",
    );
    return;
  }

  const newPhoneInput = document.getElementById(
    "mobile-unified-modify-phone-new",
  );
  const phone = newPhoneInput ? newPhoneInput.value.trim() : "";

  if (!phone || phone.length !== 11) {
    showModalAlert("请输入正确的11位手机号", "提示");
    return;
  }

  const sendBtn = document.getElementById(
    "mobile-unified-modify-phone-send-code",
  );
  if (sendBtn) sendBtn.disabled = true;

  // 打开图形验证码模态框
  openCaptchaModal({
    phone: phone,
    button: sendBtn,
    originalText: "发送验证码",
    scene: "modify",
  });
}

async function confirmMobileUnifiedModifyPhone() {
  // 获取用户输入的原密码，用于身份验证
  const password = document
    .getElementById("mobile-unified-modify-phone-password")
    .value.trim();
  // 验证原密码是否已填写，这是安全验证的必要步骤
  if (!password) {
    showModalAlert("请输入原密码进行验证", "提示");
    return;
  }
  const newPhone = document
    .getElementById("mobile-unified-modify-phone-new")
    .value.trim();
  const code = document
    .getElementById("mobile-unified-modify-phone-code")
    .value.trim();

  if (!newPhone || newPhone.length !== 11) {
    showModalAlert("请输入正确的11位手机号", "提示");
    return;
  }

  if (!code) {
    showModalAlert("请输入验证码", "提示");
    return;
  }

  try {
    const response = await fetch("/api/user/update_phone", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        new_phone: newPhone,
        sms_code: code,
        password: password,
      }), // 添加原密码参数用于身份验证
    });

    const result = await response.json();

    if (result.success) {
      showModalAlert("手机号修改成功", "成功");
      closeMobileUnifiedModifyPhoneModal();
      // 刷新个人信息
      loadMobileUnifiedProfile();
    } else {
      showModalAlert(result.message || "修改失败", "错误");
    }
  } catch (e) {
    console.error("[移动端统一面板-修改手机号] 失败:", e);
    showModalAlert("修改失败: " + e.message, "错误");
  }
}

// 【移动端统一面板】更新基本信息
async function updateMobileUnifiedBasicInfo() {
  const nickname = document
    .getElementById("mobile-unified-profile-nickname")
    .value.trim();

  // 新增：确保获取到当前用户名 (全局变量 currentAuthUsername 在 initializeApp/loadPersonalInfo 中赋值)
  if (!currentAuthUsername) {
    showModalAlert("无法获取当前用户信息，请刷新页面", "错误");
    return;
  }

  try {
    // 修正：参考 updateBasicInfo，使用正确的后端接口和 PUT 方法
    const response = await fetch(
      "/api/admin/users/" +
        encodeURIComponent(currentAuthUsername) +
        "/basic_info",
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
        body: JSON.stringify({ nickname: nickname }),
      },
    );

    const result = await response.json();

    if (result.success) {
      showModalAlert("基本信息更新成功", "成功");
      // 刷新个人信息
      loadMobileUnifiedProfile();
    } else {
      showModalAlert(result.message || "更新失败", "错误");
    }
  } catch (e) {
    console.error("[移动端统一面板-更新基本信息] 失败:", e);
    showModalAlert("更新失败: " + e.message, "错误");
  }
}

// 【移动端统一面板】修改密码
// 支持两种验证模式：原密码验证 或 短信验证码验证
async function updateMobileUnifiedPassword() {
  // 获取当前密码输入框DOM元素
  const currentPasswordInput = document.getElementById(
    "mobile-unified-current-password",
  );
  // 获取新密码输入框DOM元素
  const newPasswordInput = document.getElementById(
    "mobile-unified-new-password",
  );
  // 获取确认新密码输入框DOM元素
  const confirmPasswordInput = document.getElementById(
    "mobile-unified-confirm-password",
  );

  // 获取输入框的值
  const currentPassword = currentPasswordInput
    ? currentPasswordInput.value
    : "";
  const newPassword = newPasswordInput ? newPasswordInput.value : "";
  const confirmPassword = confirmPasswordInput
    ? confirmPasswordInput.value
    : "";

  // 判断当前是否使用短信验证模式
  const useSmsVerify = mobilePasswordVerifyMode === "sms";
  // 如果是短信验证模式，获取短信验证码
  const smsCode = useSmsVerify
    ? document.getElementById("mobile-password-sms-code")?.value?.trim()
    : null;

  // 校验用户信息是否可用
  if (!currentAuthUsername) {
    showModalAlert("无法获取当前用户信息，请刷新页面", "错误");
    return;
  }

  // 根据验证模式进行不同的校验
  if (!useSmsVerify) {
    // 密码验证模式：检查原密码是否填写
    if (!currentPassword) {
      showModalAlert(
        '请输入当前密码，或点击"使用短信验证"通过短信验证码修改密码',
        "提示",
      );
      return;
    }
  } else {
    // 短信验证模式：检查验证码是否填写
    if (!smsCode) {
      showModalAlert("请填写短信验证码", "提示");
      return;
    }
    // 验证码格式校验（6位数字）
    if (!/^\d{6}$/.test(smsCode)) {
      showModalAlert("短信验证码格式不正确，请输入6位数字", "提示");
      return;
    }
  }

  // 检查新密码是否填写
  if (!newPassword) {
    showModalAlert("请输入新密码", "提示");
    return;
  }

  // 检查两次输入的新密码是否一致
  if (newPassword !== confirmPassword) {
    showModalAlert("两次输入的新密码不一致", "提示");
    return;
  }

  // 检查新密码强度
  // 在提交密码修改请求之前，先检查新密码是否为弱密码
  // 这可以防止用户设置不安全的密码，提高账户安全性
  var weakCheck = checkWeakPassword(newPassword);
  if (weakCheck.isWeak) {
    // 如果新密码过弱，显示具体的错误原因
    showModalAlert(weakCheck.reason, "密码强度不足");
    return;
  }

  // 检查新密码长度是否符合要求（最少6位）
  if (newPassword.length < 6) {
    showModalAlert("新密码长度至少为6位", "提示");
    return;
  }

  try {
    // 构建API请求体
    const requestBody = {
      username: currentAuthUsername, // 必填：当前用户名
      new_password: newPassword, // 必填：新密码
    };

    // 根据验证模式添加不同的验证字段
    if (useSmsVerify) {
      // 短信验证模式：传递短信验证码，原密码设为null
      requestBody.sms_code = smsCode;
      requestBody.old_password = null;
      console.log("[移动端统一面板-修改密码] 使用短信验证模式提交");
    } else {
      // 密码验证模式：传递原密码
      requestBody.old_password = currentPassword;
      console.log("[移动端统一面板-修改密码] 使用密码验证模式提交");
    }

    // 发送密码修改请求到后端API
    const response = await fetch("/auth/admin/reset_password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(requestBody),
    });

    // 解析API响应
    const result = await response.json();

    if (result.success) {
      // 密码修改成功
      showModalAlert("密码修改成功", "成功");
      // 清空密码输入框
      if (currentPasswordInput) currentPasswordInput.value = "";
      if (newPasswordInput) newPasswordInput.value = "";
      if (confirmPasswordInput) confirmPasswordInput.value = "";
      // 重置验证模式到默认状态（密码验证）
      resetPasswordVerifyMode("mobile");
    } else {
      // 密码修改失败，显示错误信息
      const errorMsg = useSmsVerify
        ? result.message || "请检查短信验证码是否正确"
        : result.message || "修改失败";
      showModalAlert(errorMsg, "错误");
    }
  } catch (e) {
    // 捕获网络错误或其他异常
    console.error("[移动端统一面板-修改密码] 失败:", e);
    showModalAlert("修改失败: " + e.message, "错误");
  }
}

// ========================================
// 【移动端统一面板】功能补全：2FA、主题、样式
// ========================================

// 1. 生成 2FA 密钥
async function generateMobileUnified2FA() {
  try {
    const response = await fetch("/auth/2fa/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();

    if (!result.success) {
      showModalAlert(`生成2FA失败: ${result.message}`, "错误");
      return;
    }

    // 更新UI显示
    const setupDiv = document.getElementById("mobile-unified-2fa-setup");
    const actionsDiv = document.getElementById("mobile-unified-2fa-actions");
    if (setupDiv) setupDiv.classList.remove("hidden");
    if (actionsDiv) actionsDiv.classList.add("hidden");

    // 显示密钥
    const secretSpan = document.getElementById("mobile-unified-2fa-secret");
    if (secretSpan && result.secret) {
      secretSpan.textContent = result.secret;
    }

    // 生成二维码
    const qrCanvas = document.getElementById("mobile-unified-2fa-qr");
    if (qrCanvas && result.qr_uri) {
      if (typeof QRCode !== "undefined") {
        // 清除旧内容
        const ctx = qrCanvas.getContext("2d");
        ctx.clearRect(0, 0, qrCanvas.width, qrCanvas.height);

        QRCode.toCanvas(
          qrCanvas,
          result.qr_uri,
          { width: 160, margin: 2 },
          function (error) {
            if (error) {
              console.error("QR Code generation error:", error);
              showModalAlert("二维码生成失败", "错误");
            }
          },
        );
      } else {
        showModalAlert("QRCode库未加载，请刷新页面重试", "错误");
      }
    }
  } catch (e) {
    console.error("生成2FA失败:", e);
    showModalAlert(`生成失败: ${e.message}`, "错误");
  }
}

// 2. 启用 2FA
async function enableMobileUnified2FA() {
  const codeInput = document.getElementById("mobile-unified-2fa-code");
  if (!codeInput || !codeInput.value) {
    showModalAlert("请输入验证码", "提示");
    return;
  }

  try {
    const response = await fetch("/auth/2fa/enable", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        code: codeInput.value,
      }),
    });
    const result = await response.json();

    if (result.success) {
      showModalAlert("2FA启用成功！", "成功");
      // 刷新个人信息面板以更新状态
      loadMobileUnifiedProfile();
    } else {
      showModalAlert(`启用失败: ${result.message}`, "错误");
    }
  } catch (e) {
    console.error("启用2FA失败:", e);
    showModalAlert(`启用失败: ${e.message}`, "错误");
  }
}

// 3. 关闭 2FA
async function disableMobileUnified2FA() {
  const confirmed = await jsShowConfirm(
    "确认关闭2FA",
    "关闭双因素认证后，账号安全性将降低。确定要继续吗？",
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/2fa/disable", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });
    const result = await response.json();

    if (result.success) {
      showModalAlert("2FA已关闭", "成功");
      loadMobileUnifiedProfile();
    } else {
      showModalAlert(`关闭失败: ${result.message}`, "错误");
    }
  } catch (e) {
    console.error("关闭2FA失败:", e);
    showModalAlert(`关闭失败: ${e.message}`, "错误");
  }
}

// 5. 设置主题样式
function setMobileUnifiedThemeStyle(styleName) {
  if (typeof setThemeStyle === "function") {
    setThemeStyle(styleName);
  }

  renderThemeStyleButtons(
    document.getElementById("mobile-unified-theme-style-buttons"),
    styleName,
    { mobile: true },
  );
}

// ========================================
// 【移动端用户管理】专用模态框函数
// 为移动端用户列表中的操作按钮提供适配的UI
// ========================================

// 【移动端】查看用户学校账户密码
async function showMobileUserSchoolAccounts(username) {
  let modal = document.getElementById("mobile-user-school-accounts-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-user-school-accounts-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileUserSchoolAccounts();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileUserSchoolAccounts()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileUserSchoolAccounts()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileUserSchoolAccounts()">
          <svg class="w-6 h-6 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
          </svg>
          <h3 class="text-xl font-bold text-indigo-600 text-center">学校账户密码</h3>
        </div>
        <div class="text-center text-sm text-slate-500" id="mobile-school-accounts-username"></div>
        <div id="mobile-school-accounts-list" class="space-y-3 max-h-[50vh] overflow-y-auto">
          <p class="text-slate-400 text-center py-10 text-xs">加载中...</p>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileUserSchoolAccounts()" class="flex-1 py-2 px-4 bg-slate-100 text-slate-600 rounded-lg text-sm">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  document.getElementById("mobile-school-accounts-username").textContent =
    `用户: ${username}`;
  document.getElementById("mobile-school-accounts-list").innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);

  try {
    const response = await fetch(
      `/auth/get_user_school_accounts_only?username=${encodeURIComponent(username)}`,
      {
        headers: { "X-Session-ID": sessionUUID },
      },
    );
    const result = await response.json();

    if (!result.success) {
      document.getElementById("mobile-school-accounts-list").innerHTML =
        `<p class="text-red-500 text-center py-10 text-xs">${
          result.message || "加载失败"
        }</p>`;
      return;
    }

    const accounts = result.accounts || {};
    const accountCount = Object.keys(accounts).length;

    // 更新账户总数显示
    const countEl = document.getElementById("mobile-school-accounts-count");
    if (countEl) {
      countEl.textContent = accountCount.toString();
    }

    if (accountCount === 0) {
      document.getElementById("mobile-school-accounts-list").innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">该用户暂无学校账户</p>';
      return;
    }

    let html = "";
    for (const [schoolUsername, accountData] of Object.entries(accounts)) {
      let password =
        typeof accountData === "string"
          ? accountData
          : accountData?.password || "";
      let ua = typeof accountData === "object" ? accountData?.ua || "" : "";

      html += `
        <div class="bg-gradient-to-br from-white to-slate-50 p-4 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-200 space-y-3">
          <div class="flex items-center gap-3 pb-2 border-b border-slate-100">
            <svg class="w-5 h-5 text-indigo-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
            </svg>
            <div class="flex-1 min-w-0">
              <div class="text-xs text-slate-500 font-medium">学校账号</div>
              <div class="font-semibold text-slate-800 text-sm truncate">${escapeHtml(
                schoolUsername,
              )}</div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <svg class="w-5 h-5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
            </svg>
            <div class="flex-1 min-w-0">
              <div class="text-xs text-slate-500 font-medium">密码</div>
              <div class="font-mono text-xs text-slate-700 select-all bg-white px-3 py-1 rounded-md border border-slate-300 shadow-sm">${escapeHtml(
                password,
              )}</div>
            </div>
          </div>
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <svg class="w-4 h-4 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
              </svg>
              <div class="text-xs text-slate-500 font-medium">User Agent</div>
            </div>
            ${
              ua
                ? `<div class="text-xs text-slate-600 break-words bg-slate-100 px-3 py-2 rounded-md border max-h-auto overflow-y-hidden">${escapeHtml(
                    ua,
                  )}</div>`
                : '<div class="text-xs text-slate-400 italic text-center py-2">无UA信息</div>'
            }
          </div>
          
            <button 
              class="w-full py-2.5 px-4 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 active:bg-blue-700 transition-colors max-h-[36px] flex items-center justify-center gap-2"
              data-account='${JSON.stringify({
                authUsername: username,
                schoolUsername: schoolUsername,
                password: password,
                ua: ua,
              }).replace(/'/g, "&apos;")}'
              onclick="(function(btn) { const data = JSON.parse(btn.getAttribute('data-account')); editSchoolAccount(data.authUsername, data.schoolUsername, data.password, data.ua); })(this)"
              title="编辑此账户的密码和UA">
              <!-- 编辑图标 -->
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
              </svg>
              编辑账户
            </button>
            
            <!-- 查看详情按钮：显示该学校账号的备份详情和欠费信息 -->
            <!-- 调用 View_details_of_users_with_outstanding_payments 函数 -->
            <!-- 该函数会显示一个包含详细信息的弹窗（学号、姓名、欠费次数等） -->
            <button 
              class="w-full py-2.5 px-4 bg-sky-500 text-white rounded-lg text-sm font-medium hover:bg-sky-600 active:bg-sky-700 transition-colors max-h-[36px] flex items-center justify-center gap-2"
              onclick="View_details_of_users_with_outstanding_payments(${escapeInlineJsArg(
                schoolUsername,
              )})"
              title="查看此账户的详细信息（备份数据、欠费次数等）">
              <!-- 眼睛图标 -->
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
              查看详情
            </button>
            
            <!-- 删除按钮：确认后删除账户 -->
            <!-- 使用红色背景，表示危险操作 -->
            <!-- 删除操作会触发二次确认对话框 -->
            <button 
              class="w-full py-2.5 px-4 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 active:bg-red-700 transition-colors max-h-[36px] flex items-center justify-center gap-2"
              data-auth-username='${escapeHtml(username)}'
              data-school-username='${escapeHtml(schoolUsername)}'
              onclick="(function(btn) { deleteSchoolAccount(btn.getAttribute('data-auth-username'), btn.getAttribute('data-school-username')); })(this)"
              title="删除此账户（不可恢复）">
              <!-- 垃圾桶图标 -->
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
              </svg>
              删除账户
            </button>
          </div>
        </div>
      `;
    }

    document.getElementById("mobile-school-accounts-list").innerHTML = html;
  } catch (e) {
    document.getElementById("mobile-school-accounts-list").innerHTML =
      `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${e.message}</p>`;
  }
}

function closeMobileUserSchoolAccounts() {
  const modal = document.getElementById("mobile-user-school-accounts-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

// 【移动端】查看用户日志
async function showMobileUserLogs(username) {
  let modal = document.getElementById("mobile-user-logs-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-user-logs-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileUserLogs();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileUserLogs()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileUserLogs()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileUserLogs()">
          <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
          </svg>
          <h3 class="text-xl font-bold text-blue-600 text-center">用户日志</h3>
        </div>
        <div class="text-center text-sm text-slate-500" id="mobile-user-logs-username"></div>
        <div class="flex gap-2 border-b border-slate-200">
          <button id="mobile-log-tab-login" onclick="switchMobileUserLogTab('login')" class="flex-1 py-2 text-sm font-semibold text-sky-600 border-b-2 border-sky-600">登录日志</button>
          <button id="mobile-log-tab-audit" onclick="switchMobileUserLogTab('audit')" class="flex-1 py-2 text-sm font-semibold text-slate-400 border-b-2 border-transparent">审计日志</button>
        </div>
        <div id="mobile-user-logs-content" class="space-y-2 max-h-[45vh] overflow-y-auto">
          <p class="text-slate-400 text-center py-10 text-xs">加载中...</p>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileUserLogs()" class="flex-1 py-2 px-4 bg-slate-100 text-slate-600 rounded-lg text-sm">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  window.currentMobileLogUsername = username;
  document.getElementById("mobile-user-logs-username").textContent =
    `用户: ${username}`;

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);

  // 默认显示登录日志
  switchMobileUserLogTab("login");
}

function closeMobileUserLogs() {
  const modal = document.getElementById("mobile-user-logs-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

async function switchMobileUserLogTab(tab) {
  const loginTab = document.getElementById("mobile-log-tab-login");
  const auditTab = document.getElementById("mobile-log-tab-audit");
  const content = document.getElementById("mobile-user-logs-content");
  const username = window.currentMobileLogUsername;

  if (tab === "login") {
    loginTab.className =
      "flex-1 py-2 text-sm font-semibold text-sky-600 border-b-2 border-sky-600";
    auditTab.className =
      "flex-1 py-2 text-sm font-semibold text-slate-400 border-b-2 border-transparent";
    await loadMobileUserLoginLogs(username);
  } else {
    auditTab.className =
      "flex-1 py-2 text-sm font-semibold text-sky-600 border-b-2 border-sky-600";
    loginTab.className =
      "flex-1 py-2 text-sm font-semibold text-slate-400 border-b-2 border-transparent";
    await loadMobileUserAuditLogs(username);
  }
}

async function loadMobileUserLoginLogs(username) {
  const content = document.getElementById("mobile-user-logs-content");
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  try {
    const response = await fetch(
      `/api/admin/logs/login_history?username=${encodeURIComponent(username)}`,
      {
        headers: { "X-Session-ID": sessionUUID },
      },
    );
    const data = await response.json();

    if (data.success && data.logs && data.logs.length > 0) {
      content.innerHTML = data.logs
        .map(
          (log) => `
        <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg">
          <div class="flex justify-between items-start mb-2">
            <span class="text-xs text-slate-500">${(
              log.datetime || "N/A"
            ).replace("T", " ")}</span>
            ${
              log.success
                ? '<span class="text-xs px-2 py-0.5 rounded bg-green-100 text-green-600">成功</span>'
                : '<span class="text-xs px-2 py-0.5 rounded bg-red-100 text-red-600">失败</span>'
            }
          </div>
          <div class="text-xs text-slate-600">IP: ${
            log.ip_address || "N/A"
          }</div>
          ${
            log.location
              ? `<div class="text-xs text-slate-500">${log.location}</div>`
              : ""
          }
        </div>
      `,
        )
        .join("");
    } else {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">暂无登录日志</p>';
    }
  } catch (e) {
    content.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${e.message}</p>`;
  }
}

async function loadMobileUserAuditLogs(username) {
  const content = document.getElementById("mobile-user-logs-content");
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  try {
    const response = await fetch(
      `/api/admin/logs/audit?username=${encodeURIComponent(username)}`,
      {
        headers: { "X-Session-ID": sessionUUID },
      },
    );
    const data = await response.json();

    if (data.success && data.logs && data.logs.length > 0) {
      content.innerHTML = data.logs
        .slice()
        .reverse()
        .map(
          (log) => `
        <div class="p-3 bg-slate-50 border border-slate-200 rounded-lg">
          <div class="flex justify-between items-start mb-2">
            <span class="text-xs text-slate-500">${(
              log.datetime || "N/A"
            ).replace("T", " ")}</span>
            <span class="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-600">${
              log.action || "操作"
            }</span>
          </div>
          <div class="text-xs text-slate-600">${log.details || "无详情"}</div>
        </div>
      `,
        )
        .join("");
    } else {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">暂无审计日志</p>';
    }
  } catch (e) {
    content.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${e.message}</p>`;
  }
}

// 【移动端】会话管理
function showMobileUserSessions(username, currentMax) {
  let modal = document.getElementById("mobile-user-sessions-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-user-sessions-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileUserSessions();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileUserSessions()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileUserSessions()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileUserSessions()">
          <svg class="w-6 h-6 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <h3 class="text-xl font-bold text-blue-600 text-center">会话管理</h3>
        </div>
        <div class="space-y-4">
          <div class="text-center text-sm text-slate-600">用户: <span id="mobile-sessions-username" class="font-semibold"></span></div>
          <div class="text-center text-sm text-slate-500">当前最大会话数: <span id="mobile-sessions-current" class="font-semibold text-sky-600"></span></div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">新的最大会话数</label>
            <input type="number" id="mobile-new-max-sessions" min="0" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="0 表示无限制">
            <p class="text-xs text-slate-500 mt-1">输入 0 表示无限制</p>
          </div>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileUserSessions()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileUserSessions()" class="flex-1 py-2 px-4 bg-sky-500 text-white rounded-lg text-sm">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  window.currentMobileSessionsUsername = username;
  document.getElementById("mobile-sessions-username").textContent = username;
  document.getElementById("mobile-sessions-current").textContent =
    currentMax === -1 ? "无限制" : currentMax;
  document.getElementById("mobile-new-max-sessions").value =
    currentMax === -1 ? 0 : currentMax;

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileUserSessions() {
  const modal = document.getElementById("mobile-user-sessions-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

async function submitMobileUserSessions() {
  const username = window.currentMobileSessionsUsername;
  const newMax = parseInt(
    document.getElementById("mobile-new-max-sessions").value,
  );

  if (isNaN(newMax) || newMax < 0) {
    showModalAlert("请输入有效的数字（0或更大）", "错误");
    return;
  }

  const maxSessions = newMax === 0 ? -1 : newMax;

  try {
    const response = await fetch("/auth/admin/update_max_sessions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username, max_sessions: maxSessions }),
    });

    const result = await response.json();
    if (result.success) {
      showModalAlert(
        `已更新用户 ${username} 的最大会话数为: ${
          maxSessions === -1 ? "无限制" : maxSessions
        }`,
        "成功",
      );
      closeMobileUserSessions();
      loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"));
    } else {
      showModalAlert(result.message || "更新失败", "错误");
    }
  } catch (e) {
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

// 【移动端】权限设置
async function showMobileUserPermissions(username) {
  let modal = document.getElementById("mobile-user-permissions-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-user-permissions-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileUserPermissions();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileUserPermissions()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileUserPermissions()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileUserPermissions()">
          <svg class="w-6 h-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
          </svg>
          <h3 class="text-xl font-bold text-emerald-600 text-center">权限设置</h3>
        </div>
        <div class="text-center text-sm text-slate-600">用户: <span id="mobile-permissions-username" class="font-semibold"></span></div>
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p class="text-xs text-blue-700">权限组: <span id="mobile-user-base-group" class="font-mono font-semibold"></span></p>
          <p class="text-xs text-slate-600 mt-1">💡 绿色表示新增权限，红色表示移除权限</p>
        </div>
        <div id="mobile-user-permissions-list" class="space-y-1 max-h-[40vh] overflow-y-auto border border-slate-200 rounded-lg p-2">
          <p class="text-slate-400 text-center py-10 text-xs">加载中...</p>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileUserPermissions()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileUserPermissions()" class="flex-1 py-2 px-4 bg-emerald-500 text-white rounded-lg text-sm">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  window.currentMobilePermissionsUsername = username;
  document.getElementById("mobile-permissions-username").textContent = username;
  document.getElementById("mobile-user-permissions-list").innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);

  try {
    const response = await fetch("/auth/admin/get_user_permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username }),
    });
    const result = await response.json();

    if (!result.success) {
      showModalAlert("无法加载用户权限信息", "错误");
      return;
    }

    document.getElementById("mobile-user-base-group").textContent =
      result.group || "guest";

    if (result.all_permissions) {
      const groupPerms = result.group_permissions || {};
      const addedPerms = result.added_permissions || {};
      const removedPerms = result.removed_permissions || {};

      const html = Object.keys(result.all_permissions)
        .map((perm) => {
          const isAdded = addedPerms[perm] === true;
          const isRemoved = removedPerms[perm] === true;
          const currentValue = result.all_permissions[perm];
          const groupValue = groupPerms[perm] || false;

          let statusClass = "";
          if (isAdded) statusClass = "bg-green-50 border-green-200";
          else if (isRemoved) statusClass = "bg-red-50 border-red-200";

          return `
          <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded cursor-pointer border ${statusClass}">
            <input type="checkbox" class="w-4 h-4 rounded" data-permission="${perm}" data-group-value="${groupValue}" ${
              currentValue ? "checked" : ""
            }>
            <span class="text-xs text-slate-700 flex-1">${translatePermission(
              perm,
            )}</span>
            ${
              isAdded
                ? '<span class="text-xs text-green-600">(新增)</span>'
                : ""
            }
            ${
              isRemoved
                ? '<span class="text-xs text-red-600">(移除)</span>'
                : ""
            }
          </label>
        `;
        })
        .join("");

      document.getElementById("mobile-user-permissions-list").innerHTML = html;
    }
  } catch (e) {
    showModalAlert("加载失败: " + e.message, "错误");
  }
}

function closeMobileUserPermissions() {
  const modal = document.getElementById("mobile-user-permissions-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

async function submitMobileUserPermissions() {
  const username = window.currentMobilePermissionsUsername;
  const container = document.getElementById("mobile-user-permissions-list");

  const addedPermissions = {};
  const removedPermissions = {};

  container.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    const perm = cb.getAttribute("data-permission");
    const groupValue = cb.getAttribute("data-group-value") === "true";
    const currentValue = cb.checked;

    if (currentValue && !groupValue) {
      addedPermissions[perm] = true;
    } else if (!currentValue && groupValue) {
      removedPermissions[perm] = true;
    }
  });

  try {
    const response = await fetch("/auth/admin/set_user_permission", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        username,
        added_permissions: addedPermissions,
        removed_permissions: removedPermissions,
      }),
    });

    const result = await response.json();
    if (result.success) {
      showModalAlert(`用户 ${username} 的权限已更新`, "成功");
      closeMobileUserPermissions();
      loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"));
    } else {
      showModalAlert(result.message || "更新失败", "错误");
    }
  } catch (e) {
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

// 【移动端】修改昵称
function showMobileModifyNickname(username, currentNickname) {
  let modal = document.getElementById("mobile-modify-nickname-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-modify-nickname-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileModifyNickname();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileModifyNickname()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileModifyNickname()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileModifyNickname()">
          <svg class="w-6 h-6 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
          </svg>
          <h3 class="text-xl font-bold text-teal-600 text-center">修改昵称</h3>
        </div>
        <div class="text-center text-sm text-slate-600">用户: <span id="mobile-nickname-username" class="font-semibold"></span></div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">当前昵称</label>
          <input type="text" id="mobile-current-nickname" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" readonly value="${
            currentNickname || "当前无昵称"
          }">
        </div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">新昵称</label>
          <input type="text" id="mobile-modify-new-nickname" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="请输入新昵称">
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileModifyNickname()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileModifyNickname()" class="flex-1 py-2 px-4 bg-teal-500 text-white rounded-lg text-sm">保存</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  window.currentMobileNicknameUsername = username;
  document.getElementById("mobile-nickname-username").textContent = username;
  document.getElementById("mobile-current-nickname").value =
    currentNickname || "未设置";
  // 使用新的 ID 清空输入框
  document.getElementById("mobile-modify-new-nickname").value = "";

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileModifyNickname() {
  const modal = document.getElementById("mobile-modify-nickname-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

async function submitMobileModifyNickname() {
  const username = window.currentMobileNicknameUsername;
  // 获取新的唯一 ID 的值
  const newNickname = document
    .getElementById("mobile-modify-new-nickname")
    .value.trim();

  logMessage_Info("提交新昵称: " + newNickname);

  if (!newNickname) {
    showModalAlert("请输入新昵称", "提示");
    return;
  }

  try {
    const response = await fetch("/auth/admin/update_user_nickname", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        username: username,
        nickname: newNickname,
      }),
    });

    const result = await response.json();
    if (result.success) {
      showModalAlert(`用户 ${username} 的昵称已更新`, "成功");
      closeMobileModifyNickname();
      loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"));
    } else {
      showModalAlert(result.message || "更新失败", "错误");
    }
  } catch (e) {
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

// 【移动端】管理员修改用户手机号
function showMobileAdminModifyPhone(username, currentPhone) {
  let modal = document.getElementById("mobile-admin-modify-phone-modal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "mobile-admin-modify-phone-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileAdminModifyPhone();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileAdminModifyPhone()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileAdminModifyPhone()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileAdminModifyPhone()">
          <svg class="w-6 h-6 text-teal-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
          </svg>
          <h3 class="text-xl font-bold text-teal-600 text-center">修改手机号</h3>
        </div>
        <div class="text-center text-sm text-slate-600">用户: <span id="mobile-admin-phone-username" class="font-semibold"></span></div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">当前手机号</label>
          <input type="tel" id="mobile-admin-phone-current" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-50" readonly>
        </div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">新手机号</label>
          <input type="tel" id="mobile-admin-phone-new" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="请输入新手机号" maxlength="11" inputmode="numeric">
        </div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">短信验证码（可选）</label>
          <div class="flex gap-2">
            <input type="text" id="mobile-admin-phone-code" class="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="验证码" maxlength="6" inputmode="numeric">
            <button id="mobile-admin-phone-send-btn" onclick="sendMobileAdminPhoneCode()" class="px-4 py-2 bg-sky-500 text-white rounded-lg text-sm whitespace-nowrap">发送</button>
          </div>
          <p class="text-xs text-slate-500 mt-1">管理员修改手机号不强制要求验证码，如填写将进行校验</p>
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileAdminModifyPhone()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileAdminModifyPhone()" class="flex-1 py-2 px-4 bg-teal-500 text-white rounded-lg text-sm">确认</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  window.currentMobileAdminPhoneUsername = username;
  document.getElementById("mobile-admin-phone-username").textContent = username;
  document.getElementById("mobile-admin-phone-current").value =
    currentPhone || "未绑定";
  _showPhoneLocationNearInput(document.getElementById("mobile-admin-phone-current"), currentPhone);
  document.getElementById("mobile-admin-phone-new").value = "";
  document.getElementById("mobile-admin-phone-code").value = "";

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileAdminModifyPhone() {
  const modal = document.getElementById("mobile-admin-modify-phone-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

let mobileAdminPhoneCooldown = 0;

async function sendMobileAdminPhoneCode() {
  // 检查冷却时间（虽然 openCaptchaModal 内部也会处理，但这里保留检查体验更好）
  if (mobileAdminPhoneCooldown > 0) {
    showModalAlert(`请等待 ${mobileAdminPhoneCooldown} 秒后再发送`, "提示");
    return;
  }

  const newPhone = document
    .getElementById("mobile-admin-phone-new")
    .value.trim();
  if (!newPhone || !/^1[3-9]\d{9}$/.test(newPhone)) {
    showModalAlert("请输入正确的手机号", "提示");
    return;
  }

  const sendBtn = document.getElementById("mobile-admin-phone-send-btn");
  const originalText = "发送"; // 或者 sendBtn.textContent

  // 不再直接 fetch，而是打开图形验证码模态框
  // 模态框确认后会自动调用后端接口，并携带 captcha_id 和 code
  openCaptchaModal({
    phone: newPhone,
    button: sendBtn,
    originalText: originalText,
    scene: "modify", // 场景标识，与后端对应
  });

  // 记录日志
  console.log("[管理员修改手机] 已打开图形验证码模态框");
}

async function submitMobileAdminModifyPhone() {
  const username = window.currentMobileAdminPhoneUsername;
  const newPhone = document
    .getElementById("mobile-admin-phone-new")
    .value.trim();
  const code = document.getElementById("mobile-admin-phone-code").value.trim();

  if (!newPhone) {
    showModalAlert("请输入新手机号", "提示");
    return;
  }

  if (!/^1[3-9]\d{9}$/.test(newPhone)) {
    showModalAlert("请输入正确的手机号格式", "提示");
    return;
  }

  try {
    const response = await fetch("/auth/admin/update_user_phone", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        username: username,
        pnew_phone: newPhone,
        sms_code: code || null,
      }),
    });

    const result = await response.json();
    if (result.success) {
      showModalAlert(`用户 ${username} 的手机号已更新`, "成功");
      closeMobileAdminModifyPhone();
      loadAdminUsers().then(() => copyAdminContentToMultiPanel("users"));
    } else {
      showModalAlert(result.message || "更新失败", "错误");
    }
  } catch (e) {
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

// 【移动端】重置密码
function showMobileResetPassword(username) {
  let modal = document.getElementById("mobile-reset-password-modal");
  if (!modal) {
    let password_input_id = document.getElementById("mobile-new-password_2");
    if (password_input_id) {
      password_input_id.value = "";
    }
    modal = document.createElement("div");
    modal.id = "mobile-reset-password-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileResetPassword();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileResetPassword()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[85vh] overflow-y-auto" onclick="event.stopPropagation()">
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileResetPassword()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileResetPassword()">
          <svg class="w-6 h-6 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
          </svg>
          <h3 class="text-xl font-bold text-purple-600 text-center">重置密码</h3>
        </div>
        <div class="text-center text-sm text-slate-600">用户: <span id="mobile-reset-password-username" class="font-semibold"></span></div>
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">新密码（至少6位）</label>
          <input type="password" id="mobile-new-password_2" class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" placeholder="请输入新密码">
        </div>
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileResetPassword()" class="flex-1 py-2 px-4 border border-slate-300 rounded-lg text-sm text-slate-600">取消</button>
          <button onclick="submitMobileResetPassword()" class="flex-1 py-2 px-4 bg-purple-500 text-white rounded-lg text-sm">确认重置</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  window.currentMobileResetPasswordUsername = username;
  document.getElementById("mobile-reset-password-username").textContent =
    username;
  document.getElementById("mobile-new-password").value = "";

  // [修正] 添加 show 类以触发显示动画
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
}

function closeMobileResetPassword() {
  const modal = document.getElementById("mobile-reset-password-modal");
  if (modal) {
    // [修正] 移除 show 类并等待动画结束
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

async function submitMobileResetPassword() {
  const username = window.currentMobileResetPasswordUsername;
  const newPassword = document.getElementById("mobile-new-password_2").value;

  if (!newPassword || newPassword.length < 6) {
    logMessage_Warning(
      "密码长度不足, 当前输入密码：" +
        newPassword +
        "， 长度：" +
        newPassword.length,
    );
    showModalAlert("密码长度至少为6个字符", "错误");
    return;
  }

  try {
    const response = await fetch("/auth/admin/force_reset_password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        target_username: username,
        new_password: newPassword,
      }),
    });

    const result = await response.json();
    if (result.success) {
      showModalAlert(`用户 ${username} 的密码已重置`, "成功");
      closeMobileResetPassword();
    } else {
      showModalAlert(result.message || "重置失败", "错误");
    }
  } catch (e) {
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

async function addMobileSelectedConfig() {
  const select = document.getElementById("mobile-multi-config-user-select");
  const user = select ? select.value : "";

  if (!user) {
    openManualAccountModal();
    return;
  }

  let passwordToUse = "";

  // 尝试从已登录的 school_accounts 获取密码 (参照 multi_addFromConfig)
  if (
    typeof sessionUUID !== "undefined" &&
    sessionUUID &&
    typeof currentAuthUsername !== "undefined" &&
    currentAuthUsername
  ) {
    try {
      const response = await fetch("/auth/get_user_school_accounts", {
        method: "GET",
        headers: {
          "X-Session-ID": sessionUUID,
        },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success && result.accounts) {
          const accountData = result.accounts[user];
          if (accountData) {
            if (typeof accountData === "string") {
              passwordToUse = accountData;
            } else if (
              typeof accountData === "object" &&
              accountData !== null
            ) {
              passwordToUse = accountData.password || "";
            }
          }
        }
      }
    } catch (error) {
      console.warn(
        `[移动端-添加配置] 无法加载 school_accounts: ${error.message}`,
      );
    }
  }

  try {
    const result = await callPythonAPI(
      "multi_add_account",
      user,
      passwordToUse,
    );

    if (
      result &&
      result.success === false &&
      result.action === "request_password"
    ) {
      showModalAlert(
        `账号 ${result.username} 缺少密码，请在弹窗中补全。`,
        "缺少密码",
      );
      // 打开手动添加模态框并预填用户名
      openManualAccountModal();
      setTimeout(() => {
        const uInput = document.getElementById("manual-account-username");
        const pInput = document.getElementById("manual-account-password");
        if (uInput) uInput.value = result.username;
        if (pInput) pInput.focus();
      }, 300);
    } else if (result && result.accounts) {
      renderMultiAccountList(result.accounts);
      showModalAlert("账号已添加", "成功");
    } else {
      showModalAlert(result?.message || "添加失败", "错误");
    }
  } catch (error) {
    console.error("[移动端] 添加配置失败:", error);
    showModalAlert("添加配置失败", "错误");
  }
}
async function addMobileAllConfigs() {
  const confirmed = await jsShowConfirm(
    "确认添加全部配置用户",
    "将把配置中的所有用户添加到多账号列表，是否继续？",
  );
  if (!confirmed) return;

  const confirmedAgain = await jsShowConfirm(
    "再次确认批量添加",
    "请再次确认：即将批量添加全部配置用户，并可能需要补充缺失密码。",
  );
  if (!confirmedAgain) return;

  try {
    showModalAlert("正在批量加载所有配置...", "提示");
    const result = await callPythonAPI("multi_load_accounts_from_config");

    if (result && result.accounts) {
      // 如果当前已登录，尝试从 school_accounts 同步密码和UA
      if (
        typeof sessionUUID !== "undefined" &&
        sessionUUID &&
        typeof currentAuthUsername !== "undefined" &&
        currentAuthUsername
      ) {
        try {
          const response = await fetch("/auth/get_user_school_accounts", {
            method: "GET",
            headers: {
              "X-Session-ID": sessionUUID,
            },
          });

          if (response.ok) {
            const schoolAccountsResult = await response.json();
            if (schoolAccountsResult.success && schoolAccountsResult.accounts) {
              const accountDataMap = schoolAccountsResult.accounts;
              let updatedCount = 0;
              result.accounts.forEach((account) => {
                if (account.username && accountDataMap[account.username]) {
                  const accountData = accountDataMap[account.username];
                  if (typeof accountData === "string") {
                    account.password = accountData;
                    updatedCount++;
                  } else if (
                    typeof accountData === "object" &&
                    accountData !== null
                  ) {
                    if (accountData.password) {
                      account.password = accountData.password;
                    }
                    if (accountData.ua) {
                      account.device_ua = accountData.ua;
                    }
                    updatedCount++;
                  }
                }
              });
              if (updatedCount > 0) {
                console.log(
                  `[移动端-批量添加] 已从 school_accounts 更新 ${updatedCount} 个账号的密码和UA`,
                );
              }
            }
          }
        } catch (error) {
          console.warn(
            `[移动端-批量添加] 无法加载 school_accounts: ${error.message}`,
          );
        }
      }
      renderMultiAccountList(result.accounts);
    }

    if (
      result &&
      result.accounts_missing_password &&
      result.accounts_missing_password.length > 0
    ) {
      // 交给统一的四阶段补密码流程（会询问是否补密码、支持勾选与逐个补全），
      // 不再用"如 xxx"这种只列一个的提示代替完整清单。
      if (typeof startMissingPasswordFlow === "function") {
        startMissingPasswordFlow(result.accounts_missing_password);
      } else {
        const missingCount = result.accounts_missing_password.length;
        showModalAlert(
          `批量添加完成。\n但有 ${missingCount} 个账号缺少密码。\n请使用"手动添加"功能补全密码。`,
          "提示",
        );
      }
    } else {
      showModalAlert("批量添加配置成功", "成功");
    }
  } catch (error) {
    console.error("[移动端] 批量添加配置失败:", error);
    showModalAlert("批量添加配置失败: " + error.message, "错误");
  }
}
function openManualAccountModal() {
  const modal = document.getElementById("mobile-manual-account-modal");
  if (!modal) {
    console.error("[移动端] 找不到手动账号输入模态框");
    return;
  }

  const usernameInput = document.getElementById("manual-account-username");
  const passwordInput = document.getElementById("manual-account-password");
  if (usernameInput) usernameInput.value = "";
  if (passwordInput) passwordInput.value = "";

  modal.classList.remove("hidden");
  modal.classList.add("show");

  setTimeout(() => {
    if (usernameInput) usernameInput.focus();
  }, 100);

  console.log("[移动端] 已打开手动账号输入模态框");
}
function closeManualAccountModal() {
  const modal = document.getElementById("mobile-manual-account-modal");
  if (!modal) {
    return;
  }
  modal.classList.add("hidden");
  modal.classList.remove("show");
  const usernameInput = document.getElementById("manual-account-username");
  const passwordInput = document.getElementById("manual-account-password");
  if (usernameInput) usernameInput.value = "";
  if (passwordInput) passwordInput.value = "";

  console.log("[移动端] 已关闭手动账号输入模态框");
}
async function confirmManualAccountAdd() {
  const usernameInput = document.getElementById("manual-account-username");
  const passwordInput = document.getElementById("manual-account-password");
  if (!usernameInput || !passwordInput) {
    showModalAlert("找不到输入框元素", "错误");
    return;
  }
  const username = usernameInput.value.trim();
  if (!username) {
    showModalAlert("请输入用户名", "错误");
    usernameInput.focus();
    return;
  }
  const password = passwordInput.value;
  if (!password) {
    showModalAlert("请输入密码", "错误");
    passwordInput.focus();
    return;
  }

  try {
    showModalAlert("正在添加账号...", "提示");
    // 参数必须用命名对象：传对象会让后端把它当 username 本身，
    // 直接返回"无效的用户名"。
    const result = await callPythonAPI("multi_add_account", {
      username: username,
      password: password,
      tag: undefined,
      params: {},
    });

    if (result && result.success === false && result.reason === "already_exists") {
      // 账号已存在且状态正常，不算添加成功
      showModalAlert(result.message || `账号 ${username} 已存在，未重复添加。`);
      closeManualAccountModal();
      await mobileRefreshMultiAccounts();
    } else if (
      result &&
      result.success === false &&
      result.reason === "account_running"
    ) {
      showModalAlert(
        result.message || "该账号正在执行任务，请先停止后再试。",
        "错误",
      );
    } else if (result && result.success) {
      showModalAlert("账号添加成功", "成功");
      closeManualAccountModal();
      await mobileRefreshMultiAccounts();
      console.log(`[移动端] 手动添加账号成功: ${username}`);
    } else {
      showModalAlert(`添加失败: ${result.message || "未知错误"}`, "错误");
      console.error(
        "[移动端] 手动添加账号失败:",
        createSafeClientLogValue(result),
      );
    }
  } catch (error) {
    console.error("[移动端] 手动添加账号异常:", error);
    showModalAlert("添加账号时发生错误", "错误");
  }
}
function importMobileAccountList() {
  try {
    // 之前这里调用 importMultiAccountList()，但该函数全项目未定义，
    // 因此按钮永远只弹"导入功能未实现"。统一委托桌面端同一个导入实现，
    // 提示也走同一套合并结果弹窗（multi_importFromExcel 内部会 input.click()）。
    if (typeof multi_importFromExcel === "function") {
      multi_importFromExcel();
    } else {
      showModalAlert("导入功能未实现", "错误");
      console.error("[移动端] multi_importFromExcel函数未定义");
    }
  } catch (error) {
    console.error("[移动端] 导入账号列表失败:", error);
    showModalAlert("导入失败: " + error.message, "错误");
  }
}
async function downloadMobileAccountTemplate() {
  try {
    if (typeof multi_downloadTemplate === "function") {
      await multi_downloadTemplate();
      showModalAlert("模板下载成功", "成功");
    } else {
      showModalAlert("下载模板功能未实现", "错误");
      console.error("[移动端] multi_downloadTemplate函数未定义");
    }
  } catch (error) {
    console.error("[移动端] 下载模板失败:", error);
    showModalAlert("下载模板失败: " + error.message, "错误");
  }
}
function exportMobileAccountList() {
  try {
    if (typeof exportMultiAccountList === "function") {
      exportMultiAccountList();
    } else {
      showModalAlert("导出功能未实现", "错误");
    }
  } catch (error) {
    console.error("[移动端] 导出账号列表失败:", error);
    showModalAlert("导出失败", "错误");
  }
}
/**
 * 刷新移动端选中的账号
 * 该函数会逐个刷新用户在移动端选择的账号，并更新它们的状态信息
 */
async function mobileRefreshSelectedAccounts() {
  try {
    // 1. 查找移动端账号列表中所有被选中的复选框
    const selected = document.querySelectorAll(
      '#mobile-multi-account-list input[type="checkbox"]:checked',
    );

    // 2. 检查是否有选中的账号，如果没有则提示用户并退出
    if (selected.length === 0) {
      showModalAlert("请先选择要刷新的账号", "错误");
      return;
    }

    // 3. 显示提示信息，告知用户正在刷新账号
    showModalAlert(`正在刷新 ${selected.length} 个账号...`, "提示");

    // 4. 从选中的复选框中提取对应的用户名列表
    // 遍历每个选中的复选框，找到其最近的带有 data-username 属性的父元素，并提取用户名
    const usernames = Array.from(selected)
      .map((checkbox) => {
        const item = checkbox.closest("[data-username]"); // 向上查找包含 data-username 属性的祖先元素
        return item ? item.dataset.username : null; // 提取 username，如果找不到则返回 null
      })
      .filter((u) => u); // 过滤掉 null 值，确保只保留有效的用户名

    // 5. 逐个刷新选中的账号
    // 使用 for...of 循环以确保按顺序执行异步操作
    for (const username of usernames) {
      try {
        // 5.1 找到该用户名对应的移动端账号列表项元素
        const item = document.getElementById(`mobile-multi-acc-${username}`);

        // 5.2 如果找到该元素，更新其状态文本为"刷新中..."（提供视觉反馈）
        if (item) {
          const statusEl = item.querySelector(".status-text"); // 查找状态文本显示元素
          if (statusEl) statusEl.textContent = "刷新中..."; // 更新显示为"刷新中..."
        }

        // 5.3 调用后端API刷新该账号的状态信息
        // 该API会重新获取账号的任务列表、完成情况等最新数据
        await callPythonAPI("multi_refresh_single_status", username);
      } catch (e) {
        // 5.4 如果某个账号刷新失败，记录错误日志但继续刷新其他账号（不中断流程）
        console.error(`刷新账号 ${username} 失败:`, e);
      }
    }

    // 6. 所有账号刷新完成后，显示成功提示
    showModalAlert("已刷新选中账号", "成功");
  } catch (error) {
    // 7. 如果整个刷新流程出现未预期的错误，记录错误日志并提示用户
    console.error("[移动端] 刷新选中账号失败:", error);
    showModalAlert("刷新失败", "错误");
  }
}
async function deleteMobileSelectedAccounts() {
  try {
    // 1. 获取移动端容器内的选中项
    const container = document.getElementById("mobile-multi-account-list");
    if (!container) return;

    const selectedCheckboxes = container.querySelectorAll(
      'input[type="checkbox"]:checked',
    );

    if (selectedCheckboxes.length === 0) {
      showModalAlert("请先选择要删除的账号", "错误");
      return;
    }

    // 2. 提取选中的用户名
    const selectedUsernames = Array.from(selectedCheckboxes).map(
      (cb) => cb.closest("[data-username]").dataset.username,
    );

    showMobileConfirm(
      "确认删除",
      `确定要删除选中的 ${selectedUsernames.length} 个账号吗？`,
      async () => {
        try {
          // 3. 直接调用后端API，不再通过 multi_removeSelected 代理
          const result = await callPythonAPI(
            "multi_remove_selected_accounts",
            selectedUsernames,
          );

          if (result && result.success) {
            showModalAlert("已删除选中账号", "成功");
            // 4. 更新UI列表 (renderMultiAccountList 会同时更新PC和移动端列表)
            if (result.accounts) {
              renderMultiAccountList(result.accounts);
            } else {
              await mobileRefreshMultiAccounts();
            }
          } else {
            showModalAlert(result?.message || "删除失败", "错误");
          }
        } catch (error) {
          console.error("[移动端] 删除选中账号失败:", error);
          showModalAlert("删除失败", "错误");
        }
      },
    );
  } catch (error) {
    console.error("[移动端] 删除选中账号失败:", error);
    showModalAlert("删除失败", "错误");
  }
}
async function deleteMobileAllAccounts() {
  try {
    showMobileConfirm(
      "确认删除",
      "确定要删除所有账号吗？此操作不可恢复！",
      async () => {
        try {
          if (typeof multi_removeAll === "function") {
            await multi_removeAll(true);
            showModalAlert("已删除所有账号", "成功");
            await mobileRefreshMultiAccounts();
          } else {
            showModalAlert("删除功能未实现", "错误");
          }
        } catch (error) {
          console.error("[移动端] 删除所有账号失败:", error);
          showModalAlert("删除失败", "错误");
        }
      },
    );
  } catch (error) {
    console.error("[移动端] 删除所有账号失败:", error);
    showModalAlert("删除失败", "错误");
  }
}
/**
 * saveMobileMultiGlobalSettings - 保存移动端多账号模式的全局设置
 *
 * 功能说明：
 * 1. 收集 mobile-multi-settings-panel 面板中所有带有 data-key 属性的输入元素
 * 2. 包括 mobile-multi-global-params-container 容器内的参数
 * 3. 包括自动签到设置区域 (mobile-multi-auto_attendance_*) 的参数
 * 4. 将收集到的参数通过 callPythonAPI('update_param', ...) 保存到 multi_global_params
 */
function saveMobileMultiGlobalSettings() {
  try {
    // 获取整个设置面板容器，以便收集所有参数（包括自动签到设置区域）
    const settingsPanel = document.getElementById(
      "mobile-multi-settings-panel",
    );
    // 同时获取原有的全局参数容器，用于向后兼容
    const container = document.getElementById(
      "mobile-multi-global-params-container",
    );

    // 如果两个容器都不存在，则显示错误提示并返回
    if (!settingsPanel && !container) {
      showModalAlert("找不到全局参数容器", "错误");
      return;
    }

    // 初始化参数对象，用于存储收集到的所有键值对
    const params = {};

    /**
     * collectInputs - 辅助函数，用于从指定容器中收集输入元素的值
     * @param {HTMLElement} containerEl - 要收集输入的容器元素
     *
     * 处理逻辑：
     * - checkbox 类型：获取 checked 布尔值
     * - number 类型：解析为浮点数，无效值默认为 0
     * - 其他类型：获取 value 字符串值
     */
    function collectInputs(containerEl) {
      // 如果容器不存在，直接返回
      if (!containerEl) return;
      // 遍历容器内所有的 input, select, textarea 元素
      containerEl
        .querySelectorAll("input, select, textarea")
        .forEach((input) => {
          // 获取 data-key 属性，这是参数的键名
          const key = input.dataset.key;
          // 如果没有 data-key 属性，跳过该元素
          if (!key) return;
          // 根据输入类型获取对应的值
          if (input.type === "checkbox") {
            // 复选框：获取 checked 状态（布尔值）
            params[key] = input.checked;
          } else if (input.type === "number") {
            // 数字输入框：解析为浮点数，无效值默认为 0
            params[key] = parseFloat(input.value) || 0;
          } else {
            // 其他类型（文本、选择框等）：获取字符串值
            params[key] = input.value;
          }
        });
    }

    // 从整个设置面板收集参数（包括自动签到设置区域）
    collectInputs(settingsPanel);
    // 从全局参数容器收集参数（保持向后兼容）
    collectInputs(container);

    // 检查 callPythonAPI 函数是否可用
    if (typeof callPythonAPI === "function") {
      // 遍历所有收集到的参数，逐个调用 API 保存
      Object.keys(params).forEach((key) => {
        callPythonAPI("update_param", key, params[key]);
      });
      // 显示保存成功提示
      showModalAlert("全局设置已保存", "成功");
      console.log(
        "[移动端] 全局参数已保存，参数数量:",
        Object.keys(params).length,
      );
    } else {
      // API 不可用时显示错误提示
      showModalAlert("API不可用", "错误");
    }
  } catch (error) {
    // 捕获并记录任何异常
    console.error("[移动端] 保存全局设置失败:", error);
    showModalAlert("保存失败", "错误");
  }
}
function clearMobileMultiLog() {
  try {
    const mobileLog = document.getElementById("mobile-multi-log-text");
    if (mobileLog) {
      mobileLog.value = "";
    }
    const pcLog = document.getElementById("multi-log-text");
    if (pcLog) {
      pcLog.value = "";
    }

    showModalAlert("日志已清空", "成功");
  } catch (error) {
    console.error("[移动端] 清空日志失败:", error);
    showModalAlert("清空日志失败", "错误");
  }
}
function scrollMobileMultiLogToBottom() {
  try {
    const mobileLog = document.getElementById("mobile-multi-log-text");
    if (mobileLog) {
      mobileLog.scrollTop = mobileLog.scrollHeight;
    }
  } catch (error) {
    console.error("[移动端] 滚动日志失败:", error);
  }
}
function syncMultiLogToMobile() {
  try {
    const pcLog = document.getElementById("multi-log-text");
    const mobileLog = document.getElementById("mobile-multi-log-text");
    if (pcLog && mobileLog) {
      if (pcLog.value !== mobileLog.value) {
        mobileLog.value = pcLog.value;
      }
    }
  } catch (error) {
    console.error("[移动端] 同步日志失败:", error);
  }
}
setInterval(syncMultiLogToMobile, 1000);

console.log("[移动端] Phase 4d功能已加载完成");
let currentHistoryTaskId = null;
async function openMobileHistoryModal(taskId, taskName) {
  currentHistoryTaskId = taskId;
  const modal = document.getElementById("mobile-history-modal");
  const taskNameEl = document.getElementById("mobile-history-task-name");
  const listContent = document.getElementById("mobile-history-list-content");
  if (!modal) return;
  modal.classList.remove("hidden");
  if (taskNameEl) {
    taskNameEl.textContent = taskName || "未知任务";
  }
  if (listContent) {
    listContent.innerHTML =
      '<p class="text-slate-400 text-center py-10">加载中...</p>';
  }
  try {
    const response = await fetch(`/api/history/${taskId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    if (!response.ok) {
      throw new Error("获取历史记录失败");
    }

    const data = await response.json();
    if (data && data.history && data.history.length > 0) {
      let html = "";
      data.history.forEach((record, index) => {
        const date = new Date(record.timestamp);
        const timeStr = date.toLocaleString("zh-CN");
        const distKm = (record.distance / 1000).toFixed(2);
        const minutes = Math.floor(record.duration / 60);
        const seconds = record.duration % 60;
        const durationStr = `${String(minutes).padStart(2, "0")}:${String(
          seconds,
        ).padStart(2, "0")}`;
        const statusColors = {
          completed: "green",
          failed: "red",
          partial: "orange",
        };
        const statusColor = statusColors[record.status] || "slate";
        const statusTexts = {
          completed: "已完成",
          failed: "失败",
          partial: "部分完成",
        };
        const statusText = statusTexts[record.status] || record.status;
        html += `
        <div class="p-3 bg-slate-50 rounded-lg border border-slate-200 cursor-pointer hover:bg-slate-100 transition"
          onclick="openMobileTrackModal(${escapeInlineJsArg(record.id)}, ${escapeInlineJsArg(record.task_id)})">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs text-slate-600">${timeStr}</span>
            <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-${statusColor}-100 text-${statusColor}-700">${statusText}</span>
          </div>
          <div class="grid grid-cols-3 gap-2 text-center">
            <div>
              <p class="text-xs text-slate-500">距离</p>
              <p class="font-bold text-sm text-blue-600">${distKm} km</p>
            </div>
            <div>
              <p class="text-xs text-slate-500">时长</p>
              <p class="font-bold text-sm text-green-600">${durationStr}</p>
            </div>
            <div>
              <p class="text-xs text-slate-500">配速</p>
              <p class="font-bold text-sm text-purple-600">${
                record.pace || "--:--"
              }</p>
            </div>
          </div>
        </div>
      `;
      });
      listContent.innerHTML = html;
    } else {
      listContent.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无历史记录</p>';
    }
  } catch (error) {
    console.error("加载历史记录失败:", error);
    if (listContent) {
      listContent.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${error.message}</p>`;
    }
  }
}
function closeMobileHistoryModal() {
  const modal = document.getElementById("mobile-history-modal");
  if (modal) {
    modal.classList.add("hidden");
  }
  currentHistoryTaskId = null;
}
let mobileTrackMapInstance = null;
let mobileTrackPolyline = null;
let mobileTrackMarkers = [];
async function openMobileTrackModal(recordId, taskId) {
  const modal = document.getElementById("mobile-track-modal");
  if (!modal) return;
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);
  await initMobileTrackMap();

  try {
    const response = await fetch(
      `/api/get_historical_track?task_id=${taskId}&record_id=${recordId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionUUID,
        },
      },
    );
    if (!response.ok) {
      throw new Error("获取路径数据失败");
    }
    const data = await response.json();
    const timeEl = document.getElementById("mobile-track-time");
    const distEl = document.getElementById("mobile-track-distance");
    const durEl = document.getElementById("mobile-track-duration");
    const paceEl = document.getElementById("mobile-track-pace");
    if (timeEl && data.timestamp) {
      const date = new Date(data.timestamp);
      timeEl.textContent = date.toLocaleString("zh-CN");
    }
    if (distEl && data.distance) {
      distEl.textContent = `${(data.distance / 1000).toFixed(2)} km`;
    }
    if (durEl && data.duration) {
      const min = Math.floor(data.duration / 60);
      const sec = data.duration % 60;
      durEl.textContent = `${String(min).padStart(2, "0")}:${String(
        sec,
      ).padStart(2, "0")}`;
    }
    if (paceEl && data.pace) {
      paceEl.textContent = data.pace;
    }
    if (getActiveMapProvider() !== "amap") {
      if (data.path && data.path.length > 0) {
        drawProviderRouteOnMap("mobile-track-map-container", data.path, {
          strokeColor: "#3b82f6",
          strokeWeight: 4,
          strokeOpacity: 0.8,
          showEndpoints: true,
        });
      }
    } else if (mobileTrackMapInstance && data.path && data.path.length > 0) {
      clearMobileTrackMap();
      const path = data.path.map((p) => new AMapInstance.LngLat(p[0], p[1]));
      mobileTrackPolyline = new AMapInstance.Polyline({
        path: path,
        strokeColor: "#3b82f6",
        strokeWeight: 4,
        strokeOpacity: 0.8,
        map: mobileTrackMapInstance,
      });
      if (path.length > 0) {
        const startMarker = new AMapInstance.Marker({
          position: path[0],
          icon: new AMapInstance.Icon({
            image:
              "data:image/svg+xml;base64," +
              btoa(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#22c55e" width="32" height="32"><circle cx="12" cy="12" r="10"/><text x="12" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="bold">起</text></svg>',
              ),
            size: new AMapInstance.Size(32, 32),
          }),
          map: mobileTrackMapInstance,
        });
        mobileTrackMarkers.push(startMarker);
      }
      if (path.length > 1) {
        const endMarker = new AMapInstance.Marker({
          position: path[path.length - 1],
          icon: new AMapInstance.Icon({
            image:
              "data:image/svg+xml;base64," +
              btoa(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#ef4444" width="32" height="32"><circle cx="12" cy="12" r="10"/><text x="12" y="16" text-anchor="middle" fill="white" font-size="12" font-weight="bold">终</text></svg>',
              ),
            size: new AMapInstance.Size(32, 32),
          }),
          map: mobileTrackMapInstance,
        });
        mobileTrackMarkers.push(endMarker);
      }
      if (data.checkpoints && data.checkpoints.length > 0) {
        data.checkpoints.forEach((cp, idx) => {
          const marker = new AMapInstance.Marker({
            position: new AMapInstance.LngLat(cp[0], cp[1]),
            icon: new AMapInstance.Icon({
              image:
                "data:image/svg+xml;base64," +
                btoa(
                  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f59e0b" width="28" height="28"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/><text x="12" y="12" text-anchor="middle" fill="white" font-size="8" font-weight="bold">${
                    idx + 1
                  }</text></svg>`,
                ),
              size: new AMapInstance.Size(28, 28),
            }),
            map: mobileTrackMapInstance,
          });
          mobileTrackMarkers.push(marker);
        });
      }
      mobileTrackMapInstance.setFitView();
    }
  } catch (error) {
    console.error("加载路径失败:", error);
    showModalAlert("加载路径失败: " + error.message, "错误");
  }
}
async function initMobileTrackMap() {
  if (getActiveMapProvider() !== "amap") {
    await ensureActiveMapProviderRuntimeIfNeeded("移动历史轨迹地图");
    initProviderMap("mobile-track-map-container", false);
    return;
  }
  if (mobileTrackMapInstance) return;
  if (!AMapInstance) {
    console.error("高德地图API未加载");
    return;
  }
  try {
    mobileTrackMapInstance = new AMapInstance.Map(
      "mobile-track-map-container",
      {
        viewMode: "2D",
        zoom: 15,
        center: [113.390342, 22.527403],
      },
    );
  } catch (error) {
    console.error("初始化路径地图失败:", error);
  }
}
function clearMobileTrackMap() {
  if (getActiveMapProvider() !== "amap") {
    clearProviderMapOverlays("mobile-track-map-container");
    return;
  }
  if (mobileTrackPolyline) {
    mobileTrackPolyline.setMap(null);
    mobileTrackPolyline = null;
  }
  mobileTrackMarkers.forEach((marker) => {
    marker.setMap(null);
  });
  mobileTrackMarkers = [];
}
function closeMobileTrackModal() {
  const modal = document.getElementById("mobile-track-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
  clearMobileTrackMap();
  if (mobileTrackMapInstance) {
    mobileTrackMapInstance.destroy();
    mobileTrackMapInstance = null;
  }
}
function mobileTrackZoomIn() {
  zoomProviderMap("mobile-track-map-container", 1);
}

function mobileTrackZoomOut() {
  zoomProviderMap("mobile-track-map-container", -1);
}

function mobileTrackFitView() {
  fitProviderMapToLastRoute("mobile-track-map-container");
}
let mobileMapAttendanceInstance = null;
let mobileMapAttendanceMarker = null;
let mobileMapAttendanceNoticeId = null;
let mobileMapAttendanceTarget = null;
let mobileMapAttendanceSelected = null;
async function openMobileMapAttendanceModal(noticeId, targetCoords) {
  console.log("[地图选点] 打开模态框", { noticeId, targetCoords });
  mobileMapAttendanceNoticeId = noticeId;
  mobileMapAttendanceTarget = targetCoords;
  mobileMapAttendanceSelected = null;
  const modal = document.getElementById("mobile-map-attendance-modal");
  if (!modal) {
    console.error("[地图选点] 模态框元素不存在");
    return;
  }
  modal.classList.remove("hidden");
  const coordsDisplay = document.getElementById("mobile-map-attendance-coords");
  const confirmBtn = document.getElementById(
    "mobile-map-attendance-confirm-btn",
  );
  if (coordsDisplay) coordsDisplay.textContent = "未选择";
  if (confirmBtn) confirmBtn.disabled = true;
  setTimeout(() => {
    initMobileMapAttendance(targetCoords);
  }, 300);
}
async function initMobileMapAttendance(targetCoords) {
  console.log("[地图选点] 初始化地图", targetCoords);
  if (mobileMapAttendanceInstance) {
    mobileMapAttendanceInstance.destroy();
    mobileMapAttendanceInstance = null;
  }
  if (getActiveMapProvider() !== "amap") {
    renderMapProviderFrontendPlaceholder("mobile-map-attendance-container", false);
    showModalAlert(
      `当前地图提供方为${getMapProviderDisplayName()}，暂不使用前端高德地图选点。`,
      "提示",
    );
    return;
  }
  if (typeof AMap === "undefined") {
    console.error("[地图选点] 高德地图API未加载");
    showModalAlert("地图加载失败，请刷新页面重试", "错误");
    return;
  }

  const container = document.getElementById("mobile-map-attendance-container");
  if (!container) {
    console.error("[地图选点] 地图容器不存在");
    return;
  }
  container.innerHTML = "";
  try {
    mobileMapAttendanceInstance = new AMap.Map(
      "mobile-map-attendance-container",
      {
        zoom: 17,
        center: targetCoords,
        mapStyle: "amap://styles/normal",
        showLabel: true,
        viewMode: "2D",
      },
    );
    console.log("[地图选点] 地图实例创建成功");
    const targetMarker = new AMap.Marker({
      position: targetCoords,
      icon: new AMap.Icon({
        size: new AMap.Size(32, 32),
        image:
          "data:image/svg+xml;base64," +
          btoa(`
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
          <circle cx="16" cy="16" r="14" fill="#3b82f6" stroke="white" stroke-width="3"/>
          <text x="16" y="21" text-anchor="middle" fill="white" font-size="18" font-weight="bold">🎯</text>
        </svg>
      `),
        imageSize: new AMap.Size(32, 32),
      }),
      title: "目标签到位置",
      zIndex: 100,
    });
    mobileMapAttendanceInstance.add(targetMarker);
    mobileMapAttendanceInstance.on("click", (e) => {
      const lng = e.lnglat.getLng();
      const lat = e.lnglat.getLat();
      console.log("[地图选点] 用户点击位置", { lng, lat });
      mobileMapAttendanceSelected = [lng, lat];
      const coordsDisplay = document.getElementById(
        "mobile-map-attendance-coords",
      );
      if (coordsDisplay) {
        coordsDisplay.textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
      }
      const confirmBtn = document.getElementById(
        "mobile-map-attendance-confirm-btn",
      );
      if (confirmBtn) {
        confirmBtn.disabled = false;
      }
      if (mobileMapAttendanceMarker) {
        mobileMapAttendanceInstance.remove(mobileMapAttendanceMarker);
      }
      mobileMapAttendanceMarker = new AMap.Marker({
        position: [lng, lat],
        icon: new AMap.Icon({
          size: new AMap.Size(40, 40),
          image:
            "data:image/svg+xml;base64," +
            btoa(`
          <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
            <circle cx="20" cy="20" r="18" fill="#ef4444" stroke="white" stroke-width="4"/>
            <text x="20" y="26" text-anchor="middle" fill="white" font-size="22" font-weight="bold">📍</text>
          </svg>
        `),
          imageSize: new AMap.Size(40, 40),
        }),
        title: "选中的签到位置",
        zIndex: 110,
      });
      mobileMapAttendanceInstance.add(mobileMapAttendanceMarker);
    });

    console.log("[地图选点] 地图初始化完成，等待用户选点");
  } catch (error) {
    console.error("[地图选点] 地图初始化失败", error);
    showModalAlert("地图初始化失败：" + error.message, "错误");
  }
}
async function confirmMobileMapAttendance() {
  console.log("[地图选点] 确认签到", {
    noticeId: mobileMapAttendanceNoticeId,
    selected: mobileMapAttendanceSelected,
  });
  if (!mobileMapAttendanceSelected) {
    showModalAlert("请先在地图上点击选择签到位置", "警告");
    return;
  }
  const confirmBtn = document.getElementById(
    "mobile-map-attendance-confirm-btn",
  );
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = '<span class="animate-pulse">签到中...</span>';
  }
  try {
    const result = await callPythonAPI("sign_in", {
      notice_id: mobileMapAttendanceNoticeId,
      longitude: mobileMapAttendanceSelected[0],
      latitude: mobileMapAttendanceSelected[1],
    });
    console.log(
      "[地图选点] 签到API返回",
      createSafeClientLogValue(result),
    );
    if (result.success) {
      showModalAlert("✅ 签到成功！", "成功");
      closeMobileMapAttendanceModal();
      setTimeout(() => {
        refreshNotificationsUI(true, true);
      }, 1000);
    } else {
      showModalAlert("❌ 签到失败：" + (result.message || "未知错误"), "错误");
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = `
        <span class="flex items-center justify-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          确认签到
        </span>
      `;
      }
    }
  } catch (error) {
    console.error("[地图选点] 签到失败", error);
    showModalAlert("签到失败：" + error.message, "错误");

    // 恢复按钮状态
    if (confirmBtn) {
      confirmBtn.disabled = false;
      confirmBtn.innerHTML = `
      <span class="flex items-center justify-center gap-2">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        确认签到
      </span>
    `;
    }
  }
}
function closeMobileMapAttendanceModal() {
  console.log("[地图选点] 关闭模态框");
  const modal = document.getElementById("mobile-map-attendance-modal");
  if (modal) {
    modal.classList.add("hidden");
  }
  if (mobileMapAttendanceMarker) {
    if (mobileMapAttendanceInstance) {
      mobileMapAttendanceInstance.remove(mobileMapAttendanceMarker);
    }
    mobileMapAttendanceMarker = null;
  }

  if (mobileMapAttendanceInstance) {
    mobileMapAttendanceInstance.destroy();
    mobileMapAttendanceInstance = null;
  }
  mobileMapAttendanceNoticeId = null;
  mobileMapAttendanceTarget = null;
  mobileMapAttendanceSelected = null;
}
let taskLongPressTimer = null;
let taskLongPressed = false;
function attachTaskTouchHandlers(taskItem, taskData) {
  if (!taskItem) return;
  taskItem.addEventListener("touchstart", (e) => {
    taskLongPressed = false;
    taskLongPressTimer = setTimeout(() => {
      taskLongPressed = true;
      if (navigator.vibrate) {
        navigator.vibrate(50);
      }
      openMobileHistoryModal(taskData.id, taskData.name);
    }, 500);
  });
  taskItem.addEventListener("touchmove", () => {
    if (taskLongPressTimer) {
      clearTimeout(taskLongPressTimer);
      taskLongPressTimer = null;
    }
  });
  taskItem.addEventListener("touchend", (e) => {
    if (taskLongPressTimer) {
      clearTimeout(taskLongPressTimer);
      taskLongPressTimer = null;
    }
    if (taskLongPressed) {
      e.preventDefault();
      return;
    }
    showMobileTaskDetails(taskData);
  });
  taskItem.addEventListener("touchcancel", () => {
    if (taskLongPressTimer) {
      clearTimeout(taskLongPressTimer);
      taskLongPressTimer = null;
    }
  });
}
function showMobileTaskDetails(taskData) {
  const modal = document.getElementById("mobile-task-details-modal");
  const content = document.getElementById("mobile-task-details-content");

  if (!modal || !content) return;
  let html = `
  <div class="space-y-3">
    <div class="flex items-center justify-between p-3 bg-sky-50 rounded-lg">
      <span class="text-sm text-slate-600">任务名称</span>
      <span class="font-semibold text-slate-800">${
        taskData.name || "未命名"
      }</span>
    </div>
    
    <div class="grid grid-cols-2 gap-2">
      <div class="p-3 bg-blue-50 rounded-lg text-center">
        <p class="text-xs text-slate-500 mb-1">距离</p>
        <p class="font-bold text-lg text-blue-600">${
          taskData.distance ? (taskData.distance / 1000).toFixed(2) : "--"
        } km</p>
      </div>
      <div class="p-3 bg-green-50 rounded-lg text-center">
        <p class="text-xs text-slate-500 mb-1">时长</p>
        <p class="font-bold text-lg text-green-600">${
          taskData.duration || "--:--"
        }</p>
      </div>
    </div>
    
    <div class="p-3 bg-slate-50 rounded-lg">
      <p class="text-xs text-slate-500 mb-1">状态</p>
      <p class="font-semibold text-slate-800">${taskData.status || "未知"}</p>
    </div>
    
    ${
      taskData.description
        ? `
    <div class="p-3 bg-slate-50 rounded-lg">
      <p class="text-xs text-slate-500 mb-1">描述</p>
      <p class="text-sm text-slate-700">${taskData.description}</p>
    </div>
    `
        : ""
    }
  </div>
`;

  content.innerHTML = html;

  modal.classList.remove("hidden");
}
function toggleMobileTaskDetails(show) {
  const modal = document.getElementById("mobile-task-details-modal");
  if (!modal) return;

  if (show) {
    modal.classList.remove("hidden");
  } else {
    modal.classList.add("hidden");
  }
}

console.log("[移动端] Phase 4c功能已加载");

// ============================================================
// 【Phase 5】移动端管理面板功能修复
// 修复IP封禁、短信配置、提醒面板、验证码面板等功能
// ============================================================

// =============================================
// 【1】移动端IP封禁面板专用函数
// =============================================

/**
 * 更新移动端IP封禁目标输入框的提示信息
 * 根据选择的封禁类型（单个IP或IP范围）动态更新占位符和提示
 */
function mobileUpdateBanTargetHint() {
  // 获取封禁类型选择框和目标输入框
  const banTypeSelect = document.getElementById("mobile-multi-ban-type");
  const banTargetInput = document.getElementById("mobile-multi-ban-target");
  const banTargetHint = document.getElementById("mobile-multi-ban-target-hint");

  // 如果元素不存在则直接返回
  if (!banTypeSelect || !banTargetInput || !banTargetHint) return;

  // 获取当前选择的封禁类型
  const type = banTypeSelect.value;

  // 根据封禁类型更新提示和占位符
  if (type === "ip") {
    // 单个IP模式
    banTargetInput.placeholder = "例如：192.168.1.1";
    banTargetHint.textContent = "示例: 192.168.1.1";
  } else if (type === "range") {
    // IP范围模式
    banTargetInput.placeholder = "例如：192.168.1.1-192.168.1.100";
    banTargetHint.textContent = "示例: 192.168.1.1-192.168.1.100";
  }

  // 输入框内容改变后清除之前的错误状态
  mobileValidateIPBanTarget();
}

/**
 * 验证移动端IP封禁目标的格式是否正确
 * @returns {boolean} 验证是否通过
 */
function mobileValidateIPBanTarget() {
  // 获取相关DOM元素
  const banTypeSelect = document.getElementById("mobile-multi-ban-type");
  const banTargetInput = document.getElementById("mobile-multi-ban-target");
  const banTargetError = document.getElementById(
    "mobile-multi-ban-target-error",
  );

  // 如果元素不存在则返回false
  if (!banTypeSelect || !banTargetInput || !banTargetError) {
    console.error("[移动端IP封禁] 无法找到DOM元素");
    return false;
  }

  // 获取封禁类型和目标值
  const type = banTypeSelect.value;
  const target = banTargetInput.value.trim();

  // IP地址正则表达式
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;

  // 如果目标为空，显示错误提示
  if (!target) {
    banTargetError.textContent = "封禁目标不能为空";
    banTargetError.classList.remove("hidden");
    banTargetInput.classList.add("border-red-500");
    return false;
  }

  // 验证单个IP格式
  if (type === "ip" && !ipRegex.test(target)) {
    banTargetError.textContent =
      "格式错误，请输入有效的IP地址（例如: 192.168.1.1）";
    banTargetError.classList.remove("hidden");
    banTargetInput.classList.add("border-red-500");
    return false;
  }

  // 验证IP范围格式
  if (type === "range") {
    const parts = target.split("-");
    if (
      parts.length !== 2 ||
      !ipRegex.test(parts[0].trim()) ||
      !ipRegex.test(parts[1].trim())
    ) {
      banTargetError.textContent =
        "格式错误，请输入有效的IP范围（例如: 192.168.1.1-192.168.1.100）";
      banTargetError.classList.remove("hidden");
      banTargetInput.classList.add("border-red-500");
      return false;
    }
  }

  // 验证通过，隐藏错误提示
  banTargetError.classList.add("hidden");
  banTargetInput.classList.remove("border-red-500");
  return true;
}

/**
 * 移动端添加IP封禁规则
 * 调用后端API添加新的IP封禁规则，并刷新列表
 */
async function mobileAddIPBan() {
  // 获取封禁类型用于生成更具体的错误消息
  const type = document.getElementById("mobile-multi-ban-type").value;
  const formatHint =
    type === "ip"
      ? "单个IP格式：192.168.1.1"
      : "IP范围格式：192.168.1.1-192.168.1.100";

  // 验证输入格式
  if (!mobileValidateIPBanTarget()) {
    showModalAlert(`输入格式不正确。${formatHint}`, "添加失败");
    return;
  }

  // 获取表单数据
  const target = document
    .getElementById("mobile-multi-ban-target")
    .value.trim();
  const scope = document.getElementById("mobile-multi-ban-scope").value;

  try {
    // 调用后端API添加封禁规则
    const response = await fetch("/api/admin/ip_bans", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ target, type, scope }),
    });

    const result = await response.json();
    if (result.success) {
      // 添加成功，显示提示并清空表单
      showModalAlert("封禁规则已添加", "成功");
      document.getElementById("mobile-multi-ban-target").value = "";

      // 清除错误提示状态
      const banTargetError = document.getElementById(
        "mobile-multi-ban-target-error",
      );
      const banTargetInput = document.getElementById("mobile-multi-ban-target");
      if (banTargetError) banTargetError.classList.add("hidden");
      if (banTargetInput) banTargetInput.classList.remove("border-red-500");

      // 刷新PC端和移动端的IP封禁列表
      loadIPBans();
      mobileRefreshIPBanList();
    } else {
      showModalAlert(result.message || "添加失败", "错误");
    }
  } catch (e) {
    console.error("[移动端IP封禁] 添加失败:", e);
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

/**
 * 刷新移动端IP封禁列表
 * 从后端加载最新的IP封禁规则并渲染到移动端界面
 */
async function mobileRefreshIPBanList() {
  // 获取移动端IP封禁列表容器
  const listEl = document.getElementById("mobile-multi-ip-ban-list");
  if (!listEl) {
    console.error("[移动端IP封禁] 找不到列表容器");
    return;
  }

  // 显示加载状态
  listEl.innerHTML =
    '<p class="text-slate-400 text-center py-6 text-xs">加载中...</p>';

  try {
    // 调用后端API获取IP封禁列表
    const response = await fetch("/api/admin/ip_bans", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    // 渲染IP封禁列表
    if (result.success && result.bans && result.bans.length > 0) {
      listEl.innerHTML = result.bans
        .map(
          (ban) => `
            <div class="bg-white border border-slate-200 rounded-lg p-3 flex justify-between items-center">
              <div class="flex-1">
                <span class="font-semibold text-sm text-slate-800">${escapeHtml(
                  ban.target,
                )}</span>
                <div class="flex gap-2 mt-1">
                  <span class="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">${
                    ban.type === "ip" ? "单个IP" : "IP范围"
                  }</span>
                  <span class="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">${
                    ban.scope === "all" ? "全部功能" : "仅留言板"
                  }</span>
                </div>
              </div>
              <button
                onclick="mobileRemoveIPBan(${escapeInlineJsArg(ban.id)})"
                class="btn btn-danger !py-1 !px-3 text-xs min-h-[36px]"
              >
                删除
              </button>
            </div>
          `,
        )
        .join("");
    } else {
      // 没有封禁规则时显示提示
      listEl.innerHTML =
        '<p class="text-slate-400 text-center py-6 text-xs">暂无封禁规则</p>';
    }

    console.log("[移动端IP封禁] 列表已刷新");
  } catch (e) {
    console.error("[移动端IP封禁] 加载失败:", e);
    listEl.innerHTML = `<p class="text-red-500 text-center py-6 text-xs">加载失败: ${e.message}</p>`;
  }
}

/**
 * 移动端删除IP封禁规则
 * @param {string} banId - 要删除的封禁规则ID
 */
async function mobileRemoveIPBan(banId) {
  // 显示确认对话框
  const confirmed = await jsShowConfirm("确认删除", "确定要删除此封禁规则吗？");
  if (!confirmed) return;

  try {
    // 调用后端API删除封禁规则
    const response = await fetch(`/api/admin/ip_bans/${banId}`, {
      method: "DELETE",
      headers: { "X-Session-ID": sessionUUID },
    });

    const result = await response.json();
    if (result.success) {
      showModalAlert("封禁规则已删除", "成功");
      // 刷新PC端和移动端的IP封禁列表
      loadIPBans();
      mobileRefreshIPBanList();
    } else {
      showModalAlert(result.message || "删除失败", "错误");
    }
  } catch (e) {
    console.error("[移动端IP封禁] 删除失败:", e);
    showModalAlert("操作失败: " + e.message, "错误");
  }
}

/**
 * 移动端异步确认对话框（返回Promise）
 * @param {string} title - 对话框标题
 * @param {string} message - 对话框消息
 * @returns {Promise<boolean>} 用户是否确认
 */
function showMobileConfirmAsync(title, message) {
  return new Promise((resolve) => {
    // 优先使用Swal如果可用
    if (typeof Swal !== "undefined") {
      Swal.fire({
        title: title,
        text: message,
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "确认",
        cancelButtonText: "取消",
        confirmButtonColor: "#ef4444",
        cancelButtonColor: "#64748b",
      }).then((result) => {
        resolve(result.isConfirmed);
      });
    } else {
      // 回退到原生confirm
      resolve(confirm(`${title}\n${message}`));
    }
  });
}

// =============================================
// 【2】移动端短信配置面板专用函数
// =============================================

/**
 * 加载移动端短信配置面板
 * 从后端获取配置并填充到移动端表单
 */
async function mobileLoadSMSConfig() {
  // 获取移动端短信配置内容容器
  const contentEl = document.getElementById("mobile-multi-admin-sms-content");
  if (!contentEl) {
    console.error("[移动端短信配置] 找不到内容容器");
    return;
  }

  // 显示加载状态
  contentEl.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  try {
    // 调用后端API获取短信配置
    const response = await fetch("/api/admin/sms/config", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (result.success) {
      const config = result.config;
      // 渲染移动端短信配置表单
      contentEl.innerHTML = `
        <!-- 短信服务主开关 -->
        <div class="bg-white border border-slate-200 rounded-lg p-3">
          <div class="flex items-center justify-between">
            <div>
              <h5 class="font-semibold text-sm text-slate-800">启用短信服务</h5>
              <p class="text-xs text-slate-500">开启后可使用短信验证功能</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" id="mobile-sms-enabled" class="sr-only peer" ${
                config.enable_sms_service ? "checked" : ""
              } onchange="mobileHandleSmsMainSwitch()">
              <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>

        <!-- 功能开关组 -->
        <div class="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-3">
          <h5 class="font-semibold text-xs text-slate-700">功能开关</h5>
          
          <div class="flex items-center justify-between py-2 border-b border-slate-100">
            <span class="text-xs text-slate-600">允许手机号绑定/修改</span>
            <input type="checkbox" id="mobile-sms-enable-phone-modification" class="w-4 h-4 rounded" ${
              config.enable_phone_modification ? "checked" : ""
            }>
          </div>
          
          <div class="flex items-center justify-between py-2 border-b border-slate-100">
            <span class="text-xs text-slate-600">允许手机号登录</span>
            <input type="checkbox" id="mobile-sms-enable-phone-login" class="w-4 h-4 rounded" ${
              config.enable_phone_login ? "checked" : ""
            }>
          </div>
          
          <div class="flex items-center justify-between py-2">
            <span class="text-xs text-slate-600">注册时强制手机验证</span>
            <input type="checkbox" id="mobile-sms-enable-phone-registration-verify" class="w-4 h-4 rounded" ${
              config.enable_phone_registration_verify ? "checked" : ""
            }>
          </div>
        </div>

        <!-- API配置 -->
        <div class="bg-white border border-slate-200 rounded-lg p-3 space-y-3">
          <h5 class="font-semibold text-xs text-slate-700">API配置</h5>
          
          <div>
            <label class="block text-xs text-slate-600 mb-1">用户名/账号</label>
            <input type="text" id="mobile-sms-username" value="${
              config.username || ""
            }" class="input-field text-xs w-full" placeholder="短信服务商账号">
          </div>
          
          <div>
            <label class="block text-xs text-slate-600 mb-1">API Key</label>
            <input type="password" id="mobile-sms-apikey" value="${
              config.api_key || ""
            }" class="input-field text-xs w-full" placeholder="短信服务商API密钥">
          </div>
          
          <div>
            <label class="block text-xs text-slate-600 mb-1">签名</label>
            <div class="flex items-center gap-2">
              <span class="text-sm text-slate-500">【</span>
              <input type="text" id="mobile-sms-signature" value="${getSmsSignatureInnerValue(config.signature || "")}" class="input-field text-xs w-full" placeholder="短信签名主体">
              <span class="text-sm text-slate-500">】</span>
            </div>
          </div>
          
          <div>
            <label class="block text-xs text-slate-600 mb-1">模板ID</label>
            <input type="text" id="mobile-sms-template" value="${
              config.template_register || ""
            }" class="input-field text-xs w-full" placeholder="验证码模板ID">
          </div>
        </div>

        <!-- 限制配置 -->
        <div class="bg-white border border-slate-200 rounded-lg p-3 space-y-3">
          <h5 class="font-semibold text-xs text-slate-700">安全限制</h5>
          
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-slate-600 mb-1">验证码有效期(分钟)</label>
              <input type="number" id="mobile-sms-code-expire" value="${
                config.code_expire_minutes || 5
              }" class="input-field text-xs w-full" min="1" max="30">
            </div>
            <div>
              <label class="block text-xs text-slate-600 mb-1">账号日限额</label>
              <input type="number" id="mobile-sms-limit-account" value="${
                config.rate_limit_per_account_day || 10
              }" class="input-field text-xs w-full" min="1">
            </div>
            <div>
              <label class="block text-xs text-slate-600 mb-1">IP日限额</label>
              <input type="number" id="mobile-sms-limit-ip" value="${
                config.rate_limit_per_ip_day || 20
              }" class="input-field text-xs w-full" min="1">
            </div>
            <div>
              <label class="block text-xs text-slate-600 mb-1">手机号日限额</label>
              <input type="number" id="mobile-sms-limit-phone" value="${
                config.rate_limit_per_phone_day || 5
              }" class="input-field text-xs w-full" min="1">
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="flex flex-col gap-2">
          <div class="flex gap-2">
              <button onclick="mobileSaveSMSConfig()" class="btn btn-primary flex-1 !py-2 text-sm min-h-[44px]">
                💾 保存配置
              </button>
              <button onclick="mobileCheckSMSBalance()" class="btn btn-ghost border border-slate-300 flex-1 !py-2 text-sm min-h-[44px]">
                💰 查询余额
              </button>
          </div>
          
          <div class="flex gap-2">
              <button onclick="openSMSHistoryModal()" class="btn btn-ghost border border-slate-300 flex-1 !py-2 text-sm min-h-[44px]">
                📋 发送历史
              </button>
              <button onclick="openMobileVerificationCodesModal()" class="btn btn-ghost border border-slate-300 flex-1 !py-2 text-sm min-h-[44px]">
                🔑 验证码管理
              </button>
          </div>
          
          <button onclick="openSMSTestModal()" class="btn btn-success w-full !py-2 text-sm min-h-[44px]">
            🧪 测试发送
          </button>
        </div>
      `;

      bindSmsSignatureInputSanitization(document.getElementById("mobile-sms-signature"));
      console.log("[移动端短信配置] 配置已加载");
    } else {
      contentEl.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${
        result.message || "未知错误"
      }</p>`;
    }
  } catch (e) {
    console.error("[移动端短信配置] 加载失败:", e);
    contentEl.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${e.message}</p>`;
  }
}

/**
 * 移动端短信服务主开关变更处理
 * 当主开关关闭时，同时关闭所有子功能开关
 */
function mobileHandleSmsMainSwitch() {
  const mainSwitch = document.getElementById("mobile-sms-enabled");
  if (!mainSwitch) return;

  // 如果主开关关闭，同时关闭所有子功能
  if (!mainSwitch.checked) {
    const phoneModification = document.getElementById(
      "mobile-sms-enable-phone-modification",
    );
    const phoneLogin = document.getElementById("mobile-sms-enable-phone-login");
    const phoneRegistrationVerify = document.getElementById(
      "mobile-sms-enable-phone-registration-verify",
    );

    if (phoneModification) phoneModification.checked = false;
    if (phoneLogin) phoneLogin.checked = false;
    if (phoneRegistrationVerify) phoneRegistrationVerify.checked = false;
  }
}

/**
 * 保存移动端短信配置
 */
async function mobileSaveSMSConfig() {
  // 收集表单数据
  const config = {
    enable_sms_service:
      document.getElementById("mobile-sms-enabled")?.checked || false,
    enable_phone_modification:
      document.getElementById("mobile-sms-enable-phone-modification")
        ?.checked || false,
    enable_phone_login:
      document.getElementById("mobile-sms-enable-phone-login")?.checked ||
      false,
    enable_phone_registration_verify:
      document.getElementById("mobile-sms-enable-phone-registration-verify")
        ?.checked || false,
    username:
      document.getElementById("mobile-sms-username")?.value.trim() || "",
    api_key: document.getElementById("mobile-sms-apikey")?.value.trim() || "",
    signature: normalizeSmsSignature(
      document.getElementById("mobile-sms-signature")?.value,
    ),
    template_register:
      document.getElementById("mobile-sms-template")?.value.trim() || "",
    code_expire_minutes:
      parseInt(document.getElementById("mobile-sms-code-expire")?.value) || 5,
    rate_limit_per_account_day:
      parseInt(document.getElementById("mobile-sms-limit-account")?.value) ||
      10,
    rate_limit_per_ip_day:
      parseInt(document.getElementById("mobile-sms-limit-ip")?.value) || 20,
    rate_limit_per_phone_day:
      parseInt(document.getElementById("mobile-sms-limit-phone")?.value) || 5,
  };

  try {
    // 调用后端API保存配置
    const response = await fetch("/api/admin/sms/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(config),
    });
    const result = await response.json();

    if (result.success) {
      showModalAlert("短信配置已保存", "成功");
      // 同步更新PC端配置（如果存在）
      if (typeof loadSMSConfig === "function") {
        loadSMSConfig();
      }
    } else {
      showModalAlert(result.message || "保存失败", "错误");
    }
  } catch (e) {
    console.error("[移动端短信配置] 保存失败:", e);
    showModalAlert("保存失败: " + e.message, "错误");
  }
}

/**
 * 移动端查询短信余额
 */
async function mobileCheckSMSBalance() {
  try {
    showModalAlert("正在查询余额...", "提示");

    const response = await fetch("/api/admin/sms/check_balance", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (result.success) {
      showModalAlert(`当前余额: ${result.balance || "未知"} 条`, "余额查询");
    } else {
      showModalAlert(result.message || "查询失败", "错误");
    }
  } catch (e) {
    console.error("[移动端短信配置] 查询余额失败:", e);
    showModalAlert("查询失败: " + e.message, "错误");
  }
}

// =============================================
// 【3】移动端验证码面板专用函数
// =============================================

/**
 * 加载移动端验证码设置
 * 从缓存或API获取验证码配置参数
 */
/**
 * 加载验证码配置参数（移动端）
 * 从后端 /api/captcha/config API 获取验证码配置参数并填充到移动端表单中
 *
 * 功能说明：
 * - 调用 /api/captcha/config API 获取最新的验证码配置
 * - 将获取到的配置值填充到移动端的三个输入框中
 * - 提供友好的错误提示和日志记录
 * - 与PC端的loadCaptchaSettings()功能平行，但适配移动端UI
 *
 * 涉及的表单字段：
 * - mobile-captcha-length: 验证码字符长度（3-6）
 * - mobile-captcha-scale-factor: 图像缩放因子（2-4）
 * - mobile-captcha-noise-level: 噪声级别（0.0-0.3）
 *
 * @returns {Promise<void>} 无返回值
 */
async function mobileLoadCaptchaSettings(showAlert = true) {
  try {
    // 步骤1：记录开始加载的日志，便于调试和追踪
    console.log("[移动端验证码] 开始从 /api/captcha/config 加载验证码配置...");

    // 步骤2：调用后端API获取验证码配置
    // 使用fetch进行HTTP GET请求
    const response = await fetch("/api/captcha/config", {
      method: "GET", // 使用GET方法获取数据
      headers: {
        // 发送Session ID用于身份验证，确保只有已登录的管理员可以访问
        "X-Session-ID": sessionUUID,
        // 指定期望的响应内容类型为JSON
        "Content-Type": "application/json",
      },
      // 包含cookie凭证，确保会话状态正确传递
      credentials: "include",
    });

    // 步骤3：解析响应的JSON数据
    // await确保等待JSON解析完成
    const result = await response.json();

    // 步骤4：检查API调用是否成功
    // result.success 表示后端是否成功返回了配置数据
    // result.config 包含实际的配置参数对象
    if (result && result.success && result.config) {
      // 步骤5：从返回的config对象中提取配置参数
      const settings = result.config;

      // 步骤6：调用辅助函数更新移动端表单
      // mobileUpdateCaptchaForm 会处理实际的DOM更新操作
      mobileUpdateCaptchaForm(settings);

      // 只记录加载状态，避免把验证码服务配置写入控制台。
      console.log("[移动端验证码] 已从 /api/captcha/config 加载配置");

      // 步骤8：显示成功提示（使用移动端专用的提示函数）
      // showModalAlert是移动端使用的提示函数，比Swal更适合移动设备
      if (showAlert){
        showModalAlert("验证码配置已加载", "成功");}
    } else {
      // 步骤9：处理API返回成功但没有配置数据的情况
      // 这通常表示配置文件不存在或格式错误
      console.warn("[移动端验证码] API返回成功但未包含配置数据，使用默认值");

      // 步骤10：使用默认配置对象更新表单
      mobileUpdateCaptchaForm({
        ...DEFAULT_CAPTCHA_PROVIDER_SETTINGS,
        length: 4, // 默认长度4个字符
        scale_factor: 2, // 默认缩放因子2倍
        noise_level: 0.08, // 默认噪点比例8%
      });

      // 步骤11：显示警告提示，告知用户正在使用默认值
      if (showAlert) {
        showModalAlert("未找到配置文件，已加载默认值", "警告");
      }
    }
  } catch (error) {
    // 步骤12：捕获并处理所有可能的异常（网络错误、解析错误等）
    // 记录详细的错误日志，包含错误对象的完整信息
    console.error("[移动端验证码] 从 /api/captcha/config 加载配置失败:", error);

    // 步骤13：在发生错误时，仍然提供默认值，确保用户可以继续使用
    mobileUpdateCaptchaForm({
      ...DEFAULT_CAPTCHA_PROVIDER_SETTINGS,
      length: 4, // 默认长度
      scale_factor: 2, // 默认缩放因子
      noise_level: 0.08, // 默认噪点比例
    });

    // 步骤14：显示友好的错误提示给用户
    // 包含具体的错误原因，帮助用户理解问题所在
    showModalAlert("加载验证码配置失败: " + error.message, "错误");
  }
}

/**
 * 更新移动端验证码表单
 * 这是一个辅助函数，用于将验证码配置参数填充到移动端的表单输入框中
 *
 * 功能说明：
 * - 接收一个配置对象（包含length、scale_factor、noise_level）
 * - 查找移动端的三个输入框元素
 * - 将配置值填充到对应的输入框中
 * - 如果输入框不存在，则跳过（安全性检查）
 *
 * 设计模式：
 * - 使用可选链操作符(?.)确保在元素不存在时不会抛出错误
 * - 使用逻辑或(||)运算符提供默认值
 * - 将UI更新逻辑与数据获取逻辑分离，提高代码可维护性
 *
 * @param {Object} settings - 验证码配置对象
 * @param {number} settings.length - 验证码字符长度（3-6）
 * @param {number} settings.scale_factor - 图像缩放因子（2-4）
 * @param {number} settings.noise_level - 噪声级别（0.0-0.3）
 */
function mobileUpdateCaptchaForm(settings) {
  // 步骤1：获取移动端验证码长度输入框的DOM元素引用
  // 使用document.getElementById根据元素ID获取元素
  const lengthInput = document.getElementById("mobile-captcha-length");

  // 步骤2：获取移动端细分倍数（缩放因子）输入框的DOM元素引用
  const scaleInput = document.getElementById("mobile-captcha-scale-factor");

  // 步骤3：获取移动端噪点比例（噪声级别）输入框的DOM元素引用
  const noiseInput = document.getElementById("mobile-captcha-noise-level");

  // 步骤4：填充验证码长度输入框
  // 【修复】使用 !== undefined 判断，正确区分"值为0"和"未设置"
  // 原代码：settings.length || 4 会将0误判为falsy值
  // 新代码：只有在undefined时才使用默认值4
  // 使用if检查确保元素存在，避免在元素不存在时产生错误
  if (lengthInput)
    lengthInput.value = settings.length !== undefined ? settings.length : 4;

  // 步骤5：填充细分倍数输入框
  // 【修复】使用 !== undefined 判断，正确区分"值为0"和"未设置"
  // 原代码：settings.scale_factor || 2 可能将0误判为falsy值（虽然scale_factor不太可能为0）
  // 如果scaleInput存在，则将其value属性设置为settings.scale_factor或默认值2
  if (scaleInput)
    scaleInput.value =
      settings.scale_factor !== undefined ? settings.scale_factor : 2;

  // 步骤6：填充噪点比例输入框
  // 【修复】使用 !== undefined 判断，正确区分"值为0.0"和"未设置"
  // ⚠️ 关键修复：当noise_level为0.0时，原代码 settings.noise_level || 0.08 会错误地返回0.08
  // 因为JavaScript中0.0是falsy值，|| 运算符会跳过它并使用默认值
  // 新代码：只有在noise_level === undefined时才使用默认值0.08，允许用户设置0.0
  // 如果noiseInput存在，则将其value属性设置为settings.noise_level或默认值0.08
  if (noiseInput)
    noiseInput.value =
      settings.noise_level !== undefined ? settings.noise_level : 0.08;
  applyCaptchaProviderSettings(settings, "mobile-");
}

/**
 * 保存移动端验证码设置
 */
async function mobileSaveCaptchaSettings() {
  try {
    console.log("[移动端验证码] 开始保存验证码配置...");

    // 获取表单数据
    const length = parseInt(
      document.getElementById("mobile-captcha-length")?.value,
    );
    const scale_factor = parseInt(
      document.getElementById("mobile-captcha-scale-factor")?.value,
    );
    const noise_level = parseFloat(
      document.getElementById("mobile-captcha-noise-level")?.value,
    );

    // 参数验证
    if (isNaN(length) || length < 3 || length > 6) {
      showModalAlert("验证码长度必须在3-6之间", "参数错误");
      return;
    }
    if (isNaN(scale_factor) || scale_factor < 2 || scale_factor > 32) {
      showModalAlert("细分倍数必须在2-32之间", "参数错误");
      return;
    }
    if (isNaN(noise_level) || noise_level < 0 || noise_level > 0.3) {
      showModalAlert("噪点比例必须在0.00-0.30之间", "参数错误");
      return;
    }
    const providerConfig = readCaptchaProviderForm("mobile-");
    if (providerConfig.provider === "behavior" && !providerConfig.behavior_base_url) {
      showModalAlert("选择验证码服务器时，服务地址不能为空", "参数错误");
      return;
    }

    // 调用后端API保存配置 - 使用正确的 API 端点 /api/captcha/save_settings
    const result = await callPythonAPI_raw(
      "/api/captcha/save_settings",
      "POST",
      {
        length: length,
        scale_factor: scale_factor,
        noise_level: noise_level,
        ...providerConfig,
      },
    );

    if (result && result.success) {
      showModalAlert("验证码设置已保存", "成功");
      // 同步更新PC端表单（如果存在）
      const pcLength = document.getElementById("captcha-length");
      const pcScale = document.getElementById("captcha-scale-factor");
      const pcNoise = document.getElementById("captcha-noise-level");
      if (pcLength) pcLength.value = length;
      if (pcScale) pcScale.value = scale_factor;
      if (pcNoise) pcNoise.value = noise_level;
      applyCaptchaProviderSettings(providerConfig, "");
      setRuntimeCaptchaProviderConfig(providerConfig);
    } else {
      showModalAlert(result?.message || "保存失败", "错误");
    }
  } catch (error) {
    console.error("[移动端验证码] 保存失败:", error);
    showModalAlert("保存验证码设置失败: " + error.message, "错误");
  }
}

/**
 * 移动端测试验证码生成
 */
async function mobileTestCaptcha() {
  // UI反馈：禁用按钮并显示加载状态
  try {
    const testCaptchaBtnEl = $("mobile-test-captcha-btn");
    if (testCaptchaBtnEl) {
      testCaptchaBtnEl.classList.add("btn-loading");
      testCaptchaBtnEl.setAttribute("disabled", "disabled");
    }
  } catch (e) {
    console.error("设置测试按钮加载状态失败:", e);
  }

  try {
    console.log("[移动端验证码] 测试生成验证码...");
    const providerConfig = readCaptchaProviderForm("mobile-");
    if (providerConfig.provider === "behavior" && !providerConfig.behavior_base_url) {
      Swal.fire({
        icon: "error",
        title: "参数错误",
        text: "选择验证码服务器时，服务地址不能为空",
      });
      return;
    }

    // 获取当前表单配置
    const length =
      parseInt(document.getElementById("mobile-captcha-length")?.value) || 4;
    const scale_factor =
      parseInt(document.getElementById("mobile-captcha-scale-factor")?.value) ||
      2;
    const noise_level =
      parseFloat(
        document.getElementById("mobile-captcha-noise-level")?.value,
      ) || 0.08;

    if (providerConfig.provider !== "behavior") {
      if (isNaN(length) || length < 3 || length > 6) {
        Swal.fire({
          icon: "error",
          title: "参数错误",
          text: "验证码长度必须在3-6之间",
        });
        return;
      }
      if (isNaN(scale_factor) || scale_factor < 2 || scale_factor > 32) {
        Swal.fire({
          icon: "error",
          title: "参数错误",
          text: "细分倍数必须在2-32之间",
        });
        return;
      }
      if (isNaN(noise_level) || noise_level < 0 || noise_level > 0.3) {
        Swal.fire({
          icon: "error",
          title: "参数错误",
          text: "噪点比例必须在0.0-0.3之间",
        });
        return;
      }
    }

    Background_width =
      document.getElementById("mobile-multi-admin-captcha-panel").clientWidth -
      35;

    // 调用后端API生成验证码 - 使用正确的 API 端点 /api/captcha/test_generate
    const response = await fetch("/api/captcha/test_generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      credentials: "include",
      body: JSON.stringify({
        length,
        scale_factor,
        noise_level,
        weight: Background_width,
        ...providerConfig,
      }),
    });

    const result = await response.json();

    // 显示预览区域
    const previewContainer = document.getElementById(
      "mobile-captcha-test-preview",
    );
    const previewDisplay = document.getElementById(
      "mobile-captcha-preview-display",
    );
    const previewAnswer = document.getElementById(
      "mobile-captcha-preview-answer",
    );

    if (previewContainer && previewDisplay && previewAnswer) {
      previewContainer.classList.remove("hidden");

      console.log("[移动端验证码] 测试生成响应已收到");

      // 检查后端返回结果是否成功
      if (result && result.success) {
        if (result.provider === "behavior") {
          console.log("[移动端验证码] 验证码服务器测试生成成功");
        }
        renderCaptchaTestPreview(result, "mobile-");
      } else {
        // 后端返回失败或结果无效，显示错误信息
        previewDisplay.innerHTML = `<p class="text-red-500 text-xs">生成失败: ${
          result?.message || "未知错误"
        }</p>`;
        previewAnswer.textContent = "-";
      }
    }
  } catch (error) {
    console.error("[移动端验证码] 测试失败:", error);
    showModalAlert("生成验证码失败: " + error.message, "错误");
  } finally {
    try {
      const testCaptchaBtnEl = $("mobile-test-captcha-btn");
      if (testCaptchaBtnEl) {
        testCaptchaBtnEl.classList.remove("btn-loading");
        testCaptchaBtnEl.removeAttribute("disabled");
      }
    } catch (e) {
      console.error("恢复测试按钮状态失败:", e);
    }
  }
}

// 切换移动端验证码面板视图 (设置 <-> 历史)
function toggleMobileCaptchaView(view) {
  const settingsView = document.getElementById("mobile-captcha-settings-view");
  const historyView = document.getElementById("mobile-captcha-history-view");

  if (view === "history") {
    if (settingsView) settingsView.classList.add("hidden");
    if (historyView) {
      historyView.classList.remove("hidden");
      // 初始化日期
      const dateInput = document.getElementById("mobile-captcha-date");
      if (dateInput && !dateInput.value) {
        dateInput.value = new Date().toISOString().split("T")[0];
      }
      mobileLoadCaptchaHistory();
    }
  } else {
    if (historyView) historyView.classList.add("hidden");
    if (settingsView) settingsView.classList.remove("hidden");
  }
}

// 加载移动端验证码历史
async function mobileLoadCaptchaHistory() {
  const listContainer = document.getElementById("mobile-captcha-history-list");
  const dateInput = document.getElementById("mobile-captcha-date");
  const statusSelect = document.getElementById("mobile-captcha-status");

  if (!listContainer || !dateInput) return;

  listContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  try {
    const date = dateInput.value.replace(/-/g, "");
    const status = statusSelect ? statusSelect.value : "";
    const params = new URLSearchParams({ date });
    if (status) params.append("status", status);

    const response = await fetch(`/api/captcha/history?${params}`, {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (!result.success) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">${result.message}</p>`;
      return;
    }

    const records = result.data || [];
    if (records.length === 0) {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">该日期没有记录</p>';
      return;
    }

    // 渲染验证码历史记录列表
    listContainer.innerHTML = records
      .map((record) => {
        // 根据验证状态设置不同的背景色和文字颜色
        const statusClass =
          {
            created: "bg-yellow-100 text-yellow-800", // 待验证 - 黄色
            verified_success: "bg-green-100 text-green-800", // 成功 - 绿色
            verified_failed: "bg-red-100 text-red-800", // 失败 - 红色
            expired: "bg-gray-100 text-gray-800", // 过期 - 灰色
            test_generated: "bg-blue-100 text-blue-800", // 测试 - 蓝色
          }[record.status] || "bg-gray-100 text-gray-800";

        // 根据验证状态设置显示的中文文本
        const statusText =
          {
            created: "待验证",
            verified_success: "成功",
            verified_failed: "失败",
            expired: "过期",
            test_generated: "测试",
          }[record.status] || record.status;

        const captchaCode = getCaptchaHistoryDisplayText(record);

        // 返回单条记录的HTML模板
        return `
          <div class="bg-white border border-slate-200 rounded-lg p-3">
              <div class="flex justify-between items-start mb-1">
                  <div class="flex items-center gap-2">
                      <span class="${
                        isBehaviorCaptchaRecord(record) ? "" : "font-mono"
                      } font-bold text-slate-700">${captchaCode}</span>
                      <span class="text-[10px] px-1.5 py-0.5 rounded ${statusClass}">${statusText}</span>
                  </div>
                  <span class="text-xs text-slate-400">${
                    record.timestamp_readable
                      ? record.timestamp_readable.split(" ")[1]
                      : "N/A"
                  }</span>
              </div>
              <div class="text-xs text-slate-500 flex justify-between">
                  <span>IP: ${record.client_ip || "N/A"}</span>
                  ${
                    record.verified_input
                      ? `<span class="${
                          record.status === "verified_success"
                            ? "text-green-600"
                            : "text-red-600"
                        }">输入: ${record.verified_input}</span>`
                      : ""
                  }
              </div>
          </div>
          `;
      })
      .join("");
  } catch (e) {
    console.error("[移动端验证码] 加载历史失败:", e);
    listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败</p>`;
  }
}

// =============================================
// 【3.5】移动端验证码历史记录模态框专用函数
// =============================================

/**
 * 打开移动端验证码历史记录模态框
 * 初始化日期选择器并加载历史数据
 */
function openMobileCaptchaHistoryModal() {
  // 获取模态框元素
  const modal = document.getElementById("mobile-captcha-history-modal");
  if (!modal) {
    console.error("[移动端验证码历史] 找不到模态框元素");
    return;
  }

  // 初始化日期选择器为当天日期
  const dateInput = document.getElementById(
    "mobile-captcha-history-modal-date",
  );
  if (dateInput && !dateInput.value) {
    // 设置日期为今天，格式为 YYYY-MM-DD
    dateInput.value = new Date().toISOString().split("T")[0];
  }

  // 重置状态筛选为全部
  const statusSelect = document.getElementById(
    "mobile-captcha-history-modal-status",
  );
  if (statusSelect) {
    statusSelect.value = "";
  }

  // 显示模态框 - 添加 show 类实现动画效果
  modal.classList.remove("hidden");
  // 使用 requestAnimationFrame 确保动画生效
  requestAnimationFrame(() => {
    modal.classList.add("show");
  });

  // 自动加载历史数据
  loadMobileCaptchaHistoryModal();

  console.log("[移动端验证码历史] 模态框已打开");
}

/**
 * 关闭移动端验证码历史记录模态框
 */
function closeMobileCaptchaHistoryModal() {
  // 获取模态框元素
  const modal = document.getElementById("mobile-captcha-history-modal");
  if (!modal) return;

  // 移除 show 类，触发关闭动画
  modal.classList.remove("show");

  // 等待动画完成后隐藏模态框
  setTimeout(() => {
    modal.classList.add("hidden");
  }, 300); // 动画持续时间

  console.log("[移动端验证码历史] 模态框已关闭");
}

/**
 * 加载移动端验证码历史记录模态框中的数据
 * 根据选择的日期和状态筛选条件从后端获取数据
 */
async function loadMobileCaptchaHistoryModal() {
  // 获取列表容器元素
  const listContainer = document.getElementById(
    "mobile-captcha-history-modal-list",
  );
  // 获取日期输入框
  const dateInput = document.getElementById(
    "mobile-captcha-history-modal-date",
  );
  // 获取状态筛选下拉框
  const statusSelect = document.getElementById(
    "mobile-captcha-history-modal-status",
  );

  // 检查必要元素是否存在
  if (!listContainer || !dateInput) {
    console.error("[移动端验证码历史] 找不到必要的DOM元素");
    return;
  }

  // 显示加载状态
  listContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-sm">⏳ 加载中...</p>';

  const need_weight =
    document.getElementById("mobile-captcha-history-modal-list").clientWidth -
    document.getElementById("mobile-captcha-history-modal-list").offsetLeft -
    50;
  console.log("移动端验证码历史模态框宽度:", need_weight);

  try {
    // 获取日期值并转换为后端需要的格式（YYYYMMDD）
    const date = dateInput.value.replace(/-/g, "");
    // 获取状态筛选值
    const status = statusSelect ? statusSelect.value : "";

    // 构建查询参数
    const params = new URLSearchParams({ date });
    if (status) {
      params.append("status", status);
    }

    // 调用后端API获取验证码历史记录
    const response = await fetch(
      `/api/captcha/history?${params}&weight=${need_weight}`,
      {
        method: "GET",
        headers: { "X-Session-ID": sessionUUID },
      },
    );
    const result = await response.json();

    // 检查请求是否成功
    if (!result.success) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-sm">❌ ${
        result.message || "加载失败"
      }</p>`;
      return;
    }

    // 获取记录数据
    const records = result.data || [];

    // 处理空数据情况
    if (records.length === 0) {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-sm">📭 该日期没有验证码记录</p>';
      return;
    }

    // 调试日志：输出第一条记录的完整结构，便于排查字段命名问题
    // 这里输出所有字段，帮助开发者确认 code 字段是否存在
    console.log("[移动端验证码历史] 已收到验证码记录:", records.length);
    // 额外调试：检查 code 字段是否存在
    if (records[0]) {
      console.log("[移动端验证码历史] 记录字段数量:", Object.keys(records[0]).length);
    }

    // 更新统计数据（若模态框中存在对应元素）
    const total = records.length;
    const success = records.filter(
      (r) => r.status === "verified_success",
    ).length;
    const failed = records.filter((r) => r.status === "verified_failed").length;
    const pending = records.filter((r) => r.status === "created").length;
    const expired = records.filter((r) => r.status === "expired").length;
    const testGenerated = records.filter(
      (r) => r.status === "test_generated",
    ).length;
    const statTotal = document.getElementById("mobile-captcha-stat-total");
    const statSuccess = document.getElementById("mobile-captcha-stat-success");
    const statFailed = document.getElementById("mobile-captcha-stat-failed");
    const statPending = document.getElementById("mobile-captcha-stat-pending");
    const statExpired = document.getElementById("mobile-captcha-stat-expired");
    const statTest = document.getElementById("mobile-captcha-stat-test");
    if (statTotal) statTotal.textContent = total;
    if (statSuccess) statSuccess.textContent = success;
    if (statFailed) statFailed.textContent = failed;
    if (statPending) statPending.textContent = pending;
    if (statExpired) statExpired.textContent = expired;
    if (statTest) statTest.textContent = testGenerated;

    // 渲染历史记录列表，包含详情按钮和图片（如有）
    listContainer.innerHTML = "";
    records.forEach((record) => {
      const statusClass =
        {
          created: "bg-yellow-100 text-yellow-800",
          verified_success: "bg-green-100 text-green-800",
          verified_failed: "bg-red-100 text-red-800",
          expired: "bg-gray-100 text-gray-800",
          test_generated: "bg-blue-100 text-blue-800",
        }[record.status] || "bg-gray-100 text-gray-800";

      const statusText =
        {
          created: "⏳ 待验证",
          verified_success: "✅ 成功",
          verified_failed: "❌ 失败",
          expired: "⏰ 过期",
          test_generated: "🧪 测试",
        }[record.status] || record.status;

      const captchaCode = getCaptchaHistoryDisplayText(record);

      const itemDiv = document.createElement("div");
      itemDiv.className =
        "bg-white border border-slate-200 rounded-lg p-3 shadow-sm mb-2";
      itemDiv.innerHTML = `
        <div class="flex justify-between items-start mb-2">
          <div class="flex items-center gap-2">
            <span class="${
              isBehaviorCaptchaRecord(record) ? "" : "font-mono"
            } font-bold text-lg text-slate-700">${captchaCode}</span>
            <span class="text-xs px-2 py-1 rounded-full ${statusClass}">${statusText}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-400">${
              record.timestamp_readable
                ? record.timestamp_readable.split(" ")[1]
                : "N/A"
            }</span>
            <button class="btn btn-ghost btn-sm !py-1 !px-2 text-xs" onclick="showCaptchaDetail(${escapeInlineJsArg(record.captcha_id)})">详情</button>
          </div>
        </div>
        <div class="text-xs text-slate-500 flex flex-col gap-1">
          <div class="flex justify-between">
            <span>🌐 IP: ${record.client_ip || "N/A"}</span>
            ${
              record.verified_input
                ? `<span class="${record.status === "verified_success" ? "text-green-600" : "text-red-600"}">📝 输入: ${record.verified_input}</span>`
                : ""
            }
          </div>
          ${record.timestamp_readable ? `<span class="text-slate-400">📅 ${record.timestamp_readable}</span>` : ""}
          ${
            !isBehaviorCaptchaRecord(record) && record.html
              ? `<div class="mt-2 pt-2 border-t border-slate-100 rounded overflow-hidden bg-slate-50 p-2"><div class="scale-75 origin-center">${record.html}</div></div>`
              : ""
          }
        </div>
      `;
      listContainer.appendChild(itemDiv);
    });

    console.log(`[移动端验证码历史] 加载完成，共 ${records.length} 条记录`);
  } catch (error) {
    // 捕获并处理异常
    console.error("[移动端验证码历史] 加载失败:", error);
    listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-sm">❌ 加载失败: ${error.message}</p>`;
  }
}

// =============================================
// 【4】移动端定时提醒面板专用函数
// =============================================

/**
 * 刷新移动端定时提醒列表
 */
async function mobileRefreshReminders() {
  // 获取移动端提醒列表容器
  const listContainer = document.getElementById(
    "mobile-multi-admin-reminders-content",
  );
  if (!listContainer) {
    console.error("[移动端提醒] 找不到列表容器 mobile-multi-admin-reminders-content");
    return;
  }

  // 显示加载状态
  listContainer.innerHTML =
    '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';

  try {
    // 调用后端API获取提醒列表
    const response = await fetch("/api/reminders/list", {
      method: "GET",
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (!result.success) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">${
        result.message || "加载失败"
      }</p>`;
      return;
    }

    const reminders = result.reminders || [];
    const total = reminders.length;
    const enabled = reminders.filter((r) => r.enabled).length;
    const disabled = total - enabled;

    // 更新移动端统计数据
    const statTotal = document.getElementById("mobile-reminder-stat-total");
    const statEnabled = document.getElementById("mobile-reminder-stat-enabled");
    const statDisabled = document.getElementById(
      "mobile-reminder-stat-disabled",
    );
    if (statTotal) statTotal.textContent = total;
    if (statEnabled) statEnabled.textContent = enabled;
    if (statDisabled) statDisabled.textContent = disabled;

    // 渲染提醒列表
    if (reminders.length === 0) {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">暂无提醒，点击"添加"创建新提醒</p>';
      return;
    }

    listContainer.innerHTML = "";
    reminders.forEach((reminder, index) => {
      const itemDiv = document.createElement("div");
      // 根据是否跨天设置样式
      const isCrossDay = reminder.start_time > reminder.end_time;
      const timeIcon = isCrossDay ? "🌙" : "☀️";
      const timeHint = isCrossDay ? "(跨天)" : "";
      // 为每个提醒的 Markdown 内容创建唯一ID
      const messageContainerId = `mobile-reminder-message-${reminder.id}-${index}`;

      itemDiv.className = "bg-white border border-slate-200 rounded-lg p-3";
      itemDiv.innerHTML = `
        <div class="flex justify-between items-start gap-2">
          <div class="flex-1 min-w-0">
            <!-- 标题和状态 -->
            <div class="flex items-center gap-2 mb-1">
              <h5 class="font-semibold text-sm text-slate-800 truncate">${escapeHtml(
                reminder.title,
              )}</h5>
              <span class="text-xs px-1.5 py-0.5 rounded ${
                reminder.enabled
                  ? "bg-green-100 text-green-700"
                  : "bg-slate-100 text-slate-600"
              }">${reminder.enabled ? "启用" : "禁用"}</span>
              ${
                reminder.allow_guest_view === true
                  ? '<span class="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 whitespace-nowrap">访客可见</span>'
                  : ""
              }
            </div>
            <!-- 提醒内容（Markdown渲染） -->
            <div id="${messageContainerId}" class="text-xs text-slate-600 mb-2 mobile-reminder-markdown-content"></div>
            <!-- 时间范围 -->
            <div class="flex items-center gap-1 text-xs ${
              isCrossDay ? "text-purple-600" : "text-blue-600"
            }">
              <span>${timeIcon} ${reminder.start_time} - ${
                reminder.end_time
              } ${timeHint}</span>
            </div>
          </div>
          <!-- 操作按钮 -->
          <div class="flex flex-col gap-1 flex-shrink-0">
            <button onclick="openMobileReminderEditModal('${
              reminder.id
            }')" class="btn btn-ghost !py-1 !px-2 text-xs min-h-[32px]">
              编辑
            </button>
            <button onclick="mobileToggleReminderEnabled('${
              reminder.id
            }', ${!reminder.enabled})" class="btn btn-ghost !py-1 !px-2 text-xs min-h-[32px] ${
              reminder.enabled ? "text-yellow-600" : "text-green-600"
            }">
              ${reminder.enabled ? "禁用" : "启用"}
            </button>
            <button onclick="deleteMobileReminder('${
              reminder.id
            }', '${escapeHtml(
              reminder.title,
            )}')" class="btn btn-ghost !py-1 !px-2 text-xs min-h-[32px] text-red-600">
              删除
            </button>
          </div>
        </div>
      `;
      listContainer.appendChild(itemDiv);
    });
    
    // 渲染所有提醒内容的 Markdown（与留言板 admin-messages-list_modal 相同方式）
    console.log("[移动端提醒] 开始使用 Editor.md 渲染 Markdown...");
    (function renderRemindersMarkdown(remindersList) {
      if (!remindersList || !remindersList.length) return;
      remindersList.forEach((reminder, index) => {
        const messageContainerId = `mobile-reminder-message-${reminder.id}-${index}`;
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
            console.warn("[移动端提醒] Markdown渲染失败，回退为纯文本显示", e);
          }
        }

        // 最后回退：以转义文本并保留换行展示
        container.innerHTML = escapeHtml(markdownText).replace(
          /\n/g,
          "<br>",
        );
      });
    })(reminders);

    console.log(`[移动端提醒] 已加载 ${reminders.length} 条提醒`);
  } catch (error) {
    console.error("[移动端提醒] 加载失败:", error);
    listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-xs">加载失败: ${error.message}</p>`;
  }
}

/**
 * 初始化移动端提醒 Editor.md 编辑器（仅初始化一次）
 * @returns {Promise<boolean>}
 */
async function ensureMobileReminderEditorInitialized() {
  try {
    const textareaEl = document.getElementById("mobile-reminder-message-field");
    const editorEl = document.getElementById("mobile-reminder-editor");
    const setFallbackVisibility = (useEditor) => {
      if (textareaEl) {
        textareaEl.style.display = useEditor ? "none" : "";
      }
      if (editorEl) {
        editorEl.style.display = useEditor ? "" : "none";
      }
    };

    if (
      mobileReminderEditor &&
      typeof mobileReminderEditor.getMarkdown === "function"
    ) {
      setFallbackVisibility(true);
      return true;
    }
    if (typeof editormd === "undefined") {
      setFallbackVisibility(false);
      return false;
    }
    if (!editorEl) {
      setFallbackVisibility(false);
      return false;
    }

    mobileReminderEditor = editormd("mobile-reminder-editor", {
          // ===== 基本配置 =====
          // 编辑器模式：
          // gfm：GitHub Flavored Markdown，与 Markdown 语法基本相同，但增加了一些扩展语法，如表格、任务列表等
          // markdown：标准 Markdown 语法
          mode: "gfm",
          // 表单元素名称，用于提交表单时标识该编辑器
          name: "mobile-reminder-message-field",
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
          height: "600px",
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
          placeholder: "请输入提醒内容（支持 Markdown，最多500字）",
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
          onchange: function () {
            // try {
            //   const md = mobileMultiMessageEditor.getMarkdown() || "";
            //   const ta = document.getElementById("mobile-multi-message-content");
            //   const count = document.getElementById(
            //     "mobile-multi-message-char-count",
            //   );
            //   if (ta) ta.value = md;
            //   if (count) count.textContent = String(md.length);
            // } catch (_) {}
          },
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
          /*
          toolbarIcons: function () {
            return [
              "undo",
              "redo",
              "|",
              "bold",
              "italic",
              "quote",
              "|",
              "list-ul",
              "list-ol",
              "|",
              "link",
              "image",
              "code-block",
              "|",
              "watch",
              "preview",
            ];
          },
          */
          // 工具栏标题（自定义工具栏按钮的提示文本）
          toolbarTitles: {},
          // 工具栏处理程序（自定义工具栏按钮的点击事件）
          toolbarHandlers: {},
          // 使用 HTML 标签创建工具栏图标，未使用默认 <a> 标签（自定义工具栏图标的 HTML）
          toolbarCustomIcons: {},
          // 工具栏图标文本（自定义工具栏按钮的文本）
          toolbarIconTexts: {},
          // 父容器层级（用于解决全屏模式下的定位问题）
          parentContainerLayer: "2",
          // 全屏的时候是否允许滚动
          fullScreenScrolling: false,
          // 全屏的时候编辑器位于父容器的坐标位置
          fullScreenCoordinatesX: null,
          fullScreenCoordinatesY: "0px",
          // 进入全屏自动滚动
          fullScreenAutomaticScrolling: "0%",
          fullScreenAutomaticScrollingOuterHtml: true,
          // 锁定所有父容器
          fullScreenForceDisableAllScroll: false,
          // 弹窗打开时自动滚动位置
          dialogOpenAutoScroll: "110px",
          dialogOpenAutoScrollOuterHtml: true,
        });

    setFallbackVisibility(true);
    return true;
  } catch (e) {
    console.error("[移动端提醒] Editor.md 初始化失败:", e);
    const textareaEl = document.getElementById("mobile-reminder-message-field");
    const editorEl = document.getElementById("mobile-reminder-editor");
    if (textareaEl) textareaEl.style.display = "";
    if (editorEl) editorEl.style.display = "none";
    return false;
  }
}

/**
 * 打开移动端提醒编辑模态框
 * @param {string} reminderId - 提醒ID（空字符串表示新建）
 */
async function openMobileReminderEditModal(reminderId = "") {
  // 检查或创建移动端提醒编辑模态框
  let modal = document.getElementById("mobile-reminder-edit-modal");
  if (!modal) {
    // 创建移动端专用的提醒编辑模态框
    modal = document.createElement("div");
    modal.id = "mobile-reminder-edit-modal";
    modal.className = "fixed inset-0 hidden mobile-modal z-[60]";
    modal.onclick = function (e) {
      if (e.target === modal) closeMobileReminderEditModal();
    };
    modal.innerHTML = `
      <div class="absolute inset-0 bg-black/40" onclick="closeMobileReminderEditModal()"></div>
      <div class="mobile-modal-content bg-white rounded-t-3xl p-6 space-y-4 max-h-[90vh] overflow-y-auto" onclick="event.stopPropagation()">
        <!-- 拖拽手柄 -->
        <div class="flex justify-center mb-2 cursor-pointer" onclick="closeMobileReminderEditModal()">
          <div class="w-12 h-1.5 bg-slate-300 rounded-full"></div>
        </div>
        <!-- 模态框标题 -->
        <div class="flex items-center justify-center gap-2 pb-3 border-b border-slate-200 cursor-pointer" onclick="closeMobileReminderEditModal()">
          <svg class="w-6 h-6 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <h3 id="mobile-reminder-modal-title" class="text-xl font-bold text-amber-600 text-center">⏰ 添加定时提醒</h3>
        </div>
        <!-- 隐藏字段：提醒ID -->
        <input type="hidden" id="mobile-reminder-id-field" value="">
        <!-- 提醒标题 -->
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">提醒标题 <span class="text-red-500">*</span></label>
          <input type="text" id="mobile-reminder-title-field" class="input-field text-sm w-full" placeholder="请输入提醒标题（最多50字）" maxlength="50">
        </div>
        <!-- 提醒内容 -->
        <div>
          <label class="block text-sm font-semibold text-slate-700 mb-2">提醒内容 <span class="text-red-500">*</span></label>
          <textarea id="mobile-reminder-message-field" rows="3" class="input-field text-sm w-full resize-none" placeholder="请输入提醒内容（最多500字）" maxlength="500"></textarea>
          <div id="mobile-reminder-editor" style="min-height: 180px; border-radius: 6px; background: #fff; border: 1px solid #e6e6e6; margin-top: 8px;"></div>
        </div>
        <!-- 时间设置 -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">开始时间 <span class="text-red-500">*</span></label>
            <input type="time" id="mobile-reminder-start-time-field" class="input-field text-sm w-full">
          </div>
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-2">结束时间 <span class="text-red-500">*</span></label>
            <input type="time" id="mobile-reminder-end-time-field" class="input-field text-sm w-full">
          </div>
        </div>
        <p class="text-xs text-blue-600 bg-blue-50 p-2 rounded">💡 提示：如果结束时间小于开始时间，系统会认为是跨天提醒（例如：20:00 到次日 08:00）</p>
        <!-- 启用状态 -->
        <div class="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
          <span class="text-sm font-semibold text-slate-700">立即启用</span>
          <label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" id="mobile-reminder-enabled-field" class="sr-only peer" checked>
            <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-amber-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-amber-500"></div>
          </label>
        </div>
        <div class="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
          <label for="mobile-reminder-allow-guest-view-field" class="text-sm font-semibold text-slate-700">允许访客查看</label>
          <input type="checkbox" id="mobile-reminder-allow-guest-view-field" class="w-5 h-5 accent-amber-500">
        </div>
        <!-- 操作按钮 -->
        <div class="flex gap-3 pt-4 border-t border-slate-100">
          <button onclick="closeMobileReminderEditModal()" class="flex-1 py-3 px-4 border border-slate-300 rounded-xl text-sm text-slate-600 min-h-[48px]">取消</button>
          <button onclick="saveMobileReminder()" class="flex-1 py-3 px-4 bg-amber-500 text-white rounded-xl text-sm font-semibold min-h-[48px]">保存提醒</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  // 获取表单元素
  const title = document.getElementById("mobile-reminder-modal-title");
  const idField = document.getElementById("mobile-reminder-id-field");
  const titleField = document.getElementById("mobile-reminder-title-field");
  const messageField = document.getElementById("mobile-reminder-message-field");
  const startTimeField = document.getElementById(
    "mobile-reminder-start-time-field",
  );
  const endTimeField = document.getElementById(
    "mobile-reminder-end-time-field",
  );
  const enabledField = document.getElementById("mobile-reminder-enabled-field");
  const allowGuestViewField = document.getElementById(
    "mobile-reminder-allow-guest-view-field",
  );

  // 如果是编辑模式，加载现有数据
  if (reminderId) {
    if (title) title.textContent = "✏️ 编辑定时提醒";
    try {
      const response = await fetch("/api/reminders/list", {
        method: "GET",
        headers: { "X-Session-ID": sessionUUID },
      });
      const result = await response.json();
      if (result.success) {
        const reminder = result.reminders.find((r) => r.id === reminderId);
        if (reminder) {
          if (idField) idField.value = reminder.id;
          if (titleField) titleField.value = reminder.title;
          if (messageField) messageField.value = reminder.message;
          if (startTimeField) startTimeField.value = reminder.start_time;
          if (endTimeField) endTimeField.value = reminder.end_time;
          if (enabledField) enabledField.checked = reminder.enabled;
          if (allowGuestViewField)
            allowGuestViewField.checked = reminder.allow_guest_view === true;
        } else {
          showModalAlert("提醒不存在", "错误");
          return;
        }
      }
    } catch (error) {
      console.error("[移动端提醒] 加载提醒数据失败:", error);
      showModalAlert("加载提醒数据失败", "错误");
      return;
    }
  } else {
    // 新建模式，清空表单
    if (title) title.textContent = "⏰ 添加定时提醒";
    if (idField) idField.value = "";
    if (titleField) titleField.value = "";
    if (messageField) messageField.value = "";
    if (startTimeField) startTimeField.value = "";
    if (endTimeField) endTimeField.value = "";
    if (enabledField) enabledField.checked = true;
    if (allowGuestViewField) allowGuestViewField.checked = false;
  }

  // 显示模态框
  modal.classList.remove("hidden");
  setTimeout(() => {
    modal.classList.add("show");
  }, 10);

  // 模态框可见后再初始化/刷新编辑器，避免隐藏状态下全屏坐标计算偶发失效
  setTimeout(async () => {
    const initialMessage = messageField ? messageField.value || "" : "";
    await ensureMobileReminderEditorInitialized();
    if (
      mobileReminderEditor &&
      typeof mobileReminderEditor.setMarkdown === "function"
    ) {
      mobileReminderEditor.setMarkdown(initialMessage);
    }
    if (
      mobileReminderEditor &&
      mobileReminderEditor.cm &&
      typeof mobileReminderEditor.cm.refresh === "function"
    ) {
      mobileReminderEditor.cm.refresh();
    }

  }, 60);

  // 聚焦到标题输入框
  if (titleField) titleField.focus();
}

/**
 * 关闭移动端提醒编辑模态框
 */
function closeMobileReminderEditModal() {
  const modal = document.getElementById("mobile-reminder-edit-modal");
  if (modal) {
    modal.classList.remove("show");
    setTimeout(() => {
      modal.classList.add("hidden");
    }, 300);
  }
}

/**
 * 保存移动端提醒
 */
async function saveMobileReminder() {
  // 获取表单数据
  const id =
    document.getElementById("mobile-reminder-id-field")?.value.trim() || "";
  const title =
    document.getElementById("mobile-reminder-title-field")?.value.trim() || "";
  const messageFromTextarea =
    document.getElementById("mobile-reminder-message-field")?.value.trim() ||
    "";
  const messageFromEditor =
    mobileReminderEditor &&
    typeof mobileReminderEditor.getMarkdown === "function"
      ? (mobileReminderEditor.getMarkdown() || "").trim()
      : "";
  const message = messageFromEditor || messageFromTextarea;
  const startTime =
    document.getElementById("mobile-reminder-start-time-field")?.value || "";
  const endTime =
    document.getElementById("mobile-reminder-end-time-field")?.value || "";
  const enabled =
    document.getElementById("mobile-reminder-enabled-field")?.checked || false;
  const allowGuestView =
    document.getElementById("mobile-reminder-allow-guest-view-field")?.checked ===
    true;

  // 表单验证
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

  // 时间格式验证
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
      allow_guest_view: allowGuestView,
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
      showModalAlert(isUpdate ? "提醒更新成功" : "提醒添加成功", "成功");
      closeMobileReminderEditModal();
      // 刷新移动端和PC端提醒列表
      mobileRefreshReminders();
      if (typeof loadReminders === "function") {
        loadReminders();
      }
    } else {
      showModalAlert(result.message || "保存失败", "错误");
    }
  } catch (error) {
    console.error("[移动端提醒] 保存失败:", error);
    showModalAlert("保存提醒时发生错误: " + error.message, "错误");
  }
}

/**
 * 移动端切换提醒启用状态
 * @param {string} reminderId - 提醒ID
 * @param {boolean} newEnabledState - 新的启用状态
 */
async function mobileToggleReminderEnabled(reminderId, newEnabledState) {
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
        `[移动端提醒] 提醒状态已更新: ID=${reminderId}, enabled=${newEnabledState}`,
      );
      // 刷新移动端和PC端提醒列表
      mobileRefreshReminders();
      if (typeof loadReminders === "function") {
        loadReminders();
      }
    } else {
      showModalAlert(result.message || "更新状态失败", "错误");
    }
  } catch (error) {
    console.error("[移动端提醒] 更新状态失败:", error);
    showModalAlert("更新提醒状态时发生错误: " + error.message, "错误");
  }
}

/**
 * 移动端删除提醒
 * @param {string} reminderId - 提醒ID
 * @param {string} reminderTitle - 提醒标题（用于确认对话框）
 */
async function deleteMobileReminder(reminderId, reminderTitle) {
  // 显示确认对话框
  const confirmed = await showMobileConfirmAsync(
    "确认删除",
    `确定要删除提醒「${reminderTitle}」吗？此操作不可恢复。`,
  );
  if (!confirmed) return;

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
      showModalAlert("提醒已删除", "成功");
      // 刷新移动端和PC端提醒列表
      mobileRefreshReminders();
      if (typeof loadReminders === "function") {
        loadReminders();
      }
    } else {
      showModalAlert(result.message || "删除失败", "错误");
    }
  } catch (error) {
    console.error("[移动端提醒] 删除失败:", error);
    showModalAlert("删除提醒时发生错误: " + error.message, "错误");
  }
}

console.log("[移动端] Phase 5 管理面板功能修复已加载");

// --- Next Script Block ---

window.addEventListener("beforeunload", () => {
  stopMultiAccountAutoRefresh();
});

// =============================================================================
// 密码恢复任务管理功能
// =============================================================================

/**
 * 更新密码恢复任务列表显示
 *
 * 功能说明：
 *   此函数负责将后端返回的密码恢复任务状态数据渲染到前端界面上。
 *   它会同时更新桌面版和移动版两个不同的任务列表容器，确保在不同设备上
 *   用户都能看到最新的任务状态。
 *
 * 参数：
 *   tasks (Array) - 任务状态数组，每个任务对象包含以下字段：
 *     - account (String): 正在尝试恢复密码的账号名称
 *     - status (String): 任务当前状态，可能的值包括：
 *         * "running" - 任务正在运行中
 *         * "success" - 密码已成功找到
 *         * "failed" - 任务失败（密码未找到或出现错误）
 *         * "stopped" - 任务已被用户手动停止
 *     - attempts (Number): 已经尝试的密码组合数量
 *     - password (String, 可选): 如果status为"success"，此字段包含找到的密码
 *     - start_time (String, 可选): 任务开始的时间戳（格式化后的字符串）
 *     - end_time (String, 可选): 任务结束的时间戳（格式化后的字符串）
 *
 * 返回值：
 *   无返回值（void）
 *
 * 实现细节：
 *   1. 获取DOM元素：分别获取桌面版和移动版的任务列表容器
 *   2. 空状态处理：如果没有任务，显示友好的提示信息
 *   3. 任务卡片生成：遍历每个任务，根据状态生成不同样式的卡片HTML
 *   4. 状态着色：使用Tailwind CSS的颜色类，为不同状态应用不同的视觉效果
 *   5. DOM更新：将生成的HTML插入到对应的容器中
 */
function updateBruteforceTaskList(tasks) {
  // 通过ID选择器获取桌面版任务列表的DOM容器
  // 这个容器通常在主界面的管理面板中
  const desktopList = document.getElementById("bruteforce-task-list");

  // 通过ID选择器获取移动版任务列表的DOM容器
  // 移动版界面通常有独立的、更紧凑的布局
  const mobileList = document.getElementById("mobile-bruteforce-task-list");

  // 边界情况处理：检查tasks是否为空、未定义或空数组
  // 这是一个重要的防御性编程实践，避免在空数据时出现错误
  if (!tasks || tasks.length === 0) {
    // 定义空状态的提示消息HTML
    // 使用Tailwind CSS类来实现居中、灰色、适当的内边距
    const emptyMessage =
      '<div class="text-slate-400 text-center py-8 text-sm">暂无任务</div>';

    // 如果桌面版容器存在，则插入空状态消息
    if (desktopList) desktopList.innerHTML = emptyMessage;

    // 如果移动版容器存在，则插入更紧凑的空状态消息
    // 注意移动版使用更小的字体(text-xs)和内边距(py-4)
    if (mobileList)
      mobileList.innerHTML =
        '<div class="text-slate-400 text-center py-4 text-xs">暂无任务</div>';

    // 处理完空状态后，直接返回，不再执行后续的任务渲染逻辑
    return;
  }

  // 初始化两个字符串变量，用于累积生成的HTML代码
  // 分别对应桌面版和移动版的任务列表HTML
  let desktopHTML = "";
  let mobileHTML = "";

  // 遍历tasks数组中的每一个任务对象
  // 使用forEach方法可以简洁地处理数组中的每个元素
  tasks.forEach((task) => {
    // ====================================================================
    // 步骤1：根据任务状态确定视觉样式
    // ====================================================================

    // 初始化状态相关的变量，默认值对应"运行中"状态
    let statusColor = "slate"; // Tailwind颜色类名，slate表示灰色系
    let statusIcon = "⏳"; // Unicode图标，沙漏表示进行中
    let statusText = "运行中"; // 中文状态文本

    // 通过if-else链检查任务的status字段，设置相应的视觉元素
    if (task.status === "success") {
      // 成功状态：使用绿色主题
      statusColor = "green"; // 绿色传达积极、完成的信息
      statusIcon = "✅"; // 对勾图标，直观表示成功
      statusText = "成功"; // 简洁的状态文本
    } else if (task.status === "failed") {
      // 失败状态：使用红色主题
      statusColor = "red"; // 红色警示失败或错误
      statusIcon = "❌"; // 叉号图标，表示未通过
      statusText = "失败"; // 明确的失败提示
    } else if (task.status === "stopped") {
      // 已停止状态：使用橙色主题
      statusColor = "orange"; // 橙色表示警告或中性状态
      statusIcon = "⏸️"; // 暂停图标，表示中断
      statusText = "已停止"; // 说明是用户主动停止
    }
    // 注意：如果status为"running"或其他未知值，将保持默认的slate样式

    // ====================================================================
    // 步骤2：生成桌面版任务卡片HTML
    // ====================================================================

    // 使用模板字符串构建HTML，可以方便地嵌入变量和表达式
    desktopHTML += `
            <div class="p-3 border border-${statusColor}-200 bg-${statusColor}-50 rounded-lg">
                <!-- 任务卡片的外层容器，使用状态颜色的浅色背景和边框 -->
                <!-- p-3: 内边距，border: 边框，rounded-lg: 圆角 -->
                
                <div class="flex justify-between items-start mb-2">
                    <!-- 顶部信息行：使用flex布局，左右分布，顶部对齐 -->
                    
                    <div>
                        <!-- 左侧：账号名称和状态标签 -->
                        
                        <span class="font-semibold text-slate-800">${
                          task.account
                        }</span>
                        <!-- 显示账号名称，使用加粗字体和深灰色 -->
                        
                        <span class="ml-2 text-sm px-2 py-0.5 rounded bg-${statusColor}-100 text-${statusColor}-700">
                            <!-- 状态徽章：使用状态颜色的浅色背景和深色文字 -->
                            <!-- ml-2: 左边距与账号名分隔，px-2 py-0.5: 内边距，rounded: 圆角 -->
                            ${statusIcon} ${statusText}
                            <!-- 显示状态图标和文字 -->
                        </span>
                    </div>
                    
                    ${
                      task.status === "running"
                        ? `
                        <!-- 右侧：仅在任务运行中时显示停止按钮 -->
                        <!-- 使用三元表达式进行条件渲染 -->
                        
                        <button onclick="stopBruteforce(${escapeInlineJsArg(task.account)})" class="text-xs btn btn-ghost !py-1 !px-2">
                            <!-- 停止按钮：调用stopBruteforce函数，传入账号名称 -->
                            <!-- btn-ghost: 幽灵按钮样式（透明背景） -->
                            <!-- !py-1 !px-2: 使用!important覆盖默认按钮尺寸 -->
                            停止
                        </button>
                    `
                        : ""
                    }
                    <!-- 如果不是运行中状态，则不渲染按钮（空字符串） -->
                </div>
                
                <div class="text-sm text-slate-600">
                    <!-- 详细信息区域：较小的字体和中等灰色 -->
                    
                    <div>已尝试: ${task.attempts || 0} 个密码</div>
                    <!-- 显示尝试次数，使用 || 运算符提供默认值0 -->
                    <!-- 如果task.attempts为undefined/null/0，则显示0 -->
                    
                    ${
                      task.password
                        ? `<div class="text-green-600 font-semibold">密码: ${task.password}</div>`
                        : ""
                    }
                    <!-- 条件渲染：仅当找到密码时才显示此行 -->
                    <!-- 使用绿色和加粗突出显示找到的密码 -->
                    
                    ${
                      task.start_time
                        ? `<div class="text-xs text-slate-500 mt-1">开始时间: ${task.start_time}</div>`
                        : ""
                    }
                    <!-- 条件渲染：如果有开始时间，则显示 -->
                    <!-- text-xs: 更小的字号，text-slate-500: 更浅的灰色，mt-1: 顶部边距 -->
                </div>
            </div>
        `;

    // ====================================================================
    // 步骤3：生成移动版任务卡片HTML（更紧凑的版本）
    // ====================================================================

    // 移动版的设计理念：在小屏幕上节省空间，简化信息展示
    mobileHTML += `
            <div class="p-2 border border-${statusColor}-200 bg-${statusColor}-50 rounded text-xs">
                <!-- 外层容器：比桌面版更小的内边距(p-2)和字体(text-xs) -->
                
                <div class="flex justify-between items-center mb-1">
                    <!-- 顶部信息行：居中对齐，较小的底部边距 -->
                    
                    <span class="font-semibold">${task.account}</span>
                    <!-- 账号名称：加粗但不设置颜色，继承父元素的text-xs -->
                    
                    <span class="text-xs px-1.5 py-0.5 rounded bg-${statusColor}-100 text-${statusColor}-700">
                        <!-- 状态徽章：更小的内边距以节省空间 -->
                        ${statusIcon} ${statusText}
                    </span>
                </div>
                
                <div class="text-xs text-slate-600">
                    <!-- 详细信息区域：极小字体 -->
                    
                    尝试: ${task.attempts || 0} 个
                    <!-- 简化的尝试次数显示，省略"已"和"密码"等冗余词汇 -->
                    
                    ${
                      task.password
                        ? `<div class="text-green-600 font-semibold">密码: ${task.password}</div>`
                        : ""
                    }
                    <!-- 密码显示逻辑与桌面版相同 -->
                    <!-- 注意：移动版省略了开始时间，进一步简化界面 -->
                </div>
            </div>
        `;
  });
  // forEach循环结束，此时desktopHTML和mobileHTML已包含所有任务卡片的HTML代码

  // ====================================================================
  // 步骤4：更新DOM，将生成的HTML插入到页面中
  // ====================================================================

  // 如果桌面版容器存在于DOM中，则更新其innerHTML
  // innerHTML会完全替换容器内的现有内容
  if (desktopList) desktopList.innerHTML = desktopHTML;

  // 如果移动版容器存在于DOM中，则更新其innerHTML
  if (mobileList) mobileList.innerHTML = mobileHTML;

  // 函数执行完毕，任务列表已更新到页面上
  // 用户现在可以看到所有任务的最新状态
}

/**
 * 加载应用初始数据的统一封装函数
 *
 * 功能概述：
 *   这是一个关键的初始化函数，负责在应用启动或用户登录后从后端获取
 *   必要的初始数据。它不仅调用API，还会根据返回的数据自动执行相应的
 *   UI更新操作，特别是为超级管理员自动更新密码恢复任务列表。
 *
 * 核心功能：
 *   1. 统一调用：将所有对 get_initial_data API 的调用集中到此函数
 *   2. 数据获取：从后端获取用户列表、最后登录用户、权限信息等初始数据
 *   3. 自动更新：如果响应中包含密码恢复任务列表（仅超级管理员可见），
 *      自动调用 updateBruteforceTaskList() 更新UI
 *   4. 错误处理：捕获并记录API调用过程中的任何错误
 *
 * 设计优势：
 *   - 代码复用：避免在多处重复写API调用和任务列表更新逻辑
 *   - 维护性：将来如果需要修改初始化逻辑，只需修改此函数
 *   - 一致性：确保所有初始化流程都执行相同的更新逻辑
 *   - 可测试性：将逻辑封装后更容易进行单元测试
 *
 * 调用时机：
 *   - 应用首次加载时
 *   - 用户登录成功后
 *   - 用户切换账号后
 *   - 需要刷新用户数据时
 *
 * 返回值：
 *   Promise<Object> - 一个Promise对象，resolve时返回包含初始数据的对象
 *   返回的对象结构（示例）：
 *   {
 *     success: true,                    // API调用是否成功
 *     users: [...],                     // 用户列表数组
 *     last_login_user: "username",      // 最后登录的用户名
 *     is_superadmin: true/false,        // 当前用户是否为超级管理员
 *     bruteforce_task_list: [...],      // (可选)密码恢复任务列表，仅超级管理员有此字段
 *     // ... 其他初始数据字段
 *   }
 *
 * 异常处理：
 *   如果API调用失败，函数会：
 *   1. 在控制台输出错误日志（包含 [初始化] 前缀便于过滤）
 *   2. 将错误向上抛出（throw），让调用者可以捕获并处理
 *
 * 使用示例：
 *   try {
 *     const data = await loadInitialData();
 *     if (data.success) {
 *       console.log('初始化成功', data);
 *     }
 *   } catch (error) {
 *     console.error('初始化失败', error);
 *   }
 */
// ============================================================================
// 全局变量：用于loadInitialData的限流机制
// ============================================================================
let lastInitialDataRequest = 0; // 上次请求的时间戳（毫秒）
let lastInitialDataResponse = null; // 缓存的上次响应数据
const INITIAL_DATA_RATE_LIMIT = 500; // 限流时间：500毫秒（0.5秒）
