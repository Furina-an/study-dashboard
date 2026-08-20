import { defineStore } from 'pinia'
import { api } from '../api'

export const useStatsStore = defineStore('stats', {
  state: () => ({
    today: null,
    trend: [],
    heatmap: [],
    streak: null,
    loading: false,
    error: '',
  }),
  actions: {
    async refresh(days = 7) {
      this.loading = true
      this.error = ''
      try {
        const [today, trend, heatmap, streak] = await Promise.all([
          api.todayStats(),
          api.trend(days),
          api.heatmap(105),
          api.streak(),
        ])
        this.today = today
        this.trend = trend
        this.heatmap = heatmap
        this.streak = streak
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async refreshToday() {
      try {
        this.today = await api.todayStats()
      } catch {
        /* 忽略 */
      }
    },
  },
})
