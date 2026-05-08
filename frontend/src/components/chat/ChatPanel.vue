<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useI18n } from '@/i18n'
import PlanCard from './PlanCard.vue'
import type { ToolCallEvent } from '@/types'
import { marked } from 'marked'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'        // HTML
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'
import diff from 'highlight.js/lib/languages/diff'
import plaintext from 'highlight.js/lib/languages/plaintext'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('css', css)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('md', markdown)
hljs.registerLanguage('diff', diff)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)

// 配置 marked + highlight.js
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: (code: string, lang: string) => {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
})

// Markdown 渲染 + 代码块包裹
function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = marked.parse(text) as string
  html = html.split('<pre><code').join(
    '<div class="code-block"><div class="code-block-header">' +
    '<span class="code-block-lang"></span>' +
    '<button class="code-block-copy">复制</button></div><pre><code'
  )
  html = html.split('</code></pre>').join('</code></pre></div>')
  return html
}

const props = defineProps<{
  messages: { id: string; role: string; content: string; timestamp: string; toolCalls?: ToolCallEvent[]; plan?: any; planSteps?: any[]; attachments?: any[] }[]
  isGenerating?: boolean
}>()

const emit = defineEmits<{
  quickStart: [text: string]
}>()

const quickCards = [
  { icon: '📝', label: '写代码', text: '开发一个五子棋HTML游戏' },
  { icon: '📊', label: '数据分析', text: '分析CSV销售数据并生成报告' },
  { icon: '🔍', label: '查资料', text: '搜索最新AI框架对比' },
  { icon: '🐛', label: '调试修复', text: '帮我修复这个Python脚本的bug' },
]

const { t } = useI18n()
const panelRef = ref<HTMLElement | null>(null)
const collapsedTools = ref<Set<string>>(new Set())

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const scrollToBottom = async () => {
  await nextTick()
  if (panelRef.value) panelRef.value.scrollTop = panelRef.value.scrollHeight
}

watch(() => props.messages.length, scrollToBottom)
watch(() => props.isGenerating, scrollToBottom)

const isCommandBanner = (m: any) => {
  if (m.role !== 'system') return false
  const c = m.content || ''
  return c.includes('MODE') || c.includes('会话已清空')
}

const getCmdStyle = (content: string) => {
  if (content.includes('PLAN')) return 'bg-amber-900/20 border-amber-700/40 text-amber-300'
  if (content.includes('YOLO')) return 'bg-emerald-900/20 border-emerald-700/40 text-emerald-300'
  if (content.includes('BRAINSTORM')) return 'bg-purple-900/20 border-purple-700/40 text-purple-300'
  if (content.includes('清空')) return 'bg-blue-900/20 border-blue-700/40 text-blue-300'
  return 'bg-slate-800 border-slate-700 text-slate-300'
}

const getCmdIcon = (content: string) => {
  if (content.includes('PLAN')) return '🟡'
  if (content.includes('YOLO')) return '🟢'
  if (content.includes('BRAINSTORM')) return '💡'
  if (content.includes('清空')) return '🆕'
  return '📋'
}

const toggleToolCard = (id: string) => {
  if (collapsedTools.value.has(id)) collapsedTools.value.delete(id)
  else collapsedTools.value.add(id)
}

onMounted(() => {
  document.addEventListener('click', (e: Event) => {
    const btn = (e.target as HTMLElement).closest('.code-block-copy')
    if (!btn) return
    const block = btn.closest('.code-block')
    if (!block) return
    const code = block.querySelector('code')
    if (!code) return
    navigator.clipboard.writeText(code.textContent || '').then(() => {
      ;(btn as HTMLElement).textContent = '✓'
      setTimeout(() => { (btn as HTMLElement).textContent = '复制' }, 2000)
    }).catch(() => {})
  })
})
</script>

