import { defineStore } from 'pinia'
import { api } from '../api'

export const useAiStore = defineStore('ai', {
  state: () => ({
    config: null,
    loading: false,
    test: { status: 'idle', message: '', latency: null },
  }),
  getters: {
    hasConfig: (state) => Boolean(state.config?.has_api_key),
  },
  actions: {
    async fetchConfig() {
      this.loading = true
      try {
        this.config = await api.getAiConfig()
      } finally {
        this.loading = false
      }
    },
    async test(payload) {
      this.test = { status: 'testing', message: '', latency: null }
      try {
        const result = await api.testAiConfig(payload)
        this.test = { status: 'ok', message: result.message, latency: result.latency_ms }
      } catch (e) {
        this.test = { status: 'fail', message: e.message, latency: null }
        throw e
      }
    },
    async save(payload) {
      this.config = await api.saveAiConfig(payload)
    },
    async clear() {
      await api.deleteAiConfig()
      this.config = null
    },
  },
})
