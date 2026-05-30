import { ACCESS_TOKEN_STORAGE_KEY } from '@/stores/auth'

/**
 * WebSocket 入口：开发环境走 Vite 同源 `/ws` 代理，避免写死 localhost
 *（用局域网 IP 打开前端时，ws://localhost:8000 会连到错误主机）。
 * 生产 / vite preview 未配置代理时，设置 VITE_WS_URL（如 ws://127.0.0.1:8000/ws）。
 */
function buildAuthQuery(): string {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  if (accessToken) {
    return `?token=${encodeURIComponent(accessToken)}`
  }
  const apiKey = localStorage.getItem('apiKey') || ''
  return apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : ''
}

export function resolveWebSocketUrl(): string {
  const query = buildAuthQuery()

  const fromEnv = import.meta.env.VITE_WS_URL as string | undefined
  if (fromEnv?.trim()) {
    const base = fromEnv.trim().replace(/\/+$/, '')
    return `${base}${query}`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws${query}`
}

/** 会议助手实时录音 WebSocket（浏览器无法带 Header，使用 token 或 api_key query）。 */
export function resolveMeetingWebSocketUrl(options?: { language?: string }): string {
  const params = new URLSearchParams()
  const accessToken = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  if (accessToken) {
    params.set('token', accessToken)
  } else {
    const apiKey = localStorage.getItem('apiKey') || ''
    if (apiKey) params.set('api_key', apiKey)
  }
  const lang = options?.language ?? localStorage.getItem('meeting_asr_language') ?? ''
  if (lang && lang !== 'auto') params.set('language', lang)
  const query = params.toString() ? `?${params.toString()}` : ''
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/meeting/ws/record${query}`
}
