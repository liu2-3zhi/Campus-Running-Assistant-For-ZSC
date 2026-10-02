// Legacy admin user, school account, and permission management UI extracted from main.js.
function showCreateUserModal() {
  const modal = $("newUserModal");
  if (modal) {
    $("newUsername").value = "";
    $("newPassword").value = "";
    $("newUserPhone").value = "";
    $("newUserNickname").value = "";
    $("newUserSmsCode").value = "";
    $("newUserSmsGroup").style.display = "none";
    $("newUserModal").style.display = "flex";
    $("newPasswordConfirm").value = "";
    modal.style.display = "flex";

    // 监听手机号输入，显示/隐藏验证码区域
    const phoneInput = $("newUserPhone");
    phoneInput.oninput = () => {
      const phone = phoneInput.value.trim();
      $("newUserSmsGroup").style.display = phone ? "block" : "none";
    };

    const confirmBtn = $("newUserConfirm");
    confirmBtn.onclick = async () => {
      // ========== 步骤1：获取用户输入 ==========
      const inputUsername = $("newUsername").value.trim();
      const inputPassword = $("newPassword").value;
      const inputPhone = $("newUserPhone").value.trim();
      const inputNickname = $("newUserNickname").value.trim();
      const inputSmsCode = $("newUserSmsCode").value.trim();

      // ========== 步骤2：输入验证 ==========

      // 验证账号和密码是否为空
      if (!inputUsername || !inputPassword) {
        // showModalAlert("账号和密码均不能为空");
        Swal.fire({
          title: "错误",
          text: "账号和密码均不能为空",
          icon: "error",
        });
        return;
      }

      // 验证密码长度（至少6个字符）
      if (!inputPassword || inputPassword.length < 6) {
        // showModalAlert("密码长度至少为6个字符", "错误");
        Swal.fire({
          title: "错误",
          text: "密码长度至少为6个字符",
          icon: "error",
        });
        return;
      }

      // 如果填写了手机号，验证格式（中国大陆手机号：1开头的11位数字）
      if (inputPhone && !/^1[3-9]\d{9}$/.test(inputPhone)) {
        // showModalAlert("请输入正确的手机号格式", "错误");
        Swal.fire({
          title: "错误",
          text: "请输入正确的手机号格式",
          icon: "error",
        });
        return;
      }

      // ========== 步骤3：设置用户组 ==========
      // 新创建的用户默认属于 "user" 用户组
      const group = "user";

      // ========== 步骤4：显示加载状态 ==========
      setButtonLoading("newUserConfirm", true, "创建中...");

      try {
        // ========== 步骤5：调用后端API创建用户 ==========

        // 管理员创建用户API：/auth/admin/create_user
        //
        // available_runs（可用次数）处理说明：
        // - 此API请求中**不需要**传递 available_runs 参数
        // - 后端会自动从 .\configs\config.json 的 [Payment_Settings] -> default_available_runs 读取默认值
        // - 这确保了通过 PC端管理员界面（admin-create-user_modal）创建的用户
        //   与其他方式（移动端、自助注册）创建的用户使用统一的默认 available_runs
        // - 如需修改某个用户的 available_runs，请在用户创建后通过用户管理功能进行修改
        //
        // 请求参数说明：
        // - username: 用户名（必填）
        // - password: 密码（必填）
        // - group: 用户组（此处固定为 "user"）
        // - phone: 手机号（可选，如填写则会绑定到用户）
        // - nickname: 昵称（可选，如不填则使用用户名作为昵称）
        // - sms_code: 短信验证码（可选，如填写则会进行校验）
        const response = await fetch("/auth/admin/create_user", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-ID": sessionUUID, // 使用会话UUID进行身份验证
          },
          body: JSON.stringify({
            username: inputUsername,
            password: inputPassword,
            group: group,
            phone: inputPhone || "", // 空字符串表示未填写
            nickname: inputNickname || "", // 空字符串表示未填写
            sms_code: inputSmsCode || "", // 验证码可选，如非空则校验
          }),
        });

        // ========== 步骤6：解析API响应 ==========
        const result = await response.json();

        // ========== 步骤7：处理创建结果 ==========
        if (result.success) {
          // ===== 创建成功 =====
          // showModalAlert("用户创建成功！");
          Swal.fire({
            title: "成功",
            text: "用户创建成功！",
            icon: "success",
          });

          // 关闭创建用户模态框
          closeNewUserModal();

          // 刷新用户列表，显示新创建的用户
          if (typeof loadAdminUsers === "function") {
            // [修正] 创建成功后加载数据并同步UI
            await loadAdminUsers();

            // // 同步到移动端多账号面板
            // const multiAdminModal = document.getElementById(
            //   "mobile-multi-admin-panel-modal"
            // );
            // if (
            //   multiAdminModal &&
            //   !multiAdminModal.classList.contains("hidden")
            // ) {
            if (typeof copyAdminContentToMultiPanel === "function") {
              copyAdminContentToMultiPanel("users");
            }
            // }

            // 同步到移动端单账号面板
            const singleAdminModal = document.getElementById(
              "mobile-admin-panel-modal",
            );
            if (
              singleAdminModal &&
              !singleAdminModal.classList.contains("hidden")
            ) {
              // if (typeof copyAdminContentToPanelVersion === "function") {
              //   copyAdminContentToPanelVersion("users");
              // }
            }
          }
        } else {
          // ===== 创建失败 =====
          // showModalAlert(`创建失败: ${result.message || "未知错误"}`);
          Swal.fire({
            title: "错误",
            text: `创建失败: ${result.message || "未知错误"}`,
            icon: "error",
          });
        }
      } catch (e) {
        // ========== 异常处理 ==========
        // 捕获网络错误、解析错误等异常
        // showModalAlert(`创建时发生错误: ${e.message}`);
        Swal.fire({
          title: "错误",
          text: `创建时发生错误: ${e.message}`,
          icon: "error",
        });
        logMessage_Error("创建用户时发生错误:", e);
      } finally {
        // ========== 步骤8：恢复按钮状态 ==========
        // 无论成功或失败，都要恢复按钮的正常状态
        setButtonLoading("newUserConfirm", false, "确认");
      }
    };
  }
}

// ======创建权限组对话框
let currentEditGroupKey = null;
let currentManageUsername = null;

async function showCreateGroupModal() {
  const modal = $("create-group-modal");
  if (!modal) return;
  const keyInput = $("new-group-key");
  const nameInput = $("new-group-name");
  if (keyInput) keyInput.value = "";
  if (nameInput) nameInput.value = "";
  try {
    const response = await fetch("/auth/admin/list_groups", {
      headers: { "X-Session-ID": sessionUUID },
    });
    const result = await response.json();

    if (result.success && result.groups) {
      const firstGroup = Object.values(result.groups)[0];
      if (firstGroup && firstGroup.permissions) {
        const permissionsContainer = $("create-group-permissions");
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
    logMessage_Error("加载权限列表失败:", e);
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
}
function showSchoolAccountsModal() {
  const modal = $("school-accounts-modal");
  if (modal) {
    modal.style.display = "flex";
    loadSchoolAccounts();
  }
}

function closeSchoolAccountsModal() {
  const modal = $("school-accounts-modal");
  if (modal) {
    modal.style.display = "none";
  }
}
async function loadSchoolAccounts() {
  const content = $("school-accounts-content");
  if (!content) return;
  content.innerHTML =
    '<p class="text-slate-400 text-center py-10">加载中...</p>';

  try {
    const response = await fetch("/auth/admin/get_all_users_school_accounts", {
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });

    const data = await response.json();
    if (!data.success) {
      content.innerHTML = `<p class="text-red-500 text-center py-10">${
        data.message || "加载失败"
      }</p>`;
      return;
    }
    const allAccounts = data.all_accounts;
    if (Object.keys(allAccounts).length === 0) {
      content.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无数据</p>';
      return;
    }
    let html = "";
    for (const [authUsername, accounts] of Object.entries(allAccounts)) {
      const accountCount = Object.keys(accounts).length;

      html += `
            <div class="border border-slate-200 rounded-lg p-4 bg-slate-50">
              <!-- 标题行：显示认证用户名和账户数量，以及"添加 School Account"按钮 -->
              <div class="flex justify-between items-center mb-3">
                <h4 class="font-semibold text-slate-800">
                  认证用户: ${escapeHtml(authUsername)} 
                  <span class="text-sm text-slate-500">(${accountCount} 个学校账户)</span>
                </h4>
                <!-- "添加 School Account" 按钮 - 使用拟态风格 -->
                <button 
                  onclick="openSchoolAccountModal(${escapeInlineJsArg(
                    authUsername,
                  )})"
                  class="px-4 py-2 rounded-lg text-sm font-medium text-sky-600 bg-white border border-sky-300 hover:bg-sky-50 hover:border-sky-400 transition-all flex items-center gap-2"
                  style="box-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1), -1px -1px 2px rgba(255, 255, 255, 0.8);"
                  title="为此用户添加新的学校账号">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                  </svg>
                  添加账户
                </button>
              </div>
              
              <!-- 学校账户列表容器 -->
              <div class="space-y-2">
          `;

      if (accountCount === 0) {
        html +=
          '<p class="text-slate-400 text-sm">暂无学校账户，点击上方"添加账户"按钮开始添加</p>';
      } else {
        for (const [schoolUsername, accountData] of Object.entries(accounts)) {
          let password = "";
          let ua = "";

          if (typeof accountData === "string") {
            password = accountData;
          } else if (typeof accountData === "object" && accountData !== null) {
            password = accountData.password || "";
            ua = accountData.ua || "";
          }

          html += `
                <div class="bg-white p-3 rounded border border-slate-200 space-y-2">
                  <!-- 顶部行：学校用户名 + 编辑和删除按钮 -->
                  <div class="flex justify-between items-center">
                    <span class="font-medium text-slate-700">${escapeHtml(
                      schoolUsername,
                    )}</span>
                    
                    <!-- 操作按钮组 -->
                    <div class="flex gap-2">
                      <!-- 编辑按钮 - 拟态风格 -->
                      <button 
                        onclick="openSchoolAccountModal(${escapeInlineJsArg(
                          authUsername,
                        )}, ${escapeInlineJsArg(schoolUsername)}, ${escapeInlineJsArg(
                          password,
                        )}, ${escapeInlineJsArg(ua)})"
                        class="px-3 py-1.5 rounded-lg text-xs font-medium text-blue-600 bg-white border border-blue-300 hover:bg-blue-50 hover:border-blue-400 transition-all flex items-center gap-1"
                        style="box-shadow: 1px 1px 2px rgba(0, 0, 0, 0.08), -0.5px -0.5px 1px rgba(255, 255, 255, 0.8);"
                        title="编辑此学校账号">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        编辑
                      </button>
                      
                      <!-- 删除按钮 - 拟态风格 -->
                      <button 
                        onclick="deleteSchoolAccount(${escapeInlineJsArg(
                          authUsername,
                        )}, ${escapeInlineJsArg(schoolUsername)})"
                        class="px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 bg-white border border-red-300 hover:bg-red-50 hover:border-red-400 transition-all flex items-center gap-1"
                        style="box-shadow: 1px 1px 2px rgba(0, 0, 0, 0.08), -0.5px -0.5px 1px rgba(255, 255, 255, 0.8);"
                        title="删除此学校账号">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        删除
                      </button>
                    </div>
                  </div>
                  
                  <!-- 密码显示行 -->
                  <div class="text-sm">
                    <span class="text-slate-500">密码:</span>
                    <span class="font-mono text-slate-600 ml-2">${escapeHtml(
                      password,
                    )}</span>
                  </div>
                  
                  <!-- UA 显示行（仅当 UA 存在时显示） -->
                  ${
                    ua
                      ? `
                  <div class="text-sm">
                    <span class="text-slate-500">UA:</span>
                    <span class="font-mono text-xs text-slate-600 ml-2 break-all">${escapeHtml(
                      ua,
                    )}</span>
                  </div>
                  `
                      : ""
                  }
                </div>
              `;
        }
      }

      html += `
              </div>
            </div>
          `;
    }

    content.innerHTML = html;
  } catch (error) {
    console.error("加载 school accounts 失败:", error);
    content.innerHTML =
      '<p class="text-red-500 text-center py-10">加载失败，请检查网络连接</p>';
  }
}

function openSchoolAccountModal(
  authUsername,
  schoolUsername = "",
  password = "",
  ua = "",
) {
  const modal = $("edit-school-account-modal");
  if (!modal) {
    logMessage_Error("School Account 编辑模态框不存在");
    return;
  }

  const authUsernameInput = $("edit-school-account-auth-username");
  const schoolUsernameInput = $("edit-school-account-school-username");
  const passwordInput = $("edit-school-account-password");
  const uaInput = $("edit-school-account-ua");
  const originalUsernameInput = $("edit-school-account-original-username");
  const modalTitle = $("edit-school-account-modal-title");

  if (
    !authUsernameInput ||
    !schoolUsernameInput ||
    !passwordInput ||
    !uaInput ||
    !originalUsernameInput
  ) {
    logMessage_Error("School Account 编辑表单元素不完整");
    return;
  }

  authUsernameInput.value = authUsername;
  schoolUsernameInput.value = schoolUsername;
  passwordInput.value = password;
  uaInput.value = ua;
  originalUsernameInput.value = schoolUsername;
  if (schoolUsername) {
    if (modalTitle) modalTitle.textContent = "编辑 School Account";
    schoolUsernameInput.readOnly = true;
    schoolUsernameInput.classList.add("bg-slate-100", "cursor-not-allowed");
  } else {
    if (modalTitle) modalTitle.textContent = "添加 School Account";
    schoolUsernameInput.readOnly = false;
    schoolUsernameInput.classList.remove("bg-slate-100", "cursor-not-allowed");
  }

  modal.classList.remove("hidden");
  modal.classList.add("flex");
  setTimeout(() => {
    if (schoolUsername) {
      passwordInput.focus();
    } else {
      schoolUsernameInput.focus();
    }
  }, 300);
}
function closeEditSchoolAccountModal() {
  const modal = $("edit-school-account-modal");
  if (!modal) return;
  modal.classList.add("hidden");
  modal.classList.remove("flex");
  const authUsernameInput = $("edit-school-account-auth-username");
  const schoolUsernameInput = $("edit-school-account-school-username");
  const passwordInput = $("edit-school-account-password");
  const uaInput = $("edit-school-account-ua");
  const originalUsernameInput = $("edit-school-account-original-username");

  if (authUsernameInput) authUsernameInput.value = "";
  if (schoolUsernameInput) {
    schoolUsernameInput.value = "";
    schoolUsernameInput.readOnly = false;
    schoolUsernameInput.classList.remove("bg-slate-100", "cursor-not-allowed");
  }
  if (passwordInput) passwordInput.value = "";
  if (uaInput) uaInput.value = "";
  if (originalUsernameInput) originalUsernameInput.value = "";
}

async function submitSchoolAccount() {
  const authUsernameInput = $("edit-school-account-auth-username");
  const schoolUsernameInput = $("edit-school-account-school-username");
  const passwordInput = $("edit-school-account-password");
  const uaInput = $("edit-school-account-ua");
  const originalUsernameInput = $("edit-school-account-original-username");
  if (
    !authUsernameInput ||
    !schoolUsernameInput ||
    !passwordInput ||
    !uaInput ||
    !originalUsernameInput
  ) {
    // showModalAlert("表单元素不完整，无法提交", "错误");
    Swal.fire({
      title: "错误",
      text: "表单元素不完整，无法提交",
      icon: "error",
    });
    return;
  }
  const authUsername = authUsernameInput.value.trim();
  const schoolUsername = schoolUsernameInput.value.trim();
  const password = passwordInput.value.trim();
  const ua = uaInput.value.trim();
  const originalUsername = originalUsernameInput.value.trim();

  if (!authUsername) {
    // showModalAlert("认证用户名不能为空", "验证失败");
    Swal.fire({
      title: "错误",
      text: "认证用户名不能为空",
      icon: "error",
    });
    return;
  }

  if (!schoolUsername) {
    // showModalAlert("学校账号用户名不能为空", "验证失败");
    Swal.fire({
      title: "错误",
      text: "学校账号用户名不能为空",
      icon: "error",
    });
    schoolUsernameInput.focus();
    return;
  }

  if (!password) {
    // showModalAlert("密码不能为空", "验证失败");
    Swal.fire({
      title: "错误",
      text: "密码不能为空",
      icon: "error",
    });
    passwordInput.focus();
    return;
  }
  const data = {
    auth_username: authUsername,
    school_username: schoolUsername,
    password: password,
    ua: ua || null,
  };
  if (originalUsername) {
    data.original_username = originalUsername;
  }

  try {
    const result = await callPythonAPI_raw(
      "/api/admin/school_account/save",
      "POST",
      data,
    );
    if (result.success) {
      // showModalAlert(
      //   originalUsername ? "学校账号更新成功" : "学校账号添加成功",
      //   "成功"
      // );
      Swal.fire({
        title: "成功",
        text: originalUsername ? "学校账号更新成功" : "学校账号添加成功",
        icon: "success",
      });
      closeEditSchoolAccountModal();

      // 刷新全局列表（如果有）
      loadSchoolAccounts();

      // 如果当前打开了单个用户的管理模态框，也需要刷新该列表
      const manageModal = $("manage-school-accounts-modal");
      if (manageModal && !manageModal.classList.contains("hidden")) {
        // authUsername 是该函数前面获取的变量，正好对应当前操作的认证用户名
        await showUserSchoolAccounts(authUsername);
      }
    } else {
      // showModalAlert(result.message || "保存失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "保存失败",
        icon: "error",
      });
    }
  } catch (error) {
    logMessage_Error("保存 School Account 失败:", error);
    // showModalAlert("保存失败，请检查网络连接: " + error.message, "错误");
    Swal.fire({
      title: "错误",
      text: "保存失败，请检查网络连接: " + error.message,
      icon: "error",
    });
  }
}
async function deleteSchoolAccount(authUsername, schoolUsername) {
  const confirmed = await jsShowConfirm(
    "确认删除",
    `您确定要删除学校账号 "${schoolUsername}" 吗？\n此操作不可恢复。`,
  );
  if (!confirmed) {
    return;
  }

  try {
    const result = await callPythonAPI_raw(
      "/api/admin/school_account/delete",
      "POST",
      {
        auth_username: authUsername,
        school_username: schoolUsername,
      },
    );

    if (result.success) {
      // showModalAlert("学校账号删除成功", "成功");
      Swal.fire({
        title: "成功",
        text: "学校账号删除成功",
      });
      loadSchoolAccounts();
    } else {
      // showModalAlert(result.message || "删除失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "删除失败",
        icon: "error",
      });
    }
  } catch (error) {
    logMessage_Error("删除 School Account 失败:", error);
    // showModalAlert("删除失败，请检查网络连接: " + error.message, "错误");
    Swal.fire({
      title: "错误",
      text: "删除失败，请检查网络连接: " + error.message,
      icon: "error",
    });
  }
}

