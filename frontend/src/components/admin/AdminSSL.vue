<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

const sslConfig = ref(null)
const certInfo = ref(null)
const loading = ref(false)
const error = ref('')
const success = ref('')
const uploading = ref(false)
const toggling = ref(false)
const sslEnabled = ref(false)

const certFile = ref(null)
const keyFile = ref(null)

const certValid = computed(() => certInfo.value && !certInfo.value.error)

function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN')
}

async function loadSSLStatus() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/ssl/info', 'GET')
    sslConfig.value = res.config || null
    certInfo.value = res.cert_info || null
    sslEnabled.value = !!(res.config && res.config.ssl_enabled)
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
    formData.append('cert_file', certFile.value)
    formData.append('key_file', keyFile.value)
    const auth = useAuthStore()
    const sessionId = auth.getAuthenticatedSessionHeaderValue()
    const headers = {}
    if (sessionId) headers['X-Session-ID'] = sessionId
    const res = await fetch('/api/admin/ssl/upload', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: formData,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok || data.success === false) {
      throw new Error(data.message || '上传失败')
    }
    success.value = data.message || 'SSL证书已上传'
    certFile.value = null
    keyFile.value = null
    await loadSSLStatus()
  } catch (e) {
    error.value = e.message || '上传证书失败'
  } finally {
    uploading.value = false
  }
}

async function toggleSSL() {
  toggling.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/ssl/toggle', 'POST', { enabled: !sslEnabled.value })
    if (res && res.success === false) {
      error.value = res.message || '切换SSL失败'
      return
    }
    sslEnabled.value = !!res.ssl_enabled
    success.value = res.message || (sslEnabled.value ? 'SSL已启用' : 'SSL已禁用')
  } catch (e) {
    error.value = e.message || '切换SSL失败'
  } finally {
    toggling.value = false
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
        <div v-if="certValid" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="sm:col-span-2">
            <div class="text-xs text-[var(--ink-secondary)] mb-1">主题</div>
            <div class="text-sm font-medium text-[var(--ink)] break-all">{{ certInfo.subject }}</div>
          </div>
          <div>
            <div class="text-xs text-[var(--ink-secondary)] mb-1">颁发者</div>
            <div class="text-sm font-medium text-[var(--ink)] break-all">{{ certInfo.issuer || '--' }}</div>
          </div>
          <div>
            <div class="text-xs text-[var(--ink-secondary)] mb-1">到期日期</div>
            <div class="text-sm font-medium" :class="certInfo.is_expired ? 'text-red-500' : 'text-[var(--ink)]'">
              {{ formatDate(certInfo.not_after) }}
              <span v-if="certInfo.is_expired" class="ml-1">（已过期）</span>
            </div>
          </div>
          <div v-if="certInfo.san && certInfo.san.length" class="sm:col-span-2">
            <div class="text-xs text-[var(--ink-secondary)] mb-1">备用域名 (SAN)</div>
            <div class="text-sm text-[var(--ink)] break-all">{{ certInfo.san.join(', ') }}</div>
          </div>
        </div>
        <div v-else class="text-sm text-[var(--ink-secondary)]">{{ certInfo?.error || '暂无证书信息' }}</div>
      </div>

      <!-- SSL toggle -->
      <div class="panel p-4">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="font-medium text-[var(--ink)]">SSL / HTTPS</h3>
            <p class="text-xs text-[var(--ink-secondary)] mt-1">启用或禁用 HTTPS（需重启服务器才能生效）</p>
          </div>
          <button
            class="btn text-sm"
            :class="sslEnabled ? 'btn-primary' : 'btn-secondary'"
            :disabled="toggling"
            @click="toggleSSL"
          >
            {{ toggling ? '切换中...' : (sslEnabled ? '已启用' : '已禁用') }}
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
