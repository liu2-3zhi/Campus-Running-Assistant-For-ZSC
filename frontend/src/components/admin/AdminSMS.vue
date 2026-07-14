<script setup>
import { ref, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const success = ref('')
const error = ref('')

const provider = ref('aliyun')
const apiKey = ref('')
const apiSecret = ref('')
const signName = ref('')
const templateId = ref('')

const testPhone = ref('')
const testResult = ref('')
const testError = ref('')

async function fetchConfig() {
  loading.value = true
  error.value = ''
  try {
    const data = await callRawAPI('/api/admin/sms/config', 'GET')
    if (data.success && data.config) {
      provider.value = data.config.provider || 'aliyun'
      apiKey.value = data.config.api_key || ''
      apiSecret.value = data.config.api_secret || ''
      signName.value = data.config.sign_name || ''
      templateId.value = data.config.template_id || ''
    }
  } catch (e) {
    error.value = e.message || '加载短信配置失败'
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  success.value = ''
  error.value = ''
  try {
    const data = await callRawAPI('/api/admin/sms/config', 'POST', {
      provider: provider.value,
      api_key: apiKey.value,
      api_secret: apiSecret.value,
      sign_name: signName.value,
      template_id: templateId.value,
    })
    if (data.success) {
      success.value = '短信配置已保存'
    } else {
      error.value = data.message || '保存失败'
    }
  } catch (e) {
    error.value = e.message || '保存短信配置失败'
  } finally {
    saving.value = false
  }
}

async function sendTestSMS() {
  if (!testPhone.value) return
  testing.value = true
  testResult.value = ''
  testError.value = ''
  try {
    const data = await callRawAPI('/api/sms/test_send', 'POST', {
      phone: testPhone.value,
    })
    if (data.success) {
      testResult.value = '测试短信发送成功'
    } else {
      testError.value = data.message || '发送失败'
    }
  } catch (e) {
    testError.value = e.message || '发送测试短信失败'
  } finally {
    testing.value = false
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
      <!-- Provider Configuration -->
      <div class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">短信服务配置</h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">服务商</label>
            <select v-model="provider" class="select-field w-full">
              <option value="aliyun">阿里云</option>
              <option value="tencent">腾讯云</option>
              <option value="other">其他</option>
            </select>
          </div>

          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">API Key</label>
            <input v-model="apiKey" type="text" class="input-field w-full" placeholder="输入 API Key" />
          </div>

          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">API Secret</label>
            <input v-model="apiSecret" type="password" class="input-field w-full" placeholder="输入 API Secret" />
          </div>

          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">签名名称</label>
            <input v-model="signName" type="text" class="input-field w-full" placeholder="短信签名" />
          </div>

          <div>
            <label class="block text-sm text-[var(--ink-secondary)] mb-1">模板 ID</label>
            <input v-model="templateId" type="text" class="input-field w-full" placeholder="短信模板 ID" />
          </div>
        </div>

        <div class="flex justify-end">
          <button @click="saveConfig" :disabled="saving" class="btn btn-primary">
            {{ saving ? '保存中...' : '保存配置' }}
          </button>
        </div>
      </div>

      <!-- Test SMS -->
      <div class="panel p-5 space-y-4">
        <h3 class="text-base font-semibold text-[var(--ink)]">发送测试短信</h3>

        <div class="flex gap-3">
          <input
            v-model="testPhone"
            type="tel"
            class="input-field flex-1"
            placeholder="输入手机号"
          />
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
    </template>
  </div>
</template>