function closeCreateGroupModal() {
  const modal = $("create-group-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
}

async function submitCreateGroup() {
  const keyInput = $("new-group-key");
  const nameInput = $("new-group-name");

  if (!keyInput || !nameInput) return;

  const groupKey = keyInput.value.trim();
  const groupName = nameInput.value.trim();

  if (!groupKey || !nameInput) {
    // showModalAlert("请填写权限组键名和名称", "错误");
    Swal.fire({
      title: "错误",
      text: "请填写权限组键名和名称",
      icon: "error",
    });
    return;
  }

  const permissionsContainer = $("create-group-permissions");
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
      // showModalAlert(`权限组 ${groupName} 创建成功`, "成功");
      Swal.fire({
        title: "成功",
        text: `权限组 ${groupName} 创建成功`,
        icon: "success",
      });
      closeCreateGroupModal();
      loadAdminGroups();
    } else {
      // showModalAlert(result.message || "创建失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "创建失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

// ========== 用户列表排序 ==========
let _adminUsersCacheData = null; // 缓存用户列表数据 { users, groups }
let _adminUsersSortField = "created_at"; // 当前排序字段
let _adminUsersSortDir = "desc"; // 当前排序方向: "asc" | "desc"

function _sortAdminUsersArray(users, field, dir) {
  const sorted = [...users];
  sorted.sort((a, b) => {
    let va, vb;
    if (field === "tfa") {
      va = a["2fa_enabled"] || a["tfa_enabled"] ? 1 : 0;
      vb = b["2fa_enabled"] || b["tfa_enabled"] ? 1 : 0;
    } else if (field === "auth_username" || field === "nickname") {
      va = (a[field] || "").toLowerCase();
      vb = (b[field] || "").toLowerCase();
    } else if (field === "max_sessions") {
      // -1 表示无限制，排序时视为极大值
      va = a[field] === -1 ? Infinity : (a[field] ?? 0);
      vb = b[field] === -1 ? Infinity : (b[field] ?? 0);
    } else if (field === "available_runs") {
      va = a[field] === -1 ? Infinity : (a[field] ?? 0);
      vb = b[field] === -1 ? Infinity : (b[field] ?? 0);
    } else {
      // 数值型字段：created_at、last_login
      va = a[field] ?? 0;
      vb = b[field] ?? 0;
    }
    if (va < vb) return dir === "asc" ? -1 : 1;
    if (va > vb) return dir === "asc" ? 1 : -1;
    return 0;
  });
  return sorted;
}

function _syncAdminUsersSortUI() {
  const dirLabel = _adminUsersSortDir === "asc" ? "↑ 升序" : "↓ 降序";
  ["admin-users-sort-dir_modal", "mobile-admin-users-sort-dir"].forEach(
    (id) => {
      const btn = document.getElementById(id);
      if (btn) {
        btn.textContent = dirLabel;
        btn.dataset.dir = _adminUsersSortDir;
      }
    },
  );
  ["admin-users-sort-field_modal", "mobile-admin-users-sort-field"].forEach(
    (id) => {
      const sel = document.getElementById(id);
      if (sel) sel.value = _adminUsersSortField;
    },
  );
}

function resortAdminUsers() {
  // 从触发变更的控件读取排序字段
  const pcField = document.getElementById("admin-users-sort-field_modal");
  const mobileField = document.getElementById("mobile-admin-users-sort-field");
  // 使用当前可见或最近修改的控件值
  if (
    document.activeElement &&
    document.activeElement.id === "mobile-admin-users-sort-field" &&
    mobileField
  ) {
    _adminUsersSortField = mobileField.value;
  } else if (pcField) {
    _adminUsersSortField = pcField.value;
  } else if (mobileField) {
    _adminUsersSortField = mobileField.value;
  }
  _rerenderAdminUsersList();
}

function toggleAdminUsersSort() {
  _adminUsersSortDir = _adminUsersSortDir === "desc" ? "asc" : "desc";
  _rerenderAdminUsersList();
}

function _rerenderAdminUsersList() {
  if (!_adminUsersCacheData) return;
  const { users, groups } = _adminUsersCacheData;
  const sorted = _sortAdminUsersArray(
    users,
    _adminUsersSortField,
    _adminUsersSortDir,
  );
  _syncAdminUsersSortUI();

  const groupSelect = (user) => `
    <select class="text-sm border border-slate-300 rounded px-2 py-1" onchange="updateUserGroup('${
      user.auth_username
    }', this.value)">
      ${groups.map((g) => `<option value="${g}" ${g === user.group ? "selected" : ""}>${g}</option>`).join("")}
    </select>`;

  const listHtml = sorted
    .map((user) => {
      const createdDate = new Date(user.created_at * 1000).toLocaleString();
      const lastLoginDate = user.last_login
        ? new Date(user.last_login * 1000).toLocaleString()
        : "从未登录";
      const isBanned = user.banned || false;
      const bannedBadge = isBanned
        ? '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full ml-2">已封禁</span>'
        : "";
      return `
      <div class="border border-slate-200 rounded-lg p-3 mb-2">
        <div class="flex flex-col md:flex-row justify-between items-start gap-3">
          <div class="flex items-start gap-3 flex-1 w-full md:w-auto">
            <div id="avatar-${user.auth_username}" class="flex-shrink-0 w-16 h-16 rounded-full bg-slate-200 flex items-center justify-center overflow-hidden border-2 border-slate-300">
              <span class="text-2xl text-slate-400">👤</span>
            </div>
            <div class="flex-1">
              <p class="font-semibold text-slate-800">${user.auth_username}${bannedBadge}</p>
              <p class="text-xs text-slate-500">昵称: ${user.nickname || "未设置"}</p>
              <p class="text-xs text-slate-500">手机号: ${user.phone || "未绑定"}<span class="phone-location-badge" data-phone="${user.phone || ""}"></span></p>
              <p class="text-xs text-slate-500">创建时间: ${createdDate}</p>
              <p class="text-xs text-slate-500">最后登录: ${lastLoginDate}</p>
              <p class="text-xs text-slate-500">登录IP: ${user.last_login_ip || "无记录"} (${user.last_login_city || "未知"})</p>
              <p class="text-xs text-slate-500">会话限制: ${user.max_sessions === -1 ? "无限制" : user.max_sessions + "个"}</p>
              <p class="text-xs text-slate-500">
                可用次数:
                <span id="available-runs-${user.auth_username}" class="${
                  user.available_runs === -1
                    ? "text-green-600 font-semibold"
                    : user.available_runs === 0
                      ? "text-red-600 font-semibold"
                      : "text-blue-600 font-semibold"
                }">
                  ${user.available_runs === -1 ? "无限制" : user.available_runs + "次"}
                </span>
              </p>
              <p class="text-xs ${user["2fa_enabled"] || user.tfa_enabled ? "text-green-600" : "text-slate-400"}">2FA: ${user["2fa_enabled"] || user.tfa_enabled ? "已启用" : "未启用"}</p>
            </div>
          </div>
          <div class="flex flex-col md:items-end gap-1 w-full md:w-auto mt-2 md:mt-0">
            <div class="flex justify-between md:justify-end items-center w-full">
              <span class="text-xs text-slate-600 mr-2">权限组:</span>
              ${groupSelect(user)}
            </div>
            <div class="flex flex-col gap-1.5 mt-2 w-full" id="user-actions-${user.auth_username}">
              <div class="grid grid-cols-3 md:grid-cols-6 gap-2 w-full p-2 bg-base-100 rounded-xl border border-base-200 shadow-sm">
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border-indigo-100 border" onclick="showUserSchoolAccounts(${escapeInlineJsArg(user.auth_username)})">账户密码</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-blue-50 text-blue-600 hover:bg-blue-100 border-blue-100 border" onclick="showUserLogs(${escapeInlineJsArg(user.auth_username)})">查看日志</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-blue-50 text-blue-600 hover:bg-blue-100 border-blue-100 border" onclick="setUserMaxSessions(${escapeInlineJsArg(user.auth_username)}, ${user.max_sessions || 1})">会话管理</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-cyan-50 text-cyan-600 hover:bg-cyan-100 border-cyan-100 border" onclick="editAvailableRuns(${escapeInlineJsArg(user.auth_username)}, ${user.available_runs !== undefined ? user.available_runs : 0})">修改次数</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 border-emerald-100 border" onclick="manageUserPermissions(${escapeInlineJsArg(user.auth_username)})">权限设置</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-teal-50 text-teal-600 hover:bg-teal-100 border-teal-100 border" onclick="modifyUserNickname(${escapeInlineJsArg(user.auth_username)}, ${escapeInlineJsArg(user.nickname || "")})">修改昵称</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-teal-50 text-teal-600 hover:bg-teal-100 border-teal-100 border" onclick="modifyUserPhone(${escapeInlineJsArg(user.auth_username)}, ${escapeInlineJsArg(user.phone || "")})">修改手机</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-purple-50 text-purple-600 hover:bg-purple-100 border-purple-100 border" onclick="resetUserPassword(${escapeInlineJsArg(user.auth_username)})">重置密码</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-amber-50 text-amber-600 hover:bg-amber-100 border-amber-100 border" onclick="forceLogoutUser(${escapeInlineJsArg(user.auth_username)})">强制登出</button>
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-rose-50 text-rose-600 hover:bg-rose-100 border-rose-100 border" onclick="clearUserAvatar(${escapeInlineJsArg(user.auth_username)})">清除头像</button>
                ${
                  user["2fa_enabled"] || user.tfa_enabled
                    ? `<button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-orange-50 text-orange-600 hover:bg-orange-100 border-orange-100 border" onclick="forceDisable2FA(${escapeInlineJsArg(user.auth_username)})">关闭2FA</button>`
                    : `<button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-slate-50 text-slate-300 border-slate-200 border cursor-not-allowed" disabled onclick="forceDisable2FA(${escapeInlineJsArg(user.auth_username)})">2FA未启用</button>`
                }
                ${
                  isBanned
                    ? `<button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-green-100 text-green-700 hover:bg-green-200 border-green-200 border font-bold" onclick="unbanUser(${escapeInlineJsArg(user.auth_username)})">解封用户</button>`
                    : `<button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-red-100 text-red-700 hover:bg-red-200 border-red-200 border font-bold" onclick="banUser(${escapeInlineJsArg(user.auth_username)})">封禁用户</button>`
                }
                <button class="btn !btn-xs !h-7 !min-h-0 !text-xs flex-1 bg-red-600 text-white hover:bg-red-700 border-red-600 border shadow-md" onclick="deleteUser(${escapeInlineJsArg(user.auth_username)})">彻底删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    })
    .join("");

  const listEl = $("admin-users-list_modal");
  if (listEl) {
    listEl.innerHTML = listHtml;
    listEl.querySelectorAll(".phone-location-badge[data-phone]").forEach(async (span) => {
      const phone = span.dataset.phone;
      if (!phone) return;
      const info = await fetchPhoneInfo(phone);
      span.innerHTML = _phoneInfoBadge(info);
    });
  }

  // 重新同步到移动端并重新绑定移动端按钮事件处理器
  if (typeof copyAdminContentToMultiPanel === "function") {
    copyAdminContentToMultiPanel("users");
  }

  // 重新加载用户头像
  sorted.forEach((user) => loadUserAvatar(user.auth_username));
}

// 手机号归属地查询缓存
const _phoneInfoCache = {};
async function fetchPhoneInfo(phone) {
  if (!phone || phone === "未绑定") return null;
  const key = String(phone).replace(/\D/g, "");
  if (!key) return null;
  if (_phoneInfoCache[key] !== undefined) return _phoneInfoCache[key];
  try {
    const resp = await fetch(`/api/phone_info?phone=${encodeURIComponent(key)}`, {
      headers: { "X-Session-ID": sessionUUID },
    });
    const data = await resp.json();
    const result = data.success ? { province: data.province || "", city: data.city || "", sp: data.sp || "" } : null;
    _phoneInfoCache[key] = result;
    return result;
  } catch {
    _phoneInfoCache[key] = null;
    return null;
  }
}
function _phoneInfoBadge(info) {
  if (!info) return "";
  const parts = [info.province, info.city, info.sp].filter(Boolean);
  if (!parts.length) return "";
  return ` <span class="text-[11px] text-slate-400">(${parts.join(" ")})</span>`;
}
// 在 phone input 旁边显示归属地（找或创建 .phone-location-tag span）
async function _showPhoneLocationNearInput(inputEl, phone) {
  if (!inputEl) return;
  let tag = inputEl.parentElement && inputEl.parentElement.querySelector(".phone-location-tag");
  if (!tag) {
    tag = document.createElement("span");
    tag.className = "phone-location-tag text-[11px] text-slate-400 ml-1";
    inputEl.insertAdjacentElement("afterend", tag);
  }
  tag.textContent = "";
  if (!phone || phone === "未绑定") return;
  const info = await fetchPhoneInfo(phone);
  if (info) {
    const parts = [info.province, info.city, info.sp].filter(Boolean);
    if (parts.length) tag.textContent = `(${parts.join(" ")})`;
  }
}

async function loadAdminUsers(keywordOverride = null) {
  try {
    const keywordInput = document.getElementById("admin-users-search-input_modal");
    const mobileKeywordInput = document.getElementById(
      "mobile-multi-admin-users-search-input",
    );
    const keyword =
      keywordOverride != null
        ? String(keywordOverride).trim()
        : keywordInput?.value.trim() || mobileKeywordInput?.value.trim() || "";
    const response = await fetch(
      keyword
        ? `/auth/admin/list_users?keyword=${encodeURIComponent(keyword)}`
        : "/auth/admin/list_users",
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );
    const result = await response.json();

    if (keywordInput && mobileKeywordInput) {
      if (document.activeElement === mobileKeywordInput) {
        keywordInput.value = keyword;
      } else {
        mobileKeywordInput.value = keyword;
      }
    } else if (keywordInput) {
      keywordInput.value = keyword;
    } else if (mobileKeywordInput) {
      mobileKeywordInput.value = keyword;
    }

    if (!result.success) {
      const errorHtml = `<p class="text-red-500 text-center py-10">${result.message}</p>`;
      const listEl = $("admin-users-list_modal");
      if (listEl) listEl.innerHTML = errorHtml;
      return;
    }

    const listEl = $("admin-users-list_modal");
    if (result.users.length === 0) {
      listEl.innerHTML =
        '<p class="text-slate-400 text-center py-10">暂无用户</p>';
      if (typeof copyAdminContentToMultiPanel === "function") {
        copyAdminContentToMultiPanel("users");
      }
      return;
    }
    const groupsResp = await fetch("/auth/admin/list_groups", {
      headers: {
        "X-Session-ID": sessionUUID,
      },
    });
    const groupsData = await groupsResp.json();
    const groups = groupsData.success
      ? Object.keys(groupsData.groups)
      : ["guest", "user", "admin"];

    // 缓存数据并使用排序渲染
    _adminUsersCacheData = { users: result.users, groups };
    _rerenderAdminUsersList();
  } catch (e) {
    const listEl = $("admin-users-list_modal");
    if (listEl) {
      listEl.innerHTML = `<p class="text-red-500 text-center py-10">加载失败: ${e.message}</p>`;
    }
  }
}

async function updateUserGroup(username, newGroup) {
  try {
    const response = await fetch("/auth/admin/update_user_group", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        target_username: username,
        new_group: newGroup,
      }),
    });

    const result = await response.json();
    if (result.success) {
      logMessage_Info(`用户 ${username} 的权限组已更新为 ${newGroup}`);
    } else {
      // showModalAlert(`更新失败: ${result.message}`, "操作失败");
      Swal.fire({
        title: "操作失败",
        text: `更新失败: ${result.message}`,
        icon: "error",
      });
      // [修正] 等待PC端列表刷新完成后，同步到移动端，实现回退效果
      await loadAdminUsers();
      if (typeof copyAdminContentToMultiPanel === "function")
        copyAdminContentToMultiPanel("users");
      if (typeof copyAdminContentToPanelVersion === "function")
        copyAdminContentToPanelVersion("users");
    }
  } catch (e) {
    // showModalAlert(`更新失败: ${e.message}`, "网络错误");
    Swal.fire({
      title: "网络失败",
      text: `更新失败: ${e.message}`,
      icon: "error",
    });
    // [修正] 等待PC端列表刷新完成后，同步到移动端，实现回退效果
    await loadAdminUsers();
    if (typeof copyAdminContentToMultiPanel === "function")
      copyAdminContentToMultiPanel("users");
    if (typeof copyAdminContentToPanelVersion === "function")
      copyAdminContentToPanelVersion("users");
  }
}

