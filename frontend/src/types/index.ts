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

export interface ToolCallEvent {
  tool: string
  parameters: Record<string, any>
  success?: boolean
  output?: string
  error?: string
  timestamp: string
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