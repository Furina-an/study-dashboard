<template>
  <div class="bar-chart">
    <svg :viewBox="`0 0 ${width} ${height}`" class="bar-chart-svg" role="img" aria-label="专注趋势柱状图">
      <line
        v-for="bar in bars"
        :key="'grid-' + bar.date"
        :x1="bar.x"
        :x2="bar.x"
        y1="4"
        :y2="height - labelSpace + 2"
        class="grid-line"
      />
      <rect
        v-for="bar in bars"
        :key="bar.date"
        :x="bar.x - barWidth / 2"
        :y="height - labelSpace - bar.h"
        :width="barWidth"
        :height="bar.h"
        rx="3"
        class="bar"
      />
      <text
        v-for="bar in bars"
        :key="'value-' + bar.date"
        :x="bar.x"
        :y="height - labelSpace - bar.h - 6"
        text-anchor="middle"
        class="bar-value"
      >{{ bar.value > 0 ? bar.value : '' }}</text>
      <text
        v-for="bar in bars"
        :key="'label-' + bar.date"
        :x="bar.x"
        :y="height - 8"
        text-anchor="middle"
        class="bar-label"
      >{{ bar.label }}</text>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  height: { type: Number, default: 220 },
  labelSpace: { type: Number, default: 26 },
})

const width = 560
const barWidth = 30
const maxValue = computed(() =>
  Math.max(1, ...props.data.map((d) => d.focus_minutes)),
)

const bars = computed(() => {
  const count = props.data.length
  const usableHeight = props.height - props.labelSpace - 18
  const slot = count > 0 ? width / count : 0
  return props.data.map((point, index) => ({
    date: point.date,
    label: point.date.slice(5),
    value: point.focus_minutes,
    x: slot * index + slot / 2,
    h: (point.focus_minutes / maxValue.value) * usableHeight,
  }))
})
</script>