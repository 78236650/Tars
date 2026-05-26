import axios from 'axios'
import type {
  User,
  UserListResponse,
  LoginResult,
  Personality,
  PersonalityResponse,
  MemoryItem,
  MemoryStats,
  CoreMemoryBlocksResponse,
  RecentMemoryResponse,
  LongtermMemoryResponse,
  MemoryCompressionStatus,
  MemoryMergeResponse,
  MemoryTreeResponse,
  MemoryTreeSearchResponse,
  MemoryEntityGraphResponse,
  EntityRelationsResponse,
  SubAgent,
  SubAgentListResponse,
  SubAgentConfig,
  ApiResponse,
  ChatSession,
  ChatHistoryMessage,
  Endpoint,
  ModelsOverviewResponse,
  ModelSwitchBody,
  ModelSwitchResult,
  DataSource,
  DataSourceConnectionInput,
  BIQueryResult,
  BIChartResult,
  ReminderNotification,
  ReminderNotificationListData,
  KnowledgeCollection,
  KnowledgeDocument,
  KnowledgeSearchResult,
  DocProfile,
  DocumentStatusResponse,
  DocumentPassage,
  Transcription,
  TranscriptionListData,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  // 模型列表 / 切换、大文件等可能超过 10s；过短会表现为「模型连不上」
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('apiKey')
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  // v4.0.2: 发送用户 ID 作为 tenant_id 实现多租户隔离
  const userJson = localStorage.getItem('auth_user')
  if (userJson) {
    try {
      const user = JSON.parse(userJson)
      if (user?.id) {
        config.headers['X-Tenant-ID'] = user.id
        config.headers['X-User-Role'] = user.role || 'user'
      }
    } catch {}
  }
  return config
})

export const authApi = {
  login: async (identifier: string, password: string): Promise<LoginResult> => {
    const response = await api.post<ApiResponse<LoginResult>>('/auth/login', {
      identifier,
      password,
    })
    return response.data.data as LoginResult
  },

  getCurrentUser: async (apiKey?: string): Promise<User> => {
    const params = apiKey ? { api_key: apiKey } : undefined
    const response = await api.get<User>('/users/me', { params })
    return response.data
  },
  
  getUsers: async (): Promise<UserListResponse> => {
    const response = await api.get<UserListResponse>('/users')
    return response.data
  },
  
  createUser: async (
    username: string,
    email: string,
    password: string,
    role: string = 'user'
  ): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>('/users', { username, email, password, role })
    return response.data
  },
  
  updateUser: async (userId: string, data: Partial<User>): Promise<ApiResponse> => {
    const response = await api.put<ApiResponse>(`/users/${userId}`, data)
    return response.data
  },
  
  deleteUser: async (userId: string): Promise<ApiResponse> => {
    const response = await api.delete<ApiResponse>(`/users/${userId}`)
    return response.data
  }
}

export const personalityApi = {
  getPersonality: async (): Promise<PersonalityResponse> => {
    const response = await api.get<PersonalityResponse>('/personality')
    return response.data
  },
  
  updatePersonality: async (data: {
    parameters?: Partial<Personality['parameters']>
    communication_style?: string
    behavior_rules?: string[]
  }): Promise<PersonalityResponse> => {
    const response = await api.put<PersonalityResponse>('/personality', data)
    return response.data
  }
}

