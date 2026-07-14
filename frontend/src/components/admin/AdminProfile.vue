<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const loading = ref(false)
const error = ref('')
const success = ref('')

const profile = ref({
  avatar: '',
  display_name: '',
  theme: 'light',
  theme_style: '',
})

const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const savingName = ref(false)
const savingTheme = ref(false)
const changingPassword = ref(false)
const uploadingAvatar = ref(false)

const themeOptions = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
]

const themeStyles = [
  { value: 'default', label: '默认', color: '#3b82f6' },
  { value: 'ocean', label: '海洋', color: '#0ea5e9' },
  { value: 'forest', label: '森林', color: '#22c55e' },
  { value: 'sunset', label: '日落', color: '#f97316' },
  { value: 'lavender', label: '薰衣草', color: '#a855f7' },
  { value: 'rose', label: '玫瑰', color: '#f43f5e' },
]

function clearMessages() { error.value = ''; success.value = '' }

async function loadProfile() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/auth/user/details', 'GET')
    const user = res.user || res
    profile.value = {
      avatar: user.avatar_url || user.avatar || '',
      display_name: user.nickname || user.display_name || '',
      theme: user.theme || 'light',
      theme_style: user.theme_style || 'default',
    }
  } catch (e) {
    error.value = e.message || '加载个人信息失败'
  } finally {
    loading.value = false
  }
}

async function saveDisplayName() {
  savingName.value = true
  clearMessages()
  try {
    const auth = useAuthStore()
    const username = auth.username
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = { 'Content-Type': 'application/json' }
    if (sessionId) headers['X-Session-ID'] = sessionId
    const res = await fetch(`/api/admin/users/${encodeURIComponent(username)}/basic_info`, {
      method: 'PUT',
      headers,
      credentials: 'include',
      body: JSON.stringify({ nickname: profile.value.display_name }),
    })
    const data = await res.json()
    if (!res.ok || data.success === false) {
      throw new Error(data.message || '保存失败')
    }
    success.value = '显示名称已保存'
  } catch (e) {
    error.value = e.message || '保存显示名称失败'
  } finally {
    savingName.value = false
  }
}

async function saveTheme() {
  savingTheme.value = true
  clearMessages()
  try {
    await callRawAPI('/auth/user/update_theme', 'POST', {
      theme: profile.value.theme,
      theme_style: profile.value.theme_style,
    })
    success.value = '主题已保存'
  } catch (e) {
    error.value = e.message || '保存主题失败'
  } finally {
    savingTheme.value = false
  }
}

async function changePassword() {
  clearMessages()
  if (!passwordForm.value.old_password || !passwordForm.value.new_password) {
    error.value = '请填写旧密码和新密码'
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    error.value = '两次输入的新密码不一致'
    return
  }
  changingPassword.value = true
  try {
    const auth = useAuthStore()
    await callRawAPI('/auth/admin/reset_password', 'POST', {
      username: auth.username,
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password,
    })
    success.value = '密码已修改'
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
  } catch (e) {
    error.value = e.message || '修改密码失败'
  } finally {
    changingPassword.value = false
  }
}

function triggerAvatarUpload() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    uploadingAvatar.value = true
    clearMessages()
    try {
      const formData = new FormData()
      formData.append('avatar', file)
      const auth = useAuthStore()
      const sessionId = auth.getAuthenticatedSessionHeaderValue()
      const hdrs = {}
      if (sessionId) hdrs['X-Session-ID'] = sessionId
      const res = await fetch('/auth/user/upload_avatar', {
        method: 'POST',
        headers: hdrs,
        credentials: 'include',
        body: formData,
      })
      if (!res.ok) throw new Error('上传失败')
      const data = await res.json()
      profile.value.avatar = data.avatar_url || data.avatar || ''
      success.value = '头像已上传'
    } catch (e) {
      error.value = e.message || '上传头像失败'
    } finally {
      uploadingAvatar.value = false
    }
  }
  input.click()
}

