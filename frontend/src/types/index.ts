export interface User {
  id: string
  username: string
  email: string
  role: string
  api_key?: string
  created_at: string
  last_login?: string
}

export interface UserResponse {
  success: boolean
  message: string
  data?: User
}

export interface UserListResponse {
  users: User[]
  total: number
}

export interface SoulParameters {
  honesty: number
  humor: number
  initiative: number
  empathy: number
  formality: number
  creativity: number
  conciseness: number
  technical_depth: number
  curiosity: number
  skepticism: number
}

export interface SoulIdentity {
  name: string
  role: string
  creator: string
}

export interface Personality {
  identity: SoulIdentity
  parameters: SoulParameters
  communication_style: string
  behavior_rules: string[]
}

export interface PersonalityResponse {
  success: boolean
  message: string
  data?: Personality
}

export interface MemoryItem {
  id: string
  content: string
  summary: string
  category: string
  importance: number
  created_at: string | null
  updated_at: string | null
  last_accessed: string | null
  source: string
  pinned: boolean
  compressed_from: string[]
  memory_type: 'episodic' | 'longterm' | 'compressed' | string
  event_time: string | null
  entity_refs: string[]
}

export interface MemoryStats {
  total: number
  recent: number
  longterm: number
  pending_compression: number
  last_compressed_at: string | null
}

export interface CoreMemoryBlocksResponse {
  blocks: Record<string, string>
}

export interface RecentMemoryResponse {
  items: MemoryItem[]
  page: number
  page_size: number
  total: number
}

export interface LongtermMemoryGroup {
  group_name: string
  items: MemoryItem[]
}

export interface LongtermMemoryResponse {
  page: number
  page_size: number
  total: number
  groups: LongtermMemoryGroup[]
}

export interface MemoryCompressionStatus {
  status: string
  running: boolean
  last_started_at: string | null
  last_finished_at: string | null
  progress: Record<string, unknown>
  last_report?: {
    status: string
    compressed_count: number
    cleaned_count?: number
    entities?: string[]
    error?: string
  } | null
}

export interface MemoryMergeResponse {
  preview_only: boolean
  merged_content: string
  source_memory_ids: string[]
  importance: number
  memory_type: string
  entity_refs: string[]
  memory?: MemoryItem
}

export interface SubAgent {
  type: string
  name: string
  description: string
  icon: string
  enabled: boolean
  llm_model?: string
  llm_provider?: string
  temperature: number
  personality_weight: number
}

export interface SubAgentListResponse {
  subagents: Record<string, SubAgent>
}

export interface SubAgentConfig {
  llm_model?: string
  llm_provider?: string
  temperature?: number
  personality_weight?: number
  enabled?: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  attachments?: any[]
  thinking?: any
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
}

export interface SettingsState {
  personality: Personality | null
  subagents: Record<string, SubAgent>
  availableModels: string[]
}

export interface ApiResponse<T = unknown> {
  success: boolean
  message: string
  data?: T
  timestamp?: string
}

// ========= Tools & Skills v2 =========

export interface Tool {
  id: string
  name: string
  icon: string
  type: 'builtin' | 'plugin' | 'prompt'
  source: 'builtin' | 'local' | 'skillhub'
  status: 'active' | 'disabled'
  description: string
  version?: string
  author?: string
  permissions?: string[]
  parameters_schema?: Record<string, any>
}

export interface SkillItem {
  id: string
  name: string
  description: string
  type: 'plugin' | 'prompt'
  version: string
  author: string
  tags: string[]
  enabled: boolean
  source: string
  permissions: string[]
  prompt_template?: string
  parameters?: { name: string; type: string; description: string; required: boolean; default?: any }[]
}

export interface SkillHubPackage {
  id: string
  name: string
  description: string
  author: string
  version: string
  downloads: number
  type: 'plugin' | 'prompt'
  tags: string[]
  permissions: string[]
  github_url: string
  stars: number
  installed?: boolean
  tars_version_min?: string
  usage?: string
}

export interface BIChartData {
  chart_type: string
  title: string
  echarts_option: Record<string, any>
  data_summary: string
  raw_data?: Record<string, any>[]
}

export interface KnowledgeCollection {
  id: string
  name: string
  description?: string
  created_at: string
  updated_at: string
}

export interface KnowledgeDocument {
  id: string
  file_name: string
  file_type: string
  chunk_count: number
  status: string
  created_at: string
}

export interface KnowledgeSearchResult {
  text: string
  metadata: Record<string, any>
  score: number
  source: {
    collection_id: string
    file_name: string
    chunk_index: number
    chunk_total: number
  }
}

export interface ToolCallEvent {
  id?: string
  tool: string
  parameters: Record<string, any>
  success?: boolean
  output?: string
  error?: string
  duration?: number
  timestamp: string
  metadata?: Record<string, any>
}

export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ChatHistoryMessage {
  id: string
  role: string
  content: string
  timestamp: string
}

export interface ReminderSummaryLog {
  step: string
  status: string
  message: string
  timestamp?: string
}

export interface ReminderNotification {
  id: string
  job_id: string
  session_id: string | null
  task_name: string
  message: string
  delivery_status: string
  error_message: string | null
  is_read: boolean
  triggered_at: string
  read_at: string | null
  created_at: string
  updated_at: string
  summary_logs?: ReminderSummaryLog[]
}

export interface ReminderNotificationListData {
  notifications: ReminderNotification[]
  total: number
  unread_total: number
  limit: number
  offset: number
}

/** OpenAI 兼容 API 端点（模型配置页） */
export interface Endpoint {
  id: string
  name: string
  base_url: string
  api_key: string
  models: string[]
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface ModelsOverviewResponse {
  ollama_models: string[]
  ollama_base_url: string
  ollama_status: string
  endpoints: Endpoint[]
  current: {
    provider: 'ollama' | 'openai_compatible'
    endpoint_id: string | null
    model: string
  }
}

export interface ModelSwitchBody {
  provider: 'ollama' | 'openai_compatible'
  model: string
  endpoint_id?: string | null
}

export interface ModelSwitchResult {
  success: boolean
  message?: string
  current?: ModelsOverviewResponse['current']
}

// ========= BI Analytics =========

export interface DataSource {
  id: string
  name: string
  db_type: string
  readonly: boolean
  schema_snapshot: Record<string, any>
  schema_annotations: Record<string, any>
  created_at: string
  updated_at: string
}

export interface BIQueryResult {
  success: boolean
  data: Record<string, any>[]
  columns: string[]
  row_count: number
  error: string | null
  sql: string
}

export interface BIChartResult {
  chart_type: string
  title: string
  echarts_option: Record<string, any>
  data_summary: string
  raw_data: Record<string, any>[]
}

// ========= Meeting Voice Recognition =========

export interface Transcription {
  id: string
  user_id: string
  file_name: string | null
  file_size: number | null
  duration: number | null
  language: string | null
  status: 'pending' | 'processing' | 'completed' | 'failed'
  transcript: string | null
  summary: string | null
  key_points: string[]
  model_used: string | null
  created_at: string | null
  completed_at: string | null
  error_message: string | null
  approved_at: string | null
  knowledge_doc_id: string | null
}

export interface TranscriptionListData {
  success: boolean
  transcriptions: Transcription[]
  total: number
  limit: number
  offset: number
}
