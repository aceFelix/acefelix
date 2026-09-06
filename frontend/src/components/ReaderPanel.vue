<!--
  阅读器面板：实体属性的图片/文档在中间区域就地展示浏览
  - 图片：<img> 直接渲染
  - PDF：<iframe> 内嵌浏览器自带查看器（翻页/缩放/搜索）
  - Markdown：fetch 文本 → marked 渲染 → DOMPurify 消毒（防 XSS）
  - txt：fetch 文本 → <pre> 原样展示
  - docx：fetch ArrayBuffer → mammoth 转 HTML → DOMPurify 消毒
    （动态 import 按需加载，避免 ~500KB 的 mammoth 进主包；复杂排版保真度有限）
  - 其他格式（xmind 等二期支持）：降级为「新窗口打开/下载」
  悬浮于 3D 宇宙背景之上，毛玻璃风格与整体主题一致。
  @author aceFelix
-->
<script setup>
import { ref, watch, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  // 阅读项：{ url: 绝对地址, title: 展示标题 }
  item: { type: Object, default: null },
})
const emit = defineEmits(['close'])

// 文本类内容（md/txt）的加载状态
const textContent = ref('')
const loading = ref(false)
const loadError = ref('')
// docx 转换后的 HTML（已经 DOMPurify 消毒）
const docxHtml = ref('')

/**
 * 按 URL 扩展名判定内容种类
 * @returns {'image'|'pdf'|'md'|'text'|'docx'|'other'}
 */
const kind = computed(() => {
  const u = (props.item?.url || '').split('?')[0].split('#')[0].toLowerCase()
  if (/\.(png|jpe?g|gif|webp|svg|bmp|ico|avif)$/.test(u)) return 'image'
  if (u.endsWith('.pdf')) return 'pdf'
  if (u.endsWith('.md')) return 'md'
  if (u.endsWith('.txt')) return 'text'
  if (u.endsWith('.docx')) return 'docx'
  return 'other'
})

// 切换阅读项时按需拉取内容（md/txt 取文本，docx 取二进制并转 HTML，图片/PDF 交给浏览器）
watch(
  () => props.item?.url,
  async (url) => {
    textContent.value = ''
    docxHtml.value = ''
    loadError.value = ''
    if (!url) return
    if (kind.value === 'md' || kind.value === 'text') {
      loading.value = true
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        textContent.value = await res.text()
      } catch (err) {
        loadError.value = `内容加载失败：${err.message}（可尝试新窗口打开）`
      } finally {
        loading.value = false
      }
    } else if (kind.value === 'docx') {
      loading.value = true
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const buffer = await res.arrayBuffer()
        // 动态 import：仅首次打开 docx 时才加载 mammoth（浏览器版入口，不依赖 Node fs）
        const mammoth = await import('mammoth/mammoth.browser')
        const result = await mammoth.convertToHtml({ arrayBuffer: buffer })
        // 转换出的 HTML 必须消毒，防止文档内嵌恶意标签/属性造成 XSS
        docxHtml.value = DOMPurify.sanitize(result.value)
      } catch (err) {
        loadError.value = `docx 解析失败：${err.message}（加密/损坏文档可尝试新窗口打开）`
      } finally {
        loading.value = false
      }
    }
  },
  { immediate: true }
)

/**
 * Markdown 渲染：marked 解析为 HTML 后必须经 DOMPurify 消毒，
 * 防止文档中内嵌 <script>/事件属性造成 XSS
 */
const renderedHtml = computed(() => {
  if (kind.value !== 'md' || !textContent.value) return ''
  return DOMPurify.sanitize(marked.parse(textContent.value))
})

// ESC 快捷关闭
watch(
  () => props.item,
  (val) => {
    const onKey = (e) => e.key === 'Escape' && emit('close')
    if (val) window.addEventListener('keydown', onKey)
    else window.removeEventListener('keydown', onKey)
  }
)
</script>

