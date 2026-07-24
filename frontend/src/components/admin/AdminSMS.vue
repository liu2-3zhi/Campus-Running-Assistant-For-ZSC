<script setup>
import { ref, reactive, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const checkingBalance = ref(false)
const loadingHistory = ref(false)
const loadingReplies = ref(false)
const success = ref('')
const error = ref('')

const config = reactive({
  enable_sms_service: false,
  enable_phone_modification: false,
  enable_phone_login: false,
  enable_phone_registration_verify: false,
  username: '',
  api_key: '',
  signature: '',
  template_register: '',
  code_expire_minutes: 5,
  rate_limit_per_account_day: 10,
  rate_limit_per_ip_day: 20,
  rate_limit_per_phone_day: 5,
})

const webhookUrl = ref('')

// 测试短信
const testPhone = ref('')
const testCode = ref('')
const testResult = ref('')
const testError = ref('')

// 余额
const balance = ref(null)

// 短信历史
const historyDate = ref('')
const historyPhone = ref('')
const historyRecords = ref([])
const historyLoaded = ref(false)

// 回复记录
const replyLogs = ref([])
const repliesLoaded = ref(false)

function clearMsg() { success.value = ''; error.value = '' }

function formatTime(rec) {
  if (rec && rec.datetime) return rec.datetime
  const ts = rec && rec.timestamp
  if (ts != null) {
    const d = new Date(ts < 1e12 ? ts * 1000 : ts)
    if (!isNaN(d.getTime())) return d.toLocaleString('zh-CN')
  }
  return '--'
}

async function fetchConfig() {
  loading.value = true
  clearMsg()
  try {
    const data = await callRawAPI('/api/admin/sms/config', 'GET')
    if (data.success && data.config) {
      const c = data.config
      config.enable_sms_service = !!c.enable_sms_service
      config.enable_phone_modification = !!c.enable_phone_modification
      config.enable_phone_login = !!c.enable_phone_login
      config.enable_phone_registration_verify = !!c.enable_phone_registration_verify
      config.username = c.username || ''
      config.api_key = c.api_key || ''
      config.signature = c.signature || ''
      config.template_register = c.template_register || ''
      config.code_expire_minutes = c.code_expire_minutes ?? 5
      config.rate_limit_per_account_day = c.rate_limit_per_account_day ?? 10
      config.rate_limit_per_ip_day = c.rate_limit_per_ip_day ?? 20
      config.rate_limit_per_phone_day = c.rate_limit_per_phone_day ?? 5
    } else if (data.success === false) {
      error.value = data.message || '加载短信配置失败'
    }
    webhookUrl.value = window.location.origin + '/sms-reply-webhook'
  } catch (e) {
    error.value = e.message || '加载短信配置失败'
  } finally {
    loading.value = false
  }
}

function onMainSwitchChange() {
  // 主开关关闭时联动关闭三个子开关
  if (!config.enable_sms_service) {
    config.enable_phone_modification = false
    config.enable_phone_login = false
    config.enable_phone_registration_verify = false
  }
}

async function saveConfig() {
  saving.value = true
  clearMsg()
  try {
    const data = await callRawAPI('/api/admin/sms/config', 'POST', {
      enable_sms_service: config.enable_sms_service,
      enable_phone_modification: config.enable_phone_modification,
      enable_phone_login: config.enable_phone_login,
      enable_phone_registration_verify: config.enable_phone_registration_verify,
      username: config.username,
      api_key: config.api_key,
      signature: config.signature,
      template_register: config.template_register,
      code_expire_minutes: Math.max(1, parseInt(config.code_expire_minutes) || 5),
      rate_limit_per_account_day: Math.max(0, parseInt(config.rate_limit_per_account_day) || 0),
      rate_limit_per_ip_day: Math.max(0, parseInt(config.rate_limit_per_ip_day) || 0),
      rate_limit_per_phone_day: Math.max(0, parseInt(config.rate_limit_per_phone_day) || 0),
    })
    if (data.success) {
      success.value = data.message || '短信配置已保存'
    } else {
      error.value = data.message || '保存失败'
    }
  } catch (e) {
    error.value = e.message || '保存短信配置失败'
  } finally {
    saving.value = false
  }
}

async function checkBalance() {
  checkingBalance.value = true
  clearMsg()
  try {
    const data = await callRawAPI('/api/admin/sms/check_balance', 'GET')
    if (data.success) {
      balance.value = { balance: data.balance, sent_today: data.sent_today, message: data.message }
    } else {
      balance.value = { message: data.message || '查询失败', error: true }
    }
  } catch (e) {
    error.value = e.message || '查询余额失败'
  } finally {
    checkingBalance.value = false
  }
}

async function sendTestSMS() {
  testResult.value = ''
  testError.value = ''
  if (!/^1[3-9]\d{9}$/.test(testPhone.value)) {
    testError.value = '请输入正确的手机号'
    return
  }
  if (testCode.value && !/^\d{4,8}$/.test(testCode.value)) {
    testError.value = '自定义验证码需为 4-8 位数字'
    return
  }
  testing.value = true
  try {
    const body = { phone: testPhone.value }
    if (testCode.value) body.code = testCode.value
    const data = await callRawAPI('/api/sms/test_send', 'POST', body)
    if (data.success) {
      testResult.value = '测试短信发送成功' + (data.code ? '，验证码：' + data.code : '')
    } else {
      testError.value = data.message || '发送失败'
    }
  } catch (e) {
    testError.value = e.message || '发送测试短信失败'
  } finally {
    testing.value = false
  }
}

async function loadHistory() {
  loadingHistory.value = true
  clearMsg()
  try {
    const params = {}
    if (historyDate.value) params.date = historyDate.value
    if (historyPhone.value) params.phone = historyPhone.value
    const qs = new URLSearchParams(params).toString()
    const data = await callRawAPI('/api/admin/sms/history' + (qs ? '?' + qs : ''), 'GET')
    if (data.success) {
      historyRecords.value = data.records || []
      historyLoaded.value = true
    } else {
      error.value = data.message || '获取历史失败'
    }
  } catch (e) {
    error.value = e.message || '获取短信历史失败'
  } finally {
    loadingHistory.value = false
  }
}

async function loadReplyLogs() {
  loadingReplies.value = true
  clearMsg()
  try {
    const data = await callRawAPI('/api/sms/reply-logs?limit=50', 'GET')
    if (data.success) {
      replyLogs.value = data.logs || []
      repliesLoaded.value = true
    } else {
      error.value = data.message || '获取回复记录失败'
    }
  } catch (e) {
    error.value = e.message || '获取短信回复记录失败'
  } finally {
    loadingReplies.value = false
  }
}

onMounted(fetchConfig)
</script>

<template>
  <div class="space-y-6">
    <!-- Alerts -->
    <div v-if="success" class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between">
      <span>{{ success }}</span>
      <button @click="success = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>
    <div v-if="error" class="p-3 rounded-lg bg-red-500/10 text-red-500 flex items-center justify-between">
      <span>{{ error }}</span>
      <button @click="error = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-[var(--ink-muted)]">加载中...</div>

    <template v-else>
      <!-- Service switches -->
      <div class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">短信服务开关</h3>
        <label class="flex items-center justify-between gap-3">
          <span class="text-sm text-[var(--ink)]">启用短信服务</span>
          <input v-model="config.enable_sms_service" type="checkbox" class="w-5 h-5" @change="onMainSwitchChange" />
        </label>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 pl-1" :class="config.enable_sms_service ? '' : 'opacity-50'">
          <label class="flex items-center justify-between gap-2">
            <span class="text-sm text-[var(--ink-secondary)]">修改手机号验证</span>
            <input v-model="config.enable_phone_modification" type="checkbox" class="w-5 h-5" :disabled="!config.enable_sms_service" />
          </label>
          <label class="flex items-center justify-between gap-2">
            <span class="text-sm text-[var(--ink-secondary)]">手机号登录</span>
            <input v-model="config.enable_phone_login" type="checkbox" class="w-5 h-5" :disabled="!config.enable_sms_service" />
          </label>
          <label class="flex items-center justify-between gap-2">
            <span class="text-sm text-[var(--ink-secondary)]">注册手机验证</span>
            <input v-model="config.enable_phone_registration_verify" type="checkbox" class="w-5 h-5" :disabled="!config.enable_sms_service" />
          </label>
        </div>
      </div>

      <!-- SMSBao account config -->
      <div class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">短信宝配置</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">账号 (username)</label>
            <input v-model="config.username" type="text" class="input-field w-full" placeholder="短信宝账号" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">API Key (接口密钥)</label>
            <input v-model="config.api_key" type="password" class="input-field w-full" placeholder="短信宝 API Key" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">短信签名</label>
            <input v-model="config.signature" type="text" class="input-field w-full" placeholder="例如：【校园跑】" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">注册模板</label>
            <input v-model="config.template_register" type="text" class="input-field w-full" placeholder="注册验证码短信模板" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">验证码有效期（分钟）</label>
            <input v-model.number="config.code_expire_minutes" type="number" min="1" class="input-field w-full" />
          </div>
        </div>
      </div>

      <!-- Rate limits -->
      <div class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">发送限流（每日）</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">每账号每日上限</label>
            <input v-model.number="config.rate_limit_per_account_day" type="number" min="0" class="input-field w-full" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">每 IP 每日上限</label>
            <input v-model.number="config.rate_limit_per_ip_day" type="number" min="0" class="input-field w-full" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">每手机号每日上限</label>
            <input v-model.number="config.rate_limit_per_phone_day" type="number" min="0" class="input-field w-full" />
          </div>
        </div>
        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">回复 Webhook 地址</label>
          <input :value="webhookUrl" type="text" class="input-field w-full" readonly />
          <p class="text-xs text-[var(--ink-muted)] mt-1">在短信宝后台配置此地址以接收用户回复。</p>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <button @click="checkBalance" :disabled="checkingBalance" class="btn btn-secondary">
            {{ checkingBalance ? '查询中...' : '查询余额' }}
          </button>
          <button @click="saveConfig" :disabled="saving" class="btn btn-primary">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
        </div>
        <div v-if="balance" class="p-3 rounded-lg text-sm" :class="balance.error ? 'bg-amber-500/10 text-amber-600' : 'bg-[var(--success)]/10 text-[var(--success)]'">
          <template v-if="!balance.error">剩余条数：<b>{{ balance.balance }}</b>，今日已发送：<b>{{ balance.sent_today }}</b>。</template>
          <span>{{ balance.message }}</span>
        </div>
      </div>

      <!-- Test SMS -->
      <div class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">发送测试短信</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input v-model="testPhone" type="tel" class="input-field w-full" placeholder="输入手机号" />
          <input v-model="testCode" type="text" class="input-field w-full" placeholder="自定义验证码（可选，4-8位）" />
        </div>
        <div class="flex justify-end">
          <button @click="sendTestSMS" :disabled="testing || !testPhone" class="btn btn-secondary">
            {{ testing ? '发送中...' : '发送测试' }}
          </button>
        </div>
        <div v-if="testResult" class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between">
          <span>{{ testResult }}</span>
          <button @click="testResult = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
        </div>
        <div v-if="testError" class="p-3 rounded-lg bg-red-500/10 text-red-500 flex items-center justify-between">
          <span>{{ testError }}</span>
          <button @click="testError = ''" class="ml-2 opacity-60 hover:opacity-100">&times;</button>
        </div>
      </div>

      <!-- SMS history -->
      <div class="panel p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-[var(--ink)]">短信发送历史</h3>
          <button @click="loadHistory" :disabled="loadingHistory" class="btn btn-ghost text-sm">
            {{ loadingHistory ? '加载中...' : '查询' }}
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input v-model="historyDate" type="date" class="input-field w-full" />
          <input v-model="historyPhone" type="text" class="input-field w-full" placeholder="按手机号筛选" />
        </div>
        <div v-if="historyLoaded">
          <div v-if="historyRecords.length === 0" class="py-6 text-center text-[var(--ink-secondary)] text-sm">暂无记录</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="border-b border-[var(--border-color)]">
                <tr>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">时间</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">手机号</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">用户</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">IP</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium">内容</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(rec, idx) in historyRecords" :key="idx" class="border-b border-[var(--border-color)]">
                  <td class="px-2 py-1.5 whitespace-nowrap">{{ formatTime(rec) }}</td>
                  <td class="px-2 py-1.5 font-mono whitespace-nowrap">{{ rec.phone || '--' }}</td>
                  <td class="px-2 py-1.5 whitespace-nowrap">{{ rec.username || '--' }}</td>
                  <td class="px-2 py-1.5 font-mono whitespace-nowrap">{{ rec.ip || '--' }}</td>
                  <td class="px-2 py-1.5 break-words">{{ rec.content || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- SMS reply logs -->
      <div class="panel p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-[var(--ink)]">短信回复记录</h3>
          <button @click="loadReplyLogs" :disabled="loadingReplies" class="btn btn-ghost text-sm">
            {{ loadingReplies ? '加载中...' : '刷新' }}
          </button>
        </div>
        <div v-if="repliesLoaded">
          <div v-if="replyLogs.length === 0" class="py-6 text-center text-[var(--ink-secondary)] text-sm">暂无回复记录</div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="border-b border-[var(--border-color)]">
                <tr>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">时间</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">手机号</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium">回复内容</th>
                  <th class="text-left px-2 py-1.5 text-[var(--ink-secondary)] font-medium whitespace-nowrap">IP</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(log, idx) in replyLogs" :key="idx" class="border-b border-[var(--border-color)]">
                  <td class="px-2 py-1.5 whitespace-nowrap">{{ formatTime(log) }}</td>
                  <td class="px-2 py-1.5 font-mono whitespace-nowrap">{{ log.phone || '--' }}</td>
                  <td class="px-2 py-1.5 break-words">{{ log.content || '--' }}</td>
                  <td class="px-2 py-1.5 font-mono whitespace-nowrap">{{ log.ip || '--' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
