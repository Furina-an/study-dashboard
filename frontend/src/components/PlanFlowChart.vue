<template>
  <div>
    <div v-if="!nodes.length" class="muted">暂无计划，请先在「计划树」中创建计划。</div>
    <template v-else>
      <div class="flow-toolbar panel">
        <div class="toolbar-row">
          <label class="ctl">
            布局
            <select v-model="layoutMode" class="input narrow" @change="onLayoutChange">
              <option value="vertical">纵向树</option>
              <option value="horizontal">横向树</option>
              <option value="radial">径向图</option>
            </select>
          </label>
          <label class="ctl ctl-range">
            节点宽
            <input v-model.number="settings.nodeW" type="range" min="140" max="320" step="10" />
            <span class="ctl-val">{{ settings.nodeW }}</span>
          </label>
          <label class="ctl ctl-range">
            节点高
            <input v-model.number="settings.nodeH" type="range" min="52" max="140" step="4" />
            <span class="ctl-val">{{ settings.nodeH }}</span>
          </label>
          <label class="ctl ctl-check">
            <input v-model="showStatus" type="checkbox" /> 显示状态
          </label>
          <label class="ctl ctl-check">
            <input v-model="editMode" type="checkbox" /> 自由编辑
          </label>
          <button class="btn small" @click="resetOverrides">重置布局</button>
        </div>
        <div class="toolbar-row">
          <span class="theme-label">主题：</span>
          <button
            v-for="(th, key) in themes"
            :key="key"
            class="theme-swatch"
            :class="{ active: themeKey === key }"
            :style="{ background: th.bg, borderColor: th.stroke }"
            :title="th.label"
            @click="applyTheme(key)"
          >
            {{ th.label }}
          </button>
          <label class="ctl ctl-color">填充 <input type="color" v-model="settings.fill" /></label>
          <label class="ctl ctl-color">边框 <input type="color" v-model="settings.stroke" /></label>
          <label class="ctl ctl-color">文字 <input type="color" v-model="settings.textColor" /></label>
          <label class="ctl ctl-color">连线 <input type="color" v-model="settings.lineColor" /></label>
          <label class="ctl ctl-color">背景 <input type="color" v-model="settings.bg" /></label>
        </div>
      </div>

      <div class="flow-wrap" :class="{ editing: editMode }">
        <svg
          ref="svgEl"
          class="flow-svg"
          :viewBox="viewBox"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <marker id="flow-arrow-v2" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" :fill="settings.lineColor" />
            </marker>
          </defs>

          <rect :x="bounds.x" :y="bounds.y" :width="bounds.w" :height="bounds.h" :fill="settings.bg" />

          <g class="flow-connectors">
            <polyline
              v-for="(conn, i) in connectors"
              :key="i"
              class="flow-line"
              :points="conn.points"
              :stroke="settings.lineColor"
              marker-end="url(#flow-arrow-v2)"
            />
          </g>

          <g class="flow-nodes">
            <g
              v-for="node in finalNodes"
              :key="node.plan.id"
              class="flow-node"
              :class="{ selected: node.plan.id === selectedId, draggable: editMode }"
              :transform="`translate(${node.x - node.w / 2}, ${node.y - node.h / 2})`"
              @pointerdown="onNodePointerDown($event, node)"
            >
              <rect
                class="flow-node-bg"
                :width="node.w"
                :height="node.h"
                rx="10"
                :fill="node.fill"
                :stroke="node.stroke"
                :stroke-width="node.plan.id === selectedId ? 2.6 : 1.4"
              />
              <text
                v-for="(line, i) in node.lines"
                :key="i"
                class="flow-title"
                :x="node.w / 2"
                :y="titleLineY(node.h, i, node.lines.length)"
                :fill="node.textColor"
              >
                {{ line }}
              </text>
              <text v-if="showStatus" class="flow-status" :x="node.w / 2" :y="node.h - 10" :fill="statusColor(node.plan.status)">
                {{ statusLabel(node.plan.status) }}
              </text>
            </g>
          </g>
        </svg>
      </div>
      <p v-if="editMode" class="muted flow-tip">
        自由编辑：拖动节点调整位置，点击节点后在下方面板微调该节点的宽高与颜色。
      </p>

      <div v-if="selectedOverride && selectedNode" class="flow-detail panel">
        <div class="panel-head">
          <h2>节点：{{ selectedNode.title }}</h2>
          <button class="btn small" @click="$emit('locate', selectedNode.id)">在计划树中定位</button>
        </div>
        <div class="toolbar-row">
          <label class="ctl ctl-range">
            宽
            <input v-model.number="selectedOverride.width" type="range" min="140" max="320" step="10" />
            <span class="ctl-val">{{ selectedOverride.width || settings.nodeW }}</span>
          </label>
          <label class="ctl ctl-range">
            高
            <input v-model.number="selectedOverride.height" type="range" min="52" max="140" step="4" />
            <span class="ctl-val">{{ selectedOverride.height || settings.nodeH }}</span>
          </label>
          <label class="ctl ctl-color">填充 <input type="color" v-model="selectedOverride.fill" /></label>
          <label class="ctl ctl-color">边框 <input type="color" v-model="selectedOverride.stroke" /></label>
          <label class="ctl ctl-color">文字 <input type="color" v-model="selectedOverride.textColor" /></label>
          <button class="btn small" @click="resetNodeOverride">重置该节点</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { usePlansStore } from '../stores/plans'
