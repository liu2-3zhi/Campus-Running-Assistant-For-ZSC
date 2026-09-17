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

    <div class="flex items-center justify-between gap-3">
      <h4 class="font-semibold">用户列表</h4>
      <div class="flex gap-2">
        <button class="btn btn-primary !px-2 !py-1" @click="showAddForm = !showAddForm">
          {{ showAddForm ? '取消新增' : '新增用户' }}
        </button>
        <button class="btn btn-ghost !px-2 !py-1" :disabled="loading" @click="loadUsers">
          刷新
        </button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
      <input
        v-model="searchQuery"
        class="input-field min-w-[14rem] flex-1 !rounded-none !border-0 !p-0 !shadow-none"
        type="text"
        placeholder="搜索昵称 / 用户名 / 手机号 / 学校账号"
        @input="onFilterChange"
      />
      <button class="btn btn-primary !px-3 !py-1 text-sm" type="button" @click="onFilterChange">
        搜索
      </button>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs text-slate-500">排序：</span>
      <select v-model="sortKey" class="rounded border border-slate-300 px-2 py-1 text-xs" @change="onFilterChange">
        <option value="created_at">创建时间</option>
        <option value="auth_username">用户名</option>
        <option value="nickname">昵称</option>
        <option value="last_login">最后登录时间</option>
        <option value="max_sessions">会话限制数量</option>
        <option value="available_runs">可用次数</option>
        <option value="2fa_enabled">2FA</option>
      </select>
      <button
        class="btn btn-ghost !px-2 !py-0.5 text-xs border border-slate-300"
        type="button"
        @click="sortAsc = !sortAsc"
      >
        {{ sortAsc ? '↑ 升序' : '↓ 降序' }}
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

    <div
      v-else
      id="admin-users-list_modal"
      class="-mr-2 max-h-[50vh] space-y-2 overflow-y-auto pr-2"
    >
      <p v-if="sortedUsers.length === 0" class="py-10 text-center text-slate-400">
        暂无用户
      </p>
      <div
        v-for="user in sortedUsers"
        :key="user.auth_username"
        class="mb-2 rounded-lg border border-slate-200 p-3"
      >
        <div class="flex flex-col justify-between items-start gap-3 md:flex-row">
          <div class="flex w-full flex-1 items-start gap-3 md:w-auto">
            <div class="flex h-16 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-slate-300 bg-slate-200">
              <img
                v-if="user.avatar_url && user.avatar_url !== 'default_avatar.png'"
                :src="user.avatar_url"
                :alt="user.auth_username"
                class="h-full w-full object-cover"
              />
              <span v-else class="text-2xl text-slate-400">👤</span>
            </div>
            <div class="min-w-0 flex-1">
              <p class="font-semibold text-slate-800">
                {{ user.auth_username }}
                <span v-if="user.banned" class="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-600">
                  已封禁
                </span>
              </p>
              <p class="text-xs text-slate-500">昵称: {{ user.nickname || '未设置' }}</p>
              <p class="text-xs text-slate-500">手机号: {{ user.phone || '未绑定' }}</p>
              <p class="text-xs text-slate-500">创建时间: {{ formatDate(user.created_at) }}</p>
              <p class="text-xs text-slate-500">最后登录: {{ user.last_login ? formatDate(user.last_login) : '从未登录' }}</p>
              <p class="text-xs text-slate-500">登录IP: {{ user.last_login_ip || '无记录' }} ({{ user.last_login_city || '未知' }})</p>
              <p class="text-xs text-slate-500">会话限制: {{ sessionsText(user) }}{{ user.max_sessions === -1 ? '' : '个' }}</p>
              <p class="text-xs text-slate-500">
                可用次数:
                <span class="font-semibold" :class="user.available_runs === -1 ? 'text-green-600' : user.available_runs === 0 ? 'text-red-600' : 'text-blue-600'">
                  {{ user.available_runs === -1 ? '无限制' : (user.available_runs ?? 0) + '次' }}
                </span>
              </p>
              <p class="text-xs" :class="user['2fa_enabled'] ? 'text-green-600' : 'text-slate-400'">
                2FA: {{ user['2fa_enabled'] ? '已启用' : '未启用' }}
              </p>
            </div>
          </div>
          <div class="flex w-full flex-col gap-1 md:w-auto md:items-end">
            <div class="flex w-full items-center justify-between md:justify-end">
              <span class="mr-2 text-xs text-slate-600">权限组:</span>
              <select
                class="rounded border border-slate-300 px-2 py-1 text-sm"
                :value="user.group"
                @change="updateGroup(user, $event.target.value)"
              >
                <option v-for="opt in groupOptions" :key="opt.key" :value="opt.key">{{ opt.name }}</option>
                <option v-if="!groupOptions.some(o => o.key === user.group)" :value="user.group">{{ groupName(user.group) }}</option>
              </select>
            </div>
            <div class="mt-2 grid w-full grid-cols-3 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2 md:grid-cols-6">
              <button class="btn h-7 min-h-0 border border-indigo-100 bg-indigo-50 px-2 text-xs text-indigo-600" @click="editAvailableRuns(user)">修改次数</button>
              <button class="btn h-7 min-h-0 border border-teal-100 bg-teal-50 px-2 text-xs text-teal-600" @click="modifyNickname(user)">修改昵称</button>
              <button class="btn h-7 min-h-0 border border-teal-100 bg-teal-50 px-2 text-xs text-teal-600" @click="modifyPhone(user)">修改手机</button>
              <button class="btn h-7 min-h-0 border border-purple-100 bg-purple-50 px-2 text-xs text-purple-600" @click="resetPassword(user)">重置密码</button>
              <button class="btn h-7 min-h-0 border border-amber-100 bg-amber-50 px-2 text-xs text-amber-600" @click="forceLogout(user)">强制登出</button>
              <button class="btn h-7 min-h-0 border border-rose-100 bg-rose-50 px-2 text-xs text-rose-600" @click="clearAvatar(user)">清除头像</button>
              <button
                class="btn h-7 min-h-0 border border-orange-100 bg-orange-50 px-2 text-xs text-orange-600"
                :disabled="!user['2fa_enabled']"
                @click="forceDisable2FA(user)"
              >
                {{ user['2fa_enabled'] ? '关闭2FA' : '2FA未启用' }}
              </button>
              <button
                class="btn h-7 min-h-0 border px-2 text-xs font-bold"
                :class="user.banned ? 'border-green-200 bg-green-100 text-green-700' : 'border-red-200 bg-red-100 text-red-700'"
                @click="toggleBan(user)"
              >
                {{ user.banned ? '解封用户' : '封禁用户' }}
              </button>
              <button class="btn h-7 min-h-0 border border-red-600 bg-red-600 px-2 text-xs text-white" @click="deleteUser(user)">彻底删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>
