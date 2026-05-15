/**
 * WebSocket 入口：开发环境走 Vite 同源 `/ws` 代理，避免写死 localhost
 *（用局域网 IP 打开前端时，ws://localhost:8000 会连到错误主机）。
 * 生产 / vite preview 未配置代理时，设置 VITE_WS_URL（如 ws://127.0.0.1:8000/ws）。
 */
export function resolveWebSocketUrl(): string {
  const fromEnv = import.meta.env.VITE_WS_URL as string | undefined
  if (fromEnv?.trim()) {
    return fromEnv.trim()
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws`
}
