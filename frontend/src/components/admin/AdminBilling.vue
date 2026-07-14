<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import AppModal from '@/components/common/AppModal.vue'

/* ── 账单状态语义（复刻附录 C）── */
const STATUS_MAP = {
  pending: { label: '待支付', icon: '⏳', cls: 'bg-amber-100 text-amber-700' },
  paid: { label: '已支付', icon: '✓', cls: 'bg-green-100 text-green-700' },
  closed: { label: '已关闭', icon: '⛔', cls: 'bg-slate-100 text-slate-600' },
  refunded_partial: { label: '部分退款', icon: '↩', cls: 'bg-orange-100 text-orange-700' },
  refunded_full: { label: '全额退款', icon: '↩', cls: 'bg-rose-100 text-rose-700' },
  admin_cleared: { label: '管理员清除', icon: '✓', cls: 'bg-sky-100 text-sky-700' },
}

function statusInfo(status) {
  return STATUS_MAP[status] || { label: status || '未知', icon: '•', cls: 'bg-gray-100 text-gray-600' }
}

/* ── 列表状态 ── */
const records = ref([])
const summary = ref(null)
const total = ref(0)
const loaded = ref(false)
const loading = ref(false)
const error = ref('')
const success = ref('')

/* ── 筛选 / 分页 ── */
const schoolInput = ref('')
const keyword = ref('')
const page = ref(1)
const pageSize = ref(50)

/* ── 添加账单弹窗 ── */
const showAddModal = ref(false)
const adding = ref(false)
const addForm = ref({ school_username: '', mode: 'count', count: 1, amount: 0, reason: '' })

/* ── 编辑账单弹窗 ── */
const showEditModal = ref(false)
const editing = ref(false)
const editRecord = ref(null)
const editForm = ref({ amount: 0, status: 'pending', reason: '' })

/* 弹窗内独立提示（与页面级 error/success 分离） */
const formError = ref('')

/* ── 消息辅助 ── */
function clearMessages() {
  error.value = ''
  success.value = ''
}
function showSuccess(msg) {
  success.value = msg
  error.value = ''
  setTimeout(() => { if (success.value === msg) success.value = '' }, 3000)
}
function showError(msg) {
  error.value = msg
  success.value = ''
}

/* ── 格式化辅助 ── */
function formatAmount(v) {
  const n = Number(v)
  if (!isFinite(n)) return '¥0.00'
  return '¥' + n.toFixed(2)
}

function formatTime(record) {
  const beijing = record.created_at_beijing || record.create_time_beijing
  if (beijing) return String(beijing).replace('T', ' ').replace('Z', '').replace('+08:00', '')
  const raw = record.created_at || record.create_time || record.created || record.time
  if (!raw) return '--'
  const d = new Date(raw)
  if (isNaN(d.getTime())) return String(raw)
  return d.toLocaleString('zh-CN', { hour12: false })
}

/* ── 统计卡（total / pending / paid / admin_cleared 的计数与金额）── */
function pick(obj, keys, fallback) {
  if (!obj) return fallback
  for (const k of keys) {
    if (obj[k] != null) return obj[k]
  }
  return fallback
}

const derived = computed(() => {
  const acc = {
    total: { c: 0, a: 0 },
    paid: { c: 0, a: 0 },
    pending: { c: 0, a: 0 },
    admin_cleared: { c: 0, a: 0 },
  }
  for (const r of records.value) {
    const amt = Number(r.amount) || 0
    acc.total.c++
    acc.total.a += amt
    if (r.status === 'paid') { acc.paid.c++; acc.paid.a += amt }
    else if (r.status === 'pending') { acc.pending.c++; acc.pending.a += amt }
    else if (r.status === 'admin_cleared') { acc.admin_cleared.c++; acc.admin_cleared.a += amt }
  }
  return acc
})