export const memoryApi = {
  getStats: async (): Promise<MemoryStats> => {
    const response = await api.get<MemoryStats>('/memory/stats')
    return response.data
  },

  getCoreBlocks: async (): Promise<CoreMemoryBlocksResponse> => {
    const response = await api.get<CoreMemoryBlocksResponse>('/memory/core')
    return response.data
  },

  updateCoreBlock: async (block: string, content: string): Promise<{ success: boolean; block: string; content: string }> => {
    const response = await api.put<{ success: boolean; block: string; content: string }>(`/memory/core/${block}`, { content })
    return response.data
  },

  getRecent: async (params?: { page?: number; q?: string; cat?: string }): Promise<RecentMemoryResponse> => {
    const response = await api.get<RecentMemoryResponse>('/memory/recent', { params })
    return response.data
  },

  getAll: async (params?: { page?: number; q?: string; cat?: string; memory_type?: string }): Promise<RecentMemoryResponse> => {
    const response = await api.get<RecentMemoryResponse>('/memory/all', { params })
    return response.data
  },

  getLongterm: async (params?: { page?: number; group_by?: string }): Promise<LongtermMemoryResponse> => {
    const response = await api.get<LongtermMemoryResponse>('/memory/longterm', { params })
    return response.data
  },

  getTree: async (params?: {
    view?: 'entity' | 'provenance'
    max_per_bucket?: number
    include_core?: boolean
    include_orphan?: boolean
    user_id?: string
  }): Promise<MemoryTreeResponse> => {
    const response = await api.get<MemoryTreeResponse>('/memory/tree', { params })
    return response.data
  },

  getTreeRelations: async (entityId: string, userId?: string): Promise<EntityRelationsResponse> => {
    const response = await api.get<EntityRelationsResponse>('/memory/tree/relations', {
      params: { entity_id: entityId, user_id: userId || undefined },
    })
    return response.data
  },

  searchTree: async (params: {
    q: string
    limit?: number
    view?: 'entity' | 'provenance'
    user_id?: string
  }): Promise<MemoryTreeSearchResponse> => {
    const response = await api.get<MemoryTreeSearchResponse>('/memory/tree/search', { params })
    return response.data
  },

  getTreeGraph: async (userId?: string): Promise<MemoryEntityGraphResponse> => {
    const response = await api.get<MemoryEntityGraphResponse>('/memory/tree/graph', {
      params: { user_id: userId || undefined },
    })
    return response.data
  },

  getMemory: async (id: string): Promise<MemoryItem> => {
    const response = await api.get<MemoryItem>(`/memory/${id}`)
    return response.data
  },

  updateMemory: async (id: string, content: string): Promise<MemoryItem> => {
    const response = await api.put<MemoryItem>(`/memory/${id}`, { content })
    return response.data
  },

  deleteMemory: async (id: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(`/memory/${id}`)
    return response.data
  },

  pinMemory: async (id: string, pinned: boolean): Promise<{ success: boolean; pinned: boolean }> => {
    const response = await api.post<{ success: boolean; pinned: boolean }>(`/memory/${id}/pin`, { pinned })
    return response.data
  },

  promoteMemory: async (id: string): Promise<MemoryItem> => {
    const response = await api.post<MemoryItem>(`/memory/${id}/promote`)
    return response.data
  },

  compressAll: async (): Promise<{ status: string; compressed_count: number; cleaned_count?: number }> => {
    const response = await api.post<{ status: string; compressed_count: number; cleaned_count?: number }>('/memory/compress')
    return response.data
  },

  getCompressStatus: async (): Promise<MemoryCompressionStatus> => {
    const response = await api.get<MemoryCompressionStatus>('/memory/compress/status')
    return response.data
  },

  mergeMemories: async (memoryIds: string[], previewOnly: boolean): Promise<MemoryMergeResponse> => {
    const response = await api.post<MemoryMergeResponse>('/memory/merge', {
      memory_ids: memoryIds,
      preview_only: previewOnly,
    })
    return response.data
  },

  extractFromTurn: async (payload: {
    user_content: string
    assistant_content: string
  }): Promise<{ items: Array<{ content: string; category: string; importance: number }> }> => {
    const response = await api.post<{ items: Array<{ content: string; category: string; importance: number }> }>(
      '/memory/extract-from-turn',
      payload,
    )
    return response.data
  },

  saveFromTurn: async (payload: {
    items: Array<{ content: string; category: string; importance?: number }>
    user_context?: string
    publish_to_knowledge?: boolean
    promotion_group_id?: string
  }): Promise<{
    saved: MemoryItem[]
    skipped: number
    knowledge_doc_ids?: string[]
    promotion_group_id?: string
    promotion_trigger?: string
  }> => {
    const response = await api.post<{
      saved: MemoryItem[]
      skipped: number
      knowledge_doc_ids?: string[]
      promotion_group_id?: string
      promotion_trigger?: string
    }>('/memory/save-from-turn', payload)
    return response.data
  },

  exportMemories: async (tenantId?: string) => {
    const response = await api.get('/memory/export', {
      params: tenantId ? { user_id: tenantId } : undefined,
    })
    return response.data
  },
}

export const subagentApi = {
  getSubagents: async (): Promise<SubAgentListResponse> => {
    const response = await api.get<SubAgentListResponse>('/subagents')
    return response.data
  },
  
  getSubagent: async (agentType: string): Promise<ApiResponse<SubAgent>> => {
    const response = await api.get<ApiResponse<SubAgent>>(`/subagents/${agentType}`)
    return response.data
  },
  
  updateSubagent: async (agentType: string, config: SubAgentConfig): Promise<ApiResponse> => {
    const response = await api.put<ApiResponse>(`/subagents/${agentType}`, config)
    return response.data
  },
  
  invokeSubagent: async (agentType: string, task: string): Promise<ApiResponse<{ result: string }>> => {
    const response = await api.post<ApiResponse<{ result: string }>>(`/subagents/${agentType}/invoke`, { task })
    return response.data
  }
}

