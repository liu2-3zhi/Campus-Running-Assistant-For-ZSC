<script setup>
import { ref, computed, onMounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

// 事件类型中文映射
const EVENT_TYPE_TEXT = {
  billing_created: '创建',
  billing_amount_changed: '金额变化',
  billing_status_changed: '状态变化',
  billing_admin_cleared: '管理员清除',
  billing_reason_changed: '原因变化',
  billing_deleted: '删除',
}

// 事件类型徽章配色
const EVENT_TYPE_BADGE = {
  billing_created: 'bg-[var(--success)]/10 text-[var(--success)]',
  billing_amount_changed: 'bg-amber-500/10 text-amber-600',
  billing_status_changed: 'bg-sky-500/10 text-sky-600',
  billing_admin_cleared: 'bg-purple-500/10 text-purple-600',
  billing_reason_changed: 'bg-indigo-500/10 text-indigo-600',
  billing_deleted: 'bg-red-500/10 text-red-500',
}

const EVENT_TYPE_OPTIONS = [
  { value: '', label: '全部事件' },
  { value: 'billing_created', label: '创建' },
  { value: 'billing_amount_changed', label: '金额变化' },
  { value: 'billing_status_changed', label: '状态变化' },
  { value: 'billing_admin_cleared', label: '管理员清除' },
  { value: 'billing_reason_changed', label: '原因变化' },
  { value: 'billing_deleted', label: '删除' },
]

const PAGE_SIZE = 50

// 筛选条件
const keyword = ref('')
const eventType = ref('')

// 数据与分页
const logs = ref([])
const total = ref(0)
const currentPage = ref(1)
const loading = ref(false)
const error = ref('')

// 详情弹窗
const detailLog = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / PAGE_SIZE)))

function eventText(type) {
  return EVENT_TYPE_TEXT[String(type || '')] || String(type || '未知事件')
}

function eventBadgeClass(type) {
  return EVENT_TYPE_BADGE[String(type || '')] || 'bg-[var(--ink-muted)]/10 text-[var(--ink-secondary)]'
}

function formatJson(value) {
  try {
    return JSON.stringify(value || {}, null, 2)
  } catch (e) {
    return String(value ?? '')
  }
}

function logTime(log) {
  return log.created_at_beijing || log.created_at || '-'
}

function fieldOrDash(value) {
  const s = value === null || value === undefined ? '' : String(value)
  return s.length ? s : '-'
}

async function loadBillingLogs(page = 1) {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    })
    if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
    if (eventType.value) params.set('event_type', eventType.value)

    const data = await callRawAPI(`/api/admin/billing/logs?${params.toString()}`, 'GET')
    if (!data.success) {
      throw new Error(data.message || '加载账单日志失败')
    }
    logs.value = data.logs || []
    total.value = Number(data.total || 0)
    currentPage.value = page
  } catch (e) {
    logs.value = []
    error.value = e.message || '加载账单日志失败'
  } finally {
    loading.value = false
  }
}

function search() {
  loadBillingLogs(1)
}

function prevPage() {
  if (currentPage.value <= 1 || loading.value) return
  loadBillingLogs(currentPage.value - 1)
}

function nextPage() {
  if (currentPage.value >= totalPages.value || loading.value) return
  loadBillingLogs(currentPage.value + 1)
}

function openDetail(log) {
  detailLog.value = log
}

function closeDetail() {
  detailLog.value = null
}

onMounted(() => loadBillingLogs(1))
</script>