const statCards = computed(() => {
  const s = summary.value
  const d = derived.value
  return [
    {
      key: 'total', label: '总计',
      count: pick(s, ['total_count', 'total'], d.total.c),
      amount: pick(s, ['total_amount'], d.total.a),
      cls: 'text-[var(--accent)]',
    },
    {
      key: 'pending', label: '待支付',
      count: pick(s, ['pending_count'], d.pending.c),
      amount: pick(s, ['pending_amount'], d.pending.a),
      cls: 'text-amber-600',
    },
    {
      key: 'paid', label: '已支付',
      count: pick(s, ['paid_count'], d.paid.c),
      amount: pick(s, ['paid_amount'], d.paid.a),
      cls: 'text-green-600',
    },
    {
      key: 'admin_cleared', label: '管理员清除',
      count: pick(s, ['admin_cleared_count'], d.admin_cleared.c),
      amount: pick(s, ['admin_cleared_amount'], d.admin_cleared.a),
      cls: 'text-sky-600',
    },
  ]
})

const totalPages = computed(() => Math.max(1, Math.ceil((Number(total.value) || 0) / pageSize.value)))

/* ── API：加载账单列表 ── */
async function loadList(toPage) {
  if (toPage) page.value = toPage
  loading.value = true
  clearMessages()
  try {
    const params = new URLSearchParams()
    if (schoolInput.value.trim()) params.set('school_username', schoolInput.value.trim())
    if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
    params.set('page', String(page.value))
    params.set('page_size', String(pageSize.value))
    const data = await callRawAPI('/api/admin/billing/list?' + params.toString(), 'GET')
    records.value = data.billings || data.records || data.list || data.items || data.data || []
    summary.value = data.summary || null
    total.value = pick(data, ['total', 'total_count'], null)
      ?? pick(data.summary, ['total_count', 'total'], records.value.length)
    loaded.value = true
  } catch (e) {
    showError(e.message || '加载账单列表失败')
  } finally {
    loading.value = false
  }
}

function doSearch() {
  loadList(1)
}
function prevPage() {
  if (page.value > 1) loadList(page.value - 1)
}
function nextPage() {
  if (page.value < totalPages.value) loadList(page.value + 1)
}

/* ── API：添加账单 ── */
function openAdd() {
  addForm.value = { school_username: '', mode: 'count', count: 1, amount: 0, reason: '' }
  formError.value = ''
  showAddModal.value = true
}

async function submitAdd() {
  const school = addForm.value.school_username.trim()
  if (!school) { formError.value = '请输入学校账号'; return }
  if (addForm.value.mode === 'count' && !(Number(addForm.value.count) >= 1)) {
    formError.value = '按次数模式下，次数需 ≥ 1'
    return
  }
  if (addForm.value.mode === 'amount' && !(Number(addForm.value.amount) > 0)) {
    formError.value = '按金额模式下，金额需大于 0'
    return
  }
  adding.value = true
  formError.value = ''
  try {
    const body = {
      school_username: school,
      mode: addForm.value.mode,
      reason: addForm.value.reason.trim(),
    }
    if (addForm.value.mode === 'count') body.count = Number(addForm.value.count)
    else body.amount = Number(addForm.value.amount)

    const data = await callRawAPI('/api/admin/billing/add', 'POST', body)
    const bid = pick(data, ['billing_id'], null) ?? pick(data.billing, ['billing_id'], null)
    const amt = pick(data, ['amount'], null) ?? pick(data.billing, ['amount'], null)
    let msg = '账单添加成功'
    if (bid != null) msg += `（账单号 ${bid}${amt != null ? '，金额 ' + formatAmount(amt) : ''}）`
    showAddModal.value = false
    showSuccess(msg)
    await loadList()
  } catch (e) {
    formError.value = e.message || '添加账单失败'
  } finally {
    adding.value = false
  }
}

/* ── API：编辑账单 ── */
function openEdit(record) {
  editRecord.value = record
  editForm.value = {
    amount: Number(record.amount) || 0,
    status: ['pending', 'paid', 'admin_cleared'].includes(record.status) ? record.status : 'pending',
    reason: record.reason || '',
  }
  formError.value = ''
  showEditModal.value = true
}

async function submitEdit() {
  if (!editRecord.value) return
  const amt = Number(editForm.value.amount)
  if (!(amt > 0)) { formError.value = '金额需大于 0'; return }
  editing.value = true
  formError.value = ''
  try {
    await callRawAPI('/api/admin/billing/update', 'POST', {
      billing_id: editRecord.value.billing_id,
      school_username: editRecord.value.school_username,
      reason: editForm.value.reason.trim(),
      amount: amt,
      status: editForm.value.status,
    })
    showEditModal.value = false
    showSuccess('账单已更新')
    await loadList()
  } catch (e) {
    formError.value = e.message || '更新账单失败'
  } finally {
    editing.value = false
  }
}

