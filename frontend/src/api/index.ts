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
  SessionArtifactsData,
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
  OrchestrationTaskDetail,
  OrchestrationTaskListResponse,
  OrchestrationDispatchResult,
  VpHorizonResponse,
  VpVoyageDetail,
  VpAdoptResult,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  // 模型列表 / 切换、大文件等可能超过 10s；过短会表现为「模型连不上」
  timeout: 120000
})

api.interceptors.request.use((config) => {
  const accessToken = localStorage.getItem('tars_access_token')
  if (accessToken) {
    config.headers['Authorization'] = `Bearer ${accessToken}`
  } else {
    const apiKey = localStorage.getItem('apiKey')
    if (apiKey) {
      config.headers['X-API-Key'] = apiKey
    }
  }
  const userJson = localStorage.getItem('auth_user')
  if (userJson) {
    try {
      const user = JSON.parse(userJson)
      if (user?.role) {
        config.headers['X-User-Role'] = user.role
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

  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
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

  getArtifacts: async (id: string): Promise<SessionArtifactsData> => {
    const response = await api.get<{ success: boolean; data: SessionArtifactsData }>(`/sessions/${id}/artifacts`)
    return response.data.data
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

const scopeUserParams = (userId?: string) =>
  userId ? { user_id: userId } : undefined

export const plansApi = {
  list: async (options?: { userId?: string }): Promise<{ plans: Record<string, unknown>[] }> => {
    const response = await api.get('/plans', { params: scopeUserParams(options?.userId) })
    return response.data
  },

  get: async (planId: string, options?: { userId?: string }): Promise<Record<string, unknown>> => {
    const response = await api.get(`/plans/${planId}`, { params: scopeUserParams(options?.userId) })
    return response.data
  },

  approve: async (
    planId: string,
    steps?: Record<string, unknown>[],
    options?: { userId?: string },
  ): Promise<{ success: boolean; plan_id: string; status: string }> => {
    const response = await api.post(`/plans/${planId}/approve`, { steps }, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  reject: async (
    planId: string,
    options?: { userId?: string },
  ): Promise<{ success: boolean; plan_id: string; status: string }> => {
    const response = await api.post(`/plans/${planId}/reject`, undefined, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  retry: async (
    planId: string,
    options?: { userId?: string },
  ): Promise<{ success: boolean; plan_id: string; status: string }> => {
    const response = await api.post(`/plans/${planId}/retry`, undefined, {
      params: scopeUserParams(options?.userId),
    })
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
  listDataSources: async (options?: { userId?: string }): Promise<{ datasources: DataSource[] }> => {
    const response = await api.get('/datasources/', {
      params: options?.userId ? { user_id: options.userId } : undefined,
    })
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

const insightScopeParams = (options?: { userId?: string; sessionId?: string }) => {
  const params: Record<string, string> = {}
  if (options?.userId) params.user_id = options.userId
  if (options?.sessionId) params.session_id = options.sessionId
  return Object.keys(params).length ? params : undefined
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

  getLlmSettings: async (options?: { userId?: string }): Promise<InsightLlmSettingsResponse> => {
    const response = await api.get('/insight/llm/settings', {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  saveLlmSettings: async (
    body: InsightLlmSettingsPayload,
    options?: { userId?: string },
  ): Promise<InsightLlmSettingsResponse & { success: boolean }> => {
    const response = await api.put('/insight/llm/settings', body, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  startProfile: async (
    datasourceId: string,
    options?: {
      force?: boolean
      llm?: InsightLlmSettingsPayload & { persist?: boolean }
      pending_question?: string
      session_id?: string
      userId?: string
    }
  ): Promise<{ success: boolean; run_id: string; status: string }> => {
    const response = await api.post(`/insight/datasources/${datasourceId}/profile`, {
      force: options?.force ?? false,
      llm: options?.llm,
      pending_question: options?.pending_question,
      session_id: options?.session_id,
    }, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  startForge: async (
    datasourceId: string,
    options?: {
      force?: boolean
      pending_question?: string
      session_id?: string
      userId?: string
    }
  ): Promise<{ success: boolean; run_id: string; status: string }> => {
    const response = await api.post(`/insight/datasources/${datasourceId}/forge`, {
      force: options?.force ?? false,
      pending_question: options?.pending_question,
      session_id: options?.session_id,
    }, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  listProfileRuns: async (
    datasourceId: string,
    options?: { userId?: string },
  ): Promise<{ runs: InsightProfileRunSummary[] }> => {
    const response = await api.get(`/insight/datasources/${datasourceId}/profile/runs`, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  getProfileRun: async (
    runId: string,
    options?: { userId?: string },
  ): Promise<InsightProfileRunSummary & { insight_snapshot?: unknown }> => {
    const response = await api.get(`/insight/profile/runs/${runId}`, {
      params: scopeUserParams(options?.userId),
    })
    return response.data
  },

  getDatasourceBrief: async (
    datasourceId: string,
    options?: { userId?: string },
  ): Promise<InsightDatasourceBrief> => {
    const response = await api.get(`/insight/datasources/${datasourceId}/brief`, {
      params: options?.userId ? { user_id: options.userId } : undefined,
    })
    return response.data
  },

  getWorkflow: async (
    datasourceId: string,
    options?: { sessionId?: string; userId?: string },
  ): Promise<Record<string, unknown>> => {
    const response = await api.get(`/insight/datasources/${datasourceId}/workflow`, {
      params: insightScopeParams(options),
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
    config?: { signal?: AbortSignal; userId?: string },
  ): Promise<InsightMetricAnswer> => {
    const response = await api.post(
      `/insight/datasources/${datasourceId}/ask`,
      body,
      {
        ...config,
        params: scopeUserParams(config?.userId),
      },
    )
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
  username: string
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

export const orchestrationApi = {
  listTasks: async (page = 1, pageSize = 20): Promise<OrchestrationTaskListResponse> => {
    const response = await api.get<OrchestrationTaskListResponse>('/orchestration/tasks', {
      params: { page, page_size: pageSize },
    })
    return response.data
  },

  getTask: async (taskId: string): Promise<OrchestrationTaskDetail> => {
    const response = await api.get<OrchestrationTaskDetail>(`/orchestration/tasks/${taskId}`)
    return response.data
  },

  dispatch: async (sessionId: string, goal: string): Promise<OrchestrationDispatchResult> => {
    const response = await api.post<OrchestrationDispatchResult>('/orchestration/dispatch', {
      session_id: sessionId,
      goal,
    })
    return response.data
  },
}

export const vesselPlanApi = {
  demoStatus: async () => {
    const response = await api.get('/vessel-plans/demo/status')
    return response.data
  },
  resetDemo: async () => {
    const response = await api.post('/vessel-plans/demo/reset')
    return response.data
  },
  getHorizon: async (hours = 48) => {
    const response = await api.get<VpHorizonResponse>('/vessel-plans/horizon', { params: { hours } })
    return response.data
  },
  optimize: async (horizonHours = 48) => {
    const response = await api.post<VpHorizonResponse>('/vessel-plans/optimize', {
      horizon_hours: horizonHours,
    })
    return response.data
  },
  recompute: async (horizonHours = 48) => {
    const response = await api.post<VpHorizonResponse>('/vessel-plans/recompute', {
      horizon_hours: horizonHours,
    })
    return response.data
  },
  patchAssignment: async (
    voyageId: string,
    body: { berth_id?: string; etb?: string; etd?: string; locked?: boolean },
  ) => {
    const response = await api.patch<VpVoyageDetail>(`/vessel-plans/assignments/${voyageId}`, body)
    return response.data
  },
  getVoyage: async (voyageId: string) => {
    const response = await api.get<VpVoyageDetail>(`/vessel-plans/voyages/${voyageId}`)
    return response.data
  },
  adopt: async (voyageIds: string[], sessionId: string) => {
    const response = await api.post<VpAdoptResult>('/vessel-plans/adopt', {
      voyage_ids: voyageIds,
      session_id: sessionId,
    })
    return response.data
  },
}

// ── v5.0.1: 售前管理 ────────────────────────────────────────

export interface PresalesProject {
  id: string
  name: string
  customer_name: string
  industry: string
  status: string
  requirement_summary: string
  proposal_content: string
  ppt_outline: string
  tags: string[]
  created_by: string
  created_at: string
  updated_at: string
  tenant_id: string
}

export interface PresalesProjectListResponse {
  projects: PresalesProject[]
  total: number
  page: number
  page_size: number
}

export interface PresalesMaterial {
  id: string
  project_id: string
  material_type: string
  title: string
  wiki_page_name: string
  knowledge_doc_id: string
  file_path: string
  uploaded_by: string
  created_at: string
}

export interface PresalesMaterialListResponse {
  materials: PresalesMaterial[]
}

export interface PresalesWorkflow {
  id: string
  project_id: string
  workflow_type: string
  status: string
  orchestration_task_id: string
  input_data: string
  output_data: string
  created_by: string
  created_at: string
  updated_at: string
  tenant_id: string
}

export const presalesApi = {
  listProjects: async (params?: {
    page?: number
    page_size?: number
    status?: string
  }): Promise<PresalesProjectListResponse> => {
    const response = await api.get<PresalesProjectListResponse>('/presales/projects', { params })
    return response.data
  },

  getProject: async (id: string): Promise<PresalesProject> => {
    const response = await api.get<PresalesProject>(`/presales/projects/${id}`)
    return response.data
  },

  createProject: async (data: {
    name: string
    customer_name?: string
    industry?: string
    tags?: string[]
  }): Promise<{ success: boolean; id: string }> => {
    const response = await api.post<{ success: boolean; id: string }>('/presales/projects', data)
    return response.data
  },

  updateProject: async (id: string, data: Record<string, unknown>): Promise<{ success: boolean }> => {
    const response = await api.put<{ success: boolean }>(`/presales/projects/${id}`, data)
    return response.data
  },

  deleteProject: async (id: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(`/presales/projects/${id}`)
    return response.data
  },

  listMaterials: async (projectId: string): Promise<PresalesMaterialListResponse> => {
    const response = await api.get<PresalesMaterialListResponse>(`/presales/projects/${projectId}/materials`)
    return response.data
  },

  addMaterial: async (projectId: string, data: {
    material_type?: string
    title?: string
    wiki_page_name?: string
    knowledge_doc_id?: string
    file_path?: string
  }): Promise<{ success: boolean; id: string }> => {
    const response = await api.post<{ success: boolean; id: string }>(`/presales/projects/${projectId}/materials`, data)
    return response.data
  },

  startWorkflow: async (data: {
    workflow_type: string
    input_data?: string
  }): Promise<{ success: boolean; id: string; status: string }> => {
    const response = await api.post<{ success: boolean; id: string; status: string }>('/presales/workflows', data)
    return response.data
  },

  getWorkflow: async (id: string): Promise<PresalesWorkflow> => {
    const response = await api.get<PresalesWorkflow>(`/presales/workflows/${id}`)
    return response.data
  },

  generateProposal: async (projectId: string, context?: string): Promise<{ success: boolean; project_id: string; message: string }> => {
    const response = await api.post<{ success: boolean; project_id: string; message: string }>('/presales/generate/proposal', {
      project_id: projectId,
      context: context || '',
    })
    return response.data
  },

  generatePpt: async (projectId: string, context?: string): Promise<{ success: boolean; project_id: string; message: string }> => {
    const response = await api.post<{ success: boolean; project_id: string; message: string }>('/presales/generate/ppt', {
      project_id: projectId,
      context: context || '',
    })
    return response.data
  },
}
