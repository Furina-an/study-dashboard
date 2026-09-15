import { defineStore } from 'pinia'
import { api } from '../api'

export const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

export const COURSE_COLORS = [
  '#4f46e5',
  '#0ea5e9',
  '#059669',
  '#d97706',
  '#e11d48',
  '#7c3aed',
  '#0891b2',
  '#65a30d',
]

/** 未指定颜色时按课程名哈希取固定调色板，保证同名课程颜色稳定。 */
export function courseColor(course) {
  if (course?.color) return course.color
  let hash = 0
  for (const char of course?.name || '') {
    hash = (hash * 31 + char.codePointAt(0)) % 9973
  }
  return COURSE_COLORS[hash % COURSE_COLORS.length]
}

/** 「1-16」→ [1..16]，供可编辑预览表使用。 */
export function parseWeeksText(text) {
  const raw = String(text || '').trim()
  if (!raw) return null
  const weeks = new Set()
  const rangePattern = /(\d+)\s*[-~至到]\s*(\d+)/g
  for (const range of raw.match(rangePattern) || []) {
    const [first, second] = range.split(/[-~至到]/).map((item) => parseInt(item, 10))
    for (let week = Math.min(first, second); week <= Math.max(first, second); week += 1) {
      weeks.add(week)
    }
  }
  const rest = raw.replace(rangePattern, ' ')
  for (const token of rest.match(/\d+/g) || []) weeks.add(parseInt(token, 10))
  let list = [...weeks].filter((week) => week >= 1 && week <= 30).sort((a, b) => a - b)
  const odd = /单/.test(raw)
  const even = /双/.test(raw)
  if (list.length && odd && !even) list = list.filter((week) => week % 2 === 1)
  else if (list.length && even && !odd) list = list.filter((week) => week % 2 === 0)
  return list.length ? list : null
}

/** [1,2,3,5] → 「1-3,5」，便于在输入框里编辑。 */
export function formatWeeks(weeks) {
  if (!Array.isArray(weeks) || !weeks.length) return ''
  const sorted = [...new Set(weeks)].sort((a, b) => a - b)
  const parts = []
  let start = sorted[0]
  let prev = sorted[0]
  for (const week of sorted.slice(1)) {
    if (week === prev + 1) {
      prev = week
      continue
    }
    parts.push(start === prev ? `${start}` : `${start}-${prev}`)
    start = week
    prev = week
  }
  parts.push(start === prev ? `${start}` : `${start}-${prev}`)
  return parts.join(',')
}

export const useTimetableStore = defineStore('timetable', {
  state: () => ({
    settings: null,
    courses: [],
    loading: false,
    error: '',
  }),
  getters: {
    termStart: (state) => state.settings?.term_start || '',
    totalWeeks: (state) => state.settings?.total_weeks || 16,
    periods: (state) => state.settings?.periods || [],
    currentWeek: (state) => state.settings?.current_week || null,
    loaded: (state) => Boolean(state.settings),
  },
  actions: {
    async fetch() {
      this.loading = true
      this.error = ''
      try {
        const [settings, courses] = await Promise.all([
          api.getTimetableSettings(),
          api.listCourses(),
        ])
        this.settings = settings
        this.courses = courses
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async saveSettings(partial) {
      this.settings = await api.saveTimetableSettings(partial)
      return this.settings
    },
    async createCourse(payload) {
      const row = await api.createCourse(payload)
      this.courses.push(row)
      return row
    },
    async updateCourse(id, payload) {
      const row = await api.updateCourse(id, payload)
      const index = this.courses.findIndex((item) => item.id === id)
      if (index !== -1) this.courses[index] = row
      return row
    },
    async removeCourse(id) {
      await api.deleteCourse(id)
      this.courses = this.courses.filter((item) => item.id !== id)
    },
    async bulkSave(courses, replace) {
      const rows = await api.bulkSaveCourses(courses, replace)
      this.courses = replace ? rows : [...this.courses, ...rows]
      return rows
    },
    reset() {
      this.settings = null
      this.courses = []
      this.error = ''
    },
  },
})
