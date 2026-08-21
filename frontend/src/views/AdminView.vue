<template>
  <div class="admin-layout">
    <!-- 左侧导航 -->
    <aside class="admin-side">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="side-btn"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        <span class="side-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </aside>

    <!-- 右侧内容 -->
    <div class="admin-main">
      <div class="page-head">
        <h1>🛡️ 运营后台</h1>
        <p class="muted">
          邀请码控制注册人数、用户状态管理、用户上传文件审核与整合。
        </p>
      </div>

      <p v-if="error" class="banner error">{{ error }}</p>
      <p v-if="notice" class="banner info">{{ notice }}</p>

      <!-- 概览 -->
      <section v-if="activeTab === 'overview'" class="stat-cards">
        <div class="stat-card accent">
          <div class="stat-value">{{ stats.total_users }}</div>
          <div class="stat-label">注册用户</div>
          <div class="stat-sub">当前使用人数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.active_invites }}</div>
          <div class="stat-label">有效邀请码</div>
          <div class="stat-sub">启用中</div>
        </div>
        <div class="stat-card success">
          <div class="stat-value">{{ stats.unused_invites }}</div>
          <div class="stat-label">未使用邀请码</div>
          <div class="stat-sub">还可发放</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_invites }}</div>
          <div class="stat-label">累计邀请码</div>
          <div class="stat-sub">历史全部</div>
        </div>
      </section>

      <!-- 邀请码管理 -->
      <template v-else-if="activeTab === 'invites'">
        <section class="panel">
          <h2>🎟️ 生成邀请码</h2>
          <div class="form-grid">
            <label class="field">
              <span>生成数量</span>
              <input v-model.number="form.count" type="number" min="1" max="50" class="input" />
            </label>
            <label class="field">
              <span>每个码可用次数</span>
              <input v-model.number="form.maxUses" type="number" min="1" max="1000" class="input" />
            </label>
            <label class="field">
              <span>有效天数（留空=永久）</span>
              <input v-model.number="form.expiresDays" type="number" min="1" max="3650" class="input" placeholder="例如 30" />
            </label>
            <label class="field">
              <span>备注（可选）</span>
              <input v-model="form.remark" class="input" maxlength="200" placeholder="如：送给同学 / 内测第二批" />
            </label>
          </div>
          <button class="btn primary" :disabled="generating" @click="generate">
            {{ generating ? '生成中…' : '生成邀请码' }}
          </button>

          <div v-if="newCodes.length" class="new-codes">
            <div class="panel-head">
              <h3>✅ 新生成的 {{ newCodes.length }} 个邀请码</h3>
              <button class="btn small ghost" @click="copyCodes">复制全部</button>
            </div>
            <div class="code-grid">
              <code
                v-for="item in newCodes"
                :key="item.id"
                class="code-chip"
                :title="'点击复制：' + item.code"
                @click="copyOne(item.code)"
              >{{ item.code }}</code>
            </div>
            <p class="muted small">点击单个邀请码即可复制；请妥善保管，仅发给想邀请的人。</p>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2>📋 邀请码列表（{{ invites.length }}）</h2>
            <button class="btn small ghost" @click="loadInvites">刷新</button>
          </div>
          <p v-if="invitesLoading" class="muted">加载中…</p>
          <p v-else-if="!invites.length" class="muted">还没有生成过邀请码。</p>
          <div v-else class="file-table">
            <div class="file-row file-head">
              <span>邀请码</span>
              <span>使用</span>
              <span>有效期</span>
              <span>状态</span>
              <span>备注</span>
              <span>创建时间</span>
              <span>操作</span>
            </div>
            <div v-for="item in invites" :key="item.id" class="file-row">
              <span>
                <code
                  class="code-chip"
                  :class="{ dim: !item.active }"
                  :title="'点击复制'"
                  @click="copyOne(item.code)"
                >{{ item.code }}</code>
              </span>
              <span>{{ item.used_count }} / {{ item.max_uses }}</span>
              <span class="muted">{{ item.expires_at ? formatTime(item.expires_at) : '永久' }}</span>
              <span>
                <span class="tag" :class="item.active ? 'tag-ok' : ''">{{ item.active ? '启用' : '停用' }}</span>
                <span v-if="item.used_count >= item.max_uses" class="tag">已用完</span>
              </span>
              <span class="muted">{{ item.remark || '—' }}</span>
              <span class="muted">{{ formatTime(item.created_at) }}</span>
              <span class="file-actions">
                <button class="btn small" @click="toggleInvite(item)">
                  {{ item.active ? '停用' : '启用' }}
                </button>
                <button class="btn small danger" @click="removeInvite(item)">删除</button>
              </span>
            </div>
          </div>
        </section>
      </template>

      <!-- 用户管理 -->
      <section v-else-if="activeTab === 'users'" class="panel">
        <div class="panel-head">
          <h2>👥 注册用户（{{ users.length }}）</h2>
          <button class="btn small ghost" @click="loadUsers">刷新</button>
        </div>
        <p v-if="usersLoading" class="muted">加载中…</p>
        <p v-else-if="!users.length" class="muted">暂无用户。</p>
        <div v-else class="file-table">
          <div class="file-row file-head">
            <span>用户名</span>
            <span>角色</span>
            <span>状态</span>
            <span>注册时间</span>
            <span>操作</span>
          </div>
          <div v-for="user in users" :key="user.id" class="file-row">
            <span class="file-name">{{ user.username }}</span>
            <span>
              <span class="tag" :class="user.is_admin ? 'tag-ok' : ''">{{ user.is_admin ? '管理员' : '普通用户' }}</span>
            </span>
            <span>
              <span class="tag" :class="user.is_active ? 'tag-ok' : 'tag-overdue'">{{ user.is_active ? '正常' : '已禁用' }}</span>
            </span>
            <span class="muted">{{ formatTime(user.created_at) }}</span>
            <span class="file-actions">
              <button
                v-if="user.id !== authUser?.id && !user.is_admin"
                class="btn small"
                :class="user.is_active ? 'danger' : ''"
                @click="toggleUser(user)"
              >
                {{ user.is_active ? '禁用' : '启用' }}
              </button>
              <span v-else class="muted small">—</span>
            </span>
          </div>
        </div>
      </section>

      <!-- 文件运营 -->
      <section v-else-if="activeTab === 'files'" class="panel">
        <div class="panel-head">
          <h2>📁 用户文件（{{ filteredFiles.length }}）</h2>
          <div class="list-actions">
            <select v-model="fileFilter" class="input filter-select" @change="loadFiles">
              <option value="">全部状态</option>
              <option value="uploaded">待处理</option>
              <option value="approved">已放行</option>
              <option value="rejected">已拒绝</option>
              <option value="quarantined">已隔离</option>
            </select>
            <button class="btn small ghost" @click="loadFiles">刷新</button>
          </div>
        </div>
        <p v-if="filesLoading" class="muted">加载中…</p>
        <p v-else-if="!filteredFiles.length" class="muted">暂无用户上传的文件。</p>
        <div v-else class="file-table">
          <div class="file-row file-head">
            <span>文件</span>
            <span>上传者</span>
            <span>分类</span>
            <span>大小</span>
            <span>状态 / 扫描</span>
            <span>时间</span>
            <span>操作</span>
          </div>
          <div v-for="file in filteredFiles" :key="file.id" class="file-row">
            <span class="file-name">
              <span class="file-icon">{{ extIcon(file.ext) }}</span>
              <span class="file-title">{{ file.original_name }}</span>
              <span v-if="file.description" class="file-desc">{{ file.description }}</span>
            </span>
            <span>{{ file.owner_username }}</span>
            <span>{{ file.category || '—' }}</span>
            <span>{{ formatSize(file.size_bytes) }}</span>
            <span class="file-tags">
              <span class="tag" :class="statusClass(file.status)">{{ statusLabel(file.status) }}</span>
              <span class="tag" :class="scanClass(file.scan_status)">{{ scanLabel(file.scan_status) }}</span>
              <span v-if="file.integrated" class="tag tag-ok">✅ 已整合</span>
            </span>
            <span class="muted">{{ formatTime(file.created_at) }}</span>
            <span class="file-actions">
              <button class="btn small" title="下载" @click="download(file)">⬇️</button>
              <button v-if="file.status !== 'approved'" class="btn small" @click="setFileStatus(file, 'approved')">放行</button>
              <button v-if="file.status !== 'rejected'" class="btn small danger" @click="setFileStatus(file, 'rejected')">拒绝</button>
              <button v-if="file.status !== 'quarantined'" class="btn small" @click="setFileStatus(file, 'quarantined')">隔离</button>
              <button class="btn small ghost" @click="rescan(file)">扫描</button>
              <button class="btn small ghost" @click="toggleIntegrate(file)">
                {{ file.integrated ? '取消整合' : '标记整合' }}
              </button>
              <button class="btn small ghost" :class="{ 'btn-primary-text': file.is_recommended }" @click="toggleRecommend(file)">
                {{ file.is_recommended ? '★ 取消推荐' : '推荐' }}
              </button>
              <button class="btn small danger" title="删除" @click="removeFile(file)">🗑️</button>
            </span>
          </div>
        </div>
      </section>

      <!-- 安全中心 -->
      <section v-else-if="activeTab === 'security'" class="panel">
        <div class="panel-head">
          <h2>🛡️ 安全中心 · 文件查杀</h2>
          <div class="list-actions">
            <button class="btn small primary" :disabled="scanning" @click="runScanAll">
              {{ scanning ? '扫描中…' : '一键全量扫描' }}
            </button>
            <button class="btn small ghost" @click="loadSecurity">刷新</button>
          </div>
        </div>
        <p class="muted small">
          扫描为只读操作，不会修改或删除任何用户文件；命中风险的文件仅移入隔离区，可随时放行恢复。
        </p>
        <div v-if="scanSummary" class="stat-cards">
          <div class="stat-card">
            <div class="stat-value">{{ scanSummary.total_files }}</div>
            <div class="stat-label">文件总数</div>
          </div>
          <div class="stat-card success">
            <div class="stat-value">{{ scanSummary.clean }}</div>
            <div class="stat-label">安全</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ scanSummary.pending }}</div>
            <div class="stat-label">待扫描</div>
          </div>
          <div class="stat-card" :class="{ 'has-risk': scanSummary.infected }">
            <div class="stat-value">{{ scanSummary.infected }}</div>
            <div class="stat-label">风险（已隔离）</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ scanSummary.error }}</div>
            <div class="stat-label">扫描异常</div>
          </div>
        </div>
        <p v-if="scanSummary" class="muted small">
          杀毒命令：{{ scanSummary.scan_command_configured ? scanSummary.scan_command : '未配置 SCAN_COMMAND（查毒预留，可在环境变量配置 clamscan）' }}
        </p>

        <h3 style="margin-top: 18px">📜 扫描日志</h3>
        <p v-if="scanLogsLoading" class="muted">加载中…</p>
        <div v-else-if="scanLogs.length" class="file-table">
          <div class="file-row file-head">
            <span>时间</span>
            <span>方式</span>
            <span>文件数</span>
            <span>安全</span>
            <span>风险</span>
            <span>异常</span>
            <span>说明</span>
          </div>
          <div v-for="log in scanLogs" :key="log.id" class="file-row">
            <span class="muted">{{ formatTime(log.created_at) }}</span>
            <span>{{ log.action === 'manual' ? '手动全量' : log.action }}</span>
            <span>{{ log.total_files }}</span>
            <span>{{ log.clean_count }}</span>
            <span>{{ log.infected_count }}</span>
            <span>{{ log.error_count }}</span>
            <span class="muted">{{ log.message }}</span>
          </div>
        </div>
        <p v-else class="muted">还没有扫描记录。</p>
      </section>

      <!-- 高数资料 -->
      <section v-else-if="activeTab === 'math'" class="panel">
        <h2>🧮 高数资料管理</h2>
        <p class="muted small">上传的资料会发布到「高数复习」页，所有用户可浏览下载；可随时编辑或删除。</p>
        <div class="upload-row">
          <input v-model="mathTitle" class="input" placeholder="标题（如：高数期末复习提纲）" maxlength="100" />
          <input v-model="mathDesc" class="input" placeholder="一句话描述（可选）" maxlength="500" />
          <label class="btn ghost file-btn">
            {{ mathFileName() || '选择文件…' }}
            <input type="file" accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.md,.txt,.png,.jpg,.jpeg,.gif,.webp" @change="onMathPick" />
          </label>
          <button class="btn primary" :disabled="!mathFile || mathUploading || !mathTitle.trim()" @click="doMathUpload">
            {{ mathUploading ? '上传中…' : '发布资料' }}
          </button>
        </div>

        <div class="panel-head" style="margin-top: 18px">
          <h3>📚 已发布资料（{{ mathResources.length }}）</h3>
          <button class="btn small ghost" @click="loadMathResources">刷新</button>
        </div>
        <p v-if="mathLoading" class="muted">加载中…</p>
        <p v-else-if="!mathResources.length" class="muted">还没有发布任何资料。</p>
        <div v-else class="file-table">
          <div class="file-row file-head">
            <span>标题</span>
            <span>文件</span>
            <span>大小</span>
            <span>发布时间</span>
            <span>操作</span>
          </div>
          <div v-for="item in mathResources" :key="item.id" class="file-row">
            <span class="file-name">
              <span class="file-title">{{ item.title }}</span>
              <span v-if="item.description" class="file-desc">{{ item.description }}</span>
            </span>
            <span>{{ item.original_name }}</span>
            <span>{{ formatSize(item.size_bytes) }}</span>
            <span class="muted">{{ formatTime(item.created_at) }}</span>
            <span class="file-actions">
              <button class="btn small" title="下载" @click="downloadMath(item)">⬇️</button>
              <button class="btn small" @click="editMath(item)">编辑</button>
              <button class="btn small danger" @click="removeMath(item)">删除</button>
            </span>
          </div>
        </div>

        <div v-if="mathEditing" class="new-codes">
          <div class="panel-head">
            <h3>✏️ 编辑：{{ mathEditing.title }}</h3>
            <button class="btn small ghost" @click="mathEditing = null">取消</button>
          </div>
          <input v-model="mathEditTitle" class="input" placeholder="标题" maxlength="100" style="margin-bottom: 8px" />
          <input v-model="mathEditDesc" class="input" placeholder="描述（可选）" maxlength="500" style="margin-bottom: 8px" />
          <button class="btn primary" :disabled="mathSaving || !mathEditTitle.trim()" @click="saveMathEdit">
            {{ mathSaving ? '保存中…' : '保存修改' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const authUser = computed(() => auth.user)

const tabs = [
  { key: 'overview', icon: '📊', label: '概览' },
  { key: 'invites', icon: '🎟️', label: '邀请码' },
  { key: 'users', icon: '👥', label: '用户' },
  { key: 'files', icon: '📁', label: '文件运营' },
  { key: 'security', icon: '🛡️', label: '安全中心' },
  { key: 'math', icon: '🧮', label: '高数资料' },
]
const activeTab = ref('overview')

const stats = reactive({ total_users: 0, total_invites: 0, active_invites: 0, unused_invites: 0 })
const invites = ref([])
const users = ref([])
const files = ref([])
const newCodes = ref([])
const invitesLoading = ref(false)
const usersLoading = ref(false)
const filesLoading = ref(false)
const generating = ref(false)
const error = ref('')
const notice = ref('')
const fileFilter = ref('')
const filesLoaded = ref(false)
const scanSummary = ref(null)
const scanLogs = ref([])
const scanning = ref(false)
const scanLogsLoading = ref(false)
const securityLoaded = ref(false)
const mathResources = ref([])
const mathLoading = ref(false)
const mathFile = ref(null)
const mathTitle = ref('')
const mathDesc = ref('')
const mathUploading = ref(false)
const mathEditing = ref(null)
const mathEditTitle = ref('')
const mathEditDesc = ref('')
const mathSaving = ref(false)

const form = reactive({ count: 1, maxUses: 1, expiresDays: null, remark: '' })

const filteredFiles = computed(() => files.value)

function flashNotice(text) {
  notice.value = text
  setTimeout(() => (notice.value = ''), 4000)
}

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
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
function statusLabel(value) { return (STATUS[value] || [value])[0] }
function statusClass(value) { return (STATUS[value] || ['', ''])[1] }
function scanLabel(value) { return (SCAN[value] || [value])[0] }
function scanClass(value) { return (SCAN[value] || ['', ''])[1] }
function extIcon(ext) {
  const map = {
    '.pdf': '📕', '.doc': '📘', '.docx': '📘', '.ppt': '📙', '.pptx': '📙',
    '.xls': '📗', '.xlsx': '📗', '.md': '📝', '.txt': '📄', '.csv': '📊',
  }
  return map[ext] || '📎'
}

function switchTab(key) {
  activeTab.value = key
  if (key === 'files' && !filesLoaded.value) loadFiles()
  if (key === 'security' && !securityLoaded.value) loadSecurity()
  if (key === 'math' && !mathResources.value.length) loadMathResources()
}

async function loadOverview() {
  try {
    Object.assign(stats, await api.adminStats())
  } catch (e) {
    error.value = e.message
  }
}

async function loadInvites() {
  invitesLoading.value = true
  try {
    invites.value = await api.listInvites()
  } catch (e) {
    error.value = e.message
  } finally {
    invitesLoading.value = false
  }
}

async function loadUsers() {
  usersLoading.value = true
  try {
    users.value = await api.listAdminUsers()
  } catch (e) {
    error.value = e.message
  } finally {
    usersLoading.value = false
  }
}

async function loadFiles() {
  filesLoading.value = true
  try {
    files.value = await api.listFiles('all', fileFilter.value || undefined)
    filesLoaded.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    filesLoading.value = false
  }
}

async function generate() {
  error.value = ''
  generating.value = true
  try {
    const payload = {
      count: form.count || 1,
      max_uses: form.maxUses || 1,
      expires_days: form.expiresDays || null,
      remark: form.remark || '',
    }
    newCodes.value = await api.createInvites(payload)
    form.remark = ''
    flashNotice(`已生成 ${newCodes.value.length} 个邀请码，可在下方复制`)
    await loadInvites()
  } catch (e) {
    error.value = e.message
  } finally {
    generating.value = false
  }
}

async function toggleInvite(item) {
  try {
    const row = await api.updateInvite(item.id, { active: !item.active })
    item.active = row.active
  } catch (e) {
    error.value = e.message
  }
}

async function removeInvite(item) {
  if (!window.confirm(`确定删除邀请码 ${item.code} 吗？`)) return
  try {
    await api.deleteInvite(item.id)
    invites.value = invites.value.filter((entry) => entry.id !== item.id)
  } catch (e) {
    error.value = e.message
  }
}

async function toggleUser(user) {
  const action = user.is_active ? '禁用' : '启用'
  if (user.is_active && !window.confirm(`确定禁用用户「${user.username}」吗？禁用后该账号无法登录。`)) return
  try {
    const row = await api.updateAdminUser(user.id, { is_active: !user.is_active })
    user.is_active = row.is_active
    flashNotice(`已${action}用户「${user.username}」`)
  } catch (e) {
    error.value = e.message
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
    error.value = e.message
  }
}

async function removeFile(file) {
  if (!window.confirm(`确定删除「${file.original_name}」吗？磁盘文件将一并删除。`)) return
  try {
    await api.deleteFile(file.id)
    files.value = files.value.filter((item) => item.id !== file.id)
  } catch (e) {
    error.value = e.message
  }
}

async function setFileStatus(file, status) {
  try {
    const row = await api.updateFile(file.id, { status })
    Object.assign(file, row)
  } catch (e) {
    error.value = e.message
  }
}

async function rescan(file) {
  try {
    const row = await api.rescanFile(file.id)
    Object.assign(file, row)
    flashNotice(row.scan_message || '扫描完成')
  } catch (e) {
    error.value = e.message
  }
}

async function toggleIntegrate(file) {
  try {
    const row = await api.updateFile(file.id, { integrated: !file.integrated })
    Object.assign(file, row)
  } catch (e) {
    error.value = e.message
  }
}

async function toggleRecommend(file) {
  try {
    const row = await api.updateFile(file.id, { is_recommended: !file.is_recommended })
    Object.assign(file, row)
    flashNotice(row.is_recommended ? '已推荐，全员可在「推荐资料库」看到' : '已取消推荐')
  } catch (e) {
    error.value = e.message
  }
}

async function loadSecurity() {
  scanLogsLoading.value = true
  try {
    const [summary, logs] = await Promise.all([api.adminScanSummary(), api.adminScanLogs(20)])
    scanSummary.value = summary
    scanLogs.value = logs
    securityLoaded.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    scanLogsLoading.value = false
  }
}

async function runScanAll() {
  if (!window.confirm('将对全部用户文件执行一次全量扫描（只读，风险文件会移入隔离区，可放行恢复）。继续？')) return
  scanning.value = true
  error.value = ''
  try {
    const result = await api.adminScanAll()
    flashNotice(result.message)
    await loadSecurity()
    await loadFiles()
  } catch (e) {
    error.value = e.message
  } finally {
    scanning.value = false
  }
}

function mathFileName() {
  return mathFile.value ? mathFile.value.name : ''
}

function onMathPick(event) {
  mathFile.value = event.target.files?.[0] || null
}

async function loadMathResources() {
  mathLoading.value = true
  try {
    mathResources.value = await api.listMathResources()
  } catch (e) {
    error.value = e.message
  } finally {
    mathLoading.value = false
  }
}

async function doMathUpload() {
  if (!mathFile.value || !mathTitle.value.trim() || mathUploading.value) return
  mathUploading.value = true
  error.value = ''
  try {
    await api.uploadMathResource(mathFile.value, mathTitle.value.trim(), mathDesc.value.trim())
    flashNotice('资料已发布')
    mathFile.value = null
    mathTitle.value = ''
    mathDesc.value = ''
    await loadMathResources()
  } catch (e) {
    error.value = e.message
  } finally {
    mathUploading.value = false
  }
}

async function downloadMath(item) {
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
  } catch (e) {
    error.value = e.message
  }
}

function editMath(item) {
  mathEditing.value = item
  mathEditTitle.value = item.title
  mathEditDesc.value = item.description
}

async function saveMathEdit() {
  if (!mathEditing.value || mathSaving.value) return
  mathSaving.value = true
  error.value = ''
  try {
    const row = await api.updateMathResource(mathEditing.value.id, {
      title: mathEditTitle.value.trim(),
      description: mathEditDesc.value.trim(),
    })
    const index = mathResources.value.findIndex((item) => item.id === row.id)
    if (index !== -1) mathResources.value[index] = row
    flashNotice('已保存修改')
    mathEditing.value = null
  } catch (e) {
    error.value = e.message
  } finally {
    mathSaving.value = false
  }
}

async function removeMath(item) {
  if (!window.confirm(`确定删除资料「${item.title}」吗？文件将一并删除。`)) return
  try {
    await api.deleteMathResource(item.id)
    mathResources.value = mathResources.value.filter((entry) => entry.id !== item.id)
  } catch (e) {
    error.value = e.message
  }
}

async function copyOne(code) {
  try {
    await navigator.clipboard.writeText(code)
    flashNotice(`已复制：${code}`)
  } catch {
    window.prompt('请手动复制：', code)
  }
}

async function copyCodes() {
  const text = newCodes.value.map((item) => item.code).join('\n')
  try {
    await navigator.clipboard.writeText(text)
    flashNotice('已复制全部邀请码')
  } catch {
    window.prompt('请手动复制：', text)
  }
}

onMounted(async () => {
  await auth.init()
  await Promise.all([loadOverview(), loadInvites(), loadUsers()])
})
</script>

<style scoped>
.admin-layout {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}
.admin-side {
  width: 168px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  background: var(--bg-soft, #eef1fa);
  border: 1px solid var(--border, #d5dbe8);
  border-radius: var(--radius, 16px);
  position: sticky;
  top: 16px;
}
.side-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: var(--radius-sm, 10px);
  background: transparent;
  color: var(--text, #1f2430);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease, color 0.15s ease;
}
.side-btn:hover {
  background: var(--primary-soft, #e8edfd);
}
.side-btn.active {
  background: var(--primary, #4f6ef7);
  color: #fff;
  font-weight: 600;
}
.side-icon {
  font-size: 16px;
}
.admin-main {
  flex: 1;
  min-width: 0;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.new-codes {
  margin-top: 16px;
  padding: 14px;
  border: 1px dashed var(--border, #d5dbe8);
  border-radius: 12px;
}
.code-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.code-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 8px;
  background: var(--bg-soft, #eef1fa);
  font-family: 'Cascadia Mono', Consolas, monospace;
  font-size: 13px;
  cursor: pointer;
  user-select: all;
}
.code-chip.dim {
  opacity: 0.55;
}
.list-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-select {
  width: 140px;
}
@media (max-width: 767px) {
  .admin-layout {
    flex-direction: column;
  }
  .admin-side {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    position: static;
    top: auto;
  }
  .side-btn {
    flex-shrink: 0;
    justify-content: center;
  }
}
</style>
