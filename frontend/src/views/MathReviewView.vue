<template>
  <div class="page math-page">
    <div class="page-head math-head">
      <div>
        <h1>🧮 高数复习</h1>
        <p class="date-line">高等数学（上）期末复习提纲 · {{ store.total }} 个知识点 · 进度与笔记按账号保存</p>
      </div>
      <div class="head-actions">
        <button class="btn small" @click="collapseAll">折叠全部</button>
        <button class="btn small" @click="expandAll">展开全部</button>
        <button class="btn small danger" :disabled="!store.done" @click="resetProgress">
          清除进度
        </button>
      </div>
    </div>

    <div class="math-progress">
      <div class="math-progress-label">
        <span>总进度</span>
        <span>{{ store.done }} / {{ store.total }}（{{ store.percent }}%）</span>
      </div>
      <div class="math-progress-bar"><i :style="{ width: store.percent + '%' }"></i></div>
    </div>

    <div class="math-toolbar">
      <div class="math-search">
        <input
          v-model="searchQuery"
          type="search"
          placeholder="搜索知识点（如：极限、夹逼、等价无穷小…）"
        />
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</button>
      </div>
      <div class="filter-chips">
        <button
          v-for="tag in tagOptions"
          :key="tag"
          class="chip"
          :class="{ active: activeTag === tag }"
          @click="activeTag = tag"
        >
          {{ tag }}
          <span v-if="tag !== '全部'" class="chip-count">{{ tagCount(tag) }}</span>
        </button>
      </div>
      <span class="result-count">{{ visibleItemCount }} 条结果</span>
    </div>

    <div class="math-layout">
      <aside class="math-toc">
        <h3>📚 目录</h3>
        <a
          v-for="ch in store.chapters"
          :key="ch.id"
          href="#"
          @click.prevent="scrollToChapter(ch.id)"
        >
          <span class="toc-num">{{ ch.num }}</span>{{ ch.short }}
          <span class="toc-stat">{{ ch.done }}/{{ ch.total }}</span>
        </a>
      </aside>

      <main class="math-main">
        <p v-if="store.loading" class="muted">加载中…</p>
        <p v-else-if="store.error" class="error-text">{{ store.error }}</p>
        <template v-else>
          <section
            v-for="ch in filteredChapters"
            :key="ch.id"
            :id="'math-ch-' + ch.id"
            class="math-chapter panel"
          >
            <div class="chapter-head" @click="toggleChapter(ch.id)">
              <span class="chapter-title">{{ ch.num }} {{ ch.title }}</span>
              <span class="chapter-progress">{{ ch.done }}/{{ ch.total }}</span>
              <button
                class="note-btn"
                title="章节笔记"
                :class="{ editing: editingNote === ch.id }"
                @click.stop="openNote(ch)"
              >
                📝
              </button>
              <span class="collapse-arrow">{{ isCollapsed(ch.id) ? '▸' : '▾' }}</span>
            </div>
            <div class="chapter-progress-bar">
              <i :style="{ width: chapterPercent(ch) + '%' }"></i>
            </div>

            <div v-if="editingNote === ch.id" class="note-editor">
              <textarea
                v-model="noteDraft"
                class="input"
                rows="3"
                :placeholder="ch.note_placeholder"
              ></textarea>
              <div class="note-actions">
                <button class="btn small primary" :disabled="busy" @click="saveNote(ch)">
                  {{ busy ? '保存中…' : '保存笔记' }}
                </button>
                <button class="btn small" @click="closeNote">取消</button>
              </div>
            </div>
            <p v-else-if="ch.note" class="chapter-note" @click="openNote(ch)">
              📝 {{ ch.note }}
            </p>

            <template v-if="!isCollapsed(ch.id)">
              <div v-for="sub in ch.subs" :key="sub.title" class="math-sub">
                <div class="sub-head">
                  <h4>{{ sub.title }}</h4>
                  <span v-if="sub.tag" class="tag tag-math">{{ sub.tag }}</span>
                </div>
                <ul class="math-items">
                  <li
                    v-for="item in sub.items"
                    :key="item.id"
                    class="math-item"
                    :class="{ done: item.done }"
                  >
                    <input
                      type="checkbox"
                      :checked="item.done"
                      :title="item.done ? '标记为未掌握' : '标记为已掌握'"
                      @change="toggleItem(item)"
                    />
                    <div class="item-content">
                      <span v-for="(seg, idx) in renderItem(item)" :key="idx">
                        <template v-if="seg.type === 'text'">{{ seg.text }}</template>
                        <span v-else-if="!seg.block" class="math-inline" v-html="seg.html"></span>
                        <div v-else class="math-block" v-html="seg.html"></div>
                      </span>
                    </div>
                  </li>
                </ul>
              </div>
              <p v-if="!ch.subs.length" class="muted">该章节没有匹配项。</p>
            </template>
          </section>

          <p v-if="!filteredChapters.length" class="empty-state">
            没有匹配的知识点，换个关键词或标签试试。
          </p>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useMathStore } from '../stores/math'