export const modelApi = {
  getModelsOverview: async (): Promise<ModelsOverviewResponse> => {
    const response = await api.get<ModelsOverviewResponse>('/models/')
    return response.data
  },

  switchModel: async (body: ModelSwitchBody): Promise<ModelSwitchResult> => {
    const response = await api.post<ModelSwitchResult>('/models/switch', {
      provider: body.provider,
      model: body.model,
      endpoint_id: body.endpoint_id ?? undefined,
    })
    return response.data
  },

  listEndpoints: async (): Promise<Endpoint[]> => {
    const response = await api.get<Endpoint[]>('/models/endpoints')
    return response.data
  },

  createEndpoint: async (data: {
    name: string
    base_url: string
    api_key?: string
  }): Promise<Endpoint> => {
    const response = await api.post<Endpoint>('/models/endpoints', data)
    return response.data
  },

  updateEndpoint: async (
    id: string,
    data: Partial<{
      name: string
      base_url: string
      api_key: string
      models: string[]
      enabled: boolean
    }>
  ): Promise<Endpoint> => {
    const response = await api.put<Endpoint>(`/models/endpoints/${id}`, data)
    return response.data
  },

  deleteEndpoint: async (id: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(`/models/endpoints/${id}`)
    return response.data
  },

  fetchEndpointModels: async (
    id: string
  ): Promise<{ success: boolean; models: string[]; changed: boolean }> => {
    const response = await api.post(`/models/endpoints/${id}/fetch-models`)
    return response.data
  },

  testEndpoint: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.post(`/models/endpoints/${id}/test`)
    return response.data
  },
}

export default api

// ========= Tools & Skills v2 API =========

export const toolsApi = {
  listTools: () => api.get('/tools/'),
  getToolDetail: (id: string) => api.get(`/tools/${id}`),
  updateToolConfig: (id: string, config: any) => api.put(`/tools/${id}/config`, { config }),
  toggleToolStatus: (id: string, status: string) => api.put(`/tools/${id}/status`, { status }),
  executeTool: (toolName: string, parameters: any) => api.post('/tools/execute', { tool_name: toolName, parameters }),
}

export const skillsApi = {
  listSkills: () => api.get('/skills/'),
  getSkill: (id: string) => api.get(`/skills/${id}`),
  createPromptSkill: (data: any) => api.post('/skills/create-prompt', data),
  deleteSkill: (id: string) => api.delete(`/skills/${id}`),
  enableSkill: (id: string) => api.put(`/skills/${id}/enable`),
  disableSkill: (id: string) => api.put(`/skills/${id}/disable`),
  reload: () => api.post('/skills/reload'),
  // v4.0.0: 技能统计
  getStats: () => api.get('/skills/stats'),
  getPendingArchive: (days = 30) => api.get('/skills/pending-archive', { params: { days } }),
  archive: (id: string) => api.put(`/skills/${id}/archive`),
  activate: (id: string) => api.put(`/skills/${id}/activate`),
}

export const skillhubApi = {
  getCatalog: () => api.get('/skillhub/catalog'),
  search: (query: string) => api.get('/skillhub/search', { params: { q: query } }),
  getDetail: (id: string) => api.get(`/skillhub/detail/${id}`),
  install: (
    skillId: string,
    options?: { confirmPermissions?: boolean; skipDependencyCheck?: boolean; scope?: 'tenant' | 'global' },
  ) =>
    api.post('/skillhub/install', {
      skill_id: skillId,
      confirm_permissions: options?.confirmPermissions ?? true,
      skip_dependency_check: options?.skipDependencyCheck ?? false,
      scope: options?.scope,
    }),
  uninstall: (skillId: string) => api.post('/skillhub/uninstall', { skill_id: skillId }),
  listInstalled: () => api.get('/skillhub/installed'),
  checkUpdates: () => api.get('/skillhub/updates'),
}

