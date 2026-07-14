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
      if (data?.styles) {
        availableStyles.value = data.styles
      }
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
    backgroundImage.value = url
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
    isDark, currentStyle, themeConfig, availableStyles, backgroundImage,
    toggleDark, setDark, applyDarkMode,
    loadThemeStyles, setStyle, setBackgroundImage, initFromStorage,
  }
})
