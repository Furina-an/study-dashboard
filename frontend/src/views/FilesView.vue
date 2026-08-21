<template>
  <div class="page">
    <div class="page-head">
      <h1>📁 学习文件</h1>
      <p class="muted">
        上传学习资料，安全隔离存储；运营（管理员）可扫描查毒、放行并整合入库。
      </p>
    </div>

    <p v-if="store.error" class="banner error">{{ store.error }}</p>
    <p v-if="notice" class="banner info">{{ notice }}</p>

    <!-- 推荐资料库 -->
    <section v-if="recommended.length" class="panel">
      <div class="panel-head">
        <h2>📚 推荐资料库（管理员精选）</h2>
        <button class="btn small ghost" @click="loadRecommended">刷新</button>
      </div>
      <p v-if="recLoading" class="muted">加载中…</p>
      <div v-else class="file-table">
        <div class="file-row file-head">
          <span>文件</span>
          <span>分类</span>
          <span>大小</span>
          <span>上传者</span>
          <span>时间</span>
          <span>操作</span>
        </div>
        <div v-for="file in recommended" :key="file.id" class="file-row">
          <span class="file-name">
            <span class="file-icon">{{ extIcon(file.ext) }}</span>
            <span class="file-title">{{ file.original_name }}</span>
            <span v-if="file.description" class="file-desc">{{ file.description }}</span>
          </span>
          <span>{{ file.category || '—' }}</span>
          <span>{{ formatSize(file.size_bytes) }}</span>
          <span>{{ file.owner_username }}</span>
          <span class="muted">{{ formatTime(file.created_at) }}</span>
          <span class="file-actions">
            <button class="btn small" title="下载" @click="download(file)">⬇️</button>
          </span>
        </div>
      </div>
    </section>

    <!-- 上传区 -->
    <section class="panel">
      <h2>⬆️ 上传文件</h2>
      <div class="upload-row">
        <label class="btn ghost file-btn">
          {{ pickedName || '选择文件…' }}
          <input type="file" accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.md,.txt,.png,.jpg,.jpeg,.gif,.webp" @change="onPick" />
        </label>
        <input v-model="category" class="input" list="file-categories" placeholder="分类（如 数学 / 试卷 / 笔记）" maxlength="50" />
        <datalist id="file-categories">
          <option v-for="item in categoryOptions" :key="item" :value="item" />
        </datalist>
        <input v-model="description" class="input" placeholder="一句话描述（可选）" maxlength="200" />
        <button class="btn primary" :disabled="!picked || uploading" @click="doUpload">
          {{ uploading ? '上传中…' : '上传' }}
        </button>
      </div>
      <p class="muted small">
        支持 PDF / Word / PPT / Excel / Markdown / 图片，最大 {{ maxMb }}MB；文件按账号隔离存储，上传后先进入「待扫描」队列。
      </p>
    </section>

    <!-- 列表 -->
    <section class="panel">
      <div class="panel-head">
        <h2>🗂️ 文件列表（{{ store.files.length }}）</h2>
        <div class="list-actions">
          <button
            v-if="auth.isAdmin"
            class="btn small ghost"
            @click="switchScope"
          >
            {{ store.scope === 'all' ? '仅我上传' : '全部用户（管理员）' }}
          </button>
          <button class="btn small ghost" @click="store.fetch(store.scope)">刷新</button>
        </div>
      </div>

      <p v-if="store.loading" class="muted">加载中…</p>
      <p v-else-if="!store.files.length" class="muted">
        还没有文件，先上传一份学习资料吧。
      </p>
      <div v-else class="file-table">
        <div class="file-row file-head">
          <span>文件</span>
          <span>分类</span>
          <span>大小</span>
          <span>状态 / 扫描</span>
          <span v-if="auth.isAdmin">上传者</span>
          <span>时间</span>
          <span>操作</span>
        </div>
        <div v-for="file in store.files" :key="file.id" class="file-row">
          <span class="file-name">
            <span class="file-icon">{{ extIcon(file.ext) }}</span>
            <span class="file-title">{{ file.original_name }}</span>
            <span v-if="file.description" class="file-desc">{{ file.description }}</span>
          </span>
          <span>{{ file.category || '—' }}</span>
          <span>{{ formatSize(file.size_bytes) }}</span>
          <span class="file-tags">
            <span class="tag" :class="statusClass(file.status)">{{ statusLabel(file.status) }}</span>
            <span class="tag" :class="scanClass(file.scan_status)">{{ scanLabel(file.scan_status) }}</span>
            <span v-if="file.integrated" class="tag tag-ok">✅ 已整合</span>
          </span>
          <span v-if="auth.isAdmin">{{ file.owner_username }}</span>
          <span class="muted">{{ formatTime(file.created_at) }}</span>
          <span class="file-actions">
            <button
              class="btn small"
              :disabled="file.status === 'quarantined' && !auth.isAdmin"
              :title="file.status === 'quarantined' && !auth.isAdmin ? '文件已被隔离' : ''"
              @click="download(file)"
            >
              ⬇️
            </button>
            <button class="btn small danger" @click="remove(file)">🗑️</button>
            <template v-if="auth.isAdmin">
              <button class="btn small" @click="setStatus(file, 'approved')">放行</button>
              <button class="btn small" @click="setStatus(file, 'quarantined')">隔离</button>
              <button class="btn small ghost" @click="rescan(file)">扫描</button>
              <button class="btn small ghost" @click="toggleIntegrate(file)">
                {{ file.integrated ? '取消整合' : '标记整合' }}
              </button>
            </template>
          </span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'
