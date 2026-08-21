<template>
  <div class="page">
    <div class="dashboard-hero">
      <h1>{{ greeting }}</h1>
      <p class="date-line">{{ todayText }}</p>
    </div>

    <p v-if="statsStore.error" class="banner error">
      {{ statsStore.error }}（双击项目根目录 start.bat 或 启动后端.bat 启动后端；云端见部署文档）
    </p>

    <section class="stat-cards">
      <div class="stat-card">
        <div class="stat-value">{{ statsStore.today?.focus_minutes ?? '–' }}</div>
        <div class="stat-label">今日专注（分钟）</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ statsStore.today?.focus_count ?? '–' }}</div>
        <div class="stat-label">专注次数</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ statsStore.today?.tasks_completed ?? '–' }}</div>
        <div class="stat-label">完成任务</div>
      </div>
      <div class="stat-card accent">
        <div class="stat-value">🔥 {{ statsStore.streak?.current_streak ?? '–' }}</div>
        <div class="stat-label">连续专注（天）</div>
        <div class="stat-sub">最长 {{ statsStore.streak?.best_streak ?? 0 }} 天</div>
      </div>
    </section>

    <!-- 总站 · 功能中心 -->
    <section class="hub-section">
      <div class="hub-head">
        <h2>🧭 功能中心</h2>
        <span class="muted">学习管理台 + 高数复习，按账号数据隔离</span>
      </div>
      <div class="hub-grid">
        <router-link v-for="card in visibleCards" :key="card.to" :to="card.to" class="hub-card" :class="card.accent">
          <span class="hub-icon">{{ card.icon }}</span>
          <div class="hub-info">
            <div class="hub-title">
              {{ card.title }}
              <span v-if="card.badge" class="tag tag-new">{{ card.badge }}</span>
            </div>
            <div class="hub-desc">{{ card.desc }}</div>
            <div v-if="card.to === '/math'" class="math-mini">
              <span class="math-mini-text">管理员发布 · 全员可浏览下载</span>
            </div>
          </div>
          <span class="hub-arrow">→</span>
        </router-link>
      </div>
    </section>

    <!-- 预留功能区 -->
    <section class="hub-section">
      <div class="hub-head">
        <h2>🧩 预留功能区</h2>
        <span class="muted">规划中，后续迭代逐步接入</span>
      </div>
      <div class="hub-grid">
        <div v-for="card in reservedCards" :key="card.title" class="hub-card reserved">
          <span class="hub-icon">{{ card.icon }}</span>
          <div class="hub-info">
            <div class="hub-title">
              {{ card.title }}
              <span class="tag tag-reserved">预留</span>
            </div>
            <div class="hub-desc">{{ card.desc }}</div>
          </div>
        </div>
      </div>
    </section>

    <div class="grid-2">
      <section class="panel">
        <div class="panel-head">
          <h2>今日打卡</h2>
          <router-link to="/tasks" class="btn small ghost">去打卡 →</router-link>
        </div>
        <p v-if="!tasksStore.habits.length" class="muted">
          还没有习惯，去 <router-link to="/tasks">任务页</router-link> 把任务设为「习惯」。
        </p>
        <ul v-else class="task-mini-list">
          <li v-for="habit in tasksStore.habits" :key="habit.id">
            <span>{{ habit.checked_today ? '✅' : '⬜' }}</span>
            <span class="task-title">{{ habit.title }}</span>
            <span class="filter-gap"></span>
            <span class="habit-streak">🔥 {{ habit.current_streak }} 天</span>
          </li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>到期复习</h2>
          <router-link to="/reviews" class="btn small ghost">去复习 →</router-link>
        </div>
        <p v-if="!reviewsStore.reviews.length" class="muted">
          暂无到期复习。完成任务后会自动生成 1/2/4/7/15/30 天复习计划。
        </p>
        <ul v-else class="task-mini-list">
          <li v-for="review in reviewsStore.reviews.slice(0, 5)" :key="review.id">
            <span>{{ review.source_type === 'task' ? '📋' : '🗂️' }}</span>
            <span class="task-title">{{ review.source_title }}</span>
            <span v-if="isOverdue(review.due_date)" class="tag tag-overdue">逾期</span>
            <span v-else class="tag tag-due">今天</span>
          </li>
        </ul>
      </section>
    </div>

    <section class="panel">
      <h2>进行中的任务</h2>
      <ul v-if="tasksStore.doingTasks.length" class="task-mini-list">
        <li v-for="task in tasksStore.doingTasks" :key="task.id">
          <span class="task-title">{{ task.title }}</span>
          <span v-if="task.subject" class="task-subject">{{ task.subject }}</span>
        </li>
      </ul>
      <p v-else class="muted">
        暂无进行中的任务，去 <router-link to="/tasks">任务页</router-link> 添加一个吧。
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useStatsStore } from '../stores/stats'
import { useTasksStore } from '../stores/tasks'
import { useReviewsStore } from '../stores/reviews'
import { useSettingsStore } from '../stores/settings'

