<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const bans = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')

const newBan = ref({ target: '', type: 'ip', scope: 'all' })
const targetError = ref('')
const banning = ref(false)

const ipRegex = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/

function clearMessages() { error.value = ''; success.value = '' }

function isValidIP(ip) {
  const m = ipRegex.exec((ip || '').trim())
  if (!m) return false
  return m.slice(1).every(p => Number(p) >= 0 && Number(p) <= 255)
}

function ipToInt(ip) {
  return ip.trim().split('.').reduce((acc, p) => (acc << 8) + Number(p), 0) >>> 0
}

function scopeLabel(scope) {
  return scope === 'all' ? '全部' : '仅留言板'
}

function typeLabel(type) {
  return type === 'range' ? 'IP 范围' : 'IP 地址'
}

function formatDate(value) {
  if (!value && value !== 0) return '--'
  // 后端 created_at 为 time.time() 秒级时间戳
  const ms = typeof value === 'number' ? (value < 1e12 ? value * 1000 : value) : Date.parse(value)
  const d = new Date(ms)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN')
}

function validateTarget() {
  const target = newBan.value.target.trim()
  targetError.value = ''
  if (!target) {
    targetError.value = '请输入封禁目标'
    return false
  }
  if (newBan.value.type === 'ip') {
    if (!isValidIP(target)) {
      targetError.value = 'IP 地址格式不正确（例如 192.168.1.100）'
      return false
    }
  } else if (newBan.value.type === 'range') {
    const parts = target.split('-')
    if (parts.length !== 2 || !isValidIP(parts[0]) || !isValidIP(parts[1])) {
      targetError.value = 'IP 范围格式不正确（例如 192.168.1.1-192.168.1.255）'
      return false
    }
    if (ipToInt(parts[0]) > ipToInt(parts[1])) {
      targetError.value = '起始 IP 必须小于或等于结束 IP'
      return false
    }
  }
  return true
}

async function loadBans() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/ip_bans', 'GET')
    bans.value = res.bans || []
  } catch (e) {
    error.value = e.message || '加载IP封禁列表失败'
  } finally {
    loading.value = false
  }
}

async function banIP() {
  if (!validateTarget()) {
    error.value = targetError.value
    return
  }
  banning.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/ip_bans', 'POST', {
      target: newBan.value.target.trim(),
      type: newBan.value.type,
      scope: newBan.value.scope,
    })
    if (res && res.success === false) {
      error.value = res.message || '封禁失败'
      return
    }
    success.value = '已添加封禁规则: ' + newBan.value.target.trim()
    newBan.value = { target: '', type: 'ip', scope: 'all' }
    targetError.value = ''
    await loadBans()
  } catch (e) {
    error.value = e.message || '封禁失败'
  } finally {
    banning.value = false
  }
}

async function unbanIP(ban) {
  if (!confirm('确定要删除封禁规则 "' + ban.target + '" 吗？')) return
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/ip_bans/' + encodeURIComponent(ban.id), 'DELETE')
    if (res && res.success === false) {
      error.value = res.message || '删除失败'
      return
    }
    success.value = '已删除封禁规则: ' + ban.target
    await loadBans()
  } catch (e) {
    error.value = e.message || '删除封禁规则失败'
  }
}

onMounted(loadBans)
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-lg font-semibold text-[var(--ink)]">IP 封禁管理</h2>

    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&#x2715;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <!-- Add ban form -->
    <div class="panel p-4 space-y-3">
      <h3 class="font-medium text-[var(--ink)]">添加封禁</h3>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">封禁类型</label>
          <select v-model="newBan.type" class="select-field w-full" @change="validateTarget">
            <option value="ip">IP 地址</option>
            <option value="range">IP 范围</option>
          </select>
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">封禁目标 *</label>
          <input
            v-model="newBan.target"
            class="input-field w-full"
            :class="targetError ? 'border-red-500' : ''"
            type="text"
            :placeholder="newBan.type === 'range' ? '例如: 192.168.1.1-192.168.1.255' : '例如: 192.168.1.100'"
            @input="targetError = ''"
          />
          <p v-if="targetError" class="text-xs text-red-500 mt-1">{{ targetError }}</p>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">封禁范围</label>
          <select v-model="newBan.scope" class="select-field w-full">
            <option value="all">全部</option>
            <option value="messages_only">仅留言板</option>
          </select>
        </div>
      </div>
      <button class="btn btn-primary text-sm" :disabled="banning" @click="banIP">
        {{ banning ? '封禁中...' : '添加封禁' }}
      </button>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <div v-else class="panel overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-[var(--border-color)]">
          <tr>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">封禁目标</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">类型</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">范围</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">创建时间</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="bans.length === 0">
            <td colspan="5" class="px-3 py-6 text-center text-[var(--ink-secondary)]">暂无封禁记录</td>
          </tr>
          <tr
            v-for="ban in bans"
            :key="ban.id"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <td class="px-3 py-2 font-mono">{{ ban.target }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ typeLabel(ban.type) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ scopeLabel(ban.scope) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(ban.created_at) }}</td>
            <td class="px-3 py-2">
              <button class="btn btn-danger text-xs px-2 py-1" @click="unbanIP(ban)">解封</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