import { useThemeStore } from '../stores/theme'

defineProps({
  plans: { type: Array, default: () => [] },
})

const emit = defineEmits(['select', 'locate'])

const GAP_X = 28
const GAP_Y = 52
const PAD = 40

const plansStore = usePlansStore()
const theme = useThemeStore()
const svgEl = ref(null)

const layoutMode = ref('vertical')
const themeKey = ref('default')
const showStatus = ref(true)
const editMode = ref(false)

const selectedId = ref(null)
const selectedPlan = ref(null)

const overrides = reactive({})

const themes = {
  default: { label: '默认', fill: '#ffffff', stroke: '#e3e7f0', textColor: '#1f2430', lineColor: '#93a0c0', bg: '#ffffff' },
  blue: { label: '蓝调', fill: '#eef2ff', stroke: '#4f6ef7', textColor: '#1f2430', lineColor: '#4f6ef7', bg: '#ffffff' },
  warm: { label: '暖橙', fill: '#fff7ed', stroke: '#f59e0b', textColor: '#7c2d12', lineColor: '#f59e0b', bg: '#fffdf8' },
  dark: { label: '深色', fill: '#232936', stroke: '#4f6ef7', textColor: '#eef2ff', lineColor: '#6b7a99', bg: '#14161f' },
  morandi: { label: '莫兰迪', fill: '#f3f0ec', stroke: '#a5b4a0', textColor: '#3f4a3c', lineColor: '#9aa79b', bg: '#faf9f6' },
}

const settings = reactive({
  nodeW: 200,
  nodeH: 64,
  ...themes.default,
})

function applyTheme(key) {
  themeKey.value = key
  Object.assign(settings, themes[key])
}

// 应用深色模式时，未手动选过主题则自动跟随「深色」预设
watch(
  () => theme.dark,
  (dark) => {
    if (themeKey.value === 'default') applyTheme(dark ? 'dark' : 'default')
  },
  { immediate: true },
)

function ensureOverride(id) {
  if (!overrides[id]) overrides[id] = {}
  return overrides[id]
}

function resetOverrides() {
  for (const key of Object.keys(overrides)) delete overrides[key]
  selectedId.value = null
  selectedPlan.value = null
}

function onLayoutChange() {
  for (const key of Object.keys(overrides)) {
    const item = overrides[key]
    delete item.x
    delete item.y
  }
}

function resetNodeOverride() {
  if (selectedId.value != null) delete overrides[selectedId.value]
}

const selectedNode = computed(() => {
  const id = selectedId.value
  if (id == null) return null
  const plan = plansStore.planById(id)
  return plan ? { ...plan } : null
})

const selectedOverride = computed(() => {
  const id = selectedId.value
  if (id == null) return null
  return ensureOverride(id)
})

const roots = computed(() => plansStore.roots)

function childrenOf(plan) {
  return plansStore.childrenMap[plan.id] || []
}

/* ---------- 布局算法 ---------- */

function computeGrid() {
  const pos = new Map()
  let leafCursor = 0
  function walk(plan, level) {
    const kids = childrenOf(plan)
    let col
    if (kids.length) {
      const cols = kids.map((kid) => walk(kid, level + 1))
      col = (Math.min(...cols) + Math.max(...cols)) / 2
    } else {
      col = leafCursor
      leafCursor += 1
    }
    pos.set(plan.id, { level, col })
    return col
  }
  for (const root of roots.value) walk(root, 0)
  return pos
}

