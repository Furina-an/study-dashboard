<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>复习计划</h1>
        <p class="date-line">艾宾浩斯遗忘曲线 · 任务/计划完成后自动生成 1/2/4/7/15/30 天复习节点</p>
      </div>
      <button
        class="btn primary"
        :disabled="!dueCount || busy"
        @click="completeAllDue"
      >
        {{ busy ? '处理中…' : `一键完成到期（${dueCount}）` }}
      </button>
    </div>

    <div class="filter-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        class="chip"
        :class="{ active: status === tab.value }"
        @click="switchTab(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="reviewsStore.loading" class="muted">加载中…</p>
    <p v-else-if="reviewsStore.error" class="error-text">{{ reviewsStore.error }}</p>
    <div v-else-if="!filtered.length" class="empty-state">
      这个分组下暂时没有复习项。
      <template v-if="status === 'due'">
        去 <router-link to="/tasks">任务页</router-link> 完成任务后会自动生成复习计划。
      </template>
    </div>

    <ul v-else class="review-list">
      <li
        v-for="review in filtered"
        :key="review.id"
        class="review-item"
        :class="{ done: review.reviewed_at }"
      >
        <div class="review-main">
          <span class="review-icon">{{ review.source_type === 'task' ? '📋' : '🗂️' }}</span>
          <div class="review-info">
            <div class="review-title">
              {{ review.source_title }}
              <span class="tag" :class="review.source_type === 'plan' ? 'tag-plan' : 'tag-task'">
                {{ review.source_type === 'plan' ? '计划' : '任务' }}
              </span>
              <span class="tag tag-empty">{{ intervalLabel(review.interval_days) }}</span>
              <span v-if="!review.reviewed_at && isOverdue(review.due_date)" class="tag tag-overdue">
                已逾期 {{ overdueDays(review.due_date) }} 天
              </span>
              <span v-else-if="!review.reviewed_at && isToday(review.due_date)" class="tag tag-due">今天到期</span>
            </div>
            <div class="review-meta">间隔 {{ review.interval_days }} 天 · {{ review.source_type === 'plan' ? '计划完成时生成' : '任务完成时生成' }}</div>
          </div>
        </div>
        <div class="review-side">
          <span class="review-date">📅 {{ formatDate(review.due_date) }}</span>
          <button v-if="!review.reviewed_at" class="btn small primary" :disabled="busy" @click="complete(review)">
            复习完成
          </button>
          <span v-else class="review-done">✅ {{ formatDateTime(review.reviewed_at) }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useReviewsStore } from '../stores/reviews'

const reviewsStore = useReviewsStore()

const REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]
const status = ref('due')
const busy = ref(false)

const tabs = [
  { value: 'due', label: '待复习（含逾期）' },
  { value: 'upcoming', label: '未来 30 天' },
  { value: 'all', label: '全部记录' },
]

const filtered = computed(() => reviewsStore.reviews)
const dueCount = computed(() =>
  reviewsStore.reviews.filter((r) => !r.reviewed_at && isOverdue(r.due_date)).length +
  reviewsStore.reviews.filter((r) => !r.reviewed_at && isToday(r.due_date)).length,
)

function switchTab(value) {
  status.value = value
  reviewsStore.fetch(value)
}

function intervalLabel(days) {
  const index = REVIEW_INTERVALS.indexOf(days)
  return index >= 0 ? `第 ${index + 1} 次复习` : `${days} 天`
}

function parseDate(value) {
  return new Date(`${value}T00:00:00`)
}

function isToday(value) {
  const today = new Date()
  const target = parseDate(value)
  return (
    target.getFullYear() === today.getFullYear() &&
    target.getMonth() === today.getMonth() &&
    target.getDate() === today.getDate()
  )
}

function isOverdue(value) {
  return parseDate(value) < new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00`)
}

function overdueDays(value) {
  const today = new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00`)
  return Math.max(0, Math.round((today - parseDate(value)) / 86400000))
}

function formatDate(value) {
  return parseDate(value).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatDateTime(value) {
  const date = new Date(value)
  return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function complete(review) {
  busy.value = true
  try {
    await reviewsStore.complete(review.id)
  } catch (e) {
    reviewsStore.error = e.message
  } finally {
    busy.value = false
  }
}

async function completeAllDue() {
  busy.value = true
  try {
    await reviewsStore.completeDue()
  } catch (e) {
    reviewsStore.error = e.message
  } finally {
    busy.value = false
  }
}

onMounted(() => reviewsStore.fetch('due'))
</script>
