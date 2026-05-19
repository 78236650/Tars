import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

/** Render Markdown to HTML for v-html (caller must sanitize trust boundary). */
export function renderMarkdown(text: string): string {
  if (!text?.trim()) return ''
  return marked.parse(text) as string
}
