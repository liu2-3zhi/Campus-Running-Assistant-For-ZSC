<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'
import TabPanel from '@/components/common/TabPanel.vue'

// ── 子标签 ──
const subTabs = [
  { key: 'config', label: '支付方式' },
  { key: 'query', label: '订单查询' },
  { key: 'refund', label: '退款' },
  { key: 'test', label: '测试支付' },
  { key: 'product-test', label: '商品名测试' },
  { key: 'yipay', label: '易支付配置' },
]
const activeTab = ref('config')

function onTabChange(key) {
  activeTab.value = key
  if (key === 'query' && orders.value.length === 0) loadOrders()
  if (key === 'yipay' && !yipayLoaded.value) loadYiPay()
}

// ── 公共提示 ──
function alertOk(title, text) {
  window.Swal?.fire({ icon: 'success', title, text, timer: 1600, showConfirmButton: false })
}
function alertErr(title, text) {
  window.Swal?.fire({ icon: 'error', title, text })
}
async function confirmDialog(title, text) {
  if (window.Swal) {
    const r = await window.Swal.fire({ icon: 'warning', title, text, showCancelButton: true, confirmButtonText: '确定', cancelButtonText: '取消' })
    return !!r.isConfirmed
  }
  return window.confirm(`${title}\n${text}`)
}

// ── 公共工具 ──
function toArr(v) {
  if (Array.isArray(v)) return v.filter(Boolean)
  if (typeof v === 'string') return v.split(',').map((s) => s.trim()).filter(Boolean)
  return []
}
function normalizeMethods(raw) {
  if (!raw) return {}
  if (Array.isArray(raw)) {
    const obj = {}
    raw.forEach((m) => { if (m && m.code) obj[m.code] = m })
    return obj
  }
  return raw
}
function sanitizeSvg(svg) {
  if (!svg || typeof svg !== 'string') return ''
  return svg
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
}
const METHOD_LABELS = { alipay: '支付宝', wxpay: '微信支付', wechat: '微信支付', qqpay: 'QQ钱包', qq: 'QQ钱包', bank: '网银支付', unionpay: '云闪付' }
function methodLabel(code) { return paymentMethodDefs.value[code]?.name || METHOD_LABELS[code] || code }

function pad2(n) { return String(n).padStart(2, '0') }
function genRefundNo() {
  const d = new Date()
  const ts = `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}${pad2(d.getHours())}${pad2(d.getMinutes())}${pad2(d.getSeconds())}`
  return `REFUND${ts}${Math.floor(100000 + Math.random() * 900000)}`
}

// 订单状态映射
const ORDER_STATUS = {
  TRADE_SUCCESS: { text: '已支付', cls: 'text-green-600' },
  paid: { text: '已支付', cls: 'text-green-600' },
  completed: { text: '已完成', cls: 'text-green-600' },
  pending: { text: '待支付', cls: 'text-amber-600' },
  failed: { text: '失败', cls: 'text-red-500' },
  closed: { text: '已关闭', cls: 'text-slate-500' },
  refunded_partial: { text: '部分退款', cls: 'text-orange-600' },
  refunded_full: { text: '全额退款', cls: 'text-rose-600' },
  frozen: { text: '已冻结', cls: 'text-sky-600' },
  preauth: { text: '预授权', cls: 'text-indigo-600' },
  timeout: { text: '超时', cls: 'text-slate-500' },
}
function statusInfo(s) { return ORDER_STATUS[s] || { text: s || '未知', cls: 'text-[var(--ink-secondary)]' } }

// ==================== Tab 1: 支付方式 ====================
const paymentMethodDefs = ref({})
const enabledMethods = ref([])
const methodsLoading = ref(false)
const savingMethods = ref(false)

async function loadPaymentMethods() {
  methodsLoading.value = true
  try {
    const defs = await callRawAPI('/api/payment/methods_config', 'GET')
    paymentMethodDefs.value = normalizeMethods(defs.methods || defs.payment_methods || defs.data || defs)
    try {
      const cfg = await callRawAPI('/api/admin/payment/config', 'GET')
      enabledMethods.value = toArr(cfg.enabled_payment_methods ?? cfg.enabled_methods)
    } catch (e) {
      enabledMethods.value = Object.keys(paymentMethodDefs.value)
    }
  } catch (e) {
    alertErr('加载失败', e.message || '加载支付方式失败')
  } finally {
    methodsLoading.value = false
  }
}
function isEnabled(code) { return enabledMethods.value.includes(code) }
function toggleEnabled(code) {
  const i = enabledMethods.value.indexOf(code)
  if (i >= 0) enabledMethods.value.splice(i, 1)
  else enabledMethods.value.push(code)
}
async function saveEnabledMethods() {
  if (enabledMethods.value.length === 0) { alertErr('保存失败', '请至少启用一个支付方式'); return }
  savingMethods.value = true
  try {
    const data = await callRawAPI('/api/admin/payment/config', 'PUT', { enabled_payment_methods: enabledMethods.value })
    if (data.success !== false) { alertOk('保存成功', '支付方式配置已更新'); await loadPaymentMethods() }
    else alertErr('保存失败', data.message || '保存失败')
  } catch (e) { alertErr('保存失败', e.message) } finally { savingMethods.value = false }
}

