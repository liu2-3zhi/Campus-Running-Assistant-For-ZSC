<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const bans = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')

const newBan = ref({ ip: '', reason: '' })
const banning = ref(false)

function clearMessages() { error.value = ''; success.value = '' }

function formatDate(dateStr) {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('zh-CN')
}

async function loadBans() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/ip_bans', 'GET')
    bans.value = res.bans || res || []
  } catch (e) {
    error.value = e.message || '加载IP封禁列表失败'
  } finally {
    loading.value = false
  }
}

async function banIP() {
  if (!newBan.value.ip.trim()) {
    error.value = '请输入IP地址'
    return
  }
  banning.value = true
  clearMessages()
  try {
    await callRawAPI('/api/admin/ip_bans', 'POST', { ip: newBan.value.ip.trim(), reason: newBan.value.reason.trim() })
    success.value = '已封禁IP: ' + newBan.value.ip
    newBan.value = { ip: '', reason: '' }
    await loadBans()
  } catch (e) {
    error.value = e.message || '封禁IP失败'
  } finally {
    banning.value = false
  }
}

async function unbanIP(ip) {
  if (!confirm('确定要解封IP "' + ip + '" 吗？')) return
  clearMessages()
  try {
    await callRawAPI('/api/admin/ip_bans/' + encodeURIComponent(ip), 'DELETE')
    success.value = '已解封IP: ' + ip
    await loadBans()
  } catch (e) {
    error.value = e.message || '解封IP失败'
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
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">IP 地址 *</label>
          <input v-model="newBan.ip" class="input-field w-full" type="text" placeholder="例如: 192.168.1.100" />
        </div>
        <div>
          <label class="block text-xs text-[var(--ink-secondary)] mb-1">封禁原因</label>
          <input v-model="newBan.reason" class="input-field w-full" type="text" placeholder="封禁原因" />
        </div>
      </div>
      <button class="btn btn-primary text-sm" :disabled="banning" @click="banIP">
        {{ banning ? '封禁中...' : '封禁IP' }}
      </button>
    </div>

    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <div v-else class="panel overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-[var(--border-color)]">
          <tr>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">IP 地址</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">原因</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">封禁日期</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="bans.length === 0">
            <td colspan="4" class="px-3 py-6 text-center text-[var(--ink-secondary)]">暂无封禁记录</td>
          </tr>
          <tr
            v-for="ban in bans"
            :key="ban.ip"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <td class="px-3 py-2 font-mono">{{ ban.ip }}</td>
            <td class="px-3 py-2">{{ ban.reason || '--' }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatDate(ban.created_at || ban.date || ban.banned_at) }}</td>
            <td class="px-3 py-2">
              <button class="btn btn-danger text-xs px-2 py-1" @click="unbanIP(ban.ip)">解封</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
