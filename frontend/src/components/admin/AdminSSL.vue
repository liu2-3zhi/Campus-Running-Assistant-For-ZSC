<script setup>
import { ref, onMounted } from 'vue'
import { callAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const sslInfo = ref(null)
const loading = ref(false)
const error = ref('')
const success = ref('')
const uploading = ref(false)
const httpsEnabled = ref(false)

const certFile = ref(null)
const keyFile = ref(null)

function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleDateString('zh-CN')
}

async function loadSSLStatus() {
  loading.value = true
  clearMessages()
  try {
    const res = await callAPI('admin_ssl_status')
    sslInfo.value = res
    httpsEnabled.value = res.https_enabled || false
  } catch (e) {
    error.value = e.message || '加载SSL状态失败'
  } finally {
    loading.value = false
  }
}

function onCertFileChange(e) {
  certFile.value = e.target.files?.[0] || null
}

function onKeyFileChange(e) {
  keyFile.value = e.target.files?.[0] || null
}

async function uploadCert() {
  if (!certFile.value || !keyFile.value) {
    error.value = '请选择证书文件和密钥文件'
    return
  }
  uploading.value = true
  clearMessages()
  try {
    const formData = new FormData()
    formData.append('cert', certFile.value)
    formData.append('key', keyFile.value)
    const auth = useAuthStore()
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = {}
    if (sessionId) headers['X-Session-ID'] = sessionId
    const res = await fetch('/api/admin_ssl_upload', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: formData,
    })
    if (!res.ok) throw new Error('上传失败')
    await res.json()
    success.value = 'SSL证书已上传'
    certFile.value = null
    keyFile.value = null
    await loadSSLStatus()
  } catch (e) {
    error.value = e.message || '上传证书失败'
  } finally {
    uploading.value = false
  }
}

async function toggleHTTPS() {
  clearMessages()
  try {
    await callAPI('admin_ssl_toggle', { enabled: !httpsEnabled.value })
    httpsEnabled.value = !httpsEnabled.value
    success.value = httpsEnabled.value ? 'HTTPS已启用' : 'HTTPS已禁用'
  } catch (e) {
    error.value = e.message || '切换HTTPS失败'
  }
}

onMounted(loadSSLStatus)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-[var(--ink)]">SSL / HTTPS 管理</h2>

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
      <!-- Current cert info -->
      <div class="panel p-4">
        <h3 class="font-medium text-[var(--ink)] mb-3">当前证书信息</h3>
        <div v-if="sslInfo && sslInfo.domain" class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <div class="text-xs text-[var(--ink-secondary)] mb-1">域名</div>
            <div class="text-sm font-medium text-[var(--ink)]">{{ sslInfo.domain }}</div>
          </div>
          <div>
            <div class="text-xs text-[var(--ink-secondary)] mb-1">到期日期</div>
            <div class="text-sm font-medium text-[var(--ink)]">{{ formatDate(sslInfo.expiry || sslInfo.expires_at) }}</div>
          </div>
          <div>
            <div class="text-xs text-[var(--ink-secondary)] mb-1">颁发者</div>
            <div class="text-sm font-medium text-[var(--ink)]">{{ sslInfo.issuer || '--' }}</div>
          </div>
        </div>
        <div v-else class="text-sm text-[var(--ink-secondary)]">暂无证书信息</div>
      </div>

      <!-- HTTPS toggle -->
      <div class="panel p-4">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="font-medium text-[var(--ink)]">HTTPS</h3>
            <p class="text-xs text-[var(--ink-secondary)] mt-1">启用或禁用HTTPS强制跳转</p>
          </div>
          <button
            class="btn text-sm"
            :class="httpsEnabled ? 'btn-primary' : 'btn-secondary'"
            @click="toggleHTTPS"
          >
            {{ httpsEnabled ? '已启用' : '已禁用' }}
          </button>
        </div>
      </div>

      <!-- Upload cert -->
      <div class="panel p-4 space-y-3">
        <h3 class="font-medium text-[var(--ink)]">上传证书</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-[var(--ink-secondary)] mb-1">证书文件 (.pem / .crt)</label>
            <input type="file" accept=".pem,.crt,.cer" class="input-field w-full text-sm" @change="onCertFileChange" />
          </div>
          <div>
            <label class="block text-xs text-[var(--ink-secondary)] mb-1">密钥文件 (.key)</label>
            <input type="file" accept=".key,.pem" class="input-field w-full text-sm" @change="onKeyFileChange" />
          </div>
        </div>
        <button class="btn btn-primary text-sm" :disabled="uploading" @click="uploadCert">
          {{ uploading ? '上传中...' : '上传证书' }}
        </button>
      </div>
    </template>
  </div>
</template>
