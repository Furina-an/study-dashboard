<template>
  <div class="tutor-layout">
    <aside class="tutor-side">
      <button class="btn primary" style="width: 100%" @click="newChat">＋ 新对话</button>
      <div v-if="tutor.sessions.length" class="tutor-session-list">
        <div
          v-for="s in tutor.sessions"
          :key="s.id"
          class="tutor-session"
          :class="{ active: tutor.activeId === s.id }"
          @click="open(s)"
        >
          <span class="tutor-session-title">{{ s.title }}</span>
          <span class="muted small">{{ s.message_count }} 条</span>
          <button class="icon-btn" title="删除对话" @click.stop="remove(s)">🗑</button>
        </div>
      </div>
      <p v-else class="muted">还没有对话，试着问点什么吧</p>
    </aside>

    <section class="panel tutor-main">
      <div class="tutor-toolbar">
        <span class="tutor-source">{{ sourceLabel }}</span>
        <button class="btn small ghost" @click="showSettings = !showSettings">
          ⚙️ 调整 {{ showSettings ? '▲' : '▼' }}
        </button>
      </div>

      <div v-if="showSettings" class="tutor-settings">
        <div class="tutor-settings-row">
          <label class="muted">API 来源</label>
          <div class="seg">
            <button class="chip" :class="{ active: prefs.mode === 'custom' }" @click="prefs.mode = 'custom'">
              🔑 自定义 API
            </button>
            <button
              class="chip"
              :class="{ active: prefs.mode === 'free' }"
              :disabled="!freeAvailable"
              :title="freeAvailable ? '' : '管理员未配置免费通道'"
              @click="prefs.mode = 'free'"
            >
              🆓 免费（管理员共享）
            </button>
          </div>
          <p v-if="prefs.mode === 'free' && !freeAvailable" class="error-text">
            管理员尚未配置免费通道，可切换到「自定义 API」或联系管理员。
          </p>
        </div>

        <div class="tutor-settings-row">
          <label class="muted">模型（留空用默认）</label>
          <input
            v-model="prefs.model"
            class="input grow"
            list="tutor-model-suggestions"
            placeholder="如 deepseek-chat / qwen-plus"
            maxlength="100"
          />
          <datalist id="tutor-model-suggestions">
            <option v-for="m in modelSuggestions" :key="m" :value="m"></option>
          </datalist>
        </div>

        <div class="tutor-settings-row">
          <label class="muted">教学风格</label>
          <select v-model="prefs.style" class="input">
            <option v-for="o in styleOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </div>

        <div class="tutor-settings-row">
          <label class="muted">温度：{{ prefs.temperature }}</label>
          <input v-model.number="prefs.temperature" type="range" min="0" max="2" step="0.1" class="slider" />
        </div>

        <div class="tutor-settings-row grid-2">
          <label class="muted">
            最大回复长度
            <input v-model.number="prefs.max_tokens" type="number" min="100" max="8000" class="input" />
          </label>
          <label class="muted">
            上下文条数
            <input v-model.number="prefs.context_limit" type="number" min="4" max="40" class="input" />
          </label>
        </div>

        <p class="muted small">
          模型 / 风格 / 温度 / 长度立即作用于下一条消息；「API 来源」与「上下文条数」保存为默认后生效。
        </p>
        <div class="tutor-settings-actions">
          <span v-if="settingsMsg" class="muted">{{ settingsMsg }}</span>
          <button class="btn small" @click="resetDefaults">恢复默认</button>
          <button class="btn small primary" :disabled="settingsSaving" @click="saveDefaults">
            {{ settingsSaving ? '保存中…' : '保存为默认' }}
          </button>
        </div>
      </div>

      <div ref="msgBox" class="tutor-messages">
        <div v-if="!tutor.activeId && !tutor.messages.length" class="tutor-empty">
          <div class="tutor-emoji">🤖</div>
          <h2>AI 助教</h2>
          <p class="muted">参照港大 DeepTutor 辅导模式：围绕你的问题引导式讲解，帮你真正理解知识。</p>
          <div class="chip-row">
            <button v-for="s in suggested" :key="s" class="chip" @click="ask(s)">{{ s }}</button>
          </div>
        </div>
        <template v-else>
          <div v-for="m in tutor.messages" :key="m.id" class="msg" :class="m.role">
            <div class="msg-bubble"><Md :source="m.content" /></div>
          </div>
          <div v-if="tutor.sending" class="msg assistant">
            <div class="msg-bubble typing">正在思考…</div>
          </div>
        </template>
      </div>

      <div v-if="tutor.error" class="error-banner">
        <span>{{ tutor.error }}</span>
        <router-link v-if="!isFreeMode" to="/ai-settings" class="btn small ghost">去 AI 设置</router-link>
      </div>

      <div class="tutor-input-row">
        <input
          v-model="subject"
          class="input"
          placeholder="科目（可选）"
          maxlength="50"
          style="max-width: 140px"
        />
        <input
          v-model="message"
          class="input grow"
          placeholder="输入你的问题，回车发送…"
          :disabled="tutor.sending"
          @keyup.enter="send"
        />
        <button class="btn primary" :disabled="!message.trim() || tutor.sending" @click="send">
          {{ tutor.sending ? '…' : '发送' }}
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useTutorStore } from '../stores/tutor'
import Md from '../components/Md.vue'

const tutor = useTutorStore()
const message = ref('')
const subject = ref('')
const msgBox = ref(null)
const showSettings = ref(false)
const settingsSaving = ref(false)
const settingsMsg = ref('')

const suggested = ['什么是导数？', '帮我解释一下泰勒展开', '如何制定有效的学习计划？']

