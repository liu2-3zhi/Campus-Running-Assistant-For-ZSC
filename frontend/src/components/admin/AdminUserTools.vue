<script setup>
import { ref, computed, onMounted } from 'vue'
import { callRawAPI } from '@/services/api'
import AppModal from '@/components/common/AppModal.vue'

const props = defineProps({ username: { type: String, required: true }, mode: { type: String, required: true } })
const emit = defineEmits(['close', 'updated'])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const success = ref('')
const accounts = ref({})
const logs = ref([])
const logTab = ref('login_history')
const permissionData = ref({})
const permissionValues = ref({})
const schoolForm = ref(null)
const schoolFormError = ref('')
const schoolIsNew = ref(false)
const schoolDetail = ref(null)
const detailLoading = ref(false)
const detailError = ref('')
const detailVisible = ref(false)
const title = computed(() => ({ accounts: '学校账户管理', logs: '用户日志', permissions: '管理用户权限' })[props.mode])
const schoolAccounts = computed(() => Object.entries(accounts.value).map(([school_username, account]) => ({
  school_username,
  password: typeof account === 'string' ? account : account?.password || '',
  ua: typeof account === 'object' && account ? account.ua || '' : '',
})))

const permissionLabels = {
  login: '登录系统', execute_task: '执行任务', execute_multi_account: '执行多账号任务',
  use_attendance: '使用签到功能', view_logs: '查看日志', clear_logs: '清空日志',
  manage_users: '管理用户', manage_permissions: '管理权限', reset_user_password: '重置用户密码',
  view_audit_logs: '查看审计日志', view_all_sessions: '查看系统中的所有会话',
  force_logout_users: '强制用户登出', manage_system: '修改系统配置',
  create_permission_groups: '创建权限组', delete_permission_groups: '删除权限组', modify_permission_groups: '修改权限组',
  auto_fill_password: '查看所有学校账号密码', import_offline: '导入离线文件', export_data: '导出数据',
  import_data: '导入数据', backup_data: '备份数据', modify_params: '修改参数',
  manage_own_sessions: '管理自己的会话', manage_user_sessions: '管理用户会话', view_session_details: '查看会话详情',
  view_captcha_history: '查看图形化验证码历史', god_mode: '查看所有会话',
  use_login_button: '使用登录按钮', use_multi_account_button: '使用多账号控制台按钮', use_import_button: '导入离线文件',
  view_messages: '查看留言板', post_messages: '发表留言', delete_own_messages: '删除自己的留言',
  delete_any_messages: '删除任何留言', view_all_messages: '查看所有留言', modify_config: '修改配置',
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    let result
    if (props.mode === 'accounts') {
      result = await callRawAPI(`/auth/get_user_school_accounts_only?username=${encodeURIComponent(props.username)}`, 'GET')
    } else if (props.mode === 'logs') {
      result = await callRawAPI(`/api/admin/logs/${logTab.value}?username=${encodeURIComponent(props.username)}`, 'GET')
    } else {
      result = await callRawAPI('/auth/admin/get_user_permissions', 'POST', { username: props.username })
    }
    if (result.success === false) throw new Error(result.message || '加载失败')
    if (props.mode === 'accounts') accounts.value = result.accounts || {}
    else if (props.mode === 'logs') logs.value = logTab.value === 'audit' ? [...(result.logs || [])].reverse() : result.logs || []
    else {
      permissionData.value = result
      permissionValues.value = { ...result.all_permissions }
    }
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function permissionDifference(key) {
  const current = !!permissionValues.value[key]
  const base = !!permissionData.value.group_permissions?.[key]
  return current === base ? '' : current ? 'added' : 'removed'
}

async function savePermissions() {
  if (saving.value || permissionData.value.group === 'super_admin') return
  saving.value = true
  error.value = ''
  const added_permissions = {}
  const removed_permissions = {}
  for (const key of Object.keys(permissionValues.value)) {
    const difference = permissionDifference(key)
    if (difference === 'added') added_permissions[key] = true
    if (difference === 'removed') removed_permissions[key] = true
  }
  try {
    const result = await callRawAPI('/auth/admin/set_user_permission', 'POST', { username: props.username, added_permissions, removed_permissions })
    if (result.success === false) throw new Error(result.message || '保存失败')
    emit('updated')
    emit('close')
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function editSchool(account = null) {
  schoolIsNew.value = !account
  schoolForm.value = account ? { ...account } : { school_username: '', password: '', ua: '' }
  schoolFormError.value = ''
}

async function saveSchool() {
  if (saving.value || !schoolForm.value) return
  const form = schoolForm.value
  if (!form.school_username.trim() || !form.password.trim()) {
    schoolFormError.value = '学校账号和密码不能为空'
    return
  }
  saving.value = true
  schoolFormError.value = ''
  try {
    const result = await callRawAPI(`/api/admin/school_account/${schoolIsNew.value ? 'save' : 'update'}`, 'POST', {
      auth_username: props.username, school_username: form.school_username.trim(), password: form.password.trim(), ua: form.ua.trim(),
    })
    if (result.success === false) throw new Error(result.message || '保存失败')
    schoolForm.value = null
    await loadData()
    success.value = result.message || '学校账户已保存'
    emit('updated')
  } catch (e) {
    schoolFormError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function deleteSchool(account) {
  if (saving.value || !confirm(`确定要删除学校账户 ${account.school_username} 吗？此操作不可恢复。`)) return
  saving.value = true
  error.value = ''
  try {
    const result = await callRawAPI('/api/admin/school_account/delete', 'POST', { auth_username: props.username, school_username: account.school_username })
    if (result.success === false) throw new Error(result.message || '删除失败')
    await loadData()
    success.value = result.message || '学校账户已删除'
    emit('updated')
  } catch (e) {
    error.value = e.message || '删除失败'
  } finally {
    saving.value = false
  }
}

async function showSchoolDetail(account) {
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  schoolDetail.value = null
  try {
    const result = await callRawAPI(`/api/admin/backup-info?school_username=${encodeURIComponent(account.school_username)}`, 'GET')
    if (result.success === false) throw new Error(result.message || '加载详情失败')
    const data = typeof result.data === 'string' ? JSON.parse(result.data) : result.data || {}
    const stats = await callRawAPI('/api/school_account/stats', 'POST', { school_username: account.school_username }).catch(() => null)
    schoolDetail.value = { ...data, ...(stats?.success ? stats.data : {}), school_username: account.school_username }
  } catch (e) {
    detailError.value = e.message || '加载详情失败'
  } finally {
    detailLoading.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <AppModal :visible="true" :title="title" width="max-w-3xl" @close="emit('close')">
    <div class="space-y-4">
      <p class="text-sm text-slate-600">用户: <strong class="text-sky-600">{{ username }}</strong><template v-if="mode === 'permissions'"> · 基础权限组: {{ permissionData.group || '--' }}</template></p>
      <div v-if="error" class="rounded-lg bg-red-50 p-3 text-sm text-red-600">{{ error }}</div>
      <div v-if="success" class="rounded-lg bg-green-50 p-3 text-sm text-green-700">{{ success }}</div>
      <div v-if="mode === 'logs'" class="flex gap-4 border-b border-slate-200">
        <button v-for="tab in [{ key: 'login_history', label: '登录日志' }, { key: 'audit', label: '操作日志' }]" :key="tab.key" class="border-b-2 px-4 py-2 font-semibold" :class="logTab === tab.key ? 'border-sky-600 text-sky-600' : 'border-transparent text-slate-400'" @click="logTab = tab.key; loadData()">{{ tab.label }}</button>
      </div>
      <div v-if="loading" class="py-10 text-center text-slate-400">加载中...</div>
      <template v-else-if="!error">
        <template v-if="mode === 'accounts'">
          <div class="flex items-center justify-between"><span class="text-sm text-slate-500">共 {{ schoolAccounts.length }} 个学校账户</span><button class="btn btn-primary !px-3 !py-1 text-sm" @click="editSchool()">新增学校账户</button></div>
          <p v-if="!schoolAccounts.length" class="py-10 text-center text-slate-400">暂无学校账户</p>
          <div v-for="account in schoolAccounts" :key="account.school_username" class="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <strong class="break-all text-lg text-slate-800">{{ account.school_username }}</strong>
              <div class="flex gap-2"><button class="btn btn-primary !px-3 !py-1 !text-xs" @click="editSchool(account)">编辑</button><button class="btn btn-danger !px-3 !py-1 !text-xs" :disabled="saving" @click="deleteSchool(account)">删除</button><button class="btn bg-sky-500 !px-3 !py-1 !text-xs text-white" @click="showSchoolDetail(account)">查看详情</button></div>
            </div>
            <p class="break-all text-sm text-slate-500">密码: <span class="ml-2 select-all font-mono text-slate-700">{{ account.password }}</span></p>
            <p class="break-all text-sm text-slate-500">User-Agent: <span class="select-all font-mono text-slate-700">{{ account.ua || '未设置' }}</span></p>
          </div>
        </template>
        <template v-else-if="mode === 'logs'">
          <p v-if="!logs.length" class="py-10 text-center text-slate-400">{{ logTab === 'audit' ? '暂无操作记录' : '暂无登录记录' }}</p>
          <div v-for="(log, index) in logs" :key="index" class="space-y-1 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
            <p class="font-semibold text-slate-700">{{ logTab === 'audit' ? '时间' : '登录时间' }}: {{ (log.datetime || 'N/A').replace('T', ' ') }}</p>
            <template v-if="logTab === 'audit'"><p>操作类型: {{ log.action || 'N/A' }}</p><p class="break-all">详情: {{ log.details || 'N/A' }}</p></template>
            <p>IP地址: {{ log.ip_address || 'N/A' }}</p>
            <template v-if="logTab !== 'audit'"><p class="break-all">设备信息: {{ log.user_agent || 'N/A' }}</p><p v-if="log.location">位置: {{ log.location }}</p><p :class="log.success === false ? 'text-red-600' : 'text-green-600'">{{ log.success === false ? '登录失败' : '登录成功' }}</p></template>
          </div>
        </template>
        <template v-else>
          <p v-if="permissionData.group === 'super_admin'" class="text-sm text-amber-600">超级管理员的权限不可修改。</p>
          <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label v-for="(_, key) in permissionValues" :key="key" class="flex cursor-pointer items-center gap-2 rounded border p-2" :class="permissionDifference(key) === 'added' ? 'border-green-200 bg-green-50' : permissionDifference(key) === 'removed' ? 'border-red-200 bg-red-50' : 'border-slate-200 hover:bg-slate-50'">
              <input v-model="permissionValues[key]" type="checkbox" class="h-4 w-4 rounded" :disabled="permissionData.group === 'super_admin'" />
              <span class="flex-1 text-sm text-slate-700">{{ permissionLabels[key] || key }}</span><span v-if="permissionDifference(key)" class="text-xs" :class="permissionDifference(key) === 'added' ? 'text-green-600' : 'text-red-600'">{{ permissionDifference(key) === 'added' ? '(新增)' : '(移除)' }}</span>
            </label>
          </div>
        </template>
      </template>
      <div class="flex justify-end gap-2"><button class="btn btn-ghost" @click="emit('close')">关闭</button><button v-if="mode === 'permissions'" class="btn btn-primary" :disabled="loading || saving || !!error || permissionData.group === 'super_admin'" @click="savePermissions">{{ saving ? '保存中...' : '保存权限' }}</button></div>
    </div>
  </AppModal>
  <AppModal :visible="!!schoolForm" :title="schoolIsNew ? '新增学校账户' : '编辑学校账户'" width="max-w-lg" @close="schoolForm = null">
    <form v-if="schoolForm" class="space-y-4" @submit.prevent="saveSchool">
      <p v-if="schoolFormError" class="text-sm text-red-600">{{ schoolFormError }}</p>
      <label class="block text-sm text-slate-600">学校账号<input v-model="schoolForm.school_username" class="input-field mt-1 w-full" :readonly="!schoolIsNew" required /></label>
      <label class="block text-sm text-slate-600">密码<input v-model="schoolForm.password" type="text" class="input-field mt-1 w-full" autocomplete="off" required /></label>
      <label class="block text-sm text-slate-600">User-Agent<textarea v-model="schoolForm.ua" class="input-field mt-1 w-full" rows="3" placeholder="留空自动生成" /></label>
      <div class="flex justify-end gap-2"><button class="btn btn-ghost" type="button" @click="schoolForm = null">取消</button><button class="btn btn-primary" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button></div>
    </form>
  </AppModal>
  <AppModal :visible="detailVisible" title="学校账户详情" width="max-w-xl" @close="detailVisible = false; schoolDetail = null">
    <p v-if="detailLoading" class="py-10 text-center text-slate-400">加载中...</p>
    <p v-else-if="detailError" class="text-red-600">{{ detailError }}</p>
    <dl v-else-if="schoolDetail" class="grid grid-cols-2 gap-3 text-sm">
      <dt>学校账号</dt><dd>{{ schoolDetail.school_username }}</dd>
      <dt>姓名</dt><dd>{{ schoolDetail.name || schoolDetail.real_name || schoolDetail.userInfo?.realName || schoolDetail.user_info?.realName || '--' }}</dd>
      <dt>学校</dt><dd>{{ schoolDetail.school_name || schoolDetail.userInfo?.schoolName || schoolDetail.user_info?.schoolName || '--' }}</dd>
      <dt>完成次数</dt><dd>{{ schoolDetail.completed_count ?? '--' }}</dd>
      <dt>欠费次数</dt><dd>{{ schoolDetail.overdue_count ?? '--' }}</dd>
    </dl>
  </AppModal>
</template>