<template>
  <div class="space-y-4">
    <!-- 标题区 -->
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h2 class="text-lg font-semibold text-[var(--ink)]">账单日志</h2>
        <p class="text-sm text-[var(--ink-secondary)]">查看账单创建、修改、清除与删除等审计记录</p>
      </div>
      <button class="btn btn-secondary text-sm" :disabled="loading" @click="loadBillingLogs(currentPage)">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>

    <!-- 筛选栏 -->
    <div class="flex flex-wrap items-center gap-3">
      <input
        v-model="keyword"
        type="text"
        class="input-field text-sm flex-1 min-w-[200px]"
        placeholder="搜索账单号 / 用户 / 手机 / 学校账号"
        @keyup.enter="search"
      />
      <select v-model="eventType" class="select-field text-sm" @change="search">
        <option v-for="opt in EVENT_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
      <button class="btn btn-primary text-sm" :disabled="loading" @click="search">搜索</button>
    </div>

    <!-- 错误提示 -->
    <div
      v-if="error"
      class="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm flex items-center justify-between"
    >
      <span>加载失败：{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&times;</button>
    </div>

    <!-- 列表 -->
    <div class="space-y-3">
      <div v-if="loading" class="flex flex-col items-center justify-center py-12 text-[var(--ink-muted)]">
        <div class="text-3xl mb-2 animate-spin">⏳</div>
        <p class="text-sm">正在加载账单日志...</p>
      </div>

      <div
        v-else-if="logs.length === 0"
        class="flex flex-col items-center justify-center py-12 text-[var(--ink-muted)] gap-2"
      >
        <div class="text-4xl opacity-40">📄</div>
        <p class="text-sm">暂无账单日志</p>
      </div>

      <template v-else>
        <div
          v-for="(log, idx) in logs"
          :key="log.id || log.billing_id + '-' + idx"
          class="panel p-4 space-y-3"
        >
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <span
              class="inline-flex px-2.5 py-1 rounded-full text-xs font-medium"
              :class="eventBadgeClass(log.event_type)"
            >
              {{ eventText(log.event_type) }}
            </span>
            <span class="text-xs text-[var(--ink-muted)]">{{ logTime(log) }}</span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-[var(--ink-secondary)]">
            <div>账单号：<span class="font-mono text-[var(--ink)]">{{ fieldOrDash(log.billing_id) }}</span></div>
            <div>学校账号：<span class="font-mono text-[var(--ink)]">{{ fieldOrDash(log.school_username) }}</span></div>
            <div>用户：{{ fieldOrDash(log.auth_username) }}</div>
            <div>昵称：{{ fieldOrDash(log.nickname) }}</div>
            <div>手机号：{{ fieldOrDash(log.phone) }}</div>
            <div>操作人：{{ fieldOrDash(log.operator_username) }}</div>
          </div>

          <div class="text-sm text-[var(--ink-secondary)]">说明：{{ fieldOrDash(log.details) }}</div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div class="rounded-lg border border-[var(--border-color)] bg-black/[0.02] p-3">
              <div class="font-semibold text-[var(--ink-secondary)] mb-1">变更前</div>
              <pre class="whitespace-pre-wrap break-all text-[var(--ink-muted)]">{{ formatJson(log.before) }}</pre>
            </div>
            <div class="rounded-lg border border-[var(--border-color)] bg-black/[0.02] p-3">
              <div class="font-semibold text-[var(--ink-secondary)] mb-1">变更后</div>
              <pre class="whitespace-pre-wrap break-all text-[var(--ink-muted)]">{{ formatJson(log.after) }}</pre>
            </div>
          </div>

          <div class="flex justify-end">
            <button class="btn btn-ghost text-xs" @click="openDetail(log)">查看详情</button>
          </div>
        </div>
      </template>
    </div>

    <!-- 分页 -->
    <div class="flex items-center justify-between text-sm text-[var(--ink-secondary)]">
      <button
        class="btn btn-secondary text-sm"
        :disabled="currentPage <= 1 || loading"
        @click="prevPage"
      >
        上一页
      </button>
      <span>第 {{ currentPage }} 页 / 共 {{ totalPages }} 页</span>
      <button
        class="btn btn-secondary text-sm"
        :disabled="currentPage >= totalPages || loading"
        @click="nextPage"
      >
        下一页
      </button>
    </div>

    <!-- 详情弹窗 -->
    <div
      v-if="detailLog"
      class="fixed inset-0 z-[20001] flex items-center justify-center p-4 bg-black/60"
      @click.self="closeDetail"
    >
      <div class="panel w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5 space-y-4">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-2">
            <span
              class="inline-flex px-2.5 py-1 rounded-full text-xs font-medium"
              :class="eventBadgeClass(detailLog.event_type)"
            >
              {{ eventText(detailLog.event_type) }}
            </span>
            <h3 class="text-base font-semibold text-[var(--ink)]">账单日志详情</h3>
          </div>
          <button class="opacity-60 hover:opacity-100 text-xl leading-none" @click="closeDetail">&times;</button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-[var(--ink-secondary)]">
          <div>账单号：<span class="font-mono text-[var(--ink)]">{{ fieldOrDash(detailLog.billing_id) }}</span></div>
          <div>学校账号：<span class="font-mono text-[var(--ink)]">{{ fieldOrDash(detailLog.school_username) }}</span></div>
          <div>用户：{{ fieldOrDash(detailLog.auth_username) }}</div>
          <div>昵称：{{ fieldOrDash(detailLog.nickname) }}</div>
          <div>手机号：{{ fieldOrDash(detailLog.phone) }}</div>
          <div>操作人：{{ fieldOrDash(detailLog.operator_username) }}</div>
          <div>时间：{{ logTime(detailLog) }}</div>
        </div>

        <div class="text-sm text-[var(--ink-secondary)]">说明：{{ fieldOrDash(detailLog.details) }}</div>

        <div class="space-y-3 text-xs">
          <div class="rounded-lg border border-[var(--border-color)] p-3">
            <div class="font-semibold text-[var(--ink-secondary)] mb-1">变更前</div>
            <pre class="whitespace-pre-wrap break-all text-[var(--ink-muted)]">{{ formatJson(detailLog.before) }}</pre>
          </div>
          <div class="rounded-lg border border-[var(--border-color)] p-3">
            <div class="font-semibold text-[var(--ink-secondary)] mb-1">变更后</div>
            <pre class="whitespace-pre-wrap break-all text-[var(--ink-muted)]">{{ formatJson(detailLog.after) }}</pre>
          </div>
        </div>

        <div class="flex justify-end">
          <button class="btn btn-secondary text-sm" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
