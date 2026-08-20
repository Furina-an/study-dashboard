<template>
  <div class="page auth-page">
    <div class="panel auth-panel">
      <h1>注册账号</h1>
      <p class="muted">注册需要管理员发放的邀请码（本地默认主码 studydash）</p>

      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>用户名</span>
          <input v-model.trim="username" class="input" placeholder="3-50 位字母/数字/下划线" autocomplete="username" required />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" class="input" type="password" placeholder="至少 6 位" autocomplete="new-password" required />
        </label>
        <label class="field">
          <span>邀请码</span>
          <input v-model.trim="inviteCode" class="input" placeholder="请输入邀请码" required />
        </label>
        <p v-if="error" class="error-text">{{ error }}</p>
        <button class="btn primary wide" type="submit" :disabled="submitting">
          {{ submitting ? '注册中…' : '注册并登录' }}
        </button>
      </form>

      <p class="muted center">
        已有账号？
        <router-link :to="{ name: 'login', query: $route.query }">去登录</router-link>
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
const inviteCode = ref('')
const error = ref('')
const submitting = ref(false)

async function submit() {
  if (!username.value || !password.value || !inviteCode.value) return
  submitting.value = true
  error.value = ''
  try {
    await auth.register(username.value, password.value, inviteCode.value)
    const redirect = typeof route.query.redirect === 'string' && route.query.redirect ? route.query.redirect : ''
    router.push(redirect || (auth.isAdmin ? '/admin' : '/'))
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>