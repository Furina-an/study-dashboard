<template>
  <div class="page">
    <h1>任务管理</h1>

    <section class="panel">
      <form class="task-form" @submit.prevent="createTask">
        <input
          v-model="form.title"
          class="input grow"
          placeholder="任务标题（必填）"
          maxlength="200"
          required
        />
        <input
          v-model="form.subject"
          class="input"
          list="subject-datalist"
          placeholder="科目"
          maxlength="50"
        />
        <datalist id="subject-datalist">
          <option v-for="subject in settings.taskSubjects" :key="subject" :value="subject"></option>
        </datalist>
        <input
          v-model.number="form.estimated_minutes"
          class="input narrow"
          type="number"
          min="1"
          max="600"
          placeholder="分钟"
          title="预计分钟"
        />
        <select v-model="form.plan_id" class="input" title="所属计划">
          <option :value="null">不挂计划</option>
          <option v-for="plan in plansStore.plans" :key="plan.id" :value="plan.id">
            {{ '　'.repeat(depthOf(plan)) }}{{ plan.title }}
          </option>
        </select>
        <label class="checkbox-line" title="习惯任务：按频率打卡，不进入已完成状态">
          <input v-model="form.is_habit" type="checkbox" />
          🔁 设为习惯
        </label>
        <template v-if="form.is_habit">
          <select v-model="form.habit_frequency" class="input" title="打卡频率">
            <option value="daily">每天</option>
            <option value="weekdays">工作日</option>
            <option value="custom">自定义星期</option>
          </select>
          <div v-if="form.habit_frequency === 'custom'" class="weekday-row">
            <label v-for="day in weekdays" :key="day.value" class="weekday-chip" :class="{ active: form.habit_days.includes(day.value) }">
              <input v-model="form.habit_days" type="checkbox" :value="day.value" class="hidden-check" />
              {{ day.label }}
            </label>
          </div>
        </template>
        <button class="btn primary" type="submit" :disabled="submitting">
          {{ submitting ? '添加中…' : '添加任务' }}
        </button>
      </form>
      <p v-if="formError" class="error-text">{{ formError }}</p>
    </section>

    <section class="panel">
      <div class="filter-tabs">
        <button
          v-for="f in filters"
          :key="f.value"
          class="chip"
          :class="{ active: filter === f.value }"
          @click="onFilterChange(f.value)"
        >
          {{ f.label }}
        </button>
        <span class="filter-gap"></span>
        <select
          v-model="filterPlanId"
          class="input narrow"
          title="按所属计划筛选"
          @change="onFilterPlanChange"
        >
          <option :value="null">全部计划</option>
          <option v-for="plan in plansStore.plans" :key="plan.id" :value="plan.id">
            {{ '　'.repeat(depthOf(plan)) }}{{ plan.title }}
          </option>
        </select>
      </div>

      <p v-if="tasksStore.loading">加载中…</p>
      <p v-else-if="!filteredTasks.length" class="muted">这个分组下还没有任务。</p>
      <ul v-else class="task-list">
        <li v-for="task in filteredTasks" :key="task.id" class="task-item" :class="task.status">
          <div class="task-main">
            <span class="task-title">{{ task.title }}</span>
            <span v-if="task.is_habit" class="tag tag-habit">🔁 习惯</span>
            <span v-if="task.plan_id && planName(task.plan_id)" class="task-plan">{{ planName(task.plan_id) }}</span>
            <span v-if="task.subject" class="task-subject">{{ task.subject }}</span>
            <span class="task-meta">预计 {{ task.estimated_minutes }} 分钟</span>
            <span v-if="task.is_habit" class="habit-streak">🔥 {{ habitOf(task)?.current_streak ?? 0 }} 天</span>
            <span v-if="task.is_habit && habitOf(task)?.scheduled_today === false" class="tag tag-muted">今日非打卡日</span>
          </div>
          <div class="task-actions">
            <template v-if="task.is_habit">
              <button
                v-if="!habitOf(task)?.checked_today"
                class="btn small success"
                :disabled="checkingId === task.id"
                @click="doCheckin(task)"
              >
                {{ checkingId === task.id ? '打卡中…' : '✅ 打卡' }}
              </button>
              <button
                v-else
                class="btn small"
                :disabled="checkingId === task.id"
                @click="undoCheckin(task)"
              >
                {{ checkingId === task.id ? '撤销中…' : '已打卡 ✓ 撤销' }}
              </button>
            </template>
            <template v-else>
              <button v-if="task.status !== 'done'" class="btn small primary" @click="setStatus(task, 'done')">完成</button>
              <button v-if="task.status === 'done'" class="btn small" @click="setStatus(task, 'todo')">重开</button>
            </template>
            <button class="btn small" @click="toggleDoing(task)">
              {{ task.status === 'doing' ? '取消进行' : '开始做' }}
            </button>
            <button class="btn small danger" @click="removeTask(task)">删除</button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useTasksStore } from '../stores/tasks'
