import { defineStore } from 'pinia'
import { api } from '../api'

export const useQuizStore = defineStore('quiz', {
  state: () => ({
    bank: [],
    subjects: [],
    mastery: null,
    loading: false,
    generateError: '',
  }),
  actions: {
    async fetchBank(subject = '', source = '') {
      this.loading = true
      try {
        this.bank = await api.listQuestions(subject, source)
        this.subjects = [...new Set(this.bank.map((q) => q.subject).filter(Boolean))].sort()
      } finally {
        this.loading = false
      }
    },
    async create(payload) {
      const item = await api.createQuestion(payload)
      this.bank.unshift(item)
      await this.fetchBank()
      return item
    },
    async update(id, payload) {
      await api.updateQuestion(id, payload)
      await this.fetchBank()
    },
    async remove(id) {
      await api.deleteQuestion(id)
      await this.fetchBank()
    },
    async generate(payload) {
      this.generateError = ''
      try {
        const created = await api.generateQuestions(payload)
        await this.fetchBank()
        return created
      } catch (e) {
        this.generateError = e.message
        throw e
      }
    },
    async fetchMastery() {
      this.mastery = await api.quizMastery()
    },
  },
})