// 新增 / 编辑 支付方式弹窗
const showMethodModal = ref(false)
const methodModalMode = ref('add')
const savingMethod = ref(false)
const methodError = ref('')
const methodForm = reactive({ code: '', name: '', logoType: 'svg', svg: '', image: '', icon: '', description: '', borderColor: '', textColor: '' })
function resetMethodForm() {
  Object.assign(methodForm, { code: '', name: '', logoType: 'svg', svg: '', image: '', icon: '', description: '', borderColor: '', textColor: '' })
  methodError.value = ''
}
function openAddMethod() { resetMethodForm(); methodModalMode.value = 'add'; showMethodModal.value = true }
function openEditMethod(code) {
  const def = paymentMethodDefs.value[code] || {}
  resetMethodForm()
  methodForm.code = code
  methodForm.name = def.name || ''
  methodForm.svg = def.svg || ''
  methodForm.image = def.image || ''
  methodForm.logoType = def.image ? 'image' : 'svg'
  methodForm.icon = def.icon || ''
  methodForm.description = def.description || ''
  methodForm.borderColor = def.borderColor || ''
  methodForm.textColor = def.textColor || ''
  methodModalMode.value = 'edit'
  showMethodModal.value = true
}
async function saveMethod() {
  methodError.value = ''
  if (!/^[a-zA-Z0-9_]+$/.test(methodForm.code)) { methodError.value = '方式代码只能包含字母、数字、下划线'; return }
  if (!methodForm.name.trim()) { methodError.value = '请填写支付方式名称'; return }
  if (methodForm.logoType === 'svg' ? !methodForm.svg.trim() : !methodForm.image.trim()) {
    methodError.value = methodForm.logoType === 'svg' ? '请填写 SVG 代码' : '请填写图片地址'
    return
  }
  savingMethod.value = true
  try {
    const body = {
      name: methodForm.name.trim(),
      icon: methodForm.logoType,
      svg: methodForm.logoType === 'svg' ? methodForm.svg : '',
      image: methodForm.logoType === 'image' ? methodForm.image : '',
      description: methodForm.description,
      borderColor: methodForm.borderColor,
      textColor: methodForm.textColor,
    }
    let data
    if (methodModalMode.value === 'edit') {
      data = await callRawAPI(`/api/admin/payment_methods/${encodeURIComponent(methodForm.code)}`, 'PUT', body)
    } else {
      data = await callRawAPI('/api/admin/payment_methods', 'POST', { code: methodForm.code, ...body })
    }
    if (data.success !== false) {
      showMethodModal.value = false
      alertOk('保存成功', '支付方式已保存')
      await loadPaymentMethods()
    } else {
      methodError.value = data.message || '保存失败'
    }
  } catch (e) {
    methodError.value = e.message || '保存失败'
  } finally {
    savingMethod.value = false
  }
}
async function deleteMethod(code) {
  if (!(await confirmDialog('确认删除', `确定删除支付方式「${code}」吗？此操作不可恢复。`))) return
  try {
    const data = await callRawAPI(`/api/admin/payment_methods/${encodeURIComponent(code)}`, 'DELETE')
    if (data.success !== false) { alertOk('已删除', '支付方式已删除'); await loadPaymentMethods() }
    else alertErr('删除失败', data.message || '删除失败')
  } catch (e) { alertErr('删除失败', e.message) }
}

// ==================== Tab 2: 订单查询 ====================
const queryTradeNo = ref('')
const querying = ref(false)
const queryResult = ref(null)
const queryError = ref('')
async function queryOrder() {
  if (!queryTradeNo.value.trim()) { queryError.value = '请输入订单号'; return }
  querying.value = true; queryError.value = ''; queryResult.value = null
  try {
    const data = await callRawAPI('/api/payment/query', 'POST', { order_id: queryTradeNo.value.trim() })
    if (data.success !== false) queryResult.value = data.order || data
    else queryError.value = data.message || '查询失败'
  } catch (e) { queryError.value = e.message || '查询失败' } finally { querying.value = false }
}

const orders = ref([])
const ordersLoading = ref(false)
const filters = reactive({ status: '', paytype: '', username: '', orderno: '' })
async function loadOrders() {
  ordersLoading.value = true
  try {
    const data = await callRawAPI('/api/admin/payment/local_orders', 'GET')
    const list = data.orders || data.data || []
    list.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
    orders.value = list
  } catch (e) { alertErr('加载失败', e.message || '加载订单失败'); orders.value = [] } finally { ordersLoading.value = false }
}
const filteredOrders = computed(() => orders.value.filter((o) => {
  if (filters.status && o.status !== filters.status) return false
  if (filters.paytype && o.pay_type !== filters.paytype) return false
  if (filters.username && !String(o.username || '').includes(filters.username)) return false
  if (filters.orderno) {
    const k = filters.orderno
    if (!String(o.order_id || '').includes(k) && !String(o.trade_no || '').includes(k) && !String(o.api_trade_no || '').includes(k)) return false
  }
  return true
}))