// ====================
// 用户管理功能函数
// ====================
async function banUser(username) {
  const confirmed = await jsShowConfirm(
    "确认封禁",
    `确定要封禁用户 ${username} 吗？`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/ban_user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${username} 已被封禁`, "成功");
      // showModalAlert(`用户usernameusername} 已被封禁`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 已被封禁`,
        icon: "success",
      });

      // [修正] 统一调用一次刷新，避免并发竞争导致头像丢失
      loadAdminUsers().then(() => {
        // 同步到移动端多账号面板
        if (typeof copyAdminContentToMultiPanel === "function") {
          copyAdminContentToMultiPanel("users");
        }
        // 同步到移动端单账号面板
        if (typeof copyAdminContentToPanelVersion === "function") {
          copyAdminContentToPanelVersion("users");
        }
      });
    } else {
      // showModalAlert(result.message || "封禁失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "封禁失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function unbanUser(username) {
  const confirmed = await jsShowConfirm(
    "确认解封",
    `确定要解封用户 ${username} 吗？`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/unban_user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${username} 已解封`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 已解封`,
        icon: "success",
      });

      // [修正] 统一调用一次刷新，避免并发竞争导致头像丢失
      loadAdminUsers().then(() => {
        // 同步到移动端多账号面板
        if (typeof copyAdminContentToMultiPanel === "function") {
          copyAdminContentToMultiPanel("users");
        }
        // 同步到移动端单账号面板
        if (typeof copyAdminContentToPanelVersion === "function") {
          copyAdminContentToPanelVersion("users");
        }
      });
    } else {
      // showModalAlert(result.message || "解封失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "解封失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function forceDisable2FA(username) {
  const confirmed = await jsShowConfirm(
    "强制关闭2FA",
    `确定要为用户 ${username} 关闭双因素认证吗？`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/force_disable_2fa", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        target_username: username,
      }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${username} 的2FA已关闭`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 的2FA已关闭`,
        icon: "success",
      });
      // [修正] 统一调用一次刷新，避免并发竞争导致头像丢失
      loadAdminUsers().then(() => {
        if (typeof copyAdminContentToMultiPanel === "function") {
          copyAdminContentToMultiPanel("users");
        }
        if (typeof copyAdminContentToPanelVersion === "function") {
          copyAdminContentToPanelVersion("users");
        }
      });
    } else {
      // showModalAlert(result.message || "操作失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "操作失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function resetUserPassword(username) {
  const newPassword = await new Promise((resolve) => {
    const modal = document.createElement("div");
    modal.className = "fixed inset-0 flex items-center justify-center z-50";
    modal.innerHTML = `
          <div class="fixed inset-0 bg-black bg-opacity-50" onclick="this.parentElement.remove()"></div>
          <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4 relative z-10">
            <h3 class="text-lg font-semibold text-slate-800 mb-4">重置密码 - ${username}</h3>
            <div class="mb-4">
              <label class="block text-sm font-semibold text-slate-700 mb-2">新密码（至少6位）</label>
              <input type="password" id="reset-password-input" class="input-field w-full" placeholder="输入新密码">
            </div>
            <div class="flex gap-2 justify-end">
              <button class="btn btn-ghost" onclick="this.closest('.fixed').remove()">取消</button>
              <button class="btn btn-primary" id="confirm-reset-password">确认重置</button>
            </div>
          </div>
        `;
    document.body.appendChild(modal);

    const confirmBtn = modal.querySelector("#confirm-reset-password");
    const passwordInput = modal.querySelector("#reset-password-input");

    confirmBtn.onclick = () => {
      const password = passwordInput.value;
      if (!password || password.length < 6) {
        // showModalAlert("密码长度至少为6个字符", "错误");
        Swal.fire({
          title: "错误",
          text: "密码长度至少为6个字符",
          icon: "error",
        });
        return;
      }
      modal.remove();
      resolve(password);
    };
  });

  if (!newPassword) return;

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
      // showModalAlert(`用户 ${username} 的密码已重置`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 的密码已重置`,
        icon: "success",
      });
    } else {
      // showModalAlert(result.message || "重置失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "重置失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function deleteUser(username) {
  const confirmed = await jsShowConfirm(
    "确认删除",
    `确定要删除用户 ${username} 吗？\n此操作不可恢复！`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/delete_user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${username} 已删除`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 已删除`,
        icon: "success",
      });

      // [修正] 删除成功后重新加载数据，并强制同步UI到移动端面板
      // 按照要求执行 loadAdminUsers().then(...) 链式调用
      loadAdminUsers().then(() => {
        // 强制更新移动端多账号管理面板的用户列表
        if (typeof copyAdminContentToMultiPanel === "function") {
          copyAdminContentToMultiPanel("users");
        }

        // 同时更新移动端单账号管理面板的用户列表（保持一致性）
        if (typeof copyAdminContentToPanelVersion === "function") {
          copyAdminContentToPanelVersion("users");
        }
      });
    } else {
      // showModalAlert(result.message || "删除失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "删除失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

// ============================================================
// 新增：强制登出用户前端逻辑
// ============================================================
async function forceLogoutUser(username) {
  const confirmed = await jsShowConfirm(
    "确认强制登出",
    `确定要强制登出用户 <strong>${username}</strong> 吗？<br>该用户的所有活跃会话将被立即销毁。`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/force_logout_user", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username: username }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(result.message || "用户已强制登出", "成功", "success");
      Swal.fire({
        title: "成功",
        text: result.message || "用户已强制登出",
        icon: "success",
      });
      loadAdminUsers(); // 刷新列表以更新状态（虽然登出不会立即改变列表显示，但刷新是个好习惯）
    } else {
      // showModalAlert(result.message || "操作失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "操作失败",
        icon: "error",
      });
    }
  } catch (e) {
    console.error("强制登出失败:", e);
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

async function loadUserAvatar(username) {
  try {
    const response = await fetch(
      `/auth/user/avatar?username=${encodeURIComponent(username)}`,
      {
        headers: {
          "X-Session-ID": sessionUUID,
        },
      },
    );

    const result = await response.json();

    // 使用 querySelectorAll 获取所有匹配的头像容器
    // 解决 PC 端和移动端面板同时存在相同 ID 导致的更新错位问题
    const avatarDivs = document.querySelectorAll(`[id='avatar-${username}']`);

    if (avatarDivs.length === 0) return;

    avatarDivs.forEach((avatarDiv) => {
      if (result.success && result.avatar_url) {
        const avatarUrlWithSession = `${result.avatar_url}?session_id=${sessionUUID}`;
        avatarDiv.innerHTML = `<img src="${avatarUrlWithSession}" alt="${username}" class="w-full h-full object-cover" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" /><span class="text-2xl text-slate-400" style="display:none;">👤</span>`;
      } else {
        avatarDiv.innerHTML = `<span class="text-2xl text-slate-400">👤</span>`;
      }
    });
  } catch (e) {
    logMessage_Error(`加载用户头像失败 ${username}:`, e);
  }
}

async function clearUserAvatar(username) {
  const confirmed = await jsShowConfirm(
    "确认清除头像",
    `确定要清除用户 ${username} 的头像吗？`,
  );
  if (!confirmed) return;

  try {
    const response = await fetch("/auth/admin/clear_user_avatar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`已清除用户 ${username} 的头像`, "成功");
      Swal.fire({
        title: "成功",
        text: `已清除用户 ${username} 的头像`,
        icon: "success",
      });
      loadUserAvatar(username);
    } else {
      // showModalAlert(result.message || "清除失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "清除失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

function setUserMaxSessions(username, currentMax) {
  $("sessions-username").textContent = username;
  $("sessions-current-max").textContent =
    currentMax === -1 ? "无限制" : currentMax;
  $("new-max-sessions").value = currentMax === -1 ? 0 : currentMax;

  showModal("set-max-sessions-modal");
}

async function submitSetMaxSessions() {
  const username = $("sessions-username").textContent;
  const newMaxInput = $("new-max-sessions");
  const newMax = parseInt(newMaxInput.value);

  if (isNaN(newMax) || newMax < 0) {
    // showModalAlert("请输入有效的数字（0或更大）", "错误");
    Swal.fire({
      title: "错误",
      text: "请输入有效的数字（0或更大）",
      icon: "error",
    });
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
      // showModalAlert(
      //   `已更新用户 ${username} 的最大会话数为: ${
      //     maxSessions === -1 ? "无限制" : maxSessions
      //   }`,
      //   "成功"
      // );
      Swal.fire({
        title: "成功",
        text: `已更新用户 ${username} 的最大会话数为: ${
          maxSessions === -1 ? "无限制" : maxSessions
        }`,
        icon: "success",
      });
      hideModal("set-max-sessions-modal");
      loadAdminUsers();
    } else {
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

/**
 * 编辑用户的可用执行次数
 *
 * 功能说明：
 * 1. 弹出 SweetAlert2 输入框，让管理员输入新的可用次数
 * 2. 支持输入 -1 表示无限次数，0 表示无可用次数，正数表示具体次数
 * 3. 验证输入的合法性（必须是整数且 >= -1）
 * 4. 调用后端API更新用户的可用次数
 * 5. 更新成功后刷新用户列表显示
 *
 * @param {string} username - 要修改的用户名
 * @param {number} currentRuns - 当前的可用次数值
 */
async function editAvailableRuns(username, currentRuns) {
  // 步骤1：使用 SweetAlert2 弹出输入对话框
  // 提供友好的用户界面，让管理员输入新的可用次数值
  const { value: newRuns } = await Swal.fire({
    title: "修改可用执行次数", // 对话框标题
    html: `
            <div class="text-left mb-4">
              <p class="text-sm text-slate-600 mb-2">用户：<strong class="text-slate-800">${username}</strong></p>
              <p class="text-sm text-slate-600 mb-2">当前次数：<strong class="text-blue-600">${
                currentRuns === -1 ? "无限制" : currentRuns + "次"
              }</strong></p>
              <div class="bg-blue-50 border-l-4 border-blue-500 p-3 mt-3">
                <p class="text-xs text-blue-700">💡 提示：</p>
                <ul class="text-xs text-blue-600 mt-1 ml-4 list-disc">
                  <li>输入 <strong>-1</strong> 表示无限次数</li>
                  <li>输入 <strong>0</strong> 表示没有可用次数</li>
                  <li>输入正整数表示具体可用次数</li>
                </ul>
              </div>
            </div>
          `,
    input: "number", // 输入框类型为数字
    inputLabel: "请输入新的可用次数", // 输入框标签
    inputValue: currentRuns, // 默认值为当前的可用次数
    showCancelButton: true, // 显示取消按钮
    confirmButtonText: "确认修改", // 确认按钮文本
    cancelButtonText: "取消", // 取消按钮文本
    confirmButtonColor: "#3085d6", // 确认按钮颜色
    cancelButtonColor: "#d33", // 取消按钮颜色
    // 步骤2：输入验证器 - 在用户点击确认前验证输入的合法性
    inputValidator: (value) => {
      // 检查输入是否为空（允许输入0，所以需要特殊判断）
      if (value === null || value === undefined || value === "") {
        return "请输入有效的次数！";
      }

      // 将输入转换为整数
      const numValue = parseInt(value);

      // 检查是否为有效的整数
      if (isNaN(numValue)) {
        return "请输入有效的整数！";
      }

      // 检查取值范围：必须 >= -1
      // -1 表示无限次数，0 表示无可用次数，正数表示具体次数
      if (numValue < -1) {
        return "次数不能小于-1！（-1表示无限次数）";
      }

      // 验证通过，返回 undefined 表示没有错误
      return undefined;
    },
  });

  // 步骤3：检查用户是否点击了取消按钮
  // 如果 newRuns 为 undefined，说明用户取消了操作，直接返回
  if (newRuns === undefined) {
    return;
  }

  // 步骤4：调用更新函数，将新的可用次数发送到后端
  await updateAvailableRuns(username, parseInt(newRuns));
}

/**
 * 更新用户的可用执行次数（调用后端API）
 *
 * 功能说明：
 * 1. 发送 POST 请求到后端 API
 * 2. 传递用户名和新的可用次数值
 * 3. 处理响应结果，显示成功或失败消息
 * 4. 成功后刷新用户列表以更新显示
 *
 * @param {string} username - 要修改的用户名
 * @param {number} newRuns - 新的可用次数值
 */
async function updateAvailableRuns(username, newRuns) {
  try {
    // 步骤1：显示加载提示，告知用户正在处理
    Swal.fire({
      title: "处理中...",
      text: "正在更新可用次数",
      allowOutsideClick: false, // 禁止点击外部关闭
      allowEscapeKey: false, // 禁止按ESC键关闭
      didOpen: () => {
        Swal.showLoading(); // 显示加载动画
      },
    });

    // 步骤2：发送 POST 请求到后端 API
    const response = await fetch("/api/admin/update_available_runs", {
      method: "POST", // HTTP方法为POST
      headers: {
        "Content-Type": "application/json", // 请求体格式为JSON
        "X-Session-ID": sessionUUID, // 传递会话ID用于身份验证
      },
      // 步骤3：将请求数据转换为JSON字符串
      body: JSON.stringify({
        username: username, // 目标用户名
        available_runs: newRuns, // 新的可用次数
      }),
    });

    // 步骤4：解析响应的JSON数据
    const result = await response.json();

    // 步骤5：根据响应结果显示相应的提示消息
    if (result.success) {
      // 成功情况：显示成功消息
      Swal.fire({
        icon: "success", // 成功图标
        title: "更新成功", // 标题
        text: result.message || "可用次数已更新", // 显示后端返回的消息
        confirmButtonText: "确定", // 确认按钮文本
      });

      // 步骤6：刷新用户列表，更新界面显示
      // 这会重新加载所有用户数据，确保显示的次数是最新的
      loadAdminUsers();
    } else {
      // 失败情况：显示错误消息
      Swal.fire({
        icon: "error", // 错误图标
        title: "更新失败", // 标题
        text: result.message || "操作失败，请重试", // 显示错误原因
        confirmButtonText: "确定", // 确认按钮文本
      });
    }
  } catch (error) {
    // 步骤7：捕获网络错误或其他异常
    console.error("更新可用次数失败:", error); // 在控制台记录错误详情

    // 显示友好的错误提示给用户
    Swal.fire({
      icon: "error", // 错误图标
      title: "网络错误", // 标题
      text: "网络请求失败，请检查网络连接后重试", // 错误说明
      confirmButtonText: "确定", // 确认按钮文本
    });
  }
}

/**
 * 显示指定用户的学校账户列表（PC端管理界面）
 *
 * 功能说明：
 * - 从服务器获取指定认证用户（auth user）的所有学校账号（school accounts）
 * - 在模态框中显示账号列表，包含用户名、密码、User-Agent等信息
 * - 提供编辑、删除、查看详情等操作按钮
 *
 * 安全特性：
 * - 输入验证：验证username参数的合法性
 * - XSS防护：使用escapeHtml()转义所有用户输入
 * - 超时控制：设置10秒请求超时，防止无限等待
 * - 错误处理：完整的try-catch处理网络和解析错误
 *
 * @param {string} username - 目标认证用户名（auth username）
 * @returns {Promise<void>}
 *
 * 调用场景：
 * - 管理员点击"管理学校账户"按钮
 * - 需要查看或管理某个用户的学校账号信息
 *
 * 权限要求：
 * - 需要manage_users权限（后端验证）
 * - 会话必须有效（sessionUUID存在且有效）
 */
async function showUserSchoolAccounts(username) {
  // ========== 步骤1：输入验证（前端防护第一层）==========
  // 验证username参数是否合法，防止无效输入和潜在的安全问题
  try {
    // 检查1：确保username不为空
    if (!username) {
      console.error("[学校账户管理] 参数错误：username为空");
      // showModalAlert("用户名不能为空", "参数错误");
      Swal.fire({
        title: "参数错误",
        text: "用户名不能为空",
        icon: "error",
      });
      return;
    }

    // 检查2：确保username是字符串类型
    if (typeof username !== "string") {
      console.error(
        "[学校账户管理] 参数错误：username不是字符串类型",
        typeof username,
      );
      // showModalAlert("用户名格式错误", "参数错误");
      Swal.fire({
        title: "参数错误",
        text: "用户名格式错误",
        icon: "error",
      });
      return;
    }

    // 检查3：验证username长度（防止超长输入）
    // 与后端MAX_USERNAME_LENGTH保持一致（200字符）
    const MAX_USERNAME_LENGTH = 200;
    if (username.length > MAX_USERNAME_LENGTH) {
      console.error(
        `[学校账户管理] 参数错误：username过长 (${username.length} > ${MAX_USERNAME_LENGTH})`,
      );
      // showModalAlert(
      //   `用户名长度不能超过${MAX_USERNAME_LENGTH}个字符`,
      //   "参数错误"
      // );
      Swal.fire({
        title: "参数错误",
        text: `用户名长度不能超过${MAX_USERNAME_LENGTH}个字符`,
        icon: "error",
      });
      return;
    }

    // 检查4：验证username格式（只允许字母、数字、下划线、连字符、点和@）
    // 与后端USERNAME_PATTERN正则保持一致
    // 注意：连字符在字符类中需要转义或放在开头/结尾
    const USERNAME_PATTERN = /^[a-zA-Z0-9_\-.@]+$/;
    if (!USERNAME_PATTERN.test(username)) {
      console.error("[学校账户管理] 参数错误：username包含非法字符", username);
      // showModalAlert(
      //   "用户名包含非法字符，只允许字母、数字、下划线、连字符、点和@符号",
      //   "参数错误"
      // );
      Swal.fire({
        title: "参数错误",
        text: "用户名包含非法字符，只允许字母、数字、下划线、连字符、点和@符号",
        icon: "error",
      });
      return;
    }

    // 检查5：验证会话ID是否存在
    if (!sessionUUID) {
      console.error("[学校账户管理] 会话错误：sessionUUID不存在");
      // showModalAlert("会话已过期，请重新登录", "会话错误");
      Swal.fire({
        title: "会话错误",
        text: "会话已过期，请重新登录",
        icon: "error",
      });
      return;
    }

    // 输入验证通过，记录调试日志
    console.log(
      `[学校账户管理] 开始加载用户账户：${username}（长度：${username.length}）`,
    );
  } catch (validationError) {
    // 输入验证本身发生异常（理论上不应该发生，但做好防护）
    console.error("[学校账户管理] 输入验证异常：", validationError);
    // showModalAlert("输入验证失败，请稍后重试", "错误");
    Swal.fire({
      title: "错误",
      text: "输入验证失败，请稍后重试",
      icon: "error",
    });
    return;
  }

  // ========== 步骤2：发起API请求（添加超时控制）==========
  try {
    // 创建AbortController用于实现请求超时
    // 如果10秒内没有响应，自动取消请求
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
      console.warn("[学校账户管理] 请求超时，已自动取消");
    }, 10000); // 10秒超时

    // 发送GET请求到后端API
    // 使用encodeURIComponent编码username，防止特殊字符导致URL解析错误
    const response = await fetch(
      `/auth/get_user_school_accounts_only?username=${encodeURIComponent(
        username,
      )}`,
      {
        method: "GET", // 明确指定请求方法
        headers: {
          "X-Session-ID": sessionUUID, // 会话ID，用于后端身份验证
        },
        signal: controller.signal, // 绑定AbortController，支持超时取消
      },
    );

    // 请求成功，清除超时定时器
    clearTimeout(timeoutId);

    // 检查HTTP状态码
    // 注意：fetch只在网络错误时抛出异常，HTTP 4xx/5xx不会抛异常
    if (!response.ok) {
      // HTTP状态码不是2xx
      console.error(
        `[学校账户管理] HTTP请求失败：状态码 ${response.status}`,
        response.statusText,
      );

      // 根据状态码给出更友好的错误提示
      let errorMessage = "加载失败";
      if (response.status === 401) {
        errorMessage = "会话已过期，请重新登录";
      } else if (response.status === 403) {
        errorMessage = "权限不足，需要管理员权限";
      } else if (response.status === 404) {
        errorMessage = "用户不存在";
      } else if (response.status >= 500) {
        errorMessage = "服务器错误，请稍后重试";
      }

      // showModalAlert(errorMessage, "错误");
      Swal.fire({
        title: "错误",
        text: errorMessage,
        icon: "error",
      });
      return;
    }

    // ========== 步骤3：解析JSON响应 ==========
    // 使用try-catch捕获JSON解析错误
    let result;
    try {
      result = await response.json();
    } catch (jsonError) {
      // JSON解析失败，说明响应内容不是有效的JSON
      console.error(
        "[学校账户管理] JSON解析失败，HTTP状态码:",
        response.status,
      );
      // showModalAlert("服务器返回了无效的数据格式", "解析错误");
      Swal.fire({
        title: "解析错误",
        text: "服务器返回了无效的数据格式",
        icon: "error",
      });
      return;
    }

    // ========== 步骤4：验证响应数据格式 ==========
    // 检查响应是否包含success字段
    if (typeof result.success === "undefined") {
      console.error(
        "[学校账户管理] 响应数据格式错误：缺少success字段",
        createSafeClientLogValue(result),
      );
      // showModalAlert("服务器返回了格式错误的数据", "数据错误");
      Swal.fire({
        title: "数据错误",
        text: "服务器返回了格式错误的数据",
        icon: "error",
      });
      return;
    }

    // 检查操作是否成功
    if (!result.success) {
      // 服务器返回失败状态
      const errorMessage = result.message || "加载失败";
      console.warn(`[学校账户管理] 操作失败：${errorMessage}`);
      // showModalAlert(errorMessage, "错误");
      Swal.fire({
        title: "错误",
        text: errorMessage,
        icon: "error",
      });
      return;
    }

    // ========== 步骤5：提取账户数据并验证 ==========
    // 从响应中获取accounts字段，如果不存在则使用空对象
    const accounts = result.accounts || {};

    // 验证accounts是否为对象类型
    if (typeof accounts !== "object" || Array.isArray(accounts)) {
      console.error(
        "[学校账户管理] 数据格式错误：accounts不是对象",
        typeof accounts,
      );
      // showModalAlert("账户数据格式错误", "数据错误");
      Swal.fire({
        title: "数据错误",
        text: "账户数据格式错误",
        icon: "error",
      });
      return;
    }

    // 计算账户数量
    const accountCount = Object.keys(accounts).length;

    // 记录成功日志
    console.log(
      `[学校账户管理] 成功加载 ${accountCount} 个学校账户（用户：${username}）`,
    );

    // ========== 步骤6：更新UI显示用户名和统计信息 ==========
    // 使用textContent而不是innerHTML，防止XSS攻击
    // textContent会自动转义HTML标签，安全性更高
    const usernameElement = $("school-accounts-username");
    const countElement = $("school-accounts-count");

    // 验证DOM元素是否存在
    if (!usernameElement || !countElement) {
      console.error("[学校账户管理] DOM元素不存在");
      // showModalAlert("界面加载失败，请刷新页面重试", "界面错误");
      Swal.fire({
        title: "界面错误",
        text: "界面加载失败，请刷新页面重试",
        icon: "error",
      });
      return;
    }

    // 安全地设置用户名和账户数量
    usernameElement.textContent = username;
    countElement.textContent = accountCount;

    // ========== 步骤7：渲染账户列表 ==========
    const listContainer = $("school-accounts-list");

    // 验证列表容器是否存在
    if (!listContainer) {
      console.error("[学校账户管理] 列表容器元素不存在");
      // showModalAlert("界面加载失败，请刷新页面重试", "界面错误");
      Swal.fire({
        title: "界面错误",
        text: "界面加载失败，请刷新页面重试",
        icon: "error",
      });
      return;
    }

    // 情况1：没有账户，显示空状态提示
    if (accountCount === 0) {
      // 使用innerHTML是安全的，因为这是静态HTML，不包含用户输入
      listContainer.innerHTML =
        '<p class="text-slate-400 text-center py-10">该用户暂无学校账户</p>';
      console.log("[学校账户管理] 该用户暂无学校账户");
      showModal("manage-school-accounts-modal");
      return; // 提前返回，不需要后续渲染
    }

    // 情况2：有账户，逐个渲染账户卡片
    let html = ""; // 累积HTML字符串

    // 遍历所有账户，生成HTML
    for (const [schoolUsername, accountData] of Object.entries(accounts)) {
      // [安全检查] 验证schoolUsername和accountData的有效性
      // 防止服务器返回了异常数据导致前端崩溃
      if (!schoolUsername || typeof schoolUsername !== "string") {
        console.warn("[学校账户管理] 跳过无效的学校账户名：", schoolUsername);
        continue; // 跳过这个无效账户
      }

      // ========== 提取账户信息（兼容新旧格式）==========
      let password = "";
      let ua = "";

      // 旧格式：accountData是字符串（仅包含密码）
      if (typeof accountData === "string") {
        password = accountData;
        console.log(
          `[学校账户管理] 账户 ${schoolUsername} 使用旧格式（仅密码）`,
        );
      }
      // 新格式：accountData是对象（包含password和ua字段）
      else if (typeof accountData === "object" && accountData !== null) {
        password = accountData.password || "";
        ua = accountData.ua || "";
        console.log(
          `[学校账户管理] 账户 ${schoolUsername} 使用新格式（password + ua）`,
        );
      }
      // 未知格式：记录警告并跳过
      else {
        console.warn(
          `[学校账户管理] 账户 ${schoolUsername} 数据格式未知：`,
          typeof accountData,
        );
        continue;
      }

      // ========== 准备安全的数据传递（防止XSS和JSON注入）==========
      // 将账户数据打包成JSON字符串，用于存储在HTML的data属性中
      // 后续按钮点击时会解析这个JSON并传递给处理函数
      const accountDataJson = JSON.stringify({
        authUsername: username, // 认证用户名
        schoolUsername: schoolUsername, // 学校账号用户名
        password: password, // 密码
        ua: ua, // User-Agent
      });

      // ========== 生成账户卡片HTML（使用模板字符串）==========
      // 注意：所有用户输入都必须通过escapeHtml()转义，防止XSS攻击
      html += `
            <div class="bg-slate-50 p-4 rounded-lg border border-slate-200 space-y-3">
              <!-- 学校账户用户名 -->
              <div class="flex items-center justify-between">
                <!-- 用户名显示：使用escapeHtml()转义，防止XSS -->
                <div class="font-semibold text-slate-800 text-lg">${escapeHtml(
                  schoolUsername,
                )}</div>
                
                <!-- 操作按钮组：包含编辑、删除、查看详情三个按钮 -->
                <div class="flex gap-2">
                  <!-- 
                    ========== 编辑按钮 ==========
                    功能：打开编辑模态框，允许修改密码和UA
                    
                    【关键修复点】data-account属性的处理（PC版）：
                    - accountDataJson 已通过 JSON.stringify() 生成，格式正确
                    - 不能使用 escapeHtml()，因为它会将双引号转义为 &quot;，破坏JSON格式
                    - 只需转义单引号为 &apos;，因为HTML属性值使用单引号包裹
                    - 这样 JSON.parse() 可以正确解析数据，按钮才能正常工作
                    
                    安全性说明：
                    - JSON.stringify() 已经对特殊字符进行了转义（包括<>等）
                    - replace(/'/g, "&apos;") 只转义单引号，避免破坏HTML属性
                    - JSON.parse() 在onclick中安全解析数据
                    - 这种方法比escapeHtml()更适合JSON数据，因为它保持了JSON的可解析性
                    - 如果使用escapeHtml()，会将"转义为&quot;，导致JSON.parse()失败
                  -->
                  <button 
                    class="btn btn-sm btn-primary !py-1 !px-3 !text-xs" 
                    data-account='${accountDataJson.replace(/'/g, "&apos;")}'
                    onclick="(function(btn) { 
                      try {
                        const data = JSON.parse(btn.getAttribute('data-account')); 
                        editSchoolAccount(data.authUsername, data.schoolUsername, data.password, data.ua); 
                      } catch(e) {
                        console.error('[编辑按钮] JSON解析失败:', e);
                        showModalAlert('数据解析失败', '错误');
                      }
                    })(this)"
                    title="编辑此账户">
                    编辑
                  </button>
                  
                  <!-- 
                    ========== 删除按钮 ==========
                    功能：删除学校账号（需要确认）
                    
                    数据传递方式：
                    - 使用两个独立的data属性存储authUsername和schoolUsername
                    - 每个值都经过escapeHtml()转义，确保安全
                    - 点击时从data属性读取并调用deleteSchoolAccount函数
                  -->
                  <button 
                    class="btn btn-sm btn-danger !py-1 !px-3 !text-xs" 
                    data-auth-username='${escapeHtml(username)}'
                    data-school-username='${escapeHtml(schoolUsername)}'
                    onclick="(function(btn) { 
                      deleteSchoolAccount(
                        btn.getAttribute('data-auth-username'), 
                        btn.getAttribute('data-school-username')
                      ); 
                    })(this)"
                    title="删除此账户">
                    删除
                  </button>
                  
                  <!-- 
                    ========== 查看详情按钮 ==========
                    功能：显示该学校账号的备份详情和欠费信息
                    
                    调用函数：View_details_of_users_with_outstanding_payments
                    - 该函数会显示一个包含详细信息的弹窗
                    - 包括：学号、姓名、欠费次数等
                    - schoolUsername经过escapeHtml()转义后安全嵌入
                  -->
                  <button 
                    class="btn btn-sm !py-1 !px-3 !text-xs bg-sky-500 text-white hover:bg-sky-600 border-sky-500" 
                    onclick="View_details_of_users_with_outstanding_payments(${escapeInlineJsArg(
                      schoolUsername,
                    )})"
                    title="查看此账户的详细信息">
                    查看详情
                  </button>
                </div>
              </div>
              
              <!-- 
                ========== 密码显示区域 ==========
                - 使用font-mono（等宽字体）便于复制
                - 使用select-all类支持双击全选
                - password经过escapeHtml()转义，防止XSS
              -->
              <div class="text-sm">
                <span class="text-slate-500">密码:</span>
                <span class="font-mono text-slate-700 ml-2 select-all">${escapeHtml(
                  password,
                )}</span>
              </div>
              
              <!-- 
                ========== User-Agent显示区域（条件渲染）==========
                - 只在UA存在时显示
                - UA可能很长，使用break-all自动换行
                - 使用小号字体（text-xs）节省空间
                - ua经过escapeHtml()转义，防止XSS
              -->
              ${
                ua
                  ? `
              <div class="text-sm">
                <span class="text-slate-500">User-Agent:</span>
                <div class="font-mono text-xs text-slate-600 mt-1 p-2 bg-white rounded break-all select-all">${escapeHtml(
                  ua,
                )}</div>
              </div>
              `
                  : ""
              }
            </div>
          `;
    } // end for loop

    // ========== 步骤8：将生成的HTML插入DOM ==========
    // 使用innerHTML是必要的，因为需要插入HTML结构
    // 安全性已经通过escapeHtml()确保
    listContainer.innerHTML = html;

    // 记录渲染成功日志
    console.log(`[学校账户管理] 成功渲染 ${accountCount} 个账户卡片`);
  } catch (error) {
    // ========== 异常处理（捕获所有未预期的错误）==========
    // 区分不同类型的错误并给出友好提示
    console.error("[学校账户管理] 发生异常：", error);

    let errorMessage = "加载失败，请稍后重试";

    // 网络错误（无法连接到服务器）
    if (
      error.name === "NetworkError" ||
      error.message.includes("Failed to fetch")
    ) {
      errorMessage = "网络连接失败，请检查网络后重试";
    }
    // 请求超时（AbortController触发）
    else if (error.name === "AbortError") {
      errorMessage = "请求超时，请稍后重试";
    }
    // JSON解析错误（已在前面处理，这里是兜底）
    else if (error.name === "SyntaxError") {
      errorMessage = "服务器返回了无效的数据格式";
    }

    // showModalAlert(errorMessage, "错误");
    Swal.fire({
      title: "错误",
      text: errorMessage,
      icon: "error",
    });
  }
  // ========== 最后：显示模态框 ==========
  // 在所有数据加载和渲染完成后，显示包含账户列表的模态框
  // 这样用户看到的是完整渲染好的内容，不会看到加载过程
  showModal("manage-school-accounts-modal");
}

function closeManageSchoolAccountsModal() {
  hideModal("manage-school-accounts-modal");
}
function editSchoolAccount(authUsername, schoolUsername, password, ua) {
  const authUsernameField = $("edit-school-account-auth-username");
  const schoolUsernameField = $("edit-school-account-school-username");

  if (authUsernameField) {
    authUsernameField.value = authUsername;
  }

  if (schoolUsernameField) {
    schoolUsernameField.value = schoolUsername;
  }

  const passwordField = $("edit-school-account-password");
  const uaField = $("edit-school-account-ua");

  if (passwordField) {
    passwordField.value = password;
  }

  if (uaField) {
    uaField.value = ua || "";
  }

  const authUsernameSpan = $("edit-auth-username");
  const schoolUsernameSpan = $("edit-school-username");
  const passwordInput = $("edit-school-password");
  const uaTextarea = $("edit-school-ua");

  if (authUsernameSpan) {
    authUsernameSpan.textContent = authUsername;
  }

  if (schoolUsernameSpan) {
    schoolUsernameSpan.textContent = schoolUsername;
  }

  if (passwordInput) {
    passwordInput.value = password;
  }

  if (uaTextarea) {
    uaTextarea.value = ua || "";
  }

  showModal("edit-school-account-modal");
}

function addNewSchoolAccount() {
  const currentAuthUsername = $("school-accounts-username")?.textContent || "";

  const authUsernameField = $("edit-school-account-auth-username");
  const schoolUsernameField = $("edit-school-account-school-username");
  const passwordField = $("edit-school-account-password");
  const uaField = $("edit-school-account-ua");

  if (authUsernameField) {
    authUsernameField.value = currentAuthUsername;
  }

  if (schoolUsernameField) {
    schoolUsernameField.value = "";
    schoolUsernameField.readOnly = false;
  }

  if (passwordField) {
    passwordField.value = "";
  }

  if (uaField) {
    uaField.value = "";
  }
  const authUsernameSpan = $("edit-auth-username");
  const schoolUsernameSpan = $("edit-school-username");
  const passwordInput = $("edit-school-password");
  const uaTextarea = $("edit-school-ua");

  if (authUsernameSpan) {
    authUsernameSpan.textContent = currentAuthUsername;
  }

  if (schoolUsernameSpan) {
    schoolUsernameSpan.textContent = "";
  }

  if (passwordInput) {
    passwordInput.value = "";
  }

  if (uaTextarea) {
    uaTextarea.value = "";
  }
  const modalTitle = $("edit-school-account-modal-title");
  if (modalTitle) {
    modalTitle.textContent = "新增学校账户";
  }
  showModal("edit-school-account-modal");

  console.log("[学校账户管理] 已打开新增学校账户模态框");
}
async function generateRandomUAForSchoolAccount() {
  try {
    console.log("[学校账户管理] 开始生成随机User-Agent...");
    const result = await callPythonAPI("generate_new_ua");
    if (!result) {
      console.error("[学校账户管理] 生成UA失败：API返回空结果");
      // showModalAlert("生成失败：无法连接到服务器", "错误");
      Swal.fire({
        title: "错误",
        text: "生成失败：无法连接到服务器",
        icon: "error",
      });
      return;
    }
    const newUA = typeof result === "string" ? result : result.ua;

    if (!newUA) {
      console.error("[学校账户管理] 生成UA失败：返回的UA为空");
      // showModalAlert("生成失败：返回的User-Agent为空", "错误");
      Swal.fire({
        title: "错误",
        text: "生成失败：返回的User-Agent为空",
        icon: "error",
      });
      return;
    }
    const uaField = $("edit-school-account-ua");
    if (uaField) {
      uaField.value = newUA;
      console.log(
        "[学校账户管理] 已生成并填充随机UA:",
        newUA.substring(0, 50) + "...",
      );
    }
    const uaTextarea = $("edit-school-ua");
    if (uaTextarea) {
      uaTextarea.value = newUA;
    }
    // showModalAlert("已生成随机User-Agent", "成功");
    Swal.fire({
      title: "成功",
      text: "已生成随机User-Agent",
      icon: "success",
    });
  } catch (error) {
    console.error("[学校账户管理] 生成UA时发生错误:", error);
    // showModalAlert("生成失败: " + error.message, "错误");
    Swal.fire({
      title: "错误",
      text: "生成失败: " + error.message,
      icon: "error",
    });
  }
}
function closeEditSchoolAccountModal() {
  // 关闭现代化样式的模态框（主要使用的版本）
  hideModal("edit-school-account-modal");

  // 同时关闭简洁样式的模态框（备用版本），以防它被打开
  // 修复ID冲突后的ID引用更新
  const simpleModal = $("edit-school-account-modal-simple");
  if (simpleModal) {
    simpleModal.classList.add("hidden");
    simpleModal.classList.remove("flex");
  }
}
async function submitEditSchoolAccount() {
  // 获取表单中的数据
  // 注意：auth_username和school_username存储在span元素的textContent中
  // password和ua存储在input/textarea元素的value中
  const authUsername = $("edit-auth-username").textContent;
  const schoolUsername = $("edit-school-username").textContent;
  const password = $("edit-school-password").value.trim();
  const ua = $("edit-school-ua").value.trim();

  // 验证密码不能为空
  if (!password) {
    // showModalAlert("密码不能为空", "错误");
    Swal.fire({
      title: "错误",
      text: "密码不能为空",
      icon: "error",
    });
    return;
  }

  try {
    // 向服务器发送更新请求
    const response = await fetch("/api/admin/school_account/update", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        auth_username: authUsername,
        school_username: schoolUsername,
        password: password,
        ua: ua,
      }),
    });

    // 解析服务器响应
    const result = await response.json();

    if (result.success) {
      // 更新成功，显示成功提示
      // showModalAlert(result.message || "更新成功", "成功");
      Swal.fire({
        title: "成功",
        text: result.message || "更新成功",
        icon: "success",
      });

      // 关闭编辑模态框
      closeEditSchoolAccountModal();

      // 判断当前是在PC端还是移动端模态框中
      // 通过检查移动端模态框是否显示来判断
      const mobileModal = $("mobile-user-school-accounts-modal");
      const isMobileModalVisible =
        mobileModal && !mobileModal.classList.contains("hidden");

      if (isMobileModalVisible) {
        // 如果是在移动端模态框中，刷新移动端列表
        await showMobileUserSchoolAccounts(authUsername);
      } else {
        // 如果是在PC端模态框中，刷新PC端列表
        await showUserSchoolAccounts(authUsername);
      }
    } else {
      // 更新失败，显示错误提示
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("submitEditSchoolAccount error:", error);
    // showModalAlert("更新失败: " + error.message, "错误");
    Swal.fire({
      title: "错误",
      text: "更新失败: " + error.message,
      icon: "error",
    });
  }
}

async function deleteSchoolAccount(authUsername, schoolUsername) {
  // 显示确认对话框，防止误删除操作
  // jsShowConfirm是异步函数，返回Promise<boolean>
  const confirmed = await jsShowConfirm(
    "确认删除",
    `确定要删除学校账户 <strong>${escapeHtml(
      schoolUsername,
    )}</strong> 吗？此操作不可恢复。`,
  );

  // 如果用户点击取消，则提前返回，不执行删除操作
  if (!confirmed) return;

  try {
    // 向服务器发送DELETE请求
    const response = await fetch("/api/admin/school_account/delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        auth_username: authUsername,
        school_username: schoolUsername,
      }),
    });

    // 解析服务器响应
    const result = await response.json();

    if (result.success) {
      // 删除成功，显示成功提示
      // showModalAlert(result.message || "删除成功", "成功");
      Swal.fire({
        title: "成功",
        text: result.message || "删除成功",
        icon: "success",
      });

      // 判断当前是在PC端还是移动端模态框中
      // 通过检查移动端模态框是否显示来判断
      const mobileModal = $("mobile-user-school-accounts-modal");
      const isMobileModalVisible =
        mobileModal && !mobileModal.classList.contains("hidden");

      if (isMobileModalVisible) {
        // 如果是在移动端模态框中，刷新移动端列表
        await showMobileUserSchoolAccounts(authUsername);
      } else {
        // 如果是在PC端模态框中，刷新PC端列表
        await showUserSchoolAccounts(authUsername);
      }
    } else {
      // 删除失败，显示错误提示
      // showModalAlert(result.message || "删除失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "删除失败",
        icon: "error",
      });
    }
  } catch (error) {
    // 捕获网络错误或其他异常
    console.error("deleteSchoolAccount error:", error);
    // showModalAlert("删除失败: " + error.message, "错误");
    Swal.fire({
      title: "错误",
      text: "删除失败: " + error.message,
      icon: "error",
    });
  }
}

