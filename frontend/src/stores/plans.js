import { defineStore } from 'pinia'
import { api } from '../api'

export const usePlansStore = defineStore('plans', {
  state: () => ({
    plans: [],
    loading: false,
    error: '',
  }),
  getters: {
    roots: (state) => state.plans.filter((plan) => plan.parent_id === null),
    childrenMap: (state) => {
      const map = {}
      for (const plan of state.plans) {
        const key = plan.parent_id ?? 'root'
        if (!map[key]) map[key] = []
        map[key].push(plan)
      }
      return map
    },
  },
  actions: {
    childrenOf(parentId) {
      return this.plans.filter((plan) => plan.parent_id === parentId)
    },
    planById(id) {
      return this.plans.find((plan) => plan.id === id)
    },
    async fetchPlans() {
      this.loading = true
      this.error = ''
      try {
        this.plans = await api.listPlans()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async addPlan(payload) {
      const plan = await api.createPlan(payload)
      this.plans.push(plan)
      return plan
    },
    async updatePlan(id, patch) {
      const updated = await api.updatePlan(id, patch)
      const index = this.plans.findIndex((plan) => plan.id === id)
      if (index !== -1) this.plans[index] = updated
      return updated
    },
    async removePlan(id) {
      await api.deletePlan(id)
      const doomed = new Set([id])
      let grew = true
      while (grew) {
        grew = false
        for (const plan of this.plans) {
          if (doomed.has(plan.parent_id) && !doomed.has(plan.id)) {
            doomed.add(plan.id)
            grew = true
          }
        }
      }
      this.plans = this.plans.filter((plan) => !doomed.has(plan.id))
    },
    async breakdownPlan(id, mode, templateKey, templateId) {
      const result = await api.breakdownPlan(id, {
        mode,
        template_key: templateKey || undefined,
        template_id: templateId || undefined,
      })
      this.plans.push(...result.created)
      return result.created
    },
  },
})
