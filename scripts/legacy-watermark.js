// Watermark configuration and administration extracted from main.js.
function updateWatermarkDefaultLabel() {
  // ========== PC端标签更新 ==========
  // 获取PC端默认值开关元素（checkbox）
  const defaultCheckbox_PC = document.getElementById(
    "watermark-default-value_modal",
  );
  // 获取PC端默认值标签元素
  const defaultLabel_PC = document.getElementById(
    "watermark-default-label_modal",
  );

  // 如果PC端两个元素都存在，则更新标签文本
  if (defaultCheckbox_PC && defaultLabel_PC) {
    // 根据checkbox的checked状态设置标签文本
    // checked=true 表示允许去水印，显示"允许"
    // checked=false 表示禁止去水印，显示"禁止"
    defaultLabel_PC.textContent = defaultCheckbox_PC.checked ? "允许" : "禁止";
  }

  // ========== 【问题45修复】移动端标签更新 ==========
  // 获取移动端默认值开关元素（checkbox）
  // 使用-mobile后缀以区别于PC端的_modal后缀
  const defaultCheckbox_Mobile = document.getElementById(
    "watermark-default-value-mobile",
  );
  // 获取移动端默认值标签元素
  const defaultLabel_Mobile = document.getElementById(
    "watermark-default-label-mobile",
  );

  // 如果移动端两个元素都存在，则更新标签文本
  if (defaultCheckbox_Mobile && defaultLabel_Mobile) {
    // 根据checkbox的checked状态设置标签文本（与PC端逻辑相同）
    defaultLabel_Mobile.textContent = defaultCheckbox_Mobile.checked
      ? "允许"
      : "禁止";
  }
}

/**
 * 加载高德地图去水印控制配置
 *
 * 功能说明：
 * 从服务器获取水印控制配置，包括系统默认值和所有用户的个性化设置，
 * 并更新UI显示（包括PC端和移动端）。
 *
 * API端点：GET /api/amap/watermark_control/config
 * 权限要求：管理员权限 + view_config 权限
 *
 * 响应数据格式：
 * {
 *   "success": true,
 *   "config": {
 *     "default": true/false,  // 系统默认值
 *     "users": {
 *       "username1": true,
 *       "username2": false,
 *       ...
 *     }
 *   },
 *   "all_users": ["username1", "username2", ...]  // 系统中所有用户
 * }
 *
 * UI更新内容：
 * 1. 更新系统默认值开关状态（PC端和移动端）
 * 2. 更新用户数量显示
 * 3. 生成用户权限列表（只显示已自定义的用户）
 *
 * 【问题45修复】此函数现在同时支持PC端和移动端
 * 原问题：只支持PC端（_modal后缀的元素）
 * 修复方案：检测移动端容器，如果存在则同步更新移动端UI
 *
 * 错误处理：
 * 1. 网络请求失败：显示错误提示
 * 2. 响应解析失败：显示错误提示
 * 3. 服务器返回失败：显示错误消息
 */
async function loadWatermarkControlConfig() {
  configLoadState.watermark = false;
  try {
    // ========== 步骤1: 显示加载状态 ==========
    // 记录日志，便于调试
    console.log("[水印控制] 正在加载水印控制配置...");

    // 更新PC端用户列表容器，显示"加载中..."提示
    const listContainer_PC = document.getElementById(
      "watermark-users-list_modal",
    );
    if (listContainer_PC) {
      listContainer_PC.innerHTML =
        '<p class="text-slate-400 text-center py-10">加载中...</p>';
    }

    // 【问题45修复】更新移动端用户列表容器，显示"加载中..."提示
    const listContainer_Mobile = document.getElementById(
      "watermark-users-list-mobile",
    );
    if (listContainer_Mobile) {
      listContainer_Mobile.innerHTML =
        '<p class="text-slate-400 text-center py-6 text-xs">加载中...</p>';
    }

    // ========== 步骤2: 发送HTTP请求获取配置 ==========
    // 使用fetch API发送GET请求到服务器
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "GET", // HTTP方法：GET（获取数据）
      headers: {
        "Content-Type": "application/json", // 告诉服务器我们期望JSON格式的响应
        "X-Session-ID": sessionUUID, // 传递会话ID，用于身份验证
      },
    });

    // ========== 步骤3: 解析响应数据 ==========
    // 将响应体解析为JSON对象
    const data = await response.json();

    // ========== 步骤4: 检查响应状态 ==========
    // 如果请求失败（success=false），抛出错误
    if (!data.success) {
      throw new Error(data.message || "获取水印控制配置失败");
    }

    // ========== 步骤5: 提取配置数据 ==========
    // 从响应中提取各项配置数据
    const config = data.config; // 配置对象，包含default和users
    const defaultValue = config.default; // 系统默认值（true/false）
    const usersConfig = config.users; // 用户个性化配置字典
    const allUsers = data.all_users; // 系统中所有用户的列表

    // ========== 步骤6: 更新默认值开关（PC端和移动端）==========
    // 找到PC端默认值开关元素（checkbox）
    const defaultCheckbox_PC = document.getElementById(
      "watermark-default-value_modal",
    );
    if (defaultCheckbox_PC) {
      // 设置PC端开关状态（checked表示允许去水印）
      defaultCheckbox_PC.checked = defaultValue;
    }

    // 【问题45修复】找到移动端默认值开关元素（checkbox）
    const defaultCheckbox_Mobile = document.getElementById(
      "watermark-default-value-mobile",
    );
    if (defaultCheckbox_Mobile) {
      // 设置移动端开关状态（checked表示允许去水印）
      defaultCheckbox_Mobile.checked = defaultValue;
    }

    // 更新默认值标签显示（PC端和移动端都会更新）
    updateWatermarkDefaultLabel();

    // ========== 步骤7: 更新用户数量显示（PC端和移动端）==========
    // 获取已自定义的用户数量（而非系统所有用户数量）
    const customizedUsersCount = Object.keys(usersConfig).length;

    const userCountElement_PC = document.getElementById(
      "watermark-user-count_modal",
    );
    if (userCountElement_PC) {
      userCountElement_PC.textContent = `共 ${customizedUsersCount} 个自定义用户`;
    }

    // 【问题45修复】更新移动端用户数量显示
    const userCountElement_Mobile = document.getElementById(
      "watermark-user-count-mobile",
    );
    if (userCountElement_Mobile) {
      userCountElement_Mobile.textContent = `共 ${customizedUsersCount} 个自定义用户`;
    }

    // ========== 步骤8: 生成用户权限列表（PC端）==========
    // 【修复问题38】只显示已自定义的用户（在usersConfig中的用户）
    // 使用正确的变量名 listContainer_PC
    if (listContainer_PC) {
      // 清空加载提示
      listContainer_PC.innerHTML = "";

      // 获取已自定义的用户列表（即在usersConfig中的用户）
      const customizedUsers = Object.keys(usersConfig);

      if (customizedUsers.length === 0) {
        // 如果没有自定义用户，显示空状态提示
        listContainer_PC.innerHTML =
          '<p class="text-slate-400 text-center py-10">暂无已自定义的用户，点击右侧"添加"按钮添加</p>';
      } else {
        // 为每个已自定义的用户创建一个权限控制项
        customizedUsers.forEach((username) => {
          // 获取该用户的配置值（一定在usersConfig中）
          const userValue = usersConfig[username];

          // [安全修复] 使用escapeHtml()函数转义用户名，防止XSS攻击
          // 转义后的用户名可以安全地插入到HTML中，避免特殊字符（如'<>"等）导致的安全问题
          const safeUsername = escapeHtml(username);

          // 创建用户权限控制项的HTML
          // 包含：用户名 + 开关按钮 + 删除按钮
          const userItem = document.createElement("div");
          userItem.className =
            "bg-white p-3 rounded-lg border border-slate-200 flex items-center justify-between";

          // 构建HTML内容
          userItem.innerHTML = `
            <div class="flex-1">
              <span class="text-sm font-medium text-slate-700">${safeUsername}</span>
              <p class="text-xs text-slate-500 mt-0.5">已自定义</p>
            </div>
            <div class="flex items-center gap-2">
              <label class="relative inline-flex items-center cursor-pointer">
                <input 
                  type="checkbox" 
                  id="watermark-user-${safeUsername}_modal" 
                  class="sr-only peer watermark-user-checkbox" 
                  data-username="${safeUsername}"
                  ${userValue ? "checked" : ""}
                >
                <div class="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
              <button 
                onclick="deleteWatermarkUser(${escapeInlineJsArg(username)})"
                class="px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
                title="删除此用户的自定义配置，恢复使用默认值"
              >
                <svg class="w-3 h-3 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
              </button>
            </div>
          `;

          // 将用户项添加到列表容器中
          listContainer_PC.appendChild(userItem);
        });
      }
    }

    // ========== 步骤9: 记录成功日志 ==========
    console.log("[水印控制] 配置加载成功（PC端）");
    configLoadState.watermark = true;
  } catch (error) {
    configLoadState.watermark = false;
    // ========== 错误处理 ==========
    // 捕获所有可能的错误（网络错误、解析错误、服务器错误等）
    console.error("[水印控制] 加载配置失败（PC端）:", error);

    // 显示错误提示
    // showModalAlert("加载水印控制配置失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "加载失败",
      text: `加载失败：${error.message || "未知错误"}`,
    });

    // 更新UI显示错误状态
    const listContainer = document.getElementById("watermark-users-list_modal");
    if (listContainer) {
      listContainer.innerHTML =
        '<p class="text-red-500 text-center py-10">加载失败：' +
        error.message +
        "</p>";
    }
  }
}

