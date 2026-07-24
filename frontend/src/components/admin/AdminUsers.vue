<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

/* ── reactive state ── */
const users = ref([])
const groups = ref({})          // dict: { key: { name, is_system, permissions } }
const loading = ref(false)
const error = ref('')
const success = ref('')

/* ── search / filter ── */
const searchQuery = ref('')
const groupFilter = ref('')
const statusFilter = ref('')

/* ── sort ── */
const sortKey = ref('created_at')
const sortAsc = ref(false)

/* ── pagination ── */
const currentPage = ref(1)
const pageSize = ref(10)

/* ── add-user form ── */
const showAddForm = ref(false)
const addForm = ref({ username: '', password: '', nickname: '', phone: '', group: 'user' })
const addLoading = ref(false)

/* ── helpers ── */
function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr) {
  if (dateStr === null || dateStr === undefined || dateStr === '') return '--'
  let ms = dateStr
  if (typeof dateStr === 'number') {
    // 后端 created_at / last_login 多为 Unix 秒级时间戳
    ms = dateStr < 1e12 ? dateStr * 1000 : dateStr
  }
  const d = new Date(ms)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function groupName(key) {
  return groups.value?.[key]?.name || key || '--'
}

/* 可分配的权限组（后端禁止分配 super_admin） */
const groupOptions = computed(() =>
  Object.entries(groups.value || {})
    .filter(([key]) => key !== 'super_admin')
    .map(([key, g]) => ({ key, name: g.name || key }))
)

function sessionsText(u) {
  return u.max_sessions === -1 ? '无限制' : (u.max_sessions ?? 1)
}
function runsText(u) {
  if (u.available_runs === -1) return '无限'
  if (!u.available_runs) return '无'
  return u.available_runs
}

/* ── filtered + sorted + paginated users ── */
const filteredUsers = computed(() => {
  let list = users.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(u =>
      (u.auth_username || '').toLowerCase().includes(q) ||
      (u.nickname || '').toLowerCase().includes(q) ||
      (u.phone || '').toLowerCase().includes(q)
    )
  }
  if (groupFilter.value) {
    list = list.filter(u => u.group === groupFilter.value)
  }
  if (statusFilter.value) {
    list = list.filter(u => {
      if (statusFilter.value === 'active') return !u.banned
      if (statusFilter.value === 'banned') return u.banned
      return true
    })
  }
  return list
})

const sortedUsers = computed(() => {
  const list = [...filteredUsers.value]
  const key = sortKey.value
  const dir = sortAsc.value ? 1 : -1
  list.sort((a, b) => {
    let va = a[key] ?? ''
    let vb = b[key] ?? ''
    if ((key === 'max_sessions' || key === 'available_runs') ) {
      va = va === -1 ? Infinity : va
      vb = vb === -1 ? Infinity : vb
    }
    if (typeof va === 'string' && typeof vb === 'string') return va.localeCompare(vb) * dir
    return (va > vb ? 1 : va < vb ? -1 : 0) * dir
  })
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(sortedUsers.value.length / pageSize.value)))
const paginatedUsers = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return sortedUsers.value.slice(start, start + pageSize.value)
})

function toggleSort(key) {
  if (sortKey.value === key) {
    sortAsc.value = !sortAsc.value
  } else {
    sortKey.value = key
    sortAsc.value = true
  }
}

function sortIcon(key) {
  if (sortKey.value !== key) return ''
  return sortAsc.value ? '▲' : '▼'
}

function prevPage() { if (currentPage.value > 1) currentPage.value-- }
function nextPage() { if (currentPage.value < totalPages.value) currentPage.value++ }

function onFilterChange() { currentPage.value = 1 }

/* ── API: load users + groups ── */
async function loadUsers() {
  loading.value = true
  clearMessages()
  try {
    const [uRes, gRes] = await Promise.all([
      callRawAPI('/auth/admin/list_users', 'GET'),
      callRawAPI('/auth/admin/list_groups', 'GET').catch(() => ({ groups: {} })),
    ])
    users.value = uRes.users || []
    groups.value = gRes.groups || {}
  } catch (e) {
    error.value = e.message || '加载用户列表失败'
  } finally {
    loading.value = false
  }
}

