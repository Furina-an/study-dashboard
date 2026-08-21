import { defineStore } from 'pinia'
import { api } from '../api'

export const useTutorStore = defineStore('tutor', {
  state: () => ({
    sessions: [],
    activeId: null,
    messages: [],
    loading: false,
    sending: false,
    error: '',
    settings: null,
  }),
  actions: {
    async fetchSessions() {
      this.sessions = await api.listTutorSessions()
    },
    async fetchSettings() {
      this.settings = await api.getTutorSettings()
    },
    async saveSettings(payload) {
      this.settings = await api.saveTutorSettings(payload)
    },
    async openSession(id) {
      this.activeId = id
      this.error = ''
      if (!id) {
        this.messages = []
        return
      }
      this.loading = true
      try {
        this.messages = await api.listTutorMessages(id)
      } finally {
        this.loading = false
      }
    },
    async send(message, subject, overrides = {}) {
      this.sending = true
      this.error = ''
      try {
        const result = await api.tutorChat({
          session_id: this.activeId,
          message,
          subject,
          ...overrides,
        })
        this.activeId = result.session_id
        this.messages = await api.listTutorMessages(result.session_id)
        await this.fetchSessions()
        return result
      } catch (e) {
        this.error = e.message
        throw e
      } finally {
        this.sending = false
      }
    },
    async remove(id) {
      await api.deleteTutorSession(id)
      if (this.activeId === id) this.activeId = null
      await this.fetchSessions()
    },
  },
})
