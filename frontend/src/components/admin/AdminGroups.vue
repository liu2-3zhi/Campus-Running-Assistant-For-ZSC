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
          <div v-if="showCreateForm" class="flex gap-2 mb-2">
            <input
              v-model="newGroupName"
              type="text"
              class="input-field text-sm flex-1"
              placeholder="组名称"
              @keyup.enter="createGroup"
            />
            <button class="btn btn-primary text-xs" :disabled="creating" @click="createGroup">
              {{ creating ? '...' : '创建' }}
            </button>
            <button class="btn btn-ghost text-xs" @click="cancelCreate">取消</button>
          </div>

          <!-- Loading -->
          <div v-if="loading" class="py-4 text-center text-[var(--ink-muted)] text-sm">
            加载中...
          </div>

          <!-- Group items -->
          <template v-else>
            <div
              v-for="group in groups"
              :key="group.id"
              class="px-3 py-2 rounded-lg cursor-pointer transition-colors flex items-center justify-between"
              :class="
                selectedGroupId === group.id
                  ? 'bg-[var(--accent)] text-white'
                  : 'text-[var(--ink-secondary)] hover:bg-[var(--glass)]'
              "
              @click="selectGroup(group)"
            >
              <span class="text-sm truncate">{{ group.name }}</span>
              <span
                class="text-xs px-1.5 py-0.5 rounded-full"
                :class="
                  selectedGroupId === group.id
                    ? 'bg-white/20 text-white'
                    : 'bg-[var(--glass)] text-[var(--ink-muted)]'
                "
              >
                {{ group.member_count ?? 0 }}
              </span>
            </div>
            <div
              v-if="groups.length === 0"
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
              {{ selectedGroup.name }} - 权限配置
            </h3>
            <button
              class="btn btn-danger text-xs"
              :disabled="deleting"
              @click="confirmDeleteGroup"
            >
              {{ deleting ? '删除中...' : '删除组' }}
            </button>
          </div>

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
              v-for="perm in allPermissions"
              :key="perm.key"
              class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-[var(--glass)] cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="editPermissions.includes(perm.key)"
                class="rounded border-[var(--border-color)] text-[var(--accent)] focus:ring-[var(--accent)]"
                @change="togglePermission(perm.key)"
              />
              <span class="text-sm text-[var(--ink)]">{{ perm.label }}</span>
            </label>
          </div>

          <!-- Save button -->
          <div class="flex justify-end">
            <button
              class="btn btn-primary"
              :disabled="saving"
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
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const allPermissions = [
  { key: 'manage_users', label: '用户管理' },
  { key: 'manage_groups', label: '权限组管理' },
  { key: 'view_logs', label: '查看日志' },
  { key: 'manage_sessions', label: '会话管理' },
  { key: 'manage_ip_bans', label: 'IP封禁管理' },
  { key: 'manage_sms', label: '短信配置' },
  { key: 'manage_config', label: '系统配置' },
  { key: 'manage_captcha', label: '验证码管理' },
  { key: 'manage_reminders', label: '定时提醒' },
  { key: 'manage_ssl', label: 'SSL管理' },
  { key: 'manage_cdn', label: 'CDN管理' },
  { key: 'manage_security', label: '安全管理' },
  { key: 'view_payment_logs', label: '查看支付日志' },
  { key: 'manage_payment', label: '支付管理' },
  { key: 'manage_pricing', label: '定价管理' },
  { key: 'manage_watermark', label: '水印管理' },
  { key: 'manage_billing', label: '账单管理' },
  { key: 'view_billing_logs', label: '查看账单日志' },
  { key: 'restore_accounts', label: '恢复账号' },
]

const groups = ref([])
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

const showCreateForm = ref(false)
const newGroupName = ref('')
const creating = ref(false)

const selectedGroupId = ref(null)
const selectedGroup = ref(null)
const editPermissions = ref([])
const saving = ref(false)

const showDeleteConfirm = ref(false)
const deleting = ref(false)

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
    groups.value = data.groups || []
  } catch (e) {
    showError(e.message || '获取权限组失败')
  } finally {
    loading.value = false
  }
}

function selectGroup(group) {
  selectedGroupId.value = group.id
  selectedGroup.value = group
  editPermissions.value = [...(group.permissions || [])]
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
  newGroupName.value = ''
}

async function createGroup() {
  const name = newGroupName.value.trim()
  if (!name) return
  creating.value = true
  clearMessages()
  try {
    await callRawAPI('/auth/admin/create_group', 'POST', { group_name: name, display_name: name })
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
  saving.value = true
  clearMessages()
  try {
    await callRawAPI('/auth/admin/update_group', 'POST', {
      group_key: selectedGroup.value.id,
      permissions: editPermissions.value
    })
    showSuccess('权限已保存')
    await fetchGroups()
    // Re-select to update local state
    const updated = groups.value.find(g => g.id === selectedGroupId.value)
    if (updated) selectGroup(updated)
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
    await callRawAPI('/auth/admin/delete_group', 'POST', { group_name: selectedGroup.value.id })
    showSuccess(`权限组「${selectedGroup.value.name}」已删除`)
    selectedGroupId.value = null
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