/**
 * 保存水印控制配置（PC端）
 *
 * 功能说明：
 * 收集PC端管理面板中的默认值设置和所有用户的权限设置，并发送到服务器保存。
 *
 * 数据收集：
 * 1. 读取默认值开关（watermark-default-value_modal）的checked状态
 * 2. 遍历所有标记为 watermark-user-checkbox 的复选框，
 *    读取每个复选框的 data-username 属性和 checked 状态，
 *    构建用户配置字典。
 *
 * API端点：PUT /api/amap/watermark_control/config
 * 权限要求：管理员权限 + modify_config 权限
 *
 * 请求体格式：
 * {
 *   "default": true/false,  // 系统默认值
 *   "users": {
 *     "username1": true,
 *     "username2": false,
 *     ...
 *   }
 * }
 */
async function saveWatermarkControlConfig() {
  if (!ensureConfigLoaded("watermark", "水印控制")) {
    return;
  }
  try {
    // ========== 步骤1: 收集默认值配置 ==========
    console.log("[水印控制] 正在收集配置数据（PC端）...");

    // 获取默认值开关的状态
    const defaultCheckbox = document.getElementById(
      "watermark-default-value_modal",
    );
    const defaultValue = defaultCheckbox ? defaultCheckbox.checked : true;

    // ========== 步骤2: 收集用户配置数据 ==========
    // 创建一个空对象，用于存储所有用户的配置
    const usersConfig = {};

    // 查找所有的用户权限复选框
    const checkboxes = document.querySelectorAll(".watermark-user-checkbox");

    // 遍历每个复选框，提取用户名和配置值
    checkboxes.forEach((checkbox) => {
      // 从 data-username 属性获取用户名
      const username = checkbox.getAttribute("data-username");

      // 从 checked 属性获取配置值（true=允许，false=禁止）
      const allowed = checkbox.checked;

      // 将用户配置添加到字典中
      usersConfig[username] = allowed;
    });

    // ========== 步骤3: 构建请求体 ==========
    const requestBody = {
      default: defaultValue, // 添加默认值字段
      users: usersConfig,
    };

    // 只记录数量，避免日志暴露用户账号列表。
    console.log(
      "[水印控制] 准备保存配置（PC端），用户数:",
      Object.keys(usersConfig).length,
    );

    // ========== 步骤4: 发送HTTP请求保存配置 ==========
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "PUT", // HTTP方法：PUT（更新数据）
      headers: {
        "Content-Type": "application/json", // 告诉服务器我们发送的是JSON数据
        "X-Session-ID": sessionUUID, // 传递会话ID，用于身份验证
      },
      body: JSON.stringify(requestBody), // 将请求体转换为JSON字符串
    });

    // ========== 步骤5: 解析响应数据 ==========
    const data = await response.json();

    // ========== 步骤6: 检查响应状态 ==========
    if (!data.success) {
      throw new Error(data.message || "保存水印控制配置失败");
    }

    // ========== 步骤7: 显示成功提示 ==========
    // showModalAlert("水印控制配置已成功保存！");
    Swal.fire({
      icon: "success",
      title: "保存成功",
      text: "水印控制配置已成功保存！",
    });

    // ========== 步骤8: 记录成功日志 ==========
    console.log("[水印控制] 配置保存成功（PC端）");
  } catch (error) {
    // ========== 错误处理 ==========
    console.error("[水印控制] 保存配置失败（PC端）:", error);
    // showModalAlert("保存水印控制配置失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "保存失败",
      text: `保存失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 删除水印控制用户的自定义配置（PC端）
 *
 * 功能说明：
 * 删除指定用户的自定义水印控制配置，使其恢复使用系统默认值。
 *
 * 实现步骤：
 * 1. 确认用户是否要删除
 * 2. 获取当前配置
 * 3. 从usersConfig中删除该用户
 * 4. 保存更新后的配置
 * 5. 刷新列表
 *
 * @param {string} username - 要删除配置的用户名
 *
 * API端点：
 * - GET /api/amap/watermark_control/config - 获取当前配置
 * - PUT /api/amap/watermark_control/config - 保存更新后的配置
 */
async function deleteWatermarkUser(username) {
  try {
    // ========== 步骤1: 使用SweetAlert2进行二次确认 ==========
    // 为什么使用Swal.fire而不是原生confirm:
    // 1. 提供更美观、现代化的用户界面，提升用户体验
    // 2. 支持自定义样式（按钮颜色、图标等），使界面更符合设计规范
    // 3. 更好的可读性，文本显示更清晰，避免原生对话框的简陋外观
    // 4. 与项目中其他使用Swal.fire的地方保持一致的交互风格
    const result = await Swal.fire({
      // title: 对话框标题，使用疑问句让用户明确当前操作的性质
      title: "确认删除用户配置？",

      // html: 对话框的主要内容，使用HTML格式以支持更丰富的文本展示
      // 使用<strong>标签突出显示用户名，让用户清楚知道要删除的是哪个用户
      // 使用<br><br>进行段落分隔，提高可读性
      html: `您即将删除用户 <strong>"${username}"</strong> 的自定义水印配置。<br><br>删除后该用户将使用系统默认值。<br><br>此操作不可撤销，请谨慎操作。`,

      // icon: 显示警告图标，提示用户这是一个需要谨慎处理的操作
      // 'warning' 图标会显示为黄色感叹号，符合删除操作的警告性质
      icon: "warning",

      // showCancelButton: 显示取消按钮，给用户提供退出的机会，防止误操作
      showCancelButton: true,

      // confirmButtonColor: 确认按钮使用红色（#ef4444 是Tailwind的red-500）
      // 红色表示这是一个危险操作，提醒用户三思而后行
      confirmButtonColor: "#ef4444",

      // cancelButtonColor: 取消按钮使用蓝色（#3085d6 是SweetAlert2的默认蓝色）
      // 蓝色表示安全的、非破坏性的操作
      cancelButtonColor: "#3085d6",

      // confirmButtonText: 确认按钮的文字，使用明确的动作描述
      // "确定删除"比简单的"确定"更能让用户明白点击后的后果
      confirmButtonText: "确定删除",

      // cancelButtonText: 取消按钮的文字，使用简洁的中文表达
      cancelButtonText: "取消",

      // focusCancel: 默认聚焦到取消按钮，而不是确认按钮
      // 这是一个重要的安全设计：防止用户不小心按回车键就执行了删除操作
      // 用户必须主动移动焦点或点击才能确认删除
      focusCancel: true,

      // reverseButtons: 反转按钮顺序，让取消按钮显示在左边，确认按钮在右边
      // 这符合常见的UI设计习惯（危险操作按钮通常在右侧）
      reverseButtons: true,
    });

    // 处理用户的选择结果
    // result.isConfirmed: 如果用户点击了"确定删除"按钮，此属性为true
    // result.isDismissed: 如果用户点击了"取消"按钮或点击对话框外部关闭，此属性为true
    if (!result.isConfirmed) {
      // 用户取消了删除操作（点击取消、按ESC键或点击对话框外部）
      // 记录日志后直接返回，不执行后续的删除逻辑
      console.log(`[水印控制] 用户取消删除"${username}"的配置`);
      return; // 提前返回，终止函数执行
    }

    // 如果代码执行到这里，说明用户已经确认要删除
    // 记录日志，标记删除操作的开始
    console.log(`[水印控制] 正在删除用户"${username}"的自定义配置...`);

    // ========== 步骤2: 获取当前配置 ==========
    // 需要先获取完整配置，然后删除指定用户，再保存
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.message || "获取当前配置失败");
    }

    // ========== 步骤3: 从配置中删除该用户 ==========
    const usersConfig = data.config.users || {};

    // 检查用户是否存在于配置中
    if (!(username in usersConfig)) {
      console.warn(`[水印控制] 用户"${username}"不在配置中，无需删除`);
      // showModalAlert(`用户"${username}"未在配置中，无需删除`);
      Swal.fire({
        icon: "info",
        title: "提示",
        text: `用户"${username}"未在配置中，无需删除`,
      });
      return;
    }

    // 删除该用户的配置
    delete usersConfig[username];

    console.log(`[水印控制] 已从配置中移除用户"${username}"`);

    // ========== 步骤4: 保存更新后的配置 ==========
    const saveResponse = await fetch("/api/amap/watermark_control/config", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        users: usersConfig,
      }),
    });

    const saveData = await saveResponse.json();

    if (!saveData.success) {
      throw new Error(saveData.message || "保存配置失败");
    }

    // ========== 步骤5: 显示成功提示并刷新列表 ==========
    // showModalAlert(
    //   `已成功删除用户"${username}"的自定义配置！\n\n该用户现在将使用系统默认值。`
    // );
    Swal.fire({
      icon: "success",
      title: "删除成功",
      text: `已成功删除用户"${username}"的自定义配置！\n\n该用户现在将使用系统默认值。`,
    });

    console.log(`[水印控制] 成功删除用户"${username}"的配置`);

    // 重新加载配置以刷新显示
    await loadWatermarkControlConfig();
  } catch (error) {
    // ========== 错误处理 ==========
    console.error(`[水印控制] 删除用户"${username}"的配置失败:`, error);
    // showModalAlert(`删除配置失败：${error.message}`);
    Swal.fire({
      icon: "error",
      title: "删除失败",
      text: `删除失败：${error.message || "未知错误"}`,
    });
  }
}

/**
 * 打开添加水印控制用户的模态框
 *
 * 功能说明：
 * 显示一个模态框，列出所有尚未添加到水印控制配置的用户，
 * 允许管理员选择用户添加到配置列表中。
 *
 * 数据来源：
 * 从 /api/amap/watermark_control/config 获取所有用户列表和当前配置，
 * 然后筛选出未在配置中的用户。
 *
 * 操作流程：
 * 1. 获取当前配置（已有的用户列表）
 * 2. 获取所有系统用户
 * 3. 筛选出未配置的用户
 * 4. 显示可添加的用户列表
 * 5. 管理员点击"添加"按钮后，将用户添加到配置中（默认允许去水印）
 *
 * 【移动端兼容性说明】
 * 该函数已针对移动端进行优化，支持触摸事件和点击事件。
 * 如果在移动端遇到点击无响应的问题，请：
 * 1. 确保已切换到"水印控制"标签页（面板才会显示）
 * 2. 打开浏览器控制台查看是否有错误日志
 * 3. 尝试在控制台手动执行: openAddWatermarkUserModal()
 * 4. 检查网络连接是否正常（需要从服务器加载用户列表）
 */
async function openAddWatermarkUserModal() {
  // 【调试日志】记录函数调用，便于排查按钮点击是否生效
  console.log("[水印控制] openAddWatermarkUserModal() 函数被调用");

  try {
    // [步骤1] 显示模态框
    // 获取模态框元素
    const modal = document.getElementById("add-watermark-user-modal");
    if (!modal) {
      // 如果模态框不存在，记录错误并通过弹窗提示用户
      const errorMsg = "无法找到添加用户模态框元素，请刷新页面后重试";
      console.error("[水印控制] " + errorMsg);
      // 使用模态框提示用户，让错误更明显
      // showModalAlert(errorMsg, "错误");
      // 使用Swal.fire替代showModalAlert，提供更好的用户体验
      Swal.fire({
        icon: "error",
        title: "错误",
        text: errorMsg,
      });
      return;
    }

    // 移除hidden类，使模态框可见
    modal.classList.remove("hidden");
    // 【调试日志】确认模态框已成功打开
    console.log("[水印控制] 模态框已打开，开始加载用户列表...");

    // [步骤2] 显示加载状态
    console.log("[水印控制] 正在加载可添加的用户列表...");

    // 获取用户列表容器元素
    const listContainer = document.getElementById(
      "available-watermark-users-list",
    );
    if (!listContainer) {
      // 如果列表容器不存在，记录错误并通过弹窗提示用户
      const errorMsg = "无法找到用户列表容器元素，页面可能未正确加载";
      console.error("[水印控制] " + errorMsg);
      // 关闭模态框，因为无法显示内容
      modal.classList.add("hidden");
      // 使用模态框提示用户
      // showModalAlert(errorMsg, "错误");
      // 使用Swal.fire替代showModalAlert，提供更好的用户体验
      Swal.fire({
        icon: "error",
        title: "错误",
        text: errorMsg,
      });
      return;
    }

    // 显示"加载中..."提示
    listContainer.innerHTML =
      '<p class="text-slate-400 text-center py-10 text-sm">加载中...</p>';

    // [步骤3] 发送HTTP请求获取配置和用户列表
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 传递会话ID用于身份验证
      },
    });

    // [步骤4] 解析响应数据
    const data = await response.json();

    // 检查请求是否成功
    if (!data.success) {
      throw new Error(data.message || "获取用户列表失败");
    }

    // [步骤5] 提取数据
    // 获取当前已配置的用户列表
    const configuredUsers = data.config.users || {};

    // 获取所有系统用户列表
    // 【调试日志】记录API返回的用户数据，便于排查用户列表加载问题
    const allUsers = data.all_users || [];
    console.log(`[水印控制] API返回系统用户数: ${allUsers.length}`);
    console.log(`[水印控制] 已配置用户数: ${Object.keys(configuredUsers).length}`);

    // [步骤6] 筛选出未配置的用户
    // 只显示那些尚未在水印控制配置中的用户
    const availableUsers = allUsers.filter(
      (username) => !(username in configuredUsers),
    );

    // [步骤7] 生成用户列表HTML
    if (availableUsers.length === 0) {
      // 如果没有可添加的用户，显示提示信息
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-sm">所有用户都已添加到配置中</p>';
    } else {
      // 清空容器，准备添加用户项
      listContainer.innerHTML = "";

      // 为每个可添加的用户创建一个列表项
      availableUsers.forEach((username) => {
        // 创建用户项容器
        const userItem = document.createElement("div");
        // 添加CSS类：白色背景、圆角、边框、flex布局
        userItem.className =
          "bg-white p-3 rounded-lg border border-slate-200 flex items-center justify-between hover:bg-slate-50 transition-colors";
        // 为搜索功能添加data属性（存储原始用户名的小写形式用于搜索）
        userItem.setAttribute("data-username", username.toLowerCase());

        // [安全修复] 使用escapeHtml()函数转义用户名，防止XSS攻击
        // 转义后的用户名可以安全地插入到HTML中，避免特殊字符（如'<>"等）导致的安全问题
        const safeUsername = escapeHtml(username);

        // 构建HTML内容：用户名 + 添加按钮
        // 注意：按钮的onclick中也使用转义后的用户名，确保JavaScript字符串安全
        userItem.innerHTML = `
          <div class="flex-1">
            <span class="text-sm font-medium text-slate-700">${safeUsername}</span>
          </div>
          <button onclick="addWatermarkUser(${escapeInlineJsArg(username)})" class="px-3 py-1 bg-green-500 text-white text-xs rounded-md hover:bg-green-600 active:bg-green-700 transition-colors" title="添加此用户">
            <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
            </svg>
            添加
          </button>
        `;

        // 将用户项添加到列表容器中
        listContainer.appendChild(userItem);
      });
    }

    // [步骤8] 记录成功日志
    console.log(
      `[水印控制] ✓ 可添加用户列表加载完成，共 ${availableUsers.length} 个用户可添加`,
    );
    console.log("[水印控制] ✓ 模态框已成功打开并显示用户列表");
  } catch (error) {
    // [错误处理] 捕获所有可能的错误
    console.error("[水印控制] 加载可添加用户列表失败:", error);

    // 显示友好的错误提示，包含详细的错误信息
    // showModalAlert(
    //   "加载用户列表失败：" + error.message + "\n\n请检查网络连接或刷新页面重试。",
    //   "加载失败"
    // );
    // 使用Swal.fire替代showModalAlert，提供更好的用户体验
    Swal.fire({
      icon: "error",
      title: "加载失败",
      text: `加载用户列表失败：${error.message}\n\n请检查网络连接或刷新页面重试。`,
    });

    // 在列表容器中显示错误信息
    const listContainer = document.getElementById(
      "available-watermark-users-list",
    );
    if (listContainer) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-sm">加载失败：${error.message}</p>`;
    }
  }
}

