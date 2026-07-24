<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-[var(--ink)]">权限组管理</h2>

    <!-- Error / Success messages -->
    <div
      v-if="errorMsg"
      class="px-4 py-2 rounded-lg bg-[var(--danger)]/10 text-[var(--danger)] text-sm"
    >
      {{ errorMsg }}
    </div>
    <div
      v-if="successMsg"
      class="px-4 py-2 rounded-lg bg-[var(--success)]/10 text-[var(--success)] text-sm"
    >
      {{ successMsg }}
    </div>

    <div class="flex flex-col md:flex-row gap-4">
      <!-- Left: Group list -->
      <div class="w-full md:w-64 flex-shrink-0 space-y-2">
        <div class="panel p-3 space-y-1">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm font-medium text-[var(--ink-secondary)]">权限组列表</span>
            <button class="btn btn-primary text-xs" @click="showCreateForm = true">
              + 新建
            </button>
          </div>

          <!-- Create form -->
          <div v-if="showCreateForm" class="space-y-2 mb-2">
            <input
              v-model="newGroupKey"
              type="text"
              class="input-field text-sm w-full"
              placeholder="组标识（英文，如 vip）"
            />
            <input
              v-model="newGroupName"
              type="text"
              class="input-field text-sm w-full"
              placeholder="组显示名称"
              @keyup.enter="createGroup"
            />
            <div class="flex gap-2">
              <button class="btn btn-primary text-xs flex-1" :disabled="creating" @click="createGroup">
                {{ creating ? '...' : '创建' }}
              </button>
              <button class="btn btn-ghost text-xs" @click="cancelCreate">取消</button>
            </div>
          </div>

          <!-- Loading -->
          <div v-if="loading" class="py-4 text-center text-[var(--ink-muted)] text-sm">
            加载中...
          </div>

          <!-- Group items -->
          <template v-else>
            <div
              v-for="group in groupList"
              :key="group.key"
              class="px-3 py-2 rounded-lg cursor-pointer transition-colors flex items-center justify-between"
              :class="
                selectedKey === group.key
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--ink-secondary)] hover:bg-[var(--glass)]'
              "
              @click="selectGroup(group)"
            >
              <span class="text-sm truncate">{{ group.name }}</span>
              <span
                v-if="group.is_system"
                class="text-xs px-1.5 py-0.5 rounded-full"
                :class="
                  selectedKey === group.key
                    ? 'bg-white/20 text-white'
                    : 'bg-[var(--glass)] text-[var(--ink-muted)]'
                "
              >
                系统
              </span>
            </div>
            <div
              v-if="groupList.length === 0"
              class="py-4 text-center text-[var(--ink-muted)] text-sm"
            >
              暂无权限组
            </div>
          </template>
        </div>
      </div>

      <!-- Right: Permissions editor -->
      <div class="flex-1">
        <div v-if="!selectedGroup" class="panel p-6 text-center text-[var(--ink-muted)] text-sm">
          请从左侧选择一个权限组进行编辑
        </div>

        <div v-else class="panel p-4 space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-base font-semibold text-[var(--ink)]">
              {{ selectedGroup.name }}
              <span class="text-xs text-[var(--ink-muted)] font-mono">({{ selectedGroup.key }})</span>
            </h3>
            <button
              v-if="!selectedGroup.is_system"
              class="btn btn-danger text-xs"
              :disabled="deleting"
              @click="confirmDeleteGroup"
            >
              {{ deleting ? '删除中...' : '删除组' }}
            </button>
          </div>

          <p v-if="selectedGroup.key === 'super_admin'" class="text-xs text-[var(--warning)]">
            超级管理员组拥有所有权限且不可编辑。
          </p>

          <!-- Delete confirmation -->
          <div
            v-if="showDeleteConfirm"
            class="px-4 py-3 rounded-lg bg-[var(--danger)]/10 border border-[var(--danger)]/30 space-y-2"
          >
            <p class="text-sm text-[var(--danger)]">
              确定要删除权限组「{{ selectedGroup.name }}」吗？此操作不可撤销。
            </p>
            <div class="flex gap-2">
              <button class="btn btn-danger text-xs" :disabled="deleting" @click="deleteGroup">
                确认删除
              </button>
              <button class="btn btn-ghost text-xs" @click="showDeleteConfirm = false">
                取消
              </button>
            </div>
          </div>

          <!-- Permissions checkboxes -->
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            <label
              v-for="key in allPermissionKeys"
              :key="key"
              class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-[var(--glass)] cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="editPermissions.includes(key)"
                :disabled="selectedGroup.key === 'super_admin'"
                class="rounded border-[var(--border-color)] text-[var(--accent)] focus:ring-[var(--accent)]"
                @change="togglePermission(key)"
              />
              <span class="text-sm text-[var(--ink)]">{{ translatePermission(key) }}</span>
            </label>
          </div>

          <!-- Save button -->
          <div class="flex justify-end">
            <button
              class="btn btn-primary"
              :disabled="saving || selectedGroup.key === 'super_admin'"
              @click="savePermissions"
            >
              {{ saving ? '保存中...' : '保存权限' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

/* 权限键 → 中文文案（未命中回退原始键） */
const PERMISSION_LABELS = {
  view_tasks: '查看任务', create_tasks: '创建任务', delete_tasks: '删除任务',
  start_tasks: '开始任务', stop_tasks: '停止任务', view_map: '查看地图',
  record_path: '录制路径', auto_generate_path: '自动生成路径',
  view_notifications: '查看通知', mark_notifications_read: '标记通知已读',
  view_user_details: '查看用户详情', modify_user_settings: '修改用户设置',
  execute_multi_account: '多账号执行', use_attendance: '使用签到',
  view_logs: '查看日志', clear_logs: '清空日志', auto_fill_password: '自动填充密码',
  import_offline: '离线导入', export_data: '导出数据', modify_params: '修改参数',
  manage_own_sessions: '管理自己的会话', use_login_button: '使用登录按钮',
  use_multi_account_button: '使用多账号按钮', use_import_button: '使用导入按钮',
  view_messages: '查看留言', post_messages: '发布留言',
  delete_own_messages: '删除自己的留言', delete_any_messages: '删除任意留言',
  modify_config: '修改配置', view_session_details: '查看会话详情',
  manage_users: '用户管理', manage_permissions: '权限管理',
  reset_user_password: '重置用户密码', view_audit_logs: '查看审计日志',
  view_all_sessions: '查看所有会话', force_logout_users: '强制登出用户',
  manage_user_sessions: '管理用户会话', view_captcha_history: '查看验证码历史',
  manage_system: '系统管理', create_permission_groups: '创建权限组',
  modify_permission_groups: '修改权限组', delete_permission_groups: '删除权限组',
  god_mode: '上帝模式', manage_billing: '账单管理', view_billing_logs: '查看账单日志',
  restore_accounts: '恢复账号', manage_payment: '支付管理', manage_pricing: '定价管理',
  manage_watermark: '水印管理',
}

function translatePermission(key) {
  return PERMISSION_LABELS[key] || key
}

const groups = ref({})          // dict: key -> { name, is_system, permissions:{k:bool} }
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const showCreateForm = ref(false)
const newGroupKey = ref('')
const newGroupName = ref('')
const creating = ref(false)

const selectedKey = ref(null)
const selectedGroup = ref(null)
const editPermissions = ref([])
const saving = ref(false)

const showDeleteConfirm = ref(false)
const deleting = ref(false)

const groupList = computed(() =>
  Object.entries(groups.value || {}).map(([key, g]) => ({
    key,
    name: g.name || key,
    is_system: g.is_system || false,
    permissions: g.permissions || {},
  }))
)

/* 所有权限键的并集（后端已将每组补全为同一键集） */
const allPermissionKeys = computed(() => {
  const set = new Set()
  for (const g of Object.values(groups.value || {})) {
    for (const k of Object.keys(g.permissions || {})) set.add(k)
  }
  return Array.from(set).sort()
})

function clearMessages() {
  errorMsg.value = ''
  successMsg.value = ''
}

function showSuccess(msg) {
  successMsg.value = msg
  errorMsg.value = ''
  setTimeout(() => { successMsg.value = '' }, 3000)
}

function showError(msg) {
  errorMsg.value = msg
  successMsg.value = ''
}

async function fetchGroups() {
  loading.value = true
  clearMessages()
  try {
    const data = await callRawAPI('/auth/admin/list_groups', 'GET')
    groups.value = data.groups || {}
    // 保持当前选中
    if (selectedKey.value && groups.value[selectedKey.value]) {
      selectGroup({ key: selectedKey.value, ...groups.value[selectedKey.value] })
    }
  } catch (e) {
    showError(e.message || '获取权限组失败')
  } finally {
    loading.value = false
  }
}

function selectGroup(group) {
  selectedKey.value = group.key
  const g = groups.value[group.key] || {}
  selectedGroup.value = { key: group.key, name: g.name || group.key, is_system: g.is_system || false }
  const perms = g.permissions || {}
  editPermissions.value = Object.keys(perms).filter(k => perms[k])
  showDeleteConfirm.value = false
  clearMessages()
}

function togglePermission(key) {
  const idx = editPermissions.value.indexOf(key)
  if (idx >= 0) {
    editPermissions.value.splice(idx, 1)
  } else {
    editPermissions.value.push(key)
  }
}

function cancelCreate() {
  showCreateForm.value = false
  newGroupKey.value = ''
  newGroupName.value = ''
}

async function createGroup() {
  const key = newGroupKey.value.trim()
  const name = newGroupName.value.trim()
  if (!key) { showError('组标识不能为空'); return }
  if (!name) { showError('组显示名称不能为空'); return }
  creating.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/auth/admin/create_group', 'POST', {
      group_name: key,
      display_name: name,
      permissions: {},
    })
    if (res && res.success === false) throw new Error(res.message || '创建失败')
    showSuccess(`权限组「${name}」创建成功`)
    cancelCreate()
    await fetchGroups()
  } catch (e) {
    showError(e.message || '创建权限组失败')
  } finally {
    creating.value = false
  }
}