// ==================== 移动端学校账户管理功能 ====================
// 以下函数专门用于移动端的学校账户管理模态框
// 功能与PC端保持一致，但适配了移动端的UI和交互方式
// ================================================================

/**
 * 关闭移动端学校账户管理模态框
 *
 * 功能说明：
 * - 隐藏移动端的学校账户管理模态框（mobile-user-school-accounts-modal）
 * - 使用CSS过渡动画实现平滑的关闭效果
 *
 * 调用时机：
 * - 用户点击模态框外的背景遮罩层
 * - 用户点击模态框底部的"关闭"按钮
 *
 * 注意事项：
 * - 该函数不会关闭二级模态框（如edit-school-account-modal）
 * - 如果二级模态框已打开，需要先关闭二级模态框
 *
 * 修复说明（2024）：
 * - 问题原因：由于showMobileUserSchoolAccounts()函数存在两个定义，第二个定义（动态创建模态框）
 *   会覆盖第一个定义。第二个定义使用的是"show"类来控制显示，而不是"flex"类。
 * - 原实现使用hideModal()函数，该函数移除"flex"类并添加"hidden"类，但实际模态框使用的是"show"类，
 *   导致hideModal()无法正确隐藏模态框。
 * - 修复方法：改为直接操作DOM，移除"show"类并添加"hidden"类，与实际使用的类名模式保持一致。
 * - 参考了closeMobileUserSchoolAccounts()函数的实现（line 42556），该函数正确处理了"show"类。
 */