const store = useMathStore()

const searchQuery = ref('')
const activeTag = ref('全部')
const collapsed = reactive(new Set())
const editingNote = ref(null)
const noteDraft = ref('')
const busy = ref(false)

const tagOptions = ['全部', '必考', '必背', '高频', '证明题', '定义题', '应用题', '易错']

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const htmlCache = new Map()
function renderItem(item) {
  if (htmlCache.has(item.id)) return htmlCache.get(item.id)
  const rendered = item.segments.map((seg) => {
    if (seg.t === 'math') {
      let html = ''
      try {
        html = katex.renderToString(seg.tex, {
          displayMode: Boolean(seg.block),
          throwOnError: false,
        })
      } catch {
        html = `<span class="katex-fallback">${escapeHtml(seg.fallback || seg.tex)}</span>`
      }
      return { type: 'math', block: Boolean(seg.block), html }
    }
    return { type: 'text', text: seg.v }
  })
  htmlCache.set(item.id, rendered)
  return rendered
}

function matches(item) {
  const tagOk = activeTag.value === '全部' || item.tag === activeTag.value
  if (!tagOk) return false
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return true
  return item.segments.some((seg) => {
    const text = seg.t === 'math' ? `${seg.tex} ${seg.fallback || ''}` : seg.v
    return text.toLowerCase().includes(q)
  })
}

const filteredChapters = computed(() => {
  if (!searchQuery.value.trim() && activeTag.value === '全部') return store.chapters
  return store.chapters
    .map((ch) => ({
      ...ch,
      subs: ch.subs
        .map((sub) => ({ ...sub, items: sub.items.filter(matches) }))
        .filter((sub) => sub.items.length),
    }))
    .filter((ch) => ch.subs.length)
})

const visibleItemCount = computed(() =>
  filteredChapters.value.reduce(
    (sum, ch) => sum + ch.subs.reduce((s, sub) => s + sub.items.length, 0),
    0,
  ),
)

function tagCount(tag) {
  return store.chapters.reduce(
    (sum, ch) => sum + ch.subs.reduce((s, sub) => s + sub.items.filter((i) => i.tag === tag).length, 0),
    0,
  )
}

function chapterPercent(ch) {
  return ch.total ? Math.round((ch.done / ch.total) * 100) : 0
}

function isCollapsed(id) {
  return collapsed.has(id)
}

function toggleChapter(id) {
  if (collapsed.has(id)) collapsed.delete(id)
  else collapsed.add(id)
}

function collapseAll() {
  for (const ch of store.chapters) collapsed.add(ch.id)
}

function expandAll() {
  collapsed.clear()
}

