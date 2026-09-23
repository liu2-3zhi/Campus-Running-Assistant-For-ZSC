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
const changingUA = ref(false)

// --- User list ---
function populateUsers(data) {
  if (data?.ua) userAgent.value = data.ua
  if (data?.users && Array.isArray(data.users) && data.users.length > 0) {
    userList.value = data.users.map(user => typeof user === 'string' ? { username: user } : user)
    if (!selectedUser.value) {
      const last = data.last_user || data.lastUser
      selectedUser.value = last || userList.value[0].username || userList.value[0].name || ''
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
  const username = loginForm.username.trim()
  if (!username) return
  try {
    const data = await callAPI('on_user_selected', { username })
    if (username !== loginForm.username.trim()) return
    loginForm.password = data?.password || ''
    const ua = data?.ua || data?.user_agent
    userAgent.value = ua || '(新用户将在登录时自动生成)'
    if (data?.params) app.pythonParams = data.params
  } catch (_) {}
}

// --- Random UA ---
async function randomUA() {
  changingUA.value = true
  errorMsg.value = ''
  try {
    userAgent.value = await callAPI('generate_new_ua')
  } catch (e) {
    errorMsg.value = e.message || '生成 User-Agent 失败'
  } finally {
    changingUA.value = false
  }
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
<div class="space-y-5 w-full">
              <div class="space-y-2">
                <label
                  class="block text-sm font-bold leading-6 text-slate-700 flex items-center gap-2"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-4 h-4 text-slate-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                    ></path>
                  </svg>
                  {{ app.isMobile ? "选择用户" : "选择账号" }}
                </label>
                <select
                  id="user-combo" v-model="selectedUser" @change="onUserSelect"
                  class="select-field"
                  title="选择已保存的账号或创建新账号"
                  aria-label="选择账号"
                ><option value="">{{ app.isMobile ? "请选择用户" : "" }}</option><option v-for="user in userList" :key="user.username || user.name" :value="user.username || user.name">{{ user.display_name || user.nickname || user.username || user.name }}</option></select>
              </div>

              <div class="space-y-2">
                <label
                  class="block text-sm font-bold leading-6 text-slate-700 flex items-center gap-2"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-4 h-4 text-slate-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                    ></path>
                  </svg>
                  用户名
                </label>
                <input
                  type="text"
                  id="username-entry" v-model="loginForm.username" @blur="autoFillPassword"
                  class="input-field"
                  placeholder="请输入学号或工号"
                  autocomplete="username"
                />
              </div>

              <div class="space-y-2">
                <label
                  class="block text-sm font-bold leading-6 text-slate-700 flex items-center gap-2"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-4 h-4 text-slate-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                    ></path>
                  </svg>
                  密码
                </label>
                <input
                  type="password"
                  id="password-entry" v-model="loginForm.password" @keyup.enter="handleLogin"
                  class="input-field"
                  placeholder="请输入密码，一般为身份证后六位"
                  autocomplete="current-password"
                />
              </div>
            </div>

            <button
              id="login-button" :disabled="loading" @click="handleLogin"
              class="btn btn-primary w-full py-3.5 text-lg font-bold shadow-xl shadow-sky-300/40 hover:shadow-2xl hover:shadow-sky-400/50 transition-all duration-300"
              title="登录"
              aria-label="登录"
            >
              <span>{{ loading ? '登录中...' : '登录' }}</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="w-5 h-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L12.586 11H5a1 1 0 110-2h7.586l-2.293-2.293a1 1 0 010-1.414z"
                  clip-rule="evenodd"
                ></path>
              </svg>
            </button>

            <div class="relative flex py-3 items-center">
              <div class="flex-grow border-t border-slate-300"></div>
              <span class="flex-shrink mx-5 text-slate-400 text-sm font-medium"
                >或者</span
              >
              <div class="flex-grow border-t border-slate-300"></div>
            </div>

            <button
              id="import-button" @click="handleImport"
              class="btn btn-success w-full py-3 font-bold shadow-lg shadow-green-300/30 hover:shadow-xl hover:shadow-green-400/40 transition-all duration-300"
              title="导入"
              aria-label="导入"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                ></path>
              </svg>
              <span>导入离线文件</span>
            </button>

            <div class="pt-4 space-y-3 border-t border-slate-200">
              <div class="flex justify-between items-center">
                <span
                  class="text-sm font-semibold text-slate-600 flex items-center gap-2"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-4 h-4 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    ></path>
                  </svg>
                  User-Agent 标识
                </span>

                <button
                  id="random-ua-btn" :disabled="changingUA" @click="randomUA"
                  title="随机生成新的User-Agent，用于模拟不同设备和浏览器"
                  class="btn btn-ghost !py-1.5 !px-3 text-xs hover:bg-sky-100 transition-colors"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    ></path>
                  </svg>
                  <span>随机</span>
                </button>
              </div>

              <p
                id="ua-label"
                class="text-xs text-slate-600 break-all bg-gradient-to-br from-white to-slate-50 border border-slate-300 p-3 rounded-xl leading-relaxed shadow-inner"
              >
                {{ userAgent || '(未加载)' }}
              </p>
            </div>
<div v-if="errorMsg" class="rounded-lg bg-red-50 p-3 text-sm text-red-600">{{ errorMsg }}</div>
</template>
<style scoped>
@media(max-width: 767px) {
label svg, #login-button svg { display: none; }
label { margin-bottom: 8px; font-size: 14px; }
.input-field, .select-field { padding: 12px 16px; border: 2px solid #e2e8f0; border-radius: 12px; box-shadow: none; font-size: 16px; min-height: 52px; }
#login-button { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); border-radius: 12px; min-height: 50px; font-size: 17px; }
}
</style>
