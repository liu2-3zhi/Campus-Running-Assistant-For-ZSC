/**
 * usePayment.js —— 用户端支付 / 欠费拦截 / 账单支付 核心逻辑
 *
 * 复刻 original（scripts/main.new.js 58933–62148 用户端 + 63610–64769 账单支付）：
 *   - 创建订单 / 查询订单 / 订单轮询状态机（3s×20）
 *   - 支付页轮询状态机（2s×600）与二维码
 *   - 欠费检查（/api/check_overdue）+ 欠费待支付账单选择弹窗
 *   - 账单支付流程（选择支付方式 → 创建账单订单 → 轮询）
 *
 * 权威依据：docs/original-analysis/24-JS-易支付与账单.md §2 / §4 / §7。
 * 所有网络请求走 @/services/api 的 callRawAPI（自动带 X-Session-ID）。
 * 二维码库运行时动态加载 /api/cdn/qrcode（失败回退 jsdelivr），不改 package.json。
 */
import { callRawAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { sanitizeSvg } from '@/utils/sanitizeSvg'

/* ============================================================================
 * 常量与工具
 * ==========================================================================*/

// 订单卡片支付方式文本（§2.9）
export const ORDER_PAYTYPE_TEXT = { alipay: '支付宝', wxpay: '微信支付', bank: '网银支付' }
// 支付页支付方式名称 fallback（§4.8）
export const METHOD_NAME_FALLBACK = { alipay: '支付宝', wxpay: '微信', qqpay: 'QQ钱包', bank: '网银', unionpay: '云闪付' }

// 订单状态徽章（§2.9）
export const ORDER_STATUS_CONFIG = {
  pending: { text: '待支付', cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  paid: { text: '已支付', cls: 'bg-green-50 text-green-700 border-green-200' },
  closed: { text: '已关闭', cls: 'bg-slate-50 text-slate-700 border-slate-200' },
}
export function orderStatusInfo(status) {
  return ORDER_STATUS_CONFIG[status] || { text: '未知', cls: 'bg-slate-50 text-slate-700 border-slate-200' }
}
export function orderPayTypeText(payType) {
  return ORDER_PAYTYPE_TEXT[payType] || payType || '未知'
}

// 账单状态语义（附录 C）
export const BILLING_STATUS_CONFIG = {
  pending: { label: '待支付', icon: '⏳', cls: 'bg-amber-100 text-amber-700' },
  paid: { label: '已支付', icon: '✓', cls: 'bg-green-100 text-green-700' },
  closed: { label: '已关闭', icon: '⛔', cls: 'bg-slate-100 text-slate-600' },
  refunded_partial: { label: '部分退款', icon: '↩', cls: 'bg-orange-100 text-orange-700' },
  refunded_full: { label: '全额退款', icon: '↩', cls: 'bg-rose-100 text-rose-700' },
  admin_cleared: { label: '管理员清除', icon: '✓', cls: 'bg-sky-100 text-sky-700' },
}
export function billingStatusInfo(status) {
  return BILLING_STATUS_CONFIG[status] || { label: status || '未知', icon: '•', cls: 'bg-gray-100 text-gray-600' }
}
// 可支付判定：pending 或 closed（§7.0 isBillingStatusPayable）
export function isBillingStatusPayable(status) {
  return status === 'pending' || status === 'closed'
}

function getSwal() {
  return typeof window !== 'undefined' ? window.Swal : null
}

// 易支付设备类型探测（original 为全局 Get_YiPAi_device）
export function getYiPaiDevice() {
  try {
    if (typeof window !== 'undefined' && typeof window.Get_YiPAi_device === 'function') {
      return window.Get_YiPAi_device()
    }
  } catch (_) { /* ignore */ }
  return ''
}

export function escapeHtml(v) {
  if (v == null) return ''
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// 时间格式化（§7.0 _fmtBillTime）：legacy UTC(...Z) → 北京时间(+8h)，否则去 T/Z/+08:00
export function fmtBillTime(v) {
  if (!v) return ''
  const s = String(v)
  if (/Z$/.test(s) && !/\+08:00/.test(s)) {
    const d = new Date(s)
    if (!isNaN(d.getTime())) {
      const bj = new Date(d.getTime() + 8 * 3600 * 1000)
      return bj.toISOString().replace('T', ' ').replace(/\.\d+Z$/, '').replace('Z', '')
    }
  }
  return s.replace('T', ' ').replace('Z', '').replace('+08:00', '')
}
export function getBillingTime(record, key) {
  if (!record) return ''
  return record[key + '_beijing'] || fmtBillTime(record[key])
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

/* ============================================================================
 * 二维码库动态加载（技术约束：不装 qrcode，运行时加载 CDN）
 * ==========================================================================*/
let _qrcodePromise = null
export function ensureQRCode() {
  if (typeof window !== 'undefined' && window.QRCode) return Promise.resolve(window.QRCode)
  if (_qrcodePromise) return _qrcodePromise
  _qrcodePromise = new Promise((resolve) => {
    const finish = () => resolve((typeof window !== 'undefined' && window.QRCode) || null)
    const existing = document.getElementById('qrcode-cdn-script')
    if (existing) {
      if (window.QRCode) return finish()
      existing.addEventListener('load', finish)
      existing.addEventListener('error', finish)
      return
    }
    const primary = document.createElement('script')
    primary.id = 'qrcode-cdn-script'
    primary.src = '/api/cdn/qrcode'
    primary.onload = finish
    primary.onerror = () => {
      // 回退 jsdelivr
      const fallback = document.createElement('script')
      fallback.src = 'https://cdn.jsdelivr.net/npm/qrcode/build/qrcode.min.js'
      fallback.onload = finish
      fallback.onerror = finish
      document.head.appendChild(fallback)
    }
    document.head.appendChild(primary)
  })
  return _qrcodePromise
}

/* ============================================================================
 * 基础订单 API（§2.3 / §2.4 / §2.8）
 * ==========================================================================*/
export async function verifyHost(appHost) {
  try {
    return await callRawAPI('/api/payment/verify_host', 'POST', { app_host: appHost })
  } catch (e) {
    return { success: false, message: e.message || '域名验证失败' }
  }
}

export async function createPaymentOrderRequest(body) {
  try {
    return await callRawAPI('/api/payment/create', 'POST', body)
  } catch (e) {
    return { success: false, message: e.message || '创建订单失败' }
  }
}

export async function queryOrderStatus(orderId) {
  if (!orderId) return { success: false, message: '订单号不能为空' }
  try {
    return await callRawAPI('/api/payment/query', 'POST', { order_id: orderId })
  } catch (e) {
    return { success: false, message: e.message || '查询订单状态失败' }
  }
}

export async function fetchPaymentOrders(status, page, perPage = 10) {
  let url = `/api/payment/orders?page=${page}&per_page=${perPage}`
  if (status && status !== 'all') url += `&status=${status}`
  try {
    return await callRawAPI(url, 'GET')
  } catch (e) {
    return { success: false, message: e.message || '加载订单失败' }
  }
}

/* ============================================================================
 * 订单轮询状态机（§2.5：3000ms × 20，单例定时器，复刻全局 paymentPollingTimer）
 * ==========================================================================*/
let _orderPollingTimer = null
let _orderPollingCount = 0

export function stopOrderPolling() {
  if (_orderPollingTimer) {
    clearInterval(_orderPollingTimer)
    _orderPollingTimer = null
  }
  _orderPollingCount = 0
}

export function startOrderPolling(orderId, { onPaid } = {}) {
  stopOrderPolling()
  _orderPollingCount = 0
  const Swal = getSwal()
  _orderPollingTimer = setInterval(async () => {
    _orderPollingCount++
    const result = await queryOrderStatus(orderId)
    if (result && result.success) {
      if (result.status === 'paid') {
        stopOrderPolling()
        Swal?.fire({ icon: 'success', title: '支付成功', text: '订单已支付，感谢您的支持！', confirmButtonText: '确定' })
        try { onPaid && onPaid(result) } catch (_) { /* ignore */ }
        return
      }
      if (result.status === 'closed') {
        stopOrderPolling()
        Swal?.fire({ icon: 'info', title: '订单已关闭', text: '订单已被关闭或取消', confirmButtonText: '确定' })
        return
      }
    }
    if (_orderPollingCount >= 20) {
      stopOrderPolling()
      Swal?.fire({ icon: 'warning', title: '查询超时', text: '订单状态查询超时，请稍后在"我的订单"中手动查询', confirmButtonText: '确定' })
    }
  }, 3000)
}

/* 继续支付（§2.11）：查询订单 → 打开支付页 → 启动轮询 */
export async function continuePay(orderId, { onPaid } = {}) {
  const Swal = getSwal()
  try {
    const result = await queryOrderStatus(orderId)
    if (!result.success) {
      Swal?.fire({ icon: 'error', title: '错误', text: result.message || '查询订单失败', confirmButtonText: '确定' })
      return
    }
    if (result.status !== 'pending') {
      Swal?.fire({ icon: 'info', title: '提示', text: '该订单不是待支付状态', confirmButtonText: '确定' })
      return
    }
    const payUrl = result.order && result.order.pay_url
    if (payUrl) window.open(payUrl, '_blank')
    startOrderPolling(orderId, { onPaid })
    Swal?.fire({ icon: 'info', title: '提示', text: '请在新打开的页面完成支付', confirmButtonText: '确定', timer: 2000 })
  } catch (e) {
    Swal?.fire({ icon: 'error', title: '错误', text: '操作失败，请稍后重试', confirmButtonText: '确定' })
  }
}

/* 刷新单订单状态（§2.12） */
export async function refreshOrderStatus(orderId) {
  const Swal = getSwal()
  try {
    Swal?.fire({ title: '查询中...', text: '正在查询订单状态', allowOutsideClick: false, didOpen: () => Swal.showLoading() })
    const result = await queryOrderStatus(orderId)
    Swal?.close()
    if (!result.success) {
      Swal?.fire({ icon: 'error', title: '查询失败', text: result.message || '查询订单状态失败', confirmButtonText: '确定' })
      return result
    }
    const map = {
      paid: { title: '订单已支付', icon: 'success' },
      pending: { title: '订单待支付', icon: 'info' },
      closed: { title: '订单已关闭', icon: 'warning' },
    }
    const cfg = map[result.status] || { title: '订单状态未知', icon: 'question' }
    Swal?.fire({ icon: cfg.icon, title: cfg.title, text: `订单号：${orderId}`, confirmButtonText: '确定' })
    return result
  } catch (e) {
    Swal?.close()
    Swal?.fire({ icon: 'error', title: '错误', text: '查询失败，请稍后重试', confirmButtonText: '确定' })
    return { success: false }
  }
}

/* ============================================================================
 * 支付页轮询状态机（§4.8 showPaymentPageWithPolling：2000ms × 600，含二维码）
 * ==========================================================================*/
export async function showPaymentPageWithPolling(orderId, payUrl, totalAmount, paymentMethod, payType) {
  const Swal = getSwal()
  if (!Swal) { window.open(payUrl, '_blank'); return }

  // 支付方式名称映射
  let names = {}
  try {
    const cfg = await callRawAPI('/api/payment/methods_config', 'GET')
    if (cfg && cfg.success && Array.isArray(cfg.methods)) {
      cfg.methods.forEach((m) => { if (m && m.code) names[m.code] = m.name })
    }
  } catch (_) { /* ignore */ }
  if (Object.keys(names).length === 0) names = { ...METHOD_NAME_FALLBACK }
  const methodName = names[paymentMethod] || paymentMethod || ''

  let pollingInterval = null
  let pollingCount = 0
  const maxPollingCount = 600

  const isQr = payType === 'qrcode'
  const qrBlock = isQr
    ? `<div id="payment-qrcode-container" style="margin-bottom:20px;padding:15px;background:white;border-radius:8px;">
         <div style="color:#64748b;font-size:13px;margin-bottom:10px;">请扫描二维码支付</div>
         <canvas id="payment-qrcode-canvas" style="display:block;margin:0 auto;"></canvas>
         <div id="payment-qrcode-fallback" style="display:none;font-size:12px;color:#475569;margin-top:8px;">
           二维码加载失败，请点击链接支付
         </div>
       </div>`
    : ''
  const linkBlock = !isQr
    ? `<div style="margin-bottom:20px;">
         <a href="${escapeHtml(payUrl)}" target="_blank" rel="noopener noreferrer"
            style="display:inline-block;padding:12px 40px;background:#3b82f6;color:white;text-decoration:none;border-radius:8px;font-weight:600;">
           🔗 打开支付页面
         </a>
       </div>`
    : ''

  function updatePaymentStatus(status, message) {
    const indicator = document.getElementById('payment-status-indicator')
    if (!indicator) return
    const cfg = {
      success: { background: '#dcfce7', border: '#22c55e', color: '#14532d', icon: '✅' },
      failed: { background: '#fee2e2', border: '#ef4444', color: '#7f1d1d', icon: '❌' },
      timeout: { background: '#f3f4f6', border: '#9ca3af', color: '#1f2937', icon: '⏱️' },
    }[status] || { background: '#fee2e2', border: '#ef4444', color: '#7f1d1d', icon: '❌' }
    indicator.style.background = cfg.background
    indicator.style.borderColor = cfg.border
    indicator.style.color = cfg.color
    indicator.innerHTML = `<div style="font-size:16px;font-weight:600;">${cfg.icon} ${escapeHtml(message)}</div>`
  }

  await Swal.fire({
    title: '请完成支付',
    icon: 'info',
    html: `
      <div style="text-align:center;">
        <div style="margin-bottom:20px;">
          <div style="color:#64748b;font-size:14px;margin-bottom:5px;">订单号</div>
          <div style="font-family:monospace;font-size:13px;color:#475569;background:#f1f5f9;padding:8px;border-radius:6px;word-break:break-all;">${escapeHtml(orderId)}</div>
        </div>
        <div style="padding:15px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:10px;margin-bottom:20px;">
          <div style="color:rgba(255,255,255,0.9);font-size:13px;">支付方式：${escapeHtml(methodName)}</div>
          <div style="color:white;font-size:28px;font-weight:bold;margin-top:5px;">¥${escapeHtml(totalAmount)}</div>
        </div>
        <div style="margin-bottom:15px;padding:10px;background:#f8fafc;border-radius:6px;">
          <div style="color:#64748b;font-size:12px;margin-bottom:5px;">支付链接</div>
          <div style="font-family:monospace;font-size:11px;color:#475569;word-break:break-all;max-height:60px;overflow-y:auto;">${escapeHtml(payUrl)}</div>
        </div>
        ${qrBlock}
        ${linkBlock}
        <div id="payment-status-indicator" style="padding:15px;background:#fef3c7;border:2px solid #fbbf24;border-radius:8px;color:#92400e;font-size:14px;">
          <div style="display:flex;align-items:center;justify-content:center;">
            <div style="width:20px;height:20px;border:3px solid #fbbf24;border-top-color:transparent;border-radius:50%;animation:usePaymentSpin 1s linear infinite;margin-right:10px;"></div>
            <span>正在等待支付...</span>
          </div>
          <div style="margin-top:8px;font-size:12px;color:#78350f;">系统正在实时检测支付状态</div>
        </div>
      </div>
      <style>@keyframes usePaymentSpin{to{transform:rotate(360deg);}}</style>`,
    showCancelButton: true,
    showConfirmButton: false,
    cancelButtonText: '取消支付',
    cancelButtonColor: '#94a3b8',
    allowOutsideClick: false,
    allowEscapeKey: false,
    width: '550px',
    didOpen: async () => {
      if (isQr) {
        try {
          await new Promise((r) => setTimeout(r, 100))
          const canvas = document.getElementById('payment-qrcode-canvas')
          const QR = await ensureQRCode()
          if (canvas && QR && typeof QR.toCanvas === 'function') {
            await QR.toCanvas(canvas, payUrl, { width: 200, height: 200, margin: 2, color: { dark: '#000000', light: '#ffffff' } })
          } else {
            // 降级：显示可点击链接
            const fb = document.getElementById('payment-qrcode-fallback')
            if (fb) {
              fb.style.display = 'block'
              fb.innerHTML = `<a href="${escapeHtml(payUrl)}" target="_blank" rel="noopener noreferrer" style="color:#3b82f6;">🔗 打开支付页面</a>`
            }
          }
        } catch (e) {
          console.error('[支付二维码] 生成失败:', e)
        }
      }

      pollingInterval = setInterval(async () => {
        pollingCount++
        if (pollingCount > maxPollingCount) {
          clearInterval(pollingInterval)
          updatePaymentStatus('timeout', '支付超时，请重新发起支付')
          return
        }
        try {
          const queryResult = await callRawAPI('/api/payment/query', 'POST', { order_id: orderId })
          if (queryResult.success && queryResult.order) {
            const st = queryResult.order.status
            if (st === 'paid' || st === 'completed') {
              clearInterval(pollingInterval)
              updatePaymentStatus('success', '支付成功！')
              setTimeout(async () => {
                Swal.close()
                await Swal.fire({ title: '支付成功！', text: '欠费已清零，感谢您的支付', icon: 'success', confirmButtonText: '确定' })
              }, 1000)
            } else if (st === 'failed' || st === 'closed') {
              clearInterval(pollingInterval)
              updatePaymentStatus('failed', '支付失败')
            }
          }
        } catch (e) {
          console.error('查询订单状态失败:', e)
        }
      }, 2000)
    },
    willClose: () => {
      if (pollingInterval) clearInterval(pollingInterval)
    },
  })
}

/* ============================================================================
 * 欠费检查（§4.1 / §4.2 / §4.5）
 * ==========================================================================*/
let _requirePaymentCache = { value: null, ts: 0 }

export async function isPaymentRequiredForOverdueCheck() {
  const now = Date.now()
  if (_requirePaymentCache.value !== null && now - _requirePaymentCache.ts < 30 * 1000) {
    return _requirePaymentCache.value
  }
  try {
    const result = await callRawAPI('/api/config/pricing', 'GET')
    if (result && result.success && result.config && typeof result.config.require_payment !== 'undefined') {
      const enabled = result.config.require_payment === true || String(result.config.require_payment).toLowerCase() === 'true'
      _requirePaymentCache = { value: enabled, ts: now }
      return enabled
    }
  } catch (e) {
    console.warn('[欠费检查] 获取 require_payment 配置失败，回退默认开启', e)
  }
  // Vue 版无 #pricing-require-payment_modal，回退默认开启（与 original 缺省一致）
  return true
}

/**
 * 欠费检查（§4.1）
 * @param {null|string|string[]} schoolUsernameOrList
 * @returns {Promise<boolean>} true=允许继续；false=有欠费已弹窗，阻止开始
 */
export async function checkOverdueBeforeStart(schoolUsernameOrList = null) {
  const Swal = getSwal()
  try {
    const body = {}
    if (typeof schoolUsernameOrList === 'string') {
      body.school_username = schoolUsernameOrList
    } else if (Array.isArray(schoolUsernameOrList) && schoolUsernameOrList.length > 0) {
      body.school_usernames = schoolUsernameOrList
    }
    const result = await callRawAPI('/api/check_overdue', 'POST', body)
    if (!result.success) {
      Swal?.fire({ icon: 'error', title: '错误', text: result.message || '欠费检查失败', confirmButtonText: '确定' })
      return true // 容错不阻塞
    }
    if (result.has_overdue) {
      await showOverduePaymentModal(result.overdue_accounts)
      return false
    }
    return true
  } catch (e) {
    console.error('检查欠费失败:', e)
    return true // 容错不阻塞
  }
}

function collectMultiAccountUsernames() {
  const usernames = new Set()
  // 优先复刻 original：DOM 中的 [data-username]
  if (typeof document !== 'undefined') {
    ;['multi-account-list', 'mobile-multi-account-list'].forEach((id) => {
      const container = document.getElementById(id)
      if (!container) return
      container.querySelectorAll('[data-username]').forEach((el) => {
        const u = (el.dataset.username || '').trim()
        if (u) usernames.add(u)
      })
    })
  }
  // 回退：从 app store 的多账号用户列表推导
  if (usernames.size === 0) {
    try {
      const app = useAppStore()
      const list = app.users || app.accounts || []
      if (Array.isArray(list)) {
        list.forEach((u) => {
          const v = String(u.school_username || u.student_id || u.username || '').trim()
          if (v) usernames.add(v)
        })
      }
    } catch (_) { /* ignore */ }
  }
  return Array.from(usernames)
}

function isMultiAccountMode() {
  try {
    const app = useAppStore()
    if (app.isMultiMode) return true
  } catch (_) { /* ignore */ }
  if (typeof window !== 'undefined' && window.mobileAdminPanelMode === 'multi') return true
  return false
}

/**
 * 按当前模式发起欠费检查（§4.5）——供 ControlTabs startRun/startAll 前置调用
 */
export async function checkOverdueBeforeStartByCurrentMode() {
  if (!(await isPaymentRequiredForOverdueCheck())) return true
  if (isMultiAccountMode()) {
    const usernames = collectMultiAccountUsernames()
    return usernames.length > 0 ? await checkOverdueBeforeStart(usernames) : true
  }
  let sid = ''
  try {
    const auth = useAuthStore()
    sid = String(auth.studentId || '').trim()
  } catch (_) { /* ignore */ }
  return sid ? await checkOverdueBeforeStart(sid) : await checkOverdueBeforeStart()
}

/* ============================================================================
 * 账单列表 / 欠费待支付账单选择弹窗（§4.6 / §7.1）
 * ==========================================================================*/
export async function fetchBillingList(schoolUsername = '') {
  let url = '/api/billing/list'
  if (schoolUsername) url += `?school_username=${encodeURIComponent(schoolUsername)}`
  try {
    return await callRawAPI(url, 'GET')
  } catch (e) {
    return { success: false, message: e.message || '加载账单失败', records: [] }
  }
}

/**
 * 欠费账号待支付账单选择弹窗（§4.6）——勾选后进入账单合并支付流程
 */
export async function showOverduePaymentModal(overdueAccounts) {
  const Swal = getSwal()
  if (!Swal) return

  Swal.fire({ title: '正在获取欠费账单', allowOutsideClick: false, didOpen: () => Swal.showLoading() })

  const overdueSet = new Set(
    (overdueAccounts || [])
      .map((a) => a.school_username || a.username || '')
      .filter(Boolean),
  )

  let pendingBills = []
  try {
    const result = await fetchBillingList()
    if (result.success) {
      pendingBills = (result.records || []).filter(
        (r) => r.status === 'pending' && overdueSet.has(r.school_username),
      )
    }
  } catch (e) {
    console.warn('[showOverduePaymentModal] 获取账单失败:', e)
  }

  Swal.close()

  if (!pendingBills.length) {
    await Swal.fire({
      title: '暂无待支付账单',
      text: '未找到对应的待支付账单记录，请联系管理员确认。',
      icon: 'info',
      confirmButtonText: '确定',
    })
    return
  }

  const totalAmount = pendingBills
    .reduce((s, r) => s + (parseFloat(r.amount) || 0), 0)
    .toFixed(2)

  const isMobile = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 767px)').matches

  const updateTotal = `document.getElementById('overdue-total-amount').textContent='¥'+[...document.querySelectorAll('[data-overdue-bill-select]')].filter(c=>c.checked).reduce((s,c)=>s+parseFloat(c.dataset.amount||0),0).toFixed(2);`

  let bodyHtml, modalWidth
  if (isMobile) {
    const cardsHtml = pendingBills.map((r, idx) => {
      const safeId = escapeHtml(r.billing_id || '')
      const safeSchool = escapeHtml(r.school_username || '-')
      const safeName = escapeHtml(r.school_name || r.school_username || '-')
      const safeReason = escapeHtml(r.reason || '-')
      const amount = r.amount != null ? parseFloat(r.amount) : 0
      const fmtAmount = '¥' + amount.toFixed(2)
      return `
<div class="bg-white border-2 border-slate-200 rounded-2xl shadow-sm overflow-hidden cursor-pointer"
     onclick="const cb=document.getElementById('ob-${idx}');cb.checked=!cb.checked;${updateTotal}this.style.borderColor=cb.checked?'#3b82f6':'#e2e8f0';">
  <div class="flex items-center gap-2 px-3 py-2.5 bg-slate-50 border-b border-slate-200">
    <input id="ob-${idx}" type="checkbox" data-overdue-bill-select="1"
      data-billing-id="${safeId}" data-school-username="${safeSchool}" data-amount="${amount}" checked
      onclick="event.stopPropagation();${updateTotal}this.closest('[onclick]').style.borderColor=this.checked?'#3b82f6':'#e2e8f0';"
      class="w-4 h-4 flex-shrink-0 accent-blue-500">
    <div class="flex-1 min-w-0 text-left">
      <div class="text-[10px] text-slate-500 leading-none mb-0.5">学校账号</div>
      <div class="text-xs font-semibold text-slate-800 truncate">${safeSchool}</div>
    </div>
  </div>
  <div class="px-3 pt-2 pb-2.5 text-left">
    <div class="flex items-center gap-1.5 mb-1.5">
      <span class="text-[10px] text-slate-500">姓名</span>
      <span class="text-[11px] font-medium text-slate-700 truncate">${safeName}</span>
    </div>
    <div class="grid grid-cols-2 gap-1.5 text-[11px] mb-1.5">
      <div class="bg-amber-50 border border-amber-100 rounded-xl px-2.5 py-1.5">
        <div class="text-amber-600/70 text-[10px]">金额</div><div class="text-amber-700 font-bold">${fmtAmount}</div>
      </div>
      <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5">
        <div class="text-slate-500 text-[10px]">创建时间</div><div class="text-slate-700 text-[10px] break-all">${escapeHtml(getBillingTime(r, 'created_at') || '-')}</div>
      </div>
    </div>
    <div class="bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5 text-[10px]">
      <div class="text-slate-500">详情</div><div class="text-slate-800 break-all">${safeReason}</div>
    </div>
  </div>
</div>`
    }).join('')
    bodyHtml = `
      <div class="text-left space-y-3">
        <p class="text-[11px] text-slate-500">💡 点击卡片或勾选可切换选中状态</p>
        <div class="space-y-2" style="max-height:55vh;overflow-y:auto;">${cardsHtml}</div>
        <div class="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-2xl p-3 text-center shadow-md">
          <div class="text-white/70 text-[10px] mb-0.5">合计金额</div>
          <div id="overdue-total-amount" class="text-white text-2xl font-bold">¥${totalAmount}</div>
        </div>
      </div>`
    modalWidth = '95vw'
  } else {
    const rowsHtml = pendingBills.map((r, idx) => {
      const safeId = escapeHtml(r.billing_id || '')
      const safeSchool = escapeHtml(r.school_username || '-')
      const safeName = escapeHtml(r.school_name || r.school_username || '-')
      const safeReason = escapeHtml(r.reason || '-')
      const amount = r.amount != null ? parseFloat(r.amount) : 0
      const fmtAmount = '¥' + amount.toFixed(2)
      const fmtTime = escapeHtml(getBillingTime(r, 'created_at') || '-')
      return `
        <tr class="border-b border-slate-100 hover:bg-blue-50/40 cursor-pointer"
            onclick="const cb=document.getElementById('ob-${idx}');cb.checked=!cb.checked;${updateTotal}">
          <td class="py-2.5 pl-3 pr-2 text-center">
            <input id="ob-${idx}" type="checkbox" data-overdue-bill-select="1"
              data-billing-id="${safeId}" data-school-username="${safeSchool}" data-amount="${amount}" checked
              onclick="event.stopPropagation();${updateTotal}" class="w-4 h-4 accent-blue-500">
          </td>
          <td class="py-2.5 px-2"><div class="text-sm font-medium text-slate-800">${safeSchool}</div></td>
          <td class="py-2.5 px-2"><div class="text-xs text-slate-500">${safeName}</div></td>
          <td class="py-2.5 px-2 text-sm text-slate-600" style="max-width:180px;"><div class="break-words" title="${safeReason}">${safeReason}</div></td>
          <td class="py-2.5 px-2 text-sm font-semibold text-amber-600 whitespace-nowrap">${fmtAmount}</td>
          <td class="py-2.5 px-2 text-xs text-slate-400 whitespace-nowrap">${fmtTime}</td>
        </tr>`
    }).join('')
    bodyHtml = `
      <div class="text-left">
        <p class="text-xs text-slate-500 mb-3">💡 点击行可切换勾选，勾选后点击"确认支付"合并发起支付</p>
        <div class="rounded-xl border border-slate-200 overflow-hidden mb-3">
          <div style="overflow-x:auto;max-height:288px;overflow-y:auto;">
            <table class="w-full text-left border-collapse text-xs text-center">
              <thead>
                <tr class="bg-slate-100 sticky top-0 z-10">
                  <th class="py-2.5 pl-3 pr-2 w-8">
                    <input type="checkbox" checked
                      onclick="document.querySelectorAll('[data-overdue-bill-select]').forEach(c=>c.checked=this.checked);${updateTotal}"
                      class="w-4 h-4 accent-blue-500">
                  </th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600 whitespace-nowrap">学校账号</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600">姓名</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600">详情</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600 whitespace-nowrap">金额</th>
                  <th class="py-2.5 px-2 font-semibold text-slate-600 whitespace-nowrap">创建时间</th>
                </tr>
              </thead>
              <tbody class="bg-white">${rowsHtml}</tbody>
            </table>
          </div>
        </div>
        <div class="bg-gradient-to-r from-blue-500 to-indigo-600 rounded-xl px-5 py-3 flex items-center justify-between shadow-md">
          <span class="text-white/80 text-sm">合计金额</span>
          <span id="overdue-total-amount" class="text-white text-2xl font-bold">¥${totalAmount}</span>
        </div>
      </div>`
    modalWidth = '780px'
  }

  const result = await Swal.fire({
    title: '选择要支付的账单',
    html: bodyHtml,
    showCancelButton: true,
    confirmButtonText: '确认支付',
    cancelButtonText: '取消',
    confirmButtonColor: '#3b82f6',
    cancelButtonColor: '#94a3b8',
    width: modalWidth,
  })
  if (!result.isConfirmed) return

  const selectedBills = []
  document.querySelectorAll('[data-overdue-bill-select]').forEach((cb) => {
    if (cb.checked) {
      selectedBills.push({ billing_id: cb.dataset.billingId, school_username: cb.dataset.schoolUsername })
    }
  })
  if (!selectedBills.length) {
    await Swal.fire({ title: '提示', text: '请至少选择一条账单', icon: 'info', confirmButtonText: '确定' })
    return
  }

  const payType = await chooseBillingPayType({ title: '选择支付方式', totalAmount })
  if (!payType) return
  await runBillingPaymentFlow(selectedBills, payType)
}

/* ============================================================================
 * 账单支付方式选择 / 创建订单 / 轮询（§7.3 / §7.4 / §7.8 / §7.10）
 * ==========================================================================*/
async function loadMethodsConfig() {
  let enabledMethods = []
  let methods = {}
  try {
    const r = await callRawAPI('/api/payment/methods_config', 'GET')
    enabledMethods = r.enabled_methods || r.enabled_payment_methods || []
    methods = normalizeMethods(r.methods || r.payment_methods || {})
  } catch (_) { /* ignore */ }
  try {
    const c = await callRawAPI('/api/admin/payment/config', 'GET')
    const cfg = c.config || c
    const full = normalizeMethods(cfg.payment_methods || {})
    if (Object.keys(full).length) methods = { ...methods, ...full }
    if (!enabledMethods.length) enabledMethods = cfg.enabled_payment_methods || []
  } catch (_) { /* ignore */ }
  if (!enabledMethods.length) enabledMethods = Object.keys(methods)
  return { enabledMethods, methods }
}

/**
 * 账单支付统一"选择支付方式"弹窗（§7.3）——返回选中方式代码或 null
 */
export async function chooseBillingPayType({ title = '选择支付方式', totalAmount } = {}) {
  const Swal = getSwal()
  if (!Swal) return null
  const { enabledMethods, methods } = await loadMethodsConfig()
  if (!enabledMethods.length) {
    await Swal.fire({ icon: 'warning', title: '暂无可用支付方式', text: '请联系管理员配置支付方式', confirmButtonText: '确定' })
    return null
  }

  const cardsHtml = enabledMethods.map((code) => {
    const def = methods[code] || {}
    const name = def.name || METHOD_NAME_FALLBACK[code] || code
    const border = def.borderColor || '#e2e8f0'
    const textColor = def.textColor || '#1f2937'
    let iconHtml = '💳'
    if (def.svg) iconHtml = `<span style="display:inline-flex;width:28px;height:28px;">${sanitizeSvg(def.svg)}</span>`
    else if (def.image) iconHtml = `<img src="${escapeHtml(def.image)}" style="width:28px;height:28px;object-fit:contain;" alt="">`
    else if (def.icon) iconHtml = escapeHtml(def.icon)
    const safeCode = escapeHtml(code)
    return `
      <label for="bpm-${safeCode}" class="billing-pm-card" data-code="${safeCode}"
        onclick="window.selectBillingPaymentMethod && window.selectBillingPaymentMethod('${safeCode}')"
        style="display:flex;align-items:center;gap:12px;padding:12px 14px;border:2px solid ${border};border-radius:12px;cursor:pointer;margin-bottom:10px;transition:all .15s;">
        <input id="bpm-${safeCode}" type="radio" name="billing-payment-method" value="${safeCode}" class="w-4 h-4 accent-blue-500">
        <span style="font-size:22px;line-height:1;color:${textColor};">${iconHtml}</span>
        <span style="font-size:15px;font-weight:600;color:${textColor};">${escapeHtml(name)}</span>
      </label>`
  }).join('')

  const amountBlock = totalAmount != null
    ? `<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:10px;padding:12px;margin-bottom:14px;text-align:center;">
         <div style="color:rgba(255,255,255,0.85);font-size:12px;">应付金额</div>
         <div style="color:white;font-size:26px;font-weight:bold;">¥${escapeHtml(totalAmount)}</div>
       </div>`
    : ''

  const { value } = await Swal.fire({
    title,
    html: `<div class="text-left">${amountBlock}${cardsHtml}</div>`,
    showCancelButton: true,
    confirmButtonText: '确认支付',
    cancelButtonText: '取消',
    confirmButtonColor: '#3b82f6',
    cancelButtonColor: '#94a3b8',
    width: (typeof window !== 'undefined' && window.innerWidth < 600) ? '95vw' : '460px',
    didOpen: () => {
      window.selectBillingPaymentMethod = (code) => {
        const radio = document.getElementById('bpm-' + code)
        if (radio) radio.checked = true
        document.querySelectorAll('.billing-pm-card').forEach((el) => {
          el.style.boxShadow = el.dataset.code === code ? '0 0 0 2px #3b82f6 inset' : 'none'
        })
      }
    },
    preConfirm: () => {
      const sel = document.querySelector('input[name="billing-payment-method"]:checked')
      if (!sel) {
        Swal.showValidationMessage('请选择支付方式')
        return false
      }
      return sel.value
    },
  })
  return value || null
}

/**
 * 创建账单支付订单并按支付类型展示（§7.4）
 */
async function createBillingPaymentOrderAndOpen(billingItems, payType) {
  const body = {
    billing_items: billingItems,
    pay_type: payType,
    device: getYiPaiDevice(),
    payment_type: 'web',
    app_host: `${window.location.protocol}//${window.location.host}`,
  }
  const orderResult = await callRawAPI('/api/payment/create_order_for_billing', 'POST', body)
  if (!orderResult || orderResult.success === false) {
    throw new Error((orderResult && orderResult.message) || '创建账单支付订单失败')
  }

  const responsePayType = orderResult.pay_type || payType
  const payInfo = orderResult.pay_info || orderResult.pay_url || orderResult.payurl || orderResult.qrcode || ''
  const orderId = orderResult.order_id

  if (responsePayType === 'qrcode') {
    await showBillingQrModal(orderId, payInfo, orderResult)
    orderResult.__handledByQr = true
  } else if (responsePayType === 'html') {
    const w = window.open('', '_blank')
    if (w) { w.document.write(payInfo); w.document.close() }
  } else {
    // jump / '' / 其它
    window.open(orderResult.pay_url || payInfo, '_blank', 'noopener,noreferrer')
  }
  return orderResult
}

/* 账单二维码弹窗 + 本地轮询（§7.4 qrcode 分支，3000ms） */
async function showBillingQrModal(orderId, payInfo, orderResult) {
  const Swal = getSwal()
  if (!Swal) return { status: 'canceled', paid: false }
  let pollingInterval = null
  let paid = false

  await Swal.fire({
    title: '请扫码支付',
    html: `
      <div style="text-align:center;">
        ${orderResult.reused_qr ? '<div style="color:#0284c7;font-size:12px;margin-bottom:8px;">已复用二维码</div>' : ''}
        <div id="billing-payment-qrcode-wrap" style="padding:15px;background:white;border-radius:8px;display:inline-block;">
          <canvas id="billing-payment-qrcode-canvas" style="display:block;margin:0 auto;"></canvas>
          <div id="billing-qrcode-fallback" style="display:none;font-size:12px;margin-top:8px;"></div>
        </div>
        <div id="billing-qrcode-local-status" style="margin-top:12px;padding:10px;background:#fef3c7;border:2px solid #fbbf24;border-radius:8px;color:#92400e;font-size:13px;">正在等待支付...</div>
      </div>`,
    showCancelButton: true,
    showConfirmButton: false,
    cancelButtonText: '取消',
    allowOutsideClick: false,
    width: '360px',
    didOpen: async () => {
      try {
        await new Promise((r) => setTimeout(r, 100))
        const canvas = document.getElementById('billing-payment-qrcode-canvas')
        const QR = await ensureQRCode()
        if (canvas && QR && typeof QR.toCanvas === 'function') {
          await QR.toCanvas(canvas, payInfo, { width: 220, height: 220, margin: 2, color: { dark: '#000000', light: '#ffffff' } })
        } else {
          const fb = document.getElementById('billing-qrcode-fallback')
          if (fb) {
            fb.style.display = 'block'
            fb.innerHTML = `<a href="${escapeHtml(payInfo)}" target="_blank" rel="noopener noreferrer" style="color:#3b82f6;">🔗 打开支付链接</a>`
          }
        }
      } catch (e) {
        console.error('[账单二维码] 生成失败:', e)
      }

      pollingInterval = setInterval(async () => {
        try {
          const r = await callRawAPI('/api/payment/query_billing_local', 'POST', { order_id: orderId })
          const st = r && (r.status || (r.order && r.order.status))
          const statusEl = document.getElementById('billing-qrcode-local-status')
          if (st === 'paid') {
            paid = true
            clearInterval(pollingInterval)
            Swal.close()
          } else if (st === 'closed' || (st && String(st).startsWith('refunded'))) {
            if (statusEl) statusEl.textContent = billingStatusInfo(st).label
          }
        } catch (_) { /* 网络波动继续轮询 */ }
      }, 3000)
    },
    willClose: () => { if (pollingInterval) clearInterval(pollingInterval) },
  })

  if (paid) {
    await Swal.fire({ icon: 'success', title: '支付成功', text: '账单已支付，感谢您的支持！', confirmButtonText: '确定' })
  }
  return { status: paid ? 'paid' : 'canceled', paid }
}

/* 账单支付轮询等待弹窗（§7.8：3000ms，10 分钟上限） */
async function showBillingPaymentPollingModal(orderResult) {
  const Swal = getSwal()
  if (!Swal) return { status: 'canceled', paid: false }
  const orderId = orderResult.order_id
  const maxDurationMs = 10 * 60 * 1000
  const pollIntervalMs = 3000
  const startTs = Date.now()
  let pollTimer = null
  let elapsedTimer = null
  let finalStatus = 'pending'
  let paid = false

  const hintByType = {
    qrcode: '请扫码完成支付后返回本页',
    jump: '请在新打开的页面完成支付',
    html: '请在新打开的页面完成支付',
  }
  const hint = hintByType[orderResult.pay_type] || '请完成支付后返回本页'

  await Swal.fire({
    title: '等待支付结果',
    html: `
      <div style="text-align:center;">
        <div style="margin-bottom:10px;color:#64748b;font-size:13px;">${escapeHtml(hint)}</div>
        <div id="billing-pay-poll-status" style="padding:12px;background:#fef3c7;border:2px solid #fbbf24;border-radius:8px;color:#92400e;font-size:14px;">正在检测支付状态...</div>
        <div id="billing-pay-poll-elapsed" style="margin-top:8px;font-size:12px;color:#94a3b8;">已等待 0 秒</div>
      </div>`,
    showCancelButton: true,
    showConfirmButton: false,
    cancelButtonText: '我已完成/关闭',
    allowOutsideClick: false,
    width: '420px',
    didOpen: () => {
      elapsedTimer = setInterval(() => {
        const el = document.getElementById('billing-pay-poll-elapsed')
        if (el) el.textContent = `已等待 ${Math.floor((Date.now() - startTs) / 1000)} 秒`
      }, 1000)
      pollTimer = setInterval(async () => {
        if (Date.now() - startTs > maxDurationMs) {
          finalStatus = 'timeout'
          clearInterval(pollTimer)
          Swal.close()
          return
        }
        try {
          const r = await callRawAPI('/api/payment/query_billing_local', 'POST', { order_id: orderId })
          const st = r && (r.status || (r.order && r.order.status))
          const statusEl = document.getElementById('billing-pay-poll-status')
          if (st === 'paid') {
            paid = true
            finalStatus = 'paid'
            clearInterval(pollTimer)
            Swal.close()
          } else if (st === 'closed') {
            finalStatus = 'closed'
            clearInterval(pollTimer)
            Swal.close()
          } else if (st && String(st).startsWith('refunded')) {
            if (statusEl) statusEl.textContent = billingStatusInfo(st).label
          }
        } catch (_) { /* 继续轮询 */ }
      }, pollIntervalMs)
    },
    willClose: () => {
      if (pollTimer) clearInterval(pollTimer)
      if (elapsedTimer) clearInterval(elapsedTimer)
    },
  })

  return { status: finalStatus, paid }
}

async function showBillingPollingResultSummary(pollingResult) {
  const Swal = getSwal()
  if (!Swal || !pollingResult) return
  if (pollingResult.paid || pollingResult.status === 'paid') {
    await Swal.fire({ icon: 'success', title: '支付成功', text: '账单已支付，感谢您的支持！', confirmButtonText: '确定' })
  } else if (pollingResult.status === 'timeout') {
    await Swal.fire({ icon: 'info', title: '支付未完成', text: '未检测到支付结果，请稍后在"我的账单"中确认。', confirmButtonText: '确定' })
  }
}

/**
 * 账单支付主流程（§7.10）：创建订单 → 轮询 → 总结
 */
export async function runBillingPaymentFlow(billingItems, payType) {
  const Swal = getSwal()
  try {
    const orderResult = await createBillingPaymentOrderAndOpen(billingItems, payType)
    // qrcode 分支已在 showBillingQrModal 内自带本地轮询并总结
    if (!orderResult.__handledByQr) {
      const pollingResult = await showBillingPaymentPollingModal(orderResult)
      await showBillingPollingResultSummary(pollingResult)
    }
  } catch (e) {
    Swal?.fire({ icon: 'error', title: '支付失败', text: e.message || '支付过程出错，请稍后重试', confirmButtonText: '确定' })
  }
}

/**
 * 批量/单条账单支付（§7.11 / §7.13）——供 BillingModal 调用
 * @param {Array<{billing_id, school_username}>} items
 */
export async function paySelectedBilling(items, { confirm = true } = {}) {
  const Swal = getSwal()
  if (!items || !items.length) {
    Swal?.fire({ icon: 'warning', title: '提示', text: '请至少选择一条账单', confirmButtonText: '确定' })
    return
  }
  if (confirm && Swal) {
    const r = await Swal.fire({
      icon: 'question',
      title: '确认支付',
      text: `将对选中的 ${items.length} 条账单发起支付`,
      showCancelButton: true,
      confirmButtonText: '继续',
      cancelButtonText: '取消',
    })
    if (!r.isConfirmed) return
  }
  const payType = await chooseBillingPayType({ title: '选择支付方式' })
  if (!payType) return
  await runBillingPaymentFlow(items, payType)
}
