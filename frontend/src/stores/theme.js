import { defineStore } from 'pinia'

const STORAGE_KEY = 'studydash-theme'
const ACCENT_KEY = 'studydash-accent'

function systemPrefersDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

function initialDark() {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'dark') return true
  if (saved === 'light') return false
  return systemPrefersDark()
}

export const useThemeStore = defineStore('theme', {
  state: () => ({
    dark: false,
    accent: 'indigo',
    ready: false,
  }),
  actions: {
    init() {
      if (this.ready) return
      this.dark = initialDark()
      this.accent = localStorage.getItem(ACCENT_KEY) || 'indigo'
      this.apply()
      this.ready = true
    },
    apply() {
      document.documentElement.dataset.theme = this.dark ? 'dark' : 'light'
      document.documentElement.dataset.accent = this.accent
    },
    persist() {
      localStorage.setItem(STORAGE_KEY, this.dark ? 'dark' : 'light')
      localStorage.setItem(ACCENT_KEY, this.accent)
    },
    applySettings(settings) {
      // 已登录：以云端设置为准（未加载前用 localStorage 回退）
      if (!settings) return
      const mode = settings.theme_mode || 'system'
      this.dark = mode === 'dark' ? true : mode === 'light' ? false : systemPrefersDark()
      this.accent = ['indigo', 'green', 'rose', 'amber', 'violet'].includes(settings.accent)
        ? settings.accent
        : 'indigo'
      this.apply()
      this.persist()
      this.ready = true
    },
    toggle() {
      this.dark = !this.dark
      this.apply()
      this.persist()
      return this.dark
    },
  },
})