/* ── API：删除账单 ── */
async function deleteBilling(record) {
  if (!confirm(`确定要删除账单「${record.billing_id}」吗？此操作不可恢复。`)) return
  clearMessages()
  try {
    await callRawAPI('/api/admin/billing/delete', 'POST', {
      billing_id: record.billing_id,
      school_username: record.school_username,
    })
    showSuccess('账单已删除')
    await loadList()
  } catch (e) {
    showError(e.message || '删除账单失败')
  }
}

onMounted(() => loadList(1))
</script>

<template>
  <div class="space-y-4">
    <!-- 标题 + 操作 -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-[var(--ink)]">账单管理</h2>
        <p class="text-sm text-[var(--ink-secondary)]">查询所有用户或指定用户的账单记录</p>
      </div>
      <div class="flex items-center gap-2">
        <button class="btn btn-secondary" :disabled="loading" @click="loadList(page)">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button class="btn btn-primary" @click="openAdd">添加账单</button>
      </div>
    </div>

    <!-- 提示 -->
    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&times;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-500/10 text-red-500 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&times;</button>
    </div>

    <!-- 搜索栏 -->
    <div class="panel p-4 flex flex-wrap items-end gap-3">
      <div class="flex-1 min-w-[180px]">
        <label class="block text-xs text-[var(--ink-secondary)] mb-1">学校账号筛选</label>
        <input
          v-model="schoolInput"
          type="text"
          class="input-field w-full"
          placeholder="输入学校账号筛选（留空查询有权限全部）"
          @keyup.enter="doSearch"
        />
      </div>
      <div class="flex-[2] min-w-[220px]">
        <label class="block text-xs text-[var(--ink-secondary)] mb-1">关键词搜索</label>
        <input
          v-model="keyword"
          type="text"
          class="input-field w-full"
          placeholder="搜索昵称 / 用户名 / 手机号 / 学号 / 账单号 / 订单号 / 流水号"
          @keyup.enter="doSearch"
        />
      </div>
      <button class="btn btn-primary" :disabled="loading" @click="doSearch">搜索</button>
    </div>

    <!-- 统计卡 -->
    <div v-if="loaded && records.length" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div v-for="card in statCards" :key="card.key" class="panel p-4">
        <div class="text-xs text-[var(--ink-secondary)]">{{ card.label }}</div>
        <div class="mt-1 text-2xl font-semibold" :class="card.cls">{{ card.count }}</div>
        <div class="text-xs text-[var(--ink-muted)] mt-0.5">{{ formatAmount(card.amount) }}</div>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <!-- 空态 -->
    <div v-else-if="loaded && records.length === 0" class="panel py-16 text-center">
      <div class="text-4xl mb-2">📄</div>
      <p class="text-sm text-[var(--ink-secondary)]">暂无账单记录</p>
    </div>

    <!-- 账单表格 -->
    <div v-else-if="records.length" class="panel overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-[var(--border-color)]">
          <tr>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">账单号</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">学校账号</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">用户</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">金额</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">状态</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">订单 / 流水</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">创建时间</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in records"
            :key="r.billing_id"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <td class="px-3 py-2 font-mono whitespace-nowrap">{{ r.billing_id }}</td>
            <td class="px-3 py-2 whitespace-nowrap">
              <div>{{ r.school_username || '--' }}</div>
              <div v-if="r.reason" class="text-xs text-[var(--ink-muted)] max-w-[200px] truncate" :title="r.reason">
                {{ r.reason }}
              </div>
            </td>
            <td class="px-3 py-2">
              <div class="font-medium">{{ r.nickname || r.username || '--' }}</div>
              <div class="text-xs text-[var(--ink-muted)]">
                <span v-if="r.username">@{{ r.username }}</span>
                <span v-if="r.phone"> · {{ r.phone }}</span>
                <span v-if="r.student_number"> · 学号 {{ r.student_number }}</span>
              </div>
            </td>
            <td class="px-3 py-2 whitespace-nowrap font-medium">{{ formatAmount(r.amount) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs" :class="statusInfo(r.status).cls">
                <span>{{ statusInfo(r.status).icon }}</span>
                <span>{{ statusInfo(r.status).label }}</span>
              </span>
            </td>
            <td class="px-3 py-2 whitespace-nowrap text-xs text-[var(--ink-secondary)]">
              <div v-if="r.order_id">订单 {{ r.order_id }}</div>
              <div v-if="r.trade_no">流水 {{ r.trade_no }}</div>
              <div v-if="!r.order_id && !r.trade_no">--</div>
            </td>
            <td class="px-3 py-2 whitespace-nowrap text-xs text-[var(--ink-secondary)]">{{ formatTime(r) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">
              <div class="flex items-center gap-1">
                <button class="btn btn-ghost text-xs px-2 py-1" @click="openEdit(r)">编辑</button>
                <button class="btn btn-danger text-xs px-2 py-1" @click="deleteBilling(r)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="loaded && records.length" class="flex flex-wrap items-center justify-end gap-2 text-sm text-[var(--ink-secondary)]">
      <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
      <button class="btn btn-secondary text-xs px-2 py-1" :disabled="page <= 1 || loading" @click="prevPage">上一页</button>
      <button class="btn btn-secondary text-xs px-2 py-1" :disabled="page >= totalPages || loading" @click="nextPage">下一页</button>
    </div>

    <!-- 添加账单弹窗 -->
    <AppModal :visible="showAddModal" title="添加账单" width="max-w-md" @close="showAddModal = false">
      <div class="space-y-4">
        <div v-if="formError" class="px-3 py-2 rounded-lg text-sm bg-red-500/10 text-red-500">{{ formError }}</div>

        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">学校账号 *</label>
          <input v-model="addForm.school_username" type="text" class="input-field w-full" placeholder="输入学校账号" />
        </div>

        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">计费模式</label>
          <div class="flex items-center gap-4">
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="addForm.mode" type="radio" value="count" /> 按次数
            </label>
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input v-model="addForm.mode" type="radio" value="amount" /> 按金额
            </label>
          </div>
        </div>

        <div v-if="addForm.mode === 'count'">
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">次数 *</label>
          <input v-model.number="addForm.count" type="number" min="1" step="1" class="input-field w-full" placeholder="生成账单的次数" />
        </div>
        <div v-else>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">金额（元）*</label>
          <input v-model.number="addForm.amount" type="number" min="0.01" step="0.01" class="input-field w-full" placeholder="账单金额" />
        </div>

        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">原因 / 说明</label>
          <input v-model="addForm.reason" type="text" class="input-field w-full" placeholder="选填，记录添加原因" />
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button class="btn btn-secondary" @click="showAddModal = false">取消</button>
          <button class="btn btn-primary" :disabled="adding" @click="submitAdd">
            {{ adding ? '提交中...' : '确认添加' }}
          </button>
        </div>
      </div>
    </AppModal>

    <!-- 编辑账单弹窗 -->
    <AppModal :visible="showEditModal" title="编辑账单" width="max-w-md" @close="showEditModal = false">
      <div class="space-y-4">
        <div v-if="formError" class="px-3 py-2 rounded-lg text-sm bg-red-500/10 text-red-500">{{ formError }}</div>

        <div v-if="editRecord" class="text-xs text-[var(--ink-muted)]">
          账单号 {{ editRecord.billing_id }} · 学校账号 {{ editRecord.school_username }}
        </div>

        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">金额（元）*</label>
          <input v-model.number="editForm.amount" type="number" min="0.01" step="0.01" class="input-field w-full" />
        </div>

        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">状态</label>
          <select v-model="editForm.status" class="select-field w-full">
            <option value="pending">待支付</option>
            <option value="paid">已支付</option>
            <option value="admin_cleared">管理员清除</option>
          </select>
        </div>

        <div>
          <label class="block text-sm text-[var(--ink-secondary)] mb-1">原因 / 说明</label>
          <input v-model="editForm.reason" type="text" class="input-field w-full" placeholder="选填，记录修改原因" />
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button class="btn btn-secondary" @click="showEditModal = false">取消</button>
          <button class="btn btn-primary" :disabled="editing" @click="submitEdit">
            {{ editing ? '保存中...' : '保存修改' }}
          </button>
        </div>
      </div>
    </AppModal>
  </div>
</template>
