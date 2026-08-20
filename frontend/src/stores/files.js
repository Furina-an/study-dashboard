import { defineStore } from 'pinia'
import { api } from '../api'

export const useFilesStore = defineStore('files', {
  state: () => ({
    files: [],
    scope: 'mine',
    loading: false,
    error: '',
  }),
  actions: {
    async fetch(scope = this.scope) {
      this.scope = scope
      this.loading = true
      this.error = ''
      try {
        this.files = await api.listFiles(scope)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async upload(file, category, description) {
      const row = await api.uploadFile(file, category, description)
      this.files.unshift(row)
      return row
    },
    async remove(id) {
      await api.deleteFile(id)
      this.files = this.files.filter((item) => item.id !== id)
    },
    async update(id, data) {
      const row = await api.updateFile(id, data)
      const index = this.files.findIndex((item) => item.id === id)
      if (index !== -1) this.files[index] = row
      return row
    },
    async rescan(id) {
      const row = await api.rescanFile(id)
      const index = this.files.findIndex((item) => item.id === id)
      if (index !== -1) this.files[index] = row
      return row
    },
  },
})