export const sessionsApi = {
  list: async (): Promise<ChatSession[]> => {
    const response = await api.get<ChatSession[]>('/sessions/')
    return response.data
  },

  create: async (): Promise<ChatSession> => {
    const response = await api.post<ChatSession>('/sessions/')
    return response.data
  },

  getMessages: async (id: string): Promise<ChatHistoryMessage[]> => {
    const response = await api.get<ChatHistoryMessage[]>(`/sessions/${id}/messages`)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/sessions/${id}`)
  },

  updateTitle: async (id: string, title: string): Promise<void> => {
    await api.patch(`/sessions/${id}`, { title })
  },
}

export const reminderNotificationsApi = {
  list: async (params?: { limit?: number; offset?: number }): Promise<ReminderNotificationListData> => {
    const response = await api.get<ApiResponse<ReminderNotificationListData>>('/reminder-notifications', { params })
    return response.data.data as ReminderNotificationListData
  },

  getDetail: async (id: string): Promise<ReminderNotification> => {
    const response = await api.get<ApiResponse<ReminderNotification>>(`/reminder-notifications/${id}`)
    return response.data.data as ReminderNotification
  },

  markRead: async (id: string): Promise<ReminderNotification> => {
    const response = await api.post<ApiResponse<ReminderNotification>>(`/reminder-notifications/${id}/read`)
    return response.data.data as ReminderNotification
  },
}

export const approvalsApi = {
  approve: async (approvalId: string): Promise<{ success: boolean; approval_id: string; status: string }> => {
    const response = await api.post(`/approvals/${approvalId}/approve`)
    return response.data
  },

  deny: async (approvalId: string): Promise<{ success: boolean; approval_id: string; status: string }> => {
    const response = await api.post(`/approvals/${approvalId}/deny`)
    return response.data
  },
}

export const plansApi = {
  list: async (): Promise<{ plans: Record<string, unknown>[] }> => {
    const response = await api.get('/plans')
    return response.data
  },

  get: async (planId: string): Promise<Record<string, unknown>> => {
    const response = await api.get(`/plans/${planId}`)
    return response.data
  },

  approve: async (
    planId: string,
    steps?: Record<string, unknown>[],
  ): Promise<{ success: boolean; plan_id: string; status: string }> => {
    const response = await api.post(`/plans/${planId}/approve`, { steps })
    return response.data
  },

  reject: async (planId: string): Promise<{ success: boolean; plan_id: string; status: string }> => {
    const response = await api.post(`/plans/${planId}/reject`)
    return response.data
  },

  retry: async (planId: string): Promise<{ success: boolean; plan_id: string; status: string }> => {
    const response = await api.post(`/plans/${planId}/retry`)
    return response.data
  },
}

export const handoffsApi = {
  accept: async (handoffId: string): Promise<{ success: boolean; handoff_id: string; status: string }> => {
    const response = await api.post(`/handoffs/${handoffId}/accept`)
    return response.data
  },

  reject: async (handoffId: string): Promise<{ success: boolean; handoff_id: string; status: string }> => {
    const response = await api.post(`/handoffs/${handoffId}/reject`)
    return response.data
  },
}

// ========= BI Analytics API =========

export const biApi = {
  listDataSources: async (): Promise<{ datasources: DataSource[] }> => {
    const response = await api.get('/datasources/')
    return response.data
  },

  getDataSource: async (id: string): Promise<DataSource> => {
    const response = await api.get(`/datasources/${id}`)
    return response.data
  },

  createDataSource: async (data: DataSourceConnectionInput & { name: string }): Promise<{ success: boolean; datasource: DataSource }> => {
    const response = await api.post('/datasources/', data)
    return response.data
  },

  updateDataSource: async (id: string, data: Partial<DataSourceConnectionInput & { name: string }>): Promise<{ success: boolean; datasource: DataSource }> => {
    const response = await api.put(`/datasources/${id}`, data)
    return response.data
  },

  testConnectionConfig: async (data: DataSourceConnectionInput): Promise<{ success: boolean; message: string }> => {
    const response = await api.post('/datasources/test-config', data)
    return response.data
  },

  deleteDataSource: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/datasources/${id}`)
    return response.data
  },

  testConnection: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.post(`/datasources/${id}/test`)
    return response.data
  },

  refreshSchema: async (id: string): Promise<{ success: boolean; schema_snapshot: Record<string, any> }> => {
    const response = await api.post(`/datasources/${id}/refresh-schema`)
    return response.data
  },

  updateAnnotations: async (id: string, annotations: Record<string, any>): Promise<{ success: boolean; schema_annotations: Record<string, any> }> => {
    const response = await api.put(`/datasources/${id}/annotations`, { annotations })
    return response.data
  },

  executeQuery: async (id: string, sql: string): Promise<BIQueryResult> => {
    const response = await api.post(`/datasources/${id}/query`, { sql })
    return response.data
  },

  generateChart: async (id: string, sql: string, chart_type?: string, user_question?: string): Promise<BIChartResult> => {
    const response = await api.post(`/datasources/${id}/chart`, { sql, chart_type, user_question })
    return response.data
  },
}

// ========= InsightForge 鉴数 API =========

export interface InsightProfileRunSummary {
  id: string
  status: string
  capability_version?: string
  progress?: Record<string, unknown>
  error?: string | null
  created_at?: string
  finished_at?: string | null
}

