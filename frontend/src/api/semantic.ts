import { apiClient } from './index'

export interface GlossaryTerm {
  id: string
  term: string
  definition: string
  domain: string
  aliases?: string[]
}

export interface FieldSemantic {
  id: string
  datasource_id: string
  table_name: string
  column_name: string
  term_id: string | null
  suggested_term: string | null
  confidence: number
  status: string
}

export const semanticApi = {
  listTerms: (domain?: string) =>
    apiClient
      .get<{ terms: GlossaryTerm[] }>('/semantic/terms', { params: domain ? { domain } : {} })
      .then((r) => r.data.terms),
  createTerm: (body: { term: string; definition: string; domain?: string; aliases?: string[] }) =>
    apiClient.post('/semantic/terms', body).then((r) => r.data),
  deleteTerm: (id: string) =>
    apiClient.delete(`/semantic/terms/${id}`).then((r) => r.data),
  listFieldSemantics: (datasourceId: string, table?: string, status?: string) =>
    apiClient
      .get<{ items: FieldSemantic[] }>('/semantic/field-semantics', {
        params: { datasource_id: datasourceId, table_name: table, status },
      })
      .then((r) => r.data.items),
  suggestBindings: (body: { datasource_id: string; table_name: string; columns: string[] }) =>
    apiClient.post('/semantic/field-semantics/suggest', body).then((r) => r.data),
  confirmBinding: (fieldId: string, termId: string) =>
    apiClient.post(`/semantic/field-semantics/${fieldId}/confirm`, { term_id: termId }).then((r) => r.data),
}