/**
 * 关闭添加水印控制用户的模态框
 *
 * 功能说明：
 * 隐藏添加用户的模态框，并清空搜索框的内容。
 */
function closeAddWatermarkUserModal() {
  // [步骤1] 获取模态框元素
  const modal = document.getElementById("add-watermark-user-modal");
  if (!modal) {
    return;
  }

  // [步骤2] 添加hidden类，隐藏模态框
  modal.classList.add("hidden");

  // [步骤3] 清空搜索框内容
  const searchInput = document.getElementById("watermark-user-search");
  if (searchInput) {
    searchInput.value = "";
  }

  // [步骤4] 记录日志
  console.log("[水印控制] 已关闭添加用户模态框");
}

/**
 * 【诊断工具】检查添加水印用户模态框的状态
 *
 * 功能说明：
 * 这是一个诊断函数，用于排查"添加用户"按钮点击无效的问题。
 * 该函数会检查所有相关DOM元素是否存在，并输出详细的诊断信息。
 *
 * 使用方法：
 * 在浏览器控制台中执行: diagnoseAddWatermarkUserModal()
 *
 * 诊断项目：
 * 1. 检查模态框元素是否存在
 * 2. 检查用户列表容器是否存在
 * 3. 检查移动端面板是否可见
 * 4. 检查PC端面板是否可见
 * 5. 检查函数是否可访问
 * 6. 尝试手动触发模态框打开
 *
 * @returns {Object} 诊断结果对象，包含各项检查的状态
 */