export interface InsightLlmSettingsPayload {
  use_chat_default: boolean
  provider?: 'ollama' | 'openai_compatible'
  model?: string
  endpoint_id?: string | null
}

export interface InsightLlmSettingsResponse {
  settings: InsightLlmSettingsPayload
  chat_current: {
    provider: string
    endpoint_id?: string | null
    model: string
    label?: string
    endpoint_name?: string | null
  }
  effective: {
    label: string
    source: string
    selection: Record<string, unknown>
  }
}

export const insightApi = {
  version: async (): Promise<Record<string, unknown>> => {
    const response = await api.get('/insight/version')
    return response.data
  },

  getLlmOptions: async (): Promise<ModelsOverviewResponse> => {
    const response = await api.get('/insight/llm/options')
    return response.data
  },

  getLlmSettings: async (): Promise<InsightLlmSettingsResponse> => {
    const response = await api.get('/insight/llm/settings')
    return response.data
  },

  saveLlmSettings: async (
    body: InsightLlmSettingsPayload
  ): Promise<InsightLlmSettingsResponse & { success: boolean }> => {
    const response = await api.put('/insight/llm/settings', body)
    return response.data
  },

  startProfile: async (
    datasourceId: string,
    options?: {
      force?: boolean
      llm?: InsightLlmSettingsPayload & { persist?: boolean }
      pending_question?: string
      session_id?: string
    }
  ): Promise<{ success: boolean; run_id: string; status: string }> => {
    const response = await api.post(`/insight/datasources/${datasourceId}/profile`, {
      force: options?.force ?? false,
      llm: options?.llm,
      pending_question: options?.pending_question,
      session_id: options?.session_id,
    })
    return response.data
  },

  startForge: async (
    datasourceId: string,
    options?: {
      force?: boolean
      pending_question?: string
      session_id?: string
    }
  ): Promise<{ success: boolean; run_id: string; status: string }> => {
    const response = await api.post(`/insight/datasources/${datasourceId}/forge`, {
      force: options?.force ?? false,
      pending_question: options?.pending_question,
      session_id: options?.session_id,
    })
    return response.data
  },

  listProfileRuns: async (
    datasourceId: string
  ): Promise<{ runs: InsightProfileRunSummary[] }> => {
    const response = await api.get(`/insight/datasources/${datasourceId}/profile/runs`)
    return response.data
  },

  getProfileRun: async (runId: string): Promise<InsightProfileRunSummary & { insight_snapshot?: unknown }> => {
    const response = await api.get(`/insight/profile/runs/${runId}`)
    return response.data
  },

  getDatasourceBrief: async (datasourceId: string): Promise<InsightDatasourceBrief> => {
    const response = await api.get(`/insight/datasources/${datasourceId}/brief`)
    return response.data
  },

  getWorkflow: async (
    datasourceId: string,
    sessionId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.get(`/insight/datasources/${datasourceId}/workflow`, {
      params: sessionId ? { session_id: sessionId } : undefined,
    })
    return response.data
  },

  ask: async (
    datasourceId: string,
    body: {
      question: string
      candidate_metric_keys?: string[]
      as_of_date?: string
      session_id?: string
    },
    config?: { signal?: AbortSignal },
  ): Promise<InsightMetricAnswer> => {
    const response = await api.post(`/insight/datasources/${datasourceId}/ask`, body, config)
    return response.data
  },

  feedback: async (
    questionLogId: string,
    score: number
  ): Promise<{ success: boolean; downgraded?: boolean }> => {
    const response = await api.post(`/insight/ask/${questionLogId}/feedback`, {
      feedback: score,
    })
    return response.data
  },

  adoptMetric: async (options: {
    metric_id?: string
    question_log_id?: string
    definition?: string
    sql_template?: string
  }): Promise<{ success: boolean; metric?: Record<string, unknown> }> => {
    const { metric_id, ...rest } = options
    if (metric_id) {
      const response = await api.post(`/insight/metrics/${metric_id}/adopt`, rest)
      return response.data
    }
    const response = await api.post('/insight/metrics/adopt', options)
    return response.data
  },
}

export interface InsightWorkflowState {
  datasource_state: string
  session_state: string
  show_workflow_strip: boolean
  block_reason?: string | null
  forge_progress?: {
    phase?: string
    percent?: number
    message?: string
    run_id?: string
  } | null
  pending_question?: { text: string; session_id?: string }
  datasource_id?: string
  datasource_name?: string
}

export interface InsightMetricCitation {
  doc_id: string
  title: string
  snippet: string
  source_type: string
  relevance: number
}

