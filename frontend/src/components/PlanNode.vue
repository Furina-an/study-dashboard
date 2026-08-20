<template>
  <div class="plan-node" :style="{ marginLeft: depth * 22 + 'px' }">
    <div class="plan-row" :id="`plan-node-${plan.id}`" :class="{ highlighted: highlighted }">
      <button
        class="plan-toggle"
        :disabled="!children.length"
        :title="children.length ? (expanded ? '收起' : '展开') : '无子计划'"
        @click="$emit('toggle', plan.id)"
      >
        {{ children.length ? (expanded ? '▾' : '▸') : '•' }}
      </button>

      <div class="plan-info" @click="children.length && $emit('toggle', plan.id)">
        <div class="plan-title-row">
          <span class="plan-title">{{ plan.title }}</span>
          <select
            class="plan-status-select"
            :class="plan.status"
            :value="plan.status"
            @change="$emit('set-status', plan, $event.target.value)"
          >
            <option value="todo">待办</option>
            <option value="doing">进行中</option>
            <option value="done">已完成</option>
          </select>
        </div>
        <p v-if="plan.description" class="plan-desc">{{ plan.description }}</p>
      </div>

      <div class="plan-actions">
        <button class="btn small" title="添加子计划" @click="$emit('add-child', plan)">+子计划</button>
        <button class="btn small" title="一键拆解" @click="$emit('breakdown', plan)">拆解</button>
        <button class="btn small" title="添加任务" @click="$emit('add-task', plan)">+任务</button>
        <button class="btn small" title="编辑" @click="$emit('edit', plan)">编辑</button>
        <button class="btn small danger" title="删除（级联删除子计划）" @click="$emit('delete', plan)">删除</button>
      </div>
    </div>

    <div v-if="expanded && children.length" class="plan-children">
      <PlanNode
        v-for="child in children"
        :key="child.id"
        :plan="child"
        :depth="depth + 1"
        :expanded="expandedIds.has(child.id)"
        :highlighted="highlightedId === child.id"
        @toggle="$emit('toggle', $event)"
        @add-child="$emit('add-child', $event)"
        @breakdown="$emit('breakdown', $event)"
        @add-task="$emit('add-task', $event)"
        @edit="$emit('edit', $event)"
        @delete="$emit('delete', $event)"
        @set-status="(plan, status) => $emit('set-status', plan, status)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePlansStore } from '../stores/plans'

defineOptions({ name: 'PlanNode' })

const props = defineProps({
  plan: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  expanded: { type: Boolean, default: true },
  expandedIds: { type: Set, default: () => new Set() },
  highlighted: { type: Boolean, default: false },
  highlightedId: { type: Number, default: null },
})

defineEmits(['toggle', 'add-child', 'breakdown', 'add-task', 'edit', 'delete', 'set-status'])

const plansStore = usePlansStore()
const children = computed(() => plansStore.childrenMap[props.plan.id] || [])
</script>