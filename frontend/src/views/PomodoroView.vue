<template>
  <div class="page pomodoro-page">
    <h1>专注计时</h1>

    <section class="panel timer-panel">
      <div class="timer-options">
        <button
          v-for="option in durations"
          :key="option"
          class="chip"
          :class="{ active: durationMin === option && !running }"
          :disabled="running"
          @click="setDuration(option)"
        >
          {{ option }} 分钟
        </button>
      </div>

      <TimerCircle :total="durationMin * 60" :remaining="remaining" />

      <div class="timer-controls">
        <button v-if="!running" class="btn primary big" @click="start">开始</button>
        <button v-else class="btn big" @click="pause">暂停</button>
        <button class="btn big" @click="reset">重置</button>
      </div>
      <p class="muted status-line">{{ statusText }}</p>
    </section>

    <div v-if="showCompleteDialog" class="modal-backdrop">
      <div class="modal">
        <h2>🎉 完成一个番茄钟！</h2>
        <p>这次专注了 {{ finishedMinutes }} 分钟，关联到哪个任务？（可选）</p>
        <select v-model="selectedTaskId" class="input">
          <option :value="null">不关联任务</option>
          <option v-for="task in tasksStore.tasks" :key="task.id" :value="task.id">
            {{ task.title }}{{ task.subject ? '（' + task.subject + '）' : '' }}
          </option>
        </select>
        <div class="modal-actions">
          <button class="btn primary" :disabled="submitting" @click="submitSession">
            {{ submitting ? '记录中…' : '记录本次专注' }}
          </button>
          <button class="btn" @click="closeDialog">放弃记录</button>
        </div>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import TimerCircle from '../components/TimerCircle.vue'
import { api } from '../api'
import { useTasksStore } from '../stores/tasks'
import { useSettingsStore } from '../stores/settings'

const tasksStore = useTasksStore()
const settings = useSettingsStore()

const durations = computed(() => settings.pomodoroDurations)
const durationMin = ref(settings.pomodoroDefault || 25)
const remaining = ref((settings.pomodoroDefault || 25) * 60)
const running = ref(false)
let timerId = null

const showCompleteDialog = ref(false)
const finishedMinutes = ref(0)
const selectedTaskId = ref(null)
const submitting = ref(false)
const submitError = ref('')

const statusText = computed(() => {
  if (running.value) return '专注中，保持节奏…'
  if (remaining.value === durationMin.value * 60) return '准备就绪，点击开始'
  if (remaining.value === 0) return '本次专注已完成'
  return '已暂停'
})

function setDuration(minutes) {
  durationMin.value = minutes
  remaining.value = minutes * 60
}

// 设置加载/更新后同步默认时长
watch(
  () => [settings.pomodoroDurations, settings.pomodoroDefault],
  ([list, def]) => {
    if (!running.value && remaining.value === 0) {
      durationMin.value = def && list.includes(def) ? def : list[0]
      remaining.value = durationMin.value * 60
    }
  },
)

function start() {
  if (remaining.value <= 0) setDuration(durationMin.value)
  running.value = true
  timerId = setInterval(() => {
    remaining.value -= 1
    if (remaining.value <= 0) finish()
  }, 1000)
}

function pause() {
  running.value = false
  if (timerId !== null) {
    clearInterval(timerId)
    timerId = null
  }
}

function reset() {
  pause()
  remaining.value = durationMin.value * 60
}

function finish() {
  pause()
  finishedMinutes.value = durationMin.value
  remaining.value = 0
  beep()
  if (!tasksStore.tasks.length) tasksStore.fetchTasks()
  showCompleteDialog.value = true
}

async function submitSession() {
  submitting.value = true
  submitError.value = ''
  try {
    await api.createSession({
      task_id: selectedTaskId.value,
      duration_minutes: finishedMinutes.value,
    })
    closeDialog()
  } catch (e) {
    submitError.value = `记录失败：${e.message}`
  } finally {
    submitting.value = false
  }
}

function closeDialog() {
  showCompleteDialog.value = false
  selectedTaskId.value = null
  submitError.value = ''
  remaining.value = durationMin.value * 60
}

function beep() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    const ctx = new AudioCtx()
    const oscillator = ctx.createOscillator()
    const gain = ctx.createGain()
    oscillator.connect(gain)
    gain.connect(ctx.destination)
    oscillator.frequency.value = 880
    gain.gain.setValueAtTime(0.2, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6)
    oscillator.start()
    oscillator.stop(ctx.currentTime + 0.6)
  } catch {
    /* 浏览器不支持音频时静默 */
  }
}

onBeforeUnmount(() => {
  if (timerId !== null) clearInterval(timerId)
})

onMounted(async () => {
  await settings.fetch()
  if (!running.value) {
    const def = settings.pomodoroDefault
    durationMin.value = def
    remaining.value = def * 60
  }
})
</script>
