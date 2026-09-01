<template>
  <div class="page">
    <h1>日历与看板</h1>
    <p class="date-line">按截止日期规划任务，拖拽看板快速调整状态。</p>

    <div class="filter-tabs page-tabs">
      <button class="chip" :class="{ active: tab === 'month' }" @click="tab = 'month'">📅 月历</button>
      <button class="chip" :class="{ active: tab === 'kanban' }" @click="tab = 'kanban'">🗂️ 看板</button>
    </div>

    <template v-if="tab === 'month'">
      <section class="panel">
        <div class="panel-head">
          <button class="btn small" @click="shiftMonth(-1)">‹ 上月</button>
          <h2>{{ yearMonth }}</h2>
          <button class="btn small" @click="shiftMonth(1)">下月 ›</button>
          <button class="btn small ghost" @click="goToday">今天</button>
        </div>
        <div class="cal-grid">
          <div v-for="weekday in weekdayLabels" :key="weekday" class="cal-weekday">{{ weekday }}</div>
          <div
            v-for="cell in cells"
            :key="cell.key"
            class="cal-cell"
            :class="{ 'cal-muted': !cell.inMonth, 'cal-today': cell.isToday, 'cal-selected': selected === cell.key }"
            @click="selected = cell.key"
          >
            <div class="cal-daynum">{{ cell.day }}</div>
            <div class="cal-items">
              <div v-for="item in cell.items.slice(0, 3)" :key="item.key" class="cal-item" :class="item.kind">
                {{ item.text }}
              </div>
              <div v-if="cell.items.length > 3" class="cal-more">+{{ cell.items.length - 3 }} 项</div>
            </div>
            <div v-if="focusMinutes[cell.key]" class="cal-focus">🔥 {{ focusMinutes[cell.key] }}分</div>
          </div>
        </div>
      </section>

      <section v-if="selected" class="panel">
        <div class="panel-head">
          <h2>{{ selected }} 安排</h2>
          <router-link to="/tasks" class="btn small ghost">去任务页 →</router-link>
        </div>
        <h3 class="muted">任务（{{ dayTasksDetail.length }}）</h3>
        <ul class="task-mini-list">
          <li v-for="task in dayTasksDetail" :key="task.id">
            <span class="task-title">{{ task.title }}</span>
            <span class="filter-gap"></span>
            <span class="tag" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span>
          </li>
          <li v-if="!dayTasksDetail.length" class="muted">无</li>
        </ul>
        <h3 class="muted">复习（{{ dayReviewsDetail.length }}）</h3>
        <ul class="task-mini-list">
          <li v-for="review in dayReviewsDetail" :key="review.id">
            <span class="task-title">{{ review.source_title }}</span>
            <span class="filter-gap"></span>
            <span class="tag tag-due">{{ review.source_type === 'plan' ? '计划' : '任务' }}</span>
          </li>
          <li v-if="!dayReviewsDetail.length" class="muted">无</li>
        </ul>
        <p v-if="focusMinutes[selected]" class="muted">🔥 当日专注 {{ focusMinutes[selected] }} 分钟</p>
      </section>
    </template>

    <template v-else>
      <section class="panel">
        <div class="panel-head">
          <h2>任务看板</h2>
          <span class="muted">把卡片拖到目标列即可更新状态</span>
        </div>
        <div class="kanban">
          <div
            v-for="col in kanbanCols"
            :key="col.status"
            class="kanban-col"
            @dragover.prevent
            @drop="onDrop(col.status)"
          >
            <h3>{{ col.label }} <span class="muted">({{ kanbanTasks(col.status).length }})</span></h3>
            <div
              v-for="task in kanbanTasks(col.status)"
              :key="task.id"
              class="kanban-card"
              :class="{ 'kanban-overdue': isOverdue(task) }"
              draggable="true"
              @dragstart="dragTask = task"
              @dragend="dragTask = null"
            >
              <div class="task-title">{{ task.title }}</div>
              <div class="kanban-meta">
                <span v-if="task.subject" class="tag">{{ task.subject }}</span>
                <span v-if="task.due_date" class="tag" :class="{ 'tag-overdue': isOverdue(task) }">📅 {{ task.due_date }}</span>
                <span v-else class="tag tag-muted">无截止</span>
              </div>
            </div>
            <p v-if="!kanbanTasks(col.status).length" class="muted kanban-empty">拖到这里</p>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { useTasksStore } from '../stores/tasks'