export interface InsightMetricAnswer {
  value: number | string | null
  unit?: string
  caliber_tier: 'official' | 'suggested' | 'adhoc'
  metric_key?: string
  definition: string
  sql: string
  filters_summary: string
  as_of?: string
  lag_seconds?: number
  confidence: number
  branch: string
  reasoning?: string
  open_questions?: string[]
  candidates?: string[]
  error?: { code: string; message: string }
  question_log_id?: string
  metric_id?: string
  citations?: InsightMetricCitation[]
}

export interface InsightDatasourceBrief {
  datasource: {
    id: string
    name: string
    db_type: string
    table_count: number
    annotation_count: number
  }
  latest_run: InsightProfileRunSummary | null
  insight_snapshot: Record<string, unknown>
  schema_annotations: Record<string, unknown>
  metrics: Array<{
    id: string
    metric_key: string
    display_name: string
    definition: string
    status: string
    confidence?: number
  }>
  open_questions: string[]
  llm_errors?: string[]
  llm_status?: string
  llm_used?: Record<string, unknown>
  phase: {
    profile: boolean
    metric_qa_in_chat: boolean
    workbench: boolean | string
  }
}

// ========= Knowledge Base API =========

export const knowledgeApi = {
  listCollections: async (): Promise<{ collections: KnowledgeCollection[] }> => {
    const response = await api.get('/knowledge/collections')
    return response.data
  },

  createCollection: async (data: { name: string; description?: string; default_doc_type?: string }): Promise<{ success: boolean; collection: KnowledgeCollection }> => {
    const response = await api.post('/knowledge/collections', data)
    return response.data
  },

  deleteCollection: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/knowledge/collections/${id}`)
    return response.data
  },

  listDocuments: async (collectionId: string): Promise<{ documents: KnowledgeDocument[] }> => {
    const response = await api.get(`/knowledge/collections/${collectionId}/documents`)
    return response.data
  },

  uploadDocument: async (collectionId: string, file: File, docType?: string): Promise<{ success: boolean; document: KnowledgeDocument }> => {
    const formData = new FormData()
    formData.append('file', file)
    if (docType) {
      formData.append('doc_type', docType)
    }
    const response = await api.post(`/knowledge/collections/${collectionId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  getDocumentProfile: async (collectionId: string, docId: string): Promise<DocProfile> => {
    const response = await api.get(`/knowledge/collections/${collectionId}/documents/${docId}/profile`)
    return response.data
  },

  getDocumentStatus: async (collectionId: string, docId: string): Promise<DocumentStatusResponse> => {
    const response = await api.get(`/knowledge/collections/${collectionId}/documents/${docId}/status`)
    return response.data
  },

  getDocumentPassages: async (
    collectionId: string,
    docId: string,
    sectionId?: string,
  ): Promise<{ doc_id: string; section_id?: string | null; passages: DocumentPassage[] }> => {
    const params = sectionId ? { section_id: sectionId } : undefined
    const response = await api.get(`/knowledge/collections/${collectionId}/documents/${docId}/passages`, { params })
    return response.data
  },

  reEnrichDocument: async (collectionId: string, docId: string): Promise<{ success: boolean; doc_id: string; status: string }> => {
    const response = await api.post(`/knowledge/collections/${collectionId}/documents/${docId}/re-enrich`)
    return response.data
  },

  deleteDocument: async (collectionId: string, docId: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/knowledge/collections/${collectionId}/documents/${docId}`)
    return response.data
  },

  search: async (query: string, collectionIds?: string[], top_k?: number, mode?: string): Promise<{ query: string; mode?: string; results: KnowledgeSearchResult[]; total: number }> => {
    const response = await api.post('/knowledge/search', { query, collection_ids: collectionIds, top_k, mode: mode || 'chat' })
    return response.data
  },

  queryCollection: async (collectionId: string, query: string, top_k?: number, mode?: string): Promise<{ query: string; collection_id: string; mode?: string; results: KnowledgeSearchResult[]; total: number }> => {
    const response = await api.post(`/knowledge/collections/${collectionId}/query`, { query, top_k, mode: mode || 'chat' })
    return response.data
  },

  reindexEstimate: async (collectionId: string, docIds?: string[]): Promise<{ doc_count: number; est_tokens: number; require_confirm: boolean; doc_ids: string[] }> => {
    const response = await api.post(`/knowledge/collections/${collectionId}/reindex/estimate`, { doc_ids: docIds })
    return response.data
  },

  reindexCollection: async (collectionId: string, options?: { doc_ids?: string[]; confirm?: boolean }): Promise<{ success: boolean; scheduled: number; status: string }> => {
    const response = await api.post(`/knowledge/collections/${collectionId}/reindex`, {
      doc_ids: options?.doc_ids,
      confirm: options?.confirm ?? false,
    })
    return response.data
  },

  resolveRef: async (docId: string): Promise<{ doc_id: string; title: string; snippet: string; collection_id?: string; source_type?: string }> => {
    const response = await api.get(`/knowledge/ref/${encodeURIComponent(docId)}`)
    return response.data
  },
}

// ========= Meeting Voice Recognition API =========

export const meetingApi = {
  upload: async (file: File, language?: string): Promise<{ success: boolean; transcription: Transcription }> => {
    const formData = new FormData()
    formData.append('file', file)
    if (language) {
      formData.append('language', language)
    }
    const response = await api.post('/meeting/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  transcribe: async (filePath: string, language?: string): Promise<{ success: boolean; transcription: Transcription }> => {
    const response = await api.post('/meeting/transcribe', { file_path: filePath, language })
    return response.data
  },

  summarize: async (transcriptionId: string): Promise<{ success: boolean; transcription: Transcription }> => {
    const response = await api.post('/meeting/summarize', { transcription_id: transcriptionId })
    return response.data
  },

  getStatus: async (id: string): Promise<{ success: boolean; transcription: Transcription }> => {
    const response = await api.get(`/meeting/status/${id}`)
    return response.data
  },

  listHistory: async (limit?: number, offset?: number): Promise<TranscriptionListData> => {
    const response = await api.get('/meeting/history', { params: { limit, offset } })
    return response.data
  },

  delete: async (id: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/meeting/${id}`)
    return response.data
  },

  fetchAudio: async (transcriptionId: string): Promise<Blob> => {
    const response = await api.get(`/meeting/${transcriptionId}/audio`, {
      responseType: 'blob',
    })
    return response.data
  },

  approveToKnowledge: async (id: string, summary: string, keyPoints: string[]): Promise<{ success: boolean; message: string; knowledge_doc_id: string }> => {
    const response = await api.post(`/meeting/${id}/approve-to-knowledge`, { summary, key_points: keyPoints })
    return response.data
  },

  updateSummary: async (id: string, summary: string, keyPoints: string[]): Promise<{ success: boolean }> => {
    const response = await api.put(`/meeting/${id}/summary`, { summary, key_points: keyPoints })
    return response.data
  },

  getPromptTemplates: async (): Promise<{
    templates: Array<{ id: string; name: string; description: string; prompt: string; is_default?: boolean }>
    custom_prompt?: string
    active_template: string
  }> => {
    const response = await api.get('/meeting/settings/templates')
    return response.data
  },

  getAsrSettings: async (): Promise<{
    backend: string
    configured_backend?: string
    model: string
    whisper_model: string
    whisper_model_options: Array<{ id: string; label: string }>
    language_default: string
    output_script: string
    realtime_mode?: string
    preprocess_enabled?: boolean
    language_options: Array<{ id: string; label: string }>
  }> => {
    const response = await api.get('/meeting/settings/asr')
    return response.data
  },

  setAsrSettings: async (payload: {
    whisper_model: string
  }): Promise<{ success: boolean; message?: string; whisper_model?: string; model?: string }> => {
    const response = await api.put('/meeting/settings/asr', payload)
    return response.data
  },

  getModelSettings: async (): Promise<{ provider: string; model: string; endpoint_id?: string | null; source?: string }> => {
    const response = await api.get('/meeting/settings/model')
    return response.data
  },

  setModelSettings: async (payload: {
    provider: string
    model: string
    endpoint_id?: string
  }): Promise<{ success: boolean; message?: string }> => {
    const response = await api.put('/meeting/settings/model', payload)
    return response.data
  },

  saveCustomPrompt: async (prompt: string): Promise<{ success: boolean }> => {
    const response = await api.put('/meeting/settings/prompt', { prompt })
    return response.data
  },

  resetCustomPrompt: async (): Promise<{ success: boolean; active_template?: string; message?: string }> => {
    const response = await api.delete('/meeting/settings/prompt')
    return response.data
  },
}

