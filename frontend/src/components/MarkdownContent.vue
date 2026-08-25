<template>
  <div class="markdown-body" v-html="sanitized"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{ content: string; streaming?: boolean }>()

// During streaming, marked.parse receives incomplete markdown and renders
// raw syntax characters (**, `, ```) as plain text. Closing unclosed
// constructs before parsing prevents layout thrash and visual glitches.
function closeIncompleteMarkdown(content: string): string {
  // Close unclosed code fences (most disruptive when left open)
  const fenceMatches = [...content.matchAll(/^(`{3,})/gm)]
  const insideCodeFence = fenceMatches.length % 2 !== 0
  if (insideCodeFence) {
    // Return early: inside a code fence, other inline syntax is literal text
    return content + '\n' + fenceMatches[fenceMatches.length - 1][1]
  }

  // Close unclosed inline code on the last line only
  const lastLine = content.slice(content.lastIndexOf('\n') + 1)
  const singleBackticks = (lastLine.match(/(?<!`)`(?!`)/g) || []).length
  if (singleBackticks % 2 !== 0) {
    content += '`'
  }

  // Close unclosed bold (**)
  const boldCount = (content.match(/\*\*/g) || []).length
  if (boldCount % 2 !== 0) {
    content += '**'
  }

  return content
}

const sanitized = computed(() => {
  const raw = props.streaming ? closeIncompleteMarkdown(props.content) : props.content
  return DOMPurify.sanitize(
    marked.parse(raw, { gfm: true, breaks: true }) as string
  )
})
</script>

<style>
.markdown-body {
  line-height: 1.7;
  word-break: break-word;
  color: inherit;
}

.markdown-body p {
  margin: 0 0 0.75em;
}
.markdown-body p:last-child {
  margin-bottom: 0;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin: 0.9em 0 0.4em;
  font-weight: 600;
  line-height: 1.3;
}
.markdown-body h1 { font-size: 1.4em; }
.markdown-body h2 { font-size: 1.2em; }
.markdown-body h3 { font-size: 1.05em; }

.markdown-body ul,
.markdown-body ol {
  padding-left: 1.5em;
  margin: 0.4em 0 0.75em;
}
.markdown-body li {
  margin: 0.2em 0;
}

.markdown-body code {
  background: #f0f2f5;
  border-radius: 4px;
  padding: 0.15em 0.4em;
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 0.88em;
  color: #c7254e;
}

.markdown-body pre {
  background: #f0f2f5;
  border-radius: 8px;
  padding: 12px 16px;
  overflow-x: auto;
  margin: 0.5em 0;
}
.markdown-body pre code {
  background: none;
  padding: 0;
  color: #303133;
  font-size: 0.85em;
}

.markdown-body blockquote {
  border-left: 4px solid #409eff;
  margin: 0.5em 0;
  padding: 0.3em 0 0.3em 1em;
  color: #606266;
  background: #ecf5ff;
  border-radius: 0 6px 6px 0;
}

.markdown-body strong { font-weight: 600; }
.markdown-body em { font-style: italic; }

.markdown-body hr {
  border: none;
  border-top: 1px solid #e4e7ed;
  margin: 0.8em 0;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5em 0;
  font-size: 0.9em;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid #e4e7ed;
  padding: 6px 10px;
  text-align: left;
}
.markdown-body th {
  background: #f5f7fa;
  font-weight: 600;
}
</style>