function diagnoseAddWatermarkUserModal() {
  console.log("========================================");
  console.log("【水印控制诊断工具】开始诊断...");
  console.log("========================================");

  // 诊断结果对象
  const diagnosis = {
    timestamp: new Date().toISOString(),
    checks: {},
  };

  // 检查1: 模态框元素
  const modal = document.getElementById("add-watermark-user-modal");
  diagnosis.checks.modalExists = !!modal;
  console.log(
    `✓ 检查1: 模态框元素 (add-watermark-user-modal)`,
    modal ? "✓ 存在" : "✗ 不存在",
  );
  if (modal) {
    diagnosis.checks.modalVisible = !modal.classList.contains("hidden");
    console.log(
      `  - 当前状态:`,
      modal.classList.contains("hidden") ? "隐藏" : "可见",
    );
  }

  // 检查2: 用户列表容器
  const listContainer = document.getElementById(
    "available-watermark-users-list",
  );
  diagnosis.checks.listContainerExists = !!listContainer;
  console.log(
    `✓ 检查2: 用户列表容器 (available-watermark-users-list)`,
    listContainer ? "✓ 存在" : "✗ 不存在",
  );

  // 检查3: 移动端面板
  const mobilePanel = document.getElementById(
    "mobile-multi-admin-watermark-panel",
  );
  diagnosis.checks.mobilePanelExists = !!mobilePanel;
  console.log(
    `✓ 检查3: 移动端面板 (mobile-multi-admin-watermark-panel)`,
    mobilePanel ? "✓ 存在" : "✗ 不存在",
  );
  if (mobilePanel) {
    diagnosis.checks.mobilePanelVisible =
      !mobilePanel.classList.contains("hidden");
    console.log(
      `  - 当前状态:`,
      mobilePanel.classList.contains("hidden")
        ? "隐藏 (这是正常的，需要切换到水印控制标签)"
        : "可见",
    );
  }

  // 检查4: PC端按钮（通过搜索包含onclick属性的按钮）
  const buttons = document.querySelectorAll(
    'button[onclick*="openAddWatermarkUserModal"]',
  );
  diagnosis.checks.buttonsCount = buttons.length;
  console.log(`✓ 检查4: 找到 ${buttons.length} 个"添加用户"按钮`);
  buttons.forEach((btn, index) => {
    console.log(
      `  - 按钮 ${index + 1}:`,
      btn.offsetParent === null ? "不可见（父元素隐藏）" : "可见",
    );
  });

  // 检查5: 函数可访问性
  diagnosis.checks.functionAccessible =
    typeof openAddWatermarkUserModal === "function";
  console.log(
    `✓ 检查5: openAddWatermarkUserModal 函数`,
    diagnosis.checks.functionAccessible ? "✓ 可访问" : "✗ 不可访问",
  );

  // 检查6: Session UUID（API调用需要）
  diagnosis.checks.sessionUUID = typeof sessionUUID !== "undefined";
  console.log(
    `✓ 检查6: sessionUUID`,
    diagnosis.checks.sessionUUID
      ? `✓ 已定义 (${sessionUUID ? "有值" : "为空"})`
      : "✗ 未定义",
  );

  // 总结
  console.log("========================================");
  const allChecksPass = Object.values(diagnosis.checks).every(
    (v) => v === true || typeof v === "number",
  );
  if (allChecksPass) {
    console.log("✓ 所有检查通过！");
    console.log("💡 提示: 如果按钮仍然无效，请确保：");
    console.log("   1. 已切换到水印控制标签页");
    console.log("   2. 尝试手动执行: openAddWatermarkUserModal()");
  } else {
    console.log("✗ 发现问题，请查看上方详细信息");
  }
  console.log("========================================");

  // 返回诊断结果
  return diagnosis;
}

