import { useEffect, useRef, useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useAppStore } from './stores/useAppStore'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  id: string
}

type ModelData = {
  models: string[]
  current_model: string
}

type Skill = {
  id: string
  name: string
  description: string
  version: string
  author: string | null
  category: string
  status: string
  icon: string
  tags: string[]
}

type Settings = {
  darkMode: boolean
  soundEnabled: boolean
  autoSave: boolean
}

function App() {
  const { connectionStatus, sessionId, setConnectionStatus, setSessionId } = useAppStore()
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [models, setModels] = useState<string[]>([])
  const [currentModel, setCurrentModel] = useState('')
  const [isSwitching, setIsSwitching] = useState(false)
  const [skills, setSkills] = useState<Skill[]>([])
  const [activeTab, setActiveTab] = useState<'chat' | 'skills' | 'board' | 'settings'>('chat')
  const [isLoadingSkills, setIsLoadingSkills] = useState(false)
  const [settings, setSettings] = useState<Settings>({
    darkMode: false,
    soundEnabled: true,
    autoSave: true
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const { status, sendMessage } = useWebSocket({
    url: 'ws://localhost:8000/ws',
    onEvent: (event) => {
      if (event.type === 'text_chunk') {
        setChatMessages(prev => {
          const lastMsg = prev[prev.length - 1]
          if (lastMsg?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...lastMsg, content: lastMsg.content + (event.content || '') }
            ]
          }
          return [...prev, { role: 'assistant', content: event.content || '', id: Date.now().toString() }]
        })
      } else if (event.type === 'welcome') {
        setSessionId(event.session_id)
      }
    },
    onConnected: (id) => {
      setSessionId(id)
    }
  })

  useEffect(() => {
    setConnectionStatus(status)
  }, [status, setConnectionStatus])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  // 深色模式应用
  useEffect(() => {
    if (settings.darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [settings.darkMode])

  // 获取模型列表
  const fetchModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/models')
      const data: ModelData = await response.json()
      setModels(data.models)
      setCurrentModel(data.current_model)
    } catch (error) {
      console.error('获取模型列表失败:', error)
    }
  }

  useEffect(() => {
    if (status === 'connected') {
      fetchModels()
      fetchSkills()
    }
  }, [status])

  // 获取技能列表
  const fetchSkills = async () => {
    setIsLoadingSkills(true)
    try {
      const response = await fetch('http://localhost:8000/api/skills')
      const data = await response.json()
      setSkills(data.skills)
    } catch (error) {
      console.error('获取技能列表失败:', error)
    } finally {
      setIsLoadingSkills(false)
    }
  }

  // 切换模型
  const handleSwitchModel = async (modelName: string) => {
    if (modelName === currentModel) return
    setIsSwitching(true)
    try {
      const response = await fetch('http://localhost:8000/api/models/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName })
      })
      const data = await response.json()
      if (data.success) {
        setCurrentModel(data.current_model)
      }
    } catch (error) {
      console.error('模型切换失败:', error)
    } finally {
      setIsSwitching(false)
    }
  }

  // 切换技能状态
  const toggleSkill = async (skillId: string, currentStatus: string) => {
    const endpoint = currentStatus === 'active' ? 'deactivate' : 'activate'
    try {
      const response = await fetch(`http://localhost:8000/api/skills/${skillId}/${endpoint}`, {
        method: 'POST'
      })
      const data = await response.json()
      if (data.success) {
        fetchSkills()
      }
    } catch (error) {
      console.error('技能状态切换失败:', error)
    }
  }

  const getStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'bg-green-50 border-green-500 text-green-800 dark:bg-green-900/30 dark:border-green-700 dark:text-green-400'
      case 'connecting':
      case 'reconnecting':
        return 'bg-yellow-50 border-yellow-500 text-yellow-800 dark:bg-yellow-900/30 dark:border-yellow-700 dark:text-yellow-400'
      default:
        return 'bg-red-50 border-red-500 text-red-800 dark:bg-red-900/30 dark:border-red-700 dark:text-red-400'
    }
  }

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || connectionStatus !== 'connected') return

    const content = inputValue
    setInputValue('')

    setChatMessages(prev => [
      ...prev,
      { role: 'user', content, id: Date.now().toString() }
    ])

    sendMessage({
      type: 'chat',
      session_id: sessionId,
      content
    })
  }

  const getCategoryLabel = (category: string) => {
    const labels: Record<string, string> = {
      productivity: '生产力',
      creative: '创意',
      utility: '工具',
      entertainment: '娱乐',
      education: '教育',
      other: '其他'
    }
    return labels[category] || category
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      productivity: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      creative: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
      utility: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      entertainment: 'bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-400',
      education: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      other: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
    }
    return colors[category] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
  }

  return (
    <div className={`min-h-screen flex flex-col transition-colors duration-300 ${settings.darkMode ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-900'}`}>
      {/* Header */}
      <header className={`shadow-sm border-b transition-colors ${settings.darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <h1 className={`text-2xl font-bold ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>🚀 TARS AI Agent</h1>
          <div className="flex items-center gap-4">
            {/* 模型选择器 */}
            <div className="flex items-center gap-2">
              <label className={`text-sm font-medium ${settings.darkMode ? 'text-gray-300' : 'text-gray-600'}`}>模型:</label>
              <select
                value={currentModel}
                onChange={(e) => handleSwitchModel(e.target.value)}
                disabled={isSwitching || connectionStatus !== 'connected'}
                className={`border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed ${
                  settings.darkMode
                    ? 'bg-gray-700 border-gray-600 text-white'
                    : 'bg-white border-gray-300 text-gray-900'
                }`}
              >
                {models.map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
              {isSwitching && <span className="text-sm text-blue-600 dark:text-blue-400">切换中...</span>}
            </div>
            {/* 连接状态 */}
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm border-l-4 ${getStatusColor()}`}>
              <span className="text-lg">{
                connectionStatus === 'connected' ? '🟢' :
                connectionStatus === 'connecting' ? '🟡' :
                connectionStatus === 'reconnecting' ? '🟠' : '🔴'
              }</span>
              <span className="capitalize">{connectionStatus}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className={`border-b transition-colors ${settings.darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex gap-1">
            {[
              { id: 'chat', label: '💬 聊天' },
              { id: 'skills', label: '📦 技能市场' },
              { id: 'board', label: '📋 工作看板' },
              { id: 'settings', label: '⚙️ 设置' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-4 py-3 font-medium transition-colors ${
                  activeTab === tab.id
                    ? `${settings.darkMode ? 'text-blue-400 border-blue-400' : 'text-blue-600 border-blue-600'} border-b-2`
                    : `${settings.darkMode ? 'text-gray-400 hover:text-gray-200' : 'text-gray-500 hover:text-gray-700'}`
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 flex flex-col max-w-4xl mx-auto w-full px-4 py-6">
        {activeTab === 'chat' ? (
          <div className={`flex-1 rounded-lg shadow p-4 flex flex-col transition-colors ${
            settings.darkMode ? 'bg-gray-800' : 'bg-white'
          }`}>
            <div className="flex-1 overflow-y-auto mb-4 space-y-4">
              {chatMessages.length === 0 ? (
                <div className={`flex flex-col items-center justify-center h-full py-12 ${
                  settings.darkMode ? 'text-gray-400' : 'text-gray-400'
                }`}>
                  <div className="text-6xl mb-4">🤖</div>
                  <p className="text-lg">你好！我是 TARS，有什么可以帮你的吗？</p>
                </div>
              ) : (
                chatMessages.map(msg => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-lg p-4 ${
                      msg.role === 'user'
                        ? 'bg-blue-500 text-white'
                        : settings.darkMode ? 'bg-gray-700 text-gray-100' : 'bg-gray-100 text-gray-800'
                    }`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSend} className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={connectionStatus !== 'connected'}
                placeholder="输入消息..."
                className={`flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 ${
                  settings.darkMode
                    ? 'bg-gray-700 border-gray-600 text-white placeholder-gray-400'
                    : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400'
                }`}
              />
              <button
                type="submit"
                disabled={connectionStatus !== 'connected' || !inputValue.trim()}
                className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white px-6 py-2 rounded-lg transition-colors"
              >
                发送
              </button>
            </form>
          </div>
        ) : activeTab === 'skills' ? (
          <div className={`rounded-lg shadow p-6 transition-colors ${
            settings.darkMode ? 'bg-gray-800' : 'bg-white'
          }`}>
            <div className="flex items-center justify-between mb-6">
              <h2 className={`text-xl font-bold ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>技能列表</h2>
              <button
                onClick={fetchSkills}
                disabled={isLoadingSkills}
                className={`px-4 py-2 rounded-lg transition-colors ${
                  settings.darkMode
                    ? 'bg-gray-700 hover:bg-gray-600 text-white'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-800'
                }`}
              >
                {isLoadingSkills ? '加载中...' : '🔄 刷新'}
              </button>
            </div>
            
            {isLoadingSkills ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" />
              </div>
            ) : skills.length === 0 ? (
              <div className={`text-center py-12 ${settings.darkMode ? 'text-gray-400' : 'text-gray-400'}`}>
                <div className="text-4xl mb-4">📭</div>
                <p>暂无技能，点击下方按钮初始化默认技能</p>
                <button
                  onClick={async () => {
                    await fetch('http://localhost:8000/api/skills/init-default', { method: 'POST' })
                    fetchSkills()
                  }}
                  className="mt-4 bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors"
                >
                  初始化默认技能
                </button>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {skills.map(skill => (
                  <div key={skill.id} className={`border rounded-lg p-4 hover:shadow-md transition-all ${
                    settings.darkMode ? 'border-gray-600' : 'border-gray-200'
                  }`}>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-3xl">{skill.icon}</span>
                        <div>
                          <h3 className={`font-semibold ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>{skill.name}</h3>
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs ${getCategoryColor(skill.category)}`}>
                            {getCategoryLabel(skill.category)}
                          </span>
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs ${
                        skill.status === 'active'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                      }`}>
                        {skill.status === 'active' ? '已激活' : '已停用'}
                      </span>
                    </div>
                    <p className={`mt-2 text-sm ${settings.darkMode ? 'text-gray-300' : 'text-gray-600'}`}>{skill.description}</p>
                    <div className="mt-3 flex items-center justify-between">
                      <div className="flex gap-1 flex-wrap">
                        {skill.tags.map(tag => (
                          <span key={tag} className={`text-xs px-2 py-0.5 rounded ${
                            settings.darkMode ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600'
                          }`}>
                            #{tag}
                          </span>
                        ))}
                      </div>
                      <button
                        onClick={() => toggleSkill(skill.id, skill.status)}
                        className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                          skill.status === 'active'
                            ? 'bg-red-100 text-red-600 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-800/40'
                            : 'bg-green-100 text-green-600 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-800/40'
                        }`}
                      >
                        {skill.status === 'active' ? '停用' : '激活'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : activeTab === 'board' ? (
          <div className={`rounded-lg shadow p-6 transition-colors ${
            settings.darkMode ? 'bg-gray-800' : 'bg-white'
          }`}>
            <h2 className={`text-xl font-bold mb-6 ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>工作看板</h2>
            <div className="grid gap-6 md:grid-cols-3">
              <div className={`border rounded-lg p-4 ${settings.darkMode ? 'border-gray-600' : 'border-gray-200'}`}>
                <h3 className={`font-semibold mb-3 ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>📌 待办</h3>
                <div className="text-center py-8 text-gray-400">
                  <div className="text-3xl mb-2">💡</div>
                  <p>功能开发中...</p>
                </div>
              </div>
              <div className={`border rounded-lg p-4 ${settings.darkMode ? 'border-gray-600' : 'border-gray-200'}`}>
                <h3 className={`font-semibold mb-3 ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>🔄 进行中</h3>
                <div className="text-center py-8 text-gray-400">
                  <div className="text-3xl mb-2">💡</div>
                  <p>功能开发中...</p>
                </div>
              </div>
              <div className={`border rounded-lg p-4 ${settings.darkMode ? 'border-gray-600' : 'border-gray-200'}`}>
                <h3 className={`font-semibold mb-3 ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>✅ 已完成</h3>
                <div className="text-center py-8 text-gray-400">
                  <div className="text-3xl mb-2">💡</div>
                  <p>功能开发中...</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className={`rounded-lg shadow p-6 transition-colors ${
            settings.darkMode ? 'bg-gray-800' : 'bg-white'
          }`}>
            <h2 className={`text-xl font-bold mb-6 ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>系统设置</h2>
            <div className="space-y-6">
              {/* 深色模式 */}
              <div className="flex items-center justify-between py-4 border-b border-gray-200 dark:border-gray-600">
                <div>
                  <h3 className={`font-medium ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>深色模式</h3>
                  <p className={`text-sm ${settings.darkMode ? 'text-gray-400' : 'text-gray-500'}`}>切换深色/浅色主题</p>
                </div>
                <button
                  onClick={() => setSettings(s => ({ ...s, darkMode: !s.darkMode }))}
                  className={`relative w-14 h-8 rounded-full transition-colors ${
                    settings.darkMode ? 'bg-blue-500' : 'bg-gray-300'
                  }`}
                >
                  <div className={`absolute top-1 left-1 bg-white w-6 h-6 rounded-full transition-transform ${
                    settings.darkMode ? 'translate-x-6' : ''
                  }`} />
                </button>
              </div>

              {/* 声音开关 */}
              <div className="flex items-center justify-between py-4 border-b border-gray-200 dark:border-gray-600">
                <div>
                  <h3 className={`font-medium ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>声音提示</h3>
                  <p className={`text-sm ${settings.darkMode ? 'text-gray-400' : 'text-gray-500'}`}>启用声音通知</p>
                </div>
                <button
                  onClick={() => setSettings(s => ({ ...s, soundEnabled: !s.soundEnabled }))}
                  className={`relative w-14 h-8 rounded-full transition-colors ${
                    settings.soundEnabled ? 'bg-blue-500' : 'bg-gray-300'
                  }`}
                >
                  <div className={`absolute top-1 left-1 bg-white w-6 h-6 rounded-full transition-transform ${
                    settings.soundEnabled ? 'translate-x-6' : ''
                  }`} />
                </button>
              </div>

              {/* 自动保存 */}
              <div className="flex items-center justify-between py-4 border-b border-gray-200 dark:border-gray-600">
                <div>
                  <h3 className={`font-medium ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>自动保存</h3>
                  <p className={`text-sm ${settings.darkMode ? 'text-gray-400' : 'text-gray-500'}`}>自动保存聊天记录</p>
                </div>
                <button
                  onClick={() => setSettings(s => ({ ...s, autoSave: !s.autoSave }))}
                  className={`relative w-14 h-8 rounded-full transition-colors ${
                    settings.autoSave ? 'bg-blue-500' : 'bg-gray-300'
                  }`}
                >
                  <div className={`absolute top-1 left-1 bg-white w-6 h-6 rounded-full transition-transform ${
                    settings.autoSave ? 'translate-x-6' : ''
                  }`} />
                </button>
              </div>

              {/* 关于 */}
              <div className="pt-4">
                <h3 className={`font-medium mb-2 ${settings.darkMode ? 'text-white' : 'text-gray-800'}`}>关于 TARS</h3>
                <p className={`text-sm ${settings.darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  版本: 1.0.0
                </p>
                <p className={`text-sm ${settings.darkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                  一个可扩展的 AI Agent 系统
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