import { useFilesStore } from '../stores/files'
import { useSettingsStore } from '../stores/settings'

const auth = useAuthStore()
const store = useFilesStore()
const settings = useSettingsStore()

const picked = ref(null)
const pickedName = computed(() => (picked.value ? picked.value.name : ''))
const category = ref('')
const description = ref('')
const uploading = ref(false)
const notice = ref('')
const maxMb = computed(() => settings.settings?.max_upload_mb || 20)
const categoryOptions = ['数学', '英语', '专业课', '笔记', '试卷', '真题', '其他']
const recommended = ref([])
const recLoading = ref(false)

async function loadRecommended() {
  recLoading.value = true
  try {
    recommended.value = await api.listRecommendedFiles()
  } catch (e) {
    store.error = e.message
  } finally {
    recLoading.value = false
  }
}

function onPick(event) {
  picked.value = event.target.files?.[0] || null
}

async function doUpload() {
  if (!picked.value || uploading.value) return
  uploading.value = true
  store.error = ''
  notice.value = ''
  try {
    await store.upload(picked.value, category.value, description.value)
    notice.value = '上传成功，已进入待扫描队列'
    picked.value = null
    category.value = ''
    description.value = ''
  } catch (e) {
    store.error = e.message
  } finally {
    uploading.value = false
    store.fetch(store.scope)
  }
}

async function download(file) {
  try {
    const blob = await api.downloadFile(file.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = file.original_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    store.error = e.message
  }
}

async function remove(file) {
  if (!window.confirm(`确定删除「${file.original_name}」吗？磁盘文件将一并删除。`)) return
  try {
    await store.remove(file.id)
  } catch (e) {
    store.error = e.message
  }
}

async function setStatus(file, status) {
  try {
    await store.update(file.id, { status })
  } catch (e) {
    store.error = e.message
  }
}

async function rescan(file) {
  try {
    const row = await store.rescan(file.id)
    notice.value = row.scan_message || '扫描完成'
  } catch (e) {
    store.error = e.message
  }
}

async function toggleIntegrate(file) {
  try {
    await store.update(file.id, { integrated: !file.integrated })
  } catch (e) {
    store.error = e.message
  }
}

function switchScope() {
  store.fetch(store.scope === 'all' ? 'mine' : 'all')
}

const STATUS = {
  uploaded: ['待处理', 'tag-due'],
  approved: ['已放行', 'tag-ok'],
  rejected: ['已拒绝', 'tag-overdue'],
  quarantined: ['已隔离', 'tag-overdue'],
}
const SCAN = {
  pending: ['待扫描', 'tag-empty'],
  clean: ['安全', 'tag-ok'],
  infected: ['发现风险', 'tag-overdue'],
  error: ['扫描异常', 'tag-overdue'],
}

function statusLabel(value) {
  return (STATUS[value] || [value])[0]
}
function statusClass(value) {
  return (STATUS[value] || ['', ''])[1]
}
function scanLabel(value) {
  return (SCAN[value] || [value])[0]
}
function scanClass(value) {
  return (SCAN[value] || ['', ''])[1]
}
function extIcon(ext) {
  const map = {
    '.pdf': '📕', '.doc': '📘', '.docx': '📘', '.ppt': '📙', '.pptx': '📙',
    '.xls': '📗', '.xlsx': '📗', '.md': '📝', '.txt': '📄', '.csv': '📊',
  }
  return map[ext] || '📎'
}
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
function formatTime(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  await settings.fetch()
  await Promise.all([store.fetch(auth.isAdmin ? store.scope : 'mine'), loadRecommended()])
})
</script>
