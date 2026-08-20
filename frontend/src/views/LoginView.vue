<template>
  <div class="page auth-page">
    <div class="panel auth-panel">
      <h1>登录 StudyDash</h1>
      <p class="muted">登录后管理你的任务和专注记录</p>

      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>用户名</span>
          <input v-model.trim="username" class="input" placeholder="用户名" autocomplete="username" required />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" class="input" type="password" placeholder="密码" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button class="btn primary wide" type="submit" :disabled="submitting">
          {{ submitting ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="muted center">
        还没有账号？
        <router-link :to="{ name: 'register', query: $route.query }">去注册</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  if (!username.value || !password.value) return
  submitting.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    const redirect = typeof route.query.redirect === 'string' && route.query.redirect ? route.query.redirect : ''
    router.push(redirect || (auth.isAdmin ? '/admin' : '/'))
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>