// ========= v4.0.0: Modules API =========

export interface ModuleStatus {
  name: string
  enabled: boolean
  description?: string
  modules?: string[]
}

export const modulesApi = {
  list: async (): Promise<ModuleStatus[]> => {
    const response = await api.get<ModuleStatus[]>('/modules')
    return response.data
  }
}

// ========= v4.0.0: Providers API =========

export interface ProviderInfo {
  name: string
  display_name: string
  auth_type: string
  supports_tools: boolean
}

export const providersApi = {
  list: async (): Promise<ProviderInfo[]> => {
    const response = await api.get<ProviderInfo[]>('/providers')
    return response.data
  },

  test: async (name: string): Promise<{ status: string; models_count?: number; message?: string }> => {
    const response = await api.post(`/providers/${name}/test`)
    return response.data
  },

  getUsage: (params?: { tenant_id?: string; provider?: string; limit?: number }) =>
    api.get('/providers/usage', { params }),
}

// ========= v4.0.0: Audit API =========

export interface AuditLogItem {
  id: string
  timestamp: string
  user_id: string
  action: string
  resource: string
  detail: string
  ip_address: string
}

export interface AuditLogResponse {
  items: AuditLogItem[]
  page: number
  page_size: number
  total: number
}

export const auditApi = {
  getLogs: async (params?: {
    action?: string
    action_group?: string
    user_id?: string
    tenant_id?: string
    page?: number
    page_size?: number
  }): Promise<AuditLogResponse> => {
    const response = await api.get<{
      items: Array<Record<string, string | null | undefined>>
      page: number
      page_size: number
      total: number
    }>('/audit/logs', { params })
    const data = response.data
    return {
      page: data.page,
      page_size: data.page_size,
      total: data.total,
      items: (data.items || []).map((item) => ({
        id: String(item.id ?? ''),
        timestamp: String(item.timestamp ?? item.created_at ?? ''),
        user_id: String(item.user_id ?? ''),
        action: String(item.action ?? ''),
        resource: String(
          item.resource ??
            [item.resource_type, item.resource_id].filter(Boolean).join(':') ??
            ''
        ),
        detail: String(item.detail ?? ''),
        ip_address: String(item.ip_address ?? item.client_ip ?? ''),
      })),
    }
  }
}