<template>
  <div ref="panelRef" class="flex-1 overflow-y-auto scroll-smooth">
    <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full px-6">
      <div class="w-16 h-16 bg-gradient-to-br from-blue-500/20 to-purple-600/20 rounded-2xl flex items-center justify-center mb-4 ring-1 ring-blue-500/20">
        <svg class="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
      </div>
      <h2 class="text-xl font-semibold text-white mb-1">TARS Agent</h2>
      <p class="text-sm text-slate-400 mb-8">你的 AI 工程助手 — 代码、规划、执行</p>

      <!-- 快捷入口 -->
      <div class="grid grid-cols-2 gap-3 w-full max-w-md">
        <button
          v-for="card in quickCards"
          :key="card.text"
          @click="$emit('quickStart', card.text)"
          class="flex items-center gap-3 px-4 py-3 bg-slate-800/60 border border-slate-700/60 rounded-xl hover:border-blue-500/50 hover:bg-slate-800 transition-all text-left group"
        >
          <span class="text-lg group-hover:scale-110 transition-transform">{{ card.icon }}</span>
          <div>
            <p class="text-sm text-slate-300 group-hover:text-white transition-colors">{{ card.label }}</p>
            <p class="text-xs text-slate-500">{{ card.text }}</p>
          </div>
        </button>
      </div>
    </div>

    <div v-else class="max-w-3xl mx-auto px-6 py-6 space-y-1">
      <template v-for="(msg, idx) in messages" :key="idx">

        <div v-if="isCommandBanner(msg)" class="flex justify-center py-2">
          <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border text-xs font-medium" :class="getCmdStyle(msg.content)">
            <span>{{ getCmdIcon(msg.content) }}</span>
            <span>{{ msg.content }}</span>
          </div>
        </div>

        <PlanCard v-else-if="(msg as any).planSteps" :plan="(msg as any).plan" :steps="(msg as any).planSteps" />

        <div v-else class="flex gap-3 py-2" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
          <div class="flex-shrink-0 mt-1">
            <div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
              :class="{
                'bg-blue-600 text-white': msg.role === 'user',
                'bg-gradient-to-br from-blue-500 to-purple-600 text-white': msg.role === 'assistant',
                'bg-red-900/50 text-red-300': msg.role === 'system',
              }">
              <template v-if="msg.role === 'user'">你</template>
              <template v-else-if="msg.role === 'assistant'">T</template>
              <template v-else>!</template>
            </div>
          </div>

          <div class="flex-1 min-w-0" :class="msg.role === 'user' ? 'flex flex-col items-end' : ''">
            <div class="flex items-center gap-2 mb-1" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
              <span class="text-xs font-semibold" :class="{
                'text-blue-400': msg.role === 'user',
                'text-purple-400': msg.role === 'assistant',
                'text-red-400': msg.role === 'system',
              }">{{ msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'TARS' : 'System' }}</span>
              <span class="text-[10px] text-slate-600">{{ formatTime(msg.timestamp) }}</span>
            </div>

            <!-- 用户气泡 -->
            <div v-if="msg.role === 'user'" class="inline-block max-w-[85%] px-4 py-2.5 bg-blue-600 text-white rounded-2xl rounded-tr-sm">
              <div class="whitespace-pre-wrap text-sm leading-relaxed">{{ msg.content }}</div>
              <div v-if="msg.attachments?.length" class="mt-2 flex flex-wrap gap-1.5">
                <span v-for="att in msg.attachments" :key="att.file_id" class="text-xs px-2 py-0.5 bg-blue-500/50 rounded-full">{{ att.name }}</span>
              </div>
            </div>

            <!-- TARS 卡片 -->
            <div v-else class="max-w-[95%]">
              <div class="markdown-body text-sm text-slate-300 leading-relaxed" v-html="renderMarkdown(msg.content)"></div>

              <!-- 工具调用 -->
              <div v-if="msg.toolCalls?.length" class="mt-3 space-y-1.5">
                <div v-for="tc in msg.toolCalls" :key="tc.id || tc.tool" class="bg-slate-800/60 border border-slate-700/60 rounded-lg overflow-hidden">
                  <button @click="toggleToolCard(tc.id || tc.tool)" class="w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-slate-700/50 transition-colors">
                    <svg class="w-3 h-3 transition-transform" :class="collapsedTools.has(tc.id || tc.tool) ? '' : 'rotate-90'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                    </svg>
                    <span class="text-blue-400 font-medium">🔧 {{ tc.tool }}</span>
                    <span v-if="tc.duration" class="text-slate-600 ml-auto">{{ tc.duration }}s</span>
                    <span v-if="tc.output && !tc.error" class="text-green-500 ml-1">✓</span>
                    <span v-if="tc.error" class="text-red-500 ml-1">✕</span>
                  </button>
                  <div v-if="!collapsedTools.has(tc.id || tc.tool)" class="px-3 pb-2">
                    <div v-if="tc.output" class="text-xs text-slate-400 bg-slate-900/50 rounded p-2 max-h-32 overflow-auto font-mono whitespace-pre-wrap">{{ tc.output }}</div>
                    <div v-if="tc.error" class="text-xs text-red-400 bg-red-900/20 rounded p-2">{{ tc.error }}</div>
                  </div>
                </div>
              </div>

              <div class="flex items-center gap-2 mt-2 opacity-0 hover:opacity-100 transition-opacity">
                <button class="text-xs text-slate-600 hover:text-slate-400" title="复制">📋</button>
                <button class="text-xs text-slate-600 hover:text-slate-400" title="引用">💬</button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- 思考中 -->
      <div v-if="isGenerating" class="flex items-center gap-3 pl-11 py-2">
        <div class="flex gap-1">
          <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0s"></span>
          <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0.2s"></span>
          <span class="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style="animation-delay:0.4s"></span>
        </div>
        <span class="text-xs text-slate-500">{{ t('chat.thinking') }}</span>
      </div>
    </div>
  </div>
