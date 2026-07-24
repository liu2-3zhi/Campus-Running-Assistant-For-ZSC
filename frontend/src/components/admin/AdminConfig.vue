<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

/* ── state ── */
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')
const isDirty = ref(false)

/*
 * section 定义。
 * - save: 保存时使用的 config.ini 节名（提交给后端 /api/admin/config/save 的键）
 * - load: 加载时读取的节名（后端 /api/admin/config/load 返回结构）
 * 注意：新手帮助字段在加载时挂在 Guest 节下，但保存时需放到 Help 节，故 load/save 不同。
 */
const sections = [
  {
    save: 'Guest', load: 'Guest', label: '游客设置',
    fields: [
      { key: 'allow_guest_login', label: '允许游客登录', type: 'boolean' },
    ],
  },
  {
    save: 'Help', load: 'Guest', label: '新手帮助',
    fields: [
      { key: 'show_newbie_help', label: '显示新手帮助', type: 'boolean' },
      { key: 'newbie_help_url', label: '新手帮助链接', type: 'text' },
    ],
  },
  {
    save: 'System', load: 'System', label: '系统设置',
    fields: [
      { key: 'session_expiry_days', label: '会话有效天数', type: 'number' },
      { key: 'session_inactivity_timeout', label: '会话不活跃超时(秒)', type: 'number' },
      { key: 'session_monitor_check_interval', label: '会话监控检查间隔(秒)', type: 'number' },
      { key: 'school_accounts_dir', label: '学校账户目录', type: 'text' },
      { key: 'system_accounts_dir', label: '系统账户目录', type: 'text' },
      { key: 'permissions_file', label: '权限文件', type: 'text' },
    ],
  },
  {
    save: 'Logging', load: 'Logging', label: '日志设置',
    fields: [
      { key: 'log_rotation_size_mb', label: '日志轮转大小(MB)', type: 'number' },
      { key: 'archive_max_size_mb', label: '归档最大大小(MB)', type: 'number' },
      { key: 'random_background_cache_max_size_mb', label: '随机背景缓存上限(MB)', type: 'number' },
      { key: 'log_dir', label: '日志目录', type: 'text' },
      { key: 'archive_dir', label: '归档目录', type: 'text' },
    ],
  },
  {
    save: 'Security', load: 'Security', label: '安全设置',
    fields: [
      { key: 'password_storage', label: '密码存储方式', type: 'select', options: ['plaintext', 'sha256', 'bcrypt'] },
      { key: 'brute_force_protection', label: '暴力破解防护', type: 'boolean' },
      { key: 'login_log_retention_days', label: '登录日志保留天数', type: 'number' },
    ],
  },
  {
    save: 'IP_Location', load: 'IP_Location', label: 'IP 归属地',
    fields: [
      { key: 'query_order', label: '查询顺序(逗号分隔)', type: 'text' },
      { key: 'amap_web_api_key', label: '高德 Web API Key', type: 'password' },
      { key: 'uapipro_api_key', label: 'UAPIPro API Key', type: 'password' },
    ],
  },
  {
    save: 'API', load: 'API', label: '接口密钥',
    fields: [
      { key: 'captcha_api_key', label: '验证码 API Key', type: 'password' },
    ],
  },
  {
    save: 'Beian', load: 'Beian', label: '备案信息',
    fields: [
      { key: 'icp_number', label: 'ICP 备案号', type: 'text' },
      { key: 'show_icp', label: '显示 ICP 备案', type: 'boolean' },
      { key: 'police_number', label: '公安网备案号', type: 'text' },
      { key: 'show_police', label: '显示公安备案', type: 'boolean' },
    ],
  },
  {
    save: 'baidu_cloud', load: 'baidu_cloud', label: '百度云内容审核',
    fields: [
      { key: 'api_key', label: 'API Key', type: 'password' },
      { key: 'secret_key', label: 'Secret Key', type: 'password' },
      { key: 'strategy_id', label: '策略 ID', type: 'text' },
    ],
  },
  {
    save: 'Content_Review', load: 'Content_Review', label: '留言审核',
    fields: [
      { key: 'enable_message_review', label: '启用留言内容审核', type: 'boolean' },
    ],
  },
  {
    save: 'Features', load: 'Features', label: '账号功能',
    fields: [
      { key: 'account_cancellation_wait_hours', label: '账号注销冷静期(小时)', type: 'number' },
    ],
  },
]

/* ── config form（按 save 节名分组） ── */
const configForm = reactive({})
for (const s of sections) {
  if (!configForm[s.save]) configForm[s.save] = {}
}

/* ── snapshot of original config for dirty detection ── */
let originalSnapshot = ''

/* ── expanded sections（首个默认展开） ── */
const expandedSections = reactive({})
sections.forEach((s, i) => { expandedSections[s.save] = i === 0 })

/* ── helpers ── */
function clearMessages() { error.value = ''; success.value = '' }

function toggleSection(key) {
  expandedSections[key] = !expandedSections[key]
}

function takeSnapshot() {
  originalSnapshot = JSON.stringify(configForm)
}

function toBool(v) {
  if (typeof v === 'boolean') return v
  if (typeof v === 'number') return v !== 0
  if (typeof v === 'string') return ['true', '1', 'yes', 'on'].includes(v.trim().toLowerCase())
  return !!v
}

