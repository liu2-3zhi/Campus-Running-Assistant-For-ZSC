<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue'
import { normalizeBackendPageOrigin } from '@/services/mapBackendOrigin'
import { MAP_PROVIDER_OPTIONS, MAP_PROFILE_FIELDS, createMapConfigProfile, moveMapConfigProfile, removeMapConfigProfile } from '@/utils/mapConfigProfiles'

const map = defineModel({ type: Object, required: true })
const list = ref(null)
const newProvider = ref('amap')
const draggingId = ref('')
const message = ref('')
const error = ref('')
let pointerId = null

const providerName = provider => MAP_PROVIDER_OPTIONS.find(option => option.value === provider)?.label || provider
const optionLabel = profile => `${profile.name || '未命名配置'} · ${providerName(profile.provider)}`

async function addProfile() {
  const profile = createMapConfigProfile(newProvider.value, map.value.configs)
  map.value.configs.push(profile)
  message.value = `已添加${profile.name}`
  await nextTick()
  document.getElementById(`map-profile-${profile.id}-name`)?.focus()
}

function moveProfile(id, index) {
  map.value.configs = moveMapConfigProfile(map.value.configs, id, index)
  message.value = '配置顺序已更新'
}

function removeProfile(profile) {
  const wasSelected = map.value.frontend_config_id === profile.id || map.value.backend_config_id === profile.id
  Object.assign(map.value, removeMapConfigProfile(map.value, profile.id))
  message.value = wasSelected
    ? `已删除${profile.name}，使用此配置的前端或后端已改用${map.value.configs[0].name}`
    : `已删除${profile.name}`
}

function normalizeOrigin(profile, useCurrent = false) {
  try {
    profile.backend_page_origin = normalizeBackendPageOrigin(useCurrent ? window.location.origin : profile.backend_page_origin)
    error.value = ''
  } catch (e) { error.value = e.message }
}

function stopDrag(event) {
  if (event && event.pointerId !== pointerId) return
  window.removeEventListener('pointermove', dragProfile)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
  if (draggingId.value) message.value = '配置顺序已更新'
  draggingId.value = ''
  pointerId = null
}

function startDrag(event, id) {
  if (event.button !== 0 || event.isPrimary === false) return
  stopDrag()
  event.preventDefault()
  pointerId = event.pointerId
  draggingId.value = id
  window.addEventListener('pointermove', dragProfile, { passive: false })
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
}

function dragProfile(event) {
  if (event.pointerId !== pointerId || !list.value) return
  event.preventDefault()
  const card = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-map-config-card]')
  if (card && list.value.contains(card) && card.dataset.mapConfigCard !== draggingId.value) {
    const targetId = card.dataset.mapConfigCard
    const remaining = map.value.configs.filter(profile => profile.id !== draggingId.value)
    const target = remaining.findIndex(profile => profile.id === targetId)
    const bounds = card.getBoundingClientRect()
    const after = event.clientY > bounds.top + bounds.height / 2
    moveProfile(draggingId.value, target + (after ? 1 : 0))
  }
  let scrollHost = list.value.parentElement
  while (scrollHost && !(/auto|scroll/.test(getComputedStyle(scrollHost).overflowY) && scrollHost.scrollHeight > scrollHost.clientHeight)) {
    scrollHost = scrollHost.parentElement
  }
  const bounds = scrollHost?.getBoundingClientRect() || { top: 0, bottom: window.innerHeight }
  const amount = event.clientY < bounds.top + 48 ? -20 : event.clientY > bounds.bottom - 48 ? 20 : 0
  if (amount) (scrollHost || window).scrollBy({ top: amount })
}

onBeforeUnmount(() => stopDrag())
</script>

