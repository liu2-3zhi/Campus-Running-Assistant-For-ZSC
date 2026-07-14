<script setup>
import { ref, reactive, onMounted } from 'vue'
import { callAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'

const props = defineProps({
  initialData: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['login-success', 'import-users'])

const auth = useAuthStore()
const app = useAppStore()

// --- State ---
const selectedUser = ref('')
const loginForm = reactive({
  username: '',
  password: '',
})
const userAgent = ref('')
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const userList = ref([])

// --- User list ---
function populateUsers(data) {
  if (data?.users && Array.isArray(data.users) && data.users.length > 0) {
    userList.value = data.users
    if (!selectedUser.value) {
      const last = data.last_user || data.lastUser
      selectedUser.value = last || data.users[0].username || data.users[0].name || ''
      onUserSelect()
    }
  }
}

// --- Load saved user combo from backend (对齐原始 loadInitialData 填充 user-combo) ---
async function loadUserCombo() {
  try {
    const data = await callAPI('get_initial_data')
    if (data) populateUsers(data)
  } catch (_) {}
}

function onUserSelect() {
  const user = userList.value.find(
    (u) => (u.username || u.name) === selectedUser.value
  )
  if (user) {
    loginForm.username = user.username || user.name || ''
    loginForm.password = ''
    autoFillPassword()
  }
}

// --- Auto-fill password & UA via backend (on_user_selected) ---
async function autoFillPassword() {
  if (!loginForm.username) return
  try {
    const data = await callAPI('on_user_selected', { username: loginForm.username })
    if (data?.password) {
      loginForm.password = data.password
    }
    const ua = data?.ua || data?.user_agent
    if (ua) userAgent.value = ua
  } catch (_) {}
}

// --- Random UA ---
const uaPresets = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
  'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/125.0.0.0 Mobile Safari/537.36',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
]

function randomUA() {
  const idx = Math.floor(Math.random() * uaPresets.length)
  userAgent.value = uaPresets[idx]
}

// --- Login ---
async function handleLogin() {
  if (!loginForm.username || !loginForm.password) {
    errorMsg.value = '请输入用户名和密码'
    return
  }

  errorMsg.value = ''
  successMsg.value = ''
  loading.value = true
  try {
    const data = await callAPI('login', {
      username: loginForm.username,
      password: loginForm.password,
    })

    if (data.success === false) {
      errorMsg.value = data.message || '登录失败'
      return
    }

    auth.setLoginResult(data)
    successMsg.value = '登录成功'
    emit('login-success', data)
  } catch (e) {
    errorMsg.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

// --- Import ---
function handleImport() {
  emit('import-users')
}

// --- Lifecycle ---
onMounted(() => {
  populateUsers(props.initialData)
  loadUserCombo()
})
</script>

<template>
  <div class="space-y-4">
    <!-- User combo select -->
    <div v-if="userList.length > 0" class="relative">
      <select
        v-model="selectedUser"
        class="w-full appearance-none rounded-xl border-2 border-slate-200 bg-white px-4 py-3 pr-10 text-sm font-medium text-slate-700 outline-none transition-colors focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        @change="onUserSelect"
      >
        <option value="">请选择用户</option>
        <option v-for="user in userList" :key="user.username || user.name" :value="user.username || user.name">
          {{ user.display_name || user.nickname || user.username || user.name }}
        </option>
      </select>
      <div class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
        <svg class="h-5 w-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>

    <!-- Username -->
    <div>
      <input
        v-model="loginForm.username"
        type="text"
        class="w-full rounded-xl border-2 border-slate-200 px-4 py-3 text-sm outline-none transition-colors focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        placeholder="请输入学号或工号"
        autocomplete="username"
        @blur="autoFillPassword"
      />
    </div>

    <!-- Password -->
    <div>
      <input
        v-model="loginForm.password"
        type="password"
        class="w-full rounded-xl border-2 border-slate-200 px-4 py-3 text-sm outline-none transition-colors focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
        placeholder="请输入密码，一般为身份证后六位"
        autocomplete="current-password"
        @keyup.enter="handleLogin"
      />
    </div>

    <!-- Login button -->
    <button
      class="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-sky-600 text-white font-semibold shadow-lg shadow-sky-300/50 hover:bg-sky-700 hover:shadow-sky-400/50 transition-all duration-300 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
      :disabled="loading"
      @click="handleLogin"
    >
      <span>{{ loading ? '登录中...' : '立即登录' }}</span>
      <svg v-if="!loading" class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
      </svg>
    </button>

    <!-- Divider -->
    <div class="relative flex items-center py-1">
      <div class="flex-grow border-t border-slate-200"></div>
      <span class="mx-4 shrink-0 text-xs text-slate-400">或者</span>
      <div class="flex-grow border-t border-slate-200"></div>
    </div>

    <!-- Import button (green) -->
    <button
      class="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-green-500 text-white font-semibold shadow-lg shadow-green-300/40 hover:from-emerald-600 hover:to-green-600 transition-all duration-300 active:scale-[0.98]"
      @click="handleImport"
    >
      <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
      </svg>
      导入离线文件
    </button>

    <!-- User-Agent section -->
    <div class="rounded-xl border border-slate-200 bg-slate-50/60 p-3 space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5 text-xs font-medium text-slate-500">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          User-Agent 标识
        </div>
        <button
          class="shrink-0 flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
          @click="randomUA"
          title="随机生成新的User-Agent，用于模拟不同设备和浏览器"
        >
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.3-3M20 15a8 8 0 01-14.3 3" />
          </svg>
          随机
        </button>
      </div>
      <p class="break-all text-xs text-slate-400" :title="userAgent">
        {{ userAgent || '(未加载)' }}
      </p>
    </div>

    <!-- Messages -->
    <div v-if="errorMsg" class="rounded-lg bg-red-50 p-3 text-sm text-red-600">
      {{ errorMsg }}
    </div>
    <div v-if="successMsg" class="rounded-lg bg-green-50 p-3 text-sm text-green-600">
      {{ successMsg }}
    </div>
  </div>
</template>
