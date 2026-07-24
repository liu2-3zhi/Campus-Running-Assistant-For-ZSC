<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { callAPI, callRawAPI } from '@/services/api'
import AppModal from '@/components/common/AppModal.vue'

// ── 列表状态 ────────────────────────────────────────────────
const accounts = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')
const restoringUser = ref('')

// ── 详情弹窗状态 ────────────────────────────────────────────
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const detail = ref(null)
const detailUsername = ref('')

// ── 冲突输入弹窗（Promise 化）───────────────────────────────
const prompt = reactive({
  visible: false,
  title: '',
  message: '',
  label: '',
  placeholder: '',
  input: '',
  allowEmpty: false,
  confirmText: '确定',
})
let promptResolver = null

// ── 恢复流程内部游标（贯穿冲突循环）─────────────────────────
const _restoreAs = ref('')
const _phoneOverride = ref(null)
const _forcePhoneClear = ref(false)

const BILLING_STATUS_LABELS = {
  pending: '待支付',
  paid: '已支付',
  closed: '已关闭',
  refunded_partial: '部分退款',
  refunded_full: '全额退款',
  admin_cleared: '管理员清除',
}

const accountCount = computed(() => accounts.value.length)

const sortedAccounts = computed(() => {
  return [...accounts.value].sort((a, b) =>
    String(b.deleted_at || '').localeCompare(String(a.deleted_at || ''))
  )
})

function clearMessages() {
  error.value = ''
  success.value = ''
}

function formatTime(v) {
  if (v === null || v === undefined || v === '') return '--'
  let d
  if (typeof v === 'number') {
    d = new Date(v < 1e12 ? v * 1000 : v)
  } else {
    d = new Date(v)
  }
  if (isNaN(d.getTime())) return String(v)
  return d.toLocaleString('zh-CN')
}

function formatRuns(v) {
  if (v === -1 || v === '-1') return '无限制'
  if (v === null || v === undefined || v === '') return '0'
  return String(v)
}

function billingStatusLabel(status) {
  return BILLING_STATUS_LABELS[status] || status || '--'
}