const manualQueryNo = ref('')
const manualQuerying = ref(false)
async function manualQuery() {
  if (!manualQueryNo.value.trim()) { alertErr('提示', '请输入订单号'); return }
  manualQuerying.value = true
  try {
    const data = await callRawAPI('/api/admin/payment/query_order', 'POST', { order_id: manualQueryNo.value.trim() })
    if (data.success !== false) { alertOk('查询成功', data.source ? `来源：${data.source}` : '已更新本地订单'); manualQueryNo.value = ''; await loadOrders() }
    else alertErr('查询失败', data.message || '查询失败')
  } catch (e) { alertErr('查询失败', e.message) } finally { manualQuerying.value = false }
}

const fetching = ref(false)
async function fetchFromPlatform() {
  fetching.value = true
  try {
    const data = await callRawAPI('/api/admin/payment/fetch_orders', 'POST', { offset: 0, limit: 50 })
    if (data.success !== false) { alertOk('拉取完成', `获取 ${data.fetched ?? 0} 条，保存 ${data.saved ?? 0} 条，失败 ${data.failed ?? 0} 条`); await loadOrders() }
    else alertErr('拉取失败', data.message || '拉取失败')
  } catch (e) { alertErr('拉取失败', e.message) } finally { fetching.value = false }
}

const selectedOrder = ref(null)
const showOrderModal = ref(false)
function showOrderDetail(o) { selectedOrder.value = o; showOrderModal.value = true }
function detailRows(o) {
  if (!o) return []
  return [
    ['订单号', o.order_id],
    ['交易号', o.trade_no],
    ['平台交易号', o.api_trade_no],
    ['状态', statusInfo(o.status).text],
    ['金额', o.amount != null ? `¥${o.amount}` : ''],
    ['支付方式', o.pay_type ? methodLabel(o.pay_type) : ''],
    ['用户', o.username],
    ['买家', o.buyer],
    ['商品名', o.product_name],
    ['创建时间', o.created_at],
    ['支付时间', o.paid_time],
    ['客户端 IP', o.clientip],
    ['退款金额', o.refundmoney],
    ['附加参数', o.param],
    ['来自平台同步', o.synced_from_platform ? '是' : ''],
    ['同步时间', o.synced_time],
  ].filter((r) => r[1] !== undefined && r[1] !== null && r[1] !== '')
}
async function refreshOrderDetailLocal() {
  if (!selectedOrder.value) return
  try {
    const data = await callRawAPI('/api/admin/payment/order_detail', 'POST', { order_id: selectedOrder.value.order_id })
    if (data.success !== false) { selectedOrder.value = data.order || data; await loadOrders() }
  } catch (e) { alertErr('刷新失败', e.message) }
}
async function refreshOrderDetailPlatform() {
  if (!selectedOrder.value) return
  try {
    const data = await callRawAPI('/api/admin/payment/query_order', 'POST', { order_id: selectedOrder.value.order_id })
    if (data.success !== false) { selectedOrder.value = data.order || data; await loadOrders() }
  } catch (e) { alertErr('刷新失败', e.message) }
}
async function copyOrderNo() {
  const t = selectedOrder.value?.order_id || ''
  if (!t) return
  try { await navigator.clipboard.writeText(t); alertOk('已复制', t) } catch (e) { alertErr('复制失败', e.message) }
}

// ==================== Tab 3: 退款 ====================
const refundForm = reactive({ tradeNo: '', amount: '', refundNo: '', reason: '' })
const refunding = ref(false)
const refundResult = ref(null)
const refundError = ref('')
let refundTimer = null
function onRefundTradeNoInput() {
  if (refundTimer) clearTimeout(refundTimer)
  const tradeNo = refundForm.tradeNo.trim()
  if (!tradeNo) { refundForm.amount = ''; return }
  refundTimer = setTimeout(() => autoFillRefundAmount(tradeNo), 500)
}
async function autoFillRefundAmount(tradeNo) {
  if (tradeNo.length < 10) return
  try {
    const data = await callRawAPI(`/api/payment/order_by_tradeno?trade_no=${encodeURIComponent(tradeNo)}`, 'GET')
    const order = data.order || data
    const refunded = parseFloat(order.refundmoney || 0) > 0 || (order.refund_count || 0) >= 1 ||
      (Array.isArray(order.refund_records) && order.refund_records.length > 0) || String(order.status || '').startsWith('refunded')
    if (refunded) { window.Swal?.fire({ icon: 'warning', title: '该订单已退款', text: '无法再次退款' }); refundForm.amount = ''; return }
    const amt = parseFloat(order.amount)
    if (!isNaN(amt)) refundForm.amount = (amt * 0.8).toFixed(2)
  } catch (e) { /* 静默：查询失败不打断输入 */ }
}
function fillRefundNo() { refundForm.refundNo = genRefundNo() }
async function submitRefund() {
  refundError.value = ''; refundResult.value = null
  if (!refundForm.tradeNo.trim()) { refundError.value = '请输入订单号'; return }
  const amt = parseFloat(refundForm.amount)
  if (isNaN(amt) || amt <= 0) { refundError.value = '请输入有效退款金额'; return }
  if (!refundForm.refundNo.trim()) refundForm.refundNo = genRefundNo()
  refunding.value = true
  try {
    const data = await callRawAPI('/api/payment/refund', 'POST', {
      trade_no: refundForm.tradeNo.trim(),
      refund_amount: amt,
      refund_no: refundForm.refundNo.trim(),
      reason: refundForm.reason.trim(),
    })
    if (data.success !== false) {
      refundResult.value = data
      Object.assign(refundForm, { tradeNo: '', amount: '', refundNo: '', reason: '' })
    } else {
      refundError.value = data.message || '退款失败'
    }
  } catch (e) { refundError.value = e.message || '退款失败' } finally { refunding.value = false }
}

