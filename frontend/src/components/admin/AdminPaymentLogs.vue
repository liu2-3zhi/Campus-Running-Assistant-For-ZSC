<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import AppModal from '@/components/common/AppModal.vue'

const auth = useAuthStore()
const canViewAllUsers = computed(() => !!auth.permissions?.view_audit_logs)
const showAllUsers = ref(false)
const viewingAllUsers = computed(() => canViewAllUsers.value && showAllUsers.value)

// ---- 列表状态 ----
const logs = ref([])
const users = ref([])
const total = ref(0)
const currentPage = ref(1)
const perPage = ref(20)
const loading = ref(false)
const error = ref('')

// ---- 筛选条件 ----
const filterUserId = ref('')
const filterAction = ref('')
const filterStartDate = ref('')
const filterEndDate = ref('')

// ---- 详情弹窗 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detailData = ref(null)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / perPage.value))
)

// 操作类型 -> 中文与徽章样式
const ACTION_CONFIG = {
  create_order: { label: '创建订单', cls: 'bg-blue-100 text-blue-700' },
  query_order: { label: '查询订单', cls: 'bg-purple-100 text-purple-700' },
  create_order_failed: { label: '创建失败', cls: 'bg-red-100 text-red-700' },
  payment_success_notify: { label: '支付成功通知', cls: 'bg-emerald-100 text-emerald-700' },
  payment_success: { label: '支付成功', cls: 'bg-emerald-100 text-emerald-700' },
  payment_notify: { label: '支付通知', cls: 'bg-teal-100 text-teal-700' },
  payment_fail: { label: '支付失败', cls: 'bg-red-100 text-red-700' },
  refund: { label: '退款操作', cls: 'bg-orange-100 text-orange-700' },
  refund_failed: { label: '退款失败', cls: 'bg-red-100 text-red-700' },
  fetch_orders_from_platform: { label: '从平台拉取订单', cls: 'bg-sky-100 text-sky-700' },
  sync_order_from_platform: { label: '从平台同步订单', cls: 'bg-sky-100 text-sky-700' },
  query_order_by_tradeno: { label: '按订单号查询', cls: 'bg-purple-100 text-purple-700' },
  order_status_updated: { label: '订单状态更新', cls: 'bg-cyan-100 text-cyan-700' },
  create_order_from_notify: { label: '根据通知补建订单', cls: 'bg-blue-100 text-blue-700' },
  query_platform_order_failed: { label: '平台订单查询失败', cls: 'bg-red-100 text-red-700' },
  payment_notify_no_public_key: { label: '支付通知未配置公钥', cls: 'bg-amber-100 text-amber-700' },
  payment_notify_signature_failed: { label: '支付通知验签失败', cls: 'bg-red-100 text-red-700' },
  payment_notify_order_not_found: { label: '支付通知订单不存在', cls: 'bg-red-100 text-red-700' },
  payment_duplicate_notify: { label: '重复支付通知', cls: 'bg-amber-100 text-amber-700' },
  create_overdue_order: { label: '创建欠费订单', cls: 'bg-orange-100 text-orange-700' },
  overdue_payment_completed: { label: '欠费支付完成', cls: 'bg-emerald-100 text-emerald-700' },
  overdue_payment_error: { label: '欠费支付处理失败', cls: 'bg-red-100 text-red-700' },
  create_billing_order: { label: '创建账单订单', cls: 'bg-blue-100 text-blue-700' },
  billing_payment_completed: { label: '账单支付完成', cls: 'bg-emerald-100 text-emerald-700' },
  query_billing_order_active: { label: '主动查询账单订单', cls: 'bg-purple-100 text-purple-700' },
  query_billing_order_local: { label: '本地查询账单订单', cls: 'bg-purple-100 text-purple-700' },
  admin_update_payment_config: { label: '更新支付配置', cls: 'bg-amber-100 text-amber-700' },
  admin_update_pricing_config: { label: '更新价格配置', cls: 'bg-amber-100 text-amber-700' },
  admin_update_yipay_config: { label: '更新易支付配置', cls: 'bg-amber-100 text-amber-700' },
  admin_clear_overdue: { label: '调整欠费次数', cls: 'bg-amber-100 text-amber-700' },
  config_update: { label: '配置更新', cls: 'bg-amber-100 text-amber-700' },
}

const ACTION_FILTER_OPTIONS = Object.entries(ACTION_CONFIG).map(([value, config]) => ({
  value,
  label: config.label,
}))

function actionInfo(action) {
  return ACTION_CONFIG[action] || { label: action || '未知操作', cls: 'bg-slate-100 text-slate-600' }
}

