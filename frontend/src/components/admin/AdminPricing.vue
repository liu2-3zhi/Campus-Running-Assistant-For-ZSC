<script setup>
import { ref, reactive, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const loaded = ref(false)

const config = reactive({
  require_payment: false,
  per_run_cost: 0,
  default_available_runs: 0,
  show_available_runs: false,
  available_runs_format: '剩余免费次数：{available_runs} 次',
  show_available_runs_on_register: false,
  register_available_runs_hint: '注册即可得 {available_runs} 次校园跑',
})

async function loadConfig() {
  loading.value = true
  try {
    const data = await callRawAPI('/api/admin/pricing_config', 'GET')
    if (data?.success && data.config) {
      const c = data.config
      config.require_payment = !!c.require_payment
      config.per_run_cost = c.per_run_cost ?? 0
      config.default_available_runs = c.default_available_runs ?? 0
      config.show_available_runs = !!c.show_available_runs
      config.available_runs_format = c.available_runs_format || '剩余免费次数：{available_runs} 次'
      config.show_available_runs_on_register = !!c.show_available_runs_on_register
      config.register_available_runs_hint = c.register_available_runs_hint || '注册即可得 {available_runs} 次校园跑'
      loaded.value = true
    }
  } catch (e) {
    window.Swal?.fire({ icon: 'error', title: '加载失败', text: e.message || '加载价格配置失败' })
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!loaded.value) {
    window.Swal?.fire({ icon: 'warning', title: '提示', text: '请先加载配置后再保存' })
    return
  }
  if (Number(config.per_run_cost) < 0) {
    window.Swal?.fire({ icon: 'warning', title: '提示', text: '单次跑步费用不能为负数' })
    return
  }
  if (Number(config.default_available_runs) < 0) {
    window.Swal?.fire({ icon: 'warning', title: '提示', text: '默认免费次数不能为负数' })
    return
  }
  if (!config.available_runs_format || !config.available_runs_format.trim()) {
    window.Swal?.fire({ icon: 'warning', title: '提示', text: '剩余次数显示格式不能为空' })
    return
  }
  if (!config.register_available_runs_hint || !config.register_available_runs_hint.trim()) {
    window.Swal?.fire({ icon: 'warning', title: '提示', text: '注册页提示文本不能为空' })
    return
  }
  saving.value = true
  try {
    const data = await callRawAPI('/api/admin/pricing_config', 'PUT', {
      require_payment: config.require_payment,
      per_run_cost: parseFloat(Number(config.per_run_cost).toFixed(2)),
      default_available_runs: Math.max(0, Math.floor(Number(config.default_available_runs))),
      show_available_runs: config.show_available_runs,
      available_runs_format: config.available_runs_format,
      show_available_runs_on_register: config.show_available_runs_on_register,
      register_available_runs_hint: config.register_available_runs_hint,
    })
    if (data?.success) {
      window.Swal?.fire({ icon: 'success', title: '保存成功', text: '价格配置已更新', timer: 1500, showConfirmButton: false })
    } else {
      throw new Error(data?.message || '保存失败')
    }
  } catch (e) {
    window.Swal?.fire({ icon: 'error', title: '保存失败', text: e.message || '保存价格配置失败' })
  } finally {
    saving.value = false
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="space-y-4">
    <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: linear-gradient(to right, var(--glass), var(--base-color))">
      <h3 class="text-lg font-bold text-[var(--ink)] mb-2">价格配置管理</h3>
      <p class="text-sm text-[var(--ink-secondary)]">配置系统的价格策略，包括是否启用付费模式、单次跑步费用和新用户的默认免费次数。</p>
    </div>

    <div v-if="loading" class="text-center py-8 text-sm text-[var(--ink-muted)]">加载中...</div>

    <template v-else>
      <!-- 是否需要付费 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <label class="block text-sm font-semibold text-[var(--ink)] mb-1">是否需要付费</label>
            <p class="text-xs text-[var(--ink-muted)]">开启后，用户需要支付才能使用跑步服务；关闭后，所有用户可免费使用。</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer ml-4">
            <input v-model="config.require_payment" type="checkbox" class="sr-only peer" />
            <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer peer-checked:bg-[var(--accent)] peer-focus:ring-2 peer-focus:ring-[var(--accent)] after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
          </label>
        </div>
      </div>

      <!-- 单次跑步费用 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <label class="block text-sm font-semibold text-[var(--ink)] mb-1">单次跑步费用（元）</label>
        <p class="text-xs text-[var(--ink-muted)] mb-2">用于计算用户欠费金额 = 欠费次数 × 单次费用。设置为0表示免费。</p>
        <input v-model.number="config.per_run_cost" type="number" class="input-field" min="0" step="0.01" placeholder="例如：1.0" />
        <p class="text-xs text-[var(--ink-muted)] mt-1">支持小数，最多两位小数（如1.50）</p>
      </div>

      <!-- 新用户默认免费次数 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <label class="block text-sm font-semibold text-[var(--ink)] mb-1">新用户默认免费次数</label>
        <p class="text-xs text-[var(--ink-muted)] mb-2">新用户注册时自动获得的免费跑步次数。设置为0表示无免费次数。</p>
        <input v-model.number="config.default_available_runs" type="number" class="input-field" min="0" step="1" placeholder="例如：10" />
        <p class="text-xs text-[var(--ink-muted)] mt-1">必须是非负整数（如0、10、100）</p>
      </div>

      <!-- 个人资料页显示剩余次数 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <label class="block text-sm font-semibold text-[var(--ink)] mb-1">个人资料页显示剩余次数</label>
            <p class="text-xs text-[var(--ink-muted)]">开启后，用户在个人资料页面可以看到自己的剩余跑步次数。</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer ml-4">
            <input v-model="config.show_available_runs" type="checkbox" class="sr-only peer" />
            <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer peer-checked:bg-[var(--accent)] peer-focus:ring-2 peer-focus:ring-[var(--accent)] after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
          </label>
        </div>
      </div>

      <!-- 剩余次数显示格式 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <label class="block text-sm font-semibold text-[var(--ink)] mb-1">剩余次数显示格式</label>
        <p class="text-xs text-[var(--ink-muted)] mb-2">自定义剩余次数在个人资料页面的显示格式。使用 {available_runs} 作为占位符。</p>
        <input v-model="config.available_runs_format" type="text" class="input-field" placeholder="例如：剩余免费次数：{available_runs} 次" />
        <p class="text-xs text-[var(--ink-muted)] mt-1">示例：剩余免费次数：{available_runs} 次 → 剩余免费次数：10 次</p>
      </div>

      <!-- 注册页显示免费次数提示 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <div class="flex items-center justify-between">
          <div class="flex-1">
            <label class="block text-sm font-semibold text-[var(--ink)] mb-1">注册页显示免费次数提示</label>
            <p class="text-xs text-[var(--ink-muted)]">开启后，用户在注册页面可以看到注册即可获得的免费次数提示。</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer ml-4">
            <input v-model="config.show_available_runs_on_register" type="checkbox" class="sr-only peer" />
            <div class="w-11 h-6 bg-gray-300 dark:bg-gray-600 rounded-full peer peer-checked:bg-[var(--accent)] peer-focus:ring-2 peer-focus:ring-[var(--accent)] after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full"></div>
          </label>
        </div>
      </div>

      <!-- 注册页提示文本 -->
      <div class="rounded-lg border border-[var(--border-color)] p-4" style="background: var(--glass)">
        <label class="block text-sm font-semibold text-[var(--ink)] mb-1">注册页提示文本</label>
        <p class="text-xs text-[var(--ink-muted)] mb-2">自定义注册页面的免费次数提示文本。使用 {available_runs} 作为占位符。</p>
        <input v-model="config.register_available_runs_hint" type="text" class="input-field" placeholder="例如：注册即可得 {available_runs} 次校园跑" />
        <p class="text-xs text-[var(--ink-muted)] mt-1">示例：注册即可得 {available_runs} 次校园跑 → 注册即可得 10 次校园跑</p>
      </div>

      <!-- 操作按钮 -->
      <div class="grid grid-cols-2 gap-3 pt-2">
        <button class="btn btn-secondary justify-center" :disabled="loading" @click="loadConfig">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          刷新配置
        </button>
        <button class="btn btn-primary justify-center" :disabled="saving || !loaded" @click="saveConfig">
          <svg v-if="!saving" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
          {{ saving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </template>
  </div>
</template>