function computeRadial() {
  const pos = new Map()
  const leaves = new Map()
  function countLeaves(plan) {
    const kids = childrenOf(plan)
    const total = kids.length ? kids.reduce((sum, kid) => sum + countLeaves(kid), 0) : 1
    leaves.set(plan.id, total)
    return total
  }
  const totalLeaves = roots.value.reduce((sum, root) => sum + countLeaves(root), 0)
  const RADIUS_STEP = 150
  function place(plan, level, angleStart, angleEnd) {
    const angle = (angleStart + angleEnd) / 2
    const radius = level * RADIUS_STEP
    pos.set(plan.id, {
      x: radius * Math.cos(angle),
      y: radius * Math.sin(angle),
    })
    const kids = childrenOf(plan)
    const total = leaves.get(plan.id)
    let cursor = angleStart
    for (const kid of kids) {
      const span = ((angleEnd - angleStart) * leaves.get(kid.id)) / total
      place(kid, level + 1, cursor, cursor + span)
      cursor += span
    }
  }
  let cursor = -Math.PI / 2
  for (const root of roots.value) {
    const span = ((2 * Math.PI) * leaves.get(root.id)) / totalLeaves
    place(root, 1, cursor, cursor + span)
    cursor += span
  }
  return pos
}

function nodePosition(planId) {
  if (layoutMode.value === 'radial') return computeRadial().get(planId)
  const grid = computeGrid().get(planId)
  if (!grid) return { x: 0, y: 0 }
  if (layoutMode.value === 'horizontal') {
    return {
      x: PAD + grid.level * (settings.nodeW + GAP_X) + settings.nodeW / 2,
      y: PAD + grid.col * (settings.nodeH + GAP_Y) + settings.nodeH / 2,
    }
  }
  return {
    x: PAD + grid.col * (settings.nodeW + GAP_X) + settings.nodeW / 2,
    y: PAD + grid.level * (settings.nodeH + GAP_Y) + settings.nodeH / 2,
  }
}

const autoNodes = computed(() => {
  const seen = new Set()
  const result = []
  function walk(plan) {
    if (seen.has(plan.id)) return
    seen.add(plan.id)
    const position = nodePosition(plan.id)
    result.push({ plan, x: position.x, y: position.y })
    for (const kid of childrenOf(plan)) walk(kid)
  }
  for (const root of roots.value) walk(root)
  return result
})

const finalNodes = computed(() =>
  autoNodes.value.map((node) => {
    const ov = overrides[node.plan.id]
    const w = ov?.width || settings.nodeW
    const h = ov?.height || settings.nodeH
    return {
      ...node,
      w,
      h,
      x: ov?.x != null ? ov.x : node.x,
      y: ov?.y != null ? ov.y : node.y,
      fill: ov?.fill || settings.fill,
      stroke: ov?.stroke || settings.stroke,
      textColor: ov?.textColor || settings.textColor,
      lines: wrapTitle(node.plan.title, w, h),
    }
  }),
)

const nodes = computed(() => autoNodes.value)

const connectors = computed(() => {
  const byId = new Map(finalNodes.value.map((node) => [node.plan.id, node]))
  const list = []
  for (const node of finalNodes.value) {
    for (const kid of childrenOf(node.plan)) {
      const child = byId.get(kid.id)
      if (!child) continue
      if (layoutMode.value === 'radial') {
        list.push({ points: `${node.x},${node.y} ${child.x},${child.y}` })
      } else if (layoutMode.value === 'horizontal') {
        const midY = (node.y + child.y) / 2
        list.push({
          points: `${node.x + node.w / 2},${node.y} ${node.x + node.w / 2},${midY} ${child.x - child.w / 2},${midY} ${child.x - child.w / 2},${child.y}`,
        })
      } else {
        const midX = (node.x + child.x) / 2
        list.push({
          points: `${node.x},${node.y + node.h / 2} ${node.x},${midX} ${child.x},${midX} ${child.x},${child.y - child.h / 2}`,
        })
      }
    }
  }
  return list
})

const bounds = computed(() => {
  if (!finalNodes.value.length) return { x: 0, y: 0, w: 600, h: 200 }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const node of finalNodes.value) {
    minX = Math.min(minX, node.x - node.w / 2)
    maxX = Math.max(maxX, node.x + node.w / 2)
    minY = Math.min(minY, node.y - node.h / 2)
    maxY = Math.max(maxY, node.y + node.h / 2)
  }
  return {
    x: minX - PAD,
    y: minY - PAD,
    w: maxX - minX + PAD * 2,
    h: maxY - minY + PAD * 2,
  }
})

const viewBox = computed(() => `${bounds.value.x} ${bounds.value.y} ${bounds.value.w} ${bounds.value.h}`)

/* ---------- 文本与状态 ---------- */

const TITLE_FONT = "600 13px -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif"
const TITLE_LINE_H = 16
const TITLE_PAD_X = 10
const TITLE_TOP = 16
const STATUS_ZONE_H = 26

let measureCtx = null

function textWidth(text) {
  if (!measureCtx) measureCtx = document.createElement('canvas').getContext('2d')
  measureCtx.font = TITLE_FONT
  return measureCtx.measureText(text).width
}

