<script setup>
/**
 * PaymentModal.vue —— 用户支付弹窗（复刻 original §2.1–§2.3 openPaymentModal / createPaymentOrder）
 * 金额 / 支付方式（动态加载启用方式）/ 商品描述 → 校验 → 验证域名 → 创建订单 → 新窗口支付 → 启动轮询。
 */
import { ref, watch } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import { sanitizeSvg } from '@/utils/sanitizeSvg'
import {
  METHOD_NAME_FALLBACK,
  getYiPaiDevice,
  verifyHost,
  createPaymentOrderRequest,
  startOrderPolling,
  loadMethodsConfig,
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

function alertMsg(text, title = '提示', icon = 'info') {
  if (window.Swal) window.Swal.fire({ icon, title, text, confirmButtonText: '确定' })
  else window.alert(`${title}\n${text}`)
}

async function loadEnabledMethods() {
  loadingMethods.value = true
  methodsError.value = ''
  methods.value = []
  try {
    const { enabledMethods: enabled, methods: defs } = await loadMethodsConfig()

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
    selectedMethod.value = methods.value[0]?.code || ''
    if (!methods.value.length) methodsError.value = '暂无可用的支付方式'
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
  <AppModal :visible="visible" panel title="在线支付" width="max-w-md" @close="emit('close')">
    <div class="space-y-4">
      <!-- 金额 -->
      <div>
        <label for="payment-amount" class="block text-sm font-semibold leading-6 text-slate-700 mb-1">支付金额 <span class="text-red-500">*</span></label>
        <input
          id="payment-amount"
          v-model="amount"
          type="number"
          min="0.01"
          step="0.01"
          inputmode="decimal"
          class="input-field w-full"
          placeholder="请输入支付金额（最低0.01元）"
        />
      </div>

      <!-- 支付方式 -->
      <div>
        <label class="block text-sm font-semibold leading-6 text-slate-700 mb-2">支付方式 <span class="text-red-500">*</span></label>
        <div v-if="loadingMethods" class="text-center py-6 text-sm text-[var(--ink-muted)]">加载中...</div>
        <div v-else-if="methodsError" class="text-center py-6 text-sm text-[var(--ink-muted)]">{{ methodsError }}</div>
        <div v-else class="space-y-2">
          <label
            v-for="m in methods"
            :key="m.code"
            class="flex items-center gap-3 p-3 rounded-lg border-2 border-slate-200 cursor-pointer transition-colors"
          >
            <input type="radio" name="payment-method" :value="m.code" v-model="selectedMethod" class="w-4 h-4" />
            <span class="flex items-center gap-2">
            <span class="h-7 flex items-center justify-center shrink-0">
              <span v-if="m.svg" class="w-6 h-6 flex items-center justify-center" v-html="sanitizeSvg(m.svg)"></span>
              <img v-else-if="m.image" :src="m.image" class="w-6 h-6 object-contain" alt="" />
              <span v-else class="text-lg">{{ m.icon && !['svg', 'image'].includes(m.icon) ? m.icon : '💳' }}</span>
            </span>
            <span class="text-sm font-medium text-slate-700">{{ m.name }}</span>
            </span>
          </label>
        </div>
      </div>

      <div>
        <label for="payment-product-name" class="block text-sm font-semibold leading-6 text-slate-700 mb-1">商品描述</label>
        <input id="payment-product-name" v-model="productName" type="text" class="input-field w-full" placeholder="商品描述（例如：跑步服务费用）" />
      </div>

      <!-- 操作按钮 -->
      <div class="flex justify-end gap-3 pt-4 border-t border-slate-200">
        <button class="btn btn-ghost" @click="emit('close')">取消</button>
        <button
          class="btn btn-primary"
          :disabled="submitting || loadingMethods || !methods.length"
          @click="submit"
        >
          {{ submitting ? '创建中...' : '立即支付' }}
        </button>
      </div>
    </div>
  </AppModal>
</template>
