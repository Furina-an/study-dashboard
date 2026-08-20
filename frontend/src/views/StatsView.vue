<template>
  <div class="page">
    <h1>学习统计</h1>

    <section class="stat-cards">
      <div class="stat-card">
        <div class="stat-value">{{ statsStore.today?.focus_minutes ?? '–' }}</div>
        <div class="stat-label">今日专注（分钟）</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ statsStore.today?.focus_count ?? '–' }}</div>
        <div class="stat-label">今日专注次数</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ statsStore.today?.tasks_completed ?? '–' }}</div>
        <div class="stat-label">今日完成任务</div>
      </div>
      <div class="stat-card accent">
        <div class="stat-value">🔥 {{ statsStore.streak?.current_streak ?? '–' }}</div>
        <div class="stat-label">连续专注（天）</div>
        <div class="stat-sub">
          最长 {{ statsStore.streak?.best_streak ?? 0 }} 天 · 共专注 {{ statsStore.streak?.focused_days ?? 0 }} 天
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>专注热力图（近 105 天）</h2>
        <span class="muted">共 {{ totalMinutes }} 分钟</span>
      </div>
      <p v-if="statsStore.loading" class="muted">加载中…</p>
      <p v-else-if="statsStore.error" class="error-text">{{ statsStore.error }}</p>
      <EChart v-else :option="heatmapOption" height="220px" />
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>专注趋势</h2>
        <select v-model.number="days" class="input narrow" @change="refresh">
          <option :value="7">近 7 天</option>
          <option :value="14">近 14 天</option>
          <option :value="30">近 30 天</option>
        </select>
      </div>
      <EChart v-if="trendPoints.length" :option="trendOption" height="300px" />
      <p v-else class="muted">暂无数据</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import EChart from '../components/EChart.vue'
import { useStatsStore } from '../stores/stats'
import { useThemeStore } from '../stores/theme'

const statsStore = useStatsStore()
const theme = useThemeStore()
const isDark = computed(() => theme.dark)
const days = ref(7)

const totalMinutes = computed(() =>
  statsStore.heatmap.reduce((sum, point) => sum + point.focus_minutes, 0),
)

const trendPoints = computed(() => statsStore.trend)

const trendOption = computed(() => {
  const gradient = {
    type: 'linear',
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: '#6366f1' },
      { offset: 1, color: '#a5b4fc' },
    ],
  }
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: isDark.value ? '#171b2d' : '#ffffff',
      borderColor: isDark.value ? '#2a3050' : '#e5e8f2',
      textStyle: { color: isDark.value ? '#e6e9f5' : '#0f172a' },
      formatter: (params) => {
        const point = params[0]
        return `${point.name}<br/>专注 ${point.value} 分钟`
      },
    },
    grid: { left: 44, right: 16, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: trendPoints.value.map((p) => p.date.slice(5)),
      axisLine: { lineStyle: { color: isDark.value ? '#2a3050' : '#e5e8f2' } },
      axisTick: { show: false },
      axisLabel: { color: isDark.value ? '#8b93b0' : '#94a3b8', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: isDark.value ? '#1d2236' : '#eef1f8' } },
      axisLabel: { color: isDark.value ? '#8b93b0' : '#94a3b8', fontSize: 11 },
    },
    series: [
      {
        name: '专注分钟',
        type: 'bar',
        data: trendPoints.value.map((p) => p.focus_minutes),
        barMaxWidth: 26,
        itemStyle: {
          borderRadius: [6, 6, 2, 2],
          color: gradient,
        },
        emphasis: { itemStyle: { color: '#4f46e5' } },
      },
    ],
  }
})

const heatmapOption = computed(() => {
  const points = statsStore.heatmap
  if (!points.length) return {}
  const start = points[0].date
  const end = points[points.length - 1].date
  return {
    tooltip: {
      backgroundColor: isDark.value ? '#171b2d' : '#ffffff',
      borderColor: isDark.value ? '#2a3050' : '#e5e8f2',
      textStyle: { color: isDark.value ? '#e6e9f5' : '#0f172a' },
      formatter: (params) => {
        const [dateStr, minutes] = params.value
        return `${dateStr}<br/>专注 <b>${minutes}</b> 分钟`
      },
    },
    visualMap: {
      min: 0,
      max: 120,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      text: ['多', '少'],
      textStyle: { color: isDark.value ? '#8b93b0' : '#94a3b8', fontSize: 11 },
      inRange: {
        color: isDark.value
          ? ['#1d2236', '#2d2f52', '#4f46e5', '#6366f1', '#818cf8', '#fbbf24']
          : ['#f1f5f9', '#e0e7ff', '#a5b4fc', '#6366f1', '#4f46e5', '#f59e0b'],
      },
    },
    calendar: {
      range: [start, end],
      cellSize: ['auto', 14],
      itemStyle: { borderWidth: 3, borderColor: isDark.value ? '#0f1220' : '#ffffff', borderRadius: 3 },
      splitLine: { show: false },
      yearLabel: { show: false },
      dayLabel: { nameMap: ['日', '一', '二', '三', '四', '五', '六'], fontSize: 10, color: '#94a3b8' },
      monthLabel: { nameMap: 'CN', fontSize: 11, color: isDark.value ? '#8b93b0' : '#64748b' },
    },
    series: [
      {
        type: 'heatmap',
        coordinateSystem: 'calendar',
        data: points.map((p) => [p.date, p.focus_minutes]),
      },
    ],
  }
})

function refresh() {
  statsStore.refresh(days.value)
}

onMounted(refresh)
</script>
