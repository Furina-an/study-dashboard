import { defineStore } from 'pinia'
import { api } from '../api'

export const useReviewsStore = defineStore('reviews', {
  state: () => ({
    reviews: [],
    status: 'due',
    loading: false,
    error: '',
  }),
  getters: {
    dueReviews: (state) => state.reviews.filter((r) => !r.reviewed_at),
  },
  actions: {
    async fetch(status = this.status) {
      this.status = status
      this.loading = true
      this.error = ''
      try {
        this.reviews = await api.listReviews(status)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async complete(id) {
      const updated = await api.completeReview(id)
      const index = this.reviews.findIndex((r) => r.id === id)
      if (index !== -1) this.reviews[index] = updated
      return updated
    },
    async completeDue() {
      const result = await api.completeDueReviews()
      if (result.completed > 0) await this.fetch(this.status)
      return result
    },
    reviewById(id) {
      return this.reviews.find((r) => r.id === id)
    },
  },
})