/* ── API: add user ── */
async function submitAddUser() {
  if (!addForm.value.username || !addForm.value.password) {
    error.value = '用户名和密码不能为空'
    return
  }
  if (addForm.value.password.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  if (addForm.value.phone && !/^1[3-9]\d{9}$/.test(addForm.value.phone)) {
    error.value = '手机号格式不正确'
    return
  }
  addLoading.value = true
  clearMessages()
  try {
    await callRawAPI('/auth/admin/create_user', 'POST', {
      username: addForm.value.username,
      password: addForm.value.password,
      nickname: addForm.value.nickname,
      phone: addForm.value.phone,
      group: addForm.value.group,
    })
    success.value = '用户已添加'
    addForm.value = { username: '', password: '', nickname: '', phone: '', group: 'user' }
    showAddForm.value = false
    await loadUsers()
  } catch (e) {
    error.value = e.message || '添加用户失败'
  } finally {
    addLoading.value = false
  }
}

/* ── generic operation runner ── */
async function runOp(fn, okMsg) {
  clearMessages()
  try {
    const res = await fn()
    if (res && res.success === false) throw new Error(res.message || '操作失败')
    if (okMsg) success.value = okMsg
    await loadUsers()
  } catch (e) {
    error.value = e.message || '操作失败'
  }
}

/* ── ban / unban ── */
function toggleBan(user) {
  const action = user.banned ? 'unban' : 'ban'
  runOp(
    () => callRawAPI('/auth/admin/' + action + '_user', 'POST', { username: user.auth_username }),
    user.banned ? '已解封用户' : '已封禁用户'
  )
}

/* ── delete ── */
function deleteUser(user) {
  if (!confirm('确定要删除用户 "' + user.auth_username + '" 吗？此操作不可恢复。')) return
  runOp(() => callRawAPI('/auth/admin/delete_user', 'POST', { username: user.auth_username }), '用户已删除')
}

/* ── reset password（管理员输入新密码） ── */
function resetPassword(user) {
  const pwd = prompt('为用户 "' + user.auth_username + '" 设置新密码（至少 6 位）：', '')
  if (pwd === null) return
  if (pwd.length < 6) { error.value = '密码至少 6 位'; return }
  runOp(
    () => callRawAPI('/auth/admin/force_reset_password', 'POST', { target_username: user.auth_username, new_password: pwd }),
    '密码已重置'
  )
}

/* ── force logout ── */
function forceLogout(user) {
  if (!confirm('确定要强制登出用户 "' + user.auth_username + '" 的所有会话吗？')) return
  runOp(() => callRawAPI('/auth/admin/force_logout_user', 'POST', { username: user.auth_username }), '已强制登出该用户')
}

/* ── force disable 2FA ── */
function forceDisable2FA(user) {
  if (!confirm('确定要强制关闭用户 "' + user.auth_username + '" 的双因素认证 (2FA) 吗？')) return
  runOp(() => callRawAPI('/auth/admin/force_disable_2fa', 'POST', { target_username: user.auth_username }), '已关闭该用户 2FA')
}

/* ── clear avatar ── */
function clearAvatar(user) {
  if (!confirm('确定要清除用户 "' + user.auth_username + '" 的头像吗？')) return
  runOp(() => callRawAPI('/auth/admin/clear_user_avatar', 'POST', { username: user.auth_username }), '已清除该用户头像')
}

/* ── set max sessions（0 => 无限制/-1） ── */
function setMaxSessions(user) {
  const cur = user.max_sessions === -1 ? 0 : (user.max_sessions ?? 1)
  const input = prompt('设置用户 "' + user.auth_username + '" 的最大会话数（0 表示无限制）：', String(cur))
  if (input === null) return
  const n = parseInt(input, 10)
  if (isNaN(n) || n < 0) { error.value = '请输入非负整数'; return }
  const max_sessions = n === 0 ? -1 : n
  runOp(() => callRawAPI('/auth/admin/update_max_sessions', 'POST', { username: user.auth_username, max_sessions }), '已更新最大会话数')
}

/* ── edit available runs（-1 无限，0 无） ── */
function editAvailableRuns(user) {
  const input = prompt('设置用户 "' + user.auth_username + '" 的可用执行次数（-1 无限，0 无）：', String(user.available_runs ?? 0))
  if (input === null) return
  const n = parseInt(input, 10)
  if (isNaN(n) || n < -1) { error.value = '请输入 -1 或非负整数'; return }
  runOp(() => callRawAPI('/api/admin/update_available_runs', 'POST', { username: user.auth_username, available_runs: n }), '已更新可用次数')
}

/* ── modify nickname ── */
function modifyNickname(user) {
  const input = prompt('修改用户 "' + user.auth_username + '" 的昵称：', user.nickname || '')
  if (input === null) return
  const nickname = input.trim()
  if (!nickname) { error.value = '昵称不能为空'; return }
  runOp(() => callRawAPI('/auth/admin/update_user_nickname', 'POST', { username: user.auth_username, nickname }), '昵称已更新')
}

/* ── modify phone（可选短信验证码） ── */
function modifyPhone(user) {
  const input = prompt('修改用户 "' + user.auth_username + '" 的手机号：', user.phone || '')
  if (input === null) return
  const new_phone = input.trim()
  if (!/^1[3-9]\d{9}$/.test(new_phone)) { error.value = '手机号格式不正确'; return }
  const code = prompt('短信验证码（如无需验证可留空）：', '')
  if (code === null) return
  runOp(
    () => callRawAPI('/auth/admin/update_user_phone', 'POST', { username: user.auth_username, new_phone, sms_code: code.trim() }),
    '手机号已更新'
  )
}

/* ── update group ── */
function updateGroup(user, newGroup) {
  if (!newGroup || newGroup === user.group) return
  runOp(() => callRawAPI('/auth/admin/update_user_group', 'POST', { target_username: user.auth_username, new_group: newGroup }), '权限组已更新')
}

/* ── lifecycle ── */
onMounted(loadUsers)
</script>

<template>
  <div class="space-y-4">

    <!-- success / error alerts -->
    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&#x2715;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <!-- top bar: filters + add button -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="searchQuery"
          class="input-field w-48"
          type="text"
          placeholder="搜索用户名/昵称/手机"
          @input="onFilterChange"
        />
        <select v-model="groupFilter" class="select-field" @change="onFilterChange">
          <option value="">全部权限组</option>
          <option v-for="opt in groupOptions" :key="opt.key" :value="opt.key">{{ opt.name }}</option>
        </select>
        <select v-model="statusFilter" class="select-field" @change="onFilterChange">
          <option value="">全部状态</option>
          <option value="active">正常</option>
          <option value="banned">已封禁</option>
        </select>
      </div>
      <button class="btn btn-primary" @click="showAddForm = !showAddForm">
        {{ showAddForm ? '取消' : '添加用户' }}
      </button>
    </div>

    <!-- add-user form panel -->
    <div v-if="showAddForm" class="panel p-4 space-y-3">
      <h3 class="font-medium text-[var(--ink)]">添加新用户</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">用户名 *</label>
          <input v-model="addForm.username" class="input-field w-full" type="text" placeholder="用户名" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">密码 *</label>
          <input v-model="addForm.password" class="input-field w-full" type="password" placeholder="密码（至少 6 位）" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">昵称</label>
          <input v-model="addForm.nickname" class="input-field w-full" type="text" placeholder="昵称" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">手机号</label>
          <input v-model="addForm.phone" class="input-field w-full" type="text" placeholder="手机号（可选）" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">权限组</label>
          <select v-model="addForm.group" class="select-field w-full">
            <option v-for="opt in groupOptions" :key="opt.key" :value="opt.key">{{ opt.name }}</option>
          </select>
        </div>
      </div>
      <div class="flex items-center gap-2 pt-1">
        <button class="btn btn-primary" :disabled="addLoading" @click="submitAddUser">
          {{ addLoading ? '提交中...' : '提交' }}
        </button>
        <button class="btn btn-secondary" @click="showAddForm = false">取消</button>
      </div>
    </div>

    <!-- loading -->
    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <!-- user table -->
    <div v-else class="panel overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-[var(--border-color)]">
          <tr>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('auth_username')">
              用户名 <span class="text-xs">{{ sortIcon('auth_username') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('nickname')">
              昵称 <span class="text-xs">{{ sortIcon('nickname') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">手机</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">权限组</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('banned')">
              状态 <span class="text-xs">{{ sortIcon('banned') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('max_sessions')">
              会话 <span class="text-xs">{{ sortIcon('max_sessions') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('available_runs')">
              次数 <span class="text-xs">{{ sortIcon('available_runs') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('2fa_enabled')">
              2FA <span class="text-xs">{{ sortIcon('2fa_enabled') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('created_at')">
              创建时间 <span class="text-xs">{{ sortIcon('created_at') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="paginatedUsers.length === 0">
            <td colspan="10" class="px-3 py-6 text-center text-[var(--ink-secondary)]">暂无数据</td>
          </tr>
          <tr
            v-for="user in paginatedUsers"
            :key="user.auth_username"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <!-- username -->
            <td class="px-3 py-2 font-mono whitespace-nowrap">{{ user.auth_username }}</td>
            <!-- nickname -->
            <td class="px-3 py-2">{{ user.nickname || '--' }}</td>
            <!-- phone -->
            <td class="px-3 py-2 font-mono whitespace-nowrap">{{ user.phone || '--' }}</td>
            <!-- group select -->
            <td class="px-3 py-2">
              <select
                class="select-field text-xs"
                :value="user.group"
                @change="updateGroup(user, $event.target.value)"
              >
                <option v-for="opt in groupOptions" :key="opt.key" :value="opt.key">{{ opt.name }}</option>
                <option v-if="!groupOptions.some(o => o.key === user.group)" :value="user.group">{{ groupName(user.group) }}</option>
              </select>
            </td>
            <!-- status badge -->
            <td class="px-3 py-2">
              <span v-if="user.banned" class="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-700">已封禁</span>
              <span v-else class="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">正常</span>
            </td>
            <!-- sessions -->
            <td class="px-3 py-2 whitespace-nowrap">{{ sessionsText(user) }}</td>
            <!-- runs -->
            <td class="px-3 py-2 whitespace-nowrap">{{ runsText(user) }}</td>
            <!-- 2FA -->
            <td class="px-3 py-2">
              <span v-if="user['2fa_enabled']" class="px-2 py-0.5 rounded-full text-xs bg-[var(--accent)]/15 text-[var(--accent)]">已启用</span>
              <span v-else class="text-[var(--ink-muted)]">未启用</span>
            </td>
            <!-- created date -->
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(user.created_at) }}</td>
            <!-- actions -->
            <td class="px-3 py-2">
              <div class="flex flex-wrap items-center gap-1">
                <button
                  class="btn btn-ghost text-xs px-2 py-1"
                  @click="toggleBan(user)"
                >{{ user.banned ? '解封' : '封禁' }}</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="resetPassword(user)">重置密码</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="modifyNickname(user)">昵称</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="modifyPhone(user)">手机</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="setMaxSessions(user)">会话数</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="editAvailableRuns(user)">次数</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="forceLogout(user)">强制登出</button>
                <button v-if="user['2fa_enabled']" class="btn btn-ghost text-xs px-2 py-1" @click="forceDisable2FA(user)">关闭2FA</button>
                <button class="btn btn-ghost text-xs px-2 py-1" @click="clearAvatar(user)">清除头像</button>
                <button class="btn btn-danger text-xs px-2 py-1" @click="deleteUser(user)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- pagination -->
    <div v-if="!loading && sortedUsers.length > 0" class="flex flex-wrap items-center justify-between gap-3 text-sm text-[var(--ink-secondary)]">
      <div class="flex items-center gap-2">
        <span>每页</span>
        <select v-model.number="pageSize" class="select-field text-xs" @change="currentPage = 1">
          <option :value="10">10</option>
          <option :value="25">25</option>
          <option :value="50">50</option>
        </select>
        <span>条</span>
      </div>
      <div class="flex items-center gap-2">
        <span>第 {{ currentPage }} / {{ totalPages }} 页，共 {{ sortedUsers.length }} 条</span>
        <button class="btn btn-secondary text-xs px-2 py-1" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
        <button class="btn btn-secondary text-xs px-2 py-1" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
      </div>
    </div>

  </div>
</template>