function closeMobileUserSchoolAccountsModal() {
  // 步骤1：通过DOM API获取模态框元素
  // 使用document.getElementById而不是$()工具函数，确保在任何情况下都能获取到元素
  const modal = document.getElementById("mobile-user-school-accounts-modal");

  // 步骤2：检查模态框元素是否存在
  // 如果元素不存在（例如尚未创建或已被删除），直接返回，避免后续操作出错
  if (!modal) {
    console.warn("[移动端学校账户管理] 模态框元素未找到，无法关闭");
    return;
  }

  // 步骤3：移除"show"类，触发CSS过渡动画
  // "show"类用于控制模态框的显示状态（通过CSS的opacity和transform属性）
  // 移除该类会触发淡出和下滑动画，提供更好的用户体验
  modal.classList.remove("show");

  // 步骤4：延迟添加"hidden"类，等待CSS过渡动画完成
  // 延迟时间300ms与CSS transition的持续时间保持一致
  // 这样可以确保用户看到完整的关闭动画，然后才将模态框从文档流中移除
  // 使用setTimeout是一种常见的处理CSS动画的模式
  setTimeout(() => {
    // 添加"hidden"类，将模态框的display属性设置为none
    // 这会将模态框从文档流中完全移除，释放页面空间
    modal.classList.add("hidden");

    // 输出日志，便于调试和追踪模态框的关闭操作
    // 日志在动画完成后输出，表示模态框已完全关闭
    console.log("[移动端学校账户管理] 模态框已关闭（动画完成）");
  }, 300); // 300ms延迟，与CSS过渡动画时长匹配

  // 立即输出日志，表示关闭操作已开始
  console.log("[移动端学校账户管理] 开始关闭模态框（触发动画）");
}

