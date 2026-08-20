<template>
  <div class="page">
    <h1>计划管理</h1>
    <p class="date-line">大计划 → 子计划 → 任务，逐层拆解，配合流程图查看整体结构。</p>

    <div class="filter-tabs page-tabs">
      <button class="chip" :class="{ active: activeTab === 'tree' }" @click="activeTab = 'tree'">
        计划树
      </button>
      <button class="chip" :class="{ active: activeTab === 'flow' }" @click="activeTab = 'flow'">
        流程图
      </button>
    </div>

    <p v-if="plansStore.error" class="banner error">{{ plansStore.error }}</p>
    <p v-if="bannerError" class="banner error">{{ bannerError }}</p>

    <!-- 计划树 -->
    <template v-if="activeTab === 'tree'">
      <section class="panel">
        <h2>新建根计划</h2>
        <form class="plan-form" @submit.prevent="addRootPlan">
          <input
            v-model="rootTitle"
            class="input grow"
            placeholder="计划标题（必填，1-100 字）"
            maxlength="100"
            required
          />
          <input
            v-model="rootDescription"
            class="input grow"
            placeholder="一句话描述（可选）"
            maxlength="500"
          />
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '创建中…' : '创建计划' }}
          </button>
        </form>
        <p v-if="rootError" class="error-text">{{ rootError }}</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>我的计划</h2>
          <button class="btn small" @click="expandAll">全部展开</button>
        </div>
        <p v-if="plansStore.loading">加载中…</p>
        <p v-else-if="!plansStore.roots.length" class="muted">
          还没有计划，先在顶部创建一个吧。
        </p>
        <PlanNode
          v-for="plan in plansStore.roots"
          :key="plan.id"
          :plan="plan"
          :expanded="expandedIds.has(plan.id)"
          :expanded-ids="expandedIds"
          :highlighted-id="highlightedId"
          @toggle="toggleNode"
          @add-child="openAddChild"
          @edit="openEdit"
          @add-task="openAddTask"
          @breakdown="openBreakdown"
          @delete="removePlan"
          @set-status="setStatus"
        />
      </section>
    </template>

    <!-- 流程图 -->
    <template v-else>
      <section class="panel">
        <div class="panel-head">
          <h2>计划流程图</h2>
          <div class="flow-actions">
            <button class="btn small" :disabled="!plansStore.plans.length" @click="flowRef?.exportSvg()">
              导出 SVG
            </button>
            <button class="btn small primary" :disabled="!plansStore.plans.length" @click="flowRef?.exportPng()">
              导出 PNG
            </button>
          </div>
        </div>
        <PlanFlowChart
          ref="flowRef"
          :plans="plansStore.plans"
          @select="highlightNode"
          @locate="locatePlan"
        />
      </section>
    </template>

    <!-- 计划弹层（新建/编辑） -->
    <div v-if="planModal.open" class="modal-backdrop" @click.self="planModal.open = false">
      <div class="modal">
        <h2>{{ planModal.mode === 'edit' ? '编辑计划' : '添加子计划' }}</h2>
        <p v-if="planModal.parentName" class="muted">上级：{{ planModal.parentName }}</p>
        <input v-model="planModal.title" class="input" placeholder="计划标题（必填）" maxlength="100" />
        <textarea
          v-model="planModal.description"
          class="input textarea"
          placeholder="描述（可选，≤500 字）"
          maxlength="500"
          rows="3"
        ></textarea>
        <p v-if="planModal.error" class="error-text">{{ planModal.error }}</p>
        <div class="modal-actions">
          <button class="btn" @click="planModal.open = false">取消</button>
          <button class="btn primary" :disabled="planModal.submitting" @click="savePlan">
            {{ planModal.submitting ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 任务弹层 -->
    <div v-if="taskModal.open" class="modal-backdrop" @click.self="taskModal.open = false">
      <div class="modal">
        <h2>为「{{ taskModal.plan?.title }}」添加任务</h2>
        <input v-model="taskModal.title" class="input" placeholder="任务标题（必填）" maxlength="200" />
        <input v-model="taskModal.subject" class="input" placeholder="科目（可选）" maxlength="50" />
        <input
          v-model.number="taskModal.estimated_minutes"
          class="input"
          type="number"
          min="1"
          max="600"
          placeholder="预计分钟"
        />
        <p v-if="taskModal.error" class="error-text">{{ taskModal.error }}</p>
        <div class="modal-actions">
          <button class="btn" @click="taskModal.open = false">取消</button>
          <button class="btn primary" :disabled="taskModal.submitting" @click="saveTask">
            {{ taskModal.submitting ? '保存中…' : '添加任务' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 拆解弹层 -->
    <div v-if="breakdownModal.open" class="modal-backdrop" @click.self="breakdownModal.open = false">
      <div class="modal">
        <h2>拆解「{{ breakdownModal.plan?.title }}」</h2>
        <p class="muted">把大计划拆成若干子计划，可继续逐层拆解。</p>

        <div class="breakdown-modes">
          <button
            class="chip"
            :class="{ active: breakdownModal.mode === 'template' }"
            @click="breakdownModal.mode = 'template'; breakdownModal.useMine = false"
          >
            内置 / 我的模板
          </button>
          <button
            v-if="settings.planTemplates.length"
            class="chip"
            :class="{ active: breakdownModal.mode === 'template' && breakdownModal.useMine }"
            @click="breakdownModal.mode = 'template'; breakdownModal.useMine = true"
          >
            📁 我的模板
          </button>
          <button
            class="chip"
            :class="{ active: breakdownModal.mode === 'ai' }"
            @click="breakdownModal.mode = 'ai'"
          >
            AI 拆解
          </button>
        </div>

        <div v-if="breakdownModal.mode === 'template' && !breakdownModal.useMine" class="field">
          <label>选择模板</label>
          <select v-model="breakdownModal.templateKey" class="input">
            <option value="study">学习计划</option>
            <option value="project">项目计划</option>
            <option value="exam">备考计划</option>
          </select>
        </div>

        <div v-else-if="breakdownModal.mode === 'template' && breakdownModal.useMine" class="field">
          <label>选择我的模板</label>
          <select v-model="breakdownModal.templateId" class="input">
            <option v-for="tpl in settings.planTemplates" :key="tpl.id" :value="tpl.id">
              {{ tpl.name }}（{{ tpl.children.length }} 项）
            </option>
          </select>
          <p class="muted small-note">也可到 <router-link to="/settings">设置 → 个性化</router-link> 管理模板。</p>
        </div>

        <div v-else class="ai-hint">
          <p v-if="aiStore.hasConfig" class="muted">
            将使用你的 AI 配置（<code>{{ aiStore.config.model }}</code>）进行拆解。
          </p>
          <template v-else>
            <p class="muted">
              当前账号尚未配置 AI 服务。可在 <router-link to="/ai-settings">AI 设置</router-link>
              中填写自己的 API；若服务器已配置 <code>LLM_API_KEY</code> 环境变量，也可直接使用。
            </p>
            <router-link class="btn small primary" to="/ai-settings">前往 AI 设置</router-link>
          </template>
        </div>

        <p v-if="breakdownModal.error" class="error-text">{{ breakdownModal.error }}</p>
        <div class="modal-actions">
          <button class="btn" @click="breakdownModal.open = false">取消</button>
          <button class="btn primary" :disabled="breakdownModal.submitting" @click="runBreakdown">
            {{ breakdownModal.submitting ? '拆解中…' : '开始拆解' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import PlanNode from '../components/PlanNode.vue'
import PlanFlowChart from '../components/PlanFlowChart.vue'
import { useAiStore } from '../stores/ai'
import { usePlansStore } from '../stores/plans'
import { useTasksStore } from '../stores/tasks'
import { useSettingsStore } from '../stores/settings'

const aiStore = useAiStore()
const settings = useSettingsStore()
const plansStore = usePlansStore()
const tasksStore = useTasksStore()

const activeTab = ref('tree')
const flowRef = ref(null)
const bannerError = ref('')

const rootTitle = ref('')
const rootDescription = ref('')
const rootError = ref('')
const submitting = ref(false)

const expandedIds = ref(new Set())
const highlightedId = ref(null)

const planModal = ref({
  open: false,
  mode: 'create',
  parentId: null,
  parentName: '',
  plan: null,
  title: '',
  description: '',
  error: '',
  submitting: false,
})

const taskModal = ref({
  open: false,
  plan: null,
  title: '',
  subject: '',
  estimated_minutes: 25,
  error: '',
  submitting: false,
})

const breakdownModal = ref({
  open: false,
  plan: null,
  mode: 'template',
  templateKey: 'study',
  useMine: false,
  templateId: null,
  error: '',
  submitting: false,
})

function syncExpanded() {
  const next = new Set(expandedIds.value)
  for (const plan of plansStore.plans) next.add(plan.id)
  expandedIds.value = next
}

function toggleNode(id) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

function expandAll() {
  expandedIds.value = new Set(plansStore.plans.map((plan) => plan.id))
}

async function addRootPlan() {
  const title = rootTitle.value.trim()
  if (!title) return
  submitting.value = true
  rootError.value = ''
  try {
    const plan = await plansStore.addPlan({
      title,
      description: rootDescription.value.trim(),
    })
    expandedIds.value = new Set([...expandedIds.value, plan.id])
    rootTitle.value = ''
    rootDescription.value = ''
  } catch (e) {
    rootError.value = e.message
  } finally {
    submitting.value = false
  }
}

function openAddChild(plan) {
  planModal.value = {
    open: true,
    mode: 'create',
    parentId: plan.id,
    parentName: plan.title,
    plan: null,
    title: '',
    description: '',
    error: '',
    submitting: false,
  }
}

function openEdit(plan) {
  planModal.value = {
    open: true,
    mode: 'edit',
    parentId: null,
    parentName: '',
    plan,
    title: plan.title,
    description: plan.description,
    error: '',
    submitting: false,
  }
}

async function savePlan() {
  const title = planModal.value.title.trim()
  if (!title) {
    planModal.value.error = '标题不能为空'
    return
  }
  planModal.value.submitting = true
  planModal.value.error = ''
  try {
    if (planModal.value.mode === 'edit') {
      const plan = await plansStore.updatePlan(planModal.value.plan.id, {
        title,
        description: planModal.value.description.trim(),
      })
      expandedIds.value = new Set([...expandedIds.value, plan.id])
    } else {
      const plan = await plansStore.addPlan({
        title,
        description: planModal.value.description.trim(),
        parent_id: planModal.value.parentId,
      })
      expandedIds.value = new Set([...expandedIds.value, plan.id])
    }
    planModal.value.open = false
  } catch (e) {
    planModal.value.error = e.message
  } finally {
    planModal.value.submitting = false
  }
}

async function setStatus(plan, status) {
  try {
    await plansStore.updatePlan(plan.id, { status })
  } catch (e) {
    bannerError.value = e.message
  }
}

async function removePlan(plan) {
  if (!window.confirm(`确定删除「${plan.title}」及其全部子计划？`)) return
  try {
    await plansStore.removePlan(plan.id)
  } catch (e) {
    bannerError.value = e.message
  }
}

function openAddTask(plan) {
  taskModal.value = {
    open: true,
    plan,
    title: '',
    subject: '',
    estimated_minutes: 25,
    error: '',
    submitting: false,
  }
}

async function saveTask() {
  const title = taskModal.value.title.trim()
  if (!title) {
    taskModal.value.error = '任务标题不能为空'
    return
  }
  taskModal.value.submitting = true
  taskModal.value.error = ''
  try {
    await tasksStore.addTask({
      title,
      subject: taskModal.value.subject.trim(),
      estimated_minutes: taskModal.value.estimated_minutes || 25,
      plan_id: taskModal.value.plan.id,
    })
    taskModal.value.open = false
  } catch (e) {
    taskModal.value.error = e.message
  } finally {
    taskModal.value.submitting = false
  }
}

  function openBreakdown(plan) {
  breakdownModal.value = {
    open: true,
    plan,
    mode: 'template',
    templateKey: 'study',
    useMine: false,
    templateId: settings.planTemplates[0]?.id ?? null,
    error: '',
    submitting: false,
  }
}

async function runBreakdown() {
  const plan = breakdownModal.value.plan
  const mode = breakdownModal.value.mode
  const templateKey = mode === 'template' ? breakdownModal.value.templateKey : undefined
  const templateId = mode === 'template' && breakdownModal.value.useMine ? breakdownModal.value.templateId : undefined
  breakdownModal.value.submitting = true
  breakdownModal.value.error = ''
  try {
    const created = await plansStore.breakdownPlan(plan.id, mode, templateKey, templateId)
    expandedIds.value = new Set([
      ...expandedIds.value,
      plan.id,
      ...created.map((item) => item.id),
    ])
    breakdownModal.value.open = false
  } catch (e) {
    breakdownModal.value.error = e.message
  } finally {
    breakdownModal.value.submitting = false
  }
}

function highlightNode(plan) {
  highlightedId.value = plan.id
  setTimeout(() => {
    if (highlightedId.value === plan.id) highlightedId.value = null
  }, 2000)
}

async function locatePlan(planId) {
  activeTab.value = 'tree'
  const chain = []
  let current = plansStore.planById(planId)
  while (current) {
    chain.unshift(current.id)
    current = current.parent_id != null ? plansStore.planById(current.parent_id) : null
  }
  const next = new Set(expandedIds.value)
  for (const id of chain) next.add(id)
  expandedIds.value = next

  highlightedId.value = planId
  await nextTick()
  const el = document.getElementById(`plan-node-${planId}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  setTimeout(() => {
    if (highlightedId.value === planId) highlightedId.value = null
  }, 2500)
}

onMounted(async () => {
  aiStore.fetchConfig()
  await settings.fetch()
  await settings.fetchPlanTemplates()
  await plansStore.fetchPlans()
  syncExpanded()
  if (!tasksStore.tasks.length) tasksStore.fetchTasks()
})
</script>
