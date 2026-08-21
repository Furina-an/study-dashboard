<template>
  <header class="navbar">
    <router-link to="/" class="brand">📚 StudyDash</router-link>
    <nav class="nav-links">
      <template v-if="auth.isAuthenticated">
        <router-link to="/" exact-active-class="active">首页</router-link>
        <router-link to="/pomodoro" active-class="active">专注</router-link>
        <router-link to="/tasks" active-class="active">任务</router-link>
        <router-link to="/plans" active-class="active">计划</router-link>
        <router-link to="/tutor" active-class="active">助教</router-link>
        <router-link to="/quiz" active-class="active">测验</router-link>
        <router-link to="/files" active-class="active">文件</router-link>
        <router-link to="/reviews" active-class="active">复习</router-link>
        <router-link to="/stats" active-class="active">统计</router-link>
        <router-link to="/math" active-class="active">高数</router-link>
        <router-link to="/ai-settings" active-class="active">AI</router-link>
        <router-link v-if="auth.isAdmin" to="/admin" active-class="active">管理</router-link>
        <router-link to="/settings" class="nav-icon" title="设置">⚙️</router-link>
        <span class="nav-divider"></span>
        <span class="user-chip">👤 {{ auth.user?.username }}</span>
        <button
          class="backend-pill"
          :class="backend.status"
          :title="backendTip"
          @click="backend.check()"
        >
          <span class="dot"></span>{{ backendLabel }}
        </button>
        <button class="btn small" @click="logout">退出</button>
      </template>
      <template v-else>
        <router-link to="/login">登录</router-link>
        <router-link to="/register">注册</router-link>
      </template>
    </nav>
    <button
      class="btn small theme-toggle"
      :title="theme.dark ? '切换到浅色模式' : '切换到深色模式'"
      @click="toggleTheme"
    >
      {{ theme.dark ? '☀️' : '🌙' }}
    </button>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useBackendStore } from '../stores/backend'
import { useSettingsStore } from '../stores/settings'
import { useThemeStore } from '../stores/theme'

const auth = useAuthStore()
const backend = useBackendStore()
const settings = useSettingsStore()
const theme = useThemeStore()
const router = useRouter()

const backendLabel = computed(() => {
  if (backend.status === 'online') return '后端在线'
  if (backend.status === 'offline') return '后端未启动'
  return backend.checking ? '检测中…' : '后端检测'
})

const backendTip = computed(() => {
  if (backend.status === 'offline') {
    return '后端未启动：双击 start.bat（或 启动后端.bat）启动，点击重新检测'
  }
  return '后端健康状态（每 15 秒自动检测，点击立即检测）'
})

onMounted(() => backend.startPolling())
onBeforeUnmount(() => backend.stopPolling())

function toggleTheme() {
  const dark = theme.toggle()
  if (auth.isAuthenticated && settings.settings) {
    settings.save({ theme_mode: dark ? 'dark' : 'light' }).catch(() => {})
  }
}

function logout() {
  auth.logout()
  settings.reset()
  router.push('/login')
}
</script>