import { usePlansStore } from '../stores/plans'
import { useSettingsStore } from '../stores/settings'

const tasksStore = useTasksStore()
const plansStore = usePlansStore()
const settings = useSettingsStore()

const form = ref({
  title: '',
  subject: '',
  estimated_minutes: 25,
  plan_id: null,
  is_habit: false,
  habit_frequency: 'daily',
  habit_days: [],
})
const submitting = ref(false)
const formError = ref('')
const filter = ref('all')
const filterPlanId = ref(null)
const checkingId = ref(null)

const filters = [
  { value: 'all', label: '全部' },
  { value: 'todo', label: '待办' },
  { value: 'doing', label: '进行中' },
  { value: 'done', label: '已完成' },
  { value: 'habit', label: '🔁 习惯' },
]

const weekdays = [
  { value: 1, label: '一' },
  { value: 2, label: '二' },
  { value: 3, label: '三' },
  { value: 4, label: '四' },
  { value: 5, label: '五' },
  { value: 6, label: '六' },
  { value: 7, label: '日' },
]

const filteredTasks = computed(() => {
  let tasks = tasksStore.tasks
  if (filter.value === 'habit') tasks = tasks.filter((task) => task.is_habit)
  else if (filter.value !== 'all') tasks = tasks.filter((task) => task.status === filter.value)
  return tasks
})

function habitOf(task) {
  return tasksStore.habitById(task.id)
}

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

function planName(planId) {
  const plan = plansStore.planById(planId)
  return plan ? plan.title : ''
}

async function loadPlans() {
  if (!plansStore.plans.length) await plansStore.fetchPlans()
}

function onFilterChange(value) {
  filter.value = value
  if (value === 'habit') {
    tasksStore.fetchTasks(filterPlanId.value, true)
  } else {
    tasksStore.fetchTasks(filterPlanId.value)
  }
}

function onFilterPlanChange() {
  onFilterChange(filter.value)
}

async function loadTasks() {
  await loadPlans()
  tasksStore.fetchTasks(filterPlanId.value, filter.value === 'habit' ? true : undefined)
  tasksStore.fetchHabits()
}

onMounted(async () => {
  await settings.fetch()
  form.value.estimated_minutes = settings.defaultEstimatedMinutes
  form.value.habit_frequency = settings.habitFrequencyDefault
  await loadTasks()
})

async function createTask() {
  const title = form.value.title.trim()
  if (!title) return
  submitting.value = true
  formError.value = ''
  try {
    await tasksStore.addTask({
      title,
      subject: form.value.subject.trim(),
      estimated_minutes: form.value.estimated_minutes || 25,
      plan_id: form.value.plan_id,
      is_habit: form.value.is_habit,
      habit_frequency: form.value.is_habit ? form.value.habit_frequency : 'daily',
      habit_days: form.value.habit_frequency === 'custom' ? form.value.habit_days : undefined,
    })
    form.value = {
      title: '',
      subject: '',
      estimated_minutes: settings.defaultEstimatedMinutes,
      plan_id: null,
      is_habit: false,
      habit_frequency: settings.habitFrequencyDefault,
      habit_days: [],
    }
    if (filter.value === 'habit') await tasksStore.fetchTasks(filterPlanId.value, true)
    await tasksStore.fetchHabits()
  } catch (e) {
    formError.value = e.message
  } finally {
    submitting.value = false
  }
}

async function setStatus(task, status) {
  try {
    await tasksStore.updateTask(task.id, { status })
  } catch (e) {
    formError.value = e.message
  }
}

function toggleDoing(task) {
  if (task.is_habit) return
  setStatus(task, task.status === 'doing' ? 'todo' : 'doing')
}

async function doCheckin(task) {
  checkingId.value = task.id
  try {
    await tasksStore.checkin(task.id)
  } catch (e) {
    formError.value = e.message
  } finally {
    checkingId.value = null
  }
}

async function undoCheckin(task) {
  checkingId.value = task.id
  try {
    await tasksStore.uncheckin(task.id)
  } catch (e) {
    formError.value = e.message
  } finally {
    checkingId.value = null
  }
}

async function removeTask(task) {
  if (!window.confirm(`确定删除「${task.title}」？`)) return
  try {
    await tasksStore.removeTask(task.id)
  } catch (e) {
    formError.value = e.message
  }
}
</script>

<style scoped>
.weekday-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.weekday-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.weekday-chip.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  font-weight: 700;
}

.hidden-check {
  display: none;
}

.tag-muted {
  background: var(--surface-soft);
  color: var(--text-muted);
  border: 1px solid var(--border);
}
</style>
