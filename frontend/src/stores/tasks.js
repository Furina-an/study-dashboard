import { defineStore } from 'pinia'
import { api } from '../api'

export const useTasksStore = defineStore('tasks', {
  state: () => ({
    tasks: [],
    habits: [],
    loading: false,
    error: '',
  }),
  getters: {
    todoTasks: (state) => state.tasks.filter((t) => t.status === 'todo'),
    doingTasks: (state) => state.tasks.filter((t) => t.status === 'doing'),
    doneTasks: (state) => state.tasks.filter((t) => t.status === 'done'),
    habitTasks: (state) => state.tasks.filter((t) => t.is_habit),
  },
  actions: {
    async fetchTasks(planId, habit) {
      this.loading = true
      this.error = ''
      try {
        this.tasks = await api.listTasks(planId, habit)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async addTask(payload) {
      const task = await api.createTask(payload)
      this.tasks.unshift(task)
      return task
    },
    async updateTask(id, patch) {
      const updated = await api.updateTask(id, patch)
      const index = this.tasks.findIndex((t) => t.id === id)
      if (index !== -1) this.tasks[index] = updated
      return updated
    },
    async removeTask(id) {
      await api.deleteTask(id)
      this.tasks = this.tasks.filter((t) => t.id !== id)
      this.habits = this.habits.filter((h) => h.id !== id)
    },
    async fetchHabits() {
      this.loading = true
      this.error = ''
      try {
        this.habits = await api.listHabits()
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async checkin(id) {
      const result = await api.checkinTask(id)
      await this.fetchHabits()
      return result
    },
    async uncheckin(id) {
      const result = await api.uncheckinTask(id)
      await this.fetchHabits()
      return result
    },
    habitById(id) {
      return this.habits.find((h) => h.id === id)
    },
  },
})
