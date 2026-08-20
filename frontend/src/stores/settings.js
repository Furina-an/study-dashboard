import { defineStore } from 'pinia'
import { api } from '../api'
import { useThemeStore } from './theme'

export const HUB_CARD_KEYS = ['math', 'pomodoro', 'tasks', 'plans', 'reviews', 'stats', 'ai', 'files']

const HUB_CARD_LABELS = {
  math: '高数复习',
  pomodoro: '番茄专注',
  tasks: '任务管理',
  plans: '计划拆解',
  reviews: '复习提醒',
  stats: '统计看板',
  ai: 'AI 服务',
  files: '学习文件',
}

function defaultHubCards() {
  return HUB_CARD_KEYS.map((key, order) => ({ key, visible: true, order }))
}

function defaults() {
  return {
    theme_mode: 'system',
    accent: 'indigo',
    pomodoro_durations: [25, 45, 60],
    pomodoro_default: 25,
    review_intervals: [1, 2, 4, 7, 15, 30],
    habit_frequency_default: 'daily',
    default_estimated_minutes: 25,
    hub_cards: defaultHubCards(),
    task_subjects: [],
  }
}

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    settings: null,
    planTemplates: [],
    loading: false,
  }),
  getters: {
    loaded: (state) => Boolean(state.settings),
    themeMode: (state) => state.settings?.theme_mode || 'system',
    accent: (state) => state.settings?.accent || 'indigo',
    pomodoroDurations: (state) => state.settings?.pomodoro_durations?.length ? state.settings.pomodoro_durations : [25, 45, 60],
    pomodoroDefault: (state) =>
      state.settings?.pomodoro_default && state.settings.pomodoro_durations?.includes(state.settings.pomodoro_default)
        ? state.settings.pomodoro_default
        : (state.settings?.pomodoro_durations?.[0] || 25),
    reviewIntervals: (state) => state.settings?.review_intervals?.length ? state.settings.review_intervals : [1, 2, 4, 7, 15, 30],
    habitFrequencyDefault: (state) => state.settings?.habit_frequency_default || 'daily',
    defaultEstimatedMinutes: (state) => state.settings?.default_estimated_minutes || 25,
    taskSubjects: (state) => state.settings?.task_subjects || [],
    hubCards: (state) => {
      const stored = state.settings?.hub_cards
      if (!Array.isArray(stored) || !stored.length) return defaultHubCards()
      const valid = stored.filter((card) => HUB_CARD_KEYS.includes(card.key))
      // 兼容旧数据：新加入的卡片自动追加到末尾
      const present = new Set(valid.map((card) => card.key))
      const missing = defaultHubCards().filter((card) => !present.has(card.key))
      return [...valid, ...missing]
    },
  },
  actions: {
    async fetch() {
      if (this.settings || this.loading) return
      this.loading = true
      try {
        this.settings = await api.getSettings()
        useThemeStore().applySettings(this.settings)
      } catch {
        this.settings = defaults()
      } finally {
        this.loading = false
      }
    },
    async save(partial) {
      const updated = await api.saveSettings(partial)
      this.settings = { ...(this.settings || defaults()), ...updated }
      useThemeStore().applySettings(this.settings)
      return updated
    },
    async fetchPlanTemplates() {
      this.planTemplates = await api.listPlanTemplates()
      return this.planTemplates
    },
    async createPlanTemplate(payload) {
      const row = await api.createPlanTemplate(payload)
      this.planTemplates.unshift(row)
      return row
    },
    async updatePlanTemplate(id, payload) {
      const row = await api.updatePlanTemplate(id, payload)
      const index = this.planTemplates.findIndex((item) => item.id === id)
      if (index !== -1) this.planTemplates[index] = row
      return row
    },
    async removePlanTemplate(id) {
      await api.deletePlanTemplate(id)
      this.planTemplates = this.planTemplates.filter((item) => item.id !== id)
    },
    cardVisible(key) {
      const card = this.hubCards.find((item) => item.key === key)
      return card ? card.visible !== false : true
    },
    hubCardLabel(key) {
      return HUB_CARD_LABELS[key] || key
    },
    reset() {
      this.settings = null
      this.planTemplates = []
      useThemeStore().init()
    },
  },
})
