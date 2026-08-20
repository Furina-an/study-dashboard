import { defineStore } from 'pinia'
import { api, getToken, setToken } from '../api'
import { useSettingsStore } from './settings'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken() || '',
    user: null,
    ready: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    isAdmin: (state) => Boolean(state.user?.is_admin),
  },
  actions: {
    async login(username, password) {
      const data = await api.login({ username, password })
      useSettingsStore().reset()
      this.applySession(data)
    },
    async register(username, password, inviteCode) {
      const data = await api.register({
        username,
        password,
        invite_code: inviteCode,
      })
      useSettingsStore().reset()
      this.applySession(data)
    },
    applySession(data) {
      this.token = data.access_token
      this.user = data.user
      setToken(data.access_token)
    },
    logout() {
      this.token = ''
      this.user = null
      setToken(null)
    },
    async fetchMe() {
      this.user = await api.me()
    },
    async init() {
      if (this.ready) return
      if (this.token && !this.user) {
        try {
          await this.fetchMe()
        } catch {
          this.logout()
        }
      }
      this.ready = true
    },
  },
})