const auth = useAuthStore()
const statsStore = useStatsStore()
const tasksStore = useTasksStore()
const reviewsStore = useReviewsStore()
const settings = useSettingsStore()

const liveCards = [
  {
    key: 'math',
    to: '/math',
    icon: '🧮',
    title: '高数资料',
    desc: '管理员发布的高数学习资料 · 全员浏览下载',
    accent: 'math',
  },
  { key: 'pomodoro', to: '/pomodoro', icon: '🍅', title: '番茄专注', desc: '自定义时长专注计时，完成后计入统计' },
  { key: 'tasks', to: '/tasks', icon: '✅', title: '任务管理', desc: '待办 + 习惯打卡，可按计划归类' },
  { key: 'plans', to: '/plans', icon: '🗂️', title: '计划拆解', desc: '大计划拆小计划，手动 / 模板 / AI' },
  { key: 'files', to: '/files', icon: '📁', title: '学习文件', desc: '上传学习资料，运营整合入库' },
  { key: 'reviews', to: '/reviews', icon: '🔁', title: '复习提醒', desc: '自定义艾宾浩斯间隔复习节点' },
  { key: 'stats', to: '/stats', icon: '📊', title: '统计看板', desc: '专注热力图、30 天趋势、连续天数' },
  { key: 'ai', to: '/ai-settings', icon: '🤖', title: 'AI 服务', desc: '配置 OpenAI 兼容接口，用于计划 AI 拆解' },
  { key: 'tutor', to: '/tutor', icon: '🧑‍🏫', title: 'AI 助教', desc: '引导式辅导答疑，随时提问' },
  { key: 'quiz', to: '/quiz', icon: '📝', title: '题库测验', desc: '题库 + AI 出题 + 掌握度统计' },
  { key: 'settings', to: '/settings', icon: '⚙️', title: '数据备份', desc: '个性化设置、导出 / 导入备份，部署与端口' },
]

const visibleCards = computed(() => {
  const configured = settings.hubCards
  const ordered = configured.length
    ? configured
        .filter((card) => card.visible !== false)
        .slice()
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map((card) => liveCards.find((item) => item.key === card.key))
        .filter(Boolean)
    : liveCards.filter((card) => card.key !== 'settings')
  // 设置卡片固定展示
  const settingsCard = liveCards.find((card) => card.key === 'settings')
  if (settingsCard) ordered.push(settingsCard)
  return ordered
})

const reservedCards = [
  { icon: '🎯', title: '冲刺计划', desc: '目标 → 冲刺路线图与阶段里程碑' },
  { icon: '🏆', title: '雅思备考', desc: '听说读写专项数据与备考报告' },
  { icon: '⏱️', title: '迷你番茄钟', desc: '独立轻量番茄钟，快捷桌面入口' },
  { icon: '📈', title: '周 / 月报告', desc: '学习数据导出 Excel / PDF' },
]

const greeting = computed(() => {
  if (auth.user?.username) return `嗨，${auth.user.username}，欢迎回到总站 💪`
  return '欢迎回到总站 💪'
})

const todayText = computed(() => {
  const today = new Date()
  return today.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
})

function isOverdue(value) {
  const today = new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00`)
  return new Date(`${value}T00:00:00`) < today
}

onMounted(() => {
  settings.fetch()
  statsStore.refresh()
  tasksStore.fetchTasks()
  tasksStore.fetchHabits()
  reviewsStore.fetch('due')
})
</script>
