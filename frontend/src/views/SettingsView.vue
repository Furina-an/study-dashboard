<template>
  <div class="page settings-page">
    <div class="page-head">
      <h1>⚙️ 设置</h1>
      <p class="date-line">账号信息 · 个性化 · 数据备份 · 部署与端口预留</p>
    </div>

    <section class="panel">
      <h2>👤 账号信息</h2>
      <div class="info-row">
        <span class="info-label">用户名</span>
        <span>{{ auth.user?.username }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">注册时间</span>
        <span>{{ formatDate(auth.user?.created_at) }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">数据隔离</span>
        <span>任务 / 计划 / 专注 / 复习 / 习惯 / 高数进度均按账号分开存储</span>
      </div>
    </section>

    <!-- ===== 个性化 ===== -->
    <section class="panel">
      <div class="panel-head">
        <h2>🎨 个性化</h2>
        <span class="muted">偏好按账号保存，换设备同步</span>
      </div>
      <p v-if="flash.message" class="result" :class="flash.kind">{{ flash.message }}</p>

      <h3 class="sub-title">外观</h3>
      <div class="field">
        <label>主题模式</label>
        <div class="segmented">
          <button
            v-for="mode in themeModes"
            :key="mode.value"
            class="chip"
            :class="{ active: form.theme_mode === mode.value }"
            @click="saveAppearance({ theme_mode: mode.value })"
          >
            {{ mode.label }}
          </button>
        </div>
      </div>
      <div class="field">
        <label>强调色</label>
        <div class="accent-row">
          <button
            v-for="acc in accents"
            :key="acc.value"
            class="accent-swatch"
            :class="['accent-' + acc.value, { active: form.accent === acc.value }]"
            :title="acc.label"
            @click="saveAppearance({ accent: acc.value })"
          ></button>
          <span class="muted">全站主色即时生效</span>
        </div>
      </div>

      <h3 class="sub-title">番茄钟时长</h3>
      <div class="field">
        <label>时长列表（1-5 项，每项 1-180 分钟）</label>
        <div class="tag-list">
          <span v-for="(d, idx) in form.pomodoro_durations" :key="d" class="tag tag-pomodoro">
            {{ d }} 分钟
            <button
              v-if="d !== form.pomodoro_default"
              class="mini-btn"
              title="设为默认"
              @click="setDefaultDuration(d)"
            >⭐</button>
            <button
              v-if="form.pomodoro_durations.length > 1"
              class="mini-btn"
              title="删除"
              @click="removeDuration(idx)"
            >✕</button>
            <span v-if="d === form.pomodoro_default" class="tag-default">默认</span>
          </span>
          <input
            v-model.number="newDuration"
            class="input narrow"
            type="number"
            min="1"
            max="180"
            placeholder="新增时长"
            @keyup.enter="addDuration"
          />
          <button class="btn small" :disabled="!newDuration" @click="addDuration">添加</button>
        </div>
        <div class="field-actions">
          <button class="btn primary" :disabled="saving" @click="savePomodoro">
            {{ saving ? '保存中…' : '保存番茄钟设置' }}
          </button>
        </div>
      </div>

      <h3 class="sub-title">复习间隔</h3>
      <div class="field">
        <label>艾宾浩斯间隔（1-8 项，每项 1-365 天，保存时自动排序去重）</label>
        <div class="tag-list">
          <span v-for="(iv, idx) in form.review_intervals" :key="iv" class="tag tag-review">
            第 {{ iv }} 天
            <button class="mini-btn" title="删除" @click="removeInterval(idx)">✕</button>
          </span>
          <input
            v-model.number="newInterval"
            class="input narrow"
            type="number"
            min="1"
            max="365"
            placeholder="新增间隔"
            @keyup.enter="addInterval"
          />
          <button class="btn small" :disabled="!newInterval" @click="addInterval">添加</button>
        </div>
        <div class="field-actions">
          <button class="btn primary" :disabled="saving" @click="saveReviewIntervals">
            {{ saving ? '保存中…' : '保存复习间隔' }}
          </button>
        </div>
      </div>

      <h3 class="sub-title">任务默认值</h3>
      <div class="field-grid">
        <div class="field">
          <label>习惯默认频率</label>
          <select v-model="form.habit_frequency_default" class="input">
            <option value="daily">每天</option>
            <option value="weekdays">工作日</option>
            <option value="custom">自定义星期</option>
          </select>
        </div>
        <div class="field">
          <label>任务默认预计分钟</label>
          <input v-model.number="form.default_estimated_minutes" class="input" type="number" min="1" max="600" />
        </div>
      </div>
      <div class="field">
        <label>科目库（新建任务时快捷选择，最多 50 项）</label>
        <div class="tag-list">
          <span v-for="(subject, idx) in form.task_subjects" :key="subject" class="tag tag-subject">
            {{ subject }}
            <button class="mini-btn" title="删除" @click="removeSubject(idx)">✕</button>
          </span>
          <input
            v-model="newSubject"
            class="input"
            maxlength="50"
            placeholder="输入科目后回车添加"
            @keyup.enter="addSubject"
          />
          <button class="btn small" :disabled="!newSubject.trim()" @click="addSubject">添加</button>
        </div>
        <div class="field-actions">
          <button class="btn primary" :disabled="saving" @click="saveTaskDefaults">
            {{ saving ? '保存中…' : '保存任务默认值' }}
          </button>
        </div>
      </div>

      <h3 class="sub-title">首页功能卡片</h3>
      <p class="muted small-tip">勾选显示 / 取消隐藏；「设置」卡片固定展示，不在配置范围。</p>
      <div class="hub-card-editor">
        <div v-for="(card, idx) in form.hub_cards" :key="card.key" class="hub-card-row">
          <label class="checkbox-line">
            <input v-model="card.visible" type="checkbox" />
            {{ settings.hubCardLabel(card.key) }}
          </label>
          <div class="row-actions">
            <button class="btn small" :disabled="idx === 0" title="上移" @click="moveCard(idx, -1)">↑</button>
            <button class="btn small" :disabled="idx === form.hub_cards.length - 1" title="下移" @click="moveCard(idx, 1)">↓</button>
          </div>
        </div>
      </div>
      <div class="field-actions">
        <button class="btn primary" :disabled="saving" @click="saveHubCards">
          {{ saving ? '保存中…' : '保存首页布局' }}
        </button>
      </div>

      <h3 class="sub-title">我的计划模板</h3>
      <p class="muted small-tip">在「计划」页拆解大计划时可直接选用；每个模板含 1-20 个子项。</p>
      <p v-if="settings.planTemplates.length === 0" class="muted">还没有自定义模板。</p>
      <ul v-else class="template-list">
        <li v-for="tpl in settings.planTemplates" :key="tpl.id" class="template-row">
          <div class="template-info">
            <span class="template-name">🗂️ {{ tpl.name }}</span>
            <span class="muted">{{ tpl.children.length }} 个子项</span>
          </div>
          <div class="row-actions">
            <button class="btn small" @click="openTemplateModal(tpl)">编辑</button>
            <button class="btn small danger" @click="removeTemplate(tpl)">删除</button>
          </div>
        </li>
      </ul>
      <div class="field-actions">
        <button class="btn" @click="openTemplateModal(null)">＋ 新建模板</button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>💾 数据备份</h2>
        <span class="muted">导出为 JSON，可换设备 / 换账号恢复</span>
      </div>
      <p class="backup-tip">
        备份包含：任务、计划、专注记录、习惯打卡、复习节点、个性化设置、计划模板、高数掌握进度与章节笔记、AI 配置（不含 Key）。
        <br />⚠️ AI 的 API Key 为加密存储，不随备份导出，恢复后需到「AI 设置」重新填写。
      </p>
      <div class="backup-actions">
        <button class="btn primary" :disabled="busy" @click="exportBackup">
          {{ busy ? '处理中…' : '⬇️ 导出备份' }}
        </button>
        <button class="btn" :disabled="busy" @click="pickFile">⬆️ 导入备份</button>
        <input
          ref="fileInput"
          type="file"
          accept="application/json,.json"
          class="hidden-file"
          @change="onFilePicked"
        />
      </div>
      <p v-if="message" class="result" :class="messageKind">{{ message }}</p>
    </section>

    <section class="panel">
      <h2>☁️ 部署与端口（已预留）</h2>
      <p class="backup-tip">
        后端端口由环境变量 <code>PORT</code> 指定（本地默认 <code>8000</code>），主机由 <code>HOST</code> 指定
        （云端默认 <code>0.0.0.0</code>），统一入口为 <code>backend/run.py</code>。
      </p>
      <div class="info-row">
        <span class="info-label">本地启动</span>
        <code>start.bat</code>（默认端口 8000，也可设置 <code>PORT</code> 覆盖）
      </div>
      <div class="info-row">
        <span class="info-label">单服务器</span>
        <code>deploy/deploy.sh</code>（Nginx + systemd，内网端口 8000）
      </div>
      <div class="info-row">
        <span class="info-label">容器部署</span>
        <code>Dockerfile</code>，例如 <code>docker run -p 8000:8000 -e SECRET_KEY=... -e INVITE_CODE=... studydash</code>
      </div>
      <div class="info-row">
        <span class="info-label">Render</span>
        <code>render.yaml</code>，Web Service 自动注入 <code>PORT</code>；数据库用 <code>DATABASE_URL</code>（PostgreSQL）
      </div>
      <p class="backup-tip">
        云端数据库（PostgreSQL）同样支持导入本功能导出的 JSON 备份；部署细节见 README「部署到云端」。
      </p>
    </section>

    <!-- 计划模板弹层 -->
    <div v-if="templateModal.open" class="modal-backdrop" @click.self="templateModal.open = false">
      <div class="modal">
        <h2>{{ templateModal.id ? '编辑模板' : '新建模板' }}</h2>
        <div class="field">
          <label>模板名称（必填，1-50 字）</label>
          <input v-model="templateModal.name" class="input" maxlength="50" placeholder="例如：期末复习冲刺" />
        </div>
        <div class="field">
          <label>子计划（1-20 项）</label>
          <div v-for="(child, idx) in templateModal.children" :key="idx" class="template-child-row">
            <input v-model="child.title" class="input grow" maxlength="100" placeholder="子计划标题" />
            <input v-model="child.description" class="input grow" maxlength="500" placeholder="说明（可选）" />
            <button class="btn small danger" @click="removeTemplateChild(idx)">✕</button>
          </div>
          <button class="btn small" :disabled="templateModal.children.length >= 20" @click="addTemplateChild">
            ＋ 添加子项
          </button>
        </div>
        <p v-if="templateModal.error" class="error-text">{{ templateModal.error }}</p>
        <div class="modal-actions">
          <button class="btn" @click="templateModal.open = false">取消</button>
          <button class="btn primary" :disabled="saving" @click="saveTemplate">
            {{ saving ? '保存中…' : '保存模板' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useSettingsStore } from '../stores/settings'
import { api } from '../api'

const auth = useAuthStore()
const settings = useSettingsStore()

const themeModes = [
  { value: 'light', label: '☀️ 浅色' },
  { value: 'dark', label: '🌙 深色' },
  { value: 'system', label: '💻 跟随系统' },
]
const accents = [
  { value: 'indigo', label: '靛蓝' },
  { value: 'green', label: '翠绿' },
  { value: 'rose', label: '玫瑰' },
  { value: 'amber', label: '琥珀' },
  { value: 'violet', label: '紫罗兰' },
]

const form = reactive({
  theme_mode: 'system',
  accent: 'indigo',
  pomodoro_durations: [25, 45, 60],
  pomodoro_default: 25,
  review_intervals: [1, 2, 4, 7, 15, 30],
  habit_frequency_default: 'daily',
  default_estimated_minutes: 25,
  task_subjects: [],
  hub_cards: [],
})

const newDuration = ref(null)
const newInterval = ref(null)
const newSubject = ref('')
const saving = ref(false)
const flash = reactive({ message: '', kind: 'ok' })

const templateModal = reactive({
  open: false,
  id: null,
  name: '',
  children: [],
  error: '',
})

const busy = ref(false)
const message = ref('')
const messageKind = ref('ok')
const fileInput = ref(null)

function syncFromStore() {
  form.theme_mode = settings.themeMode
  form.accent = settings.accent
  form.pomodoro_durations = [...settings.pomodoroDurations]
  form.pomodoro_default = settings.pomodoroDefault
  form.review_intervals = [...settings.reviewIntervals]
  form.habit_frequency_default = settings.habitFrequencyDefault
  form.default_estimated_minutes = settings.defaultEstimatedMinutes
  form.task_subjects = [...settings.taskSubjects]
  form.hub_cards = settings.hubCards.map((card) => ({ ...card }))
}

function flashOk(text) {
  flash.message = text
  flash.kind = 'ok'
}
function flashError(text) {
  flash.message = text
  flash.kind = 'error'
}

async function saveAppearance(partial) {
  try {
    await settings.save(partial)
    Object.assign(form, partial)
    flashOk('外观已保存并生效')
  } catch (e) {
    flashError(e.message)
  }
}

function addDuration() {
  const value = Number(newDuration.value)
  if (!value || value < 1 || value > 180) return
  if (!form.pomodoro_durations.includes(value)) form.pomodoro_durations.push(value)
  newDuration.value = null
}
function removeDuration(idx) {
  form.pomodoro_durations.splice(idx, 1)
  if (!form.pomodoro_durations.includes(form.pomodoro_default)) {
    form.pomodoro_default = form.pomodoro_durations[0]
  }
}
function setDefaultDuration(value) {
  form.pomodoro_default = value
}
async function savePomodoro() {
  saving.value = true
  try {
    await settings.save({
      pomodoro_durations: form.pomodoro_durations,
      pomodoro_default: form.pomodoro_default,
    })
    syncFromStore()
    flashOk('番茄钟设置已保存')
  } catch (e) {
    flashError(e.message)
  } finally {
    saving.value = false
  }
}

function addInterval() {
  const value = Number(newInterval.value)
  if (!value || value < 1 || value > 365) return
  if (!form.review_intervals.includes(value)) form.review_intervals.push(value)
  newInterval.value = null
}
function removeInterval(idx) {
  form.review_intervals.splice(idx, 1)
}
async function saveReviewIntervals() {
  saving.value = true
  try {
    await settings.save({ review_intervals: form.review_intervals })
    syncFromStore()
    flashOk('复习间隔已保存')
  } catch (e) {
    flashError(e.message)
  } finally {
    saving.value = false
  }
}

function addSubject() {
  const value = newSubject.value.trim()
  if (!value) return
  if (!form.task_subjects.includes(value)) form.task_subjects.push(value.slice(0, 50))
  newSubject.value = ''
}
function removeSubject(idx) {
  form.task_subjects.splice(idx, 1)
}
async function saveTaskDefaults() {
  saving.value = true
  try {
    await settings.save({
      habit_frequency_default: form.habit_frequency_default,
      default_estimated_minutes: form.default_estimated_minutes,
      task_subjects: form.task_subjects,
    })
    syncFromStore()
    flashOk('任务默认值已保存')
  } catch (e) {
    flashError(e.message)
  } finally {
    saving.value = false
  }
}

function moveCard(idx, delta) {
  const target = idx + delta
  if (target < 0 || target >= form.hub_cards.length) return
  const cards = form.hub_cards
  ;[cards[idx], cards[target]] = [cards[target], cards[idx]]
}
async function saveHubCards() {
  saving.value = true
  try {
    await settings.save({ hub_cards: form.hub_cards.map((card, order) => ({ ...card, order })) })
    syncFromStore()
    flashOk('首页布局已保存')
  } catch (e) {
    flashError(e.message)
  } finally {
    saving.value = false
  }
}

function openTemplateModal(tpl) {
  templateModal.id = tpl?.id ?? null
  templateModal.name = tpl?.name ?? ''
  templateModal.children = (tpl?.children ?? []).map((child) => ({ ...child }))
  templateModal.error = ''
  templateModal.open = true
}
function addTemplateChild() {
  templateModal.children.push({ title: '', description: '' })
}
function removeTemplateChild(idx) {
  templateModal.children.splice(idx, 1)
}
async function saveTemplate() {
  const name = templateModal.name.trim()
  const children = templateModal.children
    .filter((child) => child.title.trim())
    .map((child) => ({ title: child.title.trim(), description: child.description.trim() }))
  if (!name) {
    templateModal.error = '请填写模板名称'
    return
  }
  if (!children.length) {
    templateModal.error = '至少需要一个子计划标题'
    return
  }
  saving.value = true
  templateModal.error = ''
  try {
    if (templateModal.id) {
      await settings.updatePlanTemplate(templateModal.id, { name, children })
    } else {
      await settings.createPlanTemplate({ name, children })
    }
    templateModal.open = false
    flashOk('计划模板已保存')
  } catch (e) {
    templateModal.error = e.message
  } finally {
    saving.value = false
  }
}
async function removeTemplate(tpl) {
  if (!window.confirm(`确定删除模板「${tpl.name}」？`)) return
  try {
    await settings.removePlanTemplate(tpl.id)
    flashOk('模板已删除')
  } catch (e) {
    flashError(e.message)
  }
}

function formatDate(value) {
  if (!value) return '–'
  return new Date(value).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

async function exportBackup() {
  busy.value = true
  message.value = ''
  try {
    const data = await api.exportBackup()
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `studydash-backup-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    const d = data.data
    messageKind.value = 'ok'
    message.value = `✅ 已导出：${d.tasks.length} 任务 / ${d.plans.length} 计划 / ${d.sessions.length} 专注 / ${d.reviews.length} 复习 / 设置 ${d.settings ? 1 : 0} / 模板 ${d.plan_templates?.length ?? 0} / 高数已掌握 ${d.math_progress.length}`
  } catch (err) {
    messageKind.value = 'error'
    message.value = `导出失败：${err.message}`
  } finally {
    busy.value = false
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFilePicked(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  let data
  try {
    data = JSON.parse(await file.text())
  } catch {
    messageKind.value = 'error'
    message.value = '文件不是有效的 JSON，请选择 StudyDash 导出的备份文件'
    return
  }
  if (data.schema_version !== 1 || !data.data) {
    messageKind.value = 'error'
    message.value = '不是 StudyDash 备份文件（缺少 schema_version 或 data 字段）'
    return
  }
  const backupUser = data.user?.username
  const fromOther = backupUser && backupUser !== auth.user?.username ? `（备份来自账号 ${backupUser}）` : ''
  const confirmed = confirm(
    `导入将【覆盖】当前账号的全部数据（任务 / 计划 / 专注 / 复习 / 习惯 / 个性化 / 高数进度）${fromOther}。\n\n建议先导出当前数据备份，确定继续吗？`,
  )
  if (!confirmed) return
  busy.value = true
  message.value = ''
  try {
    const result = await api.importBackup(data)
    const c = result.counts
    messageKind.value = 'ok'
    message.value = `✅ 恢复完成：${c.plans} 计划 / ${c.tasks} 任务 / ${c.sessions} 专注 / ${c.checkins} 打卡 / ${c.reviews} 复习 / AI ${c.ai_config} / 设置 ${c.settings ?? 0} / 模板 ${c.plan_templates ?? 0} / 高数进度 ${c.math_progress} / 笔记 ${c.math_notes}`
    if (settings.settings) {
      await settings.fetch()
      syncFromStore()
      await settings.fetchPlanTemplates()
    }
  } catch (err) {
    messageKind.value = 'error'
    message.value = `导入失败：${err.message}`
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await settings.fetch()
  syncFromStore()
  await settings.fetchPlanTemplates()
})
</script>

<style scoped>
.info-row {
  display: flex;
  gap: 12px;
  padding: 9px 0;
  border-bottom: 1px dashed var(--border);
  font-size: 14px;
  align-items: baseline;
}

.info-row:last-child {
  border-bottom: 0;
}

.info-label {
  width: 96px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.backup-tip {
  font-size: 13px;
  color: var(--text-muted);
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  line-height: 1.7;
}

.backup-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.hidden-file {
  display: none;
}

.result {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  white-space: pre-wrap;
}

.result.ok {
  background: var(--success-soft);
  color: var(--success);
  border: 1px solid var(--success);
}

.result.error {
  background: var(--danger-soft);
  color: var(--danger);
  border: 1px solid var(--danger);
}

.sub-title {
  margin: 22px 0 10px;
  font-size: 15px;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  padding-bottom: 6px;
}

.field {
  margin-bottom: 14px;
}

.field label {
  display: block;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.segmented {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.accent-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.accent-swatch {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 3px solid var(--surface);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.2);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.accent-swatch:hover {
  transform: scale(1.12);
}

.accent-swatch.active {
  box-shadow: 0 0 0 2px var(--text);
  transform: scale(1.08);
}

.accent-indigo { background: #4f46e5; }
.accent-green { background: #059669; }
.accent-rose { background: #e11d48; }
.accent-amber { background: #d97706; }
.accent-violet { background: #7c3aed; }

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag-pomodoro,
.tag-review,
.tag-subject {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--primary-soft);
  color: var(--primary);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 600;
}

.tag-default {
  font-size: 11px;
  background: var(--success);
  color: #fff;
  border-radius: 999px;
  padding: 1px 8px;
}

.mini-btn {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  opacity: 0.75;
}

.mini-btn:hover {
  opacity: 1;
}

.field-actions {
  margin-top: 12px;
}

.small-tip {
  font-size: 12px;
  margin: 2px 0 10px;
}

.hub-card-editor {
  display: grid;
  gap: 8px;
  max-width: 480px;
}

.hub-card-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
}

.row-actions {
  display: flex;
  gap: 6px;
}

.template-list {
  list-style: none;
  padding: 0;
  margin: 0 0 10px;
  display: grid;
  gap: 8px;
  max-width: 560px;
}

.template-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
}

.template-info {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.template-name {
  font-weight: 700;
}

.template-child-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

@media (max-width: 720px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
  .template-child-row {
    flex-direction: column;
  }
}
</style>
