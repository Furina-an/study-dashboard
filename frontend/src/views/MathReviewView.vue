<template>
  <div class="page math-page">
    <div class="page-head">
      <div>
        <h1>🧮 高数资料</h1>
        <p class="date-line">
          管理员发布的高等数学学习资料，全员可浏览下载；内容由管理员随时维护更新。
        </p>
      </div>
      <div class="head-actions">
        <button class="btn small ghost" @click="loadResources">刷新</button>
      </div>
    </div>

    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-if="notice" class="banner info">{{ notice }}</p>

    <section class="panel">
      <div class="panel-head">
        <h2>📚 资料列表（{{ resources.length }}）</h2>
      </div>
      <p v-if="loading" class="muted">加载中…</p>
      <p v-else-if="!resources.length" class="empty-state">
        管理员还没有发布高数资料，请耐心等待或联系管理员。
      </p>
      <div v-else class="file-table">
        <div class="file-row file-head">
          <span>资料</span>
          <span>文件</span>
          <span>大小</span>
          <span>发布时间</span>
          <span>操作</span>
        </div>
        <div v-for="item in resources" :key="item.id" class="file-row">
          <span class="file-name">
            <span class="file-icon">{{ extIcon(item.ext) }}</span>
            <span class="file-title">{{ item.title }}</span>
            <span v-if="item.description" class="file-desc">{{ item.description }}</span>
          </span>
          <span>{{ item.original_name }}</span>
          <span>{{ formatSize(item.size_bytes) }}</span>
          <span class="muted">{{ formatTime(item.created_at) }}</span>
          <span class="file-actions">
            <button class="btn small primary" @click="download(item)">⬇️ 下载</button>
          </span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const resources = ref([])
const loading = ref(false)
const error = ref('')
const notice = ref('')

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function extIcon(ext) {
  const map = {
    '.pdf': '📕', '.doc': '📘', '.docx': '📘', '.ppt': '📙', '.pptx': '📙',
    '.xls': '📗', '.xlsx': '📗', '.md': '📝', '.txt': '📄', '.csv': '📊',
  }
  return map[ext] || '📎'
}

async function loadResources() {
  loading.value = true
  error.value = ''
  try {
    resources.value = await api.listMathResources()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function download(item) {
  try {
    const blob = await api.downloadMathResource(item.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = item.original_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    notice.value = `开始下载：${item.original_name}`
    setTimeout(() => (notice.value = ''), 3000)
  } catch (e) {
    error.value = e.message
  }
}

onMounted(loadResources)
</script>