<template>
  <div class="reader-overlay" @click.self="emit('close')">
    <div class="reader-panel">
      <!-- 头部：标题 + 新窗口打开（兜底） + 关闭 -->
      <div class="reader-header">
        <span class="reader-icon">{{ kind === 'image' ? '🖼️' : '📄' }}</span>
        <span class="reader-title" :title="item?.url">{{ item?.title || '预览' }}</span>
        <a class="reader-open" :href="item?.url" target="_blank" title="在新窗口打开">↗ 新窗口</a>
        <button class="reader-close" title="关闭 (Esc)" @click="emit('close')">✕</button>
      </div>

      <!-- 内容区：按种类分流渲染 -->
      <div class="reader-body">
        <img v-if="kind === 'image'" :src="item?.url" class="reader-image" />
        <iframe v-else-if="kind === 'pdf'" :src="item?.url" class="reader-frame"></iframe>
        <div v-else-if="kind === 'md'" class="reader-text">
          <div v-if="loading" class="reader-hint">加载中...</div>
          <div v-else-if="loadError" class="reader-hint error">{{ loadError }}</div>
          <!-- eslint-disable-next-line vue/no-v-html -- 已经 DOMPurify 消毒 -->
          <div v-else class="md-body" v-html="renderedHtml"></div>
        </div>
        <div v-else-if="kind === 'text'" class="reader-text">
          <div v-if="loading" class="reader-hint">加载中...</div>
          <div v-else-if="loadError" class="reader-hint error">{{ loadError }}</div>
          <pre v-else class="txt-body">{{ textContent }}</pre>
        </div>
        <!-- docx：mammoth 转出的 HTML 复用 md 排版样式（已经 DOMPurify 消毒） -->
        <div v-else-if="kind === 'docx'" class="reader-text">
          <div v-if="loading" class="reader-hint">docx 解析中...</div>
          <div v-else-if="loadError" class="reader-hint error">{{ loadError }}</div>
          <!-- eslint-disable-next-line vue/no-v-html -- 已经 DOMPurify 消毒 -->
          <div v-else class="md-body" v-html="docxHtml"></div>
        </div>
        <!-- 二期格式（xmind）与未知格式的降级提示 -->
        <div v-else class="reader-fallback">
          <p>该格式暂不支持内嵌预览（xmind 将在后续版本支持）</p>
          <a class="btn-primary-link" :href="item?.url" target="_blank">↗ 新窗口打开 / 下载</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 遮罩层：全屏模态，点击空白处关闭；恢复指针交互（布局层是穿透的） */
.reader-overlay {
  position: fixed;
  inset: 0;
  z-index: 8; /* 高于侧栏(2)/状态栏(5)，低于顶栏(10) */
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  pointer-events: auto;
}
/* 阅读窗：毛玻璃面板，与宇宙主题一致 */
.reader-panel {
  width: min(1000px, 92vw);
  height: min(760px, 86vh);
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.45);
  overflow: hidden;
}
.reader-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.reader-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.reader-open {
  font-size: 12px;
  color: var(--accent, #4ecdc4);
  text-decoration: none;
  flex-shrink: 0;
}
.reader-open:hover {
  text-decoration: underline;
}
.reader-close {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}
.reader-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}
.reader-body {
  flex: 1;
  min-height: 0; /* 关键：Grid/Flex 子项内部滚动必需 */
  overflow: hidden;
  display: flex;
}
.reader-image {
  margin: auto;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.reader-frame {
  flex: 1;
  border: none;
  background: #1a1a2e;
}
.reader-text {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 16px 24px;
}
.reader-hint {
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}
.reader-hint.error {
  color: var(--danger, #ff6b6b);
}
.txt-body {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
}
.reader-fallback {
  margin: auto;
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
}
.btn-primary-link {
  display: inline-block;
  margin-top: 12px;
  padding: 8px 16px;
  border-radius: 6px;
  background: var(--accent, #4ecdc4);
  color: #0b0d17;
  font-weight: 600;
  text-decoration: none;
}

/* Markdown 正文排版（v-html 内容不受 scoped 影响，用 :deep 穿透） */
.md-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
}
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3) {
  margin: 16px 0 8px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 4px;
}
.md-body :deep(p) {
  margin: 8px 0;
}
.md-body :deep(code) {
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12.5px;
}
.md-body :deep(pre) {
  background: rgba(0, 0, 0, 0.35);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}
.md-body :deep(pre code) {
  background: transparent;
  padding: 0;
}
.md-body :deep(img) {
  max-width: 100%;
  border-radius: 6px;
}
.md-body :deep(a) {
  color: var(--accent, #4ecdc4);
}
.md-body :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid var(--border);
  padding: 4px 10px;
}
.md-body :deep(blockquote) {
  border-left: 3px solid var(--accent, #4ecdc4);
  margin: 8px 0;
  padding: 2px 12px;
  color: var(--text-secondary);
}
</style>