async function savePermissions() {
  if (!selectedGroup.value) return
  if (selectedGroup.value.key === 'super_admin') return
  saving.value = true
  clearMessages()
  try {
    // 构建完整的 {key: bool} 权限字典
    const permissions = {}
    for (const k of allPermissionKeys.value) {
      permissions[k] = editPermissions.value.includes(k)
    }
    const res = await callRawAPI('/auth/admin/update_group', 'POST', {
      group_key: selectedGroup.value.key,
      permissions,
    })
    if (res && res.success === false) throw new Error(res.message || '保存失败')
    showSuccess('权限已保存')
    await fetchGroups()
  } catch (e) {
    showError(e.message || '保存权限失败')
  } finally {
    saving.value = false
  }
}

function confirmDeleteGroup() {
  showDeleteConfirm.value = true
}

async function deleteGroup() {
  if (!selectedGroup.value) return
  deleting.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/auth/admin/delete_group', 'POST', { group_name: selectedGroup.value.key })
    if (res && res.success === false) throw new Error(res.message || '删除失败')
    showSuccess(`权限组「${selectedGroup.value.name}」已删除`)
    selectedKey.value = null
    selectedGroup.value = null
    editPermissions.value = []
    showDeleteConfirm.value = false
    await fetchGroups()
  } catch (e) {
    showError(e.message || '删除权限组失败')
  } finally {
    deleting.value = false
  }
}

onMounted(fetchGroups)
</script>
