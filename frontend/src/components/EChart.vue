<template>
  <div ref="chartEl" class="echart" :style="{ height }"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '320px' },
})

const chartEl = ref(null)
let chart = null
let resizeObserver = null

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(props.option, true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  if (typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(chartEl.value)
  } else {
    window.addEventListener('resize', resize)
  }
})

watch(() => props.option, render, { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = null
})
</script>