function coerceValue(type, raw) {
  if (type === 'boolean') return toBool(raw)
  if (type === 'number') {
    if (raw === '' || raw === null || raw === undefined) return 0
    const n = Number(raw)
    return isNaN(n) ? 0 : n
  }
  return raw === null || raw === undefined ? '' : String(raw)
}

/* ── dirty watcher ── */
watch(
  () => JSON.stringify(configForm),
  (val) => { isDirty.value = val !== originalSnapshot },
  { deep: true }
)

/* ── apply loaded data to form ── */
function applyConfig(config) {
  for (const s of sections) {
    const source = config[s.load] || {}
    if (!configForm[s.save]) configForm[s.save] = {}
    for (const field of s.fields) {
      configForm[s.save][field.key] = coerceValue(field.type, source[field.key])
    }
  }
  takeSnapshot()
}

/* ── API: load config ── */
async function loadConfig() {
  loading.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/config/load', 'GET')
    applyConfig(res.config || {})
    isDirty.value = false
  } catch (e) {
    error.value = e.message || '加载配置失败'
  } finally {
    loading.value = false
  }
}

/* ── API: save config ── */
async function saveConfig() {
  saving.value = true
  clearMessages()
  try {
    const res = await callRawAPI('/api/admin/config/save', 'POST', { ...configForm })
    if (res && res.success === false) throw new Error(res.message || '保存失败')
    success.value = '配置已保存'
    takeSnapshot()
    isDirty.value = false
  } catch (e) {
    error.value = e.message || '保存配置失败'
  } finally {
    saving.value = false
  }
}

/* ── reset: reload from server ── */
async function resetConfig() {
  await loadConfig()
  success.value = '配置已重置为服务器版本'
}

/* ── lifecycle ── */
onMounted(loadConfig)
</script>

<template>
  <div class="space-y-4">

    <!-- success / error alerts -->
    <div v-if="success" class="px-4 py-2 rounded-lg text-sm bg-green-100 text-green-700 flex items-center justify-between">
      <span>{{ success }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="success = ''">&#x2715;</button>
    </div>
    <div v-if="error" class="px-4 py-2 rounded-lg text-sm bg-red-100 text-red-700 flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="ml-2 opacity-60 hover:opacity-100" @click="error = ''">&#x2715;</button>
    </div>

    <!-- loading -->
    <div v-if="loading" class="py-12 text-center text-[var(--ink-secondary)]">加载配置中...</div>

    <!-- config form -->
    <template v-else>
      <!-- collapsible sections -->
      <div v-for="section in sections" :key="section.save" class="panel p-4 mb-4">
        <button
          @click="toggleSection(section.save)"
          class="w-full flex items-center justify-between text-left font-medium text-[var(--ink)]"
        >
          <span>{{ section.label }}</span>
          <span class="text-[var(--ink-muted)] transition-transform duration-200" :class="expandedSections[section.save] ? '' : '-rotate-90'">&#9660;</span>
        </button>
        <div v-show="expandedSections[section.save]" class="mt-4 space-y-3">
          <div
            v-for="field in section.fields"
            :key="field.key"
            class="flex flex-col sm:flex-row sm:items-center gap-2"
          >
            <label class="text-sm text-[var(--ink-secondary)] sm:w-52 flex-shrink-0">{{ field.label }}</label>

            <!-- boolean toggle -->
            <template v-if="field.type === 'boolean'">
              <button
                type="button"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0"
                :class="configForm[section.save]?.[field.key] ? 'bg-[var(--accent)]' : 'bg-gray-300'"
                @click="configForm[section.save][field.key] = !configForm[section.save][field.key]"
              >
                <span
                  class="inline-block h-4 w-4 rounded-full bg-white transition-transform"
                  :class="configForm[section.save]?.[field.key] ? 'translate-x-6' : 'translate-x-1'"
                />
              </button>
              <span class="text-xs text-[var(--ink-muted)]">{{ configForm[section.save]?.[field.key] ? '已启用' : '已禁用' }}</span>
            </template>

            <!-- select -->
            <template v-else-if="field.type === 'select'">
              <select class="select-field sm:max-w-xs" v-model="configForm[section.save][field.key]">
                <option v-for="opt in field.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
            </template>

            <!-- number input -->
            <template v-else-if="field.type === 'number'">
              <input
                type="number"
                class="input-field sm:max-w-xs"
                v-model.number="configForm[section.save][field.key]"
              />
            </template>

            <!-- password input -->
            <template v-else-if="field.type === 'password'">
              <input
                type="password"
                class="input-field flex-1"
                v-model="configForm[section.save][field.key]"
                autocomplete="off"
              />
            </template>

            <!-- text input (default) -->
            <template v-else>
              <input
                type="text"
                class="input-field flex-1"
                v-model="configForm[section.save][field.key]"
              />
            </template>
          </div>
        </div>
      </div>

      <!-- action buttons -->
      <div class="flex items-center gap-3 pt-2">
        <button
          class="btn btn-primary relative"
          :disabled="saving || !isDirty"
          @click="saveConfig"
        >
          <span v-if="isDirty" class="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-[var(--warning)] border-2 border-[var(--card-bg)]"></span>
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <button
          class="btn btn-secondary"
          :disabled="loading || saving"
          @click="resetConfig"
        >
          重置
        </button>
        <span v-if="isDirty" class="text-xs text-[var(--warning)]">有未保存的更改</span>
      </div>
    </template>

  </div>
</template>
