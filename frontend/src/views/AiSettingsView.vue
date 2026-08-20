<template>
  <div class="page ai-page">
    <div class="page-head">
      <h1>🤖 AI 服务设置</h1>
      <span class="muted">为「计划 AI 拆解」接入 OpenAI 兼容接口</span>
    </div>

    <div v-if="store.hasConfig" class="banner info ai-status">
      ✅ 已配置 <b>{{ providerLabel }}</b> · 模型 <code>{{ form.model }}</code> ·
      Key <code>{{ store.config.api_key_masked }}</code>
    </div>

    <section class="panel">
      <h2>① 选择服务商</h2>
      <p class="muted">点击卡片自动填充接口地址与默认模型；也可以选「自定义」手动填写。</p>
      <div class="provider-grid">
        <button
          v-for="p in providers"
          :key="p.key"
          type="button"
          class="provider-card"
          :class="{ active: form.provider === p.key }"
          @click="pickProvider(p)"
        >
          <span class="provider-logo">{{ p.logo }}</span>
          <span class="provider-name">{{ p.label }}</span>
          <span class="provider-hint">{{ p.hint }}</span>
        </button>
      </div>
    </section>

    <section class="panel">
      <h2>② 连接配置</h2>

      <div class="field">
        <label>接口地址（Base URL）</label>
        <div class="input-row">
          <input v-model.trim="form.base_url" class="input grow" placeholder="https://api.example.com/v1" />
          <button
            v-if="presetForCurrent"
            type="button"
            class="btn small"
            @click="resetToPreset"
          >
            恢复默认
          </button>
        </div>
      </div>

      <div class="field">
        <label>模型（Model）</label>
        <input
          v-model.trim="form.model"
          class="input grow"
          list="model-suggestions"
          placeholder="如 deepseek-chat / qwen-plus / gpt-4o-mini"
        />
        <datalist id="model-suggestions">
          <option v-for="m in modelSuggestions" :key="m" :value="m"></option>
        </datalist>
      </div>

      <div class="field">
        <label>API Key</label>
        <div class="input-row">
          <input
            v-model="form.api_key"
            :type="showKey ? 'text' : 'password'"
            class="input grow"
            :placeholder="store.hasConfig ? '已保存，留空则保持不变' : 'sk-...'"
            autocomplete="off"
          />
          <button type="button" class="btn small" @click="showKey = !showKey">
            {{ showKey ? '隐藏' : '显示' }}
          </button>
        </div>
        <p v-if="store.hasConfig" class="muted field-note">
          已保存 Key：<code>{{ store.config.api_key_masked }}</code>，留空保存则保持不变。
        </p>
        <p class="muted field-note">Key 在服务器加密存储，接口只返回掩码，不会泄露明文。</p>
      </div>
    </section>

    <section class="panel">
      <h2>③ 测试与保存</h2>

      <div v-if="store.test.status === 'testing'" class="test-result pending">
        ⏳ 正在测试连接…
      </div>
      <div v-else-if="store.test.status === 'ok'" class="test-result ok">
        ✅ {{ store.test.message }}
        <span v-if="store.test.latency != null" class="test-latency">（{{ store.test.latency }} ms）</span>
      </div>
      <div v-else-if="store.test.status === 'fail'" class="test-result fail">
        ❌ {{ store.test.message }}
      </div>

      <div class="ai-actions">
        <button
          type="button"
          class="btn"
          :disabled="store.test.status === 'testing' || (!form.api_key && !store.hasConfig)"
          @click="runTest"
        >
          {{ store.test.status === 'testing' ? '测试中…' : '测试连接' }}
        </button>
        <button
          type="button"
          class="btn primary"
          :disabled="store.test.status === 'testing' || !form.base_url || !form.model"
          @click="save"
        >
          保存配置
        </button>
        <button v-if="store.hasConfig" type="button" class="btn danger" @click="clearConfig">
          清除配置
        </button>
      </div>
      <p v-if="saveError" class="error-text">{{ saveError }}</p>
    </section>

    <p class="muted ai-tip">
      提示：未配置任何 AI 服务时，计划页的「AI 拆解」会提示去设置；服务器若配置了
      <code>LLM_API_KEY</code> 环境变量，仍可作为兜底。
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useAiStore } from '../stores/ai'

const store = useAiStore()

const providers = [
  { key: 'openai', label: 'OpenAI', logo: '🅾️', hint: 'gpt-4o-mini', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { key: 'deepseek', label: 'DeepSeek', logo: '🐋', hint: 'deepseek-chat', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { key: 'qwen', label: '通义千问', logo: '🌙', hint: 'qwen-plus', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { key: 'zhipu', label: '智谱 GLM', logo: '🔮', hint: 'glm-4-flash', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { key: 'moonshot', label: 'Kimi', logo: '🌕', hint: 'moonshot-v1-8k', baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { key: 'custom', label: '自定义', logo: '🛠️', hint: '手动填写', baseUrl: '', model: '' },
]

const form = reactive({
  provider: 'custom',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o-mini',
  api_key: '',
})
const showKey = ref(false)
const saveError = ref('')

const providerLabel = computed(
  () => providers.find((p) => p.key === store.config?.provider)?.label || store.config?.provider || '',
)
const presetForCurrent = computed(
  () => providers.find((p) => p.key === form.provider && p.baseUrl),
)
const modelSuggestions = computed(() => [...new Set(providers.map((p) => p.model).filter(Boolean))])

function pickProvider(p) {
  form.provider = p.key
  if (p.baseUrl) {
    form.base_url = p.baseUrl
    form.model = p.model
  }
}

function resetToPreset() {
  const p = presetForCurrent.value
  if (p) {
    form.base_url = p.baseUrl
    form.model = p.model
  }
}

function applyConfig(config) {
  form.provider = config?.provider || 'custom'
  form.base_url = config?.base_url || 'https://api.openai.com/v1'
  form.model = config?.model || 'gpt-4o-mini'
  form.api_key = ''
}

async function runTest() {
  saveError.value = ''
  try {
    await store.test({
      provider: form.provider,
      base_url: form.base_url,
      model: form.model,
      api_key: form.api_key || undefined,
    })
  } catch {
    /* 结果已写入 store.test */
  }
}

async function save() {
  saveError.value = ''
  try {
    await store.save({
      provider: form.provider,
      base_url: form.base_url,
      model: form.model,
      api_key: form.api_key || undefined,
    })
    form.api_key = ''
  } catch (e) {
    saveError.value = e.message
  }
}

async function clearConfig() {
  if (!window.confirm('确定清除已保存的 AI 配置吗？')) return
  try {
    await store.clear()
    applyConfig(null)
    store.test = { status: 'idle', message: '', latency: null }
  } catch (e) {
    saveError.value = e.message
  }
}

onMounted(async () => {
  await store.fetchConfig()
  applyConfig(store.config)
})
</script>
