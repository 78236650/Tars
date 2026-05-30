/** 港航调度 UI 元数据 — 面向业务人员，隐藏技术术语 */

export type DispatchMode = 'scenario' | 'guided' | 'advanced'

export interface ScenarioTemplate {
  id: string
  icon: string
  goalTemplate: string
  /** i18n key prefix: orchestration.scenario.{id} */
}

export const SCENARIO_TEMPLATES: ScenarioTemplate[] = [
  {
    id: 'berth_unload',
    icon: 'lucide:anchor',
    goalTemplate: '安排{ship}靠泊卸货，箱量约{boxes}箱',
  },
  {
    id: 'yard_allocate',
    icon: 'lucide:warehouse',
    goalTemplate: '为{ship}分配堆场箱位，箱量约{boxes}箱',
  },
  {
    id: 'vessel_check',
    icon: 'lucide:ship',
    goalTemplate: '确认{ship}船舶动态与到港时间',
  },
]

export interface AgentMeta {
  labelKey: string
  icon: string
  accentClass: string
}

export const AGENT_META: Record<string, AgentMeta> = {
  berth: {
    labelKey: 'orchestration.agent.berth',
    icon: 'lucide:anchor',
    accentClass: 'border-sky-500/30 bg-sky-500/10 text-sky-200',
  },
  yard: {
    labelKey: 'orchestration.agent.yard',
    icon: 'lucide:warehouse',
    accentClass: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  },
  vessel: {
    labelKey: 'orchestration.agent.vessel',
    icon: 'lucide:ship',
    accentClass: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  },
  research: {
    labelKey: 'orchestration.agent.research',
    icon: 'lucide:search',
    accentClass: 'border-border bg-surface-3 text-content-muted',
  },
  plan: {
    labelKey: 'orchestration.agent.plan',
    icon: 'lucide:list-checks',
    accentClass: 'border-border bg-surface-3 text-content-muted',
  },
}

export function agentMeta(type: string): AgentMeta {
  return (
    AGENT_META[type] ?? {
      labelKey: 'orchestration.agent.other',
      icon: 'lucide:bot',
      accentClass: 'border-border bg-surface-3 text-content-muted',
    }
  )
}

export function fillScenarioGoal(
  template: string,
  vars: { ship: string; boxes: string; berth?: string },
): string {
  return template
    .replace('{ship}', vars.ship.trim() || '目标船舶')
    .replace('{boxes}', vars.boxes.trim() || '若干')
    .replace('{berth}', vars.berth?.trim() || '')
}

export function buildGuidedGoal(fields: {
  ship: string
  boxes: string
  berth: string
  eta: string
  jobType: string
}): string {
  const parts: string[] = [`安排${fields.ship.trim() || '目标航次'}`]
  if (fields.berth.trim()) {
    parts.push(`靠${fields.berth.trim()}`)
  } else {
    parts.push('靠泊')
  }
  if (fields.jobType === 'unload') {
    parts.push('卸货')
  } else if (fields.jobType === 'load') {
    parts.push('装货')
  }
  if (fields.boxes.trim()) {
    parts.push(`${fields.boxes.trim()}箱`)
  }
  if (fields.eta.trim()) {
    parts.push(`预计到港${fields.eta.trim()}`)
  }
  return parts.join('')
}

/** 将共享黑板 JSON 转为业务可读摘要行 */
export function formatSharedSummary(shared: Record<string, unknown>): { key: string; text: string }[] {
  const rows: { key: string; text: string }[] = []
  const berth = shared.berth as Record<string, unknown> | undefined
  if (berth?.recommendation) {
    rows.push({ key: 'berth', text: String(berth.recommendation) })
  }
  const vessel = shared.vessel as Record<string, unknown> | undefined
  if (vessel?.status) {
    rows.push({ key: 'vessel', text: String(vessel.status) })
  }
  const yard = shared.yard as Record<string, unknown> | undefined
  if (yard?.allocation) {
    rows.push({ key: 'yard', text: String(yard.allocation) })
  }
  return rows
}
