<template>
  <div class="timer-circle" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" viewBox="0 0 100 100">
      <defs>
        <linearGradient id="timerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#6366f1" />
          <stop offset="100%" stop-color="#4f46e5" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="45" class="timer-circle-bg" />
      <circle
        cx="50"
        cy="50"
        r="45"
        class="timer-circle-fg"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
      />
    </svg>
    <div class="timer-circle-time">{{ display }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  total: { type: Number, required: true },
  remaining: { type: Number, required: true },
  size: { type: Number, default: 260 },
})

const circumference = 2 * Math.PI * 45

const dashOffset = computed(() => {
  if (props.total <= 0) return 0
  const ratio = Math.max(0, Math.min(1, props.remaining / props.total))
  return circumference * (1 - ratio)
})

const display = computed(() => {
  const minutes = Math.floor(props.remaining / 60)
  const seconds = props.remaining % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
</script>
