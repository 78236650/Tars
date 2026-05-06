import axios from 'axios'
import type {
  User,
  UserListResponse,
  Personality,
  PersonalityResponse,
  SubAgent,
  SubAgentListResponse,
  SubAgentConfig,
  ApiResponse,
  ChatSession,
  ChatHistoryMessage,
} from '@/types'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

api.interceptors.request.use((config) => {
  const apiKey = localStorage.getItem('apiKey')
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey
  }
  return config
})

export const authApi = {
  getCurrentUser: async (apiKey?: string): Promise<User> => {
    const params = apiKey ? { api_key: apiKey } : undefined
    const response = await api.get<User>('/users/me', { params })
    return response.data
  },
  
  getUsers: async (): Promise<UserListResponse> => {
    const response = await api.get<UserListResponse>('/users')
    return response.data
  },
  
  createUser: async (username: string, email: string, role: string = 'user'): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>('/users', { username, email, role })
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
  getModels: async (): Promise<{ models: string[], current_model: string }> => {
    const response = await api.get<{ models: string[], current_model: string }>('/models')
    return response.data
  },
  
  switchModel: async (modelName: string): Promise<ApiResponse> => {
    const response = await api.post<ApiResponse>('/models/switch', { model_name: modelName })
    return response.data
  }
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
}

export const skillhubApi = {
  search: (query: string) => api.get('/skillhub/search', { params: { q: query } }),
  getDetail: (id: string) => api.get(`/skillhub/detail/${id}`),
  install: (skillId: string) => api.post('/skillhub/install', { skill_id: skillId }),
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