import { apiClient } from './index'

export interface QualityRule {
  id: string
  datasource_id: string
  table_name: string
  kind: string
  name: string
  params: Record<string, unknown>
  engine: string
  enabled: boolean
}

export interface RuleResult {
  rule_id: string
  rule_name: string
  kind: string
  engine: string
  passed_count: number
  failed_count: number
  sample_violations: unknown[]
}

export interface CheckRunReport {
  id: string
  datasource_id: string
  table_name: string
  status: string
  total_rows: number
  truncated: boolean
  summary: {
    rule_results: RuleResult[]
    total_passed: number
    total_failed: number
    errors: string[]
  }
}

export const governanceApi = {
  ruleKinds: () =>
    apiClient.get<{ kinds: string[] }>('/governance/rule-kinds').then((r) => r.data.kinds),
  listRules: (datasourceId: string, table?: string) =>
    apiClient
      .get<{ rules: QualityRule[] }>('/governance/rules', {
        params: { datasource_id: datasourceId, table_name: table },
      })
      .then((r) => r.data.rules),
  createRule: (body: Partial<QualityRule>) =>
    apiClient.post<QualityRule>('/governance/rules', body).then((r) => r.data),
  deleteRule: (id: string) =>
    apiClient.delete(`/governance/rules/${id}`).then((r) => r.data),
  validate: (datasourceId: string, table: string) =>
    apiClient
      .post<CheckRunReport>('/governance/validate', null, {
        params: { datasource_id: datasourceId, table_name: table },
      })
      .then((r) => r.data),
}
