<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const cdnConfig = ref(null)
const loading = ref(false)
const error = ref('')
const success = ref('')
const toggling = ref(false)
const refreshing = ref(false)

function clearMessages() { error.value = ''; success.value = '' }

async function loadCDNConfig() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/cdn/config', 'GET')
    cdnConfig.value = res
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
    const newState = !(cdnConfig.value?.enabled)
    await callRawAPI('/api/admin/cdn/config', 'POST', { enabled: newState })
    if (cdnConfig.value) cdnConfig.value.enabled = newState
    success.value = newState ? 'CDN已启用' : 'CDN已禁用'
  } catch (e) {
    error.value = e.message || '切换CDN失败'
  } finally {
    toggling.value = false
  }
}

async function forceRefresh() {
  refreshing.value = true
  clearMessages()
  try {
    await callRawAPI('/api/cdn/refresh', 'POST')
    success.value = 'CDN缓存已刷新'
    await loadCDNConfig()
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
              :class="cdnConfig.enabled ? 'bg-green-500' : 'bg-gray-400'"
            />
            <div>
              <h3 class="font-medium text-[var(--ink)]">CDN 状态</h3>
              <p class="text-xs text-[var(--ink-secondary)]">{{ cdnConfig.enabled ? '已启用' : '已禁用' }}</p>
            </div>
          </div>
          <button
            class="btn text-sm"
            :class="cdnConfig.enabled ? 'btn-secondary' : 'btn-primary'"
            :disabled="toggling"
            @click="toggleCDN"
          >
            {{ toggling ? '切换中...' : (cdnConfig.enabled ? '禁用CDN' : '启用CDN') }}
          </button>
        </div>
      </div>

      <!-- Cache info -->
      <div class="panel p-4">
        <h3 class="font-medium text-[var(--ink)] mb-3">缓存信息</h3>
        <div class="flex items-center justify-between">
          <div>
            <div class="text-xs text-[var(--ink-secondary)] mb-1">缓存文件数</div>
            <div class="text-lg font-semibold text-[var(--ink)]">{{ cdnConfig.cached_files ?? cdnConfig.cache_count ?? '--' }}</div>
          </div>
          <button class="btn btn-secondary text-sm" :disabled="refreshing" @click="forceRefresh">
            {{ refreshing ? '刷新中...' : '强制刷新' }}
          </button>
        </div>
      </div>
    </template>

    <div v-else class="py-8 text-center text-[var(--ink-secondary)]">无法加载CDN配置</div>
  </div>
</template>
