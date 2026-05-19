import { describe, expect, it } from 'vitest'
import {
  closeOpenFences,
  renderChatMarkdown,
  replaceKnowledgeRefs,
  shouldRenderAsInlineCode,
  softenInlineCode,
  unwrapOuterCodeFence,
} from './chatMarkdown'

describe('chatMarkdown', () => {
  it('unwraps outer markdown fence', () => {
    const input = '```markdown\n# Title\n\nHello world\n```'
    expect(unwrapOuterCodeFence(input)).toBe('# Title\n\nHello world')
  })

  it('closes open fence while streaming', () => {
    expect(closeOpenFences('```python\nprint(1)')).toContain('```')
  })

  it('does not treat long prose as inline code', () => {
    expect(shouldRenderAsInlineCode('这是一段比较长的中文说明，用于解释当前步骤。')).toBe(false)
    expect(shouldRenderAsInlineCode('npm install')).toBe(true)
  })

  it('softens over-long inline code in html', () => {
    const html = '<p><code>这是一段比较长的中文说明，用于解释当前步骤与注意事项。</code></p>'
    expect(softenInlineCode(html)).not.toContain('<code>')
    expect(softenInlineCode(html)).toContain('中文说明')
  })

  it('renders fenced code with language label', () => {
    const html = renderChatMarkdown('```js\nconsole.log(1)\n```', { copyLabel: '复制' })
    expect(html).toContain('code-block')
    expect(html).toContain('code-block-lang">js')
    expect(html).toContain('hljs')
    expect(html.replace(/<[^>]+>/g, '')).toContain('console.log(1)')
  })

  it('preserves SQL body inside code block wrapper', () => {
    const sql = 'SELECT SUM(amount) FROM orders WHERE status = 1'
    const html = renderChatMarkdown(`\`\`\`sql\n${sql}\n\`\`\``, { copyLabel: '复制' })
    expect(html).toContain('code-block-pre')
    expect(html.replace(/<[^>]+>/g, '')).toContain(sql)
  })

  it('renders knowledge ref citations with optional title', () => {
    const html = renderChatMarkdown('根据 [ref:doc1|会议纪要] 可知。')
    expect(html).toContain('knowledge-ref')
    expect(html).toContain('会议纪要')
    expect(html).toContain('data-doc-id="doc1"')
  })

  it('renders knowledge ref citations as links', () => {
    const html = renderChatMarkdown('根据会议纪要 [ref:doc_meeting_1] 可知。')
    expect(html).toContain('knowledge-ref')
    expect(html).toContain('doc_meeting_1')
    expect(html).toContain('/knowledge?doc_id=doc_meeting_1')
  })

  it('replaceKnowledgeRefs handles doc ids', () => {
    expect(replaceKnowledgeRefs('[ref:abc-123]')).toContain('data-doc-id="abc-123"')
  })
})
