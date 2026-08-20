import { defineStore } from 'pinia'
import { api } from '../api'

export const useMathStore = defineStore('math', {
  state: () => ({
    chapters: [],
    done: 0,
    total: 0,
    loading: false,
    error: '',
  }),
  getters: {
    percent() {
      if (!this.total) return 0
      return Math.round((this.done / this.total) * 100)
    },
  },
  actions: {
    async fetchTree() {
      this.loading = true
      this.error = ''
      try {
        const data = await api.mathTree()
        this.chapters = data.chapters
        this.done = data.done
        this.total = data.total
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async setDone(itemId, done) {
      await api.mathProgress(itemId, done)
      const found = this.findItem(itemId)
      if (found) found.done = done
      this.done = this.chapters.reduce(
        (sum, ch) => sum + ch.subs.reduce((s, sub) => s + sub.items.filter((i) => i.done).length, 0),
        0,
      )
    },
    async saveNote(chapterId, content) {
      await api.mathNote(chapterId, content)
      const chapter = this.chapters.find((ch) => ch.id === chapterId)
      if (chapter) chapter.note = content
    },
    async resetProgress() {
      await api.mathResetProgress()
      for (const ch of this.chapters) {
        for (const sub of ch.subs) for (const item of sub.items) item.done = false
      }
      this.done = 0
    },
    findItem(itemId) {
      for (const ch of this.chapters) {
        for (const sub of ch.subs) {
          const item = sub.items.find((i) => i.id === itemId)
          if (item) return item
        }
      }
      return null
    },
  },
})
