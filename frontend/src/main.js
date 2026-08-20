import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import './assets/main.css'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')

// 恢复登录会话（路由守卫会等待 ready）
useAuthStore(pinia).init()
// 应用主题（挂载前，避免闪烁）
useThemeStore(pinia).init()