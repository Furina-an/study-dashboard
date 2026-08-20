const API_BASE = import.meta.env.VITE_API_BASE || ''
const TOKEN_KEY = 'studydash_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request(url, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${url}`, { ...options, headers })

  if (res.status === 401 && !url.startsWith('/api/auth/')) {
    setToken(null)
    const path = window.location.pathname
    if (!path.startsWith('/login') && !path.startsWith('/register')) {
      window.location.href = '/login'
    }
  }

  if (!res.ok) {
    let detail = `请求失败（${res.status}）`
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch {
      /* 忽略解析失败 */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

function qs(params = {}) {
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
  return query ? `?${query}` : ''
}

async function fileRequest(url, options = {}) {
  const headers = { ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${url}`, { ...options, headers })

  if (res.status === 401 && !url.startsWith('/api/auth/')) {
    setToken(null)
    const path = window.location.pathname
    if (!path.startsWith('/login') && !path.startsWith('/register')) {
      window.location.href = '/login'
    }
  }
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch {
      /* 忽略解析失败 */
    }
    throw new Error(detail)
  }
  return res
}

export const api = {
  register: (data) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: (data) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/api/auth/me'),
  health: () => request('/api/health'),

  listTasks: (planId, habit) => request(`/api/tasks${qs({ plan_id: planId, habit })}`),
  createTask: (data) => request('/api/tasks', { method: 'POST', body: JSON.stringify(data) }),
  updateTask: (id, data) => request(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteTask: (id) => request(`/api/tasks/${id}`, { method: 'DELETE' }),
  checkinTask: (id) => request(`/api/tasks/${id}/checkin`, { method: 'POST' }),
  uncheckinTask: (id) => request(`/api/tasks/${id}/checkin`, { method: 'DELETE' }),

  listHabits: () => request('/api/habits'),

  createSession: (data) => request('/api/sessions', { method: 'POST', body: JSON.stringify(data) }),

  todayStats: () => request('/api/stats/today'),
  trend: (days = 7) => request(`/api/stats/trend?days=${days}`),
  heatmap: (days = 105) => request(`/api/stats/heatmap?days=${days}`),
  streak: () => request('/api/stats/streak'),

  listPlans: () => request('/api/plans'),
  createPlan: (data) => request('/api/plans', { method: 'POST', body: JSON.stringify(data) }),
  updatePlan: (id, data) => request(`/api/plans/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deletePlan: (id) => request(`/api/plans/${id}`, { method: 'DELETE' }),
  breakdownPlan: (id, data) => request(`/api/plans/${id}/breakdown`, { method: 'POST', body: JSON.stringify(data) }),

  getAiConfig: () => request('/api/ai/config'),
  saveAiConfig: (data) => request('/api/ai/config', { method: 'PUT', body: JSON.stringify(data) }),
  deleteAiConfig: () => request('/api/ai/config', { method: 'DELETE' }),
  testAiConfig: (data) => request('/api/ai/test', { method: 'POST', body: JSON.stringify(data) }),

  listReviews: (status = 'due') => request(`/api/reviews${qs({ status })}`),
  mathTree: () => request('/api/math/tree'),
  mathProgress: (itemId, done) =>
    request(`/api/math/items/${itemId}/progress`, {
      method: 'PUT',
      body: JSON.stringify({ done }),
    }),
  mathNote: (chapterId, content) =>
    request(`/api/math/chapters/${chapterId}/note`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
  mathResetProgress: () => request('/api/math/progress', { method: 'DELETE' }),
  exportBackup: () => request('/api/backup/export'),
  importBackup: (data) =>
    request('/api/backup/import', { method: 'POST', body: JSON.stringify(data) }),


  completeReview: (id) => request(`/api/reviews/${id}/complete`, { method: 'POST' }),
  completeDueReviews: () => request('/api/reviews/complete-due', { method: 'POST' }),

  getSettings: () => request('/api/settings'),
  saveSettings: (data) => request('/api/settings', { method: 'PUT', body: JSON.stringify(data) }),

  listPlanTemplates: () => request('/api/plan-templates'),
  createPlanTemplate: (data) => request('/api/plan-templates', { method: 'POST', body: JSON.stringify(data) }),
  updatePlanTemplate: (id, data) => request(`/api/plan-templates/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deletePlanTemplate: (id) => request(`/api/plan-templates/${id}`, { method: 'DELETE' }),

  listFiles: (scope = 'mine', status) => request(`/api/files${qs({ scope, status })}`),
  uploadFile: (file, category = '', description = '') => {
    const params = new URLSearchParams({
      filename: file.name,
      category,
      description,
    })
    return fileRequest(`/api/files?${params.toString()}`, {
      method: 'POST',
      body: file,
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    }).then((res) => res.json())
  },
  downloadFile: async (id) => {
    const res = await fileRequest(`/api/files/${id}/download`)
    return res.blob()
  },
  deleteFile: (id) => request(`/api/files/${id}`, { method: 'DELETE' }),
  updateFile: (id, data) => request(`/api/files/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  rescanFile: (id) => request(`/api/files/${id}/scan`, { method: 'POST' }),
  adminStats: () => request('/api/admin/stats'),
  listInvites: () => request('/api/admin/invites'),
  createInvites: (data) => request('/api/admin/invites', { method: 'POST', body: JSON.stringify(data) }),
  updateInvite: (id, data) => request(`/api/admin/invites/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteInvite: (id) => request(`/api/admin/invites/${id}`, { method: 'DELETE' }),
  listAdminUsers: () => request('/api/admin/users'),
  updateAdminUser: (id, data) => request(`/api/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
}
