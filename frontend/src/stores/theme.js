import { defineStore } from 'pinia'
import { ref } from 'vue'
import { callAPI } from '@/services/api'
import { useAuthStore } from '@/stores/auth'

// Style validation deferred to backend; availableStyles populated by loadThemeStyles()

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)
  const currentStyle = ref('default')
  const themeConfig = ref(null)
  const availableStyles = ref([])
  const backgroundImage = ref('')
  const backgroundAssignment = ref(null)

  function backgroundValue(url, mobile = false) {
    if (!url) return ''
    const alpha = mobile ? '0.12' : '0.10'
    return `linear-gradient(rgba(255,255,255,${alpha}), rgba(255,255,255,${alpha})), url("${url}") center / cover no-repeat${mobile ? '' : ' fixed'}`
  }

  function setBackgroundAssignment(assignment, bound = false) {
    const next = assignment && typeof assignment === 'object' ? assignment : null
    const pc = String(next?.pc?.image_url || '').trim()
    const mobile = String(next?.mobile?.image_url || '').trim()
    if (!pc && !mobile) return false
    const previous = backgroundAssignment.value || {}
    const merged = {
      ...previous,
      ...next,
      pc: { ...(previous.pc || {}), ...(next.pc || {}) },
      mobile: { ...(previous.mobile || {}), ...(next.mobile || {}) },
    }
    if (!pc && previous.pc?.image_url) merged.pc.image_url = previous.pc.image_url
    if (!mobile && previous.mobile?.image_url) merged.mobile.image_url = previous.mobile.image_url
    backgroundAssignment.value = merged
    backgroundImage.value = merged.pc?.image_url || merged.mobile?.image_url || ''
    const desktop = document.getElementById('auth-login-container')
    if (desktop && merged.pc?.image_url) desktop.style.background = backgroundValue(merged.pc.image_url)
    const mobileContent = document.getElementById('mobile-content')
    if (mobileContent && merged.mobile?.image_url) mobileContent.style.background = backgroundValue(merged.mobile.image_url, true)
    return true
  }

  function toggleDark() {
    isDark.value = !isDark.value
    applyDarkMode()
  }

  function setDark(dark) {
    isDark.value = dark
    applyDarkMode()
  }

  function applyDarkMode() {
    if (isDark.value) {
      document.body.classList.add('dark-mode')
    } else {
      document.body.classList.remove('dark-mode')
    }
    localStorage.setItem('theme_preference', isDark.value ? 'dark' : 'light')
  }

  async function loadThemeStyles() {
    try {
      const data = await callAPI('get_theme_styles')
      if (data?.theme_styles) {
        availableStyles.value = data.theme_styles
      }
      setBackgroundAssignment(data?.theme_background)
    } catch (_) {}
  }

  async function setStyle(styleName) {
    if (!styleName) return
    if (availableStyles.value.length > 0 && !availableStyles.value.some(s => (s.id || s) === styleName)) {
      console.warn(`[Theme] 未知的主题样式: ${styleName}`)
      return
    }

    currentStyle.value = styleName
    localStorage.setItem('theme_style', styleName)

    const auth = useAuthStore()
    if (auth.isAuthenticated) {
      try {
        const data = await callAPI('get_theme_config', { style_id: styleName })
        if (data?.css_variables || data?.config) {
          themeConfig.value = data.css_variables || data.config || data
          applyThemeConfig()
        }
      } catch (_) {}

      try {
        await callAPI('update_param', { key: 'theme_style', value: styleName })
      } catch (_) {}
    }
  }

  function applyThemeConfig() {
    if (!themeConfig.value) return
    const root = document.documentElement
    const vars = themeConfig.value.css_variables || themeConfig.value
    Object.entries(vars).forEach(([key, value]) => {
      if (key.startsWith('--')) {
        root.style.setProperty(key, value)
      }
    })
  }

  function setBackgroundImage(url) {
    if (url) backgroundImage.value = url
  }

  function initFromStorage() {
    const saved = localStorage.getItem('theme_preference')
    if (saved === 'dark') {
      isDark.value = true
      applyDarkMode()
    }
    const savedStyle = localStorage.getItem('theme_style')
    if (savedStyle) {
      currentStyle.value = savedStyle
    }
  }

  return {
    isDark, currentStyle, themeConfig, availableStyles, backgroundImage, backgroundAssignment,
    toggleDark, setDark, applyDarkMode,
    loadThemeStyles, setStyle, setBackgroundImage, setBackgroundAssignment, initFromStorage,
  }
})
