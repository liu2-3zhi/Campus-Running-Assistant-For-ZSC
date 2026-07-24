<script setup>
import { ref, computed, onMounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

const API_URL = '/api/amap/watermark_control/config'

const loading = ref(false)
const saving = ref(false)
const refreshing = ref(false)
const success = ref('')
const error = ref('')

// 系统默认去水印权限（未在下方列表中配置的用户使用此默认值）
const defaultValue = ref(false)
// 已自定义用户列表：[{ username, enabled }]
const configuredUsers = ref([])
// 全部用户名（用于「添加用户」弹窗）
const allUsers = ref([])

// 添加用户弹窗状态
const showAddModal = ref(false)
const userSearch = ref('')
const modalLoading = ref(false)
const pendingUser = ref('')

function clearMessages() {
  success.value = ''
  error.value = ''
}

const defaultLabel = computed(() => (defaultValue.value ? '允许' : '禁止'))
const userCount = computed(() => configuredUsers.value.length)

// 可添加用户 = 全部用户 - 已配置用户，并按搜索关键字过滤
const availableUsers = computed(() => {
  const configured = new Set(configuredUsers.value.map((u) => u.username))
  const kw = userSearch.value.trim().toLowerCase()
  return allUsers.value
    .filter((u) => !configured.has(u))
    .filter((u) => !kw || String(u).toLowerCase().includes(kw))
})

function applyConfig(data) {
  const cfg = (data && data.config) || {}
  defaultValue.value = !!cfg.default
  const usersObj = cfg.users || {}
  configuredUsers.value = Object.keys(usersObj)
    .sort()
    .map((username) => ({ username, enabled: !!usersObj[username] }))
  allUsers.value = (data && data.all_users) || []
}

// 读取水印控制配置（对应 loadWatermarkControlConfig）
async function loadConfig() {
  loading.value = true
  clearMessages()
  try {
    const data = await callRawAPI(API_URL, 'GET')
    applyConfig(data)
  } catch (e) {
    error.value = e.message || '加载水印控制配置失败'
  } finally {
    loading.value = false
  }
}

// 保存水印控制配置（对应 saveWatermarkControlConfig）
async function saveConfig() {
  saving.value = true
  clearMessages()
  try {
    const users = {}
    configuredUsers.value.forEach((u) => {
      users[u.username] = !!u.enabled
    })
    const data = await callRawAPI(API_URL, 'PUT', {
      default: defaultValue.value,
      users,
    })
    if (data && data.success === false) {
      error.value = data.message || '保存失败'
    } else {
      success.value = '水印控制配置已保存'
    }
  } catch (e) {
    error.value = e.message || '保存水印控制配置失败'
  } finally {
    saving.value = false
  }
}

// 刷新配置（对应刷新按钮 / refreshWatermarkUserList）
async function refreshConfig() {
  refreshing.value = true
  clearMessages()
  try {
    const data = await callRawAPI(API_URL, 'GET')
    applyConfig(data)
    success.value = '已从服务器重新加载配置'
  } catch (e) {
    error.value = e.message || '刷新配置失败'
  } finally {
    refreshing.value = false
  }
}

// 删除用户自定义配置（对应 deleteWatermarkUser）
async function deleteUser(username) {
  if (!window.confirm(`确定要移除用户 "${username}" 的自定义水印配置吗？移除后该用户将使用系统默认值。`)) {
    return
  }
  clearMessages()
  try {
    const data = await callRawAPI(API_URL, 'GET')
    const usersObj = (data && data.config && data.config.users) || {}
    delete usersObj[username]
    await callRawAPI(API_URL, 'PUT', { users: usersObj })
    success.value = `已移除用户 "${username}" 的水印配置`
    await loadConfig()
  } catch (e) {
    error.value = e.message || '移除用户失败'
  }
}

// 打开添加用户弹窗（对应 openAddWatermarkUserModal）
async function openAddModal() {
  showAddModal.value = true
  userSearch.value = ''
  modalLoading.value = true
  clearMessages()
  try {
    const data = await callRawAPI(API_URL, 'GET')
    applyConfig(data)
  } catch (e) {
    error.value = e.message || '加载可添加用户列表失败'
  } finally {
    modalLoading.value = false
  }
}

function closeAddModal() {
  showAddModal.value = false
  userSearch.value = ''
}

// 刷新弹窗内的可添加用户列表（对应 refreshWatermarkUserList）
async function refreshAvailableUsers() {
  modalLoading.value = true
  try {
    const data = await callRawAPI(API_URL, 'GET')
    applyConfig(data)
  } catch (e) {
    error.value = e.message || '刷新用户列表失败'
  } finally {
    modalLoading.value = false
  }
}

// 添加用户到水印控制（对应 addWatermarkUser）
async function addUser(username) {
  pendingUser.value = username
  clearMessages()
  try {
    const data = await callRawAPI(API_URL, 'GET')
    const cfg = (data && data.config) || {}
    const usersObj = cfg.users || {}
    usersObj[username] = true
    await callRawAPI(API_URL, 'PUT', { default: cfg.default, users: usersObj })
    success.value = `已添加用户 "${username}"`
    closeAddModal()
    await loadConfig()
  } catch (e) {
    error.value = e.message || '添加用户失败'
  } finally {
    pendingUser.value = ''
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="space-y-6">
    <!-- Alerts -->
    <div
      v-if="success"
      class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between"
    >
      <span>{{ success }}</span>
      <button @click="success = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>
    <div
      v-if="error"
      class="p-3 rounded-lg bg-red-500/10 text-red-500 flex items-center justify-between"
    >
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-[var(--ink-muted)]">加载中...</div>

    <template v-else>
      <!-- 标题 -->
      <div>
        <h2 class="text-lg font-semibold text-[var(--ink)]">高德地图去水印控制</h2>
        <p class="text-sm text-[var(--ink-secondary)] mt-1">
          配置用户是否可以使用高德地图去水印功能。未配置的用户使用系统默认值。
        </p>
      </div>

      <!-- 系统默认值配置 -->
      <div class="panel p-5 space-y-3">
        <h3 class="text-base font-semibold text-[var(--ink)]">系统默认值</h3>
        <div class="flex flex-col sm:flex-row sm:items-center gap-3">
          <label class="text-sm text-[var(--ink-secondary)]">系统默认去水印权限：</label>
          <select v-model="defaultValue" class="select-field w-full sm:w-40">
            <option :value="true">允许</option>
            <option :value="false">禁止</option>
          </select>
          <span
            class="text-sm font-medium"
            :class="defaultValue ? 'text-[var(--accent)]' : 'text-[var(--ink-muted)]'"
          >
            当前：{{ defaultLabel }}
          </span>
        </div>
        <p class="text-xs text-[var(--ink-muted)]">未在下方列表中配置的用户将使用此默认值。</p>
      </div>

      <!-- 用户权限配置 -->
      <div class="panel p-5 space-y-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-base font-semibold text-[var(--ink)]">用户权限配置</h3>
            <p class="text-xs text-[var(--ink-muted)] mt-1">共 {{ userCount }} 个用户</p>
          </div>
          <button
            @click="openAddModal"
            class="btn btn-secondary text-sm"
            title="点击添加用户到水印控制列表"
          >
            添加用户
          </button>
        </div>

        <div
          class="border border-[var(--border-color)] rounded-lg divide-y divide-[var(--border-color)] max-h-[50vh] overflow-y-auto"
        >
          <div
            v-if="configuredUsers.length === 0"
            class="px-4 py-8 text-center text-sm text-[var(--ink-muted)]"
          >
            暂无自定义用户，全部用户使用系统默认值
          </div>
          <div
            v-for="user in configuredUsers"
            :key="user.username"
            class="flex items-center justify-between gap-3 px-4 py-3 hover:bg-[var(--glass)]"
          >
            <span class="text-sm text-[var(--ink)] font-medium truncate">{{ user.username }}</span>
            <div class="flex items-center gap-4 shrink-0">
              <label class="flex items-center gap-2 cursor-pointer text-sm">
                <input
                  v-model="user.enabled"
                  type="checkbox"
                  class="watermark-user-checkbox accent-[var(--accent)] w-4 h-4"
                />
                <span :class="user.enabled ? 'text-[var(--accent)]' : 'text-[var(--ink-muted)]'">
                  {{ user.enabled ? '允许' : '禁止' }}
                </span>
              </label>
              <button
                @click="deleteUser(user.username)"
                class="btn btn-danger text-xs px-2 py-1"
                title="移除该用户的自定义配置"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作按钮组 -->
      <div class="flex flex-col sm:flex-row gap-3">
        <button
          @click="refreshConfig"
          :disabled="refreshing"
          class="btn btn-ghost flex-1"
          title="点击从服务器重新加载水印控制配置"
        >
          {{ refreshing ? '刷新中...' : '刷新配置' }}
        </button>
        <button
          @click="saveConfig"
          :disabled="saving"
          class="btn btn-primary flex-1"
          title="点击保存当前的水印控制配置"
        >
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </template>

    <!-- 添加用户弹窗 -->
    <div
      v-if="showAddModal"
      class="fixed inset-0 z-[20001] flex items-center justify-center p-4"
    >
      <div class="absolute inset-0 bg-black/70" @click="closeAddModal"></div>
      <div
        class="relative panel w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden"
      >
        <!-- 标题栏 -->
        <div class="flex items-center justify-between gap-3 p-4 border-b border-[var(--border-color)]">
          <h3 class="text-base font-semibold text-[var(--ink)]">添加用户到水印控制</h3>
          <div class="flex items-center gap-2">
            <button
              @click="refreshAvailableUsers"
              :disabled="modalLoading"
              class="btn btn-ghost text-xs px-2 py-1"
              title="刷新用户列表"
            >
              刷新
            </button>
            <button
              @click="closeAddModal"
              class="text-[var(--ink-muted)] hover:text-[var(--ink)] text-xl leading-none px-1"
              title="关闭"
            >
              &times;
            </button>
          </div>
        </div>

        <!-- 内容区 -->
        <div class="p-4 space-y-3 overflow-y-auto">
          <p class="text-xs text-[var(--ink-secondary)]">
            从下方列表中选择要添加到水印控制配置的用户。添加后，您可以为该用户设置是否允许使用去水印功能。
          </p>
          <input
            v-model="userSearch"
            type="text"
            class="input-field w-full"
            placeholder="搜索用户名..."
            aria-label="搜索用户"
          />

          <div v-if="modalLoading" class="py-8 text-center text-sm text-[var(--ink-muted)]">
            加载中...
          </div>
          <div
            v-else
            class="border border-[var(--border-color)] rounded-lg divide-y divide-[var(--border-color)] max-h-[50vh] overflow-y-auto"
          >
            <div
              v-if="availableUsers.length === 0"
              class="px-4 py-8 text-center text-sm text-[var(--ink-muted)]"
            >
              没有可添加的用户
            </div>
            <div
              v-for="u in availableUsers"
              :key="u"
              class="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-[var(--glass)]"
            >
              <span class="text-sm text-[var(--ink)] truncate">{{ u }}</span>
              <button
                @click="addUser(u)"
                :disabled="pendingUser === u"
                class="btn btn-primary text-xs px-3 py-1 shrink-0"
              >
                {{ pendingUser === u ? '添加中...' : '添加' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 底部 -->
        <div class="p-4 border-t border-[var(--border-color)] flex justify-end">
          <button @click="closeAddModal" class="btn btn-ghost" title="关闭对话框">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