/**
 * 刷新移动端学校账户列表
 *
 * 功能说明：
 * - 重新从服务器加载当前用户的学校账户数据
 * - 更新移动端模态框中的账户列表显示
 *
 * 实现逻辑：
 * - 获取当前正在查看的用户名（从mobile-school-accounts-username元素）
 * - 调用showMobileUserSchoolAccounts函数重新加载数据
 *
 * 用户体验：
 * - 用户点击"刷新"按钮后，可以看到最新的账户数据
 * - 如果在其他地方修改了账户信息，可以通过刷新来同步显示
 *
 * 错误处理：
 * - 如果无法获取用户名，会在控制台输出错误信息并提示用户
 */
async function mobileRefreshSchoolAccounts() {
  // 输出日志，标记刷新操作的开始
  console.log("[移动端学校账户管理] 开始刷新账户列表...");

  // 尝试获取当前显示的用户名
  // $("mobile-school-accounts-username")获取DOM元素
  // ?.textContent 使用可选链操作符，如果元素不存在则返回undefined
  // || "" 如果textContent为空或undefined，则使用空字符串作为默认值
  const currentUsername =
    $("mobile-school-accounts-username")?.textContent || "";

  // 验证用户名是否有效
  if (!currentUsername) {
    // 如果用户名为空，输出错误日志
    console.error("[移动端学校账户管理] 刷新失败：无法获取当前用户名");

    // 使用showModalAlert显示友好的错误提示
    // showModalAlert("刷新失败：无法确定当前用户", "错误");
    Swal.fire({
      title: "错误",
      text: "刷新失败：无法确定当前用户",
      icon: "error",
    });

    // 提前返回，不执行后续的刷新操作
    return;
  }

  // 调用showMobileUserSchoolAccounts函数重新加载账户数据
  // 该函数会自动：
  // 1. 从服务器获取最新数据
  // 2. 更新账户列表的HTML
  // 3. 更新账户统计信息
  await showMobileUserSchoolAccounts(currentUsername);

  // 输出成功日志
  console.log("[移动端学校账户管理] 账户列表刷新完成");
}

/**
 * 移动端：打开新增学校账户表单
 *
 * 功能说明：
 * - 打开新增学校账户的表单模态框（edit-school-account-modal）
 * - 复用PC端的编辑模态框，但将其用于新增账户
 * - 预填充当前用户名，清空其他字段
 *
 * 设计思路：
 * - 移动端和PC端共用同一个编辑表单模态框（edit-school-account-modal）
 * - 通过修改表单标题和字段内容，区分"新增"和"编辑"两种场景
 * - 这样可以减少代码重复，保持UI一致性
 *
 * 表单字段处理：
 * - auth_username（认证用户名）：自动填充当前用户名，设为只读
 * - school_username（学校账号用户名）：清空，允许用户输入
 * - password（密码）：清空，允许用户输入
 * - ua（User-Agent）：清空，允许用户输入或使用生成功能
 *
 * 注意事项：
 * - 新增操作不会关闭移动端的主模态框（mobile-user-school-accounts-modal）
 * - 两个模态框会叠加显示（二级模态框在上层）
 * - 提交或关闭二级模态框后，会自动刷新主模态框的数据
 */