/**
 * 刷新水印用户列表
 *
 * 功能说明：
 * 重新加载可添加的用户列表，用于在添加用户后更新列表，
 * 或者手动刷新以获取最新的用户数据。
 *
 * 调用场景：
 * 1. 用户点击刷新按钮时
 * 2. 成功添加用户后自动调用
 *
 * 实现细节：
 * - 显示"加载中..."提示
 * - 重新调用openAddWatermarkUserModal的核心逻辑
 * - 不关闭模态框，保持用户体验流畅
 *
 * @returns {Promise<void>} 无返回值
 */
async function refreshWatermarkUserList() {
  try {
    // [步骤1] 显示加载状态
    console.log("[水印控制] 正在刷新用户列表...");

    // 获取用户列表容器元素
    const listContainer = document.getElementById(
      "available-watermark-users-list",
    );
    if (!listContainer) {
      console.error("[水印控制] 无法找到用户列表容器元素");
      return;
    }

    // 显示"加载中..."提示
    listContainer.innerHTML =
      '<p class="text-slate-400 text-center py-10 text-sm">刷新中...</p>';

    // [步骤2] 发送HTTP请求获取配置和用户列表
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID, // 传递会话ID用于身份验证
      },
    });

    // [步骤3] 解析响应数据
    const data = await response.json();

    // 检查请求是否成功
    if (!data.success) {
      throw new Error(data.message || "刷新用户列表失败");
    }

    // [步骤4] 提取数据
    // 获取当前已配置的用户列表
    const configuredUsers = data.config.users || {};

    // 获取所有系统用户列表
    // 【调试日志】记录API返回的用户数据
    const allUsers = data.all_users || [];
    console.log(`[水印控制] 刷新后的系统用户数: ${allUsers.length}`);
    console.log(
      `[水印控制] 刷新后的已配置用户数: ${Object.keys(configuredUsers).length}`,
    );

    // [步骤5] 筛选出未配置的用户
    const availableUsers = allUsers.filter(
      (username) => !(username in configuredUsers),
    );

    // [步骤6] 生成用户列表HTML
    if (availableUsers.length === 0) {
      // 如果没有可添加的用户，显示提示信息
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-sm">所有用户都已添加到配置中</p>';
    } else {
      // 清空容器，准备添加用户项
      listContainer.innerHTML = "";

      // 为每个可添加的用户创建一个列表项
      availableUsers.forEach((username) => {
        // 创建用户项容器
        const userItem = document.createElement("div");
        // 添加CSS类：白色背景、圆角、边框、flex布局
        userItem.className =
          "bg-white p-3 rounded-lg border border-slate-200 flex items-center justify-between hover:bg-slate-50 transition-colors";
        // 为搜索功能添加data属性
        userItem.setAttribute("data-username", username.toLowerCase());

        // [安全修复] 使用escapeHtml()函数转义用户名，防止XSS攻击
        const safeUsername = escapeHtml(username);

        // 构建HTML内容：用户名 + 添加按钮
        userItem.innerHTML = `
          <div class="flex-1">
            <span class="text-sm font-medium text-slate-700">${safeUsername}</span>
          </div>
          <button onclick="addWatermarkUser(${escapeInlineJsArg(username)})" class="px-3 py-1 bg-green-500 text-white text-xs rounded-md hover:bg-green-600 active:bg-green-700 transition-colors" title="添加此用户">
            <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
            </svg>
            添加
          </button>
        `;

        // 将用户项添加到列表容器中
        listContainer.appendChild(userItem);
      });
    }

    // [步骤7] 记录成功日志
    console.log(
      `[水印控制] 用户列表刷新完成，共 ${availableUsers.length} 个可添加用户`,
    );

    // [步骤8] 显示成功提示（可选，避免过多打扰）
    // 使用简短的Toast提示，而不是弹窗
    Swal.fire({
      icon: "success",
      title: "刷新成功",
      toast: true,
      position: "top-end",
      showConfirmButton: false,
      timer: 1500,
    });
  } catch (error) {
    // [错误处理] 捕获所有可能的错误
    console.error("[水印控制] 刷新用户列表失败:", error);

    // 显示错误提示
    // showModalAlert("刷新用户列表失败：" + error.message);
    Swal.fire({
      icon: "error",
      title: "刷新失败",
      text: `刷新用户列表失败：${error.message}\n\n请检查网络连接或刷新页面重试。`,
    });

    // 在列表容器中显示错误信息
    const listContainer = document.getElementById(
      "available-watermark-users-list",
    );
    if (listContainer) {
      listContainer.innerHTML = `<p class="text-red-500 text-center py-10 text-sm">刷新失败：${error.message}</p>`;
    }
  }
}