function wrapTitle(title, nodeW, nodeH) {
  const maxWidth = Math.max(48, nodeW - TITLE_PAD_X * 2)
  const statusH = showStatus.value ? STATUS_ZONE_H : 0
  const maxLines = Math.max(1, Math.floor((nodeH - TITLE_TOP - statusH) / TITLE_LINE_H))
  const chars = Array.from(String(title))
  const lines = []
  let current = ''
  for (const ch of chars) {
    if (current && textWidth(current + ch) > maxWidth) {
      lines.push(current)
      current = ch
      if (lines.length >= maxLines) break
    } else {
      current += ch
    }
  }
  if (current && lines.length < maxLines) lines.push(current)
  if (lines.length && lines.join('').length < chars.length) {
    const last = lines.pop() || ''
    let ellipsized = last
    while (ellipsized.length > 1 && textWidth(ellipsized + '…') > maxWidth) {
      ellipsized = ellipsized.slice(0, -1)
    }
    lines.push(ellipsized + '…')
  }
  return lines
}

function titleLineY(nodeH, lineIndex, lineCount) {
  const statusH = showStatus.value ? STATUS_ZONE_H : 0
  const areaH = Math.max(0, nodeH - TITLE_TOP - statusH)
  const blockH = lineCount * TITLE_LINE_H
  const top = TITLE_TOP + Math.max(0, (areaH - blockH) / 2)
  return top + lineIndex * TITLE_LINE_H + 13
}

function statusLabel(status) {
  return { todo: '待办', doing: '进行中', done: '已完成' }[status] || status
}

function statusColor(status) {
  return { todo: '#9aa3b2', doing: '#4f6ef7', done: '#22a06b' }[status] || '#9aa3b2'
}


/* ---------- 交互：选择与拖动 ---------- */

let dragState = null

function onNodePointerDown(event, node) {
  event.preventDefault()
  selectedId.value = node.plan.id
  selectedPlan.value = node.plan
  emit('select', node.plan)
  if (!editMode.value) return

  const rect = svgEl.value.getBoundingClientRect()
  const scaleX = bounds.value.w / rect.width
  const scaleY = bounds.value.h / rect.height
  const offsetX = (event.clientX - rect.left) * scaleX + bounds.value.x
  const offsetY = (event.clientY - rect.top) * scaleY + bounds.value.y
  const ov = ensureOverride(node.plan.id)
  dragState = {
    id: node.plan.id,
    offsetX,
    offsetY,
    originX: ov.x != null ? ov.x : node.x,
    originY: ov.y != null ? ov.y : node.y,
  }
  window.addEventListener('pointermove', onWindowPointerMove)
  window.addEventListener('pointerup', onWindowPointerUp)
}

function onWindowPointerMove(event) {
  if (!dragState) return
  const rect = svgEl.value.getBoundingClientRect()
  const scaleX = bounds.value.w / rect.width
  const scaleY = bounds.value.h / rect.height
  const x = (event.clientX - rect.left) * scaleX + bounds.value.x
  const y = (event.clientY - rect.top) * scaleY + bounds.value.y
  const ov = ensureOverride(dragState.id)
  ov.x = dragState.originX + (x - dragState.offsetX)
  ov.y = dragState.originY + (y - dragState.offsetY)
}

function onWindowPointerUp() {
  dragState = null
  window.removeEventListener('pointermove', onWindowPointerMove)
  window.removeEventListener('pointerup', onWindowPointerUp)
}

/* ---------- 导出 ---------- */

function currentSvgString() {
  const svg = svgEl.value
  if (!svg) return ''
  const clone = svg.cloneNode(true)
  clone.removeAttribute('class')
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink')
  clone.setAttribute('width', bounds.value.w)
  clone.setAttribute('height', bounds.value.h)
  clone.setAttribute('viewBox', viewBox.value)
  return new XMLSerializer().serializeToString(clone)
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function exportSvg() {
  const svg = currentSvgString()
  if (!svg) return
  downloadBlob(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }), 'plan-flow.svg')
}

function exportPng() {
  const svg = currentSvgString()
  if (!svg) return
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const image = new Image()
  image.onload = () => {
    const scale = 2
    const canvas = document.createElement('canvas')
    canvas.width = bounds.value.w * scale
    canvas.height = bounds.value.h * scale
    const ctx = canvas.getContext('2d')
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height)
    URL.revokeObjectURL(url)
    canvas.toBlob((pngBlob) => {
      if (pngBlob) downloadBlob(pngBlob, 'plan-flow.png')
    }, 'image/png')
  }
  image.onerror = () => URL.revokeObjectURL(url)
  image.src = url
}

defineExpose({ exportSvg, exportPng })
</script>