// 状态 -> 中文与徽章样式
function statusInfo(status) {
  const normalized = String(status || '').trim()
  if (!normalized) return null
  const map = {
    success: { label: '成功', cls: 'bg-emerald-100 text-emerald-700' },
    completed: { label: '成功', cls: 'bg-emerald-100 text-emerald-700' },
    paid: { label: '已支付', cls: 'bg-emerald-100 text-emerald-700' },
    pending: { label: '处理中', cls: 'bg-amber-100 text-amber-700' },
    processing: { label: '处理中', cls: 'bg-amber-100 text-amber-700' },
    failed: { label: '失败', cls: 'bg-red-100 text-red-700' },
    fail: { label: '失败', cls: 'bg-red-100 text-red-700' },
    error: { label: '失败', cls: 'bg-red-100 text-red-700' },
    refunded_partial: { label: '部分退款', cls: 'bg-orange-100 text-orange-700' },
    refunded_full: { label: '全额退款', cls: 'bg-orange-100 text-orange-700' },
    frozen: { label: '已冻结', cls: 'bg-slate-100 text-slate-600' },
    preauth: { label: '预授权', cls: 'bg-blue-100 text-blue-700' },
    timeout: { label: '支付超时', cls: 'bg-red-100 text-red-700' },
    closed: { label: '已关闭', cls: 'bg-slate-100 text-slate-600' },
  }
  return map[normalized] || { label: normalized, cls: 'bg-slate-100 text-slate-600' }
}

function formatTime(log) {
  if (log && log.datetime) return log.datetime
  const ts = log && log.timestamp
  if (!ts) return '--'
  const ms = ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ms)
  return isNaN(d.getTime()) ? '--' : d.toLocaleString('zh-CN', { hour12: false })
}

function formatAmount(amount) {
  if (amount === undefined || amount === null || amount === '') return '-'
  const n = parseFloat(amount)
  if (isNaN(n)) return '-'
  return `¥${n.toFixed(2)}`
}

async function fetchLogs(page = currentPage.value) {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('page', String(page))
    params.set('per_page', String(perPage.value))
    if (viewingAllUsers.value && filterUserId.value) params.set('user_id', filterUserId.value)
    if (filterAction.value) params.set('action', filterAction.value)
    if (filterStartDate.value) params.set('start_date', filterStartDate.value)
    if (filterEndDate.value) params.set('end_date', filterEndDate.value)

    const endpoint = viewingAllUsers.value ? '/api/admin/payment_logs' : '/api/payment_logs'
    const data = await callRawAPI(`${endpoint}?${params.toString()}`, 'GET')
    if (data.success === false) {
      throw new Error(data.message || '获取支付日志失败')
    }
    logs.value = data.logs || []
    total.value = data.total || 0
    currentPage.value = data.page || page
    if (Array.isArray(data.users)) users.value = data.users
  } catch (e) {
    logs.value = []
    total.value = 0
    error.value = e.message || '获取支付日志失败'
  } finally {
    loading.value = false
  }
}

function searchLogs() {
  currentPage.value = 1
  fetchLogs(1)
}

function resetFilters() {
  filterUserId.value = ''
  filterAction.value = ''
  filterStartDate.value = ''
  filterEndDate.value = ''
  currentPage.value = 1
  fetchLogs(1)
}

function goPage(page) {
  if (page < 1 || page > totalPages.value || loading.value) return
  currentPage.value = page
  fetchLogs(page)
}

