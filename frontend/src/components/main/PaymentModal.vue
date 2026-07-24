<script setup>
/**
 * PaymentModal.vue —— 用户支付弹窗（复刻 original §2.1–§2.3 openPaymentModal / createPaymentOrder）
 * 金额 / 支付方式（动态加载启用方式）/ 商品描述 → 校验 → 验证域名 → 创建订单 → 新窗口支付 → 启动轮询。
 */
import { ref, watch } from 'vue'
import { callRawAPI } from '@/services/api'
import AppModal from '@/components/common/AppModal.vue'
import { sanitizeSvg } from '@/utils/sanitizeSvg'
import {
  METHOD_NAME_FALLBACK,
  getYiPaiDevice,
  verifyHost,
  createPaymentOrderRequest,
  startOrderPolling,
} from '@/composables/usePayment'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'paid'])

const amount = ref('')
const productName = ref('在线支付')
const selectedMethod = ref('')
const methods = ref([]) // [{ code, name, svg, image, icon, borderColor, textColor }]
const loadingMethods = ref(false)
const methodsError = ref('')
const submitting = ref(false)

function getSwal() { return window.Swal }
function alertMsg(text, title = '提示', icon = 'info') {
  if (window.Swal) window.Swal.fire({ icon, title, text, confirmButtonText: '确定' })
  else window.alert(`${title}\n${text}`)
}

function normalizeMethods(raw) {
  if (!raw) return {}
  if (Array.isArray(raw)) {
    const o = {}
    raw.forEach((m) => { if (m && m.code) o[m.code] = m })
    return o
  }
  return raw
}

async function loadEnabledMethods() {
  loadingMethods.value = true
  methodsError.value = ''
  methods.value = []
  try {
    // 支付方式定义
    let defs = {}
    try {
      const cfg = await callRawAPI('/api/payment/methods_config', 'GET')
      defs = normalizeMethods(cfg.methods || cfg.payment_methods || {})
    } catch (_) { /* ignore */ }

    // 启用的支付方式
    let enabled = []
    try {
      const c = await callRawAPI('/api/admin/payment/config', 'GET')
      const conf = c.config || c
      enabled = conf.enabled_payment_methods || []
    } catch (_) { /* ignore */ }
    if (!enabled.length) {
      // 回退：methods_config 的 enabled_methods，或全部定义
      try {
        const cfg2 = await callRawAPI('/api/payment/methods_config', 'GET')
        enabled = cfg2.enabled_methods || []
      } catch (_) { /* ignore */ }
    }
    if (!enabled.length) enabled = Object.keys(defs)

    methods.value = enabled.map((code) => {
      const d = defs[code] || {}
      return {
        code,
        name: d.name || METHOD_NAME_FALLBACK[code] || code,
        svg: d.svg || '',
        image: d.image || '',
        icon: d.icon || '',
        borderColor: d.borderColor || '',
        textColor: d.textColor || '',
      }
    })
    if (methods.value.length) selectedMethod.value = methods.value[0].code
    else methodsError.value = '暂无可用的支付方式'
  } catch (e) {
    methodsError.value = e.message || '加载支付方式失败'
  } finally {
    loadingMethods.value = false
  }
}

function resetForm() {
  amount.value = ''
  productName.value = '在线支付'
  selectedMethod.value = ''
}

// 复刻 original closePaymentModal：关闭支付弹窗不停止订单轮询
// （轮询为共享单例，支付页关闭后仍需检测支付结果，仅"我的订单"关闭时停止）
watch(() => props.visible, (v) => {
  if (v) {
    resetForm()
    loadEnabledMethods()
  }
})

async function submit() {
  const amt = String(amount.value).trim()
  if (!amt) { alertMsg('请输入支付金额'); return }
  if (parseFloat(amt) < 0.01) { alertMsg('支付金额不能低于0.01元'); return }
  if (!selectedMethod.value) { alertMsg('请选择支付方式'); return }
  const pn = String(productName.value).trim()
  if (!pn) { alertMsg('请输入商品描述'); return }

  submitting.value = true
  const appHost = window.location.protocol + '//' + window.location.host
  try {
    const verify = await verifyHost(appHost)
    if (!verify.success) {
      alertMsg(verify.message || '当前域名未授权，无法创建订单', '验证失败', 'error')
      return
    }
    const createResult = await createPaymentOrderRequest({
      amount: amt,
      payment_type: 'jump',
      payment_method: selectedMethod.value,
      product_name: pn,
      app_host: appHost,
      return_url: window.location.href,
      sub_openid: '',
      sub_appid: '',
      device: getYiPaiDevice(),
    })
    if (!createResult.success) {
      alertMsg(createResult.message || '创建订单时出错，请稍后重试', '创建订单失败', 'error')
      return
    }
    const payUrl = createResult.pay_url
    const orderId = createResult.order_id
    emit('close')
    if (payUrl) window.open(payUrl, '_blank')
    alertMsg('请在新打开的页面完成支付，支付完成后会自动刷新订单状态', '订单已创建', 'success')
    startOrderPolling(orderId, { onPaid: () => emit('paid') })
  } catch (e) {
    alertMsg('网络错误，请检查网络连接后重试', '错误', 'error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal :visible="visible" title="发起支付" width="max-w-md" @close="emit('close')">
    <div class="space-y-4">
      <!-- 金额 -->
      <div>
        <label class="block text-sm text-[var(--ink-secondary)] mb-1">支付金额（元）</label>
        <input
          v-model="amount"
          type="number"
          min="0.01"
          step="0.01"
          class="input-field w-full"
          placeholder="请输入支付金额（不低于 0.01）"
        />
      </div>

      <!-- 商品描述 -->
      <div>
        <label class="block text-sm text-[var(--ink-secondary)] mb-1">商品描述</label>
        <input v-model="productName" type="text" class="input-field w-full" placeholder="在线支付" />
      </div>

      <!-- 支付方式 -->
      <div>
        <label class="block text-sm text-[var(--ink-secondary)] mb-2">支付方式</label>
        <div v-if="loadingMethods" class="text-center py-6 text-sm text-[var(--ink-muted)]">加载中...</div>
        <div v-else-if="methodsError" class="text-center py-6 text-sm text-[var(--ink-muted)]">{{ methodsError }}</div>
        <div v-else class="space-y-2">
          <label
            v-for="m in methods"
            :key="m.code"
            class="flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition-all"
            :style="{ borderColor: selectedMethod === m.code ? (m.borderColor || 'var(--accent)') : 'var(--border-color)' }"
          >
            <input type="radio" name="payment-method" :value="m.code" v-model="selectedMethod" class="w-4 h-4 accent-[var(--accent)]" />
            <span class="w-7 h-7 flex items-center justify-center shrink-0">
              <span v-if="m.svg" class="w-6 h-6 flex items-center justify-center" v-html="sanitizeSvg(m.svg)"></span>
              <img v-else-if="m.image" :src="m.image" class="w-6 h-6 object-contain" alt="" />
              <span v-else class="text-lg">{{ m.icon || '💳' }}</span>
            </span>
            <span class="text-sm font-semibold" :style="{ color: m.textColor || 'var(--ink)' }">{{ m.name }}</span>
          </label>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex justify-end gap-2 pt-1">
        <button class="btn btn-secondary" @click="emit('close')">取消</button>
        <button
          class="btn btn-primary"
          :disabled="submitting || loadingMethods || !methods.length"
          @click="submit"
        >
          {{ submitting ? '创建中...' : '确认支付' }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