function mobileAddNewSchoolAccount() {
  // 输出日志，标记新增账户操作的开始
  console.log("[移动端学校账户管理] 打开新增账户表单...");

  // 获取当前正在管理的用户名
  // 从移动端模态框的标题中提取用户名
  // ?.textContent 使用可选链操作符避免null引用错误
  // || "" 如果获取失败，使用空字符串作为后备值
  const currentAuthUsername =
    $("mobile-school-accounts-username")?.textContent || "";

  // 验证用户名是否有效
  if (!currentAuthUsername) {
    // 如果无法获取用户名，输出错误日志
    console.error("[移动端学校账户管理] 打开新增表单失败：无法获取当前用户名");

    // 显示友好的错误提示
    // showModalAlert("无法打开新增表单：用户名无效", "错误");
    Swal.fire({
      title: "错误",
      text: "无法打开新增表单：用户名无效",
      icon: "error",
    });

    // 提前返回，不执行后续操作
    return;
  }

  // ========== 填充表单字段 ==========
  // 获取表单中的各个输入字段的DOM元素
  const authUsernameField = $("edit-school-account-auth-username");
  const schoolUsernameField = $("edit-school-account-school-username");
  const passwordField = $("edit-school-account-password");
  const uaField = $("edit-school-account-ua");

  // 填充"认证用户名"字段
  if (authUsernameField) {
    // 设置字段值为当前用户名
    authUsernameField.value = currentAuthUsername;

    // 设置为只读，防止用户修改（新增账户不应该改变所属用户）
    authUsernameField.readOnly = true;
  }

  // 清空"学校账号用户名"字段
  if (schoolUsernameField) {
    // 清空字段内容，等待用户输入新的学校账号
    schoolUsernameField.value = "";

    // 设置为可编辑状态（新增时必须输入学校账号）
    schoolUsernameField.readOnly = false;
  }

  // 清空"密码"字段
  if (passwordField) {
    // 清空密码，等待用户输入新密码
    passwordField.value = "";
  }

  // 清空"User-Agent"字段
  if (uaField) {
    // 清空UA字段，用户可以手动输入或使用"生成随机UA"按钮
    uaField.value = "";
  }

  // ========== 更新模态框标题 ==========
  // 获取模态框标题元素
  const modalTitle = $("edit-school-account-modal-title");
  if (modalTitle) {
    // 修改标题文字为"新增学校账户"，区别于"编辑学校账户"
    modalTitle.textContent = "新增学校账户";
  }

  // ========== 显示编辑表单模态框 ==========
  // 调用showModal工具函数显示二级模态框
  // 该模态框会叠加在移动端主模态框之上
  showModal("edit-school-account-modal");

  // 输出成功日志
  console.log("[移动端学校账户管理] 已打开新增学校账户表单");
}

/**
 * 移动端：编辑学校账户
 *
 * 功能说明：
 * - 打开编辑学校账户的表单模态框（edit-school-account-modal）
 * - 预填充现有账户的所有信息
 * - 允许用户修改密码和User-Agent，但不允许修改学校账号用户名
 *
 * 参数说明：
 * @param {string} authUsername - 认证用户名（账户所属用户）
 * @param {string} schoolUsername - 学校账号用户名（要编辑的账户标识）
 * @param {string} password - 当前密码（预填充到表单中）
 * @param {string} ua - 当前User-Agent（预填充到表单中，可能为空）
 *
 * 设计思路：
 * - 与mobileAddNewSchoolAccount复用同一个模态框
 * - 通过预填充数据和设置只读属性来区分"编辑"场景
 * - 学校账号用户名不可修改（因为它是账户的唯一标识）
 *
 * 表单字段处理：
 * - auth_username：预填充并设为只读
 * - school_username：预填充并设为只读（编辑时不允许修改账号标识）
 * - password：预填充现有密码，允许修改
 * - ua：预填充现有UA（如果有），允许修改
 *
 * 用户体验：
 * - 用户可以直接看到当前账户的所有信息
 * - 可以修改密码和UA，提交后更新到服务器
 * - 编辑完成后自动刷新账户列表
 */
function mobileEditSchoolAccount(authUsername, schoolUsername, password, ua) {
  // 输出日志，标记编辑操作的开始，包含账户标识信息
  console.log(
    `[移动端学校账户管理] 打开编辑表单：${authUsername} - ${schoolUsername}`,
  );

  // ========== 填充表单字段 ==========
  // 获取表单中的各个输入字段的DOM元素
  const authUsernameField = $("edit-school-account-auth-username");
  const schoolUsernameField = $("edit-school-account-school-username");
  const passwordField = $("edit-school-account-password");
  const uaField = $("edit-school-account-ua");

  // 填充"认证用户名"字段
  if (authUsernameField) {
    // 设置字段值为传入的认证用户名
    authUsernameField.value = authUsername;

    // 设置为只读，防止用户修改所属用户
    authUsernameField.readOnly = true;
  }

  // 填充"学校账号用户名"字段
  if (schoolUsernameField) {
    // 设置字段值为传入的学校账号用户名
    schoolUsernameField.value = schoolUsername;

    // 设置为只读，因为学校账号用户名是账户的唯一标识，不允许修改
    // 如果需要修改学校账号用户名，应该删除旧账户并新增一个账户
    schoolUsernameField.readOnly = true;
  }

  // 填充"密码"字段
  if (passwordField) {
    // 设置字段值为传入的密码
    // 用户可以看到当前密码，并根据需要进行修改
    passwordField.value = password;
  }

  // 填充"User-Agent"字段
  if (uaField) {
    // 设置字段值为传入的User-Agent
    // 使用 || "" 确保即使ua为null或undefined，也设置为空字符串
    // 这样可以避免在输入框中显示"undefined"或"null"文本
    uaField.value = ua || "";
  }

  // ========== 更新模态框标题 ==========
  // 获取模态框标题元素
  const modalTitle = $("edit-school-account-modal-title");
  if (modalTitle) {
    // 修改标题文字为"编辑学校账户"，区别于"新增学校账户"
    modalTitle.textContent = "编辑学校账户";
  }

  // ========== 显示编辑表单模态框 ==========
  // 调用showModal工具函数显示二级模态框
  // 该模态框会叠加在移动端主模态框之上
  showModal("edit-school-account-modal");

  // 输出成功日志
  console.log("[移动端学校账户管理] 已打开编辑学校账户表单");
}

/**
 * 显示移动端学校账户管理模态框
 *
 * 功能说明：
 * - 从服务器加载指定用户的所有学校账户数据
 * - 在移动端模态框中显示账户列表
 * - 渲染每个账户的详细信息和操作按钮（编辑、删除、查看详情）
 *
 * 参数说明：
 * @param {string} username - 要查询学校账户的用户名
 *
 * 功能流程：
 * 1. 向服务器发送GET请求，获取用户的学校账户数据
 * 2. 解析返回的JSON数据，验证是否成功
 * 3. 更新模态框标题，显示用户名和账户总数
 * 4. 遍历账户数据，为每个账户生成HTML卡片
 * 5. 将生成的HTML插入到账户列表容器中
 * 6. 显示移动端模态框
 *
 * 账户卡片包含内容：
 * - 学校账号用户名（醒目显示）
 * - 密码（等宽字体，可选中复制）
 * - User-Agent（如果存在，显示在可滚动的代码块中）
 * - 操作按钮：编辑、删除、查看详情
 *
 * 错误处理：
 * - 网络请求失败：捕获异常并显示错误提示
 * - 服务器返回错误：解析error message并显示
 * - 没有账户数据：显示友好的空状态提示
 *
 * 安全措施：
 * - 使用escapeHtml函数转义所有用户输入，防止XSS攻击
 * - 使用JSON.stringify和data属性安全传递复杂数据
 * - 使用encodeURIComponent编码URL参数
 */
async function showMobileUserSchoolAccounts(username) {
  // 输出日志，标记数据加载的开始
  console.log(`[移动端学校账户管理] 开始加载用户账户：${username}`);

  try {
    // ========== 发送HTTP请求获取账户数据 ==========
    // 构建API端点URL，使用encodeURIComponent编码用户名，避免特殊字符导致的问题
    const apiUrl = `/auth/get_user_school_accounts_only?username=${encodeURIComponent(
      username,
    )}`;

    // 发送GET请求到服务器
    const response = await fetch(apiUrl, {
      headers: {
        // 添加会话ID到请求头，用于服务器端的身份验证
        // sessionUUID应该在用户登录时设置，存储在全局变量中
        "X-Session-ID": sessionUUID,
      },
    });

    // 解析响应体为JSON对象
    const result = await response.json();

    // ========== 验证API响应 ==========
    // 检查result.success标志，判断服务器端操作是否成功
    if (!result.success) {
      // 如果失败，显示服务器返回的错误消息
      // result.message包含服务器提供的错误描述
      // 如果message不存在，使用默认文本"加载失败"
      // showModalAlert(result.message || "加载失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "加载失败",
        icon: "error",
      });

      // 输出错误日志，便于调试
      console.error("[移动端学校账户管理] 加载失败：", result.message);

      // 提前返回，不执行后续的渲染操作
      return;
    }

    // ========== 解析账户数据 ==========
    // result.accounts是一个对象，键为学校账号用户名，值为账户详情
    // 使用 || {} 确保即使accounts不存在，也有一个空对象作为后备值
    const accounts = result.accounts || {};

    // 计算账户总数
    // Object.keys()返回对象的所有键组成的数组
    // .length获取数组长度，即账户数量
    const accountCount = Object.keys(accounts).length;

    // 输出日志，显示成功加载的账户数量
    console.log(`[移动端学校账户管理] 成功加载 ${accountCount} 个账户`);

    // ========== 更新模态框标题和统计信息 ==========
    // 更新标题中的用户名显示
    // $()函数是getElementById的简写
    const usernameEl = $("mobile-school-accounts-username");
    if (usernameEl) {
      // 使用textContent而非innerHTML，避免XSS攻击
      usernameEl.textContent = username;
    }

    // 更新账户总数显示
    const countEl = $("mobile-school-accounts-count");
    if (countEl) {
      // 将账户数量转换为字符串并显示
      countEl.textContent = accountCount.toString();
    }

    // ========== 渲染账户列表 ==========
    // 获取账户列表容器元素
    const listContainer = $("mobile-school-accounts-list");

    // 验证容器元素是否存在
    if (!listContainer) {
      console.error("[移动端学校账户管理] 错误：找不到账户列表容器元素");
      return;
    }

    // 判断是否有账户数据
    if (accountCount === 0) {
      // ========== 空状态处理 ==========
      // 如果没有账户，显示友好的空状态提示
      listContainer.innerHTML = `
              <p class="text-slate-400 text-center text-xs py-8">
                该用户暂无学校账户
              </p>
            `;
    } else {
      // ========== 生成账户卡片HTML ==========
      // 初始化HTML字符串
      let html = "";

      // 遍历accounts对象的所有条目
      // Object.entries()返回[key, value]对的数组
      for (const [schoolUsername, accountData] of Object.entries(accounts)) {
        // 解析账户数据
        // accountData可能是字符串（仅包含密码）或对象（包含password和ua）
        let password = "";
        let ua = "";

        if (typeof accountData === "string") {
          // 如果accountData是字符串，则它就是密码
          password = accountData;
        } else if (typeof accountData === "object" && accountData !== null) {
          // 如果accountData是对象，则提取password和ua字段
          password = accountData.password || "";
          ua = accountData.ua || "";
        }

        // 构建账户数据的JSON字符串，用于传递给onclick函数
        // 将所有需要的数据打包成一个对象
        const accountDataJson = JSON.stringify({
          authUsername: username,
          schoolUsername: schoolUsername,
          password: password,
          ua: ua,
        });

        // 生成账户卡片的HTML
        // 使用模板字符串拼接HTML，注意所有动态内容都要用escapeHtml转义
        html += `
                <!-- 账户卡片容器 -->
                <!-- bg-slate-50: 浅灰色背景，区分不同的账户卡片 -->
                <!-- p-3: 内边距0.75rem，移动端紧凑布局 -->
                <!-- rounded-lg: 中等圆角 -->
                <!-- border border-slate-200: 淡灰色边框 -->
                <!-- space-y-2: 子元素之间垂直间距0.5rem -->
                <div class="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-2">
                  
                  <!-- 学校账号用户名和操作按钮行 -->
                  <!-- flex items-center justify-between: 左右两端对齐布局 -->
                  <div class="flex items-center justify-between">
                    
                    <!-- 学校账号用户名 -->
                    <!-- font-semibold: 字体半粗 -->
                    <!-- text-slate-800: 深灰色文字 -->
                    <!-- text-base: 字体大小1rem（16px） -->
                    <div class="font-semibold text-slate-800 text-base">
                      ${escapeHtml(schoolUsername)}
                    </div>
                    
                    <!-- 操作按钮组 -->
                    <!-- flex gap-1.5: 水平排列，按钮之间间距6px -->
                    <div class="flex gap-1.5">
                    
                      <button 
                        class="py-1 px-2 bg-sky-500 text-white rounded text-xs font-medium hover:bg-sky-600 transition min-h-[36px]" 
                        data-account='${accountDataJson.replace(
                          /'/g,
                          "&apos;",
                        )}'
                        onclick="(function(btn) { 
                          const data = JSON.parse(btn.getAttribute('data-account')); 
                          mobileEditSchoolAccount(data.authUsername, data.schoolUsername, data.password, data.ua); 
                        })(this)"
                        title="编辑此账户">
                        编辑
                      </button>
                      
                      <!-- 删除按钮 -->
                      <!-- 点击时调用deleteSchoolAccount函数（PC端和移动端共用） -->
                      <!-- 删除成功后会自动刷新列表 -->
                      <!-- bg-red-500: 红色背景，表示危险操作 -->
                      <!-- hover:bg-red-600: 鼠标悬停时颜色加深 -->
                      <!-- 【尺寸优化】与编辑按钮保持一致：min-h-[36px] + py-1 px-2 -->
                      <button 
                        class="py-1 px-2 bg-red-500 text-white rounded text-xs font-medium hover:bg-red-600 transition min-h-[36px]" 
                        data-auth-username='${escapeHtml(username)}'
                        data-school-username='${escapeHtml(schoolUsername)}'
                        onclick="(function(btn) { 
                          deleteSchoolAccount(
                            btn.getAttribute('data-auth-username'), 
                            btn.getAttribute('data-school-username')
                          ); 
                        })(this)"
                        title="删除此账户">
                        删除
                      </button>
                      
                      <!-- 查看详情按钮 -->
                      <!-- 调用View_details_of_users_with_outstanding_payments函数 -->
                      <!-- 显示学号、姓名、欠费信息等详细数据 -->
                      <!-- bg-emerald-500: 翡翠绿色背景 -->
                      <!-- hover:bg-emerald-600: 鼠标悬停时颜色加深 -->
                      <!-- 【尺寸优化】与编辑按钮保持一致：min-h-[36px] + py-1 px-2 -->
                      <button 
                        class="py-1 px-2 bg-emerald-500 text-white rounded text-xs font-medium hover:bg-emerald-600 transition min-h-[36px]" 
                        onclick="View_details_of_users_with_outstanding_payments(${escapeInlineJsArg(
                          schoolUsername,
                        )})"
                        title="查看此账户的详细信息">
                        详情
                      </button>
                    </div>
                  </div>
                  
                  <!-- 密码显示行 -->
                  <!-- text-xs: 小字体（12px） -->
                  <div class="text-xs">
                    <!-- 标签文字 -->
                    <!-- text-slate-500: 中灰色，次要信息 -->
                    <span class="text-slate-500">密码:</span>
                    
                    <!-- 密码内容 -->
                    <!-- font-mono: 等宽字体，适合显示密码 -->
                    <!-- text-slate-700: 深灰色 -->
                    <!-- ml-2: 左边距0.5rem（8px） -->
                    <!-- select-all: 点击时自动全选内容，方便复制 -->
                    <span class="font-mono text-slate-700 ml-2 select-all">
                      ${escapeHtml(password)}
                    </span>
                  </div>
                  
                  ${
                    // 条件渲染：只在UA存在时显示User-Agent区域
                    ua
                      ? `
                  <!-- User-Agent显示区域 -->
                  <div class="text-xs">
                    <!-- 标签文字 -->
                    <span class="text-slate-500">User-Agent:</span>
                    
                    <!-- UA内容容器 -->
                    <!-- font-mono: 等宽字体，适合显示长字符串 -->
                    <!-- text-xs: 小字体 -->
                    <!-- text-slate-600: 中灰色 -->
                    <!-- mt-1: 顶部外边距0.25rem（4px） -->
                    <!-- p-2: 内边距0.5rem（8px） -->
                    <!-- bg-white: 白色背景，与卡片背景区分 -->
                    <!-- rounded: 小圆角 -->
                    <!-- break-all: 允许在任意字符处换行，避免长字符串溢出 -->
                    <!-- select-all: 点击时自动全选内容，方便复制 -->
                    <div class="font-mono text-xs text-slate-600 mt-1 p-2 bg-white rounded break-all select-all">
                      ${escapeHtml(ua)}
                    </div>
                  </div>
                  `
                      : "" // 如果ua不存在，返回空字符串，不渲染该区域
                  }
                </div>
              `;
      }

      // 将生成的HTML插入到列表容器中
      listContainer.innerHTML = html;
    }

    // ========== 显示移动端模态框 ==========
    // 调用showModal工具函数显示模态框
    // showModal会自动处理显示动画、事件绑定等工作
    showModal("mobile-user-school-accounts-modal");

    // 输出成功日志
    console.log("[移动端学校账户管理] 模态框已显示");
  } catch (error) {
    // ========== 错误处理 ==========
    // 捕获所有可能的异常（网络错误、解析错误等）

    // 输出详细的错误日志到控制台，便于开发调试
    console.error("[移动端学校账户管理] 加载失败：", error);

    // 显示友好的错误提示给用户
    // error.message包含错误的具体描述
    // showModalAlert("加载失败: " + error.message, "错误");
    Swal.fire({
      title: "错误",
      text: "加载失败: " + error.message,
      icon: "error",
    });
  }
}
// ==================== 移动端学校账户管理功能 END ====================

