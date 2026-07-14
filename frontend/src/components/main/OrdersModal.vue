<script setup>
/**
 * OrdersModal.vue —— 用户订单列表弹窗（复刻 original §2.6–§2.12）
 * 状态筛选 / 分页 / 继续支付 / 查询状态 / 刷新。GET /api/payment/orders。
 */
import { ref, watch, onUnmounted } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import {
  fetchPaymentOrders,
  orderStatusInfo,
  orderPayTypeText,
  continuePay,
  refreshOrderStatus,
  stopOrderPolling,
} from '@/composables/usePayment'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const PER_PAGE = 10
const orders = ref([])
const total = ref(0)
const currentPage = ref(1)
const totalPages = ref(1)
const currentStatus = ref('all')
const loading = ref(false)
const errorMsg = ref('')

const filters = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待支付' },
  { key: 'paid', label: '已支付' },
  { key: 'closed', label: '已关闭' },
]

function formatAmount(v) {
  const n = parseFloat(v)
  return isNaN(n) ? '¥0.00' : '¥' + n.toFixed(2)
}
function formatTime(v) {
  if (!v) return '--'
  const d = new Date(v)
  if (isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  })
}

async function loadOrders(status = currentStatus.value, page = currentPage.value) {
  currentStatus.value = status
  currentPage.value = page
  loading.value = true
  errorMsg.value = ''
  try {
    const result = await fetchPaymentOrders(status, page, PER_PAGE)
    if (!result.success) {
      errorMsg.value = result.message || '加载订单失败'
      orders.value = []
      total.value = 0
      totalPages.value = 1
      return
    }
    orders.value = result.orders || []
    total.value = result.total || 0
    totalPages.value = Math.max(1, Math.ceil(total.value / PER_PAGE))
  } catch (e) {
    errorMsg.value = '网络错误，请稍后重试'
    orders.value = []
  } finally {
    loading.value = false
  }
}

function setFilter(status) {
  loadOrders(status, 1)
}
function prevPage() {
  if (currentPage.value > 1) loadOrders(currentStatus.value, currentPage.value - 1)
}
function nextPage() {
  if (currentPage.value < totalPages.value) loadOrders(currentStatus.value, currentPage.value + 1)
}

async function onContinuePay(orderId) {
  await continuePay(orderId, { onPaid: () => loadOrders() })
}
async function onRefreshStatus(orderId) {
  await refreshOrderStatus(orderId)
  await loadOrders(currentStatus.value, currentPage.value)
}

watch(() => props.visible, (v) => {
  if (v) {
    currentStatus.value = 'all'
    currentPage.value = 1
    loadOrders('all', 1)
  } else {
    stopOrderPolling()
  }
})

onUnmounted(() => stopOrderPolling())
</script>

<template>
  <AppModal :visible="visible" title="我的订单" width="max-w-lg" @close="emit('close')">
    <div class="space-y-3">
      <!-- 筛选 + 刷新 -->
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex gap-1.5 flex-wrap">
          <button
            v-for="f in filters"
            :key="f.key"
            class="text-xs px-3 py-1 rounded-full border transition-colors"
            :class="currentStatus === f.key
              ? 'bg-sky-500 text-white border-sky-500'
              : 'border-[var(--border-color)] text-[var(--ink-secondary)] hover:bg-[var(--glass)]'"
            @click="setFilter(f.key)"
          >
            {{ f.label }}
          </button>
        </div>
        <button class="btn btn-secondary text-xs px-3 py-1" :disabled="loading" @click="loadOrders(currentStatus, currentPage)">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <!-- 列表 -->
      <div class="max-h-[55vh] overflow-y-auto space-y-3">
        <div v-if="loading" class="text-center py-10 text-sm text-[var(--ink-muted)]">加载中...</div>
        <div v-else-if="errorMsg" class="text-center py-10 text-sm text-red-500">{{ errorMsg }}</div>
        <div v-else-if="orders.length === 0" class="text-center py-12">
          <svg class="w-14 h-14 mx-auto text-[var(--ink-muted)] mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p class="text-sm text-[var(--ink-muted)]">暂无订单</p>
        </div>

        <div
          v-for="order in orders"
          :key="order.order_id"
          class="rounded-xl border-2 p-4 space-y-3"
          :class="orderStatusInfo(order.status).cls"
        >
          <div class="flex justify-between items-start">
            <div class="min-w-0">
              <p class="text-xs text-[var(--ink-muted)]">订单号</p>
              <p class="text-sm font-mono font-semibold text-[var(--ink)] break-all">{{ order.order_id }}</p>
            </div>
            <span class="px-3 py-1 rounded-full text-xs font-semibold border shrink-0" :class="orderStatusInfo(order.status).cls">
              {{ orderStatusInfo(order.status).text }}
            </span>
          </div>

          <div class="space-y-1.5 text-sm">
            <div class="flex justify-between">
              <span class="text-[var(--ink-muted)]">支付金额</span>
              <span class="font-bold text-lg text-sky-600">{{ formatAmount(order.amount) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--ink-muted)]">支付方式</span>
              <span class="text-[var(--ink)]">{{ orderPayTypeText(order.pay_type) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--ink-muted)]">商品名称</span>
              <span class="text-[var(--ink)]">{{ order.product_name || '在线支付' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--ink-muted)]">创建时间</span>
              <span class="text-[var(--ink-muted)] text-xs">{{ formatTime(order.create_time) }}</span>
            </div>
          </div>

          <div class="flex gap-2 pt-2 border-t border-[var(--border-color)]/60">
            <button
              v-if="order.status === 'pending'"
              class="flex-1 py-2 px-3 bg-sky-500 text-white rounded-lg text-xs font-medium hover:bg-sky-600 transition"
              @click="onContinuePay(order.order_id)"
            >
              继续支付
            </button>
            <button
              class="py-2 px-3 rounded-lg text-xs font-medium bg-[var(--glass)] text-[var(--ink-secondary)] hover:bg-[var(--border-color)] transition"
              :class="order.status === 'pending' ? 'flex-1' : 'w-full'"
              @click="onRefreshStatus(order.order_id)"
            >
              查询状态
            </button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="!loading && orders.length" class="flex items-center justify-between text-xs text-[var(--ink-secondary)] pt-1">
        <button
          class="btn btn-secondary text-xs px-3 py-1"
          :disabled="currentPage <= 1"
          @click="prevPage"
        >上一页</button>
        <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
        <button
          class="btn btn-secondary text-xs px-3 py-1"
          :disabled="currentPage >= totalPages"
          @click="nextPage"
        >下一页</button>
      </div>
    </div>
  </AppModal>
</template>
