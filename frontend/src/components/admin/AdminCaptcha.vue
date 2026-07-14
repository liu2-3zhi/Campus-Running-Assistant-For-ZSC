<script setup>
import { ref, computed, onMounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'

// ---- 全局状态 ----
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const success = ref('')
const error = ref('')

// ---- 验证码配置参数 ----
const configLoaded = ref(false)
const length = ref(4)
const scaleFactor = ref(2)
const noiseLevel = ref(0.08)

// 配置面板 ref（用于计算测试生成时的显示宽度）
const configPanelRef = ref(null)

// ---- 测试生成预览 ----
const previewReady = ref(false)
const previewId = ref('')
const previewCode = ref('')
const previewWidth = ref(343)
const previewHeight = ref(119)
const previewTs = ref(0)

const previewSrc = computed(() =>
  previewId.value
    ? `/api/captcha/html/${previewId.value}?t=${previewTs.value}&width=${previewWidth.value}`
    : ''
)

// ---- 历史记录 ----
const historyLoading = ref(false)
const historyError = ref('')
const historyDate = ref(todayStr())
const historyStatus = ref('')
const records = ref([])
const historyPanelRef = ref(null)

// ---- 详情模态框 ----
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detail = ref(null)

// ---- 统计 ----
const stats = computed(() => {
  const list = records.value || []
  return {
    total: list.length,
    success: list.filter((r) => r.status === 'verified_success').length,
    failed: list.filter((r) => r.status === 'verified_failed').length,
    pending: list.filter((r) => r.status === 'created').length,
    expired: list.filter((r) => r.status === 'expired').length,
    test: list.filter((r) => r.status === 'test_generated').length,
  }
})

// ---- 工具函数 ----
function todayStr() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const STATUS_TEXT = {
  created: '待验证',
  verified_success: '验证成功',
  verified_failed: '验证失败',
  expired: '已过期',
  test_generated: '测试生成',
}
const STATUS_CLASS = {
  created: 'bg-yellow-100 text-yellow-800',
  verified_success: 'bg-green-100 text-green-800',
  verified_failed: 'bg-red-100 text-red-800',
  expired: 'bg-gray-100 text-gray-800',
  test_generated: 'bg-blue-100 text-blue-800',
}

function statusText(status) {
  return STATUS_TEXT[status] || status || '-'
}
function statusClass(status) {
  return STATUS_CLASS[status] || 'bg-gray-100 text-gray-800'
}
function captchaCodeOf(rec) {
  return rec.code || rec.captcha_code || 'N/A'
}
function createdTime(rec) {
  if (rec.timestamp_readable) return rec.timestamp_readable
  if (rec.timestamp) return new Date(rec.timestamp * 1000).toLocaleString('zh-CN')
  return '-'
}

// 计算验证码显示宽度（复刻原逻辑：面板宽度 - 偏移，限制 200-1000）
function computeWeight(el, offset) {
  if (!el || !el.clientWidth) return ''
  let w = el.clientWidth - offset
  if (w > 1000) w = 1000
  if (w < 200) w = 200
  return w
}

function validateParams() {
  const len = parseInt(length.value)
  const scale = parseInt(scaleFactor.value)
  const noise = parseFloat(noiseLevel.value)
  if (isNaN(len) || len < 3 || len > 6) {
    error.value = '验证码长度必须在 3-6 之间'
    return null
  }
  if (isNaN(scale) || scale < 2 || scale > 32) {
    error.value = '细分倍数必须在 2-32 之间'
    return null
  }
  if (isNaN(noise) || noise < 0 || noise > 0.3) {
    error.value = '噪点比例必须在 0.0-0.3 之间'
    return null
  }
  return { length: len, scale_factor: scale, noise_level: noise }
}

// ---- API 调用 ----
async function fetchConfig(showSuccess = false) {
  loading.value = true
  error.value = ''
  try {
    const result = await callRawAPI('/api/captcha/config', 'GET')
    if (result && result.success && result.config) {
      const s = result.config
      // 使用 !== undefined 判断，正确区分"值为 0"与"未设置"
      length.value = s.length !== undefined ? s.length : 4
      scaleFactor.value = s.scale_factor !== undefined ? s.scale_factor : 2
      noiseLevel.value = s.noise_level !== undefined ? s.noise_level : 0.08
      configLoaded.value = true
      if (showSuccess) success.value = '验证码配置已加载'
    } else {
      length.value = 4
      scaleFactor.value = 2
      noiseLevel.value = 0.08
      configLoaded.value = true
    }
  } catch (e) {
    error.value = e.message || '加载验证码配置失败'
    length.value = 4
    scaleFactor.value = 2
    noiseLevel.value = 0.08
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  success.value = ''
  error.value = ''
  if (!configLoaded.value) {
    error.value = '请先等待配置加载完成再保存'
    return
  }
  const params = validateParams()
  if (!params) return
  saving.value = true
  try {
    const result = await callRawAPI('/api/captcha/save_settings', 'POST', params)
    if (result && result.success) {
      success.value = '验证码设置已保存'
    } else {
      error.value = result?.message || '保存失败'
    }
  } catch (e) {
    error.value = e.message || '保存验证码设置失败'
  } finally {
    saving.value = false
  }
}

async function testGenerate() {
  success.value = ''
  error.value = ''
  const params = validateParams()
  if (!params) return
  testing.value = true
  try {
    const weight = computeWeight(configPanelRef.value, 400)
    const result = await callRawAPI('/api/captcha/test_generate', 'POST', {
      ...params,
      weight,
    })
    if (result && result.success) {
      previewId.value = result.captcha_id
      previewWidth.value = result.width || 343
      previewHeight.value = result.height || 119
      previewCode.value = result.code
      previewTs.value = Date.now()
      previewReady.value = true
    } else {
      error.value = result?.message || '生成失败'
    }
  } catch (e) {
    error.value = e.message || '生成测试验证码失败'
  } finally {
    testing.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    const date = (historyDate.value || '').replace(/-/g, '')
    const params = new URLSearchParams({ date })
    if (historyStatus.value) params.append('status', historyStatus.value)
    const weight = computeWeight(historyPanelRef.value, 200)
    let url = `/api/captcha/history?${params.toString()}`
    if (weight !== '') url += `&weight=${weight}`
    const result = await callRawAPI(url, 'GET')
    if (result && result.success) {
      records.value = result.data || []
    } else {
      records.value = []
      historyError.value = result?.message || '加载失败'
    }
  } catch (e) {
    records.value = []
    historyError.value = e.message || '加载验证码历史失败'
  } finally {
    historyLoading.value = false
  }
}

async function showDetail(id) {
  if (!id) return
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const result = await callRawAPI(`/api/captcha/detail/${id}`, 'GET')
    if (result && result.success && result.data) {
      detail.value = result.data
    } else {
      detailError.value = result?.message || '未找到该验证码的详细信息'
    }
  } catch (e) {
    detailError.value = e.message || '获取验证码详情失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailVisible.value = false
  detail.value = null
  detailError.value = ''
}

onMounted(async () => {
  await fetchConfig()
  await loadHistory()
})
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
      <!-- 验证码参数配置 -->
      <div ref="configPanelRef" class="panel p-5 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-[var(--ink)]">🔒 验证码参数配置</h3>
          <button @click="fetchConfig(true)" :disabled="loading" class="btn btn-secondary text-sm">
            🔄 刷新配置
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">验证码长度（3-6）</label>
            <input v-model.number="length" type="number" min="3" max="6" step="1" class="input-field w-full" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">细分倍数（2-32）</label>
            <input v-model.number="scaleFactor" type="number" min="2" max="32" step="1" class="input-field w-full" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">噪点比例（0.0-0.3）</label>
            <input v-model.number="noiseLevel" type="number" min="0" max="0.3" step="0.01" class="input-field w-full" />
          </div>
        </div>

        <div class="flex flex-wrap justify-end gap-3">
          <button @click="testGenerate" :disabled="testing" class="btn btn-secondary">
            {{ testing ? '生成中...' : '🔄 测试生成' }}
          </button>
          <button @click="saveConfig" :disabled="saving" class="btn btn-primary">
            {{ saving ? '保存中...' : '💾 保存设置' }}
          </button>
        </div>

        <!-- 测试生成预览 -->
        <div v-if="previewReady" class="mt-2 p-4 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] space-y-2">
          <div class="text-sm text-[var(--ink-secondary)]">预览：</div>
          <div class="flex items-center justify-center bg-white rounded p-2 overflow-hidden">
            <iframe
              :src="previewSrc"
              :style="{ width: previewWidth + 'px', height: previewHeight + 'px', maxWidth: previewWidth + 'px', maxHeight: previewHeight + 'px' }"
              class="border-none block mx-auto"
              scrolling="no"
              frameborder="0"
              title="验证码预览"
            ></iframe>
          </div>
          <div class="text-sm text-[var(--ink-secondary)]">
            正确答案：<span class="font-mono font-bold text-[var(--ink)]">{{ previewCode }}</span>
          </div>
        </div>
      </div>

      <!-- 验证码历史记录 -->
      <div ref="historyPanelRef" class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">📜 验证码历史记录</h3>

        <!-- 筛选 -->
        <div class="flex flex-wrap items-end gap-3">
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">日期</label>
            <input v-model="historyDate" type="date" class="input-field" />
          </div>
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">状态</label>
            <select v-model="historyStatus" class="select-field">
              <option value="">全部</option>
              <option value="created">待验证</option>
              <option value="verified_success">验证成功</option>
              <option value="verified_failed">验证失败</option>
              <option value="expired">已过期</option>
              <option value="test_generated">测试生成</option>
            </select>
          </div>
          <button @click="loadHistory" :disabled="historyLoading" class="btn btn-secondary">
            {{ historyLoading ? '加载中...' : '🔄 刷新记录' }}
          </button>
        </div>

        <!-- 统计 -->
        <div class="grid grid-cols-3 md:grid-cols-6 gap-2 text-center">
          <div class="p-2 rounded-lg bg-[var(--surface-2)]">
            <div class="text-lg font-bold text-[var(--ink)]">{{ stats.total }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">总计</div>
          </div>
          <div class="p-2 rounded-lg bg-[var(--surface-2)]">
            <div class="text-lg font-bold text-green-600">{{ stats.success }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">成功</div>
          </div>
          <div class="p-2 rounded-lg bg-[var(--surface-2)]">
            <div class="text-lg font-bold text-red-500">{{ stats.failed }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">失败</div>
          </div>
          <div class="p-2 rounded-lg bg-[var(--surface-2)]">
            <div class="text-lg font-bold text-yellow-600">{{ stats.pending }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">待验证</div>
          </div>
          <div class="p-2 rounded-lg bg-[var(--surface-2)]">
            <div class="text-lg font-bold text-gray-500">{{ stats.expired }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">已过期</div>
          </div>
          <div class="p-2 rounded-lg bg-[var(--surface-2)]">
            <div class="text-lg font-bold text-blue-600">{{ stats.test }}</div>
            <div class="text-xs text-[var(--ink-secondary)]">测试</div>
          </div>
        </div>

        <!-- 历史提示/错误 -->
        <div v-if="historyError" class="p-3 rounded-lg bg-red-500/10 text-red-500">{{ historyError }}</div>

        <!-- 列表 -->
        <div v-if="historyLoading" class="text-center py-10 text-[var(--ink-muted)]">加载中...</div>
        <div v-else-if="records.length === 0" class="text-center py-10 text-[var(--ink-muted)]">该日期没有验证码记录</div>
        <div v-else class="space-y-2">
          <div
            v-for="record in records"
            :key="record.captcha_id"
            class="p-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] hover:shadow-md transition-shadow"
          >
            <div class="flex justify-between items-start mb-2">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-mono text-sm text-[var(--ink-secondary)]">ID: {{ record.captcha_id || 'N/A' }}</span>
                  <span class="px-2 py-0.5 text-xs rounded" :class="statusClass(record.status)">{{ statusText(record.status) }}</span>
                </div>
                <div class="text-xs text-[var(--ink-secondary)] space-y-0.5">
                  <div>验证码: <span class="font-semibold text-[var(--ink)] font-mono">{{ captchaCodeOf(record) }}</span></div>
                  <div>创建时间: {{ createdTime(record) }}</div>
                  <div v-if="record.verified_at_readable">验证时间: {{ record.verified_at_readable }}</div>
                  <div v-if="record.verified_input">
                    用户输入:
                    <span
                      class="font-semibold"
                      :class="record.status === 'verified_success' ? 'text-green-600' : 'text-red-600'"
                    >{{ record.verified_input }}</span>
                  </div>
                  <div>客户端IP: {{ record.client_ip || 'N/A' }}</div>
                </div>
              </div>
              <button
                @click="showDetail(record.captcha_id)"
                class="text-sm text-blue-600 hover:text-blue-800 ml-2 bg-blue-50 px-2 py-1 rounded"
              >
                详情
              </button>
            </div>
            <div v-if="record.html" class="mt-2 pt-2 border-t border-[var(--border)]">
              <div class="text-xs text-[var(--ink-secondary)] mb-1">验证码图片:</div>
              <div class="flex items-center justify-center bg-white p-2 rounded overflow-hidden">
                <div class="scale-75 origin-center" v-html="record.html"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 验证码详情模态框 -->
    <div v-if="detailVisible" class="fixed inset-0 z-[1054] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/50" @click="closeDetail"></div>
      <div class="relative panel p-5 w-full max-w-lg max-h-[85vh] overflow-y-auto space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-blue-600">🔍 验证码详细信息</h3>
          <button @click="closeDetail" class="opacity-60 hover:opacity-100 text-xl leading-none">&times;</button>
        </div>

        <div v-if="detailLoading" class="text-center py-10 text-[var(--ink-muted)]">加载中...</div>
        <div v-else-if="detailError" class="p-3 rounded-lg bg-red-500/10 text-red-500">{{ detailError }}</div>
        <template v-else-if="detail">
          <!-- 基本信息 -->
          <div class="p-3 rounded-lg bg-[var(--surface-2)] space-y-1 text-sm">
            <div class="font-semibold text-[var(--ink)] mb-1">📋 基本信息</div>
            <div class="flex justify-between"><span class="text-[var(--ink-secondary)]">验证码ID</span><span class="font-mono">{{ detail.captcha_id || '-' }}</span></div>
            <div class="flex justify-between"><span class="text-[var(--ink-secondary)]">验证码</span><span class="font-mono font-bold">{{ detail.code || '-' }}</span></div>
            <div class="flex justify-between items-center">
              <span class="text-[var(--ink-secondary)]">状态</span>
              <span class="px-2 py-1 text-xs rounded" :class="statusClass(detail.status)">{{ statusText(detail.status) }}</span>
            </div>
          </div>

          <!-- 时间信息 -->
          <div class="p-3 rounded-lg bg-[var(--surface-2)] space-y-1 text-sm">
            <div class="font-semibold text-[var(--ink)] mb-1">⏰ 时间信息</div>
            <div class="flex justify-between"><span class="text-[var(--ink-secondary)]">创建时间</span><span>{{ createdTime(detail) }}</span></div>
            <div v-if="detail.verified_at_readable" class="flex justify-between"><span class="text-[var(--ink-secondary)]">验证时间</span><span>{{ detail.verified_at_readable }}</span></div>
            <div v-if="detail.expired_at_readable" class="flex justify-between"><span class="text-[var(--ink-secondary)]">过期时间</span><span>{{ detail.expired_at_readable }}</span></div>
          </div>

          <!-- 验证信息 -->
          <div v-if="detail.verified_input" class="p-3 rounded-lg bg-[var(--surface-2)] space-y-1 text-sm">
            <div class="font-semibold text-[var(--ink)] mb-1">✅ 验证信息</div>
            <div class="flex justify-between">
              <span class="text-[var(--ink-secondary)]">用户输入</span>
              <span class="font-mono font-bold" :class="detail.status === 'verified_success' ? 'text-green-600' : 'text-red-600'">{{ detail.verified_input }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--ink-secondary)]">验证结果</span>
              <span class="font-semibold" :class="detail.status === 'verified_success' ? 'text-green-600' : 'text-red-600'">
                {{ detail.status === 'verified_success' ? '✅ 验证成功' : '❌ 验证失败' }}
              </span>
            </div>
          </div>

          <!-- 客户端信息 -->
          <div class="p-3 rounded-lg bg-[var(--surface-2)] space-y-1 text-sm">
            <div class="font-semibold text-[var(--ink)] mb-1">🌐 客户端信息</div>
            <div class="flex justify-between"><span class="text-[var(--ink-secondary)]">IP地址</span><span class="font-mono">{{ detail.client_ip || 'N/A' }}</span></div>
            <div class="flex flex-col gap-1">
              <span class="text-[var(--ink-secondary)]">User Agent</span>
              <span class="text-xs break-all">{{ detail.user_agent || 'N/A' }}</span>
            </div>
          </div>

          <!-- 验证码图片 -->
          <div v-if="detail.html" class="p-3 rounded-lg bg-[var(--surface-2)] space-y-1 text-sm">
            <div class="font-semibold text-[var(--ink)] mb-1">🖼️ 验证码图片</div>
            <div class="flex items-center justify-center bg-white p-2 rounded overflow-hidden">
              <div class="origin-center" v-html="detail.html"></div>
            </div>
          </div>
        </template>

        <div class="flex justify-end">
          <button @click="closeDetail" class="btn btn-secondary">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
