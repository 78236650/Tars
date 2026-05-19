import { describe, expect, it } from 'vitest'
import {
  extractSummarySections,
  normalizeMeetingSummary,
  summaryHasKeyPointsSection,
} from './meetingSummary'

describe('normalizeMeetingSummary', () => {
  it('extracts markdown from multiline python dict repr', () => {
    const raw = `{'content': '## 会议信息
- 主题：测试

## 核心摘要
内容'}`
    const out = normalizeMeetingSummary(raw)
    expect(out).toContain('## 会议信息')
    expect(out).toContain('- 主题：测试')
    expect(out).not.toContain("'content'")
  })

  it('extracts markdown from JSON content field', () => {
    const raw = `{'content': '## 会议信息\\n- 主题：测试\\n\\n## 核心摘要\\n内容'}`
    const out = normalizeMeetingSummary(raw)
    expect(out).toContain('## 会议信息')
    expect(out).toContain('- 主题：测试')
    expect(out).not.toContain("'content'")
  })

  it('passes through clean markdown', () => {
    const md = '## 核心摘要\n\n这是正文。'
    expect(normalizeMeetingSummary(md)).toBe(md)
  })
})

describe('extractSummarySections', () => {
  it('lists h2 headings', () => {
    const md = '## 会议信息\n\n## 核心摘要\n\n正文'
    expect(extractSummarySections(md).map(s => s.title)).toEqual(['会议信息', '核心摘要'])
  })
})

describe('summaryHasKeyPointsSection', () => {
  it('detects embedded key points section', () => {
    expect(summaryHasKeyPointsSection('## 关键要点\n- a')).toBe(true)
    expect(summaryHasKeyPointsSection('## 行动项\n- a')).toBe(false)
  })
})
