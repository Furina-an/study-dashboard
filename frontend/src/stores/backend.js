import { defineStore } from 'pinia'
import { api } from '../api'

let timer = null

export const useBackendStore = defineStore('backend', {
  state: () => ({
    status: 'unknown', // unknown | online | offline
    checking: false,
  }),
  actions: {
    async check() {
      this.checking = true
      try {
        await api.health()
        this.status = 'online'
      } catch {
        this.status = 'offline'
      } finally {
        this.checking = false
      }
      return this.status
    },
    startPolling(intervalMs = 15000) {
      this.stopPolling()
      this.check()
      timer = setInterval(() => this.check(), intervalMs)
    },
    stopPolling() {
      if (timer) {
        clearInterval(timer)
        timer = null
      }
    },
  },
})