/**
 * 添加用户到水印控制配置
 *
 * 功能说明：
 * 将指定的用户添加到水印控制配置中，默认权限为"允许去水印"（true）。
 * 添加完成后，关闭模态框并重新加载配置，以在主面板中显示新添加的用户。
 *
 * 参数:
 * @param {string} username - 要添加的用户名
 *
 * 操作流程：
 * 1. 获取当前配置
 * 2. 将新用户添加到配置中（设为true）
 * 3. 保存配置到服务器
 * 4. 关闭模态框
 * 5. 重新加载主面板配置
 */
async function addWatermarkUser(username) {
  try {
    // [步骤1] 参数验证
    if (!username) {
      throw new Error("用户名不能为空");
    }

    // [步骤2] 记录操作日志
    console.log(`[水印控制] 正在添加用户 "${username}" 到配置...`);

    // [步骤3] 获取当前配置
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    const data = await response.json();
    if (!data.success) {
      throw new Error(data.message || "获取当前配置失败");
    }

    // [步骤4] 构建新的配置
    // 获取当前的用户配置
    const currentUsers = data.config.users || {};

    // 添加新用户，默认权限为true（允许去水印）
    currentUsers[username] = true;

    // 构建完整的配置对象
    const newConfig = {
      default: data.config.default, // 保持默认值不变
      users: currentUsers, // 使用更新后的用户配置
    };

    // [步骤5] 保存新配置到服务器
    const saveResponse = await fetch("/api/amap/watermark_control/config", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(newConfig),
    });

    const saveData = await saveResponse.json();
    if (!saveData.success) {
      throw new Error(saveData.message || "保存配置失败");
    }

    // [步骤6] 关闭模态框
    closeAddWatermarkUserModal();

    // [步骤7] 重新加载主面板配置，以显示新添加的用户
    await loadWatermarkControlConfig();

    // [步骤8] 显示成功提示
    // [安全修复] 使用escapeHtml()转义用户名，防止在提示信息中出现XSS漏洞
    const safeUsername = escapeHtml(username);
    // showModalAlert(`用户 "${safeUsername}" 已成功添加到水印控制配置！`);
    Swal.fire({
      icon: "success",
      title: "添加成功",
      text: `用户 "${safeUsername}" 已成功添加到水印控制配置！`,
    });

    // [步骤9] 记录成功日志
    console.log(`[水印控制] 用户 "${username}" 添加成功`);
  } catch (error) {
    // [错误处理] 捕获所有可能的错误
    console.error(`[水印控制] 添加用户 "${username}" 失败:`, error);

    // 显示错误提示
    // showModalAlert(`添加用户失败：${error.message}`);
    Swal.fire({
      icon: "error",
      title: "添加失败",
      text: `添加用户失败：${error.message}\n\n请检查网络连接或刷新页面重试。`,
    });
  }
}

/**
 * 搜索过滤可添加的用户
 *
 * 功能说明：
 * 根据搜索框中输入的关键词，过滤用户列表，只显示匹配的用户。
 * 匹配规则：用户名包含关键词（不区分大小写）。
 *
 * 操作流程：
 * 1. 获取搜索框中的关键词
 * 2. 转换为小写（不区分大小写）
 * 3. 遍历所有用户项
 * 4. 检查用户名是否包含关键词
 * 5. 显示或隐藏用户项
 */
function filterWatermarkUsers() {
  // [步骤1] 获取搜索框元素和关键词
  const searchInput = document.getElementById("watermark-user-search");
  if (!searchInput) {
    return;
  }

  // 获取搜索关键词，并转换为小写
  const keyword = searchInput.value.toLowerCase().trim();

  // [步骤2] 获取所有用户项元素
  const listContainer = document.getElementById(
    "available-watermark-users-list",
  );
  if (!listContainer) {
    return;
  }

  // 获取所有包含data-username属性的用户项
  const userItems = listContainer.querySelectorAll("[data-username]");

  // [步骤3] 遍历所有用户项，显示或隐藏
  let visibleCount = 0; // 统计可见的用户数量

  userItems.forEach((item) => {
    // 获取用户名（已经是小写）
    const username = item.getAttribute("data-username");

    // 检查用户名是否包含关键词
    if (!keyword || username.includes(keyword)) {
      // 包含关键词或搜索框为空，显示此用户项
      item.style.display = "";
      visibleCount++;
    } else {
      // 不包含关键词，隐藏此用户项
      item.style.display = "none";
    }
  });

  // [步骤4] 如果没有匹配的用户，显示提示信息
  // 检查是否有"无结果"提示元素
  let noResultsMsg = listContainer.querySelector(".no-results-message");

  if (visibleCount === 0 && userItems.length > 0) {
    // 没有匹配的用户，显示提示
    if (!noResultsMsg) {
      // 如果提示元素不存在，创建它
      noResultsMsg = document.createElement("p");
      noResultsMsg.className =
        "no-results-message text-slate-400 text-center py-10 text-sm";
      noResultsMsg.textContent = `未找到匹配 "${keyword}" 的用户`;
      listContainer.appendChild(noResultsMsg);
    } else {
      // 如果提示元素已存在，更新文本
      noResultsMsg.textContent = `未找到匹配 "${keyword}" 的用户`;
      noResultsMsg.style.display = "";
    }
  } else if (noResultsMsg) {
    // 有匹配的用户，隐藏提示
    noResultsMsg.style.display = "none";
  }

  // [步骤5] 记录调试日志
  console.log(
    `[水印控制] 搜索关键词: "${keyword}", 匹配用户数: ${visibleCount}`,
  );
}