const tasksStore = useTasksStore()
const tab = ref('month')
const viewYear = ref(new Date().getFullYear())
const viewMonth = ref(new Date().getMonth())
const selected = ref(new Date().toISOString().slice(0, 10))
const cal = ref({ tasks: [], reviews: [], focus_minutes: {} })
const dragTask = ref(null)

const weekdayLabels = ['一', '二', '三', '四', '五', '六', '日']
const kanbanCols = [
  { status: 'todo', label: '📥 待办' },
  { status: 'doing', label: '⚡ 进行中' },
  { status: 'done', label: '✅ 已完成' },
]

const yearMonth = computed(() => `${viewYear.value} 年 ${viewMonth.value + 1} 月`)

const gridStart = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value, 1)
  const offset = (first.getDay() + 6) % 7 // 周一为一周开始
  return new Date(viewYear.value, viewMonth.value, 1 - offset)
})

const cells = computed(() => {
  const list = []
  const todayIso = new Date().toISOString().slice(0, 10)
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(
      gridStart.value.getFullYear(),
      gridStart.value.getMonth(),
      gridStart.value.getDate() + i,
    )
    const iso = toIso(d)
    list.push({
      key: iso,
      day: d.getDate(),
      inMonth: d.getMonth() === viewMonth.value,
      isToday: iso === todayIso,
      items: [...dayItems(iso)],
    })
  }
  return list
})

const focusMinutes = computed(() => cal.value.focus_minutes || {})

function toIso(d) {
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function dayItems(iso) {
  const tasks = cal.value.tasks
    .filter((t) => t.due_date === iso)
    .map((t) => ({ key: `t${t.id}`, kind: 'task', text: t.title }))
  const reviews = cal.value.reviews
    .filter((r) => r.due_date === iso)
    .map((r) => ({ key: `r${r.id}`, kind: 'review', text: `🔁 ${r.source_title}` }))
  return [...tasks, ...reviews]
}

const dayTasksDetail = computed(() => cal.value.tasks.filter((t) => t.due_date === selected.value))
const dayReviewsDetail = computed(() => cal.value.reviews.filter((r) => r.due_date === selected.value))

async function fetchCalendar() {
  const start = toIso(gridStart.value)
  const last = new Date(
    gridStart.value.getFullYear(),
    gridStart.value.getMonth(),
    gridStart.value.getDate() + 41,
  )
  cal.value = await api.calendarData(start, toIso(last))
}

function shiftMonth(delta) {
  viewMonth.value += delta
  if (viewMonth.value < 0) {
    viewMonth.value = 11
    viewYear.value -= 1
  }
  if (viewMonth.value > 11) {
    viewMonth.value = 0
    viewYear.value += 1
  }
}

function goToday() {
  const now = new Date()
  viewYear.value = now.getFullYear()
  viewMonth.value = now.getMonth()
  selected.value = toIso(now)
}

function kanbanTasks(status) {
  return tasksStore.tasks.filter((t) => !t.is_habit && t.status === status)
}

function isOverdue(task) {
  if (task.status === 'done' || !task.due_date) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(`${task.due_date}T00:00:00`)
  return due < today
}

function statusLabel(status) {
  return { todo: '待办', doing: '进行中', done: '完成' }[status] || status
}

function statusClass(status) {
  return { todo: 'tag-due', doing: 'tag-habit', done: 'tag-done' }[status] || ''
}

async function onDrop(status) {
  if (!dragTask.value || dragTask.value.status === status) return
  const task = dragTask.value
  dragTask.value = null
  try {
    await tasksStore.updateTask(task.id, { status })
  } catch (e) {
    /* 更新失败时看板保持原状态 */
  }
}

watch([viewYear, viewMonth], () => {
  fetchCalendar()
})

onMounted(async () => {
  try {
    await fetchCalendar()
  } catch (e) {
    /* 后端未就绪时静默，用户可切页重试 */
  }
  if (!tasksStore.tasks.length) await tasksStore.fetchTasks()
})
</script>
