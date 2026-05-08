import { ref } from 'vue'

export const messages: Record<string, Record<string, string>> = {
  zh: {
    // 导航
    'nav.chat': '聊天',
    'nav.models': '模型',
    'nav.tools': '工具',
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
    'common.enabled': '已启用',
    'common.disabled': '已禁用',

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
    'chat.fileTooLarge': '文件超过 20MB 限制',
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

    // Settings
    'settings.title': '设置',
    'settings.personality': '人格设置',
    'settings.subagents': '子代理',
    'settings.users': '用户管理',
  },
  en: {
    // Navigation
    'nav.chat': 'Chat',
    'nav.models': 'Models',
    'nav.tools': 'Tools',
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
    'common.enabled': 'Enabled',
    'common.disabled': 'Disabled',

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
    'chat.fileTooLarge': 'File exceeds 20MB limit',
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

    // Settings
    'settings.title': 'Settings',
    'settings.personality': 'Personality',
    'settings.subagents': 'Sub-Agents',
    'settings.users': 'Users',
  }
}

const LOCALE_KEY = 'tars_locale'

// 全局响应式 locale（所有组件共享）
const globalLocale = ref<string>(localStorage.getItem(LOCALE_KEY) || 'zh')

export const useI18n = () => {
  const locale = globalLocale

  const t = (key: string): string => {
    return messages[locale.value]?.[key] || messages['zh'][key] || key
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
