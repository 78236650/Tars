import { marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import css from 'highlight.js/lib/languages/css'
import xml from 'highlight.js/lib/languages/xml'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import markdownLang from 'highlight.js/lib/languages/markdown'
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
hljs.registerLanguage('markdown', markdownLang)
hljs.registerLanguage('md', markdownLang)
hljs.registerLanguage('diff', diff)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)

let configured = false

function ensureMarked() {
  if (configured) return
  marked.use(
    markedHighlight({
      langPrefix: 'hljs language-',
      highlight(code: string, lang: string) {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value
        }
        return hljs.highlightAuto(code).value
      },
    }),
  )
  marked.setOptions({
    breaks: true,
    gfm: true,
  })
  configured = true
}

/** 整段被包在单个 ```markdown 围栏里时解开 */
export function unwrapOuterCodeFence(text: string): string {
  const trimmed = text.trim()
  const match = trimmed.match(/^```(?:markdown|md|text)?\s*\n([\s\S]*?)\n```$/i)
  if (match) return match[1].trim()
  return text
}

/** 流式输出时临时闭合未结束的围栏 */
export function closeOpenFences(text: string): string {
  const count = (text.match(/^```/gm) || []).length
  if (count % 2 === 1) return `${text}\n\`\`\``
  return text
}

/** 过长或像正文的片段不应渲染成行内 code */
export function shouldRenderAsInlineCode(code: string): boolean {
  const value = code.trim()
  if (!value) return false
  if (value.length > 72) return false
  if (/[\u4e00-\u9fff]/.test(value) && value.length > 16) return false
  if ((value.match(/[.!?。！？]/g) || []).length >= 2) return false
  if (/\n/.test(value)) return false
  return true
}

/** 将 [ref:doc_id] 或 [ref:doc_id|标题] 转为可点击的知识库引用卡片 */
export function replaceKnowledgeRefs(text: string): string {
  return text.replace(/\[ref:([^\]|]+)(?:\|([^\]]+))?\]/g, (_match, docId: string, docTitle?: string) => {
    const safeId = escapeHtml(docId.trim())
    const label = escapeHtml((docTitle || docId).trim())
    const href = `/knowledge?doc_id=${encodeURIComponent(docId.trim())}`
    return (
      `<a href="${href}" class="knowledge-ref" data-doc-id="${safeId}" data-doc-title="${label}" title="${label}">` +
      `<span class="knowledge-ref-icon">📎</span><span class="knowledge-ref-label">${label}</span></a>`
    )
  })
}

export function normalizeChatMarkdown(text: string, options?: { streaming?: boolean }): string {
  let normalized = text.replace(/\r\n/g, '\n')
  normalized = unwrapOuterCodeFence(normalized)
  normalized = replaceKnowledgeRefs(normalized)
  if (options?.streaming) {
    normalized = closeOpenFences(normalized)
  }
  return normalized
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** 将误解析的超长行内 code 还原为普通文本（保留 pre 内 code） */
export function softenInlineCode(html: string): string {
  const parts = html.split(/(<pre[\s\S]*?<\/pre>)/g)
  return parts
    .map((part) => {
      if (part.startsWith('<pre')) return part
      return part.replace(/<code>([^<]*)<\/code>/g, (full, inner: string) => {
        const decoded = inner
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&amp;/g, '&')
        if (shouldRenderAsInlineCode(decoded)) return full
        return escapeHtml(decoded)
      })
    })
    .join('')
}

export function wrapCodeBlocks(html: string, copyLabel: string): string {
  return html.replace(
    /<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g,
    (_match, attrs: string) => {
      const langMatch = attrs.match(/language-([\w-]+)/)
      const lang = langMatch?.[1] || ''
      const langLabel = lang && lang !== 'text' && lang !== 'plaintext' ? lang : ''
      return (
        '<div class="code-block">' +
        '<div class="code-block-header">' +
        `<span class="code-block-lang">${langLabel}</span>` +
        `<button type="button" class="code-block-copy">${copyLabel}</button>` +
        `</div><pre><code${attrs}>`
      )
    },
  ).replace(/<\/code><\/pre>/g, '</code></pre></div>')
}

export function renderChatMarkdown(
  text: string,
  options?: { streaming?: boolean; copyLabel?: string },
): string {
  if (!text?.trim()) return ''
  ensureMarked()
  const source = normalizeChatMarkdown(text, { streaming: options?.streaming })
  let html = marked.parse(source) as string
  html = softenInlineCode(html)
  html = wrapCodeBlocks(html, options?.copyLabel || 'Copy')
  html = html.replace(/<table>/g, '<div class="table-wrap"><table>').replace(/<\/table>/g, '</table></div>')
  return html
}
