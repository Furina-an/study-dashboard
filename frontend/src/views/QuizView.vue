<template>
  <div>
    <div class="filter-tabs page-tabs">
      <button class="chip" :class="{ active: tab === 'practice' }" @click="switchTab('practice')">练习</button>
      <button class="chip" :class="{ active: tab === 'bank' }" @click="switchTab('bank')">题库</button>
      <button class="chip" :class="{ active: tab === 'mastery' }" @click="switchTab('mastery')">掌握度</button>
    </div>

    <!-- 练习 -->
    <section v-if="tab === 'practice'" class="panel">
      <template v-if="!running">
        <h2>开始一场测验</h2>
        <p class="muted">从题库随机抽题，即时判分并给出解析；答题记录计入掌握度统计。</p>
        <div class="form-row">
          <label>
            科目
            <select v-model="setup.subject" class="input">
              <option value="">全部科目</option>
              <option v-for="s in allSubjects" :key="s" :value="s">{{ s }}</option>
            </select>
          </label>
          <label>
            题量
            <input v-model.number="setup.count" type="number" min="1" max="20" class="input narrow" />
          </label>
          <button class="btn primary" :disabled="starting" @click="startQuiz">
            {{ starting ? '组卷中…' : '开始' }}
          </button>
        </div>
        <p v-if="startError" class="error-text">{{ startError }}</p>
      </template>
      <template v-else>
        <div class="quiz-head">
          <span class="tag">{{ done ? '已完成' : `第 ${index + 1} / ${questions.length} 题` }}</span>
          <button class="btn small ghost" @click="quitQuiz">退出</button>
        </div>
        <template v-if="!done">
          <h3>{{ current.question }}</h3>
          <p v-if="current.subject" class="muted">科目：{{ current.subject }}</p>
          <div class="quiz-options">
            <button
              v-for="(opt, i) in current.options"
              :key="i"
              class="quiz-option"
              :class="{
                selected: selected === i && feedback === null,
                correct: feedback !== null && i === feedback.correct_answer,
                wrong: feedback !== null && selected === i && !feedback.correct,
              }"
              :disabled="feedback !== null"
              @click="selected = i"
            >
              <span class="opt-key">{{ letters[i] }}</span>{{ opt }}
            </button>
          </div>
          <div v-if="feedback !== null" class="quiz-feedback" :class="feedback.correct ? 'ok' : 'bad'">
            <strong>{{ feedback.correct ? '✅ 回答正确' : '❌ 回答错误' }}（正确答案 {{ letters[feedback.correct_answer] }}）</strong>
            <p v-if="feedback.explanation" class="muted">{{ feedback.explanation }}</p>
          </div>
          <div class="quiz-actions">
            <button v-if="feedback === null" class="btn primary" :disabled="selected === null" @click="submit">
              提交答案
            </button>
            <button v-else class="btn primary" @click="next">下一题</button>
          </div>
        </template>
        <template v-else>
          <div class="quiz-done">
            <div class="quiz-score">{{ score }} / {{ questions.length }}</div>
            <p class="muted">正确率 {{ scorePercent }}%</p>
            <div class="quiz-actions">
              <button class="btn" @click="quitQuiz">返回</button>
              <button class="btn primary" @click="startQuiz">再来一组</button>
            </div>
          </div>
        </template>
      </template>
    </section>

    <!-- 题库 -->
    <section v-if="tab === 'bank'" class="panel">
      <div class="panel-head">
        <h2>题库（{{ quizStore.bank.length }}）</h2>
        <div class="list-actions">
          <button class="btn small ghost" @click="aiPanel = !aiPanel">🤖 AI 出题</button>
          <button class="btn small primary" @click="openCreate">＋ 新建题目</button>
        </div>
      </div>

      <div v-if="aiPanel" class="ai-generate">
        <div class="form-row">
          <input v-model="aiForm.subject" class="input" placeholder="科目（必填）" maxlength="50" />
          <input v-model="aiForm.topic" class="input grow" placeholder="知识点（可选）" maxlength="200" />
          <input v-model.number="aiForm.count" type="number" min="1" max="10" class="input narrow" placeholder="题量" />
          <button class="btn primary" :disabled="!aiForm.subject.trim() || generating" @click="generate">
            {{ generating ? '生成中…' : '生成' }}
          </button>
        </div>
        <p v-if="aiResultMsg" class="muted">{{ aiResultMsg }}</p>
        <p v-if="quizStore.generateError" class="error-text">{{ quizStore.generateError }}</p>
      </div>

      <div class="form-row" style="margin-top: 12px">
        <select v-model="bankFilter.subject" class="input narrow" @change="reloadBank">
          <option value="">全部科目</option>
          <option v-for="s in allSubjects" :key="s" :value="s">{{ s }}</option>
        </select>
        <div class="filter-tabs">
          <button class="chip" :class="{ active: bankFilter.source === '' }" @click="setSource('')">全部</button>
          <button class="chip" :class="{ active: bankFilter.source === 'manual' }" @click="setSource('manual')">手动</button>
          <button class="chip" :class="{ active: bankFilter.source === 'ai' }" @click="setSource('ai')">AI</button>
        </div>
      </div>

      <div v-if="quizStore.bank.length" class="file-table" style="margin-top: 12px">
        <div v-for="q in quizStore.bank" :key="q.id" class="bank-item">
          <div class="bank-main">
            <div class="bank-q">
              <span v-if="q.subject" class="tag">{{ q.subject }}</span>
              <span class="tag" :class="q.source === 'ai' ? 'tag-ai' : ''">{{ q.source === 'ai' ? '🤖 AI' : '✍️ 手动' }}</span>
              <span class="bank-text">{{ q.question }}</span>
            </div>
            <div class="bank-options">
              <span v-for="(opt, i) in q.options" :key="i" class="bank-opt" :class="{ answer: i === q.answer }">
                {{ letters[i] }}. {{ opt }}
              </span>
            </div>
            <p v-if="q.explanation" class="muted small">解析：{{ q.explanation }}</p>
          </div>
          <div class="list-actions">
            <button class="btn small ghost" @click="openEdit(q)">编辑</button>
            <button class="btn small danger" @click="remove(q)">删除</button>
          </div>
        </div>
      </div>
      <p v-else class="muted">题库为空，可以「＋ 新建题目」或「🤖 AI 出题」。</p>
    </section>

    <!-- 掌握度 -->
    <section v-if="tab === 'mastery'" class="panel">
      <h2>掌握度</h2>
      <p class="muted">基于答题记录，按科目统计正确率（含近 7 天表现）。</p>
      <div v-if="quizStore.mastery" class="mastery-grid">
        <div class="mastery-card overall">
          <div class="mastery-num">{{ percent(quizStore.mastery.overall_accuracy) }}%</div>
          <div class="muted">
            总体正确率 · 已答 {{ quizStore.mastery.total_answered }} 题 / 答对 {{ quizStore.mastery.total_correct }} 题
          </div>
        </div>
        <div v-for="s in quizStore.mastery.subjects" :key="s.subject" class="mastery-card">
          <div class="mastery-head">
            <span class="tag">{{ s.subject }}</span>
            <span class="mastery-num small">{{ percent(s.accuracy) }}%</span>
          </div>
          <div class="bar"><div class="bar-fill" :style="{ width: percent(s.accuracy) + '%' }"></div></div>
          <div class="muted small">
            共 {{ s.total }} 题 / 答对 {{ s.correct }} 题 · 近 7 天 {{ s.last_7d_correct }}/{{ s.last_7d_total }}
          </div>
        </div>
      </div>
      <p v-else class="muted">还没有答题记录，去「练习」做一组题吧。</p>
    </section>

    <!-- 题目弹层（新建/编辑） -->
    <div v-if="questionModal.open" class="modal-backdrop" @click.self="questionModal.open = false">
      <div class="modal">
        <h2>{{ questionModal.mode === 'edit' ? '编辑题目' : '新建题目' }}</h2>
        <input v-model="questionModal.subject" class="input" placeholder="科目（可选）" maxlength="50" />
        <textarea
          v-model="questionModal.question"
          class="input textarea"
          rows="2"
          placeholder="题干（必填）"
          maxlength="2000"
        ></textarea>
        <label class="muted">选项（每行一个，至少 2 个，最多 6 个）</label>
        <textarea v-model="questionModal.optionsText" class="input textarea" rows="4" placeholder="选项A&#10;选项B"></textarea>
        <label class="muted">正确答案</label>
        <select v-model.number="questionModal.answer" class="input">
          <option v-for="(opt, i) in optionsList" :key="i" :value="i">{{ letters[i] }}. {{ opt }}</option>
        </select>
        <textarea
          v-model="questionModal.explanation"
          class="input textarea"
          rows="2"
          placeholder="解析（可选）"
          maxlength="2000"
        ></textarea>
        <p v-if="questionModal.error" class="error-text">{{ questionModal.error }}</p>
        <div class="modal-actions">
          <button class="btn" @click="questionModal.open = false">取消</button>
          <button class="btn primary" :disabled="questionModal.submitting" @click="saveQuestion">
            {{ questionModal.submitting ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api'
import { useQuizStore } from '../stores/quiz'
import { useSettingsStore } from '../stores/settings'

const quizStore = useQuizStore()
const settings = useSettingsStore()

const letters = ['A', 'B', 'C', 'D', 'E', 'F']
const tab = ref('practice')

const setup = reactive({ subject: '', count: 5 })
const running = ref(false)
const starting = ref(false)
const startError = ref('')
const questions = ref([])
const index = ref(0)
const selected = ref(null)
const feedback = ref(null)
const results = ref([])
const done = ref(false)

const allSubjects = computed(() => {
  const set = new Set(quizStore.subjects)
  for (const s of settings.taskSubjects || []) set.add(s)
  for (const q of quizStore.bank) if (q.subject) set.add(q.subject)
  return [...set].sort()
})
const current = computed(() => questions.value[index.value] || {})
const score = computed(() => results.value.filter((r) => r && r.correct).length)
const scorePercent = computed(() =>
  questions.value.length ? Math.round((score.value / questions.value.length) * 100) : 0,
)
const optionsList = computed(() =>
  questionModal.optionsText.split('\n').map((s) => s.trim()).filter(Boolean),
)
const percent = (value) => Math.round((value || 0) * 100)

async function switchTab(next) {
  tab.value = next
  if (next === 'bank') await quizStore.fetchBank(bankFilter.subject, bankFilter.source)
  if (next === 'mastery') await quizStore.fetchMastery()
}

async function startQuiz() {
  starting.value = true
  startError.value = ''
  try {
    const list = await api.quizSession(setup.subject || '', setup.count || 5)
    if (!list.length) {
      startError.value = '题库为空，请先录入或 AI 生成题目'
      return
    }
    questions.value = list
    index.value = 0
    selected.value = null
    feedback.value = null
    results.value = []
    done.value = false
    running.value = true
  } catch (e) {
    startError.value = e.message
  } finally {
    starting.value = false
  }
}

async function submit() {
  if (selected.value === null || feedback.value !== null) return
  try {
    const result = await api.quizAnswer({
      question_id: current.value.id,
      answer_index: selected.value,
    })
    feedback.value = result
    results.value[index.value] = result
  } catch (e) {
    startError.value = e.message
  }
}

function next() {
  if (index.value < questions.value.length - 1) {
    index.value += 1
    selected.value = null
    feedback.value = null
  } else {
    done.value = true
  }
}

function quitQuiz() {
  running.value = false
  questions.value = []
}

// ---------------- 题库 ----------------
const bankFilter = reactive({ subject: '', source: '' })
const aiPanel = ref(false)
const generating = ref(false)
const aiResultMsg = ref('')
const aiForm = reactive({ subject: '', topic: '', count: 5 })

const questionModal = reactive({
  open: false,
  mode: 'create',
  id: null,
  subject: '',
  question: '',
  optionsText: '',
  answer: 0,
  explanation: '',
  error: '',
  submitting: false,
})

function openCreate() {
  Object.assign(questionModal, {
    open: true,
    mode: 'create',
    id: null,
    subject: '',
    question: '',
    optionsText: '选项A\n选项B',
    answer: 0,
    explanation: '',
    error: '',
  })
}

function openEdit(q) {
  Object.assign(questionModal, {
    open: true,
    mode: 'edit',
    id: q.id,
    subject: q.subject,
    question: q.question,
    optionsText: q.options.join('\n'),
    answer: q.answer,
    explanation: q.explanation,
    error: '',
  })
}

async function saveQuestion() {
  const options = optionsList.value
  if (!questionModal.question.trim()) {
    questionModal.error = '请填写题干'
    return
  }
  if (options.length < 2 || options.length > 6) {
    questionModal.error = '选项需为 2-6 个'
    return
  }
  if (questionModal.answer < 0 || questionModal.answer >= options.length) {
    questionModal.error = '答案序号超出选项范围'
    return
  }
  questionModal.submitting = true
  try {
    const payload = {
      subject: questionModal.subject.trim(),
      question: questionModal.question.trim(),
      options,
      answer: questionModal.answer,
      explanation: questionModal.explanation.trim(),
    }
    if (questionModal.mode === 'edit') {
      await quizStore.update(questionModal.id, payload)
    } else {
      await quizStore.create(payload)
    }
    questionModal.open = false
  } catch (e) {
    questionModal.error = e.message
  } finally {
    questionModal.submitting = false
  }
}

async function remove(q) {
  if (!confirm(`删除题目「${q.question.slice(0, 30)}」？`)) return
  await quizStore.remove(q.id)
}

async function generate() {
  generating.value = true
  aiResultMsg.value = ''
  try {
    const created = await quizStore.generate({
      subject: aiForm.subject.trim(),
      topic: aiForm.topic.trim(),
      count: aiForm.count || 5,
    })
    aiResultMsg.value = `已生成 ${created.length} 道题目并加入题库`
  } catch {
    /* 错误由 store.generateError 展示 */
  } finally {
    generating.value = false
  }
}

async function reloadBank() {
  await quizStore.fetchBank(bankFilter.subject, bankFilter.source)
}

function setSource(source) {
  bankFilter.source = source
  reloadBank()
}

onMounted(async () => {
  await quizStore.fetchBank()
})
</script>

<style scoped>
.quiz-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.quiz-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.quiz-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  font-size: 14px;
}
.quiz-option:hover:not(:disabled) {
  border-color: var(--primary-light);
  background: var(--primary-soft);
}
.quiz-option.selected {
  border-color: var(--primary);
  background: var(--primary-soft);
  box-shadow: 0 0 0 3px var(--primary-soft);
}
.quiz-option.correct {
  border-color: #16a34a;
  background: rgba(34, 197, 94, 0.12);
}
.quiz-option.wrong {
  border-color: #dc2626;
  background: rgba(239, 68, 68, 0.1);
}
.opt-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}
.quiz-feedback {
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 10px;
}
.quiz-feedback.ok { background: rgba(34, 197, 94, 0.12); color: #16a34a; }
.quiz-feedback.bad { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.quiz-actions { display: flex; gap: 8px; margin-top: 14px; }
.quiz-done { text-align: center; padding: 24px 0; }
.quiz-score { font-size: 40px; font-weight: 800; color: var(--primary); }

.ai-generate {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed var(--border);
  border-radius: 10px;
}
.bank-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 8px;
}
.bank-main { flex: 1; }
.bank-q { display: flex; align-items: flex-start; gap: 8px; flex-wrap: wrap; }
.bank-text { font-weight: 600; }
.bank-options { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; }
.bank-opt { font-size: 13px; color: var(--text-muted); }
.bank-opt.answer { color: #16a34a; font-weight: 700; }
.tag-ai { background: rgba(139, 92, 246, 0.12); color: #7c3aed; }

.mastery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.mastery-card {
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}
.mastery-card.overall { border-color: var(--primary-light); background: var(--primary-soft); }
.mastery-num { font-size: 28px; font-weight: 800; color: var(--primary); }
.mastery-num.small { font-size: 18px; }
.mastery-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.bar {
  height: 8px;
  border-radius: 4px;
  background: var(--border);
  overflow: hidden;
  margin: 8px 0;
}
.bar-fill { height: 100%; border-radius: 4px; background: var(--primary); }
@media (max-width: 768px) {
  .bank-item { flex-direction: column; }
}
</style>
