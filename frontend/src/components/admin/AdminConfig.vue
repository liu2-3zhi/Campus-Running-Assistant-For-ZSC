<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

/* ── state ── */
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')
const isDirty = ref(false)

/* ── section definitions ── */
const sectionMeta = {
  general: {
    label: '通用设置',
    fields: [
      { key: 'site_name', label: '站点名称', type: 'text' },
      { key: 'site_description', label: '站点描述', type: 'text' },
      { key: 'maintenance_mode', label: '维护模式', type: 'boolean' },
    ],
  },
  security: {
    label: '安全设置',
    fields: [
      { key: 'session_timeout', label: '会话超时(分钟)', type: 'number' },
      { key: 'max_login_attempts', label: '最大登录尝试', type: 'number' },
      { key: 'captcha_enabled', label: '验证码开关', type: 'boolean' },
    ],
  },
  email_sms: {
    label: '邮件/短信',
    fields: [
      { key: 'smtp_host', label: 'SMTP主机', type: 'text' },
      { key: 'smtp_port', label: 'SMTP端口', type: 'number' },
      { key: 'smtp_user', label: 'SMTP用户', type: 'text' },
      { key: 'smtp_password', label: 'SMTP密码', type: 'password' },
      { key: 'smtp_ssl', label: 'SMTP SSL', type: 'boolean' },
      { key: 'sms_gateway', label: '短信网关', type: 'text' },
      { key: 'sms_api_key', label: '短信API密钥', type: 'password' },
    ],
  },
  storage: {
    label: '存储设置',
    fields: [
      { key: 'storage_path', label: '存储路径', type: 'text' },
      { key: 'max_file_size', label: '最大文件大小(MB)', type: 'number' },
      { key: 'allowed_extensions', label: '允许的扩展名', type: 'text' },
    ],
  },
}

/* ── config form ── */
const configForm = reactive({
  general: {},
  security: {},
  email_sms: {},
  storage: {},
})

/* ── snapshot of original config for dirty detection ── */
let originalSnapshot = ''

/* ── expanded sections ── */
const expandedSections = reactive({
  general: true,
  security: false,
  email_sms: false,
  storage: false,
})

/* ── helpers ── */
function clearMessages() { error.value = ''; success.value = '' }

function toggleSection(key) {
  expandedSections[key] = !expandedSections[key]
}

function takeSnapshot() {
  originalSnapshot = JSON.stringify(configForm)
}

/* ── dirty watcher ── */
watch(
  () => JSON.stringify(configForm),
  (val) => { isDirty.value = val !== originalSnapshot },
  { deep: true }
)

/* ── apply loaded data to form ── */
function applyConfig(config) {
  for (const sectionKey of Object.keys(sectionMeta)) {
    const source = config[sectionKey] || {}
    if (!configForm[sectionKey]) configForm[sectionKey] = {}
    for (const field of sectionMeta[sectionKey].fields) {
      configForm[sectionKey][field.key] = source[field.key] ?? getDefaultForType(field.type)
    }
  }
  takeSnapshot()
}

function getDefaultForType(type) {
  if (type === 'boolean') return false
  if (type === 'number') return 0
  return ''
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
    await callRawAPI('/api/admin/config/save', 'POST', { ...configForm })
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
      <div v-for="(meta, sectionKey) in sectionMeta" :key="sectionKey" class="panel p-4 mb-4">
        <button
          @click="toggleSection(sectionKey)"
          class="w-full flex items-center justify-between text-left font-medium text-[var(--ink)]"
        >
          <span>{{ meta.label }}</span>
          <span class="text-[var(--ink-muted)] transition-transform duration-200" :class="expandedSections[sectionKey] ? '' : '-rotate-90'">&#9660;</span>
        </button>
        <div v-show="expandedSections[sectionKey]" class="mt-4 space-y-3">
          <div
            v-for="field in meta.fields"
            :key="field.key"
            class="flex flex-col sm:flex-row sm:items-center gap-2"
          >
            <label class="text-sm text-[var(--ink-secondary)] sm:w-40 flex-shrink-0">{{ field.label }}</label>

            <!-- boolean toggle -->
            <template v-if="field.type === 'boolean'">
              <button
                type="button"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0"
                :class="configForm[sectionKey]?.[field.key] ? 'bg-[var(--accent)]' : 'bg-gray-300'"
                @click="configForm[sectionKey][field.key] = !configForm[sectionKey][field.key]"
              >
                <span
                  class="inline-block h-4 w-4 rounded-full bg-white transition-transform"
                  :class="configForm[sectionKey]?.[field.key] ? 'translate-x-6' : 'translate-x-1'"
                />
              </button>
              <span class="text-xs text-[var(--ink-muted)]">{{ configForm[sectionKey]?.[field.key] ? '已启用' : '已禁用' }}</span>
            </template>

            <!-- number input -->
            <template v-else-if="field.type === 'number'">
              <input
                type="number"
                class="input-field sm:max-w-xs"
                v-model.number="configForm[sectionKey][field.key]"
              />
            </template>

            <!-- password input -->
            <template v-else-if="field.type === 'password'">
              <input
                type="password"
                class="input-field flex-1"
                v-model="configForm[sectionKey][field.key]"
                autocomplete="off"
              />
            </template>

            <!-- text input (default) -->
            <template v-else>
              <input
                type="text"
                class="input-field flex-1"
                v-model="configForm[sectionKey][field.key]"
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