const styleOptions = [
  { value: 'socratic', label: '苏格拉底式（引导提问）' },
  { value: 'concise', label: '简洁直接' },
  { value: 'detailed', label: '详细讲解' },
  { value: 'exam', label: '考试风格（讲完出题）' },
]
const modelSuggestions = [
  'gpt-4o-mini',
  'deepseek-chat',
  'deepseek-reasoner',
  'qwen-plus',
  'qwen-turbo',
  'glm-4-flash',
  'moonshot-v1-8k',
]

const prefs = reactive({
  mode: 'custom',
  model: '',
  style: 'socratic',
  temperature: 0.7,
  max_tokens: 1000,
  context_limit: 20,
})

const freeAvailable = computed(() => Boolean(tutor.settings?.free_available))
const isFreeMode = computed(() => prefs.mode === 'free')
const sourceLabel = computed(() => {
  const model = prefs.model ? ` · ${prefs.model}` : ''
  return isFreeMode.value ? `🆓 免费（管理员共享）${model}` : `🔑 自定义 API${model}`
})

const scrollBottom = async () => {
  await nextTick()
  if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
}
watch(() => [tutor.messages.length, tutor.sending], scrollBottom)

onMounted(async () => {
  await Promise.all([tutor.fetchSessions(), tutor.fetchSettings()])
  resetDefaults()
  if (tutor.sessions.length) await tutor.openSession(tutor.sessions[0].id)
})

function resetDefaults() {
  const s = tutor.settings || {}
  Object.assign(prefs, {
    mode: s.mode || 'custom',
    model: s.model || '',
    style: s.style || 'socratic',
    temperature: s.temperature ?? 0.7,
    max_tokens: s.max_tokens || 1000,
    context_limit: s.context_limit || 20,
  })
  settingsMsg.value = ''
}

async function saveDefaults() {
  settingsSaving.value = true
  settingsMsg.value = ''
  try {
    await tutor.saveSettings({
      mode: prefs.mode,
      model: prefs.model.trim(),
      style: prefs.style,
      temperature: prefs.temperature,
      max_tokens: prefs.max_tokens,
      context_limit: prefs.context_limit,
    })
    settingsMsg.value = '✅ 已保存为默认'
  } catch (e) {
    settingsMsg.value = e.message
  } finally {
    settingsSaving.value = false
  }
}

async function open(s) {
  await tutor.openSession(s.id)
  scrollBottom()
}

function newChat() {
  tutor.openSession(null)
}

async function remove(s) {
  if (!confirm(`删除对话「${s.title}」？`)) return
  await tutor.remove(s.id)
}

async function send() {
  const text = message.value.trim()
  if (!text || tutor.sending) return
  message.value = ''
  const overrides = {
    style: prefs.style,
    temperature: prefs.temperature,
    max_tokens: prefs.max_tokens,
  }
  if (prefs.model.trim()) overrides.model = prefs.model.trim()
  try {
    await tutor.send(text, subject.value.trim(), overrides)
    scrollBottom()
  } catch {
    message.value = text
    scrollBottom()
  }
}

function ask(question) {
  message.value = question
  send()
}
</script>

<style scoped>
.tutor-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 16px;
  height: calc(100vh - 170px);
  min-height: 420px;
}
.tutor-side {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  overflow-y: auto;
}
.tutor-session-list { display: flex; flex-direction: column; gap: 6px; }
.tutor-session {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
}
.tutor-session:hover { background: var(--surface-hover, rgba(99,102,241,0.06)); }
.tutor-session.active { border-color: var(--primary); background: var(--primary-soft); }
.tutor-session-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.icon-btn { border: none; background: none; cursor: pointer; opacity: 0.6; font-size: 13px; }
.icon-btn:hover { opacity: 1; }
.tutor-main { display: flex; flex-direction: column; overflow: hidden; }

.tutor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 2px 4px 8px;
  border-bottom: 1px solid var(--border);
}
.tutor-source { font-size: 13px; color: var(--text-muted); }

.tutor-settings {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  margin-top: 10px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  background: var(--surface-soft, rgba(99,102,241,0.03));
}
.tutor-settings-row { display: flex; flex-direction: column; gap: 6px; }
.tutor-settings-row.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.seg { display: flex; gap: 8px; flex-wrap: wrap; }
.seg .chip:disabled { opacity: 0.45; cursor: not-allowed; }
.slider { width: 100%; accent-color: var(--primary); }
.tutor-settings-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tutor-messages { flex: 1; overflow-y: auto; padding: 8px 4px; display: flex; flex-direction: column; gap: 10px; }
.tutor-empty { margin: auto; text-align: center; max-width: 480px; }
.tutor-emoji { font-size: 44px; margin-bottom: 8px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 12px; }
.msg { display: flex; }
.msg.user { justify-content: flex-end; }
.msg-bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 14px;
  line-height: 1.6;
  background: var(--surface-hover, rgba(99,102,241,0.06));
  border: 1px solid var(--border);
}
.msg.user .msg-bubble {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
.msg.user .msg-bubble :deep(a) { color: #fff; text-decoration: underline; }
.msg.assistant .msg-bubble { border-top-left-radius: 4px; }
.msg.user .msg-bubble { border-top-right-radius: 4px; }
.typing { opacity: 0.6; }
.error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  margin: 8px 4px 0;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  font-size: 13px;
}
.tutor-input-row { display: flex; gap: 8px; padding: 10px 4px 0; }
@media (max-width: 768px) {
  .tutor-layout { grid-template-columns: 1fr; height: auto; }
  .tutor-side { flex-direction: row; overflow-x: auto; }
  .tutor-session-list { flex-direction: row; }
  .tutor-settings-row.grid-2 { grid-template-columns: 1fr; }
}
</style>