async function openDetail(log) {
  if (!viewingAllUsers.value) {
    detailError.value = ''
    detailLoading.value = false
    detailData.value = log
    detailVisible.value = true
    return
  }
  const logId = log.log_id
  if (!logId) {
    detailError.value = '缺少日志 ID，无法查看详情'
    detailData.value = null
    detailVisible.value = true
    return
  }
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detailData.value = null
  try {
    const data = await callRawAPI('/api/admin/payment/log_detail', 'POST', { log_id: logId })
    if (data.success === false) {
      throw new Error(data.message || '获取日志详情失败')
    }
    detailData.value = data.log_detail || {}
  } catch (e) {
    detailError.value = e.message || '获取日志详情失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detailData.value = null
  detailError.value = ''
}

const detailJson = computed(() =>
  detailData.value ? JSON.stringify(detailData.value, null, 2) : ''
)

onMounted(() => fetchLogs(1))
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-[var(--ink)]">支付历史</h2>
      <button class="btn btn-secondary text-sm" :disabled="loading" @click="fetchLogs(currentPage)">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <p class="text-sm text-[var(--ink-secondary)]">
      {{ viewingAllUsers ? '查看所有用户的支付操作日志，支持按用户、操作类型与日期范围筛选。' : '查看自己的支付操作记录，支持按操作类型与日期范围筛选。' }}
    </p>
    <label v-if="canViewAllUsers" class="flex items-center gap-2 text-sm text-[var(--ink-secondary)]">
      <input v-model="showAllUsers" type="checkbox" class="h-4 w-4 accent-sky-600" @change="resetFilters" />
      查看所有用户
    </label>

    <!-- 筛选条件 -->
    <div class="panel p-4 space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <div v-if="viewingAllUsers">
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">用户</label>
          <select v-model="filterUserId" class="select-field w-full text-sm">
            <option value="">全部用户</option>
            <option v-for="u in users" :key="u" :value="u">{{ u }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">操作类型</label>
          <select v-model="filterAction" class="select-field w-full text-sm">
            <option value="">全部操作</option>
            <option v-for="option in ACTION_FILTER_OPTIONS" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">开始日期</label>
          <input v-model="filterStartDate" type="date" class="input-field w-full text-sm" />
        </div>
        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">结束日期</label>
          <input v-model="filterEndDate" type="date" class="input-field w-full text-sm" />
        </div>
      </div>
      <div class="flex flex-wrap gap-3">
        <button class="btn btn-primary text-sm" :disabled="loading" @click="searchLogs">查询日志</button>
        <button class="btn btn-ghost text-sm" :disabled="loading" @click="resetFilters">重置</button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="fetchLogs(currentPage)">重试</button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading && logs.length === 0" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <!-- 空态 -->
    <div v-else-if="!loading && logs.length === 0 && !error" class="panel py-12 text-center text-[var(--ink-secondary)]">
      <div class="text-4xl mb-3">🧾</div>
      <p class="text-sm">暂无支付日志</p>
    </div>

    <!-- 日志卡片列表 -->
    <div v-else class="space-y-3">
      <div
        v-for="(log, idx) in logs"
        :key="log.log_id || idx"
        class="panel p-4"
      >
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="actionInfo(log.action).cls">
              {{ actionInfo(log.action).label }}
            </span>
            <span
              v-if="statusInfo(log.status)"
              class="px-2 py-0.5 rounded-full text-xs font-medium"
              :class="statusInfo(log.status).cls"
            >
              {{ statusInfo(log.status).label }}
            </span>
          </div>
          <span class="text-base font-semibold text-[var(--ink)]">{{ formatAmount(log.amount) }}</span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">订单号:</span>
            <span class="font-mono break-all text-[var(--ink)]">{{ log.order_id || '-' }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">用户:</span>
            <span class="font-mono break-all text-[var(--ink)]">{{ log.user_id || '-' }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">时间:</span>
            <span class="text-[var(--ink)]">{{ formatTime(log) }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">客户端 IP:</span>
            <span class="font-mono text-[var(--ink)]">{{ log.client_ip || '-' }}</span>
          </div>
        </div>

        <div class="mt-3 flex justify-end">
          <button class="btn btn-secondary text-xs px-3 py-1" @click="openDetail(log)">查看详情</button>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="logs.length > 0" class="flex items-center justify-between text-sm text-[var(--ink-secondary)]">
      <button
        class="btn btn-secondary text-sm"
        :disabled="currentPage <= 1 || loading"
        @click="goPage(currentPage - 1)"
      >
        上一页
      </button>
      <span>第 {{ currentPage }} / {{ totalPages }} 页（共 {{ total }} 条）</span>
      <button
        class="btn btn-secondary text-sm"
        :disabled="currentPage >= totalPages || loading"
        @click="goPage(currentPage + 1)"
      >
        下一页
      </button>
    </div>

    <!-- 详情弹窗 -->
    <AppModal :visible="detailVisible" title="支付日志详情" width="max-w-2xl" @close="closeDetail">
      <div v-if="detailLoading" class="py-10 text-center text-[var(--ink-secondary)]">加载中...</div>
      <div v-else-if="detailError" class="px-4 py-3 rounded-lg text-sm bg-red-100 text-red-700">
        {{ detailError }}
      </div>
      <div v-else-if="detailData" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">时间:</span>
            <span class="text-[var(--ink)]">{{ formatTime(detailData) }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">操作类型:</span>
            <span class="text-[var(--ink)]">{{ actionInfo(detailData.action).label }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">状态:</span>
            <span class="text-[var(--ink)]">{{ statusInfo(detailData.status)?.label || detailData.status || '-' }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">用户:</span>
            <span class="font-mono break-all text-[var(--ink)]">{{ detailData.user_id || '-' }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">订单号:</span>
            <span class="font-mono break-all text-[var(--ink)]">{{ detailData.order_id || '-' }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">客户端 IP:</span>
            <span class="font-mono text-[var(--ink)]">{{ detailData.client_ip || '-' }}</span>
          </div>
          <div class="flex gap-2">
            <span class="text-[var(--ink-secondary)] shrink-0">金额:</span>
            <span class="text-[var(--ink)]">{{ formatAmount(detailData.amount) }}</span>
          </div>
        </div>

        <div>
          <div class="text-sm text-[var(--ink-secondary)] mb-1">完整数据</div>
          <pre class="p-3 rounded-lg bg-[var(--glass)] text-xs font-mono overflow-auto max-h-80 text-[var(--ink)] whitespace-pre-wrap break-all">{{ detailJson }}</pre>
        </div>
      </div>
      <div v-else class="py-10 text-center text-[var(--ink-secondary)]">暂无详情数据</div>

      <div class="mt-4 flex justify-end">
        <button class="btn btn-secondary text-sm" @click="closeDetail">关闭</button>
      </div>
    </AppModal>
  </div>
</template>