onMounted(loadProfile)
</script>

<template>
  <div class="space-y-6">
    <h2 class="text-lg font-semibold text-[var(--ink)]">个人信息</h2>

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&#x2715;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <template v-else>
      <!-- Avatar section -->
      <div class="panel p-4">
        <h3 class="font-medium text-[var(--ink)] mb-3">头像</h3>
        <div class="flex items-center gap-4">
          <div class="w-20 h-20 rounded-full bg-[var(--glass)] border-2 border-[var(--border-color)] flex items-center justify-center overflow-hidden">
            <img v-if="profile.avatar" :src="profile.avatar" alt="头像" class="w-full h-full object-cover" />
            <span v-else class="text-3xl text-[var(--ink-muted)]">&#x1F464;</span>
          </div>
          <button class="btn btn-secondary text-sm" :disabled="uploadingAvatar" @click="triggerAvatarUpload">
            {{ uploadingAvatar ? '上传中...' : '上传头像' }}
          </button>
        </div>
      </div>

      <!-- Display name -->
      <div class="panel p-4">
        <h3 class="font-medium text-[var(--ink)] mb-3">显示名称</h3>
        <div class="flex items-center gap-3">
          <input v-model="profile.display_name" class="input-field flex-1" type="text" placeholder="显示名称" />
          <button class="btn btn-primary text-sm" :disabled="savingName" @click="saveDisplayName">
            {{ savingName ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>

      <!-- Theme preference -->
      <div class="panel p-4">
        <h3 class="font-medium text-[var(--ink)] mb-3">主题设置</h3>
        <div class="space-y-4">
          <div class="flex items-center gap-3">
            <label class="block text-xs text-[var(--ink-secondary)]">颜色模式</label>
            <select v-model="profile.theme" class="select-field">
              <option v-for="opt in themeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--ink-secondary)] mb-2">主题风格</label>
            <div class="grid grid-cols-3 sm:grid-cols-6 gap-2">
              <button
                v-for="style in themeStyles"
                :key="style.value"
                class="flex flex-col items-center gap-1 p-2 rounded-lg border-2 transition-colors"
                :class="profile.theme_style === style.value ? 'border-[var(--accent)] bg-[var(--accent)]/5' : 'border-[var(--border-color)] hover:border-[var(--ink-muted)]'"
                @click="profile.theme_style = style.value"
              >
                <span class="w-6 h-6 rounded-full" :style="{ backgroundColor: style.color }" />
                <span class="text-xs text-[var(--ink-secondary)]">{{ style.label }}</span>
              </button>
            </div>
          </div>
          <button class="btn btn-primary text-sm" :disabled="savingTheme" @click="saveTheme">
            {{ savingTheme ? '保存中...' : '保存主题' }}
          </button>
        </div>
      </div>

      <!-- Password change -->
      <div class="panel p-4">
        <h3 class="font-medium text-[var(--ink)] mb-3">修改密码</h3>
        <div class="space-y-3 max-w-md">
          <div>
            <label class="block text-xs text-[var(--ink-secondary)] mb-1">旧密码</label>
            <input v-model="passwordForm.old_password" class="input-field w-full" type="password" placeholder="当前密码" />
          </div>
          <div>
            <label class="block text-xs text-[var(--ink-secondary)] mb-1">新密码</label>
            <input v-model="passwordForm.new_password" class="input-field w-full" type="password" placeholder="新密码" />
          </div>
          <div>
            <label class="block text-xs text-[var(--ink-secondary)] mb-1">确认新密码</label>
            <input v-model="passwordForm.confirm_password" class="input-field w-full" type="password" placeholder="再次输入新密码" />
          </div>
          <button class="btn btn-primary text-sm" :disabled="changingPassword" @click="changePassword">
            {{ changingPassword ? '提交中...' : '修改密码' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
