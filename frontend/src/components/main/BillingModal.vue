<script setup>
/**
 * BillingModal.vue —— 用户账单列表弹窗（复刻 original §7.1 loadUserBillingList）
 * GET /api/billing/list（可 ?school_username=）；勾选待支付/已关闭账单 → 批量发起账单支付。
 */
import { ref, computed, watch } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import {
  fetchBillingList,
  billingStatusInfo,
  isBillingStatusPayable,
  getBillingTime,
  paySelectedBilling,
} from '@/composables/usePayment'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const records = ref([])
const loading = ref(false)
const errorMsg = ref('')
const schoolFilter = ref('')
const selectedIds = ref(new Set())

function formatAmount(v) {
  const n = parseFloat(v)
  return isNaN(n) ? '¥0.00' : '¥' + n.toFixed(2)
}

const payableRecords = computed(() => records.value.filter((r) => isBillingStatusPayable(r.status)))

const selectedItems = computed(() =>
  records.value
    .filter((r) => selectedIds.value.has(r.billing_id) && isBillingStatusPayable(r.status))
    .map((r) => ({ billing_id: r.billing_id, school_username: r.school_username })),
)

async function loadList() {
  loading.value = true
  errorMsg.value = ''
  selectedIds.value = new Set()
  try {
    const result = await fetchBillingList(schoolFilter.value.trim())
    if (!result.success) {
      errorMsg.value = result.message || '加载账单失败'
      records.value = []
      return
    }
    records.value = result.records || result.billings || result.list || []
  } catch (e) {
    errorMsg.value = e.message || '网络错误，请稍后重试'
    records.value = []
  } finally {
    loading.value = false
  }
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  selectedIds.value = s
}
function selectAllPayable() {
  selectedIds.value = new Set(payableRecords.value.map((r) => r.billing_id))
}
function clearSelection() {
  selectedIds.value = new Set()
}

async function payBatch() {
  await paySelectedBilling(selectedItems.value)
  await loadList()
}
async function paySingle(record) {
  await paySelectedBilling([{ billing_id: record.billing_id, school_username: record.school_username }])
  await loadList()
}

watch(() => props.visible, (v) => {
  if (v) {
    schoolFilter.value = ''
    loadList()
  }
})
</script>

<template>
  <AppModal :visible="visible" title="我的账单" width="max-w-lg" @close="emit('close')">
    <div class="space-y-3">
      <!-- 筛选 + 操作条 -->
      <div class="flex items-center gap-2 flex-wrap">
        <input
          v-model="schoolFilter"
          type="text"
          class="input-field flex-1 min-w-[140px] text-sm"
          placeholder="按学校账号筛选（留空看全部）"
          @keyup.enter="loadList"
        />
        <button class="btn btn-secondary text-xs px-3 py-1.5" :disabled="loading" @click="loadList">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <div v-if="payableRecords.length" class="flex items-center gap-2 flex-wrap text-xs">
        <button class="btn btn-ghost text-xs px-2 py-1 border border-[var(--border-color)]" @click="selectAllPayable">全选待支付</button>
        <button class="btn btn-ghost text-xs px-2 py-1 border border-[var(--border-color)]" @click="clearSelection">清空选择</button>
        <button
          class="btn btn-primary text-xs px-3 py-1 ml-auto"
          :disabled="!selectedItems.length"
          @click="payBatch"
        >
          批量支付{{ selectedItems.length ? `（${selectedItems.length}）` : '' }}
        </button>
      </div>

      <!-- 列表 -->
      <div class="max-h-[55vh] overflow-y-auto space-y-2">
        <div v-if="loading" class="text-center py-10 text-sm text-[var(--ink-muted)]">加载中...</div>
        <div v-else-if="errorMsg" class="text-center py-10 text-sm text-red-500">{{ errorMsg }}</div>
        <div v-else-if="records.length === 0" class="text-center py-12">
          <div class="text-4xl mb-2">📄</div>
          <p class="text-sm text-[var(--ink-muted)]">暂无账单记录</p>
        </div>

        <div
          v-for="r in records"
          :key="r.billing_id"
          class="rounded-xl border border-[var(--border-color)] p-3 space-y-2"
          :class="selectedIds.has(r.billing_id) ? 'ring-2 ring-[var(--accent)]' : ''"
        >
          <div class="flex items-start gap-2">
            <input
              v-if="isBillingStatusPayable(r.status)"
              type="checkbox"
              class="mt-1 w-4 h-4 accent-[var(--accent)] shrink-0"
              :checked="selectedIds.has(r.billing_id)"
              @change="toggleSelect(r.billing_id)"
            />
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-mono text-[var(--ink-muted)] truncate">账单号 {{ r.billing_id }}</span>
                <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs shrink-0" :class="billingStatusInfo(r.status).cls">
                  <span>{{ billingStatusInfo(r.status).icon }}</span>
                  <span>{{ billingStatusInfo(r.status).label }}</span>
                </span>
              </div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-sm text-[var(--ink)]">{{ r.school_name || r.school_username || '--' }}</span>
                <span class="text-base font-bold text-amber-600">{{ formatAmount(r.amount) }}</span>
              </div>
              <div v-if="r.reason" class="text-xs text-[var(--ink-muted)] mt-0.5 break-all">{{ r.reason }}</div>
              <div class="text-[10px] text-[var(--ink-muted)] mt-1">{{ getBillingTime(r, 'created_at') || '--' }}</div>
            </div>
          </div>
          <div v-if="isBillingStatusPayable(r.status)" class="flex justify-end pt-1 border-t border-[var(--border-color)]/60">
            <button class="btn btn-primary text-xs px-3 py-1" @click="paySingle(r)">支付</button>
          </div>
        </div>
      </div>
    </div>
  </AppModal>
</template>
