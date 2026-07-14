<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

/* ── reactive state ── */
const users = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')

/* ── search / filter ── */
const searchQuery = ref('')
const roleFilter = ref('')
const statusFilter = ref('')

/* ── sort ── */
const sortKey = ref('created_at')
const sortAsc = ref(false)

/* ── pagination ── */
const currentPage = ref(1)
const pageSize = ref(10)

/* ── add-user form ── */
const showAddForm = ref(false)
const addForm = ref({ username: '', password: '', display_name: '', role: 'user' })
const addLoading = ref(false)

/* ── helpers ── */
function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

/* ── filtered + sorted + paginated users ── */
const filteredUsers = computed(() => {
  let list = users.value
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(u =>
      (u.username || '').toLowerCase().includes(q) ||
      (u.display_name || '').toLowerCase().includes(q)
    )
  }
  if (roleFilter.value) {
    list = list.filter(u => u.role === roleFilter.value)
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
    const va = a[key] ?? ''
    const vb = b[key] ?? ''
    if (typeof va === 'string') return va.localeCompare(vb) * dir
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

/* ── API: load users ── */
async function loadUsers() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/auth/admin/list_users', 'GET')
    users.value = res.users || []
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
  addLoading.value = true
  clearMessages()
  try {
    await callRawAPI('/auth/admin/create_user', 'POST', {
      username: addForm.value.username,
      password: addForm.value.password,
      nickname: addForm.value.display_name,
      group: addForm.value.role
    })
    success.value = '用户已添加'
    addForm.value = { username: '', password: '', display_name: '', role: 'user' }
    showAddForm.value = false
    await loadUsers()
  } catch (e) {
    error.value = e.message || '添加用户失败'
  } finally {
    addLoading.value = false
  }
}

/* ── API: ban / unban ── */
async function toggleBan(user) {
  clearMessages()
  const action = user.banned ? 'unban' : 'ban'
  try {
    await callRawAPI('/auth/admin/' + action + '_user', 'POST', { username: user.username })
    success.value = user.banned ? '已解封用户' : '已封禁用户'
    await loadUsers()
  } catch (e) {
    error.value = e.message || '操作失败'
  }
}

/* ── API: delete user ── */
async function deleteUser(user) {
  if (!confirm('确定要删除用户 "' + user.username + '" 吗？此操作不可恢复。')) return
  clearMessages()
  try {
    await callRawAPI('/auth/admin/delete_user', 'POST', { username: user.username })
    success.value = '用户已删除'
    await loadUsers()
  } catch (e) {
    error.value = e.message || '删除用户失败'
  }
}

/* ── API: reset password ── */
async function resetPassword(user) {
  if (!confirm('确定要重置用户 "' + user.username + '" 的密码吗？')) return
  clearMessages()
  try {
    const res = await callRawAPI('/auth/admin/force_reset_password', 'POST', { target_username: user.username })
    success.value = '密码已重置' + (res.new_password ? '，新密码: ' + res.new_password : '')
  } catch (e) {
    error.value = e.message || '重置密码失败'
  }
}

/* ── detail / edit / permissions (emits) ── */
const emit = defineEmits(['view-user', 'edit-user', 'manage-permissions'])

function viewUser(user) { emit('view-user', user) }
function editUser(user) { emit('edit-user', user) }
function managePermissions(user) { emit('manage-permissions', user) }

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
          placeholder="搜索用户名/显示名"
          @input="onFilterChange"
        />
        <select v-model="roleFilter" class="select-field" @change="onFilterChange">
          <option value="">全部角色</option>
          <option value="admin">管理员</option>
          <option value="user">普通用户</option>
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
          <input v-model="addForm.password" class="input-field w-full" type="password" placeholder="密码" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">显示名</label>
          <input v-model="addForm.display_name" class="input-field w-full" type="text" placeholder="显示名称" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">角色</label>
          <select v-model="addForm.role" class="select-field w-full">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
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
                @click="toggleSort('username')">
              用户名 <span class="text-xs">{{ sortIcon('username') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('display_name')">
              显示名 <span class="text-xs">{{ sortIcon('display_name') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('role')">
              角色 <span class="text-xs">{{ sortIcon('role') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('banned')">
              状态 <span class="text-xs">{{ sortIcon('banned') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium cursor-pointer select-none whitespace-nowrap"
                @click="toggleSort('created_at')">
              创建日期 <span class="text-xs">{{ sortIcon('created_at') }}</span>
            </th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="paginatedUsers.length === 0">
            <td colspan="6" class="px-3 py-6 text-center text-[var(--ink-secondary)]">暂无数据</td>
          </tr>
          <tr
            v-for="user in paginatedUsers"
            :key="user.id"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <!-- username -->
            <td class="px-3 py-2 font-mono">{{ user.username }}</td>
            <!-- display name -->
            <td class="px-3 py-2">{{ user.display_name || '--' }}</td>
            <!-- role badge -->
            <td class="px-3 py-2">
              <span
                v-if="user.role === 'admin'"
                class="px-2 py-0.5 rounded-full text-xs bg-[var(--accent)]/15 text-[var(--accent)]"
              >管理员</span>
              <span v-else class="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">普通用户</span>
            </td>
            <!-- status badge -->
            <td class="px-3 py-2">
              <span v-if="user.banned" class="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-700">已封禁</span>
              <span v-else class="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">正常</span>
            </td>
            <!-- created date -->
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(user.created_at) }}</td>
            <!-- actions -->
            <td class="px-3 py-2">
              <div class="flex flex-wrap items-center gap-1">
                <button class="btn btn-ghost text-xs px-2 py-1" title="查看" @click="viewUser(user)">查看</button>
                <button class="btn btn-ghost text-xs px-2 py-1" title="编辑" @click="editUser(user)">编辑</button>
                <button
                  class="btn btn-ghost text-xs px-2 py-1"
                  :title="user.banned ? '解封' : '封禁'"
                  @click="toggleBan(user)"
                >{{ user.banned ? '解封' : '封禁' }}</button>
                <button class="btn btn-ghost text-xs px-2 py-1" title="权限" @click="managePermissions(user)">权限</button>
                <button class="btn btn-ghost text-xs px-2 py-1" title="重置密码" @click="resetPassword(user)">重置密码</button>
                <button class="btn btn-danger text-xs px-2 py-1" title="删除" @click="deleteUser(user)">删除</button>
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