// ==================== Tab 4: 测试支付 ====================
const testForm = reactive({ amount: '0.01', productMode: 'manual', productName: '测试商品', quantity: 1, method: 'alipay', payType: 'jump', authCode: '', subOpenid: '', subAppid: '' })
const creatingTest = ref(false)
const testResult = ref(null)
const testError = ref('')
const enabledMethodCodes = computed(() => (enabledMethods.value.length ? enabledMethods.value : Object.keys(paymentMethodDefs.value)))
async function createTestOrder() {
  testError.value = ''; testResult.value = null
  const amt = parseFloat(testForm.amount)
  if (isNaN(amt) || amt <= 0) { testError.value = '请输入有效金额'; return }
  if (testForm.payType === 'scan' && !/^\d{18}$/.test(testForm.authCode.trim())) { testError.value = '付款码需为 18 位数字'; return }
  if (testForm.payType === 'jsapi' && (!testForm.subOpenid.trim() || !testForm.subAppid.trim())) { testError.value = 'JSAPI 需填写 sub_openid 与 sub_appid'; return }
  creatingTest.value = true
  try {
    let productName = testForm.productName
    if (testForm.productMode === 'auto') {
      const pn = await callRawAPI('/api/admin/generate_product_name', 'POST', { quantity: Number(testForm.quantity) || 1 })
      productName = pn.product_name || pn.name || productName
    }
    const body = {
      amount: amt,
      product_name: productName,
      preserve_product_name: true,
      payment_method: testForm.method,
      payment_type: testForm.payType,
      app_host: `${location.protocol}//${location.host}`,
      return_url: location.href,
      device: (typeof window.Get_YiPAi_device === 'function') ? window.Get_YiPAi_device() : '',
      sub_appid: testForm.subAppid,
      sub_openid: testForm.subOpenid,
      auth_code: testForm.authCode,
    }
    const data = await callRawAPI('/api/payment/create', 'POST', body)
    if (data.success !== false) testResult.value = data
    else testError.value = data.message || '创建失败'
  } catch (e) { testError.value = e.message || '创建失败' } finally { creatingTest.value = false }
}
const testPayUrl = computed(() => testResult.value?.pay_url || testResult.value?.payurl || '')
function openTestPayUrl() {
  if (testPayUrl.value) window.open(testPayUrl.value, '_blank', 'noopener,noreferrer')
}

// ==================== Tab 5: 商品名测试 ====================
const productQuantity = ref(1)
const genning = ref(false)
const productTestResult = ref(null)
function byteLen(str) { try { return new Blob([str]).size } catch (e) { return str ? str.length : 0 } }
async function generateProductName() {
  const q = Math.min(9999, Math.max(1, Number(productQuantity.value) || 1))
  genning.value = true
  try {
    const data = await callRawAPI('/api/admin/generate_product_name', 'POST', { quantity: q })
    const name = data.product_name || data.name || ''
    productTestResult.value = { name, length: byteLen(name) }
  } catch (e) { alertErr('生成失败', e.message) } finally { genning.value = false }
}
const batchList = ref([])
const batching = ref(false)
async function batchTest() {
  batching.value = true; batchList.value = []
  const quantities = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
  try {
    for (const q of quantities) {
      try {
        const data = await callRawAPI('/api/admin/generate_product_name', 'POST', { quantity: q })
        const name = data.product_name || data.name || ''
        const bytes = byteLen(name)
        batchList.value.push({ quantity: q, name, bytes, over: bytes > 127 })
      } catch (e) {
        batchList.value.push({ quantity: q, name: '(生成失败)', bytes: 0, over: false })
      }
    }
  } finally {
    batching.value = false
  }
}

// ==================== Tab 6: 易支付配置 ====================
const yipay = reactive({ host: '', pid: '', key: '', product_id: '', app_host: '', pubc_key: '', payment_timeout_minutes: 30, enabled_payment_methods: '' })
const yipayLoading = ref(false)
const yipaySaving = ref(false)
const yipayLoaded = ref(false)
async function loadYiPay() {
  yipayLoading.value = true
  try {
    const data = await callRawAPI('/api/admin/yipay_config', 'GET')
    const c = data.config || data
    yipay.host = c.host || ''
    yipay.pid = c.pid || ''
    yipay.key = c.key || ''
    yipay.product_id = c.product_id || ''
    yipay.app_host = c.app_host || ''
    yipay.pubc_key = c.pubc_key || ''
    yipay.payment_timeout_minutes = c.payment_timeout_minutes ?? 30
    yipay.enabled_payment_methods = Array.isArray(c.enabled_payment_methods) ? c.enabled_payment_methods.join(',') : (c.enabled_payment_methods || '')
    yipayLoaded.value = true
  } catch (e) {
    alertErr('加载失败', e.message || '加载易支付配置失败')
  } finally {
    yipayLoading.value = false
  }
}
async function saveYiPay() {
  if (!yipayLoaded.value) { alertErr('提示', '请先加载配置后再保存'); return }
  const host = yipay.host.replace(/\/+$/, '')
  if (!host || !yipay.pid || !yipay.key || !yipay.pubc_key) { alertErr('保存失败', 'host / pid / key / 平台公钥 均为必填'); return }
  const timeout = Number(yipay.payment_timeout_minutes)
  if (isNaN(timeout) || timeout < 10 || timeout > 3600) { alertErr('保存失败', '支付超时需在 10-3600 分钟之间'); return }
  yipaySaving.value = true
  try {
    const data = await callRawAPI('/api/admin/yipay_config', 'PUT', {
      host,
      pid: yipay.pid,
      key: yipay.key,
      product_id: yipay.product_id,
      app_host: yipay.app_host,
      pubc_key: yipay.pubc_key,
      payment_timeout_minutes: timeout,
      enabled_payment_methods: toArr(yipay.enabled_payment_methods).join(','),
    })
    if (data.success !== false) { yipay.host = host; alertOk('保存成功', '易支付配置已更新') }
    else alertErr('保存失败', data.message || '保存失败')
  } catch (e) { alertErr('保存失败', e.message) } finally { yipaySaving.value = false }
}