/**
 * 加载水印控制配置（移动端）
 *
 * 功能说明：
 * 与PC端的 loadWatermarkControlConfig() 功能相同，但操作移动端的表单元素。
 * 支持两个移动端面板：
 * 1. mobile-multi-admin-watermark-panel（查看面板，显示所有用户）
 * 2. mobile-multi-admin-watermark-control-panel（配置面板，使用-ctrl后缀的ID）
 *
 * 表单元素：
 * - mobile-watermark-default-value / mobile-watermark-default-value-ctrl：显示系统默认值
 * - mobile-watermark-user-count / mobile-watermark-user-count-ctrl：显示用户总数
 * - mobile-watermark-users-list / mobile-watermark-users-list-ctrl：用户权限列表容器
 */
async function loadMobileWatermarkControlConfig() {
  try {
    // ========== 步骤1: 显示加载状态 ==========
    console.log("[水印控制] 正在加载水印控制配置（移动端）...");

    // 获取两个可能的列表容器（查看面板和配置面板）
    const listContainer = document.getElementById(
      "mobile-watermark-users-list",
    );
    const listContainerCtrl = document.getElementById(
      "mobile-watermark-users-list-ctrl",
    );

    // 为两个容器显示加载状态
    if (listContainer) {
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';
    }
    if (listContainerCtrl) {
      listContainerCtrl.innerHTML =
        '<p class="text-slate-400 text-center py-10 text-xs">加载中...</p>';
    }

    // ========== 步骤2: 发送HTTP请求获取配置 ==========
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
    });

    // ========== 步骤3: 解析响应数据 ==========
    const data = await response.json();

    // ========== 步骤4: 检查响应状态 ==========
    if (!data.success) {
      throw new Error(data.message || "获取水印控制配置失败");
    }

    // ========== 步骤5: 提取配置数据 ==========
    const config = data.config;
    const defaultValue = config.default;
    const usersConfig = config.users;
    const allUsers = data.all_users;

    // ========== 步骤6: 更新默认值开关（移动端）==========
    // 【问题45修复】找到移动端默认值开关元素（checkbox）
    const defaultCheckbox_Mobile = document.getElementById(
      "watermark-default-value-mobile",
    );
    if (defaultCheckbox_Mobile) {
      // 设置移动端开关状态（checked表示允许去水印）
      defaultCheckbox_Mobile.checked = defaultValue;
    }

    // 更新默认值标签显示（会同时更新PC端和移动端）
    updateWatermarkDefaultLabel();

    // 【兼容性】同时保留旧的只读显示更新（如果存在）
    // 更新查看面板的默认值显示（旧版，可能在其他地方使用）
    const defaultValueElement = document.getElementById(
      "mobile-watermark-default-value",
    );
    if (defaultValueElement) {
      defaultValueElement.textContent = defaultValue
        ? "允许去水印"
        : "禁止去水印";

      if (defaultValue) {
        defaultValueElement.className = "text-xs font-bold text-green-600";
      } else {
        defaultValueElement.className = "text-xs font-bold text-red-600";
      }
    }

    // 更新配置面板的默认值显示（旧版，可能在其他地方使用）
    const defaultValueElementCtrl = document.getElementById(
      "mobile-watermark-default-value-ctrl",
    );
    if (defaultValueElementCtrl) {
      defaultValueElementCtrl.textContent = defaultValue
        ? "允许去水印"
        : "禁止去水印";

      if (defaultValue) {
        defaultValueElementCtrl.className = "text-xs font-bold text-green-600";
      } else {
        defaultValueElementCtrl.className = "text-xs font-bold text-red-600";
      }
    }

    // ========== 步骤7: 更新用户数量显示（显示自定义用户数量）==========
    // 获取已自定义的用户数量（而非系统所有用户数量）
    const customizedUsersCount = Object.keys(usersConfig).length;

    // 更新查看面板的用户数量
    const userCountElement = document.getElementById(
      "mobile-watermark-user-count",
    );
    if (userCountElement) {
      userCountElement.textContent = `共 ${customizedUsersCount} 个自定义用户`;
    }

    // 更新配置面板的用户数量
    const userCountElementCtrl = document.getElementById(
      "mobile-watermark-user-count-ctrl",
    );
    if (userCountElementCtrl) {
      userCountElementCtrl.textContent = `共 ${customizedUsersCount} 个自定义用户`;
    }

    // ========== 步骤8: 生成用户权限列表（移动端样式）==========
    // 【修改】与PC端保持一致：只显示已自定义的用户（在usersConfig中的用户）
    // 为查看面板生成列表（仅显示自定义用户）
    if (listContainer) {
      // 清空当前内容
      listContainer.innerHTML = "";

      // 获取已自定义的用户列表（即在usersConfig中的用户）
      // 说明：只有在配置文件中明确设置过的用户才会显示在列表中
      const customizedUsers = Object.keys(usersConfig);

      // 判断是否有自定义用户
      if (customizedUsers.length === 0) {
        // 如果没有自定义用户，显示空状态提示
        listContainer.innerHTML =
          '<p class="text-slate-400 text-center py-10 text-xs">暂无已自定义的用户，点击右侧"添加"按钮添加</p>';
      } else {
        // 为每个已自定义的用户创建一个权限控制项
        customizedUsers.forEach((username) => {
          // 获取该用户的配置值（一定在usersConfig中）
          const userValue = usersConfig[username];

          // [安全修复] 使用escapeHtml()函数转义用户名，防止XSS攻击
          // 转义后的用户名可以安全地插入到HTML中，避免特殊字符（如'<>"等）导致的安全问题
          const safeUsername = escapeHtml(username);

          // 创建用户权限控制项的HTML元素
          const userItem = document.createElement("div");
          userItem.className =
            "bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between";

          // 移动端使用更紧凑的布局
          // 包含：用户名（带"已自定义"标签）+ 开关按钮
          userItem.innerHTML = `
            <div class="flex-1">
              <span class="text-xs font-medium text-slate-700">${safeUsername}</span>
              <p class="text-xs text-slate-500 mt-0.5">已自定义</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer ml-3">
              <input 
                type="checkbox" 
                id="mobile-watermark-user-${safeUsername}" 
                class="sr-only peer mobile-watermark-user-checkbox" 
                data-username="${safeUsername}"
                ${userValue ? "checked" : ""}
              >
              <div class="w-9 h-5 bg-slate-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          `;

          // 将用户项添加到列表容器中
          listContainer.appendChild(userItem);
        });
      }
    }

    // 为配置面板生成列表（仅显示自定义用户，与查看面板逻辑一致）
    if (listContainerCtrl) {
      // 清空当前内容
      listContainerCtrl.innerHTML = "";

      // 获取已自定义的用户列表（即在usersConfig中的用户）
      const customizedUsers = Object.keys(usersConfig);

      // 判断是否有自定义用户
      if (customizedUsers.length === 0) {
        // 如果没有自定义用户，显示空状态提示
        listContainerCtrl.innerHTML =
          '<p class="text-slate-400 text-center py-10 text-xs">暂无已自定义的用户，点击右侧"添加"按钮添加</p>';
      } else {
        // 为每个已自定义的用户创建一个权限控制项
        customizedUsers.forEach((username) => {
          // 获取该用户的配置值（一定在usersConfig中）
          const userValue = usersConfig[username];

          // [安全修复] 使用escapeHtml()函数转义用户名，防止XSS攻击
          const safeUsername = escapeHtml(username);

          // 创建用户权限控制项的HTML元素
          const userItem = document.createElement("div");
          userItem.className =
            "bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between";

          // 移动端使用更紧凑的布局
          // 包含：用户名（带"已自定义"标签）+ 开关按钮
          userItem.innerHTML = `
            <div class="flex-1">
              <span class="text-xs font-medium text-slate-700">${safeUsername}</span>
              <p class="text-xs text-slate-500 mt-0.5">已自定义</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer ml-3">
              <input 
                type="checkbox" 
                id="mobile-watermark-user-ctrl-${safeUsername}" 
                class="sr-only peer mobile-watermark-user-checkbox" 
                data-username="${safeUsername}"
                ${userValue ? "checked" : ""}
              >
              <div class="w-9 h-5 bg-slate-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          `;

          // 将用户项添加到列表容器中
          listContainerCtrl.appendChild(userItem);
        });
      }
    }

    // ========== 步骤9: 记录成功日志 ==========
    console.log("[水印控制] 配置加载成功（移动端）");
  } catch (error) {
    // ========== 错误处理 ==========
    console.error("[水印控制] 加载配置失败（移动端）:", error);
    alert("加载水印控制配置失败：" + error.message);

    // 在两个容器中显示错误信息
    const listContainer = document.getElementById(
      "mobile-watermark-users-list",
    );
    if (listContainer) {
      listContainer.innerHTML =
        '<p class="text-red-500 text-center py-10 text-xs">加载失败：' +
        error.message +
        "</p>";
    }

    const listContainerCtrl = document.getElementById(
      "mobile-watermark-users-list-ctrl",
    );
    if (listContainerCtrl) {
      listContainerCtrl.innerHTML =
        '<p class="text-red-500 text-center py-10 text-xs">加载失败：' +
        error.message +
        "</p>";
    }
  }
}

