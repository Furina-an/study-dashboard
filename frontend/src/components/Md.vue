<template>
  <div class="md-body" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ source: { type: String, default: '' } })

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function inline(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[*\s>])[*_]([^*_]+)[*_]($|[*\s<])/g, '$1<em>$2</em>$3')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
}

function render(md) {
  const lines = escapeHtml(md).split('\n')
  const out = []
  let inCode = false
  let codeBuf = []
  let inList = false
  let para = []
  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.join(' ')}</p>`)
      para = []
    }
  }
  const flushList = () => {
    if (inList) {
      out.push('</ul>')
      inList = false
    }
  }
  for (const raw of lines) {
    if (raw.trim().startsWith('```')) {
      flushPara()
      flushList()
      if (inCode) {
        out.push(`<pre><code>${codeBuf.join('\n')}</code></pre>`)
        codeBuf = []
        inCode = false
      } else {
        inCode = true
      }
      continue
    }
    if (inCode) {
      codeBuf.push(raw)
      continue
    }
    const line = raw.trim()
    if (!line) {
      flushPara()
      flushList()
      continue
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      flushPara()
      flushList()
      const level = heading[1].length
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`)
      continue
    }
    const item = line.match(/^[-*]\s+(.*)$/)
    if (item) {
      flushPara()
      if (!inList) {
        out.push('<ul>')
        inList = true
      }
      out.push(`<li>${inline(item[1])}</li>`)
      continue
    }
    const quote = line.match(/^>\s?(.*)$/)
    if (quote) {
      flushPara()
      flushList()
      out.push(`<blockquote>${inline(quote[1])}</blockquote>`)
      continue
    }
    para.push(line)
  }
  flushPara()
  flushList()
  if (inCode) out.push(`<pre><code>${codeBuf.join('\n')}</code></pre>`)
  return out.join('\n')
}

const html = computed(() => render(props.source))
</script>

<style scoped>
.md-body :deep(p) { margin: 6px 0; }
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3), .md-body :deep(h4) {
  margin: 10px 0 6px;
  line-height: 1.4;
}
.md-body :deep(h1) { font-size: 1.25em; }
.md-body :deep(h2) { font-size: 1.15em; }
.md-body :deep(h3) { font-size: 1.05em; }
.md-body :deep(ul) { margin: 6px 0; padding-left: 20px; }
.md-body :deep(li) { margin: 3px 0; }
.md-body :deep(code) {
  background: rgba(99, 102, 241, 0.1);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.92em;
}
.md-body :deep(pre) {
  background: rgba(0, 0, 0, 0.06);
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}
.md-body :deep(pre code) { background: none; padding: 0; }
.md-body :deep(blockquote) {
  border-left: 3px solid var(--primary-light);
  padding-left: 10px;
  margin: 6px 0;
  color: var(--text-muted);
}
.md-body :deep(a) { color: var(--primary); }
</style>
