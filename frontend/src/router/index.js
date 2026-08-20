import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: '登录', guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../views/RegisterView.vue'),
    meta: { title: '注册', guestOnly: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { title: '首页', requiresAuth: true },
  },
  {
    path: '/pomodoro',
    name: 'pomodoro',
    component: () => import('../views/PomodoroView.vue'),
    meta: { title: '专注', requiresAuth: true },
  },
  {
    path: '/tasks',
    name: 'tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { title: '任务', requiresAuth: true },
  },
  {
    path: '/plans',
    name: 'plans',
    component: () => import('../views/PlansView.vue'),
    meta: { title: '计划', requiresAuth: true },
  },
  {
    path: '/files',
    name: 'files',
    component: () => import('../views/FilesView.vue'),
    meta: { title: '文件', requiresAuth: true },
  },
  {
    path: '/reviews',
    name: 'reviews',
    component: () => import('../views/ReviewsView.vue'),
    meta: { title: '复习', requiresAuth: true },
  },
  {
    path: '/math',
    name: 'math',
    component: () => import('../views/MathReviewView.vue'),
    meta: { title: '高数复习', requiresAuth: true },
  },
  {
    path: '/stats',
    name: 'stats',
    component: () => import('../views/StatsView.vue'),
    meta: { title: '统计', requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { title: '设置', requiresAuth: true },
  },
  {
    path: '/ai-settings',
    name: 'ai-settings',
    component: () => import('../views/AiSettingsView.vue'),
    meta: { title: 'AI 设置', requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminView.vue'),
    meta: { title: '管理后台', requiresAuth: true, requiresAdmin: true },
  },

]
const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.init()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'dashboard' }
  }
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · StudyDash` : 'StudyDash'
})

export default router