/**
 * 保存水印控制配置（移动端）
 *
 * 功能说明：
 * 与PC端的 saveWatermarkControlConfig() 功能相同，但操作移动端的表单元素。
 *
 * 【问题45修复】现在包含默认值的收集和保存
 * 原问题：移动端只保存用户配置，不保存默认值
 * 修复方案：参考PC端实现，同时收集默认值和用户配置
 */
async function saveMobileWatermarkControlConfig() {
  try {
    // ========== 步骤1: 收集默认值配置 ==========
    console.log("[水印控制] 正在收集配置数据（移动端）...");

    // 【问题45修复】获取移动端默认值开关的状态
    const defaultCheckbox = document.getElementById(
      "watermark-default-value-mobile",
    );
    const defaultValue = defaultCheckbox ? defaultCheckbox.checked : true;

    // ========== 步骤2: 收集用户配置数据 ==========
    const usersConfig = {};

    // 查找移动端的所有用户权限复选框
    const checkboxes = document.querySelectorAll(
      ".mobile-watermark-user-checkbox",
    );

    checkboxes.forEach((checkbox) => {
      const username = checkbox.getAttribute("data-username");
      const allowed = checkbox.checked;
      usersConfig[username] = allowed;
    });

    // ========== 步骤3: 构建请求体 ==========
    // 【问题45修复】添加默认值字段，与PC端保持一致
    const requestBody = {
      default: defaultValue, // 添加默认值字段
      users: usersConfig,
    };

    console.log(
      "[水印控制] 准备保存配置（移动端），用户数:",
      Object.keys(usersConfig).length,
    );

    // ========== 步骤3: 发送HTTP请求保存配置 ==========
    const response = await fetch("/api/amap/watermark_control/config", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify(requestBody),
    });

    // ========== 步骤4: 解析响应数据 ==========
    const data = await response.json();

    // ========== 步骤5: 检查响应状态 ==========
    if (!data.success) {
      throw new Error(data.message || "保存水印控制配置失败");
    }

    // ========== 步骤6: 显示成功提示（移动端使用alert）==========
    alert("水印控制配置已成功保存！");

    // ========== 步骤7: 记录成功日志 ==========
    console.log("[水印控制] 配置保存成功（移动端）");
  } catch (error) {
    // ========== 错误处理 ==========
    console.error("[水印控制] 保存配置失败（移动端）:", error);
    alert("保存水印控制配置失败：" + error.message);
  }
}

// ========================================
// 页面加载完成后的初始化逻辑
// ========================================

/**
 * DOMContentLoaded事件监听器
 *
 * 功能：在DOM完全加载和解析后立即执行初始化代码
 * 时机：HTML文档被完全加载和解析完成后触发，无需等待样式表、图像等资源
 *
 * 执行内容：
 * 1. 调用 loadPaymentMethodsConfig() 加载支付方式配置
 * 2. 其他页面初始化逻辑可以在这里添加
 *
 * 注意事项：
 * 1. 此事件在页面加载的早期阶段触发，确保配置尽早可用
 * 2. 如果有其他依赖PAYMENT_METHODS的初始化代码，应该在loadPaymentMethodsConfig()完成后执行
 */
document.addEventListener("DOMContentLoaded", function () {
  // 加载支付方式配置
  // 这是异步操作，会在后台执行，不阻塞其他初始化逻辑
  loadPaymentMethodsConfig(
    (show_Modal_Alert = false),
    (DOMContentLoaded_Event = true),
  );
});