</template>
<style>
@import "highlight.js/styles/atom-one-dark.css";
.code-block { position: relative; margin: 1rem 0; border-radius: 0.75rem; overflow: hidden; border: 1px solid rgba(51,65,85,0.5); }
.code-block-header { display: flex; align-items: center; justify-content: space-between; padding: 0.375rem 1rem; background: rgba(30,41,59,0.8); font-size: 0.75rem; }
.code-block-lang { color: #64748b; }
.code-block-copy { color: #94a3b8; cursor: pointer; background: none; border: none; font-size: 0.75rem; }
.code-block-copy:hover { color: #e2e8f0; }
.code-block pre { margin: 0; border-radius: 0; }
.code-block code { display: block; padding: 1rem; }
.markdown-body h1 { font-size: 1.25rem; font-weight: 700; color: #fff; margin: 1.5rem 0 0.75rem; }
.markdown-body h2 { font-size: 1.1rem; font-weight: 600; color: #f1f5f9; margin: 1.25rem 0 0.5rem; }
.markdown-body h3 { font-size: 1rem; font-weight: 500; color: #e2e8f0; margin: 1rem 0 0.5rem; }
.markdown-body p { margin-bottom: 0.75rem; line-height: 1.65; }
.markdown-body ul { list-style: disc; padding-left: 1.5rem; margin-bottom: 0.75rem; }
.markdown-body ol { list-style: decimal; padding-left: 1.5rem; margin-bottom: 0.75rem; }
.markdown-body li { margin-bottom: 0.25rem; }
.markdown-body a { color: #60a5fa; text-decoration: underline; }
.markdown-body strong { color: #f1f5f9; font-weight: 600; }
.markdown-body code { background: #1e293b; color: #fda4af; font-size: 0.8rem; padding: 0.125rem 0.375rem; border-radius: 0.25rem; font-family: "SF Mono","Fira Code",monospace; }
.markdown-body pre { background: #0f172a; border: 1px solid rgba(51,65,85,0.5); border-radius: 0.75rem; padding: 1rem; margin: 1rem 0; overflow-x: auto; }
.markdown-body pre code { background: transparent; color: #cbd5e1; padding: 0; font-size: 0.8rem; line-height: 1.5; }
.markdown-body table { width: 100%; font-size: 0.75rem; border-collapse: collapse; margin: 0.75rem 0; }
.markdown-body th { background: #1e293b; color: #e2e8f0; padding: 0.5rem 0.75rem; text-align: left; font-weight: 500; border: 1px solid #334155; }
.markdown-body td { padding: 0.5rem 0.75rem; border: 1px solid rgba(51,65,85,0.5); color: #cbd5e1; }
.markdown-body blockquote { border-left: 3px solid rgba(96,165,250,0.4); padding-left: 1rem; margin: 0.75rem 0; color: #94a3b8; font-style: italic; }
.markdown-body hr { border-color: #334155; margin: 1rem 0; }
.markdown-body img { border-radius: 0.5rem; max-width: 100%; margin: 0.75rem 0; }
/* highlight.js overrides for dark theme */
.hljs { background: transparent !important; }
</style>