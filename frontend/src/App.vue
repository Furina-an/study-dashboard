<script setup>
import { onMounted } from 'vue'
import NavBar from './components/NavBar.vue'
import { useAuthStore } from './stores/auth'
import { useBackendStore } from './stores/backend'
import { useSettingsStore } from './stores/settings'

const auth = useAuthStore()
const backend = useBackendStore()
const settings = useSettingsStore()

onMounted(async () => {
  backend.startPolling()
  if (!auth.ready) await auth.init()
  if (auth.isAuthenticated) await settings.fetch()
})
</script>

<template>
  <div class="app-shell">
    <NavBar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>