// ========= v4.0.0: Admin Memory API =========

export interface AdminMemoryUser {
  tenant_id: string
  memory_count: number
  shared_count: number
}

export interface AdminMemoryUsersResponse {
  users: AdminMemoryUser[]
}

export const adminMemoryApi = {
  getUsers: async (): Promise<AdminMemoryUsersResponse> => {
    const response = await api.get<AdminMemoryUsersResponse>('/admin/memory/users')
    return response.data
  },

  getUserMemories: async (userId: string): Promise<{ items: MemoryItem[] }> => {
    const response = await api.get<{ items: MemoryItem[] }>(`/admin/memory/users/${userId}`)
    return response.data
  },

  purgeUser: async (userId: string): Promise<{ success: boolean }> => {
    const response = await api.delete(`/admin/memory/users/${userId}/purge`)
    return response.data
  },

  createShared: async (data: { content: string; category: string }): Promise<{ success: boolean }> => {
    const response = await api.post('/admin/memory/shared', data)
    return response.data
  },

  deleteShared: async (id: string): Promise<{ success: boolean }> => {
    const response = await api.delete(`/admin/memory/shared/${id}`)
    return response.data
  }
}

// ========= v4.0.2: Roles API =========

export interface RoleTemplate {
  id: string
  name: string
  description: string
  is_builtin: boolean
  allowed_tools: string[] | '*'
  denied_tools: string[]
  allowed_modules: string[]
  resource_permissions?: Record<string, string[]>
  workspace_restriction: boolean
  max_concurrent: number
  user_count?: number
  created_at?: string
  updated_at?: string
}

export const rolesApi = {
  list: async (): Promise<RoleTemplate[]> => {
    const response = await api.get<RoleTemplate[]>('/roles')
    return response.data
  },

  get: async (id: string): Promise<RoleTemplate> => {
    const response = await api.get<RoleTemplate>(`/roles/${id}`)
    return response.data
  },

  create: async (data: Omit<RoleTemplate, 'is_builtin' | 'user_count' | 'created_at' | 'updated_at'>): Promise<{ success: boolean; template: RoleTemplate }> => {
    const response = await api.post('/roles', data)
    return response.data
  },

  update: async (id: string, data: Partial<RoleTemplate>): Promise<{ success: boolean; template: RoleTemplate }> => {
    const response = await api.put(`/roles/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<{ success: boolean }> => {
    const response = await api.delete(`/roles/${id}`)
    return response.data
  },

  assignRole: async (userId: string, roleTemplateId: string): Promise<{ success: boolean }> => {
    const response = await api.post(`/roles/users/${userId}/role`, { role_template_id: roleTemplateId })
    return response.data
  },

  getUserPermissions: async (userId: string): Promise<{ allowed_tools: string[]; allowed_modules: string[]; role_template_id: string }> => {
    const response = await api.get(`/roles/users/${userId}/permissions`)
    return response.data
  }
}
