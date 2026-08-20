<template>
  <div class="page">
    <div class="page-head">
      <h1>🛡️ 管理后台</h1>
      <p class="muted">
        通过邀请码控制注册人数：生成、限次、限时、启停，并查看注册用户。
      </p>
    </div>

    <p v-if="error" class="banner error">{{ error }}</p>
    <p v-if="notice" class="banner info">{{ notice }}</p>

    <!-- 概览 -->
    <section class="stat-cards">
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

    <!-- 生成邀请码 -->
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
          <code v-for="item in newCodes" :key="item.id" class="code-chip" @click="copyOne(item.code)" :title="'点击复制：' + item.code">
            {{ item.code }}
          </code>
        </div>
        <p class="muted small">点击单个邀请码即可复制；请妥善保管，仅发给想邀请的人。</p>
      </div>
    </section>

    <!-- 邀请码列表 -->
    <section class="panel">
      <div class="panel-head">
        <h2>📋 邀请码管理（{{ invites.length }}）</h2>
        <button class="btn small ghost" @click="loadAll">刷新</button>
      </div>
      <p v-if="loading" class="muted">加载中…</p>
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
            <code class="code-chip" :class="{ dim: !item.active }" @click="copyOne(item.code)" :title="'点击复制'">{{ item.code }}</code>
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
            <button class="btn small" @click="toggle(item)">
              {{ item.active ? '停用' : '启用' }}
            </button>
            <button class="btn small danger" @click="removeInvite(item)">删除</button>
          </span>
        </div>
      </div>
    </section>

    <!-- 用户列表 -->
    <section class="panel">
      <div class="panel-head">
        <h2>👥 注册用户（{{ users.length }}）</h2>
        <button class="btn small ghost" @click="loadAll">刷新</button>
      </div>
      <p v-if="usersLoading" class="muted">加载中…</p>
      <p v-else-if="!users.length" class="muted">暂无用户。</p>
      <div v-else class="file-table">
        <div class="file-row file-head">
          <span>用户名</span>
          <span>角色</span>
          <span>注册时间</span>
        </div>
        <div v-for="user in users" :key="user.id" class="file-row">
          <span class="file-name">{{ user.username }}</span>
          <span><span class="tag" :class="user.is_admin ? 'tag-ok' : ''">{{ user.is_admin ? '管理员' : '普通用户' }}</span></span>
          <span class="muted">{{ formatTime(user.created_at) }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api'

const stats = reactive({ total_users: 0, total_invites: 0, active_invites: 0, unused_invites: 0 })
const invites = ref([])
const users = ref([])
const newCodes = ref([])
const loading = ref(false)
const usersLoading = ref(false)
const generating = ref(false)
const error = ref('')
const notice = ref('')

const form = reactive({ count: 1, maxUses: 1, expiresDays: null, remark: '' })

function formatTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 10)
  return date.toLocaleString('zh-CN', { hour12: false })
}

async function loadAll() {
  error.value = ''
  loading.value = true
  usersLoading.value = true
  try {
    const [statsData, inviteList, userList] = await Promise.all([
      api.adminStats(),
      api.listInvites(),
      api.listAdminUsers(),
    ])
    Object.assign(stats, statsData)
    invites.value = inviteList
    users.value = userList
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
    usersLoading.value = false
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
    const created = await api.createInvites(payload)
    newCodes.value = created
    form.remark = ''
    notice.value = `已生成 ${created.length} 个邀请码，可在下方复制`
    await loadAll()
    setTimeout(() => (notice.value = ''), 5000)
  } catch (e) {
    error.value = e.message
  } finally {
    generating.value = false
  }
}

async function toggle(item) {
  try {
    await api.updateInvite(item.id, { active: !item.active })
    item.active = !item.active
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

async function copyOne(code) {
  try {
    await navigator.clipboard.writeText(code)
    notice.value = `已复制：${code}`
  } catch {
    window.prompt('请手动复制：', code)
  }
  setTimeout(() => (notice.value = ''), 2500)
}

async function copyCodes() {
  const text = newCodes.value.map((item) => item.code).join('\n')
  try {
    await navigator.clipboard.writeText(text)
    notice.value = '已复制全部邀请码'
  } catch {
    window.prompt('请手动复制：', text)
  }
  setTimeout(() => (notice.value = ''), 2500)
}

onMounted(loadAll)
</script>

<style scoped>
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
</style>