<template>
  <div class="space-y-4" data-map-config-editor>
    <p class="text-sm text-[var(--ink-secondary)]">同一地图供应商可添加多份配置，前端地图和后端路径规划可分别选择。拖动手柄调整卡片顺序，也可使用上移、下移按钮。</p>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <label class="space-y-1 text-sm">
        <span class="text-[var(--ink-secondary)]">前端地图配置</span>
        <select v-model="map.frontend_config_id" class="select-field" aria-label="前端地图配置">
          <option v-for="profile in map.configs" :key="profile.id" :value="profile.id">{{ optionLabel(profile) }}</option>
        </select>
      </label>
      <label class="space-y-1 text-sm">
        <span class="text-[var(--ink-secondary)]">后端路径规划配置</span>
        <select v-model="map.backend_config_id" class="select-field" aria-label="后端路径规划配置">
          <option v-for="profile in map.configs" :key="profile.id" :value="profile.id">{{ optionLabel(profile) }}</option>
        </select>
      </label>
    </div>
    <div class="flex flex-col sm:flex-row sm:items-end gap-2">
      <label class="flex-1 min-w-0 space-y-1 text-sm">
        <span class="text-[var(--ink-secondary)]">新增配置供应商</span>
        <select v-model="newProvider" class="select-field" aria-label="新增配置供应商">
          <option v-for="option in MAP_PROVIDER_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </label>
      <button type="button" class="btn btn-secondary shrink-0" @click="addProfile">添加地图配置</button>
    </div>
    <p role="status" aria-live="polite" class="text-xs text-[var(--ink-secondary)]">{{ message }}</p>
    <p v-if="error" role="alert" class="text-sm text-red-600">{{ error }}</p>
    <div ref="list" class="space-y-3" aria-label="地图配置卡片">
      <article
        v-for="(profile, index) in map.configs" :key="profile.id"
        :data-map-config-card="profile.id" :aria-label="optionLabel(profile)"
        class="border border-[var(--border-color)] rounded-lg p-3 sm:p-4 space-y-3 min-w-0"
        :class="draggingId === profile.id ? 'opacity-60 ring-2 ring-[var(--accent)]' : ''"
      >
        <div class="flex items-center gap-2 flex-wrap">
          <button type="button" class="btn btn-ghost !px-3 !py-2 touch-none cursor-grab" :aria-label="`拖动${profile.name || '地图配置'}排序`" @pointerdown="startDrag($event, profile.id)" @keydown.up.prevent="moveProfile(profile.id, index - 1)" @keydown.down.prevent="moveProfile(profile.id, index + 1)">
            <svg width="16" height="20" viewBox="0 0 16 20" fill="currentColor" aria-hidden="true"><circle cx="5" cy="4" r="1.5" /><circle cx="11" cy="4" r="1.5" /><circle cx="5" cy="10" r="1.5" /><circle cx="11" cy="10" r="1.5" /><circle cx="5" cy="16" r="1.5" /><circle cx="11" cy="16" r="1.5" /></svg>
          </button>
          <span class="font-medium text-sm flex-1">{{ index + 1 }}. {{ providerName(profile.provider) }}</span>
          <span v-if="map.frontend_config_id === profile.id" class="text-xs text-[var(--accent)]">前端使用</span>
          <span v-if="map.backend_config_id === profile.id" class="text-xs text-[var(--accent)]">后端使用</span>
          <div class="flex items-center gap-1 ml-auto">
            <button type="button" class="btn btn-ghost !px-2 !py-1 text-xs" :disabled="index === 0" :aria-label="`上移${profile.name}`" @click="moveProfile(profile.id, index - 1)">上移</button>
            <button type="button" class="btn btn-ghost !px-2 !py-1 text-xs" :disabled="index === map.configs.length - 1" :aria-label="`下移${profile.name}`" @click="moveProfile(profile.id, index + 1)">下移</button>
            <button type="button" class="btn btn-ghost !px-2 !py-1 text-xs text-red-600" :disabled="map.configs.length <= 1" :aria-label="`删除${profile.name}`" @click="removeProfile(profile)">删除</button>
          </div>
        </div>
        <div class="grid grid-cols-1 gap-3">
          <label class="space-y-1 text-sm" :for="`map-profile-${profile.id}-name`">
            <span class="text-[var(--ink-secondary)]">配置名称</span>
            <input :id="`map-profile-${profile.id}-name`" v-model="profile.name" class="input-field" maxlength="100" autocomplete="off" placeholder="例如：高德前端" />
          </label>
          <label v-for="field in MAP_PROFILE_FIELDS[profile.provider]" :key="field.key" class="space-y-1 text-sm" :for="`map-profile-${profile.id}-${field.key}`">
            <span class="text-[var(--ink-secondary)]">{{ field.label }}</span>
            <input :id="`map-profile-${profile.id}-${field.key}`" v-model="profile[field.key]" type="password" class="input-field" autocomplete="off" />
          </label>
          <div class="space-y-1 text-sm">
            <label class="text-[var(--ink-secondary)]" :for="`map-profile-${profile.id}-origin`">地图页面来源（选填）</label>
            <div class="flex flex-col sm:flex-row gap-2">
              <input :id="`map-profile-${profile.id}-origin`" v-model="profile.backend_page_origin" type="text" class="input-field flex-1 min-w-0" placeholder="https://example.com" @blur="normalizeOrigin(profile)" />
              <button type="button" class="btn btn-secondary shrink-0" @click="normalizeOrigin(profile, true)">使用当前页面来源</button>
            </div>
            <p class="text-xs text-[var(--ink-muted)]">此配置用于后端规划或前端代理时使用；留空继承全局来源。</p>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>
