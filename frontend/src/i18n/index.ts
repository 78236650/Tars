import { ref } from 'vue'

type MessageParams = Record<string, string | number>

export const messages: Record<string, Record<string, string>> = {
  zh: {
    // 导航
    'nav.chat': '聊天',
    'nav.memory': '记忆管理',
    'nav.models': '模型',
    'nav.tools': '工具',
    'nav.bi': 'BI 分析',
    'nav.knowledge': '知识库',
    'nav.meeting': '会议助手',
    'nav.settings': '设置',

    // 通用
    'common.loading': '加载中...',
    'common.save': '保存',
    'common.cancel': '取消',
    'common.delete': '删除',
    'common.edit': '编辑',
    'common.create': '创建',
    'common.search': '搜索',
    'common.install': '安装',
    'common.uninstall': '卸载',
    'common.enable': '启用',
    'common.disable': '禁用',
    'common.close': '关闭',
    'common.confirm': '确认',
    'common.success': '成功',
    'common.error': '错误',
    'common.send': '发送',
    'common.reset': '重置',
    'common.test': '测试',
    'common.back': '返回',
    'common.backToChat': '返回聊天',
    'common.enabled': '已启用',
    'common.disabled': '已禁用',
    'common.model': '模型',
    'common.notSelected': '未选择',
    'common.deleteFailed': '删除失败',

    // Desktop
    'desktop.default.title': 'TARS 工作台',
    'desktop.default.subtitle': '统一桌面工作台',
    'desktop.chat.title': '聊天工作台',
    'desktop.chat.subtitle': '对话、计划、文件和提醒都在同一个主工作区完成。',
    'desktop.memory.title': '记忆工作台',
    'desktop.memory.subtitle': '用更清晰的结构管理人格、近期/长期记忆与压缩状态。',
    'desktop.settings.title': '系统设置',
    'desktop.settings.subtitle': '集中管理子代理、用户和桌面工作台的基础配置。',
    'desktop.models.title': '模型中心',
    'desktop.models.subtitle': '统一切换本地与远端模型，管理端点与连通性。',
    'desktop.tools.title': '工具与技能',
    'desktop.tools.subtitle': '查看内置工具、已安装技能以及 SkillHub 生态。',
    'desktop.bi.title': 'BI 分析台',
    'desktop.bi.subtitle': '管理数据源、执行 SQL，并把结果转换为图表。',
    'desktop.meeting.title': '会议工作台',
    'desktop.meeting.subtitle': '录音、上传、转写与历史复盘整合到同一桌面流中。',
    'desktop.knowledge.title': '知识库',
    'desktop.knowledge.subtitle': '创建知识库、上传文档并直接验证检索效果。',

    // Sidebar
    'sidebar.currentModel': '当前模型',
    'sidebar.ollama': 'Ollama',
    'sidebar.custom': '自定义模型',
    'sidebar.openrouter': 'OpenRouter',
    'sidebar.addCustomModel': '添加自定义模型',
    'sidebar.configureOpenrouter': '请在设置页面配置 OpenRouter',
    'sidebar.goToSettings': '去设置 →',
    'sidebar.collapse': '折叠侧边栏',
    'sidebar.expand': '展开侧边栏',
    'sidebar.switchedTo': '已切换到',
    'sidebar.switchFailed': '切换失败',
    'sidebar.language': '语言',
    'sidebar.localModels': '本地模型',
    'sidebar.noEndpointModels': '暂无模型，请在模型页拉取或手动添加',
    'sidebar.modelConfigLink': '模型配置',

    // Chat
    'chat.title': 'TARS Agent',
    'chat.subtitle': 'AI Assistant',
    'chat.connected': '已连接',
    'chat.disconnected': '未连接',
    'chat.placeholder': '输入消息...',
    'chat.welcome': '欢迎使用 TARS Agent',
    'chat.welcomeHint': '开始对话吧',
    'chat.thinking': 'TARS 思考中...',
    'chat.uploadFailed': '上传失败',
    'chat.fileTooLarge': '文件超过 50MB 限制，请提供文件路径由工具直接读取',
    'chat.maxFiles': '最多上传 5 个文件',
    'chat.uploadTooltip': '上传文件',
    'chat.newChat': '新对话',
    'chat.noSessions': '暂无会话',
    'chat.deleteConfirm': '确定删除该会话？',
    'chat.sessionDeleted': '会话已删除',

    // Tools
    'tools.title': 'Tools 管理中心',
    'tools.subtitle': '管理工具和技能',
    'tools.addSkill': '添加技能',
    'tools.tabBuiltin': '内置工具',
    'tools.tabSkills': '已安装技能',
    'tools.tabSkillhub': 'SkillHub 商店',
    'tools.searchPlaceholder': '搜索...',
    'tools.noTools': '没有找到工具',
    'tools.noSkills': '暂无已安装技能',
    'tools.hubSearchPlaceholder': '搜索 SkillHub 技能...',
    'tools.hubSearchHint': '输入关键词搜索 SkillHub 社区技能',
    'tools.installing': '安装中...',
    'tools.searching': '搜索中...',
    'tools.installed': '已安装',
    'tools.reinstall': '重装',
    'tools.installSuccess': '安装成功',
    'tools.installFailed': '安装失败',
    'tools.browseCatalog': '浏览技能目录',
    'tools.catalogEmpty': '技能目录为空',
    'tools.filterAll': '全部',
    'tools.filterPlugin': '工具类',
    'tools.filterPrompt': '提示词类',
    'tools.usageTitle': '用法说明',
    'tools.compatible': '兼容',
    'tools.incompatible': '不兼容',

    // Tool Detail
    'toolDetail.description': '描述',
    'toolDetail.tags': '标签',
    'toolDetail.promptTemplate': 'Prompt 模板',
    'toolDetail.parameters': '参数',
    'toolDetail.permissions': '权限声明',
    'toolDetail.usage': '使用方法',
    'toolDetail.required': '必填',
    'toolDetail.defaultValue': '默认值',
    'toolDetail.builtin': '内置工具',
    'toolDetail.plugin': 'Plugin 技能',
    'toolDetail.prompt': 'Prompt 技能',
    'toolDetail.uninstallConfirm': '确定要卸载这个技能吗？',
    'toolDetail.uninstalled': '技能已卸载',
    'toolDetail.enabledMsg': '技能已启用',
    'toolDetail.disabledMsg': '技能已禁用',
    'toolDetail.operationFailed': '操作失败',

    // Add Skill Modal
    'addSkill.title': '创建 Prompt 技能',
    'addSkill.id': 'ID',
    'addSkill.idPlaceholder': 'my_skill（小写字母+下划线）',
    'addSkill.name': '名称',
    'addSkill.namePlaceholder': '我的技能',
    'addSkill.description': '描述',
    'addSkill.descPlaceholder': '技能描述',
    'addSkill.tags': '标签（逗号分隔）',
    'addSkill.tagsPlaceholder': 'writing, creative',
    'addSkill.template': 'Prompt 模板',
    'addSkill.templatePlaceholder': '你现在是一个 XXX 专家。请遵循以下原则：\n1. ...\n2. ...',
    'addSkill.templateHint': 'Prompt 模板会在对话时注入到 system prompt 中，增强 LLM 行为',
    'addSkill.fillRequired': '请填写完整必填字段',
    'addSkill.creating': '创建中...',
    'addSkill.createFailed': '创建失败',

    // Models
    'models.title': '模型配置',
    'models.subtitle': '管理 AI 模型 Provider',
    'models.backToChat': '返回聊天',
    'models.ollama': 'Ollama (本地)',
    'models.ollamaDesc': '本地运行的大模型，隐私性好，速度快',
    'models.openrouter': 'OpenRouter',
    'models.openrouterDesc': '支持多种云端模型，选择丰富',
    'models.anthropic': 'Anthropic (Claude)',
    'models.anthropicDesc': 'Anthropic 的 Claude 系列模型',
    'models.openai': 'OpenAI (GPT)',
    'models.openaiDesc': 'OpenAI 的 GPT 系列模型',

    'modelsPage.ollamaBlock': 'Ollama 本地模型',
    'modelsPage.ollamaEnvHint': '连接地址由环境变量 OLLAMA_BASE_URL 提供，此处不可编辑。',
    'modelsPage.ollamaEmpty': '未检测到本地模型。可在终端执行：ollama pull <model>',
    'modelsPage.remoteBlock': 'OpenAI 兼容端点',
    'modelsPage.addEndpoint': '添加端点',
    'modelsPage.namePh': '显示名，如 DeepSeek API',
    'modelsPage.baseUrlPh': 'Base URL，如 https://api.deepseek.com/v1',
    'modelsPage.apiKeyPh': 'API Key（可选）',
    'modelsPage.noEndpoints': '尚未添加远程端点。',
    'modelsPage.fetchModels': '拉取模型',
    'modelsPage.noModelsHint': '若自动拉取失败，可手动添加模型 ID。',
    'modelsPage.manualModels': '手动添加模型',
    'modelsPage.manualPlaceholder': '每行一个模型 ID，或用英文逗号分隔',
    'modelsPage.editEndpoint': '编辑端点',
    'modelsPage.apiKeyLeaveBlank': '留空则不修改 API Key',
    'modelsPage.modelsOnePerLine': '模型列表（每行一个）',
    'modelsPage.switched': '已切换模型',
    'modelsPage.fillRequired': '请填写名称与 Base URL',
    'modelsPage.endpointCreated': '端点已添加',
    'modelsPage.deleteConfirm': '确定删除该端点？',
    'modelsPage.fetchOk': '已拉取 {count} 个模型',
    'modelsPage.fetchOkPrefix': '已拉取',
    'modelsPage.fetchEmpty': '未解析到模型列表，可手动添加',
    'modelsPage.manualEmpty': '请输入至少一个模型 ID',

    // Settings
    'settings.title': '设置',
    'settings.personality': '人格设置',
    'settings.subagents': '子代理',
    'settings.users': '用户管理',
  },
  en: {
    // Navigation
    'nav.chat': 'Chat',
    'nav.memory': 'Memory',
    'nav.models': 'Models',
    'nav.tools': 'Tools',
    'nav.bi': 'BI Analytics',
    'nav.knowledge': 'Knowledge',
    'nav.meeting': 'Meeting',
    'nav.settings': 'Settings',

    // Common
    'common.loading': 'Loading...',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.create': 'Create',
    'common.search': 'Search',
    'common.install': 'Install',
    'common.uninstall': 'Uninstall',
    'common.enable': 'Enable',
    'common.disable': 'Disable',
    'common.close': 'Close',
    'common.confirm': 'Confirm',
    'common.success': 'Success',
    'common.error': 'Error',
    'common.send': 'Send',
    'common.reset': 'Reset',
    'common.test': 'Test',
    'common.back': 'Back',
    'common.backToChat': 'Back to Chat',
    'common.enabled': 'Enabled',
    'common.disabled': 'Disabled',
    'common.model': 'Model',
    'common.notSelected': 'Not selected',
    'common.deleteFailed': 'Delete failed',

    // Desktop
    'desktop.default.title': 'TARS Workspace',
    'desktop.default.subtitle': 'Unified workspace shell',
    'desktop.chat.title': 'Chat Workspace',
    'desktop.chat.subtitle': 'Handle conversations, plans, files, and reminders in one primary workspace.',
    'desktop.memory.title': 'Memory Workspace',
    'desktop.memory.subtitle': 'Manage personality, recent and long-term memory, and compression with a clearer structure.',
    'desktop.settings.title': 'System Settings',
    'desktop.settings.subtitle': 'Manage sub-agents, users, and desktop workspace configuration in one place.',
    'desktop.models.title': 'Model Center',
    'desktop.models.subtitle': 'Switch local and remote models, and manage endpoints and connectivity.',
    'desktop.tools.title': 'Tools and Skills',
    'desktop.tools.subtitle': 'Browse built-in tools, installed skills, and the SkillHub ecosystem.',
    'desktop.bi.title': 'BI Console',
    'desktop.bi.subtitle': 'Manage data sources, run SQL, and turn results into charts.',
    'desktop.meeting.title': 'Meeting Workspace',
    'desktop.meeting.subtitle': 'Bring recording, uploads, transcription, and review into one desktop flow.',
    'desktop.knowledge.title': 'Knowledge Base',
    'desktop.knowledge.subtitle': 'Create knowledge bases, upload documents, and verify retrieval results directly.',

    // Sidebar
    'sidebar.currentModel': 'Current Model',
    'sidebar.ollama': 'Ollama',
    'sidebar.custom': 'Custom',
    'sidebar.openrouter': 'OpenRouter',
    'sidebar.addCustomModel': 'Add Custom Model',
    'sidebar.configureOpenrouter': 'Configure OpenRouter in Settings',
    'sidebar.goToSettings': 'Go to Settings →',
    'sidebar.collapse': 'Collapse sidebar',
    'sidebar.expand': 'Expand sidebar',
    'sidebar.switchedTo': 'Switched to',
    'sidebar.switchFailed': 'Switch failed',
    'sidebar.language': 'Language',
    'sidebar.localModels': 'Local models',
    'sidebar.noEndpointModels': 'No models yet — fetch or add on the Models page',
    'sidebar.modelConfigLink': 'Model settings',

    // Chat
    'chat.title': 'TARS Agent',
    'chat.subtitle': 'AI Assistant',
    'chat.connected': 'Connected',
    'chat.disconnected': 'Disconnected',
    'chat.placeholder': 'Type a message...',
    'chat.welcome': 'Welcome to TARS Agent',
    'chat.welcomeHint': 'Start a conversation to get started',
    'chat.thinking': 'TARS is thinking...',
    'chat.uploadFailed': 'Upload failed',
    'chat.fileTooLarge': 'File exceeds 50MB limit, provide file path for direct tool read',
    'chat.maxFiles': 'Maximum 5 files per message',
    'chat.uploadTooltip': 'Upload file',
    'chat.newChat': 'New Chat',
    'chat.noSessions': 'No sessions yet',
    'chat.deleteConfirm': 'Delete this session?',
    'chat.sessionDeleted': 'Session deleted',

    // Tools
    'tools.title': 'Tools Center',
    'tools.subtitle': 'Manage tools and skills',
    'tools.addSkill': 'Add Skill',
    'tools.tabBuiltin': 'Built-in Tools',
    'tools.tabSkills': 'Installed Skills',
    'tools.tabSkillhub': 'SkillHub Store',
    'tools.searchPlaceholder': 'Search...',
    'tools.noTools': 'No tools found',
    'tools.noSkills': 'No skills installed',
    'tools.hubSearchPlaceholder': 'Search SkillHub skills...',
    'tools.hubSearchHint': 'Enter keywords to search community skills',
    'tools.installing': 'Installing...',
    'tools.searching': 'Searching...',
    'tools.installed': 'Installed',
    'tools.reinstall': 'Reinstall',
    'tools.installSuccess': 'Install successful',
    'tools.installFailed': 'Install failed',
    'tools.browseCatalog': 'Browse Catalog',
    'tools.catalogEmpty': 'Catalog is empty',
    'tools.filterAll': 'All',
    'tools.filterPlugin': 'Tools',
    'tools.filterPrompt': 'Prompts',
    'tools.usageTitle': 'Usage',
    'tools.compatible': 'Compatible',
    'tools.incompatible': 'Incompatible',

    // Tool Detail
    'toolDetail.description': 'Description',
    'toolDetail.tags': 'Tags',
    'toolDetail.promptTemplate': 'Prompt Template',
    'toolDetail.parameters': 'Parameters',
    'toolDetail.permissions': 'Permissions',
    'toolDetail.usage': 'Usage',
    'toolDetail.required': 'Required',
    'toolDetail.defaultValue': 'Default',
    'toolDetail.builtin': 'Built-in Tool',
    'toolDetail.plugin': 'Plugin Skill',
    'toolDetail.prompt': 'Prompt Skill',
    'toolDetail.uninstallConfirm': 'Are you sure you want to uninstall this skill?',
    'toolDetail.uninstalled': 'Skill uninstalled',
    'toolDetail.enabledMsg': 'Skill enabled',
    'toolDetail.disabledMsg': 'Skill disabled',
    'toolDetail.operationFailed': 'Operation failed',

    // Add Skill Modal
    'addSkill.title': 'Create Prompt Skill',
    'addSkill.id': 'ID',
    'addSkill.idPlaceholder': 'my_skill (lowercase + underscore)',
    'addSkill.name': 'Name',
    'addSkill.namePlaceholder': 'My Skill',
    'addSkill.description': 'Description',
    'addSkill.descPlaceholder': 'Skill description',
    'addSkill.tags': 'Tags (comma separated)',
    'addSkill.tagsPlaceholder': 'writing, creative',
    'addSkill.template': 'Prompt Template',
    'addSkill.templatePlaceholder': 'You are an expert in XXX. Follow these principles:\n1. ...\n2. ...',
    'addSkill.templateHint': 'The prompt template is injected into the system prompt during conversations',
    'addSkill.fillRequired': 'Please fill in all required fields',
    'addSkill.creating': 'Creating...',
    'addSkill.createFailed': 'Creation failed',

    // Models
    'models.title': 'Model Config',
    'models.subtitle': 'Manage AI Model Providers',
    'models.backToChat': 'Back to Chat',
    'models.ollama': 'Ollama (Local)',
    'models.ollamaDesc': 'Local LLMs with privacy and fast response',
    'models.openrouter': 'OpenRouter',
    'models.openrouterDesc': 'Multiple cloud models, rich selection',
    'models.anthropic': 'Anthropic (Claude)',
    'models.anthropicDesc': 'Anthropic Claude series',
    'models.openai': 'OpenAI (GPT)',
    'models.openaiDesc': 'OpenAI GPT series',

    'modelsPage.ollamaBlock': 'Ollama (local)',
    'modelsPage.ollamaEnvHint': 'URL comes from OLLAMA_BASE_URL; read-only here.',
    'modelsPage.ollamaEmpty': 'No local models detected. Run: ollama pull <model>',
    'modelsPage.remoteBlock': 'OpenAI-compatible endpoints',
    'modelsPage.addEndpoint': 'Add endpoint',
    'modelsPage.namePh': 'Display name, e.g. DeepSeek API',
    'modelsPage.baseUrlPh': 'Base URL, e.g. https://api.deepseek.com/v1',
    'modelsPage.apiKeyPh': 'API key (optional)',
    'modelsPage.noEndpoints': 'No remote endpoints yet.',
    'modelsPage.fetchModels': 'Fetch models',
    'modelsPage.noModelsHint': 'If auto-fetch fails, add model IDs manually.',
    'modelsPage.manualModels': 'Add models manually',
    'modelsPage.manualPlaceholder': 'One model ID per line, or comma-separated',
    'modelsPage.editEndpoint': 'Edit endpoint',
    'modelsPage.apiKeyLeaveBlank': 'Leave blank to keep the current API key',
    'modelsPage.modelsOnePerLine': 'Models (one per line)',
    'modelsPage.switched': 'Model switched',
    'modelsPage.fillRequired': 'Name and Base URL are required',
    'modelsPage.endpointCreated': 'Endpoint created',
    'modelsPage.deleteConfirm': 'Delete this endpoint?',
    'modelsPage.fetchOk': 'Fetched {count} models',
    'modelsPage.fetchOkPrefix': 'Fetched',
    'modelsPage.fetchEmpty': 'No models parsed; add manually',
    'modelsPage.manualEmpty': 'Enter at least one model ID',

    // Settings
    'settings.title': 'Settings',
    'settings.personality': 'Personality',
    'settings.subagents': 'Sub-Agents',
    'settings.users': 'Users',
  }
}

const LOCALE_KEY = 'tars_locale'

const interpolate = (template: string, params?: MessageParams): string => {
  if (!params) {
    return template
  }

  return Object.entries(params).reduce((result, [key, value]) => {
    return result.replaceAll(`{${key}}`, String(value))
  }, template)
}

// 全局响应式 locale（所有组件共享）
const globalLocale = ref<string>(localStorage.getItem(LOCALE_KEY) || 'zh')

export const useI18n = () => {
  const locale = globalLocale

  const t = (key: string, params?: MessageParams): string => {
    const message = messages[locale.value]?.[key] || messages['zh'][key] || key
    return interpolate(message, params)
  }

  const setLocale = (newLocale: string) => {
    if (messages[newLocale]) {
      locale.value = newLocale
      localStorage.setItem(LOCALE_KEY, newLocale)
    }
  }

  const toggleLocale = () => {
    const newLocale = locale.value === 'zh' ? 'en' : 'zh'
    setLocale(newLocale)
  }

  return {
    locale,
    t,
    setLocale,
    toggleLocale
  }
}

export default useI18n