onMounted(loadPaymentMethods)
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: linear-gradient(to right, var(--glass), var(--base-color))">
      <h3 class="text-lg font-bold text-[var(--ink)] mb-1">支付设置</h3>
      <p class="text-sm text-[var(--ink-secondary)]">管理支付方式、查询订单、处理退款、测试支付流程以及配置易支付参数。</p>
    </div>

    <TabPanel :tabs="subTabs" :model-value="activeTab" @update:model-value="onTabChange">
      <!-- ============ 支付方式 ============ -->
      <template #config>
        <div class="space-y-4">
          <div class="flex items-center justify-between flex-wrap gap-2">
            <h4 class="text-base font-semibold text-[var(--ink)]">支付方式管理</h4>
            <div class="flex gap-2">
              <button class="btn btn-secondary" :disabled="methodsLoading" @click="loadPaymentMethods">刷新</button>
              <button class="btn btn-secondary" @click="openAddMethod">新增支付方式</button>
              <button class="btn btn-primary" :disabled="savingMethods" @click="saveEnabledMethods">
                {{ savingMethods ? '保存中...' : '保存启用配置' }}
              </button>
            </div>
          </div>

          <div v-if="methodsLoading" class="text-center py-10 text-sm text-[var(--ink-muted)]">加载中...</div>
          <div v-else-if="Object.keys(paymentMethodDefs).length === 0" class="text-center py-10 text-sm text-[var(--ink-muted)]">暂无支付方式</div>
          <div v-else class="space-y-2">
            <div
              v-for="(def, code) in paymentMethodDefs"
              :key="code"
              class="panel p-3 flex items-center gap-3"
            >
              <div class="w-10 h-10 flex-shrink-0 flex items-center justify-center rounded-lg border" :style="{ borderColor: def.borderColor || 'var(--border-color)' }">
                <div v-if="def.svg" class="w-6 h-6 flex items-center justify-center" v-html="sanitizeSvg(def.svg)"></div>
                <img v-else-if="def.image" :src="def.image" class="w-6 h-6 object-contain" alt="" />
                <span v-else class="text-lg">{{ def.icon || '💳' }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-semibold text-[var(--ink)] truncate">{{ def.name || code }}</div>
                <div class="text-xs text-[var(--ink-muted)] truncate">{{ code }}<span v-if="def.description"> · {{ def.description }}</span></div>
              </div>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" class="sr-only peer" :checked="isEnabled(code)" @change="toggleEnabled(code)" />
                <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer peer-checked:bg-[var(--accent)] after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
              </label>
              <button class="btn btn-secondary !py-1.5 !px-3" @click="openEditMethod(code)">编辑</button>
              <button class="btn btn-danger !py-1.5 !px-3" @click="deleteMethod(code)">删除</button>
            </div>
          </div>
        </div>
      </template>

      <!-- ============ 订单查询 ============ -->
      <template #query>
        <div class="space-y-4">
          <!-- 单笔查询 -->
          <div class="panel p-4 space-y-3">
            <h4 class="text-base font-semibold text-[var(--ink)]">单笔订单查询</h4>
            <div class="flex gap-2">
              <input v-model="queryTradeNo" class="input-field flex-1" placeholder="输入订单号 / 交易号" @keyup.enter="queryOrder" />
              <button class="btn btn-primary" :disabled="querying" @click="queryOrder">{{ querying ? '查询中...' : '查询' }}</button>
            </div>
            <div v-if="queryError" class="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">{{ queryError }}</div>
            <div v-if="queryResult" class="rounded-lg border border-[var(--border-color)] p-3 text-sm space-y-1" style="background: var(--glass)">
              <div v-for="row in detailRows(queryResult)" :key="row[0]" class="flex gap-2">
                <span class="text-[var(--ink-muted)] w-24 flex-shrink-0">{{ row[0] }}</span>
                <span class="text-[var(--ink)] break-all">{{ row[1] }}</span>
              </div>
            </div>
          </div>

          <!-- 手动补单 / 平台拉单 -->
          <div class="panel p-4 space-y-3">
            <h4 class="text-base font-semibold text-[var(--ink)]">订单同步</h4>
            <div class="flex gap-2">
              <input v-model="manualQueryNo" class="input-field flex-1" placeholder="订单号（本地无则从平台查询并保存）" />
              <button class="btn btn-secondary" :disabled="manualQuerying" @click="manualQuery">{{ manualQuerying ? '查询中...' : '查询补单' }}</button>
              <button class="btn btn-secondary" :disabled="fetching" @click="fetchFromPlatform">{{ fetching ? '拉取中...' : '平台批量拉单' }}</button>
            </div>
          </div>

          <!-- 本地订单列表 -->
          <div class="panel p-4 space-y-3">
            <div class="flex items-center justify-between flex-wrap gap-2">
              <h4 class="text-base font-semibold text-[var(--ink)]">本地订单（{{ filteredOrders.length }}）</h4>
              <button class="btn btn-secondary !py-1.5 !px-3" :disabled="ordersLoading" @click="loadOrders">刷新</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-2">
              <select v-model="filters.status" class="select-field">
                <option value="">全部状态</option>
                <option value="pending">待支付</option>
                <option value="paid">已支付</option>
                <option value="closed">已关闭</option>
                <option value="refunded_partial">部分退款</option>
                <option value="refunded_full">全额退款</option>
                <option value="failed">失败</option>
              </select>
              <select v-model="filters.paytype" class="select-field">
                <option value="">全部方式</option>
                <option value="alipay">支付宝</option>
                <option value="wxpay">微信支付</option>
                <option value="qqpay">QQ钱包</option>
                <option value="bank">网银</option>
                <option value="unionpay">云闪付</option>
              </select>
              <input v-model="filters.username" class="input-field" placeholder="用户名" />
              <input v-model="filters.orderno" class="input-field" placeholder="订单号" />
            </div>

            <div v-if="ordersLoading" class="text-center py-8 text-sm text-[var(--ink-muted)]">加载中...</div>
            <div v-else-if="filteredOrders.length === 0" class="text-center py-8 text-sm text-[var(--ink-muted)]">暂无订单</div>
            <div v-else class="space-y-2">
              <div
                v-for="(o, idx) in filteredOrders"
                :key="o.order_id || o.trade_no || idx"
                class="rounded-lg border border-[var(--border-color)] p-3 flex items-center gap-3"
                style="background: var(--glass)"
              >
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium text-[var(--ink)] truncate">{{ o.order_id || o.trade_no }}</div>
                  <div class="text-xs text-[var(--ink-muted)] truncate">
                    {{ o.username || '-' }} · {{ o.pay_type ? methodLabel(o.pay_type) : '-' }} · {{ o.created_at || '-' }}
                  </div>
                </div>
                <div class="text-right flex-shrink-0">
                  <div class="text-sm font-semibold text-[var(--ink)]">¥{{ o.amount ?? '-' }}</div>
                  <div class="text-xs" :class="statusInfo(o.status).cls">{{ statusInfo(o.status).text }}</div>
                </div>
                <button class="btn btn-secondary !py-1.5 !px-3" @click="showOrderDetail(o)">查看</button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ============ 退款 ============ -->
      <template #refund>
        <div class="panel p-4 space-y-3 max-w-xl">
          <h4 class="text-base font-semibold text-[var(--ink)]">发起退款</h4>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">订单号</label>
            <input v-model="refundForm.tradeNo" class="input-field" placeholder="输入订单号（自动带出退款金额）" @input="onRefundTradeNoInput" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">退款金额（元）</label>
            <input v-model="refundForm.amount" type="number" min="0" step="0.01" class="input-field" placeholder="默认订单金额的 80%" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">退款单号</label>
            <div class="flex gap-2">
              <input v-model="refundForm.refundNo" class="input-field flex-1" placeholder="留空自动生成" />
              <button class="btn btn-secondary" @click="fillRefundNo">生成</button>
            </div>
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">退款原因</label>
            <input v-model="refundForm.reason" class="input-field" placeholder="选填" />
          </div>
          <button class="btn btn-primary w-full justify-center" :disabled="refunding" @click="submitRefund">
            {{ refunding ? '退款中...' : '提交退款' }}
          </button>
          <div v-if="refundError" class="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">{{ refundError }}</div>
          <div v-if="refundResult" class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] text-sm space-y-1">
            <div class="font-semibold">退款成功</div>
            <div v-if="refundResult.refund_no">退款单号：{{ refundResult.refund_no }}</div>
            <div v-if="refundResult.refund_amount != null">退款金额：¥{{ refundResult.refund_amount }}</div>
            <div v-if="refundResult.message">{{ refundResult.message }}</div>
          </div>
        </div>
      </template>

      <!-- ============ 测试支付 ============ -->
      <template #test>
        <div class="panel p-4 space-y-3 max-w-xl">
          <h4 class="text-base font-semibold text-[var(--ink)]">创建测试订单</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">金额（元）</label>
              <input v-model="testForm.amount" type="number" min="0.01" step="0.01" class="input-field" />
            </div>
            <div>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">支付方式</label>
              <select v-model="testForm.method" class="select-field">
                <option v-for="code in enabledMethodCodes" :key="code" :value="code">{{ methodLabel(code) }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">支付类型</label>
              <select v-model="testForm.payType" class="select-field">
                <option value="jump">跳转 (jump)</option>
                <option value="html">页面 (html)</option>
                <option value="qrcode">二维码 (qrcode)</option>
                <option value="urlscheme">URL Scheme</option>
                <option value="scan">扫码枪 (scan)</option>
                <option value="jsapi">JSAPI</option>
                <option value="app">APP</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">商品名来源</label>
              <select v-model="testForm.productMode" class="select-field">
                <option value="manual">手动输入</option>
                <option value="auto">自动生成</option>
              </select>
            </div>
            <div v-if="testForm.productMode === 'manual'" class="md:col-span-2">
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">商品名</label>
              <input v-model="testForm.productName" class="input-field" />
            </div>
            <div v-else>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">生成数量</label>
              <input v-model.number="testForm.quantity" type="number" min="1" max="9999" class="input-field" />
            </div>
            <div v-if="testForm.payType === 'scan'" class="md:col-span-2">
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">付款码（18 位数字）</label>
              <input v-model="testForm.authCode" class="input-field" placeholder="扫码枪读取的付款码" />
            </div>
            <template v-if="testForm.payType === 'jsapi'">
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">sub_openid</label>
                <input v-model="testForm.subOpenid" class="input-field" />
              </div>
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">sub_appid</label>
                <input v-model="testForm.subAppid" class="input-field" />
              </div>
            </template>
          </div>
          <button class="btn btn-primary w-full justify-center" :disabled="creatingTest" @click="createTestOrder">
            {{ creatingTest ? '创建中...' : '创建测试订单' }}
          </button>
          <div v-if="testError" class="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">{{ testError }}</div>
          <div v-if="testResult" class="rounded-lg border border-[var(--border-color)] p-3 text-sm space-y-2" style="background: var(--glass)">
            <div class="font-semibold text-[var(--ink)]">订单创建成功</div>
            <div v-if="testResult.order_id" class="flex gap-2"><span class="text-[var(--ink-muted)] w-20">订单号</span><span class="break-all">{{ testResult.order_id }}</span></div>
            <div v-if="testResult.trade_no" class="flex gap-2"><span class="text-[var(--ink-muted)] w-20">交易号</span><span class="break-all">{{ testResult.trade_no }}</span></div>
            <div v-if="testResult.amount != null" class="flex gap-2"><span class="text-[var(--ink-muted)] w-20">金额</span><span>¥{{ testResult.amount }}</span></div>
            <div v-if="testResult.pay_type" class="flex gap-2"><span class="text-[var(--ink-muted)] w-20">支付类型</span><span>{{ testResult.pay_type }}</span></div>
            <div v-if="testPayUrl">
              <label class="block text-[var(--ink-muted)] mb-1">支付链接 / 信息</label>
              <textarea :value="testPayUrl" rows="3" readonly class="input-field font-mono text-xs"></textarea>
              <button class="btn btn-secondary mt-2" @click="openTestPayUrl">打开支付链接</button>
            </div>
          </div>
        </div>
      </template>

      <!-- ============ 商品名测试 ============ -->
      <template #product-test>
        <div class="space-y-4">
          <div class="panel p-4 space-y-3 max-w-xl">
            <h4 class="text-base font-semibold text-[var(--ink)]">生成趣味商品名</h4>
            <div class="flex gap-2">
              <input v-model.number="productQuantity" type="number" min="1" max="9999" class="input-field flex-1" placeholder="数量" />
              <button class="btn btn-primary" :disabled="genning" @click="generateProductName">{{ genning ? '生成中...' : '生成' }}</button>
            </div>
            <div v-if="productTestResult" class="rounded-lg border border-[var(--border-color)] p-3 text-sm" style="background: var(--glass)">
              <div class="text-[var(--ink)] break-all">{{ productTestResult.name }}</div>
              <div class="text-xs mt-1" :class="productTestResult.length > 127 ? 'text-red-500' : 'text-[var(--ink-muted)]'">字节数：{{ productTestResult.length }}{{ productTestResult.length > 127 ? '（超出 127 限制）' : '' }}</div>
            </div>
          </div>

          <div class="panel p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h4 class="text-base font-semibold text-[var(--ink)]">批量长度测试</h4>
              <button class="btn btn-secondary !py-1.5 !px-3" :disabled="batching" @click="batchTest">{{ batching ? '测试中...' : '开始批量测试' }}</button>
            </div>
            <div v-if="batchList.length" class="space-y-1">
              <div v-for="item in batchList" :key="item.quantity" class="flex items-center gap-3 text-sm rounded-lg border border-[var(--border-color)] p-2" style="background: var(--glass)">
                <span class="w-16 flex-shrink-0 text-[var(--ink-muted)]">×{{ item.quantity }}</span>
                <span class="flex-1 break-all text-[var(--ink)]">{{ item.name }}</span>
                <span class="flex-shrink-0 text-xs" :class="item.over ? 'text-red-500' : 'text-[var(--ink-muted)]'">{{ item.bytes }}B</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ============ 易支付配置 ============ -->
      <template #yipay>
        <div class="panel p-4 space-y-3 max-w-xl">
          <div class="flex items-center justify-between">
            <h4 class="text-base font-semibold text-[var(--ink)]">易支付参数配置</h4>
            <button class="btn btn-secondary !py-1.5 !px-3" :disabled="yipayLoading" @click="loadYiPay">{{ yipayLoading ? '加载中...' : '刷新' }}</button>
          </div>
          <div v-if="yipayLoading" class="text-center py-8 text-sm text-[var(--ink-muted)]">加载中...</div>
          <template v-else>
            <div>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">接口地址 host</label>
              <input v-model="yipay.host" class="input-field" placeholder="https://pay.example.com" />
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">商户 PID</label>
                <input v-model="yipay.pid" class="input-field" />
              </div>
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">商户密钥 key</label>
                <input v-model="yipay.key" type="password" class="input-field" />
              </div>
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">产品 ID</label>
                <input v-model="yipay.product_id" class="input-field" />
              </div>
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">回调 app_host</label>
                <input v-model="yipay.app_host" class="input-field" />
              </div>
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">支付超时（分钟，10-3600）</label>
                <input v-model.number="yipay.payment_timeout_minutes" type="number" min="10" max="3600" class="input-field" />
              </div>
              <div>
                <label class="block text-sm text-[var(--ink-secondary)] mb-1">启用支付方式（逗号分隔）</label>
                <input v-model="yipay.enabled_payment_methods" class="input-field" placeholder="alipay,wxpay" />
              </div>
            </div>
            <div>
              <label class="block text-sm text-[var(--ink-secondary)] mb-1">平台公钥 pubc_key</label>
              <textarea v-model="yipay.pubc_key" rows="4" class="input-field font-mono text-xs"></textarea>
            </div>
            <button class="btn btn-primary w-full justify-center" :disabled="yipaySaving || !yipayLoaded" @click="saveYiPay">
              {{ yipaySaving ? '保存中...' : '保存易支付配置' }}
            </button>
          </template>
        </div>
      </template>
    </TabPanel>

    <!-- 支付方式新增/编辑 弹窗 -->
    <div v-if="showMethodModal" class="modal-backdrop flex items-center justify-center p-4" @click.self="showMethodModal = false">
      <div class="modal-content w-full max-w-lg p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-[var(--ink)]">{{ methodModalMode === 'edit' ? '编辑支付方式' : '新增支付方式' }}</h3>
          <button class="text-[var(--ink-muted)] hover:text-[var(--ink)]" @click="showMethodModal = false">&times;</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">方式代码</label>
            <input v-model="methodForm.code" class="input-field" :disabled="methodModalMode === 'edit'" placeholder="alipay" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">名称</label>
            <input v-model="methodForm.name" class="input-field" placeholder="支付宝" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">Logo 类型</label>
            <select v-model="methodForm.logoType" class="select-field">
              <option value="svg">SVG 代码</option>
              <option value="image">图片地址</option>
            </select>
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">图标 icon（可选 emoji）</label>
            <input v-model="methodForm.icon" class="input-field" placeholder="💳" />
          </div>
          <div v-if="methodForm.logoType === 'svg'" class="md:col-span-2">
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">SVG 代码</label>
            <textarea v-model="methodForm.svg" rows="3" class="input-field font-mono text-xs" placeholder="<svg ...></svg>"></textarea>
          </div>
          <div v-else class="md:col-span-2">
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">图片地址</label>
            <input v-model="methodForm.image" class="input-field" placeholder="https://.../logo.png" />
          </div>
          <div class="md:col-span-2">
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">描述</label>
            <input v-model="methodForm.description" class="input-field" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">边框颜色</label>
            <input v-model="methodForm.borderColor" class="input-field" placeholder="#1677ff" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">文字颜色</label>
            <input v-model="methodForm.textColor" class="input-field" placeholder="#1677ff" />
          </div>
        </div>
        <div v-if="methodError" class="p-3 rounded-lg bg-red-500/10 text-red-500 text-sm">{{ methodError }}</div>
        <div class="flex justify-end gap-2">
          <button class="btn btn-secondary" @click="showMethodModal = false">取消</button>
          <button class="btn btn-primary" :disabled="savingMethod" @click="saveMethod">{{ savingMethod ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 订单详情 弹窗 -->
    <div v-if="showOrderModal" class="modal-backdrop flex items-center justify-center p-4" @click.self="showOrderModal = false">
      <div class="modal-content w-full max-w-lg p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-[var(--ink)]">订单详情</h3>
          <button class="text-[var(--ink-muted)] hover:text-[var(--ink)]" @click="showOrderModal = false">&times;</button>
        </div>
        <div class="text-sm space-y-1 max-h-[50vh] overflow-y-auto">
          <div v-for="row in detailRows(selectedOrder)" :key="row[0]" class="flex gap-2">
            <span class="text-[var(--ink-muted)] w-24 flex-shrink-0">{{ row[0] }}</span>
            <span class="text-[var(--ink)] break-all">{{ row[1] }}</span>
          </div>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <button class="btn btn-secondary" @click="copyOrderNo">复制订单号</button>
          <button class="btn btn-secondary" @click="refreshOrderDetailLocal">刷新本地</button>
          <button class="btn btn-primary" @click="refreshOrderDetailPlatform">从平台刷新</button>
        </div>
      </div>
    </div>
  </div>
</template>
