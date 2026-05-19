/** Normalize meeting summary text for display (handles legacy bad LLM payloads). */
export function normalizeMeetingSummary(raw: string | null | undefined): string {
  if (!raw?.trim()) return ''

  let text = raw.trim()
  text = unescapeLiteralNewlines(text)

  if (text.startsWith('{')) {
    const parsed = tryParseObject(text)
    if (parsed) {
      for (const key of ['summary', 'content', 'text', 'markdown', 'output']) {
        const val = parsed[key]
        if (typeof val === 'string' && val.trim()) {
          return unescapeLiteralNewlines(val.trim())
        }
      }
    }
  }

  return text
}

function unescapeLiteralNewlines(text: string): string {
  if (!text.includes('\n') && text.includes('\\n')) {
    return text.replace(/\\n/g, '\n').replace(/\\t/g, '\t')
  }
  return text
}

function tryParseObject(text: string): Record<string, unknown> | null {
  try {
    const data = JSON.parse(text)
    return typeof data === 'object' && data !== null ? (data as Record<string, unknown>) : null
  } catch {
    /* fall through */
  }

  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start < 0 || end <= start) return null

  const snippet = text.slice(start, end + 1)
  try {
    const data = JSON.parse(snippet)
    return typeof data === 'object' && data !== null ? (data as Record<string, unknown>) : null
  } catch {
    /* fall through */
  }

  // Python dict repr with multiline content (common LLM mistake)
  const contentMatch = snippet.match(/['"]content['"]\s*:\s*['"]([\s\S]*?)['"]\s*\}?/)
  if (contentMatch?.[1]) {
    return { content: contentMatch[1] }
  }
  const summaryMatch = snippet.match(/['"]summary['"]\s*:\s*['"]([\s\S]*?)['"]\s*[,}]/)
  if (summaryMatch?.[1]) {
    return { summary: summaryMatch[1] }
  }

  return null
}

export interface SummarySection {
  id: string
  title: string
}

/** Split markdown summary into H2 sections for in-page navigation. */
export function extractSummarySections(markdown: string): SummarySection[] {
  const normalized = normalizeMeetingSummary(markdown)
  if (!normalized) return []

  const sections: SummarySection[] = []
  for (const line of normalized.split('\n')) {
    const match = line.match(/^##\s+(.+?)\s*$/)
    if (!match) continue
    const title = match[1].trim()
    sections.push({
      id: slugify(title),
      title,
    })
  }
  return sections
}

export function summaryHasKeyPointsSection(markdown: string): boolean {
  const normalized = normalizeMeetingSummary(markdown)
  return /##\s*(关键要点|Key Points|核心摘要|Executive Summary)/i.test(normalized)
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    || 'section'
}