function scrollToChapter(id) {
  document.getElementById(`math-ch-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function toggleItem(item) {
  try {
    await store.setDone(item.id, !item.done)
  } catch (err) {
    alert(`保存失败：${err.message}`)
  }
}

function openNote(ch) {
  editingNote.value = ch.id
  noteDraft.value = ch.note || ''
}

function closeNote() {
  editingNote.value = null
  noteDraft.value = ''
}

async function saveNote(ch) {
  busy.value = true
  try {
    await store.saveNote(ch.id, noteDraft.value)
    closeNote()
  } catch (err) {
    alert(`笔记保存失败：${err.message}`)
  } finally {
    busy.value = false
  }
}

async function resetProgress() {
  if (!confirm('确定清除全部已掌握标记吗？此操作不可撤销。')) return
  try {
    await store.resetProgress()
  } catch (err) {
    alert(`清除失败：${err.message}`)
  }
}

onMounted(() => {
  store.fetchTree()
})
</script>

<style scoped>
.math-page .page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.head-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.math-progress {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 14px;
}

.math-progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.math-progress-bar {
  height: 10px;
  background: rgba(148, 163, 184, 0.22);
  border-radius: 99px;
  overflow: hidden;
}

.math-progress-bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--primary), #22c55e);
  border-radius: 99px;
  transition: width 0.4s ease;
}

.math-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  box-shadow: var(--shadow-sm);
}

.math-search {
  position: relative;
}

.math-search input {
  width: 100%;
  padding: 10px 36px 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
  color: var(--text);
  font: inherit;
  font-size: 14px;
}

.math-search input:focus {
  outline: 2px solid var(--primary);
  border-color: var(--primary);
}

.search-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 6px;
}

.filter-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.chip-count {
  font-size: 11px;
  opacity: 0.75;
  margin-left: 3px;
}

.result-count {
  font-size: 12.5px;
  color: var(--text-muted);
}

.math-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 18px;
  align-items: start;
}

.math-toc {
  position: sticky;
  top: 76px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px;
  box-shadow: var(--shadow-sm);
}

.math-toc h3 {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.math-toc a {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 8px;
  color: var(--text);
  text-decoration: none;
  font-size: 13.5px;
  transition: 0.15s;
}

.math-toc a:hover {
  background: var(--primary-soft);
  color: var(--primary);
}

.toc-num {
  min-width: 22px;
  color: var(--primary);
  font-weight: 700;
}

.toc-stat {
  margin-left: auto;
  font-size: 12px;
  color: var(--success);
  font-weight: 600;
}

.math-main {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.math-chapter {
  scroll-margin-top: 90px;
  padding: 16px 18px;
}

.chapter-head {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.chapter-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--primary-dark);
  border-left: 5px solid var(--primary);
  padding-left: 12px;
  flex: 1;
}

.chapter-progress {
  font-size: 12.5px;
  color: var(--text-muted);
}

.note-btn {
  border: 0;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  opacity: 0.65;
  transition: 0.15s;
}

.note-btn:hover,
.note-btn.editing {
  opacity: 1;
  transform: scale(1.12);
}

.collapse-arrow {
  color: var(--text-muted);
  font-size: 15px;
}

.chapter-progress-bar {
  height: 6px;
  background: rgba(148, 163, 184, 0.22);
  border-radius: 99px;
  overflow: hidden;
  margin: 10px 0 12px;
}

.chapter-progress-bar i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--primary), #22c55e);
  border-radius: 99px;
  transition: width 0.4s;
}

.chapter-note {
  font-size: 13.5px;
  background: var(--accent-soft);
  border: 1px dashed var(--accent);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  margin-bottom: 12px;
  cursor: pointer;
  white-space: pre-wrap;
}

.note-editor {
  margin-bottom: 12px;
}

.note-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.math-sub {
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 10px;
}

.sub-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.sub-head h4 {
  font-size: 14.5px;
}

.tag-math {
  background: var(--warn-bg, var(--accent-soft));
  color: var(--warn, var(--accent));
  font-size: 11px;
}

.math-items {
  list-style: none;
  margin-top: 6px;
}

.math-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 7px 8px;
  border-radius: 8px;
  cursor: default;
  transition: 0.15s;
  font-size: 14.5px;
  line-height: 1.8;
}

.math-item:hover {
  background: var(--primary-soft);
}

.math-item.done {
  background: var(--success-soft);
}

.math-item.done .item-content {
  color: #14532d;
  text-decoration: line-through;
  text-decoration-color: #86efac;
}

:root[data-theme='dark'] .math-item.done .item-content {
  color: #a7f3d0;
}

.math-item input[type='checkbox'] {
  appearance: none;
  -webkit-appearance: none;
  width: 19px;
  height: 19px;
  min-width: 19px;
  border: 2px solid #94a3b8;
  border-radius: 6px;
  cursor: pointer;
  margin-top: 4px;
  position: relative;
  transition: 0.15s;
  background: var(--surface);
}

.math-item input[type='checkbox']:checked {
  background: var(--primary);
  border-color: var(--primary);
}

.math-item input[type='checkbox']:checked::after {
  content: '✓';
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  line-height: 1;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-content :deep(.math-inline .katex) {
  font-size: 1.05em;
}

.item-content :deep(.math-block) {
  margin: 8px 0;
  overflow-x: auto;
  padding: 6px 0;
}

.item-content :deep(.math-block .katex-display) {
  margin: 0;
}

.katex-fallback {
  color: var(--danger);
  font-style: italic;
}

@media (max-width: 900px) {
  .math-layout {
    grid-template-columns: 1fr;
  }

  .math-toc {
    position: static;
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding: 10px;
  }

  .math-toc h3 {
    display: none;
  }

  .math-toc a {
    white-space: nowrap;
    flex: 0 0 auto;
  }
}
</style>
