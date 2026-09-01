<template>
  <div v-if="open" class="modal-backdrop" @click.self="close">
    <div class="modal">
      <h2>✨ AI 每日学习计划</h2>
      <p class="muted">输入目标与截止日期，AI 帮你拆成每天可执行的小任务，并按「每日可投入分钟」自动排期。</p>

      <template v-if="!result">
        <form @submit.prevent="submit">
          <input
            v-model="form.goal"
            class="input"
            placeholder="学习目标（必填，如：考研数学基础一轮）"
            maxlength="100"
            required
          />
          <div class="form-row">
            <input v-model="form.deadline" type="date" class="input" required title="截止日期" />
            <input
              v-model.number="form.daily_minutes"
              type="number"
              class="input"
              min="15"
              max="600"
              placeholder="每天分钟"
              title="每日可投入分钟"
            />
          </div>
          <div class="form-row">
            <input v-model="form.subject" class="input" list="aiplan-subjects" placeholder="科目（可选）" maxlength="50" />
            <datalist id="aiplan-subjects">
              <option v-for="subject in settings.taskSubjects" :key="subject" :value="subject"></option>
            </datalist>
            <select v-model="form.plan_id" class="input" title="挂到计划">
              <option :value="null">自动新建计划</option>
              <option v-for="plan in plansStore.plans" :key="plan.id" :value="plan.id">
                {{ '　'.repeat(depthOf(plan)) }}{{ plan.title }}
              </option>
            </select>
          </div>
          <p v-if="error" class="error-text">{{ error }}</p>
          <div class="modal-actions">
            <button type="button" class="btn" @click="close">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '生成中…' : '生成每日计划' }}
            </button>
          </div>
        </form>
      </template>

      <template v-else>
        <p class="success-text">✅ 已生成「{{ result.plan.title }}」，共 {{ result.tasks.length }} 个任务</p>
        <ul class="task-mini-list">
          <li v-for="task in result.tasks" :key="task.id">
            <span class="task-title">{{ task.title }}</span>
            <span class="filter-gap"></span>
            <span class="task-meta">📅 {{ task.due_date }} · {{ task.estimated_minutes }} 分钟</span>
          </li>
        </ul>
        <div class="modal-actions">
          <button class="btn" @click="close">完成</button>
          <router-link class="btn primary" to="/calendar" @click="close">去日历查看 →</router-link>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { api } from '../api'
import { usePlansStore } from '../stores/plans'
import { useSettingsStore } from '../stores/settings'
import { useTasksStore } from '../stores/tasks'

const props = defineProps({
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const plansStore = usePlansStore()
const settings = useSettingsStore()
const tasksStore = useTasksStore()

function defaultDeadline() {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  return d.toISOString().slice(0, 10)
}

const form = ref({
  goal: '',
  deadline: defaultDeadline(),
  daily_minutes: 120,
  subject: '',
  plan_id: null,
})
const submitting = ref(false)
const error = ref('')
const result = ref(null)

watch(
  () => props.open,
  (open) => {
    if (!open) {
      result.value = null
      error.value = ''
      return
    }
    form.value = {
      goal: '',
      deadline: defaultDeadline(),
      daily_minutes: settings.defaultEstimatedMinutes * 4 || 120,
      subject: '',
      plan_id: null,
    }
    if (!settings.loaded) settings.fetch()
    if (!plansStore.plans.length) plansStore.fetchPlans()
  },
)

function depthOf(plan, seen = new Set()) {
  let depth = 0
  let current = plan
  while (current.parent_id != null) {
    if (seen.has(current.id)) break
    seen.add(current.id)
    depth += 1
    current = plansStore.planById(current.parent_id)
    if (!current) break
  }
  return depth
}

async function submit() {
  if (!form.value.goal.trim() || !form.value.deadline) return
  submitting.value = true
  error.value = ''
  try {
    result.value = await api.dailyPlan({
      goal: form.value.goal.trim(),
      deadline: form.value.deadline,
      daily_minutes: form.value.daily_minutes || 120,
      subject: form.value.subject.trim(),
      plan_id: form.value.plan_id,
    })
    tasksStore.fetchTasks()
    plansStore.fetchPlans()
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

function close() {
  emit('close')
}
</script>
