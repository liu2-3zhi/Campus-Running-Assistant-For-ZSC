<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const cdnConfig = ref(null)
const cacheTime = ref(3600)
const loading = ref(false)
const error = ref('')
const success = ref('')
const toggling = ref(false)
const saving = ref(false)
const refreshing = ref(false)

function clearMessages() { error.value = ''; success.value = '' }

async function loadCDNConfig() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/cdn/config', 'GET')
    cdnConfig.value = res.config || res
    cacheTime.value = cdnConfig.value?.cache_time ?? 3600
  } catch (e) {
    error.value = e.message || '加载CDN配置失败'
  } finally {
    loading.value = false
  }
}

async function toggleCDN() {
  toggling.value = true
  clearMessages()
  try {
    const newState = !(cdnConfig.value?.cdn_enabled)
    const res = await callRawAPI('/api/admin/cdn/config', 'POST', {
      cdn_enabled: newState,
      cache_time: Math.max(0, Math.floor(Number(cacheTime.value) || 0)),
    })
    if (res && res.success === false) {
      error.value = res.message || '切换CDN失败'
      return
    }
    if (cdnConfig.value) cdnConfig.value.cdn_enabled = newState
    success.value = newState ? 'CDN已启用' : 'CDN已禁用'
  } catch (e) {
    error.value = e.message || '切换CDN失败'
  } finally {
    toggling.value = false
  }
}

async function saveCacheTime() {
  saving.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/cdn/config', 'POST', {
      cdn_enabled: !!cdnConfig.value?.cdn_enabled,
      cache_time: Math.max(0, Math.floor(Number(cacheTime.value) || 0)),
    })
    if (res && res.success === false) {
      error.value = res.message || '保存失败'
      return
    }
    if (cdnConfig.value) cdnConfig.value.cache_time = Math.max(0, Math.floor(Number(cacheTime.value) || 0))
    success.value = 'CDN缓存配置已保存'
  } catch (e) {
    error.value = e.message || '保存CDN配置失败'
  } finally {
    saving.value = false
  }
}

async function forceRefresh() {
  refreshing.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/cdn/refresh', 'POST')
    if (res && res.success === false) {
      error.value = res.message || '刷新CDN缓存失败'
      return
    }
    success.value = res.message || 'CDN缓存已刷新'
  } catch (e) {
    error.value = e.message || '刷新CDN缓存失败'
  } finally {
    refreshing.value = false
  }
}

onMounted(loadCDNConfig)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-[var(--ink)]">CDN 管理</h2>

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&#x2715;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <template v-else-if="cdnConfig">
      <!-- CDN status -->
      <div class="panel p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span
              class="w-3 h-3 rounded-full"
              :class="cdnConfig.cdn_enabled ? 'bg-green-500' : 'bg-gray-400'"
            />
            <div>
              <h3 class="font-medium text-[var(--ink)]">CDN 状态</h3>
              <p class="text-xs text-[var(--ink-secondary)]">{{ cdnConfig.cdn_enabled ? '已启用' : '已禁用' }}</p>
            </div>
          </div>
          <button
            class="btn text-sm"
            :class="cdnConfig.cdn_enabled ? 'btn-secondary' : 'btn-primary'"
            :disabled="toggling"
            @click="toggleCDN"
          >
            {{ toggling ? '切换中...' : (cdnConfig.cdn_enabled ? '禁用CDN' : '启用CDN') }}
          </button>
        </div>
      </div>

      <!-- Cache config -->
      <div class="panel p-4 space-y-3">
        <h3 class="font-medium text-[var(--ink)]">缓存配置</h3>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">缓存时间（秒）</label>
          <input v-model.number="cacheTime" type="number" min="0" step="1" class="input-field w-full sm:w-64" placeholder="例如: 3600" />
          <p class="text-xs text-[var(--ink-muted)] mt-1">静态资源在 CDN 上的缓存有效期，0 表示不缓存。</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="btn btn-primary text-sm" :disabled="saving" @click="saveCacheTime">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
          <button class="btn btn-secondary text-sm" :disabled="refreshing" @click="forceRefresh">
            {{ refreshing ? '刷新中...' : '强制刷新缓存' }}
          </button>
        </div>
      </div>
    </template>

    <div v-else class="py-8 text-center text-[var(--ink-secondary)]">无法加载CDN配置</div>
  </div>
</template>