function avatarSrc(url) {
  if (!url || url === 'default_avatar.png') return '/default_avatar.png'
  if (/^https?:\/\//.test(url) || url.startsWith('/api/avatar/')) return url
  return url.startsWith('/') ? url : `/${url}`
}

function onAvatarError(e) {
  if (e?.target) e.target.src = '/default_avatar.png'
}

// ── 加载已删除账号列表 ──────────────────────────────────────
async function loadAccounts() {
  loading.value = true
  clearMessages()
  try {
    const data = await callRawAPI('/api/admin/removed_accounts', 'GET')
    const obj = (data && data.removed_accounts) || {}
    accounts.value = Object.entries(obj).map(([username, info]) => ({
      username,
      ...info,
    }))
  } catch (e) {
    error.value = e.message || '加载已删除账号列表失败'
  } finally {
    loading.value = false
  }
}

// ── 查看详情 ────────────────────────────────────────────────
async function openDetail(username) {
  detailUsername.value = username
  detail.value = null
  detailError.value = ''
  detailLoading.value = true
  detailVisible.value = true
  try {
    const data = await callRawAPI(
      `/api/admin/removed_account_detail?auth_username=${encodeURIComponent(username)}`,
      'GET'
    )
    if (data && data.success && data.detail) {
      detail.value = data.detail
    } else {
      detailError.value = (data && data.message) || '获取详情失败'
    }
  } catch (e) {
    detailError.value = e.message || '获取已删除账号详情失败'
  } finally {
    detailLoading.value = false
  }
}

// ── 冲突输入弹窗 ────────────────────────────────────────────
function openPrompt(opts) {
  return new Promise((resolve) => {
    prompt.title = opts.title || ''
    prompt.message = opts.message || ''
    prompt.label = opts.label || ''
    prompt.placeholder = opts.placeholder || ''
    prompt.input = opts.value || ''
    prompt.allowEmpty = !!opts.allowEmpty
    prompt.confirmText = opts.confirmText || '确定'
    prompt.visible = true
    promptResolver = resolve
  })
}

function confirmPrompt() {
  const v = (prompt.input || '').trim()
  if (!v && !prompt.allowEmpty) return
  prompt.visible = false
  const r = promptResolver
  promptResolver = null
  if (r) r({ confirmed: true, value: v })
}

function cancelPrompt() {
  prompt.visible = false
  const r = promptResolver
  promptResolver = null
  if (r) r({ confirmed: false, value: '' })
}

// 用户名冲突 → 提示输入新用户名
async function resolveUsernameConflict() {
  const r = await openPrompt({
    title: '用户名冲突',
    message: '该用户名已存在，请输入新的用户名以完成恢复。',
    label: '新用户名',
    placeholder: '输入新的用户名',
    value: _restoreAs.value,
    confirmText: '继续恢复',
  })
  if (!r.confirmed || !r.value) return false
  _restoreAs.value = r.value
  return true
}

// 手机号冲突 → 提示输入新手机号（留空则清空）
async function resolvePhoneConflict() {
  const r = await openPrompt({
    title: '手机号冲突',
    message: '该手机号已被其他账号绑定。请输入新的手机号，或留空以清空手机号后恢复。',
    label: '新手机号',
    placeholder: '输入新手机号（留空 = 清空手机号）',
    value: '',
    allowEmpty: true,
    confirmText: '继续恢复',
  })
  if (!r.confirmed) return false
  if (!r.value) {
    _phoneOverride.value = ''
    _forcePhoneClear.value = true
  } else {
    _phoneOverride.value = r.value
    _forcePhoneClear.value = false
  }
  return true
}

function isUsernameConflict(msg) {
  return msg.includes('用户名') && msg.includes('已存在')
}

function isPhoneConflict(msg) {
  return msg.includes('手机号') && msg.includes('已被')
}

// ── 恢复账号（内置用户名/手机号冲突循环处理）────────────────
async function restoreAccount(authUsername) {
  if (
    !window.confirm(
      `确定要恢复账号「${authUsername}」吗？\n恢复后该账号将重新出现在系统中。`
    )
  ) {
    return false
  }

  clearMessages()
  restoringUser.value = authUsername
  _restoreAs.value = authUsername
  _phoneOverride.value = null
  _forcePhoneClear.value = false

  try {
    for (let attempt = 0; attempt < 10; attempt++) {
      const body = { auth_username: authUsername, restore_as: _restoreAs.value }
      if (_phoneOverride.value !== null) body.phone_override = _phoneOverride.value
      if (_forcePhoneClear.value) body.force_phone_clear = true

      try {
        const data = await callRawAPI('/api/admin/restore_account', 'POST', body)
        if (data && data.success) {
          success.value =
            data.message || `账号「${data.restored_as || _restoreAs.value}」已成功恢复`
          await loadAccounts()
          return true
        }
        // 200 但 success=false：防御性处理可能携带的 conflict 字段
        if (data && data.conflict === 'username') {
          if (await resolveUsernameConflict()) continue
          return false
        }
        if (data && data.conflict === 'phone') {
          if (await resolvePhoneConflict()) continue
          return false
        }
        error.value = (data && data.message) || '恢复失败'
        return false
      } catch (e) {
        // callRawAPI 对 409 会抛错，冲突信息仅存于 message 中
        const msg = e.message || ''
        if (isUsernameConflict(msg)) {
          if (await resolveUsernameConflict()) continue
          return false
        }
        if (isPhoneConflict(msg)) {
          if (await resolvePhoneConflict()) continue
          return false
        }
        error.value = msg || '恢复账号失败'
        return false
      }
    }
    error.value = '恢复失败：冲突处理次数过多，请稍后重试'
    return false
  } finally {
    restoringUser.value = ''
  }
}

onMounted(loadAccounts)
</script>

<template>
  <div class="space-y-4">
    <!-- 标题栏 -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-[var(--ink)]">恢复账号</h2>
        <p class="text-sm text-[var(--ink-secondary)]">从删除记录中恢复已删除的用户账号</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-sm text-[var(--ink-secondary)]">
          共 <strong class="text-[var(--ink)]">{{ accountCount }}</strong> 个已删除账号
        </span>
        <button class="btn btn-secondary text-sm" :disabled="loading" @click="loadAccounts">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- Alerts -->
    <div v-if="success" class="p-3 rounded-lg bg-[var(--success)]/10 text-[var(--success)] flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&times;</button>
    </div>
    <div v-if="error" class="p-3 rounded-lg bg-red-500/10 text-red-500 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&times;</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载中...</div>

    <!-- 列表 -->
    <div v-else class="panel overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-[var(--border-color)]">
          <tr>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">账号</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">手机号</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">可用次数</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">2FA</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">最后登录</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">注销时间</th>
            <th class="text-left px-3 py-2 text-[var(--ink-secondary)] font-medium whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="sortedAccounts.length === 0">
            <td colspan="7" class="px-3 py-8 text-center text-[var(--ink-secondary)]">
              暂无已删除账号记录
            </td>
          </tr>
          <tr
            v-for="acc in sortedAccounts"
            :key="acc.username"
            class="border-b border-[var(--border-color)] hover:bg-[var(--glass)]"
          >
            <td class="px-3 py-2">
              <div class="flex items-center gap-2">
                <img
                  :src="avatarSrc(acc.avatar_url)"
                  class="w-8 h-8 rounded-full object-cover bg-[var(--glass)] shrink-0"
                  alt="avatar"
                  @error="onAvatarError"
                />
                <div class="min-w-0">
                  <div class="font-mono text-[var(--ink)] truncate">{{ acc.username }}</div>
                  <div class="text-xs text-[var(--ink-secondary)] truncate">{{ acc.nickname || acc.username }}</div>
                </div>
              </div>
            </td>
            <td class="px-3 py-2 font-mono">{{ acc.phone || '--' }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatRuns(acc.available_runs) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ acc['2fa_enabled'] ? '已开启' : '未开启' }}</td>
            <td class="px-3 py-2 whitespace-nowrap">
              <div>{{ formatTime(acc.last_login) }}</div>
              <div class="text-xs text-[var(--ink-secondary)]">
                {{ acc.last_login_ip || '--' }}
                <span v-if="acc.last_login_city && acc.last_login_city !== '未知'">· {{ acc.last_login_city }}</span>
              </div>
            </td>
            <td class="px-3 py-2 whitespace-nowrap">{{ formatTime(acc.deleted_at) }}</td>
            <td class="px-3 py-2">
              <div class="flex items-center gap-2">
                <button class="btn btn-secondary text-xs px-2 py-1" @click="openDetail(acc.username)">详情</button>
                <button
                  class="btn btn-primary text-xs px-2 py-1"
                  :disabled="restoringUser === acc.username"
                  @click="restoreAccount(acc.username)"
                >
                  {{ restoringUser === acc.username ? '恢复中...' : '恢复' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 详情弹窗 -->
    <AppModal :visible="detailVisible" title="已删除账号详情" width="max-w-2xl" @close="detailVisible = false">
      <div class="max-h-[70vh] overflow-y-auto pr-1 space-y-5">
        <div v-if="detailLoading" class="py-10 text-center text-[var(--ink-secondary)]">加载中...</div>
        <div v-else-if="detailError" class="p-3 rounded-lg bg-red-500/10 text-red-500">{{ detailError }}</div>

        <template v-else-if="detail">
          <!-- 基础信息 -->
          <div class="flex items-center gap-3">
            <img
              :src="avatarSrc(detail.avatar_url)"
              class="w-12 h-12 rounded-full object-cover bg-[var(--glass)]"
              alt="avatar"
              @error="onAvatarError"
            />
            <div>
              <div class="font-mono font-semibold text-[var(--ink)]">{{ detail.auth_username }}</div>
              <div class="text-sm text-[var(--ink-secondary)]">{{ detail.nickname }}</div>
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div><span class="text-[var(--ink-secondary)]">登录 IP：</span><span class="text-[var(--ink)]">{{ detail.last_login_ip || '--' }}</span></div>
            <div><span class="text-[var(--ink-secondary)]">最后登录：</span><span class="text-[var(--ink)]">{{ formatTime(detail.last_login) }}</span></div>
            <div><span class="text-[var(--ink-secondary)]">注册时间：</span><span class="text-[var(--ink)]">{{ formatTime(detail.register_time) }}</span></div>
            <div><span class="text-[var(--ink-secondary)]">注销时间：</span><span class="text-[var(--ink)]">{{ formatTime(detail.deleted_at) }}</span></div>
          </div>

          <!-- 有权限学校账号 -->
          <div>
            <h4 class="text-sm font-semibold text-[var(--ink)] mb-2">有权限学校账号（{{ (detail.school_accounts || []).length }}）</h4>
            <div v-if="(detail.school_accounts || []).length" class="flex flex-wrap gap-2">
              <span
                v-for="sa in detail.school_accounts"
                :key="sa"
                class="px-2 py-1 rounded-md text-xs font-mono bg-[var(--glass)] text-[var(--ink)]"
              >{{ sa }}</span>
            </div>
            <p v-else class="text-sm text-[var(--ink-secondary)]">无</p>
          </div>

          <!-- 权限组 / 权限 -->
          <div>
            <h4 class="text-sm font-semibold text-[var(--ink)] mb-2">权限组</h4>
            <p class="text-sm text-[var(--ink)]">
              {{ (detail.permission_group && detail.permission_group.name) || '--' }}
              <span class="text-[var(--ink-secondary)] font-mono">（{{ (detail.permission_group && detail.permission_group.key) || '--' }}）</span>
            </p>
            <div class="mt-2">
              <div class="text-xs text-[var(--ink-secondary)] mb-1">最终生效权限</div>
              <div v-if="detail.permissions && (detail.permissions.enabled_permissions || []).length" class="flex flex-wrap gap-1.5">
                <span
                  v-for="p in detail.permissions.enabled_permissions"
                  :key="p"
                  class="px-2 py-0.5 rounded text-xs font-mono bg-[var(--success)]/10 text-[var(--success)]"
                >{{ p }}</span>
              </div>
              <p v-else class="text-sm text-[var(--ink-secondary)]">无</p>
            </div>
            <div v-if="detail.permissions && detail.permissions.user_custom_permissions" class="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div>
                <span class="text-[var(--ink-secondary)]">自定义追加：</span>
                <span class="text-[var(--ink)] font-mono">{{ (detail.permissions.user_custom_permissions.added || []).join('、') || '无' }}</span>
              </div>
              <div>
                <span class="text-[var(--ink-secondary)]">自定义移除：</span>
                <span class="text-[var(--ink)] font-mono">{{ (detail.permissions.user_custom_permissions.removed || []).join('、') || '无' }}</span>
              </div>
            </div>
          </div>

          <!-- 留言记录 -->
          <div v-if="detail.messages">
            <h4 class="text-sm font-semibold text-[var(--ink)] mb-2">
              留言记录（现存 {{ detail.messages.total_current || 0 }} / 已删 {{ detail.messages.total_deleted || 0 }}）
            </h4>
            <div v-if="(detail.messages.records || []).length" class="space-y-2">
              <div
                v-for="(m, i) in detail.messages.records"
                :key="m.id || i"
                class="p-2 rounded-md bg-[var(--glass)] text-sm"
              >
                <div class="flex items-center justify-between gap-2 mb-1">
                  <span
                    class="px-1.5 py-0.5 rounded text-xs"
                    :class="m.source === 'deleted' ? 'bg-red-500/10 text-red-500' : 'bg-[var(--success)]/10 text-[var(--success)]'"
                  >{{ m.status_text || (m.source === 'deleted' ? '已删' : '现存') }}</span>
                  <span class="text-xs text-[var(--ink-secondary)]">{{ formatTime(m.timestamp) }}</span>
                </div>
                <div class="text-[var(--ink)] break-words">{{ m.content }}</div>
              </div>
            </div>
            <p v-else class="text-sm text-[var(--ink-secondary)]">无</p>
          </div>

          <!-- 账单记录 -->
          <div v-if="detail.billing">
            <h4 class="text-sm font-semibold text-[var(--ink)] mb-2">账单记录</h4>
            <div v-if="detail.billing.stats" class="flex flex-wrap gap-3 text-xs text-[var(--ink-secondary)] mb-2">
              <span>总计 <strong class="text-[var(--ink)]">{{ detail.billing.stats.total || 0 }}</strong></span>
              <span>待支付 <strong class="text-[var(--ink)]">{{ detail.billing.stats.pending || 0 }}</strong></span>
              <span>已支付 <strong class="text-[var(--ink)]">{{ detail.billing.stats.paid || 0 }}</strong></span>
              <span>管理员清除 <strong class="text-[var(--ink)]">{{ detail.billing.stats.admin_cleared || 0 }}</strong></span>
              <span>待支付金额 <strong class="text-[var(--ink)]">¥{{ detail.billing.stats.pending_amount || 0 }}</strong></span>
            </div>
            <div v-if="(detail.billing.records || []).length" class="space-y-1.5">
              <div
                v-for="(b, i) in detail.billing.records"
                :key="b.billing_id || i"
                class="p-2 rounded-md bg-[var(--glass)] text-sm flex items-center justify-between gap-2"
              >
                <div class="min-w-0">
                  <div class="font-mono text-[var(--ink)] truncate">{{ b.school_username }}</div>
                  <div class="text-xs text-[var(--ink-secondary)] truncate">{{ b.reason || '--' }} · {{ formatTime(b.created_at_beijing || b.created_at) }}</div>
                </div>
                <div class="text-right shrink-0">
                  <div class="text-[var(--ink)]">¥{{ b.amount }}</div>
                  <div class="text-xs text-[var(--ink-secondary)]">{{ billingStatusLabel(b.status) }}</div>
                </div>
              </div>
            </div>
            <p v-else class="text-sm text-[var(--ink-secondary)]">无</p>
          </div>
        </template>
      </div>

      <div class="mt-4 flex justify-end">
        <button class="btn btn-secondary" @click="detailVisible = false">关闭</button>
      </div>
    </AppModal>

    <!-- 冲突输入弹窗 -->
    <AppModal :visible="prompt.visible" :title="prompt.title" width="max-w-md" @close="cancelPrompt">
      <div class="space-y-3">
        <p v-if="prompt.message" class="text-sm text-[var(--ink-secondary)]">{{ prompt.message }}</p>
        <div>
          <label v-if="prompt.label" class="block text-sm text-[var(--ink-secondary)] mb-1">{{ prompt.label }}</label>
          <input
            v-model="prompt.input"
            type="text"
            class="input-field w-full"
            :placeholder="prompt.placeholder"
            @keyup.enter="confirmPrompt"
          />
        </div>
        <div class="flex justify-end gap-2 pt-1">
          <button class="btn btn-secondary" @click="cancelPrompt">取消</button>
          <button class="btn btn-primary" @click="confirmPrompt">{{ prompt.confirmText }}</button>
        </div>
      </div>
    </AppModal>
  </div>
</template>