async function manageUserPermissions(username) {
  currentManageUsername = username;
  const modal = $("manage-user-permissions-modal");
  if (!modal) return;

  try {
    const response = await fetch("/auth/admin/get_user_permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({ username: username }),
    });
    const result = await response.json();

    if (!result.success) {
      // showModalAlert("无法加载用户权限信息", "错误");
      Swal.fire({
        title: "错误",
        text: "无法加载用户权限信息",
        icon: "error",
      });
      return;
    }

    const nameEl = $("manage-user-name");
    const groupEl = $("user-base-group");
    if (nameEl) nameEl.textContent = username;
    if (groupEl) groupEl.textContent = result.group || "guest";

    if (groupEl === "super_admin") {
      // showModalAlert("无法修改超级管理员的权限", "错误");
      Swal.fire({
        title: "错误",
        text: "无法修改超级管理员的权限",
        icon: "error",
      });
      return;
    }
    const permissionsContainer = $("manage-user-permissions-list");
    if (permissionsContainer && result.all_permissions) {
      const groupPerms = result.group_permissions || {};
      const addedPerms = result.added_permissions || {};
      const removedPerms = result.removed_permissions || {};

      permissionsContainer.innerHTML = Object.keys(result.all_permissions)
        .map((perm) => {
          const groupHas = groupPerms[perm] || false;
          const isAdded = addedPerms[perm] === true;
          const isRemoved = removedPerms[perm] === true;
          const currentValue = result.all_permissions[perm];

          let statusClass = "";
          let statusText = "";
          if (isAdded) {
            statusClass = "bg-green-50 border-green-200";
            statusText = "(新增)";
          } else if (isRemoved) {
            statusClass = "bg-red-50 border-red-200";
            statusText = "(移除)";
          }

          return `
              <label class="flex items-center gap-2 p-2 hover:bg-slate-50 rounded cursor-pointer border ${statusClass}">
                <input type="checkbox" class="w-4 h-4 rounded" data-permission="${perm}" data-group-value="${groupHas}" ${
                  currentValue ? "checked" : ""
                }>
                <span class="text-sm text-slate-700 flex-1">${translatePermission(
                  perm,
                )}</span>
                ${
                  statusText
                    ? `<span class="text-xs ${
                        isAdded ? "text-green-600" : "text-red-600"
                      }">${statusText}</span>`
                    : ""
                }
              </label>
            `;
        })
        .join("");
    }

    modal.classList.remove("hidden");
    modal.classList.add("flex");
  } catch (e) {
    // showModalAlert("加载失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "加载失败: " + e.message,
      icon: "error",
    });
  }
}

function closeManageUserPermissionsModal() {
  const modal = $("manage-user-permissions-modal");
  if (modal) {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }
  currentManageUsername = null;
}

async function submitManageUserPermissions() {
  if (!currentManageUsername) return;

  const permissionsContainer = $("manage-user-permissions-list");
  if (!permissionsContainer) return;

  const addedPermissions = {};
  const removedPermissions = {};

  const checkboxes = permissionsContainer.querySelectorAll(
    'input[type="checkbox"]',
  );
  checkboxes.forEach((cb) => {
    const perm = cb.getAttribute("data-permission");
    const groupValue = cb.getAttribute("data-group-value") === "true";
    const currentValue = cb.checked;

    if (currentValue !== groupValue) {
      if (currentValue) {
        addedPermissions[perm] = true;
      } else {
        removedPermissions[perm] = true;
      }
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
        username: currentManageUsername,
        added_permissions: addedPermissions,
        removed_permissions: removedPermissions,
      }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${currentManageUsername} 的权限已更新`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${currentManageUsername} 的权限已更新`,
        icon: "success",
      });
      closeManageUserPermissionsModal();
      loadAdminUsers();
    } else {
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

function showResetPasswordModal(username) {
  $("reset-password-username").textContent = username;
  $("reset-new-password").value = "";
  $("reset-confirm-password").value = "";
  showModal("reset-user-password-modal");
}

async function submitResetUserPassword() {
  const username = $("reset-password-username").textContent;
  const newPassword = $("reset-new-password").value;
  const confirmPassword = $("reset-confirm-password").value;

  if (!newPassword || !confirmPassword) {
    // showModalAlert("请填写所有密码字段", "提示");
    Swal.fire({
      title: "提示",
      text: "请填写所有密码字段",
      icon: "warning",
    });
    return;
  }

  if (newPassword.length < 6) {
    // showModalAlert("密码长度至少为6个字符", "错误");
    Swal.fire({
      title: "错误",
      text: "密码长度至少为6个字符",
      icon: "error",
    });
    return;
  }

  if (newPassword !== confirmPassword) {
    // showModalAlert("两次输入的密码不一致", "错误");
    Swal.fire({
      title: "错误",
      text: "两次输入的密码不一致",
      icon: "error",
    });
    return;
  }

  try {
    const response = await fetch("/auth/admin/reset_password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": sessionUUID,
      },
      body: JSON.stringify({
        username,
        new_password: newPassword,
      }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${username} 的密码已重置`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 的密码已重置`,
        icon: "success",
      });
      hideModal("reset-user-password-modal");
    } else {
      // showModalAlert(result.message || "密码重置失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "密码重置失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

function modifyUserPhone(username, currentPhone) {
  $("admin-modify-phone-username").value = username;
  $("admin-modify-phone-current").value = currentPhone || "未绑定";
  $("admin-modify-phone-new").value = "";
  $("admin-modify-phone-code").value = "";
  $("admin-modify-phone-modal").classList.remove("hidden");
  _showPhoneLocationNearInput($("admin-modify-phone-current"), currentPhone);

  const adminCurrentPhoneInput = $("admin-modify-phone-current");
  const adminCurrentPhoneWrapper = adminCurrentPhoneInput
    ? adminCurrentPhoneInput.closest(".phone-input-wrapper")
    : null;
  if (adminCurrentPhoneWrapper) {
    const prefix = adminCurrentPhoneWrapper.querySelector(".phone-prefix");
    const isUnbound =
      !adminCurrentPhoneInput.value ||
      adminCurrentPhoneInput.value === "未绑定";

    if (prefix) {
      prefix.style.display = isUnbound ? "none" : "inline";
    }
    adminCurrentPhoneWrapper.classList.toggle("prefix-hidden", isUnbound);
  }
}

function closeAdminModifyPhoneModal() {
  $("admin-modify-phone-modal").classList.add("hidden");
}

async function sendAdminModifyPhoneCode() {
  const newPhone = $("admin-modify-phone-new").value.trim();
  if (!newPhone || !/^1[3-9]\d{9}$/.test(newPhone)) {
    // showModalAlert("请输入正确的手机号");
    Swal.fire({
      title: "错误",
      text: "请输入正确的手机号",
      icon: "error",
    });
    return;
  }

  const sendBtn = $("admin-modify-phone-send-btn");
  // 注意：这里不再立即禁用按钮，而是由 openCaptchaModal 处理后续流程
  const originalText = "发送验证码";

  // 调用通用验证码模态框，它会自动处理图形验证和短信发送
  openCaptchaModal({
    phone: newPhone,
    button: sendBtn,
    originalText: originalText,
    scene: "modify", // 保持与旧代码一致的场景标识
  });
}

async function submitAdminModifyPhone() {
  const username = $("admin-modify-phone-username").value;
  const newPhone = $("admin-modify-phone-new").value.trim();
  const code = $("admin-modify-phone-code").value.trim();

  if (!newPhone) {
    // showModalAlert("请输入新手机号");
    Swal.fire({
      title: "错误",
      text: "请输入新手机号",
      icon: "error",
    });
    return;
  }

  if (!/^1[3-9]\d{9}$/.test(newPhone)) {
    // showModalAlert("请输入正确的手机号格式");
    Swal.fire({
      title: "错误",
      text: "请输入正确的手机号格式",
      icon: "error",
    });
    return;
  }
  try {
    const bindResult = await callPythonAPI_raw(
      "/api/auth/check_phone",
      "POST",
      { phone: newPhone },
    );
    if (
      bindResult &&
      bindResult.is_bound &&
      bindResult.bound_to_user !== username
    ) {
      const confirmed = await jsShowConfirm(
        "手机号已被绑定",
        `您输入的新手机号 ${newPhone} 已被用户 ${bindResult.bound_to_user} 绑定。\n\n是否继续？\n\n如果继续，该手机号将从原账号上强制解绑并绑定到 ${username} 账号上。`,
      );

      if (!confirmed) {
        logMessage_Info(
          "[管理员修改手机号] 用户取消操作，因为手机号已被绑定。",
        );
        return;
      }
      logMessage_Info("[管理员修改手机号] 用户已确认强制解绑，继续操作...");
    } else if (
      bindResult &&
      bindResult.is_bound &&
      bindResult.bound_to_user === username
    ) {
      // showModalAlert("此手机号已绑定到该用户。", "提示");
      Swal.fire({
        title: "提示",
        text: "此手机号已绑定到该用户。",
        icon: "info",
      });
      closeAdminModifyPhoneModal();
      return;
    }
  } catch (e) {
    logMessage_Error("检查手机号绑定失败:", e);
    // showModalAlert(`检查手机号失败: ${e.message}，请稍后重试`, "网络错误");
    Swal.fire({
      title: "网络错误",
      text: `检查手机号失败: ${e.message}，请稍后重试`,
      icon: "error",
    });
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
        new_phone: newPhone,
        sms_code: code || "",
      }),
    });

    const result = await response.json();
    if (result.success) {
      // showModalAlert(`用户 ${username} 的手机号已更新`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 的手机号已更新`,
        icon: "success",
      });
      closeAdminModifyPhoneModal();
      loadAdminUsers();
    } else {
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}

function modifyUserNickname(username, currentNickname) {
  $("admin-modify-nickname-username").value = username;
  $("admin-modify-nickname-current").value = currentNickname || "未设置";
  $("admin-modify-nickname-new").value = "";
  $("admin-modify-nickname-modal").classList.remove("hidden");
}

function closeAdminModifyNicknameModal() {
  $("admin-modify-nickname-modal").classList.add("hidden");
}

async function submitAdminModifyNickname() {
  const username = $("admin-modify-nickname-username").value;
  const newNickname = $("admin-modify-nickname-new").value.trim();

  if (!newNickname) {
    // showModalAlert("请输入新昵称");
    Swal.fire({
      title: "错误",
      text: "请输入新昵称",
      icon: "error",
    });
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
      // showModalAlert(`用户 ${username} 的昵称已更新`, "成功");
      Swal.fire({
        title: "成功",
        text: `用户 ${username} 的昵称已更新`,
        icon: "success",
      });
      closeAdminModifyNicknameModal();
      loadAdminUsers();
    } else {
      // showModalAlert(result.message || "更新失败", "错误");
      Swal.fire({
        title: "错误",
        text: result.message || "更新失败",
        icon: "error",
      });
    }
  } catch (e) {
    // showModalAlert("操作失败: " + e.message, "错误");
    Swal.fire({
      title: "错误",
      text: "操作失败: " + e.message,
      icon: "error",
    });
  }
}
